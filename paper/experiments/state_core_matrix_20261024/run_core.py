"""Frozen 24-condition matrix; each cell gates first and reuses its gate records."""
import argparse,fcntl,gzip,json,os,sys,time
from pathlib import Path
from plan import ROOT,MODELS,conditions,save,sha
sys.path.insert(0,str(ROOT/'snapshot/howskill'))
from legacy_core import Scorer
from frozen_run import Engine,neutral_ids,record_bytes,read_records
from grading import evaluate

def main():
    p=argparse.ArgumentParser();p.add_argument('--cell',required=True);a=p.parse_args()
    cell=next(c for c in json.loads((ROOT/'cells.json').read_text())['cells'] if c['key']==a.cell)
    out=ROOT/'outputs'/a.cell;out.mkdir(parents=True,exist_ok=True)
    with (out/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/'audit.json').exists():
            print('ALREADY_AUDITED_NO_GENERATION');return
        frozen=json.loads((ROOT/'source-manifest.json').read_text())
        assert all(sha(ROOT/k)==v for k,v in frozen.items()),'Source bundle changed'
        import torch,transformers
        from howskill import sra
        torch.manual_seed(0);torch.set_num_threads(4)
        assert '4090' in torch.cuda.get_device_name(),'Expected 4090 hardware'
        model=MODELS+'/'+cell['model'];sc=Scorer(model,'eager');engine=Engine(sc,1536)
        assert engine.depth==cell['depth']
        assert all(sha(Path(model)/k)==v for k,v in cell['model_asset_sha256'].items())
        instances,skills,pairs,distractor=sra.load(cell['dataset']);neutral=json.loads((ROOT/'neutral.json').read_text())['neutral_a']
        manifest={'cell':cell,'sources':frozen,'torch':torch.__version__,'transformers':transformers.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(),'max_new':1536,'protocol':'bf16/eager/split/greedy','conditions':conditions()}
        mp=out/'manifest.json'
        if mp.exists():assert json.loads(mp.read_text())==json.loads(json.dumps(manifest)),'Manifest conflict'
        else:save(mp,manifest)
        def run_phase(label,ids,arms,seed=()):
            raw=out/(label+'.jsonl.gz');progress=out/(label+'.progress.json');done=out/(label+'.done.json')
            rows=read_records(raw) if raw.exists() else [];bykey={(r['instance_id'],r['arm'],r['layer']):r for r in rows}
            assert len(rows)==len(bykey),'Duplicate existing records'
            expected={(iid,arm,l) for iid in ids for arm,l in arms};assert set(bykey)<=expected
            if done.exists():
                d=json.loads(done.read_text());assert set(bykey)==expected and d['raw_sha256']==sha(raw);return bykey
            with raw.open('ab') as stream:
                def append(row):
                    key=(row['instance_id'],row['arm'],row['layer']);assert key in expected and key not in bykey
                    stream.write(record_bytes(row,True));stream.flush();os.fsync(stream.fileno());bykey[key]=row
                    save(progress,{'cell':a.cell,'phase':label,'records':len(bykey),'expected':len(expected),'last_key':list(key),'time':time.time()})
                    print(json.dumps({'cell':a.cell,'phase':label,'records':len(bykey),'expected':len(expected)}),flush=True)
                for row in seed:
                    key=(row['instance_id'],row['arm'],row['layer'])
                    if key in expected and key not in bykey:append(dict(row,reused_from='gate: same cell, source manifest and protocol'))
                for iid in ids:
                    if all((iid,arm,l) in bykey for arm,l in arms):continue
                    item=sc.build(instances[iid],skills,pairs,distractor);lo,hi=item['lo'],item['hi'];span=(lo,hi)
                    inputs={'donor':item['ids_g'],'wrong':item['ids_r'],'no_skill':item['ids_none'],'neutral_a':neutral_ids(sc,item['ids_g'],span,neutral)}
                    assert max(x.shape[1] for x in inputs.values())+1536<=cell['context_limit']
                    donor_past,donor_h=engine.prefix(inputs['donor'],span);donor_kv=engine.snapshot(donor_past);del donor_past
                    for arm,layer in arms:
                        if (iid,arm,layer) in bykey:continue
                        started=time.monotonic();bg,action=arm.split(':') if ':' in arm else (arm,arm);ids0=inputs[bg]
                        state=donor_h[layer] if action in ('SC','SC_exact') else None
                        if action=='identity':
                            own,ownh=engine.prefix(ids0,span);del own;state=ownh[layer]
                        past,_=engine.prefix(ids0,span,patch_layer=layer if state is not None else None,state=state)
                        n=ids0.shape[1]-1;source=list(range(lo,hi));other=list(range(lo))+list(range(hi,n));positions=[];layers=[]
                        if action=='SC':layers=list(range(layer+1));positions=source
                        elif action in ('SC_exact','C_all','suffix_replay'):layers=list(range(engine.depth));positions=source
                        elif action=='B_only':layers=list(range(engine.depth));positions=other
                        elif action=='full_copy':layers=list(range(engine.depth));positions=list(range(n))
                        measure=bg!='no_skill';before=engine.audit(past,donor_kv,span) if measure else None
                        if layers:
                            with torch.inference_mode():engine.write(past,donor_kv,positions,layers)
                        if action=='suffix_replay':
                            past.crop(hi)
                            with torch.inference_mode():
                                if hi<n:
                                    replay=ids0[:,hi:-1].to(sc.device)
                                    result=sc.model(input_ids=replay,attention_mask=torch.ones((1,n),dtype=ids0.dtype,device=sc.device),past_key_values=past,use_cache=True);past=result.past_key_values
                        after=engine.audit(past,donor_kv,span) if measure else None
                        result=engine.generate(ids0,past,span);del past
                        append({'cell':a.cell,'instance_id':iid,'group':sra.group_key(instances[iid]),'arm':arm,'layer':layer,'source_span':[lo,hi],'prompt_tokens':ids0.shape[1],'seconds':time.monotonic()-started,'correct':evaluate(result['text'],instances[iid]),'cache_audit_before':before,'cache_audit_after':after,'written_layers':layers,'written_position_count':len(positions),**result})
            assert set(bykey)==expected
            for row in reversed(list(bykey.values())):assert evaluate(row['text'],instances[row['instance_id']])==row['correct'],'Reverse-order grading drift'
            save(done,{'cell':a.cell,'phase':label,'records':len(bykey),'items':len(ids),'raw_sha256':sha(raw),'finished_at':time.time()});return bykey
        gate_arms=conditions()+[('wrong:identity',16)]
        gate=run_phase('gate',cell['gate_ids'],gate_arms)
        for iid in cell['gate_ids']:
            assert gate[(iid,'wrong:identity',16)]['token_ids']==gate[(iid,'wrong',-1)]['token_ids'],'Own-state identity failed'
            for bg in ('wrong','neutral_a'):
                assert gate[(iid,bg+':full_copy',-1)]['token_ids']==gate[(iid,'donor',-1)]['token_ids'],'Full-prefix identity failed'
                for l in (8,16,24):
                    vals=gate[(iid,bg+':SC_exact',l)]['cache_audit_after'];assert all(v['max_abs']==0 for v in vals if v['region']=='source'),'Explicit source write incomplete'
        save(out/'GATE-PASSED.json',{'cell':a.cell,'gate_records':len(gate),'time':time.time()})
        run_phase('core',cell['ids'],conditions(),seed=gate.values())
        print('GENERATION_COMPLETE',a.cell,flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as exc:
        # Preserve all append-only outputs for diagnosis, never auto-retry a failed cell.
        cellarg=sys.argv[sys.argv.index('--cell')+1] if '--cell' in sys.argv else 'unknown'
        out=ROOT/'outputs'/cellarg;out.mkdir(parents=True,exist_ok=True);save(out/'failed.json',{'error':str(exc),'time':time.time()});raise
