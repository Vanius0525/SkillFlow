# WWW 引言关联的先例核查与本稿写法

日期：2026-10-12。范围：只调整现稿叙事，不增加 Web 实验。以下区分录用事实、论文内容与对本稿的判断，不推断审稿人的录用原因。

## 结论

确实存在通过 Web 服务动机引出通用模型研究、实验主要采用非 Web 专用 benchmark 的 WWW 正会论文。可以借鉴“具体场景 → 可研究的底层问题 → 受控验证”的结构。不能据此推出“首页出现 Web 就必然满足 2027 范围要求”。

2027 官网要求首页说明对 Web 和所投 track 的相关性，并要求回答具体 Web 科学问题，仅使用 Web 数据或 API 不够。[官方 CFP](https://www2027.thewebconf.org/research-track-papers/)

本稿已将第一页开头改为：Web 检索系统需要决定怎样交付和保留外部程序文档 → 模型形成的状态什么时候能够代替文档、什么时候仍需访问源 token → 固定正确文档的受控 reader 研究。正文不声称跑过检索、网页操作、HTML 压缩或端到端 Web 系统。最贴近的是 Search, Recommendation, and Retrieval-Augmented AI；最终范围判断仍由会议作出。

## 直接可借鉴：AIM

**标题**：AI Model Modulation with Logits Redistribution。  
**出处**：WWW 2025，4699–4709，DOI 10.1145/3696410.3714737。  
**一手材料**：[作者公开论文](https://www.zihan.com.au/assets/files/WWW25AIM.pdf)、[会议目录](https://archives.iw3c2.org/www2025/www2025-proceedings.pdf)、[大学机构存档](https://digital.library.adelaide.edu.au/items/23b15c77-af84-4ff7-8bb0-b83b2f1803bd)。  
**阅读深度**：全文可访问，重点核对 PDF p1–2 和 §4.1–4.2。

首页以在线模型服务的免费/付费档位为一个具体动机，并给出在线服务例子；核心方法是在输出 logits 上调节分布。实验采用 CIFAR-10/100、ADE20K、KITTI、GSM8K、MMLU，涵盖视觉模型与 Llama，并未把浏览器交互作为评价对象。

**一句话结论**：在线服务需求可以引出通用模型机制/方法，并以通用任务验证。  
**与本项目关系**：这是较强的写法先例，但其方法直接实现服务商所需的可控质量分级，动机与所测能力的联系比“任何 LLM 都能用于 Web”具体。我们也应明确落到“源文档依赖的判定”，而非空泛的 Web agent 潜在应用。不能称其研究结论与 Web 完全无关。

## 较贴近但版本核验不完整：postEdit

**标题**：Assessing and Post-Processing Black Box Large Language Models for Knowledge Editing。  
**出处**：WWW 2025，1716–1732，DOI 10.1145/3696410.3714732。  
**一手材料**：[会议投稿 PDF](https://openreview.net/pdf?id=aGhk1VNcRJ)、[作者仓库及正式引用](https://github.com/songxiaoshuai/postEdit)、[早期 arXiv 2402.08631v2](https://arxiv.org/html/2402.08631v2)。  
**阅读深度**：搜索索引可读取 WWW 投稿版首页，开头明确从 Web 信息传播与 Web 应用中的 LLM 引入；OpenReview 直连遇到验证页，下载又遇 TLS 错误，未取得完整 WWW 版 PDF。早期 arXiv 全文和作者仓库可访问，不能冒充最终版全文核对。

方法是黑盒模型输出后处理，评价知识更新与原有表达保留。作者代码含 CounterFact/zsRE 数据流程。早期稿与 WWW 稿标题、引言不同，录用由正式会议目录和作者引用交叉核实。

**一句话结论**：有“Web 应用引入 → 通用知识编辑”的真实正会先例。  
**与本项目关系**：支持应用动机与底层受控研究相连的叙事；由于未完整取得最终全文，不把它作为“全篇只有 intro 涉及 Web”的确定证据。

## 相近写法但不能算完全无 Web 联系：SheetAgent

**标题**：SheetAgent: Towards a Generalist Agent for Spreadsheet Reasoning and Manipulation via Large Language Models。  
**出处**：WWW 2025，DOI 10.1145/3696410.3714962，arXiv:2403.03636v3。  
**一手全文**：[WWW 版 HTML](https://arxiv.org/html/2403.03636v3)。  
**阅读深度**：摘要、引言、§4、数据附录。

摘要明确以 Web 中普遍存在的电子表格为动机，引言用 Google Sheets/Excel 工作说明问题。实验主要是 spreadsheet 操作与表格推理，采用 SheetRM、SheetCopilot benchmark、WikiTableQuestions、FeTaQA、TabFact，包含来自 Wikipedia 的表格。

**一句话结论**：没有浏览器评测也可以研究 Web 相关的通用工作内容。  
**与本项目关系**：可参考由内容使用需求引出研究问题的方式，但它有具体表格任务，不能描述为实验完全与 Web 无关。

## 排除的反例：Division-of-Thoughts

**标题**：Division-of-Thoughts: Harnessing Hybrid Language Model Synergy for Efficient On-Device Agents。  
**出处**：WWW 2025，DOI 10.1145/3696410.3714765，arXiv:2502.04392。  
**一手全文**：[WWW 版 HTML](https://arxiv.org/html/2502.04392v1)。

从在线助手引入，随后研究端云模型协同；但实验表实际包含 WebShop。**不能用它证明只修改 intro 就够**。它仍可作为“应用需求 → 底层技术瓶颈”的结构参考。

## 本稿采用的背景引用

**HtmlRAG: HTML is Better Than Plain Text for Modeling Retrieved Knowledge in RAG Systems**，WWW 2025，DOI 10.1145/3696410.3714546，arXiv:2411.02959v2。  
[一手全文](https://arxiv.org/html/2411.02959v2)。

它直接研究 Web 文档交付格式与内容保留，支持本稿引言的外部动机；它不是“Web 无关”先例，也不证明本稿的 hidden-state 结果能直接改进 HTML 压缩。新增引用仅用于引言，未把先例列表硬塞进机制 related work。

## 修改后的论证边界

- 首页已有具体 Web 问题及 reader 侧受控研究定位，满足“明确说明联系”这一写作动作。
- 当前结果可以支持 LLM 上下文表示的诊断原则，不能宣称已提升 Web 检索/任务成功率或节省系统成本。
- “已录用”不等于“因为这段 intro 而录用”；年份、track、整体贡献都可能影响判断。
- 用户本轮不做 Web 实验的约束已遵守，补实验方案也只围绕 Figure 4 的中间区间。
