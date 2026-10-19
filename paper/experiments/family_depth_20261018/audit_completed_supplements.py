"""Independent, versioned regrading of completed supplements; never edit raw."""
import argparse,copy,hashlib,json,random,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(exist_ok=False)
sys.path.insert(0,str(a.root/'repo/howskill'))
from howskill import sra,sra_eval
import latex2sympy2 as parser
initial={k:copy.deepcopy(getattr(parser,k)) for k in ('var','variances','VARIABLE_VALUES','frac_type','is_real')}
inst,*_=sra.load('theoremqa')
def grade(text,iid):
 for k,v in initial.items():setattr(parser,k,copy.deepcopy(v))
 return sra_eval.evaluate(text,inst[iid])
paths=[]
for suite in ['battery','battery-l2','windows','bridge','repair']:
 f=a.root/f'deepseek-theoremqa-corrected54-{suite}.jsonl'
 assert f.with_suffix('.done.json').exists(),f
 paths.append(f)
legacy=a.root/'legacy-replay-20261019'
assert (legacy/'q06-replay.done.json').exists()
for out in sorted(legacy.glob('q06-*.jsonl')):
 if out.name.endswith('.answers.jsonl'):continue
 done=out.with_suffix('.done.json')
 if not done.exists():continue
 raw=out.with_suffix('.answers.jsonl');d=json.loads(done.read_text())
 assert d['records']==len(out.read_text().splitlines()) and d['answers']==len(raw.read_text().splitlines())
 if 'raw_sha256' in d:assert d['raw_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest()
 paths.append(raw)
assert len(paths)==13,('Expected 5 DeepSeek + 7 Qwen0.6 blocks + 1 KO',len(paths))
cache={};examples={};reports=[];start=time.time()
for path in paths:
 rows=[json.loads(s) for s in path.read_text().splitlines()];overlay=[];changes=[]
 for idx,r in enumerate(rows):
  iid=r['instance_id'];sha=hashlib.sha256(r['text'].encode()).hexdigest();key=(iid,sha)
  if key not in cache:cache[key]=grade(r['text'],iid);examples[key]=r['text']
  result=cache[key]
  g={'record_index':idx,'instance_id':iid,'text_sha256':sha,**result}
  overlay.append(g)
  if bool(result['correct'])!=bool(r['correct']):changes.append(g)
 rel=str(path.relative_to(a.root));target=a.output/(rel+'.grading.jsonl');target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in overlay))
 reports.append({'file':rel,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'records':len(rows),'changed_labels':changes,'truncated_records':sum(bool(r.get('truncated')) for r in rows)})
 print('AUDITED',rel,len(rows),'changed',len(changes),flush=True)
for key in reversed(list(cache)):assert grade(examples[key],key[0])==cache[key],key
keys=list(cache);random.Random(0).shuffle(keys);checks=keys[:16]
code="import sys,json;sys.path.insert(0,sys.argv[1]);from howskill import sra_eval;x=json.load(sys.stdin);print(json.dumps(sra_eval.evaluate(x['text'],x['item'])))"
for iid,sha in checks:
 r=subprocess.run([sys.executable,'-c',code,str(a.root/'repo/howskill')],input=json.dumps({'text':examples[iid,sha],'item':inst[iid]}),text=True,capture_output=True,check=True,timeout=30)
 assert json.loads(r.stdout)==cache[iid,sha]
report={'files':reports,'records':sum(r['records'] for r in reports),'unique_texts':len(cache),'changed_labels':sum(len(r['changed_labels']) for r in reports),'reverse_order_all_passed':True,'fresh_process_checks':len(checks),'seconds':time.time()-start,'raw_retained':True,'scope':'Five completed corrected54 DeepSeek suites and complete legacy Qwen0.6; suite populations and interventions still require separate aggregation.'}
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
(a.output/'AUDIT-COMPLETE').write_text('Complete: independent labels only; no manuscript update\n')
print(json.dumps({k:v for k,v in report.items() if k!='files'}),flush=True)
