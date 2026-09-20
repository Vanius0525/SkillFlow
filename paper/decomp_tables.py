#!/usr/bin/env python3
r"""The synthetic-decomposition appendix displays, at the scale the main text uses.

    python paper/decomp_tables.py
        -> paper/tab-causal.tex, tab-parperp.tex, tab-geometry-tierA.tex
           (+ paper/decomp-values.json for the prose and the model ladder)

Until 2026-09-20 these three tables were the 200-item pilot
(whitebox/results/20260910-e14, rescued cell 48) while \S4.1 in the main text
had moved to the 358-item rerun `d17-neutral` (rescued cell 82). The same
quantity appeared as 0.812 in the appendix and 0.805 in the main text, which is
one number too many for one measurement. Everything here is rebuilt from
`d17-neutral` (+ `d17-neutral-b`, the layers the mirror bug lost), Qwen3-1.7B in
float32, 28 layers, the same run the main text quotes.

The columns and the layers are the ones the surrounding prose names, so the
text keeps pointing at the cells it discusses; only the scale changes.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TA = ROOT / "whitebox/results/fetched/tA"
TAGS = ["d17-neutral", "d17-neutral-b"]


def layers_of(tags):
    out = {}
    for t in tags:
        for p in sorted((TA / t).glob("layer_*.jsonl")):
            rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
            if rows:
                out[int(p.stem.split("_")[1])] = rows
    return out


def main():
    L = layers_of(TAGS)
    need = list(range(28))
    missing = [x for x in need if x not in L]
    if missing:
        print(f"decomp_tables: d17-neutral is missing layers {missing}")
        return False
    n = len(L[26])
    assert all(len(v) == n for v in L.values()), "the item set moves between layers"
    R = {x: [r for r in L[x] if r["cell"] == "R"] for x in L}
    n_R = len(R[26])
    assert all(len(v) == n_R for v in R.values()), "the rescued cell moves between layers"

    def f(x, arm):
        return sum(bool(r["ok_" + arm]) for r in R[x]) / n_R

    def cell(arm, cols):
        """One table cell: a value at a layer, or a min--max over a layer range."""
        if isinstance(cols, int):
            return f"{f(cols, arm):.3f}"
        lo, hi = min(f(x, arm) for x in cols), max(f(x, arm) for x in cols)
        return f"{lo:.2f}--{hi:.2f}"

    vals = {"n": n, "n_R": n_R, "source": TAGS, "layers": sorted(L)}

    # ---- tab:causal -------------------------------------------------------
    COLS = [("L17--20", range(17, 21)), ("L21", 21), ("L24", 24), ("L26", 26), ("L27", 27)]
    CAUSAL = [(r"$h_{\text{skill}}$ (replace outright; upper ref.)", "replace_real"),
              (r"$h_{\text{skill}}$ into the wrong-document prompt", "fil_replace_real"),
              None,
              (r"$h_{\text{no}} + 0.5\,\dvec_i$", "add_d_a0.5"),
              (r"$h_{\text{no}} + \dvec_i$ \quad (content)", "add_d_a1"),
              (r"$h_{\text{no}} + 2\,\dvec_i$", "add_d_a2"),
              None,
              (r"$h_{\text{no}} + \gvec_i$ \quad (presence)", "add_g"),
              (r"$h_{\text{no}} + \bar{\dvec}$ \ (one shared direction)", "add_dbar"),
              (r"$h_{\text{no}} + \dvec_j$ \ (same family)", "add_d_samefam"),
              (r"$h_{\text{no}} + \dvec_j$ \ (other family)", "add_d_crossfam")]
    body = []
    for item in CAUSAL:
        if item is None:
            body.append(r"\midrule")
            continue
        label, arm = item
        body.append(label + " & " + " & ".join(cell(arm, c) for _, c in COLS) + r" \\")
        vals.setdefault("causal", {})[arm] = {name: cell(arm, c) for name, c in COLS}
    write("tab-causal.tex",
          [r"\begin{tabular}{lccccc}", r"\toprule",
           r"injected at the last prompt position & " +
           " & ".join(name for name, _ in COLS) + r"\\", r"\midrule"] + body +
          [r"\bottomrule", r"\end{tabular}"])

    # ---- tab:parperp ------------------------------------------------------
    PP = [(r"$h_{\text{no}} + \dvec_i$ (whole)", "add_d_a1"),
          (r"$h_{\text{no}} + (\dvec_i\!\cdot\!u)u$ (shared dir.)", "add_d_par"),
          (r"$h_{\text{no}} + \dvec_i^{\perp}$ (item-specific)", "add_d_perp"),
          (r"$h_{\text{no}} + \bar{\dvec}$ (shared dir., fixed norm)", "add_dbar")]
    PPL = [16, 18, 20, 21, 24, 26]
    body = [f"{label} & " + " & ".join(f"{f(x, arm):.3f}" for x in PPL) + r" \\"
            for label, arm in PP]
    for label, arm in PP:
        vals.setdefault("parperp", {})[arm] = {x: round(f(x, arm), 3) for x in PPL}
    write("tab-parperp.tex",
          [r"\begin{tabular}{lcccccc}", r"\toprule",
           "injected & " + " & ".join(f"L{x}" for x in PPL) + r" \\", r"\midrule"] +
          body + [r"\bottomrule", r"\end{tabular}"])
    # the claim the caption makes: the two halves swap at layer 21
    swap = [x for x in sorted(L) if f(x, "add_d_perp") > f(x, "add_d_par")]
    vals["parperp_crossover"] = swap[0] if swap else None

    # ---- tab:geometry-tierA ----------------------------------------------
    summary = json.loads((TA / "d17-neutral/summary.json").read_text())["per_layer"]
    GL = [0, 10, 14, 21, 27]
    G = ["norm_d", "norm_g", "ratio_d_over_t", "cos_d_g", "cos_dd_within_family",
         "cos_dd_cross_family", "pr_d_centred", "frac_d_on_mean"]
    body = []
    for x in GL:
        g = summary[str(x)]["geometry"]
        cells = [f"{g['norm_d']:8.2f}", f"{g['norm_g']:8.2f}", f"{g['ratio_d_over_t']:.2f}",
                 (f"${g['cos_d_g']:.2f}$" if g["cos_d_g"] >= 0 else
                  f"$-{abs(g['cos_d_g']):.2f}$"),
                 f"{g['cos_dd_within_family']:.3f}", f"{g['cos_dd_cross_family']:.3f}",
                 f"{g['pr_d_centred']:.1f}", f"{g['frac_d_on_mean']:.3f}"]
        body.append(f"{x:2d} & " + " & ".join(cells) + r" \\")
        vals.setdefault("geometry", {})[x] = {k: round(g[k], 3) for k in G}
    write("tab-geometry-tierA.tex",
          [r"\begin{tabular}{rrrrrrrrr}", r"\toprule",
           r"layer & $\|\dvec\|$ & $\|\gvec\|$ & $\|\dvec\|/\|\tvec\|$ & $\cos(\dvec,\gvec)$",
           r"& \multicolumn{2}{c}{$\cos(\dvec_i,\dvec_j)$} & $\mathrm{PR}(\dvec)$ & on mean \\",
           r"\cmidrule(lr){6-7}", r"& & & & & same fam. & cross fam. & & \\", r"\midrule"] +
          body + [r"\bottomrule", r"\end{tabular}"])

    # ---- the numbers the model-ladder table and the prose quote -----------
    whole = {k: sum(bool(r["ok_" + k]) for r in L[26]) / n for k in ("no", "fil", "yes")}
    vals["whole_set_L26"] = {k: round(v, 3) for k, v in whole.items()}
    vals["ladder_1.7B"] = {"replace": round(f(26, "replace_real"), 3),
                           "add_d": round(f(26, "add_d_a1"), 3),
                           "add_g_best": round(max(f(x, "add_g") for x in range(21, 28)), 3)}
    vals["layers_norm_g_over_t"] = [x for x in sorted(L)
                                    if summary[str(x)]["geometry"]["norm_g"] >
                                    summary[str(x)]["geometry"]["norm_t"]]
    (ROOT / "paper/decomp-values.json").write_text(json.dumps(vals, indent=1) + "\n")
    print(json.dumps({k: v for k, v in vals.items() if k != "causal"}, indent=1))
    print(f"-> tab-causal.tex, tab-parperp.tex, tab-geometry-tierA.tex (n={n}, n_R={n_R})")
    return True


def write(name, lines):
    (ROOT / "paper" / name).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
