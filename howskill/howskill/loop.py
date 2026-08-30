"""The agentic loop.

This is SR-Agents' ``infer/engines/tool_loop.py`` (TOOL_CALL / TOOL_RESULT
interception, restricted exec namespace, 5-round cap) with the four things
the mechanism experiments need and upstream does not provide:

  1. forced prefix    — seed the loop with someone else's turns, then continue
                        freely. Required for trajectory grafting (P7).
  2. skill schedule   — control which turns the skill text is visible on.
                        Required for the temporal ablation (P4).
  3. structured log   — every turn recorded as a dict (messages, raw text,
                        tool calls, token usage, optional logprobs) rather
                        than concatenated strings. Required for step-level
                        readouts and for the whitebox replay (P8).
  4. determinism      — fixed seed/temperature, and a replay check that the
                        forced prefix actually reproduces.

The scoring-relevant output (``model_output``) is assembled exactly as
upstream does: only model-generated text, with TOOL_RESULT lines living in
the transcript. Changing that would break P1 calibration.
"""

from __future__ import annotations

import ast
import math
import re
import time

TOOL_CALL_RE = re.compile(r"^TOOL_CALL:\s*(\w+)\(([^)]*)\)\s*$", re.MULTILINE)

MAX_TOOL_ROUNDS = 5          # upstream _MAX_TOOL_ROUNDS

SAFE_BUILTINS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "int": int, "float": float, "str": str, "len": len,
    "sum": sum, "pow": pow, "bool": bool,
    "True": True, "False": False, "None": None,
    "range": range, "enumerate": enumerate, "zip": zip,
    "isinstance": isinstance,
}


# ---------------------------------------------------------------------------
# Tool machinery (upstream behaviour)
# ---------------------------------------------------------------------------

def _parse_call_args(args_str: str, tool_def: dict) -> dict | None:
    if not args_str:
        return {}
    try:
        tree = ast.parse(f"_f({args_str})", mode="eval")
        call = tree.body
        result: dict = {}
        param_names = list(tool_def.get("parameters", {}).keys())
        for i, arg in enumerate(call.args):
            key = param_names[i] if i < len(param_names) else f"_pos_{i}"
            result[key] = ast.literal_eval(arg)
        for kw in call.keywords:
            result[kw.arg] = ast.literal_eval(kw.value)
        return result
    except Exception:
        return None


def parse_tool_call(text: str, available: dict[str, dict]):
    for match in TOOL_CALL_RE.finditer(text):
        name = match.group(1)
        if name in available:
            args = _parse_call_args(match.group(2).strip(), available[name])
            if args is not None:
                return text[: match.end()], name, args
    return None


def execute_tool(tool_def: dict, args: dict) -> str:
    ns = {"__builtins__": SAFE_BUILTINS, "math": math}
    exec(tool_def["implementation"], ns)  # noqa: S102
    return str(ns[tool_def["name"]](**args))


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

class Trajectory:
    """Structured record of one episode."""

    def __init__(self):
        self.turns: list[dict] = []
        self.messages: list[dict] = []
        self.model_output = ""
        self.transcript = ""
        self.stop_reason = None
        self.forced_turns = 0
        self.prefix_reproduced: bool | None = None
        self.wall_seconds = 0.0

    def to_dict(self) -> dict:
        return {
            "turns": self.turns,
            "messages": self.messages,
            "model_output": self.model_output,
            "transcript": self.transcript,
            "stop_reason": self.stop_reason,
            "forced_turns": self.forced_turns,
            "prefix_reproduced": self.prefix_reproduced,
            "wall_seconds": round(self.wall_seconds, 3),
            "n_turns": len(self.turns),
            "n_tool_calls": sum(1 for t in self.turns if t.get("tool_call")),
            "n_tool_errors": sum(1 for t in self.turns if t.get("tool_error")),
        }


def _skill_visible(schedule: str, turn_idx: int, any_tool_yet: bool) -> bool:
    """P4 temporal ablation. ``turn_idx`` is 0-based."""
    if schedule == "all":
        return True
    if schedule == "first":
        return turn_idx == 0
    if schedule == "late":
        # withheld until after the first tool call has happened
        return any_tool_yet
    raise ValueError(f"unknown skill schedule: {schedule}")


def run_episode(
    chat_fn,
    system: str,
    user_with_skill: str,
    user_without_skill: str,
    tools: list[dict],
    *,
    skill_schedule: str = "all",
    forced_prefix: list[dict] | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
    verify_prefix: bool = True,
) -> Trajectory:
    """Run one episode.

    ``chat_fn(messages) -> (text, meta)`` does the model call; meta may carry
    usage/logprobs and is recorded verbatim.

    ``user_with_skill`` / ``user_without_skill`` are the two forms of the
    first user message; the schedule decides which one is in context on each
    turn. For ``skill_schedule='all'`` only the former is ever used, which is
    exactly upstream behaviour.

    ``forced_prefix`` is a list of message dicts to install before generating
    (P7 grafting). Turns are counted from after the prefix.
    """
    traj = Trajectory()
    t0 = time.time()
    tool_index = {t["name"]: t for t in tools}

    def first_user(visible: bool) -> str:
        return user_with_skill if visible else user_without_skill

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": first_user(
        _skill_visible(skill_schedule, 0, False))})

    if forced_prefix:
        messages.extend(forced_prefix)
        traj.forced_turns = len(forced_prefix)
        for m in forced_prefix:
            if m["role"] == "assistant":
                traj.model_output += m["content"]
                traj.transcript += m["content"]
            else:
                traj.transcript += "\n" + m["content"] + "\n"

    any_tool_yet = any(m["role"] == "user" and m["content"].startswith("TOOL_RESULT:")
                       for m in (forced_prefix or []))

    for turn_idx in range(max_rounds):
        # refresh skill visibility for this turn
        visible = _skill_visible(skill_schedule, turn_idx, any_tool_yet)
        for m in messages:
            if m["role"] == "user":
                m["content"] = first_user(visible)
                break

        response, meta = chat_fn(messages)
        if not response:
            traj.stop_reason = "empty_response"
            break

        parsed = parse_tool_call(response, tool_index)
        turn = {
            "turn": turn_idx,
            "skill_visible": visible,
            "raw": response,
            "meta": meta,
            "tool_call": None,
            "tool_result": None,
        }

        if parsed is None:
            traj.model_output += response
            traj.transcript += response
            turn["final"] = True
            traj.turns.append(turn)
            traj.stop_reason = "answered"
            break

        head, tool_name, args = parsed
        try:
            result = execute_tool(tool_index[tool_name], args)
        except Exception as e:  # noqa: BLE001 — upstream swallows and continues
            result = f"Error: {e}"

        turn["tool_call"] = {"name": tool_name, "args": args}
        turn["tool_result"] = result
        # Upstream swallows the exception and hands the text back to the model,
        # which is faithful but leaves a broken tool indistinguishable from a
        # working one in the results. Record it; the string the model sees is
        # unchanged, so this does not affect any measurement.
        turn["tool_error"] = result.startswith("Error:")
        turn["final"] = False
        traj.turns.append(turn)

        traj.model_output += head
        traj.transcript += head + f"\nTOOL_RESULT: {result}\n"
        messages.append({"role": "assistant", "content": head})
        messages.append({"role": "user", "content": f"TOOL_RESULT: {result}"})
        any_tool_yet = True
    else:
        traj.stop_reason = "max_rounds"

    traj.messages = messages
    traj.wall_seconds = time.time() - t0
    return traj


def make_prefix(traj_dict: dict, upto_turn: int) -> list[dict]:
    """Build a forced prefix from a recorded trajectory's first ``upto_turn``
    turns (1-based count), for grafting. Returns the assistant/user message
    pairs that followed the initial user message.
    """
    out: list[dict] = []
    for t in traj_dict["turns"][:upto_turn]:
        if t.get("tool_call") is None:
            break                      # a final answer ends the prefix
        head = t["raw"]
        m = TOOL_CALL_RE.search(head)
        if m:
            head = head[: m.end()]
        out.append({"role": "assistant", "content": head})
        out.append({"role": "user", "content": f"TOOL_RESULT: {t['tool_result']}"})
    return out
