#!/usr/bin/env python3
"""
E6: counterfactual skill. Is the model actually reading the table?

Change one factor in the skill, leave the question alone, and see which value the
answer follows:

    follows the counterfactual   the model read that row -> H1, and specifically
                                 a per-item, per-row read
    follows the true value       the model is not reading the table; the benefit
                                 came from somewhere else
    neither                      the conflict disorganised the computation -> H5

Why this experiment earns its place next to E1 and E2: it uses no hooks. E1 and
E2 both depend on machinery that can fail silently -- HANDOFF-whitebox.md 12.3d
is one such failure that would have produced a publishable-looking null -- and
they can only be checked against each other, which does not help when both are
instrument-limited. E6 is an ordinary forward pass. It can therefore FALSIFY the
other two: if E6 shows the model tracking the table row by row while E1 reports no
layer depending on the skill span, E1 is broken, not the hypothesis.

It also produces a per-item label (did THIS item follow the text?), so the layer
curves can be correlated against it rather than compared as averages.

    python e6_counterfactual.py --model ../models/Qwen3-1.7B --run-id e6-tierA
    python e6_counterfactual.py --model ../models/Qwen3-1.7B --flavour near

The counterfactual document is generated, not edited: tasks/tier_a/render_skill.py
rebuilds the whole skill from the conversion tables, so the worked examples stay
consistent with the perturbed factor. Editing by hand would leave the examples
contradicting the table, and a model reading a self-contradictory document is a
different experiment. render_skill.py --check runs first and refuses to continue
unless rendering the UNPERTURBED tables reproduces the committed skill byte for
byte -- that is what makes "the only difference is the perturbation" a fact
rather than an intention.

Two flavours of perturbation, from SWE-Skills-Bench's Finding 4 (HANDOFF 9.2b),
where the skills that actively HURT were the ones whose templates nearly matched
the task:

    far    the replacement factor is as far from the original as the table allows
    near   the smallest coherent change

If `near` anchors the model more strongly than `far`, that reproduces their
context-interference mechanism in a setting where the ground truth is known.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
TIER_A = HERE / "tasks" / "tier_a"
sys.path.insert(0, str(TIER_A))
import render_skill as RS                                    # noqa: E402


def coherent_values(fam: str, unit: str) -> list[int]:
    """
    Replacement factors that keep the document coherent.

    The skill states that each unit is "an exact whole multiple of the unit one
    step below", and the Equals column is derived from that. A replacement has to
    keep both neighbours whole multiples, or the rendered table contradicts its
    own prose -- which would confound the perturbation with document quality.
    """
    t = RS.FAMILIES[fam]
    names = list(t)
    i = names.index(unit)
    prev = t[names[i - 1]]
    nxt = t[names[i + 1]] if i + 1 < len(names) else None
    out = []
    v = prev * 2
    while v < (nxt if nxt else prev * 64):
        if v != t[unit] and v % prev == 0 and (nxt is None or nxt % v == 0):
            out.append(v)
        v += prev
    return out


def pick(fam: str, unit: str, flavour: str) -> int | None:
    cands = coherent_values(fam, unit)
    if not cands:
        return None
    cur = RS.FAMILIES[fam][unit]
    key = (lambda v: -abs(v - cur)) if flavour == "far" else (lambda v: abs(v - cur))
    return sorted(cands, key=key)[0]


def numbers_in(text: str) -> set:
    return {int(m) for m in re.findall("[0-9]+", text)}


def clean(x: float) -> bool:
    return abs(x - round(x)) < 1e-9 and round(x) > 0


def prepare(items, flavour, true_banned):
    """
    Build the per-item counterfactual. Separated from main() so it can run --
    and be tested -- without torch or a GPU.

    The perturbed unit is chosen per item: the source unit when it has a coherent
    replacement, otherwise the target. Perturbing a base unit would rescale its
    whole family, which changes every row rather than one.
    """
    prepared = []
    skipped = {"no_unit": 0, "not_clean": 0, "contaminated": 0, "same_answer": 0}
    for it in items:
        fam, src, dst, val = it["family"], it["src"], it["dst"], it["value"]
        names = list(RS.FAMILIES[fam])
        unit = None
        for cand in (src, dst):
            if names.index(cand) > 0 and coherent_values(fam, cand):
                unit = cand
                break
        if unit is None:
            skipped["no_unit"] += 1
            continue
        new_val = pick(fam, unit, flavour)
        fams = RS.perturb(unit, new_val)
        t2 = fams[fam]
        gold_true = val * RS.FAMILIES[fam][src] / RS.FAMILIES[fam][dst]
        gold_cf = val * t2[src] / t2[dst]
        if not (clean(gold_true) and clean(gold_cf)):
            skipped["not_clean"] += 1
            continue
        # The two values have to be separated by more than the scorer's own
        # tolerance, several times over. num_correct accepts 2% error, so two
        # golds 1% apart would both match the same answer and "which one did it
        # follow" would have no answer -- silently, as a stable-looking number.
        if abs(gold_cf - gold_true) <= 0.10 * max(abs(gold_true), 1.0):
            skipped["same_answer"] += 1
            continue
        cf_body = RS.render(fams)
        # Same contamination rule as the generator: an answer printed in the
        # document can be copied instead of derived, and copying looks like
        # reading the table when it is not.
        if round(gold_cf) in numbers_in(cf_body) or round(gold_true) in true_banned:
            skipped["contaminated"] += 1
            continue
        prepared.append({
            "id": it["id"], "question": it["question_num"],
            "unit": unit, "orig_factor": RS.FAMILIES[fam][unit], "new_factor": new_val,
            "gold_true": str(round(gold_true)), "gold_cf": str(round(gold_cf)),
            "cf_body": cf_body,
            "cf_skill": "\n# Skill: zorb-units\n\n" + cf_body,
        })
    return prepared, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", default=str(TIER_A / "tasks.jsonl"))
    ap.add_argument("--flavour", choices=["far", "near"], default="far")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-new-tokens", type=int, default=24)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="prepare the items and show one counterfactual, then stop; "
                         "needs no GPU and no model")
    args = ap.parse_args()

    # Refuse to run on an edited skill: without this, "the documents differ only
    # in the factor" is an assumption instead of a checked fact.
    chk = subprocess.run([sys.executable, str(TIER_A / "render_skill.py"), "--check"],
                         capture_output=True, text=True)
    print(chk.stdout.strip() or chk.stderr.strip())
    if chk.returncode != 0:
        raise SystemExit(1)

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id

    items = [json.loads(l) for l in io.open(args.tasks, encoding="utf-8") if l.strip()]
    if args.limit:
        items = items[:args.limit]

    true_body = RS.render(RS.FAMILIES)
    true_skill = f"\n# Skill: zorb-units\n\n{true_body}"
    true_banned = numbers_in(true_body)

    # ---- build the counterfactual for each item ---------------------------
    #
    # The perturbed unit is chosen per item: the source unit when it has a
    # coherent replacement, otherwise the target. Perturbing a base unit would
    # rescale its whole family, which changes every row rather than one.
    prepared, skipped = prepare(items, args.flavour, true_banned)

    print(f"model   : {args.model}")
    print(f"tasks   : {args.tasks}")
    print(f"flavour : {args.flavour}")
    print(f"usable  : {len(prepared)}/{len(items)}  "
          f"(skipped {dict((k, v) for k, v in skipped.items() if v)})")
    print(f"run id  : {run_id}\n")
    if not prepared:
        print("[FAIL] no usable items"); raise SystemExit(1)

    if args.dry_run:
        p0 = prepared[0]
        print(f"  sample: {p0['id']}  {p0['unit']} {p0['orig_factor']} -> "
              f"{p0['new_factor']}   answer {p0['gold_true']} -> {p0['gold_cf']}")
        import difflib
        diff = list(difflib.unified_diff(
            true_body.splitlines(), p0["cf_body"].splitlines(),
            "true", "counterfactual", lineterm="", n=0))
        changed = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        print(f"  the two documents differ in {changed} lines:")
        for line in diff[:24]:
            print("   ", line)
        return

    import model as M
    out_dir.mkdir(parents=True, exist_ok=True)
    r = M.load(args.model, device=args.device)
    M.write_run_info(out_dir, r, {
        "experiment": "e6_counterfactual", "run_id": run_id,
        "tasks": str(args.tasks), "flavour": args.flavour,
        "n_items": len(prepared), "decoding": "greedy",
    })

    rows, t0 = [], time.time()
    for i, p in enumerate(prepared):
        row = {k: p[k] for k in ("id", "unit", "orig_factor", "new_factor",
                                 "gold_true", "gold_cf")}
        for cond, skill in (("no_skill", None), ("true", true_skill),
                            ("cf", p["cf_skill"])):
            ids = M.encode(r, M.render(r, M.build_messages(p["question"], skill, "num")))
            text = M.generate(r, ids, max_new_tokens=args.max_new_tokens)
            pred = M.extract_num(text)
            row[cond] = {
                "pred": pred, "raw": text.strip()[:120],
                "follows": ("true" if pred is not None
                            and M.num_correct(pred, float(p["gold_true"]))
                            else "cf" if pred is not None
                            and M.num_correct(pred, float(p["gold_cf"]))
                            else "unparsed" if pred is None else "neither"),
                # Continuous companion to the generated answer: which of the two
                # values the model would rather emit, even when it emits neither.
                "lp_true": M.answer_logprob(r, ids, p["gold_true"]),
                "lp_cf": M.answer_logprob(r, ids, p["gold_cf"]),
            }
        rows.append(row)
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(prepared)}  {el:.0f}s ({el/(i+1):.1f}s/item)",
                  flush=True)

    with io.open(out_dir / "per_item.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n = len(rows)

    def share(cond, what):
        return sum(1 for x in rows if x[cond]["follows"] == what) / n

    def lp_gap(cond):
        return sum(x[cond]["lp_cf"] - x[cond]["lp_true"] for x in rows) / n

    print(f"\n{'='*64}")
    print(f"  n = {n}   perturbation: {args.flavour}")
    print(f"  {'condition':<10} {'-> true':>8} {'-> cf':>8} {'neither':>9} "
          f"{'unparsed':>9}   mean lp(cf) - lp(true)")
    for cond in ("no_skill", "true", "cf"):
        print(f"  {cond:<10} {share(cond,'true'):>7.1%} {share(cond,'cf'):>8.1%} "
              f"{share(cond,'neither'):>8.1%} {share(cond,'unparsed'):>9.1%}"
              f"        {lp_gap(cond):+.3f}")

    followed = share("cf", "cf")
    kept = share("cf", "true")
    decided = followed + kept
    summary = {
        "experiment": "e6_counterfactual",
        "run_id": run_id, "n": n, "flavour": args.flavour,
        "follow_rate": followed / decided if decided else float("nan"),
        "shares": {c: {w: share(c, w) for w in ("true", "cf", "neither", "unparsed")}
                   for c in ("no_skill", "true", "cf")},
        "lp_gap": {c: lp_gap(c) for c in ("no_skill", "true", "cf")},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n  reading it:")
    if decided < 0.2:
        print("    Under the counterfactual the model mostly answers neither value.")
        print("    The conflict is disorganising the computation rather than being")
        print("    resolved one way or the other -- that is H5, and the follow rate")
        print("    below is computed on too few decided items to mean much.")
    fr = summary["follow_rate"]
    print(f"    follow rate (of the items that chose one of the two): {fr:.1%}")
    if fr > 0.8:
        print("    The model tracks the table row by row -> H1 for this skill.")
        print("    E1 must then find layers that depend on the skill span; if it")
        print("    reports none, E1 is the thing that is wrong.")
    elif fr < 0.2:
        print("    The model ignores the perturbed factor and keeps answering with")
        print("    the true one. It is not reading this row -- the benefit measured")
        print("    in e0 comes from somewhere else. Check contamination first: an")
        print("    answer the model already knows makes this outcome trivial.")
    else:
        print("    Mixed. Report the split rather than a verdict, and use the")
        print("    per-item labels in per_item.jsonl to split the E1/E2 curves by")
        print("    whether that item followed the text.")
    print(f"\n  results: {out_dir}")
    print("=" * 64)


if __name__ == "__main__":
    main()
