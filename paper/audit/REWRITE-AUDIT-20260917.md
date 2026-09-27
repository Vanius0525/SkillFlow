# 正文重写与核查记录

日期：2026-09-17。

## 完成的改写

- 正文严格采用五节：Introduction、Related Work、Problem Formulation、Experiment、Conclusion。
- Introduction 依次说明研究问题、行为与几何之间的 paradox、拆分与答案格式实验、skill span 的核心发现、rank 与深度的进一步验证。按用户后续要求，贡献最终合并为三项：定位、rank、转移/读取的深度分离。
- 主线明确为：skill 是否形成单向量或多位置表示 → 哪些表示能恢复行为 → 所需 rank → 注入深度与继续读取的差异 → 跨模型和任务复现。
- 新增统一的 Problem Formulation，定义对照、donor/receiver、位置集合、span 矩阵、注入剂量、恢复率、中心化截秩与充分性/必要性。
- 正文和附录均无独立 Limitations 章节；原有适用范围、阴性结果、修复前后来源说明保留在相应实验与附录的 evaluation/provenance 说明中。
- 正文优先用 skill；两张主图和主表标签同步调整。正文标题改为 `A Skill's Effect Lives on Its Own Tokens`，维持原题的中心结论。
- 原稿完整保存在 `.snapshots/skillvector-20260917-before-rewrite.{tex,bib,pdf}`；修改过的主图、生成代码和主表也有快照。

## 数值与方法口径核查

执行 `python3 ../whitebox/analysis/audit.py`：**309 项通过，ALL CHECKS PASSED**。日志保存在 `DATA-AUDIT-20260917.txt`。这些检查重算原稿关键数值，不等于重新运行模型或验证所有机制解释。

所有表格实验数值不变；`tab-big40.tex` 只改标签。两张主图用原始运行标签重新生成，数字标签与原 PDF 完全相同。最终使用的运行标签：

| 图或实验 | 运行标签 / 来源 | 核验 |
|---|---|---|
| 最后位置 vs skill span | `diffvec-cot-L*`、`fixmask-dev10` | 上图 n=20；下图 n=16，四个 calculator；两个 panel 的 receiver 和样本不同 |
| 主 rank 图 | `rank40-l8`、`fixmask-lad06-rank`、`mis3-rank-L4` | 三条曲线及 bottom-k 对照对应原稿 |
| 40-calculator battery | `fixmask-big40` | 从 160 题/40 组筛出 60 题/15 组 |
| 40-calculator depth | `big40-depth` | 从 120 题/40 组筛出 60 题/20 组；与 battery 的 60 题不是同一集合 |
| TheoremQA | `replication.restricted()` 与 `tqa-span` 原始行 | 按 skill 分组筛选；singleton skill 才退化为逐题筛选。Qwen3-8B battery 保留 99 题/75 组 |

### 原稿统计标注错误：本次保留数值，纠正说明

1. **主表 accuracy CI 并非 calculator bootstrap。** `tables.load()` 在汇总时对所有键使用 `k[3:]`，把 `calculator_id` 变为 `culator_id`；随后 `by.get('calculator_id')` 得到 None，`ci()` 实际执行逐题正态近似。原稿如 0.750 的 [0.640, 0.860] 对应这一算法。本次按“不改变实验结果”保留区间，图注明确实际算法。
2. **rank 图误差条并非 calculator bootstrap。** `figs.fig_rank()` 使用 `boot(src[key])`，逐题采样，再用固定的 donor–receiver gap 缩放；图注已据实修改。channels 图也是逐题 bootstrap。
3. **跨模型汇总表的恢复率区间确实按组 bootstrap。** `replication.boot()` 按 skill/calculator 分组抽样并重算恢复率；正文据此区分区间口径。

同一 skill 的多题存在依赖，因此逐题区间可能低估不确定性。本次没有重算替换这些历史区间，也没有把它们伪称为聚类估计。若投稿前继续改统计，需明确授权改变报告的区间、同时修复生成器并重新生成对应图表；原点估计无需因此改变。

## 避免超出证据的改写

- 原摘要“所有最后位置干预都落在 baseline”与原表最高 0.15、baseline 0.05 不完全一致，改为恢复有限，并保留 3/18 与深层 0–1 的实测数字。
- 不再称两个位置上是“同一个向量”；它们是同一 subtraction protocol 下的不同表示，分别为一个向量和一个矩阵。
- 明确 k 是中心化部分的方向数，保留均值后完整注入矩阵 rank 至多 k+1；k* 是有限网格上的半幅 knee，不能当成完全恢复需要的最小 rank。
- 不把“one-time patch 的表现依赖 answer format”写成关于任意 hidden state 容量的普适信息论定理。
- depth 的 0.11 表述为晚期恢复弱；保留早期 binding 可能解释晚期必要性与晚期不足性的关系。
- 保留 pre-fix 标签和 identity-control 故障；没有把修复前实验写成修复后验证。

## 引用

核对了原有 48 条记录的一手来源；明细、每篇的一句话结论和项目关系见 `CITATION-AUDIT-20260917.md`。修正正刊标题/出处混用、更新 ICML 2025 出处、补齐作者。正文没有不存在的 citation key。

## 结构和编译检查

- 原有 label 全部保留；无重复 label；35 个 figure/table 环境开闭匹配。正文恰好 3 图、4 表、3 项贡献。
- 所有 input、includegraphics、ref 和 citation key 均可解析。
- 正文引用附录中的 `tab:laddermodels` 和 `tab:prdiag` 是显式的 Appendix 引用，属于预期情况。
- 使用原有 `bash build.sh` / Windows MiKTeX 编译；正文 9 页、全文 41 页，0 error / 0 未定义引用 / 0 overfull；最终日志另存 `BUILD-CHECK-20260917.txt`。

## 后续要求：3 图 4 表

- 新表 1 将附录答案格式阶梯整理成同一表，逐项列 evaluated / rescued / recovery。原始检查显示：MC 和 numeric 各 120 题，CoT 为其中 80 题的子集，因此正文明确这一区别。
- 新表 3 将附录的修复后 skill quarters 与 doc-last 实验合并展示，数值来自 `fixmask-big40` + `fixmask-quarters40-q0..q3` 和 `fixmask-dl`。
- 新图 3 从 `big40-depth`、`ko-8b-fast`、`fixmask-window` 重画：分别是 span replacement、cumulative attention knockout 和 windows；对应 §4.6 与贡献 3。
- 可复现命令：`MPLCONFIGDIR=/tmp/skillvector-mpl python3 main_evidence.py`。原始曲线值另存 `main-evidence-values.json`。不需要模型重跑。
- 原有主图的数值标签、主表实验数字均与原快照一致；新图表只是已有实验结果的新展示方式。

## 投稿信息与尚待作者补充的事实

- [ICLR 2027 官方 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)：摘要截止 2026-09-18 23:59 AoE，全文截止 2026-09-25 23:59 AoE；对应北京时间为 9 月 19 日和 9 月 26 日 19:59。初投稿正文按官方 Submission instructions 的 9 页限制检查。
- [官方 AI 使用政策](https://iclr.cc/Conferences/2027/AIPolicyForAuthors)要求单独披露 AI 使用且不计页数。本次声明只覆盖能够确认的本轮写作、查文献、核对记录和图标签修改；已询问用户此前是否用于代码、研究设计、结果分析，尚未得到回复。不能将当前声明视为对全部历史 AI 使用的完整核实。
- 未提交或推送 Git，未上传至投稿系统。
