## 2026-10-21 新对话接管：LogicBench运行中，周期检查已取消

- 用户最新要求：更新交接，由新对话接管；取消本对话周期检查。只继续本轮LogicBench，不操作其他实验、不更新论文；不恢复任何旧timer。延迟的旧监督消息一律忽略。
- 当前入口：`experiments/logicbench_20261021/HANDOFF.md`；最新实测状态：`experiments/logicbench_20261021/monitor-state.json`（2026-10-21 17:50 CST）。
- DeepSeek已完成2240条并经独立进程重判；全760题gold 66.32%、none 57.37%，有效89题/15skill。Mistral 2043/2240、Llama 998/2240、Qwen 360/2240，均RUNNING。Llama当前Job为wt-logic-llama-1021-r1，原911条已复用。
- 已停止logicbench-hourly-01a1587f.timer；systemctl --user list-timers --all显示0 timers。SUPERVISION-CANCELLED与watch-config.json.cancelled_at防止误恢复；不因新对话接管自动重建周期检查。GPU Job继续运行，没有停止实验。
- 下一步先查询四个现有Job并读取远端outputs中的progress/summary/done；不要再次提交整池。远端个人HDD：/inspire/hdd/project/project-public/czxs253130660/logicbench-20261021-v1；观察CPU wt-family-prep-1018，保留自动停止设置。CPU不可用时先诊断观察通道，不当作GPU失败。
- 本次交接仅保存代码/数据快照及小摘要，原始输出留远端。仓库另有其他对话/历史稿件改动，不纳入本轮提交、不覆盖。正式深度矩阵尚未启动；先完成四模型基线并核验真实结果。

## 接管所需操作

```bash
inspire --json job status wt-logic-q8-1021 wt-logic-mistral-1021 wt-logic-llama-1021-r1 wt-logic-deepseek-1021 --workspace 可上网GPU资源
inspire notebook status wt-family-prep-1018 --workspace CPU资源空间
inspire job logs wt-logic-llama-1021-r1 --workspace 可上网GPU资源 --tail 20
```

- 代码：本目录baseline.py、engine.py、snapshot/；配置jobs.json为最初四任务，llama-resume-job.json为已提交续跑任务，当前四任务名以watch-config.json.active_names为准。这些配置供核查，不直接batch重提。
- 远端结果在上述HDD目录outputs/{q8,mistral,llama,deepseek}.jsonl；相邻*.progress.json、*.summary.json、*.done.json和*.run.json。done须与summary完整记录数2240和raw SHA256一致。
- Python解释器：/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python。完成后可在CPU用`python /inspire/hdd/project/project-public/czxs253130660/logicbench-20261021-v1/baseline.py --audit /inspire/hdd/project/project-public/czxs253130660/logicbench-20261021-v1/outputs/MODEL.jsonl`重新核验；MODEL替换成具体key。只重判，不重新生成。
- Llama定位修复和兼容版本记录见resume-note.json；初始SHA清单initial-manifest.json，现行manifest.json；720题token跨度回归已通过。续跑只补缺失记录，有独占锁与唯一键检查。
- 已验证DeepSeek摘要deepseek.summary.json；后续只取回小summary/done/hardware/需要的诊断，不搬大raw和权重。新对话先读取inspire skill及平台记忆。
- 用户明确取消监督，watch.py已增加取消标记检查；若仅需手动观察，直接CLI查询，不删取消标记、不恢复timer。实验尚未结束；本次提交仅为交接checkpoint，不代表四模型完成。

## 历史启动状态（2026-10-21 17:37 CST；以下以顶部接管状态为准）

- 原始四Job已成功提交且都实际开始过。DeepSeek SUCCEEDED；Qwen RUNNING 309/2240、Mistral RUNNING 1852/2240；Llama续跑wt-logic-llama-1021-r1 QUEUING，已有911条保留。
- DeepSeek完整2240条唯一键及独立进程逆序重判通过，gold 504/760、none 436/760、receiver 368/720，eligible89题/15skill；gold救回171题、伤害103题。输出截断gold1/receiver1/none0；这是固定评分器结果，不把子集准确率称整体收益。小摘要已取回。
- Llama失败原因：logicbench_00317题末尾一个空格，chat模板trim后原prompt.rindex(user)失败。只修复渲染后user定位，生成prompt不变；720题全部token source-span和前后缀一致性回归通过。修复与版本衔接见resume-note.json、initial-manifest.json和manifest.json，续跑会自动跳过原911条。Qwen/Mistral已加载的代码进程不受磁盘文件更新影响。
- 校验：本地760题正确/错误答案评分与字符跨度检查、py_compile；远端全代码/数据SHA256、torch2.7.0a0/CUDA12.8/Transformers4.57.6。每条输出fsync，独占锁，完成后独立进程重判，再写done。
- 每小时监督：logicbench-hourly-01a1587f.timer，首次18:30 CST；watch.py实测通过，无观察错误。全部四done或watch-config.json过期后自停；CPU观察实例原自动停止约21小时后，必要时先检查状态，不能把观察失败当GPU失败。
- 下一步：核验Llama续跑日志和三个剩余模型完整摘要；全部完成后取回小summary、核验网格/重复键/截断、停止监督，更新交接并按约定提交推送。本轮尚在运行，暂不提交未完成实验。

# LogicBench四模型核验（2026-10-21）

当前目标：先跑LogicBench；不操作其他实验、不更新论文。
数据：760题/19 skills；四模型Qwen3-8B、Mistral-7B-Instruct-v0.3、Llama-3.1-8B-Instruct、deepseek-llm-7b-chat。
本轮：全量gold/no-skill基线；固定logicbench_006作为长度对齐receiver，gold自身为006的40题只测gold/no-skill，不作错skill配对。其余720题三基线。逐题gold正确、receiver和no-skill错误者列入screen；不使用旧标签。
推理：BF16/eager/greedy/full-prefill，max_new=900，Qwen关闭thinking，DeepSeek system合入user；代码和输入冻结于snapshot，记录SHA256。
输出：远端个人HDD logicbench-20261021-v1；模型只读SSD现有权重，不下载。
进度：已提交并运行；最新状态见顶部。不要重复执行首次提交。

## Open Ideas / 值得深挖的问题
暂无新增。
