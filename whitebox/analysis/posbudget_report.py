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
           "pb-td", "pb-tq"]
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
CONTRASTS = [("rn", "mx", "own vs misplaced"), ("rn", "tq", "span vs outside"),
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
        for bud in BUDGETS:
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
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
                         "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42,
                         "legend.fontsize": 6.6})
    A = rep["arms"]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55), layout="constrained",
                             gridspec_kw={"width_ratios": [1.25, 1.0, 1.0]})

    def series(ax, strat, buds, offset=1.0, label=None, lw=1.6):
        c, mk = STRAT[strat][1], STRAT[strat][2]
        xs, ys, lo, hi = [], [], [], []
        for b in buds:
            v = A.get(f"{strat}{b}")
            if not v or v.get("positions") is None:
                continue
            xs.append(v["positions"] * offset); ys.append(v["rho"])
            lo.append(max(v["rho"] - v["ci_cluster"][0], 0))
            hi.append(max(v["ci_cluster"][1] - v["rho"], 0))
        if not xs:
            return
        ax.errorbar(xs, ys, yerr=[lo, hi], color=c, marker=mk, ms=4.2, lw=lw,
                    capsize=1.8, elinewidth=0.8, label=label or STRAT[strat][0],
                    mfc="white" if strat in ("mx", "wd") else c, mew=1.2)

    def deco(ax, title):
        ax.set_xscale("log", base=2)
        ax.axhline(0, color="#8c6d1f", lw=0.8, zorder=0)
        ax.axhline(1, color="#009E73", lw=0.8, ls="--", zorder=0)
        ax.set_ylim(-0.08, 1.12)
        ax.set_title(title, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e6e6", lw=0.6, zorder=-1)

    a_, b_, c_ = axes
    for s in ("ev", "rn", "td", "mx"):
        series(a_, s, BUDGETS)
    series(a_, "tq", ["1", "4", "16", "64", "256"], offset=1.0)
    if "dshuf" in A:
        v = A["dshuf"]
        a_.plot([v["positions"] * 1.08], [v["rho"]], marker="*", ms=8, color="#D55E00",
                ls="none", label="full span, random permutation")
    deco(a_, "(a) how many positions, and whose states")
    a_.set_xlabel("positions written at layer 8 (log scale)")
    a_.set_ylabel(r"recovery $\rho$")
    a_.legend(loc="upper left", frameon=False, handlelength=1.6, borderaxespad=0.2)

    for s in ("wf", "we", "wd", "wr"):
        series(b_, s, ["1", "4", "16", "64", "256"])
    for q, name in (("q0", "Q1"), ("q1", "Q2"), ("q2", "Q3"), ("q3", "Q4")):
        if q in A:
            b_.plot([A[q]["positions"]], [A[q]["rho"]], marker="_", ms=9, mew=2, color="#333333")
            b_.annotate(name, (A[q]["positions"], A[q]["rho"]), xytext=(4, -2),
                        textcoords="offset points", fontsize=6, color="#333333")
    deco(b_, "(b) same budget, different content")
    b_.set_xlabel("contiguous window length")
    b_.legend(loc="upper left", frameon=False, handlelength=1.6, borderaxespad=0.2)

    for s in ("ev", "rn", "td", "mx", "wf", "we", "wd", "wr"):
        xs = [A[f"{s}{b}"]["energy"] for b in BUDGETS
              if f"{s}{b}" in A and A[f"{s}{b}"].get("energy") is not None]
        ys = [A[f"{s}{b}"]["rho"] for b in BUDGETS
              if f"{s}{b}" in A and A[f"{s}{b}"].get("energy") is not None]
        if xs:
            c_.plot(xs, ys, marker=STRAT[s][2], ls="none", ms=4.2, color=STRAT[s][1],
                    mfc="white" if s in ("mx", "wd") else STRAT[s][1], mew=1.1)
    c_.set_xscale("log")
    c_.axhline(0, color="#8c6d1f", lw=0.8, zorder=0)
    c_.axhline(1, color="#009E73", lw=0.8, ls="--", zorder=0)
    c_.set_ylim(-0.08, 1.12)
    c_.set_title("(c) recovery against content energy written", loc="left")
    c_.set_xlabel(r"share of the span's $\sum_p\|d_p\|^2$ written")
    c_.spines[["top", "right"]].set_visible(False)
    c_.grid(axis="y", color="#e6e6e6", lw=0.6, zorder=-1)
    for ax in axes:
        ax.text(0.99, 0.02, f"n = {rep['n_items']}", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=6.4, color="#555555")
    for ext in ("pdf", "png"):
        fig.savefig(ROOT / f"paper/fig-posbudget.{ext}", bbox_inches="tight",
                    dpi=200 if ext == "png" else None)
    plt.close(fig)
    print("-> paper/fig-posbudget.pdf")


if __name__ == "__main__":
    main()
