#!/usr/bin/env python3
"""
AppWorld adapter.

AppWorld (StonyBrookNLP, ACL'24 Best Resource Paper) is the long-horizon cell of
the benchmark set. GAIA averages roughly 5-15 steps, which is short enough that
context management has little room to matter; AppWorld allows up to 2000 API
calls and defaults to 1000 interactions per task, so a transcript there actually
outgrows a 32k window. That is the regime SkillFlow claims to be about.

Two things make it different from GAIA, and the adapter exists to absorb both:

  1. The action space is a Python interpreter, not a filesystem. The agent does
     not run bash; it writes code that calls `apis.<app>.<endpoint>(...)`, and
     variables persist across calls. So AppWorld tasks get their own tool
     surface — a single `execute` tool — instead of bash/read_file/write_file.

  2. Completion is environment state, not text. The agent calls
     `apis.supervisor.complete_task()` and the environment reports
     `world.task_completed()`. Scoring is database-state-based: unit tests check
     both that the goal was reached and that nothing else was damaged (the TGC
     and SGC numbers in the paper), so there is no answer string to match.

Install (on the server, not in this repo):

    pip install appworld
    appworld install
    appworld download data

Docker is optional — AppWorld runs serverless in-process via FastAPI's
TestClient, which is why it fits the "no per-task container" constraint.

Official aggregate numbers come from the CLI, not from this file:

    appworld evaluate <experiment_name> <split>
"""

from __future__ import annotations

import json
import os
from typing import Any

# Every AppWorld import is deferred. The rest of the harness must remain usable
# on a machine where AppWorld is not installed, and an ImportError at module
# scope would take GAIA down with it.
_IMPORT_ERROR: str | None = None


def _appworld():
    """Import appworld, or raise with the install commands rather than a stack trace."""
    global _IMPORT_ERROR
    try:
        import appworld  # noqa: F401
        from appworld import AppWorld, load_task_ids
        return AppWorld, load_task_ids
    except ImportError as e:  # pragma: no cover - depends on the machine
        _IMPORT_ERROR = str(e)
        raise ImportError(
            "AppWorld is not installed. On the server:\n"
            "    pip install appworld\n"
            "    appworld install\n"
            "    appworld download data\n"
            f"(original error: {e})"
        ) from e


def is_available() -> bool:
    """True if AppWorld can be imported. Used to skip cleanly, never to guess."""
    try:
        _appworld()
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

SPLITS = ("train", "dev", "test_normal", "test_challenge")


def load_appworld_tasks(split: str = "dev", max_questions: int | None = None) -> list[dict]:
    """
    Task ids for a split. The instruction itself is only available inside the
    environment context, so tasks are loaded lazily: this returns ids, and
    `AppWorldSession` opens each one.
    """
    if split not in SPLITS:
        raise ValueError(f"unknown AppWorld split {split!r}; choose from {SPLITS}")
    _, load_task_ids = _appworld()
    task_ids = list(load_task_ids(split))
    if max_questions:
        task_ids = task_ids[:max_questions]
    return [{"task_id": tid, "split": split} for tid in task_ids]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
# Kept close to AppWorld's own minimal-agent template: the agent acts on behalf
# of a supervisor whose credentials it must look up, discovers APIs through the
# api_docs app rather than being handed a 457-endpoint dump, and decides for
# itself when the task is done.

BASE_SYSTEM_APPWORLD = """\
You are an autonomous coding agent acting on behalf of a supervisor. You \
complete the supervisor's request by writing and running small blocks of \
Python that call app APIs.

The only action available to you is the `execute` tool, which runs Python in a \
persistent interpreter: variables you define in one call are still there in the \
next. There is no shell and no filesystem access — everything happens through \
the APIs.

How to work:
1. Discover before you call. `apis.api_docs.show_app_descriptions()` lists the \
apps; `apis.api_docs.show_api_descriptions(app_name='...')` lists an app's \
APIs; `apis.api_docs.show_api_doc(app_name='...', api_name='...')` gives the \
exact signature. Do not guess an endpoint or its arguments.
2. Credentials come from the supervisor app: \
`apis.supervisor.show_account_passwords()` returns the passwords you need to \
log in. Most APIs need an access_token obtained by logging in first.
3. Run SMALL blocks and print what you need to see. A block that does five \
things at once tells you nothing about which of them failed.
4. Read the API docs for how results are paginated, and page through them — \
the first page is rarely the whole answer.
5. When, and only when, the request is fully satisfied, call \
`apis.supervisor.complete_task()`. Nobody will confirm this for you; deciding \
it is part of the task.

Write plain Python only — no markdown fences, no commentary inside the code."""


def build_task_prompt(world) -> str:
    """The user-facing task message: the instruction plus who it is for."""
    task = world.task
    sup = task.supervisor
    parts = [
        "## Supervisor",
        f"You are acting on behalf of {_attr(sup, 'first_name')} "
        f"{_attr(sup, 'last_name')}.",
    ]
    for field in ("email", "phone_number"):
        value = _attr(sup, field)
        if value:
            parts.append(f"- {field}: {value}")
    parts += [
        "",
        "Their account passwords are available through "
        "`apis.supervisor.show_account_passwords()`.",
        "",
        "## Request",
        str(task.instruction).strip(),
    ]
    return "\n".join(parts)


def _attr(obj, name: str) -> str:
    """Read a field from the supervisor object, whether it is an object or a dict."""
    if isinstance(obj, dict):
        return str(obj.get(name, "") or "")
    return str(getattr(obj, name, "") or "")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class AppWorldSession:
    """
    One task's environment, opened as a context manager.

    `experiment_name` decides where AppWorld writes its own outputs
    (./experiments/outputs/<experiment_name>/), which is also what the official
    `appworld evaluate` CLI reads, so it must be stable across a run.
    """

    def __init__(self, task_id: str, experiment_name: str, **kwargs):
        self.task_id = task_id
        self.experiment_name = experiment_name
        self._kwargs = kwargs
        self.world = None

    def __enter__(self):
        AppWorld, _ = _appworld()
        self.world = AppWorld(task_id=self.task_id,
                              experiment_name=self.experiment_name,
                              **self._kwargs)
        self.world.__enter__()
        return self

    def __exit__(self, *exc):
        if self.world is not None:
            return self.world.__exit__(*exc)
        return False

    # -- agent-facing ------------------------------------------------------
    @property
    def instruction(self) -> str:
        return str(self.world.task.instruction)

    def prompt(self) -> str:
        return build_task_prompt(self.world)

    def execute(self, code: str) -> str:
        """Run one code block. AppWorld returns printed output or a stack trace."""
        try:
            return str(self.world.execute(code))
        except Exception as e:
            # An environment-side failure must reach the model as an
            # observation, not kill the task.
            return f"[environment error] {type(e).__name__}: {e}"

    def completed(self) -> bool:
        try:
            return bool(self.world.task_completed())
        except Exception:
            return False

    # -- scoring -----------------------------------------------------------
    def evaluate(self) -> dict:
        """
        Per-task evaluation.

        AppWorld scores from database state, not from an answer string, and the
        exact shape of `evaluate().to_dict()` is the environment's business, so
        the whole dict is kept and `success` is derived defensively. Treat the
        aggregate from `appworld evaluate <experiment> <split>` as the number of
        record; this is for per-task logging and a live pass rate.
        """
        try:
            report = self.world.evaluate()
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

        raw: Any
        try:
            raw = report.to_dict()
        except Exception:
            raw = report

        return {"success": _extract_success(raw), "raw": _jsonable(raw)}


def _extract_success(raw) -> bool:
    """
    Pull a pass/fail out of AppWorld's evaluation report.

    Checked in order of specificity. AppWorld's headline metric is Task Goal
    Completion, so that wins when present; `success`/`passed` are accepted as
    aliases; failing everything, a report with no failed tests counts as a pass.
    """
    if not isinstance(raw, dict):
        return bool(raw)
    for key in ("success", "passed", "task_goal_completion", "tgc"):
        if key in raw:
            return bool(raw[key])
    for key in ("num_failed_tests", "failed_tests", "failures"):
        if key in raw:
            value = raw[key]
            return len(value) == 0 if isinstance(value, (list, tuple)) else not value
    return False


def _jsonable(value):
    """Best-effort conversion so the report can go straight into the JSONL."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Tool surface
# ---------------------------------------------------------------------------
# AppWorld's action space is a Python interpreter, so the filesystem tools are
# not merely unnecessary here — offering them invites the model to try bash and
# burn its budget on calls the environment cannot serve.

EXECUTE_TOOL = {
    "name": "execute",
    "description": (
        "Run a block of Python in the persistent task interpreter and return "
        "whatever it prints, or the stack trace if it raises. Variables persist "
        "between calls. Use it to look up API docs, log in, and act. Keep "
        "blocks small and print what you need to inspect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source. No markdown fences.",
            }
        },
        "required": ["code"],
    },
}


def experiment_name_for(output_path: str | None, fallback: str = "skillflow") -> str:
    """
    Stable AppWorld experiment name derived from the results filename, so a
    cell's AppWorld outputs sit next to its JSONL and `appworld evaluate` can be
    pointed at exactly one cell.
    """
    if not output_path:
        return fallback
    stem = os.path.splitext(os.path.basename(output_path))[0]
    return stem or fallback
