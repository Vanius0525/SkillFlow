# PROTOCOL — 完整实验流程

配套 `DESIGN-mechanism.md`（方法论）与 `HANDOFF.md`（调研）。本文档是**可执行的流程**：
用什么 harness、跑哪些 task+skill、按什么顺序、每步的门槛与停止条件。

最后更新：2026-08-31 · 状态：**P1 GATE-1 通过、P2 GATE-2 通过，执行中**

---

## 0. Harness：结论与理由

### 0.1 结论

**主实验自建最小循环 `howskill/loop.py`；但 harness 不是一个选择，是一个必须被显式控制的变量。**

具体是三套配置，用途不同，**不要混用**：

| 配置 | 用途 | 形态 | 何时用 |
|---|---|---|---|
| **H-repro** | **校准 harness 正确性** | 复刻 SRA-Bench：单轮、无工具、skill 直接 prepend、temp 0.7、128K ctx | P1，只跑一次 |
| **H-agent** | **主实验** | 自建循环：单 `python` 工具、多轮、temp 0、全量 step 日志、支持强制前缀 | P2–P5、P7 |
| **H-disclose** | **标定投递协议的差距** | 复刻 SRA-Bench 的 Progressive Disclosure：目录 + `LOAD_SKILL: <i>`，上限 10 轮 | P6 |

### 0.2 为什么不用厂商 CLI（Claude Code / Codex CLI 那一路）

结合 `HANDOFF.md` §4.5：头部证据（SkillsBench、SWE-Skills-Bench）全部是
**闭源模型 + 厂商 CLI + skill 作为磁盘文件由 agent 自行发现**。看起来"跟随主流"应该用同类 harness，
但对本实验不成立，三个理由：

1. **它们跑不了 Qwen3-8B**。Claude Code 绑定 Anthropic 模型；SkillFlow-bench 那种用 Qwen-Coder CLI /
   Kimi-CLI 的路子可行，但换来的是下一条问题。
2. **CLI harness 让轨迹嫁接不可能**。CLI 自己管理 context（压缩、截断、工具集、系统提示），
   我们拿不到也控制不了完整 message 列表。而 §4.4 的嫁接**要求我们拥有 message 列表**。
   这是硬阻断，不是不方便。
3. **CLI 引入大量无关自变量**：自动压缩、内置工具、重试策略。机制实验里这些都是混淆项。

### 0.3 但也不能只用自建循环

`HANDOFF.md` §4.5.2 的发现是：**投递方式本身就是一等自变量**，
SRA-Bench 两端差 **28.5pp**（Qwen3-4B/MedCalc：Oracle 73.5 vs Progressive Disclosure 45.0，
skill loading rate 仅 33.4%）。若只报 Oracle 的数字，读者会拿去和 SkillsBench 的 +16.2pp 比，那是错的。

所以 **P6 用 H-disclose 自己测一遍这个差距**，而不是引用 SRA-Bench 的 28.5pp ——
我们的模型、我们的任务子集、我们的实现，得到我们自己的标定值。

### 0.4 关键校准：用已发表数字验我们的 harness

我们的自建循环没有任何外部参照 —— 除非跑一个**已经被发表过的 model × task × 设置**。

> **SRA-Bench published：Qwen3-4B on MedCalc-Bench，LLM Direct 22.0 / Oracle Skill 73.5。**

P1 就是复现这两个数。**这是整个实验唯一的 harness 正确性外部检验**，
直接回应 `DESIGN-mechanism.md` §7 里「实测远低于预期时先怀疑 harness」那条风险 ——
没有这一步，我们无法区分「Qwen3-8B 就是这样」和「我们的循环有 bug」。

---

## 1. Task + Skill：具体用什么

### 1.1 数据

| 项 | 来源 | 规模 |
|---|---|---|
| 任务实例 | HF `WeihangSu/SRA-Bench` → `instances/medcalcbench.json` | **1,100**（55 calculator × 20，已实测核对） |
| gold skill | HF `WeihangSu/SRA-Bench` → `corpus/corpus.json`（232 MB）中 `medcalcbench_*` | **55** |
| step 级 GT | HF `ncbi/MedCalc-Bench-v1.0` 的 `Relevant Entities` + `Ground Truth Explanation` | join 得到，**需报告 join 率** |
| 判分 | 实例自带 `lower_limit` / `upper_limit` | decimal 640 / integer 400 / date 60；decimal 实测 ±5% |

### 1.2 skill 的模块（消融单位）—— 已由 P0 实测确定

> **2026-08-29 更新**：原先按论文 A.4.1 模板假设的 A–E 五模块**已被实测证伪**
> （正文里没有 Python 实现；Example 兼作协议演示；单位换算只在 15/55 里）。
> 完整实测见 [`P0-FINDINGS.md`](P0-FINDINGS.md)。下表是**经验导出**的真实结构。

| 模块 | 定义 | 覆盖 | 对应步骤 |
|---|---|---|---|
| **M1 context** | 首个 `###` 之前的引言段 | 55/55 | S1 认对计算器 |
| **M2 inputs** | `Required Inputs` | 55/55 | S2 变量抽取 |
| **M3 procedure** | `Computation` ∪ `Scoring Criteria` | 55/55 | S4 套公式/评分 |
| **M4 tool-doc** | `Calculation Tool(s)`——**只描述签名，无实现** | 55/55 | S4（工具调用） |
| **M5 example** | `Example`——**同时演示 `TOOL_CALL:` 语法** | 55/55 | S5 + 协议演示 |
| M6 units | `Unit Conversion` 及变体 | 15/55 | S3 单位归一 |
| M7 notes | `Key Notes` / `Important Conventions` | 11/55 | 缺省值与边界处理 |

**M1–M5 切分率 100%**，消融照做。M6/M7 覆盖太少（15 / 11 个 calculator），
**降级为分层观察，不作为独立消融臂**。

**另有一个独立于正文的消融维度**：skill 的 `tools` JSON 字段。
55/55 都带可执行工具（共 71 个，全部含 `implementation` 源码）。
`−M4`（删正文描述）与 `−tool`（删可执行工具）是**两个不同的干预**，
其差值 = 「知道有工具」与「工具真的能用」各自的价值。

### 1.3 两级实例集

- **全集 1,100** —— 用于主效应、H6 判定、投递协议标定（P1、P2、P6）
- **深挖子集 ~400** —— 用于内容消融、时间消融、嫁接（P3–P5、P7）

深挖子集的**选取规则**（P2 跑完后确定，不能事先拍）：

1. 该 calculator 的 gold skill 能干净切出 5 个模块（P0 产出）
2. 该 calculator 有 step 级 GT（join 成功）
3. **A0 基线落在 15%–75%** —— 排除地板与天花板。基线贴地时臂间差被压进噪声，消融读不出信号
4. 在满足上述条件的 calculator 里，按 A0 基线分层均匀取约 20 个 calculator（400 实例）

---

## 2. 条件矩阵

**因子**（不做全交叉，见 §3 各阶段的具体组合）：

- **投递** ：`inject`（prepend，SRA-Bench B.1 格式）/ `disclose`（LOAD_SKILL 目录）
- **工具** ：`none` / `python`
- **skill 内容** ：`none` / `gold` / `−A`..`−E` / `neutral` / `shuffled` / `corrupted`
- **skill 可见性**：`all` / `first-only` / `late-only`
- **模型** ：`Qwen3-4B`（校准锚点）/ `Qwen3-8B`（主）

**控制臂定义**（三个都必须有，理由见 `DESIGN-mechanism.md` §4.2）：

- `neutral` — 换成**另一个 calculator 的 gold skill**。同模板、同长度量级、内容全错。
  ⚠️ 按 calculator 配对采样，上线前跑泄漏自查：不能同族（如两个都算 BMI 衍生量）、
  不能含本题答案量级的数字。
- `shuffled` — gold skill 句子顺序打乱（保 token、毁流程）
- `corrupted` — gold skill 的数值常数/阈值被扰动（保结构、毁正确性）

---

## 3. 执行阶段与门槛

> 每个阶段都有 **GATE**。GATE 不过就停下来查，不要往下推。

### P0 — 构建与验证（无 GPU 或极少）

- [x] **1. 抽出 55 个 gold skill —— 完成 2026-08-29**（整包下不动，用断点续传拿前 11.7 MB
  连续前缀 + 从截断 JSON 里 `raw_decode` 抢救；636 个 gold skill 全数恢复。见 `P0-FINDINGS.md` §0）
- [x] **2. 模块切分 —— 完成，M1–M5 切分率 100%**，但**模块定义已按实测重写**（§1.2）。
  论文 A.4.1 的 A–E 模板被证伪，四处设计随之修改，见 `P0-FINDINGS.md` §2
- [x] **3. join step 级 GT —— 完成 2026-08-29，命中 1,098/1,100（99.8%）**。
  ⚠️ `ncbi/MedCalc-Bench-v1.0` 在 HF 上**受限**，改走 GitHub `ncbi-nlp/MedCalc-Bench`
  的 `datasets/test_data.csv`。原以为需同时 join train——**不需要**，该 CSV 实际有 1,100 行。
  `Relevant Entities` 100% 解析为非空 dict，54% 的值带显式单位。见 `P0-FINDINGS.md` §5
4. 写**中间值解析器**（从轨迹里抽 agent 提交的 S1–S5 中间值），人工核对 50 条。
   **产出：解析成功率**
5. 构造 `neutral` 配对 + 跑泄漏自查
6. 写 `howskill/loop.py` + selftest

**GATE-0**：模块切分率 ≥80%、join 率 ≥90%、中间值解析率 ≥80%。
任一不达标：该读数降级（见 §7），但不阻断主效应。

### P1 — Harness 校准（复现已发表数字）

- 模型 **Qwen3-4B**，配置 **H-repro**（单轮、无工具、temp 0.7、128K ctx，
  skill 用 SRA-Bench B.1 的 `Relevant Skill:\n{skill}\n{prompt}` 格式）
- 臂：`Direct` / `Oracle`，全集 1,100
- **对照目标：22.0 / 73.5**

**GATE-1（硬门槛）**：两个数都落在 **±5pp** 内。
不过就是我们的 harness 有问题 —— 查答案抽取、prompt 格式、temp、上下文截断，**不要继续**。

### P2 — 主效应 + H6 判定

- 模型 **Qwen3-8B**，配置 **H-agent**（python 工具、多轮、temp 0）
- 臂：`A0 none` / `A1 gold` / `ctrl-neutral`，全集 1,100
- 同时跑 temp 0.7 × 3 seed 的稳健性组（同样三臂）

**GATE-2（硬门槛，即 H6）**：`A1 − ctrl-neutral` 显著为正（按 calculator 聚类 bootstrap）。
- 若 `ctrl-neutral ≈ A1` → **存在效应主导，所有内容性解释作废**。停下改方向。
  （这本身是个强结论，值得单独写，但 P3–P5 就没有意义了）
- 若 `A1 − A0` < 15pp → 先查 harness（P1 已过的话，查工具是否真的执行、答案抽取是否失效）

P2 结束后**确定深挖子集**（§1.3 规则）。

### P3 — 内容消融（模块已由 P0 实测确定）

- **H-agent**，深挖子集 ~400
- 臂（8 个）：`−M1` / `−M2` / `−M3` / `−M4` / `−M5-full` / `−M5-clinical` /
  `ctrl-shuffled` / `ctrl-corrupted`
  - `−M5-full` 整节删除；**`−M5-clinical` 保留最小 `TOOL_CALL:` 语法演示、只删临床病例** ——
    因为 55/55 的 Example 兼作协议演示，直接删会把「少了例子」和「不会调工具了」混在一起。
    两臂之差 = 协议演示的价值
- 读数：每臂的 Δ；**以及失败模式转移矩阵的变化** ——
  关键不是「删 M2 掉了几分」，而是「删 M2 是否**特异地**抬高 S2 的失败率」。
  若删任何模块都只是均匀掉分 → 作用不是内容性的
- M6/M7 不设独立臂，只在拥有它们的子集上做分层观察

### P4 — 时间消融

> **2026-08-31 修订**：原定义「首次工具调用后才注入」在实测深度下**不可能触发**，见 §3.9。
> `late` 已改为：第 0 轮无 skill 作答 → 注入 skill + 一句复核指令 → 重答，判分取**最后**一个
> `ANSWER:`。事件版保留为 `late-tool`，但只在明确要问「工具调用之后」时才用。

- **H-agent**，深挖子集 ~400
- 臂：`T-first`（仅第 1 轮可见）/ `T-late`（先答再看 skill，可修正）
- 判据：
  - `T-first ≈ T-all` → skill 是**计划种子**
  - `T-late ≈ T-all` → skill 是**校验器/修复器**
  - 都显著低 → skill 需**持续在场**，是被反复回查的参考手册
- ⚠️ `T-late` 多了一句 `REVISE_PROMPT`（`loop.py`），这是该臂定义的一部分，
  也是它唯一多出的文本。与 `T-all` 比较时要记住这一点：
  差异里含「被要求复核」的成分，不是纯粹的「skill 来晚了」

### P5 — 「知道有工具」vs「工具真的能用」⭐

> **2026-08-29 修订**：原设计以为 SRA-Bench 的 MedCalc 无工具、我们加 python 是刻意偏离。
> **实测证伪**：55/55 的 skill 自带可执行工具（共 71 个），SR-Agents 的 `DirectEngine`
> 见到 `tools` 就进 `TOOL_CALL/TOOL_RESULT` 循环（上限 5 轮）。
> **Oracle 条件下 MedCalc 本来就是 agentic 的。** 见 `P0-FINDINGS.md` §2.2。

改成一个更干净的 2×2 —— 正文描述与可执行工具是**两个可独立拆除的东西**：

| | `tools` 字段在 | `tools` 字段删掉 |
|---|---|---|
| **正文含 M4** | 完整（= A1） | 模型以为有工具，调用必然失败 |
| **正文删 M4** | 工具可用但没被介绍 | 双删（纯 prose 基线） |

- **H-agent**，深挖子集，4 格各一臂（其中「完整」复用 P2 的 A1，「−M4」复用 P3）
- 读数：
  - **工具可执行性的价值** = 含 M4 那一行的左右之差
  - **工具被介绍的价值** = `tools` 在场那一列的上下之差
  - 右上角那格还额外产出一个**失败模式**读数：模型在工具调用持续报错时会不会自救
- 若可执行性的价值远大于被介绍的价值 → **H5 工具解锁**成立，
  结论是「skill 里的可执行代码只有在 agent 能执行它时才兑现价值」，
  对「skill 该怎么写」有直接实践含义

### P6 — 投递协议标定

- 模型 **Qwen3-8B**，配置 **H-disclose**（SRA-Bench B.3 的目录 + `LOAD_SKILL:`，上限 10 轮）
- 候选目录：gold skill + 若干干扰项（用 BM25 top-50 或固定 55 个 calculator skill 全表，二选一并说明）
- 全集 1,100
- **产出两个数**：端到端通过率、**skill loading rate**
- 用途：报出**我们自己的** Oracle vs Disclose 差距，作为「我们的 Δ 与 SkillsBench 系数字不可直接比」的量化依据

### P7 — 轨迹嫁接（因果定位）

- 只在 **discordant 实例**上（`A1` 成功 & `A0` 失败），预估 300–450 条
- 对齐两条轨迹，找首个实质分歧轮次 `t*`
- **正向 `Graft(t)`**：喂 `A1` 的前 1..t 轮作强制前缀 → **撤掉 skill** → 自由续跑
- **反向 `Graft'(t)`**：喂 `A0` 的坏前缀 1..t 给**带 skill** 的 agent
- 每条取 3–5 个嫁接点
- 读数：成功率 vs t 曲线，**跃升处即因果瓶颈**
- ⚠️ vLLM 非逐位确定：每次嫁接都要**校验前缀真的复现**，对不上的丢弃并计数

### P8 — 白盒（条件执行）

**仅在 P2–P7 已经给出明确的行为层结论后再做**，且只在 P7 挑出的 ~100 条上。

- 两段式：**vLLM 生成（已有轨迹）→ HF transformers teacher-forced 单次前向重放**
- ⚠️ 上线前断言：重放的 logprob 与 vLLM 记录一致，否则 token 错位，所有内部量都是错的且不报错
- 读数优先级：① skill span 注意力质量（逐层，就地聚合成标量，用 eager attention）
  ② 激活嫁接（residual stream patching，给出层级定位）③ logit lens

---

### 3.9 深度约束 —— P2 实测后补记（2026-08-31）

设计时（`DESIGN-mechanism.md` §4.1）假设「任务是单次输入，但需要多轮循环」，
时间轴与轨迹轴的价值都建立在这个假设上。**P2 实测的循环深度否定了它的强版本**：

| 臂 | 平均轮数 | 平均工具调用 |
|---|---|---|
| `no_skill` | 1.0 | **0** |
| `ctrl_neutral` | 1.1 | 0.1 |
| `gold` | **2.0** | 1.0 |

典型 gold 轨迹 = 「想一下 → 调一次工具 → 报答案」。撞满 5 轮的是空转，不是深推理。
选型时的六条理由（`DESIGN-mechanism.md` §2.1）里**没有一条是循环深度** ——
动态范围、效应量、模块与步骤对齐、step 级 GT、判分确定、能在 4090 上跑。
深度不是被权衡掉的，是当初就没进入判据。三个后果：

1. **P4 的 `late` 曾经是空定义**。循环在模型给出答案时即终止（`loop.py`），
   而无 skill 的 agent 不知道工具名（签名在 M4 里，实测 0 次调用），
   所以它第 0 轮答完就收工，永远走不到「首次工具调用之后」。
   该臂会静默退化成 `no_skill`，读数关于任何东西都不成立。已按上文改为显式复核轮。
2. **P7 的嫁接点只有 1–2 个**。「成功率 vs t 曲线的跃升处即瓶颈」需要 t 有若干取值；
   2.0 轮意味着实际只能比较「嫁接第 1 轮 vs 不嫁接」。P7 在本任务上退化为二值对比，
   仍有意义（它仍能回答「第一步是不是瓶颈」），但**不要画成曲线**。
3. **论文措辞**：可以说「在带工具调用的循环里」，不能说「在多步 agent 任务里」。

**这不改变 P2/P3 的有效性** —— 内容轴（哪个模块有用）不依赖深度，
`gold − ctrl_neutral = +47.5pp` 也不依赖深度。受限的是时间轴与轨迹轴的解释力。

**若要支持真正的多步机制主张**，需要第二个深度 ≥5–10 轮的 task+skill 组合，
作为独立阶段（见 §9），不阻塞 P3–P6。

---

## 4. 指标与分析

**主表**
- 每臂通过率 + **按 calculator 聚类的 bootstrap CI**（不是按实例 —— 同 calculator 的 20 条不独立）
- 主效应报 **`A1 − ctrl-neutral`**（扣掉存在效应），**并列报出** `A1 − A0`（对齐外部论文）

**step 级**
- 失败模式转移矩阵（行 = A0 的首个出错步骤，列 = A1 的），全局 + 按 calculator 分层
- 特别标出 **`(none→S_k)` 负向格子** = skill 把本来做对的题做错了

**成本**
- 每臂的 prompt/completion token 数、轮数分布。
  综述 2606.11435 点名"指标几乎全是二元 pass/fail，忽略 token 成本"，顺手补上

**必须报告的元数据**
- GATE-0 的三个率、GATE-1 的复现偏差、嫁接前缀复现失败数、`unparsed` 比例

---

## 5. 算力预算（单张 4090，Qwen3-8B + vLLM）

| 阶段 | episode 数 | 备注 |
|---|---|---|
| P1 | 2,200 | Qwen3-4B，单轮，最便宜 |
| P2 | 3,300 + 9,900（temp 0.7 × 3 seed） | 多轮 |
| P3 | 2,800 | 7 臂 × 400 |
| P4 | 800 | 2 臂 × 400 |
| P5 | 800 | 2 臂 × 400 |
| P6 | 1,100 | 多轮 LOAD_SKILL |
| P7 | ~3,000 | 嫁接 |
| **合计** | **≈ 24,000** | 约 **2–3 天 GPU**，P8 另计 |

先跑 P0→P1→P2 即可判定方向（约 1 天），再决定是否投入 P3 之后。

---

## 6. 风险与停止规则

| 情况 | 动作 |
|---|---|
| GATE-1 不过（复现不出 22.0/73.5） | **停**。查答案抽取 / prompt 格式 / 截断。这是 harness bug，不是发现 |
| GATE-2 不过（`ctrl-neutral ≈ A1`） | **停 P3–P5**。改写成"存在效应主导"的论文，H6 本身是结论 |
| 模块切分率 <80% | 改用实际标题切分重新定义消融单位；若仍不行，P3 降级为「整份 vs 无」 |
| 中间值解析率 <80% | §4 的 step 级读数不可信，退回 `fail/pass` + 嫁接曲线（P7 仍有效） |
| step GT join 率低 | join 不上的实例排除出 step 级分析，**但仍留在主效应里**；报告 join 率 |
| 嫁接前缀复现率低 | 记录并报告，不要假装没发生；必要时改用固定 batch 组成 |
| Δ 远低于预期（<15pp）且 GATE-1 已过 | 查工具是否真的执行、返回值是否被当成普通文本、循环是否空转 —— 这些都会表现为"模型不行"且不报错 |

---

## 7. 与外部数字比较时的纪律

1. **我们的 Oracle Δ 不能与 SkillsBench 的 +16.2pp 并排比较** —— 投递协议不同（`HANDOFF.md` §4.5.2）。
   要比就用 P6 的 disclose 数字，并说明差距。
2. **我们加了 python 工具，SRA-Bench 没有** —— 所以 P2 的绝对分不能直接对 73.5。
   能对的只有 P1（H-repro，刻意复刻）。
3. **ALFWorld 的数字不要引用作对比** —— 两篇之间 harness 差异导致绝对分冲突（`HANDOFF.md` §1.1）。
4. 既往 skillflow / whitebox 的结论一律作为待检验假设（`HANDOFF.md` §5.5）。

---

## 8. 执行清单

- [x] ~~P0-1 下载 corpus.json，抽 55 个 gold skill~~ **完成 2026-08-29**
- [x] ~~P0-2 模块切分器 + 报告切分率~~ **完成：切分率 100%，但模块定义被证伪并重写**
      → `P0-FINDINGS.md`
- [x] 附带完成：取回并读通 SR-Agents 的 harness 源码（prompt / 抽取 / 判分 / 工具循环），
      P0-6 应以其 `tool_loop.py` 为蓝本而非从零写
- [x] ~~P0-3 join 原始 MedCalc-Bench~~ **完成：1,098/1,100 = 99.8%，0 未命中**
- [x] ~~P0-5 `neutral` 配对 + 泄漏自查~~ **完成：55/55，0 同族、0 泄漏、长度比中位 0.982**
- [x] ~~P0-6 循环实现~~ **完成：`../howskill/`，38/38 离线自检通过**
- [ ] P0-4 中间值解析器的**人工校准** —— 解析器已写好，但需真实轨迹才能校准。
      **顺延到 P1 之后**用其轨迹做校准集，人工核 50 条并报告解析率

> **本地工作到此结束。代码与数据见 [`../howskill/`](../howskill/)，
> 服务器上的命令、GATE 判据与报数纪律见 `../howskill/README.md`。**
- [ ] **P1 复现 Qwen3-4B 的 22.0 / 73.5 ← GATE-1**
- [ ] **P2 主效应 + H6 ← GATE-2**，之后确定深挖子集
- [ ] P3 内容消融 → P4 时间消融 → P5 工具×D 交互
- [ ] P6 投递协议标定
- [ ] P7 轨迹嫁接
- [ ] P8 白盒（条件执行）

---

## 9. 第二个 task：深度（待定，不阻塞 P3–P6）

§3.9 说明了为什么 MedCalc 撑不起多步机制的主张。若要补，第二个组合必须同时满足
（前三条是当初 MedCalc 选型里就有的，第四条是这次补上的）：

1. skill 原文**随论文/代码发布**，不用我们自己写 —— 否则外部可比性归零（ALFWorld 就是栽在这）
2. 判分确定，不用 LLM-judge
3. 开源小模型上不触底不触顶
4. **典型轨迹深度 ≥5–10 轮**，且深度来自任务本身而非空转

候选与已知障碍：

| 候选 | 深度 | 障碍 |
|---|---|---|
| ALFWorld（LatentSkill） | 高 | skill 未发布；两篇论文绝对分互相冲突（`HANDOFF.md` §1.1） |
| AppWorld | 高 | 仓库有 `appworld_adapter.py`；需确认有无现成 skill 语料 |
| GAIA（smolagents / inspect） | 中高 | 仓库有两套启动器；无配套 gold skill，判分依赖答案匹配 |
| SWE-Skills-Bench 系 | 高 | 闭源模型 + 厂商 CLI 的证据；开源模型上是否成立未知 |

**先做的事不是选任务，是量深度**：在候选上跑一遍 no-skill 基线，记录轮数分布，
拿到 §3.9 那张表的对应版本再决定。深度是这次的第一判据，不能再靠论文正文推断。
