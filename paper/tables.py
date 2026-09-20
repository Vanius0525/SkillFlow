#!/usr/bin/env python3
"""LaTeX tables for the real-skill results, generated from the run outputs.

    python tables.py --medcalc ../howskill/results/p8-wb/fetched/by-host --out .

Same rule as figs.py: a table in the paper and a figure in the paper must not be
able to disagree, and the only way to guarantee that is for both to be produced
from the same files by code. Nothing here takes a number as an argument.

Each table is written to its own file and \\input{} from the paper, so a rerun
updates the paper without anyone retyping a digit.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import random


def load(paths, restrict=None):
    """{arm: [bool]} merged across shards by instance, plus the note count.

    The battery is sharded by ARM across boxes; every shard runs the same notes
    and differs only in which donors it decodes. So this is a union over arm
    keys grouped by instance_id. Concatenating instead would count a note once
    per shard in the baselines and silently hide a shard that ran a different
    instance set -- which is why the disagreement check below is loud.
    """
    rows, seen = {}, collections.defaultdict(set)
    fillers = set()
    for path in paths:
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            iid = r.get("instance_id")
            if not iid:
                continue
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
            tgt["calculator_id"] = r.get("calculator_id", tgt.get("calculator_id"))
            for k, v in r.items():
                if k.startswith("ok_"):
                    if k in tgt and tgt[k] != v:
                        print(f"[warn] {iid} {k} disagrees across shards: "
                              f"{tgt[k]} vs {v}")
                    tgt[k] = bool(v)
                    seen[k[3:]].add(path)
    if len(fillers) > 1:
        raise SystemExit(
            f"refusing to merge runs with different receivers: {sorted(fillers)}"
            f"\n  files: {list(paths)}")
    if restrict == "needs_document":
        before = len(rows)
        rows = needs_document(rows)
        print(f"  restricted to the calculators the receiver never solves: "
              f"{len(rows)} of {before} instances")
    by = collections.defaultdict(list)
    for r in rows.values():
        for k, v in r.items():
            by[k[3:]].append(v)
    return by, len(rows)


def ci(v, clusters=None, n_boot=10000, seed=0):
    """Mean with a 95% interval, clustered by calculator when told the clusters.

    The four instances of a calculator share a byte-identical document, and
    with the document ahead of the question their content vector is literally
    the same tensor, so their outcomes are not independent -- on most arms they
    are all 0 or all 1. A binomial interval over instances therefore reports
    n=20 worth of precision from what is closer to n=5. Resampling calculators
    with replacement is the right estimator, and it is the one the behavioural
    table already uses.

    On the saturated arms it changes almost nothing (0.95 stays [0.85, 1.00]),
    which is itself worth knowing; it widens the intermediate ones, e.g.
    alpha=0.6 from [0.62, 0.98] to [0.50, 1.00].
    """
    m = sum(v) / len(v)
    if not clusters:
        se = math.sqrt(max(m * (1 - m), 0.0) / len(v))
        return m, max(0.0, m - 1.96 * se), min(1.0, m + 1.96 * se)
    groups = collections.defaultdict(list)
    for val, c in zip(v, clusters):
        groups[c].append(val)
    keys = sorted(groups)
    rng = random.Random(seed)
    ms = []
    for _ in range(n_boot):
        pool = []
        for _ in keys:
            pool += groups[keys[rng.randrange(len(keys))]]
        ms.append(sum(pool) / len(pool))
    ms.sort()
    return m, ms[int(0.025 * n_boot)], ms[int(0.975 * n_boot)]


def needs_document(rows):
    """Keep the instances the RECEIVER does not already solve.

    The rescued cell R is defined by gold against NO document, but every span
    arm is measured against a receiver that holds a WRONG document, and on some
    calculators that wrong document is all the model needed -- disrupt it with
    anything and it falls back on knowledge it already has. Measured: on the
    four calculators whose receiver is non-zero, norm-matched Gaussian noise
    written into the span scores 0.500 and a donor from another skill 0.875,
    while on the six whose receiver is zero the same arms score 0.000 and
    0.143. Averaging the two groups reports partial transfer where there is
    none. So causal arms are read on the instances where the document is
    load-bearing against the receiver actually used.
    """
    # The criterion is per CALCULATOR, not per instance. "This model can do this
    # calculator without the gold document" is a property of the calculator;
    # an individual instance failing under the receiver can be chance, and
    # keeping such instances readmits the very calculators the split is for --
    # per-instance it keeps 34 of 40 and the foreign-donor arm reads 0.39,
    # per-calculator it keeps 21 and the same arm reads 0.14.
    #
    # It conditions on the RECEIVER, which is a control, and on no intervention
    # arm, so it cannot manufacture the contrast it is used to report.
    acc = collections.defaultdict(list)
    for r in rows.values():
        if "ok_receiver" in r:
            acc[r["calculator_id"]].append(bool(r["ok_receiver"]))
    keep = {c for c, v in acc.items() if sum(v) == 0}
    return {k: r for k, r in rows.items() if r["calculator_id"] in keep}


def resolve(by, arm, layer):
    for k in (arm, f"{arm}_L{layer}"):
        if k in by:
            return k
    return None


def tab_battery(span_paths, diffvec_paths, out: pathlib.Path, layer=8,
                restrict=None, name="tab-battery"):
    """The paper's first table: the same content vector, two places to put it."""
    by, n = load(span_paths, restrict=restrict)
    dv = collections.defaultdict(dict)
    for path in diffvec_paths:
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            L = r.get("layer")
            for k, v in r.items():
                if k.startswith("ok_") and isinstance(v, bool):
                    dv[k[3:]].setdefault(L, []).append(v)
    # one number per arm, at the layer that arm does best on: the claim is that
    # no layer works, so the table has to show the strongest one
    best = {a: max(d.values(), key=lambda v: sum(v) / len(v))
            for a, d in dv.items()}

    left = [(r"replace the state with $h_{\text{skill}}$", "replace_gold"),
            (r"$h+\dvec$", "add_d"),
            (r"$h+\gvec$", "add_g"),
            (r"$h+\dvec_j$, another instance of this skill", "add_d_samecalc"),
            (r"$h+\dvec_j$, another skill", "add_d_crosscalc")]
    right = [(r"$h_{\text{recv}}+\dvec$ \ (= $h_{\text{skill}}$, $\alpha=1$)",
              "real"),
             (r"$h_{\text{recv}}+2\dvec$", "a2"),
             (r"$h_{\text{recv}}+\tfrac12\dvec$", "a0.5"),
             (r"$h_{\text{recv}}+\tfrac14\dvec$", "a0.25"),
             (r"$h_{\text{recv}}+\dvec$, shared prefix only", "realm"),
             (r"$h_{\text{recv}}+\bar{\dvec}_{j}$, another skill, same prefix",
              "dcross"),
             (r"$h_{\text{recv}}+\dvec$, span positions permuted", "dshuf"),
             (r"$h_{\text{recv}}+$ noise, $\|\cdot\|$ matched per position",
              "drand"),
             (r"$h_{\text{recv}}$ itself (must be a no-op)", "self")]

    def row(label, vals):
        if not vals:
            return None
        m, lo, hi = ci(vals)
        return f"{label} & ${m:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ \\\\"

    lines = [r"\begin{tabular}{@{}lcc@{}}", r"\toprule",
             r"& accuracy & CI$_{95}$ \\", r"\midrule",
             r"\multicolumn{3}{@{}l}{\emph{the gold document in the prompt, "
             r"and no document at all}}\\"]
    for lab, key, src in ((r"\quad gold document in context", "gold", best),
                          (r"\quad no document", "none", best)):
        r_ = row(lab, src.get(key, []))
        if r_:
            lines.append(r_)
    lines += [r"\midrule",
              r"\multicolumn{3}{@{}l}{\emph{written into the last prompt "
              r"position} (best layer of 10, 14, 20, 30 for each arm)}\\"]
    for lab, key in left:
        r_ = row(r"\quad " + lab, best.get(key, []))
        if r_:
            lines.append(r_)
    lines += [r"\midrule",
              r"\multicolumn{3}{@{}l}{\emph{written over the document's own "
              r"span}, layer " + str(layer) + r"}\\"]
    r_ = row(r"\quad the filler document, unpatched (the floor here)",
             by.get("receiver", []))
    if r_:
        lines.append(r_)
    for lab, key in right:
        k = resolve(by, key, layer)
        r_ = row(r"\quad " + lab, by.get(k, []) if k else [])
        if r_:
            lines.append(r_)
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{name}.tex  ({n} notes)")


def tab_realspan(span_paths, out: pathlib.Path, name="tab-realspan",
                 restrict=None):
    """The depth curve of the document-span transplant, as run.

    Written from the merged shards rather than typed, because this table went
    into an earlier draft at n=12 and read 0.42/0.58/0.33/0.08 where the
    completed n=40 run reads 0.400/0.475/0.175/0.150 -- a shape that was not
    yet a shape.
    """
    by, n = load(span_paths, restrict=restrict)
    layers = sorted({int(k.split("_L")[1]) for k in by
                     if k.startswith("real_L") and k[6:].isdigit()})
    floor = sum(by["receiver"]) / len(by["receiver"])
    top = sum(by["gold_in_context"]) / len(by["gold_in_context"])
    lines = [r"\begin{tabular}{@{}r" + "c" * 3 + r"@{}}", r"\toprule",
             r"layer & accuracy & CI$_{95}$ & fraction of the document's "
             r"own effect \\", r"\midrule"]
    for L in layers:
        m, lo, hi = ci(by[f"real_L{L}"])
        f = (m - floor) / max(top - floor, 1e-9)
        star = ""
        k = f"self_L{L}"
        if k in by:
            sm = sum(by[k]) / len(by[k])
            star = rf" \quad\tiny(no-op arm {sm:.3f})"
        lines.append(f"{L} & ${m:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & "
                     f"${f:+.2f}${star} \\\\")
    if "real_alllayers" in by:
        m, lo, hi = ci(by["real_alllayers"])
        f = (m - floor) / max(top - floor, 1e-9)
        lines += [r"\midrule",
                  f"every layer & ${m:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & "
                  f"${f:+.2f}$ \\\\"]
    lines += [r"\midrule",
              f"\\emph{{the filler document, unpatched}} & ${floor:.3f}$ & & "
              f"$0.00$ \\\\",
              f"\\emph{{the gold document in context}} & ${top:.3f}$ & & "
              f"$1.00$ \\\\",
              r"\bottomrule", r"\end{tabular}"]
    (out / f"{name}.tex").write_text("\n".join(lines) + "\n",
                                     encoding="utf-8")
    print(f"{name}.tex  ({n} notes, {len(layers)} layers)")


def tab_skilltask(paths, out: pathlib.Path, layer=8, restrict=None,
                  name="tab-skilltask"):
    """What the carrying vector contains, with the document after the question."""
    by, n = load(paths, restrict=restrict)
    if "receiver" not in by:
        print("tab-skilltask: no baselines in these shards, skipped")
        return
    f = sum(by["receiver"]) / len(by["receiver"])
    t = sum(by["gold_in_context"]) / len(by["gold_in_context"])
    items = [(r"$\dvec_i$, this instance's own", "real"),
             (r"$\bar{\dvec}_{\neg i}$, the mean over the skill's other "
              r"instances", "dbar"),
             (r"$\dvec_j$, one other instance", "dother"),
             (r"$\dvec_i^{\parallel}$, the half along that mean", "dpar"),
             (r"$\dvec_i^{\perp}$, the rest", "dperp"),
             (r"$\bar{\dvec}$, another skill", "dcross"),
             (r"$\bar{\dvec}$, averaged over every skill", "dall"),
             (r"the same $\dvec_i$, span positions permuted", "dshuf"),
             (r"noise, norm matched per position", "drand")]
    lines = [r"\begin{tabular}{@{}lccc@{}}", r"\toprule",
             r"donor written over the document's span & accuracy & CI$_{95}$ "
             r"& fraction \\", r"\midrule",
             rf"\emph{{the filler document, unpatched}} & ${f:.3f}$ & & "
             rf"$0.00$ \\",
             rf"\emph{{the gold document in context}} & ${t:.3f}$ & & "
             rf"$1.00$ \\", r"\midrule"]
    for lab, key in items:
        k = resolve(by, key, layer)
        if not k or k not in by:
            continue
        m, lo, hi = ci(by[k])
        frac = (m - f) / max(t - f, 1e-9)
        lines.append(f"{lab} & ${m:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & "
                     f"${frac:+.2f}$ \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{name}.tex  ({n} notes)")


def tab_geometry(paths, out: pathlib.Path):
    """Norms, rank and directions of the span's content vector, by layer."""
    acc = {}
    for path in paths:
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            for g in r.get("geom", []):
                d = acc.setdefault(g["layer"], {})
                for k, v in g.items():
                    if k != "layer":
                        d.setdefault(k, []).append(v)
    if not acc:
        print("tab-geometry: nothing to read")
        return
    mean = {L: {k: sum(v) / len(v) for k, v in d.items()}
            for L, d in acc.items()}
    cols = [("d_norm", r"$\|\dvec\|$", "{:.0f}"),
            ("cos_d_all", r"$\cos(\dvec_i,\bar{\dvec})$", "{:.3f}"),
            ("frac_par_all", r"energy along $\bar{\dvec}$", "{:.2f}"),
            ("d_over_h", r"$\|\dvec\|/\|h\|$", "{:.2f}"),
            ("pr_d", r"PR$(\dvec)$", "{:.1f}"),
            ("pr_hg", r"PR$(h_{\text{skill}})$", "{:.1f}"),
            ("cos_d_cross", r"$\cos(\dvec_i,\dvec_k)$, other skill", "{:.3f}")]
    lines = [r"\begin{tabular}{@{}r" + "c" * len(cols) + r"@{}}", r"\toprule",
             "layer & " + " & ".join(c[1] for c in cols) + r" \\", r"\midrule"]
    for L in sorted(mean):
        vals = [c[2].format(mean[L][c[0]]) if c[0] in mean[L] else "--"
                for c in cols]
        lines.append(f"{L} & " + " & ".join(f"${v}$" for v in vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "tab-geometry.tex").write_text("\n".join(lines) + "\n",
                                          encoding="utf-8")
    print("tab-geometry.tex")


def tab_big40(paths, out: pathlib.Path, layer=8, name="tab-big40"):
    """The whole span battery on forty calculators instead of ten.

    The first version of every causal number here came from ten calculators and
    twenty items, which is the single most likely reason for a reviewer to stop
    reading. This is the same battery on forty, and the restriction that defines
    the split is recomputed inside it rather than carried over.
    """
    if name == "tab-big40":
        # The main table now uses paired, per-arm baselines and group CIs.
        # Do not let this legacy entry point overwrite it with pooled ratios.
        from main_evidence import span_battery
        if out.resolve() != pathlib.Path(__file__).resolve().parent:
            raise ValueError("Generate the audited main table in paper/ via main_evidence.py")
        span_battery()
        return
    by, n = load(paths, restrict="needs_document")
    if "receiver" not in by or "gold_in_context" not in by:
        print(f"{name}: no baselines in these shards, skipped")
        return
    cl = by.get("calculator_id")
    f = sum(by["receiver"]) / len(by["receiver"])
    t = sum(by["gold_in_context"]) / len(by["gold_in_context"])
    items = [(r"\emph{the gold document in context}", "gold_in_context"),
             (r"$h_{\text{recv}}+\dvec$ \ (=$h_{\text{skill}}$, $\alpha=1$)",
              "real"),
             (r"the same $\dvec$, only over the prefix shared with another skill", "realm"),
             (r"$h_{\text{recv}}+\tfrac12\dvec$", "a0.5"),
             (r"$\bar{\dvec}$, a skill in another family", "dfar"),
             (r"$\bar{\dvec}$, a skill in the same family", "dnear"),
             (r"the same $\dvec$, span positions permuted", "dshuf"),
             (r"noise, $\|\cdot\|$ matched per position", "drand"),
             (r"\emph{$h_{\text{recv}}$ itself} (the null arm)", "self"),
             (r"\emph{the filler document, unpatched}", "receiver")]
    lines = [r"\begin{tabular}{@{}lccc@{}}", r"\toprule",
             r"donor written over the document's span & accuracy & CI$_{95}$ "
             r"& fraction \\", r"\midrule"]
    for lab, key in items:
        k = resolve(by, key, layer)
        if not k or k not in by:
            continue
        m, lo, hi = ci(by[k], cl)
        frac = (m - f) / max(t - f, 1e-9)
        lines.append(f"{lab} & ${m:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & "
                     f"${frac:+.2f}$ \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{name}.tex  ({n} instances)")


def tab_ladder_models(specs, out: pathlib.Path, name="tab-ladder-models"):
    """The same channel and the same rank curve on three model widths.

    specs: [(label, d, n_layers, layer, [paths])]. The restricted split is
    recomputed per model, because "the receiver never solves this calculator"
    is a statement about a model and not about a calculator.
    """
    rows = []
    for lab, d, nl, layer, paths in specs:
        paths = [q for q in paths if pathlib.Path(q).exists()]
        if not paths:
            continue
        by, n = load(paths, restrict="needs_document")
        if "receiver" not in by:
            continue
        cl = by.get("calculator_id")
        f = sum(by["receiver"]) / len(by["receiver"])
        t = sum(by["gold_in_context"]) / len(by["gold_in_context"])
        cell = {"label": lab, "d": d, "nl": nl, "L": layer, "n": n,
                "gold": t, "recv": f}
        for key in ["real", "rank16", "rank32", "rank64", "rank128",
                    "rank64lo"]:
            k = resolve(by, key, layer)
            if k and k in by:
                m, _, _ = ci(by[k], cl)
                cell[key] = (m - f) / max(t - f, 1e-9)
        # k*: the rank at which half the curve's range is recovered,
        # interpolated in log2 k. The definition was fixed before the ladder
        # ran; a width-proportional account predicts 12 / 24 / 48.
        grid = [(kk, cell[f"rank{kk}"]) for kk in (16, 32, 64, 128)
                if f"rank{kk}" in cell]
        if len(grid) >= 2:
            half = grid[0][1] + 0.5 * (max(v for _, v in grid) - grid[0][1])
            for (k0, v0), (k1, v1) in zip(grid, grid[1:]):
                if v0 <= half <= v1 and v1 > v0:
                    cell["kstar"] = k0 * 2 ** ((half - v0) / (v1 - v0))
                    break
        rows.append(cell)
    if not rows:
        print(f"{name}: no ladder shards found, skipped")
        return
    hdr = (r"\begin{tabular}{@{}lrrrrr" + "r" * 7 + r"@{}}" + "\n" + r"\toprule"
           + "\n" + r"model & $d$ & layers & inject & $n$ & gold & "
           r"$\rho$(full) & $k{=}16$ & $32$ & $64$ & $128$ & bottom-$64$ "
           r"& $k^{*}$ \\"
           + "\n" + r"\midrule")
    out_lines = [hdr]
    for c in rows:
        g = lambda k: (f"${c[k]:+.2f}$" if k in c else "---")
        out_lines.append(
            f"{c['label']} & ${c['d']}$ & ${c['nl']}$ & ${c['L']}$ & ${c['n']}$ "
            f"& ${c['gold']:.3f}$ & {g('real')} & {g('rank16')} & "
            f"{g('rank32')} & {g('rank64')} & {g('rank128')} & "
            f"{g('rank64lo')} & "
            + (f"${c['kstar']:.0f}$" if "kstar" in c else "---")
            + r" \\")
    out_lines += [r"\bottomrule", r"\end{tabular}"]
    (out / f"{name}.tex").write_text("\n".join(out_lines) + "\n",
                                     encoding="utf-8")
    print(f"{name}.tex  ({len(rows)} models)")


def tab_prdiag(paths, out: pathlib.Path, name="tab-prdiag",
               layers=(8, 12, 14, 16, 20, 28, 34)):
    """Participation ratio of the content matrix, measured four ways.

    The plain number collapses at one layer; each of the three corrections for
    massive activations removes the collapse. Medians, because the plain column
    is bimodal and its mean describes no item.

    The PR columns are the CENTRED content matrix (d_pr_*), which is the
    quantity the text calls "the centred participation ratio" and the one
    Eq. (rank) truncates. They used to be the state's own PR (pr_hg /
    hg_pr_*), which differs by about fifteen points away from the collapse and
    left the paragraph's numbers unfindable in the table it cited. The last two
    columns stay on the state: a massive activation is a property of h, not of
    the difference between two h's.
    """
    rows = []
    for q in paths:
        for line in pathlib.Path(q).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        print(f"{name}: no shards, skipped")
        return
    per = collections.defaultdict(list)
    for r in rows:
        for gl in r.get("geom", []):
            per[gl["layer"]].append(gl)
    med = lambda gs, k: sorted(x[k] for x in gs if k in x)[len(
        [x for x in gs if k in x]) // 2]
    lines = [r"\begin{tabular}{@{}rrrrrrr@{}}", r"\toprule",
             r"& \multicolumn{4}{c}{participation ratio, computed\ldots} & "
             r"\multicolumn{2}{c}{massive activations} \\",
             r"\cmidrule(lr){2-5}\cmidrule(l){6-7}",
             r"layer & as usual & drop 4 loud & unit-norm. & drop 8 dims "
             r"& $\max/\mathrm{med}\,\|h\|$ & top-8 var. \\",
             r"\midrule"]
    for L in layers:
        gs = per.get(L)
        if not gs:
            continue
        lines.append(
            f"${L}$ & ${med(gs, 'pr_d'):.1f}$ & "
            f"${med(gs, 'd_pr_droppos'):.1f}$ & "
            f"${med(gs, 'd_pr_unit'):.1f}$ & "
            f"${med(gs, 'd_pr_dropdim'):.1f}$ & "
            f"${med(gs, 'hg_norm_ratio'):.1f}$ & "
            f"${100 * med(gs, 'hg_top_dim_share'):.1f}\\%$ \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{name}.tex  ({len(rows)} instances)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--medcalc", required=True)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    root = pathlib.Path(a.medcalc)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    g = lambda pat: sorted(str(q) for q in root.glob(pat))

    # Newest receiver definition first. Mixing receivers inside one table
    # would put arms measured against a 0.175 floor next to arms measured
    # against a 0.85 one; see filler_ids_for in wb_spanvec.
    newgen = g("*/spanvec-fs-first.jsonl")
    first = ((newgen + g("*/spanvec-fs-parts.jsonl")
              + g("*/spanvec-fs-quarters.jsonl")
              + g("*/spanvec-fs-nearfar.jsonl")) if newgen else
             (g("*/spanvec-dose.jsonl") + g("*/spanvec-ctrl.jsonl")
              + g("*/spanvec-doseR.jsonl") + g("*/spanvec-parts.jsonl")))
    if first:
        tab_battery(first, g("*/diffvec-cot-L*.jsonl"), out)
        tab_battery(first, g("*/diffvec-cot-L*.jsonl"), out,
                    restrict="needs_document", name="tab-battery-dep")
    dlnew = g("*/spanvec-fs-dl.jsonl")
    dl = (dlnew + g("*/spanvec-fs-dlctrl.jsonl") if dlnew else
          g("*/spanvec-doclast.jsonl") + g("*/spanvec-dl-ctrl.jsonl"))
    if dl:
        tab_skilltask(dl, out)
        tab_skilltask(dl, out, restrict="needs_document",
                      name="tab-skilltask-dep")
    # The layer sweep exists twice: the original twelve-layer run against each
    # skill's paired control, and a five-layer replication against the fixed
    # one. They are separate tables, not a merge -- different receivers.
    span = g("*/skillspan-*.jsonl")
    if span:
        tab_realspan(span, out)
        tab_realspan(span, out, name="tab-realspan-dep",
                     restrict="needs_document")
    # the depth shard carries no baselines of its own; the baseline shard ran
    # the same receiver, and load() refuses the merge if it did not
    repl = g("*/spanvec-fs-depth.jsonl")
    if repl:
        tab_realspan(repl + g("*/spanvec-fs-base.jsonl"), out,
                     name="tab-realspan-fixed")
    geo = g("*/spanvec-fs-geomf.jsonl") or g("*/spanvec-geom-first.jsonl")
    if geo:
        tab_geometry(geo, out)
    for tag, pat in [("tab-prdiag", "*/prdiag-8b-df.jsonl"),
                     ("tab-prdiag-06", "*/prdiag-06-df.jsonl"),
                     ("tab-prdiag-17", "*/prdiag-17-df.jsonl"),
                     ("tab-prdiag-dl", "*/prdiag-8b-dl.jsonl")]:
        q = g(pat)
        if q:
            tab_prdiag(q, out, name=tag)
    # The full-dataset rerun replaces the forty-calculator shards here: same
    # battery, same code, every rescued item of every calculator with at least
    # two (467 over 48; the restriction then keeps 135 over 14). The subset
    # shards big40-base/realm/ctrl/noise are still on disk and are what the
    # appendix compares against.
    big = g("*/full-battery-a.jsonl") + g("*/full-battery-b.jsonl")
    if not big:
        big = (g("*/big40-base.jsonl") + g("*/big40-realm.jsonl")
               + g("*/big40-ctrl.jsonl") + g("*/big40-noise.jsonl"))
    if big:
        tab_big40(big, out)
    tab_ladder_models(
        [("Qwen3-0.6B", 1024, 28, 6,
          g("*/lad06-base.jsonl") + g("*/lad06-rank.jsonl")),
         ("Qwen3-1.7B", 2048, 28, 6,
          g("*/lad17-big.jsonl") or g("*/lad17-rank2.jsonl") or
          (g("*/lad17-base.jsonl") + g("*/lad17-rank.jsonl"))),
         ("Qwen3-8B", 4096, 36, 8,
          g("*/full-rank-a.jsonl") + g("*/full-rank-b.jsonl")
          + g("*/full-battery-a.jsonl") or g("*/rank40-l8.jsonl"))], out)


if __name__ == "__main__":
    main()
