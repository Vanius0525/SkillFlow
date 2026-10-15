#!/usr/bin/env python3
"""Existing-result heatmap: same-item transfer failure AND knockout failure.
Rows are skill groups sorted by ID, never by outcomes. Only baseline-valid
items in both protocols enter. This is a descriptive, not mechanistic, check.
"""
import collections
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import replication as rep
from depth_crossmodel import knockout
from _paths import VALUES, FIGURES


def main():
    cells=[]
    for task,model,nl,layer,bat,dep,rk,ko in rep.resolved_rows():
        rows=[r for rs in rep.restricted(rep.load(dep)).values() for r in rs]
        kr=knockout(ko)
        rows=[r for r in rows if r['ok_gold_in_context'] and not r['ok_receiver'] and
              r['instance_id'] in kr and kr[r['instance_id']].get('ok_with') and
              not kr[r['instance_id']].get('ok_without')]
        groups=collections.defaultdict(list)
        for r in rows:groups[r['calculator_id']].append(r)
        ids=sorted(groups)
        joint=[[sum(not r[f'ok_real_L{l}'] and not kr[r['instance_id']]['ko'][l]
                    for r in groups[g])/len(groups[g]) for l in range(nl)] for g in ids]
        c=dict(task=task,model=model,n_layers=nl,n=len(rows),groups=ids,
               group_n=[len(groups[g]) for g in ids],joint_failure=joint,
               ids=sorted(r['instance_id'] for r in rows),
               none_baseline_disagreements=sum(bool(r['ok_none']) for r in rows))
        cells.append(c)
        print(task,model,'n',c['n'],'groups',len(ids),'none disagreements',c['none_baseline_disagreements'])
    cmap=LinearSegmentedColormap.from_list('source_dependence',['#F5F8FC','#F5D0A7','#CB6B2C'])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,3,figsize=(7.1,3.45),layout='constrained')
    for i,task in enumerate(['MedCalc','TheoremQA']):
        for j,model in enumerate(['Qwen3-8B','Qwen3-0.6B','Mistral-7B']):
            c=next(c for c in cells if c['task']==task and c['model']==model);ax=axes[i,j];nl=c['n_layers']
            im=ax.imshow(c['joint_failure'],cmap=cmap,vmin=0,vmax=1,aspect='auto',interpolation='nearest',extent=(-.5,nl-.5,len(c['groups'])-.5,-.5))
            ax.set_xticks(sorted(set([0,8,16,24,nl-1])));ax.set_yticks([])
            ax.spines[['top','right','left']].set_visible(False);ax.spines['bottom'].set_color('#AAB4BE')
            ax.tick_params(labelsize=7,length=2)
            if i==0:ax.set_title(model,loc='left',fontsize=9,fontweight='bold')
            if i==1:ax.set_xlabel('Intervention layer L',fontsize=8)
            if j==0:ax.set_ylabel(task+'\nSkill groups (ID order)',fontsize=8)
    fig.colorbar(im,ax=axes.ravel().tolist(),fraction=.025,pad=.025,label='Same-item joint failure fraction',ticks=[0,.5,1])
    for ext in ['pdf','png']:fig.savefig(FIGURES/('fig-joint-failure.'+ext),bbox_inches='tight',dpi=220)
    plt.close(fig)
    (VALUES/'joint-failure-values.json').write_text(json.dumps(cells,indent=2)+'\n')

if __name__=='__main__':main()
