#!/usr/bin/env python3
"""Vector teaser: contextual ability, two interventions, measured depth gap."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import numpy as np

PAPER=Path(__file__).resolve().parents[1]
INK='#20384B'; MUTED='#657889'; BLUE='#2864A5'; TEAL='#278577'; AMBER='#BD6D26'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'text.color':INK,
                     'pdf.fonttype':42,'svg.fonttype':'none'})


def main():
    source=PAPER/'values/depth-crossmodel-values.json'
    cell=next(r for r in json.loads(source.read_text())
              if r['model']=='Qwen3-8B' and r['task']=='MedCalc')['common']
    assert cell['n']==134 and cell['transfer_boundary']==13 and cell['reading_boundary']==25
    fig=plt.figure(figsize=(7.25,2.92),facecolor='white')
    ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,150);ax.set_ylim(0,60);ax.axis('off')

    def text(x,y,s,size=7.7,weight='normal',color=INK,ha='left',**kw):
        ax.text(x,y,s,fontsize=size,fontweight=weight,color=color,ha=ha,va='center',**kw)
    def box(x,y,w,h,fill='white',edge='none',radius=1.5,lw=.65):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0,rounding_size={radius}',
                                   facecolor=fill,edgecolor=edge,linewidth=lw))
    def arrow(x1,y1,x2,y2,color=MUTED,lw=1.2,style='-|>',rad=0):
        ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle=style,
            mutation_scale=8,linewidth=lw,color=color,connectionstyle=f'arc3,rad={rad}'))
    def doc(x,y,w,h,color,heading):
        box(x,y,w,h,'white',color,radius=.8)
        ax.add_patch(Rectangle((x,y+h-2.2),w,2.2,color=color,lw=0))
        for j,frac in enumerate([.76,.85,.58]):
            ax.plot([x+1.5,x+frac*w],[y+h-4.1-j*1.6]*2,color=color,lw=.7,alpha=.65)
        text(x+w/2,y-2.2,heading,6.5,ha='center',color=color)
    def tokens(x,y,wrong=False):
        for k in range(12):
            fill=('#BAC4CD' if wrong else TEAL) if 2<=k<8 else '#DCE3E9'
            box(x+k*2.5,y,2,2.5,fill,radius=.35)
    text(1,57,'WHEN DOES A CONTEXTUAL ABILITY BECOME A REUSABLE SKILL?',9.2,'bold')
    text(1,53.3,'Successful use is the starting point. Transfer and source access ask what sustains it.',7.4,color=MUTED)
    for x,w,c in [(0,37.5,'#F3F7F9'),(40,60,'#F3F7FB'),(102.5,47.5,'#FBF6EE')]:
        box(x,4,w,45.5,c)

    text(3,46,'01  CONTEXT GIVES AN ABILITY',6.7,'bold',color=MUTED)
    doc(5,31,10,10,TEAL,'New rule')
    doc(23,31,10,10,'#8394A3','Question')
    arrow(10,27,15,23.5);arrow(28,27,23,23.5)
    for j in range(3):
        box(9+j*.7,18+j*2,19,3.2,['#C8D6E0','#DFE8EE','#EDF2F6'][j],edge='#A6BBCB',radius=.6)
    text(19.2,21,'Language model',6.6,ha='center')
    arrow(19,16.6,19,13.5,color=TEAL)
    box(6.5,7.6,25,5.4,'#E1EEE8',radius=1)
    text(19,10.3,'Correct application',7,'bold',TEAL,ha='center')

    text(43,46,'02  TEST TWO PROPERTIES',6.7,'bold',color=MUTED)
    text(43,41,'Can the states travel?',8.4,'bold',BLUE)
    text(43,36.6,'Correct-skill run',6.7,color=TEAL)
    tokens(43,32.2)
    text(43,23.3,'Wrong-skill receiver',6.7,color=MUTED)
    tokens(43,26.4,wrong=True)
    arrow(56,32.1,56,29.1,BLUE,lw=1.7)
    text(77,31,'Replace skill states\nat layer L',6.9,color=BLUE,linespacing=1.5)
    ax.plot([43,96],[20,20],color='#D4DFE8',lw=.6)
    text(43,16.5,'Does the source still matter?',8.4,'bold',TEAL)
    box(43,8.2,14,4.8,'white',TEAL,radius=.7)
    text(50,10.6,'Skill tokens',6.5,color=TEAL,ha='center')
    box(77,8.2,19,4.8,'white','#97ABB8',radius=.7)
    text(86.5,10.6,'Later computation',6.5,ha='center')
    arrow(58,10.6,76,10.6,TEAL)
    ax.plot([66,69],[8.8,12.4],color=AMBER,lw=1.7)
    ax.plot([66,69],[12.4,8.8],color=AMBER,lw=1.7)
    text(67.5,5.7,'Block skill attention from L onward',5.9,color=MUTED,ha='center')

    text(105.5,46,'03  THE TWO CAN SEPARATE',6.7,'bold',color=AMBER)
    text(105.5,41.7,'Qwen3-8B / MedCalc',7.5,'bold')
    plot=fig.add_axes([106/150,17.5/60,40/150,17/60],facecolor='none')
    x=np.arange(36); transfer=np.array(cell['transfer']); dependence=1-np.array(cell['retention'])
    plot.axvspan(13,25,color='#F4D6AF',alpha=.8,lw=0)
    plot.axhline(.5,color='#C6B59E',ls=(0,(2,3)),lw=.55)
    plot.plot(x,transfer,color=BLUE,lw=1.45)
    plot.plot(x,dependence,color=TEAL,lw=1.45)
    plot.set_xlim(0,35);plot.set_ylim(-.035,1.07)
    plot.set_xticks([0,13,25,35]);plot.set_yticks([0,1])
    plot.tick_params(labelsize=6,length=2,pad=2,colors=MUTED)
    plot.spines[['top','right']].set_visible(False)
    for key in ('left','bottom'):plot.spines[key].set_color('#B6B0A7');plot.spines[key].set_linewidth(.5)
    plot.set_xlabel('Model layer',fontsize=6.6,labelpad=2,color=MUTED)
    plot.plot([],[],color=BLUE,label='Transfer recovery',lw=1.5)
    plot.plot([],[],color=TEAL,label='Source dependence (1 − retention)',lw=1.5)
    plot.legend(loc='upper left',bbox_to_anchor=(-.06,1.25),fontsize=5.4,
                frameon=False,handlelength=1.3,labelspacing=.3,borderaxespad=0)
    text(126,9.3,'Weak transfer.\nSource still needed.',7.3,'bold',AMBER,ha='center',linespacing=1.35)
    text(75,1.2,'Using a contextual skill and reusing its internal states are different capabilities.',8,'bold',ha='center')

    for ext in ('pdf','svg','png'):
        fig.savefig(PAPER/f'figures/fig-teaser.{ext}',dpi=240,facecolor='white')
    evidence=dict(source=str(source.relative_to(PAPER)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  model='Qwen3-8B',task='MedCalc',sample='common eligible items',n=cell['n'],
                  transfer=cell['transfer'],source_dependence=dependence.tolist(),
                  transfer_boundary=13,reading_boundary=25)
    (PAPER/'figures/fig-teaser-values.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
