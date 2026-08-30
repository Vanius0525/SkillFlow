# P1 — Harness 校准（GATE-1）

执行 2026-08-31，Inspire 4090 容器。**GATE-1 通过。**

配置：Qwen3-4B（`models/Qwen3-4B`，本次新下载）、vLLM、H-repro
（单轮、`--no-tool-protocol`、temp 0.7、seed 0、`thinking=False`、max_tokens 4096），
全集 1,100 实例。命令见 `../howskill/README.md` §P1。

## 结果

| 臂 | 我们 | SRA-Bench 发表 | 偏差 | 95% CI（calculator 聚类） |
|---|---|---|---|---|
| Direct (`no_skill`) | **22.0%**（242/1100） | 22.0 | 0.0pp | [15.5, 29.3] |
| Oracle (`gold`) | **69.6%**（766/1100） | 73.5 | −3.9pp | [61.2, 77.1] |

两个发表值都落在各自 CI 内 —— 偏差在 calculator 级抽样噪声之内。

成本：Direct 1,174 tok / 1.0 轮 / 0 次调用；Oracle 3,392 tok / 1.8 轮 / 0.9 次调用（**2.9×**）。

**结论**：`prompts.py` / `grade.py` 对 SR-Agents 的移植正确，抽取与判分与上游一致。
这是整个协议唯一的外部检验，P2 及之后的绝对分因此有了立足点。

## 诊断

| 量 | 值 | 含义 |
|---|---|---|
| `no_answer` | **0 / 1100** | 抽取器从未失手，README 排查清单第 2、3 项排除 |
| `stop_reason = max_rounds` | 52（4.7%），**准确率 0.0%** | −3.9pp 的全部来源 |
| `stop_reason = answered` | 1,048，准确率 73.1% | 剔掉撞上限的即与 73.5 重合 |
| `n_tool_calls > 0` | 600 / 1100（55%） | 工具循环确实在跑 |

**5 轮上限吃掉了整个差距。** 上游 `_MAX_TOOL_ROUNDS` 同样是 5，所以这不是我们的偏离，
是同一个上限在这份权重/采样下咬得更紧。**报数仍报 69.6%** —— 73.1 是剔除失败样本后的值，
只作定位用，不作结果报出。

## 一个待查的观察

调用了工具的实例**准确率更低**：`tool>0` 62.8%（n=600）vs `tool==0` 77.8%（n=500）。

⚠️ 不可作因果读 —— 几乎肯定含选择效应（难的 calculator 才逼出工具调用）。
需要按 calculator 分层后再看组内差。若组内差仍显著为负，说明是调用本身在拖后腿
（参数抽错、单位未归一），这对 P5 的 2×2（「知道有工具」vs「工具真能用」）是强先验。
这里是 4B + H-repro，主实验是 8B + H-agent，不能直接外推。

## 操作备注

- `run-server.sh stop` 只 kill 父 PID，vLLM 的 EngineCore 子进程会活下来占着显存，
  下一次 start 报 `Engine core initialization failed`。切模型固定用
  `pkill -f "vllm serve"; sleep 5` 再确认 `nvidia-smi --query-compute-apps`。
- `data/medcalcbench.json` 按 calculator 排成 55 段 × 20 条，`--n-per-calc 0` 时
  `run.py` 的 `subset` 原样返回。**跑动中的累计 acc 不可读** —— 它是前若干个
  calculator 的成绩，不是随机样本。只看末尾汇总行。
- P1 的 1,100 条轨迹可作 P0-4（中间值解析器人工校准）的校准集，但它是单轮的；
  step 级读数的真正校准应等 P2 的 agentic 轨迹。
