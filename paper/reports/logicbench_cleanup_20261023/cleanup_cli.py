"""Stop and remove only explicitly enumerated user-abandoned LogicBench jobs."""
import argparse,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
NAMES=['wt-lfull-'+m+'-s'+str(s)+'-1022' for m in ('q8','mistral','llama','deepseek') for s in (0,1)]+['wt-lfull-mistral-s'+str(s)+'-r1-1022' for s in (0,1)]+['wt-logic-'+m+'-1021' for m in ('q8','mistral','llama','deepseek')]+['wt-logic-llama-1021-r1']
CLI='/home/vanius/.local/bin/inspire';WS='可上网GPU资源'
def invoke(args):
 r=subprocess.run([CLI,*args],capture_output=True,text=True,timeout=65)
 return {'command':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
def status():
 r=invoke(['--json','job','status',*NAMES,'--workspace',WS]);assert r['returncode'] in (0,16),r
 return json.loads(r['stdout'])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['stop','delete']);a=ap.parse_args()
 before=status();(P/f'{a.phase}-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n')
 assert before['success'] and not before['data']['unresolved']
 receipts=[]
 if a.phase=='stop':
  for j in before['data']['items']:
   if j['status'] not in ('SUCCEEDED','FAILED','CANCELLED','STOPPED'):
    r=invoke(['job','stop',j['name'],'--workspace',WS]);receipts.append(r)
    (P/'stop-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
    assert r['returncode']==0,r
 else:
  assert all(j['status'] in ('SUCCEEDED','FAILED','CANCELLED','STOPPED') for j in before['data']['items'])
  for name in NAMES:
   r=invoke(['job','delete',name,'--workspace',WS,'--yes']);receipts.append(r)
   (P/'delete-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
   assert r['returncode']==0,r
 after=status();(P/f'{a.phase}-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
 if a.phase=='stop':assert all(j['status'] in ('SUCCEEDED','FAILED','CANCELLED','STOPPED') for j in after['data']['items'])
 else:assert not after['data']['items'] and len(after['data']['unresolved'])==len(NAMES)
 print(a.phase,'verified',len(receipts),'actions')
if __name__=='__main__':main()
