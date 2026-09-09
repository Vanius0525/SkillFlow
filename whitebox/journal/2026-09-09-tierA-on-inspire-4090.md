# 2026-09-09 — Tier A 整跑移到启智 4090，E10 首跑，三条挂着的账一次结清

run id `20260909-130000`，Qwen3-1.7B，**float32**，39 题，逐层 0..27。
机器换了：旧的 `skillflow-ubuntu`（4090 48GB）连不上之后，这一跑在**启智
`可上网GPU资源` / `4090-cuda12.8-2` / notebook `wt-gpu-wb`** 上做。
`nvidia-smi` 报 **`NVIDIA GeForce RTX 4090, 49140 MiB`** —— 和 HANDOFF §0.1 记的
那台旧机器**逐 MiB 一致**，所以这不是换硬件，是换了同型号的另一台。

## 0. 命令

```bash
# 机器配置（whitebox.conf，不进 git）：模型和 venv 都在共享盘 ssd 那一层，
# 因为 hdd 的个人配额已经满了（详见全局 CLAUDE.md）
BASE=/inspire/ssd/project/project-public/czxs253130660/agent-harness/whitebox
cd $BASE
RUN_ID=20260909-130000 ./run-whitebox.sh --phase a          # e7 这一阶段当时失败
RUN_ID=20260909-130000 ./run-whitebox.sh --only e7-tierA --force   # 修好之后补
python e2_acc.py results/20260909-130000/e2-tierA results/20260909-130000/e2-tierA-k4
```

阶段耗时：`selftest` 18s、`e0-tierA` 56s、`e0-tierA-filler` 69s、`e6` 41+37s、
`e2-tierA` 151s、`e2-tierA-k4` 174s、**`e10-tierA` 258s**、`e1-tierA` 349s、
`e7-tierA` 936s。整条（含补跑 e7）约 35 分钟。

## 1. 先说环境：21 项自检全过，这是第一次在 GPU 上跑

HANDOFF §12.4 一直挂着「所有和 GPU 相关的东西都没验证过」，并按可能性排了三处
最可能失败的地方。**三处全过**：

```
5. attention knockout
  [  OK  ] blocked span receives ~no attention  -- max attention into blocked span = 0
  [  OK  ] knockout changes the output  -- max |dlogit| = 21.02
5b. per-layer attention knockout
  [  OK  ] per-layer hook fired
  [  OK  ] single-layer knockout changes output  -- max |dlogit| = 1.524
  [  OK  ] single-layer effect is smaller than all-layer  -- one-layer 1.52 vs all-layer 21
...
  passed 21, failed 0
```

transformers 是 **4.57.6**（钉在 `<5`：代码按 `>=4.51` 写的，而 5.x 改了 attn 的
调用面，§12.4 第 1 条点名的正是这个签名）。显存没到上限。

**`e0-tierA` 的四个数逐位复现旧机器**：`acc_no_skill` 0.2308（§12.3o: 0.231）、
`delta_acc_pp` **+20.51**（§12.3o: +20.5）、`n` 39、`mcnemar_gained` **13**
（§12.3x「skill 修好的 13 题」）。贪心解码，所以这是等价性证明，不是巧合。

## 2. `--probe answer` 从来没跑起来过：argparse 漏了一个选项

`run-whitebox.sh` 自 §12.3x 起就传 `--probe answer`，`e7_repr.py` 的函数体也早就
把它映到 `answer_mc` 字段，**只有 argparse 的 `choices` 还写着 `["none","family"]`**。
于是这个阶段 7 秒就死：

```
e7_repr.py: error: argument --probe: invalid choice: 'answer' (choose from 'none', 'family')
```

没人撞见过，因为上一次真跑早于这个切换，而 §12.3y 的静态审查覆盖的是
`e10_span.py` / `e2_patch.py` / `tierb.sh`，不含这个 flag。修在 `301a207`。

**教训可复用**：写了一个脚本把 `run-whitebox.sh` / `tierb.sh` 里传的每个 flag 和
每个脚本的 `add_argument` 对了一遍（含 `choices` 的取值），修完无其它不匹配。
这类「文档说改了、代码只改了一半」的账，跑之前能静态查出来。

## 3. E10 首跑：内容在原位能被读到层 10，层 11 断崖

`e10_span.py`，span 688 token，接收方 = 把 skill 正文换成等长 filler token
的 prompt（长度相同、span 外逐 token 相同、RoPE 相位对齐）。

```
  span=688 tok   filler-receiver acc_lo=0.154   real-skill acc_hi=0.436
  ceiling (all 28 layers at once): acc=0.385  recovery=1.505

  layer   recovery   acc_real   acc_self
     0      +1.505     0.385     0.154
     1      +1.516     0.385     0.154
     2      +0.763     0.333     0.154
     3      +0.159     0.436     0.154
     4      -0.123     0.436     0.154
     5      -0.173     0.333     0.154
     6      -0.408     0.308     0.154
     7      -0.617     0.359     0.154
     8      -0.891     0.359     0.154
     9      -1.169     0.333     0.154
    10      -1.163     0.308     0.154
    11      +0.056     0.128     0.154     <-- 断崖
    12      -0.100     0.179     0.154
    ...（13..27 都在 0.128-0.205，基线 0.154 附近或以下）
    27      -0.000     0.154     0.154
```

三条预注册**全部命中**：

1. **`self` 逐层精确空操作** —— `acc_self` 每层都是 0.154，`self_max_dev_nats = 0.0`，
   `donor_item_drift = 0.0`。通路自证这次是端到端成立的（对比 §12.3p/q 追了两轮的
   那个末层对不上）。
2. **早高晚低** —— 层 0..10 的 `acc_real` 在 0.308–0.436 之间，层 3–4 **等于真 skill
   的天花板 0.436**；层 11 起掉到基线以下。
3. **末几层 ~0**（内建负对照）—— 层 21..27 的 recovery 在 ±0.06 内。

**判断**：「最后一层还能在原位读到文档」是**层 10**。这是 E1 想回答而功效不够的
那个问题，改成正面提供内容之后一次就读出来了。

**天花板条件（28 层一起换）给 0.385，低于单层最好的 0.436。** 这不是 bug：
它说明移植不是「越多越好」，一次换一层就够，全换反而引入了层间不一致。
（`ceiling_n_layers: 28` 已按 §12.3y 的修法走 `all_layers`，不是抽稀。）

**当时不确定的**：层 0–1 的移植几乎等于把 token 本身放回去（层 0 就是 embedding），
所以那两层的 0.385 不是「读到了」的证据，只是「内容在那里」。真正有信息量的是
**层 3–10 这一段**：此时残差已经过了若干层计算，却仍然能被下游读出来用对。
层 2 掉到 0.333、层 3–4 回到 0.436 这个非单调，n=39 下可能只是噪声。

## 4. E2：`mean`/`mismatched` 的 logprob 比 real 高，答案是「off-manifold 抬升」

§12.3w 埋下、§12.3y 接上读数的两个预注册判据，这一跑第一次有数据。

聚合 recovery（logprob）那一列，层 21–27：

```
  layer       real mismatch mean vec   filler
     21       1.47    -3.25     5.43     2.78
     22       0.95    -4.05     4.71     3.37
     ...
     27       1.00    -4.32     6.41     3.03
```

`mean` 和 `filler` 都比 `real` 高。**但准确率是反的**（层 21）：real 0.436、
mean 0.282、filler 0.205、mismatch 0.205。

mass / margin 分解给出机制（`mass` = log P(下一个 token 是某个选项字母)，
`margin` = lp(gold) − max(其余三个)）：

```
  --- layer 19（准确率峰值，落在打坏区间里）
  condition      n      mass    d mass    margin  d margin      acc
  no doc        39    -0.000    +0.000    -5.966    +0.000    0.231
  with skill    39    -0.019    -0.019    -2.491    +3.475    0.436
  real          39    -0.000    -0.000    -2.740    +3.226    0.462
  mismatch      39    -0.000    -0.000    -4.336    +1.630    0.385
  mean vec      39    -0.000    -0.000    -7.231    -1.265    0.231
  filler        39    -0.077    -0.077    -4.172    +1.794    0.256

  --- layer 21（预先定死的层）
  real          39    -0.038    -0.038    -2.345    +3.621    0.436
  mismatch      39    -0.054    -0.054    -7.350    -1.384    0.205
  mean vec      39    -0.000    -0.000    -2.817    +3.149    0.282
  filler        39    -0.188    -0.188    -3.981    +1.986    0.205
```

**判断**：
- **层 19 上 `mean` 的 margin 是 −1.265**，即它在「选」，而且**选反了**。
  配合它 +5.4 的 recovery：它把 gold token 的概率抬上去了，却没让 gold 变成 argmax。
  `e2_acc.py` 自己的判词就是这个：*"It lifts the gold token's probability without
  making it the argmax, which is what an off-manifold direction does."*
  **所以「mean 比 real 高」是真实存在且可解释的，不是偶然：聚合 gold logprob 在
  这里不是行为的代理量。**
- **层 21 上 `mean` 的 margin 变成 +3.149（文档的 91%），准确率却只有 0.282。**
  这一层它确实在「选」，方向也对，但力度不足以让 argmax 过线。所以 mean 的异常
  **不是一个恒定现象，而是分层的**：层 19 选反、层 21 选对但不够。
- `mismatch` 在层 21 的 margin 是 **−1.384**，正是 §12.3y 预测的 mismatched 形状
  （「纯扰动会把 margin 压平而不是压负」）。

## 5. 最直接的内容证据：别题向量把**供体那道题的答案**写了进来

```
  --- does the mismatched vector carry the donor's answer?   (layer 19)
        argmax == DONOR's gold    11/39  = 0.282   p=0.380 against 0.25
        argmax == its OWN gold    15/39  = 0.385
      At chance.

  --- does the mismatched vector carry the donor's answer?   (layer 21)
        argmax == DONOR's gold    16/39  = 0.410   p=0.020 against 0.25
        argmax == its OWN gold     8/39  = 0.205
      Above chance.
```

**层 21 上 p=0.020**。这是整个研究里**关于内容最正面的一条证据**：尾部那个向量里
装着供体那道题的答案，而不只是「有份文档在」这个状态。层 19 上是随机 —— 又一次
说明打坏区间里读不出东西。

配套的分组表（层 21，`fixed` = skill 修好的 13 题）：

```
  group                    n     real mismatch mean vec   filler     lp real
  fixed (wrong -> right)  13    0.923    0.308    0.231    0.000      +10.31
  never (wrong -> wrong)  17    0.059    0.118    0.294    0.118       -1.81
  kept (right -> right)    4    1.000    0.250    0.500    0.750       -0.01
  broken (right -> wrong)   5    0.000    0.200    0.200    0.600      -12.70

  among the 30 items wrong without a document:
                     skill right   skill wrong
      patch right         12             1
      patch wrong          1            16
      92% of what the patch fixes is also fixed by the document.
```

**real 在层 21 上几乎是逐题精确的**：修好 12/13、保住 4/4、没打坏任何一道、
`never` 组只动 1/17。`filler` 修 **0/13** —— 和 §12.3t 一致。
§12.3s 那条已撤回的「别题向量恢复 75%」在**层 19 上复现了**（mismatch 0.615 /
real 0.615），在层 21 上是 0.308。**撤回成立，而且现在有了两层并排的证据。**

## 6. E7：层 27 的峰值确实是分母造成的，真正的峰在 21–22

§12.3x 第 3 条要判的事。`delta_norm` 和 `base_norm` 现在分开存了：

```
  L   |d|_zorb  |h|_zorb  rel_zorb   |  |d|_fill  |h|_fill  rel_fill   | cos_zorb  PR_zorb
   0      2.37     13.93    0.1698   |      2.70     13.93    0.1939   |    0.999     1.00
   8     26.47     57.78    0.4581   |     27.84     57.78    0.4818   |    0.998     1.00
  16    106.75    244.96    0.4358   |    111.58    244.96    0.4555   |    0.965     1.07
  18    223.19    406.76    0.5487   |    186.20    406.76    0.4578   |    0.866     1.31
  21    451.36    775.92    0.5817   |    363.30    775.92    0.4682   |    0.806     1.51
  22    528.02    904.19    0.5840   |    437.18    904.19    0.4835   |    0.800     1.53
  26    840.73   2315.50    0.3631   |    682.87   2315.50    0.2949   |    0.743     1.74
  27    940.47   1183.51    0.7946   |    720.43   1183.51    0.6087   |    0.731     1.79
```

**`|h|` 单调爬到层 26 的 2315.5，然后在层 27 塌到 1183.5（减半）**，而 `|d|` 只从
840.7 平滑升到 940.5（+12%）。所以 `rel_norm` 从 0.363 跳到 0.795 **全部来自分母**。
→ **「峰值层 27 / 0.795」不能进论文。** 排掉伪影后真正的峰是 **层 21–22 的 0.58**，
和 E2 的效应层重合。

顺带两条新的：

- **`|d|_skill` 只从层 18 起才超过 `|d|_filler`**（223 vs 186；层 16 还是 filler 更大
  111.6 vs 106.8）。所以「注入的位移」在层 16 之前对真 skill 和中性文档**是同一个东西**。
- **`cos` 0.999 → 0.731、`PR` 1.00 → 1.79**：早层所有题共用一个方向（纯粹是
  「有份文档在」这个状态），层 18 之后才开始按题分开。

`cross_skill_cosine_ci`（§12.3x 第 4 条，「从来没查过」）：
**point 0.9475，CI95 [0.9469, 0.9479]，层 4**。区间极窄，所以论文里
"as close as they are to each other" 这句**可以写**。

## 7. `--probe answer` 是个零，但大概率是功效不足

```
  linear probe: which option is correct
    no_skill           best 0.30 at layer 8  (permuted 0.39)
    zorb-units         best 0.34 at layer 4  (permuted 0.23)
    filler-neutral     best 0.26 at layer 14 (permuted 0.30)
```

四选一的随机水平是 0.25，三条都贴着它，而 `permuted` 基线在 0.23–0.39 之间乱跳
—— **噪声地板比信号宽**。n=39、4 类、5 折交叉验证 = 每折约 8 道测试题。
**这条读不出东西，应当报成「功效不足」，不是「答案不可线性解码」。**
§12.3u 第 2 条期望的余量确实存在（no-skill 0.231 vs 随机 0.25），但余量不等于功效。

## 8. 这一跑留下的待办

1. **E10 的层 3–10 那一段需要更大的 n。** 0.436 / 0.333 / 0.308 / 0.359 的非单调
   在 39 题上分不开。这是目前最值得加题的地方 —— 它是唯一一条直接读出
   「内容在第几层还在原位」的通道。
2. **层 10→11 的断崖要和 E2 的层 21 对上。** 现在的图像是：内容在原位可读到 10，
   到 21 已经被摘要进最后一个位置。**层 11–20 这一段谁也没覆盖**，而打坏区间
   （17–20）恰好在里面。
3. **`mean` 向量在层 19 选反、层 21 选对但不够** —— 这个分层行为本身需要解释，
   它可能就是「打坏区间」的另一种表现。
4. 论文里三处要改：峰值层 27 的那一列删掉（第 6 节）、`--probe answer` 报成功效
   不足而不是零（第 7 节）、层 21 的 p=0.020 供体证据是新的正面证据（第 5 节）。
