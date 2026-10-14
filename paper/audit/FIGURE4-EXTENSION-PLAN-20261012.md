# Figure 4 中间区间：多模型与多任务扩展方案

日期：2026-10-12。状态：方案，未运行新模型实验，未把计划结果写进正文。范围仅为现有 transfer/reading 间隙的复核、展示和扩展，不新增 Web benchmark。

## 1. 具体要回答的问题

Figure 4 显示：Qwen3-8B/MedCalc 的 span transfer（将正确文档的状态注入错误文档运行，度量恢复了多少准确率增益）在 L13 低于一半；cumulative attention knockout（从某层起持续禁止注意力访问文档，度量仍答对的比例）到 L25 才保留至少一半正确题。

因此有 L13–24 的中间区间：不能有效转移，但仍依赖源文档。把它与早期有效转移、晚期较能容忍屏蔽共同描述为三个操作性区间，可以由现有数据支持。**不是“transfer → 第三阶段 → reading”的时间序列**，因为 reading 在早期和中间区间均可能必需；也不等于识别了三个独立内部算法。

研究问题：这一中间区间在其他模型/任务中是否稳定存在，其跨度是否对测量分母、阈值和重复注入稳健？

## 2. 已有结果，不要重复申请算力

来源：paper/values/replication-values.json、paper/tools/replication.py 的 FILL 和 DONE_ROWS、现有 Table 4。

| task | model | transfer 曲线 n | knockout n | transfer crossing | reading crossing |
|---|---|---:|---:|---:|---:|
| MedCalc | Qwen3-8B | 135 | 134 | 13/36 | 25/36 |
| TheoremQA | Qwen3-8B | 99 | 63 | 13/36 | 21/36 |
| MedCalc | Qwen3-0.6B | 362 | 90 | 11/28 | 22/28 |
| TheoremQA | Qwen3-0.6B | 132 | 125 | 11/28 | 20/28 |
| MedCalc | Mistral-7B | 92 | 46 | 7/32 | 27/32 |
| TheoremQA | Mistral-7B | 115 | 65 | 7/32 | 19/32 |

六组的一层分辨率补跑已有记录。因此“首次扩展到多模型/多任务”不准确；有价值的是将两条完整曲线、差值不确定性与重复晚层注入一起扩展。

**需优先核对的测量问题**：相同 screened groups 不等于两个干预有完全相同的题目分母。当前脚本的 knockout 只保留其独立 baseline 下 ok_with=True 且 ok_without=False 的题，transfer 则按其运行内筛选。特别是 Qwen3-0.6B/MedCalc 的 362 vs 90，不能笼统叫“362 道题上的严格配对”。原因是否仅 baseline/数值运行差异，需要逐 item 核对，不能凭交接猜测。

## 3. P0：只分析已有文件，先不跑 GPU

1. 由每组 sources.depth 和 sources.knockout 合并逐题逐层记录。检查重复键冲突、模型及 prompt/scorer 版本、真实 intervention layer 与 hook 是层前/层后、每层 item 是否完整。不要用不同 item 拼曲线。
2. 原始分母版本保留，用它复现 Table 4。另取 transfer 与 knockout 的共同 instance ID，并以双方 baseline 条件为明确筛选规则，计算严格共同子集上的两条曲线。报告前后 n/group 数和边界，不覆盖旧数字。
3. 画 2×3 panel，列是三模型，行是两任务。横轴归一化层深度 L/N，同时附实际层号；纵轴分别注明 transfer recovery ρ 与 knockout survival q，不能叫同一量。中间区间以 ρ<0.5 且 q<0.5 标出。
4. 以 skill/calculator 为重采样单位，对同一次抽样同时重算两条曲线及边界。95% CI（置信区间）由重采样分布的 2.5% 和 97.5% 分位给出，用于表示抽样不确定性；不是六组点估计差值的误差条拼接。
5. 主指标为 Δ=(L_read−L_transfer)/N。正值代表读取依赖比转移有效性维持更深。报告每组 Δ、95% CI、bootstrap 中无法识别边界的比例。曲线非单调时同时报告所有反穿越，不通过平滑隐藏。
6. 0.5 为沿用的主阈值；预先固定 0.25/0.5/0.75 的二维阈值网格做敏感性分析，不挑最大间隙。独立阈值变化是描述稳健性，不把 ρ 与 q 当作相同标度。
7. 报告每个 group 的差异及 leave-one-group-out 结果，检查主结果是否被少数 calculator 支配；TheoremQA 多个 group 只有一题，要明确这一结构。

成功判据：共同子集上仍能在多个模型和两任务看到连续中间区间，且结论不依赖一个阈值。失败判据：配对后间隙消失/反转，或 interval 大量不可识别。无论何者都保留，不通过改变筛选“修复”结论。分析完成前不新增正文数字。

## 4. P1：最小新增实验，只扩展 Figure 4(b)

现有重复窗口对照主要覆盖 Qwen3-8B 的 MedCalc/TheoremQA。优先补 **Mistral-7B × MedCalc/TheoremQA**，再按资源补 Qwen3-0.6B 两任务，以区分 Qwen 特性与跨模型现象。暂不优先 Qwen3-1.7B，因为历史 skill-rescued 比例偏小。

每个 cell 固定 P0 验证后的 receiver、题目、prompt、生成预算、scorer 和精度。保存完整 baseline 与生成答案。每条臂均使用相应层的 donor 状态，不把某层状态重复写到其他层。

最小臂：
- 无干预 donor、receiver，以及同状态回写的 identity。
- transfer crossing 前的四层窗口、包含 crossing 的四层窗口。
- 中间区间前部和后部各一个四层窗口。
- 从中间区间前部直到最后一层的长窗口。
- 全层 span replacement，作为重复注入可工作的正对照。

窗口按 P0 固定的边界或归一化位置提前生成并记录，不能看新结果后挑窗口。与同起点的单层结果配对比较；若原始运行不可比，同批补该单层臂。

主比较：中间区间的长窗口是否显著恢复到早期转移水平，还是接近同起点单层值？同时报告 paired recovery 差与 group-bootstrap 区间。若长窗口在某模型显著救回，正文必须改为“间隙普遍、重复修复的可行性依模型而变”，不能继续泛化“晚层注入均无效”。

最低仪器检查：
- identity 的完整输出一致，而非仅 final accuracy 一致；
- knockout hook 在 prefill 和 decode 均生效；核对其屏蔽所有 query 到 skill keys，不误称仅 question-token 敲除；
- layer indexing 一致：span 的层后 hook 与 attention 的层内干预存在最多一层的边界解释差异，需标注；
- 每条曲线 baseline 与分母固定，失败任务重跑原配置，不混入成功片段。

算力预算不沿用旧交接估计：先在计划模型上用少量题实测单层/窗口耗时和峰值显存，再按 item×arms 外推，加约 20% 重试余量。当前没有实测，不能给可靠 GPU·h。

## 5. 仅在仍有必要时：增加一个真正新 cell

如果 P0/P1 已形成稳健的三模型两任务图，不必为模型数量继续堆实验。若跨家族稳健性仍不足，优先新家族在 MedCalc 的一个 cell，而不是新增多个任务和训练配置。模型需先有稳定、非触底的正确文档增益，再做成对深度扫层；按与现有 cell 同样的筛选条件报告全量和条件子集。

若选择新增任务，要求外部程序确实决定答案、数值/符号评分确定、存在可用的等长错误程序，并保持自由作答协议。先验筛选只依据无文档/正确/错误文档三个 baseline，不看 patch outcome。具体任务与模型选择需另行调研，本轮不指定未验证的新 benchmark。

## 6. 当前不安排的机制扩展

接收态联合 patch、反向损坏、语义覆盖严格匹配等可以解释间隙的来源，但不属于用户本轮只考虑的多模型/多任务扩展。正文将“接收态交互”保留为解释边界，不写作已验证机制，也不把这些额外实验当成本轮修改的前置要求。

## Open Ideas / 值得深挖的问题

2026-10-12：将“仍被读取但不能被转移”的区间作为表示可复用性的压力测试。触发观察是主比较 L13 vs L25，且已有六组不同边界；潜在价值是区分信息存在、行为可迁移与接收计算的相容性。最小验证就是 P0 的共同子集复核加 P1 的跨家族长窗口。现有 TV/FV/JIT/IV 近邻已覆盖局部转移和多层相互作用，独立新意需要建立在成对读取依赖诊断上，不能仅凭三阶段命名宣称首创。该问题延续此前接收态假说，本轮不声称新发现独立机制。
