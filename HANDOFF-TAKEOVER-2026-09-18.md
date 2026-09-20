# 接管文档：SkillVector（2026-09-18，写给新的 Claude Code 实例）

一口气读完就能接手。更早的细节在 [`HANDOFF-TAKEOVER-2026-09-16.md`](HANDOFF-TAKEOVER-2026-09-16.md)
（919 行，§12–§16 是这两天的全部过程），再早的在 `HANDOFF-whitebox.md`。
**本文件是最新的一份，与它冲突时以本文件为准。**

> **已被 [`HANDOFF-TAKEOVER-2026-09-20.md`](HANDOFF-TAKEOVER-2026-09-20.md) 取代**（09-18→09-20 的全量补跑、
> 逐层补齐与新实验都在那里）。本文件保留作历史记录。

> **09-18 起新一轮实验**（位置预算曲线 + 正文全量补跑 + Figure 2 / Table 1 修复）的调度与发现记录在
> [`CAMPAIGN-2026-09-18.md`](CAMPAIGN-2026-09-18.md)；§3 的两个待办已并入那里。

---

## 0. 一段话现状

论文 `paper/skillvector.tex` **可投**：9 页正文、0 error、0 undefined、0 overfull，
审计 `whitebox/analysis/audit.py` **385 条全部通过**。
MedCalc × Qwen3-8B 的**每一个正文表图都已改接全量数据**（467 题 / 48 calculator，
筛选后 135 / 14），主结论全部成立。
**16 个全量作业已全部跑完，结果都在本地**；11 台 GPU 实例被平台停了，**零损失**。
**还剩两个该补的作业**（见 §3），都是因为现值是 pre-fix 而不是因为样本量。

---

## 1. 先跑这三条确认环境没坏

```bash
cd ~/proj/agent-harness
python3 whitebox/analysis/audit.py        # 必须 ALL CHECKS PASSED（385 条）
./paper/build.sh                          # 必须 errors=none, undefined=0, overfull=0, main text pages=9
python3 whitebox/analysis/full_rerun_report.py   # 全量 vs 子集，逐臂
```

---

## 2. 论文现在是什么状态

### 2.1 正文表图的数据来源（全部已接全量）

| 显示项 | 生成脚本 | 现在用的 tag | n |
|---|---|---|---|
| 表 2 `tab-big40` | `paper/tables.py` | `full-battery-a/b` | 135 / 14 calc |
| 表 3 `tab-replication`（MedCalc×8B 行） | `paper/replication.py` | `full-battery-*`/`full-depth-*`/`full-rank-*`/`full-ko` | 135 (14) |
| 表 4 `tab-skill-content` | `paper/main_evidence.py` | `full-battery-a`+`full-quarters`；`full-dl-a/b` | 135；151 |
| 图 2 `fig-rank-medcalc` | `paper/figs.py` | `full-rank-a/b`+`full-battery-a` | 135 |
| 图 3 `fig-transfer-reading` | `paper/main_evidence.py` | `full-depth-*`/`full-ko`/`full-window` | 135 / 466 / 137 |

**改完图表后必须重跑三件事**：对应生成脚本 → `audit.py` → `build.sh`。
生成命令：

```bash
python3 paper/tables.py --medcalc howskill/results/p8-wb/fetched/by-host --out paper
MPLCONFIGDIR=/tmp/skillvector-mpl python3 paper/figs.py --medcalc howskill/results/p8-wb/fetched/by-host --out paper
cd paper && MPLCONFIGDIR=/tmp/skillvector-mpl python3 main_evidence.py && cd ..
python3 paper/replication.py
```

### 2.2 全量后变动最大的数字（都已写进正文并有 check）

| | 子集（旧） | 全量（现在） |
|---|---|---|
| 移植 `real_L8` | 0.87 | **0.89** [0.76, 0.97] |
| 秩曲线 k=4/16/32/64/128 | .13/.06/.13/.54/.77 | **.07/.05/.12/.63/.77** |
| k\* | 52 [43,72] | **47 [43,55]**（占宽度 1.1%） |
| 层窗口 8–11/12–15/14–19/16–35 | 1.00/0.96/**0.38**/0.11 | 0.91/0.74/**0.10**/0.10 |
| 敲除 @24/28/32 | .38/.75/.95 (n=40) | **.46/.79/.91** (n=466)，reading 0.70→**0.78** |
| 顺序（L16，skill-last vs first） | 0.85 vs 0.19 | **0.49 vs 0.06** |
| 接收方能解处的另一技能donor | 0.47 (n=24) | **0.17 (n=332)** vs 受限处 0.05 |

### 2.3 修掉的一个事实错误

正文原写塌陷在 "past layer 14"。**实际整个跌落在 12→13 的单层**，L13 此前从未测过。
L13 与 L14 在两种限制口径下都不可区分。`14–19` 窗口从 0.38 掉到 0.10 印证了这个边界。

---

## 3. 该补的两个作业（唯一的实验待办）

**不是因为样本量，是因为这两个数现在只有 pre-fix 的版本，而它们是论证支点。**

| 优先级 | 臂 | 正文位置 | 现值 | 为什么必须补 |
|---|---|---|---|---|
| **高** | **全层注入** | §5.5「Patching every layer gives $0.950$ recovery in a pre-fix run」 | 0.950，pre-fix，无 CI | 这是「过了 L14 失败的是某一深度的**交接**、不是机制本身」的**反事实支柱**，整个 §5.5 靠它 |
| **高** | **`normrecv`** | §5.4「matching each position to the receiver's norm leaves recovery at 1.06 versus 1.06 (pre-fix)」 | 1.06，pre-fix | 直接反驳「效应只是范数变大」 |
| 中（可选） | `dall` | §5.4「Averaging content across skills … recovers only 0.11」 | 0.11，pre-fix | 作用已由全量的 `dcross` .05 / `dfar` .05 / `dnear` .12 承担，补上更整齐 |

### 3.1 命令

机器**现在全部 STOPPED**，先按 §5 起两台，然后：

```bash
B=/inspire/ssd/project/project-public/czxs253130660
# A：doc-first 缺的两个臂（约 4 h）
./whitebox/launch.sh <host> full-extra wb_spanvec \
  "--model $B/models/Qwen3-8B --per-calc 20 --max-calcs 55 --max-new 900 \
   --mode decode --filler fixedskill --layers 8 --arms dall,normrecv"
# B：全层注入 = 覆盖全部层的窗口（约 2 h）
./whitebox/launch.sh <host> full-alllayers wb_spanpatch \
  "--model $B/models/Qwen3-8B --per-calc 20 --max-calcs 55 --max-new 900 \
   --matched --span skill --layers 8 --window 0:35"
```

**两者都不带 `--baselines`**，按 instance_id 与 `full-battery-a` 合并取基线
（`full_rerun_report.py` / `replication.py` 的 `load()` 就是这么合的）。

### 3.2 跑完之后

1. 用 `restrict(_by([...]))` + `_rho` 算出 `ok_dall_L8` / `ok_normrecv_L8` / `ok_real_w0_35`；
2. 改 §5.4 和 §5.5 的那三句，去掉 "pre-fix" 标注；
3. `audit.py` 里加 3 条 check；
4. `build.sh` 确认仍是 9 页。

### 3.3 如果决定不跑

现状可交付。但**建议把「全层注入 0.950」那句从正文移到附录**——
它在正文承担的论证分量与它的证据强度（单个 pre-fix 数、无 CI、无全量）不匹配。

---

## 4. 正文里**不需要**全量的部分（别浪费机器）

| 位置 | n | 理由 |
|---|---|---|
| 表 1 `tab-answer-format` | 120 | **Tier A 合成任务**，不是 MedCalc，没有「全量」概念 |
| 图 1 顶栏（最终位置探针） | 20，pre-fix | 该实验从未在修复后重跑；且与 `full-*` 接收方不同 |
| 图 1 底栏（span 注入开发集） | 16 | `figs.py` 的 `load_spanvec` **正确拒绝**合并不同接收方：`full-*` 用 `--filler fixedskill`，`spanvec-fs-*` 不是，强合会把针对 0.175 基线与 0.85 基线的臂画在同一轴上。**不要绕过这个检查。** |
| §5.3 两处 `n=16` | 16 | 故意留作 provenance，旁边就是全量数字 |
| 表 3 的 0.6B / Mistral / TheoremQA 行 | 各自 | 不同模型/任务，本次没重跑，各自 tag 自洽；表注已写明只有 MedCalc×8B 是全量 |

---

## 5. 机器：全部 STOPPED，要用先起

```bash
inspire notebook list --workspace 可上网GPU资源          # 11 台 wt-gpu-*，全 STOPPED
inspire notebook start wt-gpu-hsw --workspace 可上网GPU资源
inspire notebook connection refresh wt-gpu-hsw --workspace 可上网GPU资源   # 常要跑两次
ssh-keygen -R "[wt-gpu-hsw]:22222"
./whitebox/push_local.sh inspire-me-wt-gpu-hsw howskill whitebox
./whitebox/mirror_start.sh hsw                          # 结果镜像到共享盘
```

**新建实例还要手动把 ssh-config 追加进 `~/.ssh/config`**（平台只打印不写入）：
`inspire notebook ssh-config <name> --workspace 可上网GPU资源`。
刚起来的容器 20 s 超时不够，`push_local.sh` 会 `lost connection`，等一会重试即可。

### 5.1 常驻进程一律 `setsid`，**不要挂成 harness 后台任务**

harness 在内存压力下会杀掉自己的后台任务（实测 `free` 显示空闲 10 G 时也照杀），
而 `setsid` 脱离的守护进程不受影响。

```bash
(nohup setsid ./whitebox/watch.sh 600 467 3 >> logs/watch.log 2>&1 </dev/null &)
(nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 </dev/null &)
```

`watch.sh` 报警或全部完成时写 `logs/watch.alert`，定时检查读它即可。
**核查守护进程要看 ppid**（命令替换会产生同名瞬时子进程）：

```bash
ps -eo pid,ppid,args | awk '$3 ~ /bash$/ && $4 ~ /(autofetch|watch)\.sh$/ {print "pid="$1" ppid="$2" "$4}'
```

---

## 6. 数据：19 个结果文件，192 MB，**只有本地这一份**

`howskill/results/p8-wb/fetched/by-host/<host>/<tag>.jsonl`，被 `.gitignore` 排除，
远端 `/root` 已随停机清空，共享盘 `ssd/.../wbout/` 上还有一份镜像但要起机器才能读。

**全量作业（全部 467 行，`full-ko`/`full-window` 是 469，那两个模块题池不同）**：
`full-battery-a/b`、`full-rank-a/b`、`full-depth-a/b/c13/d`、`full-dose`、`full-quarters`、
`full-ko`、`full-window`、`full-dl-a/b`、`full-heads`、`pc-lpcot`、`heads-ko`、`heads-ko-rand`。

⚠ **建议尽早打包备份**（36 MB 时就提过，现在 192 MB）。

---

## 7. 这两天的检查工作与结论（PREREG 判定）

预注册写在 `HANDOFF-TAKEOVER-2026-09-16.md` §12.11，**在数据回来之前固化**。

### 7.1 P-A：定性成立，定量区间落空

预测 ρ(13) ∈ [0.28, 0.45]：per-item **0.32 命中**，per-calc **0.16 偏低出界**。
**prereg 的缺陷是我没预先指定限制口径**——如实记录，不要事后挑一个说命中。
定性核心「L13 属于 L14 那一档而不是 L12 那一档」在两种口径下都成立。

### 7.2 P-B：强烈成立

行为在 12→13 单层跌掉量程的 **61%**（per-calc），
机制代理 `closed@last` 同一步只跌 **14%**，比值 **4.2×**（预测 ≥2×）。

### 7.3 P-C：断崖**不是**评分阈值的产物

`wb_lpcot.py`，教师强制 gold 推理链、全程无解码阈值，n=442/48 calc：

| 区间 | L4→8 | L8→12 | **L12→13** | L13→14 | L14→16 |
|---|---|---|---|---|---|
| 每层跌幅占量程 | 0.8% | 3.7% | **26.8%** | 0.3% | 14.7% |

连续量在 12→13 也有单层突变（邻近区段的 7 倍）。行为（61%）比它陡 2.3×，
所以**评分阈值放大了断崖但没有制造它**。跌幅在四个四分位上均匀（.20/.26/.31/.21），
**不集中在答案处**——与评分阈值签名相反。

**废弃的指标要记住**：`lp_ans`（ANSWER 段）无用，分母 (gold−recv) 中位数仅 0.0014、
59% 的题 |分母|<0.01。教师强制完整推理后任何条件都能预测最后那个数。

### 7.4 P3 头敲除：成立，但效应只比随机多 0.15

名单在 23 个 calculator 上按 `‖dg‖/‖resid‖` 排序，**在留出的 23 个上测试**（非循环）：

| 留出测试集 n=195 / 23 calc | 准确率 | 相对 gold 保留 |
|---|---|---|
| 同层随机 32 头 | 0.764 | +0.768 |
| 定向敲除 32 个读者头 | 0.610 | +0.613 |
| **配对差** | **+0.154 [0.061, 0.251]** | McNemar 39:9, **p<0.0001** |

**必须同时说**：随机 32 头也削掉 23%，32 个头（2.8%）只移除 39%。
读出是**弥散但有结构**的，没有可命名的读者头集合。

### 7.5 头读出图（`full-heads`，n=455/47 calc）

- 归一化后读出集中在 **L12–21，峰值 L18**（原始 `‖dg‖` 的深层主导是残差范数增长的假象）。
- **top 1% 的头（11/1152）只占 10.5%，top 5% 占 31.1%**。
- `recovery`（下游读出）全程 **0.86–0.99**，连 L24 都是。
- 注意力 enrichment 0.4–1.2x（span 占 prompt 51.4%），**注意力质量本身不是探测器**。
- ⚠ **455 而非 467**：12 题在 span 构造上被跳过，**原因未查，写进论文前要查**。

### 7.6 一条构造性论证（附录里保留的、最硬的一段）

注入 `h_gold` 到 L16 之后，span 位置在 L17+ 只 attend 到两个 run 完全相同的前缀、
和同样被改写成 gold 的更早 span 位置 → **span 自己的状态从 L17 起和 gold 逐比特相同**。
内容既在、也确实被下游读走（`recovery` 0.86–0.99），行为却塌。
→ 丢的只能是 L≤16 期间消费位置对 span 的读。**这直接证伪「深层装不下」的解释。**

---

## 8. 新数据与论文主线的关系（我的判断）

- **紧密，已写进正文**：全量重跑本身、L13 与断崖定位（修了事实错误）、k\*/窗口/敲除/顺序的数值更新。
- **中等，是主线的防守，放附录**：**P-C**。不进论文的话，§5.5 的 "falls off a cliff" 是可攻击的。
- **松，建议不进这篇**：**头读出与敲除**。结论偏负面（弥散），概念上不新
  （Retrieval Heads ICLR 2025、ReDeEP ICLR 2025、Geva EMNLP 2023 已覆盖「哪些头读上下文」），
  且没有改变主线任何数字。现在放在附录 `app:fullscale` 作为「我们查过读者侧」。
  唯一真正连回主线的是 §7.6 那条构造性论证。

⚠ **真正的新问题不在这篇里**（已记 `IDEAS.md` I4 + 当日修正段）：
行为在 12→13 跌 61% 量程，而所有机制量（`closed@last` 14%、连续 q 27%）都平缓得多。
**存在一个现有头级读出账本预测不出的阈值非线性**，Retrieval Heads / ReDeEP / Geva 那条线都没碰。
最小验证：跨模型看 `closed@last` 与 ρ 的断崖层是否都对得上（±2 层）。

---

## 9. 新代码（这两天写的，都在仓库里）

| 文件 | 作用 |
|---|---|
| `howskill/howskill/wb_heads.py` | 头级读出图（`--mode map`）与定向敲除（`--mode knockout`）。**`--attn eager` 强制**，sdpa 返回 `attn_weights=None` 会让所有数静默变 0；内置仪器自检（重建 self_attn 输出，相对误差 3.06e-03） |
| `howskill/howskill/wb_lpcot.py` | P-C 的连续因变量：教师强制 gold 推理链打分 |
| `whitebox/analysis/head_map.py` | 读头图，**两遍流式**（147 MB 文件整读会 OOM，见 §10） |
| `whitebox/analysis/full_rerun_report.py` | 全量 vs 子集逐臂对照 |
| `whitebox/full-rerun.sh` | 作业表 + `plan/push/launch/status` |
| `whitebox/mirror.sh` / `mirror_start.sh` | 每台机器常驻，3 分钟把结果镜像到共享盘 |
| `whitebox/watch.sh` | 事件驱动看门狗，异常即退出并写 `logs/watch.alert` |

---

## 10. 这两天踩的坑（别再踩）

1. **`pkill -f 'xxx.sh'` / `pgrep -f` 会匹配到自己所在的 ssh/bash 命令行**（命令行里含该字符串），
   结果把自己杀掉。中过两次（一次杀了 mirror 启动，一次杀了 autofetch + 自己的 shell）。
   一律锚定：`pkill -f '^bash /root/mirror.sh'`，或
   `ps -eo pid,args | awk '$2 ~ /bash$/ && $3 ~ /autofetch\.sh$/ {print $1}'`。
2. **不要把监控挂成 harness 后台任务**（见 §5.1）。
3. **不要整读全量头图**（147 MB 嵌套 list → 几 GB，把看门狗挤死）。用改后的 `head_map.py`（峰值 18 MB）。
4. **冒烟别用「救回题最多的 calculator」**——救回题数与文档长度相关，会系统性低估工期 3–4 倍。
   实测 ~15 s/解码，不是冒烟外推的 8.5 s。
5. **全量是 467 题 / 48 calculator，不是 469/49**（旧手册写错了，看门狗阈值被它卡过）。
6. **平台会一次性停掉所有实例**（09-13、09-17 各一次）。镜像 + autofetch 是为此存在的，这次零损失。
7. `launch.sh` 拒绝复用已有 tag（防止 relaunch 截断已完成的运行）——要重跑就换 tag。

---

## 11. 仓库状态

`master` 分支，**79 个文件未提交**（整个 `paper/` 的生成产物、新脚本、新文档都在里面）。
`howskill/results/` 被 `.gitignore` 排除。
要提交的话按主题分几个 commit：(1) 新实验模块，(2) 分析脚本与运维脚本，(3) 论文与审计，(4) 文档。
