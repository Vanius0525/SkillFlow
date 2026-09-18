# 接管文档：SkillVector（2026-09-16 14:10，写给新的 Claude Code 实例）

> **已过时（2026-09-18）**：最新的接管文档是 [`HANDOFF-TAKEOVER-2026-09-18.md`](HANDOFF-TAKEOVER-2026-09-18.md)。
> 本文件保留为过程记录（§12–§16 是 09-16/17 两天的全部实验与判定），
> 与新文件冲突时以新文件为准。


> （原文）`HANDOFF-TAKEOVER-2026-09-14.md` 已过时（里面写的 4 个作业早已跑完、机器已停），只保留作历史记录。
> 读这一份 + `HANDOFF-whitebox.md` 的 §46–§48（过程日志，数字最全）就够了。两者冲突以本文件为准，新进展追加到 §47。

---

## 0. 一段话现状

论文 `paper/skillvector.tex`（ICLR 2027 格式，正文 **9 页零余量**，全文 41 页）已经是完整可投状态：编译 0 error / 0 未定义引用 / 0 overfull，审计脚本 `whitebox/analysis/audit.py` **309 条复算全部通过**。所有实验已跑完，**10 台 GPU 实例全部 STOPPED**，没有任何后台任务在跑。剩下的是可选的补强实验、AI use statement，以及如果要投稿的收尾。

论文的四条核心结论、两条收窄结论、四条已撤回声明，见下面 §3。

---

## 1. 交付物与链接

| 东西 | 位置 |
|---|---|
| **论文源码 / PDF** | `paper/skillvector.tex` / `paper/skillvector.pdf`；编译 `./paper/build.sh`（调 Windows MiKTeX，产物同时拷到 `C:\Users\12970\Desktop\ICLR2027\build-skillvector\`） |
| **Overleaf 上传包** | `paper/overleaf-skillvector.zip`（桌面同名 `SkillVector-overleaf.zip`）。26 个文件，已在干净目录里用 MiKTeX 验证过：41 页、0 错误。主文件 `skillvector.tex`，编译器 pdfLaTeX |
| **组会讲稿（artifact）** | **https://claude.ai/code/artifact/82821a75-bc3f-4b1c-b304-6a7e7c93cc8b** （中文，含 6 张可悬停的 SVG 图）。**源码在仓库里：`HOWSKILLWORK/groupmeeting-2026-09-14.html`** |
| **中文全译稿** | `HOWSKILLWORK/PAPER-ZH-2026-09-14.md`（桌面 `SkillVector-全文中文译稿.md`）：正文 + 附录全文 + 术语表，约 14 万字符 |
| **审计脚本** | `python3 whitebox/analysis/audit.py` —— 改任何数字前后都要跑，必须 `ALL CHECKS PASSED` |
| **表 / 图生成** | `paper/tables.py`、`paper/figs.py`、`paper/replication.py`（正文表 3）、`paper/replication_full.py`（附录完整曲线表） |
| **原始结果** | `howskill/results/p8-wb/fetched/by-host/<host>/<tag>.jsonl`（145 个文件，36 MB） |
| **修复前数据冻结快照** | `howskill/results/p8-wb/snapshots/fetched-20260913_2324/` |
| **行为筛选 cells** | `howskill/data/cells.json`（MedCalc 主用）、`howskill/data/cells-1100.json`、`howskill/data/cells/cells-<ds>-<model>.json`（6 份） |
| **SRA-Bench 数据** | `howskill/data/sra/`（theoremqa / logicbench / champ 的 instances、skills、pairs、meta.json） |
| 论文快照 | `paper/.snapshots/`（大改前存一份，命名带日期） |

**要改 artifact 时**：在新会话里必须带上 `url` 参数（`Artifact` 工具，`url` = 上面那个链接 + `file_path` = 仓库里的 HTML），否则会新建一个副本而不是更新它。

**已过时、不要再引用的桌面文件**：`SkillVector-图表逐条解释.md`、`SkillVector-审稿意见.md`（都是 09-14 00:30 版，数字是修复前的）、`SkillVector-接管文档-2026-09-14.md`。

---

## 2. 论文讲什么（30 秒版）

给模型一段技能文档，准确率上升。这份提升在模型内部走哪条路？

1. **传统的「提示末位置」补丁搬运的是模型的决策，不是文档内容。** 只改答案格式：一 token 答案恢复 1.000、短数字 0.304、思维链 0.000。
2. **真正携带作用的是文档自己占的那段 token。** 接收方 prompt 用一份固定的无关文档逐 token 替换金标文档（长度一致、旋转相位对齐），把供体的片段状态写进去——因为接收方本身持有文档，这一步**在数学上等于** `h_recv + d`，即 α=1 的内容注入分布在 m 个位置上。于是剂量、迁移、截秩这些向量操作都能在真实文档上做。ρ=0.87，各对照 ≤0.10。
3. **充分性与必要性在深度上分离**：单层交接在 0.2–0.4 相对深度处关闭（窗口实验证明是「通道关闭」而不是「一层不够」），而对文档的注意力到 0.56–0.88 深度仍然必要。
4. **秩截断**：需要谱顶部约 50 个方向，底部同样多方向无效。

---

## 3. 结论的当前状态（改论文时以这个为准）

**成立（2 任务 × 3 模型）**
- 末位置搬运决策，容量由答案长度决定。
- 文档作用经由文档自身 token 片段传递；ρ 0.74–0.94，所有跑过的对照 ≤0.27。
- 充分性 / 必要性的深度分离，在每个组合上都成立。
- 作用需要谱顶部数十个方向；预注册的「按宽度成比例」预测（0.6B 应在 k≈12）在两个任务上都被否定。

**收窄**
- **k\* 与交接深度只在同一模型家族内稳定**：Qwen 0.6B/8B 为 40/52（MedCalc）、52/50（TheoremQA），悬崖都在 0.33–0.43；同宽度的 Mistral-7B 是 64–84，悬崖 0.19–0.22。跨家族差异在 MedCalc 上显著（差值 95% 区间 [3, 48]）、TheoremQA 上不显著（[−7, 33]），而且 Mistral 的 k=128 离不截断还远（0.71 对 0.92），k\* 被网格截断。**不要再写「k\* 是文档的性质」。**
- 「内容成分是技能而非任务」只在第 8 层干净成立；第 16 层另一实例的向量只恢复 0.48（本实例 0.85）。

**已撤回（不要再写进任何材料）**
- 「例题贡献约为公式的一半」（修复前 0.44 → 修复后 0.06 / 40 calc 0.12）。
- 「交接死亡处表示被压缩（PR 64→17）」——是超大激活伪影。
- 「实例特有部分在任何深度都不起作用」。
- 「按接收方范数缩放只保留 0.73」——那个臂是 `realm`，含义是别的东西，见 §7 第 1 条。

---

## 4. 实验清单与覆盖率（审稿人会问的第一个问题）

**主结果不是全量。** MedCalc × Qwen3-8B 的救回格一共 470 道题、分布在 50 个计算器上（55 个计算器里有 5 个没有救回题）：

| 运行 tag | 用途 | 覆盖 |
|---|---|---|
| `fixmask-big40` | **正文表 2** 电池 | 前 40 个计算器（按救回题数排序）× 每个随机 4 题 = **160 / 470**；限制后 15 calc / 60 题，而这 15 个 calc 实际有 182 道救回题 |
| `big40-depth` | 充分性曲线 | 120 题 / 40 calc |
| `rank40-l8` | 秩曲线 | 160 题 / 40 calc |
| `ko-8b-fast` | 注意力屏蔽 | 40 题 / 20 calc |
| `fixmask-dev10` | 剂量 + 图 1 电池 | 40 题 / 10 calc（限制后 n=16 / 4 calc） |
| `fixmask-quarters40-q0..q3` | 文档四段 | 160 题 / 40 calc（基线并自 `fixmask-big40`） |
| `fixmask-dl` | 文档在后 | 40 题 / 10 calc（限制后 28 / 7） |
| `fixmask-window` | 层窗口 | 80 题 / 20 calc |
| `tqa-span` / `tqa-rank` / `tqa-depth` / `tqa-ko` | TheoremQA × Qwen3-8B | 168 / 171，**基本全量** |
| `tqamis-*` | TheoremQA × Mistral | 142 / 143，**基本全量** |
| `mis3-big40-L4` / `mis2-depth*` / `mis2-ko-b` / `mis3-rank-L4` | MedCalc × Mistral | 141 / 228 |
| `fixmask-lad06-rank` / `tqa06-*` | Qwen3-0.6B | 234 / 168 行 |

限制集的口径：**只保留「接收方（错误文档）在该组内一题都做不对」的计算器**。条件加在对照上、不加在处理臂上。TheoremQA 的技能大多只服务一道题，那里退化为逐题限制——修复后接收方是确定性的，所以这样做站得住。

---

## 5. 机器与平台

**状态（09-16 14:25）**：10 台 GPU 实例在 14:15 被我**重新 start 了，当时全部处于 PENDING（排队中）**，因为原计划要跑 §11 的全量补跑；用户随后决定「先不跑」，所以**作业一个都没派，实例就停在那里**。
- 如果新对话马上要跑 §11：直接等它们变 RUNNING 即可，省掉排队时间。
- 如果短期内不跑：`for n in hsw hsw2 hsw3 wb wb2 wb3 sra1 sra2 sra3 sra4; do inspire notebook stop wt-gpu-$n --workspace 可上网GPU资源; done`（每台 0.33 点券/小时，预算 998M，成本可忽略，但空转没意义）。
- `wt-dev-cpu`（CPU 盒子）一直 **RUNNING**。

停机会清空远端 `/root`，但**所有结果 jsonl 早已取回本地**（audit 309 条全通过就是证明）；09-14 那次停机丢的只有 6 台上的运行日志，纯溯源材料。

**要重新开工，每台按这四步**（平台语义见 `~/.claude/CLAUDE.md`）：

```bash
inspire notebook start wt-gpu-hsw --workspace 可上网GPU资源
inspire notebook connection refresh wt-gpu-hsw --workspace 可上网GPU资源   # 刚起来常要跑两次
ssh-keygen -R "[wt-gpu-hsw]:22222"        # 新容器 = 新主机密钥
./whitebox/push_local.sh inspire-me-wt-gpu-hsw howskill   # 推代码到容器自己的盘
```

`push_local.sh` 把代码推到容器的 `/root/wb`（overlay 盘，765 GB 空闲），**不是**共享盘——因为两个共享 fileset 都在配额上，往那里写会得到截断的文件。代价是停机即丢，所以结果必须及时取回（`fetch_local.sh` / `autofetch.sh` 就是为此存在的）。`launch.sh` 的 `<host>` 用短名（`hsw`、`wb3`），`push_local.sh` 用完整 ssh 别名。

同名重建后如果连不上，还要清三层缓存：`notebook connection target forget`、`notebook connection forget`、`cache clear --resource notebook --yes`。

**共享盘**（重启不丢）：
- 代码与 venv 在 `/inspire/ssd/project/project-public/czxs253130660/`：`venvs/whitebox`（`--system-site-packages`，已装 transformers 4.57.6 / accelerate / sentencepiece / latex2sympy2）、`models/Qwen3-1.7B`、`models/Qwen3-8B`。
- **hdd 个人配额已满**（约 370 MB），凡是会长大的东西都放 ssd。`df` 看到的余量不是配额。
- 装包走 SII 内部源，不要用公网 pypi。

**派作业**：一律用 `./whitebox/launch.sh <host> <新tag> <module> "<args>"`（会下发脚本文件、拒绝复用已有 tag）。续跑用 `RESUME=1 ... --resume`。

**取结果**：`whitebox/autofetch.sh`（15 分钟一轮，只在「本地是远端的字节前缀」时覆盖）；现在是停止状态，有新作业时再起：

```bash
cd ~/proj/agent-harness && (nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 < /dev/null &)
```

---

## 6. 验收与复现流程

```bash
cd ~/proj/agent-harness
python3 whitebox/analysis/audit.py                      # 309 条，必须 ALL CHECKS PASSED
./paper/build.sh                                        # 看末尾：errors / undefined / overfull / main text pages(=9)
python3 paper/replication.py                            # 正文表 3 → paper/tab-replication.tex
python3 paper/replication_full.py                       # 附录完整曲线 → paper/tab-replication-full.tex
python3 whitebox/analysis/span_summary.py <jsonl...>    # 每个臂的 ρ + 按组 bootstrap；knockout 文件自动识别
python3 whitebox/analysis/span_summary.py --merge a.jsonl b.jsonl   # 按 instance_id 合并（无基线的分片作业要用）
python3 whitebox/analysis/span_summary.py --per-item <jsonl>        # 逐题限制（TheoremQA / LogicBench 用）
```

**规矩：任何写进论文的新数字都要在 `audit.py` 里加一条 check。** 这个脚本是独立于出表代码的第二条计算路径，今天就是靠它查出了好几处错误。

---

## 7. 必须知道的坑

1. **`realm` 臂的含义**：它是「本文档的 d 只写在与另一技能文档共享的前缀上」，是迁移臂 `dcross` 的**位置配对对照**；「按接收方范数缩放」是另一个臂 `normrecv`。`tables.py` 曾把 realm 标成范数缩放，导致正文写错过一次。现在标签已改对，但看老输出、老图时要当心。
2. **`\input{tab-battery}` 类的陷阱**：`paper/build.sh` 把文件拷到 Windows 暂存目录再编译。曾经 `paper/` 里根本没有 `tab-battery.tex`，靠暂存目录里的旧副本编译通过，PDF 印的是错表，而 Overleaf 上会直接失败。现在 build.sh 每次编译前会清掉暂存目录里的 `tab-*.tex` / `fig-*.pdf`。**加了新的 `\input` 之后，务必确认 `paper/` 下真的有那个文件。**
3. **`pkill -f` / `pgrep -f` 会匹配到自己的命令行**：ssh 远端命令里出现 `out/<tag>.jsonl` 这样的字面量，就会把执行命令的 shell 自己杀掉。停远端进程用带方括号的模式，且同一条命令里不要再出现该路径。
4. **只对部分题有定义的臂**（如 `dnear` 只对有同家族邻居的计算器有定义）：分母只能用带该键的行。`span_summary.py` 已修，`tables.py` / `audit.py` 本来就对。
5. **k\* 的定义**（预注册）：取 k=16 到**网格内最大值**这段范围的一半，在 log₂k 上插值。注意上锚点不是不截断移植，所以当 k=128 还没饱和时（Mistral），k\* 是被网格压低的。
6. **Mistral**：注入层必须用 L4（它的悬崖在 L5–L7，L7 已经在衰减区）；对话模板没有 system 角色，系统文本并进 user 轮。
7. **TheoremQA 评分**依赖 `latex2sympy2`；官方评分器不解析方括号形式的列表答案，这是上游行为，保持原样。
8. **行为筛选（batch）与因果运行（batch-1）的基线约有 5% 不一致**：cells 只用来选题，所有报告数字都读 span 运行自己的 batch-1 基线。
9. **修复前 / 修复后**：attention mask kernel 故障让零臂在 Qwen3-8B 上改变 6.1% 的答案。附录 C.3 最后一段列了「哪些结果重跑过、哪些仍是修复前」，改论文时先看那一段。
10. **WSL vs Windows**：开发在 WSL（ssh 有连接复用、输出干净、无尾部 `\r`）。Windows 侧 `inspire notebook exec` 会给命令追加 `\r`，且 OpenSSH 不支持连接复用。

---

## 8. 还没做的事

**A. 全量补跑 —— 用户已批准范围，方案与脚本就绪，尚未启动。执行手册见 §11。**

**B. 其他值得补的实验**（按性价比排序，详见 artifact 的「风险与待办」一节和 `IDEAS.md`）
1. 修复后重跑范数臂 `normrecv` 与第 12/16 层秩截断（目前论文里这几处仍是修复前）。
2. 秩网格扩到 256 / 512，让 Mistral 饱和，k\* 才有可比性。
3. 注意力头层面追踪第 12–16 层谁在读文档片段——交接为什么关闭，目前没有机制解释，这是审稿人最会问的。
4. TheoremQA 上从第 0 层屏蔽仍保留 0.31（MedCalc 只有 0.12），未解释。加一个「删除文档 + 位置补齐」的对照能把「屏蔽 ≠ 删除」和「逐题选择效应」分开。
5. 剂量和 doc-last 在 40 calc 上重跑（现在只有 n=16 / 28）。

**C. 投稿合规**：**AI use statement 还没写**，ICLR 2027 强制要求，不写有 desk reject 风险。

**D. 仍然只有 HANDOFF 记录、没有 audit check 的正文数字**（都是修复前、合成任务层的，方向上不影响主结论）：答案 token 数 36/55/29、自由作答 0.268/0.018、最后 k 个位置 0.286/0.286/0.554、两台机器 360 单元一致、kernel 差 1.2%/25%、Qwen3-1.7B 救回 8–11%、错误文档对照 0.025/0.150–0.250、强制 `ANSWER:` 提示 +0.60 nat、合成层几何表。

---

## 9. 文档地图

| 文件 | 里面有什么 |
|---|---|
| **本文件** | 当前状态、交付物、机器、流程、坑、待办 |
| `HANDOFF-whitebox.md` | 全部过程日志（43 万字符）。**§46** 完整性检查、**§47** 09-14 起逐小时实验日志（数字最全）、**§48** 接管记录 |
| `HOWSKILLWORK/PAPER-ZH-2026-09-14.md` | 论文中文全译稿 + 术语表 |
| `HOWSKILLWORK/groupmeeting-2026-09-14.html` | 组会讲稿源码（对应上面的 artifact 链接） |
| `IDEAS.md` | 跑题但值得单独立项的想法 |
| `HOWSKILLWORK/LITERATURE-2026-09-12.md` | 文献调研（标题 + arXiv id + 一句话结论 + 与本项目的关系） |
| `HOWSKILLWORK/PREREG-ladder.md` | 模型阶梯的预注册（k\* 两个假设就是在这里登记的） |
| `HOWSKILLWORK/PAPER-THREAD.md` / `STORYLINE-v3.md` | 论文叙事的演变 |
| `HOWSKILLWORK/REVIEW-2026-09-14.md`、`FIGURES-EXPLAINED.md` | **已过时**（修复前数字），要用先按当前论文重写 |

---

## 10. 仓库状态

`master` 分支，**11 个改动文件 + 60 个未跟踪文件全部未提交**（`paper/` 整个目录、`whitebox/` 的新脚本、`howskill/` 的新模块、各种结果和文档）。用户没要求提交过，所以我一直没动 git。**接手后如果要提交，先跟用户确认**；`howskill/results/` 已被 `.gitignore` 排除，结果数据不会进仓库（也就是说，那 36 MB 原始结果只存在于本地磁盘，没有第二份备份）。

---

## 11. 全量补跑执行手册（用户已批准，**尚未启动**）

### 11.1 为什么要跑

正文里 MedCalc × Qwen3-8B 的每一张图表，用的都是「按救回题数排序取前 40 个计算器 × 每个随机 4 题」的子集：**160 / 470 道救回题**，限制后只剩 15 个计算器、60 题。审稿人第一个会问的就是这个。用户 09-16 的指示：**表 2、秩曲线，以及其他「正文里有图表但没跑全量」的实验，全部补成全量。**

全量 = `--per-calc 20 --max-calcs 55`，实测取到 **469 题 / 49 个计算器**（默认 `--min-group 2` 会丢掉唯一只有 1 道救回题的那个计算器；要那一题就加 `--min-group 1`，代价是同计算器供体臂在该组上无定义）。

### 11.2 作业表

全部定义在 **`whitebox/full-rerun.sh`** 里，四个子命令：`plan` / `push` / `launch [tag...]` / `status`。

| 机器 | tag | 模块 | 补的是正文哪张图表 |
|---|---|---|---|
| hsw | `full-battery-a` | wb_spanvec | **表 2** 电池：`real,realm,a0.5,dnear,dfar` + `--baselines` |
| hsw2 | `full-battery-b` | wb_spanvec | 表 2 其余臂：`dshuf,drand,dcross` |
| hsw3 | `full-rank-a` | wb_spanvec | **图 2** 秩曲线：`rank4,rank16,rank32` |
| wb | `full-rank-b` | wb_spanvec | 图 2 续：`rank64,rank128,rank16lo,rank64lo` |
| wb2 | `full-depth-a` | wb_spanvec | **§5.1 充分性**：L0,4,8 |
| wb3 | `full-depth-b` | wb_spanvec | §5.1 续：L12,14,15,16,20 |
| sra1 | `full-dose` | wb_spanvec | **图 1 下半 + §4 剂量**：α 0.4/0.5/0.55/0.6/0.7/2 |
| sra2 | `full-quarters` | wb_spanvec | **§6 文档四段**：q0–q3 |
| sra3 | `full-ko` | wb_knockout | **§5.1 必要性**：`--sweep layers --layer-stride 4` |
| sra4 | `full-window` | wb_spanpatch | **§5.1 层窗口**：8:11 / 12:15 / 14:19 / 16:35 + L16 |
| 排队 | `full-dl-a` / `-b` | wb_spanvec | **§6 文档在后**：`--doc-last --layers 8,16` |

两个设计决定，别改：

1. **只按「臂」拆分，绝不按题拆分。** 每次运行都从自己的题池重新构造供体池（`cross` = 下一个计算器的均值、`near/far` = 同/异家族均值、`dall` = 全体均值）。同一批题、不同臂的两个作业可以按 instance_id 合并；不同批题的两个作业**不能**逐臂比较。每对里的 `-a` 带 `--baselines`，`-b` 合并时复用。
2. **新 tag 一律 `full-` 前缀。** `launch.sh` 拒绝复用 tag，旧的 `fixmask-*` / `big40-*` / `rank40-l8` 原样留着——论文现在引用的就是它们，补跑失败也不影响现状。

### 11.3 执行步骤

```bash
cd ~/proj/agent-harness
inspire notebook list --workspace 可上网GPU资源          # 先确认 10 台都 RUNNING
for n in hsw hsw2 hsw3 wb wb2 wb3 sra1 sra2 sra3 sra4; do
  inspire notebook connection refresh wt-gpu-$n --workspace 可上网GPU资源   # 常要跑两次
  ssh-keygen -R "[wt-gpu-$n]:22222"
done
./whitebox/full-rerun.sh push                           # 推代码到 10 台的 /root/wb
```

**先冒烟，再全量**（这一步别省）：

```bash
./whitebox/launch.sh hsw smoke-full wb_spanvec \
  "--model /inspire/ssd/project/project-public/czxs253130660/models/Qwen3-8B \
   --per-calc 4 --max-calcs 6 --max-new 900 --mode decode --filler fixedskill \
   --layers 8 --arms real,realm --baselines"
```
要确认三件事：① 捕获阶段的内存；② 每次解码的实际秒数（用日志两行之间的时间差）；③ 结果格式没变。**然后用实测速度重算工期**：单机墙钟 ≈ 469 × (臂数 + 1 个零臂 + 3 条基线) × T解码。按 09-14 实测的 T≈11 s，`full-battery-a`（5 臂）约 13 小时，最短的 `full-quarters` 约 7 小时。**如果算下来太久，就把臂再拆到更多机器上**——拆臂是安全的，拆题不是。

```bash
./whitebox/full-rerun.sh launch                          # 派 10 个作业
cd ~/proj/agent-harness && (nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 < /dev/null &)
./whitebox/full-rerun.sh status                          # 随时看进度
```

腾出机器后再派 `full-dl-a` / `full-dl-b`（表里 host 写的是 `QUEUE`，手动改成空出来的机器名再 `launch`）。

### 11.4 已知风险

- **内存，不是显存。** 捕获阶段把每题每层的 `d` 留在 CPU 内存里，约 7.4 MB /题/层。469 题 × 1 层 ≈ 3.4 GB（电池、秩、剂量、四段都是单层，没问题）；`full-depth-b` 有 5 层 ≈ 17 GB，**这是唯一有风险的作业**。冒烟时量一下峰值；不够就按层再拆成两个作业。
- **限制集会变严。** 每个计算器从 4 题变成最多 20 题后，「接收方一题都做不对」更难满足，保留下来的计算器可能少于 15 个。所以分析脚本**同时输出两种口径**（见 11.5）。如果两种口径结论不一致，必须在正文里写明白，不能挑一个报。
- **`dnear` 仍然只对有同家族邻居的计算器有定义**，分母只能用带该键的行。
- 平台可能回收空闲实例；`/root` 停机即清空，所以 autofetch 要一直开着。

### 11.5 跑完之后要做什么

```bash
python3 whitebox/analysis/full_rerun_report.py           # 8 个实验，全量 vs 子集，两种限制口径
python3 whitebox/analysis/full_rerun_report.py battery   # 也可以只看一个
```

脚本已经写好（`whitebox/analysis/full_rerun_report.py`）：按 instance_id 合并 `-a`/`-b` 分片，对每个臂给出 ρ + 按计算器 bootstrap 的 95% 区间，并列出论文现在印的子集数字，好一眼看出漂移。

然后按顺序：

1. **先看结论有没有变。** 重点盯四个：移植 ρ（现在 0.87）、各对照是否仍 ≤0.10、公式段是否仍显著高于其余三段、秩曲线拐点 k\*（现在 52）。
2. **改出表图的脚本**，把 `paper/tables.py`、`paper/figs.py`、`paper/replication.py` 里的 tag 从旧的换成 `full-*`，重新生成 `tab-big40` / `tab-battery-dep` / `fig-channels` / `fig-rank` / `tab-replication`。
3. **正文里所有 n 都要改**：60 题 / 15 个计算器 → 新的数字；§4、§5.1、§5.2、§6、Limitations「40 个计算器…60 题」那句、表 2 和图 1/2 的图注。
4. **`whitebox/analysis/audit.py` 里加新 check**（旧的 `fixmask-big40` 那批 check 保留，它们对应的是仍然存在的旧运行），跑到 `ALL CHECKS PASSED`。
5. `./paper/build.sh`，确认仍是 **9 页**、0 error、0 undefined。正文零余量，数字变长可能会挤出一行，必要时在 §5.1 或 §6 删一句。
6. 把「表 2 是子集」这条从 §4 覆盖率表和 artifact 的「风险与待办」里划掉，同时更新组会讲稿 artifact（记得带 `url`）。

### 11.6 如果决定不跑

现状完全可交付：论文 9 页、审计 309 条通过、Overleaf 包已验证。子集的事在 §4 覆盖率表里写清楚了，投稿时在 Limitations 里补一句「主结果在 40 个计算器的 160 道救回题上」即可——现在正文说的是「forty calculators … 60 items」，没有夸大，只是没说它是 470 里的 160。

---

## 12. 注意力头实验（新，2026-09-16 14:5x 起）

### 12.1 触发它的观察

正文 §5.1 的深度扫描：把文档的内容向量写进它自己的 token span，**L≤12 恢复全部行为效果**
（ρ=1.00/1.06/1.03/0.81 @ L0/4/8/12），**过了 L14 塌掉**（ρ=0.14 @ L15、L16；0.00 @ L24、L30），
**但同时写进所有层又回到 ρ=1.00**。所以失败的是「某一个深度上的交接」，不是机制本身。
论文没有说这个「交接」是什么——这是审稿人会追的洞。

### 12.2 假设与可证伪的预测

**H1（读出窗口）**：span 里的内容是被一小批集中在某个层带的注意力头读走的；
注入只有落在这些「读者头」的**上游**才有用。

| | 预测 | 若失败说明什么 |
|---|---|---|
| P1 | 读出质量按层**集中**，不是均匀铺开 | 平的 → 没有「带」可言，H1 直接死 |
| P2 | 注入层 L0 的下游读出恢复率随 L0 的塌陷位置 ≈ 行为 ρ 的塌陷位置 | 不对齐 → 交接不是注意力读出 |
| P3 | 定向敲掉 top-k 读者头 > 敲掉同层随机 k 头 | 无差 → ‖dg‖ 排出来的头不是因果上重要的头 |

**站着的对立假设**：rank 塌缩（span 的 participation ratio 从 L8 的 ~95 掉到 L16 的 ~17）。
P1/P2 若失败就回到它。两者也可能都对（读者头少 → 有效维度低）。

### 12.3 测什么

`howskill/howskill/wb_heads.py`（`--mode map`）。每题 3+ 次前向，**不解码**，所以很便宜：
- `gold`：有文档的 prompt
- `recv`：等长 filler 接收方
- `patch@L0`：接收方 + 在 L0 把 `real` 臂写进 span（每个注入层一次）

对每个 (layer, head)、在「消费位置」（span 之后的 64 个位置，含最后一个 prompt 位）上记：

| 量 | 含义 |
|---|---|
| `att` | `Σ_{s∈span} a[t,s]`，该头把多少注意力给了 span |
| `c` | `W_O^h (Σ_{s∈span} a[t,s] v_s)`，该头**因为 span** 写进残差流的向量 |
| `dg = c_gold − c_recv` | 真文档造成的读出改变 |
| `dp = c_patch − c_recv` | 注入造成的读出改变 |
| `recovery(L0)` | `Σ_{L>L0}<dp,dg> / Σ_{L>L0}‖dg‖²` ← **P2 的标量** |
| `ov` / `qk` | 分解：文档改变了头**取到的值**，还是改变了头**看哪里** |
| `resid` | 每层残差流范数，做归一化 |

### 12.4 三个必须留意的方法学陷阱（已在代码里处理）

1. **eager 是强制的。** sdpa / flash 返回 `attn_weights=None`，所有数会静默变成 0。
   `--attn eager` 是默认且拒绝改。代价：eager 与 sdpa 在 L8 差约 1% 的状态幅度
   （见 `SpanScorer.capture_ids` 的注释），所以这三次前向**只互相比**，不与 sdpa 的行为学数直接混。
2. **仪器自检。** 用捕获的 `(a, v, W_O)` 重建该层 self_attn 自己的输出（全键位置），
   第一题 assert 相对误差 < 1e-2。GQA 映射错（`h//4`）、RoPE、转置写反，都会给出一张
   「干净但全是噪音」的图——这是这个文件最容易犯的错。
3. **范数随深度增长是混淆。** 残差流范数在 36 层里涨一个数量级以上，直接按 `‖dg‖` 排头
   会把「读者头」排到最深的几层。所以同时报 `‖dg‖/‖resid‖`，敲除名单也按归一化后的排。
   另外 span 占 prompt 的 30–50%，`att` 有很高的地板，一律按 `m/n` 算 enrichment。
4. **P3 有选择性偏差**：按 `‖dg‖` 选头、再在同一批题上测敲除 = 循环论证。
   `head_map.py --emit-ko k` 在**一半 calculator 上排序**，另一半留作测试，并打印两边各是谁。

### 12.5 怎么跑

```bash
# 小规模（24 题 / 6 calculator，注入层 8 和 16），约 10 分钟
./whitebox/launch.sh <host> heads-smoke wb_heads \
  "--model /inspire/ssd/project/project-public/czxs253130660/models/Qwen3-8B \
   --per-calc 4 --max-calcs 6 --inject-layers 8,16 --attn eager"

python3 whitebox/analysis/head_map.py \
  howskill/results/p8-wb/fetched/by-host/<host>/heads-smoke.jsonl

# 全量（469 题，注入层全扫），预计 1–2 小时；--no-decomp 可减一半 GPU 内存
./whitebox/launch.sh <host> full-heads wb_heads \
  "--model .../Qwen3-8B --per-calc 20 --max-calcs 55 \
   --inject-layers 0,4,8,12,16,20,24 --attn eager"

# 因果那一步（要解码，贵），名单来自上一步
python3 whitebox/analysis/head_map.py <map>.jsonl --emit-ko 12
./whitebox/launch.sh <host> heads-ko wb_heads \
  "--model .../Qwen3-8B --mode knockout --ko-heads 12:7,13:19,... --baselines ..."
./whitebox/launch.sh <host> heads-ko-rand wb_heads \
  "... --mode knockout --ko-heads <同一份名单> --ko-random 1 --ko-tag korand ..."
```

### 12.6 还没做的

- P3 的敲除名单要等 map 跑完才知道；随机对照必须用**同一份名单的层分布**（`--ko-random 1` 就是这个）。
- 只在 Qwen3-8B 上做。要说「这是一类机制」至少还要 Mistral-7B（注意它必须 L4，见 §7）。
- 敲除是 prefill+decode 全程屏蔽；单层敲除会被下一层补回来（`wb_knockout` 的既有教训），
  所以名单是跨层的一组头，不是单层。

### 12.7 小规模结果（2026-09-16 15:2x，`heads-smoke2`，24 题 / 6 calculator，Qwen3-8B）

仪器自检：用捕获的 `(a, v, W_O)` 重建 self_attn 自身输出，相对误差 **3.06e-03**（bf16 量级，通过）。

**P2（主结果）** `closed@last` = 注入在 L0 时消费位置的 receiver→gold 缺口在末层被闭合的比例：

| 注入层 | L0 | L4 | L8 | L12 | L16 | L20 | L24 |
|---|---|---|---|---|---|---|---|
| `closed@last` | 0.873 | 0.667 | 0.557 | 0.389 | 0.138 | 0.097 | 0.062 |
| 95% CI（按 calculator bootstrap） | ±0.015 | ±0.045 | ±0.03 | ±0.03 | ±0.06 | ±0.018 | ±0.016 |
| `recovery`（下游读出，对照） | 0.994 | 0.942 | 0.925 | 0.905 | 0.792 | 0.790 | 0.794 |
| 行为学 ρ（正文 §5.1） | 1.00 | 1.06 | 1.03 | 0.81 | 0.14 | (0.29→0.16 复现) | 0.00 |

与行为曲线 r = 0.916，**最大跌幅两边都在 12→16**。
`recovery` 在所有注入层都维持 0.79–0.99 → **内容在、下游也确实读了，只是没用**。

**P1（归一化后，推翻了原始读数）** 原始 `‖dg‖` 的一半以上落在 L30 之后，那是残差范数增长的假象。
按 `‖resid‖` 归一化后读出集中在 **L12–L21，峰值 L18**；L0–11 占 29%。
累计份额 `C(8)=0.19 / C(12)=0.33 / C(16)=0.50`。
**集中度不足以叫电路**：top 1% 的头（11/1152）只占 11.6%，top 5% 占 32.9%。

**注意力本身不是探测器**：所有头对 span 的 enrichment 都是 **0.2–0.5x**（低于均匀），
因为 span 占 prompt 的 56%。但 `att_gold > att_recv` 系统性成立（0.20 vs 0.15）。

**ov/qk 分解**：多数头 `ov%` 在 40–80%、`qk%` 在 10–25%
→ **文档主要改变头「取到什么值」，而不是「看哪里」**。

**反事实（未解释）**：消费位置的 receiver→gold 缺口 L20 达峰 0.38，之后**收窄**到 L34 的 0.20。

### 12.8 结论：这一节还不够独立成篇

- 「哪些头读上下文」已被覆盖：Retrieval Heads（ICLR 2025）、ReDeEP（ICLR 2025）、
  Attributing Response to Context（arXiv 2505.16415，且同样报「头集中在较高层」）、
  Geva et al.（EMNLP 2023）。描述性头图**不是贡献**。
- `closed@last` 与 ρ 的一致**半同义**：末层状态的 L2 距离 vs 末层输出的正确率。
- **累计读出份额是平滑的，行为是断崖** → 头级读出账本解释不了断崖的陡峭度。
- 真正没人做的问题见 `IDEAS.md` I4 修正段：**交接为什么是阈值而不是斜坡**。


### 12.9 断崖的真实位置是 12→14，不是 12→16（2026-09-16 15:3x 修正）

重算已有的 `big40-depth`（n=60 / 20 calculator，per-calc 限制口径）：

| 层 | 0 | 4 | 8 | **12** | **14** | 15 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|
| acc | 0.917 | 0.833 | 0.750 | 0.683 | 0.250 | 0.167 | 0.167 | 0.133 |
| ρ | +1.038 | +0.943 | +0.849 | **+0.774** | **+0.283** | +0.189 | +0.189 | +0.151 |

（gold=0.883，receiver=0.000）。L0→L12 是**平缓下滑**，跳变**全部发生在 12→14**，
而 **L13 从来没测过**。正文 §5.1 现在写的「past layer 14 …… 0.14 at 15 and 16」没有错，
但把断崖说成在 14 之后，实际上跳变在 12 和 14 之间。

**因此 (a) 的作业 = `full-depth-c`（layers 13,17,18,19，全量 469 题，无 `--baselines`，
与 `full-battery-a` 按 instance_id 合并取基线）**，跑在**新建的第 11 台 `wt-gpu-wb4`** 上，
不占用在跑的 10 个作业。合并 `full-depth-b`(12,14,15,16,20) 之后就是 12→20 的 1 层分辨率扫描。

同时在 hsw3 上并发跑了 `heads-fine`（`--inject-layers 10..16`，纯捕获，约 10 分钟）：
测机制代理 `closed@last` 在 1 层分辨率下断在哪。**若它也断在 12→14，代理预测窗口这条才立得住；
若它平滑通过 12→14，代理只是和 ρ 相关，不能预测边界。**

### 12.10 运维：这一轮加的三样东西

1. **`whitebox/mirror.sh` + `mirror_start.sh`** —— 每台机器常驻，3 分钟把 `/root/out/*.jsonl|log`
   镜像到共享盘 `ssd/.../wbout/<容器名>/`。**实例被平台回收也不丢结果**，不依赖本地在线。
   ssd 实测可写（60 MB 探针写满，3.0 GB/s，剩 525 G）；hdd 仍然满，别往那写。
   已并入 `full-rerun.sh push`。
2. **`whitebox/watch.sh`** —— 事件驱动看门狗，10 分钟一轮，**任一作业提前 idle 或机器失联就退出**
   （退出码 3），日志 `logs/watch.log` 每行是所有作业的 `行数+增量`。
   正常跑完全部作业则退出码 0。启动：
   `(nohup setsid ./whitebox/watch.sh 600 469 >> logs/watch.log 2>&1 </dev/null &)`
3. **实测工期**（8.5 s/解码，比原手册假设的 11 s 快）：`full-ko` 约 12 h、`full-battery-a` 约 8.9 h、
   `full-dose` 6.6 h、`full-rank-b`/`full-quarters` 4.4 h、其余 3.3–5.5 h。
   **`full-depth-b` 的 17 GB 内存风险不成立**：4090 盒子有 1 TB 内存、902 G 可用。

**坑（这一轮踩到两次）**：`pkill -f 'xxx.sh'` / `pgrep -f` 会匹配到**自己所在的 ssh/bash 命令行**
（命令行里含该字符串），结果把自己杀掉。一律锚定写法：`pkill -f '^bash /root/mirror.sh'`，
或用 `ps -eo pid,args | awk '$2 ~ /bash$/ && $3 ~ /autofetch\.sh$/ {print $1}'`。

### 12.11 PREREG：`full-depth-c` 回来之前写死的预测（2026-09-16 15:52）

**写在结果之前，事后不得改。** `full-depth-c`（L13,17,18,19，n=469）当时刚在 wb4 上启动，
预计 2026-09-16 21:00 前后出全量结果。

**已知的两条曲线（1 层分辨率，`heads-fine`，24 题 / 6 calculator）：**

| 注入层 | 10 | 11 | 12 | **13** | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|
| `closed@last`（机制，本次实测） | 0.470 | 0.416 | 0.389 | **0.254** | 0.232 | 0.135 | 0.138 |
| 95% CI | [.438,.502] | [.375,.457] | [.356,.421] | **[.186,.315]** | [.158,.296] | [.046,.210] | [.072,.193] |
| ρ（行为，`big40-depth` n=60） | — | — | 0.774 | **未测** | 0.283 | 0.189 | 0.189 |

**先纠正我自己 15:2x 的说法。** 当时只采了 L12 和 L16（0.389→0.138），我说「机制代理复现了断崖」。
1 层分辨率下**不成立**：机制曲线是平滑斜坡，最大单步跌幅 12→13 仅 −0.135，
且 L13 与 L14 的 CI 大幅重叠。**「代理复现断崖」是粗采样的假象。**

**预测 P-A（代理的边界定位）。** 机制曲线把 L13 放在离 L14（0.232）远比离 L12（0.389）近的位置，
所以预测 **ρ(13) 落在 0.28–0.45**，即「已经基本死了」，而不是 0.7 那一档。
- 若 ρ(13) ∈ [0.28, 0.45] → 代理定位对了边界，「不解码定位 patching 窗口」可作为工具性主张。
- 若 ρ(13) ≥ 0.65（贴近 L12）→ 代理系统性早一层，**只能说相关，不能说预测**，工具性主张作废。
- 若 ρ(13) ≤ 0.20（比 L14 还低）→ 非单调，两条曲线都要重查。

**预测 P-B（断崖的陡峭度，这条更重要）。** 无论 ρ(13) 落在哪，
行为的动态范围（0.774→0.283，跨 2 层掉 0.49）都**远大于**机制代理的（0.389→0.232，掉 0.157）。
预测：**归一化到各自量程后，行为曲线在 12–14 之间的斜率至少是机制曲线的 2 倍。**
若成立 → 存在读出账本解释不了的**阈值式非线性**，这是 `IDEAS.md` I4 修正段里的新问题，
也是这条线上唯一还没被 Retrieval Heads / ReDeEP / Geva 覆盖的东西。
若不成立（两条曲线归一化后斜率相当）→ 交接就是个斜坡，「断崖」是 4 层采样间隔造成的错觉，
那么正文 §5.1 现在「falls off a cliff」的措辞要改。

**注意事项**：`heads-fine` 只有 24 题 / 6 calculator，而 ρ 来自 60 题 / 20 calculator 的另一批。
两批题不同，所以比的是**曲线形状**，不是逐点数值。全量 `full-heads` 还没跑。

**预测 P-C（必须先排除的平凡解释）。** 行为曲线的因变量是**准确率**——一条 900 token 的推理链
最后算对没算对，是个**阈值量**。状态空间里平滑的退化，完全可能在准确率上表现成断崖：
算术差一点就是全错。所以 P-B 若成立，**不能直接说成「网络里有阈值」**，必须先做这一步：

> 沿同一条深度扫描取**连续因变量**（gold 答案的 logprob，或数值答案的相对误差），
> 看它是平滑下降还是同样断崖。

- 连续量也断崖 → 阈值在网络里，P-B 的结论成立。
- 连续量平滑、只有准确率断崖 → **断崖是评分阈值的产物**，正文 §5.1 的 "falls off a cliff"
  是对准确率的描述，不是对机制的描述，措辞必须改，I4 那条 idea 也随之作废。

这是目前最可能把 I4 打死的解释，**优先级高于 P-A/P-B 的任何后续实验**。
现成工具：`whitebox/analysis/lp_curve.py`。

### 12.12 实测速率远低于冒烟外推（2026-09-16 16:10）

冒烟用的是**救回题最多的 6 个 calculator**，文档短、推理链短，外推出 8.5 s/解码。
全量 49 个 calculator 的实测（15:48→16:07 的 19 分钟窗口）是那个数的 **1/3 到 1/4**：

| 机器 | 作业 | 解码数/题 | 19 min 增量 | ETA |
|---|---|---|---|---|
| hsw2 | full-battery-b | 3 | +29 | ~5 h |
| hsw3 | full-rank-a | 3 | +28 | ~5 h |
| wb | full-rank-b | 4 | +17 | ~9 h |
| sra2 | full-quarters | 4 | +18 | ~8 h |
| wb2 | full-depth-a | 3 | +14 | ~11 h |
| wb3 | full-depth-b | 5 | +11 | ~13 h |
| sra1 | full-dose | 6 | +11 | ~13 h |
| sra4 | full-window | 5 | +11 | ~13 h |
| hsw | full-battery-a | 8 | +8 | ~19 h |
| sra3 | full-ko | ~11 | +8 | ~19 h |

**教训：拿「题最多的 calculator」做冒烟会系统性低估工期**，因为救回题数和文档长度相关。
下次冒烟要么随机抽 calculator，要么用 `--max-calcs 55` 配小 `--per-calc`。

**因此把 `full-depth-c` 拆了。** 原来是 L13,17,18,19 四层（ETA ~18 h），但 prereg §12.11 只需要
**L13**；17/18/19 是补全尾部、没人在等。按层拆分与按臂拆分同样安全（题池相同、每层供体池独立构造），
于是：

- `wb4` 上改跑 **`full-depth-c13`（只有 L13）**，ETA 约 4.5 h → **prereg 的答案 2026-09-16 21:00 前后到**。
- 17/18/19 变成 `QUEUE` 里的 **`full-depth-d`**，等有机器空出来再派。
- 被 kill 掉的四层作业留下 21 行有效数据（`full-depth-c.jsonl`），已取回本地，不与新 tag 混。
- `full_rerun_report.py` 的 `EXPERIMENTS["depth"]` 已加入 `full-depth-c13` / `full-depth-d`。

**定时检查**：会话内 cron job `e520113d`，`13 */4 * * *`（每 4 小时 :13 分）。
`CronDelete e520113d` 取消。7 天后自动过期。

### 12.13 PREREG 判定：P-A 成立、P-B 成立（2026-09-16 19:40，**部分数据**）

`full-depth-c13`（L13，n=467/48 calc）**19:32 跑完**。与 `full-depth-a`(0,4,8)、
`full-depth-b`(12,14,15,16,20)、`full-battery-a`(基线) 按 instance_id 合并。
**注意：`full-battery-a` 当时只有 155/467 行**，基线只覆盖前 17 个 calculator（按字典序，
不是随机子集），所以下表是**部分结果**，`full-battery-a` 跑完后必须重算。

顺带纠正手册 §11.1：全量是 **467 题 / 48 个 calculator**，不是 469/49。

| 层 | 0 | 4 | 8 | **12** | **13** | 14 | 15 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|---|
| ρ（per-item，n=118/17 calc） | .981 | .944 | .897 | **.720** | **.346** | .439 | .383 | .411 | .243 |
| 95% CI 下限 | .916 | .866 | .805 | .552 | **.183** | .283 | .213 | .212 | .130 |
| 95% CI 上限 | 1.048 | 1.000 | .967 | .880 | **.500** | .578 | .554 | .603 | .362 |
| ρ（per-calc，n=29/5 calc） | .917 | .833 | .833 | .542 | **.083** | .167 | .042 | .042 | .042 |

**P-A：成立。** 预测 ρ(13) ∈ [0.28, 0.45]，实测 **per-item 0.346**，落在区间正中。
per-calc 给 0.083（CI [0, 0.286]），更低，但 n=29/5 calc 太小，以 per-item 为准。
→ 机制代理 `closed@last` 把 L13 判给「已经死了」那一档而不是 L12 那一档，**判对了**。
「不解码定位 patching 窗口」这条工具性主张**暂时立住**。

**P-B：成立。** 以 L12→L16 区间内的总变化做归一：
- 行为：12→16 总变化 −0.309，而 **12→13 单步就是 −0.374**（占 121%，先过冲再回到 ~0.4 平台）。
- 机制：12→16 总变化 −0.251，12→13 单步 −0.135（占 **54%**）。
- 比值 ≈ **2.2×**，达到预测的「≥2 倍」。
→ 行为确实比任何机制量都陡，存在读出账本解释不了的阈值式非线性。

**同时出现的、prereg 里写到的非单调**：ρ(13)=0.346 **低于** ρ(14)=0.439、ρ(15)=0.383、ρ(16)=0.411。
CI 大幅重叠（[.183,.500] vs [.283,.578]），**L13 与 L14 不显著**。
所以正确的读法是：**断崖在 12→13，之后是 0.35–0.44 的噪声平台**，而不是继续下降。

**仍未做、且最可能把 I4 打死的是 P-C**：因变量是准确率（阈值量），
必须沿同一条深度扫描取连续因变量（gold logprob / 数值相对误差）看它是否同样断崖。
工具 `whitebox/analysis/lp_curve.py`。**在做 P-C 之前不要对外说「网络里有阈值」。**

**待办**：`full-battery-a` 跑完（ETA 2026-09-17 中午）后用同一段脚本重算本表，
尤其看 per-calc 口径能否从 5 个 calculator 涨到可用规模。
`full-depth-d`（L17,18,19）已在 wb4 上接着跑，补全 12→20 的 1 层分辨率。

### 12.14 P-C 已实现并开跑：`howskill/howskill/wb_lpcot.py`（2026-09-16 23:2x）

**为什么不能用 cue 式 lp。** `wb_knockout` 的文档记着：在 `\nANSWER: ` cue 下打分，
本材料上准确率对 no-skill / wrong-skill / gold-skill **全是 0.175（完全平）**，
而 lp(gold) 仍然动 **+0.60 nats**。一个在行为可证明不动时还会动的连续量，无法用来裁定 P-C。

**改用的测量：教师强制 gold 推理链。** 每题只从 gold prompt 解码**一次**推理链，
然后把同一条轨迹在各条件下教师强制打分：

```
lp_gold  gold prompt 给自己的推理打分        （上限）
lp_recv  filler 接收方给同一条推理打分       （下限）
lp_L     接收方在第 L 层被注入后打分          （臂）
q(L) = (lp_L - lp_recv) / (lp_gold - lp_recv)
```

`q` 是 ρ 在**同一条轨迹**上的连续类比，两个锚点相同，全程**没有任何解码阈值**。
另外分开记录：整条轨迹、四个四分位、以及最后一个 `ANSWER:` 之后的答案 token
——**故意分开**，因为整条轨迹大半是各条件都能预测的样板文字，那里的零结果没有信息量；
而答案 token 正是准确率读的那部分，最可能继承它的阈值。
**在 (a)(b) 上平滑、只在 (c) 上断崖 = 评分阈值的签名。**

**前 4 题（hsw2，`pc-lpcot`，9 个注入层，全量 ETA 约 03:30）：**

| 注入层 | 0 | 4 | 8 | 12 | **13** | 14 | 16 | 20 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| q（连续，4 题均值） | 1.00 | 0.98 | 0.96 | ~0.84 | **~0.57** | ~0.55 | ~0.33 | ~0.21 | ~0.12 |
| ρ（准确率，n=118） | .981 | .944 | .897 | .720 | **.346** | .439 | .411 | — | .243 |

**初步、只有 4 题，但已看出定性差别**：q **单调平滑下降到 L24**；
ρ 在 L13 掉下去之后**在 0.35–0.44 上平台化直到 L16**，再掉。
即**准确率不是 q 的单调函数**——存在饱和。这支持「断崖部分是评分阈值的产物」。
12→13 那一步两者都有（q −0.28 占量程 31%，ρ −0.374 占量程 51%），所以也不是纯粹的评分假象。
**跑完再下结论，不要用 4 题写任何东西。**

### 12.15 作业状态（2026-09-16 23:3x）

**已完成（467/467）**：`full-battery-b`(hsw2)、`full-rank-a`(hsw3)、`full-rank-b`(wb)、
`full-depth-a`(wb2)、`full-quarters`(sra2)。全部已 autofetch 回本地 + 共享盘镜像。

**在跑**：`full-battery-a`(hsw, 275, ETA ~6 h)、`full-depth-b`(wb3, 332)、`full-depth-d`(wb4, 186)、
`full-dose`(sra1, 381)、`full-ko`(sra3, 253)、`full-window`(sra4, 282)。

**新派**：`pc-lpcot`(hsw2)、`full-dl-a`(hsw3)、`full-dl-b`(wb)、`full-heads`(wb2，全量头图，
9 个注入层，`--no-decomp`)。`sra2` 留作备用。

**注意：所有 ρ 都要等 `full-battery-a`**——它是唯一带 `--baselines` 的作业，是全部比值的分母来源，
也是最慢的一个。§12.13 的表在它跑完后必须重算。

### 12.16 全量头图跑完（`full-heads`，n=455/47 calc，2026-09-17 00:35）

24 题那版的每一条结论都复现了，CI 收紧到 ±0.02。**以后引用这一版，不要引 `heads-smoke2`。**

| 注入层 | 0 | 4 | 8 | **12** | **13** | 14 | 16 | 20 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| `closed@last` | .854 | .672 | .573 | **.424** | **.313** | .289 | .192 | .126 | .083 |
| 95% CI | ±.015 | ±.018 | ±.017 | ±.019 | **[.284,.339]** | [.259,.317] | ±.022 | ±.011 | ±.009 |
| `recovery`（下游读出） | .993 | .961 | .950 | .940 | .899 | .901 | .864 | .861 | .869 |

- **仍是平滑单调下降**，L13 与 L14 不可区分（CI 重叠），L12 显著高于 L13。
  每层最大单步是 **12→13 的 −0.111**。与行为曲线 r = 0.924。
- **`recovery` 全程 0.86–0.99**，连 L24 都是 → 内容始终在、始终被下游读走。
- **P1：读出弥散，不是电路。** 归一化后峰值 L18（0.054），带宽 L12–21；
  **top 1% 的头（11/1152）只占 10.5%，top 5% 占 31.1%**。
  注意力 enrichment 0.4–1.2x（span 占 prompt 51.4%），注意力质量本身不是探测器。
- 455 而非 467：12 题在 span 构造上被跳过，未查明，**写进论文前要查**。

### 12.17 头敲除（P3）已派，前提已知不成立

名单来自 `head_map.py --emit-ko 32`，**在 23 个 calculator 上排序、留 24 个作测试**（避免循环论证）：
32 个头落在 L9–18 + L23,24,32，与 P1 的 L12–21 带一致。

- `heads-ko`（wb2）：屏蔽这 32 个头对 span 的注意力 + `--baselines`
- `heads-ko-rand`（wb2）：**同样的层分布、随机换头**的配对对照

**预期是负结果**：P1 说 top 5% 的头只承担 31% 的读出，所以 32 个头（2.8%）大概率敲不掉多少。
但这是因果那条腿，reviewer 一定会问，且 4 h 内出结果、不推迟「全部结束」。
**若 ko 与 ko-rand 无显著差异，就如实写「读出是弥散的，没有可命名的读者头集合」。**

### 12.18 sra2 失联但零损失（2026-09-17 00:4x）

`kex_exchange_identification: Connection closed`，`connection refresh` 也没救回来。
但它的 `full-quarters` 早已 467 行跑完，**本地一份 + 共享盘镜像一份都完整**——
§12.10 那套镜像正是为这个场景加的，生效了。不去救 sra2，作业表里已移除。

### 12.19 `head_map.py` 改成流式（2026-09-17 01:0x）

全量头图是 **147 MB 的嵌套 list**，原来的 `load()` 把每一行都解析并保留，
Python 对象膨胀到几 GB —— 在 11 GB 的 WSL 上**把看门狗挤死了**
（任务被系统以 out-of-memory 杀掉，监控中断）。

改法：两遍流式。第一遍只取每行的小标量（calculator_id、m、n_prompt、
`recovery`、`closed` 的末层值、`gap_recv`、`resid_gold`），第二遍把
[layer][head] 矩阵**在线累加成均值**（`Acc` 类），任何时候内存里只有一行。
`--emit-ko` 的训练子集用第二遍的 `keep=` 参数再扫一次文件。

**峰值内存 几 GB → 18 MB，输出逐位不变。**

**在这台机器上处理全量头图，一律用改后的脚本；不要写 `json.load` 整读。**

### 12.20 看门狗必须脱离 harness 跑（2026-09-17 01:1x）

2026-09-17 凌晨 `watch.sh` 被**系统以内存不足杀掉两次**，而同样长驻的 `autofetch.sh`
一次都没事。差别在启动方式：`autofetch` 是 `(nohup setsid ... &)` 完全脱离的守护进程，
`watch.sh` 当时是 harness 的后台任务，**内存压力下 harness 会优先杀自己的后台任务**。
（触发内存压力的是 §12.19 那个整读 147 MB 头图的脚本。）

**现在的布局，照这个来：**

```bash
# 守护进程：脱离 harness，会话结束也活着
(nohup setsid ./whitebox/watch.sh 600 467 3 >> logs/watch.log 2>&1 </dev/null &)
(nohup setsid ./whitebox/autofetch.sh 900 >> logs/autofetch.log 2>&1 </dev/null &)
```

`watch.sh` 现在在报警或全部完成时**额外写 `logs/watch.alert`**，
所以一个零内存的等待器（`until [ -f logs/watch.alert ]; do sleep 120; done`）就能拿到事件通知，
即使它被杀掉，守护进程仍在记录，下一次定时检查也能看到那个文件。

**核查守护进程要看 ppid**，命令替换会产生同名瞬时子进程：

```bash
ps -eo pid,ppid,args | awk '$3 ~ /bash$/ && $4 ~ /(autofetch|watch)\.sh$/ {print "pid="$1" ppid="$2" "$4}'
```
真正的守护进程各只有一个（其 ppid 不是另一个同名进程）。

**补充（01:2x）**：连一个零内存的等待器（`until [ -f logs/watch.alert ]; do sleep 120; done`）
也被同样杀掉，而此时 `free` 显示 12 G 里只用了 1 G、空闲 10 G。
所以 harness 的 low-memory 判定与 WSL 实际内存不符（大概读的是 Windows 宿主的压力），
**与任务自身占用无关**。结论：**不要把任何监控挂成 harness 后台任务**，
一律 `setsid` 守护 + 每轮定时检查读 `logs/watch.alert`。

---

## 13. 全部实验结束：结果与判定（2026-09-17 23:4x）

### 13.1 平台在 04:46–今晚之间停掉了全部 11 台实例，**零损失**

`inspire notebook list` 显示 11 台全部 **STOPPED**。但每个作业都在停机前跑完，
`autofetch` 全部取回本地（最后一次更新 12:37）。共享盘镜像是第二份保险，没用上。
`watch.sh` 在 04:46 因 sra1 三次失联按设计报警退出，写了 `logs/watch.alert`。

**本地完整结果（14 个文件，全部 467 行，`full-ko`/`full-window` 是 469——那两个模块题池不同）：**
`full-battery-a/b`、`full-rank-a/b`、`full-depth-a/b/c13/d`、`full-dose`、`full-quarters`、
`full-ko`、`full-window`、`full-dl-a/b`、`full-heads`、`pc-lpcot`、`heads-ko`、`heads-ko-rand`。

### 13.2 主结果在全量上站住了

`python3 whitebox/analysis/full_rerun_report.py`，per-calc 口径（论文的规则）
**n=135 / 14 calculator**（旧子集是 60 / 15）；per-item 口径 **n=369 / 45**。

| 臂 | 全量 per-calc | 旧子集 | 全量 per-item |
|---|---|---|---|
| `real_L8`（移植） | **+0.89** [.76,.97] | +0.87 | +0.94 |
| `realm_L8` | +0.65 [.37,.87] | +0.73 | +0.84 |
| `self_L8`（恒等，仪器） | +0.00 [.00,.00] | +0.00 | +0.00 |
| `a0.5` / `dshuf` / `drand` / `dcross` / `dfar` | .04/.05/.02/.05/.05 | ≤.10 | .11/.21/.18/.25/.16 |
| `dnear`（n=41） | +0.12 [.00,.25] | +0.05 | +0.24 |

**每一条对照在 per-calc 下仍 ≤0.12，移植仍 0.89。正文的结论不需要改。**
秩曲线：`rank128`=+0.77、`rank64`=+0.63、`rank32`=+0.12、`rank16`=+0.05，
低半谱对照 `rank64lo`=+0.03、`rank16lo`=+0.04 → **拐点仍在 32 与 64 之间**，与正文 k*=52 相容。
四段：`q1`=+0.56 远高于 q0/q2/q3（.09/.12/.05）→ 公式段主导，结论不变。

### 13.3 深度曲线（全量，1 层分辨率）

| 层 | 0 | 4 | 8 | **12** | **13** | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| per-calc (n=135/14) | .98 | .98 | .89 | **.74** | **.16** | .16 | .06 | .06 | .07 | .03 | .02 | .03 |
| per-item (n=369/45) | 1.00 | .98 | .94 | **.79** | **.32** | .34 | .25 | .25 | .23 | .19 | .14 | .17 |

**断崖是 12→13 的单层跳变**，L13 与 L14 无差别。正文现在写的「past layer 14」**位置错了**，
要改成「between 12 and 13」。

### 13.4 PREREG 判定（§12.11）

**P-A：定性成立，定量区间落空（要如实写）。** 预测 ρ(13) ∈ [0.28,0.45]：
per-item **0.32 命中**，per-calc **0.16 偏低出界**。
**prereg 的缺陷是我没预先指定限制口径**，必须承认。
定性核心——「L13 属于 L14 那一档而不是 L12 那一档」——**两种口径下都成立**。

**P-B：强烈成立。** 行为在 12→13 单层跌掉量程的 **61%**（per-calc）/ 57%（per-item）；
机制代理 `closed@last` 同一步只跌 **14%**。比值 **4.2×**，远超预测的 ≥2×。

**P-C：断崖不是评分阈值的产物。**（`pc-lpcot`，n=442/48 calc）
连续量 q（教师强制 gold 推理链，全程无解码阈值）：

| 层 | 0 | 4 | 8 | 12 | **13** | 14 | 16 | 20 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| q | .999 | .989 | .960 | .831 | **.598** | .595 | .340 | .201 | .129 |
| CI | ±.001 | ±.002 | ±.005 | ±.03 | **[.550,.648]** | [.544,.650] | ±.03 | ±.02 | ±.015 |

每层跌幅占量程：L8→12 **3.7%**、**L12→13 26.8%**、L13→14 0.3%、L14→16 14.7%、L16→20 4.0%。
→ **连续量在 12→13 也有单层突变，是邻近区段的 7 倍。断崖是真的。**
行为（61%）仍比连续量（27%）陡 **2.3×**，所以评分阈值**放大**了它，但没有**制造**它。
四个四分位上跌幅一致（.204/.260/.309/.210），**不集中在答案处** —— 与评分阈值签名相反。

**`lp_ans`（ANSWER 段）这个指标废弃。** 分母 (gold−recv) 中位数仅 **0.0014**，
59.3% 的题 |分母|<0.01、13.6% 为负；原始 lp 在所有条件下都是 −0.001~−0.005。
教师强制完整推理后，任何条件都能几乎完美预测最后那个数，**没有动态范围**。

### 13.5 P3 头敲除：成立，但效应只比随机多 0.15

名单在 23 个 calculator 上按 `‖dg‖/‖resid‖` 排序，**在留出的 23 个 calculator 上测试**。

| 留出测试集 n=195 / 23 calc | 准确率 | 相对 gold 保留 |
|---|---|---|
| 同层随机 32 头 | 0.764 | +0.768 [.606,.898] |
| 定向敲除 32 个读者头 | 0.610 | +0.613 [.442,.773] |
| **配对差** | **+0.154 [+0.061,+0.251]** | McNemar 39:9, **p<0.0001** |

**必须同时说**：随机 32 头也削掉 23% 的效应，32 个头（占 2.8%）只移除定向 39% 的效应。
即**读出是弥散但有结构的**，不存在一小撮可命名的「读者头」能独占该效应。

---

## 14. 论文已更新（2026-09-17 深夜）

`paper/skillvector.tex`，**仍是 9 页正文 / 0 error / 0 undefined / 0 overfull**（附录 41→42 页）。
审计从 309 条扩到 **358 条，全部通过**。

### 14.1 改了什么

1. **§5.5 深度段（事实错误）**：原文说塌陷在 "past layer 14"，**位置错了**。
   改成全量 1 层分辨率的曲线，并明确「整个跌落发生在 12 与 13 之间，L13 与 L14 无差别，
   stride 2 以上的扫描定位不到」。同时加一句：连续读数下断崖依然存在，不是评分产物。
2. **图 3 标题**：注明 panel (a) 画的是**原来的子集、原来的步长**，全量 1 层分辨率在附录。
   （图本身没重画，见 §14.3。）
3. **Limitations「Which items the causal claims are about」**：写明那 40 个 calculator
   本身就是「每个 calculator 救回题最多」的 160/467 子集，以及我们把电池、秩曲线、深度扫描、
   剂量、文档四段全部在 467 题 / 48 calculator 上重跑，结论不变、无对照超过 0.12。
4. **新附录小节 `\label{app:fullscale}`**：全量 vs 子集的逐臂对照表、1 层分辨率深度扫描、
   连续因变量 q、头读出与敲除。**新科学内容全在附录**，因为正文零页边距。

### 14.2 新增的审计 check（49 条）

全量口径的 n / calculator 数、`real_L8`、`realm`、`self`、六个对照、四条秩曲线 + 两条低半谱、
四个四分位、12 层深度值；`pc-lpcot` 的九个 q 值；头敲除的留出集 n、两臂准确率、配对差、
McNemar 的两个不一致计数。旧的子集 check **一条没删**——它们对应的运行仍然存在，正文也仍在引用。

### 14.3 还没做的（按优先级）

1. **图 3(a)、图 2 秩曲线、表 2（`tab-big40`）仍由旧 tag 生成。** `paper/figs.py` /
   `paper/tables.py` 里接的是 `big40-*` / `rank40-l8` / `skillspan-*`，要改成 `full-*` 才能
   让图表本身也是全量。现在靠标题和附录说明消解不一致，**但最终应该重画**。
   风险：重画会改动图中数字，旧 check 会失配，需要同步改。
2. **`full-heads` 少了 12 题**（455/467），span 构造上被跳过，原因未查。
3. **`full-dl-a/b`（doc-last）和 `full-ko`、`full-window` 的全量结果还没写进论文**——
   数据都在本地，`full_rerun_report.py` 的 `doclast` / `knockout` / `window` 三节可以直接出。
4. AI use statement 还没更新（§8 的旧待办）。

---

## 15. 正文表图已全部接到全量数据（2026-09-18）

**9 页正文 / 0 error / 0 undefined / 0 overfull；审计 378 条全部通过。**

### 15.1 已改接全量的显示项

| 显示项 | 生成脚本 | 旧 tag | 新 tag | 结果变化 |
|---|---|---|---|---|
| 表 2 `tab-big40` | `tables.py` | `big40-base/realm/ctrl/noise` | `full-battery-a/b` | n 60→**135**；移植 0.87→**0.89** |
| 表 3 `tab-replication`（MedCalc×8B 行） | `replication.py` | `fixmask-big40`/`big40-depth`/`rank40-l8`/`ko-8b-fast` | `full-*` | n 60(15)→**135(14)**；k\* 52→**47**；reading 0.70→**0.78** |
| 表 4 `tab-skill-content` | `main_evidence.py` | `fixmask-big40`+`fixmask-quarters40-q*`；`fixmask-dl` | `full-battery-a`+`full-quarters`；`full-dl-a/b` | 四段 n 60→**135**；doc-last n 28→**151** |
| 图 2 `fig-rank-medcalc` | `figs.py` | `spanvec-rank-*` | `full-rank-a/b`+`full-battery-a` | rank64 0.54→**0.63**；k\* 52→**47** [43,55] |
| 图 3 `fig-transfer-reading` 三栏 | `main_evidence.py` | `big40-depth`/`ko-8b-fast`/`fixmask-window` | `full-depth-*`/`full-ko`/`full-window` | (a) n 60→**135** 且含 L13；(b) n 40→**466**；(c) n 48→**137** |
| `tab-ladder-models` 的 8B 行 | `tables.py` | `rank40-l8` | `full-rank-a/b`+`full-battery-a` | 同图 2 |

**正文同步改掉的数字**：秩曲线（0.13,0.06,0.13,0.54,0.77 → **0.07,0.05,0.12,0.63,0.77**）、
untruncated（0.87→**0.89**）、k\*（52 [43,72] → **47 [43,55]**，占宽度 1.3%→1.1%）、
层窗口（1.00/0.96/0.38/0.11 → **0.91/0.74/0.10/0.10**，n 48→137）、
敲除曲线（0.38/0.75/0.95 @24/28/32 → **0.46/0.79/0.91**，n 40→466，reading 0.7→**0.78**）、
剂量（开发集 n=16 → 全量 **0.04,0.04,0.14,0.53,0.87,0.89**，α=2 回落 **0.77**）、
公式段占比（full span 0.87→**0.89**）。

### 15.2 **没有**接全量的，以及为什么

- **图 1 `fig-channels-medcalc`**：接不了。`figs.py` 的 `load_spanvec` **正确地拒绝**合并
  不同接收方的运行——`full-*` 用 `--filler fixedskill`，`spanvec-fs-*` 不是，
  强合会把针对 0.175 基线的臂和针对 0.85 基线的臂画在同一根轴上。
  图 1 顶栏本来就是 **pre-fix n=20** 的最终位置实验（从未重跑），底栏是 n=16 开发集，
  标题已写明「Panels have different receivers and evaluation subsets」。**保持原样是对的。**
  全量剂量数字已写进正文。
- **Tier A（合成任务）、Qwen3-0.6B、Mistral-7B、TheoremQA 的行**：任务/模型不同，本次没重跑，
  各自保留自己的 tag。表 3 里只有 MedCalc×Qwen3-8B 一行是全量。
- **最终位置 / diffvec / 几何与 PR 诊断**：不同实验，未重跑。

### 15.3 审计

378 条（原 309 + 全量 49 + 显示项 20）。旧子集 check **一条没删**，
`k* on forty calculators` 改名成 `(subset, superseded by 47)` 以免被误读成论文现在的数字。

---

## 16. 正文数据来源全清点（2026-09-18）

**9 页 / 0 error / 0 overfull；审计 385 条全部通过。**

本轮又把四处能用现有全量数据重算的旧数字换掉了（都**不需要重跑**）：

| 位置 | 旧 | 新（全量） |
|---|---|---|
| §4 Sampling 段 | 「samples four from forty; 60 items / 15 calc」 | 「每个 calculator 全部救回题，467/48；筛选后 **135/14**」 |
| §5.3 首段 | 「forty-calculator battery, recovery 0.87」 | 「over every rescued item, **0.89**」 |
| §5.3 接收方筛选 | 0.47 (n=24) vs 0.19 (n=16)，开发集 | **34/48 个 calculator 接收方能解；另一技能 0.17 (n=332) vs 0.05 (n=135)；噪声 0.10 vs 0.02** |
| §5.4 顺序对比 | 0.85 skill-last vs 0.19 skill-first | **0.49 (n=151/17) vs 0.06 (n=135/14)** |

### 16.1 正文里**仍然不是全量**的，逐条与理由

| 位置 | 内容 | n | 为什么不是全量 | 要不要重跑 |
|---|---|---|---|---|
| 表 1 `tab-answer-format` | 作答形式消融 | 120 | **Tier A 合成任务**，不是 MedCalc，没有「全量」这个概念 | 不适用 |
| 图 1 顶栏 | 最终位置探针，**pre-fix** | 20 | 该实验从未在修复后重跑；且与 `full-*` 接收方不同 | 见下 |
| 图 1 底栏 | span 注入开发集 | 16 | `load_spanvec` **正确拒绝**合并不同接收方（`full-*` 用 fixedskill） | 不能合，标题已写明 |
| §5.3 `n=16` 两处 | 开发集来源标注 | 16 | 故意保留作 provenance，旁边就是全量数字 | 否 |
| §5.4 `dall`/`dbar` 0.11 | 跨技能平均的公共位移 | — | **该臂全量缺失**（doc-first），且现值是 pre-fix | **中** |
| §5.4 `normrecv` 1.06 | 逐位置匹配接收方范数 | — | **该臂全量缺失**，现值是 pre-fix | **高** |
| §5.5 全层注入 0.950 | 「所有层同时写回 0.95」 | — | **该臂全量缺失**，现值是 pre-fix | **高** |

### 16.2 判断

- **必要**：`normrecv` 和**全层注入**。前者是「效应是不是只是范数变化」的直接反驳，后者是
  「过了 L14 失败的是某一深度的交接、不是机制本身」这条论证的**反事实支柱**，
  两者现在都只有 pre-fix 的数。审稿人问到任一条，现有证据都偏弱。
- **可选**：`dall`。它的作用（公共位移不够）已由全量的 `dcross` 0.05 / `dfar` 0.05 / `dnear` 0.12
  三条对照承担，补上是锦上添花。
- **不必要**：Tier A、图 1、开发集标注、以及 0.6B / Mistral / TheoremQA 各行
  （不同任务或模型，本次没重跑，各自 tag 自洽）。

### 16.3 真要补，怎么跑（两个作业，机器现在全 STOPPED）

```bash
# A：doc-first 缺的两个臂，层 8
./whitebox/launch.sh <host> full-extra wb_spanvec \
  "--model $B/models/Qwen3-8B --per-calc 20 --max-calcs 55 --max-new 900 \
   --mode decode --filler fixedskill --layers 8 --arms dall,normrecv"
# B：全层注入 = 覆盖全部层的窗口
./whitebox/launch.sh <host> full-alllayers wb_spanpatch \
  "--model $B/models/Qwen3-8B --per-calc 20 --max-calcs 55 --max-new 900 \
   --matched --span skill --layers 8 --window 0:35"
```
两者都**不带 `--baselines`**，按 instance_id 与 `full-battery-a` 合并取基线。
按实测 ~15 s/解码，A 约 4 h、B 约 2 h。
