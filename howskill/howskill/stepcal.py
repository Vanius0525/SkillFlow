"""Dump a stratified sample of step-level classifications for human review.

    python -m howskill.stepcal results/p1/p1-direct.jsonl --n 50

P0-4: the S1-S5 first-failure parser was written offline and has never been
checked against a real trajectory. PROTOCOL.md gates the whole step-level
readout on a >=80% parse rate, but a parse rate says nothing about whether the
labels are *right* — that needs eyes on 50 of them.

Only incorrect instances are sampled: `first_failure` returns 'none' for the
ones that passed, and reviewing those tells us nothing. The sample is
stratified over the predicted label so that rare labels get looked at too —
a uniform sample of a mostly-S4 arm would never surface an S3 mistake.

Output is one JSON object per line, holding everything a reviewer needs and
nothing else: the prediction, the ground truth it was judged against, and the
agent's own text (truncated). Fill in "verdict" per line as either "ok" or the
label you think it should have been.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random

from howskill.steps import STEPS, first_failure

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
LABELS = ["S1", "S2", "S3", "S4", "S5", "unparsed"]


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                if "error" not in r:
                    rows.append(r)
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("results_file")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-chars", type=int, default=3000,
                   help="truncate the agent transcript to this many chars")
    p.add_argument("--out", default="")
    a = p.parse_args(argv)

    gt = {g["instance_id"]: g for g in json.load(
        open(os.path.join(DATA, "stepgt.json"), encoding="utf-8"))}
    inst = {i["instance_id"]: i for i in json.load(
        open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
    names = {s["skill_id"]: s.get("name") for s in json.load(
        open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}

    rows = load_jsonl(a.results_file)
    labelled = []
    for r in rows:
        fr = first_failure(r.get("trajectory") or {}, inst[r["instance_id"]],
                           gt.get(r["instance_id"]), {"correct": r["correct"]},
                           calculator_name=names.get(r.get("skill_id")))
        labelled.append((r, fr))

    dist = collections.Counter(fr["fail_step"] for _, fr in labelled)
    wrong = [(r, fr) for r, fr in labelled if fr["fail_step"] != "none"]
    n_unparsed = dist.get("unparsed", 0)
    parse_rate = 1 - n_unparsed / max(1, len(wrong))

    print(f"{len(rows)} instances, {len(wrong)} incorrect")
    for k in ["none"] + LABELS:
        if dist.get(k):
            print(f"  {k:9s} {dist[k]:5d}")
    print(f"parse rate (of incorrect): {100*parse_rate:.1f}%  "
          f"(PROTOCOL.md GATE-0 wants >=80%)")

    # Stratified: every predicted label gets at least a few, the rest
    # proportional. A uniform sample would never show us a rare label.
    by_label: dict = {}
    for r, fr in wrong:
        by_label.setdefault(fr["fail_step"], []).append((r, fr))
    rng = random.Random(a.seed)
    floor = min(5, a.n // max(1, len(by_label)))
    picked = []
    for lab in sorted(by_label, key=lambda x: LABELS.index(x) if x in LABELS else 9):
        xs = sorted(by_label[lab], key=lambda z: z[0]["instance_id"])
        rng.shuffle(xs)
        take = max(floor, round(a.n * len(by_label[lab]) / len(wrong)))
        picked.extend(xs[:take])
    rng.shuffle(picked)
    picked = picked[:a.n]

    out_path = a.out or (os.path.splitext(a.results_file)[0] + "-stepcal.jsonl")
    with open(out_path, "w", encoding="utf-8") as fh:
        for r, fr in picked:
            g = gt.get(r["instance_id"]) or {}
            traj = r.get("trajectory") or {}
            text = traj.get("transcript") or traj.get("model_output") or ""
            fh.write(json.dumps({
                "instance_id": r["instance_id"],
                "calculator_id": r["calculator_id"],
                "calculator_name": names.get(r.get("skill_id")),
                "pred_step": fr["fail_step"],
                "pred_detail": fr["detail"],
                "verdict": "",
                "gt_answer": r["gt_answer"],
                "extracted_answer": r["extracted_answer"],
                "gt_entities": g.get("relevant_entities"),
                "gt_explanation": (g.get("gt_explanation") or "")[:1200],
                "n_tool_calls": traj.get("n_tool_calls"),
                "stop_reason": traj.get("stop_reason"),
                "transcript": text[:a.max_chars],
            }, ensure_ascii=False) + "\n")

    size = os.path.getsize(out_path)
    print(f"\n{len(picked)} sampled -> {out_path}  ({size/1024:.0f} KB)")
    print("Review each line's pred_step against gt_explanation + transcript; "
          "put 'ok' or the correct label in \"verdict\".")


if __name__ == "__main__":
    main()
