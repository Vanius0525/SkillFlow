"""Independent CPU-only process: raw keys, isolated regrading, identities and statistics."""
import argparse,collections,gzip,json,sys,time
from pathlib import Path
from plan import ROOT,conditions,sha,save
sys.path.insert(0,str(ROOT/'snapshot/howskill'))
from grading import evaluate

def audit(cellkey):
    from howskill import sra
    import numpy as np
    cell=next(c for c in json.loads((ROOT/'cells.json').read_text())['cells'] if c['key']==cellkey);out=ROOT/'outputs'/cellkey
    manifest=json.loads((out/'manifest.json').read_text());assert manifest['cell']==cell
    assert all(sha(ROOT/k)==v for k,v in manifest['sources'].items())
    instances,_,_,_=sra.load(cell['dataset']);rows={};source_error=collections.Counter();summaries={}
    for label,ids,arms in [('gate',cell['gate_ids'],conditions()+[('wrong:identity',16)]),('core',cell['ids'],conditions())]:
        raw=out/(label+'.jsonl.gz');done=json.loads((out/(label+'.done.json')).read_text());assert done['raw_sha256']==sha(raw)
        expected={(iid,arm,l) for iid in ids for arm,l in arms};data={}
        with gzip.open(raw,'rt') as f:
            for line in f:
                row=json.loads(line);key=(row['instance_id'],row['arm'],row['layer']);assert key not in data and key in expected
                assert row['cell']==cellkey and row['n_generated']==len(row['token_ids'])
                assert row['correct']==evaluate(row['text'],instances[row['instance_id']]),'Independent regrade failed'
                if row['cache_audit_after'] is not None:
                    vals=row['cache_audit_after'];assert {(v['layer'],v['tensor'],v['region']) for v in vals}=={(l,t,r) for l in range(cell['depth']) for t in ('K','V') for r in ('source','other')}
                    action=row['arm'].split(':')[-1];source=[v for v in vals if v['region']=='source']
                    if action in ('SC_exact','C_all','full_copy','suffix_replay'):assert all(v['max_abs']==0 for v in source),'Source write mismatch'
                    if label=='core' and action=='SC' and any(v['max_abs']!=0 for v in source):source_error[row['arm']+'@'+str(row['layer'])]+=1
                data[key]=row
        assert set(data)==expected and done['records']==len(data)
        for row in reversed(list(data.values())):assert row['correct']==evaluate(row['text'],instances[row['instance_id']])
        if label=='core':rows=data
        else:
            for iid in ids:assert data[(iid,'wrong:identity',16)]['token_ids']==data[(iid,'wrong',-1)]['token_ids']
        summaries[label]={'records':len(data),'sha256':sha(raw),'forward_reverse_regrade_passed':True}
    for arm,l in conditions():
        rr=[rows[(iid,arm,l)] for iid in cell['ids']];correct=sum(r['correct'] for r in rr)
        summaries[arm+'@'+str(l)]={'n':len(rr),'correct':correct,'accuracy':correct/len(rr),'truncated':sum(r['truncated'] for r in rr),'seconds_excluding_reused':sum(r['seconds'] for r in rr if 'reused_from' not in r)}
    eq={}
    for bg in ('wrong','neutral_a'):
        for action in ('full_copy','suffix_replay'):
            n=sum(rows[(iid,bg+':'+action,-1)]['token_ids']==rows[(iid,'donor',-1)]['token_ids'] for iid in cell['ids']);eq[bg+':'+action]={'equal':n,'total':len(cell['ids'])}
            if action=='full_copy':assert n==len(cell['ids']),'Complete-prefix identity failure'
        for l in (8,16,24):
            n=sum(rows[(iid,bg+':SC',l)]['token_ids']==rows[(iid,bg+':SC_exact',l)]['token_ids'] for iid in cell['ids']);eq[bg+':SC_vs_exact@'+str(l)]={'equal':n,'total':len(cell['ids'])}
    # Paired bootstrap samples skill groups, preserving within-group dependencies.
    groups=sorted(set(r['group'] for r in rows.values()));intervals={};rng=np.random.default_rng(20261024)
    for bg in ('wrong','neutral_a'):
        for action in ('SC','SC_exact'):
            num=[];den=[]
            for g in groups:
                ids=[iid for iid in cell['ids'] if rows[(iid,bg+':'+action,8)]['group']==g];den.append(len(ids));num.append(sum(int(rows[(iid,bg+':'+action,8)]['correct'])-int(rows[(iid,bg+':'+action,24)]['correct']) for iid in ids))
            ix=rng.integers(0,len(groups),size=(10000,len(groups)));boot=np.asarray(num)[ix].sum(1)/np.asarray(den)[ix].sum(1)
            intervals[bg+':'+action+'8_minus_24']={'difference':sum(num)/sum(den),'ci95':np.quantile(boot,[.025,.975]).tolist(),'groups':len(groups),'group_signs':{'positive':sum(v>0 for v in num),'tie':sum(v==0 for v in num),'negative':sum(v<0 for v in num)}}
    labels={arm+'@'+str(l):{'ids':cell['ids'],'correct_ids':[iid for iid in cell['ids'] if rows[(iid,arm,l)]['correct']],'truncated_ids':[iid for iid in cell['ids'] if rows[(iid,arm,l)]['truncated']]} for arm,l in conditions()}
    save(out/'binary-outcomes.json',{'cell':cellkey,'groups':{iid:rows[(iid,'donor',-1)]['group'] for iid in cell['ids']},'conditions':labels})
    result={'cell':cellkey,'n':len(cell['ids']),'groups':len(groups),'records':len(rows),'independent_audit_passed':True,'source_error_SC_items':dict(source_error),'token_equality':eq,'summaries':summaries,'paired_intervals':intervals,'time':time.time()};save(out/'audit.json',result);print('AUDIT_SUMMARY '+json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cell',required=True);a=p.parse_args();audit(a.cell)
