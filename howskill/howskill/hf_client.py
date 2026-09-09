"""A local HF transformers chat client with the same interface as ChatClient.

WHY THIS EXISTS

The P8 pipeline generates with vLLM and then replays with HF transformers, and
GATE-W0 exists because those two can disagree: a different kernel, a different
dtype path, or a chat template applied with different kwargs shifts the token
stream, and a shifted stream makes every internal measurement wrong without
raising anything (P8-WHITEBOX.md 3.5). That gate is load-bearing and it is also
the most likely place for this line to stall on something that is not a
finding.

Generating with the same engine that replays removes the disagreement at the
source rather than testing for it afterwards. This client uses the SAME
tokenizer object type, the SAME `apply_chat_template(..., add_generation_prompt
=True, enable_thinking=...)` call and the SAME `attn_implementation="eager"` as
`wb_replay.Replayer`, so the prompt tokens are identical by construction and
GATE-W0 becomes a check on the replay arithmetic alone.

The second reason is practical: it removes a vLLM install (0.11.0 + cu128,
several GB, its own torch) from the critical path on a box that already has the
image's CUDA torch.

WHAT IT COSTS

Throughput. One stream, greedy, no continuous batching. Batching was considered
and rejected: left-padding a batch changes the reduction order, which moves
logprobs by a small amount that is nevertheless exactly what GATE-W0 measures,
and a silent result change is worse here than a slower run. So callers must use
`--workers 1`; `run.py` enforces it.

Determinism: temperature is ignored unless > 0, and greedy decoding with one
sequence per forward is reproducible on a fixed machine.
"""

from __future__ import annotations

import os
import threading


class HFClient:
    def __init__(self, model_dir: str, temperature: float = 0.0,
                 max_tokens: int = 4096, thinking: bool = False,
                 seed: int | None = 0, logprobs: int | None = None,
                 dtype: str = "bfloat16", device: str = "cuda"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.model_dir = model_dir
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.seed = seed
        self.logprobs = logprobs
        self.dtype = dtype
        self.device = device
        # One GPU, one stream. The lock is not for speed, it is so that a
        # caller that forgot --workers 1 gets serialised rather than two
        # generates interleaving on the same module.
        self._lock = threading.Lock()

        self.tok = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_dir, torch_dtype=getattr(torch, dtype),
            device_map=device, attn_implementation="eager")
        self.model.eval()
        if seed is not None:
            torch.manual_seed(seed)

    def config(self) -> dict:
        return {"engine": "hf", "model": self.model_dir, "dtype": self.dtype,
                "device": self.device, "temperature": self.temperature,
                "max_tokens": self.max_tokens, "thinking": self.thinking,
                "seed": self.seed, "logprobs": self.logprobs,
                # recorded so a later replay can assert it matched
                "attn_implementation": "eager",
                "chat_template_kwargs": {"enable_thinking": self.thinking}}

    def __call__(self, messages: list[dict]) -> tuple[str, dict]:
        t = self.torch
        # Identical to wb_replay.Replayer.build_inputs -- that is the point.
        prompt = self.tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=self.thinking)
        enc = self.tok(prompt, return_tensors="pt")
        ids = enc["input_ids"].to(self.device)
        attn = enc["attention_mask"].to(self.device)
        n_prompt = int(ids.shape[1])

        gen_kwargs = dict(max_new_tokens=self.max_tokens,
                          return_dict_in_generate=True, output_scores=True,
                          pad_token_id=self.tok.pad_token_id
                          or self.tok.eos_token_id)
        if self.temperature and self.temperature > 0:
            gen_kwargs.update(do_sample=True, temperature=self.temperature)
        else:
            gen_kwargs.update(do_sample=False)

        with self._lock, t.no_grad():
            out = self.model.generate(input_ids=ids, attention_mask=attn,
                                      **gen_kwargs)

        seq = out.sequences[0]
        new = seq[n_prompt:]
        text = self.tok.decode(new, skip_special_tokens=True)

        finish = "stop" if int(new.shape[0]) < self.max_tokens else "length"
        meta: dict = {
            "usage": {"prompt_tokens": n_prompt,
                      "completion_tokens": int(new.shape[0]),
                      "total_tokens": n_prompt + int(new.shape[0])},
            "finish_reason": finish,
        }

        if self.logprobs:
            # OpenAI shape, because that is what wb_replay.vllm_logprobs reads:
            # meta["logprobs"]["content"][i]["logprob"]. `scores` holds one
            # tensor per generated step, already the logits for that step.
            content = []
            for step, sc in enumerate(out.scores):
                if step >= new.shape[0]:
                    break
                lp = t.log_softmax(sc[0].float(), dim=-1)
                tid = int(new[step])
                content.append({
                    "token": self.tok.convert_ids_to_tokens([tid])[0],
                    "logprob": float(lp[tid]),
                })
            meta["logprobs"] = {"content": content}

        return text, meta


def from_args(a) -> HFClient:
    """Build one from the run.py namespace, resolving the weights directory."""
    d = (getattr(a, "hf_model_dir", "") or os.environ.get("WB_MODEL", "")
         or os.environ.get("WB_MAIN_MODEL", ""))
    if not d:
        raise SystemExit(
            "[FAIL] --engine hf needs the local weights: pass --hf-model-dir "
            "or set WB_MODEL / WB_MAIN_MODEL. The served-model name that "
            "--model carries is a vLLM concept and is not a path.")
    if not os.path.isdir(d):
        raise SystemExit(f"[FAIL] --hf-model-dir is not a directory: {d}")
    return HFClient(d, temperature=a.temperature, max_tokens=a.max_tokens,
                    thinking=a.thinking, seed=a.seed,
                    logprobs=a.logprobs or None,
                    dtype=getattr(a, "hf_dtype", "bfloat16"))
