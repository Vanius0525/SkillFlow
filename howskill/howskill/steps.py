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

DESIGN RULE: be conservative. If a step's evidence cannot be located in the
trajectory, mark it 'unparsed' — never guess. PROTOCOL.md gates the whole
step-level readout on >=80% parse rate; a parser that guesses would pass the
gate while producing noise.
"""

from __future__ import annotations

import ast
import re

STEPS = ["S1", "S2", "S3", "S4", "S5"]

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_entities(raw: str) -> dict:
    """Relevant Entities is a python-literal dict string."""
    try:
        v = ast.literal_eval(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def entity_values(entities: dict) -> dict[str, tuple[float | None, str | None]]:
    """Normalise to {name: (numeric_value_or_None, unit_or_None)}."""
    out = {}
    for k, v in entities.items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
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


def _numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text or ""):
        try:
            out.append(float(m.group(0)))
        except ValueError:
            pass
    return out


def _close(a: float, b: float, rel: float = 0.01) -> bool:
    return abs(a - b) <= max(abs(b) * rel, 1e-9)


def check_extraction(traj_text: str, entities: dict) -> dict:
    """S2: does the trajectory mention each ground-truth entity value?

    This is deliberately weak-but-honest: it asks whether the correct value
    appears anywhere in the agent's own text (or in its tool-call arguments),
    not whether the agent 'understood' it. A value that never appears was
    certainly not extracted; a value that appears may still have been used
    wrongly, which is what S4 is for.
    """
    ev = entity_values(entities)
    nums = _numbers_in(traj_text)
    found, missing, unknown = [], [], []
    for name, (val, _unit) in ev.items():
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
    """
    expl = explanation or ""
    if not re.search(r"which is|convert", expl, re.I):
        return {"applicable": False, "parsed": False, "ok": None}
    # converted values appear in the explanation as "... = <value> <unit>"
    targets = []
    for m in re.finditer(r"=\s*(-?\d+(?:\.\d+)?)\s*([a-zA-Z/%²]+)", expl):
        try:
            targets.append(float(m.group(1)))
        except ValueError:
            pass
    if not targets:
        return {"applicable": True, "parsed": False, "ok": None}
    nums = _numbers_in(traj_text)
    hit = [t for t in targets if any(_close(n, t) for n in nums)]
    return {"applicable": True, "parsed": True,
            "ok": len(hit) >= max(1, len(targets) // 2),
            "n_targets": len(targets), "n_hit": len(hit)}


def first_failure(traj: dict, instance: dict, gt: dict | None,
                  graded: dict, calculator_name: str | None = None) -> dict:
    """Classify the first step that went wrong.

    Returns {'fail_step': 'S1'|..|'S5'|'none'|'unparsed', 'detail': {...}}.

    ``calculator_name`` is what the S1 test needs and the step-GT join does not
    carry: `stepgt.json` has `skill_id`, and the name lives in
    `medcalc_skills.json`. Callers must look it up and pass it — without it the
    S1 branch below can never fire and every wrong-calculator failure is
    silently reported as S4.
    """
    text = traj.get("transcript") or traj.get("model_output") or ""
    detail: dict = {}

    if graded.get("correct"):
        return {"fail_step": "none", "detail": detail}

    if gt is None:
        return {"fail_step": "unparsed", "detail": {"reason": "no step GT"}}

    entities = parse_entities(gt.get("relevant_entities") or "")
    if not entities:
        return {"fail_step": "unparsed", "detail": {"reason": "entities unparsed"}}

    # S5: right number, wrong presentation -> the extracted answer is wrong but
    # the correct value does appear in the agent's text
    try:
        gt_ans = float(str(instance["eval_data"]["answer"]).strip())
        if any(_close(n, gt_ans, 0.001) for n in _numbers_in(text)):
            detail["note"] = "correct value present but not the reported answer"
            return {"fail_step": "S5", "detail": detail}
    except (TypeError, ValueError):
        pass

    ext = check_extraction(text, entities)
    detail["extraction"] = ext
    if ext["parsed"] and not ext["ok"]:
        return {"fail_step": "S2", "detail": detail}

    uni = check_units(text, entities, gt.get("gt_explanation") or "")
    detail["units"] = uni
    if uni["parsed"] and uni["ok"] is False:
        return {"fail_step": "S3", "detail": detail}

    # S1 vs S4: if the agent never invoked the right machinery at all we call
    # it S1, otherwise the inputs were right and the arithmetic was not.
    if not ext["parsed"]:
        return {"fail_step": "unparsed", "detail": detail}

    calc_name = (calculator_name or gt.get("calculator_name") or "").lower()
    if calc_name and calc_name.split()[0] not in text.lower() \
            and not traj.get("n_tool_calls"):
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
    keys = ["none"] + STEPS + ["unparsed"]
    mat = {x: {y: 0 for y in keys} for x in keys}
    for iid, sa in a.items():
        sb = b.get(iid)
        if sb is None:
            continue
        mat[sa][sb] += 1
    return mat
