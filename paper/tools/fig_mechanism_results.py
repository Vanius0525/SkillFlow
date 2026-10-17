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
    left=np.array(primary['accuracy'])[2:]
    right=np.array(edges['loss'])
    if left.shape!=(4,4) or right.shape!=(3,3):
        raise ValueError('Unexpected measured arm grid')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,
                         'svg.fonttype':'none','text.color':'#263746'})
    fig,axes=plt.subplots(1,2,figsize=(7.1,2.55),layout='constrained',
                          gridspec_kw={'width_ratios':[1.12,1]})
    specs=[(axes[0],left,repair['layers'],['S: residual','C: cache','SC: joint','SC + recut'],
            'Blues','(a) Source-state and cache repair','Answer accuracy',
            primary['n'],len(primary['groups'])),
           (axes[1],right,edges['layers'],['Reader → source','Source → source','Both paths'],
            'Oranges','(b) Which attention path matters?','Accuracy lost after the cut',
            edges['rescued_n'],len(edges['groups']))]
    for ax,matrix,layers,rows,cmap,title,cblabel,n,g in specs:
        im=ax.imshow(matrix,vmin=0,vmax=1,cmap=cmap,aspect='auto',interpolation='nearest')
        ax.set_xticks(range(len(layers)),layers)
        ax.set_yticks(range(len(rows)),rows)
        ax.set_xlabel('Intervention layer',fontsize=8)
        ax.set_title(title+f'\n(n={n}; {g} skills)',loc='left',fontsize=8,fontweight='bold',pad=8)
        ax.tick_params(length=0,labelsize=7)
        ax.spines[:].set_visible(False)
        for (r,c),value in np.ndenumerate(matrix):
            ax.text(c,r,f'{value:.2f}',ha='center',va='center',fontsize=8,
                    color='white' if value>.65 else '#253E50')
        bar=fig.colorbar(im,ax=ax,orientation='horizontal',fraction=.085,pad=.16,shrink=.87)
        bar.set_ticks([0,.5,1]);bar.ax.tick_params(labelsize=6,length=2)
        bar.set_label(cblabel,fontsize=7,labelpad=2)
        bar.outline.set_visible(False)
    for ext in ('pdf','png','svg'):
        fig.savefig(FIG/f'fig-mechanism-results.{ext}',dpi=240,facecolor='white')
    metadata=dict(repair_source_sha256=hashlib.sha256(repair_path.read_bytes()).hexdigest(),
                  edges_source_sha256=hashlib.sha256(edges_path.read_bytes()).hexdigest(),
                  repair_n=primary['n'],edges_n=edges['rescued_n'],
                  repair_ids=primary['ids'],edges_ids=edges['rescued_ids'],
                  repair_layers=repair['layers'],edges_layers=edges['layers'],
                  repair_accuracy=left.tolist(),edge_loss=right.tolist())
    (FIG/'fig-mechanism-results-values.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__=='__main__':main()
