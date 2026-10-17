#!/usr/bin/env python3
"""Finite milestone watcher; never starts or retries GPU experiments."""
import datetime as dt
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REMOTE = '/inspire/ssd/project/project-public/czxs253130660/mechanism-20261017-v1'


def main():
    cfg = json.loads((HERE.parent/'mechanism_20261016/thread-check.json').read_text())
    inspire = shutil.which('inspire') or '/home/vanius/.local/bin/inspire'
    expiry = dt.datetime.fromisoformat(cfg['expires_at'])
    statepath = HERE/'watch-state.json'
    state = json.loads(statepath.read_text()) if statepath.exists() else {'notified':[]}
    failures = 0
    while dt.datetime.now(dt.timezone.utc) < expiry:
        if (HERE.parent/'mechanism_20261016/PAPER-TASK-COMPLETE').exists():
            return
        code = ('import pathlib,json; p=pathlib.Path('+repr(REMOTE)+'); '
                'print(json.dumps({"status":json.loads((p/"pipeline-status.json").read_text()),'
                '"bridge14":(p/"bridge14-eager.done.json").exists(),'
                '"repair_ready":all((p/"parallel"/("repair-s4-"+str(s)+".done.json")).exists() for s in range(4)),'
                '"workers":[json.loads(f.read_text()) for f in sorted((p/"parallel").glob("worker-*.status.json"))],'
                '"done":(p/"pipeline.done.json").exists(),'
                '"failed":json.loads((p/"pipeline.failed.json").read_text()) if (p/"pipeline.failed.json").exists() else None}))')
        try:
            r = subprocess.run([inspire,'--account','me','notebook','exec',
                'wt-mechanism-4090-1017','--workspace','可上网GPU资源','--timeout','40',
                'python -c '+shlex.quote(code)],capture_output=True,text=True,timeout=65)
            r.check_returncode()
            lines = [x for x in r.stdout.splitlines() if x.startswith('{')]
            observed = json.loads(lines[-1])
            failures = 0
        except Exception as exc:
            failures += 1
            observed = {'error':str(exc),'consecutive_failures':failures}
        with (HERE/'watch-observations.jsonl').open('a') as fh:
            fh.write(json.dumps(dict(time=dt.datetime.now(dt.timezone.utc).isoformat(),**observed))+'\n')
        milestone = ('failed' if observed.get('failed') else 'done' if observed.get('done')
                     else 'repair_ready' if observed.get('repair_ready') and 'repair_ready' not in state['notified']
                     else 'bridge14' if observed.get('bridge14') else 'monitor_failed' if failures>=3 else None)
        if milestone and milestone not in state['notified']:
            message = ('实验里程碑自动续接：'+milestone+'。读取paper/HANDOFF.md最新入口及'
                       'experiments/mechanism_20261017/watch-observations.jsonl；'
                       '核验远端完成标记、取回完整JSONL和manifest后审计。'
                       'bridge14完成时先分析协议漂移，正式repair已改为四张4090的固定题目分片，勿重复启动或恢复旧串行pipeline。'
                       'repair_ready时下载parallel/repair-s4-{0,1,2,3}的JSONL/done/manifest，全部齐后用支持多输入的analyze.py生成正文热力图；edges随后自动运行。'
                       '修复结果使用按skill重采样的不确定性，'
                       '新增推理只做Qwen3-8B+MedCalc。把真实图表替换到正文预留面板，未完成面板继续明确待填；'
                       '同步更新实验结果、方法与样本分母、图注、摘要、引言贡献、结论及相关附录。'
                       '两版PDF编译、数值审计与Overleaf ZIP验证后导出到桌面新的干净版本目录，保留旧审阅快照。'
                       '整个任务完成后commit/push、更新HANDOFF并创建PAPER-TASK-COMPLETE停止检查。'
                       '失败则诊断修复并保留原产物；不自动重复下载或删除数据。')
            r = subprocess.run([cfg['codex'],'queue','--thread',cfg['thread'],
                '--message',message],cwd=ROOT,capture_output=True,text=True,timeout=60)
            r.check_returncode()
            state['notified'].append(milestone)
            state['last_queue_stdout'] = r.stdout
            statepath.write_text(json.dumps(state,indent=2)+'\n')
        if observed.get('done') or observed.get('failed') or failures>=3:
            return
        time.sleep(300)


if __name__ == '__main__':
    main()
