#!/usr/bin/env python3
"""Independently compare main-text displays with the selected local records.

Run after main_evidence.py, replication.py and fig_{channels,rank}_full.py.
The archived audit.py also checks the historical synthetic/geometry results.
This checker additionally protects against stale rendered assets, partial
curves, mismatched receivers and unpaired recovery denominators.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import random
import re
import sys

import pymupdf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BY = ROOT / 'howskill/results/p8-wb/fetched/by-host'
sources, checks = {}, []


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def read(path):
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load(tags):
    merged = {}
    for tag in tags:
        paths = sorted(BY.glob(f'*/{tag}.jsonl'))
        check(f'source exists: {tag}', bool(paths))
        for path in paths:
            for row in read(path):
                target = merged.setdefault(row['instance_id'], {})
                for key in row.keys() & target.keys():
                    if key.startswith('ok_') or key in ('calculator_id','filler','format','model'):
                        check(f'compatible {tag}/{row["instance_id"]}/{key}', row[key] == target[key])
                target.update(row)
    return list(merged.values())


def screen(rows):
    check('all receiver baselines present', all('ok_receiver' in r and 'ok_gold_in_context' in r for r in rows))
    failed = {r['calculator_id'] for r in rows if r['ok_receiver']}
    return [r for r in rows if r['calculator_id'] not in failed]


def mean(rows, key):
    return sum(bool(r[key]) for r in rows) / len(rows)


def rho(rows, key):
    selected = [r for r in rows if key in r]
    return ((mean(selected,key) - mean(selected,'ok_receiver')) /
            (mean(selected,'ok_gold_in_context') - mean(selected,'ok_receiver')))


def close(label, value, expected):
    check(label, math.isclose(value, expected, abs_tol=1e-12))


def data(name):
    return json.loads((HERE/name).read_text())


def table_row(name, prefix):
    lines = [line for line in (HERE/name).read_text().splitlines() if line.startswith(prefix)]
    check(f'{name}: unique row {prefix}', len(lines) == 1)
    return lines[0]


def prose(needle):
    check('main text: '+needle, needle in main)


main = re.sub(r'\s+', ' ', (HERE/'skillvector.tex').read_text().split(r'\label{endmain}')[0])
battery = data('battery-values.json')
base = screen(load(battery['sources']))
check('battery 135 items / 14 groups', len(base)==135 and len({r['calculator_id'] for r in base})==14)
table = (HERE/'tab-big40.tex').read_text()
for arm, values in battery['arms'].items():
    key = 'ok_'+arm
    rows = [r for r in base if key in r]
    check(f'battery {arm}: n',len(rows)==values['n'])
    close(f'battery {arm}: accuracy',mean(rows,key),values['accuracy'])
    close(f'battery {arm}: paired recovery',rho(base,key),values['rho'])
    lo, hi = values['ci']
    tail = f'& ${len(rows)}$ & ${values["accuracy"]:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & ${values["rho"]:+.2f}$'
    check(f'battery {arm}: TeX values',tail in table)
check('same-family row not normalised by 135-item baseline', battery['arms']['dnear_L8']['n']==41 and round(battery['arms']['dnear_L8']['rho'],2)==.12)

channels = data('fig-channels-values.json')
rows = screen(load(channels['sources']))
close('Figure 1 donor baseline',mean(rows,'ok_gold_in_context'),channels['gold'][0])
for panel in ['top','bottom']:
    for arm, values in channels[panel].items():
        key=f'ok_{arm}_L8'
        check(f'Figure 1 {arm}: paired complete sample',all(key in r for r in rows) and values['n']==len(rows)==135)
        close(f'Figure 1 {arm}: accuracy',mean(rows,key),values['acc'][0])
        if panel=='bottom':
            close(f'Figure 1/table 2 {arm}: accuracy',values['acc'][0],battery['arms'][arm+'_L8']['accuracy'])
            check(f'Figure 1/table 2 {arm}: identical intervals',values['acc'][1:]==battery['arms'][arm+'_L8']['ci'])

replication = data('replication-values.json')
rank = data('fig-rank-values.json')
for cell in replication:
    name=f'{cell["task"]}/{cell["model"]}'
    layer={'Qwen3-8B':8,'Qwen3-0.6B':6,'Mistral-7B':4}[cell['model']]
    rows=screen(load(cell['sources']['battery']))
    check(name+': battery sample',len(rows)==cell['n'] and len({r['calculator_id'] for r in rows})==cell['g'])
    close(name+': battery recovery',rho(rows,f'ok_real_L{layer}'),cell['rho'])
    for arm, v in cell['controls'].items():
        close(name+': control '+arm,rho(rows,f'ok_{arm}_L{layer}'),v['rho'])
    if cell['controls']:
        close(name+': includes largest control',max(v['rho'] for v in cell['controls'].values()),cell['ctrl'])
    line=table_row('tab-replication.tex',cell['task']+' & '+cell['model']+' &')
    check(name+': table recovery',f'${cell["rho"]:.2f}$ $[{cell["lo"]:.2f},{cell["hi"]:.2f}]$' in line)
    check(name+': table sample',f'${cell["n"]}$ (${cell["g"]}$)' in line)
    if cell['task']=='MedCalc':
        curve=rank[cell['model']]
        check(name+': figure/table rank sources',curve['tags']==cell['sources']['rank'])
        rr=screen(load(curve['tags']))
        check(name+': rank sample',len(rr)==curve['n']==cell['rank_n'])
        close(name+': untruncated rank baseline',rho(rr,f'ok_real_L{layer}'),curve['full'])
        close(name+': rank knee',curve['kstar'],cell['kstar'])
        for which in ['top','bottom']:
            for k,v in curve[which].items():
                key=f'ok_rank{k}{"lo" if which=="bottom" else ""}_L{layer}'
                check(name+': complete rank '+key,all(key in r for r in rr))
                close(name+': rank value '+key,rho(rr,key),v[0])

depth=data('main-evidence-values.json')
dr=screen(load(replication[0]['sources']['depth']))
for layer,value in depth['sufficiency']:
    close(f'Figure 3 span layer {layer}',rho(dr,f'ok_real_L{layer}'),value)
ko=[r for r in load(['full-ko']) if r['ok_with'] and not r['ok_without']]
check('Figure 3 knockout n',len(ko)==466)
for layer,value in depth['necessity']:
    close(f'Figure 3 knockout layer {layer}',sum(r['ok_block_from'][r['layers'].index(layer)] for r in ko)/len(ko),value)
wr=screen(load(depth['window_sources']))
check('Figure 3 windows on the battery receiver and items',len(wr)==depth['window_n']==135)
for window,value in depth['windows'].items():
    close(f'Figure 3 window {window}',rho(wr,f'ok_real_{window}'),value)

quarters=screen(load(['full-battery-a','full-quarters']))
last=screen(load(['full-dl-a','full-dl-b']))
for label,arm in [('Prose description','q0'),('Formulas','q1'),('Tool signatures','q2'),('Worked example','q3'),('Full span','real')]:
    line=table_row('tab-skill-content.tex',label+' &')
    check('Table 3 '+arm, f'${rho(quarters,f"ok_{arm}_L8"):.2f}$' in line)
for label,arm in [('This instance','real'),('Other instances of the same skill','dother'),('Instance-specific remainder','dperp')]:
    line=table_row('tab-skill-content.tex',label+' &')
    check('Table 3 '+arm, f'${rho(last,f"ok_{arm}_L8"):.2f}$ & ${rho(last,f"ok_{arm}_L16"):.2f}$' in line)

afv=data('answer-format-values.json')
if 'identity' in afv:
    check('Table 1 identity exact', afv['identity'][0]==afv['identity'][1] > 0)
for name, v in afv['formats'].items():
    curves=[]
    srcs=v['sources'] if 'sources' in v else [v['source']]
    paths=sorted(p for s in srcs for p in Path(s).glob('layer_*.jsonl'))
    if 'sources' in v:
        check('Table 1 '+name+': 36 layers', len(paths)==36)
    for path in paths:
        rr=read(path); rescued=[r for r in rr if r['cell']=='R']
        key='gok_replace_real' if 'gok_replace_real' in rescued[0] else 'ok_replace_real'
        curves.append(mean(rescued,key))
        check('Table 1 '+name+': sample',len(rr)==v['n'] and len(rescued)==v['rescued'])
    close('Table 1 '+name+': best recovery',max(curves),v['best'])
    check('Table 1 '+name+': TeX',f'& {v["n"]} & {v["rescued"]} & ${v["best"]:.3f}$' in table_row('tab-answer-format.tex',name+' &'))

beh=data('behaviour-values.json')
behavior_rows={key:{r['instance_id']:r for r in read(ROOT/f'howskill/results/p8-step/p8-{key}.jsonl')}
               for key in beh['accuracy']}
for key,rows in behavior_rows.items():
    check('behaviour paired sample '+key,set(rows)==set(behavior_rows['no_skill']) and len(rows)==1100)
    close('behaviour accuracy '+key,mean(list(rows.values()),'correct'),beh['accuracy'][key])
    prose(f'${100*beh["accuracy"][key]:.1f}\\%$')
deltas=collections.defaultdict(list)
for iid,row in behavior_rows['no_skill'].items():
    deltas[row['calculator_id']].append(int(behavior_rows['ctrl_neutral_no_tool'][iid]['correct'])-int(row['correct']))
means=[sum(v)/len(v) for v in deltas.values()]
rng=random.Random(0)
draws=sorted(sum(rng.choices(means,k=len(means)))/len(means) for _ in range(10000))
ci=[draws[250]*100,draws[9750]*100]
check('paired behavioural group bootstrap',ci==beh['wrong_minus_none_ci_pp'])
prose(f'$[{ci[0]:.1f},{ci[1]:+.1f}]$')

for needle in ['accuracy from $0.000$ to $0.815$', '$0.03$, $0.06$ and $0.05$',
               'same-family mean control recovers $0.12$ on its $41$ eligible items',
               '$0.89$, $0.74$, $0.16$ and $0.06$',
               'recovers $0.98$ [$0.91,1.03$]', 'largest control is $0.35$',
               'recovery on the same items is $0.71$', '$k^{*}=72$ [$46,94$] on MedCalc',
               '$0.00,0.12,0.79,0.67$, giving $k^{*}=43$ [$39,52$]',
               '$0.235$ for state replacement', '$365$--$1{,}630$ positions',
               'recovers only $0.03$ with the skill first ($n=135$) and $0.04$',
               'preserves $0.87$ recovery, compared with $0.89$']:
    prose(needle)
for needle in ['item-bootstrap','n=137','at or below $0.27$','within $0.10$ accuracy',
               '$0.304$','$415$--$1{,}630$','development comparison','$k^{*}=84$','(pre-fix)']:
    check('no stale main claim: '+needle,needle not in main)

for filename, labels in [('fig-channels-medcalc.pdf',['135','0.81','0.03','0.06']),
                         ('fig-rank-medcalc.pdf',['Mistral','72','135','362','256']),
                         ('fig-transfer-reading.pdf',['135','0.74','0.98'])]:
    pdf=pymupdf.open(HERE/filename)
    text=' '.join(page.get_text() for page in pdf)
    for label in labels:check(filename+': rendered '+label,label in text)

# Guard the reporting fixes with the two actual problematic cases.
import replication as rep
try:
    rep.load(['full-window','full-battery-a'])
except ValueError:
    check('incompatible receivers now rejected',True)
else:
    check('incompatible receivers now rejected',False)
for tags in [('q06-bat-a','q06-bat-b'),('mis-rank-a','mis-rank-b','mis-rank-lo')]:
    check('full rerun complete and used: '+','.join(tags),rep.complete(tags))

manifest={'checks_passed':len(checks),'source_sha256':sources,
          'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [HERE/'skillvector.tex', *[HERE/x for x in
                  ['tab-answer-format.tex','tab-big40.tex','tab-skill-content.tex','tab-replication.tex',
                   'fig-channels-medcalc.pdf','fig-rank-medcalc.pdf','fig-transfer-reading.pdf']]]},
          'selection_policy':'latest complete local measurement family; no partial curves or incompatible baseline merges',
          'scope':'main displays and updated prose; historical diagnostics additionally checked by whitebox/analysis/audit.py'}
(HERE/'DATA-CONSISTENCY-20260918.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'PASS: {len(checks)} checks; {len(sources)} source files hashed.')
