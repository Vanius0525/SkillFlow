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
| 评测入口 | `python -m evals.alfworld.evaluate`，flag 含 `--skill_context_dir` / `--max_steps 50` / `--max_new_tokens 4096` | LatentSkill README |
| 数据 | `alfworld_data/alfworld/` + `config_tw.yaml` | 同上 |

## 3. 未确认、必须读代码才能定的

论文正文都没写，**不要靠猜**（MedCalc 那次「以为没有工具」就是猜出来的）：

1. **baseline prompt 里有没有 few-shot 专家轨迹**。ALFWorld 的经典 ReAct 基线放 2 条同类别
   完整示范，加不加能差十几到二十点 —— 这是 43.6 vs 67.1 那 23pp 最可能的来源。
   **间接证据指向"没有"**：表里 vanilla 的 prefill 只有 **0.44k**，放两条完整轨迹不可能这么短。
   开跑前用代码确认，不要停在这条推断上。
2. 解码参数（temperature / top-p / 是否 `enable_thinking`）—— 正文未披露。
3. 动作格式：ReAct？是否把 admissible actions 列给模型？非法动作怎么处理
   （ALFWorld 对不合法动作返回 "Nothing happens"，烧步还是重提示，对小模型是生死差别）。
4. `context_max_length` / `conversation_max_length` 的实际取值，以及超长怎么截断。
5. **那 5 个 skill 具体是怎么从 62 个里组出来的**（整类拼接？只取 task-specific？带不带 12 个通用的？）。
   prefill 从 0.44k 涨到 1.21k，即 skill 约 **0.77k token**，可以用它反推组合方式。

## 4. 我们要自己写的部分

和 MedCalc 一样，**不直接用它的 evaluate 脚本**，理由不变（`PROTOCOL.md` §0.2）：
时间轴要控制 skill 在第几步可见，轨迹轴要塞强制前缀，两者都**要求我们拥有 message 列表**。

做法照搬 `howskill/loop.py` 的成功路径：**忠实移植它的 prompt 构造、动作解析与判分**，
外面套我们自己的四个钩子（强制前缀 / 可见性调度 / 结构化日志 / 确定性）。
移植的部分不许"改进"——GATE-1′ 只有在这些位与上游一致时才有意义。

## 5. 三个开跑前必须解决的问题

### 5.1 功效：n=138 时约 45%

用 `analyze.paired_delta` 模拟真效应 +9.3pp：

| 形状 | 20 个 seed 里显著 |
|---|---|
| ALFWorld：6 簇 × 23 = 138 | **9/20（约 45%）** |
| MedCalc：55 簇 × 20 = 1,100 | 20/20 |

**即使 skill 真的有效，也有一半概率读不出来。** 对策（开跑前定死，不许事后挑）：
seen + unseen 全上（274）、多 seed、以及下面的聚类单元问题。

### 5.2 聚类单元：6 个类别不够

MedCalc 有 55 个 calculator 可聚类；ALFWorld 只有 6 个任务类别。
6 簇有放回重抽 20,000 次**只产生 74 个不同的均值**，分位数 CI 不可靠；
单臂 CI 宽度从 MedCalc 的 11.5pp 涨到 **31.9pp**。

候选方案（**必须在看到结果之前选定并写进报告**）：
- 按 **game file** 聚类（每个类别下有多个不同房间/物品布局，簇数远多于 6）
- 或按类别分层 + 实例级配对差值，并明确声明簇内相关性未被完全吸收
- 不可接受：当成 274 个独立样本报一个窄 CI

### 5.3 内容轴在这里做不了

skill 只有 `title / principle / when_to_apply` 三个字段、约 30 词，
没有 M1–M5 那样的模块结构，也**没有可执行工具**（P5 不迁移）。
ALFWorld 上能做的内容干预最多是 `−principle` / `−when_to_apply` / `ctrl-neutral`（换成别类的 skill）。

**分工写清楚**：MedCalc 负责内容轴与工具，ALFWorld 负责时间轴与轨迹轴。
不要指望在 ALFWorld 上重做一遍模块消融，也不要用 ALFWorld 的结论去覆盖 MedCalc 的。

---

## 6. 执行顺序

1. 拉 SkillRL 与 LatentSkill 的代码，回答 §3 的五个问题 —— **纯读代码，不占 GPU**
2. 定 §5.2 的聚类单元，算 §5.1 的功效，确定实际要跑多少 episode
3. 装 ALFWorld 数据，跑通 vanilla 单条 episode，确认步数与动作解析
4. 移植 prompt / 动作解析 / 判分 + 我们的四个钩子，写 selftest
5. **GATE-1′**：seen 上复现 43.6 / 52.9（±5pp）
6. 过了才做时间轴（`first` / `late`）与轨迹嫁接（t = 5/10/20/…）
