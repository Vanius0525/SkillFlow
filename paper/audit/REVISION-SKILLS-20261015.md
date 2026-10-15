# 2026-10-15 Skill 主线、图表与共同题目核查

## 当前状态

用户要求全文优先使用 skill；保留 Abstract / Introduction / Related Work / Problem Formulation / Experiments / Conclusion。Figure 1 减少轴外文字并去掉贴标题的样本注记；Figure 2 展开跨模型跨家族；Figure 3 精简；所有表统一视觉系统。

## 新核验事实（无模型推理）

原 Figure 2(a) 仅绘 Qwen3-8B / MedCalc，但 `replication.resolved_rows()` 已含六组完整逐层曲线。新 `tools/depth_crossmodel.py` 读取同一源数据，核查合并冲突及全部层完整性，另对两种干预共同 eligible item IDs 重算曲线。共同题目仍用各自干预的 baseline，不能解释成相同 receiver 或因果机制已识别。

| Task | Model | 共同 n | T / R | R-T 的组 bootstrap 95% CI |
|---|---|---:|---:|---:|
| MedCalc | Qwen3-8B | 134 | 13 / 25 | [12,17] |
| MedCalc | Qwen3-0.6B | 90 | 11 / 22 | [10,13] |
| MedCalc | Mistral-7B | 46 | 7 / 27 | [9.975,24] |
| TheoremQA | Qwen3-8B | 63 | 13 / 21 | [5,10] |
| TheoremQA | Qwen3-0.6B | 125 | 11 / 20 | [8,10] |
| TheoremQA | Mistral-7B | 65 | 7 / 19 | [9,13] |

所有组合 2000 次重采样均有可观测 crossing，未删去无 crossing 的重复。bootstrap 顺序比例不是 p-value，不用于宣称机制显著。0.4 / 0.5 / 0.6 阈值敏感性亦保留正向边界差。Qwen3-8B / MedCalc 的 q 在 L26 再低于 0.5，不能写成严格单调三阶段；“三阶段”仅表示操作性深度区间。其他五组共同题目在首次 reading crossing 后无 0.5 recrossing。

现有数据足以执行本次跨模型验证，因此未启动启智资源，也无后台任务需要周期检查。未扩到第三模型家族，未做真实浏览器实验。

## 补充文献核查（一手 arXiv 摘要，2026-10-15）

- **Agent Workflow Memory**, arXiv:2409.07429 (2024), https://arxiv.org/abs/2409.07429 ：从历史轨迹提取可复用 workflow 并提供给 Web agent，报告 Mind2Web / WebArena 提升。关系：支撑 Web 上 skill 注入与复用的动机，不能作为隐状态转移机制证据。
- **WebXSkill: Skill Learning for Autonomous Web Agents**, arXiv:2604.13318v2 (2026), https://arxiv.org/abs/2604.13318 ：组合可执行程序和逐步文字指导，按任务检索和部署 Web skills。关系：强调 skill 传播有不同载体；本文聚焦文字 skill 在模型计算中的利用，不声称改进该系统。
- **Are Online Skill and Memory Modules Always Worth Their Tokens? A Budget-Constrained Study of Web Agents**, arXiv:2606.15017v2 (2026), https://arxiv.org/abs/2606.15017 ：在等总 token 预算下技能/记忆模块的 aggregate 优势可消失。关系：限制“Web 任务需要技能”的泛化，正文采用“已有系统使用且在相应设置中改善”的有证据表述。

## 故事线

1. Context skill 注入有收益，但状态能否被复用与源是否仍需访问不是同一问题。
2. 匹配内容与位置控制建立有效早层 transfer probe，避免用失败的末位置 probe 推理内部利用情况。
3. 六组全层曲线给出早层有效转移 / 中间弱转移但依赖读取 / 晚层较耐受切断的操作性区间。
4. 共同题目及组 bootstrap 排除样本分母不同足以解释边界排序这一替代解释。
5. 重复晚层注入约束“只因注入层数少”的解释；内容/位置与 rank 结果说明被复用对象的结构。
6. Web 动机落在技能注入、分享、状态复用与源保留的评价，而非已获得浏览器效率收益。

## 展示取舍

Figure 1 行内短标签，样本数和层只放 caption。Figure 2 六个子图；原重复窗口数据保留正文精确数字。Figure 3 主文仅展示内容与位置，完整四面板留扩展附录。谱诊断转入扩展附录，减少偏离主线。表格统一淡蓝表头、轻条纹、蓝灰规则线和行距，不以配色编码显著性。

## Open Ideas / 值得深挖的问题

沿用已有 receiver 相容性问题，本轮无足以单独立项的新发现。共同题目核查只消除分母层面的疑问，不能消除 donor/receiver 计算背景不同这一识别边界。下一步判别实验仍是晚层 skill/query 联合移植或 receiver-state 交互，而不是更多相似模型的重复曲线。

## 当场记录的反事实与表述修正

Figure 3 精简时核实：half-span 的 skill-step-centred block 恢复 0.82，但 description-centred block 也为 0.80，不能暗示前者独占有效内容。宽 block 会覆盖多个 section；正文已明确该限制。原来的 block-count 对照同样混杂语义覆盖，故只保留在扩展图，不用于“连续性是独立原因”的结论。

全文检查还修正了 setup 附录对 Table 2 的过时 0.750 引用，当前 audited accuracy 为 0.815；删除“contamination is impossible”等无法保证的绝对断言。

## 最终验证与交付

- `MPLCONFIGDIR=/tmp/skillvector-mpl python3 paper/tools/check_main_data.py`：124,560 检查通过，475 个源文件哈希。包含六组原曲线、共同 IDs、逐层重算、表格值、阈值敏感性与 bootstrap 可观测边界检查。
- `python3 whitebox/analysis/audit.py`：ALL CHECKS PASSED。
- Windows MiKTeX 独立临时目录编译：投稿版 8/12 页，扩展版正文 8 页、全文 36 页，两者无 undefined / overfull。新增表/完整补充图与迁出的细节导致扩展版增加页数。
- `skillvector-www2027.pdf`、`skillvector.pdf`、`overleaf-skillvector.zip` 均更新，目视检查首页、三张改版主图、主证据表和末页。
- 所有数据来自已有完成实验；无新启智任务，也无待轮询任务。
