#!/usr/bin/env python3
"""Compare e14 runs that differ only in which document was subtracted.

    python e14_fillers.py neutral=<dir> shuffled=<dir> corrupted=<dir>

The decomposition is defined by a control document, so its conclusions are
conditional on that document. Three controls, tightening in what they hold
fixed:

  neutral    an unrelated text of similar length   -> d = "this is about units"
  shuffled   the same lines, scrambled             -> d = "the document is coherent"
  corrupted  the same table, different factors     -> d = "the factors are THESE"

If the R-cell curve for `add_d` survives all three, the content component is the
factors and not the topic. If it survives only against `neutral`, it is the
topic, and the paper's central claim has to be narrowed to say so.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random


def boot(v, seed=0, n=4000):
    v = [x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not v:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(v)
    ms = sorted(sum(v[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return sum(v) / k, ms[int(0.025 * n)], ms[int(0.975 * n)]


def load(run: pathlib.Path):
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rows = {}
    for L in summary["layers"]:
        p = run / f"layer_{L:02d}.jsonl"
        if p.exists():
            rows[L] = [json.loads(x) for x in
                       p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return summary, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", help="tag=run_dir")
    ap.add_argument("--conds", default="replace_real,add_d_a1,add_g,add_dbar,"
                                       "add_d_samefam,add_d_crossfam")
    ap.add_argument("--cell", default="R")
    a = ap.parse_args()

    runs = {}
    for spec in a.specs:
        tag, _, path = spec.partition("=")
        runs[tag] = load(pathlib.Path(path))

    print("baselines and cell sizes")
    for tag, (sm, _) in runs.items():
        cells = sm.get("cells", {})
        print(f"  {tag:10s} no {sm['acc_no']:.3f}  filler {sm['acc_filler']:.3f}"
              f"  skill {sm['acc_skill']:.3f}   "
              + " ".join(f"{c}={len(cells.get(c, []))}" for c in "RFKB"))

    conds = [c for c in a.conds.split(",") if c]
    for cond in conds:
        print(f"\n=== {cond}: fraction of cell {a.cell} correct ===")
        tags = list(runs)
        print("  L    " + "".join(f"{t[:18]:>22}" for t in tags))
        layers = sorted(set.intersection(*[set(r[1]) for r in runs.values()]))
        for L in layers:
            line = f"  {L:3d}  "
            for t in tags:
                sm, rows = runs[t]
                keep = set(sm["cells"][a.cell])
                v = [1.0 if r.get(f"ok_{cond}") else 0.0 for r in rows[L]
                     if r["id"] in keep and r.get(f"ok_{cond}") is not None]
                if not v:
                    line += f"{'-':>22}"
                    continue
                m, lo, hi = boot(v, seed=L)
                line += f"{m:8.3f} [{lo:.2f},{hi:.2f}]"
            print(line)

    print("\n=== geometry: ||d|| / ||g|| and cos(d,g) ===")
    tags = list(runs)
    layers = sorted(set.intersection(*[set(map(int, r[0]["per_layer"]))
                                       for r in runs.values()]))
    print("  L    " + "".join(f"{t[:20]:>26}" for t in tags))
    for L in layers:
        line = f"  {L:3d}  "
        for t in tags:
            g = runs[t][0]["per_layer"][str(L)]["geometry"]
            line += (f"  |d|{g['norm_d']:8.1f} |g|{g['norm_g']:8.1f}"
                     f" cos{g['cos_d_g']:+.2f}")
        print(line)


if __name__ == "__main__":
    main()
