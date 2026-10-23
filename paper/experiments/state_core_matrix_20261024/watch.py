"""Three-hour scoped supervision; errors in observation are not GPU failures."""
import argparse,datetime,fcntl,json,subprocess,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def call(args,timeout=150):
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError((r.stdout+r.stderr)[-1600:])
    return r.stdout

def main():
    p=argparse.ArgumentParser();p.add_argument('--no-notify',action='store_true');a=p.parse_args();cfg=json.loads((ROOT/'watch-config.json').read_text())
    if (ROOT/'SUPERVISION-CANCELLED').exists():return
    with (ROOT/'watch.lock').open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        if (ROOT/'SUPERVISION-COMPLETE').exists():return
        state={'checked_at':datetime.datetime.now().astimezone().isoformat(),'scope':'seven new core24 cells; q8-medcalc reused','supervision_expired':time.time()>=cfg['expires_at']}
        launch=json.loads((ROOT/'launch-state.json').read_text());state['launch_status']=launch['status']
        try:
            names=launch.get('submitted',[])
            if names:
                result=json.loads(call([cfg['inspire'],'--account','me','--json','job','status',*names,'--workspace','可上网GPU资源']))
                assert result['success'] and not result['data'].get('unresolved');data=result['data'];items=data.get('items',[data]);state['statuses']={x['name']:x['status'] for x in items}
            if cfg.get('observer_mode')=='platform_logs' and names:
                keys={j['name']:j['cell'] for j in json.loads((ROOT/'jobs.json').read_text())['jobs']}
                def read_log(name):
                    text=call([cfg['inspire'],'--account','me','job','logs',name,'--workspace','可上网GPU资源','--tail','20','--limit','50'])
                    v={};cell=keys[name]
                    for line in text.splitlines():
                        marker='AUDIT_SUMMARY '
                        if marker in line:
                            audit=json.JSONDecoder().raw_decode(line.split(marker,1)[1])[0]
                            assert audit['cell']==cell and audit['independent_audit_passed']
                            target=ROOT/'retrieved';target.mkdir(exist_ok=True);(target/(cell+'.audit.json')).write_text(json.dumps(audit,indent=2)+'\n')
                            v.update(audit=audit,core_verified=True,gate_verified=True)
                        elif '{' in line:
                            try:
                                progress=json.JSONDecoder().raw_decode(line[line.index('{'):])[0]
                                if progress.get('cell')==cell and 'phase' in progress:v[progress['phase']]=progress
                            except (ValueError,AttributeError):pass
                    old=ROOT/'retrieved'/(cell+'.audit.json')
                    if old.exists() and 'audit' not in v:v.update(audit=json.loads(old.read_text()),core_verified=True,gate_verified=True)
                    if state.get('statuses',{}).get(name)=='FAILED':v['failure']='Job FAILED; inspect platform logs before any retry.'
                    return cell,v
                with ThreadPoolExecutor(max_workers=3) as pool:cells=dict(pool.map(read_log,names))
                state['observed']={'cells':cells,'channel':'platform job logs; independent audit summaries, no Notebook dependency'}
            elif cfg.get('observer_ssh_config'):
                raw=call(['ssh','-F',cfg['observer_ssh_config'],'-o','BatchMode=yes','-o','ConnectTimeout=20',cfg['observer_ssh_host'],cfg['remote_python']+' '+cfg['remote_root']+'/observe_remote.py'])
                obs=json.loads(next(x[4:] for x in raw.splitlines() if x.startswith('OBS ')));state['observed']=obs
            else:state['observation_error']='Preparation/observation channel not configured yet; do not classify as GPU failure.'
        except Exception as e:state['observation_error']=str(e)
        cells=state.get('observed',{}).get('cells',{});complete=len(cells)==7 and all(v.get('core_verified') and v.get('gate_verified') and v.get('audit',{}).get('independent_audit_passed') and not v.get('failure') for v in cells.values()) and all(v=='SUCCEEDED' for v in state.get('statuses',{}).values());state['all_cells_independently_audited']=complete
        (ROOT/'monitor-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
        with (ROOT/'monitor-history.jsonl').open('a') as out:out.write(json.dumps(state,ensure_ascii=False)+'\n')
        if not a.no_notify:
            msg='核心24条件跨模型实验三小时检查：'+json.dumps(state,ensure_ascii=False)+'。先读paper/experiments/state_core_matrix_20261024/HANDOFF.md、launch-state.json、monitor-state.json与watch-config.json，仅监督本轮七组合24条件。Qwen/MedCalc旧实验已完成并复用，不重跑；旧depth①、LogicBench和其他family任务不得恢复或操作。若提交状态不明先核对同名平台任务，不重复提交。CPU观察错误不是GPU失败，仅修复本轮观察通道。不得自动改论文或Overleaf。每cell已由worker先gate后正式并执行独立进程审计，完成后取回小audit和二值标签，核查所有键/身份/缓存覆盖/截断/统计与整矩阵差异，更新交接。若监督到期明确报告未完成部分。若本轮尚在准备且无GPU提交，继续已授权准备与提交，不虚报运行。若已完成标记存在仅去重，不恢复旧任务。'
            call([cfg['codex'],'queue','--thread',cfg['thread'],'--message',msg],timeout=60)
        if complete or state['supervision_expired']:
            if complete:(ROOT/'SUPERVISION-COMPLETE').write_text(state['checked_at']+'\n')
            call(['systemctl','--user','stop',cfg['timer']],timeout=20)
        print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
