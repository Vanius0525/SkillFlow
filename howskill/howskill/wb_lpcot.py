"""P-C -- a CONTINUOUS dependent variable along the transplant's depth sweep.

    python -m howskill.wb_lpcot --model $BASE/models/Qwen3-8B \
        --per-calc 20 --max-calcs 55 --layers 8,12,13,14,16 --out results/pc.jsonl

WHY THIS FILE EXISTS

The depth sweep's dependent variable is ACCURACY over a 900-token chain of
thought: the arithmetic comes out right or it does not. That is a threshold on
top of whatever the network does, and a perfectly smooth degradation inside the
network would still show up as a cliff in it. So the cliff the sweep reports
(rho 0.720 at layer 12, 0.346 at 13) is not yet evidence of a threshold IN THE
MODEL -- it is evidence of a threshold in the grader. Everything the head
analysis concluded rests on telling those two apart.

THE MEASUREMENT. Decode the chain of thought ONCE from the gold prompt, then
teacher-force that same trajectory under every other condition and read its
log-probability:

    lp_gold   the gold prompt scores its own reasoning          (ceiling)
    lp_recv   the filler receiver scores the gold reasoning     (floor)
    lp_L      the receiver patched at layer L scores it         (the arm)
    q(L)   =  (lp_L - lp_recv) / (lp_gold - lp_recv)

q is a continuous analogue of rho on the SAME trajectory, with the same two
anchors, and no decoding threshold anywhere in it. If q falls off a cliff
between layers 12 and 13 the threshold is in the network; if q declines
smoothly while rho cliffs, the cliff belongs to the grader and the "threshold
nonlinearity" reading has to be withdrawn.

WHY NOT THE CUE. wb_patch scores under a "\nANSWER: " cue, and on this material
that protocol is already known to dissociate from the task: accuracy reads
0.175 for no-skill, wrong-skill AND gold-skill alike while lp(gold) still moves
+0.60 nats (see wb_knockout's docstring). A continuous variable that moves when
the behaviour provably does not cannot settle this question. Scoring the full
reasoning trajectory keeps the dependent variable on the same object the
behavioural run graded.

WHAT IS RECORDED, per layer. The mean log-probability over (a) the whole
trajectory, (b) each quarter of it, and (c) the tokens after the final
"ANSWER:" marker. They are reported separately on purpose: the whole trajectory
is mostly boilerplate that every condition predicts equally, so a null there is
uninformative, while the answer tokens are the part accuracy actually reads and
are the most likely to inherit its threshold. A quantity that cliffs in (c) but
not in (a) or (b) is the signature of a grader threshold.

ONE ITEM SET. Items, calculators, seed and the filler receiver are built by the
same code path as wb_spanvec, so rows join the depth sweep on instance_id.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

from howskill.wb_diffvec import graded, pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spanpatch import SpanScorer, _OutputLock, resume_done
from howskill.wb_spanvec import build_item

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


class CotScorer(SpanScorer):
    def score_ids_cont(self, ids, cont_ids, layer=None, positions=None,
                       donor=None):
        """Per-token log-probabilities of `cont_ids` appended to `ids`.

        The continuation is teacher-forced: the model never chooses a token, so
        the number cannot be moved by a decoding threshold. The patch is applied
        with the same hook the behavioural run uses, at the same positions, so
        the only difference between this and `decode_ids` is who picks the
        tokens.
        """
        t = self.torch
        ids = ids.to(self.device)
        cont = cont_ids.to(self.device)
        full = t.cat([ids, cont], dim=1)
        att = t.ones_like(full)
        handles = []
        if donor is not None:
            handles.append(self.patch_hook(layer, positions, donor)(self.model))
        try:
            with t.no_grad():
                out = self.model(input_ids=full, attention_mask=att,
                                 use_cache=False)
        finally:
            for h in handles:
                h.remove()
        lp = t.log_softmax(out.logits[0].float()[:-1], dim=-1)
        got = lp.gather(1, full[0][1:].unsqueeze(1)).squeeze(1)
        return got[ids.shape[1] - 1:].cpu()


def summarise(lp, ans_start):
    """Mean over the whole trajectory, over each quarter, and over the answer."""
    n = lp.shape[0]
    q = n // 4
    out = {"lp": round(float(lp.mean()), 5), "n_tok": int(n)}
    for k in range(4):
        a, b = k * q, (k + 1) * q if k < 3 else n
        out[f"lp_q{k}"] = round(float(lp[a:b].mean()), 5) if b > a else None
    out["lp_ans"] = (round(float(lp[ans_start:].mean()), 5)
                     if ans_start is not None and ans_start < n else None)
    return out


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="medcalcbench")
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", required=True)
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--cells-keep", default="R")
    p.add_argument("--per-calc", type=int, default=20)
    p.add_argument("--max-calcs", type=int, default=55)
    p.add_argument("--min-group", type=int, default=2)
    p.add_argument("--filler", choices=["fixedskill", "fixed", "ctrl"],
                   default="fixedskill")
    p.add_argument("--layers", default="8,12,13,14,16")
    p.add_argument("--max-new", type=int, default=900)
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    n_cells = sum(len(v) for v in cells.values())
    from howskill import sra
    instances, skills, pairs, distractor = sra.load(a.dataset)
    import howskill.wb_spanvec as sv
    sv.FIXED_DISTRACTOR_SKILL = distractor

    sc = CotScorer(a.model, attn=a.attn)
    sc.cue = ""
    layers = [int(x) for x in a.layers.split(",") if x.strip()]
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, {k: v for k, v in instances.items()
                                  if distractor not in v["skill_annotations"]},
                          keep, a.per_calc, a.max_calcs, a.seed,
                          min_group=a.min_group)
    groups = collections.defaultdict(list)
    for calc, cell, iid in todo:
        groups[calc].append((cell, iid))
    order = sorted(groups)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    done = resume_done(a.out) if a.resume else set()
    print(f"model {os.path.basename(a.model.rstrip('/'))}, "
          f"{sc.model.config.num_hidden_layers} layers", flush=True)
    print(f"lpcot: {sum(len(v) for v in groups.values())} instances over "
          f"{len(order)} calculators x {len(layers)} layers, attn={a.attn}",
          flush=True)

    with _OutputLock(a.out), \
            open(a.out, "a" if a.resume else "w", encoding="utf-8") as fh:
        for gi, calc in enumerate(order):
            for cell, iid in groups[calc]:
                if iid in done:
                    continue
                it = build_item(sc, instances[iid], skills, pairs, a.arm,
                                a.ctrl_arm, filler=a.filler)
                # the reference trajectory: what the model does WITH the
                # document, decoded once, then scored under every condition
                text = sc.decode_ids(it["ids_g"], max_new=a.max_new)
                cont = sc.tok(text, return_tensors="pt",
                              add_special_tokens=False)["input_ids"]
                if cont.shape[1] < 8:
                    print(f"  skip {iid}: gold trajectory is {cont.shape[1]} "
                          f"tokens", flush=True)
                    continue
                # where the graded answer starts, in continuation tokens
                cut = text.rfind("ANSWER:")
                ans_start = None
                if cut >= 0:
                    ans_start = sc.tok(text[:cut], return_tensors="pt",
                                       add_special_tokens=False
                                       )["input_ids"].shape[1]
                rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
                       "dataset": a.dataset, "mode": "lpcot",
                       "model": os.path.basename(a.model.rstrip("/")),
                       "cells_n": n_cells, "filler": a.filler,
                       "n_patched": len(it["pos"]),
                       "n_prompt": int(it["ids_g"].shape[1]),
                       "layers": layers,
                       "ok_gold_in_context": graded(text, instances[iid], "cot"),
                       "has_answer_marker": ans_start is not None}
                g = sc.score_ids_cont(it["ids_g"], cont)
                r = sc.score_ids_cont(it["ids_r"], cont)
                rec["gold"] = summarise(g, ans_start)
                rec["recv"] = summarise(r, ans_start)
                for L in layers:
                    h_g = sc.capture_ids(it["ids_g"], L, it["pos"])
                    h_r = sc.capture_ids(it["ids_r"], L, it["pos"])
                    donor = h_g.float()        # = h_r + d, the `real` arm
                    lp = sc.score_ids_cont(it["ids_r"], cont, L, it["pos"],
                                           donor)
                    rec[f"L{L}"] = summarise(lp, ans_start)
                    del h_g, h_r, donor, lp
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                den = rec["gold"]["lp"] - rec["recv"]["lp"]
                qs = " ".join(
                    f"L{L}={((rec[f'L{L}']['lp'] - rec['recv']['lp']) / den):+.3f}"
                    for L in layers) if abs(den) > 1e-6 else "(den~0)"
                print(f"  [{gi+1}/{len(order)} {calc}] {iid} "
                      f"ntok={cont.shape[1]} gold={rec['gold']['lp']:.3f} "
                      f"recv={rec['recv']['lp']:.3f}  q: {qs}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
