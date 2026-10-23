# 本轮实验②③已完成（2026-10-23）

6076条正式结果＋14条gate已独立审计通过；没有新增推理或论文修改。实验①保持取消。小时timer已停止，TASK-COMPLETE保护禁止旧调度器恢复提交。迟到通知仅去重。

阅读：[结果与论文含义](../../reports/状态完整性补实验结果_20261023.md)。汇总及二值标签在retrieved/，无回答正文；完整原始gzip保留远端SSD v2。当前冻结代码SHA清单为compressed-manifest.json；先前manifest与备份配置属历史。

审计结束后本轮观察CPU已stop；实例和数据未删除。不要直接运行旧提交配置或恢复timer。新实验须重新定义范围/输出目录，不覆盖本轮记录。

---
以下为历史过程，由以上完成状态覆盖：

# 当前运行入口：v2无损压缩保存（2026-10-22）

用户仅批准删除SSD v1/write-probe.bin，已释放256MiB；旧结果保留。完整donor记录1条已无损复用，不重新生成。
有效ROOT=/inspire/ssd/project/project-public/czxs253130660/state-completeness-20261022-v2；raw文件现为.jsonl.gz，逐条gzip member，读取使用gzip.open；done/progress/manifest sidecar不带.gz。
当前任务wt-state-repair-s0-1022-r3（gate&&repair0），通过gate后提交wt-state-repair-s1-1022-r3。调度器state-completeness-compressed-launch-1022.service；原小时timer不变。旧r2失败/旧depth取消均不恢复。
只保留实验②③，正式6076条＋gate14。Engine计算代码AST未变，5项本地/远端测试通过。详情见HANDOFF.md和storage-recovery-20261022.json。

---
以下历史记录由上方入口覆盖：

# 当前有效范围：实验①已取消，仅保留②③

2026-10-22用户取消逐层稳健性复测。下方原计划为历史记录，不能据此提交depth。
当前jobs.json只有两个repair任务；首任务gate&&repair-0，第二任务须gate通过。统一协议、wrong与neutral两背景、L8/16/24状态/缓存组合、全source/非source/完整copy/suffix重放、内容与等8层窗口对照保留。
正式6076条＋gate14；最多2卡。小时监督仅等待两个repair分片，不等待取消的depth。旧depth首任务已CANCELLED且无输出，其余depth不提交。
当前调度器state-completeness-repair-launch-1022.service；旧state-completeness-launch-1022.service已停止。取消①意味着本轮不再独立验证原全深度分离是否对中性receiver和统一协议稳健。

---
历史设计：

# 状态复制完整性：当前启动实验

面向问题：晚层迁移失败究竟是只复制了部分状态，还是还存在接收执行历史的影响？本实验不预设答案。

## 一个直观例子

给模型一本正确的计算说明书与一道题，作为donor；接收执行则读错说明书或读无关的图书馆/旅行文字。现有S只更换某层的说明书位置内部向量。缓存KV是注意力以后会读取的历史记录，既包含说明书位置，也包含题目位置。换掉说明书记录不一定抹掉此前处理题目时形成的记录。

## 本轮已经冻结的实验

Qwen3-8B、MedCalc的124历史候选/14个计算器；所有条件BF16/eager/split-prefill/greedy、最多1536新tokens。所有题保留，不按新干预结果筛选。

1. 全36层：wrong与neutral-A接收执行各测S，与同协议donor来源注意力切断KO比较。neutral-B预定L8/16/24敏感性检查。
2. L8/16/24：两种接收执行各测S、低层cache、SC、显式全source覆盖SC_exact。
3. 与深度无关：全source KV、仅非source KV、完整prefix KV、source正确后的后续prompt重算。
4. 内容对照：全source写入正确skill、原wrong skill或neutral-B内容。
5. 等覆盖预算：在原receiver背景下分别写入0–7、8–15、16–23、24–31层source KV，另保留全层覆盖。

共20460条正式生成，分为2个depth shard和2个repair shard，最多4张4090。重复基线不跨suite静默合并，最终审计其token是否相同。当前不是四模型全矩阵，不启动LogicBench。

## 哪种结果回应哪种质疑

|问题|有判别力的结果|解释限制|
|---|---|---|
|分离只是数值协议差异？|统一协议后仍存在|若消失则重估原主张|
|wrong skill只是强干扰？|neutral下仍存在且效果相近|neutral也不是绝对无影响，保留两份文本|
|仅仅缺source缓存？|C_all已接近完整copy|支持覆盖解释，不能强推历史机制|
|source补齐后为何仍失败？|source精确相同而SC_exact与C_all不同|支持非source背景作用，不等于已定位错误结论|
|只要多复制点就行？|等位置/层预算时正确内容明显优于wrong/neutral|区分内容与泛化扰动，不能证明唯一语义机制|
|是不是仪器漏状态？|完整prefix复制token-exact复现donor|这是正控制，不是论文新发现|

## 正控制与进度

两道预定题先做14条gate，source自身写回与完整prefix复制必须逐token一致；通过才接正式任务，失败退出。suffix replay另记录是否完全复现，不把BF16数值差异伪装成缓存语义发现。

远端新有效路径：`/inspire/ssd/project/project-public/czxs253130660/state-completeness-20261022-v1`。
HDD同名目录是首次失败现场，保留不删。HDD首条保存Errno122；SSD256MiB写入探针成功。失败原因为存储，不是机制检验结果。

本地`deployment.json`、`launch-state.json`及平台status是状态入口。有限systemd服务`state-completeness-launch-1022.service`只负责等待gate并提交剩余任务，最多20小时，依赖本机在线；不代表持续结果审计或完成通知。GPU Job一旦提交，不依赖本机维持运行。CPU保留原23小时自动停止。

```bash
python3 experiments/state_completeness_20261022/test_instruments.py
inspire --account me job status wt-state-depth-s0-1022-r1 --workspace 可上网GPU资源
```

不预报准确率或显著性；所有预期都是可证伪假设。完整结果后需独立进程重判、键集合/哈希/截断检查、按skill整组重采样的不确定性与逐skill结果，再决定是否扩模型或改论文。当前不修改Overleaf。

## 2026-10-22 18:23 新增小时监督

用户授权后已建立state-completeness-hourly-01a162f7.timer，每小时整点（CST），绑定当前对话；首次完整检查和通知成功，最新重试任务仍排队。全部正式分片生成哈希/条数核验后停止，最多72小时；独立评分与统计审计仍由当前对话续接。依赖WSL/systemd/Codex在线。现有launch服务只负责gate与提交，和小时监督不是同一任务。其他对话LogicBench-full定时器未操作。
