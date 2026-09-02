"""Prompt construction — faithful port of SR-Agents ``src/sragents/prompts.py``
for the medcalcbench builder, plus the Full-Skill-Injection format from the
paper's Appendix B.1.

Do not reword these strings. P1 calibration depends on them matching.
Verified against SR-Agents @ main, fetched 2026-08-29.
"""

from __future__ import annotations

MEDCALC_SYSTEM = (
    "You are a helpful assistant for calculating a score for a given "
    "patient note. Please think step-by-step to solve the question and "
    "then generate the required score."
)

MEDCALC_USER_SUFFIX = (
    "Show your step-by-step calculation, then write your final answer on "
    "its own line in exactly this format:\n"
    "ANSWER: <your answer>\n\n"
    "For numeric answers, give the number only (e.g., 25.24). "
    "For date answers, use MM/DD/YYYY format. "
    "For scores, give the integer value. "
    "Do not include units or explanations in the ANSWER line."
)

# Appended when the injected skills expose executable tools. SR-Agents relies
# on the skill's own Example section to teach this syntax; we state it
# explicitly as well so that the -M5-full arm (which deletes every worked
# example) does not silently lose the ability to call tools for a reason
# unrelated to the ablation being tested.
TOOL_PROTOCOL = (
    "\n\nYou may call a provided tool by writing, on its own line:\n"
    "TOOL_CALL: function_name(arg=value, ...)\n"
    "You will then receive a line starting with TOOL_RESULT: containing the "
    "return value, and may continue."
)


def build_prompt(instance: dict, skills: list[dict] | None = None,
                 tool_protocol: bool = False) -> tuple[str, str]:
    """Return ``(system, user)``.

    Skill injection format is SR-Agents' Full-Skill Injection (Appendix B.1):

        Relevant Skill:
        {skill content}

        {original user prompt}

    Multiple skills are joined with a horizontal rule, as upstream.
    """
    system = MEDCALC_SYSTEM
    user = f"{instance['question']}\n\n{MEDCALC_USER_SUFFIX}"

    if tool_protocol:
        system = system + TOOL_PROTOCOL

    contents = [s["content"] for s in (skills or []) if s.get("content")]
    if contents:
        skill_block = "\n---\n".join(contents)
        user = f"Relevant Skill:\n{skill_block}\n\n{user}"

    return system, user


SKILL_HEAD = "Relevant Skill:\n"


def build_prompt_spans(instance: dict, skills: list[dict] | None = None,
                       tool_protocol: bool = False):
    """``build_prompt`` plus character spans of each region of the user message.

    The whitebox analyses compare what happens at the skill's token positions
    against what happens at the task's, so those positions have to be recorded
    when the run happens: a span cannot be recovered from a JSONL row later,
    and re-deriving it risks disagreeing with the string actually sent.

    Returns ``(system, user, spans)``, spans being character offsets into
    ``user``: ``{"skill": [a,b] | None, "task": [a,b], "suffix": [a,b]}``.
    Token spans are derived from these at replay time, on the machine whose
    tokenizer produced the run.

    Calls ``build_prompt`` rather than rebuilding the string, so the two cannot
    drift — P1 calibration depends on that exact string.
    """
    system, user = build_prompt(instance, skills, tool_protocol)

    task_text = instance["question"]
    t0 = user.index(task_text)
    s0 = user.index(MEDCALC_USER_SUFFIX, t0 + len(task_text))
    spans = {
        "skill": None,
        "task": [t0, t0 + len(task_text)],
        "suffix": [s0, s0 + len(MEDCALC_USER_SUFFIX)],
    }
    if user.startswith(SKILL_HEAD):
        # the block ends two characters before the task: the "\n\n" separator
        spans["skill"] = [len(SKILL_HEAD), t0 - 2]
    return system, user, spans
