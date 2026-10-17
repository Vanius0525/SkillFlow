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
            'tab:fullscale':('tableA1','tables/tab-fullscale-float.tex')}
    for label,(name,source) in labels.items():
        matches=re.findall(r'(\\begin\{(figure\*?|table\*?)\}.*?\\end\{\2\})',
                           (PAPER/source).read_text(),re.S)
        block=next(block for block,_ in matches if r'\label{'+label+'}' in block)
        (BUNDLE/'latex'/f'{name}.tex').write_text(block+'\n')
    stems=['fig-teaser','fig-intervention-design','fig-transfer-reading','fig-mechanism-results']
    for stem in stems:
        for ext in ['pdf','png','svg']:
            shutil.copy2(PAPER/'figures'/f'{stem}.{ext}',BUNDLE/'figures'/f'{stem}.{ext}')
    shutil.copy2(PAPER/'tables/tab-paired-depth.tex',BUNDLE/'tables/tab-paired-depth.tex')
    for name in ['_paths.py','style_main_figures.py','fig_teaser.py','fig_intervention_design.py','fig_mechanism_results.py','build_boundary_table.py']:
        shutil.copy2(PAPER/'tools'/name,BUNDLE/'source/tools'/name)
    for name in ['depth-crossmodel-values.json','fig-channels-values.json']:
        shutil.copy2(PAPER/'values'/name,BUNDLE/'source/values'/name)
    for name in ['fig-mechanism-repair.json','fig-mechanism-edges.json']:
        shutil.copy2(PAPER/'figures'/name,BUNDLE/'source/figures'/name)
    style=r'''\definecolor{TableInk}{HTML}{284A63}
\definecolor{TableHeader}{HTML}{EAF0F6}
\definecolor{TransferHighlight}{HTML}{E4F1ED}
\definecolor{ConflictHighlight}{HTML}{FFF0DD}
\definecolor{TableStripe}{HTML}{F5F8FA}
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
'''
    for name in ['figure1','figure2','figure3','figure4','table1','table2','table3','tableA1']:
        project+=f'\\input{{latex/{name}}}\n\\clearpage\n'
    project+='\\end{document}\n'
    (BUNDLE/'figures.tex').write_text(project)
    readme='''# 最新版 paper figure

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
| Figure 3 | 展示分离现象及其范围 | 3模型×2任务，每层实测；蓝为残差迁移恢复rho，橙为屏蔽后保留比例q，虚线是共同样本。浅色区为首次半效应边界之间的区间，存在重新越阈，不能称为严格单调阶段。 |
| Figure 4 | 展示恢复和继续读取的机制证据 | 114题/14skill，S、C、SC及SC后recut准确率；右侧比较reader-to-source与source-to-source切断造成的准确率损失。L16恢复明显且recut损害；L24无同样额外recut损失。 |

Figure 1的source dependence=1-q，Figure 3画的是q本身，两者方向相反，轴标签和说明已分别标明。
KV表示attention的key/value缓存，保存已处理token的注意力向量；reader指skill span以外的question/answer token。联合替换没有重放或修复全部接收方计算历史。

## 表格说明

- Table 1：验证早期探针，正确内容、位置排列与噪声对照；末位置替换与整段替换容量不同。
- Table 2：共同样本的边界T/R、差值Delta及按skill分组bootstrap的95%置信区间。区间端点由分位数计算，可以不是整数。
- Table 3：114题机制对比的准确率差，单位为百分点，含已有95%区间；避免将恢复图的原始单元格再列一遍。
- 附录表：全样本与开发子样本、不同筛选规则的对照。

## 重新生成

需要Python、NumPy、Matplotlib。命令在本目录运行：

```bash
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/fig_teaser.py
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/fig_intervention_design.py
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/style_main_figures.py
MPLCONFIGDIR=/tmp/paper-mpl python3 source/tools/fig_mechanism_results.py
```

快照脚本输出至`source/figures/`，不覆盖本目录已交付的`figures/`。
从完整仓库刷新本目录：`python3 tools/export_figure_bundle.py`。
数据均来自既有完成实验；本轮不新增推理。详细核验见仓库audit/FOUR-FIGURE-STORY-20261017.json。
'''
    (BUNDLE/'README.md').write_text(readme)
    handoff=PAPER/'HANDOFF-NEXT-CONVERSATION.md'
    if handoff.exists():shutil.copy2(handoff,BUNDLE/handoff.name)
    manifest={str(p.relative_to(BUNDLE)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(BUNDLE.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Figure bundle refreshed: {len(manifest)} files, {sum(p.stat().st_size for p in BUNDLE.rglob("*") if p.is_file()):,} bytes')


if __name__=='__main__':main()
