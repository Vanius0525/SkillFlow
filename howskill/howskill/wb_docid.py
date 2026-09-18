"""Can the last prompt position say WHICH document is in the prompt, when the
question cannot give it away?

WHY THIS FILE EXISTS

wb_vecstats decodes the calculator's identity from a vector at the last prompt
position and reaches 0.93-1.00 against a chance rate of 0.024. That number is
weaker than it looks, because MedCalc questions name the calculator they want
("using the Cockcroft-Gault Equation..."). The prompt already carries the label,
so a late-layer state reporting it is not evidence that the document was read --
which is why the no-document baseline climbs to 0.96 by layer 26.

This file removes the leak by construction. Every item is run with EVERY
document, so the class label is "which document is in the slot" and the question
is constant within an item and varies within every class. A classifier that
still separates the classes is separating documents, not questions.

    python -m howskill.wb_docid --model $BASE/models/Qwen3-8B \
        --out results/p8-wb/docid.jsonl

WHAT IS CLASSIFIED, at each layer

    h       the residual state itself
    d       h minus the same item's state under a fixed filler document, the
            content component wb_spanvec injects
    recv    the fixed-filler state, which carries no document-specific
            information at all and is the negative control: it must sit at
            chance, and it is the check that the protocol is not leaking the
            item identity into the class assignment

Leave-one-out nearest class mean on cosine similarity. No training, no
hyperparameter, so there is nothing to overfit.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

from howskill import arms as arms_mod
from howskill.prompts import build_prompt_spans
from howskill.wb_diffvec import pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spanpatch import SpanScorer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


def ncm_loo(vecs, labels, torch):
    """Leave-one-out nearest class mean on cosine similarity.

    The held-out point is removed from its own class mean, which is the whole
    point: with four points per class an unadjusted mean would contain the
    point being classified and the accuracy would be meaningless.
    """
    X = torch.stack(vecs).float()
    X = X / X.norm(dim=-1, keepdim=True).clamp_min(1e-9)
    classes = sorted(set(labels))
    idx = {c: [i for i, l in enumerate(labels) if l == c] for c in classes}
    sums = {c: X[idx[c]].sum(0) for c in classes}
    ok = 0
    for i, l in enumerate(labels):
        best, best_c = None, None
        for c in classes:
            n = len(idx[c])
            if c == l:
                if n < 2:
                    continue
                mu = (sums[c] - X[i]) / (n - 1)
            else:
                mu = sums[c] / n
            sim = float(torch.nn.functional.cosine_similarity(
                X[i], mu, dim=0))
            if best is None or sim > best:
                best, best_c = sim, c
        ok += (best_c == l)
    return ok / len(labels), len(classes)


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--per-calc", type=int, default=4)
    p.add_argument("--max-calcs", type=int, default=10)
    p.add_argument("--layers", default="0,6,10,14,18,22,26,30,35")
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    import torch

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    instances = {i["instance_id"]: i for i in json.load(
        open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
    skills = {s["skill_id"]: s for s in json.load(
        open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}
    pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"),
                          encoding="utf-8"))

    sc = SpanScorer(a.model, attn=a.attn)
    sc.cue = ""
    layers = [int(x) for x in a.layers.split(",") if x.strip()]
    todo = pick_instances(cells, instances, ["R"], a.per_calc, a.max_calcs,
                          a.seed)
    items = [iid for _, _, iid in todo]
    # one gold document per calculator in the set -- these are the classes
    docs = {}
    for calc, _, iid in todo:
        sid = instances[iid]["skill_annotations"][0]
        docs.setdefault(calc, sid)
    from howskill.wb_spanvec import FIXED_FILLER

    print(f"{len(items)} items x {len(docs)} documents = "
          f"{len(items)*(len(docs)+1)} forwards, layers {layers}", flush=True)

    def last_state(system, user, layer_set):
        enc = sc.tok(sc._prompt(system, user), return_tensors="pt")
        store = {}
        handles = []
        for L in layer_set:
            def fn(_m, _i, out, L=L):
                h = out[0] if isinstance(out, tuple) else out
                store[L] = h[0, -1, :].detach().float().cpu()
                return out
            handles.append(sc.model.model.layers[L].register_forward_hook(fn))
        try:
            with sc.torch.no_grad():
                sc.model(input_ids=enc["input_ids"].to(sc.device),
                         use_cache=False)
        finally:
            for h in handles:
                h.remove()
        return store

    H = collections.defaultdict(dict)   # (iid, calc) -> {layer: vec}
    RECV = {}
    for k, iid in enumerate(items, 1):
        inst = instances[iid]
        filler = [{"skill_id": "fixed", "content": FIXED_FILLER}]
        s0, u0, _ = build_prompt_spans(inst, skills=filler)
        RECV[iid] = last_state(s0, u0, layers)
        for calc, sid in docs.items():
            doc = arms_mod.build("gold_no_tool", skills.get(sid),
                                 neutral_for=skills.get(pairs.get(sid)), seed=0)
            s, u, _ = build_prompt_spans(inst, skills=doc)
            H[(iid, calc)] = last_state(s, u, layers)
        if k % 5 == 0 or k == len(items):
            print(f"  {k}/{len(items)}", flush=True)

    rows = []
    for L in layers:
        vh, vd, vr, lab = [], [], [], []
        for (iid, calc), st in H.items():
            vh.append(st[L])
            vd.append(st[L] - RECV[iid][L])
            lab.append(calc)
        # Negative control: the receiver holds no document, so the SAME state
        # replicated once per class must be inseparable. Assigning labels in
        # item order instead would let the classifier use the patient note,
        # which is calculator-specific -- that would be a control that fails
        # for the wrong reason.
        lab_r = []
        for iid in items:
            for calc in sorted(docs):
                vr.append(RECV[iid][L])
                lab_r.append(calc)
        acc_h, K = ncm_loo(vh, lab, torch)
        acc_d, _ = ncm_loo(vd, lab, torch)
        acc_r, _ = ncm_loo(vr, lab_r, torch)
        row = {"layer": L, "n": len(vh), "n_classes": K,
               "chance": 1.0 / K, "ncm_h": acc_h, "ncm_d": acc_d,
               "ncm_receiver_control": acc_r}
        rows.append(row)
        print(f"  L{L:2d}  ncm(h)={acc_h:.3f}  ncm(d)={acc_d:.3f}  "
              f"receiver control={acc_r:.3f}  (chance {1/K:.3f})", flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
