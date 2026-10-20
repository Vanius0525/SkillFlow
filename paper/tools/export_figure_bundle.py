#!/usr/bin/env python3
"""Refresh a self-contained figure/table workspace from active manuscript inputs."""
import hashlib
import json
from pathlib import Path
import re
import shutil

PAPER=Path(__file__).resolve().parents[1]
BUNDLE=PAPER/'paper figure'


def main():
    for folder in ['figures','latex','tables','source/tools','source/values','source/figures','source/audit']:
        (BUNDLE/folder).mkdir(parents=True,exist_ok=True)
    (BUNDLE/'source/audit/README.md').write_text('Plot reproduction writes input hashes here.\n')
    labels={'fig:teaser':('figure1','sections/01-introduction.tex'),
            'fig:design':('figure2','sections/03-problem-formulation.tex'),
            'fig:transferreading':('figure3','sections/04-experiment.tex'),
            'fig:mechanism':('figure4','sections/04-experiment.tex'),
            'tab:probe':('table1','sections/04-experiment.tex'),
            'tab:paireddepth':('table2','sections/04-experiment.tex'),
            'tab:mechanism-contrasts':('table3','sections/04-experiment.tex'),
            'tab:fullscale':('tableA1','tables/tab-fullscale-float.tex'),
            'tab:repair-extension':('tableA2','appendix/a-setup.tex'),
            'tab:extension-populations':('tableA3','appendix/a-setup.tex')}
    for label,(name,source) in labels.items():
        matches=re.findall(r'(\\begin\{(figure\*?|table\*?)\}.*?\\end\{\2\})',
                           (PAPER/source).read_text(),re.S)
        block=next(block for block,_ in matches if r'\label{'+label+'}' in block)
        (BUNDLE/'latex'/f'{name}.tex').write_text(block+'\n')
    stems=['fig-teaser','fig-intervention-design','fig-transfer-reading','fig-mechanism-results']
    for stem in stems:
        for ext in ['pdf','png','svg']:
            shutil.copy2(PAPER/'figures'/f'{stem}.{ext}',BUNDLE/'figures'/f'{stem}.{ext}')
    for name in ['tab-paired-depth.tex','tab-control-matrix.tex','tab-mechanism-contrasts.tex','tab-additional-controls.tex','tab-repair-extension.tex','tab-extension-populations.tex']:
        shutil.copy2(PAPER/'tables'/name,BUNDLE/'tables'/name)
    for name in ['_paths.py','figure_fonts.py','style_main_figures.py','fig_teaser.py','fig_intervention_design.py','fig_mechanism_results.py','build_boundary_table.py']:
        shutil.copy2(PAPER/'tools'/name,BUNDLE/'source/tools'/name)
    for name in ['depth-current-values.json','eight-cell-display-values.json','repair-extension-values.json','fig-channels-values.json']:
        shutil.copy2(PAPER/'values'/name,BUNDLE/'source/values'/name)
    for name in ['fig-mechanism-repair.json','fig-mechanism-edges.json']:
        shutil.copy2(PAPER/'figures'/name,BUNDLE/'source/figures'/name)
    style=r'''\usepackage{etoolbox}
\AtBeginEnvironment{tabular}{\normalfont\rmfamily\fontsize{9}{11}\selectfont\renewcommand{\arraystretch}{1.22}}
\definecolor{TableInk}{HTML}{284A63}
\definecolor{TableHeader}{HTML}{FFFFFF}
\definecolor{TransferHighlight}{HTML}{FFFFFF}
\definecolor{ConflictHighlight}{HTML}{FFFFFF}
\definecolor{TableStripe}{HTML}{FFFFFF}
'''
    (BUNDLE/'latex/style.tex').write_text(style)
    project=r'''\PassOptionsToPackage{table}{xcolor}
\documentclass[sigconf,anonymous,review]{acmart}
\setcopyright{none}
\acmDOI{}
\acmISBN{}
\settopmatter{printacmref=false}
\usepackage{amsmath}
\input{latex/style}
\graphicspath{{figures/}}
\begin{document}
\title{Current Figure and Table Reference}
\author{Anonymous Author(s)}
\maketitle
This file collects the current manuscript displays. Recovery is defined as
\begin{equation}
\rho=\frac{\mathrm{acc}(\mathrm{patch})-\mathrm{acc}(\mathrm{receiver})}
{\mathrm{acc}(\mathrm{donor})-\mathrm{acc}(\mathrm{receiver})}.
\label{eq:rho}
\end{equation}
Source-attention dependence is $d(L)=1-q(L)$, the fraction of originally
correct answers lost under cumulative source-attention knockout.
'''
    for name in ['figure1','figure2','figure3','figure4','table1','table2','table3','tableA1','tableA2','tableA3']:
        project+=f'\\input{{latex/{name}}}\n\\clearpage\n'
    project+='\\end{document}\n'
    (BUNDLE/'figures.tex').write_text(project)
    readme='''# 当前图表：4个主模型 × 2个benchmark

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
'''
    (BUNDLE/'README.md').write_text(readme)
    handoff=PAPER/'HANDOFF-NEXT-CONVERSATION.md'
    if handoff.exists():shutil.copy2(handoff,BUNDLE/handoff.name)
    manifest={str(p.relative_to(BUNDLE)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(BUNDLE.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Figure bundle refreshed: {len(manifest)} files, {sum(p.stat().st_size for p in BUNDLE.rglob("*") if p.is_file()):,} bytes')


if __name__=='__main__':main()
