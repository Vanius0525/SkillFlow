"""Build the four behavioural cells the whitebox work is stratified on.

    python -m howskill.cells results/p8-step --out data/cells.json

P8-WHITEBOX.md §3.2. Crossing correctness without the skill against
correctness with it gives:

    R  rescued     wrong -> right   the phenomenon to explain
    F  persistent  wrong -> wrong   the control that matters most
    K  kept        right -> right
    B  broken      right -> wrong   rare, and the only cell where the skill hurt

R against F is the core contrast: both start wrong, so task difficulty is
roughly held fixed and what differs is whether the skill took. That is an
argument about conditioning, not randomisation -- the cells are defined by an
outcome, so F may still hold the harder calculators. The `--paired` listing
exists for that: it keeps only calculators contributing to both R and F, so
the contrast can be run within calculator as well as pooled.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os

CELLS = ["R", "F", "K", "B"]
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_arm(results_dir: str, needle: str) -> dict:
    hits = [f for f in sorted(glob.glob(os.path.join(results_dir, "*.jsonl")))
            if needle in os.path.basename(f)]
    if not hits:
        raise SystemExit(f"no arm matching {needle!r} in {results_dir}")
    if len(hits) > 1:
        print(f"[warn] {needle!r} matches {[os.path.basename(h) for h in hits]}; "
              f"using {os.path.basename(hits[0])}")
    rows = {}
    with open(hits[0], encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if "error" not in r:
                rows[r["instance_id"]] = r
    return rows


def cell_of(without_ok: bool, with_ok: bool) -> str:
    if not without_ok and with_ok:
        return "R"
    if not without_ok and not with_ok:
        return "F"
    if without_ok and with_ok:
        return "K"
    return "B"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("results_dir")
    p.add_argument("--without", default="no_skill", help="arm run without a skill")
    p.add_argument("--with", dest="with_", default="gold_no_tool",
                   help="arm run with the skill")
    p.add_argument("--paired", action="store_true",
                   help="keep only calculators that contribute to both R and F")
    p.add_argument("--out", default=os.path.join(HERE, "data", "cells.json"))
    a = p.parse_args(argv)

    a0 = load_arm(a.results_dir, a.without)
    a1 = load_arm(a.results_dir, a.with_)
    shared = sorted(set(a0) & set(a1))
    if not shared:
        raise SystemExit("the two arms share no instances")

    cells: dict = {c: [] for c in CELLS}
    by_calc: dict = collections.defaultdict(lambda: collections.Counter())
    for iid in shared:
        c = cell_of(bool(a0[iid]["correct"]), bool(a1[iid]["correct"]))
        cells[c].append(iid)
        by_calc[a0[iid]["calculator_id"]][c] += 1

    if a.paired:
        keep = {c for c, cnt in by_calc.items() if cnt["R"] and cnt["F"]}
        before = {c: len(v) for c, v in cells.items()}
        cells = {c: [i for i in v if a0[i]["calculator_id"] in keep]
                 for c, v in cells.items()}
        print(f"paired: {len(keep)}/{len(by_calc)} calculators contribute to "
              f"both R and F; {before} -> "
              f"{ {c: len(v) for c, v in cells.items()} }")

    n = sum(len(v) for v in cells.values())
    print(f"{n} instances in both arms "
          f"({a.without} vs {a.with_})")
    for c in CELLS:
        print(f"  {c}  {len(cells[c]):>5}  {100*len(cells[c])/max(n,1):5.1f}%")
    small = [c for c in ("R", "F") if len(cells[c]) < 100]
    if small:
        print(f"[warn] GATE-W1 wants >=100 in R and F; short: {small}")

    json.dump({"cells": cells,
               "arms": {"without": a.without, "with": a.with_},
               "results_dir": os.path.abspath(a.results_dir),
               "paired": a.paired},
              open(a.out, "w"), indent=1)
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
