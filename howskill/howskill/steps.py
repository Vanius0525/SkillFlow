"""Step-level readout: where in S1-S5 did the agent first go wrong?

Ground truth comes from the join to original MedCalc-Bench (P0-3):
  Relevant Entities      -> structured {name: value | [value, unit]}   (S2/S3)
  Ground Truth Explanation -> step-by-step derivation                  (S3/S4)
  answer + limits        -> final                                      (S5)

Steps:
  S1 calculator   did it work on the right calculator/formula at all
  S2 extraction   did it pull the right variable values out of the note
  S3 units        did it normalise units correctly
  S4 computation  did it apply the formula / branch correctly
  S5 format       right value, wrong presentation
  no_answer       never emitted an answer at all (loop hit the round cap)

DESIGN RULE: be conservative. If a step's evidence cannot be located in the
trajectory, mark it 'unparsed' — never guess. PROTOCOL.md gates the whole
step-level readout on >=80% parse rate; a parser that guesses would pass the
gate while producing noise.

The first calibration against real trajectories (P0-4, 50 P1-Oracle failures
reviewed) agreed with only 14/50 labels, and every rule that was wrong was
wrong in the direction of over-claiming. What changed as a result:

  * S5 was read off `transcript`, which contains the TOOL_RESULT lines — so an
    episode whose tool computed the right value was labelled "computed it,
    misreported it" even when the agent never used that value and never
    answered at all. S5 now reads the agent's OWN text, and episodes that
    never answered get their own label instead of being scattered across S5.
  * S5 also fired on coincidence: a score of 3 collides with "3 cm" anywhere
    in the text. It is now tested only for answers with discriminative power
    — the same lesson the neutral pairing hit in P0 (小整数没有区分度).
  * Boolean criteria were compared as the numbers 0/1 (bool is an int
    subclass), which is not a test of anything. They are now not checkable,
    which makes the pure-score calculators unparsed rather than mislabelled.
  * "190,000" parsed as 190 and 000, so a value that was present read as
    missing. Thousands separators are now understood.
  * S1 required the calculator's name in the text; agents write "GBS" or "the
    male formula". S1 now needs positive evidence of a DIFFERENT calculator.
  * S3 required half of the GT's unit-conversion chain to appear, so an agent
    that converted correctly by a shorter route was marked as a unit failure.
    It now compares the converted RESULT only.
"""

from __future__ import annotations

import ast
import re

STEPS = ["S1", "S2", "S3", "S4", "S5"]
LABELS = ["none"] + STEPS + ["no_answer", "unparsed"]

# Thousands separators first, so "190,000" is one number and not two.
_NUM_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
# The GT explanation states the result of a conversion as "... converts to X"
# or "... which is X". The intermediate mol/g/mg steps are not required: an
# agent may divide by 88.42 in one go and still be right.
_CONV_RE = re.compile(r"(?:converts?\s+to|which\s+is)\s+(-?\d[\d,]*(?:\.\d+)?)", re.I)


def parse_entities(raw: str) -> dict:
    """Relevant Entities is a python-literal dict string."""
    try:
        v = ast.literal_eval(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def entity_values(entities: dict) -> dict[str, tuple[float | None, str | None]]:
    """Normalise to {name: (numeric_value_or_None, unit_or_None)}.

    Booleans are deliberately NOT numeric here. They are criteria flags, and
    `bool` being a subclass of `int` had them compared as the literals 0 and 1
    — a test every trajectory passes or fails by accident.
    """
    out = {}
    for k, v in entities.items():
        if isinstance(v, bool):
            out[k] = (None, None)
        elif isinstance(v, (list, tuple)) and len(v) == 2:
            val, unit = v
            try:
                out[k] = (float(val), str(unit))
            except (TypeError, ValueError):
                out[k] = (None, str(unit))
        elif isinstance(v, (int, float)):
            out[k] = (float(v), None)
        else:
            out[k] = (None, None)
    return out


def date_entities(entities: dict) -> dict[str, str]:
    """String entities that are literal dates, which can be matched exactly.

    Prose strings ('Highly suspicious') are excluded on purpose: matching them
    would mean deciding whether "> 3x the upper limit" says the same thing as
    "greater than three times normal limit", and a parser that guesses at that
    is worse than one that abstains.
    """
    return {k: v for k, v in entities.items()
            if isinstance(v, str) and _DATE_RE.match(v.strip())}


def _numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text or ""):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def _close(a: float, b: float, rel: float = 0.01) -> bool:
    return abs(a - b) <= max(abs(b) * rel, 1e-9)


def _mentions(text: str, literal: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(literal) + r"(?!\w)",
                     text or "", re.I) is not None


def discriminative(answer) -> bool:
    """Is this answer distinctive enough to be recognised in free text?

    A score of 3 collides with "3 cm", "3 days", a tool argument, a step
    number. Only a non-integer or a large integer identifies itself.
    """
    try:
        v = float(str(answer).strip())
    except (TypeError, ValueError):
        return False
    return v != int(v) or abs(v) > 20


def check_extraction(traj_text: str, entities: dict) -> dict:
    """S2: does the trajectory mention each ground-truth entity value?

    This is deliberately weak-but-honest: it asks whether the correct value
    appears anywhere in the agent's own text (or in its tool-call arguments),
    not whether the agent 'understood' it. A value that never appears was
    certainly not extracted; a value that appears may still have been used
    wrongly, which is what S4 is for.

    Boolean criteria and prose-valued entities are counted as unknown, so a
    calculator whose inputs are all yes/no answers yields checkable == 0 and
    the episode is reported unparsed rather than labelled from noise.
    """
    ev = entity_values(entities)
    dates = date_entities(entities)
    nums = _numbers_in(traj_text)
    found, missing, unknown = [], [], []
    for name, (val, _unit) in ev.items():
        if name in dates:
            (found if _mentions(traj_text, dates[name]) else missing).append(name)
            continue
        if val is None:
            unknown.append(name)
            continue
        if any(_close(n, val) for n in nums):
            found.append(name)
        else:
            missing.append(name)
    checkable = len(found) + len(missing)
    return {
        "found": found, "missing": missing, "unknown": unknown,
        "checkable": checkable,
        "ok": (checkable > 0 and not missing),
        "parsed": checkable > 0,
    }


def check_units(traj_text: str, entities: dict, explanation: str) -> dict:
    """S3: only meaningful for instances whose GT explanation actually does a
    conversion. Otherwise returns parsed=False so it is excluded, rather than
    counted as a pass — see P0-FINDINGS §2.4 (units exist in only 15/55).

    Only the RESULT of each conversion is required to appear. The GT walks
    µmol -> mol -> g -> mg -> per dL; an agent that divides by 88.42 in one
    step lands on the same number and is not a unit failure.
    """
    expl = explanation or ""
    if not re.search(r"which is|convert", expl, re.I):
        return {"applicable": False, "parsed": False, "ok": None}
    targets = []
    for m in _CONV_RE.finditer(expl):
        try:
            targets.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    if not targets:
        return {"applicable": True, "parsed": False, "ok": None}
    nums = _numbers_in(traj_text)
    hit = [t for t in targets if any(_close(n, t) for n in nums)]
    return {"applicable": True, "parsed": True,
            "ok": len(hit) == len(targets),
            "n_targets": len(targets), "n_hit": len(hit)}


def _tool_results(traj: dict) -> str:
    return " ".join(str(t.get("tool_result"))
                    for t in (traj.get("turns") or [])
                    if t.get("tool_result") is not None)


def first_failure(traj: dict, instance: dict, gt: dict | None,
                  graded: dict, calculator_name: str | None = None,
                  calculator_names: list[str] | None = None) -> dict:
    """Classify the first step that went wrong.

    Returns {'fail_step': 'S1'|..|'S5'|'no_answer'|'none'|'unparsed', ...}.

    ``calculator_name`` is what the S1 test needs and the step-GT join does not
    carry: `stepgt.json` has `skill_id`, and the name lives in
    `medcalc_skills.json`. Callers must look it up and pass it — without it the
    S1 branch below can never fire. ``calculator_names`` is every calculator's
    name, needed because S1 now requires evidence that the agent worked on a
    different calculator, not merely that it failed to name this one.
    """
    own = traj.get("model_output") or ""
    text = own or traj.get("transcript") or ""
    detail: dict = {}

    if graded.get("correct"):
        return {"fail_step": "none", "detail": detail}

    if gt is None:
        return {"fail_step": "unparsed", "detail": {"reason": "no step GT"}}

    entities = parse_entities(gt.get("relevant_entities") or "")
    if not entities:
        return {"fail_step": "unparsed", "detail": {"reason": "entities unparsed"}}

    gt_ans = instance["eval_data"]["answer"]

    # The agent never answered: the loop ran out of rounds, or the reply was
    # empty. Scoring still produced a number (upstream extraction falls back to
    # the last number in the text, which is typically a tool-call argument),
    # so this looks like a wrong answer and is not one.
    never_answered = (traj.get("stop_reason") in ("max_rounds", "empty_response")
                      or "ANSWER:" not in own)
    if never_answered:
        detail["stop_reason"] = traj.get("stop_reason")
        if discriminative(gt_ans):
            detail["computed_in_tool"] = any(
                _close(n, float(str(gt_ans).strip()), 0.001)
                for n in _numbers_in(_tool_results(traj)))
        return {"fail_step": "no_answer", "detail": detail}

    # S5: right number, wrong presentation. Read the agent's own text only —
    # a TOOL_RESULT carrying the right value proves the tool worked, not that
    # the agent had the answer. And only for answers that identify themselves.
    if discriminative(gt_ans):
        ent_nums = [v for v, _ in entity_values(entities).values() if v is not None]
        tail = own[-400:]
        hits = [n for n in _numbers_in(tail)
                if _close(n, float(str(gt_ans).strip()), 0.001)
                and not any(_close(n, e, 1e-9) for e in ent_nums)]
        if hits:
            detail["note"] = "correct value present in the agent's own text"
            return {"fail_step": "S5", "detail": detail}
    else:
        detail["s5_skipped"] = "answer not discriminative"

    ext = check_extraction(text, entities)
    detail["extraction"] = ext
    if ext["parsed"] and not ext["ok"]:
        return {"fail_step": "S2", "detail": detail}

    uni = check_units(text, entities, gt.get("gt_explanation") or "")
    detail["units"] = uni
    if uni["parsed"] and uni["ok"] is False:
        return {"fail_step": "S3", "detail": detail}

    if not ext["parsed"]:
        return {"fail_step": "unparsed", "detail": detail}

    # S1 needs positive evidence that a different calculator was used. Absence
    # of this calculator's name is not evidence: agents write "GBS" for
    # Glasgow-Blatchford and "the male formula" for Framingham.
    mine = (calculator_name or gt.get("calculator_name") or "").lower()
    if mine and calculator_names:
        low = text.lower()
        if not any(_mentions(low, w) for w in mine.split() if len(w) >= 4):
            others = [n for n in calculator_names
                      if n and n.lower() != mine
                      and any(_mentions(low, w) for w in n.lower().split()
                              if len(w) >= 5)]
            if others:
                detail["other_calculator"] = others[:3]
                return {"fail_step": "S1", "detail": detail}

    return {"fail_step": "S4", "detail": detail}


def transition_matrix(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """Failure-mode transition matrix between two arms, keyed by instance_id.

    rows_* are [{'instance_id':..., 'fail_step':...}, ...]. Cells are
    (arm_a step -> arm_b step). The (none -> S_k) cells are the negative
    effects: instances the skill broke.
    """
    a = {r["instance_id"]: r["fail_step"] for r in rows_a}
    b = {r["instance_id"]: r["fail_step"] for r in rows_b}
    mat = {x: {y: 0 for y in LABELS} for x in LABELS}
    for iid, sa in a.items():
        sb = b.get(iid)
        if sb is None:
            continue
        mat[sa][sb] += 1
    return mat
