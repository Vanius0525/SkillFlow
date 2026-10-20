"""Validate current display coverage against bound audit counts and rendered PDFs."""
import argparse,hashlib,json,re
from pathlib import Path
import pymupdf
from _paths import PAPER,VALUES,TABLES,FIGURES,AUDIT
from make_overleaf_zip import project_members
v=json.loads((VALUES/'eight-cell-display-values.json').read_text());rows=v['rows']
for p,h in v['source_sha256'].items():assert hashlib.sha256((PAPER/p).read_bytes()).hexdigest()==h,p
expected={(m,t) for m in ['Qwen3-8B','Mistral-7B','Llama-3.1-8B','DeepSeek-LLM-7B'] for t in ['MedCalc','TheoremQA']}
assert {(r['model'],r['task']) for r in rows}==expected
matrix=json.loads((PAPER/'experiments/family_depth_20261018/completed-matrix-audit-20261020-r3.json').read_text());by={x['file']:x for x in matrix['files']}
count=0
for r in rows:
 pre={'Qwen3-8B':'backfill-q8','Mistral-7B':'backfill-mistral','Llama-3.1-8B':'llama','DeepSeek-LLM-7B':'deepseek'}[r['model']]+'-'+r['task'].lower()
 for suite,key,layers in [('repair','repair',[8,12,16,24]),('edges','edges',[8,16,24])]:
  if r['historical_l8']:
   f=json.loads((PAPER/'experiments/mechanism_20261017/formal-audit.json').read_text());src=f['results'][suite]
   assert r['n']==f['primary_n'] and r['groups']==f['groups']
   for i,a in enumerate(src['arms']):
    for j,l in enumerate(src['layers']):assert r[key][a][str(l)]['correct']==src['n_correct'][i][j];count+=1
  else:
   x=by[pre+('-corrected54' if r['model']=='DeepSeek-LLM-7B' and r['task']=='TheoremQA' else '')+'-'+suite+'.jsonl']
   assert r['n']==x['eligible_n'] and r['groups']==x['eligible_groups'] and not x['unexpected_missing_grid']
   for e in x['estimates']:
    if e['arm'] in r[key] and e['layer'] in layers:
     z=r[key][e['arm']][str(e['layer'])];assert (z['n'],z['correct'])==(e['n'],e['correct']);count+=1
 for key in ['battery_l2','battery_l8']:
  for arm,e in r[key].items():
   if e is not None:assert e['accuracy']==e['correct']/e['n']
 for key in ['repair','edges']:
  for a,grid in r[key].items():
   for l,e in grid.items():assert e['accuracy']==e['correct']/e['n']
for name in ['tab-control-matrix.tex','tab-mechanism-contrasts.tex','tab-additional-controls.tex','tab-repair-extension.tex','tab-extension-populations.tex']:
 text=(TABLES/name).read_text()
 for r in rows:assert text.count(r['label']+' & '+r['task']+' & ')==1,(name,r['model'],r['task'])
# Every active empirical display has eight cells; the design figure is schematic.
for name in ['fig-teaser.pdf','fig-mechanism-results.pdf']:
 doc=pymupdf.open(FIGURES/name);text=' '.join(p.get_text() for p in doc)
 for r in rows:
  label=r['label'].replace('Llama-3.1-8B','Llama-8B')+' / '+('MC' if r['task']=='MedCalc' else 'TQA')
  assert label in text,(name,label)
tex='\n'.join(p.read_text() for p in project_members(PAPER) if p.suffix=='.tex')
assert not re.search('Qwen3-0[.]6B|app:scale-check|fig-depth-scale-check',tex)
assert len(re.findall(r'\\begin\{table\*?\}',tex))==6
pdf=pymupdf.open(PAPER/'skillvector-www2027.pdf');text='\n'.join(p.get_text() for p in pdf)
assert len(pdf)<=12 and 'Qwen3-0.6B' not in text and '??' not in text
for n in range(1,7):assert f'Table {n}:' in text
parser=argparse.ArgumentParser();parser.add_argument('--stage',type=Path,required=True);stage=parser.parse_args().stage
aux=(stage/'main.aux').read_text();main=int(re.search(r'\\newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}',aux)[1]);assert main<=8
log=(stage/'main.log').read_text(errors='replace');assert not re.search(r'^! |Overfull \\[hv]box|LaTeX Warning: (Reference|Citation).*undefined',log,re.M)
report={'model_benchmark_cells':8,'empirical_figures':3,'schematic_figures':1,'tables':6,'mechanism_arm_layer_counts_verified':count,'source_hashes_verified':True,'small_model_in_active_manuscript':False,'main_pages':main,'total_pages':len(pdf),'errors':0,'undefined':0,'overfull':0,'raw_inference_run':False,'pdf_sha256':hashlib.sha256((PAPER/'skillvector-www2027.pdf').read_bytes()).hexdigest()}
(AUDIT/'EIGHT-CELL-COVERAGE-20261020.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
