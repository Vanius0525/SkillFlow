#!/usr/bin/env python3
"""Tier C: separate the RANK of the mapping from the LENGTH of the answer.

    python whitebox/tasks/tier_c/build.py

WHY THIS TASK EXISTS

Two limits on what an injected vector can carry are usually conflated.

  Dong et al. (arXiv:2506.09048) prove that injecting a single task vector is
  functionally a rank-one map, so a task whose input->output relation is
  high-rank -- a bijection, for instance -- cannot be encoded by one vector.

  We find that a patch at one position cannot carry an answer that occupies
  many tokens, whatever the mapping is.

The ladder in the main text (multiple choice -> free-form -> chain of thought)
cannot separate them: it changes the answer length, the difficulty and the
mapping all at once. This task varies the two axes independently.

TWO FAMILIES, ONE DOCUMENT EACH, FIVE ANSWER LENGTHS

  copy    the document says: write the given word N times.
          The mapping is the IDENTITY on the word -- as low-rank as a mapping
          can be, and the same for every item. Dong's limit does not bind.
          N is fixed by the document, so the answer is exactly N words.

  cipher  the document gives a ten-entry digit->word cipher.
          The mapping is a BIJECTION on ten symbols, which is exactly the case
          Dong's Proposition 4 rules out for a rank-one map. Answer length is
          the number of digits asked for.

Crossing family with length gives a 2 x 5 grid. The prediction the paper makes
is that a single-position patch falls off with N in BOTH families, including
the copy family where the mapping is trivial; if it holds up in copy and only
fails in cipher, the length account is wrong and what we measured was rank.

Both vocabularies are invented, so the no-document floor is zero by
construction, and every document states its own N, so no item can be solved by
guessing the format.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))

WORDS = ["zom", "vix", "quen", "brel", "sen", "targ", "nuk", "plov",
         "wisk", "dref", "flen", "murk", "glaive", "torv", "pesk", "yarn"]
CIPHER = {d: w for d, w in enumerate(WORDS[:10])}
LENGTHS = (1, 2, 4, 8, 16)


def copy_skill(n: int) -> str:
    return f"""# Skill: Renslow repetition

A word is written in Renslow repetition by writing it exactly {n} time{'s' if n > 1 else ''},
separated by single spaces, and nothing else.

Do not write anything but the repeated word. Do not add punctuation.

### Example

The word `torv` in Renslow repetition is:
{' '.join(['torv'] * n)}
"""


CIPHER_SKILL = """# Skill: Renslow digit notation

Renslow notation writes a number by replacing each of its digits, left to
right, with that digit's Renslow word. The words are:

| digit | word |
|---|---|
""" + "\n".join(f"| {d} | {w} |" for d, w in CIPHER.items()) + """

Write the words in the same order as the digits, separated by single spaces,
and nothing else. Do not write the digits themselves.

### Example

The number 30 is written: brel zom
"""


def build(per_length=40, seed=0):
    rng = random.Random(seed)
    items = []
    # copy: the mapping is the identity; N comes from the document
    pool = [w for w in WORDS if w != "torv"]          # the example word is out
    for n in LENGTHS:
        for i in range(per_length):
            w = pool[(i * 7 + n) % len(pool)]         # deterministic, spread
            items.append({
                "id": f"tierC-copy-N{n:02d}-{i:03d}",
                "family": "copy", "answer_len": n, "skill": f"copy{n}",
                "question": f"Write `{w}` in Renslow repetition.",
                "answer": " ".join([w] * n),
            })
    # cipher: the mapping is a bijection on ten symbols
    for L in LENGTHS:
        want, seen, k = min(per_length, 10 ** L), set(), 0
        while k < want:
            digits = [rng.randrange(10) for _ in range(L)]
            if tuple(digits) in seen:
                continue
            seen.add(tuple(digits))
            k += 1
            items.append({
                "id": f"tierC-cipher-L{L:02d}-{k:03d}",
                "family": "cipher", "answer_len": L, "skill": "cipher",
                "question": "Write %s in Renslow notation."
                            % "".join(str(d) for d in digits),
                "answer": " ".join(CIPHER[d] for d in digits),
            })
    return items


def main():
    items = build()
    with open(os.path.join(HERE, "tasks.jsonl"), "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    for n in LENGTHS:
        with open(os.path.join(HERE, f"SKILL.copy{n}.md"), "w",
                  encoding="utf-8") as fh:
            fh.write(copy_skill(n))
    with open(os.path.join(HERE, "SKILL.cipher.md"), "w",
              encoding="utf-8") as fh:
        fh.write(CIPHER_SKILL)
    by = {}
    for it in items:
        by[(it["family"], it["answer_len"])] = \
            by.get((it["family"], it["answer_len"]), 0) + 1
    print(f"{len(items)} items -> {os.path.join(HERE, 'tasks.jsonl')}")
    for k in sorted(by):
        print(f"  {k[0]:7s} answer_len={k[1]:2d}  n={by[k]}")
    for f in ("copy", "cipher"):
        ex = next(x for x in items if x["family"] == f and x["answer_len"] == 4)
        print(f"  {f:7s} example: {ex['question']}  ->  {ex['answer']}")


if __name__ == "__main__":
    main()
