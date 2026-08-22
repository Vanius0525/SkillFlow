#!/usr/bin/env python3
"""
Check whether a skill leaks the answers of the tasks it is paired with.

If it does, the experiment measures retrieval of a literal answer string rather
than any mechanism worth naming, and the whole H1/H2 split becomes meaningless
-- everything looks like H1.

Two checks:

  1  the gold answer appears verbatim in the skill text
  2  a long n-gram is shared between the question and the skill

Check 2 catches the subtler case: the skill contains a worked example of the
same problem, so the model can pattern-match rather than apply anything.

Tier A cannot be contaminated by construction (invented units), so a hit there
means the generator and the skill drifted apart -- which is worth knowing too.

    python contamination.py
    python contamination.py --n 8      # stricter n-gram length
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent

PAIRS = [
    ("tasks/tier_a/tasks.jsonl", "tasks/tier_a/SKILL.zorb-units.md"),
    ("tasks/tier_b/tasks.jsonl", "tasks/tier_b/SKILL.pchem-constants.md"),
    ("tasks/tier_b/tasks.jsonl", "tasks/tier_b/SKILL.pchem-procedure.md"),
    # Tier B v2 pairs the same two skills with the generated setup-selection
    # set. Its gold is a composite -- "<relation> + <constant>" -- and neither
    # document contains that pairing, because one holds the relations and the
    # other holds the constants. A hit here would mean the generator drifted
    # into quoting a skill rather than combining the two.
    ("tasks/tier_b2/tasks.jsonl", "tasks/tier_b/SKILL.pchem-constants.md"),
    ("tasks/tier_b2/tasks.jsonl", "tasks/tier_b/SKILL.pchem-procedure.md"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def ngrams(s: str, n: int):
    w = norm(s).split()
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="n-gram length for overlap")
    args = ap.parse_args()

    total_bad = 0
    for tpath, spath in PAIRS:
        tp, sp = HERE / tpath, HERE / spath
        if not tp.exists() or not sp.exists():
            print(f"[skip] {tpath} + {spath.split('/')[-1]} (missing)")
            continue
        items = [json.loads(l) for l in io.open(tp, encoding="utf-8") if l.strip()]
        skill = sp.read_text(encoding="utf-8")
        sk_norm = norm(skill)
        sk_ngrams = ngrams(skill, args.n)

        answer_hits, ngram_hits = [], []
        for it in items:
            gold = str(it.get("answer_num") or it.get("answer_raw") or "")
            q = it.get("question_mc") or it.get("question") or ""
            # a bare short number matches everywhere; only flag >= 3 chars
            if len(gold) >= 3 and f" {gold.lower()} " in f" {sk_norm} ":
                answer_hits.append(it["id"])
            if ngrams(q, args.n) & sk_ngrams:
                ngram_hits.append(it["id"])

        bad = set(answer_hits) | set(ngram_hits)
        total_bad += len(bad)
        tag = "OK  " if not bad else "HIT "
        print(f"[{tag}] {tpath.split('/')[-2]} x {sp.name}: "
              f"{len(items)} items, answer-in-skill {len(answer_hits)}, "
              f"{args.n}-gram overlap {len(ngram_hits)}")
        if bad:
            print(f"        affected ids: {sorted(bad)[:10]}"
                  f"{' ...' if len(bad) > 10 else ''}")

    print()
    if total_bad:
        print(f"{total_bad} item/skill combinations flagged. Drop those items "
              f"before running, or the effect you measure is memorisation.")
    else:
        print("No contamination found. Note this only rules out literal overlap; "
              "it cannot rule out the model having seen these textbook problems "
              "during pretraining, which is what the no-skill baseline measures.")


if __name__ == "__main__":
    main()
