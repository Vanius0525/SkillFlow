# tier_b2 — 选装置（Tier B v2）

生成器 `build.py` 的 docstring 是这份题集的完整说明；这里只放跑的人需要的三行。

```bash
python build.py            # 写 tasks.jsonl
python build.py --check    # 验证提交进仓库的那份和生成器逐字节一致
```

`--check` 顺带验两件只有在这里才验得了的事：

1. 四个选项仍然构成 2×2（`correct` / `wrong_const` / `wrong_rel` / `wrong_both`），
   金标字母落在 `correct` 上，两个轴都不退化。
2. 它引用的六个关系式和五个常数在 `../tier_b/SKILL.pchem-*.md` 里**逐字存在**。
   这一条一旦漂了，题目就没法从文档里答出来，而那种零结果看起来和「skill 没用」
   一模一样——这是整个题集最容易悄悄坏掉的地方。

`setup-whitebox.sh` 会跑这个 `--check`，所以流水线每次开跑之前都会验一遍。

## 为什么不用 SciBench 原题

试过。关系式标签没法从题干机械地定出来：九个关系式的关键词匹配在 196 道题里只有
53 道唯一命中，139 道一个都不命中，而且命中的严重偏向理想气体（23/53）。
SciBench 自带的 `*_sol.json` 只覆盖 42 道，也不够。手工标 196 道化学题的
可靠性达不到「金标」的要求，靠关键词标又会把标签和 skill 的决策表绑在一起。

代价是效度：题不再是外部的。这一条写在 `build.py` 的 docstring、
`README.md` 的 Tier B v2 一节、以及 `HANDOFF-whitebox.md` §15 里，三处一致。
