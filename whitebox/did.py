#!/usr/bin/env python3
"""
The preregistered double dissociation, as one number with an interval.

HANDOFF-whitebox.md 15.3 predicted that two documents with disjoint content move
different axes of the 2x2: `SKILL.pchem-constants` holds only numbers, so it can
only repair a wrong constant; `SKILL.pchem-procedure` holds only methods, so it
can only repair a wrong relation. The first attempt to check that (12.3i) split
the items each document repaired and read off the proportions. Two things were
wrong with it. The effect it split had never cleared Phase 0, so it was carving
up something nobody had confirmed existed. And a proportion of repaired items is
a coarse readout: with 5 repairs on one side, the axis split is noise.

This script uses the axis margins instead (e0_effect.py --margins):

    m_const = lp(correct) - lp(wrong_const)     differs only in the constant
    m_rel   = lp(correct) - lp(wrong_rel)       differs only in the relation

A margin cancels anything that shifts both options equally, which is what E7
found dominates the residual once any long document is in context (12.3j). So
the margins measure content in a way the gold logprob cannot.

The dissociation is an interaction, so it is one number:

    DiD = (dm_const - dm_rel)|constants  -  (dm_rel - dm_const)|procedure ... no.

    Written out properly, with d denoting "with document minus without":

    lean(doc)  = d m_own(doc) - d m_other(doc)
    DiD        = lean(constants) + lean(procedure)

`lean` is how much a document favours its own axis over the other one, and the
dissociation claims both leans are positive. Summing them gives the interaction
term of the 2x2, and its sign is only interpretable when both parts agree -- a
large positive lean on one side can otherwise mask a negative one on the other,
so both are printed and the verdict requires both.

Items are resampled ONCE per bootstrap draw and every quantity is recomputed
from that same resample. The four deltas share their sampling noise that way,
which is the whole point: the interaction is a difference of differences, and
resampling each part independently would inflate its variance beyond anything
the data implies.

    python did.py results/<run-id>

Reads results/<run-id>/e0-tierB-const/per_item.jsonl and .../e0-tierB-proc/, or
whatever two directories are named with --const and --proc.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import random
import sys


def load_margins(path: pathlib.Path, axis: str):
    """{item_id: (margin_without, margin_with)} for one axis."""
    out = {}
    with io.open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            a = (r.get("no_skill") or {}).get("margins") or {}
            b = (r.get("with_skill") or {}).get("margins") or {}
            if axis in a and axis in b:
                out[r["id"]] = (a[axis], b[axis])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=pathlib.Path)
    ap.add_argument("--const", default="e0-tierB-const")
    ap.add_argument("--proc", default="e0-tierB-proc")
    ap.add_argument("--boot", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    paths = {}
    for tag, name in (("const", args.const), ("proc", args.proc)):
        p = args.run_dir / name / "per_item.jsonl"
        if not p.exists():
            print(f"[FAIL] 缺 {p}")
            print("       先跑带 --margins 的 e0-tierB-const / e0-tierB-proc。")
            return 1
        paths[tag] = p

    data = {}
    for tag in ("const", "proc"):
        for axis in ("wrong_const", "wrong_rel"):
            data[(tag, axis)] = load_margins(paths[tag], axis)

    # The two documents have to be compared on the SAME items, or the two leans
    # have different denominators and their sum is not an interaction term.
    ids = set.intersection(*(set(v) for v in data.values()))
    if not ids:
        print("[FAIL] 两份产物里没有共同的题 —— 它们不是在同一批题上跑的,"
              "双重差分没有定义。")
        return 1
    ids = sorted(ids)
    n = len(ids)
    for k, v in data.items():
        if len(v) != n:
            print(f"  (注意) {k[0]}/{k[1]} 有 {len(v)} 题,取交集后用 {n} 题")

    def leans(sample):
        """(lean_const, lean_proc, DiD) on one resample of the item ids."""
        def delta(tag, axis):
            m = data[(tag, axis)]
            return sum(m[i][1] - m[i][0] for i in sample) / len(sample)
        lc = delta("const", "wrong_const") - delta("const", "wrong_rel")
        lp = delta("proc", "wrong_rel") - delta("proc", "wrong_const")
        return lc, lp, lc + lp

    pt = leans(ids)
    rng = random.Random(args.seed)
    draws = [leans([ids[rng.randrange(n)] for _ in range(n)])
             for _ in range(args.boot)]

    def ci(idx):
        v = sorted(d[idx] for d in draws)
        return v[int(0.025 * len(v))], v[min(len(v) - 1, int(0.975 * len(v)))]

    print()
    print("=" * 68)
    print(f"  双重分离（轴间距）   n={n} 题   {args.boot} 次配对 bootstrap")
    print("=" * 68)
    labels = ["constants 偏向常数轴的程度", "procedure 偏向关系式轴的程度",
              "双重差分 DiD"]
    lo_hi = [ci(i) for i in range(3)]
    for lab, v, (lo, hi) in zip(labels, pt, lo_hi):
        tag = "CI 不含 0" if (lo > 0 or hi < 0) else "CI 含 0"
        print(f"  {lab:<30} {v:+.4f}   CI95 [{lo:+.4f}, {hi:+.4f}]   {tag}")

    both_lean = pt[0] > 0 and pt[1] > 0
    lo_did, hi_did = lo_hi[2]
    lo_c, hi_c = lo_hi[0]
    lo_p, hi_p = lo_hi[1]

    print()
    print("  判据（跑之前写死的,见 HANDOFF 12.3l）：")
    print("    两份文档各自的 lean 都 > 0,且两个 CI 都不含 0 —— 才叫双重分离成立。")
    print("    DiD 的 CI 不含 0 只是必要条件：一边很大另一边为负时它照样为正。")
    print()
    if both_lean and lo_c > 0 and lo_p > 0:
        print("  ==> 双重分离**成立**。两份内容互斥的文档各自只动自己那个轴,")
        print("      而且是在通用成分被间距消掉之后。E2 的 example/principle")
        print("      预注册对照现在有前提了。")
    elif lo_did > 0 and not (lo_c > 0 and lo_p > 0):
        print("  ==> DiD 显著但**分离不成立**：只有一份文档站住了。报这个不对称,")
        print("      不要报「分离」——另一份动的是别人的轴,或者根本没动。")
    elif not both_lean:
        print("  ==> **方向上就不成立**：至少一份文档更动的是别人的轴。这直接反驳")
        print("      「内容不同的文档走不同机制」,而那正是 E2 预注册预测的前提。")
    else:
        print("  ==> 方向对,但 CI 压不住 0 —— 功效不够。这批题是整个题池,")
        print("      唯一诚实的杠杆是多生成题、并把题变难（HANDOFF 15.6）。")
        print("      **不要在同一批题上重测。**")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
