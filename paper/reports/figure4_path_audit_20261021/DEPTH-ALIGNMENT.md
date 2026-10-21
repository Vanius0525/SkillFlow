# Figure4固定层号与边界对齐核查（2026-10-21）

用户问题：所有组合都用L8/L16/L24是否真实执行，是否应按前文阶段选择不同层？

事实：isolated_suite_worker.py与suite_worker.py给edges传入--layers 8,16,24，repair为8,12,16,24；values/eight-cell-display-values.json八行均有这些层。前次raw_comparison.json核查了可用日志的三个层。故图未虚构层号；但这套固定网格不是按各组合边界对齐的机制阶段实验。不能将三层称作普遍共享的早/中/晚机制阶段。

前文定义：T为恢复rho首次<.5，R为依赖d首次<=.5；属于各组合总体曲线上的半效应边界，不是理论预言的精确相变，也不是时间阶段。曲线可能重新越阈，严格判定某层应检查该层rho/d，不仅按首次T/R分箱。机制实验另用fresh split-prefill人口，深度曲线的边界不能自动当作机制人口的已验证边界。

以下按tables/tab-paired-depth.tex的首次边界位置标记，E=L<T；M=T<=L<R；P=L>=R。M只是位于首次边界间，是否当层同时满足rho<.5且d>.5仍须查曲线。

|模型|任务|T|R|L8|L16|L24|
|---|---|---:|---:|---|---|---|
|Qwen3-8B|MedCalc|13|25|E|M|M|
|Qwen3-8B|TheoremQA|13|21|E|M|P|
|Mistral-7B|MedCalc|7|27|M|M|M|
|Mistral-7B|TheoremQA|7|19|M|M|P|
|Llama-3.1-8B|MedCalc|7|18|M|M|P|
|Llama-3.1-8B|TheoremQA|6|18|M|M|P|
|DeepSeek-7B|MedCalc|6|21|M|M|P|
|DeepSeek-7B|TheoremQA|4|19|M|M|P|

判断：L16都处于各组合首次T/R之间，具有中间区间探针的可比性，但未匹配区间相对位置。L8仅Qwen两组在T之前；L24对Qwen/MedCalc、Mistral/MedCalc仍在T/R之间，对其余6组已过首次R。L24适合“相同绝对切断层的跨组合结果”，不能直接支持“各组合共同晚阶段机制”。也不能将Both冗余问题与层号问题混为一谈。

建议：现有图明确标固定干预层号；若主张跨模型阶段一致，应先按每组原始rho/d确定满足条件的区间，再在独立/预留人口选择对应层，运行相同机制协议。若只用现有数据，不得把缺失的阶段对齐层插值成实测；可保留L16中间区间对照，并将其他层作为深度敏感性结果。T/R存在样本和阈值不确定性，应使用区间或敏感性分析，避免按噪声交点强行选层。

本轮无新推理实验、无改图/正文/Overleaf；该结论只依据本地实验代码与稿件，不涉及领域新颖性判断。
