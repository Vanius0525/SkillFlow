"""Bounded hourly observation of this LogicBench baseline run only."""
import datetime as dt
import argparse
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
INSPIRE = '/home/vanius/.local/bin/inspire'


def call(argv):
    r = subprocess.run(argv, text=True, capture_output=True, timeout=60)
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr)[-1200:])
    return r.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=HERE/'watch-config.json')
    parser.add_argument('--no-notify', action='store_true')
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    cancelled = HERE/cfg.get('cancel_marker', 'SUPERVISION-CANCELLED')
    complete = HERE/cfg.get('complete_marker', 'SUPERVISION-COMPLETE')
    if cfg.get('cancelled_at') or cancelled.exists():
        print('SUPERVISION_CANCELLED_BY_USER')
        return
    with (HERE/'watch.lock').open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if time.time() >= cfg['expires_at'] or complete.exists():
            call(['systemctl', '--user', 'stop', cfg['timer']])
            return
        state = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            names = cfg.get('active_names') or [j['name'] for j in json.loads((HERE/'jobs.json').read_text())['jobs']]
            d = json.loads(call([INSPIRE, '--json', 'job', 'status', *names,
                                 '--workspace', '可上网GPU资源']))
            assert d['success'] and not d['data'].get('unresolved')
            state['statuses'] = {x['name']: x['status'] for x in d['data']['items']}
            code = '''import pathlib,json,hashlib
p=pathlib.Path('/inspire/hdd/project/project-public/czxs253130660/logicbench-20261021-v1/outputs')
progress={f.stem:json.loads(f.read_text()) for f in p.glob('*.progress.json')}
summary={}
for f in p.glob('*.summary.json'):
 d=json.loads(f.read_text());summary[f.stem]={k:d[k] for k in ('complete','records','all','paired','common_n','groups')}
verified={}
for key in ('q8','mistral','llama','deepseek'):
 f=p/(key+'.done.json')
 if not f.exists(): continue
 done=json.loads(f.read_text());s=json.loads((p/(key+'.summary.json')).read_text())
 sha=hashlib.sha256((p/(key+'.jsonl')).read_bytes()).hexdigest()
 verified[key]=bool(s['complete'] and s['records']==done['records']==2240 and s['raw_sha256']==done['sha256']==sha)
print('OBS '+json.dumps({'progress':progress,'summary':summary,'verified':verified,'done':[f.stem for f in p.glob('*.done.json')],'sizes':{f.name:f.stat().st_size for f in p.glob('*.jsonl')}}))
'''
            raw = call([INSPIRE, 'notebook', 'exec', 'wt-family-prep-1018', '--workspace', 'CPU资源空间',
                        'python -c '+shlex.quote(code), '--timeout', '40'])
            state['observed'] = json.loads(next(line[4:] for line in raw.splitlines() if line.startswith('OBS ')))
        except Exception as e:
            state['error'] = str(e)
        (HERE/'monitor-state.json').write_text(json.dumps(state, indent=2, ensure_ascii=False)+'\n')
        with (HERE/'monitor-history.jsonl').open('a') as f:
            f.write(json.dumps(state, ensure_ascii=False)+'\n')
        if not args.no_notify:
            message = ('LogicBench小时监督 '+state['checked_at']+'：'+json.dumps(state, ensure_ascii=False)+
                       '。先读取paper/experiments/logicbench_20261021/HANDOFF.md与monitor-state.json；'
                       '只检查本轮四模型基线、报告实际进度及结果，不操作其他实验、不修改论文。'
                       '若此消息已过期或本轮已完成则忽略；不要重复提交或重跑已有记录。'
                       '全部完成后核验summary/raw/done并取回小型摘要，记录交接并停止本轮监督。')
            call([cfg['codex'], 'queue', '--thread', cfg['thread'], '--message', message])
        verified = state.get('observed', {}).get('verified', {})
        if len(verified) == 4 and all(verified.values()):
            complete.write_text(state['checked_at']+'\n')
            call(['systemctl', '--user', 'stop', cfg['timer']])


if __name__ == '__main__':
    main()
