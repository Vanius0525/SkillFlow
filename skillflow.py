#!/usr/bin/env python3
"""
SkillFlow: Long-Horizon Agent Execution with Residual Context

Implements the SkillFlow framework from the paper, built on the
eval_scibench_with_skills.py agent harness. Key components:

1. Goal Anchoring      – parse user request into structured goal (obj, hard, pref, risk)
2. Skill Planning      – decompose task into skill sequence, select relevant skills
3. Skill Compression   – LLM-based task-aware compression of full skill docs before execution
4. Residual Context    – multi-channel memory (goal, exec, risk) with bypass to raw evidence
5. Local Execution     – execute each skill with local context, not full history
6. Action Gating       – (stub) risk-aware gating for high-impact actions

Usage:
  # Interactive mode
  python skillflow.py

  # Single task mode
  python skillflow.py --task "Solve the integral of x^2 from 0 to 3"

  # Batch evaluation on SciBench
  python skillflow.py --eval-scibench --subjects calculus --max 5
"""

import os
import re
import sys
import json
import copy
import time
import base64
import string
import argparse
import mimetypes
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from llm_backend import make_client
import condenser as cond
import agent_contract as ac
import gaia_scorer
import appworld_adapter as aw

# Backend selection (set from CLI in __main__; default = Claude API).
# context_window / compress_ratio are None until set from CLI; accessors below
# fall back to the module defaults (see get_context_window / compress_ratio).
_BACKEND = {"name": "claude", "base_url": None, "model": None,
            "context_window": None, "compress_ratio": None}

# Transcript condenser, set from the CLI. Kept as module state (like _BACKEND)
# so every run_skillflow call site picks it up without a signature change; each
# task still builds its own condenser instance, so worker threads never share.
_CONDENSER = {"name": "none", "keep_first": 1, "attention_window": 2,
              "max_size": 0, "ratio": 0.8, "max_calls": 4}

# Termination contract and GAIA judge, both set from the CLI.
_CONTRACT = {"submit_tool": True, "max_continues": ac.MAX_CONTINUES}
_JUDGE = {"mode": "official"}


def _make_condenser(stats, client=None, task_hint=""):
    """
    Build this task's condenser.

    `client`/`task_hint` are only used by --condenser llm, which needs a model
    to summarise with. They are threaded through rather than read from module
    state so that the summariser is per task, like the condenser itself.
    """
    kwargs = {}
    if _CONDENSER["name"] == "llm" and client is not None:
        kwargs["summarize"] = cond.make_summarizer(client, MODEL, task_hint)
        kwargs["max_calls_per_condensation"] = _CONDENSER["max_calls"]
    return cond.make_condenser(
        _CONDENSER["name"], stats=stats,
        keep_first=_CONDENSER["keep_first"],
        attention_window=_CONDENSER["attention_window"],
        max_size=_CONDENSER["max_size"],
        ratio=_CONDENSER["ratio"],
        **kwargs,
    )


def _make_client(api_key: str | None = None):
    """Construct the LLM client for the configured backend (claude | qwen)."""
    return make_client(
        _BACKEND["name"],
        api_key=api_key,
        base_url=_BACKEND["base_url"],
        model=_BACKEND["model"],
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HARNESS_ROOT = Path(__file__).parent
# All files created by the agent (bash / write_file) land here, not in the
# harness root. Reads/lists of relative paths are also resolved against it.
WORK_DIR = HARNESS_ROOT / "agent_workspace"
WORK_DIR.mkdir(parents=True, exist_ok=True)
SKILLS_DIR = Path.home() / "agent-harness" / "scibench_skills"

# SciBench paths
SCIBENCH_DATASET_DIR = HARNESS_ROOT / "SciBench" / "dataset" / "original"

# GAIA paths
GAIA_VALIDATION_DIR = HARNESS_ROOT / "GAIA" / "2023" / "validation"
GAIA_METADATA_FILE = GAIA_VALIDATION_DIR / "metadata.parquet"
GAIA_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
GAIA_TEXT_EXTS = {".txt", ".py", ".json", ".jsonld", ".csv", ".md"}

# DABstep paths
DABSTEP_DIR = HARNESS_ROOT / "DABstep"
DABSTEP_TASKS_DIR = DABSTEP_DIR / "data" / "tasks"
DABSTEP_CONTEXT_DIR = DABSTEP_DIR / "data" / "context"
ASSISTANTBENCH_DIR = HARNESS_ROOT / "AssistantBench"

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS_PER_CALL = 4096
TOKEN_BUDGET_PER_TASK = 8000
FORCE_ANSWER_THRESHOLD = 400
TASK_TIMEOUT = 300
REL_TOL = 0.05

# Circuit breakers for the agent loop. A small model that calls a tool the
# harness does not have (e.g. a skill doc written for a different harness)
# will otherwise repeat the identical call until the whole token budget is gone.
# Counted per identical (tool, args) signature across the whole turn, so varying
# the arguments is never penalised and genuine retries have room.
# Both are env-overridable because the right value is benchmark-dependent: 40
# is generous for GAIA, where a task is 5-15 steps, but truncates AppWorld,
# which allows up to 2000 API calls and whose tasks routinely need dozens of
# them. Capping there would measure the circuit breaker, not the agent.
MAX_IDENTICAL_TOOL_CALLS = int(os.environ.get("MAX_IDENTICAL_TOOL_CALLS", "5"))
MAX_TOOL_CALLS_PER_TURN = int(os.environ.get("MAX_TOOL_CALLS_PER_TURN", "40"))

# One `curl` of a web page can put an entire HTML document into the transcript,
# which then gets resent on every subsequent call. Cap what a tool may return.
MAX_TOOL_OUTPUT_CHARS = int(os.environ.get("MAX_TOOL_OUTPUT_CHARS", "16000"))

# max_tokens has to fit in whatever the context window has left, not just in the
# output budget: asking for 4096 when the input is already 31k of a 32k window
# is rejected outright with a 400, losing the whole task.
CONTEXT_SAFETY_MARGIN = 512     # slack for estimation error and template overhead

# "Unlimited" sentinel values — used when --no-limit or 0 is passed
UNLIMITED_TOKENS = 10_000_000   # 10M output tokens (effectively infinite)
UNLIMITED_TIMEOUT = 86400       # 24 hours

# ---------------------------------------------------------------------------
# Context-window-aware skill compression
# ---------------------------------------------------------------------------
# Skill docs are injected at FULL length by default. Task-aware compression
# (SkillFlow Component 3) only kicks in once the assembled execution prompt
# reaches CONTEXT_COMPRESS_RATIO of the model's context window — i.e. we
# compress a skill only when we are actually about to run out of room. The
# residual-context machinery (Component 4) is unchanged.
DEFAULT_CONTEXT_WINDOW = int(os.environ.get("MODEL_CONTEXT_WINDOW", "200000"))
CONTEXT_COMPRESS_RATIO = float(os.environ.get("CONTEXT_COMPRESS_RATIO", "0.8"))
_CHARS_PER_TOKEN = 4   # rough heuristic; enough to gauge context pressure


def _estimate_tokens(text: str) -> int:
    """Cheap, dependency-free token estimate (~4 chars/token)."""
    if not text:
        return 0
    return (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


def _content_to_text(content) -> str:
    """Flatten a user-message content (str or list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    parts.append(b.get("text", ""))
                elif b.get("type") == "image":
                    parts.append("[image]")  # non-text; negligible for the estimate
            else:
                parts.append(str(b))
        return "\n".join(parts)
    return str(content)


def _estimate_block(b) -> str:
    """
    Flatten one content block for size estimation.

    Separate from _content_to_text because that one only walks text/image
    blocks — it is used where those are all that exist. Here the bulk of the
    transcript is tool_result and tool_use payloads, and missing them would
    under-estimate the request badly.
    """
    if isinstance(b, dict):
        t = b.get("type")
        if t == "text":
            return b.get("text", "")
        if t == "tool_result":
            return _content_to_text(b.get("content"))
        if t == "tool_use":
            return json.dumps(b.get("input", {}), ensure_ascii=False, default=str)
        if t == "image":
            return "[image]"
        return str(b)
    if getattr(b, "text", None):
        return b.text
    inp = getattr(b, "input", None)
    if inp is not None:
        return json.dumps(inp, ensure_ascii=False, default=str)
    return str(b)


def _request_tokens(system: str, messages: list) -> int:
    """Estimate the input size of the next request."""
    total = _estimate_tokens(system)
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            total += sum(_estimate_tokens(_estimate_block(b)) for b in c)
        else:
            total += _estimate_tokens(_content_to_text(c))
    return total


def _truncate_output(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Keep the head and tail of an oversized tool result, drop the middle."""
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    return (
        text[:head]
        + f"\n\n[... {len(text) - limit} characters cut by the harness; a tool "
          f"result may not exceed {limit}. Re-run with something narrower — "
          f"grep, head, or a parser — rather than dumping the whole thing ...]\n\n"
        + text[-tail:]
    )


def get_context_window(client) -> int:
    """
    Resolve the model's max context window: explicit CLI override wins, then
    a backend-provided attribute (QwenClient.context_window), then env, then
    the module default (Claude ≈ 200k).
    """
    override = _BACKEND.get("context_window")
    if override:
        return int(override)
    cw = getattr(client, "context_window", None)
    if cw:
        return int(cw)
    return DEFAULT_CONTEXT_WINDOW


def compress_ratio() -> float:
    """Effective compression trigger ratio (CLI override, else module default)."""
    r = _BACKEND.get("compress_ratio")
    return float(r) if r is not None else CONTEXT_COMPRESS_RATIO

# ---------------------------------------------------------------------------
# Compression instrumentation
# ---------------------------------------------------------------------------
# Both compression components (3: task-aware skill compression, 4: residual
# compaction) are gated on context pressure. Whether that gate ever opens is an
# empirical question, not a given — with a 32k window and a 15k-char skill doc
# it may not — so every pressure reading is counted and reported next to
# accuracy. A run where `compression fired` is 0 measured planning and local
# context only, whatever the pipeline description says.


@dataclass
class CompressionStats:
    """Per-task record of when context pressure was checked and what fired."""
    window: int = 0
    threshold: int = 0
    checks: int = 0                 # pressure evaluated this many times
    fired: int = 0                  # ... and compression actually ran this many
    skill_compressions: int = 0
    residual_compressions: int = 0
    peak_prompt_tokens: int = 0     # largest request seen, transcript included
    chars_saved: int = 0
    fired_at_step_start: int = 0
    fired_in_loop: int = 0

    def observe(self, prompt_tokens: int) -> None:
        self.checks += 1
        self.peak_prompt_tokens = max(self.peak_prompt_tokens, prompt_tokens)


def compression_threshold(client) -> int:
    """Prompt size (tokens) at which skill + residual compression triggers."""
    return int(get_context_window(client) * compress_ratio())


class _CompressionAggregate:
    """
    Process-wide compression counters. One eval run is one process (see
    run-experiments.sh, which is strictly serial), so a module-level aggregate
    is enough; worker threads add to it under a lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.tasks = 0
        self.tasks_fired = 0
        self.checks = 0
        self.fired = 0
        self.skill_compressions = 0
        self.residual_compressions = 0
        self.chars_saved = 0
        self.peak_prompt_tokens = 0
        self.window = 0
        self.threshold = 0

    def add(self, s: CompressionStats) -> None:
        with self._lock:
            self.tasks += 1
            if s.fired:
                self.tasks_fired += 1
            self.checks += s.checks
            self.fired += s.fired
            self.skill_compressions += s.skill_compressions
            self.residual_compressions += s.residual_compressions
            self.chars_saved += s.chars_saved
            self.peak_prompt_tokens = max(self.peak_prompt_tokens, s.peak_prompt_tokens)
            self.window = s.window or self.window
            self.threshold = s.threshold or self.threshold

    def summary(self) -> dict:
        with self._lock:
            return {
                "tasks": self.tasks,
                "tasks_where_compression_fired": self.tasks_fired,
                "pressure_checks": self.checks,
                "compressions_fired": self.fired,
                "skill_compressions": self.skill_compressions,
                "residual_compressions": self.residual_compressions,
                "chars_saved": self.chars_saved,
                "peak_prompt_tokens": self.peak_prompt_tokens,
                "context_window": self.window,
                "trigger_threshold": self.threshold,
                "peak_over_threshold": (
                    round(self.peak_prompt_tokens / self.threshold, 3)
                    if self.threshold else None
                ),
            }

    def render(self) -> str:
        s = self.summary()
        if not s["tasks"]:
            return "  compression        : (no tasks recorded)"
        lines = [
            f"  compression fired  : {s['tasks_where_compression_fired']}/{s['tasks']} tasks"
            f"  ({s['compressions_fired']} times in {s['pressure_checks']} pressure checks)",
            f"  trigger threshold  : {s['trigger_threshold']:,} tok"
            f"  ({compress_ratio():.0%} of {s['context_window']:,})",
            f"  peak request seen  : {s['peak_prompt_tokens']:,} tok"
            + (f"  ({s['peak_over_threshold']:.2f}x threshold)"
               if s["peak_over_threshold"] is not None else ""),
        ]
        if s["compressions_fired"]:
            lines.append(
                f"  skill/residual     : {s['skill_compressions']} skill docs, "
                f"{s['residual_compressions']} exec records, "
                f"{s['chars_saved']:,} chars saved"
            )
        else:
            lines.append(
                "  [!] compression NEVER fired: components 3 and 4 were inactive for "
                "this entire run. Any measured effect comes from goal anchoring, "
                "iterative planning and per-step local context only."
            )
        return chr(10).join(lines)


COMPRESSION_AGG = _CompressionAggregate()


ALL_SUBJECTS = [
    "atkins", "calculus", "chemmc", "class", "diff",
    "fund", "matter", "quan", "stat", "thermo",
]

# ---------------------------------------------------------------------------
# Data classes for SkillFlow state
# ---------------------------------------------------------------------------


@dataclass
class GoalAnchor:
    """Persistent structured goal representation G = (obj, hard, pref, risk)."""
    objective: str = ""           # G^obj: core task objective
    hard_constraints: list = field(default_factory=list)  # G^hard: never violate
    preferences: list = field(default_factory=list)       # G^pref: soft preferences
    risk_boundaries: list = field(default_factory=list)   # G^risk: action boundaries
    raw_request: str = ""         # bypass channel: original user request verbatim


@dataclass
class ExecMemoryItem:
    """One skill execution record m_i (raw until compressed under context pressure)."""
    skill_name: str = ""
    subgoal: str = ""
    key_outcome: str = ""        # raw full output when compressed=False; summary when True
    evidence: str = ""           # raw snippet / file ref for bypass
    status: str = "pending"      # success | failed | pending
    unresolved: str = ""         # next-step dependencies
    compressed: bool = True      # False = raw result awaiting lazy compression


@dataclass
class ResidualContext:
    """
    R_t = (R^goal, R^exec, R^risk)
    Multi-channel residual memory with bypass to raw evidence.
    """
    # Channel 1: Goal Residual – persistent, near-lossless
    goal_text: str = ""
    hard_constraints: list = field(default_factory=list)

    # Channel 2: Execution Residual – compressed skill states
    exec_items: list = field(default_factory=list)  # list[ExecMemoryItem]

    # Channel 3: Risk Residual – unresolved high-impact conditions
    risk_items: list = field(default_factory=list)   # list[str]

    # Bypass channel: raw snippets attached to summaries (Section 5.2)
    raw_evidence: list = field(default_factory=list)  # list[dict] with source refs

    def to_prompt_text(self) -> str:
        """Serialize residual context into a prompt-ready string."""
        parts = []

        # Goal channel (always present)
        parts.append("## Goal Residual")
        parts.append(self.goal_text)
        if self.hard_constraints:
            parts.append("### Hard Constraints (MUST preserve)")
            for c in self.hard_constraints:
                parts.append(f"- {c}")

        # Execution channel
        if self.exec_items:
            parts.append("\n## Execution Residual")
            for item in self.exec_items:
                if isinstance(item, dict):
                    item = ExecMemoryItem(**item)
                parts.append(
                    f"- [{item.status}] {item.skill_name}: {item.key_outcome}"
                )
                if item.unresolved:
                    parts.append(f"  (unresolved: {item.unresolved})")

        # Risk channel
        if self.risk_items:
            parts.append("\n## Risk Residual")
            for r in self.risk_items:
                parts.append(f"- ⚠ {r}")

        # Raw evidence bypass (Section 5.2 residual pathways)
        if self.raw_evidence:
            parts.append("\n## Raw Evidence (bypass channel)")
            for ev in self.raw_evidence[-5:]:  # keep last 5 for compactness
                src = ev.get("source", "unknown")
                snippet = ev.get("snippet", "")[:300]
                parts.append(f"- [{src}]: {snippet}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Skills loader (from harness)
# ---------------------------------------------------------------------------

SKILL_DOCS: dict = {}  # skill_name -> full SKILL.md content


def _parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    for line in fm_text.splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            result[key] = val
    return result


def _infer_description(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return line[:200]
    return "(no description)"


def load_skills(skills_dir: Path) -> str:
    """Populate SKILL_DOCS and return a compact index string."""
    global SKILL_DOCS
    SKILL_DOCS = {}
    if not skills_dir.exists():
        return ""
    index_rows = []
    for skill_path in sorted(skills_dir.iterdir()):
        skill_md = skill_path / "SKILL.md"
        if not (skill_path.is_dir() and skill_md.exists()):
            continue
        content = skill_md.read_text(encoding="utf-8").strip()
        fm = _parse_frontmatter(content)
        name = fm.get("name") or skill_path.name
        description = fm.get("description") or _infer_description(content)
        SKILL_DOCS[name] = content
        short_desc = description if len(description) <= 160 else description[:157] + "..."
        index_rows.append(f"- **{name}**: {short_desc}")
    if not index_rows:
        return ""
    header = (
        "# Available Skills\n\n"
        "Each entry shows skill name and brief description.\n\n"
    )
    return header + "\n".join(index_rows)


# ---------------------------------------------------------------------------
# Tool definitions (from harness)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command or shell script. Use this to run Python "
            "calculations, install packages, or perform any shell operation. "
            "IMPORTANT: Do NOT generate plots, charts, or images — you cannot "
            "see image outputs. Only use print() to output numeric results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to execute."},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30).", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates parent directories if needed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories at a given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: harness root).", "default": "."}
            },
        },
    },
]


class Toolset:
    """
    The tool surface for one task, and how a call to it is executed.

    Benchmarks do not share an action space. GAIA and SciBench act on a
    filesystem through bash; AppWorld's action space IS a Python interpreter
    bound to a live environment, and handing that agent a bash tool only invites
    it to spend its budget on calls the environment cannot serve. Rather than
    branching inside the agent loop, each benchmark supplies a Toolset.

    `should_stop` exists because completion is not always a message: AppWorld
    ends when the environment says the task is done, not when the model says so.
    """

    def base_tools(self) -> list:
        return TOOLS

    def tools(self) -> list:
        """Base tools, plus `submit` when the termination contract is on."""
        if _CONTRACT["submit_tool"]:
            return self.base_tools() + [ac.SUBMIT_TOOL]
        return self.base_tools()

    def execute(self, name: str, inputs: dict) -> str:
        return execute_tool(name, inputs)

    def should_stop(self) -> bool:
        """Checked after each tool call; True ends the turn."""
        return False


DEFAULT_TOOLSET = Toolset()


def active_tools() -> list:
    """
    Tool schemas for this run: the harness tools, plus `submit` when the
    termination contract is on. Built per call rather than baked into TOOLS so
    that both `--no-submit-tool` and the default agree about what exists —
    including in the "no such tool" message below.
    """
    return DEFAULT_TOOLSET.tools()


def _unknown_tool_error(name: str) -> str:
    """
    Explicit, actionable error for a tool this harness does not register.

    Skill docs imported from other harnesses may document tools (e.g.
    `internet_search`) that do not exist here. A bland "Unknown tool: X" reads
    like ordinary output to a small model, which then retries verbatim, so name
    the constraint and the way forward instead.
    """
    available = ", ".join(t["name"] for t in active_tools())
    return (
        f"[error] No such tool: '{name}'. This harness provides only: {available}. "
        f"Calling '{name}' again will always fail — use one of the available tools "
        f"instead (shell commands and scripts go through bash)."
    )


def _tool_signature(name: str, inputs: dict) -> str:
    """Stable key for detecting the model repeating an identical tool call."""
    try:
        return f"{name}:{json.dumps(inputs, sort_keys=True, ensure_ascii=False)}"
    except TypeError:
        return f"{name}:{inputs!r}"


def execute_tool(name: str, inputs: dict) -> str:
    try:
        if name == "bash":
            command = inputs["command"]
            timeout = inputs.get("timeout", 30)
            env = os.environ.copy()
            env["MPLBACKEND"] = "Agg"  # prevent matplotlib GUI popups
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(WORK_DIR), env=env,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return _truncate_output(output.strip()) or "(no output)"

        elif name == "read_file":
            path = Path(inputs["path"]).expanduser()
            if not path.is_absolute():
                path = WORK_DIR / path
            return _truncate_output(path.read_text(encoding="utf-8"))

        elif name == "write_file":
            path = Path(inputs["path"]).expanduser()
            if not path.is_absolute():
                path = WORK_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(inputs["content"], encoding="utf-8")
            return f"Written {len(inputs['content'])} bytes to {path}"

        elif name == "list_files":
            path = Path(inputs.get("path", ".")).expanduser()
            if not path.is_absolute():
                path = WORK_DIR / path
            entries = [f"[{'d' if e.is_dir() else 'f'}] {e.name}" for e in sorted(path.iterdir())]
            return "\n".join(entries) if entries else "(empty directory)"

        else:
            return _unknown_tool_error(name)

    except subprocess.TimeoutExpired:
        return f"[error] Command timed out after {inputs.get('timeout', 30)}s"
    except FileNotFoundError as e:
        return f"[error] File not found: {e}"
    except Exception as e:
        return f"[error] {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# SkillFlow Component 1: Goal Anchoring
# ---------------------------------------------------------------------------

GOAL_ANCHOR_SYSTEM = """\
You are a goal analysis assistant. Given a user request, extract a structured goal representation.

Output EXACTLY this JSON format (no markdown fences):
{
  "objective": "the core task objective in one sentence",
  "hard_constraints": ["constraint that must never be violated", ...],
  "preferences": ["soft preference that can be traded off", ...],
  "risk_boundaries": ["high-impact action that needs caution", ...]
}

Be concise. Hard constraints are things like "do not delete files", "must use specific units".
Preferences are stylistic or optional requirements. Risk boundaries are actions that could cause harm if wrong.
If a category is empty, use an empty list []."""


def anchor_goal(
    client: anthropic.Anthropic,
    user_request: str,
) -> tuple[GoalAnchor, int, int]:
    """
    Component 1: Parse user request into structured goal G = (obj, hard, pref, risk).
    Returns (GoalAnchor, input_tokens, output_tokens).
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=GOAL_ANCHOR_SYSTEM,
            messages=[{"role": "user", "content": user_request}],
        )
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        raw = response.content[0].text.strip()

        # Parse JSON (handle possible markdown fences)
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)

        goal = GoalAnchor(
            objective=parsed.get("objective", user_request),
            hard_constraints=parsed.get("hard_constraints", []),
            preferences=parsed.get("preferences", []),
            risk_boundaries=parsed.get("risk_boundaries", []),
            raw_request=user_request,  # bypass: keep original verbatim
        )
        return goal, in_tok, out_tok

    except Exception as e:
        # Fallback: use raw request as objective
        return GoalAnchor(
            objective=user_request,
            raw_request=user_request,
        ), 0, 0


# ---------------------------------------------------------------------------
# SkillFlow Component 2: Iterative Skill Planning
# ---------------------------------------------------------------------------

SKILL_PLAN_SYSTEM = """\
You are a task planning assistant for an iterative agent. Given a task, the \
current execution state (what has been done so far), and a list of available \
skills, decide the NEXT single skill to execute.

Rules:
1. If the task is already completed based on the execution state, reply with \
exactly the word "done" (nothing else).
2. If no skill is relevant, reply with exactly the word "none" (nothing else).
3. Otherwise, reply with EXACTLY ONE skill name from the list (nothing else).
4. Do NOT repeat a skill that has already succeeded unless the prior result \
was insufficient and you need to retry with different parameters.
5. Consider what information is still missing and pick the skill that best \
addresses the next gap."""


def plan_next_skill(
    client: anthropic.Anthropic,
    goal: GoalAnchor,
    residual: ResidualContext,
    skills_index: str,
) -> tuple[str | None, int, int]:
    """
    Plan the next skill to execute based on current residual state.
    Returns (skill_name, in_tok, out_tok).
    Returns None as skill_name when task is done or no skill is needed.
    """
    if not skills_index or not SKILL_DOCS:
        return None, 0, 0

    # Build execution state summary from residual
    exec_summary = ""
    if residual.exec_items:
        exec_lines = []
        for item in residual.exec_items:
            if isinstance(item, dict):
                item = ExecMemoryItem(**item)
            exec_lines.append(
                f"- [{item.status}] {item.skill_name}: {item.key_outcome}"
            )
            if item.unresolved:
                exec_lines.append(f"  (unresolved: {item.unresolved})")
        exec_summary = "## Completed steps so far:\n" + "\n".join(exec_lines)
    else:
        exec_summary = "## Completed steps so far:\n(none — this is the first step)"

    risk_summary = ""
    if residual.risk_items:
        risk_summary = "\n## Unresolved risks:\n" + "\n".join(
            f"- {r}" for r in residual.risk_items
        )

    prompt = (
        f"## Task\n"
        f"Objective: {goal.objective}\n"
        f"Original request: {goal.raw_request}\n"
        f"Hard constraints: {', '.join(goal.hard_constraints) or 'none'}\n\n"
        f"{exec_summary}\n"
        f"{risk_summary}\n\n"
        f"{skills_index}\n\n"
        f"What is the next single skill to execute? "
        f"Reply with the skill name, 'done', or 'none'."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=64,
            system=SKILL_PLAN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip().lower()
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens

        # Check for done / none
        if raw in ("done", "none"):
            return None, in_tok, out_tok

        # Match against known skill names
        for skill_name in SKILL_DOCS:
            if skill_name.lower() in raw:
                return skill_name, in_tok, out_tok

        # No match — treat as done
        return None, in_tok, out_tok

    except Exception as e:
        print(f"  [WARN] skill planning failed: {e}")
        return None, 0, 0


# ---------------------------------------------------------------------------
# SkillFlow Component 3: Task-Aware Skill Compression
# ---------------------------------------------------------------------------

SKILL_COMPRESS_SYSTEM = """\
You are a context compression assistant. Given a full skill document and a task description, \
produce a compressed version that retains ONLY the information needed to execute this specific task.

Rules:
1. Keep all tool invocation commands, script paths, and API usage patterns needed for the task.
2. Keep configuration requirements (env vars, dependencies) relevant to the task.
3. Remove examples, features, and documentation sections NOT relevant to the task.
4. Preserve exact command syntax — do not paraphrase commands.
5. Output the compressed skill doc directly, no preamble.
6. Omit sections that are unnecessary for this task; compress appropriately while preserving all task-relevant instructions."""


def compress_skill(
    client: anthropic.Anthropic,
    skill_name: str,
    skill_doc: str,
    goal: GoalAnchor,
) -> tuple[str, int, int]:
    """
    Component 3: LLM-based task-aware compression of skill doc.
    Compresses skill_doc based on the specific task goal, keeping only
    what's needed for execution. Returns (compressed_doc, in_tok, out_tok).
    """
    # Skip compression for very short docs
    if len(skill_doc) < 500:
        return skill_doc, 0, 0

    prompt = (
        f"## Task\n"
        f"Objective: {goal.objective}\n"
        f"Hard constraints: {', '.join(goal.hard_constraints) or 'none'}\n\n"
        f"## Full Skill Document: {skill_name}\n\n"
        f"{skill_doc}\n\n"
        f"Produce the compressed version now."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16384,
            system=SKILL_COMPRESS_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        compressed = response.content[0].text.strip()
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens

        # Sanity check: if compression produced something too short or empty, use original
        if len(compressed) < 50:
            return skill_doc, in_tok, out_tok

        return compressed, in_tok, out_tok

    except Exception as e:
        print(f"  [WARN] skill compression failed for {skill_name}: {e}")
        return skill_doc, 0, 0


# ---------------------------------------------------------------------------
# SkillFlow Component 4: Residual Context Management
# ---------------------------------------------------------------------------

def init_residual(goal: GoalAnchor) -> ResidualContext:
    """Initialize R_0 from goal anchor."""
    return ResidualContext(
        goal_text=f"Objective: {goal.objective}",
        hard_constraints=list(goal.hard_constraints),
        exec_items=[],
        risk_items=list(goal.risk_boundaries),
        raw_evidence=[{
            "source": "original_request",
            "snippet": goal.raw_request[:500],
        }],
    )


COMPRESS_EXEC_SYSTEM = """\
You are an execution state compressor. Given the skill that was just executed, \
its output, and the current goal, produce a compressed execution record.

Output EXACTLY this JSON (no markdown fences):
{
  "skill_name": "name of the skill",
  "subgoal": "what this skill step was trying to achieve",
  "key_outcome": "the main result or answer produced",
  "evidence": "key raw snippet or reference supporting the outcome",
  "status": "success or failed",
  "unresolved": "any remaining issues or dependencies, empty string if none"
}"""


def compress_execution(
    client: anthropic.Anthropic,
    skill_name: str,
    execution_output: str,
    goal: GoalAnchor,
) -> tuple[ExecMemoryItem, int, int]:
    """
    Compress a skill execution result into a structured memory item.
    Preserves raw evidence as a bypass channel.
    """
    prompt = (
        f"Goal: {goal.objective}\n"
        f"Skill executed: {skill_name}\n"
        f"Output (truncated to 2000 chars):\n{execution_output[:2000]}\n\n"
        f"Compress this execution into the JSON record."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=COMPRESS_EXEC_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)

        item = ExecMemoryItem(
            skill_name=parsed.get("skill_name", skill_name),
            subgoal=parsed.get("subgoal", ""),
            key_outcome=parsed.get("key_outcome", ""),
            evidence=parsed.get("evidence", execution_output[:200]),
            status=parsed.get("status", "success"),
            unresolved=parsed.get("unresolved", ""),
        )
        return item, response.usage.input_tokens, response.usage.output_tokens

    except Exception:
        # Fallback: simple compression
        return ExecMemoryItem(
            skill_name=skill_name,
            subgoal="execute skill",
            key_outcome=execution_output[:200],
            evidence=execution_output[:100],
            status="success",
            unresolved="",
        ), 0, 0


def update_residual(
    residual: ResidualContext,
    exec_item: ExecMemoryItem,
    raw_output: str,
) -> ResidualContext:
    """
    R_t = UpdateResidual(R_{t-1}, S_t, e_t, G)
    Updates all three channels and appends raw evidence bypass.
    """
    new_r = copy.deepcopy(residual)

    # Channel 2: append execution record
    new_r.exec_items.append(asdict(exec_item))

    # Channel 3: update risk items based on unresolved issues
    if exec_item.unresolved:
        new_r.risk_items.append(f"From {exec_item.skill_name}: {exec_item.unresolved}")

    # Remove resolved risk items if skill succeeded
    if exec_item.status == "success" and exec_item.skill_name:
        new_r.risk_items = [
            r for r in new_r.risk_items
            if exec_item.skill_name not in r or "unresolved" in r.lower()
        ]

    # Bypass channel: raw evidence (Section 5.2)
    new_r.raw_evidence.append({
        "source": f"skill:{exec_item.skill_name}",
        "snippet": raw_output[:300],
    })

    # Keep raw evidence bounded (layered memory with rollback capability)
    if len(new_r.raw_evidence) > 10:
        new_r.raw_evidence = new_r.raw_evidence[-10:]

    return new_r


def add_raw_execution(
    residual: ResidualContext,
    skill_name: str,
    raw_output: str,
) -> ResidualContext:
    """
    Append a skill's RAW execution result to the residual WITHOUT any LLM call.

    Execution-result compression is deferred: the raw output stays in the
    execution channel at full length until context pressure crosses the compress
    ratio, at which point compress_residual() folds it into a compact record.
    """
    new_r = copy.deepcopy(residual)
    new_r.exec_items.append(asdict(ExecMemoryItem(
        skill_name=skill_name or "direct",
        subgoal="",
        key_outcome=raw_output,      # full, uncompressed
        evidence=raw_output,
        status="success",
        unresolved="",
        compressed=False,
    )))
    new_r.raw_evidence.append({
        "source": f"skill:{skill_name or 'direct'}",
        "snippet": raw_output[:300],
    })
    if len(new_r.raw_evidence) > 10:
        new_r.raw_evidence = new_r.raw_evidence[-10:]
    return new_r


def compress_residual(
    client: anthropic.Anthropic,
    residual: ResidualContext,
    goal: GoalAnchor,
) -> tuple[ResidualContext, int, int]:
    """
    Lazily compress any RAW (uncompressed) execution records in the residual into
    structured memory items. Called ONLY under context pressure (see
    assemble_execution_context), never on every step. Risk-channel bookkeeping
    that used to live in update_residual happens here, at compression time.

    Returns (new_residual, in_tokens, out_tokens).
    """
    in_tot = out_tot = 0
    new_r = copy.deepcopy(residual)
    new_items = []
    for raw in new_r.exec_items:
        item = raw if isinstance(raw, dict) else asdict(raw)
        if item.get("compressed", True):
            new_items.append(item)
            continue
        comp, cin, cout = compress_execution(
            client, item.get("skill_name", ""), item.get("key_outcome", ""), goal
        )
        in_tot += cin
        out_tot += cout
        d = asdict(comp)
        d["compressed"] = True
        new_items.append(d)
        # Risk channel (moved from update_residual → applied at compression time)
        if comp.unresolved:
            new_r.risk_items.append(f"From {comp.skill_name}: {comp.unresolved}")
        if comp.status == "success" and comp.skill_name:
            new_r.risk_items = [
                r for r in new_r.risk_items
                if comp.skill_name not in r or "unresolved" in r.lower()
            ]
    new_r.exec_items = new_items
    return new_r, in_tot, out_tot


# ---------------------------------------------------------------------------
# SkillFlow Component 5: Local Skill Execution (Agent Loop)
# ---------------------------------------------------------------------------

BASE_SYSTEM_SCIBENCH = """\
You are a highly capable scientific problem-solving assistant with access to \
tools for executing scripts and interacting with the filesystem.
You are given college-level science and mathematics problems (physics, \
chemistry, calculus, etc.). Work through each problem step by step.
When computation is needed, use the bash tool to run Python calculations \
rather than computing by hand. Install any missing Python packages \
automatically with pip and retry — do not ask the user to install them.

Your response must end with a line in this exact format:
FINAL ANSWER: <numeric value>

The final answer must be a single number (integer or decimal). \
Do NOT include units or extra text after the number."""

BASE_SYSTEM_GAIA = """\
You are a highly capable assistant with access to tools for executing scripts \
and interacting with the filesystem.
When you need to perform actions, use the available tools rather than just \
describing what you would do.
If a script fails due to a missing Python package, install it automatically \
with pip and retry. Do not ask the user to install packages manually.

Your response must end with a line in this exact format:
FINAL ANSWER: <your answer>

The final answer should be a short, direct value (a word, number, name, date, \
etc.) with no extra explanation."""

# Default for backward compat
BASE_SYSTEM = BASE_SYSTEM_SCIBENCH

FORCE_ANSWER_MSG = (
    "URGENT: You are running out of time/budget. "
    "Stop all tool use immediately. Based on everything you have done so far, "
    "provide your best FINAL ANSWER now in the format:\n"
    "FINAL ANSWER: <your answer>\n"
    "Give your best guess even if uncertain. Do NOT call any more tools."
)

# Seconds before deadline to trigger force-answer (instead of hard timeout)
TIMEOUT_GRACE_SECONDS = 30


def build_execution_prompt(
    goal: GoalAnchor,
    residual: ResidualContext,
    compressed_skills: dict[str, str],
    base_system: str = BASE_SYSTEM,
) -> str:
    """
    Build the execution prompt: C_t^local = [R^goal, R^exec, R^risk, S_t, E_t]
    This is the multi-channel composition from Section 3.6.
    """
    parts = [base_system]

    # Channel 1: Goal residual (always first, always present)
    parts.append(f"\n# Task Goal (Residual Channel)\n{residual.to_prompt_text()}")

    # Skill docs (full by default; task-aware compressed only under context pressure)
    for skill_name, skill_doc in compressed_skills.items():
        parts.append(f"\n# Skill: {skill_name}\n\n{skill_doc}")

    return "\n".join(parts)


class ContextCompressor:
    """
    Owns the execution system prompt for one skill step and compresses it when a
    request crosses the context-pressure threshold.

    The pressure check used to run only at step assembly, which measures the
    emptiest moment of the step: the transcript is empty there, so the estimate
    was little more than base_system + one skill doc + the residual. With a 32k
    window that never reached 80%, and components 3 and 4 never ran.

    What actually fills the window is the transcript — a single bash result may
    be MAX_TOOL_OUTPUT_CHARS long and is resent on every subsequent call — so
    the same compressor is handed to run_agent_loop, which re-checks before
    every model call with the live transcript included in the estimate.

    Compression is idempotent: the skill doc is compressed at most once, and
    residual records are only compressed while raw ones remain, so a check that
    has nothing left to shrink is free and is not counted as a firing.
    """

    def __init__(self, client, goal: GoalAnchor, residual: ResidualContext,
                 skill_name: Optional[str], base_system: str,
                 stats: "CompressionStats", verbose: bool = False,
                 prefix: str = "[SkillFlow]", step: Optional[int] = None):
        self.client = client
        self.goal = goal
        self.residual = residual
        self.base_system = base_system
        self.stats = stats
        self.verbose = verbose
        self.prefix = prefix
        self.step = step

        self.skill_name = skill_name if (skill_name and skill_name in SKILL_DOCS) else None
        self.threshold = compression_threshold(client)
        stats.window = get_context_window(client)
        stats.threshold = self.threshold

        self._skill_docs: dict[str, str] = {}
        self.orig_len = self.used_len = 0
        if self.skill_name:
            doc = SKILL_DOCS[self.skill_name]
            self._skill_docs[self.skill_name] = doc
            self.orig_len = self.used_len = len(doc)
        self._skill_compressed = False

    def system(self) -> str:
        """Current execution system prompt (compressed or not)."""
        return build_execution_prompt(
            self.goal, self.residual, self._skill_docs, base_system=self.base_system
        )

    def _raw_exec_count(self) -> int:
        """Execution records still held at full length in the residual."""
        return sum(
            1 for it in self.residual.exec_items
            if not (it if isinstance(it, dict) else asdict(it)).get("compressed", True)
        )

    def _has_work(self) -> bool:
        """Is there anything left that compression could still shrink?"""
        if self.skill_name and not self._skill_compressed:
            return True
        return self._raw_exec_count() > 0

    def check(self, prompt_tokens: int, where: str) -> tuple[Optional[str], int, int]:
        """
        Record a pressure reading and compress if it crosses the threshold.

        Returns (new_system or None when nothing changed, in_tok, out_tok).
        Every call is counted, so `stats.checks` is the denominator for "how
        often did we look" and `stats.fired` the numerator for "how often did
        it matter".
        """
        self.stats.observe(prompt_tokens)
        if prompt_tokens < self.threshold or not self._has_work():
            return None, 0, 0

        before = len(self.system())
        cin = cout = 0

        # 1) Compress the skill doc (Component 3) — once per step.
        if self.skill_name and not self._skill_compressed:
            compressed, sk_in, sk_out = compress_skill(
                self.client, self.skill_name, SKILL_DOCS[self.skill_name], self.goal
            )
            self._skill_docs[self.skill_name] = compressed
            self.used_len = len(compressed)
            self._skill_compressed = True
            self.stats.skill_compressions += 1
            cin += sk_in
            cout += sk_out

        # 2) Compress raw execution records in the residual (Component 4).
        n_raw = self._raw_exec_count()
        if n_raw:
            self.residual, r_in, r_out = compress_residual(
                self.client, self.residual, self.goal
            )
            self.stats.residual_compressions += n_raw
            cin += r_in
            cout += r_out

        system = self.system()
        self.stats.fired += 1
        self.stats.chars_saved += max(0, before - len(system))
        if where == "loop":
            self.stats.fired_in_loop += 1
        else:
            self.stats.fired_at_step_start += 1

        if self.verbose:
            print(f"{self.prefix} [compress@{where}] step={self.step} "
                  f"~{prompt_tokens}tok >= {self.threshold} -> system "
                  f"{before} -> {len(system)} chars "
                  f"(skill={self.stats.skill_compressions}, exec={n_raw})", flush=True)
        return system, cin, cout


def assemble_execution_context(
    client,
    goal: GoalAnchor,
    residual: ResidualContext,
    skill_name: Optional[str],
    msg_content,
    base_system: str = BASE_SYSTEM,
    verbose: bool = False,
    prefix: str = "[SkillFlow]",
    step: Optional[int] = None,
    stats: Optional["CompressionStats"] = None,
) -> tuple[str, ContextCompressor, int, int, int, int]:
    """
    Build the execution system prompt for one step and return the compressor
    that owns it.

    The skill doc and the accumulated residual go in at FULL length first; the
    assembled prompt is then measured. Only if it reaches compress_ratio() of
    the model's context window do we compress. This is the step-start reading
    only — the returned compressor must be passed to run_agent_loop, which
    re-checks before every model call with the transcript included. That is
    where the window actually fills up.

    Returns (system, compressor, orig_len, used_len, in_tok, out_tok).
    orig_len/used_len are 0 when no skill doc is in play.
    """
    compressor = ContextCompressor(
        client, goal, residual, skill_name, base_system,
        stats if stats is not None else CompressionStats(),
        verbose=verbose, prefix=prefix, step=step,
    )
    system = compressor.system()
    prompt_tokens = (_estimate_tokens(system)
                     + _estimate_tokens(_content_to_text(msg_content)))

    new_system, cin, cout = compressor.check(prompt_tokens, where="step-start")
    if new_system is not None:
        system = new_system
    elif verbose:
        print(f"{prefix} Step {step}b: prompt ~{prompt_tokens}tok < "
              f"{compressor.threshold} ({compress_ratio():.0%} of "
              f"{get_context_window(client)}) -> full context "
              f"(no compression)", flush=True)

    return system, compressor, compressor.orig_len, compressor.used_len, cin, cout


def _force_final_answer(
    client: anthropic.Anthropic,
    messages: list,
    system: str,
    reason: str,
    max_tokens: int | None = None,
) -> tuple[str, int, int]:
    """Force the LLM to give a final answer based on what it has so far."""
    messages.append({"role": "user", "content": FORCE_ANSWER_MSG})
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens or max(FORCE_ANSWER_THRESHOLD, 256),
            system=system,
            messages=messages,
        )
        text = "\n".join(
            b.text for b in response.content if hasattr(b, "text") and b.text
        )
        messages.append({"role": "assistant", "content": response.content})
        return (
            f"[{reason}] " + text,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
    except Exception as e:
        print(f"    [WARN] force-answer call failed: {e}", flush=True)
        return f"[{reason}] (force-answer failed)", 0, 0


def run_agent_loop(
    client: anthropic.Anthropic,
    messages: list,
    system: str,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    deadline: float | None = None,
    verbose: bool = True,
    compressor: Optional[ContextCompressor] = None,
    condenser: Optional["cond.Condenser"] = None,
    contract_stats: Optional["ac.ContractStats"] = None,
    toolset: Optional[Toolset] = None,
) -> tuple[str, int, int]:
    """
    Run the agentic tool-use loop.
    On timeout or budget exhaustion, forces LLM to give a final answer
    instead of raising an exception.

    When `compressor` is supplied, context pressure is re-evaluated before every
    model call and the system prompt is compressed in place once it crosses the
    threshold. Without it the loop still refuses to overflow the window, but its
    only recourse is to abandon the turn and force an answer.

    Returns (final_text, total_input_tokens, total_output_tokens).
    """
    total_in = total_out = 0
    budget_enabled = token_budget < UNLIMITED_TOKENS
    tool_call_count = 0
    repeat_counts: dict[str, int] = {}
    p = "    [agent]"
    submit_enabled = _CONTRACT["submit_tool"]
    max_continues = _CONTRACT["max_continues"]
    continues = 0
    tools = toolset if toolset is not None else DEFAULT_TOOLSET
    if contract_stats is not None:
        contract_stats.submit_enabled = submit_enabled

    while True:
        # ---- Context pressure: bound the request before measuring the room ----
        # This is the point where the window actually fills: the transcript
        # carries every tool result (each up to MAX_TOOL_OUTPUT_CHARS) and is
        # resent on every call, so it dwarfs the system prompt long before step
        # assembly would notice. Acting here is what keeps the "context
        # exhausted" bail-out below a last resort rather than the normal exit.
        #
        # Cheapest first: the condenser masks old observations for free, and
        # only what it cannot recover is worth spending a compression call on.
        # Either may be absent — that is what makes the ablation cells
        # (condenser only / compressor only / both / neither) possible.
        if condenser is not None:
            condenser.condense(
                messages, _request_tokens(system, messages),
                condenser.threshold_for(get_context_window(client)),
                verbose=verbose, prefix=p + " ",
            )

        if compressor is not None:
            new_system, comp_in, comp_out = compressor.check(
                _request_tokens(system, messages), where="loop"
            )
            total_in += comp_in
            total_out += comp_out
            if new_system is not None:
                system = new_system

        # Room left in the context window for the reply. The transcript grows
        # with every tool result, so this shrinks even when the output budget
        # does not — and a max_tokens that does not fit is a hard 400.
        ctx_room = (get_context_window(client)
                    - _request_tokens(system, messages)
                    - CONTEXT_SAFETY_MARGIN)
        force_max = max(64, min(FORCE_ANSWER_THRESHOLD, ctx_room))

        # ---- Timeout check: force answer instead of raising ----
        if deadline is not None and time.time() >= deadline - TIMEOUT_GRACE_SECONDS:
            if verbose:
                print(f"{p} approaching deadline, forcing final answer...", flush=True)
            text, fin, fout = _force_final_answer(
                client, messages, system, "timeout", force_max
            )
            total_in += fin
            total_out += fout
            return text, total_in, total_out

        remaining = token_budget - total_out

        # ---- Context check: no room left for a useful reply ----
        if ctx_room < FORCE_ANSWER_THRESHOLD:
            if verbose:
                print(f"{p} context nearly full ({ctx_room} tokens of room left), "
                      f"forcing final answer...", flush=True)
            if ctx_room < 64:
                # Not even room for a forced answer; report rather than 400.
                return "[context exhausted] ", total_in, total_out
            text, fin, fout = _force_final_answer(
                client, messages, system, "context exhausted", force_max
            )
            total_in += fin
            total_out += fout
            return text, total_in, total_out

        # ---- Budget check: force answer instead of truncating ----
        if budget_enabled and remaining <= FORCE_ANSWER_THRESHOLD:
            if verbose:
                print(f"{p} budget nearly exhausted ({remaining} remaining), forcing final answer...", flush=True)
            text, fin, fout = _force_final_answer(
                client, messages, system, "budget exceeded", force_max
            )
            total_in += fin
            total_out += fout
            return text, total_in, total_out

        # ---- Normal call with tools ----
        call_max = MAX_TOKENS_PER_CALL if not budget_enabled else min(MAX_TOKENS_PER_CALL, remaining)
        call_max = max(1, min(call_max, ctx_room))
        response = client.messages.create(
            model=MODEL,
            max_tokens=call_max,
            system=system,
            tools=tools.tools(),
            messages=messages,
        )
        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens

        text_parts = [b.text for b in response.content if hasattr(b, "text") and b.text]

        if response.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": response.content})
            text = "\n".join(text_parts)

            # Stopping is not the same as finishing. A model that trails off
            # mid-plan gets nudged rather than scored on its last line.
            if (submit_enabled and not ac.has_explicit_answer(text)
                    and continues < max_continues):
                continues += 1
                if contract_stats is not None:
                    contract_stats.continues += 1
                messages.append({"role": "user", "content": ac.CONTINUE_MSG})
                if verbose:
                    print(f"{p} end_turn with no answer, nudging "
                          f"({continues}/{max_continues})", flush=True)
                continue

            if contract_stats is not None:
                if not ac.has_explicit_answer(text):
                    contract_stats.ended_without_answer += 1
                elif continues:
                    contract_stats.rescued += 1
            if verbose:
                print(f"{p} end_turn after {tool_call_count} tool calls, "
                      f"tokens={total_in}in/{total_out}out", flush=True)
            return text, total_in, total_out

        if response.stop_reason == "tool_use":
            # `submit` ends the turn: it is the contract, not a tool to execute.
            submit_block = ac.find_submit_block(response.content) if submit_enabled else None
            if submit_block is not None:
                messages.append({"role": "assistant", "content": response.content})
                answer = ac.answer_from_submit(submit_block)
                if contract_stats is not None:
                    contract_stats.submitted += 1
                    if continues:
                        contract_stats.rescued += 1
                if verbose:
                    print(f"{p} submit({answer[:60]!r}) after {tool_call_count} "
                          f"tool calls, tokens={total_in}in/{total_out}out", flush=True)
                return ac.as_final_answer(answer), total_in, total_out

            tool_results = []
            stuck = False
            for block in response.content:
                if block.type == "tool_use":
                    tool_call_count += 1
                    sig = _tool_signature(block.name, block.input)
                    repeat_counts[sig] = repeat_counts.get(sig, 0) + 1
                    repeats = repeat_counts[sig]

                    # ---- Log each tool call ----
                    input_summary = json.dumps(block.input, ensure_ascii=False)
                    if len(input_summary) > 120:
                        input_summary = input_summary[:117] + "..."
                    if verbose:
                        print(f"{p} tool[{tool_call_count}] {block.name}({input_summary})", flush=True)

                    if repeats > MAX_IDENTICAL_TOOL_CALLS:
                        # Refuse the call but let the turn continue: the model can
                        # still change approach or answer. Only a further repeat
                        # after this warning is treated as a hard loop.
                        result = (
                            f"[error] This exact {block.name} call has already been made "
                            f"{repeats - 1} times with no progress, so it was not executed. "
                            f"Do not repeat it. Change your approach, or give your FINAL "
                            f"ANSWER now based on what you already have."
                        )
                        stuck = stuck or repeats > MAX_IDENTICAL_TOOL_CALLS + 1
                    else:
                        result = tools.execute(block.name, block.input)

                    if verbose:
                        result_preview = result[:150].replace("\n", "\\n") if result else "(empty)"
                        print(f"{p}   → {result_preview}", flush=True)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            # ---- Environment-signalled completion ----
            # AppWorld ends when the environment reports the task done, which
            # can happen without the model saying anything at all.
            if tools.should_stop():
                if verbose:
                    print(f"{p} environment reports task complete after "
                          f"{tool_call_count} tool calls", flush=True)
                return ("\n".join(text_parts) or "[task completed]",
                        total_in, total_out)

            # ---- Circuit breaker: force an answer instead of burning the budget ----
            if stuck or tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
                reason = "tool loop" if stuck else "tool call limit"
                if verbose:
                    print(f"{p} {reason} after {tool_call_count} tool calls, "
                          f"forcing final answer...", flush=True)
                text, fin, fout = _force_final_answer(client, messages, system, reason)
                total_in += fin
                total_out += fout
                return text, total_in, total_out
        else:
            messages.append({"role": "assistant", "content": response.content})
            if verbose:
                print(f"{p} stopped: {response.stop_reason} after {tool_call_count} tool calls", flush=True)
            return (
                f"[stopped: {response.stop_reason}] " + "\n".join(text_parts),
                total_in, total_out,
            )


# ---------------------------------------------------------------------------
# SkillFlow Main Pipeline
# ---------------------------------------------------------------------------

MAX_SKILL_STEPS = 5  # default max iterations in the skill planning loop


def run_skillflow(
    client: anthropic.Anthropic,
    user_request: str,
    skills_index: str,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
    verbose: bool = True,
    base_system: str = BASE_SYSTEM_SCIBENCH,
    user_content: str | list | None = None,
    toolset: Optional[Toolset] = None,
) -> dict:
    """
    Run the full SkillFlow pipeline on a single task.
    Algorithm 1 from the paper — iterative skill planning loop.

    Each iteration: plan next skill → compress → execute → compress result → update residual.
    Loop terminates when planner returns 'done'/'none', max_steps reached, or budget/timeout hit.

    Returns a result dict with response, tokens, residual state, etc.
    """
    deadline = None if task_timeout >= UNLIMITED_TIMEOUT else time.time() + task_timeout
    total_in = total_out = 0
    p = "[SkillFlow]"
    # One stats object per task: shared across this task's steps, never across
    # tasks, so the worker threads need no lock of their own.
    comp_stats = CompressionStats()
    cond_stats = cond.CondenserStats()
    condenser = _make_condenser(cond_stats, client, user_request)
    contract_stats = ac.ContractStats()

    # ---- Step 1: Goal Anchoring (Alg line 1) ----
    if verbose:
        print(f"{p} Step 1: Goal Anchoring...", end="", flush=True)
    goal, gin, gout = anchor_goal(client, user_request)
    total_in += gin
    total_out += gout
    if verbose:
        print(f" obj='{goal.objective[:60]}...'", flush=True)

    # ---- Step 2: Initialize Residual Context (Alg lines 2-4) ----
    residual = init_residual(goal)

    # ---- Iterative Skill Planning Loop (Alg lines 5-19) ----
    all_chosen_skills: list[str] = []
    all_compressed_lengths: dict[str, int] = {}
    all_original_lengths: dict[str, int] = {}
    step_responses: list[str] = []
    timed_out = False
    budget_hit = False
    skill_disabled = (k <= 0)

    msg_content = user_content if user_content is not None else user_request

    for step in range(1, max_steps + 1):
        # Check deadline — if past deadline, force one last answer attempt
        if deadline is not None and time.time() >= deadline - TIMEOUT_GRACE_SECONDS:
            if verbose:
                print(f"{p} [TIMEOUT] deadline approaching before step {step}, "
                      f"forcing final answer...", flush=True)
            timed_out = True
            # Force final answer using whatever residual we have so far
            system = build_execution_prompt(goal, residual, {}, base_system=base_system)
            messages = [{"role": "user", "content": msg_content}]
            text, fin, fout = _force_final_answer(client, messages, system, "timeout")
            total_in += fin
            total_out += fout
            step_responses.append(text)
            break

        # ---- Plan next skill (Alg line 8: S_t = PlanSkill(G, R_t, E_t)) ----
        if skill_disabled:
            # k=0: no skills, run one agent loop and stop
            skill_name = None
            if step > 1:
                break
        else:
            if verbose:
                print(f"{p} Step {step}a: Planning next skill...", end="", flush=True)
            skill_name, pin, pout = plan_next_skill(
                client, goal, residual, skills_index,
            )
            total_in += pin
            total_out += pout
            if verbose:
                print(f" → {skill_name or 'done/none'}", flush=True)

            if skill_name is None:
                # Planner says done or no skill needed
                if step == 1:
                    # First step and planner says no skill — run without skills
                    pass
                else:
                    # Done after previous steps
                    break

        # ---- Build local execution context (Alg line 9) ----
        # Each step gets a FRESH messages list — local context, not full history.
        # Prior step results are conveyed through the residual, not message history.
        # Skill docs AND the accumulated residual go in at full length; all
        # compression (skill + execution results) triggers only when the
        # assembled prompt reaches compress_ratio() of the context window.
        system, compressor, orig_len, used_len, cin, cout = assemble_execution_context(
            client, goal, residual, skill_name, msg_content,
            base_system=base_system, verbose=verbose, prefix=p, step=step,
            stats=comp_stats,
        )
        residual = compressor.residual
        messages = [{"role": "user", "content": msg_content}]
        total_in += cin
        total_out += cout
        if skill_name and skill_name in SKILL_DOCS:
            all_original_lengths[skill_name] = orig_len
            all_compressed_lengths[skill_name] = used_len

        # ---- Execute agent loop (Alg line 10) ----
        remaining_budget = token_budget if token_budget >= UNLIMITED_TOKENS else max(token_budget - total_out, FORCE_ANSWER_THRESHOLD)
        budget_label = "unlimited" if remaining_budget >= UNLIMITED_TOKENS else str(remaining_budget)
        if verbose:
            print(f"{p} Step {step}c: Agent loop (budget={budget_label})...", flush=True)

        try:
            response_text, ain, aout = run_agent_loop(
                client, messages, system,
                token_budget=remaining_budget,
                deadline=deadline,
                verbose=verbose,
                compressor=compressor,
                condenser=condenser,
                contract_stats=contract_stats,
                toolset=toolset,
            )
            total_in += ain
            total_out += aout
        except Exception as e:
            if verbose:
                print(f"{p} [ERROR] {type(e).__name__}: {e}", flush=True)
            response_text = ""

        # The loop may have compacted the residual mid-turn; keep that work.
        residual = compressor.residual

        # Track whether timeout/budget was hit (from agent loop's response prefix)
        if response_text.startswith("[timeout]"):
            timed_out = True
        if response_text.startswith("[budget exceeded]"):
            budget_hit = True

        # Record skill used in this step (after execution, not before)
        if skill_name and skill_name in SKILL_DOCS:
            all_chosen_skills.append(skill_name)

        step_responses.append(response_text)

        # ---- Record execution into residual (Alg lines 11-15) ----
        # Store the RAW result only — no LLM call here. Execution-result
        # compression is deferred to assemble_execution_context and runs only
        # when context pressure crosses the compress ratio, not every step.
        exec_skill = skill_name or "direct"
        if response_text:
            residual = add_raw_execution(residual, exec_skill, response_text)
            if verbose:
                print(f"{p} Step {step}d: recorded raw execution "
                      f"(exec_items={len(residual.exec_items)}, "
                      f"raw_evidence={len(residual.raw_evidence)})", flush=True)

        # If no skills (k=0), only run one iteration
        if skill_disabled:
            break

        # If timed out or budget hit, no more iterations
        if timed_out or budget_hit:
            if verbose:
                reason = "timeout" if timed_out else "budget"
                print(f"{p} Stopping iteration ({reason}).", flush=True)
            break

        # If budget is nearly exhausted, stop iterating
        if token_budget < UNLIMITED_TOKENS and total_out >= token_budget * 0.9:
            if verbose:
                print(f"{p} Budget nearly exhausted ({total_out}/{token_budget}), "
                      f"stopping iteration.", flush=True)
            break

    # ---- Compose final response from all steps ----
    # Usually the last step holds the answer, but a step can end on a tool
    # result, a nudge limit or an exception and carry none. Taking it blindly
    # discards an answer an earlier step already produced and scores a solved
    # task as unsolved, so prefer the most recent step that actually answered.
    final_response = next(
        (r for r in reversed(step_responses) if ac.has_explicit_answer(r)), "")
    if not final_response:
        final_response = next((r for r in reversed(step_responses) if r.strip()), "")

    COMPRESSION_AGG.add(comp_stats)
    cond.CONDENSER_AGG.add(cond_stats)
    ac.CONTRACT_AGG.add(contract_stats)

    return {
        "response": final_response,
        "goal": asdict(goal),
        "residual": {
            "goal_text": residual.goal_text,
            "hard_constraints": residual.hard_constraints,
            "exec_items": residual.exec_items,
            "risk_items": residual.risk_items,
            "raw_evidence": residual.raw_evidence,
        },
        "chosen_skills": all_chosen_skills,
        "compressed_skill_lengths": all_compressed_lengths,
        "original_skill_lengths": all_original_lengths,
        "compression": asdict(comp_stats),
        "condenser": asdict(cond_stats),
        "contract": asdict(contract_stats),
        "skill_steps": len(step_responses),
        "step_responses": [r[:500] for r in step_responses],  # for debugging
        "timed_out": timed_out,
        "budget_exceeded": budget_hit,
        "tokens": {
            "input": total_in,
            "output": total_out,
            "total": total_in + total_out,
        },
    }


# ---------------------------------------------------------------------------
# AppWorld toolset
# ---------------------------------------------------------------------------


class AppWorldToolset(Toolset):
    """
    AppWorld's action space: one `execute` tool bound to a live session.

    The filesystem tools are withheld deliberately. They cannot reach the
    environment, and offering them to a small model reliably produces a run of
    bash calls that accomplish nothing but fill the transcript.
    """

    def __init__(self, session: "aw.AppWorldSession"):
        self.session = session

    def base_tools(self) -> list:
        return [aw.EXECUTE_TOOL]

    def execute(self, name: str, inputs: dict) -> str:
        if name == "execute":
            return self.session.execute(inputs.get("code", ""))
        return _unknown_tool_error(name)

    def should_stop(self) -> bool:
        return self.session.completed()


# ---------------------------------------------------------------------------
# Plain framework (the baseline SkillFlow is measured against)
# ---------------------------------------------------------------------------

SKILL_SELECTION_SYSTEM = """\
You are a skill selection assistant. Given a task and a list of available \
skills, pick the skills most relevant to completing it. Reply with skill names \
only, one per line, or 'none'."""


def select_skills(client, question: str, skills_index: str, k: int = 1):
    """
    One-shot top-k skill selection: the whole of the plain harness's skill logic.

    Returns (chosen_names, in_tok, out_tok). k<=0 skips the call entirely, so a
    no-skills baseline costs nothing extra.
    """
    if k <= 0 or not skills_index or not SKILL_DOCS:
        return [], 0, 0

    instruction = (
        "Which ONE skill above is most relevant to completing this task? "
        "Reply with the exact skill name, or 'none'."
        if k == 1 else
        f"Which up to {k} skills above are most relevant to completing this task? "
        f"List each chosen skill name on its own line (most relevant first), "
        f"or reply with 'none' if no skill applies."
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=min(32 * k + 32, 256),
            system=SKILL_SELECTION_SYSTEM,
            messages=[{"role": "user", "content":
                       f"Task:\n{question}\n\n{skills_index}\n\n{instruction}"}],
        )
        raw = response.content[0].text.strip()
        chosen, seen = [], set()
        for line in raw.splitlines():
            line = line.strip().strip("-•* ").lower()
            for name in SKILL_DOCS:
                if name.lower() in line and name not in seen:
                    chosen.append(name)
                    seen.add(name)
                    break
            if len(chosen) == k:
                break
        return chosen, response.usage.input_tokens, response.usage.output_tokens
    except Exception as e:
        print(f"  [WARN] skill selection failed: {e}", flush=True)
        return [], 0, 0


def run_plain(
    client,
    user_request: str,
    skills_index: str,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,     # unused; kept for signature parity
    verbose: bool = True,
    base_system: str = BASE_SYSTEM_SCIBENCH,
    user_content: str | list | None = None,
    toolset: Optional[Toolset] = None,
) -> dict:
    """
    The plain harness: select top-k skills once, inject them whole, run one
    agent loop. No goal anchoring, no planning loop, no residual.

    This exists so every benchmark has a baseline built from the same agent
    loop, tool surface, termination contract and condenser as SkillFlow. A
    baseline that differs from the method in those respects measures the
    difference in plumbing, not in method — which is exactly the trap this
    whole comparison is trying to avoid.

    Returns the same dict shape as run_skillflow so all downstream reporting
    works unchanged.
    """
    deadline = None if task_timeout >= UNLIMITED_TIMEOUT else time.time() + task_timeout
    total_in = total_out = 0
    comp_stats = CompressionStats()
    cond_stats = cond.CondenserStats()
    condenser = _make_condenser(cond_stats, client, user_request)
    contract_stats = ac.ContractStats()

    chosen, sel_in, sel_out = select_skills(client, user_request, skills_index, k)
    total_in += sel_in
    total_out += sel_out
    if verbose:
        print(f"[plain] skills: {', '.join(chosen) if chosen else '(none)'}", flush=True)

    system = base_system
    original_lengths, used_lengths = {}, {}
    for name in chosen:
        doc = SKILL_DOCS[name]
        system += f"\n\n# Skill: {name}\n\n{doc}"
        original_lengths[name] = used_lengths[name] = len(doc)

    msg_content = user_content if user_content is not None else user_request
    messages = [{"role": "user", "content": msg_content}]
    comp_stats.window = get_context_window(client)
    comp_stats.threshold = compression_threshold(client)

    try:
        response_text, ain, aout = run_agent_loop(
            client, messages, system,
            token_budget=token_budget, deadline=deadline, verbose=verbose,
            condenser=condenser, contract_stats=contract_stats, toolset=toolset,
        )
        total_in += ain
        total_out += aout
    except Exception as e:
        if verbose:
            print(f"[plain] [ERROR] {type(e).__name__}: {e}", flush=True)
        response_text = ""

    COMPRESSION_AGG.add(comp_stats)
    cond.CONDENSER_AGG.add(cond_stats)
    ac.CONTRACT_AGG.add(contract_stats)

    return {
        "response": response_text,
        "goal": {},
        "residual": {"goal_text": "", "hard_constraints": [], "exec_items": [],
                     "risk_items": [], "raw_evidence": []},
        "chosen_skills": chosen,
        "compressed_skill_lengths": used_lengths,
        "original_skill_lengths": original_lengths,
        "compression": asdict(comp_stats),
        "condenser": asdict(cond_stats),
        "contract": asdict(contract_stats),
        "skill_steps": 1,
        "step_responses": [response_text[:500]],
        "timed_out": response_text.startswith("[timeout]"),
        "budget_exceeded": response_text.startswith("[budget exceeded]"),
        "tokens": {"input": total_in, "output": total_out,
                   "total": total_in + total_out},
    }


def run_framework(framework: str, **kwargs) -> dict:
    """Dispatch to the configured framework. Both return the same dict shape."""
    if framework == "plain":
        return run_plain(**kwargs)
    return run_skillflow(**kwargs)


# ---------------------------------------------------------------------------
# AppWorld evaluation
# ---------------------------------------------------------------------------


def run_appworld_task(
    idx: int, n: int, task: dict,
    client, skills_index: str,
    k: int, token_budget: int, delay: float,
    output_file: str, file_lock: threading.Lock,
    stats: dict, stats_lock: threading.Lock,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
    framework: str = "skillflow",
    experiment_name: str = "skillflow",
) -> dict:
    """Run one AppWorld task inside its own environment session."""
    p = f"[T{idx:3d}/{n}]"
    task_id = task["task_id"]
    print(f"\n{p} appworld {task_id}", flush=True)

    result: dict = {}
    evaluation: dict = {"success": False, "error": "session never opened"}
    try:
        with aw.AppWorldSession(task_id, experiment_name) as session:
            request = session.prompt()
            preview = session.instruction.replace("\n", " ")[:77]
            print(f"{p}   Q: {preview}{'...' if len(preview) == 77 else ''}", flush=True)

            result = run_framework(
                framework,
                client=client,
                user_request=request,
                skills_index=skills_index,
                k=k,
                token_budget=token_budget,
                task_timeout=task_timeout,
                max_steps=max_steps,
                verbose=True,
                base_system=aw.BASE_SYSTEM_APPWORLD,
                toolset=AppWorldToolset(session),
            )
            # Score inside the session: evaluation reads environment state, and
            # that state is gone once the context manager exits.
            evaluation = session.evaluate()
    except ImportError as e:
        print(f"{p}   [FATAL] {e}", flush=True)
        raise
    except Exception as e:
        print(f"{p}   [ERROR] {type(e).__name__}: {e}", flush=True)
        evaluation = {"success": False, "error": f"{type(e).__name__}: {e}"}

    correct = bool(evaluation.get("success"))
    tok = result.get("tokens", {"input": 0, "output": 0, "total": 0})

    task_result = {
        "benchmark": "appworld",
        "framework": framework,
        "task_id": task_id,
        "split": task.get("split", ""),
        "chosen_skills": result.get("chosen_skills", []),
        "skill_steps": result.get("skill_steps", 0),
        "correct": correct,
        "evaluation": evaluation,
        "response": result.get("response", ""),
        "timed_out": result.get("timed_out", False),
        "budget_exceeded": result.get("budget_exceeded", False),
        "tokens": tok,
        "compression": result.get("compression", {}),
        "condenser": result.get("condenser", {}),
        "contract": result.get("contract", {}),
    }

    with stats_lock:
        stats["all"]["total"] += 1
        stats["all"]["tokens_input"] += tok.get("input", 0)
        stats["all"]["tokens_output"] += tok.get("output", 0)
        if correct:
            stats["all"]["correct"] += 1

    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(task_result, ensure_ascii=False) + "\n")

    status = "✓ PASS" if correct else "✗ FAIL"
    print(f"{p}   {status}  tok={tok.get('input', 0)}in/{tok.get('output', 0)}out", flush=True)

    if delay > 0:
        time.sleep(delay)
    return task_result


def evaluate_appworld(
    split: str = "dev",
    max_questions: int | None = None,
    output_file: str | None = None,
    api_key: str | None = None,
    delay: float = 0.0,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
    framework: str = "skillflow",
):
    """
    Run AppWorld.

    Note on workers: each task opens its own environment, so parallelism is
    bounded by what the AppWorld backend tolerates rather than by the model
    server. Start at 1 and raise it only after a clean run.
    """
    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR) if k > 0 else ""
    tasks = aw.load_appworld_tasks(split=split, max_questions=max_questions)
    n = len(tasks)

    if output_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{framework}_appworld_{split}_{n}q_k{k}_{ts}.jsonl"
    experiment_name = aw.experiment_name_for(output_file, f"{framework}_appworld")

    budget_s = "unlimited" if token_budget >= UNLIMITED_TOKENS else f"{token_budget}"
    timeout_s = "unlimited" if task_timeout >= UNLIMITED_TIMEOUT else f"{task_timeout}s"

    print(f"=== AppWorld Evaluation ({framework}) ===")
    print(f"Model    : {MODEL}")
    print(f"Split    : {split}")
    print(f"Tasks    : {n}")
    print(f"Workers  : {workers}")
    print(f"Skills   : {'k=' + str(k) if k > 0 else 'disabled (k=0)'}")
    print(f"Tok budget: {budget_s} output tokens/task  |  timeout: {timeout_s}/task")
    print(f"Experiment: {experiment_name}")
    print(f"Output   : {output_file}\n")

    stats = {"all": {"correct": 0, "total": 0, "tokens_input": 0, "tokens_output": 0}}
    stats_lock = threading.Lock()
    file_lock = threading.Lock()

    task_kwargs = dict(
        client=client, skills_index=skills_index, k=k,
        token_budget=token_budget, delay=delay,
        output_file=output_file, file_lock=file_lock,
        stats=stats, stats_lock=stats_lock,
        task_timeout=task_timeout, max_steps=max_steps,
        framework=framework, experiment_name=experiment_name,
    )

    indexed = list(enumerate(tasks, start=1))
    if workers <= 1:
        for idx, task in indexed:
            run_appworld_task(idx=idx, n=n, task=task, **task_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_appworld_task, idx=idx, n=n, task=task,
                                **task_kwargs): idx
                for idx, task in indexed
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[T{futures[future]:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    s = stats["all"]
    total, correct = s["total"], s["correct"]
    acc = correct / total * 100 if total else 0.0

    print("\n" + "=" * 60)
    print("APPWORLD RESULTS SUMMARY")
    print("=" * 60)
    print(f"  {framework:10s}: {correct}/{total}  ({acc:.1f}%)  "
          f"tokens {s['tokens_input']:,}in/{s['tokens_output']:,}out")
    print("-" * 60)
    print(COMPRESSION_AGG.render())
    print(cond.CONDENSER_AGG.render())
    print(ac.CONTRACT_AGG.render())
    print("=" * 60)
    print(f"Saved to : {output_file}")
    print(f"Official aggregate: appworld evaluate {experiment_name} {split}")

    summary = {
        "_type": "summary",
        "compression": COMPRESSION_AGG.summary(),
        "condenser": cond.CONDENSER_AGG.summary(),
        "contract": ac.CONTRACT_AGG.summary(),
        "framework": framework,
        "benchmark": "appworld",
        "model": MODEL,
        "split": split,
        "k": k,
        "workers": workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "experiment_name": experiment_name,
        "scorer": "appworld-official (per-task); run `appworld evaluate` for TGC/SGC",
        "overall": {
            "correct": correct, "total": total, "accuracy": round(acc, 2),
            "tokens_input": s["tokens_input"], "tokens_output": s["tokens_output"],
        },
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# Answer extraction & scoring (from eval_scibench_with_skills.py)
# ---------------------------------------------------------------------------

def extract_final_answer(response_text: str) -> str:
    for line in reversed(response_text.strip().splitlines()):
        m = re.match(r"FINAL ANSWER:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    lines = [l.strip() for l in response_text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def parse_number(s: str) -> float | None:
    s = s.replace("$", "").replace("\\", "").strip()
    m = re.search(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", s)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


def is_correct_scibench(predicted_str: str, gold_str: str, rel_tol: float = REL_TOL) -> bool:
    """SciBench scoring: 5% relative tolerance on numeric value."""
    pred = parse_number(predicted_str)
    gold = parse_number(gold_str)
    if pred is None or gold is None:
        return False
    if gold == 0:
        return abs(pred) < 1e-9
    return abs(pred - gold) / abs(gold) <= rel_tol


# ---------------------------------------------------------------------------
# GAIA Answer Normalization & Scoring
# ---------------------------------------------------------------------------

def _normalize_number(s: str) -> str:
    s = s.replace(",", "").strip()
    try:
        return str(float(s))
    except ValueError:
        return s


def _normalize_answer_gaia(raw: str) -> str:
    s = raw.strip().lower()
    s = s.rstrip(string.punctuation)
    s = re.sub(r"^(a|an|the)\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    num = _normalize_number(s)
    if num != s:
        return num
    return s


def _try_numeric_gaia(predicted: str, gold: str, rel_tol: float = 0.02) -> bool | None:
    """
    If both answers parse as numbers, return True iff within rel_tol.
    Returns None if either answer is non-numeric.
    """
    pred_num = parse_number(predicted)
    gold_num = parse_number(gold)
    if pred_num is None or gold_num is None:
        return None
    if gold_num == 0:
        return abs(pred_num) < 1e-9
    return abs(pred_num - gold_num) / abs(gold_num) <= rel_tol


def is_correct_gaia(predicted: str, gold: str, client: anthropic.Anthropic | None = None) -> bool:
    """
    GAIA scoring.

    Default (`--judge official`) is the official leaderboard scorer: exact match
    under GAIA's own normalisation. It is the only mode whose numbers can be put
    next to a published GAIA result.

    `--judge llm` restores the previous behaviour — 2% relative tolerance on
    numbers, then an LLM equivalence judge. It is strictly more lenient than the
    official scorer and is kept only to reproduce pre-fix numbers; anything
    measured with it is comparable with nothing but itself.
    """
    if not predicted:
        return False

    if _JUDGE["mode"] == "official":
        return gaia_scorer.question_scorer(predicted, gold)

    # 1. Numeric fast-path
    numeric_result = _try_numeric_gaia(predicted, gold)
    if numeric_result is not None:
        return numeric_result

    # 2. LLM semantic judge
    if client is not None:
        prompt = (
            "You are a strict answer-equivalence judge for a benchmark evaluation.\n"
            "Decide whether the predicted answer conveys the same meaning as the gold answer.\n"
            "Rules:\n"
            "- Minor wording differences, abbreviations, or punctuation are OK.\n"
            "- Different facts, names, dates, or values are NOT equivalent.\n"
            "- Respond with exactly one word: YES or NO.\n\n"
            f"Gold answer  : {gold}\n"
            f"Predicted    : {predicted}\n\n"
            "Are they semantically equivalent? (YES/NO)"
        )
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=16,
                messages=[{"role": "user", "content": prompt}],
            )
            verdict = resp.content[0].text.strip().upper()
            return verdict.startswith("YES")
        except Exception:
            pass  # fall through to exact-match fallback

    # 3. Fallback: normalized exact match
    return _normalize_answer_gaia(predicted) == _normalize_answer_gaia(gold)


# ---------------------------------------------------------------------------
# GAIA File Handling
# ---------------------------------------------------------------------------

def _build_gaia_user_content(question: str, file_name: str) -> tuple[list | str, str]:
    """
    Build user message content for a GAIA task, handling attached files.
    Returns (content, file_handling_mode).
    content is a string (text-only) or list (multimodal with images).
    file_handling_mode: 'none' | 'image' | 'text' | 'unsupported'
    """
    if not file_name:
        return question, "none"

    file_path = GAIA_VALIDATION_DIR / file_name
    ext = os.path.splitext(file_name)[1].lower()

    if ext in GAIA_IMAGE_EXTS:
        try:
            with open(file_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
            media_type = mimetypes.guess_type(file_name)[0] or "image/png"
            content = [
                {"type": "text", "text": question},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
            ]
            return content, "image"
        except Exception:
            pass

    if ext in GAIA_TEXT_EXTS:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                file_content = f.read()
            text = f"{question}\n\n--- File: {file_name} ---\n{file_content}\n--- End of file ---"
            return text, "text"
        except Exception:
            pass

    text = (
        f"{question}\n\n"
        f"[Note: This question references '{file_name}' which cannot be read "
        f"(unsupported format).]"
    )
    return text, "unsupported"


# ---------------------------------------------------------------------------
# SciBench Evaluation Mode
# ---------------------------------------------------------------------------

def load_problems(subjects: list[str]) -> list[dict]:
    problems = []
    for subject in subjects:
        path = SCIBENCH_DATASET_DIR / f"{subject}.json"
        if not path.exists():
            print(f"[WARN] dataset file not found: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for p in data:
            p["subject"] = subject
        problems.extend(data)
    return problems


def run_scibench_task(
    idx: int, n: int, problem: dict,
    client: anthropic.Anthropic, skills_index: str,
    k: int, token_budget: int, delay: float,
    output_file: str, file_lock: threading.Lock,
    stats: dict, stats_lock: threading.Lock,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
) -> dict:
    """Run one SciBench problem through the SkillFlow pipeline."""
    p = f"[T{idx:3d}/{n}]"

    subject = problem.get("subject", "unknown")
    problemid = problem.get("problemid", "").strip()
    question = problem["problem_text"].strip()
    gold_str = str(problem.get("answer_number", "")).strip()
    unit = problem.get("unit", "").strip()

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    print(f"\n{p} [{subject}] {problemid}", flush=True)
    print(f"{p}   Q: {q_preview}", flush=True)

    unit_hint = f"\n\n(The expected answer unit is: {unit})" if unit else ""
    full_question = f"{question}{unit_hint}"

    # Run full SkillFlow pipeline
    result = run_skillflow(
        client=client,
        user_request=full_question,
        skills_index=skills_index,
        k=k,
        token_budget=token_budget,
        task_timeout=task_timeout,
        max_steps=max_steps,
        verbose=True,
        base_system=BASE_SYSTEM_SCIBENCH,
    )

    response_text = result["response"]
    predicted_str = extract_final_answer(response_text)
    correct = is_correct_scibench(predicted_str, gold_str)

    task_result = {
        "subject": subject,
        "problemid": problemid,
        "unit": unit,
        "chosen_skills": result["chosen_skills"],
        "compressed_skill_lengths": result["compressed_skill_lengths"],
        "original_skill_lengths": result["original_skill_lengths"],
        "skill_steps": result["skill_steps"],
        "step_responses": result["step_responses"],
        "question": question,
        "gold": gold_str,
        "predicted": predicted_str,
        "correct": correct,
        "response": response_text,
        "timed_out": result["timed_out"],
        "budget_exceeded": result["budget_exceeded"],
        "tokens": result["tokens"],
        "residual": result["residual"],
        "compression": result.get("compression", {}),
        "condenser": result.get("condenser", {}),
        "contract": result.get("contract", {}),
    }

    with stats_lock:
        stats[subject]["total"] += 1
        stats[subject]["tokens_input"] += result["tokens"]["input"]
        stats[subject]["tokens_output"] += result["tokens"]["output"]
        if correct:
            stats[subject]["correct"] += 1

    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(task_result, ensure_ascii=False) + "\n")

    status = "✓ PASS" if correct else ("⏱ TIMEOUT" if result["timed_out"] else "✗ FAIL")
    budget_tag = " [BUDGET!]" if result["budget_exceeded"] else ""
    tok = result["tokens"]
    steps_tag = f" steps={result['skill_steps']}"
    print(f"{p}   {status}  tok={tok['input']}in/{tok['output']}out{steps_tag}{budget_tag}", flush=True)
    print(f"{p}   gold={repr(gold_str)[:30]}  pred={repr(predicted_str)[:30]}", flush=True)

    # Compression stats
    for sn in result["chosen_skills"]:
        orig = result["original_skill_lengths"].get(sn, 0)
        comp = result["compressed_skill_lengths"].get(sn, 0)
        if orig > 0:
            print(f"{p}   skill '{sn}': {orig} → {comp} chars ({comp/orig*100:.0f}%)", flush=True)

    if delay > 0:
        time.sleep(delay)

    return task_result


def evaluate_scibench(
    subjects: list[str] = ALL_SUBJECTS,
    max_questions: int | None = None,
    output_file: str | None = None,
    api_key: str | None = None,
    delay: float = 0.5,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
):
    """Run SkillFlow on SciBench benchmark."""
    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR) if k > 0 else ""
    skill_names = sorted(SKILL_DOCS.keys()) if k > 0 else []

    problems = load_problems(subjects)
    if max_questions:
        problems = problems[:max_questions]

    n = len(problems)
    if output_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        subj_str = "-".join(sorted(subjects))
        output_file = f"skillflow_results_{subj_str}_{n}q_k{k}_{ts}.jsonl"

    print(f"=== SkillFlow Evaluation ===")
    print(f"Model    : {MODEL}")
    print(f"Subjects : {', '.join(subjects)}")
    print(f"Questions: {n}")
    print(f"Workers  : {workers}")
    if k > 0:
        print(f"Skills   : {', '.join(skill_names) if skill_names else '(none)'}  (k={k})")
    else:
        print(f"Skills   : disabled (k=0)")
    budget_s = "unlimited" if token_budget >= UNLIMITED_TOKENS else f"{token_budget}"
    timeout_s = "unlimited" if task_timeout >= UNLIMITED_TIMEOUT else f"{task_timeout}s"
    print(f"Tok budget: {budget_s} output tokens/task  |  timeout: {timeout_s}/task")
    print(f"Max steps: {max_steps} skill iterations")
    print(f"Pipeline : Goal Anchor → [Plan Skill → Compress → Execute → Update Residual] × N")
    print(f"Output   : {output_file}\n")

    stats = {
        s: {"correct": 0, "total": 0, "tokens_input": 0, "tokens_output": 0}
        for s in subjects
    }
    stats_lock = threading.Lock()
    file_lock = threading.Lock()

    task_kwargs = dict(
        client=client, skills_index=skills_index, k=k,
        token_budget=token_budget, delay=delay,
        output_file=output_file, file_lock=file_lock,
        stats=stats, stats_lock=stats_lock,
        task_timeout=task_timeout,
        max_steps=max_steps,
    )

    indexed = [(i + 1, p) for i, p in enumerate(problems)]

    if workers <= 1:
        for idx, prob in indexed:
            run_scibench_task(idx=idx, n=n, problem=prob, **task_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_scibench_task, idx=idx, n=n, problem=prob, **task_kwargs): idx
                for idx, prob in indexed
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    idx = futures[future]
                    print(f"[T{idx:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    # Summary
    print("\n" + "=" * 60)
    print("SKILLFLOW RESULTS SUMMARY")
    print("=" * 60)
    total_correct = total_total = 0
    grand_in = grand_out = 0
    per_subject = {}
    for subj in subjects:
        c = stats[subj]["correct"]
        t = stats[subj]["total"]
        ti = stats[subj]["tokens_input"]
        to_ = stats[subj]["tokens_output"]
        if t == 0:
            continue
        acc = c / t * 100
        avg_in = ti // t
        avg_out = to_ // t
        total_correct += c
        total_total += t
        grand_in += ti
        grand_out += to_
        per_subject[subj] = {
            "correct": c, "total": t, "accuracy": round(acc, 2),
            "tokens_input": ti, "tokens_output": to_,
        }
        print(f"  {subj:10s}: {c}/{t}  ({acc:.1f}%)  "
              f"tokens avg {avg_in}in/{avg_out}out  total {ti+to_:,}")

    overall = total_correct / total_total * 100 if total_total else 0
    print(f"  {'Overall':10s}: {total_correct}/{total_total}  ({overall:.1f}%)")
    print("-" * 60)
    print(COMPRESSION_AGG.render())
    print(cond.CONDENSER_AGG.render())
    print(ac.CONTRACT_AGG.render())
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
        "compression": COMPRESSION_AGG.summary(),
        "condenser": cond.CONDENSER_AGG.summary(),
        "contract": ac.CONTRACT_AGG.summary(),
        "framework": "skillflow",
        "model": MODEL,
        "k": k,
        "max_steps": max_steps,
        "workers": workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "pipeline": "goal_anchor → [plan_skill → compress → execute → update_residual] × N",
        "per_subject": per_subject,
        "overall": {
            "correct": total_correct,
            "total": total_total,
            "accuracy": round(overall, 2),
            "tokens_input": grand_in,
            "tokens_output": grand_out,
        },
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# GAIA Evaluation Mode
# ---------------------------------------------------------------------------

def load_gaia_tasks(levels: tuple = (1, 2), max_questions: int | None = None):
    """Load GAIA validation tasks, filtering by level."""
    import pandas as pd
    df = pd.read_parquet(str(GAIA_METADATA_FILE))
    df = df[df["Level"].isin([str(l) for l in levels])].reset_index(drop=True)
    if max_questions:
        df = df.head(max_questions)
    return df


def run_gaia_task(
    idx: int, n: int, row,
    client: anthropic.Anthropic, skills_index: str,
    k: int, token_budget: int, delay: float,
    output_file: str, file_lock: threading.Lock,
    stats: dict, stats_lock: threading.Lock,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
) -> dict:
    """Run one GAIA task through the SkillFlow pipeline."""
    p = f"[T{idx:3d}/{n}]"

    task_id = row["task_id"]
    question = row["Question"]
    gold = str(row["Final answer"])
    level = str(row["Level"])
    file_name = row.get("file_name", "") or ""

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    print(f"\n{p} L{level} | {task_id}", flush=True)
    print(f"{p}   Q: {q_preview}", flush=True)

    # Build user content (handles images/text files)
    user_content, file_mode = _build_gaia_user_content(question, file_name)

    # Run full SkillFlow pipeline
    result = run_skillflow(
        client=client,
        user_request=question,
        skills_index=skills_index,
        k=k,
        token_budget=token_budget,
        task_timeout=task_timeout,
        max_steps=max_steps,
        verbose=True,
        base_system=BASE_SYSTEM_GAIA,
        user_content=user_content,
    )

    response_text = result["response"]
    predicted = extract_final_answer(response_text)
    correct = is_correct_gaia(predicted, gold, client=client)

    task_result = {
        "task_id": task_id,
        "level": level,
        "file_name": file_name,
        "file_mode": file_mode,
        "chosen_skills": result["chosen_skills"],
        "compressed_skill_lengths": result["compressed_skill_lengths"],
        "original_skill_lengths": result["original_skill_lengths"],
        "skill_steps": result["skill_steps"],
        "step_responses": result["step_responses"],
        "question": question,
        "gold": gold,
        "predicted": predicted,
        "correct": correct,
        "response": response_text,
        "timed_out": result["timed_out"],
        "budget_exceeded": result["budget_exceeded"],
        "tokens": result["tokens"],
        "residual": result["residual"],
        "compression": result.get("compression", {}),
        "condenser": result.get("condenser", {}),
        "contract": result.get("contract", {}),
    }

    with stats_lock:
        stats[level]["total"] += 1
        stats[level]["tokens_input"] += result["tokens"]["input"]
        stats[level]["tokens_output"] += result["tokens"]["output"]
        if correct:
            stats[level]["correct"] += 1

    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(task_result, ensure_ascii=False) + "\n")

    status = "✓ PASS" if correct else ("⏱ TIMEOUT" if result["timed_out"] else "✗ FAIL")
    file_tag = f"[{file_mode}]" if file_mode != "none" else ""
    budget_tag = " [BUDGET!]" if result["budget_exceeded"] else ""
    tok = result["tokens"]
    steps_tag = f" steps={result['skill_steps']}"
    print(f"{p}   {status}  tok={tok['input']}in/{tok['output']}out{steps_tag}  {file_tag}{budget_tag}", flush=True)
    print(f"{p}   gold={repr(gold)[:40]}  pred={repr(predicted)[:40]}", flush=True)

    if delay > 0:
        time.sleep(delay)

    return task_result


def evaluate_gaia(
    levels: tuple = (1, 2),
    max_questions: int | None = None,
    output_file: str | None = None,
    api_key: str | None = None,
    delay: float = 0.5,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
):
    """Run SkillFlow on GAIA benchmark (Level 1 & 2)."""
    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR) if k > 0 else ""
    skill_names = sorted(SKILL_DOCS.keys()) if k > 0 else []

    df = load_gaia_tasks(levels=levels, max_questions=max_questions)
    n = len(df)

    if output_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        lvl_str = "".join(str(l) for l in sorted(levels))
        output_file = f"skillflow_gaia_L{lvl_str}_{n}q_k{k}_{ts}.jsonl"

    budget_s = "unlimited" if token_budget >= UNLIMITED_TOKENS else f"{token_budget}"
    timeout_s = "unlimited" if task_timeout >= UNLIMITED_TIMEOUT else f"{task_timeout}s"

    print(f"=== SkillFlow GAIA Evaluation ===")
    print(f"Model    : {MODEL}")
    print(f"Levels   : {sorted(levels)}")
    print(f"Questions: {n}")
    print(f"Workers  : {workers}")
    if k > 0:
        print(f"Skills   : {', '.join(skill_names) if skill_names else '(none)'}  (k={k})")
    else:
        print(f"Skills   : disabled (k=0)")
    print(f"Tok budget: {budget_s} output tokens/task  |  timeout: {timeout_s}/task")
    print(f"Max steps: {max_steps} skill iterations")
    print(f"Pipeline : Goal Anchor → [Plan Skill → Compress → Execute → Update Residual] × N")
    print(f"Output   : {output_file}\n")

    stats = {
        str(l): {"correct": 0, "total": 0, "tokens_input": 0, "tokens_output": 0}
        for l in levels
    }
    stats_lock = threading.Lock()
    file_lock = threading.Lock()

    task_kwargs = dict(
        client=client, skills_index=skills_index, k=k,
        token_budget=token_budget, delay=delay,
        output_file=output_file, file_lock=file_lock,
        stats=stats, stats_lock=stats_lock,
        task_timeout=task_timeout,
        max_steps=max_steps,
    )

    rows = [(idx, row) for idx, (_, row) in enumerate(df.iterrows(), start=1)]

    if workers <= 1:
        for idx, row in rows:
            run_gaia_task(idx=idx, n=n, row=row, **task_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_gaia_task, idx=idx, n=n, row=row, **task_kwargs): idx
                for idx, row in rows
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    idx = futures[future]
                    print(f"[T{idx:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    # Summary
    print("\n" + "=" * 60)
    print("SKILLFLOW GAIA RESULTS SUMMARY")
    print("=" * 60)
    total_correct = total_total = 0
    grand_in = grand_out = 0
    per_level = {}
    for lvl in sorted(stats):
        c = stats[lvl]["correct"]
        t = stats[lvl]["total"]
        ti = stats[lvl]["tokens_input"]
        to_ = stats[lvl]["tokens_output"]
        if t == 0:
            continue
        acc = c / t * 100
        avg_in = ti // t
        avg_out = to_ // t
        total_correct += c
        total_total += t
        grand_in += ti
        grand_out += to_
        per_level[f"level_{lvl}"] = {
            "correct": c, "total": t, "accuracy": round(acc, 2),
            "tokens_input": ti, "tokens_output": to_,
        }
        print(f"  Level {lvl}: {c}/{t}  ({acc:.1f}%)  "
              f"tokens avg {avg_in}in/{avg_out}out  total {ti+to_:,}")

    overall = total_correct / total_total * 100 if total_total else 0
    print(f"  Overall : {total_correct}/{total_total}  ({overall:.1f}%)")
    print("-" * 60)
    print(COMPRESSION_AGG.render())
    print(cond.CONDENSER_AGG.render())
    print(ac.CONTRACT_AGG.render())
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
        "compression": COMPRESSION_AGG.summary(),
        "condenser": cond.CONDENSER_AGG.summary(),
        "contract": ac.CONTRACT_AGG.summary(),
        "framework": "skillflow",
        "benchmark": "gaia",
        "model": MODEL,
        "k": k,
        "max_steps": max_steps,
        "workers": workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "pipeline": "goal_anchor → [plan_skill → compress → execute → update_residual] × N",
        "levels": sorted(str(l) for l in levels),
        "per_level": per_level,
        "overall": {
            "correct": total_correct,
            "total": total_total,
            "accuracy": round(overall, 2),
            "tokens_input": grand_in,
            "tokens_output": grand_out,
        },
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# DABstep Evaluation Mode
# ---------------------------------------------------------------------------

BASE_SYSTEM_DABSTEP = f"""\
You are a data analyst agent solving questions about a payments dataset.
You have access to tools for executing scripts and reading the filesystem.

The relevant context files live in the directory:
  {DABSTEP_CONTEXT_DIR}

Files available there:
  - manual.md                    (domain manual; READ THIS FIRST)
  - payments-readme.md           (payments table schema/notes)
  - payments.csv                 (transaction-level payments data)
  - fees.json                    (fee rules)
  - merchant_data.json           (per-merchant info)
  - merchant_category_codes.csv  (MCC reference)
  - acquirer_countries.csv       (acquirer country reference)

Read the manual and readme before answering, then write Python (pandas) to
compute the answer from the data. If a Python package is missing, install it
with pip and retry.

Follow the guidelines in the question EXACTLY for answer formatting
(e.g. country code, percentage rounding, comma-separated list, currency).
If a question has no applicable answer, respond with 'Not Applicable'.

Your response must end with a line in this exact format:
FINAL ANSWER: <your answer>

The final answer must be a short, direct value with no extra explanation."""


def load_dabstep_tasks(split: str = "all", max_questions: int | None = None) -> list[dict]:
    """Load DABstep tasks from the local download."""
    fname = "dev.jsonl" if split == "dev" else "all.jsonl"
    path = DABSTEP_TASKS_DIR / fname
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    if max_questions:
        tasks = tasks[:max_questions]
    return tasks


def is_correct_dabstep(predicted: str, gold: str) -> bool:
    """Use the official DABstep scorer (vendored from adyen/DABstep Space)."""
    from dabstep_scorer import question_scorer
    if not predicted or not gold:
        return False
    return question_scorer(predicted, gold)


def run_dabstep_task(
    idx: int, n: int, task: dict,
    client: anthropic.Anthropic, skills_index: str,
    k: int, token_budget: int, delay: float,
    output_file: str, file_lock: threading.Lock,
    stats: dict, stats_lock: threading.Lock,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
) -> dict:
    """Run one DABstep task through the SkillFlow pipeline."""
    p = f"[T{idx:3d}/{n}]"

    task_id = str(task["task_id"])
    question = task["question"]
    guidelines = task.get("guidelines", "")
    gold = str(task.get("answer", ""))
    level = task.get("level", "unknown")

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    print(f"\n{p} [{level}] {task_id}", flush=True)
    print(f"{p}   Q: {q_preview}", flush=True)

    full_question = (
        f"{question}\n\n"
        f"Answer guidelines: {guidelines}\n\n"
        f"Context files are in: {DABSTEP_CONTEXT_DIR}"
    )

    result = run_skillflow(
        client=client,
        user_request=full_question,
        skills_index=skills_index,
        k=k,
        token_budget=token_budget,
        task_timeout=task_timeout,
        max_steps=max_steps,
        verbose=True,
        base_system=BASE_SYSTEM_DABSTEP,
    )

    response_text = result["response"]
    predicted = extract_final_answer(response_text)
    has_gold = bool(gold)
    correct = is_correct_dabstep(predicted, gold) if has_gold else None

    task_result = {
        "task_id": task_id,
        "level": level,
        "chosen_skills": result["chosen_skills"],
        "compressed_skill_lengths": result["compressed_skill_lengths"],
        "original_skill_lengths": result["original_skill_lengths"],
        "skill_steps": result["skill_steps"],
        "step_responses": result["step_responses"],
        "question": question,
        "guidelines": guidelines,
        "gold": gold,
        "predicted": predicted,
        "correct": correct,
        "response": response_text,
        "timed_out": result["timed_out"],
        "budget_exceeded": result["budget_exceeded"],
        "tokens": result["tokens"],
        "residual": result["residual"],
        "compression": result.get("compression", {}),
        "condenser": result.get("condenser", {}),
        "contract": result.get("contract", {}),
    }

    with stats_lock:
        stats[level]["total"] += 1
        stats[level]["tokens_input"] += result["tokens"]["input"]
        stats[level]["tokens_output"] += result["tokens"]["output"]
        if has_gold:
            stats[level].setdefault("scored", 0)
            stats[level]["scored"] += 1
            if correct:
                stats[level]["correct"] += 1

    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(task_result, ensure_ascii=False) + "\n")

    if not has_gold:
        status = "● SUBMIT" if not result["timed_out"] else "⏱ TIMEOUT"
    else:
        status = "✓ PASS" if correct else ("⏱ TIMEOUT" if result["timed_out"] else "✗ FAIL")
    budget_tag = " [BUDGET!]" if result["budget_exceeded"] else ""
    tok = result["tokens"]
    steps_tag = f" steps={result['skill_steps']}"
    print(f"{p}   {status}  tok={tok['input']}in/{tok['output']}out{steps_tag}{budget_tag}", flush=True)
    if has_gold:
        print(f"{p}   gold={repr(gold)[:40]}  pred={repr(predicted)[:40]}", flush=True)
    else:
        print(f"{p}   pred={repr(predicted)[:60]}", flush=True)

    if delay > 0:
        time.sleep(delay)

    return task_result


def evaluate_dabstep(
    split: str = "dev",
    max_questions: int | None = None,
    output_file: str | None = None,
    api_key: str | None = None,
    delay: float = 0.5,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
):
    """Run SkillFlow on the DABstep benchmark."""
    if not DABSTEP_TASKS_DIR.exists():
        raise FileNotFoundError(
            f"DABstep tasks not found at {DABSTEP_TASKS_DIR}. "
            f"Download via: huggingface-cli download adyen/DABstep --repo-type dataset --local-dir {DABSTEP_DIR}"
        )

    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR) if k > 0 else ""
    skill_names = sorted(SKILL_DOCS.keys()) if k > 0 else []

    tasks = load_dabstep_tasks(split=split, max_questions=max_questions)
    n = len(tasks)

    if output_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"skillflow_dabstep_{split}_{n}q_k{k}_{ts}.jsonl"

    budget_s = "unlimited" if token_budget >= UNLIMITED_TOKENS else f"{token_budget}"
    timeout_s = "unlimited" if task_timeout >= UNLIMITED_TIMEOUT else f"{task_timeout}s"

    print(f"=== SkillFlow DABstep Evaluation ===")
    print(f"Model    : {MODEL}")
    print(f"Split    : {split}")
    print(f"Questions: {n}")
    print(f"Workers  : {workers}")
    if k > 0:
        print(f"Skills   : {', '.join(skill_names) if skill_names else '(none)'}  (k={k})")
    else:
        print(f"Skills   : disabled (k=0)")
    print(f"Tok budget: {budget_s} output tokens/task  |  timeout: {timeout_s}/task")
    print(f"Max steps: {max_steps} skill iterations")
    print(f"Context  : {DABSTEP_CONTEXT_DIR}")
    print(f"Output   : {output_file}\n")

    levels = sorted({t.get("level", "unknown") for t in tasks})
    stats = {lv: {"correct": 0, "total": 0, "tokens_input": 0, "tokens_output": 0} for lv in levels}
    stats_lock = threading.Lock()
    file_lock = threading.Lock()

    task_kwargs = dict(
        client=client, skills_index=skills_index, k=k,
        token_budget=token_budget, delay=delay,
        output_file=output_file, file_lock=file_lock,
        stats=stats, stats_lock=stats_lock,
        task_timeout=task_timeout, max_steps=max_steps,
    )

    indexed = list(enumerate(tasks, start=1))

    if workers <= 1:
        for idx, t in indexed:
            run_dabstep_task(idx=idx, n=n, task=t, **task_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_dabstep_task, idx=idx, n=n, task=t, **task_kwargs): idx
                for idx, t in indexed
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    idx = futures[future]
                    print(f"[T{idx:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    # Summary
    print("\n" + "=" * 60)
    print("SKILLFLOW DABSTEP RESULTS SUMMARY")
    print("=" * 60)
    has_gold_split = (split == "dev")
    total_correct = total_scored = 0
    grand_in = grand_out = 0
    per_level = {}
    for lv in levels:
        c = stats[lv]["correct"]
        t = stats[lv]["total"]
        ti = stats[lv]["tokens_input"]
        to_ = stats[lv]["tokens_output"]
        scored = stats[lv].get("scored", 0)
        if t == 0:
            continue
        grand_in += ti
        grand_out += to_
        if has_gold_split and scored:
            acc = c / scored * 100
            total_correct += c
            total_scored += scored
            per_level[lv] = {"correct": c, "total": scored, "accuracy": round(acc, 2),
                             "tokens_input": ti, "tokens_output": to_}
            print(f"  {lv:8s}: {c}/{scored}  ({acc:.1f}%)  total tokens {ti+to_:,}")
        else:
            per_level[lv] = {"completed": t, "tokens_input": ti, "tokens_output": to_}
            print(f"  {lv:8s}: {t} answered  total tokens {ti+to_:,}")

    if has_gold_split and total_scored:
        overall = total_correct / total_scored * 100
        print(f"  Overall : {total_correct}/{total_scored}  ({overall:.1f}%)  [official scorer]")
    else:
        overall = None
        print(f"  Overall : N/A — gold answers not public for split='{split}';")
        print(f"            use 'dabstep-submit' to upload to leaderboard for grading.")
    print("-" * 60)
    print(COMPRESSION_AGG.render())
    print(cond.CONDENSER_AGG.render())
    print(ac.CONTRACT_AGG.render())
    print("=" * 60)
    print(f"Saved to : {output_file}")

    # Emit leaderboard-format submission file for non-dev splits
    submission_path = None
    if split != "dev":
        submission_path = build_dabstep_submission(output_file)
        print(f"Submission jsonl: {submission_path}")
        print(f"  → upload at https://huggingface.co/spaces/adyen/DABstep")
        print(f"  → or run: python3 skillflow.py dabstep-submit --file {submission_path} ...")

    summary = {
        "_type": "summary",
        "compression": COMPRESSION_AGG.summary(),
        "condenser": cond.CONDENSER_AGG.summary(),
        "contract": ac.CONTRACT_AGG.summary(),
        "framework": "skillflow",
        "benchmark": "dabstep",
        "model": MODEL,
        "split": split,
        "k": k,
        "max_steps": max_steps,
        "workers": workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "per_level": per_level,
        "overall": (
            {"correct": total_correct, "total": total_scored,
             "accuracy": round(overall, 2),
             "tokens_input": grand_in, "tokens_output": grand_out}
            if overall is not None else
            {"scoring": "leaderboard_only",
             "tokens_input": grand_in, "tokens_output": grand_out}
        ),
        "submission_file": submission_path,
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# DABstep Leaderboard submission helpers
# ---------------------------------------------------------------------------

def build_dabstep_submission(results_jsonl: str, output_path: str | None = None) -> str:
    """
    Build a leaderboard-format jsonl from a skillflow DABstep results file.
    The leaderboard requires one row per task in `all.jsonl`; missing tasks
    are filled with 'Not Applicable'. Columns: task_id, agent_answer, reasoning_trace.
    """
    all_tasks = load_dabstep_tasks(split="all")
    answers: dict[str, str] = {}
    traces: dict[str, str] = {}
    with open(results_jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("_type") == "summary":
                continue
            tid = str(obj.get("task_id", ""))
            if not tid:
                continue
            ans = (obj.get("predicted") or "").strip() or "Not Applicable"
            answers[tid] = ans
            trace = obj.get("response", "") or ""
            traces[tid] = trace[-2000:]

    if output_path is None:
        output_path = results_jsonl.replace(".jsonl", "") + ".submission.jsonl"

    filled = 0
    with open(output_path, "w") as f:
        for t in all_tasks:
            tid = str(t["task_id"])
            row = {
                "task_id": tid,
                "agent_answer": answers.get(tid, "Not Applicable"),
                "reasoning_trace": traces.get(tid, ""),
            }
            if tid in answers:
                filled += 1
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[submission] {filled}/{len(all_tasks)} tasks filled with model answers; "
          f"rest stubbed as 'Not Applicable'")
    return output_path


def upload_dabstep_submission(
    submission_file: str,
    agent_name: str,
    model_family: str,
    organisation: str,
    mail: str,
    repo_url: str = "",
    hf_token: str | None = None,
) -> dict:
    """
    Upload a submission jsonl to the adyen/DABstep HF Space and fetch
    per-task scores from the dataset's task_scores split.
    Requires: pip install gradio_client huggingface_hub  + HF_TOKEN env var.
    """
    from gradio_client import Client, handle_file
    from huggingface_hub import hf_hub_download
    from datetime import datetime as _dt

    hf_token = hf_token or os.environ.get("HF_TOKEN")
    if not hf_token:
        raise RuntimeError("Need HF_TOKEN — login at https://huggingface.co/settings/tokens")

    print(f"[submit] Connecting to adyen/DABstep Space ...")
    client = Client("adyen/DABstep", token=hf_token)

    try:
        result = client.predict(
            "all", agent_name, model_family, repo_url,
            handle_file(submission_file), organisation, mail,
            api_name="/process_submission",
        )
    except Exception as e:
        print(f"[submit] api_name failed ({e}); listing endpoints ...")
        view = client.view_api(return_format="dict")
        print(json.dumps(view, indent=2)[:2000])
        raise

    print(f"[submit] Server response:\n{result}")

    today = _dt.utcnow().strftime("%d-%m-%Y")
    filename_id = f"v1__{organisation}-{agent_name}__{today}"
    score_file = f"data/task_scores/{filename_id}.jsonl"
    print(f"[submit] Fetching per-task scores: {score_file}")

    for attempt in range(6):
        try:
            local_path = hf_hub_download(
                repo_id="adyen/DABstep", repo_type="dataset",
                filename=score_file, force_download=True,
                local_dir=str(DABSTEP_DIR),
            )
            scores = [json.loads(l) for l in open(local_path) if l.strip()]
            correct = sum(1 for s in scores if s.get("score"))
            n = len(scores)
            print(f"[submit] ✓ Got scores: {correct}/{n} ({100*correct/n:.1f}%)")
            return {"submission_id": filename_id, "scores_path": local_path,
                    "correct": correct, "total": n,
                    "server_response": str(result)}
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"[submit] not yet available ({e}); retry in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Score file {score_file} not available yet — try fetch-scores later")


def fetch_dabstep_scores(submission_id: str) -> str:
    """Download and pretty-print per-task scores for an already-uploaded submission."""
    from huggingface_hub import hf_hub_download
    score_file = f"data/task_scores/{submission_id}.jsonl"
    local = hf_hub_download(
        repo_id="adyen/DABstep", repo_type="dataset",
        filename=score_file, force_download=True,
        local_dir=str(DABSTEP_DIR),
    )
    scores = [json.loads(l) for l in open(local) if l.strip()]
    by_lvl = {}
    for s in scores:
        lv = s.get("level", "?")
        by_lvl.setdefault(lv, []).append(s)
    print(f"=== Per-task scores: {submission_id} ===")
    total_c = total_n = 0
    for lv, items in sorted(by_lvl.items()):
        c = sum(1 for x in items if x.get("score"))
        n = len(items)
        total_c += c; total_n += n
        print(f"  {lv:8s}: {c}/{n} ({100*c/n:.1f}%)")
    if total_n:
        print(f"  Overall : {total_c}/{total_n} ({100*total_c/total_n:.1f}%)")
    print(f"Saved to: {local}")
    return local


# ---------------------------------------------------------------------------
# Interactive Mode
# ---------------------------------------------------------------------------

def interactive_mode(api_key: str | None = None, k: int = 1, max_steps: int = MAX_SKILL_STEPS):
    """Run SkillFlow in interactive chat mode with persistent residual context."""
    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR)
    print(f"[skillflow] Loaded skills: {', '.join(sorted(SKILL_DOCS.keys()))}")
    print(f"[skillflow] Model: {MODEL}")
    print("[skillflow] Interactive mode. Commands: /quit, /clear, /residual, /skills\n")

    residual: Optional[ResidualContext] = None
    goal: Optional[GoalAnchor] = None

    while True:
        try:
            user_input = input("\033[36mYou>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[skillflow] Exiting.")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break
        elif user_input == "/clear":
            residual = None
            goal = None
            print("[skillflow] Conversation and residual context cleared.")
            continue
        elif user_input == "/residual":
            if residual:
                print(residual.to_prompt_text())
            else:
                print("[skillflow] No residual context yet.")
            continue
        elif user_input == "/skills":
            print(skills_index if skills_index else "[skillflow] No skills loaded.")
            continue

        # First message: anchor goal
        if goal is None:
            goal, _, _ = anchor_goal(client, user_input)
            residual = init_residual(goal)
            print(f"[skillflow] Goal anchored: {goal.objective[:80]}")

        # Iterative skill planning loop
        for step in range(1, max_steps + 1):
            # Plan next skill
            skill_name, _, _ = plan_next_skill(client, goal, residual, skills_index)
            if skill_name is None and step > 1:
                print(f"[skillflow] Planner: done after {step - 1} steps.")
                break

            # Build system prompt with current residual. Skill docs go in at
            # full length; compression only triggers under context pressure.
            if skill_name and skill_name in SKILL_DOCS:
                print(f"[skillflow] Step {step}: executing skill '{skill_name}'")
            system, residual, _, _, _, _ = assemble_execution_context(
                client, goal, residual, skill_name, user_input,
                base_system=BASE_SYSTEM.replace(
                    "Your response must end with",
                    "When you have a final numeric answer, end with",
                ),
                verbose=True, prefix="[skillflow]", step=step,
            )

            # Fresh messages — local context only
            messages = [{"role": "user", "content": user_input}]

            try:
                reply, _, _ = run_agent_loop(client, messages, system)
                print(f"\n\033[35mAssistant>\033[0m {reply}\n")

                # Store the raw result; compression is deferred until context
                # pressure (handled inside assemble_execution_context next step).
                exec_skill = skill_name or "direct"
                residual = add_raw_execution(residual, exec_skill, reply)

            except Exception as e:
                print(f"\n[error] {e}\n")
                break

            # If no skill was used, only one iteration needed
            if skill_name is None:
                break


# ---------------------------------------------------------------------------
# AssistantBench Evaluation Mode
# ---------------------------------------------------------------------------

BASE_SYSTEM_ASSISTANTBENCH = """\
You are a research agent answering open-domain web questions from the
AssistantBench benchmark. Each question requires gathering up-to-date
information from the open web and synthesizing a precise answer.

You have shell tools (bash, read_file, write_file, list_files). Use them
to fetch web pages (e.g. `curl -sL <url>`), parse HTML/JSON, and aggregate
results. When a query needs search, hit a search engine endpoint
(e.g. https://duckduckgo.com/html/?q=...) and follow promising links.
Install any missing Python packages with pip.

Answer formatting rules — follow EXACTLY:
  - Numbers: bare number, no units, no commas (e.g. `1010000`, `14.2`).
            Use a percentage like `23%` only if the question asks for one.
  - Single string: just the value, no surrounding text.
  - List of items: one item per line, in newline-separated form.
  - Key/value answers: a JSON object on a single line.
  - If no answer exists, respond with `Not Applicable`.

Your response must end with a line in this exact format:
FINAL ANSWER: <your answer>

For multi-line list answers, place the list on lines BEFORE the FINAL
ANSWER line, then repeat the full list on the FINAL ANSWER line using
newline-escapes is NOT needed — just put the list on the line after
`FINAL ANSWER:` separated by ` | ` (pipe) so it stays one line, OR
put the answer on multiple lines after `FINAL ANSWER:` with no further
text after."""


def load_assistantbench_tasks(split: str = "dev", max_questions: int | None = None) -> list[dict]:
    """Load AssistantBench tasks from the local download."""
    fname = f"assistant_bench_v1.0_{split}.jsonl"
    path = ASSISTANTBENCH_DIR / fname
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    if max_questions:
        tasks = tasks[:max_questions]
    return tasks


def _extract_assistantbench_answer(response_text: str) -> str:
    """Mirror of eval_assistant_with_skill.extract_final_answer.

    Pulls everything after the LAST 'FINAL ANSWER:' line; supports multi-line
    list answers. Kept identical to the eval script so the only experimental
    variable between SkillFlow and eval is the agentic loop itself.
    """
    text = response_text.strip()
    matches = list(re.finditer(r"FINAL ANSWER:\s*(.*)", text, re.IGNORECASE))
    if not matches:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return lines[-1] if lines else ""
    last = matches[-1]
    rest = text[last.start(1):].strip()
    out_lines = [ln.strip() for ln in rest.splitlines() if ln.strip()]
    return "\n".join(out_lines)


def is_correct_assistantbench(predicted: str, gold: str, threshold: float = 0.5) -> bool:
    from assistantbench_scorer import is_correct_assistantbench as _ic
    return _ic(predicted, gold, threshold=threshold)


def score_assistantbench(predicted: str, gold: str) -> float:
    from assistantbench_scorer import question_scorer
    return question_scorer(predicted, gold)


def run_assistantbench_task(
    idx: int, n: int, task: dict,
    client: anthropic.Anthropic, skills_index: str,
    k: int, token_budget: int, delay: float,
    output_file: str, file_lock: threading.Lock,
    stats: dict, stats_lock: threading.Lock,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
) -> dict:
    """Run one AssistantBench task through the SkillFlow pipeline."""
    p = f"[T{idx:3d}/{n}]"

    task_id = str(task["id"])
    question = task["task"]
    gold = str(task.get("answer", ""))
    difficulty = task.get("difficulty", "unknown")

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    print(f"\n{p} [{difficulty}] {task_id[:10]}", flush=True)
    print(f"{p}   Q: {q_preview}", flush=True)

    result = run_skillflow(
        client=client,
        user_request=question,
        skills_index=skills_index,
        k=k,
        token_budget=token_budget,
        task_timeout=task_timeout,
        max_steps=max_steps,
        verbose=True,
        base_system=BASE_SYSTEM_ASSISTANTBENCH,
    )

    response_text = result["response"]
    predicted = _extract_assistantbench_answer(response_text)
    has_gold = bool(gold)
    soft = score_assistantbench(predicted, gold) if has_gold else None
    correct = (soft >= 0.5) if soft is not None else None

    task_result = {
        "task_id": task_id,
        "difficulty": difficulty,
        "chosen_skills": result["chosen_skills"],
        "compressed_skill_lengths": result["compressed_skill_lengths"],
        "original_skill_lengths": result["original_skill_lengths"],
        "skill_steps": result["skill_steps"],
        "step_responses": result["step_responses"],
        "question": question,
        "gold": gold,
        "predicted": predicted,
        "soft_score": soft,
        "correct": correct,
        "response": response_text,
        "timed_out": result["timed_out"],
        "budget_exceeded": result["budget_exceeded"],
        "tokens": result["tokens"],
        "residual": result["residual"],
        "compression": result.get("compression", {}),
        "condenser": result.get("condenser", {}),
        "contract": result.get("contract", {}),
    }

    with stats_lock:
        s = stats[difficulty]
        s["total"] += 1
        s["tokens_input"] += result["tokens"]["input"]
        s["tokens_output"] += result["tokens"]["output"]
        if has_gold:
            s.setdefault("scored", 0)
            s.setdefault("soft_sum", 0.0)
            s["scored"] += 1
            s["soft_sum"] += soft
            if correct:
                s["correct"] += 1

    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(task_result, ensure_ascii=False) + "\n")

    if not has_gold:
        status = "● SUBMIT" if not result["timed_out"] else "⏱ TIMEOUT"
    else:
        status = "✓ PASS" if correct else ("⏱ TIMEOUT" if result["timed_out"] else "✗ FAIL")
    budget_tag = " [BUDGET!]" if result["budget_exceeded"] else ""
    tok = result["tokens"]
    soft_tag = f" soft={soft:.2f}" if soft is not None else ""
    print(f"{p}   {status}  tok={tok['input']}in/{tok['output']}out steps={result['skill_steps']}{soft_tag}{budget_tag}", flush=True)
    if has_gold:
        print(f"{p}   gold={repr(gold)[:60]}", flush=True)
        print(f"{p}   pred={repr(predicted)[:60]}", flush=True)

    if delay > 0:
        time.sleep(delay)

    return task_result


def evaluate_assistantbench(
    split: str = "dev",
    max_questions: int | None = None,
    output_file: str | None = None,
    api_key: str | None = None,
    delay: float = 0.5,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
    max_steps: int = MAX_SKILL_STEPS,
):
    """Run SkillFlow on the AssistantBench benchmark."""
    if not ASSISTANTBENCH_DIR.exists():
        raise FileNotFoundError(
            f"AssistantBench tasks not found at {ASSISTANTBENCH_DIR}. "
            f"Download via: huggingface-cli download AssistantBench/AssistantBench "
            f"--repo-type dataset --local-dir {ASSISTANTBENCH_DIR}"
        )

    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR) if k > 0 else ""
    skill_names = sorted(SKILL_DOCS.keys()) if k > 0 else []

    tasks = load_assistantbench_tasks(split=split, max_questions=max_questions)
    n = len(tasks)

    if output_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"skillflow_assistantbench_{split}_{n}q_k{k}_{ts}.jsonl"

    budget_s = "unlimited" if token_budget >= UNLIMITED_TOKENS else f"{token_budget}"
    timeout_s = "unlimited" if task_timeout >= UNLIMITED_TIMEOUT else f"{task_timeout}s"

    print(f"=== SkillFlow AssistantBench Evaluation ===")
    print(f"Model    : {MODEL}")
    print(f"Split    : {split}")
    print(f"Questions: {n}")
    print(f"Workers  : {workers}")
    if k > 0:
        print(f"Skills   : {', '.join(skill_names) if skill_names else '(none)'}  (k={k})")
    else:
        print(f"Skills   : disabled (k=0)")
    print(f"Tok budget: {budget_s} output tokens/task  |  timeout: {timeout_s}/task")
    print(f"Max steps: {max_steps} skill iterations")
    print(f"Output   : {output_file}\n")

    diffs = sorted({t.get("difficulty", "unknown") for t in tasks})
    stats = {d: {"correct": 0, "total": 0, "tokens_input": 0, "tokens_output": 0,
                 "scored": 0, "soft_sum": 0.0} for d in diffs}
    stats_lock = threading.Lock()
    file_lock = threading.Lock()

    task_kwargs = dict(
        client=client, skills_index=skills_index, k=k,
        token_budget=token_budget, delay=delay,
        output_file=output_file, file_lock=file_lock,
        stats=stats, stats_lock=stats_lock,
        task_timeout=task_timeout, max_steps=max_steps,
    )

    indexed = list(enumerate(tasks, start=1))

    if workers <= 1:
        for idx, t in indexed:
            run_assistantbench_task(idx=idx, n=n, task=t, **task_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_assistantbench_task, idx=idx, n=n, task=t, **task_kwargs): idx
                for idx, t in indexed
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    idx = futures[future]
                    print(f"[T{idx:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    print("\n" + "=" * 60)
    print("SKILLFLOW ASSISTANTBENCH RESULTS SUMMARY")
    print("=" * 60)
    has_gold_split = (split == "dev")
    total_correct = total_scored = 0
    total_soft = 0.0
    grand_in = grand_out = 0
    per_diff = {}
    for d in diffs:
        s = stats[d]
        if s["total"] == 0:
            continue
        grand_in += s["tokens_input"]; grand_out += s["tokens_output"]
        if has_gold_split and s["scored"]:
            acc = s["correct"] / s["scored"] * 100
            soft_avg = s["soft_sum"] / s["scored"]
            total_correct += s["correct"]; total_scored += s["scored"]
            total_soft += s["soft_sum"]
            per_diff[d] = {"correct": s["correct"], "total": s["scored"],
                           "accuracy": round(acc, 2), "soft_avg": round(soft_avg, 4),
                           "tokens_input": s["tokens_input"], "tokens_output": s["tokens_output"]}
            print(f"  {d:8s}: {s['correct']}/{s['scored']}  ({acc:.1f}%)  "
                  f"soft={soft_avg:.3f}  tokens {s['tokens_input']+s['tokens_output']:,}")
        else:
            per_diff[d] = {"completed": s["total"],
                           "tokens_input": s["tokens_input"], "tokens_output": s["tokens_output"]}
            print(f"  {d:8s}: {s['total']} answered  tokens {s['tokens_input']+s['tokens_output']:,}")

    overall = None
    if has_gold_split and total_scored:
        overall_acc = total_correct / total_scored * 100
        overall_soft = total_soft / total_scored
        print(f"  Overall : {total_correct}/{total_scored}  ({overall_acc:.1f}%)  "
              f"soft={overall_soft:.3f}")
        overall = {"correct": total_correct, "total": total_scored,
                   "accuracy": round(overall_acc, 2), "soft_avg": round(overall_soft, 4),
                   "tokens_input": grand_in, "tokens_output": grand_out}
    else:
        print(f"  Overall : N/A — gold answers not public for split='{split}'.")
    print("-" * 60)
    print(COMPRESSION_AGG.render())
    print(cond.CONDENSER_AGG.render())
    print(ac.CONTRACT_AGG.render())
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
        "compression": COMPRESSION_AGG.summary(),
        "condenser": cond.CONDENSER_AGG.summary(),
        "contract": ac.CONTRACT_AGG.summary(),
        "framework": "skillflow",
        "benchmark": "assistantbench",
        "model": MODEL,
        "split": split,
        "k": k,
        "max_steps": max_steps,
        "workers": workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "per_difficulty": per_diff,
        "overall": overall or {"scoring": "leaderboard_only",
                               "tokens_input": grand_in, "tokens_output": grand_out},
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SkillFlow: Long-Horizon Agent Execution with Residual Context"
    )
    subparsers = parser.add_subparsers(dest="mode", help="Execution mode")

    def _add_backend_args(p):
        p.add_argument("--backend", choices=["claude", "qwen"], default="claude",
                       help="LLM backend (default: claude). 'qwen' = local "
                            "OpenAI-compatible server (vLLM/SGLang/Ollama).")
        p.add_argument("--qwen-base-url",
                       default=os.environ.get("QWEN_BASE_URL", "http://localhost:8000/v1"),
                       help="OpenAI-compatible base URL for --backend qwen "
                            "(default: vLLM on :8000; Ollama uses :11434).")
        p.add_argument("--qwen-model",
                       default=os.environ.get("QWEN_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
                       help="Model name served by the qwen backend (must match "
                            "what the server exposes).")
        p.add_argument("--context-window", type=int, default=None,
                       help="Model max context window (tokens). Overrides the "
                            "backend default; used to decide when a skill doc is "
                            "compressed (see --compress-ratio).")
        cond.add_condenser_args(p)
        ac.add_contract_args(p)
        p.add_argument("--framework", choices=["skillflow", "plain"],
                       default="skillflow",
                       help="which framework to run (default: skillflow). "
                            "'plain' is the baseline: one-shot top-k skill "
                            "selection, whole docs injected, a single agent "
                            "loop — same tools, contract and condenser as "
                            "SkillFlow, so only the framework differs.")
        p.add_argument("--judge", choices=["official", "llm"], default="official",
                       help="GAIA answer judge (default: official). 'official' is "
                            "the GAIA leaderboard scorer and the only mode "
                            "comparable with published results; 'llm' is the old "
                            "lenient tolerance+LLM judge, kept for reproduction.")
        p.add_argument("--compress-ratio", type=float,
                       default=CONTEXT_COMPRESS_RATIO,
                       help="Compress a skill doc once the assembled prompt "
                            f"reaches this fraction of the context window "
                            f"(default: {CONTEXT_COMPRESS_RATIO}, e.g. 0.9).")

    # Interactive mode
    interactive_parser = subparsers.add_parser("interactive", help="Interactive chat mode")
    interactive_parser.add_argument("--api-key", default=None)
    interactive_parser.add_argument("--top-k", type=int, default=1)

    # Single task mode
    task_parser = subparsers.add_parser("task", help="Run a single task")
    task_parser.add_argument("--task", required=True, help="Task description")
    task_parser.add_argument("--api-key", default=None)
    task_parser.add_argument("--top-k", type=int, default=1)
    task_parser.add_argument("--max-steps", type=int, default=MAX_SKILL_STEPS,
                             help="Max skill planning iterations (default: 5)")
    task_parser.add_argument("--token-budget", type=int, default=TOKEN_BUDGET_PER_TASK,
                             help="Max output tokens (0 = unlimited)")
    task_parser.add_argument("--timeout", type=int, default=TASK_TIMEOUT,
                             help="Wall-clock timeout in seconds (0 = unlimited)")
    task_parser.add_argument("--no-limit", action="store_true",
                             help="Disable both token budget and timeout limits")

    # Evaluation mode (SciBench or GAIA)
    eval_parser = subparsers.add_parser("eval", help="Benchmark evaluation")
    eval_parser.add_argument("--benchmark",
                             choices=["scibench", "gaia", "dabstep",
                                      "assistantbench", "appworld"],
                             default="scibench",
                             help="Which benchmark to evaluate (default: scibench)")
    # SciBench-specific
    eval_parser.add_argument("--subjects", nargs="+", default=ALL_SUBJECTS, choices=ALL_SUBJECTS,
                             help="SciBench subjects (ignored for gaia/dabstep)")
    # GAIA-specific
    eval_parser.add_argument("--levels", nargs="+", type=int, default=[1, 2],
                             help="GAIA levels to evaluate (default: 1 2, ignored for scibench/dabstep)")
    # DABstep-specific
    eval_parser.add_argument(
        "--appworld-split", choices=list(aw.SPLITS), default="dev",
        help="AppWorld split (default: dev). test_normal/test_challenge are "
             "for final numbers only.")
    eval_parser.add_argument("--dabstep-split", choices=["dev", "all"], default="dev",
                             help="DABstep split to evaluate (default: dev, ignored for scibench/gaia)")
    # AssistantBench-specific
    eval_parser.add_argument("--assistantbench-split", choices=["dev", "test"], default="dev",
                             help="AssistantBench split to evaluate (default: dev — local scoring; "
                                  "test has no public gold)")
    # Common
    eval_parser.add_argument("--max", type=int, default=None)
    eval_parser.add_argument("--output", default=None)
    eval_parser.add_argument("--delay", type=float, default=0.5)
    eval_parser.add_argument("--api-key", default=None)
    eval_parser.add_argument("--workers", type=int, default=1)
    eval_parser.add_argument("--task-timeout", type=int, default=TASK_TIMEOUT,
                             help="Wall-clock timeout in seconds (0 = unlimited)")
    eval_parser.add_argument("--top-k", type=int, default=1)
    eval_parser.add_argument("--max-steps", type=int, default=MAX_SKILL_STEPS,
                             help="Max skill planning iterations (default: 5)")
    eval_parser.add_argument("--token-budget", type=int, default=TOKEN_BUDGET_PER_TASK,
                             help="Max output tokens (0 = unlimited)")
    eval_parser.add_argument("--no-limit", action="store_true",
                             help="Disable both token budget and timeout limits")

    # DABstep leaderboard submission
    sub_parser = subparsers.add_parser("dabstep-submit",
        help="Build & upload a DABstep leaderboard submission, then fetch per-task scores")
    sub_parser.add_argument("--results", default=None,
        help="skillflow DABstep results jsonl (split=all). Required unless --file is given.")
    sub_parser.add_argument("--file", default=None,
        help="Pre-built submission jsonl (skip build step)")
    sub_parser.add_argument("--agent-name", required=True)
    sub_parser.add_argument("--model-family", required=True)
    sub_parser.add_argument("--organisation", required=True)
    sub_parser.add_argument("--mail", required=True)
    sub_parser.add_argument("--repo-url", default="")
    sub_parser.add_argument("--hf-token", default=None,
        help="HF token (else uses $HF_TOKEN)")
    sub_parser.add_argument("--build-only", action="store_true",
        help="Only build the submission jsonl; do not upload")

    # Fetch already-uploaded scores
    fetch_parser = subparsers.add_parser("dabstep-fetch",
        help="Fetch per-task scores for an existing DABstep submission_id")
    fetch_parser.add_argument("--submission-id", required=True,
        help="e.g. v1__MyOrg-MyAgent__27-04-2026")

    for _p in (interactive_parser, task_parser, eval_parser):
        _add_backend_args(_p)

    args = parser.parse_args()

    _BACKEND["name"] = getattr(args, "backend", "claude")
    _BACKEND["base_url"] = getattr(args, "qwen_base_url", None)
    _BACKEND["model"] = getattr(args, "qwen_model", None)
    _BACKEND["context_window"] = getattr(args, "context_window", None)
    _BACKEND["compress_ratio"] = getattr(args, "compress_ratio", None)
    _CONDENSER["name"] = getattr(args, "condenser", "none")
    _CONDENSER["keep_first"] = getattr(args, "keep_first", 1)
    _CONDENSER["attention_window"] = getattr(args, "attention_window", 2)
    _CONDENSER["max_size"] = getattr(args, "condenser_max_size", 0)
    _CONDENSER["ratio"] = getattr(args, "condense_ratio", 0.8)
    _CONDENSER["max_calls"] = getattr(args, "condenser_max_calls", 4)
    _CONTRACT["submit_tool"] = getattr(args, "submit_tool", True)
    _CONTRACT["max_continues"] = getattr(args, "max_continues", ac.MAX_CONTINUES)
    _JUDGE["mode"] = getattr(args, "judge", "official")

    # Display/logging: MODEL is the Claude id used for real Anthropic calls, but
    # the qwen backend ignores it (see llm_backend.QwenClient). Reflect the model
    # that actually runs so summaries and result records don't mislabel as Haiku.
    if _BACKEND["name"] == "qwen":
        MODEL = _BACKEND["model"] or os.environ.get("QWEN_MODEL", "Qwen/Qwen3-8B")

    def _resolve_limits(args_obj):
        """Resolve --no-limit and 0 values into sentinel constants."""
        budget = getattr(args_obj, "token_budget", TOKEN_BUDGET_PER_TASK)
        timeout = getattr(args_obj, "timeout", None) or getattr(args_obj, "task_timeout", TASK_TIMEOUT)
        no_limit = getattr(args_obj, "no_limit", False)
        if no_limit or budget == 0:
            budget = UNLIMITED_TOKENS
        if no_limit or timeout == 0:
            timeout = UNLIMITED_TIMEOUT
        return budget, timeout

    if args.mode == "interactive" or args.mode is None:
        interactive_mode(
            api_key=getattr(args, "api_key", None),
            k=getattr(args, "top_k", 1),
        )

    elif args.mode == "task":
        budget, timeout = _resolve_limits(args)
        client = _make_client(args.api_key)
        skills_index = load_skills(SKILLS_DIR)
        result = run_skillflow(
            client=client,
            user_request=args.task,
            skills_index=skills_index,
            k=args.top_k,
            max_steps=args.max_steps,
            token_budget=budget,
            task_timeout=timeout,
            verbose=True,
        )
        print(f"\n{'='*60}")
        print(f"Response:\n{result['response']}")
        print(f"\nTokens: {result['tokens']}")
        print(f"Skills: {result['chosen_skills']} ({result['skill_steps']} steps)")
        print(f"Compression: {result['compressed_skill_lengths']}")

    elif args.mode == "eval":
        budget, timeout = _resolve_limits(args)
        max_steps = getattr(args, "max_steps", MAX_SKILL_STEPS)

        if args.benchmark == "scibench":
            evaluate_scibench(
                subjects=args.subjects,
                max_questions=args.max,
                output_file=args.output,
                api_key=args.api_key,
                delay=args.delay,
                k=args.top_k,
                token_budget=budget,
                workers=args.workers,
                task_timeout=timeout,
                max_steps=max_steps,
            )
        elif args.benchmark == "gaia":
            evaluate_gaia(
                levels=tuple(args.levels),
                max_questions=args.max,
                output_file=args.output,
                api_key=args.api_key,
                delay=args.delay,
                k=args.top_k,
                token_budget=budget,
                workers=args.workers,
                task_timeout=timeout,
                max_steps=max_steps,
            )
        elif args.benchmark == "dabstep":
            evaluate_dabstep(
                split=args.dabstep_split,
                max_questions=args.max,
                output_file=args.output,
                api_key=args.api_key,
                delay=args.delay,
                k=args.top_k,
                token_budget=budget,
                workers=args.workers,
                task_timeout=timeout,
                max_steps=max_steps,
            )
        elif args.benchmark == "appworld":
            evaluate_appworld(
                split=args.appworld_split,
                max_questions=args.max,
                output_file=args.output,
                api_key=args.api_key,
                delay=args.delay,
                k=args.top_k,
                token_budget=budget,
                workers=args.workers,
                task_timeout=timeout,
                max_steps=max_steps,
                framework=args.framework,
            )
        elif args.benchmark == "assistantbench":
            evaluate_assistantbench(
                split=args.assistantbench_split,
                max_questions=args.max,
                output_file=args.output,
                api_key=args.api_key,
                delay=args.delay,
                k=args.top_k,
                token_budget=budget,
                workers=args.workers,
                task_timeout=timeout,
                max_steps=max_steps,
            )

    elif args.mode == "dabstep-submit":
        if args.file:
            sub_path = args.file
        elif args.results:
            sub_path = build_dabstep_submission(args.results)
        else:
            raise SystemExit("Provide --results <skillflow.jsonl> or --file <submission.jsonl>")
        if args.build_only:
            print(f"Built submission: {sub_path}")
        else:
            upload_dabstep_submission(
                submission_file=sub_path,
                agent_name=args.agent_name,
                model_family=args.model_family,
                organisation=args.organisation,
                mail=args.mail,
                repo_url=args.repo_url,
                hf_token=args.hf_token,
            )

    elif args.mode == "dabstep-fetch":
        fetch_dabstep_scores(args.submission_id)
