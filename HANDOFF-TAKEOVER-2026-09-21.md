# 接管文档：SkillVector（2026-09-21，写给新的 Claude Code 实例）

读完这一份就能接手。上一份是 [`HANDOFF-TAKEOVER-2026-09-20.md`](HANDOFF-TAKEOVER-2026-09-20.md)，
这一轮（09-20 → 09-21）的调度、**事前预注册**与逐条对照在
[`CAMPAIGN-2026-09-20.md`](CAMPAIGN-2026-09-20.md)。
每个正文显示项对应哪个实验、用谁的材料、多大样本，在
[`EXPERIMENTS.md`](EXPERIMENTS.md)（**新建，要随实验变化实时维护**）。
**与更早文档冲突时以本文件为准。**

---

## 0. 一段话现状

上一份 §5 列的四个缺口（第 2、3、5、6 项）**全部补完**，12 个作业全部回收校验；
第 6 项**证伪了论文原有的一个说法**，正文与附录已改写。
另外发现并修掉一类系统性问题：**附录大量显示项还停在 200 题 / 120 题 / 20 个 calculator 的旧样本，
而正文早已是全量**——同一个量在正文印 0.805、在附录印 0.812。全部重建，不需要 GPU。
论文 `paper/skillvector.tex` 可编译：0 error、0 未定义引用、0 overfull，**正文 10 页**，全文 **46 页**。
`paper/check_main_data.py` **70,201 项通过**（原 64,599），`whitebox/analysis/audit.py` 通过。
**所有实例应为 STOPPED**（见 §6 的待办）。12 个 commit 已推 GitHub（`e07fec5..568d2b3`）。

---

## 1. 先跑这四条确认环境没坏

```bash
cd ~/proj/agent-harness
python3 paper/check_main_data.py          # 必须 PASS: 70201 checks
python3 whitebox/analysis/audit.py        # 必须 ALL CHECKS PASSED
./paper/build.sh                          # errors=none / undefined=0 / overfull=0 / main text pages=10
cd paper && MPLCONFIGDIR=/tmp/skillvector-mpl python3 refresh_main_data.py   # 八个阶段全过
```

`refresh_main_data.py` 不覆盖这三个新脚本，改了对应数据要手动跑：

```bash
python3 paper/controls_table.py    # tab-controls.tex  （§4.2 的三个对照文档）
python3 paper/decomp_tables.py     # tab-causal / tab-parperp / tab-geometry-tierA
cd paper && python3 figs.py --e14 "tierA=../whitebox/results/fetched/tA/d17-neutral" --out .
```

---

## 2. 这一轮做了什么

### 2.1 四项补跑（预注册 → 结果）

预测和证伪条件写在 `CAMPAIGN-2026-09-20.md` §1，**数据回来之前**固化；结果在 §5。

| 项 | 内容 | 结果 |
|---|---|---|
| 2 | TheoremQA 秩曲线补密网格（k=8/24/48/96/192/256/384，三个模型） | **k\* 一字未动**（49.7 / 52.1 / 64.0），表 4 逐字节不变；三条曲线都在 k≤384 回到未截断值 |
| 3 | Mistral×MedCalc 补 k=192/384/512 | .632 / **.842** / .825 —— **恰在 k=384 回到未截断的 .842**（两个 Qwen 在 256）。图 4 横轴已延到 512 |
| 5 | 两个负对照补满 28 层 | 新补的**第 25 层就是 shuffled 对照的最大值**（.280 > 原上界 .256）→ 正文区间 .17–.26 改为 **.17–.28**。原区间确实是「哪些层碰巧跑过」的产物 |
| 6 | Tier A 补丁位置阶梯 | **证伪**，见 §2.2 |

### 2.2 ⚠ 第 6 项：位置阶梯在 k=16 饱和，原文说法为假

交接文档原本写「补 k=64 / 256」。**无文档 prompt 只有 61–63 个 token**（实测，358 题全量），
补丁写的是它的最后 k 位，所以 k=64 会索引到负位置、k=256 不存在。改跑 **k=32 / 48 / 61**，
其中 61 = 整条 prompt 的全部位置，是这条阶梯**物理上的最后一级**。

```
k  =    1      4     16     32     48     61
ρ  =  .235   .261   .403   .403   .395   .370     ← .403 也是所有 k × 全部 36 层的全局上限
```

- k=32 与 k=16 在 L29 上**逐题完全相同**（0 个不一致对）；k=61 丢 4 题、没多对任何一题。
- 原文 "how much of it a patch transports is a function of how many positions it is given" **为假**，已改写。

**改写后的口径（重要，2026-09-21 又收窄过一次）**：
- **.403 vs 1.000** ← 差在**作答形式**。同一个探针、同一个接收方、同一个 donor，多选格式到 1.000。这个比较是干净的。
- **.403 vs .89（MedCalc 整段注入）← 不能归因于位置**。在同一批自由作答材料上，
  写文档自己的 688 个 token 只有**层 0** 到 .408（≈把文档放回去），层 3 起 ≤.17，层 15 起归零
  （`tab:windows2`）——**比写末 16 位还差**。自由作答下这个任务任何通道都不超过约 .41，
  所以天花板是**格式**造成的，不是位置。
- 真正隔离「位置」的是 MedCalc 上那个**同接收方、同题、同层**的对照：整段 .89 vs span 之后最多 256 位 .05。
- **未排除的混杂**：阶梯注入的接收方是**无文档** prompt，而整段注入是**错文档** prompt。
  已知旁证（1.7B 多选末位置）是错文档接收方**从不更差**、中层更好，方向与「接收方解释天花板」相反，
  **但自由作答下没测过**。论文附录已明说这一点。补测见 §5。

### 2.3 附录全面落后于正文（这一轮最大的一类修复）

**症状**：同一个量两个数。正文 §4.2 是 358 题的 0.805，附录 `tab:controls` / `tab:causal` /
`tab:parperp` / `tab:ladder` / `fig:causal` / `fig:decomp` 是 200 题（rescued cell 48）的 0.812，
而正文让读者去附录看「the full comparison」。§B.6 和 `tab:format` / `tab:windows2` 的 8B 部分
则是 120 题的旧样本（free-form 效应 0→0.467、rescued 56、单位置天花板 0.304）。

**处理**：全部用**已有**的全量运行重建，不花 GPU。两个数字大到改变句子：
- **跨 family 的 donor：0.167 → 0.049**（L27）。48 题的小样本把它高估了一倍多。
- 8B 多选的 presence：从「恰好等于 0.250 的随机线」变成 **0.298**，图注已改口径。

**`tab:prdiag` 另有一层问题**：正文说「centred participation ratio」并引用 .85 / 62–99，
那是**内容矩阵**的 PR；而表里报的是**状态**的 PR，两者差约 15 点——读者按图索骥找不到那两个数。
表已改成内容矩阵，并从 20 个 calculator 换到全部 48 个。顺带修掉一个错数：
**谱坍缩在 L16 是 1.0，不是 17**（全量下坍缩是彻底的，反而加强了那段自己的论点）。

### 2.4 其他修复

- **`d17-neutral` 第 24/25/26 层本地是 0 行**（上一轮 mirror bug 残留），共享盘上有完整副本。
  两个自检都读不到这三层，所以连过两轮 campaign 没被发现。`fetch_ta.sh --mirror` 取各副本中最长的一份。
- **TheoremQA 抽样没披露**：附录原写「747 题」，实际**每 skill ≤4 题、≤200 skill** → 142–168 题 / 113–122 skill。已写明。
- **一段话在两个附录小节里逐字重复**，已去重。
- **意外复现**：改队列后没重推 sra4，`tA-num-k48` 在两台机器上各跑了一遍——
  不同容器、不同卡、36 层 × 358 题 × 最长 900 token 生成，**逐字节完全相同**。已记进附录 `app:limits`。

### 2.5 新增的文件

| 文件 | 作用 |
|---|---|
| `EXPERIMENTS.md` | **实时维护**：每个显示项 → 材料/模型/n/接收方/tag/生成脚本；谁的材料 vs 我们自造；Tier A 用在哪；两个容易被问住的 n（41、99–132）；口径速查 |
| `CAMPAIGN-2026-09-20.md` | 本轮预注册 + 逐条对照 + 过程中的发现 |
| `paper/controls_table.py` | 从 `d17-*(+b)` 重建 `tab-controls`，缺任一层就拒绝出表 |
| `paper/decomp_tables.py` | 从 `d17-neutral(+b)` 重建 `tab-causal` / `tab-parperp` / `tab-geometry-tierA` |
| `whitebox/fetch_ta.sh` | 回收 e14 的逐层文件（以前每轮手动拉）；`--mirror` 从共享盘取最长副本 |
| `whitebox/progress.sh` | 每个作业一行，按它欠的题数/层数报进度 |

---

## 3. 本轮产生的 tag

密网格秩曲线：`tqa-rank-d1/d2`(99)、`tqa06-rank-d1/d2`(132)、`tqamis-rank-d1/d2`(115)、`mis-rank-hi`(221)。
负对照补层：`d17-shuffled-b`、`d17-corrupted-b`（各 14 层 × 358 题）。
位置阶梯：`tA-num-k32`、`tA-num-k48`、`tA-num-k61`（各 36 层 × 358 题）。

⚠ 结果只有本地一份（`.gitignore` 排除），共享盘 `ssd/.../wbout/` 上有镜像但要起机器才能读。
**仍然建议尽早打包备份。**

---

## 4. 正文表图 → 数据来源

见 [`EXPERIMENTS.md`](EXPERIMENTS.md) §2 的完整表。改完数据后必须重跑：
对应生成脚本 → `check_main_data.py` → `build.sh`。

---

## 5. 仍然不是「全量」/ 仍未做的部分

**上一份 §5 剩下的三项（都没做）**

1. **TheoremQA 三行**每 skill ≤4 题的抽样上限。严格全量需重跑三行的电池/秩/深度/敲除，约 **60 GPU·h**，收益 1–2%。
   （上限本身已在附录写明，所以这是「可以不做但要说」的那一类。）
4. **表 3 下半（问题依赖）只有第 8、16 两层**。补全 36 层 ≈ **64 GPU·h**；粗网格（0/4/12/20/28）≈ 6 GPU·h。
7. **逐层敲除只在各行受限题上做**（MedCalc 8B 134 题）。全部 466 题的逐层版 ≈ **45 GPU·h**。

**这一轮新暴露的两项（用户 2026-09-21 明确说先不要开跑，等他的新 idea）**

8. **自由作答下的接收方对照**：把 `tA-num-k*` 的 `--no-filler-receiver` 去掉重跑一条臂，
   看「无文档接收方 vs 错文档接收方」是否解释 .403 的天花板。约 **4 GPU·h**。
9. **真实材料上的题目 span 通道**：现有 MedCalc / TheoremQA 的窗口实验全部是 `--span skill`，
   **`--span task` 从没在真实材料上跑过**。`wb_spanpatch` 已原生支持，不需要新代码：

   ```
   qspan-mc8-<a..d>|wb_spanpatch|--model $B/models/Qwen3-8B --per-calc 20 --max-calcs 55 \
     --max-new 900 --matched --filler fixedskill --no-baselines --span task \
     --calcs 13,18,23,24,29,32,33,36,43,49,60,64,67,7 --layers <每 9 层一组>
   ```
   TheoremQA 同形，加 `--dataset theoremqa --cells data/cells/cells-tqa-qwen8b.json --min-group 1
   --per-calc 4 --max-calcs 400 --calcs <dep1-tqa8-a 的 75 个>`。
   两个任务各 36 层 ≈ **16–20 GPU·h**。跑完就能把附录 `fig:windows` / `tab:windows2` 那套
   「文档 span → 题目 span → 末位置」的接力故事从 Tier A 换到真实材料上。

**按设计不扫的自变量**（不算缺口，但要在正文说清楚）：图 1 与表 2 固定在层 8；
秩曲线固定在各模型的注入层；剂量曲线固定 α 网格。

---

## 6. 机器：已确认全部 STOPPED（2026-09-21 接手时核实，无需再处理）

2026-09-21 我为 §5 第 9 项准备实验时，对 **sra2 / sra4 / hsw / wb** 执行过
`inspire notebook start --no-wait`，随后用户叫停。**没有执行过 `qstart`，本地也没有守护进程，
所以即使起来了也没有任何作业在跑**。

**核实结果**：`inspire notebook list --workspace 可上网GPU资源` 显示 `可上网GPU资源` 下
11 台实例（`wt-gpu-wb/wb2/wb3/wb4`、`sra1-4`、`hsw/hsw2/hsw3`）**全部 STOPPED**。
那批 `start` 没有生效，不烧点券，**不需要执行任何停机操作**。
队列文件已 `git checkout` 还原成昨天那批**已完成**的作业，不会被误跑。

⚠ **原文对断连原因的归因是错的，已更正**：当时 `getaddrinfo ENOTFOUND qz.sii.edu.cn`
**不是** CLAUDE.md 记的「WSL DNS 走错网卡」，而是 **v2rayN 的 sing-box TUN 劫持了 53 端口**。
平台四个域名全是只有校园 DNS 才有记录的私网地址，走远程 DNS 必然 NXDOMAIN。
它**不会自恢复**，必须写 hosts 绕开 DNS（TUN 对私网 `10.0.0.0/8` 本来就直连，路由层没问题）。
完整的 IP 表、幂等脚本、WSL 侧补同步的做法、以及两个会导致误判的诊断陷阱，
已写进 CLAUDE.md 新增的「VPN 与平台内网域名」一节。**开着 VPN 排查平台连不上时先看那一节。**

同日的环境自检（§1 四条中的前三条）已全部跑过：`check_main_data.py` PASS 70201 checks、
`audit.py` ALL CHECKS PASSED、`build.sh` errors=none / undefined=0 / overfull=0 / 正文 10 页 / 全文 46 页。

**运维基础设施**（本地守护进程，**当前全部已停**，需要时再起）：

```bash
(nohup setsid ./whitebox/fleet.sh 600 >> logs/fleet.log 2>&1 </dev/null &)      # 空闲停机/掉线重拉/被平台停掉续跑
(nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 </dev/null &)  # 每 15 分钟回收，含 e14 逐层文件
```

**踩过的坑（本轮新增）**

- **两个 8B 的 `e14` 作业不能共用一张 4090**。捕获是每题 3 个 `36层 × k位 × 4096` 的张量，
  全程留在显存里：k=61 要 19 GB、k=32 要 10 GB，各自还要 16 GB 权重。**一台一个**。
- `fleet.sh` 的重启规则只看「不可达 + 平台显示 STOPPED + 不是我们停的」，**从不看队列内容**，
  所以上轮结束后它把三台机器重新拉起来跑已完成的队列。起机前先停 `fleet.sh`。
- 不用的机器的队列文件要**删掉**而不是清空——`hosts()` 是从队列文件推出主机列表的。
- `fetch_ta.sh` 里内层 `ssh` 必须带 `</dev/null`，否则它会把 while 循环的 stdin 吃掉，
  每轮只处理一个文件（本轮中过一次）。
- `inspire notebook connection refresh` 报 `Cached notebook target is unavailable` 时，
  按 CLAUDE.md 清三层缓存再刷新（本轮 hsw3 中过一次，清完一次就好）。

---

## 7. 环境变化

- **VPN 与平台共存已配好**（2026-09-21）：Windows hosts 里写了 4 条 `# BEGIN/END SII-INSPIRE`
  托管记录，开着 v2rayN TUN 也能用平台，其余流量照常走 VPN（实测 github / google 均 200）。
  IP 若变化，改 `C:\Users\12970\AppData\Local\Temp\sii-hosts.ps1` 提权重跑即可（幂等）。
  细节见 CLAUDE.md「VPN 与平台内网域名」一节。
- **GitHub 走 443**：2026-09-21 本机 22 端口被拒（`Connection closed by 20.205.243.166 port 22`），
  `~/.ssh/config` 已加 `Host github.com / HostName ssh.github.com / Port 443 / User git`，
  备份在 `~/.ssh/config.bak-20260921`。`git push` 现在直接可用。
- 桌面上的最新 PDF：`C:\Users\12970\Desktop\skillvector-2026-09-21.pdf`。

---

## 8. 下一步建议（按性价比排序）

1. **等用户的新 idea**。他 2026-09-21 明确说**先不要加新实验**——§5 第 8、9 项已经写好命令，
   但不要自行开跑。
2. **压回 9 页**（若要投 ICLR）：正文 10 页。可压：§4.8 Readout checks 整段移附录、
   §4.3 剂量细节缩一半。**不要**缩字号或图。
3. `IDEAS.md` **I7**（位置不可替代）的最小验证：一条还原 `position_ids` 的臂 + 一条换错文档接收方的臂，
   约 1 GPU·h，直接决定正文对这条结果的解释口径。它和 **I6**（整段平移 1 位即失效）是同一族问题的两端。
4. 把 192 MB+ 的结果打包备份到共享盘以外的地方。

---

## 9. Open Ideas

见 `IDEAS.md`：**I7**（本轮新增：补丁给再多位置也换不到文档自己的位置，位置身份假说 vs RoPE 相位假说可分离）、
I6（注入状态必须逐位归位）、I1/I2（作答形式与单位置补丁的混杂）、I4（行为断崖与机制量的非线性差）。
`CAMPAIGN-2026-09-20.md` §3 记着本轮过程中的反事实观察。
