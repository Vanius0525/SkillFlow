#!/usr/bin/env python3
"""
E10: in-place span transplant. Can the model read the skill where it sits?

E2 patches ONE position -- the last prompt token -- with the state the model had
built after reading the whole document. That asks whether the model's own
summary is portable. It cannot ask whether the document is legible from where
the document actually is, because the receiving run has no document and so has
no positions to write into.

This does. Donor and recipient are token-for-token identical except inside the
document's own span:

    donor      system: "<preamble># Skill: zorb-units\\n\\n<SKILL BODY>"  user: Q
    recipient  system: "<preamble># Skill: zorb-units\\n\\n<FILLER TEXT>" user: Q

The recipient is built by token substitution, not by rendering a different
prompt: the skill body's token span is overwritten with the same number of
tokens taken from the filler document as it is tokenised in its own prompt. Both
sequences then have identical length and identical tokens everywhere outside the
span, so every position index means the same thing in both, and RoPE phases
line up. Rendering a filler prompt instead would shift the question by the
difference in document length, and a transplanted residual would land at a
position it was never computed for.

Then, at layer L, the recipient's residuals across the whole span are replaced
by the donor's, and the run finishes normally. Everything after the span --
the question, the answer instruction, the chat suffix -- keeps its own values at
layer L and attends back to the transplanted span at layers L+1 and above.

What this measures that E2 cannot. The answer is read at the last prompt token.
For the transplant to change it, information has to travel from the span to that
position, and it can only do so through attention in the layers ABOVE L. So the
curve falls off exactly where the model stops being able to read the document,
which is E1's question asked positively -- by supplying the content rather than
by blocking it. E1 asks it by ablation and needs the effect to survive a
difference of differences; at 39 items its interval contains zero.

Preregistered prediction, written before the first run:

  1. Recovery is HIGH at early layers and falls toward zero at late ones -- the
     mirror image of E2's tail patch, which is flat early and rises late. If
     both curves were high in the same place, one of the two would be measuring
     the intervention rather than the model.
  2. The last layers read ~0. There is no attention left to carry the span to
     the answer position, so a late transplant cannot matter. This is the
     built-in negative control, and it is the one E2 does not have: E2's last
     layer reads 1.0 by construction because it writes straight through.
  3. `self` -- transplanting the recipient's own span residuals back into
     itself -- must be an exact no-op at every layer. This is the path
     self-proof, the same role the last-layer identity plays in E2.

A note on what the donor states are. The skill sits in the system message,
before the question, so under causal attention the skill tokens cannot see the
question: their residuals are IDENTICAL for every item. The script checks this
rather than assuming it, and reports the residual difference between two items.
One consequence is that this experiment has no per-item donor and therefore no
`mismatched` condition -- there is nothing to mismatch. Another is that whatever
the skill span holds, it is item-independent by construction, so any item
specificity in the result has to come from the question reading it.

    python e10_span.py --model ../models/Qwen3-1.7B \\
        --tasks tasks/tier_a/tasks.jsonl \\
        --skill tasks/tier_a/SKILL.zorb-units.md \\
        --mode mc --limit 40 --run-id e10-tierA

Cost is one forward per (item, layer, condition), the same order as E2. The
patch itself is wider -- the whole document span rather than one position -- but
`model.patch_layer` already takes a sequence of positions.
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

OPTION_IDS: dict[str, int] = {}


def load_tasks(path, limit=None):
    items = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return items[:limit] if limit else items


def fields(item, mode):
    if "question_mc" in item:
        if mode == "mc":
            return item["question_mc"], item["answer_mc"], None
        if "question_num" not in item:
            raise SystemExit(f"[FAIL] {item['id']} has no numeric form -- run "
                             f"this task set with --mode mc.")
        return item["question_num"], item["answer_num"], None
    return item["question"], item["answer_raw"], item.get("unit") or None


@torch.no_grad()
def score(r, ids, answer, layer=None, positions=None, vector=None):
    """(mean gold logprob, argmax-over-options is gold, option logprobs)."""
    ans_ids = r.tok(answer, return_tensors="pt",
                    add_special_tokens=False).input_ids.to(r.device)
    full = torch.cat([ids, ans_ids], dim=1)
    if vector is None:
        logits = r.model(full, use_cache=False).logits.float()
    else:
        with M.patch_layer(r, layer, positions, vector, prefill_only=False):
            logits = r.model(full, use_cache=False).logits.float()

    lp = torch.log_softmax(logits[:, :-1], dim=-1)
    picked = lp.gather(-1, full[:, 1:].unsqueeze(-1)).squeeze(-1)
    value = picked[0, -ans_ids.shape[1]:].mean().item()

    ok, opts = None, None
    if OPTION_IDS:
        row = logits[0, int(ids.shape[1]) - 1]
        best = max(OPTION_IDS, key=lambda t: row[OPTION_IDS[t]].item())
        ok = best == answer
        rl = torch.log_softmax(row.float(), dim=-1)
        opts = {t: float(rl[i]) for t, i in OPTION_IDS.items()}
        opts["_best"] = best
    return value, ok, opts


@torch.no_grad()
def score_all_layers(r, ids, answer, layers, positions, vecs):
    """The same measurement with the span replaced at EVERY layer at once.

    The ceiling for the sweep, and the control that says what a flat or zero
    sweep means. Patching one layer leaves the span inconsistent above it: the
    transplanted states are the skill's, but the layers above recompute from a
    context that is otherwise the recipient's. Replacing every layer removes
    that inconsistency, so the span simply IS the skill's representation at all
    depths and the question attends to it normally.

      near the with-skill baseline -> the transplant mechanism works, and the
                                      single-layer curve is measuring where one
                                      layer's worth of it suffices
      far below it                 -> the mechanism itself does not carry, and
                                      no reading of the sweep is safe

    One forward per item rather than per layer, so it costs nothing next to the
    sweep.
    """
    import contextlib
    ans_ids = r.tok(answer, return_tensors="pt",
                    add_special_tokens=False).input_ids.to(r.device)
    full = torch.cat([ids, ans_ids], dim=1)
    with contextlib.ExitStack() as st:
        for L in layers:
            st.enter_context(M.patch_layer(r, L, positions, vecs[L],
                                           prefill_only=False))
        logits = r.model(full, use_cache=False).logits.float()
    lp = torch.log_softmax(logits[:, :-1], dim=-1)
    picked = lp.gather(-1, full[:, 1:].unsqueeze(-1)).squeeze(-1)
    value = picked[0, -ans_ids.shape[1]:].mean().item()
    ok = None
    if OPTION_IDS:
        row = logits[0, int(ids.shape[1]) - 1]
        ok = max(OPTION_IDS, key=lambda t: row[OPTION_IDS[t]].item()) == answer
    return value, ok


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
    return "".join(chars[min(9, max(0, int((v - lo) / rng * 9)))] if v == v
                   else "?" for v in vals)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--mode", choices=["mc", "num"], required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--layer-step", type=int, default=1)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    filler = M.load_skill(FILLER)
    skill_body = pathlib.Path(args.skill).read_text(encoding="utf-8").strip()
    filler_body = FILLER.read_text(encoding="utf-8").strip()

    r = M.load(args.model, device=args.device)
    layers = list(range(0, r.n_layers, args.layer_step))

    if args.mode == "mc":
        for letter in "ABCD":
            t = r.tok(letter, add_special_tokens=False).input_ids
            if len(t) == 1:
                OPTION_IDS[letter] = int(t[0])
        if len(OPTION_IDS) != 4:
            print("  [!] option letters are not single tokens here -- the "
                  "accuracy curve is disabled.")
            OPTION_IDS.clear()

    print(f"model  : {args.model}   {r.n_layers} layers")
    print(f"skill  : {args.skill}")
    print(f"filler : {FILLER}  (the tokens the span is overwritten WITH in the "
          f"recipient)")
    M.write_run_info(out_dir, r, {
        "experiment": "e10_span", "run_id": run_id, "tasks": str(args.tasks),
        "skill": str(args.skill), "filler": str(FILLER), "mode": args.mode,
        "n_items": len(items), "layer_step": args.layer_step,
        "dv": "answer_logprob + option argmax",
    })

    # ---- pass 1: build the aligned pair, cache the donor states ------------
    #
    # The span states are cached ONCE, not per item. The skill sits in the
    # system message ahead of the question, so under causal attention its
    # residuals cannot depend on which item this is -- and storing them per item
    # would be 688 x 2048 x 28 floats each, 158 MB, or 12 GB across 39 items and
    # two conditions. The independence is checked on the first two items below,
    # and the run stops if it does not hold, because everything after that point
    # would be using item 0's states for every item.
    print("\n[1/2] aligned prompts + donor states")
    base, dropped = [], 0
    donor = recip = None
    probe = []                       # (donor, recip) for the first two items
    for i, it in enumerate(items):
        q, gold, unit = fields(it, args.mode)
        ids_s = M.encode(r, M.render(r, M.build_messages(q, skill, args.mode, unit)))
        ids_f = M.encode(r, M.render(r, M.build_messages(q, filler, args.mode, unit)))
        s_span = M.find_span(r, ids_s, skill_body)
        f_span = M.find_span(r, ids_f, filler_body)
        if s_span is None or f_span is None:
            dropped += 1
            continue
        width = s_span[1] - s_span[0]
        if f_span[1] - f_span[0] < width:
            raise SystemExit(
                f"[FAIL] the filler is shorter than the skill "
                f"({f_span[1] - f_span[0]} vs {width} tokens). The recipient "
                f"cannot be built without truncating the skill's span, which "
                f"would leave part of the skill in place. Lengthen "
                f"{FILLER.name} and re-run.")

        # Token substitution: identical everywhere outside the span, identical
        # length, so every position index means the same thing in both runs.
        ids_c = ids_s.clone()
        ids_c[0, s_span[0]:s_span[1]] = ids_f[0, f_span[0]:f_span[0] + width]
        assert ids_c.shape == ids_s.shape

        lp_hi, ok_hi, op_hi = score(r, ids_s, gold)
        lp_lo, ok_lo, op_lo = score(r, ids_c, gold)

        # The span states. Captured through the same hook the patch writes
        # into, exactly as E2 does, so the two agree by construction. Taken on
        # the first two items only: the first pair is what the sweep uses, the
        # second exists to test the independence claim.
        if len(probe) < 2:
            probe.append((M.capture_block_outputs(r, ids_s, layers, span=s_span),
                          M.capture_block_outputs(r, ids_c, layers, span=s_span)))
            if donor is None:
                donor, recip = probe[0]

        # The ceiling: every layer replaced at once, one forward per item.
        lp_all, ok_all = score_all_layers(
            r, ids_c, gold, layers, list(range(s_span[0], s_span[1])), donor)

        base.append({"id": it["id"], "gold": gold, "ids_c": ids_c,
                     "span": (s_span[0], s_span[1]), "width": width,
                     "lp_hi": lp_hi, "lp_lo": lp_lo, "lp_all": lp_all,
                     "ok_hi": ok_hi, "ok_lo": ok_lo, "ok_all": ok_all,
                     "opt_hi": op_hi, "opt_lo": op_lo})
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(items)}", flush=True)

    if dropped:
        print(f"  [!] {dropped} items dropped: a span could not be located")
    if not base:
        raise SystemExit("[FAIL] no usable items")

    b0 = base[0]
    print(f"  span   : {b0['span'][0]}..{b0['span'][1]}  "
          f"({b0['width']} tokens, the whole skill body)")

    # The skill sits in the system message, ahead of the question, so under
    # causal attention its residuals cannot depend on which item this is. That
    # is a claim about the architecture; check it rather than trust it, because
    # if it fails the donor states are not what this experiment says they are.
    if not all(b["span"] == b0["span"] for b in base):
        raise SystemExit(
            "[FAIL] the skill's span sits at different positions for different "
            "items. The\n       system block should be identical across items, "
            "so this means the prompt is\n       not built the way this "
            "experiment assumes. Stopping.")
    drift = float("nan")
    if len(probe) > 1:
        mid = layers[len(layers) // 2]
        drift = max(float((probe[0][j][L] - probe[1][j][L]).abs().max())
                    for j in (0, 1) for L in (layers[0], mid, layers[-1]))
        print(f"  item-independence check (layers {layers[0]}, {mid}, "
              f"{layers[-1]}): max|d| = {drift:.2e}")
        if drift > 1e-3:
            raise SystemExit(
                f"[FAIL] the span states differ across items by {drift:.2e}. "
                "Under causal\n       attention the skill sits ahead of the "
                "question and cannot see it, so this\n       should be zero. "
                "One shared cache is used for every item, which would\n"
                "       now be wrong. Stopping rather than reporting it.")
        probe = probe[:1]            # release the second item's 316 MB

    # ---- pass 2: the sweep -------------------------------------------------
    print("\n[2/2] layer sweep")
    per_layer, t0 = {}, time.time()
    for n, L in enumerate(layers):
        rows = []
        for b in base:
            pos = list(range(b["span"][0], b["span"][1]))
            lp_r, ok_r, op_r = score(r, b["ids_c"], b["gold"], L, pos,
                                     donor[L])
            lp_s, ok_s, op_s = score(r, b["ids_c"], b["gold"], L, pos,
                                     recip[L])
            rows.append({"id": b["id"],
                         "lp_real": lp_r, "lp_self": lp_s,
                         "lp_lo": b["lp_lo"], "lp_hi": b["lp_hi"],
                         "ok_real": ok_r, "ok_self": ok_s,
                         "ok_lo": b["ok_lo"], "ok_hi": b["ok_hi"],
                         "opt_real": op_r, "opt_self": op_s,
                         "opt_lo": b["opt_lo"], "opt_hi": b["opt_hi"]})

        # Denominator is skill minus RECIPIENT, not skill minus nothing. Both
        # runs carry a document of the same length in the same place, so this
        # ratio is about content from the start and does not have to be
        # corrected for presence afterwards the way E2's does.
        def recov(key):
            num = sum(x[key] - x["lp_lo"] for x in rows) / len(rows)
            den = sum(x["lp_hi"] - x["lp_lo"] for x in rows) / len(rows)
            return num / den if abs(den) > 1e-6 else float("nan")

        def acc(key):
            got = [x["ok_" + key] for x in rows if x.get("ok_" + key) is not None]
            return sum(got) / len(got) if got else float("nan")

        # The self condition is an identity, so its deviation is measured in
        # nats rather than reported as a recovery: a ratio would divide a
        # rounding error by a small denominator and print something alarming.
        self_dev = max(abs(x["lp_self"] - x["lp_lo"]) for x in rows)
        per_layer[L] = {
            "layer": L, "rows": rows,
            "recovery": recov("lp_real"),
            # The interval is on the NUMERATOR in nats, not on the ratio: a
            # ratio resampled over items inherits the denominator's spread as
            # well, and the numerator is what the sweep actually measures.
            "delta_nats_ci95": list(bootstrap_ci(
                [x["lp_real"] - x["lp_lo"] for x in rows])),
            "acc": {"real": acc("real"), "self": acc("self"),
                    "lo": acc("lo"), "hi": acc("hi")},
            "self_max_dev_nats": self_dev,
        }
        d = per_layer[L]
        flag = "" if self_dev < 1e-4 else f"   [SELF DEV {self_dev:.3e}]"
        a = d["acc"]["real"]
        print(f"    layer {L:>3}  recovery {d['recovery']:+.3f}  "
              f"acc {a:.3f}{flag}   [{n+1}/{len(layers)}, "
              f"{time.time()-t0:.0f}s]", flush=True)

    # ---- report ------------------------------------------------------------
    with io.open(out_dir / "per_layer_span.jsonl", "w", encoding="utf-8",
                 newline="\n") as f:
        for L in layers:
            f.write(json.dumps(per_layer[L], ensure_ascii=False) + "\n")

    curve = [per_layer[L]["recovery"] for L in layers]
    accs = [per_layer[L]["acc"]["real"] for L in layers]
    worst_self = max(per_layer[L]["self_max_dev_nats"] for L in layers)
    a_lo, a_hi = per_layer[layers[0]]["acc"]["lo"], per_layer[layers[0]]["acc"]["hi"]

    n = len(base)
    lp_all = sum(b["lp_all"] for b in base) / n
    lp_lo_m = sum(b["lp_lo"] for b in base) / n
    lp_hi_m = sum(b["lp_hi"] for b in base) / n
    acc_all = (sum(b["ok_all"] for b in base) / n
               if base[0]["ok_all"] is not None else float("nan"))
    rec_all = ((lp_all - lp_lo_m) / (lp_hi_m - lp_lo_m)
               if abs(lp_hi_m - lp_lo_m) > 1e-6 else float("nan"))

    summary = {
        "experiment": "e10_span", "run_id": run_id,
        "n_items": len(base), "layers": layers,
        "span_width_tokens": b0["width"],
        "recovery": curve, "acc_real": accs,
        "acc_lo": a_lo, "acc_hi": a_hi,
        "recovery_all_layers": rec_all, "acc_all_layers": acc_all,
        "acc_self": [per_layer[L]["acc"]["self"] for L in layers],
        "self_max_dev_nats": worst_self,
        "donor_item_drift": drift,
        "mean_logprob_delta": (sum(x["lp_hi"] - x["lp_lo"] for x in
                                   per_layer[layers[0]]["rows"]) / len(base)),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'=' * 64}")
    print(f"  n={len(base)}   span {b0['width']} tokens   layers "
          f"{layers[0]}..{layers[-1]}")
    print(f"  recovery  {sparkline(curve)}")
    print(f"  accuracy  {sparkline(accs)}   recipient {a_lo:.3f} -> "
          f"donor {a_hi:.3f}")
    print(f"\n  ceiling (every layer replaced at once): recovery "
          f"{rec_all:+.3f}   acc {acc_all:.3f}")
    if rec_all < 0.5:
        print("    [!] Even replacing the span at EVERY layer does not bring "
              "the effect back.")
        print("        The transplant mechanism itself is not carrying, so a "
              "flat or zero")
        print("        single-layer curve says nothing about which layers read "
              "the document.")
    else:
        print("    The mechanism carries, so the single-layer curve below is "
              "measuring")
        print("    where one layer's worth of it is enough.")
    print(f"\n  path self-proof: worst `self` deviation {worst_self:.3e} nats "
          f"({'OK' if worst_self < 1e-4 else 'BROKEN -- read nothing above'})")

    print("\n  reading it (predictions were written before the run):")
    early = [c for L, c in zip(layers, curve) if L < r.n_layers // 3]
    late = [c for L, c in zip(layers, curve) if L >= 2 * r.n_layers // 3]
    me = sum(early) / len(early) if early else float("nan")
    ml = sum(late) / len(late) if late else float("nan")
    print(f"    early third {me:+.3f}   late third {ml:+.3f}")
    if me > ml + 0.2:
        print("    Falls with depth, as predicted: the transplant works while")
        print("    there are still layers in which the question can attend back")
        print("    to the span, and stops working when there are not. The layer")
        print("    it dies at is the last one at which this model can read the")
        print("    document -- E1's question, answered by supplying content")
        print("    rather than by blocking it.")
    elif ml > me + 0.2:
        print("    RISES with depth, which the design did not predict. A late")
        print("    transplant has no attention left to reach the answer")
        print("    position, so a rising curve is more likely to be the patch")
        print("    disturbing the forward pass than the model reading the span.")
        print("    Check the accuracy curve and the option margins before")
        print("    interpreting any of it.")
    else:
        print("    Flat. Either the span is not read at any layer, or the")
        print("    transplant is not reaching the answer position at all --")
        print("    the `self` deviation above separates those two.")


if __name__ == "__main__":
    main()
