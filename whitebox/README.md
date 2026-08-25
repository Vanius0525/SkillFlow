# whitebox — 操作手册

skill 注入的白盒实验。**研究设计在 [`../HANDOFF-whitebox.md`](../HANDOFF-whitebox.md)**
（假设、实验、陷阱、执行步骤）；这份只讲怎么跑。

和 `../HANDOFF.md`（agent harness 黑盒对比）共用模型和仓库，实验方法完全不同。

状态（2026-08-25，四个对照跑完）：Tier A 整条梯队跑完了（1.7B，runs `20260822-031238` /
`20260822-175713`，两次数字一致——贪心解码）。Tier B **v1 已经下线**：它的 e0 两对
都没过门槛，而且是贴着地板没过（8B，run `20260822-181445`），根因是无 CoT 设定下
模型要在一次前向里做三位有效数字的算术，见 HANDOFF §15。**Tier B v2（选装置，
`tasks/tier_b2/`，116 题，无算术）也跑过首跑了**（run `20260822-195002`）：

- 两对 e0 **仍然没过门槛**，但这次卡在**另一端**——无 skill 基线 0.819，余量只有
  18.1pp，准确率那一档（Δ≥15pp）在这个基线上根本够不着。**v1 死在地板，v2 死在
  天花板。**
- 常数那份差 **0.008**（logprob CI 下界 −0.008）没过；方法那份是干净的零。
- §15.3 预注册的**双重分离不成立**：常数那份 12 题里 11 题落在自己的轴，方法那份
  5 题里 4 题落在**它按构造碰不到的**单位轴。
- e7 报两份内容互斥的 skill **方向余弦 0.97**、有效维数 1.0/116——但这一跑
  **没有中性对照**，所以它还分不开「skill 的签名」和「上下文里多了一份长文档」。

原始输出和逐条判断在 [`journal/2026-08-24-tierB-v2.md`](journal/2026-08-24-tierB-v2.md)，
结论在 HANDOFF §12.3i。

**2026-08-25 的四个对照改变了结论的形状**（run `20260825-112500` + 三次单跑，
原始输出在 [`journal/2026-08-25-controls.md`](journal/2026-08-25-controls.md)，
判断在 HANDOFF §12.3j）：

- **中性对照把 e7 的 0.97 打掉了。** `filler-neutral` 与两份 skill 的方向余弦
  +0.945 / +0.955，两份 skill 之间 +0.972 —— 一样高，而且 filler 的 ‖d‖/‖h‖ 最大。
  **e7 现在测的是「上下文里多了一份长文档」，不是「文档说了什么」。**
- **「Tier A 修好的 19 题 100% 来自检索错」是错的**：84% 来自 `echo`（模型原样抄
  题干数字）。**Tier A 那个 +36.2pp 的主体是 engagement，不是检索。** 同时
  `wrong_family` 从 2 涨到 14 —— skill 也让它更多地选错表。
- **离域负对照合格**（+4.3pp / logprob −0.175，CI 都含 0），但 mode 和题集都对不上
  v2，还回答不了上面那个问题。
- **E6 确认 H1**：swing +3.43，`follow_rate = nan` 是抽取坏了，不是 H5。
- **模型确认为 Qwen3-8B**（挂了两轮的那条）。

**下一步（顺序按 HANDOFF §16.7 改过，先剥「文档存在」效应）：**

0. **E2 带中性文档对照跑一遍** —— 既然 e7 分不开 skill 和 filler，E2 的恢复率很可能
   也分不开。**这条决定 E2 的所有历史数字还算不算数。** 代码已就位
   （`e2_patch.py --filler`，流水线三个 e2 阶段默认带上）：

   ```bash
   ./run-whitebox.sh --only e2-tierA --force     # 1.7B，分钟级，先在这里看
   ./run-whitebox.sh --only e7-tierB --force     # 顺带拿到三个余弦的 bootstrap CI
   ```

   e2 会打出 `内容余量 = real − filler`。**余量 < 0.15 就说明补丁送进去的是
   「上下文里有份长文档」，那个恢复率不能当 H1/H2 的证据用。**

**下面这几条是上一轮的清单，仍然有效：**

1. **重跑一次汇总。** `report.py` 现在会打出余量告警（并算出"要修好剩下错题的
   83%"）、门槛差在哪一档差多少、门槛感知的轴拆分。
   `python report.py results/20260822-195002`，几秒。
2. **查这一跑用的是哪个模型。** `results/20260822-195002/e0-tierB-const/run-info.json`。
   这条挂了两次了；基线 0.819 的解释直接依赖它。
3. **e7 带中性对照重跑。** `./run-whitebox.sh --only e7-tierB --force`——现在会把
   `tasks/filler-neutral.md` 当第三份文档一起跑。**眼下最便宜、信息量最大的一步**：
   它决定 0.97 是不是 skill 的签名。
4. **改生成器，把基线压到 0.4–0.7。** 更难混的常数变体、更贴近的关系式对。标定要在
   **另一批生成的题**上做，不能在这 116 道上按对错筛——那是按因变量选样本，v1 就是
   那么掉到地板的。
5. **Tier A 的两条旧账**（都不用 GPU）：`errors.py` 加了 `echo` 类别之后没重跑，
   「修好的 19 题 100% 来自检索错」要重看；`e6_diagnose.py` 没在
   `results/20260822-175713/e6-tierA` 上跑过（lp swing +3.43 指向"抽取坏了"，不是 H5）。

第 4 条现在有了具体设计：**Tier B v3，分步归因的程序型任务**（L=4 的链，每一步由
skill 的一段拥有，金标前缀 teacher-forcing 让每步重新成为独立的测量单元）。它同时
解掉基线标定和"每一步的 skill 是否 work"两件事。设计见 HANDOFF §16，两篇本地论文
的深读补充见 §9.2d。**动生成器之前先把上面第 3 条（e7 中性对照）跑完**——那个结果
会改变 v3 该怎么写。

---

## 目录

| 文件 | 作用 |
|---|---|
| `model.py` | **唯一碰权重的模块**。加载、hook、激活补丁、注意力敲除、打分 |
| `selftest.py` | 干预机制的自检。跑实验前必须全过 |
| `e0_effect.py` | Phase 0 效应筛查（第 3 步）。**行为层，无层间数据** |
| `e2_patch.py` | **E2 激活补丁层扫描 —— 恢复率 vs 层** |
| `e1_knockout.py` | **E1 注意力敲除层扫描 —— 依赖度 vs 层** |
| `e6_counterfactual.py` | **E6 反事实 skill —— 答案跟着改过的表走吗**（不用 hook）|
| `e7_repr.py` | **E7 表示层几何 —— 注入之后出现了什么 pattern**（最便宜的那个）|
| `run-whitebox.sh` | **流水线：按顺序跑完多个实验**，断点续跑、逐阶段日志 |
| `report.py` | 把一次 run 的所有 summary.json 汇总成一页 + **交叉校验** |
| `whitebox.conf.example` | 机器配置模板（复制成 `whitebox.conf`，不进 git）|
| `errors.py` | 错误类型学（第 4 步）。**纯后处理，不用 GPU** |
| `e6_diagnose.py` | E6 的 follow rate 无定义时读什么。**纯后处理，不用 GPU** |
| `journal/` | **每次实跑的原始输出和当时的判断**，一次一个文件 |
| `tasks/tier_a/render_skill.py` | 从换算表渲染 skill；E6 的反事实文档由它生成 |
| `tasks/filler-neutral.md` | E1 的对照文档（结构相似、任务无关） |
| `run-whitebox.sh` | 服务器端一键运行（体检 → 自检 → Tier A → Tier B） |
| `contamination.py` | skill 是否泄漏答案 |
| `setup-whitebox.sh` | 服务器端体检 + 可选安装 |
| `tasks/tier_a/` | 合成任务（正对照）：虚构 Zorb 单位制 |
| `tasks/tier_b/` | **v1，已下线**：SciBench 物理化学原题 + 两份知识型 skill |
| `tasks/tier_b2/` | **梯队 b 实际在跑的**：选装置，2×2 因子设计，无算术 |
| `results/<run-id>/` | 每次跑的产物 |

---

## 服务器上跑

```bash
cd /inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness/whitebox
../run-server.sh stop          # vLLM 按 gpu_memory_utilization 预留显存,先让开
./setup-whitebox.sh            # 只检查，不动环境
./setup-whitebox.sh --install --download
```

### 远程那台机器上：从零到出结果

这台是 Inspire 的 4090（48GB）容器。`/root` 每次重启都会被清空,持久目录是
`$BASE`,所以第一条命令永远是 `source env.sh`。

```bash
BASE=/inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness
source $BASE/env.sh                 # venv、HF 镜像、PATH 都在这里面

# 1. 同步代码。注意 git lfs pull —— reset --hard 不会更新 LFS 内容,
#    少了它 SciBench 的 parquet 是 131 字节的指针,Tier B 会莫名其妙地空
cd $BASE && git fetch && git reset --hard origin/master && git lfs pull

# 2. 让开显存。vLLM 按 gpu_memory_utilization 预留,不管用不用得上
$BASE/run-server.sh stop

# 3. 体检（只检查,一个包都不装）
cd $BASE/whitebox
./setup-whitebox.sh
#    缺依赖 / 缺小模型时再加参数,torch 无论如何不由它安装或升级：
#    ./setup-whitebox.sh --install --download

# 4. 配置（只做一次；这个文件不进 git）
cp whitebox.conf.example whitebox.conf
$EDITOR whitebox.conf               # 确认 WB_DEV_MODEL / WB_MAIN_MODEL 路径

# 5. 先 smoke 一遍：每阶段几题几层,一两分钟,数字没意义,看能不能跑通
./run-whitebox.sh --smoke --phase a

# 6. 真跑梯队 a（1.7B,十几分钟,可以在前台看）
./run-whitebox.sh --phase a

# 7. 梯队 b（8B,小时级）。容器里没有 tmux,所以 nohup
mkdir -p logs
nohup ./run-whitebox.sh --phase b > logs/wb-$(date +%m%d).log 2>&1 &
tail -f logs/wb-*.log

# 8. 汇总（随时可以再看一次,不用重跑）
python report.py results/<run-id>

# 9. 跑完把 vLLM 放回去（黑盒那批实验要用）
$BASE/run-server.sh start
```

几条这台机器上的具体注意事项：

- **不要往终端里粘贴多行内容**（heredoc 在这个终端里会被吃掉字符）。所有脚本和
  文档都在仓库里,用 `git` 同步,不要手工粘。
- **中断了不用从头开始**：`RUN_ID=<上次那个> ./run-whitebox.sh --phase a`,已经有
  `summary.json` 的阶段会跳过。run id 就是 `results/` 下的目录名。
- **显存不够时**先降 `WB_E1_LIMIT`,不要降 `WB_TIERB_GROUP`——分组只影响一次敲几层,
  不省显存。E1 的 prompt 同时含 skill 和等长填充文档,是全流程里最长的。
- **只想重跑某一个阶段**：`./run-whitebox.sh --only e2-tierA --force`（不带
  `--force` 会因为已有结果而跳过）。
- 梯队 a 用 1.7B,可以和 vLLM 共存;梯队 b 用 8B,一定要先 stop。

### 一条命令跑完一梯队

```bash
cp whitebox.conf.example whitebox.conf   # 改模型路径，一次就好
./run-whitebox.sh --list                 # 有哪些阶段、各自回答什么问题
./run-whitebox.sh --phase a              # 梯队 0+a：1.7B，十几分钟
nohup ./run-whitebox.sh --phase b > logs/wb.log 2>&1 &   # 梯队 b：8B，长跑
tail -f logs/wb.log
python report.py results/<run-id>        # 随时再看一次汇总
```

| 参数 | 作用 |
|---|---|
| `--list` | 列出阶段和每个阶段回答的问题，不跑任何东西 |
| `--phase a\|b\|all` | 按梯队跑（梯队 0 的门槛永远跑）|
| `--only NAME` / `--from NAME` / `--skip NAME` | 单跑 / 从某阶段起 / 排除某阶段 |
| `--dry-run` | 只打印会执行的命令 |
| `--force` | 忽略"已经跑过"，重跑 |
| `--smoke` | 每阶段几题几层，一两分钟跑通全流程（数字无意义，只验能不能跑）|
| `--no-gate` | 跳过 Phase 0 门槛检查（分母是在别的 run 里确认的时候用）|
| `RUN_ID=xxx` | 接着上次那个 run 继续（默认按时间戳新建）|

**断点续跑是默认行为**：某阶段的 `summary.json` 已经在了就跳过，所以中断之后重跑
同一个 `RUN_ID` 就行。服务器上没有 tmux，长跑用 `nohup`。

配置全在 `whitebox.conf`（模型路径、题数、层扫描粒度、K 值），环境变量优先，
`--config` 可以指定别的文件。这个文件**不进 git** —— 和 `env.sh` 同理，它是这台
机器的部署状态，不是源码。

阶段之间的门槛是硬的：自检不过直接退出；Tier B 的层间实验在对应的 Phase 0 门槛
没过时**跳过并说明原因**，因为恢复率的分母就是那个行为效应差值。

梯队怎么划分、每个阶段大概会得到什么结论，见 HANDOFF §13。

`setup-whitebox.sh` **默认一个包都不装**。这个 venv 同时供着 vLLM，而 vLLM 对
torch 版本很挑；一次顺手的 `pip install -U` 就可能把黑盒那批实验弄坏。torch 无论
如何都不由这个脚本安装或升级。

然后按顺序：

```bash
# 1. 自检 —— 全过才往下走
python selftest.py --model ../models/Qwen3-1.7B

# 2. Tier A 正对照 —— 这里没有大效应 = 流水线坏了，不是假设错了
python e0_effect.py --model ../models/Qwen3-1.7B \
  --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
  --mode mc --run-id tierA-dev

# 3. Tier B v2 效应筛查 —— 结论从这里出
python e0_effect.py --model ../models/Qwen3-8B \
  --tasks tasks/tier_b2/tasks.jsonl --skill tasks/tier_b/SKILL.pchem-constants.md \
  --mode mc --run-id tierB-const-8b

# 4. 双重分离的一半：这份 skill 修的是哪个轴（纯后处理，不用 GPU）
python errors.py --per-item results/tierB-const-8b/per_item.jsonl \
  --tasks tasks/tier_b2/tasks.jsonl --mode mc --label pchem-constants
```

**第 1 步不能跳。** 自检测的不是假设，是代码有没有做它声称的事。坏掉的干预照样
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

### Tier B v2：选装置（116 题，梯队 b 实际在跑的）

> **v1（SciBench 原题 + 填空）已经下线，代码和题池还在 `tasks/tier_b/`。**
> 它测不出东西，原因不是题太多步——很多是一步——而是这个设计
> `enable_thinking=False` + 24 token + 「只给最终数字」，模型得在一次前向里把
> `25000 / 373.15` 算到三位有效数字。8B 无 skill 0.067，地板上没有余量，
> skill 再有用也涨不动。详见 HANDOFF §15。
>
> v2 把**算术拿掉，化学留下**：给一个场景和四个候选装置，选哪个是对的，
> 不用算。题目由 `tasks/tier_b2/build.py` 生成，`--check` 能逐字节复现。

**四个选项是一个 2×2 因子设计**，这是这份题集存在的理由：

|  | 常数对 | 常数错 |
|---|---|---|
| **关系式对** | `correct` | `wrong_const` |
| **关系式错** | `wrong_rel` | `wrong_both` |

两个轴分别由两份 skill 拥有，而且**互不覆盖**：

- `SKILL.pchem-constants` 只有数值 → 只能修 `wrong_const`（单位轴）
- `SKILL.pchem-procedure` 只有方法 → 只能修 `wrong_rel`（关系式轴）

所以预注册的预测是**双重分离**，不是一个准确率差值。`errors.py` 逐题给出是哪个轴，
`report.py` 把两份 skill 的结果并起来判定。一份 skill 同时动两个轴，
example/principle 这条线就当场被证伪了——而那正是 E2 整个预测赖以成立的东西。

> **首跑（run `20260822-195002`）没有成立。** 常数那份修好的 12 题里 11 题落在
> 自己的轴，方法那份修好的 5 题里 4 题落在**它按构造碰不到的**单位轴，而且两对
> e0 都没过门槛（基线 0.819，余量 18.1pp）。所以现在能说的是「一份有未确认的效应
> 且落在自己的轴上，另一份没有效应」，**不能**说分离、也**不能**说证伪——在没过
> 门槛的效应上拆轴，拆的是没被确认的东西。见 HANDOFF §12.3i。

题目长这样：

> 1.78 mol of nitrogen expands isothermally and reversibly from 9.55 dm^3 to
> 16.07 dm^3 at 37 degC. The work done is required in joules.
>
> Which setup is correct? Do not carry out the calculation.
> A. reversible isothermal work, using R = 82.06 cm^3 atm K^-1 mol^-1
> B. reversible isothermal work, using R = 8.314 J K^-1 mol^-1   ← 对
> C. perfect gas law, using R = 82.06 cm^3 atm K^-1 mol^-1
> D. perfect gas law, using R = 8.314 J K^-1 mol^-1

干扰项永远不是随机的：每一个都是正确装置**只翻一个轴**得到的，所以模型选了哪个字母，
就说明它犯的是哪一类错。错的关系式只从**易混对**里取（气体定律 ↔ van der Waals，
cell potential ↔ Nernst），不会给一个不读文档也能排除的选项。

**效度必须照实说。** v1 的题是外部的、公开的（SciBench 原题，一字未改）；v2 不是，
场景和选项都是这里生成的，关系式和常数直接抄自两份 skill，所以**按构造就能被它们解出来**
——和 Tier A 一样，理由也一样。这让 v2 成了**第二个正对照**，surface 词汇更真实而已，
**不是**「skill 在真实世界里有多大用」的证据。不要从这份题集引用效应量。

金标字母在 A/B/C/D 上**严格等分**（116 = 4 × 29），所以一个只会选 C 的模型正好得 0.25。

#### 两份 skill 的内容互斥（E2 预注册预测的前提）

#### `SKILL.pchem-constants` —— 只有数值，没有方法

v2 里它负责**单位轴**。以上面那道 work 题为例，模型要挑对 R 的哪一版：答案要焦耳，
所以是 `R = 8.314 J K⁻¹ mol⁻¹`，不是 `82.06 cm³ atm K⁻¹ mol⁻¹`。

模型多半"知道" R，但**知道的是哪一版**才是关键。这份 skill 给的是**具体数值**，
预期走 H1（检索）。

> v1 的同一件事需要先算出来才看得见：
> `10.0 mol C₂H₆ 关在 4.860 dm³、27 °C，求压强 → 50.7 atm`，
> 挑错 R 那一版答案就差一个常数因子。v2 把「挑」和「算」拆开，只保留前者。

#### `SKILL.pchem-procedure` —— 只有方法，没有一个数值

v2 里它负责**关系式轴**。它提供的是 Step 1 那张表：给了 p、V、n、T 中的三个求第四个
→ 理想气体定律；real gas、中等压强 → van der Waals；非标准浓度 → Nernst。

**它里面一个常数都没有。** 所以它要是有效，效果只能来自**选对关系式**，
不可能来自提供数值。预期走 H2（选择）。

v2 只覆盖它的 Step 1。Step 2–4（符号约定、电子数、报告前自检）没有常数轴，
塞不进 2×2；双重分离要是成立了，符号那一版是下一个该做的题集。

#### 这个对照就是 E2 的判决

| skill | 抽象层级 | 预测（跑之前写死） |
|---|---|---|
| `pchem-constants` | 偏 `example` | 行为上只动**单位轴**；激活补丁**压不进**单个向量 |
| `pchem-procedure` | 偏 `principle` | 行为上只动**关系式轴**；激活补丁**压得进** |

第一列（行为层的双重分离）**不需要 GPU 层扫描**：`e0` + `errors.py` 就能判。
它先跑，因为它要是不成立，第二列在解释什么就已经不清楚了。

抽象层级的三分来自 SAPO（见 HANDOFF §9.2）。预测写在跑之前，跑完直接对照，避免
在多重比较里挑显著的讲故事。

#### 单位必须写进 prompt（v1 的遗留约束）

SciBench 有些题把比例因子放在单位字段里（答案 `1.602`，单位 `10⁻¹⁷ J`）。不声明
单位的话模型答 `1.602e-17`，scorer 判错，测到的就成了约定不一致而不是化学。
`model.py:build_messages` 会把单位加进用户轮。

v2 用不到这条——它的答案是字母——但 `build_messages` 的行为没变，v1 的题池还在，
拿它跑对照时这条仍然适用。

---

## E2：第一个层间实验

`e0_effect.py` 全是行为层测量，不产生任何层间数据。**`e2_patch.py` 才是。**

```bash
# 先在 Tier A 上跑 —— 正对照，效应必然大，用来确认曲线可读
python e2_patch.py --model ../models/Qwen3-1.7B \
  --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
  --mode mc --limit 40 --run-id e2-tierA

# Tier B v2 —— 和 e0 用同一批题。两份 skill 必须落在同一个题池上，
# 否则两条恢复率曲线不可比（这也是 v2 不再做 --filter-known 的原因之一）
python e2_patch.py --model ../models/Qwen3-8B \
  --tasks tasks/tier_b2/tasks.jsonl \
  --skill tasks/tier_b/SKILL.pchem-procedure.md \
  --mode mc --limit 60 --layer-step 2 --run-id e2-tierB-proc
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

### 补一个位置还是补 K 个

`--tail-k`（默认 1）。低恢复率有两种读法：效应压不进向量（H1），或者**一个位置装
不下**——单位置是脚本选的容量上限，不是模型选的。所以 K=1 报出低恢复时，脚本会提示
用 `--tail-k 4` 再跑一次：多位置也压不进，H1 才立得住。

两份 prompt 长度不同，所以 K 个位置**从末尾对齐**（问题和 chat 后缀在那里对得上，
skill 段落在哪儿都对不上）。`selftest` 第 4b 项守着行和位置的绑定：用自己的值补 K
个位置必须是空操作，而把这 K 行**倒过来**必须改变输出——只测空操作的话，任何对称的
错位都能蒙混过去。

### 一个实现上的关键点

补丁必须落在**最后一个 prompt token**，不是序列最后一个 token。打分时 prompt 和
答案是拼在一起做一次前向的，所以位置用的是 `prompt_len - 1` 的绝对下标；用 `-1`
会补到答案内部，测的就完全是另一回事了。

---

## E7：表示层几何 —— 最便宜的那个

```bash
python e7_repr.py --selftest                     # 指标自检，不用 GPU，几秒
python e7_repr.py --model ../models/Qwen3-1.7B   --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md   --mode mc --probe family --run-id e7-tierA
```

不干预，只看有 skill / 无 skill 两次前向在 prompt 最后一个 token 上的差
`d = h_有 − h_无`，逐层算四个量：

| 量 | 高说明什么 |
|---|---|
| `‖d‖/‖h‖` | 那一层被推得最狠（平坦 = 只是"多了段文本"的普遍扰动）|
| 各题 d 的平均余弦 | **一个共享方向** —— "有 skill 在"是个状态，不是内容 |
| participation ratio | 有效维数；≈1 是单轴，≈题数是没有结构 |
| 两份 skill 的平均方向夹角 | 注入有没有**通用签名**，与是哪份 skill 无关 |

每题两次前向，没有 hook，没有层扫描——1.7B 上几十秒。它直接回答"内部表示有没有
pattern"，而不是从干预结果反推。

**`--skill` 可以给多次，而且必须给一份不是 skill 的。** 两份 skill 走同一个方向
（首跑余弦 0.97）只有在**一份等长的中性文档走不出这个方向**时才是关于 skill 的
结论；否则测到的是"上下文里多了一份长文档"。`run-whitebox.sh` 的两个 e7 阶段现在
都把 `tasks/filler-neutral.md` 当第三份文档一起跑，`report.py` 缺它时会点名要。

**它和 E2 可以互相矛盾**：E2 的 `mean` 条件如果恢复得和 `real` 一样好，E7 的平均
余弦就必须高。`report.py` 会把这条矛盾直接打出来。

`--probe family` 另问一件事：任务需要的那个变量（该查哪张表）在表示里线性可读吗，
skill 有没有让它更早可读。**读这条要小心**：47 题、2048 维，不正则的探针能分开
任何标签。脚本先降维、交叉验证、并打印**打乱标签的基线**；真值不明显高于打乱值时，
那不是结论，是容量。

---

## E6：反事实 skill —— 不用 hook 的那个实验

```bash
python e6_counterfactual.py --model unused --dry-run     # 不用 GPU，先看能用几题
python e6_counterfactual.py --model ../models/Qwen3-1.7B --run-id e6-tierA
python e6_counterfactual.py --model ../models/Qwen3-1.7B --flavour near --run-id e6-tierA-near
```

把 skill 里的一个换算因子改掉（`glorn 7 → 42`），题目不动，看答案跟谁走：跟改过的
值 = 模型真的在读那张表（H1）；跟原值 = 它没在读；两个都不是 = 冲突把计算打乱了
（H5）。

**为什么值得单独跑**：E1 和 E2 都依赖 hook，而 hook 会静默失效（§12.3d 就是一次）。
E6 只用普通前向，所以它能**证伪** E1/E2：E6 说模型在逐行读表、E1 却报"没有哪一层
依赖 skill"，那是 E1 坏了。它还给出**逐题标签**，可以用来切分 E1/E2 的曲线，而不是
只比较平均值。

反事实文档是**渲染**出来的，不是手改的：`tasks/tier_a/render_skill.py` 从换算表
重建整份 skill，worked examples 里的数跟着一起变，所以两份文档只差那个因子。
`render_skill.py --check` 会先验证"用未扰动的表渲染 = 仓库里那份 skill，逐字节
相同"，不通过就拒绝往下跑——这条是"只差一个因子"能当事实用的前提。

`--flavour near` 把因子改成**最小的相容改动**，`far` 改成表允许的最远值。
SWE-Skills-Bench 里真正有害的 skill 都是"近似匹配"的（HANDOFF §9.2b），
如果 near 比 far 更能锚住模型，那就是在可控条件下复现了他们的机制。

---

## 错误类型学（第 4 步）：skill 消掉的是哪一类错

```bash
python errors.py --per-item results/tierA-dev/per_item.jsonl   --tasks tasks/tier_a/tasks.jsonl
```

**不用 GPU，不用模型**——它只读 `e0_effect.py` 的产物。Tier A 的每个干扰项都对应
一种具体的读错方式，所以答错本身就说明错在哪：

| 类别 | 含义 | 指向 |
|---|---|---|
| `unparsed` | 输出里根本没有答案 | H3 格式 |
| `wrong_row` | 找对了表、取错了行 | H1 检索 |
| `wrong_family` | 读了错的那张表 | H2 选择 |
| `inverted` | 该乘的除了 | H2 选择 |

配对设计让"哪一类错被修好了"是精确的：逐题跟踪它从无 skill 的类别搬到了有 skill 的
哪一类。Tier B 走另一套（数值残差：`const_version` 比值 101.325、`unit_prefix`
比值 1000、`kelvin` 差 273.15 …），因为"答案差一个常数因子"不是推理错，是拿错了
常数的版本。

**这一步该在层扫描之前跑**：它不花算力，却能告诉你四个假设的大致份额。如果修好的
题里八成是 `unparsed`，那主线是 H3，激活补丁扫层是在解释别的东西。

---

## E1：注意力敲除层扫描

```bash
python e1_knockout.py --model ../models/Qwen3-1.7B \
  --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
  --mode mc --limit 40 --run-id e1-tierA

# 8B 先粗扫（每 4 层一组），定位到热点再用 --group 1 细扫那一段
python e1_knockout.py --model ../models/Qwen3-8B \
  --tasks tasks/tier_b2/tasks.jsonl \
  --skill tasks/tier_b/SKILL.pchem-constants.md \
  --mode mc --limit 60 --group 4 --run-id e1-tierB-const
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

两个条件下模型看到的内容完全一样，唯一差别是挡住了哪一段。单报 `effect` 等于把
"挡住任意同长度片段都会造成的损伤"算到 skill 头上。

**挡住的是 skill 的全文**，不是它的开头。这一点写在这里是因为它曾经不是：早先的
版本定位 `skill_body[:400]` 的 span，而这个仓库里每份 skill 的前 400 字符都是
YAML frontmatter —— 挡住的是 skill 的**描述**，换算表、常数、决策流程一个都没挡到。
那个版本只可能报出"没有哪一层依赖 skill"，而且看起来像个发现。`selftest` 第 6b 项
现在守着这条：全文 span 必须一直延伸到文档结尾。

**对照按 skill 的 token 数从填充文档开头取同样长的一段**，所以填充文档必须是更长的
那一份（现在约 1.8 倍）。反过来（把 skill 截短去迁就填充文档）会重新掉进上面那个
坑，所以脚本直接报错退出，不会悄悄缩短。

**两份文档的先后顺序按题目奇偶交替**（`--order alternate`，默认）。挡住靠前的一段
和挡住靠后的一段本来就不是同一种扰动，顺序固定的话"位置"和"内容"是混在一起的。
峰值那一组会分别报出两种顺序下的 net，**符号不一致直接警告**——那说明测到的是位置。

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
