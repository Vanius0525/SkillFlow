#!/usr/bin/env python3
"""Stage reachable submission files under the linked Overleaf folder."""
import argparse
from pathlib import Path
import shutil
from make_overleaf_zip import project_members
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
paper=Path(__file__).resolve().parents[1]
a.directory.mkdir(parents=True,exist_ok=False)
target=a.directory/'overleaf-skillvector';target.mkdir()
for source in project_members(paper):
    dest=target/source.relative_to(paper);dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)
print(a.directory.resolve())
print('Run full olcli diff before editing and again immediately before push; preserve remote-only files.')
