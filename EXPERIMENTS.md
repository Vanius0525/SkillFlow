# 正文实验清单（实时维护）

**用途**：每一项正文显示项（表/图/段落）对应的是哪个实验、用的是谁的材料、多大样本、
哪个 tag。改动实验或正文时**同步更新本文件**。

最后更新 **2026-09-21**。配套文件：`CAMPAIGN-2026-09-20.md`（本轮补跑与预注册）、
`HANDOFF-TAKEOVER-2026-09-20.md`（接管）、`IDEAS.md`（待深挖）。

---

## 0. 三句话

- 论文的**主材料是别人的**：MedCalc-Bench 的题 + SRA-Bench 的 skill，一共 1,100 题；
  外加 SRA-Bench 的 TheoremQA 子集。
- **我们自造的只有 Tier A**（zorb 单位换算），它只承担 §4.2 一节（约一页）、摘要 2–4 句、
  Introduction 一段，以及 §4.8 两句。论文自己写明：
  *"this is the only place in the paper where the synthetic material carries an argument of its own."*
- **Tier B / Tier B2 / Tier C 一次都没进论文**。Tier C（`whitebox/tier_c_run.py`，
  copy/cipher 两个 family）是当时探「是映射的秩还是答案长度」的侧支，结论没写进去。

---

## 1. 材料：谁的，我们改了什么

| 材料 | 来源 | 题 | skill | 作答形式 | 评分 | 我们加的 |
|---|---|---|---|---|---|---|
| **MedCalc** | MedCalc-Bench \citep{khandekar2024medcalc} 的题 + SRA-Bench \citep{su2026srabench} 的 55 个 gold calculator skill | 55 × 20 = **1,100**，别人的 | 别人的 | 别人的：step-by-step reasoning → 数字 | 别人的 benchmark scorer，数值容差，**无模型参与** | 接收方筛选（screen）、四格划分 R/F/K/B、注入臂 |
| **TheoremQA** | SRA-Bench 的 TheoremQA 子集，prompt 与 scorer **逐字沿用** | 池子 747 题 / 320 skill，别人的 | 别人的 | 别人的 | 别人的 | **抽样上限：每 skill ≤4 题、≤200 skill** → 实际 142–168 题 / 113–122 skill；同一套筛选 |
| **Tier A（合成）** | **全部我们自造** | `whitebox/tasks/tier_a/build_large.py` 生成 **358** 题 | `SKILL.zorb-units.md`，我们写的编造单位表 | **我们规定的三种**：`mc` 四选一 / `num` 只答数字 / `cot` 分步推理 | 我们写的精确匹配，**零 floor** | 匹配长度的错 skill `filler-neutral.md`；两个更紧的对照 `ctrl_shuffled` / `ctrl_corrupted`（`make_controls.py`） |
| Tier B / B2 | 我们自造（物化常量/流程） | — | — | — | — | **未进论文** |
| Tier C | 我们自造（`tasks/tier_c/`，copy1/2/4/8/16 + cipher + renslow） | — | — | — | — | **未进论文** |
| LogicBench / CHAMP / ToolQA / BigCodeBench | 别人的 | — | — | — | — | 只在 §4.8 一句 + 附录提及，**不承担结论** |

**为什么需要 Tier A**：MedCalc 上做不出「presence component 恰好等于 wrong-skill baseline」
这种**等式**（0.098 = 0.098）——真实材料没有精确的零 floor，也没有逐 token 长度匹配的负对照。
Tier A 的单位是编造的，模型没有先验，答案要么对要么错。

**历史约定（仍生效）**：`HANDOFF-whitebox.md` 记过「**『skill 有多有用』的量级不要再从 Tier A/B 引用**」。
正文守住了：39.7pp 的效应量级出自 MedCalc；Tier A 只用来报恢复比例 ρ 和作答形式对比。

---

## 2. 正文各项 → 实验内容 → 数据

PDF 里 §4 是 Experiment，所以小节编号是 §4.1 setup、§4.2 起为实验。

| 显示项 | 小节 | 材料 | 模型 | n | 接收方 | 测的是什么 | tag | 生成脚本 |
|---|---|---|---|---|---|---|---|---|
| 摘要 2–4 句、Intro 第 3 段 | — | **Tier A** | 1.7B + 8B | 358 | 无文档 | 分解 + 作答形式阶梯 | `d17-neutral(+b)`、`tA-mc`、`tA-num-a/b`、`tA-cot-1..4` | — |
| Intro 第 2 段（cosine .91–.95） | — | **Tier A** | 1.7B | 358 | — | 对/错 skill 在末位置的状态差夹角 | `d17-neutral` | — |
| 行为基线 74.2/34.5/31.5% | §4.1 | MedCalc | 8B | 1,100 | — | 纯行为，无干预 | `p8-step/p8-*.jsonl` | `check_main_data` |
| **表 1** 作答形式 | §4.2 | **Tier A** | 8B | 358 × 36 层 | 无文档 | 末位置整体替换在 mc/num/cot 三种形式下的恢复 | `tA-mc`、`tA-num-a/b`、`tA-cot-1..4`(+`tA-cot-self`) | `main_evidence.answer_format_full` |
| §4.2 分解（.098/.805） | §4.2 | **Tier A** | 1.7B fp32 | 358（R=82） | 无文档 | presence vs content 在末位置 | `d17-neutral(+b)` | `campaign_numbers` §6 |
| §4.2 负对照（.17–.28） | §4.2 | **Tier A** | 1.7B fp32 | 358 × **28 层全量** | 无文档 | 换对照文档后 content 还剩多少 | `d17-shuffled(+b)`、`d17-corrupted(+b)` | `controls_table.py` |
| §4.2 位置阶梯（.235….370） | §4.2 | **Tier A** | 8B | 358 × 36 层 | **无文档** | 末 k 位补丁，k=1/4/16/32/48/**61** | `tA-num-a/b`、`tA-num-k4/k16/k32/k48/k61` | `check_main_data` |
| **表 2** span 电池 | §4.3 | MedCalc | 8B | **135**（14 calc） | **错 skill**，长度匹配 | 整段注入 + 全部对照臂，层 8 | `full-battery-a/b` | `tables.tab_big40` |
| **图 1** 位置通道 | §4.3 | MedCalc | 8B | 135 | 错 skill | span vs 末 1/16/256 位，同层同题 | `full-battery-a/b` + `pb-tq` | `fig_channels_full.py` |
| **图 2** 位置预算 | §4.4 | MedCalc | 8B | 135 | 错 skill | 固定预算只改选位：连续性/落点/逐位精确 | `pb-*`、`fp-*`、`fp1-*` | `fig_posbudget.py` |
| **表 3(skill content)** | §4.5 | MedCalc | 8B | 135 / 151 | 错 skill | 四个 span 四分之一；问题依赖（skill 在问题后） | `full-battery-a`+`full-quarters`；`full-dl-a/b` | `main_evidence.skill_content` |
| **图 4** 秩曲线 | §4.6 | MedCalc | 8B / 0.6B / Mistral | 135 / 362 / 92 | 错 skill | 截断到秩 k 再注入，k=1…512 | `full-rank-*`、`x8-rank-*`、`q06-rank-*`、`mis-rank-*`(+`-hi`) | `fig_rank_full.py` |
| **图 3** 深度 | §4.7 | MedCalc | 8B | 135（敲除 134） | 错 skill | 逐层整段注入 / 累积 attention 敲除 / 末位置 | `full-depth-*`+`dep1-mc8-*`；`full-ko`+`ko1-mc8-*` | `main_evidence.depth_v2` |
| §4.7 谱分析 | §4.7 | MedCalc | 8B | 96 / **48 calc** | — | 内容矩阵的中心化 PR + massive activations | `geom-8b`（表 `tab:prdiag`） | `tables.tab_prdiag` |
| **表 4(replication)** | §4.8 | MedCalc + TheoremQA | 三个模型 | 见下 | 各自错 skill | ρ / 最大对照 / 交接边界 / 读取边界 / k\* | 见 `replication.py` ROWS/NEW/FILL/RANK_DENSE | `replication.py` |
| §4.8 读数诊断 | §4.8 | **Tier A** | 1.7B | 358 | — | 共享均值向量的 logprob 反转（+5.05 nats 而准确率更低） | `rd-e2` | `check_main_data` |
| §4.8 corrupted 捷径（.54/.82） | §4.8 | **Tier A** | 1.7B | 358 | — | 破坏数字/打乱行后整集还剩多少效应 | `d17-corrupted(+b)`、`d17-shuffled(+b)` | `controls_table.py` |

**表 4 六行规模**（`resolved_rows()` 实测）：

| 行 | n（题） | groups | 注入层 | 模型层数 |
|---|---|---|---|---|
| MedCalc × Qwen3-8B | 135 | 14 | 8 | 36 |
| TheoremQA × Qwen3-8B | 99 | 75 | 8 | 36 |
| MedCalc × Qwen3-0.6B | 362 | 38 | 6 | 28 |
| TheoremQA × Qwen3-0.6B | 132 | 97 | 6 | 28 |
| MedCalc × Mistral-7B | 92 | 20 | 4 | 32 |
| TheoremQA × Mistral-7B | 115 | 94 | 4 | 32 |

---

## 3. 两个容易被问住的 n

### 3.1 表 2 的 "mean from the same skill family" 为什么 n=41

`dnear` 臂 = **同一 family 里其他 calculator 的 content 差向量的均值**。
`wb_spanvec.py` 里 family 由 skill 标题推出（`family_of`：`qtc` / `delta` /
`liver`(child-pugh, fibrosis) …），而且：

```python
for tag, pool in (("near", same), ("far", other)):
    if not pool:          # 没有同族兄弟 → 这一臂对该 calculator 根本不存在
        continue
```

筛选后剩的 **14 个 calculator 里，只有 3 个（13、64、67）在集合内有同族兄弟**，
它们的题数分别是 2 + 20 + 19 = **41**。其余 11 个 calculator 在这个集合里是孤例，
`ok_dnear_L8` 这个 key 压根不写，所以不进分母。

**这是有意为之，不是缺数据**：如果用 135 题的基线去归一化只有 41 题的臂，
就会把「另一个 skill」和「一个近似的 skill」混在一起算。`check_main_data.py` 里有一条
专门守它：`same-family row not normalised by 135-item baseline`。
表 2 的脚注也写明了这一行的 n 与别行不同。

同理 Mistral×MedCalc 的同族均值是 **31** 题。

### 3.2 TheoremQA 为什么 n 只有 99–132 而不是 747

每次运行抽样上限 **每 skill ≤4 题、≤200 skill** → 142–168 题；再过接收方筛选 → 99/132/115。
747 是**题池**不是评测集。这一条 2026-09-21 已写进附录 `app:replication`。

---

## 4. 未解的口径问题（会影响结论强度）

### 4.1 ⚠ Tier A 位置阶梯的接收方没有对照

阶梯（k=1…61）注入的接收方是**无文档 prompt**（`--no-filler-receiver`），
而 MedCalc 的整段注入用的是**长度匹配的错文档 prompt**。所以
「0.403 vs 0.89」这个落差**同时**跨了三件事：任务（Tier A vs MedCalc）、
接收方（无文档 vs 错文档）、位置（问题尾部 vs 文档自己的 span）。

已知的旁证：在 **1.7B 多选**的末位置上，把 `h_skill` 写进**错文档** prompt 给
0.976–1.000，写进**无文档** prompt 给 0.988–1.000 —— 错文档接收方**从不更差**，
中层还更好（L17–20：0.51–0.77 vs 0.29–0.45，见 `tab:causal`）。
**但自由作答格式下没测过。**

最小补测：把 `tA-num-k*` 的 `--no-filler-receiver` 去掉重跑一条臂（约 4 GPU·h）。

### 4.2 Tier A 上「写文档自己的 span」也不超过 ~0.41

同一批自由作答材料上，整段注入（688 个 token）只有**层 0** 到 0.408
（≈ 把文档原样放回去），层 3 起 ≤0.17，层 15 起归零（`tab:windows2`，n=120 旧样本）。
所以 **0.403 的天花板不能归因于「位置不是文档自己的」**——在这个任务上，
写文档自己的位置反而更差。真正隔离「位置」这个变量的是 MedCalc 上那个
**同接收方、同题、同层**的对照：整段 0.89 vs span 之后最多 256 位 0.05。

2026-09-21 已据此改写附录 §B.6（原文把 0.403 vs 0.89 归因于位置，是**跨任务比较，说过头了**）。

### 4.3 §5 仍未做的三项

见 `HANDOFF-TAKEOVER-2026-09-20.md` §5：第 1 项（TheoremQA 严格全量，~60 GPU·h）、
第 4 项（表 3 下半问题依赖补全 36 层，~64 GPU·h）、第 7 项（全部 466 题逐层敲除，~45 GPU·h）。

---

## 5. 口径速查

- **rescued cell (R)**：没文档答错、有文档答对。主要因果比较只在 R 上做。
  另三格：F（都错）、K（都对）、B（没文档对、有文档错）。
- **ρ（recovery）** = (acc(arm) − acc(receiver)) / (acc(donor) − acc(receiver))。
  ρ=1 表示复现 donor 的全部增益，>1 表示比 donor 还好。
- **screen（接收方筛选）**：只保留「错 skill 接收方一题都答不对」的 skill group。
  逐 run、逐模型、逐任务各筛一次，**不看干预结果**。
- **donor / receiver**：donor = 带正确 skill 的那次前向；receiver = 被写入的那条 prompt。
- **k\*（rank knee）**：固定网格 {16,32,64,128} 上，从 k=16 爬到最大值一半所需的秩，
  在 log2 k 上插值。**定义在数据回来前就固定了**，所以 2026-09-20 加密网格后它一字未动。
