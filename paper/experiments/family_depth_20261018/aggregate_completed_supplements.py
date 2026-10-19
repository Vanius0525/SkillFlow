"""Aggregate audited supplements; reconstruct each suite's own baselines."""
import argparse,collections,hashlib,json,re,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
audit=a.root/'post-quota-audit-20261019';report=json.loads((audit/'report.json').read_text())
assert (audit/'AUDIT-COMPLETE').exists() and report['reverse_order_all_passed'] and report['fresh_process_checks']==16
assert report['changed_labels']==0
sources={r['file']:r for r in report['files']}
def audited(path):
 rel=str(path.relative_to(a.root));data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==sources[rel]['sha256']
 rows=[json.loads(s) for s in data.splitlines()];overlay=[json.loads(s) for s in (audit/(rel+'.grading.jsonl')).read_text().splitlines()]
 assert len(rows)==len(overlay)==sources[rel]['records']
 for idx,(r,g) in enumerate(zip(rows,overlay)):
  assert idx==g['record_index'] and r['instance_id']==g['instance_id'] and hashlib.sha256(r['text'].encode()).hexdigest()==g['text_sha256']
  r['correct']=bool(g['correct'])
 return rows
sys.path.insert(0,str(a.root/'repo/howskill'))
from howskill import sra
from howskill.wb_spanvec import family_of
instances,skills,*_=sra.load('theoremqa')
results=[]
for suite in ['battery','battery-l2','windows','bridge','repair']:
 path=a.root/f'deepseek-theoremqa-corrected54-{suite}.jsonl';assert path.with_suffix('.done.json').exists();rows=audited(path)
 by={}
 for r in rows:
  key=(r['instance_id'],r['arm'],r['layer']);assert key not in by;by[key]=r
 groups=collections.defaultdict(set)
 for r in rows:
  if r['arm']=='donor':groups[r['group']].add(r['instance_id'])
 eligible=[];missing_baselines=[]
 for group,ids in groups.items():
  if any((i,arm,-1) not in by for i in ids for arm in ['donor','receiver','no_skill']):missing_baselines+=sorted(ids);continue
  if any(by[i,'receiver',-1]['correct'] for i in ids):continue
  eligible += sorted(i for i in ids if by[i,'donor',-1]['correct'] and not by[i,'no_skill',-1]['correct'])
 arms=sorted({(r['arm'],r['layer']) for r in rows if r['layer']>=0})
 missing=[(i,arm,l) for i in eligible for arm,l in arms if (i,arm,l) not in by]
 unavailable=[];unexpected_missing=[]
 families={g:family_of(skills[instances[sorted(ids)[0]]['skill_annotations'][0]]['content'].splitlines()[0].strip('# ')) for g,ids in groups.items()}
 for iid,arm,l in missing:
  g=by[iid,'donor',-1]['group']
  if arm=='same_family_mean' and not any(h!=g and families[h]==families[g] for h in groups):unavailable.append((iid,arm,l))
  else:unexpected_missing.append((iid,arm,l))
 estimates=[]
 for arm,l in arms:
  obs=[by[i,arm,l] for i in eligible if (i,arm,l) in by]
  estimates.append({'arm':arm,'layer':l,'n':len(obs),'correct':sum(r['correct'] for r in obs),'accuracy':sum(r['correct'] for r in obs)/len(obs) if obs else None,'truncated':sum(bool(r.get('truncated')) for r in obs)})
 identity=[]
 for r in rows:
  if r['arm']=='identity':
   assert (r['instance_id'],'receiver',-1) in by
   if r['token_ids']!=by[r['instance_id'],'receiver',-1]['token_ids']:identity.append([r['instance_id'],r['layer']])
 result={'suite':suite,'model':'DeepSeek-LLM-7B-Chat','task':'TheoremQA','observed_baseline_items':sum(map(len,groups.values())),'eligible_ids':eligible,'eligible_n':len(eligible),'eligible_groups':len({by[i,'donor',-1]['group'] for i in eligible}),'missing_baselines':missing_baselines,'missing_observed_grid':missing,'structurally_unavailable':unavailable,'unexpected_missing':unexpected_missing,'identity_failures':identity,'estimates':estimates,'scope':'Bridge limited to two candidates; variable donor controls can be structurally unavailable; never impute missing arms.'}
 results.append(result)
# Legacy narrow tables and raw answers are bound one-to-one by generation order.
legacy=a.root/'legacy-replay-20261019';tr={};ko={};baseline={};identity=[];mapping_count=0
expected=json.loads((legacy/'legacy-q06-theoremqa.expected.json').read_text())
for path in sorted(legacy.glob('q06-*.jsonl')):
 if path.name.endswith('.answers.jsonl') or not path.with_suffix('.done.json').exists():continue
 done=json.loads(path.with_suffix('.done.json').read_text());wide=[json.loads(s) for s in path.read_text().splitlines()];raw=audited(path.with_suffix('.answers.jsonl'))
 assert done['answers']==len(raw) and done['records']==len(wide)
 if 'output_sha256' in done:assert hashlib.sha256(path.read_bytes()).hexdigest()==done['output_sha256']
 want=[]
 for r in wide:
  iid=r['instance_id']
  for k,v in r.items():
   if not k.startswith('ok_'):continue
   if isinstance(v,list):
    assert k=='ok_block_from' and r['layers']==list(range(28)) and len(v)==28
    want += [(iid,f'ko_L{l}',x) for l,x in zip(r['layers'],v)]
   else:want.append((iid,k,v))
 assert len(want)==len(raw),(path,len(want),len(raw))
 tokens={}
 for (iid,k,v),rr in zip(want,raw):
  assert iid==rr['instance_id'] and bool(v)==rr['correct'],(path,iid,k)
  tokens[iid,k]=rr;mapping_count+=1
 for r in wide:
  iid=r['instance_id']
  if 'transfer' in path.name:
   e=expected[iid];assert (r['n_prompt'],r['n_patched'],r['doc_start'])==(e['n_prompt'],e['n_patched'],e['doc_start'])
   if 'ok_receiver' in r:assert iid not in baseline;baseline[iid]=r
   for l in r['layers']:
    rr=tokens[iid,f'ok_real_L{l}'];assert rr['arm_local']=='real' and rr['layer_local']==l
    assert (iid,l) not in tr;tr[iid,l]=rr
    if f'ok_self_L{l}' in r:
     assert iid in baseline
     # The receiver baseline raw is in the first block.
     if 'ok_receiver' in r:baseline[iid]['receiver_tokens']=tokens[iid,'ok_receiver']['token_ids']
     if tokens[iid,f'ok_self_L{l}']['token_ids']!=baseline[iid]['receiver_tokens']:identity.append([iid,l])
  else:
   ko[iid]={'wide':r,'raw':{k:rr for (i,k),rr in tokens.items() if i==iid}}
groups=collections.defaultdict(list)
for r in baseline.values():groups[r['calculator_id']].append(r)
eligible={r['instance_id'] for rs in groups.values() if not any(r['ok_receiver'] for r in rs) for r in rs if r['ok_gold_in_context'] and not r['ok_none']}
assert len(baseline)==168 and set(baseline)==set(expected)
assert set(ko)==eligible,('KO was admitted using the complete transfer baselines',len(ko),len(eligible))
ids=sorted(i for i in eligible if ko[i]['wide']['ok_with'] and not ko[i]['wide']['ok_without'])
missing=[(i,l,arm) for i in ids for l in range(28) for arm in ['transfer','knockout'] if (arm=='transfer' and (i,l) not in tr) or (arm=='knockout' and f'ko_L{l}' not in ko[i]['raw'])]
assert not missing and not identity
transfer=[sum(tr[i,l]['correct'] for i in ids)/len(ids) for l in range(28)]
retention=[sum(ko[i]['raw'][f'ko_L{l}']['correct'] for i in ids)/len(ids) for l in range(28)]
legacy_result={'model':'Qwen3-0.6B','task':'TheoremQA','candidate_n':len(baseline),'transfer_eligible_n':len(eligible),'common_n':len(ids),'common_groups':len({baseline[i]['calculator_id'] for i in ids}),'ids':ids,'raw_mapping_records':mapping_count,'identity_failures':identity,'missing':missing,'transfer':transfer,'retention':retention,'transfer_boundary':next((l for l,x in enumerate(transfer) if x<.5),None),'reading_boundary':next((l for l,x in enumerate(retention) if x>=.5),None),'truncated':{'transfer':[sum(tr[i,l]['truncated'] for i in ids) for l in range(28)],'knockout':[sum(ko[i]['raw'][f'ko_L{l}']['truncated'] for i in ids) for l in range(28)]},'scope':'Regeneration on frozen 168 candidates, not recovery of missing historical text; knockout budget 900 has historical-budget caveat. Full raw and narrow mapping verified; all layers and available self identities checked.'}
result={'source_audit':'post-quota-audit-20261019/report.json','sources':sources,'deepseek_suites':results,'legacy_q06':legacy_result,'raw_retained':True,'paper_updated':False}
assert not a.out.exists();a.out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'deepseek':[{'suite':r['suite'],'n':r['eligible_n'],'groups':r['eligible_groups'],'missing':len(r['missing_observed_grid']),'identity_failures':len(r['identity_failures'])} for r in results],'q06':{k:legacy_result[k] for k in ['candidate_n','transfer_eligible_n','common_n','common_groups','transfer_boundary','reading_boundary','raw_mapping_records']}}))
