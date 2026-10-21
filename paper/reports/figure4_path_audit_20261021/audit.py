import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
files=list((ROOT/'experiments/family_depth_20261018/retrieved/snapshot-20261019').glob('*-edges.jsonl'))
files+=list((ROOT/'experiments/mechanism_20261017/parallel').glob('edges*.jsonl'))
result=[]
for p in files:
 keyed={}
 for line in p.open():
  r=json.loads(line);keyed[r['instance_id'],r['arm'],r['layer']]=r
 for l in [8,16,24]:
  pairs=[]
  for (i,a,layer),r in keyed.items():
   if a=='cut_reader_both' and layer==l and (i,'cut_both_both',l) in keyed:pairs.append((r,keyed[i,'cut_both_both',l]))
  if not pairs:continue
  result.append(dict(file=str(p.relative_to(ROOT)),layer=l,n=len(pairs),tokens_equal=sum(a['token_ids']==b['token_ids'] for a,b in pairs),correct_equal=sum(a['correct']==b['correct'] for a,b in pairs),first_equal=sum(a['first']==b['first'] for a,b in pairs),different_masked_rows=sum(a['instrumentation']['masked_rows']!=b['instrumentation']['masked_rows'] for a,b in pairs),examples=[{'reader':a['instrumentation'],'both':b['instrumentation'],'source_span':a['source_span']} for a,b in pairs[:1]]))
(ROOT/'reports/figure4_path_audit_20261021/raw_comparison.json').write_text(json.dumps(result,indent=2)+'\n')
for r in result:print(Path(r['file']).name,r['layer'],r['n'],'tokens=',r['tokens_equal'],'correct=',r['correct_equal'],'first=',r['first_equal'],'different_mask=',r['different_masked_rows'])
