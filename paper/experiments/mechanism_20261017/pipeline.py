#!/usr/bin/env python3
"""Predeclared bounded sequence. Failed controls stop the entire pipeline."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PYTHON = '/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python'
MODEL = '/inspire/ssd/project/project-public/czxs253130660/models/Qwen3-8B'


def main():
    # OS lock prevents simultaneous pipelines from even loading a second model.
    import fcntl
    with (ROOT/'pipeline.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stages = [('bridge2-eager', 'bridge', 'eager', 'ids-bridge14.json', '8,16', 2),
                  ('bridge2-sdpa', 'bridge', 'sdpa', 'ids-bridge14.json', '8,16', 2),
                  ('bridge14-eager', 'bridge', 'eager', 'ids-bridge14.json', '8,16', 0),
                  ('repair124-eager', 'repair', 'eager', 'ids-repair124.json', '8,12,16,24', 0)]
        for name, suite, backend, ids, layers, limit in stages:
            out = ROOT/(name+'.jsonl')
            command = [PYTHON, '-u', str(ROOT/'run.py'), '--repo', str(ROOT/'repo'),
                       '--model', MODEL, '--ids', str(ROOT/ids), '--out', str(out),
                       '--suite', suite, '--backend', backend, '--layers', layers,
                       '--max-new', '1536', '--limit', str(limit)]
            (ROOT/'pipeline-status.json').write_text(json.dumps(dict(
                stage=name, command=command, started_at=time.time()), indent=2)+'\n')
            print('STAGE_START', name, datetime.datetime.now().isoformat(), flush=True)
            with (ROOT/(name+'.log')).open('a') as fh:
                result = subprocess.run(command, stdout=fh, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{name} failed with exit code {result.returncode}; inspect stage log')
            if not out.with_suffix('.done.json').exists():
                raise RuntimeError(f'{name} missing completion marker')
            if name == 'bridge14-eager':
                rows = [json.loads(x) for x in out.read_text().splitlines()]
                keyed = {(r['instance_id'],r['arm'],r['layer']):r for r in rows}
                eligible = [i for i in json.loads((ROOT/ids).read_text())['ids']
                            if keyed[i,'donor',-1]['correct'] and not keyed[i,'receiver',-1]['correct']]
                positive = sum(keyed[i,'S_split',8]['correct'] for i in eligible)
                control = dict(eligible=len(eligible), early_positive=positive,
                               rule='Identity controls must pass and at least one baseline-valid early S_split control must repair.')
                (ROOT/'bridge-gate.json').write_text(json.dumps(control,indent=2)+'\n')
                if not eligible or not positive:
                    raise RuntimeError('Early positive control absent; formal repair not launched')
            print('STAGE_DONE', name, flush=True)
        (ROOT/'pipeline.done.json').write_text(json.dumps(dict(finished_at=time.time()))+'\n')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        (ROOT/'pipeline.failed.json').write_text(json.dumps(dict(error=str(exc),time=time.time()))+'\n')
        raise
