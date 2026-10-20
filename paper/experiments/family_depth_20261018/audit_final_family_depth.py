"""Merge verified grading overlays and frozen-screen depth supplements."""
import argparse,collections,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--overlay',type=Path,required=True);a=p.parse_args()
report=json.loads((a.overlay/'report.json').read_text());assert report['reverse_order_all_passed'] and report['fresh_process_checks']>=16
results=[]
for model in ['llama','deepseek']:
 for task in ['medcalc','theoremqa']:
  names=[f'{model}-{task}-s{k}.jsonl' for k in range(2)]
  if model=='deepseek' and task=='theoremqa':names += [f'deepseek-theoremqa-scorefix-s{k}.jsonl' for k in range(2)]
  records={};drift=[];sources={}
  for name in names:
   path=a.root/name;assert path.with_suffix('.done.json').exists(),path
   rows=[json.loads(s) for s in path.read_text().splitlines()];sources[name]=hashlib.sha256(path.read_bytes()).hexdigest()
   if task=='theoremqa':
    assert report['sources'][name]==sources[name],name
    grades=[json.loads(s) for s in (a.overlay/name).read_text().splitlines()];assert len(rows)==len(grades)
    for r,g in zip(rows,grades):
     assert all(r[k]==g[k] for k in ('instance_id','arm','layer')) and hashlib.sha256(r['text'].encode()).hexdigest()==g['text_sha256'];r['correct']=g['correct']
   for r in rows:
    key=(r['instance_id'],r['arm'],r['layer'])
    if key in records:
     previous=records[key]
     if previous['token_ids']!=r['token_ids']:drift.append({'id':key[0],'arm':key[1],'layer':key[2],'same_label':bool(previous['correct'])==bool(r['correct'])})
     assert key[1] in ['donor','receiver','no_skill'],'Duplicate intervention'
    else:records[key]=r
  if task=='theoremqa':ids=report['screens'][model]['common_ids']
  else:ids=[i for k in range(2) for i in json.loads((a.root/f'{model}-{task}-s{k}.screen.json').read_text())['common_ids']]
  manifest=json.loads((a.root/f'{model}-{task}-s0.manifest.json').read_text());nl=manifest['n_layers'];missing=[];identity=[]
  for i in ids:
   assert records[i,'donor',-1]['correct'] and not records[i,'receiver',-1]['correct'] and not records[i,'no_skill',-1]['correct']
   for l in [0,nl-1]:
    if records[i,'identity',l]['token_ids']!=records[i,'receiver',-1]['token_ids']:identity.append([i,l])
   for l in range(nl):
    for arm in ['transfer','knockout']:
     if (i,arm,l) not in records:missing.append([i,arm,l])
  result={'model':model,'task':task,'n':len(ids),'groups':len({records[i,'donor',-1]['group'] for i in ids}),'baseline_token_drift':drift,'missing':missing,'identity_failures':identity,'sources':sources,'ids':ids,'status':'complete' if not drift and not missing and not identity else 'requires_review'}
  if not missing:
   tr=[sum(records[i,'transfer',l]['correct'] for i in ids)/len(ids) for l in range(nl)];q=[sum(records[i,'knockout',l]['correct'] for i in ids)/len(ids) for l in range(nl)]
   result.update(transfer=tr,retention=q,dependence=[1-x for x in q],transfer_boundary=next((l for l,x in enumerate(tr) if x<.5),None),reading_boundary=next((l for l,x in enumerate(q) if x>=.5),None),truncated={arm:[sum(bool(records[i,arm,l]['truncated']) for i in ids) for l in range(nl)] for arm in ['transfer','knockout']})
  results.append(result)
print('REPORT_JSON '+json.dumps({'comparisons':results}))
