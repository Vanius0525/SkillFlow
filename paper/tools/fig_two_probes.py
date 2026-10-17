#!/usr/bin/env python3
"""Conceptual two-probe design, following the supplied v2 narrative."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from _paths import FIGURES

plt.rcParams.update({'font.family':'DejaVu Sans','pdf.fonttype':42,
                     'svg.fonttype':'none','text.color':'#263746'})
fig, ax = plt.subplots(figsize=(7.1, 1.9))
ax.set(xlim=(0,12), ylim=(0,3.25))
ax.axis('off')
for y, color, title, boxes in [
    (1.95, '#2866A0', '(a) Transfer: can skill states help another execution?', [
        ('Correct-skill donor', 'Skill-span states at layer L'),
        ('Copy states into receiver', 'Keep its prior caches and history'),
        ('Wrong-skill receiver', r'Recovered skill benefit: $\rho(L)$')]),
    (.35, '#D27A29', '(b) Dependence: does the original execution still need the skill?', [
        ('Correct-skill execution', 'Skill and question in context'),
        ('Block attention to skill', 'From layer L onward'),
        ('Original execution continues', r'Retained performance: $q(L)$')])]:
    ax.text(.08,y+1.02,title,fontsize=8.1,fontweight='bold',color=color)
    for x,(title,detail) in zip([.1,4.2,8.3],boxes):
        ax.add_patch(FancyBboxPatch((x,y),3.55,.75,
            boxstyle='round,pad=.05,rounding_size=.08',
            facecolor='#F5F8FA',edgecolor=color,linewidth=.7))
        ax.text(x+1.775,y+.49,title,ha='center',fontsize=7.3,fontweight='medium')
        ax.text(x+1.775,y+.20,detail,ha='center',fontsize=6.5)
    for x in [3.72,7.82]:
        ax.add_patch(FancyArrowPatch((x,y+.375),(x+.39,y+.375),
            arrowstyle='-|>',mutation_scale=9,color=color,linewidth=.8))
fig.subplots_adjust(left=.01,right=.99,top=.98,bottom=.01)
for ext in ['pdf','png','svg']:
    fig.savefig(FIGURES/f'fig-two-probes.{ext}',dpi=220,facecolor='white')
plt.close(fig)
