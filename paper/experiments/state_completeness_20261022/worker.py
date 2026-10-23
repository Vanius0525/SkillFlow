"""One bounded GPU worker: gate must succeed before any formal inference."""
import argparse
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
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('gate', 'depth', 'repair'), required=True)
    p.add_argument('--shard', type=int, default=0)
    p.add_argument('--shards', type=int, default=1)
    a = p.parse_args()
    out = ROOT/'outputs'
    out.mkdir(exist_ok=True)
    label = f'{a.mode}-{a.shard}-of-{a.shards}'
    try:
        if a.mode != 'gate':
            gate = out/'gate-0-of-1.done.json'
            data = json.loads(gate.read_text())
            raw = gate.with_name('gate-0-of-1.jsonl.gz')
            assert data['records'] == 14
            assert hashlib.sha256(raw.read_bytes()).hexdigest() == data['raw_sha256']
        subprocess.run(['nvidia-smi', '--query-gpu=name,uuid,driver_version,memory.total',
                        '--format=csv'], check=True)
        cmd = [PYTHON, '-u', str(ROOT/'run.py'), '--model', MODEL, '--mode', a.mode,
               '--out', str(out/f'{label}.jsonl.gz'), '--shard', str(a.shard),
               '--shards', str(a.shards)]
        subprocess.run(cmd, check=True)
        print('WORKER_COMPLETE', label, flush=True)
    except BaseException as exc:
        (out/f'{label}.failed.json').write_text(json.dumps({'error':str(exc), 'time':time.time()})+'\n')
        raise


if __name__ == '__main__':
    main()
