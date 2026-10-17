#!/usr/bin/env python3
"""Preserve the live bridge, then join four independent GPU item shards."""
import fcntl
import json
from pathlib import Path
import subprocess
import time


def main():
    root=Path(__file__).resolve().parent
    parallel=root/'parallel'; parallel.mkdir(exist_ok=True)
    started=time.monotonic()
    with (root/'parallel-orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # The original bridge child survives the superseded serial parent.
        while not (root/'bridge14-eager.done.json').exists():
            if time.monotonic()-started>3*3600:
                raise RuntimeError('Bridge did not complete within three hours')
            time.sleep(15)
        rows=[json.loads(x) for x in (root/'bridge14-eager.jsonl').read_text().splitlines()]
        keyed={(r['instance_id'],r['arm'],r['layer']):r for r in rows}
        ids=json.loads((root/'ids-bridge14.json').read_text())['ids']
        if len(rows)!=210 or len(keyed)!=210:
            raise RuntimeError('Bridge coverage mismatch')
        for r in rows:
            if r['arm'].startswith('identity_'):
                baseline='receiver_full' if r['arm'].endswith('_full') else 'receiver'
                if r['token_ids']!=keyed[r['instance_id'],baseline,-1]['token_ids']:
                    raise RuntimeError('Bridge identity failed')
        valid=[i for i in ids if keyed[i,'donor',-1]['correct'] and not keyed[i,'receiver',-1]['correct']]
        positive=sum(keyed[i,'S_split',8]['correct'] for i in valid)
        (root/'bridge-gate.json').write_text(json.dumps(dict(eligible=len(valid),early_positive=positive))+'\n')
        if not positive: raise RuntimeError('Early positive control absent')
        python='/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python'
        with (parallel/'worker-0.log').open('a') as log:
            child=subprocess.Popen([python,'-u',str(root/'worker.py'),'--root',str(root),'--shard','0'],
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        (parallel/'worker-0.pid').write_text(str(child.pid)+'\n')
        (root/'pipeline-status.json').write_text(json.dumps(dict(stage='parallel-repair-and-edges',
            shards=4,started_at=time.time(),output=str(parallel)),indent=2)+'\n')
        while time.monotonic()-started<20*3600:
            failed=list(parallel.glob('worker-*.failed.json'))
            if failed: raise RuntimeError('Worker failed: '+str(failed))
            if all((parallel/f'worker-{s}.done.json').exists() for s in range(4)):
                (root/'pipeline.done.json').write_text(json.dumps(dict(finished_at=time.time(),
                    protocol='four item shards; repair then phase-both edge controls'))+'\n')
                return
            time.sleep(60)
        raise RuntimeError('Parallel pipeline exceeded its twenty-hour bound')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        Path(__file__).with_name('pipeline.failed.json').write_text(json.dumps(dict(error=str(exc),time=time.time()))+'\n')
        raise
