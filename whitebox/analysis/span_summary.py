#!/usr/bin/env python3
"""Restricted-split summary of span runs: rho per arm with a cluster bootstrap.

    python whitebox/analysis/span_summary.py by-host/sra1/tqa-span.jsonl [...]

Same rule as audit.restrict and tables.py: keep the groups (calculator / skill)
whose receiver never solves an item; rho = (acc - receiver) / (gold - receiver);
95% intervals resample groups. Knockout files (ok_block_from) are summarised as
the fraction of rescued items kept when attention to the document is blocked from
layer L on.
"""
import collections
import json
import random
import sys


def load(paths):
    rows = {}
    for p in paths:
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                rows.setdefault(r["instance_id"], {}).update(r)
    return list(rows.values())


PER_ITEM = "--per-item" in sys.argv


def span(rows, B=2000):
    bc = collections.defaultdict(list)
    for r in rows:
        # --per-item: keep the ITEMS whose receiver fails, grouped as before for
        # the bootstrap. Defensible only after the instrument fix, where the
        # receiver is deterministic and the null arm reproduces it exactly.
        if PER_ITEM and r.get("ok_receiver"):
            continue
        bc[r["calculator_id"]].append(r)
    dep = [c for c, rs in bc.items() if not any(x.get("ok_receiver") for x in rs)]
    sel = [r for c in dep for r in bc[c]]
    fr = lambda k, S: sum(bool(r.get(k)) for r in S) / len(S)
    if not sel:
        print("  nothing survives the restriction"); return
    g, f = fr("ok_gold_in_context", sel), fr("ok_receiver", sel)
    arms = sorted({k for r in rows for k in r if k.startswith("ok_") and "_L" in k},
                  key=lambda k: (k.split("_L")[0], int(k.split("_L")[1]) if k.split("_L")[1].isdigit() else 0))
    print(f"  rows {len(rows)} over {len(bc)} groups | restricted n={len(sel)} over "
          f"{len(dep)} groups | none {fr('ok_none', sel):.2f} receiver {f:.2f} gold {g:.2f}"
          f" | unrestricted receiver {fr('ok_receiver', rows):.2f} gold {fr('ok_gold_in_context', rows):.2f}")
    rng = random.Random(0)
    for k in arms:
        # an arm can be defined on a subset only (dnear exists for calculators
        # with a same-family neighbour): read it, and its baselines, on the rows
        # that carry it -- counting a missing key as wrong understated dnear 3x
        has = lambda S: [r for r in S if k in r]
        dep_k = [c for c in dep if any(k in r for r in bc[c])]
        sk = has(sel)
        gk, fk = fr("ok_gold_in_context", sk), fr("ok_receiver", sk)
        vals = []
        for _ in range(B):
            S = has([r for c in (rng.choice(dep_k) for _ in dep_k) for r in bc[c]])
            if not S:
                continue
            gg, ff = fr("ok_gold_in_context", S), fr("ok_receiver", S)
            if gg - ff > 0:
                vals.append((fr(k, S) - ff) / (gg - ff))
        vals.sort()
        lo, hi = (vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]) if vals else (float("nan"),) * 2
        tag = "" if len(sk) == len(sel) else f"  (n={len(sk)})"
        print(f"    {k[3:]:14s} rho={(fr(k, sk) - fk) / max(gk - fk, 1e-9):+.2f}  [{lo:+.2f},{hi:+.2f}]{tag}")


def knockout(rows):
    kp = [r for r in rows if r["ok_with"] and not r["ok_without"]]
    lay = rows[0]["layers"]
    print(f"  rows {len(rows)} | rescued {len(kp)} over {len({r['calculator_id'] for r in kp})} groups")
    print("    kept when blocked from L: " + " ".join(
        f"L{L}={sum(bool(r['ok_block_from'][i]) for r in kp) / max(1, len(kp)):.2f}"
        for i, L in enumerate(lay)))


if __name__ == "__main__":
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    # --merge: one summary over all files joined on instance_id, for arms run
    # without --baselines whose baselines live in a sibling run on the same items
    for group in ([paths] if "--merge" in sys.argv else [[p] for p in paths]):
        rows = load(group)
        print(" + ".join(group))
        (knockout if rows and "ok_block_from" in rows[0] else span)(rows)
