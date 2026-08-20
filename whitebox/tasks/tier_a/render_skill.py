#!/usr/bin/env python3
"""
Render SKILL.zorb-units.md from the conversion tables.

Why a renderer for a file that already exists: E6 (HANDOFF-whitebox.md section 3)
needs a COUNTERFACTUAL skill -- the same document with one factor changed -- to
ask whether the model is really reading the table or answering from somewhere
else. Editing the document by hand leaves the worked examples stating results the
table no longer supports, and the model would then be reading a self-contradictory
document: a different experiment, and a confounded one.

Generating both versions from the table keeps every derived number consistent, so
the true and counterfactual documents differ ONLY in the intended factor.

The guarantee that makes this usable:

    python render_skill.py --check

renders with the unperturbed tables and compares against the committed
SKILL.zorb-units.md byte for byte. If that passes, any difference between the
rendered counterfactual and the committed skill is the perturbation and nothing
else. It runs inside e6_counterfactual.py before any measurement.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE / "SKILL.zorb-units.md"

# Must match build.py:FAMILIES.
FAMILIES = {
    "length": {"dref": 1, "glorn": 7, "varak": 84, "skellum": 420},
    "mass": {"zunt": 1, "pelm": 9, "brask": 180},
    "duration": {"tovek": 1, "wemp": 15, "cradal": 60},
}

TITLE = {"length": "Length", "mass": "Mass", "duration": "Duration"}


def fmt(x: float) -> str:
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:g}"


def render(fams: dict) -> str:
    L, M, D = fams["length"], fams["mass"], fams["duration"]
    units = {f: list(t) for f, t in fams.items()}
    lines = []
    add = lines.append

    add("---")
    add("name: zorb-units")
    add('description: "Conversion reference for the Zorb measurement system, used '
        'in Kelmar engineering documents. Use when converting between Zorb units '
        'of length (' + ", ".join(units["length"]) + "), mass ("
        + ", ".join(units["mass"]) + "), or duration ("
        + ", ".join(units["duration"]) + '), or when a quantity is stated in Zorb '
        'units and another Zorb unit is requested."')
    add("---")
    add("")
    add("# Zorb Unit System")
    add("")
    add("The Zorb system is the measurement standard used in Kelmar engineering")
    add("documents. Each quantity family has one base unit and several larger units")
    add("defined as exact whole multiples of the unit one step below.")
    add("")
    add("## When to Use")
    add("")
    add("- A quantity is given in one Zorb unit and requested in another")
    add("- A Kelmar document states a measurement and an equivalent is needed")
    add("- Converting across more than one step in the same family")
    add("")
    add("## Conversion Tables")

    for fam in ("length", "mass", "duration"):
        t = fams[fam]
        names = list(t)
        base = names[0]
        add("")
        add(f"### {TITLE[fam]}")
        add("")
        add(f"| Unit | Equals | In base units ({base}) |")
        add("| ---- | ------ | " + "-" * (len("In base units (") + len(base) + 1) + " |")
        for i, u in enumerate(names):
            if i == 0:
                equals = "base unit"
            else:
                prev = names[i - 1]
                equals = f"{fmt(t[u] / t[prev])} {prev}"
            add(f"| {u} | {equals} | {fmt(t[u])} |")

    add("")
    add("## Procedure")
    add("")
    add("1. Identify the quantity family (length, mass, or duration). Units never")
    add("   convert across families.")
    add('2. Look up both units in the "In base units" column of that family\'s table.')
    add("3. Multiply the value by the source unit's base value, then divide by the")
    add("   target unit's base value.")
    add("")
    add("## Worked Examples")
    add("")
    # Every number below is derived, so a perturbed table stays self-consistent.
    add("**Converting down one step.** How many dref are in 3 glorn?")
    add(f"A glorn is {fmt(L['glorn'])} dref, so 3 x {fmt(L['glorn'])} = "
        f"{fmt(3 * L['glorn'])} dref.")
    add("")
    add("**Converting down two steps.** How many dref are in 2 varak?")
    add(f"A varak is {fmt(L['varak'])} dref, so 2 x {fmt(L['varak'])} = "
        f"{fmt(2 * L['varak'])} dref.")
    add("")
    add(f"**Converting up.** How many pelm are in {fmt(60 * M['pelm'])} zunt?")
    add(f"A pelm is {fmt(M['pelm'])} zunt, so {fmt(60 * M['pelm'])} / "
        f"{fmt(M['pelm'])} = 60 pelm.")
    add("")
    add("**Across two named units.** How many glorn are in 3 skellum?")
    add(f"A skellum is {fmt(L['skellum'])} dref and a glorn is {fmt(L['glorn'])} "
        f"dref, so 3 x {fmt(L['skellum'])} / {fmt(L['glorn'])} = "
        f"{fmt(3 * L['skellum'] / L['glorn'])} glorn.")
    add("")
    add("## Notes")
    add("")
    add("- All factors are exact; no rounding is required for the conversions above.")
    add("- Length, mass and duration units are never interchangeable, even where the")
    add("  numeric factors coincide.")
    add("")
    _ = D
    return "\n".join(lines)


def perturb(unit: str, new_base: float) -> dict:
    """A copy of FAMILIES with one unit's base value replaced."""
    out = {f: dict(t) for f, t in FAMILIES.items()}
    for fam, t in out.items():
        if unit in t:
            if list(t).index(unit) == 0:
                raise ValueError(f"{unit} is the base unit of {fam}; "
                                 f"perturbing it rescales the whole family")
            t[unit] = new_base
            return out
    raise KeyError(unit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the committed skill matches this renderer")
    ap.add_argument("--unit", help="perturb this unit's base value")
    ap.add_argument("--value", type=float, help="the replacement base value")
    args = ap.parse_args()

    if args.check:
        want = SKILL.read_text(encoding="utf-8")
        got = render(FAMILIES)
        if want.replace("\r\n", "\n") == got:
            print(f"[ OK ] {SKILL.name} matches the renderer")
            return
        print(f"[FAIL] {SKILL.name} differs from the renderer. The counterfactual")
        print("       skill would then differ from the committed one in ways other")
        print("       than the perturbation, and E6 would measure those too.")
        import difflib
        for line in list(difflib.unified_diff(
                want.replace("\r\n", "\n").splitlines(), got.splitlines(),
                "committed", "rendered", lineterm=""))[:40]:
            print("      ", line)
        sys.exit(1)

    fams = FAMILIES if not args.unit else perturb(args.unit, args.value)
    sys.stdout.write(render(fams))


if __name__ == "__main__":
    main()
