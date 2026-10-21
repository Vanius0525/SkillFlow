"""Reproducible Figure 4 alternatives; no manuscript files overwritten."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from figure_fonts import configure_fonts
configure_fonts()
OUT=Path(__file__).resolve().parent
rows=json.loads((OUT/'data.json').read_text())['rows']
ARMS=['cut_reader_both','cut_self_both']
COLORS=['#D27A29','#2866A0']
LABELS=['Post-skill to skill','Skill to skill']
cmap=LinearSegmentedColormap.from_list('accuracy',['#F6F9FA','#A8D3CD','#176E68'])
labels=[r['label'].replace('Llama-3.1-8B','Llama-8B')+' / '+('MC' if r['task']=='MedCalc' else 'TQA') for r in rows]
def save(fig,name):
 for ext in ['png','pdf','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=240,facecolor='white',bbox_inches='tight')
 plt.close(fig)
def clean(ax):
 ax.spines[['top','right','left','bottom']].set_visible(False);ax.tick_params(length=0,labelsize=9)
def repair(ax):
 z=np.array([[100*r['repair'][arm]['16']['accuracy'] for arm in ['S','C','SC','SC_recut']] for r in rows])
 ax.imshow(z,vmin=0,vmax=100,aspect='auto',cmap=cmap)
 for i in range(8):
  for j in range(4):ax.text(j,i,f'{z[i,j]:.1f}',ha='center',va='center',fontsize=9,color='white' if z[i,j]>65 else '#263746')
 ax.set(xticks=range(4),xticklabels=['S','C','SC','SC + recut'],yticks=range(8),yticklabels=labels)
 ax.set_title('(a) L16 repair accuracy (%)',loc='left',fontweight='bold',fontsize=12,pad=16);clean(ax)
 for k in [1.5,3.5,5.5]:ax.axhline(k,color='#CAD4DC',lw=.8)
def bars(ax,layer,show_labels=False,numbers=False):
 y=np.arange(8)
 for j,(arm,color,label) in enumerate(zip(ARMS,COLORS,LABELS)):
  v=[100*(1-r['edges'][arm][str(layer)]['accuracy']) for r in rows]
  yy=y+(j-.5)*.30
  ax.barh(yy,v,height=.26,color=color,label=label,zorder=3)
  if numbers:
   for x,yi in zip(v,yy):ax.text(x+1,yi,f'{x:.1f}',va='center',fontsize=7)
 ax.set(yticks=y,yticklabels=labels if show_labels else [],ylim=(7.5,-.5),xlim=(0,112 if numbers else 100),xticks=[0,25,50,75,100])
 ax.grid(axis='x',color='#E8EDF2',lw=.7);ax.set_axisbelow(True);clean(ax)
 for k in [1.5,3.5,5.5]:ax.axhline(k,color='#CAD4DC',lw=.8)
# Current GitHub layout, horizontal bars.
f,axs=plt.subplots(1,2,figsize=(11,5.3),gridspec_kw={'width_ratios':[1.25,1]},layout='constrained')
repair(axs[0]);bars(axs[1],24,numbers=True)
axs[1].set_title('(b) L24 path dependence',loc='left',fontweight='bold',fontsize=12,pad=16)
axs[1].set_xlabel('Originally correct answers lost (%)');f.legend(*axs[1].get_legend_handles_labels(),loc='outside upper center',ncol=2,frameon=False)
save(f,'01_github_L24_horizontal')
# All eight combinations and three measured intervention layers.
f,axs=plt.subplots(1,4,figsize=(15,5.2),gridspec_kw={'width_ratios':[1.25,1,1,1]},layout='constrained')
repair(axs[0])
for ax,layer in zip(axs[1:],[8,16,24]):
 bars(ax,layer);ax.set_title(f'L{layer}',fontsize=12,fontweight='bold',pad=16);ax.set_xlabel('Correct answers lost (%)')
f.legend(*axs[1].get_legend_handles_labels(),loc='outside upper center',ncol=2,frameon=False,title='(b) Attention-path dependence across layers')
save(f,'02_eight_combinations_multilayer_horizontal')
# Single-case Overleaf content, replacing b with grouped vertical bars.
r=rows[0];f,axs=plt.subplots(1,2,figsize=(10.8,4.2),layout='constrained')
z=np.array([[100*r['repair'][arm][str(l)]['accuracy'] for l in [8,12,16,24]] for arm in ['S','C','SC','SC_recut']])
axs[0].imshow(z,vmin=0,vmax=100,aspect='auto',cmap=cmap)
for i in range(4):
 for j in range(4):axs[0].text(j,i,f'{z[i,j]:.1f}',ha='center',va='center',color='white' if z[i,j]>65 else '#263746',fontsize=10)
axs[0].set(xticks=range(4),xticklabels=['L8','L12','L16','L24'],yticks=range(4),yticklabels=['S','C','SC','SC + recut'],xlabel='Replacement layer');axs[0].set_title('(a) Repair accuracy (%)',loc='left',fontweight='bold')
for j,(arm,col,label) in enumerate(zip(ARMS,COLORS,LABELS)):
 v=[100*(1-r['edges'][arm][str(l)]['accuracy']) for l in [8,16,24]];x=np.arange(3)+(j-.5)*.30
 axs[1].bar(x,v,width=.28,color=col,label=label,zorder=3)
 for xx,vv in zip(x,v):axs[1].text(xx,vv+1.2,f'{vv:.1f}',ha='center',fontsize=8)
axs[1].set(xticks=range(3),xticklabels=['L8','L16','L24'],ylim=(0,108),yticks=[0,25,50,75,100],ylabel='Correct answers lost (%)',xlabel='Intervention layer');axs[1].grid(axis='y',color='#E8EDF2');axs[1].set_axisbelow(True);axs[1].set_title('(b) Attention-path dependence',loc='left',fontweight='bold')
for ax in axs:clean(ax)
f.legend(*axs[1].get_legend_handles_labels(),loc='outside upper center',ncol=2,frameon=False,title='Qwen3-8B / MedCalc')
save(f,'03_overleaf_single_case_multilayer_vertical')
# Eight small multiples: vertical bars, all measured layers.
f,axs=plt.subplots(2,4,figsize=(13,6),layout='constrained',sharey=True)
for ax,r,label in zip(axs.flat,rows,labels):
 for j,(arm,col,legend) in enumerate(zip(ARMS,COLORS,LABELS)):
  v=[100*(1-r['edges'][arm][str(l)]['accuracy']) for l in [8,16,24]]
  ax.bar(np.arange(3)+(j-.5)*.30,v,width=.28,color=col,label=legend,zorder=3)
 ax.set(xticks=range(3),xticklabels=['L8','L16','L24'],ylim=(0,103),yticks=[0,25,50,75,100]);ax.set_title(label,fontsize=11);ax.grid(axis='y',color='#E8EDF2');ax.set_axisbelow(True);clean(ax)
for ax in axs[:,0]:ax.set_ylabel('Correct answers lost (%)')
f.legend(*axs.flat[0].get_legend_handles_labels(),loc='outside upper center',ncol=2,frameon=False,title='(b) Attention-path dependence across layers')
save(f,'04_panel_b_multilayer_small_multiples')
print('Generated four variants in PNG/PDF/SVG')

# Contact sheet for desktop review.
from PIL import Image, ImageDraw
tiles=[]
for path in sorted(OUT.glob('0*.png')):
 im=Image.open(path).convert('RGB');im.thumbnail((1400,650))
 tile=Image.new('RGB',(1440,700),'white');tile.paste(im,((1440-im.width)//2,35))
 ImageDraw.Draw(tile).text((20,10),path.stem,fill='black');tiles.append(tile)
overview=Image.new('RGB',(1440,700*len(tiles)),'white')
for i,tile in enumerate(tiles):overview.paste(tile,(0,700*i))
overview.save(OUT/'overview.png')
