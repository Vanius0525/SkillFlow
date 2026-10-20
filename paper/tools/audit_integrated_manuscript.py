"""Audit current manuscript numbers, reachable inputs and rendered figures."""
import argparse,hashlib,json,re
from pathlib import Path
import pymupdf
from make_overleaf_zip import project_members
from _paths import PAPER,VALUES,TABLES,FIGURES,AUDIT
p=argparse.ArgumentParser();p.add_argument('--pdf',type=Path);a=p.parse_args()
cells=json.loads((VALUES/'depth-current-values.json').read_text());lookup={(c['model'],c['task']):c for c in cells};assert len(lookup)==8
integration=json.loads((AUDIT/'INTEGRATION-20261020.json').read_text())
for name,digest in integration['input_sha256'].items():assert hashlib.sha256((PAPER/name).read_bytes()).hexdigest()==digest,name
# Verify displayed boundaries and independent samples directly from the measured arrays.
table=(TABLES/'tab-paired-depth.tex').read_text()
for c in cells:
 tr,q=c['transfer'],c['retention'];t=next(i for i,v in enumerate(tr) if v<.5);r=next(i for i,v in enumerate(q) if v>=.5)
 assert (t,r)==(c['transfer_boundary'],c['reading_boundary'])
 for tau in [.4,.5,.6]:assert next(i for i,v in enumerate(tr) if v<tau)<next(i for i,v in enumerate(q) if v>=tau)
 if True:
  n,g=c['common']['n'],c['common']['groups'];row=f'${n}/{g}$ & ${t}$ & ${r}$ & ${r-t}$ & ${100*(r-t)/c["n_layers"]:.1f}$';assert row in table,row
# Bind each new depth vector to the finalized independent audit (not to rounded prose).
e=PAPER/'experiments/family_depth_20261018'
for name,model in [('q8-independent-audit-20261020.json','Qwen3-8B'),('mistral-independent-audit-20261020-r1.json','Mistral-7B')]:
 source=json.loads((e/name).read_text());c=lookup[model,'TheoremQA'];assert c['transfer']==source['transfer'] and c['retention']==source['retention'] and c['common']['ids']==source['common_ids']
repair=json.loads((VALUES/'repair-extension-values.json').read_text());rtable=(TABLES/'tab-repair-extension.tex').read_text();assert len(repair)==8
for x in repair:
 assert all(x['accuracy'][arm]==v/x['n'] for arm,v in x['correct'].items())
 assert x['gain_pp']==100*(x['correct']['SC']-x['correct']['S'])/x['n']
 assert x['gain_pp']>0 and x['recut_loss_pp']>0
 vals=' & '.join(f'${100*x["accuracy"][arm]:.1f}$' for arm in ['S','C','SC','SC_recut']);assert vals in rtable,vals
# Only inspect reachable manuscript inputs; dormant legacy appendices are not submitted.
members=project_members(PAPER);tex='\n'.join(f.read_text() for f in members if f.suffix=='.tex')
checked_tex='\n'.join(line for line in tex.splitlines() if not line.startswith(r'\newcommand{\PEND}'))
assert not re.search(r'\bPending\b|\bconfidence interval\b|\bbootstrap interval\b|\b95\\?%\b|\bCI\b',checked_tex,re.I)
assert not re.search(r'(?<!other )(six|seven) (verified|completed|main|model--)',tex)
assert '\\input{tables/tab-repair-extension}' in tex and '\\input{tables/tab-extension-populations}' in tex
assert 'eight verified model--benchmark' in tex
assert not re.search(r'Qwen3-0[.]6B|app:scale-check|fig-depth-scale-check',tex)
labels=re.findall(r'\\label\{([^}]+)\}',tex);assert len(labels)==len(set(labels))
figure_checks={}
for name,expected in [('fig-transfer-reading.pdf',8)]:
 doc=pymupdf.open(FIGURES/name);text=' '.join(page.get_text() for page in doc)
 assert text.count('T/R =')==expected,(name,text.count('T/R ='))
 assert 'Skill transfer' in text and 'Skill dependence' in text
 for c in cells:
  n,g=c['common']['n'],c['common']['groups'];assert f'n={n}, G={g}' in text,(name,n,g)
  assert f"{c['transfer_boundary']}/{c['reading_boundary']}" in text
 figure_checks[name]={'panels':expected,'sha256':hashlib.sha256((FIGURES/name).read_bytes()).hexdigest()}
result={'main_depth_cells':8,'supplementary_depth_cells':0,'repair_rows':8,'input_hashes_bound':True,'threshold_checks_passed':True,'reachable_tex_no_pending_or_displayed_uncertainty':True,'figure_checks':figure_checks,'raw_inference_run':False}
if a.pdf:
 doc=pymupdf.open(a.pdf);assert len(doc)<=12,('total page limit',len(doc));pdftext='\n'.join(p.get_text() for p in doc);assert 'Pending' not in pdftext and '??' not in pdftext
 for snippet in ['82/66','72/58','43.4','37.7']:assert snippet in pdftext,snippet
 result.update(total_pages=len(doc),pdf_sha256=hashlib.sha256(a.pdf.read_bytes()).hexdigest())
(AUDIT/'MANUSCRIPT-INTEGRATED-20261020.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
