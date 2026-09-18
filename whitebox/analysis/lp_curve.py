#!/usr/bin/env python3
"""Per-layer decomposition of the gold-answer logprob channel (Tier A, E2).

Answers the standing question "why do the CONTROL patches score higher on
lp(gold) than the real one?" by taking the aggregate apart three ways:

  1. mean vs median          -- is the aggregate driven by a deep tail?
  2. entropy over the four   -- is the winner flattening the distribution
     option letters             rather than choosing?
  3. difficulty tercile      -- where in the item set does the lift come from,
     (split on lp_no, which     and does that stratum have any accuracy to give?
     never sees the compared
     quantity)
Usage: python lp_curve.py <run_dir>/e2-tierA/per_layer.jsonl
"""
import json, math, sys, statistics as st

path = sys.argv[1] if len(sys.argv) > 1 else \
    "../results/20260909-130000/e2-tierA/per_layer.jsonl"
layers = [json.loads(l) for l in open(path, encoding="utf-8")]

CONDS = ["real", "mismatched", "mean", "filler", "no", "yes"]


def entropy(opt):
    lps = [v for k, v in opt.items() if k != "_best"]
    ps = [math.exp(x) for x in lps]
    s = sum(ps)
    if s <= 0:
        return float("nan")
    ps = [p / s for p in ps]
    return -sum(p * math.log(p + 1e-12) for p in ps)


print(f"file: {path}   layers: {len(layers)}   n items: {len(layers[0]['rows'])}")
print()
print("per-layer MEAN lp(gold)   [yes/no are layer-independent references]")
hdr = "  L  " + "".join(f"{c:>12}" for c in CONDS) + "   acc_real acc_mean acc_mis"
print(hdr)
for rec in layers:
    rows = rec["rows"]
    line = f"{rec['layer']:3d}  "
    for c in CONDS:
        vals = [r[f"lp_{c}"] for r in rows if f"lp_{c}" in r]
        line += f"{st.mean(vals):12.3f}" if vals else f"{'-':>12}"
    for c in ("real", "mean", "mismatched"):
        v = [r.get(f"ok_{c}") for r in rows]
        v = [x for x in v if x is not None]
        line += f"{sum(v)/len(v):9.3f}" if v else "        -"
    print(line)

print()
print("MEDIAN lp(gold)  (same table, median instead of mean)")
print("  L  " + "".join(f"{c:>12}" for c in CONDS))
for rec in layers:
    rows = rec["rows"]
    line = f"{rec['layer']:3d}  "
    for c in CONDS:
        vals = [r[f"lp_{c}"] for r in rows if f"lp_{c}" in r]
        line += f"{st.median(vals):12.3f}" if vals else f"{'-':>12}"
    print(line)

print()
print("ENTROPY over the four option letters (max ln4 = 1.386)")
print("  L  " + "".join(f"{c:>12}" for c in CONDS))
for rec in layers:
    rows = rec["rows"]
    line = f"{rec['layer']:3d}  "
    for c in CONDS:
        vals = [entropy(r[f"opt_{c}"]) for r in rows if f"opt_{c}" in r]
        line += f"{st.mean(vals):12.4f}" if vals else f"{'-':>12}"
    print(line)

print()
print("DIFFICULTY TERCILES (split by lp_no; the split never sees the compared quantity)")
rows0 = layers[0]["rows"]
order = sorted(rows0, key=lambda r: r["lp_no"])
n = len(order)
hard = {r["id"] for r in order[:n // 3]}
mid = {r["id"] for r in order[n // 3: 2 * n // 3]}
easy = {r["id"] for r in order[2 * n // 3:]}
print(f"  hard n={len(hard)}  mid n={len(mid)}  easy n={len(easy)}")
for name, grp in (("hard", hard), ("mid", mid), ("easy", easy)):
    print(f"\n  --- {name} ---")
    print("  L  " + "".join(f"{c:>12}" for c in CONDS) +
          "   acc_real acc_mean  acc_yes acc_no")
    for rec in layers:
        rows = [r for r in rec["rows"] if r["id"] in grp]
        line = f"{rec['layer']:3d}  "
        for c in CONDS:
            vals = [r[f"lp_{c}"] for r in rows if f"lp_{c}" in r]
            line += f"{st.mean(vals):12.3f}" if vals else f"{'-':>12}"
        for c in ("real", "mean", "yes", "no"):
            v = [r.get(f"ok_{c}") for r in rows]
            v = [x for x in v if x is not None]
            line += f"{sum(v)/len(v):9.3f}" if v else "        -"
        print(line)
