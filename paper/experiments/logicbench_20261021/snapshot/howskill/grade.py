"""MedCalc-Bench answer extraction + scoring.

FAITHFUL PORT of SR-Agents ``src/sragents/evaluate/datasets/medcalcbench.py``
(itself ported from ncbi-nlp/MedCalc-Bench ``evaluation/evaluate.py``), plus
``evaluate/common.py``. Do not "improve" this: P1 calibration reproduces
SRA-Bench's published Qwen3-4B numbers (22.0 Direct / 73.5 Oracle) and that
only means anything if extraction and scoring are bit-for-bit theirs.

Verified against SR-Agents @ main, fetched 2026-08-29.
"""

from __future__ import annotations

import re
from datetime import datetime

_DATE_IDS = {13, 68}
_GESTATIONAL_ID = 69
_INTEGER_IDS = {
    4, 15, 16, 17, 18, 20, 21, 25, 27, 28, 29, 32, 33, 36, 43, 45, 48, 51, 69,
}

_TRIGGERS = (
    "The answer is:",
    "the answer is:",
    "Therefore, the answer is",
    "therefore, the answer is",
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks, and any unclosed trailing block."""
    if not text:
        return text
    text = _THINK_RE.sub("", text)
    # an unterminated <think> (hit the token limit mid-thought) swallows the
    # rest of the output; drop it rather than letting it poison extraction
    idx = text.find("<think>")
    if idx != -1:
        text = text[:idx]
    return text.strip()


def extract_from_trigger(raw_output: str) -> str | None:
    best_pos, best_trigger = -1, ""
    for trigger in _TRIGGERS:
        pos = raw_output.rfind(trigger)
        if pos > best_pos:
            best_pos, best_trigger = pos, trigger
    if best_pos == -1:
        return None
    after = raw_output[best_pos + len(best_trigger):]
    answer = after.split("\n")[0].strip()
    return answer.rstrip(".").rstrip("/").strip()


def extract(raw_output: str, eval_data: dict) -> str:
    output_type = eval_data.get("output_type", "decimal")
    calculator_id = eval_data.get("calculator_id", 0)

    for line in reversed(raw_output.strip().split("\n")):
        line = line.strip()
        if line.upper().startswith("ANSWER:"):
            return line[len("ANSWER:"):].strip().strip("*").strip()

    m = re.search(r'[Aa]nswer":\s*(.*?)\}', raw_output)
    if m:
        answer = m.group(1).strip().strip('"').strip("'")
        if answer and answer not in (
            "str(short_and_direct_answer_of_the_question)",
            "str(value which is the answer to the question)",
            "X.XX",
        ):
            return answer

    answer = extract_from_trigger(raw_output)
    if answer is not None:
        return answer

    if output_type == "date" or calculator_id in _DATE_IDS:
        m = re.search(r"(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(\d{4})", raw_output)
        if m:
            return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"

    if calculator_id == _GESTATIONAL_ID:
        m = re.search(
            r"\(?[\"\']?(\d+)\s*(?:weeks?)?\s*,?\s*[\"\']?(\d+)\s*(?:days?)?[\"\']?\s*\)?",
            raw_output,
        )
        if m:
            return f"({m.group(1)}, {m.group(2)})"

    matches = re.findall(r"-?\d+\.?\d*", raw_output)
    if matches:
        return matches[-1]

    lines = [l.strip() for l in raw_output.strip().split("\n") if l.strip()]
    return lines[-1] if lines else ""


def _safe_parse_number(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)$", s)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        if den != 0:
            return num / den
    return None


def _extract_weeks_days(s: str):
    m = re.search(
        r"\(?[\"\']?(\d+)\s*(?:weeks?)?[\"\']?,?\s*[\"\']?(\d+)\s*(?:days?)?[\"\']?\s*\)?",
        s or "",
    )
    return (int(m.group(1)), int(m.group(2))) if m else None


def score(extracted: str, eval_data: dict) -> dict:
    calid = eval_data.get("calculator_id", 0)
    output_type = eval_data.get("output_type", "decimal")

    if calid in _DATE_IDS:
        gt = str(eval_data["answer"]).strip()
        try:
            correct = (datetime.strptime(gt, "%m/%d/%Y")
                       == datetime.strptime(extracted.strip(), "%m/%d/%Y"))
        except (ValueError, TypeError):
            correct = False
        return {"correct": correct, "output_type": "date"}

    if calid == _GESTATIONAL_ID:
        gt_t = _extract_weeks_days(str(eval_data["answer"]).strip())
        pred_t = _extract_weeks_days(extracted)
        return {"correct": gt_t is not None and gt_t == pred_t,
                "output_type": "gestational_age"}

    gt_str = str(eval_data["answer"]).strip()

    if calid in _INTEGER_IDS or output_type == "integer":
        gt_num = _safe_parse_number(gt_str)
        pred_num = _safe_parse_number(extracted.strip())
        correct = (gt_num is not None and pred_num is not None
                   and round(pred_num) == round(gt_num))
        return {"correct": correct, "output_type": "integer"}

    pred_num = _safe_parse_number(extracted.strip())
    lower = _safe_parse_number(str(eval_data.get("lower_limit", "")).strip())
    upper = _safe_parse_number(str(eval_data.get("upper_limit", "")).strip())
    correct = (pred_num is not None and lower is not None and upper is not None
               and lower <= pred_num <= upper)
    return {"correct": correct, "output_type": "decimal"}


def evaluate(raw_output: str, instance: dict) -> dict:
    eval_data = instance["eval_data"]
    extracted = extract(strip_think_tags(raw_output), eval_data)
    result = score(extracted, eval_data)
    result["extracted_answer"] = extracted
    return result
