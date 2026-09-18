#!/usr/bin/env python3
"""Tier A, larger n. Same generator, wider value range, separate output file.

`build.py` is frozen: `tasks.jsonl` (n=39) is what every run before 2026-09-10
used, and regenerating it would silently invalidate those comparisons. So this
is a second file rather than a flag on the first.

Why more items at all. Every headline in HANDOFF-whitebox.md that rests on Tier A
is limited by n. The skill fixes 13 of 39 items, so the "did the patch put those
back" reading is a count out of 13, and a difference of one item moves it by
7.7pp. The four-cell split (rescued / persistent / kept / broken) that the
HOWSKILLWORK line uses gets 13 / 9 / 9 / 8 out of 39 -- too few to compare cells.
Widening the value range is the only knob that does not change the skill, the
prompt, or the distractor logic, so the new items are the same experiment.

Constraints kept identical to build.py:
  - integer answers only (otherwise the free-numeric form measures rounding)
  - answers appearing in the skill document are dropped (copy-a-worked-example)
  - distractors are misreadings of the table, never random
  - the key is rotated A/B/C/D so a position-biased model still scores at chance
  - `other != dst` in the neighbouring-row branch, so the question's own quantity
    never becomes an option (HANDOFF-whitebox.md 12.3m)

    python build_large.py --max-value 40        # -> tasks.large.jsonl
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import random

import build as B          # FAMILIES, convert, is_clean, distractors, classify_option

HERE = pathlib.Path(__file__).resolve().parent
SEED = 20260910


def build(max_value: int, seed: int = SEED):
    rng = random.Random(seed)
    banned = B.skill_numbers()
    items, skipped, idx = [], 0, 0

    pairs = []
    for fam, table in B.FAMILIES.items():
        units = list(table)
        for src in units:
            for dst in units:
                if src != dst:
                    pairs.append((fam, src, dst))

    # value-major rather than pair-major, so that a truncated file is still
    # balanced across families rather than being all `length`.
    for value in range(2, max_value + 1):
        for fam, src, dst in pairs:
            correct = B.convert(value, src, dst, fam)
            if not B.is_clean(correct):
                continue
            if round(correct) in banned:
                skipped += 1
                continue
            ds = B.distractors(value, src, dst, fam, correct, rng)
            if len(ds) < 3:
                continue
            ds = ds[:3]

            question = (f"A Kelmar document lists a quantity of {value} {src}. "
                        f"How many {dst} is that?")
            options = ds + [round(correct)]
            rng.shuffle(options)
            target_slot = idx % 4
            cur = options.index(round(correct))
            options[cur], options[target_slot] = options[target_slot], options[cur]
            letter = "ABCD"[target_slot]

            items.append({
                "id": f"tierAL-{idx:04d}",
                "family": fam, "src": src, "dst": dst, "value": value,
                "hops": abs(list(B.FAMILIES[fam]).index(src)
                            - list(B.FAMILIES[fam]).index(dst)),
                "question_mc": question + "\n" + "\n".join(
                    f"{L}. {o}" for L, o in zip("ABCD", options)),
                "answer_mc": letter,
                "question_num": question + " Answer with the number only.",
                "answer_num": str(round(correct)),
                "options": options,
                "option_kinds": {
                    L: B.classify_option(o, value, src, dst, fam, correct)
                    for L, o in zip("ABCD", options)},
            })
            idx += 1
    return items, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-value", type=int, default=40)
    ap.add_argument("--out", default="tasks.large.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items, skipped = build(args.max_value)
    fam = collections.Counter(i["family"] for i in items)
    kinds = collections.Counter(k for i in items for k in i["option_kinds"].values())
    keys = collections.Counter(i["answer_mc"] for i in items)
    # Overlap on the DESIGN cell (family, src, dst, value), not on the rendered
    # question: the option order is reshuffled under a different seed, so a
    # string comparison would report zero and hide that the frozen 39 are all
    # re-derived here. All 39 should reappear; anything less is a regression in
    # the shared generator.
    cell = lambda i: (i["family"], i["src"], i["dst"], i["value"])
    old = [json.loads(l) for l in open(HERE / "tasks.jsonl", encoding="utf-8")]
    overlap = {cell(i) for i in old} & {cell(i) for i in items}

    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, sort_keys=True, ensure_ascii=False).encode())

    print(f"n            : {len(items)}   (skipped {skipped} contaminated)")
    print(f"families     : {dict(fam)}")
    print(f"answer key   : {dict(keys)}")
    print(f"option kinds : {dict(kinds)}")
    print(f"design cells shared with frozen tasks.jsonl : "
          f"{len(overlap)} / {len(old)}")
    print(f"sha256[:16]  : {h.hexdigest()[:16]}")
    if args.dry_run:
        return
    with open(HERE / args.out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {HERE / args.out}")


if __name__ == "__main__":
    main()
