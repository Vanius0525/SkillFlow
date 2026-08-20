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
    ap.add_argument("--tail-k", type=int, default=1,
                    help="patch the last K prompt positions instead of only the "
                         "last one. A low recovery at K=1 can mean the effect does "
                         "not compress, or just that one position is too small a "
                         "container; K>1 tells those apart")
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
    print(f"patch  : last {args.tail_k} prompt position"
          f"{'s' if args.tail_k > 1 else ''}")
    print(f"run id : {run_id}\n")
    M.write_run_info(out_dir, r, {
        "experiment": "e2_patch", "run_id": run_id, "tasks": str(args.tasks),
        "skill": str(args.skill), "mode": args.mode, "n_items": len(items),
        "layers": layers, "dv": "answer_logprob", "tail_k": args.tail_k,
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
        # hidden_states[L+1] is the output of layer L; the last K prompt tokens.
        # The two prompts differ in length, so the positions are aligned from the
        # END -- the question and the chat suffix line up there, the skill block
        # does not line up anywhere.
        k = args.tail_k
        vecs = {L: cap.hidden_states[L + 1][0, -k:].detach().clone() for L in layers}
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

    # Mean vector per layer, rescaled to the typical norm at that layer.
    #
    # A plain mean is not a usable residual state. Norms grow with depth and the
    # directions partly cancel, so the average is short and off-manifold; the
    # first run of this produced "recovery" of -136 at late layers, which is not
    # a control failing to recover but a forward pass being destroyed. Keeping
    # the mean DIRECTION and restoring a plausible MAGNITUDE makes the condition
    # answer the question it was meant to ask: is one shared direction enough?
    mean_vec = {}
    for L in layers:
        stack = torch.stack([b["vecs"][L] for b in base])       # [n, k, d]
        mv = stack.mean(0)                                      # [k, d]
        norms = stack.norm(dim=-1).mean(0).unsqueeze(-1)        # [k, 1]
        mean_vec[L] = mv / (mv.norm(dim=-1, keepdim=True) + 1e-6) * norms
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
            # last K PROMPT tokens, absolute indices into prompt+answer
            pos = list(range(b["prompt_len_no"] - args.tail_k, b["prompt_len_no"]))
            real = logprob_with_patch(r, b["ids_no"], b["gold"], L, pos, b["vecs"][L])
            mism = logprob_with_patch(r, b["ids_no"], b["gold"], L, pos,
                                      base[shifted[i]]["vecs"][L])
            meanp = logprob_with_patch(r, b["ids_no"], b["gold"], L, pos, mean_vec[L])
            rows.append({"id": b["id"], "lp_real": real, "lp_mismatched": mism,
                         "lp_mean": meanp, "lp_no": b["lp_no"], "lp_yes": b["lp_yes"]})

        # Ratio of MEANS, not the mean of per-item ratios.
        #
        # Per item the denominator is that item's own skill effect, which can be
        # near zero, so one item with a tiny denominator and a large numerator
        # dominates the average. Aggregating first is the standard form in the
        # patching literature and is bounded by the data rather than by the
        # smallest denominator in it.
        def recov(key):
            num = sum(x[key] - x["lp_no"] for x in rows) / len(rows)
            den = sum(x["lp_yes"] - x["lp_no"] for x in rows) / len(rows)
            return num / den if abs(den) > 1e-6 else float("nan")

        def recov_boot(key, n=2000, seed=0):
            rng = random.Random(seed)
            k = len(rows)
            out = []
            for _ in range(n):
                s = [rows[rng.randrange(k)] for _ in range(k)]
                num = sum(x[key] - x["lp_no"] for x in s) / k
                den = sum(x["lp_yes"] - x["lp_no"] for x in s) / k
                if abs(den) > 1e-6:
                    out.append(num / den)
            out.sort()
            return (out[int(0.025 * len(out))], out[int(0.975 * len(out))]) if out \
                else (float("nan"), float("nan"))

        # An injected vector can push the forward pass off-manifold entirely, and
        # a logprob of -800 is a broken run rather than a low score. Counting them
        # keeps that distinct from "this condition recovers little".
        def destroyed(key):
            return sum(1 for x in rows if x[key] < x["lp_no"] - 20)

        keys = ("real", "mismatched", "mean")
        per_layer[L] = {
            "layer": L, "rows": rows,
            "recovery": {k: recov(f"lp_{k}") for k in keys},
            "ci95": {k: recov_boot(f"lp_{k}") for k in keys},
            "destroyed": {k: destroyed(f"lp_{k}") for k in keys},
        }
        el = time.time() - t0
        rr = per_layer[L]["recovery"]
        dd = per_layer[L]["destroyed"]
        broke = "".join(f" [{k[:4]}:{dd[k]} broken]" for k in dd if dd[k])
        print(f"    layer {L:>3}  real {rr['real']:+.3f}  "
              f"mismatched {rr['mismatched']:+.3f}  mean {rr['mean']:+.3f}"
              f"{broke}   [{n+1}/{len(layers)}, {el:.0f}s]", flush=True)

    # ---- report ------------------------------------------------------------
    with io.open(out_dir / "per_layer.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for L in layers:
            d = dict(per_layer[L])
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    curve = [per_layer[L]["recovery"]["real"] for L in layers]
    ctrl = [per_layer[L]["recovery"]["mismatched"] for L in layers]
    mcur = [per_layer[L]["recovery"]["mean"] for L in layers]
    # Exclude the final layers from "best layer".
    #
    # Patching the last layer at the last prompt token overwrites the state that
    # directly produces the next token, so for a single-token answer the recovery
    # is high by construction rather than by finding anything. The first Tier A
    # run scored +1.465 there -- above 100% -- with the MISMATCHED control also at
    # +0.799, which is the tell: another item's vector should not help, and does
    # only because the position is degenerate. Reported separately below.
    TAIL = 2
    candidates = layers[:-TAIL] if len(layers) > TAIL + 2 else layers
    best = max(candidates, key=lambda L: per_layer[L]["recovery"]["real"])
    br = per_layer[best]["recovery"]
    bci = per_layer[best]["ci95"]["real"]
    tail_layers = [L for L in layers if L not in candidates]

    summary = {
        "run_id": run_id, "n_items": len(items), "layers": layers,
        "tail_k": args.tail_k,
        "mean_logprob_delta": mean_delta,
        "recovery_real": curve, "recovery_mismatched": ctrl, "recovery_mean": mcur,
        "best_layer": best, "best_recovery": br["real"],
        "best_recovery_ci95": list(bci),
        "best_layer_mismatched": br["mismatched"], "best_layer_meanvec": br["mean"],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*64}")
    print(f"  layers {layers[0]}..{layers[-1]} step {args.layer_step}, "
          f"n={len(items)}, K={args.tail_k}")
    print(f"  real        {sparkline(curve)}")
    print(f"  mismatched  {sparkline(ctrl)}")
    print(f"  mean vector {sparkline(mcur)}")
    print(f"\n  best layer {best} (final {len(tail_layers)} excluded): "
          f"recovery {br['real']:+.3f} CI95 [{bci[0]:+.3f}, {bci[1]:+.3f}]")
    print(f"    mismatched control at that layer: {br['mismatched']:+.3f}")
    print(f"    mean-vector       at that layer: {br['mean']:+.3f}")
    if tail_layers:
        print(f"    excluded (degenerate: overwrites the state that emits the "
              f"answer token):")
        for L in tail_layers:
            rr = per_layer[L]["recovery"]
            print(f"      layer {L}: real {rr['real']:+.3f}  "
                  f"mismatched {rr['mismatched']:+.3f}")

    # A layer where the mismatched control also recovers is not evidence of
    # anything: it means patching that position helps regardless of content.
    degenerate = [L for L in candidates
                  if per_layer[L]["recovery"]["mismatched"] > 0.4]
    if degenerate:
        print(f"\n  [!] mismatched also recovers > 0.4 at layers {degenerate}. "
              f"Patching there\n      helps whatever vector is used, so those "
              f"layers carry no information about the skill.")

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
        if args.tail_k == 1:
            print("    Before concluding that: re-run with --tail-k 4. One position")
            print("    is a container size this script chose, not one the model did,")
            print("    and 'does not fit in one vector' is a weaker claim than 'does")
            print("    not compress'.")
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
