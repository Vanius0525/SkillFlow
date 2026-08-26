# 2026-08-25 — Tier A 整条梯队 + e7-tierB（run `20260825-123259`）

```bash
./run-whitebox.sh --phase a
RUN_ID=20260825-123259 ./run-whitebox.sh --only e7-tierB --force
```

12 个阶段全过，15 分钟（1.7B）+ 96 秒（8B）。

**这一跑用的是旧代码。** 当天推上去的 `--filler` / `--boot` / errors 分层 / `--control`
四处改动**一个都没生效**——远程漏了 `git reset --hard origin/master`。三条独立证据：

- `e2-tierA` 的 banner 没有 `filler :` 那一行（新代码无论给不给 `--filler` 都会打一行），
  逐层也只有 `real / mismatched / mean` 三列；
- 两个 e7 都没有 `cross-document cosine at layer N ... bootstrap draws` 那段；
- `errors-tierA` 没有 `split by whether the model even attempted the task`，
  `report.py` 也没打 `分层：`，连「**没有中性文档对照**」那句警告都没有——
  而旧 e2 结果喂进新 `report.py` 必然触发它。

**但它给出了一个不依赖 filler 的决定性结果**（§2.1），所以照常记录。

---

## 1. 原样贴的关键输出

### 1.1 e2-tierA：超额恢复，平均向量比真向量还好

```
[1/2] baselines + cache
  mean logprob delta (with - without skill): +5.0269

[2/2] layer sweep   （只贴转折点之后）
    layer  17  real +0.487  mismatched -0.029  mean +0.212
    layer  19  real +0.697  mismatched +0.422  mean +0.936
    layer  21  real +1.058  mismatched +0.246  mean +1.617
    layer  24  real +1.072  mismatched +0.228  mean +1.578
    layer  26  real +1.029  mismatched +0.177  mean +1.904
    layer  27  real +1.428  mismatched +0.825  mean +2.011

  best layer 24 (final 2 excluded): recovery +1.072 CI95 [+1.012, +1.223]
    mismatched control at that layer: +0.228
    mean-vector       at that layer: +1.578

  [!] mismatched also recovers > 0.4 at layers [19, 20].

  [!] The patch OVER-recovers: real +1.072, mean +1.578 (1.0 = the whole effect).
```

`e2-tierA-k4`（补 4 个位置）几乎逐行一样：best layer 21，real +1.086
CI95 [+0.996,+1.304]，mismatched +0.289，mean **+1.653**。
**K=1 和 K=4 没有差别**，所以「一个位置装不下」这条备择解释在 Tier A 上排除掉了。

### 1.2 errors-tierA（旧版，没有分层）

```
  without skill  correct 4(8.5%)  echo 37(78.7%)  wrong_row 3  wrong_family 2  inverted 1
  with skill     correct 21(44.7%) echo 5(10.6%)  wrong_row 6  wrong_family 14 inverted 1
  became correct: 19   from echo 16   from wrong_row 3
  became wrong:    2   into wrong_family 2
```

和 2026-08-25-controls.md 那次逐字节相同（贪心解码）。

### 1.3 e0-tierA 两个模式

```
mc    n=47  0.085 -> 0.447  (+36.2pp, CI95 [+21.3,+53.2])
            logprob -12.673 -> -7.769  (+4.903, CI95 [+2.285,+7.580])  配对 +19/-2
            [!] Baseline 0.085 is below chance (0.250) with 100% parsed
                most common wrong answer: 'B' on 12/43 of the wrong items
num   n=47  0.000 -> 0.000  (+0.0pp)
            logprob -9.701 -> -10.746  (-1.045, CI95 [-2.280,+0.139])
```

### 1.4 e1-tierA

```
    layers   0-3    effect -5.126  control -1.415  net -3.711
    layers   4-7    effect -5.466  control -0.167  net -5.299
    layers   8-11   effect -5.965  control +1.045  net -7.010
    layers  12-15   effect -1.641  control -0.428  net -1.214
    layers  16-19   effect -1.648  control +0.153  net -1.800
    layers  20-23   effect -0.301  control -0.017  net -0.284
    layers  24-27   effect +0.139  control -0.013  net +0.152

  peak: layers 24-27  net +0.152 CI95 [+0.040, +0.273]
    by document order: skill-first +0.288, filler-first +0.015
```

### 1.5 e7-tierA（第一次带中性对照）

```
  zorb-units      峰值层 27  ||d||/||h|| 0.639  逐题余弦 +0.675  有效维数 2.1/47  PC1 31.2%
  filler-neutral  峰值层  6  ||d||/||h|| 0.500  逐题余弦 +0.997  有效维数 1.0/47  PC1 16.5%
  zorb-units vs filler-neutral   max +0.943 at layer 4

  linear probe: which conversion table does this item need
    no_skill        best 1.00 at layer 2   (permuted 0.24)
    zorb-units      best 1.00 at layer 14  (permuted 0.19)
    filler-neutral  best 1.00 at layer 17  (permuted 0.32)
```

### 1.6 e7-tierB

和 2026-08-25-controls.md 那次**逐字节相同**（0.523 / 0.519 / 0.549，
0.972 / 0.945 / 0.955）。贪心解码，两次跑一致——这是 §12.3g 记过的性质，又验证一次。

### 1.7 e6 两个口味

两个都是 `跟改过的值 0% / 跟原值 0% / 都不是 100%`，`follow rate = nan`。
lp 偏好：far 的 `cf` 条件 **+2.281**，near 的 **+2.086**；
但 `no_skill` 一列 far 是 **−0.784**、near 是 **+0.885** —— 两个口味在这一列上不同。

---

## 2. 判断，以及它依赖哪个数字

### 2.1 补丁做到的比文档本身还多，而且「无内容」的那一版做得最好

依赖三个数：`real +1.072`、`mean +1.578`、`mismatched +0.228`，分母 `+5.027`。

`1.0` 的定义是「补丁复现了文档的**全部**行为效应」。所以：

- **real 超过 1** —— 补丁比真放一份文档还有效；
- **mean 比 real 还高 47%** —— 而平均向量按构造**不含任何逐题内容**；
- mismatched 只有 +0.23 —— 排除「补哪儿都行」。

`errors-tierA` 给出了超过 1 的机制：**文档自己制造错误**，`wrong_family` 从 2 涨到
14，变坏的 2 题全进这一类。补丁把「有文档在」那个状态给了模型，**却没把 688 token
文档的干扰代价一起给**，所以它比真放文档更划算。

**这条结论不依赖 filler 条件**——mean 向量本身就是一个「无内容」对照，而且是比
filler 更强的那种（filler 至少还是一份真文本，mean 连文本都不是）。

合起来（配 e7-tierA 的 +0.943）：

> **Tier A 上的「skill 有用」= 一个通用状态 + 一份带副作用的文档。
> 补丁只给状态、不给副作用，所以恢复率 > 1。**

### 2.2 E1 不是「持续依赖」，是「几乎不依赖」

依赖 `net +0.152` 对 `e0 的 logprob 位移 +4.903`：**3.1%**。屏蔽掉整整 688 token 的
skill 全文，只损失效应的 3%。

`report.py` 当时把它判成「和 E2 互斥」，**那是只看了峰值位置（晚层）没看量级**。
按量级读，E1 和 E2 **不矛盾**：模型本来就没怎么读那份文本，所以它当然压得进一个向量。
这一跑之后 `report.py` 和 `fmt_e1` 都改成先除以行为效应再判（见 §12.3k 的代码表）。

顺带一条要单记的：**按文档顺序拆开是 skill-first +0.288 / filler-first +0.015，
差 19 倍。** 代码里现有的检查只看符号是否相反（没触发），量级差这么多同样说明
测到的有位置成分。

### 2.3 Tier A 作为「仪器灵敏度证明」基本站不住了

三个数一起看：`e0-tierA-num` 是 **0.000 → 0.000**（完全地板）；mc 基线 0.085
**低于随机 0.25**，且 100% 可解析、最常见错答是 'B'（12/43）；修好的 19 题里
16 题来自 echo。

所以 Tier A 的 +36.2pp = **「从被某个干扰项吸住 / 抄题干」变成「在四个选项里选对」**，
模型产出那个数的能力**是零**。§3 E2 里「Tier A 的高恢复率是仪器灵敏度证明」那句，
证明的是仪器能恢复**一个作答模式状态**——而那正是最容易压进单个向量的东西。
§12.3j-bis 已经写了要打折，这一跑把它坐实了。

### 2.4 探针饱和，读不出东西

`no_skill` 在**层 2** 就到 1.00（打乱 0.24）。「这题该查哪张表」不用 skill、
在第 2 层就线性可读——**任务变量在题干里是明写的**。所以三条探针曲线不能拿来比较
「skill 有没有让它更早可读」，这个 probe 在 Tier A 上没有区分力。

### 2.5 e7-tierA：skill 和 filler 在这里**不是**完全同形（和 Tier B 不同）

依赖 `逐题余弦 0.675 vs 0.997`、`有效维数 2.1 vs 1.0`、`峰值层 27 vs 6`。

Tier B 上三份文档四个量逐项同形；**Tier A 上不是**：zorb-units 的位移逐题差异更大
（余弦 0.675）、住在 2.1 维里，峰值层也差了 21 层。**所以 Tier A 的 skill 位移里
确实有 filler 没有的结构。**

但跨文档方向余弦仍然是 **+0.943**，也就是说：**共享的那个方向照样是通用的，
skill 特有的部分是叠在它上面的一小块。** 这正是 `--boot` 要去量的东西，
而这一跑没有它。

---

## 3. 预注册：下一跑之前先写下来

`--filler` 生效之后，e2-tierA 会多出 `内容余量 = real − filler`。基于 §2.1
（mean 已经超额恢复）和 e7-tierA 的 0.943：

> **预测：filler 捕获的向量也会恢复到 1.0 附近，内容余量 < 0.15。**

- 命中 → 是一个**被预注册命中的预测**，比事后解释强得多，
  §12.3j-bis「E2 的恢复率测的是文档存在」就此确认；
- **明显更低**（余量 ≥ 0.15）→ mean 向量的超额另有原因，
  「无内容对照」和「中性文档对照」测的不是同一件事，得重新想。

写在跑之前，是为了两种结果都已经有归属。

---

## 4. 还没查的

1. **`e0-tierA` 的 'B' 干扰项**：43 道错题里 12 道答 B，基线因此低于随机。
   `errors.py` 的 `wrong_family` / `wrong_row` 拆不出「为什么是 B」。
   如果 B 在生成器里有系统性位置（比如常是某个特定变换），那是题的问题。
2. **e1 的顺序效应 19 倍**（§2.2）。
3. **e6 两个口味的 `no_skill` 一列符号相反**（far −0.784 / near +0.885）。
   `no_skill` 条件下两个口味的**上下文是一样的**（都没有 skill），
   差别只在被比较的那两个值。所以这一列的差是**题目子集**造成的
   （far n=40，near n=31，筛掉的条件不同），不是条件效应——但没验过。
