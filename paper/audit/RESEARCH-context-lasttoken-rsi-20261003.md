# 当前正文的 context/prompt、last-token 与 RSI 研究定位

日期：2026-10-03。对象：`paper/sections/00-abstract.tex` 至 `05-conclusion.tex`，尤其 §4.4 位置预算、§4.6 rank、§4.7 深度。用户已确认 RSI 指 Recursive Self-Improvement（递归自我改进）。

本轮是文献与研究设计审查，未进行模型实验；本地数字来自当前正文及已有结果文件，不等于本轮独立重跑。外部论文的实验结论均为作者报告。本报告区分领域已有发现、当前项目结果、我们的推断与待验证假说，不主张搜索穷尽。

## 1. 判断

1. 我们属于 context/instruction 的机制解释谱系，不是只与 agent skill benchmark 有关。把 context 改叫 skill 不构成科学创新。
2. 单位置注入、内容差分、源文本位置 patch、跨层扫描、累计 attention masking、长输出中转移失效，分别都有先例。最有潜力的贡献是**在长程序文档上，匹配比较位置结构及表示 rank，并在同一任务/模型/筛选口径下分离“可转移”与“仍被使用”的边界**。
3. 当前是有价值的因果现象论文候选，但机制解释还不闭合。最值得补的是能区分两种解释的实验，而不是再加几条相同趋势的曲线。
4. 不能据此判断已经足够成为强 WWW 投稿：除了科学性，当前正文缺少明确 Web 科学问题，存在范围风险；不是换成 ACM 模板或在引言加入 agent 即可解决。
5. RSI 可以连接，但应作为独立问题推进。已有 self-evolving skill 工作做过技能贡献、组合干扰和跨域反转。新空间在**内部计算怎样中介可继承的技能改进，尤其 meta-skill 怎样提高下一轮改进能力**，而不是再做一次结果分数审计。

## 2. 文献地图：方法、贡献与本项目关系

阅读深度：F=查全文相关方法/结果；A=核查一手摘要/会议记录，未逐项复核全文。未核实正式录用的条目仅标 arXiv，不从第三方网页推断会议。

| 工作及一手出处 | 方法与一句话结论 | 对我们的影响 | 阅读 |
|---|---|---|---|
| Olsson et al., **In-context Learning and Induction Heads**, 2022, [arXiv:2209.11895](https://arxiv.org/abs/2209.11895) | 观察训练过程、匹配/复制行为和 head ablation；小 attention-only 模型提供强因果证据，大模型证据较间接。 | 已有工作不仅观察热图，也干预实现上下文计算的组件；我们尚未定位可解释的执行电路。 | A |
| Wang et al., **Label Words are Anchors: An Information Flow Perspective for Understanding In-Context Learning**, EMNLP 2023, [arXiv:2305.14160](https://aclanthology.org/2023.emnlp-main.609.pdf) | 用梯度相关的 saliency（显著性/敏感度）分析及屏蔽检验浅层汇集到标签、深层读取标签的路径，并用于压缩和重加权。 | “上下文信息存放在源 token 并在后续读取”不是新命题；我们对象是长程序文档和持续生成。 | F |
| Hendel et al., **In-Context Learning Creates Task Vectors**, Findings EMNLP 2023, [arXiv:2310.15916](https://aclanthology.org/2023.findings-emnlp.624.pdf) | few-shot + dummy query 的最后箭头 token 状态，在相同层替换 zero-shot 真 query 的最后箭头；开发集选层，主任务限单 token 输出。 | last-token replacement 的直接先例；dummy query 避免搬运目标题答案。 | F |
| Todd et al., **Function Vectors in Large Language Models**, ICLR 2024, [arXiv:2310.15213v2](https://arxiv.org/html/2310.15213v2) | 将正确示例的平均 attention-head 输出 patch 到乱标签运行，筛选因果影响大的 heads；聚合为 FV，加到新 prompt 末位置。 | 我们替换整 residual 不等于完整复现 FV；FV 的 head 提取与跨 query 泛化不可省略后再宣称击败。 | F |
| Yin & Steinhardt, **Which Attention Heads Matter for In-Context Learning?**, ICML 2025, [PMLR 267](https://proceedings.mlr.press/v267/yin25e.html), arXiv:2502.14010 | 12 模型的 head ablation 比较 induction 与 FV heads，报告较大模型的 few-shot ICL 更依赖后者。 | 若要解释 skill 如何执行，可比较具体 heads；不能将一类上下文机制视为普遍解释。 | A |
| Davidson et al., **Do different prompting methods yield a common task representation in language models?**, [arXiv:2505.12075v3](https://arxiv.org/html/2505.12075) | 从短指令和示例分别提取 FV，采用无关文本/其他任务指令等控制；两者涉及部分不同 heads，组合有互补效应。 | “从示例扩展到指令”已经被做过；skill 中 procedure 与 example 的区别有直接先例。 | F |
| Dong et al., **Understanding Task Vectors in In-Context Learning: Emergence, Functionality, and Limitations**, ICLR 2026, [会议记录](https://proceedings.iclr.cc/paper_files/paper/2026/hash/20dcab0f14046a5c6b02b61da9f13229-Abstract-Conference.html), [arXiv:2506.09048](https://arxiv.org/html/2506.09048v1) | 线性 Transformer 理论、双射任务及 saliency，预测单 TV 的高秩映射限制，并把多 TV 注入 few-shot 各箭头位置。 | 多向量修复单向量不足不新；其映射 rank 不同于我们的跨位置差分矩阵 rank。不要把线性模型定理当作所有 LLM 的容量定理。 | F |
| Li et al., **Just-in-time and distributed task representations in language models**, [arXiv:2509.04466v3](https://arxiv.org/html/2509.04466) | 对多个 token 做状态移植，另训练线性 probe 解码 task identity；加入重复、列表、混合子任务，区分可解码与可转移表示，Gemma 与 Qwen 复现。 | 最近邻之一：已研究时间局部性、语义范围与长输出衰减。v3 也明确单 TV 可以支持某些长输出，不能简化成“长答案一定失败”。 | F |
| Sia et al., **Where does In-context Learning Happen in Large Language Models?**, NeurIPS 2024, [论文](https://www.cs.jhu.edu/~kevinduh/papers/sia24where.pdf), arXiv:2403.04510 | 从某层起屏蔽示例/指令/query，另分析单层和 head gate；翻译与代码生成显示不再依赖 context attention 的深度。 | 累计 context knockout 与 reading boundary 有直接先例；我们的新增是与 span transfer 在相同设置下配对比较。 | F |
| Pola & Balasubramanian, **Where does an LLM begin computing an instruction?**, 2025 workshop extended abstract / [arXiv:2511.10694v1](https://arxiv.org/html/2511.10694v1) | 最小指令对比，分别 patch 关键词、content-control 和最后 context token，观察答案翻转率的层间变点。 | 直接覆盖源指令位置 vs 最后位置、以及晚层移植失效；未见同样的累计读取敲除配对。其“晚层不再重读”的解释不能仅由 patch 失败推出。 | F |
| Bigoulaeva et al., **Patches of Nonlinearity: Instruction Vectors in Large Language Models**, ACL 2026, [会议记录](https://aclanthology.org/2026.acl-long.559/), [arXiv:2602.07930v2](https://arxiv.org/html/2602.07930v2) | 比较 base/SFT/DPO；将指令末 token 状态移到 query 前 filler；多层 patch 发现非加性交互，并用局部映射及路径分析探究 circuit selection。 | **现稿遗漏的重要近邻**：query 前的 instruction token 可以承载可转移信息，且单层失败可来自组件交互；应补 skill 末 token、多层对应控制。 | F |
| Stolfo et al., **Improving Instruction-Following in Language Models through Activation Steering**, ICLR 2025, [arXiv:2410.12877v2](https://arxiv.org/html/2410.12877v2) | 从有/无指令的末 token 差分均值提取方向，在一个层的所有 token 位置实施 steering，控制格式、长度、关键词。 | **抽取位置与施加位置不是一回事**；我们的 prefill 一次注入不能排除 decode 持续注入。 | F |
| Feng & Steinhardt, **How do Language Models Bind Entities in Context?**, ICLR 2024, [arXiv:2310.17191](https://proceedings.iclr.cc/paper_files/paper/2024/hash/9d1b7fc578c0d2d6431fc26d736ecaf3-Abstract-Conference.html) | 用因果干预分离实体内容和 binding ID，检验可组合及跨任务性质。 | 可借鉴的机制深度：我们的连续性是否来自变量—公式—步骤的绑定，尚无实验识别。 | A |
| Liu et al., **Lost in the Middle: How Language Models Use Long Contexts**, TACL 2024, [论文](https://aclanthology.org/2024.tacl-1.9/), arXiv:2307.03172 | 改变相关信息在长输入中的位置，在问答与键值检索上测行为。 | 输入布局效应是已有发现；我们的隐藏态位置干预不等于证明真实文本切块/重排也有相同影响。 | A |
| Mu et al., **Learning to Compress Prompts with Gist Tokens**, NeurIPS 2023, [arXiv:2304.08467](https://arxiv.org/abs/2304.08467) | 用训练和 attention bottleneck 将 prompt 信息编码成 gist token。 | 学到的压缩表示与原模型自然出现的状态不同；未经训练的 patch 失败不能推翻压缩可能性。 | A |
| Ge et al., **In-context Autoencoder for Context Compression in a Large Language Model**, ICLR 2024, [arXiv:2307.06945](https://arxiv.org/abs/2307.06945) | 训练编码器将 context 压入较少 memory slots，再供语言模型使用。 | 同上；若要宣传压缩收益，需要比较额外训练成本与真实生成行为。 | A |
| Ardoin et al., **Prompt Compression via Activation Aggregation**, 2026, [arXiv:2607.08399v1](https://arxiv.org/html/2607.08399v1) | 学习激活加权聚合，将一个 patch vector 写入 placeholder；在其任务上实现 prompt 压缩。 | 不能把原生最后位置失败表述为任意单向量压缩不可能；可作为学习式对照，但不是同一 estimand。 | F |
| Dura et al., **Mechanistic Interpretability of Chain-of-Thought Reasoning via Sequential Activation Patching**, 2026, [arXiv:2608.22332](https://arxiv.org/abs/2608.22332) | 把干预扩展到推理生成序列。 | 需区分生成前静态 patch 与逐生成步骤的干预；本轮只核查摘要，不据此声称特定实现细节。 | A |
| Zhang & Nanda, **Towards Best Practices of Activation Patching in Language Models: Metrics and Methods**, ICLR 2024, [arXiv:2309.16042](https://arxiv.org/abs/2309.16042)；Heimersheim & Nanda, **How to use and interpret activation patching**, [arXiv:2404.15255](https://arxiv.org/abs/2404.15255) | 系统讨论 corruption、读数、干预与结论边界。 | 身份控制只是仪器正确性，不证明干预恢复了原计算路径。 | A |
| Makelov et al., **Is This the Subspace You Are Looking for? An Interpretability Illusion for Subspace Activation Patching**, ICLR 2024, [arXiv:2311.17030](https://arxiv.org/abs/2311.17030) | subspace patch 可能借助非原生机制改变输出，产生解释错觉。 | rank 恢复曲线是该干预族的行为性质，不直接是原计算的内在维度。 | A |
| Vaidyanathan et al., **The Curse of Multiple Mediators: Hidden Interaction Effects in Activation Patching**, 2026, [arXiv:2606.27510v1](https://arxiv.org/html/2606.27510v1) | 因果中介分解与 IOI 实验强调 patch 效果依赖未替换组件的状态和交互。 | 为“晚层 donor skill 与 wrong receiver 已有状态不兼容”提供明确候选解释；不是我们已证明的机制。 | F |

几类方法的证据强度不同：attention 可视化/显著性是候选定位；probe 成功只证明可解码；activation patching 检验指定接收态下的恢复；ablation 检验指定破坏方式下的依赖；path patching 检验选定路径；训练式压缩证明可学习到替代载体。不能把这些全部统称为“看到了信息流”。

## 3. 当前贡献：哪些成立，哪些尚不够

### 3.1 可保留的新证据

- 长程序文档的内容差分在**原位 span**恢复较多效果：Qwen3-8B/MedCalc 筛选子集 n=135、14 calculators，ρ=0.89；跨任务/模型有复现。ρ=(干预准确率−receiver 准确率)/(donor 准确率−receiver 准确率)，1 为恢复完整 donor 增益，0 为无恢复。
- 原位内容、位置预算、块结构、错位、语义区段、rank 和深度共同提供比“一个向量试一下”更细的表征约束。
- 同设置下 transfer crossing 与 reading crossing 明显分离，是比任一单独边界更有价值的发现。Qwen3-8B 主结果约 L13 vs L25；这是操作性干预边界，不自动等于模型程序阶段。
- 维度截断后读取真实回答，避免只凭谱统计讲压缩；Qwen 宽度四倍而 rank knee 43/47，反驳该特定宽度正比预测，但不是普适 scaling law。

### 3.2 不能主打的泛化

- 首次发现 prompt/skill 存在内部表示、首次从文本抽取向量、首次采用 last token 或 span patch。
- 长输出必然无法由单向量控制；Li v3 与持续 steering 都提供边界反例。
- ρ=0.89 表示恢复全 benchmark 的 89% 或完整算法已被定位。主因果口径筛选了 rescued items 和 receiver 全错的技能组。
- skill 只存在于其自己的 token；模型在后续 token/缓存也可形成相关状态，patch failure 不是不存在信息。
- 删去异常大激活后的谱诊断证明不存在压缩；只能否定该统计量对原压缩解释的支持。
- “skill first 的表示不依赖后续 query”是 causal mask 的结构事实；skill-last 跨题迁移才是额外经验检验。

### 3.3 本轮查出的正文—实现问题

正文 §4.4：c1x256 vs c32x256 写成“constant budget and energy”。实现 `howskill/howskill/wb_posbudget.py` 的 `select` 为不同块数重新抽取**不同位置**，`donor = h_r[dst] + d[src]` 直接注入，未按项匹配/归一化能量。现有 JSON 为：

| arm | 写入位置数 | 平均内容差分能量份额 | 写入位置中 procedure 区段比例 | ρ |
|---|---:|---:|---:|---:|
| c1x256 | 256 | 0.290591 | 0.386169 | 0.370968 |
| c2x256 | 256 | 0.291496 | 0.279022 | 0.241935 |
| c4x256 | 256 | 0.288674 | 0.284896 | 0.217742 |
| c8x256 | 256 | 0.292319 | 0.297801 | 0.129032 |
| c16x256 | 256 | 0.292435 | 0.311690 | 0.080645 |
| c32x256 | 256 | 0.294672 | 0.307465 | 0.080645 |

来源：`whitebox/analysis/out/posbudget.json` 的 `arms`。能量很接近，但不相等；procedure 覆盖分布也不同。因此应写成“固定位置预算、平均能量接近的方案比较”，不能说其他因素完全固定。不是宣称能量差已经解释了效果；目前没有这样的证据。

此外，正文 McNemar p<1e-6 是题级配对检验；题按 calculator 聚集，不能把它当作考虑组内相关后的显著性。现有 calculator-bootstrap 的恢复差区间 [0.09,0.48] 更符合分组口径；14 个组下仍要报告逐组稳健性。这里 bootstrap 指重采样 calculator 来估计不确定性，95% CI 为该方法给出的置信区间。

本轮未修改正文、图、实验实现或历史产物，只记录审查结果。

### 3.4 最值得做的判别实验

**A. 晚层失败是“信息消失”，还是“接收计算状态不兼容”？**

在同一层/同一 prompt 对，做四格：错误运行；只换 skill span；只换预先指定的 query 状态；同时换 span+query。补反向 patch（把错误状态写到正确运行）、同运行 identity，以及不同 wrong-skill 接收方。query 范围避开直接输出瓶颈，并在独立开发集定位置，防止搬答案。若 late joint patch 恢复而 span-only 不恢复，支持交互/接收态解释；随后用具体 head 或 KV 路径做定位。若只换 query 已全恢复，则不能归因于 joint synergy。

**B. 连续性还是“完整程序单元”与 token 混合边界？**

保持 token 预算，显式匹配 procedure/example/定义覆盖、位置区间和能量分布，多个抽样种子；用等义、等长或接近等长的错误版本作 receiver，避免完全不同文档产生大量局部不一致。补“完整语义步骤”vs“切碎同一步骤”。能量归一化会改变 dose，须同时保留原 dose 控制；位置结构与语义完整性无法靠一次 shuffle 完全分离。

**C. 机制外推到系统必须另测。**

用自然文本的 procedure-preserving 截取对比随机/重要性分数截取和合理压缩基线，在相同 context token 预算下测新任务。隐藏态剪碎失败不逻辑蕴含文本剪碎失败；原生模型可能重编码改写后的 prompt。

## 4. Last token 是否合理、如何设计公平比较

合理，有直接先例，但只是一种通道假设。最后一个 prompt token 能因果访问所有前文，其最终层状态直接给出下一 token 分布；因而是检测任务选择/答案准备的自然位置，而不是已知的整份程序存储器。

| 实验谱系 | 读取哪里 | 写入哪里/何时 | 要证明什么 |
|---|---|---|---|
| Hendel TV | few-shot + dummy query 的末 token | zero-shot 新 query 末 token，同层替换 | 跨 query 的 task transfer |
| Todd FV | 最后位置的多个因果 heads，跨 prompts 均值 | 新 prompt 末位置，残差加法 | 聚合 function representation 的作用 |
| Li JIT | 末冒号及其他模板 token | zero-shot 对应 token，同层替换 | token 时间局部性、跨子任务范围 |
| Pola onset | 改变指令的关键词区段/末位置 | 基础 prompt 对应位置 | 源指令作用的层边界与晚层答案整合 |
| Bigoulaeva IV | **指令末 token，位于 query 之前** | query 前 filler，一层或多层 | 指令摘要、层间非加性交互 |
| Stolfo steering | 有/无指令的末 token 差分均值 | 一个层的所有 token 位置 | 持续生成中的格式/长度等约束 |
| 本文 | 同题正确/错误 skill 的 prompt 状态 | prefill（整段输入首次前向计算）时一次 patch，之后正常 decode | 此自然状态能否通过指定位置恢复输出 |

实现证据：`whitebox/model.py:218` 默认 `prefill_only=True`；`howskill/howskill/wb_spanpatch.py:220` 仅在首个 forward 注册 hook，随后移除再自回归生成。

**必须区分的三个 last：** prompt 的末 token、skill/instruction 的末 token、已经生成完整推理后的末 token。三者可见信息不同。现稿里的 last 是第一种。

**关键推论：**若 donor/receiver 是同题，把最终层末位置整个 residual 替换，下一 token 分布随之复制。这在单 token 答案上可以接近直接复制答案决策。成功本身不能证明 query-independent skill；早中层、dummy/其他 query donor 和新题测试更有辨识力。

因此现稿的 1.000/0.235/0.003 应解释为**该一次性干预对输出格式敏感**。MC、短数值、CoT 同时改变计算轨迹与输出方式，尚未单独识别“长度”的因果效应。更严格的长度实验需改变同一个答案的编码长度，并保持任务映射和求解要求不变。

建议的最小公平比较：prompt-last、skill-last、procedure 末尾、训练外 query 的 TV/FV、跨层单次 vs 同一方向逐生成 token 注入、原位 span。选层/强度使用独立开发集，最终测试固定；若报告测试集所有层最佳值，则标为 oracle upper envelope（事后最佳上包络），不能与调参协议不同的数字直接排名。

## 5. WWW 是否足够

来源：[WWW 2027 Research Track CFP](https://www2027.thewebconf.org/research-track-papers/)，2026-10-03 查阅。官网要求首页说明与 Web 和 track 的关系，仅使用 Web 数据/API 不够，会因范围不符 desk reject（送审前拒稿）。页面列有 Search, Recommendation, and Retrieval-Augmented AI 及 Web Infrastructure and Agentic Systems，但这不自动免除 Web 问题要求。

**科学性判断（主观审稿评估，不是录用概率）：**目前的实验量足以支撑一篇研究论文，但用旧的“单向量不够、skill 分布在多个 token”叙事，增量弱。用“可转移性与持续读取分离”作为主问题，结合连续程序单元和接收态交互做出可预测的新机制，竞争力会明显提高。方法新颖不是必要条件；可复现、令人意外且解释清楚的科学发现也可以成为核心贡献。

**范围判断：**当前主实验是无工具的 MedCalc/TheoremQA，Web 相关性未在问题和评价上建立。可考虑真实的检索增强 Web 程序文档、API 工作流或 Web agent 的技能投递/截取问题，并验证机制导出的设计对系统有效。只附加一个 Web 数据集不一定解决范围风险。如果不准备改变科学问题，NLP/ML 机制解释 venue 与现稿更自然匹配。

建议主线（不是改稿已完成）：
“For procedural context, transferable state and continued contextual dependence separate; successful transfer depends on the compatibility and structure of the transplanted states.”
其中 compatibility 当前仍是待检验解释，不可当作已验证标题结论。

## 6. RSI：已有工作与真正的连接

工作定义：普通 self-improvement 是系统更新后做任务更好；较强 RSI 要求更新被后续改进过程继承，且能测试**改进过程本身**是否更有效。系统级 RSI 不要求每轮都改基础模型权重。Transformer 深度也不是 RSI 的迭代轮数。

| 工作与出处 | 更新对象、方法和结论 | 与本项目关系 |
|---|---|---|
| **Reflexion: Language Agents with Verbal Reinforcement Learning**, NeurIPS 2023, [arXiv:2303.11366](https://arxiv.org/abs/2303.11366) | 保存语言反思以改善后续尝试。 | 外部 memory 改变输入，不直接展示内部技能计算机制。 |
| **Voyager: An Open-Ended Embodied Agent with Large Language Models**, [arXiv:2305.16291](https://arxiv.org/abs/2305.16291) | 反馈驱动生成可执行程序，积累技能库并复用。 | skill 可能由解释器执行；不能把程序执行收益全部归于 LLM 内部表示。 |
| **Gödel Agent: A Self-Referential Agent Framework for Recursive Self-Improvement**, ACL 2025, [论文](https://aclanthology.org/2025.acl-long.1354.pdf), arXiv:2410.04444 | 自修改 agent 逻辑，按目标反馈改进。 | 系统自修改先例，不是本文仅研究一次 forward 的同一对象。 |
| **Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents**, [arXiv:2505.22954](https://arxiv.org/abs/2505.22954) | 自修改代码、评测与开放式 archive 搜索；报告编码基准增益。 | 需要区分工具、搜索、context 管理与真正程序内容的作用。 |
| **GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning**, [arXiv:2507.19457](https://arxiv.org/abs/2507.19457) | 从执行轨迹做自然语言反思、变异和 Pareto 候选组合。 | 可作为改进 skill 文本的强基线；仅换成 patch 分数选择候选未必有增量。 |
| **Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models**, [arXiv:2510.04618v3](https://arxiv.org/html/2510.04618v3) | generation/reflection/curation 与增量 playbook 更新，避免整段重写丢失细节。 | 最容易衔接的外部技能迭代载体；context collapse 的文本层问题不等于隐藏态 rank collapse。 |
| **HyperAgents**, [arXiv:2603.19461v1](https://arxiv.org/html/2603.19461v1) | 冻结基础模型，把 task agent 与修改它的 meta agent 放在可编辑程序内；消融固定 meta agent。 | 给“改善下一轮改进效率”的正确对照；其主实验仍固定 parent selection，不是任意部件完全自演化。 |
| **Recursive self-improvement of AI research agents**, [arXiv:2609.26457v1](https://arxiv.org/html/2609.26457v1)，2026-09-22 | AIDE² 双层 agent 搜索，八天七次接受改进，并测试外部基准。 | 最新相关工作；作者同时说明新 agent 在外层改进角色上相对强基线尚无法决定性区分，不能把 task 提升当作改进能力已显著提升。 |
| **Evolving Programmatic Skill Networks**, [arXiv:2601.03509v2](https://arxiv.org/abs/2601.03509) | 程序技能组合网络、故障定位、按成熟度更新和可回滚重构。 | “skill 复合/干扰/持续保留”已被系统研究；我们的增量应是模型内部因果解释。 |
| **Coalition-Aware Skill Reliability for Self-Evolving Agents**, [arXiv:2608.22610v1](https://arxiv.org/html/2608.22610v1) | 对 skill bank 做移除与组合审计，以 Shapley 边际选择技能，发现组合污染与跨域效用反转。 | **RSI 构想最直接近邻**：若仅做“新技能真有用吗/会不会伤旧技能”，已经重叠。其主要干预是技能库层，不是 hidden-state patch。 |
| **CaSKG: Counterfactual-Causal Skill Graphs for Scalable Agent Skill Retrieval**, [arXiv:2608.25500v1](https://arxiv.org/html/2608.25500v1) | 用文本层移除/替换/顺序假设的 LLM 评分校准技能关系图，服务检索。 | 不要把它称作神经内部因果实验；也不要把文本反事实判断等同真实执行干预。 |
| **SAEScientist-Bench: Can AI Agents Conduct Autonomous SAE Interpretability Research?**, [arXiv:2609.09113v2](https://arxiv.org/html/2609.09113v2) | agent 使用 SAE（稀疏自编码器，将激活分解为稀疏特征）工具发现并 steering 概念；与专家参照比较。 | “agent 自动做解释研究”已有近邻；本项目应研究自改进的内部机制，而不只是让 agent 跑解释脚本。 |

### 6.1 最可行的起点：固定模型，研究版本化 skill 的计算效应

设系统为 `(固定模型权重, skill bank, retrieval, harness, evaluator)`。先仅允许更新 skill 文本，冻结其余部分。对版本 s0/s1 做：原始行为比较、从 s1 到 s0 的内容局部 patch、反向 patch、不同题目 donor、等长等义改写、无关更新，以及多个 receiver。真实自然长度更新和 token 对齐机制子集应分别报告，不能为了 patch 对齐而只允许不自然的更新。

任务分为改进生成集、选择验证集、最终隐藏测试集，最好按 skill/任务家族分开。每个实验重置会话与环境；只让指定 skill 版本跨轮保留，防止轨迹/答案被当作改进遗产。工具执行结果、检索到的文档和模型上下文都记录来源。

可回答的问题是：“一个通过验证的 skill 更新，究竟改变了程序内容的使用、任务选择，还是只改变了格式/输出先验？”这比看 embedding 更具体，但仍要证明比文本消融多识别了什么。

### 6.2 ⚠ 值得单独立项：meta-skill 的内部因果效应能否传到下一代改进效率

**假说而非结论。** 比如一个可改写 meta-skill 指导系统如何定位失败、设计对照、修订下游技能。若 s1 比 s0 能产出更有效的新 skill，可否把 s1 的局部表示移植到 s0 的改进调用中，恢复其生成更好后代的能力？

最小两阶段实验：

1. 固定开放权重模型和一批共同的失败轨迹，对同一批输入比较旧/新 meta-skill，保存生成的 candidate skill。准备 old、new、new→old patch、old→new patch、等长无关更新、文本关键句消融六臂。
2. 在**全新进程和独立任务**中，让固定 executor 使用各臂生成的 candidate skill；测相同总预算下的隐藏测试增益、成功改进概率、旧技能保持率。不能按被干预模型自己的自评分认定改进有效。
3. 若第一阶段成立，再把新 meta-skill 交给下一轮，比较固定 improver、只更新 task-skill、同时更新 meta-skill 的多条独立演化链。

潜在强结果：对 meta-skill 某程序部分的双向干预，能改变**下一代新任务的增益**，并在独立样本预测/改善下一轮改进效率；不是只让当次回答更像正确答案。

最近邻：HyperAgents/AIDE² 证明系统层循环可行，Coalition-Aware 研究技能库效用，IV/JIT 研究静态任务表示；本轮未查到它们做上述“两阶段、内部干预→独立后代质量”的同一实验。仅是尚未发现重合，不构成首创证明。

失败标准：新 meta-skill 没有稳定的 task-family 外增益；patch 只改变格式；效果依赖同题 donor；额外 patch 成本抵消收益；文本消融已解释全部且 whitebox 没有新预测。先做行为筛选，再决定是否花 GPU 做内部干预。

### 6.3 次优方向与不建议做的方向

- 次优：技能库增长是否改变目标 skill 的读取/绑定路径，造成“外部记忆仍在、内部用不上”。必须区分 retrieval failure、delivery failure 和 computation failure，并与 Coalition-Aware/CaSKG 比较；仅画负迁移曲线不够。
- 有条件：用机制预测指导 procedure-preserving context 构造，减少迭代重写后的退化。要与 ACE/GEPA、文本重要性与同预算随机方法比较；不能将高 rank、较早 transfer boundary 或高 patch recovery 本身设为改进目标，三者都未被证明单调对应真实任务质量。
- 不建议：直接把现稿改名为 RSI；从固定权重的一次 forward 推断递归能力增长；一上来复现昂贵完整 DGM；把模型解释自己“如何改进”的文本当作内部机制证据。

## 7. 建议工作顺序

1. 先修贡献表述与遗漏近邻：JIT、Davidson、IV、Sia/Pola，并收窄 constant energy 与独占存储说法。
2. 优先做 late span/query 交互及匹配语义覆盖的连续性对照，挑一个能形成机制预测的主线。
3. 若坚持 WWW，再明确一个实际 Web 科学问题并用机制产生可检验的系统预测；别只补包装。
4. RSI 另线先测旧/新 meta-skill 是否产生跨家族、等预算的后代质量差异，再决定 whitebox 扩展。

## 8. 核查记录与未完成项

- 读当前六个正文文件、主 replication 表、paper/HANDOFF、whitebox 历史交接以及相关代码。
- 代码核查命令：`sed -n '215,265p' whitebox/model.py`；`sed -n '180,236p' howskill/howskill/wb_posbudget.py`；`sed -n '335,425p' howskill/howskill/wb_posbudget.py`；读取 `whitebox/analysis/out/posbudget.json` 的六个 cNx256 arm。
- 初次 JIT 读到 v1，后续核对了 v3：增加 Qwen 复现，且对长输出结论更审慎；报告以 v3 为准。
- 若干指定 arXiv HTML 版本返回 404，改从摘要页解析有效版本/使用会议 PDF；ACL 2026 IV 的 PDF fetch 失败，全文核查采用 arXiv v2，会议身份采用 ACL Anthology。
- 本轮没有重新运行 GPU 实验、没有进行完整 raw-run 审计、没有编译 LaTeX；文件变化仅为研究记录。以上候选机制都未被本轮实验验证。
- 待下一任务：用户选择论文主线或 RSI 试验后，再形成具体 preregistration（预注册：运行前固定假设、样本、读数与判据）。
