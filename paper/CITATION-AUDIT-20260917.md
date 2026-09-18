# 引用核查记录

日期：2026-09-17。检查范围为原版 `skillvector.bib` 的 48 条记录：47 条 arXiv 页面及 1 条作者机构博客。标题、作者与标识符逐项对照公开一手来源；正文关键论断另检查摘要及正刊页面。该检查不等同于逐篇复现被引论文。

## 已修正的书目信息

- Sia et al. 的 NeurIPS 2024 正刊标题是 **Where does In-context Learning Happen in Large Language Models?**，原条目混用了预印本中的 Translation 标题和正刊会议信息。[正刊页面](https://proceedings.neurips.cc/paper_files/paper/2024/hash/3979818cdc7bc8dbeec87170c11ee340-Abstract-Conference.html)。保留原 cite key，避免引用断裂。
- Dong et al. 的 **Emergent Response Planning in LLMs** 已发表于 ICML 2025，更新原 arXiv-only 条目。[PMLR](https://proceedings.mlr.press/v267/dong25p.html)。
- Liu et al. 的正刊作者字段补齐 **James Y. Zou**。[PMLR](https://proceedings.mlr.press/v235/liu24bx.html)。
- SRA-Bench 作者由 `Su, Weihang and others` 补为 arXiv 上的完整九人列表。
- Dong et al. 的 task-vector 论文 ICLR 2026 出处已由[正式 proceedings](https://proceedings.iclr.cc/paper_files/paper/2026/hash/20dcab0f14046a5c6b02b61da9f13229-Abstract-Conference.html)验证。
- Mehrafarin et al. 的 arXiv 页面明确注明 “To appear in Findings of EMNLP 2026”，保留该出处。

## 逐项核查与本项目的关系

| 标题 | 一手来源 | 一句话结论与用途 |
|---|---|---|
| In-Context Learning Creates Task Vectors | [arXiv:2310.15916](https://arxiv.org/abs/2310.15916) | 示例上下文可形成可转移任务向量；对照本文单位置干预。 |
| Function Vectors in Large Language Models | [arXiv:2310.15213](https://arxiv.org/abs/2310.15213) | 识别和干预功能向量；对照紧凑任务表示。 |
| Editing Models with Task Arithmetic | [arXiv:2212.04089](https://arxiv.org/abs/2212.04089) | 权重空间的任务向量支持模型编辑；与本文激活空间干预区分。 |
| Towards Best Practices of Activation Patching in Language Models: Metrics and Methods | [arXiv:2309.16042](https://arxiv.org/abs/2309.16042) | 激活修补结论依赖指标与干预方法；支持匹配对照设计。 |
| How to use and interpret activation patching | [arXiv:2404.15255](https://arxiv.org/abs/2404.15255) | 说明激活修补的实施与解释；支持因果干预方法。 |
| Just-in-time and distributed task representations in language models | [arXiv:2509.04466](https://arxiv.org/abs/2509.04466) | 任务表征可随计算动态分布；补充单向量假设的背景。 |
| Where does an LLM begin computing an instruction? | [arXiv:2511.10694](https://arxiv.org/abs/2511.10694) | 逐层干预研究指令计算起点；与深度边界比较。 |
| A Mechanistic Lens on Semantic Conflicts: Using Activation Patching to Understand LLM Behavior | [arXiv:2607.05587](https://arxiv.org/abs/2607.05587) | 以激活修补研究语义冲突；附录相关机制工作。 |
| How Do LLMs Cite? A Mechanistic Interpretation of Attribution in Retrieval-Augmented Generation | [arXiv:2606.28358](https://arxiv.org/abs/2606.28358) | 研究检索增强生成的引用行为；附录信息迁移比较。 |
| SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks | [arXiv:2602.12670](https://arxiv.org/abs/2602.12670) | 评测 skills 在多种任务上的收益；引言的行为评测背景。 |
| SkillsInjector: Dynamic Skill Context Construction for LLM Agents | [arXiv:2605.29794](https://arxiv.org/abs/2605.29794) | 研究动态构建 skill context；附录 skill 使用方式比较。 |
| SWE-Skills-Bench: Do Agent Skills Actually Help in Real-World Software Engineering? | [arXiv:2603.15401](https://arxiv.org/abs/2603.15401) | 评测软件工程任务中的 agent skills；Related Work 的行为评测背景。 |
| Skill-to-LoRA: From Using Skills to Learning Behaviors for Token-Efficient LLM Agents | [arXiv:2606.16769](https://arxiv.org/abs/2606.16769) | 将 skill 转换为 LoRA；与推理时已有表示区分。 |
| Understanding Task Vectors in In-Context Learning: Emergence, Functionality, and Limitations | [arXiv:2506.09048](https://arxiv.org/abs/2506.09048) | 分析任务向量与单示例等价关系及高秩映射失效；区分 task-map rank 与 representation rank。 |
| When Chain-of-Thought Fails, the Solution Hides in the Hidden States | [arXiv:2604.23351](https://arxiv.org/abs/2604.23351) | 通过已完成推理轨迹中的隐状态恢复答案；区分推理前 donor 与推理后 donor。 |
| Answer, Assemble, Ace: Understanding How LMs Answer Multiple Choice Questions | [arXiv:2407.15018](https://arxiv.org/abs/2407.15018) | 分析选择题答案符号决策的形成；解释答案格式实验。 |
| Steering off Course: Reliability Challenges in Steering Language Models | [arXiv:2504.04635](https://arxiv.org/abs/2504.04635) | 评估 steering 的可靠性；附录紧凑干预的实证比较。 |
| Mechanistic Interpretability of Chain-of-Thought Reasoning via Sequential Activation Patching | [arXiv:2608.22332](https://arxiv.org/abs/2608.22332) | 沿生成轨迹进行连续激活修补；支持静态位置不足以描述长推理的动机。 |
| Prompt Compression via Activation Aggregation | [arXiv:2607.08399](https://arxiv.org/abs/2607.08399) | 学习加权聚合激活压缩提示；明确它使用训练过的聚合器。 |
| Causal Dimensionality of Transformer Representations: Measurement, Scaling, and Layer Structure | [arXiv:2605.08740](https://arxiv.org/abs/2605.08740) | 以 Jacobian 相关量定义因果维度；与本文注入矩阵的秩不同。 |
| Dynamics of the Transformer Residual Stream: Coupling Spectral Geometry to Network Topology | [arXiv:2605.14258](https://arxiv.org/abs/2605.14258) | 研究 Jacobian 与跨层算子的谱结构；与本文表示矩阵不同。 |
| Doc-to-LoRA: Learning to Instantly Internalize Contexts | [arXiv:2602.15902](https://arxiv.org/abs/2602.15902) | 学习把上下文内化为 LoRA；与激活注入路径比较。 |
| Training Plug-n-Play Knowledge Modules with Deep Context Distillation | [arXiv:2503.08727](https://arxiv.org/abs/2503.08727) | 训练深层上下文蒸馏模块；与无额外训练的干预比较。 |
| When Context Returns: Toward Robust Internalization in On-Policy Distillation | [arXiv:2606.11627](https://arxiv.org/abs/2606.11627) | 讨论蒸馏内化后的上下文鲁棒性；附录相关内化工作。 |
| Massive Activations in Large Language Models | [arXiv:2402.17762](https://arxiv.org/abs/2402.17762) | 发现少量位置与维度上的超大激活；支撑 participation ratio 伪影诊断。 |
| A Single Layer to Explain Them All:Understanding Massive Activations in Large Language Models | [arXiv:2605.08504](https://arxiv.org/abs/2605.08504) | 研究超大激活的层级起源；支撑逐层检查异常激活。 |
| MedCalc-Bench: Evaluating Large Language Models for Medical Calculations | [arXiv:2406.12036](https://arxiv.org/abs/2406.12036) | 提供临床计算评测；本文主要题目与评分来源。 |
| Skill Retrieval Augmentation for Agentic AI | [arXiv:2604.24594](https://arxiv.org/abs/2604.24594) | 提出 SRA 并提供 SRA-Bench；本文外部 skills 与第二任务来源。 |
| Qwen3 Technical Report | [arXiv:2505.09388](https://arxiv.org/abs/2505.09388) | Qwen3 模型技术报告；模型来源。 |
| Mistral 7B | [arXiv:2310.06825](https://arxiv.org/abs/2310.06825) | Mistral 7B 技术报告；模型家族来源，不单独证明 v0.3 的全部实现细节。 |
| Locating and Editing Factual Associations in GPT | [arXiv:2202.05262](https://arxiv.org/abs/2202.05262) | 定位和编辑事实关联；对照已有因果追踪方法。 |
| Dissecting Recall of Factual Associations in Auto-Regressive Language Models | [arXiv:2304.14767](https://arxiv.org/abs/2304.14767) | 解析事实召回的信息流；对照逐层表示转移。 |
| Where does In-context Translation Happen in Large Language Models | [arXiv:2403.04510](https://arxiv.org/abs/2403.04510) | 通过 context masking 研究任务识别边界；使用 NeurIPS 正刊标题修正旧预印本标题。 |
| Label Words are Anchors: An Information Flow Perspective for Understanding In-Context Learning | [arXiv:2305.14160](https://arxiv.org/abs/2305.14160) | 分析标签词的信息汇聚作用；附录信息流比较。 |
| All Bark and No Bite: Rogue Dimensions in Transformer Language Models Obscure Representational Quality | [arXiv:2109.04404](https://arxiv.org/abs/2109.04404) | 少数异常维度影响相似度统计；支持几何测量需要异常检查。 |
| BERT Busters: Outlier Dimensions that Disrupt Transformers | [arXiv:2105.06990](https://arxiv.org/abs/2105.06990) | 异常维度可干扰 Transformer；补充谱与相似度诊断背景。 |
| Learning to Compress Prompts with Gist Tokens | [arXiv:2304.08467](https://arxiv.org/abs/2304.08467) | 训练 gist tokens 压缩提示；区别于未训练的单位置写入。 |
| In-context Autoencoder for Context Compression in a Large Language Model | [arXiv:2307.06945](https://arxiv.org/abs/2307.06945) | 训练上下文自编码器压缩上下文；区别于自然计算中的表示。 |
| In-context Vectors: Making In Context Learning More Effective and Controllable Through Latent Space Steering | [arXiv:2311.06668](https://arxiv.org/abs/2311.06668) | 通过激活向量进行上下文 steering；区分持续干预与一次写入。 |
| Improving Instruction-Following in Language Models through Activation Steering | [arXiv:2410.12877](https://arxiv.org/abs/2410.12877) | 通过 activation steering 改善指令遵循；相关干预方法。 |
| Steering Llama 2 via Contrastive Activation Addition | [arXiv:2312.06681](https://arxiv.org/abs/2312.06681) | 对比激活相加引导生成；区分多个位置重复注入。 |
| Emergent Response Planning in LLMs | [arXiv:2502.06258](https://arxiv.org/abs/2502.06258) | 隐状态可预测未来响应属性；是 probing 证据，不等价于可因果转移全部响应。 |
| Is This the Subspace You Are Looking for? An Interpretability Illusion for Subspace Activation Patching | [arXiv:2311.17030](https://arxiv.org/abs/2311.17030) | 子空间干预可能激活非自然使用的路径；解释 rank 干预的范围。 |
| How do Language Models Bind Entities in Context? | [arXiv:2310.17191](https://arxiv.org/abs/2310.17191) | 研究上下文中的实体绑定；为早期绑定影响晚期读出提供可能解释。 |
| The geometry of hidden representations of large transformer models | [arXiv:2302.00294](https://arxiv.org/abs/2302.00294) | 研究隐藏表示几何；区分描述性谱统计和因果截秩。 |
| Artifacts or Abduction: How Do LLMs Answer Multiple-Choice Questions Without the Question? | [arXiv:2402.12483](https://arxiv.org/abs/2402.12483) | 选择题可利用答案选项伪影；支持选择题格式诊断。 |
| Rethinking the Role of Demonstrations: What Makes In-Context Learning Work? | [arXiv:2202.12837](https://arxiv.org/abs/2202.12837) | 示例的格式与分布也可影响 ICL；附录内容和存在效应的背景。 |
| Defeating Nondeterminism in LLM Inference | [Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) | 作者署名 Horace He，与 Thinking Machines 同事合作；支持 kernel 与浮点运算导致输出差异的背景，不替代本文自己的故障诊断。 |

## 改写时收窄的引用性表述

- 不再把线性 transformer 中的 task-map 结论写成所有 LLM 单向量的普适上限。
- 明确 learned activation aggregation 和 gist/context autoencoder 使用学习得到的压缩机制。
- 不再以本文 residual-state 伪影直接断言其他论文测量不同数学对象的谱结论无效。
- 正文不再声称自己是所有 rank 工作中唯一做因果截断的论文；直接说明所截断的对象和读出指标。

