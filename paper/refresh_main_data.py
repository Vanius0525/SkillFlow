#!/usr/bin/env python3
"""Regenerate and audit the main displays; no model runs or network access."""
from pathlib import Path
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
env = dict(os.environ, MPLCONFIGDIR='/tmp/skillvector-mpl')
scripts = ['main_evidence.py', 'replication.py', 'replication_full.py',
           'fig_channels_full.py', 'fig_rank_full.py', 'fig_posbudget.py',
           'check_main_data.py',
           '../whitebox/analysis/audit.py']
logs = []
for script in scripts:
    result = subprocess.run([sys.executable, str(HERE/script)], cwd=HERE,
                            env=env, text=True, capture_output=True)
    logs.append(f'=== {script} (exit {result.returncode}) ===\n{result.stdout}{result.stderr}')
    (HERE/'DATA-AUDIT-20260918.txt').write_text('\n'.join(logs))
    print(script, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
    if result.returncode:
        print(result.stdout, result.stderr)
        raise SystemExit(result.returncode)
