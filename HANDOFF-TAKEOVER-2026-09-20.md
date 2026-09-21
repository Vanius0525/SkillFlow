# 接管文档：SkillVector（2026-09-20，写给新的 Claude Code 实例）

> **已被取代**：见 [`HANDOFF-TAKEOVER-2026-09-21.md`](HANDOFF-TAKEOVER-2026-09-21.md)。
> 本文件保留作历史记录。
>
> **2026-09-20 晚更新**：§5 的第 2、3、5、6 项已全部补完，结果与论文改动见
> [`CAMPAIGN-2026-09-20.md`](CAMPAIGN-2026-09-20.md)（含事前预注册与逐条对照）。
> 第 6 项**证伪了论文原有的一个说法**，已改写；新开的问题记在 `IDEAS.md` I7。
> §5 现在只剩第 1、4、7 项未做。下面 §5 的表格已按此更新。

读完这一份就能接手。上一份是 [`HANDOFF-TAKEOVER-2026-09-18.md`](HANDOFF-TAKEOVER-2026-09-18.md)（仍可查旧细节），
这一轮（09-18 → 09-20）的调度与逐条发现记录在 [`CAMPAIGN-2026-09-18.md`](CAMPAIGN-2026-09-18.md)。
**与更早文档冲突时以本文件为准。**

---

## 0. 一段话现状

论文 `paper/skillvector.tex` 可编译：0 error、0 未定义引用、0 overfull，**正文 10 页**（用户已同意暂时超出 ICLR 的 9 页限制），全文 44 页。
`paper/check_main_data.py` **64,599 项全部通过**，`whitebox/analysis/audit.py` 通过。
**11 台 GPU 实例全部 STOPPED，没有作业在跑**；本轮所有结果都已拉回本地并校验（逐行可解析、行数=唯一题数=预期）。
正文新增 §4.4「Which positions carry the effect」+ 图 2（位置预算四栏图）；图 3 改为逐层、共用层轴的新设计。
代码与论文已推到 GitHub（`master`，最新 `6ec78b1`；改动前的论文打了标签 `paper-2026-09-18-before-full-rerun`）。

---

## 1. 先跑这四条确认环境没坏

```bash
cd ~/proj/agent-harness
python3 paper/check_main_data.py          # 必须 PASS: 64599 checks
python3 whitebox/analysis/audit.py        # 必须 ALL CHECKS PASSED
./paper/build.sh                          # errors=none / undefined=0 / overfull=0 / main text pages=10
cd paper && MPLCONFIGDIR=/tmp/skillvector-mpl python3 refresh_main_data.py   # 重建全部 4 图 4 表并自检
```

`refresh_main_data.py` 会依次跑 `main_evidence.py`、`replication.py`、`replication_full.py`、
`fig_channels_full.py`、`fig_rank_full.py`、`fig_posbudget.py`、`check_main_data.py`、`audit.py`，任何一步失败即停。

---

## 2. 正文表图 → 数据来源（全部为修复后数据）

| 显示项 | 生成脚本 | tag | n |
|---|---|---|---|
| 表 1 作答形式 | `main_evidence.answer_format_full` | `tA-mc` / `tA-num-a,b` / `tA-cot-1..4` (+`tA-cot-self`) | 358 题 × 36 层 |
| 图 1 位置通道（最后位置 vs span，层 8） | `fig_channels_full.py` | `full-battery-a/b` + `pb-tq` | 135 |
| **图 2 位置预算（新）** | `fig_posbudget.py` → `whitebox/analysis/posbudget_report.py` | `pb-*`、`fp-*`（见 §4） | 135 |
| 表 2 span 电池 | `main_evidence.span_battery` | `full-battery-a/b` | 135（同族臂 41） |
| 表 3 跨模型复现 | `replication.py` | 见 `ROWS`/`NEW`/`FILL` | 各行不同 |
| 表 4 skill 内容与问题依赖 | `main_evidence.skill_content` | `full-battery-a`+`full-quarters`；`full-dl-a/b` | 135；151 |
| 图 3 深度（新版，逐层） | `main_evidence.depth_v2` | `full-depth-*`+`dep1-mc8-*`；`full-ko`+`ko1-mc8-*`；`pb-tq`+`fp-*`+`fp1-*`；`x8-win-a/b`+`win1-a/b` | 135（敲除 134） |
| 图 4 秩曲线 | `fig_rank_full.py` | `full-rank-*`+`x8-rank-*`；`q06-rank-*`；`mis-rank-*` | 135 / 362 / 92 |

**改完数据后必须重跑**：对应生成脚本 → `check_main_data.py` → `build.sh`。

---

## 3. 本轮（09-18 → 09-20）做了什么

### 3.1 新实验：位置预算（正文 §4.4 + 图 2）

模块 `howskill/howskill/wb_posbudget.py`，报告 `whitebox/analysis/posbudget_report.py`。
同一批 135 题（14 calculator）、层 8、与电池相同的接收方；预注册写在 `CAMPAIGN-2026-09-18.md` §1（数据回来前固化）。

- 固定预算只改选位：均匀 / 随机 / 最大‖d‖ / 错位（同一批状态平移半段）/ 语义连续窗（流程·描述·示例·随机）/ span 外最后 B 位。
- 追加：`cNxB` 同预算切成 N 个连续块；`shD` 整段平移 D 位；`snD/sbD` 不卷绕平移；`xfD/xlD` 原位但去掉首/尾 D 位。
- 结论：**恢复不由位置数或注入能量决定**（分散写一半 ≤.15、span 外 ≤.07），而由**连续性**（256 位 1 块 .37 → 32 块 .08）、
  **落在流程段**（半段连续窗 .82 vs 示例段 .18）与**逐位精确放置**（平移 1 位 .15–.22；去掉首/尾 16 位仍 .89–.92）决定。
- 仪器检查：identity 135/135、整段注入复现电池 135/135、跨作业重复臂 135/135（×2）。

### 3.2 正文里「不是全量 / 未覆盖全部层」的补跑

- 表 1：修复 Tier A 的 mask bug（`capture_block_outputs`/`score_with_patch`/`first_token` 现在都传显式 mask），
  加 identity 臂；三种作答形式统一 358 题 × 36 层 → 1.000 / 0.235 / 0.003，identity 逐题精确。
- 图 3：单层注入、注意力敲除、最后位置都补到**全部 36 层**，前两者在同一批题上配对；窗口平铺覆盖整个层栈。
  交接边界 L13（0.36），读取边界 L25（0.69）。
- 表 3：0.6B 与 Mistral 的 MedCalc 行换成全量；6 行的 handover / reading 都改为逐层、与彼此配对。
- 窗口实验改用与电池一致的接收方（`wb_spanpatch --filler fixedskill`，逐题核对 467/467 一致），并新增全层注入 0.98。
- §4.1 分解：1.7B fp32、358 题全量（presence .098 = wrong-skill 基线，content .805）。
- §4.7 两个读数诊断全量重跑：共享均值 +5.05 nats 而准确率更低（.251 vs .288）；强制 `ANSWER:` 提示把增益从 39.7pp 压到 4.7pp、
  仍留 +1.08 nats。
- 几何：massive activation 在 48 个 calculator 的 35 个上出现（121–195×，同两维）；span 宽度 365–1,630；跨实例余弦 ≥.994。

### 3.3 发现并修掉的方法学问题

1. **窗口实验接收方与电池不同**（旧 `wb_spanpatch --matched` 把 span 填成 control prompt 的前缀）：467 题里只有 358 题行为一致，
   却用电池基线归一化。已加 `--filler fixedskill` 并重跑。
2. **Tier A 的 mask 不一致**（捕获不传、解码传），与 MedCalc 那条线 6.1% null 臂翻转同源。已修，identity 现在逐题精确。
3. **mirror 的 `cp -ru` 会把正在写的 e14 层文件复制成 0 字节**且永不更新（`d17-neutral` 第 24–26 层两次中招）。
   已改为按大小比对 + 临时名原子替换。
4. **秩拐点的家族差异被收窄**：全量下 MedCalc 72 [46,94] vs 47 [43,55]、TheoremQA 64 [50,79] vs 50 [39,67]，两个任务区间都重叠 →
   正文改为「有迹象但未确立」。

### 3.4 运维基础设施（这一轮新建）

| 文件 | 作用 |
|---|---|
| `whitebox/qrun.sh` | 远端常驻队列执行器：一个作业接一个，`--resume` 续跑，完成写 `.done`（镜像到共享盘），队列空写 `.idle` |
| `whitebox/qstart.sh <host> [--push]` | 下发 `whitebox/queues/<host>[.2].txt` 并确保 runner 在（每台可跑两条队列） |
| `whitebox/fleet.sh` | 本地守护：空闲 15 分钟停机、runner 掉了重拉、被平台停掉且队列未完成则自动重启续跑 |
| `whitebox/mirror.sh` | 远端每 3 分钟把 `/root/out` 镜像到共享盘（含 `.done` 与 e14 目录） |
| `whitebox/analysis/campaign_numbers.py` | 一次性算出正文所有「已有实验」的全量新数字 → `whitebox/analysis/out/campaign-numbers.{json,md}` |

---

## 4. 本轮产生的 tag（全部已在 `howskill/results/p8-wb/fetched/by-host/`，e14 类在 `whitebox/results/fetched/tA/`）

位置预算：`pb-ev pb-rn pb-mx pb-td pb-tq pb-wf pb-wd pb-we pb-wr pb-c256 pb-chalf pb-sh pb-wh pb-sn pb-sx`（各 135）、
`fp-a fp-b fp-c`（7 层）、`fp1-a..d`（其余 29 层）。
补层：`dep1-mc8-a..d`(135)、`ko1-mc8-a..f`(134)、`win1-a/b`(135)、`dep1-tqa8-a..d`(99)、`ko1-tqa8-a..c`(63)、
`dep1-mc06-a/b`(362)、`ko1-mc06`(90)、`dep1-tqa06`(132)、`ko1-tqa06`(125)、`dep1-mcmis`(92)、`ko1-mcmis`(46)、
`dep1-tqamis-a/b`(115)、`ko1-tqamis`(65)。
全量补测：`x8-extra`、`x8-dl-dall`、`x8-win-a/b`、`x8-rank-x`、`x8-rank-lo`、`t8-win`、
`mis-bat-a/b`、`mis-rank-a/b/lo`、`mis-depth-a/b`、`mis-ko`、`q06-bat-a/b`、`q06-rank-a/b/lo`、`q06-depth-a/b`、`q06-ko`、
`t06-bat`、`t06-ko`、`geom-8b/06/17`、`rd-cue`。
Tier A：`tA-mc`、`tA-num-a/b`、`tA-num-k4/k16`、`tA-cot-1..4`、`tA-cot-self`、`d17-neutral(+b)`、`d17-shuffled`、`d17-corrupted`、`rd-e2`。

⚠ 结果只有本地一份（`.gitignore` 排除），共享盘 `ssd/.../wbout/` 上有镜像但要起机器才能读。**建议尽早打包备份。**

---

## 5. 仍然不是「全量」的部分（如实清单，附成本）

**任务维度**
1. **TheoremQA 三行**每个 skill 组最多取 4 题：8B 168/170、0.6B 168/172、Mistral 142/143。
   要严格全量需把三行的电池/秩/深度/敲除全部重跑（换抽样会改变题集），约 60 GPU·h，收益 1–2%。
   **仍未做**，但抽样上限已在附录 `app:replication` 写明（原文只说「747 题」，是题池不是评测集）。

**自变量维度（坐标轴没覆盖满）**
2. ~~秩曲线：TheoremQA 三行仍是稀疏 5 点~~ **已补**（`tqa-rank-d1/d2`、`tqa06-rank-d1/d2`、
   `tqamis-rank-d1/d2`，k=8/24/48/96/192/256/384）。三条曲线都在 k≤384 回到未截断值；
   **k\* 一字未动**（定义在固定网格 {16,32,64,128} 上）。
3. ~~Mistral×MedCalc 在 k=256 只有 .72~~ **已补**（`mis-rank-hi`，k=192/384/512）：
   .632/.842/.825，**在 k=384 恰好回到未截断的 .842**，图 4 横轴已延到 512。
4. **表 4 下半（问题依赖）只有第 8、16 两层**。补全 36 层 ≈ 64 GPU·h；粗网格（0/4/12/20/28）≈ 6 GPU·h。
5. ~~§4.1 的两个负对照只跑了 14/28 层~~ **已补**（`d17-shuffled-b`、`d17-corrupted-b`）。
   新补的第 25 层是 shuffled 对照的**最大值**（.280 > 原区间上界 .256）→ 正文区间由
   .17–.26 改为 **.17–.28**。原区间确实是「哪些层碰巧跑过」的产物。
6. ~~表 1 的「补丁位置数」只有 1/4/16，补 64/256~~ **口径改了并已补**：无文档 prompt 只有
   **61–63 个 token**，k=64 会写到负位置、k=256 不存在。改跑 k=32/48/**61**（61 = 整条 prompt）。
   结果 .235/.261/**.403**/.403/.395/.370 —— **在 k=16 饱和，之后不升反降**，
   **证伪**了原文「a patch transports as much as the positions it is given」。已改写，见 `IDEAS.md` I7。
7. **逐层敲除只在各行的受限题上做**（MedCalc 8B 134 题）。若要在全部 466 rescued 题上做逐层敲除 ≈ 45 GPU·h
   （现有 466 题版本是步长 4，附录仍可引用）。

**按设计不扫的自变量**（不算缺口，但要在正文说清楚）：图 1 与表 2 固定在层 8；秩曲线固定在各模型的注入层；剂量曲线固定 α 网格。

---

## 6. 机器与运维（全部 STOPPED，要用先起）

```bash
inspire notebook list --workspace 可上网GPU资源
inspire notebook start wt-gpu-hsw --workspace 可上网GPU资源 --no-wait
inspire notebook connection refresh wt-gpu-hsw --workspace 可上网GPU资源   # 常要两次
ssh-keygen -R "[wt-gpu-hsw]:22222"
./whitebox/qstart.sh hsw --push        # 推代码 + 起 mirror + 起队列执行器
(nohup setsid ./whitebox/fleet.sh 600 >> logs/fleet.log 2>&1 </dev/null &)
(nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 </dev/null &)
```

**踩过的坑（本轮新增）**
- 起机前**先停 `fleet.sh`**：它会在你推新代码之前用旧代码把队列拉起来，导致前两次 attempt 失败。
- 平台会停掉**队列跑空**的实例（GPU 0%），也会在实例连续运行约 24 h 后停掉（sra4）。`fleet.sh` 的空闲停机是必要的。
- 实例重启后 `/root/out` 可能**只保留文件名、内容为空或残缺**；jsonl 按行数取镜像里最大的副本，e14 目录按总字节取。
- 本机 WSL 重启会同时带走 `fleet.sh`、`autofetch.sh` 和会话内 cron；重启后先确认这三样。
- WSL 的 DNS 代理有时解析不到 `qz.sii.edu.cn`（走错网卡）。Windows 侧 `nslookup` 能解析就是这个问题，通常几分钟自恢复。
- `pkill -f '<pattern>'` 会匹配到自己所在的命令行（本轮又中过一次，把自己杀了）。一律用
  `ps -eo pid,args | awk '$2=="bash" && $3=="whitebox/fleet.sh" {print $1}' | xargs -r kill`。

---

## 7. 下一步建议（按性价比排序）

1. **压回 9 页**（若要投 ICLR）：正文现在 10 页。可压缩的位置：§4.7 Readout checks 整段移附录、Related Work 精简、
   §4.3 剂量细节缩一半。**不要**缩字号或图。
2. 补 §5 清单里的 2、3、5、6（合计约 15 GPU·h），这四项能让图 2/表 3 的秩曲线与表 1 的位置数轴真正覆盖满。
3. `IDEAS.md` I6（平移 1 位即失效）的最小验证：平移同时用 `position_ids` 还原 RoPE 相位，一条臂、约 0.5 GPU·h，
   直接决定正文对这条结果的解释口径。
4. 把 192 MB+ 的结果打包备份到共享盘以外的地方。

---

## 8. Open Ideas

见 `IDEAS.md`：I6（注入状态必须逐位归位）、I1/I2（作答形式与单位置补丁的混杂）、I4（行为断崖与机制量的非线性差）。
`CAMPAIGN-2026-09-18.md` §6.0 记着过程中的反事实观察。
