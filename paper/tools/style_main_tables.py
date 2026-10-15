#!/usr/bin/env python3
"""Typeset the two main evidence tables from audited numerical records."""
import json
from _paths import TABLES, VALUES

battery=json.loads((VALUES/'battery-values.json').read_text())['arms']
rows=[(r'\emph{correct skill in context}','gold_in_context'),
      (r'$h_{\text{recv}}+\dvec$ \ (full span)','real_L8'),
      ('correct content, shared prefix','realm_L8'),
      (r'half dose ($\alpha=0.5$)','a0.5_L8'),
      ('another skill (individual donor)','dcross_L8'),
      ('mean from another skill family','dfar_L8'),
      ('mean from the same skill family','dnear_L8'),
      ('positions permuted','dshuf_L8'),
      ('norm-matched Gaussian noise','drand_L8'),
      (r'\emph{identity intervention}','self_L8'),
      (r'\emph{wrong skill, unpatched}','receiver')]
out=[r'\begin{tabular}{@{}lrccc@{}}',r'\toprule',
     r'\textbf{Intervention} & $n$ & \textbf{Accuracy} & \textbf{95\% CI} & \textbf{Recovery} $\rho$ \\',r'\midrule']
for label,key in rows:
    v=battery[key];lo,hi=v['ci']
    if key in ('real_L8','a0.5_L8','self_L8'):out.append(r'\addlinespace[3pt]')
    out.append(f'{label} & ${v["n"]}$ & ${v["accuracy"]:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & ${v["rho"]:+.2f}$ '+r'\\')
out += [r'\bottomrule',r'\end{tabular}']
(TABLES/'tab-big40.tex').write_text('\n'.join(out)+'\n')

cells=json.loads((VALUES/'replication-values.json').read_text())
out=[r'\begin{tabular}{@{}llrccccc@{}}',r'\toprule',
     r'\textbf{Task} & \textbf{Model} & $n_T/n_R$ (groups) & $\rho$ [95\% CI] & \textbf{Control} & \textbf{Transfer} & \textbf{Reading} & $k^{*}$ \\',r'\midrule']
for i,c in enumerate(cells):
    if i and cells[i-1]['model']!=c['model']:out.append(r'\addlinespace[3pt]')
    ho,rd=c['handover'],c['reading']
    out.append(f'{c["task"]} & {c["model"]} & ${c["n"]}/{rd[1]}$ (${c["g"]}$) & '
               f'${c["rho"]:.2f}$ $[{c["lo"]:.2f},{c["hi"]:.2f}]$ & ${c["ctrl"]:.2f}$ & '
               f'${ho[0]:.2f}$--${ho[1]:.2f}$ & ${rd[0]:.2f}$ & ${c["kstar"]:.0f}$ '+r'\\')
out += [r'\bottomrule',r'\end{tabular}']
(TABLES/'tab-replication.tex').write_text('\n'.join(out)+'\n')
print('Typeset evidence tables with intervention groups and explicit transfer/reading sample sizes.')
