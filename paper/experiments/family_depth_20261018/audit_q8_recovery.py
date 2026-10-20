"""Audit completed Qwen8 recovery without altering generation outputs."""
import argparse, collections, copy, hashlib, json, random, re, subprocess, sys, time
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
p.add_argument('--recovery',type=Path,required=True)
p.add_argument('--output',type=Path)
p.add_argument('--report-stdout',action='store_true',help='Keep overlays in memory and emit report without shared-disk writes')
a=p.parse_args()
if not a.report_stdout:
 assert a.output is not None
 a.output.mkdir(exist_ok=False)
start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
sys.path.insert(0,str(a.root/'repo/howskill'))
from howskill import sra,sra_eval
import latex2sympy2 as parser
initial={k:copy.deepcopy(getattr(parser,k)) for k in ('var','variances','VARIABLE_VALUES','frac_type','is_real')}
instances,*_=sra.load('theoremqa')
def grade(text,iid):
 for k,v in initial.items():setattr(parser,k,copy.deepcopy(v))
 return sra_eval.evaluate(text,instances[iid])
old=a.root/'legacy-replay-20261019'
expected_path=old/'legacy-q8-theoremqa.expected.json'
expected=json.loads(expected_path.read_text())
recovery_done=json.loads((a.recovery/'q8-transfer-recovery.done.json').read_text())
paths=[Path(s) for s in recovery_done['blocks']]
assert len(paths)==9 and len(set(paths))==9
paths.append(a.recovery/'q8-knockout.jsonl')
cache={};texts={};reports=[];baselines={};transfer={};knockout={};identity=[];mapping=0;changed=[]
for bi,path in enumerate(paths):
 wide=rows(path);rawpath=path.with_suffix('.answers.jsonl');raw=rows(rawpath)
 done=json.loads(path.with_suffix('.done.json').read_text())
 manifest=json.loads(path.with_suffix('.replay-manifest.json').read_text())
 assert done['records']==len(wide) and done['answers']==len(raw)
 hashes={'raw_sha256':sha(rawpath),'output_sha256':sha(path)}
 for k,v in hashes.items():
  if k in done:assert done[k]==v,(path,k)
 assert manifest['expected_sha256']==sha(expected_path)
 module='wb_spanvec' if bi<9 else 'wb_knockout'
 assert manifest['module_sha256']==sha(a.root/f'repo/howskill/howskill/{module}.py')
 args=manifest['args'];assert args[args.index('--max-new')+1]=='900'
 assert args[args.index('--attn')+1]==('sdpa' if bi<9 else 'eager')
 if bi<9:
  want_layers=list(range(bi*4,min(bi*4+4,36)))
  assert args[args.index('--layers')+1]==','.join(map(str,want_layers))
 else:want_layers=list(range(36))
 want=[]
 for r in wide:
  iid=r['instance_id'];assert iid in expected
  for k,v in r.items():
   if not k.startswith('ok_'):continue
   if isinstance(v,list):
    assert k=='ok_block_from' and r['layers']==want_layers and len(v)==len(want_layers)
    want.extend((iid,f'ko_L{l}',x) for l,x in zip(r['layers'],v))
   else:want.append((iid,k,v))
 assert len(want)==len(raw)
 tokenmap={};overlay=[]
 for idx,((iid,key,label),rr) in enumerate(zip(want,raw)):
  assert iid==rr['instance_id'] and bool(label)==bool(rr['correct'])
  assert rr['seq']==idx and len(rr['token_ids'])<=900
  textsha=hashlib.sha256(rr['text'].encode()).hexdigest();ck=(iid,textsha)
  if ck not in cache:cache[ck]=grade(rr['text'],iid);texts[ck]=rr['text']
  result=cache[ck]
  g={'record_index':idx,'instance_id':iid,'key':key,'text_sha256':textsha,**result}
  overlay.append(g)
  if bool(result['correct'])!=bool(label):changed.append({'file':path.name,**g})
  tokenmap[iid,key]={**rr,'correct':bool(result['correct'])};mapping+=1
 # Overlays preserve a one-to-one mapping to each original answer.
 if not a.report_stdout:(a.output/(rawpath.name+'.grading.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in overlay))
 for r in wide:
  iid=r['instance_id']
  corrected={k:tokenmap[iid,k]['correct'] for k,v in r.items() if k.startswith('ok_') and not isinstance(v,list)}
  if bi<9:
   e=expected[iid]
   assert (r['n_prompt'],r['n_patched'],r['doc_start'])==(e['n_prompt'],e['n_patched'],e['doc_start'])
   assert r['layers']==want_layers
   if bi==0:
    assert iid not in baselines
    baselines[iid]={**r,**corrected,'receiver_tokens':tokenmap[iid,'ok_receiver']['token_ids']}
   for l in want_layers:
    rr=tokenmap[iid,f'ok_real_L{l}']
    assert rr['arm_local']=='real' and rr['layer_local']==l and (iid,l) not in transfer
    transfer[iid,l]=rr
    if f'ok_self_L{l}' in r:
     if tokenmap[iid,f'ok_self_L{l}']['token_ids']!=baselines[iid]['receiver_tokens']:identity.append([iid,l])
  else:
   assert iid not in knockout
   knockout[iid]={'wide':{**r,**corrected},'raw':{k:rr for (i,k),rr in tokenmap.items() if i==iid}}
 reports.append({'path':str(path),'raw':str(rawpath),**hashes,'records':len(wide),'answers':len(raw),'manifest_sha256':sha(path.with_suffix('.replay-manifest.json')),'done_has_hashes':all(k in done for k in hashes),'admission':manifest.get('optimization',{})})
 print('AUDITED',path.name,len(wide),len(raw),flush=True)
assert set(baselines)==set(expected) and len(baselines)==168
groups=collections.defaultdict(list)
for r in baselines.values():groups[r['calculator_id']].append(r)
eligible={r['instance_id'] for rs in groups.values() if not any(x['ok_receiver'] for x in rs) for r in rs if r['ok_gold_in_context'] and not r['ok_none']}
# Qwen8 KO began before admission was enabled, so full-candidate KO is valid.
assert eligible<=set(knockout)<=set(expected)
ids=sorted(i for i in eligible if knockout[i]['wide']['ok_with'] and not knockout[i]['wide']['ok_without'])
missing=[(i,l,arm) for i in ids for l in range(36) for arm in ['transfer','knockout'] if (arm=='transfer' and (i,l) not in transfer) or (arm=='knockout' and f'ko_L{l}' not in knockout[i]['raw'])]
transfer_missing=[(i,l) for i in eligible for l in range(36) if (i,l) not in transfer]
assert not missing and not transfer_missing and not identity
# Regrade in reverse order to detect leaked symbolic-parser state.
for key in reversed(list(cache)):assert grade(texts[key],key[0])==cache[key],key
keys=list(cache);random.Random(0).shuffle(keys)
code="import sys,json;sys.path.insert(0,sys.argv[1]);from howskill import sra_eval;x=json.load(sys.stdin);print(json.dumps(sra_eval.evaluate(x['text'],x['item'])))"
for key in keys[:16]:
 iid,_=key
 r=subprocess.run([sys.executable,'-c',code,str(a.root/'repo/howskill')],input=json.dumps({'text':texts[key],'item':instances[iid]}),text=True,capture_output=True,check=True,timeout=30)
 assert json.loads(r.stdout)==cache[key],key
n=len(ids)
t=[sum(transfer[i,l]['correct'] for i in ids)/n for l in range(36)] if n else None
k=[sum(knockout[i]['raw'][f'ko_L{l}']['correct'] for i in ids)/n for l in range(36)] if n else None
result={'model':'Qwen3-8B','task':'TheoremQA','sources':reports,'raw_mapping_records':mapping,'unique_texts':len(cache),'changed_labels':changed,'reverse_order_all_passed':True,'fresh_process_checks':min(16,len(keys)),'candidate_n':168,'transfer_eligible_ids':sorted(eligible),'transfer_eligible_n':len(eligible),'knockout_observed_n':len(knockout),'common_ids':ids,'common_n':n,'common_groups':len({baselines[i]['calculator_id'] for i in ids}),'identity_failures':identity,'missing_common_grid':missing,'missing_transfer_eligible_grid':transfer_missing,'transfer':t,'retention':k,'transfer_boundary':next((l for l,x in enumerate(t) if x<.5),None) if t else None,'reading_boundary':next((l for l,x in enumerate(k) if x>=.5),None) if k else None,'truncated_transfer':[sum(transfer[i,l]['truncated'] for i in ids) for l in range(36)],'truncated_knockout':[sum(knockout[i]['raw'][f'ko_L{l}']['truncated'] for i in ids) for l in range(36)],'seconds':time.time()-start,'raw_retained':True,'paper_updated':False,'scope':'Frozen candidates; SSD complete first block plus HDD completed recovery only. Full candidate KO admitted at aggregation. Historical KO budget exact comparability remains unverified. Changes in baseline labels can invalidate generation admission; inspect changed_labels before manuscript use.'}
if a.report_stdout:
 print('REPORT_JSON '+json.dumps(result),flush=True)
 print('MEMORY_AUDIT_COMPLETE',flush=True)
else:
 (a.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
 (a.output/'AUDIT-COMPLETE').write_text('Independent audit and aggregation complete; manuscript unchanged\n')
print(json.dumps({key:result[key] for key in ['candidate_n','transfer_eligible_n','knockout_observed_n','common_n','common_groups','raw_mapping_records','transfer_boundary','reading_boundary','seconds']}),flush=True)
