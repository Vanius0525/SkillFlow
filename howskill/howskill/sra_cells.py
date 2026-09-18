#!/usr/bin/env python3
"""Merge sra_behave shards into one cells file per (dataset, model).

    python -m howskill.sra_cells <fetched/by-host> <out dir>

Shards are the per-box outputs of `sra_behave --shard i/n` (tags beh-<ds>-<model>
and beh-<ds>-<model>-sN). A resumed shard can contain rows for instances outside
its own slice, and two shards can decode the same (instance, arm); duplicates
must agree on `ok` or the merge refuses -- a disagreement would mean two
different prompts or graders ran under one tag.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys


def main(root, out):
    root, out = pathlib.Path(root), pathlib.Path(out)
    groups = collections.defaultdict(list)
    for q in sorted(root.glob("*/beh-*.jsonl")):
        base = q.stem
        parts = base.split("-")
        if parts[-1].startswith("s") and parts[-1][1:].isdigit():
            base = "-".join(parts[:-1])
        groups[base].append(q)
    for base, files in sorted(groups.items()):
        ok, meta, conflicts = collections.defaultdict(dict), {}, 0
        for q in files:
            for line in open(q, encoding="utf-8"):
                if not line.strip():
                    continue
                r = json.loads(line)
                meta = {"dataset": r["dataset"], "model": r["model"]}
                prev = ok[r["instance_id"]].get(r["arm"])
                if prev is not None and prev != r["ok"]:
                    conflicts += 1
                ok[r["instance_id"]][r["arm"]] = r["ok"]
        cells = {"R": [], "F": [], "K": [], "B": []}
        complete = {i: v for i, v in ok.items() if {"none", "gold"} <= set(v)}
        for iid, v in sorted(complete.items()):
            cells["R" if v["gold"] and not v["none"] else
                  "K" if v["gold"] and v["none"] else
                  "B" if v["none"] else "F"].append(iid)
        arms = sorted({a for v in ok.values() for a in v})
        acc = {a: round(sum(v.get(a, False) for v in complete.values())
                        / max(1, len(complete)), 4) for a in arms}
        doc = {"cells": cells, **meta, "n": len(complete), "accuracy": acc,
               "shards": [f"{q.parent.name}/{q.name}" for q in files],
               "duplicate_disagreements": conflicts}
        (out / f"cells-{base[4:]}.json").write_text(json.dumps(doc, indent=1))
        print(f"{base}: n={len(complete)} acc={acc} "
              + " ".join(f"{k}={len(v)}" for k, v in cells.items())
              + f" shards={len(files)} dup-disagree={conflicts}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
