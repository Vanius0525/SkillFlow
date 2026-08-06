#!/usr/bin/env python3
"""
GAIA Benchmark Evaluation with Skills - Level 1 & 2
Uses Agent Harness + Skills progressive disclosure + Claude Haiku 4.5.

Flow per question:
  1. Skill selection call (1st API call): show task text + skills index
     (name + description only) → LLM picks up to k skills or "none".
  2. Agent loop (2nd+ API call): system prompt includes BASE_SYSTEM +
     full docs of all chosen skills; tools (bash, read_file, write_file,
     list_files) available for multi-step execution.
     When cumulative output tokens approach token_budget, the loop is
     interrupted and the model is forced to give a final answer.

Hyperparameters:
  --top-k          max skills selected per task (default 1)
  --token-budget   max output tokens per task in the agent loop (default 8000)

Skills directory: ~/agent-harness/anthropic_skills/skills/skills
File handling (same as eval_gaia.py):
  - Images (PNG/JPG):  passed as vision input
  - Text files (TXT/PY/JSON/JSONLD/CSV/MD): content inserted into prompt
  - Other files: noted in prompt but not provided
"""

import os
import re
import json
import time
import base64
import string
import argparse
import mimetypes
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
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

VALIDATION_DIR = os.path.join(os.path.dirname(__file__), "GAIA/2023/validation")
METADATA_FILE  = os.path.join(VALIDATION_DIR, "metadata.parquet")
SKILLS_DIR     = Path.home() / "agent-harness" / "anthropic_skills" / "skills" / "skills"
HARNESS_ROOT   = Path(__file__).parent
# All files created by the agent (bash / write_file) land here, not in the
# harness root. Reads/lists of relative paths are also resolved against it.
WORK_DIR       = HARNESS_ROOT / "agent_workspace"
WORK_DIR.mkdir(parents=True, exist_ok=True)
MODEL                  = "claude-haiku-4-5-20251001"
MAX_TOKENS_PER_CALL    = 4096   # max output tokens for a single API call
TOKEN_BUDGET_PER_TASK  = 8000   # total output token budget across the whole agent loop
FORCE_ANSWER_THRESHOLD = 400    # when remaining budget drops below this, force final answer
TASK_TIMEOUT           = 300    # per-task wall-clock time limit in seconds (5 min)

# Circuit breakers for the agent loop. A small model that calls a tool the
# harness does not have (e.g. a skill doc written for a different harness) will
# otherwise repeat the identical call until the whole token budget is gone.
# Counted per identical (tool, args) signature across the whole turn, so varying
# the arguments is never penalised and genuine retries have room.
MAX_IDENTICAL_TOOL_CALLS = 5    # same tool+args this many times, then stop executing it
MAX_TOOL_CALLS_PER_TURN  = 40   # absolute cap on tool calls in one agent turn

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
TEXT_EXTS  = {".txt", ".py", ".json", ".jsonld", ".csv", ".md"}

# System prompt for the actual task execution agent
BASE_SYSTEM = """\
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

# System prompt for the skill-selection pre-call
SKILL_SELECTION_SYSTEM = """\
You are a task routing assistant. Given a task and a list of available skills, \
select the most helpful skills up to the requested limit.
Reply with ONLY the exact skill names as listed (one per line), or the single \
word "none" if no skill is relevant. Do not explain your choices."""

# Injected into the conversation when the output token budget is nearly exhausted
FORCE_ANSWER_MSG = (
    "You are running low on your output token budget. "
    "Stop all tool use immediately and provide your FINAL ANSWER now in the format:\n"
    "FINAL ANSWER: <your answer>"
)

# ---------------------------------------------------------------------------
# Skills loader  (mirrors harness.py logic)
# ---------------------------------------------------------------------------

SKILL_DOCS: dict = {}   # skill_name -> full SKILL.md content


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
    """Populate SKILL_DOCS and return a compact index string for the system prompt."""
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

        name        = fm.get("name") or skill_path.name
        description = fm.get("description") or _infer_description(content)

        SKILL_DOCS[name] = content
        short_desc = description if len(description) <= 160 else description[:157] + "..."
        index_rows.append(f"- **{name}**: {short_desc}")

    if not index_rows:
        return ""

    header = (
        "# Available Skills\n\n"
        "The skills below are available. Each entry shows its name and a brief description.\n\n"
    )
    return header + "\n".join(index_rows)


# ---------------------------------------------------------------------------
# Step 1 – Skill selection  (first API call per question)
# ---------------------------------------------------------------------------

def select_skill(
    client: anthropic.Anthropic,
    question: str,
    skills_index: str,
    k: int = 1,
) -> tuple[list[str], list[str], int, int]:
    """
    Ask the LLM to pick up to k skills for this task.
    Returns (chosen_names, chosen_docs, input_tokens, output_tokens).
    chosen_names / chosen_docs are parallel lists of length 0..k.
    """
    if not skills_index or not SKILL_DOCS:
        return [], [], 0, 0

    if k == 1:
        instruction = (
            "Which ONE skill above is most relevant to completing this task? "
            "Reply with the exact skill name, or 'none'."
        )
    else:
        instruction = (
            f"Which up to {k} skills above are most relevant to completing this task? "
            f"List each chosen skill name on its own line (most relevant first), "
            f"or reply with 'none' if no skill applies."
        )

    selection_prompt = (
        f"Task:\n{question}\n\n"
        f"{skills_index}\n\n"
        f"{instruction}"
    )
    sel_max_tokens = min(32 * k + 32, 256)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=sel_max_tokens,
            system=SKILL_SELECTION_SYSTEM,
            messages=[{"role": "user", "content": selection_prompt}],
        )
        in_tok  = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        raw = response.content[0].text.strip()

        # Collect up to k recognised skill names in the order they appear in the response.
        chosen_names: list[str] = []
        seen: set[str] = set()
        for line in raw.splitlines():
            line = line.strip().strip("-•* ").lower()
            for skill_name in SKILL_DOCS:
                if skill_name.lower() in line and skill_name not in seen:
                    chosen_names.append(skill_name)
                    seen.add(skill_name)
                    break
            if len(chosen_names) == k:
                break

        chosen_docs = [SKILL_DOCS[n] for n in chosen_names]
        return chosen_names, chosen_docs, in_tok, out_tok

    except Exception as e:
        print(f"  [WARN] skill selection failed: {e}")
        return [], [], 0, 0


# ---------------------------------------------------------------------------
# Tool definitions for agent loop  (mirrors harness.py)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command or shell script. Use this to run skill scripts, "
            "install packages, or perform any shell operation. "
            "Working directory is the harness root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute."
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30).",
                    "default": 30
                },
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
                "path":    {"type": "string", "description": "Absolute or relative path to the file."},
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
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: harness root).",
                    "default": ".",
                }
            },
        },
    },
]


def _unknown_tool_error(name: str) -> str:
    """
    Explicit, actionable error for a tool this harness does not register.

    Skill docs imported from other harnesses may document tools (e.g.
    `internet_search`) that do not exist here. A bland "Unknown tool: X" reads
    like ordinary output to a small model, which then retries verbatim, so name
    the constraint and the way forward instead.
    """
    available = ", ".join(t["name"] for t in TOOLS)
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
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(WORK_DIR),
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
            entries = [
                f"[{'d' if e.is_dir() else 'f'}] {e.name}"
                for e in sorted(path.iterdir())
            ]
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
# Step 2+ – Agent loop  (mirrors harness.py run_agent_turn)
# ---------------------------------------------------------------------------

def run_agent_turn(
    client: anthropic.Anthropic,
    messages: list,
    system: str,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    deadline: float | None = None,
) -> tuple[str, int, int]:
    """
    Run one full agent turn (may involve multiple tool calls).
    Returns (final_text, total_input_tokens, total_output_tokens).
    Token counts are accumulated across every API call in the loop.

    When cumulative output tokens approach token_budget (within
    FORCE_ANSWER_THRESHOLD), the loop is interrupted: a forced-answer
    message is injected and one final text-only call is made.

    If deadline (time.time() value) is set and exceeded at the start of
    any iteration, raises TimeoutError immediately.
    """
    total_in = total_out = 0
    tool_call_count = 0
    repeat_counts: dict[str, int] = {}
    force_reason = ""

    while True:
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError(f"task exceeded {TASK_TIMEOUT}s wall-clock limit")

        remaining = token_budget - total_out

        # --- budget nearly exhausted (or loop broken out of): force final answer ---
        if force_reason or remaining <= FORCE_ANSWER_THRESHOLD:
            reason = force_reason or "budget exceeded"
            messages.append({"role": "user", "content": FORCE_ANSWER_MSG})
            response = client.messages.create(
                model=MODEL,
                max_tokens=max(FORCE_ANSWER_THRESHOLD, 64),
                system=system,
                messages=messages,          # no tools= → text-only reply
            )
            total_in  += response.usage.input_tokens
            total_out += response.usage.output_tokens
            text = "\n".join(
                b.text for b in response.content if hasattr(b, "text") and b.text
            )
            messages.append({"role": "assistant", "content": response.content})
            return f"[{reason}] " + text, total_in, total_out

        # --- normal call ---
        call_max = min(MAX_TOKENS_PER_CALL, remaining)
        response = client.messages.create(
            model=MODEL,
            max_tokens=call_max,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        total_in  += response.usage.input_tokens
        total_out += response.usage.output_tokens

        text_parts = [b.text for b in response.content if hasattr(b, "text") and b.text]

        if response.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": response.content})
            return "\n".join(text_parts), total_in, total_out

        if response.stop_reason == "tool_use":
            tool_results = []
            stuck = False
            for block in response.content:
                if block.type == "tool_use":
                    tool_call_count += 1
                    sig = _tool_signature(block.name, block.input)
                    repeat_counts[sig] = repeat_counts.get(sig, 0) + 1
                    repeats = repeat_counts[sig]

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
                        result = execute_tool(block.name, block.input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            # Force an answer next iteration instead of burning the whole budget.
            if stuck:
                force_reason = "tool loop"
            elif tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
                force_reason = "tool call limit"

        else:
            messages.append({"role": "assistant", "content": response.content})
            return f"[stopped: {response.stop_reason}] " + "\n".join(text_parts), total_in, total_out


# ---------------------------------------------------------------------------
# Answer normalization  (from eval_gaia.py)
# ---------------------------------------------------------------------------

def normalize_number(s: str) -> str:
    s = s.replace(",", "").strip()
    try:
        return str(float(s))
    except ValueError:
        return s


def normalize_answer(raw: str) -> str:
    s = raw.strip().lower()
    s = s.rstrip(string.punctuation)
    s = re.sub(r"^(a|an|the)\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    num = normalize_number(s)
    if num != s:
        return num
    return s


def extract_final_answer(response_text: str) -> str:
    for line in reversed(response_text.strip().splitlines()):
        m = re.match(r"FINAL ANSWER:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    lines = [l.strip() for l in response_text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def is_correct(predicted: str, gold: str) -> bool:
    return normalize_answer(predicted) == normalize_answer(gold)


# ---------------------------------------------------------------------------
# File handling  (from eval_gaia.py)
# ---------------------------------------------------------------------------

def build_user_content(question: str, file_name: str) -> tuple[list | str, str]:
    """
    Returns (content, file_handling_mode).
    content is a string (text-only) or list (multimodal).
    file_handling_mode: 'none' | 'image' | 'text' | 'unsupported'
    """
    if not file_name:
        return question, "none"

    file_path = os.path.join(VALIDATION_DIR, file_name)
    ext = os.path.splitext(file_name)[1].lower()

    if ext in IMAGE_EXTS:
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

    if ext in TEXT_EXTS:
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
# Evaluation
# ---------------------------------------------------------------------------

def make_output_filename(levels: list[int], n_questions: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lvl_str = "".join(str(l) for l in sorted(levels))
    return f"gaia_skills_results_L{lvl_str}_{n_questions}q_{ts}.jsonl"


# ---------------------------------------------------------------------------
# Per-task worker  (called from both sequential and parallel paths)
# ---------------------------------------------------------------------------

def run_task(
    idx: int,
    n: int,
    row,
    client: anthropic.Anthropic,
    skills_index: str,
    k: int,
    token_budget: int,
    delay: float,
    output_file: str,
    file_lock: threading.Lock,
    stats: dict,
    stats_lock: threading.Lock,
    task_timeout: int = TASK_TIMEOUT,
) -> dict:
    """Execute one GAIA task end-to-end and record the result."""
    p = f"[T{idx:3d}/{n}]"   # per-line prefix keeps parallel output readable

    task_id   = row["task_id"]
    question  = row["Question"]
    gold      = str(row["Final answer"])
    level     = str(row["Level"])
    file_name = row.get("file_name", "") or ""

    deadline  = time.time() + task_timeout

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    print(f"\n{p} L{level} | {task_id}", flush=True)
    print(f"{p}   Q: {q_preview}", flush=True)
    print(f"{p}   → selecting skill (k={k}) ...", end="", flush=True)

    # ------------------------------------------------------------------
    # Step 1: skill selection  (first API call)
    # ------------------------------------------------------------------
    chosen_skills, chosen_docs, sel_in, sel_out = select_skill(
        client, question, skills_index, k=k
    )
    skill_label = ", ".join(chosen_skills) if chosen_skills else "none"
    print(f" [{skill_label}]", flush=True)
    if delay > 0:
        time.sleep(delay)

    # ------------------------------------------------------------------
    # Step 2: compose system prompt with (optional) full skill context
    # ------------------------------------------------------------------
    system = BASE_SYSTEM
    for skill_name, skill_doc in zip(chosen_skills, chosen_docs):
        system += f"\n\n# Skill: {skill_name}\n\n{skill_doc}"

    # ------------------------------------------------------------------
    # Step 3: build user message (file handling)
    # ------------------------------------------------------------------
    user_content, file_mode = build_user_content(question, file_name)

    # ------------------------------------------------------------------
    # Step 4: run agent loop  (second+ API call)
    # ------------------------------------------------------------------
    print(f"{p}   → running agent (budget={token_budget}, timeout={task_timeout}s) ...",
          end="", flush=True)
    messages = [{"role": "user", "content": user_content}]
    timed_out = False
    try:
        response_text, agent_in, agent_out = run_agent_turn(
            client, messages, system,
            token_budget=token_budget,
            deadline=deadline,
        )
        predicted = extract_final_answer(response_text)
        correct   = is_correct(predicted, gold)
    except TimeoutError as e:
        print(f"\n{p}   [TIMEOUT] {e}", flush=True)
        response_text = ""
        predicted     = ""
        correct       = False
        agent_in = agent_out = 0
        timed_out = True
    except Exception as e:
        print(f"\n{p}   [ERROR] {e}", flush=True)
        response_text = ""
        predicted     = ""
        correct       = False
        agent_in = agent_out = 0

    task_in  = sel_in  + agent_in
    task_out = sel_out + agent_out

    budget_hit = response_text.startswith("[budget exceeded]")
    result = {
        "task_id":        task_id,
        "level":          level,
        "file_name":      file_name,
        "file_mode":      file_mode,
        "chosen_skills":  chosen_skills,
        "question":       question,
        "gold":           gold,
        "predicted":      predicted,
        "correct":        correct,
        "response":       response_text,
        "timed_out":      timed_out,
        "budget_exceeded": budget_hit,
        "tokens": {
            "input":         task_in,
            "output":        task_out,
            "total":         task_in + task_out,
            "selection_in":  sel_in,
            "selection_out": sel_out,
            "agent_in":      agent_in,
            "agent_out":     agent_out,
        },
    }

    # --- thread-safe stats update ---
    with stats_lock:
        stats[level]["total"]        += 1
        stats[level]["tokens_input"]  += task_in
        stats[level]["tokens_output"] += task_out
        if correct:
            stats[level]["correct"] += 1

    # --- thread-safe file write ---
    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    # --- result line ---
    status     = "✓ PASS" if correct else ("⏱ TIMEOUT" if timed_out else "✗ FAIL")
    file_tag   = f"[{file_mode}]" if file_mode != "none" else ""
    budget_tag = " [BUDGET!]" if budget_hit else ""
    print(f"{p}   {status}  tok={task_in}in/{task_out}out  {file_tag}{budget_tag}", flush=True)
    print(f"{p}   gold={repr(gold)[:40]}  pred={repr(predicted)[:40]}", flush=True)

    if delay > 0:
        time.sleep(delay)

    return result


# ---------------------------------------------------------------------------
# Evaluation orchestrator
# ---------------------------------------------------------------------------

def evaluate(
    levels=(1, 2),
    max_questions=None,
    output_file=None,
    api_key=None,
    delay=0.5,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
):
    client = _make_client(api_key)

    # Load skills index once (read-only after this point — safe to share across threads)
    skills_index = load_skills(SKILLS_DIR)
    skill_names  = sorted(SKILL_DOCS.keys())

    df = pd.read_parquet(METADATA_FILE)
    df = df[df["Level"].isin([str(l) for l in levels])].reset_index(drop=True)
    if max_questions:
        df = df.head(max_questions)

    n = len(df)
    if output_file is None:
        output_file = make_output_filename(levels, n)

    print(f"Model    : {MODEL}")
    print(f"Levels   : {levels}")
    print(f"Questions: {n}")
    print(f"Workers  : {workers}")
    print(f"Skills   : {', '.join(skill_names) if skill_names else '(none loaded)'}  (k={k})")
    print(f"Tok budget: {token_budget} output tokens/task  |  timeout: {task_timeout}s/task")
    print(f"Output   : {output_file}\n")

    stats      = {str(l): {"correct": 0, "total": 0, "tokens_input": 0, "tokens_output": 0}
                  for l in levels}
    stats_lock = threading.Lock()
    file_lock  = threading.Lock()

    # Common kwargs shared by every run_task call
    task_kwargs = dict(
        client=client,
        skills_index=skills_index,
        k=k,
        token_budget=token_budget,
        delay=delay,
        output_file=output_file,
        file_lock=file_lock,
        stats=stats,
        stats_lock=stats_lock,
        task_timeout=task_timeout,
    )

    rows = [(idx, row) for idx, (_, row) in enumerate(df.iterrows(), start=1)]

    if workers <= 1:
        # Sequential path (no overhead, easier debugging)
        for idx, row in rows:
            run_task(idx=idx, n=n, row=row, **task_kwargs)
    else:
        # Parallel path
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_task, idx=idx, n=n, row=row, **task_kwargs): idx
                for idx, row in rows
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    idx = futures[future]
                    print(f"[T{idx:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    total_correct = total_total = 0
    grand_in = grand_out = 0
    per_level = {}
    for lvl in sorted(stats):
        c   = stats[lvl]["correct"]
        t   = stats[lvl]["total"]
        ti  = stats[lvl]["tokens_input"]
        to_ = stats[lvl]["tokens_output"]
        acc     = c / t * 100 if t else 0
        avg_in  = ti  // t if t else 0
        avg_out = to_ // t if t else 0
        total_correct += c
        total_total   += t
        grand_in      += ti
        grand_out     += to_
        per_level[f"level_{lvl}"] = {
            "correct": c, "total": t, "accuracy": round(acc, 2),
            "tokens_input": ti, "tokens_output": to_,
            "tokens_total": ti + to_,
            "avg_tokens_input": avg_in, "avg_tokens_output": avg_out,
        }
        print(f"  Level {lvl}: {c}/{t}  ({acc:.1f}%)  "
              f"tokens avg {avg_in}in/{avg_out}out  total {ti+to_:,}")
    overall      = total_correct / total_total * 100 if total_total else 0
    grand_avg_in  = grand_in  // total_total if total_total else 0
    grand_avg_out = grand_out // total_total if total_total else 0
    print(f"  Overall : {total_correct}/{total_total}  ({overall:.1f}%)  "
          f"tokens avg {grand_avg_in}in/{grand_avg_out}out  total {grand_in+grand_out:,}")
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type":        "summary",
        "model":        MODEL,
        "k":            k,
        "workers":      workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "skills":       skill_names,
        "levels":       sorted(str(l) for l in levels),
        "timestamp":    datetime.now().isoformat(),
        "per_level":    per_level,
        "overall": {
            "correct":           total_correct,
            "total":             total_total,
            "accuracy":          round(overall, 2),
            "tokens_input":      grand_in,
            "tokens_output":     grand_out,
            "tokens_total":      grand_in + grand_out,
            "avg_tokens_input":  grand_avg_in,
            "avg_tokens_output": grand_avg_out,
        },
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate Claude Haiku 4.5 on GAIA with Skills progressive disclosure"
    )
    parser.add_argument(
        "--levels", nargs="+", type=int, default=[1, 2],
        help="Levels to evaluate (default: 1 2)",
    )
    parser.add_argument(
        "--max", type=int, default=None,
        help="Max number of questions (useful for quick smoke tests)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output JSONL file (default: auto-named with timestamp and count)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay in seconds between API calls (default: 0.5)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Anthropic API key (default: ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Number of parallel task workers (default: 1 = sequential). "
             "Each worker makes independent API calls concurrently.",
    )
    parser.add_argument(
        "--task-timeout", type=int, default=TASK_TIMEOUT,
        help=f"Per-task wall-clock time limit in seconds (default: {TASK_TIMEOUT}). "
             "A task that exceeds this is recorded as timed out.",
    )
    parser.add_argument(
        "--top-k", type=int, default=1,
        help="Max number of skills the model may select per task (default: 1)",
    )
    parser.add_argument(
        "--token-budget", type=int, default=TOKEN_BUDGET_PER_TASK,
        help=f"Max output tokens per task across the entire agent loop "
             f"(default: {TOKEN_BUDGET_PER_TASK}). When the remaining budget "
             f"drops below {FORCE_ANSWER_THRESHOLD}, the model is forced to "
             f"give its final answer immediately.",
    )
    parser.add_argument("--backend", choices=["claude", "qwen"], default="claude",
                        help="LLM backend (default: claude). 'qwen' = local "
                             "OpenAI-compatible server (vLLM/SGLang/Ollama).")
    parser.add_argument("--qwen-base-url",
                        default=os.environ.get("QWEN_BASE_URL", "http://localhost:8000/v1"),
                        help="OpenAI-compatible base URL for --backend qwen "
                             "(default: vLLM on :8000; Ollama uses :11434).")
    parser.add_argument("--qwen-model",
                        default=os.environ.get("QWEN_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
                        help="Model name served by the qwen backend.")
    args = parser.parse_args()

    _BACKEND["name"] = getattr(args, "backend", "claude")
    _BACKEND["base_url"] = getattr(args, "qwen_base_url", None)
    _BACKEND["model"] = getattr(args, "qwen_model", None)

    # Display/logging: MODEL is the Claude id used for real Anthropic calls, but
    # the qwen backend ignores it (see llm_backend.QwenClient). Reflect the model
    # that actually runs so summaries and result records don't mislabel as Haiku.
    if _BACKEND["name"] == "qwen":
        MODEL = _BACKEND["model"] or os.environ.get("QWEN_MODEL", "Qwen/Qwen3-8B")

    if args.top_k < 1:
        parser.error("--top-k must be >= 1")

    evaluate(
        levels=args.levels,
        max_questions=args.max,
        output_file=args.output,
        api_key=args.api_key,
        delay=args.delay,
        k=args.top_k,
        token_budget=args.token_budget,
        workers=args.workers,
        task_timeout=args.task_timeout,
    )
