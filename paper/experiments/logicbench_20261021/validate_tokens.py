import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import baseline
from engine import Scorer
from transformers import AutoTokenizer
import torch
inst,skills,pairs,distractor=baseline.inputs()
sc=Scorer.__new__(Scorer)
sc.torch=torch
sc.model_path=str(baseline.MODEL_ROOT/baseline.MODELS['llama'])
sc.tok=AutoTokenizer.from_pretrained(sc.model_path,local_files_only=True)
n=0
for iid,i in sorted(inst.items()):
 if i['skill_annotations'][0]==distractor:continue
 b=sc.build(i,skills,pairs,distractor)
 assert b['lo']<b['hi']<b['ids_g'].shape[1]
 assert torch.equal(b['ids_g'][:,:b['lo']],b['ids_r'][:,:b['lo']])
 assert torch.equal(b['ids_g'][:,b['hi']:],b['ids_r'][:,b['hi']:])
 n+=1
assert n==720
print('TOKENIZER_CHECK '+json.dumps({'llama_paired_questions':n,'source_and_prefix_suffix_checks':'passed'}))
