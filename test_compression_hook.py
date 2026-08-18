#!/usr/bin/env python3
"""
Pre-flight check for SkillFlow's context-pressure gate. No GPU, no vLLM, no API.

Both compression components are gated on context pressure, so whether they run
at all is a property of the configuration, not of the code. This asserts that
the gate is reachable under the settings you are about to run 15 experiment
groups with — a run where compression never fires measures goal anchoring,
iterative planning and per-step local context, and nothing else.

    python test_compression_hook.py                    # defaults (qwen 32k)
    python test_compression_hook.py --context-window 32768 --compress-ratio 0.5

Exits non-zero if the gate is unreachable, so it can guard a batch:

    python test_compression_hook.py && ./run-experiments.sh
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    # Let the check run on a machine without the SDK (e.g. a laptop).
    import types
    stub = types.ModuleType("anthropic")
    stub.Anthropic = type("Anthropic", (), {"__init__": lambda self, *a, **k: None})
    stub.APIStatusError = type("APIStatusError", (Exception,), {})
    sys.modules["anthropic"] = stub

import skillflow as sf


# ---------------------------------------------------------------------------
# Fake client: canned tool-use turns, no network.
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


class _Messages:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kw):
        self.owner.calls += 1
        if self.owner.calls > self.owner.tool_turns:
            return _Resp([_Blk(type="text", text="FINAL ANSWER: 42")], "end_turn")
        return _Resp(
            [_Blk(type="tool_use", id=f"t{self.owner.calls}", name="bash",
                  input={"command": f"echo {self.owner.calls}"}, text=None)],
            "tool_use",
        )


class FakeClient:
    def __init__(self, window, tool_turns):
        self.context_window = window
        self.tool_turns = tool_turns
        self.calls = 0
        self.messages = _Messages(self)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context-window", type=int, default=None,
                    help="override the model context window (default: qwen 32768)")
    ap.add_argument("--compress-ratio", type=float, default=None,
                    help="override the trigger ratio (default: %.2f)"
                         % sf.CONTEXT_COMPRESS_RATIO)
    ap.add_argument("--skills-dir", default=str(HERE / "scibench_skills"))
    ap.add_argument("--tool-turns", type=int, default=8,
                    help="how many full-size tool results to put in the transcript")
    args = ap.parse_args()

    sf._BACKEND["context_window"] = args.context_window
    sf._BACKEND["compress_ratio"] = args.compress_ratio

    window = args.context_window or 32768
    client = FakeClient(window, args.tool_turns)
    threshold = sf.compression_threshold(client)

    sf.load_skills(pathlib.Path(args.skills_dir))
    if not sf.SKILL_DOCS:
        print(f"[FATAL] no skills loaded from {args.skills_dir}")
        return 2
    name, doc = max(sf.SKILL_DOCS.items(), key=lambda kv: len(kv[1]))

    print("=" * 66)
    print(" SkillFlow context-pressure gate")
    print("=" * 66)
    print(f"  context window    : {sf.get_context_window(client):,} tok")
    print(f"  compress ratio    : {sf.compress_ratio():.0%}")
    print(f"  trigger threshold : {threshold:,} tok  (~{threshold * 4:,} chars)")
    print(f"  skills            : {len(sf.SKILL_DOCS)}, largest is "
          f"{name} at {len(doc):,} chars (~{len(doc) // 4:,} tok)")
    print(f"  tool output cap   : {sf.MAX_TOOL_OUTPUT_CHARS:,} chars "
          f"(~{sf.MAX_TOOL_OUTPUT_CHARS // 4:,} tok per tool result)")

    goal = sf.GoalAnchor(objective="pre-flight", hard_constraints=[],
                         raw_request="pre-flight")

    # ---- 1. Step start, worst case this config can produce -----------------
    residual = sf.init_residual(goal)
    for _ in range(sf.MAX_SKILL_STEPS):
        residual = sf.add_raw_execution(residual, name, "x" * 3000)

    s1 = sf.CompressionStats()
    _, compressor, *_ = sf.assemble_execution_context(
        client, goal, residual, name, "pre-flight",
        base_system=sf.BASE_SYSTEM_SCIBENCH, verbose=False, stats=s1,
    )
    print("\n-- 1. step-start check, worst case (biggest skill + full residual)")
    print(f"  peak      : {s1.peak_prompt_tokens:,} tok "
          f"({s1.peak_prompt_tokens / threshold:.0%} of threshold)")
    print(f"  fired     : {s1.fired}")
    if s1.fired == 0:
        print("  -> as expected: the step-start reading alone cannot open the gate,")
        print("     because the transcript is still empty at that point.")

    # ---- 2. In-loop, with a transcript carrying real tool output -----------
    real_execute, real_skill, real_exec = (
        sf.execute_tool, sf.compress_skill, sf.compress_execution)
    sf.execute_tool = lambda n, i: "R" * sf.MAX_TOOL_OUTPUT_CHARS
    sf.compress_skill = lambda c, n, d, g: ("[compressed skill doc]", 0, 0)
    sf.compress_execution = lambda c, n, raw, g: (
        sf.ExecMemoryItem(skill_name=n, key_outcome="[summary]",
                          evidence=raw[:200], status="success"), 0, 0)
    try:
        s2 = sf.CompressionStats()
        r2 = sf.init_residual(goal)
        for _ in range(3):
            r2 = sf.add_raw_execution(r2, name, "y" * 3000)
        system, comp2, *_ = sf.assemble_execution_context(
            client, goal, r2, name, "pre-flight",
            base_system=sf.BASE_SYSTEM_SCIBENCH, verbose=False, stats=s2,
        )
        sf.run_agent_loop(
            client, [{"role": "user", "content": "pre-flight"}], system,
            token_budget=10_000_000, deadline=None, verbose=False,
            compressor=comp2,
        )
    finally:
        sf.execute_tool, sf.compress_skill, sf.compress_execution = (
            real_execute, real_skill, real_exec)

    print(f"\n-- 2. in-loop check, {args.tool_turns} full-size tool results")
    print(f"  peak      : {s2.peak_prompt_tokens:,} tok "
          f"({s2.peak_prompt_tokens / threshold:.0%} of threshold)")
    print(f"  checks    : {s2.checks}")
    print(f"  fired     : {s2.fired} (step-start={s2.fired_at_step_start}, "
          f"in-loop={s2.fired_in_loop})")
    print(f"  saved     : {s2.chars_saved:,} chars")

    # ---- 3. Idempotence ---------------------------------------------------
    # Only meaningful once something has actually been compressed: before the
    # first firing there is still work to do, so a further check *should* fire.
    reached_gate = s2.fired_in_loop > 0
    ok_idem = True
    if reached_gate:
        before = s2.fired
        for _ in range(5):
            comp2.check(threshold * 2, where="loop")
        ok_idem = s2.fired == before
        print(f"\n-- 3. idempotence: 5 more checks at 2x threshold -> fired "
              f"{before} then {s2.fired}  [{'ok' if ok_idem else 'FAIL'}]")
    else:
        print("\n-- 3. idempotence: skipped (nothing compressed yet)")

    # ---- 4. Condenser -----------------------------------------------------
    # The invariant that matters: every tool_use must keep a matching
    # tool_result, or the provider rejects the whole request with a 400 and the
    # task is lost. Masking preserves that; deleting messages would not.
    import condenser as cond
    msgs = [{"role": "user", "content": "task"}]
    for i in range(6):
        msgs.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "bash", "input": {}}]})
        msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}",
             "content": "R" * sf.MAX_TOOL_OUTPUT_CHARS}]})

    cd = cond.make_condenser("heuristic", keep_first=1, attention_window=2)
    n_before = len(msgs)
    cd.condense(msgs, prompt_tokens=threshold + 1, threshold=threshold)
    uses = [b["id"] for m in msgs for b in (m["content"] if isinstance(m["content"], list) else [])
            if isinstance(b, dict) and b.get("type") == "tool_use"]
    results = [b["tool_use_id"] for m in msgs for b in (m["content"] if isinstance(m["content"], list) else [])
               if isinstance(b, dict) and b.get("type") == "tool_result"]
    verbatim = sum(
        1 for m in msgs for b in (m["content"] if isinstance(m["content"], list) else [])
        if isinstance(b, dict) and b.get("type") == "tool_result"
        and not cond._as_text(b["content"]).startswith(cond.ELISION_PREFIX))
    fired_once = cd.stats.fired
    for _ in range(3):
        cd.condense(msgs, prompt_tokens=threshold * 10, threshold=threshold)

    ok_pairing = uses == results and len(msgs) == n_before
    ok_window = verbatim == 2
    ok_cond_idem = cd.stats.fired == fired_once
    print("\n-- 4. heuristic condenser (6 full-size observations)")
    print(f"  masked    : {cd.stats.blocks_masked}, dropped "
          f"{cd.stats.chars_dropped:,} chars")
    print(f"  pairing   : {len(uses)} tool_use / {len(results)} tool_result, "
          f"{len(msgs)} messages  [{'ok' if ok_pairing else 'FAIL'}]")
    print(f"  window    : {verbatim} kept verbatim (attention_window=2)  "
          f"[{'ok' if ok_window else 'FAIL'}]")
    print(f"  idempotent: {'ok' if ok_cond_idem else 'FAIL'}")

    # ---- verdict ----------------------------------------------------------
    print("\n" + "=" * 66)
    problems = []
    if not ok_pairing:
        problems.append("condenser broke tool_use/tool_result pairing — every "
                        "request would 400")
    if not ok_window:
        problems.append(f"attention_window kept {verbatim} observations, expected 2")
    if not ok_cond_idem:
        problems.append("condenser re-masks already-masked observations")
    if not ok_idem:
        problems.append("compressor re-fires with nothing left to shrink")
    if not reached_gate:
        need = (threshold - s2.peak_prompt_tokens) * 4 // sf.MAX_TOOL_OUTPUT_CHARS + 1
        problems.append(
            f"the gate is UNREACHABLE at ratio {sf.compress_ratio():.2f} on a "
            f"{sf.get_context_window(client):,}-token window: a transcript of "
            f"{args.tool_turns} maximum-size tool results peaked at "
            f"{s2.peak_prompt_tokens:,} tok, still {threshold - s2.peak_prompt_tokens:,} "
            f"short (~{need} more tool calls). Components 3 and 4 will not run. "
            f"Lower --compress-ratio or raise the tool output cap."
        )
    if problems:
        for p in problems:
            print(f" [FAIL] {p}")
        print("=" * 66)
        return 1

    print(" [OK] the context-pressure gate is reachable and idempotent.")
    print(f"      compression fires once the request passes {threshold:,} tok.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
