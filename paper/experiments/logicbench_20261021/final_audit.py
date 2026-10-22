"""Read remote baseline outputs, regrade and retrieve only small audit artifacts."""
import json
from pathlib import Path
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
CODE = r'''
import sys,json,pathlib,hashlib,datetime
root=pathlib.Path('/inspire/hdd/project/project-public/czxs253130660/logicbench-20261021-v1')
sys.path.insert(0,str(root))
import baseline as b
out={}; eligible={}
for key in ('q8','mistral','llama','deepseek'):
 p=root/'outputs'/(key+'.jsonl')
 old=json.loads(p.with_suffix('.summary.json').read_text())
 new=b.audit(p)
 assert {k:v for k,v in old.items() if k!='time'}=={k:v for k,v in new.items() if k!='time'}
 done=json.loads(p.with_suffix('.done.json').read_text())
 assert done['records']==new['records']==2240 and done['sha256']==new['raw_sha256']==b.digest(p)
 rows=b.read_rows(p);ids=sorted({i for i,a in rows});paired=[i for i in ids if (i,'receiver') in rows]
 clean=[i for i in paired if not any(rows[i,a]['truncated'] for a in ('donor','receiver','no_skill'))]
 e=set(new['common_ids']);eligible[key]=e
 def stats(pop):
  return {'n':len(pop),'correct':{a:sum(rows[i,a]['correct'] for i in pop) for a in ('donor','receiver','no_skill')}}
 contaminated=sorted(e-set(clean))
 out[key]={'summary':new,'done':done,'hardware':p.with_suffix('.hardware.jsonl').read_text(),'audit':{'independent_regrade_matches':True,'raw_sha256_matches':True,'paired':stats(paired),'all_three_untruncated':stats(clean),'eligible_with_any_truncation':contaminated,'eligible_untruncated_n':len(e & set(clean)),'eligible_truncated_by_arm':{a:sum(rows[i,a]['truncated'] for i in e) for a in ('donor','receiver','no_skill')}}}
print('FINAL_AUDIT '+json.dumps({'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models':out,'four_model_eligible_intersection':sorted(set.intersection(*eligible.values()))}))
'''

def main():
    cmd = 'python_path=/inspire/ssd/project/project-public/czxs253130660/venvs/whitebox/bin/python; "$python_path" -c '+shlex.quote(CODE)
    r=subprocess.run(['inspire','notebook','exec','wt-family-prep-1018','--workspace','CPU资源空间',cmd,'--timeout','120'],text=True,capture_output=True,timeout=150)
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr)[-3000:])
    result=json.loads(next(l[len('FINAL_AUDIT '):] for l in r.stdout.splitlines() if l.startswith('FINAL_AUDIT ')))
    dest=HERE/'retrieved';dest.mkdir(exist_ok=True)
    for key,model in result['models'].items():
        for kind in ('summary','done','audit'):
            (dest/f'{key}.{kind}.json').write_text(json.dumps(model[kind],indent=2)+'\n')
        (dest/f'{key}.hardware.jsonl').write_text(model['hardware'])
    (HERE/'final-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    for key,m in result['models'].items():print(key,json.dumps(m['audit']))
    print('four_model_eligible_intersection',len(result['four_model_eligible_intersection']))

if __name__=='__main__':main()
