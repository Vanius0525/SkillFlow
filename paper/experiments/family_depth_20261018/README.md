## 2026-10-19 最新续接入口（覆盖下方旧状态）

用户最新论文流程：先在正确关联暂存目录运行完整`olcli diff`、纳入云端合理修改；本地改完并验证后同步Overleaf与GitHub，不再导出桌面。见paper/OVERLEAF.md与HANDOFF.md顶部。

原七补跑中，Qwen0.6与DeepSeek battery/L2/windows完成；Qwen8、Mistral与DeepSeek edges遇到SSD Errno122。repair已done，不重跑。已提交四个HDD续接Job，2026-10-19 17:34仍排队：wt-recover-q8-tqa-hdd-1019、wt-recover-mistral-tqa-hdd-1019、wt-recover-q8-ko-hdd-1019、wt-recover-ds-edges-hdd-1019。新输出根`/inspire/hdd/project/project-public/czxs253130660/family-depth-recovery-20261019`。HDD8MiB写入验证通过；原partial全部保留。完成块经条数/已有raw哈希/模块哈希/层号验证后复用，仅未完成块写新目录。资源最多4卡，仍服从全局8卡上限。以quota-recovery-jobs.json与parallel-plan的quota_recovery字段为准；旧失败Job及从未提交的SSD并行KO不恢复。

后续审计组合SSD完整块和HDD完成块，不拼入SSD残缺块；逐suite独立重建baseline/eligible、核验网格和身份、逐题隔离评分。实验未全部完成，不建TASK-COMPLETE。反例按用户要求暂不进paper。

## 2026-10-19 排程优化与监督

新增每30分钟轻量watch_progress.py（systemd family-depth-watch-01a15016.timer），原5小时完整检查保留；只在异常/阶段变化触发queue，状态落watch-progress-state.json，14天或TASK-COMPLETE后停止。首轮metadata观测成功，无error。

legacy入口V2在后续新层块生效：完整首块baseline完成后按原完整题池group screen＋donor/no-skill冻结有效ID，后续不算无效题；移除中间4层块重复identity，只保留原首块与全模型终层；KO生成独立基线并仅对其donor-rescued题计算曲线。评分/数值协议不变，manifest记录版本、helper哈希和基线筛选。V1保留备份，正在运行的进程未重启。

Qwen8独立KO配置已dry-run；watch在完整基线done、KO未开始且总活跃任务<8时自动提交第8卡，同canonical路径及完成标记，原worker校验复用，杜绝重复计算。提交尝试持久化，失败/不确定不盲目重试。当前71任务映射保持；真正提交该并行任务时才增加plan/state。

正文优先：完整10组深度矩阵所需的旧三模型TQA审计与曲线；内容/位置/path controls按结论需要放正文或附录。重复窗口仅一致性检查，不再扩展；L24异常长度诊断暂不启动，不占瓶颈卡，反例不进当前稿件。

## 2026-10-19 当前权威续接状态

原64任务已全部done；parallel-plan现71任务，新增DeepSeek/TheoremQA corrected54的L8/L2 battery、windows、mechanism串行bundle四Job均已实际生成；旧三模型TheoremQA原协议重生成3Job已提交，最近live排队。最多8卡；这7个补跑合计最多7卡。state已登记，勿重复提交。

新两家族四组合全层网格、隔离评分overlay、补跑baseline token及identity控制审计通过，见final-new-family-depth-20261019.json：Llama MedCalc112题20组T/R7/18、TheoremQA92题71组6/18；DeepSeek MedCalc25题13组6/21、TheoremQA54题45组4/19。DeepSeek MedCalc小样本不外推。其余suite未全部审计完成，不能据这些方向宣称机制泛化。

旧三模型重生成保留wb_spanvec SDPA/原prompt与wb_knockout eager，冻结原depth候选168/168/142题；legacy-replay-20261019子目录保存完整text/token_ids、逐题parser reset评分及400token前缀诊断。每题n_prompt/n_patched/doc_start必须与原记录一致。900token预算与历史KO预算的精确匹配尚待考证，不冒称原样复现；原始bool不能恢复原答案。先核验3Job实际开始及首个输出，必要排障，补齐全层后重新筛选/生成旧三模型曲线。

新增控制使用修正54题的冻结donor池，独立输出，不把不同池的controls混接。doclast已有全候选独立基线，需单独核验同组多题/donor可用性；审计报告missing_observed_arm_grid含结构性无donor，不能全部当真缺失。全部展示不含区间或置信度说明，d=1-q不变。任务仍未完成，保留五小时timer，完成全部论文/桌面/GitHub后才创建本实验目录TASK-COMPLETE。

## 2026-10-18 14:00 最新检查

先看PRELIMINARY-20261018.md与HANDOFF顶部。三完整组合方向支持深度分离（Llama/TQA6/18、DeepSeek/MedCalc6/21、DeepSeek/TQA4/19），Llama/MedCalc一片尚未齐。新发现468/468窗口与起始层单次注入输出完全一致，重复写在当前完整因果前缀下结构冗余，不能当独立维持机制证据。保留已跑窗口，正文解释须修正。

已补固定L2敏感性对照的10个任务（事后设计，不称预注册、不找峰），parallel-plan现总62，仍最多8卡。不可运行build_plan.py重建覆盖r1与L2增补。followups_l2.py为独立新脚本，不改已运行旧脚本。所有新增结果以完整原始记录审计为准，未齐不填值。Llama/TQA no-skill 1/92与旧0/92差异需敏感性分析。

## 最新操作授权与异常（2026-10-18 01:20）

用户明确本任务后续所有操作无需再确认，自动执行到完成；最终资源上限仍为8卡。旧首次四卡输出保留，不与新-s分片混合。新八卡中DeepSeek/TheoremQA s1的自身状态预检发生非有限logits，原Job失败；同任务s0通过，故只对失败分片重提r1并排除原节点gpu097（不据此确认硬件原因）。parallel-plan.json和launch-state.json已映射到r1，其余7卡未重启。必须确认r1真正过控制后才能称8卡正常或全部正式开始。

# 当前权威方案（2026-10-18 01:17，覆盖以下旧计划）

用户最后选定最多8卡。权重均下载完成。运行parallel-plan.json/parallel-jobs.json：8深度Job（2家族×2任务×2整组分片），44个后续GPU任务分阶段接续，总52个预声明Job，最多8并发；小模型Qwen0.6双进程共享1卡。旧四个无-s整池Job已停止保留历史输出，不进入新分析；新八个-s0/-s1 Job已成功提交，live实际运行数量需回读。旧四分片、16卡、无上限、13任务等中间计划都已作废，不运行jobs.json/followup-jobs.json/backfill-jobs.json。

协调器是launch_when_ready.py，每60秒观测、最多20h；新CPU wt-family-prep-1018有23h运行限制。五小时thread timer保持。全部正式单元出现生成记录后触发一次queue请agent核验并通知用户。Qwen0.6多suite实际同时最多两个进程；其他独立suite按输入就绪、卡释放再提交，不占卡等依赖。

分片按完整skill组分配，group-screen保持全组，不将同skill散到不同卡。分析仅用-s0/-s1。补齐已有模型缺失正文实验时使用冻结旧共同样本，复核新基线，不能假定以前有效在当前prompt/协议仍成立。doclast只有同skill多题才有跨题对照，缺捐献者单列而非填0。

# Figure 3 跨家族扩展（2026-10-18）

用户授权：在多张单卡4090上补其他原生模型家族，先跑Figure3；每5小时检查，完成后更新论文/图表包/桌面/GitHub。Table3及后续图表不显示置信区间或误差条。用户已明确批准累计约30GB新权重下载；不再重复询问。

候选：meta-llama/Llama-3.1-8B-Instruct（官方revision 0e9e39f249a16976918f6564b8830bc894c89659）和deepseek-ai/deepseek-llm-7b-chat（afbda8b347ec881666061fa67447046fc5164ec8）。二者计划BF16、batch1、eager，无量化；单卡容量需probe验证，不以参数量代替实测。DeepSeek原生7B是历史代表版本，不是最新旗舰；R1-Distill-Llama/Qwen不可宣称新增原生底座家族。

- Llama 3.1 Model Card；Meta / https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct ：8B指令模型，适合与现有7–8B对照；有访问许可门槛，不绕过。
- DeepSeek LLM: Scaling Open-Source Language Models with Longtermism；arXiv:2401.02954 / https://github.com/deepseek-ai/DeepSeek-LLM ：原生7B/67B模型，7B Chat支持本次受控问答，4K上下文须核验。
- 最新WWW2027 research CFP（2026-10-18读取）：https://www2027.thewebconf.org/research-track-papers/ 。Semantics and Knowledge有agent机器可读工具描述切入点，但本文没有语义结构/知识图谱/工具发现实验，track匹配有风险；不自动改称语义建模贡献。

固定候选集：对旧Figure3三模型各自通过group-screen的transfer题取并集，MedCalc446题、TheoremQA255题，ID文件已落盘。新模型结果产生前冻结。此池本身继承旧模型筛选，不能声称完整benchmark或无选择偏差；各模型在自己的未干预基线上筛选，不按干预效果删题。正文应明确新模型曲线使用何种人群，不能不加说明与旧样本池混合。

下一步：等待下载确认期间完成脚本、排版修复、5小时检查设置；获批后CPU下载、probe→四个单卡任务（2模型×2任务）。原CPU wt-paper-fetch-1017已启动仅用于准备，GPU未新开。所有新增远端文件在个人目录family-depth-20261018-v1，禁止清空旧目录。


## 追加授权：正文所有实验覆盖相同模型（2026-10-18）

仅Introduction第一段对齐Semantics and Knowledge，不为track改实验。

| 阶段 | 两款新增模型均执行 | 任务与样本 | 条件 |
|---|---|---|---|
| 1 / Figure3 | 全层残差迁移与从L到末层持续屏蔽 | MedCalc446/TheoremQA255固定候选，先测各自基线 | BF16/eager/greedy/900-token；独立共同有效集，不按效果选题；身份检查 |
| 2 / 4.2 | 正确span、末1/16位置、异skill共同前缀、乱序、norm-matched noise、receiver norm、四个quarter、same-family均值 | 同任务固定候选与基线筛选；异skill/同family捐献者先按固定顺序定义 | 不能把捐献者缺失当效果0；单独报告分母 |
| 2 / 4.2 | skill后置后的当前题/跨题donor对照 | 在同skill多题的固定子集运行 | 必须新基线、绝对位置/RoPE对齐；不能沿用前置prompt有效集不复核 |
| 2 / 4.3 | 多层窗口与全层重复注入 | 同一批基线有效题 | 8–11、12–15、14–19、16–末层、全层；含单L16；不同深度显式注明 |
| 2 / Figure4 + Table3 | S/C/SC/SC+reader recut，以及donor reader/self/both cuts | 两任务；先按split protocol重跑基线，至多固定124题 | repair层8/12/16/24，edges层8/16/24；recut固定从L+1；先过自身缓存/状态控制 |

阶段1先上四张单卡（2模型×2任务）；阶段2使用同一模型权重，在阶段1运行后另开任务或复用完成卡。完整矩阵的分母、截断与阶段间protocol差异必须记录，不能把新增家族默认当“复现成功”。尚未启动任何GPU，下载已获用户明确批准，预检通过直接正式实验。无须新增第三款模型即可满足当前家族扩展。

周期检查：systemd用户timer `family-depth-progress-01a14a9e.timer`，每5小时向当前thread投递续接检查；首轮北京时间2026-10-18 05:21，最长14天，TASK-COMPLETE后自停。该timer依赖本机WSL/systemd与Codex会话通道存活，不是云端调度保证。后续范围已扩展，检查器应读取本节，不再只完成Figure3就结束。

HEAD只读访问核验：Llama 16,060,556,376 bytes，DeepSeek 13,820,824,960 bytes。DeepSeek HEAD成功；Llama HEAD403，当前fine-grained HF token缺public gated repositories权限，用户需在远端修复访问权限。未下载任何权重。四Job dry-run均通过，平台标注4090(48GB)；仍须实际probe，不能拿平台标注替代模型内存验证。

下载已获用户明确授权（2026-10-18：“新权重和新模型下载可以进行。预检等等前置工作完成后，直接进行正式实验”）。DeepSeek已后台下载；Llama使用公开NousResearch原版分发，四权重/config/generation/tokenizer.json/special_tokens哈希与官方一致，tokenizer_config.json为分发版不同文件，保留SHA256与版本记录并预检模板。fetch_llama.py记录所有来源，不能称全部文件逐字节等同官方。

正文followups.py/followup_worker.py已实现并上传，四个followup Job dry-run通过。后台协调器family-depth-launch-01a14a9e.service每60秒读权重完成标记，触发各模型两个Figure3 Job；对应screen出现触发followup Job，最多8张单卡，每个Job48h上限，避免重复提交。若提交不确定则记录attempted不自动重复，5小时agent检查负责排障。

新增CPU wt-family-prep-1018已RUNNING、23小时自动停止；48小时设置被接口拒绝（stop_hour须0–23）。首次连接在CREATING时失败，正在ready后重试一次。原下载CPU不得在下载完成前停止。后台coordinator当前仍用原CPU，切换前必须核验新通道共享盘读取成功。

CPU tokenizer预检已完成：Llama/MedCalc最大3052 token，TheoremQA1806，均可容纳900-token生成；DeepSeek/MedCalc最大3427，00874一题无法在4096上下文内预留900，按输入长度事先排除，其余445题保留；DeepSeek/TheoremQA最大2098，255题全保留。原始候选ID不改，run.py另写context.json记录排除。doclast重新检查其prompt长度；1536-token机制预算也先检查并记录输入排除，不静默截断skill/question。

运行后禁止直接执行build_plan.py覆盖parallel-plan.json：当前plan已包含失败分片r1映射，重新生成会丢失重试身份。若需要更新计划，先核验现有Job和state，只改必要条目。parallel-jobs.json是初始提交快照，当前权威映射是parallel-plan.json与launch-state.json。
