"""Replay original whitebox protocols; retain every full answer and generated token.
Candidate IDs are frozen from all historical depth records, before regrading.
"""
import argparse,copy,hashlib,importlib,inspect,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--module',required=True);p.add_argument('--expected',required=True);p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args();args=a.args[1:] if a.args[:1]==['--'] else a.args
sys.path.insert(0,str(Path(a.repo)/'howskill'))
from howskill import wb_diffvec,sra_eval
import latex2sympy2 as parser
initial={k:copy.deepcopy(getattr(parser,k)) for k in ('var','variances','VARIABLE_VALUES','frac_type','is_real')}
out=Path(args[args.index('--out')+1]);raw=out.with_suffix('.answers.jsonl')
if out.exists() and raw.exists() and out.with_suffix('.done.json').exists():
 cached=json.loads(out.with_suffix('.replay-manifest.json').read_text());done=json.loads(out.with_suffix('.done.json').read_text())
 assert cached['args']==args and cached['expected_sha256']==hashlib.sha256(Path(a.expected).read_bytes()).hexdigest(),'Checkpoint protocol mismatch'
 assert done['records']==len(out.read_text().splitlines()) and done['answers']==len(raw.read_text().splitlines()),'Checkpoint record-count mismatch'
 if 'raw_sha256' in done:assert done['raw_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest()
 module_path=Path(a.repo)/'howskill/howskill'/(''+a.module+'.py')
 assert cached['module_sha256']==hashlib.sha256(module_path.read_bytes()).hexdigest(),'Checkpoint module mismatch'
 print('CHECKPOINT_REUSED '+str(out),flush=True);sys.exit(0)
if raw.exists() and not out.with_suffix('.done.json').exists() and a.module=='wb_knockout':
 # An independently submitted KO worker may own this exact output. Wait only
 # when a declared parallel marker exists, then validate its completed output.
 parallel=out.with_suffix('.parallel-owner.json')
 if parallel.exists():
  import time,os
  deadline=time.monotonic()+24*3600
  while time.monotonic()<deadline and not out.with_suffix('.done.json').exists():time.sleep(60)
  if out.with_suffix('.done.json').exists():os.execv(sys.executable,[sys.executable,__file__,*sys.argv[1:]])
  raise RuntimeError('Parallel KO did not complete within bounded wait; inspect owner Job')
assert not out.exists() and not raw.exists(),'Fresh paths required; inspect partial output rather than restarting'

last={};original_init=wb_diffvec.VecScorer.__init__
def init(self,*x,**kw):
 original_init(self,*x,**kw);original_decode=self.tok.decode
 def decode(tokens,*da,**dkw):
  text=original_decode(tokens,*da,**dkw)
  values=tokens.tolist() if hasattr(tokens,'tolist') else list(tokens)
  if values and isinstance(values[0],int):
   last.clear();last.update(token_ids=values,truncated=len(values)>=int(args[args.index('--max-new')+1]),prefix400=original_decode(values[:400],skip_special_tokens=True))
  return text
 self.tok.decode=decode
wb_diffvec.VecScorer.__init__=init
count=0
fh=raw.open('x',buffering=1)
def grade(text,instance,task_mode):
 global count
 for k,v in initial.items():setattr(parser,k,copy.deepcopy(v))
 result=sra_eval.evaluate(text,instance)
 frame=inspect.currentframe().f_back;local=frame.f_locals
 record={'instance_id':instance['instance_id'],'seq':count,'text':text,'correct':bool(result['correct']),'caller_line':frame.f_lineno,'caller':frame.f_code.co_filename,'arm_local':local.get('arm'),'layer_local':local.get('L'),**last}
 for k,v in initial.items():setattr(parser,k,copy.deepcopy(v))
 record['correct_prefix400']=bool(sra_eval.evaluate(record['prefix400'],instance)['correct'])
 fh.write(json.dumps(record,ensure_ascii=False)+'\n');count+=1;return bool(result['correct'])
wb_diffvec.graded=grade
module=importlib.import_module('howskill.'+a.module)
# Baseline-only admission, never selection on an intervention outcome.
# Current processes retain v1 in memory; this applies at the next layer block.
optimization={'admission_helper_sha256':hashlib.sha256((Path(__file__).parent/'baseline_admission.py').read_bytes()).hexdigest(),'version':'baseline-admission-v2','baseline_screen_applied':False,'identity_policy':'original first block; global final layer thereafter'}
first=out.parent/(out.name.split('-')[0]+'-transfer-00.jsonl')
if '--baselines' not in args and first.with_suffix('.done.json').exists():
 baseline=[json.loads(line) for line in first.read_text().splitlines()]
 assert baseline and all(all(k in r for k in ['ok_gold_in_context','ok_receiver','ok_none']) for r in baseline)
 from baseline_admission import admitted_ids
 eligible=admitted_ids(baseline)
 original_pick=module.pick_instances
 def pick(*pa,**pk):
  selected=original_pick(*pa,**pk)
  return [row for row in selected if row[2] in eligible]
 module.pick_instances=pick
 optimization.update(baseline_screen_applied=True,baseline_sha256=hashlib.sha256(first.read_bytes()).hexdigest(),eligible_ids=sorted(eligible),original_candidates=len(baseline))
 assert eligible,'No baseline-eligible items: inspect and emit an explicit empty-population result instead'
 if a.module=='wb_spanvec':
  original_make=module.make_donor
  def make(arm,*ma,**mk):
   caller=inspect.currentframe().f_back.f_locals
   if arm=='self' and caller['L'] not in [0,caller['sc'].model.config.num_hidden_layers-1]:return None
   return original_make(arm,*ma,**mk)
  module.make_donor=make
if a.module=='wb_knockout':
 # The first two own-protocol baselines are still generated for every admitted
 # item. No expensive KO curve is needed if that item is not donor-rescued.
 source=Path(module.__file__).read_text()
 old='            if a.sweep in ("layers", "both"):\n'
 new='            if a.sweep in ("layers", "both") and (a.no_baselines or (rec.get("ok_with") and not rec.get("ok_without"))):\n'
 assert source.count(old)==1
 optimized_source=source.replace(old,new)
 optimization['knockout_source_sha256']=hashlib.sha256(optimized_source.encode()).hexdigest()
 # Re-execution imports the patched grader. Reapply the admission hook below.
 exec(compile(optimized_source,module.__file__,'exec'),module.__dict__)
 if optimization['baseline_screen_applied']:module.pick_instances=pick
expected=json.loads(Path(a.expected).read_text())
if a.module=='wb_spanvec':
 original_build=module.build_item
 def build(sc,inst,*x,**kw):
  b=original_build(sc,inst,*x,**kw)
  if b is not None:
   e=expected[inst['instance_id']]
   assert (int(b['ids_g'].shape[1]),len(b['pos']),b['doc_start'])==(e['n_prompt'],e['n_patched'],e['doc_start']),('Historical prompt/span mismatch',inst['instance_id'])
  return b
 module.build_item=build
meta={'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'module_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),'args':args,'expected_sha256':hashlib.sha256(Path(a.expected).read_bytes()).hexdigest(),'grading':'official, fresh parser globals per answer; retain raw text/tokens; prefix400 diagnostic','optimization':optimization}
out.with_suffix('.replay-manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
module.main(args);fh.close();out.with_suffix('.done.json').write_text(json.dumps({'answers':count,'records':len(out.read_text().splitlines()),'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest()})+'\n')
