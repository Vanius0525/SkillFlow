# P0 实测结果 — 55 个 MedCalc gold skill 的真实结构

执行日期：2026-08-29 · 对应 `PROTOCOL.md` 的 P0-1 / P0-2

**结论：`PROTOCOL.md` §1.2 的「A.4.1 五模块模板」按字面理解被证伪，
但存在一个更好的、经验导出的模块结构，切分率 100%。GATE-0 的模块项通过。**

---

## 0. 数据获取（附：一个可复用的绕路方法）

`corpus.json` 232 MB，直连与镜像的持续传输都会被重置（实测 49 B/s，ETA 54 天）。
**可用的办法**：636 个 gold skill 全部位于文件开头，`web_*` 干扰项从约 20 MB 起才出现。
用 `curl -C -` 反复断点续传拿到**前 11.7 MB 的连续前缀**，再从截断的 JSON 数组里
逐个 `raw_decode` 抢救出完整对象即可。

恢复到 1,514 个 skill：theoremqa 320 / bigcodebench 139 / champ 89 /
**medcalcbench 55** / logicbench 19 / toolqa 14 / web 878。
**六个数据集的 gold skill 全部齐了（636/636）。**

已存 `medcalc_skills.json`（55 条）。

---

## 1. 真实的章节结构

55 份文档，每份 4–9 个 `###` 小节（中位数 5）。按「出现在多少份里」统计：

| 章节标题 | 出现 | 性质 |
|---|---|---|
| `Required Inputs` | **55/55** | 通用 |
| `Example` | **55/55** | 通用 |
| `Calculation Tool`(47) + `Calculation Tools`(8) | **55/55**（并集） | 通用 |
| `Computation`(36) + `Scoring Criteria`(19) | **55/55**（并集） | 通用，**两种互斥形态** |
| `Unit Conversion`(13) + 变体(2) | 15/55 | **可选** |
| `Key Notes`(6) + `Important Conventions`(5) | 11/55 | 可选 |
| 一次性标题（`EKG`/`Special Cases`/`MME Conversion Table`…） | 各 1 | 长尾 |

正文长度：min 1,104 / 中位 2,078 / max 6,523 字符（均值 2,380，约 500 token）。

### 1.1 修正后的模块定义（替换 `PROTOCOL.md` §1.2）

| 模块 | 定义 | 覆盖 | 对应步骤 |
|---|---|---|---|
| **M1 context** | 首个 `###` 之前的引言段 | 55/55 | S1 认对计算器 |
| **M2 inputs** | `Required Inputs` | 55/55 | S2 变量抽取 |
| **M3 procedure** | `Computation` ∪ `Scoring Criteria` | 55/55 | S4 套公式/评分 |
| **M4 tool-doc** | `Calculation Tool(s)` — **只描述签名** | 55/55 | S4（工具调用） |
| **M5 example** | `Example` | 55/55 | S5 + **协议演示**（见 §2.3） |
| M6 units | `Unit Conversion` 及变体 | 15/55 | S3 单位归一 |
| M7 notes | `Key Notes` / `Important Conventions` | 11/55 | 缺省值与边界处理 |

**五个通用模块的切分率 = 100%**，消融方案可以照常做，但**消融单位要换成 M1–M5**，
M6/M7 只能在拥有它们的子集上做（15 和 11 条 calculator，n 太小，降级为观察性）。

---

## 2. 四条推翻或修改原设计的发现

### 2.1 ⚠️ 正文里没有 Python 实现 —— 「模块 D」不存在

论文 A.4.1 的模板写着要有 *"A Python function compute_{name}(...)"*，
但**55/55 的正文里都没有 `def`**。实际情况是：

- 正文的 `Calculation Tool` 小节**只描述签名与参数含义**
- 真正的实现在 skill 的 **`tools` JSON 字段**里，独立于正文

所以原计划的「删掉模块 D」是个**歧义操作**，现在必须拆成两个互不相同的干预：

- **`−M4`**：删掉正文里的工具描述（模型不知道有这个工具）
- **`−tool`**：删掉 `tools` 字段（工具不存在，无法执行）

这两者的差值本身就是一个干净的读数：**「知道有工具」与「工具真的能用」各自值多少分。**

### 2.2 ⚠️ 55/55 的 skill 都带可执行 tools —— SRA-Bench 的 MedCalc 本来就是 agentic 的

实测：46 份带 1 个工具、4 份带 2 个、3 份带 3 个、2 份带 4 个，**合计 71 个工具，
全部含可执行的 `implementation`**（`def ...` 源码字符串）。

而 SR-Agents 的 `DirectEngine` 里有：

```python
tools = [t for s in skills for t in s.get("tools", [])]
if tools:
    model_output, transcript = run_with_tools(...)   # TOOL_CALL/TOOL_RESULT 循环，上限 5 轮
```

**所以 Oracle Skill 条件下 MedCalc 一直是多轮工具循环**，不是我先前判断的单轮问答。
`PROTOCOL.md` §P5 的前提（"SRA-Bench 无工具，我们加工具是刻意偏离"）**作废**。

**这其实是好消息**：
- P1 复现不需要我们额外搭工具环境 —— 照抄 `run_with_tools` 即可
- 「skill 解锁工具使用」（H5）不再需要我们自己造，benchmark 自带
- 而且工具是 **skill 自带的**，不是环境预置的 —— 这正是「skill 提供能力」最纯粹的形态

### 2.3 ⚠️ Example 同时是「协议演示」—— 消融它会有混淆

55/55 的 `Example` 小节里都出现了 `TOOL_CALL: ...` / `TOOL_RESULT: ...` 的完整演示。
也就是说 M5 承担了两个功能：

1. 临床演算的 worked example
2. **教模型 `TOOL_CALL:` 这个调用语法长什么样**

直接 `−M5` 会同时抹掉两者，若观察到掉分，无法区分是「少了例子」还是「不会调工具了」。
**处置**：M5 的消融拆成两臂 ——
- `−M5-full`：整节删除
- `−M5-clinical`：保留一个最小的 `TOOL_CALL:` 语法演示，只删临床病例内容

两者之差 = 协议演示的价值；`−M5-clinical` vs 完整 = worked example 本身的价值。

### 2.4 单位换算只存在于 15/55

原设计把 S3（单位归一）当作一个通用步骤，实际只有 15 个 calculator 有 `Unit Conversion` 小节。
**失败模式转移矩阵里的 S3 行必须按「该 calculator 是否涉及单位换算」分层**，
否则 40 条里混进 40 条根本没有单位问题的实例，信号会被稀释。

---

## 3. 从 SR-Agents 源码读到的实现细节（P1 复现要用）

已取回并读过：`medcalcbench.py` / `prompts.py` / `direct.py` / `tool_loop.py` /
`oracle.py` / `progressive_disclosure.py` / `base.py` / `llm.py` / `definitions.py` / `runner.py`。

**skill 注入格式**（`prompts.py`）：
```
Relevant Skill:
{skill_content}

{原 user prompt}
```
多个 skill 用 `\n---\n` 连接。

**MedCalc 的 prompt**（`prompts.py::_build_medcalcbench`）：
- system：`You are a helpful assistant for calculating a score for a given patient note. Please think step-by-step to solve the question and then generate the required score.`
- user：题面 + 要求最后一行输出 `ANSWER: <your answer>`，并规定数值只给数字、日期用 MM/DD/YYYY、分数给整数、ANSWER 行不带单位和解释

**答案抽取**（`medcalcbench.py::_extract`，优先级从高到低）：
`ANSWER:` 行 → JSON `answer` 字段 → trigger 短语 → 日期正则 → 孕周正则 → **最后一个数字** → 最后一行

**判分**（`_eval`）：
- 日期：`calculator_id ∈ {13, 68}`，`%m/%d/%Y` 精确相等
- 孕周：`calculator_id == 69`，(weeks, days) 元组相等
- 整数：`calculator_id ∈ {4,15,16,17,18,20,21,25,27,28,29,32,33,36,43,45,48,51,69}` 或 `output_type=="integer"`，`round(pred)==round(gt)`
- 小数：`lower_limit <= pred <= upper_limit`
- 抽取前先 `strip_think_tags()`

**工具循环**（`tool_loop.py`）：
- 语法 `TOOL_CALL: fn(a=1, b="x")`，正则须**整行匹配**
- `_MAX_TOOL_ROUNDS = 5`
- 受限命名空间：仅 `_SAFE_BUILTINS` + `math`
- 返回 `(model_output, transcript)`——**`model_output` 只含模型生成的 token，
  `TOOL_RESULT` 只进 transcript**。判分喂的是 `model_output`
- 工具执行异常被吞成 `f"Error: {e}"` 继续

**引擎选择**（`definitions.py`）：MedCalc 的 `llm_direct` 与 `oracle_skill` 都用 `engine="direct"`
（只有 ToolQA 用 `react`）。

### 3.1 ⚠️ P1 复现的一个风险点

`DirectEngine.__init__` 默认 `thinking=False`，但 `medcalcbench.py` 又调用了 `strip_think_tags()`。
两者并存说明 thinking 的开关可能随实验而变。我们的部署默认 `enable_thinking:false`
（见 [[qwen3-skillflow-deployment]]）。**若 P1 复现不出 22.0 / 73.5，thinking 开关是第一个要试的变量。**

---

## 4. 对 PROTOCOL.md 的修改清单

- [x] §1.2 模块表 → 换成本文 §1.1 的 M1–M7
- [x] §P3 消融臂 → `−M1`..`−M5` + `−tool` + `−M5-clinical`，M6/M7 降级为分层观察
- [x] §P5 前提作废 → 改为 `−M4`（工具描述）与 `−tool`（可执行工具）的二维对照
- [x] §3 判分与 prompt → 直接采用 SR-Agents 的实现，不自己写
- [ ] §4 step 级读数 → S3 行需按「是否有 Unit Conversion 小节」分层

---

---

## 5. P0-3 step 级 ground truth 的 join —— 完成，99.8%

### 5.1 数据源：原始 v1.0 是**受限数据集**，走 GitHub 绕过

`ncbi/MedCalc-Bench-v1.0` 在 HF 上是 **gated**（"Access to dataset is restricted.
You must have access to it and be authenticated"），`resolve/main` 只返回 133 字节的提示。

**可用替代**（均无需认证）：
- ✅ **采用**：GitHub `ncbi-nlp/MedCalc-Bench` 的 `datasets/test_data.csv`（5.35 MB，未压缩、非 LFS）
  —— 这就是 v1.0 原版，与 SRA-Bench 同源
- 备选：HF `nsk7153/MedCalc-Bench-Verified`（ungated，含 parquet 2 MB）。
  但它是**修订版**，答案可能与 SRA-Bench 依据的 v1.0 不一致，非必要不用

### 5.2 join 结果

| 指标 | 结果 |
|---|---|
| SRA-Bench 实例 | 1,100 |
| v1.0 test 行数 | **1,100** |
| **精确 1:1 命中** | **1,098 / 1,100 = 99.8%** |
| 歧义（同 calculator 下多行匹配） | 2 |
| 未命中 | **0** |
| **GT 答案一致性**（原版 vs SRA-Bench） | **1,098 / 1,098 = 100%** |
| `Relevant Entities` 解析为非空 dict | **1,098 / 1,098 = 100%** |

**匹配方法**：不解析 question（SRA 的格式是 `Patient Note:\n{note}\n\n{question}`，
**没有 `Question:` 分隔符**，且病历本身含空行，解析会失败——实测 0/1100）。
改用**包含匹配**：`calculator_id` 相同 且 原版 `Patient Note`（归一化空白后）是
SRA `question` 的子串。

### 5.3 ⚠️ 修正一条先前的记录

`HANDOFF.md` §1.1 曾写「SRA-Bench 1,100 ≠ 原始 test 1,047，需同时 join train」。
**这是错的**：HF 的 dataset_info 声明 test=1047，但**实际 CSV 有 1,100 行**，
且 1,098 条直接命中，**完全不需要 join train**。已在 `HANDOFF.md` 更正。

### 5.4 step 级 GT 的可用性

`Relevant Entities` 是结构化 dict，例：

```python
{'sex': 'Male', 'age': [87, 'years'], 'weight': [48.0, 'kg'],
 'height': [163.0, 'cm'], 'creatinine': [1.4, 'mg/dL']}
```

- 每实例实体数：min 1 / 中位 **3** / max 30
- **54% 的实体值带显式单位**（`[数值, 单位]` 二元组）→ **S2 变量抽取与 S3 单位归一都可机检**
- 覆盖全部 55 个 calculator（54 个各 20 条，1 个 18 条）

`Ground Truth Explanation` 是逐步自然语言推导，**含中间值与单位换算的显式写法**，例：
*"The patient's height is 163.0 cm, which is 163.0 cm * 1 m / 100 cm = 1.63 m."*
长度 min 260 / 中位 1,247 / max 7,444 字符；**346/1,098 明确含单位换算步骤**
（与 §2.4 的「M6 只在 15/55」互相印证：单位问题确实只涉及部分 calculator）。

**结论：`PROTOCOL.md` §4 的 step 级读数依赖成立，GATE-0 的 join 项通过（99.8% ≫ 90%）。**
已存 `p0_3_joined.json`（1,098 条）。

---

---

## 6. P0-5 中性对照配对 —— 完成，审计干净

配对规则：另一个 calculator 的 gold skill，**长度接近 + 跨计算器族 + 不含本题答案值**。

| 审计项 | 结果 |
|---|---|
| 配对成功 | **55 / 55** |
| 同族配对 | **0** |
| 答案值泄漏 | **0** |
| 长度比（中性/gold） | min 0.459 / **中位 0.982** / max 1.282 |

### 6.1 ⚠️ 一个差点毁掉这一臂的判据错误

第一版把「中性 skill 含有任何等于某条实例答案的数字」都算作泄漏，结果 **14/55 配不上**。

原因：评分类计算器的答案是**小整数**（CHA2DS2-VASc 0–9、Glasgow 3–15），
而**任何 skill 文档的评分表里都有小整数**，于是候选被清空。

修正：只把**有区分度的值**算作泄漏 —— 含小数部分，或绝对值 ≥ 25。
真正要防的是「抄到题目自己的特征值」，不是「出现了数字 4」。
判据在 `howskill/arms.py::is_distinctive`，改后 55/55 全部配上且审计为 0。

---

## 7. P0-6 循环实现 —— 完成，38 项离线自检全过

**没有从零写**，而是移植 + 加钩子：

- **忠实移植**（`grade.py` / `prompts.py`）：MedCalc 的 prompt、五级答案抽取、
  判分规则（date/gestational/integer 的 calculator_id 集合）。
  **不得"改进"** —— P1 复现别人发表的数字，只有抽取与判分逐位一致才有意义。
- **fork + 加钩子**（`loop.py`）：在 SR-Agents 的 `run_with_tools` 基础上加了
  ① 强制前缀注入（P7）② skill 可见性调度（P4）③ 结构化 per-turn 落盘 ④ 确定性配置。
  判分口径与上游一致：`model_output` 只含模型生成的 token，`TOOL_RESULT` 只进 transcript。

**离线自检**（`python -m howskill.selftest`，无需 GPU）覆盖数据完整性、模块切分、
13 个臂的构造、prompt 格式、判分的 8 个边界用例、工具循环、
**时间调度的四个断言**（first/late 各验 skill 在第 0 轮与第 1 轮的可见性）、
**嫁接前缀真的进了 context**、step 解析。**38/38 通过。**
另跑了 55 skills × 13 arms = **715 次臂构造，0 失败**。

---

## 8. 交付物

代码与数据在 **`../howskill/`**，可直接搬到 4090：

```
data/   medcalc_skills.json  medcalcbench.json  stepgt.json  neutral_pairs.json
howskill/  modules arms prompts grade loop steps run analyze selftest llm
README.md  服务器上的 setup 与 P1→P7 的具体命令、GATE 判据、报数纪律
```

数据随包提交（约 6 MB），服务器不必再跟网络搏斗。

## 9. 仍未完成（需要 GPU，留到服务器上）

- [ ] **P0-4 中间值解析器的人工校准** —— 解析器已写好（`steps.py`），但**校准需要真实轨迹**，
      而现在一条都没有。正确顺序是 **P1 跑完后**用它的轨迹当校准集，人工核 50 条，
      报告解析率；<80% 则 step 级读数降级（`PROTOCOL.md` §6）
- [ ] P1 → GATE-1 → P2 → GATE-2 → P3–P7
