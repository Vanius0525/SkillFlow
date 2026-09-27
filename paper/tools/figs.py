#!/usr/bin/env python3
"""Figures for the mechanism paper, straight from the run outputs.

    python figs.py --e14 <run_dir> --out .

No intermediate CSV: a figure that disagrees with a table in the paper should be
impossible to produce, and the only way to guarantee that is for both to be read
from the same file by the same code. Anything the figure needs that is not in
the run output is a bug in the experiment, not something to patch here.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def save(fig, out: pathlib.Path, name: str):
    """PDF for the paper, PNG next to it so the figure can actually be looked at.

    A vector figure nobody renders is a figure nobody checks, and the failure
    mode is not a crash -- it is a legend covering the curve that matters.
    """
    # bbox_inches="tight" so a legend placed below the axes is not clipped;
    # without it the figure box is the axes box and anything outside is cut
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(out / f"{name}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

# Colour-blind-safe, and distinguishable in greyscale by line style as well.
STYLE = {
    "replace_real":  dict(color="#333333", ls="-",  lw=1.8, label=r"replace with $h_{\rm skill}$"),
    "add_d_a1":      dict(color="#0072B2", ls="-",  lw=2.2, label=r"$h_{\rm no}+d$  (content)"),
    "add_g":         dict(color="#D55E00", ls="--", lw=2.0, label=r"$h_{\rm no}+g$  (presence)"),
    "add_t":         dict(color="#999999", ls=":",  lw=1.5, label=r"$h_{\rm no}+t$  (both)"),
    "add_dbar":      dict(color="#009E73", ls="-.", lw=1.6, label=r"$h_{\rm no}+\bar{d}$  (shared dir.)"),
    "add_d_samefam": dict(color="#56B4E9", ls="--", lw=1.4, label=r"$h_{\rm no}+d_j$  (same family)"),
    "add_d_crossfam":dict(color="#CC79A7", ls=":",  lw=1.4, label=r"$h_{\rm no}+d_j$  (other family)"),
    "add_d_a0.5":    dict(color="#0072B2", ls=":",  lw=1.0, label=r"$\alpha=0.5$"),
    "add_d_a2":      dict(color="#0072B2", ls="--", lw=1.0, label=r"$\alpha=2$"),
}


def boot(vals, n_boot=2000, seed=0):
    vals = [v for v in vals if v is not None]
    if not vals:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(vals)
    ms = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k
                for _ in range(n_boot))
    return sum(vals) / k, ms[int(0.025 * n_boot)], ms[int(0.975 * n_boot)]


def load_e14(run_dir: pathlib.Path):
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    rows = {}
    for L in summary["layers"]:
        p = run_dir / f"layer_{L:02d}.jsonl"
        if p.exists():
            rows[L] = [json.loads(x) for x in
                       p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return summary, rows


def fig_decomposition(summary, out: pathlib.Path, tag: str):
    """Norms, the angle between the components, and the effective rank."""
    layers = sorted(int(L) for L in summary["per_layer"])
    g = [summary["per_layer"][str(L)]["geometry"] for L in layers]
    fig, ax = plt.subplots(1, 3, figsize=(10.5, 2.9))

    ax[0].plot(layers, [z["norm_d"] for z in g], color="#0072B2", lw=2,
               label=r"$\|d\|$ content")
    ax[0].plot(layers, [z["norm_g"] for z in g], color="#D55E00", lw=2, ls="--",
               label=r"$\|g\|$ presence")
    ax[0].plot(layers, [z["norm_t"] for z in g], color="#999999", lw=1.2, ls=":",
               label=r"$\|t\|$ total")
    ax[0].set_yscale("log")
    ax[0].set_ylabel("norm (log)")
    ax[0].legend(fontsize=7, frameon=False)

    # Not cos(d,g): by the law of cosines it is determined by the three norms
    # and agrees with them to 0.002 here, so plotting it would be plotting the
    # left panel twice. The non-redundant statement is which of the two
    # displacements is longer.
    ax[1].axhline(1.0, color="k", lw=0.6)
    ax[1].plot(layers, [z["norm_g"] / z["norm_t"] for z in g],
               color="#D55E00", lw=2, ls="--", label=r"$\|g\|/\|t\|$")
    ax[1].plot(layers, [z["norm_d"] / z["norm_t"] for z in g],
               color="#0072B2", lw=2, label=r"$\|d\|/\|t\|$")
    ax[1].set_ylabel("share of the total displacement")
    ax[1].legend(fontsize=7, frameon=False, loc="center left")
    ax[1].text(0.30, 0.30, "above 1: the WRONG document moves\nthe state "
                           "further than the skill does",
               transform=ax[1].transAxes, fontsize=6.5, color="#555555",
               va="bottom")

    key_in = "cos_dd_within_family" if "cos_dd_within_family" in g[0] else "cos_dd_same_calc"
    key_x = "cos_dd_cross_family" if "cos_dd_cross_family" in g[0] else "cos_dd_cross_calc"
    ax[2].plot(layers, [z[key_in] for z in g], color="#0072B2", lw=2,
               label="same family/skill")
    ax[2].plot(layers, [z[key_x] for z in g], color="#CC79A7", lw=2, ls="--",
               label="different")
    ax[2].set_ylabel(r"$\cos(d_i,d_j)$")
    ax[2].legend(fontsize=7, frameon=False, loc="lower left")

    for a in ax:
        a.set_xlabel("layer")
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, f"fig-decomp-{tag}")


def fig_causal(summary, rows, out: pathlib.Path, tag: str, cell="R"):
    """The judgment figure: what each injected component repairs, on cell R."""
    layers = sorted(rows)
    keep = set(summary["cells"][cell])
    # add_t is omitted on purpose: h_no + t == h_skill exactly, so its curve
    # lies under `replace_real` and drawing both only hides one of them. It is
    # run and checked -- the two agree to the item -- but it is an identity, not
    # a condition.
    conds = [c for c in ("replace_real", "add_d_a1", "add_g",
                         "add_dbar", "add_d_samefam", "add_d_crossfam")
             if any(f"lp_{c}" in r for r in rows[layers[0]])]

    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    for c in conds:
        m, lo, hi = [], [], []
        for L in layers:
            v = [1.0 if r.get(f"ok_{c}") else 0.0 for r in rows[L]
                 if r["id"] in keep and r.get(f"ok_{c}") is not None]
            a, b, d = boot(v, seed=L)
            m.append(a); lo.append(b); hi.append(d)
        st = STYLE.get(c, dict(label=c))
        ax.plot(layers, m, **st)
        if c in ("add_d_a1", "add_g"):
            ax.fill_between(layers, lo, hi, color=st["color"], alpha=0.13, lw=0)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("layer at which the vector is injected")
    ax.set_ylabel(f"fraction of cell {cell} answered correctly\n(n={len(keep)})")
    ax.set_ylim(-0.03, 1.03)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7.5, frameon=False, ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    save(fig, out, f"fig-causal-{tag}")


def fig_dose(summary, rows, out: pathlib.Path, tag: str, cell="R"):
    layers = sorted(rows)
    keep = set(summary["cells"][cell])
    conds = [c for c in rows[layers[0]][0] if c.startswith("lp_add_d_a")]
    conds = sorted({c[3:] for c in conds})
    if len(conds) < 2:
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    for c in conds:
        m = []
        for L in layers:
            v = [1.0 if r.get(f"ok_{c}") else 0.0 for r in rows[L]
                 if r["id"] in keep and r.get(f"ok_{c}") is not None]
            m.append(sum(v) / len(v) if v else float("nan"))
        ax.plot(layers, m, **STYLE.get(c, dict(label=c)))
    ax.set_xlabel("layer"); ax.set_ylabel(f"cell {cell} accuracy")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7, frameon=False, title=r"$h_{\rm no}+\alpha d$",
              title_fontsize=7)
    fig.tight_layout()
    save(fig, out, f"fig-dose-{tag}")


def fig_windows(run_dir: pathlib.Path, out: pathlib.Path, tag: str):
    """Three transplant channels and the cumulative knockout, on one layer axis.

    The three channels are separate experiments with different receivers, so
    their baselines differ and the curves are not directly comparable in
    height. They are comparable in SHAPE and in where they cross their own
    baseline, which is the claim, so each is drawn against its own baseline as
    a dotted line of the same colour.
    """
    def load(name):
        p = run_dir / name / "summary.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    e10, e12, e13 = load("e10-tierA"), load("e12-tierA"), load("e13-tierA-from")
    if not (e10 and e12 and e13):
        print("  (windows figure skipped: e10/e12/e13 summaries not all present)")
        return
    fig, ax = plt.subplots(1, 2, figsize=(9.6, 3.2), sharex=True)

    ax[0].plot(e10["layers"], e10["acc_real"], color="#0072B2", lw=2,
               label="document span (688 tok)")
    ax[0].axhline(e10["acc_lo"], color="#0072B2", ls=":", lw=1)
    ax[0].plot(e12["layers"], e12["acc_real"], color="#009E73", lw=2,
               label="question span (42--47 tok)")
    ax[0].axhline(e12["acc_lo"], color="#009E73", ls=":", lw=1)
    ax[0].set_ylabel("accuracy after transplant")
    ax[0].set_title("what a position group is sufficient for", fontsize=9)
    ax[0].legend(fontsize=7, frameon=False)

    arms = [("all_to_skill", "#D55E00", "-", "every position $\\to$ document"),
            ("q_to_skill", "#009E73", "--", "question span $\\to$ document"),
            ("last_to_skill", "#0072B2", "-.", "last position $\\to$ document")]
    for key, col, ls, lab in arms:
        if key in e13["accuracy"]:
            ax[1].plot(e13["layers"], e13["accuracy"][key], color=col, ls=ls,
                       lw=2, label=lab)
    ax[1].axhline(e13["base_acc"], color="k", ls=":", lw=1)
    ax[1].set_ylabel("accuracy with attention blocked\nfrom this layer on")
    ax[1].set_title("what is necessary", fontsize=9)
    ax[1].legend(fontsize=7, frameon=False, loc="lower right")

    for a in ax:
        a.set_xlabel("layer")
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, f"fig-windows-{tag}")


def fig_decode(report_path: pathlib.Path, out: pathlib.Path, tag: str):
    """The one contrast the clinical material is uniquely able to make.

    Left: how well each vector identifies WHICH of 41 skills is in the prompt,
    leave-one-out, against the no-document state as the baseline that matters
    (a patient note identifies its own calculator). Right: what injecting the
    same vector back achieves on the same material. The two panels share a
    layer axis on purpose -- the point is that the left one is near ceiling
    exactly where the right one is at floor.
    """
    r = json.loads(report_path.read_text(encoding="utf-8"))
    layers = r["layers"]
    pl = r["per_layer"]
    fig, ax = plt.subplots(1, 2, figsize=(9.4, 3.2))

    ax[0].axhline(pl[str(layers[0])]["ncm_chance"], color="k", ls=":", lw=1)
    ax[0].text(layers[1], pl[str(layers[0])]["ncm_chance"] + 0.02,
               f"chance ({pl[str(layers[0])]['ncm_chance']:.3f})",
               fontsize=7, color="#444444")
    for key, col, ls, lab in (("ncm_d", "#0072B2", "-", r"$d$  content"),
                              ("ncm_g", "#D55E00", "--", r"$g$  presence"),
                              ("ncm_h0", "#999999", ":", r"$h_{\rm no}$  no document")):
        ax[0].plot(layers, [pl[str(L)][key] for L in layers],
                   color=col, ls=ls, lw=2, label=lab)
    ax[0].set_ylim(-0.03, 1.05)
    ax[0].set_ylabel("leave-one-out identification\nof which of 41 skills")
    ax[0].set_title("what the vector encodes", fontsize=9)
    ax[0].legend(fontsize=7, frameon=False, loc="center right")

    for key, col, lab in (("pr_mu_d", "#0072B2", "between skills"),
                          ("pr_resid_d", "#CC79A7", "within a skill")):
        ax[1].plot(layers, [pl[str(L)][key] for L in layers],
                   color=col, lw=2, label=lab)
    ax[1].set_ylabel("effective dimensions of $d$")
    ax[1].set_title("how many dimensions it uses", fontsize=9)
    ax[1].legend(fontsize=7, frameon=False)

    for a in ax:
        a.set_xlabel("layer")
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, out, f"fig-decode-{tag}")


def fig_ladder(out: pathlib.Path):
    """Which positions a transplant can move, against how long the answer is.

    Every cell is stored as the RAW triple it was measured as -- the receiver's
    own accuracy, the patched accuracy, and the donor's -- and the fraction is
    computed here. Storing fractions is how an earlier draft came to compare a
    0.408 against a 1.000 and report that a longer answer made the document
    span *stronger*: the two had different donors (0.467 and 1.000), and as a
    fraction of what was there to recover they are 0.87 and 1.00. The
    difference between the formats is a depth profile, not a height at layer 0.

    Sources, all Qwen3-8B:
      MC and free-form    e10_span / e12_taskspan / e14_decomp on the synthetic
                          items (paper Table~ref{tab:windows2})
      step by step        e10-cot summary.json  acc_real[0]=1.000, lo 0, hi 1
                          e12-cot summary.json  acc_real=0 at every layer
                          e14-cot-k16           0.000 at every layer
      clinical            skillspan merged (n=40), wb_spanpatch --span task,
                          wb_diffvec replace_gold at its best layer
    """
    fig, ax = plt.subplots(figsize=(7.6, 3.5))
    labels = ["multiple choice\n(1 token)",
              "free-form number\n(2--4 tokens)",
              "step by step\n(hundreds)"]
    # (receiver, patched, donor) at the channel's best layer
    cells = {
        "the document's own span": ("#0072B2", "o", {
            0: (0.233, 0.575, 0.550),   # 8B, multiple choice
            1: (0.008, 0.408, 0.467),   # 8B, free-form
            2: (0.000, 1.000, 1.000)}),  # 8B, step by step (e10-cot L0)
        "the question span": ("#009E73", "s", {
            0: (0.233, 0.517, 0.550),
            1: (0.008, 0.025, 0.467),
            2: (0.000, 0.000, 1.000)}),  # e12-cot, every layer
        "the final position": ("#D55E00", "^", {
            0: (0.000, 1.000, 1.000),
            1: (0.000, 0.304, 1.000),
            2: (0.000, 0.000, 1.000)}),  # e14-cot, k=1 and k=16 alike
    }
    med = {"the document's own span": ("#0072B2", "o", (0.175, 1.000, 0.950)),
           "the question span": ("#009E73", "s", (0.175, 0.150, 0.950)),
           "the final position": ("#D55E00", "^", (0.050, 0.150, 0.950))}
    frac = lambda t: (t[1] - t[0]) / max(t[2] - t[0], 1e-9)
    for name, (col, mk, pts) in cells.items():
        xs = sorted(pts)
        ax.plot(xs, [frac(pts[x]) for x in xs], color=col, marker=mk, lw=2,
                ms=7, label=name)
        mcol, mmk, mtriple = med[name]
        ax.plot([2.75], [frac(mtriple)], color=mcol, marker=mmk, ms=8,
                mfc="none", mew=1.8, ls="none")
    ax.axvline(2.38, color="#bbbbbb", lw=1, ls=":")
    ax.axhline(1.0, color="#bbbbbb", lw=0.8, ls="--")
    ax.set_xticks([0, 1, 2, 2.75])
    ax.set_xticklabels(labels + ["clinical skills\n(step by step)"], fontsize=8)
    ax.set_xlim(-0.25, 3.05)
    ax.set_ylim(-0.12, 1.22)
    ax.set_ylabel("recovered, as a fraction of\nthe document's own effect")
    ax.axhline(0, color="k", lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="center left",
              bbox_to_anchor=(0.03, 0.47))
    ax.text(1.04, 1.16, "filled: one model, one item set,\nonly the answer "
                        "format changes\nopen: a different material",
            fontsize=7, color="#555555", va="top")
    fig.tight_layout()
    save(fig, out, "fig-ladder")


def needs_document(rows):
    """Instances from the calculators the RECEIVER never solves.

    Every span arm is measured against a receiver holding a wrong document, and
    on some calculators that wrong document is all the model needed: disrupt it
    with anything and the model falls back on knowledge it already has.
    Measured on the calculators whose receiver is non-zero, norm-matched
    Gaussian noise written into the span scores 0.500 and a foreign donor
    0.875; on the calculators whose receiver is zero the same arms score 0.000
    and 0.059. Pooling the two reports partial transfer where there is none.

    The criterion is per calculator, because "this model can do this calculator
    unaided" is a property of the calculator, and it conditions on the receiver
    -- a control -- and on no intervention arm.
    """
    acc = {}
    for r in rows.values():
        if "receiver" in r:
            acc.setdefault(r["calculator_id"], []).append(bool(r["receiver"]))
    keep = {c for c, v in acc.items() if sum(v) == 0}
    return {k: r for k, r in rows.items() if r.get("calculator_id") in keep}


def load_spanvec(paths, restrict=None):
    """{arm: [bool, ...]} merged across shards, plus the note count.

    Refuses to merge shards that used different receivers. The receiver defines
    the floor every arm is measured against, and two of ours differ by only
    0.01 in accuracy, so a mixed merge is invisible in the output and wrong in
    the argument. The rows carry the filler they were run with; this checks it
    rather than trusting the file names.
    """
    rows = {}
    fillers = set()
    for p in paths:
        for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            iid = r.get("instance_id")
            if not iid:
                continue
            # a row from before the field existed counts as its own kind,
            # so old and new runs cannot be merged silently either
            # cell, filler and prompt order all define what the numbers
            # mean; an R-cell run merged with an F-cell one reads gold 0.40
            # instead of 0.90 and nothing downstream can tell
            fillers.add((r.get("cells_n", "?"),
                         r.get("model", "?"),
                         r.get("filler", "unrecorded"),
                         r.get("format", "doc_first"),
                         r.get("cell", "?")[:1] if isinstance(r.get("cell"), str)
                         else "?"))
            tgt = rows.setdefault(iid, {})
            tgt["calculator_id"] = r.get("calculator_id",
                                         tgt.get("calculator_id"))
            for k, v in r.items():
                if k.startswith("ok_"):
                    tgt[k[3:]] = bool(v)
    if len(fillers) > 1:
        raise SystemExit(
            f"refusing to merge runs with different receivers: {sorted(fillers)}\n"
            f"  files: {list(paths)}\n"
            f"  the receiver is the floor every arm is measured against, and "
            f"two of ours differ by 0.01, so mixing them is invisible here and "
            f"wrong in the paper")
    if restrict == "needs_document":
        rows = needs_document(rows)
    by = {}
    for r in rows.values():
        for k, v in r.items():
            if k != "calculator_id":
                by.setdefault(k, []).append(v)
    return by, len(rows)


def _resolve(by, arm, layer=None):
    """Arm keys carry the layer they were run at (`real_L8`); baselines do not.

    Callers name arms, not keys, because the same arm is run at several layers
    across shards and a figure that silently picked whichever key sorted first
    would be wrong in a way nothing downstream could catch.
    """
    if arm in by:
        return arm
    if layer is not None and f"{arm}_L{layer}" in by:
        return f"{arm}_L{layer}"
    cand = [k for k in by if k.rsplit("_L", 1)[0] == arm and "_L" in k]
    return cand[0] if len(cand) == 1 else None


def _frac(by, key, floor_key="receiver", top_key="gold_in_context"):
    """Where an arm sits between the receiver baseline and the gold ceiling.

    Raw accuracy is not comparable across formats: doc-last lifts the receiver
    from 0.175 to 0.350 and lowers gold from 0.950 to 0.925, so the same arm at
    the same accuracy means something different in the two. The fraction of the
    recoverable range is the quantity that transfers.
    """
    key = _resolve(by, key)
    if key is None:
        return None
    f = sum(by[floor_key]) / len(by[floor_key])
    t = sum(by[top_key]) / len(by[top_key])
    m = sum(by[key]) / len(by[key])
    return (m - f) / max(t - f, 1e-9)


def fig_channels(dose, ctrl, diffvec, out: pathlib.Path):
    """The paper's first figure: same model, same notes, same decomposition.

    Every arm that injects at the last prompt position sits on the no-skill
    baseline. The same content, written over the skill's own token span,
    recovers everything. The contrast is the result; the individual arm values
    are secondary, which is why they share one axis.
    """
    by, n = load_spanvec(list(dose) + list(ctrl),
                         restrict="needs_document")
    dv = {}
    for p in diffvec:
        for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            L = r.get("layer")
            for k, v in r.items():
                if k.startswith("ok_") and isinstance(v, bool):
                    dv.setdefault((k[3:], L), []).append(v)
    # One bar per arm, at the layer that arm does best on. Pooling the layers
    # would let a strong layer be hidden by three weak ones, and the claim here
    # is that no layer works -- so the figure has to show the best one.
    best = {}
    for (arm, _), v in dv.items():
        m = sum(v) / len(v)
        if arm not in best or m > sum(best[arm]) / len(best[arm]):
            best[arm] = v
    dv = best

    last = [(r"replace with $h_{\rm gold}$", "replace_gold"),
            (r"$+\,d$  (content)", "add_d"),
            (r"$+\,g$  (presence)", "add_g"),
            (r"$+\,d_j$, same skill", "add_d_samecalc"),
            (r"$+\,d_j$, another skill", "add_d_crosscalc")]
    span = [(r"$h_{\rm recv}+d$  $(\alpha\!=\!1)$", "real"),
            (r"$h_{\rm recv}+0.5\,d$", "a0.5"),
            (r"$+\,d_j$, another skill", "dcross"),
            (r"$+\,d$, positions shuffled", "dshuf"),
            (r"noise, $\|\cdot\|$ matched", "drand")]

    # Horizontal bars: six arms with multi-word names do not fit under a
    # vertical axis at this width without overlapping, and an earlier version
    # of this figure was unreadable for exactly that reason.
    fig, (axT, axB) = plt.subplots(2, 1, figsize=(4.9, 3.2), sharex=True,
                                   gridspec_kw={"height_ratios": [5, 6]})
    base = sum(dv["none"]) / len(dv["none"])
    gold = sum(dv["gold"]) / len(dv["gold"])
    recv = sum(by["receiver"]) / len(by["receiver"])
    # each panel is read on its own items, so each gets its own gold line: the
    # restricted span items read 1.00 and inheriting the top panel's 0.95
    # drew the skill below the transplant
    gold_span = sum(by["gold_in_context"]) / len(by["gold_in_context"])
    for ax, items, src, title, floor, floor_lab, gold in (
            (axT, last, dv, "written at the last prompt position "
             f"($n={len(dv.get('gold', []))}$)", base, "no skill", gold),
            (axB, span, by, "written over the skill's own span "
             f"($n={n}$)", recv, "filler skill, unpatched", gold_span)):
        names = [a for a, _ in items]
        vals, los, his = [], [], []
        for _, k in items:
            key = _resolve(src, k) if src is by else k
            v = src.get(key, []) if key else []
            m, lo, hi = boot(v) if v else (float("nan"),) * 3
            vals.append(m); los.append(max(m - lo, 0)); his.append(max(hi - m, 0))
        y = list(range(len(names)))[::-1]
        cols = ["#0072B2"] + ["#a6cee3"] * (len(names) - 1)
        ax.barh(y, vals, color=cols, height=0.6, edgecolor="#31688e", lw=0.4)
        ax.errorbar(vals, y, xerr=[los, his], fmt="none", ecolor="#333333",
                    capsize=2, lw=0.9)
        for yi, (m, h) in zip(y, zip(vals, his)):
            if m == m:
                ax.text(min(m + h + 0.02, 1.16), yi, f"{m:.2f}", va="center",
                        fontsize=7, color="#333333")
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=7.6)
        ax.axvline(gold, color="#009E73", lw=1.1, ls="--", zorder=0)
        ax.axvline(floor, color="#D55E00", lw=1.1, ls=":", zorder=0)
        ax.set_title(title, fontsize=8.8, loc="left", pad=6)
        ax.set_xlim(0, 1.12)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5)
        # floor labels go UNDER the lowest bar, not over the title
        ax.text(floor + 0.012, -0.72, f"{floor_lab} ({floor:.2f})",
                fontsize=6.6, color="#D55E00", va="center")
        ax.set_ylim(-1.1, len(names) - 0.4)
    for ax, gl in ((axT, sum(dv["gold"]) / len(dv["gold"])), (axB, gold_span)):
        ax.text(gl - 0.012, -0.72, f"gold skill ({gl:.2f})",
                fontsize=6.6, color="#009E73", va="center", ha="right")
    axB.set_xlabel("accuracy on the rescued items the skill is needed for",
                   fontsize=8)
    # no suptitle: the caption names the model and material, and a title wider
    # than the axes sets the tight bounding box and shrinks the plot inside it
    fig.tight_layout()
    save(fig, out, "fig-channels-medcalc")


def fig_dose_medcalc(paths, out: pathlib.Path):
    """Dose in alpha, its norm-matched twin, and the controls.

    The rescaled arms exist because h_recv + 2d is longer than any state the
    model sees at those positions, so without them the curve confounds how much
    of the content is written with how big the result is. They land on the
    plain arms to within a point, which is the answer: the effect is not about
    magnitude.
    """
    by, n = load_spanvec(paths, restrict="needs_document")
    alphas, ys = [], []
    for a in (0.25, 0.5, 0.6, 0.75, 1.0, 1.5, 2.0, 3.0):
        key = "real" if a == 1.0 else f"a{a:g}"
        f = _frac(by, key)
        if f is not None:
            alphas.append(a); ys.append(f)
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.plot(alphas, ys, "o-", color="#0072B2", lw=2.2, ms=6,
            label=r"$h_{\rm recv}+\alpha\,d$", zorder=3)
    rn_a, rn_y = [], []
    for a in (0.5, 2.0, 3.0):
        f = _frac(by, f"a{a:g}r")
        if f is not None:
            rn_a.append(a); rn_y.append(f)
    if rn_a:
        ax.plot(rn_a, rn_y, "s", color="#56B4E9", ms=9, mfc="none", mew=2,
                ls="none", label=r"same, rescaled to $\|h_{\rm gold}\|$",
                zorder=4)
    refs = [("the document itself", None, "#009E73", "--", 1.0),
            (r"$d$ from another skill", "dcross", "#D55E00", "--", None),
            (r"$d$, span positions permuted", "dshuf", "#CC79A7", "-.", None),
            (r"norm-matched noise", "drand", "#999999", ":", None),
            (r"the receiver, unpatched", None, "#8c6d1f", "-", 0.0)]
    # The controls all land inside a 0.16-wide band, so they go in the legend
    # rather than as text on the lines: four labels stacked to avoid collision
    # sit nowhere near the line they name, which is worse than no label.
    for label, key, col, ls, fixed in refs:
        f = fixed if key is None else _frac(by, key)
        if f is None:
            continue
        ax.axhline(f, color=col, ls=ls, lw=1.2,
                   label=f"{label}  ({f:+.2f})")
    ax.set_xlabel(r"$\alpha$")
    ax.set_ylabel("recovered, as a fraction of\nthe document\u2019s own effect")
    ax.set_xlim(0.05, 3.2)
    ax.set_ylim(-0.3, 1.25)
    ax.set_xticks([0, 0.5, 1, 1.5, 2, 2.5, 3])
    ax.legend(fontsize=7, frameon=False, loc="center left",
              bbox_to_anchor=(1.01, 0.5))
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(f"layer 8, the document's own span, {n} rescued clinical "
                 f"items", fontsize=9)
    fig.tight_layout()
    save(fig, out, "fig-dose-medcalc")


def load_geometry(paths):
    """{layer: {stat: mean}} from a wb_spanvec --mode geometry run."""
    acc = {}
    for path in paths:
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            for g in r.get("geom", []):
                d = acc.setdefault(g["layer"], {})
                for k, v in g.items():
                    # the robust-PR helper also records WHICH positions and
                    # dimensions were dropped; those are lists and have no mean
                    if k != "layer" and isinstance(v, (int, float)):
                        d.setdefault(k, []).append(v)

    def summarise(k, v):
        # the plain participation ratio is bimodal past the massive-activation
        # layer -- three quarters of items at 1.0 and the rest at 75 -- so its
        # mean describes no item. Every PR column is summarised by the median.
        if k.startswith("pr_") or "_pr_" in k:
            return sorted(v)[len(v) // 2]
        return sum(v) / len(v)

    return {L: {k: summarise(k, v) for k, v in d.items()}
            for L, d in acc.items()}


def fig_depth_medcalc(span_paths, geom_paths, out: pathlib.Path):
    """How deep the document's own span can still be handed over, against what
    the span's representation is doing at the same depth.

    Left axis: a single-layer transplant of the document span, as a fraction of
    what the document itself recovers. Right axis: the participation ratio of
    that span's positions, centred.

    An earlier version of this figure plotted only the plain participation
    ratio, which collapses in the same interval as the transplant, and the paper
    read the two together as a mechanism. The collapse is massive activations:
    one token per document acquires a state ~150x the span median norm at a
    fixed layer. So the plain curve is kept -- it is what the usual recipe
    produces, and readers will have seen it elsewhere -- and the corrected curve
    is drawn next to it. They separate exactly at the emergence layer, and only
    the plain one collapses.
    """
    by, n = load_spanvec(span_paths, restrict="needs_document")
    floor = sum(by["receiver"]) / len(by["receiver"])
    top = sum(by["gold_in_context"]) / len(by["gold_in_context"])
    pts = []
    for k in by:
        if k.startswith("real_L") and k != "real_alllayers":
            L = int(k.split("_L")[1])
            m, lo, hi = boot(by[k])
            f = lambda x: (x - floor) / max(top - floor, 1e-9)
            pts.append((L, f(m), f(lo), f(hi)))
    pts.sort()
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.fill_between(xs, [p[2] for p in pts], [p[3] for p in pts],
                    color="#0072B2", alpha=0.15, lw=0)
    ax.plot(xs, ys, "o-", color="#0072B2", lw=2, ms=5,
            label="transplant of the document span")
    if "real_alllayers" in by:
        m, _, _ = boot(by["real_alllayers"])
        v = (m - floor) / max(top - floor, 1e-9)
        ax.axhline(v, color="#0072B2", ls="--", lw=1.2)
        ax.text(30, v - 0.07, f"every layer at once ({v:.2f})", fontsize=7,
                color="#0072B2", ha="right")
    ax.axhline(0, color="#D55E00", ls=":", lw=1.2)
    ax.text(30, -0.09, "the receiver, unpatched", fontsize=7, color="#D55E00",
            ha="right")
    ax.set_xlabel("layer the span is written at")
    ax.set_ylabel("recovered, as a fraction of\nthe document's own effect")
    ax.set_ylim(-0.16, 1.18)
    ax.spines[["top"]].set_visible(False)

    geo = load_geometry(geom_paths)
    if geo:
        ax2 = ax.twinx()
        gl = sorted(geo)
        ax2.plot(gl, [geo[L]["pr_d"] for L in gl], "s--", color="#999999",
                 lw=1.3, ms=4,
                 label="participation ratio of $d$, as usually computed")
        if any("d_pr_droppos" in geo[L] for L in gl):
            gr = [L for L in gl if "d_pr_droppos" in geo[L]]
            ax2.plot(gr, [geo[L]["d_pr_droppos"] for L in gr], "s-",
                     color="#CC79A7", lw=1.8, ms=4,
                     label="same, 4 massive-activation positions removed")
        ax2.set_ylabel("participation ratio (centred)", color="#CC79A7")
        ax2.tick_params(axis="y", labelcolor="#CC79A7")
        ax2.spines[["top"]].set_visible(False)
        ax2.set_ylim(0, 105)
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False,
                  loc="lower left", bbox_to_anchor=(0.02, 0.07))
    else:
        ax.legend(fontsize=7, frameon=False)
    ax.set_title(f"Qwen3-8B, {n} rescued clinical items", fontsize=9)
    fig.tight_layout()
    save(fig, out, "fig-depth-medcalc")


def fig_skilltask(paths, out: pathlib.Path):
    """What the content vector contains once it is allowed to contain anything.

    With the document first -- the format the behavioural runs use -- causal
    attention makes the document's states independent of the patient note, so
    within a calculator d is one tensor and every cross-note arm is an
    identity. Moving the document after the question lets d see the note. What
    then transfers is the part shared across notes; the note-specific
    remainder, injected alone, lands below the receiver's own baseline.
    """
    by, n = load_spanvec(paths, restrict="needs_document")
    items = [(r"$d_i$ (own instance)", "real"),
             (r"$\bar{d}_{\neg i}$ (mean of the others)", "dbar"),
             (r"$d_j$ (one other instance)", "dother"),
             (r"$d_i^{\parallel}$ (along that mean)", "dpar"),
             (r"$d_i^{\perp}$ (the rest)", "dperp"),
             (r"$\bar{d}$, a related skill", "dnear"),
             (r"$\bar{d}$, an unrelated skill", "dfar"),
             (r"$\bar{d}$, another skill", "dcross"),
             (r"$\bar{d}$, every skill averaged", "dall"),
             (r"positions shuffled", "dshuf"),
             (r"norm-matched noise", "drand")]
    rows = [(lab, _frac(by, k)) for lab, k in items]
    rows = [(lab, v) for lab, v in rows if v is not None]
    fig, ax = plt.subplots(figsize=(6.6, 0.40 * len(rows) + 1.6))
    ys = range(len(rows))[::-1]
    cols = ["#0072B2" if v > 0.5 else "#56B4E9" if v > 0.05 else "#999999"
            for _, v in rows]
    ax.barh(list(ys), [v for _, v in rows], color=cols, height=0.62)
    for y, (_, v) in zip(ys, rows):
        # value labels always outside the bar, on the side the bar points
        ax.text(v + (0.015 if v >= 0 else -0.015), y, f"{v:+.2f}", fontsize=7,
                va="center", ha="left" if v >= 0 else "right",
                clip_on=False)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([lab for lab, _ in rows], fontsize=8)
    ax.axvline(0, color="k", lw=0.8)
    ax.axvline(1, color="#009E73", lw=1, ls="--")
    ax.text(1.0, len(rows) - 0.35, "the document itself", fontsize=7,
            color="#009E73", ha="center", va="bottom")
    ax.set_xlabel("recovered, as a fraction of the document's own effect")
    ax.set_xlim(-0.62, 1.18)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_ylim(-0.7, len(rows) + 0.15)
    ax.set_title(f"document placed after the question, layer 8, "
                 f"{n} rescued items", fontsize=9, pad=14)
    fig.tight_layout()
    save(fig, out, "fig-skilltask-medcalc")


def fig_rank(paths, out: pathlib.Path, ladder=None, family=None):
    """How many directions of the content matrix the effect needs, and that the
    number does not scale with the model.

    At a layer where the transplant still recovers everything, the content
    matrix is truncated to rank k across the span's positions before it is
    written. The dashed control keeps the BOTTOM k directions instead --- same
    rank, the discarded half of the spectrum. Without it, "k directions
    suffice" could not be told apart from "any k directions will do".

    The second curve is the same experiment on Qwen3-0.6B, whose residual
    stream is four times narrower. A width-proportional account puts its knee
    at k~12; it is in the same place as the 8B's. An earlier version of this
    figure shaded the span's participation ratio behind the curve; that number
    turned out to be a massive-activation artefact and the shading is gone.
    """
    def curve(src, keys):
        base = sum(src["receiver"]) / len(src["receiver"])
        top = sum(src["gold_in_context"]) / len(src["gold_in_context"])
        g = lambda x: (x - base) / max(top - base, 1e-9)
        ks, ys, los, his = [], [], [], []
        for k in keys:
            key = _resolve(src, f"rank{k}")
            if not key or key not in src:
                continue
            m, lo, hi = boot(src[key])
            ks.append(k); ys.append(g(m))
            los.append(g(m) - g(lo)); his.append(g(hi) - g(m))
        return ks, ys, los, his, g

    by, n = load_spanvec(paths, restrict="needs_document")
    ks, ys, los, his, g = curve(by, (1, 2, 4, 8, 16, 32, 64, 128))
    fig, ax = plt.subplots(figsize=(5.8, 3.7))
    ax.errorbar(ks, ys, yerr=[los, his], fmt="o-", color="#0072B2", lw=2,
                ms=5.5, capsize=3,
                label=f"Qwen3-8B, layer 8 ($d\\!=\\!4096$)")
    lo_ks, lo_ys = [], []
    for k in (16, 64):
        key = _resolve(by, f"rank{k}lo")
        if key and key in by:
            lo_ks.append(k)
            lo_ys.append(g(sum(by[key]) / len(by[key])))
    if lo_ks:
        ax.plot(lo_ks, lo_ys, "s--", color="#D55E00", ms=7, mfc="none", mew=1.8,
                label="bottom $k$ directions (control)")
    if ladder:
        by2, n2 = load_spanvec(ladder, restrict="needs_document")
        k2, y2, l2, h2, _ = curve(by2, (4, 16, 24, 32, 40, 48, 56, 64, 128))
        if k2:
            ax.errorbar(k2, y2, yerr=[l2, h2], fmt="^-", color="#56B4E9",
                        lw=1.6, ms=5, capsize=2, alpha=0.95,
                        label="Qwen3-0.6B, layer 6 ($d\\!=\\!1024$)")
            ax.annotate("width-proportional\nprediction for 0.6B", xy=(12, 0.5),
                        xytext=(4.2, 0.72), fontsize=6.8, color="#777777",
                        ha="center",
                        arrowprops=dict(arrowstyle="->", color="#999999",
                                        lw=0.9))
            ax.axvline(12, color="#999999", ls=":", lw=1.0, zorder=0)
    if family:
        # a second model family at the same width: whether k* is a property of
        # the skill or of the model is decided here, not by the 0.6B curve
        by3, _ = load_spanvec(family, restrict="needs_document")
        k3, y3, l3, h3, _ = curve(by3, (4, 16, 32, 64, 128))
        if k3:
            ax.errorbar(k3, y3, yerr=[l3, h3], fmt="D-", color="#CC79A7",
                        lw=1.6, ms=4.5, capsize=2, alpha=0.95,
                        label="Mistral-7B, layer 4 ($d\\!=\\!4096$)")
    ax.axhline(1.0, color="#009E73", ls="--", lw=1.1, zorder=0)
    # rho is normalised by the gold prompt, not by the untruncated transplant
    # (0.87 / 0.89 / 0.92 on the three models), so this line is the skill
    ax.text(130, 1.02, "the skill in the prompt", fontsize=7,
            color="#009E73", ha="right")
    ax.axhline(0.0, color="#8c6d1f", ls="-", lw=1.0, zorder=0)
    ax.text(1.05, -0.10, "the receiver, unpatched", fontsize=7,
            color="#8c6d1f")
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8, 16, 32, 64, 128])
    ax.set_xticklabels([1, 2, 4, 8, 16, 32, 64, 128], fontsize=8)
    ax.set_xlabel("rank $k$ the content matrix is truncated to, before "
                  "injection", fontsize=9)
    ax.set_ylabel("recovered, as a fraction of\nthe skill's own effect",
                  fontsize=9)
    ax.set_ylim(-0.20, 1.18)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=7.2, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.20), ncol=2, columnspacing=1.6,
              handletextpad=0.5)
    ax.set_title("the same truncation on three models, each injected before "
                 "its own handover", fontsize=8.6)
    fig.tight_layout()
    save(fig, out, "fig-rank-medcalc")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--e14", action="append", default=[],
                    help="run dir; repeatable, as tag=path")
    ap.add_argument("--windows", default=None,
                    help="a run dir containing e10-tierA / e12-tierA / "
                         "e13-tierA-from")
    ap.add_argument("--ladder", action="store_true",
                    help="the channel x answer-length summary figure")
    ap.add_argument("--decode", default=None,
                    help="a wb_vecstats report.json")
    ap.add_argument("--medcalc", default=None,
                    help="the fetched/by-host root holding the real-skill "
                         "shards; the arm-sharded files are globbed from it")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.ladder:
        fig_ladder(out)
        print("ladder figure written")
    if args.medcalc:
        root = pathlib.Path(args.medcalc)
        g = lambda pat: sorted(str(q) for q in root.glob(pat))
        # pick ONE generation of runs for the whole figure; load_spanvec
        # refuses a mix, so this decides rather than discovers
        # NOTE: the full-dataset runs cannot be merged into this figure.
        # load_spanvec refuses runs with different receivers, and full-* uses
        # the fixedskill filler while the spanvec-fs-* generation does not;
        # merging them would put arms measured against different baselines on
        # one axis. Figure 1 therefore stays on the development set, which its
        # caption states, and the full-scale dose numbers are in the text.
        newgen = g("*/spanvec-fs-first.jsonl")
        if newgen:
            dose = newgen
            ctrl = g("*/spanvec-fs-parts.jsonl") + g("*/spanvec-fs-quarters.jsonl")
        else:
            dose = fulldose or g("*/spanvec-dose.jsonl")
            ctrl = g("*/spanvec-ctrl.jsonl")
        # L* only, as tables.py globs it: "*" also matched diffvec-cot-corrupted-
        # L2030, a run against a different control, and pooled it into layers
        # 20/30 -- add_d read 3/40 in the figure against 3/20 in tab:battery
        dv = g("*/diffvec-cot-L*.jsonl")
        if dose and ctrl and dv:
            fig_channels(dose, ctrl, dv, out)
            print("channels figure")
        allsv = ((g("*/spanvec-fs-first.jsonl") + g("*/spanvec-fs-parts.jsonl")
                  + g("*/spanvec-fs-quarters.jsonl")
                  + g("*/spanvec-fs-dose.jsonl")) if newgen else
                 (g("*/spanvec-dose.jsonl") + g("*/spanvec-ctrl.jsonl")
                  + g("*/spanvec-doseR.jsonl")))
        if allsv:
            fig_dose_medcalc(allsv, out)
            print("dose figure")
        span = g("*/skillspan-*.jsonl")
        if span:
            fig_depth_medcalc(span, g("*/prdiag-8b-df.jsonl")
                              or g("*/spanvec-fs-geomf.jsonl")
                              or g("*/spanvec-geom-first.jsonl"), out)
            print("depth figure")
        dlnew = g("*/spanvec-fs-dl.jsonl")
        # full-dataset rank curve: every rescued item, not the forty-calculator
        # sample. full-battery-a supplies the baselines and the untruncated arm.
        rk = (g("*/full-rank-a.jsonl") + g("*/full-rank-b.jsonl")
              + g("*/full-battery-a.jsonl")) or g("*/spanvec-rank-*.jsonl")
        if rk:
            fig_rank(rk, out,
                     ladder=g("*/lad06-fine.jsonl") or g("*/lad06-rank.jsonl"))
            print("rank figure")
        dl = (dlnew + g("*/spanvec-fs-dlctrl.jsonl") if dlnew else
              g("*/spanvec-doclast.jsonl") + g("*/spanvec-dl-ctrl.jsonl"))
        if dl:
            fig_skilltask(dl, out)
            print("skill/task figure")
    if args.decode:
        fig_decode(pathlib.Path(args.decode), out, "medcalc")
        print(f"decode figure from {args.decode}")
    if args.windows:
        fig_windows(pathlib.Path(args.windows), out, "tierA")
        print(f"windows figure from {args.windows}")
    for spec in args.e14:
        tag, _, path = spec.partition("=")
        if not path:
            tag, path = "e14", spec
        run = pathlib.Path(path)
        summary, rows = load_e14(run)
        fig_decomposition(summary, out, tag)
        if rows:
            fig_causal(summary, rows, out, tag)
            fig_dose(summary, rows, out, tag)
        print(f"{tag}: figures from {run}")


if __name__ == "__main__":
    main()


