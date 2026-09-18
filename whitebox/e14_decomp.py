#!/usr/bin/env python
"""
E14 -- decompose the injected displacement, then ask what each part can do.

Reading a skill document moves the residual stream at the last prompt position
from h_no to h_yes. E7 showed that most of that movement is not about the
document's content: a neutral filler of similar length moves it almost as far
and in almost the same direction (cross-document cosine 0.947 on Tier A, 0.944
-- 0.956 on Tier B). E11 then showed that the small remainder is what carries
the behaviour. E14 makes that pair of facts one measurement instead of two, and
adds the three questions E11 could not answer.

THE DECOMPOSITION (per item i, per layer L, at the last prompt position)

    t_i = h_yes - h_no        total displacement caused by "read this skill"
    g_i = h_fil - h_no        presence: what a document of the same shape does
    d_i = h_yes - h_fil       content: what is left after presence cancels
    t_i = g_i + d_i           exactly, by construction

WHAT IS NEW RELATIVE TO E11

1. The filler-prompt receiver. E11 only ever injected into the no-document
   forward, so "the content component works" was confounded with "the receiver
   had no document at all". Here the same vector is injected into a receiver
   that IS reading a document -- just the wrong one. If d only works on the
   empty receiver, it is repairing an absence rather than delivering content.
   Note h_fil + 1.0*d_i == h_yes exactly, so that arm is E2's `real` patch with
   the context swapped, and the pair (no-receiver, filler-receiver) isolates
   what the surrounding 700 tokens contribute.

2. Donor structure. E11's `add_diff_shift` took the donor from i+1, which in
   Tier A is usually the same conversion family. Same-family and cross-family
   donors are separated here, because "reusable skill vector" and "reusable
   within one row of the table" are different claims (HANDOFF-whitebox.md 17.1).

3. Geometry stored per item, not just per layer: ||d||, ||g||, ||t||, the angles
   between them, and the pairwise cosine structure of {d_i} split by family. The
   four-cell label (rescued / persistent / kept / broken) is stored with it, so
   the question "do the items the skill rescues have a different d?" is an
   offline groupby rather than another GPU run.

4. A dose-response on alpha. The magnitude was never measured, only assumed;
   an effect that is flat in alpha and an effect that scales are different
   mechanisms and the mean-vector artefact (a flattened output distribution
   that lifts lp(gold) without moving the argmax) shows up as the former.

READING IT

Accuracy first, logprob second. E2 established that lp(gold) can move a long way
with the argmax standing still, so a condition is only carrying content if it
moves the count of rescued items. `add_g` near the baseline at every layer is
what licenses calling d "the content component"; without that row the whole
decomposition is a definition rather than a finding.

    python e14_decomp.py --model ../models/Qwen3-1.7B \\
      --tasks tasks/tier_a/tasks.large.jsonl \\
      --skill tasks/tier_a/SKILL.zorb-units.md \\
      --filler tasks/filler-neutral.md --mode mc --limit 160 \\
      --run-id <run>/e14-tierA
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import random
import time

import torch

import genacc as GA
import model as M
import e2_patch as E2

HERE = pathlib.Path(__file__).resolve().parent

#: set from --mode in main(); read by gen_correct, which the sweep calls in a
#: closure and cannot take another argument without touching every call site.
COT = [False]


def cos(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.nn.functional.cosine_similarity(
        a.flatten().float(), b.flatten().float(), dim=0))


def norm_match(v: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """`v`'s direction carried at `target`'s norm."""
    return v / (v.norm(dim=-1, keepdim=True) + 1e-6) \
        * target.norm(dim=-1, keepdim=True)


def participation_ratio(mat: torch.Tensor, centre: bool = False) -> float:
    """(sum s^2)^2 / sum s^4 over the singular values -- effective rank.

    Uncentred, 1.0 means every item's difference vector points the same way,
    i.e. the content component is one shared direction. That number is almost
    always near 1 here and says little, because a large common offset swamps
    the spread; report it for completeness.

    Centred is the informative one: it removes the shared direction first and
    asks how many dimensions the item-to-item VARIATION occupies. "A reusable
    skill vector exists" predicts a small centred PR (the residual is noise);
    E11's item-specific result predicts a large one.
    """
    mat = mat.float()
    if centre:
        mat = mat - mat.mean(0, keepdim=True)
    s = torch.linalg.svdvals(mat)
    s2 = (s ** 2).sum()
    s4 = (s ** 4).sum()
    return float(s2 * s2 / (s4 + 1e-12))


def gen_correct(r, ids, gold, layer=None, position=None, vector=None,
                max_new=12, rel_tol=1e-6):
    """Thin wrapper over genacc.gen_ok, kept for the call sites below.

    The implementation lives in genacc.py because e10, e12 and e14 all need it
    and three copies of a patched decode is three chances for one of them to
    hold the hook open through the decode steps.
    """
    return GA.gen_ok(r, ids, gold, layer, position, vector,
                     max_new=max_new, rel_tol=rel_tol, cot=COT[0])


def cell_of(ok_no, ok_yes) -> str:
    """The four-cell label used by the HOWSKILLWORK line, applied to Tier A.

    R rescued  (wrong -> right)      the only cell where the skill demonstrably works
    F persist  (wrong -> wrong)      the skill was available and did not land
    K kept     (right -> right)      no headroom
    B broken   (right -> wrong)      the skill cost an item
    """
    if ok_no is None or ok_yes is None:
        return "?"
    return {(False, True): "R", (False, False): "F",
            (True, True): "K", (True, False): "B"}[(bool(ok_no), bool(ok_yes))]


def _aggregate(rows, conds, mean_delta, geometry):
    """Per-layer summary from the stored rows.

    Module level so that --resume can rebuild a layer's summary from its file
    without re-running any forwards. An arm scored but not decoded has ok=None
    in the free-form modes; counting that as 0.0 would print a confident zero
    for an arm nobody measured, so those report nan.
    """
    def acc_of(key, cell=None):
        v = [r_.get(f"ok_{key}") for r_ in rows
             if f"lp_{key}" in r_ and (cell is None or r_["cell"] == cell)]
        v = [x for x in v if x is not None]
        return sum(v) / len(v) if v else float("nan")

    def mean_of(key, fn):
        v = [fn(r_) for r_ in rows if f"lp_{key}" in r_]
        return sum(v) / len(v) if v else float("nan")

    return {
        "recovery": {c: (mean_of(c, lambda r_, c=c: r_[f"lp_{c}"] - r_["lp_no"])
                         / mean_delta if abs(mean_delta) > 1e-9 else float("nan"))
                     for c in conds},
        "lp": {c: mean_of(c, lambda r_, c=c: r_[f"lp_{c}"]) for c in conds},
        "accuracy": {c: acc_of(c) for c in conds},
        "acc_by_cell": {c: {cc: acc_of(c, cc) for cc in "RFKB"} for c in conds},
        "geometry": geometry,
    }


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--filler", required=True)
    ap.add_argument("--mode", choices=["mc", "num", "num_cot"], required=True)
    ap.add_argument("--limit", type=int, default=160)
    ap.add_argument("--tail-k", type=int, default=1,
                    help="how many of the last prompt positions to capture and "
                         "patch. k=1 is a capacity limit that was chosen, not "
                         "measured; sweeping it separates 'the effect does not "
                         "compress' from 'the effect does not compress into ONE "
                         "position'. In free-form answering that distinction "
                         "turned out to decide the experiment.")
    ap.add_argument("--layer-step", type=int, default=1)
    ap.add_argument("--layers", default=None,
                    help="explicit comma-separated layer list, overriding "
                         "--layer-step. On the 8B the sweep is dominated by "
                         "the number of layers, and the windows worth paying "
                         "for are known from E10/E12/E2.")
    ap.add_argument("--alpha", default="0.5,1.0,2.0")
    ap.add_argument("--gen-acc", action="store_true",
                    help="also decode greedily under each patch and score the "
                         "generated answer. Required for --mode num, where the "
                         "option-letter argmax does not exist; optional (and "
                         "slow) for --mode mc.")
    ap.add_argument("--gen-tokens", type=int, default=12)
    ap.add_argument("--gen-arms", default=None,
                    help="comma-separated arm names that get a decode as well "
                         "as a teacher-forced logprob. Decoding is ~10x the "
                         "cost of scoring, so on the 8B this is how the run "
                         "fits in an hour. Default: every arm.")
    ap.add_argument("--arms", default=None,
                    help="comma-separated arm names to run at all. Default: "
                         "every arm.")
    ap.add_argument("--no-filler-receiver", action="store_true",
                    help="skip the arms whose receiver is the filler prompt. "
                         "They are the expensive ones (a ~700 token forward "
                         "each) and the cheap half of the experiment still "
                         "stands without them.")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default=None,
                    help="sets WB_DTYPE for this run (Tier A logprobs are read "
                         "in float32; see model._default_dtype)")
    ap.add_argument("--resume", action="store_true",
                    help="skip layers whose output file already has every item")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    if args.mode.startswith("num") and not args.gen_acc:
        raise SystemExit(
            "[FAIL] --mode num has no option-letter argmax, so without "
            "--gen-acc there is no accuracy channel and the four cells "
            "(rescued / persistent / kept / broken) are undefined. Either "
            "pass --gen-acc or run --mode mc.")

    COT[0] = args.mode == "num_cot"
    if COT[0] and args.gen_tokens < 64:
        args.gen_tokens = 320

    if args.dtype:
        import os
        os.environ["WB_DTYPE"] = args.dtype
    alphas = [float(a) for a in str(args.alpha).split(",") if a.strip()]
    if 1.0 not in alphas:
        alphas.append(1.0)
    alphas.sort()
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    per_layer_cached: dict[int, list] = {}
    items = E2.load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    filler = M.load_skill(args.filler)
    r = M.load(args.model, device=args.device)
    if args.layers:
        layers = sorted({int(x) for x in args.layers.split(",") if x.strip()})
        bad = [L for L in layers if not 0 <= L < r.n_layers]
        if bad:
            raise SystemExit(f"[FAIL] --layers out of range for this model: {bad}")
    else:
        layers = list(range(0, r.n_layers, args.layer_step))
    want_arms = ({x.strip() for x in args.arms.split(",") if x.strip()}
                 if args.arms else None)
    gen_arms = ({x.strip() for x in args.gen_arms.split(",") if x.strip()}
                if args.gen_arms else None)
    rng = random.Random(args.seed)

    print(f"model  : {args.model}")
    print(f"tasks  : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skill  : {args.skill}")
    print(f"filler : {args.filler}")
    print(f"layers : {len(layers)} of {r.n_layers} (step {args.layer_step})")
    print(f"alphas : {alphas}   filler-receiver: "
          f"{not args.no_filler_receiver}   tail-k: {args.tail_k}")
    print(f"run id : {run_id}\n")

    M.write_run_info(out_dir, r, {
        "experiment": "e14_decomp", "run_id": run_id, "tasks": str(args.tasks),
        "arms": sorted(want_arms) if want_arms else "all",
        "gen_arms": sorted(gen_arms) if gen_arms else "all",
        "skill": str(args.skill), "filler": str(args.filler), "mode": args.mode,
        "n_items": len(items), "layers": layers, "alphas": alphas,
        "filler_receiver": not args.no_filler_receiver, "seed": args.seed,
        "tail_k": args.tail_k,
    })

    E2.OPTION_IDS.clear()
    if args.mode == "mc":
        for letter in "ABCD":
            t = r.tok(letter, add_special_tokens=False).input_ids
            if len(t) == 1:
                E2.OPTION_IDS[letter] = int(t[0])
        if len(E2.OPTION_IDS) != 4:
            print("  [!] option letters are not single tokens -- accuracy off.")
            E2.OPTION_IDS.clear()

    # ---- pass 1: three forwards and three captures per item ----------------
    print("[1/3] baselines + captures")
    base, t0 = [], time.time()
    for i, it in enumerate(items):
        q, gold, unit = E2.fields(it, args.mode)
        ids_no = M.encode(r, M.render(r, M.build_messages(q, None, args.mode, unit)))
        ids_yes = M.encode(r, M.render(r, M.build_messages(q, skill, args.mode, unit)))
        ids_fil = M.encode(r, M.render(r, M.build_messages(q, filler, args.mode, unit)))

        lp_no, ok_no, op_no = E2.score_with_patch(r, ids_no, gold)
        lp_yes, ok_yes, op_yes = E2.score_with_patch(r, ids_yes, gold)
        lp_fil, ok_fil, op_fil = E2.score_with_patch(r, ids_fil, gold)

        gen = {}
        if args.gen_acc:
            for tag, ids_ in (("no", ids_no), ("yes", ids_yes), ("fil", ids_fil)):
                okg, txt = gen_correct(r, ids_, gold, max_new=args.gen_tokens)
                gen[f"gok_{tag}"] = okg
                gen[f"gtxt_{tag}"] = txt
            # In num mode the generated answer IS the accuracy channel, so the
            # four-cell label has to come from it or it does not exist at all.
            if args.mode.startswith("num"):
                ok_no, ok_yes, ok_fil = (gen["gok_no"], gen["gok_yes"],
                                         gen["gok_fil"])

        base.append({
            "id": it["id"], "gold": gold, "family": it.get("family", "?"),
            "src": it.get("src"), "dst": it.get("dst"), "value": it.get("value"),
            "lp_no": lp_no, "lp_yes": lp_yes, "lp_fil": lp_fil,
            "ok_no": ok_no, "ok_yes": ok_yes, "ok_fil": ok_fil,
            "opt_no": op_no, "opt_yes": op_yes, "opt_fil": op_fil,
            "cell": cell_of(ok_no, ok_yes), **gen,
            "prompt_len_no": int(ids_no.shape[1]),
            "prompt_len_fil": int(ids_fil.shape[1]),
            "ids_no": ids_no, "ids_fil": ids_fil, "ids_yes": ids_yes,
            "v_no": M.capture_block_outputs(r, ids_no, layers, args.tail_k),
            "v_yes": M.capture_block_outputs(r, ids_yes, layers, args.tail_k),
            "v_fil": M.capture_block_outputs(r, ids_fil, layers, args.tail_k),
        })
        if (i + 1) % 20 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s ({el/(i+1):.2f}s/item)",
                  flush=True)

    n = len(base)
    cells = {c: [b["id"] for b in base if b["cell"] == c] for c in "RFKB"}
    mean_delta = sum(b["lp_yes"] - b["lp_no"] for b in base) / n
    fil_delta = sum(b["lp_fil"] - b["lp_no"] for b in base) / n
    acc = lambda k: sum(1 for b in base if b[k]) / n
    print(f"\n  accuracy  no-doc {acc('ok_no'):.3f}   filler {acc('ok_fil'):.3f}"
          f"   skill {acc('ok_yes'):.3f}"
          + ("   [generated answers]" if args.mode == "num" else ""))
    print(f"  logprob   skill-no {mean_delta:+.4f}   filler-no {fil_delta:+.4f}")
    print("  cells     " + "  ".join(f"{c}={len(cells[c])}" for c in "RFKB"))
    if len(cells["R"]) < 10:
        print("  [!] fewer than 10 rescued items -- the count channel has no "
              "resolution. Raise --limit or check the task set.")

    # ---- instrument check ---------------------------------------------------
    # Patch the LAST layer's output at the patched positions with the skill
    # run's state. The logits at the final position are then the skill run's by
    # construction, so the next token must be the skill run's next token. This
    # separates "the injection does not carry the content" from "the injection
    # is not happening", and the two are indistinguishable in an accuracy curve
    # that reads zero.
    Llast = layers[-1]
    if Llast == r.n_layers - 1:
        agree = 0
        probe = base[:min(10, n)]
        for b in probe:
            K = args.tail_k
            pos = (b["prompt_len_no"] - 1 if K == 1
                   else list(range(b["prompt_len_no"] - K, b["prompt_len_no"])))
            want = GA.first_token(r, b["ids_yes"]) if "ids_yes" in b else None
            got = GA.first_token(r, b["ids_no"], Llast, pos, b["v_yes"][Llast])
            agree += int(want == got) if want is not None else 0
        print(f"  self-test  last-layer patch reproduces the skill run's next "
              f"token on {agree}/{len(probe)} items"
              + ("" if agree == len(probe) else
                 "   [!] the hook is not writing where the capture read"))
    else:
        print("  self-test  skipped: the layer list does not include the last "
              "layer, where the check is exact.")

    # ---- donor assignment ---------------------------------------------------
    # Two derangements: one that stays inside the family, one that leaves it.
    # Both are fixed before the sweep so every layer sees the same pairing.
    by_fam: dict[str, list[int]] = {}
    for i, b in enumerate(base):
        by_fam.setdefault(b["family"], []).append(i)

    same_fam, cross_fam = [None] * n, [None] * n
    for fam, idxs in by_fam.items():
        if len(idxs) >= 2:
            rot = idxs[1:] + idxs[:1]
            for a, b_ in zip(idxs, rot):
                same_fam[a] = b_
    others = {fam: [i for f2, ii in by_fam.items() if f2 != fam for i in ii]
              for fam in by_fam}
    for i, b in enumerate(base):
        pool = others.get(b["family"]) or []
        cross_fam[i] = rng.choice(pool) if pool else None
    n_same = sum(x is not None for x in same_fam)
    n_cross = sum(x is not None for x in cross_fam)
    print(f"  donors    same-family {n_same}/{n}   cross-family {n_cross}/{n}")

    # ---- pass 2: geometry ---------------------------------------------------
    print("\n[2/3] geometry")
    geom = {}
    for L in layers:
        D = torch.stack([(b["v_yes"][L] - b["v_fil"][L]).flatten() for b in base])
        G = torch.stack([(b["v_fil"][L] - b["v_no"][L]).flatten() for b in base])
        T = torch.stack([(b["v_yes"][L] - b["v_no"][L]).flatten() for b in base])
        H = torch.stack([b["v_no"][L].flatten() for b in base])

        Dn = torch.nn.functional.normalize(D.float(), dim=-1)
        Gn = torch.nn.functional.normalize(G.float(), dim=-1)
        CD = Dn @ Dn.T
        CG = Gn @ Gn.T
        same = torch.zeros(n, n, dtype=torch.bool)
        for idxs in by_fam.values():
            for a, b_ in itertools.combinations(idxs, 2):
                same[a, b_] = same[b_, a] = True
        off = ~torch.eye(n, dtype=torch.bool)
        cross = off & ~same

        geom[L] = {
            "norm_d": float(D.norm(dim=-1).mean()),
            "norm_g": float(G.norm(dim=-1).mean()),
            "norm_t": float(T.norm(dim=-1).mean()),
            "norm_h_no": float(H.norm(dim=-1).mean()),
            "ratio_d_over_t": float((D.norm(dim=-1) / (T.norm(dim=-1) + 1e-9)).mean()),
            "ratio_d_over_h": float((D.norm(dim=-1) / (H.norm(dim=-1) + 1e-9)).mean()),
            "cos_d_g": float(torch.nn.functional.cosine_similarity(
                D.float(), G.float(), dim=-1).mean()),
            "cos_d_hno": float(torch.nn.functional.cosine_similarity(
                D.float(), H.float(), dim=-1).mean()),
            "cos_g_hno": float(torch.nn.functional.cosine_similarity(
                G.float(), H.float(), dim=-1).mean()),
            "cos_dd_within_family": float(CD[same].mean()) if same.any() else float("nan"),
            "cos_dd_cross_family": float(CD[cross].mean()) if cross.any() else float("nan"),
            "cos_dd_all": float(CD[off].mean()),
            "cos_gg_all": float(CG[off].mean()),
            "pr_d": participation_ratio(D),
            "pr_g": participation_ratio(G),
            "pr_d_centred": participation_ratio(D, centre=True),
            "pr_g_centred": participation_ratio(G, centre=True),
            # How much of a single item's content vector the shared mean
            # explains: the projection of d_i on the unit mean direction,
            # divided by ||d_i||. 1.0 = the item adds nothing of its own.
            "frac_d_on_mean": float((
                (D.float() @ torch.nn.functional.normalize(
                    D.float().mean(0), dim=0)).abs()
                / (D.norm(dim=-1) + 1e-9)).mean()),
        }
    print("  L   ||d||   ||g||   ||t||  d/t   cos(d,g)  cos(dd)in cos(dd)x"
          "   PRc_d  PRc_g  d_on_mean")
    for L in layers:
        z = geom[L]
        print(f"  {L:3d} {z['norm_d']:7.2f} {z['norm_g']:7.2f} {z['norm_t']:7.2f}"
              f" {z['ratio_d_over_t']:5.2f} {z['cos_d_g']:9.3f}"
              f" {z['cos_dd_within_family']:9.3f} {z['cos_dd_cross_family']:8.3f}"
              f" {z['pr_d_centred']:7.1f} {z['pr_g_centred']:6.1f}"
              f" {z['frac_d_on_mean']:10.3f}")

    # ---- pass 3: the injection sweep ---------------------------------------
    print("\n[3/3] injection sweep")
    # Per-layer files are written whole, so a layer either exists or does not;
    # --resume skips the ones that do. The platform reclaims these instances on
    # its own schedule and a 28-layer fp32 sweep is two hours, so losing the
    # first twenty layers to a reclaim in the twenty-first is a real cost and
    # not a hypothetical one.
    done_layers: set[int] = set()
    if args.resume:
        for L in layers:
            f = out_dir / f"layer_{L:02d}.jsonl"
            if f.exists() and f.stat().st_size > 0:
                try:
                    rows_prev = [json.loads(x) for x in
                                 f.read_text(encoding="utf-8").splitlines() if x.strip()]
                except json.JSONDecodeError:
                    continue                    # truncated by an interruption
                if len(rows_prev) == n:
                    done_layers.add(L)
                    per_layer_cached[L] = rows_prev
        if done_layers:
            print(f"  [resume] {len(done_layers)} complete layers already on "
                  f"disk: {sorted(done_layers)}")

    per_layer, t0 = {}, time.time()
    for k, L in enumerate(layers):
        # shared directions at this layer, restored to the typical per-item norm
        # Row-wise renormalisation, i.e. per patched position. A plain average
        # of residuals is short because the directions partly cancel, and a
        # short vector at a layer that never produces one is off-manifold --
        # which is precisely what the mean-vector artefact turned out to be.
        # With --tail-k > 1 each position gets its own norm, because position
        # norms differ by an order of magnitude across the chat suffix.
        def _renorm(stack):
            m = stack.mean(0)
            return (m / (m.norm(dim=-1, keepdim=True) + 1e-6)
                    * stack.norm(dim=-1).mean(0).unsqueeze(-1))

        Ds = torch.stack([b["v_yes"][L] - b["v_fil"][L] for b in base])
        dbar = _renorm(Ds)
        dbar_fam = {
            fam: _renorm(torch.stack([base[i]["v_yes"][L] - base[i]["v_fil"][L]
                                      for i in idxs]))
            for fam, idxs in by_fam.items()}

        if L in done_layers:
            # Reuse the stored rows rather than skipping the layer outright:
            # every aggregate below is computed from `rows`, so a `continue`
            # would leave this layer out of the summary and the printed tables.
            rows = per_layer_cached[L]
            conds = sorted({k2[3:] for r_ in rows for k2 in r_
                            if k2.startswith("lp_")
                            and k2 not in ("lp_no", "lp_yes", "lp_fil")})
            per_layer[L] = _aggregate(rows, conds, mean_delta, geom[L])
            continue

        rows = []
        for i, b in enumerate(base):
            h_no, h_yes, h_fil = b["v_no"][L], b["v_yes"][L], b["v_fil"][L]
            d, g, t = h_yes - h_fil, h_fil - h_no, h_yes - h_no
            # Aligned at the END of the prompt, not by absolute index: the
            # three prompts differ in length by the document, and the last K
            # positions are the question tail and the chat suffix in all three.
            K = args.tail_k
            pos_no = (b["prompt_len_no"] - 1 if K == 1
                      else list(range(b["prompt_len_no"] - K,
                                      b["prompt_len_no"])))
            pos_fil = (b["prompt_len_fil"] - 1 if K == 1
                       else list(range(b["prompt_len_fil"] - K,
                                       b["prompt_len_fil"])))

            row = {"id": b["id"], "gold": b["gold"], "family": b["family"],
                   "cell": b["cell"],
                   "lp_no": b["lp_no"], "lp_yes": b["lp_yes"], "lp_fil": b["lp_fil"],
                   "ok_no": b["ok_no"], "ok_yes": b["ok_yes"], "ok_fil": b["ok_fil"],
                   "opt_no": b["opt_no"], "opt_yes": b["opt_yes"],
                   "norm_d": float(d.norm()), "norm_g": float(g.norm()),
                   "norm_t": float(t.norm()), "norm_h_no": float(h_no.norm()),
                   "cos_d_g": cos(d, g), "cos_d_hno": cos(d, h_no),
                   "cos_d_t": cos(d, t)}

            def put(name, vec, ids=None, pos=None):
                if want_arms is not None and name not in want_arms:
                    return
                ids_ = ids if ids is not None else b["ids_no"]
                pos_ = pos if pos is not None else pos_no
                lp, ok, op = E2.score_with_patch(r, ids_, b["gold"], L, pos_, vec)
                row[f"lp_{name}"], row[f"ok_{name}"] = lp, ok
                if op is not None:
                    row[f"opt_{name}"] = op
                if args.gen_acc and (gen_arms is None or name in gen_arms):
                    okg, txt = gen_correct(r, ids_, b["gold"], L, pos_, vec,
                                           max_new=args.gen_tokens)
                    row[f"gok_{name}"] = okg
                    if args.mode.startswith("num"):
                        row[f"ok_{name}"] = okg
                    if i < 3:
                        row[f"gtxt_{name}"] = txt

            put("replace_real", h_yes)
            # identity: the receiver's own state written back where it was
            # read. Must reproduce ok_no / gok_no on every item, or the patch
            # path and the capture path disagree (the pre-fix mask fault).
            put("replace_self", h_no)
            for a in alphas:
                put(f"add_d_a{a:g}", h_no + a * d)
            put("add_d_renorm", norm_match(h_no + d, h_no))
            put("add_g", h_no + g)
            put("add_t", h_no + t)
            put("add_dbar", h_no + dbar)
            put("add_dbar_fam", h_no + dbar_fam[b["family"]])
            # Second-level split of the content component itself, along the
            # direction shared by every item and orthogonal to it:
            #     d_i = (d_i . u) u  +  d_i^perp,     u = dbar / ||dbar||
            # `par` is "the same content direction, this item's amount of it";
            # `perp` is what only this item contributes. add_dbar already tests
            # a fixed multiple of u; these two say how the behaviour divides
            # between the reusable direction and the per-item remainder, which
            # is the question a shared skill vector would live or die on.
            u = dbar / (dbar.norm(dim=-1, keepdim=True) + 1e-6)
            par = (d * u).sum(-1, keepdim=True) * u
            put("add_d_par", h_no + par)
            put("add_d_perp", h_no + (d - par))
            if same_fam[i] is not None:
                j = same_fam[i]
                row["donor_same_id"] = base[j]["id"]
                put("add_d_samefam",
                    h_no + (base[j]["v_yes"][L] - base[j]["v_fil"][L]))
            if cross_fam[i] is not None:
                j = cross_fam[i]
                row["donor_cross_id"] = base[j]["id"]
                put("add_d_crossfam",
                    h_no + (base[j]["v_yes"][L] - base[j]["v_fil"][L]))

            if not args.no_filler_receiver:
                # Same vectors, receiver is the filler forward. alpha=1 on d is
                # h_yes exactly, so it is named for what it is.
                put("fil_replace_real", h_yes, b["ids_fil"], pos_fil)
                for a in alphas:
                    if a == 1.0:
                        continue
                    put(f"fil_add_d_a{a:g}", h_fil + a * d, b["ids_fil"], pos_fil)
                put("fil_add_dbar", h_fil + dbar, b["ids_fil"], pos_fil)
                put("fil_add_g", h_fil + g, b["ids_fil"], pos_fil)
            rows.append(row)

        conds = sorted({k2[3:] for r_ in rows for k2 in r_
                        if k2.startswith("lp_")
                        and k2 not in ("lp_no", "lp_yes", "lp_fil")})
        per_layer[L] = _aggregate(rows, conds, mean_delta, geom[L])

        with open(out_dir / f"layer_{L:02d}.jsonl", "w", encoding="utf-8") as f:
            for r_ in rows:
                f.write(json.dumps(r_, ensure_ascii=False) + "\n")
        done_layers.add(L)

        if (k + 1) % 4 == 0 or k == len(layers) - 1:
            el = time.time() - t0
            head = per_layer[L]["accuracy"]
            print(f"    layer {L:3d}  " +
                  "  ".join(f"{c[:11]} {head[c]:.3f}"
                            for c in conds[:4]) +
                  f"   [{k+1}/{len(layers)}, {el:.0f}s]", flush=True)

    # ---- report -------------------------------------------------------------
    conds = sorted(per_layer[layers[0]]["accuracy"].keys())
    R = cells["R"]
    print("\n" + "=" * 78)
    print(f"  E14 decomposition   n={n}   R={len(R)} F={len(cells['F'])} "
          f"K={len(cells['K'])} B={len(cells['B'])}")
    print("=" * 78)
    for title, key in (("accuracy, all items", "accuracy"),
                       ("recovery of lp(gold)", "recovery")):
        print(f"\n  {title}")
        print("  layer " + "".join(f"{c[:14]:>15}" for c in conds))
        for L in layers:
            print(f"  {L:5d} " + "".join(
                f"{per_layer[L][key].get(c, float('nan')):15.3f}" for c in conds))
    print(f"\n  accuracy on the R cell only (n={len(R)}) -- read this first")
    print("  layer " + "".join(f"{c[:14]:>15}" for c in conds))
    for L in layers:
        print(f"  {L:5d} " + "".join(
            f"{per_layer[L]['acc_by_cell'][c]['R']:15.3f}" for c in conds))

    summary = {"experiment": "e14_decomp", "run_id": run_id, "n_items": n,
               "layers": layers, "alphas": alphas, "conditions": conds,
               "tail_k": args.tail_k,
               "acc_no": acc("ok_no"), "acc_filler": acc("ok_fil"),
               "acc_skill": acc("ok_yes"),
               "mean_delta_logprob": mean_delta,
               "filler_delta_logprob": fil_delta,
               "cells": {c: cells[c] for c in "RFKB"},
               "per_layer": {str(L): per_layer[L] for L in layers}}
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  results: {out_dir}")


if __name__ == "__main__":
    main()
