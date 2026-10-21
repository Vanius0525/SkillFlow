# Figure4 Both vs reader 核查（2026-10-21）

目标：解释L24的Both paths与Post-skill to skill为何全等，核查实现和设计。

结论：当前累计切边协议中，两臂对后续输出在标准因果Transformer计算图上结构性等价。Both作为独立机制对比冗余；不能把相等解释为skill内部更新无作用，也不能用它证明无交互。上次绘图只做数值/排版核查，未识别此设计问题。

代码证据：experiments/mechanism_20261017/run.py::mask_edges分别选择q>=hi（reader）、lo<=q<hi（self）、q>=lo（both），key都取lo:hi。Engine.generate注册到model.layers[cut:]的每一个attention模块；phase=both贯穿prefill与decode。两臂不是同一个mask。这里路径名称用query→key的“读取”方向，信息实际从key流向query。

结构推导：按位置分成A=skill之前、S=skill span、P=skill之后。起始切断层的输入相同；Both额外改变S的内部attention。A因因果性不能读取后面的S，因此不受影响；P在两臂中都不能读取S，且其他层内运算逐位置执行，因此该层P相同。按层归纳，所有后续层P相同；decode继续屏蔽读取S，故输出相同。原先较低层已传给P的信息在两臂中均保留。结论依赖标准因果注意力、连续完整span、从同层到最后一层持续阻断；不推广到只切一层或在更晚层恢复读取。

数值验证：python reports/figure4_path_audit_20261021/audit.py。本地snapshot-20261019的8份edges日志（含非主图Qwen0.6B），加Qwen8/MedCalc正式4分片，共801个item记录、3层、2403对。所有pair均完整token_ids相同、correct相同、first字段（存储top5 token及log概率）相同；所有pair的masked_rows不同。只核查记录中的首步top5概率，不声称全部词表/每步logits逐项相同。输出raw_comparison.json。

范围限制：snapshot-20261019不是当前全部最终r3原始文件，尤其DeepSeek/TheoremQA含旧的51-item日志；不能用本次比较冒充最终corrected54逐题复审。当前主图八组合在三层的reader/both准确率全等另由values/eight-cell-display-values.json核对。结构性原因不依赖这些评分人口差别。未新跑GPU或访问启智。

建议：Figure4(b)主图只保留reader与self两种干预；Both可作为预期等价的仪器一致性检查。若要识别内部更新对后续读取的影响，可在有限层/窗口切断self、允许更晚层重新读取，做窗口×路径的对照；若读边仍一直切到末层，比较both与reader无法识别新增效应。此处只是建议，未修改论文、图或Overleaf。

下一步：向用户解释设计冗余；等待其决定图中删去Both或重新设计有限窗口实验。

## Open Ideas / 值得深挖的问题
2026-10-21：有限窗口切断skill内部更新、再开放下游读取，可区分“更新受损”与“读出口被截断”。触发：2403对累计reader/both干预输出完全相同，推导发现结构等价。最小验证：固定同一人口、同一层窗、reader/self/both四臂含baseline，在窗口后恢复所有读边；检查内部状态差异是否经恢复的读取影响输出。属于当前机制实验修正方向，尚无新颖性证据，不宣称独立顶会idea。

## 2026-10-21 固定层号与理论阶段
已核对：所有组合edges实际网格为8/16/24；repair为8/12/16/24。固定层不等于阶段对齐。L16在八组首次T/R之间，L8仅Qwen两组在T前，L24有两组仍在T/R之间、六组过首次R。完整映射与split-prefill人口/重新越阈限制见DEPTH-ALIGNMENT.md。上一轮把多层称“多阶段”不准确，应更正为多干预深度；尚未重新设计或运行阶段对齐实验。
