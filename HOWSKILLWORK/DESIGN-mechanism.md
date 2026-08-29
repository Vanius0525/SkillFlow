# DESIGN — skill 为什么 work：在 Qwen3-8B 上做 step 级机制归因

承接 `HANDOFF.md`（调研）。本文档回答三个问题：

1. 选哪个 **skill + task pair** 在开源模型上复现「skill 确实有效」？
2. 用**怎样的 harness**？
3. 对「单次输入、多轮 agentic 循环」的任务，**怎样探究 skill 的作用机制**，
   具体到**哪一步**、**为什么是那一步**？黑盒能做到哪、白盒能加什么？

最后更新：2026-08-29 · 状态：**设计完成，数据依赖已全部核实，未开跑**

---

## 0. 结论

1. **选 MedCalc-Bench + SRA-Bench 的 55 个 gold calculator skill。** 这是唯一一个同时满足
   「开源小模型上增益巨大 + skill 原文可下载 + 判分确定 + 有 step 级 ground truth」的组合。
   Qwen3-4B 上 **22.0 → 73.5（+51.5pp）**，是整张 SRA-Bench 表里最大的效应。
2. **ALFWorld 降级为备选。** LatentSkill 的 5 个 ALFWorld skill **没有随代码发布**
   （repo 要求外部传 `--skill_context_dir`），复现要自己重写 skill，外部可比性就没了。
3. **不要用仓库现有的四个 eval loop。** 另写一个最小的、可确定性重放的循环。
   机制实验需要 per-step 日志 + 强制前缀注入，现有循环的熔断器和路径改写都是混淆项。
4. **机制归因的核心是：agentic 循环给了你一条时间轴，于是可以在三个互相独立的轴上做干预** ——
   skill 内容（哪个模块）、skill 可见性（哪几轮）、轨迹前缀（嫁接到第几步）。
   三轴交叉才能把「哪一步有用」从「哪部分内容有用」里分离出来。
5. **白盒能做，但必须「vLLM 生成 → HF teacher-forced 重放」两段式**，不要试图带 hook 生成
   （hook = PyTorch forward hook，注册在某层上、前向经过时触发的回调，用来读出或改写中间张量；
   与 `.claude/settings.json` 里 Claude Code 的 "hooks" 是同名不同物）。
   先黑盒后白盒：黑盒负责找出 discordant 实例，白盒只在那一小撮上解释机制。

### 0.1 ⚠️ 本设计独立自证，不依赖既往 skillflow / whitebox 结果

本文档的每一条设计决策都建立在**外部已发表工作的数字**或**本轮实测的数据事实**之上，
不建立在 `../skillflow.py` 那套 harness 或 `../whitebox/` 既往产出的结论之上。

原因：那批结果未经独立复核，且已知至少一次 **harness 静默失败被误读为模型能力问题**
（未注册的工具返回普通字符串，小模型据此反复重试直至耗尽预算）；
四个 eval 入口又各自复制了一份 `execute_tool` 和 agent loop，修复不一定同步落地。
在系统重跑之前，无法判断还有多少结论受同类问题污染。

因此：**不复用现有循环**（§3.1）；既往观察（如「patch 打败 document」「无内容版本也能赢」）
在本实验中**一律作为待检验假设**，由本实验自己的控制臂重新验证（分别对应 §4.2 的模块消融和
`ctrl-neutral`）；若结论冲突，**以本实验为准**并记录冲突点。
`HANDOFF.md` §5.3 那张「外部佐证」表仍然有效 —— 它引的是外部论文，不是我们自己的既往结果。

---

## 1. 本轮核实到的事实（相对 HANDOFF.md 的更新）

全部为本轮实际拉取/下载核实，不是转述摘要。

| 事项 | 结果 |
|---|---|
| SRA-Bench 数据可得性 | ✅ HF `WeihangSu/SRA-Bench`。`instances/medcalcbench.json` 3.69 MB，`corpus/corpus.json` 232 MB（含全部 26,262 skill） |
| MedCalc 实例结构 | ✅ 实测：**1,100 实例 / 55 个 gold skill / 每个恰好 20 条**，`skill_annotations` 每条恰好一个 gold skill |
| 判分方式 | ✅ `eval_data = {answer, calculator_id, output_type, lower_limit, upper_limit}`，**确定性数值容差判分，无 LLM-as-judge** |
| 答案类型分布 | decimal 640 / integer 400 / date 60 |
| **容差带** | decimal 实测为 **±5%**（如 answer 25.2381 → [23.976, 26.500]）→ **舍入/格式混淆基本被排除** |
| gold skill 文档结构 | ✅ 论文 A.4.1 给出固定模板（见 §2.2），**5 个模块边界是构造时就有的**，不需要我们事后切 |
| step 级 ground truth | ✅ 原始 `ncbi/MedCalc-Bench-v1.0` 有 **`Relevant Entities`**（抽取出的临床变量）+ **`Ground Truth Explanation`**（逐步演算） |
| LatentSkill ALFWorld skill | ❌ **未发布**，repo 只接受外部 `--skill_context_dir`，指向 Xia et al. (2026) 的 skill library |
| LatentSkill Qwen3-8B 基线 | ✅ In-Context Skill = **52.9 seen / 56.0 unseen**（与 74.3−21.4、69.4−13.4 自洽） |

### 1.1 两条需要写进论文的矛盾/坑

- **ALFWorld 绝对分在两篇之间对不上**：SkillsInjector 报 Qwen3-8B **no-skill 67.1**，
  LatentSkill 报同模型 **in-context skill 只有 52.9/56.0**，即「给了 skill」比「没给 skill」还低 10+ 点。
  这不是矛盾结论，是 **ALFWorld 的绝对分严重依赖 harness/prompt/step 上限**（LatentSkill 用 50 步、4096 ctx）。
  跨论文引用 ALFWorld 数字必须连 harness 一起引。**这也是不选 ALFWorld 的第二个理由。**
- ~~**SRA-Bench 1,100 ≠ 原始 test split 1,047**，需同时扫 train~~
  **2026-08-29 实测更正：这条是错的。** HF 的 dataset_info 声明 test=1047，但 GitHub 上的
  `datasets/test_data.csv` **实际有 1,100 行**。用 `Calculator ID` + `Patient Note`
  包含匹配命中 **1,098/1,100（99.8%）**，0 未命中，**不需要 join train**，
  且 GT 答案与 SRA-Bench 100% 一致。另：`ncbi/MedCalc-Bench-v1.0` 在 HF 上是**受限数据集**，
  须走 GitHub 取。详见 [`P0-FINDINGS.md`](P0-FINDINGS.md) §5。

---

## 2. 选定的 skill + task pair

### 2.1 为什么是 MedCalc

外部数字（SRA-Bench Table 2，MedCalc 列）：

| 模型 | LLM Direct | Oracle Skill | Δ | Full-Inject | LLM Select | Prog. Disclosure |
|---|---|---|---|---|---|---|
| **Qwen3-4B** | **22.0** | **73.5** | **+51.5** | 36.1 | 65.7 | 45.0 |
| Llama-3.1-8B | 26.9 | 62.0 | +35.1 | 36.7 | 57.0 | 59.6 |
| Qwen3-32B | 53.9 | 83.5 | +29.6 | 59.5 | 82.5 | 71.1 |
| Qwen3-235B | 58.2 | 84.5 | +26.3 | 66.2 | 82.5 | 77.1 |

**Qwen3-8B 未被测过**，夹在 4B（+51.5）和 32B（+29.6）之间，预期 **+35~45pp**。

选它的理由，按重要性：

1. **动态范围理想**：预期 baseline 25~50%、上限 75~85%。**既不触底也不触顶** ——
   这正是 SkillsBench 在开源模型上（no-skill 5.2%）会毁掉对照的地板效应问题。
2. **效应量巨大**：+35pp 量级意味着 n=20/calculator 就能在单个 calculator 上看出差异，
   可以做**按 calculator 分层的机制分析**，而不只是一个全局平均数。
3. **skill 内容与任务步骤天然对齐**（§2.2）—— 这是能做 step 归因的前提，多数任务没有这个性质。
4. **有 step 级 GT**：`Relevant Entities` + `Ground Truth Explanation` 让中间步骤可机检。
5. **判分确定 + ±5% 容差**：格式/舍入混淆（H3）基本不存在，省掉一整组控制。
6. **纯文本、无模拟器、无外网**，4090 上跑得动。

### 2.2 skill 文档的模块结构（关键）

SRA-Bench 论文 A.4.1 的构造 prompt 规定了固定模板，所以**每个 gold skill 都有同样的 5 个模块**：

| 模块 | 内容 | 对应任务步骤 | 对应机制假设 |
|---|---|---|---|
| **A** | 临床背景 1–2 句 | S1 认对计算器 | 检索/消歧 |
| **B** | 必需输入 + 单位 + 单位换算 | S2 变量抽取、S3 单位归一 | 知识注入（本体） |
| **C** | 符号化的分步计算流程 | S4 套公式/分支 | 程序性脚手架 |
| **D** | `compute_{name}(...)` Python 实现 | S4（可执行路径） | 工具解锁 |
| **E** | 一个新造病例的 worked example | S5 输出形态 | 示例/格式 |

**这是本设计能成立的支点**：模块边界不是我们事后切出来的，是 skill 构造时就规定的，
所以「删掉模块 B」是一个干净的、非任意的干预。而模块 → 步骤的映射给出了**可证伪的预测**：
删掉 B 应当**特异地**抬高 S2/S3 的失败率，而不是均匀抬高所有步骤的失败率。
如果删掉任何模块都只是均匀掉分，那就说明 skill 的作用不是内容性的（见 §4.5 的 H6）。

### 2.3 任务的步骤分解

MedCalc 单条实例的隐含步骤（每步都有 GT 可查）：

- **S1 识别计算器 / 选公式** — GT: `Calculator Name`
- **S2 从病历抽取变量** — GT: `Relevant Entities`（结构化，可精确比对）
- **S3 单位换算 / 归一化** — GT: 从 `Ground Truth Explanation` 解析
- **S4 套公式 / 走对条件分支** — GT: 同上
- **S5 舍入与输出格式** — GT: `answer` + 容差带

---

## 3. Harness

### 3.1 不复用现有循环

仓库里 `skillflow.py` / `eval_scibench_with_skills.py` / `eval_assistant_with_skill.py` /
`eval_gaia_with_skills.py` 各自带一份 `execute_tool` 和 agent loop。不用它们，因为：

- 它们带**熔断器**（重复 tool 调用 5 次后拒绝、40 次上限、force-answer 前缀）。
  这些是为了救坏循环加的，但在机制实验里它们**本身就是一个干预**，会和 skill 的效应混在一起。
- `fix_skill_paths.py` 那套相对路径改写只对 scibench_skills 有意义。
- 机制实验需要两个现有循环都没有的能力：**确定性重放** 和 **强制前缀注入**。

### 3.2 新循环的要求

`howskill/loop.py`，尽量小：

- **工具集固定为一个**：`python(code) -> stdout`。不给 bash、不给文件系统、不给检索。
  工具越少，轨迹的分支越少，step 对齐越容易。
- **决定性优先**：主实验 `temperature=0`。理由不是「效果更好」，而是
  **轨迹嫁接（§4.4）要求前缀能被精确重放**。另开一组 `temperature=0.7 × 3 seed`
  验证结论对采样的稳健性（SRA-Bench 用的是 0.7，要能对得上）。
  ⚠️ vLLM 在不同 batch 组成下**并非逐位确定**；嫁接重放时必须校验前缀真的复现了，对不上的实例丢弃并计数。
- **每轮全量落盘**：完整 messages、每个 assistant token 的 top-k logprob、工具输入输出、
  以及 skill 文本在 prompt 中的 **token span 起止**（白盒阶段要用，事后补不回来）。
- **`enable_thinking:false`**（沿用现有部署的约定），且白盒重放必须用**同一个 chat template**
  —— 模板不一致导致的 token 错位是这类实验最常见的静默失败。
- **skill 注入方式固定为 Oracle**：直接把 gold skill 放进 context，**不做检索**。
  理由：Qwen3-4B 在 MedCalc 上的 skill loading rate 只有 **33.4%**，
  检索/加载环节会把「模型愿不愿意用」和「skill 有没有用」搅在一起。
  我们研究的是后者，就要把前者钉死。

---

## 4. 黑盒机制方法（主体）

### 4.1 为什么 agentic 循环反而更好做

任务是**单次输入**，但需要**多轮循环**。这看起来更难分析，实际上更好分析 ——
因为循环把一个原本原子的「回答」**展开成了一条带时间轴的轨迹**，于是可以在三个正交轴上干预：

| 轴 | 干预 | 回答的问题 |
|---|---|---|
| **内容轴** | 删掉 skill 的模块 X | 哪部分**内容**有用 |
| **时间轴** | 只在第 t 轮让 skill 可见 | skill 在**什么时候**被用 |
| **轨迹轴** | 把 skill 轨迹的前 t 步嫁接给无 skill 的 agent | 哪一**步**是因果瓶颈 |

单轮任务只有内容轴。**三轴交叉才能区分「模块 C 有用」和「第 2 步有用」** ——
否则这两个说法是纠缠的。

### 4.2 实验臂

每条实例跑以下条件（`ctrl-*` 是控制臂，不是消融臂）：

**主臂**
- `A0 no-skill` — 基线
- `A1 gold-full` — 完整 gold skill（Oracle）

**内容消融（leave-one-out，逐模块）**
- `A2 −A` 去临床背景 / `A3 −B` 去输入与单位 / `A4 −C` 去计算流程
- `A5 −D` 去 Python 实现 / `A6 −E` 去 worked example

**控制臂（用来分辨「内容」与「存在」）**
- `ctrl-neutral` — 换成**另一个 calculator 的 gold skill**。
  同分布、同模板、同长度量级、内容全错。
  ⚠️ 必须**按 calculator 配对采样**并检查：中性 skill 里不能出现本题答案量级的数字，
  也不能恰好是同族计算器（例如两个都算 BMI 衍生量）。
- `ctrl-shuffled` — gold skill 的句子顺序打乱（保 token、毁流程）
- `ctrl-corrupted` — gold skill 的**数值常数/阈值被扰动**（保结构、毁正确性）

`ctrl-neutral` 是最重要的一臂：SkillsInjector 报告 random-skill 一致微正（+1.5~2.6），
说明**存在效应非零**。任何 `A1 − A0` 的报数如果没有减掉 `ctrl-neutral − A0`，都是虚高的。

**时间消融（只在时间轴上动，内容永远是完整 gold skill）**
- `T-all` = A1（全程可见）
- `T-first` — 只在第 1 轮 prompt 里出现，之后从 context 里移除
- `T-late` — 第 1 轮不给，**第一次工具调用之后**才注入

三者的对比是直接的机制判据：
- `T-first ≈ T-all` → skill 是**计划种子**：内容在第一轮就被转写进 agent 自己的话里，之后不需要它在场。
- `T-late ≈ T-all` → skill 是**校验器/修复器**：它的价值在于纠正已经走偏的执行。
- 两者都显著低于 `T-all` → skill 需要**持续在场**，说明是被反复回查的**参考手册**。

### 4.3 step 级读数：失败模式转移矩阵

对每条轨迹，用 GT 解析出 agent 在 S1–S5 各步**实际提交的中间值**，与 GT 比对，
记录**第一个出错的步骤**（`fail_step ∈ {S1..S5, none}`）。

然后对同一实例的配对轨迹画**转移矩阵**：行 = `A0` 的 fail_step，列 = `A1` 的 fail_step。

这一张表就是「skill 在哪一步有用」的**主要读数**，而且是纯黑盒的：

- 质量集中在 `(S2→none)` 或 `(S3→none)` → skill 主要修的是**变量抽取/单位**
- 集中在 `(S4→none)` → 修的是**公式与分支**
- 对角线上还有 `(S1→S1)` 残留 → skill 没能解决**选错计算器**
- 出现 `(none→S_k)` 的**负向格子** → skill 把本来做对的题做错了，这是负效应的直接定位

**这比任何单一 Δ 数字都信息量大**，且能按 calculator 分层看（55 × 20 的设计支持这个）。

⚠️ 中间值解析必须是**保守的**：解析不出来就标 `unparsed`，不要猜。
先在 50 条上人工核对解析器，报告解析成功率；解析率低于 ~80% 的话这个读数不可信。

### 4.4 轨迹嫁接（因果定位，对应「和删掉这一步的轨迹对比」）

前三节都还是「关联」。要说**某一步是因果瓶颈**，需要嫁接：

只在 **discordant 实例**上做（`A1` 成功且 `A0` 失败）—— 效应全在这撮里，其余实例做嫁接是浪费算力。

- 对齐 `A0` 与 `A1` 的轨迹，找**首个实质分歧轮次** `t*`。
- **正向嫁接 `Graft(t)`**：把 `A1` 轨迹的第 1..t 轮消息作为强制前缀喂给 agent，
  然后**把 skill 拿掉**，让它自由续跑。
- 画 **成功率 vs t** 曲线。**曲线跃升的那个 t，就是 skill 贡献所集中的那一步。**
  - `Graft(1)` 就恢复了 → 全部价值在第一次决策（选对公式/列对变量）
  - 只有当 t 越过含单位换算的那一轮才恢复 → 瓶颈是 S3
- **反向嫁接 `Graft'(t)`**：把 `A0` 的坏前缀 1..t 喂给**带 skill** 的 agent。
  若仍能成功 → skill 有**修复能力**（不只是规划）；若不能 → skill 的作用**只在前缀未污染时有效**，
  这是一个很强的、可写进论文的结论。

正反两向合起来，把「哪一步」从相关性抬到了因果性。这就是
「和删掉这一步的轨迹进行对比」的严格版本：不是删掉，而是**替换**并观察下游是否被拯救。

### 4.5 要区分的机制假设与各自的预测

| 假设 | 说的是 | 预测的特征 |
|---|---|---|
| **H1 知识注入** | 补了模型没有的公式/阈值 | `−B`/`−C` 掉最多；`ctrl-corrupted` 掉到接近 `A0`；转移矩阵集中在 S4 |
| **H2 程序脚手架** | 补的是控制流不是事实 | `ctrl-shuffled` 显著掉（顺序重要）；`T-first ≈ T-all` |
| **H3 格式契约** | 只是把答案写成可判分的样子 | 本任务基本可排除（±5% 容差）；仍需在 integer/date 的 460 条上单独查 |
| **H4 自检与纠错** | 让模型回头验算 | `T-late ≈ T-all`；带 skill 的轨迹**轮数更多**但错误率更低 |
| **H5 工具解锁** | 给了可直接调用的实现 | `−D` 掉最多；增益与「轨迹里真的调用了 python」强相关 |
| **H6 存在效应** | 与内容无关 | `ctrl-neutral ≈ A1`。**若成立，上面所有内容性解释都作废** —— 所以它必须先被排除 |

**H6 必须先测。** 这是整个设计里唯一一个「会推翻其他所有结论」的分支。

### 4.6 报数规范

- 主效应报 **`A1 − ctrl-neutral`**（扣掉存在效应），同时**并列报出** `A1 − A0` 以便与外部论文对齐。
- 所有 Δ 带 **按 calculator 聚类的 bootstrap 置信区间**（不是按实例 —— 同一 calculator 的 20 条不独立）。
- 报告 **token 成本**：skill 臂的 prompt 长得多。综述 2606.11435 点名「指标几乎全是二元 pass/fail，
  忽略 token 成本」，我们顺手补上这个缺口。

---

## 5. 白盒：能拿到什么，怎么拿

### 5.1 先说限制

**当前部署的 vLLM 拿不到内部状态。** vLLM 的 OpenAI 接口只给 `logprobs`，
没有 hidden states、没有 attention。要拿内部计算必须走 HF `transformers`（或 nnsight / TransformerLens）。

### 5.2 可行路线：两段式

**不要试图带着 hook 生成。** 正确做法：

1. **生成阶段**：全部用 vLLM 跑（快、批量大），把轨迹 + skill 的 token span 落盘。
2. **重放阶段**：把已确定的轨迹用 HF transformers **teacher-forced 单次前向**重放，
   在指定 token 位置抓内部量。

这样把「要吞吐」和「要内省」解耦，是在单张 4090 上唯一现实的做法。
Qwen3-8B bf16 权重约 16 GB，24 GB 卡上**只做前向**是够的（生成 + hook 就很紧张）。

⚠️ 重放必须与生成用**完全一致的 chat template 和 `enable_thinking` 设置**，否则 token 位置错位，
拿到的所有内部量都是错的，**而且不会报错**。上线前先做一个断言：重放的 logprob 与 vLLM 记录的
在容差内一致，不一致就停。

### 5.3 四个值得做的白盒读数

按「性价比 / 与黑盒结论的耦合度」排序：

1. **skill span 的注意力质量**（最便宜、和 §4.2 时间轴直接对应）
   每个生成 token 上，注意力落在 **skill span / 病历 span / 指令 span** 的比例，逐层。
   给出一条 **「模型什么时候真的在看 skill」** 的曲线，是 `T-first / T-late` 消融的内部对应物。
   ⚠️ 工程约束：**不能把注意力矩阵全部物化**（层 × 头 × seq² 会爆显存）。
   必须用 eager attention 实现（flash/SDPA 不返回权重），并**在每层前向时就地聚合成三个标量**再丢弃。
   ⚠️ 解释约束：注意力权重**本身不是因果证据**，必须和第 2 项配对使用。
2. **激活嫁接（activation patching）** —— §4.4 轨迹嫁接的内部版本
   同一前缀下跑 with-skill / without-skill 两遍，把 with-skill 的 residual stream
   在 (layer, position) 上 patch 进 without-skill，看正确答案 token 的 logit 何时翻转。
   给出**层级定位**：skill 的效应是在早层（词法/检索）还是中后层（组合/计算）注入的。
3. **logit lens**：在模型提交某个中间变量的那个 token 位置，看正确值是否在**更浅的层**就成为 top-1。
   若是 → skill 让计算「变简单了」，而不只是「给了答案」。
4. **skill span 注意力屏蔽**：从第 t 轮起把对 skill span 的注意力置零，
   不改 prompt 就实现时间轴消融 —— 比重新 prompt 更干净（prompt 长度不变，位置编码不变）。

### 5.4 黑盒还是白盒？—— 建议

**黑盒先行，白盒随后，且让黑盒的产物直接喂给白盒。**

理由：§4.3 的转移矩阵 + §4.4 的嫁接曲线，**已经能在行为层面回答「哪一步、为什么」**，
而且有统计效力（1,100 实例）。白盒的价值不在于重复这个结论，而在于解释
**「为什么这一步会被修好」** —— 而这只需要在黑盒挑出的一小撮 discordant 实例上做。

反过来做（先白盒）会浪费 4090：在一个还没做过行为刻画的任务上抓 hidden states，
你不知道该看哪个 token 位置、哪一层、哪几条实例。

---

## 6. 成本与分期

单张 4090 + Qwen3-8B + vLLM。

**Pilot（先做这个）**：55 calculator × 10 实例 = 550 条 × 4 臂（`A0`/`A1`/`ctrl-neutral`/`T-first`）
- 目的：① 验证 Qwen3-8B 上 Δ 真的落在 +35~45pp；② **排除 H6**；③ 校准中间值解析器
- 规模：约 2,200 episode，估计 **数小时**
- **门槛**：若 `A1 − ctrl-neutral` 不显著为正，**停下重新设计**，不要往下推

**Full**：1,100 条 × 10 臂（主 + 消融 + 控制 + 时间）× temperature 0
- 约 11,000 episode；每条 ~3–5 轮、prompt ~2.5k、输出 ~600 token
- 输出 token 合计 ~7M，按 4090 上批量吞吐估计 **约 1 天 GPU**
- 加 `temperature=0.7 × 3 seed` 的稳健性组再约 1 天

**Graft**：只在 discordant 实例上（预估 300~450 条）× 每条 3~5 个嫁接点 × 正反两向
- 约 2,000~4,500 episode，**半天**

**白盒**：discordant 实例的一个子集（~100 条）teacher-forced 重放
- 前向次数不大，瓶颈在实现和对齐校验，不在算力

---

## 7. 风险

| 风险 | 处置 |
|---|---|
| **H6 成立**（中性 skill ≈ gold skill） | Pilot 就会暴露。真成立的话它本身是个强结论，但整套内容/步骤归因作废，要改方向 |
| **中间值解析率太低** | §4.3 读数不可信。先人工核 50 条，解析率 <80% 就退回到只用 `fail/pass` + 嫁接曲线 |
| ~~**step GT join 不上**~~ | **已解除（2026-08-29）**：实测 1,098/1,100 命中，0 未命中，`Relevant Entities` 100% 解析为非空 dict。剩下 2 条歧义实例排除出 step 级分析即可 |
| **vLLM 非逐位确定** | 嫁接重放时校验前缀复现；对不上的丢弃并计数，不要假装没发生 |
| **白盒 token 错位** | 上线前做 logprob 一致性断言，不一致即停 |
| **`ctrl-neutral` 泄漏** | 中性 skill 可能同族、或含本题答案量级的数字。按 calculator 配对采样 + 上线前跑自动泄漏检查（干扰项里混进题目自己的数字是这类控制臂的典型失效模式） |
| **Qwen3-8B 实际增益远小于预期** | 4B 是 +51.5、32B 是 +29.6，8B 不该低于 +25。**若实测 <15pp，先怀疑 harness 而不是模型** —— 工具未注册、返回值被当成普通文本、循环空转都会表现为「模型不行」，且不报错。查 trajectory 里的工具调用是否真的执行了 |

---

## 8. 待办

- [ ] 下载 `corpus/corpus.json`（232 MB，走 hf-mirror），抽出 55 个 `medcalcbench_*` gold skill
- [ ] 核实 55 个 skill 是否**真的都符合 A.4.1 的 5 模块模板** —— §2.2/§4.2 全建立在这上面。
      写个解析器切模块，报告切不干净的比例；比例高就要改消融方案
- [ ] join `ncbi/MedCalc-Bench-v1.0` 的 `Relevant Entities` + `Ground Truth Explanation`，报告 join 率
- [ ] 写 `howskill/loop.py`（单 python 工具、确定性、全量 step 日志、强制前缀模式）
- [ ] 写中间值解析器 + 人工核对 50 条
- [ ] 构造 `ctrl-neutral` 配对并跑泄漏自查
- [ ] 跑 Pilot，先判 H6
- [ ] （Pilot 通过后）Full → Graft → 白盒
