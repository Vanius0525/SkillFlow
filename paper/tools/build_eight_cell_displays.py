"""Generate eight-cell manuscript displays from the final r3 audit, without inference."""
import hashlib,json
from pathlib import Path
from _paths import PAPER,VALUES,TABLES,AUDIT
E=PAPER/'experiments/family_depth_20261018'
source=E/'completed-matrix-audit-20261020-r3.json'
m=json.loads(source.read_text());by={x['file']:x for x in m['files']}
f=json.loads((PAPER/'experiments/mechanism_20261017/formal-audit.json').read_text())
channels=json.loads((VALUES/'fig-channels-values.json').read_text())
history=json.loads((E/'completion-matrix-20261020-r3.json').read_text())['historical_q8_medcalc_doclast_verified']
windows=json.loads((VALUES/'main-evidence-values.json').read_text())['windows']
models=['Qwen3-8B','Mistral-7B','Llama-3.1-8B','DeepSeek-LLM-7B']
rows=[]
for model in models:
 for task in ['MedCalc','TheoremQA']:
  historical=(model,task)==('Qwen3-8B','MedCalc')
  pre={'Qwen3-8B':'backfill-q8','Mistral-7B':'backfill-mistral','Llama-3.1-8B':'llama','DeepSeek-LLM-7B':'deepseek'}[model]+'-'+task.lower()
  def get(suite):
   p=pre+('-corrected54' if model==models[-1] and task=='TheoremQA' and suite!='doclast' else '')
   x=by[p+'-'+suite+'.jsonl'];assert not x['unexpected_missing_grid'];return x
  def est(x,arm,layer):
   z=next(e for e in x['estimates'] if (e['arm'],e['layer'])==(arm,layer));return {'n':z['n'],'correct':z['correct'],'accuracy':z['correct']/z['n']}
  b2=get('battery-l2');b8=None if historical else get('battery')
  controls={}
  for arm in ['real','last_1','last_16','matched_prefix','other_skill','permuted','noise']:
   if historical:
    lookup={'real':('bottom','real'),'last_1':('top','tq1'),'last_16':('top','tq16'),'other_skill':('bottom','dcross'),'permuted':('bottom','dshuf'),'noise':('bottom','drand')}
    if arm=='matched_prefix':
     # Prefix-normalized recovery has a different matched donor baseline.
     controls[arm]=None;continue
    section,key=lookup[arm];acc=channels[section][key]['acc'][0];n=channels['n'];k=round(n*acc);assert abs(k/n-acc)<1e-12
    controls[arm]={'n':n,'correct':k,'accuracy':acc}
   else:controls[arm]=est(b8,arm,8)
  r={'model':model,'task':task,'label':model.replace('DeepSeek-LLM-7B','DeepSeek-7B'),'battery_l8':controls,'battery_l2':{a:est(b2,a,2) for a in ['real','last_1','last_16','other_skill','permuted','noise']},'l2_n':b2['eligible_n'],'l8_n':135 if historical else b8['eligible_n'],'historical_l8':historical}
  if historical:
   r.update(n=f['primary_n'],groups=f['groups'])
   r['repair']={a:{str(l):{'n':r['n'],'correct':f['results']['repair']['n_correct'][i][j],'accuracy':f['results']['repair']['accuracy'][i][j]} for j,l in enumerate(f['results']['repair']['layers'])} for i,a in enumerate(f['results']['repair']['arms'])}
   r['edges']={a:{str(l):{'n':r['n'],'correct':f['results']['edges']['n_correct'][i][j],'accuracy':f['results']['edges']['accuracy'][i][j]} for j,l in enumerate(f['results']['edges']['layers'])} for i,a in enumerate(f['results']['edges']['arms'])}
   r['cross_question']={'n':151,'current_l8':history['L8_current_rho'],'other_l8':history['L8_other_rho'],'unit':'recovery'}
   r['windows']={'n':135,'single':windows['w16_35'],'window_8_11':windows['w8_11'],'window_12_15':windows['w12_15'],'window_14_19':windows['w14_19'],'window_late':windows['w16_35'],'unit':'recovery'}
  else:
   x=get('repair');y=get('edges');assert set(x['eligible_ids'])==set(y['eligible_ids'])
   r.update(n=x['eligible_n'],groups=x['eligible_groups'])
   r['repair']={a:{str(l):est(x,a,l) for l in [8,12,16,24]} for a in ['S','C','SC','SC_recut']}
   r['edges']={a:{str(l):est(y,a,l) for l in [8,16,24]} for a in ['cut_reader_both','cut_self_both','cut_both_both']}
   x=get('doclast');cur=est(x,'current_question',8);oth=est(x,'other_question',8);assert cur['n']==oth['n']
   r['cross_question']={'n':oth['n'],'current_l8':cur['accuracy'],'other_l8':oth['accuracy'],'unit':'accuracy'}
   x=get('windows');late=next(e['arm'] for e in x['estimates'] if e['arm'].startswith('window_16_'))
   r['windows']={'n':x['eligible_n'],**{a:est(x,a,16 if a=='single' else {'window_8_11':8,'window_12_15':12,'window_14_19':14,late:16}[a])['accuracy'] for a in ['single','window_8_11','window_12_15','window_14_19',late]},'unit':'accuracy'}
   r['windows']['window_late']=r['windows'].pop(late)
  acc=lambda a,l:r['repair'][a][str(l)]['accuracy']
  r['gain_pp']=100*(acc('SC',16)-acc('S',16));r['additive_pp']=100*(acc('SC',16)-acc('S',16)-acc('C',16));r['recut_loss_pp']=100*(acc('SC',16)-acc('SC_recut',16))
  r['path_difference_pp']=100*(r['edges']['cut_self_both']['24']['accuracy']-r['edges']['cut_reader_both']['24']['accuracy'])
  rows.append(r)
assert len(rows)==8
out={'source_sha256':{str(p.relative_to(PAPER)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,E/'completion-matrix-20261020-r3.json',PAPER/'experiments/mechanism_20261017/formal-audit.json',VALUES/'fig-channels-values.json',VALUES/'main-evidence-values.json']},'rows':rows}
(VALUES/'eight-cell-display-values.json').write_text(json.dumps(out,indent=2)+'\n')
def table(name,cols,header,body):
 (TABLES/name).write_text('\n'.join([r'\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}'+cols+r'@{}}',r'\toprule',header+r' \\',r'\midrule',*body,r'\bottomrule',r'\end{tabular*}'])+'\n')
def row(r,vals):return r['label']+' & '+r['task']+' & '+' & '.join(vals)+r' \\'
def pct(x):return f'${100*x:.1f}$'
table('tab-control-matrix.tex','llrrrrrrrr',r'Model & Task & $n_2/n_8$ & L2 span & L8 span & Last 1 & Last 16 & Other & Permuted & Noise',[row(r,[f"${r['l2_n']}/{r['l8_n']}$",pct(r['battery_l2']['real']['accuracy']),*[pct(r['battery_l8'][a]['accuracy']) for a in ['real','last_1','last_16','other_skill','permuted','noise']]]) for r in rows])
table('tab-mechanism-contrasts.tex','llrrrrr',r'Model & Task & $n/G$ & L16: $SC-S$ & L16: interaction & L16: recut loss & L24: path gap',[row(r,[f"${r['n']}/{r['groups']}$",*[f"${r[k]:+.1f}$" for k in ['gain_pp','additive_pp','recut_loss_pp','path_difference_pp']]]) for r in rows])
# All eight additional-control rows use explicit units, preserving historical normalization.
table('tab-additional-controls.tex','llrlrrrrrr',r'Model & Task & $n_{\rm cross}/n_{\rm win}$ & Unit & Current & Other & W8--11 & W12--15 & W14--19 & W16--end',[row(r,[f"${r['cross_question']['n']}/{r['windows']['n']}$",'$\\rho$' if r['historical_l8'] else 'Acc.',*[f'${x:.2f}$' for x in [r['cross_question']['current_l8'],r['cross_question']['other_l8'],*[r['windows'][a] for a in ['window_8_11','window_12_15','window_14_19','window_late']]]]]) for r in rows])
print('Generated eight-cell controls, repair/path grids, contrasts, cross-question/windows.')
