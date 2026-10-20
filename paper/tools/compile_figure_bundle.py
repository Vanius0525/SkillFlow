#!/usr/bin/env python3
"""Compile the standalone figure/table collection in a fresh Windows stage."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import pymupdf

PAPER=Path(__file__).resolve().parents[1]
BUNDLE=PAPER/'paper figure'
BIN=Path('/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64')
stage=Path(tempfile.mkdtemp(prefix='build-figure-collection.',dir='/mnt/c/Users/12970/Desktop/WWW2027'))
for folder in ['latex','figures','tables']:
    shutil.copytree(BUNDLE/folder,stage/folder)
shutil.copy2(BUNDLE/'figures.tex',stage/'figures.tex')
for i in range(3):
    with (stage/f'compile-{i}.txt').open('w') as output:
        run=subprocess.run([str(BIN/'pdflatex.exe'),'-interaction=nonstopmode','-halt-on-error','figures.tex'],
                           cwd=stage,stdout=output,stderr=subprocess.STDOUT,timeout=180)
    if run.returncode:raise RuntimeError(f'Figure collection compilation failed: {stage}')
log=(stage/'figures.log').read_text(errors='replace')
assert not re.search(r'^! |LaTeX Warning: (Reference|Citation).*undefined',log,re.M)
assert 'Overfull \\hbox' not in log
pdf=pymupdf.open(stage/'figures.pdf')
text='\n'.join(p.get_text() for p in pdf)
for i in range(1,5):assert f'Figure {i}:' in text
for i in range(1,7):assert f'Table {i}:' in text
shutil.copy2(stage/'figures.pdf',BUNDLE/'Figures-and-Tables.pdf')
report={'stage':str(stage),'pages':len(pdf),'figures':4,'tables':6,
        'errors':0,'undefined':0,'overfull_hbox':0}
(PAPER/'audit/FIGURE-COLLECTION-20261020.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
