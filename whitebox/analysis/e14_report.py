#!/usr/bin/env python3
"""Read an e14_decomp run and print the tables the paper needs.

    python e14_report.py <run_dir>            # e.g. ../results/20260910-e14/e14-tierA-mc-1.7B-fp32
    python e14_report.py <run_dir> --latex    # the same, as booktabs bodies

Three readings, in the order they should be read:

  1. accuracy on the R cell   the count channel, the only one with a
                              behavioural referent (HANDOFF-whitebox.md 12.3ab
                              section 7 shows what happens when it is skipped)
  2. geometry per layer       norms, angles, cross-item cosines, effective rank
  3. logprob per layer        reported, never read first

Confidence intervals are a nonparametric bootstrap over items. On a proportion
of 40-60 items they are wide; that is the honest width, and quoting a peak
without one is how a curve with no shape gets published as a curve with shape.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random


def boot_ci(vals, n_boot=4000, seed=0):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    m = sum(vals) / len(vals)
    ms = []
    k = len(vals)
    for _ in range(n_boot):
        ms.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    ms.sort()
    return m, ms[int(0.025 * n_boot)], ms[int(0.975 * n_boot)]


def load(run_dir: pathlib.Path):
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    layers = summary["layers"]
    per_layer_rows = {}
    for L in layers:
        p = run_dir / f"layer_{L:02d}.jsonl"
        if p.exists():
            per_layer_rows[L] = [json.loads(x) for x in
                                 p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return summary, per_layer_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--cell", default="R")
    ap.add_argument("--conds", default=None,
                    help="comma-separated subset, in the order you want them")
    ap.add_argument("--latex", action="store_true")
    args = ap.parse_args()

    run = pathlib.Path(args.run_dir)
    summary, rows = load(run)
    layers = [L for L in summary["layers"] if L in rows]
    conds = (args.conds.split(",") if args.conds else summary["conditions"])
    cells = summary.get("cells", {})

    print(f"run       : {run}")
    print(f"n items   : {summary['n_items']}   layers: {len(layers)}")
    print(f"baselines : no-doc {summary['acc_no']:.3f}   filler "
          f"{summary['acc_filler']:.3f}   skill {summary['acc_skill']:.3f}")
    print(f"logprob   : skill-no {summary['mean_delta_logprob']:+.4f}   "
          f"filler-no {summary['filler_delta_logprob']:+.4f}")
    print("cells     : " + "  ".join(f"{c}={len(cells.get(c, []))}" for c in "RFKB"))
    print()

    keep = set(cells.get(args.cell, []))
    print(f"=== accuracy on cell {args.cell} (n={len(keep)}), mean [95% CI] ===")
    hdr = "  L    " + "".join(f"{c[:16]:>22}" for c in conds)
    print(hdr)
    for L in layers:
        rs = [r for r in rows[L] if r["id"] in keep]
        line = f"  {L:3d}  "
        for c in conds:
            v = [1.0 if r.get(f"ok_{c}") else 0.0 for r in rs if f"lp_{c}" in r
                 and r.get(f"ok_{c}") is not None]
            if not v:
                line += f"{'-':>22}"
                continue
            m, lo, hi = boot_ci(v, seed=L)
            line += f"{m:8.3f} [{lo:.2f},{hi:.2f}]"
        print(line)

    print(f"\n=== accuracy, all {summary['n_items']} items ===")
    print(hdr.replace("[95% CI]", ""))
    for L in layers:
        line = f"  {L:3d}  "
        for c in conds:
            v = [1.0 if r.get(f"ok_{c}") else 0.0 for r in rows[L]
                 if f"lp_{c}" in r and r.get(f"ok_{c}") is not None]
            line += f"{(sum(v)/len(v) if v else float('nan')):22.3f}"
        print(line)

    print("\n=== geometry ===")
    g0 = summary["per_layer"][str(layers[0])]["geometry"]
    keys = [k for k in ("norm_d", "norm_g", "norm_t", "ratio_d_over_t",
                        "cos_d_g", "cos_dd_within_family", "cos_dd_cross_family",
                        "pr_d_centred", "pr_g_centred", "frac_d_on_mean") if k in g0]
    print("  L  " + "".join(f"{k[:12]:>14}" for k in keys))
    for L in layers:
        g = summary["per_layer"][str(L)]["geometry"]
        print(f"  {L:3d}" + "".join(f"{g[k]:14.3f}" for k in keys))

    print("\n=== mean lp(gold) per condition ===")
    print("  L  " + "".join(f"{c[:12]:>14}" for c in conds))
    for L in layers:
        line = f"  {L:3d}"
        for c in conds:
            v = [r[f"lp_{c}"] for r in rows[L] if f"lp_{c}" in r]
            line += f"{(sum(v)/len(v) if v else float('nan')):14.3f}"
        print(line)

    if args.latex:
        print("\n=== LaTeX: R-cell accuracy ===")
        for L in layers:
            rs = [r for r in rows[L] if r["id"] in keep]
            cellstr = []
            for c in conds:
                v = [1.0 if r.get(f"ok_{c}") else 0.0 for r in rs
                     if r.get(f"ok_{c}") is not None]
                cellstr.append(f"{sum(v)/len(v):.3f}" if v else "---")
            print(f"{L} & " + " & ".join(cellstr) + r" \\")


if __name__ == "__main__":
    main()
