"""Aggregate the whitebox readouts and apply GATE-W2.

    python -m howskill.wb_analyze results/p8-wb/profiles.jsonl
    python -m howskill.wb_analyze results/p8-wb/patch.jsonl --kind patch

The claim P8-WHITEBOX.md §3.5 asks for has two halves, and this prints both:
R and F must be separable on a measurement, AND the same measurement must not
separate them when the skill is a mismatched one. A curve that differs between
cells under gold and differs just as much under ctrl_neutral is a statement
about having a document in the prompt, not about what the document says.

Intervals are bootstrapped over instances. Unlike the behavioural table there
is no calculator-level clustering here: the cells are small and already
stratified, and the honest reading is per-instance variation within a cell,
reported as such.
"""

from __future__ import annotations

import argparse
import json
import math
import random


def load(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                if "error" not in r:
                    out.append(r)
    return out


def boot_mean(xs: list[float], n_boot: int = 2000, seed: int = 0):
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    if not xs:
        return float("nan"), (float("nan"), float("nan"))
    rng = random.Random(seed)
    m = sum(xs) / len(xs)
    ms = []
    for _ in range(n_boot):
        s = [xs[rng.randrange(len(xs))] for _ in xs]
        ms.append(sum(s) / len(s))
    ms.sort()
    return m, (ms[int(0.025 * n_boot)], ms[int(0.975 * n_boot)])


def by_cell(rows: list[dict], key) -> dict:
    out: dict = {}
    for r in rows:
        out.setdefault(r["cell"], []).append(key(r))
    return out


def layer_curve(rows: list[dict], field: str, cell: str) -> list[list[float]]:
    """Transpose per-instance layer curves into per-layer value lists."""
    cur = [r[field] for r in rows if r["cell"] == cell and r.get(field)]
    if not cur:
        return []
    n = min(len(c) for c in cur)
    return [[c[i] for c in cur] for i in range(n)]


def print_profiles(rows: list[dict]):
    gates = [(r.get("gate_w0_with") or {}).get("ok") for r in rows]
    n_ok = sum(1 for g in gates if g)
    print(f"GATE-W0: {n_ok}/{len(gates)} forwards reproduce generation"
          + ("" if n_ok == len(gates) else
             "   [FAIL — internal numbers below are not trustworthy]"))
    counts = {c: sum(1 for r in rows if r["cell"] == c) for c in ("R", "F", "K", "B")}
    print(f"cells: {counts}")
    short = [c for c in ("R", "F") if counts.get(c, 0) < 100]
    if short:
        print(f"[warn] GATE-W1 wants >=100 in R and F; short: {short}")

    print("\n=== CKA(task span): with-skill vs without-skill, by layer ===")
    print("  layer        R                    F              R-F")
    for cell in ("R", "F"):
        if not layer_curve(rows, "cka_task", cell):
            print(f"  (no cka_task for cell {cell})")
            return
    cr = layer_curve(rows, "cka_task", "R")
    cf = layer_curve(rows, "cka_task", "F")
    layers = rows[0].get("layers") or list(range(len(cr)))
    for i in range(min(len(cr), len(cf))):
        mr, (lr, hr) = boot_mean(cr[i])
        mf, (lf, hf) = boot_mean(cf[i])
        d = mr - mf
        star = "  *" if (lr > hf or lf > hr) else ""
        print(f"  {layers[i]:>5}  {mr:5.3f} [{lr:5.3f},{hr:5.3f}]  "
              f"{mf:5.3f} [{lf:5.3f},{hf:5.3f}]  {d:+6.3f}{star}")

    print("\n=== task-span entropy (with skill), by layer ===")
    for cell in ("R", "F"):
        cur = [r["task_profile_with"] for r in rows
               if r["cell"] == cell and r.get("task_profile_with")]
        if not cur:
            continue
        n = min(len(c) for c in cur)
        vals = [boot_mean([c[i]["entropy"] for c in cur])[0] for i in range(n)]
        peak = max(range(n), key=lambda i: vals[i])
        trough = min(range(n), key=lambda i: vals[i])
        print(f"  cell {cell}: n={len(cur)}  entropy peak at layer index "
              f"{peak}, trough at {trough}  "
              f"(first {min(6,n)}: {[round(v,2) for v in vals[:6]]})")


def print_patch(rows: list[dict]):
    print("=== knockout: what the answer loses when the skill is unattendable ===")
    for cell in ("R", "F"):
        rs = [r for r in rows if r["cell"] == cell]
        if not rs:
            continue
        d_skill = [r["knockout_skill"] - r["s_with"] for r in rs]
        d_ctrl = [r["knockout_ctrl"] - r["s_with"] for r in rs]
        ms, (ls, hs) = boot_mean(d_skill)
        mc, (lc, hc) = boot_mean(d_ctrl)
        print(f"  {cell}  n={len(rs)}  skill span {ms:+.3f} [{ls:+.3f},{hs:+.3f}]"
              f"   length-matched control {mc:+.3f} [{lc:+.3f},{hc:+.3f}]")

    print("\n=== patch: recovery by layer (task-span tail -> no-skill run) ===")
    for cell in ("R", "F"):
        rs = [r for r in rows if r["cell"] == cell and r.get("patch_task_tail")]
        if not rs:
            continue
        n = min(len(r["patch_task_tail"]) for r in rs)
        print(f"  cell {cell} (n={len(rs)}):")
        for i in range(n):
            L = rs[0]["patch_task_tail"][i]["layer"]
            m, (lo, hi) = boot_mean([r["patch_task_tail"][i]["recovery"]
                                     for r in rs])
            bar = "#" * max(0, min(40, int(round(m * 20))))
            print(f"    layer {L:>3}  {m:+6.3f} [{lo:+6.3f},{hi:+6.3f}]  {bar}")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--kind", default="profiles", choices=["profiles", "patch"])
    a = p.parse_args(argv)
    rows = load(a.path)
    if not rows:
        print(f"no usable rows in {a.path}")
        return 1
    (print_profiles if a.kind == "profiles" else print_patch)(rows)
    print("\nGATE-W2 reminder: rerun the same command on the ctrl_neutral "
          "outputs. A separation that also appears there is about a document "
          "being present, not about its content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
