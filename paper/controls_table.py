#!/usr/bin/env python3
r"""Table `tab:controls`: the decomposition against three control documents.

    python paper/controls_table.py   -> paper/tab-controls.tex (+ values JSON)

The table shipped until 2026-09-20 came from the 200-item pilot
(whitebox/results/20260910-e14/e14-tierA-mc-1.7B-fp32, rescued cell 48), while
the text of \S4.1 had already moved to the 358-item rerun. Two scales for one
quantity is one number too many, so the table is rebuilt from the same runs the
text uses: d17-neutral, d17-shuffled, d17-corrupted, each 358 items on
Qwen3-1.7B in float32, with `-b` holding the layers a pass skipped.

Columns, all on the rescued cell (the model fails without the document and
solves it with):

    control in context   ok_fil, which is the control document actually in the
                         prompt -- one number, it does not depend on the layer
    h_no + g             ok_add_g, the presence component injected into the
                         no-document prompt
    h_no + d             ok_add_d_a1, the content component, i.e. the residual
                         once that control is what is subtracted

Ranges are over layers 21--27, the band the text quotes; a run that has not
finished every one of those layers is refused rather than reported.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TA = ROOT / "whitebox/results/fetched/tA"
BAND = range(21, 28)
ROWS = [("unrelated text, matched length", ["d17-neutral", "d17-neutral-b"]),
        ("same document, lines scrambled", ["d17-shuffled", "d17-shuffled-b"]),
        ("same document, factors replaced", ["d17-corrupted", "d17-corrupted-b"])]


def layers_of(tags):
    out = {}
    for t in tags:
        for p in sorted((TA / t).glob("layer_*.jsonl")):
            rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
            if rows:
                out[int(p.stem.split("_")[1])] = rows
    return out


def fmt(lo, hi):
    return f"{lo:.3f}" if abs(hi - lo) < 5e-4 else f"{lo:.3f}--{hi:.3f}"


def main():
    vals, body = {}, []
    for name, tags in ROWS:
        L = layers_of(tags)
        missing = [x for x in BAND if x not in L]
        if missing:
            print(f"controls_table: {name} is missing layers {missing}; table left alone")
            return False
        R = [r for r in L[21] if r["cell"] == "R"]
        ids = {r["id"] for r in R}
        for x in BAND:
            assert {r["id"] for r in L[x] if r["cell"] == "R"} == ids, \
                f"{name}: the rescued cell moves between layers"
        frac = lambda rows, key: sum(bool(r[key]) for r in rows) / len(rows)
        # ok_fil is a property of the item, not of the layer: assert that.
        ctx = {frac([r for r in L[x] if r["cell"] == "R"], "ok_fil") for x in BAND}
        assert len(ctx) == 1, f"{name}: ok_fil varies by layer {sorted(ctx)}"
        band = {k: [frac([r for r in L[x] if r["cell"] == "R"], f"ok_{k}") for x in BAND]
                for k in ("add_g", "add_d_a1")}
        vals[name] = {"n": len(L[21]), "n_R": len(R), "layers": sorted(L),
                      "in_context": round(ctx.pop(), 3),
                      "add_g": [round(min(band["add_g"]), 3), round(max(band["add_g"]), 3)],
                      "add_d": [round(min(band["add_d_a1"]), 3), round(max(band["add_d_a1"]), 3)],
                      "add_d_by_layer": {x: round(v, 3) for x, v in zip(BAND, band["add_d_a1"])}}
        v = vals[name]
        bold = r"\textbf{%s}" if name.startswith("unrelated") else "%s"
        body.append(f"{name:<35} & {v['in_context']:.3f} & "
                    f"{bold % fmt(*v['add_g'])} & {bold % fmt(*v['add_d'])} " + r"\\")

    n, n_R = vals[ROWS[0][0]]["n"], vals[ROWS[0][0]]["n_R"]
    assert all(v["n"] == n and v["n_R"] == n_R for v in vals.values()), \
        "the three controls do not share an item set"
    out = [r"\begin{tabular}{lccc}", r"\toprule",
           r"control document & \multicolumn{3}{c}{fraction of the rescued cell correct}\\",
           r"\cmidrule(lr){2-4}",
           r" & control in context & $h_{\text{no}}+\gvec$ & $h_{\text{no}}+\dvec$ \\",
           r"\midrule"] + body + [
           r"\midrule",
           r"gold skill in context & 1.000 & --- & --- \\",
           r"no document           & 0.000 & --- & --- \\",
           r"\bottomrule", r"\end{tabular}"]
    (ROOT / "paper/tab-controls.tex").write_text("\n".join(out) + "\n")
    (ROOT / "paper/controls-values.json").write_text(json.dumps(
        {"status": f"358-item rerun, Qwen3-1.7B fp32, rescued cell {n_R}, layers 21-27",
         "n": n, "n_R": n_R, "rows": vals}, indent=1) + "\n")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "add_d_by_layer"}
                      for k, v in vals.items()}, indent=1))
    print("-> paper/tab-controls.tex")
    return True


if __name__ == "__main__":
    main()
