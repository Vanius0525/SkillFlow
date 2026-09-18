#!/usr/bin/env python3
"""Behavioural screen: no document / gold skill / wrong skill, on a whole dataset.

    python -m howskill.sra_behave --model $B/models/Qwen3-8B --dataset theoremqa \
        --out /root/out/beh-tqa-8b.jsonl --cells-out /root/out/cells-tqa-8b.json

Every causal run is read on the RESCUED cell -- items the gold document fixes --
and which items those are is a fact about a model, not about a dataset. The span
runs on Mistral borrowed Qwen3-8B's cells and got a gold accuracy of 0.33 on
them (HANDOFF §47), which is what this script exists to avoid.

Decoding is batched with left padding, greedy, the same max_new and the same
chat-template wrapper as the span runs. Batching changes bf16 numerics slightly,
so a cell label here can disagree with the batch-1 baselines a span run
recomputes for itself; this file only SELECTS items, and every number the paper
reports is read from the batch-1 baselines of the run that measures it.

Rows are one per (instance, arm), flushed as each batch finishes, so --resume
picks up after a reclaim. The cells file is written at the end:
    R = gold right, none wrong   F = both wrong   K = both right   B = gold wrong, none right
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import types

from howskill import sra
from howskill.prompts import build_prompt
from howskill.wb_diffvec import VecScorer, graded


def arm_skills(arm, inst, skills, pairs):
    sids = inst["skill_annotations"]
    if arm == "none":
        return []
    if arm == "gold":
        return [skills[s] for s in sids]
    if arm == "wrong":
        return [skills[pairs[s]] for s in sids]
    raise ValueError(arm)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--dataset", required=True, choices=sra.DATASETS)
    p.add_argument("--arms", default="none,gold,wrong")
    p.add_argument("--max-new", type=int, default=900)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--shard", default="0/1",
                   help="i/n: this process takes every n-th instance of the sorted "
                        "id list starting at i; merge the n cells files afterwards")
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--out", required=True)
    p.add_argument("--cells-out", required=True)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    instances, skills, pairs, _ = sra.load(a.dataset)
    ids = sorted(instances)
    if a.limit:
        ids = ids[:a.limit]
    si, sn = (int(x) for x in a.shard.split("/"))
    ids = ids[si::sn]
    arms = [x for x in a.arms.split(",") if x]

    tok = AutoTokenizer.from_pretrained(a.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        a.model, torch_dtype=torch.bfloat16, device_map="cuda",
        attn_implementation=a.attn).eval()
    # the span runs' own wrapper, so the templated string is identical
    shim = types.SimpleNamespace(tok=tok, thinking=False, cue="", prompt_mode="?")
    to_text = lambda s, u: VecScorer._prompt(shim, s, u)

    done = set()
    if a.resume and os.path.exists(a.out):
        for line in open(a.out, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                done.add((r["instance_id"], r["arm"]))
    jobs = []
    for iid in ids:
        for arm in arms:
            if (iid, arm) in done:
                continue
            system, user = build_prompt(instances[iid],
                                        skills=arm_skills(arm, instances[iid],
                                                          skills, pairs))
            jobs.append((iid, arm, to_text(system, user)))
    # longest first: an OOM shows up in the first batch, not after hours
    jobs.sort(key=lambda j: -len(j[2]))
    model_name = os.path.basename(a.model.rstrip("/"))
    print(f"{model_name} on {a.dataset}: {len(ids)} instances x {arms}, "
          f"{len(jobs)} decodes to do, batch {a.batch}, prompt_mode "
          f"{shim.prompt_mode}", flush=True)

    def run(chunk):
        """Generate for a chunk; on OOM split it in half and try again."""
        enc = tok([t for _, _, t in chunk], return_tensors="pt",
                  padding=True, add_special_tokens=False).to("cuda")
        try:
            with torch.no_grad():
                out = model.generate(**enc, max_new_tokens=a.max_new,
                                     do_sample=False, temperature=None,
                                     top_p=None, top_k=None,
                                     eos_token_id=tok.eos_token_id,
                                     pad_token_id=tok.pad_token_id)
        except torch.OutOfMemoryError:
            del enc
            torch.cuda.empty_cache()
            if len(chunk) == 1:
                raise
            h = len(chunk) // 2
            return run(chunk[:h]) + run(chunk[h:])
        gen = out[:, enc["input_ids"].shape[1]:]
        return list(zip(chunk, gen.cpu()))

    import time
    t0 = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "a", encoding="utf-8") as fh:
        for b0 in range(0, len(jobs), a.batch):
            for (iid, arm, _), g in run(jobs[b0:b0 + a.batch]):
                text = tok.decode(g, skip_special_tokens=True)
                n_new = int((g != tok.pad_token_id).sum())
                fh.write(json.dumps({
                    "instance_id": iid, "dataset": a.dataset, "arm": arm,
                    "model": model_name, "prompt_mode": shim.prompt_mode,
                    "ok": graded(text, instances[iid], "cot"),
                    "n_new": n_new, "hit_max": n_new >= a.max_new,
                    "tail": text[-300:]}) + "\n")
            fh.flush()
            print(f"  {min(b0 + a.batch, len(jobs))}/{len(jobs)}  "
                  f"{time.time() - t0:.0f}s", flush=True)

    ok = collections.defaultdict(dict)
    for line in open(a.out, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            ok[r["instance_id"]][r["arm"]] = r["ok"]
    cells = {"R": [], "F": [], "K": [], "B": []}
    for iid, v in sorted(ok.items()):
        if "gold" not in v or "none" not in v:
            continue
        cells["R" if v["gold"] and not v["none"] else
              "K" if v["gold"] and v["none"] else
              "B" if v["none"] else "F"].append(iid)
    acc = {arm: sum(v.get(arm, False) for v in ok.values()) / max(1, len(ok))
           for arm in arms}
    json.dump({"cells": cells, "arms": arms, "model": model_name,
               "dataset": a.dataset, "n": len(ok), "accuracy": acc,
               "source": os.path.basename(a.out)},
              open(a.cells_out, "w", encoding="utf-8"), indent=1)
    print(f"accuracy {acc}; cells " +
          " ".join(f"{k}={len(v)}" for k, v in cells.items()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
