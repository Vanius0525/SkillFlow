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
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,
                         'svg.fonttype':'none','text.color':'#263746'})
    fig,axes=plt.subplots(1,2,figsize=(7.1,2.7),layout='constrained',
                          gridspec_kw={'width_ratios':[1.16,1]})
    colors=['#2866A0','#8494A4','#268C82','#D27A29']
    markers=['o','s','D','v']
    specs=[(axes[0],left,repair['layers'],
            ['S: skill states','C: source cache','SC: joint repair','SC + reader recut'],
            '(a) Source-state and cache repair','Answer accuracy'),
           (axes[1],right,edges['layers'],
            ['Reader to source','Source to source','Both paths'],
            '(b) Which attention path matters?','Fraction of correct answers lost')]
    for ax,matrix,layers,labels,title,ylabel in specs:
        x=np.arange(len(layers))
        offsets=np.linspace(-.24,.24,len(labels))
        for i,(label,offset) in enumerate(zip(labels,offsets)):
            vals=matrix[i]
            color=colors[i] if ax is axes[0] else [colors[3],colors[0],colors[1]][i]
            ax.vlines(x+offset,0,vals,color=color,alpha=.17,lw=2)
            points=ax.scatter(x+offset,vals,color=color,marker=markers[i],s=31,
                       edgecolors='white',linewidths=.55,zorder=4,label=label)
            points.set_gid(f'measured-{"repair" if ax is axes[0] else "edges"}-{i}')
        ax.set(xticks=x,xticklabels=layers,ylim=(-.025,1.04),
               yticks=[0,.25,.5,.75,1],xlabel='Intervention layer',ylabel=ylabel)
        ax.set_yticklabels(['0','.25','.50','.75','1.0'])
        ax.set_title(title,loc='left',fontsize=8.5,fontweight='bold',pad=38)
        ax.legend(loc='lower left',bbox_to_anchor=(-.02,1.005),
                  ncol=2,fontsize=6.4,frameon=False,columnspacing=.7,
                  handletextpad=.35,borderaxespad=0)
        ax.spines[['top','right']].set_visible(False)
        ax.spines[['bottom','left']].set_color('#AAB4BE')
        ax.tick_params(labelsize=7,length=2.5,color='#AAB4BE')
        ax.grid(axis='y',color='#E8EDF2',lw=.6)
        ax.set_axisbelow(True)
    # The central contrast is annotated without repeating the whole table.
    axes[0].annotate('Joint repair',xy=(2+.08,left[2,2]),xytext=(1.1,.58),
                     fontsize=7,color=colors[2],
                     arrowprops={'arrowstyle':'-','color':colors[2],'lw':.7})
    axes[1].text(2,.88,'Reader access dominates',ha='center',fontsize=6.5,color='#94551D')
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
