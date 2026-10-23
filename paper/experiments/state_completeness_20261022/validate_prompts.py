"""CPU preflight: render every frozen question and verify replacement boundaries."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'snapshot'/'howskill'))
import torch
from transformers import AutoTokenizer
from howskill import sra
from legacy_core import Scorer
from run import neutral_ids

model = '/inspire/ssd/project/project-public/czxs253130660/models/Qwen3-8B'
sc = Scorer.__new__(Scorer)
sc.torch, sc.model_path = torch, model
sc.tok = AutoTokenizer.from_pretrained(model, local_files_only=True)
instances, skills, pairs, distractor = sra.load('medcalcbench')
ids = json.loads((ROOT/'ids.json').read_text())['ids']
texts = json.loads((ROOT/'neutral.json').read_text())
records = []
for iid in ids:
    item = sc.build(instances[iid], skills, pairs, distractor)
    lo, hi = item['lo'], item['hi']
    assert 0 < lo < hi < item['ids_g'].shape[1]-1
    for label, text in texts.items():
        new = neutral_ids(sc, item['ids_g'], (lo, hi), text)
        assert new.shape == item['ids_g'].shape
        assert torch.equal(new[:, :lo], item['ids_g'][:, :lo])
        assert torch.equal(new[:, hi:], item['ids_g'][:, hi:])
    records.append(dict(id=iid, group=sra.group_key(instances[iid]),
                        prompt_tokens=item['ids_g'].shape[1], source_tokens=hi-lo))
report = dict(items=len(records), groups=len({x['group'] for x in records}),
              max_prompt_tokens=max(x['prompt_tokens'] for x in records),
              source_min=min(x['source_tokens'] for x in records),
              source_max=max(x['source_tokens'] for x in records),
              records=records)
print(json.dumps(report))
