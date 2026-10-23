from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parent
REMOTE='/inspire/ssd/project/project-public/czxs253130660/state-core-matrix-20261024-v1'
PYTHON='/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python'
MODELS='/inspire/ssd/project/project-public/czxs253130660/models'

def conditions():
    arms=[(x,-1) for x in ('donor','wrong','neutral_a','no_skill')]
    for bg in ('wrong','neutral_a'):
        arms += [(bg+':'+action,l) for l in (8,16,24) for action in ('SC','SC_exact')]
        arms += [(bg+':'+action,-1) for action in ('C_all','B_only','full_copy','suffix_replay')]
    assert len(arms)==len(set(arms))==24
    return arms

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
