# ALFWorld — 深度轴的第二个任务

`PROTOCOL.md` §3.9 记录了为什么需要它：MedCalc 实测 2.0 轮，时间轴与轨迹轴撑不起来。
本文件是 ALFWorld 线的**复现规格**，对应 §9 的判定。

最后更新：2026-08-31 · 状态：**规格已定，未开跑**

---

## 1. 对标哪一篇：LatentSkill 的 in-context 臂

ALFWorld 的绝对分跨论文冲突（LatentSkill 无 skill 43.6%，SkillsInjector 同模型 67.1%）。
不去调和，**选一篇照抄**，理由：LatentSkill 的模型（Qwen3-8B frozen）、投递方式
（按类别配对、无检索 = Oracle 强制注入）与我们最接近。

**GATE-1′（硬门槛）**：复现下表 seen 的 **43.6 / 52.9**，±5pp。不过就停下查，和 MedCalc 一样。

### 复现目标（LatentSkill Table，单位 %）

| Split | 臂 | Pick | Look | Clean | Heat | Cool | Pick2 | **Avg** | prefill |
|---|---|---|---|---|---|---|---|---|---|
| seen | Vanilla | 82.9 | 46.2 | 18.5 | 37.5 | 32.0 | 29.2 | **43.6** | 0.44k |
| seen | In-Context Skill | 85.7 | 69.2 | 70.4 | 31.3 | 12.0 | 33.3 | **52.9** | 1.21k |
| unseen | Vanilla | 54.2 | 55.6 | 41.9 | 47.8 | 57.1 | 23.5 | **47.0** | 0.44k |
| unseen | In-Context Skill | 70.8 | 61.1 | 74.2 | 43.5 | 47.6 | 23.5 | **56.0** | 1.23k |

（LatentSkill 自己那一行不用管 —— 它是 LoRA 超网络，不是我们要复现的对象。）

**这张表里最值得做的不是平均值，是分类别的异质性**：seen 上 skill 把 Clean 从
18.5 抬到 70.4（**+51.9**），却把 Cool 从 32.0 打到 12.0（**−20.0**）、Heat 从 37.5 打到 31.3。
同一批 skill、同一个模型，**一类大涨一类大跌**。这与我们 P2 测到的
「错配 skill 比无 skill 差 3.9pp」是同一现象的不同剂量，也是 ALFWorld 值得做的主要理由。

---

## 2. 已确认的设置

| 项 | 值 | 来源 |
|---|---|---|
| 模型 | **Qwen3-8B，frozen** | LatentSkill 正文 |
| 步数上限 | **50 步/episode** | 同上 |
| 集合大小 | **seen 140 / unseen 134** | 同上 |
| skill 数 | **5**，按类别配对、无检索（Pick 与 Pick2 共用一个） | 同上 |
| skill 来源 | SkillRL `memory_data/alfworld/claude_style_skills.json`，62 个 | 已直接读过该文件 |
| 评测入口 | `python -m evals.alfworld.evaluate`，见 `evals/alfworld/run_eval.sh` | LatentSkill 仓库 |
| 数据 | `alfworld_data/alfworld/` + `evals/alfworld/config_tw.yaml` | 同上 |
| skill 文件 | **`evals/alfworld/skills/*.txt`，就在 LatentSkill 仓库里** | 已读 |
| 实跑 flag | `--max_steps 50 --max_new_tokens 2048 --history_length 5 --context_max_length 4096 --conversation_max_length 4096` | `run_eval.sh` |

## 3. 五个未确认项 —— 已从代码读出（2026-08-31）

来源：`yuaofan0-oss/LatentSkill` 的 `evals/alfworld/{prompts.py, evaluate.py, run_eval.sh}`。
**skill 文件也在这个仓库里**（`evals/alfworld/skills/*.txt`），不必去 SkillRL 取。

| # | 问题 | 答案 |
|---|---|---|
| 1 | baseline 有 few-shot 吗 | **没有。** 基线用 `ALFWORLD_TEMPLATE_NO_HIS`，零样本。仓库里另有 `ALFWORLD_REACT_TEMPLATE_NO_HIS` 带 `REACT_FEW_SHOT_EXAMPLE`，**但不是评测用的那个** |
| 2 | 解码 | **贪心**（`do_sample=False`），无 temperature/top-p；`apply_chat_template(..., enable_thinking=True)` |
| 3 | 动作格式 | `<think>…</think>` + `<action>…</action>`；**admissible actions 每步列进 prompt**；解析不中就回退到原文，再不行强制 `look`，并计入 `invalid_action_counts` |
| 4 | 上下文 | `history_length 5` —— **只保留最近 5 个 (obs, action) 对，每个 obs 截到 300 字符**；`context_max_length` / `conversation_max_length` 均 4096 |
| 5 | skill 怎么组 | 按 task type 直接读 `skills/{pick_and_place,cool,heat,clean,look_at_obj_in_light}.txt` 五个文件之一。`general_alfworld.txt` / `mistakes_alfworld.txt` 是 `moe_combo` 模式才单独加载的**组件**，普通 in-context 臂不额外拼 |

**第 1 条解释了 43.6 vs SkillsInjector 67.1 的 23pp**：基线是零样本，不放专家轨迹。
**第 4 条解释了 prefill 恒为 0.44k** —— 上下文不随步数增长，只带最近 5 步。
两条互相印证，之前那个"prefill 太短所以大概没有 few-shot"的推断成立。

⚠️ **`max_new_tokens` 三处不一致**：`run_eval.sh` 写 2048，`evaluate.py` 默认 512，README 例子 4096。
以 `run_eval.sh` 的 **2048** 为准（那是他们实际跑的脚本），并在报告里写明这个歧义。

⚠️ **`enable_thinking=True`** —— 和我们 MedCalc 侧的约定（`thinking=False`）相反。
ALFWorld 复现必须开 thinking，两个任务的这个开关不同，**结果文件里必须各自记录**。

## 4. 我们要自己写的部分

和 MedCalc 一样，**不直接用它的 evaluate 脚本**，理由不变（`PROTOCOL.md` §0.2）：
时间轴要控制 skill 在第几步可见，轨迹轴要塞强制前缀，两者都**要求我们拥有 message 列表**。

做法照搬 `howskill/loop.py` 的成功路径：**忠实移植它的 prompt 构造、动作解析与判分**，
外面套我们自己的四个钩子（强制前缀 / 可见性调度 / 结构化日志 / 确定性）。
移植的部分不许"改进"——GATE-1′ 只有在这些位与上游一致时才有意义。

## 5. 三个开跑前必须解决的问题

### 5.1 / 5.2 功效与聚类单元 —— 已决（2026-08-31）

**先想清楚为什么聚类。** MedCalc 按 calculator 聚，是因为**每个 calculator 一份 skill**，
skill 的效应是 per-calculator 的抽样，55 份 skill = 55 次独立抽样。
ALFWorld **只有 5 份 skill 文档**。换成按 game file 聚类不解决问题 ——
它增加的是任务实例的独立性，不是 skill 的独立性。

**结论：ALFWorld 上不做「skill 一般而言有多少收益」的总体推断。** 5 次抽样支撑不起来。
改为**条件推断**：这 5 份 skill 在这 6 类任务上各自做了什么。

**报数方式定为**：
- 主读数 = **按类别的配对差值**，类别内按实例 bootstrap（实例间确实近似独立：不同房间布局、不同物品）
- 平均值照报，但明确写成「6 个任务类型的平均」，**不给它套一个关于 skill 总体的 CI**
- 6 个类别 = 6 次检验，报多重比较校正后的判据
- 不可接受：把 274 条当独立样本、报一个跨类别的窄 CI

**功效（按类别，实例级 CI，400 次模拟）**：

| 效应（LatentSkill 实测） | n=23（单 split） | n=46（seen+unseen） |
|---|---|---|
| Clean +51.9pp | 96% | **100%** |
| Look +23.0pp | 40% | 62% |
| Cool −20.0pp | 35% | 62% |
| Heat −6.2pp | 5% | 10% |
| 假想 +10pp | 12% | 17% |

**能撑住的结论只有大效应那一类。** Clean 的 +51.9 稳；Cool 的 −20 要两个 split 合起来才到 62%；
Heat 那种个位数效应在这个样本量上**测不出来，也不要去测**。

⚠️ **加 seed 不能增加样本量** —— 上游是贪心解码（`do_sample=False`），重跑逐位相同。
要靠采样加样本就得开 temperature，那就偏离了复现设置。

**因此分两段跑**：
1. **GATE-1′ 用标准 140/134**，贪心、照抄设置，只为对上 43.6 / 52.9 —— 可比性优先
2. **机制实验（时间轴、嫁接）另从 ALFWorld 的 training games 里抽更大的样本**。
   那部分不需要对任何已发表数字，样本量由我们定，功效问题就此解决。
   （ALFWorld 训练集有上千个 game，具体数目装完数据后核实）

### 5.3 内容轴：比预想的能做（修正 2026-08-31）

先前根据 SkillRL 的 JSON（每条 `title / principle / when_to_apply`，约 30 词）判断
「没有模块结构、内容轴做不了」。**读了实际投喂的文件后这条不成立**：
LatentSkill 喂给模型的是 `skills/clean.txt` 这类**约 1,050 词的三段式文档**：

| 段 | 内容 | 与 MedCalc 的对应 |
|---|---|---|
| **General Principles** | 6 条通用策略（系统性探索、先到目的地、进度追踪…） | 无对应，MedCalc 没有跨任务的通用段 |
| **Task Skills**（如 Clean Skills） | 6 条本类专用原则，每条带斜体 *Apply when* 触发条件 | ≈ M3 procedure + M2 的适用条件 |
| **Mistakes to Avoid** | 5 组 Don't / Instead 对照 | ≈ M7 notes，但 MedCalc 只有 11/55 有 |

即 62 条 JSON 是**素材**，按类别渲染成 5 份文档才是实际注入的东西。
所以内容消融可做：**`−general` / `−task` / `−mistakes`** 三个干净的臂。

更省事的是：**仓库已经自带控制臂的变体目录**，不用我们自己构造 ——
`skills_noise/`、`skills_paraphrase/`、`skills_reordered/`、`skills_plaintext/`，
分别对应我们的 `ctrl_corrupted` / 同义改写 / `ctrl_shuffled` / 去格式。
**用他们的版本而不是我们自己扰动**：可比性更好，也少一处自由度。

仍然**不迁移**的是 P5：ALFWorld 的 skill 没有可执行工具。

**分工**：MedCalc 负责工具轴与细粒度模块消融（M1–M5），
ALFWorld 负责时间轴、轨迹轴与**粗粒度三段消融**。
两边的内容轴结论可以互相印证，但粒度不同，不要混report。

---

## 6. 执行顺序

1. ~~拉代码回答 §3 的五个问题~~ **完成 2026-08-31，见 §3**
2. ~~定聚类单元与功效~~ **完成 2026-08-31，见 §5.1/5.2：条件推断 + 两段式样本**
3. 装 ALFWorld 数据，跑通 vanilla 单条 episode，确认步数与动作解析
4. 移植 prompt / 动作解析 / 判分 + 我们的四个钩子，写 selftest
5. **GATE-1′**：seen 上复现 43.6 / 52.9（±5pp）
6. 过了才做时间轴（`first` / `late`）与轨迹嫁接（t = 5/10/20/…）
