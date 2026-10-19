#!/usr/bin/env python3
"""Render the two measured mechanism panels; never fill missing cells."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

PAPER=Path(__file__).resolve().parents[1]
FIG=PAPER/'figures'


def main():
    repair_path=FIG/'fig-mechanism-repair.json'
    edges_path=FIG/'fig-mechanism-edges.json'
    repair=json.loads(repair_path.read_text())
    edges=json.loads(edges_path.read_text())
    primary=repair['samples'][repair['primary']]
    if repair['layers']!=[8,12,16,24] or edges['layers']!=[8,16,24]:
        raise ValueError('Unexpected measured layer grid')
    if len(repair['manifests'])!=4 or len(edges['manifests'])!=4:
        raise ValueError('All four completed shards are required')
    if set(primary['ids']) != set(edges['rescued_ids']):
        raise ValueError('Mechanism panels must use identical primary item IDs')
    left=np.array(primary['accuracy'])[2:]
    right=np.array(edges['loss'])
    if left.shape!=(4,4) or right.shape!=(3,3):
        raise ValueError('Unexpected measured arm grid')
    plt.rcParams.update({'font.size':9,'pdf.fonttype':42,
                         'svg.fonttype':'none','text.color':'#263746'})
    from figure_fonts import configure_fonts
    configure_fonts()
    from matplotlib.colors import LinearSegmentedColormap
    fig,axes=plt.subplots(1,2,figsize=(7.1,3.35),layout='constrained',
                          gridspec_kw={'width_ratios':[1.15,1]})
    a,b=axes
    cmap=LinearSegmentedColormap.from_list('recovery',['#F6F9FA','#A8D3CD','#176E68'])
    heat=a.imshow(left*100,vmin=0,vmax=100,cmap=cmap,aspect='auto')
    heat.set_gid('measured-repair-heatmap')
    for row in range(4):
        for col in range(4):
            a.text(col,row,f'{left[row,col]*100:.1f}',ha='center',va='center',
                   fontsize=9,color='white' if left[row,col]>.65 else '#263746')
    a.set(xticks=range(4),xticklabels=[f'L{x}' for x in repair['layers']],
          yticks=range(4),yticklabels=['S: states','C: cache','SC: both','SC + recut'],
          xlabel='Replacement layer')
    a.set_xticks(np.arange(-.5,4,1),minor=True)
    a.set_yticks(np.arange(-.5,4,1),minor=True)
    a.grid(which='minor',color='white',linewidth=2)
    a.tick_params(which='both',length=0,pad=7,labelsize=8.5)
    a.spines[['top','right','bottom','left']].set_visible(False)
    a.set_title('(a) Replacement accuracy (%)',loc='left',fontsize=9.5,
                fontweight='bold',pad=43)
    colors=['#D27A29','#2866A0','#8494A4']
    labels=['Post-skill to skill','Skill to skill','Both paths']
    for i,(color,label,marker) in enumerate(zip(colors,labels,['o','s','D'])):
        y=np.arange(3)+(i-1)*.19
        points=b.scatter(right[i]*100,y,color=color,marker=marker,s=35,
                         edgecolors='white',linewidths=.6,zorder=3,label=label)
        points.set_gid(f'measured-edges-{i}')
    b.set(yticks=range(3),yticklabels=[f'L{x}' for x in edges['layers']],
          ylim=(2.5,-.5),xlim=(-3,103),xticks=[0,25,50,75,100],
          xlabel='Originally correct answers lost (%)')
    b.set_title('(b) Attention-path dependence',loc='left',fontsize=9.5,
                fontweight='bold',pad=43)
    b.legend(loc='lower left',bbox_to_anchor=(-.04,1.005),ncol=2,
             fontsize=7.5,frameon=False,columnspacing=.6,handletextpad=.3)
    b.spines[['top','right','left']].set_visible(False)
    b.spines['bottom'].set_color('#AAB4BE')
    b.tick_params(labelsize=8,length=0,pad=6)
    b.grid(axis='x',color='#E8EDF2',lw=.6)
    b.set_axisbelow(True)
    for y in [.5,1.5]:b.axhline(y,color='#E8EDF2',lw=.6)
    b.annotate('Post-skill access dominates',xy=(right[0,2]*100,1.81),
               xytext=(35,2.4),ha='center',fontsize=7.5,color='#94551D',
               arrowprops={'arrowstyle':'-','color':'#94551D','lw':.7})
    for ext in ('pdf','png','svg'):
        fig.savefig(FIG/f'fig-mechanism-results.{ext}',dpi=240,facecolor='white')
    svg=FIG/'fig-mechanism-results.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    metadata=dict(repair_source_sha256=hashlib.sha256(repair_path.read_bytes()).hexdigest(),
                  edges_source_sha256=hashlib.sha256(edges_path.read_bytes()).hexdigest(),
                  repair_n=primary['n'],edges_n=edges['rescued_n'],
                  repair_ids=primary['ids'],edges_ids=edges['rescued_ids'],
                  repair_layers=repair['layers'],edges_layers=edges['layers'],
                  repair_accuracy=left.tolist(),edge_loss=right.tolist())
    (FIG/'fig-mechanism-results-values.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':main()
