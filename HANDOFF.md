# HANDOFF — GAIA scaffold 对比怎么在远端跑

面向"接手这台服务器、要把实验跑出来"的人。只写操作和踩过的坑，方法论看
`experiments-agents.sh` 顶部的注释。

最后更新：2026-08-19

---

## 0. 现状速览

| scaffold | 状态 | 说明 |
|---|---|---|
| SkillFlow | 可跑 | 本仓库自己的方法 |
| smolagents | 可跑 | HF CodeAgent |
| inspect | **阻塞** | 数据链路已通，卡在 `web_browser` 需要沙箱服务，见 §5 |

所以现在的入口是**两家模式**：

```bash
./experiments-agents-noinspect.sh
```

inspect 修好之后换回 `./experiments-agents.sh`，其他一切不变 —— 两个脚本共用同
一套批次逻辑、同一套 run 目录格式，产出的 jsonl 可以直接并排比较。

---

## 1. 远端从零跑起来

```bash
cd /inspire/qb-dev/project/multi-agent/czxs253130660/agent-harness
git pull
source env.sh                    # 只存在服务器上，不在仓库里
```

`env.sh` 里有 vLLM 地址、模型名、API key 等。**它不进 git**，换机器要自己重建。

启动模型服务：

```bash
./run-server.sh start
curl -sf http://localhost:8000/health && echo OK
```

装外部依赖（首次或换环境时）：

```bash
./setup-external.sh              # 装 + 逐项体检
./setup-external.sh --check      # 只查不装
```

GAIA 数据是 LFS 存的，首次 clone 之后需要：

```bash
git lfs pull
head -c 4 GAIA/2023/validation/metadata.parquet    # 要看到 PAR1，不是指针文件
```

---

## 2. GAIA 数据这条链（inspect 专有，踩过三个坑）

只跑两家模式的话这一节可以跳过 —— SkillFlow 和 smolagents 直接读仓库里的
`GAIA/`，不经过 huggingface_hub。

### 为什么需要 `run_inspect_gaia.py`

`inspect_evals/gaia/dataset.py:49` **无条件**调 `snapshot_download`，没有"本地已
就位就跳过"的分支。而且 `local_dir` 一填，huggingface_hub 连离线捷径都走不了：
它得先列远端 repo tree 才知道该有哪些文件，所以在看磁盘之前就已经上网了。

GAIA 是 gated 数据集，这次联网需要通过审批的 HF 账号。仓库里的 `GAIA/` 就是这
个数据集的完整副本（授权在当初 commit 进来时就付过了），所以那次下载纯属仪式。

`run_inspect_gaia.py` 在本地副本齐全时把 `snapshot_download` 换成"直接返回本地
目录"；副本不在就**什么都不改**，原样退回上游的下载逻辑。

> **写论文时必须声明**：eval 是上游的，数据集是同一个 gated release 的本地副本，
> 而不是按 pin 住的 revision 重新拉取的。

### 三个坑

1. **`HF_HUB_OFFLINE=1` 救不了这里，只会让它必然失败。** 离线模式不会让
   `snapshot_download` 改读 `local_dir`，只会让它在列 tree 那一步抛
   `OfflineModeIsEnabled`。`experiments-agents.sh` 里有 `unset HF_HUB_OFFLINE`。
   `env.sh` 里目前导了 `HF_HUB_OFFLINE=1`，脚本会覆盖掉，手动跑要自己注意。

2. **环境变量名是 `INSPECT_EVALS_CACHE_DIR`**，不是 `..._PATH`（后者是
   `constants.py` 里那个模块级常量的名字，不是环境变量）。写错的话数据摆一处、
   加载器去另一处找，两边各自都"看起来正常"。不设则退回
   `platformdirs.user_cache_dir("inspect_evals")`，Linux 上是 `~/.cache/inspect_evals`。
   `run_inspect_gaia.py` 现在会自动兜底到 `<repo>/.inspect_cache`。

3. **中断的下载会留下半截目录。** 403 打断的 `snapshot_download` 会留下一个有
   `2023/` 但没有 `metadata.parquet` 的目录。它有两重坑：挡住 `ln -s`，而且
   `ln -s 源 已存在的目录` 会把软链建到那个目录**里面**去，命令退出 0，看着像
   成功实际没接上。

### 填数据

```bash
./setup-external.sh --only gaia
```

或者手动（`--only gaia` 会连带跑第 0 节的公共前提检查，那里可能触发
`pip install --upgrade openai`，不想让它动环境就用这个）：

```bash
mkdir -p .inspect_cache/gaia_dataset
ln -s "$PWD/GAIA" .inspect_cache/gaia_dataset/GAIA
ls -ld .inspect_cache/gaia_dataset/GAIA     # 开头必须是 l，-d 不能少
```

`ls` 不加 `-d` 列的是目录**内容**，看到的 `GAIA -> ...` 可能是错建在里面的那个链。

用软链而不是拷贝，是因为 `snapshot_download` 已经被换掉，那个目录不会有任何写
入，80MB 的独立副本只剩"两份数据可能漂移"这一个后果。文件系统不支持软链时
`setup-external.sh` 会自动退回 `cp -r`。

---

## 3. 跑实验

```bash
./experiments-agents-noinspect.sh --dry-run    # 先看会跑哪些 cell
MAXQ=3 ./experiments-agents-noinspect.sh       # 冒烟，每 level 3 题
./experiments-agents-noinspect.sh              # 全量
```

常用环境变量（完整列表见 `experiments-agents.sh` 顶部）：

| 变量 | 默认 | 含义 |
|---|---|---|
| `LEVELS` | `"1 2"` | GAIA 难度档。L3 上 8B 基本 0 分，只拉长时间 |
| `MAXQ` | `0` | 每 level 题数上限，0 = 全量。非 0 就是冒烟，不是正式结果 |
| `TIMEOUT` | `300` | 每题墙钟上限，三家共用 |
| `CONCURRENCY` | `3` | **必须三家一致**，否则准确率差里会混进排队效应 |
| `REPEATS` | `1` | 想要方差估计就设 3 |
| `K` | `8` | SkillFlow 的 top-k |
| `RUN_ID` | 时间戳 | 见下 |

### 后台跑（全量要几小时）

`experiments-agents-noinspect.sh` **默认自动转后台**，直接跑就行，起来之后可以
关终端：

```bash
./experiments-agents-noinspect.sh
```

它会打印 run id 和一组跟进命令，然后立刻把终端还给你。产物、日志、pid 都在
`logs/<run id>/` 和 `results/<run id>/` 下。

```bash
tail -f logs/$RUN_ID/console.log             # 总进度（哪个 cell 在跑）
tail -f logs/$RUN_ID/agents_smolagents.log   # 单个 cell 的实时输出
pgrep -af experiments-agents                 # 还活着没
kill $(cat logs/$RUN_ID/run.pid)             # 停掉
```

> **关终端之前先 `tail -5 logs/$RUN_ID/console.log` 确认它真起来了。**
> venv 和 vLLM 这两项在脱离**之前**就在前台查了，挂了会当场报错、不会转后台；
> 但 LFS 指针和 scorer 契约那两项慢一些，跑在子进程里，失败只会落进
> console.log。

例外情况：

- `--dry-run` 自动留在前台（它就是给你看输出的）
- `--fg` 强制前台，在 tmux 里跑或者调试时用

```bash
tmux new -s gaia
./experiments-agents-noinspect.sh --fg
# Ctrl-B 然后 D 脱离；tmux attach -t gaia 接回来
```

`experiments-agents.sh`（三家模式）**没有**这个自动行为，要手动 nohup：

```bash
RUN_ID=$(date +%Y%m%d-%H%M%S)
mkdir -p logs/$RUN_ID
RUN_ID=$RUN_ID nohup ./experiments-agents.sh > logs/$RUN_ID/console.log 2>&1 &
disown
```

中途断了不用从头来 —— `.done` 标记在 run 目录里，同一个 `RUN_ID` 续跑会跳过已
完成的 cell：

```bash
RUN_ID=<那次的> ./experiments-agents-noinspect.sh
```

### run 目录

每次调用落到自己的目录，跑第二遍不会盖掉第一遍：

```
results/20260818-175613/
    run-info.txt              配置快照 + git commit
    agents_smolagents.jsonl
    agents_skillflow_k8.jsonl
    inspect_logs/*.eval
logs/20260818-175613/
    agents_smolagents.log
    .done/                    完成标记
results/latest -> 20260818-175613
```

`.done` 标记在 run 目录里，所以续跑和新跑由 `RUN_ID` 一个变量决定：

```bash
./experiments-agents.sh                          # 新的一批
RUN_ID=20260818-175613 ./experiments-agents.sh   # 接着那批，已完成的 cell 跳过
```

某个 cell 挂了，修好之后用 `RUN_ID=<那次的>` 续跑即可，不用从头来。脚本结尾在
有失败时会把这条命令打出来。

---

## 4. 看结果

```bash
python summarize-agents.py --results-dir results/20260818-175613
python summarize-agents.py --results-dir results/latest        # 最近一次启动的
inspect view --log-dir results/20260818-175613/inspect_logs    # inspect 那一格
```

**跑完务必看截断率。** `TIMEOUT` 砍掉的题和答错的题在准确率里长得一模一样，截
断率高的话这批数字反映的是时间预算而不是 scaffold。

三家的 token 口径不完全可比（各自 prompt 开销不同），token 只作成本参考，结论
看准确率。

---

## 5. 当前阻塞：inspect 的 `web_browser`

### 症状

```
PrerequisiteError: The web browser service was not found in any of the
sandboxes for this sample.
```

在这之前会有两条 WARNING：`Task declares sandbox 'docker' ... but the 'local'
sandbox ... tools will not be available`。

### 原因

`inspect_evals/gaia/gaia.py` 的 `default_solver`：

```python
tools=[bash(code_timeout), python(code_timeout)] + web_browser(),
```

`web_browser()` 不是进程内工具，是**沙箱里的一个服务**。
`legacy_tool_support_sandbox` 用 `sandbox_with("inspect-tool-support", True)` 去
每个 sandbox 里探这个可执行文件，探不到就抛 `PrerequisiteError`。官方靠
`aisiuk/inspect-tool-support` 这个 Docker 镜像提供它。

这台机器上 Docker daemon 起不来，只能用 `--sandbox local`，于是没有这个服务。
`bash` 和 `python` 在 local 下能跑（直接在进程里执行），`web_browser` 不行。

**跟 GAIA 数据无关** —— 数据那条链已经验证通了：补丁生效、86 道 validation 载
入、模型解析成功、agent 真的开始调工具了。

### 三条路

| 方案 | 代价 | 偏离程度 |
|---|---|---|
| 装 `inspect-tool-support` 到宿主 venv | 要 Playwright + 浏览器二进制，容器里可能装不上 | 最小 |
| 传自定义 solver 去掉 `web_browser` | 一行配置 | 大 |
| Docker sandbox | daemon 起不来 | 无，但不可行 |

先试第一条，一条命令，可回退：

```bash
python -m pip install inspect-tool-support
inspect-tool-support post-install     # 这步下浏览器二进制，容器里可能失败
which inspect-tool-support            # 要在 PATH 上，local sandbox 才探得到
```

`post-install` 在缺系统依赖的容器里可能装不上 —— `setup-external.sh` 开头跳过
Magentic-One 就是同一个理由（Playwright + 浏览器二进制）。

装成了之后：

```bash
./smoke-inspect-gaia.sh              # 八层全跑，最后真跑一题
./experiments-agents.sh              # 换回三家模式
```

**两个必须写进论文的点**：

- 即使装上，浏览器跑在**宿主进程**里而不是沙箱里，这个隔离性差异要和
  `--sandbox local` 一起声明。
- 这台机器网络走 `hf-mirror`，是受限环境。浏览器能不能出网是另一回事。仓库里有
  `install-searxng.sh` / `run-searxng.sh`，smolagents 那边应该指向本地 SearxNG，
  而 inspect 的 `web_browser` 不走那条路 —— 两家的联网能力可能本来就不对等，这
  是比较有效性的问题，不是配置问题。

第二条路（去掉浏览器）是**研究设计决定，不是技术决定**：去掉之后 inspect 就不再
是"官方参考实现"，三家的能力面也不再对齐。

---

## 6. 冒烟测试

```bash
./smoke-inspect-gaia.sh --no-eval    # 只跑离线部分，不需要 vLLM
./smoke-inspect-gaia.sh              # 全套，最后真跑一题
```

八层，前一层不过就停 —— 因为这条链上每一层坏掉，报出来的都是同一个
`GatedRepoError`/403，单看那个报错分不出是 LFS 没拉、路径不对、还是补丁没挂上。

| 层 | 测什么 |
|---|---|
| 1 | `GAIA/` 是真 parquet 还是 LFS 指针 |
| 2 | 暂存路径能读到，且穿过软链读到的也是 `PAR1` |
| 3 | `inspect_ai` / `inspect_evals` 可导入 |
| 4 | `GAIA_DATASET_DIR` 是否**就是**第 2 层那个路径 |
| 5 | `HF_HUB_OFFLINE=1` 下建真 task |
| 6 | 题数、首题 id、附件文件真的在磁盘上 |
| 7 | vLLM 活着，且 model id 一字不差 |
| 8 | 真跑一题（凭据映射 / sandbox / agent / scorer） |

第 5 层最有分量：平时不该设 `HF_HUB_OFFLINE`，但在这里反过来当断言用 —— 补丁真
挂上就不会有网络请求，所以强制离线也必须能过。**通过 = 证明零联网**，而不只是
"这次碰巧没报错"。

第 8 层目前会停在 §5 那个 `web_browser` 问题上，这是预期的。

---

## 7. 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `GatedRepoError: 403` | 补丁没生效或数据没填 | 跑 `./smoke-inspect-gaia.sh --no-eval` 定位到具体层 |
| `OfflineModeIsEnabled` | `HF_HUB_OFFLINE=1` + 走了真下载 | `unset HF_HUB_OFFLINE`，然后填数据 |
| `no usable local GAIA copy at /root/.cache/...` | 缓存路径没指到仓库 | `export INSPECT_EVALS_CACHE_DIR=$PWD/.inspect_cache` |
| `Model name '' should be in the format of ...` | 手动跑时 `$INSPECT_MODEL` 是空的 | 那变量只活在 `experiments-agents.sh` 里，手动跑要显式传 |
| `不是有效 parquet(LFS 指针?)` | LFS 没拉 | `git lfs pull` |
| `$DEST 存在但不完整` | 中断的下载留下半截目录 | 先 `find` 看内容，确认后 `rm -rf` 再重建软链 |
| `PrerequisiteError: web browser service` | 见 §5 | — |

手动跑单题（`$INSPECT_MODEL` 等变量不在环境里，要显式给）：

```bash
LOCAL_API_KEY="${OPENAI_API_KEY:-EMPTY}" LOCAL_BASE_URL="${QWEN_BASE_URL:-http://localhost:8000/v1}" \
python run_inspect_gaia.py eval inspect_evals/gaia_level1 \
  --model "openai-api/local/${QWEN_MODEL:-Qwen/Qwen3-8B}" \
  --sandbox local --limit 1
```

`LOCAL_*` 这两个变量名来自 provider 名 —— 它取自模型串的第二段
（`openai-api/`**`local`**`/...`）并大写。`experiments-agents.sh` 里是自动推的。

---

## 8. 文件地图

| 文件 | 作用 |
|---|---|
| `experiments-agents.sh` | 三家对比的批次入口，所有配置在顶部 |
| `experiments-agents-noinspect.sh` | 两家模式（薄包装，只设 `SCAFFOLDS` 后转交） |
| `run_inspect_gaia.py` | inspect 的启动器，负责换掉 `snapshot_download` |
| `smoke-inspect-gaia.sh` | 八层冒烟测试 |
| `setup-external.sh` | 装外部依赖 + 逐项体检 + 填 GAIA 数据 |
| `summarize-agents.py` | 读 `results/<run>/agents_*.jsonl` 出对比表 |
| `run-server.sh` | vLLM 起停 |
| `env.sh` | **只在服务器上**，不进 git |
| `GAIA/` | 数据集副本，LFS 存储 |

---

## 8.5 待处理：对比里 skill 这个变量没有被隔离

**记录于 2026-08-19，之后处理。**

核过代码：`run_smolagents_gaia.py` **完全不注入 skill**，全文只有 `from skillflow
import load_gaia_tasks`（共用题目加载器）。所以三家现在是这样：

| | JSON 工具调用 | Python 代码动作 |
|---|---|---|
| **无 skill** | inspect（**目前被 web_browser 卡住**） | smolagents |
| **有 skill** | SkillFlow | 空缺 |

smolagents 那一格是**有意**只隔离 CodeAct 轴的（见 `run_smolagents_gaia.py` 头部：
CodeAct 论文报告光动作格式就值约 20 点）。但结果是 SkillFlow vs smolagents 同时
变了两个东西：

```
SkillFlow  = 有 skill + JSON 工具调用
smolagents = 无 skill + Python 代码动作
```

**SkillFlow 赢了分不清是不是 skill 的功劳；smolagents 赢了分不清是不是 CodeAct。**

### 这让修 inspect 的价值变了

inspect 是"react agent + JSON 工具 + 无 skill"，正好落在左上角那格。**它不只是
第三个参照，它是补齐 2×2 的那一块。** §5 那个 `web_browser` 问题因此比原先看起来
更值得解决。

### 还差一个更省事的臂

`skillflow.py --framework plain` 存在，但它**仍然注入 skill**（一次性 top-k、整
文档注入），是编排方式的消融，**不是 skill 的消融**。

最省事的补法是给 skillflow 加一个 `--no-skills` 臂：同一套工具、同一个契约、同一个
循环，只是不注入 skill。那样"skill 值多少"就能在**同一个 scaffold 内部**读出来，
不用跨 scaffold 比较——跨 scaffold 永远混着别的差异。

**优先级建议**：`--no-skills` 臂 > 修 inspect。前者更便宜，而且它测的正是主线问题。

---

## 9. 论文里必须声明的偏离

1. **数据集**：上游的 eval，同一个 gated release 的**本地副本**，而不是按 pin 住
   的 revision 重新拉取。
2. **沙箱**：`--sandbox local` 而非官方默认的 Docker。Inspect 官方文档说 local
   沙箱只应在"整个评测已经跑在另一层沙箱里"时使用 —— 租的容器正好是那一层，所
   以成立，但配置确实不同于官方。
3. **工具集**（如果最终去掉 `web_browser`）：inspect 那一格不再是官方参考实现。
4. **单次运行**：`REPEATS=1` 时没有方差估计。
5. **token 口径**：三家 prompt 开销不同，token 数不可直接比较。
