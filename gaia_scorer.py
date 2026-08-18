#!/usr/bin/env python3
"""
Official GAIA scorer.

A verbatim port of `scorer.py` from the GAIA leaderboard Space
(https://huggingface.co/spaces/gaia-benchmark/leaderboard), kept byte-faithful
on purpose. It is deliberately NOT "improved": the point of using the official
scorer is that a number produced here is comparable with every published GAIA
result, and any local tweak — a relative tolerance, a semantic judge, a
lenient article-stripper — silently forfeits that.

What it does:
  * gold parses as a number  -> strip $ % , and compare exactly as floats
  * gold contains , or ;     -> split into a list, compare element-wise
                                (numbers exactly, strings case/space-insensitively
                                but WITH punctuation retained)
  * otherwise                -> compare as strings, lowercased, whitespace and
                                punctuation removed

Note the asymmetry that trips people up: in list mode, punctuation is kept, so
"St. Petersburg" and "St Petersburg" differ. That is the official behaviour and
is preserved here.

The only deviations from upstream are that the diagnostic `print`s are dropped
(they would flood a 165-task run) and `numpy`/`json` are not imported, since
neither is used by the scoring functions.
"""

import re
import string
import warnings


def normalize_number_str(number_str: str) -> float:
    for char in ["$", "%", ","]:
        number_str = number_str.replace(char, "")
    try:
        return float(number_str)
    except ValueError:
        return float("inf")


def split_string(s: str, char_list: list[str] = [",", ";"]) -> list[str]:
    pattern = f"[{''.join(char_list)}]"
    return re.split(pattern, s)


def normalize_str(input_str, remove_punct=True) -> str:
    no_spaces = re.sub(r"\s", "", input_str)
    if remove_punct:
        translator = str.maketrans("", "", string.punctuation)
        return no_spaces.lower().translate(translator)
    else:
        return no_spaces.lower()


def is_float(element) -> bool:
    try:
        float(element)
        return True
    except (ValueError, TypeError):
        return False


def question_scorer(model_answer: str, ground_truth: str) -> bool:
    """True iff `model_answer` matches `ground_truth` under official GAIA rules."""
    if model_answer is None:
        model_answer = "None"

    if is_float(ground_truth):
        normalized_answer = normalize_number_str(model_answer)
        return normalized_answer == float(ground_truth)

    elif any(char in ground_truth for char in [",", ";"]):
        gt_elems = split_string(ground_truth)
        ma_elems = split_string(model_answer)

        if len(gt_elems) != len(ma_elems):
            warnings.warn(
                "Answer lists have different lengths, returning False.", UserWarning
            )
            return False

        comparisons = []
        for ma_elem, gt_elem in zip(ma_elems, gt_elems):
            if is_float(gt_elem):
                normalized_ma_elem = normalize_number_str(ma_elem)
                comparisons.append(normalized_ma_elem == float(gt_elem))
            else:
                comparisons.append(
                    normalize_str(ma_elem, remove_punct=False)
                    == normalize_str(gt_elem, remove_punct=False)
                )
        return all(comparisons)

    else:
        return normalize_str(model_answer) == normalize_str(ground_truth)
