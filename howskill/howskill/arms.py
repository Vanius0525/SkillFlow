"""Experiment arms: given an instance + its gold skill, produce the skill
payload (content + tools) that goes into the prompt.

An arm is a pure function of (gold_skill, all_skills, seed) -> list[skill dict]
so every arm is reproducible from its name and the seed alone.

Arms (see HOWSKILLWORK/PROTOCOL.md §2):

  no_skill        nothing injected                                (A0)
  gold            the full gold skill                             (A1)
  drop_M1..M5     leave-one-out content ablation                  (P3)
  m5_clinical     Example replaced by a TOOL_CALL syntax stub     (P3)
  no_tool         gold prose, but the executable tools removed    (P5)
  no_tool_no_M4   tools removed AND the tool-doc section removed  (P5)
  ctrl_neutral    another calculator's gold skill (length-matched)
  ctrl_shuffled   gold skill, sentence order destroyed
  ctrl_corrupted  gold skill, numeric constants perturbed
"""

from __future__ import annotations

import random
import re

from howskill.modules import (
    corrupted,
    render,
    render_m5_clinical,
    shuffled,
    split_modules,
)

ARMS = [
    "no_skill",
    "gold",
    "drop_M1", "drop_M2", "drop_M3", "drop_M4", "drop_M5",
    "m5_clinical",
    "no_tool", "no_tool_no_M4",
    "ctrl_neutral", "ctrl_shuffled", "ctrl_corrupted",
]

# Arms that are pure controls (never used to claim a content effect).
CONTROL_ARMS = {"ctrl_neutral", "ctrl_shuffled", "ctrl_corrupted"}


def _mk(skill: dict, content: str, tools=None) -> dict:
    out = dict(skill)
    out["content"] = content
    out["tools"] = tools if tools is not None else skill.get("tools")
    return out


def build(arm: str, gold: dict, neutral_for: dict | None = None,
          seed: int = 0) -> list[dict]:
    """Return the list of skill dicts to inject for ``arm``."""
    if arm == "no_skill":
        return []

    if arm == "ctrl_neutral":
        if neutral_for is None:
            raise ValueError("ctrl_neutral needs a paired neutral skill")
        return [neutral_for]

    mods = split_modules(gold["content"])

    if arm == "gold":
        return [gold]
    if arm.startswith("drop_"):
        return [_mk(gold, render(mods, drop={arm.split("_", 1)[1]}))]
    if arm == "m5_clinical":
        return [_mk(gold, render_m5_clinical(mods))]
    if arm == "no_tool":
        return [_mk(gold, gold["content"], tools=[])]
    if arm == "no_tool_no_M4":
        return [_mk(gold, render(mods, drop={"M4"}), tools=[])]
    if arm == "ctrl_shuffled":
        return [_mk(gold, shuffled(gold["content"], seed))]
    if arm == "ctrl_corrupted":
        return [_mk(gold, corrupted(gold["content"], seed))]

    raise ValueError(f"unknown arm: {arm}")


# ---------------------------------------------------------------------------
# Neutral-control pairing
# ---------------------------------------------------------------------------

_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")
# Calculator families that share machinery; a neutral skill must not come
# from the same family as the gold one, or it stops being neutral.
_FAMILY_HINTS = [
    ("bmi", "body mass", "ideal body weight", "adjusted body weight", "body surface"),
    ("creatinine", "crcl", "cockcroft", "gfr", "kidney", "renal"),
    ("sodium", "osmolality", "free water", "water deficit"),
    ("wells", "pe ", "dvt", "embolism", "thrombosis"),
    ("chads", "cha2ds2", "atrial fibrillation", "stroke risk"),
    ("apache", "sofa", "sepsis", "organ failure"),
    ("gestational", "pregnan", "due date", "menstrual"),
    ("opioid", "morphine", "mme"),
    ("anion gap", "bicarbonate", "acid"),
    ("glasgow", "coma", "consciousness"),
]


def _families(text: str) -> set[int]:
    t = text.lower()
    return {i for i, hints in enumerate(_FAMILY_HINTS) if any(h in t for h in hints)}


def _numbers(text: str) -> set[float]:
    out = set()
    for m in _NUM.finditer(text):
        try:
            out.add(float(m.group(1)))
        except ValueError:
            pass
    return out


def is_distinctive(v: float) -> bool:
    """Is this answer value one a model could plausibly *copy* out of an
    unrelated document, rather than one that occurs everywhere by chance?

    Small integers are the scores of the scoring-type calculators (CHA2DS2-VASc
    0-9, Glasgow 3-15, ...). They appear in every skill document's tables, so
    treating them as leaks excludes essentially every candidate and makes
    neutral pairing impossible. Only non-integers and large/precise values
    carry real copy risk.
    """
    if v != int(v):
        return True                      # has a decimal part
    return abs(v) >= 25                  # large enough to be non-generic


def _leakable(answers: set[float]) -> set[float]:
    return {v for v in answers if is_distinctive(v)}


def pair_neutrals(skills: list[dict], instances: list[dict],
                  seed: int = 0) -> tuple[dict, list[str]]:
    """Assign each gold skill a neutral partner: another calculator's gold
    skill, matched on length, from a different calculator family, and not
    containing any of the answer values of the instances it will be shown for.

    Returns ({skill_id: neutral_skill_id}, [warning, ...]).
    """
    rng = random.Random(seed)
    by_id = {s["skill_id"]: s for s in skills}

    # answers that must not appear verbatim in the neutral skill
    answers: dict[str, set[float]] = {}
    for inst in instances:
        sid = inst["skill_annotations"][0] if inst["skill_annotations"] else None
        if not sid:
            continue
        try:
            answers.setdefault(sid, set()).add(float(inst["eval_data"]["answer"]))
        except (TypeError, ValueError):
            pass  # date / gestational answers are not numeric

    fams = {s["skill_id"]: _families(s["name"] + " " + s["content"]) for s in skills}
    nums = {s["skill_id"]: _numbers(s["content"]) for s in skills}
    lens = {s["skill_id"]: len(s["content"]) for s in skills}

    mapping, warnings = {}, []
    for s in skills:
        sid = s["skill_id"]
        want = lens[sid]
        cands = []
        for t in skills:
            tid = t["skill_id"]
            if tid == sid:
                continue
            if fams[sid] and fams[tid] & fams[sid]:
                continue                       # same family -> not neutral
            leak = _leakable(answers.get(sid, set())) & nums[tid]
            if leak:
                continue                       # would leak an answer value
            cands.append((abs(lens[tid] - want), tid))
        if not cands:
            # relax the family constraint before giving up, but say so
            for t in skills:
                tid = t["skill_id"]
                if tid == sid:
                    continue
                if _leakable(answers.get(sid, set())) & nums[tid]:
                    continue
                cands.append((abs(lens[tid] - want), tid))
            warnings.append(f"{sid}: no cross-family neutral, relaxed family constraint")
        if not cands:
            warnings.append(f"{sid}: NO NEUTRAL FOUND")
            continue
        cands.sort()
        # pick randomly among the 5 closest by length, so the mapping is not
        # a deterministic function of length alone
        pool = cands[: min(5, len(cands))]
        mapping[sid] = by_id[rng.choice(pool)[1]]["skill_id"]

    return mapping, warnings


def audit_neutrals(mapping: dict, skills: list[dict],
                   instances: list[dict]) -> dict:
    """Leakage self-check for the neutral pairing (PROTOCOL.md P0-5)."""
    by_id = {s["skill_id"]: s for s in skills}
    fams = {s["skill_id"]: _families(s["name"] + " " + s["content"]) for s in skills}
    nums = {s["skill_id"]: _numbers(s["content"]) for s in skills}
    lens = {s["skill_id"]: len(s["content"]) for s in skills}

    answers: dict[str, set[float]] = {}
    for inst in instances:
        sid = inst["skill_annotations"][0] if inst["skill_annotations"] else None
        if not sid:
            continue
        try:
            answers.setdefault(sid, set()).add(float(inst["eval_data"]["answer"]))
        except (TypeError, ValueError):
            pass

    same_family, leaks, ratios = [], [], []
    for sid, nid in mapping.items():
        if fams[sid] and fams[nid] & fams[sid]:
            same_family.append((sid, nid))
        hit = _leakable(answers.get(sid, set())) & nums[nid]
        if hit:
            leaks.append((sid, nid, sorted(hit)[:5]))
        ratios.append(lens[nid] / max(1, lens[sid]))

    ratios.sort()
    return {
        "n": len(mapping),
        "same_family": same_family,
        "answer_leaks": leaks,
        "len_ratio_min": round(ratios[0], 3) if ratios else None,
        "len_ratio_median": round(ratios[len(ratios) // 2], 3) if ratios else None,
        "len_ratio_max": round(ratios[-1], 3) if ratios else None,
    }
