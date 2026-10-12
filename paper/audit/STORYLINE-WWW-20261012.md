# 论文故事线与 WWW 扩展方案

日期：2026-10-12。当前工作：根据已有调研调整正文和引用，保持章节顺序，不启动模型实验。新 Web 结果和机制解释都是待验证计划。

## 1. 建议主线

中心问题：给模型一份外部程序后，什么状态能把程序效果转给另一次运行，这种可转移性与原运行持续读取程序的依赖是什么关系？

完整论证按现有正文展开：
1. 正确文档带来明显增益，错误等长文档不带来相同收益。末位置的大位移不一定解释行为增益，内容差分才是待研究对象。
2. 单位置恢复随答案形式变化。把自然产生的一个末位置向量当作程序表示的全部，会漏掉有效的源位置状态。已有 TV/FV、JIT 和 IV 研究是出发点，不是被当前协议一概否定的对象。
3. 原位 span 恢复大部分筛选子集增益，跨题内容转移支持它不只搬运单题答案。位置选择和保留方向的控制描述这个干预载体的结构。连续性与语义覆盖仍需分开。
4. 核心发现是配对的深度分离：span 已不能有效转移时，原运行仍需要读它。两种干预的运行背景不同，形成待解释问题，而不是直接证明内部执行阶段。
5. 下一层机制检验：晚层失败是否来自源程序状态与接收计算的交互？四格实验比较 span-only、query-only、joint 和原运行，再加反向干预和跨题 donor。若 joint 只是在搬答案，则解释失败。
6. 若转向 WWW，验证实际 Web 文档交付策略能否改善多步任务。隐藏态错位结果只是预测来源，必须再做自然文本层实验。

当前题目改为 `Transferring and Reading Skills in Language Model Contexts`，去掉旧标题暗示的独占存储。正文顺序、实验图表结构和原始数值保持。位置预算图同步修订误导性文字标签。A 类竞争力来自可复现发现和可检验解释，不取决于给 skill 起新名字。机制方向有价值，但当前不能保证录用。

## 2. WWW 的具体关系，按建议优先级排序

官网要求首页说明 Web 科学问题。仅使用网上数据或 API 不满足要求。[W1] 以下不是已验证方法或首创声明。

### A. Web 程序文档的检索与交付（与现稿最接近）

问题：Web agent 从帮助中心、操作指南和 API 文档获取流程时，检索系统如何在 token 预算内保留可执行的程序结构？相关片段是否齐全，与前提、变量定义、步骤之间的联系是否保留，是两个可分别控制的因素。

例子：对 Web 应用执行带条件的筛选、批量修改或业务提交。文档分别说明前置权限、字段语义、过滤条件和提交检查。系统可能检索到所有关键词，却丢失“先检查条件再执行”的联系。

设计分两阶段：
- 固定相关文档为 oracle 输入（事先确保检索正确），隔离交付和计算问题。比较整文、固定长度块、句子/语义块、按步骤边界保留的块、同预算摘要和随机截取。对照程序信息覆盖、顺序和位置，不能让方法只是多保留关键句。
- 再加入真实检索，比较检索召回和下游任务成功，分别报告 retrieval failure 与读取/执行失败。方法在开发集定参数，按文档/任务家族划分测试，避免同一规程的近重复泄漏。

白盒连接：只对同一网页状态和相同行动历史做配对，先测试下一步动作的干预效果，再测试完整任务。成功率是主读数，额外报告动作数、输入 token 和延迟。按规程/任务家族重采样不确定性。

候选载体：WorkArena 的企业 Web 应用任务及 WorkArena++ 的组合流程。数据集提供环境和任务，不自动提供与本研究完全匹配的程序文档，需要核查或单独构造并发布文档来源。[W2–W3]

增量要求：仅发现“语义切块优于随机切块”太弱。需要在相同程序内容覆盖下识别具体失败条件，或由内部干预预测哪些截取方式会失败，并在未见任务验证。

### B. 多步 Web 工作流中的规程保留与重新投递（Web 相关性最直接）

问题：连续浏览和操作时，agent 何时仍依赖外部规程？上下文压缩后哪些约束最先丢失？能否以较少 token 保持程序正确执行？

载体：WebArena 的可复现网站，优先核查 WebArena-Verified 的修订任务与评测器。[W4–W5] 报告浏览器最终状态是否满足任务，而非只看动作字符串相似度。

比较：始终保留、只初始提供、逐步检索、固定间隔重新提供、完整步骤摘要、按阶段提供。各臂控制总 token、动作预算和模型。用同一状态快照比较决定动作的单步因果作用，再做独立的完整 rollout（从初始状态到终止的执行轨迹）。轨迹分叉后不能直接把不同网页的隐藏态差异解释为 skill 效应。

关键边界：一次 forward 的 layer 深度不等于多轮 agent 时间。当前 L13/L25 不能直接推导“第几步删文档”。必须测实际步骤依赖，使用无测试标签的规则预测保留时机。

潜在贡献：把规程依赖从静态 prompt 扩展为 Web 动作过程的可预测量，并在成功率相近时减少输入成本。成本和性能都要测，当前稿件没有该结果。

### C. Web 文档版本冲突与程序更新（更独立，当前不优先）

问题：同一服务存在旧版和新版操作文档，agent 已按旧文档形成计划，晚到的新规程为何不能纠正执行？

构造版本明确、来源可追溯的网页规程，在固定环境快照下比较替换相关句、替换整段、重新规划。区分检索选错版本、网页状态变化、内部接收态交互。以真实执行结果评估。

与当前兼容性假说关联强，但需要版本数据、真实执行和新的近邻调研。它可能成为独立研究，暂不写入当前论文的已验证贡献。不要用人工拼接冲突 prompt 代替 Web 场景的论证。

## 3. 时间与决策

2026-10-12 查官网：摘要 10 月 18 日、全文 10 月 25 日，均 AoE。[W1] 当前距离全文日期约 13 天。若浏览环境、程序文档和稳定 evaluator 尚未具备，同时补机制识别和完整 Web 系统实验风险很高。应先确认已有环境能否产生可靠 pilot，再决定是否赶这一轮。范围适配不能只通过引言包装完成。

优先建议：A 为当前稿的扩展入口，B 为更完整的 WWW 故事。先验证固定检索下程序交付效应，再扩真实检索或多步保留。RSI 留作独立方向，避免同一篇同时承诺表示机制、Web 系统和递归改进。

## 4. 本次直接修改

- 标题去掉 `Lives on Its Own Tokens` 的排他暗示。
- 引言补已有紧凑任务/指令表示和 JIT 的定位，维持原有实验推进顺序。
- Related Work 增加 Davidson 指令 FV、Bigoulaeva 的 IV；显式引用已有 bib 中的 JIT；明确 Sia 的累计 masking 和 Pola 的位置 patch 与本研究的联系。
- Dong 的理论表述限定到 linear-attention 设置，并区分任务映射 rank 和本文状态差分矩阵 rank。
- 方法说明 prompt-last 与 prefill 一次注入。
- 答案形式结果说明同时改变输出长度和计算。同题最终层替换下一 token 决策，解释其测量对象。
- 位置预算段删除 `constant budget and energy` 和 `Contiguity does`，使用组级置信区间，写清实际平均能量和 procedure 覆盖差异。纠正错位操作是移动差分而非整体 donor 状态。
- 深度段直接解释两种干预的背景，指出接收状态交互这一具体开放问题。结论减少重复防御性措辞。
- 位置预算图的 `budget and energy fixed` 等标签同步修订，使用现有 posbudget.json 重绘，未重新计算实验数值。附录中将 JIT 的可转移性局部性等同读取敲除的两处表述也同步修正。
- 附录 A 的旧 provenance 段仍把 synthetic/final-position 主文实验称为修复前结果，与现有正文和交接记录冲突。改为区分当前修正版主文与历史开发诊断，并去掉过时的重复清单。附录 B 将接收态兼容性从已断言的解释改为待直接检验的问题。
- 用户新要求：少用分号和破折号，避免模板化对比及重复免责声明。本次新增英文按此精简。

## 5. 一手文献

- [W1] WWW 2027 Research Track CFP：https://www2027.thewebconf.org/research-track-papers/ 。Web 研究问题和日期依据。
- [W2] WorkArena: How Capable Are Web Agents at Solving Common Knowledge Work Tasks? ICML 2024, arXiv:2403.07718；https://github.com/ServiceNow/WorkArena 。企业 Web 操作环境，候选实验载体。
- [W3] WorkArena++: Towards Compositional Planning and Reasoning-based Common Knowledge Work Tasks, NeurIPS 2024, arXiv:2407.05291；https://arxiv.org/abs/2407.05291 。组合流程，更接近程序执行。
- [W4] WebArena: A Realistic Web Environment for Building Autonomous Agents, arXiv:2307.13854；https://arxiv.org/abs/2307.13854 。可复现网站和功能性成功判断。
- [W5] WebArena-Verified 官方仓库：https://github.com/ServiceNow/webarena-verified 。修订任务与评测，采用前需核查版本和部署要求。
- Davidson et al., Do different prompting methods yield a common task representation in language models?, arXiv:2505.12075v3；https://arxiv.org/abs/2505.12075 。指令/示例 FV 部分组件不同；“从示例扩展到指令”不足以单独成为创新。
- Bigoulaeva et al., Patches of Nonlinearity: Instruction Vectors in Large Language Models, ACL 2026；https://aclanthology.org/2026.acl-long.559/ 。query 前指令末位置和跨层非加性交互；需区别 skill-last 与 prompt-last。
- Li et al., Just-in-time and distributed task representations in language models, arXiv:2509.04466v3；https://arxiv.org/abs/2509.04466 。可转移性具有时间与语义局部性，本文需定位在长程序的结构和读取依赖。
