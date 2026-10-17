#!/usr/bin/env python3
"""Render publication figures from audited values, without recomputing results.

Run after the numeric generators. Every displayed point comes directly from
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

BLUE, TEAL, ORANGE, PURPLE, GRAY = '#2866A0', '#268C82', '#D27A29', '#8772AE', '#8693A0'
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.titlesize': 9,
    'axes.labelsize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 7, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    'axes.edgecolor': '#AAB4BE', 'axes.labelcolor': '#263746',
    'text.color': '#263746', 'xtick.color': '#53616F', 'ytick.color': '#53616F',
    'axes.linewidth': .6, 'grid.color': '#E8EDF2', 'grid.linewidth': .55,
    'legend.frameon': False, 'savefig.facecolor': 'white',
})
INPUTS = ['fig-channels-values.json', 'depth-crossmodel-values.json']

def data(name):
    return json.loads((VALUES/name).read_text())

def frame(ax, title=None):
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y')
    ax.set_facecolor('white')
    ax.tick_params(length=3, width=.6)
    if title:
        ax.set_title(title, loc='left', fontweight='bold', pad=8)

def save(fig, name):
    fig.savefig(FIGURES/f'{name}.pdf', bbox_inches='tight', pad_inches=.035)
    fig.savefig(FIGURES/f'{name}.png', bbox_inches='tight', pad_inches=.035, dpi=220)
    fig.savefig(FIGURES/f'{name}.svg', bbox_inches='tight', pad_inches=.035)
    svg=FIGURES/f'{name}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)

def err(values):
    return [[max(v-lo, 0) for v, lo, hi in values],
            [max(hi-v, 0) for v, lo, hi in values]]

def channels():
    d=data(INPUTS[0])
    fig, axes=plt.subplots(1, 2, figsize=(7.1, 2.35), layout='constrained')
    specs=[('top', [('tq1','Last 1'),('tq16','Last 16'),
                    ('tq256',r'Last $\leq$256')], '(a) After skill'),
           ('bottom', [('real','Correct skill'),('a0.5','Half dose'),
                       ('dcross','Other skill'),('dshuf','Permuted'),
                       ('drand','Noise')], '(b) Skill span')]
    for ax,(key,rows,title) in zip(axes,specs):
        yy=np.arange(len(rows))[::-1]+(5-len(rows))/2
        vals=[d[key][k]['acc'] for k,_ in rows]
        colors=[BLUE if key=='bottom' and k=='real' else '#94A7B8' for k,_ in rows]
        ax.barh(yy,[v[0] for v in vals],height=.55,color=colors,zorder=2)
        ax.errorbar([v[0] for v in vals],yy,xerr=None,fmt='none',
                    ecolor='#34495A',capsize=2,lw=.85,zorder=3)
        # Labels sit in each row above the mark, freeing the left margin.
        for y,v,(_,label) in zip(yy,vals,rows):
            ax.text(.02,y+.37,label,va='bottom',fontsize=7.5)
            ax.text(v[0]+.025,y,f'{v[0]:.2f}',va='center',fontsize=7.5)
        ax.axvline(d['gold'][0],ls='--',color=TEAL,lw=1)
        ax.set(yticks=[],xlim=(0,1.08),ylim=(-.5,5.05),xlabel='Answer accuracy')
        ax.set_xticks([0,.25,.5,.75,1],['0','.25','.50','.75','1.0'])
        frame(ax,title);ax.spines['left'].set_visible(False)
        ax.grid(False);ax.grid(axis='x')
    fig.legend([plt.Line2D([],[],ls='--',color=TEAL)],['Correct skill in context (0.92)'],
               loc='outside lower center',fontsize=7)
    save(fig,'fig-channels-medcalc')

def depth():
    cells=data('depth-crossmodel-values.json')
    fig,axes=plt.subplots(2,3,figsize=(7.1,3.78),sharey=True,layout='constrained')
    for row,task in enumerate(['MedCalc','TheoremQA']):
        for col,model in enumerate(['Qwen3-8B','Qwen3-0.6B','Mistral-7B']):
            c=next(c for c in cells if c['task']==task and c['model']==model)
            ax=axes[row,col]; nl=c['n_layers']; x=np.arange(nl)
            tb,rb=c['transfer_boundary'],c['reading_boundary']
            frame(ax,model if row==0 else None)
            ax.axvspan(tb-.5,rb-.5,color='#F5BE7E',alpha=.26,lw=0,zorder=0)
            ax.axhline(.5,color='#A4AFBA',ls=(0,(2.5,2.5)),lw=.7,zorder=1)
            for l in [tb,rb]:ax.axvline(l-.5,color='#C7A582',lw=.6,ls=(0,(2,3)),zorder=1)
            ax.plot(x,c['transfer'],color=BLUE,lw=1.6,marker='o',ms=2.1,
                    markeredgecolor='white',markeredgewidth=.35,zorder=3,label=r'Skill transfer $\rho$')
            ax.plot(x,c['retention'],color=ORANGE,lw=1.6,marker='s',ms=1.9,
                    markeredgecolor='white',markeredgewidth=.3,zorder=3,label=r'Skill-attention knockout $q$')
            # Every point is measured; dotted overlays retain the common-ID check.
            ax.plot(x,c['common']['transfer'],color=BLUE,lw=.8,ls=(0,(1,2)),alpha=.8,zorder=4)
            ax.plot(x,c['common']['retention'],color=ORANGE,lw=.8,ls=(0,(1,2)),alpha=.8,zorder=4)
            ax.text((tb+rb-1)/2,1.03,f'L{tb}–L{rb}',ha='center',va='center',
                    fontsize=6.8,color='#94551D')
            ax.set(xlim=(0,nl-1),ylim=(-.035,1.105),
                   xticks=sorted(set([0,8,16,24,nl-1])),yticks=[0,.5,1])
            ax.set_yticklabels(['0','.5','1.0'])
            if col==0:ax.set_ylabel(task+'\nRecovery / retention',labelpad=6)
            if row==1:ax.set_xlabel('Intervention layer L',labelpad=4)
    handles,labels=axes[0,0].get_legend_handles_labels()
    handles.append(plt.Line2D([],[],color=GRAY,lw=1,ls=(0,(1,2))))
    labels.append('Common-item check')
    fig.legend(handles,labels,loc='outside upper center',ncol=3,fontsize=7,
               handlelength=2.4,columnspacing=1.8)
    save(fig,'fig-transfer-reading')


def rank():
    d=data('fig-rank-values.json');fig,axes=plt.subplots(1,3,figsize=(7.1,2.4),sharey=True,layout='constrained')
    for ax,(name,color,marker) in zip(axes,[('Qwen3-8B',BLUE,'o'),('Qwen3-0.6B',TEAL,'^'),('Mistral-7B',PURPLE,'D')]):
        c=d[name]
        for key,ls in [('top','-'),('bottom','--')]:
            pts=sorted((int(k),v) for k,v in c[key].items())
            x=[k for k,v in pts];values=[v for k,v in pts]
            ax.errorbar(x,[v[0] for v in values],yerr=None,
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
    d=data('posbudget.json');A=d['arms'];full=A['evfull']['rho'];median=d['span_width']['median']
    fig,axes=plt.subplots(2,2,figsize=(7.1,4.5),layout='constrained')
    a,b,c,e=axes.flat
    def series(ax,pts,color,marker,label,ls='-'):
        x=[x for x,v in pts];vs=[(v['rho'],*v['ci_cluster']) for x,v in pts]
        ax.errorbar(x,[v[0] for v in vs],yerr=None,color=color,marker=marker,
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
    names=[('wf','skill steps'),('wd','description'),('wr','random'),('we','example')]
    for off,budget,color,label in [(-.18,'256',BLUE,'256 positions'),(.18,'half',PURPLE,'Half span')]:
        vs=[A[k+budget] for k,_ in names];xx=np.arange(4)+off
        c.bar(xx,[v['rho'] for v in vs],width=.31,color=color,alpha=.88,label=label)
        c.errorbar(xx,[v['rho'] for v in vs],yerr=None,
                   fmt='none',ecolor='#34495A',capsize=2,lw=.7)
        for x,v in zip(xx,vs):c.text(x,v['rho']+.025,f'{v["rho"]:.2f}',ha='center',fontsize=6.5)
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
                                  '(c) Skill-step blocks recover more','(d) Displacement disrupts transfer']):
        ax.axhline(full,color=TEAL,ls='--',lw=.9,alpha=.6)
        ax.set(ylim=(-.04,1.07),yticks=[0,.25,.5,.75,1]);frame(ax,title)
    for ax in [a,c]:ax.set_ylabel(r'Recovery $\rho$')
    save(fig,'fig-posbudget-full')

def position_main():
    d=data('posbudget.json'); A=d['arms']; full=A['evfull']['rho']
    fig,(a,b)=plt.subplots(1,2,figsize=(7.1,2.35),layout='constrained')
    names=[('wf','Skill steps'),('wd','Description'),('wr','Random'),('we','Example')]
    for off,budget,color,label in [(-.18,'256',BLUE,'256 positions'),(.18,'half',TEAL,'Half span')]:
        vs=[A[k+budget] for k,_ in names];xx=np.arange(4)+off
        a.bar(xx,[v['rho'] for v in vs],width=.31,color=color,label=label,zorder=2)
        a.errorbar(xx,[v['rho'] for v in vs],yerr=None,
                   fmt='none',ecolor='#34495A',capsize=2,lw=.7)
        for x,v in zip(xx,vs):a.text(x,v['rho']+.025,f'{v["rho"]:.2f}',ha='center',fontsize=6.8)
    a.set_xticks(range(4),[n for _,n in names]);a.set_xlabel('Section at the centre of one block')
    a.legend(loc='upper right',fontsize=7)
    for key,color,marker,label in [('sh',ORANGE,'o','Cyclic shift'),('sn',PURPLE,'s','Later, no wrap'),('sb',BLUE,'D','Earlier, no wrap')]:
        grid=[1,4,16,64,256] if key=='sh' else [1,4,16]
        vs=[A[f'{key}{n}'] for n in grid]
        b.errorbar(grid,[v['rho'] for v in vs],yerr=None,
                   color=color,marker=marker,ms=3,lw=1.2,capsize=2,label=label)
    b.set_xscale('log',base=2);b.set_xticks([1,4,16,64,256],['1','4','16','64','256'])
    b.set_xlabel('Position displacement D');b.legend(loc='upper right',fontsize=7)
    for ax,title in [(a,'(a) Which skill content is transferred?'),(b,'(b) Where is that content written?')]:
        frame(ax,title);ax.set(ylim=(-.04,1.1),yticks=[0,.25,.5,.75,1])
        ax.axhline(full,color=TEAL,lw=.85,ls='--',alpha=.7)
    a.set_ylabel(r'Recovery $\rho$')
    save(fig,'fig-posbudget')

if __name__=='__main__':
    before={f:hashlib.sha256((VALUES/f).read_bytes()).hexdigest() for f in INPUTS}
    channels();depth()
    after={f:hashlib.sha256((VALUES/f).read_bytes()).hexdigest() for f in INPUTS}
    assert before==after
    (AUDIT/'FIGURE-STYLE-WEBSKILLS-20261017.json').write_text(json.dumps({'input_sha256':before,
        'numeric_records_unchanged':True,'figures': ['fig-channels-medcalc','fig-transfer-reading']},indent=2)+'\n')
    print('Rendered submission point-estimate figures; numerical records unchanged.')
