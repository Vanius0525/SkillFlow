#!/usr/bin/env python3
"""Complete fixed-ID reader/source-self/both attention-path comparison."""
import argparse
import json
from pathlib import Path
import numpy as np
from load_completed import load_completed


def main():
    p=argparse.ArgumentParser()
    p.add_argument('inputs',nargs='+')
    p.add_argument('--ids',required=True)
    p.add_argument('--out-prefix',required=True)
    p.add_argument('--layers',default='8,16,24')
    a=p.parse_args()
    ids,rows,keyed,provenance=load_completed(a.inputs,a.ids,'edges',a.layers)
    layers=[int(x) for x in a.layers.split(',')]
    arms=['cut_reader_both','cut_self_both','cut_both_both']
    expected={(i,arm,-1) for i in ids for arm in ('no_skill','donor','receiver')}
    expected|={(i,arm,l) for i in ids for arm in arms for l in layers}
    if set(keyed)!=expected:raise ValueError('Incomplete edge/phase/layer coverage')
    for r in rows:
        if len(r['token_ids'])!=r['n_generated']:raise ValueError('Token count mismatch')
        if r['arm'] in arms and not r['instrumentation']['mask_calls']:
            raise ValueError('Cut not applied')
    valid=[i for i in ids if keyed[i,'donor',-1]['correct'] and not keyed[i,'receiver',-1]['correct']]
    rescued=[i for i in valid if not keyed[i,'no_skill',-1]['correct']]
    if not rescued:raise ValueError('No fresh-protocol rescued items')
    groups=sorted({keyed[i,'donor',-1]['group'] for i in rescued})
    gindex={g:j for j,g in enumerate(groups)}
    counts=np.zeros(len(groups));totals=np.zeros((len(groups),len(arms),len(layers)))
    truncated=np.zeros((len(arms),len(layers)),dtype=int)
    truncated_correct=np.zeros_like(truncated)
    for i in rescued:
        g=gindex[keyed[i,'donor',-1]['group']];counts[g]+=1
        for j,arm in enumerate(arms):
            for k,l in enumerate(layers):
                row=keyed[i,arm,l]
                totals[g,j,k]+=int(row['correct'])
                truncated[j,k]+=int(row['truncated'])
                truncated_correct[j,k]+=int(row['truncated'] and row['correct'])
    accuracy=totals.sum(0)/len(rescued)
    rng=np.random.default_rng(1017)
    draws=rng.multinomial(len(groups),np.ones(len(groups))/len(groups),size=10000)
    boot=np.einsum('bg,gaj->baj',draws,totals)/(draws@counts)[:,None,None]
    lower=accuracy-truncated_correct/len(rescued);upper=lower+truncated/len(rescued)
    report=dict(**provenance,expected_n=len(ids),valid_n=len(valid),rescued_n=len(rescued),
                baseline_truncation={arm:sum(keyed[i,arm,-1]['truncated'] for i in ids)
                                     for arm in ('no_skill','donor','receiver')},
                rescued_baselines_untruncated=[i for i in rescued if not any(keyed[i,arm,-1]['truncated']
                    for arm in ('no_skill','donor','receiver'))],
                rescued_ids=rescued,groups=groups,layers=layers,arms=arms,
                retained_accuracy=accuracy.tolist(),loss=(1-accuracy).tolist(),
                retained_cluster_ci95=np.quantile(boot,[.025,.975],axis=0).tolist(),
                truncated=truncated.tolist(),truncation_accuracy_bounds=[lower.tolist(),upper.tolist()],
                reader_minus_self_loss=(accuracy[1]-accuracy[0]).tolist(),
                reader_minus_self_loss_ci95=np.quantile(boot[:,1]-boot[:,0],[.025,.975],axis=0).tolist())
    prefix=Path(a.out_prefix);prefix.parent.mkdir(parents=True,exist_ok=True)
    Path(str(prefix)+'.json').write_text(json.dumps(report,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(5.5,2.3),layout='constrained')
    matrix=1-accuracy
    im=ax.imshow(matrix,vmin=0,vmax=1,cmap='Oranges',aspect='auto',interpolation='nearest')
    ax.set_xticks(range(len(layers)),layers)
    ax.set_yticks(range(3),['Block reader → source','Block source → source','Block both paths'])
    ax.set_xlabel('Cut from layer onward')
    ax.set_title(f'Qwen3-8B / MedCalc; n={len(rescued)}, {len(groups)} skills',loc='left')
    for (r,c),v in np.ndenumerate(matrix):
        ax.text(c,r,f'{v:.2f}',ha='center',va='center',color='white' if v>.65 else '#4b3321')
    fig.colorbar(im,ax=ax,label='Accuracy lost from correct donor')
    for ext in ('pdf','png'):fig.savefig(str(prefix)+'.'+ext,dpi=220,bbox_inches='tight')
    print(json.dumps(dict(expected=len(ids),valid=len(valid),rescued=len(rescued),groups=len(groups))))


if __name__=='__main__':main()
