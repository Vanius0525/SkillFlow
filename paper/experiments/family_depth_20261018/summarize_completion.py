"""Summarize audited conditional experiment coverage; never modify manuscript values."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
PAPER=HERE.parents[1]
def load(name):return json.loads((HERE/name).read_text())
audit=load('completed-matrix-audit-20261020-r3.json')
newdepth=load('final-family-depth-audit-20261020.json')['comparisons']
assert audit['reverse_order_all_passed'] and audit['fresh_process_checks']==16 and not audit['new_grading_changes']
for x in audit['files']:
 assert not x['missing_baselines'] and not x['missing_fixed_candidates'] and not x['identity_failures'] and not x['cross_question_donor_failures']
 if x['suite']!='depth':assert not x['unexpected_missing_grid']
assert all(x['status']=='complete' and not x['missing'] and not x['baseline_token_drift'] for x in newdepth)
# Every source in the previously finalized new-family curves was rechecked.
byfile={x['file']:x for x in audit['files']}
for x in newdepth:
 for name,digest in x['sources'].items():assert byfile[name]['sha256']==digest
legacy=[]
for name in ['q8-independent-audit-20261020.json','mistral-independent-audit-20261020-r1.json']:
 x=load(name);assert not x['changed_labels'] and not x['missing_common_grid'] and not x['identity_failures'] and x['fresh_process_checks']==16
 legacy.append({'model':x['model'],'benchmark':'TheoremQA','n':x['common_n'],'groups':x['common_groups'],'T':x['transfer_boundary'],'R':x['reading_boundary'],'status':'audited','report':name})
old=json.loads((PAPER/'values/depth-verified-extension-20261019.json').read_text())
depth=[]
for x in old[:3]:depth.append({'model':x['model'],'benchmark':'MedCalc','n':x['common']['n'],'groups':x['common']['groups'],'T':x['transfer_boundary'],'R':x['reading_boundary'],'status':'historically_audited_sources_revalidated'})
depth+=legacy
for x in newdepth:depth.append({'model':x['model'],'benchmark':x['task'],'n':x['n'],'groups':x['groups'],'T':x['transfer_boundary'],'R':x['reading_boundary'],'status':'audited','report':'final-family-depth-audit-20261020.json'})
x=load('aggregated-post-quota-20261019-v2.json')['legacy_q06'];assert not x['missing'] and not x['identity_failures']
depth.append({'model':'Qwen3-0.6B','benchmark':'TheoremQA','n':x['common_n'],'groups':x['common_groups'],'T':x['transfer_boundary'],'R':x['reading_boundary'],'status':'previously_audited','report':'aggregated-post-quota-20261019-v2.json'})
assert len(depth)==10
suites=['battery','battery-l2','doclast','windows','bridge','repair','edges']
controls=[]
for model in ['q8','mistral','llama','deepseek','q06']:
 for task in ['medcalc','theoremqa']:
  for suite in suites:
   if model=='q8' and task=='medcalc' and suite!='battery-l2':
    controls.append({'model':model,'benchmark':task,'suite':suite,'status':'historical_verified','scope':'Original Qwen8/MedCalc probe and mechanism artifacts; not uniform regeneration with the new families.'});continue
   matches=[x for x in audit['files'] if x['model']==model and task in x['file'] and x['suite']==suite]
   if model=='deepseek' and task=='theoremqa' and suite!='doclast':matches=[x for x in matches if 'corrected54' in x['file']]
   assert len(matches)==1,(model,task,suite,[x['file'] for x in matches])
   x=matches[0];assert not x['unexpected_missing_grid']
   controls.append({'model':model,'benchmark':task,'suite':suite,'status':'audited','file':x['file'],'eligible_n':x['eligible_n'],'eligible_groups':x['eligible_groups'],'structurally_unavailable_records':x['structurally_unavailable_n']})
assert len(controls)==70
hist=load('historical-source-bindings-20261020.json');assert all(y['matches'] for x in hist for y in x['checks'])
# Check the remaining original Qwen8/MedCalc control artifacts are present.
by=PAPER.parent/'howskill/results/p8-wb/fetched/by-host'
tags=['full-battery-a','full-battery-b','full-window','full-dl-a','full-dl-b','full-quarters','pb-tq']
historical_controls=[]
for tag in tags:
 files=sorted(by.glob('*/'+tag+'.jsonl'));assert files,tag
 for p in files:historical_controls.append({'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'records':len(p.read_text().splitlines())})
sys_path = str(PAPER/'tools')
import sys
sys.path.insert(0,sys_path)
import replication as rep
dl=rep.restricted(rep.load(['full-dl-a','full-dl-b']))
assert len(dl)==17 and sum(map(len,dl.values()))==151
result={'date':'2026-10-20','main_model_benchmark_cells':8,'supplementary_cells':2,'depth':depth,'control_suite_cells':70,'controls':controls,'historical_q8_medcalc_control_files':historical_controls,'historical_q8_medcalc_doclast_verified':{'n':151,'groups':17,'L8_current_rho':rep.rho(dl,'ok_real_L8'),'L8_other_rho':rep.rho(dl,'ok_dother_L8')},'audited_family_files':len(audit['files']),'audited_family_records':sum(x['records'] for x in audit['files']),'identity_checks':sum(x['identity_checked'] for x in audit['files']),'unexpected_missing_final_grid':0,'repair_edges_baseline_token_drift':sum(len(x['token_drift']) for x in audit['repair_edges_baseline_comparison']),'eligibility_correction':'Mechanism bridge/repair/edges use per-item fresh baselines, matching original analyze.py; r1/r2 summaries are superseded for final manuscript use.','conditional_generation_and_remaining_audits_complete':True,'manuscript_integration_complete':False,'limits':['These are frozen conditional candidate populations, not full-benchmark sweeps for every model.','Historical Qwen8/MedCalc support is reused; all 70 cells are not uniform reruns.','Same-family and cross-question donor availability restrict some cells; absent donors are not imputed as zero.','Depth and mechanism/controls use independently screened populations and different protocols; do not impose one denominator.','Exact historical knockout budget equivalence for regenerated legacy TheoremQA remains unverified.','Old DeepSeek depth missing records are resolved by merging scorefix supplements; do not double-count baselines.','HDD quota remains unresolved for durable writes; audit reports were returned directly to local storage.']}
out=HERE/'completion-matrix-20261020-r3.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
lines=['# 正文实验完成度核验（2026-10-20）','','在既定冻结候选集与各suite独立基线下，主比较4模型×2 benchmark的8格、补充Qwen0.6的2格，深度实验均已完成并有审计依据。内容/位置、固定L2、跨题、窗口、bridge、repair、edges共70个模型×任务×suite格均有结果；其中Qwen8/MedCalc六格沿用原始已验证实验，其他64格本轮按协议核验。','', '本轮未更新论文，不能把数据齐全当交付完成。当前正文仍保留Qwen8、Mistral/TheoremQA Pending。','','| 模型 | benchmark | 共同题数/组数 | T/R（首次50%边界） |','|---|---|---:|---:|']
for x in depth:lines.append(f"| {x['model']} | {x['benchmark']} | {x['n']}/{x['groups']} | {x['T']}/{x['R']} |")
lines+=['','80个family文件/87,915条记录完成网格和基线重建；6,024项已执行身份对照无失败。新评分无标签变化；DeepSeek corrected54 edges/repair 54题基线token一致，各自有效46题。旧DeepSeek深度的300个缺失键已由5题scorefix补齐，合并后无缺失、无token漂移。','','HDD整盘仍余约25TiB、inode充足，个人目录占约58GiB。Errno122说明受配额约束，精确限额未查得。artifacts约26GiB、support_opd_20261002约12GiB是其他研究产物；models约12GiB；wheelhouse约3GiB。均未删除。审计已改为不写共享盘，本次任务不受阻；长期恢复持久写入仍需核对可再生缓存/旧checkpoint用途后经用户确认清理，或由管理员调高配额。','','证据边界：']+[f'- {s}' for s in result['limits']]
(HERE/'COMPLETION-20261020-r3.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'depth_cells':len(depth),'control_cells':len(controls),'family_files':len(audit['files']),'identity_checks':result['identity_checks'],'all_conditional_generation_and_audits_complete':True,'paper_updated':False}))
