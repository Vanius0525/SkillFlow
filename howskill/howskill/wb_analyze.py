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

from howskill.wb_replay import ARGMAX_FLOOR, MAD_MAX


def regate(g: dict | None) -> bool | None:
    """Re-apply the CURRENT gate to a stored record instead of trusting `ok`.

    `ok` is frozen at write time, so a file written before a threshold was
    corrected reports the old verdict forever. Both corrections so far went the
    same way -- a criterion that scaled with completion length, rejecting
    forwards whose absolute error matched the accepted ones -- and both were
    found only because someone read the raw fields. Recomputing here means a
    stale file and a fresh one are judged by the same rule, and no rerun is
    needed to change a verdict that was never about the arithmetic.
    """
    if not g:
        return None
    if not isinstance(g.get("mad"), float):
        return g.get("ok")
    ok = g["mad"] <= MAD_MAX
    if isinstance(g.get("argmax_match"), float):
        ok = ok and g["argmax_match"] >= ARGMAX_FLOOR
    return bool(ok)


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


def print_profiles(rows: list[dict], label: str = ""):
    gates = []
    for r in rows:
        for k in ("gate_w0_with", "gate_w0_without"):
            v = regate(r.get(k))
            if v is not None:
                gates.append(v)
    n_ok = sum(1 for g in gates if g)
    stale = sum(1 for r in rows for k in ("gate_w0_with", "gate_w0_without")
                if (r.get(k) or {}).get("ok") is not None
                and regate(r.get(k)) != (r.get(k) or {}).get("ok"))
    head = f"GATE-W0{(' [' + label + ']') if label else ''}"
    print(f"{head}: {n_ok}/{len(gates)} forwards reproduce generation"
          f"   (thresholds: mad<={MAD_MAX}, argmax>={ARGMAX_FLOOR})"
          + ("" if n_ok == len(gates) else
             "   [FAIL - internal numbers below are not trustworthy]"))
    if stale:
        print(f"  ({stale} verdicts differ from the `ok` stored in the file; "
              f"the file predates a threshold correction -- see "
              f"wb_replay.ARGMAX_FLOOR)")
    mads = [g["mad"] for r in rows for k in ("gate_w0_with", "gate_w0_without")
            if isinstance((r.get(k) or {}).get("mad"), float)
            for g in [r[k]]]
    if mads:
        mads.sort()
        print(f"  mad: median {mads[len(mads)//2]:.5f}  max {mads[-1]:.5f}")
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
    p.add_argument("--compare", default=None,
                   help="a ctrl_neutral profiles file. With it, GATE-W2 is "
                        "decided here instead of by eye across two runs.")
    a = p.parse_args(argv)
    rows = load(a.path)
    if not rows:
        print(f"no usable rows in {a.path}")
        return 1
    if a.kind == "patch":
        print_patch(rows)
        return 0
    print_profiles(rows, label="gold" if a.compare else "")
    if not a.compare:
        print("\nGATE-W2 reminder: rerun the same command on the ctrl_neutral "
              "outputs, or pass --compare <neutral.jsonl>. A separation that "
              "also appears there is about a document being present, not "
              "about its content.")
        return 0

    ctrl = load(a.compare)
    print("\n" + "=" * 74)
    print_profiles(ctrl, label="neutral")
    print("\n" + "=" * 74)
    print("GATE-W2: R-F on cka_task, gold vs mismatched skill")
    print("=" * 74)
    print("  A layer counts only if R and F separate under GOLD and do NOT")
    print("  separate under NEUTRAL. Separation = non-overlapping bootstrap CIs.")
    print("\n  layer      gold R-F           neutral R-F        verdict")
    gr, gf = layer_curve(rows, "cka_task", "R"), layer_curve(rows, "cka_task", "F")
    nr, nf = layer_curve(ctrl, "cka_task", "R"), layer_curve(ctrl, "cka_task", "F")
    if not (gr and gf and nr and nf):
        print("  [!] one of the four cell curves is empty -- nothing to compare.")
        return 1
    layers = rows[0].get("layers") or list(range(len(gr)))
    n = min(len(gr), len(gf), len(nr), len(nf))
    passed = []
    for i in range(n):
        mr, (lr, hr) = boot_mean(gr[i]); mf, (lf, hf) = boot_mean(gf[i])
        Mr, (Lr, Hr) = boot_mean(nr[i]); Mf, (Lf, Hf) = boot_mean(nf[i])
        gsep = lr > hf or lf > hr
        nsep = Lr > Hf or Lf > Hr
        verd = ("CONTENT" if gsep and not nsep else
                "presence" if gsep and nsep else
                "no separation" if not gsep else "")
        if gsep and not nsep:
            passed.append(layers[i])
        print(f"  {layers[i]:>5}  {mr-mf:+7.4f}            {Mr-Mf:+7.4f}"
              f"            {verd}")
    print(f"\n  layers where the separation is content-specific: "
          f"{passed if passed else 'NONE'}")
    if not passed:
        print("  -> the R vs F separation reported under gold does not survive "
              "the control. It is about a document being present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
