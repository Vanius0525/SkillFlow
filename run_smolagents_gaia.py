#!/usr/bin/env python3
"""
smolagents CodeAgent on GAIA.

An external scaffold has to run as itself, or the comparison is meaningless.
This file therefore does NOT reimplement smolagents inside our agent loop: it
hands smolagents the task and lets it run its own ReAct loop, its own code
executor, its own prompts and its own termination. What we keep control of is
only the three things that must be identical across every cell:

  * the task set     -- the same GAIA rows, via skillflow.load_gaia_tasks
  * the scorer       -- gaia_scorer.question_scorer, the official one
  * the output shape -- the same JSONL, so results/ stays uniform

What this buys is the CodeAct axis. Our harness has the model emit JSON tool
calls; smolagents has it emit executable Python. The CodeAct paper reports up
to ~20 points from that difference alone, so without this cell a reader cannot
tell whether SkillFlow's numbers reflect the method or the action format.

Model: any OpenAI-compatible endpoint, i.e. the same vLLM the rest of the
harness talks to. Same weights, same server, different scaffold.

    python run_smolagents_gaia.py --levels 1 2 --output results/gaia_smolagents.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import gaia_scorer

# skillflow owns the GAIA loader; importing it is deliberate, so both cells
# evaluate byte-identical task rows rather than two similar-looking sets.
from skillflow import GAIA_VALIDATION_DIR, load_gaia_tasks


def _require_smolagents():
    try:
        from smolagents import CodeAgent, OpenAIServerModel  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "smolagents is not installed. On the server:\n"
            "    pip install 'smolagents[toolkit]'\n"
            f"(original error: {e})"
        ) from e


# GAIA is scored by exact match, so the answer format is not a style note.
ANSWER_INSTRUCTION = (
    "\n\nReport your answer with the `final_answer` tool. The answer must be "
    "the short, direct value the question asks for -- a number, a word, a name, "
    "a date, or a comma-separated list -- with no explanation, no units unless "
    "the question asks for them, and no surrounding sentence. Do not write "
    "'The answer is'; give the value itself."
)

# CodeAgent runs real Python, so what it can import IS its capability surface.
# These cover GAIA's attachment types (xlsx, pdf, csv, json, images, audio) and
# nothing that would let it wander outside the task.
DEFAULT_IMPORTS = [
    "pandas", "numpy", "json", "csv", "re", "math", "statistics", "itertools",
    "collections", "datetime", "os", "pathlib", "zipfile", "io", "string",
    "openpyxl", "pypdf", "PyPDF2", "bs4", "requests", "PIL", "chess",
    "unicodedata", "fractions", "urllib", "urllib.parse", "sympy",
]


class _Deadline:
    """
    Wall-clock limit for one task.

    smolagents has no timeout of its own, and killing a thread mid-run is not
    possible in Python, so the limit is enforced where the library gives us a
    hook: a step callback that raises once the budget is spent. The run stops
    at the next step boundary rather than instantly, which is close enough and
    leaves no orphaned thread behind.
    """

    def __init__(self, seconds: float | None):
        self.until = None if not seconds else time.time() + seconds

    def __call__(self, *args, **kwargs):
        if self.until and time.time() > self.until:
            raise TimeoutError("task wall-clock limit reached")


def build_agent(args, deadline: _Deadline):
    from smolagents import CodeAgent, OpenAIServerModel, VisitWebpageTool, WebSearchTool

    model = OpenAIServerModel(
        model_id=args.model,
        api_base=args.base_url,
        api_key=os.environ.get("OPENAI_API_KEY", "EMPTY"),
        # smolagents #908: OpenAIServerModel sends structured content parts that
        # vLLM's chat endpoint rejects. Flattening to plain text is the
        # documented workaround and is required for any vLLM-served model.
        flatten_messages_as_text=True,
    )

    tools = []
    if not args.no_search:
        try:
            tools.append(WebSearchTool())
        except Exception as e:
            print(f"[WARN] WebSearchTool unavailable ({e}); continuing without it")
    # Kept even under --no-search: that flag turns off the search *engine*, not
    # the ability to fetch a URL the question or an attachment names.
    tools.append(VisitWebpageTool())

    return CodeAgent(
        tools=tools,
        model=model,
        max_steps=args.max_steps,
        additional_authorized_imports=DEFAULT_IMPORTS,
        verbosity_level=args.verbosity,
        step_callbacks=[deadline],
    )


def _token_counts(agent) -> dict:
    """
    Read token usage out of smolagents.

    The accessor has moved between versions (monitor counters, then a
    TokenUsage on RunResult), so every shape is tried and a miss reports zeros
    rather than taking the run down.
    """
    monitor = getattr(agent, "monitor", None)
    if monitor is not None:
        getter = getattr(monitor, "get_total_token_counts", None)
        if callable(getter):
            try:
                counts = getter()
            except Exception:
                counts = None
            if isinstance(counts, dict):
                return {"input": counts.get("input", 0) or counts.get("input_tokens", 0),
                        "output": counts.get("output", 0) or counts.get("output_tokens", 0)}
            if counts is not None:
                return {"input": getattr(counts, "input_tokens", 0),
                        "output": getattr(counts, "output_tokens", 0)}
        return {"input": getattr(monitor, "total_input_token_count", 0),
                "output": getattr(monitor, "total_output_token_count", 0)}
    return {"input": 0, "output": 0}


def _answer_text(result) -> str:
    """smolagents returns the final_answer payload; normalise it to a string."""
    if result is None:
        return ""
    text = str(result).strip()
    # Some models still wrap the value in a sentence despite the instruction.
    for line in reversed(text.splitlines()):
        if line.strip().upper().startswith("FINAL ANSWER:"):
            return line.split(":", 1)[1].strip()
    return text


def run_one(idx: int, n: int, row, args) -> dict:
    question = str(row["Question"]).strip()
    gold = str(row["Final answer"]).strip()
    level = str(row["Level"])
    task_id = str(row.get("task_id", ""))
    file_name = str(row.get("file_name", "") or "")

    task = question
    if file_name:
        path = Path(GAIA_VALIDATION_DIR) / file_name
        task += (f"\n\nAn attachment for this question is at: {path}\n"
                 f"Read it with Python (open it, or use pandas/openpyxl/pypdf as "
                 f"appropriate for its type).")
    task += ANSWER_INSTRUCTION

    print(f"\n[T{idx:3d}/{n}] L{level} {task_id}", flush=True)
    print(f"[T{idx:3d}/{n}]   Q: {question[:77]}{'...' if len(question) > 77 else ''}",
          flush=True)

    deadline = _Deadline(args.task_timeout)
    agent = build_agent(args, deadline)

    started = time.time()
    timed_out = False
    error = ""
    try:
        result = agent.run(task)
        predicted = _answer_text(result)
    except TimeoutError:
        timed_out = True
        predicted = ""
        print(f"[T{idx:3d}/{n}]   [TIMEOUT] after {args.task_timeout}s", flush=True)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        predicted = ""
        print(f"[T{idx:3d}/{n}]   [ERROR] {error}", flush=True)

    correct = gaia_scorer.question_scorer(predicted, gold) if predicted else False
    tokens = _token_counts(agent)
    tokens["total"] = tokens["input"] + tokens["output"]
    steps = len(getattr(getattr(agent, "memory", None), "steps", []) or [])

    status = "PASS" if correct else ("TIMEOUT" if timed_out else "FAIL")
    print(f"[T{idx:3d}/{n}]   {status}  steps={steps}  "
          f"tok={tokens['input']}in/{tokens['output']}out  "
          f"{time.time() - started:.0f}s", flush=True)
    print(f"[T{idx:3d}/{n}]   gold={gold[:40]!r}  pred={predicted[:40]!r}", flush=True)

    return {
        "benchmark": "gaia",
        "framework": "smolagents",
        "scaffold": "CodeAgent",
        "task_id": task_id,
        "level": level,
        "question": question,
        "file_name": file_name,
        "gold": gold,
        "predicted": predicted,
        "correct": correct,
        "steps": steps,
        "timed_out": timed_out,
        "error": error,
        "wall_seconds": round(time.time() - started, 1),
        "tokens": tokens,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--levels", nargs="+", type=int, default=[1, 2])
    ap.add_argument("--max", type=int, default=None, help="cap the number of tasks")
    ap.add_argument("--output", default=None)
    ap.add_argument("--model", default=os.environ.get("QWEN_MODEL", "Qwen/Qwen3-8B"),
                    help="model id served by the endpoint")
    ap.add_argument("--base-url",
                    default=os.environ.get("QWEN_BASE_URL", "http://localhost:8000/v1"),
                    help="OpenAI-compatible base URL (the same vLLM as the rest)")
    ap.add_argument("--max-steps", type=int, default=20,
                    help="smolagents max steps per task (default: 20)")
    ap.add_argument("--task-timeout", type=int, default=600,
                    help="wall-clock seconds per task, 0 to disable")
    ap.add_argument("--no-search", action="store_true",
                    help="drop the web search tool (offline runs)")
    ap.add_argument("--verbosity", type=int, default=1)
    args = ap.parse_args()

    _require_smolagents()

    df = load_gaia_tasks(levels=tuple(args.levels), max_questions=args.max)
    n = len(df)
    output = args.output or (
        f"smolagents_gaia_L{''.join(str(l) for l in sorted(args.levels))}_{n}q_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")

    print("=== smolagents CodeAgent on GAIA ===")
    print(f"Model     : {args.model} @ {args.base_url}")
    print(f"Levels    : {sorted(args.levels)}")
    print(f"Tasks     : {n}")
    print(f"Max steps : {args.max_steps}   timeout: {args.task_timeout}s/task")
    print(f"Scorer    : official GAIA")
    print(f"Output    : {output}\n")

    # Sequential on purpose: smolagents runs a code executor per task, and the
    # point of this cell is the scaffold, not throughput.
    stats: dict[str, dict] = {}
    with open(output, "a") as fh:
        for idx, (_, row) in enumerate(df.iterrows(), start=1):
            result = run_one(idx, n, row, args)
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")
            fh.flush()
            lvl = result["level"]
            s = stats.setdefault(lvl, {"correct": 0, "total": 0, "in": 0, "out": 0})
            s["total"] += 1
            s["correct"] += int(result["correct"])
            s["in"] += result["tokens"]["input"]
            s["out"] += result["tokens"]["output"]

    print("\n" + "=" * 60)
    print("SMOLAGENTS GAIA RESULTS SUMMARY")
    print("=" * 60)
    total_c = total_t = g_in = g_out = 0
    per_level = {}
    for lvl in sorted(stats):
        s = stats[lvl]
        acc = s["correct"] / s["total"] * 100 if s["total"] else 0
        total_c += s["correct"]
        total_t += s["total"]
        g_in += s["in"]
        g_out += s["out"]
        per_level[f"level_{lvl}"] = {"correct": s["correct"], "total": s["total"],
                                     "accuracy": round(acc, 2),
                                     "tokens_input": s["in"], "tokens_output": s["out"]}
        print(f"  Level {lvl}: {s['correct']}/{s['total']}  ({acc:.1f}%)  "
              f"tokens {s['in']:,}in/{s['out']:,}out")
    overall = total_c / total_t * 100 if total_t else 0
    print(f"  Overall : {total_c}/{total_t}  ({overall:.1f}%)")
    print("=" * 60)
    print(f"Saved to : {output}")

    with open(output, "a") as fh:
        fh.write(json.dumps({
            "_type": "summary",
            "framework": "smolagents",
            "scaffold": "CodeAgent",
            "benchmark": "gaia",
            "model": args.model,
            "base_url": args.base_url,
            "max_steps": args.max_steps,
            "task_timeout": args.task_timeout,
            "scorer": "gaia-official",
            "levels": sorted(str(l) for l in args.levels),
            "per_level": per_level,
            "overall": {"correct": total_c, "total": total_t,
                        "accuracy": round(overall, 2),
                        "tokens_input": g_in, "tokens_output": g_out},
        }, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
