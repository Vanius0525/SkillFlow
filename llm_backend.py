"""
Local LLM backend adapter.

Lets the SkillFlow / eval harnesses talk to a local OpenAI-compatible server
(vLLM, SGLang, Ollama, ...) serving an open model such as Qwen3-30B-A3B,
WITHOUT changing any of the agent-loop / tool-calling / scoring code.

The Qwen client mimics the small slice of the `anthropic.Anthropic` interface
the harness actually uses:

    client.messages.create(model=, max_tokens=, system=, tools=, messages=)
        -> response with:
             .content       list of blocks (text / tool_use), Anthropic-shaped
             .stop_reason   "end_turn" | "tool_use" | "max_tokens"
             .usage.input_tokens / .usage.output_tokens

Because the returned object has the same shape as a real Anthropic response,
the existing code (run_agent_loop, tool dispatch, answer extraction) works
unchanged regardless of backend.
"""

import os
import json


# ---------------------------------------------------------------------------
# Anthropic-shaped response objects (duck-typed)
# ---------------------------------------------------------------------------

class _TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict):
        self.id = id
        self.name = name
        self.input = input


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    def __init__(self, content: list, stop_reason: str, usage: _Usage):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage


# ---------------------------------------------------------------------------
# Block helpers (handle both dicts and our block objects in message history)
# ---------------------------------------------------------------------------

def _btype(b):
    return b.get("type") if isinstance(b, dict) else getattr(b, "type", None)


def _bget(b, key):
    return b.get(key) if isinstance(b, dict) else getattr(b, key, None)


def _stringify(content) -> str:
    """Flatten an Anthropic tool_result `content` into a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for x in content:
            if isinstance(x, dict):
                parts.append(x.get("text", json.dumps(x, ensure_ascii=False)))
            else:
                parts.append(str(x))
        return "\n".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# Anthropic -> OpenAI conversion
# ---------------------------------------------------------------------------

def _tools_to_openai(tools):
    out = []
    for t in tools or []:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema",
                                    {"type": "object", "properties": {}}),
            },
        })
    return out


def _messages_to_openai(messages, system):
    out = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            if isinstance(content, str):
                out.append({"role": "user", "content": content})
                continue
            # list of blocks: tool_result -> "tool" messages; text/image -> "user"
            tool_results = [b for b in content if _btype(b) == "tool_result"]
            for b in tool_results:
                out.append({
                    "role": "tool",
                    "tool_call_id": _bget(b, "tool_use_id"),
                    "content": _stringify(_bget(b, "content")),
                })
            texts = []
            for b in content:
                bt = _btype(b)
                if bt == "text":
                    texts.append(_bget(b, "text"))
                elif bt == "image":
                    texts.append("[image omitted: local text model cannot view images]")
            if texts:
                out.append({"role": "user", "content": "\n".join(texts)})

        elif role == "assistant":
            text_parts, tool_calls = [], []
            for b in (content if isinstance(content, list) else [content]):
                bt = _btype(b)
                if bt == "text":
                    text_parts.append(_bget(b, "text"))
                elif bt == "tool_use":
                    tool_calls.append({
                        "id": _bget(b, "id"),
                        "type": "function",
                        "function": {
                            "name": _bget(b, "name"),
                            "arguments": json.dumps(_bget(b, "input") or {},
                                                    ensure_ascii=False),
                        },
                    })
            m = {"role": "assistant",
                 "content": "\n".join(text_parts) if text_parts else None}
            if tool_calls:
                m["tool_calls"] = tool_calls
            out.append(m)

    return out


def _response_from_openai(completion) -> _Response:
    choice = completion.choices[0]
    msg = choice.message

    blocks = []
    if getattr(msg, "content", None):
        blocks.append(_TextBlock(msg.content))

    tool_calls = getattr(msg, "tool_calls", None) or []
    for tc in tool_calls:
        try:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
        except (json.JSONDecodeError, TypeError):
            args = {}
        blocks.append(_ToolUseBlock(id=tc.id, name=tc.function.name, input=args))

    if not blocks:
        blocks.append(_TextBlock(""))

    finish = choice.finish_reason
    if tool_calls or finish == "tool_calls":
        stop_reason = "tool_use"
    elif finish == "length":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"

    usage = getattr(completion, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    return _Response(blocks, stop_reason, _Usage(in_tok, out_tok))


# ---------------------------------------------------------------------------
# OpenAI-compatible client with an Anthropic-shaped .messages.create()
# ---------------------------------------------------------------------------

class _Messages:
    def __init__(self, client: "QwenClient"):
        self._client = client

    def create(self, model=None, max_tokens=1024, messages=None,
               system=None, tools=None, **kwargs):
        # `model` (the Claude id) is ignored — we use the configured local model.
        oai_messages = _messages_to_openai(messages or [], system)
        params = dict(model=self._client._model,
                      messages=oai_messages,
                      max_tokens=max_tokens)
        if tools:
            params["tools"] = _tools_to_openai(tools)
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        # Qwen3 hybrid-thinking models: disable <think> blocks unless
        # QWEN_ENABLE_THINKING=1. The harness makes many small-max_tokens
        # calls (plan=64, compress=256) that thinking would consume entirely.
        if os.environ.get("QWEN_ENABLE_THINKING", "0") != "1":
            params["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": False}
            }
        completion = self._client._openai.chat.completions.create(**params)
        return _response_from_openai(completion)


class QwenClient:
    """Anthropic-API-shaped wrapper around an OpenAI-compatible endpoint."""

    def __init__(self, base_url: str, model: str, api_key: str = "EMPTY",
                 context_window: int | None = None):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "The 'qwen' backend needs the openai package: pip install openai"
            ) from e
        self._openai = OpenAI(base_url=base_url, api_key=api_key or "EMPTY")
        self._model = model
        # Max context window of the served model — used by the harness to decide
        # when to compress skill docs. Qwen3 dense/MoE default to 32768; the
        # -2507 variants serve up to 262144. Override via QWEN_CONTEXT_WINDOW.
        self.context_window = int(
            context_window or os.environ.get("QWEN_CONTEXT_WINDOW", "32768")
        )
        self.messages = _Messages(self)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_client(backend: str = "claude", api_key: str | None = None,
                base_url: str | None = None, model: str | None = None):
    """
    Return an LLM client for the chosen backend.

    backend="claude" -> real anthropic.Anthropic
    backend="qwen"   -> QwenClient against a local OpenAI-compatible server
    """
    if backend == "qwen":
        return QwenClient(
            base_url=base_url or os.environ.get("QWEN_BASE_URL", "http://localhost:8000/v1"),
            model=model or os.environ.get("QWEN_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
            api_key=api_key or os.environ.get("QWEN_API_KEY", "EMPTY"),
        )

    import anthropic
    return anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
