#!/usr/bin/env python3
"""
E2: activation patching across layers. The decisive experiment.

Question: can the effect of putting a skill in context be compressed into a
single residual-stream vector?

  cache   run WITH the skill, take the residual stream at the last prompt token
          of layer L
  patch   run WITHOUT the skill, overwrite that same position at layer L with
          the cached vector
  score   how much of the skill's benefit came back

  recovery = (patched - no_skill) / (with_skill - no_skill)

High recovery at some layer means the model does not need continued access to
the skill text -- one vector carries the effect, which is capability selection
(H2). Low recovery everywhere means the model keeps reading the skill's literal
content and no summary substitutes for it, which is retrieval (H1).

This runs before the attention work on purpose: its answer decides which of the
two is the main line, so investing in the other one first can be wasted.

Pre-registered prediction, written before any run (HANDOFF-whitebox.md 9.2,
after SAPO's principle/pattern/example levels):

    SKILL.pchem-procedure   principle-like  ->  should compress   (high recovery)
    SKILL.pchem-constants   example-like    ->  should not        (low recovery)
    SKILL.zorb-units        example-like    ->  should not

Conditions. The last two are not decoration -- without them a recovery number
cannot be interpreted:

  real        the item's own cached vector
  mismatched  another item's cached vector. Recovers as much? Then the vector is
              not carrying task-specific content and "recovery" was measuring
              the disturbance itself, not the skill.
  mean        the mean cached vector over all items. As good as real? Then the
              effect is one global "a skill is present" direction rather than
              per-item content -- a strictly stronger form of H2.

Dependent variable is the gold answer's logprob throughout. Each patched
measurement is then a single forward pass, which is what makes a full layer sweep
affordable -- scoring by generated accuracy instead would multiply the cost by
the number of layers, and accuracy is the coarser signal anyway.

    python e2_patch.py --model ../models/Qwen3-1.7B \
        --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
        --mode mc --limit 40 --run-id e2-tierA

    python e2_patch.py --model ../models/Qwen3-8B \
        --tasks tasks/tier_b/tasks.filtered.pchem-procedure.jsonl \
        --skill tasks/tier_b/SKILL.pchem-procedure.md \
        --mode num --limit 60 --layer-step 2 --run-id e2-tierB-proc

DO NOT read a recovery curve before the Phase 0 gate has passed for this
task/skill pair. With no behavioural effect the denominator is noise and the
ratio is meaningless -- not small, meaningless.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import random
import time

import torch

import model as M

HERE = pathlib.Path(__file__).resolve().parent


def load_tasks(path, limit=None):
    items = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return items[:limit] if limit else items


def fields(item, mode):
    if "question_mc" in item:
        return (item["question_mc"], item["answer_mc"], None) if mode == "mc" \
            else (item["question_num"], item["answer_num"], None)
    return item["question"], item["answer_raw"], item.get("unit") or None


@torch.no_grad()
def logprob_with_patch(r, ids, answer, layer=None, position=None, vector=None):
    """
    Mean logprob of `answer`, optionally patching one position of one layer.

    The patch is applied inside a single forward over prompt+answer, so
    `position` is an absolute index into that sequence -- it must be the last
    PROMPT token, not the last token, or the intervention lands inside the answer
    and measures something else entirely.
    """
    ans_ids = r.tok(answer, return_tensors="pt",
                    add_special_tokens=False).input_ids.to(r.device)
    full = torch.cat([ids, ans_ids], dim=1)

    if vector is None:
        logits = r.model(full, use_cache=False).logits.float()
    else:
        with M.patch_layer(r, layer, position, vector, prefill_only=False):
            logits = r.model(full, use_cache=False).logits.float()

    lp = torch.log_softmax(logits[:, :-1], dim=-1)
    picked = lp.gather(-1, full[:, 1:].unsqueeze(-1)).squeeze(-1)
    return picked[0, -ans_ids.shape[1]:].mean().item()


def bootstrap_ci(vals, n=2000, seed=0):
    if not vals:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    k = len(vals)
    means = []
    for _ in range(n):
        means.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n)]


def sparkline(vals) -> str:
    """Compact curve for reading over ssh."""
    chars = " .:-=+*#%@"
    fin = [v for v in vals if v == v]
    if not fin:
        return ""
    lo, hi = min(fin), max(fin)
    rng = (hi - lo) or 1.0
    return "".join(chars[min(9, max(0, int((v - lo) / rng * 9)))] if v == v else "?"
                   for v in vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--layer-step", type=int, default=1,
                    help="sweep every Nth layer; use 2-4 for a first pass at 8B")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    r = M.load(args.model, device=args.device)
    layers = list(range(0, r.n_layers, args.layer_step))

    print(f"model  : {args.model}")
    print(f"tasks  : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skill  : {args.skill}")
    print(f"layers : {len(layers)} of {r.n_layers} (step {args.layer_step})")
    print(f"run id : {run_id}\n")
    M.write_run_info(out_dir, r, {
        "experiment": "e2_patch", "run_id": run_id, "tasks": str(args.tasks),
        "skill": str(args.skill), "mode": args.mode, "n_items": len(items),
        "layers": layers, "dv": "answer_logprob",
    })

    # ---- pass 1: baselines and the cached vectors -------------------------
    # One forward with the skill gives every layer's residual at once, so the
    # cache costs one pass per item rather than one per layer.
    print("[1/2] baselines + cache")
    base = []
    t0 = time.time()
    for i, it in enumerate(items):
        q, gold, unit = fields(it, args.mode)
        ids_no = M.encode(r, M.render(r, M.build_messages(q, None, args.mode, unit)))
        ids_yes = M.encode(r, M.render(r, M.build_messages(q, skill, args.mode, unit)))

        lp_no = logprob_with_patch(r, ids_no, gold)
        lp_yes = logprob_with_patch(r, ids_yes, gold)

        cap = M.capture(r, ids_yes)
        # hidden_states[L+1] is the output of layer L; last prompt token
        vecs = {L: cap.hidden_states[L + 1][0, -1].detach().clone() for L in layers}
        del cap

        base.append({
            "id": it["id"], "gold": gold,
            "lp_no": lp_no, "lp_yes": lp_yes,
            "delta": lp_yes - lp_no,
            "prompt_len_no": int(ids_no.shape[1]),
            "ids_no": ids_no, "vecs": vecs,
        })
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s ({el/(i+1):.1f}s/item)", flush=True)

    mean_delta = sum(b["delta"] for b in base) / len(base)
    print(f"\n  mean logprob delta (with - without skill): {mean_delta:+.4f}")
    if abs(mean_delta) < 1e-3:
        print("  [!] The skill barely moves the logprob on these items. Recovery")
        print("      is a ratio over this number -- it will be noise. Check the")
        print("      Phase 0 gate (e0_effect.py) before reading anything below.")

    # mean vector per layer, and a derangement for the mismatched control
    mean_vec = {L: torch.stack([b["vecs"][L] for b in base]).mean(0) for L in layers}
    # rotate by one: a derangement, so no item is ever paired with itself
    order = list(range(len(base)))
    shifted = order[1:] + order[:1]

    # ---- pass 2: the sweep -------------------------------------------------
    print("\n[2/2] layer sweep")
    per_layer = {}
    t0 = time.time()
    for n, L in enumerate(layers):
        rows = []
        for i, b in enumerate(base):
            pos = b["prompt_len_no"] - 1          # last PROMPT token
            real = logprob_with_patch(r, b["ids_no"], b["gold"], L, pos, b["vecs"][L])
            mism = logprob_with_patch(r, b["ids_no"], b["gold"], L, pos,
                                      base[shifted[i]]["vecs"][L])
            meanp = logprob_with_patch(r, b["ids_no"], b["gold"], L, pos, mean_vec[L])
            rows.append({"id": b["id"], "lp_real": real, "lp_mismatched": mism,
                         "lp_mean": meanp, "lp_no": b["lp_no"], "lp_yes": b["lp_yes"]})

        def recov(key):
            out = []
            for x in rows:
                den = x["lp_yes"] - x["lp_no"]
                if abs(den) > 1e-6:
                    out.append((x[key] - x["lp_no"]) / den)
            return out

        rec = {k: recov(f"lp_{k}") for k in ("real", "mismatched", "mean")}
        per_layer[L] = {
            "layer": L, "rows": rows,
            "recovery": {k: (sum(v) / len(v) if v else float("nan"))
                         for k, v in rec.items()},
            "ci95": {k: bootstrap_ci(v) for k, v in rec.items()},
        }
        el = time.time() - t0
        rr = per_layer[L]["recovery"]
        print(f"    layer {L:>3}  real {rr['real']:+.3f}  "
              f"mismatched {rr['mismatched']:+.3f}  mean {rr['mean']:+.3f}"
              f"   [{n+1}/{len(layers)}, {el:.0f}s]", flush=True)

    # ---- report ------------------------------------------------------------
    with io.open(out_dir / "per_layer.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for L in layers:
            d = dict(per_layer[L])
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    curve = [per_layer[L]["recovery"]["real"] for L in layers]
    ctrl = [per_layer[L]["recovery"]["mismatched"] for L in layers]
    mcur = [per_layer[L]["recovery"]["mean"] for L in layers]
    best = max(layers, key=lambda L: per_layer[L]["recovery"]["real"])
    br = per_layer[best]["recovery"]
    bci = per_layer[best]["ci95"]["real"]

    summary = {
        "run_id": run_id, "n_items": len(items), "layers": layers,
        "mean_logprob_delta": mean_delta,
        "recovery_real": curve, "recovery_mismatched": ctrl, "recovery_mean": mcur,
        "best_layer": best, "best_recovery": br["real"],
        "best_recovery_ci95": list(bci),
        "best_layer_mismatched": br["mismatched"], "best_layer_meanvec": br["mean"],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*64}")
    print(f"  layers {layers[0]}..{layers[-1]} step {args.layer_step}, n={len(items)}")
    print(f"  real        {sparkline(curve)}")
    print(f"  mismatched  {sparkline(ctrl)}")
    print(f"  mean vector {sparkline(mcur)}")
    print(f"\n  best layer {best}: recovery {br['real']:+.3f} "
          f"CI95 [{bci[0]:+.3f}, {bci[1]:+.3f}]")
    print(f"    mismatched control at that layer: {br['mismatched']:+.3f}")
    print(f"    mean-vector       at that layer: {br['mean']:+.3f}")

    print(f"\n  reading it:")
    margin = br["real"] - br["mismatched"]
    if br["real"] > 0.5 and margin > 0.2:
        print("    Compresses into a vector, and the mismatched control does not")
        print("    reproduce it -> H2 (capability selection). Next: what does the")
        print("    vector encode? E1 attention work drops to a check.")
        if br["mean"] > br["real"] - 0.1:
            print("    The MEAN vector works about as well -- the effect is one")
            print("    global direction, not per-item content. Stronger than H2.")
    elif br["real"] < 0.2:
        print("    Does not compress at any layer -> H1 (the model keeps reading")
        print("    the skill text). Next: E1 attention knockout becomes the main line.")
    elif margin < 0.1:
        print("    Real and mismatched are close. The number is measuring the")
        print("    disturbance of patching, not the skill. Do not report recovery;")
        print("    check the Phase 0 effect size first.")
    else:
        print("    Partial recovery. Report the curve rather than a verdict, and")
        print("    run E1 -- both mechanisms are probably contributing.")
    print(f"\n  results: {out_dir}")
    print("=" * 64)


if __name__ == "__main__":
    main()
