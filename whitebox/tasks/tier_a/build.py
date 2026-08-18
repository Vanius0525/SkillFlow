#!/usr/bin/env python3
"""
Generate the Tier A task set: conversions in the fictional Zorb unit system.

Tier A is the positive control, not a research result. Its job is to be a task
where the skill is provably necessary, so that a null from the intervention code
can be told apart from a null hypothesis. If activation patching cannot detect an
effect here, the patching code is broken.

Design choices and why:

- The units are invented, so the no-skill baseline is chance by construction and
  contamination is impossible. Nothing else in the design gives both.
- Multiple choice with single-letter answers, because the dependent variable is
  the logprob of the answer token and a single token makes that unambiguous. It
  also removes arithmetic from the measurement: the model looks up a factor and
  picks, rather than having to compute cleanly.
- A free-numeric variant is emitted alongside, for when the full
  lookup-then-compute chain is what you want to measure.
- Distractors are values reachable by MISREADING the table -- the neighbouring
  row, the wrong family, the inverted direction -- never random numbers. A model
  that read the table and grabbed the wrong row lands on a specific distractor,
  which makes the error diagnostic rather than just wrong.
- Answer letters are balanced across A/B/C/D so a position-biased model still
  scores near chance without the skill.

Output is frozen to tasks.jsonl with a hash printed; regenerating with the same
seed reproduces it byte for byte.

    python build.py            # write tasks.jsonl
    python build.py --check    # verify the committed file matches this generator
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import random
import re

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "tasks.jsonl"
SEED = 20260819

# Family -> {unit: value in that family's base unit}. Must match SKILL.zorb-units.md.
FAMILIES = {
    "length": {"dref": 1, "glorn": 7, "varak": 84, "skellum": 420},
    "mass": {"zunt": 1, "pelm": 9, "brask": 180},
    "duration": {"tovek": 1, "wemp": 15, "cradal": 60},
}


def convert(value: int, src: str, dst: str, fam: str) -> float:
    t = FAMILIES[fam]
    return value * t[src] / t[dst]


def is_clean(x: float) -> bool:
    """Keep only conversions with an exact integer answer.

    A non-integer answer would make the free-numeric variant depend on rounding
    convention, and the scorer would then be measuring formatting rather than
    the conversion.
    """
    return abs(x - round(x)) < 1e-9 and round(x) > 0


def distractors(value: int, src: str, dst: str, fam: str, correct: float, rng):
    """Wrong answers a model reaches by misreading the table, not random noise."""
    t = FAMILIES[fam]
    cands = []

    # neighbouring row in the same family: right table, wrong line
    for other in t:
        if other != src:
            v = value * t[other] / t[dst]
            if is_clean(v):
                cands.append(round(v))

    # wrong family: read the factor off the wrong table
    for ofam, ot in FAMILIES.items():
        if ofam == fam:
            continue
        base = list(ot.values())[1]
        v = value * base
        if is_clean(v):
            cands.append(round(v))

    # inverted direction: divided where it should have multiplied
    inv = value * t[dst] / t[src]
    if is_clean(inv):
        cands.append(round(inv))

    seen, out = {round(correct)}, []
    rng.shuffle(cands)
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def skill_numbers() -> set:
    """Every standalone number appearing in the skill document.

    The worked-examples block states results like "3 x 7 = 21 dref". A task whose
    answer is one of those can be solved by copying the example instead of
    reading the table, which is contamination: it would register as H1 retrieval
    regardless of what the model actually does. Reading the skill here, rather
    than keeping a hand-written exclusion list, means the two files stay
    consistent when either changes.

    The pattern is a character class with no backslash on purpose. An earlier
    edit of this file turned the escape in a backslash class into a literal
    control byte; the pattern then matched nothing, the set came back empty,
    every item silently passed the filter, and both sed and inspect.getsource
    rendered the byte invisibly, so the source looked correct while the check
    did nothing.
    """
    txt = (HERE / "SKILL.zorb-units.md").read_text(encoding="utf-8")
    return {int(m) for m in re.findall("[0-9]+", txt)}


def build():
    rng = random.Random(SEED)
    banned = skill_numbers()
    items = []
    skipped = 0
    pairs = []
    for fam, table in FAMILIES.items():
        units = list(table)
        for src in units:
            for dst in units:
                if src != dst:
                    pairs.append((fam, src, dst))

    idx = 0
    for fam, src, dst in pairs:
        for value in (2, 3, 4, 5, 6):
            correct = convert(value, src, dst, fam)
            if not is_clean(correct):
                continue
            if round(correct) in banned:
                skipped += 1
                continue
            ds = distractors(value, src, dst, fam, correct, rng)
            if len(ds) < 3:
                continue
            ds = ds[:3]

            question = (f"A Kelmar document lists a quantity of {value} {src}. "
                        f"How many {dst} is that?")
            options = ds + [round(correct)]
            rng.shuffle(options)
            # balance the key: rotate the correct option into a target slot
            target_slot = idx % 4
            cur = options.index(round(correct))
            options[cur], options[target_slot] = options[target_slot], options[cur]
            letter = "ABCD"[target_slot]

            items.append({
                "id": f"tierA-{idx:04d}",
                "family": fam,
                "src": src,
                "dst": dst,
                "value": value,
                "hops": abs(list(FAMILIES[fam]).index(src)
                            - list(FAMILIES[fam]).index(dst)),
                "question_mc": question + "\n" + "\n".join(
                    f"{L}. {o}" for L, o in zip("ABCD", options)),
                "answer_mc": letter,
                "question_num": question + " Answer with the number only.",
                "answer_num": str(round(correct)),
                "options": options,
            })
            idx += 1

    if skipped:
        print(f"(skipped {skipped} items whose answer also appears in the skill "
              f"document -- they could be solved by copying a worked example)")
    return items


def digest(items) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify tasks.jsonl matches what this generator produces")
    args = ap.parse_args()

    items = build()
    d = digest(items)

    if args.check:
        if not OUT.exists():
            print("[FAIL] tasks.jsonl missing -- run without --check first")
            raise SystemExit(1)
        have = [json.loads(l) for l in io.open(OUT, encoding="utf-8") if l.strip()]
        if digest(have) != d:
            print(f"[FAIL] tasks.jsonl does not match the generator "
                  f"(file {digest(have)} vs generator {d})")
            raise SystemExit(1)
        print(f"[ OK ] tasks.jsonl matches the generator, {len(have)} items, sha {d}")
        return

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")

    keys = [it["answer_mc"] for it in items]
    print(f"wrote {OUT} -- {len(items)} items, sha {d}")
    print("answer-key balance:", {L: keys.count(L) for L in "ABCD"})
    print("hop distribution :", {h: sum(1 for i in items if i['hops'] == h)
                                 for h in sorted({i['hops'] for i in items})})
    print("families         :", {f: sum(1 for i in items if i['family'] == f)
                                 for f in FAMILIES})


if __name__ == "__main__":
    main()
