# SkillVector 论文重写交接

更新日期：2026-09-18。

## 2026-09-18 正文逐段润色

- 用户任务：逐段润色 `skillvector.tex` 正文，提高可读性、术语引入和逻辑衔接，保留整体结构。本轮已处理摘要、Introduction、Related Work、Problem Formulation、Experiment、Conclusion、三项贡献与七处图表说明。
- 保留五个顶级章节、七个实验子节、17 个 paragraph 标题位置、3 图 4 表、全部公式、label、引用键及图表输入文件；`\\label{endmain}` 后内容与本轮修改前逐字一致。未改实验脚本或原始结果，未提交/推送。
- 同步正文中已被本地记录证实的旧数字：主 span 恢复 0.89、rank32 0.12、bottom64 0.03、rank knee 47；全文统一筛选后 135 题/14 calculators 的适用范围。使用 `python3 whitebox/analysis/full_rerun_report.py battery rank` 核验；按 `paper/replication.py` 的分组筛选和 kstar 定义、2000 次 calculator bootstrap 独立计算得 47.2909 [43.3021, 54.7581]，故正文统一为 47 [43,55]，替换另一处旧区间 [43,72]。
- 将“整个 drop 都发生在一层”收窄为“最大下降发生在 12–13 层”；后续层最大值按本地附录曲线改为 0.07。连续概率读出支持存在较陡下降，但其阈值并不等同于 accuracy 的 0.5 crossing。删除从 quarter 结果推出其他部分必须组合贡献的推断；prompt-order 比较明确不是同一样本的配对估计。
- 检查：`python3 paper/checks.py paper/skillvector.tex` 无重复标签，36 对全篇图表环境匹配；源码对比确认结构/公式/引用不丢失。`bash paper/build.sh` 最终正文 9 页、全文 42 页，0 LaTeX error、0 未定义引用、0 overfull，已更新 PDF。第一次编译正文 10 页，压缩重复表述后恢复 9 页；未改字号/页边距或缩图来压页。
- 改前源码备份：`.snapshots/skillvector-20260918-before-polish.tex`。修改说明与待核对项：`POLISH-AUDIT-20260918.md`。
- **仍存在的投稿前问题（非润色能解决）**：现有图 1 PDF 底部写 n=20、accuracy=0.95，与图注开发子集 n=16/1.00 不一致；图 2 PDF 只有两条 Qwen 曲线，没有正文/图注所述 Mistral，且其版本与当前 135 题结果不同。此次不重生成图或改变实验范围，图表资产与正文的一致性仍未通过。
- 主表 `tab-big40.tex` 的同 family 条目只覆盖 n=41；当前表用总体 donor 分母报 0.13，而匹配该 arm 样本的计算为 0.12。正文保留已核验的完整子集控制，不再笼统声称所有同/异类控制相同；表内口径待专门修正。附录也残留旧样本说明与不成立的“所有 control 不超过 0.12”等表述，按本轮正文范围未修改。
- 下一步：同步图表生成器与其实际样本、逐 arm 分母及图注，清理附录旧数值/旧说明，再作投稿前完整数据审计；pre-fix synthetic/final-position 结果仍需修复后验证。本轮未更新 Overleaf ZIP，避免将未完成数据一致性检查的包视为投稿定稿。

## 当前任务

按用户要求重写 `skillvector.tex` 正文，结构为 Introduction、Related Work、Problem Formulation、Experiment、Conclusion。引言依次讲问题、paradox、关键实验、核心发现、进一步验证，并归纳 3–4 项贡献。保留实验结果和分析结论，优先使用 skill，检查数据与引用，不保留 Limitations 部分。

## 已验证事实

- 修改前正文有 11 个顶级章节，Introduction 有 6 项贡献；独立 Limitations 在正文与附录各一处。
- 已保存原始 tex、bib、pdf 到 `.snapshots/*-20260917-before-rewrite.*`。
- 当前仓库已有大量其他未提交工作；本次仅在 paper 目录修改，不提交或推送。
- 旧 build.sh 使用 Windows MiKTeX 并写入 `/mnt/c/...`，需另查可用的本地编译路径。
- 2026-09-17 图表样本审计：当前正文 MedCalc 因果图表仍引用从 55 个计算器中按 rescued 数最多选出的 40 个、每组 4 个，共 160/470 rescued item；再按 receiver 全错筛到 15 组/60 item。此“top 40”选取规则未见于正文采样段落。参见 `../whitebox/full-rerun.sh` 的 WHY 注释及 `skillvector.tex` 实验设置。
- 本地 `../howskill/results/p8-wb/fetched/by-host/*/full-*.jsonl` 已有全量重跑文件；`python ../whitebox/analysis/full_rerun_report.py battery rank depth quarters knockout dose doclast window` 显示主要 span 注入在组筛选下为 0.89（旧 0.87）、rank128 为 0.77（旧 0.77）、formula quarter 为 0.56（旧 0.56）、depth L12/L13 为 0.74/0.16；但 skill-last L16 own 恢复率从旧 0.85 变为 0.49，同组他例从 0.48 变 0.29，需改写相关论断。多数 full span 输出只有 467 item/48 calculators，knockout 有 469/49；缺的两项是 calculator 28 的 `medcalcbench_00937`、`medcalcbench_00925`，必须查明。正文尚未吸收这些结果。

## 完成状态

- 已完成五节结构重写；用户后续要求将贡献压缩为三项、正文采用 3 图 4 表，均已落实。
- 三个贡献：可转移 skill 表示的因果定位；恢复所需表示 rank；skill 转移与继续读取的深度分离。
- 主图：最后位置 vs skill span、rank 曲线、替换/累计注意力敲除/层窗口三面板。主表：答案格式、span controls、skill 内容与题目依赖、跨模型与任务复现。
- 注意力敲除位于正文 §4.6 及图 3(b)；第三个贡献显式提及 cumulative attention knockout。
- 新增 `main_evidence.py`，从原始记录生成新增主图及两张表。无需新增模型实验；旧附录深度图仍保持其原来的历史定位，不混入修复后主图。
- `python3 ../whitebox/analysis/audit.py`：309 项通过；日志 `DATA-AUDIT-20260917.txt`。
- 原有所有 label 保留，35 对图表环境匹配；五节、3 图、4 表、3 项贡献的结构断言通过。
- Windows MiKTeX 编译通过：正文 9 页，全文 41 页，0 error / 0 未定义引用 / 0 overfull；已查看主要页面排版。日志 `BUILD-CHECK-20260917.txt`。
- 已更新 `skillvector.pdf` 和 `overleaf-skillvector.zip`；ZIP 已做依赖和 CRC 检查，内容与当前主 tex 一致。
- 原有 48 条引用均核对一手页面；更正见 `CITATION-AUDIT-20260917.md`。完整改写说明见 `REWRITE-AUDIT-20260917.md`。

## 已发现并处理的口径问题

- 原稿 battery accuracy CI 实际为逐题正态近似，rank 图误差条实际为逐题 bootstrap；本次保留所有区间数值，纠正图注与方法说明。生成器 `tables.load()` 的 calculator_id 键切片问题尚未修改，避免擅自改变用户要求保留的统计结果。
- battery 和 depth 都写 n=60，但分别为 15 和 20 个 calculator，已明确。
- TheoremQA 实际按 skill 分组筛选，singleton 才等于逐题筛选，已明确。
- 答案格式的 MC/numeric 各 120 题，CoT 为其中 80 题子集；新表同时列 evaluated 与 rescued，避免“完全相同样本”表述。
- k 指中心化方向数，保留均值后完整注入 rank 至多 k+1；k* 是有限网格的半幅 knee，不是完全恢复所需的最小 rank。

## 尚待用户补充

- 已通过异步问题询问历史 AI 使用范围，尚未回复。当前 AI Use Statement 仅陈述本轮已确认用途，不声称已完整核实此前的代码/实验设计/结果分析历史。官方要求与截止日期已记录在核查报告。
- 无提交/推送/投稿系统上传操作。
- 2026-09-17 正文审阅：现有五节主线完整，编译 PDF 的结论落在第 9 页，符合 ICLR 2027 正文不超过 9 页的页数要求。科学审稿风险集中在：主结果仅对 40 个计算器中筛出的 15 个组/60 个 item 成立；仪器修复前的 synthetic、final-position 与部分机制结果仍承担核心叙事；rank knee 是网格上的半高点而非最小充分秩；跨任务和模型的对照并不齐全。下一步优先在修复后重跑支撑主张的诊断、报告未筛选总体及每组效果，并收窄 abstract/conclusion 的外推。

## 失败尝试及原因

- 首次沙箱内调用 Windows MiKTeX 因 WSL socket 权限失败，经工具请求授权后正常编译。
- 图标签改名时暂将内部筛选键 needs_document 一并改名，数值一致性检查立即识别出 n=40 与原 n=16 的不一致；已修复内部键并重生成，最终图的全部数字标签与原稿一致，错误中间图未作为最终结果交付。

## Open Ideas / 值得深挖的问题

- **2026-09-17：skill span 的位置预算与任务映射复杂度是否共同决定单向量失效？** 触发：现稿单位置与完整 span（约 415–1,630 token）干预的效果差很大，但同时改变了干预容量；Dong et al., arXiv:2506.09048 的双射任务使 task vector 在原任务/逆任务较好、组合双射接近随机。值得做：把“答案长所以单向量失败”与“技能映射本身需要分布式表示”分开。最小实验：同一模型、同一 skill 与答案格式下，在独立 held-out 题上比较 1/4/16/64/全 span 的保序位置预算、相同预算的语义区域和随机/错位控制；另构造低/高映射复杂度的技能，在各预算下画恢复曲线。若高复杂度任务在等长答案下需要更多位置，且不是单纯 token 数或扰动能量造成，可能形成独立机制结果；若所有曲线只由答案长度或扰动总量解释，则该想法失败。
  - 现有部分位置证据：40-calculator 修复后 quarter ablation 已覆盖四个独立四分之一及完整 span（$0.12/0.56/0.12/0.12$ 对 $0.87$）；共享前缀有 $0.73$ 对完整 span $0.87$。因此新实验是填补同一 skill span 内连续、等预算、跨长度的位置剂量曲线，不是首次做局部 span 干预。

## 相关论文记录

- Dong et al., *Understanding Task Vectors in In-Context Learning: Emergence, Functionality, and Limitations*, arXiv:2506.09048：线性 Transformer 分析预测单 task vector 在双射映射上的表达限制，并用原任务/逆任务/组合双射的对照表及多向量注入验证；与本稿相关的是对“一个位置何时够用”的正面反例设计，但其映射秩不同于本稿 span 矩阵截断秩。
