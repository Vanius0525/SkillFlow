#!/usr/bin/env python3
"""Measured eight-cell overview; no pooling across populations."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from _paths import VALUES,AUDIT
from style_main_figures import BLUE,ORANGE,TEAL,frame,save

def main():
 rows=json.loads((VALUES/'eight-cell-display-values.json').read_text())['rows'];depth=json.loads((VALUES/'depth-current-values.json').read_text());lookup={(r['model'],r['task']):r for r in depth}
 fig,axes=plt.subplots(1,3,figsize=(7.1,2.65),layout='constrained',sharey=True)
 y=np.arange(8);labels=[r['label'].replace('Llama-3.1-8B','Llama-8B')+' / '+('MC' if r['task']=='MedCalc' else 'TQA') for r in rows]
 a,b,c=axes
 a.scatter([100*r['battery_l2']['real']['accuracy'] for r in rows],y-.12,color=BLUE,s=18,label='L2')
 a.scatter([100*r['battery_l8']['real']['accuracy'] for r in rows],y+.12,color=ORANGE,marker='s',s=18,label='L8')
 a.set(yticks=y,yticklabels=labels,ylim=(7.5,-.5),xlim=(0,105),xticks=[0,50,100],xlabel='Span-patch accuracy (%)')
 gaps=[100*(lookup[r['model'],r['task']]['reading_boundary']-lookup[r['model'],r['task']]['transfer_boundary'])/lookup[r['model'],r['task']]['n_layers'] for r in rows]
 b.barh(y,gaps,height=.5,color=TEAL);b.set(xlim=(0,70),xticks=[0,30,60],xlabel='Boundary gap / depth (%)')
 c.scatter([r['gain_pp'] for r in rows],y-.12,color=BLUE,s=18,label='SC − S')
 c.scatter([r['recut_loss_pp'] for r in rows],y+.12,color=ORANGE,marker='s',s=18,label='Recut loss')
 c.set(xlim=(0,50),xticks=[0,20,40],xlabel='L16 accuracy difference (pp)')
 for ax,title in zip(axes,['(a) State transfer','(b) Depth separation','(c) Partial repair']):
  frame(ax,title);ax.set_title(title,loc='left',fontweight='bold',pad=30);ax.grid(False);ax.grid(axis='x',color='#E8EDF2',lw=.5);ax.tick_params(labelsize=7,length=0);ax.spines['left'].set_visible(False);ax.set_xlabel(ax.get_xlabel(),fontsize=8)
  for k in [1.5,3.5,5.5]:ax.axhline(k,color='#E8EDF2',lw=.5)
 for ax in [a,c]:ax.legend(loc='lower center',bbox_to_anchor=(.5,1.0),ncol=2,fontsize=7,columnspacing=.8,handletextpad=.3)
 save(fig,'fig-teaser')
 (AUDIT/'TEASER-EIGHT-CELL-20261020.json').write_text(json.dumps({'cells':8,'gaps_percent_depth':gaps,'models':[r['model'] for r in rows],'tasks':[r['task'] for r in rows]},indent=2)+'\n')
if __name__=='__main__':main()
