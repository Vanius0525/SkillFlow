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
