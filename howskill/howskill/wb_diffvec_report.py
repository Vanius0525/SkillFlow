"""Read one or more wb_diffvec outputs and print the tables the paper needs.

    python -m howskill.wb_diffvec_report results/p8-wb/diffvec-cot-*.jsonl

Several files because the layer grid is split across boxes: each run repeats
pass 1 (captures and baselines are cheap next to a 900-token decode) and covers
a disjoint set of layers, so concatenating by layer is exact rather than an
approximation. Instance ids are checked for agreement before anything is merged;
a mismatch means the two runs sampled different items and the merge would be
comparing different things layer by layer.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys


def boot(vals, n_boot=4000, seed=0):
    vals = [v for v in vals if v is not None
            and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(vals)
    ms = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k
                for _ in range(n_boot))
    return sum(vals) / k, ms[int(0.025 * n_boot)], ms[int(0.975 * n_boot)]


def load(paths):
    meta, rows = {}, []
    ids_by_file = {}
    for path in paths:
        seen = set()
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("kind") == "meta":
                for L, g in (r.get("geometry") or {}).items():
                    meta[int(L)] = g
                continue
            rows.append(r)
            seen.add(r["instance_id"])
        ids_by_file[path] = seen
    sets = list(ids_by_file.values())
    if len(sets) > 1:
        common = set.intersection(*sets)
        for path, s in ids_by_file.items():
            if s != common:
                print(f"  [warn] {path} covers {len(s)} instances, "
                      f"{len(s - common)} of them not shared with the others; "
                      f"per-layer rows will not be over the same item set.",
                      file=sys.stderr)
    return meta, rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+")
    p.add_argument("--cell", default="R")
    a = p.parse_args(argv)

    meta, rows = load(a.paths)
    if not rows:
        print("no rows")
        return 1
    layers = sorted({r["layer"] for r in rows})
    cells = collections.Counter(r["cell"] for r in
                                {r["instance_id"]: r for r in rows}.values())
    print(f"files  : {len(a.paths)}   rows: {len(rows)}   layers: {layers}")
    print(f"cells  : {dict(cells)}")

    base = {r["instance_id"]: r for r in rows}
    for tag in ("none", "ctrl", "gold"):
        v = [r[f"ok_{tag}"] for r in base.values() if f"ok_{tag}" in r]
        w = [r[f"ok_{tag}"] for r in base.values()
             if f"ok_{tag}" in r and r["cell"] == a.cell]
        if v:
            print(f"  baseline {tag:5s}: all {sum(v)/len(v):.3f} (n={len(v)})"
                  f"   cell {a.cell} {sum(w)/len(w):.3f} (n={len(w)})")

    arms = sorted({k[3:] for r in rows for k in r if k.startswith("ok_")
                   and k[3:] not in ("none", "ctrl", "gold")})
    if arms:
        print(f"\n=== decoded accuracy, cell {a.cell}, mean [95% CI] ===")
        print("  L    " + "".join(f"{x[:16]:>22}" for x in arms))
        for L in layers:
            rs = [r for r in rows if r["layer"] == L and r["cell"] == a.cell]
            line = f"  {L:3d}  "
            for x in arms:
                v = [1.0 if r.get(f"ok_{x}") else 0.0 for r in rs
                     if f"ok_{x}" in r]
                if not v:
                    line += f"{'-':>22}"
                    continue
                m, lo, hi = boot(v, seed=L)
                line += f"{m:8.3f} [{lo:.2f},{hi:.2f}]"
            print(line)

    lparms = sorted({k[3:] for r in rows for k in r if k.startswith("lp_")
                     and k[3:] not in ("none", "ctrl", "gold")})
    print("\n=== mean lp(answer) per arm (reported, not read first) ===")
    print("  L    " + "".join(f"{x[:14]:>16}" for x in ["none", "ctrl", "gold"] + lparms))
    for L in layers:
        rs = [r for r in rows if r["layer"] == L]
        line = f"  {L:3d}  "
        for x in ["none", "ctrl", "gold"] + lparms:
            v = [r[f"lp_{x}"] for r in rs if f"lp_{x}" in r]
            line += f"{(sum(v)/len(v) if v else float('nan')):16.3f}"
        print(line)

    if meta:
        keys = ["norm_d", "norm_g", "norm_t", "ratio_d_over_t", "cos_d_g",
                "cos_dd_same_calc", "cos_dd_cross_calc", "pr_d_centred"]
        print("\n=== geometry ===")
        print("  L  " + "".join(f"{k[:14]:>16}" for k in keys))
        for L in sorted(meta):
            g = meta[L]
            print(f"  {L:3d}" + "".join(f"{g.get(k, float('nan')):16.3f}"
                                        for k in keys))
        print("\n=== geometry by cell (||d||, ||g||, cos(d,g)) ===")
        cellnames = sorted({k.split("_")[-1] for g in meta.values()
                            for k in g if k.startswith("norm_d_")})
        for L in sorted(meta):
            g = meta[L]
            parts = []
            for c in cellnames:
                parts.append(f"{c}: |d| {g.get(f'norm_d_{c}', float('nan')):7.1f} "
                             f"|g| {g.get(f'norm_g_{c}', float('nan')):7.1f} "
                             f"cos {g.get(f'cos_d_g_{c}', float('nan')):+.3f}")
            print(f"  {L:3d}  " + "   ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
