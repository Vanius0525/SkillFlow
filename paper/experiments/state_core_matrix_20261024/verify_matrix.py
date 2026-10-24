"""Local independent audit of small exported labels and runtime audit metadata."""
import json,hashlib,pathlib
import numpy as np
from plan import ROOT,conditions,save

def main():
    root=ROOT/'retrieved/export';cells=json.loads((root/'cells.json').read_text())['cells'];expected=json.loads((ROOT/'preflight-summary.json').read_text());assert len(cells)==7
    frozen=json.loads((root/'source-manifest.json').read_text());pre=json.loads((root/'source-manifest-preflight.json').read_text());assert frozen==dict(pre,**{'cells.json':hashlib.sha256((root/'cells.json').read_bytes()).hexdigest()})
    assert pre==json.loads((ROOT/'source-manifest-preflight.json').read_text()),'Deployed source manifest differs from submitted source hashes'
    checks=[];matrix=[];total=0
    for cell in cells:
        key=cell['key'];d=root/'outputs'/key;a=json.loads((d/'audit.json').read_text());labels=json.loads((d/'binary-outcomes.json').read_text());m=json.loads((d/'manifest.json').read_text());assert m['cell']==cell and m['sources']==frozen
        assert a==json.loads((ROOT/'retrieved'/(key+'.audit.json')).read_text()),'Log summary differs from exported audit'
        assert a['independent_audit_passed'] and not a['source_error_SC_items'];assert len(cell['ids'])==len(set(cell['ids']))==a['n'];assert len(set(labels['groups'].values()))==a['groups']
        assert set(labels['conditions'])=={arm+'@'+str(l) for arm,l in conditions()};assert set(labels['groups'])==set(cell['ids'])
        for phase,n in [('gate',50),('core',cell['expected_records'])]:
            done=json.loads((d/(phase+'.done.json')).read_text());assert done['records']==n==a['summaries'][phase]['records'];assert done['raw_sha256']==a['summaries'][phase]['sha256']
        assert json.loads((d/'GATE-PASSED.json').read_text())['gate_records']==50
        for arm,data in labels['conditions'].items():
            assert data['ids']==cell['ids'];assert len(data['ids'])==len(set(data['ids']));assert len(data['correct_ids'])==len(set(data['correct_ids']));assert set(data['correct_ids'])<=set(data['ids']);assert set(data['truncated_ids'])<=set(data['ids'])
            s=a['summaries'][arm];assert s['n']==a['n'] and s['correct']==len(data['correct_ids']) and s['truncated']==len(data['truncated_ids']);assert s['accuracy']==s['correct']/s['n']
        rng=np.random.default_rng(20261024);groups=sorted(set(labels['groups'].values()));n=a['n']
        for bg in ('wrong','neutral_a'):
            full=labels['conditions'][bg+':full_copy@-1'];assert full['correct_ids']==labels['conditions']['donor@-1']['correct_ids']
            assert a['token_equality'][bg+':full_copy']['equal']==n
            for l in (8,16,24):
                assert labels['conditions'][bg+':SC@'+str(l)]==labels['conditions'][bg+':SC_exact@'+str(l)]
                assert a['token_equality'][bg+':SC_vs_exact@'+str(l)]['equal']==n
            for action in ('SC','SC_exact'):
                l8=labels['conditions'][bg+':'+action+'@8'];l24=labels['conditions'][bg+':'+action+'@24'];num=[];den=[]
                for g in groups:
                    ids=[iid for iid in cell['ids'] if labels['groups'][iid]==g];den.append(len(ids));num.append(sum(int(i in l8['correct_ids'])-int(i in l24['correct_ids']) for i in ids))
                ix=rng.integers(0,len(groups),size=(10000,len(groups)));boot=np.asarray(num)[ix].sum(1)/np.asarray(den)[ix].sum(1);ci=np.quantile(boot,[.025,.975]).tolist();old=a['paired_intervals'][bg+':'+action+'8_minus_24'];assert old['difference']==sum(num)/sum(den);assert np.allclose(ci,old['ci95'],atol=1e-12)
        matrix.append({'cell':key,'n':n,'groups':a['groups'],'summaries':a['summaries'],'paired_intervals':a['paired_intervals'],'token_equality':a['token_equality']});total+=a['records'];checks.append({'cell':key,'records':a['records'],'local_label_and_bootstrap_check':True,'full_prefix_token_pairs':2*n,'SC_vs_exact_token_pairs':6*n})
    assert total==expected['total_formal_records']==10944
    save(ROOT/'retrieved/matrix-audit.json',{'verified':True,'formal_records':total,'cells':checks,'inference_rerun':False,'notes':['Raw gzip hashes were checked by independent remote process and cross-checked between exported done and audit metadata locally.','No raw answer text or model tensors were downloaded.','Bootstrap intervals are exploratory and unadjusted for multiple comparisons.']});save(ROOT/'retrieved/matrix-results.json',{'cells':matrix});print('Local matrix audit passed:7 cells,10944 formal labels, exact identity counts, all paired bootstrap intervals.')
if __name__=='__main__':main()
