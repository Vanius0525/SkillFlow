#!/usr/bin/env python3
"""Bounded 30-minute supervision; notify on faults, launch one ready KO job."""
import datetime as dt,fcntl,json,shlex,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT='/inspire/ssd/project/project-public/czxs253130660/family-depth-20261018-v1'
INSPIRE='/home/vanius/.local/bin/inspire';STATE=HERE/'watch-progress-state.json'
NAMES=['wt-fix-ds-tqa-battery-1019','wt-fix-ds-tqa-battery-l2-1019','wt-fix-ds-tqa-windows-1019','wt-fix-ds-tqa-mechanism-1019','wt-legacy-q8-tqa-1019','wt-legacy-q06-tqa-1019','wt-legacy-mistral-tqa-1019']
RECOVERY_ROOT='/inspire/hdd/project/project-public/czxs253130660/family-depth-recovery-20261019'
NAMES=[n for n in NAMES if n not in ['wt-fix-ds-tqa-mechanism-1019','wt-legacy-q8-tqa-1019','wt-legacy-mistral-tqa-1019']]+['wt-recover-q8-tqa-hdd-1019','wt-recover-mistral-tqa-hdd-1019','wt-recover-q8-ko-hdd-1019','wt-recover-ds-edges-hdd-1019']
PAR='wt-legacy-q8-ko-par-1019'
def call(args,timeout=60):
 r=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-1600:])
 return r.stdout
def remote(code):
 return call([INSPIRE,'notebook','exec','wt-family-prep-1018','--workspace','CPU资源空间','python -c '+shlex.quote(code),'--timeout','40'])
def main():
 with (HERE/'watch-progress.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  cfg=json.loads((HERE/'thread-check.json').read_text());now=dt.datetime.now(dt.timezone.utc)
  if now>=dt.datetime.fromisoformat(cfg['expires_at']) or (HERE/'TASK-COMPLETE').exists():
   subprocess.run(['systemctl','--user','stop','family-depth-watch-01a15016.timer'],check=True);return
  state=json.loads(STATE.read_text()) if STATE.exists() else {'notified':[]}
  def save():STATE.write_text(json.dumps(state,indent=2)+'\n')
  def notify(key,message):
   if key in state['notified']:return
   call([cfg['codex'],'queue','--thread',cfg['thread'],'--message','实验监督触发：'+message+'。先读paper/HANDOFF.md最新入口，自动诊断续接，不重复生成已完成结果。'],60)
   state['notified'].append(key);save()
  state['checked_at']=now.isoformat();save()
  try:
   names=NAMES+([PAR] if state.get('parallel_attempted') else [])
   status=json.loads(call([INSPIRE,'--json','job','status',*names,'--workspace','可上网GPU资源']))
   items=status['data']['items'];state['statuses']={x['name']:x['status'] for x in items}
   code="""import json,time
from pathlib import Path
p=Path(ROOT);d=p/'legacy-replay-20261019'
h=Path('/inspire/hdd/project/project-public/czxs253130660/family-depth-recovery-20261019')
paths=list(p.glob('deepseek-theoremqa-corrected54*.jsonl'))+list(d.glob('*.answers.jsonl'))+list(h.glob('*.jsonl'))
print('WATCH '+json.dumps({'first_done':(d/'q8-transfer-00.done.json').exists(),'ko_started':(d/'q8-knockout.answers.jsonl').exists(),'ko_done':(d/'q8-knockout.done.json').exists(),'legacy_done':[x.name for x in d.glob('*-replay.done.json')],'recovery_done':[x.name for x in h.glob('*.done.json')],'files':{str(x):{'bytes':x.stat().st_size,'mtime':x.stat().st_mtime} for x in paths},'time':time.time()}))
""".replace('Path(ROOT)','Path('+repr(ROOT)+')')
   output=remote(code);seen=json.loads(next(x.split(' ',1)[1] for x in output.splitlines() if x.startswith('WATCH ')));state['observed']=seen;save()
   for name,status in state['statuses'].items():
    if any(k in status.lower() for k in ['fail','error','cancel']):notify('failure:'+name+':'+status,name+'出现'+status+'；检查watch-progress-state.json和日志')
   previous=state.get('last_sizes',{});sizes={k:v['bytes'] for k,v in seen['files'].items()};state['last_sizes']=sizes
   if sizes!=previous:state['last_progress_at']=time.time()
   elif state['statuses'] and any(x=='job_running' for x in state['statuses'].values()) and time.time()-state.get('last_progress_at',time.time())>7200:notify('stale:'+str(int(time.time()//7200)),'正式输出整体超过2小时无增长，请核对生成、捕获与平台状态')
   active=sum(x in ['job_running','job_creating','job_queuing','job_pending'] for x in state['statuses'].values())
   if seen['first_done'] and not seen['ko_started'] and not state.get('parallel_attempted') and active<8 and state['statuses'].get('wt-legacy-q8-tqa-1019')=='job_running':
    state['parallel_attempted']=True;save() # Never blindly retry an uncertain submission.
    remote("from pathlib import Path;import json;p=Path("+repr(ROOT+'/legacy-replay-20261019/q8-knockout.parallel-owner.json')+");assert not p.exists();p.write_text(json.dumps({'job':"+repr(PAR)+",'protocol':'canonical KO output, validated checkpoint reuse by original worker'}))")
    job=json.loads((HERE/'q8-knockout-parallel-job.json').read_text())['jobs'][0]
    plan_path=HERE/'parallel-plan.json';plan=json.loads(plan_path.read_text());assert PAR not in plan['readiness']
    plan['jobs'].append(job);plan['readiness'][PAR]={'kind':'followup','model':'q8','task':'theoremqa','suite':'legacy-ko-parallel','old_model':True,'screen':'backfill-q8-theoremqa.screen.json','prefix':ROOT+'/legacy-replay-20261019/q8','done':'legacy-replay-20261019/q8-knockout.done.json'};plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    launch_path=HERE/'launch-state.json';launch=json.loads(launch_path.read_text());launch['attempted'].append(PAR);launch_path.write_text(json.dumps(launch,indent=2)+'\n')
    response=call([INSPIRE,'job','batch',str(HERE/'q8-knockout-parallel-job.json')],120)
    state['parallel_submitted']=True;state['parallel_submission_response']=response;save()
    launch=json.loads(launch_path.read_text());launch['submitted'].append(PAR);launch_path.write_text(json.dumps(launch,indent=2)+'\n')
    notify('parallel-started','Qwen8完整首批基线已完成，KO独立单卡已提交；总活跃任务不超过8，原worker将验证复用同一KO完成产物')
   state.pop('last_error',None);save()
  except Exception as e:
   state['last_error']=str(e);save();notify('monitor-error:'+type(e).__name__,'监督脚本遇到'+type(e).__name__+'，细节见watch-progress-state.json；不能盲目重试提交')
if __name__=='__main__':main()
