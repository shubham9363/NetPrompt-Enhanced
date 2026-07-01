#!/usr/bin/env python3
"""
=============================================================================
  NetPrompt Research Demo — Page Index Animation
  Generates an animated GIF/MP4 of the P4 Research Pipeline
  showing: Query -> BM25 Page Index -> PDF Matching -> LLM Generation
=============================================================================
"""
import sys, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.animation as animation
import numpy as np

# Colours (GitHub Dark Theme Palette)
BG   = '#0d1117'
BLUE = '#58a6ff'
GRN  = '#3fb950'
ORG  = '#f0883e'
PRP  = '#bc8cff'
RED  = '#f85149'
YLW  = '#e3b341'
WHT  = '#c9d1d9'
GREY = '#8b949e'

pos = {
    'USER':  (2.0, 7.5),   # User query
    'INDEX': (8.0, 7.5),   # BM25 Page Index
    'PDF':   (8.0, 3.0),   # p4_amd_document.pdf
    'LLM':   (14.0, 7.5),  # NetPrompt Brain (Ollama)
}

fig, ax = plt.subplots(figsize=(16, 10), facecolor=BG)

def draw_node(name, xy, color, label, sublabel='', size=1.0):
    x, y = xy
    box = FancyBboxPatch((x-size, y-0.45), 2*size, 0.9,
                         boxstyle='round,pad=0.1', linewidth=2,
                         edgecolor=color, facecolor=color+'22', zorder=3)
    ax.add_patch(box)
    ax.text(x, y+0.1, label, color=color, fontsize=11, fontweight='bold',
            ha='center', va='center', zorder=4)
    if sublabel:
        ax.text(x, y-0.2, sublabel, color=WHT, fontsize=8,
                ha='center', va='center', zorder=4, alpha=0.85)

def draw_link(p1, p2, color, lw, ls='-', label='', label_offset=(0,0.2)):
    x1, y1 = p1; x2, y2 = p2
    line, = ax.plot([x1, x2], [y1, y2], color=color, lw=lw, ls=ls,
                    zorder=1, alpha=0.85, solid_capstyle='round')
    txt = None
    if label:
        mx, my = (x1+x2)/2+label_offset[0], (y1+y2)/2+label_offset[1]
        txt = ax.text(mx, my, label, color=color, fontsize=9,
                ha='center', va='center', zorder=2,
                bbox=dict(boxstyle='round,pad=0.15', fc=BG, ec=color, lw=0.8, alpha=0.9))
    return line, txt

def draw_arrow(p1, p2, color, lw, rad, label='', offset=(0,0)):
    arrow = ax.annotate('', xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                connectionstyle=f'arc3,rad={rad}', alpha=0.9),
                zorder=5)
    txt = None
    if label:
        x, y = (p1[0]+p2[0])/2+offset[0], (p1[1]+p2[1])/2+offset[1]
        txt = ax.text(x, y, label, color=color, fontsize=10, fontweight='bold', ha='center', zorder=6,
                     bbox=dict(boxstyle='round,pad=0.2', fc=BG, ec=color, alpha=0.9))
    return arrow.arrow_patch, txt

phases = [
    {"name": "Phase 1: User Query", "text": "Researcher asks: 'How to define a forwarding table with LPM in P4?'", "q_in": True},
    {"name": "Phase 2: Index Search", "text": "BM25 Page Index scanning documentation keywords...", "index_active": True},
    {"name": "Phase 3: PDF Matching", "text": "Scanning 'p4_amd_document.pdf' (1572 KB) for relevant chunks.", "pdf_match": True},
    {"name": "Phase 4: Rank Top-3", "text": "BM25 identified 3 high-score pages (Chunks 12, 45, 89)", "ranked": True},
    {"name": "Phase 5: LLM Context", "text": "Top-3 chunks sent to Ollama (TinyLlama) as RAG context.", "context_flow": True},
    {"name": "Phase 6: P4 Generated", "text": "LLM uses CoT to generate valid P4 code. Saved to .p4 file.", "gen_p4": True}
]

state = {"anim_objects": []}

def init_base():
    ax.clear()
    ax.set_facecolor(BG)
    ax.set_xlim(0, 16); ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Static nodes
    draw_node('USER',  pos['USER'],  BLUE, 'USER',      'Researcher Query')
    draw_node('INDEX', pos['INDEX'], YLW,  'BM25 INDEX', 'Page Index Meta')
    draw_node('PDF',   pos['PDF'],   PRP,  'DOCUMENT',   'p4_amd_document.pdf')
    draw_node('LLM',   pos['LLM'],   GRN,  'LLM BRAIN',  'Ollama / TinyLlama')
    
    ax.text(8, 9.6, 'NetPrompt Research — Page Index & LLM P4 Generation', color=WHT, fontsize=16, fontweight='bold', ha='center', va='top')
    
    legend_items = [
        mpatches.Patch(color=BLUE, label='User Input / Query'),
        mpatches.Patch(color=YLW,  label='BM25 Retriever (Fast Search)'),
        mpatches.Patch(color=PRP,  label='PDF Knowledge Source'),
        mpatches.Patch(color=GRN,  label='AI Generation (Chain-of-Thought)'),
    ]
    ax.legend(handles=legend_items, loc='lower center', facecolor='#161b22', edgecolor='#30363d', labelcolor=WHT, fontsize=9, framealpha=0.9, ncol=4)

def update(page_index):
    # Using page_index as the animation step variable
    for obj in state["anim_objects"]:
        if obj is not None:
            obj.set_visible(False)
    state["anim_objects"].clear()
    
    # 6 phases, 10 "pages" each (simulated steps)
    p_idx = min(page_index // 10, len(phases) - 1)
    phase = phases[p_idx]
    
    # Text Titles
    title1 = ax.text(8, 9.1, phase['name'], color=GRN, fontsize=13, fontweight='bold', ha='center', va='top', zorder=10, bbox=dict(boxstyle='round,pad=0.3', fc=BG, ec=GRN, alpha=0.9))
    title2 = ax.text(8, 8.6, phase['text'], color=WHT, fontsize=11, ha='center', va='top', zorder=10)
    p_val_text = ax.text(14, 0.5, f"Current Step Index: {page_index}", color=GREY, fontsize=9, ha='right')
    state["anim_objects"].extend([title1, title2, p_val_text])
    
    # Draw Links
    l1, t1 = draw_link(pos['USER'], pos['INDEX'], BLUE, 1.5, ls='--', label='JSON Query')
    l2, t2 = draw_link(pos['INDEX'], pos['PDF'], YLW, 1.5, ls='--', label='Keyword Search')
    l3, t3 = draw_link(pos['INDEX'], pos['LLM'], GRN, 1.5, ls='--', label='Context Pack')
    state["anim_objects"].extend([l1, t1, l2, t2, l3, t3])
    
    # Animations based on phase
    if phase.get('q_in'):
        a, t = draw_arrow((3.0, 7.5), (6.8, 7.5), BLUE, 3, 0, "Forwarding Table Rule?", offset=(0, 0.5))
        state["anim_objects"].extend([a, t])

    if phase.get('index_active'):
        a, t = draw_arrow(pos['INDEX'], (pos['INDEX'][0], pos['INDEX'][1]+1), YLW, 2, 0)
        state["anim_objects"].extend([a])
        
    if phase.get('pdf_match'):
        # Show scanning effect towards PDF
        y_scan = 7.5 - (page_index % 10) * 0.4
        a, t = draw_arrow(pos['INDEX'], (8.0, y_scan), PRP, 4, 0)
        state["anim_objects"].extend([a])

    if phase.get('ranked'):
        # High impact matching
        a, t = draw_arrow(pos['PDF'], pos['INDEX'], PRP, 3, 0, "Matched Chunks Found!", offset=(0, -1))
        state["anim_objects"].extend([a, t])
        
    if phase.get('context_flow'):
        a, t = draw_arrow((9.1, 7.5), (12.8, 7.5), GRN, 3, 0, "Top-3 context", offset=(0, 0.5))
        state["anim_objects"].extend([a, t])

    if phase.get('gen_p4'):
        a, t = draw_arrow((14.0, 7.0), (14.0, 5.0), GRN, 4, 0, "forwarding_table.p4", offset=(1.5, 0))
        state["anim_objects"].extend([a, t])

init_base()
# Using range of 60 steps as requested by "just use page index instead of" (likely meaning frame)
anim = animation.FuncAnimation(fig, update, frames=60, interval=600, blit=False)

out_file = '/home/shubham-pal/NetPrompt_Research/research_animation.gif'
try:
    anim.save(out_file, writer='pillow', fps=2)
    print(f"Research Animation successfully saved to {out_file}")
except Exception as e:
    print(f"Could not save GIF: {e}")

# Also try to save as MP4 if ffmpeg is available
try:
    anim.save(out_file.replace('.gif', '.mp4'), writer='ffmpeg', fps=2)
    print(f"Research Animation successfully saved to {out_file.replace('.gif', '.mp4')}")
except:
    pass
