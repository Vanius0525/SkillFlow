#!/usr/bin/env python3
"""Every number the 2026-09-18 full-scale reruns produce for the manuscript.

    python3 whitebox/analysis/campaign_numbers.py

Writes whitebox/analysis/out/campaign-numbers.{json,md} and figures under
whitebox/analysis/out/figs/. Nothing is written into paper/: the manuscript is
edited separately and this file is the hand-off (CAMPAIGN-2026-09-18.md).

Estimators are the manuscript's own: `replication.rho` (recovery over the items
that have the arm, against the same items' receiver and gold), restricted per
run by `replication.restricted`, intervals by `replication.boot` (calculator /
skill-group bootstrap), and the pre-registered grid knee `replication.kstar`.
"""
from __future__ import annotations

import collections
import json
import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "paper"))
import replication as rep  # noqa: E402  (import only; its main() writes paper/)

OUT = ROOT / "whitebox/analysis/out"
TA = ROOT / "whitebox/results/fetched/tA"
res = {}
md = []


def r2(x):
    return None if x is None else round(x, 3)


def arm(groups, key):
    v = rep.rho(groups, key)
    if v is None:
        return None
    lo, hi = rep.boot(groups, key)
    n = sum(1 for rs in groups.values() for r in rs if key in r)
    return {"rho": r2(v), "ci": [r2(lo), r2(hi)], "n": n}


def kstar_ci(groups, L, B=2000):
    cs, rng, vals = list(groups), random.Random(0), []
    for _ in range(B):
        g = {i: groups[c] for i, c in enumerate(rng.choice(cs) for _ in cs)}
        k = rep.kstar(g, L)
        if k is not None:
            vals.append(k)
    vals.sort()
    return [r2(vals[int(.025 * len(vals))]), r2(vals[int(.975 * len(vals)) - 1])] if vals else None


def section(title):
    md.append(f"\n## {title}\n")


# ---- 1. doc-first dall / normrecv, doc-last dall ---------------------------
section("1. Common shift and norm (sec. 4.4; were pre-fix)")
g = rep.restricted(rep.load(["full-battery-a", "x8-extra"]))
res["x8_extra"] = {k: arm(g, f"ok_{k}_L8") for k in ("real", "dall", "normrecv")}
gl = rep.restricted(rep.load(["full-dl-a", "x8-dl-dall"]))
res["x8_dl_dall"] = {k: arm(gl, f"ok_{k}_L8") for k in ("real", "dall")}
res["x8_extra"]["n_items_groups"] = [sum(map(len, g.values())), len(g)]
res["x8_dl_dall"]["n_items_groups"] = [sum(map(len, gl.values())), len(gl)]
md.append(f"doc-first (n={res['x8_extra']['n_items_groups']}): " + ", ".join(
    f"{k} {v['rho']} {v['ci']}" for k, v in res["x8_extra"].items() if isinstance(v, dict)))
md.append(f"\ndoc-last (n={res['x8_dl_dall']['n_items_groups']}): " + ", ".join(
    f"{k} {v['rho']} {v['ci']}" for k, v in res["x8_dl_dall"].items() if isinstance(v, dict)))

# ---- 2. layer windows and the all-layer transplant (Fig. 3c, sec. 4.6) -----
section("2. Layer windows with the battery's receiver (Fig. 3c) and every layer at once")
gw = rep.restricted(rep.load(["x8-win-a", "x8-win-b", "full-battery-a"]))
res["windows_8b"] = {k: arm(gw, f"ok_real_{k}") for k in
                     ("L16", "w8_11", "w12_15", "w14_19", "w16_35", "w0_35")}
res["windows_8b"]["self_L16_equals_receiver"] = None
wa = {r["instance_id"]: r for r in rep.load(["x8-win-a"])}
ba = {r["instance_id"]: r for r in rep.load(["full-battery-a"])}
both = [i for i in wa if "ok_self_L16" in wa[i] and i in ba]
res["windows_8b"]["self_L16_equals_receiver"] = [
    sum(bool(wa[i]["ok_self_L16"]) == bool(ba[i]["ok_receiver"]) for i in both), len(both)]
def load_overridden(tags, base_tag):
    """The pre-2026-09-18 merge: `tags` rows, then the battery's baselines
    written over theirs. replication.load now refuses this (conflicting
    receivers), which is correct; it is reproduced here only to show what the
    manuscript's old window numbers were computed from."""
    rows = {}
    for t in tags:
        for q in sorted(rep.BY.glob(f"*/{t}.jsonl")):
            for line in open(q):
                if line.strip():
                    r = json.loads(line)
                    rows.setdefault(r["instance_id"], {}).update(r)
    for q in sorted(rep.BY.glob(f"*/{base_tag}.jsonl")):
        for line in open(q):
            if line.strip():
                r = json.loads(line)
                if r["instance_id"] in rows:
                    rows[r["instance_id"]].update({k: v for k, v in r.items()
                                                   if k in ("ok_receiver", "ok_gold_in_context", "ok_none")})
    return list(rows.values())


old = rep.restricted(load_overridden(["full-window"], "full-battery-a"))
res["windows_8b_old_ctrl_receiver"] = {k: r2(rep.rho(old, f"ok_real_{k}")) for k in
                                       ("L16", "w8_11", "w12_15", "w14_19", "w16_35")}
res["windows_8b"]["n_items_groups"] = [sum(map(len, gw.values())), len(gw)]
md.append("| arm | new (fixed-skill receiver) | 95% CI | old (ctrl receiver, battery baselines) |")
md.append("|---|---|---|---|")
for k in ("L16", "w8_11", "w12_15", "w14_19", "w16_35", "w0_35"):
    v = res["windows_8b"][k]
    md.append(f"| {k} | {v['rho']} | {v['ci']} | {res['windows_8b_old_ctrl_receiver'].get(k, '--')} |")
md.append(f"\nidentity (self_L16 == battery receiver): {res['windows_8b']['self_L16_equals_receiver']}")
gt = rep.restricted(rep.load(["t8-win", "tqa-span"]))
res["windows_tqa8b"] = {k: arm(gt, f"ok_real_{k}") for k in
                        ("L16", "w8_11", "w12_15", "w14_19", "w16_35")}
res["windows_tqa8b"]["n_items_groups"] = [sum(1 for rs in gt.values() for r in rs if "ok_real_w8_11" in r), len(gt)]
oldt = rep.restricted(load_overridden(["tqa-window"], "tqa-span"))
res["windows_tqa8b_old"] = {k: r2(rep.rho(oldt, f"ok_real_{k}")) for k in
                            ("L16", "w8_11", "w12_15", "w14_19", "w16_35")}
md.append("\nTheoremQA windows, new vs old: " + ", ".join(
    f"{k} {res['windows_tqa8b'][k]['rho']} (old {res['windows_tqa8b_old'][k]})"
    for k in ("w8_11", "w12_15", "w14_19", "w16_35", "L16")))

# ---- 3. rank curves on three models (Fig. 2, Table 3) ----------------------
section("3. Rank truncation, full data, three models (Fig. 2)")
TOP = (1, 2, 4, 8, 16, 24, 32, 40, 48, 56, 64, 96, 128, 192, 256, 384, 512)
BOT = (4, 16, 32, 64, 128)
for name, L, tags in (("Qwen3-8B", 8, ["full-battery-a", "full-rank-a", "full-rank-b", "x8-rank-x", "x8-rank-lo"]),
                      ("Qwen3-0.6B", 6, ["q06-bat-a", "q06-rank-a", "q06-rank-b", "q06-rank-lo"]),
                      ("Mistral-7B", 4, ["mis-bat-a", "mis-rank-a", "mis-rank-b", "mis-rank-lo",
                                         "mis-rank-hi"]),
                      ("TheoremQA/Qwen3-8B", 8, ["tqa-rank", "tqa-rank-d1", "tqa-rank-d2"]),
                      ("TheoremQA/Qwen3-0.6B", 6, ["tqa06-rank", "tqa06-rank-d1", "tqa06-rank-d2"]),
                      ("TheoremQA/Mistral-7B", 4, ["tqamis-rank", "tqamis-rank-d1", "tqamis-rank-d2"])):
    gg = rep.restricted(rep.load(tags))
    ent = {"n_items_groups": [sum(map(len, gg.values())), len(gg)],
           "full": arm(gg, f"ok_real_L{L}"),
           "top": {k: arm(gg, f"ok_rank{k}_L{L}") for k in TOP},
           "bottom": {k: arm(gg, f"ok_rank{k}lo_L{L}") for k in BOT},
           "kstar": r2(rep.kstar(gg, L)), "kstar_ci": kstar_ci(gg, L)}
    ent["top"] = {k: v for k, v in ent["top"].items() if v}
    ent["bottom"] = {k: v for k, v in ent["bottom"].items() if v}
    res[f"rank_{name}"] = ent
    md.append(f"**{name}** n={ent['n_items_groups']}, untruncated {ent['full']['rho']} {ent['full']['ci']}, "
              f"k* = {ent['kstar']} {ent['kstar_ci']}")
    md.append("  top: " + ", ".join(f"{k}:{v['rho']}" for k, v in ent["top"].items()))
    md.append("  bottom: " + ", ".join(f"{k}:{v['rho']}" for k, v in ent["bottom"].items()))

# ---- 4. replication table rows (Table 3) -----------------------------------
section("4. Replication rows now at full scale (Table 3)")
CONTROLS = ("drand", "dshuf", "a0.5", "dcross", "dfar")
for label, nl, L, bat, dep, rk, ko in (
        ("MedCalc / Qwen3-0.6B", 28, 6, ["q06-bat-a", "q06-bat-b"],
         ["q06-depth-a", "q06-depth-b", "q06-bat-a"],
         ["q06-rank-a", "q06-rank-b", "q06-rank-lo", "q06-bat-a"], ["q06-ko"]),
        ("MedCalc / Mistral-7B", 32, 4, ["mis-bat-a", "mis-bat-b"],
         ["mis-depth-a", "mis-depth-b", "mis-bat-a"],
         ["mis-rank-a", "mis-rank-b", "mis-rank-lo", "mis-bat-a"], ["mis-ko"]),
        ("TheoremQA / Qwen3-0.6B", 28, 6, ["t06-bat", "tqa06-rank"], ["tqa06-depth"],
         ["tqa06-rank"], ["t06-ko"])):
    gb = rep.restricted(rep.load(bat))
    ctrl = {c: r2(rep.rho(gb, f"ok_{c}_L{L}")) for c in CONTROLS}
    ctrl = {c: v for c, v in ctrl.items() if v is not None}
    gd = rep.restricted(rep.load(dep))
    depth = sorted((int(k.split("L")[-1]), r2(rep.rho(gd, k))) for k in
                   {k for rs in gd.values() for r in rs for k in r if k.startswith("ok_real_L")})
    kor = rep.load(ko)
    ent = {"n_items_groups": [sum(map(len, gb.values())), len(gb)],
           "rho": arm(gb, f"ok_real_L{L}"), "controls": ctrl,
           "max_control": max(ctrl.values()) if ctrl else None,
           "handover": rep.handover(gd, nl), "depth_curve": depth,
           "reading": rep.reading(kor, nl), "ko_rows": len(kor),
           "kstar": r2(rep.kstar(rep.restricted(rep.load(rk)), L))}
    res[f"table3_{label}"] = ent
    md.append(f"**{label}** n={ent['n_items_groups']} rho {ent['rho']['rho']} {ent['rho']['ci']}; "
              f"max control {ent['max_control']} {ctrl}; handover {ent['handover']}; "
              f"reading {ent['reading']} (ko rows {ent['ko_rows']}); k* {ent['kstar']}")
    md.append(f"  depth curve: {depth}")

# ---- 5. Table 1: answer format, post-fix, 358 items, 36 layers --------------
section("5. Answer format (Table 1), post-fix, all 358 items, 36 layers each")


def e14(tags):
    out = {}
    for t in tags:
        for p in sorted((TA / t).glob("layer_*.jsonl")):
            out[int(p.stem.split("_")[1])] = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return out


def curve(L, key, cell="R"):
    c = {}
    for layer, rows in L.items():
        rr = [r for r in rows if r["cell"] == cell and r.get(key) is not None]
        if rr:
            c[layer] = sum(bool(r[key]) for r in rr) / len(rr)
    return c


t1 = {}
for fmt, tags in (("multiple choice", ["tA-mc"]), ("numeric", ["tA-num-a", "tA-num-b"]),
                  ("chain of thought", ["tA-cot-1", "tA-cot-2", "tA-cot-3", "tA-cot-4"]),
                  ("numeric, last 4 positions", ["tA-num-k4"]),
                  ("numeric, last 16 positions", ["tA-num-k16"]),
                  ("numeric, last 32 positions", ["tA-num-k32"]),
                  ("numeric, last 48 positions", ["tA-num-k48"]),
                  ("numeric, whole prompt (k=61)", ["tA-num-k61"])):
    L = {k: v for k, v in e14(tags).items() if v}
    if not L:
        continue
    any_rows = next(iter(L.values()))
    cells = collections.Counter(r["cell"] for r in any_rows)
    ent = {"layers": len(L), "n": len(any_rows), "cells": dict(cells)}
    for a in ("replace_real", "add_d_a1", "add_g"):
        c = curve(L, f"ok_{a}")
        if c:
            best = max(c, key=c.get)
            ent[a] = {"best": r2(c[best]), "best_layer": best, "max_layer_le_22": r2(max(v for k, v in c.items() if k <= 22))}
    ident = [r["ok_replace_self"] == r["ok_no"] for rows in L.values() for r in rows if "ok_replace_self" in r]
    if ident:
        ent["identity"] = [sum(ident), len(ident)]
    base = any_rows
    ent["acc"] = {k: r2(sum(bool(r[k]) for r in base) / len(base)) for k in ("ok_no", "ok_yes", "ok_fil")}
    t1[fmt] = ent
cs = e14(["tA-cot-self"])
if cs:
    ident = [r["ok_replace_self"] == r["ok_no"] for rows in cs.values() for r in rows]
    t1["chain of thought"]["identity"] = [sum(ident), len(ident)]
res["table1"] = t1
md.append("| format | n | R | best replace (layer) | content add_d | presence add_g | max through L22 | identity | acc no/skill/filler |")
md.append("|---|---|---|---|---|---|---|---|---|")
for fmt, e in t1.items():
    rr = e.get("replace_real", {})
    md.append(f"| {fmt} | {e['n']} | {e['cells'].get('R')} | {rr.get('best')} (L{rr.get('best_layer')}) | "
              f"{e.get('add_d_a1', {}).get('best', '--')} | {e.get('add_g', {}).get('best', '--')} | "
              f"{rr.get('max_layer_le_22')} | {e.get('identity')} | {e['acc']} |")

# ---- 6. Sec 4.1 decomposition, Qwen3-1.7B fp32, 358 items -------------------
section("6. Decomposition on the synthetic task (sec. 4.1), Qwen3-1.7B fp32, 358 items")
dn = {k: v for k, v in e14(["d17-neutral", "d17-neutral-b"]).items() if v}
if dn and 26 in dn:
    r26 = dn[26]
    fr = lambda key, cell: r2(sum(bool(r[key]) for r in r26 if r["cell"] == cell) /
                              max(1, sum(1 for r in r26 if r["cell"] == cell)))
    d = {"cells": dict(collections.Counter(r["cell"] for r in r26))}
    for a in ("replace_real", "add_d_a1", "add_g", "add_d_a0.5", "add_d_a2", "add_dbar"):
        d[a] = {c: fr(f"ok_{a}", c) for c in "RFKB"}
    best = {}
    for a in ("replace_real", "add_d_a1", "add_g"):
        c = curve(dn, f"ok_{a}")
        if not c:
            continue
        b = max(c, key=c.get)
        best[a] = [b, r2(c[b])]
    d["best_layer_R"] = best
    ident = [r["ok_replace_self"] == r["ok_no"] for rows in dn.values() for r in rows if "ok_replace_self" in r]
    d["identity"] = [sum(ident), len(ident)]
    res["decomp_17"] = d
    md.append(f"cells {d['cells']}; identity {d['identity']}; best layer on R {best}")
    md.append("layer 26 by cell (R/F/K/B): " + "; ".join(
        f"{a} {d[a]}" for a in ("replace_real", "add_d_a1", "add_g", "add_d_a0.5", "add_d_a2", "add_dbar")))
for tag in ("d17-shuffled", "d17-corrupted"):
    # <tag>-b holds the fourteen layers the first pass skipped, among them 23
    # and 25, which are inside the 21--27 band the paper quotes.
    L = e14([tag, tag + "-b"])
    if L:
        dc, gc = curve(L, "ok_add_d_a1"), curve(L, "ok_add_g")
        dv = {k: v for k, v in dc.items() if 21 <= k <= 27}
        gv = {k: v for k, v in gc.items() if 21 <= k <= 27}
        if not dv or not gv:
            continue
        dbest = max(dc, key=dc.get)
        res[tag] = {"layers": sorted(L),
                    "add_d_R_21_27": [r2(min(dv.values())), r2(max(dv.values()))],
                    "add_g_R_21_27": [r2(min(gv.values())), r2(max(gv.values()))],
                    "add_d_best": [dbest, r2(dc[dbest])],
                    "add_d_curve": {k: r2(v) for k, v in sorted(dc.items())},
                    "add_g_curve": {k: r2(v) for k, v in sorted(gc.items())}}
        md.append(f"{tag} ({len(L)} layers): content d on R over L21-27 "
                  f"{res[tag]['add_d_R_21_27']}, presence g {res[tag]['add_g_R_21_27']}, "
                  f"best d {res[tag]['add_d_best']}")

# ---- 7. geometry: massive activations, corrected PR -------------------------
section("7. Span geometry on every calculator (sec. 4.6 spectral paragraph)")
for tag in ("geom-8b", "geom-06", "geom-17"):
    rows = rep.load([tag])
    if not rows:
        continue
    per = collections.defaultdict(list)
    for r in rows:
        for gl_ in r.get("geom", []):
            per[gl_["layer"]].append((r["calculator_id"], gl_))
    med = lambda L, k: statistics.median(g[k] for _, g in per[L])
    Ls = sorted(per)
    ent = {"items": len(rows), "calcs": len({r["calculator_id"] for r in rows}),
           "pr_hg_median": {L: r2(med(L, "pr_hg")) for L in Ls},
           "pr_droppos_median": {L: r2(med(L, "hg_pr_droppos")) for L in Ls},
           "norm_ratio_median": {L: r2(med(L, "hg_norm_ratio")) for L in Ls}}
    if 16 in per:
        loud = [(c, g) for c, g in per[16] if g["hg_norm_ratio"] > 20]
        ent["L16_loud_items"] = len(loud)
        ent["L16_loud_calcs"] = len({c for c, _ in loud})
        ent["L16_loud_ratio_range"] = [r2(min(g["hg_norm_ratio"] for _, g in loud)),
                                       r2(max(g["hg_norm_ratio"] for _, g in loud))] if loud else None
        ent["L16_loud_dims"] = collections.Counter(tuple(sorted(g["hg_top_dim"][:2])) for _, g in loud).most_common(3)
    lo20 = [L for L in Ls if L <= 20]
    dpr = {L: statistics.mean(g["d_pr_droppos"] for _, g in per[L]) for L in lo20}
    ent["content_pr_droppos_L0_20"] = [r2(min(dpr.values())), r2(max(dpr.values()))]
    ent["frac_par_all_by_layer"] = {L: r2(statistics.mean(g["frac_par_all"] for _, g in per[L])) for L in Ls}
    res[tag] = ent
    md.append(f"**{tag}** {ent['items']} items / {ent['calcs']} calcs; L16 loud "
              f"{ent.get('L16_loud_items')} items ({ent.get('L16_loud_calcs')} calcs), ratio {ent.get('L16_loud_ratio_range')}, dims {ent.get('L16_loud_dims')}; "
              f"content PR (4 loud positions dropped) L0-20 {ent['content_pr_droppos_L0_20']}")
    md.append(f"  PR as usually computed: {ent['pr_hg_median']}")
    md.append(f"  PR, loud positions dropped: {ent['pr_droppos_median']}")

# ---- 8. span width on the restricted set -----------------------------------
ba_r = rep.restricted(rep.load(["full-battery-a"]))
ws = [r["n_patched"] for rs in ba_r.values() for r in rs]
res["span_width_restricted"] = [min(ws), max(ws)]
section("8. Span width")
md.append(f"restricted set (135 items): {min(ws)}-{max(ws)} positions")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "campaign-numbers.json").write_text(json.dumps(res, indent=1, default=str))
(OUT / "campaign-numbers.md").write_text("# Full-scale rerun numbers (2026-09-18)\n" + "\n".join(md) + "\n")
print("\n".join(md))
