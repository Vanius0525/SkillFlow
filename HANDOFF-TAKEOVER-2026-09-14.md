> ⚠ **本文件已过时（2026-09-16）**：里面描述的 4 个运行中作业早已跑完、10 台 GPU 实例已全部停机、论文数字已大量更正。
> **请改读 `HANDOFF-TAKEOVER-2026-09-16.md`。** 本文件仅作历史记录保留。

# 接管文档：SkillVector 论文（2026-09-14 14:55，写给新对话）

> 新对话请**先完整读本文件**，再按需查阅 `HANDOFF-whitebox.md` 的 §46（完整性检查）和 §47（今天逐小时的实验日志，数字最全）。
> 本文件是**当前状态的快照 + 可直接执行的命令**；§47 是过程记录。两者冲突时以本文件为准，并请把新进展追加到 §47。

---

## 0. 一段话讲清现状

论文 `paper/skillvector.tex`（ICLR 2027 投稿格式，正文 **9 页、零余量**，全文 47 页）的核心结论如下：

1. 最后一个 prompt 位置的补丁搬运的是**决策**，不是文档内容。
2. 文档作用经由**文档自己的 token span** 传递：早期层整段移植可完全复现文档效应，各类对照都在地板附近。
3. 单层交接在中层断掉，但注意力 knockout 显示模型到深层仍在读文档。
4. 截断注入对象的秩：拐点 k\* 约 50。

今天完成了三件事：
- 把所有能重跑的数字换成了 **mask 修复后**的数据；
- 补了**第二个任务领域（TheoremQA）**和**第二个模型家族（Mistral-7B）**；
- 修了一批数据、引用和写作上的错误。

**审计 `whitebox/analysis/audit.py` 178 条全部通过（ALL CHECKS PASSED）**，`paper/build.sh` 输出 0 error、0 未定义引用、0 overfull。

**还没做完的**：
- 4 个作业在收尾（§2）；
- 新结果还没写进论文正文（§4）；
- 用户要求的全文数据核查、综合审稿、中文全译稿、最终 HANDOFF（§5）。

---

## 1. 关键位置

| 东西 | 位置 |
|---|---|
| 主仓库（WSL） | `~/proj/agent-harness`（git 仓库，但 `paper/` 和大量新文件**未提交**；用户没要求提交，不要擅自 commit） |
| 论文源码 / PDF | `paper/skillvector.tex` / `paper/skillvector.pdf`；编译 `./paper/build.sh`（调用 Windows MiKTeX，输出也拷到 `C:\Users\12970\Desktop\ICLR2027\build-skillvector\`） |
| 论文快照 | `paper/.snapshots/`（今天的快照带 `0914` 字样；大改前先存） |
| 表 / 图生成 | `paper/tables.py`、`paper/figs.py`、**新增** `paper/replication.py`（跨任务×模型总表 → `paper/tab-replication.tex`，尚未 `\input` 进正文） |
| 审计 | `python3 whitebox/analysis/audit.py`（改任何数字前后都跑，**必须 ALL CHECKS PASSED**） |
| 取回的原始结果 | `howskill/results/p8-wb/fetched/by-host/<host>/<tag>.jsonl` |
| 修复前数据冻结快照 | `howskill/results/p8-wb/snapshots/fetched-20260913_2324/`（audit 从这里读修复前的数据） |
| 被重跑替换掉的旧文件 | `howskill/results/p8-wb/fetched/superseded/` |
| 行为筛选合并后的 cells | `howskill/data/cells/cells-<ds>-<model>.json` |
| SRA-Bench 数据 | `howskill/data/sra/`（theoremqa / logicbench / champ 的 instances、skills、pairs 和 meta.json） |
| 桌面交付物 | `C:\Users\12970\Desktop\SkillVector-图表逐条解释.md`、`SkillVector-审稿意见.md`（09-14 00:30 版，**图表和数字已部分过时**，最终要按新论文重写） |
| 仓库内同名副本 | `HOWSKILLWORK/FIGURES-EXPLAINED.md`、`HOWSKILLWORK/REVIEW-2026-09-14.md` |

---

## 2. 正在运行的作业（14:55）——具体命令

所有作业都是在远端用 `setsid nohup` 启动的 detached 进程，不依赖任何本地会话。
机器 ssh 别名为 `inspire-me-wt-gpu-<host>`。启动脚本在远端 `/root/_launch_<tag>.sh`，日志在 `/root/out/<tag>.log`，结果在 `/root/out/<tag>.jsonl`。

`B=/inspire/ssd/project/project-public/czxs253130660`，`PY=$B/venvs/whitebox/bin/python`，工作目录 `/root/wb/howskill`。

| host | tag | 进度（14:50） | 用途 | 实际命令（去掉 `$PY -u -m howskill.`） |
|---|---|---|---|---|
| wb2 | tqamis-depth | 129/142 | Mistral×TheoremQA 深度曲线 | `wb_spanvec --model $B/models/Mistral-7B-Instruct-v0.3 --dataset theoremqa --cells data/cells/cells-tqa-mistral.json --min-group 1 --max-new 900 --mode decode --layers 0,2,4,5,6,7,10,14,20 --filler fixedskill --baselines --per-calc 4 --max-calcs 200 --arms real --out /root/out/tqamis-depth.jsonl` |
| sra1 | tqamis-rank | 136/142 | Mistral×TheoremQA 秩曲线（L4） | `wb_spanvec --model $B/models/Mistral-7B-Instruct-v0.3 --dataset theoremqa --cells data/cells/cells-tqa-mistral.json --min-group 1 --max-new 900 --mode decode --layers 4 --filler fixedskill --baselines --per-calc 4 --max-calcs 200 --arms real,rank4,rank16,rank32,rank64,rank128,rank16lo,rank64lo --out /root/out/tqamis-rank.jsonl` |
| sra2 | fixmask-quarters40-q0 | 157/160 | 文档四段定位（40 calc），描述段 | `wb_spanvec --model $B/models/Qwen3-8B --mode decode --layers 8 --filler fixedskill --max-new 900 --per-calc 4 --max-calcs 40 --arms q0 --out /root/out/fixmask-quarters40-q0.jsonl` |
| hsw2 | fixmask-quarters40-q2 | 159/160 | 同上，工具签名段 | 同上，`--arms q2`，输出 `fixmask-quarters40-q2.jsonl` |
| hsw | fixmask-quarters40-q1 | ✅ 160 | 公式段 | `--arms q1` |
| wb3 | fixmask-quarters40-q3 | ✅ 160 | 例题段 | `--arms q3` |

- quarters40 的 4 个分段作业**都没有 `--baselines`**。它们选题的参数（种子 0、`--per-calc 4 --max-calcs 40`、默认 cells）和 `fixmask-big40` 完全相同，所以基线要从 `wb/fixmask-big40.jsonl` 按 instance_id 合并过来。`whitebox/analysis/span_summary.py` 可以一次传入多个文件，会自动合并。
- 空闲机器：hsw3、wb、sra3、sra4、hsw、wb3。**按计划不再派新实验**。

**判断作业是否结束**：

```bash
cd ~/proj/agent-harness && ./whitebox/status.sh            # 10 台一行一个：gpu%、在跑的 tag、近期行数、有无 Traceback
# 或逐个：
ssh inspire-me-wt-gpu-sra1 'wc -l < /root/out/tqamis-rank.jsonl; pgrep -f "[w]b_spanvec" >/dev/null && echo running || echo DONE'
```

**取回**：
- 本地 `whitebox/autofetch.sh` 常驻（PID 684736，15 分钟一轮，日志 `logs/autofetch.log`），规则见 §6。
- 等不及可以手动取：`scp inspire-me-wt-gpu-<host>:/root/out/<tag>.jsonl howskill/results/p8-wb/fetched/by-host/<host>/`
- 检查 autofetch 是否还活着：`ps -eo pid,etime,args | awk '$3=="bash" && $4=="./whitebox/autofetch.sh"'`
- 挂了就重启：`cd ~/proj/agent-harness && (nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 < /dev/null &)`

**作业结束后的分析**：

```bash
F=howskill/results/p8-wb/fetched/by-host
python3 whitebox/analysis/span_summary.py $F/wb2/tqamis-depth.jsonl $F/sra1/tqamis-rank.jsonl
python3 whitebox/analysis/span_summary.py $F/wb/fixmask-big40.jsonl $F/sra2/fixmask-quarters40-q0.jsonl \
    $F/hsw/fixmask-quarters40-q1.jsonl $F/hsw2/fixmask-quarters40-q2.jsonl $F/wb3/fixmask-quarters40-q3.jsonl
python3 paper/replication.py        # 刷新跨任务×模型总表
python3 whitebox/analysis/audit.py  # 必须 ALL CHECKS PASSED
```

---

## 3. 今天得到的结果（已核实，数字来自原始 jsonl）

### 3.1 跨任务 × 模型总表（`paper/replication.py`，Mistral×TheoremQA 两列尚为部分数据）

| 任务 | 模型 | n（组） | 注入 ρ [95% CI] | 最高对照 | 交接悬崖（相对深度） | k\* | 仍在读文档（knockout 保留 ≥0.5 的相对深度） |
|---|---|---|---|---|---|---|---|
| MedCalc | Qwen3-8B（L8） | 60 (15) | .87 [.73,.98] | .10 | .33–.39 | 52 | .78 |
| TheoremQA | Qwen3-8B（L8） | 99 (75) | .84 [.75,.92] | .25 | .33–.39 | 50 | .56 |
| MedCalc | Qwen3-0.6B（L6） | 204 (35) | .89 [.70,1.09] | — | .36–.43（修复前） | 40 | — |
| TheoremQA | Qwen3-0.6B（L6） | 132 (97) | .74 [.66,.82] | — | .36–.43 | 52 | — |
| MedCalc | Mistral-7B（L4） | 92 (26) | .92 [.77,1.09] | .27 | .19–.22 | **84** | .875 |
| TheoremQA | Mistral-7B（L4） | 115 (94) | .94 [.84,1.05] | .27 | 部分 .22–.31 | 部分 63 | .63 |

**对论文结论的影响（必须写进正文）**：

- ✅ **通道结论**（文档 span 移植远高于对照）在 2 个任务 × 3 个模型上都成立。
- ✅ **交接悬崖的相对深度**在 Qwen 家族内一致（两个领域、两个宽度都是 0.33–0.43）；❌ **跨家族不一致**：Mistral 早得多（0.19–0.31）。
- ✅ **k\* 不随宽度缩放**在 Qwen 家族内成立（MedCalc 0.6B 40 / 8B 52；TheoremQA 52 / 50）；❌ **跨家族不成立**：Mistral 同样 d=4096，k\* 为 63–84。所以「k\* 是文档的性质」要改成「在同一家族内不随宽度变」。
- ✅ **充分性与必要性的深度分离**在所有组合上都成立，而且 Mistral 上分离更大（悬崖 ≈0.2，但到 0.875 仍在读文档）。必要性边界随领域变化（TheoremQA 早于 MedCalc）。
- Mistral 的对照地板（0.13–0.27）高于 Qwen3-8B（MedCalc ≤0.10）。**Mistral 的注入层必须用 L4**：L7 已经在它的悬崖上，那里测到的「部分复现」是注入层选错造成的（mis2-big40：real .54，打乱 .27）。
- **LogicBench**（760 题，大多是二值答案）：按 skill 限制后几乎为空；逐题限制 n=57 时 real .75，但半剂量 .44、另一 skill .38 都偏高，深度曲线也没有悬崖。**判断为方法的适用边界**：答案空间很小时，任何扰动都相当于重掷硬币，逐题限制又挑出了靠运气失败的题。写进 Limitations，**不能写成「跨领域不复现」**。
- **CHAMP**：可用救回题只有 20 道，只报行为层（none .354 / gold .498 / wrong .422，错误 skill 反而帮忙）。**ToolQA**（需要工具查外部数据）和 **BigCodeBench**（需要沙箱执行单测）排除。

### 3.2 MedCalc × Qwen3-8B 的修复后重跑（均已换进论文，除非标注）

| 结果 | 修复后 | 修复前（旧论文值） | 状态 |
|---|---|---|---|
| 表 2 电池（fixmask-big40 + fixmask-dnear） | real .87 / realm .73 / α½ .06 / 远亲 .06 / 同 family .06（仅 20 题有定义） / 打乱 .08 / 噪声 .10 / 零臂 .00 | .87/.77/.13/.04/.12/.12/.13/.04 | ✅ 已换 |
| 充分性曲线（big40-depth） | L0 1.04 / L4 .94 / L8 .85 / L12 .77 / L14 .28 / L15 .19 / L16 .19 / L20 .15 | .94/.98/.87/.76/.36/.23/.23/.17 | ✅ 已换 |
| 必要性（ko-8b-fast） | L≤20 .08–.15，但 **L4 .33**；L24 .375 / L28 .75 / L32 .95 | 「L≤20 都 ≤.15」 | ✅ 已换 |
| 层窗口（fixmask-window） | w8–11 1.00 / w12–15 .96 / w14–19 .38 / w16–35 .11 | 同 | ✅ |
| 40 calc 秩（rank40-l8） | k4 .13 / 16 .06 / 32 .13 / 64 .54 / 128 .77 / full .87 / bottom .06/.00 / **k\*=52** | .12/.08/.10/.50/.73、k\*=54、bottom .02/.06 | ✅ 已换 |
| 10 calc 头条秩曲线的 k\* | **45**（预注册定义，修复前数据） | 「≈48」（两种定义都算不出） | ✅ 已改 |
| 0.6B 秩阶梯（fixmask-lad06-rank） | k16 .02 / 32 .21 / 64 .74 / 128 .72 / full .89 / **k\*=40** | k\*=41 | ✅ 表 4 已换；**正文 §5.3 的 0.6B 数字还是修复前的，待改** |
| 10 calc 开发集 + 剂量（fixmask-dev10，**限制集仅 n=16 / 4 calc**） | α .4 .06 / .5 .00 / .55 .06 / **.6 .62** / .7 .94 / 1.0 1.00；另一 skill .19 / 打乱 .00 / 噪声 .00 | .17/.03/.17/.88/.97/1.00（n=30）；打乱 .10 | **图 1 和 tab-battery-dep 已重生成；§4 正文数字待改** |
| doc-last（fixmask-dl，n=28） | real L8 1.00 / **L16 .85**；dbar 1.00/.63；dother .96/.48；**dperp .04/.04** | 1.06 vs 1.00；L16 .14→.80 | **§whose 正文待改** |
| 文档四段（fixmask-quarters，10 calc，n=16） | 描述 .12 / **公式 .81** / 工具签名 .06 / **例题 .06** | .28/.83/.11/**.44** | ⚠ **「例题贡献约一半」修复后不成立**；quarters40 收尾中，出结果后改正文 |

### 3.3 Mistral 其他结果（MedCalc，Mistral 自己的 cells）

- 深度（mis2-depth + mis2-depth-fine，n=79）：L0 1.00 / L1 .98 / L2 1.00 / L3 1.02 / L4 .98 / L5 .90 / L6 .76 / **L7 .49** / L10 .35 / L12 .22 / L20 .10 / L24 .06。
- knockout（mis2-ko-b，n=72）：L0 .11 / L4 .17 / L8 .12 / L12 .24 / L16 .24 / L20 .26 / L24 .42 / L28 .58。
- 电池 L4（mis3-big40-L4，n=92）：real .92 / realm .69 / α½ .27 / 打乱 .27 / 远亲 .24 / 噪声 .15 / 零臂 .00。
- 秩 L4（mis3-rank-L4）：k4 .17 / 16 .20 / 32 .14 / 64 .29 / 128 .71 / full .92 / bottom16 .08 / bottom64 .17 → k\*=84。
- 行为层：MedCalc none .140 / gold .261 / wrong .104（R=228）；TheoremQA none .146 / gold .293 / wrong .123（R=143）。

### 3.4 行为筛选（sra_behave，批量解码，只用于选题）

| 数据集 × 模型 | none | gold | wrong | R |
|---|---|---|---|---|
| TheoremQA × Qwen3-8B | .465 | .624 | .451 | 171 |
| TheoremQA × Qwen3-0.6B | .153 | .347 | .162 | 173 |
| TheoremQA × Mistral-7B | .146 | .293 | .123 | 143 |
| LogicBench × Qwen3-8B | .762 | .862 | .717 | 137 |
| CHAMP × Qwen3-8B | .354 | .498 | .422 | 51（可用 20） |
| MedCalc × Mistral-7B | .140 | .261 | .104 | 228 |

---

## 4. 论文：已改 / 待改

### 4.1 今天已经改好的（审计全部通过）

- 删除了 skill 识别实验（摘要、§whose、附录段落、fig:decode、tab:decode）。
- 引用：补 MedCalc-Bench、SRA-Bench、Qwen3、Mistral（bib 已有）、Meng 2022、Geva 2023、Sia 2024、Wang 2023、Timkey 2021、Kovaleva 2021、gist、ICAE、ICV、Stolfo 2025、CAA、response planning、Makelov 2023、Feng&Steinhardt 2023、Balepur 2024、Min 2022、Thinking Machines 博客；改 zhang2023 → ICLR 2024、ragcite → ECIR 2026、ROME 第三作者 Andonian。全部对照 arXiv 核实。
- 修掉「Eq. ??」「§??」、图 1 图注 Left/Right、图 1 画图脚本混入 corrupted 对照的 bug、多处和数据不符的数字（零臂 1766/93.9%/108、80/80、massive activation 34/40 与 99–180×、97.7%、27、doc-first「逐位相同」、k\* 45/52、底部 k、L4 knockout 等），以及「k\* 随深度不变」这类过度声称。
- 表 2、表 4、图 1、tab-battery-dep 已用修复后数据重生成。附录 app:depth 删掉了作废的 max-new 400 knockout 和一段自相矛盾的论述。

### 4.2 待改（新对话接手的主要工作）

**硬约束：正文 ≤ 9 页，当前零余量**。每加一段，就要在别处删掉同样多。

1. **把 `paper/tab-replication.tex` 放进正文**（建议放在 §5.3 末尾或单独一小节「Replication across tasks and model families」），加一列「reading」（必要性边界）。
   - 同时压缩 §5.1 的 massive activation 撤回段（细节已在附录）和 §6 陷阱段来腾出空间。
2. **§Setup**：加 TheoremQA（SRA-Bench，747 题、320 skill，官方 prompt 和评分器逐字照搬）和 Mistral-7B-Instruct-v0.3 `\citep{jiang2023mistral}`；说明每个模型用自己的行为筛选 cells；TheoremQA 多为单题组，限制退化为逐题（修复后接收方是确定性的，所以可以这样做）。
3. **§5.1**：「两个边界在 0.6B 上落在同一相对深度」要限定为 Qwen 家族内；补 Mistral（悬崖 ≈0.2、仍在读 ≈0.875）和 TheoremQA。
4. **§5.3**：「需要多少方向是文档的性质」→ 只在家族内成立；补 TheoremQA（52/50）和 Mistral（84/63）；0.6B 数字换成修复后（k\*=40；k=16/32/64/128 → .02/.21/.74/.72）。
5. **摘要、结论、贡献列表**：「does not scale with model width」→ 限定「within a model family」；加一句跨两个任务、两个家族复现通道和对照。
6. **§4**：剂量句换成修复后（阈值 .55–.6，n=16），打乱 .08 / 噪声 .10（40 calc 已换），图 1 图注里的 n 核对一下（图题现在由脚本写 n=20 / n=16）。
7. **§whose**：doc-last 数字换成 fixmask-dl；四段定位等 quarters40 出结果后改（很可能要删「例题约一半」）。
8. **Limitations**：写 LogicBench 边界、CHAMP 样本不足、ToolQA/BigCodeBench 排除理由、Mistral 对照地板偏高、k\* 与家族相关。
9. **附录**：pre/post-fix 披露段（「An instrument fault, and which results predate its fix」）按最终状态更新；新增一小节放 TheoremQA 和 Mistral 的完整曲线（可以直接用 span_summary 的输出做表）。
10. 每改一处：`python3 whitebox/analysis/audit.py`（新数字要**加 check**）→ `./paper/build.sh`（9 页、0 未定义引用）。

---

## 5. 用户交代、尚未完成的任务（按顺序）

1. 等 §2 的作业跑完 → 分析 → 写进论文（§4.2）。
2. **全部实验完成后，完整核查论文中的所有数据、结论和计算值**。做法：逐段读正文和附录，每个数字要么有 audit check，要么当场用原始 jsonl 重算。
3. **整篇论文的综合评价与审稿意见**（上一版在 `HOWSKILLWORK/REVIEW-2026-09-14.md`，已过时，要按新论文重写）。桌面放一份。
4. **全文翻译成中文**，术语保留英文并加中文解释，**放桌面**（例如 `C:\Users\12970\Desktop\SkillVector-全文中文译稿.md`）。桌面上的图表逐条解释也要按最终论文更新。
5. 生成最终 HANDOFF。
6. **AI use statement：用户明确说先不管**（ICLR 2027 强制要求，desk reject 风险，最终要提醒用户）。
7. 用户要求**每小时检查一次，持续到北京时间 2026-09-14 21:15**（原话写的是 10:00，与「20 小时后」矛盾，取较晚者）。
   - 本会话的定时任务 `9c91242c` 是 session-only 的，**旧会话结束就失效**。新会话要用 CronCreate 重建（每小时第 17 分，prompt 可以抄 §47 开头的例行检查清单）。
   - 更重要的一点：**两次检查之间要继续干活，不要空等**（用户已经批评过这一点）。
8. 今天新开的 4 台 4090（`wt-gpu-sra1..4`）用完后问用户是否 stop（费用很低，0.33 点券/小时，但不用就该关）。**stop 前先确认 /root/out 下的结果都已取回**（stop 后容器重建，/root 清空）。

---

## 6. 必须知道的坑（今天全踩过）

- **`pkill -f` / `pgrep -f` 会匹配到自己的命令行**：ssh 远端命令里只要出现 `out/<tag>.jsonl` 这样的字面量，就会把执行命令的 shell 自己杀掉。停远端进程用 `pkill -f "[w]b_spanvec.*tag名最后一个字母加方括号"`，而且同一条命令里不能再出现这个路径；启动作业一律用 `whitebox/launch.sh`（下发脚本文件）。
- **`launch.sh` 拒绝复用已有 tag**（2026-09-13 同名重跑截断过 5 个完成的结果）。续跑用 `RESUME=1 ./whitebox/launch.sh <host> <tag> <module> "<args> --resume"`。
- **autofetch 规则**：只在「本地文件是远端的字节前缀」时覆盖；行数相等但内容不同也视为不一致，旧文件先挪到 `fetched/superseded/`；远端 0 行的文件跳过。改脚本要用「写新文件 + mv」，**不要 `sed -i`**（运行中的 bash 仍读旧 inode，要重启进程才生效）。
- **后台 watcher（`watch_jobs.sh`）会被 Claude Code 以「内存不足」杀掉**，不要用它，靠定时检查加主动轮询。
- **限制集口径**：MedCalc 按 calculator（接收方从不做对）；TheoremQA 多为单题组，用 `--min-group 1`，实际等于逐题；LogicBench 按 skill 限制为空，只能 `span_summary.py --per-item`，而且结果不可信（见 §3.1）。
- **只在部分题上有定义的臂**（例如 `dnear` 只对有同 family 邻居的 calculator 有定义）：分母只能用带该键的行。`span_summary.py` 已修；`tables.py` 和 audit 的 `frac` 本来就对。
- **k\* 定义**：取 k=16 到曲线最大值这段范围的一半，在 log₂k 上插值（`tables.py` 和 `replication.py` 一致，是预注册定义）。不要用「full-rank 的一半」。
- **行为筛选（batch）和因果运行（batch-1）的基线有约 5% 不一致**：cells 只用来选题，所有报告数字都读 span 运行自己的 batch-1 基线。
- **Mistral**：注入层用 L4（它的悬崖在 L5–L7）；tokenizer 需要 sentencepiece（已装进共享 venv）；模板把 system 合并进 user。
- **TheoremQA 评分**依赖 `latex2sympy2`（已 `--no-deps` 装进共享 venv）；官方评分器不解析方括号形式的列表答案，这是上游行为，保持原样。
- **共享盘配额**：hdd 个人目录已满；ssd 上 models 约 71G，接近配额。结果都在各机器的 /root/out，靠 autofetch 取回本地。
- **GPU 盒子现在能直连 huggingface.co**（和 CLAUDE.md 的旧记录不同）。

---

## 7. 常用命令速查

```bash
cd ~/proj/agent-harness
./whitebox/status.sh                                   # 10 台状态
python3 whitebox/analysis/span_summary.py <jsonl...>   # ρ + 按组 bootstrap CI；knockout 文件自动识别
python3 whitebox/analysis/span_summary.py --per-item <jsonl>
python3 paper/replication.py                           # 跨任务×模型总表
python3 whitebox/analysis/audit.py                     # 审计
./paper/build.sh                                       # 编译（看末尾：errors / undefined / overfull / main text pages）
cd howskill && python3 -m howskill.sra_cells results/p8-wb/fetched/by-host data/cells   # 合并行为筛选分片
# 新作业（先推代码）：
./whitebox/push_local.sh inspire-me-wt-gpu-<host> howskill
./whitebox/launch.sh <host> <new-tag> wb_spanvec "--model $B/models/Qwen3-8B --dataset theoremqa --cells data/cells/cells-tqa-qwen8b.json --min-group 1 --layers 8 --filler fixedskill --baselines --max-new 900 --per-calc 4 --max-calcs 200 --arms real,..."
# 重新生成论文表图（在 paper/ 下用 importlib 调 tables.tab_big40 / tab_ladder_models / tab_battery(restrict="needs_document", name="tab-battery-dep") / figs.fig_channels，示例见 HANDOFF §47 12:45–14:55 条目）
```

平台（CLAUDE.md 有完整流程）：
- 实例列表：`inspire notebook list --workspace 可上网GPU资源`
- 机器被回收（STOPPED）时：`inspire notebook start <n>` → `connection refresh`（常要跑两次）→ `ssh-keygen -R "[<n>]:22222"` → `push_local.sh` → 重新 launch。**先保数据**。
