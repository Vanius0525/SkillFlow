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

# Backend selection (set from CLI in __main__; default = Claude API).
_BACKEND = {"name": "claude", "base_url": None, "model": None}


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

# "Unlimited" sentinel values — used when --no-limit or 0 is passed
UNLIMITED_TOKENS = 10_000_000   # 10M output tokens (effectively infinite)
UNLIMITED_TIMEOUT = 86400       # 24 hours

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
    """One compressed skill execution record m_i."""
    skill_name: str = ""
    subgoal: str = ""
    key_outcome: str = ""
    evidence: str = ""           # raw snippet / file ref for bypass
    status: str = "pending"      # success | failed | pending
    unresolved: str = ""         # next-step dependencies


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
            return output.strip() or "(no output)"

        elif name == "read_file":
            path = Path(inputs["path"])
            if not path.is_absolute():
                path = WORK_DIR / path
            return path.read_text(encoding="utf-8")

        elif name == "write_file":
            path = Path(inputs["path"])
            if not path.is_absolute():
                path = WORK_DIR / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(inputs["content"], encoding="utf-8")
            return f"Written {len(inputs['content'])} bytes to {path}"

        elif name == "list_files":
            path = Path(inputs.get("path", "."))
            if not path.is_absolute():
                path = WORK_DIR / path
            entries = [f"[{'d' if e.is_dir() else 'f'}] {e.name}" for e in sorted(path.iterdir())]
            return "\n".join(entries) if entries else "(empty directory)"

        else:
            return f"Unknown tool: {name}"

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

    # Compressed skill docs (task-aware compressed, not full text)
    for skill_name, compressed_doc in compressed_skills.items():
        parts.append(f"\n# Skill: {skill_name} (compressed for task)\n\n{compressed_doc}")

    return "\n".join(parts)


def _force_final_answer(
    client: anthropic.Anthropic,
    messages: list,
    system: str,
    reason: str,
) -> tuple[str, int, int]:
    """Force the LLM to give a final answer based on what it has so far."""
    messages.append({"role": "user", "content": FORCE_ANSWER_MSG})
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max(FORCE_ANSWER_THRESHOLD, 256),
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
) -> tuple[str, int, int]:
    """
    Run the agentic tool-use loop.
    On timeout or budget exhaustion, forces LLM to give a final answer
    instead of raising an exception.
    Returns (final_text, total_input_tokens, total_output_tokens).
    """
    total_in = total_out = 0
    budget_enabled = token_budget < UNLIMITED_TOKENS
    tool_call_count = 0
    p = "    [agent]"

    while True:
        # ---- Timeout check: force answer instead of raising ----
        if deadline is not None and time.time() >= deadline - TIMEOUT_GRACE_SECONDS:
            if verbose:
                print(f"{p} approaching deadline, forcing final answer...", flush=True)
            text, fin, fout = _force_final_answer(
                client, messages, system, "timeout"
            )
            total_in += fin
            total_out += fout
            return text, total_in, total_out

        remaining = token_budget - total_out

        # ---- Budget check: force answer instead of truncating ----
        if budget_enabled and remaining <= FORCE_ANSWER_THRESHOLD:
            if verbose:
                print(f"{p} budget nearly exhausted ({remaining} remaining), forcing final answer...", flush=True)
            text, fin, fout = _force_final_answer(
                client, messages, system, "budget exceeded"
            )
            total_in += fin
            total_out += fout
            return text, total_in, total_out

        # ---- Normal call with tools ----
        call_max = MAX_TOKENS_PER_CALL if not budget_enabled else min(MAX_TOKENS_PER_CALL, remaining)
        response = client.messages.create(
            model=MODEL,
            max_tokens=call_max,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        total_in += response.usage.input_tokens
        total_out += response.usage.output_tokens

        text_parts = [b.text for b in response.content if hasattr(b, "text") and b.text]

        if response.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": response.content})
            if verbose:
                print(f"{p} end_turn after {tool_call_count} tool calls, "
                      f"tokens={total_in}in/{total_out}out", flush=True)
            return "\n".join(text_parts), total_in, total_out

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_call_count += 1
                    # ---- Log each tool call ----
                    input_summary = json.dumps(block.input, ensure_ascii=False)
                    if len(input_summary) > 120:
                        input_summary = input_summary[:117] + "..."
                    if verbose:
                        print(f"{p} tool[{tool_call_count}] {block.name}({input_summary})", flush=True)

                    result = execute_tool(block.name, block.input)

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

        # ---- Compress skill (Alg implicit: task-aware compression) ----
        compressed_skills: dict[str, str] = {}
        if skill_name and skill_name in SKILL_DOCS:
            orig_len = len(SKILL_DOCS[skill_name])
            all_original_lengths[skill_name] = orig_len
            if verbose:
                print(f"{p} Step {step}b: Compressing '{skill_name}' ({orig_len} chars)...", end="", flush=True)
            compressed, cin, cout = compress_skill(
                client, skill_name, SKILL_DOCS[skill_name], goal
            )
            compressed_skills[skill_name] = compressed
            all_compressed_lengths[skill_name] = len(compressed)
            total_in += cin
            total_out += cout
            if verbose:
                ratio = len(compressed) / max(orig_len, 1) * 100
                print(f" → {len(compressed)} chars ({ratio:.0f}%)", flush=True)

        # ---- Build local execution context (Alg line 9) ----
        # Each step gets a FRESH messages list — local context, not full history.
        # Prior step results are conveyed through the residual, not message history.
        system = build_execution_prompt(goal, residual, compressed_skills, base_system=base_system)
        messages = [{"role": "user", "content": msg_content}]

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
            )
            total_in += ain
            total_out += aout
        except Exception as e:
            if verbose:
                print(f"{p} [ERROR] {type(e).__name__}: {e}", flush=True)
            response_text = ""

        # Track whether timeout/budget was hit (from agent loop's response prefix)
        if response_text.startswith("[timeout]"):
            timed_out = True
        if response_text.startswith("[budget exceeded]"):
            budget_hit = True

        # Record skill used in this step (after execution, not before)
        if skill_name and skill_name in SKILL_DOCS:
            all_chosen_skills.append(skill_name)

        step_responses.append(response_text)

        # ---- Compress execution & update residual (Alg lines 11-15) ----
        exec_skill = skill_name or "direct"
        if response_text:
            if verbose:
                print(f"{p} Step {step}d: Compressing execution & updating residual...", flush=True)
            try:
                exec_item, ein, eout = compress_execution(
                    client, exec_skill, response_text, goal
                )
                total_in += ein
                total_out += eout
                residual = update_residual(residual, exec_item, response_text)
                if verbose:
                    print(f"{p}   residual: exec_items={len(residual.exec_items)}, "
                          f"risk_items={len(residual.risk_items)}, "
                          f"raw_evidence={len(residual.raw_evidence)}", flush=True)
            except Exception as e:
                if verbose:
                    print(f"{p}   [WARN] exec compression failed: {e}", flush=True)

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
    # The last step's response is the primary answer; earlier steps contribute context
    final_response = step_responses[-1] if step_responses else ""

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
    GAIA scoring:
    - If both answers are numeric: correct iff within 2% relative tolerance.
    - Otherwise: use LLM to judge semantic equivalence.
    Falls back to normalized exact-match if LLM call fails.
    """
    if not predicted:
        return False

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
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
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
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
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

            # Compress skill
            compressed_skills = {}
            if skill_name and skill_name in SKILL_DOCS:
                compressed, _, _ = compress_skill(client, skill_name, SKILL_DOCS[skill_name], goal)
                compressed_skills[skill_name] = compressed
                print(f"[skillflow] Step {step}: executing skill '{skill_name}'")

            # Build system prompt with current residual
            system = build_execution_prompt(goal, residual, compressed_skills,
                                            base_system=BASE_SYSTEM.replace(
                                                "Your response must end with", "When you have a final numeric answer, end with"
                                            ))

            # Fresh messages — local context only
            messages = [{"role": "user", "content": user_input}]

            try:
                reply, _, _ = run_agent_loop(client, messages, system)
                print(f"\n\033[35mAssistant>\033[0m {reply}\n")

                # Compress and update residual
                exec_skill = skill_name or "direct"
                exec_item, _, _ = compress_execution(client, exec_skill, reply, goal)
                residual = update_residual(residual, exec_item, reply)

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
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
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
    eval_parser.add_argument("--benchmark", choices=["scibench", "gaia", "dabstep", "assistantbench"], default="scibench",
                             help="Which benchmark to evaluate (default: scibench)")
    # SciBench-specific
    eval_parser.add_argument("--subjects", nargs="+", default=ALL_SUBJECTS, choices=ALL_SUBJECTS,
                             help="SciBench subjects (ignored for gaia/dabstep)")
    # GAIA-specific
    eval_parser.add_argument("--levels", nargs="+", type=int, default=[1, 2],
                             help="GAIA levels to evaluate (default: 1 2, ignored for scibench/dabstep)")
    # DABstep-specific
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
