#!/usr/bin/env python3
"""Check reachable manuscript citations and record focused primary-source review."""
import collections
import json
from pathlib import Path
import re
from make_overleaf_zip import project_members

PAPER=Path(__file__).resolve().parents[1]

def main():
    texts={str(p.relative_to(PAPER)):re.sub(r'(?<!\\)%[^\n]*','',p.read_text())
           for p in project_members(PAPER) if p.suffix=='.tex'}
    bib=(PAPER/'skillvector.bib').read_text()
    keys=re.findall(r'@\w+\s*\{\s*([^,]+),',bib)
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate bibliography keys')
    cited={k.strip() for text in texts.values()
           for group in re.findall(r'\\cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}',text)
           for k in group.split(',')}
    if cited-set(keys):raise ValueError('Missing citations: '+str(cited-set(keys)))
    labels=collections.Counter(l for t in texts.values() for l in re.findall(r'\\label\{([^}]+)\}',t))
    if any(n>1 for n in labels.values()):raise ValueError('Duplicate labels')
    for name,t in texts.items():
        for env in ['figure','figure*','table','table*','tabular']:
            if t.count('\\begin{'+env+'}')!=t.count('\\end{'+env+'}'):
                raise ValueError(f'Unmatched {env} in {name}')
    if 'AI Use Statement' in texts['main.tex']:raise ValueError('Requested AI statement removal is missing')
    if 'zhang2025agentskills' not in cited:raise ValueError('Agent Skills definition lacks its primary citation')
    report=dict(scope='All reachable citation keys and labels; focused primary-source content/metadata review of seven Web/Agent Skills and closest-neighbor references. Existing references retain prior audits.',
                bib_entries=len(keys),cited_entries=len(cited),tex_files=len(texts),
                missing_citation_keys=[],duplicate_keys=[],duplicate_labels=[],
                ai_use_statement_removed=True,
                primary_sources={
                    'zhang2025agentskills':'https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills',
                    'wang2024awm':'https://proceedings.mlr.press/v267/wang25bx.html',
                    'wang2026webxskill':'https://arxiv.org/abs/2604.13318v2',
                    'tan2025htmlrag':'https://arxiv.org/abs/2411.02959',
                    'yang2025internalcot':'https://aclanthology.org/2025.emnlp-main.1147/',
                    'vaidyanathan2026mediators':'https://arxiv.org/html/2606.27510',
                    'li2026prefillnotes':'https://arxiv.org/html/2606.17107'},
                corrections=['AWM updated to ICML 2025 / PMLR 267:63897–63911.',
                             'Cache-neighbor comparison includes precompiled skill-cache composition.',
                             'Agent Skills definition cites the original Anthropic article, with named authors and 2025 publication date.'])
    (PAPER/'audit/CITATIONS-WEB-REVISION-20261017.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(f'PASS: {len(cited)} cited works; {len(keys)} bibliography entries; {len(texts)} TeX inputs; no missing keys or duplicate labels.')

if __name__=='__main__':main()
