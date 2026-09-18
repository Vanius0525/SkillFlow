#!/usr/bin/env python3
"""Read a `wb_heads --mode map` run and test its three predictions.

    python whitebox/analysis/head_map.py heads-smoke.jsonl
    python whitebox/analysis/head_map.py heads-smoke.jsonl --emit-ko 12

The file's claim is that the document's content leaves its span through a small
set of attention heads in a band of layers, and that an injection is useful only
upstream of that band. Three things are printed, in the order they can falsify
it:

  P1  how concentrated the read-out is, by layer and over heads. A flat profile
      kills the account outright: if every layer reads the span about equally,
      there is no band to be upstream of.
  P2  `recovery`, the projection of the read-out an injection at L0 causes onto
      the read-out the real document causes, over the layers DOWNSTREAM of L0.
      The prediction is that this tracks behavioural rho: ~1 at L0 <= 12,
      near 0 at L0 >= 16. It is measured without decoding anything.
  P3  the head list for `wb_heads --mode knockout`, which is the causal test.
      Heads are ranked on ||dg||, so the ranking and the knockout must not be
      read on the same items -- `--emit-ko` takes its ranking from the
      calculators NOT named by `--holdout`, and prints which items are left.

CAVEAT ON ||dg||. It is the norm of a residual-stream write, not an effect. A
head with a large write whose direction the rest of the network ignores would
rank highly here and do nothing under knockout. That is exactly why P3 exists,
and why a null there is informative rather than a failure of the pipeline.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import random
import sys


def scalars(paths):
    """Pass 1: the small per-row fields, streaming.

    The full-scale map is 147 MB of nested lists and a list of parsed rows is
    several GB -- enough to get this process killed on a 11 GB WSL box, which is
    what happened on 2026-09-17. Nothing here needs every row in memory at once:
    the matrices are only ever averaged, and the bootstrap only needs a handful
    of floats per row. So the file is read twice, streaming both times.
    """
    out = []
    for p in paths:
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("mode") != "map":
                continue
            out.append({
                "calculator_id": r["calculator_id"],
                "m": r["m"], "n_prompt": r["n_prompt"],
                "instrument_rel_err": r.get("instrument_rel_err"),
                "recovery": r.get("recovery") or {},
                "closed_last": {k: v[-1] for k, v in
                                (r.get("closed") or {}).items() if v},
                "gap_recv": r.get("gap_recv"),
                "resid_gold": r.get("resid_gold"),
            })
            del r
    return out


class Acc:
    """Running mean of one [layer][head] matrix, over a chosen set of rows."""

    def __init__(self, keep=None):
        self.keep, self.sum, self.n = keep, {}, collections.Counter()

    def add(self, r):
        if self.keep is not None and r["calculator_id"] not in self.keep:
            return
        for key in ("att_gold", "att_recv", "c_recv_norm", "dg_norm",
                    "ov_dot_dg", "qk_dot_dg"):
            m = r.get(key)
            if not m:
                continue
            a = self.sum.get(key)
            if a is None:
                a = self.sum[key] = [[0.0] * len(m[0]) for _ in m]
            for i, row in enumerate(m):
                ai = a[i]
                for j, v in enumerate(row):
                    ai[j] += v
            self.n[key] += 1

    def get(self, key):
        a, n = self.sum.get(key), self.n[key]
        return [[v / n for v in row] for row in a] if a and n else None


def matrices(paths, keep=None):
    """Pass 2: mean matrices, streaming, optionally over a subset of groups."""
    acc = Acc(keep)
    for p in paths:
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("mode") == "map":
                acc.add(r)
            del r
    return acc


def boot_mean(vals, groups, n=2000, seed=0):
    """Cluster bootstrap over calculators, as the rest of the analysis does."""
    by = collections.defaultdict(list)
    for v, g in zip(vals, groups):
        by[g].append(v)
    cs, rng, out = list(by), random.Random(seed), []
    if not cs:
        return None, None
    point = sum(vals) / len(vals)
    for _ in range(n):
        S = [x for c in (rng.choice(cs) for _ in cs) for x in by[c]]
        out.append(sum(S) / len(S))
    out.sort()
    return point, (out[int(.025 * n)], out[int(.975 * n)])


def p1(rows, acc):
    dg = acc.get("dg_norm")
    ag = acc.get("att_gold")
    ar = acc.get("att_recv")
    nL, nH = len(dg), len(dg[0])
    tot = sum(sum(r) for r in dg)
    # the span's share of the prompt: what a head that spread its attention
    # evenly would put on the span, so "reads the span" is not just "is wide"
    unif = sum(r["m"] / r["n_prompt"] for r in rows) / len(rows)
    print(f"\n=== P1  read-out by layer  ({len(rows)} items, "
          f"{len({r['calculator_id'] for r in rows})} calculators, "
          f"{nL} layers x {nH} heads) ===")
    print(f"  span is {unif:.1%} of the prompt, so uniform attention on it "
          f"would read {unif:.3f}")
    # ||dg|| is a write into a residual stream whose norm grows by more than
    # 10x with depth, so the raw share is reported next to the share of the
    # stream it is written into. A band that is only visible in the raw column
    # is a norm artefact, not a read-out.
    rg = None
    for r in rows:
        if r.get("resid_gold"):
            rg = [0.0] * len(r["resid_gold"])
            break
    if rg is not None:
        n_r = 0
        for r in rows:
            if r.get("resid_gold"):
                for i, v in enumerate(r["resid_gold"]):
                    rg[i] += v
                n_r += 1
        rg = [v / n_r for v in rg]
    rel = [sum(dg[L]) / rg[L] for L in range(nL)] if rg else None
    trel = sum(rel) if rel else 1.0
    print("  layer  share of ||dg||   cum     share/||resid||  max head   enrich")
    cum = 0.0
    for L in range(nL):
        s = sum(dg[L]) / tot
        cum += s
        h = max(range(nH), key=lambda x: dg[L][x])
        bar = "#" * int(round(s * 160))
        rl = f"{rel[L] / trel:6.3f}" if rel else "     -"
        rbar = "#" * int(round((rel[L] / trel) * 160)) if rel else ""
        print(f"   {L:3d}   {s:6.3f} {bar:<18.18s} {cum:5.3f}  {rl} "
              f"{rbar:<18.18s} h{h:<2d} {ag[L][h] / unif:5.1f}x")
    flat = [(dg[L][h], L, h) for L in range(nL) for h in range(nH)]
    flat.sort(reverse=True)
    k1 = max(1, len(flat) // 100)
    print(f"  concentration: top 1% of heads ({k1}) carry "
          f"{sum(v for v, _, _ in flat[:k1]) / tot:.1%} of the read-out; "
          f"top 5% carry {sum(v for v, _, _ in flat[:5 * k1]) / tot:.1%}")
    print("\n  rank  head    ||dg||  /resid  att_gold  att_recv  enrich   ov%    qk%")
    ov = acc.get("ov_dot_dg")
    qk = acc.get("qk_dot_dg")
    d2 = [[v * v for v in row] for row in dg]
    for i, (v, L, h) in enumerate(flat[:20]):
        o = f"{100 * ov[L][h] / d2[L][h]:5.1f}" if ov and d2[L][h] else "    -"
        q = f"{100 * qk[L][h] / d2[L][h]:5.1f}" if qk and d2[L][h] else "    -"
        rl = f"{v / rg[L]:6.4f}" if rg else "     -"
        print(f"  {i+1:4d}  L{L:02d}h{h:02d}  {v:7.2f}  {rl}  {ag[L][h]:8.3f}  "
              f"{ar[L][h]:8.3f}  {ag[L][h] / unif:5.1f}x  {o}  {q}")
    return


def p2(rows):
    """The depth curve, measured with no decoding.

    `closed[L0][L]` is the fraction of the receiver-to-gold gap at the CONSUMER
    positions -- the question text, which has to use the document -- that an
    injection at L0 has closed by layer L. The number printed is at the last
    layer, which is what the decoder actually reads.

    `recovery[L0]` is printed beside it as the control that makes the reading
    unambiguous. From L0+1 on, the SPAN's own states are identical to gold by
    construction: the span attends only to the shared prefix and to itself, and
    both are gold after the patch. So the document's content IS present, and is
    read out downstream, whatever `closed` says. If `closed` collapses while
    `recovery` does not, the failure is on the reader side and not the content
    side -- which also rules out the rank-collapse account, since at L0+1 the
    content is the gold content bit for bit.
    """
    rho_paper = {0: 1.00, 4: 1.06, 8: 1.03, 12: 0.81, 15: 0.14, 16: 0.14,
                 18: 0.07, 20: 0.29, 24: 0.00, 30: 0.00}
    layers = sorted({int(k) for r in rows for k in r["closed_last"]})
    if not layers:
        return
    print("\n=== P2  what an injection at L0 restores at the consumer positions ===")
    print("  inject   gap closed at the last layer      recovery   rho(paper)")
    print("           point    95% CI            n      downstream")
    pts = {}
    for L0 in layers:
        vals = [r["closed_last"][str(L0)] for r in rows if str(L0) in r["closed_last"]]
        gs = [r["calculator_id"] for r in rows if str(L0) in r["closed_last"]]
        if not vals:
            continue
        pt, ci = boot_mean(vals, gs)
        pts[L0] = pt
        rv = [r["recovery"][str(L0)] for r in rows
              if r["recovery"].get(str(L0)) is not None]
        rp = rho_paper.get(L0)
        bar = "#" * int(round(max(pt, 0) * 30))
        print(f"   L{L0:<5d} {pt:7.3f}  [{ci[0]:6.3f},{ci[1]:6.3f}] {len(vals):4d}   "
              f"{(sum(rv)/len(rv) if rv else float('nan')):8.3f}   "
              f"{'' if rp is None else f'{rp:5.2f}'}  {bar}")
    xs = [L for L in pts if rho_paper.get(L) is not None]
    if len(xs) > 2:
        a = [pts[L] for L in xs]
        b = [rho_paper[L] for L in xs]
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        den = math.sqrt(sum((x - ma) ** 2 for x in a)
                        * sum((y - mb) ** 2 for y in b))
        if den:
            print(f"  correlation with the behavioural depth curve over "
                  f"{len(xs)} shared layers: r = {num / den:.3f}")
        # where the cliff is, in each curve, by the largest drop between
        # consecutive measured layers
        def cliff(vals, ks):
            d = [(vals[i] - vals[i + 1], ks[i], ks[i + 1])
                 for i in range(len(ks) - 1)]
            return max(d)
        print(f"  largest drop: mechanistic {cliff(a, xs)[1]}->{cliff(a, xs)[2]}, "
              f"behavioural {cliff(b, xs)[1]}->{cliff(b, xs)[2]}")

    # the gap the injection has to close, layer by layer, in the receiver
    g = [r["gap_recv"] for r in rows if r.get("gap_recv")]
    if g:
        nL = len(g[0])
        mg = [sum(x[L] for x in g) / len(g) for L in range(nL)]
        print("\n  receiver-to-gold divergence at the consumer positions, by layer")
        print("  (relative to the residual norm; this is what an injection must undo)")
        for L in range(0, nL, 2):
            print(f"   L{L:<3d} {mg[L]:7.4f} " + "#" * int(round(mg[L] * 120)))


def p3(rows, paths, k, holdout):
    """Rank heads on the calculators NOT held out, print the list to knock out."""
    hs = sorted({r["calculator_id"] for r in rows})
    if holdout:
        test = [c for c in hs if c in set(holdout.split(","))]
    else:
        test = hs[::2]                      # every other calculator
    train = [c for c in hs if c not in set(test)]
    if not train:
        print("\n=== P3 === not enough calculators to split; rank on all")
        train, test = hs, []
    dg = matrices(paths, keep=set(train)).get("dg_norm")
    rg = next((r["resid_gold"] for r in rows if r.get("resid_gold")), None)
    # ranked on the write relative to the stream, for the reason P1 prints both
    fl = sorted(((dg[L][h] / (rg[L] if rg else 1.0), L, h)
                 for L in range(len(dg))
                 for h in range(len(dg[0]))), reverse=True)[:k]
    print(f"\n=== P3  knockout list ===")
    print(f"  ranked on {len(train)} calculators ({','.join(train)}), "
          f"to be tested on {len(test)} ({','.join(test)})")
    print("  --ko-heads " + ",".join(f"{L}:{h}" for _, L, h in sorted(
        fl, key=lambda t: (t[1], t[2]))))
    print(f"  layers touched: "
          f"{sorted({L for _, L, _ in fl})}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--emit-ko", type=int, default=0,
                    help="print the top-k head list for the knockout arm")
    ap.add_argument("--holdout", default="",
                    help="calculators to reserve for the knockout test")
    a = ap.parse_args()
    rows = scalars(a.files)
    if not rows:
        sys.exit("no map rows in " + " ".join(a.files))
    err = [r["instrument_rel_err"] for r in rows
           if r.get("instrument_rel_err") is not None]
    if err:
        print(f"instrument: attention output reconstructed to "
              f"{max(err):.2e} relative")
    acc = matrices(a.files)
    p1(rows, acc)
    p2(rows)
    if a.emit_ko:
        p3(rows, a.files, a.emit_ko, a.holdout)


if __name__ == "__main__":
    main()
