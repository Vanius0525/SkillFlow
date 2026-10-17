# 新对话交接：机制探针已完成，正式实验尚未启动

核查时间：**2026-10-16 23:49，北京时间**。这是当前执行状态，优先于旧 `HANDOFF-20261016.md` 中“没有启动新实验”和早间记录中的“探针正在运行”。

## 1. 用户目标、优先级与授权

1. 解释论文中 reading but cannot transfer 的中间区间，实际运行机制实验并生成正文热力图，随后继续改写 WWW 论文。
2. 启动前说明与整体论文脉络已放桌面：`/mnt/c/Users/12970/Desktop/WWW论文实验启动说明与整体脉络_20261016.md`；仓库副本在 `reports/`。预期结果明确标为假说。
3. 用户追加：在现有 MedCalc、TheoremQA 上加入 Llama 或 DeepSeek 等可在4090部署的新家族，跑主实验完整双曲线。
4. **最新优先级：先跑新机制实验，运行成功后再跑新家族的旧主实验补充。** 不要反过来优先下载/扩模型。
5. 论文措辞不要太防御性；方法边界集中写一次，正文推进发现和解释，避免反复复述图表或限制。
6. 用户最新要求：核实是否跑上、大概要多久，写交接给新对话。此交接不取消原实验和改写授权。

日常读写、执行、小依赖安装和网络请求已经授权，不逐项询问。累计/单次下载>1GiB仍需明确批准；删除已有文件必须先获批准。任务未完成，当前改动尚未commit/push；最终完整完成后只提交本任务文件到master。不要包含用户原有 `howskill/data/cells.json.tmp`。

## 2. 当前状态：没有正在运行的机制实验

| 任务 | 平台状态 | 说明 |
|---|---|---|
| `wt-mechanism-env-1016` | job_succeeded | CUDA、共享盘权重、Python环境验证成功 |
| `wt-mechanism-probe-1016` | job_failed | 在加载模型前发现远端wb_spanpatch源码与本地不一致；没有实验结果 |
| `wt-mechanism-probe2-1016` | **job_succeeded** | 2题×L8/L16探针，40条基线/干预输出；11:27:11结束 |
| 124题正式机制实验 | **尚未创建** | 需要先完成协议桥接检查 |
| 新家族双曲线 | **尚未创建** | 按用户要求排在新机制实验之后 |

此前有一次约83KB命令提交返回API InternalError，live列表确认未创建任务。缩小源码包并使用独立最小推理循环后，probe2成功。不要重复提交已成功的probe2。

后台 `monitor.py` 曾启动，每600秒查询，只读不自动续跑；日志显示最后连续三次API查询失败，**13:17已自行退出**。没有当前有效的周期监控，更没有自动启动正式实验或自动改写论文的调度器。观测日志首次11:21，随后12:54/13:05/13:17；不能声称中间全程准时每10分钟检查。`active-jobs.json`已清空，旧PID记录只是历史，不能拿它直接kill进程。

## 3. 已取得的探针证据和未解问题

本地证据：

- `experiments/mechanism_20261016/probe2-platform-log.txt`：平台完整日志快照。
- `experiments/mechanism_20261016/probe2-summary.json`：从日志提取的耗时、分段检查及旧结果对比。
- `experiments/mechanism_20261016/status-20261016.json`：最新状态。

**平台日志不是完整原始数据。** 原始 `probe.jsonl`（生成文本、token IDs、hook计数、首token分布）、manifest与done文件还在远端，尚未取回，也尚未在本地逐字段审计。当前“完成”的证据为平台success、exit code0、两个ITEM_DONE、40条日志。下一步应回读done与JSONL。

探针设置：Qwen3-8B，BF16，eager attention，H200，固定2题 `medcalcbench_00987`、`medcalcbench_00266`；L8/L16；max_new=900；三种边的全程knockout；S/C/SC/SC_recut及identity_SC。没有启用R，尚未测prefill-only/decode-only。

已验证：

- 两题donor均对、receiver均错；完整/分段prefill的这四个baseline正确性一致。
- 4次identity_SC均完成且程序未触发token序列不一致断言，说明本探针内自身残差+自身缓存写回是恒等操作。
- mask方向/索引/非原地修改/fail-closed的4项CPU测试已通过；GPU切断臂完成。

必须处理：

- 完整与分段prefill输出文本：第一题donor相同、receiver不同；第二题donor和receiver均不同。**程序成功不等于协议等价已经通过。**
- 旧审计记录中第二题 `ok_real_L8=True`；新探针S@L8为False。第一题旧/新S@L8均False；两题旧/新L16均False。因此早层正控制还需要扩大并桥接，不能直接把新热图接到旧曲线上。
- 潜在差异有旧实验SDPA/新实验eager、旧4090/新H200、完整/分段prefill。一次改变多项，尚未定位原因。保持同一个模型、硬件和backend后分别改变协议，捕获与注入必须使用同一计算形状/attention mask。
- 第二题SC@L16达到900token上限，记为truncated=True；不能将未完成输出当成机制失效的强证据，需预设较高token上限的敏感性检查。
- 第二题SC@L8答对而S/C单独答错，recut后又错；这是**单题线索**，不是机制成立。两题/两个skill不具备推断效力。

## 4. 耗时估计（依据真实探针）

40条生成耗时合计360.50秒；平均9.01秒，中位数8.09秒，范围3.43–24.94秒。2题推理约6分钟；平台从创建11:18:29到完成11:27:11约8分42秒，包含调度/加载。

按计划124题、L8/12/16/24/28：

- repair：每题2基线+5层×4臂（S/C/SC/SC_recut），共2728次生成。
- edges：每题2基线+5层×8臂（both/prefill/decode拆分，decode没有source-self臂），共5208次生成。
- 合计7936次，按均值约**19.9 GPU小时**。单卡粗估20–30小时；4张同类卡、工作量均衡且顺利调度，粗估**6–10小时**。这是正式计算时长估计，**不是已经开始倒计时**。
- 两题不足以估计长尾；排队、协议排障、R修复、规则反事实、第二家族机制复现、新家族旧双曲线不在上述耗时中。改为更高max_new后重估。

## 5. 实验代码与语义

目录：`paper/experiments/mechanism_20261016/`。

- `run.py`：独立Scorer/Engine，不再调用旧白盒推理循环；复用本地快照的提示/skill处理/评分依赖。
- `test_instruments.py`：4项CPU mask测试。
- `ids-qwen8-medcalc.json`：之前严格joint-baseline-valid的124题/14组，按组ID交错排序，不按新结果挑题。
- `analyze.py`：固定完整共同样本、重新检查donor正确/receiver错误；保留历史固定集合分母。缺臂/缺层默认拒绝生成正式图，显式allow-incomplete才绘开发图。
- `monitor.py`：只读有限监控，所有任务终态、连续3次失败或24h到期退出；不自动重启。需改进timeout异常处理并验证新进程持续运行。
- `deployment.json`：probe2目录及数据SHA256。

S：prefix prefill中替换block L的source输出；C：prefix完成后，仅将source位置层0..L的KV替换成donor，再计算最终提示token。**C不追溯重算先前reader状态或reader缓存。** 所有repair臂使用相同分段协议。

R可选：题目token residual，排除最终提示token；SC_recut为同次执行从L+1起切断reader→source。mask reader行q≥source_end，source-self行source_start≤q<source_end；保持因果mask，拒绝缺4D mask及全遮蔽合法行。

重要待补：新协议目前只有donor/receiver基线，124题的no-skill eligibility来自旧协议。若正文继续声称新协议rescued，需补新协议no-skill基线；或明确仅以新donor/receiver筛选、不混用术语。

配置+源码哈希拒绝不兼容续跑，flock禁止多个writer。原始JSONL逐条flush，完成后写`.done.json`。**不要修改run.py后对旧输出直接resume；应开新版本目录/输出，并记录版本差异。**

## 6. 启智资产与访问

使用前读取 `/home/vanius/.codex/skills/inspire/SKILL.md`；本地账号alias `me`。2026-10-16实测：

- Workspace：`分布式训练空间`；Project：`公共科研项目`。
- Probe2 Group：`开发区-H200-3号机房-2-cuda12.8版本`；quota `1,20,200`；image `ngc-pytorch:25.02-cuda12.8.0-py3`；priority4；max-time2h。
- 以上是历史已用配置，新作业重新查live quota/availability，不当作无限可用。
- Python：`/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python`。
- 模型：`/inspire/ssd/project/project-public/czxs253130660/models/Qwen3-8B`。
- 同目录已缓存Qwen3-0.6B/1.7B/14B、Qwen2.5-7B-Instruct、Mistral-7B-Instruct-v0.3；没有发现Llama/DeepSeek。
- 原代码/数据资产：`/inspire/ssd/project/project-public/czxs253130660/agent-harness`；**旧wb_spanpatch与本地不同，不能直接信任其推理循环。**
- Probe2完整独立目录：`/inspire/ssd/project/project-public/czxs253130660/mechanism-20261016-v2`。含`run.py`、`analyze.py`、`repo/howskill/howskill/`依赖快照、数据副本、probe结果。
- torch `2.7.0a0+ecf3bae40a.nv25.02`，transformers `4.57.6`，CUDA可用。

CPU `wt-dev-cpu`已恢复RUNNING，但SSH隧道建立报`xterm surface not ready`。原CLI7.1.8及临时7.1.12都失败；未清缓存/删文件/重试密码。临时安装路径`/tmp/inspire-cli-7.1.12`可能在新环境消失。**/tmp中的提交计划文件目前已经不存在，不能依赖它续接。**

已成功的替代路径：`inspire job create --command`中携带约34KB压缩本地源码，解包到新的个人目录，数据复制前校验哈希，再运行。禁止覆盖旧目录。运行中的`inspire job shell ... --rank 0`已成功进入交互shell；probe2现在结束，不能假设旧shell还可用。

原始结果取回优先修复CPU文件通道；必要时用短只读Job读取共享盘done/manifest及压缩结果，经平台日志取回小产物并校验SHA256。不要为文件访问重跑已经完成的模型实验。

## 7. 下一对话立即执行的步骤

1. 核对平台状态，确保没有其他会话新增任务，读本地probe2日志与summary。
2. 回读远端`probe.done.json`、`probe.exit.json`和完整`probe.jsonl`，核对40条记录、唯一键、token一致性与mask计数。
3. **先做协议桥接小实验**：同模型/同硬件固定backend，比较完整与分段prefill；再固定协议比较eager/SDPA。扩为按ID固定的每组1题（14题），包含正/负早层控制。不得按新干预成功筛样本。对截断臂预设更高max_new。`Engine.capture`目前固定prefix，若新增full-capture要明确参数，不能用prefix捕获冒充full-capture。
4. 新协议自身identity通过、正控制和差异范围明确后，启动E1/E2正式124题实验。可用suite与shard参数分到4个单卡Job（repair/edges各两分片），正式输出新命名，不覆盖probe。
5. 更新active-jobs、manifest、HANDOFF；启动并验证有限监控进程，立即检查后每10分钟记录。给出经实测更新的ETA。
6. 结果齐后用analyze.py生成真实热力图；先审计共同分母、截断和各臂完成度。S/C无法解释时再启R；修复有效再做同次recut/规则精确反事实。当前2题不能制作正文结论图。
7. 新机制实验成功后再跑新家族主实验，然后据证据重写论文和图表。不要把预期结论写入正文。

状态命令（已验证）：

```sh
inspire job list --workspace 分布式训练空间 --keyword wt-mechanism --all
inspire job status wt-mechanism-probe2-1016 --workspace 分布式训练空间
inspire job logs wt-mechanism-probe2-1016 --workspace 分布式训练空间 --all
python3 experiments/mechanism_20261016/test_instruments.py
```

正式运行参数模板（**不是现有已提交任务**；先完成第3步，使用独立输出路径）：`run.py --repo <v2>/repo --model <models>/Qwen3-8B --ids <v2>/ids-qwen8-medcalc.json --suite repair|edges --layers 8,12,16,24,28 --shards 2 --shard 0|1 --max-new <验证后的上限> --out <新结果路径>`。

## 8. 新家族任务与下载批准

候选已核查官方模型元数据：

- `deepseek-ai/deepseek-llm-7b-chat`：从头训练的DeepSeek 7B，不是Distill-Qwen；官方2个bin权重合计13,820,824,960字节，约13.82GB/12.87GiB，revision `afbda8b347ec881666061fa67447046fc5164ec8`，非gated。官方不推荐system prompt，应统一合入user。
- `meta-llama/Llama-3.1-8B-Instruct`：4个safetensors合计16,060,556,376字节，约16.06GB，manual gated；需已有访问授权。
- 已通过异步问题请求>1GiB下载批准，**可见会话尚无明确批准**；“先跑新实验”不是批准大下载。不能先下载后补问。
- 预定个人路径`/inspire/ssd/project/project-public/czxs253130660/models/DeepSeek-LLM-7B-Chat`。不向共享public目录写入。
- 新模型需自己的none/gold/wrong基线与筛选；MedCalc和TheoremQA均逐层跑完整双曲线。不能用Qwen124题作为其主样本；需检查EOS/eot集合、模板、token span、上下文长度和实际显存。

## 9. 论文、图表与本地验证

最新已提交HEAD：`1209f67`（前轮机制设计报告）。本轮有未提交文件，`git status`为准：HANDOFF、build.sh、intro/related/formulation/conclusion、bib、两版PDF、审计JSON、新experiments目录和启动说明。

已改写：

- 方法明确block-output patch不追溯更新低层KV；原knockout包含source内部更新。
- Related Work增加Models Take Notes at Prefill、Multiple Mediators两条核查过的预印本引用。
- 引言/结论以发现为先；删除结论重复的方法免责声明。新实验结果尚未写入论文。
- build.sh改用新临时构建目录，避免rm旧构建；不会删除历史构建记录。

本轮已通过：CPU4项测试、py_compile、git diff --check；数值审计132,551 checks/475源文件；投稿版正文7页/全文11页，扩展版37页，两版无error/undefined/overfull。构建发生在早间；/tmp构建日志可能已消失。

尚未更新Overleaf ZIP；尚未生成新机制热力图。现有正文joint-failure图仍是旧结果的同题描述图。计划机制主图为“修复条件×实际层号”的准确率热图；边拆分图可作第二面板。原始不确定性统计保留，图中按用户偏好只画点估计。

## 10. Open Ideas / 值得深挖的问题

2026-10-16：完整执行状态是否决定skill可迁移性？代码与probe提示需要区分来源残差、低层缓存和reader历史。第二题L8仅联合SC成功且recut后失败，是后续检查线索；样本只有1题，且新旧S@L8不一致，不能宣称发现协同机制。最小下一步是协议桥接+固定14组小样本，再决定扩大。一般缓存旧结论与中介交互已有近邻，本稿增量应是深度区间的可预测解释。

不要在新对话重复启动探针或从旧HANDOFF恢复过时论文结构。先查当前状态、拿齐原始输出、定位协议差异，再扩批量。
