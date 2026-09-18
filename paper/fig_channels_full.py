#!/usr/bin/env python3
"""Figure 1 (fig-channels-medcalc) on the full restricted set, one receiver.

    cd paper && MPLCONFIGDIR=/tmp/skillvector-mpl python3 fig_channels_full.py

The earlier version put two different experiments on one axis: a top panel of
final-position vector arms on twenty pre-fix items with a NO-skill receiver,
and a bottom panel of span arms on a sixteen-item development set with the
wrong-skill receiver, and its caption had to warn that the panels were not
comparable. Both panels now read the same 135 rescued items from the same 14
calculators, into the same wrong-skill receiver, after the instrument fix:

  top     donor states at the last 1, 16, or up to 256 positions after the
          skill, all at layer 8 (completed pb-tq comparison);
  bottom  the span battery at layer 8 (wb_spanvec full-battery-a/b).

Incomplete multi-layer fp-* runs are excluded. Error bars use the same
calculator bootstrap as the main table.
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import replication as rep

HERE = pathlib.Path(__file__).resolve().parent
plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42})


def acc_ci(groups, key):
    # Use the same estimator and draws as the main battery table.
    return rep.accuracy(groups, key, B=2000)[:4]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE))
    out = pathlib.Path(ap.parse_args().out)
    # The multi-layer fp-* shards are incomplete. Use the completed, paired
    # layer-8 position comparison, not maxima on changing partial subsets.
    tags = ["full-battery-a", "full-battery-b", "pb-tq"]
    groups = rep.restricted(rep.load(tags))
    n = sum(len(v) for v in groups.values())
    top = []
    for arm, label in (("tq1", "last prompt position"),
                       ("tq16", "last 16 prompt positions"),
                       ("tq256", r"last $\leq$256 prompt positions")):
        best = None
        for L in [8]:
            key = f"ok_{arm}_L{L}"
            if not any(key in r for rs in groups.values() for r in rs):
                continue
            v = acc_ci(groups, key)
            assert v[3] == n, (arm, v[3], n)
            if best is None or v[0] > best[1][0]:
                best = (L, v)
        if best:
            top.append((label, best[1], arm, best[0]))
    bottom = []
    for arm, label in (("real", r"$h_{\rm recv}+d$  $(\alpha=1)$"),
                       ("a0.5", r"$h_{\rm recv}+0.5\,d$"),
                       ("dcross", r"$+\,d_j$, another skill"),
                       ("dshuf", r"$+\,d$, positions permuted"),
                       ("drand", r"noise, $\|\cdot\|$ matched")):
        bottom.append((label, acc_ci(groups, f"ok_{arm}_L8"), arm, 8))
    gold = acc_ci(groups, "ok_gold_in_context")
    recv = acc_ci(groups, "ok_receiver")

    # Layout and styling follow figs.fig_channels: horizontal bars, the first
    # arm of each panel in the dark shade, each panel's own correct-skill and
    # receiver lines labelled under its lowest bar.
    fig, (axT, axB) = plt.subplots(2, 1, figsize=(4.9, 3.0), sharex=True,
                                   gridspec_kw={"height_ratios": [len(top) + 0.7,
                                                                  len(bottom) + 0.7]})
    for ax, items, title in (
            (axT, top, f"written at the last prompt positions, after the skill ($n={n}$)"),
            (axB, bottom, f"written over the skill's own span ($n={n}$)")):
        y = list(range(len(items)))[::-1]
        vals = [v[1][0] for v in items]
        lo = [max(v[1][0] - v[1][1], 0) for v in items]
        hi = [max(v[1][2] - v[1][0], 0) for v in items]
        cols = ["#0072B2"] + ["#a6cee3"] * (len(items) - 1)
        ax.barh(y, vals, color=cols, height=0.6, edgecolor="#31688e", lw=0.4)
        ax.errorbar(vals, y, xerr=[lo, hi], fmt="none", ecolor="#333333", capsize=2, lw=0.9)
        for yi, v, h in zip(y, vals, hi):
            ax.text(min(v + h + 0.02, 1.16), yi, f"{v:.2f}", va="center", fontsize=7,
                    color="#333333")
        ax.set_yticks(y)
        ax.set_yticklabels([v[0] for v in items], fontsize=7.6)
        ax.axvline(gold[0], color="#009E73", lw=1.1, ls="--", zorder=0)
        ax.axvline(recv[0], color="#D55E00", lw=1.1, ls=":", zorder=0)
        ax.set_title(title, fontsize=8.8, loc="left", pad=6)
        ax.set_xlim(0, 1.12)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5)
        # baseline labels go UNDER the lowest bar, not over the title
        ax.text(recv[0] + 0.012, -0.72, f"wrong-skill receiver ({recv[0]:.2f})",
                fontsize=6.6, color="#D55E00", va="center")
        ax.text(gold[0] - 0.012, -0.72, f"correct skill ({gold[0]:.2f})",
                fontsize=6.6, color="#009E73", va="center", ha="right")
        ax.set_ylim(-1.1, len(items) - 0.4)
    axB.set_xlabel("accuracy on the rescued items the skill is needed for", fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig-channels-medcalc.pdf", bbox_inches="tight")
    fig.savefig(out / "fig-channels-medcalc.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    vals = {"sources": tags, "n": n, "groups": len(groups), "gold": gold[:3], "receiver": recv[:3],
            "top": {a: {"layer": L, "acc": v[:3], "n": v[3]} for _, v, a, L in top},
            "bottom": {a: {"acc": v[:3], "n": v[3]} for _, v, a, _ in bottom}}
    (out / "fig-channels-values.json").write_text(json.dumps(vals, indent=1))
    print(json.dumps(vals))


if __name__ == "__main__":
    main()
