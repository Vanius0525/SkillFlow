"""
AssistantBench answer scorer.

Implements the type-aware "answer F1" used by the AssistantBench paper
(Yoran et al., 2024). Adapted from the official scoring logic at
https://github.com/oriyor/assistant-bench.

Answer types handled:
  - number  : min/max ratio (0 if signs differ; exact 0 case handled)
  - string  : token-level F1 (lowercased, stripped of punctuation)
  - list    : best-matching pairwise F1 over items (each item scored recursively)
  - dict    : per-key F1 over values (each value scored recursively)

Both gold and predicted answers may be raw strings; we attempt to parse them
into the same structural type before comparing.
"""

from __future__ import annotations

import json
import re
import string
from collections import Counter

_NUM_RE = re.compile(r"^[\-+]?\d[\d,]*\.?\d*%?$")


def _strip_punct(s: str) -> str:
    return s.translate(str.maketrans("", "", string.punctuation))


def _normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = _strip_punct(s)
    s = re.sub(r"\s+", " ", s)
    return s


def _try_number(s):
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        return None
    t = s.strip().replace(",", "")
    pct = t.endswith("%")
    if pct:
        t = t[:-1]
    try:
        v = float(t)
        if pct:
            v /= 100.0
        return v
    except ValueError:
        return None


def _parse_answer(raw):
    """Parse a raw answer string into number / list / dict / string."""
    if raw is None:
        return ""
    if isinstance(raw, (int, float, list, dict)):
        return raw
    s = str(raw).strip()
    if not s:
        return ""

    n = _try_number(s)
    if n is not None and _NUM_RE.match(s.replace(" ", "")):
        return n

    # JSON list / dict
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
        try:
            return json.loads(s)
        except Exception:
            pass

    # Newline- or comma-separated list
    if "\n" in s:
        items = [x.strip() for x in s.split("\n") if x.strip()]
        if len(items) > 1:
            return [_parse_answer(x) for x in items]

    return s


def _score_number(p, g) -> float:
    p = float(p); g = float(g)
    if p == 0 and g == 0:
        return 1.0
    if p == 0 or g == 0:
        return 0.0
    if (p < 0) != (g < 0):
        return 0.0
    p, g = abs(p), abs(g)
    return min(p, g) / max(p, g)


def _score_string(p, g) -> float:
    p_toks = _normalize_text(str(p)).split()
    g_toks = _normalize_text(str(g)).split()
    if not p_toks and not g_toks:
        return 1.0
    if not p_toks or not g_toks:
        return 0.0
    common = Counter(p_toks) & Counter(g_toks)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(p_toks)
    recall = overlap / len(g_toks)
    return 2 * precision * recall / (precision + recall)


def _score_list(pred_list, gold_list) -> float:
    if not pred_list and not gold_list:
        return 1.0
    if not pred_list or not gold_list:
        return 0.0
    # Greedy best-match: pair each gold item with the pred item maximizing score.
    used = set()
    total = 0.0
    for g in gold_list:
        best = 0.0
        best_i = -1
        for i, p in enumerate(pred_list):
            if i in used:
                continue
            s = _score_pair(p, g)
            if s > best:
                best = s; best_i = i
        if best_i >= 0:
            used.add(best_i)
        total += best
    recall = total / len(gold_list)
    precision = total / len(pred_list)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _score_dict(pred_dict, gold_dict) -> float:
    if not pred_dict and not gold_dict:
        return 1.0
    if not pred_dict or not gold_dict:
        return 0.0
    keys = set(gold_dict) | set(pred_dict)
    total = 0.0
    for k in keys:
        if k in pred_dict and k in gold_dict:
            total += _score_pair(pred_dict[k], gold_dict[k])
    return total / len(keys)


def _score_pair(p, g) -> float:
    pp = _parse_answer(p)
    gg = _parse_answer(g)
    if isinstance(gg, dict) and isinstance(pp, dict):
        return _score_dict(pp, gg)
    if isinstance(gg, list) and isinstance(pp, list):
        return _score_list(pp, gg)
    if isinstance(gg, list):
        return _score_list(pp if isinstance(pp, list) else [pp], gg)
    if isinstance(pp, list):
        return _score_list(pp, [gg])
    pn = _try_number(pp); gn = _try_number(gg)
    if pn is not None and gn is not None:
        return _score_number(pn, gn)
    return _score_string(pp, gg)


def question_scorer(predicted: str, gold: str) -> float:
    """Return a soft score in [0, 1] for one (predicted, gold) pair."""
    if predicted is None or gold is None:
        return 0.0
    if not str(predicted).strip() or not str(gold).strip():
        return 0.0
    return float(_score_pair(predicted, gold))


def is_correct_assistantbench(predicted: str, gold: str, threshold: float = 0.5) -> bool:
    """Hard accuracy at a soft-score threshold (paper uses soft score directly)."""
    return question_scorer(predicted, gold) >= threshold
