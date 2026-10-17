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
2. **Figure 1 teaser重画。** 展示早层0.89恢复、共同样本上的迁移/依赖分离、L16源缓存联合替换部分恢复与recut损失。三个panel样本分别135、134、114题，不能解读为同一批题的逐题过程。Figure 1画source dependence=1-q，Figure 3画retention=q，方向不同但标签和图注已说明。
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
