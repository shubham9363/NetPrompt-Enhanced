import os
import subprocess
import time
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Switch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error

class P4Switch(Switch):
    def __init__(self, name, json_file, thrift_port, device_id, **params):
        Switch.__init__(self, name, **params)
        self.json_file = json_file
        self.thrift_port = thrift_port
        self.device_id = device_id
        self.proc = None

    def start(self, controllers):
        cmd = [
            'simple_switch',
            '--thrift-port', str(self.thrift_port),
            '--device-id', str(self.device_id),
            '--nanolog', f'ipc:///tmp/bm-{self.device_id}-log.ipc',
            '--log-console',
            self.json_file
        ]
        for idx, intf in enumerate(self.intfList()):
            if intf.name != "lo":
                cmd.extend(['-i', f"{idx+1}@{intf.name}"])
        info(f"Starting P4 switch {self.name}: {' '.join(cmd)}\n")
        self.proc = subprocess.Popen(
            cmd,
            stdout=open(f'{self.name}.log', 'w'),
            stderr=subprocess.STDOUT
        )
        time.sleep(1)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()

class FastRerouteTopo(Topo):
    def __init__(self, json_file):
        Topo.__init__(self)
        switches = []
        for i in range(1, 4):
            sw = self.addSwitch(
                f's{i}',
                cls=P4Switch,
                json_file=json_file,
                thrift_port=9090 + (i-1),
                device_id=i
            )
            switches.append(sw)

        hosts = []
        for i in range(1, 4):
            host = self.addHost(
                f'h{i}',
                ip=f'10.0.{i}.1/24',
                mac=f'00:00:00:00:0{i}:01',
                defaultRoute=f'via 10.0.{i}.254'
            )
            hosts.append(host)
            self.addLink(host, switches[i-1], port1=0, port2=2, cls=TCLink, bw=100, delay='1ms')

        # Primary links
        self.addLink(switches[0], switches[1], port1=3, port2=3, cls=TCLink, bw=50, delay='1ms')  # s1-s2
        self.addLink(switches[1], switches[2], port1=4, port2=3, cls=TCLink, bw=50, delay='1ms')  # s2-s3
        self.addLink(switches[2], switches[0], port1=4, port2=4, cls=TCLink, bw=50, delay='1ms')  # s3-s1

        # Backup links
        self.addLink(switches[0], switches[1], port1=5, port2=5, cls=TCLink, bw=30, delay='10ms')  # s1-s2
        self.addLink(switches[1], switches[2], port1=6, port2=5, cls=TCLink, bw=30, delay='10ms')  # s2-s3
        self.addLink(switches[2], switches[0], port1=6, port2=6, cls=TCLink, bw=30, delay='10ms')  # s3-s1

def configure_switch(sw):
    thrift_port = sw.thrift_port
    config = [
        'register_write link_status 2 1',  # Port to host
        'register_write link_status 3 1',  # Primary port
        'register_write link_status 4 1',  # Primary port
        'register_write link_status 5 1',  # Backup port
        'register_write link_status 6 1',  # Backup port
    ]

    if sw.name == 's1':
        config += [
            'table_add arp_table generate_arp_reply 10.0.1.254 => 00:00:00:00:01:01 10.0.1.254',
            'table_add ipv4_lpm set_routes 10.0.1.1/32 => 2 00:00:00:00:01:01 0 00:00:00:00:00:00 00:00:00:00:01:01',
            'table_add ipv4_lpm set_routes 10.0.2.1/32 => 3 00:00:00:00:02:02 5 00:00:00:00:02:04 00:00:00:00:01:02',
            'table_add ipv4_lpm set_routes 10.0.3.1/32 => 4 00:00:00:00:03:03 6 00:00:00:00:03:06 00:00:00:00:01:03',
            'table_add backup_routes set_backup_nhop 10.0.2.1/32 => 00:00:00:00:02:04 5 00:00:00:00:01:04',
            'table_add backup_routes set_backup_nhop 10.0.3.1/32 => 00:00:00:00:03:06 6 00:00:00:00:01:06',
        ]
    elif sw.name == 's2':
        config += [
            'table_add arp_table generate_arp_reply 10.0.2.254 => 00:00:00:00:02:01 10.0.2.254',
            'table_add ipv4_lpm set_routes 10.0.2.1/32 => 2 00:00:00:00:02:01 0 00:00:00:00:00:00 00:00:00:00:02:01',
            'table_add ipv4_lpm set_routes 10.0.3.1/32 => 4 00:00:00:00:03:03 6 00:00:00:00:03:05 00:00:00:00:02:03',
            'table_add ipv4_lpm set_routes 10.0.1.1/32 => 3 00:00:00:00:01:02 5 00:00:00:00:01:04 00:00:00:00:02:02',
            'table_add backup_routes set_backup_nhop 10.0.3.1/32 => 00:00:00:00:03:05 6 00:00:00:00:02:05',
            'table_add backup_routes set_backup_nhop 10.0.1.1/32 => 00:00:00:00:01:04 5 00:00:00:00:02:04',
        ]
    elif sw.name == 's3':
        config += [
            'table_add arp_table generate_arp_reply 10.0.3.254 => 00:00:00:00:03:01 10.0.3.254',
            'table_add ipv4_lpm set_routes 10.0.3.1/32 => 2 00:00:00:00:03:01 0 00:00:00:00:00:00 00:00:00:00:03:01',
            'table_add ipv4_lpm set_routes 10.0.1.1/32 => 4 00:00:00:00:01:03 6 00:00:00:00:01:06 00:00:00:00:03:02',
            'table_add ipv4_lpm set_routes 10.0.2.1/32 => 3 00:00:00:00:02:03 5 00:00:00:00:02:05 00:00:00:00:03:03',
            'table_add backup_routes set_backup_nhop 10.0.1.1/32 => 00:00:00:00:01:06 6 00:00:00:00:03:06',
            'table_add backup_routes set_backup_nhop 10.0.2.1/32 => 00:00:00:00:02:05 5 00:00:00:00:03:05',
        ]

    try:
        subprocess.run(
            ['simple_switch_CLI', '--thrift-port', str(thrift_port)],
            input='\n'.join(config),
            text=True,
            check=True,
            timeout=10
        )
        info(f"Configured switch {sw.name} successfully\n")
    except subprocess.SubprocessError as e:
        error(f"Failed to configure {sw.name}: {str(e)}\n")

def read_registers(net, switch_name, thrift_port, output_file):
    info(f"\n*** {switch_name} Registers:\n")
    with open(output_file, 'w') as f:
        subprocess.run(f"echo 'register_read link_status' | simple_switch_CLI --thrift-port {thrift_port}", shell=True, stdout=f)
        subprocess.run(f"echo 'register_read backup_counter' | simple_switch_CLI --thrift-port {thrift_port}", shell=True, stdout=f)
        subprocess.run(f"echo 'register_read drop_counter' | simple_switch_CLI --thrift-port {thrift_port}", shell=True, stdout=f)
        subprocess.run(f"echo 'register_read active_port' | simple_switch_CLI --thrift-port {thrift_port}", shell=True, stdout=f)
        subprocess.run(f"echo 'register_read h1_to_h2_active_port' | simple_switch_CLI --thrift-port {thrift_port}", shell=True, stdout=f)
    with open(output_file, 'r') as f:
        info(f.read())

def log_registers_periodically(net, switch_name, thrift_port, base_filename):
    for i in range(20):  # Log every 2 seconds for 40 seconds
        time.sleep(2)
        timestamp = i * 2
        output_file = f"{base_filename}_t{timestamp}.txt"
        info(f"*** Logging {switch_name} Registers at {timestamp} seconds\n")
        with open(output_file, 'w') as f:
            subprocess.run(f"echo 'register_read h1_to_h2_active_port' | simple_switch_CLI --thrift-port {thrift_port}", shell=True, stdout=f)
        with open(output_file, 'r') as f:
            info(f.read())

def compile_p4_program(p4_file):
    json_file = p4_file.replace('.p4', '.json')
    try:
        result = subprocess.run(
            ['p4c-bm2-ss', '--std', 'p4-16', '-o', json_file, p4_file],
            check=True,
            capture_output=True,
            text=True
        )
        info("P4 compilation succeeded:\n" + result.stderr + "\n")
        return json_file
    except subprocess.CalledProcessError as e:
        error("P4 compilation failed:\n" + e.stderr + "\n")
        return None

def execute_switch_cmd(net, switch_name, thrift_port, cmd):
    try:
        result = subprocess.run(
            ['simple_switch_CLI', '--thrift-port', str(thrift_port)],
            input=cmd,
            text=True,
            capture_output=True,
            check=True,
            timeout=5
        )
        info(f"Executed '{cmd}' on {switch_name}: {result.stdout}\n")
        return True
    except subprocess.SubprocessError as e:
        error(f"Failed to execute '{cmd}' on {switch_name}: {e.stderr}\n")
        return False

def verify_link_delays(net):
    info("*** Verifying link delays\n")
    s1 = net.get('s1')
    s2 = net.get('s2')
    # Verify primary link (should be 1ms)
    info("Primary link s1-eth3 delay:\n")
    s1.cmdPrint('tc qdisc show dev s1-eth3')
    info("Primary link s2-eth3 delay:\n")
    s2.cmdPrint('tc qdisc show dev s2-eth3')
    # Verify backup link (should be 10ms)
    info("Backup link s1-eth5 delay:\n")
    s1.cmdPrint('tc qdisc show dev s1-eth5')
    info("Backup link s2-eth5 delay:\n")
    s2.cmdPrint('tc qdisc show dev s2-eth5')
    # Ensure backup link delay is set correctly
    s1.cmd('tc qdisc replace dev s1-eth5 root netem delay 10ms')
    s2.cmd('tc qdisc replace dev s2-eth5 root netem delay 10ms')
    info("Backup link delays set to 10ms\n")

def main():
    setLogLevel('info')
    os.system('pkill -f "simple_switch|bmv2"')
    
    json_file = compile_p4_program("fast_reroute.p4")
    if not json_file:
        error("Failed to compile P4 program\n")
        return

    net = Mininet(
        topo=FastRerouteTopo(json_file),
        controller=None,
        link=TCLink,
        autoSetMacs=True
    )
    net.start()

    try:
        # Configure switches
        for sw in net.switches:
            configure_switch(sw)
            time.sleep(0.5)

        # Ensure hosts respond to pings
        for host in net.hosts:
            host.cmd('sysctl -w net.ipv4.icmp_echo_ignore_all=0 >/dev/null')

        # Preconfigure ARP to avoid delays
        h1 = net.get('h1')
        h2 = net.get('h2')
        h3 = net.get('h3')
        h1.cmd('arp -s 10.0.2.254 00:00:00:00:02:01')
        h2.cmd('arp -s 10.0.1.254 00:00:00:00:01:01')
        h3.cmd('arp -s 10.0.1.254 00:00:00:00:01:01')
        h3.cmd('arp -s 10.0.2.254 00:00:00:00:02:01')
        info("*** Preconfigured ARP entries on hosts\n")

        # Verify link delays
        verify_link_delays(net)

        # Initial state
        info("*** Initial Register State\n")
        read_registers(net, 's1', 9090, 's1_initial_regs.txt')
        read_registers(net, 's2', 9091, 's2_initial_regs.txt')
        read_registers(net, 's3', 9092, 's3_initial_regs.txt')

        # Start continuous ping with timestamps in background
        info("*** Starting continuous ping from h1 to h2\n")
        h1.cmd('ping -D -i 0.1 -c 400 10.0.2.1 > h1_ping.log 2>&1 &')  # 400 pings to cover 40s
        time.sleep(2)  # Allow ping to start

        # Start periodic logging of h1_to_h2_active_port on s1
        info("*** Starting periodic logging of h1_to_h2_active_port on s1\n")
        subprocess.Popen(['python3', '-c', '''
import subprocess
import time
for i in range(20):  # Log every 2 seconds for 40 seconds
    timestamp = i * 2
    output_file = f"s1_periodic_t{timestamp}.txt"
    with open(output_file, 'w') as f:
        subprocess.run("echo 'register_read h1_to_h2_active_port' | simple_switch_CLI --thrift-port 9090", shell=True, stdout=f)
    time.sleep(2)
'''], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Start background traffic to create congestion
        info("*** Starting background traffic from h3 to h2\n")
        h2.cmd('iperf -s -u -p 5001 > h2_iperf_server.log 2>&1 &')  # Background server
        time.sleep(1)  # Allow server to start
        iperf_cmd = h3.cmd('iperf -c 10.0.2.1 -u -p 5001 -b 25M -t 45 -i 1 > h3_iperf_client.log 2>&1 &')
        info(f"iperf client output: {iperf_cmd}")
        time.sleep(12)  # Allow iperf to generate initial data (12s to reach 14s total)

        # Read registers during congestion (pre-failure, at ~14s)
        info("*** Register State During Congestion (Pre-Failure)\n")
        read_registers(net, 's1', 9090, 's1_congestion_pre_failure.txt')
        read_registers(net, 's2', 9091, 's2_congestion_pre_failure.txt')
        read_registers(net, 's3', 9092, 's3_congestion_pre_failure.txt')

        # Simulate link failure between s1 and s2 (primary link) at 15s
        info("\n*** Simulating link failure between s1 and s2 (primary link)\n")
        time.sleep(1)  # Ensure we hit 15s
        s1 = net.get('s1')
        s2 = net.get('s2')
        s1_s2_links = net.linksBetween(s1, s2)
        info(f"Links between s1 and s2: {s1_s2_links}\n")
        primary_link_found = False
        for link in s1_s2_links:
            info(f"Checking link: {link.intf1.name} <-> {link.intf2.name}\n")
            if link.intf1.name == 's1-eth3' and link.intf2.name == 's2-eth3':
                info(f"Disabling primary link: {link}\n")
                try:
                    link.stop()
                    time.sleep(0.5)  # Ensure link is fully down
                except AttributeError as e:
                    error(f"Failed to stop link {link}: {e}\n")
                primary_link_found = True
                if (execute_switch_cmd(net, 's1', 9090, 'register_write link_status 3 0') and
                    execute_switch_cmd(net, 's2', 9091, 'register_write link_status 3 0')):
                    info("Link failure commands executed successfully\n")
                else:
                    error("Link failure commands failed\n")
                break
        if not primary_link_found:
            error("Primary link s1-eth3 <-> s2-eth3 not found! Listing all links:\n")
            for link in net.links:
                info(f"Link: {link.intf1.name} <-> {link.intf2.name}\n")
        time.sleep(25)  # Capture post-failure data until ~40s

        # Post-failure state
        info("*** Post-Failure Register State\n")
        read_registers(net, 's1', 9090, 's1_post_regs.txt')
        read_registers(net, 's2', 9091, 's2_post_regs.txt')
        read_registers(net, 's3', 9092, 's3_post_regs.txt')

        info("*** Testing backup path\n")
        net.pingAll()

        # Display logs
        info("*** Full h1 ping log:\n")
        with open('h1_ping.log', 'r') as f:
            info(f.read())
        info("*** h3 to h2 iperf client log:\n")
        with open('h3_iperf_client.log', 'r') as f:
            info(f.read())
        info("*** h2 iperf server log:\n")
        with open('h2_iperf_server.log', 'r') as f:
            info(f.read())

        # CLI(net)
    finally:
        h1.cmd('pkill -f "ping.*10.0.2.1"')
        h2.cmd('pkill -f "iperf.*5001"')
        h3.cmd('pkill -f "iperf.*10.0.2.1"')
        time.sleep(2)  # Ensure processes terminate
        try:
            net.stop()
        except AttributeError as e:
            error(f"Error during net.stop(): {e}\n")
        os.system('pkill -f "simple_switch|bmv2"')

if __name__ == '__main__':
    main()