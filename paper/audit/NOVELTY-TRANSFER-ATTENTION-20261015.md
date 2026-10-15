# Reading-dependent but weakly transferable：新颖性专项核查

日期：2026-10-15。范围：本论文橙色深度区间，即正确 skill 的源位置状态移到 wrong-skill receiver 时恢复较弱，但对正确运行实施累计 skill-attention knockout 仍明显损伤表现。

## 判断

**本轮核查的一手论文中，尚未找到明确提出和系统报告相同配对深度区间的工作；这不是“证明全领域无人提出”。** 该判断限于所列已检查的方法、结果与附录，不能写成“首次发现模型仍在利用不可转移信息”这一宽泛命题。

重要修正：**将 context masking 与 activation patching 联用本身已有直接先例**，尤其 EMNLP 2025 的 Internal Chain-of-Thought。此前若把贡献概括成首次配对两种方法，则不成立。我们的可辩护 delta 是：在相同 skill/model/task 与明确 receiver 条件下，将源 span-transfer 的衰退边界与累计源注意力依赖的消退边界作逐深度比较，并复核共同 eligible items，从而指出 transfer failure 不足以推出 source independence。

## 一手近邻逐项比较

| 论文与出处 | 已有结果 | 与当前橙区的关系 | 核查深度 |
|---|---|---|---|
| **Where does In-context Learning Happen in Large Language Models?**, Sia et al., NeurIPS 2024, arXiv:2403.04510；https://www.cs.jhu.edu/~kevinduh/papers/sia24where.pdf | 从某层起屏蔽上下文注意力，研究 task recognition 后何时不再需要 context | 累计 source-attention masking 有直接先例；未见同一源 span transfer 的失效边界配对 | 原 NeurIPS PDF 方法/结果；arXiv 当前 HTML 标题为 Where does In-context Translation Happen，版本差异不混同 |
| **Where does an LLM begin computing an instruction?**, Pola & Balasubramanian, arXiv:2511.10694；https://arxiv.org/html/2511.10694 | 最小指令对比的逐层 residual patching，晚层预测不易翻转，以 onset 描述 reading→doing | 晚层 patch 失败非新现象；未见与累计源注意力屏蔽的保留准确率逐深度比较。我们的结果约束由 patch 失败推出“已不再读取”的解释 | 全文 activation patching、干预位置、结果和讨论 |
| **Just-in-time and distributed task representations in language models**, Li et al., arXiv:2509.04466v3；https://arxiv.org/html/2509.04466 | task identity 可持续解码，但可转移 task representations 有 token 时间局部性和语义局部性 | 解码与转移分离已有；“仍可解码”不是“屏蔽源注意力仍致损”，主要轴为 token/context progression，非我们的层深双干预边界 | 全文 §3、§4.2–4.3、附录 C/D |
| **Internal Chain-of-Thought: Empirical Evidence for Layer-wise Subtask Scheduling in LLMs**, Yang et al., EMNLP 2025, 2025.emnlp-main.1147；https://aclanthology.org/2025.emnlp-main.1147/ | 同时用 layer-from context masking 和 cross-task patching，研究复合任务的子任务学习与执行顺序 | **最需要补引用的直接近邻**。§4.1/图2 的 X 形是屏蔽下中间答案与最终答案的变化；§4.2/式7/表2/表5 的 transfer 是 composite→subtask 的最后 token 平均状态，并取最佳层的强度。未见以同一源 span 在 wrong receiver 的逐层 transfer failure 对比累计 source masking 后 performance retention，并定义两者间区间。其方法联用不属于本文首次 | 29 页全文：§4.1、§4.2、式5–7、Table 2/5、Appendix E；图2及相邻正文 |
| **Patches of Nonlinearity: Instruction Vectors in Large Language Models**, Bigoulaeva et al., ACL 2026, arXiv:2602.07930；https://arxiv.org/html/2602.07930 | instruction-vector 多层 patch 有超加性交互，给出输入依赖的局部映射与路径分析 | “单层失败不等于没有功能”已有机制背景；未见本文同形源 span-transfer/累计 source-attention knockout 深度区间 | §方法、多层实验和 §6 路径分析 |
| **The Curse of Multiple Mediators: Hidden Interaction Effects in Activation Patching**, Vaidyanathan et al., arXiv:2606.27510v1；https://arxiv.org/html/2606.27510 | activation patching 效应依赖其他组件的状态，可漏掉功能重要组件 | **一般的“patch 无效不能推出无因果作用”已有清晰论述**。本文不能将此逻辑当作新定理；可新增的是特定 skill 任务上的双曲线经验分离及其范围 | 全文摘要、§1、§3–5、NIE/PIE/INT 解释 |
| **In-Context Learning Creates Task Vectors**, Hendel et al., Findings EMNLP 2023, arXiv:2310.15916；https://aclanthology.org/2023.findings-emnlp.624/ | 从示例构造 task vector，在末位置测试任务恢复 | transfer 与层选择已有；提取位置、receiver 和任务格式不同，不能视作本文双曲线现象的既有实验 | 与本仓库 10-03 全文审查交叉核对，本次搜索复核一手记录 |

检索还覆盖 activation patching + necessity/sufficiency、instruction + context masking、task vectors + layer-from masking、transferability + source attention 等组合；weight-space task vectors/model merging、仅 probe 可解码和常规必要/充分性电路研究未作为同一现象证据。

## 论文应采用的表述

- 可以：We identify a depth interval in which source-span states have weak corrective effects in the specified wrong-skill receiver, while cumulative skill-attention knockout still substantially impairs the correct-skill computation.
- 不可以：After the transfer boundary, the skill has no value for other executions.
- 不可以：We are the first to combine patching and context masking / the first to show patching failure does not imply causal irrelevance.
- 不宜：独立“三阶段算法”或普适层深规律。阈值定义的区间、L26 recrossing、模型/任务选择和 receiver 都需要保留。

## 下一步判别实验

若要从现象推进机制，应做 span-only / query-only / joint patch 的预注册交互对照，配不同 wrong receivers。若 joint 能恢复而 span-only 失败，才支持接收态相容性解释；若 query-only 已足够则不能归因于协同。单纯增加新家族只扩现象范围，不能识别机制。新增实验按用户最新指示留到明天。
