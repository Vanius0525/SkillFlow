# 新家族全层曲线：明日续接点

用户 2026-10-15 最新指示：先不用学校资源，明天再继续需要额外实验的部分。**当前不启动、不下载、不轮询学校资源。** 无已启动远端计算任务，无完成标记待检查。

## 当前阻碍与证据

- 本机 inspire 7.1.8，`inspire update --check` 报 7.1.12 可用，未更新。
- 2026-10-15 `inspire notebook list --workspace all --all`：所有可见 Workspace unavailable，exit 13。
- `inspire account check`：TLS 建连前 socket disconnected。不是已验证的密码错误，未进行密码登录重试。
- `curl -I --connect-timeout 10 --max-time 15 https://qz.sii.edu.cn`：SSL unexpected EOF。
- 已有 `inspire-me-wt-dev-cpu` SSH：banner exchange timeout。
- `account check --details` 同样在请求时 TLS 中断，未能得到有效代理诊断。

## 明天第一步

先读本 HANDOFF 和当前 inspire skill；检查资源与现有进程，不重复创建实例。确认本机网络/校园网/代理后，只做一次 live 资源和账号核验。进入已有 CPU 实例，定向列个人共享盘 models 和 venvs；**本轮没有核实 Llama/Gemma/DeepSeek 缓存是否存在**。

权重优先级与依据：

1. `meta-llama/Llama-3.1-8B-Instruct`：https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct ，约16GB BF16权重（估算，不含缓存），独立于当前 Qwen/Mistral 家族。
2. `google/gemma-2-9b-it` 或缓存中的 Gemma 文本模型：https://huggingface.co/google/gemma-2-9b-it ，约18GB权重估算；自定义注意力结构须专门验证屏蔽 hook。Gemma 3 多模态版不能直接假定 `model.model.layers` 路径兼容。
3. `deepseek-ai/DeepSeek-R1-Distill-Llama-8B`：https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B ，官方明确基于 Llama-3.1-8B。它适合测试 reasoning/post-training 变化，**不能算独立的 DeepSeek 原生架构家族**；Distill-Qwen 同理。长 reasoning 要记录截断，不能用较短 max_new 的失败推机制。

新下载若单次或本任务累计 >1GiB，先查询 repo 文件大小与已有缓存，报告模型/来源/个人路径/预计增量并取得确认，不以用户的运行授权代替大下载确认。所有新远端文件放个人 `/inspire/ssd/project/project-public/czxs253130660/`。

## 实验合同

- 先进行 MedCalc 和 TheoremQA 三基线（none/gold/wrong）筛查，使用新模型自己的 cells，不能借 Qwen cells 作主分析。
- 优先保持 BF16 非量化；同一 checkpoint revision、tokenizer、prompt wrapper、max_new、batch=1 baseline，记录模型/代码版本和 seed。Llama 需使用生成配置的完整 EOS/eot 停止集合；不能只假设 `tok.eos_token_id` 覆盖全部终止符。
- 对新模型验证：真实 token span 映射、donor/receiver 等长且 span 外 token 相同；同 mask 的 capture/decode；写回自身状态输出一致；屏蔽必须在 prefill 与逐 token decode 的指定所有层实际触发，4D mask 缺失要 fail closed，不能像现有 `wb_knockout` hook 那样静默 return。Gemma 本地窗口/全局注意力和 softcap 不得被破坏。
- 必须记录截断率、拒答率、可评分答案率、gold 相比 none 的实际改善。没有足够 rescued items 是适用范围结果，不是“三阶段不存在”的证据。
- 主结果用每层曲线，允许粗扫作为不入 paper 的资源 probe；不得把未完成 fill-in 画作完整曲线。共同 eligible IDs 重算并保留原始分母。
- 当前可复用入口：`howskill.sra_behave`（baseline）、`howskill.wb_spanpatch --matched --filler fixedskill --span skill`（transfer）、`howskill.wb_knockout --sweep layers`（累计注意力屏蔽）。**上面的 EOS/mask fail-closed 和模型兼容性核验尚未实现/验证，不能直接把现有脚本视为新模型已支持。**
- 20分钟以上任务用后台进程+逐条flush+唯一输出锁+sentinel；运行前写本地 manifest 和远端 PID，周期检查每10分钟记录进程、行数、日志尾部、GPU利用率和失败状态。所有任务终止则退出检查；未知状态不自动重建/重复启动。
- 当前未设置明天自动唤醒或定时器。收到用户明日续接后按此继续，无需重新询问是否启动已授权的小规模验证。
