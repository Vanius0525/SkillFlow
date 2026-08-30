# HOWSKILLWORK — skill 为什么 work

研究问题：**skill 文档是通过什么机制帮助 agent 完成任务的？在多步循环里，具体是哪一步
被改善了，为什么是那一步？** 在 Qwen3-8B 等开源模型上做，黑盒为主、白盒为辅。

最后更新：2026-08-31

---

## 现在的状态

**GATE-1 已通过（2026-08-31）。下一步在 4090 上跑 P2。**

| 阶段 | 状态 |
|---|---|
| 文献调研（3 轮检索） | ✅ 完成，选型收敛 |
| 实验设计 | ✅ 完成 |
| P0 数据与代码准备 | ✅ 完成（P0-4 的人工校准顺延，需真实轨迹） |
| P1 harness 校准 | ✅ **GATE-1 通过**（22.0 / 69.6，见 [`RESULTS-P1.md`](RESULTS-P1.md)） |
| **P2 主效应 + H6 判定 ← 下一步** | ⬜ |
| P3–P5 消融 / P6 投递标定 / P7 嫁接 / P8 白盒 | ⬜ |

---

## 文档导航

| 文件 | 内容 |
|---|---|
| [`HANDOFF.md`](HANDOFF.md) | **文献调研**。12+ 篇 skill benchmark 的数字；§4.5 各篇的模型 · harness · 投递方式 · 时间横向对照；§5.5 选型结论与方法论立场 |
| [`DESIGN-mechanism.md`](DESIGN-mechanism.md) | **方法论**。三轴干预（内容 / 时间 / 轨迹）、失败模式转移矩阵、轨迹嫁接、六个机制假设、白盒路线 |
| [`PROTOCOL.md`](PROTOCOL.md) | **可执行流程**。harness 决策、P0–P8 阶段、GATE 判据与停止规则、算力预算 |
| [`RESULTS-P1.md`](RESULTS-P1.md) | **P1 实测结果**。GATE-1 判定、5 轮上限吃掉 −3.9pp 的诊断、工具调用与准确率的待查观察 |
| [`P0-FINDINGS.md`](P0-FINDINGS.md) | **P0 实测结果**。skill 的真实模块结构、四条推翻原设计的发现、step 级 GT 的 join、中性配对审计 |
| [`../howskill/`](../howskill/) | **代码与数据**，可直接搬到 4090。见其 `README.md` |

---

## 结论摘要

### 选定的 skill + task pair

**MedCalc-Bench + SRA-Bench 的 55 个 gold calculator skill。**
1,100 实例 / 55 calculator × 20 / 确定性数值容差判分（decimal ±5%，无 LLM-judge）。

外部数字：Qwen3-4B **22.0 → 73.5（+51.5pp）**，Qwen3-32B 53.9 → 83.5。
Qwen3-8B 未被测过，夹在中间，预期 +35~45pp —— 不触底也不触顶。

**ALFWorld 降为备选**：skill 原文未随代码发布；且两篇论文的绝对分互相冲突
（SkillsInjector 报 no-skill 67.1，LatentSkill 报 in-context skill 52.9/56.0），
说明其绝对分强依赖 harness。

### 方法骨架

agentic 循环把原子的「回答」展开成带时间轴的轨迹，于是有**三条正交干预轴**：
**内容轴**（删哪个模块）、**时间轴**（skill 在哪几轮可见）、**轨迹轴**（前 t 步嫁接）。
单轮任务只有第一条，所以「模块 C 有用」和「第 2 步有用」是纠缠的，三轴交叉才能拆开。

- 主读数 = **失败模式转移矩阵**（行 = 无 skill 的首个出错步骤，列 = 有 skill 的）
- 因果定位 = **轨迹嫁接**：把 skill 轨迹前 t 轮作强制前缀、撤掉 skill 让其续跑，
  画成功率 vs t，跃升处即瓶颈

### 两条必须先过的门槛

- **GATE-1**：复现 SRA-Bench 已发表的 Qwen3-4B 22.0 / 73.5（±5pp）。
  这是我们 harness 正确性的**唯一外部检验**。不过就停下调试，不是发现。
- **GATE-2（H6）**：`gold − ctrl_neutral` 必须显著为正。若中性 skill 与 gold 打平，
  效应来自**存在**而非**内容**，所有内容性解释作废 —— 停下改方向。

---

## P0 推翻或修改了原设计的五处

设计阶段的假设大多来自论文正文；实测 55 份 skill 与源码后，有五处不成立：

1. **skill 正文里没有 Python 实现**（55/55 无 `def`）。论文 A.4.1 说有，实际在
   `tools` JSON 字段里，正文只描述签名 → 「删模块 D」拆成 `−M4`（删描述）与
   `−tool`（删可执行工具）两个干预，其差值 = 「知道有工具」vs「工具真能用」
2. **SRA-Bench 的 MedCalc 本来就是 agentic 的**。55/55 带可执行工具（共 71 个），
   `DirectEngine` 见到 `tools` 就进 `TOOL_CALL/TOOL_RESULT` 循环（上限 5 轮）→
   原以为"我们加工具是刻意偏离"，错了
3. **Example 兼作协议演示**（55/55 含 `TOOL_CALL:` 示范）→ 直接删会把「少了例子」
   和「不会调工具了」混在一起，拆成 `−M5-full` 与 `−M5-clinical` 两臂
4. **单位换算只在 15/55 里** → S3 不是通用步骤，转移矩阵的 S3 行必须分层看
5. **「原始 test 只有 1,047 行、需同时 join train」是错的** → 实际 1,100 行，
   命中 1,098/1,100，不必碰 train

另有一条判据错误在写代码时才暴露：中性配对的泄漏判据若把「任何等于答案的数字」
都算泄漏，会因评分类计算器的答案是小整数而使 14/55 配不上。改为只算**有区分度的值**。

---

## 报数纪律

- 头条数字是 **`gold − ctrl_neutral`**（扣掉存在效应），并列报 `gold − no_skill` 以便对齐外部论文
- 置信区间按 **calculator** 聚类 bootstrap，不是按实例（同 calculator 的 20 条不独立）
- **我们的 Oracle 数字不能与 SkillsBench 的 +16.2pp 并排比较** —— 投递协议不同
  （强制注入 vs agent 自主发现磁盘文件），SRA-Bench 两端实测差 28.5pp。见 `HANDOFF.md` §4.5.2
- 每臂都报 token 成本
- 既往 skillflow / whitebox 的结论**一律作为待检验假设**，不作可靠先验（`HANDOFF.md` §5.5）
