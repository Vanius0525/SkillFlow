#!/usr/bin/env python3
"""Copy the verified figure workspace and new-conversation handoff to Desktop."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

PAPER=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--destination',required=True)
args=parser.parse_args()
destination=Path(args.destination)
assert (destination/'StillNeeded-overleaf.zip').is_file(),'Export and compile the manuscript first'
bundle=PAPER/'paper figure'
desktop=Path('/mnt/c/Users/12970/Desktop/paper figure')
targets=[destination/'paper figure',desktop]
assert all(not p.exists() for p in targets),'Existing figure export must be inspected before updating'
manifest=json.loads((bundle/'manifest.json').read_text())
assert all(hashlib.sha256((bundle/name).read_bytes()).hexdigest()==digest
           for name,digest in manifest.items())
for target in targets:
    shutil.copytree(bundle,target)
    assert {p.relative_to(target) for p in target.rglob('*') if p.is_file()}=={
        p.relative_to(bundle) for p in bundle.rglob('*') if p.is_file()}
    for name,digest in manifest.items():
        assert hashlib.sha256((target/name).read_bytes()).hexdigest()==digest
shutil.copy2(PAPER/'HANDOFF-NEXT-CONVERSATION.md',destination/'HANDOFF-NEXT-CONVERSATION.md')
report={'desktop_figure_folder':str(desktop),'delivery_figure_folder':str(targets[0]),
        'source':str(bundle),'files':len(manifest)+1,'sha256_manifest':manifest,
        'handoff_sha256':hashlib.sha256((PAPER/'HANDOFF-NEXT-CONVERSATION.md').read_bytes()).hexdigest(),
        'exact_copies_verified':True}
(PAPER/'audit/DESKTOP-FIGURE-BUNDLE-20261018.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: two exact figure-folder copies ({len(manifest)+1} files each) and handoff exported.')
