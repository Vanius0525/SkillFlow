#!/usr/bin/env python3
"""Eight main model/benchmark cells, measured L16 repair and L24 path cuts."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from _paths import VALUES,FIGURES
from figure_fonts import configure_fonts

def main():
 configure_fonts();rows=json.loads((VALUES/'eight-cell-display-values.json').read_text())['rows']
 from matplotlib.colors import LinearSegmentedColormap
 fig,axes=plt.subplots(1,2,figsize=(7.1,3.8),layout='constrained',gridspec_kw={'width_ratios':[1.5,1]})
 a,b=axes;left=np.array([[r['repair'][arm]['16']['accuracy'] for arm in ['S','C','SC','SC_recut']] for r in rows])*100
 a.imshow(left,vmin=0,vmax=100,aspect='auto',cmap=LinearSegmentedColormap.from_list('accuracy',['#F6F9FA','#A8D3CD','#176E68']))
 for i,r in enumerate(rows):
  for j in range(4):a.text(j,i,f'{left[i,j]:.1f}',ha='center',va='center',fontsize=8,color='white' if left[i,j]>65 else '#263746')
 labels=[r['label'].replace('Llama-3.1-8B','Llama-8B')+' / '+('MC' if r['task']=='MedCalc' else 'TQA')+f"  ({r['n']}/{r['groups']})" for r in rows]
 a.set(xticks=range(4),xticklabels=['S','C','SC','SC + recut'],yticks=range(8),yticklabels=labels)
 a.set_title('(a) L16 repair accuracy (%)',loc='left',fontsize=10,fontweight='bold',pad=33)
 a.tick_params(length=0,labelsize=8,pad=6);a.set_xlabel('Independent questions / skills in parentheses',fontsize=8)
 for j,(arm,label,color,marker) in enumerate([('cut_reader_both','Post-skill to skill','#D27A29','o'),('cut_self_both','Skill to skill','#2866A0','s'),('cut_both_both','Both paths','#8494A4','D')]):
  loss=[100*(1-r['edges'][arm]['24']['accuracy']) for r in rows]
  b.scatter(loss,np.arange(8)+(j-1)*.19,label=label,color=color,marker=marker,s=23,edgecolors='white',linewidths=.4,zorder=3)
 b.set(yticks=range(8),yticklabels=[],ylim=(7.5,-.5),xlim=(-3,103),xticks=[0,25,50,75,100],xlabel='Originally correct answers lost (%)')
 b.set_title('(b) L24 path dependence',loc='left',fontsize=10,fontweight='bold',pad=33)
 b.legend(loc='lower left',bbox_to_anchor=(-.03,1.005),fontsize=7,frameon=False,ncol=1,labelspacing=.2,handletextpad=.4)
 b.grid(axis='x',color='#E8EDF2',lw=.6);b.set_axisbelow(True);b.tick_params(length=0,labelsize=8)
 for ax in axes:
  for k in [1.5,3.5,5.5]:ax.axhline(k,color='#CAD4DC',lw=.7)
  ax.spines[['top','right','left','bottom']].set_visible(False)
 for ext in ['pdf','png','svg']:fig.savefig(FIGURES/f'fig-mechanism-results.{ext}',dpi=240,facecolor='white')
 svg=FIGURES/'fig-mechanism-results.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
 (FIGURES/'fig-mechanism-results-values.json').write_text(json.dumps({'cells':8,'repair_layer':16,'path_layer':24,'rows':rows},indent=2)+'\n')
 plt.close(fig)
if __name__=='__main__':main()
