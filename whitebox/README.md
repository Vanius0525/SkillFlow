# whitebox — 操作手册

skill 注入的白盒实验。**研究设计在 [`../HANDOFF-whitebox.md`](../HANDOFF-whitebox.md)**
（假设、实验、陷阱、执行步骤）；这份只讲怎么跑。

和 `../HANDOFF.md`（agent harness 黑盒对比）共用模型和仓库，实验方法完全不同。

状态：**代码和数据已就绪，尚未在服务器上跑过任何一次。**

---

## 目录

| 文件 | 作用 |
|---|---|
| `model.py` | **唯一碰权重的模块**。加载、hook、激活补丁、注意力敲除、打分 |
| `selftest.py` | 七项自检。跑实验前必须全过 |
| `e0_effect.py` | Phase 0 效应筛查（第 3 步）。**行为层，无层间数据** |
| `e2_patch.py` | **E2 激活补丁层扫描 —— 恢复率 vs 层** |
| `e1_knockout.py` | **E1 注意力敲除层扫描 —— 依赖度 vs 层** |
| `tasks/filler-neutral.md` | E1 的对照文档（结构相似、任务无关） |
| `run-whitebox.sh` | 服务器端一键运行（体检 → 自检 → Tier A → Tier B） |
| `contamination.py` | skill 是否泄漏答案 |
| `setup-whitebox.sh` | 服务器端体检 + 可选安装 |
| `tasks/tier_a/` | 合成任务（正对照）：虚构 Zorb 单位制 |
| `tasks/tier_b/` | 真实任务：SciBench 物理化学 + 两份知识型 skill |
| `results/<run-id>/` | 每次跑的产物 |

---

## 服务器上跑

```bash
cd /inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness/whitebox
../run-server.sh stop          # vLLM 按 gpu_memory_utilization 预留显存,先让开
./setup-whitebox.sh            # 只检查，不动环境
./setup-whitebox.sh --install --download
```

`setup-whitebox.sh` **默认一个包都不装**。这个 venv 同时供着 vLLM，而 vLLM 对
torch 版本很挑；一次顺手的 `pip install -U` 就可能把黑盒那批实验弄坏。torch 无论
如何都不由这个脚本安装或升级。

然后按顺序：

```bash
# 1. 自检 —— 七项全过才往下走
python selftest.py --model ../models/Qwen3-1.7B

# 2. Tier A 正对照 —— 这里没有大效应 = 流水线坏了，不是假设错了
python e0_effect.py --model ../models/Qwen3-1.7B \
  --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
  --mode mc --run-id tierA-dev

# 3. Tier B 效应筛查 —— 真实问题所在
python e0_effect.py --model ../models/Qwen3-8B \
  --tasks tasks/tier_b/tasks.jsonl --skill tasks/tier_b/SKILL.pchem-constants.md \
  --mode num --limit 120 --run-id tierB-const-8b \
  --filter-known tasks/tier_b/tasks.filtered.jsonl
```

**第 1 步不能跳。** 七项自检测的不是假设，是代码有没有做它声称的事。坏掉的干预照样
产出数字，只是没有意义。

---

## 模型需要怎样使用 skill 才能答对

这是设计这两层任务时最要紧的问题——如果 skill 里的信息不是**必须**的，或者不用读
skill 也能猜到，那测出来的效应就不是"skill 起作用"。

### Tier A：虚构单位制（47 题）

题目长这样：

```
A Kelmar document lists a quantity of 4 glorn. How many dref is that?
A. 4
B. 336
C. 28
D. 36
```

**没有 skill**：`glorn` 和 `dref` 是编出来的词，模型没有任何依据。准确率 = 随机
（25%），这是构造保证的，不是观察到的。

**有 skill**，模型必须依次做四件事：

1. **判定家族** —— 两个单位都在 Length 表里（跨家族不可换算）
2. **查两行** —— glorn 的 "In base units" = 7，dref = 1
3. **算一次** —— 4 × 7 / 1 = 28
4. **匹配选项** —— 28 是 C

所以要求的操作是：**在一张表里定位两行、取出两个数、做一次乘除、匹配到选项。**

这是刻意压到最小的：算术只有一步，因为要测的是"skill span 里的信息有没有进入计算"，
不是"模型会不会算"。

**三个干扰项各对应一种具体的读错方式**：

| 选项 | 怎么来的 | 说明 |
|---|---|---|
| C. 28 | 4 × 7 | 正确：读了 glorn 那一行 |
| A. 4 | 4 × 1 | 读了 dref 那一行（没换算） |
| B. 336 | 4 × 84 | 读了 varak 那一行（同表，错行） |
| D. 36 | 4 × 9 | 读了 pelm 那一行（**读错了表**，那是质量） |

**答错本身带信息**——它告诉你模型抓的是哪一行。这对 E1（注意力敲除）和 E4（分块
消融）直接有用：如果敲掉某层对 skill 的注意力之后错误从"错行"变成"随机"，说明那一
层负责的是定位而不是读取。

**关于 hops**：表里第三列直接给出"折合成基础单位"的值，所以跨 1 跳和跨 3 跳的算术
量完全一样（都是查两个数、算一次）。这是有意的——`hops` 因此是一个干净的自变量，
它变化的是"要读表里多远的一行"，而不是"算术有多难"。

**污染**：生成器会读 skill，把答案出现在 skill 里（worked examples 会给出具体数字）
的题全部剔除。这次剔了 15 题，剩 47。不剔的话模型可以照抄例子而不查表，那会一律
表现成 H1，机制就分不出来了。

### Tier B：SciBench 物理化学（196 题池）

两份 skill **内容类型互斥**，这是 E2 预注册预测能成立的前提。

#### `SKILL.pchem-constants` —— 只有数值，没有方法

题目例：

> Suppose that 10.0 mol C₂H₆(g) is confined to 4.860 dm³ at 27 °C. Predict the
> pressure exerted by the ethane from the perfect gas.  → 50.7 atm

模型必须：

1. 认出需要哪个常数（气体常数 R）
2. **挑对单位那一版**——压强要 atm、体积是 dm³，所以要 `R = 0.08206 L atm K⁻¹ mol⁻¹`，
   不是 8.314
3. 用上换算规则 `T/K = θ/°C + 273.15` → 300.15 K
4. 代入求解

模型多半"知道" R，但**知道的是哪一版**是关键。挑错单位那一版，答案就差一个常数因子。
这份 skill 提供的是**具体数值**，所以预期走 H1（检索）。

#### `SKILL.pchem-procedure` —— 只有方法，没有一个数值

同一题，这份 skill 提供的是：给了 p、V、n、T 中的三个求第四个 → 用理想气体定律；
以及符号约定、电子数怎么数、报告前怎么检查（符号、量级、单位、方向）。

**它里面一个常数都没有。** 所以它要是有效，效果只能来自**选对关系式和方向**，
不可能来自提供信息。预期走 H2（选择）。

#### 这个对照就是 E2 的判决

| skill | 抽象层级 | 预测（跑之前写死） |
|---|---|---|
| `pchem-constants` | 偏 `example` | 激活补丁**压不进**单个向量 |
| `pchem-procedure` | 偏 `principle` | 激活补丁**压得进** |

抽象层级的三分来自 SAPO（见 HANDOFF §9.2）。预测写在跑之前，跑完直接对照，避免
在多重比较里挑显著的讲故事。

#### 单位必须写进 prompt

SciBench 有些题把比例因子放在单位字段里（答案 `1.602`，单位 `10⁻¹⁷ J`）。不声明
单位的话模型答 `1.602e-17`，scorer 判错，测到的就成了约定不一致而不是化学。
`model.py:build_messages` 会把单位加进用户轮。

---

## E2：第一个层间实验

`e0_effect.py` 全是行为层测量，不产生任何层间数据。**`e2_patch.py` 才是。**

```bash
# 先在 Tier A 上跑 —— 正对照，效应必然大，用来确认曲线可读
python e2_patch.py --model ../models/Qwen3-1.7B \
  --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
  --mode mc --limit 40 --run-id e2-tierA

# Tier B，用 e0 筛过的题（--filter-known 的产物）
python e2_patch.py --model ../models/Qwen3-8B \
  --tasks tasks/tier_b/tasks.filtered.pchem-procedure.jsonl \
  --skill tasks/tier_b/SKILL.pchem-procedure.md \
  --mode num --limit 60 --layer-step 2 --run-id e2-tierB-proc
```

它做的事：对每一层 ℓ，跑有 skill 缓存最后一个 prompt token 的 residual → 跑无
skill 时把那个向量补进第 ℓ 层同一位置 → 算恢复率

```
恢复率 = (补丁后 − 无skill) / (有skill − 无skill)
```

输出是三条曲线（终端里用 sparkline 画出来，ssh 上可读）：

| 条件 | 作用 |
|---|---|
| `real` | 本题自己缓存的向量 |
| `mismatched` | **别的题**的向量。它要是也能恢复,说明测到的是"扰动"而不是 skill |
| `mean` | 所有题的**平均**向量。它要是和 real 一样好,说明效应是一个全局方向,不是逐题内容 —— 比 H2 更强的结论 |

后两条不是装饰。**缺了它们,恢复率这个数没法解释。**

### 跑之前必须满足的前提

**这对 (任务, skill) 必须已经过了 Phase 0 门槛。** 恢复率是以行为差值为分母的比
值；分母是噪声的话，这个比值不是"小"，是**没有定义**。脚本会在分母过小时打印警告，
但它不会替你停下来。

### 预注册的预测（跑之前就写死）

| skill | 抽象层级 | 预测 |
|---|---|---|
| `pchem-procedure` | principle | **压得进**向量（高恢复率）|
| `pchem-constants` | example | 压不进 |
| `zorb-units` | example | 压不进 |

来源见 HANDOFF §9.2（SAPO 的 principle/pattern/example 三分）。写在跑之前，跑完
直接对照 —— 避免在多重比较里挑显著的讲故事。

### 一个实现上的关键点

补丁必须落在**最后一个 prompt token**，不是序列最后一个 token。打分时 prompt 和
答案是拼在一起做一次前向的，所以位置用的是 `prompt_len - 1` 的绝对下标；用 `-1`
会补到答案内部，测的就完全是另一回事了。

---

## E1：注意力敲除层扫描

```bash
python e1_knockout.py --model ../models/Qwen3-1.7B \
  --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
  --mode mc --limit 40 --run-id e1-tierA

# 8B 先粗扫（每 4 层一组），定位到热点再用 --group 1 细扫那一段
python e1_knockout.py --model ../models/Qwen3-8B \
  --tasks tasks/tier_b/tasks.filtered.pchem-constants.jsonl \
  --skill tasks/tier_b/SKILL.pchem-constants.md \
  --mode num --limit 60 --group 4 --run-id e1-tierB-const
```

把所有位置**指向 skill token span 的注意力**屏蔽掉，一层（或一组层）一次，测正确
答案 logprob 掉多少。掉得最多的层 = 真正读 skill 的层。

### 对照才是设计的核心

屏蔽任何一段都会扰动注意力，扰动大小随屏蔽的 key 数量增长。所以 prompt 里**同时**
放着 skill 和一份中性填充文档（`tasks/filler-neutral.md`），每层测两次：

```
effect  = lp(不屏蔽) − lp(屏蔽 skill)
control = lp(不屏蔽) − lp(屏蔽 filler)
net     = effect − control     ← 只有这个可解释
```

两段屏蔽的 token 数取**二者较小值精确对齐**，所以对照是构造出来的，不是靠两份文档
碰巧差不多长。两个条件下模型看到的内容完全一样，唯一差别是挡住了哪一段。

单报 `effect` 等于把"挡住任意同长度片段都会造成的损伤"算到 skill 头上。

### 和 E2 互相校验

两个实验对同一件事做出**可以互相矛盾**的预测：

| E2 恢复率 | E1 峰值位置 | 一致吗 | 读作 |
|---|---|---|---|
| 高 | 早层 | ✓ | H2：一次性读入，之后不再需要 |
| 低 | 中后层持续 | ✓ | H1：反复回看 skill 文本 |
| 高 | 中后层持续 | ✗ | **矛盾** —— 其中一个是仪器问题，先查 selftest |
| 低 | 无显著峰 | ✗ | 多半效应量不够，回去看 e0 |

**先跑 E2**，它的结果决定 E1 是主线还是验证。两个都跑完再用上表对一次，比单看任何
一条曲线可靠。

### 最脆弱的一处

按层敲除靠 hook `self_attn` 改写 `attention_mask` 关键字 —— 把 4D mask 当模型参数
传下去是**全层生效**的，回答不了"哪些层读了它"。这个 hook **最依赖 transformers
版本**，所以它自己数调用次数，`e1_knockout.py` 在计数为 0 时直接报错退出。

原因是：**一个从不触发的 hook 会给出完全平坦的层曲线，而那看起来和"没有任何层依赖
它"一模一样。** `selftest.py` 第 5b 项专门守这个。

---

## 冻结与可复现

任务集由生成器产出并冻结，附 sha：

```bash
cd tasks/tier_a && python build.py --check     # 校验提交的文件和生成器一致
cd tasks/tier_b && python build.py --check
python contamination.py                         # 应当三行全 OK
```

`--check` 进了 `setup-whitebox.sh`，所以每次体检都会验一遍。skill 改一个字，
生成器排除的题目集合就可能变，`--check` 会当场报出来。

全程 greedy 解码（`temperature=0`）。有采样就分不清"skill 的作用"和"这次抽样运气好"。

---

## 已知的坑

1. **`selftest.py` 第 3 项（空操作补丁）专抓 prefill/decode 混淆。** 带 KV cache
   生成时，补丁必须只挂在 prefill 那一次前向上；挂在每个 decode step 上会在整个生成
   过程里反复注入，结果没有意义，但**看起来完全正常**。

2. **注意力敲除要求 eager attention。** sdpa 和 flash 不可靠地处理自定义 4D mask，
   会静默忽略。`model.py` 默认 `attn_implementation="eager"`，慢但正确。自检第 5 项
   会验证 mask 真的挡住了。

3. **显存。** 8B bf16 约 16GB，加上 eager attention 的注意力矩阵（seq² × heads）
   在长上下文下涨得快。先用 1.7B 调通。

4. **别用 heredoc 改这些 Python 文件。** 这个仓库的 `bash` heredoc 会把 `\b` 变成
   真正的退格字节。`tier_a/build.py` 的正则被这样毁过一次：模式匹配不到任何东西、
   过滤器静默失效，而 `sed` 和 `inspect.getsource` 都把那个字节渲染成不可见，源码
   看上去完全正确。两个 `build.py` 里的正则现在都用 `[0-9]+` 而不是反斜杠类。
