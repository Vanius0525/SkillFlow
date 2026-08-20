#!/usr/bin/env python3
"""
E7: what does injecting a skill DO to the representation? (No hooks, no sweeps.)

This is the cheapest mechanistic experiment in the repo -- two forward passes per
item -- and it is the one that answers "is there a pattern in the internal
representation" directly rather than by inference from an intervention.

For every item, take the residual stream at the last prompt token, with and
without the skill, and study the difference

    d_i(L) = h_with(i, L) - h_without(i, L)

Four questions, four measurements, each with a stated failure reading:

  1. WHERE does the skill move the representation?
     ||d(L)|| relative to ||h_without(L)||, per layer. A flat curve means the
     skill perturbs everything a little (which is what adding any text does); a
     peak means something specific happens at that depth.

  2. Is it ONE direction, or one per item?
     Mean pairwise cosine between items' d_i at that layer. High = the skill
     writes essentially the same vector regardless of the question, i.e. "a skill
     is present" is a state, not content. Low = per-item content.
     This is the geometry behind E2's `mean` condition: if that condition
     recovers as well as `real`, this number must be high, and if it is not, one
     of the two measurements is wrong.

  3. How many dimensions does it live in?
     Participation ratio of the singular values of the stacked deltas -- a
     continuous "effective number of directions". 1 means a single shared axis;
     comparable to the item count means the deltas are essentially unstructured.

  4. Do DIFFERENT skills move it in the same direction?
     Cosine between the mean deltas of two skills, per layer. A high value is the
     strong claim: injection has a generic signature that is not about which
     skill. A low value says the signature is skill-specific, and then a probe
     trained on one skill should not transfer to another.

Optionally a linear probe (--probe family) asks whether the variable the task
turns on -- which conversion table is needed -- becomes linearly decodable from
the representation, and whether the skill makes it decodable EARLIER. Read that
one carefully: with 47 items and a 2048-dimensional residual, an unregularised
probe separates anything. This one reduces dimension first, cross-validates, and
prints a label-permutation baseline; if the real accuracy is not far above the
permuted one, there is no result, only capacity.

    python e7_repr.py --model ../models/Qwen3-1.7B \
        --tasks tasks/tier_a/tasks.jsonl \
        --skill tasks/tier_a/SKILL.zorb-units.md --mode mc --probe family

    # two skills at once: the cross-skill angle is the interesting output
    python e7_repr.py --model ../models/Qwen3-8B \
        --tasks tasks/tier_b/tasks.jsonl --mode num --limit 80 \
        --skill tasks/tier_b/SKILL.pchem-constants.md \
        --skill tasks/tier_b/SKILL.pchem-procedure.md
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import random
import time

import torch

import model as M

HERE = pathlib.Path(__file__).resolve().parent


def load_tasks(path, limit=None):
    items = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return items[:limit] if limit else items


def fields(item, mode):
    if "question_mc" in item:
        return (item["question_mc"], item["answer_mc"], None) if mode == "mc" \
            else (item["question_num"], item["answer_num"], None)
    return item["question"], item["answer_raw"], item.get("unit") or None


def sparkline(vals) -> str:
    chars = " .:-=+*#%@"
    fin = [v for v in vals if v == v]
    if not fin:
        return ""
    lo, hi = min(fin), max(fin)
    rng = (hi - lo) or 1.0
    return "".join(chars[min(9, max(0, int((v - lo) / rng * 9)))] if v == v else "?"
                   for v in vals)


def participation_ratio(x: torch.Tensor) -> float:
    """
    Effective number of directions in the rows of x.

    (sum s^2)^2 / sum s^4 over singular values. Continuous, so it does not need a
    threshold on "how small counts as zero" -- which a plain rank would, and any
    such threshold on float activations is arbitrary.
    """
    s = torch.linalg.svdvals(x.float())
    s2 = s ** 2
    return float((s2.sum() ** 2) / (s2 ** 2).sum().clamp_min(1e-12))


def mean_pairwise_cosine(x: torch.Tensor, cap: int = 400, seed: int = 0) -> float:
    """Mean cosine over item pairs; sampled when there are too many pairs."""
    n = x.shape[0]
    xn = torch.nn.functional.normalize(x.float(), dim=-1)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if len(pairs) > cap:
        pairs = random.Random(seed).sample(pairs, cap)
    if not pairs:
        return float("nan")
    return float(sum(float(xn[i] @ xn[j]) for i, j in pairs) / len(pairs))


def probe_cv(x: torch.Tensor, y: list, folds: int = 5, dims: int = 16,
             epochs: int = 300, seed: int = 0) -> float:
    """
    Cross-validated accuracy of a linear probe on labels y.

    PCA to `dims` first. With more features than items every label set is
    separable, so an unreduced probe measures capacity, not structure. The caller
    is expected to compare this against the same routine on permuted labels.
    """
    labels = sorted(set(y))
    if len(labels) < 2:
        return float("nan")
    idx = {l: i for i, l in enumerate(labels)}
    yt = torch.tensor([idx[v] for v in y])
    xf = x.float()
    xf = xf - xf.mean(0, keepdim=True)

    rng = random.Random(seed)
    order = list(range(len(y)))
    rng.shuffle(order)
    accs = []
    for f in range(folds):
        te = [order[i] for i in range(f, len(order), folds)]
        tr = [i for i in order if i not in set(te)]
        if not te or len(set(yt[tr].tolist())) < 2:
            continue
        # PCA fitted on the training split only; fitting on everything leaks the
        # test items into the representation the probe sees.
        u, s, v = torch.pca_lowrank(xf[tr], q=min(dims, len(tr) - 1))
        ztr, zte = xf[tr] @ v, xf[te] @ v
        ztr = ztr / (ztr.std(0, keepdim=True) + 1e-6)
        zte = zte / (zte.std(0, keepdim=True) + 1e-6)
        w = torch.zeros(ztr.shape[1], len(labels), requires_grad=True)
        b = torch.zeros(len(labels), requires_grad=True)
        opt = torch.optim.Adam([w, b], lr=0.05, weight_decay=1e-2)
        for _ in range(epochs):
            opt.zero_grad()
            loss = torch.nn.functional.cross_entropy(ztr @ w + b, yt[tr])
            loss.backward()
            opt.step()
        with torch.no_grad():
            pred = (zte @ w + b).argmax(-1)
            accs.append(float((pred == yt[te]).float().mean()))
    return sum(accs) / len(accs) if accs else float("nan")


def selftest() -> int:
    """
    Check the metrics on data whose answer is known. Seconds, no model.

    A geometry statistic that is quietly wrong is the worst failure mode here: it
    produces a number in the right range, the sparkline looks like a curve, and
    nothing anywhere says the axis is meaningless. So each metric is run on a
    case where the correct value is arithmetic, not opinion.
    """
    ok = True

    def chk(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'  OK  ' if cond else ' FAIL '}] {name}"
              + (f"  -- {detail}" if detail else ""))

    g = torch.Generator().manual_seed(0)
    n, d = 24, 64

    same = torch.randn(1, d, generator=g).repeat(n, 1)
    chk("identical deltas -> cosine 1", abs(mean_pairwise_cosine(same) - 1) < 1e-3,
        f"{mean_pairwise_cosine(same):.4f}")
    chk("identical deltas -> participation 1",
        abs(participation_ratio(same) - 1) < 1e-2, f"{participation_ratio(same):.3f}")

    rnd = torch.randn(n, d, generator=g)
    c_rnd, pr_rnd = mean_pairwise_cosine(rnd), participation_ratio(rnd)
    chk("independent deltas -> cosine ~ 0", abs(c_rnd) < 0.15, f"{c_rnd:+.4f}")
    chk("independent deltas -> participation ~ n", pr_rnd > 0.6 * n,
        f"{pr_rnd:.1f} of {n}")

    shared = same + 0.3 * torch.randn(n, d, generator=g)
    c_sh, pr_sh = mean_pairwise_cosine(shared), participation_ratio(shared)
    chk("shared direction + noise -> cosine between", 0.5 < c_sh < 0.99,
        f"{c_sh:+.3f}")
    chk("shared direction + noise -> participation small", pr_sh < 0.4 * n,
        f"{pr_sh:.1f} of {n}")

    # a probe must beat its own permutation baseline on separable labels, and
    # must NOT beat it on labels that carry no signal
    y = ["a"] * (n // 2) + ["b"] * (n - n // 2)
    off = torch.zeros(n, d)
    off[n // 2:, 0] = 6.0
    sep = torch.randn(n, d, generator=g) + off
    acc, perm = probe_cv(sep, y), probe_cv(sep, list(reversed(y)))
    chk("probe finds a separable label", acc > 0.8, f"{acc:.2f}")
    noise = torch.randn(n, d, generator=g)
    nacc = probe_cv(noise, y)
    chk("probe does not find a label that is not there", nacc < 0.75,
        f"{nacc:.2f} (permuted-on-separable {perm:.2f})")

    print()
    print("  metrics behave as defined" if ok else "  METRICS ARE WRONG")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--tasks")
    ap.add_argument("--skill", action="append",
                    help="may be given more than once; the cross-skill angle is "
                         "then reported")
    ap.add_argument("--mode", choices=["mc", "num"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--layer-step", type=int, default=1)
    ap.add_argument("--probe", choices=["none", "family"], default="none",
                    help="'family' probes which conversion table the item needs "
                         "(Tier A only)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--selftest", action="store_true",
                    help="check the geometry metrics against known cases and exit; "
                         "no model, no GPU")
    args = ap.parse_args()

    if args.selftest:
        print("e7 metric self-test")
        raise SystemExit(selftest())
    missing = [f"--{k}" for k in ("model", "tasks", "skill", "mode")
               if not getattr(args, k)]
    if missing:
        ap.error("missing " + ", ".join(missing))

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = load_tasks(args.tasks, args.limit)
    skills = {pathlib.Path(p).stem.replace("SKILL.", ""): M.load_skill(p)
              for p in args.skill}
    r = M.load(args.model, device=args.device)
    layers = list(range(0, r.n_layers, args.layer_step))

    print(f"model  : {args.model}")
    print(f"tasks  : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skills : {', '.join(skills)}")
    print(f"layers : {len(layers)} of {r.n_layers}")
    print(f"run id : {run_id}\n")
    M.write_run_info(out_dir, r, {
        "experiment": "e7_repr", "run_id": run_id, "tasks": str(args.tasks),
        "skills": list(skills), "mode": args.mode, "n_items": len(items),
        "layers": layers, "probe": args.probe,
    })

    # ---- capture ----------------------------------------------------------
    # The no-skill pass is shared across skills: same prompt, same activations.
    print("[1/2] capture")
    base_h, deltas = [], {k: [] for k in skills}
    t0 = time.time()
    for i, it in enumerate(items):
        q, _, unit = fields(it, args.mode)
        ids_no = M.encode(r, M.render(r, M.build_messages(q, None, args.mode, unit)))
        cap_no = M.capture(r, ids_no)
        h_no = torch.stack([cap_no.hidden_states[L + 1][0, -1].float().cpu()
                            for L in layers])
        del cap_no
        base_h.append(h_no)
        for name, body in skills.items():
            ids_yes = M.encode(r, M.render(r, M.build_messages(q, body, args.mode, unit)))
            cap = M.capture(r, ids_yes)
            h_yes = torch.stack([cap.hidden_states[L + 1][0, -1].float().cpu()
                                 for L in layers])
            del cap
            deltas[name].append(h_yes - h_no)
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s ({el/(i+1):.1f}s/item)",
                  flush=True)

    H = torch.stack(base_h)                              # [n, L, d]
    D = {k: torch.stack(v) for k, v in deltas.items()}   # name -> [n, L, d]
    n = H.shape[0]

    # ---- metrics ----------------------------------------------------------
    print("\n[2/2] geometry")
    report = {}
    for name, d in D.items():
        rel, cos, pr, top1 = [], [], [], []
        for li in range(len(layers)):
            dl = d[:, li]                                # [n, d]
            rel.append(float(dl.norm(dim=-1).mean() /
                             H[:, li].norm(dim=-1).mean().clamp_min(1e-6)))
            cos.append(mean_pairwise_cosine(dl))
            pr.append(participation_ratio(dl))
            s = torch.linalg.svdvals(dl - dl.mean(0, keepdim=True))
            top1.append(float((s[0] ** 2) / (s ** 2).sum().clamp_min(1e-12)))
        report[name] = {"rel_norm": rel, "mean_pairwise_cos": cos,
                        "participation_ratio": pr, "var_explained_pc1": top1}

        peak = max(range(len(layers)), key=lambda i: rel[i])
        print(f"\n  {name}")
        print(f"    ||delta||/||h||   {sparkline(rel)}   peak layer "
              f"{layers[peak]} ({rel[peak]:.3f})")
        print(f"    pairwise cosine   {sparkline(cos)}   at peak "
              f"{cos[peak]:+.3f}")
        print(f"    participation     {sparkline(pr)}   at peak "
              f"{pr[peak]:.1f} of {n} items")
        print(f"    var by PC1        {sparkline(top1)}   at peak "
              f"{top1[peak]:.1%}")

    # ---- cross-skill angle -------------------------------------------------
    cross = {}
    names = list(D)
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            ka, kb = names[a], names[b]
            cs = []
            for li in range(len(layers)):
                ma = D[ka][:, li].mean(0)
                mb = D[kb][:, li].mean(0)
                cs.append(float(torch.nn.functional.cosine_similarity(
                    ma.unsqueeze(0), mb.unsqueeze(0))))
            cross[f"{ka}|{kb}"] = cs
            print(f"\n  mean-direction cosine  {ka} vs {kb}")
            print(f"    {sparkline(cs)}   max {max(cs):+.3f} at layer "
                  f"{layers[max(range(len(cs)), key=lambda i: cs[i])]}")

    # ---- probe -------------------------------------------------------------
    probe = {}
    if args.probe == "family":
        y = [it.get("family") for it in items]
        if any(v is None for v in y):
            print("\n  [!] --probe family needs Tier A items (no `family` field); "
                  "skipped")
        else:
            print("\n  linear probe: which conversion table does this item need")
            for cond, X in [("no_skill", H)] + [(k, H + D[k]) for k in D]:
                acc = [probe_cv(X[:, li], y) for li in range(len(layers))]
                perm = list(y)
                random.Random(1).shuffle(perm)
                base = [probe_cv(X[:, li], perm) for li in range(len(layers))]
                probe[cond] = {"acc": acc, "permuted": base}
                bi = max(range(len(acc)), key=lambda i: acc[i])
                print(f"    {cond:<18} {sparkline(acc)}  best {acc[bi]:.2f} "
                      f"at layer {layers[bi]}  (permuted {base[bi]:.2f})")

    summary = {"run_id": run_id, "n_items": n, "layers": layers,
               "per_skill": report, "cross_skill_cosine": cross, "probe": probe}
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- reading -----------------------------------------------------------
    print(f"\n{'='*64}")
    print("  reading it:")
    for name, rep in report.items():
        peak = max(range(len(layers)), key=lambda i: rep["rel_norm"][i])
        c, pr = rep["mean_pairwise_cos"][peak], rep["participation_ratio"][peak]
        print(f"    {name}: peak at layer {layers[peak]}, ", end="")
        if c > 0.5:
            print("items share one direction there.")
            print("      That is a state ('a skill is present'), not content, and")
            print("      E2's mean-vector condition should recover as well as real.")
        elif pr > 0.5 * n:
            print("deltas are nearly unstructured.")
            print("      No low-dimensional signature -- a probe or a task vector")
            print("      should not be expected to work, and if E2 says otherwise,")
            print("      one of the two is measuring something else.")
        else:
            print(f"structured but item-specific ({pr:.1f} effective directions).")
            print("      A per-item vector should transfer; a single global one")
            print("      should not.")
    if cross:
        for k, cs in cross.items():
            mx = max(cs)
            verdict = ("the same direction -- injection has a generic signature"
                       if mx > 0.5 else
                       "different directions -- the signature is skill-specific")
            print(f"    {k}: {verdict} (max cosine {mx:+.2f})")
    print(f"\n  results: {out_dir}")
    print("=" * 64)


if __name__ == "__main__":
    main()
