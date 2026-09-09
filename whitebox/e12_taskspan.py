#!/usr/bin/env python
"""
E12 -- where does the content go after the document stops being readable?

THE GAP THIS FILLS

Three channels now bracket the same transition from opposite sides:

  layers 0-10   E10 transplants the skill's OWN token residuals into an
                equal-length filler prompt and recovers the skill's accuracy
                (0.436 at layers 3-4 against a 0.154 receiver baseline).
                At layer 11 it falls off a cliff and never comes back.
  layers 11-20  nothing covers this, and the 'forward pass is damaged' band
                (17-20, HANDOFF 12.3t) sits inside it.
  layers 21+    E2 and E11 patch the LAST PROMPT POSITION and work there,
                item-specifically: another item's vector carries that item's
                answer (p=0.020), the neutral document's vector fixes 0 of 13.

So the content is in the document's own tokens early and in the last prompt
position late. Something moves it. The obvious carrier is the QUESTION's own
tokens: they are the only positions that (a) attend to the skill and (b) are
attended to by the last position.

WHAT THIS PATCHES

The receiver is built exactly as E10 builds it -- the skill's tokens replaced
by an equal-length slice of the neutral filler -- so both sequences have the
same length, are token-identical outside the skill span, and have aligned RoPE
phases. E12 then transplants the residuals at the QUESTION span instead of the
skill span.

The question span is not the last prompt token. The last prompt token lives in
the chat suffix, after the user turn ends, which is where E2 and E11 write. So
E12 is a different position, not a superset of E2, and the three windows can be
laid side by side on one axis.

PREDICTION, WRITTEN BEFORE THE RUN

If the content is relayed skill span -> question span -> last position, the
question-span curve should peak in a window LATER than E10's (0-10) and EARLIER
than E2's (21+), i.e. somewhere in 11-20. If instead it looks like E10's curve
shifted by nothing, the question tokens are not the carrier and the transfer
happens directly into the final position.

The `self` arm is the pathway self-proof: donor and receiver are the same
forward, so every layer must be an exact no-op. E10's self arm read 0.0 nats
deviation at all 28 layers; anything else here means the patch is not writing
where the capture read.

    python e12_taskspan.py --model ../models/Qwen3-1.7B \\
      --tasks tasks/tier_a/tasks.jsonl \\
      --skill tasks/tier_a/SKILL.zorb-units.md --mode mc \\
      --run-id <id>/e12-tierA
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import torch

import model as M
import e10_span as E10

HERE = pathlib.Path(__file__).resolve().parent


@torch.no_grad()
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--layer-step", type=int, default=1)
    ap.add_argument("--dtype", default=None,
                    help="float32 or bfloat16. REQUIRED in practice: the self "
                         "arm is algebraically an exact no-op, and under "
                         "bfloat16 it still reads ~0.66 nats off because the "
                         "capture forward and the scoring forward have "
                         "different sequence lengths and reduce in a different "
                         "order (HANDOFF 12.3q). Left unset it follows "
                         "$WB_DTYPE and then bfloat16, which is how the first "
                         "run of this script tripped the self-arm warning.")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    if args.dtype:
        import os
        os.environ["WB_DTYPE"] = args.dtype

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = E10.load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    filler = M.load_skill(E10.FILLER)
    skill_body = pathlib.Path(args.skill).read_text(encoding="utf-8").strip()
    filler_body = E10.FILLER.read_text(encoding="utf-8").strip()

    r = M.load(args.model, device=args.device)
    layers = list(range(0, r.n_layers, args.layer_step))
    all_layers = list(range(r.n_layers))

    E10.OPTION_IDS.clear()
    if args.mode == "mc":
        for letter in "ABCD":
            t = r.tok(letter, add_special_tokens=False).input_ids
            if len(t) == 1:
                E10.OPTION_IDS[letter] = int(t[0])
        if len(E10.OPTION_IDS) != 4:
            print("  [!] option letters are not single tokens -- accuracy off.")
            E10.OPTION_IDS.clear()

    print(f"model  : {args.model}   {r.n_layers} layers")
    print(f"skill  : {args.skill}")
    print(f"filler : {E10.FILLER}  (what the skill's tokens become in the "
          f"receiver)")
    print(f"patch  : the QUESTION span, not the skill span and not the last "
          f"prompt token")
    print(f"run id : {run_id}")
    M.write_run_info(out_dir, r, {
        "experiment": "e12_taskspan", "run_id": run_id,
        "tasks": str(args.tasks), "skill": str(args.skill),
        "filler": str(E10.FILLER), "mode": args.mode, "n_items": len(items),
        "layer_step": args.layer_step, "dv": "answer_logprob + option argmax",
    })

    # ---- the sweep, one item at a time -------------------------------------
    #
    # Unlike E10's skill span, the QUESTION span's residuals depend on the item
    # -- that is the whole point, they are downstream of both the skill and the
    # question. So they are captured per item and discarded before the next
    # one: n_layers x width x d in float32 is ~25 MB per item at 1.7B, which is
    # fine one at a time and 1 GB if kept for all 39.
    print("\n[1/1] per-item capture + layer sweep")
    n_layers = r.n_layers
    hit_real = {L: [] for L in layers}
    hit_self = {L: [] for L in layers}
    lp_real = {L: [] for L in layers}
    hi_ok, lo_ok, hi_lp, lo_lp = [], [], [], []
    ceil_ok, self_dev = [], 0.0
    widths, dropped, rows = [], 0, []
    t0 = time.time()

    for i, it in enumerate(items):
        q, gold, unit = E10.fields(it, args.mode)
        ids_s = M.encode(r, M.render(r, M.build_messages(q, skill, args.mode, unit)))
        ids_f = M.encode(r, M.render(r, M.build_messages(q, filler, args.mode, unit)))
        s_span = M.find_span(r, ids_s, skill_body)
        f_span = M.find_span(r, ids_f, filler_body)
        q_span = M.find_span(r, ids_s, q)
        if s_span is None or f_span is None or q_span is None:
            dropped += 1
            continue
        width = s_span[1] - s_span[0]
        if f_span[1] - f_span[0] < width:
            raise SystemExit("[FAIL] filler shorter than skill; see e10_span.")

        ids_c = ids_s.clone()
        ids_c[0, s_span[0]:s_span[1]] = ids_f[0, f_span[0]:f_span[0] + width]

        # The question sits after the skill in the prompt and the substitution
        # preserves length, so q_span indexes the same tokens in both. Assert
        # it rather than trust it: a mismatch here would silently transplant
        # one item's question onto another position.
        assert torch.equal(ids_c[0, q_span[0]:q_span[1]],
                           ids_s[0, q_span[0]:q_span[1]]), \
            "the question tokens differ between donor and receiver"
        widths.append(q_span[1] - q_span[0])

        lp_hi, ok_hi, _ = E10.score(r, ids_s, gold)
        lp_lo, ok_lo, _ = E10.score(r, ids_c, gold)
        hi_ok.append(bool(ok_hi)); lo_ok.append(bool(ok_lo))
        hi_lp.append(lp_hi); lo_lp.append(lp_lo)

        v_donor = M.capture_block_outputs(r, ids_s, all_layers, span=q_span)
        v_recip = M.capture_block_outputs(r, ids_c, all_layers, span=q_span)
        pos = list(range(q_span[0], q_span[1]))

        for L in layers:
            lp_r, ok_r, _ = E10.score(r, ids_c, gold, L, pos, v_donor[L])
            lp_s, ok_s, _ = E10.score(r, ids_c, gold, L, pos, v_recip[L])
            hit_real[L].append(bool(ok_r)); hit_self[L].append(bool(ok_s))
            lp_real[L].append(lp_r)
            self_dev = max(self_dev, abs(lp_s - lp_lo))

        # ceiling: every layer at once, so the span cannot recompute in a gap
        # score_all_layers returns (logprob, ok) -- two values, unlike score()
        lp_c, ok_c = E10.score_all_layers(r, ids_c, gold, all_layers, pos,
                                          v_donor)
        ceil_ok.append(bool(ok_c))
        rows.append({"id": it["id"], "gold": gold,
                     "q_span": list(q_span), "skill_span": list(s_span),
                     "lp_hi": lp_hi, "lp_lo": lp_lo, "ok_hi": bool(ok_hi),
                     "ok_lo": bool(ok_lo), "ok_ceiling": bool(ok_c)})
        del v_donor, v_recip
        if (i + 1) % 5 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s "
                  f"({el/(i+1):.1f}s/item)", flush=True)

    n = len(rows)
    if not n:
        raise SystemExit("[FAIL] every item was dropped -- check --skill.")
    acc_hi = sum(hi_ok) / n
    acc_lo = sum(lo_ok) / n
    mean_hi = sum(hi_lp) / n
    mean_lo = sum(lo_lp) / n
    span_lp = mean_hi - mean_lo

    def recov(L):
        got = sum(lp_real[L]) / n - mean_lo
        return got / span_lp if abs(span_lp) > 1e-9 else float("nan")

    print("\n" + "=" * 74)
    print(f"  E12 question-span transplant   n={n}  dropped={dropped}")
    print("=" * 74)
    print(f"  question span: {min(widths)}-{max(widths)} tokens "
          f"(skill span was {width})")
    print(f"  receiver (filler tokens) acc {acc_lo:.3f}   "
          f"donor (real skill) acc {acc_hi:.3f}")
    print(f"  ceiling (all {n_layers} layers at once) acc "
          f"{sum(ceil_ok)/n:.3f}")
    print(f"  self-transplant max deviation: {self_dev:.6f} nats")
    if self_dev > 1e-3:
        print("  [!] the self arm is NOT a no-op. The patch is not writing "
              "where the capture read -- every number below is suspect.")
    print()
    print("  layer   recovery   acc_real   acc_self")
    for L in layers:
        print(f"  {L:5d}   {recov(L):+8.3f}   "
              f"{sum(hit_real[L])/n:8.3f}   {sum(hit_self[L])/n:8.3f}")

    summary = {"experiment": "e12_taskspan", "run_id": run_id, "n_items": n,
               "dropped": dropped, "layers": layers,
               "q_span_tokens": [min(widths), max(widths)],
               "skill_span_tokens": width,
               "acc_lo": acc_lo, "acc_hi": acc_hi,
               "acc_ceiling": sum(ceil_ok) / n,
               "self_max_dev_nats": self_dev,
               "recovery": [recov(L) for L in layers],
               "acc_real": [sum(hit_real[L]) / n for L in layers],
               "acc_self": [sum(hit_self[L]) / n for L in layers],
               "mean_logprob_delta": span_lp}
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(out_dir / "items.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n  results: {out_dir}")


if __name__ == "__main__":
    main()
