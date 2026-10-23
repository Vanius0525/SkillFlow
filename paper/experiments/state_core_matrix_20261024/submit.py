"""Submit uniquely named cells once; ambiguous errors require platform reconciliation."""
import argparse,json,subprocess,time
from plan import ROOT,save
INSPIRE='/home/vanius/.local/bin/inspire'
p=argparse.ArgumentParser();p.add_argument('--only');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
statepath=ROOT/'launch-state.json';state=json.loads(statepath.read_text());jobs=json.loads((ROOT/'jobs.json').read_text())['jobs']
if state.get('in_flight_submission'):raise RuntimeError('Unresolved in-flight submission; inspect platform before retry.')
def call(args):
 r=subprocess.run([INSPIRE,'--account','me',*args],capture_output=True,text=True,timeout=240)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-2200:])
 return r.stdout
for j in jobs:
 if a.only and j['cell']!=a.only:continue
 if j['name'] in state.get('submitted',[]):continue
 existing=json.loads(call(['--json','job','list','--workspace',j['workspace'],'--keyword',j['name'],'--all']))
 assert existing['success']
 exact=[x for x in existing['data']['items'] if x['name']==j['name']]
 if exact:raise RuntimeError('Existing name requires reconciliation: '+j['name'])
 args=['job','create','--name',j['name']]
 for k in ('workspace','project','group','quota','image','priority','shm_size','max_time','command'):args+=['--'+k.replace('_','-'),str(j[k])]
 for k,v in j['env'].items():args+=['--env',k+'='+v]
 if a.dry_run:
  response=call(args+['--dry-run']);(ROOT/'dry-run.txt').write_text(response);print('DRY_RUN_OK',j['name']);break
 state.update(status='submitting_core24',in_flight_submission=j['name'],checked_at=time.time());save(statepath,state)
 try:result=call(args)
 except Exception as e:
  state.update(status='submission_ambiguous_check_live_before_retry',error=str(e));save(statepath,state);raise
 state.setdefault('submitted',[]).append(j['name']);state.pop('in_flight_submission',None);state['last_create_output']=result.strip();save(statepath,state);print('SUBMITTED',j['name'],flush=True)
state['status']='all_seven_core24_jobs_submitted_not_completion' if len(state['submitted'])==7 else 'partial_submission_waiting_bootstrap_check';save(statepath,state)
