# 正文实验完成度核验（2026-10-20）

在既定冻结候选集与各suite独立基线下，主比较4模型×2 benchmark的8格、补充Qwen0.6的2格，深度实验均已完成并有审计依据。内容/位置、固定L2、跨题、窗口、bridge、repair、edges共70个模型×任务×suite格均有结果；其中Qwen8/MedCalc六格沿用原始已验证实验，其他64格本轮按协议核验。

本轮未更新论文，不能把数据齐全当交付完成。当前正文仍保留Qwen8、Mistral/TheoremQA Pending。

| 模型 | benchmark | 共同题数/组数 | T/R（首次50%边界） |
|---|---|---:|---:|
| Qwen3-8B | MedCalc | 134/14 | 13/25 |
| Qwen3-0.6B | MedCalc | 90/21 | 11/22 |
| Mistral-7B | MedCalc | 46/16 | 7/27 |
| Qwen3-8B | TheoremQA | 82/66 | 13/21 |
| Mistral-7B-Instruct-v0.3 | TheoremQA | 72/58 | 7/19 |
| llama | medcalc | 112/20 | 7/18 |
| llama | theoremqa | 92/71 | 6/18 |
| deepseek | medcalc | 25/13 | 6/21 |
| deepseek | theoremqa | 54/45 | 4/19 |
| Qwen3-0.6B | TheoremQA | 122/92 | 11/20 |

80个family文件/87,915条记录完成网格和基线重建；6,024项已执行身份对照无失败。新评分无标签变化；DeepSeek corrected54 edges/repair 54题基线token一致，各自有效46题。旧DeepSeek深度的300个缺失键已由5题scorefix补齐，合并后无缺失、无token漂移。

HDD整盘仍余约25TiB、inode充足，个人目录占约58GiB。Errno122说明受配额约束，精确限额未查得。artifacts约26GiB、support_opd_20261002约12GiB是其他研究产物；models约12GiB；wheelhouse约3GiB。均未删除。审计已改为不写共享盘，本次任务不受阻；长期恢复持久写入仍需核对可再生缓存/旧checkpoint用途后经用户确认清理，或由管理员调高配额。

证据边界：
- These are frozen conditional candidate populations, not full-benchmark sweeps for every model.
- Historical Qwen8/MedCalc support is reused; all 70 cells are not uniform reruns.
- Same-family and cross-question donor availability restrict some cells; absent donors are not imputed as zero.
- Depth and mechanism/controls use independently screened populations and different protocols; do not impose one denominator.
- Exact historical knockout budget equivalence for regenerated legacy TheoremQA remains unverified.
- Old DeepSeek depth missing records are resolved by merging scorefix supplements; do not double-count baselines.
- HDD quota remains unresolved for durable writes; audit reports were returned directly to local storage.
