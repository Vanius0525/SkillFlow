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

assert len(re.findall(r'\\begin\{figure\*?\}',text))==3
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
    expected=f'{label} & $+{100*values[0]:.1f}$ & $[{100*values[1]:.1f},{100*values[2]:.1f}]$'
    assert expected in text,expected
edges=json.loads((PAPER/'figures/fig-mechanism-edges.json').read_text())
values=[edges['reader_minus_self_loss'][2],edges['reader_minus_self_loss_ci95'][0][2],edges['reader_minus_self_loss_ci95'][1][2]]
assert f'L24: reader minus self loss & $+{100*values[0]:.1f}$ & $[{100*values[1]:.1f},{100*values[2]:.1f}]$' in text
window_source=PAPER/'values/main-evidence-values.json'
window_data=json.loads(window_source.read_text())
window_report=json.loads((PAPER/'audit/REPEATED-REPLACEMENT-20261017.json').read_text())
assert window_report['source_sha256']==hashlib.sha256(window_source.read_bytes()).hexdigest()
assert (window_report['n'],window_report['groups'])==(135,14)
svg=ET.parse(PAPER/'figures/fig-repeated-replacement.svg').getroot()
ns={'s':'http://www.w3.org/2000/svg'}
scale=[]
for i,row in enumerate(window_report['rows']):
    if row['layers']=='16 only':
        expected=dict(window_data['sufficiency'])[16]
        assert row['writes']==1
    else:
        lo,hi=map(int,row['layers'].split('–'))
        expected=window_data['windows'][f'w{lo}_{hi}']
        assert row['writes']==hi-lo+1
    assert row['recovery']==expected
    group=svg.find(f'.//s:g[@id="measured-window-{i}"]',ns)
    assert group is not None
    coordinates=[float(v) for v in re.findall(r'-?\d+(?:\.\d+)?',group.find('s:path',ns).attrib['d'])]
    x=coordinates[::2]
    scale.append((max(x)-min(x))/expected)
assert max(scale)-min(scale)<1e-4,'Bar widths must match source recoveries'
assert window_report['point_estimates_only']
report={'numerical_inputs_unchanged':True,'input_sha256':hashes,
        'main_figures':4,'main_tables':3,'appendix_tables':1,
        'checked':'Three main tables; repeated-replacement source values, write counts and rendered bar widths',
        'repeated_replacement_conditions':len(window_report['rows'])}
(PAPER/'audit/THREE-DISPLAY-REVISION-20261017.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: {len(inputs)} numerical inputs unchanged; three main tables and six repeated-replacement bars match source values.')
