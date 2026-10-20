"""Read-only protocol-aware audit of completed family suites; emit a local report."""
import collections,copy,hashlib,json,random,subprocess,sys,time
from pathlib import Path
def eligible_population(groups,by,per_item=False):
 eligible=[]
 for ids in groups.values():
  if any((i,arm,-1) not in by for i in ids for arm in ['donor','receiver','no_skill']):continue
  if not per_item and any(by[i,'receiver',-1]['correct'] for i in ids):continue
  eligible.extend(i for i in ids if by[i,'donor',-1]['correct'] and not by[i,'receiver',-1]['correct'] and not by[i,'no_skill',-1]['correct'])
 return eligible

if '--self-test' in sys.argv:
 # A successful receiver on one question must not exclude a different rescued
 # question from the original per-item mechanism protocol.
 by={(i,arm,-1):{'correct':v} for i,vals in [('a',(True,False,False)),('b',(True,True,False)),('c',(True,False,True)),('d',(False,False,False))] for arm,v in zip(['donor','receiver','no_skill'],vals)}
 assert set(eligible_population({'g':{'a','b','c','d'}},by,True))=={'a'}
 assert eligible_population({'g':{'a','b','c','d'}},by,False)==[]
 assert set(eligible_population({'g':{'a'},'h':{'b'}},by,False))=={'a'}
 print('Population rule regression checks passed');sys.exit(0)

root=Path('/inspire/ssd/project/project-public/czxs253130660/family-depth-20261018-v1')
hdd=Path('/inspire/hdd/project/project-public/czxs253130660/family-depth-recovery-20261019')
sys.path.insert(0,str(root/'repo/howskill'))
from howskill import sra,sra_eval,grade
from howskill.wb_spanvec import family_of
import latex2sympy2 as parser
initial={k:copy.deepcopy(getattr(parser,k)) for k in ('var','variances','VARIABLE_VALUES','frac_type','is_real')}
datasets={d:sra.load(d) for d in ['theoremqa','medcalcbench']}
cache={};texts={};new_changes=[];results=[];baselines_by_file={};start=time.time()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def evaluate(r,dataset):
 iid=r['instance_id'];key=(dataset,iid,hashlib.sha256(r['text'].encode()).hexdigest())
 if key not in cache:
  if dataset=='theoremqa':
   for k,v in initial.items():setattr(parser,k,copy.deepcopy(v))
  cache[key]=(sra_eval if dataset=='theoremqa' else grade).evaluate(r['text'],datasets[dataset][0][iid]);texts[key]=r['text']
 return cache[key]
overlays=[]
for name in ['isolated-grading-refresh-20261019','post-quota-audit-20261019']:
 p=root/name;rp=p/'report.json'
 if not rp.exists():continue
 rr=json.loads(rp.read_text());assert rr['reverse_order_all_passed'] and rr['fresh_process_checks']>=16
 if isinstance(rr.get('sources'),dict):sources=rr['sources'];style='flat'
 else:sources={x['file']:x['sha256'] for x in rr['files']};style='nested'
 overlays.append((p,sources,style,sha(rp)))
paths=[]
for f in sorted(root.glob('*.jsonl')):
 if not f.with_suffix('.done.json').exists():continue
 if any(f.stem.endswith('-'+s) for s in ['battery','battery-l2','windows','doclast','bridge','repair','edges']) or any(f.stem.endswith('-'+s) for s in ['s0','s1']):paths.append(f)
paths.append(hdd/'deepseek-theoremqa-corrected54-edges.jsonl')
for path in paths:
 dataset='theoremqa' if 'theoremqa' in path.name else 'medcalcbench'
 inst,skills,*_=datasets[dataset]
 data=load(path);digest=sha(path);done=json.loads(path.with_suffix('.done.json').read_text())
 assert done['records']==len(data),(path,'record count')
 if data:assert all('text' in r and 'arm' in r for r in data)
 if '-s0' in path.stem or '-s1' in path.stem:suite='depth'
 elif path.stem.endswith('-battery-l2'):suite='battery-l2'
 else:suite=path.stem.rsplit('-',1)[1]
 model=next(m for m in ['mistral','q06','q8','llama','deepseek'] if m in path.name)
 nl={'mistral':32,'q06':28,'q8':36,'llama':32,'deepseek':30}[model]
 mp=path.with_suffix('.manifest.json');manifest=json.loads(mp.read_text()) if mp.exists() else {}
 assert manifest,(path,'missing manifest')
 maxnew=manifest.get('max_new',900 if suite in ['depth','battery','battery-l2','doclast','windows'] else 1536)
 assert all(len(r['token_ids'])<=int(maxnew) for r in data)
 used=None;labels=None
 if dataset=='theoremqa':
  for op,sources,style,rhash in reversed(overlays):
   rel=str(path.relative_to(root)) if path.is_relative_to(root) else None
   if rel in sources and sources[rel]==digest:
    target=op/(rel if style=='flat' else rel+'.grading.jsonl')
    if target.exists():labels=load(target);used={'report':str(op/'report.json'),'report_sha256':rhash};break
 if labels is not None:
  assert len(labels)==len(data)
  for idx,(r,g) in enumerate(zip(data,labels)):
   assert r['instance_id']==g['instance_id'] and hashlib.sha256(r['text'].encode()).hexdigest()==g['text_sha256']
   if 'record_index' in g:assert g['record_index']==idx
   if 'arm' in g:assert (r['arm'],r['layer'])==(g['arm'],g['layer'])
   r['correct']=bool(g['correct'])
 else:
  for r in data:
   result=evaluate(r,dataset)
   if bool(r['correct'])!=bool(result['correct']):new_changes.append({'file':path.name,'iid':r['instance_id'],'arm':r['arm'],'layer':r['layer']})
   r['correct']=bool(result['correct'])
 instrumentation_checked=0
 if suite in ['repair','edges']:
  for r in data:
   if r['layer']<0:continue
   ins=r['instrumentation']
   assert r.get('n_generated',len(r['token_ids']))==len(r['token_ids'])
   if suite=='repair':
    if r['arm'] in ['S','SC','SC_recut']:assert ins['patch_calls']==1
    if r['arm'] in ['C','SC','SC_recut']:assert ins['cache_layers_replaced']==r['layer']+1
    if r['arm']=='SC_recut':assert ins['mask_calls']>0
   else:assert ins['mask_calls']>0
   instrumentation_checked+=1
 by={}
 for r in data:
  key=(r['instance_id'],r['arm'],r['layer']);assert key not in by,(path,key);by[key]=r
 groups=collections.defaultdict(set)
 for r in data:
  if r['arm']=='donor':groups[r['group']].add(r['instance_id'])
 allids=set().union(*groups.values()) if groups else set()
 missing_baselines=[(i,arm) for i in allids for arm in ['donor','receiver','no_skill'] if (i,arm,-1) not in by]
 eligible=eligible_population(groups,by,suite in ['repair','edges','bridge'])
 donor_failures=[]
 for r in data:
  if r['arm']=='other_question':
   donors=r.get('donor_ids') or []
   if not donors or any(j==r['instance_id'] or sra.group_key(inst[j])!=r['group'] for j in donors):donor_failures.append([r['instance_id'],r['layer']])
 identity=[];identity_n=0
 for (iid,arm,l),r in by.items():
  if arm.startswith('identity'):
   ref='receiver_full' if arm.endswith('_full') else 'receiver'
   assert (iid,ref,-1) in by
   identity_n+=1
   if r['token_ids']!=by[iid,ref,-1]['token_ids']:identity.append([iid,arm,l])
 expected=[];structural=[]
 families={g:family_of(skills[inst[sorted(ids)[0]]['skill_annotations'][0]]['content'].splitlines()[0].strip('# ')) for g,ids in groups.items()}
 for i in eligible:
  g=by[i,'donor',-1]['group']
  if suite in ['battery','battery-l2']:
   l=2 if suite=='battery-l2' else 8
   expected.extend((i,arm,l) for arm in ['real','last_1','last_16','permuted','noise','normrecv','quarter_0','quarter_1','quarter_2','quarter_3'])
   if len(groups)>1:expected.extend((i,arm,l) for arm in ['other_skill','matched_prefix'])
   else:structural.extend((i,arm,l) for arm in ['other_skill','matched_prefix'])
   if any(h!=g and families[h]==families[g] for h in groups):expected.append((i,'same_family_mean',l))
   else:structural.append((i,'same_family_mean',l))
  elif suite=='doclast':
   if len(groups[g])<2:structural.extend((i,arm,l) for arm in ['current_question','other_question','identity'] for l in [8,16])
   else:expected.extend((i,arm,l) for arm in ['current_question','other_question','identity'] for l in [8,16])
  elif suite=='windows':
   expected.extend((i,f'window_{s}_{e}',s) for s,e in [(8,11),(12,15),(14,19),(16,nl-1),(0,nl-1)])
   expected.append((i,'single',16))
  elif suite=='repair':expected.extend((i,arm,l) for arm in ['S','C','SC','SC_recut'] for l in [8,12,16,24])
  elif suite=='edges':
   phases=manifest.get('phases','both').split(',')
   expected.extend((i,f'cut_{edge}_{phase}',l) for phase in phases for edge in ['reader','self','both'] if not (edge=='self' and phase=='decode') for l in [8,16,24])
  elif suite=='depth':expected.extend((i,arm,l) for arm in ['transfer','knockout'] for l in range(nl))
  elif suite=='bridge':expected.extend((i,arm,l) for arm in ['identity_S_full','S_full','identity_S_split','S_split','identity_SC'] for l in [8,12,16,24])
 if suite in ['battery','battery-l2','windows']:
  ilayers=[2,16] if suite=='battery-l2' else [8,16]
  expected.extend((i,'identity',l) for i in eligible for l in ilayers)
 if suite=='depth':expected.extend((i,'identity',l) for i in eligible for l in [0,nl-1])
 candidate_missing=[]
 if suite in ['battery','battery-l2','windows']:
  fixed=json.loads(Path(manifest['screen']).read_text())['common_ids']
  candidate_missing=sorted(set(fixed)-allids)
 elif suite in ['bridge','repair','edges']:
  fixed=json.loads(Path(manifest['ids']).read_text());fixed=fixed['ids'] if isinstance(fixed,dict) else fixed
  fixed=fixed[manifest.get('shard',0)::manifest.get('shards',1)]
  if manifest.get('limit'):fixed=fixed[:manifest['limit']]
  candidate_missing=sorted(set(fixed)-allids)
 elif suite=='doclast':
  fixed=json.loads(Path(manifest['ids']).read_text())['ids'];cx=path.with_suffix('.context.json')
  excluded=json.loads(cx.read_text()).get('excluded',[]) if cx.exists() else []
  excluded={i['id'] if isinstance(i,dict) else i for i in excluded}
  candidate_missing=sorted(set(fixed)-excluded-allids)
 missing=[key for key in expected if key not in by]
 arms=sorted({(r['arm'],r['layer']) for r in data if r['layer']>=0 and not r['arm'].startswith('identity')})
 estimates=[]
 for arm,l in arms:
  obs=[by[i,arm,l] for i in eligible if (i,arm,l) in by]
  estimates.append({'arm':arm,'layer':l,'n':len(obs),'correct':sum(r['correct'] for r in obs),'truncated':sum(bool(r['truncated']) for r in obs)})
 baselines_by_file[path.name]={i:{arm:by[i,arm,-1]['token_ids'] for arm in ['donor','receiver','no_skill'] if (i,arm,-1) in by} for i in allids}
 results.append({'file':path.name,'path':str(path),'model':model,'dataset':dataset,'suite':suite,'sha256':digest,'manifest_sha256':sha(mp),'records':len(data),'instrumentation_checked':instrumentation_checked,'baseline_n':len(allids),'eligible_n':len(eligible),'eligible_ids':sorted(eligible),'eligible_groups':len({by[i,'donor',-1]['group'] for i in eligible}),'missing_baselines':missing_baselines,'missing_fixed_candidates':candidate_missing,'unexpected_missing_grid':missing,'structurally_unavailable_n':len(structural),'identity_checked':identity_n,'cross_question_donor_failures':donor_failures,'identity_failures':identity,'grading_overlay':used,'estimates':estimates,'eligibility_rule':('per_item_fresh_split_baselines' if suite in ['repair','edges','bridge'] else 'group_receiver_screen_then_item_donor_rescue'),'scope':'Own observed protocol baselines; mechanism uses the original per-item fresh-baseline screen; structural donor unavailability explicit; bridge is a two-candidate probe.'})
 print('AUDITED',path.name,len(data),len(eligible),'missing',len(missing),flush=True)
# Independently regraded files must be order invariant, with fresh-process checks.
for key in reversed(list(cache)):
 d,iid,_=key
 r={'instance_id':iid,'text':texts[key]}
 if d=='theoremqa':
  for k,v in initial.items():setattr(parser,k,copy.deepcopy(v))
 assert (sra_eval if d=='theoremqa' else grade).evaluate(r['text'],datasets[d][0][iid])==cache[key]
keys=[k for k in cache if k[0]=='theoremqa'];random.Random(0).shuffle(keys)
code="import sys,json;sys.path.insert(0,sys.argv[1]);from howskill import sra_eval;x=json.load(sys.stdin);print(json.dumps(sra_eval.evaluate(x['text'],x['item'])))"
for key in keys[:16]:
 d,iid,_=key;r=subprocess.run([sys.executable,'-c',code,str(root/'repo/howskill')],input=json.dumps({'text':texts[key],'item':datasets[d][0][iid]}),capture_output=True,text=True,check=True,timeout=30);assert json.loads(r.stdout)==cache[key]
pairs=[]
for base in ['deepseek-theoremqa-corrected54','llama-medcalc','llama-theoremqa','deepseek-medcalc','backfill-q8-theoremqa','backfill-mistral-medcalc','backfill-mistral-theoremqa','backfill-q06-medcalc','backfill-q06-theoremqa']:
 f,g=base+'-repair.jsonl',base+'-edges.jsonl'
 if f not in baselines_by_file or g not in baselines_by_file:continue
 x,y=baselines_by_file[f],baselines_by_file[g];common=set(x)&set(y)
 drift=[(i,arm) for i in common for arm in ['donor','receiver','no_skill'] if x[i].get(arm)!=y[i].get(arm)]
 pairs.append({'prefix':base,'repair_baseline_n':len(x),'edges_baseline_n':len(y),'common_baselines':len(common),'token_drift':drift})
report={'files':results,'new_grading_changes':new_changes,'new_unique_regraded':len(cache),'new_theoremqa_unique_regraded':len(keys),'reverse_order_all_passed':True,'fresh_process_checks':min(16,len(keys)),'repair_edges_baseline_comparison':pairs,'seconds':time.time()-start,'raw_retained':True,'shared_disk_writes':False}
print('REPORT_JSON '+json.dumps(report),flush=True)
