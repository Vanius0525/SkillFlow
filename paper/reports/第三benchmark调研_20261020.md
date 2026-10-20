# 第三个 task＋skill benchmark 调研

日期：2026-10-20。范围：寻找单次加载已有、可复用 skill 后提升原任务表现的组合，供四模型×三 benchmark 扩展选型。仅调研与本地资产静态核查；未运行模型、未修改投稿稿件、未更新 Overleaf。

## 结论与推荐顺序

**最直接推荐 SRA-Bench 的 LogicBench＋19 个逻辑推理技能。** 它提供纯文本、单 skill、规则评分、每 skill 多题的完整配对，能增加非数值推理任务；已有论文同时覆盖当前 Llama-3.1-8B 和 Qwen3-8B 的收益证据。其局限是答案空间小、错误 skill 也可能有用，而且本地历史实验已见较平缓的深度下降。后者应作为边界案例保留，不能据此排除。

**如果更重视任务类型跨度，第二选择是 SRA-Bench BigCodeBench＋软件库技能。** 模型只生成一次代码，生成结束后由外部单元测试评分，可以满足单次模型执行；“评分执行代码”不等于“模型推理中使用工具”。但需新建隔离测试环境、多 skill 文档拼接协议，接入成本明显更高。

**CHAMP＋数学概念技能作为低改造备选。** 收益证据较强，但与 TheoremQA 同属数学推理；223 题中仅114题为单 skill，进一步要求同 skill 跨题 donor 会缩至95题。四模型筛选后可能过小。

这里的“单步”指一次提供 skill、一次生成完整回答，允许回答内部多步推理；不要求数学问题只有一个运算步骤。若要求每题严格一个 skill，LogicBench 适配最好，BigCodeBench 和完整 CHAMP 不满足。

## 现有两组实验的来源核实

当前稿件 `appendix/a-setup.tex` 明确：MedCalc 使用 SRA-Bench 发布的55个 calculator skill、每个20题；TheoremQA 使用其发布的 prompts、skill assignments 和 evaluator。它们不是原 benchmark 自带的 SKILL.md：SRA 作者把原始结构化标注加工为技能，并进行人工修订。因此用户对“已有论文给出有效 task＋skill 配对”的记忆基本正确，但应区分原 benchmark 与后续 skill 增强版本。

SRA 的 Oracle Skill 指直接提供标注的正确 skill，最贴近当前固定选 skill 的实验；检索策略和渐进加载结果不是本项目应直接引用的单次加载证据。[SRA 原论文，§4.2、Table 2、Appendix A](https://arxiv.org/html/2604.24594v1)。

## 广泛筛选结果

| 候选及具体组合 | 已有收益证据 | 与当前协议的关系 | 决策 |
|---|---|---|---|
| SRA LogicBench＋19个推理规则技能 | Oracle 对比无 skill 有提升；另有 Qwen3-8B 完整文本对照 | 单 skill、纯文本、客观答案，最容易接入 | 首选 |
| SRA BigCodeBench＋139个库使用技能 | 小模型和 Qwen3-8B 均有增益证据 | 一次代码生成；需单元测试及多 skill 协议 | 多样性优先时选它 |
| SRA CHAMP＋89个概念技能 | 多模型提升；Qwen3-8B 亦有正收益 | 纯文本，但约一半题多 skill，答案评分更复杂 | 备选 |
| SRA ToolQA＋14个工作流技能 | 有 Oracle 收益 | 依赖外部数据库、工具交互，不能直接改为无工具 | 排除直接接入 |
| SELF-DISCOVER 的 BBH＋固定推理结构 | 有跨模型迁移的结构收益 | 离线发现后可单次使用；结构不是原生技能包，需冻结发布结构 | 非 SRA 来源备选 |
| LEAP 的 DROP／BBH＋错误反思原则 | 原文报告原则增强收益 | 最终推理单次，但包含 few-shot examples，需区分原则和示例贡献 | 第二梯队 |
| RuleArena＋航空／NBA／税务规则 | 原文重点验证复杂规则推理及工具增强 | 规则就是任务信息；缺少同协议无规则→有skill的直接收益对照 | 不满足当前强证据要求 |
| RuleTaker／ProofWriter＋规则说明 | 有成熟逻辑数据与确定标签 | 实例特有规则是题目本身，不能当可复用 skill 的收益证据 | 不直接选 |
| SkillsBench＋人工技能 | 有广泛总体增益 | 多数需要文件、脚本、长交互；text-only不等于无工具 | 不直接选 |
| FinSkillBench＋投资管理技能 | 原文报告技能条件均值提高 | 技能含执行脚本，ReAct多轮工具，收益无法归于仅文本 | 不直接选 |
| SkillGym＋人类技能任务 | 具代码校验和技能依赖筛选 | 主要是训练/长工具轨迹，非单次纯文本增强 | 不直接选 |
| EduSkillBench＋教育技能 | 单轮子集观察到评分提升 | 仅42题，rubric包含skill执行符合度，模型与judge混杂 | 暂不选 |
| Skill Blocks 的 SearchQA＋加载文档 | 比较加载方式的质量／开销 | Full skill与不同加载方案的对照不等于证明比无skill有益 | 证据不足 |
| MCE 的 FiNER／USPTO＋演化上下文 | 已有上下文增强收益 | 多阶段学习，元层skill与最终上下文不同；USPTO上下文对小模型过长 | 不直接选 |
| SkillBenchmark 社区单轮评测 | 原生单轮skill A/B框架 | 不是成熟论文benchmark，主要依赖judge评分 | 不作为主实验 |

表中“排除”仅指不能直接支持本次单次纯文本 skill 干预，不代表这些 benchmark 无科研价值。

## 三个重点候选的直接证据

### LogicBench

原始 LogicBench 是 ACL 2024 长文，评估25种逻辑模式；SRA 合并/排除重复变体后，保留760题、19 skill、一题一skill。[原始论文](https://aclanthology.org/2024.acl-long.739/)、[技能发布](https://huggingface.co/datasets/WeihangSu/SRA-Bench)。

SRA Table 2：Llama-3.1-8B 无skill54.6%→Oracle69.5%，+14.9个百分点；Qwen3-4B 75.0%→85.1%，+10.1个百分点。原论文温度0.7，不能等同当前greedy协议，也未覆盖当前四模型全部配置。[论文表格](https://arxiv.org/html/2604.24594v1#S5.T2)。

后续 SKIM 论文 Table 2 的**未压缩 Full Text 对照**：Qwen3-8B 77.11%→85.26%，+8.15个百分点；Phi-4 48.55%→75.66%。这是另一篇论文的证据，但仍用同一 SRA 技能来源，并非独立技能构建；不能把训练后的 SKIM 列当作原模型单次 skill 收益。[SKIM](https://arxiv.org/html/2606.12203v1)。

本地静态核对：760题中542题BQA、218题MCQA；19组均40题。技能含方法、适用条件、错误模式和新编例题。例如 Modus Tollens 教授从“P→Q；¬Q”推出“¬P”。完整技能长度3352–6121字符；这不是token长度，四个tokenizer还需分别测量。

必须注意：本地 Modus Ponens 文档要求在形式化任务中把带“likely”等词的条件按基准规定处理。这可能体现对 benchmark 标签约定的适配，不完全等于普遍逻辑能力，需人工核验题目歧义和技能内容。

**历史反事实证据**：未被当前 `main.tex` 引用的 `appendix/f-rank-and-replication.tex` 记有57题/16skill的旧结果：span恢复0.75，other-skill0.38、permuted0.25、noise0.15，深度恢复L0=0.93、L16=0.49、L20=0.33。历史代码修复、筛选和评分链未在本轮重新审计，不能视为当前结论。但它提示本次应检验“深度分离”而非预设必须有陡峭断崖；旧数据不可直接拼入新实验。

### BigCodeBench

原始 BigCodeBench 为 ICLR 2025 工作；SRA 提供1140题、139个库技能，一题可关联多个库。技能讲 API、参数、调用顺序及错误处理，模型一次生成函数，再执行隐藏测试评分。[官方仓库](https://github.com/bigcode-project/bigcodebench)、[SRA数据卡](https://huggingface.co/datasets/WeihangSu/SRA-Bench)。

SRA Llama-3.1-8B 32.3%→35.2%，+2.9个百分点，增益小于LogicBench；SKIM Qwen3-8B无skill40.96%→Full Text49.30%，+8.34个百分点。后者平均增加4676 skill tokens，明显长于LogicBench的1089，可能增加全层干预成本。[SRA Table 2](https://arxiv.org/html/2604.24594v1#S5.T2)、[SKIM Table 2](https://arxiv.org/html/2606.12203v1)。

建议若选：固定完整多skill拼接顺序并将整体作为skill span；不按当前模型表现挑库。另一方案是预先定义单skill子集，但必须先静态核验规模，目前尚未计算。测试依赖、文件/网络调用、随机性、超时、隔离执行均需审计；模型生成过程中不接收测试反馈。评分用pass@1，即一次生成通过全部指定测试的比例，越高越好。

### CHAMP

原始 CHAMP 是270道竞赛数学题，包含通用concept与题目特定hint；二者不能混用。可复用skill应取SRA概念技能，不能把题目hint直接装成skill。[原始论文 arXiv:2401.06961](https://arxiv.org/html/2401.06961v2)。

SRA Llama-3.1-8B 22.4%→40.8%，+18.4个百分点；SKIM Qwen3-8B 48.88%→68.16%，+19.28个百分点。两篇的样本/推理/评分不与本地旧评估等价。[SRA](https://arxiv.org/html/2604.24594v1#S5.T2)、[SKIM](https://arxiv.org/html/2606.12203v1)。

本地223题、89技能，单skill114题、44组；其中25组至少两题、共95题。复杂答案含表达式和短语；已找到官方规则评分代码，但不能因为其名为rule-based就假定无误判或无状态污染，需独立检查等价表达式、解析失败及评分顺序。

## 本地现有资产：仅作为线索

可直接读取 `../howskill/data/sra/{logicbench,champ}_{instances,skills,pairs}.json`。源记录为2026-09-14从HF main取得；本轮未与线上最新数据逐字比较。静态统计和SHA256写于配套 `第三benchmark本地资产核查_20261020.json`。

旧 `cells-lb-qwen8b.json` 记录gold86.18%、none76.18%、wrong71.71%，R/F/K/B=137/44/518/61；旧CHAMP记录49.78%/35.43%/42.15%，R/F/K/B=51/93/60/19，单skill rescued仅21题。R指无skill错、有skill对；F两者错、K两者对、B无skill对而有skill错。

**这些是历史文件中的标签汇总，本轮没有审计原始回答或重新评分，不能作为新实验结果或论文证据。** 同时CHAMP的wrong准确率高于none，提示不能只展示rescued而隐去被破坏题和wrong-skill的整体效果。

## 接入前的最小验证设计（待实施）

1. 优先为LogicBench固定全部760题、19原版skill及数据版本；四模型分别进行无skill／正确skill／同任务其他skill三种单次生成。保持同一backend、精度、答案预算和解析器。不能用一个模型的rescued题池作为其他模型的唯一候选。
2. 先检查总体准确率、每skill准确率、R/F/K/B、标签混淆及截断，不从筛选后100% donor正确推导“skill总体有益”。四模型是否均有足够收益与样本仍未知。可预先设可行性目标为每模型至少50个独立有效干预题、覆盖至少10个skill；这是工程目标，不是统计充分性的证明。
3. 增加等长中性文档与generic reasoning指导对照；同逻辑任务的另一个skill可能共享有效推理步骤，不能把它自动视为完全无关。对BQA/MCQA分别报告，控制yes/no偏置。随机重排选项若实施，应固定为独立稳健性分析，不能与原版分数混报。
4. 不直接照搬整组receiver全错筛选。每组40题、且BQA答案空间小，这个筛选可能严重压缩人群。建议新benchmark主分析采用逐题fresh baselines，保留原组筛选为敏感性检查；与旧八格的口径差异要明示，最好对既有数据也追加可比的逐题重聚合（不自动改稿或重跑）。
5. 同题共用transfer/knockout基线、完整层网格、identity token-exact检查，明确skill span、模型模板与位置对齐。repair/path-cut仍按各suite独立fresh baselines筛选，不能套用depth分母。
6. 先冻结选型与可行性标准，再看深度结果；无论T<R是否成立、曲线是否陡峭，都保留并报告。有限样本的二分类曲线应辅以正确标签的连续分数，例如两个标签的log-probability差；输出解析格式和多token标签评分要单独验证。

不建议本轮直接把所有候选都跑全层：先确定一个benchmark的四模型总体skill收益，再为其安排深度、机制及控制矩阵。若LogicBench失败，应区分技能总体无益、有效题不足、评分问题与干预结论不成立；最后一种不能成为换benchmark理由。

## 文献记录（标题、出处、一句话结论及本项目关系）

1. **Skill Retrieval Augmentation for Agentic AI**，arXiv:2604.24594（2026）。六任务的现成skill配对和直接注入对照；第三任务最直接来源。[论文](https://arxiv.org/abs/2604.24594)、[代码](https://github.com/oneal2000/SR-Agents)。
2. **LogicBench: Towards Systematic Evaluation of Logical Reasoning Ability of Large Language Models**，ACL 2024，arXiv:2404.15522。单推理规则自然语言题；提供第三组的原始任务，不提供SRA版技能收益。[论文](https://aclanthology.org/2024.acl-long.739/)。
3. **Adaptive Multi-Resolution Procedural Knowledge Compression for Large Language Models**，arXiv:2606.12203（2026）。压缩技能并提供Qwen3-8B完整技能对照；补足当前模型尺度的收益证据。[论文](https://arxiv.org/abs/2606.12203)。
4. **CHAMP: A Competition-level Dataset for Fine-Grained Analyses of LLMs’ Mathematical Reasoning Capabilities**，arXiv:2401.06961（2024）。区分概念、提示及推理步骤；纯文本备选，需避免题目特定提示混入skill。[论文](https://arxiv.org/abs/2401.06961)。
5. **BigCodeBench: Benchmarking Code Generation with Diverse Function Calls and Complex Instructions**，ICLR 2025，arXiv:2406.15877。多库代码生成与执行测试；第三组可提供输出类型跨度。[官方仓库](https://github.com/bigcode-project/bigcodebench)。
6. **SELF-DISCOVER: Large Language Models Self-Compose Reasoning Structures**，NeurIPS 2024，arXiv:2402.03620。任务级推理结构可跨模型使用；独立于SRA的结构技能备选，需额外整理固定资产。[论文](https://papers.nips.cc/paper_files/paper/2024/hash/e41efb03e20ca3c231940a3c6917ef6f-Abstract-Conference.html)。
7. **In-Context Principle Learning from Mistakes**，ICML 2024，arXiv:2402.05403。由示例错误提炼可复用原则后帮助未见题；DROP/BBH备选，原则与few-shot示例需分开对照。[论文](https://proceedings.mlr.press/v235/zhang24at.html)。
8. **RuleArena: A Benchmark for Rule-Guided Reasoning with LLMs in Real-World Scenarios**，ACL 2025，arXiv:2412.08972。复杂现实规则推理困难，工具可助益；不是现成的纯文本skill收益证据。仓库近期有标签/缺失规则质疑，尚未独立核实。[论文](https://aclanthology.org/2025.acl-long.27/)、[航空标签问题报告](https://github.com/SkyRiver-2000/RuleArena/issues/5)。
9. **SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks**，arXiv:2602.12670（2026）。人工技能有整体收益，个别任务负收益；广泛但交互重，原论文与v1.1规模不同，不混用。[论文v1](https://arxiv.org/html/2602.12670v1)、[当前官网](https://www.skillsbench.ai/)。
10. **FinSkillBench: Evaluating AI Agents and Domain Skills for Investment Management**，arXiv:2608.18099（2026）。投资技能包有效但含执行程序和多轮工具；无法直接归因于纯文本。[论文](https://arxiv.org/abs/2608.18099)。
11. **SkillGym: Internalizing Large-Scale Human Skills into LLMs for Real-World Problem Solving**，arXiv:2609.27717（2026）。人类技能驱动可验证任务及训练轨迹；新近相关工作，但平均工具交互很长。[论文v1](https://arxiv.org/html/2609.27717v1)。
12. **EduSkillBench: Measuring the Impact of Agent Skills on Single-Turn Educational Tasks**，Preprints.org:202608.2214（2026，预印本）。单轮教育输出有观察收益；42题且skill-aligned rubric导致解释限制，不宜作为当前主证据。[论文](https://www.preprints.org/manuscript/202608.2214)。
13. **Skill Blocks: How Should an Agent Load Its Skill? A Caching-Correct Comparison of Pre-load, On-Demand Tool-Loading, Progressive Disclosure, and Hybrid**，arXiv:2608.14943（2026）。主要比较加载方式和成本；不足以代替与无skill对照的有效性证据。[论文](https://arxiv.org/abs/2608.14943)。
14. **Meta Context Engineering via Agentic Skill Evolution**，arXiv:2601.21557（2026）。演化上下文有收益，但元层skill与供求解器使用的上下文不同，不能混为单skill直接增强；USPTO对小模型有上下文长度限制。[论文](https://arxiv.org/html/2601.21557v1)。
15. **Transformers as Soft Reasoners over Language**，arXiv:2002.05867（2020）。规则推理数据和可验证标签适合作机制任务，但需要另行建立可复用skill收益。[官方RuleTaker仓库](https://github.com/allenai/ruletaker)。
16. **SkillBenchmark**，社区开源项目，非已核实论文。支持单轮原始文本调用，但judge依赖强，不作为成熟benchmark替代。[仓库](https://github.com/TiesPetersen/SkillBenchmark)。

## 未解决问题与下一动作

- 当前四模型在LogicBench的fresh baseline收益、可用题数与skill组覆盖尚无新证据；已有论文不能保证当前四模型都有效。
- BigCodeBench单skill子集规模、当前官方版本与SRA的题目对应、完整依赖体积未核查；未下载依赖或数据。
- 本地旧LogicBench/CHAMP资产与HF最新commit未逐字对比，旧输出未独立重判。
- 如果选择全部来自SRA，能够扩展任务，但仍未消除skill构建来源单一的问题。若论文诉求是跨skill来源泛化，应考虑固定SELF-DISCOVER结构的BBH子任务，代价是额外构建与验证。
- 下一条可执行动作：固定LogicBench数据/skill版本和预注册筛选标准，编写最小三基线评估与评分自检，再讨论GPU试验；本次任务止于调研交付。
