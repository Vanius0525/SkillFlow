#!/usr/bin/env python3
"""Audit six complete depth sweeps and repeat on their common eligible items.
No inference. Group bootstrap quantifies boundary uncertainty, not three
latent computational stages. Non-monotone recrossings are retained.
"""
import json
import hashlib
import numpy as np
import replication as rep
from _paths import VALUES, AUDIT


def knockout(tags):
    per = {}
    for tag in tags:
        for path in sorted(rep.BY.glob(f'*/{tag}.jsonl')):
            for line in path.read_text().splitlines():
                if not line.strip(): continue
                r = json.loads(line)
                d = per.setdefault(r['instance_id'], {'ko': {}})
                for key in ('calculator_id', 'ok_with', 'ok_without'):
                    if key in r:
                        if key in d: assert d[key] == r[key]
                        d[key] = r[key]
                for l, ok in zip(r['layers'], r['ok_block_from']):
                    if l in d['ko']: assert d['ko'][l] == ok
                    d['ko'][l] = bool(ok)
    return per


def boundary(curve, below):
    return next((l for l, v in enumerate(curve) if (v < .5 if below else v >= .5)), None)


def main():
    output=[]; hashes={}
    for task, model, nl, layer, bat, dep, rk, ko in rep.resolved_rows():
        groups=rep.restricted(rep.load(dep)); rows=[r for rs in groups.values() for r in rs]
        krows=knockout(ko)
        transfer=[rep.rho(groups, f'ok_real_L{l}') for l in range(nl)]
        retention, kn=rep.ko_curve(ko, groups=set(groups))
        assert all(v is not None for v in transfer) and set(retention)==set(range(nl))
        common=[r for r in rows if r['instance_id'] in krows and
                krows[r['instance_id']].get('ok_with') and not krows[r['instance_id']].get('ok_without')]
        assert common
        for r in common:
            assert r['calculator_id']==krows[r['instance_id']]['calculator_id']
        # Both curves use precisely these IDs; transfer keeps its own baselines.
        gids=sorted({r['calculator_id'] for r in common})
        counts=np.array([sum(r['calculator_id']==g for r in common) for g in gids])
        gold=np.array([sum(bool(r['ok_gold_in_context']) for r in common if r['calculator_id']==g) for g in gids])
        recv=np.array([sum(bool(r['ok_receiver']) for r in common if r['calculator_id']==g) for g in gids])
        t=np.array([[sum(bool(r[f'ok_real_L{l}']) for r in common if r['calculator_id']==g) for l in range(nl)] for g in gids])
        q=np.array([[sum(krows[r['instance_id']]['ko'][l] for r in common if r['calculator_id']==g) for l in range(nl)] for g in gids])
        tc=(t.sum(0)-recv.sum())/(gold.sum()-recv.sum()); qc=q.sum(0)/counts.sum()
        tb,rb=boundary(tc,True),boundary(qc,False)
        rng=np.random.default_rng(0); draws=[]
        for _ in range(2000):
            ix=rng.integers(0,len(gids),len(gids)); den=gold[ix].sum()-recv[ix].sum()
            if den<=0: continue
            bt=boundary((t[ix].sum(0)-recv[ix].sum())/den,True)
            br=boundary(q[ix].sum(0)/counts[ix].sum(),False)
            if bt is not None and br is not None: draws.append((bt,br,br-bt))
        ci=np.quantile(draws,[.025,.975],axis=0).T.tolist()
        c=dict(task=task,model=model,n_layers=nl,n_transfer=len(rows),n_reading=kn,
               transfer=transfer,retention=[retention[l] for l in range(nl)],
               transfer_boundary=boundary(transfer,True),reading_boundary=boundary([retention[l] for l in range(nl)],False),
               common=dict(n=len(common),groups=len(gids),ids=sorted(r['instance_id'] for r in common),
                   transfer=tc.tolist(),retention=qc.tolist(),transfer_boundary=tb,reading_boundary=rb,
                   boundary_ci=ci,threshold_sensitivity={str(th): [next((l for l,v in enumerate(tc) if v<th),None), next((l for l,v in enumerate(qc) if v>=th),None)] for th in [.4,.5,.6]},bootstrap_draws=len(draws),bootstrap_order_fraction=sum(x[2]>0 for x in draws)/len(draws),
                   intermediate_layers=[l for l in range(nl) if tc[l]<.5 and qc[l]<.5],
                   reading_recrossings=[l for l in range(rb+1,nl) if qc[l]<.5]),
               sources=dict(depth=dep,knockout=ko))
        output.append(c)
        for tag in dep+ko:
            for p in sorted(rep.BY.glob(f'*/{tag}.jsonl')): hashes[str(p.relative_to(rep.ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        print(task,model,'original',c['transfer_boundary'],c['reading_boundary'],'common',len(common),tb,rb,'gap CI',ci[2], 'order',c['common']['bootstrap_order_fraction'])
    (VALUES/'depth-crossmodel-values.json').write_text(json.dumps(output,indent=2)+'\n')
    (AUDIT/'DEPTH-CROSSMODEL-20261015.json').write_text(json.dumps(dict(source_sha256=hashes,bootstrap=dict(unit='skill group',draws=2000,seed=0),inference_run=False),indent=2)+'\n')

if __name__=='__main__': main()
