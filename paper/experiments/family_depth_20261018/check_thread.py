#!/usr/bin/env python3
"""Five-hour continuation, bounded to 14 days; stop only on complete/expiry."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent

def main():
    cfg=json.loads((HERE/'thread-check.json').read_text())
    now=dt.datetime.now(dt.timezone.utc)
    expired=now>=dt.datetime.fromisoformat(cfg['expires_at'])
    complete=(HERE/'TASK-COMPLETE').exists()
    if '--check' in sys.argv:
        print(json.dumps(cfg|{'expired':expired,'complete':complete}));return
    if expired or complete:
        subprocess.run(['systemctl','--user','stop',cfg['timer']],check=True);return
    message=('五小时周期检查：继续本对话已授权的Figure3跨模型家族补跑。先读paper/HANDOFF.md顶部及'
       'paper/experiments/family_depth_20261018/README.md、deployment.json，核对进程、Job、日志和done，避免重复实验。'
       '最新固定最多8卡。以parallel-plan.json和launch-state.json为准，每模型任务两个整skill分片；旧无-s四个整池Job已停止不恢复。全部正式单元实际开始后单独通知用户，不把排队当开始。范围含Llama/DeepSeek及已有模型缺失正文单元。'
       '若权重下载仍未获用户明确确认，不下载，记录阻碍；已有确认持续有效。'
       'Figure3启动后同一批模型继续覆盖正文4.2内容/位置/跨题控制、4.3重复注入窗口、4.4 S/C/SC/recut与路径切断，两任务均覆盖；详见README矩阵，不要仅完成Figure3就标完成。'
       '结果齐后核验完整层网格、基线筛选、身份控制和截断，更新Figure3及相关表、方法/样本/正文/摘要结论中受影响文字，'
       '反例仅记研究记录，按用户最新要求暂不进paper；如实保留空样本与证据边界，不预设新模型符合旧结论。全部正文、附录、图表及对应说明不展示或讨论置信区间、置信度、误差条，Table2也不例外。'
       '先完成新旧全部TheoremQA逐题隔离重判、各suite独立基线与eligible重建，必要补齐新增样本所有干预；原始JSONL保留。重复注入仅作一致性检查。'
       'Intro首段仅对齐Semantics and Knowledge的机器可读skill/工具说明，实验不按track改写。'
       '每次论文更新先在关联目录运行olcli diff审阅完整行级差异，纳入云端合理修改；本地修改并编译审计后，上传前再次diff，同步Overleaf和GitHub，不再导出桌面，保留旧交付。'
       '整项完成后只commit本次文件并push master，不碰howskill/data/cells.json.tmp；随后创建本目录TASK-COMPLETE停止此timer。'
       '更新HANDOFF记录下一步及实验资源收尾。删除及大下载确认要求继续适用，不为额度无限重试。')
    r=subprocess.run([cfg['codex'],'queue','--thread',cfg['thread'],'--message',message],
                     cwd=HERE.parents[1],capture_output=True,text=True,timeout=60)
    with (HERE/'thread-check-log.jsonl').open('a') as fh:
        fh.write(json.dumps({'time':now.isoformat(),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})+'\n')
    r.check_returncode()

if __name__=='__main__':main()
