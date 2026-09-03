#!/usr/bin/env python3
"""
E1: attention knockout across layers. Where does the model read the skill?

Block every position's attention into the skill's token span, one layer (or one
group of layers) at a time, and measure how much the gold answer's logprob falls.
The layers where it falls most are the layers that actually read the skill.

The control is the whole design. Blocking a span perturbs attention no matter
what the span contains, and the size of that perturbation scales with how many
keys are blocked. So the prompt carries a neutral filler document alongside the
skill, and every layer is measured twice:

    effect  = lp(unblocked) - lp(skill span blocked)
    control = lp(unblocked) - lp(filler span blocked)
    net     = effect - control

Only `net` is interpretable. Reporting `effect` alone would credit the skill for
damage that blocking any span of that length does.

Two things the control has to get right, both of which were wrong here once:

  what is blocked   The ENTIRE skill body, not a prefix of it. An earlier
                    version located the span of the first 400 characters, which
                    for every skill in this repo is the YAML frontmatter and the
                    opening heading -- the conversion table, the constants and
                    the decision procedure all sat outside the blocked span. That
                    version could only have reported "no layer depends on the
                    skill", and it would have looked like a finding.
  where it sits     Blocking an early span is not the same perturbation as
                    blocking a late one, so with a fixed document order the
                    position of the two documents is confounded with their
                    content: net = content + a position term whose sign the
                    order sets. Averaging both orders cancels that term.
                    --order both (the default) does the averaging WITHIN each
                    item. The earlier default, --order alternate, did it across
                    items, which is equally unbiased but makes the cancellation
                    carry the difference between two halves of the item set --
                    and on Tier A the position term (+0.100) was larger than
                    the content term (+0.083), so that penalty is what put zero
                    inside the interval. The two orders are still reported
                    separately at the peak, and opposite signs there are the
                    counterbalance working, not a broken measurement.

The filler is blocked at exactly the skill's token count, taken from the filler's
start. That requires the filler to be the longer document; if it is not, the run
stops rather than quietly shrinking the skill side to match.

Read it against E2. If E2 showed the effect compresses into a vector, E1 is a
check and the interesting layers should be early. If E2 showed it does not, E1 is
the main line: sustained dependence in the middle and later layers is what
retrieval looks like.

    python e1_knockout.py --model ../models/Qwen3-1.7B \
        --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md \
        --mode mc --limit 40 --run-id e1-tierA

    # coarse first pass at 8B, then re-run --group 1 over the hot region
    python e1_knockout.py --model ../models/Qwen3-8B \
        --tasks tasks/tier_b/tasks.filtered.pchem-constants.jsonl \
        --skill tasks/tier_b/SKILL.pchem-constants.md \
        --mode num --limit 60 --group 4 --run-id e1-tierB-const

Same precondition as E2: the Phase 0 gate must have passed for this pair. If the
skill does not change behaviour, there is no dependence to localise.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import random
import time

import torch

import model as M

HERE = pathlib.Path(__file__).resolve().parent
FILLER = HERE / "tasks" / "filler-neutral.md"


def load_tasks(path, limit=None):
    items = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return items[:limit] if limit else items


def fields(item, mode):
    if "question_mc" in item:
        if mode == "mc":
            return item["question_mc"], item["answer_mc"], None
        # Tier B v2 is multiple-choice only: its answer is "which setup",
        # which has no numeric form. Saying so beats a KeyError three
        # frames down on a field the caller never knew existed.
        if "question_num" not in item:
            raise SystemExit(
                f"[FAIL] {item['id']} has no numeric form -- this task set "
                f"is multiple-choice only. Run it with --mode mc.")
        return item["question_num"], item["answer_num"], None
    return item["question"], item["answer_raw"], item.get("unit") or None


@torch.no_grad()
def logprob_blocked(r, ids, answer, layers=None, blocked=None):
    """Gold-answer logprob, optionally blocking key ranges at the given layers."""
    ans_ids = r.tok(answer, return_tensors="pt",
                    add_special_tokens=False).input_ids.to(r.device)
    full = torch.cat([ids, ans_ids], dim=1)

    if blocked is None:
        logits = r.model(full, use_cache=False).logits.float()
        fired = None
    else:
        with M.knockout_layers(r, layers, blocked, full.shape[1]) as f:
            logits = r.model(full, use_cache=False).logits.float()
        fired = f["n"]

    lp = torch.log_softmax(logits[:, :-1], dim=-1)
    picked = lp.gather(-1, full[:, 1:].unsqueeze(-1)).squeeze(-1)
    return picked[0, -ans_ids.shape[1]:].mean().item(), fired


def bootstrap_ci(vals, n=2000, seed=0):
    if not vals:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    k = len(vals)
    means = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k
                   for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def sparkline(vals) -> str:
    chars = " .:-=+*#%@"
    fin = [v for v in vals if v == v]
    if not fin:
        return ""
    lo, hi = min(fin), max(fin)
    rng = (hi - lo) or 1.0
    return "".join(chars[min(9, max(0, int((v - lo) / rng * 9)))] if v == v else "?"
                   for v in vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--group", type=int, default=1,
                    help="layers knocked out together; 4 for a coarse first pass")
    ap.add_argument("--order", choices=["both", "alternate", "skill-first",
                                        "filler-first"],
                    default="both",
                    help="document order in the prompt. 'both' runs every item "
                         "in both orders and averages them, so the position "
                         "term cancels WITHIN each item; 'alternate' splits the "
                         "item set and cancels it across items, which is "
                         "unbiased but pays a between-item variance penalty "
                         "(HANDOFF 12.3u). 'both' costs twice the forwards.")
    ap.add_argument("--gate-unconfirmed", action="store_true",
                    help="the Phase 0 effect this experiment divides by was NOT "
                         "confirmed. Runs anyway, but marks the result: a "
                         "ratio over a denominator whose CI contains zero "
                         "is undefined, not small. The curve SHAPE stays "
                         "diagnostic; the ratio does not.")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = load_tasks(args.tasks, args.limit)
    skill_body = pathlib.Path(args.skill).read_text(encoding="utf-8")
    filler_body = FILLER.read_text(encoding="utf-8")
    skill_name = pathlib.Path(args.skill).stem.replace("SKILL.", "")

    # Both documents are in the prompt for every measurement, so the two
    # conditions differ only in which span is blocked -- not in what the model
    # was given to read.
    skill_doc = f"\n# Skill: {skill_name}\n\n{skill_body}"
    filler_doc = f"\n# Skill: archive-formatting\n\n{filler_body}"

    def orders_for(i: int) -> list[str]:
        """Which document orders this item is measured under.

        Within one item the skill span and the filler span sit at different
        positions, so net = content + a position term whose sign is set by the
        order. Averaging the two orders cancels that term. 'alternate' does the
        averaging across DIFFERENT items -- unbiased, but the cancellation then
        also carries the difference between two halves of the item set, and on
        Tier A the position term (+0.100) was larger than the content term
        (+0.083), so that penalty dominated the interval. 'both' measures each
        item under each order and cancels within the item, which is what the
        design wanted in the first place.
        """
        if args.order == "both":
            return ["skill_first", "filler_first"]
        if args.order == "skill-first":
            return ["skill_first"]
        if args.order == "filler-first":
            return ["filler_first"]
        return ["skill_first" if i % 2 == 0 else "filler_first"]

    def combined_for(order: str) -> str:
        docs = ((skill_doc, filler_doc) if order == "skill_first"
                else (filler_doc, skill_doc))
        return docs[0] + docs[1]

    r = M.load(args.model, device=args.device)
    groups = [list(range(i, min(i + args.group, r.n_layers)))
              for i in range(0, r.n_layers, args.group)]

    print(f"model  : {args.model}")
    print(f"tasks  : {args.tasks}  ({len(items)} items, mode={args.mode})")
    print(f"skill  : {args.skill}")
    print(f"filler : {FILLER.name}")
    print(f"order  : {args.order}")
    print(f"groups : {len(groups)} x {args.group} layers of {r.n_layers}")
    print(f"run id : {run_id}")
    if args.gate_unconfirmed:
        print()
        print("  " + "#" * 58)
        print("  #  [!!] Phase 0 never confirmed the effect this net is read")
        print("  #  against. The knockout curve is still a real measurement --")
        print("  #  it is a difference, not a ratio -- but 'net as a share of")
        print("  #  the behavioural effect' has no trustworthy divisor.")
        print("  " + "#" * 58)
    print()
    M.write_run_info(out_dir, r, {
        "experiment": "e1_knockout", "run_id": run_id, "tasks": str(args.tasks),
        "skill": str(args.skill), "filler": str(FILLER), "mode": args.mode,
        "n_items": len(items), "group": args.group, "order": args.order,
        "gate_unconfirmed": bool(args.gate_unconfirmed),
        "dv": "answer_logprob",
    })

    # ---- pass 1: locate both spans, and the unblocked baseline ------------
    #
    # The needle is the WHOLE document body. Blocking a prefix of it answers a
    # question nobody asked: in every skill here the first few hundred
    # characters are frontmatter, so a prefix span contains the description and
    # none of the content the answer depends on.
    print("[1/2] spans + baseline")
    base, dropped = [], 0
    for i, it in enumerate(items):
        q, gold, unit = fields(it, args.mode)
        for order in orders_for(i):
            combined = combined_for(order)
            ids = M.encode(
                r, M.render(r, M.build_messages(q, combined, args.mode, unit)))
            s_span = M.find_span(r, ids, skill_body.strip())
            f_span = M.find_span(r, ids, filler_body.strip())
            if s_span is None or f_span is None:
                dropped += 1
                continue
            width = s_span[1] - s_span[0]              # the whole skill body
            if f_span[1] - f_span[0] < width:
                print(f"  [FAIL] the filler is shorter than the skill "
                      f"({f_span[1] - f_span[0]} vs {width} tokens). The control "
                      f"cannot be\n         width-matched without truncating the "
                      f"skill, which would leave its\n         content unblocked. "
                      f"Lengthen {FILLER.name} and re-run.")
                raise SystemExit(1)
            lp0, _ = logprob_blocked(r, ids, gold)
            base.append({"id": it["id"], "gold": gold, "ids": ids, "lp0": lp0,
                         "order": order,
                         "skill": (s_span[0], s_span[1]),
                         "filler": (f_span[0], f_span[0] + width),
                         "width": width})
    if dropped:
        print(f"  [!] {dropped} items dropped: a span could not be located in the "
              f"tokenised prompt")
    if not base:
        print("  [FAIL] no usable items"); raise SystemExit(1)
    # base holds one record per (item, order), so with --order both it is twice
    # the item count. Everything reported as n is the ITEM count.
    n_unique = len({b["id"] for b in base})
    n_first = sum(1 for b in base if b["order"] == "skill_first")
    print(f"  blocked width: {base[0]['width']} tokens -- the entire skill body, "
          f"matched\n                 against the same count from the filler")
    print(f"  document order: {n_first} skill-first, {len(base) - n_first} "
          f"filler-first")

    # ---- pass 2: the sweep -------------------------------------------------
    print("\n[2/2] layer sweep")
    per_group, t0 = {}, time.time()
    for gi, g in enumerate(groups):
        eff, ctl, net = [], [], []
        by_order = {"skill_first": [], "filler_first": []}
        fired_total = 0
        # Per ITEM, not per record. With --order both an item contributes two
        # records, and averaging them is what cancels the position term; a
        # bootstrap over records would resample the two halves of one item
        # independently and throw that pairing away, reporting an interval
        # narrower than the design earns.
        per_item = {}
        for b in base:
            lp_s, f1 = logprob_blocked(r, b["ids"], b["gold"], g, [b["skill"]])
            lp_f, f2 = logprob_blocked(r, b["ids"], b["gold"], g, [b["filler"]])
            fired_total += (f1 or 0) + (f2 or 0)
            e, c = b["lp0"] - lp_s, b["lp0"] - lp_f
            per_item.setdefault(b["id"], []).append((e, c))
            by_order[b["order"]].append(e - c)
        for rec in per_item.values():
            e = sum(x for x, _ in rec) / len(rec)
            c = sum(y for _, y in rec) / len(rec)
            eff.append(e); ctl.append(c); net.append(e - c)

        if fired_total == 0:
            print(f"  [FAIL] layers {g[0]}-{g[-1]}: the knockout hook never fired.")
            print("         A flat curve from a hook that does nothing looks exactly")
            print("         like no dependence. Run selftest.py check 5b.")
            raise SystemExit(1)

        per_group[gi] = {
            "layers": g,
            "effect": sum(eff) / len(eff),
            "control": sum(ctl) / len(ctl),
            "net": sum(net) / len(net),
            "net_ci95": bootstrap_ci(net),
            "net_by_order": {k: (sum(v) / len(v) if v else float("nan"))
                             for k, v in by_order.items()},
        }
        d = per_group[gi]
        el = time.time() - t0
        print(f"    layers {g[0]:>3}-{g[-1]:<3}  effect {d['effect']:+.3f}  "
              f"control {d['control']:+.3f}  net {d['net']:+.3f}"
              f"   [{gi+1}/{len(groups)}, {el:.0f}s]", flush=True)

    # ---- report ------------------------------------------------------------
    with io.open(out_dir / "per_group.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for gi in sorted(per_group):
            f.write(json.dumps(per_group[gi], ensure_ascii=False) + "\n")

    nets = [per_group[gi]["net"] for gi in sorted(per_group)]
    effs = [per_group[gi]["effect"] for gi in sorted(per_group)]
    ctls = [per_group[gi]["control"] for gi in sorted(per_group)]
    best = max(per_group, key=lambda gi: per_group[gi]["net"])
    bd = per_group[best]

    summary = {
        "experiment": "e1_knockout",
        "run_id": run_id, "n_items": n_unique, "group": args.group,
        "n_records": len(base),
        "groups": [per_group[gi]["layers"] for gi in sorted(per_group)],
        "net": nets, "effect": effs, "control": ctls,
        "best_layers": bd["layers"], "best_net": bd["net"],
        "best_net_ci95": list(bd["net_ci95"]),
        "best_net_by_order": bd["net_by_order"],
        "blocked_width_tokens": base[0]["width"],
        "order": args.order,
        "n_skill_first": n_first,
        # Travels with the numbers. E1's net is a difference, not a ratio, so an
        # unconfirmed Phase 0 hurts it less than it hurts E2 -- but the net is
        # still read against that same behavioural effect (fmt_e1 divides by it),
        # so a reader has to know the divisor was never established.
        "gate_unconfirmed": bool(args.gate_unconfirmed),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*64}")
    print(f"  {len(groups)} groups of {args.group}, n={n_unique}, "
          f"{base[0]['width']} tokens blocked")
    print(f"  effect   {sparkline(effs)}")
    print(f"  control  {sparkline(ctls)}")
    print(f"  net      {sparkline(nets)}   <- read this one")
    print(f"\n  peak: layers {bd['layers'][0]}-{bd['layers'][-1]}  "
          f"net {bd['net']:+.3f} CI95 "
          f"[{bd['net_ci95'][0]:+.3f}, {bd['net_ci95'][1]:+.3f}]")

    # The two document orders are the same measurement with the two spans swapped
    # in position. They should agree; if they do not, what the peak is tracking is
    # where the blocked span sits, not what is in it.
    bo = bd["net_by_order"]
    sf, ff = bo["skill_first"], bo["filler_first"]
    print(f"    by document order: skill-first {sf:+.3f}, filler-first {ff:+.3f}")
    if sf == sf and ff == ff:
        pos, con = (sf - ff) / 2.0, (sf + ff) / 2.0
        print(f"      position term {pos:+.3f}, content term {con:+.3f}")
        if abs(pos) >= abs(con):
            print("    [!] The position term is at least as large as the content")
            print("        term. Opposite signs here are the counterbalance doing")
            print("        its job, not a broken measurement -- net is still the")
            print("        average of the two and so is position-free. What it")
            if args.order == "both":
                print("        costs is variance, and --order both has already")
                print("        paid that down as far as this design can.")
            else:
                print("        costs is variance, and the two halves are DIFFERENT")
                print("        items. Re-run with --order both.")

    print("\n  reading it:")
    if bd["net_ci95"][0] <= 0:
        print("    The peak's CI includes zero. No layer shows dependence on the")
        print("    skill span beyond what blocking any span of this width does.")
        print("    Either the skill is not read through attention at all, or the")
        print("    behavioural effect is too small to localise -- check e0 first.")
    else:
        frac = bd["layers"][0] / r.n_layers
        where = "early" if frac < 0.33 else ("middle" if frac < 0.67 else "late")
        print(f"    Dependence peaks in the {where} layers.")
        if where == "early":
            print("    Early reading fits H2: the skill is consumed once, up front,")
            print("    and the rest of the computation proceeds without it. Consistent")
            print("    with a high E2 recovery.")
        else:
            print("    Sustained mid/late dependence fits H1: the model keeps going")
            print("    back to the text. Expect E2 recovery to be low; if it is not,")
            print("    the two results disagree and one of them is instrumentation.")
    print(f"\n  results: {out_dir}")
    print("=" * 64)


if __name__ == "__main__":
    main()
