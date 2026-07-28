#!/usr/bin/env python3
"""
AssistantBench Evaluation with Skills (mirrors eval_gaia_with_skills.py).

Per-question flow:
  1. Skill selection call (1st API call): show task text + skills index
     (name + description only) → LLM picks up to k skills, or "none".
     If --top-k 0, this step is skipped entirely.
  2. Agent loop (2nd+ API call): system prompt = BASE_SYSTEM + full docs
     of all chosen skills; tools (bash, read_file, write_file, list_files).
     When cumulative output tokens approach token_budget (within
     FORCE_ANSWER_THRESHOLD), the loop is interrupted and the model is
     forced to produce a final answer.

Hyperparameters of interest:
  --top-k 0   : no skill selection, agent runs with bare BASE_SYSTEM
  --top-k 1/4/8 : run skill-selection first, inject up to k full SKILL.md docs

Skills directory: ~/agent-harness/scibench_skills
Dataset:          ~/agent-harness/AssistantBench/assistant_bench_v1.0_dev.jsonl
Scoring:          assistantbench_scorer.question_scorer  (soft F1 in [0,1])
                  hard "correct" = soft >= 0.5
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

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

HARNESS_ROOT          = Path(__file__).parent
# All files created by the agent (bash / write_file) land here, not in the
# harness root. Reads/lists of relative paths are also resolved against it.
WORK_DIR              = HARNESS_ROOT / "agent_workspace"
WORK_DIR.mkdir(parents=True, exist_ok=True)
SKILLS_DIR            = HARNESS_ROOT / "scibench_skills"
ASSISTANTBENCH_DIR    = HARNESS_ROOT / "AssistantBench"

MODEL                  = "claude-haiku-4-5-20251001"
MAX_TOKENS_PER_CALL    = 4096
TOKEN_BUDGET_PER_TASK  = 8000
FORCE_ANSWER_THRESHOLD = 400
TASK_TIMEOUT           = 600    # AssistantBench questions need real web work

CORRECT_THRESHOLD = 0.5         # soft score >= this → counted as "correct"

BASE_SYSTEM = """\
You are a research agent answering open-domain web questions from the
AssistantBench benchmark. Each question requires gathering up-to-date
information from the open web and synthesizing a precise answer.

You have shell tools (bash, read_file, write_file, list_files). Use them
to fetch web pages, parse HTML/JSON, and aggregate results. Install any
missing Python packages with pip if needed.

Answer formatting rules — follow EXACTLY:
  - Numbers: bare number, no units, no commas (e.g. `1010000`, `14.2`).
            Use `23%` only if the question asks for a percentage.
  - Single string: just the value, no surrounding text.
  - List of items: one item per line.
  - Key/value answers: a JSON object on a single line.
  - If no answer exists, respond with `Not Applicable`.

Your response must end with a line in this exact format:
FINAL ANSWER: <your answer>

For multi-line list answers, put the list on lines AFTER `FINAL ANSWER:`,
one item per line, with no further text after the list."""

SKILL_SELECTION_SYSTEM = """\
You are a task routing assistant. Given a task and a list of available skills, \
select the most helpful skills up to the requested limit.
Reply with ONLY the exact skill names as listed (one per line), or the single \
word "none" if no skill is relevant. Do not explain your choices."""

FORCE_ANSWER_MSG = (
    "You are running low on your output token budget. "
    "Stop all tool use immediately and provide your FINAL ANSWER now in the format:\n"
    "FINAL ANSWER: <your answer>"
)

# ---------------------------------------------------------------------------
# Skills loader
# ---------------------------------------------------------------------------

SKILL_DOCS: dict = {}


def _parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    out = {}
    for line in fm_text.splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            out[key] = val
    return out


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

    rows = []
    for skill_path in sorted(skills_dir.iterdir()):
        skill_md = skill_path / "SKILL.md"
        if not (skill_path.is_dir() and skill_md.exists()):
            continue
        content = skill_md.read_text(encoding="utf-8").strip()
        fm = _parse_frontmatter(content)
        name        = fm.get("name") or skill_path.name
        description = fm.get("description") or _infer_description(content)
        SKILL_DOCS[name] = content
        short = description if len(description) <= 160 else description[:157] + "..."
        rows.append(f"- **{name}**: {short}")

    if not rows:
        return ""
    header = (
        "# Available Skills\n\n"
        "The skills below are available. Each entry shows its name and a brief "
        "description.\n\n"
    )
    return header + "\n".join(rows)


# ---------------------------------------------------------------------------
# Step 1 — Skill selection
# ---------------------------------------------------------------------------

def select_skill(
    client: anthropic.Anthropic,
    question: str,
    skills_index: str,
    k: int = 1,
) -> tuple[list[str], list[str], int, int]:
    """Returns (chosen_names, chosen_docs, input_tokens, output_tokens)."""
    if k <= 0 or not skills_index or not SKILL_DOCS:
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

    prompt = f"Task:\n{question}\n\n{skills_index}\n\n{instruction}"
    sel_max = min(32 * k + 32, 256)

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=sel_max,
            system=SKILL_SELECTION_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        in_tok  = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        raw = resp.content[0].text.strip()

        chosen: list[str] = []
        seen: set[str] = set()
        for line in raw.splitlines():
            line = line.strip().strip("-•* ").lower()
            for name in SKILL_DOCS:
                if name.lower() in line and name not in seen:
                    chosen.append(name)
                    seen.add(name)
                    break
            if len(chosen) == k:
                break
        return chosen, [SKILL_DOCS[n] for n in chosen], in_tok, out_tok
    except Exception as e:
        print(f"  [WARN] skill selection failed: {e}")
        return [], [], 0, 0


# ---------------------------------------------------------------------------
# Tool definitions for the agent loop
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command or shell script. Use this to run skill scripts, "
            "fetch web pages, install packages, or perform any shell operation. "
            "Working directory is the harness root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to execute."},
                "timeout": {"type": "integer",
                            "description": "Timeout in seconds (default: 30).",
                            "default": 30},
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
                "path": {"type": "string", "description": "Absolute or relative path."},
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
                "path":    {"type": "string", "description": "Absolute or relative path."},
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
                "path": {"type": "string",
                         "description": "Directory path (default: harness root).",
                         "default": "."},
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
            env["MPLBACKEND"] = "Agg"
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
            entries = [f"[{'d' if e.is_dir() else 'f'}] {e.name}"
                       for e in sorted(path.iterdir())]
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
# Step 2+ — Agent loop
# ---------------------------------------------------------------------------

def run_agent_turn(
    client: anthropic.Anthropic,
    messages: list,
    system: str,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    deadline: float | None = None,
) -> tuple[str, int, int]:
    """Returns (final_text, total_input_tokens, total_output_tokens)."""
    total_in = total_out = 0

    while True:
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError(f"task exceeded wall-clock deadline")

        remaining = token_budget - total_out

        if remaining <= FORCE_ANSWER_THRESHOLD:
            messages.append({"role": "user", "content": FORCE_ANSWER_MSG})
            resp = client.messages.create(
                model=MODEL,
                max_tokens=max(FORCE_ANSWER_THRESHOLD, 64),
                system=system,
                messages=messages,
            )
            total_in  += resp.usage.input_tokens
            total_out += resp.usage.output_tokens
            text = "\n".join(b.text for b in resp.content if hasattr(b, "text") and b.text)
            messages.append({"role": "assistant", "content": resp.content})
            return "[budget exceeded] " + text, total_in, total_out

        call_max = min(MAX_TOKENS_PER_CALL, remaining)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=call_max,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        total_in  += resp.usage.input_tokens
        total_out += resp.usage.output_tokens
        text_parts = [b.text for b in resp.content if hasattr(b, "text") and b.text]

        if resp.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": resp.content})
            return "\n".join(text_parts), total_in, total_out

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            messages.append({"role": "assistant", "content": resp.content})
            return f"[stopped: {resp.stop_reason}] " + "\n".join(text_parts), total_in, total_out


# ---------------------------------------------------------------------------
# Answer extraction & scoring
# ---------------------------------------------------------------------------

def extract_final_answer(response_text: str) -> str:
    """Pulls everything after the LAST 'FINAL ANSWER:' line; supports multi-line lists."""
    text = response_text.strip()
    matches = list(re.finditer(r"FINAL ANSWER:\s*(.*)", text, re.IGNORECASE))
    if not matches:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return lines[-1] if lines else ""
    last = matches[-1]
    rest = text[last.start(1):].strip()
    # Allow multi-line list answers — keep all subsequent non-empty lines until EOF.
    out_lines = [ln.strip() for ln in rest.splitlines() if ln.strip()]
    return "\n".join(out_lines)


def score_pair(predicted: str, gold: str) -> float:
    from assistantbench_scorer import question_scorer
    return question_scorer(predicted, gold)


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------

def load_assistantbench(split: str = "dev", max_questions: int | None = None) -> list[dict]:
    fname = f"assistant_bench_v1.0_{split}.jsonl"
    path = ASSISTANTBENCH_DIR / fname
    if not path.exists():
        raise FileNotFoundError(
            f"AssistantBench tasks not found at {path}. "
            f"Download via: huggingface-cli download AssistantBench/AssistantBench "
            f"--repo-type dataset --local-dir {ASSISTANTBENCH_DIR}"
        )
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    if max_questions:
        tasks = tasks[:max_questions]
    return tasks


def make_output_filename(split: str, n: int, k: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"assistantbench_skills_results_{split}_{n}q_k{k}_{ts}.jsonl"


# ---------------------------------------------------------------------------
# Per-task worker
# ---------------------------------------------------------------------------

def run_task(
    idx: int,
    n: int,
    task: dict,
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
    p = f"[T{idx:3d}/{n}]"

    task_id    = str(task["id"])
    question   = task["task"]
    gold       = str(task.get("answer", ""))
    difficulty = task.get("difficulty", "unknown")

    deadline = time.time() + task_timeout

    q_preview = question if len(question) <= 80 else question[:77] + "..."
    print(f"\n{p} [{difficulty}] {task_id[:10]}", flush=True)
    print(f"{p}   Q: {q_preview}", flush=True)
    print(f"{p}   → selecting skill (k={k}) ...", end="", flush=True)

    # ---- Step 1: skill selection (skipped when k==0) ----
    chosen, chosen_docs, sel_in, sel_out = select_skill(client, question, skills_index, k=k)
    label = ", ".join(chosen) if chosen else ("(disabled)" if k == 0 else "none")
    print(f" [{label}]", flush=True)
    if delay > 0:
        time.sleep(delay)

    # ---- Step 2: compose system ----
    system = BASE_SYSTEM
    for name, doc in zip(chosen, chosen_docs):
        system += f"\n\n# Skill: {name}\n\n{doc}"

    # ---- Step 3: agent loop ----
    print(f"{p}   → running agent (budget={token_budget}, timeout={task_timeout}s) ...",
          end="", flush=True)
    messages = [{"role": "user", "content": question}]
    timed_out = False
    response_text = ""
    predicted = ""
    soft = 0.0
    correct = False
    agent_in = agent_out = 0
    try:
        response_text, agent_in, agent_out = run_agent_turn(
            client, messages, system,
            token_budget=token_budget,
            deadline=deadline,
        )
        predicted = extract_final_answer(response_text)
        soft = score_pair(predicted, gold) if gold else 0.0
        correct = soft >= CORRECT_THRESHOLD
    except TimeoutError as e:
        print(f"\n{p}   [TIMEOUT] {e}", flush=True)
        timed_out = True
    except Exception as e:
        print(f"\n{p}   [ERROR] {e}", flush=True)

    task_in  = sel_in  + agent_in
    task_out = sel_out + agent_out
    budget_hit = response_text.startswith("[budget exceeded]")

    result = {
        "task_id":        task_id,
        "difficulty":     difficulty,
        "chosen_skills":  chosen,
        "question":       question,
        "gold":           gold,
        "predicted":      predicted,
        "soft_score":     soft,
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

    with stats_lock:
        s = stats[difficulty]
        s["total"]         += 1
        s["tokens_input"]  += task_in
        s["tokens_output"] += task_out
        if gold:
            s["scored"]   += 1
            s["soft_sum"] += soft
            if correct:
                s["correct"] += 1

    with file_lock:
        with open(output_file, "a") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    status = ("✓ PASS" if correct
              else "⏱ TIMEOUT" if timed_out
              else "✗ FAIL")
    bt = " [BUDGET!]" if budget_hit else ""
    print(f"{p}   {status}  tok={task_in}in/{task_out}out  soft={soft:.2f}{bt}", flush=True)
    print(f"{p}   gold={repr(gold)[:60]}", flush=True)
    print(f"{p}   pred={repr(predicted)[:60]}", flush=True)

    if delay > 0:
        time.sleep(delay)
    return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def evaluate(
    split: str = "dev",
    max_questions: int | None = None,
    output_file: str | None = None,
    api_key: str | None = None,
    delay: float = 0.5,
    k: int = 1,
    token_budget: int = TOKEN_BUDGET_PER_TASK,
    workers: int = 1,
    task_timeout: int = TASK_TIMEOUT,
):
    client = _make_client(api_key)

    skills_index = load_skills(SKILLS_DIR) if k > 0 else ""
    skill_names = sorted(SKILL_DOCS.keys()) if k > 0 else []

    tasks = load_assistantbench(split=split, max_questions=max_questions)
    n = len(tasks)

    if output_file is None:
        output_file = make_output_filename(split, n, k)

    print(f"=== AssistantBench Eval (skills+agent loop) ===")
    print(f"Model    : {MODEL}")
    print(f"Split    : {split}")
    print(f"Questions: {n}")
    print(f"Workers  : {workers}")
    if k == 0:
        print(f"Skills   : disabled (k=0, no skill selection call)")
    else:
        print(f"Skills   : {', '.join(skill_names) if skill_names else '(none loaded)'}  (k={k})")
    print(f"Tok budget: {token_budget} output tokens/task  |  timeout: {task_timeout}s/task")
    print(f"Output   : {output_file}\n")

    diffs = sorted({t.get("difficulty", "unknown") for t in tasks})
    stats = {d: {"correct": 0, "total": 0, "scored": 0, "soft_sum": 0.0,
                 "tokens_input": 0, "tokens_output": 0} for d in diffs}
    stats_lock = threading.Lock()
    file_lock = threading.Lock()

    task_kwargs = dict(
        client=client, skills_index=skills_index, k=k,
        token_budget=token_budget, delay=delay,
        output_file=output_file, file_lock=file_lock,
        stats=stats, stats_lock=stats_lock,
        task_timeout=task_timeout,
    )

    indexed = list(enumerate(tasks, start=1))

    if workers <= 1:
        for idx, t in indexed:
            run_task(idx=idx, n=n, task=t, **task_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(run_task, idx=idx, n=n, task=t, **task_kwargs): idx
                       for idx, t in indexed}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    idx = futures[fut]
                    print(f"[T{idx:3d}/{n}] [UNHANDLED ERROR] {e}", flush=True)

    # ---- summary ----
    print("\n" + "=" * 60)
    print("ASSISTANTBENCH RESULTS SUMMARY")
    print("=" * 60)
    total_correct = total_scored = 0
    total_soft = 0.0
    grand_in = grand_out = 0
    per_diff = {}
    for d in diffs:
        s = stats[d]
        if s["total"] == 0:
            continue
        grand_in += s["tokens_input"]; grand_out += s["tokens_output"]
        if s["scored"]:
            acc = s["correct"] / s["scored"] * 100
            soft_avg = s["soft_sum"] / s["scored"]
            total_correct += s["correct"]
            total_scored  += s["scored"]
            total_soft    += s["soft_sum"]
            per_diff[d] = {"correct": s["correct"], "total": s["scored"],
                           "accuracy": round(acc, 2), "soft_avg": round(soft_avg, 4),
                           "tokens_input": s["tokens_input"],
                           "tokens_output": s["tokens_output"]}
            print(f"  {d:8s}: {s['correct']}/{s['scored']}  ({acc:.1f}%)  "
                  f"soft={soft_avg:.3f}  tokens {s['tokens_input']+s['tokens_output']:,}")
        else:
            per_diff[d] = {"completed": s["total"],
                           "tokens_input": s["tokens_input"],
                           "tokens_output": s["tokens_output"]}
            print(f"  {d:8s}: {s['total']} answered  "
                  f"tokens {s['tokens_input']+s['tokens_output']:,}")

    overall = None
    if total_scored:
        overall_acc = total_correct / total_scored * 100
        overall_soft = total_soft / total_scored
        print(f"  Overall : {total_correct}/{total_scored}  ({overall_acc:.1f}%)  "
              f"soft={overall_soft:.3f}")
        overall = {"correct": total_correct, "total": total_scored,
                   "accuracy": round(overall_acc, 2),
                   "soft_avg": round(overall_soft, 4),
                   "tokens_input": grand_in, "tokens_output": grand_out}
    else:
        print(f"  Overall : N/A — gold answers not public for split='{split}'.")
    print("=" * 60)
    print(f"Saved to : {output_file}")

    summary = {
        "_type":        "summary",
        "framework":    "agent-loop+skills",
        "benchmark":    "assistantbench",
        "model":        MODEL,
        "split":        split,
        "k":            k,
        "workers":      workers,
        "token_budget": token_budget,
        "task_timeout": task_timeout,
        "skills":       skill_names,
        "timestamp":    datetime.now().isoformat(),
        "per_difficulty": per_diff,
        "overall":      overall or {"scoring": "leaderboard_only",
                                    "tokens_input": grand_in,
                                    "tokens_output": grand_out},
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return stats


# ---------------------------------------------------------------------------
# CLI — sweep mode
# ---------------------------------------------------------------------------

def parse_topks(raw: str) -> list[int]:
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        v = int(tok)
        if v < 0:
            raise argparse.ArgumentTypeError(f"top-k must be >= 0 (got {v})")
        out.append(v)
    if not out:
        raise argparse.ArgumentTypeError("--top-k cannot be empty")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate AssistantBench dev with the GAIA-style agent loop, "
                    "across one or more --top-k values."
    )
    parser.add_argument("--split", default="dev", choices=["dev", "test"],
                        help="AssistantBench split (default: dev — the only one with gold)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max number of questions (smoke test)")
    parser.add_argument("--top-k", type=parse_topks, default=[0, 1, 4, 8],
                        help="Comma-separated top-k values to sweep (default: 0,1,4,8). "
                             "k=0 disables skill selection.")
    parser.add_argument("--output-prefix", default=None,
                        help="Prefix for output files; per-k file is "
                             "{prefix}_k{K}.jsonl. Default: auto-named with timestamp.")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--task-timeout", type=int, default=TASK_TIMEOUT)
    parser.add_argument("--token-budget", type=int, default=TOKEN_BUDGET_PER_TASK,
                        help=f"Output-token budget per task (default {TOKEN_BUDGET_PER_TASK}; "
                             "0 = unlimited via large sentinel)")
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

    budget = args.token_budget if args.token_budget > 0 else 10**9

    print(f"\n>>> Sweep over top-k = {args.top_k}\n")
    summaries = {}
    for k in args.top_k:
        outfile = None
        if args.output_prefix:
            outfile = f"{args.output_prefix}_k{k}.jsonl"
        print(f"\n############ TOP-K = {k} ############\n")
        evaluate(
            split=args.split,
            max_questions=args.max,
            output_file=outfile,
            api_key=args.api_key,
            delay=args.delay,
            k=k,
            token_budget=budget,
            workers=args.workers,
            task_timeout=args.task_timeout,
        )

    print("\n\n>>> Sweep complete. Per-k jsonl files were written; the last line "
          "of each contains the summary.")
