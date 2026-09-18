# 正文逐段润色记录

日期：2026-09-18。范围：`skillvector.tex` 摘要至 Conclusion，含正文图表说明；不改附录和实验。

## 段落处理

| 部分 | 本轮处理 |
| --- | --- |
| Abstract | 依次交代问题、干预、单位置局限、span 结果、rank 和深度；替换旧主结果，明确 screened subset。 |
| Introduction：问题段 | 从 skill 定义自然引出“表示在哪里”和“继续使用到何时”；减少提前堆积术语。 |
| Introduction：观察段 | 区分临床行为观察与 synthetic 几何观察，避免暗示是同一批题上的相关性证据。 |
| Introduction：单位置段 | 明确减法/注入的动作和 answer-format 依赖；避免把失败解释为 hidden-state 容量上界。 |
| Introduction：span 段 | 定义干预位置，报告当前 135 题结果，依次解释内容、位置、方向数。 |
| Introduction：推广段与贡献 | 用可理解的半幅恢复定义引出 rank summary，再交代跨层结果；保留三项贡献。 |
| Related Work：三段 | 按 context 表示、activation intervention、rank 测量串联；用直白说明替代 gist/autoencoder/Jacobian 等无解释名词罗列，保留全部引文。 |
| Problem Formulation：各段 | 解释 presence/content 的操作性定义、donor/receiver、arm、筛选条件、k 与 k+1、两种深度干预的问题差异；公式不变。 |
| Setup：三段 | 分开任务/模型、样本与不确定性、identity control；不再把 screened subset 称作所有 rescued items。 |
| Content / answer format：各段 | 把结果与推论分开；R/F/K/B 明确为四种子集上的 accuracy；区分不同 position-count 比较。 |
| Span injection：各段 | 顺序为位置选择、dose、其他内容/排列/噪声控制、筛选影响；同步已经本地核验的控制数值。 |
| Skill identity：两段 | 先讨论公式 quarter，再解释 causal masking 与 question dependence；删除不被 quarter 单独实验支持的组合因果推断；提示 prompt-order 子集不同。 |
| Rank：两段 | 解释 positional mean 的保留、领先/末尾方向差异、固定网格的 rank knee 定义和因果解释边界。 |
| Depth：三段 | 使用 transfer boundary 并映射图表中的 handover；解释 attention knockout；把 whole drop 改为 largest drop；定义 participation ratio 并删除“撤回旧解释”的过程叙述。 |
| Replication：各段 | 区分已有与缺失的实验；用对应模型与任务组织比较；不把 knee 当最小充分 rank，不外推为所有模型的规律。 |
| Readout checks | 先说为何 generated accuracy 必要，再举读出反例与额外任务的证据限制。 |
| Conclusion | 对齐正文，保留 screened subsets 和 tested tasks 的适用范围，避免将单位置结果解释为普适表示定理。 |
| 七处正文图表说明 | 逐项理顺测量、样本、对照和统计解释；现有 PDF 图资产错配另列为未解决项。 |

## 验证与保留项

- 改前备份：`.snapshots/skillvector-20260918-before-polish.tex`。
- 源码比较：五节与七个实验子节的顺序、所有 label、公式、图表路径和引用键不变；正文仍为三图四表；`\label{endmain}` 后内容逐字不变。
- `python3 paper/checks.py paper/skillvector.tex`：无重复 label，全篇图表环境 36/36 匹配。正文有两处明确指向附录表，并非丢失引用。
- `python3 whitebox/analysis/full_rerun_report.py battery rank`：核对主 span、控制与 rank 数值。使用现有 `replication.kstar` 定义、seed=0、2000 次 calculator bootstrap 核验 knee=47.2909，95% 区间 [43.3021,54.7581]。
- 最终 `bash paper/build.sh`：正文 9 页，全文 42 页，无 LaTeX error、未定义引用或 overfull。首轮 10 页，通过压缩重复句子恢复 9 页；未动排版参数。

## 尚未解决的数据/图表问题

这些问题在本轮前已存在，不能以语言润色或编译通过代替修复：

1. `fig-channels-medcalc.pdf` 底部标 n=20、span accuracy=0.95，而正文图注描述 n=16 的开发结果。这张图当前不是其图注所指的那批数据。
2. `fig-rank-medcalc.pdf` 实际只含 Qwen3-8B / Qwen3-0.6B，没有正文/图注描述的 Mistral，且图使用旧版曲线。已有 `fig_channels_full.py` / `fig_rank_full.py` 不代表产物已同步；本轮没有运行它们，避免把逐段润色扩成新一轮实验呈现重构。
3. `tab-big40.tex` 同 family control 的 n=41 与总体 n=135 不同；表内 0.13 使用总体 donor 分母，同一 arm 样本上的 recovery 为 0.12。该行样本量、分母以及表 4 的 max control 范围需要一起修正。
4. 附录保留了“forty calculators/n=60”与新数值混写、以及“任何 control 都不超过 0.12”但同表出现 0.25 等问题。按用户指定的正文范围未改附录。
5. synthetic/final-position 的重要结果仍是 pre-fix，正文已明确披露；要支撑投稿级因果结论仍需要修复后复核，不能靠降低语气消除实现风险。

未新增科研假设；上述均为文本一致性和既有证据解释问题。未提交、推送或更新投稿 ZIP。
