"""Retrieve only binary outcomes after checking the independently audited hashes."""
import json
from pathlib import Path
import shlex
import subprocess

HERE=Path(__file__).resolve().parent
audit=json.loads((HERE/'retrieved/independent-audit.json').read_text())
expected={k:v['raw_sha256'] for k,v in audit['files'].items() if k.startswith('repair')}
code='''import json,gzip,hashlib,collections
from pathlib import Path
r=Path('/inspire/ssd/project/project-public/czxs253130660/state-completeness-20261022-v2/outputs')
expected=EXPECTED
groups={};conditions={};seen=set()
for label,sha in expected.items():
 p=r/(label+'.jsonl.gz');assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
 with gzip.open(p,'rt') as f:
  for line in f:
   x=json.loads(line);i=x['instance_id'];k=x['arm']+'@'+str(x['layer'])
   assert (i,k) not in seen;seen.add((i,k));groups[i]=x['group']
   d=conditions.setdefault(k,{'ids':[],'correct_ids':[],'truncated_ids':[]})
   d['ids'].append(i)
   if x['correct']:d['correct_ids'].append(i)
   if x['truncated']:d['truncated_ids'].append(i)
assert len(seen)==6076 and len(groups)==124 and len(conditions)==49
assert all(len(x['ids'])==124 for x in conditions.values())
print(json.dumps({'groups':groups,'conditions':conditions,'raw_sha256':expected}))
'''.replace('EXPECTED',repr(expected))
command=['ssh','-F','/tmp/state-observer-audit.ssh','-o','BatchMode=yes','-o','ConnectTimeout=20',
         'state-observer-audit','python -c '+shlex.quote(code)]
r=subprocess.run(command,capture_output=True,text=True,timeout=120)
if r.returncode:raise RuntimeError(r.stderr[-1500:])
data=json.loads(r.stdout)
(HERE/'retrieved/binary-outcomes.json').write_text(json.dumps(data,indent=2)+'\n')
print('Retrieved binary labels for',len(data['groups']),'items; no answer text downloaded.')
