#!/usr/bin/env python3
"""
Emit the E2 layer sweep as a self-contained TikZ picture for the paper.

Pure TikZ, no pgfplots: the AAAI template already loads tikz, and adding a
package to a submission that compiles is a risk with no upside. Everything is
absolute coordinates computed here, so the .tex fragment has no dependencies
beyond \\usepackage{tikz}.

    python paperfig.py results/<run-id>/e2-tierA --out fig_e2sweep.tex

Then in the paper:

    \\begin{figure}[t] \\centering \\input{fig_e2sweep} \\caption{...} \\end{figure}

Four curves, and the figure only means anything with all four:

    real         the vector captured with the skill in context
    filler       captured with a neutral document instead -- the control that
                 says whether recovery is about content or about presence
    mean         the average over items, carrying no per-item content at all
    mismatched   another item's vector, the "patching anywhere helps" control

The y axis is recovery: 1.0 reproduces the document's whole behavioural effect.
Values above 1.0 are drawn, not clipped -- on Tier A they are the finding.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import pathlib
import sys

STYLE = {
    "real":       ("skillred",  "very thick",              "real (skill)"),
    "filler":     ("skillblue", "very thick, densely dashed", "filler (neutral doc)"),
    "mean":       ("black!55",  "thick, dotted",           "mean vector"),
    "mismatched": ("black!35",  "thin",                    "mismatched item"),
}


E1_STYLE = {
    "net":     ("skillred",  "very thick",              "net (skill - filler)"),
    "effect":  ("skillblue", "thick, densely dashed",   "skill span blocked"),
    "control": ("black!45",  "thin, dotted",            "filler span blocked"),
}


def nice_ticks(lo: float, hi: float, target: int = 6):
    """Round tick values covering [lo, hi], plus how many decimals to print.

    Both figures used to have a y axis with no scale on it: an axis line, and
    for the patch sweep one annotated reference line at 1.0. A reader could see
    that one curve sat above another and could not tell whether the gap was 0.5
    or 5 -- which on this data is the difference between "a little better" and
    "four times the document's entire effect".
    """
    span = hi - lo
    if span <= 0:
        return [lo], 0
    mag = 10 ** math.floor(math.log10(span / max(target, 2)))
    step = mag
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if span / step <= target + 1:
            break
    first = math.ceil(lo / step) * step
    ticks, v = [], first
    while v <= hi + 1e-9:
        ticks.append(round(v, 10))
        v += step
    # Decimals from the step, not from its magnitude: a step of 2.5 is >= 1 and
    # still needs one, and printing it with none labels two different ticks "2"
    # and "-2" -- a wrong axis reads exactly like a right one.
    dec = 0
    while dec < 3 and abs(round(step, dec) - step) > 1e-9:
        dec += 1
    return ticks, dec


def damaged_bands(rows: list[dict]) -> list[tuple[int, int]]:
    """Contiguous layer ranges where the real patch's logprob recovery is < 0.

    A patch that damages the forward pass at layer L raises the accuracy of
    every condition at L, controls included, so an accuracy figure that does
    not mark those layers invites exactly the wrong reading: on Tier A the
    aggregate accuracy peaks at layer 19, inside the damaged region, while the
    layer the text reports is 21. A reader comparing figure to text finds them
    arguing against each other, and the figure wins.

    Drawn as a light band rather than dropped, because the curve through the
    damaged region is real data about what a disturbance does.
    """
    bad = [r["layer"] for r in rows
           if isinstance(r.get("recovery", {}).get("real"), (int, float))
           and r["recovery"]["real"] < 0]
    if not bad:
        return []
    # A single positive layer inside a negative run is a blip around zero, not
    # a healthy region: on Tier A layers 4 and 12 read +0.19 and +0.10 amid
    # neighbours at -0.3 to -2.0. Merging across a one-layer gap turns what
    # would be five ragged strips into the one band the text talks about.
    out, start, prev = [], bad[0], bad[0]
    for n in bad[1:] + [None]:
        if n is None or n > prev + 2:
            out.append((start, prev))
            start = n
        prev = n
    return out


def emit_bands(a, rows, X, Y, lo, hi, note_at=None):
    """The band, plus one label on the widest of them."""
    bands = damaged_bands(rows)
    widest = max(bands, key=lambda b: b[1] - b[0], default=None)
    for x0, x1 in bands:
        if x1 == x0:
            continue
        a(f"  \\fill[black!7] ({X(x0):.3f},{Y(lo):.3f}) rectangle "
          f"({X(x1):.3f},{Y(hi):.3f});")
    if widest and widest[1] > widest[0] and note_at is not None:
        mid = (X(widest[0]) + X(widest[1])) / 2
        a(f"  \\node[anchor=south,black!45,font=\\tiny,inner sep=1pt] at "
          f"({mid:.3f},{Y(note_at):.3f}) {{forward pass damaged}};")
    return bands


def y_axis(a, Y, ticks, dec, W, H, label):
    """Gridlines, ticks and the rotated label. Shared by both figures."""
    for v in ticks:
        y = Y(v)
        a(f"  \\draw[black!8] (0,{y:.3f}) -- ({W:.3f},{y:.3f});")
        a(f"  \\draw[black!45] (-0.08,{y:.3f}) -- (0,{y:.3f});")
        a(f"  \\node[anchor=east,inner sep=3pt,black!55] at (0,{y:.3f}) "
          f"{{{v:.{dec}f}}};")
    # far enough left to clear the tick labels: the old position (x=0 with an
    # inner sep of 9pt) would now sit on top of them
    a(f"  \\node[rotate=90,anchor=south,inner sep=9pt] at (-0.52,{H/2:.3f}) "
      f"{{{label}}};")


def emit_e1(src: pathlib.Path, out: str, W: float, H: float) -> int:
    """
    The knockout sweep: net logprob cost per layer group, with its CI band.

    Never plotted before -- e1 writes per_group.jsonl and nothing read it. The
    band is the point: every group's interval has contained zero on every run so
    far, and a curve without it invites reading the peak's position as a result.
    """
    rows = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
    rows.sort(key=lambda r: r["layers"][0])
    xs = [r["layers"][0] for r in rows]
    curves = {k: [r[k] for r in rows] for k in E1_STYLE if k in rows[0]}
    lo_ci = [r["net_ci95"][0] for r in rows]
    hi_ci = [r["net_ci95"][1] for r in rows]

    vals = [v for c in curves.values() for v in c] + lo_ci + hi_ci + [0.0]
    lo, hi = min(vals), max(vals)
    pad = 0.08 * (hi - lo or 1.0)
    lo, hi = lo - pad, hi + pad

    def X(x):
        span = (xs[-1] - xs[0]) or 1
        return W * (x - xs[0]) / span

    def Y(v):
        return H * (v - lo) / (hi - lo)

    L = []
    a = L.append
    a("% generated by whitebox/paperfig.py -- do not edit by hand")
    a("\\definecolor{skillred}{HTML}{A93B26}")
    a("\\definecolor{skillblue}{HTML}{35697B}")
    a("\\begin{tikzpicture}[x=1cm,y=1cm,font=\\scriptsize]")

    # CI band for net, drawn first so the curves sit on top
    band = [f"({X(x):.3f},{Y(v):.3f})" for x, v in zip(xs, hi_ci)]
    band += [f"({X(x):.3f},{Y(v):.3f})"
             for x, v in zip(reversed(xs), reversed(lo_ci))]
    a("  \\fill[skillred!12] " + " -- ".join(band) + " -- cycle;")

    ticks, dec = nice_ticks(lo, hi)
    y_axis(a, Y, ticks, dec, W, H, "net $\\Delta$ logprob (nats)")
    if lo < 0.0 < hi:
        a(f"  \\draw[black!35,densely dotted] (0,{Y(0.0):.3f}) -- "
          f"({W:.3f},{Y(0.0):.3f});")
    a(f"  \\draw[black!45] (0,{Y(lo + pad):.3f}) -- (0,{Y(hi - pad):.3f});")
    a(f"  \\draw[black!45] (0,{Y(lo + pad):.3f}) -- ({W:.3f},{Y(lo + pad):.3f});")
    for x in (xs[0], xs[len(xs) // 2], xs[-1]):
        a(f"  \\node[anchor=north,inner sep=2pt] at ({X(x):.3f},"
          f"{Y(lo + pad):.3f}) {{{x}}};")
    a(f"  \\node[anchor=north,inner sep=8pt] at ({W/2:.3f},{Y(lo+pad):.3f}) "
      f"{{first layer of group}};")

    for key in ("control", "effect", "net"):
        if key not in curves:
            continue
        colour, style, _ = E1_STYLE[key]
        pts = " ".join(f"({X(x):.3f},{Y(v):.3f})"
                       for x, v in zip(xs, curves[key]) if v == v)
        a(f"  \\draw[{colour},{style}] plot coordinates {{{pts}}};")

    y, x = H + 0.62, 0.0
    for key in ("net", "effect", "control"):
        if key not in curves:
            continue
        colour, style, label = E1_STYLE[key]
        a(f"  \\draw[{colour},{style}] ({x:.3f},{y:.3f}) -- ({x+0.45:.3f},{y:.3f});")
        a(f"  \\node[anchor=west,inner sep=2pt] at ({x+0.5:.3f},{y:.3f}) "
          f"{{{label}}};")
        x += 0.5 + 0.06 * len(label) + 0.55
        if x > W - 1.2:
            x, y = 0.0, y - 0.42
    a("\\end{tikzpicture}")

    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  写好: {out}")
    print(f"  组 {xs[0]}..{xs[-1]}，曲线: {', '.join(curves)}")
    best = max(range(len(xs)), key=lambda i: curves["net"][i])
    print(f"  net 峰值 组起于 {xs[best]}: {curves['net'][best]:+.3f} "
          f"CI95 [{lo_ci[best]:+.3f}, {hi_ci[best]:+.3f}]"
          f"{'  (含 0)' if lo_ci[best] <= 0 <= hi_ci[best] else ''}")
    return 0


def emit_e2_acc(stage_dir: pathlib.Path, out: str, W: float, H: float) -> int:
    """The accuracy reading of the patch sweep, on its own axes.

    Not a second panel of the recovery figure: recovery is a ratio and
    accuracy is a level, and forcing them onto one y axis would make each
    one's reference lines meaningless in the other. It earns its own figure
    because the two channels fail differently -- bf16 costs a gold
    log-probability 0.5 to 2.5 nats when the gold token sits deep in the tail
    and under 0.01 when it is the argmax (HANDOFF-whitebox.md 12.3q), so a
    curve shape that appears in both does not rest on the dtype the run used.

    Returns 1, quietly, for a run that predates the accuracy columns.
    """
    src = stage_dir / "per_layer.jsonl"
    rows = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
    rows.sort(key=lambda r: r["layer"])
    if not rows or "acc" not in rows[0]:
        return 1
    layers = [r["layer"] for r in rows]
    curves = {}
    for key in STYLE:
        vals = [r["acc"].get(key) for r in rows]
        if any(v is not None and v == v for v in vals):
            curves[key] = vals
    if not curves:
        return 1

    # The two levels the curve is read against. Without them the figure says
    # "accuracy went up a bit" and cannot say up towards what.
    refs = []
    sm = stage_dir / "summary.json"
    if sm.exists():
        d = json.loads(sm.read_text(encoding="utf-8"))
        for k, lab in (("acc_yes", "with skill"), ("acc_no", "no document")):
            if isinstance(d.get(k), (int, float)):
                refs.append((lab, float(d[k])))

    finite = [v for c in curves.values() for v in c if v is not None and v == v]
    finite += [v for _, v in refs]
    lo, hi = min(finite), max(finite)
    if hi - lo < 0.08:
        lo, hi = lo - 0.04, hi + 0.04
    pad = 0.10 * (hi - lo)
    lo, hi = max(0.0, lo - pad), min(1.0, hi + pad)

    def X(layer):
        span = (layers[-1] - layers[0]) or 1
        return W * (layer - layers[0]) / span

    def Y(v):
        return H * (v - lo) / (hi - lo)

    L = []
    a = L.append
    a("% generated by whitebox/paperfig.py -- do not edit by hand")
    a("\\definecolor{skillred}{HTML}{A93B26}")
    a("\\definecolor{skillblue}{HTML}{35697B}")
    a("\\begin{tikzpicture}[x=1cm,y=1cm,font=\\scriptsize]")
    emit_bands(a, rows, X, Y, lo, hi, note_at=hi)

    for lab, v in refs:
        if not lo < v < hi:
            continue
        a(f"  \\draw[black!35,densely dashed] (0,{Y(v):.3f}) -- "
          f"({W:.3f},{Y(v):.3f});")
        a(f"  \\node[anchor=west,black!50,inner sep=2pt] at "
          f"({W+0.05:.3f},{Y(v):.3f}) {{{lab}}};")

    a(f"  \\draw[black!45] (0,{Y(lo):.3f}) -- (0,{Y(hi):.3f});")
    a(f"  \\draw[black!45] (0,{Y(lo):.3f}) -- ({W:.3f},{Y(lo):.3f});")
    for lab in (layers[0], layers[len(layers) // 2], layers[-1]):
        a(f"  \\node[anchor=north,inner sep=2pt] at ({X(lab):.3f},"
          f"{Y(lo):.3f}) {{{lab}}};")
    a(f"  \\node[anchor=north,inner sep=8pt] at ({W/2:.3f},{Y(lo):.3f}) "
      f"{{layer}};")
    ticks, dec = nice_ticks(lo, hi)
    y_axis(a, Y, ticks, dec, W, H, "accuracy")

    for key in ("mismatched", "mean", "filler", "real"):
        if key not in curves:
            continue
        colour, style, _ = STYLE[key]
        pts = " ".join(f"({X(l):.3f},{Y(v):.3f})"
                       for l, v in zip(layers, curves[key])
                       if v is not None and v == v)
        a(f"  \\draw[{colour},{style}] plot coordinates {{{pts}}};")
    a("\\end{tikzpicture}")

    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  写好: {out}  （准确率读数）")
    return 0


def emit_e2_fixed(stage_dir: pathlib.Path, out: str, W: float, H: float) -> int:
    """The same sweep restricted to the items the skill turned from wrong to
    right -- the subgroup the behavioural effect is actually made of.

    The aggregate accuracy figure cannot say whether the patch moves those
    items. On Tier A the patch scores 18 of 39 and the document 17 of 39, and
    those two sets can overlap almost completely or hardly at all; the curves
    are identical either way and the mechanisms are not. Restricted to the
    fixed group, 1.0 means the patch reproduced the whole behavioural effect
    and the no-document baseline is 0 by construction, so the axis reads
    directly as "what fraction of the effect is in the vector".

    Two things are structural and belong in the caption, not in the reader's
    head: the group is defined by the with-skill outcome, so its two baselines
    are 0 and 1 by construction and only the patch curves carry information;
    and the group is small (13 items on Tier A, fewer on Tier B unless the
    sweep runs the full pool), so this is a direction, not a rate.

    Returns 1, quietly, when the run has no per-item accuracy or no fixed
    items -- older runs, and num-mode sweeps with nothing to take an argmax
    over.
    """
    src = stage_dir / "per_layer.jsonl"
    rows = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
    rows.sort(key=lambda r: r["layer"])
    if not rows or not rows[0].get("rows"):
        return 1

    def fixed(r):
        return [x for x in r["rows"]
                if x.get("ok_no") is not None and x.get("ok_yes") is not None
                and not int(x["ok_no"]) and int(x["ok_yes"])]

    n_fixed = len(fixed(rows[0]))
    if not n_fixed:
        return 1
    layers = [r["layer"] for r in rows]
    curves = {}
    for key in STYLE:
        vals = []
        for r in rows:
            got = [x["ok_" + key] for x in fixed(r) if x.get("ok_" + key) is not None]
            vals.append(sum(got) / len(got) if got else None)
        if any(v is not None for v in vals):
            curves[key] = vals
    if not curves:
        return 1

    lo, hi = 0.0, 1.0

    def X(layer):
        span = (layers[-1] - layers[0]) or 1
        return W * (layer - layers[0]) / span

    def Y(v):
        return H * (v - lo) / (hi - lo)

    L = []
    a = L.append
    a("% generated by whitebox/paperfig.py -- do not edit by hand")
    a("\\definecolor{skillred}{HTML}{A93B26}")
    a("\\definecolor{skillblue}{HTML}{35697B}")
    a("\\begin{tikzpicture}[x=1cm,y=1cm,font=\\scriptsize]")
    emit_bands(a, rows, X, Y, lo, hi, note_at=hi)
    a(f"  \\draw[black!35,densely dashed] (0,{Y(1.0):.3f}) -- "
      f"({W:.3f},{Y(1.0):.3f});")
    a(f"  \\node[anchor=west,black!50,inner sep=2pt] at "
      f"({W+0.05:.3f},{Y(1.0):.3f}) {{whole effect}};")
    a(f"  \\draw[black!45] (0,{Y(lo):.3f}) -- (0,{Y(hi):.3f});")
    a(f"  \\draw[black!45] (0,{Y(lo):.3f}) -- ({W:.3f},{Y(lo):.3f});")
    for lab in (layers[0], layers[len(layers) // 2], layers[-1]):
        a(f"  \\node[anchor=north,inner sep=2pt] at ({X(lab):.3f},"
          f"{Y(lo):.3f}) {{{lab}}};")
    a(f"  \\node[anchor=north,inner sep=8pt] at ({W/2:.3f},{Y(lo):.3f}) "
      f"{{layer}};")
    ticks, dec = nice_ticks(lo, hi)
    y_axis(a, Y, ticks, dec, W, H, f"fixed items ($n={n_fixed}$)")
    for key in ("mismatched", "mean", "filler", "real"):
        if key not in curves:
            continue
        colour, style, _ = STYLE[key]
        pts = " ".join(f"({X(l):.3f},{Y(v):.3f})"
                       for l, v in zip(layers, curves[key]) if v is not None)
        a(f"  \\draw[{colour},{style}] plot coordinates {{{pts}}};")
    a("\\end{tikzpicture}")

    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  写好: {out}  （skill 修好的 {n_fixed} 题）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage_dir", type=pathlib.Path,
                    help="a run's e2-* directory (per_layer.jsonl) or e1-* "
                         "(per_group.jsonl); the file present picks the figure")
    ap.add_argument("--out", default="fig_e2sweep.tex")
    ap.add_argument("--all", action="store_true",
                    help="treat stage_dir as a RUN directory and emit one "
                         "figure per sweep under it, named after the stage. "
                         "This is how the pipeline calls it: which sweeps a run "
                         "holds depends on the tier, and listing them in the "
                         "shell would go stale the first time a stage is added.")
    ap.add_argument("--outdir", default=None,
                    help="with --all; default <run>/paper")
    ap.add_argument("--width", type=float, default=7.4, help="cm")
    ap.add_argument("--height", type=float, default=4.4, help="cm")
    args = ap.parse_args()

    if args.all:
        outdir = pathlib.Path(args.outdir or (args.stage_dir / "paper"))
        outdir.mkdir(parents=True, exist_ok=True)
        made = 0
        for d in sorted(p for p in args.stage_dir.iterdir() if p.is_dir()):
            tgt = str(outdir / f"fig-{d.name}.tex")
            if (d / "per_layer.jsonl").exists():
                print(f"\n[{d.name}]")
                rc = main_one(d, tgt, args.width, args.height)
                # Same sweep, second reading. Silently absent for older runs.
                if emit_e2_acc(d, str(outdir / f"fig-{d.name}-acc.tex"),
                               args.width, args.height) == 0:
                    made += 1
                # Same sweep again, restricted to the items the skill fixed.
                if emit_e2_fixed(d, str(outdir / f"fig-{d.name}-fixed.tex"),
                                 args.width, args.height) == 0:
                    made += 1
            elif (d / "per_group.jsonl").exists():
                print(f"\n[{d.name}]")
                rc = emit_e1(d / "per_group.jsonl", tgt, args.width, args.height)
            else:
                continue
            made += 1 if rc == 0 else 0
        print(f"\n  {made} 张图写进 {outdir}")
        return 0 if made else 1

    return main_one(args.stage_dir, args.out, args.width, args.height)


def main_one(stage_dir: pathlib.Path, out: str, Wcm: float, Hcm: float) -> int:
    class _A:
        pass
    args = _A()
    args.stage_dir, args.out = stage_dir, out
    args.width, args.height = Wcm, Hcm

    src = args.stage_dir / "per_layer.jsonl"
    if not src.exists():
        e1_src = args.stage_dir / "per_group.jsonl"
        if e1_src.exists():
            return emit_e1(e1_src, args.out, args.width, args.height)
        print(f"[FAIL] {args.stage_dir} 里既没有 per_layer.jsonl 也没有 "
              f"per_group.jsonl")
        return 1

    rows = [json.loads(l) for l in io.open(src, encoding="utf-8") if l.strip()]
    rows.sort(key=lambda r: r["layer"])
    layers = [r["layer"] for r in rows]
    curves = {}
    for key in STYLE:
        vals = [r["recovery"].get(key) for r in rows]
        if any(v is not None and v == v for v in vals):
            curves[key] = vals
    if "filler" not in curves:
        print("  (注意) 这一跑没有 filler 条件 —— 图里会缺那条对照曲线,"
              "而它正是判断内容 vs 在场的那一条。加 --filler 重跑 e2 更好。")

    finite = [v for c in curves.values() for v in c if v is not None and v == v]
    lo, hi = min(finite + [0.0]), max(finite + [1.0])
    pad = 0.08 * (hi - lo or 1.0)
    lo, hi = lo - pad, hi + pad

    W, H = args.width, args.height

    def X(layer):
        span = (layers[-1] - layers[0]) or 1
        return W * (layer - layers[0]) / span

    def Y(v):
        return H * (v - lo) / (hi - lo)

    L = []
    a = L.append
    a("% generated by whitebox/paperfig.py -- do not edit by hand")
    a("\\definecolor{skillred}{HTML}{A93B26}")
    a("\\definecolor{skillblue}{HTML}{35697B}")
    a("\\begin{tikzpicture}[x=1cm,y=1cm,font=\\scriptsize]")

    # y=1 is the line the whole figure is read against
    if lo < 1.0 < hi:
        a(f"  \\draw[black!30,densely dotted] (0,{Y(1.0):.3f}) -- "
          f"({W:.3f},{Y(1.0):.3f});")
        a(f"  \\node[anchor=west,black!45,inner sep=1pt] at "
          f"({W+0.05:.3f},{Y(1.0):.3f}) {{$1.0$}};")
    if lo < 0.0 < hi:
        a(f"  \\draw[black!20] (0,{Y(0.0):.3f}) -- ({W:.3f},{Y(0.0):.3f});")

    a(f"  \\draw[black!45] (0,{Y(lo + pad):.3f}) -- (0,{Y(hi - pad):.3f});")
    a(f"  \\draw[black!45] (0,{Y(lo + pad):.3f}) -- ({W:.3f},{Y(lo + pad):.3f});")

    for lab in (layers[0], layers[len(layers) // 2], layers[-1]):
        a(f"  \\node[anchor=north,inner sep=2pt] at ({X(lab):.3f},"
          f"{Y(lo + pad):.3f}) {{{lab}}};")
    a(f"  \\node[anchor=north,inner sep=8pt] at ({W/2:.3f},{Y(lo+pad):.3f}) "
      f"{{layer}};")
    ticks, dec = nice_ticks(lo, hi)
    y_axis(a, Y, ticks, dec, W, H, "recovery")

    # thin curves first so the two that carry the claim sit on top
    for key in ("mismatched", "mean", "filler", "real"):
        if key not in curves:
            continue
        colour, style, _ = STYLE[key]
        pts = " ".join(f"({X(l):.3f},{Y(v):.3f})"
                       for l, v in zip(layers, curves[key])
                       if v is not None and v == v)
        a(f"  \\draw[{colour},{style}] plot coordinates {{{pts}}};")

    y = H + 0.62
    x = 0.0
    for key in ("real", "filler", "mean", "mismatched"):
        if key not in curves:
            continue
        colour, style, label = STYLE[key]
        a(f"  \\draw[{colour},{style}] ({x:.3f},{y:.3f}) -- ({x+0.45:.3f},{y:.3f});")
        a(f"  \\node[anchor=west,inner sep=2pt] at ({x+0.5:.3f},{y:.3f}) "
          f"{{{label}}};")
        x += 0.5 + 0.06 * len(label) + 0.55
        if x > W - 1.2:
            x, y = 0.0, y - 0.42
    a("\\end{tikzpicture}")

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  写好: {args.out}")
    print(f"  层 {layers[0]}..{layers[-1]}，曲线: {', '.join(curves)}")
    # Read the layer off summary.json rather than taking the max: e2_patch
    # excludes the final layers, where patching the last prompt position simply
    # overwrites the state that emits the answer token and recovery is high by
    # construction. Quoting a margin from there would quote an artefact.
    sm = args.stage_dir / "summary.json"
    best_layer = None
    if sm.exists():
        best_layer = json.loads(sm.read_text(encoding="utf-8")).get("best_layer")
    if best_layer is None:
        tail = [l for l in layers[:-2]] or layers
        best_layer = max(tail, key=lambda l: dict(zip(layers, curves["real"]))[l])
        print("  (注意) 没有 summary.json,峰值层是这里重算的（已排除末两层）")
    at = lambda k: dict(zip(layers, curves[k])).get(best_layer)
    print(f"  real 在最佳层 {best_layer}: {at('real'):+.3f}")
    if "filler" in curves and at("filler") is not None:
        print(f"  同层 filler {at('filler'):+.3f}   "
              f"内容余量 {at('real') - at('filler'):+.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
