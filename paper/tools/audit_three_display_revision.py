#!/usr/bin/env python3
"""Check the revised displays against unchanged numerical inputs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

PAPER=Path(__file__).resolve().parents[1]
root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=PAPER,text=True).strip())
text=(PAPER/'sections/04-experiment.tex').read_text()
inputs=[p for p in (PAPER/'values').glob('*.json') if not p.name.startswith('DATA-')]
inputs += [PAPER/'figures'/name for name in
           ['fig-mechanism-repair.json','fig-mechanism-edges.json','fig-mechanism-results-values.json']]
hashes={}
for path in inputs:
    relative=path.relative_to(root).as_posix()
    original=subprocess.check_output(['git','show',f'HEAD:{relative}'],cwd=root)
    assert original==path.read_bytes(),f'Numerical input changed: {relative}'
    hashes[relative]=hashlib.sha256(original).hexdigest()

assert len(re.findall(r'\\begin\{figure\*?\}',text))==2
assert sum(len(re.findall(r'\\begin\{figure\*?\}',p.read_text()))
           for p in (PAPER/'sections').glob('*.tex'))==4
assert len(re.findall(r'\\begin\{table\*?\}',text))==3
assert '\\begin{teaserfigure}' not in (PAPER/'main.tex').read_text()
assert (PAPER/'sections/01-introduction.tex').read_text().count('Relevance to the Web and to this track.')==1

channels=json.loads((PAPER/'values/fig-channels-values.json').read_text())
gold=channels['gold'][0]
rows=[('Correct skill donor',gold,1),('Wrong skill receiver',0,0),
      ('Correct skill span',channels['bottom']['real']['acc'][0],None),
      ('Last prompt position',channels['top']['tq1']['acc'][0],None),
      ('Last $16$ prompt positions',channels['top']['tq16']['acc'][0],None),
      ('Other skill content',channels['bottom']['dcross']['acc'][0],None),
      ('Correct span, permuted',channels['bottom']['dshuf']['acc'][0],None),
      ('Norm-matched noise',channels['bottom']['drand']['acc'][0],None),
      ('Identity patch',0,0)]
for label,accuracy,recovery in rows:
    recovery=accuracy/gold if recovery is None else recovery
    a=f'{accuracy:.3f}'.lstrip('0');r=f'{recovery:.2f}'
    if recovery<1:r=r.lstrip('0')
    assert f'{label} & {a} & {r}' in text,label

depth=json.loads((PAPER/'values/depth-crossmodel-values.json').read_text())
table=(PAPER/'tables/tab-paired-depth.tex').read_text()
for cell in depth:
    common=cell['common'];t=common['transfer_boundary'];r=common['reading_boundary']
    assert f'{cell["task"]} & {cell["model"]} & ${common["n"]}$ & ${t}/{r}$' in table
    assert f'${r-t}$' in table
    lo,hi=common['boundary_ci'][2]
    assert 'CI' not in table and 'cellcolor' not in table
    for threshold,predicate in [(.4,True),(.6,True)]:
        # Evaluate the first crossings from the original measured curves.
        transfer=next(i for i,v in enumerate(common['transfer']) if v<threshold)
        retained=next(i for i,v in enumerate(common['retention']) if v>=threshold)
        assert transfer<retained,(cell['model'],cell['task'],threshold)

repair=json.loads((PAPER/'figures/fig-mechanism-repair.json').read_text())['samples']['rescued']
for key,label in [('SC_minus_S','L16: $SC-S$'),
                  ('interaction_SC_minus_S_minus_C_plus_receiver','L16: additive interaction'),
                  ('SC_minus_SC_recut','L16: $SC-(SC+\\mathrm{recut})$')]:
    contrast=repair['contrasts'][key]
    values=[contrast['estimate'][2],contrast['cluster_ci95'][0][2],contrast['cluster_ci95'][1][2]]
    expected=f'{label} & $+{100*values[0]:.1f}$'
    assert expected in text,expected
edges=json.loads((PAPER/'figures/fig-mechanism-edges.json').read_text())
values=[edges['reader_minus_self_loss'][2],edges['reader_minus_self_loss_ci95'][0][2],edges['reader_minus_self_loss_ci95'][1][2]]
assert f'L24: reader minus self loss & $+{100*values[0]:.1f}$' in text
# Table 3 and Figure 4 display point estimates, per the current user request.
for label in ('tab:mechanism-contrasts', 'fig:mechanism'):
    blocks=re.findall(r'\\begin\{(?:table|figure\*?)\}.*?\\end\{(?:table|figure\*?)\}',text,re.S)
    block=next(b for b in blocks if '\\label{'+label+'}' in b)
    assert not re.search(r'confidence|bootstrap|uncertainty|95\\%|\bCI\b',block,re.I)
# Verify the new teaser's sources and rendered positions.
import numpy as np
teaser=json.loads((PAPER/'audit/TEASER-CACHE-READING-20261017.json').read_text())
svg=ET.parse(PAPER/'figures/fig-teaser.svg').getroot()
ns={'s':'http://www.w3.org/2000/svg'}
for name,digest in teaser['input_sha256'].items():
    assert hashlib.sha256((PAPER/name).read_bytes()).hexdigest()==digest
assert (teaser['early_n'],teaser['depth_n'],teaser['repair_n'])==(135,134,114)
common=next(c['common'] for c in depth if c['task']=='MedCalc' and c['model']=='Qwen3-8B')
assert teaser['transfer']==common['transfer']
assert np.allclose(teaser['source_dependence'],1-np.array(common['retention']))
for label,expected in [('transfer',teaser['transfer']),('dependence',teaser['source_dependence'])]:
    group=svg.find(f'.//s:g[@id="teaser-{label}"]',ns)
    coords=np.array([float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',
                    group.find('s:path',ns).attrib['d'])]).reshape(-1,2)
    assert len(coords)==len(expected)
    slope,intercept=np.polyfit(expected,coords[:,1],1)
    assert slope<0 and np.max(np.abs(coords[:,1]-(slope*np.array(expected)+intercept)))<1e-4
raw_repair=json.loads((PAPER/'figures/fig-mechanism-repair.json').read_text())
expected=np.array(raw_repair['samples']['rescued']['accuracy'])[2:,2]*100
assert np.allclose(teaser['repair_accuracy_percent'],expected)
scales=[]
for i,value in enumerate(expected):
    group=svg.find(f'.//s:g[@id="teaser-repair-{i}"]',ns)
    coords=np.array([float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',
                    group.find('s:path',ns).attrib['d'])]).reshape(-1,2)
    scales.append(np.ptp(coords[:,0])/value)
assert max(scales)-min(scales)<1e-4

# Recount the already completed TheoremQA windows; no model inference.
import replication as rep
groups=rep.restricted(rep.load(['t8-win','tqa-span']))
rows=[r for group in groups.values() for r in group]
windows={}
for arm in ['w8_11','w12_15','w14_19','w16_35','L16']:
    assert sum(f'ok_real_{arm}' in r for r in rows)==99
    windows[arm]=rep.rho(groups,f'ok_real_{arm}')
assert len(groups)==75
assert windows['w16_35']==windows['L16']
appendix=(PAPER/'appendix/b-full-dataset-rerun.tex').read_text()
assert '$0.839$, $0.613$, $0.376$ and $0.204$' in appendix
assert 'equal at the reported precision under both restrictions' not in appendix
report={'numerical_inputs_unchanged':True,'input_sha256':hashes,
        'main_figures':4,'main_tables':3,'appendix_tables':1,
        'baseline_commit':'141c8fb','new_inference':False,
        'theoremqa_windows':windows,'theoremqa_n':99,'theoremqa_groups':75,
        'checked':'Three main tables including boundary intervals; teaser source values, curves and bar widths; corrected TheoremQA windows'}
(PAPER/'audit/FOUR-FIGURE-STORY-20261017.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: {len(inputs)} numerical inputs unchanged; revised displays and TheoremQA windows verified.')
