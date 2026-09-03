#!/usr/bin/env python3
"""
Read an e2 run's per_layer.jsonl and report the ACCURACY channel of the same
layer sweep: the three control curves, and how many items each margin rests on.

Why this exists. On Tier A the logprob channel cannot answer E2's question. The
filler document recovers MORE than the real skill (+2.783 vs +1.470 at layer
21), so "recovery" there is measuring that a long document's residual state was
injected at all, not that this skill's content was. Accuracy is a threshold on
the same distribution and can therefore disagree, which is why e2_patch.py
records ok_* alongside lp_* and why HANDOFF-whitebox.md 12.3r (b) pre-registered
the accuracy controls as the thing that decides whether E2 survives.

What this adds over report.py, which already prints the four numbers at the peak
layer:

  1. The whole curve, not one layer. A control that tracks real across every
     layer is a different object from one that meets it only at the argmax.
  2. The mismatched column gets judged. report.py's "another item's vector also
     recovers" check reads best_layer_mismatched, which is the LOGPROB ratio; on
     Tier A that is -3.2 and the check stays silent while the accuracy channel
     has mismatched at 15/39 against real's 18/39.
  3. The counts. Every gap on this run is a handful of items out of 39 -- real
     minus filler is 8 items, real minus mismatched is 3 -- so the difference
     alone is not a readable quantity. Paired discordant counts, an exact
     McNemar p, and a paired bootstrap CI are.

The peak layer is chosen by argmax and then tested at that same layer, which
biases any p computed there. That is why the pre-specified layer from
summary.json (the logprob argmax, fixed before this channel was looked at) is
printed next to it: agreement between the two is the part that is not selected.

Pure post-processing, like errors.py and e6_diagnose.py: no GPU, no model, no
torch.

    python e2_acc.py results/<run-id>/e2-tierA
    python e2_acc.py results/<run-id>/e2-tierA results/<run-id>/e2-tierA-k4
"""
from __future__ import annotations

import argparse
import io
import json
import math
import pathlib
import random
import sys

# real first: the rest are read against it, and against the two baselines.
CONDS = ("real", "mismatched", "mean", "filler")
LABEL = {"real": "real", "mismatched": "mismatch", "mean": "mean vec",
         "filler": "filler", "no": "no doc", "yes": "with skill"}
NAN = float("nan")


def load(stage: pathlib.Path) -> tuple[list[dict], dict]:
    p = stage / "per_layer.jsonl"
    if not p.is_file():
        sys.exit(f"no per_layer.jsonl in {stage}")
    layers = [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]
    s = stage / "summary.json"
    summary = json.loads(s.read_text(encoding="utf-8")) if s.is_file() else {}
    return layers, summary


def acc(rows: list[dict], key: str) -> float:
    got = [r["ok_" + key] for r in rows if r.get("ok_" + key) is not None]
    return sum(got) / len(got) if got else NAN


def binom_cdf(k: int, n: int) -> float:
    """P(X <= k) for X ~ Binomial(n, 1/2). n here is a discordant count, so it
    is small enough that the exact sum is cheaper than any approximation."""
    return sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n)


def mcnemar(rows: list[dict], a: str, b: str) -> tuple[int, int, float]:
    """(a right & b wrong, a wrong & b right, exact two-sided p).

    The unpaired comparison would throw away that both conditions are scored on
    the SAME 39 items with the same extractor; items that both conditions get
    right, or both get wrong, carry no information about the difference and are
    not in n.
    """
    ka, kb = "ok_" + a, "ok_" + b
    pairs = [(r[ka], r[kb]) for r in rows
             if r.get(ka) is not None and r.get(kb) is not None]
    nb = sum(1 for x, y in pairs if x and not y)
    nc = sum(1 for x, y in pairs if y and not x)
    n = nb + nc
    if n == 0:
        return nb, nc, NAN
    return nb, nc, min(1.0, 2.0 * binom_cdf(min(nb, nc), n))


def boot_delta(rows: list[dict], a: str, b: str, n: int = 4000,
               seed: int = 0) -> tuple[float, float]:
    """Paired bootstrap CI on acc(a) - acc(b): resample ITEMS, keeping both of
    an item's scores together, which is the resampling e0 and e2 already use."""
    ka, kb = "ok_" + a, "ok_" + b
    pairs = [(r[ka], r[kb]) for r in rows
             if r.get(ka) is not None and r.get(kb) is not None]
    if not pairs:
        return NAN, NAN
    rng = random.Random(seed)
    k = len(pairs)
    out = []
    for _ in range(n):
        s = [pairs[rng.randrange(k)] for _ in range(k)]
        out.append(sum(x for x, _ in s) / k - sum(y for _, y in s) / k)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def peak_index(layers: list[dict]) -> int:
    """Index of the largest real accuracy, excluding the last two layers.

    Same exclusion e2_patch.py applies to the logprob curve: patching the last
    block at the last prompt token overwrites the state that emits the answer,
    so it "recovers" by writing straight through to the output rather than by
    carrying anything.
    """
    vals = [d["acc"].get("real", NAN) for d in layers]
    body = vals[:-2] if len(vals) > 4 else vals
    best = max((v for v in body if v == v), default=NAN)
    return vals.index(best)


def has(d: dict, cond: str) -> bool:
    """A condition is present when the sweep recorded it. no/yes are baselines
    carried on every row rather than sweep conditions, so they always are."""
    return cond in ("no", "yes") or (cond in d["acc"] and d["acc"][cond] == d["acc"][cond])


def print_curves(layers: list[dict], present: list[str], i_peak: int) -> None:
    head = "layer".rjust(5) + "".join(LABEL[c].rjust(10) for c in present)
    print("\n  " + head)
    for i, d in enumerate(layers):
        cells = "".join("{:>10.3f}".format(d["acc"].get(c, NAN)) for c in present)
        print("  {:>5}{}{}".format(d["layer"], cells, " *" if i == i_peak else ""))
    print("        * peak of the real curve (last two layers excluded)")


def print_tests(d: dict, why: str) -> None:
    rows = d["rows"]
    pairs = [("real", "no"), ("real", "filler"), ("real", "mismatched"),
             ("mismatched", "filler"), ("mismatched", "no"), ("mean", "no")]
    print("\n  --- layer {}   {}".format(d["layer"], why))
    print("  {:<24}{:>16}{:>9}{:>13}{:>9}{:>20}".format(
        "comparison", "acc", "delta", "discordant", "p", "CI95 on delta"))
    for a, b in pairs:
        if not (has(d, a) and has(d, b)):
            continue
        aa, ab = acc(rows, a), acc(rows, b)
        if aa != aa or ab != ab:
            continue
        nb, nc, p = mcnemar(rows, a, b)
        lo, hi = boot_delta(rows, a, b)
        print("  {:<24}{:>7.3f} {:>7.3f}{:>+9.3f}{:>13}{:>9.3f}{:>20}".format(
            LABEL[a] + " vs " + LABEL[b], aa, ab, aa - ab,
            "{}/{}".format(nb, nc), p, "[{:+.3f},{:+.3f}]".format(lo, hi)))
    print("      discordant = (first right, second wrong) / (second right, first"
          " wrong);")
    print("      p is exact McNemar on those two counts alone.")


def read_peak(d: dict, summary: dict, a_no: float, a_yes: float) -> None:
    rows = d["rows"]
    span = a_yes - a_no
    print("\n  reading layer {}:".format(d["layer"]))
    if not has(d, "filler"):
        print("    No filler condition in this run. Without it the accuracy")
        print("    channel cannot separate content from document-presence")
        print("    either -- rerun e2_patch.py with --filler.")
        return

    a_real, a_fill = acc(rows, "real"), acc(rows, "filler")
    nb, nc, p_fill = mcnemar(rows, "real", "filler")
    if abs(span) < 1e-9:
        print("    The two baselines are equal; this curve has no room to move.")
    elif (a_fill - a_no) / span < 0.3 <= (a_real - a_no) / span:
        print("    The filler stops at the no-document baseline ({:.3f} vs {:.3f})"
              .format(a_fill, a_no))
        print("    while real reaches {:.3f}. On THIS channel the patch carries"
              .format(a_real))
        print("    content, not the mere presence of a long document -- the")
        print("    opposite of what the logprob channel says. Both readings come")
        print("    from the same run, so both go in the paper, and neither is the")
        print("    'corrected' one.")
        print("    The margin rests on {} discordant items (p={:.3f})."
              .format(nb + nc, p_fill))
    else:
        print("    The filler recovers too ({:.3f} against a no-document baseline"
              .format(a_fill))
        print("    of {:.3f}). Accuracy agrees with logprob: what the patch"
              .format(a_no))
        print("    injects is document-presence. E2 is not evidence on H1 vs H2.")

    if has(d, "mismatched") and abs(span) > 1e-9:
        a_mis = acc(rows, "mismatched")
        nb, nc, p_mis = mcnemar(rows, "real", "mismatched")
        if (a_mis - a_no) / span > 0.5:
            print("\n    Another item's vector recovers {:.0%} of the span ({:.3f}),"
                  .format((a_mis - a_no) / span, a_mis))
            print("    and real minus mismatched is {:+.3f} on {} discordant items"
                  .format(a_real - a_mis, nb + nc))
            print("    (p={:.3f}). Whatever the patch carries is shared across the"
                  .format(p_mis))
            print("    items of this skill, not specific to the item it was")
            print("    captured from. That is compatible with H2 in its strong")
            print("    form, but it is NOT the claim that the vector carries this")
            print("    item's answer -- do not write the second one.")

    if has(d, "mean"):
        a_mean = acc(rows, "mean")
        lp_mean = summary.get("best_layer_meanvec")
        if a_mean <= a_no + 1e-9 and lp_mean is not None and lp_mean > 1.0:
            print("\n    The mean vector is the reverse case: {:.3f} on accuracy,"
                  .format(a_mean))
            print("    at the no-document baseline, against a logprob recovery of")
            print("    {:+.3f}. It lifts the gold token's probability without"
                  .format(lp_mean))
            print("    making it the argmax, which is what an off-manifold")
            print("    direction does. Read it as a warning about the logprob")
            print("    channel here, not as a shared direction that works.")


def report(stage: pathlib.Path) -> None:
    layers, summary = load(stage)
    rows0 = layers[0]["rows"]
    a_no, a_yes = acc(rows0, "no"), acc(rows0, "yes")
    present = [c for c in CONDS if any(has(d, c) for d in layers)]

    print("\n" + "=" * 72)
    print(" {}   accuracy channel   n={}  K={}".format(
        stage.name, len(rows0), summary.get("tail_k", "?")))
    print("=" * 72)
    if a_no != a_no:
        print("  This mode records no accuracy (no options to take an argmax"
              " over); only the logprob channel exists here.")
        return
    print("  baselines:  no doc {:.3f}   with skill {:.3f}   span {:+.3f}"
          .format(a_no, a_yes, a_yes - a_no))

    i_peak = peak_index(layers)
    print_curves(layers, present, i_peak)

    # The peak is where the effect is largest and also where selection makes a p
    # optimistic. The logprob best layer was fixed before this channel was looked
    # at, so it is the honest one; both are printed because a conclusion holding
    # at only one of them is a conclusion about layer choice.
    print_tests(layers[i_peak],
                "accuracy peak (selected on this curve -- p is optimistic)")
    bl = summary.get("best_layer")
    i_bl = next((i for i, d in enumerate(layers) if d["layer"] == bl), None)
    if i_bl is not None and i_bl != i_peak:
        print_tests(layers[i_bl],
                    "logprob best layer (pre-specified for this channel)")

    read_peak(layers[i_peak], summary, a_no, a_yes)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stages", nargs="+", metavar="STAGE_DIR",
                    help="one or more results/<run-id>/e2-* directories")
    args = ap.parse_args()
    for s in args.stages:
        report(pathlib.Path(s))
    print()


if __name__ == "__main__":
    main()
