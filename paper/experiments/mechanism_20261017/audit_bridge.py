#!/usr/bin/env python3
"""Audit observed bridge records; explicitly label incomplete data."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import statistics


def audit(path):
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    keyed = {(r['instance_id'],r['arm'],r['layer']):r for r in rows}
    if len(rows) != len(keyed):
        raise ValueError('Duplicate keys')
    complete = path.with_suffix('.done.json').exists()
    if complete:
        done = json.loads(path.with_suffix('.done.json').read_text())
        manifest = json.loads(path.with_suffix('.manifest.json').read_text())
        if done['records'] != len(rows):
            raise ValueError('Done marker record count mismatch')
        layers = [int(x) for x in manifest['layers'].split(',')]
        selected = sorted({r['instance_id'] for r in rows})
        if done['items'] != len(selected):
            raise ValueError('Done marker item count mismatch')
        expected = {(i,a,-1) for i in selected for a in
                    ('no_skill','donor','receiver','donor_full','receiver_full')}
        expected |= {(i,a,l) for i in selected for l in layers for a in
                     ('identity_S_full','S_full','identity_S_split','S_split','identity_SC')}
        if set(keyed) != expected:
            raise ValueError('Incomplete bridge arm/layer coverage')
    identities = []
    for r in rows:
        if len(r['token_ids']) != r['n_generated']:
            raise ValueError('Token count mismatch')
        if r['arm'].startswith('identity_'):
            name = 'receiver_full' if r['arm'].endswith('_full') else 'receiver'
            same = r['token_ids'] == keyed[r['instance_id'],name,-1]['token_ids']
            identities.append(dict(instance_id=r['instance_id'],arm=r['arm'],layer=r['layer'],exact=same))
            if not same:
                raise ValueError(f'Identity failed: {r["instance_id"]} {r["arm"]}')
    drift = []
    for iid in sorted({r['instance_id'] for r in rows}):
        for arm in ('donor','receiver'):
            if (iid,arm,-1) not in keyed or (iid,arm+'_full',-1) not in keyed:
                continue
            a,b = keyed[iid,arm,-1],keyed[iid,arm+'_full',-1]
            drift.append(dict(instance_id=iid,arm=arm,tokens_equal=a['token_ids']==b['token_ids'],
                              split_correct=a['correct'],full_correct=b['correct'],
                              correctness_flip=a['correct']!=b['correct']))
    seconds = [r['seconds'] for r in rows]
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                done_marker=path.with_suffix('.done.json').exists(),records=len(rows),
                items=len({r['instance_id'] for r in rows}),identities=identities,
                protocol_drift=drift,mean_seconds=statistics.mean(seconds) if seconds else None,
                truncated=sum(bool(r['truncated']) for r in rows),
                outcomes=[{k:r[k] for k in ('instance_id','arm','layer','correct','truncated')} for r in rows])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('inputs',nargs='+')
    p.add_argument('--out',required=True)
    a=p.parse_args()
    reports=[audit(Path(x)) for x in a.inputs]
    Path(a.out).write_text(json.dumps(reports,indent=2)+'\n')
    for r in reports:
        print(json.dumps({k:r[k] for k in ('path','done_marker','records','items','mean_seconds','truncated')}))


if __name__=='__main__':main()
