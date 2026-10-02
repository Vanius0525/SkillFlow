# SkillVector 论文交接

## 2026-10-03 研究定位简报 PDF（完成）

- 用户要求先给 A 类会议竞争力判断，再概述最近邻核心实验，并将此前 last-token / RSI 问题一起整理成桌面 PDF。
- 结论：有继续投入和形成 A 类论文的基础，但当前证据尚不足以判断已达到较有把握中稿的程度；优先主打 transfer 与 reading 分离，补接收态交互和语义覆盖控制。WWW 另有 Web 范围要求。
- 交付：[7 页 PDF](reports/研究定位与相关工作_20261003.pdf)、[可编辑源稿](reports/研究定位与相关工作_20261003.md)、[构建脚本](reports/build_research_brief.py)。包含八篇最近邻的对象/实验/贡献、last-token 设计、RSI 两阶段候选和 14 条可点击一手出处。
- 桌面副本：`/mnt/c/Users/12970/Desktop/SkillFlow_论文竞争力与相关研究_20261003.pdf`。
- 验证：`python paper/reports/build_research_brief.py`；PyMuPDF 检查 7 页、文本可提取且无空字符；目视检查首页、近邻页与参考文献页。初版 Droid fallback 缺 Latin 字形，已改用 Windows Microsoft YaHei 内嵌字体并重新验证。脚本依赖 ReportLab 及本机字体路径。
- 未运行新模型实验、未修改 LaTeX。详细文献审查及待补实验仍以同日 audit 记录为准。用户既有 `howskill/data/cells.json.tmp` 未动。

## 2026-10-03 正文创新定位与 context/prompt、last-token、RSI 调研（完成）

- 用户范围：以当前 `sections/*.tex` 正文为准，评估相关研究、last-token 注入先例、WWW 适配和 Recursive Self-Improvement 的研究连接；本轮不启动模型实验、不修改论文正文。
- 已核实近邻：Hendel et al. 2023 的 task vectors、Todd et al. ICLR 2024 的 function vectors 均有末位置注入；Li et al. arXiv:2509.04466 已研究可转移表示的时间/语义局部性及长输出衰减；Sia et al. NeurIPS 2024 使用从某层起累计 context masking；Pola & Balasubramanian arXiv:2511.10694 同时 patch 指令关键词与最终 context token。因此这些单项不能笼统声称首创。
- **即时记录：正文 §4.4 的“constant budget and energy”与实现不符。** `howskill/howskill/wb_posbudget.py:215–229` 为每个块数重新选取原位位置，`:395–410` 记录 `sum(dnorm2[src])/tot` 后直接注入，没有能量归一化或逐项能量匹配。`whitebox/analysis/out/posbudget.md` 中 c1x256…c32x256 的平均能量四舍五入均为 0.29，但这不等于每项能量固定；half 档均值已有 0.49/0.50 差别。块数变化还改变了语义覆盖。连续块恢复更好的观察可保留，但“连续性是独立原因”的断言应收窄并补控制。本轮仅记录，未擅改正文/代码。
- 官方 WWW 2027 CFP 当前明确要求首页说明 Web 科学问题；仅使用 Web 数据/API 不满足范围。现稿无工具的 MedCalc/TheoremQA 机制研究存在范围风险。来源：https://www2027.thewebconf.org/research-track-papers/ （2026-10-03 核查）。
- 完整报告：[RESEARCH-context-lasttoken-rsi-20261003.md](audit/RESEARCH-context-lasttoken-rsi-20261003.md)。包含一手出处、阅读深度、方法比较、WWW 判断、判别实验、RSI 近邻与独立研究设计。
- 新补近邻：Davidson et al. arXiv:2505.12075v3 已从自然语言指令提取 FV；Bigoulaeva et al. ACL 2026 / arXiv:2602.07930v2 把 query 前指令末 token 移植到 filler，研究多层非加性交互；不能只对比最早的 few-shot task-vector 论文。
- JIT 后续核对到 v3（2025-12-01），明确某些长输出仍能被单 TV 支持，且增加 Qwen 复现；最终报告不采用 v1 的过宽概括。
- RSI 直接近邻：Coalition-Aware Skill Reliability（arXiv:2608.22610）已做技能组合与跨域效用审计；HyperAgents（2603.19461）有固定 meta-agent 对照；AIDE²（2609.26457）作者仍承认在 outer-loop 改进角色上无法决定性区分强基线。不能把 task 提升直接写成递归改进效率提升。
- 当前问题告一段落：没有新模型实验、没有修改 LaTeX。下一步优先在现稿做晚层 span/query 交互判别和连续性语义覆盖控制；RSI 独立先做 meta-skill 的后代质量行为筛选。


最新一轮：**2026-09-28，改投 WWW 2027 版式 + 整个 paper/ 目录重构**。
更早的记录（ICLR 单栏时期的重写、润色、图表样式回退）从「2026-09-18 图表样式」一节起原样保留。

---

## 2026-09-28  改成 WWW 2027（ACM acmart/sigconf）+ 目录重构

### 做了什么

1. **版式**：ICLR 单栏 `article + iclr2027_conference.sty` → **`\documentclass[sigconf, anonymous, review]{acmart}`**，
   即 WWW 2027 research track 指定的设置（<https://www2027.thewebconf.org/research-track-papers/>）。
2. **正文内容一个字没改**（用 `sed` 按行切片，切完 md5 与原文逐字节一致）。改动只有排版性的：
   图全部升为 `figure*`、23 张表升为 `table*`（两栏下单栏宽 241pt，表的自然宽度 234–498pt，
   实测见下），`[h]` → `[tbp]`，以及 7 处指向附录的 `\ref` 换成了下面说的 `\extref`。
3. **单文件 → 分章文件**：`skillvector.tex`（2873 行）拆成 `sections/`（6 个）+ `appendix/`（8 个），
   生成物进 `tables/`、`figures/`，脚本进 `tools/`，数值记录进 `values/`，审计日志进 `audit/`。
4. **附录去重与去过时**（见下「删了什么」）。
5. **两个构建目标**，靠 `main.tex` 里一个开关切换，**什么都没删**：

   | 目标 | 开关 | 页数 | 用途 |
   |---|---|---|---|
   | 投稿版 | `\extendedappendixfalse`（**默认**） | **正文 8 页 / 全文 12 页** | WWW 2027（上限 12 页含参考文献与附录） |
   | 技术报告 | `\extendedappendixtrue` | 正文 8 页 / 全文 34 页 | arXiv / 审稿人索要 / 自己查 |

   仓库里 `main.tex` 默认是**投稿版**，所以 Overleaf 上传后直接编译就是 12 页。
   `build.sh` 会在 staging 副本里按目标显式设置这一行，不依赖仓库里留成哪一边。

   ```bash
   ./build.sh              # 34 页 → skillvector.pdf
   ./build.sh submission   # 12 页 → skillvector-www2027.pdf
   ```

### 为什么必须有两个目标

WWW 2027 长文是 **8 页正文 + 参考文献 + 可选附录，总共不超过 12 页**，且前 8 页要自足。
正文（不改内容）在两栏下正好 8 页，参考文献约 1 页，**留给附录的只有约 3 页**，
而附录在两栏下是 **约 25 页**。实测各节页数（完整版）：

| 附录 | 内容 | 页数 |
|---|---|---|
| A | Setup, in full + Experimental detail + Evaluation scope | 2 |
| B | The full-dataset rerun（`tab:fullscale`、逐层深度、哪些 head 读 span） | 1.5 |
| C | Control documents + 三个 measurement traps + MC 格式 | 3 |
| D | 末位置几何 + 分解 + 答案长度阶梯 + 合成层全量 | 3 |
| E | span battery + 向量由什么构成 + 深度 + belongs | 11 |
| F | 秩截断 + model ladder + 跨任务复现 | 3 |
| G | Related work, at length | 1.5 |
| H | Additional tables | 4 |

投稿版保留 **A + B**（复现所需 + 全量重跑那张表），其余六节只是不 `\input`，
文件仍在仓库里、仍能编译。

### `\extref`：让两个版本的交叉引用都成立

正文有 7 处、核心附录有 4 处 `\ref` 指向被排除的附录。新宏：

```latex
\newcommand{\extref}[3]{\ifextendedappendix#1~\ref{#2}\else#3\fi}
```

- 完整版渲染成**和改之前逐字相同**的 `Appendix~\ref{...}`；
- 投稿版渲染成 "the extended version"，不出 `??`。

例：`\extref{Appendix}{app:onepos}{the extended version}` →
完整版 "Appendix D.1"，投稿版 "the extended version"。

### 图 1 改成并排（2026-09-28 晚）

`fig_channels_full.py` 原来是 `subplots(2, 1)`，两个面板上下叠、figsize (4.9, 3.0)、
用 `height_ratios` 让两边的条一样粗。改成 `subplots(1, 2)`、figsize (7.1, 2.15)，
长宽比从 1.84 变成 **3.49**，在两栏页面上只占一条横带。

两处为窄面板做的调整，改回去会出问题：

- 两个面板臂数不同（3 与 5）。等高的轴下直接画会让左边的条变粗，所以把条**居中放进一个
  共享的 5 槽坐标**（`off = (span - len(items)) / 2`），两边条的物理粗细相同。
- 两条基线标注原来同一行，面板宽度减半后 `wrong-skill receiver (0.00)` 和
  `correct skill (0.92)` 会叠在一起，改成上下各一行（y = −0.62 / −1.12，ylim 下界放到 −1.55）。

正文 caption 里 "Top:" / "Bottom:" 相应改成 "Left:" / "Right:"，图宽从 `0.92\textwidth`
改成 `\textwidth`（图变矮了，占不了多少高度）。`check_main_data.py` 会检查
`135 / 0.81 / 0.03 / 0.06` 四个数在 PDF 里渲染得出来，改完仍然通过。

### 删了什么（两个版本都删，理由是重复或已被取代）

| 删除项 | 理由 |
|---|---|
| `app:decomp` 开头「几何与行为相反」整段（15 行） | 与 `app:geometry` 一节几乎逐字重复，改成一句指针 |
| 第二处 "Which control you subtract chooses what you measure"（7 行） | 同一段在 `app:onepos` 已有带数字的完整版 |
| 「shuffle 打乱行序代价很小」那句的第二次出现 | 同一文件内两小节各说了一遍 |
| `app:depth` 里 **pre-fix 的 window 表**（n=27，7 个 calculator） | 紧接着的段落自己写着 "those estimates are superseded" |
| `tab:ladder` 的前两行 | 与 `tab:format` 上半块逐数字相同，改成指针 |
| `tab-prdiag-06/-17/-dl.tex`、`tab-skilltask.tex` | 生成了但全文没有 `\input` |
| `fig-decode-medcalc`、`fig-depth-medcalc`、`fig-dose-tierA`（pdf+png） | 全文没有 `\includegraphics`；decode 那张是 09-14 删掉的 skill 识别实验的遗物 |

**没有删**（想删但证据不足，留给你判断）：
- `tab:windows`（三通道表，n=39）：前两行被 `tab:windows2` 完全覆盖，第三行（末位置整集
  0.436–0.487 / 接收方 0.231）是 `tab:windows2` 没有的量，所以没动。
- `app:replication` 里 LogicBench 那条否定结果（5 行）：不承担任何正文结论，但删负结果要你点头。
- 所有其余 pre-fix 数字：文中都明确标注了 pre-fix 且给了 post-fix 对照，属于诚实记录。

### 目录结构

```
paper/
  main.tex                 前言 + ACM 元数据 + \input 骨架 + \extendedappendix 开关
  README.md                怎么编、怎么上 Overleaf、怎么重算数字
  sections/                00-abstract … 05-conclusion（6 个文件）
  appendix/                a-setup … h-additional-tables（8 个文件）
  tables/                  18 个由 tools/ 生成的 tabular 片段
  figures/                 10 个 pdf（+ png 副本，不进 Overleaf 包）
  skillvector.bib
  build.sh                 两个目标都从这里编
  tools/                   生成器 + 数据核对（原来散在 paper/ 根目录的 14 个 .py）
    _paths.py              新增：PAPER/TABLES/FIGURES/VALUES 与 main_text()
    make_overleaf_zip.py   打 Overleaf 包（这台 WSL 没有 zip(1)，用 Python 写）
  values/                  *-values.json、posbudget.json、DATA-CONSISTENCY
  audit/                   历次审计日志
  legacy/                  ICLR 的 .sty/.bst、旧 skillvector.tex、旧 .bak、旧预览图 —— **可以整个删掉**
```

### 流水线改了哪些路径（都已验证）

`tools/_paths.py` 统一给出 `PAPER / TABLES / FIGURES / VALUES / AUDIT`，以及 `main_text()`
——因为 `check_main_data.py` 原本是 `skillvector.tex.split('\label{endmain}')[0]` 拿正文做
prose 检查，拆文件后改成按 `main.tex` 的 `\input` 顺序拼 `sections/*.tex`。

```bash
cd paper
MPLCONFIGDIR=/tmp/skillvector-mpl python3 tools/refresh_main_data.py   # 8 个阶段全 PASS
python3 tools/check_main_data.py     # PASS: 70201 checks（和改之前同一个数）
python3 ../whitebox/analysis/audit.py  # ALL CHECKS PASSED
```

`refresh_main_data.py` 仍然不覆盖 `controls_table.py` / `decomp_tables.py` / `figs.py`，
改了对应数据要手动跑，命令在 `README.md`。

### 验收（2026-09-28）

| 项 | 投稿版 | 完整版 |
|---|---|---|
| LaTeX error | 0 | 0 |
| 未定义引用 | 0 | 0 |
| Overfull hbox | 0 | 0 |
| Overfull vbox | 0 | 1（1.6pt，分页产物，不是跑出版心） |
| 正文页数 | 8（上限 8） | 8 |
| 全文页数 | **12**（上限 12） | 34 |
| `check_main_data.py` | 70201 checks PASS | 同 |
| `whitebox/analysis/audit.py` | ALL CHECKS PASSED | 同 |

### 投稿前还必须做的三件事（`main.tex` 里都标了 TODO）

1. `\acmConference` / `\acmDOI` / `\acmISBN` 现在是占位符，要换成 ACM rights form 发来的那一段。
2. CCS concepts 现在是我按标准 CCS 树填的
   （`10010147.10010178.10010179` = Computing methodologies → NLP，
   `…10010187` = Knowledge representation and reasoning），**投稿前用
   <https://dl.acm.org/ccs> 重新生成一遍**。
3. `\author{Anonymous Author(s)}` 那一块，去匿名时换成真实作者。

另：正文 8 页是**踩着上限**的。任何正文改动都可能顶到 9 页，改完必须重跑 `./build.sh submission` 看页数。

### Overleaf

`paper/overleaf-skillvector.zip`（45 个文件 / 0.25 MB，`tools/make_overleaf_zip.sh` 生成）：
只含 `main.tex`、`README.md`、`.bib`、`sections/`、`appendix/`、`tables/`、`figures/*.pdf`。
不含 Python、PNG、审计日志、legacy。Overleaf 自己有 `acmart`，编译器选 pdfLaTeX。
包里默认就是投稿版（12 页）；要读完整版就在 Overleaf 里把 `\extendedappendixfalse` 改成 `true`。

---

## 2026-09-18 及更早：ICLR 单栏时期的记录

更新日期：2026-09-18（图表样式回退为当日第二轮）。

## 2026-09-18 图表样式与分页回退到旧版布局

- 用户任务：正文逻辑、表达和数据不改，把图表样式和分页改回桌面 `ICLR_2027__SkillVector/paper_` 那一版的风格和布局；数据继续用本仓库的新结果；图 2 的几条曲线要画在同一个坐标系里。
- 图 2（`fig_rank_full.py`）：三个面板合并为一个坐标系，沿用旧版 `figs.fig_rank` 的样式（标记 o/^/D、1.0 处绿色虚线、0 处接收者线、12 处的宽度比例预测标注、图例放在图下方两列），tex 里的宽度恢复为 `0.64\textwidth`。bottom-k 对照按各模型颜色画空心方块虚线，与旧版一样不画误差条；图例写入 n 和 k*。为避免三条曲线在同一 k 上重叠，加了约 ±5% 的对数轴横向错位（dodge）。标题从 “before its own handover” 改为 “at an early layer”，和新图注一致（0.6B 在 MedCalc 上没有测 handover）。
- 图 1（`fig_channels_full.py`）：改用旧版 `figs.fig_channels` 的样式：每个面板第一根柱子用深色，标题里写 n，每个面板在最低柱下方标出自己的基线（wrong-skill receiver / correct skill），x 轴标签也用旧版的。上面板的 y 轴标签缩短成 `last $\leq$256 prompt positions`，否则坐标轴被挤窄，两条基线标签会重叠。
- 表 2（`main_evidence.span_battery`）：改为旧版排版：表头小写、`CI$_{95}$`、区间写成 `[a,\,b]`、recovery 带符号，三条参照行（correct skill / identity / unpatched）用斜体；保留新增的 n 列（same-family 只有 41 项）。`check_main_data.py` 里对应的 TeX 格式断言也同步改了。表 1、3、4 的样式新旧版本本来就一样。
- 分页：把 `tab:replication` 的 table 环境（内容不变）从 §4.7 开头移到图 3 之后，得到和旧版相同的分页：p5 表1+图1，p6 表2+表3，p7 图2，p8 图3+表4，p9 正文与结论。正文仍是 9 页，全文 42 页，0 error、0 未定义引用、0 overfull。
- 验证：图 1、图 2 生成器重跑后，`fig-channels-values.json` 和 `fig-rank-values.json` 与改动前逐字节一致；`battery-values.json` 没有变化；`check_main_data.py` 27207 项全部通过（manifest 哈希已更新）；和 HEAD 比较，tex 的行集合只有 includegraphics 宽度那一行不同。
- 遗留：图 2 按旧版宽度 0.64\textwidth 缩放后，图例字号实际约 4pt，偏小（旧版也是这样），审稿时可能被提意见；如果要放大，需要从别处省出大约 3 行，否则会超 9 页。`overleaf-skillvector.zip` 仍然没有更新（原因同下一节）。

## 2026-09-18 正文逐段润色

- 用户任务：逐段润色 `skillvector.tex` 正文，提高可读性、术语引入和逻辑衔接，保留整体结构。本轮已处理摘要、Introduction、Related Work、Problem Formulation、Experiment、Conclusion、三项贡献与七处图表说明。
- 保留五个顶级章节、七个实验子节、17 个 paragraph 标题位置、3 图 4 表、全部公式、label、引用键及图表输入文件；`\\label{endmain}` 后内容与本轮修改前逐字一致。未改实验脚本或原始结果，未提交/推送。
- 同步正文中已被本地记录证实的旧数字：主 span 恢复 0.89、rank32 0.12、bottom64 0.03、rank knee 47；全文统一筛选后 135 题/14 calculators 的适用范围。使用 `python3 whitebox/analysis/full_rerun_report.py battery rank` 核验；按 `paper/replication.py` 的分组筛选和 kstar 定义、2000 次 calculator bootstrap 独立计算得 47.2909 [43.3021, 54.7581]，故正文统一为 47 [43,55]，替换另一处旧区间 [43,72]。
- 将“整个 drop 都发生在一层”收窄为“最大下降发生在 12–13 层”；后续层最大值按本地附录曲线改为 0.07。连续概率读出支持存在较陡下降，但其阈值并不等同于 accuracy 的 0.5 crossing。删除从 quarter 结果推出其他部分必须组合贡献的推断；prompt-order 比较明确不是同一样本的配对估计。
- 检查：`python3 paper/checks.py paper/skillvector.tex` 无重复标签，36 对全篇图表环境匹配；源码对比确认结构/公式/引用不丢失。`bash paper/build.sh` 最终正文 9 页、全文 42 页，0 LaTeX error、0 未定义引用、0 overfull，已更新 PDF。第一次编译正文 10 页，压缩重复表述后恢复 9 页；未改字号/页边距或缩图来压页。
- 改前源码备份：`.snapshots/skillvector-20260918-before-polish.tex`。修改说明与待核对项：`POLISH-AUDIT-20260918.md`。
- **仍存在的投稿前问题（非润色能解决）**：现有图 1 PDF 底部写 n=20、accuracy=0.95，与图注开发子集 n=16/1.00 不一致；图 2 PDF 只有两条 Qwen 曲线，没有正文/图注所述 Mistral，且其版本与当前 135 题结果不同。此次不重生成图或改变实验范围，图表资产与正文的一致性仍未通过。
- 主表 `tab-big40.tex` 的同 family 条目只覆盖 n=41；当前表用总体 donor 分母报 0.13，而匹配该 arm 样本的计算为 0.12。正文保留已核验的完整子集控制，不再笼统声称所有同/异类控制相同；表内口径待专门修正。附录也残留旧样本说明与不成立的“所有 control 不超过 0.12”等表述，按本轮正文范围未修改。
- 下一步：同步图表生成器与其实际样本、逐 arm 分母及图注，清理附录旧数值/旧说明，再作投稿前完整数据审计；pre-fix synthetic/final-position 结果仍需修复后验证。本轮未更新 Overleaf ZIP，避免将未完成数据一致性检查的包视为投稿定稿。

## 当前任务

按用户要求重写 `skillvector.tex` 正文，结构为 Introduction、Related Work、Problem Formulation、Experiment、Conclusion。引言依次讲问题、paradox、关键实验、核心发现、进一步验证，并归纳 3–4 项贡献。保留实验结果和分析结论，优先使用 skill，检查数据与引用，不保留 Limitations 部分。

## 已验证事实

- 修改前正文有 11 个顶级章节，Introduction 有 6 项贡献；独立 Limitations 在正文与附录各一处。
- 已保存原始 tex、bib、pdf 到 `.snapshots/*-20260917-before-rewrite.*`。
- 当前仓库已有大量其他未提交工作；本次仅在 paper 目录修改，不提交或推送。
- 旧 build.sh 使用 Windows MiKTeX 并写入 `/mnt/c/...`，需另查可用的本地编译路径。
- 2026-09-17 图表样本审计：当前正文 MedCalc 因果图表仍引用从 55 个计算器中按 rescued 数最多选出的 40 个、每组 4 个，共 160/470 rescued item；再按 receiver 全错筛到 15 组/60 item。此“top 40”选取规则未见于正文采样段落。参见 `../whitebox/full-rerun.sh` 的 WHY 注释及 `skillvector.tex` 实验设置。
- 本地 `../howskill/results/p8-wb/fetched/by-host/*/full-*.jsonl` 已有全量重跑文件；`python ../whitebox/analysis/full_rerun_report.py battery rank depth quarters knockout dose doclast window` 显示主要 span 注入在组筛选下为 0.89（旧 0.87）、rank128 为 0.77（旧 0.77）、formula quarter 为 0.56（旧 0.56）、depth L12/L13 为 0.74/0.16；但 skill-last L16 own 恢复率从旧 0.85 变为 0.49，同组他例从 0.48 变 0.29，需改写相关论断。多数 full span 输出只有 467 item/48 calculators，knockout 有 469/49；缺的两项是 calculator 28 的 `medcalcbench_00937`、`medcalcbench_00925`，必须查明。正文尚未吸收这些结果。

## 完成状态

- 已完成五节结构重写；用户后续要求将贡献压缩为三项、正文采用 3 图 4 表，均已落实。
- 三个贡献：可转移 skill 表示的因果定位；恢复所需表示 rank；skill 转移与继续读取的深度分离。
- 主图：最后位置 vs skill span、rank 曲线、替换/累计注意力敲除/层窗口三面板。主表：答案格式、span controls、skill 内容与题目依赖、跨模型与任务复现。
- 注意力敲除位于正文 §4.6 及图 3(b)；第三个贡献显式提及 cumulative attention knockout。
- 新增 `main_evidence.py`，从原始记录生成新增主图及两张表。无需新增模型实验；旧附录深度图仍保持其原来的历史定位，不混入修复后主图。
- `python3 ../whitebox/analysis/audit.py`：309 项通过；日志 `DATA-AUDIT-20260917.txt`。
- 原有所有 label 保留，35 对图表环境匹配；五节、3 图、4 表、3 项贡献的结构断言通过。
- Windows MiKTeX 编译通过：正文 9 页，全文 41 页，0 error / 0 未定义引用 / 0 overfull；已查看主要页面排版。日志 `BUILD-CHECK-20260917.txt`。
- 已更新 `skillvector.pdf` 和 `overleaf-skillvector.zip`；ZIP 已做依赖和 CRC 检查，内容与当前主 tex 一致。
- 原有 48 条引用均核对一手页面；更正见 `CITATION-AUDIT-20260917.md`。完整改写说明见 `REWRITE-AUDIT-20260917.md`。

## 已发现并处理的口径问题

- 原稿 battery accuracy CI 实际为逐题正态近似，rank 图误差条实际为逐题 bootstrap；本次保留所有区间数值，纠正图注与方法说明。生成器 `tables.load()` 的 calculator_id 键切片问题尚未修改，避免擅自改变用户要求保留的统计结果。
- battery 和 depth 都写 n=60，但分别为 15 和 20 个 calculator，已明确。
- TheoremQA 实际按 skill 分组筛选，singleton 才等于逐题筛选，已明确。
- 答案格式的 MC/numeric 各 120 题，CoT 为其中 80 题子集；新表同时列 evaluated 与 rescued，避免“完全相同样本”表述。
- k 指中心化方向数，保留均值后完整注入 rank 至多 k+1；k* 是有限网格的半幅 knee，不是完全恢复所需的最小 rank。

## 尚待用户补充

- 已通过异步问题询问历史 AI 使用范围，尚未回复。当前 AI Use Statement 仅陈述本轮已确认用途，不声称已完整核实此前的代码/实验设计/结果分析历史。官方要求与截止日期已记录在核查报告。
- 无提交/推送/投稿系统上传操作。
- 2026-09-17 正文审阅：现有五节主线完整，编译 PDF 的结论落在第 9 页，符合 ICLR 2027 正文不超过 9 页的页数要求。科学审稿风险集中在：主结果仅对 40 个计算器中筛出的 15 个组/60 个 item 成立；仪器修复前的 synthetic、final-position 与部分机制结果仍承担核心叙事；rank knee 是网格上的半高点而非最小充分秩；跨任务和模型的对照并不齐全。下一步优先在修复后重跑支撑主张的诊断、报告未筛选总体及每组效果，并收窄 abstract/conclusion 的外推。

## 失败尝试及原因

- 首次沙箱内调用 Windows MiKTeX 因 WSL socket 权限失败，经工具请求授权后正常编译。
- 图标签改名时暂将内部筛选键 needs_document 一并改名，数值一致性检查立即识别出 n=40 与原 n=16 的不一致；已修复内部键并重生成，最终图的全部数字标签与原稿一致，错误中间图未作为最终结果交付。

## Open Ideas / 值得深挖的问题

- **2026-10-03：meta-skill 的内部表示能否因果影响下一代改进效率？** 触发：现稿 span transfer 与 continued reading 分离；近期 HyperAgents/AIDE² 研究改进过程本身，Coalition-Aware 已覆盖技能库效用。最小验证：旧/新 meta-skill 的双向 patch 后生成 candidate skill，在全新固定 executor 与隐藏新任务评测后代质量；比较固定 improver 与更新 improver 的独立演化链。价值在连接内部因果中介与下一代可继承增益，不是又做技能移除审计。假说未验证，详细设计与失败判据见 `../IDEAS.md` 的 I8 及本轮调研报告 §6.2。

- **2026-09-17：skill span 的位置预算与任务映射复杂度是否共同决定单向量失效？** 触发：现稿单位置与完整 span（约 415–1,630 token）干预的效果差很大，但同时改变了干预容量；Dong et al., arXiv:2506.09048 的双射任务使 task vector 在原任务/逆任务较好、组合双射接近随机。值得做：把“答案长所以单向量失败”与“技能映射本身需要分布式表示”分开。最小实验：同一模型、同一 skill 与答案格式下，在独立 held-out 题上比较 1/4/16/64/全 span 的保序位置预算、相同预算的语义区域和随机/错位控制；另构造低/高映射复杂度的技能，在各预算下画恢复曲线。若高复杂度任务在等长答案下需要更多位置，且不是单纯 token 数或扰动能量造成，可能形成独立机制结果；若所有曲线只由答案长度或扰动总量解释，则该想法失败。
  - 现有部分位置证据：40-calculator 修复后 quarter ablation 已覆盖四个独立四分之一及完整 span（$0.12/0.56/0.12/0.12$ 对 $0.87$）；共享前缀有 $0.73$ 对完整 span $0.87$。因此新实验是填补同一 skill span 内连续、等预算、跨长度的位置剂量曲线，不是首次做局部 span 干预。

## 相关论文记录

- Dong et al., *Understanding Task Vectors in In-Context Learning: Emergence, Functionality, and Limitations*, arXiv:2506.09048：线性 Transformer 分析预测单 task vector 在双射映射上的表达限制，并用原任务/逆任务/组合双射的对照表及多向量注入验证；与本稿相关的是对“一个位置何时够用”的正面反例设计，但其映射秩不同于本稿 span 矩阵截断秩。
