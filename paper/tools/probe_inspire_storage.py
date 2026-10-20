"""Bounded storage probe; preserves every created file for explicit cleanup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
p.add_argument('--role', required=True)
p.add_argument('--mib', type=int, default=32)
a = p.parse_args()
if not 1 <= a.mib <= 128 or not a.run.replace('-', '').isalnum():
    p.error('bounded size and simple run name required')
r = {'host': socket.gethostname(), 'role': a.role, 'time': time.time(), 'tiers': {}}
for tier in ('ssd', 'hdd'):
    root = Path(f'/inspire/{tier}/project/project-public/czxs253130660')
    d = root / 'storage-checks' / a.run
    row = {'root': str(root)}
    r['tiers'][tier] = row
    try:
        row['df'] = subprocess.check_output(['df', '-h', str(root)], text=True)
        row['mount'] = [x.strip() for x in Path('/proc/mounts').read_text().splitlines()
                        if str(root) in x]
        d.mkdir(parents=True, exist_ok=True)
        row['existing'] = sorted(x.name for x in d.iterdir())
        for marker in sorted(d.glob('*.marker')):
            row.setdefault('markers', {})[marker.name] = marker.read_text()
        data = hashlib.sha256((a.run + a.role).encode()).digest() * 32768
        fpath = d / f'{a.role}.bin'
        digest = hashlib.sha256()
        start = time.monotonic()
        with fpath.open('xb') as f:
            for _ in range(a.mib):
                f.write(data)
                digest.update(data)
            f.flush()
            os.fsync(f.fileno())
        row['write_seconds'] = time.monotonic() - start
        row['written_bytes'] = fpath.stat().st_size
        with fpath.open('rb') as f:
            actual = hashlib.file_digest(f, 'sha256').hexdigest()
        row['sha256'] = actual
        row['readback_ok'] = actual == digest.hexdigest()
        for i in range(16):
            with (d / f'{a.role}-{i:02}.marker').open('x') as f:
                f.write(f'{a.run}:{a.role}:{i}\n')
                f.flush()
                os.fsync(f.fileno())
        row['small_files_ok'] = 16
        row['ok'] = row['readback_ok']
    except OSError as e:
        row.update(ok=False, errno=e.errno, error=str(e))
print(json.dumps(r, ensure_ascii=False, indent=2))
