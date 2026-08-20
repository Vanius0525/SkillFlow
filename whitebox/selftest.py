#!/usr/bin/env python3
"""
Unit tests for the intervention machinery. Run before trusting any result.

These do not test a hypothesis; they test that the code does what it claims.
Every one of them fails loudly on a specific bug that otherwise produces
plausible-looking numbers:

  1  structure         config read, not assumed
  2  thinking off      the think block is closed and EMPTY, and generation
                       does not open a new one. Qwen3 disables thinking by
                       emitting an empty pair, not by omitting the markers --
                       asserting absence fails on a correct configuration
  3  no-op patch       patching a layer with its OWN value changes nothing.
                       Catches the prefill-vs-decode-step error: a hook that
                       fires on every step still passes a "does it change
                       anything" check but fails this one.
  4  destructive patch  patching with zeros DOES change the output. Catches a
                       hook that silently never fires -- which otherwise looks
                       exactly like "the intervention had no effect".
  4b multi-position   patching K positions with their own values is a no-op,
                       and REVERSING those rows is not. The second half is the
                       real test: it pins each row to its position
  5  knockout          a 4D mask actually blocks attention. Catches the sdpa
                       path ignoring the custom mask.
  6  span location     find_span returns a span that decodes back to the needle
  6b whole document    the span of a full skill body reaches the END of it. A
                       prefix span covers only the frontmatter, so the knockout
                       blocks the skill's description and leaves its content
                       readable -- and reports a flat curve for it
  7  logprob sanity    a plausible continuation scores above an implausible one

Run on the smallest model available; it is seconds there and minutes at 8B.

    python selftest.py --model Qwen/Qwen3-1.7B
"""

from __future__ import annotations

import argparse
import pathlib
import re

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
    # Qwen3 turns thinking OFF by emitting an EMPTY <think></think> pair, not by
    # omitting the markers: the closed empty block is what tells the model its
    # reasoning turn is already finished. An earlier version of this check
    # asserted the substring was absent and failed on a correctly configured
    # model. What matters is that the block is closed and empty, and that
    # generation does not open a new one.
    print("\n2. thinking mode")
    msgs = M.build_messages("What is 2+2?", None, "num")
    text = M.render(r, msgs)
    print(f"     rendered tail: {text[-120:]!r}")

    m = re.search(r"<think>(.*?)</think>", text, re.S)
    if m is not None:
        check("think block is closed and empty", m.group(1).strip() == "",
              f"contains {m.group(1)[:60]!r} -- thinking is ON")
    elif "<think>" in text:
        check("think block is closed and empty", False,
              "an unclosed <think> -- thinking is ON")
    else:
        check("no think markers at all (thinking not templated)", True)

    ids = M.encode(r, text)
    print(f"     prompt tokens: {ids.shape[1]}")

    # empirical: the model must not start reasoning despite the template
    gen = M.generate(r, ids, max_new_tokens=48)
    check("generation opens no new think block", "<think>" not in gen,
          f"generated: {gen[:80]!r}")
    print(f"     generated: {gen.strip()[:60]!r}")

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

    # --- 4b. multi-position patch ----------------------------------------
    # E2 can patch the last K prompt positions (--tail-k). The same no-op
    # guarantee has to hold there, and the rows of the [K, d] vector have to line
    # up with the positions: a transposed or reversed assignment patches real
    # activations into the wrong tokens, which is not detectable downstream --
    # every number still looks like a number. The reversal check is what pins the
    # ordering, since a no-op test alone passes under any symmetric mistake.
    print("\n4b. multi-position patch")
    kk = 4
    own_k = base.hidden_states[layer + 1][0, -kk:].clone()
    pos_k = list(range(ids.shape[1] - kk, ids.shape[1]))
    with M.patch_layer(r, layer, pos_k, own_k):
        outk = r.model(ids, use_cache=False)
    noop_k = (outk.logits[:, -1].float() - ref_logits).abs().max().item()
    check("no-op patch over K positions leaves output unchanged", noop_k < 1e-2,
          f"max |dlogit| = {noop_k:.4g}")
    with M.patch_layer(r, layer, pos_k, own_k.flip(0)):
        outr = r.model(ids, use_cache=False)
    rev_k = (outr.logits[:, -1].float() - ref_logits).abs().max().item()
    check("reversing the rows does change the output", rev_k > 0.01,
          f"max |dlogit| = {rev_k:.4g} -- rows may not be bound to positions")

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

    # --- 5b. PER-LAYER knockout ------------------------------------------
    # The global mask above blocks at every layer. E1 sweeps one layer at a
    # time, which goes through a different mechanism (a hook that rewrites the
    # attention_mask kwarg on self_attn), and that mechanism is the single most
    # version-fragile thing in this repo. A hook that never fires produces a
    # perfectly flat layer curve, which reads exactly like "no layer depends on
    # this text" -- so the fire count is checked, not just the output.
    print("\n5b. per-layer attention knockout")
    with M.knockout_layers(r, [layer], blocked, n) as fired:
        with torch.no_grad():
            one = r.model(ids, use_cache=False)
    check("per-layer hook fired", fired["n"] > 0,
          "self_attn signature may differ in this transformers version")
    one_delta = (one.logits[:, -1].float() - ref_logits).abs().max().item()
    check("single-layer knockout changes output", one_delta > 0.01,
          f"max |dlogit| = {one_delta:.4g}")
    check("single-layer effect is smaller than all-layer", one_delta < ko_delta,
          f"one-layer {one_delta:.3g} vs all-layer {ko_delta:.3g}")

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

    # --- 6b. span location over a WHOLE document -------------------------
    # E1 blocks the entire skill body, so the span has to reach the end of the
    # document, not just its opening. The bug this guards produced no error and
    # no warning: locating a 400-character prefix returned a span covering the
    # YAML frontmatter -- the description of the skill -- while the conversion
    # table it describes stayed visible at every layer. A knockout that blocks
    # nothing relevant reports a flat curve, and a flat curve reads as "no layer
    # depends on the skill".
    print("\n6b. span location over a whole document")
    skill_path = pathlib.Path(__file__).resolve().parent / "tasks" / "tier_a" / \
        "SKILL.zorb-units.md"
    if not skill_path.exists():
        check("whole-document span", False, f"missing {skill_path}")
    else:
        body = skill_path.read_text(encoding="utf-8").strip()
        doc_ids = M.encode(r, M.render(r, M.build_messages(
            "What is 2+2?", M.load_skill(skill_path), "num")))
        dspan = M.find_span(r, doc_ids, body)
        if dspan is None:
            check("whole-document span located", False, "body not found in prompt")
        else:
            got = r.tok.decode(doc_ids[0, dspan[0]:dspan[1]],
                               skip_special_tokens=False)
            first, last = body.splitlines()[0], body.splitlines()[-1]
            check("whole-document span located", True,
                  f"{dspan[1] - dspan[0]} tokens")
            check("span reaches the end of the document", last in got,
                  f"last line {last[:40]!r} missing -- span stops early")
            check("span starts at the document", first in got,
                  f"first line {first[:40]!r} missing")

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
