# 当前图表：4个主模型 × 2个benchmark

更新：2026-10-20。仅采用Qwen3-8B、Mistral-7B、Llama-3.1-8B、DeepSeek-LLM-7B × MedCalc/TheoremQA的八组合。小模型不再纳入当前论文；原始实验与历史交接保留归档。

| 展示 | 当前覆盖与读法 |
|---|---|
| Figure 1 | 八组合概览：L2/L8状态替换准确率、按模型深度归一化的迁移/依赖边界差、L16修复增益与recut损失。三个panel使用各协议独立人群。 |
| Figure 2 | 通用于全部八组合的干预设计示意，不是模型实验结果。 |
| Figure 3 | 八组合逐层实测迁移恢复rho与技能注意力依赖d=1-q；保留重新越阈。 |
| Figure 4 | 八组合L16的S/C/SC/recut准确率及L24的三种注意力路径损失；每行标独立题数/技能数。 |
| Table 1 | 八组合L2/L8状态替换和L8内容/位置/噪声控制；报告原始准确率及独立分母。 |
| Table 2 | 八组合共同人群边界T/R与差值、深度归一化差值。 |
| Table 3 | 八组合L16修复、additive interaction、recut损失和L24路径损失差；单位百分点。 |
| Table 4（附录控制表） | 八组合跨题donor和重复注入窗口。历史Qwen8/MedCalc行是恢复率，其余为准确率，单位显式区分，不作排名。 |

合集Table 5/6分别为八组合L16修复原始准确率表及各suite独立分母表。

MC/TQA分别指MedCalc/TheoremQA。所有表格白底；所有曲线/图表只展示点估计。L8不是所有模型的早层；Mistral/MedCalc的additive interaction为负，不能称统一正交互。历史Qwen8/MedCalc的筛选与其他行不同，不能把各suite分母混用。

`latex/`为当前浮动体，`tables/`为其依赖，`figures/`为矢量PDF/SVG及PNG，`Figures-and-Tables.pdf`为独立编译合集。`source/values/eight-cell-display-values.json`绑定r3来源哈希；`source/values/depth-current-values.json`仅含八组合。旧历史文件保留，不作为当前生成入口。

从仓库运行：

```bash
python tools/integrate_audited_results.py
python tools/build_boundary_table.py
python tools/build_eight_cell_displays.py
MPLCONFIGDIR=/tmp/paper-mpl python tools/fig_teaser.py
MPLCONFIGDIR=/tmp/paper-mpl python tools/style_main_figures.py
MPLCONFIGDIR=/tmp/paper-mpl python tools/fig_mechanism_results.py
python tools/export_figure_bundle.py
python tools/compile_figure_bundle.py
```

图表包中可用`source/tools/fig_teaser.py`、`style_main_figures.py`、`fig_mechanism_results.py`从已审计汇总重画；输出至`source/figures/`。需要Matplotlib、NumPy与Linux Libertine字体。原始权重、推理输出与远端运行不属于绘图依赖。
