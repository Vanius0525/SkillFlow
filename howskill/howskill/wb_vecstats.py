"""M7 -- what is IN the vectors: a skill/task variance decomposition at scale.

    python -m howskill.wb_vecstats --cells data/cells.json \
        --model $BASE/models/Qwen3-8B --out results/p8-wb/vecstats

Why this experiment and not another injection. Injecting a vector back into a
forward pass measures whether the vector is SUFFICIENT to reproduce a
behaviour, and on this material that measurement reads zero for every position
group we have tried -- the answers take several hundred tokens, and a patch over
a few hundred positions does not carry that. Reading OUT of the vector asks a
different and still well-posed question: what does it encode? That question does
not need the effect to be transportable, and 55 skills x 20 instances is exactly
the design that answers it, which the synthetic tier (one document) cannot.

THE DECOMPOSITION, per instance i with skill s(i)

    d_i = h_gold(i) - h_wrong(i)      content
    g_i = h_wrong(i) - h_none(i)      presence
    t_i = h_gold(i) - h_none(i)       total

Each is a sum of a per-skill mean and a within-skill residual:

    d_i = mu_{s(i)} + e_i,     mu_s = mean of d over the instances of skill s

so eta^2 = Var(mu) / Var(d) is the fraction of the vector explained by WHICH
SKILL is present, and 1 - eta^2 is what varies with the task given the skill.
That is the "how much of this vector is skill and how much is skill x task"
question as an estimable quantity rather than a description.

Three readouts, all cheap once the vectors exist:

  eta2          the variance split above, per layer, for d, g, t and h_none.
                Prediction registered before running: eta2(d) >> eta2(g), since
                a length-matched WRONG document should not know which skill it
                is standing in for.
  ncm           leave-one-out nearest-class-mean classification of the skill
                id, on cosine similarity. Chance is 1/55. A vector that encodes
                skill identity is decodable; one that does not, is not. This is
                the same claim as eta2 with a scale a reader can hold.
  shape         norms, and participation ratio of the per-skill means and of
                the within-skill residuals separately -- how many dimensions
                carry "which skill" against "which task".

Only forwards, no generation, so the whole 1,100 instances cost minutes.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

import numpy as np

from howskill import arms as arms_mod
from howskill.prompts import build_prompt_spans
from howskill.wb_diffvec import VecScorer
from howskill.wb_replay import limit_threads

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


def eta2(vecs: np.ndarray, groups: list) -> float:
    """Fraction of total variance explained by the group label.

    Total variance is the mean squared distance to the grand mean; between is
    the same for the group means. Computed on the raw vectors rather than on
    normalised ones, because the norm is part of what we are describing.
    """
    grand = vecs.mean(0)
    tot = float(((vecs - grand) ** 2).sum(1).mean())
    if tot <= 0:
        return float("nan")
    idx = collections.defaultdict(list)
    for i, g in enumerate(groups):
        idx[g].append(i)
    between = 0.0
    for g, ii in idx.items():
        mu = vecs[ii].mean(0)
        between += len(ii) * float(((mu - grand) ** 2).sum())
    between /= len(vecs)
    return between / tot


def ncm_loo(vecs: np.ndarray, groups: list) -> tuple[float, float]:
    """(leave-one-out nearest-class-mean accuracy, chance).

    Cosine similarity to each class mean, with the held-out item removed from
    its own class mean -- otherwise a class of size 1 classifies itself
    perfectly and the number is meaningless. No training, no hyperparameter,
    no library: a classifier that can be wrong for only one reason.
    """
    labels = sorted(set(groups))
    lab_of = {g: k for k, g in enumerate(labels)}
    y = np.array([lab_of[g] for g in groups])
    sums = np.zeros((len(labels), vecs.shape[1]))
    counts = np.zeros(len(labels))
    for i in range(len(vecs)):
        sums[y[i]] += vecs[i]
        counts[y[i]] += 1
    hit = 0
    for i in range(len(vecs)):
        s = sums.copy()
        c = counts.copy()
        s[y[i]] -= vecs[i]
        c[y[i]] -= 1
        keep = c > 0
        mu = s[keep] / c[keep, None]
        mu = mu / (np.linalg.norm(mu, axis=1, keepdims=True) + 1e-9)
        v = vecs[i] / (np.linalg.norm(vecs[i]) + 1e-9)
        pred = np.arange(len(labels))[keep][int(np.argmax(mu @ v))]
        hit += int(pred == y[i])
    return hit / len(vecs), 1.0 / len(labels)


def participation_ratio(mat: np.ndarray, centre: bool = True) -> float:
    """Effective number of dimensions the rows span.

    Centred by default, and that is not a detail. Every content vector shares a
    large common component -- with a fixed control document, d_i = h_gold(i)
    minus the same vector for every i -- so an uncentred participation ratio is
    dominated by that offset and reads ~2 no matter how the classes are
    arranged. It read exactly that here, while nearest-class-mean separated 42
    classes at 0.92, which is geometrically impossible in two dimensions and is
    how the bug was caught. Centring asks the question actually intended: how
    many dimensions do the classes DIFFER in.
    """
    if centre:
        mat = mat - mat.mean(0, keepdims=True)
    s = np.linalg.svd(mat, compute_uv=False)
    s2 = (s ** 2).sum()
    return float(s2 * s2 / ((s ** 4).sum() + 1e-12))


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--fixed-filler", default=None,
                   help="use ONE skill document as the control for every "
                        "instance, instead of each gold skill's paired neutral. "
                        "Without this the control is a one-to-one function of "
                        "the gold skill, so g encodes the pairing and scores "
                        "0.63-0.97 on skill identification for a reason that "
                        "has nothing to do with presence. Pass a skill_id, or "
                        "`auto` to take the first one.")
    p.add_argument("--cells-keep", default="R,F,K,B")
    p.add_argument("--per-calc", type=int, default=20)
    p.add_argument("--max-calcs", type=int, default=55)
    p.add_argument("--layers", default="0,6,10,14,18,22,26,30,35")
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True, help="directory for report.json")
    p.add_argument("--save-vectors", default=None,
                   help="directory for the raw per-layer arrays (~300 MB); "
                        "omit to compute the statistics without writing them")
    a = p.parse_args(argv)

    from howskill.wb_diffvec import pick_instances

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    instances = {i["instance_id"]: i for i in json.load(
        open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
    skills = {s["skill_id"]: s for s in json.load(
        open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}
    pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"),
                          encoding="utf-8"))

    sc = VecScorer(a.model, attn=a.attn)
    sc.cue = ""
    layers = [int(x) for x in a.layers.split(",") if x.strip()]
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, instances, keep, a.per_calc, a.max_calcs, a.seed)
    os.makedirs(a.out, exist_ok=True)
    if a.save_vectors:
        os.makedirs(a.save_vectors, exist_ok=True)
    print(f"{len(todo)} instances over "
          f"{len({c for c, _, _ in todo})} calculators x {len(layers)} layers")

    meta, H = [], {k: {L: [] for L in layers} for k in ("gold", "ctrl", "none")}
    fixed = None
    if a.fixed_filler:
        fixed = (sorted(skills)[0] if a.fixed_filler == "auto"
                 else a.fixed_filler)
        if fixed not in skills:
            raise SystemExit(f"[FAIL] --fixed-filler {fixed} is not a skill_id")
        print(f"fixed filler: {fixed} (used as the control for every instance; "
              f"instances whose own gold skill is {fixed} are dropped)")
        todo = [t for t in todo
                if instances[t[2]]["skill_annotations"][0] != fixed]

    for k, (calc, cell, iid) in enumerate(todo, 1):
        inst = instances[iid]
        sid = inst["skill_annotations"][0]
        payload = {
            "gold": arms_mod.build(a.arm, skills.get(sid),
                                   neutral_for=skills.get(pairs.get(sid)), seed=0),
            "ctrl": arms_mod.build(
                a.ctrl_arm, skills.get(sid),
                neutral_for=skills.get(fixed if fixed else pairs.get(sid)),
                seed=0),
            "none": [],
        }
        for tag, pay in payload.items():
            sy, us, _ = build_prompt_spans(inst, skills=pay)
            caps, _ = sc.capture_all_layers(sy, us, layers)
            for L in layers:
                H[tag][L].append(caps[L].numpy().astype(np.float32))
        meta.append({"instance_id": iid, "cell": cell, "calculator_id": calc,
                     "skill_id": sid})
        if k % 25 == 0 or k == len(todo):
            print(f"  {k}/{len(todo)}", flush=True)

    calcs = [m["calculator_id"] for m in meta]
    cellv = [m["cell"] for m in meta]
    report = {"n": len(meta), "layers": layers,
              "n_calcs": len(set(calcs)),
              "cells": dict(collections.Counter(cellv)), "per_layer": {}}
    report["meta"] = meta

    print("\n  L    eta2(d) eta2(g) eta2(t) eta2(h0) | ncm(d) ncm(g) ncm(t) "
          "ncm(h0) chance | PR(mu_d) PR(res_d)")
    for L in layers:
        G = np.stack(H["gold"][L])
        C = np.stack(H["ctrl"][L])
        N = np.stack(H["none"][L])
        V = {"d": G - C, "g": C - N, "t": G - N, "h0": N}
        # Saving the raw vectors is off by default. Every number this script
        # reports is computed in memory from V; the arrays are ~300 MB for the
        # full calculator set, and both shared filesets on this cluster are at
        # their quota (a 50 MB dd writes 0 bytes). If they are wanted, point
        # --save-vectors at container-local storage, which has room, and copy
        # it off before the instance is reclaimed.
        if a.save_vectors:
            np.savez_compressed(
                os.path.join(a.save_vectors, f"layer_{L:02d}.npz"),
                **{k: v.astype(np.float16) for k, v in V.items()})
        row = {}
        for key, M in V.items():
            row[f"eta2_{key}"] = eta2(M, calcs)
            acc, chance = ncm_loo(M, calcs)
            row[f"ncm_{key}"], row["ncm_chance"] = acc, chance
            row[f"norm_{key}"] = float(np.linalg.norm(M, axis=1).mean())
        D = V["d"]
        mus, res = [], []
        by = collections.defaultdict(list)
        for i, c in enumerate(calcs):
            by[c].append(i)
        for c, ii in by.items():
            mu = D[ii].mean(0)
            mus.append(mu)
            res.extend(D[ii] - mu)
        row["pr_mu_d"] = participation_ratio(np.stack(mus))
        row["pr_mu_d_uncentred"] = participation_ratio(np.stack(mus),
                                                       centre=False)
        # residuals are already centred within class by construction
        row["pr_resid_d"] = participation_ratio(np.stack(res), centre=False)
        for cell in sorted(set(cellv)):
            m = [i for i, c in enumerate(cellv) if c == cell]
            row[f"norm_d_{cell}"] = float(np.linalg.norm(D[m], axis=1).mean())
        report["per_layer"][str(L)] = row
        print(f"  {L:3d}   {row['eta2_d']:.3f}  {row['eta2_g']:.3f}  "
              f"{row['eta2_t']:.3f}  {row['eta2_h0']:.3f}  |  "
              f"{row['ncm_d']:.3f}  {row['ncm_g']:.3f}  {row['ncm_t']:.3f}  "
              f"{row['ncm_h0']:.3f}  {row['ncm_chance']:.3f}  |  "
              f"{row['pr_mu_d']:7.1f} {row['pr_resid_d']:8.1f}", flush=True)

    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\n  eta2 is the share of a vector's variance explained by WHICH "
          f"SKILL is in the prompt;\n  1 - eta2 is what varies with the task "
          f"given the skill. ncm is leave-one-out\n  nearest-class-mean "
          f"accuracy on the same label, chance {1/len(set(calcs)):.3f}.")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
