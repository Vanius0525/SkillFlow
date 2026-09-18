"""M8 -- the position-budget curve: how many span positions the transplant
needs, and whether WHICH positions matters once the count is held fixed.

    python -m howskill.wb_posbudget --model $BASE/models/Qwen3-8B \
        --per-calc 20 --max-calcs 55 --calcs 7,13,... --layer 8 \
        --arms ev1,ev4,ev16,ev64,ev256,evhalf --out results/p8-wb/pb-ev.jsonl

WHY THIS FILE EXISTS

The paper's two interventions sit at the ends of a very long axis. Writing the
final prompt position recovers nothing on this material; writing the skill's
whole span -- 415 to 1,630 positions -- recovers 0.89. Between them nothing was
measured except the four contiguous quarters. So the rise has two readings that
the existing data cannot tell apart:

  * STATE: recovery grows with how much with-skill state is written, wherever
    it is written. Any positions, enough of them, would do.
  * STRUCTURE: recovery needs the skill's states at the skill's own positions,
    and the right ones. More state in the wrong places does not help.

The full-span permutation control (0.05 against 0.89) already says arrangement
matters at the full budget, but a permutation also destroys local adjacency,
and nothing says what happens at intermediate budgets. This file sweeps the
budget B and, at every B, varies only how the B positions are chosen.

THE ARMS  (an arm is <strategy><budget>; budget is 1,4,16,64,256, `half` = m//2
           or `full` = m, where m is the span width)

  own positions (each written with its own with-skill state, h_recv + d = h_gold)
    ev   evenly spaced over the span              order and coverage preserved
    rn   uniformly random positions               the unstructured subsample
    td   the B positions with the largest ||d||   the most state per position:
                                                  if recovery tracked injected
                                                  state, this arm would lead
  misplaced
    mx   the SAME states as `rn`, each written m//2 positions away (cyclic).
         Identical injected vectors, identical count, identical energy; only
         where they land differs. At B=full this is a cyclic shift of the whole
         span, which -- unlike the permutation control -- keeps adjacency.
  contiguous windows of B positions, same budget, located by content
    wf   centred on the procedure section (`### Computation` / `### Scoring
         Criteria`), where the formula or scoring rule is written
    wd   centred on the prose description (title to `### Required Inputs`)
    we   centred on the worked example (`### Example` to the end)
    wr   centred at a random position              contiguity without content
  fragmentation and displacement, at a fixed budget
    cNxB the budget B cut into N contiguous blocks, evenly spaced (N=1 is one
         block, N=B is single positions): count and energy fixed, only how
         broken up the written positions are changes
    shD  the whole span's content displaced by D positions, cyclically: `real`
         with every state landing D positions from where it was read
  outside the span
    tq   the LAST B prompt positions (question tail, answer instruction, chat
         suffix), written with the with-skill run's states. tq1 is the classic
         final-position patch, here into the same receiver as every other arm.

  self   the receiver's own span states -- must reproduce the receiver exactly
  real   the whole span (= evfull); must reproduce wb_spanvec's `real`

Random choices are seeded by (instance, strategy, budget), never by processing
order, so shards that split the arms across boxes draw identical positions,
and `mx` always moves exactly the positions `rn` chose.

Every arm writes at ONE layer (--layer, default 8, the battery's layer; or
each of --layers in turn, one layer per decode) into
the matched fixed-skill receiver of wb_spanvec, and the baselines are merged
from the battery run by instance_id, as wb_spanvec's arm shards are.

For every arm the row also records the realised count, the share of the span's
content energy sum ||d_p||^2 that was written, and the fraction of the written
positions that fall in each section, so recovery can be regressed on count,
energy and location together rather than read off one curve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re

from howskill.wb_diffvec import graded, pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spanpatch import SpanScorer, _OutputLock, resume_done
from howskill.wb_spans import char_to_token_span
from howskill import wb_spanvec as SV

STRATEGIES = ("ev", "rn", "td", "mx", "wf", "wd", "we", "wr", "tq")
BUDGETS = ("1", "4", "16", "64", "256", "half", "full", "all")


def parse_arm(arm: str):
    if arm in ("self", "real"):
        return arm, None
    # cNxB: the budget B split into N contiguous blocks, evenly spaced over the
    # span with one seeded offset. N=1 is a single block (= `wr`), N=B is one
    # position each (= `rn` up to the placement rule), and the budget and the
    # injected energy are held fixed across N: the only thing that changes is
    # how fragmented the written positions are.
    m = re.match(r"^c(\d+)x(.+)$", arm)
    if m and m.group(2) in BUDGETS:
        return "c" + m.group(1), m.group(2)
    # shD: the WHOLE span's content, displaced by D positions (cyclically). The
    # budget, the states and their order are those of `real`; only the absolute
    # position each one lands on changes. It says how precisely the content has
    # to sit where it was read.
    m = re.match(r"^sh(.+)$", arm)
    if m and m.group(1) in BUDGETS:
        return "sh", m.group(1)
    # The boundary controls for `sh`. A cyclic shift by one keeps every relative
    # position inside the span, so its collapse can only come from what the
    # wrap and the edges do: the last state lands on the first position, and
    # the question's first token no longer follows the state it was computed
    # after. snD / sbD shift forward / backward WITHOUT wrapping (the positions
    # left over keep the receiver's state); xfD / xlD write the span in place
    # except its first / last D positions. If sn1 and sb1 recover what `real`
    # does, the sh1 collapse was the wrap, not the displacement.
    m = re.match(r"^(sn|sb|xf|xl)(.+)$", arm)
    if m and m.group(2) in BUDGETS:
        return m.group(1), m.group(2)
    for s in STRATEGIES:
        if arm.startswith(s) and arm[len(s):] in BUDGETS:
            if arm[len(s):] == "all" and s != "tq":
                break
            return s, arm[len(s):]
    raise SystemExit(f"unknown arm {arm!r}; expected self, real or "
                     f"<{'|'.join(STRATEGIES)}><{'|'.join(BUDGETS)}>")


def seeded(iid: str, key: str, budget: int, seed: int) -> random.Random:
    h = hashlib.sha256(f"{iid}|{key}|{budget}|{seed}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def section_ranges(sc, system, user, spans, lo, hi):
    """Token ranges, relative to the span start, of the skill's sections.

    Located from the markdown headers every MedCalc skill in SRA-Bench uses.
    Returns {"D": (a, b), "F": (a, b), "E": (a, b)} with half-open ranges in
    0..m, or raises if a header is missing: a silently empty region would turn
    a location arm into a random one without anyone noticing.
    """
    prompt = sc._prompt(system, user)
    enc = sc.tok(prompt, return_offsets_mapping=True)
    offs = enc["offset_mapping"]
    base = prompt.rindex(user)
    a, b = spans["skill"]
    tlo, thi = char_to_token_span(offs, a, b, base)
    assert (tlo, thi) == (lo, hi), (
        f"skill span from offsets {(tlo, thi)} != build_item span {(lo, hi)}")
    text = user[a:b]

    def header(pat):
        m = re.search(pat, text, flags=re.M)
        return m.start() if m else None

    inputs = header(r"^### Required Inputs")
    core = header(r"^### (Computation|Scoring Criteria)\b")
    example = header(r"^### Example")
    if inputs is None or core is None or example is None:
        raise ValueError("section headers not found")
    nxt = re.search(r"^### ", text[core + 4:], flags=re.M)
    core_end = core + 4 + nxt.start() if nxt else len(text)

    def tok_range(c0, c1):
        t0, t1 = char_to_token_span(offs, a + c0, a + c1, base)
        return max(t0, lo) - lo, min(t1, hi) - lo

    return {"D": tok_range(0, inputs), "F": tok_range(core, core_end),
            "E": tok_range(example, len(text))}


def window(centre: int, budget: int, m: int) -> list[int]:
    start = min(max(centre - budget // 2, 0), m - budget)
    return list(range(start, start + budget))


def select(strategy, budget, m, iid, regions, dnorm2, seed):
    """(destination indices, source indices) inside the span, both 0..m-1."""
    if strategy == "ev":
        dst = sorted({int((j + 0.5) * m / budget) for j in range(budget)})
        assert len(dst) == budget
        return dst, dst
    if strategy in ("rn", "mx"):
        src = sorted(seeded(iid, "rn", budget, seed).sample(range(m), budget))
        if strategy == "rn":
            return src, src
        pairs = sorted(((p + m // 2) % m, p) for p in src)
        return [d for d, _ in pairs], [s for _, s in pairs]
    if strategy == "td":
        order = sorted(range(m), key=lambda p: (-dnorm2[p], p))[:budget]
        dst = sorted(order)
        return dst, dst
    if strategy in ("wf", "wd", "we"):
        a, b = regions[{"wf": "F", "wd": "D", "we": "E"}[strategy]]
        dst = window((a + b) // 2, budget, m)
        return dst, dst
    if strategy == "sn":
        src = list(range(0, m - budget))
        return [p + budget for p in src], src
    if strategy == "sb":
        src = list(range(budget, m))
        return [p - budget for p in src], src
    if strategy == "xf":
        dst = list(range(budget, m))
        return dst, dst
    if strategy == "xl":
        dst = list(range(0, m - budget))
        return dst, dst
    if strategy == "sh":
        shift = budget % m
        pairs = sorted(((p + shift) % m, p) for p in range(m))
        return [d for d, _ in pairs], [s_ for _, s_ in pairs]
    if strategy.startswith("c") and strategy[1:].isdigit():
        nb = int(strategy[1:])
        if nb > budget:
            return None
        base, extra = divmod(budget, nb)
        rng = seeded(iid, strategy, budget, seed)
        dst = []
        for i in range(nb):
            ln = base + (1 if i < extra else 0)
            lo_i = int(i * m / nb)
            hi_i = int((i + 1) * m / nb) - ln
            start = rng.randint(lo_i, max(hi_i, lo_i))
            dst.extend(range(start, min(start + ln, m)))
        dst = sorted(set(dst))
        return dst, dst
    if strategy == "wr":
        c = seeded(iid, "wr", budget, seed).randrange(m)
        dst = window(c, budget, m)
        return dst, dst
    raise AssertionError(strategy)


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="medcalcbench")
    p.add_argument("--cells", default=os.path.join(SV.DATA, "cells.json"))
    p.add_argument("--model", required=True)
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--cells-keep", default="R")
    p.add_argument("--per-calc", type=int, default=20)
    p.add_argument("--max-calcs", type=int, default=55)
    p.add_argument("--min-group", type=int, default=2)
    p.add_argument("--calcs", default="",
                   help="comma-separated calculator ids to keep; every arm here "
                        "reads only the item's own states, so filtering is safe")
    p.add_argument("--filler", default="fixedskill",
                   choices=["fixedskill", "fixed", "ctrl"])
    p.add_argument("--layer", type=int, default=8)
    p.add_argument("--layers", default="",
                   help="comma-separated layers, overriding --layer. With more "
                        "than one layer the per-arm selection record is keyed "
                        "<arm>_L<layer>. `tqall` (every position after the "
                        "span: question, instruction, template) is the "
                        "matched-receiver form of the question-span transplant.")
    p.add_argument("--arms", required=True)
    p.add_argument("--max-new", type=int, default=900)
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--dry-run", action="store_true",
                   help="tokenizer only: build every item and every selection, "
                        "print what would be written, decode nothing")
    p.add_argument("--out", required=True)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)

    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    parsed = {arm: parse_arm(arm) for arm in arms}
    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    n_cells = sum(len(v) for v in cells.values())
    from howskill import sra
    instances, skills, pairs, distractor = sra.load(a.dataset)
    SV.FIXED_DISTRACTOR_SKILL = distractor
    pool = {k: v for k, v in instances.items()
            if distractor not in v["skill_annotations"]}
    todo = pick_instances(cells, pool, [c.strip() for c in a.cells_keep.split(",")],
                          a.per_calc, a.max_calcs, a.seed, min_group=a.min_group)
    if a.calcs:
        only = {c.strip() for c in a.calcs.split(",") if c.strip()}
        todo = [t for t in todo if t[0] in only]
        missing = only - {t[0] for t in todo}
        if missing:
            raise SystemExit(f"--calcs names calculators with no items: {sorted(missing)}")

    if a.dry_run:
        from transformers import AutoTokenizer
        sc = object.__new__(SpanScorer)
        sc.tok = AutoTokenizer.from_pretrained(a.model)
        sc.thinking = False
        sc.torch = None
    else:
        sc = SpanScorer(a.model, attn=a.attn)
    sc.cue = ""
    import torch

    done = resume_done(a.out) if a.resume else set()
    todo = [t for t in todo if t[2] not in done]
    print(f"{len(todo)} items to do ({len(done)} already in {a.out}), layer "
          f"{a.layer}, arms={arms}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    layers = ([int(x) for x in a.layers.split(",") if x.strip()]
              if a.layers else [a.layer])
    agg: dict[str, list] = {}
    lock = _OutputLock(a.out) if not a.dry_run else None
    fh = open(a.out, "a" if a.resume else "w", encoding="utf-8") if not a.dry_run else None
    if lock:
        lock.__enter__()
    try:
        for k, (calc, cell, iid) in enumerate(todo, 1):
            inst = instances[iid]
            it = SV.build_item(sc, inst, skills, pairs, a.arm, a.ctrl_arm,
                               filler=a.filler)
            lo, hi = it["lo"], it["hi"]
            m = hi - lo
            n = int(it["ids_g"].shape[1])
            from howskill import arms as arms_mod
            from howskill.prompts import build_prompt_spans
            sid = inst["skill_annotations"][0]
            gold = arms_mod.build(a.arm, skills.get(sid),
                                  neutral_for=skills.get(pairs.get(sid)), seed=0)
            sg, ug, spg = build_prompt_spans(inst, skills=gold)
            regions = section_ranges(sc, sg, ug, spg, lo, hi)
            rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
                   "dataset": a.dataset, "model": os.path.basename(a.model.rstrip("/")),
                   "filler": a.filler, "format": "doc_first", "cells_n": n_cells,
                   "layer": layers[0] if len(layers) == 1 else layers,
                   "m": m, "n_prompt": n, "doc_start": lo,
                   "regions": {r: list(v) for r, v in regions.items()},
                   "arms": arms, "sel": {}}

            for L in layers:
                # one layer keeps the original row layout (sel[arm]); several
                # layers key everything per layer
                tag = (lambda arm: arm) if len(layers) == 1 else (
                    lambda arm, L=L: f"{arm}_L{L}")
                if a.dry_run:
                    dnorm2 = [1.0] * m
                else:
                    h_g, h_r, d = SV.capture_d(sc, it, L)
                    dnorm2 = (d.float().norm(dim=-1) ** 2).tolist()
                    tot = sum(dnorm2)
                    rec["d_energy" if len(layers) == 1 else f"d_energy_L{L}"] = tot
                tq_max = max([n - hi] + [0])

                def tq_budget(bud):
                    if bud == "all":
                        return tq_max
                    return min({"half": m // 2, "full": m}.get(bud) or int(bud),
                               tq_max)
                tail = None
                for arm in arms:
                    strat, bud = parsed[arm]
                    if strat in ("self", "real"):
                        dst = src = list(range(m))
                    elif strat == "tq":
                        B = tq_budget(bud)
                        pos = list(range(n - B, n))
                        info = {"n": B}
                        if not a.dry_run:
                            if tail is None or tail[0] < B:
                                want = max(tq_budget(b) for s_, b in
                                           parsed.values() if s_ == "tq")
                                tp = list(range(n - want, n))
                                hg_t = sc.capture_ids(it["ids_g"], L, tp).float()
                                hr_t = sc.capture_ids(it["ids_r"], L, tp).float()
                                tail = (want, hg_t, hr_t)
                            want, hg_t, hr_t = tail
                            donor = hg_t[want - B:]
                            info["e"] = float(((hg_t[want - B:] - hr_t[want - B:])
                                               .norm(dim=-1) ** 2).sum()) / max(tot, 1e-9)
                            ok = graded(sc.decode_ids(it["ids_r"], L, pos,
                                                      donor.to(sc.device), a.max_new),
                                        inst, "cot")
                            rec[f"ok_{arm}_L{L}"] = ok
                            agg.setdefault(tag(arm), []).append(ok)
                        rec["sel"][tag(arm)] = info
                        continue
                    else:
                        B = {"half": m // 2, "full": m}.get(bud) or int(bud)
                        sel_ = select(strat, B, m, iid, regions, dnorm2, a.seed)
                        if sel_ is None:       # e.g. more blocks than budget
                            continue
                        dst, src = sel_
                    info = {"n": len(dst)}
                    for r, (ra, rb) in regions.items():
                        info[r] = sum(ra <= q < rb for q in dst) / len(dst)
                    if len(dst) <= 16:
                        info["dst"] = dst
                        if src != dst:
                            info["src"] = src
                    if not a.dry_run:
                        info["e"] = sum(dnorm2[q] for q in src) / max(tot, 1e-9)
                        if strat == "self":
                            donor = h_r
                        else:
                            donor = h_r[dst].float() + d[src].float()
                        ok = graded(sc.decode_ids(it["ids_r"], L,
                                                  [lo + q for q in dst],
                                                  donor.to(sc.device), a.max_new),
                                    inst, "cot")
                        rec[f"ok_{arm}_L{L}"] = ok
                        agg.setdefault(tag(arm), []).append(ok)
                    rec["sel"][tag(arm)] = info
            if a.dry_run:
                if k <= 3 or k == len(todo):
                    print(json.dumps({x: rec[x] for x in
                                      ("instance_id", "calculator_id", "m",
                                       "n_prompt", "regions")}))
                    print("   ", {arm: {kk: vv for kk, vv in v.items()
                                         if kk in ("n", "F", "D", "E")}
                                  for arm, v in rec["sel"].items()})
                continue
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            line = "  ".join(f"{x} {sum(v)/len(v):.2f}" for x, v in agg.items())
            print(f"  [{k}/{len(todo)} {calc}] {iid} m={m}  {line}", flush=True)
    finally:
        if fh:
            fh.close()
        if lock:
            lock.__exit__(None, None, None)
    if not a.dry_run:
        print("\n=== summary (raw accuracy, unrestricted) ===")
        for x, v in agg.items():
            print(f"  {x:10s} n={len(v):3d}  {sum(v)/len(v):.3f}")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
