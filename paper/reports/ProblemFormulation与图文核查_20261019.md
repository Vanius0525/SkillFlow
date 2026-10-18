# Problem Formulation与图文核查（2026-10-19）

## 任务与修改

用户要求：简化Problem Formulation、用可读公式表达干预、术语先解释；统一Experiments小标题；核对图表与正文的匹配、合理性和重复。

- Formulation按Setting→S/C→knockout→recovery/dependence→boundaries组织，空白分词计数约807→635（包含图注/TeX，非纯正文词数）。六个编号公式分别表达S、C、mask、rho、d和T/R/Delta。位置集合使用mathcal I，避免与干预S重名；donor/receiver、prefill/decoding、residual、query/key/value、KV、softmax、head、rescued均就地说明。
- 不写通用Transformer递推或QK投影公式，因为其架构细节不属于本研究变量；直接用block输出替换和实际缓存写入公式。Knockout写为softmax前score置负无穷，并说明重新归一化与保留causal mask。核对run.py的mask_edges、block输出hook、0..L缓存写入及recut从L+1开始。
- 原dose alpha与delta移到实际使用它们的附录；原有eq:inject/rho/dependence标签保留，新增cache/knockout/boundaries。
- 实验所有subsection和paragraph统一名词短语、sentence case。4.2 Validation of skill-state transfer；4.3 Depth separation of transfer and dependence；4.4 Effects of source caches and continued reading。正文继续负责陈述结果，标题不再混杂动名词、判断句和名词。
- 删除实验设置重复解释prefill/decoding；机制段引用公式，避免重述S/C定义。

## 图表逐项核查

| 展示 | 与正文关系 | 处理与结论 |
|---|---|---|
| Fig1 | 早期恢复/深度分离/L16修复的概览，与Table1、Fig3、Fig4部分重复 | 保留：承担引言导航功能，三个panel的135/134/114样本仍明确，不视为同题轨迹 |
| Fig2 | S/C/SC及三类cut设计 | 与新增公式对应；caption首次展开KV；保留L与L+1差别，明确早期reader计算未重放 |
| Fig3 | 六组合rho与d深度曲线 | 与新边界公式一致，d=1-q不变；原始/共同样本两套曲线仍保留，当前边界相同，虚线解释保留；阴影非严格单调阶段 |
| Fig4 | 114题恢复准确率与路径损失 | 与S/C公式、机制文字匹配；caption补充层组为等距分类、竖线连接零点，避免误认连续层轴或区间 |
| Table1 | 早期对照的精确数值 | 与正文及汇总数据匹配；caption增加other-skill为matched-prefix，正文保留正确prefix rho=.65，容量差异保留 |
| Table2 | Fig3共同样本边界与分离不确定性 | 补充而非逐点重复；T/R/Delta与新公式对应，数值不变 |
| Table3 | Fig4派生差值与加性交互 | 保留：原始点图不直接展示这些差值；caption明确a_X是准确率，交互为a_SC-a_S-a_C+a_R，避免对干预名称直接作算术的歧义 |
| 附录表 | 全量/开发集/不同筛选的详细对照 | 保留：含主表若干重复数字是用于跨人群对照，未将不同筛选当成同一人群扩样；rank与quarter斜杠串仍可读性一般，未在本轮扩大重排 |

## 解释修正

重复写窗口在共享相同前缀、完整source span替换的因果模型中可能与首层单次写结构等价。原稿把它解释为独立的“维持状态仍不足”证据过强。保留原测值，将正文/附录统一为一致性检查，不新增推理或混入未完成新家族结果。

## 验证与范围

当前15份数值输入与HEAD逐字不变；audit_three_display_revision.py通过，四图三表与附录数值校验通过。最终编译/页面检查结果见HANDOFF。已有旧DATA-CONSISTENCY清单和未完成family_depth目录不属于本次提交。未操作远端任务。

最终验证：正文6页/全文9页，图表合集9页；两项编译均无error/undefined/overfull。已目视检查第2–3页公式与图注。原始JSON、边界表SHA不变。审计见audit/FORMULATION-REVIEW-20261019.json。
