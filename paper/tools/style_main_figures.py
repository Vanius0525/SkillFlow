#!/usr/bin/env python3
"""Render publication figures from audited values, without recomputing results.

Run after the numeric generators. Every point and interval comes directly from
values/*.json; the input hashes are recorded to make a style-only rerender
reviewable. This script never writes the numerical records.
"""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from _paths import FIGURES, VALUES, AUDIT

BLUE, TEAL, ORANGE, PURPLE, GRAY = '#2864A5', '#278577', '#C76B28', '#8963A9', '#778391'
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.titlesize': 9,
    'axes.labelsize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 7, 'pdf.fonttype': 42, 'ps.fonttype': 42,
    'axes.edgecolor': '#AAB4BE', 'axes.labelcolor': '#263746',
    'text.color': '#263746', 'xtick.color': '#53616F', 'ytick.color': '#53616F',
    'axes.linewidth': .6, 'grid.color': '#E8EDF2', 'grid.linewidth': .55,
    'legend.frameon': False, 'savefig.facecolor': 'white',
})
INPUTS = ['fig-channels-values.json', 'main-evidence-values.json',
          'fig-rank-values.json', 'posbudget.json']

def data(name):
    return json.loads((VALUES/name).read_text())

def frame(ax, title=None):
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y')
    ax.tick_params(length=3, width=.6)
    if title:
        ax.set_title(title, loc='left', fontweight='bold', pad=8)

def save(fig, name):
    fig.savefig(FIGURES/f'{name}.pdf', bbox_inches='tight', pad_inches=.035)
    fig.savefig(FIGURES/f'{name}.png', bbox_inches='tight', pad_inches=.035, dpi=220)
    plt.close(fig)

def err(values):
    return [[max(v-lo, 0) for v, lo, hi in values],
            [max(hi-v, 0) for v, lo, hi in values]]

def channels():
    d=data(INPUTS[0])
    fig, axes=plt.subplots(1, 2, figsize=(7.1, 2.25), layout='constrained')
    specs=[('top', [('tq1','Last position'),('tq16','Last 16 positions'),
                    ('tq256',r'Last $\leq$256 positions')], '(a) After the skill'),
           ('bottom', [('real','Correct content'),('a0.5','Half dose'),
                       ('dcross','Other skill'),('dshuf','Permuted positions'),
                       ('drand','Matched noise')], '(b) At the skill positions')]
    for ax,(key,rows,title) in zip(axes,specs):
        yy=np.arange(len(rows))[::-1]+(5-len(rows))/2
        vals=[d[key][k]['acc'] for k,_ in rows]
        colors=[BLUE if key=='bottom' and k=='real' else GRAY for k,_ in rows]
        ax.barh(yy,[v[0] for v in vals],height=.53,color=colors,alpha=.88,zorder=2)
        ax.errorbar([v[0] for v in vals],yy,xerr=err(vals),fmt='none',
                    ecolor='#34495A',capsize=2,lw=.85,zorder=3)
        for y,v in zip(yy,vals):
            ax.text(v[2]+.025,y,f'{v[0]:.2f}',va='center',fontsize=7.5)
        ax.axvline(d['gold'][0],ls='--',color=TEAL,lw=1)
        ax.axvline(0,ls=':',color=GRAY,lw=1)
        ax.set(yticks=yy,yticklabels=[v for _,v in rows],xlim=(0,1.08),
               ylim=(-.65,4.7),xlabel='Answer accuracy')
        ax.set_xticks([0,.25,.5,.75,1],['0','.25','.50','.75','1.0'])
        frame(ax,title)
        ax.grid(False);ax.grid(axis='x')
        ax.text(.02,1.025,f'Layer 8 · n = {d["n"]}',transform=ax.transAxes,
                fontsize=7,color=GRAY)
        ax.text(.98,.98,'Correct skill: 0.92',transform=ax.transAxes,
                ha='right',va='top',fontsize=7,color=TEAL)
    save(fig,'fig-channels-medcalc')

def depth():
    d=data(INPUTS[1])
    fig,(a,b)=plt.subplots(1,2,figsize=(7.1,2.65),layout='constrained',
                          gridspec_kw={'width_ratios':[1.22,1]})
    for key,color,marker,ls,label in [
        ('sufficiency',BLUE,'o','-',r'Span transfer: recovery $\rho$'),
        ('necessity',ORANGE,'s','-',r'Reading blocked: retained $q$'),
        ('last_position',GRAY,'^','--','Final-position transfer')]:
        x,y=zip(*d[key]);a.plot(x,y,color=color,marker=marker,ms=2.5,lw=1.5,ls=ls,label=label)
    tb,rb=d['transfer_boundary'],d['reading_boundary']
    a.axvspan(tb-.5,rb-.5,color=ORANGE,alpha=.09,lw=0)
    for x in (tb,rb):a.axvline(x-.5,color=ORANGE,lw=.8,ls=':')
    a.text(18.5,.73,'Weak transfer\ncontinued reading',ha='center',
           va='center',fontsize=8,color='#96521E')
    a.text(tb-.5,1.04,'L13',ha='center',fontsize=7,color=ORANGE)
    a.text(rb-.5,1.04,'L25',ha='center',fontsize=7,color=ORANGE)
    a.set(xlabel='Intervention layer L',ylabel='Recovery / retained fraction')
    frame(a,'(a) Transfer and reading separate')
    fig.legend(*a.get_legend_handles_labels(),loc='outside upper center',ncol=3,
               fontsize=7,handlelength=1.7)
    x,y=zip(*d['sufficiency']);b.plot(x,y,color=BLUE,alpha=.25,lw=1.2)
    for key,value in d['windows'].items():
        lo,hi=map(int,key[1:].split('_'))
        color=TEAL if lo==0 and hi==35 else PURPLE if hi-lo>5 else BLUE
        b.plot([lo,hi],[value,value],color=color,lw=4,solid_capstyle='round',alpha=.9)
        if (lo,hi) in [(0,35),(8,11),(12,15),(14,19),(16,35)]:
            center=(lo+hi)/2
            offset={(0,35):.055,(8,11):-.10,(12,15):-.10,(14,19):.055,(16,35):-.105}[(lo,hi)]
            if (lo,hi)==(8,11):center=6
            b.text(center,value+offset,f'{lo}–{hi}: {value:.2f}',ha='center',fontsize=7)
    b.text(23,.37,'Late windows do not\nrestore early recovery',ha='center',
           fontsize=8,color='#626D78')
    b.set(xlabel='Layers receiving donor states',ylabel=r'Recovery $\rho$')
    frame(b,'(b) Late repetition does not rescue')
    for ax in (a,b):
        ax.set(xlim=(-1,36),ylim=(-.06,1.12),xticks=[0,8,16,24,35],yticks=[0,.25,.5,.75,1])
        ax.axhline(.5,color=GRAY,ls=':',lw=.8)
    save(fig,'fig-transfer-reading')

def rank():
    d=data(INPUTS[2]);fig,axes=plt.subplots(1,3,figsize=(7.1,2.4),sharey=True,layout='constrained')
    for ax,(name,color,marker) in zip(axes,[('Qwen3-8B',BLUE,'o'),('Qwen3-0.6B',TEAL,'^'),('Mistral-7B',PURPLE,'D')]):
        c=d[name]
        for key,ls in [('top','-'),('bottom','--')]:
            pts=sorted((int(k),v) for k,v in c[key].items())
            x=[k for k,v in pts];values=[v for k,v in pts]
            ax.errorbar(x,[v[0] for v in values],yerr=err(values) if key=='top' else None,
                        color=color,marker=marker if key=='top' else 's',ms=3,lw=1.4,
                        ls=ls,mfc=color if key=='top' else 'white',capsize=1.5,elinewidth=.7)
        ax.axhline(c['full'],color=color,alpha=.6,lw=.85,ls=':')
        ax.text(.03,.94,f'n = {c["n"]}\n$k^*$ = {c["kstar"]:.0f}',transform=ax.transAxes,
                va='top',fontsize=8,color=color)
        ax.set_xscale('log',base=2)
        ax.set(xlim=(.8,640),ylim=(-.04,1.19),xlabel='Retained directions k')
        ax.set_xticks([1,4,16,64,256],['1','4','16','64','256'])
        frame(ax,name)
    axes[0].set_ylabel(r'Recovery $\rho$')
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([],[],color=GRAY,marker='o',ms=3,label='Leading directions'),
                        Line2D([],[],color=GRAY,ls='--',marker='s',mfc='white',ms=3,label='Bottom directions'),
                        Line2D([],[],color=GRAY,ls=':',label='Untruncated span')],
               loc='outside upper center',ncol=3,fontsize=7)
    save(fig,'fig-rank-medcalc')

def position():
    d=data(INPUTS[3]);A=d['arms'];full=A['evfull']['rho'];median=d['span_width']['median']
    fig,axes=plt.subplots(2,2,figsize=(7.1,4.5),layout='constrained')
    a,b,c,e=axes.flat
    def series(ax,pts,color,marker,label,ls='-'):
        x=[x for x,v in pts];vs=[(v['rho'],*v['ci_cluster']) for x,v in pts]
        ax.errorbar(x,[v[0] for v in vs],yerr=err(vs),color=color,marker=marker,
                    ms=3,lw=1.2,capsize=1.5,elinewidth=.6,label=label,ls=ls)
    for key,label,color,marker in [('ev','Evenly spaced',BLUE,'o'),('rn','Random',TEAL,'s'),
                                 ('td','Largest change',PURPLE,'D'),('mx','Misplaced',ORANGE,'v'),
                                 ('tq','After the skill',GRAY,'x')]:
        budgets=['1','4','16','64','256']+(['half'] if key!='tq' else [])+(['full'] if key=='mx' else [])
        series(a,[(A[key+k]['positions'],A[key+k]) for k in budgets if key+k in A],color,marker,label)
    series(a,[(median,A['evfull'])],BLUE,'*','Full span')
    a.set_xscale('log',base=2);a.set_xticks([1,4,16,64,256,1024],['1','4','16','64','256','1024'])
    a.set_xlabel('Positions written');a.legend(loc='upper left',ncol=2,fontsize=6.8)
    for budget,color,marker,label in [('256',BLUE,'o','256 positions'),('half',PURPLE,'s','Half span')]:
        series(b,[(n,A[f'c{n}x{budget}']) for n in [1,2,4,8,16,32] if f'c{n}x{budget}' in A],color,marker,label)
        b.axhline(A['rn'+budget]['rho'],color=color,ls=':',lw=1)
    b.set_xscale('log',base=2);b.set_xticks([1,2,4,8,16,32],['1','2','4','8','16','32'])
    b.set_xlabel('Number of blocks (fixed token budget)');b.legend(loc='upper right')
    names=[('wf','procedure'),('wd','description'),('wr','random'),('we','example')]
    for off,budget,color,label in [(-.18,'256',BLUE,'256 positions'),(.18,'half',PURPLE,'Half span')]:
        vs=[A[k+budget] for k,_ in names];xx=np.arange(4)+off
        c.bar(xx,[v['rho'] for v in vs],width=.31,color=color,alpha=.88,label=label)
        c.errorbar(xx,[v['rho'] for v in vs],yerr=err([(v['rho'],*v['ci_cluster']) for v in vs]),
                   fmt='none',ecolor='#34495A',capsize=2,lw=.7)
        for x,v in zip(xx,vs):c.text(x,v['ci_cluster'][1]+.015,f'{v["rho"]:.2f}',ha='center',fontsize=6.5)
    c.set_xticks(range(4),[n for _,n in names]);c.set_xlabel('Section at the centre of one block')
    c.legend(loc='upper right',fontsize=7)
    pts=[(.5,A['evfull'])]+[(n,A[f'sh{n}']) for n in [1,4,16,64,256]]+[(median/2,A['mxfull'])]
    series(e,pts,ORANGE,'o','cyclic shift')
    for key,color,marker,label in [('sn',PURPLE,'s','Later, no wrap'),('sb',BLUE,'D','Earlier, no wrap')]:
        series(e,[(n,A[f'{key}{n}']) for n in [1,4,16]],color,marker,label,'--')
    series(e,list(zip([.62,.68,.74,.8],[A[k] for k in ['xf1','xf16','xl1','xl16']])),TEAL,'v','Trim edges, in place',ls='none')
    series(e,[(median*.9,A['dshuf'])],GRAY,'x','Permuted')
    e.set_xscale('log',base=2);e.set_xticks([.5,1,4,16,64,256],['0','1','4','16','64','256'])
    e.set_xlabel('Position displacement D');e.legend(loc='upper right',fontsize=6.8)
    for ax,title in zip(axes.flat,['(a) More positions alone are insufficient','(b) Block selection changes recovery',
                                  '(c) Procedure-centred blocks recover more','(d) Displacement disrupts transfer']):
        ax.axhline(full,color=TEAL,ls='--',lw=.9,alpha=.6)
        ax.set(ylim=(-.04,1.07),yticks=[0,.25,.5,.75,1]);frame(ax,title)
    for ax in [a,c]:ax.set_ylabel(r'Recovery $\rho$')
    save(fig,'fig-posbudget')

if __name__=='__main__':
    before={f:hashlib.sha256((VALUES/f).read_bytes()).hexdigest() for f in INPUTS}
    channels();depth();rank();position()
    after={f:hashlib.sha256((VALUES/f).read_bytes()).hexdigest() for f in INPUTS}
    assert before==after
    (AUDIT/'FIGURE-STYLE-20261014.json').write_text(json.dumps({'input_sha256':before,
        'numeric_records_unchanged':True,'figures': ['fig-channels-medcalc','fig-transfer-reading',
        'fig-rank-medcalc','fig-posbudget']},indent=2)+'\n')
    print('Rendered four figures; numerical records unchanged.')
