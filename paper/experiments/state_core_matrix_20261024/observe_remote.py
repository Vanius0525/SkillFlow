"""Small shared-disk observation only; never starts or resubmits workloads."""
import json
from plan import ROOT,sha
r={'cells':{}}
for c in json.loads((ROOT/'cells.json').read_text())['cells']:
    out=ROOT/'outputs'/c['key'];v={}
    for label in ('gate','core'):
        p=out/(label+'.progress.json');d=out/(label+'.done.json');raw=out/(label+'.jsonl.gz')
        if p.exists():v[label]=json.loads(p.read_text())
        if d.exists():
            data=json.loads(d.read_text());expected=50 if label=='gate' else c['expected_records'];v[label+'_verified']=data['records']==expected and data['raw_sha256']==sha(raw)
    for name,key in [('failed.json','failure'),('audit.json','audit')]:
        p=out/name
        if p.exists():
            data=json.loads(p.read_text());v[key]=({k:data[k] for k in ('cell','n','groups','records','independent_audit_passed','source_error_SC_items','time')} if key=='audit' else data)
    r['cells'][c['key']]=v
print('OBS '+json.dumps(r))
