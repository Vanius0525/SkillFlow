#!/usr/bin/env python3
"""Render observed interventions only; fixed complete-case comparisons.

No interpolation, no unmeasured zeros, no outcome-based row sorting.
Incomplete development runs are visibly labelled, never submission figures.
"""
import argparse
import collections
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


def main():
    p = argparse.ArgumentParser()
    p.add_argument('inputs', nargs='+')
    p.add_argument('--out-prefix', required=True)
    p.add_argument('--ids', required=True)
    p.add_argument('--suite', choices=['repair','edges'], required=True)
    p.add_argument('--layers', default='8,12,16,24,28')
    p.add_argument('--with-reader', action='store_true')
    p.add_argument('--allow-incomplete', action='store_true')
    a = p.parse_args()
    records = {}
    for path in a.inputs:
        for line in Path(path).read_text().splitlines():
            r = json.loads(line)
            key = (r['instance_id'], r['arm'], r['layer'])
            if key in records:
                raise ValueError(f'Duplicate record {key}')
            records[key] = r
    ids = json.loads(Path(a.ids).read_text())['ids']
    layers = [int(x) for x in a.layers.split(',')]
    arms = (['S','C','SC'] + (['R','SR'] if a.with_reader else []) + ['SC_recut']
            if a.suite == 'repair' else
            [f'cut_{e}_{p}' for p in ['both','prefill','decode']
             for e in ['reader','self','both'] if not(e=='self' and p=='decode')])
    complete = [i for i in ids if all((i,arm,l) in records for arm in arms for l in layers)
                and (i,'donor',-1) in records and (i,'receiver',-1) in records]
    if len(complete) != len(ids) and not a.allow_incomplete:
        raise ValueError(f'Incomplete run: {len(complete)}/{len(ids)}; use explicit development override')
    if not complete:
        raise ValueError('No items have all declared arms and layers')
    # New eager/split baselines may differ from historical eligibility. Publish
    # both denominators, select using baselines only, and never hide this loss.
    eligible = [i for i in complete if records[i,'donor',-1]['correct']
                and not records[i,'receiver',-1]['correct']]
    if not eligible:
        raise ValueError('No new-protocol baseline-valid items')
    display_arms = ['receiver'] + arms if a.suite == 'repair' else arms
    matrix, all_matrix, counts, truncation = [], [], [], []
    for arm in display_arms:
        vals, allvals, ns, trunc = [], [], [], []
        for l in layers:
            keyl = -1 if arm=='receiver' else l
            rows=[records[i,arm,keyl] for i in eligible]
            allrows=[records[i,arm,keyl] for i in complete]
            score=lambda rows: sum(r['correct'] for r in rows)/len(rows)
            vals.append(score(rows) if a.suite=='repair' else 1-score(rows))
            allvals.append(score(allrows))
            ns.append(len(rows));trunc.append(sum(r['truncated'] for r in rows))
        matrix.append(vals);all_matrix.append(allvals);counts.append(ns);truncation.append(trunc)
    cmap=LinearSegmentedColormap.from_list('repair',['#F4F7FB','#B6D4E9','#316A9B','#12334E'])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(7.1,max(2.7,.32*len(display_arms)+1.2)),layout='constrained')
    im=ax.imshow(matrix,cmap=cmap,vmin=0,vmax=1,aspect='auto',interpolation='nearest')
    ax.set_xticks(range(len(layers)),layers)
    ax.set_yticks(range(len(display_arms)),[x.replace('_',' ') for x in display_arms])
    ax.set_xlabel('Intervention layer (measured points only)')
    for row in range(len(matrix)):
        for col,value in enumerate(matrix[row]):
            ax.text(col,row,f'{value:.2f}',ha='center',va='center',fontsize=8,
                    color='white' if value>.6 else '#183044')
    incomplete=len(complete)!=len(ids)
    ax.set_title(('DEVELOPMENT — incomplete run\n' if incomplete else '')+
                 f'Qwen3-8B / MedCalc; baseline-valid n={len(eligible)} of {len(complete)} complete',loc='left',fontsize=9)
    fig.colorbar(im,ax=ax,label='Answer accuracy' if a.suite=='repair' else 'Accuracy loss from correct donor',shrink=.85)
    prefix=Path(a.out_prefix);prefix.parent.mkdir(parents=True,exist_ok=True)
    for ext in ['pdf','png']:fig.savefig(str(prefix)+'.'+ext,dpi=220,bbox_inches='tight')
    plt.close(fig)
    payload=dict(expected_n=len(ids),complete_n=len(complete),eligible_n=len(eligible),
        eligible_ids=eligible,complete_ids=complete,layers=layers,arms=display_arms,
        values=matrix,unfiltered_accuracy=all_matrix,n=counts,truncated=truncation,
        development_only=incomplete,
        groups=sorted(set(records[i,'donor',-1]['group'] for i in eligible)))
    Path(str(prefix)+'.json').write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps({k:payload[k] for k in ['expected_n','complete_n','eligible_n','development_only']}))


if __name__=='__main__':main()
