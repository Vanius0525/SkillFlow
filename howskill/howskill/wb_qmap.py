"""What is actually in each quarter of the document's token span?

The q0..q3 arms split the span into token quarters and the paper names them
('the quarter holding the computation'). The names have to come from the
tokenizer's split, not from reading the document by eye: an earlier version of
this mapping was computed in characters and was wrong.
"""
import json, os, sys
B = "/inspire/ssd/project/project-public/czxs253130660"
sys.path.insert(0, f"{B}/agent-harness/howskill")
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(f"{B}/models/Qwen3-8B")
D = f"{B}/agent-harness/howskill/howskill/../data"
skills = {s["skill_id"]: s for s in json.load(open(f"{D}/medcalc_skills.json"))}
inst = json.load(open(f"{D}/medcalcbench.json"))
seen = set()
for it in inst:
    sid = it["skill_annotations"][0]
    calc = str(it["eval_data"]["calculator_id"])
    if calc in seen or calc not in ("11", "22", "56", "64"):
        continue
    seen.add(calc)
    txt = skills[sid]["content"]
    ids = tok(txt, add_special_tokens=False)["input_ids"]
    m = len(ids)
    w = m // 4
    print(f"\n===== calculator {calc}  ({sid})  m={m} tokens")
    for k in range(4):
        lo, hi = k * w, ((k + 1) * w if k < 3 else m)
        seg = tok.decode(ids[lo:hi]).strip().replace("\n", " ⏎ ")
        print(f"  q{k} [{lo}:{hi}] {seg[:230]}")
