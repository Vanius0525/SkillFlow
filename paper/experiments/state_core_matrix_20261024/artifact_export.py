"""Read-only CPU export of small metadata/labels, never answers or model tensors."""
import base64,hashlib,io,json,tarfile
from pathlib import Path
ROOT=Path('/inspire/ssd/project/project-public/czxs253130660/state-core-matrix-20261024-v1')
files=['cells.json','source-manifest.json','source-manifest-preflight.json','candidate-cells.json']
for cell in json.loads((ROOT/'cells.json').read_text())['cells']:
    files += ['outputs/'+cell['key']+'/'+name for name in ('audit.json','binary-outcomes.json','manifest.json','gate.done.json','core.done.json','GATE-PASSED.json')]
assert all((ROOT/f).is_file() for f in files)
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as archive:
    for f in files:archive.add(ROOT/f,arcname=f)
data=buf.getvalue();encoded=base64.b64encode(data).decode();parts=[encoded[i:i+800] for i in range(0,len(encoded),800)]
print('SC24_ARTIFACT_HEADER '+json.dumps({'files':len(files),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'chunks':len(parts)}),flush=True)
for i,part in enumerate(parts):print('SC24_ARTIFACT_CHUNK '+json.dumps({'index':i,'data':part}),flush=True)
print('SC24_ARTIFACT_EXPORT_COMPLETE',flush=True)
