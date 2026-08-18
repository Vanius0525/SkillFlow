#!/usr/bin/env python3
"""
Unit tests for the intervention machinery. Run before trusting any result.

These do not test a hypothesis; they test that the code does what it claims.
Every one of them fails loudly on a specific bug that otherwise produces
plausible-looking numbers:

  1  structure         config read, not assumed
  2  thinking off      no <think> in the rendered prompt
  3  no-op patch       patching a layer with its OWN value changes nothing.
                       Catches the prefill-vs-decode-step error: a hook that
                       fires on every step still passes a "does it change
                       anything" check but fails this one.
  4  destructive patch  patching with zeros DOES change the output. Catches a
                       hook that silently never fires -- which otherwise looks
                       exactly like "the intervention had no effect".
  5  knockout          a 4D mask actually blocks attention. Catches the sdpa
                       path ignoring the custom mask.
  6  span location     find_span returns a span that decodes back to the needle
  7  logprob sanity    a plausible continuation scores above an implausible one

Run on the smallest model available; it is seconds there and minutes at 8B.

    python selftest.py --model Qwen/Qwen3-1.7B
"""

from __future__ import annotations

import argparse

import torch

import model as M

PASS, FAIL = [], []


def check(name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(name)
    print(f"  [{'  OK  ' if ok else ' FAIL '}] {name}" + (f"  -- {detail}" if detail else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    print(f"loading {args.model} ...")
    r = M.load(args.model, device=args.device)

    # --- 1. structure -----------------------------------------------------
    d = r.describe()
    print("\n1. model structure (from config, not from memory)")
    for k, v in d.items():
        print(f"     {k}: {v}")
    check("config exposes layer count", isinstance(d["n_layers"], int) and d["n_layers"] > 0)
    check("layer list length matches config", len(r.layers) == d["n_layers"],
          f"{len(r.layers)} vs {d['n_layers']}")

    # --- 2. thinking mode -------------------------------------------------
    print("\n2. thinking mode")
    msgs = M.build_messages("What is 2+2?", None, "num")
    text = M.render(r, msgs)
    check("no <think> block in rendered prompt", "<think>" not in text,
          "rendered prompt still contains <think>")

    ids = M.encode(r, text)
    print(f"     prompt tokens: {ids.shape[1]}")

    # --- 3/4. activation patching ----------------------------------------
    print("\n3/4. activation patching")
    layer = d["n_layers"] // 2
    base = M.capture(r, ids)
    ref_logits = base.logits[:, -1].float().clone()
    own = base.hidden_states[layer + 1][0, -1].clone()   # after `layer`

    with M.patch_layer(r, layer, -1, own) as st:
        out = r.model(ids, use_cache=False)
    noop_delta = (out.logits[:, -1].float() - ref_logits).abs().max().item()
    check("patch hook fired", st["done"])
    check("no-op patch leaves output unchanged", noop_delta < 1e-2,
          f"max |dlogit| = {noop_delta:.4g}")

    with M.patch_layer(r, layer, -1, torch.zeros_like(own)):
        out0 = r.model(ids, use_cache=False)
    zero_delta = (out0.logits[:, -1].float() - ref_logits).abs().max().item()
    check("zero patch does change output", zero_delta > 1.0,
          f"max |dlogit| = {zero_delta:.4g} -- if ~0 the hook never fired")

    # --- 5. attention knockout -------------------------------------------
    print("\n5. attention knockout")
    n = ids.shape[1]
    blocked = [(1, max(2, n // 2))]
    mask = M.knockout_mask(n, blocked, r.device, next(r.model.parameters()).dtype)
    with torch.no_grad():
        ko = r.model(ids, attention_mask=mask, use_cache=False,
                     output_attentions=True)
    lo, hi = blocked[0]
    att = ko.attentions[layer][0, :, -1, lo:hi]
    leak = att.abs().max().item()
    check("blocked span receives ~no attention", leak < 1e-4,
          f"max attention into blocked span = {leak:.3g} -- mask ignored?")
    ko_delta = (ko.logits[:, -1].float() - ref_logits).abs().max().item()
    check("knockout changes the output", ko_delta > 1.0, f"max |dlogit| = {ko_delta:.4g}")

    # --- 6. span location -------------------------------------------------
    print("\n6. span location")
    needle = "What is 2+2?"
    span = M.find_span(r, ids, needle)
    ok = span is not None
    if ok:
        got = r.tok.decode(ids[0, span[0]:span[1]], skip_special_tokens=False)
        ok = needle in got
        check("find_span covers the needle", ok, f"span={span} decodes to {got!r}")
    else:
        check("find_span covers the needle", False, "needle not found")

    # --- 7. logprob sanity ------------------------------------------------
    print("\n7. logprob sanity")
    good = M.answer_logprob(r, ids, "4")
    bad = M.answer_logprob(r, ids, "17")
    check("plausible answer scores above implausible", good > bad,
          f"lp(4)={good:.3f}  lp(17)={bad:.3f}")

    print(f"\n{'='*60}\n  passed {len(PASS)}, failed {len(FAIL)}")
    if FAIL:
        print("  failed:", ", ".join(FAIL))
        print("  Do not run experiments until these pass -- a broken intervention")
        print("  produces numbers, just not meaningful ones.")
        raise SystemExit(1)
    print("  All good. The interventions do what they claim.")
    print("=" * 60)


if __name__ == "__main__":
    main()
