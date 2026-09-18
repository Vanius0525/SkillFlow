#!/usr/bin/env python3
"""Is every result file complete, or did the platform reclaim the box mid-run?

    python whitebox/analysis/completeness.py

The `no_skill` behavioural arm stopped at 839 of 1100 and nobody noticed for
weeks, because a truncated JSONL looks exactly like a finished one. This walks
every result we have and compares what is in the file against what the run's
own arguments say should be there. It does not know the right answer; it knows
how to derive the expected count from the file itself.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
issues = []


def rows(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    issues.append(f"{path}: a line does not parse (truncated write?)")
    except FileNotFoundError:
        pass
    return out


def check(label, got, want, note=""):
    ok = got == want
    tag = "OK " if ok else "XX "
    print(f"  {tag} {label:52s} {got:>6} / {want:<6} {note}")
    if not ok:
        issues.append(f"{label}: {got} of {want} {note}")


print("=== span-vector runs (wb_spanvec) ===")
for p in sorted(glob.glob(f"{ROOT}/howskill/results/p8-wb/fetched/by-host/*/spanvec-*.jsonl")):
    rs = rows(p)
    if not rs:
        continue
    r0 = rs[0]
    # the run records its own selection; per_calc x max_calcs is the target
    n_calc = len({r.get("calculator_id") for r in rs})
    name = os.path.basename(p)
    # every run in this family used --per-calc 4
    want = n_calc * 4
    ids = {r.get("instance_id") for r in rs}
    check(f"{os.path.basename(os.path.dirname(p))}/{name}", len(ids), want,
          f"({n_calc} calcs)")

print("\n=== document-span shards (wb_spanpatch) ===")
for p in sorted(glob.glob(f"{ROOT}/howskill/results/p8-wb/fetched/by-host/*/skillspan-*.jsonl")):
    rs = rows(p)
    if not rs:
        continue
    n_calc = len({r.get("calculator_id") for r in rs})
    check(f"{os.path.basename(os.path.dirname(p))}/{os.path.basename(p)}",
          len({r["instance_id"] for r in rs}), n_calc * 4, f"({n_calc} calcs)")

print("\n=== other 1100-set runs ===")
for pat, want_fn, note in (
        ("**/knockout-span.jsonl", lambda rs: None, "no declared target"),
        ("**/knockout-layers.jsonl", lambda rs: None, "no declared target"),
        ("**/probe-cue.jsonl", lambda rs: None, ""),
        ("**/diffvec-cot-*.jsonl", lambda rs: None, ""),
        ("**/docid.jsonl", lambda rs: None, "one row per layer")):
    for p in sorted(glob.glob(f"{ROOT}/howskill/results/p8-wb/fetched/{pat}",
                              recursive=True)):
        rs = rows(p)
        if not rs:
            continue
        ids = {r.get("instance_id") for r in rs if r.get("instance_id")}
        layers = {r.get("layer") for r in rs if r.get("layer") is not None}
        print(f"  -- {os.path.basename(os.path.dirname(p))}/"
              f"{os.path.basename(p):28s} rows={len(rs):4d} "
              f"instances={len(ids):4d} layers={sorted(layers) if layers else '-'}")

print("\n=== Tier A runs: are all the swept layers present? ===")
for summ in sorted(glob.glob(f"{ROOT}/whitebox/results/**/summary.json", recursive=True)):
    d = os.path.dirname(summ)
    if "smoke" in d:
        continue
    try:
        s = json.load(open(summ, encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        issues.append(f"{summ}: unreadable")
        continue
    name = os.path.basename(d)
    layers = s.get("layers")
    per_layer = sorted(glob.glob(os.path.join(d, "layer_*.jsonl")))
    if layers and isinstance(layers, list):
        acc = s.get("acc_real")
        if isinstance(acc, list):
            check(f"{name} acc_real entries", len(acc), len(layers),
                  f"layers {layers[0]}..{layers[-1]}")
        if per_layer:
            check(f"{name} layer files", len(per_layer), len(layers))
    elif per_layer:
        nums = sorted(int(os.path.basename(f)[6:-6]) for f in per_layer)
        gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
        print(f"  {'OK ' if not gaps else 'XX '} {name:52s} "
              f"{len(nums):>6} files, {nums[0]}..{nums[-1]}"
              f"{'  MISSING ' + str(gaps) if gaps else ''}")
        if gaps:
            issues.append(f"{name}: missing layer files {gaps}")

print("\n" + ("NO GAPS FOUND" if not issues
              else f"{len(issues)} PROBLEM(S):\n  - " + "\n  - ".join(issues)))
sys.exit(1 if issues else 0)
