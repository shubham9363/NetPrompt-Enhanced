"""
Multi-LLM Consensus Voter
Improvement 2: Runs multiple LLM-generated P4 programs through
compile + functional test + scoring + consensus voting.
"""

import os, subprocess, time
import pandas as pd
os.chdir('/home/shubham-pal/NetPrompt_Research/experimentations')

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Switch
from mininet.log import setLogLevel

LLM_CANDIDATES = {
    'ChatGPT': ('forwardChatGPT.p4',  'MyIngress.ipv4_lpm', 'forward'),
    'Claude':  ('forwardClaude.p4',   'MyIngress.ipv4_lpm', 'ipv4_forward'),
    'Deepseek':('forwardDeepseek.p4', 'MyIngress.mac_table', 'forward_to_port'),
    'Baseline':('forward.p4',         'MyIngress.ipv4_lpm', 'forward'),
}

def run_cli(cmds):
    r = subprocess.run(['simple_switch_CLI', '--thrift-port', '9090'],
                       input=cmds, capture_output=True, text=True, timeout=10)
    return r

def validate_compile(p4_file):
    json_out = p4_file.replace('.p4', '.json')
    r = subprocess.run(['p4c', '--target', 'bmv2', '--arch', 'v1model', '-o', '.', p4_file],
                       capture_output=True, text=True)
    errors = r.stderr.count('[--Werror=')
    return r.returncode == 0, errors, json_out if r.returncode == 0 else None

class P4Switch(Switch):
    def __init__(self, name, json_file, thrift_port=9090, **params):
        Switch.__init__(self, name, **params)
        self.json_file = json_file
        self.thrift_port = thrift_port
    def start(self, controllers):
        intf_args = " ".join(f"--interface {idx}@{intf.name}"
                             for idx, intf in enumerate(self.intfList()) if intf.name != "lo")
        os.system(f"simple_switch --thrift-port {self.thrift_port} "
                  f"--log-file /tmp/bmv2_voter.log --log-flush {intf_args} {self.json_file} &")
        time.sleep(4)
    def stop(self):
        os.system("pkill -f simple_switch 2>/dev/null")

class NetworkTopo(Topo):
    def __init__(self, json_file):
        Topo.__init__(self)
        s1 = self.addSwitch('s1', cls=P4Switch, json_file=json_file, thrift_port=9090)
        h1 = self.addHost('h1', ip='10.0.1.1/24', mac='00:00:00:00:01:01')
        h2 = self.addHost('h2', ip='10.0.1.2/24', mac='00:00:00:00:01:02')
        self.addLink(h1, s1, port1=0, port2=0)
        self.addLink(h2, s1, port1=0, port2=1)

def functional_test(json_file, table, action):
    os.system("pkill -f simple_switch 2>/dev/null; mn -c 2>/dev/null; sleep 2")
    net = Mininet(topo=NetworkTopo(json_file), controller=None)
    loss, rtt = 100.0, None
    try:
        net.start(); time.sleep(3)
        run_cli('mc_mgrp_create 1\nmc_node_create 0 1 2\nmc_node_associate 1 0\n')
        time.sleep(1)
        if table and action:
            run_cli(f'table_add {table} {action} 10.0.1.1/32 => 0\n'
                    f'table_add {table} {action} 10.0.1.2/32 => 1\n')
        time.sleep(1)
        h1, h2 = net.get('h1'), net.get('h2')
        h1.cmd('ifconfig h1-eth0 10.0.1.1/24 up')
        h2.cmd('ifconfig h2-eth0 10.0.1.2/24 up')
        h1.cmd('arp -i h1-eth0 -s 10.0.1.2 00:00:00:00:01:02')
        h2.cmd('arp -i h2-eth0 -s 10.0.1.1 00:00:00:00:01:01')
        h1.cmd('ip route add 10.0.1.0/24 dev h1-eth0')
        h2.cmd('ip route add 10.0.1.0/24 dev h2-eth0')
        ping = h1.cmd('ping -c 10 -W 2 10.0.1.2')
        for line in ping.split('\n'):
            if 'packet loss' in line:
                loss = float(line.split('%')[0].split()[-1])
            if 'rtt' in line and 'avg' in line:
                rtt = float(line.split('/')[4])
    except Exception as e:
        print(f"    Error: {e}")
    finally:
        net.stop()
        os.system("pkill -f simple_switch 2>/dev/null")
        time.sleep(2)
    return loss, rtt

def score(compile_ok, errors, loss, rtt, all_rtts):
    s = 0
    if compile_ok:
        s += max(0, 40 - errors * 5)
    if loss == 0.0:
        s += 40
    elif loss < 50:
        s += 40 * (1 - loss/100)
    if rtt is not None:
        valid = [r for r in all_rtts if r is not None]
        if valid and max(valid) > min(valid):
            s += 20 * (1 - (rtt - min(valid))/(max(valid) - min(valid)))
        else:
            s += 20
    return round(s, 2)

def vote(results):
    passing = {k: v for k, v in results.items() if v['loss'] == 0.0}
    score_winner = max(results, key=lambda k: results[k]['score'])
    conservative = min(passing, key=lambda k: passing[k]['rtt'] or 9999) if passing else None
    return score_winner, conservative, len(passing)

def main():
    setLogLevel('warning')
    print("\n" + "="*60)
    print("  Multi-LLM Consensus Voter")
    print("="*60)

    results = {}
    all_rtts = []

    print("\n--- Phase 1: Compile ---")
    compile_data = {}
    for llm, (p4, table, action) in LLM_CANDIDATES.items():
        ok, errors, json_out = validate_compile(p4)
        compile_data[llm] = (ok, errors, json_out, table, action)
        print(f"  {llm:10s}: {'PASS' if ok else 'FAIL'}  errors={errors}")

    print("\n--- Phase 2: Functional Test ---")
    for llm, (ok, errors, json_out, table, action) in compile_data.items():
        if not ok:
            results[llm] = {'compile': False, 'errors': errors, 'loss': 100.0, 'rtt': None, 'score': 0}
            continue
        print(f"  {llm:10s}: testing...", end='', flush=True)
        loss, rtt = functional_test(json_out, table, action)
        all_rtts.append(rtt)
        print(f" loss={loss:.0f}%  rtt={f'{rtt:.3f}ms' if rtt else 'N/A'}")
        results[llm] = {'compile': ok, 'errors': errors, 'loss': loss, 'rtt': rtt, 'score': 0}

    print("\n--- Phase 3: Scoring ---")
    for llm in results:
        r = results[llm]
        r['score'] = score(r['compile'], r['errors'], r['loss'], r['rtt'], all_rtts)
        print(f"  {llm:10s}: score={r['score']:5.1f}")

    print("\n--- Phase 4: Voting ---")
    score_winner, conservative, passing_count = vote(results)
    print(f"  Passing programs:   {passing_count}/{len(results)}")
    print(f"  Score vote winner:  {score_winner}")
    print(f"  Conservative pick:  {conservative}")

    df = pd.DataFrame([{
        'LLM': llm,
        'Compiles': 'YES' if r['compile'] else 'NO',
        'Loss': f"{r['loss']:.0f}%",
        'RTT': f"{r['rtt']:.3f}ms" if r['rtt'] else 'N/A',
        'Score': r['score'],
        'Status': 'PASS' if r['loss']==0 else 'FAIL'
    } for llm, r in results.items()])

    print("\n--- Final Results ---")
    print(df.to_string(index=False))
    df.to_csv('voting_results.csv', index=False)

    broken = [k for k in results if results[k]['loss'] > 0]
    final = conservative or score_winner
    print(f"\n  Selected program: {final}")
    print(f"  Rejected broken:  {broken}")
    print(f"  Reliability gain: {len(broken)}/{len(results)} bad programs eliminated")
    print("="*60)

if __name__ == '__main__':
    main()
