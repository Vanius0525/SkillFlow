#!/usr/bin/env python3
"""
Select the Tier B task pool from SciBench's text-only problem sets.

Tier B is where the research question lives; Tier A only proves the instruments
work. These are real problems with real skills, so the effect is whatever it
turns out to be.

Selection criteria and why:

- Source is SciBench/dataset/original/*.json, which is text with a numeric
  answer. The img/ variant is a picture of the problem and cannot be used with a
  text-only model.
- Physical chemistry subjects only (atkins, thermo, chemmc). Both Tier B skills
  are written for that domain; injecting them into a calculus problem would test
  nothing except distraction.
- A numeric answer must parse as a float. The dependent variable is the logprob
  of the answer, so an answer that is a phrase has no single position to score.
- Problems whose text is very short are dropped: they usually reference a figure
  that is not in the text version.

The pool is NOT the final task set. Items the model already answers correctly
without any skill still have to be removed, and that needs the model -- e0_effect.py
does it on the server. Removing them matters: they cannot show a skill effect and
only dilute the measured one.

    python build.py            # write tasks.jsonl
    python build.py --check    # verify the committed file matches
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
SRC = REPO / "SciBench" / "dataset" / "original"
OUT = HERE / "tasks.jsonl"

# atkins = physical chemistry (Atkins), thermo = thermodynamics/electrochemistry,
# chemmc = quantum chemistry. All three are covered by the two Tier B skills.
SUBJECTS = ["atkins", "thermo", "chemmc"]

MIN_TEXT_CHARS = 60


def parse_number(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    m = re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$", s)
    return float(s) if m else None


def clean_unit(u) -> str:
    """SciBench units are LaTeX fragments; keep them but normalise whitespace."""
    return re.sub(r"\s+", " ", (u or "").replace("$", "").replace("\\mathrm", "")).strip()


def skill_numbers() -> set:
    """Numeric literals appearing in either Tier B skill.

    An answer that coincides with a constant printed in the skill can be copied
    rather than derived -- tierB-0208 asks for the kinetic energy of an electron
    accelerated through 100 V, whose answer 1.602 is the elementary charge's
    mantissa, sitting in the constants table. Whatever the model does there, it
    registers as retrieval, so the item cannot distinguish H1 from anything else.

    Character class rather than a backslash escape, for the reason recorded in
    tier_a/build.py: a mangled escape fails silently and every display path hides
    it.
    """
    out = set()
    for p in HERE.glob("SKILL.*.md"):
        for m in re.findall("[0-9]+[.][0-9]+|[0-9]+", p.read_text(encoding="utf-8")):
            out.add(m)
    return out


def build():
    banned = skill_numbers()
    items, idx, skipped = [], 0, 0
    for subj in SUBJECTS:
        p = SRC / f"{subj}.json"
        if not p.exists():
            print(f"[WARN] missing {p} -- skipped")
            continue
        for rec in json.load(io.open(p, encoding="utf-8")):
            text = (rec.get("problem_text") or "").strip()
            num = parse_number(rec.get("answer_number"))
            if num is None or len(text) < MIN_TEXT_CHARS:
                continue
            if str(rec.get("answer_number")).strip() in banned:
                skipped += 1
                continue
            items.append({
                "id": f"tierB-{idx:04d}",
                "subject": subj,
                "problemid": (rec.get("problemid") or "").strip(),
                "question": text,
                "answer": num,
                "answer_raw": str(rec.get("answer_number")).strip(),
                "unit": clean_unit(rec.get("unit")),
            })
            idx += 1
    if skipped:
        print(f"(skipped {skipped} items whose answer coincides with a constant "
              f"printed in a Tier B skill)")
    return items


def digest(items) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    items = build()
    if not items:
        print(f"[FAIL] no items -- is {SRC} present? (git lfs pull)")
        raise SystemExit(1)
    d = digest(items)

    if args.check:
        if not OUT.exists():
            print("[FAIL] tasks.jsonl missing -- run without --check first")
            raise SystemExit(1)
        have = [json.loads(l) for l in io.open(OUT, encoding="utf-8") if l.strip()]
        if digest(have) != d:
            print(f"[FAIL] tasks.jsonl does not match ({digest(have)} vs {d})")
            raise SystemExit(1)
        print(f"[ OK ] tasks.jsonl matches, {len(have)} items, sha {d}")
        return

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"wrote {OUT} -- {len(items)} items, sha {d}")
    print("by subject:", {s: sum(1 for i in items if i["subject"] == s) for s in SUBJECTS})
    withunit = sum(1 for i in items if i["unit"])
    print(f"with a unit: {withunit}/{len(items)}")
    print("\nNOTE: this is the candidate pool. e0_effect.py --filter-known drops the")
    print("      items the model already answers correctly with no skill.")


if __name__ == "__main__":
    main()
