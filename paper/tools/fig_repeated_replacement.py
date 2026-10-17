#!/usr/bin/env python3
"""Plot measured replacement windows without changing numerical records."""
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from _paths import VALUES, FIGURES, AUDIT
from style_main_figures import BLUE, TEAL, ORANGE, frame, save


def main():
    source=VALUES/'main-evidence-values.json'
    raw=source.read_bytes()
    data=json.loads(raw)
    single=dict(data['sufficiency'])
    rows=[('0–35',data['windows']['w0_35'],36,TEAL),
          ('8–11',data['windows']['w8_11'],4,BLUE),
          ('12–15',data['windows']['w12_15'],4,BLUE),
          ('14–19',data['windows']['w14_19'],6,BLUE),
          ('16–35',data['windows']['w16_35'],20,ORANGE),
          ('16 only',single[16],1,ORANGE)]
    fig,ax=plt.subplots(figsize=(3.45,2.35),layout='constrained')
    y=np.arange(len(rows))[::-1]
    ax.axhspan(-.42,1.42,color='#FFF5E9',zorder=0,lw=0)
    bars=ax.barh(y,[r[1] for r in rows],height=.50,
                 color=[r[3] for r in rows],zorder=3)
    bars[-1].set_facecolor('white')
    bars[-1].set_edgecolor(ORANGE)
    bars[-1].set_linewidth(1.1)
    for i,(label,value,count,color) in enumerate(rows):
        bars[i].set_gid(f'measured-window-{i}')
        ax.text(value+.025,y[i],f'{value:.2f}',va='center',fontsize=7,color='#263746')
        ax.text(1.175,y[i],str(count),va='center',ha='center',fontsize=6.7,color='#53616F')
    ax.set(yticks=y,yticklabels=[r[0] for r in rows],xlim=(0,1.24),
           ylim=(-.65,5.9),xlabel=r'Skill-transfer recovery $\rho$')
    ax.set_xticks([0,.25,.5,.75,1],['0','.25','.50','.75','1.0'])
    frame(ax)
    ax.grid(False)
    ax.vlines([.25,.5,.75,1],-.65,5.45,color='#E8EDF2',lw=.55,zorder=1)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_bounds(0,1)
    ax.tick_params(axis='y',length=0,pad=5)
    ax.text(-.035,5.65,'Layers patched',transform=ax.get_yaxis_transform(),
            ha='right',fontsize=6.7,color='#53616F')
    ax.text(1.175,5.65,'Writes',ha='center',fontsize=6.7,color='#53616F')
    ax.set_title('Qwen3-8B · MedCalc',loc='left',fontweight='bold',fontsize=8.5,pad=7)
    save(fig,'fig-repeated-replacement')
    assert source.read_bytes()==raw
    report={'source_sha256':hashlib.sha256(raw).hexdigest(),
            'n':data['window_n'],'groups':data['groups'],
            'rows':[{'layers':r[0],'recovery':r[1],'writes':r[2]} for r in rows],
            'point_estimates_only':True}
    (AUDIT/'REPEATED-REPLACEMENT-20261017.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Rendered six measured conditions; source values unchanged.')


if __name__=='__main__':main()
