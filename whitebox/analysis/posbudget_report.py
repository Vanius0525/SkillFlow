#!/usr/bin/env python3
"""The position-budget curve: report, contrasts, instrument checks and figure.

    python3 whitebox/analysis/posbudget_report.py            # report + figure
    python3 whitebox/analysis/posbudget_report.py --no-fig   # numbers only

Reads the wb_posbudget shards (pb-*, fp-*) and merges them by instance_id with
the full-dataset battery, which supplies the baselines (receiver, gold), the
untruncated transplant `real_L8`, the full-span permutation `dshuf_L8` and the
contiguous quarters `q0..q3_L8`. Everything is computed on the restricted set
(calculators whose wrong-skill receiver solves none of the rescued items), the
same 135 items / 14 calculators as Table 2, the rank curve and the depth sweep.

The analysis plan was fixed before any shard returned (CAMPAIGN-2026-09-18.md
§1.3): recovery rho per arm with calculator-cluster and item bootstrap
intervals; paired contrasts at each budget with exact McNemar tests, Holm-
corrected within each family; instrument checks that must hold exactly.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[2]
BY = ROOT / "howskill/results/p8-wb/fetched/by-host"
OUT = ROOT / "whitebox/analysis/out"

PB_TAGS = ["pb-ev", "pb-rn", "pb-mx", "pb-wf", "pb-wd", "pb-we", "pb-wr",
           "pb-td", "pb-tq", "pb-c256", "pb-chalf", "pb-sh", "pb-wh"]
FP_TAGS = ["fp-a", "fp-b", "fp-c"]
BATTERY = ["full-battery-a", "full-battery-b", "full-quarters"]
BUDGETS = ["1", "4", "16", "64", "256", "half", "full"]
STRAT = {
    # key: (label, colour, marker)
    "ev": ("evenly spaced, own states", "#0072B2", "o"),
    "rn": ("random positions, own states", "#56B4E9", "s"),
    "td": ("largest $\\|d\\|$, own states", "#009E73", "D"),
    "mx": ("same states, misplaced", "#D55E00", "v"),
    "tq": ("last $B$ prompt positions", "#666666", "x"),
    "wf": ("window on procedure", "#0072B2", "o"),
    "we": ("window on worked example", "#009E73", "D"),
    "wd": ("window on description", "#CC79A7", "^"),
    "wr": ("window at random", "#999999", "s"),
}
CONTRASTS = [("c1x", "c32x", "one block vs 32 blocks"),
             ("rn", "mx", "own vs misplaced"), ("rn", "tq", "span vs outside"),
             ("td", "rn", "top-energy vs random"), ("ev", "rn", "even vs random"),
             ("wf", "wd", "procedure vs description"), ("wf", "wr", "procedure vs random window"),
             ("we", "wr", "example vs random window")]


def load(tags):
    rows = {}
    for t in tags:
        for q in sorted(BY.glob(f"*/{t}.jsonl")):
            for line in open(q, encoding="utf-8"):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tgt = rows.setdefault(r["instance_id"], {})
                sel = r.pop("sel", None)
                tgt.update(r)
                if sel:
                    tgt.setdefault("sel", {}).update(sel)
    return rows


def restricted_ids(bat):
    bc = collections.defaultdict(list)
    for iid, r in bat.items():
        bc[r["calculator_id"]].append(iid)
    keep = {c for c, ids in bc.items() if not any(bat[i].get("ok_receiver") for i in ids)}
    return sorted(i for i, r in bat.items() if r["calculator_id"] in keep)


def rho_of(rows, key):
    sel = [r for r in rows if key in r]
    if not sel:
        return None, 0
    f = lambda k: sum(bool(r.get(k)) for r in sel) / len(sel)
    g, rc = f("ok_gold_in_context"), f("ok_receiver")
    return ((f(key) - rc) / (g - rc) if g > rc else None), len(sel)


def boot(rows, key, cluster=True, B=4000, seed=0):
    rng = random.Random(seed)
    sel = [r for r in rows if key in r]
    if not sel:
        return None, None
    groups = collections.defaultdict(list)
    for r in sel:
        groups[r["calculator_id"] if cluster else r["instance_id"]].append(r)
    keys = list(groups)
    vals = []
    for _ in range(B):
        samp = [r for k in (rng.choice(keys) for _ in keys) for r in groups[k]]
        v, _ = rho_of(samp, key)
        if v is not None:
            vals.append(v)
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]


def mcnemar(a, b):
    """Exact two-sided McNemar on paired booleans."""
    n01 = sum(1 for x, y in zip(a, b) if not x and y)
    n10 = sum(1 for x, y in zip(a, b) if x and not y)
    n = n01 + n10
    if n == 0:
        return n10, n01, 1.0
    k = min(n01, n10)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return n10, n01, min(1.0, 2 * p)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj = [0.0] * len(ps)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def arm_key(strat, bud, layer=8):
    if bud == "full":
        if strat in ("ev", "rn", "td", "wf", "wd", "we", "wr"):
            return f"ok_real_L{layer}"
        if strat == "mx":
            return f"ok_mxfull_L{layer}"
    return f"ok_{strat}{bud}_L{layer}"


def realised(rows, strat, bud):
    """Mean realised position count and energy share for an arm."""
    ns, es = [], []
    for r in rows:
        if bud == "full" and strat != "mx":
            ns.append(r.get("m", r.get("n_patched")))
            es.append(1.0)
            continue
        s = r.get("sel", {}).get(f"{strat}{bud}")
        if s:
            ns.append(s["n"])
            if "e" in s:
                es.append(s["e"])
    mean = lambda v: sum(v) / len(v) if v else None
    return mean([x for x in ns if x is not None]), mean(es)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--B", type=int, default=4000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    bat = load(BATTERY)
    pb = load(PB_TAGS + FP_TAGS)
    ids = restricted_ids({k: v for k, v in bat.items() if "ok_receiver" in v})
    rows = []
    for i in ids:
        r = dict(bat[i])
        if i in pb:
            r.update({k: v for k, v in pb[i].items() if k != "sel"})
            r["sel"] = pb[i].get("sel", {})
        rows.append(r)
    calcs = sorted({r["calculator_id"] for r in rows})
    report = {"n_items": len(rows), "n_calcs": len(calcs), "calcs": calcs,
              "gold": sum(r["ok_gold_in_context"] for r in rows) / len(rows),
              "receiver": sum(r["ok_receiver"] for r in rows) / len(rows),
              "arms": {}, "checks": {}, "contrasts": []}
    ms = [r.get("n_patched") for r in rows if r.get("n_patched")]
    if ms:
        report["span_width"] = {"min": min(ms), "median": sorted(ms)[len(ms) // 2],
                                "max": max(ms)}

    # ---- instrument checks: these must hold exactly -------------------------
    pev = load(["pb-ev"])      # raw: the merge above lets these keys collide
    have = [i for i in ids if "ok_self_L8" in pev.get(i, {})]
    report["checks"]["posbudget self == battery receiver"] = [
        sum(pev[i]["ok_self_L8"] == bat[i]["ok_receiver"] for i in have), len(have)]
    have = [r for r in rows if "ok_real_L8" in pb.get(r["instance_id"], {})]
    report["checks"]["posbudget real == battery real_L8"] = [
        sum(pb[r["instance_id"]]["ok_real_L8"] == bat[r["instance_id"]]["ok_real_L8"]
            for r in have), len(have)]
    # fp-c repeats tq1/tq16 at layer 8: rows from pb-tq and fp-c are merged
    # under the same key, so determinism is checked from the raw files instead
    fpc, pbt = load(["fp-c"]), load(["pb-tq"])
    for arm in ("tq1", "tq16"):
        both = [i for i in ids if f"ok_{arm}_L8" in fpc.get(i, {})
                and f"ok_{arm}_L8" in pbt.get(i, {})]
        report["checks"][f"{arm}@L8 fp-c == pb-tq"] = [
            sum(fpc[i][f"ok_{arm}_L8"] == pbt[i][f"ok_{arm}_L8"] for i in both), len(both)]

    # ---- per-arm recovery ----------------------------------------------------
    for strat in STRAT:
        for bud in BUDGETS + (["all"] if strat == "tq" else []):
            key = arm_key(strat, bud)
            v, n = rho_of(rows, key)
            if v is None:
                continue
            clo, chi = boot(rows, key, True, a.B)
            ilo, ihi = boot(rows, key, False, a.B)
            nm, em = realised([r for r in rows if key in r], strat, bud)
            report["arms"][f"{strat}{bud}"] = {
                "key": key, "rho": v, "n": n, "ci_cluster": [clo, chi],
                "ci_item": [ilo, ihi], "positions": nm, "energy": em}
    # fragmentation, displacement and half-span windows (added 04:50, §1.5)
    PB_TAGS_EXTRA = [f"c{n}x{b}" for b in ("256", "half") for n in (1, 2, 4, 8, 16, 32)] \
        + [f"sh{d}" for d in ("1", "4", "16", "64", "256")] \
        + [f"{w}half" for w in ("wf", "we", "wd", "wr")]
    for arm in PB_TAGS_EXTRA:
        key = f"ok_{arm}_L8"
        v, n = rho_of(rows, key)
        if v is None:
            continue
        clo, chi = boot(rows, key, True, a.B)
        ilo, ihi = boot(rows, key, False, a.B)
        sel = [r.get("sel", {}).get(arm) for r in rows if key in r]
        sel = [x for x in sel if x]
        mean = lambda k: (sum(x[k] for x in sel if k in x) / max(1, sum(1 for x in sel if k in x))
                          if any(k in x for x in sel) else None)
        report["arms"][arm] = {"key": key, "rho": v, "n": n, "ci_cluster": [clo, chi],
                               "ci_item": [ilo, ihi], "positions": mean("n"),
                               "energy": mean("e"), "frac_F": mean("F")}
    for extra in ("dshuf", "q0", "q1", "q2", "q3"):
        key = f"ok_{extra}_L8"
        v, n = rho_of(rows, key)
        if v is not None:
            clo, chi = boot(rows, key, True, a.B)
            w = {"q": 0.25}.get(extra[:1], 1.0)
            report["arms"][extra] = {"key": key, "rho": v, "n": n,
                                     "ci_cluster": [clo, chi],
                                     "positions": (report.get("span_width", {}).get("median") or 0) * w}
    # final position / whole question at other layers (fp-*)
    for L in (4, 8, 10, 14, 20, 24, 30):
        for arm in ("tq1", "tq16", "tqall"):
            key = f"ok_{arm}_L{L}"
            v, n = rho_of(rows, key)
            if v is not None:
                clo, chi = boot(rows, key, True, a.B)
                report["arms"][f"{arm}@L{L}"] = {"key": key, "rho": v, "n": n,
                                                 "ci_cluster": [clo, chi]}

    # ---- paired contrasts ----------------------------------------------------
    fam = collections.defaultdict(list)
    for sa, sb, label in CONTRASTS:
        for bud in (BUDGETS if not sa.startswith("c") else ["256", "half"]):
            ka, kb = arm_key(sa, bud), arm_key(sb, bud)
            if ka == kb:
                continue
            both = [r for r in rows if ka in r and kb in r]
            if len(both) < 10:
                continue
            gap = (sum(r["ok_gold_in_context"] for r in both)
                   - sum(r["ok_receiver"] for r in both)) / len(both)
            d = (sum(r[ka] for r in both) - sum(r[kb] for r in both)) / len(both) / gap
            n10, n01, p = mcnemar([r[ka] for r in both], [r[kb] for r in both])
            groups = collections.defaultdict(list)
            for r in both:
                groups[r["calculator_id"]].append(r)
            rng, vals, keys = random.Random(1), [], list(groups)
            for _ in range(a.B):
                s = [r for k in (rng.choice(keys) for _ in keys) for r in groups[k]]
                gp = (sum(r["ok_gold_in_context"] for r in s) - sum(r["ok_receiver"] for r in s)) / len(s)
                if gp > 0:
                    vals.append((sum(r[ka] for r in s) - sum(r[kb] for r in s)) / len(s) / gp)
            vals.sort()
            c = {"family": label, "a": f"{sa}{bud}", "b": f"{sb}{bud}", "n": len(both),
                 "delta_rho": d, "ci_cluster": [vals[int(.025 * len(vals))],
                                                vals[int(.975 * len(vals)) - 1]],
                 "a_only": n10, "b_only": n01, "p": p}
            fam[label].append(c)
    for label, cs in fam.items():
        for c, pa in zip(cs, holm([c["p"] for c in cs])):
            c["p_holm"] = pa
            report["contrasts"].append(c)

    # ---- coverage: at a fixed budget, does WHERE the block sits matter? ------
    # Every contiguous-window arm at one budget, pooled, binned by how much of
    # the procedure section (### Computation / ### Scoring Criteria) the block
    # covers. The window arms differ only in where the block is centred, so
    # this reads the location effect as a continuous variable instead of four
    # named regions -- and a 256-wide window cannot be a "description" arm when
    # the description is 56 tokens long (CAMPAIGN §1.1).
    report["coverage"] = {}
    for bud in ("256", "half"):
        pool = []
        for strat in ("wf", "wd", "we", "wr", "c1"):
            arm = f"c1x{bud}" if strat == "c1" else f"{strat}{bud}"
            key = f"ok_{arm}_L8"
            for r in rows:
                s_ = r.get("sel", {}).get(arm)
                if key in r and s_ and "F" in s_:
                    pool.append((s_["F"], bool(r[key]), r["calculator_id"],
                                 r["ok_gold_in_context"], r["ok_receiver"]))
        if len(pool) < 40:
            continue
        pool.sort(key=lambda x: x[0])
        q = len(pool) // 4
        bins = [pool[:q], pool[q:2 * q], pool[2 * q:3 * q], pool[3 * q:]]
        out = []
        for bn in bins:
            gap = (sum(x[3] for x in bn) - sum(x[4] for x in bn)) / len(bn)
            rho = ((sum(x[1] for x in bn) - sum(x[4] for x in bn)) / len(bn) / gap
                   if gap > 0 else None)
            out.append({"n": len(bn), "frac_F": [round(bn[0][0], 3), round(bn[-1][0], 3)],
                        "mean_frac_F": sum(x[0] for x in bn) / len(bn), "rho": rho})
        report["coverage"][bud] = out
    (OUT / "posbudget.json").write_text(json.dumps(report, indent=1))
    lines = [f"# Position budget, Qwen3-8B MedCalc, layer 8, restricted "
             f"n={report['n_items']} / {report['n_calcs']} calculators",
             f"gold {report['gold']:.3f}, receiver {report['receiver']:.3f}, "
             f"span width {report.get('span_width')}", "",
             "## instrument checks (must be exact)"]
    for k, (ok, n) in report["checks"].items():
        lines.append(f"- {k}: {ok}/{n}" + ("" if ok == n else "  **MISMATCH**"))
    lines += ["", "## recovery", "| arm | n | positions | energy | rho | cluster 95% | item 95% |",
              "|---|---|---|---|---|---|---|"]
    fmt = lambda x: "--" if x is None else f"{x:.2f}"
    for k, v in report["arms"].items():
        ci = v.get("ci_cluster", [None, None]); ii = v.get("ci_item", [None, None])
        lines.append(f"| {k} | {v['n']} | {fmt(v.get('positions'))} | {fmt(v.get('energy'))} | "
                     f"{v['rho']:.2f} | [{fmt(ci[0])}, {fmt(ci[1])}] | [{fmt(ii[0])}, {fmt(ii[1])}] |")
    if report.get("coverage"):
        lines += ["", "## contiguous blocks, binned by how much of the procedure section they cover",
                  "| budget | quartile | n | frac in F | rho |", "|---|---|---|---|---|"]
        for bud, bins in report["coverage"].items():
            for i, b in enumerate(bins, 1):
                lines.append(f"| {bud} | Q{i} | {b['n']} | {b['frac_F'][0]:.2f}-{b['frac_F'][1]:.2f} "
                             f"(mean {b['mean_frac_F']:.2f}) | {fmt(b['rho'])} |")
    lines += ["", "## paired contrasts (delta rho = a - b; McNemar exact, Holm within family)",
              "| family | a | b | n | delta rho | cluster 95% | a-only | b-only | p | p Holm |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for c in report["contrasts"]:
        lines.append(f"| {c['family']} | {c['a']} | {c['b']} | {c['n']} | {c['delta_rho']:+.2f} | "
                     f"[{c['ci_cluster'][0]:+.2f}, {c['ci_cluster'][1]:+.2f}] | {c['a_only']} | "
                     f"{c['b_only']} | {c['p']:.2g} | {c['p_holm']:.2g} |")
    (OUT / "posbudget.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if not a.no_fig:
        figure(report)


def figure(rep):
    """Four panels, one question each, all on the same 135 items.

    (a) spread positions: count and energy do not buy recovery
    (b) the same budget cut into more blocks: contiguity does
    (c) where one contiguous block sits: the procedure section
    (d) the whole span moved by D positions: placement must be exact
    Okabe-Ito hues; every series also has its own marker and a direct label,
    so identity never rests on colour alone.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.4, "axes.labelsize": 7.8,
                         "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42,
                         "legend.fontsize": 6.6})
    A = rep["arms"]
    full = A["evfull"]["rho"]
    m_med = rep.get("span_width", {}).get("median", 896)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.9), layout="constrained")
    (a_, b_), (c_, d_) = axes

    def err(v):
        return [[max(v["rho"] - v["ci_cluster"][0], 0)], [max(v["ci_cluster"][1] - v["rho"], 0)]]

    def frame(ax, title):
        ax.axhline(0, color="#8c6d1f", lw=0.8, zorder=0)
        ax.axhline(full, color="#009E73", lw=0.9, ls="--", zorder=0)
        ax.set_ylim(-0.05, 1.02)
        ax.set_title(title, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#ececec", lw=0.6, zorder=-1)

    # (a) spread positions ---------------------------------------------------
    lines = [("ev", "evenly spaced", "#0072B2", "o"), ("rn", "random", "#56B4E9", "s"),
             ("td", "largest $\\|d_p\\|$", "#009E73", "D"),
             ("mx", "same states, misplaced", "#D55E00", "v"),
             ("tq", "after the span", "#555555", "x")]
    for key, lab, col, mk in lines:
        buds = (["1", "4", "16", "64", "256", "half"] + (["full"] if key == "mx" else [])
                if key != "tq" else ["1", "4", "16", "64", "256"])
        pts = [(A[f"{key}{b}"]["positions"], A[f"{key}{b}"]) for b in buds if f"{key}{b}" in A]
        if key == "tq" and "tqall" in A:
            pass
        xs = [x for x, _ in pts]; ys = [v["rho"] for _, v in pts]
        lo = [max(v["rho"] - v["ci_cluster"][0], 0) for _, v in pts]
        hi = [max(v["ci_cluster"][1] - v["rho"], 0) for _, v in pts]
        a_.errorbar(xs, ys, yerr=[lo, hi], color=col, marker=mk, ms=4, lw=1.4, capsize=1.6,
                    elinewidth=0.7, mfc="white" if key in ("mx", "tq") else col, mew=1.1, label=lab)
    a_.errorbar([m_med], [full], yerr=err(A["evfull"]), color="#0072B2", marker="*", ms=9,
                capsize=1.6, elinewidth=0.7)
    a_.annotate("whole span, own states", (m_med, full), xytext=(-6, -14),
                textcoords="offset points", ha="right", fontsize=6.4, color="#333333")

    a_.set_xscale("log", base=2)
    a_.set_xticks([1, 4, 16, 64, 256, 1024]); a_.set_xticklabels(["1", "4", "16", "64", "256", "1024"])
    frame(a_, "(a) spread positions: more state does not help")
    a_.set_xlabel("positions written (layer 8)")
    a_.set_ylabel(r"recovery $\rho$")
    a_.legend(loc="upper left", frameon=False, handlelength=1.5, borderaxespad=0.1, ncol=1)

    # (b) fragmentation --------------------------------------------------------
    for bud, lab, col, mk, ref in (("256", "256 positions", "#0072B2", "o", "rn256"),
                                   ("half", "half the span", "#CC79A7", "s", "rnhalf")):
        pts = [(n, A.get(f"c{n}x{bud}")) for n in (1, 2, 4, 8, 16, 32)]
        pts = [(n, v) for n, v in pts if v]
        b_.errorbar([n for n, _ in pts], [v["rho"] for _, v in pts],
                    yerr=[[max(v["rho"] - v["ci_cluster"][0], 0) for _, v in pts],
                          [max(v["ci_cluster"][1] - v["rho"], 0) for _, v in pts]],
                    color=col, marker=mk, ms=4, lw=1.5, capsize=1.6, elinewidth=0.7, label=lab)
        if ref in A:
            b_.axhline(A[ref]["rho"], color=col, lw=0.9, ls=":", zorder=0,
                       label=f"{lab}, random single positions")
    b_.set_xscale("log", base=2)
    b_.set_xticks([1, 2, 4, 8, 16, 32]); b_.set_xticklabels(["1", "2", "4", "8", "16", "32"])
    frame(b_, "(b) same budget, cut into more blocks")
    b_.set_xlabel("number of contiguous blocks (budget and energy fixed)")
    b_.legend(loc="upper right", frameon=False, handlelength=1.8)

    # (c) location of one contiguous block ------------------------------------
    names = [("wf", "procedure"), ("wd", "description"), ("wr", "random"), ("we", "worked\nexample")]
    import numpy as np
    x = np.arange(len(names)); w = 0.36
    for off, bud, col, lab in ((-w / 2, "256", "#0072B2", "256 positions"),
                               (w / 2, "half", "#CC79A7", "half the span")):
        vs = [A.get(f"{k}{bud}") for k, _ in names]
        c_.bar(x + off, [v["rho"] for v in vs], width=w - 0.04, color=col, label=lab, zorder=2)
        c_.errorbar(x + off, [v["rho"] for v in vs],
                    yerr=[[max(v["rho"] - v["ci_cluster"][0], 0) for v in vs],
                          [max(v["ci_cluster"][1] - v["rho"], 0) for v in vs]],
                    fmt="none", ecolor="#333333", capsize=1.8, lw=0.8, zorder=3)
        for xi, v in zip(x + off, vs):
            c_.text(xi, v["ci_cluster"][1] + 0.02, f"{v['rho']:.2f}", ha="center", fontsize=6)
    c_.set_xticks(x); c_.set_xticklabels([n for _, n in names])
    frame(c_, "(c) where one contiguous block is centred")
    c_.set_xlabel("section the block is centred on")
    c_.set_ylabel(r"recovery $\rho$")
    c_.legend(loc="upper right", frameon=False)

    # (d) displacement --------------------------------------------------------
    pts = [(0.5, A["evfull"])] + [(int(d), A[f"sh{d}"]) for d in ("1", "4", "16", "64", "256")
                                  if f"sh{d}" in A] + [(m_med / 2, A["mxfull"])]
    d_.errorbar([p for p, _ in pts], [v["rho"] for _, v in pts],
                yerr=[[max(v["rho"] - v["ci_cluster"][0], 0) for _, v in pts],
                      [max(v["ci_cluster"][1] - v["rho"], 0) for _, v in pts]],
                color="#D55E00", marker="o", ms=4, lw=1.5, capsize=1.6, elinewidth=0.7)
    if "dshuf" in A:
        d_.errorbar([m_med * 0.9], [A["dshuf"]["rho"]], yerr=err(A["dshuf"]), color="#555555",
                    marker="x", ms=5, capsize=1.6, elinewidth=0.7)
        d_.annotate("random\npermutation", (m_med * 0.9, A["dshuf"]["rho"]), xytext=(0, 16),
                    textcoords="offset points", ha="center", fontsize=6.2, color="#555555")
    d_.set_xscale("log", base=2)
    d_.set_xticks([0.5, 1, 4, 16, 64, 256]); d_.set_xticklabels(["0", "1", "4", "16", "64", "256"])
    frame(d_, "(d) the whole span, displaced by $D$ positions")
    d_.set_xlabel("displacement $D$ (positions; last point: half the span)")
    d_.text(0.99, 0.60, f"all panels: the same {rep['n_items']} rescued items\n"
            f"({rep['n_calcs']} calculators), Qwen3-8B, layer 8\n"
            "dashed: whole span written in place", transform=d_.transAxes,
            ha="right", va="center", fontsize=6.2, color="#555555")
    for ext in ("pdf", "png"):
        # written next to the numbers, not into paper/: the manuscript is
        # edited separately and pulls figures from here when it adopts them
        fig.savefig(OUT / f"fig-posbudget.{ext}", bbox_inches="tight",
                    dpi=220 if ext == "png" else None)
    plt.close(fig)
    print(f"-> {OUT / 'fig-posbudget.pdf'}")


if __name__ == "__main__":
    main()
