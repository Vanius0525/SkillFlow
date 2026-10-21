# Figure 4 柱状图备选（2026-10-21）

原始目标：比较多阶段的(b)柱状图，以及当前GitHub Figure4的L24柱状图；图上不显示题数，导出Windows桌面。不更新论文正文或线上Overleaf。

完成：4个方案，各有PNG/PDF/SVG，overview.png为总览。
- 01_github_L24_horizontal：GitHub当前Figure4布局，(a)L16热力图，(b)L24横向分组柱；去除题数/技能数。
- 02_eight_combinations_multilayer_horizontal：八组合，(a)L16热力图，(b)按L8/L16/L24分为三列横向分组柱。
- 03_overleaf_single_case_multilayer_vertical：复现Overleaf单案例数据布局，(a)L8/L12/L16/L24热力图，(b)L8/L16/L24竖向分组柱。
- 04_panel_b_multilayer_small_multiples：仅(b)，八组合2×4小图，每图三层×三路径。

来源：data.json来自本地Git HEAD 5dfb89d的paper/values/eight-cell-display-values.json。generate.py可独立复现，需matplotlib/numpy和tools/figure_fonts.py。图中损失=100×(1-对应路径accuracy)，保留原样本与协议，未新增实验。不同模型同层号不代表相同相对深度。三类路径是独立干预，柱状图不堆叠。

线上核对：已执行olcli完整diff，返回26个文件差异（4 added、17 modified、5 remote-only）；终端输出超长被截断，未声称已逐行审阅全文。本任务只制作离线备选，不上传。另pull当前线上23文件至/tmp/figure4-remote-20261021，直接解析当前Figure4 PDF确认其为Qwen3-8B/MedCalc单案例；逐项数值与本地data.json首行一致。不能据diff判断修改作者。

验证：运行python reports/figure4_bar_variants_20261021/generate.py；检查overview.png四图，无题数/技能数标签；(b)统一百分比零起点。原论文图未覆盖。

## Open Ideas / 值得深挖的问题
无新增独立研究idea；仅可视化已有结果。
