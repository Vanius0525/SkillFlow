"""CPU-only independent recount, regrading and paired skill-cluster summaries."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def planned_arms():
    result = [(k, -1) for k in ('donor','wrong','neutral_a','neutral_b','no_skill')]
    for bg in ('wrong','neutral_a'):
        result += [(bg+':'+k,-1) for k in ('C_all','B_only','full_copy','suffix_replay','C_wrong','C_neutral_b')]
        result += [(bg+':'+k,l) for l in (8,16,24) for k in ('S','C_low','SC','SC_exact')]
        result += [(bg+':C_window_'+str(l),-1) for l in (0,8,16,24)]
    assert len(result) == len(set(result)) == 49
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    root = Path(a.root)
    sys.path.insert(0,str(root/'snapshot'/'howskill'))
    from howskill import grade
    import numpy as np
    instances = {x['instance_id']:x for x in json.loads((root/'snapshot/howskill/data/medcalcbench.json').read_text())}
    ids = json.loads((root/'ids.json').read_text())['ids']
    arms = planned_arms()
    rows, reports, audits, failures = {}, {}, collections.defaultdict(list), []
    for shard in (0,1):
        label = f'repair-{shard}-of-2'
        path = root/'outputs'/(label+'.jsonl.gz')
        done = json.loads((root/'outputs'/(label+'.done.json')).read_text())
        manifest = json.loads((root/'outputs'/(label+'.manifest.json')).read_text())
        assert manifest['mode']=='repair' and manifest['shard']==shard and manifest['shards']==2
        assert manifest['ids']==ids[shard::2]
        assert all(sha(root/k)==v for k,v in manifest['files'].items())
        actual_sha = sha(path)
        assert done['raw_sha256'] == actual_sha
        assert done['records'] == 3038
        expected = {(iid,arm,l) for iid in ids[shard::2] for arm,l in arms}
        actual = set()
        with gzip.open(path,'rt') as f:
            for line in f:
                r = json.loads(line)
                key = (r['instance_id'],r['arm'],r['layer'])
                assert key not in actual and key not in rows
                actual.add(key)
                assert len(r['token_ids']) == r['n_generated']
                assert bool(grade.evaluate(r['text'],instances[r['instance_id']])['correct']) == r['correct']
                action = r['arm'].split(':')[-1]
                before,after = r['cache_audit_before'],r['cache_audit_after']
                if before is not None:
                    assert len(before) == len(after) == 144
                    assert {(v['layer'],v['tensor'],v['region']) for v in after} == {
                        (l,t,s) for l in range(36) for t in ('K','V') for s in ('source','other')}
                    source = [v for v in after if v['region']=='source']
                    other = [v for v in after if v['region']=='other']
                    src_exact = all(v['max_abs']==0 and v['exact_fraction']==1 for v in source)
                    other_exact = all(v['max_abs']==0 and v['exact_fraction']==1 for v in other)
                    audits[f'{r["arm"]}@{r["layer"]}'].append(dict(source_exact=src_exact,
                        other_exact=other_exact,max_source_error=max(v['max_abs'] for v in source)))
                    if action in ('C_all','SC_exact','full_copy','suffix_replay') and not src_exact:
                        failures.append({'key':key,'reason':'source_cache_not_exact'})
                    if action in ('B_only','full_copy') and not other_exact:
                        failures.append({'key':key,'reason':'other_cache_not_exact'})
                    if action == 'C_low':
                        assert r['written_layers'] == list(range(r['layer']+1))
                    if action.startswith('C_window_'):
                        start = int(action.rsplit('_',1)[1])
                        assert r['written_layers'] == list(range(start,start+8))
                r['tokens_sha256'] = hashlib.sha256(json.dumps(r['token_ids']).encode()).hexdigest()
                rows[key] = {k:r[k] for k in ('instance_id','group','arm','layer','correct',
                    'truncated','n_generated','text','tokens_sha256','seconds')}
        assert actual == expected
        reports[label] = dict(records=len(actual),raw_sha256=actual_sha,bytes=path.stat().st_size)
    assert len(rows)==6076
    gp = root/'outputs/gate-0-of-1.jsonl.gz'
    gd = json.loads((root/'outputs/gate-0-of-1.done.json').read_text())
    assert gd['records']==14 and sha(gp)==gd['raw_sha256']
    with gzip.open(gp,'rt') as f:
        gate_rows=[json.loads(line) for line in f]
    gate_arms={('donor',-1),('wrong',-1),('identity',16),('full_copy',-1),
               ('C_all',-1),('SC_exact',16),('suffix_replay',-1)}
    assert {(r['instance_id'],r['arm'],r['layer']) for r in gate_rows}=={
        (i,arm,l) for i in ids[:2] for arm,l in gate_arms}
    for r in reversed(gate_rows):
        assert len(r['token_ids'])==r['n_generated']
        assert bool(grade.evaluate(r['text'],instances[r['instance_id']])['correct'])==r['correct']
    for iid in ids[:2]:
        gr={r['arm']:r for r in gate_rows if r['instance_id']==iid}
        assert gr['identity']['token_ids']==gr['wrong']['token_ids']
        assert gr['full_copy']['token_ids']==gr['donor']['token_ids']
    reports['gate']=dict(records=14,raw_sha256=gd['raw_sha256'],independent_regrade=True)
    # Reversed-order grading in this process is independent of both generator processes.
    for key in reversed(list(rows)):
        r = rows[key]
        assert bool(grade.evaluate(r['text'],instances[r['instance_id']])['correct']) == r['correct']
    def get(iid,arm,l=-1):
        return rows[(iid,arm,l)]
    equality = {}
    for bg in ('wrong','neutral_a'):
        for action,target in [('full_copy','donor'),('suffix_replay','donor')]:
            bad = [iid for iid in ids if get(iid,bg+':'+action)['tokens_sha256'] != get(iid,target)['tokens_sha256']]
            equality[bg+':'+action] = dict(equal=len(ids)-len(bad),total=len(ids),unequal_ids=bad)
            if action=='full_copy' and bad:
                failures.append({'reason':'full_copy_not_token_exact','background':bg,'ids':bad})
    own_bad = [iid for iid in ids if get(iid,'wrong:C_wrong')['tokens_sha256'] != get(iid,'wrong')['tokens_sha256']]
    equality['wrong:C_wrong'] = dict(equal=len(ids)-len(own_bad),total=len(ids),unequal_ids=own_bad)
    if own_bad:
        failures.append({'reason':'own_source_cache_write_not_token_exact','ids':own_bad})
    for bg in ('wrong','neutral_a'):
        for l in (8,16,24):
            bad = [iid for iid in ids if get(iid,bg+':SC',l)['tokens_sha256'] != get(iid,bg+':SC_exact',l)['tokens_sha256']]
            equality[f'{bg}:SC_vs_SC_exact@{l}'] = dict(equal=len(ids)-len(bad),total=len(ids),unequal_ids=bad)
    populations = {
        'full_frozen_pool':ids,
        'wrong_baseline_screen':[i for i in ids if get(i,'donor')['correct'] and not get(i,'wrong')['correct'] and not get(i,'no_skill')['correct']],
        'neutral_baseline_screen':[i for i in ids if get(i,'donor')['correct'] and not get(i,'neutral_a')['correct'] and not get(i,'no_skill')['correct']],
        'both_receiver_screen':[i for i in ids if get(i,'donor')['correct'] and not get(i,'wrong')['correct'] and not get(i,'neutral_a')['correct'] and not get(i,'no_skill')['correct']]}
    tables = {}
    for name,pop in populations.items():
        groups = sorted({get(i,'donor')['group'] for i in pop})
        groups_ids = [[i for i in pop if get(i,'donor')['group']==g] for g in groups]
        rng = np.random.default_rng(20261023)
        picks = rng.integers(0,len(groups),size=(10000,len(groups))) if groups else None
        counts = np.array([len(x) for x in groups_ids])
        table = dict(n=len(pop),groups=len(groups),ids=pop,conditions={},contrasts={})
        for arm,l in arms:
            rr = [get(i,arm,l) for i in pop]
            table['conditions'][f'{arm}@{l}'] = dict(correct=sum(r['correct'] for r in rr),n=len(pop),
                accuracy_pct=100*sum(r['correct'] for r in rr)/len(pop) if pop else None,
                truncated=sum(r['truncated'] for r in rr))
        def contrast(label,left,right):
            if not pop:return
            def delta(i): return int(get(i,*left)['correct'])-int(get(i,*right)['correct'])
            gs = np.array([sum(delta(i) for i in members) for members in groups_ids])
            boot = 100*gs[picks].sum(axis=1)/counts[picks].sum(axis=1)
            left_tr = [get(i,*left)['truncated'] for i in pop]
            right_tr = [get(i,*right)['truncated'] for i in pop]
            lo=sum((0 if lt else int(get(i,*left)['correct']))-(1 if rt else int(get(i,*right)['correct']))
                   for i,lt,rt in zip(pop,left_tr,right_tr))
            hi=sum((1 if lt else int(get(i,*left)['correct']))-(0 if rt else int(get(i,*right)['correct']))
                   for i,lt,rt in zip(pop,left_tr,right_tr))
            table['contrasts'][label]=dict(pp=100*gs.sum()/len(pop),
                cluster_bootstrap_95ci_pp=np.quantile(boot,[.025,.975]).tolist(),
                per_group_pp={g:100*s/c for g,s,c in zip(groups,gs,counts)},
                truncation_worst_best_pp=[100*lo/len(pop),100*hi/len(pop)])
        for bg in ('wrong','neutral_a'):
            for l in (8,16,24):
                contrast(f'{bg}:SC_exact-S@{l}',(bg+':SC_exact',l),(bg+':S',l))
                contrast(f'{bg}:SC_exact-C_all@{l}',(bg+':SC_exact',l),(bg+':C_all',-1))
                contrast(f'{bg}:SC_exact-SC@{l}',(bg+':SC_exact',l),(bg+':SC',l))
            for action in ('C_wrong','C_neutral_b','suffix_replay'):
                contrast(f'{bg}:C_all-{action}',(bg+':C_all',-1),(bg+':'+action,-1))
            contrast(f'{bg}:full_copy-C_all',(bg+':full_copy',-1),(bg+':C_all',-1))
            contrast(f'{bg}:B_only-baseline',(bg+':B_only',-1),(bg,-1))
        tables[name]=table
    cache_summary = {k:dict(n=len(v),source_exact=sum(x['source_exact'] for x in v),
        other_exact=sum(x['other_exact'] for x in v),max_source_error=max(x['max_source_error'] for x in v)) for k,v in audits.items()}
    result = dict(time=time.time(),scope='Qwen3-8B/MedCalc; experiments2/3 only; no new inference',
        files=reports,records=len(rows),independent_forward_reverse_grading=True,
        instrument_failures=failures,token_equality=equality,cache_audit=cache_summary,populations=tables,
        bootstrap=dict(samples=10000,unit='skill group',seed=20261023,interpretation='exploratory intervals; no multiplicity correction'))
    Path(a.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('AUDIT_SUMMARY '+json.dumps({'records':len(rows),'instrument_failures':failures,
        'populations':{k:{'n':v['n'],'groups':v['groups']} for k,v in tables.items()}}))


if __name__=='__main__':main()
