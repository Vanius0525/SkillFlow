"""Aggregate results.

    python -m howskill.analyze results/            # per-arm table
    python -m howskill.analyze results/ --steps    # + failure transition matrix

Confidence intervals are bootstrapped by resampling CALCULATORS, not
instances: the 20 instances sharing a calculator are not independent, and
treating them as such would understate the interval roughly 4-fold.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random


def load_arm(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if "error" not in r:
                rows.append(r)
    return rows


def cluster_bootstrap(rows: list[dict], n_boot: int = 2000, seed: int = 0):
    """Mean accuracy + 95% CI, resampling calculators with replacement."""
    by_calc: dict = {}
    for r in rows:
        by_calc.setdefault(r["calculator_id"], []).append(bool(r["correct"]))
    calcs = list(by_calc)
    if not calcs:
        return 0.0, (0.0, 0.0)
    point = sum(sum(v) for v in by_calc.values()) / sum(len(v) for v in by_calc.values())
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        pick = [by_calc[rng.choice(calcs)] for _ in calcs]
        n = sum(len(v) for v in pick)
        means.append(sum(sum(v) for v in pick) / n if n else 0.0)
    means.sort()
    return point, (means[int(0.025 * n_boot)], means[int(0.975 * n_boot)])


def paired_delta(a: list[dict], b: list[dict], n_boot: int = 2000, seed: int = 0):
    """Delta (b - a) on the instances both arms ran, clustered by calculator."""
    ai = {r["instance_id"]: bool(r["correct"]) for r in a}
    bi = {r["instance_id"]: bool(r["correct"]) for r in b}
    shared = set(ai) & set(bi)
    calc = {r["instance_id"]: r["calculator_id"] for r in a}
    by_calc: dict = {}
    for iid in shared:
        by_calc.setdefault(calc[iid], []).append(bi[iid] - ai[iid])
    calcs = list(by_calc)
    if not calcs:
        return 0.0, (0.0, 0.0), 0
    tot = sum(sum(v) for v in by_calc.values())
    n = sum(len(v) for v in by_calc.values())
    point = tot / n
    rng = random.Random(seed)
    ds = []
    for _ in range(n_boot):
        pick = [by_calc[rng.choice(calcs)] for _ in calcs]
        m = sum(len(v) for v in pick)
        ds.append(sum(sum(v) for v in pick) / m if m else 0.0)
    ds.sort()
    return point, (ds[int(0.025 * n_boot)], ds[int(0.975 * n_boot)]), len(shared)


def token_cost(rows: list[dict]) -> dict:
    tot, turns, calls, n = 0, 0, 0, 0
    for r in rows:
        t = r.get("trajectory") or {}
        turns += t.get("n_turns", 0)
        calls += t.get("n_tool_calls", 0)
        for tn in t.get("turns", []):
            u = (tn.get("meta") or {}).get("usage") or {}
            tot += u.get("total_tokens", 0) or 0
        n += 1
    if not n:
        return {}
    return {"mean_tokens": round(tot / n, 1),
            "mean_turns": round(turns / n, 2),
            "mean_tool_calls": round(calls / n, 2)}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("results_dir")
    p.add_argument("--baseline", default="no_skill")
    p.add_argument("--control", default="ctrl_neutral")
    p.add_argument("--steps", action="store_true")
    a = p.parse_args(argv)

    arms = {}
    for path in sorted(glob.glob(os.path.join(a.results_dir, "*.jsonl"))):
        tag = os.path.basename(path)[:-6]
        arms[tag] = load_arm(path)

    if not arms:
        print(f"no .jsonl in {a.results_dir}")
        return 1

    print(f"{'arm':<28} {'n':>5} {'acc':>7}  {'95% CI':>16}  cost")
    print("-" * 84)
    for tag, rows in arms.items():
        pt, (lo, hi) = cluster_bootstrap(rows)
        c = token_cost(rows)
        cost = (f"{c.get('mean_tokens', 0):.0f}tok "
                f"{c.get('mean_turns', 0):.1f}turn "
                f"{c.get('mean_tool_calls', 0):.1f}call") if c else ""
        print(f"{tag:<28} {len(rows):>5} {100*pt:>6.1f}%  "
              f"[{100*lo:>5.1f},{100*hi:>5.1f}]  {cost}")

    def find(key: str):
        """Locate an arm by tag. Tags carry a run prefix (`p2-gold`), so an
        exact or startswith match silently finds nothing and the gate readout
        below is skipped without a word — say so instead."""
        hits = [t for t in arms if t == key] or [t for t in arms if key in t]
        if not hits:
            print(f"\n[warn] no arm matching {key!r} in {sorted(arms)} — "
                  "paired deltas skipped; pass --baseline/--control")
            return None
        if len(hits) > 1:
            print(f"\n[warn] {key!r} matches {hits}; using {hits[0]}")
        return arms[hits[0]]

    base = find(a.baseline)
    ctrl = find(a.control)

    if base:
        print(f"\n=== paired deltas vs {a.baseline} ===")
        for tag, rows in arms.items():
            if rows is base:
                continue
            d, (lo, hi), n = paired_delta(base, rows)
            sig = "" if lo <= 0 <= hi else "  *"
            print(f"  {tag:<28} {100*d:>+6.1f}pp  [{100*lo:>+6.1f},{100*hi:>+6.1f}]"
                  f"  n={n}{sig}")

    if ctrl:
        print(f"\n=== paired deltas vs {a.control}  (presence effect removed) ===")
        for tag, rows in arms.items():
            if rows is ctrl or (base and rows is base):
                continue
            d, (lo, hi), n = paired_delta(ctrl, rows)
            sig = "" if lo <= 0 <= hi else "  *"
            print(f"  {tag:<28} {100*d:>+6.1f}pp  [{100*lo:>+6.1f},{100*hi:>+6.1f}]"
                  f"  n={n}{sig}")
        if base:
            d, (lo, hi), n = paired_delta(base, ctrl)
            print(f"\n  H6 check — presence effect ({a.control} - {a.baseline}): "
                  f"{100*d:+.1f}pp [{100*lo:+.1f},{100*hi:+.1f}]")
            print("  If gold - ctrl_neutral is not clearly positive, STOP: the "
                  "effect is presence, not content (PROTOCOL.md GATE-2).")

    if a.steps:
        from howskill.steps import first_failure, transition_matrix
        HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gt = {g["instance_id"]: g for g in json.load(
            open(os.path.join(HERE, "data", "stepgt.json"), encoding="utf-8"))}
        inst = {i["instance_id"]: i for i in json.load(
            open(os.path.join(HERE, "data", "medcalcbench.json"), encoding="utf-8"))}
        names = {s["skill_id"]: s.get("name") for s in json.load(
            open(os.path.join(HERE, "data", "medcalc_skills.json"), encoding="utf-8"))}

        def steps_for(rows):
            out = []
            for r in rows:
                fr = first_failure(r.get("trajectory") or {}, inst[r["instance_id"]],
                                   gt.get(r["instance_id"]),
                                   {"correct": r["correct"]},
                                   calculator_name=names.get(r.get("skill_id")))
                out.append({"instance_id": r["instance_id"],
                            "fail_step": fr["fail_step"]})
            return out

        if base:
            for tag, rows in arms.items():
                if rows is base:
                    continue
                sa, sb = steps_for(base), steps_for(rows)
                unp = sum(1 for x in sa + sb if x["fail_step"] == "unparsed")
                rate = 1 - unp / max(1, len(sa) + len(sb))
                print(f"\n=== transition matrix: {a.baseline} -> {tag} ===")
                print(f"    parse rate {100*rate:.1f}%"
                      + ("   [<80% — readout NOT reliable, PROTOCOL.md GATE-0]"
                         if rate < 0.8 else ""))
                m = transition_matrix(sa, sb)
                keys = ["none", "S1", "S2", "S3", "S4", "S5", "unparsed"]
                print("      " + "".join(f"{k:>9}" for k in keys))
                for x in keys:
                    row = "".join(f"{m[x][y]:>9}" for y in keys)
                    print(f"    {x:<6}{row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
