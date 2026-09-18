#!/usr/bin/env python3
"""Tier A E2, read through the four-cell split instead of a difficulty tercile.

HANDOFF-whitebox.md 12.3aa section 5 split the items into terciles of lp_no.
That split is legitimate for comparing two interventions to each other -- it
never looks at either -- but it cannot be used against the no-document baseline,
because it was formed from that baseline and regression to the mean is then
guaranteed. The four cells

    R rescued   wrong without the skill, right with it
    F persist   wrong both ways
    K kept      right both ways
    B broken    right without the skill, wrong with it

are formed from the ACCURACY channel, so the logprob comparisons inside a cell
carry no such circularity, and they are the same cells the HOWSKILLWORK line
uses on real skills -- which makes the two studies readable side by side.

    python cells_lp.py [<run>/e2-tierA/per_layer.jsonl]
"""
import json, math, statistics as st, sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    "../results/20260909-130000/e2-tierA/per_layer.jsonl"
layers = [json.loads(l) for l in open(path, encoding="utf-8")]
CONDS = ["real", "mismatched", "mean", "filler"]


def entropy(opt):
    lps = [v for k, v in opt.items() if k != "_best"]
    ps = [math.exp(x) for x in lps]
    s = sum(ps) or 1.0
    ps = [p / s for p in ps]
    return -sum(p * math.log(p + 1e-12) for p in ps)


def margin(opt, gold):
    others = [v for k, v in opt.items() if k not in ("_best", gold)]
    return opt[gold] - max(others)


rows0 = {r["id"]: r for r in layers[0]["rows"]}
cell = {}
for i, r in rows0.items():
    key = (bool(r["ok_no"]), bool(r["ok_yes"]))
    cell[i] = {(False, True): "R", (False, False): "F",
               (True, True): "K", (True, False): "B"}[key]
n = {c: sum(1 for v in cell.values() if v == c) for c in "RFKB"}
print(f"file : {path}")
print(f"cells: R={n['R']}  F={n['F']}  K={n['K']}  B={n['B']}  (n={len(cell)})")
print("       R = the only cell where the skill demonstrably works.\n")

for c in "RFKB":
    ids = [i for i, v in cell.items() if v == c]
    if not ids:
        continue
    r0 = [rows0[i] for i in ids]
    print(f"=== cell {c}  n={len(ids)} ===")
    print(f"    lp_no {st.mean(r['lp_no'] for r in r0):+.3f}   "
          f"lp_yes {st.mean(r['lp_yes'] for r in r0):+.3f}   "
          f"lp_filler {st.mean(r['lp_filler'] for r in r0):+.3f}")
    print("     L " + "".join(f"{c2:>11}" for c2 in CONDS) +
          "   acc_real   marg_real   ent_real   ent_mean")
    for rec in layers:
        rs = [r for r in rec["rows"] if cell.get(r["id"]) == c]
        line = f"    {rec['layer']:2d} "
        for c2 in CONDS:
            line += f"{st.mean(r[f'lp_{c2}'] for r in rs):11.3f}"
        a = [r["ok_real"] for r in rs]
        line += f"{sum(a)/len(a):11.3f}"
        line += f"{st.mean(margin(r['opt_real'], r['gold']) for r in rs):12.3f}"
        line += f"{st.mean(entropy(r['opt_real']) for r in rs):11.3f}"
        line += f"{st.mean(entropy(r['opt_mean']) for r in rs):11.3f}"
        print(line)
    print()

# ---------------------------------------------------------------------------
# The decomposition that answers "why does a content-free vector out-score the
# real one on lp(gold)". Additive over cells, so it is arithmetic, not a story.
# ---------------------------------------------------------------------------
print("=" * 78)
print("  WHERE THE AGGREGATE lp(gold) GAP COMES FROM, CELL BY CELL")
print("=" * 78)
print("  A cell's contribution to a mean over n items is (n_c/n) * (its own gap).")
print()
for rec in layers:
    L = rec["layer"]
    if L < 17:
        continue
    rs = rec["rows"]
    tot = len(rs)
    agg = {c: st.mean(r[f"lp_{c}"] for r in rs) for c in CONDS}
    print(f"  --- layer {L} ---   aggregate lp: " +
          "  ".join(f"{c} {agg[c]:+.3f}" for c in CONDS))
    gap_total = agg["mean"] - agg["real"]
    print(f"      mean - real = {gap_total:+.3f} nats, split by cell:")
    for c in "RFKB":
        sub = [r for r in rs if cell.get(r["id"]) == c]
        if not sub:
            continue
        g = st.mean(r["lp_mean"] for r in sub) - st.mean(r["lp_real"] for r in sub)
        share = len(sub) / tot * g
        accs = {c2: sum(r[f"ok_{c2}"] for r in sub) / len(sub)
                for c2 in ("real", "mean", "mismatched")}
        print(f"        {c} n={len(sub):3d}  gap {g:+8.3f}  "
              f"contributes {share:+8.3f} ({100*share/gap_total:5.1f}%)  "
              f"acc real {accs['real']:.3f} mean {accs['mean']:.3f} "
              f"mis {accs['mismatched']:.3f}")
    print()
