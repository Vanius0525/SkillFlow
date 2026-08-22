#!/usr/bin/env python3
"""
Read an e6 run's per_item.jsonl and answer the question the generated answers
could not: under the counterfactual skill, which value does the model prefer?

Why this exists. e6_counterfactual.py's headline number is the follow rate, and
its denominator is "items that answered one of the two values". On the first
Tier A run that denominator was zero: 100% neither, 0% unparsed. A follow rate
of nan has two readings that point in opposite directions --

  (a) the conflict is disorganising the computation                   -> H5
  (b) extract_num is not returning the model's answer                 -> nothing

-- and no summary statistic separates them, because both produce the same
number. Only the raw generations do, so this prints them.

It also recomputes the follow rate from lp_true / lp_cf, which e6 already
records per item. Those come from answer_logprob, so they need no extraction at
all: whatever the generated text looks like, the model either puts more mass on
the counterfactual value or it does not. When (b) is what happened, this is the
measurement that survives it.

Pure post-processing, like errors.py: no GPU, no model, no torch.

    python e6_diagnose.py results/<run-id>/e6-tierA
    python e6_diagnose.py results/<run-id>/e6-tierA --show 12
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys

CONDS = ("no_skill", "true", "cf")


def load(run_dir: pathlib.Path) -> list[dict]:
    p = run_dir / "per_item.jsonl"
    if not p.is_file():
        print(f"[FAIL] no per_item.jsonl in {run_dir}")
        sys.exit(1)
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--show", type=int, default=6,
                    help="how many items to print raw generations for")
    ap.add_argument("--tasks", default=str(pathlib.Path(__file__).parent /
                                           "tasks" / "tier_a" / "tasks.jsonl"),
                    help="joined on id, to name the quantity from the question")
    args = ap.parse_args()

    rows = load(pathlib.Path(args.run_dir))
    n = len(rows)
    print(f"n = {n}   from {args.run_dir}\n")

    # The quantity in the question is a named hypothesis, not "something else":
    # errors.py reported wrong_row at 85% with no skill on this task set, and
    # the wrong row that needs no table is the one that leaves the number
    # unchanged. In MC that shows up as a distractor; in num mode the model has
    # nothing to snap to, so an echo lands on a value neither gold matches.
    quantity = {}
    tp = pathlib.Path(args.tasks)
    if tp.is_file():
        for line in io.open(tp, encoding="utf-8"):
            if line.strip():
                t = json.loads(line)
                quantity[t["id"]] = t["value"]

    # ---- 1. the raw generations -------------------------------------------
    #
    # Printed before any statistic. If the model is answering in prose, the
    # first number in the completion is a step of the arithmetic rather than
    # the answer, and every rate below is describing the regex.
    print("=" * 72)
    print(" raw generations   (gold: true -> cf)")
    print("=" * 72)
    for row in rows[:args.show]:
        print(f"\n  {row['id']}   {row['unit']} {row['orig_factor']} -> "
              f"{row['new_factor']}   answer {row['gold_true']} -> {row['gold_cf']}")
        for c in CONDS:
            d = row[c]
            print(f"    {c:<9} pred={str(d['pred']):<10} {d['follows']:<9} "
                  f"| {d['raw']!r}")

    # ---- 2. does the first number equal something we can name? ------------
    #
    # The two failure modes leave different fingerprints. Echoing the quantity
    # from the question is a real (and already observed) behaviour; emitting a
    # factor from the table is the model showing its work, and means the regex
    # took a number out of the middle of a sentence.
    print("\n" + "=" * 72)
    print(" what the extracted number actually was")
    print("=" * 72)
    for c in CONDS:
        tally: dict[str, int] = {}
        for row in rows:
            pred = row[c]["pred"]
            if pred is None:
                k = "none"
            elif near(pred, row["gold_true"]):
                k = "gold_true"
            elif near(pred, row["gold_cf"]):
                k = "gold_cf"
            elif near(pred, row["orig_factor"]):
                k = "the original factor"
            elif near(pred, row["new_factor"]):
                k = "the counterfactual factor"
            elif row["id"] in quantity and near(pred, quantity[row["id"]]):
                k = "the quantity in the question (echo)"
            else:
                k = "something else"
            tally[k] = tally.get(k, 0) + 1
        line = "  ".join(f"{k} {v}({v/n:.0%})" for k, v in
                         sorted(tally.items(), key=lambda kv: -kv[1]))
        print(f"  {c:<9} {line}")

    # ---- 3. the follow rate that needs no extraction -----------------------
    print("\n" + "=" * 72)
    print(" follow rate from logprobs   (no answer extraction involved)")
    print("=" * 72)
    print(f"  {'condition':<10} {'prefers cf':>11} {'prefers true':>13} "
          f"{'mean lp(cf)-lp(true)':>22}")
    for c in CONDS:
        pref_cf = sum(1 for r in rows if r[c]["lp_cf"] > r[c]["lp_true"])
        gap = sum(r[c]["lp_cf"] - r[c]["lp_true"] for r in rows) / n
        print(f"  {c:<10} {pref_cf/n:>10.1%} {(n-pref_cf)/n:>12.1%} "
              f"{gap:>+22.3f}")

    swing = (sum(r["cf"]["lp_cf"] - r["cf"]["lp_true"] for r in rows) / n
             - sum(r["true"]["lp_cf"] - r["true"]["lp_true"] for r in rows) / n)
    print(f"\n  swing (cf condition - true condition): {swing:+.3f}")
    print("\n  reading it:")
    if swing > 0.5:
        print("    Swapping one factor in the document moves the model toward the")
        print("    value that factor implies. It is reading that row -- H1 -- and")
        print("    the generated answers are what failed, not the mechanism.")
    elif swing < -0.5:
        print("    The model moves AWAY from the counterfactual value when shown")
        print("    it. That is not 'ignoring the table'; check the two documents")
        print("    really differ only in the factor (render_skill.py --check).")
    else:
        print("    Changing the factor barely moves the preference either way.")
        print("    The model is not reading that row: whatever the skill is doing")
        print("    here, it is not supplying this number. Cross-check against E1 --")
        print("    a real attention peak on the skill span would contradict this.")


def near(pred: float | None, gold, rel_tol: float = 0.02) -> bool:
    """Same tolerance model.num_correct uses, so labels here match the run's."""
    if pred is None:
        return False
    g = float(gold)
    if g == 0:
        return abs(pred) < 1e-9
    return abs(pred - g) / abs(g) <= rel_tol


if __name__ == "__main__":
    main()
