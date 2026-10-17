#!/usr/bin/env python3
"""One fixed item shard, with own-state controls before repair and edge cuts."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True)
    p.add_argument('--shard',type=int,required=True)
    a=p.parse_args()
    root=Path(a.root); out=root/'parallel'; out.mkdir(exist_ok=True)
    shard=a.shard
    if shard not in range(4): raise ValueError('Expected one of four fixed shards')
    python='/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python'
    common=[python,'-u',str(root/'run.py'),'--repo',str(root/'repo'),
            '--model','/inspire/ssd/project/project-public/czxs253130660/models/Qwen3-8B',
            '--ids',str(root/'ids-repair124.json'),'--shards','4','--shard',str(shard),
            '--backend','eager','--max-new','1536']
    with (out/f'worker-{shard}.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            for name,suite,layers,extra in [
                ('identity','bridge','8,12,16,24',['--limit','1']),
                ('repair','repair','8,12,16,24',[]),
                ('edges','edges','8,16,24',['--phases','both'])]:
                dest=out/f'{name}-s4-{shard}.jsonl'
                cmd=common+['--suite',suite,'--layers',layers,'--out',str(dest)]+extra
                (out/f'worker-{shard}.status.json').write_text(json.dumps(dict(
                    stage=name,shard=shard,command=cmd,time=time.time()),indent=2)+'\n')
                with dest.with_suffix('.log').open('a') as log:
                    r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
                if r.returncode or not dest.with_suffix('.done.json').exists():
                    raise RuntimeError(f'{name} shard {shard} failed: {r.returncode}')
            (out/f'worker-{shard}.done.json').write_text(json.dumps(dict(time=time.time()))+'\n')
        except Exception as exc:
            (out/f'worker-{shard}.failed.json').write_text(json.dumps(dict(error=str(exc),time=time.time()))+'\n')
            raise


if __name__=='__main__':main()
