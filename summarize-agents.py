#!/usr/bin/env python3
"""
Read results/agents_*.jsonl and print the scaffold comparison as one table.

The number that decides whether the comparison means anything is not accuracy,
it is the truncation rate. A task cut off by the wall-clock limit and a task
answered wrongly are indistinguishable in an accuracy column, so a cell that
timed out on half its tasks is reporting its time budget, not its scaffold. That
column comes first here for that reason.

    python summarize-agents.py
    python summarize-agents.py --results-dir results --glob 'agents_*.jsonl'

Inspect writes its own .eval log format rather than this JSONL, so it will not
appear here; use `inspect view --log-dir results/inspect_logs` for that cell.
"""

import argparse
import glob
import json
import os
import sys


def load(path: str) -> tuple[list[dict], dict | None]:
    tasks, summary = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a run killed mid-write leaves one partial line
            if row.get("_type") == "summary":
                summary = row
            else:
                tasks.append(row)
    return tasks, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--glob", default="agents_*.jsonl")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.results_dir, args.glob)))
    if not paths:
        print(f"no results matching {args.results_dir}/{args.glob}")
        return 1

    header = (f"{'cell':<34} {'timed out':>11} {'correct':>10} {'acc':>7} "
              f"{'tok in/out':>18}")
    print(header)
    print("-" * len(header))

    suspect = []
    for path in paths:
        tasks, summary = load(path)
        if not tasks:
            print(f"{os.path.basename(path)[:-6]:<34} {'(no tasks)':>11}")
            continue
        n = len(tasks)
        cut = sum(1 for t in tasks if t.get("timed_out") or t.get("budget_exceeded"))
        ok = sum(1 for t in tasks if t.get("correct"))
        tin = sum(t.get("tokens", {}).get("input", 0) for t in tasks)
        tout = sum(t.get("tokens", {}).get("output", 0) for t in tasks)
        rate = cut / n
        if rate >= 0.25:
            suspect.append((os.path.basename(path), rate))
        print(f"{os.path.basename(path)[:-6]:<34} "
              f"{f'{cut}/{n} ({rate:.0%})':>11} "
              f"{f'{ok}/{n}':>10} {ok / n * 100:>6.1f}% "
              f"{f'{tin:,}/{tout:,}':>18}")

    if suspect:
        print()
        print("[!] 截断率 >= 25% 的 cell —— 这些数字反映的是时间预算,不是 scaffold:")
        for name, rate in suspect:
            print(f"    {name}  {rate:.0%}")
        print("    调大 TIMEOUT 重跑,或在论文里把截断率和准确率一起报。")

    inspect_dir = os.path.join(args.results_dir, "inspect_logs")
    if os.path.isdir(inspect_dir):
        print()
        print(f"inspect 那一格是它自己的 .eval 格式,不在上表里:")
        print(f"    inspect view --log-dir {inspect_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
