"""Runner CLI.

    python -m howskill.run --arm gold --model Qwen/Qwen3-8B --out results/

Every run writes one JSONL (one line per instance) plus a `_meta.json`
recording the full configuration — model, temperature, seed, thinking flag,
arm, schedule, git commit. Results without that metadata are not comparable
and should be discarded.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from howskill import arms as arms_mod
from howskill.grade import evaluate
from howskill.llm import ChatClient
from howskill.loop import make_prefix, run_episode
from howskill.prompts import build_prompt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


def load_data():
    skills = json.load(open(f"{DATA}/medcalc_skills.json", encoding="utf-8"))
    instances = json.load(open(f"{DATA}/medcalcbench.json", encoding="utf-8"))
    by_id = {s["skill_id"]: s for s in skills}
    try:
        pairs = json.load(open(f"{DATA}/neutral_pairs.json", encoding="utf-8"))
    except FileNotFoundError:
        pairs = {}
    try:
        gt = {g["instance_id"]: g
              for g in json.load(open(f"{DATA}/stepgt.json", encoding="utf-8"))}
    except FileNotFoundError:
        gt = {}
    return skills, instances, by_id, pairs, gt


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def subset(instances, n_per_calc: int, seed: int):
    """Deterministic per-calculator subsample."""
    if n_per_calc <= 0:
        return instances
    rng = random.Random(seed)
    by_calc: dict = {}
    for x in instances:
        by_calc.setdefault(x["eval_data"]["calculator_id"], []).append(x)
    out = []
    for cid in sorted(by_calc):
        xs = sorted(by_calc[cid], key=lambda z: z["instance_id"])
        rng.shuffle(xs)
        out.extend(xs[:n_per_calc])
    return sorted(out, key=lambda z: z["instance_id"])


def run_one(inst, arm, by_id, pairs, client, schedule, prefixes, no_tool_protocol):
    sid = inst["skill_annotations"][0] if inst["skill_annotations"] else None
    gold = by_id.get(sid)
    neutral = by_id.get(pairs.get(sid)) if arm == "ctrl_neutral" else None

    payload = arms_mod.build(arm, gold, neutral_for=neutral, seed=0) if gold else []
    tools = [t for s in payload for t in (s.get("tools") or [])]

    system, user_skill = build_prompt(
        inst, skills=payload, tool_protocol=bool(tools) and not no_tool_protocol)
    _, user_plain = build_prompt(
        inst, skills=[], tool_protocol=bool(tools) and not no_tool_protocol)

    forced = None
    if prefixes:
        rec = prefixes.get(inst["instance_id"])
        if rec:
            forced = make_prefix(rec["trajectory"], rec["upto_turn"])

    traj = run_episode(
        client, system, user_skill, user_plain, tools,
        skill_schedule=schedule, forced_prefix=forced,
    )
    graded = evaluate(traj.model_output, inst)
    return {
        "instance_id": inst["instance_id"],
        "calculator_id": inst["eval_data"]["calculator_id"],
        "skill_id": sid,
        "arm": arm,
        "correct": graded["correct"],
        "extracted_answer": graded["extracted_answer"],
        "gt_answer": inst["eval_data"]["answer"],
        "output_type": graded["output_type"],
        "trajectory": traj.to_dict(),
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True, choices=arms_mod.ARMS)
    p.add_argument("--schedule", default="all", choices=["all", "first", "late"])
    p.add_argument("--model", default=os.environ.get("QWEN_MODEL", "Qwen/Qwen3-8B"))
    p.add_argument("--base-url", default=os.environ.get("QWEN_BASE_URL",
                                                        "http://127.0.0.1:8000/v1"))
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--thinking", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--logprobs", type=int, default=0)
    p.add_argument("--n-per-calc", type=int, default=0, help="0 = all 20")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", default="results")
    p.add_argument("--tag", default="")
    p.add_argument("--prefixes", default="", help="JSON of graft prefixes (P7)")
    p.add_argument("--no-tool-protocol", action="store_true",
                   help="omit the explicit TOOL_CALL syntax note (upstream parity)")
    a = p.parse_args(argv)

    skills, instances, by_id, pairs, _gt = load_data()
    insts = subset(instances, a.n_per_calc, a.seed)
    prefixes = json.load(open(a.prefixes, encoding="utf-8")) if a.prefixes else None

    client = ChatClient(base_url=a.base_url, model=a.model,
                        temperature=a.temperature, max_tokens=a.max_tokens,
                        thinking=a.thinking, seed=a.seed,
                        logprobs=a.logprobs or None)

    os.makedirs(a.out, exist_ok=True)
    tag = a.tag or f"{a.arm}-{a.schedule}-T{a.temperature}-s{a.seed}"
    path = os.path.join(a.out, f"{tag}.jsonl")
    meta = {
        "arm": a.arm, "schedule": a.schedule, "n_instances": len(insts),
        "client": client.config(), "git_commit": git_commit(),
        "argv": sys.argv, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "no_tool_protocol": a.no_tool_protocol,
    }
    json.dump(meta, open(os.path.join(a.out, f"{tag}_meta.json"), "w"), indent=1)

    t0 = time.time()
    n_ok = 0
    with open(path, "w", encoding="utf-8") as fh, \
            ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(run_one, x, a.arm, by_id, pairs, client,
                          a.schedule, prefixes, a.no_tool_protocol)
                for x in insts]
        for i, f in enumerate(futs, 1):
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001
                r = {"error": repr(e)}
            else:
                n_ok += bool(r["correct"])
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)}  acc={n_ok/i:.3f}  "
                      f"{time.time()-t0:.0f}s", flush=True)

    print(f"\n{tag}: {n_ok}/{len(insts)} = {100*n_ok/len(insts):.1f}%  -> {path}")


if __name__ == "__main__":
    main()
