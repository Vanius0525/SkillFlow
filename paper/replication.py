#!/usr/bin/env python3
"""The replication table: every core measurement, per task family and model.

    python paper/replication.py            -> paper/tab-replication.tex (+ stdout)

One row per (task, model). Each column is recomputed from the run files:

    n (groups)    restricted items / groups (calculator or skill) whose receiver
                  never solves an item -- the same rule as tables.py and audit.py
    rho           the document's own span state written at the injection layer,
                  with a 95% bootstrap interval over groups
    ctrl          the largest control arm (noise, permuted positions, half dose,
                  another skill)
    handover      relative depth between the last layer with rho >= 0.5 and the
                  first below it
    k*            half of the rank curve's range above k=16, interpolated in
                  log2 k (the definition fixed before the model ladder ran)
    reading       relative depth of the first knockout layer that keeps >= 0.5 of
                  the rescued items, i.e. where blocking the document stops
                  costing most of the effect

Files are looked up in fetched/by-host; a missing run leaves its cell as "--".
"""
from __future__ import annotations

import collections
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parents[1]
BY = ROOT / "howskill/results/p8-wb/fetched/by-host"

# The MedCalc x Qwen3-8B row is the full-dataset rerun: every rescued item of
# every calculator with at least two (467 items over 48), not the forty
# calculators x four items the battery was developed on. The subset tags it
# replaces were fixmask-big40 / big40-depth / rank40-l8 / ko-8b-fast; they still
# exist on disk and Appendix "The full-dataset rerun" reports both. The other
# rows were not rerun at full scale and keep their own tags.
# 2026-09-18: the 0.6B and Mistral MedCalc rows and the 0.6B TheoremQA
# controls/knockout are rerun at full scale (CAMPAIGN-2026-09-18). Each row
# lists the new tags first; `pick` falls back to the old ones only while a new
# tag is missing, and says so.
NEW = {
    ("MedCalc", "Qwen3-0.6B"): (["q06-bat-a", "q06-bat-b"],
                                ["q06-depth-a", "q06-depth-b", "q06-bat-a"],
                                ["q06-rank-a", "q06-rank-b", "q06-rank-lo", "q06-bat-a"],
                                ["q06-ko"]),
    ("MedCalc", "Mistral-7B"): (["mis-bat-a", "mis-bat-b"],
                                ["mis-depth-a", "mis-depth-b", "mis-bat-a"],
                                ["mis-rank-a", "mis-rank-b", "mis-rank-lo", "mis-bat-a"],
                                ["mis-ko"]),
    ("TheoremQA", "Qwen3-0.6B"): (["t06-bat", "tqa06-rank"], None, None, ["t06-ko"]),
}
DONE_ROWS = {"q06-bat-a": 467, "q06-bat-b": 467, "q06-depth-a": 467, "q06-depth-b": 467,
             "q06-rank-a": 467, "q06-rank-b": 467, "q06-rank-lo": 467, "q06-ko": 469,
             "mis-bat-a": 221, "mis-bat-b": 221, "mis-depth-a": 221, "mis-depth-b": 221,
             "mis-rank-a": 221, "mis-rank-b": 221, "mis-rank-lo": 221, "mis-ko": 221,
             "t06-bat": 168, "t06-ko": 168}


# 2026-09-19: one-layer fill-ins of every depth sweep and knockout, run on the
# screened groups of each row (the knockout additionally only on its rescued
# items). With them, both boundaries of a row are read at one-layer resolution
# on the same items. Used only when every fill-in of the row is complete.
FILL = {
    ("MedCalc", "Qwen3-8B"): (["dep1-mc8-a", "dep1-mc8-b", "dep1-mc8-c", "dep1-mc8-d"],
                              ["ko1-mc8-a", "ko1-mc8-b", "ko1-mc8-c", "ko1-mc8-d", "ko1-mc8-e", "ko1-mc8-f"]),
    ("TheoremQA", "Qwen3-8B"): (["dep1-tqa8-a", "dep1-tqa8-b", "dep1-tqa8-c", "dep1-tqa8-d"],
                                ["ko1-tqa8-a", "ko1-tqa8-b", "ko1-tqa8-c"]),
    ("MedCalc", "Qwen3-0.6B"): (["dep1-mc06-a", "dep1-mc06-b"], ["ko1-mc06"]),
    ("TheoremQA", "Qwen3-0.6B"): (["dep1-tqa06"], ["ko1-tqa06"]),
    ("MedCalc", "Mistral-7B"): (["dep1-mcmis"], ["ko1-mcmis"]),
    ("TheoremQA", "Mistral-7B"): (["dep1-tqamis-a", "dep1-tqamis-b"], ["ko1-tqamis"]),
}
DONE_ROWS.update({**{f"dep1-mc8-{x}": 135 for x in "abcd"}, **{f"ko1-mc8-{x}": 134 for x in "abcdef"},
                  **{f"dep1-tqa8-{x}": 99 for x in "abcd"}, **{f"ko1-tqa8-{x}": 63 for x in "abc"},
                  "dep1-mc06-a": 362, "dep1-mc06-b": 362, "ko1-mc06": 90,
                  "dep1-tqa06": 132, "ko1-tqa06": 125, "dep1-mcmis": 92, "ko1-mcmis": 46,
                  "dep1-tqamis-a": 115, "dep1-tqamis-b": 115, "ko1-tqamis": 65})


def ko_curve(tags, groups=None):
    """Knockout retention by block-from layer, merged across sweep files.

    `load` cannot merge these: a fill-in's `layers`/`ok_block_from` would
    overwrite the base run's. Here each file contributes its own layers;
    ok_with / ok_without come from the run that decoded them. Items are the
    rescued ones (with and not without); with `groups` (the row's screened
    calculators) only those, i.e. the items its transfer curve is read on.
    Only layers present for every such item enter the curve.
    """
    per = {}
    for t in tags:
        for q in sorted(BY.glob(f"*/{t}.jsonl")):
            for line in open(q, encoding="utf-8"):
                if not line.strip():
                    continue
                r = json.loads(line)
                d = per.setdefault(r["instance_id"], {"calculator_id": r["calculator_id"], "ko": {}})
                for k in ("ok_with", "ok_without"):
                    if k in r:
                        d[k] = r[k]
                for L, ok in zip(r.get("layers", []), r.get("ok_block_from", [])):
                    if L in d["ko"] and d["ko"][L] != ok:
                        raise ValueError(f"Conflicting knockout L{L} for {r['instance_id']} in {q}")
                    d["ko"][L] = ok
    items = [d for d in per.values() if d.get("ok_with") and not d.get("ok_without")]
    if groups is not None:
        items = [d for d in items if d["calculator_id"] in groups]
    if not items:
        return {}, 0
    layers = sorted(set.intersection(*(set(d["ko"]) for d in items)))
    return {L: sum(bool(d["ko"][L]) for d in items) / len(items) for L in layers}, len(items)


def complete(tags):
    for t in tags:
        if not list(BY.glob(f"*/{t}.jsonl")):
            return False
        need = DONE_ROWS.get(t)
        if need is None:
            continue
        n = len(load([t]))
        if n < need:
            return False
    return True


ROWS = [
    # label, model, n_layers, inject layer, battery, depth runs, rank, knockout
    ("MedCalc", "Qwen3-8B", 36, 8,
     ["full-battery-a", "full-battery-b"],
     ["full-depth-a", "full-depth-b", "full-depth-c13", "full-depth-d",
      "full-battery-a"],
     ["full-rank-a", "full-rank-b", "x8-rank-x", "x8-rank-lo", "full-battery-a"],
     ["full-ko"]),
    ("TheoremQA", "Qwen3-8B", 36, 8, ["tqa-span"], ["tqa-depth"],
     ["tqa-rank"], ["tqa-ko"]),
    ("MedCalc", "Qwen3-0.6B", 28, 6, [], [], ["fixmask-lad06-rank"], None),
    ("TheoremQA", "Qwen3-0.6B", 28, 6, [], ["tqa06-depth"], ["tqa06-rank"], None),
    ("MedCalc", "Mistral-7B", 32, 4, ["mis3-big40-L4"],
     ["mis2-depth", "mis2-depth-fine"], ["mis3-rank-L4"], ["mis2-ko-b"]),
    ("TheoremQA", "Mistral-7B", 32, 4, ["tqamis-span"], ["tqamis-depth"],
     ["tqamis-rank"], ["tqamis-ko"]),
]
CONTROLS = ("drand", "dshuf", "a0.5", "dcross", "dfar", "dnear")


def resolved_rows():
    """Select complete measurement families; never splice partial new curves."""
    for task, model, nl, layer, bat, dep, rank, ko in ROWS:
        selected = [bat, dep, rank, ko]
        for i, tags in enumerate(NEW.get((task, model), (None,) * 4)):
            if tags and complete(tags):
                selected[i] = tags
        fill = FILL.get((task, model))
        if fill and selected[1] and selected[3] and complete(fill[0] + fill[1]):
            selected[1] = selected[1] + fill[0]
            selected[3] = selected[3] + fill[1]
        yield (task, model, nl, layer, *selected)


def load(tags):
    rows = {}
    for t in tags:
        for q in sorted(BY.glob(f"*/{t}.jsonl")):
            for line in open(q, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    target = rows.setdefault(r["instance_id"], {})
                    for key, value in r.items():
                        if (key.startswith("ok_") or key in
                                ("model", "filler", "format", "calculator_id")):
                            if key in target and target[key] != value:
                                raise ValueError(f"Conflicting {key} for {r['instance_id']} in {q}")
                    target.update(r)
    return list(rows.values())


def restricted(rows):
    bc = collections.defaultdict(list)
    for r in rows:
        if "ok_receiver" not in r or "ok_gold_in_context" not in r:
            raise ValueError(f"Missing paired baselines: {r['instance_id']}")
        bc[r["calculator_id"]].append(r)
    dep = [c for c, rs in bc.items() if not any(x.get("ok_receiver") for x in rs)]
    return {c: bc[c] for c in dep}


def rho(groups, key):
    sel = [r for rs in groups.values() for r in rs if key in r]
    if not sel:
        return None
    fr = lambda k: sum(bool(r.get(k)) for r in sel) / len(sel)
    g, f = fr("ok_gold_in_context"), fr("ok_receiver")
    return (fr(key) - f) / (g - f) if g > f else None


def boot(groups, key, B=2000):
    cs, rng, vals = list(groups), random.Random(0), []
    for _ in range(B):
        v = rho({i: groups[c] for i, c in enumerate(rng.choice(cs) for _ in cs)}, key)
        if v is not None:
            vals.append(v)
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]


def accuracy(groups, key, B=2000):
    """Accuracy and calculator-bootstrap CI on exactly the arm's item set."""
    groups = {c: [r for r in rs if key in r] for c, rs in groups.items()}
    groups = {c: rs for c, rs in groups.items() if rs}
    rows = [r for rs in groups.values() for r in rs]
    if not rows:
        raise ValueError(f"No observations for {key}")
    mean = sum(bool(r[key]) for r in rows) / len(rows)
    rng, cs, vals = random.Random(0), list(groups), []
    for _ in range(B):
        sample = [r for c in (rng.choice(cs) for _ in cs) for r in groups[c]]
        vals.append(sum(bool(r[key]) for r in sample) / len(sample))
    vals.sort()
    return mean, vals[int(.025 * B)], vals[int(.975 * B)], len(rows), len(groups)


def kstar(groups, layer):
    v = {k: rho(groups, f"ok_rank{k}_L{layer}") for k in (16, 32, 64, 128)}
    if any(x is None for x in v.values()):
        return None
    grid = sorted(v.items())
    half = grid[0][1] + 0.5 * (max(x for _, x in grid) - grid[0][1])
    for (k0, v0), (k1, v1) in zip(grid, grid[1:]):
        if v0 <= half <= v1 and v1 > v0:
            return k0 * 2 ** ((half - v0) / (v1 - v0))
    return None


def handover(groups, n_layers):
    keys = sorted({k for rs in groups.values() for r in rs for k in r
                   if k.startswith("ok_real_L")}, key=lambda k: int(k.split("L")[-1]))
    curve = [(int(k.split("L")[-1]), rho(groups, k)) for k in keys]
    for (l0, v0), (l1, v1) in zip(curve, curve[1:]):
        if v0 is not None and v1 is not None and v0 >= 0.5 > v1:
            return l0 / n_layers, l1 / n_layers
    return None


def reading(rows, n_layers):
    kp = [r for r in rows if r.get("ok_with") and not r.get("ok_without")]
    if not kp:
        return None
    for i, L in enumerate(kp[0]["layers"]):
        if sum(bool(r["ok_block_from"][i]) for r in kp) / len(kp) >= 0.5:
            return L / n_layers, len(kp)
    return None


def main():
    lines, out = [], []
    for task, model, nl, L, bat, dep, rk, ko in resolved_rows():
        cell = {"task": task, "model": model,
                "sources": dict(battery=bat or rk, depth=dep, rank=rk, knockout=ko)}
        base = restricted(load(bat or (rk or [])))
        if base:
            n = sum(len(v) for v in base.values())
            r = rho(base, f"ok_real_L{L}")
            lo, hi = boot(base, f"ok_real_L{L}")
            ctrl = [rho(base, f"ok_{c}_L{L}") for c in CONTROLS]
            ctrl = [c for c in ctrl if c is not None]
            cell.update(n=n, g=len(base), rho=r, lo=lo, hi=hi,
                        ctrl=max(ctrl) if ctrl else None)
            cell['controls'] = {c: {"rho": rho(base, f"ok_{c}_L{L}"),
                                    "n": sum(f"ok_{c}_L{L}" in r for rs in base.values() for r in rs)}
                                for c in CONTROLS if rho(base, f"ok_{c}_L{L}") is not None}
        d = restricted(load(dep)) if dep else {}
        cell["handover"] = handover(d, nl) if d else None
        rkg = restricted(load(rk)) if rk else {}
        cell["kstar"] = kstar(rkg, L) if rkg else None
        cell["rank_n"] = sum(map(len, rkg.values()))
        cell["rank_groups"] = len(rkg)
        cell["depth_n"] = sum(map(len, d.values()))
        fill = FILL.get((task, model))
        if ko and fill and set(fill[1]) <= set(ko):
            # one-layer resolution, on the rescued items of this row's
            # screened groups: the same items the transfer curve is read on
            kc, kn = ko_curve(ko, groups=set(d))
            first = next((Lk for Lk in sorted(kc) if kc[Lk] >= 0.5), None)
            cell["reading"] = (first / nl, kn) if first is not None else None
            cell["ko_curve"] = kc
            cell["paired"] = True
        else:
            cell["reading"] = reading(load(ko), nl) if ko else None
        out.append(cell)

    fmt = lambda x, p="{:.2f}": "--" if x is None else p.format(x)
    lines += [r"\begin{tabular}{@{}llrccccc@{}}", r"\toprule",
              r"task & model & $n$ (groups) & $\rho$ [95\% CI] & "
              r"max control & handover & reading & $k^{*}$ \\",
              r"\midrule"]
    for c in out:
        ho, rd = c["handover"], c["reading"]
        lines.append(
            f"{c['task']} & {c['model']} & "
            + (f"${c['n']}$ (${c['g']}$)" if "n" in c else "--") + " & "
            + (f"${c['rho']:.2f}$ $[{c['lo']:.2f},{c['hi']:.2f}]$" if c.get("rho") is not None else "--")
            + " & " + (f"${c['ctrl']:.2f}$" if c.get("ctrl") is not None else "--")
            + " & " + (f"${ho[0]:.2f}$--${ho[1]:.2f}$" if ho else "--")
            + " & " + (f"${rd[0]:.2f}$" if rd else "--")
            + " & " + (f"${c['kstar']:.0f}$" if c["kstar"] else "--") + r" \\")
        print(c)
    lines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "paper/tab-replication.tex").write_text("\n".join(lines) + "\n")
    (ROOT / "paper/replication-values.json").write_text(json.dumps(out, indent=2) + "\n")
    print("-> paper/tab-replication.tex")


if __name__ == "__main__":
    main()
