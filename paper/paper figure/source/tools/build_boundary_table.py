#!/usr/bin/env python3
"""Render only the active common-item boundary table, retaining intervals."""
import json
from _paths import VALUES, TABLES

data=json.loads((VALUES/'depth-crossmodel-values.json').read_text())
lines=[r'\begin{tabular}{@{}llrccc@{}}',r'\toprule',r'\rowcolor{TableHeader}',
       r'\textbf{Task} & \textbf{Model} & $n$ & $T/R$ & $\Delta$ & $95\%$ CI \\',r'\midrule']
for task in ['MedCalc','TheoremQA']:
    if task=='TheoremQA':lines.append(r'\midrule')
    for model in ['Qwen3-8B','Qwen3-0.6B','Mistral-7B']:
        cell=next(c['common'] for c in data if c['task']==task and c['model']==model)
        t,r=cell['transfer_boundary'],cell['reading_boundary']
        lo,hi=cell['boundary_ci'][2]
        lines.append(f'{task} & {model} & ${cell["n"]}$ & ${t}/{r}$ & '
                     f'\\cellcolor{{ConflictHighlight}}${r-t}$ & $[{lo:.1f},{hi:.1f}]$ '+r'\\')
lines += [r'\bottomrule',r'\end{tabular}']
(TABLES/'tab-paired-depth.tex').write_text('\n'.join(lines)+'\n')
print('Rendered six common-item boundaries and their existing bootstrap intervals.')
