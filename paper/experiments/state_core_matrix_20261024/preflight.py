"""Freeze input-only context eligibility before any new model generation."""
from plan import *
sys.path.insert(0,str(ROOT/'snapshot/howskill'))
from howskill import sra
from transformers import AutoTokenizer,AutoConfig
from legacy_core import Scorer
from frozen_run import neutral_ids
import torch

def main():
    torch.set_num_threads(4)
    cells=json.loads((ROOT/'candidate-cells.json').read_text())['cells'];report=[]
    for c in cells:
        model=MODELS+'/'+c['model'];sc=Scorer.__new__(Scorer);sc.torch=torch;sc.device='cpu';sc.model_path=model
        sc.tok=AutoTokenizer.from_pretrained(model,local_files_only=True)
        cfg=AutoConfig.from_pretrained(model,local_files_only=True);depth=cfg.num_hidden_layers
        assert depth>24
        instances,skills,pairs,distractor=sra.load(c['dataset']);neutral=json.loads((ROOT/'neutral.json').read_text())['neutral_a'];valid=[];excluded=[]
        for iid in c['candidate_ids']:
            b=sc.build(instances[iid],skills,pairs,distractor);lo,hi=b['lo'],b['hi'];assert 0<lo<hi<b['ids_g'].shape[1]-1
            x=neutral_ids(sc,b['ids_g'],(lo,hi),neutral);assert x.shape==b['ids_g'].shape
            n=max(b[k].shape[1] for k in ('ids_g','ids_r','ids_none'))
            row={'id':iid,'group':sra.group_key(instances[iid]),'prompt_tokens':n,'source_tokens':hi-lo}
            (valid if n+1536<=cfg.max_position_embeddings else excluded).append(row)
        assert len(valid)>=2,c['key']
        c.update(ids=[x['id'] for x in valid],input_records=valid,excluded_for_context=excluded,depth=depth,context_limit=cfg.max_position_embeddings,groups=len({x['group'] for x in valid}),expected_records=24*len(valid),gate_ids=[x['id'] for x in valid[:2]],model_asset_sha256={p.name:sha(p) for p in Path(model).glob('*.json')})
        report.append(c);print(c['key'],len(valid),'items',c['groups'],'groups',len(excluded),'context exclusions',flush=True)
    save(ROOT/'cells.json',{'cells':report,'total_formal_records':sum(c['expected_records'] for c in report),'conditions_per_item':24,'completed_q8_medcalc_reused':True})
if __name__=='__main__':main()
