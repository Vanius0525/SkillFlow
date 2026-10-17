#!/usr/bin/env python3
"""Independently recount formal raw outcomes and validate rendered mechanism cells."""
import hashlib
import json
from pathlib import Path
import pymupdf
import xml.etree.ElementTree as ET

PAPER=Path(__file__).resolve().parents[1]
EXP=PAPER/'experiments/mechanism_20261017'
FIG=PAPER/'figures'


def audit():
    checks=[]; hashes={}; raw={}; summaries={}
    def check(label,value):
        if not value:raise AssertionError(label)
        checks.append(label)
    ids=json.loads((EXP/'ids-repair124.json').read_text())['ids']
    source=hashlib.sha256((EXP/'run.py').read_bytes()).hexdigest()
    ids_hash=hashlib.sha256((EXP/'ids-repair124.json').read_bytes()).hexdigest()
    identity_count=0
    for suite,count in [('identity',25),('repair',589),('edges',372)]:
        keyed={}
        for shard in range(4):
            path=EXP/f'parallel/{suite}-s4-{shard}.jsonl'
            rows=[json.loads(x) for x in path.read_text().splitlines()]
            manifest=json.loads(path.with_suffix('.manifest.json').read_text())
            done=json.loads(path.with_suffix('.done.json').read_text())
            hashes[str(path.relative_to(PAPER))]=hashlib.sha256(path.read_bytes()).hexdigest()
            check(f'{suite}/{shard} count',len(rows)==done['records']==count)
            check(f'{suite}/{shard} source and IDs',manifest['script_sha256']==source and manifest['ids_sha256']==ids_hash)
            expected=ids[shard::4][:1] if suite=='identity' else ids[shard::4]
            check(f'{suite}/{shard} partition',set(r['instance_id'] for r in rows)==set(expected))
            check(f'{suite}/{shard} config',manifest['backend']=='eager' and manifest['max_new']==1536 and manifest['shard']==shard and manifest['shards']==4)
            for r in rows:
                key=(r['instance_id'],r['arm'],r['layer'])
                check(f'unique {suite}/{key}',key not in keyed)
                check(f'tokens {suite}/{key}',len(r['token_ids'])==r['n_generated'])
                keyed[key]=r
            if suite=='identity':
                for r in rows:
                    if r['arm'].startswith('identity_'):
                        baseline='receiver_full' if r['arm'].endswith('_full') else 'receiver'
                        check(f'own state {shard}/{r["arm"]}/{r["layer"]}',r['token_ids']==keyed[r['instance_id'],baseline,-1]['token_ids'])
                        identity_count+=1
        raw[suite]=keyed
    for i in ids:
        for arm in ['donor','receiver','no_skill']:
            check(f'identical baseline {i}/{arm}',raw['repair'][i,arm,-1]['token_ids']==raw['edges'][i,arm,-1]['token_ids'])
    selected=[i for i in ids if raw['repair'][i,'donor',-1]['correct'] and not raw['repair'][i,'receiver',-1]['correct'] and not raw['repair'][i,'no_skill',-1]['correct']]
    repair=json.loads((FIG/'fig-mechanism-repair.json').read_text())
    edges=json.loads((FIG/'fig-mechanism-edges.json').read_text())
    values=json.loads((FIG/'fig-mechanism-results-values.json').read_text())
    check('same primary samples',selected==repair['samples']['rescued']['ids'] and set(selected)==set(edges['rescued_ids']))
    for suite,layers,arms in [('repair',[8,12,16,24],['S','C','SC','SC_recut']),('edges',[8,16,24],['cut_reader_both','cut_self_both','cut_both_both'])]:
        matrix=[]; truncated=[];counts=[]
        for a,arm in enumerate(arms):
            vals=[];trunc=[];ncorrect=[]
            for j,layer in enumerate(layers):
                rows=[raw[suite][i,arm,layer] for i in selected]
                n=sum(bool(r['correct']) for r in rows);value=n/len(selected)
                vals.append(value);ncorrect.append(n);trunc.append(sum(bool(r['truncated']) for r in rows))
                target=repair['samples']['rescued']['accuracy'][a+2][j] if suite=='repair' else edges['retained_accuracy'][a][j]
                check(f'raw to summary {suite}/{arm}/{layer}',abs(value-target)<1e-12)
                target=values['repair_accuracy'][a][j] if suite=='repair' else 1-values['edge_loss'][a][j]
                check(f'raw to combined figure {suite}/{arm}/{layer}',abs(value-target)<1e-12)
            matrix.append(vals);truncated.append(trunc);counts.append(ncorrect)
        summaries[suite]=dict(arms=arms,layers=layers,n_correct=counts,accuracy=matrix,truncated=truncated)
    text=' '.join(p.get_text() for p in pymupdf.open(FIG/'fig-mechanism-results.pdf'))
    check('rendered measured panels','Source-state and cache repair' in text
          and 'Which attention path matters?' in text and 'PENDING' not in text)
    # Dot plots encode values by position, with one SVG marker per measured cell.
    # Recount all dots and verify their vertical coordinates against the raw
    # outcomes using the common linear axis transform across both panels.
    svg=ET.parse(FIG/'fig-mechanism-results.svg').getroot()
    ns={'s':'http://www.w3.org/2000/svg'}
    plotted=[]
    for suite,summary in summaries.items():
        for i,row in enumerate(summary['accuracy']):
            group=svg.find(f'.//s:g[@id="measured-{suite}-{i}"]',ns)
            check(f'rendered series {suite}/{i}',group is not None)
            markers=group.findall('.//s:use',ns)
            check(f'rendered count {suite}/{i}',len(markers)==len(row))
            for marker,value in zip(markers,row):
                plotted.append((value if suite=='repair' else 1-value,float(marker.attrib['y'])))
    import numpy as np
    actual=np.array(plotted)
    slope,intercept=np.polyfit(actual[:,0],actual[:,1],1)
    check('rendered values use correct vertical scale',slope<0 and
          np.max(np.abs(actual[:,1]-(slope*actual[:,0]+intercept)))<1e-4)
    for name,key in [('fig-mechanism-repair.json','repair_source_sha256'),('fig-mechanism-edges.json','edges_source_sha256')]:
        check('summary hash '+name,hashlib.sha256((FIG/name).read_bytes()).hexdigest()==values[key])
    check('all workers completed',all((EXP/f'parallel/worker-{j}.done.json').exists() for j in range(4)))
    check('pipeline completed',(EXP/'pipeline.done.json').exists())
    check('no failures',not list((EXP/'parallel').glob('*.failed.json')))
    report=dict(checks_passed=len(checks),source_sha256=hashes,identity_controls=identity_count,
                fixed_n=len(ids),primary_n=len(selected),groups=len({raw['repair'][i,'donor',-1]['group'] for i in selected}),
                identical_repair_edges_baselines=True,results=summaries)
    (EXP/'formal-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    r=audit();print(f'PASS: {r["checks_passed"]} mechanism checks; {r["identity_controls"]} exact identities; n={r["primary_n"]}')
