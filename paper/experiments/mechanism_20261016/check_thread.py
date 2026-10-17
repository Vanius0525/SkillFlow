#!/usr/bin/env python3
"""Send a bounded four-hour progress check to the original Codex thread."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name('thread-check.json')


def main():
    cfg = json.loads(CONFIG.read_text())
    now = dt.datetime.now(dt.timezone.utc)
    expired = now >= dt.datetime.fromisoformat(cfg['expires_at'])
    if '--check' in sys.argv:
        print(json.dumps(dict(thread=cfg['thread'], expired=expired,
                              expires_at=cfg['expires_at'])))
        return
    if expired or Path(__file__).with_name('PAPER-TASK-COMPLETE').exists():
        subprocess.run(['systemctl', '--user', 'stop', cfg['timer']], check=True)
        return
    prompt = ('四小时周期检查：继续本对话已授权的 paper 任务。先读 paper/HANDOFF.md 最新入口，'
              '核验远端进程、完成标记及原始实验产物，避免重复启动；优先联网区单卡4090和能进入正文的短实验。'
              '新增推理仅限Qwen3-8B+MedCalc。结果齐后核验四个分片的JSONL、done、manifest及身份控制，'
              '生成真实图表并替换正文预留图；同步更新实验结果、方法与分母、图注、摘要、引言贡献、结论及相关附录。'
              '完成两版PDF编译、数值审计与Overleaf打包，向桌面新的干净版本目录导出，保留已有审阅快照。'
              '更新HANDOFF并报告进展。'
              '一天内完成；不为等待额度无限重试。删除及累计超过1GiB下载仍需批准。'
              '整个任务完成后按约定commit/push，并创建experiments/mechanism_20261016/PAPER-TASK-COMPLETE停止检查。')
    result = subprocess.run([cfg['codex'], 'queue', '--thread', cfg['thread'],
                             '--message', prompt], cwd=ROOT, capture_output=True,
                            text=True, timeout=60)
    with Path(__file__).with_name('thread-check-log.jsonl').open('a') as fh:
        fh.write(json.dumps(dict(time=now.isoformat(), returncode=result.returncode,
                                 stdout=result.stdout, stderr=result.stderr))+'\n')
    result.check_returncode()


if __name__ == '__main__':
    main()
