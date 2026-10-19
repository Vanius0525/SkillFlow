#!/usr/bin/env python3
"""Compile the exact upload ZIP, then export a clean, non-overwriting review."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
import pymupdf

PAPER=Path(__file__).resolve().parents[1]
BIN=Path('/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--destination',required=True)
    p.add_argument('--final',action='store_true',help='Require measured mechanism results with no draft placeholders')
    p.add_argument('--note',default='reports/桌面版本阅读说明_20261017.md')
    p.add_argument('--audit-output',default=None)
    a=p.parse_args()
    destination=Path(a.destination)
    if destination.exists():raise FileExistsError('Choose a fresh export; existing review is preserved')
    archive=PAPER/'overleaf-skillvector.zip'
    stage=Path(tempfile.mkdtemp(prefix='build-overleaf.',dir='/mnt/c/Users/12970/Desktop/WWW2027'))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC failure')
        names=z.namelist()
        for n in names:
            if Path(n).is_absolute() or '..' in Path(n).parts:
                raise ValueError('Unsafe ZIP path')
            if Path(n).suffix not in ('.tex','.bib','.pdf','.md'):
                raise ValueError('Unexpected upload artifact: '+n)
        if 'main.tex' not in names:raise ValueError('main.tex missing from ZIP root')
        z.extractall(stage)
    commands=[('pdflatex.exe',['-interaction=nonstopmode','-halt-on-error','main.tex']),
              ('bibtex.exe',['main']),
              ('pdflatex.exe',['-interaction=nonstopmode','-halt-on-error','main.tex']),
              ('bibtex.exe',['main']),
              ('pdflatex.exe',['-interaction=nonstopmode','-halt-on-error','main.tex']),
              ('pdflatex.exe',['-interaction=nonstopmode','-halt-on-error','main.tex'])]
    for j,(name,args) in enumerate(commands):
        with (stage/f'compile-{j}.txt').open('w') as log:
            r=subprocess.run([str(BIN/name),*args],cwd=stage,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if r.returncode:raise RuntimeError(f'{name} failed; inspect {stage}')
    log=(stage/'main.log').read_text(errors='replace')
    if re.search(r'^! |LaTeX Warning: (Reference|Citation).*undefined',log,re.M):
        raise ValueError('Compile errors or unresolved references in packaged project')
    pdf=pymupdf.open(stage/'main.pdf')
    aux=(stage/'main.aux').read_text(errors='replace')
    endmain=re.search(r'newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}',aux)
    text='\n'.join(page.get_text() for page in pdf)
    pending='RESULTS PENDING' in text
    if 'Still Needed, Hard to Transfer' not in text:
        raise ValueError('Packaged PDF does not contain expected title')
    if a.final and (pending or '[Draft:' in text or 'Measurements are pending' in text):
        raise ValueError('Final export still contains pending mechanism results')
    if a.final and 'figures/fig-mechanism-results.pdf' not in names:
        raise ValueError('Final export is missing the measured mechanism figure')
    if endmain is None or int(endmain.group(1))>8 or len(pdf)>12:
        raise ValueError('Review exceeds manuscript page limits')
    mechanism_pages=[j+1 for j,page in enumerate(pdf) if 'Which attention path matters?' in page.get_text()]
    if a.final and (len(mechanism_pages)!=1 or mechanism_pages[0]>int(endmain.group(1))):
        raise ValueError('Main mechanism figure falls outside the main-text boundary')
    if a.final and 'AI Use Statement' in text:
        raise ValueError('Final revision still contains the removed AI Use Statement')
    # Only create the user-facing directory after exact-ZIP compilation passes.
    destination.mkdir(parents=True,exist_ok=False)
    project=destination/'project';project.mkdir()
    with zipfile.ZipFile(archive) as z:z.extractall(project)
    shutil.copy2(archive,destination/'StillNeeded-overleaf.zip')
    shutil.copy2(stage/'main.pdf',destination/'StillNeeded-review.pdf')
    note=(PAPER/a.note).read_text()
    (destination/'阅读说明.md').write_text(note)
    facts=dict(export=str(destination),time=datetime.datetime.now().astimezone().isoformat(),
               title='Still Needed, Hard to Transfer: Using and Reusing Contextual Skills',
               zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
               zip_entries=len(names),main_pages=int(endmain.group(1)),total_pages=len(pdf),
               overfull_hbox=log.count('Overfull \\hbox'),overfull_vbox=log.count('Overfull \\vbox'),
               compile_stage=str(stage),scope='Seven verified depth comparisons across five models/four families; focused Qwen3-8B/MedCalc mechanisms',
               mechanism_results_pending=pending,mechanism_figure_pages=mechanism_pages)
    (PAPER/(a.audit_output or ('audit/DESKTOP-FINAL-20261017.json' if a.final else 'audit/DESKTOP-REVIEW-20261017.json'))).write_text(json.dumps(facts,indent=2)+'\n')
    print(json.dumps(facts,indent=2))


if __name__=='__main__':main()
