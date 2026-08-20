#!/usr/bin/env python3
"""
The only module that touches model weights. Everything else imports from here.

Why a single module: the interventions below (activation patching, attention
knockout) are the easiest place in this project to be subtly wrong in a way that
still produces plausible numbers. Keeping them in one file with one set of
self-tests (selftest.py) means there is exactly one thing to trust.

Loads with attn_implementation="eager" by default. sdpa and flash attention do
not expose per-head attention weights and do not reliably honour a custom 4D
mask, which knockout() needs. Eager is slower; correctness first.
"""

from __future__ import annotations

import json
import pathlib
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

NEG = torch.finfo(torch.float32).min / 4  # additive mask value that blocks attention


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

@dataclass
class Runner:
    model: object
    tok: object
    model_id: str
    device: str
    cfg: dict = field(default_factory=dict)

    @property
    def n_layers(self) -> int:
        # read from config, never hardcoded -- see HANDOFF-whitebox.md 0.2
        return self.model.config.num_hidden_layers

    @property
    def layers(self):
        return self.model.model.layers

    def describe(self) -> dict:
        c = self.model.config
        return {
            "model_id": self.model_id,
            "n_layers": c.num_hidden_layers,
            "hidden_size": c.hidden_size,
            "n_heads": c.num_attention_heads,
            "n_kv_heads": getattr(c, "num_key_value_heads", None),
            "vocab_size": c.vocab_size,
            "dtype": str(next(self.model.parameters()).dtype),
            "device": self.device,
        }


def load(model_id: str, device: str = "cuda", dtype=torch.bfloat16,
         attn: str = "eager") -> Runner:
    tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    common = dict(attn_implementation=attn, trust_remote_code=True)
    try:
        # transformers renamed torch_dtype -> dtype and warns on the old name
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, **common)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype, **common)
    model = model.to(device).eval()
    return Runner(model=model, tok=tok, model_id=model_id, device=device)


# ---------------------------------------------------------------------------
# prompt construction
# ---------------------------------------------------------------------------

ANSWER_INSTRUCTION = {
    "mc": "Answer with the single letter of the correct option and nothing else.",
    "num": "Give only the final number, with no unit and no explanation.",
}


def build_messages(question: str, skill: str | None, mode: str,
                   unit: str | None = None) -> list[dict]:
    """
    Assemble the chat messages. The skill goes in the system prompt as one whole
    document, matching how skillflow.py injects it ("# Skill: <name>").

    The unit is stated in the user turn on purpose. Some SciBench answers carry a
    scale factor in the unit field (answer 1.602 with unit "10^-17 J"), so
    without stating it the model answers 1.602e-17, the scorer marks it wrong,
    and what gets measured is the convention mismatch rather than the chemistry.
    """
    sys = "You are a careful assistant. Answer precisely."
    if skill:
        sys = sys + "\n" + skill
    q = question
    if unit:
        q += f"\n\nGive the answer in units of: {unit}"
    q += "\n\n" + ANSWER_INSTRUCTION[mode]
    return [{"role": "system", "content": sys}, {"role": "user", "content": q}]


def render(r: Runner, messages: list[dict]) -> str:
    """Render with thinking disabled. Verified, not assumed -- see selftest."""
    try:
        return r.tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False)
    except TypeError:
        # tokenizers without the Qwen3 kwarg
        return r.tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)


def encode(r: Runner, text: str) -> torch.Tensor:
    return r.tok(text, return_tensors="pt", add_special_tokens=False).input_ids.to(r.device)


def find_span(r: Runner, ids: torch.Tensor, needle: str) -> tuple[int, int] | None:
    """
    Token span of `needle` inside an already-encoded prompt.

    Located by decoding rather than by re-tokenising the needle: a substring
    tokenised on its own does not always produce the same ids it has in context,
    so matching id sequences silently misses. Character offsets survive that.
    """
    text = r.tok.decode(ids[0], skip_special_tokens=False)
    start_char = text.find(needle)
    if start_char < 0:
        return None
    end_char = start_char + len(needle)
    lo = hi = None
    acc = 0
    for i, t in enumerate(ids[0].tolist()):
        piece = r.tok.decode([t], skip_special_tokens=False)
        nxt = acc + len(piece)
        if lo is None and nxt > start_char:
            lo = i
        if acc < end_char:
            hi = i + 1
        acc = nxt
    return (lo, hi) if lo is not None else None


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

@torch.no_grad()
def capture(r: Runner, ids: torch.Tensor, want_attn: bool = False):
    """
    Residual stream after every layer, optionally attention weights.

    hidden_states[i] is the input to layer i; hidden_states[-1] is the final
    output. So index i in [0, n_layers] and "after layer L" is index L+1.
    """
    out = r.model(ids, output_hidden_states=True,
                  output_attentions=want_attn, use_cache=False)
    return out


# ---------------------------------------------------------------------------
# intervention: activation patching
# ---------------------------------------------------------------------------

@contextmanager
def patch_layer(r: Runner, layer: int, position: int, vector: torch.Tensor,
                prefill_only: bool = True):
    """
    Replace the residual stream at (layer, position) with `vector`.

    prefill_only is the important part. Under a KV cache, generation calls the
    model once with the whole prompt and then once per new token. Hooking every
    call re-injects the vector throughout generation, which is a different
    experiment and not the one described anywhere. The flag fires on the first
    call only; selftest.py checks it by patching a layer with its own value,
    which must leave the output bit-identical.

    `position` may be negative and is resolved against the prefill length. It may
    also be a sequence of positions, in which case `vector` carries one row per
    position -- that is the multi-position variant the design asks for
    (HANDOFF-whitebox.md section 6 step 5, item 4). It matters because a single
    position is a capacity limit that was chosen, not measured: "the effect does
    not compress" and "the effect does not compress into ONE vector" are
    different claims, and only the second one is supported by patching one place.
    """
    state = {"done": False}
    positions = [position] if isinstance(position, int) else list(position)

    def hook(_mod, _inp, out):
        if prefill_only and state["done"]:
            return out
        hs = out[0] if isinstance(out, tuple) else out
        if prefill_only and hs.shape[1] == 1:
            return out            # a decode step, not the prefill
        pos = [p if p >= 0 else hs.shape[1] + p for p in positions]
        v = vector.to(hs.dtype).to(hs.device)
        hs[:, pos, :] = v.reshape(len(pos), -1)
        state["done"] = True
        return (hs,) + tuple(out[1:]) if isinstance(out, tuple) else hs

    h = r.layers[layer].register_forward_hook(hook)
    try:
        yield state
    finally:
        h.remove()


# ---------------------------------------------------------------------------
# intervention: attention knockout
# ---------------------------------------------------------------------------

def knockout_mask(seq_len: int, blocked: Iterable[tuple[int, int]],
                  device, dtype) -> torch.Tensor:
    """
    Causal 4D additive mask with `blocked` key ranges removed for every query.

    Passing a 4D mask bypasses the library's own mask construction, which is why
    eager attention is required: sdpa and flash paths do not honour it reliably.
    """
    m = torch.full((seq_len, seq_len), NEG, device=device, dtype=torch.float32)
    m = torch.triu(m, diagonal=1)                      # standard causal mask
    for lo, hi in blocked:
        m[:, lo:hi] = NEG
    m[0, 0] = 0.0                                      # never orphan position 0
    return m.to(dtype).unsqueeze(0).unsqueeze(0)


@contextmanager
def knockout_layers(r: Runner, layers: Iterable[int],
                    blocked: Iterable[tuple[int, int]], seq_len: int):
    """
    Block attention into `blocked` key ranges, at the listed layers only.

    Passing a 4D mask as the model's `attention_mask` argument applies it at
    every layer, which answers "does the model need this text at all" but not
    "which layers read it". A layer sweep needs the mask injected into one
    attention module at a time, so this hooks self_attn and rewrites the
    attention_mask keyword for those calls.

    The hook counts its own invocations. A knockout that silently never fires is
    indistinguishable from one that fires and changes nothing -- both give a flat
    curve -- so callers should assert on `fired["n"]`.
    """
    dtype = next(r.model.parameters()).dtype
    full = knockout_mask(seq_len, blocked, r.device, dtype)
    fired = {"n": 0}
    handles = []

    def pre(_mod, a, kw):
        q = a[0].shape[1] if a else kw["hidden_states"].shape[1]
        kw["attention_mask"] = full[..., :q, :q]
        fired["n"] += 1
        return a, kw

    for L in layers:
        handles.append(
            r.layers[L].self_attn.register_forward_pre_hook(pre, with_kwargs=True))
    try:
        yield fired
    finally:
        for h in handles:
            h.remove()


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

@torch.no_grad()
def answer_logprob(r: Runner, ids: torch.Tensor, answer: str,
                   attention_mask: torch.Tensor | None = None) -> float:
    """
    Mean log-probability of `answer` continuing the prompt.

    This is the primary dependent variable: continuous, per-item, and far lower
    variance than binary correctness -- see HANDOFF-whitebox.md 2.
    """
    ans_ids = r.tok(answer, return_tensors="pt",
                    add_special_tokens=False).input_ids.to(r.device)
    full = torch.cat([ids, ans_ids], dim=1)
    kw = {}
    if attention_mask is not None:
        n = full.shape[1]
        kw["attention_mask"] = attention_mask[..., :n, :n]
    logits = r.model(full, use_cache=False, **kw).logits.float()
    lp = torch.log_softmax(logits[:, :-1], dim=-1)
    tgt = full[:, 1:]
    picked = lp.gather(-1, tgt.unsqueeze(-1)).squeeze(-1)
    return picked[0, -ans_ids.shape[1]:].mean().item()


@torch.no_grad()
def generate(r: Runner, ids: torch.Tensor, max_new_tokens: int = 24,
             attention_mask: torch.Tensor | None = None) -> str:
    """Greedy only. Sampling would mix 'the skill helped' with 'this draw was lucky'."""
    if attention_mask is None:
        # Qwen3 has pad == eos, so without an explicit mask generate() warns that
        # it cannot tell padding from content. Nothing is padded here (batch=1),
        # making the correct mask all ones -- but an unexplained warning in the
        # log of a real run is a doubt nobody should have to resolve later.
        attention_mask = torch.ones_like(ids)
    out = r.model.generate(ids, max_new_tokens=max_new_tokens, do_sample=False,
                           temperature=None, top_p=None, top_k=None,
                           pad_token_id=r.tok.eos_token_id,
                           attention_mask=attention_mask)
    return r.tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)


# ---------------------------------------------------------------------------
# answer extraction
# ---------------------------------------------------------------------------

def extract_mc(text: str) -> str | None:
    m = re.search(r"\b([ABCD])\b", text.strip())
    return m.group(1) if m else None


def extract_num(text: str) -> float | None:
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text.replace(",", ""))
    return float(m.group(0)) if m else None


def num_correct(pred: float | None, gold: float, rel_tol: float = 0.02) -> bool:
    """2% relative tolerance: these are textbook answers rounded to 3-4 figures."""
    if pred is None:
        return False
    if gold == 0:
        return abs(pred) < 1e-9
    return abs(pred - gold) / abs(gold) <= rel_tol


# ---------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------

def load_skill(path: str | pathlib.Path) -> str:
    """Read a SKILL.md and wrap it the way skillflow.py does (skillflow.py:1204)."""
    p = pathlib.Path(path)
    body = p.read_text(encoding="utf-8")
    name = p.stem.replace("SKILL.", "")
    return f"\n# Skill: {name}\n\n{body}"


def write_run_info(out_dir: pathlib.Path, r: Runner, extra: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    info = dict(r.describe())
    info.update(extra)
    (out_dir / "run-info.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
