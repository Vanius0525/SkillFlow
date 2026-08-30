#!/usr/bin/env python3
"""
Step 4: error typology. What KIND of error does the skill remove?

Post-processing only -- it reads an existing e0_effect.py run and needs no GPU
and no model. That is the point: the design (HANDOFF-whitebox.md section 6 step
4) puts this before the mechanistic experiments because it costs nothing and it
tells you which hypothesis is worth instrumenting. If 80% of the errors are
formatting, H3 is the story and a layer sweep of activation patching is the wrong
next month.

    python errors.py --per-item results/tierA-dev/per_item.jsonl \
        --tasks tasks/tier_a/tasks.jsonl

The classification is per task family:

Tier A -- reconstructed from the table, not guessed. Every distractor in Tier A
is a value reachable by one specific misreading (tier_a/build.py:distractors), so
a wrong answer says WHICH misreading happened:

    wrong_row      right table, wrong line   -- found the right table and pulled
                                                the wrong number out of it
    wrong_family   read the wrong table      -- picked the wrong procedure
    inverted       divided instead of multiplied
    other          none of the above; no diagnosis

Splitting "picked the wrong table" from "picked the right table and misread it"
is the selection-vs-execution split. Skill2-Bench (HANDOFF section 9.2c) reports
that naming the wrong skill family roughly halves per-step accuracy, i.e. that
selection is separable from execution and causally large; this is the same cut on
a task where the answer itself reveals which one failed.

Tier B -- numeric residuals. A textbook answer that is off by exactly 101.325 or
1000 is not a reasoning error, it is the wrong version of a constant:

    const_version  ratio 101.325 (R in J vs L atm) -- the error pchem-constants
                   exists to fix
    unit_prefix    ratio 1000 (L vs m^3, kJ vs J)
    magnitude      ratio a power of ten
    kelvin         off by 273.15
    sign           sign flipped
    other

Both families also carry `unparsed`: no answer could be extracted at all. That
one is not a reasoning error and must never be pooled with the others -- see
HANDOFF section 12.3b, where a below-chance Tier A baseline turned out to be
mostly this.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent

# Must match tasks/tier_a/build.py:FAMILIES. Duplicated rather than imported
# because build.py lives in a task directory and importing it here would make
# this script depend on which task set is being analysed.
FAMILIES = {
    "length": {"dref": 1, "glorn": 7, "varak": 84, "skellum": 420},
    "mass": {"zunt": 1, "pelm": 9, "brask": 180},
    "duration": {"tovek": 1, "wemp": 15, "cradal": 60},
}

# category -> which hypothesis it points at (HANDOFF-whitebox.md section 1)
POINTS_AT = {
    "correct": "-",
    "unparsed": "H3 format",
    "echo": "H0 no attempt (copied the quantity from the question)",
    "wrong_const": "H1 retrieval (right relation, constant in the wrong units)",
    "wrong_rel": "H2 selection (wrong relation, constant right)",
    "wrong_both": "both axes wrong",
    "wrong_row": "H1 retrieval (found the table, misread the line)",
    "wrong_family": "H2 selection (wrong table entirely)",
    "inverted": "H2 selection (right values, wrong direction)",
    "const_version": "H1 retrieval (wrong version of a constant)",
    "unit_prefix": "H1/H3 (convention, not chemistry)",
    "magnitude": "H1/H3 (convention, not chemistry)",
    "kelvin": "H1 retrieval (missing conversion rule)",
    "sign": "H2 selection (wrong direction)",
    "other": "no diagnosis",
}

ORDER = ["correct", "unparsed", "echo", "wrong_const", "wrong_rel",
         "wrong_both", "wrong_row", "wrong_family", "inverted",
         "const_version", "unit_prefix", "magnitude", "kelvin", "sign", "other"]


def close(a: float, b: float, tol: float = 0.02) -> bool:
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) <= tol


def predicted_value(rec: dict, task: dict, mode: str):
    """The NUMBER the model answered, whichever format the run used."""
    pred = rec.get("pred")
    if pred is None:
        return None
    if mode == "mc":
        letter = str(pred).strip()[:1]
        if letter not in "ABCD":
            return None
        opts = task.get("options")
        if not opts or len(opts) < 4:
            return None
        return float(opts["ABCD".index(letter)])
    try:
        return float(pred)
    except (TypeError, ValueError):
        return None


def classify_tier_a(value, task) -> str:
    """Which misreading of the Zorb table produces this answer."""
    if value is None:
        return "unparsed"
    fam, src, dst, v = task["family"], task["src"], task["dst"], task["value"]
    t = FAMILIES[fam]
    if close(value, v * t[src] / t[dst]):
        return "correct"
    # Answering with the quantity from the question is not a misreading of the
    # table, it is not consulting the table at all. Checked before the loop
    # below because that loop would call it wrong_row: `other` ranges over every
    # unit including dst, and t[dst]/t[dst] is 1. Every echo would then be
    # counted as an H1 retrieval error, and -- since the skill stops the echoing
    # -- as an H1 error the skill repaired. build.py puts `value` itself in the
    # distractor set, so in MC mode this answer is one option away.
    if close(value, v):
        return "echo"
    for other in t:
        if other != src and close(value, v * t[other] / t[dst]):
            return "wrong_row"
    for ofam, ot in FAMILIES.items():
        if ofam != fam and close(value, v * list(ot.values())[1]):
            return "wrong_family"
    if close(value, v * t[dst] / t[src]):
        return "inverted"
    return "other"


def classify_tier_b2(rec: dict, task: dict) -> str:
    """
    Tier B v2 needs no inference: build.py records what each option means, so
    the letter the model picked names the failure directly.

    The 2x2 is the point. `wrong_const` is a units error with the relation
    already right, which only SKILL.pchem-constants can repair; `wrong_rel` is
    the reverse, and only SKILL.pchem-procedure can repair it. A skill that
    moves both columns is not doing what its own front matter claims, and the
    example/principle contrast E2 is built on does not survive it.
    """
    pred = rec.get("pred")
    if pred is None:
        return "unparsed"
    letter = str(pred).strip()[:1]
    kinds = task.get("option_kinds") or {}
    return kinds.get(letter, "unparsed")


def classify_numeric(value, gold: float) -> str:
    """Residual typology for free numeric answers."""
    if value is None:
        return "unparsed"
    if close(value, gold):
        return "correct"
    if gold != 0 and close(value, -gold):
        return "sign"
    if abs(abs(value - gold) - 273.15) < 273.15 * 0.02:
        return "kelvin"
    if gold != 0 and value != 0:
        ratio = abs(value / gold)
        for r, name in ((101.325, "const_version"), (1000.0, "unit_prefix")):
            if close(ratio, r) or close(ratio, 1.0 / r):
                return name
        for n in range(-12, 13):
            if n and close(ratio, 10.0 ** n):
                return "magnitude"
    return "other"


def table(counts: Counter, n: int) -> list[str]:
    rows = []
    for k in ORDER:
        if counts.get(k):
            rows.append(f"    {k:<14} {counts[k]:>4}  {counts[k]/n:>6.1%}   "
                        f"{POINTS_AT[k]}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-item", required=True,
                    help="per_item.jsonl written by e0_effect.py")
    ap.add_argument("--label", default="",
                    help="which skill this run used, e.g. pchem-constants. "
                         "Recorded in the output so the Tier B v2 dissociation "
                         "can be checked across two runs.")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], default=None,
                    help="default: inferred from the gold answers")
    ap.add_argument("--out", default=None, help="write the report as json")
    args = ap.parse_args()

    tasks = {}
    for line in io.open(args.tasks, encoding="utf-8"):
        if line.strip():
            it = json.loads(line)
            tasks[it["id"]] = it
    recs = [json.loads(l) for l in io.open(args.per_item, encoding="utf-8")
            if l.strip()]
    if not recs:
        print("[FAIL] no records"); raise SystemExit(1)

    mode = args.mode
    if mode is None:
        golds = {str(r.get("gold", "")) for r in recs}
        mode = "mc" if golds <= {"A", "B", "C", "D"} else "num"
    tier_a = all("family" in tasks.get(r["id"], {}) for r in recs)
    # Tier B v2 is recognised by the field that carries its 2x2 -- the same way
    # tier_a is recognised by "family". Detecting on the data rather than on a
    # flag keeps errors.py runnable against any per_item.jsonl without the
    # caller having to remember which set produced it.
    labelled = all("option_kinds" in tasks.get(r["id"], {}) for r in recs)
    # `option_kinds` used to exist only on Tier B v2, so its presence WAS the
    # 2x2. 12.3m gave Tier A the same field, and this flag then did two things
    # nobody asked for: it read Tier A through the units/relation contrast --
    # printing "0% units errors, 0% relation errors" instead of the H1/H2 split
    # the tier was built for -- and it pulled Tier A into report.py's
    # dissociation cross-check as a row of zeros. What makes a set the 2x2 is
    # which kinds the options carry, not that they are labelled at all.
    kinds_seen = set()
    for r in recs:
        kinds_seen |= set((tasks.get(r["id"]) or {}).get("option_kinds", {}).values())
    tier_b2 = labelled and bool(kinds_seen & {"wrong_const", "wrong_rel"})

    if "pred" not in recs[0].get("no_skill", {}):
        print("[FAIL] this per_item.jsonl predates the `pred` field. Re-run")
        print("       e0_effect.py -- the raw text alone cannot be classified")
        print("       without re-implementing the extractor here, and two")
        print("       extractors that disagree is worse than no typology.")
        raise SystemExit(1)

    print(f"per-item : {args.per_item}  ({len(recs)} items)")
    which = ("Tier B v2 2x2" if tier_b2 else
             "labelled options" if labelled else
             "Tier A structural" if tier_a else "numeric residual")
    print(f"tasks    : {args.tasks}  (mode={mode}, {which} typology)\n")

    cats = {"no_skill": [], "with_skill": []}
    for r in recs:
        task = tasks.get(r["id"])
        if task is None:
            continue
        for cond in ("no_skill", "with_skill"):
            if labelled:
                # Reading the kind straight off the option the model picked
                # beats reconstructing it from the value, so this path is right
                # for Tier A too -- it is only the *reading* below that is
                # specific to the 2x2.
                c = classify_tier_b2(r[cond], task)
            elif tier_a:
                c = classify_tier_a(predicted_value(r[cond], task, mode), task)
            else:
                c = classify_numeric(predicted_value(r[cond], task, mode),
                                     float(r["gold"]))
            cats[cond].append((r["id"], c))

    n = len(cats["no_skill"])
    cn, cy = Counter(c for _, c in cats["no_skill"]), Counter(c for _, c in cats["with_skill"])

    print("  without skill")
    print("\n".join(table(cn, n)))
    print("\n  with skill")
    print("\n".join(table(cy, n)))

    # Where the gains came from. The paired design makes this exact rather than
    # a difference of two distributions: each item is followed from the category
    # it was in without the skill to the one it is in with it.
    moves = Counter()
    for (i, a), (_, b) in zip(cats["no_skill"], cats["with_skill"]):
        if a != b:
            moves[(a, b)] += 1
    gained = [(a, k) for (a, b), k in moves.items() if b == "correct"]
    lost = [(b, k) for (a, b), k in moves.items() if a == "correct"]

    print(f"\n  became correct: {sum(k for _, k in gained)} items")
    for a, k in sorted(gained, key=lambda x: -x[1]):
        print(f"    from {a:<14} {k:>4}   {POINTS_AT[a]}")
    if lost:
        print(f"  became wrong: {sum(k for _, k in lost)} items")
        for b, k in sorted(lost, key=lambda x: -x[1]):
            print(f"    into {b:<14} {k:>4}")

    # ---- engagement vs mechanism -------------------------------------------
    #
    # `echo` means the model answered with a number lifted straight out of the
    # question: it was not consulting the document badly, it was not consulting
    # it at all. Items like that are upstream of every hypothesis the layer
    # sweeps separate -- H1 vs H2 asks HOW the model reads the table, and these
    # items never got that far. On the first Tier A run 37 of 47 items were
    # echoes without the skill, and 16 of the 19 the skill fixed came from that
    # pool (HANDOFF 12.3j), so the headline effect was mostly the model starting
    # to attempt the task. Reporting the two strata together lets an engagement
    # effect be read as a mechanism one, so split them here.
    attempted = [(i, a) for (i, a) in cats["no_skill"] if a != "echo"]
    echoed = [(i, a) for (i, a) in cats["no_skill"] if a == "echo"]
    strata = None
    if echoed and attempted:
        with_by_id = dict(cats["with_skill"])
        def acc(pool, cond):
            src = with_by_id if cond == "with" else dict(cats["no_skill"])
            hit = sum(1 for (i, _) in pool if src.get(i) == "correct")
            return hit, len(pool)
        a_no, a_n = acc(attempted, "no")
        a_ys, _ = acc(attempted, "with")
        e_no, e_n = acc(echoed, "no")
        e_ys, _ = acc(echoed, "with")
        strata = {
            "attempted": {"n": a_n, "acc_no": a_no / a_n, "acc_with": a_ys / a_n},
            "echoed": {"n": e_n, "acc_no": e_no / e_n, "acc_with": e_ys / e_n},
        }
        print("\n  split by whether the model even attempted the task "
              "(without the skill)")
        print(f"    attempted (not echo)  n={a_n:<4} "
              f"{a_no/a_n:.1%} -> {a_ys/a_n:.1%}   "
              f"({(a_ys-a_no)/a_n*100:+.1f}pp)")
        print(f"    echoed the question   n={e_n:<4} "
              f"{e_no/e_n:.1%} -> {e_ys/e_n:.1%}   "
              f"({(e_ys-e_no)/e_n*100:+.1f}pp)")
        share = e_n / (e_n + a_n)
        if share > 0.5:
            print(f"    [!] {share:.0%} of the pool was echo without the skill, so the")
            print("        headline effect is mostly ENGAGEMENT (the model starting to")
            print("        answer at all), not retrieval or selection. Mechanism")
            print("        claims belong to the `attempted` row -- quote that one,")
            print("        and say the pool it came from. See HANDOFF 12.3j.")

    print("\n  reading it:")
    fixed = sum(k for _, k in gained) or 1
    if tier_b2:
        # The 2x2 makes this a within-item contrast rather than a rate: the
        # same item offers a units error and a relation error side by side,
        # so "which column did this document move" is answerable directly.
        wc = sum(k for a, k in gained if a == "wrong_const")
        wr = sum(k for a, k in gained if a == "wrong_rel")
        wb = sum(k for a, k in gained if a == "wrong_both")
        print(f"    of the items this skill fixed: {wc/fixed:.0%} were units "
              f"errors (wrong_const),")
        print(f"    {wr/fixed:.0%} were relation errors (wrong_rel), "
              f"{wb/fixed:.0%} were both")
        if wc and wr and min(wc, wr) > 0.3 * (wc + wr):
            print("    This document moved BOTH axes about equally. It is not")
            print("    behaving as values-only or methods-only, whichever it")
            print("    claims to be -- and the example/principle contrast that")
            print("    E2 preregisters does not survive that. Check the other")
            print("    skill before concluding: if both move both axes, the")
            print("    effect is 'a document is present', not its content.")
        elif wc > wr:
            print("    Mostly the units axis -> this behaves like a values")
            print("    document (expected for pchem-constants).")
        elif wr > wc:
            print("    Mostly the relation axis -> this behaves like a methods")
            print("    document (expected for pchem-procedure).")
        if cn.get("unparsed", 0) > 0.2 * n:
            frac = cn['unparsed'] / n
            print(f"    {frac:.0%} of no-skill answers carry no letter at all.")
    else:
        fmt = sum(k for a, k in gained if a == "unparsed")
        ech = sum(k for a, k in gained if a == "echo")
        sel = sum(k for a, k in gained if a in ("wrong_family", "inverted", "sign"))
        ret = sum(k for a, k in gained
                  if a in ("wrong_row", "const_version", "kelvin"))
        print(f"    of the items the skill fixed: {fmt/fixed:.0%} were unparsed "
              f"(H3), {ech/fixed:.0%} were echoes of the question (H0),\n    "
              f"{sel/fixed:.0%} were selection errors (H2), {ret/fixed:.0%} were "
              f"retrieval errors (H1)")
        if fmt / fixed > 0.5:
            print("    Most of the effect is the skill making the output parseable.")
            print("    That is H3, and it is not what the layer sweeps are set up to")
            print("    explain. Fix the answer instruction or the extractor first.")
        elif ech / fixed > 0.5:
            print("    Most of the items the skill fixed were ones where the model")
            print("    had answered with the number from the question. The skill is")
            print("    getting it to attempt the task at all, and that is upstream")
            print("    of every hypothesis the layer sweeps separate: H1 vs H2 asks")
            print("    HOW the model consults the table, and these items were not")
            print("    consulting it. Report the effect on the items that did")
            print("    attempt it separately, or the mechanism claim inherits an")
            print("    engagement effect.")
        elif cn.get("unparsed", 0) > 0.2 * n:
            print(f"    {cn['unparsed']/n:.0%} of no-skill outputs carry no answer at "
                  f"all. The accuracy delta\n    is inflated by that much before any "
                  f"mechanism is involved.")

    if args.out:
        pathlib.Path(args.out).write_text(json.dumps({
            "n": n, "mode": mode, "tier_a": tier_a, "tier_b2": tier_b2,
            # Whether the options carried kinds at all, as opposed to carrying
            # the two kinds that make a 2x2. report.py keys its dissociation
            # cross-check on tier_b2 and must not see Tier A there.
            "labelled": labelled,
            # Which document produced this file. The Tier B v2 dissociation is a
            # comparison BETWEEN two of these, and a run directory holds both,
            # so report.py needs to be able to tell them apart.
            "label": args.label,
            "no_skill": dict(cn), "with_skill": dict(cy),
            "moves": {f"{a}->{b}": k for (a, b), k in moves.items()},
            # Engagement vs mechanism (HANDOFF 12.3j). None when the pool has no
            # echo items, or no non-echo ones, and the split is not defined.
            "strata": strata,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  written: {args.out}")


if __name__ == "__main__":
    main()
