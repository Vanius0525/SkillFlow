#!/usr/bin/env python
"""
E13 -- who reads the skill: the question's tokens, or the final position?

WHAT E10/E12/E2 LEFT OPEN

Three transplant windows now sit in order on one axis: the skill's own tokens
carry the content through layer 10 (E10), the question's tokens carry it across
11-16 (E12), and the last prompt position carries it from 21 on (E2, E11). The
hand-off at layer 11 is visible from both sides -- E10 drops 0.308 -> 0.128
there while E12 rises 0.231 -> 0.308.

That is a description of WHERE the content is, not of HOW it moves. Transplants
show that a position's state suffices; they cannot show that the model actually
routes through it. Attention is the only mechanism that can move content
between positions in a decoder, so the routing question has a direct test:
block the attention and see what breaks.

THE CONTRAST THAT MATTERS

E1 already blocks attention into the skill span, but from EVERY query position
at once, so it answers "does the model need this text" and not "which positions
read it". Splitting the query side is what separates the two candidate routes:

    relay        skill span --attn--> question tokens --> ... --> last position
    direct       skill span --------------attn------------------> last position

Under the relay, blocking QUESTION -> SKILL should hurt and blocking
LAST -> SKILL should not add much. Under the direct route it is the other way
round. Both can be true at once, and the sizes then say how much rides on each.

ARMS (each is a rectangular block of the attention matrix, one layer at a time)

    all_to_skill      every query   -> skill span      E1's arm, for scale
    q_to_skill        question span -> skill span      the relay
    last_to_skill     last prompt position -> skill    the direct route
    q_to_random       question span -> a same-width non-skill key span
    lastq_to_skill    a same-width query window that is NOT the question,
                      placed after the skill -> skill span

The last two are the controls that keep a positive result from being "blocking
anything hurts": q_to_random holds the query side fixed and moves the keys,
lastq_to_skill holds the keys fixed and moves the queries. A route claim needs
its arm to beat BOTH.

PRE-REGISTERED, WRITTEN BEFORE THE RUN

If the relay carries the content, q_to_skill should cost most in the layers at
and just below E12's window onset -- roughly 8-16 -- and q_to_random should be
flat there. If instead last_to_skill dominates at every depth, the question
tokens are a place the content can be READ from rather than the road it takes,
and E12's window is then a consequence of the skill span still being visible to
them, not evidence of routing.

A knockout that never fires looks exactly like one that fires and changes
nothing, so the hook's own invocation count is asserted, as in e1_knockout.

    python e13_route.py --model ../models/Qwen3-1.7B \\
      --tasks tasks/tier_a/tasks.jsonl \\
      --skill tasks/tier_a/SKILL.zorb-units.md --mode mc \\
      --dtype float32 --run-id <id>/e13-tierA
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
from contextlib import contextmanager

import torch

import model as M
import e10_span as E10

HERE = pathlib.Path(__file__).resolve().parent
NEG = -1e30


def rect_mask(seq_len: int, blocks, device, dtype) -> torch.Tensor:
    """Causal 4D additive mask with rectangular (query, key) regions removed.

    model.knockout_mask blanks whole key COLUMNS, which is every query at once.
    This one takes ((q_lo, q_hi), (k_lo, k_hi)) pairs, which is what splitting
    the query side needs. Position 0 is never orphaned, same as there.
    """
    m = torch.full((seq_len, seq_len), NEG, device=device, dtype=torch.float32)
    m = torch.triu(m, diagonal=1)
    for (q_lo, q_hi), (k_lo, k_hi) in blocks:
        m[q_lo:q_hi, k_lo:k_hi] = NEG
    m[0, 0] = 0.0
    return m.to(dtype).unsqueeze(0).unsqueeze(0)


@contextmanager
def rect_knockout(r, layers, blocks, seq_len):
    """model.knockout_layers, but with rectangular blocks."""
    dtype = next(r.model.parameters()).dtype
    full = rect_mask(seq_len, blocks, r.device, dtype)
    fired = {"n": 0}
    handles = []

    def pre(_mod, a, kw):
        q = a[0].shape[1] if a else kw["hidden_states"].shape[1]
        kw["attention_mask"] = full[..., :q, :q]
        fired["n"] += 1
        return a, kw

    for L in layers:
        handles.append(r.layers[L].self_attn.register_forward_pre_hook(
            pre, with_kwargs=True))
    try:
        yield fired
    finally:
        for h in handles:
            h.remove()


@torch.no_grad()
def score_blocked(r, ids, answer, layers=None, blocks=None):
    """(gold logprob, argmax-over-options is gold, hook invocations)."""
    ans_ids = r.tok(answer, return_tensors="pt",
                    add_special_tokens=False).input_ids.to(r.device)
    full = torch.cat([ids, ans_ids], dim=1)
    if blocks is None:
        logits = r.model(full, use_cache=False).logits.float()
        fired = None
    else:
        with rect_knockout(r, layers, blocks, full.shape[1]) as f:
            logits = r.model(full, use_cache=False).logits.float()
        fired = f["n"]

    lp = torch.log_softmax(logits[:, :-1], dim=-1)
    picked = lp.gather(-1, full[:, 1:].unsqueeze(-1)).squeeze(-1)
    value = picked[0, -ans_ids.shape[1]:].mean().item()
    ok = None
    if E10.OPTION_IDS:
        row = logits[0, int(ids.shape[1]) - 1]
        ok = max(E10.OPTION_IDS,
                 key=lambda t: row[E10.OPTION_IDS[t]].item()) == answer
    return value, ok, fired


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
                    help="float32 or bfloat16; see e12_taskspan for why this "
                         "should not be left to the default")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    if args.dtype:
        os.environ["WB_DTYPE"] = args.dtype

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    out_dir = HERE / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    items = E10.load_tasks(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    skill_body = pathlib.Path(args.skill).read_text(encoding="utf-8").strip()

    r = M.load(args.model, device=args.device)
    layers = list(range(0, r.n_layers, args.layer_step))

    E10.OPTION_IDS.clear()
    if args.mode == "mc":
        for letter in "ABCD":
            t = r.tok(letter, add_special_tokens=False).input_ids
            if len(t) == 1:
                E10.OPTION_IDS[letter] = int(t[0])
        if len(E10.OPTION_IDS) != 4:
            print("  [!] option letters are not single tokens -- accuracy off.")
            E10.OPTION_IDS.clear()

    print(f"model  : {args.model}   {r.n_layers} layers  dtype={args.dtype}")
    print(f"skill  : {args.skill}")
    print(f"run id : {run_id}")
    M.write_run_info(out_dir, r, {
        "experiment": "e13_route", "run_id": run_id, "tasks": str(args.tasks),
        "skill": str(args.skill), "mode": args.mode, "n_items": len(items),
        "layers": layers, "dv": "answer_logprob + option argmax",
        "dtype": args.dtype,
    })

    ARMS = ["all_to_skill", "q_to_skill", "last_to_skill",
            "q_to_random", "lastq_to_skill"]
    lp = {a: {L: [] for L in layers} for a in ARMS}
    ok = {a: {L: [] for L in layers} for a in ARMS}
    base_lp, base_ok, dropped, fired_min = [], [], 0, None
    t0 = time.time()

    for i, it in enumerate(items):
        q, gold, unit = E10.fields(it, args.mode)
        ids = M.encode(r, M.render(r, M.build_messages(q, skill, args.mode, unit)))
        s_span = M.find_span(r, ids, skill_body)
        q_span = M.find_span(r, ids, q)
        if s_span is None or q_span is None:
            dropped += 1
            continue
        n_prompt = int(ids.shape[1])
        qw = q_span[1] - q_span[0]

        # A key span the same width as the skill's, placed where the skill is
        # not. The prompt is [chat preamble][skill][chat glue][question][suffix],
        # so anything of that width outside the skill has to overlap the
        # question; the honest control is therefore a same-width window taken
        # from the FRONT of the sequence, which is the chat preamble plus
        # whatever of the skill's own leading tokens fall inside it. Clamped so
        # it never reaches into the question.
        rk_hi = min(s_span[0] + (s_span[1] - s_span[0]), q_span[0])
        rand_key = (0, max(1, rk_hi))

        # A query window the same width as the question's, taken from just
        # before the question -- it sits after the skill, so it CAN attend to
        # it, which is what makes it a fair query-side control.
        lq_lo = max(s_span[1], q_span[0] - qw)
        lastq = (lq_lo, max(lq_lo + 1, q_span[0]))

        blocks = {
            "all_to_skill":   [((0, n_prompt), s_span)],
            "q_to_skill":     [(q_span, s_span)],
            "last_to_skill":  [((n_prompt - 1, n_prompt), s_span)],
            "q_to_random":    [(q_span, rand_key)],
            "lastq_to_skill": [(lastq, s_span)],
        }

        b_lp, b_ok, _ = score_blocked(r, ids, gold)
        base_lp.append(b_lp); base_ok.append(bool(b_ok))

        for L in layers:
            for arm in ARMS:
                v, o, f = score_blocked(r, ids, gold, [L], blocks[arm])
                lp[arm][L].append(v); ok[arm][L].append(bool(o))
                fired_min = f if fired_min is None else min(fired_min, f)
        if (i + 1) % 5 == 0:
            el = time.time() - t0
            print(f"    {i+1}/{len(items)}  {el:.0f}s ({el/(i+1):.1f}s/item)",
                  flush=True)

    n = len(base_lp)
    if not n:
        raise SystemExit("[FAIL] every item was dropped.")
    if not fired_min:
        raise SystemExit("[FAIL] the knockout hook never fired -- a flat curve "
                         "here would be indistinguishable from no effect.")
    mean_base = sum(base_lp) / n
    acc_base = sum(base_ok) / n

    print("\n" + "=" * 84)
    print(f"  E13 attention routing   n={n}  dropped={dropped}  "
          f"hook fired >= {fired_min} times per forward")
    print("=" * 84)
    print(f"  with skill, nothing blocked:  logprob {mean_base:+.3f}   "
          f"acc {acc_base:.3f}")
    print("\n  delta logprob vs unblocked (negative = blocking that route hurts)")
    print("  layer  " + "".join(f"{a[:14]:>16}" for a in ARMS))
    for L in layers:
        print(f"  {L:5d}  " + "".join(
            f"{sum(lp[a][L])/n - mean_base:16.3f}" for a in ARMS))
    print("\n  accuracy")
    print("  layer  " + "".join(f"{a[:14]:>16}" for a in ARMS))
    for L in layers:
        print(f"  {L:5d}  " + "".join(
            f"{sum(ok[a][L])/n:16.3f}" for a in ARMS))
    print("\n  Read q_to_skill against BOTH controls. It has to beat")
    print("  q_to_random (same queries, other keys) and lastq_to_skill")
    print("  (other queries, same keys) before it says anything about routing.")

    summary = {"experiment": "e13_route", "run_id": run_id, "n_items": n,
               "dropped": dropped, "layers": layers, "arms": ARMS,
               "base_logprob": mean_base, "base_acc": acc_base,
               "delta_logprob": {a: [sum(lp[a][L]) / n - mean_base
                                     for L in layers] for a in ARMS},
               "accuracy": {a: [sum(ok[a][L]) / n for L in layers]
                            for a in ARMS}}
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n  results: {out_dir}")


if __name__ == "__main__":
    main()
