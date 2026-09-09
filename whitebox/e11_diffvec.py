#!/usr/bin/env python
"""
E11 -- is the CONTENT component of the injection sufficient on its own?

E2 replaces the receiver's last prompt-token residual with the state the model
built while reading the real skill. That state is not pure content. E7 measured
the problem directly: a neutral filler document of similar length moves the
residual about as far as the skill does, and in nearly the same direction
(cross-document cosine 0.9475, CI95 [0.9469, 0.9479] at layer 4 on Tier A).
So "the patch works" has always been confounded with "a long document is
present".

The subtraction is the obvious move and nobody had made it:

    d_i = h_yes(i) - h_fill(i)          # same item, same layer, same position
                                        # differs only in WHICH document was read

d_i is what is left of the injection after the generic component cancels. This
script adds it to the receiver's OWN state rather than replacing anything:

    h' = h_no(i) + alpha * d_i

and asks whether that fixes the items the skill fixes. A positive answer is a
much stronger claim than E2's: it says the content part is separable, additive,
and transferable -- i.e. that a reusable skill vector exists. A negative answer
with E2 still positive says the effect needs the whole state, generic part
included, which is the reading HANDOFF 12.3x already leans to ("移植的向量装的
是整段 prompt 的状态、不是文档嵌入").

CONDITIONS (all patched into the no-document prompt, last prompt position)

    none            no patch                                    lower reference
    replace_real    h' = h_yes                                  = E2's `real`,
                                                                upper reference
    add_diff        h' = h_no + a*(h_yes - h_fill)              the question
    add_diff_renorm same, then rescaled to ||h_no||             norm control (*)
    add_diff_mean   h' = h_no + a*mean_j(d_j), norm-matched     one shared
                                                                content direction
    add_diff_shift  h' = h_no + a*d_j, j = i+1 (derangement)    item specificity
    add_generic     h' = h_no + a*(h_fill - h_no)               negative control:
                                                                the part the
                                                                subtraction removed

(*) Why the renorm arm exists. h_no is a state built over a short prompt; h_yes
and h_fill are built over prompts ~700 tokens longer. Their norms are not the
same, so h_no + d can land at a norm the layer never produces, and an
off-manifold state is exactly what the mean-vector condition turned out to be
in E2 (it lifted lp(gold) by +5.4 while leaving accuracy at the no-document
baseline -- see journal/2026-09-09). Reporting the raw and renormalised arms
side by side keeps "the direction is wrong" separable from "the magnitude is
wrong". The per-layer norm ratios are printed and stored for the same reason.

READING IT

The dependent variables are the same two as E2 and they fail differently, so
both are reported: recovery of the gold logprob, and accuracy. E2 showed the
logprob channel can move without the argmax following, so accuracy on the items
the skill actually fixed is the one to read first. mass/margin is stored per
condition (mass = log P(next token is an option letter), margin = lp(gold) -
max of the other three): a uniform lift moves mass alone, choosing moves margin.

    python e11_diffvec.py --model ../models/Qwen3-1.7B \\
      --tasks tasks/tier_a/tasks.jsonl \\
      --skill tasks/tier_a/SKILL.zorb-units.md \\
      --filler tasks/filler-neutral.md --mode mc --run-id <id>/e11-tierA
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import torch

import model as M
import e2_patch as E2

HERE = pathlib.Path(__file__).resolve().parent


def sparkline(vals) -> str:
    return E2.sparkline(vals)


def bootstrap_ci(vals, n=2000, seed=0):
    return E2.bootstrap_ci(vals, n=n, seed=seed)


def norm_match(v: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """`v`'s direction at `target`'s norm, row by row."""
    return v / (v.norm(dim=-1, keepdim=True) + 1e-6) \
        * target.norm(dim=-1, keepdim=True)


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--filler", required=True,
                    help="the neutral document. REQUIRED here -- the whole "
                         "experiment is a subtraction against it.")
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--layer-step", type=int, default=1)
    ap.add_argument("--alpha", default="1.0",
                    help="comma-separated scales for the difference vector. "
                         "Every extra value costs one more forward per item "
                         "per layer, so keep the sweep short.")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    alphas = [float(a) for a in str(args.alpha).split(",") if a.strip()]
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = E2.load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    filler = M.load_skill(args.filler)
    r = M.load(args.model, device=args.device)
    layers = list(range(0, r.n_layers, args.layer_step))

    print(f"model  : {args.model}")
    print(f"tasks  : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skill  : {args.skill}")
    print(f"filler : {args.filler}")
    print(f"layers : {len(layers)} of {r.n_layers} (step {args.layer_step})")
    print(f"alpha  : {alphas}")
    print(f"run id : {run_id}")
    print()

    M.write_run_info(out_dir, r, {
        "experiment": "e11_diffvec", "run_id": run_id, "tasks": str(args.tasks),
        "skill": str(args.skill), "filler": str(args.filler), "mode": args.mode,
        "n_items": len(items), "layers": layers, "alphas": alphas,
        "dv": "answer_logprob",
    })

    # Option letters must be single tokens or the accuracy channel is undefined.
    # Checked, not assumed -- same as e2_patch.
    E2.OPTION_IDS.clear()
    if args.mode == "mc":
        for letter in "ABCD":
            t = r.tok(letter, add_special_tokens=False).input_ids
            if len(t) == 1:
                E2.OPTION_IDS[letter] = int(t[0])
        if len(E2.OPTION_IDS) != 4:
            print("  [!] option letters are not single tokens -- accuracy off.")
            E2.OPTION_IDS.clear()

    # ---- pass 1: three states per item, one forward each -------------------
    print("[1/2] baselines + three captures per item")
    base, t0 = [], time.time()
    for i, it in enumerate(items):
        q, gold, unit = E2.fields(it, args.mode)
        ids_no = M.encode(r, M.render(r, M.build_messages(q, None, args.mode, unit)))
        ids_yes = M.encode(r, M.render(r, M.build_messages(q, skill, args.mode, unit)))
        ids_fil = M.encode(r, M.render(r, M.build_messages(q, filler, args.mode, unit)))

        lp_no, ok_no, op_no = E2.score_with_patch(r, ids_no, gold)
        lp_yes, ok_yes, op_yes = E2.score_with_patch(r, ids_yes, gold)
        lp_fil, ok_fil, op_fil = E2.score_with_patch(r, ids_fil, gold)

        # k=1: the last prompt position. The three prompts have different
        # lengths; capture_block_outputs takes the last k rows, so they align
        # at the end -- which is where the question and the chat suffix are.
        v_no = M.capture_block_outputs(r, ids_no, layers, 1)
        v_yes = M.capture_block_outputs(r, ids_yes, layers, 1)
        v_fil = M.capture_block_outputs(r, ids_fil, layers, 1)

        base.append({
            "id": it["id"], "gold": gold,
            "lp_no": lp_no, "lp_yes": lp_yes, "lp_fil": lp_fil,
            "ok_no": ok_no, "ok_yes": ok_yes, "ok_fil": ok_fil,
            "opt_no": op_no, "opt_yes": op_yes, "opt_fil": op_fil,
            "delta": lp_yes - lp_no,
            "prompt_len_no": int(ids_no.shape[1]),
            "ids_no": ids_no,
            "v_no": v_no, "v_yes": v_yes, "v_fil": v_fil,
        })
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s ({el/(i+1):.1f}s/item)",
                  flush=True)

    mean_delta = sum(b["delta"] for b in base) / len(base)
    fil_delta = sum(b["lp_fil"] - b["lp_no"] for b in base) / len(base)
    acc_no = sum(1 for b in base if b["ok_no"]) / len(base)
    acc_yes = sum(1 for b in base if b["ok_yes"]) / len(base)
    acc_fil = sum(1 for b in base if b["ok_fil"]) / len(base)
    print(f"\n  logprob  no {mean_delta:+.4f} (skill)   {fil_delta:+.4f} (filler)")
    print(f"  accuracy no-doc {acc_no:.3f}   skill {acc_yes:.3f}   "
          f"filler {acc_fil:.3f}")
    if abs(mean_delta) < 1e-3:
        print("  [!] the skill barely moves the logprob -- recovery is a ratio "
              "over this number and will be noise.")

    # The mean difference direction, restored to the typical per-layer norm of
    # d. Same reasoning as e2_patch's mean_vec: a plain average of residuals is
    # short and off-manifold because the directions partly cancel.
    mean_d = {}
    for L in layers:
        stack = torch.stack([b["v_yes"][L] - b["v_fil"][L] for b in base])
        mv = stack.mean(0)
        norms = stack.norm(dim=-1).mean(0).unsqueeze(-1)
        mean_d[L] = mv / (mv.norm(dim=-1, keepdim=True) + 1e-6) * norms

    # rotate by one -- a derangement, so no item is paired with itself
    shifted = list(range(1, len(base))) + [0]

    # ---- pass 2: the sweep --------------------------------------------------
    print("\n[2/2] layer sweep")
    per_layer, t0 = {}, time.time()
    for n, L in enumerate(layers):
        rows = []
        for i, b in enumerate(base):
            pos = b["prompt_len_no"] - 1
            h_no, h_yes, h_fil = b["v_no"][L], b["v_yes"][L], b["v_fil"][L]
            d = h_yes - h_fil
            d_shift = base[shifted[i]]["v_yes"][L] - base[shifted[i]]["v_fil"][L]
            gen = h_fil - h_no

            row = {"id": b["id"], "gold": b["gold"],
                   "lp_no": b["lp_no"], "lp_yes": b["lp_yes"],
                   "lp_fil": b["lp_fil"],
                   "ok_no": b["ok_no"], "ok_yes": b["ok_yes"],
                   "ok_fil": b["ok_fil"],
                   "opt_no": b["opt_no"], "opt_yes": b["opt_yes"],
                   "donor_id": base[shifted[i]]["id"],
                   "donor_gold": base[shifted[i]]["gold"],
                   # what the subtraction is working with, at this layer
                   "norm_h_no": float(h_no.norm()),
                   "norm_h_yes": float(h_yes.norm()),
                   "norm_d": float(d.norm()),
                   "cos_d_hno": float(torch.nn.functional.cosine_similarity(
                       d.flatten().float(), h_no.flatten().float(), dim=0))}

            def put(name, vec):
                lp, ok, op = E2.score_with_patch(r, b["ids_no"], b["gold"],
                                                 L, pos, vec)
                row[f"lp_{name}"], row[f"ok_{name}"], row[f"opt_{name}"] = lp, ok, op

            put("replace_real", h_yes)
            for a in alphas:
                tag = "" if len(alphas) == 1 else f"_a{a:g}"
                put(f"add_diff{tag}", h_no + a * d)
                put(f"add_diff_renorm{tag}", norm_match(h_no + a * d, h_no))
            a0 = alphas[0]
            put("add_diff_mean", h_no + a0 * mean_d[L])
            put("add_diff_shift", h_no + a0 * d_shift)
            put("add_generic", h_no + a0 * gen)
            rows.append(row)

        conds = [k[3:] for k in rows[0] if k.startswith("lp_")
                 and k not in ("lp_no", "lp_yes", "lp_fil")]

        def recov(key):
            num = sum(r_[f"lp_{key}"] - r_["lp_no"] for r_ in rows) / len(rows)
            return num / mean_delta if abs(mean_delta) > 1e-9 else float("nan")

        def acc(key):
            v = [r_.get(f"ok_{key}") for r_ in rows]
            v = [x for x in v if x is not None]
            return sum(v) / len(v) if v else float("nan")

        per_layer[L] = {"recovery": {c: recov(c) for c in conds},
                        "accuracy": {c: acc(c) for c in conds},
                        "norm_ratio": sum(r_["norm_d"] / (r_["norm_h_no"] + 1e-9)
                                          for r_ in rows) / len(rows),
                        "cos_d_hno": sum(r_["cos_d_hno"] for r_ in rows) / len(rows)}

        with open(out_dir / f"layer_{L:02d}.jsonl", "w", encoding="utf-8") as f:
            for r_ in rows:
                f.write(json.dumps(r_, ensure_ascii=False) + "\n")

        if (n + 1) % 4 == 0 or n == len(layers) - 1:
            el = time.time() - t0
            print(f"    layer {L:3d}  " +
                  "  ".join(f"{c} {per_layer[L]['accuracy'][c]:.3f}"
                            for c in conds[:4]) +
                  f"   [{n+1}/{len(layers)}, {el:.0f}s]", flush=True)

    # ---- report -------------------------------------------------------------
    conds = list(per_layer[layers[0]]["accuracy"].keys())
    print("\n" + "=" * 78)
    print(f"  E11 difference vector   n={len(base)}")
    print("=" * 78)
    print(f"  baselines:  no doc {acc_no:.3f}   filler {acc_fil:.3f}   "
          f"skill {acc_yes:.3f}")
    print()
    head = "  layer  " + "".join(f"{c[:13]:>14}" for c in conds)
    print("  accuracy")
    print(head)
    for L in layers:
        print(f"  {L:5d}  " + "".join(
            f"{per_layer[L]['accuracy'][c]:14.3f}" for c in conds))
    print()
    print("  recovery (logprob)")
    print(head)
    for L in layers:
        print(f"  {L:5d}  " + "".join(
            f"{per_layer[L]['recovery'][c]:14.2f}" for c in conds))
    print()
    print("  ||d|| / ||h_no||   and   cos(d, h_no)   per layer")
    print("  layer   norm_ratio   cos(d,h_no)")
    for L in layers:
        print(f"  {L:5d}   {per_layer[L]['norm_ratio']:10.3f}   "
              f"{per_layer[L]['cos_d_hno']:11.3f}")

    fixed = [b["id"] for b in base if b["ok_yes"] and not b["ok_no"]]
    print(f"\n  the skill fixes {len(fixed)} items (wrong -> right).")
    print("  layer  " + "".join(f"{c[:13]:>14}" for c in conds))
    fx = set(fixed)
    for L in layers:
        rows = [json.loads(l) for l in
                open(out_dir / f"layer_{L:02d}.jsonl", encoding="utf-8")]
        rows = [r_ for r_ in rows if r_["id"] in fx]
        if not rows:
            break
        print(f"  {L:5d}  " + "".join(
            f"{sum(1 for r_ in rows if r_.get(f'ok_{c}')) / len(rows):14.3f}"
            for c in conds))
    print("\n  Read the last block first. A condition that carries the effect")
    print("  puts that column near 1.0 somewhere; add_generic near 0 is what")
    print("  says the subtraction removed the part that does not matter.")

    summary = {"experiment": "e11_diffvec", "run_id": run_id,
               "n_items": len(base), "layers": layers, "alphas": alphas,
               "acc_no": acc_no, "acc_filler": acc_fil, "acc_skill": acc_yes,
               "mean_delta_logprob": mean_delta,
               "filler_delta_logprob": fil_delta,
               "n_fixed_by_skill": len(fixed), "fixed_ids": fixed,
               "conditions": conds,
               "per_layer": {str(L): per_layer[L] for L in layers}}
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  results: {out_dir}")


if __name__ == "__main__":
    main()
