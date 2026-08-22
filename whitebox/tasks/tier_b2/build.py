#!/usr/bin/env python3
"""
Generate the Tier B v2 task set: pick the setup, do not evaluate it.

Why this set exists
-------------------
Tier B v1 (SciBench physical chemistry, free numeric answers) measured nothing:
Qwen3-8B scored 0.067 with no skill and 0.108 with one, and a baseline that low
has no room for a skill to act in. The cause was not that the problems are
multi-step -- many are a single relation -- but that the design decodes with
thinking off and a 24-token budget, so the model has to carry a three-digit
multiply-divide in one forward pass before its first emitted token. See
HANDOFF-whitebox.md 12.3h and 15.

This set removes the arithmetic and keeps the chemistry. The model is shown a
scenario and four candidate SETUPS, and picks the one that would be correct. It
never evaluates anything.

The 2x2 that makes the set worth building
-----------------------------------------
Every item has exactly four options, laid out as a factorial over two
independent axes:

                        right constant       wrong constant
    right relation      correct              wrong_const
    wrong relation      wrong_rel            wrong_both

The two axes are owned by the two skills, and neither skill covers the other's
axis by construction:

    SKILL.pchem-constants   values only, no methods  ->  should fix wrong_const
    SKILL.pchem-procedure   methods only, no values  ->  should fix wrong_rel

So the preregistered prediction is a DOUBLE DISSOCIATION, not an accuracy delta:
constants should move wrong_const and leave wrong_rel alone, procedure should do
the reverse. That is falsifiable from e0 + errors.py alone, with no layer sweep,
and a single skill that moves both axes falsifies the example/principle framing
that E2's preregistered prediction rests on (HANDOFF 9.2).

Design choices and why
----------------------
- Single-letter answers, because the dependent variable is the logprob of the
  answer token. Same reason as Tier A.
- The distractors are never random: each is the gold setup with exactly one axis
  flipped, so the letter the model picks names which of the two failures it made.
- Wrong relations come from a CONFUSABLE pair, not from the whole table. A gas
  item is never offered "de Broglie relation"; it is offered van der Waals,
  which is what the procedure skill's Step 1 exists to separate.
- Wrong constants come from the same constant family (another unit of R, or F
  where R is right), which is what the constants skill's closing note -- "match
  R to the units already present in the problem" -- exists to separate.
- The scenario states its units explicitly, because the constant axis is a units
  question. The numbers in the scenario are never used; they are there so the
  surface form looks like the domain rather than like a quiz about a table.
- Gold letters are balanced exactly across A/B/C/D, so a position-biased model
  scores exactly at chance without a skill.

What this set does NOT cover: procedure Steps 2-4 (sign conventions, electron
count, the final check) and the Gibbs / first law / de Broglie rows of Step 1.
Steps 2-4 have no constant axis, so they do not fit the 2x2. If the double
dissociation holds here, a sign-convention set is the natural follow-up.

Validity, stated plainly
------------------------
Tier B v1's tasks were external (SciBench, stems unmodified). These are not:
both the scenarios and the options are generated here. The relations and the
constants are copied from the two skills, so the set is solvable by them by
construction -- exactly like Tier A, and for the same reason. That makes this a
second positive control with realistic surface vocabulary, NOT evidence about
how much skills help in the wild. Do not quote an effect size from this set as
a general one. HANDOFF-whitebox.md 11.2 and 15 carry the same warning.

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
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "tasks.jsonl"
SEED = 20260823

# --- constants -------------------------------------------------------------
#
# The value half of every string here appears verbatim in
# SKILL.pchem-constants.md, and verify() checks it on every build. A constant
# spelled differently from the skill would make the item unanswerable from the
# document, and the resulting null would be about the spelling.
R_J = "R = 8.314 J K^-1 mol^-1"
R_LATM = "R = 0.08206 L atm K^-1 mol^-1"
R_LBAR = "R = 8.314 x 10^-2 L bar K^-1 mol^-1"
R_CM3 = "R = 82.06 cm^3 atm K^-1 mol^-1"
F_C = "F = 96485 C mol^-1"

# --- relations -------------------------------------------------------------
#
# Names are the Relation column of SKILL.pchem-procedure.md Step 1, verbatim.
GAS = "perfect gas law"
VDW = "van der Waals"
WORK = "reversible isothermal work"
CELL = "free energy from cell potential"
NERNST = "Nernst relation"
KEQ = "free energy from equilibrium constant"

# Which wrong relation is plausible for each right one. Step 1 of the procedure
# skill separates exactly these pairs; a distractor from outside the pair could
# be rejected without reading anything, which would make the item measure
# general chemistry rather than the document.
CONFUSABLE = {
    GAS: VDW,
    VDW: GAS,
    WORK: GAS,
    CELL: NERNST,
    NERNST: CELL,
    KEQ: CELL,
}

SUBSTANCES = ["argon", "nitrogen", "methane", "carbon dioxide", "ethane",
              "oxygen", "helium", "ammonia", "krypton", "propane"]

# (pressure unit, volume unit) -> the R whose units cancel. Straight from the
# constants skill's closing note.
UNIT_PAIRS = [
    ("atm", "dm^3", R_LATM),
    ("atm", "L", R_LATM),
    ("bar", "dm^3", R_LBAR),
    ("Pa", "m^3", R_J),
    ("atm", "cm^3", R_CM3),
]

LETTERS = "ABCD"
# Option kind -> what picking it means. Consumed by errors.py.
KINDS = ["correct", "wrong_const", "wrong_rel", "wrong_both"]


def gas_specs(rng, real_gas: bool):
    """Perfect gas / van der Waals. The constant axis is which R has the units."""
    out = []
    for punit, vunit, right_r in UNIT_PAIRS:
        for _ in range(4):
            sub = rng.choice(SUBSTANCES)
            n = round(rng.uniform(0.5, 12.0), 2)
            v = round(rng.uniform(1.0, 40.0), 2)
            tc = rng.choice([15, 20, 25, 30, 45, 60, 75, 100])
            # The discriminator is stated, not shouted. It has to be present
            # -- Step 1 of the procedure skill keys on "real gas, moderate p" --
            # but capitalising it would let the model answer the relation axis
            # off the formatting instead of off the document.
            qualifier = ("The gas is at moderate pressure and does not behave "
                         "perfectly."
                         if real_gas else
                         "The gas behaves perfectly under these conditions.")
            out.append({
                "scenario": (f"A vessel of {v} {vunit} holds {n} mol of {sub} "
                             f"at {tc} degC. {qualifier} The pressure is "
                             f"required in {punit}."),
                "relation": VDW if real_gas else GAS,
                "constant": right_r,
                "wrong_constant": rng.choice(
                    [r for _, _, r in UNIT_PAIRS if r != right_r]),
            })
    return out


def work_specs(rng):
    """Reversible isothermal work, confusable with the gas law it comes from."""
    out = []
    for _ in range(16):
        sub = rng.choice(SUBSTANCES)
        n = round(rng.uniform(0.5, 6.0), 2)
        vi = round(rng.uniform(1.0, 10.0), 2)
        vf = round(vi * rng.uniform(1.5, 4.0), 2)
        tc = rng.choice([25, 37, 50, 80])
        out.append({
            "scenario": (f"{n} mol of {sub} expands isothermally and reversibly "
                         f"from {vi} dm^3 to {vf} dm^3 at {tc} degC. The work "
                         f"done is required in joules."),
            "relation": WORK,
            "constant": R_J,
            "wrong_constant": rng.choice([R_LATM, R_LBAR, R_CM3]),
        })
    return out


def electro_specs(rng):
    """Cell potential and Nernst. The constant axis is F against R."""
    out = []
    couples = ["Zn|Zn2+ and Cu2+|Cu", "Ag+|Ag and Cu2+|Cu",
               "Fe3+|Fe2+ and Ce4+|Ce3+", "Cl2|Cl- and Br2|Br-",
               "Pb2+|Pb and Sn2+|Sn", "MnO4-|Mn2+ and Fe3+|Fe2+"]
    for c in couples:
        for _ in range(3):
            e = round(rng.uniform(0.15, 1.60), 3)
            n_e = rng.choice([1, 2, 2, 3])
            out.append({
                "scenario": (f"A cell built from {c} has a standard cell "
                             f"potential of {e} V with {n_e} "
                             f"electron{'s' if n_e > 1 else ''} "
                             f"transferred. All species are at their "
                             f"standard states. The standard reaction free "
                             f"energy is required."),
                "relation": CELL,
                "constant": F_C,
                "wrong_constant": R_J,
            })
            conc = round(rng.uniform(0.01, 0.5), 3)
            out.append({
                "scenario": (f"A cell built from {c} has a standard cell "
                             f"potential of {e} V with {n_e} "
                             f"electron{'s' if n_e > 1 else ''} "
                             f"transferred. The ion concentrations are "
                             f"{conc} mol dm^-3. The cell potential under "
                             f"these conditions is required."),
                "relation": NERNST,
                "constant": R_J,
                "wrong_constant": F_C,
            })
    return out


def keq_specs(rng):
    """Equilibrium constant to free energy, confusable with the cell route."""
    out = []
    reactions = ["N2 + 3 H2 -> 2 NH3", "2 SO2 + O2 -> 2 SO3",
                 "H2 + I2 -> 2 HI", "PCl5 -> PCl3 + Cl2",
                 "CO + H2O -> CO2 + H2", "2 NO2 -> N2O4"]
    for rxn in reactions:
        for _ in range(4):
            k = rng.choice([0.0032, 0.15, 2.4, 18.0, 640.0, 12000.0])
            tc = rng.choice([25, 100, 200, 350])
            out.append({
                # Deliberately no "no electrochemical data are given": the
                # absence of a cell IS the signal, and spelling it out would
                # settle the relation axis without reading anything.
                "scenario": (f"The reaction {rxn} has an equilibrium constant "
                             f"of {k} at {tc} degC. The standard reaction free "
                             f"energy is required."),
                "relation": KEQ,
                "constant": R_J,
                "wrong_constant": F_C,
            })
    return out


def render(spec, rng, gold_letter: str):
    """One spec -> a four-option item with the gold sitting on `gold_letter`."""
    rel, con = spec["relation"], spec["constant"]
    by_kind = {
        "correct": (rel, con),
        "wrong_const": (rel, spec["wrong_constant"]),
        "wrong_rel": (CONFUSABLE[rel], con),
        "wrong_both": (CONFUSABLE[rel], spec["wrong_constant"]),
    }
    others = [k for k in KINDS if k != "correct"]
    rng.shuffle(others)
    gi = LETTERS.index(gold_letter)
    slots = others[:gi] + ["correct"] + others[gi:]

    lines = [f"{L}. {by_kind[k][0]}, using {by_kind[k][1]}"
             for L, k in zip(LETTERS, slots)]
    q = (f"{spec['scenario']}\n\n"
         f"Which setup is correct? Do not carry out the calculation.\n"
         + "\n".join(lines))
    return q, slots


def build():
    rng = random.Random(SEED)
    specs = (gas_specs(rng, False) + gas_specs(rng, True) + work_specs(rng)
             + electro_specs(rng) + keq_specs(rng))
    rng.shuffle(specs)
    # The gold letter is cycled A/B/C/D, so an exact balance needs a multiple of
    # four. Trimming after the shuffle keeps the drop unbiased across families;
    # it is printed rather than silent because a future edit to the family sizes
    # would otherwise lose items without saying so.
    keep = len(specs) // 4 * 4
    dropped, specs = len(specs) - keep, specs[:keep]

    items = []
    for i, spec in enumerate(specs):
        # Cycled rather than sampled, so the balance is exact instead of
        # approximate: a model that always answers "C" scores exactly 0.25.
        gold = LETTERS[i % 4]
        q, slots = render(spec, rng, gold)
        rel = spec["relation"]
        items.append({
            "id": f"tierB2-{i:04d}",
            "question_mc": q,
            "answer_mc": gold,
            # Composite label. Neither document states this pairing for this
            # scenario -- the relation lives in one and the constant in the
            # other -- so contamination.py has something meaningful to test.
            "answer_raw": f"{rel} + {spec['constant']}",
            "relation": rel,
            "constant": spec["constant"],
            "wrong_relation": CONFUSABLE[rel],
            "wrong_constant": spec["wrong_constant"],
            "option_kinds": {L: k for L, k in zip(LETTERS, slots)},
            "group": ("gas" if rel in (GAS, VDW)
                      else "work" if rel == WORK
                      else "equilibrium" if rel == KEQ
                      else "electrochemistry"),
        })
    return items, dropped


def verify(items) -> list[str]:
    """
    Invariants that must hold for the 2x2 to mean anything. Checked on every
    build and every --check, because a set that has quietly lost the factorial
    still produces numbers, and those numbers would be read as a dissociation.
    """
    bad = []
    sk = HERE.parent / "tier_b"
    consts = (sk / "SKILL.pchem-constants.md").read_text(encoding="utf-8")
    proc = (sk / "SKILL.pchem-procedure.md").read_text(encoding="utf-8")
    for c in (R_J, R_LATM, R_LBAR, R_CM3, F_C):
        val = c.split(" = ", 1)[1]
        if val not in consts:
            bad.append(f"constant absent from the constants skill: {c}")
    for r in (GAS, VDW, WORK, CELL, NERNST, KEQ):
        if r not in proc:
            bad.append(f"relation absent from the procedure skill: {r}")

    letters = Counter(it["answer_mc"] for it in items)
    if len(set(letters.values())) != 1:
        bad.append(f"gold letters not balanced: {dict(letters)}")
    for it in items:
        kinds = sorted(it["option_kinds"].values())
        if kinds != sorted(KINDS):
            bad.append(f"{it['id']}: options are not the 2x2 -- {kinds}")
        if it["option_kinds"][it["answer_mc"]] != "correct":
            bad.append(f"{it['id']}: gold letter does not carry the correct option")
        if it["constant"] == it["wrong_constant"]:
            bad.append(f"{it['id']}: constant axis is degenerate")
        if it["relation"] == it["wrong_relation"]:
            bad.append(f"{it['id']}: relation axis is degenerate")
    return bad


def digest(items) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the committed tasks.jsonl matches this generator")
    args = ap.parse_args()

    items, dropped = build()
    bad = verify(items)
    if bad:
        print("[FAIL] the generated set violates its own invariants:")
        for b in bad[:10]:
            print("   ", b)
        raise SystemExit(1)
    d = digest(items)

    if args.check:
        if not OUT.is_file():
            print("[FAIL] tasks.jsonl missing -- run without --check first")
            raise SystemExit(1)
        have = [json.loads(l) for l in io.open(OUT, encoding="utf-8") if l.strip()]
        if digest(have) != d:
            print(f"[FAIL] tasks.jsonl does not match the generator "
                  f"({digest(have)} vs {d}). Someone edited one of the two.")
            raise SystemExit(1)
        print(f"[ OK ] tasks.jsonl matches the generator, {len(have)} items, "
              f"sha {d}")
        return

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {OUT} -- {len(items)} items, sha {d}"
          + (f"  ({dropped} trimmed to keep the letter balance exact)"
             if dropped else ""))


if __name__ == "__main__":
    main()
