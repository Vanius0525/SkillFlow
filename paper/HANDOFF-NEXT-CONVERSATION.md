## 2026-10-24 Table 3最终格式

用户要求仅SC三个深度的每行最大值加粗（并列保留），并移除n/G列。已删除Table 3该列及表注定义，数值、其他表与正文不变。原生OT记录见reports/table3_sc_only_20261024与reports/table3_drop_ng_20261024；同步Overleaf、更新PDF后推GitHub。

## 2026-10-24 附录压缩新基线

本轮用户授权附录压缩、Table 3加粗、同步Overleaf/GitHub已落实。正文仍8页，全文由15页压至12页；六个现有文档原生OT更新、云端编译通过。旧补充表保留源文件但不再input，未删文件。正文除一条失效附录说明及Table 3格式/表注外不改。完整说明/回执reports/appendix_compression_20261024；当前PDF skillvector-www2027.pdf。下面旧15页状态已被本节覆盖，全部实验/监督仍结束，不恢复。


## 2026-10-24 新对话接管入口：周期检查已由用户明确取消

本节为最新状态，覆盖下方全部历史运行/排队/自动续接描述。用户当前只要求取消周期检查并整理交接；本次不再修改论文或启动实验。

### 运行与取消状态

- 两轮科学实验均已完成：初轮Qwen3-8B/MedCalc为6076条正式结果+14条gate；扩展轮为七组合10944条正式结果，复用原Qwen/MedCalc组成4模型×2benchmark。八cell共580个模型—题目配对，不是580道独立题或全benchmark。
- 两轮均有独立进程重判与完整性审计；七新cell的逐题二值标签、截断数、完整条件键集合及全部新bootstrap区间还在本地再次核验。小产物46个JSON/60257字节归档已取回；原始回答/模型张量留远端，不需重跑。
- 2026-10-24 15:00确认本对话三小时与旧小时timer/service均不存在或inactive。两实验目录均写入SUPERVISION-CANCELLED；TASK-COMPLETE和SUPERVISION-COMPLETE保留。取消证据：experiments/state_core_matrix_20261024/supervision-cancellation.json。旧watch配置本地已标cancelled_by_user，不提交运行时配置。
- 迟到通知只去重，不恢复CPU/GPU、timer或旧控制器；旧depth①仍取消，不操作LogicBench或其他对话family任务。科学七Job和备用只读产物导出均SUCCEEDED并释放，两个专用CPU已stop；CPU HPC两失败记录保留不删。没有待继续的实验或观察任务。

### 论文与Git当前基线

- 完整八cell结果已同步Overleaf和GitHub，实质交付提交721274e（master）。Overleaf项目6a2cfd49b99635e8e968576a，根文档overleaf-skillvector/main.tex；本地活动稿为paper/main.tex，PDF为paper/skillvector-www2027.pdf。
- §4.4正文Table3覆盖八cell×Wrong/Neutral的接收基线、C_all、SC8/16/24、其他prefix KV、完整prefix KV和后续prompt重算。附录Table7列基线与token身份，Table8列层间差值/95%CI/截断。字体9/11pt、浅蓝表头、线型与原表统一。
- 共七现有文本文件有新增/更新：Experiments、appendix/b-full-dataset-rerun、appendix/cache-coverage、Abstract、Introduction、Discussion、Conclusion。旧公式/证明、Related Work、旧图/表数据保留；原S迁移/KO依赖结果未被新SC结果替换。
- 云端编译通过，全文diff一致，无未定义引用或水平越界；正文8页、总15页（旧13页），超仓库12页目标。附录仍有1.474pt微小竖向排版告警，目检无裁切。当前是结果完整草稿，不是满足篇幅的最终投稿稿。
- 首选阅读：reports/state_core_matrix_20261024/论文修改清单.md、完整结果与解释.md、paper-data.json；核验入口audit/state-matrix-paper-20261024/delivery.json及manuscript.patch；逐题/矩阵证据experiments/state_core_matrix_20261024/retrieved/matrix-audit.json与export/。

### 结论边界与术语（不可在续接中丢失）

- 完整skill缓存指所有skill token位置、所有层的KV，不是全层/全位置residual。SC包含单层source residual与低层KV补写；本轮全source KV精确对齐，SC_exact再次覆盖不改变3480对输出。题目/模板等其他位置KV仍可能编码之前处理skill的历史；不能称为“与skill无关的信息”。
- 八cell的C_all均低于donor，完整prefix KV复制1160/1160对token复现donor；后续prompt重算准确率距donor不超过4.2pp，但不是token身份，也不是廉价可部署方法。Qwen/TQA replay62/63略高于donor61/63，已保留该数值反事实。
- SC8−SC24在六cell的两背景点估计均正；Llama/TQA为−5.4/+6.5pp、DeepSeek/MC为+8.3/−8.3pp，这四项CI都跨0；Qwen/TQA中性CI下端为0。只有五cell两背景区间均严格正，区间探索性且未多重比较校正。不得写普遍早层更优，也不能据小幅反向声称晚层更优。
- 这些边界限制的是新增SC深度效应的推广，不是原文S迁移vsKO依赖曲线T<R的直接反例。本轮没有重测原完整曲线（①已取消）。内容与等层窗口控制仍仅Qwen/MedCalc；margin充分条件、未见skill预算预测和最小必要状态均未验证。各cell历史题池不同，不可把差异直接归因于模型架构。

### 后续操作约定

- 等待新对话的具体用户指令。最明显剩余问题是15→12页篇幅与微小排版告警；本次没有授权自动压页、再开实验或重启监视，不把候选工作当已启动任务。
- 每次改稿先完整olcli diff，保留协作者修改；不要从旧/tmp快照盲目上传。当前文本使用tools/update_overleaf_text.mjs原生增量编辑，保留doc ID；History2444–2454的11条操作已回放重建七最终文件，不是整文件上传或Track Changes逐条接受/拒绝。
- 工具位置按JavaScript UTF-16 code units，不能按UTF8字节。已修复curly apostrophe导致的偏移；tools/overleaf_text_edits.test.mjs覆盖此回归。只允许已验证的ASCII编辑payload，原文Unicode上下文可定位；未验证中文插入/删除会提前拒绝。遇回读失败先查实际版本和receipt，不盲重发。
- 工作区仍有其他对话的未提交改动，不能整仓git add、reset或覆盖；本轮只提交自身交接前缀/取消标记。遵守删除/较大下载需确认、只推master且不用force。临时备份在/tmp/state-matrix-paper-20261024-active-before，不能把/tmp当唯一持久基线。

以下保留历史交接，仅供溯源，不构成运行指令。

## 2026-10-24 完整八组合结果已入稿，科学实验全部收尾

核心24条件七新cell10944/10944均SUCCEEDED并完成独立进程审计；46小JSON/60KB归档取回，本地逐题标签/截断/全部新paired bootstrap及完整键/身份/哈希声明核验通过。复用Qwen/MedCalc后八cell580模型—题目配对；SC_exact3480对输出token一致、完整prefix1160对复现donor。六cell两背景早减晚点估计正；Llama/TQA与DeepSeek/MC不稳定，Qwen/TQA neutral CI触0，不能写统一深度规律。原始回答与KV保留远端，无推理重跑。科学任务和只读收集均已结束，专用CPUstop，HPC两失败记录保留；TASK-COMPLETE/SUPERVISION-COMPLETE存在、三小时timer inactive，迟到通知仅去重，绝不恢复旧任务。
用户授权的新论文任务已完成Overleaf增量同步：§4.4 Table3扩成八cell×两背景，附录Table7基线/身份与Table8区间/截断，abstract/intro/discussion/conclusion最小新增衔接，coverage只更新BF16经验核验范围。共7现有文本文件，旧公式/证明、related work、旧图与旧表数据不变。docID保留、无整文件上传；History2444–2454共11条操作回放重建7份最终稿。摘要Unicode位置偏移已修复为UTF16并添加回归检查；ASCII编辑payload之外提前拒绝未验证编码。
最终完整olcli diff无差异，云端编译无未定义引用/水平越界，表格列宽与9/11pt/浅蓝表头/线型统一，已目检。正文仍8页、Table3第8页，总15页（旧13页，超仓库12页目标）；为尽量保留原文未删旧内容压页，未声称满足投稿页数。附录仍有1.474pt微小竖向排版告警，无表格裁切。PDF skillvector-www2027.pdf；科学结果/逐节文字修改清单reports/state_core_matrix_20261024；全差异/History/编译证据audit/state-matrix-paper-20261024。本地只同步7文字+PDF，旧版本/tmp/state-matrix-paper-20261024-active-before。Git交付提交以git log为准，仅纳入本轮文件，不含其他线程改动。下一步若用户要求再处理篇幅，不自动开新实验或恢复timer。

## 2026-10-24 核心24条件七组合扩展已启动，七GPU均RUNNING

用户授权直接运行并每3h检查。入口experiments/state_core_matrix_20261024/HANDOFF.md、launch-state.json、monitor-state.json；七个wt-sc24-{cell}-1024任务已唯一提交且00:30均RUNNING，正在各自gate，随后自动正式生成+独立进程审计，不等人工gate许可。Qwen/MedCalc旧结果复用，取消depth及其他实验不恢复。固定历史457候选，输入预检仅DeepSeek/MedCalc排除1题，正式456题×24=10944条；不是每组124或全benchmark。源码约44KB压缩包随GPU命令部署，已有共享输入逐SHA验证，不下载模型、不依赖Notebook，两个专用CPU均已STOPPED。三小时state-core-matrix-3h-01a162f7.timer active，首次约03:16 CST；观察已实测七任务状态与gate进度，无failed。7天监督到期须明确报告，完成停，依赖WSL/systemd/Codex在线。所有生成尚未完成、不提前做科学结论；后续取回小audit、cells/manifest与二值标签，独立核验完整矩阵。论文上一阶段已Overleaf/GitHub同步875119b，本轮不自动改稿。无需新许可，后续按定时消息继续真实监督，绝不重复提交或重跑已有记录。

## 2026-10-23 状态完整性结果已入稿并同步Overleaf

用户授权最小正文更新、同步Overleaf/GitHub，未启动新实验。两次完整olcli diff确认线上基线未变，以最新23文件为基线。实际正文§4.4新增完整source对照段落与单栏Table3（124题，两背景；C_all/SC8,16,24/其他位置/完整prefix/后续重算），与原114题八组合结果明确分开。附录B加内容/8层窗口、组级区间/截断/审计；coverage改过时BF16句；Discussion更新已完成方向。数学公式、原八组合图表、摘要引言结论均未新改。
四个原有doc用editor-socket/applyOtUpdate增量编辑，docID不变，各v0→v1。History2440–2443含文本操作，独立回放重建准确；非整文件上传，也未声称Track Changes。最终完整diff无差异，云端PDF13页、新表第7页、旧机制表顺延Table5；log无未定义引用或Overfull，新表已目视检查样式一致。当前23文件与PDF同步活动稿，旧本地备份/tmp/state-paper-update-20261023-active-before。审计audit/state-paper-update-20261023；报告reports/状态完整性入稿与扩展预算_20261023.md。
新增正文最小24条件/题；连同新增附录为41条件/题。按原轮约34GPUh/49条件，剩余7组合各假设124题，分别约120/200GPUh（2卡约2.5/4.2天，4卡约1.25/2.1天），仅计生成，不含排队/适配/审计，题量与速度需实测。不是全benchmark逐题跑，无未见skill预测验证；原①全层depth保持取消。接下来只完成本次Git提交推送与交付，不自动开新实验。

## 2026-10-23 Overleaf最新版只读核查完成

补实验已完成并以b7e4781提交推送；没有把新结果写入论文。本轮先保存完整olcli diff，再下载线上23文件与12页PDF，核对10月21日哈希基线及10月20日Git稿件。线上原机制正文Table3现为附录Table4（第11页），这一移动在10月21日已有；主要数学公式仍正文，共16个equation环境与10月21日逐字相同。线上新增Discussion、Figure4八组合，不能用旧本地单案例版覆盖。
新实验主要应更新§4.3及一个独立聚焦对照展示，原Table4八组合数据保留，C_all不可写入原C列。具体说明：reports/Overleaf版本核查与更新留痕_20261023.md；最新源/PDF/hash/full diff：audit/overleaf-review-20261023/。没有上传或覆盖活动稿。
用户希望云端行级留痕：当前olcli push已源码确认整文件替换，本地diff不是云端编辑日志。未来正式文本更新先验证增量编辑与History实际呈现；Track Changes是不同功能，权限未核验。本轮未打开项目History时间线，不声称识别作者或已验证上传条目的细粒度呈现。

## 2026-10-23 晚间恢复观察与独立审计（进行中）

- 处理17:00迟到通知时实际已21:48。原CPU wt-family-prep-1018为timedShutdown STOPPED，两次start均平台InternalError，不再盲重试。通用wt-dev-cpu只读探测未成功，未启动任何其他实验。
- live Job已确认两份SUCCEEDED：repair0 17:36:15结束、repair1 15:23:34结束。不能再称仍运行/排队；待读取done/hash和独立审计后才确认完整生成及结论。
- 一次notebook create请求超时，平台留下两个同名wt-state-observe-1023（21:47:43与21:47:08）。新建多余实例已stop成功，保留较早21:47:08、cpu-nat-132运行实例，4CPU/16GiB，8小时auto-stop。平台同名连接的--pick在cached/live两层不一致，CLI exec/scp交互选择失败；改用CLI成功导出的SSH配置/tmp/state-observer-audit.ssh，Host state-observer-audit，直接ssh已验证OBSERVER_READY。
- watch.py支持observer_ssh_config，watch-config已切新CPU与该SSH配置，原小时timer未恢复depth。CPU仅用于本轮观察/审计，不占GPU；不删除任何实例或数据。
- 本地新audit_results.py已上传，正在独立CPU进程核验两份完整键网格、源文件SHA、全部正序/逆序评分、gate身份/完整复制、source/other缓存精确写入、截断与按skill整组bootstrap。远端目标SSD v2/independent-audit.json；当前SSH审计进程会话41107待取输出，不重复启动新审计或生成。
- 下一步：检查审计进程结果，取回小JSON；若检查失败先诊断，不声称已通过。随后watch --no-notify验证完成与timer自停，再给可读结果说明并更新交接。原GPU/已取消depth/其他实验/论文均未操作。

## 2026-10-22 LogicBench基线与监督已完成（当前有效）

四模型各2240条，独立重判/完整网格/唯一键及done/summary/raw SHA256全部通过；小摘要已取回。监督timer已自动停止，迟到通知忽略。Qwen入选78题中13题涉及截断，四模型原入选共同交集仅6题，后续设计须处理；不自动启动深度矩阵。详见experiments/logicbench_20261021/FINAL-REPORT.md、final-audit.json与HANDOFF.md。其他实验/论文未操作。

## 2026-10-21 新对话接管：LogicBench运行中，周期检查已取消

- 用户最新要求：更新交接，由新对话接管；取消本对话周期检查。只继续本轮LogicBench，不操作其他实验、不更新论文；不恢复任何旧timer。延迟的旧监督消息一律忽略。
- 当前入口：`experiments/logicbench_20261021/HANDOFF.md`；最新实测状态：`experiments/logicbench_20261021/monitor-state.json`（2026-10-21 17:50 CST）。
- DeepSeek已完成2240条并经独立进程重判；全760题gold 66.32%、none 57.37%，有效89题/15skill。Mistral 2043/2240、Llama 998/2240、Qwen 360/2240，均RUNNING。Llama当前Job为wt-logic-llama-1021-r1，原911条已复用。
- 已停止logicbench-hourly-01a1587f.timer；systemctl --user list-timers --all显示0 timers。SUPERVISION-CANCELLED与watch-config.json.cancelled_at防止误恢复；不因新对话接管自动重建周期检查。GPU Job继续运行，没有停止实验。
- 下一步先查询四个现有Job并读取远端outputs中的progress/summary/done；不要再次提交整池。远端个人HDD：/inspire/hdd/project/project-public/czxs253130660/logicbench-20261021-v1；观察CPU wt-family-prep-1018，保留自动停止设置。CPU不可用时先诊断观察通道，不当作GPU失败。
- 本次交接仅保存代码/数据快照及小摘要，原始输出留远端。仓库另有其他对话/历史稿件改动，不纳入本轮提交、不覆盖。正式深度矩阵尚未启动；先完成四模型基线并核验真实结果。

## 2026-10-21 最新指令：CHAMP已放弃并清理，第三benchmark重新选型

- 用户明确要求放弃CHAMP并删除相关内容。本轮新建本地experiments/champ_20261020、三处远端专用实验/探针目录、4个/tmp临时产物及4个已终态wt-champ-*-1020平台条目已删除；原始结果不再作为续接或paper候选。仅保留experiments/benchmark_replacement_20261021/中的简短删除回执和替代调研。
- champ-hourly-01a1587f.timer清理前已inactive；没有活跃CHAMP监督。迟到的CHAMP小时/完成消息只报告“已按用户要求放弃和删除”，不要访问已删目录、重建代码、恢复timer或重新启动实验。
- 原4主模型×2benchmark论文保持当前版本；共享历史SRA资产和评分模块未扩删。第三benchmark重新比较，尚未授权本轮启动新GPU；按现有任务形式、skill来源、客观评分和样本覆盖筛选，不能以T<R或修复正结果挑数据。
- 当前入口experiments/benchmark_replacement_20261021/HANDOFF.md，删除范围与回执见cleanup-local.json/cleanup-remote.json。已交付reports/第三benchmark替代调研_20261021.md：优先静态核查GSM8K+21类公开模板；LogicBench为条件备选，先解决组级筛选一致性。未启动新实验。

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
