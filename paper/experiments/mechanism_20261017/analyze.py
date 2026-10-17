#!/usr/bin/env python3
"""Analyze complete fixed-ID repair data and preserve clustered uncertainty."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('inputs', nargs='+')
    p.add_argument('--ids', required=True)
    p.add_argument('--out-prefix', required=True)
    p.add_argument('--layers', default='8,12,16,24')
    args = p.parse_args()
    from load_completed import load_completed
    ids, rows, keyed, provenance = load_completed(args.inputs, args.ids, 'repair', args.layers)
    layers = [int(x) for x in args.layers.split(',')]
    arms = ['S','C','SC','SC_recut']
    expected = {(i,a,-1) for i in ids for a in ('no_skill','donor','receiver')}
    expected |= {(i,a,l) for i in ids for a in arms for l in layers}
    if set(keyed) != expected:
        raise ValueError(f'Incomplete or unexpected arms: missing={len(expected-set(keyed))}, extra={len(set(keyed)-expected)}')
    for r in rows:
        if r['n_generated'] != len(r['token_ids']):
            raise ValueError('Token count mismatch')
        if r['arm'] in ('S','SC','SC_recut') and r['instrumentation']['patch_calls'] != 1:
            raise ValueError('Residual patch missing')
        if r['arm'] in ('C','SC','SC_recut') and r['instrumentation']['cache_layers_replaced'] != r['layer']+1:
            raise ValueError('Cache repair missing')
        if r['arm'] == 'SC_recut' and not r['instrumentation']['mask_calls']:
            raise ValueError('Recut missing')
    valid = [i for i in ids if keyed[i,'donor',-1]['correct'] and not keyed[i,'receiver',-1]['correct']]
    rescued = [i for i in valid if not keyed[i,'no_skill',-1]['correct']]
    untruncated_baselines = [i for i in rescued if not any(
        keyed[i,arm,-1]['truncated'] for arm in ('no_skill','donor','receiver'))]
    samples = {'fixed':ids, 'donor_receiver_valid':valid, 'rescued':rescued,
               'rescued_baselines_untruncated':untruncated_baselines}
    report = dict(**provenance, layers=layers, arms=arms, primary='rescued', samples={},
                  fixed_baseline_truncation={arm:sum(keyed[i,arm,-1]['truncated'] for i in ids)
                                             for arm in ('no_skill','donor','receiver')})
    for label, selected in samples.items():
        if not selected:
            report['samples'][label] = {'n':0}
            continue
        groups = sorted({keyed[i,'donor',-1]['group'] for i in selected})
        group_index = {g:j for j,g in enumerate(groups)}
        # Cluster resampling preserves all items within each sampled skill.
        rng = np.random.default_rng(1017)
        draws = rng.multinomial(len(groups), np.ones(len(groups))/len(groups), size=10000)
        counts = np.zeros(len(groups))
        totals = np.zeros((len(groups),len(arms)+2,len(layers)))
        trunc = np.zeros((len(arms)+2,len(layers)),dtype=int)
        labels = ['receiver','donor']+arms
        for i in selected:
            g = group_index[keyed[i,'donor',-1]['group']]
            counts[g] += 1
            for a,arm in enumerate(labels):
                for j,l in enumerate(layers):
                    r = keyed[i,arm,-1 if arm in ('receiver','donor') else l]
                    totals[g,a,j] += int(r['correct'])
                    trunc[a,j] += int(r['truncated'])
        means = totals.sum(0)/len(selected)
        # Report censoring bounds without dropping post-intervention failures.
        lower = means.copy()
        for a,arm in enumerate(labels):
            for j,l in enumerate(layers):
                lower[a,j] = sum(bool(keyed[i,arm,-1 if arm in ('receiver','donor') else l]['correct'])
                                 and not keyed[i,arm,-1 if arm in ('receiver','donor') else l]['truncated']
                                 for i in selected)/len(selected)
        upper = lower + trunc/len(selected)
        boot = np.einsum('bg,gaj->baj',draws,totals)/(draws@counts)[:,None,None]
        contrasts = {'SC_minus_S':(means[4]-means[2],boot[:,4]-boot[:,2]),
                     'SC_minus_C':(means[4]-means[3],boot[:,4]-boot[:,3]),
                     'interaction_SC_minus_S_minus_C_plus_receiver':
                         (means[4]-means[2]-means[3]+means[0],boot[:,4]-boot[:,2]-boot[:,3]+boot[:,0]),
                     'SC_minus_SC_recut':(means[4]-means[5],boot[:,4]-boot[:,5])}
        report['samples'][label] = dict(n=len(selected),groups=groups,ids=selected,
            labels=labels,accuracy=means.tolist(),truncated=trunc.tolist(),
            truncation_accuracy_bounds=[lower.tolist(),upper.tolist()],
            SC_minus_S_truncation_bounds=[(lower[4]-upper[2]).tolist(),(upper[4]-lower[2]).tolist()],
            accuracy_cluster_ci95=np.quantile(boot,[.025,.975],axis=0).tolist(),
            contrasts={k:dict(estimate=v.tolist(),cluster_ci95=np.quantile(b,[.025,.975],axis=0).tolist())
                       for k,(v,b) in contrasts.items()})
    prefix = Path(args.out_prefix)
    prefix.parent.mkdir(parents=True,exist_ok=True)
    Path(str(prefix)+'.json').write_text(json.dumps(report,indent=2)+'\n')
    if not rescued:
        raise ValueError('No new-protocol rescued items; report saved, no primary figure')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    primary = report['samples']['rescued']
    matrix = np.array(primary['accuracy'])
    plt.rcParams.update({'font.size':9,'pdf.fonttype':42})
    fig,ax = plt.subplots(figsize=(6.4,3),layout='constrained')
    im = ax.imshow(matrix,vmin=0,vmax=1,cmap='Blues',aspect='auto',interpolation='nearest')
    ax.set_xticks(range(len(layers)),layers)
    ax.set_yticks(range(6),['Wrong-skill receiver','Correct-skill donor','S: source residual',
        'C: source cache','SC: residual + cache','SC + reader recut'])
    ax.set_xlabel('Intervention layer (measured points)')
    ax.set_title(f'Qwen3-8B / MedCalc; n={len(rescued)}, {len(primary["groups"])} skills',loc='left')
    for (r,c),v in np.ndenumerate(matrix):
        ax.text(c,r,f'{v:.2f}',ha='center',va='center',color='white' if v>.55 else '#17314b')
    fig.colorbar(im,ax=ax,label='Answer accuracy')
    for ext in ('pdf','png'):
        fig.savefig(str(prefix)+'.'+ext,dpi=220,bbox_inches='tight')
    print(json.dumps({k:v['n'] for k,v in report['samples'].items()}))


if __name__ == '__main__':
    main()
