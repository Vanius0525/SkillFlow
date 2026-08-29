"""vLLM / OpenAI-compatible chat client.

Deployment notes (Inspire 4090 container):
  vllm serve ... --enable-auto-tool-choice --tool-call-parser hermes \
                 --reasoning-parser qwen3 --served-model-name Qwen/Qwen3-8B

``enable_thinking`` is passed through ``chat_template_kwargs``. It MUST be
recorded in every result file: it changes the token stream, and the whitebox
replay (P8) has to use the identical setting or token positions misalign
silently. It is also the first thing to try if P1 calibration misses.
"""

from __future__ import annotations

import os
import time

import requests

DEFAULT_BASE = os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8000/v1")
DEFAULT_MODEL = os.environ.get("QWEN_MODEL", "Qwen/Qwen3-8B")


class ChatClient:
    def __init__(self, base_url: str = DEFAULT_BASE, model: str = DEFAULT_MODEL,
                 temperature: float = 0.0, max_tokens: int = 4096,
                 thinking: bool = False, seed: int | None = 0,
                 logprobs: int | None = None, timeout: int = 600,
                 retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.seed = seed
        self.logprobs = logprobs
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()

    def config(self) -> dict:
        return {
            "base_url": self.base_url, "model": self.model,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
            "thinking": self.thinking, "seed": self.seed,
            "logprobs": self.logprobs,
        }

    def __call__(self, messages: list[dict]) -> tuple[str, dict]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "chat_template_kwargs": {"enable_thinking": self.thinking},
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = self.logprobs

        last = None
        for attempt in range(self.retries):
            try:
                r = self.session.post(f"{self.base_url}/chat/completions",
                                      json=payload, timeout=self.timeout)
                r.raise_for_status()
                d = r.json()
                choice = d["choices"][0]
                text = choice["message"].get("content") or ""
                meta = {
                    "usage": d.get("usage"),
                    "finish_reason": choice.get("finish_reason"),
                }
                if self.logprobs and choice.get("logprobs"):
                    meta["logprobs"] = choice["logprobs"]
                return text, meta
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"chat failed after {self.retries} attempts: {last}")


class MockClient:
    """Deterministic offline client for selftest — no GPU, no server."""

    def __init__(self, script: list[str] | None = None):
        self.script = script or []
        self.i = 0
        self.seen: list[list[dict]] = []

    def config(self) -> dict:
        return {"mock": True}

    def __call__(self, messages):
        self.seen.append([dict(m) for m in messages])
        out = self.script[self.i] if self.i < len(self.script) else "ANSWER: 0"
        self.i += 1
        return out, {"usage": {"total_tokens": 0}, "finish_reason": "stop"}
