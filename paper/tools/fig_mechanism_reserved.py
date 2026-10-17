#!/usr/bin/env python3
"""Draft-only layout reservation. Blank cells are intentionally unmeasured."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

PAPER=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42})
fig,axes=plt.subplots(1,2,figsize=(7.1,1.95),gridspec_kw={'width_ratios':[1.1,1]},layout='constrained')
for ax,layers,rows,title in [
    (axes[0],[8,12,16,24],['S: source residual','C: source cache','SC: joint repair','SC + reader recut'],'(a) Repair the receiving computation'),
    (axes[1],[8,16,24],['Reader → source','Source → source','Both paths'],'(b) Separate attention paths')]:
    ax.set_xlim(-.5,len(layers)-.5);ax.set_ylim(len(rows)-.5,-.5)
    for r in range(len(rows)):
        for c in range(len(layers)):
            ax.add_patch(Rectangle((c-.47,r-.43),.94,.86,facecolor='white',
                                   edgecolor='#CCD5DC',linewidth=.7))
    ax.set_xticks(range(len(layers)),layers)
    ax.set_yticks(range(len(rows)),rows)
    ax.tick_params(length=0,labelsize=7)
    ax.spines[:].set_visible(False)
    ax.set_xlabel('Intervention layer',fontsize=7)
    ax.set_title(title,loc='left',fontsize=8,fontweight='bold',color='#284A63',pad=10)
fig.suptitle('RESULTS PENDING — RESERVED DRAFT PANELS',fontsize=9,fontweight='bold',color='#8F6738')
for ext in ('pdf','png'):
    fig.savefig(PAPER/f'figures/fig-mechanism-reserved.{ext}',dpi=220,facecolor='white')
