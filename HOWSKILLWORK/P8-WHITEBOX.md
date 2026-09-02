# P8 — 白盒：skill 在模型内部做了什么

**方向调整（2026-09-02）**：暂停 ALFWorld 等需要长程 agentic loop 的任务，
**聚焦 1–2 步的短任务**。`ALFWORLD.md` 的规格保留备查，不执行。
研究问题从「多步循环里哪一步被改善」收窄为：

> 对于**本来做错**的题，注入 skill 之后，**skill 所在位置**与**任务 prompt 所在位置**
> 的内部计算发生了什么？被救回来的题有没有**共同的 pattern**？
> 而**没被救回来**的题，其内部计算是否不同？

---

## 0. 行为层的地基已经打好

白盒必须挂在一个已经确证的行为效应上，否则是在没有效应的轨迹里找脑区。这个效应已经有了：

| | 模型 | 无 skill | 有 skill | Δ |
|---|---|---|---|---|
| **P1**（GATE-1，单轮无工具） | Qwen3-4B | **22.0%** | **69.6%** | +47.6pp |
| **P2**（GATE-2，带工具多轮） | Qwen3-8B | **33.6%** | **77.3%** | **+43.6pp**（配对 CI [+36.0,+51.5]） |

且 `gold − ctrl_neutral = +47.5pp`，即效应来自**内容**而非「有个文档在场」（H6 已排除）。
错配的 skill 反而比没有 skill 差 3.9pp。**这是白盒要解释的现象。**

---

## 1. 三篇论文：方法与结论

### 1.1 TTS-RiskArena（NeurIPS 2026 投稿，`NeurIPS_2026__Test_Time_Safety.pdf`）

**做了什么**：建 TTS-RiskArena，7 个高风险领域 × 42,000 prompt，
把同一个请求写成 4 个抽象层级（意图 → 方法类 → 技术-目标 → 可执行流程），
在 BoN / MCTS / Self-Consistency 三种 test-time scaling 下、budget 从 1 扫到 256，
测「安全风险随推理预算怎么变」。

**结论**：
- TTS 不是一致地改善安全 —— 同样的额外算力既抬 benign 任务的效用，也抬 unsafe 任务的成功率
- 把风险拆成 **generation risk**（搜索过程有没有产出 unsafe 候选）与 **selection risk**（选择器有没有挑中它），两者的曲线形状不同
- prompt 越具体（抽象层级 1→4），unsafe 成功率越高，**3、4 级最陡**
- **早期 token 的安全信号强预示最终安全性** —— 「安全区域是否可达，在生成早期就被决定了」

**方法上可借的**：
- 用 **DoLa 式的层间对比**选中间层：`M_t = argmax_j JSD(q_N(·|x_<t) ‖ q_j(·|x_<t))`，
  即「最终层分布与第 j 层分布分歧最大」的那层 = 模型内部预测仍在大幅refine 的位置
- **衰减调度**的干预：`λ_t = λ_0 exp(−γt)`，早期强、后期弱 —— 因为早期决定可达区域
- 把一个结果拆成「产生」与「选中」两段来归因

### 1.2 LLMs Should Express Uncertainty Explicitly（arXiv 2604.05306v2）

**做了什么**：训练模型显式暴露自我评估，两种设计 ——
(a) **推理结束后**verbalize 一个 confidence 分数；(b) **推理过程中**在不可靠的步骤发射 `<uncertain>` 标记。
用 GRPO 训练，在 5 个 factual QA 上评测，并做内部机制分析。

**结论（行为层）**：两者都大幅减少「自信地答错」。verbalized confidence 把
ECE 从 0.357 降到 0.036、over-confident 错误从 88.5% 降到 3.2%，同时 EM 从 24.4 升到 27.4；
`<uncertain>` 把 wrong-answer 的召回从 15.1% 提到 88.2%，可直接当 RAG 触发器。

**结论（内部机制）—— 这是对我们最有用的部分**：
- **verbalized confidence 是「磨锐已有结构」**：层间 CKA 从输入到输出**始终接近 1.0**，
  几何结构几乎不变，只是把预训练里本就存在的 confidence 结构表达得更干净
- **`<uncertain>` 是「新建内部状态」**：CKA 在**后期层逐步下降**，说明模型必须真的造一个新状态
- **两者参数漂移的位置和幅度相似**，但表征层面的后果完全不同 ——
  **「参数动了多少」不能解释行为差异，「表征几何有没有被改写」才能**

**方法上可借的（四件，全部可直接搬）**：
1. **按位置类型分组的 token-level KL**：对每个位置算两个条件下的分布 KL，
   再按位置的语义类型分组（信号 token / 结构标签 / 推理 token / 邻近上下文 / 其他）。
   回答「分布变化落在哪些位置」
2. **层间 CKA**（Centered Kernel Alignment），在指定位置上比较两个条件的表征几何。
   **CKA≈1 = 磨锐已有结构；CKA 下降 = 改写/新建状态**
3. **Logit lens 在指定 token 位置上分层展开**，按 correct / wrong 分组画热图
4. **hidden-state probe**：在某位置附近训练轻量探针预测最终答案对错，做层扫描找信号最强的层

### 1.3 Layer by Layer（ICML 2025，arXiv 2502.02013v2）

**做了什么**：跨 Pythia / Mamba / BERT / LLM2Vec，在 32 个 MTEB 任务上逐层评测表征质量，
并提出一套以**矩阵基熵**（matrix-based entropy）统一的表征质量度量。

**结论**：
- **中间层的表征普遍优于最后一层**，下游提升最高 +16%，最优层通常在**中深度**
- 自回归 decoder 有明显的**中层「压缩谷」**（prompt entropy 在中层下陷），
  BERT 这类双向模型没有 —— 是**训练目标**决定的，不是模态
- 残差连接是中层压缩的驱动来源
- 各度量与下游表现强相关（dCor 0.8+），可**无监督地选层**
- **CoT 微调让模型在各层保留更高 entropy**（保留更多上下文），Qwen2.5 vs Qwen2.5-Math 对比可见
- 极端输入：重复 token 压缩中层熵；随机 token 抬高早层熵

**方法上可借的（三个标量，逐层、逐 span 都能算，不需要训练）**：
- **Prompt Entropy**：对一段 token 的嵌入矩阵算矩阵基熵 `S_α(Z) = 1/(1−α) log Σ(λ_i/tr K)^α`。
  高 = 特征分散；低 = 压缩
- **Curvature**：相邻 token 差向量的平均夹角 `C̄ = 1/(L−2) Σ arccos(v_{k+1}·v_k / |v||v|)`。
  高 = 表征沿序列急转弯（局部特征）；低 = 平滑（全局特征）
- **Effective Rank** `exp(S_1(Z))`

代码在 `github.com/OFSkean/information_flow`。

---

## 2. 对我们的启发：把三篇合成一个可执行的读数体系

我们的问题是「skill 在内部做了什么」，三篇正好给了三个互补的层面：

| 层面 | 问题 | 借自 | 我们的具体量 |
|---|---|---|---|
| **几何** | skill 把任务表征改成了什么形状 | Layer by Layer | task span 的逐层 prompt entropy / curvature / effective rank，有 skill vs 无 skill |
| **同一性** | 是**磨锐已有结构**还是**新建状态** | Express Uncertainty | 两条件在 task span 上的**逐层 CKA** |
| **因果** | 哪些位置、哪些层真的承载了增益 | Express Uncertainty（KL 定位）+ TTS（层选择） | 位置分组 KL + **残差流嫁接**（patching）+ **skill span 注意力敲除** |
| **时机** | 结论在第几个 token 就定了 | TTS-RiskArena | 正确答案在 logit lens 下的**涌现层**；前 k 个生成 token 的可判定性 |

**最关键的一条移植**：Express Uncertainty 的「**磨锐 vs 新建**」二分，正是
「skill 是在唤醒模型已有的知识，还是在注入模型没有的知识」这个问题的表征层版本。
它对应我们黑盒的 H1（知识注入）与 H2（程序脚手架）之争，而且是**可测的**：

- **CKA 在各层都接近 1，几何不变** → skill 是**磨锐**：模型本来就"会"，只是没被激活到输出
- **CKA 在中后层显著下降** → skill 是**新建**：模型确实获得了原本没有的中间状态

---

## 3. 实验设计

### 3.1 载体：把任务压成单步

白盒要求因果链干净，**不做工具调用、不做多轮**。用 MedCalc 的**单轮无工具**条件
（= P1 的 H-repro 形态，但模型换成 Qwen3-8B）：

```
prompt = [system] + "Relevant Skill:\n{skill}\n\n" + {patient note + question}
       → 一次前向 → 生成答案（含 ANSWER: 行）
```

这样每条实例的内部计算就是一次可重放的前向，skill span 与 task span 的 token 边界明确。

> 与 P1/P2 的关系：P2 是带工具的 agentic 条件，白盒不用它。
> 需要**新跑一组单步臂**（§5），成本很低（单轮，比 P2 便宜）。

### 3.2 四个 item set（由行为结果定义）

按 `no_skill` / `gold` 的对错交叉，得到四格。**全部分析都按这四格分层**：

| 记号 | 无 skill | 有 skill | 含义 | 预估占比 |
|---|---|---|---|---|
| **R** rescued | ✗ | ✓ | **被 skill 救回来的** —— 主对象 | ~45% |
| **F** persistent | ✗ | ✗ | 给了 skill 也没救回来 —— **最重要的对照** | ~17% |
| **K** kept | ✓ | ✓ | 本来就会 | ~30% |
| **B** broken | ✓ | ✗ | **被 skill 弄坏的** —— 稀少但珍贵 | ~5% |

**R vs F 是核心对比**：两组的起点相同（无 skill 都错），差别只在 skill 有没有奏效。
这样「题目难度」被条件化掉了，剩下的差异才可能是机制。

⚠️ 四格是**行为定义的**，不是随机分组；报告时必须写明它们不是随机对照，
R 与 F 之间仍可能有未观测的难度差（例如 F 里 calculator 更难）。
**缓解**：在 calculator 内部配对（同一 calculator 里同时取 R 和 F），并报告配对后的结果。

### 3.3 五组测量

全部在**两段式**下做：vLLM 生成（拿到轨迹与答案）→ HF transformers **teacher-forced 单次前向重放**。
⚠️ 上线前必须断言：重放的 logprob 与 vLLM 记录一致。对不上就是 token 错位，
**所有内部量都会错且不报错**（这是 `PROTOCOL.md` §3 P8 已经写过的红线）。

**M1 · 几何剖面（描述性，最便宜，先做）**
- 对 **task span**（病历+问题的 token）和 **skill span** 分别算逐层 prompt entropy / curvature / effective rank
- 条件：`no_skill` / `gold` / `ctrl_neutral`；分层：R / F / K / B
- 读数：skill 是否在**中层压缩谷**处改变了 task span 的熵；R 与 F 的剖面是否分开

**M2 · 磨锐 vs 新建（CKA，主判据之一）**
- 在**位置对齐**的 task span 上，逐层算 `gold` 与 `no_skill` 两次前向的 CKA
- 位置对齐怎么做：两个 prompt 只差一个前缀（skill 段），task span 的 token **完全相同**，
  按 token 索引一一对应即可。这是 MedCalc 这种「prepend skill」格式的天然便利
- 读数：
  - R 组 CKA 高且平 → skill 磨锐已有结构
  - R 组 CKA 在中后层下降、F 组不下降 → skill 新建状态，且**建成了才救得回来**
  - R 与 F 的 CKA 曲线**不可区分** → 表征几何不是机制所在，转向 M3/M4

**M3 · 位置定位（KL 分组）**
- 逐位置算 `gold` 与 `no_skill` 的 next-token 分布 KL，按位置类型分组：
  病历数值 token / 单位 token / 问题句 token / 结构标签 / 答案位
- 读数：skill 的影响是均匀铺开，还是**集中在数值与单位这类抽取相关的位置**
  （若是后者，对应黑盒的 S2/S3，两侧证据可互相印证）

**M4 · 因果（这一组才是"证明"，前三组只是"描述"）**
- **(a) skill span 注意力敲除**：在第 ℓ 层屏蔽所有位置对 skill span 的注意力，
  teacher-forced 重放，测正确答案 logprob 的下降。扫 ℓ → 得到「skill 在哪几层被读取」
- **(b) 残差流嫁接**：把 `gold` 前向中第 ℓ 层、位置 p 的 residual 状态
  patch 进 `no_skill` 前向，测正确答案的 **recovery**（1.0 = 完全复现有 skill 的行为）。
  扫 (ℓ, p)，p 分组为 skill span / task span / 答案位
- 读数：增益是**从 skill span 直接读出**（(a) 掉分大、patch skill 位置就够），
  还是**skill 改写了 task span 的读法**（patch task 位置才够）

**M5 · 时机（涌现层）**
- 对答案首个数值 token，用 logit lens 逐层取正确答案的 rank / 概率，
  定义**涌现层** = 正确答案首次进入 top-k 的层
- 读数：R 组的涌现层是否比 K 组更晚、比 F 组存在（F 组可能根本不涌现）；
  skill 是否把涌现**提前**

### 3.4 控制臂（缺一不可）

内部量比行为量更容易「看到想看的东西」，控制必须比黑盒更严：

1. **`ctrl_neutral`**（换成别的 calculator 的 gold skill）：**每一项测量都要跑**。
   若 neutral 产生同样的几何/CKA/注意力模式 → 该模式是「有文档在场」的效应，不是内容
2. **位置匹配的随机 span**：M4 的敲除/patch 必须有一个等长的非 skill span 作对照
3. **长度匹配**：skill 使 prompt 变长，熵与曲率对长度敏感 → 报告时按 token 数归一，
   并用 `ctrl_neutral`（长度比中位 0.98）作为长度对照
4. **随机层对照**：M4 扫层时报告随机层的 patch 效果作为地板

### 3.5 判据与停止规则

- **GATE-W0（重放一致性）**：teacher-forced 重放的 token 级 logprob 与 vLLM 记录的相关性 ≥0.99，
  且答案 token 的 argmax 一致率 ≥99%。**不过就停** —— 后面所有数都是错位的产物
- **GATE-W1（有对象可解释）**：R 组样本 ≥100 且 F 组 ≥100（P2 的比例足够）
- **GATE-W2（不是长度效应）**：`ctrl_neutral` 在 M1/M2 上与 `gold` 明显不同。
  若相同 → 我们测到的是「prompt 变长」，改设计
- **主结论的形式**：R 与 F 在某个测量上**可分**，且该测量在 `ctrl_neutral` 上**不可分**。
  两个条件同时满足才算找到 pattern

### 3.6 算力

单张 4090，Qwen3-8B bf16：

| 项 | 规模 | 说明 |
|---|---|---|
| 单步行为跑（建 item set） | 3 臂 × 1,100 = 3,300 | vLLM，单轮，比 P2 便宜 |
| M1/M2/M3 重放 | ~400 条 × 2 条件 | 一次前向 + 逐层聚合，**不落盘完整 hidden state** |
| M4 patching | ~150 条 × 层数 × 位置组 | 最贵的一项，先在 20 条上试规模 |
| M5 logit lens | 复用 M1 的前向 | 几乎免费 |

⚠️ 显存：36 层 × 2k token × 4096 维 bf16 ≈ 1.2 GB/条的 hidden state。
**必须就地聚合成标量，不能整条存**（`whitebox/README.md` 有同类教训）。

---

## 4. 与既往 whitebox/ 的关系

仓库里 `../whitebox/` 有 E0–E7 一套既往实验（含 `e2_patch.py` 的 recovery、`e7_repr.py`）。
按 `HANDOFF.md` §5.5 的立场：**既往结论一律作为待检验假设**，
但**代码可以复用**（patching 的实现、层索引从 config 读取的纪律、journal 格式）。
新实验的结论以本文件为准；与既往冲突时记录冲突点，不默认既往正确。

---

## 5. 待做的代码改动（都不大）

1. **单步臂**：`run.py` 需要一个「彻底不带工具」的组合 ——
   `--arm no_tool`（删 `tools` 但保留正文）+ `--no-tool-protocol`，
   以及 `ctrl_neutral` 的无工具版本（现在 `ctrl_neutral` 会带上 neutral skill 自己的工具）
2. **span 边界落盘**：`run.py` 的结果里要记录 skill span 与 task span 的 **token 起止**
   （`DESIGN-mechanism.md` §3 已经要求过，事后补不回来）
3. **重放器**：HF teacher-forced 重放 + GATE-W0 断言
4. 逐层聚合器：prompt entropy / curvature / effective rank / CKA，就地聚合
5. patching 与注意力敲除：优先复用 `../whitebox/e2_patch.py`

---

## 6. 执行顺序

1. 代码改动 1–2，跑单步三臂 3,300 条 → 建 R/F/K/B 四格
2. 写重放器，过 **GATE-W0**
3. M1 + M2（便宜、描述性）→ 看 R 与 F 是否可分，`ctrl_neutral` 是否不可分（**GATE-W2**）
4. M3 定位 → 决定 M4 的 patch 位置分组
5. M4 因果（最贵），M5 顺带
6. 若 M1/M2/M3 全部不可分：结论是「表征层面没有可见 pattern，增益发生在别处」——
   这本身是结论，但要先排查 GATE-W0 与样本量，不要直接宣布
