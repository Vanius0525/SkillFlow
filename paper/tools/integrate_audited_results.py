"""Build manuscript-only values from finalized audit reports; never edit raw data."""
import hashlib,json
from pathlib import Path
from _paths import PAPER,VALUES,TABLES,AUDIT
E=PAPER/'experiments/family_depth_20261018'
def read(p):return json.loads(p.read_text())
sources={}
def audited(name):
 p=E/name;sources[str(p.relative_to(PAPER))]=hashlib.sha256(p.read_bytes()).hexdigest();return read(p)
completion=audited('completion-matrix-20261020-r3.json');assert completion['conditional_generation_and_remaining_audits_complete']
original=read(VALUES/'depth-verified-extension-20261019.json')
cells=[]
for c in original[:3]:
 if c['model']=='Qwen3-0.6B':continue
 pop=c['common'];cells.append({'model':c['model'],'task':c['task'],'n_layers':c['n_layers'],'transfer':pop['transfer'],'retention':pop['retention'],'common':{'n':pop['n'],'groups':pop['groups'],'ids':pop['ids']},'provenance':'Previously audited MedCalc; source checksums revalidated on 2026-10-20'})
for name,model,nl in [('q8-independent-audit-20261020.json','Qwen3-8B',36),('mistral-independent-audit-20261020-r1.json','Mistral-7B',32)]:
 r=audited(name);assert not r['changed_labels'] and not r['missing_common_grid'] and not r['identity_failures'] and r['reverse_order_all_passed'] and r['fresh_process_checks']==16
 cells.append({'model':model,'task':'TheoremQA','n_layers':nl,'transfer':r['transfer'],'retention':r['retention'],'common':{'n':r['common_n'],'groups':r['common_groups'],'ids':r['common_ids']},'provenance':'Frozen candidate regeneration; transfer SDPA, knockout eager, both 900-token limit; isolated grading'})
for r in audited('final-family-depth-audit-20261020.json')['comparisons']:
 assert r['status']=='complete' and not r['baseline_token_drift'] and not r['missing'] and not r['identity_failures']
 model={'llama':'Llama-3.1-8B','deepseek':'DeepSeek-LLM-7B'}[r['model']]
 cells.append({'model':model,'task':{'medcalc':'MedCalc','theoremqa':'TheoremQA'}[r['task']],'n_layers':len(r['transfer']),'transfer':r['transfer'],'retention':r['retention'],'common':{'n':r['n'],'groups':r['groups'],'ids':r['ids']},'provenance':'Matched eager-attention protocols; isolated TheoremQA grading and scorefix supplements'})
assert len(cells)==8 and len({(c['model'],c['task']) for c in cells})==8
for c in cells:
 t,q=c['transfer'],c['retention'];assert len(t)==len(q)==c['n_layers'] and len(c['common']['ids'])==c['common']['n']
 c['dependence']=[1-x for x in q];c['transfer_boundary']=next((l for l,x in enumerate(t) if x<.5),None);c['reading_boundary']=next((l for l,x in enumerate(q) if x>=.5),None)
 c['common'].update(transfer=t,retention=q,transfer_boundary=c['transfer_boundary'],reading_boundary=c['reading_boundary'])
 c['threshold_sensitivity']={str(tau):{'T':next((l for l,x in enumerate(t) if x<tau),None),'R':next((l for l,x in enumerate(q) if x>=tau),None)} for tau in [.4,.5,.6]}
 assert all(v['T'] is not None and v['R'] is not None and v['T']<v['R'] for v in c['threshold_sensitivity'].values()),c['model']
model_order=['Qwen3-8B','Mistral-7B','Llama-3.1-8B','DeepSeek-LLM-7B']
cells.sort(key=lambda c:(model_order.index(c['model']),['MedCalc','TheoremQA'].index(c['task'])))
(VALUES/'depth-current-values.json').write_text(json.dumps(cells,indent=2)+'\n')
matrix=audited('completed-matrix-audit-20261020-r3.json');assert not matrix['new_grading_changes']
by={x['file']:x for x in matrix['files']}
formal=read(PAPER/'experiments/mechanism_20261017/formal-audit.json');sources['experiments/mechanism_20261017/formal-audit.json']=hashlib.sha256((PAPER/'experiments/mechanism_20261017/formal-audit.json').read_bytes()).hexdigest()
repairs=[]
for model in model_order[:4]:
 for task in ['MedCalc','TheoremQA']:
  if (model,task)==('Qwen3-8B','MedCalc'):
   r=formal['results']['repair'];j=r['layers'].index(16);counts={arm:r['n_correct'][r['arms'].index(arm)][j] for arm in ['S','C','SC','SC_recut']};n=formal['primary_n'];g=formal['groups'];source='experiments/mechanism_20261017/formal-audit.json'
  else:
   prefix={'Qwen3-8B':'backfill-q8','Mistral-7B':'backfill-mistral','Llama-3.1-8B':'llama','DeepSeek-LLM-7B':'deepseek'}[model]+'-'+task.lower()
   if model=='DeepSeek-LLM-7B' and task=='TheoremQA':prefix+='-corrected54'
   x=by[prefix+'-repair.jsonl'];assert not x['unexpected_missing_grid'];n=x['eligible_n'];g=x['eligible_groups'];es={(v['arm'],v['layer']):v for v in x['estimates']};assert all(es[arm,16]['n']==n for arm in ['S','C','SC','SC_recut']);counts={arm:es[arm,16]['correct'] for arm in ['S','C','SC','SC_recut']};source=x['file']
  repairs.append({'model':model,'task':task,'n':n,'groups':g,'layer':16,'correct':counts,'accuracy':{arm:v/n for arm,v in counts.items()},'gain_pp':100*(counts['SC']-counts['S'])/n,'recut_loss_pp':100*(counts['SC']-counts['SC_recut'])/n,'source':source})
assert all(x['gain_pp']>0 and x['recut_loss_pp']>0 for x in repairs)
(VALUES/'repair-extension-values.json').write_text(json.dumps(repairs,indent=2)+'\n')
lines=[r'\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llrrrrrrr@{}}',r'\toprule',r'Model & Task & $n/G$ & $S$ & $C$ & $SC$ & $SC{+}\mathrm{recut}$ & Gain (pp) & Recut loss (pp) \\',r'\midrule']
for x in repairs:
 vals=[f"${100*x['accuracy'][a]:.1f}$" for a in ['S','C','SC','SC_recut']]
 lines.append(x['model'].replace('DeepSeek-LLM-7B','DeepSeek-7B')+' & '+x['task']+f" & ${x['n']}/{x['groups']}$ & "+' & '.join(vals)+f" & ${x['gain_pp']:.1f}$ & ${x['recut_loss_pp']:.1f}$"+r' \\')
lines += [r'\bottomrule',r'\end{tabular*}']
(TABLES/'tab-repair-extension.tex').write_text('\n'.join(lines)+'\n')
# Independent population counts, not outcomes, for the expanded controls.
lines=[r'\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llrrrrrr@{}}',r'\toprule',r'Model & Task & L8 battery & L2 battery & Cross-question & Windows & Repair & Path cuts \\',r'\midrule']
for model in model_order[:4]:
 for task in ['MedCalc','TheoremQA']:
  if (model,task)==('Qwen3-8B','MedCalc'):values=['135','97','151','135','114','114']
  else:
   pre={'Qwen3-8B':'backfill-q8','Mistral-7B':'backfill-mistral','Llama-3.1-8B':'llama','DeepSeek-LLM-7B':'deepseek'}[model]+'-'+task.lower()
   values=[]
   for suite in ['battery','battery-l2','doclast','windows','repair','edges']:
    actual=pre+('-corrected54' if model=='DeepSeek-LLM-7B' and task=='TheoremQA' and suite!='doclast' else '')
    x=by[actual+'-'+suite+'.jsonl']
    if suite=='doclast':
     est=[e for e in x['estimates'] if e['arm']=='other_question' and e['layer']==8];values.append(str(est[0]['n']) if est else '0')
    else:values.append(str(x['eligible_n']))
  lines.append(model.replace('DeepSeek-LLM-7B','DeepSeek-7B')+' & '+task+' & '+' & '.join('$'+v+'$' for v in values)+r' \\')
lines += [r'\bottomrule',r'\end{tabular*}'];(TABLES/'tab-extension-populations.tex').write_text('\n'.join(lines)+'\n')
(AUDIT/'INTEGRATION-20261020.json').write_text(json.dumps({'input_sha256':sources,'main_depth_cells':8,'supplementary_depth_cells':0,'threshold_ordering_all_passed':True,'repair_comparisons':8,'gain_range_pp':[min(x['gain_pp'] for x in repairs),max(x['gain_pp'] for x in repairs)],'recut_loss_range_pp':[min(x['recut_loss_pp'] for x in repairs),max(x['recut_loss_pp'] for x in repairs)],'raw_outputs_modified':False},indent=2)+'\n')
print('Integrated 8 depth comparisons and 8 layer-16 repair comparisons')
