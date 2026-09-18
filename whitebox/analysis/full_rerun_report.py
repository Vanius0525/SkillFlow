#!/usr/bin/env python3
"""Read the full-dataset rerun (`full-*` tags) and print it against the subset.

    python whitebox/analysis/full_rerun_report.py            # every experiment
    python whitebox/analysis/full_rerun_report.py battery    # one of them

Each experiment is the merge of its `-a` / `-b` shards on instance_id: the
shards cover the same items with disjoint arms, and only the `-a` shard carries
`--baselines`, so the merge is what makes the ratios computable.

Two restrictions are printed for every arm, because enlarging the item set
changes what the per-calculator rule keeps:

    per-calc   the paper's rule: keep calculators whose receiver never solves
               ANY item of theirs. With 20 items per calculator instead of 4
               this is a stricter condition than it was.
    per-item   keep the items whose own receiver fails. Legitimate only after
               the instrument fix, where the receiver is deterministic and the
               null arm reproduces it exactly; it is what the TheoremQA runs
               already use, since most of their groups hold a single item.

The subset column is the number the paper currently prints, recomputed here
from the old tag with the old rule, so drift is visible rather than assumed.
"""
from __future__ import annotations

import collections
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BY = ROOT / "howskill/results/p8-wb/fetched/by-host"

# name: (full tags, subset tag(s) the paper cites, layer for the arm suffix)
EXPERIMENTS = {
    "battery":  (["full-battery-a", "full-battery-b"], ["fixmask-big40", "fixmask-dnear"], 8),
    "rank":     (["full-rank-a", "full-rank-b", "full-battery-a"], ["rank40-l8"], 8),
    "depth":    (["full-depth-a", "full-depth-b", "full-depth-c13", "full-depth-d", "full-battery-a"], ["big40-depth"], None),
    "dose":     (["full-dose", "full-battery-a"], ["fixmask-dev10"], 8),
    "quarters": (["full-quarters", "full-battery-a"], ["fixmask-quarters40-q0", "fixmask-quarters40-q1",
                                                       "fixmask-quarters40-q2", "fixmask-quarters40-q3",
                                                       "fixmask-big40"], 8),
    "doclast":  (["full-dl-a", "full-dl-b"], ["fixmask-dl"], None),
    "window":   (["full-window"], ["fixmask-window"], None),
    "knockout": (["full-ko"], ["ko-8b-fast"], None),
}


def load(tags):
    rows = {}
    for t in tags:
        for q in sorted(BY.glob(f"*/{t}.jsonl")):
            for line in open(q, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    rows.setdefault(r["instance_id"], {}).update(r)
    return list(rows.values())


def restrict(rows, how):
    if how == "per-item":
        return [r for r in rows if not r.get("ok_receiver")]
    bc = collections.defaultdict(list)
    for r in rows:
        bc[r["calculator_id"]].append(r)
    keep = {c for c, rs in bc.items() if not any(x.get("ok_receiver") for x in rs)}
    return [r for r in rows if r["calculator_id"] in keep]


def rho(sel, key, boot=0):
    sk = [r for r in sel if key in r]
    if not sk:
        return None, None
    fr = lambda k, S: sum(bool(r.get(k)) for r in S) / len(S)
    g, f = fr("ok_gold_in_context", sk), fr("ok_receiver", sk)
    if g - f <= 0:
        return None, None
    point = (fr(key, sk) - f) / (g - f)
    if not boot:
        return point, None
    bc = collections.defaultdict(list)
    for r in sk:
        bc[r["calculator_id"]].append(r)
    cs, rng, vals = list(bc), random.Random(0), []
    for _ in range(boot):
        S = [r for c in (rng.choice(cs) for _ in cs) for r in bc[c]]
        gg, ff = fr("ok_gold_in_context", S), fr("ok_receiver", S)
        if gg - ff > 0:
            vals.append((fr(key, S) - ff) / (gg - ff))
    vals.sort()
    return point, (vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]) if vals else None


def knockout(rows, label):
    kp = [r for r in rows if r.get("ok_with") and not r.get("ok_without")]
    if not kp:
        print(f"  {label}: nothing"); return
    lay = kp[0]["layers"]
    print(f"  {label}: {len(kp)} rescued over "
          f"{len({r['calculator_id'] for r in kp})} calculators")
    print("    " + "  ".join(
        f"L{L}={sum(bool(r['ok_block_from'][i]) for r in kp) / len(kp):.2f}"
        for i, L in enumerate(lay)))


def arms_of(rows, layer):
    keys = {k for r in rows for k in r if k.startswith("ok_") and "_L" in k or
            (k.startswith("ok_real_w"))}
    if layer is not None:
        keys = {k for k in keys if k.endswith(f"_L{layer}") or "_w" in k}
    return sorted(keys, key=lambda k: (k.split("_L")[0], k))


def report(name):
    full_tags, sub_tags, layer = EXPERIMENTS[name]
    full, sub = load(full_tags), load(sub_tags)
    print(f"\n=== {name} ===")
    print(f"  full : {len(full):4d} items / {len({r['calculator_id'] for r in full}):2d} calculators"
          f"   ({'+'.join(full_tags)})")
    print(f"  subset: {len(sub):4d} items / {len({r['calculator_id'] for r in sub}):2d} calculators"
          f"   ({'+'.join(sub_tags)})")
    if not full:
        print("  (the full run is not present locally yet)"); return
    if "ok_block_from" in full[0]:
        knockout(full, "full"); knockout(sub, "subset") if sub else None
        return
    for how in ("per-calc", "per-item"):
        fs, ss = restrict(full, how), restrict(sub, how) if sub else []
        print(f"  -- restricted {how}: full n={len(fs)} over "
              f"{len({r['calculator_id'] for r in fs})} calculators"
              + (f", subset n={len(ss)} over {len({r['calculator_id'] for r in ss})}" if ss else ""))
        for k in arms_of(full, layer):
            p, ci = rho(fs, k, boot=2000 if how == "per-calc" else 0)
            q, _ = rho(ss, k) if ss else (None, None)
            if p is None:
                continue
            ci_s = f" [{ci[0]:+.2f},{ci[1]:+.2f}]" if ci else ""
            q_s = f"   subset {q:+.2f}" if q is not None else "   subset --"
            n_k = sum(1 for r in fs if k in r)
            tag = "" if n_k == len(fs) else f"  (n={n_k})"
            print(f"     {k[3:]:16s} {p:+.2f}{ci_s}{q_s}{tag}")


if __name__ == "__main__":
    which = sys.argv[1:] or list(EXPERIMENTS)
    for w in which:
        if w not in EXPERIMENTS:
            sys.exit(f"unknown experiment {w!r}; pick from {', '.join(EXPERIMENTS)}")
        report(w)
