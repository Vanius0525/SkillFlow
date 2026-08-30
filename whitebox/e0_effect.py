#!/usr/bin/env python3
"""
Phase 0: does the skill produce an effect worth explaining?

Nothing downstream runs until this passes. If the skill moves accuracy by a few
points, that difference sits inside sampling noise and every mechanistic measure
built on it is explaining noise -- see HANDOFF-whitebox.md section 2.

Reports both dependent variables:

  accuracy   readable, but binary and coarse
  logprob    mean log-probability of the gold answer; per-item, continuous, much
             lower variance. This is the primary DV. A skill can shift it
             consistently while accuracy barely moves, and the patching
             experiments can still be run against it.

Paired throughout: the same items under both conditions, so item difficulty
cancels. The bootstrap resamples items, not conditions.

    # Tier A, the positive control
    python e0_effect.py --model Qwen/Qwen3-1.7B \
        --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
        --mode mc --run-id tierA-1.7b

    # Tier B
    python e0_effect.py --model Qwen/Qwen3-8B \
        --tasks tasks/tier_b/tasks.jsonl --skill tasks/tier_b/SKILL.pchem-constants.md \
        --mode num --limit 120 --run-id tierB-const-8b

    # drop the items the model already answers correctly with no skill, and
    # write a filtered task file for the mechanistic experiments to use
    python e0_effect.py ... --filter-known tasks/tier_b/tasks.filtered.jsonl
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import random
import re
import time
from collections import Counter

import torch

import model as M

HERE = pathlib.Path(__file__).resolve().parent


def load_tasks(path, limit=None):
    items = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return items[:limit] if limit else items


def fields(item, mode):
    """Tier A carries both formats; Tier B is numeric only."""
    if "question_mc" in item:
        if mode == "mc":
            return item["question_mc"], item["answer_mc"], None
        # Tier B v2 is multiple-choice only: its answer is "which setup",
        # which has no numeric form. Saying so beats a KeyError three
        # frames down on a field the caller never knew existed.
        if "question_num" not in item:
            raise SystemExit(
                f"[FAIL] {item['id']} has no numeric form -- this task set "
                f"is multiple-choice only. Run it with --mode mc.")
        return item["question_num"], item["answer_num"], None
    return item["question"], item["answer_raw"], item.get("unit") or None


# Ordered for display; whatever a task file actually carries is what gets
# measured. Tier B labels its options by which factor of the 2x2 is wrong,
# Tier A by which misreading of the conversion table produces them.
AXES = ("wrong_const", "wrong_rel", "wrong_both",
        "echo", "wrong_row", "wrong_family", "inverted", "other")

AXIS_LABEL = {
    "wrong_const":  "常数轴 (correct vs wrong_const)",
    "wrong_rel":    "关系式轴 (correct vs wrong_rel)",
    "wrong_both":   "两轴都错 (correct vs wrong_both)",
    "echo":         "抄题干 (correct vs echo)",
    "wrong_row":    "读错行 (correct vs wrong_row)",
    "wrong_family": "选错表 (correct vs wrong_family)",
    "inverted":     "方向反了 (correct vs inverted)",
    "other":        "其它 (correct vs other)",
}


def option_margins(r, ids, item):
    """
    Log-prob margin between the gold option and each kind of foil.

    This exists because the gold logprob alone cannot see what Tier B needs it to
    see. E7 found that putting ANY long document in context displaces the
    prompt-final residual in one shared direction, which lifts every plausible
    continuation together -- and that lift lands squarely in lp(gold). A margin
    between two options cancels, by construction, anything that moves both of
    them equally, so it is blind to exactly the component that dominated Tier A.

    The second reason is the ceiling. Tier B v2's baseline is 0.819, leaving
    18.1pp of headroom, so the accuracy arm of the gate asks the document to fix
    83% of what is left. A margin has no ceiling: an item the model already
    answers correctly can still show the margin widen, so the measurement does
    not run out of room the way accuracy does.

    Nothing is invented here. build.py already records, per item, what each
    letter means (`option_kinds`), so the foils are read off the task file --
    they are the options the model was shown.
    """
    kinds = item.get("option_kinds")
    if not kinds:
        return None
    by_kind = {}
    for letter, kind in kinds.items():
        lp = M.answer_logprob(r, ids, letter)
        # Two options can share a kind -- Tier A often has two wrong-row foils.
        # Keep the strongest one: the margin then asks whether the model prefers
        # the gold option over the BEST competitor of that kind, which is the
        # conservative reading and does not get diluted by an easy second foil.
        if kind not in by_kind or lp > by_kind[kind]:
            by_kind[kind] = lp
    if "correct" not in by_kind:
        return None
    return {k: by_kind["correct"] - by_kind[k]
            for k in by_kind if k != "correct"}


def run_condition(r, items, skill, mode, max_new, margins=False):
    out = []
    t0 = time.time()
    for i, it in enumerate(items):
        q, gold, unit = fields(it, mode)
        ids = M.encode(r, M.render(r, M.build_messages(q, skill, mode, unit)))
        text = M.generate(r, ids, max_new_tokens=max_new)
        lp = M.answer_logprob(r, ids, gold)

        if mode == "mc":
            pred = M.extract_mc(text)
            ok = pred == gold
        else:
            pred = M.extract_num(text)
            ok = M.num_correct(pred, float(gold))

        # Whether an answer was found at all, kept separate from whether it was
        # right. A model that answers in prose scores zero and looks like a model
        # that answers wrongly; the two call for completely different fixes.
        rec = {"id": it["id"], "correct": bool(ok), "logprob": lp,
               "parsed": pred is not None, "pred": None if pred is None else str(pred),
               "raw": text.strip()[:200], "gold": gold,
               "n_prompt_tokens": int(ids.shape[1])}
        if margins:
            m = option_margins(r, ids, it)
            if m:
                rec["margins"] = m
        out.append(rec)
        if (i + 1) % 20 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s  "
                  f"({el/(i+1):.1f}s/item)", flush=True)
    return out


def chance_level(items, mode):
    """Accuracy a model gets by guessing. None when there is nothing to guess from."""
    if mode != "mc":
        return None
    letters = set()
    for it in items[:20]:
        q = it.get("question_mc") or it.get("question") or ""
        letters |= set(re.findall(r"(?m)^\s*([A-Z])[.)]\s", q))
    return 1.0 / len(letters) if letters else None


def paired_bootstrap(a, b, n=5000, seed=0):
    """CI for mean(b) - mean(a), resampling items. Returns (lo, hi) at 95%."""
    rng = random.Random(seed)
    k = len(a)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(k) for _ in range(k)]
        diffs.append(sum(b[i] - a[i] for i in idx) / k)
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--margins", action="store_true",
                    help="also score every labelled option and report the "
                         "gold-vs-foil margin per axis. Needs `option_kinds` on "
                         "the items. A margin cancels anything that moves both "
                         "options equally, so unlike the gold logprob it is "
                         "blind to the generic 'a document is present' shift, "
                         "and it has no ceiling.")
    ap.add_argument("--control", action="store_true",
                    help="this pair is a NEGATIVE CONTROL (off-domain "
                         "skill, filler document). Inverts the verdict: "
                         "not clearing the gate is the expected result, "
                         "and clearing it is the finding.")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--filter-known", metavar="OUT_JSONL", default=None,
                    help="write a task file with the no-skill-correct items removed")
    args = ap.parse_args()

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id

    items = load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    print(f"model    : {args.model}")
    print(f"tasks    : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skill    : {args.skill}  ({len(skill.split())} words)")
    print(f"run id   : {run_id}\n")

    r = M.load(args.model, device=args.device)
    M.write_run_info(out_dir, r, {
        "run_id": run_id, "tasks": str(args.tasks), "skill": str(args.skill),
        "mode": args.mode, "n_items": len(items), "decoding": "greedy",
    })
    print("structure:", json.dumps(r.describe(), ensure_ascii=False), "\n")

    # Auto-on wherever build.py labelled the options; there is no reason to make
    # the caller remember a flag for a measurement the task file already supports.
    want_margins = args.margins and any("option_kinds" in it for it in items)
    if args.margins and not want_margins:
        print("  (--margins asked for, but these items carry no `option_kinds` "
              "-- skipped)\n")

    print("[1/2] without skill")
    no = run_condition(r, items, None, args.mode, args.max_new_tokens, want_margins)
    print("[2/2] with skill")
    yes = run_condition(r, items, skill, args.mode, args.max_new_tokens, want_margins)

    acc_no = sum(x["correct"] for x in no) / len(no)
    acc_yes = sum(x["correct"] for x in yes) / len(yes)
    lp_no = [x["logprob"] for x in no]
    lp_yes = [x["logprob"] for x in yes]

    c_no = [float(x["correct"]) for x in no]
    c_yes = [float(x["correct"]) for x in yes]
    acc_lo, acc_hi = paired_bootstrap(c_no, c_yes)
    lp_lo, lp_hi = paired_bootstrap(lp_no, lp_yes)

    # McNemar counts: the discordant pairs are the whole evidence in a paired design
    b = sum(1 for x, y in zip(no, yes) if not x["correct"] and y["correct"])
    c = sum(1 for x, y in zip(no, yes) if x["correct"] and not y["correct"])

    # Per-axis margins: the paired delta and its CI, one axis at a time.
    margin_stats = {}
    for ax in AXES:
        a = [x["margins"][ax] for x in no if "margins" in x and ax in x["margins"]]
        b = [y["margins"][ax] for y in yes if "margins" in y and ax in y["margins"]]
        if len(a) != len(b) or not a:
            continue
        lo, hi = paired_bootstrap(a, b)
        margin_stats[ax] = {
            "n": len(a),
            "no_skill": sum(a) / len(a), "with_skill": sum(b) / len(b),
            "delta": sum(b) / len(b) - sum(a) / len(a),
            "ci95": [lo, hi],
            "gained": sum(1 for x, y in zip(a, b) if y > x),
            "lost": sum(1 for x, y in zip(a, b) if y < x),
        }

    parse_no = sum(x["parsed"] for x in no) / len(no)
    parse_yes = sum(x["parsed"] for x in yes) / len(yes)
    chance = chance_level(items, args.mode)

    with io.open(out_dir / "per_item.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x, y in zip(no, yes):
            f.write(json.dumps({"id": x["id"], "gold": x["gold"],
                                "no_skill": x, "with_skill": y},
                               ensure_ascii=False) + "\n")

    d_acc = (acc_yes - acc_no) * 100
    d_lp = sum(lp_yes) / len(lp_yes) - sum(lp_no) / len(lp_no)
    summary = {
        "run_id": run_id, "n": len(items),
        # mode belongs in the summary, not only in run-info.json: report.py
        # differences an arm against its control, and `num` accuracy is not on
        # the same scale as `mc` accuracy. Without this the pairing had to be
        # inferred from chance_level being None.
        "mode": args.mode,
        "acc_no_skill": acc_no, "acc_with_skill": acc_yes,
        "delta_acc_pp": d_acc,
        "delta_acc_ci95_pp": [acc_lo * 100, acc_hi * 100],
        "mean_logprob_no_skill": sum(lp_no) / len(lp_no),
        "mean_logprob_with_skill": sum(lp_yes) / len(lp_yes),
        "delta_logprob": d_lp, "delta_logprob_ci95": [lp_lo, lp_hi],
        "mcnemar_gained": b, "mcnemar_lost": c,
        "parse_rate_no_skill": parse_no, "parse_rate_with_skill": parse_yes,
        "chance_level": chance,
        # Axis margins. Keyed by foil kind; `wrong_const` is the pair that
        # differs only in the constant, `wrong_rel` only in the relation.
        "margins": margin_stats or None,
        # report.py must not apply the Phase 0 gate to a control the way it does
        # to a candidate pair: for a control, not clearing it is the pass.
        "is_control": bool(args.control),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*64}")
    print(f"  n = {len(items)}")
    print(f"  accuracy   {acc_no:.3f} -> {acc_yes:.3f}   "
          f"delta {d_acc:+.1f}pp  CI95 [{acc_lo*100:+.1f}, {acc_hi*100:+.1f}]")
    print(f"  logprob    {summary['mean_logprob_no_skill']:.3f} -> "
          f"{summary['mean_logprob_with_skill']:.3f}   "
          f"delta {d_lp:+.3f}  CI95 [{lp_lo:+.3f}, {lp_hi:+.3f}]")
    print(f"  discordant gained {b}, lost {c}")
    print(f"  answer found in output: {parse_no:.3f} without skill, "
          f"{parse_yes:.3f} with"
          + (f"   (chance = {chance:.3f})" if chance else ""))
    print(f"{'='*64}")

    # A baseline below chance is not a hard task, it is an unparsed one: the
    # model answered in a form the extractor does not recognise, and every such
    # item counts as wrong. The delta then partly measures "the skill made the
    # output parseable" (H3, formatting) rather than "the skill supplied the
    # missing knowledge" -- a different mechanism, and not the one being studied.
    # A baseline below chance has two causes that call for opposite responses,
    # and the parse rate separates them. Unparsed output -> the delta partly
    # measures H3 (formatting). Parsed output -> the model answered, in a
    # form the extractor understood, and was systematically wrong: it is being
    # pulled to a particular distractor. That is a fact about the item set and
    # it does NOT put an H3 share in the delta. The old branch assumed the
    # first cause and printed the parse rate as if it supported it, which at
    # 100% read as "answers were found in only 100% of the outputs".
    if chance and acc_no < chance * 0.8 and parse_no < 0.9:
        print(f"  [!] Baseline {acc_no:.3f} is below chance ({chance:.3f}), and")
        print(f"      {1-parse_no:.0%} of no-skill outputs carry no extractable "
              f"answer.")
        print("      Part of the delta is the skill making the output parseable")
        print("      (H3), not the skill supplying knowledge. Read the `raw` field")
        print("      of per_item.jsonl. See HANDOFF-whitebox.md 12.3b.")
        for x in [x for x in no if not x["parsed"]][:3]:
            print(f"        {x['id']}: {x['raw'][:70]!r}")
    elif chance and acc_no < chance * 0.8:
        print(f"  [!] Baseline {acc_no:.3f} is below chance ({chance:.3f}) with "
              f"{parse_no:.0%} of")
        print("      outputs parsed. So this is not a formatting problem: the")
        print("      model answered every item and was reliably wrong, which means")
        print("      one distractor is attracting it. There is no H3 share in the")
        print("      delta, but part of it may be the skill stopping that pull")
        print("      rather than supplying knowledge -- errors.py splits the two.")
        wrong = [x for x in no if x["parsed"] and not x["correct"]]
        picked = Counter(x["pred"] for x in wrong)
        if picked:
            top, k = picked.most_common(1)[0]
            print(f"      most common wrong answer: {top!r} on {k}/{len(wrong)} "
                  f"of the wrong items")
    elif parse_no < 0.9 or parse_yes < 0.9:
        print(f"  [!] Some outputs carry no extractable answer "
              f"({1-parse_no:.0%} without skill, {1-parse_yes:.0%} with). Part of")
        print("      any delta is formatting compliance rather than task content.")

    # Section 2 requires a floor and a ceiling: "无 skill 准确率不能接近 0 或 1".
    # Nothing checked it, and the chance-level warning above cannot -- it needs a
    # chance level, which numeric mode has none of. A pool the model gets 7% of
    # answers a different question than the one asked: accuracy has no room to
    # move, so a gate failure says the items are too hard, NOT that the skill is
    # inert. Those two conclusions get written up very differently.
    at_floor, at_ceiling = acc_no < 0.10, acc_no > 0.90
    if at_floor or at_ceiling:
        where = "floor" if at_floor else "ceiling"
        print(f"  [!] Baseline {acc_no:.3f} is at the {where}. Section 2 asks for "
              f"a pool")
        print("      with room in both directions; this one has none, so whatever")
        print("      the gate says below is about the items, not about the skill.")

    # Between "at the ceiling" and "room to move" there is a band the 0.90 test
    # does not catch, and Tier B v2 landed in it: a 0.819 baseline leaves
    # 18.1pp of headroom, so the accuracy arm of the gate can only be cleared
    # if the skill fixes 83% of everything still wrong. The run printed nothing
    # about that, and a gate failure under those conditions says the same thing
    # the floor case says -- it is about the item pool.
    headroom = (1 - acc_no) * 100
    tight = not at_ceiling and not at_floor and headroom < 20
    if tight:
        print(f"  [!] Baseline {acc_no:.3f} leaves only {headroom:.1f}pp of "
              f"headroom, so the")
        print(f"      accuracy arm of the gate (delta >= 15pp) asks the skill to "
              f"fix {min(1.0, 15/headroom):.0%} of")
        print("      everything still wrong. Read a failure on that arm as a fact")
        print("      about the item pool, the same way the floor case is read.")

    # gate, per HANDOFF-whitebox.md section 2
    acc_gate = d_acc >= 15 and acc_lo * 100 > 5
    lp_gate = d_acc >= 5 and lp_lo > 0
    if args.control:
        # A negative control is run to FAIL. Printing the usual "try another
        # pair" advice against it inverts the meaning of the result, which is
        # how the off-domain run of 2026-08-25 came back looking like a failure
        # when it was the control doing its job (HANDOFF 12.3j).
        if acc_gate or lp_gate:
            print("  [!] CONTROL CLEARED THE GATE -- that is the finding, and a")
            print("      bad one. A document that should not apply here moved the")
            print("      dependent variable, so the main effect cannot be read as")
            print("      content-specific. Report this before anything else.")
        else:
            print("  CONTROL BEHAVED AS EXPECTED: no effect where there should be")
            print("  none. This does NOT need a different task/skill pair.")
            print("  What it licenses depends on its own baseline: near a floor or")
            print("  a ceiling the control had little room to move either, so it")
            print("  rules out less than it looks like it does. Say which.")
    elif acc_gate:
        print("  GATE PASSED on accuracy. Proceed.")
    elif lp_gate:
        print("  GATE PASSED on logprob (accuracy delta is modest but the")
        print("  logprob shift is consistent). Use logprob as the DV downstream.")
    else:
        print("  GATE NOT PASSED.")
        if at_floor:
            print("  ...but the baseline is at the floor, so this is not the "
                  "reportable")
            print("  null. Re-select items by difficulty before concluding "
                  "anything about")
            print("  the skill -- section 2, 挑基线正好落在「会一半」区间的题.")
        elif at_ceiling or tight:
            print("  ...but the baseline is at the ceiling end, so this is not "
                  "the reportable")
            print("  null either. Regenerate harder items -- section 2 asks for a "
                  "floor AND a")
            print("  ceiling, and post-hoc filtering is what pushed v1 to the "
                  "floor (section 15).")
        else:
            print("  Try another task/skill pair. After four consecutive pairs "
                  "below")
            print("  10pp, switch to the bottleneck question -- "
                  "HANDOFF-whitebox.md")
            print("  section 6 step 3.")
    if margin_stats:
        LABEL = AXIS_LABEL
        print()
        print("  轴间距 —— gold 与只差一个轴的干扰项之间的 logprob 差")
        print("  （通用的「上下文里有份长文档」位移把两项一起抬高,相减就消掉了）")
        for ax in AXES:
            st = margin_stats.get(ax)
            if not st:
                continue
            lo, hi = st["ci95"]
            mark = "  <-- CI 不含 0" if (lo > 0 or hi < 0) else ""
            print(f"    {LABEL.get(ax, ax):<38} {st['no_skill']:+.3f} -> "
                  f"{st['with_skill']:+.3f}   delta {st['delta']:+.3f}  "
                  f"CI95 [{lo:+.3f}, {hi:+.3f}]   配对 +{st['gained']}/-{st['lost']}"
                  f"{mark}")
        wc = margin_stats.get("wrong_const")
        wr = margin_stats.get("wrong_rel")
        if wc and wr:
            print()
            print("    这份文档动哪个轴更多： "
                  f"常数轴 {wc['delta']:+.3f}   关系式轴 {wr['delta']:+.3f}")
            print("    双重分离要两份文档并排才判得了 —— report.py 会算那个双重差分。")

    print(f"  results: {out_dir}")

    if args.filter_known:
        keep_ids = {x["id"] for x in no if not x["correct"]}
        src = load_tasks(args.tasks)
        kept = [it for it in src if it["id"] in keep_ids]
        with io.open(args.filter_known, "w", encoding="utf-8", newline="\n") as f:
            for it in kept:
                f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"\n  filtered task file: {args.filter_known}")
        print(f"  kept {len(kept)}/{len(src)} (dropped the ones already correct "
              f"with no skill -- they cannot show an effect)")


if __name__ == "__main__":
    main()
