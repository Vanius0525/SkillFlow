#!/usr/bin/env python3
"""Measured overview: early residual transfer, depth separation, source repair."""
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from _paths import PAPER, VALUES, FIGURES, AUDIT
from style_main_figures import BLUE, TEAL, ORANGE, GRAY, frame, save


def main():
    depth_path=VALUES/'depth-crossmodel-values.json'
    repair_path=FIGURES/'fig-mechanism-repair.json'
    channels_path=VALUES/'fig-channels-values.json'
    cell=next(r for r in json.loads(depth_path.read_text())
              if r['model']=='Qwen3-8B' and r['task']=='MedCalc')['common']
    repair=json.loads(repair_path.read_text())
    primary=repair['samples'][repair['primary']]
    channels=json.loads(channels_path.read_text())
    recovery=channels['bottom']['real']['acc'][0]/channels['gold'][0]
    values=np.array(primary['accuracy'])[2:,2]*100
    fig=plt.figure(figsize=(7.1,2.8))
    a=fig.add_axes([.015,.19,.235,.60])
    b=fig.add_axes([.34,.23,.235,.56])
    c=fig.add_axes([.76,.23,.23,.56])
    for x,title in [(.015,'(a) Early transfer'),(.34,'(b) Depth separation'),
                    (.67,'(c) Partial late recovery')]:
        fig.text(x,.94,title,fontsize=9,fontweight='bold')
    a.set(xlim=(0,1),ylim=(0,1));a.axis('off')
    def box(y,label,color):
        a.add_patch(FancyBboxPatch((.08,y),.84,.18,boxstyle='round,pad=.015',
                    facecolor='#F5F8FA',edgecolor=color,linewidth=.7))
        a.text(.5,y+.09,label,ha='center',va='center',fontsize=8)
    box(.65,'Correct-skill states',BLUE)
    box(.29,'Wrong-skill receiver',GRAY)
    a.add_patch(FancyArrowPatch((.5,.63),(.5,.49),arrowstyle='-|>',
                               mutation_scale=9,color=BLUE,lw=1))
    a.text(.69,.55,'copy',ha='center',fontsize=7.5,color=BLUE,
           bbox={'fc':'white','ec':'none','pad':1.5})
    a.text(.5,.10,f'{recovery:.0%} of skill gain\nrecovered',ha='center',
           fontsize=8,color=BLUE,fontweight='bold')
    fig.text(.1325,.015,'Layer 8 · n = 135',ha='center',fontsize=7.5,color='#657889')

    x=np.arange(len(cell['transfer']))
    dependence=1-np.array(cell['retention'])
    frame(b)
    b.axvspan(13,25,color='#F5BE7E',alpha=.26,lw=0)
    b.plot(x,cell['transfer'],color=BLUE,lw=1.5,label='Transfer',gid='teaser-transfer')
    b.plot(x,dependence,color=ORANGE,lw=1.5,label=r'Dependence $d$',gid='teaser-dependence')
    b.axhline(.5,color='#A4AFBA',lw=.6,ls=(0,(2,3)))
    b.set(xlim=(0,35),ylim=(-.04,1.12),xticks=[0,13,25,35],
          yticks=[0,.5,1],xlabel='Intervention layer',ylabel='Recovery / dependence')
    b.set_yticklabels(['0','.5','1.0'])
    b.text(19,1.035,'Still needed',ha='center',fontsize=7,color='#94551D')
    b.legend(loc='lower left',bbox_to_anchor=(-.03,1.04),fontsize=7.2,
             ncol=2,borderaxespad=0,handlelength=1.1,labelspacing=.2,columnspacing=.7)
    fig.text(.457,.015,'Common items · n = 134',ha='center',fontsize=7.5,color='#657889')

    labels=['States only','Cache only','Both','Both + read cut']
    yy=np.arange(4)[::-1]
    bars=c.barh(yy,values,height=.50,color=[BLUE,GRAY,TEAL,ORANGE],zorder=3)
    for i,(bar,v) in enumerate(zip(bars,values)):
        bar.set_gid(f'teaser-repair-{i}')
        c.text(v+1.5,yy[i],f'{v:.1f}%',va='center',fontsize=7.5)
    c.set(yticks=yy,yticklabels=labels,xlim=(0,57),ylim=(-.55,3.6),
          xlabel='Answer accuracy (%)',xticks=[0,20,40])
    frame(c);c.grid(False);c.grid(axis='x',color='#E8EDF2',lw=.55)
    c.spines['left'].set_visible(False)
    c.tick_params(axis='y',length=0,pad=3,labelsize=7.5)
    fig.text(.875,.015,'Layer 16 · n = 114',ha='center',fontsize=7.5,color='#657889')
    save(fig,'fig-teaser')
    report={'model':'Qwen3-8B','task':'MedCalc','early_n':channels['n'],
            'early_recovery':recovery,'depth_n':cell['n'],
            'transfer':cell['transfer'],'source_dependence':dependence.tolist(),
            'repair_n':primary['n'],'repair_accuracy_percent':values.tolist(),
            'input_sha256':{str(p.relative_to(PAPER)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in [depth_path,repair_path,channels_path]}}
    (AUDIT/'TEASER-CACHE-READING-20261017.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
