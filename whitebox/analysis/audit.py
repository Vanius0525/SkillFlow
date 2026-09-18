#!/usr/bin/env python3
"""Recompute the paper's load-bearing numbers from the raw run files.

Every number in the paper was read off a printed table at some point. This
recomputes them from the jsonl, independently of the code that printed them, and
prints CLAIM vs RECOMPUTED side by side. A mismatch is either a transcription
error into the paper or a bug in the reporting path; both matter and neither is
visible by rereading the draft.

    python whitebox/analysis/audit.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
E14 = ROOT / "whitebox/results/20260910-e14/e14-tierA-mc-1.7B-fp32"
OLD = ROOT / "whitebox/results/20260909-130000"
P8 = ROOT / "howskill/results/p8-wb/fetched/shared"
# Results now arrive per host, because a shared-disk file was once overwritten by
# a two-row smoke run from another box and the mistake was invisible until this
# script compared it against the paper. Checks below glob both roots.
BYHOST = ROOT / "howskill/results/p8-wb/fetched/by-host"

fails = []


def check(label, claimed, got, tol=0.005):
    ok = got is not None and abs(claimed - got) <= tol
    if not ok:
        fails.append(label)
    print(f"  {'OK ' if ok else 'XX '} {label:48s} paper {claimed:>7.3f}   "
          f"recomputed {got if got is None else round(got, 3)}")


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def frac(rows, key, cell=None):
    v = [r.get(key) for r in rows
         if (cell is None or r.get("cell") == cell) and key in r]
    v = [x for x in v if x is not None]
    return sum(bool(x) for x in v) / len(v) if v else None


print("=== Table 3: decomposition, Tier A MC 1.7B fp32, n=200, rescued cell ===")
if (E14 / "layer_26.jsonl").exists():
    r26 = load_jsonl(E14 / "layer_26.jsonl")
    check("L26 replace_real (R)", 1.000, frac(r26, "ok_replace_real", "R"))
    check("L26 add_d alpha=1 (R)", 0.812, frac(r26, "ok_add_d_a1", "R"))
    check("L26 add_g (R)", 0.062, frac(r26, "ok_add_g", "R"))
    check("L26 add_d alpha=0.5 (R)", 0.312, frac(r26, "ok_add_d_a0.5", "R"))
    check("L26 add_d alpha=2 (R)", 0.979, frac(r26, "ok_add_d_a2", "R"))
    check("L26 add_dbar (R)", 0.062, frac(r26, "ok_add_dbar", "R"))
    print("  four-cell fidelity of replace_real (paper: 1.000/0.000/1.000/0.000)")
    for cell, claimed in (("R", 1.000), ("F", 0.000), ("K", 1.000), ("B", 0.000)):
        check(f"    cell {cell}", claimed, frac(r26, "ok_replace_real", cell))
    print("  four-cell fidelity of add_d (paper: 0.812/0.112/1.000/0.125)")
    for cell, claimed in (("R", 0.812), ("F", 0.112), ("K", 1.000), ("B", 0.125)):
        check(f"    cell {cell}", claimed, frac(r26, "ok_add_d_a1", cell))
    n = collections.Counter(r["cell"] for r in r26)
    print(f"  cell sizes recomputed: {dict(n)}  (paper: R=48 F=116 K=12 B=24)")
else:
    print("  (run dir not present locally)")

print("\n=== Table 7: aggregate logprob by cell, Tier A E2, n=39, layer 21 ===")
p = OLD / "e2-tierA/per_layer.jsonl"
if p.exists():
    layers = load_jsonl(p)
    rec = next(x for x in layers if x["layer"] == 21)
    rows = rec["rows"]
    cell = {}
    base = next(x for x in layers if x["layer"] == 0)["rows"]
    for r in base:
        cell[r["id"]] = {(False, True): "R", (False, False): "F",
                         (True, True): "K", (True, False): "B"}[
            (bool(r["ok_no"]), bool(r["ok_yes"]))]
    import statistics as st
    agg_gap = (st.mean(r["lp_mean"] for r in rows)
               - st.mean(r["lp_real"] for r in rows))
    check("aggregate mean - real (nats)", 2.747, agg_gap, tol=0.02)
    for c, claimed_gap, claimed_share in (("R", -2.506, -0.835),
                                          ("F", 5.907, 2.575),
                                          ("B", 8.455, 1.084)):
        sub = [r for r in rows if cell[r["id"]] == c]
        g = (st.mean(r["lp_mean"] for r in sub)
             - st.mean(r["lp_real"] for r in sub))
        check(f"  cell {c} gap", claimed_gap, g, tol=0.02)
        check(f"  cell {c} contribution", claimed_share,
              len(sub) / len(rows) * g, tol=0.02)
else:
    print("  (e2 run not present locally)")

print("\n=== real-skill knockout, n=40 ===")
p = P8 / "knockout-span.jsonl"
if p.exists():
    rows = load_jsonl(p)
    check("with skill", 0.550, frac(rows, "ok_with"))
    check("without skill", 0.025, frac(rows, "ok_without"))
    check("skill span masked", 0.075, frac(rows, "ok_mask_skill"))
    check("length-matched task span masked", 0.150, frac(rows, "ok_mask_ctrl"))
else:
    print("  (knockout not present locally)")

print("\n=== real-skill question-span transplant (matched receiver) ===")
ps = sorted(P8.glob("spanpatch-matched-*.jsonl"))
if ps:
    seen = {}
    for q in ps:
        for r in load_jsonl(q):
            seen[(q.name, r["instance_id"])] = r
    rows = list(seen.values())
    check("receiver baseline", 0.170, frac(rows, "ok_receiver"), tol=0.02)
    check("no document", 0.030, frac(rows, "ok_none"), tol=0.02)
    for L in (10, 16, 22):
        a, b = frac(rows, f"ok_real_L{L}"), frac(rows, f"ok_self_L{L}")
        if a is not None:
            print(f"  -- L{L}: real {a:.3f}  self {b if b is None else round(b,3)}"
                  f"  (paper: they coincide)")
else:
    print("  (span transplants not present locally)")

print("\n=== document-span transplant, merged shards ===")
ss = sorted(P8.glob("**/skillspan-*.jsonl")) + sorted(BYHOST.glob("**/skillspan-*.jsonl"))
if ss:
    seen = {}
    for q in ss:
        for r in load_jsonl(q):
            seen[r["instance_id"]] = {**seen.get(r["instance_id"], {}), **r}
    rows = list(seen.values())
    print(f"  {len(rows)} instances over {len(ss)} shards")
    check("gold in context", 0.950, frac(rows, "ok_gold_in_context"))
    check("no document", 0.025, frac(rows, "ok_none"))
    check("receiver (filler document)", 0.175, frac(rows, "ok_receiver"))
    for L, want in ((0, 0.950), (8, 1.000), (12, 0.875), (16, 0.400),
                    (24, 0.175), (30, 0.150)):
        check(f"real, layer {L}", want, frac(rows, f"ok_real_L{L}"))
    check("every layer at once", 0.950, frac(rows, "ok_real_alllayers"))
else:
    print("  (document-span shards not present locally)")

print("\n=== span-vector battery, layer 8, the receiver these were run with ===")
# geometry runs share the file naming but carry no `ok_` keys, so they would
# otherwise satisfy the `or` and leave the battery unchecked
# doc-first and doc-last are different experiments with different receivers
# (0.15 against 0.28); merging them made this script report a mismatch against
# its own expectation, which is the check working on itself
# `big-*` runs a different item set (20 calculators, not 10); merging it in
# changes which calculators survive the restriction and mixes two arm sets, so
# it is checked on its own below rather than pooled
bv = [q for q in sorted(BYHOST.glob("**/spanvec-fs-*.jsonl"))
      if "geom" not in q.name and "-dl" not in q.name
      and "big" not in q.name] or (
    sorted(BYHOST.glob("**/spanvec-dose.jsonl"))
    + sorted(BYHOST.glob("**/spanvec-ctrl.jsonl"))
    + sorted(BYHOST.glob("**/spanvec-parts.jsonl")))
if bv:
    seen = {}
    for q in bv:
        for r in load_jsonl(q):
            seen[r["instance_id"]] = {**seen.get(r["instance_id"], {}), **r}
    rows = list(seen.values())
    have = sorted({k[3:] for r in rows for k in r if k.startswith("ok_")})
    fmts = {r.get("format", "?") for r in rows}
    print(f"  {len(rows)} instances, formats {sorted(fmts)}, "
          f"arms present: {', '.join(have)}")
    if len(fmts) > 1:
        fails.append("span-vector shards mix prompt formats")
    for arm in ("self", "real", "a0.5", "a2", "realm", "dcross", "dshuf",
                "drand", "dall", "head", "tail", "normrecv", "dnear", "dfar"):
        v = frac(rows, f"ok_{arm}_L8")
        if v is not None:
            print(f"    {arm:10s} {v:.3f}")
    recv = frac(rows, "ok_receiver")
    sf = frac(rows, "ok_self_L8")
    if recv is not None and sf is not None:
        check("the no-op arm equals the receiver", recv, sf, tol=0.03)

    # The paper reports these arms on the calculators the receiver never
    # solves, because on the others any disruption of the wrong document --
    # noise included -- lets the model fall back on what it already knows.
    import collections as _c
    acc = _c.defaultdict(list)
    for r in rows:
        if "ok_receiver" in r:
            acc[r["calculator_id"]].append(bool(r["ok_receiver"]))
    keep = {c for c, v in acc.items() if sum(v) == 0}
    sub = [r for r in rows if r["calculator_id"] in keep]
    if sub:
        fl = frac(sub, "ok_receiver")
        tp = frac(sub, "ok_gold_in_context")
        print(f"\n  restricted to {sorted(keep, key=lambda x: int(x))} "
              f"-- n={len(sub)}, receiver {fl:.3f}, gold {tp:.3f}")
        for arm in ("real", "realm", "a0.5", "a2", "dnear", "dfar", "dcross",
                    "dall", "dshuf", "drand", "head", "tail", "normrecv",
                    "q1", "self"):
            v = frac(sub, f"ok_{arm}_L8")
            if v is not None:
                print(f"    {arm:10s} acc {v:.3f}   rho "
                      f"{(v - fl) / max(tp - fl, 1e-9):+.2f}")
        check("the restricted receiver is zero", 0.0, fl, tol=1e-9)
        check("norm-matched noise recovers nothing",
              0.0, frac(sub, "ok_drand_L8") or 0.0, tol=1e-9)

else:
    print("  (span-vector runs not present locally)")

print("\n=== the same three arms on twice as many calculators ===")
big = sorted(BYHOST.glob("**/spanvec-fs-big-*.jsonl"))
if big:
    seen = {}
    for q in big:
        for r in load_jsonl(q):
            seen[r["instance_id"]] = {**seen.get(r["instance_id"], {}), **r}
    rows = list(seen.values())
    import collections as _c2
    acc = _c2.defaultdict(list)
    for r in rows:
        if "ok_receiver" in r:
            acc[r["calculator_id"]].append(bool(r["ok_receiver"]))
    keep = {c for c, v in acc.items() if sum(v) == 0}
    sub = [r for r in rows if r["calculator_id"] in keep]
    fl = frac(sub, "ok_receiver")
    tp = frac(sub, "ok_gold_in_context")
    print(f"  {len(rows)} instances, {len(keep)} calculators kept, n={len(sub)}, "
          f"receiver {fl:.3f}, gold {tp:.3f}")
    for arm in ("real", "realm", "dcross", "drand", "self"):
        v = frac(sub, f"ok_{arm}_L8")
        if v is not None:
            print(f"    {arm:8s} acc {v:.3f}   rho "
                  f"{(v - fl) / max(tp - fl, 1e-9):+.2f}")
    # the instrument's own noise is bounded by the no-op arm; the paper quotes
    # about one item in twenty, so anything past 0.10 is a real problem
    check("the no-op arm stays within the instrument's noise",
          0.0, frac(sub, "ok_self_L8") or 0.0, tol=0.10)
    check("noise stays within the instrument's noise",
          0.0, frac(sub, "ok_drand_L8") or 0.0, tol=0.10)
else:
    print("  (the larger-n replication is not present locally)")


print("\n=== Tier A windows on Qwen3-8B (Table: windows) ===")
TA = ROOT / "whitebox/results/fetched"
# These four runs lived only on the cluster's shared disk until the instances
# were recycled; they are the one block of numbers in the paper that could not
# be recomputed locally, so they were copied back and are checked here.
want = {"e10-tierA-mc-8B":  (0.233, 0.575, 0.550),
        "e10-tierA-num-8B": (0.008, 0.408, 0.467),
        "e12-tierA-mc-8B":  (0.233, 0.517, 0.550),
        "e12-tierA-num-8B": (0.008, 0.025, 0.467)}
found = 0
for q in sorted(TA.glob("**/summary.json")):
    name = q.parent.name
    if name not in want:
        continue
    found += 1
    s_ = json.loads(q.read_text(encoding="utf-8"))
    recv, peak, donor = want[name]
    ar = s_.get("acc_real") or []
    check(f"{name}: receiver", recv, s_.get("acc_lo"), tol=0.01)
    check(f"{name}: peak", peak, max(ar) if ar else None, tol=0.01)
    check(f"{name}: donor", donor, s_.get("acc_hi"), tol=0.01)
if not found:
    print("  (the Tier A 8B runs are not present locally)")

print("\n=== the instrument's own noise floor (Setup) ===")
# `self` writes the receiver's own span states back over themselves, so it is a
# bit-for-bit identity and must equal `receiver`. It does not, and the size of
# the disagreement is the smallest effect this setting can resolve.
#
# Pre-fix runs are read from the snapshot taken before the 2026-09-13 relaunch,
# not from by-host: no pre-fix run can be produced again, and by-host is being
# overwritten by post-fix reruns under the SAME tags (rank40-l8, big40-depth),
# which the old `name.startswith("fixmask-")` test counted as pre-fix.
# Two shards also sit under two hosts (spanpatch-matched-wb2 identical,
# -wb3 a 51-row prefix of the 72-row file); the old glob counted both.
PREFIX_SNAP = ROOT / "howskill/results/p8-wb/snapshots/fetched-20260913_2324/by-host"
RELAUNCHED = {"rank40-l8", "ko-8b-fast", "big40-depth"}   # tags relaunch.sh reran


def is_postfix_tag(name):
    return name.startswith("fixmask-") or name[:-len(".jsonl")] in RELAUNCHED


def dedup_shards(paths):
    """One file per basename: the longest, after checking the rest are prefixes."""
    by = collections.defaultdict(list)
    for q in paths:
        by[q.name].append((q, open(q, encoding="utf-8").read().splitlines()))
    out = []
    for name, v in sorted(by.items()):
        v.sort(key=lambda t: -len(t[1]))
        for q, lines in v[1:]:
            if lines != v[0][1][:len(lines)]:
                raise SystemExit(f"{q} and {v[0][0]} share a name but not rows")
        out.append(v[0][0])
    return out


_pre = [q for q in dedup_shards(PREFIX_SNAP.glob("*/*.jsonl"))
        if not q.name.startswith("fixmask-") and q.name != "rank40-l8.jsonl"
        and q.name != "ko-8b-fast.jsonl"]
# big40-depth in the snapshot IS pre-fix (25/240 null-arm flips); the other two
# relaunched tags hold only post-fix stubs there.
_n = _same = _up = _dn = 0
_cellF_n = _cellF_bad = 0
_bymodel = collections.defaultdict(lambda: [0, 0])      # model -> [n, flips]
for q in _pre:
    try:
        rs = load_jsonl(q)
    except Exception:
        continue
    if not rs:
        continue
    for k in [k for k in rs[0] if k.startswith("ok_self_L")]:
        for r in rs:
            if k not in r or "ok_receiver" not in r:
                continue
            a, b = bool(r["ok_receiver"]), bool(r[k])
            _n += 1
            _same += (a == b)
            # rows without a model field are dispatch.sh's default, Qwen3-8B
            m = r.get("model", "Qwen3-8B")
            _bymodel[m][0] += 1
            _bymodel[m][1] += (a != b)
            if a != b:
                _up += b
                _dn += not b
            if r.get("cell") == "F":
                _cellF_n += 1
                _cellF_bad += (a != b)
check("null arm agrees with the receiver (pre-fix runs)", 0.973,
      _same / _n if _n else None, tol=0.01)
_8n, _8f = _bymodel["Qwen3-8B"]
_sn = sum(v[0] for m, v in _bymodel.items() if m != "Qwen3-8B")
_sf = sum(v[1] for m, v in _bymodel.items() if m != "Qwen3-8B")
check("pre-fix null arm agreement, Qwen3-8B", 0.939, _8n and 1 - _8f / _8n,
      tol=0.002)
check("pre-fix null-arm flips, Qwen3-8B (count)", 108, _8f, tol=0)
check("pre-fix null-arm observations, Qwen3-8B", 1766, _8n, tol=0)
check("pre-fix null-arm flip rate, 0.6B and 1.7B", 0.007, _sn and _sf / _sn,
      tol=0.001)
for m, want in (("Qwen3-0.6B", 0.006), ("Qwen3-1.7B", 0.008)):
    n, f = _bymodel[m]
    check(f"pre-fix null-arm flip rate, {m}", want, n and f / n, tol=0.001)
check("pre-fix null-arm observations, Qwen3-0.6B", 1696, _bymodel["Qwen3-0.6B"][0],
      tol=0)
print(f"    by model: " + ", ".join(f"{m} {f}/{n}" for m, (n, f)
                                     in sorted(_bymodel.items())))
# "80/80 across two reruns": the two complete post-fix reruns, frozen
_ex = _exn = 0
for q in (PREFIX_SNAP / "wb/fixmask-base.jsonl", PREFIX_SNAP / "wb3/fixmask-cellF.jsonl"):
    for r in load_jsonl(q):
        _exn += 1
        _ex += bool(r["ok_self_L8"]) == bool(r["ok_receiver"])
check("post-fix null arm exact, items (of 80)", 80, _ex, tol=0)
check("post-fix null arm, items in the two reruns", 80, _exn, tol=0)
# after capture_ids was made to pass an explicit attention mask the null arm is
# an exact identity: fixmask-* and the reruns of the relaunched tags are post-fix.
# big40-depth in by-host is still the pre-fix file until its rerun overtakes it.
_pn = _ps = 0
_post = [q for q in sorted(BYHOST.glob("*/*.jsonl")) if is_postfix_tag(q.name)]
_old_b40 = PREFIX_SNAP / "hsw2/big40-depth.jsonl"
_post = [q for q in _post if not (q.name == "big40-depth.jsonl" and _old_b40.exists()
                                  and q.read_bytes() == _old_b40.read_bytes())]
for q in _post:
    rs = load_jsonl(q)
    if not rs:
        continue
    for k in [k for k in rs[0] if k.startswith("ok_self_L")]:
        for r in rs:
            if k in r and "ok_receiver" in r:
                _pn += 1
                _ps += bool(r[k]) == bool(r["ok_receiver"])
if _pn:
    check("null arm agrees with the receiver (post-fix)", 1.000,
          _ps / _pn, tol=0.001)
    print(f"    post-fix: {_ps}/{_pn}")
check("the disagreement is symmetric (share upward)", 0.43,
      _up / (_up + _dn) if (_up + _dn) else None, tol=0.10)
check("pre-fix noise floor on the persistent-failure cell", 0.16,
      _cellF_bad / _cellF_n if _cellF_n else None, tol=0.03)
print(f"    {_n} paired observations, {_up} up, {_dn} down, "
      f"cell F {_cellF_bad}/{_cellF_n}")

def restrict(rows):
    """The paper's rule: keep the calculators whose receiver never solves.

    Reading these files per INSTANCE instead (drop items whose own `none` or
    `receiver` happened to succeed) keeps more items and different ones, and it
    moved the layer-12 rank curve from 0.00 to 0.03 and the layer-16 transplant
    from 0.06 to 0.27. Same files, same arms, different split. Every number in
    the paper uses this one.
    """
    bc = collections.defaultdict(list)
    for r in rows:
        bc[r["calculator_id"]].append(r)
    dep = {c for c, rs in bc.items() if not any(x.get("ok_receiver")
                                                for x in rs)}
    return [r for r in rows if r["calculator_id"] in dep]


print("\n=== rank truncation at depth, and the cross-layer converse ===")
_rk = {}
for nm in ("rank-l12-df", "rank-l16-df", "rank-l16-dl", "xfer-8to16"):
    rows = []
    for q in sorted(BYHOST.glob(f"*/{nm}.jsonl")):
        rows += load_jsonl(q)
    if rows:
        _rk[nm] = restrict(rows)
if _rk:
    for nm, sel in _rk.items():
        print(f"    {nm}: n={len(sel)} over "
              f"{len({r['calculator_id'] for r in sel})} calculators")
    s12 = _rk.get("rank-l12-df", [])
    if s12:
        check("layer 12: full-rank transplant", 1.000, frac(s12, "ok_real_L12"))
        check("layer 12: k=16", 0.000, frac(s12, "ok_rank16_L12"))
        check("layer 12: k=128", 0.625, frac(s12, "ok_rank128_L12"), tol=0.02)
    sdl = _rk.get("rank-l16-dl", [])
    if sdl:
        check("layer 16 doc-last: full-rank", 0.786, frac(sdl, "ok_real_L16"),
              tol=0.02)
        check("layer 16 doc-last: k=16", 0.250, frac(sdl, "ok_rank16_L16"),
              tol=0.02)
        check("layer 16 doc-last: k=128", 0.714,
              frac(sdl, "ok_rank128_L16"), tol=0.02)
    sdf = _rk.get("rank-l16-df", [])
    if sdf:
        check("layer 16 doc-first: full-rank is already the floor", 0.062,
              frac(sdf, "ok_real_L16"), tol=0.02)
    sx = _rk.get("xfer-8to16", [])
    if sx:
        check("cross-layer donor into layer 16", 0.000,
              frac(sx, "ok_xfer_L16"))
        check("same-layer donor at layer 16", 0.062, frac(sx, "ok_real_L16"),
              tol=0.02)
else:
    print("  (the rank-at-depth runs are not present locally)")

print("\n=== the battery on forty calculators, pre-fix shards (sec:battery) ===")
# Table 2 is now read from the post-fix rerun (fixmask-big40, checked below). The
# pre-fix shards are frozen in the snapshot and read only for what the paper still
# cites from them: the split, and the same-family donor, which was not rerun.
# Globbing big40-* in by-host would also pull in the post-fix big40-depth, whose
# ok_real_L8 silently overwrote the battery's own.
_b = {}
for q in [q for nm in ("big40-base", "big40-realm", "big40-ctrl", "big40-noise")
          for q in sorted(PREFIX_SNAP.glob(f"*/{nm}.jsonl"))]:
    for r in load_jsonl(q):
        _b.setdefault(r["instance_id"], {}).update(
            {k: v for k, v in r.items() if k.startswith("ok_")}
            | {"calculator_id": r["calculator_id"]})
if _b:
    bycalc = collections.defaultdict(list)
    for r in _b.values():
        bycalc[r["calculator_id"]].append(r)
    dep = {c for c, rs in bycalc.items()
           if not any(x.get("ok_receiver") for x in rs)}
    # the same rule tables.py uses: the restriction is per CALCULATOR and
    # conditions only on the receiver, never on an instance's own outcome
    keep = [r for r in _b.values() if r["calculator_id"] in dep]
    print(f"    {len(dep)} of {len(bycalc)} calculators depend on the document; "
          f"{len(keep)} items")
    g = frac(keep, "ok_gold_in_context")
    rho = lambda k: ((frac(keep, k) or 0.0) - 0.0) / g
    check("forty calculators: dependent calculators", 15.0, float(len(dep)),
          tol=0.5)
    check("forty calculators: items", 60.0, float(len(keep)), tol=1.5)
    # the same-family donor is now read from its post-fix rerun (below)
else:
    print("  (the forty-calculator runs are not present locally)")

print("\n=== massive activations own the spectrum at layer 16 (sec:depth) ===")
_p = []
for q in sorted(BYHOST.glob("*/prdiag-8b-df.jsonl")):
    _p += load_jsonl(q)
if _p:
    per = collections.defaultdict(list)
    for r in _p:
        for gl in r.get("geom", []):
            per[gl["layer"]].append(gl)
    md = lambda L, k: sorted(x[k] for x in per[L])[len(per[L]) // 2]
    print(f"    {len(_p)} instances")
    check("layer 14: PR as usually computed", 55.4, md(14, "pr_hg"), tol=3.0)
    check("layer 16: PR as usually computed", 1.0, md(16, "pr_hg"), tol=0.2)
    check("layer 16: PR, four loud positions dropped", 65.9,
          md(16, "hg_pr_droppos"), tol=4.0)
    check("layer 16: max/median position norm", 149.6,
          md(16, "hg_norm_ratio"), tol=20.0)
    check("layer 14: max/median position norm", 1.6,
          md(14, "hg_norm_ratio"), tol=0.3)
    # "one token in 34 of 40 documents ... 99 to 180 times ... the same two in
    # all 34": the paper said "each document" and "100 to 164" until 2026-09-14
    loud = [g for g in per[16] if g["hg_norm_ratio"] > 20]
    check("layer 16: documents with a massive activation", 34, len(loud), tol=0)
    check("layer 16: smallest loud ratio", 99.4,
          min(g["hg_norm_ratio"] for g in loud), tol=0.5)
    check("layer 16: largest loud ratio", 179.8,
          max(g["hg_norm_ratio"] for g in loud), tol=0.5)
    check("layer 16: loud documents on dims {676, 2276}", len(loud),
          sum(set(g["hg_top_dim"][:2]) == {676, 2276} for g in loud), tol=0)
    check("layer 16: top-8 variance share (median)", 0.977,
          md(16, "hg_top_dim_share"), tol=0.001)
    check("layer 14: top-8 variance share (median)", 0.054,
          md(14, "hg_top_dim_share"), tol=0.001)
    check("layer 16: PR, unit-normalised", 67.6, md(16, "hg_pr_unit"), tol=0.5)
    check("layer 16: PR, top eight dims dropped", 26.9,
          md(16, "hg_pr_dropdim"), tol=0.5)
else:
    print("  (the participation-ratio diagnostic is not present locally)")

print("\n=== doc-first span states across a skill's instances (sec:whose) ===")
# "bit for bit at equal prompt length, cosine >= 0.997 otherwise". The paper
# said "maximum absolute difference 0 at every layer"; on disk only the pairs
# of equal prompt length are exactly zero.
_gf = []
for q in sorted(PREFIX_SNAP.glob("*/spanvec-fs-geomf.jsonl")):
    _gf += load_jsonl(q)
if _gf:
    _cs = [g["cos_d_same"] for r in _gf for g in r.get("geom", [])
           if "cos_d_same" in g]
    check("doc-first: minimum cosine between instances", 0.997, min(_cs),
          tol=0.0005)
    _grp = collections.defaultdict(list)
    for r in _gf:
        _grp[r["calculator_id"]].append(r)
    _eq = _eq0 = 0
    for rs in _grp.values():
        for r in rs:
            o = [x for x in rs if x["instance_id"] != r["instance_id"]]
            if o and o[0]["n_prompt"] == r["n_prompt"]:
                for g in r["geom"]:
                    _eq += 1
                    _eq0 += g["maxabs_d_same"] == 0.0
    check("doc-first: equal-length pairs exactly identical", 1.0,
          _eq0 / _eq if _eq else None, tol=0)
else:
    print("  (the doc-first geometry run is not present locally)")

print("\n=== the behavioural table is three arms on ONE item set ===")
# The no-skill arm once held 839 of 1,100 rows -- the platform reclaimed the box
# mid-run -- and the missing 261 were thirteen whole calculators, not a random
# sample, so the table compared arms over different calculator sets. The arms
# are equal-n now and this check is here so that cannot recur silently.
_beh = ROOT / "whitebox/results/p8-step"
_arms = ["p8-gold_no_tool", "p8-ctrl_neutral_no_tool", "p8-no_skill"]
_counts = {}
for _a in _arms:
    q = _beh / f"{_a}.jsonl"
    if q.exists():
        _counts[_a] = sum(1 for _ in open(q, encoding="utf-8"))
if len(_counts) == 3:
    print(f"    {_counts}")
    check("the three behavioural arms have equal n", 0.0,
          float(max(_counts.values()) - min(_counts.values())), tol=0.5)
    check("the behavioural arms are 1,100 items", 1100.0,
          float(min(_counts.values())), tol=0.5)
else:
    print("  (the behavioural runs live on the shared disk, not checked here)")

print("\n=== the span stops being a channel at layer 16 (sec:depth) ===")
_w = []
for q in sorted(BYHOST.glob("*/window-16.jsonl")):
    _w += load_jsonl(q)
if _w:
    bc = collections.defaultdict(list)
    for r in _w:
        bc[r["calculator_id"]].append(r)
    dep = {c for c, rs in bc.items() if not any(x.get("ok_receiver")
                                                for x in rs)}
    kp = [r for r in _w if r["calculator_id"] in dep
          and not r.get("ok_none") and not r.get("ok_receiver")]
    print(f"    n={len(kp)} restricted over {len(dep)} calculators")
    check("window 12-15 (four layers)", 0.96, frac(kp, "ok_real_w12_15"),
          tol=0.02)
    check("window 16-35 (twenty layers)", 0.04, frac(kp, "ok_real_w16_35"),
          tol=0.02)
    check("window 14-19 straddles the boundary", 0.44,
          frac(kp, "ok_real_w14_19"), tol=0.03)
    check("single layer 16", 0.07, frac(kp, "ok_real_L16"), tol=0.02)
    check("null arm, restricted", 0.000, frac(kp, "ok_self_L16"))
else:
    print("  (the layer-window run is not present locally)")

print("\n=== the dose threshold, undoctored arms only (sec:battery) ===")
_d = []
for q in sorted(BYHOST.glob("*/dose-raw.jsonl")):
    _d += load_jsonl(q)
_d = [r for r in _d if not r.get("ok_receiver") and not r.get("ok_none")]
if _d:
    print(f"    n={len(_d)} restricted")
    for a, want in (("0.4", 0.167), ("0.5", 0.033), ("0.55", 0.167),
                    ("0.7", 0.967)):
        check(f"alpha={a}", want, frac(_d, f"ok_a{a}_L8"), tol=0.02)
    check("alpha=1 (real)", 1.000, frac(_d, "ok_real_L8"), tol=0.02)
else:
    print("  (the undoctored dose sweep is not present locally)")

print("\n=== the rank knee on Qwen3-0.6B, dense grid (sec:ladder) ===")
_f = []
for q in sorted(BYHOST.glob("*/lad06-fine.jsonl")):
    _f += load_jsonl(q)
_f = [r for r in _f if not r.get("ok_receiver") and not r.get("ok_none")]
if _f:
    _g = frac(_f, "ok_gold_in_context")
    print(f"    n={len(_f)} restricted, gold {_g:.3f}")
    for k, want in (("24", 0.04), ("32", 0.22), ("40", 0.21), ("48", 0.64),
                    ("56", 0.46), ("64", 0.85)):
        check(f"0.6B rank{k}", want, frac(_f, f"ok_rank{k}_L6") / _g, tol=0.03)
    check("0.6B full transplant", 0.93, frac(_f, "ok_real_L6") / _g, tol=0.03)
else:
    print("  (the dense 0.6B grid is not present locally)")

print("\n=== the with-document baseline must agree across scripts ===")
# The knockout script and the span script measure the same quantity -- accuracy
# with the gold document in the prompt, on the rescued cell -- through different
# code. They disagreed by 45 points for a week because wb_knockout defaults to
# --max-new 400 and the span runs use 900. Cross-check them.
_k = []
for q in list(BYHOST.glob("*/ko-8b-fast.jsonl")) + list(BYHOST.glob("*/ko-8b.jsonl")):
    _k += load_jsonl(q)
if _k:
    _w = frac(_k, "ok_with")
    print(f"    knockout with-document, n={len(_k)}: {_w:.3f}")
    check("knockout with-document matches the span runs' gold", 0.95, _w,
          tol=0.08)
else:
    print("  (the re-run knockout is not present locally yet)")

print("\n=== the layer-8 rank curve, the paper's headline (sec:rank) ===")
_r8 = []
for q in sorted(BYHOST.glob("*/spanvec-rank-*.jsonl")):
    _r8 += load_jsonl(q)
if _r8:
    sel = restrict(_r8)
    g = frac(sel, "ok_gold_in_context")
    f = frac(sel, "ok_receiver")
    rho = lambda k: ((frac(sel, k) or 0.0) - f) / max(g - f, 1e-9)
    print(f"    n={len(sel)} over {len({r['calculator_id'] for r in sel})} "
          f"calculators, gold {g:.3f}, receiver {f:.3f}")
    for k, want in (("1", 0.11), ("2", 0.06), ("4", 0.06), ("8", 0.11),
                    ("16", 0.11), ("32", 0.33), ("64", 0.72), ("128", 0.94)):
        v = rho(f"ok_rank{k}_L8")
        check(f"layer 8: k={k}", want, v, tol=0.03)
    for k, want in (("16lo", 0.00), ("64lo", 0.06)):
        check(f"layer 8: bottom {k[:-2]}", want, rho(f"ok_rank{k}_L8"),
              tol=0.03)
else:
    print("  (the layer-8 rank runs are not present locally)")

print("\n=== where inside the document the effect sits (sec:whose) ===")
_q = []
for q in sorted(BYHOST.glob("*/spanvec-fs-quarters.jsonl")):
    _q += load_jsonl(q)
# the quarter shard carries no baselines of its own; merge the baseline shard
# that ran the same items, then apply the same per-calculator restriction
_qb = {}
for q in (sorted(BYHOST.glob("*/spanvec-fs-quarters.jsonl"))
          + sorted(BYHOST.glob("*/spanvec-fs-base.jsonl"))):
    for r in load_jsonl(q):
        t = _qb.setdefault(r["instance_id"], {"calculator_id":
                                              r["calculator_id"]})
        t.update({k: bool(v) for k, v in r.items() if k.startswith("ok_")})
if _qb:
    sel = restrict(list(_qb.values()))
    g = frac(sel, "ok_gold_in_context")
    f = frac(sel, "ok_receiver")
    rho = lambda k: ((frac(sel, k) or 0.0) - f) / max(g - f, 1e-9)
    print(f"    n={len(sel)} over {len({r['calculator_id'] for r in sel})} "
          f"calculators")
    # q0 description, q1 formulas, q2 tool signatures, q3 worked example --
    # the names come from decoding the TOKEN split, not from reading the file
    for k, want in (("q0", 0.28), ("q1", 0.83), ("q2", 0.11), ("q3", 0.44)):
        check(f"quarter {k}", want, rho(f"ok_{k}_L8"), tol=0.03)
else:
    print("  (the quarter sweep is not present locally)")

print("\n=== the results that arrived after the instrument fix ===")
for nm, checks in (
        ("fixmask-big40", (("ok_real_L8", 0.87), ("ok_realm_L8", 0.73),
                           ("ok_a0.5_L8", 0.06), ("ok_dfar_L8", 0.06),
                           ("ok_dshuf_L8", 0.08), ("ok_drand_L8", 0.10),
                           ("ok_self_L8", 0.00))),
        # rerun after the fix, complete (160/160); paper updated 2026-09-14
        ("rank40-l8", (("ok_real_L8", 0.87), ("ok_rank4_L8", 0.13),
                       ("ok_rank16_L8", 0.06), ("ok_rank32_L8", 0.13),
                       ("ok_rank64_L8", 0.54), ("ok_rank128_L8", 0.77),
                       ("ok_rank16lo_L8", 0.06), ("ok_rank64lo_L8", 0.00),
                       ("ok_self_L8", 0.00))),
        # post-fix rank curve, 4 calculators / 16 items (HANDOFF §44.3)
        ("fixmask-rank", (("ok_real_L8", 1.00), ("ok_rank16_L8", 0.00),
                          ("ok_rank32_L8", 0.125), ("ok_rank64_L8", 0.75),
                          ("ok_rank128_L8", 0.875), ("ok_rank64lo_L8", 0.00),
                          ("ok_self_L8", 0.00))),
        # same-family donor, post-fix; defined only for the 20 restricted items
        # whose calculator has a same-family neighbour (frac skips the rest)
        ("fixmask-dnear", (("ok_dnear_L8", 0.06),)),
        ("fixmask-window", (("ok_real_w8_11", 1.00), ("ok_real_w12_15", 0.96),
                            ("ok_real_w14_19", 0.38),
                            ("ok_real_w16_35", 0.11),
                            ("ok_self_L16", 0.00)))):
    rows = []
    for q in sorted(BYHOST.glob(f"*/{nm}.jsonl")):
        rows += load_jsonl(q)
    if not rows:
        print(f"  ({nm} is not present locally)")
        continue
    sel = restrict(rows)
    g = frac(sel, "ok_gold_in_context")
    f = frac(sel, "ok_receiver")
    print(f"    {nm}: n={len(sel)} over "
          f"{len({r['calculator_id'] for r in sel})} calculators")
    for k, want in checks:
        v = frac(sel, k)
        if v is None:
            continue
        check(f"{nm} {k[3:]}", want, (v - f) / max(g - f, 1e-9), tol=0.03)

print("\n=== Table 1 (tab:ladder2): one probe, three answer formats, Qwen3-8B ===")
# The paper's pivot, and until 2026-09-14 the one main-text table nothing checked.
# Best layer for the two short formats; every layer run for chain of thought.
_TA8 = ROOT / "whitebox/results/fetched/agent-harness-hsw2/whitebox/results"
_lad = {}
for fmt, run in (("mc", "20260910-e14/e14-tierA-mc-8B"),
                 ("num", "20260910-e14/e14-tierA-num-8B"),
                 ("cot", "20260911-cot/e14-tierA-cot-8B-k1")):
    per, ids, nR = {}, [], 0
    for q in sorted((_TA8 / run).glob("layer_*.jsonl")):
        rows = load_jsonl(q)
        R = [r for r in rows if r["cell"] == "R"]
        k = "gok_replace_real" if "gok_replace_real" in R[0] else "ok_replace_real"
        per[q.stem] = sum(bool(r.get(k)) for r in R) / len(R)
        ids, nR = [r["id"] for r in rows], len(R)
    _lad[fmt] = (per, set(ids), nR)
if all(_lad[f][0] for f in _lad):
    check("ladder: multiple choice n_R", 44, _lad["mc"][2], tol=0)
    check("ladder: multiple choice, best layer", 1.000, max(_lad["mc"][0].values()))
    check("ladder: free-form n_R", 56, _lad["num"][2], tol=0)
    check("ladder: free-form, best layer", 0.304, max(_lad["num"][0].values()))
    check("ladder: chain of thought n_R", 80, _lad["cot"][2], tol=0)
    check("ladder: chain of thought, best layer", 0.000, max(_lad["cot"][0].values()))
    # "one item set" in the caption: MC and free-form share 120 items, CoT is 80 of them
    same = _lad["mc"][1] == _lad["num"][1] and _lad["cot"][1] <= _lad["mc"][1]
    check("ladder: CoT items are a subset of the other two", 1, int(same), tol=0)
else:
    print("  (the Tier A 8B ladder runs are not present locally)")

print("\n=== k* by the pre-registered definition (tables.py) ===")
def kstar(vals):
    """Half of the range from k=16 to the curve's max, interpolated in log2 k."""
    grid = [(k, vals[k]) for k in (16, 32, 64, 128) if k in vals]
    half = grid[0][1] + 0.5 * (max(v for _, v in grid) - grid[0][1])
    for (k0, v0), (k1, v1) in zip(grid, grid[1:]):
        if v0 <= half <= v1 and v1 > v0:
            return k0 * 2 ** ((half - v0) / (v1 - v0))
check("k* on ten calculators (paper 45)", 45.0,
      kstar({16: 0.111, 32: 0.333, 64: 0.722, 128: 0.944}), tol=0.6)
_r40 = restrict([r for q in sorted(BYHOST.glob("*/rank40-l8.jsonl"))
                 for r in load_jsonl(q)])
if _r40:
    g40, f40 = frac(_r40, "ok_gold_in_context"), frac(_r40, "ok_receiver")
    check("k* on forty calculators (subset, superseded by 47)", 52.0, kstar(
        {k: ((frac(_r40, f"ok_rank{k}_L8") or 0) - f40) / (g40 - f40)
         for k in (16, 32, 64, 128)}), tol=0.6)

print("\n=== the depth curves, recomputed at the span runs' budget ===")
_d = []
for q in sorted(BYHOST.glob("*/big40-depth.jsonl")):
    _d += load_jsonl(q)
if _d:
    sel = restrict(_d)
    g = frac(sel, "ok_gold_in_context")
    print(f"    big40-depth: n={len(sel)} over "
          f"{len({r['calculator_id'] for r in sel})} calculators")
    # post-fix rerun (the pre-fix file is in fetched/superseded/hsw2/)
    for L, want in ((0, 1.04), (4, 0.94), (8, 0.85), (12, 0.77), (14, 0.28),
                    (15, 0.19), (16, 0.19), (20, 0.15)):
        check(f"sufficiency, layer {L}", want,
              (frac(sel, f"ok_real_L{L}") or 0.0) / g, tol=0.03)
_k = []
for q in sorted(BYHOST.glob("*/ko-8b-fast.jsonl")):
    _k += load_jsonl(q)
if _k:
    kp = [r for r in _k if r["ok_with"] and not r["ok_without"]]
    lay = _k[0]["layers"]
    print(f"    ko-8b-fast: {len(kp)} rescued over "
          f"{len({r['calculator_id'] for r in kp})} calculators")
    for L, want in ((20, 0.075), (24, 0.375), (28, 0.750), (32, 0.950)):
        i = lay.index(L)
        v = sum(bool(r["ok_block_from"][i]) for r in kp) / len(kp)
        check(f"necessity, blocked from layer {L}", want, v, tol=0.03)
    # "0.08--0.15 for every L <= 20 but L=4 (0.33)": the paper said "at most
    # 0.15 for every L <= 20" until 2026-09-14, and layer 4 reads 0.325
    nec = {L: sum(bool(r["ok_block_from"][i]) for r in kp) / len(kp)
           for i, L in enumerate(lay)}
    check("necessity: layer 4, the exception", 0.325, nec.get(4), tol=0.01)
    check("necessity: max over L<=20 other than 4", 0.15,
          max(v for L, v in nec.items() if L <= 20 and L != 4), tol=0.001)
    check("necessity: min over L<=20", 0.075,
          min(v for L, v in nec.items() if L <= 20), tol=0.001)

print("\n=== numbers written into the main text on 2026-09-14 15:00-16:20 ===")
# Recomputed here with this script's own restrict/frac/kstar, not by importing
# paper/replication.py: the point is two independent paths to each number.
import random as _random


def _by(tags):
    rows = {}
    for t in tags:
        for q in sorted(BYHOST.glob(f"*/{t}.jsonl")):
            for r in load_jsonl(q):
                rows.setdefault(r["instance_id"], {}).update(r)
    return list(rows.values())


def _rho(sel, key):
    sk = [r for r in sel if key in r]
    if not sk:
        return None
    g, f = frac(sk, "ok_gold_in_context"), frac(sk, "ok_receiver")
    return ((frac(sk, key) or 0.0) - f) / max(g - f, 1e-9)


def _kstar_rows(sel, L):
    return kstar({k: _rho(sel, f"ok_rank{k}_L{L}") for k in (16, 32, 64, 128)})


def _kstar_ci(sel, L, B=2000):
    bc = collections.defaultdict(list)
    for r in sel:
        bc[r["calculator_id"]].append(r)
    cs, rng, ks = list(bc), _random.Random(0), []
    for _ in range(B):
        S = [r for c in (rng.choice(cs) for _ in cs) for r in bc[c]]
        k = _kstar_rows(S, L)
        if k is not None:
            ks.append(k)
    ks.sort()
    return ks[int(.025 * len(ks))], ks[int(.975 * len(ks))]


_q40 = restrict(_by(["fixmask-big40"] + [f"fixmask-quarters40-q{i}" for i in range(4)]))
if any("ok_q1_L8" in r for r in _q40):
    for k, want in (("q0", 0.12), ("q1", 0.56), ("q2", 0.12), ("q3", 0.12)):
        check(f"quarters, forty calculators: {k}", want, _rho(_q40, f"ok_{k}_L8"), tol=0.01)
_dl = restrict(_by(["fixmask-dl"]))
if _dl:
    check("doc-last n", 28, len(_dl), tol=0)
    for k, want in (("real_L8", 1.00), ("real_L16", 0.85), ("dother_L8", 0.96),
                    ("dother_L16", 0.48), ("dperp_L8", 0.04), ("dperp_L16", 0.04)):
        check(f"doc-last {k}", want, _rho(_dl, f"ok_{k}"), tol=0.01)
_dv = _by(["fixmask-dev10"])
if _dv:
    sel = restrict(_dv)
    check("dose sweep n (restricted)", 16, len(sel), tol=0)
    for a, want in (("0.4", 0.06), ("0.5", 0.00), ("0.55", 0.06), ("0.6", 0.62),
                    ("0.7", 0.94)):
        check(f"dose alpha={a}, after the fix", want, _rho(sel, f"ok_a{a}_L8"), tol=0.01)
    check("dose alpha=1, after the fix", 1.00, _rho(sel, "ok_real_L8"), tol=0.01)
    check("another skill, restricted", 0.19, _rho(sel, "ok_dcross_L8"), tol=0.01)
    ids = {r["instance_id"] for r in sel}
    rel = [r for r in _dv if r["instance_id"] not in ids]
    check("released split n", 24, len(rel), tol=0)
    check("another skill, released split", 0.47, _rho(rel, "ok_dcross_L8"), tol=0.01)
_tw = restrict(_by(["tqa-window"]))
if _tw:
    for k, want in (("w8_11", 0.90), ("w12_15", 0.73), ("w14_19", 0.45),
                    ("w16_35", 0.21), ("L16", 0.21)):
        check(f"TheoremQA window {k}", want, _rho(_tw, f"ok_real_{k}"), tol=0.01)
_l6 = restrict(_by(["fixmask-lad06-rank"]))
if _l6:
    for k, want in ((16, 0.02), (32, 0.21), (64, 0.74), (128, 0.72)):
        check(f"0.6B rank{k}, after the fix", want, _rho(_l6, f"ok_rank{k}_L6"), tol=0.01)

# Table tab:replication and the k* intervals quoted in sec:ladder / fig:rank
_REP = (("MedCalc/Qwen3-8B", 36, 8, ["fixmask-big40"], ["big40-depth"], "rank40-l8", "ko-8b-fast",
         0.87, 0.10, (12, 14), 0.78, 52, (43, 72)),
        ("TheoremQA/Qwen3-8B", 36, 8, ["tqa-span"], ["tqa-depth"], "tqa-rank", "tqa-ko",
         0.84, 0.25, (12, 14), 0.56, 50, None),
        ("MedCalc/Qwen3-0.6B", 28, 6, ["fixmask-lad06-rank"], [], "fixmask-lad06-rank", None,
         0.89, None, None, None, 40, (32, 50)),
        ("TheoremQA/Qwen3-0.6B", 28, 6, ["tqa06-rank"], ["tqa06-depth"], "tqa06-rank", None,
         0.74, None, (10, 12), None, 52, None),
        ("MedCalc/Mistral-7B", 32, 4, ["mis3-big40-L4"], ["mis2-depth", "mis2-depth-fine"],
         "mis3-rank-L4", "mis2-ko-b", 0.92, 0.27, (6, 7), 0.875, 84, (59, 97)),
        ("TheoremQA/Mistral-7B", 32, 4, ["tqamis-span"], ["tqamis-depth"], "tqamis-rank",
         "tqamis-ko", 0.94, 0.27, (6, 7), 0.625, 64, (50, 79)))
for (nm, nl, L, bat, dep, rk, ko, w_rho, w_ctrl, w_ho, w_read, w_k, w_ci) in _REP:
    base = restrict(_by(bat))
    if not base:
        print(f"  ({nm} battery not present locally)")
        continue
    check(f"replication {nm}: rho", w_rho, _rho(base, f"ok_real_L{L}"), tol=0.005)
    if w_ctrl is not None:
        c = [_rho(base, f"ok_{a}_L{L}") for a in ("drand", "dshuf", "a0.5", "dcross", "dfar")]
        check(f"replication {nm}: max control", w_ctrl, max(x for x in c if x is not None), tol=0.005)
    if w_ho is not None:
        d = restrict(_by(dep))
        hi, lo = _rho(d, f"ok_real_L{w_ho[0]}"), _rho(d, f"ok_real_L{w_ho[1]}")
        check(f"replication {nm}: handover L{w_ho[0]}>=.5>L{w_ho[1]}", 1,
              int(hi is not None and lo is not None and hi >= 0.5 > lo), tol=0)
    if w_read is not None:
        kr = [r for r in _by([ko]) if r.get("ok_with") and not r.get("ok_without")]
        lay = kr[0]["layers"]
        first = next(Lk for i, Lk in enumerate(lay)
                     if sum(bool(r["ok_block_from"][i]) for r in kr) / len(kr) >= 0.5)
        check(f"replication {nm}: reading (rel. depth)", w_read, first / nl, tol=0.005)
    rs = restrict(_by([rk]))
    check(f"replication {nm}: k*", w_k, _kstar_rows(rs, L), tol=0.6)
    if w_ci:
        lo, hi = _kstar_ci(rs, L)
        check(f"replication {nm}: k* CI low", w_ci[0], lo, tol=0.6)
        check(f"replication {nm}: k* CI high", w_ci[1], hi, tol=0.6)
_q10 = restrict(_by(["fixmask-quarters"]))
if _q10:
    check("quarters, ten calculators after the fix: n", 16, len(_q10), tol=0)
    for k, want in (("q0", 0.12), ("q1", 0.81), ("q2", 0.06), ("q3", 0.06)):
        check(f"quarters, ten calculators after the fix: {k}", want, _rho(_q10, f"ok_{k}_L8"), tol=0.01)
for tags, want, lab in ((["spanvec-fs-parts", "spanvec-fs-base"], 0.11, "doc first"),
                        (["spanvec-fs-dlparts", "spanvec-fs-dl"], 0.06, "doc last")):
    sel = restrict(_by(tags))
    if sel:
        check(f"all-skill mean (pre-fix), {lab}", want, _rho(sel, "ok_dall_L8"), tol=0.01)
_lb = [r for r in _by(["lb-span"]) if not r.get("ok_receiver")]
if _lb:
    # LogicBench, per-item restriction (the per-skill one leaves almost nothing)
    check("LogicBench per-item n", 57, len(_lb), tol=0)
    for k, want in (("real", 0.75), ("realm", 0.80), ("a0.5", 0.44), ("dcross", 0.38),
                    ("dshuf", 0.25), ("drand", 0.15)):
        check(f"LogicBench {k}", want, _rho(_lb, f"ok_{k}_L8"), tol=0.01)
_lbd = [r for r in _by(["lb-depth"]) if not r.get("ok_receiver")]
if _lbd:
    for L, want in ((0, 0.93), (16, 0.49), (20, 0.33)):
        check(f"LogicBench depth L{L}", want, _rho(_lbd, f"ok_real_L{L}"), tol=0.01)
print("\n=== data check of 2026-09-14 16:30: numbers that had no check ===")
# Behaviour, 1,100 items (copied from the shared disk, p8-step)
_P8S = ROOT / "howskill/results/p8-step"
if (_P8S / "p8-no_skill.jsonl").exists():
    _A = {a: {r["instance_id"]: bool(r["correct"]) for r in load_jsonl(_P8S / f"{a}.jsonl")}
          for a in ("p8-gold_no_tool", "p8-no_skill", "p8-ctrl_neutral_no_tool")}
    _acc = {a: sum(v.values()) / len(v) for a, v in _A.items()}
    check("behaviour: n per arm", 1100, min(len(v) for v in _A.values()), tol=0)
    check("behaviour: gold %", 74.2, 100 * _acc["p8-gold_no_tool"], tol=0.05)
    check("behaviour: no skill %", 34.5, 100 * _acc["p8-no_skill"], tol=0.05)
    check("behaviour: wrong skill %", 31.5, 100 * _acc["p8-ctrl_neutral_no_tool"], tol=0.05)
    check("behaviour: gold - none (pp)", 39.7,
          100 * (_acc["p8-gold_no_tool"] - _acc["p8-no_skill"]), tol=0.05)
    check("behaviour: wrong - none (pp)", -2.9,
          100 * (_acc["p8-ctrl_neutral_no_tool"] - _acc["p8-no_skill"]), tol=0.05)
# tab:controls, the d column (the text quoted the g column for the scrambled control)
_E14B = ROOT / "whitebox/results/fetched/agent-harness-wb3/whitebox/results/20260910-e14"
for run, lo, hi, glo, ghi in (("e14-tierA-mc-1.7B-shuffled", 0.188, 0.292, 0.604, 0.625),
                              ("e14-tierA-mc-1.7B-corrupted", 0.229, 0.312, 0.708, 0.750)):
    fs = [q for q in (_E14B / run).glob("layer_*.jsonl") if 21 <= int(q.stem.split("_")[1]) <= 27]
    if fs:
        dv = [frac(load_jsonl(q), "ok_add_d_a1", "R") for q in fs]
        gv = [frac(load_jsonl(q), "ok_add_g", "R") for q in fs]
        check(f"{run}: d min over 21-27", lo, min(dv), tol=0.002)
        check(f"{run}: d max over 21-27", hi, max(dv), tol=0.002)
        check(f"{run}: g min over 21-27", glo, min(gv), tol=0.002)
        check(f"{run}: g max over 21-27", ghi, max(gv), tol=0.002)
# the aggregate log-probability ordering is layer 27, the 133% decomposition layer 21
p = OLD / "e2-tierA/per_layer.jsonl"
if p.exists():
    import statistics as _st
    _l = {x["layer"]: x["rows"] for x in load_jsonl(p)}
    r27 = _l[27]
    for k, want in (("lp_mean", -2.85), ("lp_filler", -5.20), ("lp_real", -6.60),
                    ("lp_no", -7.30), ("lp_mismatched", -10.29)):
        check(f"log-prob ordering, layer 27: {k}", want, _st.mean(r[k] for r in r27), tol=0.01)
    check("mean - real at layer 27 (nats)", 3.75,
          _st.mean(r["lp_mean"] - r["lp_real"] for r in r27), tol=0.01)
    check("accuracy, mean vector, layer 27", 0.256, _st.mean(r["ok_mean"] for r in r27), tol=0.001)
    check("accuracy, real state, layer 27", 0.436, _st.mean(r["ok_real"] for r in r27), tol=0.001)
    check("F+B share of the layer-21 gap (%)", 133, 100 * (2.575 + 1.084) / 2.747, tol=0.5)
# participation ratio of the content matrix (spanvec-fs-geomf) and of the states (prdiag)
_gm = []
for q in sorted(BYHOST.glob("*/spanvec-fs-geomf.jsonl")):
    _gm += load_jsonl(q)
if _gm:
    pd = collections.defaultdict(list)
    for r in _gm:
        for gl in r["geom"]:
            pd[gl["layer"]].append(gl["pr_d"])
    check("PR of d, layer 12, mean", 64, sum(pd[12]) / len(pd[12]), tol=0.5)
    check("PR of d, layer 16, mean", 17, sum(pd[16]) / len(pd[16]), tol=0.5)
    check("PR of d, layer 16, items below 5", 32, sum(x < 5 for x in pd[16]), tol=0)
    check("PR of d, layer 16, the other eight (min)", 81, min(x for x in pd[16] if x >= 5), tol=1)
if _p:
    per = collections.defaultdict(list)
    for r in _p:
        for gl in r.get("geom", []):
            per[gl["layer"]].append(gl["pr_hg"])
    check("PR of states, layer 14, min", 47, min(per[14]), tol=0.6)
    check("PR of states, layer 14, max", 75, max(per[14]), tol=0.6)
    check("PR of states, layer 16, items below 5", 34, sum(x < 5 for x in per[16]), tol=0)

def _pr_range(tag, key, lo=0, hi=20):
    rows = [r for q in sorted(BYHOST.glob(f"*/{tag}.jsonl")) for r in load_jsonl(q)]
    per = collections.defaultdict(list)
    for r in rows:
        for gl in r.get("geom", []):
            if lo <= gl["layer"] <= hi:
                per[gl["layer"]].append(gl[key])
    m = [sum(v) / len(v) for v in per.values()]
    return (min(m), max(m)) if m else (None, None)


# "the content matrix's participation ratio agrees (66--77 on Qwen3-0.6B, 70--99
# on Qwen3-8B over layers 0--20)": the draft said 65--77 / 66--79, not recomputable
for tag, key, want in (("prdiag-06-df", "d_pr_droppos", (66, 77)),
                       ("prdiag-8b-df", "d_pr_droppos", (70, 99))):
    a, b = _pr_range(tag, key)
    check(f"{tag}: content-matrix PR over layers 0-20, min", want[0], a, tol=0.6)
    check(f"{tag}: content-matrix PR over layers 0-20, max", want[1], b, tol=0.6)

# realm is dcross's paired control (own d over the shared prefix), NOT a norm
# rescale; tables.py labelled it as one until 2026-09-14 and the text followed
if _dv:
    sel = restrict(_dv)
    check("own d on the shared prefix (realm), ten calculators", 0.94, _rho(sel, "ok_realm_L8"), tol=0.01)
    check("development set: calculators that need the document", 4,
          len({r["calculator_id"] for r in sel}), tol=0)
    rel = [r for r in _dv if r["instance_id"] not in {x["instance_id"] for x in sel}]
    check("released: receiver accuracy", 0.375, frac(rel, "ok_receiver"), tol=0.001)
    check("released: another skill accuracy", 0.667, frac(rel, "ok_dcross_L8"), tol=0.001)
    check("released: noise accuracy", 0.375, frac(rel, "ok_drand_L8"), tol=0.001)
    check("pooled transfer rho", 0.32, _rho(_dv, "ok_dcross_L8"), tol=0.005)
if _q40:
    check("own d on the shared prefix (realm), forty calculators", 0.73, _rho(_q40, "ok_realm_L8"), tol=0.005)
for tags, lab in ((["spanvec-fs-parts", "spanvec-fs-base"], "doc first"),
                  (["spanvec-fs-dlparts", "spanvec-fs-dl"], "doc last")):
    sel = restrict(_by(tags))
    if sel:
        check(f"normrecv equals real (pre-fix), {lab}", 0.0,
              _rho(sel, "ok_normrecv_L8") - _rho(sel, "ok_real_L8"), tol=0.001)
check("pre-fix normrecv, doc first", 1.06,
      _rho(restrict(_by(["spanvec-fs-parts", "spanvec-fs-base"])), "ok_normrecv_L8"), tol=0.005)

# "The span is 415 to 1,630 positions wide on the forty calculators" (the draft
# said 420 to 807, which is the pre-fix ten-calculator set)
_w = [r.get("n_patched") for r in _by(["fixmask-big40"]) if r.get("n_patched")]
if _w:
    check("span width, forty calculators, min", 415, min(_w), tol=0)
    check("span width, forty calculators, max", 1630, max(_w), tol=0)
# "replacing the final position repairs at most 3 of 18 rescued items (layer 10)
# and 0--1 from layer 14 on" (the draft said 1 of 20)
_fp = collections.defaultdict(list)
for q in sorted(BYHOST.glob("*/diffvec-cot-L*.jsonl")):
    for r in load_jsonl(q):
        if "ok_replace_gold" in r:
            _fp[r["layer"]].append(r)
if _fp:
    resc = {L: [r for r in rs if r["ok_gold"] and not r["ok_none"]] for L, rs in _fp.items()}
    check("final position: rescued items", 18, len(resc[10]), tol=0)
    check("final position: replace repairs at layer 10", 3,
          sum(bool(r["ok_replace_gold"]) for r in resc[10]), tol=0)
    check("final position: max repairs from layer 14 on", 1,
          max(sum(bool(r["ok_replace_gold"]) for r in resc[L]) for L in resc if L >= 14), tol=0)

_m = restrict(_by(["mis3-rank-L4"]))
if _m:
    check("Mistral MedCalc rank128", 0.71, _rho(_m, "ok_rank128_L4"), tol=0.005)
    check("Mistral MedCalc untruncated", 0.92, _rho(_m, "ok_real_L4"), tol=0.005)

# ---------------------------------------------------------------------------
# Appendix "The full-dataset rerun, and what reads the span" (app:fullscale).
# The subset checks above are deliberately kept: they cover runs that still
# exist and that the main text still cites.
print("\n== full-dataset rerun (467 items / 48 calculators) ==")
_full = _by(["full-battery-a", "full-battery-b", "full-rank-a", "full-rank-b",
             "full-depth-a", "full-depth-b", "full-depth-c13", "full-depth-d",
             "full-quarters"])
_fr = restrict(_full)
if _fr:
    check("full: items after per-calc restriction", 135, len(_fr), tol=0)
    check("full: calculators after restriction", 14,
          len({r["calculator_id"] for r in _fr}), tol=0)
    check("full: transplant real_L8", 0.89, _rho(_fr, "ok_real_L8"), tol=0.01)
    check("full: same skill matched prefix", 0.65, _rho(_fr, "ok_realm_L8"), tol=0.01)
    check("full: identity patch", 0.00, _rho(_fr, "ok_self_L8"), tol=0.005)
    for arm, claimed in (("a0.5", 0.04), ("dshuf", 0.05), ("drand", 0.02),
                         ("dcross", 0.05), ("dfar", 0.05), ("dnear", 0.12)):
        check(f"full: control {arm}", claimed, _rho(_fr, f"ok_{arm}_L8"), tol=0.01)
    for k, claimed in ((128, 0.77), (64, 0.63), (32, 0.12), (16, 0.05)):
        check(f"full: rank{k}", claimed, _rho(_fr, f"ok_rank{k}_L8"), tol=0.01)
    check("full: rank64lo", 0.03, _rho(_fr, "ok_rank64lo_L8"), tol=0.01)
    check("full: rank16lo", 0.04, _rho(_fr, "ok_rank16lo_L8"), tol=0.01)
    for q_, claimed in enumerate((0.09, 0.56, 0.12, 0.05)):
        check(f"full: quarter q{q_}", claimed, _rho(_fr, f"ok_q{q_}_L8"), tol=0.01)
    # the depth sweep at one-layer resolution; the cliff is 12 -> 13
    for L, claimed in ((0, 0.98), (4, 0.98), (8, 0.89), (12, 0.74), (13, 0.16),
                       (14, 0.16), (15, 0.06), (16, 0.06), (17, 0.07),
                       (18, 0.03), (19, 0.02), (20, 0.03)):
        check(f"full: depth L{L}", claimed, _rho(_fr, f"ok_real_L{L}"), tol=0.01)

# The continuous readout (pc-lpcot): q has the same anchors as rho and no
# decoding threshold, and it steps at the same layer.
print("\n== continuous readout, teacher-forced trajectory ==")
_lp = [r for q in sorted(BYHOST.glob("*/pc-lpcot.jsonl")) for r in load_jsonl(q)]
_lp = [r for r in _lp if r.get("ok_gold_in_context")]
if _lp:
    check("lpcot: items", 442, len(_lp), tol=0)
    def _q(L):
        v = []
        for r in _lp:
            den = r["gold"]["lp"] - r["recv"]["lp"]
            if abs(den) > 1e-6:
                v.append((r[f"L{L}"]["lp"] - r["recv"]["lp"]) / den)
        return sum(v) / len(v)
    for L, claimed in ((0, 0.999), (4, 0.989), (8, 0.960), (12, 0.831),
                       (13, 0.598), (14, 0.595), (16, 0.340), (20, 0.201),
                       (24, 0.129)):
        check(f"lpcot: q at L{L}", claimed, _q(L), tol=0.005)

# Head knockout on the held-out half of the calculators.
print("\n== reader-head knockout, held-out split ==")
_ko = {}
for t in ("heads-ko", "heads-ko-rand"):
    for q in sorted(BYHOST.glob(f"*/{t}.jsonl")):
        for r in load_jsonl(q):
            _ko.setdefault(r["instance_id"], {}).update(r)
_TEST = set("11 15 17 19 20 22 24 26 29 30 32 36 4 43 45 49 51 57 59 62 64 66 68 7".split())
_ks = [r for r in _ko.values() if "ok_koheads" in r and "ok_korand" in r
       and not r.get("ok_receiver") and r["calculator_id"] in _TEST]
if _ks:
    n = len(_ks)
    check("knockout: held-out items", 195, n, tol=0)
    _a = sum(bool(r["ok_korand"]) for r in _ks) / n
    _b = sum(bool(r["ok_koheads"]) for r in _ks) / n
    check("knockout: random 32 heads, accuracy", 0.764, _a, tol=0.005)
    check("knockout: selected 32 heads, accuracy", 0.610, _b, tol=0.005)
    check("knockout: paired difference", 0.154, _a - _b, tol=0.005)
    check("knockout: discordant, random right", 39,
          sum(1 for r in _ks if r["ok_korand"] and not r["ok_koheads"]), tol=0)
    check("knockout: discordant, selected right", 9,
          sum(1 for r in _ks if r["ok_koheads"] and not r["ok_korand"]), tol=0)

# The main-text displays now read the full-dataset rerun, so their numbers get
# their own checks. The subset checks above are kept: the appendix still reports
# both columns, and those runs still exist.
print("\n== main-text displays after rewiring to the full rerun ==")
_win = restrict(_by(["full-window"]))
if _win:
    check("full: window items (own receiver)", 222, len(_win), tol=0)
    for k, claimed in (("w8_11", 0.95), ("w12_15", 0.81), ("w14_19", 0.22),
                       ("w16_35", 0.10), ("L16", 0.10)):
        check(f"full: window {k}", claimed, _rho(_win, f"ok_real_{k}"), tol=0.01)
_kof = [r for q in sorted(BYHOST.glob("*/full-ko.jsonl")) for r in load_jsonl(q)]
_kof = [r for r in _kof if r.get("ok_with") and not r.get("ok_without")]
if _kof:
    check("full: knockout rescued items", 466, len(_kof), tol=0)
    _kl = _kof[0]["layers"]
    for L, claimed in ((4, 0.23), (20, 0.18), (24, 0.46), (28, 0.79), (32, 0.91)):
        i = _kl.index(L)
        check(f"full: knockout blocked from L{L}", claimed,
              sum(bool(r["ok_block_from"][i]) for r in _kof) / len(_kof), tol=0.01)
_rkf = restrict(_by(["full-rank-a", "full-rank-b", "full-battery-a"]))
if _rkf:
    check("full: k* (paper 47)", 47.0, kstar(
        {k: _rho(_rkf, f"ok_rank{k}_L8") for k in (16, 32, 64, 128)}), tol=0.6)
_dlf = restrict(_by(["full-dl-a", "full-dl-b"]))
if _dlf:
    check("full: doc-last items", 151, len(_dlf), tol=0)
    for k, L, claimed in (("real", 8, 1.02), ("real", 16, 0.49),
                          ("dother", 8, 0.98), ("dother", 16, 0.29),
                          ("dperp", 8, 0.03), ("dperp", 16, 0.05)):
        check(f"full: doc-last {k} L{L}", claimed,
              _rho(_dlf, f"ok_{k}_L{L}"), tol=0.01)

# Numbers the main text now quotes from the full rerun that no earlier check
# covered: the receiver screen, the prompt-order contrast, and the doc-last set.
print("\n== receiver screen and prompt order, full rerun ==")
_bat = _by(["full-battery-a", "full-battery-b"])
if _bat:
    _bc = collections.defaultdict(list)
    for r in _bat:
        _bc[r["calculator_id"]].append(r)
    _solved = {c for c, rs in _bc.items() if any(x.get("ok_receiver") for x in rs)}
    check("full: calculators the receiver solves", 34, len(_solved), tol=0)
    check("full: calculators restricted in", 14, len(_bc) - len(_solved), tol=0)
    _sg = [r for c in _solved for r in _bc[c]]
    check("full: items where the receiver solves", 332, len(_sg), tol=0)
    check("full: other-skill donor where receiver solves", 0.17,
          _rho(_sg, "ok_dcross_L8"), tol=0.01)
    check("full: noise where receiver solves", 0.10,
          _rho(_sg, "ok_drand_L8"), tol=0.01)
_dlo = restrict(_by(["full-dl-a", "full-dl-b"]))
_dfo = restrict(_by(["full-depth-a", "full-depth-b", "full-depth-c13",
                     "full-depth-d", "full-battery-a"]))
if _dlo and _dfo:
    check("full: order, skill last at L16", 0.49, _rho(_dlo, "ok_real_L16"), tol=0.01)
    check("full: order, skill first at L16", 0.06, _rho(_dfo, "ok_real_L16"), tol=0.01)

print("\n" + ("ALL CHECKS PASSED" if not fails
              else f"{len(fails)} MISMATCH(ES): " + "; ".join(fails)))
sys.exit(1 if fails else 0)
