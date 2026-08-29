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
from howskill.steps import first_failure, parse_entities, transition_matrix

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
    check("schedule=late: present after first tool call",
          "Relevant Skill:" in m3.seen[1][1]["content"])

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

    print("\n== steps ==")
    g = stepgt[instances[0]["instance_id"]] if instances[0]["instance_id"] in stepgt \
        else next(iter(stepgt.values()))
    ents = parse_entities(g["relevant_entities"])
    check("entities parse to non-empty dict", bool(ents), str(list(ents)[:4]))
    n_parsed = sum(1 for v in stepgt.values() if parse_entities(v["relevant_entities"]))
    check("entities parse for >=95% of step-GT",
          n_parsed >= 0.95 * len(stepgt), f"{n_parsed}/{len(stepgt)}")
    fr = first_failure({"transcript": "ANSWER: 3", "n_tool_calls": 1},
                       instances[0], g, {"correct": True})
    check("correct -> fail_step none", fr["fail_step"] == "none")
    tm = transition_matrix(
        [{"instance_id": "a", "fail_step": "S2"}],
        [{"instance_id": "a", "fail_step": "none"}])
    check("transition matrix counts (S2->none)", tm["S2"]["none"] == 1)

    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
        return 1
    print("ALL SELFTESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
