# 最新版 paper figure

本目录对应截图要求的四图三表稿，基线为三图三表版141c8fb。
Figure 1为结果teaser，Figure 2为详细干预设计，Figure 3为六组深度实验，Figure 4为源状态/缓存恢复及读取路径结果。重复注入保留在正文文字和附录，不作为主图。

## 文件使用

- `figures/`：最新版矢量PDF、可编辑SVG、PNG预览；插入论文优先用PDF。
- `latex/figure1.tex`至`figure4.tex`：原稿完整浮动体，包括caption、Description和label。
- `latex/table1.tex`至`table3.tex`：三张主表；`tableA1.tex`为附录重测表。`tables/`含表2依赖，`latex/style.tex`含颜色定义。
- `figures.tex`：可独立编译的图表合集，使用pdfLaTeX；图表编号与正文一致，合集中的附录表编号为4。
- `source/`：当前绘图脚本快照与足够重新生成图的汇总数据，不包含模型权重或推理日志。权威脚本位于仓库`tools/`，本目录由导出脚本刷新。
- `manifest.json`：所有资源SHA256。交接入口为仓库`HANDOFF-NEXT-CONVERSATION.md`，桌面交付同样提供此文件。

## 各图用途与读法

| 图 | 作用 | 数据与含义 |
|---|---|---|
| Figure 1 | 让读者先看到完整发现 | Qwen3-8B/MedCalc：早期状态迁移恢复0.89的skill增益，随后残差迁移下降但源仍被需要，L16联合替换部分恢复且后续读取仍重要。三panel分别135/134/114题，不能把它们当作同一组逐题追踪。 |
| Figure 2 | 解释替换哪些组件、保留哪些计算、怎样切断读取 | 设计示意而非数据图。S为源残差状态，C为源位置KV缓存0至L层，SC为两者；接收方早期reader计算保留。SC后reader cut从L+1开始，原donor路径切断从L开始。 |
| Figure 3 | 展示分离现象及其范围 | 3模型×2任务，每层实测；蓝为残差迁移恢复rho，橙为source-attention dependence d=1-q（原本答对、屏蔽后变错的比例）；共同样本边界另见Table 2。浅色区为首次半效应边界之间的区间，存在重新越阈，不能称为严格单调阶段。 |
| Figure 4 | 展示恢复和继续读取的机制证据 | 114题/14skill，左侧数值热力图呈现S、C、SC及SC后recut准确率（固定0–100%色阶）；右侧横向点图比较reader-to-source与source-to-source切断造成的准确率损失。L16恢复明显且recut损害；L24无同样额外recut损失。 |

Figure 1与Figure 3统一画source-attention dependence d=1-q。中间关注rho<0.5且d>0.5；边界为d首次≤0.5，等价于q首次≥0.5。后续新增模型与图表沿用这一方案；底层retention=q数据保留，展示时取补数。
KV表示attention的key/value缓存，保存已处理token的注意力向量；reader指skill span以外的question/answer token。联合替换没有重放或修复全部接收方计算历史。

## 表格说明

- Table 1：验证早期探针，正确内容、位置排列与噪声对照；末位置替换与整段替换容量不同。
- Table 2：共同样本的边界T/R及差值Delta，仅显示点估计。
- Table 3：114题机制对比的准确率差，单位为百分点，仅显示点估计；避免将恢复图的原始单元格再列一遍。
- 附录表：全样本与开发子样本、不同筛选规则的对照。

## 重新生成

需要Python、NumPy、Matplotlib及Linux Libertine字体。可通过PAPER_FONT_DIR指定字体目录；字体缺失会明确报错，不静默替换。命令在本目录运行：

```bash
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/fig_teaser.py
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/fig_intervention_design.py
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/style_main_figures.py
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/fig_mechanism_results.py
```

快照脚本输出至`source/figures/`，不覆盖本目录已交付的`figures/`。
从完整仓库刷新本目录：`python3 tools/export_figure_bundle.py`。
数据均来自既有完成实验；本轮不新增推理。详细核验见仓库audit/FOUR-FIGURE-STORY-20261017.json。
