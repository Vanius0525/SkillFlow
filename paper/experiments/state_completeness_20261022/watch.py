"""Hourly observation and current-conversation notification for this run only."""
import argparse
import datetime as dt
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parent
INSPIRE = '/home/vanius/.local/bin/inspire'


def call(args, timeout=120):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr)[-1800:])
    return r.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-notify', action='store_true')
    args = parser.parse_args()
    cfg = json.loads((HERE/'watch-config.json').read_text())
    if (HERE/'SUPERVISION-CANCELLED').exists():
        return
    with (HERE/'watch.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('CHECK_ALREADY_RUNNING')
            return
        if (HERE/'SUPERVISION-COMPLETE').exists():
            call(['systemctl','--user','stop',cfg['timer']])
            return
        state = {'checked_at': dt.datetime.now().astimezone().isoformat()}
        expired = time.time() >= cfg['expires_at']
        try:
            launch = json.loads((HERE/'launch-state.json').read_text())
            state['launch_status'] = launch['status']
            names = launch['submitted']
            statuses = json.loads(call([INSPIRE,'--account','me','--json','job','status',
                                        *names,'--workspace','可上网GPU资源']))
            assert statuses['success'] and not statuses['data'].get('unresolved')
            items = statuses['data'].get('items')
            if items is None:
                items = [statuses['data']]
            state['statuses'] = {x['name']:x['status'] for x in items}
            code = '''from pathlib import Path
import json,hashlib
r=Path('/inspire/ssd/project/project-public/czxs253130660/state-completeness-20261022-v2/outputs')
labels=['gate-0-of-1','repair-0-of-2','repair-1-of-2']
d={'progress':{},'verified':{},'failed':{},'raw':{}}
for label in labels:
 p=r/(label+'.progress.json'); f=r/(label+'.failed.json'); done=r/(label+'.done.json'); raw=r/(label+'.jsonl.gz')
 if p.exists(): d['progress'][label]=json.loads(p.read_text())
 if f.exists(): d['failed'][label]=json.loads(f.read_text())
 if raw.exists(): d['raw'][label]={'bytes':raw.stat().st_size,'mtime':raw.stat().st_mtime}
 if done.exists():
  x=json.loads(done.read_text()); expected=14 if label.startswith('gate') else 3038
  sha=hashlib.sha256()
  with raw.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1048576),b''): sha.update(chunk)
  d['verified'][label]=bool(x['records']==expected and sha.hexdigest()==x['raw_sha256'])
print('OBS '+json.dumps(d))
'''
            observer_pick = ['--pick',str(cfg['observer_pick'])] if cfg.get('observer_pick') else []
            if cfg.get('observer_ssh_config'):
                raw = call(['ssh','-F',cfg['observer_ssh_config'],'-o','BatchMode=yes',
                            '-o','ConnectTimeout=20',cfg['observer_ssh_host'],
                            'python -c '+shlex.quote(code)])
            else:
                raw = call([INSPIRE,'--account','me','notebook','exec',cfg.get('observer','wt-family-prep-1018'),
                            *observer_pick,
                            '--workspace','CPU资源空间','--timeout','90','python -c '+shlex.quote(code)])
            state['observed'] = json.loads(next(x[4:] for x in raw.splitlines() if x.startswith('OBS ')))
        except Exception as exc:
            state['error'] = str(exc)
        formal = ('repair-0-of-2','repair-1-of-2')
        verified = state.get('observed',{}).get('verified',{})
        complete = all(verified.get(k,False) for k in formal)
        state.update(generation_complete_verified=complete, supervision_expired=expired)
        (HERE/'monitor-state.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
        with (HERE/'monitor-history.jsonl').open('a') as f:
            f.write(json.dumps(state,ensure_ascii=False)+'\n')
        if not args.no_notify:
            message = ('状态完整性实验小时检查：'+json.dumps(state,ensure_ascii=False)+
                '。先读paper/experiments/state_completeness_20261022/HANDOFF.md、launch-state.json与monitor-state.json；'
                '仅监督本轮Qwen/MedCalc状态完整性实验，报告真实进度/故障。不要操作其他对话的LogicBench或family实验，'
                '实验①全层depth已由用户取消，不恢复或重提任何depth任务；只保留两份repair分片和gate。'
                '不重复提交或重跑已有记录，不改论文或Overleaf。调度器已负责gate通过后的剩余任务提交；'
                '若控制器失败，先查状态与已提交名称再处理。观察CPU以watch-config.json的observer为准；'
                '若观察CPU停止，恢复观察通道，不把观察错误当GPU失败。'
                '生成全完成后做独立进程重判、完整键集合/身份/缓存写入/截断及统计审计，取回小摘要、更新交接。'
                '若监督到期须明确报告，不静默称实验完成。迟到重复消息先核对本地状态，不恢复已停止的旧任务。')
            call([cfg['codex'],'queue','--thread',cfg['thread'],'--message',message])
        if complete or expired:
            if complete:
                (HERE/'SUPERVISION-COMPLETE').write_text(state['checked_at']+'\n')
            call(['systemctl','--user','stop',cfg['timer']])
        print(json.dumps(state,ensure_ascii=False))


if __name__ == '__main__':
    main()
