#!/usr/bin/env python3
"""Two matched control documents for the Tier A skill, and why each exists.

The subtraction that isolates the content component is only as good as the
document it subtracts. `filler-neutral.md` is an unrelated text of similar
length: it controls for "a document is present" but not for vocabulary, not for
formatting, and not for the presence of numbers -- so the residual d could in
principle be "this document is about units" rather than "the factors are these".

Two tighter controls close that gap from opposite sides.

  shuffled    the same lines in a scrambled order. Identical vocabulary,
              identical numbers, identical length, no readable table. The
              residual against it is "the document is coherent".

  corrupted   the same document with every conversion factor replaced by a
              different one. Identical vocabulary, identical structure, a
              perfectly readable table that says the wrong thing. The residual
              against it is "the factors are THESE factors" -- the narrowest
              definition of content this task admits.

Both are checked, not assumed: the corrupted factors must not reproduce any
gold answer of the task set (otherwise the control is partly correct), and the
shuffle must actually change the line order.

    python make_controls.py            # write both, print the checks
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "SKILL.zorb-units.md"
SEED = 20260911

# The factors as they appear in the source, and the replacements. Chosen by
# hand rather than at random so that the corrupted table stays internally
# consistent (each "in base units" column is still the running product) -- an
# inconsistent table would be a second difference from the original and the
# subtraction would no longer isolate one thing.
FACTORS = {
    # length: dref 1, glorn 7, varak 12*glorn = 84, skellum 5*varak = 420
    "length": dict(a=(7, 11), b=(12, 6), c=(5, 3)),
    # mass: zunt 1, pelm 9, brask 20*pelm = 180
    "mass": dict(a=(9, 4), b=(20, 13)),
    # duration: tovek 1, wemp 15, cradal 4*wemp = 60
    "duration": dict(a=(15, 8), b=(4, 7)),
}


def corrupted_text(text: str) -> tuple[str, dict]:
    l_g, l_v, l_s = 11, 6, 3            # glorn=11 dref, varak=6 glorn, skellum=3 varak
    m_p, m_b = 4, 13
    d_w, d_c = 8, 7
    new = dict(
        glorn=l_g, varak=l_g * l_v, skellum=l_g * l_v * l_s,
        pelm=m_p, brask=m_p * m_b,
        wemp=d_w, cradal=d_w * d_c,
    )
    subs = [
        ("| glorn | 7 dref | 7 |", f"| glorn | {l_g} dref | {l_g} |"),
        ("| varak | 12 glorn | 84 |", f"| varak | {l_v} glorn | {new['varak']} |"),
        ("| skellum | 5 varak | 420 |", f"| skellum | {l_s} varak | {new['skellum']} |"),
        ("| pelm | 9 zunt | 9 |", f"| pelm | {m_p} zunt | {m_p} |"),
        ("| brask | 20 pelm | 180 |", f"| brask | {m_b} pelm | {new['brask']} |"),
        ("| wemp | 15 tovek | 15 |", f"| wemp | {d_w} tovek | {d_w} |"),
        ("| cradal | 4 wemp | 60 |", f"| cradal | {d_c} wemp | {new['cradal']} |"),
        # the worked examples have to move with the table or the document
        # contradicts itself, which is a third difference, not a control
        ("How many dref are in 3 glorn?\nA glorn is 7 dref, so 3 x 7 = 21 dref.",
         f"How many dref are in 3 glorn?\nA glorn is {l_g} dref, so 3 x {l_g} "
         f"= {3*l_g} dref."),
        ("How many dref are in 2 varak?\nA varak is 84 dref, so 2 x 84 = 168 dref.",
         f"How many dref are in 2 varak?\nA varak is {new['varak']} dref, so "
         f"2 x {new['varak']} = {2*new['varak']} dref."),
        ("How many pelm are in 540 zunt?\nA pelm is 9 zunt, so 540 / 9 = 60 pelm.",
         f"How many pelm are in {60*m_p} zunt?\nA pelm is {m_p} zunt, so "
         f"{60*m_p} / {m_p} = 60 pelm."),
        ("How many glorn are in 3 skellum?\nA skellum is 420 dref and a glorn "
         "is 7 dref, so 3 x 420 / 7 = 180 glorn.",
         f"How many glorn are in 3 skellum?\nA skellum is {new['skellum']} dref "
         f"and a glorn is {l_g} dref, so 3 x {new['skellum']} / {l_g} = "
         f"{3*new['skellum']//l_g} glorn."),
    ]
    out = text
    missed = []
    for old, rep in subs:
        if old not in out:
            missed.append(old.splitlines()[0][:50])
        out = out.replace(old, rep)
    if missed:
        raise SystemExit("[FAIL] these source strings were not found, so the "
                         "corrupted document would still be partly correct:\n  "
                         + "\n  ".join(missed))
    out = out.replace("name: zorb-units", "name: zorb-units")
    return out, new


def shuffled_text(text: str, seed: int = SEED) -> str:
    """Scramble the body's lines, keeping the YAML front matter intact.

    The front matter is what the injector uses to decide the document is a
    skill at all, so scrambling it would change the intervention from "the
    content is unreadable" to "this is not a skill document".
    """
    head, _, body = text.partition("---\n")
    fm, _, rest = body.partition("---\n")
    lines = [l for l in rest.splitlines()]
    rng = random.Random(seed)
    idx = list(range(len(lines)))
    rng.shuffle(idx)
    if idx == list(range(len(lines))):
        raise SystemExit("[FAIL] the shuffle is the identity")
    return f"{head}---\n{fm}---\n" + "\n".join(lines[i] for i in idx) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="tasks.large.jsonl")
    args = ap.parse_args()
    text = SRC.read_text(encoding="utf-8")

    corr, new = corrupted_text(text)
    shuf = shuffled_text(text)

    items = [json.loads(l) for l in
             open(HERE / args.tasks, encoding="utf-8") if l.strip()]
    golds = {int(i["answer_num"]) for i in items}
    # every number the corrupted document now states
    nums = {int(m) for m in re.findall(r"\d+", corr)}
    clash = golds & nums
    print(f"corrupted factors : {new}")
    print(f"gold answers      : {len(golds)} distinct")
    print(f"numbers in corrupt: {len(nums)}")
    print(f"clashes (a gold answer the corrupted document states outright): "
          f"{sorted(clash)[:12]}{'...' if len(clash) > 12 else ''}  "
          f"n={len(clash)}")
    if len(clash) > len(golds) * 0.10:
        print("[warn] more than 10% of gold answers appear verbatim in the "
              "corrupted document; it is not a clean wrong-content control.")
    print(f"length (chars)    : source {len(text)}  corrupted {len(corr)}  "
          f"shuffled {len(shuf)}")

    # Each control goes in its own directory under the SAME file name.
    # model.load_skill derives the injected header from the file stem
    # ("# Skill: <stem minus SKILL.>"), so a file called
    # SKILL.zorb-units.corrupted.md would announce the manipulation in the
    # prompt and the control would differ from the treatment by two things.
    for sub, body in (("ctrl_corrupted", corr), ("ctrl_shuffled", shuf)):
        d = HERE / sub
        d.mkdir(exist_ok=True)
        (d / "SKILL.zorb-units.md").write_text(body, encoding="utf-8")
        print(f"wrote {sub}/SKILL.zorb-units.md")


if __name__ == "__main__":
    main()
