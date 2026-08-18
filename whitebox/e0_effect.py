#!/usr/bin/env python3
"""
Phase 0: does the skill produce an effect worth explaining?

Nothing downstream runs until this passes. If the skill moves accuracy by a few
points, that difference sits inside sampling noise and every mechanistic measure
built on it is explaining noise -- see HANDOFF-whitebox.md section 2.

Reports both dependent variables:

  accuracy   readable, but binary and coarse
  logprob    mean log-probability of the gold answer; per-item, continuous, much
             lower variance. This is the primary DV. A skill can shift it
             consistently while accuracy barely moves, and the patching
             experiments can still be run against it.

Paired throughout: the same items under both conditions, so item difficulty
cancels. The bootstrap resamples items, not conditions.

    # Tier A, the positive control
    python e0_effect.py --model Qwen/Qwen3-1.7B \
        --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
        --mode mc --run-id tierA-1.7b

    # Tier B
    python e0_effect.py --model Qwen/Qwen3-8B \
        --tasks tasks/tier_b/tasks.jsonl --skill tasks/tier_b/SKILL.pchem-constants.md \
        --mode num --limit 120 --run-id tierB-const-8b

    # drop the items the model already answers correctly with no skill, and
    # write a filtered task file for the mechanistic experiments to use
    python e0_effect.py ... --filter-known tasks/tier_b/tasks.filtered.jsonl
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
    """Tier A carries both formats; Tier B is numeric only."""
    if "question_mc" in item:
        return (item["question_mc"], item["answer_mc"], None) if mode == "mc" \
            else (item["question_num"], item["answer_num"], None)
    return item["question"], item["answer_raw"], item.get("unit") or None


def run_condition(r, items, skill, mode, max_new):
    out = []
    t0 = time.time()
    for i, it in enumerate(items):
        q, gold, unit = fields(it, mode)
        ids = M.encode(r, M.render(r, M.build_messages(q, skill, mode, unit)))
        text = M.generate(r, ids, max_new_tokens=max_new)
        lp = M.answer_logprob(r, ids, gold)

        if mode == "mc":
            ok = M.extract_mc(text) == gold
        else:
            ok = M.num_correct(M.extract_num(text), float(gold))

        out.append({"id": it["id"], "correct": bool(ok), "logprob": lp,
                    "raw": text.strip()[:200], "gold": gold,
                    "n_prompt_tokens": int(ids.shape[1])})
        if (i + 1) % 20 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s  "
                  f"({el/(i+1):.1f}s/item)", flush=True)
    return out


def paired_bootstrap(a, b, n=5000, seed=0):
    """CI for mean(b) - mean(a), resampling items. Returns (lo, hi) at 95%."""
    rng = random.Random(seed)
    k = len(a)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(k) for _ in range(k)]
        diffs.append(sum(b[i] - a[i] for i in idx) / k)
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--filter-known", metavar="OUT_JSONL", default=None,
                    help="write a task file with the no-skill-correct items removed")
    args = ap.parse_args()

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id

    items = load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    print(f"model    : {args.model}")
    print(f"tasks    : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skill    : {args.skill}  ({len(skill.split())} words)")
    print(f"run id   : {run_id}\n")

    r = M.load(args.model, device=args.device)
    M.write_run_info(out_dir, r, {
        "run_id": run_id, "tasks": str(args.tasks), "skill": str(args.skill),
        "mode": args.mode, "n_items": len(items), "decoding": "greedy",
    })
    print("structure:", json.dumps(r.describe(), ensure_ascii=False), "\n")

    print("[1/2] without skill")
    no = run_condition(r, items, None, args.mode, args.max_new_tokens)
    print("[2/2] with skill")
    yes = run_condition(r, items, skill, args.mode, args.max_new_tokens)

    acc_no = sum(x["correct"] for x in no) / len(no)
    acc_yes = sum(x["correct"] for x in yes) / len(yes)
    lp_no = [x["logprob"] for x in no]
    lp_yes = [x["logprob"] for x in yes]

    c_no = [float(x["correct"]) for x in no]
    c_yes = [float(x["correct"]) for x in yes]
    acc_lo, acc_hi = paired_bootstrap(c_no, c_yes)
    lp_lo, lp_hi = paired_bootstrap(lp_no, lp_yes)

    # McNemar counts: the discordant pairs are the whole evidence in a paired design
    b = sum(1 for x, y in zip(no, yes) if not x["correct"] and y["correct"])
    c = sum(1 for x, y in zip(no, yes) if x["correct"] and not y["correct"])

    with io.open(out_dir / "per_item.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x, y in zip(no, yes):
            f.write(json.dumps({"id": x["id"], "gold": x["gold"],
                                "no_skill": x, "with_skill": y},
                               ensure_ascii=False) + "\n")

    d_acc = (acc_yes - acc_no) * 100
    d_lp = sum(lp_yes) / len(lp_yes) - sum(lp_no) / len(lp_no)
    summary = {
        "run_id": run_id, "n": len(items),
        "acc_no_skill": acc_no, "acc_with_skill": acc_yes,
        "delta_acc_pp": d_acc,
        "delta_acc_ci95_pp": [acc_lo * 100, acc_hi * 100],
        "mean_logprob_no_skill": sum(lp_no) / len(lp_no),
        "mean_logprob_with_skill": sum(lp_yes) / len(lp_yes),
        "delta_logprob": d_lp, "delta_logprob_ci95": [lp_lo, lp_hi],
        "mcnemar_gained": b, "mcnemar_lost": c,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*64}")
    print(f"  n = {len(items)}")
    print(f"  accuracy   {acc_no:.3f} -> {acc_yes:.3f}   "
          f"delta {d_acc:+.1f}pp  CI95 [{acc_lo*100:+.1f}, {acc_hi*100:+.1f}]")
    print(f"  logprob    {summary['mean_logprob_no_skill']:.3f} -> "
          f"{summary['mean_logprob_with_skill']:.3f}   "
          f"delta {d_lp:+.3f}  CI95 [{lp_lo:+.3f}, {lp_hi:+.3f}]")
    print(f"  discordant gained {b}, lost {c}")
    print(f"{'='*64}")

    # gate, per HANDOFF-whitebox.md section 2
    acc_gate = d_acc >= 15 and acc_lo * 100 > 5
    lp_gate = d_acc >= 5 and lp_lo > 0
    if acc_gate:
        print("  GATE PASSED on accuracy. Proceed.")
    elif lp_gate:
        print("  GATE PASSED on logprob (accuracy delta is modest but the")
        print("  logprob shift is consistent). Use logprob as the DV downstream.")
    else:
        print("  GATE NOT PASSED.")
        print("  Try another task/skill pair. After four consecutive pairs below")
        print("  10pp, switch to the bottleneck question -- HANDOFF-whitebox.md")
        print("  section 6 step 3.")
    print(f"  results: {out_dir}")

    if args.filter_known:
        keep_ids = {x["id"] for x in no if not x["correct"]}
        src = load_tasks(args.tasks)
        kept = [it for it in src if it["id"] in keep_ids]
        with io.open(args.filter_known, "w", encoding="utf-8", newline="\n") as f:
            for it in kept:
                f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"\n  filtered task file: {args.filter_known}")
        print(f"  kept {len(kept)}/{len(src)} (dropped the ones already correct "
              f"with no skill -- they cannot show an effect)")


if __name__ == "__main__":
    main()
