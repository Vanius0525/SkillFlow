## 2026-10-20 当前入口：仅4主模型×2benchmark，图表覆盖更新完成

- 最新用户指令：放弃小模型相关论文结果，重点让4主模型×2benchmark覆盖所有表格和图表。用户称Qwen0.8B，当前实际小模型为Qwen3-0.6B；已从活跃正文/附录、当前深度JSON、图表与生成入口移除。原始实验、历史报告及未引用旧文件保留，不删除。
- 当前论文4图6表：Figure1八组合概览；Figure2通用干预设计；Figure3八组合逐层深度；Figure4八组合L16修复和L24路径损失。Table1八组合L2/L8控制，Table2八组合边界，Table3八组合机制差值；附录跨题/窗口、修复和独立分母三表均为八组合。图表包四图六表已全刷新，合集11页；旧七格/Pending说明已纠正。
- 科研口径：L8已在Mistral/Llama/DeepSeek迁移边界之后，不称统一早层；加入L2准确率56.0–93.4%。Mistral/MedCalc L16 additive interaction=-7.9pp，即使SC-S=+10.5pp，不能称统一正交互。历史Qwen8/MedCalc跨题/窗口行报告恢复率，其他行准确率，表中显式区分，不作排名。全部suite沿用r3独立筛选。
- 验证：python tools/build_eight_cell_displays.py；python tools/audit_eight_cell_displays.py --stage /mnt/c/Users/12970/AppData/Local/Temp/WWW2027/build-skillvector.Pq5ZnFyY；python tools/audit_integrated_manuscript.py --pdf skillvector-www2027.pdf通过，200个机制arm×layer计数核验。论文正文8/全文12页，无error/undefined/overfull。python tools/compile_figure_bundle.py通过，四图六表11页，无error/undefined/overfull hbox。
- Overleaf更新前基于当前稿件快照完整diff零差异（07:09:41Z），上传前与同一基线再完整diff零差异（07:24:42Z），未发现新增线上修改。非删除上传22文件，最终活跃源0新增/0修改差异；仅未引用历史fig-depth-scale-check.pdf为remote-only，未传播删除。云端PDF12页，每页提取文本与本地已审计PDF完全一致。证据audit/EIGHT-CELL-OVERLEAF-20261020.json及audit/EIGHT-CELL-COVERAGE-20261020.json；最终本地PDF SHA256 aed9adf8bb09dfc96529baa13f847449bc59fe5e45cc4ff1032387a8956fbc46。
- 最终论文skillvector-www2027.pdf；图表合集paper figure/Figures-and-Tables.pdf；覆盖报告reports/图表八组合覆盖核查_20261020.md。CURRENT.json记录当前八组合论文范围及新交付收据，实验完成审计仍保留历史完整产物。无新推理/远端资源/定时器/数据下载，无待续接实验。
- 后续修改论文前仍完整olcli diff，上传前再查并发。Git仅提交本次任务修改，不纳入原先的调度状态、旧DATA-CONSISTENCY和howskill临时文件；本轮提交推送完成后以git log为准。

## 2026-10-20 当前续接入口：论文交付完成，旧实验监督已关闭

- 当前任务已完成，无待续接的实验、评分、聚合、论文编译或同步步骤。用户已再次确认论文更新与同步状态；后续若收到旧 done 或小时状态消息，只去重报告，不重提实验、不恢复旧队列或定时器。下方按日期记录的“运行中／待上传／保留监督”均为历史过程，不能覆盖本节最终状态。
- 论文提交 `001f752`、收尾提交 `f6aca98` 均已推送 `origin/master`。正文、摘要、附录、表格及图表已更新；Overleaf 项目 https://www.overleaf.com/project/6a2cfd49b99635e8e968576a ，根文件 `overleaf-skillvector/main.tex`。上次交付已核验20个源文件完整 diff 零差异；云端编译正文8页、总12页，无错误、未定义引用或溢出。本次仅更新交接，不声称重新检查了线上协作修改。
- 最终 PDF：`skillvector-www2027.pdf`；SHA256 `4aa84a30100be635e0c9e2399b4610eb13327c981a27e97e1bca08a832ac3293`。交付证据：`audit/OVERLEAF-DELIVERY-20261020.json`、`audit/MANUSCRIPT-INTEGRATED-20261020.json`。下次修改论文前仍须重新完整执行 `olcli diff`，上传前再次检查。
- 实验唯一权威入口：`experiments/family_depth_20261018/CURRENT.json`，引用 r3 完成矩阵与套件审计；旧 r1/r2 不用于论文。既定冻结候选上的8个主模型×任务深度组合和2个小模型补充组合均齐全；这不等同所有模型的全量 benchmark。repair/edges/bridge 必须按原协议逐题新基线筛选，不得再套用深度实验的整组规则。
- 当前结论边界：10个条件深度组合均迁移边界早于保留边界；固定L16的8个主组合均有部分修复，SC-S提升6.8–43.4个百分点、recut后下降2.2–37.7个百分点。不能外推所有层、全量任务或统一充分机制；历史KO预算精确等价性仍有限制。
- `TASK-COMPLETE` 已存在；小时 `family-depth-watch-01a15016.timer` 和5小时 `family-depth-progress-01a14a9e.timer` 在收尾时均已实测 inactive。本次回读 CURRENT 与完成标记确认关闭记录，不重新连接平台或启动资源。
- HDD 的 Errno122 配额问题未通过清理或调额解决，审计通过纯内存计算与本地小报告绕开，未影响本次交付；精确个人配额仍未知。任何后续删除或大于1GiB下载仍需单独授权。保留原始数据、模型和历史审计。
- 仓库仍有先前遗留修改及未跟踪文件；本次只提交交接新增段，不纳入其他改动。若用户启动新的科研或审稿任务，再制定新步骤；当前没有自动续接动作。

## 2026-10-19 最新指令：只排4090，5分钟监督，完成后同步论文

- 用户取消H卡方案。此前仅阅读help/平台文档，**没有提交H100/H200任务或创建H卡实例**；parallel-plan和launch-state无H卡项，不新增第二套GPU队列。现有四个HDD续接任务均为4090单卡Job，合计最多4卡，仍服从8卡总上限。
- 最新live仍4个job_queuing，表示平台待分配GPU，不是已占卡后的内部实验顺序。保留排队位置，不重提，不修改900/1536预算或attention实现。正式开始以可解析回答text写入为准。
- 轻量监督现改为**每5分钟**：现有family-depth-watch-01a15016.timer的用户drop-in ~/.config/systemd/user/family-depth-watch-01a15016.timer.d/interval.conf，daemon-reload/restart通过，ActiveState=active，TimersMonotonic=OnUnitActiveUSec=5min。原5小时完整检查保留。watch新增各任务首次正式raw、全部正式开始和各done出现的去重queue通知；不把排队当开始，依赖WSL/Codex在线及原expiry，到TASK-COMPLETE停止。
- CPU审计后聚合已实际完成，原始JSONL和报告SHA逐文件绑定、13,845条独立评分0变化。aggregate_completed_supplements.py进一步核对Qwen0.6宽表与raw共10,335条生成条件映射、历史prompt/span、所有28层及可用self-token身份一致。冻结168候选，transfer独立基线eligible125，交集122题/92skills，T/R=11/20。该交集不等于旧主图125，不沿用旧分母；900-token KO历史预算差异仍需说明。
- DeepSeek corrected54 battery/L2/windows独立基线均54题/45groups，repair按1536/split-prefill基线为46题/40groups，不能借用Figure3的54作机制分母。bridge仅2候选中1eligible，不当完整机制样本。identity failures均0；battery和L2各52个缺格均same_family_mean；v2已逐题根据skill标题family和冻结donor池验证全部为结构不可用，unexpected_missing=0，不补不存在的donor。windows/repair有效样本的观测网格无缺失。
- 小产物experiments/family_depth_20261018/aggregated-post-quota-20261019.json与v2分类报告均已取回。新核验结果本轮先落盘，尚不修改论文数值；等4090剩余任务完成、最终完整性/基线/身份/截断审计后，先olcli完整diff纳入云端修改，再更新正文及相关图表、独立编译、同步Overleaf/GitHub，不再导出桌面。反例继续仅保留研究记录。TASK-COMPLETE尚不创建。

## 2026-10-19 已按授权删除Qwen14B，继续补跑与独立审计

- 用户明确授权先删除Qwen3-14B内容。已删除准确目录/inspire/ssd/project/project-public/czxs253130660/models/Qwen3-14B（29个文件，7,599,691,435逻辑字节/7,599,721,984分配字节，约7.08GiB），包括旧未完成下载和少量配置；目录不存在已验证。未删除Mistral consolidated或任何其他数据。删除前文件清单与完成证据audit/QWEN14B-CLEANUP-20261019.json，远端HDD也保存qwen14b-deletion-audit.json。此前提议中的Mistral清理仍未获授权。
- 清理后SSD个人目录du约92GiB（此前99GiB）。新增32MiB probe写入+fsync成功，耗时0.036s；probe保留在ROOT/ssd-after-q14-cleanup-probe-20261019.bin，不私自再删。CPU探针不等于已验证GPU节点写入，也不是完整磁盘基准。
- 对SSD加速的判断：当前所有模型权重始终在SSD，GPU加载路径未迁移；HDD只接收小规模JSONL。Qwen8首块数小时约5MB raw，结果写入量很小，因此不预期仅把结果切回SSD会明显缩短生成。为保留四个现有排队任务、避免迁移路径/重复提交风险，本轮保留HDD输出；SSD已恢复可写供新审计使用。实际GPU耗时尚未做SSD/HDD配对测速，不声称测得加速比。
- 四HDD任务最近仍queuing，未重复提交；原已完成块继续复用。30min watch保持并新增正式raw检查：四任务都有可解析text记录时才queue单独实际开始通知。5h timer保持，TASK-COMPLETE不存在。
- 等GPU期间已启动已完成补跑的独立CPU审计：audit_completed_supplements.py，覆盖DeepSeek corrected54 battery/L2/windows/bridge/repair五suite＋Qwen0.6全部7层块和KO的raw（13文件）。输出ROOT/post-quota-audit-20261019/，日志同名.log，PID元数据同名.pid（timeout进程897054），20分钟上限，不覆盖旧overlay/raw。逐题parser重置、全量逆序一致性和16 fresh-process对照；完成标记AUDIT-COMPLETE。watch已补完成/异常提醒。已实际完成：13文件/13,845回答/changed_labels=0，全部逆序重判及16 fresh-process对照通过。仍须各suite独立baseline/eligible聚合，不把标签核验完成当论文所有实验完成。
- 下一步：核验CPU审计日志/报告、4个HDD Job正式启动与写入；Qwen8/Mistral SSD完整块和HDD补块按manifest/raw哈希联合审计。继续Overleaf完整diff→本地修改→Overleaf/GitHub流程，尚不改论文数值，不导出桌面。反例暂不进paper。

## 2026-10-19 最新同步约定、术语与配额故障续接

- 用户最新要求：**每次论文更新先运行olcli完整行级diff，纳入合理云端修改；本地修改和编译审计后同步Overleaf与GitHub，不再向桌面导出。** 该要求覆盖历史桌面交付步骤，旧交付保留。详细入口OVERLEAF.md；5h检查消息已同步改为新流程，反例仍只记录研究，暂不进paper。
- 已核验关联Overleaf项目6a2cfd49b99635e8e968576a，虽然项目名仍是旧ICLR Skillflow，实际当前稿在overleaf-skillvector/。首次误用paper根作diff导致大量local-only，随后改为17项匹配暂存目录，保存并完整审阅998行真实diff。差异不能单独识别作者；采用云端更准确的历史筛选/重新评估、条件性结论、机制覆盖局限、四主模型+Qwen0.6补充检查等内容，保留用户要求的Intro首段Web语义关联。图3仍7个已核验panel（6主+1补充），不把未审计旧TheoremQA补入。Table2保留云端4模型×2任务矩阵、两Pending单元与归一化深度差；生成器已适配，原数值JSON未改。
- source统一为skill span/skill-position states/skill-position KV cache；reader改为post-skill positions，明确是skill之后的提示词和生成推理/答案token，不是receiver模型。前置token因causal mask不能读skill。Figure2/4、Table3及正文/当前附录一致；切边不删除skill、不抹去已传播的信息。Table3前三行是干预结果对比，并非各有一个mask；路径切断行准确指向query→skill keys。
- 本地编译改Windows Temp，首次通过正文8/全文11页，error/undefined/hbox/vbox均0；云端上传前再次diff核验自首次读取后无新增修改，17文件上传成功，指定nested main独立编译成功。云端PDF也核验正文8/全文11页，0error/undefined/hbox/vbox；ZIP与上传的所有TeX/Bib/PDF逐文件哈希一致，audit/OVERLEAF-TERMINOLOGY-20261019.json。没有新桌面输出。
- 实验新故障：Qwen8原Job16:55于L4块输出写入Errno122 Disk quota exceeded；DeepSeek机制17:03已完成bridge与repair，但创建edges manifest（零字节）失败；Mistral17:14在L28块写入也失败。Qwen0.6重生成与DeepSeek battery/L2/windows已成功。原失败块全部保留，不重启整池，不删文件。SSD df余量不能代表用户配额；CPU小写可成功不等于GPU大写正常。
- HDD新目录/inspire/hdd/project/project-public/czxs253130660/family-depth-recovery-20261019，8MiB写入实测通过。仅复制Qwen8/Mistral完整首块基线和小脚本；quota_recovery_worker验证SSD完成块的条数、raw哈希（如有）、模块哈希和层网格后跳过，只在HDD重生成未完成块。原partial仍在SSD，不拼接残缺raw。Qwen8transfer与KO分成2卡；Mistral补L28块后KO；DeepSeek仅edges。四Job dry-run与提交均成功，最近4个job_queuing，**尚不能宣布实际开始**。名字wt-recover-{q8-tqa,mistral-tqa,q8-ko,ds-edges}-hdd-1019，详细quota-recovery-jobs.json；总卡最多4≤8，未下载权重。
- parallel-plan/launch-state已登记新4任务（总75已提交，含被替代失败Job），quota_recovery注明旧3Job替代关系和HDD完成标记绝对路径。旧计划Qwen8 SSD并行KO从未提交，不能恢复它。watch_progress已改观察HDD与新4Job，旧失败Job由新任务取代；30min监督与5h检查均active。整项实验尚未完成，不建TASK-COMPLETE。
- 下一步：先核验4个HDD任务正式raw/manifest和GPU写入；完成后按SSD完整块+HDD续接块联合审计网格、身份与逐题隔离评分，不混入SSD残缺块。DeepSeek repair独立重判/edges及全部suite人群仍待汇总，Qwen0.6已完成输出待独立审计。暂不承诺全部完成时间，排队和存储条件影响很大。固定99题Llama长度诊断仍未提交，反例只作研究记录。

# 2026-10-19 当前交付与续接入口（覆盖下面历史）

用户最新要求：先将已核验结果更新论文并同步桌面/Overleaf ZIP/GitHub，未完成项记下来继续；新发现机制反例先留研究记录不入稿。整项实验仍未完成，五小时timer保持，勿创建TASK-COMPLETE。

当前稿为五模型/四家族七组已核验深度比较，Figure3/Table2及摘要/方法/结论已同步。原三模型MedCalc＋Llama/DeepSeek两任务；旧三模型TheoremQA在原协议重生成/隔离评分完成前不入当前图表。Figure4/Table1/Table3仍focused Qwen3-8B/MedCalc，其他已跑结果需统一审计后下一版整合。候选池偏差和25题DeepSeek/MedCalc范围已写入稿件。

先读HANDOFF.md顶部、reports/阶段交付与待补清单_20261019.md及experiments/family_depth_20261018/README.md、parallel-plan.json/launch-state.json。总71任务中原64全完成，后7为DeepSeek/TQA corrected54四项与旧三模型TQA重生成三项；新任务最多7卡。最近Qwen8/Qwen0.6已正式生成并保存text/token_ids、prompt/span对齐通过，Mistral排队；不得据job_running/旧里程碑宣称全开始，勿重复提交。

交付目标桌面StillNeeded-WWW2027-v8-VerifiedDepth-20261019，精确ZIP独立编译已通过（正文7/全文10页），正在最后同步与commit/push，先查audit/DESKTOP-VERIFIED-DEPTH-20261019.json确认是否已完成。本阶段用户已明确授权commit/push master，无须等所有后台实验完成；仅提交本次相关paper文件，不带旧DATA-CONSISTENCY修改、env或大实验产物，不碰../howskill/data/cells.json.tmp。

# 下一对话续接入口（2026-10-19）

## 先做什么

继续当前已授权跨家族论文补跑与最终交付；先读HANDOFF.md顶部、experiments/family_depth_20261018/README.md、deployment.json、parallel-plan.json、launch-state.json，live核验后再操作，不依历史进度重复启动。最多8张单卡4090。用户已批准约30GB模型下载，现已完成，不需再下载。旧四个无-s整池已停止，勿恢复/混用。不要碰../howskill/data/cells.json.tmp。

## 当前已核验进度

- 计划已增至64个GPU任务，最近live 59完成、5未完成：Qwen8/MedCalc L2 battery，Mistral/TheoremQA repair，Qwen0.6/MedCalc bundle，以及两个DeepSeek/TheoremQA scorefix深度分片。各未完成单元已有正式生成记录；两个scorefix分片最近22/24行，已单独通知全部正式开始。仍须live核验是否已完成。
- 原Figure3八深度分片全done，完整网格/身份控制审计通过；MedCalc：Llama112题/20组T/R7/18，DeepSeek25题/13组6/21。DeepSeek样本小，不外推benchmark。
- **评分污染已修复验证，不能直接沿用原correct。** latex2sympy2.var会被某题解析从dict变为Symbol，后续TypeError触发official eval回退、False被当0。最小复现parser-state-minimal-20261018.json。独立regrade_isolated.py每题恢复解析器初始globals，42927条/22468唯一输出，逆序全通过、16 fresh subprocess一致，359标签变化。报告isolated-grading-report-20261019.json，远端overlay目录isolated-grading-20261019/；保留原始JSONL，不覆写。
- Llama/TQA修复后仍92题/71组，T/R6/18。DeepSeek/TQA由51变54题/45组，新增00296/00474/00513/00588/00686，移除00320/00321；新增5题缺全层，supplement_depth.py按冻结完整候选池screen补跑两个整skill分片，勿在5题小池重新screen。jobs wt-f3-deepseek-theoremqa-scorefix-s0-1019和s1。
- **还没做完的关键工作**：旧三模型TheoremQA Figure3原始输出也需隔离重判；全部正文suite重建各自protocol下baseline与eligible；必要补齐内容/位置/跨题、重复窗口、bridge/repair/edges。新增5题不能只补depth就结束。核验截断、context预排除、无donor/空样本，并如实报告反例。

## 资源与恢复

远端root=/inspire/ssd/project/project-public/czxs253130660/family-depth-20261018-v1；CPU wt-family-prep-1018，CPU资源空间，23h时限，已在本轮重启并refresh连接。模型在同个人SSD的models，venv在venvs/whitebox/bin/python。GPU workspace可上网GPU资源，project公共科研项目，group4090-2-cuda12.8，quota1,10,100，image ngc-pytorch:25.02-cuda12.8.0-py3。只用inspire skill并以--help为准。

协调器family-depth-launch-01a14a9e.service：已重启用于两个补跑，可能在全部开始后正常退出；先查state/job，不重复提交。launch_when_ready.py最多8卡，20h bounded；原all_started_notification_queued属于旧计划，后续新增单元必须另live核验。五小时timer family-depth-progress-01a14a9e.timer保持，本机WSL/Codex需在线；完成全部实验、论文、交付与push后才创建paper/TASK-COMPLETE停timer。无无限重试。

小结果快照retrieved/snapshot-20261019，263文件，tar26,080,882bytes，sha256 ebcf73efce9c428a156d251d8114993b444b84283d375c935d576a994826f58d。provisional-depth-stored-labels-20261019.json仅结构审计，TheoremQA不能当最终结果。

## 论文展示与交付约束

- 当前已核验稿仍是旧三模型结果；新家族数值未正式入稿。当前版本另存桌面v7，详见audit/DESKTOP-HANDOFF-20261019.json，保留所有旧交付。
- 图1/3橙线统一d=1-q，蓝线rho；R=d首次≤.5。阴影只表示首次边界间隔，保留重新越阈，不称稳定阶段。Figure3当前仅两主线，共同样本检查在Table2/正文；新家族整合须解释人群。所有图表及正文不展示/讨论CI或置信度，Table2亦已取消，勿按旧timer模板恢复例外。原始统计保留。
- 主图统一Linux Libertine O，表格使用正文衬线字体、白底三线表。Fig4左数值热力图、右分组路径损失点图，不恢复旧棒棒糖布局。
- 重复注入已降为一致性检查：468/468与同起点单写token一致，完整source因果前缀下后续写入冗余，不能独立支持维持失败机制。SC/recut要独立验证，注意L24没有L16同样的recut损失。
- Intro仅首段对齐Semantics and Knowledge机器可读skill/tool描述，后续实验不为track改写。参考reports/图表审阅与改进建议_20261018.md与reports/ProblemFormulation与图文核查_20261019.md。
- 查清评分/筛选/实现问题后更新正文；不能为符合旧结论挑样本/层/指标，真实反例须限定结论。完成后向用户报告修复、结果和影响。
- 用build.sh编译唯一投稿版；make_overleaf_zip.py生成精确包，export_review.py独立编译ZIP；export_figure_bundle.py+compile_figure_bundle.py更新合集。核验数值、字体、字号、碰撞、页数、引用与截断，再同步新桌面版本及图表目录。
- 旧check_main_data.py有过时teaserfigure结构断言，不得声称全脚本通过；numeric-only或适配审计须说明。旧values/DATA-CONSISTENCY-20260918.json已有改动，不误提交。
- 整体任务最终只提交本次相关文件并push master，不建PR，不force；当前未完成实验不要打包大结果/权重/凭据。此前其他对话已提交的稿件改动勿重做。

---
以下为历史交接，若冲突以上述入口与HANDOFF.md最新记录为准。

## 2026-10-19 图表美化完成验证

- 四图字体均为LinLibertine常规/粗体/斜体，表格统一9pt及1.22行距、白底；Figure3只保留rho/d主曲线；Figure4为数值热力图＋横向分层点图。后续更新沿用当前集中字体配置和显示规则。
- 论文正文7/全文9页，合集9页；均无error/undefined/overfull。已目视四图及正文/附录表格；PDF文本清理扫描通过，15份数值输入与原稿不变。审计`audit/DISPLAY-STYLE-20261019.json`。
- PDF、Overleaf ZIP和图表包已同步；本轮只提交论文与图表改动，未完成实验目录及旧DATA-CONSISTENCY改动留本地。

- 表格追加要求：正文/附录四张表统一正文Linux Libertine系列，表内9pt/11pt行基准，arraystretch=1.22；表头常规粗细区分但不换字体，保持白底。合集使用同一tabular字体钩子。

- 字体追加要求：四图统一Linux Libertine（与acmart正文/表格同系列），含常规/粗体/斜体及数学符号；由tools/figure_fonts.py集中配置。PDF嵌入字体检查四图均仅LinLibertine，不再混用DejaVu Sans。复现需Linux Libertine或PAPER_FONT_DIR，缺失时报错。

- Figure4追加可读性改进：左侧改为四干预×四层的带数值热力图（0–100%固定色阶），右侧按层分组的横向路径损失点图，去除棒棒糖竖线。原始16+9个数值及样本不变，Table3保留派生差值。热力图颜色编码数据，普通表格保持白底。

- 追加要求已落实：Figure3去掉common-item check两条虚线和图例/图注，只保留rho与d主曲线；共同样本Table2和正文检查保留，半效应参考线保留。

## 2026-10-19 图表展示与排版新约定（覆盖旧显示要求）

- 用户要求当前全文和图表不再展示或讨论CI；已删除主文、当前附录、Table2中的对应数值和方法说明。源结果JSON保留，点估计与样本不变。
- 后续所有正文、附录和图表包均沿用纯点估计展示，Table2也不例外；表格取消所有底色，使用三线表、较大字号和行距。图中表示深度区间的浅色区域保留，因为它不是表格底色或统计区间。
- 四张主图字体与画布高度已适当增大，精简图例避免拥挤；d=1-q不变。正在重编译检查页数、文字碰撞和原始数值，随后同步PDF/ZIP/图表包并提交。

## 2026-10-19 Problem Formulation与图文重构（当前任务）

- 用户要求精简定义、可读公式、统一实验小标题及图文匹配检查。已按Setting→S/C→knockout→metrics→boundaries重构；source token集合mathcal I避免与干预S重名。新增cache/knockout/boundaries公式，dose和delta移附录。
- 实验subsection/paragraph统一名词短语；压缩重复定义。四图三表保留：Fig1概览重复有明确用途，Table3展示派生差值而非重复原点值；Fig4说明等距层组和零点竖线；Table1补匹配前缀提示。
- 重复注入降为一致性检查，保留测值，不再作为独立“维持状态失败”证据。详细报告`reports/ProblemFormulation与图文核查_20261019.md`。后续仍统一d=1-q；新家族结果尚未入当前稿，不混入未完实验。
- 最终验证：audit_three_display_revision.py通过，15份数值输入不变；源数据/边界额外SHA检查通过。论文正文6/全文9页，图表合集9页，均0 error/undefined/overfull；第2–3页公式/图注已目视核查。PDF、图表包和ZIP已同步。审计`audit/FORMULATION-REVIEW-20261019.json`。本轮完成后提交推送；既有实验目录和旧DATA-CONSISTENCY改动不提交。


## 2026-10-18 用户授权立即提交推送

- 覆盖此前等待整个远端实验完成才提交的安排：现提交已完成论文、dependence图表与交接；family_depth_20261018未完成实验及cells.json.tmp留在工作区。
- 当前显示审计通过：15份数值输入不变；论文/合集编译与dependence曲线审计已通过。额外尝试旧check_main_data.py在第108行因硬编码要求teaserfigure而中止，当前稿使用figure*；这是旧版结构检查不适配，不能报告该脚本通过。旧DATA-CONSISTENCY清单不作为本次最新验证，不随本次提交。


## 2026-10-18 用户确认：后续统一dependence展示方案

- Figure1/3橙线统一为source-attention dependence d(L)=1-q(L)，即筛选后原本答对的题中累计knockout后变错的比例；蓝线仍为恢复率rho。Problem Formulation正式定义d。
- 后续新增模型/任务、主图和图表包均沿用此方案，勿恢复为橙线q。原始JSON和统计代码继续存retention=q，在展示层取1-q；不改变筛选、人群、分母或已有T/R与CI。R定义为d首次≤0.5，与旧q首次≥0.5等价。阈值敏感性中q的τ须对应d的1−τ。
- 中间条件rho<0.5且d>0.5；阴影仅是首次边界之间，保留重新越阈。dependence包括reader访问与source自身更新，不能写成纯reader路径效应；d−rho不能当逐题比例。
- 本轮只落实该展示与定义修改，既有新家族远端实验仍按原交接继续。

- 本轮验证完成：24条绘制曲线逐条与rho/1-q核对，12套人群边界检查通过；原始depth JSON和Table2文件SHA256不变。审计`audit/DEPENDENCE-DISPLAY-20261018.json`。论文编译正文7/全文9页，0 error/undefined/overfull；图表合集9页，0 error/undefined/overfull。Figure3已目视检查。主PDF、图表包及Overleaf ZIP同步更新。

## 01:24最新状态

8张Figure3卡全通过预检并产生正式基线记录，共367条。DeepSeek/TheoremQA s1-r1已恢复，其他七卡未重启；GPU确实在正式工作。Figure3已全开这一事实已告知用户；其他正文suite尚在依赖队列，等它们也全实际开始后另行通知，不混同两个里程碑。最多8卡、每5小时检查、自动做到论文/GitHub闭环的授权继续。

## 01:20补充

用户明确后续本任务全部操作无需确认，直接自动完成。最终最多8卡。八个新任务中DeepSeek/TheoremQA s1预检失败（非有限logits），已换r1并排除gpu097，其他七卡继续；同任务s0过控制。以parallel-plan.json和launch-state.json当前映射为准，核验r1实际过控制，不把失败当开始。失败历史保留。

# 当前入口覆盖说明（2026-10-18 01:17）

先读HANDOFF.md顶部。最新上限是8卡，当前权威方案parallel-plan.json：8个新家族Figure3分片＋44个后续GPU任务（Qwen0.6同卡双进程），按依赖就绪排队，最多8占用。新八卡均已提交，尚需核验实际运行/正式生成；不要重复启动。最早四个无-s整池Job已停止，仅保留历史部分输出，不混入新分析。权重均已下载完成且下载获用户明确批准；旧“待下载确认”记载作废。

协调器family-depth-launch-01a14a9e.service和每5小时timer继续；全部正式单元实际开始后单独通知用户，不能把排队当开始。新CPU wt-family-prep-1018已可用，23h自动停止；协调器20h后需核验续接。瞬态service停止后会被回收，必要时systemd-run重建。paper文字/排版v6已同步桌面，但新增结果尚未入稿。整个任务完成后再commit/push。

---

# 2026-10-18 当前续接覆盖入口

最新任务仍在执行：用户已授权新增Llama/DeepSeek原生家族，先跑Figure3，启动后让同一批模型覆盖全部正文实验。只改Intro首段对齐Semantics and Knowledge，不为track改实验。Table3及后续所有图表不显示置信区间、误差条和相关说明，Table2原区间保留。

先读HANDOFF.md顶部与experiments/family_depth_20261018/README.md、deployment.json。冻结候选MedCalc446、TheoremQA255；四个单卡Job配置已备；新的个人SSD源码快照已展开。用户随后已明确批准约30GB权重下载并要求预检通过直接正式实验。DeepSeek官方与Llama公开原版分发均已后台下载，coordinator负责done后自动提交Figure3/probe与基线screen后的全部正文后续任务（最多8单卡）。Llama四权重分片/配置/词表与官方哈希一致，但tokenizer_config.json为不同公开分发配置，已记录来源。先读launch-state.json与服务状态，不重复下载或提交。新CPU wt-family-prep-1018已连接且共享盘读取通过，23h自动停止，coordinator已切换；权重下载仍在旧wt-paper-fetch-1017，不提前停止。DeepSeek输入长度预检仅MedCalc00874不支持900生成预算，事先排除并记录，不能无说明截断。

每5小时timer family-depth-progress-01a14a9e.timer已active，首轮2026-10-18 05:21 CST，最长14天；完成全部实验/论文/桌面/GitHub同步后才建TASK-COMPLETE停止。依赖本机WSL与Codex通道。旧机制timer不要恢复。

本轮已修Related Work重叠、Table3区间、图4图注、Intro track首段；原始数值未变。cut/recut解释在reports/cut-recut实验说明_20261018.md。任务整体未完成，不commit/push；不碰既有howskill/data/cells.json.tmp。

以下为此前完成版本历史，关于不新增实验的旧边界已被本轮用户授权覆盖。

---

# 新对话交接：WWW2027 源缓存与持续读取版

更新日期：2026-10-18。工作目录：`/home/vanius/proj/agent-harness/paper`。

## 先看什么

1. 本文件与 `HANDOFF.md` 顶部。本文件是本轮独立交接入口，历史章节只作溯源。
2. `main.tex`、`sections/00-abstract.tex`、`sections/01-introduction.tex`、`sections/04-experiment.tex`、`sections/05-conclusion.tex`。
3. `paper figure/README.md` 与 `paper figure/Figures-and-Tables.pdf`，快速核对四图分工和最新表格。

## 用户原始目标与本轮边界

- 以三图三表版（提交 `141c8fb`）为基线，按用户截图改为四张图：teaser、详细干预设计、六组深度结果、恢复与读取机制结果。上一版 `be06dc4` 的重复注入主图不采用，旧文件保留归档。
- 全文叙事自然清楚，skill优先于document/procedure，先解释术语，避免重复数字、过度防御及未经定义的现象名称。实验保持4.1 setup、4.2探针验证、4.3深度分离、4.4机制这一顺序。
- 引言以独立 `Relevance to the Web and to this track.` 段落开头。摘要聚焦科研发现。
- 遵守WWW2027标准acmart匿名双栏格式，正文不含references/appendix最多8页，全部最多12页。
- 新维护 `paper figure/` 文件夹，包含最新版图表、解释、LaTeX代码、绘图代码和可用数据。任务完成后同步桌面与GitHub，提供新对话交接。
- **不得自行新增实验。** 若后续认为需要推理，先告诉用户。本轮没有新增推理、模型下载或Inspire操作。

## 当前稿件与交付入口

- 标题：Still Needed, Hard to Transfer: Using and Reusing Contextual Skills。
- 权威源：本目录 `main.tex` 及递归加载的源文件；只维护一个投稿版。历史扩展版不编译、不交付。
- 最终稿：`skillvector-www2027.pdf`；上传包：`overleaf-skillvector.zip`，ZIP根目录有main.tex，使用pdfLaTeX和BibTeX。
- 最新桌面交付：`C:\Users\12970\Desktop\StillNeeded-WWW2027-v5-SourceCaches-20261018`，WSL对应 `/mnt/c/Users/12970/Desktop/StillNeeded-WWW2027-v5-SourceCaches-20261018/`。
- 桌面另维护 `/mnt/c/Users/12970/Desktop/paper figure/`，与仓库 `paper figure/` 内容一致；主交付目录内也附同一图表文件夹和本交接文档。
- 旧v3、v4及更早桌面目录保留，不是当前入口。

## 本轮修改完成了什么

1. **中心认识收敛。** 摘要、引言和结论强调：残差状态迁移受配套源位置KV缓存和后续源读取影响。联合替换只替换源残差及源位置缓存，没有重放接收方全部计算历史。
2. **Figure 1 teaser重画。** 展示早层0.89恢复、共同样本上的迁移/依赖分离、L16源缓存联合替换部分恢复与recut损失。三个panel样本分别135、134、114题，不能解读为同一批题的逐题过程。Figure 1与Figure 3现统一画source-attention dependence d=1-q；后续新增模型和绘图均沿用此方案，原始retention=q字段保留，展示时取补数。
3. **Figure 2详细设计新增。** 正确skill donor向wrong-skill receiver提供源残差S、源位置KV缓存C（0至L层）或两者SC，保留早期reader计算；原donor从L开始切断，SC后reader recut从L+1开始。reader指skill span外的question/answer token。
4. **Figure 3深度与Figure 4恢复结果保留。** 数值不变，图号顺延，配色/字体统一。重复注入保留正文说明和附录结果，不再单独占主图。
5. **4.3标题改为** Residual-state transfer weakens before source dependence subsides。**4.4改为** Testing source caches and continued reading。
6. 修正L≤23表述，明确这是切断起始层，从L一直屏蔽到最终层，覆盖prefill与decoding。
7. 修正附录13/14层错误：group screen均约0.16，item screen为0.32/0.34，不能说两种筛选都相同。
8. Table 2新增现有skill-group bootstrap的边界差95%区间，全部来自已有JSON，不是新实验。Table 3保留已有机制差值区间。
9. 附录补回TheoremQA重复注入：99题/75skill；8–11、12–15、14–19、16–35窗口分别0.8387097、0.6129032、0.3763441、0.2043011，L16单次也是0.2043011。原始tag为t8-win+tqa-span，兼容基线合并后应用receiver screen，已重新计数。

## 关键结果与不可越过的解释范围

- 3模型：Qwen3-8B、Qwen3-0.6B、Mistral-7B；2任务：MedCalc、TheoremQA。全深度曲线均实测。
- 主要早层battery：135题/14calculator，donor准确率0.9185、receiver为0、L8 span准确率0.8148，恢复约0.89。
- Qwen3-8B/MedCalc共同样本134题，首次半效应边界T/R=13/25；其他五组方向一致。边界是首次越阈，不是强制单调阶段，L26 retention有重新跌破阈值。
- 机制实验同114题/14skill：L16 S=4/114、C=8/114、SC=48/114、SC+recut=8/114，对应3.5%、7.0%、42.1%、7.0%。
- L24 SC=25.4%、SC+recut=27.2%，**没有**观察到与L16相同的额外recut损失，不能将L16结论泛化全层。
- L24 donor reader-cut仅保留29/114正确，self-cut保留110/114；这支持该层继续读取的重要性。
- 样本按未干预基线筛选，主要估计是条件因果效应，不是完整benchmark平均收益。现有任务是模型级技能问答，没有浏览器交互任务评测，首页Web相关性不能替代该证据。

## 验证状态

- 最终正文 **6页**、全文 **9页**；四图在第2、3、4、6页，均在正文；3张主表，附录另1张表。
- 最终工作稿构建：`/mnt/c/Users/12970/Desktop/WWW2027/build-skillvector.vMZtK0TQ`。0编译error、0undefined reference/citation、0overfull hbox/vbox，字体全部嵌入，未改正文版心、字号、行距。
- 图表合集独立编译：`build-figure-collection.mbbsip3y`，9页，4图4表，0error/undefined/overfull hbox。合集不是投稿稿，不受正文页数定义约束。
- `python3 tools/check_main_data.py --numeric-only`：132702检查/489源文件通过。此模式跳过旧稿exact-wording断言，保留数值重计数与原始数据核验。
- `python3 tools/audit_three_display_revision.py`：15份原数值输入逐字节不变；三张主表（含Table2 CI）、teaser曲线及条宽、TheoremQA窗口均核验通过。
- `python3 tools/audit_citations.py`：27实际引用/58 bib/11 TeX，无缺键或重复label。
- 独立上传ZIP编译和桌面交付证据：`audit/DESKTOP-SOURCE-CACHES-20261018.json`。ZIP共17项，SHA256为 `c634d89f30c6ca4194a01cf801e9c4cbcec9e984ad53d59664a112329dbe7400`；独立编译目录为 `build-overleaf.8ughln0x`，正文6页/全文9页、0error/undefined/overfull。逐项一致性和最终格式仍以该审计文件及会话核验为准。
- 科研审计：`audit/FOUR-FIGURE-STORY-20261017.json`、`audit/TEASER-CACHE-READING-20261017.json`；文件名保留制作日期，不表示旧版入口。

## 日常维护命令

```bash
# 图1、图2；图3与图4如需重绘也有对应脚本
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/fig_teaser.py
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/fig_intervention_design.py
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/style_main_figures.py
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/fig_mechanism_results.py
python3 tools/build_boundary_table.py
python3 tools/audit_three_display_revision.py
python3 tools/check_main_data.py --numeric-only
python3 tools/audit_citations.py
bash build.sh
python3 tools/make_overleaf_zip.py
python3 tools/export_figure_bundle.py
```

`build.sh`调用Windows MiKTeX并在桌面创建新暂存目录，可能需要沙箱审批。不要删除旧stage。导出用 `tools/export_review.py`，必须选择新目录，独立编译ZIP后才创建交付目录。

**不要直接运行旧 `style_main_tables.py` 或 `point_estimates.py` 批量覆盖当前表格。** 它们保留历史point-estimate策略，会剥掉用户刚要求保留的Table2区间。当前Table2由 `build_boundary_table.py` 维护，其余表格从正文导出。

图表包刷新由 `export_figure_bundle.py` 负责；独立合集用 `compile_figure_bundle.py`，编译后再次刷新包manifest。图表包内source目录为快照，权威脚本在tools，权威数据在values/及figures/的JSON。

## 进程、Git及续接

- 本轮所有工作为本地编辑、制图、重计数和编译，无远端模型推理，无新增定时任务。最终交付后无需等待计算结果。此前Inspire资源状态不由本交接文档做实时保证。
- 仓库为Vanius0525/SkillFlow，使用master，不建分支或PR。任务完成按用户长期授权commit并push，不force、不rebase他人提交。
- 原有未跟踪 `../howskill/data/cells.json.tmp` 与本轮无关，不读取、不提交、不删除。
- 提交/推送是本轮最后一步。新对话用 `git log -1 --oneline`、`git status --short`、`git rev-parse HEAD origin/master`确认完成提交已同步。本文件随完成提交入库且两者一致时，本轮已闭环，不要重新启动实验或自动大改稿件。
- 用户若继续提出修改，在当前v5上推进。若想加强全部receiver历史、其他模型上的SC机制、或真实Web任务，需要新实验时先报告方案与缺口，不自行启动。

## Open Ideas / 值得深挖的问题

本轮没有新增实验发现。已有L24 recut无额外损失的现象继续保留：不同深度的缓存修复与继续读取关系可能变化，但现有稀疏机制层不能确定转变位置或一般规律。后续若研究，应先设计固定样本的层间对照，并取得用户对新实验的授权。
