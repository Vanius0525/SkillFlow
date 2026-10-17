# Web / Agent Skills 修订版

本目录是本轮写作、引用与图表修订后的最新上传版本，保留此前 Final-v2 审阅快照。

## 上传与阅读

将 `StillNeeded-overleaf.zip` 上传至 Overleaf，主文件选 `main.tex`，编译器选 pdfLaTeX。
`main.tex` 只构建 WWW 2027 匿名投稿版，无扩展版切换开关。
`StillNeeded-review.pdf` 是对同一ZIP独立编译的预览；`project/` 是仅含必要编译依赖的源码。
本次目录只交付一个投稿PDF；历史扩展版不再维护、编译或打包。

## 本轮改动

- 引言从 Web agents 的技能来源切入：Web 提供网站说明、示例、API文档与步骤指导；agent 将相关知识组织、检索为 skill 并加载到上下文。
- skill 明确采用 Anthropic 的 Agent Skills 范式：以 SKILL.md 为入口、组织指令与脚本/资源的能力包。模型内部实验的分析单位是载入上下文的 skill 指令内容，选择过程固定。
- 摘要与正文优先使用 skill；document/procedure 仅用于说明载体或技能内容，不作为另一套中心概念。
- 最近邻讨论补全：Internal Chain-of-Thought已有两类干预联用；Multiple Mediators讨论一般组件交互；Models Take Notes at Prefill既研究陈旧缓存，也研究预编译技能缓存的可组合性。本文突出逐层迁移/来源依赖分离、联合修复和修复后再次切断读取的完整证据链。
- 删除 AI Use Statement；引文键和全文标签已检查，关键七项引用核查一手来源，AWM改为ICML 2025正式出版信息。
- 折线图统一蓝/橙配色、白色背景、真实点标记、轻量网格与区间标签，移除交叉箭头；没有平滑曲线、插值或修改测量值。热力图采用一致色系与清晰单元格，表格强化组间分隔和关键对照。
- 移除匿名审稿模板中未分配的 DOI/ISBN 与 ACM reference strip；保留会议名称、日期、地点与标准acmart版式。

## WWW 2027 长文长度与格式

[官方Research Track CFP](https://www2027.thewebconf.org/research-track-papers/)明确要求：

- **正文最多8页，不含参考文献和可选附录。**
- **正文＋参考文献＋附录总计最多12页。**
- 前8页自洽；reviewer不必读第8页之后的内容。
- 英文双栏，官方推荐 `\documentclass[sigconf, anonymous, review]{acmart}`。
- 首页明确说明Web及所投track相关性，采用双盲匿名审稿。

本版使用推荐class，正文8页、总计12页；主图1/2/3/4位于第1/5/6/6页，均在正文范围内。
首页摘要与引言明确Web-agent skill问题；27种PDF字体全部嵌入；无编译error、undefined reference/citation或横向越界。最终排版日志的末页平衡提示记录在格式审计中。
未修改正文页边距、字体大小或行距。表格局部样式与浮动排布不改变正文模板尺寸。
格式核验不代替会议对研究scope与贡献的判断。

## 保持的结果和贡献

没有新增推理，没有改变样本、数值或统计口径。仍然是：

1. 有效、内容敏感且可跨题复用的技能状态干预探针。
2. 三模型、两任务下，技能状态迁移先减弱、来源依赖仍继续的深度分离。
3. 源端状态与缓存联合修复恢复晚层迁移；第16层修复后再切断读取使正确率从42.1%降至7.0%。

正式机制结果仍基于同114题、14个计算器；第16层S/C/SC/再切断正确率为3.5%/7.0%/42.1%/7.0%。

## 本轮一手引用核查

- Anthropic / Zhang, Lazuka & Murag, *Equipping agents for the real world with Agent Skills*, 2025-10-16：https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills 。定义和按需加载；本稿对应skill指令内容的内部执行。
- Wang et al., *Agent Workflow Memory*, ICML2025, PMLR267:63897–63911：https://proceedings.mlr.press/v267/wang25bx.html 。从轨迹提取工作流并供Web agent使用；支持引言动机。
- Wang et al., *WebXSkill*, arXiv:2604.13318v2：https://arxiv.org/abs/2604.13318v2 。程序与自然语言指导配套、支持guided执行；支持skill部署动机。
- Tan et al., *HtmlRAG*, WWW2025, DOI10.1145/3696410.3714546：https://arxiv.org/abs/2411.02959 。Web结构化内容检索；不将其描述为Agent Skills评测。
- Yang et al., *Internal Chain-of-Thought*, EMNLP2025：https://aclanthology.org/2025.emnlp-main.1147/ 。context masking与cross-task patching联用，子任务调度；本文研究同源技能的深度分离。
- Vaidyanathan et al., *The Curse of Multiple Mediators*, arXiv:2606.27510：https://arxiv.org/html/2606.27510 。干预效果中的组件交互；本文不将此一般原理作为首次贡献。
- Li, *Models Take Notes at Prefill*, arXiv:2606.17107：https://arxiv.org/html/2606.17107 。下游缓存结论、技能缓存重定位和组合；本文比较不同深度的迁移与来源访问，并在联合修复后重新切断读取。
