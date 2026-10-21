## 2026-10-21 后续讨论：优先LogicBench

- 用户指出GSM8K固定skill未必带来accuracy提升，并提出允许组内部分receiver错误。已核查原depth代码：逐题gold=1/receiver=0足以保持现有归一化，不需要其他组员receiver全错；建议逐题gold正确、receiver和none错误，排除答对题而非整组纳入。
- 研究优先级改为LogicBench，GSM8K为后备；现成配对和文献增益不保证当前四模型有效交集。建议先全760题三基线与分层覆盖核验，任何干预前冻结入选ID及fixed-wrong，不按曲线筛选。
- 原两任务若统一逐题口径，先审计缺失深度记录；组级screen后未生成的新增题需补干预，不能只重聚合或当0。旧严格组结果保留作敏感性分析。机制原最终逐题口径不改。
- 详细设计已落盘reports/第三benchmark替代调研_20261021.md新增节；本轮只更新研究设计，未启动GPU、未更新论文/Overleaf。CHAMP继续废弃，迟到监督不恢复。

## 当前任务已完成：清理与替代方案交付

- 删除本轮461文件，共397756385逻辑字节（约379MiB）；本地新CHAMP实验目录、4个/tmp产物、个人HDD实验目录及两盘专用探针均已删除，4个终态Job删除命令均exit0。小时监督清理前已停止；迟到的旧CHAMP消息不触发恢复。
- 保留共享历史SRA资产和评分代码；不改4×2论文/Overleaf。不启动本轮替代GPU实验。删除只覆盖用户本轮放弃的新实验及专用产物；范围与回执见cleanup-local.json/cleanup-remote.json。
- 交付reports/第三benchmark替代调研_20261021.md；原作者公开JSON/text核验：GSM8K1319题，BoT21模板但无原生逐题映射；LogicBench760题/19组各40、542BQA/218MCQA；SRA-BigCodeBench1140题无单skill题；BBH计数/多步算术/词排序各250题。URL/SHA在public-asset-inspection.json与logicbench-static.json。
- 推荐先核查GSM8K+公开模板的题面标注/覆盖；LogicBench是现成skill条件备选，但组级receiver全错筛选与小答案空间冲突。严格维持原筛选可能无足够人群；统一逐题主分析须同步对旧两任务重聚合，不能对新任务偷偷换口径。当前没有已验证的直接替换。
- 验证：本地目录/临时文件不存在、JSON统计自一致、脚本语法检查；远端三目录删除回执与复验；四Job删除回执。无模型下载、推理或稿件更新。本轮完成后仅提交本轮新报告/回执/脚本及相关交接修改，不纳入旧family_depth和DATA-CONSISTENCY遗留修改。

# 第三benchmark替换与CHAMP清理（2026-10-21）

用户目标：放弃CHAMP，删除相关内容和文件，考虑其他benchmark替换方案。
范围：清理本轮新建本地experiments/champ_20261020、个人HDD/champ-20261020-v1及两盘champ-20261020-probes；移除主交接中的CHAMP续接指令。保留共享历史SRA资产/评分代码、原4×2论文及其他任务。不扩删历史共享数据。
删除授权：用户本轮明确要求；执行前核验精确路径、文件数/大小及引用，记录删除清单和回执。本地/远端未提交产物删除后通常不可恢复，用户已明确要求放弃本轮相关产物。
进度：新交接已建立；下一步只读清点、确认监督已停→清理→重调研备选。新实验未获本轮启动指令，不自动跑候选GPU。
替代标准：沿用原paper问题、单次文本skill、生成解答和可客观抽取短答案、可复用概念/过程skill、足够分组与跨题donor；不以是否T<R/repair为选择标准。

## Open Ideas / 值得深挖的问题
暂未新增；方法结论不靠挑选支持既有故事的数据集。
