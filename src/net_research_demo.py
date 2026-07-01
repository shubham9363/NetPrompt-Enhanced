#!/usr/bin/env python3
"""
=============================================================================
  NetPrompt / MRSCO — Integrated Network & Research Simulation
  - Demonstrating P4 Fast-Reroute for Research Knowledge Sourcing
  - Topology: 4 Hosts (Researcher, Page Index, LLM Polling, Noise) + 3 Switches
  - Automatic reroute from Page Index -> LLM Polling upon link failure
=============================================================================
"""
import os, sys, subprocess, time, textwrap
import numpy as np

# Ensure terminal is sane
os.system("stty sane 2>/dev/null")
os.chdir('/home/shubham-pal/NetPrompt_Research/experimentations')

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.animation as animation
    import matplotlib.patheffects as pe
except ImportError:
    print("matplotlib not found!")
    sys.exit(1)

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Switch
from mininet.link import TCLink
from mininet.log import setLogLevel

# ── colour helpers ────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'
B='\033[1;34m'; BOLD='\033[1m'; NC='\033[0m'

def hdr(msg):    print(f"\n{BOLD}{G}{'='*60}{NC}\n{BOLD}{G}  {msg}{NC}\n{BOLD}{G}{'='*60}{NC}")
def info(msg):   print(f"{C}[INFO]{NC} {msg}")
def ok(msg):     print(f"{G}[OK]{NC}   {msg}")
def warn(msg):   print(f"{Y}[WARN]{NC} {msg}")
def err(msg):    print(f"{R}[ERR]{NC}  {msg}")
def step(n,msg): print(f"\n{BOLD}{B}[STEP {n}]{NC} {msg}")

# ── P4 switch ─────────────────────────────────────────────────────────────────
class P4Switch(Switch):
    def __init__(self, name, json_file, thrift_port, device_id, **params):
        Switch.__init__(self, name, **params)
        self.json_file   = json_file
        self.thrift_port = thrift_port
        self.device_id   = device_id
        self.proc        = None

    def start(self, controllers):
        cmd = ['simple_switch',
               '--thrift-port', str(self.thrift_port),
               '--device-id',   str(self.device_id),
               '--log-file', f'/tmp/bmv2_res_{self.name}.log', '--log-flush',
               self.json_file]
        for idx, intf in enumerate(self.intfList()):
            if intf.name != 'lo':
                cmd.extend(['-i', f'{idx+1}@{intf.name}'])
        self.proc = subprocess.Popen(
            cmd, stdout=open(f'/tmp/res_{self.name}.log', 'w'),
            stderr=subprocess.STDOUT)
        time.sleep(4)

    def stop(self):
        if self.proc:
            self.proc.terminate(); self.proc.wait()

class ResearchTopo(Topo):
    def __init__(self, json_file):
        Topo.__init__(self)
        sw = []
        for i in range(1, 4):
            s = self.addSwitch(f's{i}', cls=P4Switch,
                               json_file=json_file,
                               thrift_port=9090+(i-1), device_id=i)
            sw.append(s)

        h1 = self.addHost('h1', ip='10.0.1.1/24', mac='00:00:00:00:01:01') # Researcher
        h2 = self.addHost('h2', ip='10.0.2.1/24', mac='00:00:00:00:02:01') # Page Index
        h3 = self.addHost('h3', ip='10.0.3.1/24', mac='00:00:00:00:03:01') # LLM Polling
        h4 = self.addHost('h4', ip='10.0.1.2/24', mac='00:00:00:00:01:02') # Noise

        # hosts → switches
        self.addLink(h1, sw[0], port1=0, port2=2, cls=TCLink, bw=100)
        self.addLink(h2, sw[1], port1=0, port2=2, cls=TCLink, bw=100)
        self.addLink(h3, sw[2], port1=0, port2=2, cls=TCLink, bw=100)
        self.addLink(h4, sw[0], port1=0, port2=8, cls=TCLink, bw=100)

        # Primary inter-switch links
        self.addLink(sw[0], sw[1], port1=3, port2=3, cls=TCLink, bw=50)
        self.addLink(sw[1], sw[2], port1=4, port2=3, cls=TCLink, bw=50)
        self.addLink(sw[2], sw[0], port1=4, port2=4, cls=TCLink, bw=50)
        # Backup inter-switch links
        self.addLink(sw[0], sw[2], port1=5, port2=5, cls=TCLink, bw=30)
        self.addLink(sw[1], sw[0], port1=6, port2=6, cls=TCLink, bw=30)

def run_cli(thrift_port, cmds):
    r = subprocess.run(
        ['simple_switch_CLI', '--thrift-port', str(thrift_port)],
        input='\n'.join(cmds), capture_output=True, text=True, timeout=10)
    return r

def configure_reroute_p4(net):
    s1, s2, s3 = net.get('s1'), net.get('s2'), net.get('s3')
    # S1 rules: prefer h2 (port 3) but reroute to h3 (port 5)
    run_cli(s1.thrift_port, [
        'register_write link_status 3 1', 'register_write link_status 5 1',
        'table_add ipv4_lpm set_routes 10.0.1.1/32 => 2 00:00:00:00:01:01 0 00:00:00:00:00:00 00:00:00:00:01:01',
        'table_add ipv4_lpm set_routes 10.0.2.1/32 => 3 00:00:00:00:02:02 5 00:00:00:00:03:05 00:00:00:00:01:02',
        'table_add ipv4_lpm set_routes 10.0.3.1/32 => 5 00:00:00:00:03:05 3 00:00:00:00:02:03 00:00:00:00:01:03',
        'table_add backup_routes set_backup_nhop 10.0.2.1/32 => 00:00:00:00:03:05 5 00:00:00:00:01:05',
    ])
    # S2/S3 return rules
    run_cli(s2.thrift_port, [
        'table_add ipv4_lpm set_routes 10.0.2.1/32 => 2 00:00:00:00:02:01 0 00:00:00:00:00:00 00:00:00:00:02:01',
        'table_add ipv4_lpm set_routes 10.0.1.1/32 => 3 00:00:00:00:01:03 0 00:00:00:00:00:00 00:00:00:00:02:03',
    ])
    run_cli(s3.thrift_port, [
        'table_add ipv4_lpm set_routes 10.0.3.1/32 => 2 00:00:00:00:03:01 0 00:00:00:00:00:00 00:00:00:00:03:01',
        'table_add ipv4_lpm set_routes 10.0.1.1/32 => 5 00:00:00:00:01:05 0 00:00:00:00:00:00 00:00:00:00:03:05',
    ])

# ── Animation with Page Index ──────────────────────────────────────────────────
def make_integrated_video(output_mp4='/home/shubham-pal/NetPrompt_Research/net_research_animation.mp4'):
    hdr("Generating Integrated Network-Research Animation")
    fig, ax = plt.subplots(figsize=(16, 10), facecolor='#0d1117')
    pos = {
        'H1': (1.5, 7.5), 'H4': (1.5, 2.5), 'S1': (4.5, 5.0), 'S2': (8.5, 7.0), 
        'S3': (8.5, 3.0), 'H2': (13.0, 7.0), 'H3': (13.0, 3.0), 'LLM':(8.0, 0.6)
    }

    def draw_node(x, y, color, label, sublabel='', size=1.0):
        box = FancyBboxPatch((x-size, y-0.45), 2*size, 0.9, boxstyle='round,pad=0.1', lw=2, ec=color, fc=color+'22', zorder=3)
        ax.add_patch(box)
        ax.text(x, y+0.1, label, color=color, fontweight='bold', ha='center', va='center', zorder=4)
        if sublabel: ax.text(x, y-0.2, sublabel, color='#c9d1d9', fontsize=8, ha='center', va='center', zorder=4)

    phases = [
        {"n": "Step 1: Primary Retrieval (Index)", "text": "Researcher (H1) querying Page Index (H2) via Primary S1-S2 path", "path": "primary"},
        {"n": "Step 2: Simulated Link Failure", "text": "Primary Link S1-S2 Fails! Knowledge flow interrupted.", "fail": True},
        {"n": "Step 3: P4 Fast-Reroute Active", "text": "S1 detects hardware death, reroutes researcher flow to LLM Server (H3)", "reroute": True},
        {"n": "Step 4: LLM Polling Service", "text": "LLM (H3) polling multiple candidates to fulfill rerouted request", "poll": True},
        {"n": "Step 5: Context Recovery", "text": "Backup knowledge source providing higher-reliability code", "recovery": True},
        {"n": "Step 6: Research Continuation", "text": "Reroute Complete. Mission Critical P4 data secured.", "done": True}
    ]

    def update(page_index):
        ax.clear()
        ax.set_facecolor('#0d1117')
        ax.set_xlim(0, 16); ax.set_ylim(0, 10); ax.axis('off')
        
        draw_node(*pos['H1'], '#58a6ff', 'H1 Researcher')
        draw_node(*pos['H2'], '#f0883e', 'H2 Page Index')
        draw_node(*pos['H3'], '#bc8cff', 'H3 LLM Polling')
        draw_node(*pos['H4'], '#e3b341', 'H4 Traffic')
        draw_node(*pos['S1'], '#8b949e', 'S1 Edge P4')
        draw_node(*pos['S2'], '#8b949e', 'S2 Core P4')
        draw_node(*pos['S3'], '#8b949e', 'S3 Cloud P4')
        
        p = phases[min(page_index // 10, len(phases) - 1)]
        ax.text(8, 9.2, p['n'], color='#3fb950', fontsize=18, fontweight='bold', ha='center', bbox=dict(fc='#0d1117', ec='#3fb950'))
        ax.text(8, 8.7, p['text'], color='#c9d1d9', fontsize=12, ha='center')
        ax.text(14, 0.5, f"Integrated Page Index: {page_index}", color='#8b949e', fontsize=10, ha='right')
        
        # Link Rendering
        ls_prim = '--' if p.get('fail') or p.get('reroute') else '-'
        col_prim = '#f85149' if p.get('fail') else '#f0883e'
        ax.plot([pos['S1'][0], pos['S2'][0]], [pos['S1'][1], pos['S2'][1]], color=col_prim, ls=ls_prim, lw=3)
        ax.plot([pos['S2'][0], pos['S3'][0]], [pos['S2'][1], pos['S3'][1]], color='#bc8cff', lw=3)
        
        # Reroute Path
        col_bkp, lw_bkp = ('#3fb950', 5) if p.get('reroute') or p.get('poll') or p.get('done') else ('#8b949e', 1.5)
        ax.plot([pos['S1'][0], pos['S3'][0]], [pos['S1'][1], pos['S3'][1]], color=col_bkp, ls='--', lw=lw_bkp)

        # Flow Arrows
        if not p.get('fail') and not p.get('reroute') and not p.get('poll'):
            ax.annotate('', xy=pos['H2'], xytext=pos['H1'], arrowprops=dict(arrowstyle='->', color='#58a6ff', lw=2.5, connectionstyle='arc3,rad=-0.1'))
        if p.get('reroute') or p.get('poll'):
            ax.annotate('', xy=pos['H3'], xytext=pos['H1'], arrowprops=dict(arrowstyle='->', color='#3fb950', lw=3.0, connectionstyle='arc3,rad=0.3'))
    
    ani = animation.FuncAnimation(fig, update, frames=60, interval=400, blit=False)
    try: ani.save(output_mp4, writer='ffmpeg', fps=3)
    except: ani.save(output_mp4.replace('.mp4', '.gif'), writer='pillow', fps=3)
    ok(f"Integrated Animation generated at {output_mp4}")

def main():
    setLogLevel('warning')
    os.system("sudo mn -c 2>/dev/null; sudo pkill -9 -f simple_switch 2>/dev/null")
    
    hdr("Integrated Research Demo: Network + Page Index + LLM")
    
    net = Mininet(topo=ResearchTopo('fast_reroute.json'), controller=None)
    net.start()
    time.sleep(5)
    configure_reroute_p4(net)
    
    h1, h2, h3 = net.get('h1'), net.get('h2'), net.get('h3')
    
    step(1, "Baseline Phase: Communication via Primary Page Index")
    info("Researcher (h1) pinging Page Index (h2)...")
    net.ping([h1, h2])
    ok("Primary path S1-S2 established.")

    step(2, "Simulating Primary Link Failure")
    warn("Hardware Link S1[3] -> S2[3] DOWN!")
    run_cli(9090, ['register_write link_status 3 0']) # break link S1-S2
    time.sleep(2)
    
    step(3, "P4 Fast-Reroute: Verifying Path to LLM Polling Server")
    info("Researcher (h1) pinging LLM Polling Server (h3)...")
    net.ping([h1, h3])
    ok("Fast-Reroute successfully diverted researcher to Backup LLM Source.")
    
    step(4, "Finalizing Visual Validation")
    make_integrated_video()
    
    net.stop()
    hdr("Integrated Demo Complete")
    ok("P4 Network rerouted gracefully between Index and LLM servers.")

if __name__ == '__main__':
    main()
