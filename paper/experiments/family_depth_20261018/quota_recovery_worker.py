import argparse,json,subprocess,sys,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--key');p.add_argument('--model');p.add_argument('--layers',type=int);p.add_argument('--original');p.add_argument('--repo');a=p.parse_args();here=Path(__file__).resolve().parent;old=Path(a.original)
common=['--dataset','theoremqa','--model',a.model,'--cells',str(old/f'legacy-{a.key}-theoremqa.cells.json'),'--cells-keep','R','--per-calc','10000','--max-calcs','10000','--min-group','1','--max-new','900']
def run(module,args):subprocess.run([sys.executable,'-u',str(here/'legacy_text_entry.py'),'--repo',a.repo,'--module',module,'--expected',str(old/f'legacy-{a.key}-theoremqa.expected.json'),'--',*args],check=True)
completed=[]
for start in range(0,a.layers,4):
 name=f'{a.key}-transfer-{start:02d}.jsonl';o=old/name;done=o.with_suffix('.done.json')
 if done.exists():
  d=json.loads(done.read_text());raw=o.with_suffix('.answers.jsonl');assert d['records']==len(o.read_text().splitlines()) and d['answers']==len(raw.read_text().splitlines())
  if 'raw_sha256' in d:assert d['raw_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest()
  m=json.loads(o.with_suffix('.replay-manifest.json').read_text());assert m['module_sha256']==hashlib.sha256((Path(a.repo)/'howskill/howskill/wb_spanvec.py').read_bytes()).hexdigest()
  assert m['args'][m['args'].index('--layers')+1]==','.join(map(str,range(start,min(start+4,a.layers))))
  print('REUSED_ORIGINAL_COMPLETE',o,flush=True);completed.append(str(o));continue
 assert start!=0,'Full first-block baselines must already be complete'
 out=here/name
 run('wb_spanvec',common+['--mode','decode','--attn','sdpa','--filler','fixedskill','--layers',','.join(map(str,range(start,min(start+4,a.layers)))),'--arms','real','--out',str(out)])
 completed.append(str(out))
(here/f'{a.key}-transfer-recovery.done.json').write_text(json.dumps({'blocks':completed,'notes':'Partial SSD block preserved; only unfinished blocks regenerated on HDD'})+'\n')
if a.key!='q8':run('wb_knockout',common+['--sweep','layers','--attn','eager','--layers',','.join(map(str,range(a.layers))),'--out',str(here/f'{a.key}-knockout.jsonl')])
