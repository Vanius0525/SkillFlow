"""Generation-based accuracy under a patch, shared by e10 / e12 / e14.

Why this exists. `--mode mc` gets an accuracy channel for free: the option
letters are single tokens, so the argmax over four logits at one position IS the
answer. `--mode num` has no such channel, and the cheap fix -- rewriting the
numeric items as multiple choice -- is not neutral. Measured on the same 358
items and the same skill document (HANDOFF-whitebox.md 17.2): Qwen3-1.7B scores
0.180 -> 0.300 in multiple choice and 0.000 -> 0.000 free-form, because with the
document it retrieves a factor from the table and never multiplies. Multiple
choice scores that retrieval as success and adds a positional floor on top.

So the numeric form keeps its own answer format and gets its accuracy by
decoding. `prefill_only=True` is not a detail: the patch is a claim about the
state at the end of the prompt, so it fires once and the decode steps then run
off the KV cache it produced. Re-injecting at every step is a clamp, which is a
different experiment.
"""
from __future__ import annotations

import torch

import model as M


@torch.no_grad()
def first_token(r, ids, layer=None, positions=None, vector=None) -> int:
    """The id of the token the model would emit next, under the patch.

    Used as an instrument check. Patching the LAST layer's output at the final
    prompt position makes the logits at that position identical to the donor
    run's, so the first emitted token must match the donor's exactly. If it
    does not, the hook is not firing where the capture read and every accuracy
    curve in the file is measuring nothing -- a failure that otherwise shows up
    as a clean, publishable zero.
    """
    att = torch.ones_like(ids)       # the kernel generate() and capture use
    if vector is None:
        out = r.model(ids, attention_mask=att, use_cache=False)
    else:
        with M.patch_layer(r, layer, positions, vector, prefill_only=True):
            out = r.model(ids, attention_mask=att, use_cache=False)
    return int(out.logits[0, -1].argmax().item())


def extract_cot_answer(text: str):
    """The number on the last `ANSWER:` line of a reasoning chain.

    `model.extract_num` takes the FIRST number in the string, which for a chain
    of thought is a step of the arithmetic, not the result. Returning None when
    no ANSWER line was produced is deliberate: a truncated chain is a wrong
    answer, and silently falling back to the first number would score the
    model's working instead of its conclusion.
    """
    idx = text.rfind("ANSWER:")
    if idx < 0:
        return None
    return M.extract_num(text[idx + len("ANSWER:"):])


@torch.no_grad()
def gen_ok(r, ids, gold, layer=None, positions=None, vector=None,
           max_new: int = 8, rel_tol: float = 1e-6, cot: bool = False):
    """(is the decoded number correct, the decoded text).

    rel_tol defaults to exact rather than model.py's 2%: Tier A answers are
    integers by construction, and a 2% window would let a neighbouring-row
    misreading count as correct whenever two rows are within 2% of each other.
    """
    if vector is None:
        txt = M.generate(r, ids, max_new_tokens=max_new)
    else:
        with M.patch_layer(r, layer, positions, vector, prefill_only=True):
            txt = M.generate(r, ids, max_new_tokens=max_new)
    try:
        g = float(gold)
    except (TypeError, ValueError):
        return None, txt
    pred = extract_cot_answer(txt) if cot else M.extract_num(txt)
    return M.num_correct(pred, g, rel_tol=rel_tol), txt
