#!/usr/bin/env python3
"""The replication curves in full, for the appendix.

    python paper/replication_full.py      -> paper/tab-replication-full.tex (+ stdout)

Same files and the same restriction as paper/replication.py; this prints every
point of every curve instead of the one summary number per column, so a reader
can check where a handover or a knee was read off.
"""
from __future__ import annotations

import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
_s = importlib.util.spec_from_file_location("rep", HERE / "replication.py")
rep = importlib.util.module_from_spec(_s)
_s.loader.exec_module(rep)

ARMS = (("real", "transplant"), ("realm", "own $d$ on shared prefix"), ("a0.5", r"$\alpha{=}0.5$"),
        ("dcross", "another skill"), ("dfar", "another family"), ("dnear", "same family"),
        ("dshuf", "permuted"), ("drand", "noise"), ("self", "null"))


def fmt(v):
    return "--" if v is None else f"{v:.2f}"


def layer_curve(groups, prefix, suffix=""):
    keys = sorted({k for rs in groups.values() for r in rs for k in r
                   if k.startswith(f"ok_{prefix}_L")},
                  key=lambda k: int(k.rsplit("L", 1)[1]))
    return [(int(k.rsplit("L", 1)[1]), rep.rho(groups, k)) for k in keys]


def main():
    out = []
    out += [r"\begin{tabular}{@{}p{0.15\textwidth}p{0.22\textwidth}p{0.57\textwidth}@{}}", r"\toprule",
            r"task / model & measurement & values \\", r"\midrule"]
    for task, model, nl, L, bat, dep, rk, ko in rep.resolved_rows():
        name = f"{task} / {model}"
        rows = []
        base = rep.restricted(rep.load(bat or rk or []))
        if base:
            n = sum(len(v) for v in base.values())
            vals = [f"{lab} {fmt(rep.rho(base, f'ok_{a}_L{L}'))}"
                    + (f" ($n={sum(f'ok_{a}_L{L}' in r for rs in base.values() for r in rs)}$)"
                       if sum(f'ok_{a}_L{L}' in r for rs in base.values() for r in rs) != n else "")
                    for a, lab in ARMS if rep.rho(base, f"ok_{a}_L{L}") is not None]
            rows.append((f"battery, L{L} ($n={n}$, {len(base)} groups)", ", ".join(vals)))
        if dep:
            d = rep.restricted(rep.load(dep))
            n = sum(len(v) for v in d.values())
            rows.append((f"sufficiency ($n={n}$)", ", ".join(
                f"L{l} {fmt(v)}" for l, v in layer_curve(d, "real"))))
        if ko:
            # one-layer fill-ins live in their own files, so the sweeps are
            # merged per layer (rep.ko_curve) rather than by row update, and
            # the curve is read on the rescued items of this row's screened
            # groups -- the items its transfer curve uses
            groups = set(rep.restricted(rep.load(dep))) if dep else None
            curve, kn = rep.ko_curve(ko, groups=groups)
            if curve:
                rows.append((f"necessity ($n={kn}$ rescued"
                             + (", screened groups" if groups else "") + ")",
                             ", ".join(f"L{Lk} {curve[Lk]:.2f}" for Lk in sorted(curve))))
        g = rep.restricted(rep.load(rk)) if rk else {}
        if g:
            n = sum(len(v) for v in g.values())
            ks = [k for k in (4, 16, 32, 64, 128) if rep.rho(g, f"ok_rank{k}_L{L}") is not None]
            lo = [k for k in (16, 64) if rep.rho(g, f"ok_rank{k}lo_L{L}") is not None]
            rows.append((f"rank, L{L} ($n={n}$)", ", ".join(
                [f"$k{{=}}{k}$ {fmt(rep.rho(g, f'ok_rank{k}_L{L}'))}" for k in ks]
                + [f"full {fmt(rep.rho(g, f'ok_real_L{L}'))}"]
                + [f"bottom-{k} {fmt(rep.rho(g, f'ok_rank{k}lo_L{L}'))}" for k in lo]
                + [f"$k^{{*}}$ {rep.kstar(g, L):.0f}"])))
        for i, (m, v) in enumerate(rows):
            out.append(f"{name if i == 0 else ''} & {m} & {v} \\\\")
            print(f"{name:24s} {m:36s} {v}")
        out.append(r"\midrule")
    out[-1] = r"\bottomrule"
    out.append(r"\end{tabular}")
    (HERE / "tab-replication-full.tex").write_text("\n".join(out) + "\n")
    print("-> paper/tab-replication-full.tex")


if __name__ == "__main__":
    main()
