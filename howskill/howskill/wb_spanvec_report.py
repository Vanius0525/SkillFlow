"""Merge the wb_spanvec shards and print one table.

    python -m howskill.wb_spanvec_report results/p8-wb/fetched/by-host/*/spanvec-*.jsonl

The battery is sharded by ARM, not by instance: every box runs the same 40
notes and the same capture, and differs only in which donors it decodes. So a
merge is a union over arm keys grouped by instance_id, not a concatenation --
concatenating would count each note once per shard in the baselines, which all
shards that carry them agree on, and would silently hide a shard that ran a
different instance set.
"""

from __future__ import annotations

import collections
import json
import math
import sys

ORDER = ["gold_in_context", "none", "recv_neutralprose",
         "recv_wrongskill", "recv_pairedneutral", "receiver", "self",
         "a0.25", "a0.5", "a0.75", "real", "a1.5", "a2", "a3",
         "a0.5r", "a2r", "a3r",
         "dbar", "dother", "dpar", "dperp",
         "realm", "dnear", "dfar", "dcross", "dall", "head", "tail", "normrecv",
         "q0", "q1", "q2", "q3",
         "rank1", "rank2", "rank4", "rank8", "rank16", "rank32", "rank64",
         "rank128", "rank16lo", "rank64lo", "xfer", "xfern",
         "dshuf", "drand"]

GLOSS = {
    "gold_in_context": "the gold document actually in the prompt",
    "none": "no document at all",
    "recv_neutralprose": "the slot holds neutral non-clinical prose",
    "recv_wrongskill": "the slot holds one fixed WRONG clinical skill",
    "recv_pairedneutral": "the slot holds this skill's paired neutral document",
    "receiver": "filler document, unpatched -- the floor every arm starts from",
    "self": "the receiver's own states (exact no-op; must equal receiver)",
    "a0.25": "h_recv + 0.25 d",
    "a0.5": "h_recv + 0.50 d",
    "real": "h_recv + 1.00 d  (= the gold states)",
    "a0.75": "h_recv + 0.75 d",
    "a1.5": "h_recv + 1.50 d",
    "a2": "h_recv + 2.00 d",
    "a3": "h_recv + 3.00 d",
    "a0.5r": "h_recv + 0.50 d, rescaled to the gold norm",
    "a2r": "h_recv + 2.00 d, rescaled to the gold norm",
    "a3r": "h_recv + 3.00 d, rescaled to the gold norm",
    "dbar": "h_recv + mean of the OTHER notes' d, same calculator",
    "dother": "h_recv + one other note's d, same calculator",
    "dpar": "h_recv + the half of d along that mean",
    "dperp": "h_recv + the half of d orthogonal to it",
    "realm": "h_recv + own d, on the shared prefix only (dcross's control)",
    "dcross": "h_recv + another calculator's mean d, shared prefix",
    "dshuf": "h_recv + own d with its positions permuted",
    "drand": "h_recv + noise, per-position norm matched to d",
    "dall": "h_recv + d averaged over EVERY calculator (the common shift)",
    "dnear": "h_recv + d from a RELATED skill (same quantity, other formula)",
    "dfar": "h_recv + d from an UNRELATED skill",
    "head": "own d on the FIRST half of the span only",
    "tail": "own d on the LAST half of the span only",
    "normrecv": "the gold states, rescaled to the receiver's own norm",
    "q0": "own d on the first quarter of the span only",
    "q1": "own d on the second quarter only",
    "q2": "own d on the third quarter only",
    "q3": "own d on the last quarter only",
    "rank1": "own d truncated to rank 1 across the span",
    "rank2": "rank 2", "rank4": "rank 4", "rank8": "rank 8",
    "rank16": "rank 16", "rank32": "rank 32", "rank64": "rank 64",
    "rank128": "rank 128",
    "rank16lo": "the BOTTOM 16 singular directions of d",
    "rank64lo": "the BOTTOM 64 singular directions of d",
    "xfer": "d captured at the donor layer, injected here (raw)",
    "xfern": "same, rescaled to this layer's own ||d||",
}


def ci(v):
    m = sum(v) / len(v)
    se = math.sqrt(max(m * (1 - m), 0.0) / len(v))
    return m, max(0.0, m - 1.96 * se), min(1.0, m + 1.96 * se)


def main(paths):
    rows: dict[str, dict] = {}
    shards = collections.Counter()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                iid = r.get("instance_id")
                if not iid:
                    continue
                tgt = rows.setdefault(iid, {"instance_id": iid,
                                            "cell": r.get("cell"),
                                            "calculator_id": r.get("calculator_id")})
                for k, v in r.items():
                    if k.startswith("ok_"):
                        if k in tgt and tgt[k] != v:
                            print(f"[warn] {iid} {k}: {tgt[k]} vs {v} "
                                  f"across shards")
                        tgt[k] = v
                        shards[path] += 1

    by_arm = collections.defaultdict(list)
    for r in rows.values():
        for k, v in r.items():
            if k.startswith("ok_"):
                by_arm[k[3:]].append(bool(v))

    print(f"{len(rows)} notes, {len(by_arm)} arms, from {len(paths)} files")
    for p in sorted(shards):
        print(f"  {shards[p]:5d} cells  {p}")

    layers = sorted({k.split("_L")[1] for k in by_arm if "_L" in k},
                    key=int)
    for L in layers:
        print(f"\n=== layer {L} "
              f"{'=' * 40}")
        print(f"  {'arm':16s} {'n':>4s}  {'acc':>6s}  {'95% CI':>15s}   gloss")
        for name in ORDER:
            key = name if name in by_arm else f"{name}_L{L}"
            if key not in by_arm:
                continue
            m, lo, hi = ci(by_arm[key])
            print(f"  {name:16s} {len(by_arm[key]):4d}  {m:6.3f}  "
                  f"[{lo:5.3f},{hi:5.3f}]   {GLOSS.get(name, '')}")
        extra = sorted(k for k in by_arm
                       if k.split("_L")[0] not in ORDER and k not in ORDER)
        for key in extra:
            m, lo, hi = ci(by_arm[key])
            print(f"  {key:16s} {len(by_arm[key]):4d}  {m:6.3f}  "
                  f"[{lo:5.3f},{hi:5.3f}]")

    if "receiver" in by_arm:
        base = sum(by_arm["receiver"]) / len(by_arm["receiver"])
        top = (sum(by_arm["gold_in_context"]) / len(by_arm["gold_in_context"])
               if "gold_in_context" in by_arm else 1.0)
        span = max(top - base, 1e-9)
        print(f"\n  as a fraction of what is there to recover "
              f"(receiver {base:.3f} -> gold {top:.3f}):")
        for L in layers:
            for name in ORDER:
                key = f"{name}_L{L}"
                if key not in by_arm or name in ("none", "receiver",
                                                 "gold_in_context"):
                    continue
                m = sum(by_arm[key]) / len(by_arm[key])
                print(f"    L{L} {name:12s} {(m - base) / span:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
