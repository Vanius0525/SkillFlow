"""Pick the deep-dive subset for P3-P5 and P7.

    python -m howskill.subset results/p2 --out data/deep_subset.json

PROTOCOL.md §1.3 fixes the rule and says it cannot be decided in advance: the
subset is chosen from P2's measured baseline, not from a guess about which
calculators are interesting.

  1. the gold skill splits into M1-M5          (P0: all 55 do)
  2. the calculator has step-level GT          (P0: 1,098/1,100 joined)
  3. the no_skill baseline is in 15-75%        -- floor and ceiling are
     excluded because an arm difference against a baseline near 0 or 100 is
     compressed into noise and the ablation reads nothing
  4. stratify by baseline and take ~20 calculators evenly across the range,
     so the subset is not all easy or all hard

Writes the calculator ids as JSON. `run.py --calculators` takes that file.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("results_dir", help="the P2 results directory")
    p.add_argument("--baseline", default="no_skill")
    p.add_argument("--lo", type=float, default=0.15)
    p.add_argument("--hi", type=float, default=0.75)
    p.add_argument("--n-calc", type=int, default=20)
    p.add_argument("--out", default=os.path.join(DATA, "deep_subset.json"))
    a = p.parse_args(argv)

    hits = [f for f in sorted(glob.glob(os.path.join(a.results_dir, "*.jsonl")))
            if a.baseline in os.path.basename(f)]
    if not hits:
        print(f"no arm matching {a.baseline!r} in {a.results_dir}")
        return 1
    rows = [json.loads(l) for l in open(hits[0], encoding="utf-8") if l.strip()]
    rows = [r for r in rows if "error" not in r]

    # stepgt.json carries calculator_id as a string ('2') while the instances
    # carry it as an int (2). Comparing them directly silently yields an empty
    # eligible set, which reads as "the task has no usable calculators".
    gt_calcs = set()
    for g in json.load(open(os.path.join(DATA, "stepgt.json"), encoding="utf-8")):
        try:
            gt_calcs.add(int(g["calculator_id"]))
        except (TypeError, ValueError):
            pass

    by_calc: dict = {}
    for r in rows:
        by_calc.setdefault(r["calculator_id"], []).append(bool(r["correct"]))
    acc = {c: sum(v) / len(v) for c, v in by_calc.items()}

    eligible = [(c, x) for c, x in sorted(acc.items(), key=lambda kv: kv[1])
                if a.lo <= x <= a.hi and c in gt_calcs]
    print(f"{len(acc)} calculators in {os.path.basename(hits[0])}; "
          f"{len(eligible)} with baseline in [{100*a.lo:.0f}%, {100*a.hi:.0f}%] "
          f"and step GT")
    if len(eligible) < a.n_calc:
        print(f"[warn] only {len(eligible)} eligible, wanted {a.n_calc} — "
              "taking all of them; report the reduced subset size")

    n = min(a.n_calc, len(eligible))
    if n == 0:
        print("[FAIL] nothing eligible. Floor/ceiling everywhere means the "
              "ablations cannot be read on this task — do not run P3.")
        return 1
    # Evenly spaced over the baseline-sorted list: stratification without
    # inventing bin edges.
    idx = [round(i * (len(eligible) - 1) / max(1, n - 1)) for i in range(n)]
    picked = [eligible[i] for i in sorted(set(idx))]

    print(f"\npicked {len(picked)} calculators "
          f"({20 * len(picked)} instances at 20/calc):")
    for c, x in picked:
        print(f"  calc {c:>3}  baseline {100*x:5.1f}%")

    json.dump([c for c, _ in picked], open(a.out, "w"), indent=1)
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
