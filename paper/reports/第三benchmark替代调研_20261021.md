# 第三benchmark替代方案（2026-10-21）

用户已放弃CHAMP；本报告只比较替代方案，不新增GPU实验、不改当前4模型×2benchmark论文。清理范围与回执在 `experiments/benchmark_replacement_20261021/`。

## 判断

**若优先保持现有数值问答形式，建议先核查GSM8K＋公开数学过程模板；若优先复用现成题目—skill配对，LogicBench最方便，但不能原样照搬整组receiver全错筛选。** 当前没有一个已验证满足所有原协议、可直接替换的候选。不能把“有论文报告收益”当作当前四模型和固定干预协议已验证。

原论文研究对象是一次提供可复用文本skill、生成完整解答后抽取最终答案。候选选择应基于答案形式、skill来源、覆盖和公平比较，而不依据深度曲线是否满足T<R或缓存修复是否为正。

## 候选比较

|候选|已核验资产|与当前形式的关系|主要缺口|建议|
|---|---|---|---|---|
|GSM8K＋BoT数学模板|官方测试集1319题；BoT公开21类定义/公式/解题步骤/例题|纯文本、多步解答、最后抽取数值；可将单个模板放入source span|GSM8K没有原生逐题skill标注；21类模板与1319题的覆盖、单skill可解释性、孤立文本收益未验证|优先做静态映射可行性核查，尚不是可直接正式跑的成品|
|SRA-LogicBench＋19逻辑skills|本地760题，19组各40题；542二分类/218多选；现成一题一skill|一次生成解释后抽取标签，现有span引擎改造少|短答案易偶然答对；整组receiver全错筛选可能接近空；语义相近wrong也可能帮助|条件备选；先解决一致的筛选规则，不能只为新任务单独放宽|
|BBH算法子任务＋固定SELF-DISCOVER结构|object_counting、多步算术、word_sorting各250题，前两者全为整数答案|数值或词列表输出；任务级结构可离线固定、测试时一次使用|这里只有3种task级skill；完整发布结构及输入—skill映射需整理；单组250题会使原组筛选更严|第二候选；适合补充证据，不自动等同原生skill benchmark|
|SRA-BigCodeBench＋库skills|最新官方1140题，单skill题数为0；577种精确skill集合，710题有同集合跨题候选|一次生成代码后执行测试|全部多skill；代码输出、依赖环境和较长上下文同时改变；不能取“单skill子集”解决|本轮不优先；若日后选，须显式采用多skill组合协议|
|SciBench＋过程说明|成熟大学数学/物理/化学数值问答|答案形式匹配|原论文的10类problem-solving skills是误差分析类别，不是现成增强文档；没有核实可复用skill配对及单次注入收益|暂不作为现成替换|
|DROP/GSM8K＋LEAP原则|ICML 2024报告可复用原则增强收益|短答案，最终推理可单次|原方法把原则与few-shot示例一起使用；不能把全部收益归因纯skill，更不能直接挪动含示例的span|后备来源，需隔离原则贡献与控制示例|

统计由 `inspect_public_assets.py` 对原作者公开JSON/text只读计算，保存URL、大小和SHA256，未保留整份新数据或运行模型；本地LogicBench统计单列 `logicbench-static.json`。这些是资产可用性证据，不是四模型效果证据。

## 原组级筛选不能忽略

原depth要求一个skill组里的receiver回答全部错误，再逐题要求gold正确、none错误。组越大、答案空间越小，这个条件越难成立。

独立同分布的**说明性近似**：每题wrong receiver答对概率为p、组有m题时，整组保留概率为 `(1-p)^m`。这不是实测模型估计，题间相关性会改变结果。LogicBench m=40；即使p只有0.1，整组保留约1.48%，19组期望仅0.28组。若纯随机二分类p=0.5，整组保留约9.1×10^-13。GSM8K/BBH同样受组大小影响，不能靠换任务隐去这个限制。

因此有两条清楚的路线：

1. **严格保持当前组级主分析**：只按该规则检查候选的可行性，接受可能无足够有效题；不能为了让新任务能跑而拆小组、挑wrong文档或缩题。
2. **统一采用逐题fresh baselines作为新的可比分析**：同时对原MedCalc/TheoremQA可用数据重聚合，保留原组级结果作敏感性对照；明确估计人群改变。机制仍按各suite自己的新基线筛选。此路线是协议修改，不能伪装为仅增加benchmark，本轮未实施。

LogicBench可以保留作为现成skills首选核验对象，但不应在这个矛盾未处理前直接开完整深度矩阵。

## GSM8K＋公开模板的最小准备

1. 冻结官方1319题测试集和21类公开模板的版本/SHA；输入—skill标注仅看题面，不能看四模型表现、干预结果或最终评测答案来选skill。
2. 人工核验模板公式、例题及适用条件。先统计每类覆盖、跨题donor、天然多模板需求、未覆盖题；“Equation Problem”不能自动作为所有题的通用兜底。若仅覆盖子集，预先定义并明确命名，不称完整GSM8K。
3. 对模板示例做测试题/解答重叠检查；skill应提供可复用程序，不能塞入当前题答案。原BoT有检索、实例化、动态更新及部分代码执行，当前方案只冻结文本模板，属于新的受控适配。
4. 确定统一筛选口径后，再做四模型none/gold/fixed-wrong完整基线；报告整体收益/损害、截断和人群覆盖。收益与有效人数用于可行性判断；T<R和repair正负不能用作数据/skill选择条件。
5. 不默认更大题库必然提供更多有效题，也不预设小模型/强模型均有skill收益；若模板增益不够，应如实报告，不按深度结果反复换源。

## 原始文献与本项目关系

- **Skill Retrieval Augmentation for Agentic AI**，arXiv:2604.24594，2026：发布成熟的一题—skill配对来源；LogicBench接入最直接，原两任务也来自这一来源。[原作者项目页](https://sr-agents.github.io/)、[官方数据](https://huggingface.co/datasets/WeihangSu/SRA-Bench)。
- **Adaptive Multi-Resolution Procedural Knowledge Compression for Large Language Models**，arXiv:2606.12203，2026：Full Text列给出未压缩技能对照，Qwen3-8B LogicBench为77.11→85.26%；其训练压缩结果不等同本项目原模型skill注入效果。[论文](https://arxiv.org/html/2606.12203v1)。
- **Buffer of Thoughts: Thought-Augmented Reasoning with Large Language Models**，NeurIPS 2024 Spotlight，arXiv:2406.04271：研究模板复用，官方仓库含21类数学模板；完整方法收益不能直接归于本项目拟用的固定文本单次注入。[官方代码](https://github.com/YangLing0818/buffer-of-thought-llm)、[数学模板](https://raw.githubusercontent.com/YangLing0818/buffer-of-thought-llm/main/math.txt)。
- **Training Verifiers to Solve Math Word Problems**，arXiv:2110.14168，2021：GSM8K原始任务来源，官方test为1319题；提供数值答案评分，不自带21类skill标注。[官方数据仓库](https://github.com/openai/grade-school-math)。
- **SELF-DISCOVER: Large Language Models Self-Compose Reasoning Structures**，NeurIPS 2024，arXiv:2402.03620：BBH使用task级可复用结构，MATH分支则为instance级结构，二者不可混用；前者可离线冻结供一次生成使用。[论文](https://arxiv.org/html/2402.03620v1)、[BBH原始任务](https://github.com/suzgunmirac/BIG-Bench-Hard)。
- **In-Context Principle Learning from Mistakes**，ICML 2024，arXiv:2402.05403：原则可用于未见样本，但与few-shot示例共同输入；适合作skill来源后备，需单独拆解贡献。[正刊](https://proceedings.mlr.press/v235/zhang24at.html)。
- **BigCodeBench: Benchmarking Code Generation with Diverse Function Calls and Complex Instructions**，ICLR 2025，arXiv:2406.15877：可执行评分任务，但本次SRA发布没有单skill题，接入会改变输出类型与组合设置；官方仓库当前已归档，环境需固定。[官方仓库](https://github.com/bigcode-project/bigcodebench)、[SRA原始JSON](https://huggingface.co/datasets/WeihangSu/SRA-Bench/blob/main/instances/bigcodebench.json)。
- **SciBench: Evaluating College-Level Scientific Problem-Solving Abilities of Large Language Models**，ICML 2024，arXiv:2307.10635：数值科学题答案形式合适，但原研究未提供本次所需现成的文本skill增强配对。[原论文](https://arxiv.org/abs/2307.10635)。
- **FlowEvo: Self-Evolving Agents through the Co-Evolution of Workflows and Executable Skills**，COLM 2026，arXiv:2607.21596：新近程序性skill复用工作，涉及可调用技能与推理时演化，不作为现成的冻结纯文本单次注入benchmark。[原论文](https://arxiv.org/abs/2607.21596)。

## 当前结论

优先级是**GSM8K＋公开数学模板的静态映射可行性**，其次是**解决筛选一致性后的LogicBench**，BBH算法子集作为补充。没有启动任何新GPU、下载模型、修改论文或Overleaf。先解决输入/skill标注与筛选，再讨论正式推理；不直接在未经核验的新组合上跑完整机制矩阵。
