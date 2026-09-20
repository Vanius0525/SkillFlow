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

All three models share one axis, as in the figs.py layout, so the knees can be
compared directly. Solid: top-k centred directions (Eq. rank); dashed, hollow
squares in the model's colour: bottom-k. rho is normalised by the correct skill
in the prompt (1.0) and the unpatched receiver (0.0); each model's untruncated
transplant is in the caption. k* is the pre-registered grid knee
(replication.kstar) and is quoted in the legend with n.
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import replication as rep

HERE = pathlib.Path(__file__).resolve().parent
plt.rcParams.update({"pdf.fonttype": 42})

# (label, width, inject layer, [full tags], [fallback tags], colour, marker style)
MODELS = [
    ("Qwen3-8B", 4096, 8,
     ["full-battery-a", "full-rank-a", "full-rank-b", "x8-rank-x", "x8-rank-lo"],
     ["full-battery-a", "full-rank-a", "full-rank-b"], "#0072B2",
     dict(marker="o", lw=2.0, ms=5.5, capsize=3)),
    ("Qwen3-0.6B", 1024, 6,
     ["q06-bat-a", "q06-rank-a", "q06-rank-b", "q06-rank-lo"],
     ["fixmask-lad06-rank"], "#56B4E9",
     dict(marker="^", lw=1.6, ms=5.0, capsize=2)),
    ("Mistral-7B", 4096, 4,
     ["mis-bat-a", "mis-rank-a", "mis-rank-b", "mis-rank-lo"],
     ["mis3-rank-L4"], "#CC79A7",
     dict(marker="D", lw=1.6, ms=4.5, capsize=2)),
]
TOP = (1, 2, 4, 8, 16, 24, 32, 40, 48, 56, 64, 96, 128, 192, 256, 384, 512)
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
    fig, ax = plt.subplots(figsize=(5.8, 3.7))
    summary = {}
    # a small multiplicative dodge on the log axis keeps overlapping error bars
    # of the three models legible at the same k
    dodge = {"Qwen3-8B": 1.0, "Qwen3-0.6B": 2 ** -0.07, "Mistral-7B": 2 ** 0.07}
    for name, width, L, tags, fallback, col, sty in MODELS:
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
        dx = dodge[name]
        label = f"{name}, layer {L} ($D\\!=\\!{width}$, $n\\!=\\!{n}$)"
        if ks:
            label += f", $k^*\\!=\\!{ks:.0f}$"
        if top:
            ax.errorbar([k * dx for k, *_ in top], [v for _, v, *_ in top],
                        yerr=[[max(v - a, 0) for _, v, a, _ in top],
                              [max(b - v, 0) for _, v, _, b in top]],
                        color=col, alpha=0.95, label=label, **sty)
        if bot:
            # the control keeps the discarded half of the spectrum at the same
            # rank; drawn without error bars, as in the original layout
            ax.plot([k * dx for k, *_ in bot], [v for _, v, *_ in bot], ls="--",
                    marker="s", color=col, ms=6, mfc="white", mew=1.5, lw=1.2)
    ax.plot([], [], ls="--", marker="s", color="#666666", ms=6, mfc="white", mew=1.5,
            lw=1.2, label="bottom $k$ directions (control)")
    ax.annotate("width-proportional\nprediction for 0.6B", xy=(12, 0.5),
                xytext=(4.2, 0.72), fontsize=6.8, color="#777777", ha="center",
                arrowprops=dict(arrowstyle="->", color="#999999", lw=0.9))
    ax.axvline(12, color="#999999", ls=":", lw=1.0, zorder=0)
    ax.axhline(1.0, color="#009E73", ls="--", lw=1.1, zorder=0)
    # rho is normalised by the correct skill in the prompt, not by the
    # untruncated transplant, so this line is the skill itself
    ax.text(300, 1.02, "the correct skill in the prompt", fontsize=7,
            color="#009E73", ha="right")
    ax.axhline(0.0, color="#8c6d1f", ls="-", lw=1.0, zorder=0)
    ax.text(1.05, -0.10, "the wrong-skill receiver, unpatched", fontsize=7,
            color="#8c6d1f")
    ax.set_xscale("log", base=2)
    # the grid runs to k=512. Qwen3-8B and Qwen3-0.6B are back at their
    # untruncated value by 256 and Mistral-7B only at 384, which is the whole
    # point of extending it: cutting the axis at 256 ended Mistral's curve
    # while it was still climbing and made it look like it never arrives
    ax.set_xticks([1, 2, 4, 8, 16, 32, 64, 128, 256, 512])
    ax.set_xticklabels([1, 2, 4, 8, 16, 32, 64, 128, 256, 512], fontsize=8)
    ax.set_xlim(0.85, 640)
    ax.set_xlabel("rank $k$ the content matrix is truncated to, before "
                  "injection", fontsize=9)
    ax.set_ylabel("recovery $\\rho$, as a fraction of\nthe skill's own effect",
                  fontsize=9)
    ax.set_ylim(-0.20, 1.18)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    handles, labels = ax.get_legend_handles_labels()
    # control first, then the models in MODELS order, as in the original legend
    # (matplotlib lists plain lines before errorbar containers)
    rank_of = lambda lab: (-1 if lab.startswith("bottom") else
                           next(i for i, m in enumerate(MODELS) if lab.startswith(m[0] + ",")))
    order = sorted(range(len(labels)), key=lambda i: rank_of(labels[i]))
    ax.legend([handles[i] for i in order], [labels[i] for i in order],
              fontsize=7.0, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.20), ncol=2, columnspacing=1.2,
              handletextpad=0.5)
    ax.set_title("the same truncation on three models, each injected at an "
                 "early layer", fontsize=8.6)
    fig.tight_layout()
    fig.savefig(out / "fig-rank-medcalc.pdf", bbox_inches="tight")
    fig.savefig(out / "fig-rank-medcalc.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    (out / "fig-rank-values.json").write_text(json.dumps(summary, indent=1))
    for k, v in summary.items():
        print(k, v["tags"], "n", v["n"], "groups", v["groups"], "full %.2f" % v["full"],
              "k* %s" % (None if v["kstar"] is None else round(v["kstar"], 1)))
        print("   top   ", {kk: round(x[0], 2) for kk, x in v["top"].items()})
        print("   bottom", {kk: round(x[0], 2) for kk, x in v["bottom"].items()})


if __name__ == "__main__":
    main()
