import os, subprocess, time
import pandas as pd
os.chdir('/home/shubham-pal/NetPrompt/experimentations')

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Switch
from mininet.log import setLogLevel, info

P4_PROGRAMS = {
    'forward':         ('forward.p4',         'MyIngress.ipv4_lpm', 'forward'),
    'forwardChatGPT':  ('forwardChatGPT.p4',  'MyIngress.ipv4_lpm', 'forward'),
    'forwardClaude':   ('forwardClaude.p4',   'MyIngress.ipv4_lpm', 'ipv4_forward'),
    'forwardDeepseek': ('forwardDeepseek.p4', None, None),
}

def run_cli(cmds):
    result = subprocess.run(
        ['simple_switch_CLI', '--thrift-port', '9090'],
        input=cmds, capture_output=True, text=True, timeout=10
    )
    print(result.stdout)
    return result

def compile_p4(p4_file):
    json_out = p4_file.replace('.p4', '.json')
    if os.path.exists(json_out):
        print(f"  {json_out} exists, skipping compile.")
        return json_out
    print(f"  Compiling {p4_file}...")
    r = subprocess.run(
        ['p4c', '--target', 'bmv2', '--arch', 'v1model', '-o', '.', p4_file],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  FAILED:\n{r.stderr[:300]}")
        return None
    print(f"  OK → {json_out}")
    return json_out

class P4Switch(Switch):
    def __init__(self, name, json_file, thrift_port=9090, **params):
        Switch.__init__(self, name, **params)
        self.json_file = json_file
        self.thrift_port = thrift_port

    def start(self, controllers):
        intf_args = " ".join(
            f"--interface {idx}@{intf.name}"
            for idx, intf in enumerate(self.intfList()) if intf.name != "lo"
        )
        cmd = (f"simple_switch --thrift-port {self.thrift_port} "
               f"--log-file /tmp/bmv2.log --log-flush {intf_args} {self.json_file} &")
        os.system(cmd)
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

def run_experiment(name, json_file, table, action):
    print(f"\n{'='*50}\n  {name}\n{'='*50}")
    os.system("pkill -f simple_switch 2>/dev/null; mn -c 2>/dev/null; sleep 2")

    net = Mininet(topo=NetworkTopo(json_file), controller=None)
    result = {'name': name, 'pingall': 'FAIL', 'rtt_avg': 'N/A', 'pkt_loss': '100%'}

    try:
        net.start()
        time.sleep(3)
        run_cli('mc_mgrp_create 1\nmc_node_create 0 1 2\nmc_node_associate 1 0\n')
        time.sleep(1)
        if table and action:
            run_cli(f'table_add {table} {action} 10.0.1.1/32 => 0\n'
                    f'table_add {table} {action} 10.0.1.2/32 => 1\n')
            time.sleep(1)

        h1, h2 = net.get('h1', 'h2')
        h1.cmd('ifconfig h1-eth0 10.0.1.1/24 up')
        h2.cmd('ifconfig h2-eth0 10.0.1.2/24 up')
        h1.cmd('arp -i h1-eth0 -s 10.0.1.2 00:00:00:00:01:02')
        h2.cmd('arp -i h2-eth0 -s 10.0.1.1 00:00:00:00:01:01')
        h1.cmd('ip route add 10.0.1.0/24 dev h1-eth0')
        h2.cmd('ip route add 10.0.1.0/24 dev h2-eth0')

        pa = net.pingAll(timeout=3)
        result['pingall'] = f'{100-pa:.0f}% success'

        ping_out = h1.cmd('ping -c 5 -W 2 10.0.1.2')
        print(ping_out)

        for line in ping_out.split('\n'):
            if 'rtt' in line and 'avg' in line:
                result['rtt_avg'] = f"{float(line.split('/')[4]):.3f} ms"
            if 'packet loss' in line:
                result['pkt_loss'] = line.split('%')[0].split()[-1] + '%'

    except Exception as e:
        print(f"  ERROR: {e}")
    finally:
        net.stop()
        os.system("pkill -f simple_switch 2>/dev/null")
        time.sleep(2)

    return result

setLogLevel('warning')
results = []

for name, (p4_file, table, action) in P4_PROGRAMS.items():
    json_file = compile_p4(p4_file)
    if not json_file:
        results.append({'name': name, 'pingall': 'COMPILE_FAIL', 'rtt_avg': 'N/A', 'pkt_loss': '100%'})
        continue
    results.append(run_experiment(name, json_file, table, action))
    time.sleep(3)

print("\n" + "="*60)
print("  FORWARD P4 — LLM COMPARISON RESULTS")
print("="*60)
df = pd.DataFrame(results)
print(df.to_string(index=False))
df.to_csv('forward_comparison.csv', index=False)
print("\nSaved to forward_comparison.csv")
