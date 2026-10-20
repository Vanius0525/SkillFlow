#!/usr/bin/env python3
"""Four-family main matrix; Qwen0.6 is reported as a supplementary scale check."""
import json
from _paths import VALUES, TABLES

data=json.loads((VALUES/'depth-current-values.json').read_text())
lookup={(c['model'],c['task']):c for c in data}
lines=[r'\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lrrrrrrrrrr@{}}',r'\toprule',
 r'Model & \multicolumn{5}{c}{MedCalc-Bench} & \multicolumn{5}{c}{TheoremQA} \\',
 r'\cmidrule(lr){2-6}\cmidrule(l){7-11}',
 r' & $n/G$ & $T$ & $R$ & $\Delta$ & $\Delta/D$ (\%) & $n/G$ & $T$ & $R$ & $\Delta$ & $\Delta/D$ (\%) \\',r'\midrule']
for model,name,depth in [('Qwen3-8B','Qwen3-8B',36),('Mistral-7B','Mistral-7B',32),('Llama-3.1-8B','Llama-3.1-8B',32),('DeepSeek-LLM-7B','DeepSeek-7B',30)]:
 cells=[]
 for task in ['MedCalc','TheoremQA']:
  c=lookup.get((model,task))
  assert c is not None, (model,task)
  v=c['common'];t,r=v['transfer_boundary'],v['reading_boundary'];g=v['groups']
  cells.append(f'${v["n"]}/{g}$ & ${t}$ & ${r}$ & ${r-t}$ & ${100*(r-t)/depth:.1f}$')
 lines.append(name+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular*}']
(TABLES/'tab-paired-depth.tex').write_text('\n'.join(lines)+'\n')
print('Rendered all eight audited main model--benchmark cells.')
