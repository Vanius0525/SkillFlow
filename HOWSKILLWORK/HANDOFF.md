# HANDOFF — Skills 相关论文调研：哪些 skill + task 组合被验证有效

调研问题：**在已发表的工作里，哪些「skill 文档 + 任务」的配对是被对照实验证明有效的？
其中哪些用的是开源模型（尤其 Qwen3-8B 这一档）？**

用途：给 `../HANDOFF.md`（黑盒 agent harness）和 `../HANDOFF-whitebox.md`（Qwen3-8B 白盒）
挑选**外部已知有效**的 skill+task 对，作为我们自己实验的正对照 —— 我们需要一个
「skill 确实该起作用」的设置，才能判断白盒里看到的内部变化是不是真的对应能力提升。

最后更新：2026-08-29 · 状态：**第 2 轮检索完成，8 篇已读到数字级；第 3 轮进行中**

> **2026-08-29：选型已收敛。方法论见 [`DESIGN-mechanism.md`](DESIGN-mechanism.md)，
> 可执行流程见 [`PROTOCOL.md`](PROTOCOL.md)（harness 决策 · 阶段 P0–P8 · 门槛与停止规则）。**
> 结论：正对照定为 **MedCalc-Bench + SRA-Bench 的 55 个 gold calculator skill**，
> 在 Qwen3-8B 上做 step 级机制归因。ALFWorld 降为备选（skill 原文未发布，见 §6 已核实项）。

> 版本注意：本文档里所有 arXiv 编号都按检索当天的版本记录。SkillsBench 的 v1 与
> 最新版数字不一致（见 §2.1），引用时要说明版本。

---

## 0. 一句话结论（先看这个）

1. **「skill 有效」不是普遍事实，是分布极不均匀的现象。** SkillsBench 平均 +16.2pp，
   但 software engineering 只有 +4.5pp，healthcare 有 +51.9pp；SWE-Skills-Bench 里
   49 个技能有 39 个增益为零，平均 +1.2%。
2. **想要一个稳定为正的对照设置，别选 SWE。** 选**外部知识密集、模型参数里没有、
   但步骤确定**的任务 —— 医疗计算（MedCalc-Bench）、受控环境的程序性任务（ALFWorld）
   是目前证据最硬的两类。
3. **开源模型上有硬数字的只有三篇**（§3）：LatentSkill（Qwen3-8B）、
   SkillsInjector（Qwen3-8B）、SRA-Bench（Qwen3-4B/32B/235B + Llama + Mistral）。
   主流 skill benchmark（SkillsBench / SWE-Skills-Bench / SkillLearnBench）**全部只测闭源模型**。
4. **注入方式本身就是自变量。** SkillsInjector 里「整库注入」把 ALFWorld 从 67.1 打到
   **31.5**，比不给 skill 还差一半 —— 负效应是可复现的，而且幅度比正效应大。
5. **harness 与投递方式的分裂几乎与开闭源完全重合（§4.5.2）。** 闭源那组是
   厂商 CLI + agent 自己发现磁盘上的 skill 文件；开源那组是自建循环 + 直接塞进 context。
   **这不是同一个干预**：SRA-Bench 两端都做了，差 **28.5pp**。
   跨论文比较 Δ 之前先确认投递协议是否一致。

---

## 1. 检索状态

| 轮次 | 做了什么 | 状态 |
|---|---|---|
| 1 | SkillsBench / SWE-Skills-Bench 定位 + 全文 | 完成 |
| 2 | Qwen3-8B 相关（LatentSkill / SkillsInjector / Skill-to-LoRA / SRA-Bench）+ 综述 2606.11435 的 benchmark 全表 | 完成 |
| 2.5 | 选型收敛 + 数据依赖核实 + 各篇模型/harness 横向对照（§4.5） | 完成 2026-08-29 |
| 3 | ContinualSkillBench、SkillCAT、SkillRevise、SkillJuror、AgentSkillOS、Knowledge Activation | 进行中 |
| 4 | 复现可行性排序：哪些 benchmark 的数据/skill 库能直接拉下来在 4090 上跑 | 未开始 |

本地已抽取全文（scratchpad `papers/*.txt`，`pdftotext -layout`）：
SkillsInjector、Skill-to-LoRA、综述 2606.11435、SRA-Bench、SkillFlow-bench。

---

## 2. 两个「主线」benchmark

### 2.1 SkillsBench — arXiv 2602.12670（Li et al., 2026b）

通用 skill 效用基准，是后续一大批工作的数据来源。

**版本漂移（引用时必须注明）**：

- **v1**：86 tasks / **11** professional domains / 7 agent-model configs / 7,308 trajectories，
  curated skills **+16.2pp**
- **最新摘要**：87 tasks / **8** domains / **18** model-harness configs，
  pass rate 33.9% → 50.5%（**+16.6pp**，normalized gain 25.5%），
  config 级增益范围 +4.1 ~ +25.7pp

**实验设置**：每个任务在 no-Skills / curated-Skills（/ self-generated Skills，v1）三种条件下
配对评测，deterministic verifier（pytest 类）判分。Skill 来源是 47,150 个去重公开 skill，
经自动校验 + 人工五项标准筛选。

**按 domain 的增益（v1，Δabs）** —— 这张表是选任务的主要依据：

| Domain | Δ | Domain | Δ |
|---|---|---|---|
| Healthcare | **+51.9pp** | Office & White Collar | +17.8pp |
| Manufacturing | **+41.9pp** | Finance | +15.1pp |
| Cybersecurity | +23.2pp | Media & Content | +13.9pp |
| Natural Science | +21.9pp | Robotics | +7.0pp |
| Energy | +17.9pp | Mathematics | +6.0pp |
| | | **Software Engineering** | **+4.5pp** |

难度分层：Core 17 / Extended 43 / Extreme 26。

**负效应任务**（84 个里 16 个为负）：`taxonomy-tree-merge` **−39.3pp**、
`energy-ac-optimal-power-flow` −14.3pp、`trend-anomaly-causal-inference` −12.9pp、
`exoplanet-detection-period` −11.4pp。

**其他几条对我们有用的结论**：

- **2–3 个 module 的聚焦 skill（+18.6pp）优于大而全的文档** —— 方向上与既往 whitebox 的
  「patch 打败 document」一致，但**后者未经独立复核（见 §5.5），不能当作已证实的结论互相印证**；
  本条只作为**外部**证据引用，我们自己的版本由 §5.5 的模块消融重新检验
- **小模型 + skill 可以追平大模型无 skill**
- （v1）**self-generated skills 平均无收益** —— 模型写不出自己能受益的程序性知识

**模型**：Claude Code（Opus 4.5/4.6, Sonnet 4.5, Haiku 4.5）、Gemini CLI（3 Pro / 3 Flash）、
Codex CLI（GPT-5.2）。**明确写了 "No open-weight models included"。**

### 2.2 SWE-Skills-Bench — arXiv 2603.15401（Han et al., 2026）

第一个 requirement-driven、专门隔离 skill 边际效用的 SWE 基准。
代码/数据：`github.com/GeniusHTX/SWE-Skills-Bench`、HF `GeniusHTX/SWE-Skills-Bench`。

**规模**：49 个公开 SWE skill × 真实 GitHub 仓库（固定 commit）→ **约 565 个 task instance**，
6 个子域：Deployment & DevOps 13 / Analytics & Monitoring 12 / API Development 10 /
Data Science & ML 9 / Security & Testing 4 / Developer Tools 1。

**设置**：需求文档带显式验收标准 → 映射成 pytest 执行式校验（**不用 LLM-as-judge**）；
skill 注入 `~/.claude` 目录，同一任务跑有/无 skill 两条；Docker（Ubuntu 24.04, CPU-only）。

**总体结论：49 个技能里 39 个零增益，平均只有 +1.2%。**

**7 个真正有效的 skill + task 组合**（本文档最直接可用的清单）：

| Skill | Δ pass rate |
|---|---|
| `risk-metrics-calculation` | **+30.0%** |
| `gitlab-ci-patterns` | +14.3% |
| `prompt-engineering-patterns` | +10.0% |
| `similarity-search-patterns` | +10.0% |
| `distributed-tracing` | +7.7% |
| `tdd-workflow` | +7.1% |
| `istio-traffic-management` | +7.1% |

**3 个有害的**：`springboot-tdd` −10.0%、`linkerd-patterns` −9.1%、`django-patterns` −9.1%。
作者归因为**版本错配的指导与项目实际上下文冲突**。这给出一个可搬用的**假设**：
负增益 = skill 内容与任务实际上下文冲突，而不是「多了 token」。
在本实验里对应 `ctrl-corrupted` 臂（保结构、毁正确性），由数据判定而非沿用既往结论。

**模型：只测了 Claude Haiku 4.5 + Claude Code。** 作者自己承认这是局限，
并指出 "skill utility is likely modulated by the base model's existing knowledge"
—— 这句话正好是我们用 Qwen3-8B 重跑的动机。

---

## 3. 开源模型上的硬数字（重点）

### 3.1 LatentSkill — arXiv 2606.06087（最贴近我们的设置）

**backbone 全程是 Qwen3-8B（frozen）**，做的正是「in-context skill 文本 → in-weight LoRA」
的转换（hypernetwork skill compiler 把 skill 文档映射成 LoRA 权重 Δs = Gφ(s)）。

**它给了我们最想要的东西：Qwen3-8B 上 in-context skill 的 baseline 数字。**

| 任务 | skill 设置 | 结果 |
|---|---|---|
| **ALFWorld**（6 类家务任务，seen/unseen） | 5 个 skill 按类别配对（Pick / Look / Clean / Heat / Cool / Pick2） | LatentSkill 74.3% seen / 69.4% unseen，比 **In-Context Skill 高 +21.4（seen）/ +13.4（unseen）**，prefill token 少 64.1% |
| **Search-QA**（NQ, TriviaQA, PopQA / HotpotQA, 2Wiki, MuSiQue, Bamboogle） | 3 个 skill 按推理类型（direct_retrieval / multi_hop_reasoning / comparison） | 35.6% avg EM，比 In-Context Skill **+3.0**，skill token 少 72.2% |

对我们的意义：**同一份 skill，Qwen3-8B 上「放进 context」和「压进权重」差 13~21 个点**。
这本身就是一个白盒问题 —— 为什么 in-context 的形式损失这么大。

### 3.2 SkillsInjector — arXiv 2605.29794

研究的是「注入哪些 skill、注入多少、怎么渲染」，agent 与 harness 固定，
**唯一自变量就是注入的 skill context** —— 方法论上和我们的对照设计同构。

**模型**：tau2-bench 与 SkillsBench 用 Qwen3-235B-A22B-Instruct-2507；
**ALFWorld 用 Qwen3-8B**。planner = Qwen3-Embedding-0.6B + MLP；
renderer = Qwen3-8B（从 235B teacher 蒸馏微调）。每组 5 seed，temperature 0.7，H200。
SkillsBench 只用了 87 个任务里**能离线运行的 69 个自足子集**。

**Table 1（task pass rate %）** —— 注意 ALFWorld 那一列是 Qwen3-8B：

| Method | tau2-airline | tau2-retail | tau2-telecom | SkillsBench | **ALFWorld (Qwen3-8B)** | Avg |
|---|---|---|---|---|---|---|
| No-skill | 37.6 | 51.2 | 40.0 | 5.2 | **67.1** | 40.2 |
| Random-skill | 42.4 | 53.0 | 41.9 | 6.7 | **69.0** | 42.6 |
| **Full-library** | 24.4 | 40.5 | 24.6 | 3.2 | **31.5** | 24.8 |
| BM25 | 43.6 | 54.9 | 51.2 | 12.8 | 71.2 | 46.7 |
| Dense Cosine | 45.2 | 55.3 | 54.7 | 14.2 | 72.9 | 48.5 |
| LLM-as-selector | 49.6 | 55.1 | 55.8 | 14.2 | 73.8 | 49.7 |
| SkillRouter | 54.0 | 59.8 | 62.8 | 16.5 | 74.4 | 53.5 |
| Graph of Skills | 56.1 | 60.0 | 60.4 | 15.9 | 75.4 | 53.6 |
| **SkillsInjector** | 60.0 | 61.4 | 67.0 | 22.6 | **82.7** | 58.7 |

**三条直接可用的观察**：

- **整库注入是灾难性的**：ALFWorld 67.1 → 31.5，SkillsBench 5.2 → 3.2。
  负效应幅度远大于正效应，且在 8B 和 235B 上都成立
- **随机注入一个 skill 反而略微为正**（+1.9 / +1.8）—— 说明存在与内容无关的「存在效应」。
  这是**外部**证据，独立于既往 whitebox 的 neutral control 观察；本实验用 `ctrl-neutral` 臂
  在 MedCalc 上重新测一遍（H6），并且**先于其余分析**（见 §5.5）
- SkillsBench 在开源模型上的绝对分数极低（no-skill 5.2%），任务对 8B~235B 都很难

### 3.3 SRA-Bench / Skill Retrieval Augmentation — arXiv 2604.24594（Su et al.）

代码：`github.com/oneal2000/SR-Agents`。**六个开源模型全测**：Qwen3-4B / Qwen3-32B /
Qwen3-235B-A22B、Llama-3.1-8B-Instruct / Llama-3.3-70B-Instruct、Mistral-Small-3.1-24B。
（行为分析部分另加 GLM-5.1 和 GPT-5.4。128K 上下文，temperature 0.7。）
**注意：没有 Qwen3-8B**，最接近的是 Qwen3-4B 和 Llama-3.1-8B。

**任务**：636 个 gold skill 混进 26,262 个网络采集 skill 的噪声语料，
5,400 个实例来自 6 个数据集：**TheoremQA / LogicBench / ToolQA / CHAMP / MedCalc-Bench / BigCodeBench**。
判分用各自标准协议（BigCodeBench 是 pass@1 单测）。

**Table 2 关键行 —— Llama-3.1-8B（最小的那档，最接近我们的算力条件）**：

| Method | TheoremQA | LogicBench | ToolQA | CHAMP | MedCalc | BigCodeBench | Avg |
|---|---|---|---|---|---|---|---|
| LLM Direct | 32.4 | 54.6 | 16.7 | 22.4 | 26.9 | 32.3 | 29.8 |
| **Oracle Skill** | 49.4 | 69.5 | 23.3 | 40.8 | **62.0** | 35.2 | **44.5** |
| Full-Skill Injection | 36.5 | 58.3 | 13.6 | 27.8 | 36.7 | 34.2 | 32.7 |
| LLM Selection | 35.1 | 53.8 | 19.4 | 24.7 | 57.0 | 32.1 | 37.0 |
| Progressive Disclosure | 36.9 | 50.0 | 16.4 | 25.1 | 59.6 | 31.4 | 36.3 |

**这张表是本次调研最有用的单个发现**：

- **MedCalc-Bench 是小模型上信噪比最高的 skill+task 组合**：8B 模型 26.9 → 62.0
  （**+35.1pp**），而且即使用真实检索（Progressive Disclosure 59.6 / LLM Selection 57.0）
  也能拿到绝大部分增益 —— 这个增益**不依赖 oracle**，很稳
- **TheoremQA +17.0pp、CHAMP +18.4pp、LogicBench +14.9pp** 次之
- **BigCodeBench 只有 +2.9pp** —— 又一次印证「代码任务上 skill 几乎没用」
- **ToolQA 上 Full-Skill Injection 是负的**（16.7 → 13.6）
- oracle 与真实检索之间存在系统性 gap；作者另指出**模型的 skill 加载率与是否真的需要
  外部能力无关** —— 瓶颈不只在检索，也在模型判断「何时该加载」

### 3.4 Skill-to-LoRA (S2L) — arXiv 2606.16769

和 LatentSkill 同一思路（skill 文本 → LoRA），但 **base model 是 Qwen3.6-27B**（frozen，vLLM 服务），
固定 21-skill benchmark，每个 skill 训一个独立 adapter（约 6.03M 可训练参数，
约为 base 的 0.022%）。训练输入是 skill-conditioned 合成工作流演示，
**明确不使用 benchmark 任务指令**。结论：LoRA 化的行为在大幅降低 token 开销的同时，
能追平或超过 Full Skill Text prompting。

---

## 4. 其余 skill-centric benchmark 全景

来自综述 **arXiv 2606.11435**（Ding et al., Rutgers / UNC Charlotte，
"Agent Skill Evaluation and Evolution: Frameworks and Benchmarks"，
项目页 `github.com/Cassie07/AgentSkill_Survey`）的 Table 2，六大类：

| 类别 | Benchmark | 规模 | 任务构成 |
|---|---|---|---|
| Utility | **SkillsBench** (2602.12670) | 86 tasks, 7,308 traj, 7 configs | 11 个专业领域 |
| Utility | **SkillCraft** (2603.00718) | 126 tasks | 长程组合式 tool-use，按条目数与调用链深度分级；agent 把成功的工具序列打包成持久 skill 库 |
| Generation | **SkillLearnBench** (2604.20087) | 20 tasks / 100 instances | 6 类 15 子域；三级评测（skill 质量 / 轨迹一致性 / 任务结果） |
| Retrieval | **SRA-Bench** (2604.24594) | 5,400 instances, 636 gold / 26,262 corpus | 6 源数据集，分解为 retrieval / incorporation / application |
| Retrieval | **SkillRouter** (Zheng et al., 2026) | 75 queries / 80K skills | SkillsBench 衍生；只给 name+description 相比给全文，路由准确率**掉 31–44%** |
| Retrieval | **AgentSkillOS** (2603.02176) | 30 tasks, 200 → 200K skills | 多 skill 编排；同样 skill 集下编排显著优于单 skill |
| Safety | **SkillTester** (Wang et al., 2026c) | per-skill | 2 组效用 + 3 组安全探针 |
| Safety | **SkillGuardBench** (Lv et al., 2026) | 581 packages | 包级审计，benign / suspicious / malicious |
| Safety | **SKILL-INJECT** (Schmotz et al., 2026) | 23 skills, 202 pairs | 8 类攻击 |
| SWE | **SWE-Skills-Bench** (2603.15401) | 565 instances, 49 skills | 见 §2.2 |
| Real-world | **WildClawBench** (Ding et al., 2026) | 60 tasks | 活的 OpenClaw 环境，6 类；Docker 隔离、执行后注入判分 |
| Real-world | **SkillForge** (Liu et al., 2026b) | 3,737 tasks / 1,883 tickets | 五类真实云技术支持场景 |

综述自己点出的三个结构性缺口（值得在我们论文的 related work 里引用）：

1. 效用与安全类覆盖 11 个专业领域、581 个可审计包，但**生成类只有 15 子域 20 个核心任务**
2. **没有任何 benchmark 纵向评测「演化」** —— 即 skill 是否在多轮反馈中真的变好，全是单快照
3. **指标几乎全是二元 pass/fail**，忽略 token 成本、延迟、错误类型

### 4.1 SkillLearnBench 的数字（COLM'26，`github.com/cxcscmu/SkillLearnBench`）

**模型：Claude Haiku 4.5 / Sonnet 4.6 / Opus 4.6 + Gemini 3.1 Flash Lite / 3 Flash / 3.1 Pro。
无开源模型。**

| 条件 | Accuracy |
|---|---|
| No Skill | **10.17%** |
| One-Shot 生成 | 30.44% |
| Self Feedback (K=2) | 31.08% |
| Teacher Feedback (K=3) | 27.47% |
| Skill Creator | 27.33% |
| **人写 skill** | **74.50%** |

任务是按「skill-dependent」挑出来的，所以 no-skill 基线低到 10% 是设计使然 ——
**引用时不能当成一般性的 skill 增益**。真正的结论是：
自动生成的 skill 只能拿回人写 skill 增益的约三分之一，且没有方法在所有任务/模型上领先，
**换更强的 LLM 不一定产出更好的 skill**；多轮外部反馈有真实改进，纯自反馈会递归漂移。

### 4.2 SkillFlow benchmark — arXiv 2604.17308

**注意：与本仓库 `../SkillFlow_paper/` 同名，是另一份工作，不要混淆。**

lifelong skill discovery / evolution 协议。harness：Claude Code / Codex CLI / **Qwen-Coder** / Kimi-CLI，
共 11 个模型变体（含 **Qwen-Coder-Next、Qwen3-Coder-480B**、Kimi K2.5、GPT 5.3 Codex 等）。
用 Qwen3-Embedding-4B 做 seed task 与参考 skill 的匹配。

**结论负面的居多**：skill evolution 对部分模型有大幅增益，但
GPT 5.3 Codex 52.41% → 46.39%（**−6.02**）、Qwen-Coder-Next 45.18% → 44.58%（−0.60，
尽管 skill 使用率 44.58%）、Qwen3-Coder-480B 24.70% → 24.1%（−0.6，skill 使用率高达 66.87%）。
作者的 Finding 4：**Qwen 系主要的失败模式是 "skill inflation"** —— 库越攒越大而质量不升。

---

## 4.5 横向对照：模型 · harness · skill 投递方式 · 时间

> **时间说明**：下表的日期是 **v1 提交年月，由 arXiv 编号前缀推得**（`YYMM.NNNNN`），
> 不是从页面上逐篇读出来的。**最新版可能晚于此**，SkillsBench 已知有版本漂移（§2.1），
> 引用时按 §2.1 的要求注明版本。非 arXiv 的条目单独标注。

| 论文 | v1 | 模型 | Harness | skill 怎么投递 | 判分 | 核验 |
|---|---|---|---|---|---|---|
| **SkillsBench** 2602.12670 | 2026-02 | Claude Opus 4.5 / 4.6、Sonnet 4.5、Haiku 4.5、GPT-5.2、Gemini 3 Pro / Flash（7 个，temp 0） | **Claude Code / Gemini CLI / Codex CLI** 三个商业 CLI | `environment/skills/` 下的 SKILL.md 目录，**agent 自己发现并决定读** | 程序化断言，5 trial 平均，固定分母 84 | ✅ |
| **SWE-Skills-Bench** 2603.15401 | 2026-03 | **只有 Claude Haiku 4.5** | **Claude Code** | 拷进 `~/.claude`，"agent automatically detects and integrates any skills present" | pytest 执行式，非 LLM-judge | ✅ |
| **LatentSkill** 2606.06087 | 2026-06 | **Qwen3-8B（frozen）** | 自建 `evals/alfworld/evaluate`，50 步 / 4096 ctx / 4096 max-new | 直接进 context | ALFWorld 成功率、Search-QA EM | ✅ |
| **SRA-Bench** 2604.24594 | 2026-04 | Qwen3-4B / 32B / 235B-A22B、Llama-3.1-8B / 3.3-70B、Mistral-Small-3.1-24B（行为分析另加 GLM-5.1、GPT-5.4）；128K ctx、temp 0.7 | 自建 SR-Agents | **五种设置**：Direct / **Oracle 强制注入** / Full-Inject(BM25 top-1) / LLM Selection(top-50 选一) / **Progressive Disclosure（OpenClaw 式目录 + 按需加载）** | 各数据集原协议；MedCalc 数值容差、BigCodeBench pass@1 | ✅ |
| SkillsInjector 2605.29794 | 2026-05 | Qwen3-235B-A22B-Instruct-2507（tau2 / SkillsBench）、**Qwen3-8B（ALFWorld）**；planner = Qwen3-Embedding-0.6B + MLP，renderer = Qwen3-8B（235B 蒸馏）；5 seed、temp 0.7、H200 | agent 与 harness 固定，**唯一自变量是注入的 skill context** | 注入 context | 任务通过率；SkillsBench 只用能离线跑的 69/87 子集 | ⚠️ |
| Skill-to-LoRA 2606.16769 | 2026-06 | Qwen3.6-27B（frozen，vLLM 服务） | 固定 21-skill benchmark | LoRA 权重 vs Full Skill Text prompting | — | ⚠️ |
| SkillLearnBench 2604.20087 | 2026-04 | Claude Haiku 4.5 / Sonnet 4.6 / Opus 4.6、Gemini 3.1 Flash Lite / 3 Flash / 3.1 Pro。**无开源模型** | — | — | 三级（skill 质量 / 轨迹一致性 / 任务结果） | ⚠️ |
| SkillFlow-bench 2604.17308 | 2026-04 | 11 个变体，含 Qwen-Coder-Next、Qwen3-Coder-480B、Kimi K2.5、GPT-5.3 Codex；匹配用 Qwen3-Embedding-4B | **Claude Code / Codex CLI / Qwen-Coder / Kimi-CLI** | lifelong 发现与演化 | — | ⚠️ |
| 综述 2606.11435 | 2026-06 | —（综述） | — | — | — | ⚠️ |

✅ = 2026-08-29 本轮亲自核过原文正文；⚠️ = 来自第 1–2 轮检索的记录，**本轮未重新核验**。

其余条目的 v1 年月（同样由编号推得，供 §6 第 3 轮参考）：
SkillCraft 2603.00718 → 2026-03；AgentSkillOS 2603.02176 → 2026-03；
Knowledge Activation 2603.14805 → 2026-03；SkillSafetyBench 2605.12015 → 2026-05；
SkillRevise 2606.01139 → 2026-06；cost-aware skill rewriting 2606.09421 → 2026-06；
SkillResolve-Bench 2606.10388 → 2026-06；SkillJuror 2606.11543 → 2026-06；
SkillCAT 2606.13317 → 2026-06；架构综述 2606.20631 → 2026-06；
Task-Decomposition Reranking 2607.06283 → 2026-07；ContinualSkillBench 2608.03874 → 2026-08。
SkillRouter（Zheng et al., 2026）与 §4 表里 SkillTester / SkillGuardBench / SKILL-INJECT /
WildClawBench / SkillForge 无 arXiv 编号记录，时间待第 3 轮补。

### 4.5.1 结论一：「skill 有效」的头部证据全部来自闭源模型 + 厂商 CLI

- SkillsBench 明确写了 **"No open-weight models included"**，7 个模型全是闭源。
- SWE-Skills-Bench 更极端：**整篇只测了一个模型**（Haiku 4.5 + Claude Code）。
  作者自陈局限，原话是 *"All experiments in this work use a single agent configuration:
  Claude Code with Claude Haiku 4.5. Skill utility, however, is likely modulated by the
  base model's existing knowledge and reasoning capabilities."*

所以那个 **+16.2pp** 和那个 **+1.2%**，都是在一种非常特定的模型 × harness 配置下测出来的。
这正是我们用 Qwen3-8B 重跑的动机，但也意味着**我们的数字不能直接和它们并排比较**。

### 4.5.2 结论二：harness 与投递方式的分裂，几乎与开闭源完全重合 ⭐

这是本轮最要紧的发现，直接影响我们怎么报数。

| | 闭源那组 | 开源那组 |
|---|---|---|
| harness | 厂商 CLI（Claude Code / Gemini CLI / Codex CLI） | 各自自建的研究循环 |
| skill 形态 | **磁盘上的文件**，agent 自己发现 | **直接塞进 context** |
| 模型有无「要不要用」的选择权 | **有** | 基本没有 |
| 代表 | SkillsBench、SWE-Skills-Bench、SkillFlow-bench | LatentSkill、SkillsInjector、SRA-Bench |

**这不是同一个干预。** SRA-Bench 恰好两端都做了，把差距量化了出来：

> Qwen3-4B 在 MedCalc 上，**Oracle 强制注入 73.5**，而
> **Progressive Disclosure（OpenClaw 式目录 + 按需加载）只有 45.0** —— 差 **28.5pp**。
> 同时它的 **skill loading rate 只有 33.4%**（Table 6）。

也就是说，这 28.5 点里很大一块**不是「skill 没用」，而是模型压根没去加载**。
SRA-Bench 自己的 RQ5 结论也指向这里：模型的加载行为**与是否真的需要外部能力无关**，
存在「skill-loading hallucination」。

**对我们的直接影响**（已写进 `DESIGN-mechanism.md` §3.2）：
我们选 Oracle 注入、不做检索，测的是 **skill 内容的上限效用**，
**不是** Claude Code 那种「agent 自主发现」协议下的端到端效用。
论文里必须写清楚这两个分母不同，否则读者会拿我们的数字去和 SkillsBench 的 +16.2pp 比。

### 4.5.3 一个待澄清的细节

SkillsBench 对投递方式的表述**两可**：既说 skills 是
*"provided as system-level context preceding the task instruction"*（听起来是 context 注入），
又说是基于文件系统的 `environment/skills/` 目录、"easy to edit, version, share"（听起来是 agent 自取）。
这两句不完全一致。**若要引用它的投递协议，需再翻一次正文确认**，
否则 §4.5.2 那张表里把它归入「agent 自己发现」这一格是有风险的。

---

## 5. 对我们自己实验的直接建议

### 5.1 选哪个 skill + task 做正对照

按「小模型上增益大 + 不依赖 oracle 检索 + 判分确定 + 能离线跑」排序：

1. **MedCalc-Bench + 医疗计算 skill**（SRA-Bench 提供 gold skill）
   —— Llama-3.1-8B 上 +35.1pp，真实检索下仍有约 +30pp。**首选**。
2. **ALFWorld + 按类别配对的 5 个 skill**（LatentSkill 与 SkillsInjector 都用）
   —— Qwen3-8B 上有直接可比的 in-context baseline 数字，且两篇设置基本一致。
3. **CHAMP / LogicBench / TheoremQA**（SRA-Bench）—— +15~18pp，同一套 harness 可复用。
4. **SkillsBench 的 healthcare / manufacturing 子集** —— 增益最大，但需先确认开源模型上
   绝对分数是否会像 SkillsInjector 报的 5.2% 那样触底。**地板效应会毁掉对照**：
   基线贴地时，任何臂之间的差都被压缩到噪声里，消融读不出信号。
   选任务时先验基线落在 20~60% 区间。

### 5.2 明确**不要**选的

- **任何 SWE / 代码任务**：SkillsBench +4.5pp、SWE-Skills-Bench +1.2%、
  SRA-Bench 的 BigCodeBench +2.9pp —— 三篇独立工作一致指向近零增益。
- **整库注入作为「skill 条件」**：那不是在测 skill，是在测长上下文退化（−36pp 量级）。

### 5.3 待检验假设与对应的外部证据

⚠️ 左列**不是我们的既有结论**，是从既往 skillflow/whitebox 工作里继承下来的
**待检验假设**（理由见 §5.5：那批结果未经独立复核）。右列是**外部论文**的独立证据。
两者一致只说明这个假设值得测，**不构成互相印证** —— 每一条都要由本实验的控制臂重新判定。

| 待检验假设（来自既往工作，未复核） | 外部独立证据 | 本实验中由谁判定 |
|---|---|---|
| 「patch 打败 document」 | SkillsBench：2–3 module 的聚焦 skill +18.6pp，优于 exhaustive bundle | 模块 leave-one-out（`A2`–`A6`）：若聚焦优于完整，则去掉某些模块**不该**掉分甚至该涨 |
| 「无内容版本也能赢」/ 存在效应 | SkillsInjector：random-skill 在 5 个 benchmark 上一致微正（+1.5~2.6） | **`ctrl-neutral`（H6），Pilot 阶段先判**；若 ≈ gold，其余内容性解释全部作废 |
| 需要能分辨内容与存在的 control | 综述 2606.11435 的指标缺口 #3；SkillRouter 的 metadata-only vs full-body 掉 31–44% | 这是设计约束不是假设：`ctrl-neutral` / `ctrl-shuffled` / `ctrl-corrupted` 三臂即为此而设 |
| 负增益来自内容冲突而非 token 开销 | SWE-Skills-Bench 三个有害 skill 全部归因于版本错配 | `ctrl-corrupted`（保结构、毁数值）vs `ctrl-neutral`（保长度、换内容）的对比 |

---

## 5.5 当前选型结论（2026-08-29）

调研到此收敛。完整实验设计见 [`DESIGN-mechanism.md`](DESIGN-mechanism.md)，这里只记结论。

### 选定：MedCalc-Bench + SRA-Bench 的 55 个 gold calculator skill

本轮实际下载核实（非转述摘要）：**1,100 实例 / 55 gold skill / 每个恰好 20 条**，
`skill_annotations` 每条恰好指向一个 gold skill；判分为确定性数值容差
（`lower_limit`/`upper_limit`，decimal 实测 **±5%**），**无 LLM-as-judge**；
答案类型 decimal 640 / integer 400 / date 60。

选它的核心理由：

- **动态范围**：Qwen3-4B 22.0 → 73.5（+51.5pp），Qwen3-32B 53.9 → 83.5（+29.6pp）。
  Qwen3-8B 未被测过，夹在中间，预期 +35~45pp。不触底也不触顶。
- **±5% 容差**基本排除了「skill 只是教会正确舍入/单位」这个混淆。
- **skill 模块边界是构造时就有的**：SRA-Bench 论文 A.4.1 的生成 prompt 规定固定 5 模块模板
  （临床背景 / 输入与单位换算 / 符号化流程 / `compute_*()` Python 实现 / worked example），
  正好映射到任务的 S1–S5 步 → 模块消融是干净的、非任意的干预。
- **有 step 级 ground truth**：原始 `ncbi/MedCalc-Bench-v1.0` 的 `Relevant Entities`
  是结构化的抽取变量，中间步骤可**机检**而非 LLM 判。

### ALFWorld 降为备选

- LatentSkill 的 5 个 skill **未随代码发布**，repo 只接受外部 `--skill_context_dir`。
- LatentSkill 报 Qwen3-8B in-context skill = 52.9/56.0，SkillsInjector 报同模型 no-skill = 67.1。
  **给了 skill 比没给还低 10+ 点** → ALFWorld 绝对分强依赖 harness/prompt/step 上限，
  跨论文引用不安全。

### 方法骨架

agentic 循环把原子的「回答」展开成带时间轴的轨迹，于是有**三条正交干预轴**：
内容轴（删哪个模块）、时间轴（skill 在哪几轮可见）、轨迹轴（前 t 步嫁接）。
单轮任务只有第一条轴，所以「模块 C 有用」和「第 2 步有用」是纠缠的，三轴交叉才能拆开。

主读数 = **失败模式转移矩阵**（行 = 无 skill 的首个出错步骤，列 = 有 skill 的）。
因果定位 = **轨迹嫁接**：把 skill 轨迹前 t 轮作强制前缀、然后撤掉 skill 让其续跑，
画成功率 vs t，跃升处即因果瓶颈。

**先跑 Pilot 判 H6（存在效应）**：`ctrl-neutral` 用**另一个 calculator 的 gold skill**
（同模板同长度同分布、内容全错）。若 `ctrl-neutral ≈ gold`，所有内容性解释作废，
停下重新设计。

### 白盒

vLLM 的 OpenAI 接口**只给 logprobs**，拿不到 hidden states / attention。
要内部量必须走 HF transformers，路线是两段式：**vLLM 生成 → 轨迹落盘 →
teacher-forced 单次前向重放**抓内部量。不要边生成边挂 forward hook（显存/速度都吃不消）。
**黑盒先行**：转移矩阵 + 嫁接曲线已能在行为层回答「哪一步」，白盒只在黑盒挑出的
discordant 实例上解释「为什么这一步会被修好」。

### ⚠️ 报数时必须声明的分母差异

见 §4.5.2。我们用 **Oracle 强制注入**，测的是 **skill 内容的上限效用**；
SkillsBench / SWE-Skills-Bench 用的是 **agent 自主发现磁盘上的 skill 文件**，
测的是端到端效用（含「模型愿不愿意加载」这一环）。

SRA-Bench 同时做了两端，差距是 **28.5pp**（Qwen3-4B / MedCalc：Oracle 73.5 vs
Progressive Disclosure 45.0，同时 skill loading rate 仅 33.4%）。

**所以我们的 Δ 不能和 SkillsBench 的 +16.2pp 并排比较。** 论文里要显式写明这一点，
并且最好补一组 Progressive-Disclosure 式的对照臂来标定这个差距 —— 否则
「Qwen3-8B 上 skill 增益 40pp」会被读成「比 Claude Code 上的 16pp 更有效」，那是错的。

### ⚠️ 方法论立场：不把既往 skillflow / whitebox 结果当作可靠先验

本实验的设计与结论**独立自证**，不建立在 `../skillflow.py` 那套 harness 或
`../whitebox/` 既往产出的任何数字/结论之上。理由：

1. 那批结果的可靠性未经独立复核，其中已知至少一次**harness 静默失败被误读为模型能力问题**
   （phantom tool loop：未注册的工具返回普通字符串，小模型据此反复重试直至耗尽预算）。
   在没有系统重跑之前，无法判断还有多少结论受同类问题污染。
2. 四个 eval 入口各自复制了一份 `execute_tool` 和 agent loop，且带熔断器与路径改写。
   同一套逻辑的多份副本意味着修复不一定同步落地，历史结果的可比性存疑。
3. 既往 whitebox 的任务设计（Tier A/B）与本实验的任务、判分、控制臂都不同，
   其内部结论无法直接迁移。

**具体做法**：
- **不复用**现有的四个 eval loop，另写最小循环（见 `DESIGN-mechanism.md` §3.1）。
- 既往观察（如「patch 打败 document」「无内容版本也能赢」）在本实验中
  **一律当作待检验假设而非已知事实**，用本实验自己的控制臂重新验证。
- §5.3 那张「外部佐证」对照表仍然有效 —— 它引的是**外部论文**，不是我们自己的既往结果。
- 若本实验结论与既往 skillflow/whitebox 结果冲突，**以本实验为准**，并记录冲突点。

---

## 6. 待办

- [ ] 第 3 轮：ContinualSkillBench (2608.03874)、SkillCAT (2606.13317)、
      SkillRevise (2606.01139)、SkillJuror (2606.11543)、
      cost-aware skill rewriting (2606.09421)、AgentSkillOS (2603.02176)、
      Knowledge Activation (2603.14805)、架构综述 (2606.20631)、
      SkillResolve-Bench (2606.10388)、SkillSafetyBench (2605.12015)、
      Task-Decomposition Reranking (2607.06283) —— 各自确认模型清单与是否有 Qwen3-8B
- [ ] 拉 SWE-Skills-Bench 的 HF 数据集，看 7 个有效 skill 的原文，判断是否可迁移到 Qwen3-8B
      （优先级已降低：三篇独立工作一致指向 SWE 上近零增益，不作为正对照）
- [x] ~~拉 SR-Agents 仓库，确认 MedCalc-Bench 的 gold skill 格式~~ —— **2026-08-29 完成**。
      HF `WeihangSu/SRA-Bench` 可下载；实测 1,100 实例 / 55 gold skill / 每个恰好 20 条；
      skill schema = `{skill_id, name, description, content, tools}`；
      判分为确定性数值容差（decimal 实测 ±5%），无 LLM-as-judge。详见 `DESIGN-mechanism.md` §1
- [x] ~~确认 LatentSkill 是否放出 ALFWorld 的 5 个 skill 原文~~ —— **2026-08-29 完成：没有放出。**
      repo `yuaofan0-oss/LatentSkill` 要求外部传 `--skill_context_dir`，指向 Xia et al. (2026) 的库。
      另核实其 Qwen3-8B In-Context Skill 基线 = 52.9 seen / 56.0 unseen，
      **与 SkillsInjector 报的 no-skill 67.1 冲突** → ALFWorld 绝对分强依赖 harness，跨论文引用不安全
- [x] ~~把 §5.1 的候选换算成 harness 的具体配置~~ —— **2026-08-29 完成**，见 `DESIGN-mechanism.md` §3
- [ ] 新增：join `ncbi/MedCalc-Bench-v1.0` 取 `Relevant Entities` / `Ground Truth Explanation`
      作为 step 级 ground truth（注意 SRA-Bench 1,100 ≠ 原始 test 1,047，需同时 join train）

---

## 7. 论文链接

- SkillsBench — https://arxiv.org/abs/2602.12670
- SWE-Skills-Bench — https://arxiv.org/abs/2603.15401 · https://github.com/GeniusHTX/SWE-Skills-Bench
- LatentSkill — https://arxiv.org/html/2606.06087v1
- SkillsInjector — https://arxiv.org/pdf/2605.29794
- SRA-Bench / Skill Retrieval Augmentation — https://arxiv.org/abs/2604.24594 · https://github.com/oneal2000/SR-Agents
- Skill-to-LoRA — https://arxiv.org/pdf/2606.16769
- SkillLearnBench — https://arxiv.org/abs/2604.20087 · https://github.com/cxcscmu/SkillLearnBench
- SkillCraft — https://arxiv.org/html/2603.00718v2
- SkillFlow benchmark — https://arxiv.org/pdf/2604.17308
- 综述 Agent Skill Evaluation and Evolution — https://arxiv.org/pdf/2606.11435 · https://github.com/Cassie07/AgentSkill_Survey
