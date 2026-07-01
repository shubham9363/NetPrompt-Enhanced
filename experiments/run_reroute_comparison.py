import os, subprocess, time
import pandas as pd
os.chdir('/home/shubham-pal/NetPrompt/experimentations')

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Switch
from mininet.link import TCLink
from mininet.log import setLogLevel, info, error

P4_PROGRAMS = {
    'fast_reroute':         'fast_reroute.json',
    'fast_reroute_claude':  'fast_reroute_claude.json',
    'fast_reroute_chatgpt': 'fast_reroute_chatgpt.json',
    'fast_reroute_deepseek':'fast_reroute_deepseek.json',
}

def run_cli(thrift_port, cmds):
    r = subprocess.run(
        ['simple_switch_CLI', '--thrift-port', str(thrift_port)],
        input='\n'.join(cmds), capture_output=True, text=True, timeout=30
    )
    if 'Error' in r.stdout:
        print(f"  CLI errors on port {thrift_port}:", r.stdout[:300])
    return r

class P4Switch(Switch):
    def __init__(self, name, json_file, thrift_port, device_id, **params):
        Switch.__init__(self, name, **params)
        self.json_file = json_file
        self.thrift_port = thrift_port
        self.device_id = device_id
        self.proc = None

    def start(self, controllers):
        cmd = ['simple_switch',
               '--thrift-port', str(self.thrift_port),
               '--device-id', str(self.device_id),
               '--log-file', f'/tmp/bmv2_{self.name}.log', '--log-flush',
               self.json_file]
        for idx, intf in enumerate(self.intfList()):
            if intf.name != "lo":
                cmd.extend(['-i', f"{idx+1}@{intf.name}"])
        self.proc = subprocess.Popen(cmd, stdout=open(f'/tmp/{self.name}.log','w'), stderr=subprocess.STDOUT)
        time.sleep(4)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()

class FastRerouteTopo(Topo):
    def __init__(self, json_file):
        Topo.__init__(self)
        switches = []
        for i in range(1, 4):
            sw = self.addSwitch(f's{i}', cls=P4Switch, json_file=json_file,
                                thrift_port=9090+(i-1), device_id=i)
            switches.append(sw)
        hosts = []
        for i in range(1, 4):
            host = self.addHost(f'h{i}', ip=f'10.0.{i}.1/24',
                                mac=f'00:00:00:00:0{i}:01',
                                defaultRoute=f'via 10.0.{i}.254')
            hosts.append(host)
            self.addLink(host, switches[i-1], port1=0, port2=2, cls=TCLink, bw=100, delay='1ms')
        # Primary links
        self.addLink(switches[0], switches[1], port1=3, port2=3, cls=TCLink, bw=50, delay='1ms')
        self.addLink(switches[1], switches[2], port1=4, port2=3, cls=TCLink, bw=50, delay='1ms')
        self.addLink(switches[2], switches[0], port1=4, port2=4, cls=TCLink, bw=50, delay='1ms')
        # Backup links
        self.addLink(switches[0], switches[1], port1=5, port2=5, cls=TCLink, bw=30, delay='10ms')
        self.addLink(switches[1], switches[2], port1=6, port2=5, cls=TCLink, bw=30, delay='10ms')
        self.addLink(switches[2], switches[0], port1=6, port2=6, cls=TCLink, bw=30, delay='10ms')

def configure_switches(net, set_routes_action='set_routes', backup_action='set_backup_nhop'):
    s1 = net.get('s1')
    s2 = net.get('s2')
    s3 = net.get('s3')

    for sw in [s1, s2, s3]:
        run_cli(sw.thrift_port, [
            'register_write link_status 2 1',
            'register_write link_status 3 1',
            'register_write link_status 4 1',
            'register_write link_status 5 1',
            'register_write link_status 6 1',
        ])

    run_cli(s1.thrift_port, [
        f'table_add arp_table generate_arp_reply 10.0.1.254 => 00:00:00:00:01:01 10.0.1.254',
        f'table_add ipv4_lpm {set_routes_action} 10.0.1.1/32 => 2 00:00:00:00:01:01 0 00:00:00:00:00:00 00:00:00:00:01:01',
        f'table_add ipv4_lpm {set_routes_action} 10.0.2.1/32 => 3 00:00:00:00:02:02 5 00:00:00:00:02:04 00:00:00:00:01:02',
        f'table_add ipv4_lpm {set_routes_action} 10.0.3.1/32 => 4 00:00:00:00:03:03 6 00:00:00:00:03:06 00:00:00:00:01:03',
        f'table_add backup_routes {backup_action} 10.0.2.1/32 => 00:00:00:00:02:04 5 00:00:00:00:01:04',
        f'table_add backup_routes {backup_action} 10.0.3.1/32 => 00:00:00:00:03:06 6 00:00:00:00:01:06',
    ])

    run_cli(s2.thrift_port, [
        f'table_add arp_table generate_arp_reply 10.0.2.254 => 00:00:00:00:02:01 10.0.2.254',
        f'table_add ipv4_lpm {set_routes_action} 10.0.2.1/32 => 2 00:00:00:00:02:01 0 00:00:00:00:00:00 00:00:00:00:02:01',
        f'table_add ipv4_lpm {set_routes_action} 10.0.3.1/32 => 4 00:00:00:00:03:03 6 00:00:00:00:03:05 00:00:00:00:02:03',
        f'table_add ipv4_lpm {set_routes_action} 10.0.1.1/32 => 3 00:00:00:00:01:02 5 00:00:00:00:01:04 00:00:00:00:02:02',
        f'table_add backup_routes {backup_action} 10.0.3.1/32 => 00:00:00:00:03:05 6 00:00:00:00:02:05',
        f'table_add backup_routes {backup_action} 10.0.1.1/32 => 00:00:00:00:01:04 5 00:00:00:00:02:04',
    ])

    run_cli(s3.thrift_port, [
        f'table_add arp_table generate_arp_reply 10.0.3.254 => 00:00:00:00:03:01 10.0.3.254',
        f'table_add ipv4_lpm {set_routes_action} 10.0.3.1/32 => 2 00:00:00:00:03:01 0 00:00:00:00:00:00 00:00:00:00:03:01',
        f'table_add ipv4_lpm {set_routes_action} 10.0.1.1/32 => 4 00:00:00:00:01:03 6 00:00:00:00:01:06 00:00:00:00:03:02',
        f'table_add ipv4_lpm {set_routes_action} 10.0.2.1/32 => 3 00:00:00:00:02:03 5 00:00:00:00:02:05 00:00:00:00:03:03',
        f'table_add backup_routes {backup_action} 10.0.1.1/32 => 00:00:00:00:01:06 6 00:00:00:00:03:06',
        f'table_add backup_routes {backup_action} 10.0.2.1/32 => 00:00:00:00:02:05 5 00:00:00:00:03:05',
    ])


def configure_chatgpt(net):
    """ChatGPT: set_primary_route(port, mac), set_backup_route(port, mac), exact dstAddr match"""
    s1, s2, s3 = net.get('s1'), net.get('s2'), net.get('s3')
    for sw in [s1, s2, s3]:
        run_cli(sw.thrift_port, [
            'register_write link_status_reg 2 1',
            'register_write link_status_reg 3 1',
            'register_write link_status_reg 4 1',
            'register_write link_status_reg 5 1',
            'register_write link_status_reg 6 1',
        ])
    run_cli(s1.thrift_port, [

        'table_add ipv4_lpm set_primary_route 10.0.1.1/32 => 2 00:00:00:00:01:01',
        'table_add ipv4_lpm set_primary_route 10.0.2.1/32 => 3 00:00:00:00:02:02',
        'table_add ipv4_lpm set_primary_route 10.0.3.1/32 => 4 00:00:00:00:03:03',
        'table_add backup_routes set_backup_route 10.0.2.1 => 5 00:00:00:00:02:04',
        'table_add backup_routes set_backup_route 10.0.3.1 => 6 00:00:00:00:03:06',
    ])
    run_cli(s2.thrift_port, [

        'table_add ipv4_lpm set_primary_route 10.0.2.1/32 => 2 00:00:00:00:02:01',
        'table_add ipv4_lpm set_primary_route 10.0.3.1/32 => 4 00:00:00:00:03:03',
        'table_add ipv4_lpm set_primary_route 10.0.1.1/32 => 3 00:00:00:00:01:02',
        'table_add backup_routes set_backup_route 10.0.3.1 => 6 00:00:00:00:03:05',
        'table_add backup_routes set_backup_route 10.0.1.1 => 5 00:00:00:00:01:04',
    ])
    run_cli(s3.thrift_port, [

        'table_add ipv4_lpm set_primary_route 10.0.3.1/32 => 2 00:00:00:00:03:01',
        'table_add ipv4_lpm set_primary_route 10.0.1.1/32 => 4 00:00:00:00:01:03',
        'table_add ipv4_lpm set_primary_route 10.0.2.1/32 => 3 00:00:00:00:02:03',
        'table_add backup_routes set_backup_route 10.0.1.1 => 6 00:00:00:00:01:06',
        'table_add backup_routes set_backup_route 10.0.2.1 => 5 00:00:00:00:02:05',
    ])

def configure_deepseek(net):
    """Deepseek: MyIngress.forward(port) for ipv4_lpm/backup_routes, link_status register"""
    s1, s2, s3 = net.get('s1'), net.get('s2'), net.get('s3')
    for sw in [s1, s2, s3]:
        run_cli(sw.thrift_port, [
            'register_write link_status 2 1',
            'register_write link_status 3 1',
            'register_write link_status 4 1',
            'register_write link_status 5 1',
            'register_write link_status 6 1',
        ])
    run_cli(s1.thrift_port, [
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:01:01 => 2',
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:02:01 => 3',
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:03:01 => 4',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.1.1/32 => 2',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.2.1/32 => 3',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.3.1/32 => 4',
        'table_add MyIngress.backup_routes MyIngress.forward 10.0.2.1 => 5',
        'table_add MyIngress.backup_routes MyIngress.forward 10.0.3.1 => 6',
    ])
    run_cli(s2.thrift_port, [
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:01:01 => 3',
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:02:01 => 2',
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:03:01 => 4',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.2.1/32 => 2',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.3.1/32 => 4',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.1.1/32 => 3',
        'table_add MyIngress.backup_routes MyIngress.forward 10.0.3.1 => 6',
        'table_add MyIngress.backup_routes MyIngress.forward 10.0.1.1 => 5',
    ])
    run_cli(s3.thrift_port, [
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:01:01 => 4',
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:02:01 => 3',
        'table_add MyIngress.arp_table MyIngress.forward 00:00:00:00:03:01 => 2',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.3.1/32 => 2',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.1.1/32 => 4',
        'table_add MyIngress.ipv4_lpm MyIngress.forward 10.0.2.1/32 => 3',
        'table_add MyIngress.backup_routes MyIngress.forward 10.0.1.1 => 6',
        'table_add MyIngress.backup_routes MyIngress.forward 10.0.2.1 => 5',
    ])

def run_experiment(name, json_file):
    print(f"\n{'='*50}\n  {name}\n{'='*50}")
    os.system("pkill -f simple_switch 2>/dev/null; mn -c 2>/dev/null; sleep 2")

    # Determine action names based on program
    net = Mininet(topo=FastRerouteTopo(json_file), controller=None)
    result = {'name': name, 'primary_ping': 'FAIL', 'primary_loss': '100%',
              'primary_rtt': 'N/A', 'reroute_works': 'N/A'}
    try:
        net.start()
        time.sleep(8)

        if 'chatgpt' in name:
            configure_chatgpt(net)
        elif 'deepseek' in name:
            configure_deepseek(net)
        else:
            configure_switches(net, 'set_routes', 'set_backup_nhop')
        time.sleep(2)

        h1, h2 = net.get('h1'), net.get('h2')

        h3 = net.get('h3')
        # Add routes so hosts can reach other subnets via switch
        h1.cmd('ip route add 10.0.2.0/24 via 10.0.1.254 dev h1-eth0')
        h1.cmd('ip route add 10.0.3.0/24 via 10.0.1.254 dev h1-eth0')
        h2.cmd('ip route add 10.0.1.0/24 via 10.0.2.254 dev h2-eth0')
        h2.cmd('ip route add 10.0.3.0/24 via 10.0.2.254 dev h2-eth0')
        h3.cmd('ip route add 10.0.1.0/24 via 10.0.3.254 dev h3-eth0')
        h3.cmd('ip route add 10.0.2.0/24 via 10.0.3.254 dev h3-eth0')
        # Static ARP entries
        h1.cmd('arp -s 10.0.1.254 00:00:00:00:01:01')
        h2.cmd('arp -s 10.0.2.254 00:00:00:00:02:01')
        h3.cmd('arp -s 10.0.3.254 00:00:00:00:03:01')
        time.sleep(1)

        print("--- Primary path ping h1->h2 ---")
        ping_out = h1.cmd('ping -c 5 -W 3 10.0.2.1')
        print(ping_out)

        for line in ping_out.split('\n'):
            if 'packet loss' in line:
                loss = line.split('%')[0].split()[-1]
                result['primary_loss'] = loss + '%'
                result['primary_ping'] = 'PASS' if loss == '0' else 'FAIL'
            if 'rtt' in line and 'avg' in line:
                result['primary_rtt'] = f"{float(line.split('/')[4]):.3f} ms"

    except Exception as e:
        print(f"  ERROR: {e}")
        result['primary_ping'] = f'ERROR'
    finally:
        net.stop()
        os.system("pkill -f simple_switch 2>/dev/null")
        time.sleep(3)

    return result

setLogLevel('warning')
results = []

for name, json_file in P4_PROGRAMS.items():
    if not os.path.exists(json_file):
        print(f"  {json_file} not found, skipping.")
        results.append({'name': name, 'primary_ping': 'NO_JSON',
                        'primary_loss': 'N/A', 'primary_rtt': 'N/A', 'reroute_works': 'N/A'})
        continue
    r = run_experiment(name, json_file)
    results.append(r)
    time.sleep(3)

print("\n" + "="*70)
print("  REROUTE P4 — LLM COMPARISON RESULTS")
print("="*70)
df = pd.DataFrame(results)
print(df.to_string(index=False))
df.to_csv('reroute_comparison.csv', index=False)
print("\nSaved to reroute_comparison.csv")
# This appends nothing - we need to edit inline
