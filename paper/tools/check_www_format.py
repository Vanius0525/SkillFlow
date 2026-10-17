#!/usr/bin/env python3
"""Check the local review manuscript against WWW 2027's published format limits."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import pymupdf
PAPER=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--aux',required=True)
    parser.add_argument('--log',required=True)
    parser.add_argument('--pdf',default=str(PAPER/'skillvector-www2027.pdf'))
    a=parser.parse_args()
    main=(PAPER/'main.tex').read_text()
    source=re.sub(r'(?<!\\)%[^\n]*','',main)
    assert r'\documentclass[sigconf, anonymous, review]{acmart}' in source
    assert '\\extendedappendixtrue' not in source and '\\input{appendix/c-' not in source
    assert not re.search(r'\\(?:usepackage(?:\[[^\]]*\])?\{geometry\}|setlength\{\\(?:textwidth|textheight|oddsidemargin|evensidemargin)\})',source)
    assert r'\setcopyright{none}' in source and r'\acmDOI{}' in source and r'\acmISBN{}' in source
    assert 'AI Use Statement' not in source
    aux=Path(a.aux).read_text(errors='replace')
    log=Path(a.log).read_text(errors='replace')
    end=re.search(r'newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}',aux)
    assert end is not None
    main_pages=int(end.group(1));assert main_pages<=8
    p=pymupdf.open(a.pdf);assert len(p)<=12
    first=p[0].get_text();assert 'Web agents' in first and 'skill' in first.lower()
    assert 'Anonymous Author(s)' in first
    text='\n'.join(page.get_text() for page in p)
    assert 'XXXXXXX' not in text and 'RESULTS PENDING' not in text and 'AI Use Statement' not in text
    captions={}
    for j,page in enumerate(p):
        for n in re.findall(r'Figure ([1-4]):',page.get_text()):captions[int(n)]=j+1
    assert set(captions)=={1,2,3,4} and max(captions.values())<=main_pages
    assert 'Relevance to the Web and to this track.' in first
    fonts={f[0]:f for page in p for f in page.get_fonts()}
    assert all(p.extract_font(x)[3] for x in fonts),'Unembedded font'
    assert not re.search(r'^! |LaTeX Warning: (Reference|Citation).*undefined',log,re.M)
    assert 'Overfull \\hbox' not in log
    vbox_points=[float(x) for x in re.findall(r'Overfull \\vbox \(([0-9.]+)pt',log)]
    assert all(x<=2.1 for x in vbox_points), 'Inspect substantive vertical overflow'
    report=dict(official_source='https://www2027.thewebconf.org/research-track-papers/',
                rules=dict(main_max_pages=8,references_excluded_from_main_limit=True,
                           references_and_appendix_included_in_total=True,total_max_pages=12,
                           first_eight_pages_self_contained=True,
                           documentclass='sigconf, anonymous, review; acmart'),
                pdf=str(a.pdf),pdf_sha256=hashlib.sha256(Path(a.pdf).read_bytes()).hexdigest(),
                main_pages=main_pages,total_pages=len(p),main_figure_pages=captions,
                first_page_web_relevance=True,anonymous_review=True,
                unassigned_publication_identifiers_omitted=True,all_fonts_embedded=True,
                standard_page_sizes=sorted({(page.rect.width,page.rect.height) for page in p}),
                errors=0,undefined_references=0,overfull_hbox=0,overfull_vbox=len(vbox_points),
                minor_last_page_balance_warning_points=vbox_points,
                scope='Checks format and visible first-page relevance, not scientific track acceptance or submission-system requirements.')
    (PAPER/'audit/WWW2027-FORMAT-20261017.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: WWW review format; main {main_pages}/8, total {len(p)}/12; figures {captions}; all fonts embedded.')

if __name__=='__main__':main()
