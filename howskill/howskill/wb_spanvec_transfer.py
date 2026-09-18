"""Transfer arms, split by whether the model needs the document at all.

    python -m howskill.wb_spanvec_transfer <shard>.jsonl ...

Why this exists. The donor-from-another-skill arms (`dcross`, `dnear`, `dfar`)
read about 0.4 overall, which looks like partial transfer. Broken out by
calculator they are bimodal rather than partial: on some calculators every
foreign donor scores 1.00 and on others every one scores 0.00, and which is
which does not track how related the donor is -- `dnear` and `dfar` agree to
0.04 overall.

What it tracks is whether this model needs the document for that calculator.
Where it does not, writing ANY coherent foreign document into the span disrupts
the wrong document already sitting there and the model falls back on knowledge
it already has, which is right. That is a real effect and it is not transfer of
the donor's content. So the transfer question has to be asked on the
calculators where the document is actually load-bearing, and this splits them
by the receiver's own accuracy.
"""

from __future__ import annotations

import collections
import json
import math
import sys


def ci(v):
    m = sum(v) / len(v)
    se = math.sqrt(max(m * (1 - m), 0.0) / len(v))
    return m, max(0.0, m - 1.96 * se), min(1.0, m + 1.96 * se)


def main(paths):
    rows = {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                iid = r.get("instance_id")
                if iid:
                    rows[iid] = {**rows.get(iid, {}), **r}

    by_calc = collections.defaultdict(list)
    for r in rows.values():
        by_calc[r["calculator_id"]].append(r)

    # a calculator is "document-dependent" when the receiver -- a wrong
    # document in the slot -- does not solve its items
    arms = sorted({k[3:] for r in rows.values() for k in r if k.startswith("ok_")})
    base = "self_L8" if any("ok_self_L8" in r for r in rows.values()) else "receiver"
    dep, indep = [], []
    print(f"{'calc':>5} {'n':>3} {'receiver':>9}  " +
          "  ".join(f"{a[:9]:>9}" for a in arms if a not in ("self_L8", "receiver")))
    for c in sorted(by_calc, key=lambda x: int(x) if x.isdigit() else 0):
        rs = by_calc[c]
        b = [bool(r[f"ok_{base}"]) for r in rs if f"ok_{base}" in r]
        bm = sum(b) / len(b) if b else float("nan")
        cells = []
        for a in arms:
            if a in ("self_L8", "receiver"):
                continue
            v = [bool(r[f"ok_{a}"]) for r in rs if f"ok_{a}" in r]
            cells.append(f"{sum(v)/len(v):9.2f}" if v else f"{'--':>9}")
        print(f"{c:>5} {len(rs):>3} {bm:9.2f}  " + "  ".join(cells))
        (dep if bm == 0 else indep).append(c)

    print(f"\ndocument-dependent calculators (receiver = 0): {dep}")
    print(f"the rest: {indep}")
    for label, group in (("document-dependent", dep), ("the rest", indep)):
        if not group:
            continue
        print(f"\n  === {label} ===")
        for a in arms:
            v = [bool(r[f"ok_{a}"]) for c in group for r in by_calc[c]
                 if f"ok_{a}" in r]
            if v:
                m, lo, hi = ci(v)
                print(f"    {a:16s} n={len(v):3d}  {m:.3f}  [{lo:.3f},{hi:.3f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
