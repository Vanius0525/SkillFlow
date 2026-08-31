"""Offline selftest — no GPU, no vLLM server.

Everything here must pass before shipping to the 4090. Run:

    python -m howskill.selftest
"""

from __future__ import annotations

import json
import os
import sys

from howskill import arms as arms_mod
from howskill.grade import evaluate, extract, score
from howskill.llm import MockClient
from howskill.loop import make_prefix, run_episode
from howskill.modules import example_syntax_only, split_modules
from howskill.prompts import build_prompt
from howskill.steps import (check_extraction, check_units, entity_values,
                            first_failure, parse_entities,
                            transition_matrix)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

FAILS: list[str] = []


def check(name, cond, extra=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


def main():
    skills = json.load(open(f"{DATA}/medcalc_skills.json", encoding="utf-8"))
    instances = json.load(open(f"{DATA}/medcalcbench.json", encoding="utf-8"))
    stepgt = {g["instance_id"]: g
              for g in json.load(open(f"{DATA}/stepgt.json", encoding="utf-8"))}
    pairs = json.load(open(f"{DATA}/neutral_pairs.json", encoding="utf-8"))
    by_id = {s["skill_id"]: s for s in skills}

    print("\n== data ==")
    check("55 skills", len(skills) == 55, f"got {len(skills)}")
    check("1100 instances", len(instances) == 1100, f"got {len(instances)}")
    check("1098 step-GT", len(stepgt) == 1098, f"got {len(stepgt)}")
    check("55 neutral pairs", len(pairs) == 55, f"got {len(pairs)}")
    check("all skills have executable tools",
          all(s.get("tools") and all(t.get("implementation") for t in s["tools"])
              for s in skills))

    print("\n== modules ==")
    univ = {"M2": 0, "M3": 0, "M4": 0, "M5": 0}
    for s in skills:
        m = split_modules(s["content"])
        for k in univ:
            univ[k] += bool(m.get(k))
    check("M2-M5 present in all 55", all(v == 55 for v in univ.values()), str(univ))
    check("M5 syntax stub constructible for all 55",
          all(example_syntax_only(split_modules(s["content"])) is not None
              for s in skills))

    print("\n== arms ==")
    gold = by_id["medcalcbench_000"]
    neutral = by_id[pairs["medcalcbench_000"]]
    lens = {}
    for arm in arms_mod.ARMS:
        payload = arms_mod.build(arm, gold, neutral_for=neutral, seed=0)
        lens[arm] = len(payload[0]["content"]) if payload else 0
    check("no_skill is empty", lens["no_skill"] == 0)
    check("every drop_* is shorter than gold",
          all(lens[f"drop_M{i}"] < lens["gold"] for i in range(1, 6)),
          str({k: v for k, v in lens.items() if k.startswith("drop")}))
    check("shuffled preserves length approximately",
          abs(lens["ctrl_shuffled"] - lens["gold"]) < 0.15 * lens["gold"],
          f"{lens['ctrl_shuffled']} vs {lens['gold']}")
    check("corrupted preserves length approximately",
          abs(lens["ctrl_corrupted"] - lens["gold"]) < 0.15 * lens["gold"],
          f"{lens['ctrl_corrupted']} vs {lens['gold']}")
    check("corrupted actually changes content",
          arms_mod.build("ctrl_corrupted", gold, seed=0)[0]["content"] != gold["content"])
    check("no_tool strips tools",
          arms_mod.build("no_tool", gold, seed=0)[0]["tools"] == [])
    check("m5_clinical shorter than gold but keeps TOOL_CALL",
          lens["m5_clinical"] < lens["gold"]
          and "TOOL_CALL:" in arms_mod.build("m5_clinical", gold, seed=0)[0]["content"])

    print("\n== prompts ==")
    inst = instances[0]
    sysmsg, user = build_prompt(inst, skills=[gold], tool_protocol=True)
    check("skill injected in upstream format", user.startswith("Relevant Skill:\n"))
    check("ANSWER: instruction present", "ANSWER: <your answer>" in user)
    check("question preserved verbatim", inst["question"] in user)

    print("\n== grading (upstream parity) ==")
    dec = {"answer": "25.2381", "calculator_id": 2, "output_type": "decimal",
           "lower_limit": "23.97619", "upper_limit": "26.50001"}
    check("decimal inside band", score("25.0", dec)["correct"])
    check("decimal outside band", not score("30.0", dec)["correct"])
    integ = {"answer": "4", "calculator_id": 4, "output_type": "integer"}
    check("integer rounds", score("4.4", integ)["correct"])
    check("integer wrong", not score("6", integ)["correct"])
    date = {"answer": "03/14/2023", "calculator_id": 13, "output_type": "date"}
    check("date match", score("03/14/2023", date)["correct"])
    check("ANSWER: line wins over stray numbers",
          extract("blah 999\nSome text 123\nANSWER: 25.2\n", dec) == "25.2")
    check("think tags stripped",
          evaluate("<think>the answer is 999</think>\nANSWER: 25.2",
                   {"eval_data": dec})["correct"])
    check("falls back to last number",
          extract("the result comes to 25.2", dec) == "25.2")

    print("\n== loop ==")
    tools = gold["tools"]
    call = f"TOOL_CALL: {tools[0]['name']}(" + ", ".join(
        f"{k}=1" for k in tools[0]["parameters"]) + ")"
    mock = MockClient([f"Let me compute.\n{call}", "ANSWER: 3"])
    traj = run_episode(mock, sysmsg, user, user, tools)
    check("tool executed", traj.turns and traj.turns[0]["tool_call"] is not None,
          str(traj.turns[0].get("tool_result") if traj.turns else None))
    check("2 turns recorded", len(traj.turns) == 2, f"got {len(traj.turns)}")
    check("TOOL_RESULT excluded from model_output",
          "TOOL_RESULT" not in traj.model_output)
    check("TOOL_RESULT present in transcript", "TOOL_RESULT" in traj.transcript)
    check("stop_reason answered", traj.stop_reason == "answered")

    print("\n== skill schedule (P4) ==")
    m2 = MockClient([f"go\n{call}", "ANSWER: 3"])
    t2 = run_episode(m2, sysmsg, user, "PLAIN", tools, skill_schedule="first")
    check("schedule=first: skill visible turn 0",
          "Relevant Skill:" in m2.seen[0][1]["content"])
    check("schedule=first: skill gone by turn 1",
          "Relevant Skill:" not in m2.seen[1][1]["content"])
    m3 = MockClient([f"go\n{call}", "ANSWER: 3"])
    run_episode(m3, sysmsg, user, "PLAIN", tools, skill_schedule="late")
    check("schedule=late: absent turn 0",
          "Relevant Skill:" not in m3.seen[0][1]["content"])
    check("schedule=late: present on turn 1",
          "Relevant Skill:" in m3.seen[1][1]["content"])
    # An agent that cannot see the skill does not know the tool names, and the
    # measured no_skill arm calls no tools at all. Keying 'late' on the first
    # tool call would therefore never show the skill to exactly the agents the
    # arm is about -- 'late' is keyed on the turn, and this pins the difference.
    m4 = MockClient(["ANSWER: 7", "ANSWER: 3"])
    t4 = run_episode(m4, sysmsg, user, "PLAIN", tools, skill_schedule="late")
    check("schedule=late: answering does not end the episode",
          len(m4.seen) == 2, f"{len(m4.seen)} calls")
    check("schedule=late: skill shown on the revise turn",
          len(m4.seen) > 1 and "Relevant Skill:" in m4.seen[1][1]["content"])
    check("schedule=late: the revised answer is the one graded",
          extract(t4.model_output, dec) == "3", extract(t4.model_output, dec))
    m5 = MockClient(["ANSWER: 7", "ANSWER: 3"])
    run_episode(m5, sysmsg, user, "PLAIN", tools, skill_schedule="late-tool")
    check("schedule=late-tool: no revise turn, ends on the answer",
          len(m5.seen) == 1, f"{len(m5.seen)} calls")

    print("\n== forced prefix / graft (P7) ==")
    donor = MockClient([f"donor reasoning\n{call}", "ANSWER: 3"])
    dt = run_episode(donor, sysmsg, user, user, tools)
    prefix = make_prefix(dt.to_dict(), upto_turn=1)
    check("prefix is assistant+user pair", len(prefix) == 2
          and prefix[0]["role"] == "assistant" and prefix[1]["role"] == "user")
    recv = MockClient(["ANSWER: 3"])
    rt = run_episode(recv, sysmsg, "PLAIN", "PLAIN", tools, forced_prefix=prefix)
    check("prefix installed into context", any(
        m.get("content", "").startswith("TOOL_RESULT:") for m in recv.seen[0]))
    check("forced_turns recorded", rt.forced_turns == 2, str(rt.forced_turns))

    print("\n== subset (P3) ==")
    from howskill.run import restrict
    r = restrict(instances, "2,5,9")
    check("--calculators takes an id list",
          sorted({x["eval_data"]["calculator_id"] for x in r}) == [2, 5, 9],
          f"{len(r)} instances")
    # stepgt.json stores calculator_id as a string and the instances store it
    # as an int; comparing them directly makes every calculator ineligible and
    # the subset picker reports the task as unusable.
    gt_ids = {g["calculator_id"] for g in stepgt.values()}
    inst_ids = {i["eval_data"]["calculator_id"] for i in instances}
    check("calculator_id types differ across the two files (must be coerced)",
          bool(gt_ids) and bool(inst_ids) and not (gt_ids & inst_ids),
          f"{type(next(iter(gt_ids))).__name__} vs "
          f"{type(next(iter(inst_ids))).__name__}")

    print("\n== steps ==")
    g = stepgt[instances[0]["instance_id"]] if instances[0]["instance_id"] in stepgt \
        else next(iter(stepgt.values()))
    ents = parse_entities(g["relevant_entities"])
    check("entities parse to non-empty dict", bool(ents), str(list(ents)[:4]))
    n_parsed = sum(1 for v in stepgt.values() if parse_entities(v["relevant_entities"]))
    check("entities parse for >=95% of step-GT",
          n_parsed >= 0.95 * len(stepgt), f"{n_parsed}/{len(stepgt)}")
    fr = first_failure({"model_output": "ANSWER: 3", "n_tool_calls": 1},
                       instances[0], g, {"correct": True})
    check("correct -> fail_step none", fr["fail_step"] == "none")
    # S1 needs the calculator name, which stepgt.json does not carry — it must
    # come from medcalc_skills.json via skill_id. Without it the branch is dead
    # and every wrong-calculator failure is reported as S4, silently.
    check("stepgt has no calculator_name (name must come from skills)",
          "calculator_name" not in g)
    # Needs an instance with no unit conversion in its GT explanation: S3 is
    # tested before S1, so a converting instance would stop there first.
    by_iid = {i["instance_id"]: i for i in instances}
    g1 = next((v for v in stepgt.values()
               if "convert" not in (v.get("gt_explanation") or "").lower()
               and "which is" not in (v.get("gt_explanation") or "").lower()
               and v["instance_id"] in by_iid
               and parse_entities(v["relevant_entities"])), None)
    if g1:
        i1 = by_iid[g1["instance_id"]]
        vals = [v[0] for v in entity_values(parse_entities(
            g1["relevant_entities"])).values() if v[0] is not None]
        seen = " ".join(str(v) for v in vals) + "\nANSWER: -12345"
        fr = first_failure({"model_output": seen, "n_tool_calls": 0},
                           i1, g1, {"correct": False},
                           calculator_name="Zzzznonexistent Score",
                           calculator_names=["Zzzznonexistent Score",
                                             "Wells' Criteria for DVT"])
        check("no S1 without evidence of another calculator",
              fr["fail_step"] != "S1", fr["fail_step"])
        fr = first_failure({"model_output": seen + " using Wells' Criteria",
                            "n_tool_calls": 0},
                           i1, g1, {"correct": False},
                           calculator_name="Zzzznonexistent Score",
                           calculator_names=["Zzzznonexistent Score",
                                             "Wells' Criteria for DVT"])
        check("S1 when another calculator is named",
              fr["fail_step"] == "S1", fr["fail_step"])

    # The four rules the P0-4 calibration broke. Each of these was a real
    # mislabel in the first 50 reviewed, not a hypothetical.
    inst5 = {"eval_data": dict(dec)}                       # answer 25.2381
    gt5 = {"relevant_entities": "{'weight': [38.0, 'kg']}", "gt_explanation": ""}
    check("a tool result is not evidence the agent had the answer",
          first_failure({"model_output": "TOOL_CALL: f(weight_kg=38)",
                         "transcript": "TOOL_CALL: f(weight_kg=38)\n"
                                       "TOOL_RESULT: 25.2381\n",
                         "turns": [{"tool_result": "25.2381"}],
                         "stop_reason": "max_rounds"},
                        inst5, gt5, {"correct": False})["fail_step"]
          == "no_answer")
    check("no_answer records that the tool had computed it",
          first_failure({"model_output": "TOOL_CALL: f(weight_kg=38)",
                         "turns": [{"tool_result": "25.2381"}],
                         "stop_reason": "max_rounds"},
                        inst5, gt5, {"correct": False}
                        )["detail"].get("computed_in_tool") is True)
    small = {"eval_data": {"answer": "3", "calculator_id": 16,
                           "output_type": "integer"}}
    check("a small integer answer is not discriminative",
          first_failure({"model_output": "bedridden > 3 days\nANSWER: 4",
                         "n_tool_calls": 1},
                        small, gt5, {"correct": False})["fail_step"] != "S5")
    check("thousands separators are one number",
          check_extraction("platelets 190,000 /uL",
                           {"Platelet count": [190000, "uL"]})["ok"])
    check("boolean criteria are not checkable as 0/1",
          check_extraction("nothing here",
                           {"Prior DVT": False, "Stroke": True})["checkable"] == 0)
    check("a date entity is matched literally",
          check_extraction("LMP = 11/18/2009",
                           {"Last menstrual date": "11/18/2009"})["ok"])
    check("a shorter but correct conversion is not a unit failure",
          check_units("creatinine 6.288 mg/dL", {},
                      "555.8 umol/L ... converts to 6.335 mg/dL")["ok"])
    check("an unconverted value is a unit failure",
          check_units("albumin 31 g/L", {},
                      "31.0 g/L ... converts to 3.1 g/dL")["ok"] is False)
    tm = transition_matrix(
        [{"instance_id": "a", "fail_step": "S2"}],
        [{"instance_id": "a", "fail_step": "none"}])
    check("transition matrix counts (S2->none)", tm["S2"]["none"] == 1)
    tm2 = transition_matrix(
        [{"instance_id": "a", "fail_step": "no_answer"}],
        [{"instance_id": "a", "fail_step": "none"}])
    check("transition matrix has a no_answer row", tm2["no_answer"]["none"] == 1)

    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
        return 1
    print("ALL SELFTESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
