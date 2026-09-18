"""Official SRA-Bench graders for TheoremQA, LogicBench and CHAMP.

VERBATIM PORT of SR-Agents (https://github.com/oneal2000/SR-Agents, MIT),
``src/sragents/evaluate/datasets/{theoremqa,logicbench,champ}.py`` and
``evaluate/common.py``, fetched 2026-09-14. The only edits are the imports and
the registry: the bodies are theirs so that accuracy here means what it means in
the SRA-Bench paper. MedCalc keeps its own earlier port in ``grade.py``.

Do not "improve" the extraction. TheoremQA's extractor depends on
``latex2sympy2`` when it is installed, as upstream's does; the venv must have it.
"""
from __future__ import annotations

import math
import re

from howskill.grade import extract_from_trigger   # same body as upstream common.py

# upstream sragents/llm.py, verbatim: grade.py's version also strips TRAILING
# whitespace, which moves LogicBench's last-line fallback onto a different line
_THINK_CLOSED_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<think>.*", re.DOTALL)


def strip_think_tags(text: str) -> str:
    if "<think>" not in text:
        return text
    text = _THINK_CLOSED_RE.sub("", text)
    text = _THINK_OPEN_RE.sub("", text)
    return text.lstrip()

_REGISTRY: dict = {}


def register(dataset: str):
    def wrap(fn):
        _REGISTRY[dataset] = fn
        return fn
    return wrap


def within_eps(pred: float, gt: float, eps_ratio: float = 0.04,
               abs_floor: float = 1e-9) -> bool:
    eps = max(abs(gt) * eps_ratio, abs_floor)
    return gt - eps <= pred <= gt + eps


# =========================== theoremqa ======================================
_TRIGGERS = (
    "The answer is:",
    "the answer is:",
    "Therefore, the answer is",
    "therefore, the answer is",
)


# ---------------------------------------------------------------------------
# Numeric helpers (shared between extraction and evaluation)
# ---------------------------------------------------------------------------

def _clean_units(pred_str: str) -> str:
    def _convert_pi(s: str) -> str:
        s = s.replace("\\pi", "\u03c0")
        s = re.sub(r"(?<![\d}])\\?\u03c0", "3.14", s)
        s = re.sub(r"(\d)(\\?\u03c0)", r"\1*3.14", s)
        s = re.sub(r"\{(\\?\u03c0)\}", "3.14", s)
        s = re.sub(r"\*(\\?\u03c0)", "*3.14", s)
        return s

    pred_str = _convert_pi(pred_str)
    pred_str = pred_str.replace("%", "/100")
    pred_str = pred_str.replace("$", "")
    pred_str = pred_str.replace("\u00a5", "")
    pred_str = pred_str.replace("\u00b0C", "")
    pred_str = pred_str.replace(" C", "")
    pred_str = pred_str.replace("\u00b0", "")
    return pred_str


def _floatify(num) -> float | int | None:
    if isinstance(num, (int, float)):
        return num
    try:
        num = float(num)
        if num.is_integer():
            return round(num)
        return num
    except Exception:
        return None


def _number_it(num) -> float | int | None:
    if isinstance(num, (int, float)):
        return num
    num = _clean_units(str(num))
    try:
        from latex2sympy2 import latex2sympy
        num = str(latex2sympy(num))
    except Exception:
        pass
    result = _floatify(num)
    if result is not None:
        return result
    try:
        val = eval(num)  # noqa: S307
        if isinstance(val, (list, tuple)):
            val = val[0]
        result = _floatify(val)
        if result is not None:
            return result
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _extract_answer(pred: str, answer_flag: bool = True) -> str:
    """Core answer extraction, ported from TheoremQA utils.py."""
    if any(opt in pred.lower() for opt in ["yes", "true"]):
        return "True"
    if any(opt in pred.lower() for opt in ["no", "false"]):
        return "False"
    if any(opt in pred.lower() for opt in ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)"]):
        return pred

    if answer_flag:
        pred = pred.split("=")[-1].strip()
        pred = _clean_units(pred)
        try:
            from latex2sympy2 import latex2sympy
            tmp = str(latex2sympy(pred))
            pred = str(eval(tmp))  # noqa: S307
        except Exception:
            if re.match(r"-?[\d\.]+\s\D+$", pred):
                pred = pred.split(" ")[0]
            elif re.match(r"-?[\d\.]+\s[^\s]+$", pred):
                pred = pred.split(" ")[0]
    else:
        preds = re.findall(r"-?\d*\.?\d+", pred)
        if preds:
            pred = preds[-1]
        else:
            pred = ""
    return pred


def _tqa_extract(raw_output: str) -> str:
    pred = raw_output.strip("\n")

    # Detect ICL leakage
    icl = any(pred.count(t) > 1 for t in _TRIGGERS)
    if icl:
        pred = pred.split("\n\n")[0]

    preds = re.split("|".join(re.escape(t) for t in _TRIGGERS), pred)
    if len(preds) > 1:
        answer_flag = True
        pred = preds[-1]
    else:
        answer_flag = False

    pred = pred.strip("\n").rstrip(".").rstrip("/").strip()
    pred = _extract_answer(pred, answer_flag)
    pred = pred.rstrip(".").rstrip("/")
    return pred


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _compare_two_numbers(p, gt) -> bool:
    try:
        if p is None or math.isnan(p):
            return False
        if isinstance(gt, int):
            return round(p) == gt
        return within_eps(pred=p, gt=gt)
    except Exception:
        return False


def _compare_two_list(pred, gt) -> bool:
    if not isinstance(pred, list):
        return False
    if len(pred) != len(gt):
        return False
    if any(not isinstance(x, (int, float)) for x in pred):
        return False
    return all(
        _compare_two_numbers(p, g)
        for p, g in zip(sorted(pred), sorted(gt))
    )


def _compare_answer_with_groundtruth(answer, groundtruth_str, groundtruth_num=None):
    if groundtruth_str.lower() in ("(a)", "(b)", "(c)", "(d)", "(e)", "(f)"):
        return groundtruth_str.lower() in answer.lower()
    if answer.lower() == groundtruth_str.lower():
        return True
    if groundtruth_num is not None:
        if isinstance(groundtruth_num, (int, float)):
            return _compare_two_numbers(_number_it(answer), groundtruth_num)
        else:
            if answer.startswith("(") and answer.endswith(")"):
                try:
                    answer_list = list(eval(answer))  # noqa: S307
                    answer_list = [_number_it(a) for a in answer_list]
                    return _compare_two_list(answer_list, groundtruth_num)
                except Exception:
                    return False
            return False
    return False


def _eval(extracted: str, eval_data: dict) -> dict:
    gt_str = str(eval_data["answer"]).strip()
    answer_type = eval_data.get("answer_type", "float")
    gt_num = None

    if "list" in answer_type:
        try:
            parsed = eval(gt_str)  # noqa: S307
            if isinstance(parsed, (list, tuple)):
                gt_num = list(parsed)
        except Exception:
            gt_num = None
    elif answer_type in ("integer", "float"):
        gt_num = _floatify(gt_str)

    correct = _compare_answer_with_groundtruth(extracted, gt_str, gt_num)
    return {"correct": correct, "answer_type": answer_type}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

@register("theoremqa")
def _eval_theoremqa(raw_output: str, instance: dict) -> dict:
    extracted = _tqa_extract(strip_think_tags(raw_output))
    result = _eval(extracted, instance["eval_data"])
    result["extracted_answer"] = extracted
    return result

# =========================== logicbench =====================================
# # Extraction
# ---------------------------------------------------------------------------

def _extract_bqa(text: str) -> str:
    lower = text.lower()

    # Last-match semantics: a model may state a tentative answer early
    # and revise it later; the final stated answer wins.
    matches = list(re.finditer(
        r"(?:the\s+)?answer\s+is[:\s]*\**\s*(yes|no|true|false)\b", lower
    ))
    if matches:
        return "yes" if matches[-1].group(1) in ("yes", "true") else "no"

    m = re.match(r"\**(yes|no)\**[.,!\s]", lower)
    if m:
        return m.group(1)

    tail = lower[-500:]
    neg_patterns = [
        r"cannot\s+(?:be\s+)?(?:conclude|infer|say|determine)",
        r"not\s+necessarily\s+true",
        r"not\s+(?:possible|correct|true|valid)",
        r"cannot\s+(?:logically|necessarily|definitively)",
        r"\bno,\s",
    ]
    for pat in neg_patterns:
        if re.search(pat, tail):
            return "no"

    matches = list(re.finditer(r"\b(yes|no)\b", tail))
    if matches:
        return matches[-1].group(1)

    if "true" in tail:
        return "yes"
    if "false" in tail:
        return "no"
    return text.split("\n")[-1].strip().lower()


def _extract_mcqa(text: str, question: str) -> str:
    lower = text.lower()

    matches = list(re.finditer(r"choice[_ ]?(\d+)", lower))
    if matches:
        return f"choice_{matches[-1].group(1)}"

    m = re.search(
        r"(?:answer|option)\s*(?:is)?[:\s]*\**\s*(?:choice[_ ]?)?(\d+)\b", lower
    )
    if m:
        return f"choice_{m.group(1)}"

    # Try to match actual choice text from the question
    choice_texts = []
    for i in range(1, 6):
        qm = re.search(
            rf"choice_{i}:\s*(.+?)(?:\n|choice_|$)",
            question,
            re.IGNORECASE,
        )
        if qm:
            choice_texts.append((i, qm.group(1).strip()))

    tail = lower[-500:]
    for idx, ct in reversed(choice_texts):
        if ct.lower()[:40] in tail:
            return f"choice_{idx}"

    answer = extract_from_trigger(text)
    if answer is None:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        answer = lines[-1] if lines else ""
    answer = answer.strip().lower()

    m = re.search(r"\b([1-5])\b", answer)
    if m:
        return f"choice_{m.group(1)}"
    return answer


def _lb_extract(raw_output: str, instance: dict) -> str:
    text = raw_output.strip()
    task_type = instance["eval_data"].get("task_type", "BQA")
    if task_type == "BQA":
        return _extract_bqa(text)
    return _extract_mcqa(text, instance.get("question", ""))


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

@register("logicbench")
def _eval_logicbench(raw_output: str, instance: dict) -> dict:
    eval_data = instance["eval_data"]
    extracted = _lb_extract(strip_think_tags(raw_output), instance)
    gt = eval_data["answer"].strip().lower()
    pred = extracted.strip().lower()
    return {
        "extracted_answer": extracted,
        "correct": pred == gt,
        "task_type": eval_data.get("task_type", "BQA"),
    }

# =========================== champ ==========================================
def _champ_extract(raw_output: str) -> str:
    # Try structured ANSWER: line (last occurrence)
    for line in reversed(raw_output.strip().split("\n")):
        line = line.strip()
        if line.upper().startswith("ANSWER:"):
            answer = line[len("ANSWER:"):].strip()
            answer = answer.strip("*").strip()
            return answer

    answer = extract_from_trigger(raw_output)
    if answer is not None:
        return answer

    lines = [line.strip() for line in raw_output.strip().split("\n") if line.strip()]
    return lines[-1] if lines else ""


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _extract_alternatives(s: str) -> list[str]:
    """E.g. "C(10, 5), or equivalently 252" → ["252"]."""
    alts = []
    m = re.search(r",?\s*or\s+(?:equivalently|approximately)\s+(.+)$", s, flags=re.I)
    if m:
        alt_part = m.group(1).strip().rstrip(".")
        alt_part = re.sub(r"\s*\([^)]*\)\s*$", "", alt_part).strip()
        if alt_part:
            alts.append(alt_part)
    return alts


def _normalize_str(s: str) -> str:
    s = s.strip().rstrip(".")
    s = re.sub(r",?\s*or\s+(?:equivalently|approximately)\s+.*$", "", s, flags=re.I)
    s = re.sub(r"\s+\((?:i\.e\.[,\s]|none\b)[^)]*\)\s*$", "", s, flags=re.I)
    s = " ".join(s.split())
    return s.strip()


def _try_parse_number(s: str) -> float | int | None:
    s = s.strip()
    if not s:
        return None
    try:
        val = float(s)
        if val.is_integer():
            return int(val)
        return val
    except ValueError:
        pass
    m = re.match(r"^(-?\d+)\s*/\s*(\d+)$", s)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den != 0:
            return num / den
    expr = s.replace("^", "**")
    expr = re.sub(r"\bsqrt\(([^)]+)\)", r"(\1)**0.5", expr)
    try:
        val = eval(expr)  # noqa: S307
        if isinstance(val, (int, float)):
            return val
    except Exception:
        pass
    return None


def _sympy_equal(s1: str, s2: str) -> bool:
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            parse_expr,
            standard_transformations,
            implicit_multiplication_application,
            convert_xor,
        )
    except ImportError:
        return False

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )

    def _prep(s: str) -> str:
        s = s.strip().replace("^", "**")
        s = re.sub(r"\bsqrt\(", "sqrt(", s)
        s = re.sub(r"\bC\(([^,]+),\s*([^)]+)\)", r"binomial(\1, \2)", s)
        s = re.sub(r"\b(\w+)!", r"factorial(\1)", s)
        return s

    try:
        e1 = parse_expr(_prep(s1), transformations=transformations)
        e2 = parse_expr(_prep(s2), transformations=transformations)
        return sympy.simplify(e1 - e2) == 0
    except Exception:
        return False


_CANONICAL_MAP = [
    (r"^no\s+(?:\w+\s+)*solutions?$", "no solutions"),
    (r"^no\s+(?:\w+\s+)*(?:possible\s+)?values?$", "no such values"),
    (r"^no such values$", "no such values"),
    (r"^0 pairs$", "0"),
    (r"^0 roots$", "0"),
    (r"^(.+?)\s+is the only possible value.*$", r"\1"),
    (r"^the limit exists and is equal to\s+(.+)$", r"\1"),
    (r"^the limit does not exist$", "limit does not exist"),
    (r"^at most 0\b.*$", "0"),
    (r"^exactly one\b.*$", "1"),
    (r"^(\d+)\s+values?$", r"\1"),
    (r"^(\d+)\s+inequalit(?:y|ies)$", r"\1"),
]


def _canonicalize(s: str) -> str:
    s_lower = s.strip().lower()
    for pattern, replacement in _CANONICAL_MAP:
        m = re.match(pattern, s_lower)
        if m:
            return m.expand(replacement)
    return s


def _try_match(gt_str: str, pred_str: str) -> dict | None:
    gt_canon = _canonicalize(gt_str)
    pred_canon = _canonicalize(pred_str)

    if gt_canon.lower() == pred_canon.lower():
        return {"correct": True, "match_type": "canonical"}

    gt_num = _try_parse_number(gt_canon)
    pred_num = _try_parse_number(pred_canon)
    if gt_num is not None and pred_num is not None:
        try:
            if isinstance(gt_num, int):
                correct = math.isfinite(pred_num) and round(pred_num) == gt_num
            else:
                correct = within_eps(pred_num, gt_num)
        except (OverflowError, ValueError):
            correct = False
        if correct:
            return {"correct": True, "match_type": "numeric"}

    if _sympy_equal(gt_canon, pred_canon):
        return {"correct": True, "match_type": "symbolic"}

    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

@register("champ")
def _eval_champ(raw_output: str, instance: dict) -> dict:
    eval_data = instance["eval_data"]
    gt_raw = str(eval_data["answer"]).strip()
    extracted = _champ_extract(strip_think_tags(raw_output))
    pred_raw = extracted.strip()

    gt_alternatives = _extract_alternatives(gt_raw)
    gt_norm = _normalize_str(gt_raw)
    pred_norm = _normalize_str(pred_raw)

    # Exact string match
    if gt_norm.lower() == pred_norm.lower():
        return {"extracted_answer": extracted, "correct": True, "match_type": "exact"}

    # Yes/No
    gt_lower = gt_norm.lower()
    pred_lower = pred_norm.lower()
    if gt_lower in ("yes", "no"):
        pred_yn = None
        if any(w in pred_lower for w in ("yes", "true")):
            pred_yn = "yes"
        elif any(w in pred_lower for w in ("no", "false")):
            pred_yn = "no"
        if pred_yn is not None:
            return {"extracted_answer": extracted, "correct": pred_yn == gt_lower, "match_type": "yes_no"}

    # Canonical, numeric, symbolic
    result = _try_match(gt_norm, pred_norm)
    if result is not None:
        result["extracted_answer"] = extracted
        return result

    # Alternative representations
    for alt in gt_alternatives:
        alt_norm = _normalize_str(alt)
        if alt_norm.lower() == pred_norm.lower():
            return {"extracted_answer": extracted, "correct": True, "match_type": "exact_alt"}
        result = _try_match(alt_norm, pred_norm)
        if result is not None:
            result["match_type"] += "_alt"
            result["extracted_answer"] = extracted
            return result

    return {"extracted_answer": extracted, "correct": False, "match_type": "none"}


# =========================== dispatch =======================================
def evaluate(raw_output: str, instance: dict) -> dict:
    """Route by ``instance["dataset"]``, as SR-Agents' dispatcher does."""
    return _REGISTRY[instance["dataset"]](raw_output, instance)
