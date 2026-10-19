#!/usr/bin/env python3
"""Render only the active common-item boundary table, using point estimates."""
import json
from _paths import VALUES, TABLES

data=json.loads((VALUES/'depth-verified-extension-20261019.json').read_text())
lines=[r'\begin{tabular}{@{}llrcc@{}}',r'\toprule',
       r'\textbf{Task} & \textbf{Model} & $n$ & $T/R$ & $\Delta$ \\',r'\midrule']
for task in ['MedCalc','TheoremQA']:
    if task=='TheoremQA':lines.append(r'\midrule')
    for c in data:
        if c['task']!=task:continue
        cell=c['common'];t,r=cell['transfer_boundary'],cell['reading_boundary']
        name={'Llama-3.1-8B':'Llama-8B','DeepSeek-LLM-7B':'DeepSeek-7B'}.get(c['model'],c['model'])
        lines.append(f'{task} & {name} & ${cell["n"]}$ & ${t}/{r}$ & ${r-t}$ '+r'\\')
lines += [r'\bottomrule',r'\end{tabular}']
(TABLES/'tab-paired-depth.tex').write_text('\n'.join(lines)+'\n')
print('Rendered seven verified common-item boundaries and separations.')
