#!/usr/bin/env python3
"""Figure 2 (fig-rank-medcalc): the rank curve on three models, full data.

    cd paper && MPLCONFIGDIR=/tmp/skillvector-mpl python3 fig_rank_full.py

What changed from the figs.py version, and why:

  * Mistral-7B is drawn. figs.py had a `family=` branch that main() never
    called, so the caption quoted a Mistral knee the figure did not show.
  * Qwen3-0.6B is the post-fix full run. figs.py drew `lad06-fine`, a pre-fix
    run with only k=24..64, under a caption that says "after the fix".
  * The bottom-k control covers the grid instead of two points: it was only
    ever run at k=16 and 64.
  * Every model is every rescued item of every calculator with at least two,
    restricted per run, and the intervals bootstrap calculators (the unit the
    restriction and the dependence are defined on), not items.

One panel per model, shared y. Solid: top-k centred directions (Eq. rank);
dashed, hollow: bottom-k. The dotted horizontal line is that model's own
untruncated transplant. k* is the pre-registered grid knee (replication.kstar).
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import replication as rep

HERE = pathlib.Path(__file__).resolve().parent
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42,
                     "legend.fontsize": 6.8})

# (label, width, inject layer, [full tags], [fallback tags], colour, width-prediction)
MODELS = [
    ("Qwen3-8B", 4096, 8,
     ["full-battery-a", "full-rank-a", "full-rank-b", "x8-rank-x", "x8-rank-lo"],
     ["full-battery-a", "full-rank-a", "full-rank-b"], "#0072B2"),
    ("Qwen3-0.6B", 1024, 6,
     ["q06-bat-a", "q06-rank-a", "q06-rank-b", "q06-rank-lo"],
     ["fixmask-lad06-rank"], "#56B4E9"),
    ("Mistral-7B", 4096, 4,
     ["mis-bat-a", "mis-rank-a", "mis-rank-b", "mis-rank-lo"],
     ["mis3-rank-L4"], "#CC79A7"),
]
TOP = (1, 2, 4, 8, 16, 24, 32, 40, 48, 56, 64, 96, 128, 256)
BOTTOM = (4, 16, 32, 64, 128)


def have(tags):
    return all(any(rep.BY.glob(f"*/{t}.jsonl")) for t in tags)


def curve(groups, L, ks, lo=False):
    out = []
    for k in ks:
        key = f"ok_rank{k}{'lo' if lo else ''}_L{L}"
        v = rep.rho(groups, key)
        if v is None:
            continue
        a, b = rep.boot(groups, key)
        out.append((k, v, a, b))
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE))
    out = pathlib.Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.35), sharey=True, layout="constrained")
    summary = {}
    for ax, (name, width, L, tags, fallback, col) in zip(axes, MODELS):
        # Share the table's completed-run selection. File existence alone is
        # insufficient: current new rank shards contain only partial samples.
        used = next(row[6] for row in rep.resolved_rows()
                    if row[0] == "MedCalc" and row[1] == name)
        groups = rep.restricted(rep.load(used))
        n = sum(len(v) for v in groups.values())
        top, bot = curve(groups, L, TOP), curve(groups, L, BOTTOM, lo=True)
        full = rep.rho(groups, f"ok_real_L{L}")
        fa, fb = rep.boot(groups, f"ok_real_L{L}")
        ks = rep.kstar(groups, L)
        summary[name] = {"tags": used, "n": n, "groups": len(groups), "full": full,
                         "full_ci": [fa, fb], "kstar": ks,
                         "top": {k: [v, a, b] for k, v, a, b in top},
                         "bottom": {k: [v, a, b] for k, v, a, b in bot}}
        if top:
            ax.errorbar([k for k, *_ in top], [v for _, v, *_ in top],
                        yerr=[[max(v - a, 0) for _, v, a, _ in top],
                              [max(b - v, 0) for _, v, _, b in top]],
                        color=col, marker="o", ms=3.6, lw=1.6, capsize=1.6,
                        elinewidth=0.7, label="top $k$ directions")
        if bot:
            ax.errorbar([k for k, *_ in bot], [v for _, v, *_ in bot],
                        yerr=[[max(v - a, 0) for _, v, a, _ in bot],
                              [max(b - v, 0) for _, v, _, b in bot]],
                        color=col, marker="s", ms=3.8, lw=1.1, ls="--", mfc="white",
                        mew=1.1, capsize=1.6, elinewidth=0.7, label="bottom $k$ (control)")
        if full is not None:
            ax.axhline(full, color=col, ls=":", lw=1.0)
            ax.text(1.05, full + 0.03, f"untruncated {full:.2f}", fontsize=6.4, color="#333333")
        if ks:
            ax.axvline(ks, color="#777777", lw=0.8, ls="-.", zorder=0)
            ax.text(ks * 1.08, 0.04, f"$k^*={ks:.0f}$", fontsize=6.6, color="#333333")
        if name == "Qwen3-0.6B":
            ax.axvline(12, color="#bbbbbb", lw=0.8, ls=":", zorder=0)
            ax.text(12 / 1.12, 0.62, "width-proportional\nprediction", fontsize=5.8,
                    color="#777777", ha="right")
        ax.axhline(0, color="#8c6d1f", lw=0.8, zorder=0)
        ax.set_xscale("log", base=2)
        ax.set_xticks([4, 16, 64, 128])
        ax.set_xticklabels(["4", "16", "64", "128"])
        ax.set_xlim(3, 160)
        ax.set_ylim(-0.08, 1.12)
        ax.set_title(f"{name} ($D={width}$, layer {L})", loc="left")
        ax.text(0.98, 0.02, f"n = {n} ({len(groups)} calc.)", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=6.2, color="#555555")
        ax.set_xlabel("retained centred directions $k$")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#eeeeee", lw=0.6, zorder=-1)
    axes[0].set_ylabel(r"recovery $\rho$")
    axes[0].legend(loc="upper left", frameon=False, bbox_to_anchor=(0.0, 0.80))
    fig.savefig(out / "fig-rank-medcalc.pdf", bbox_inches="tight")
    fig.savefig(out / "fig-rank-medcalc.png", bbox_inches="tight", dpi=200)
    (out / "fig-rank-values.json").write_text(json.dumps(summary, indent=1))
    for k, v in summary.items():
        print(k, v["tags"], "n", v["n"], "groups", v["groups"], "full %.2f" % v["full"],
              "k* %s" % (None if v["kstar"] is None else round(v["kstar"], 1)))
        print("   top   ", {kk: round(x[0], 2) for kk, x in v["top"].items()})
        print("   bottom", {kk: round(x[0], 2) for kk, x in v["bottom"].items()})


if __name__ == "__main__":
    main()
