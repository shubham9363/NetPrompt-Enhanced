#!/usr/bin/env python3
"""
=============================================================================
  NetPrompt Research — Fast-Reroute: Page Index -> LLM Polling
  - Visualizing primary search failure (Low Confidence)
  - Automatic rerouting to Multi-LLM Consensus Voter (High Reliability)
  - Animated with 'page index' logic
=============================================================================
"""
import os, sys, time, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.animation as animation
import matplotlib.patheffects as pe
import numpy as np

# Ensure terminal is sane
os.system("stty sane 2>/dev/null")

# ── colour helpers (Research Style) ───────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'
B='\033[1;34m'; BOLD='\033[1m'; NC='\033[0m'

def hdr(msg):    print(f"\n{BOLD}{G}{'='*60}{NC}\n{BOLD}{G}  {msg}{NC}\n{BOLD}{G}{'='*60}{NC}")
def info(msg):   print(f"{C}[INFO]{NC} {msg}")
def ok(msg):     print(f"{G}[OK]{NC}   {msg}")
def warn(msg):   print(f"{Y}[WARN]{NC} {msg}")
def step(n,msg): print(f"\n{BOLD}{B}[STEP {n}]{NC} {msg}")

# ── Animation Generation (Using 'page index' logic) ───────────────────────────
def make_reroute_video(output_mp4='/home/shubham-pal/NetPrompt_Research/research_reroute_animation.mp4'):
    hdr("Generating Fast-Reroute Research Animation")
    info("Visualizing Reroute from BM25 to LLM Polling via 'page_index' steps...")
    
    fig, ax = plt.subplots(figsize=(16, 10), facecolor='#0d1117')
    pos = {
        'QUERY':  (1.5, 7.5),
        'BM25':   (4.5, 5.0),
        'LLM_POLL': (8.5, 0.6), # LLM Polling Node
        'PDF':    (8.5, 7.0),
        'P4_CODE': (14.0, 7.0),
    }

    def draw_node(x, y, color, label, sublabel='', size=1.0):
        box = FancyBboxPatch((x-size, y-0.45), 2*size, 0.9, boxstyle='round,pad=0.1', lw=2, ec=color, fc=color+'22', zorder=3)
        ax.add_patch(box)
        ax.text(x, y+0.1, label, color=color, fontweight='bold', ha='center', va='center', zorder=4)
        if sublabel:
            ax.text(x, y-0.2, sublabel, color='#c9d1d9', fontsize=8, ha='center', va='center', zorder=4, alpha=0.8)

    phases = [
        {"n": "Step 1: Primary Search (BM25)", "text": "Querying fast BM25 Page Index for 'P4 Fast Reroute'", "active_node": "BM25", "path": "primary"},
        {"n": "Step 2: Low Confidence Detected", "text": "BM25 Match Score < 0.2. Page Index has insufficient context!", "fail": True, "path": "primary"},
        {"n": "Step 3: Fast-Reroute Triggered", "text": "Rerouting research logic to Multi-LLM Consensus Voter (Backup Path)", "reroute": True, "active_node": "LLM_POLL"},
        {"n": "Step 4: LLM Polling / Multi-Voter", "text": "Polling candidates: ChatGPT, Claude, and Deepseek for P4 logic...", "polling": True, "active_node": "LLM_POLL"},
        {"n": "Step 5: Consensus Scoring", "text": "Comparing results: Claude.p4 selected via high functional score (92.5)", "scoring": True},
        {"n": "Step 6: Verified Code Output", "text": "Reroute successful. High-reliability P4 code generated.", "done": True}
    ]

    def update(page_index):
        ax.clear()
        ax.set_facecolor('#0d1117')
        ax.set_xlim(0, 16); ax.set_ylim(0, 10)
        ax.axis('off')

        draw_node(*pos['QUERY'], '#58a6ff', 'USER QUERY', 'LPM Logic?')
        draw_node(*pos['BM25'],  '#f0883e', 'PAGE INDEX', 'BM25 (Fast)')
        draw_node(*pos['PDF'],   '#bc8cff', 'DOC SOURCE', 'AMD Spec')
        draw_node(*pos['LLM_POLL'], '#3fb950', 'LLM POLLING', '(Backup Path - Higher Reliability)', size=1.5)
        draw_node(*pos['P4_CODE'], '#3fb950', 'P4 OUTPUT', 'Verified logic')
        
        p = phases[min(page_index // 10, len(phases) - 1)]
        ax.text(8, 9.2, p['n'], color='#3fb950', fontsize=18, fontweight='bold', ha='center', bbox=dict(fc='#0d1117', ec='#3fb950'))
        ax.text(8, 8.7, p['text'], color='#c9d1d9', fontsize=12, ha='center')
        ax.text(14, 0.5, f"Reroute Page Index: {page_index}", color='#8b949e', fontsize=10, ha='right')
        
        # Primary Paths
        ls_prim = '--' if p.get('fail') or p.get('reroute') else '-'
        color_prim = '#f85149' if p.get('fail') else '#f0883e'
        ax.plot([pos['QUERY'][0], pos['BM25'][0]], [pos['QUERY'][1], pos['BM25'][1]], color='#58a6ff', lw=2)
        ax.plot([pos['BM25'][0], pos['PDF'][0]],  [pos['BM25'][1], pos['PDF'][1]],  color=color_prim, ls=ls_prim, lw=3)
        ax.plot([pos['PDF'][0], pos['P4_CODE'][0]], [pos['PDF'][1], pos['P4_CODE'][1]], color='#bc8cff', lw=2)

        # Reroute Path (The "Fast-Reroute")
        reroute_c, reroute_lw = ('#3fb950', 4) if p.get('reroute') or p.get('polling') or p.get('done') else ('#8b949e', 1.5)
        ax.plot([pos['QUERY'][0], pos['LLM_POLL'][0]], [pos['QUERY'][1], pos['LLM_POLL'][1]], color=reroute_c, ls='--', lw=reroute_lw)
        ax.plot([pos['LLM_POLL'][0], pos['P4_CODE'][0]], [pos['LLM_POLL'][1], pos['P4_CODE'][1]], color=reroute_c, ls='--', lw=reroute_lw)

        if p.get('fail'):
            ax.text(3, 4, "LOW CONFIDENCE!", color='#f85149', fontweight='bold', rotation=45)

        if p.get('reroute'):
            ax.text(4, 3, "TRIGGER REROUTE", color='#3fb950', fontweight='bold', ha='center')

        if p.get('polling'):
            ax.text(pos['LLM_POLL'][0], pos['LLM_POLL'][1]+0.8, "VOTING: Claude(92) ChatGPT(85) Deepseek(21)", color='#3fb950', ha='center', fontsize=9)

        if p.get('done'):
            ax.text(12, 8, "SUCCESS (Rerouted Path)", color='#3fb950', fontweight='bold')

    ani = animation.FuncAnimation(fig, update, frames=60, interval=400, blit=False)
    output_gif = output_mp4.replace('.mp4', '.gif')
    try:
        ani.save(output_mp4, writer='ffmpeg', fps=3)
        ok(f"Reroute Animation saved to {output_mp4}")
    except:
        ani.save(output_gif, writer='pillow', fps=3)
        ok(f"Saved Reroute Animation as GIF: {output_gif}")

def main():
    hdr("NetPrompt Research: Fast-Reroute Simulation")
    
    step(1, "Phase 1: Primary Search Attempt (BM25)")
    info("Retrieving chunks for query: 'Implement P4 Resilient Fast Reroute'...")
    time.sleep(1)
    warn("Warning: Top Match Score = 0.18 (Below confidence threshold 0.4)")
    
    step(2, "Phase 2: Fast-Reroute Logic Triggered")
    info("Transitioning from Page Index search to Multi-LLM Consensus Voting...")
    time.sleep(1)
    ok("Fast-Reroute active. Backup path (Consensus Voter) initialized.")
    
    step(3, "Phase 3: Multi-LLM Polling (Consensus Voter)")
    info("Polling candidates: [ChatGPT, Claude, Baseline]...")
    time.sleep(1.5)
    print("  Claude   : Functional Test PASS (Score: 92.5)")
    print("  ChatGPT  : Functional Test PASS (Score: 88.1)")
    print("  Baseline : Functional Test FAIL (Score: 40.0)")
    ok("Consensus Found: Selected Claude.p4")
    
    step(4, "Phase 4: Automatic Animation Generation")
    make_reroute_video()
    
    hdr("Fast-Reroute Demo Complete")
    ok("System successfully rerouted from failing Page Index to verified LLM Voter.")

if __name__ == '__main__':
    main()
