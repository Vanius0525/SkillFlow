"""Merge wb_spanpatch shards and print the layer curve with intervals.

    python -m howskill.wb_spanpatch_report results/p8-wb/skillspan-*.jsonl

Shards cover disjoint layer sets over the SAME instances (pick_instances is
seeded), so merging is by instance id and the baselines must agree between
shards -- they are recomputed independently in each, which makes their
agreement a free consistency check rather than a redundancy. The check is
printed; a disagreement means the shards did not sample the same items.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys


def boot(v, seed=0, n=4000):
    v = [x for x in v if x is not None]
    if not v:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(v)
    ms = sorted(sum(v[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return sum(v) / k, ms[int(0.025 * n)], ms[int(0.975 * n)]


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+")
    a = p.parse_args(argv)

    # Deduplicate by (file, instance). A run relaunched while an earlier copy
    # of itself was still alive appends the same instances twice -- --resume
    # reads the file once, at start, so two concurrent writers both think they
    # have work to do. Later rows win; the duplicate count is printed, because
    # a shard with duplicates is silently weighting some items more than others.
    rows, base = [], collections.defaultdict(dict)
    seen, dup = {}, 0
    for path in a.paths:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            key = (path, r["instance_id"])
            if key in seen:
                dup += 1
            seen[key] = r
    for (path, _iid), r in seen.items():
        rows.append((path, r))
        for k in ("ok_none", "ok_receiver", "ok_gold_in_context"):
            if k in r:
                base[k].setdefault(path, []).append(float(r[k]))

    ids = {r["instance_id"] for _, r in rows}
    print(f"files {len(a.paths)}   rows {len(rows)}   distinct instances "
          f"{len(ids)}   duplicate rows dropped: {dup}")
    print(f"cells {dict(collections.Counter(r['cell'] for _, r in rows))}")
    matched = {bool(r.get("matched")) for _, r in rows}
    spans = {r.get("n_patched") for _, r in rows}
    print(f"matched receiver: {matched}   patched positions: "
          f"min {min(x for x in spans if x)} max {max(x for x in spans if x)}")

    print("\nbaselines, recomputed independently per shard (they should agree)")
    for k, per in sorted(base.items()):
        parts = "   ".join(f"{path.split('/')[-1]}: {sum(v)/len(v):.3f} "
                           f"(n={len(v)})" for path, v in per.items())
        print(f"  {k[3:]:16s} {parts}")

    curve = collections.defaultdict(list)
    for _, r in rows:
        for k, v in r.items():
            if k.startswith("ok_real_") or k.startswith("ok_self_"):
                curve[k[3:]].append(float(v))
    print("\ntransplant, mean [95% CI]")
    def sortkey(k):
        tail = k.rsplit("_L", 1)[-1]
        return (0 if k.startswith("real") else 1,
                int(tail) if tail.isdigit() else 10 ** 6)
    for k in sorted(curve, key=sortkey):
        m, lo, hi = boot(curve[k], seed=abs(hash(k)) % 1000)
        bar = "#" * int(round(m * 30))
        print(f"  {k:22s} n={len(curve[k]):3d}  {m:.3f} [{lo:.3f},{hi:.3f}]  {bar}")
    print("\n  `self_*` must equal the receiver baseline; `real_*` above it is "
          "the effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
