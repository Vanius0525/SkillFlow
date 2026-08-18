#!/usr/bin/env python3
"""
Termination contract for the agent loop.

A regular expression over the transcript is not a termination signal. When a
model stops emitting tool calls it has not necessarily finished — small models
routinely stop after a paragraph of reasoning, or after narrating what they
are about to do — and a harness that treats "stopped talking" as "answered"
scores those turns as wrong answers rather than as unfinished ones. That is a
harness artefact, and it inflates whatever scaffold happens to have more
chances to speak.

The fix is the one Inspect AI's `react` agent uses:

  1. an explicit `submit` tool is the only clean way to end a turn, and
  2. when the model stops without submitting, it is nudged to continue or to
     submit, up to `MAX_CONTINUES` times, before silence is accepted.

Both harnesses import this module so the contract is identical on either side
of the comparison. `submit`'s answer is returned as a `FINAL ANSWER:` line so
the existing extractors keep working unchanged; whether a turn actually ended
via `submit` is recorded in `ContractStats` rather than being inferred later.
"""

import re
import threading
from dataclasses import dataclass

# The tool that ends a turn. Description is deliberately blunt about format:
# GAIA is scored by exact match, so "a word, number, name or date" is not a
# style note, it is the difference between right and wrong.
SUBMIT_TOOL = {
    "name": "submit",
    "description": (
        "Submit your final answer and end the task. Call this once, as soon as "
        "you have the answer. The answer must be the short, direct value the "
        "question asks for — a word, a number, a name, a date, or a "
        "comma-separated list — with no explanation, no units unless the "
        "question asks for them, and no surrounding sentence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The final answer, and nothing else.",
            }
        },
        "required": ["answer"],
    },
}

# Inspect AI's default continue message, near-verbatim.
CONTINUE_MSG = (
    "Please proceed to the next step using your best judgement. If you believe "
    "you have completed the task, call the `submit` tool with your final answer."
)

# How many times a silent model is nudged before silence is accepted. Small on
# purpose: this is a fix for models that stop one step early, not a licence to
# keep re-prompting a model that has genuinely given up.
MAX_CONTINUES = 3

_FINAL_ANSWER_RE = re.compile(r"^\s*FINAL ANSWER:\s*(.+)", re.IGNORECASE | re.MULTILINE)


def has_explicit_answer(text: str) -> bool:
    """
    True only for a real `FINAL ANSWER:` line.

    Deliberately stricter than the extractors, which fall back to "the last
    non-empty line" and therefore always return something. Deciding whether to
    nudge needs to distinguish "answered" from "said anything at all".
    """
    return bool(text) and bool(_FINAL_ANSWER_RE.search(text))


def submitted_answer(text: str) -> str:
    """The answer from a `FINAL ANSWER:` line, or '' if there is none."""
    m = None
    for m in _FINAL_ANSWER_RE.finditer(text or ""):
        pass  # keep the last match
    return m.group(1).strip() if m else ""


def find_submit_block(content) -> object | None:
    """The `submit` tool_use block in a model response, if it called one."""
    for block in content or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == "submit":
            return block
        if isinstance(block, dict) and block.get("type") == "tool_use" \
                and block.get("name") == "submit":
            return block
    return None


def answer_from_submit(block) -> str:
    """Read the `answer` argument out of a submit block."""
    inputs = block.get("input", {}) if isinstance(block, dict) else getattr(block, "input", {})
    return str((inputs or {}).get("answer", "")).strip()


def as_final_answer(answer: str) -> str:
    """Render a submitted answer in the form the extractors already understand."""
    return f"FINAL ANSWER: {answer}"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class ContractStats:
    """Per-task record of how the turn ended."""
    submit_enabled: bool = False
    submitted: int = 0             # turns ended by a submit() call
    continues: int = 0             # nudges issued
    rescued: int = 0               # turns that answered only after a nudge
    ended_without_answer: int = 0  # turns that produced no explicit answer at all


class _ContractAggregate:
    """Process-wide contract counters; one eval run is one process."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.enabled = False
        self.tasks = 0
        self.submitted = 0
        self.continues = 0
        self.rescued = 0
        self.ended_without_answer = 0

    def add(self, s: ContractStats) -> None:
        with self._lock:
            self.enabled = self.enabled or s.submit_enabled
            self.tasks += 1
            self.submitted += s.submitted
            self.continues += s.continues
            self.rescued += s.rescued
            self.ended_without_answer += s.ended_without_answer

    def summary(self) -> dict:
        with self._lock:
            return {
                "submit_tool": self.enabled,
                "tasks": self.tasks,
                "turns_submitted": self.submitted,
                "continues_issued": self.continues,
                "turns_rescued_by_continue": self.rescued,
                "turns_without_explicit_answer": self.ended_without_answer,
            }

    def render(self) -> str:
        s = self.summary()
        if not s["submit_tool"]:
            return ("  termination        : regex only (no submit tool) — a turn that "
                    "stops talking is scored as its last line")
        return (
            f"  termination        : submit tool on — {s['turns_submitted']} turns "
            f"submitted, {s['continues_issued']} nudges issued, "
            f"{s['turns_rescued_by_continue']} turns rescued, "
            f"{s['turns_without_explicit_answer']} still ended with no answer"
        )


CONTRACT_AGG = _ContractAggregate()


def add_contract_args(parser) -> None:
    """Register the shared termination-contract CLI flags."""
    parser.add_argument(
        "--no-submit-tool", dest="submit_tool", action="store_false", default=True,
        help="disable the submit tool and the continue nudge, restoring the old "
             "'first end_turn wins' behaviour. Only useful for reproducing "
             "pre-fix numbers — it makes the harness score unfinished turns as "
             "wrong answers.")
    parser.add_argument(
        "--max-continues", type=int, default=MAX_CONTINUES,
        help=f"how many times a silent model is nudged to continue or submit "
             f"(default: {MAX_CONTINUES})")
