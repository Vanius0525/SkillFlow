#!/usr/bin/env python3
"""
Pre-flight for the termination contract and the GAIA scorer. No GPU, no API.

Two things here decide whether a GAIA number means anything:

  * the scorer — the official one is the only mode comparable with published
    results, and it is stricter than what this repo used before, so a silent
    regression back to the lenient version would inflate every score;
  * the contract — `submit` plus the continue nudge must behave identically in
    skillflow.py and in the baseline harnesses, or the gap between them is
    partly a measure of who got more chances to speak.

    python test_contract_and_scorer.py

Exits non-zero on any failure, so it can guard a batch:

    python test_contract_and_scorer.py && ./run-experiments.sh
"""
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

for name, attrs in (("anthropic", {"Anthropic": type("Anthropic", (), {}),
                                   "APIStatusError": type("E", (Exception,), {})}),
                    ("pandas", {"read_parquet": lambda *a, **k: None})):
    try:
        __import__(name)
    except ModuleNotFoundError:
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod

import agent_contract as ac
import gaia_scorer as gs
import skillflow as sf
import eval_gaia_with_skills as eg

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {msg}")
    if not cond:
        FAILURES.append(msg)


def banner(title: str) -> None:
    print("\n" + "=" * 68 + f"\n {title}\n" + "=" * 68)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    input_tokens = 100
    output_tokens = 20


class _Resp:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason, self.usage = content, stop_reason, _Usage()


class Scripted:
    """Replays a fixed list of (stop_reason, blocks) responses."""

    context_window = 32768

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.tools_seen: list[str] = []
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        self.tools_seen = [t["name"] for t in kw.get("tools", [])]
        stop, blocks = self.script.pop(0) if self.script else (
            "end_turn", [_Blk(type="text", text="")])
        return _Resp(blocks, stop)


def loop(script, stats, budget=10_000_000):
    client = Scripted(script)
    text, _, _ = sf.run_agent_loop(
        client, [{"role": "user", "content": "q"}], "sys",
        token_budget=budget, verbose=False, contract_stats=stats)
    return text, client


# ---------------------------------------------------------------------------
banner("1. Official GAIA scorer")
CASES = [
    ("42", "42", True),
    ("42.0", "42", True),
    ("$42,000", "42000", True),
    ("41", "42", False),
    ("42.5", "42", False),                     # exact float match, no tolerance
    ("Paris", "paris", True),
    ("  Paris  ", "Paris", True),
    ("Paris.", "Paris", True),                 # punctuation stripped in string mode
    ("the Louvre", "Louvre", False),           # articles NOT stripped
    ("a, b, c", "a,b,c", True),
    ("b, a, c", "a,b,c", False),               # list order matters
    ("a, b", "a,b,c", False),                  # length mismatch
    ("1, 2.0, 3", "1,2,3", True),
    ("St. Petersburg", "St Petersburg", True),
    ("Rome, St. Petersburg", "Rome,St Petersburg", False),  # list mode keeps punctuation
]
for pred, gold, want in CASES:
    check(gs.question_scorer(pred, gold) == want, f"{pred!r} vs {gold!r} -> {want}")
check(gs.question_scorer(None, "x") is False, "None answer scores False, no crash")

banner("2. Both harnesses score identically")
sf._JUDGE["mode"] = "official"
disagree = [(p, g) for p, g, _ in CASES if sf.is_correct_gaia(p, g) != eg.is_correct(p, g)]
check(not disagree, f"skillflow and eval_gaia agree on all {len(CASES)} cases")
if disagree:
    print("      disagreements:", disagree)
check(sf.is_correct_gaia("the Louvre", "Louvre") is False,
      "official strictness is live (the lenient scorer would say True)")

banner("3. Termination contract")
sf.execute_tool = lambda name, inputs: "ok"
sf._CONDENSER["name"] = "none"
sf._CONTRACT.update(submit_tool=True, max_continues=3)

s = ac.ContractStats()
text, client = loop([("tool_use", [_Blk(type="tool_use", id="s1", name="submit",
                                        input={"answer": "Bruce Wayne"}, text=None)])], s)
check(text == "FINAL ANSWER: Bruce Wayne", f"submit surfaces its answer: {text!r}")
check(s.submitted == 1, "submission counted")
check("submit" in client.tools_seen, f"submit offered to the model: {client.tools_seen}")

s = ac.ContractStats()
text, _ = loop([
    ("end_turn", [_Blk(type="text", text="Let me think about this.")]),
    ("end_turn", [_Blk(type="text", text="Still thinking.")]),
    ("tool_use", [_Blk(type="tool_use", id="s1", name="submit",
                       input={"answer": "7"}, text=None)]),
], s)
check(text == "FINAL ANSWER: 7", f"a silent model is nudged, then answers: {text!r}")
check(s.continues == 2 and s.rescued == 1, f"2 nudges, 1 rescue (got {s.continues}, {s.rescued})")

s = ac.ContractStats()
_, client = loop([("end_turn", [_Blk(type="text", text="hmm")])] * 10, s)
check(s.continues == 3, f"nudges capped at max_continues=3 (got {s.continues})")
check(client.calls == 4, f"1 call + 3 nudges = 4 (got {client.calls})")
check(s.ended_without_answer == 1, "answerless ending is recorded, not hidden")

s = ac.ContractStats()
text, _ = loop([("end_turn", [_Blk(type="text", text="Done.\nFINAL ANSWER: 9")])], s)
check(s.continues == 0, "no nudge when the model already answered")
check(sf.extract_final_answer(text) == "9", "answer still extractable")

sf._CONTRACT.update(submit_tool=False)
s = ac.ContractStats()
_, client = loop([("end_turn", [_Blk(type="text", text="hmm")])] * 5, s)
check(client.calls == 1 and s.continues == 0, "--no-submit-tool restores first-end_turn-wins")
check("submit" not in client.tools_seen, "submit withheld when disabled")
sf._CONTRACT.update(submit_tool=True)

banner("4. An earlier step's answer is not discarded")
sf.load_skills(HERE / "scibench_skills")
sf.anchor_goal = lambda c, req: (sf.GoalAnchor(objective="o", raw_request=req), 0, 0)
_plan = iter(["code-sandbox", "code-sandbox", None])
sf.plan_next_skill = lambda *a: (next(_plan, None), 0, 0)


class TwoStep:
    """Step 1 answers; step 2 says nothing. The answer must survive."""

    context_window = 32768

    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        text = "FINAL ANSWER: 1024" if self.calls == 1 else ""
        return _Resp([_Blk(type="text", text=text)], "end_turn")


res = sf.run_skillflow(client=TwoStep(), user_request="q", skills_index="(idx)",
                       k=8, token_budget=10_000_000, task_timeout=86400,
                       max_steps=2, verbose=False)
check(sf.extract_final_answer(res["response"]) == "1024",
      f"step 1's answer survives step 2's silence: {res['response']!r}")
check(res["skill_steps"] == 2, f"both steps ran (got {res['skill_steps']})")

# ---------------------------------------------------------------------------
print("\n" + "=" * 68)
if FAILURES:
    print(f" {len(FAILURES)} FAILURE(S)")
    for f in FAILURES:
        print("   -", f)
    print("=" * 68)
    sys.exit(1)
print(" ALL CHECKS PASSED")
print("=" * 68)
