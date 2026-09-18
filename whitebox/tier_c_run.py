#!/usr/bin/env python3
"""Tier C: is it the rank of the mapping, or the length of the answer?

    python whitebox/tier_c_run.py --model $B/models/Qwen3-8B \
        --out results/tierC.jsonl

For each (family, answer length) cell this measures, on the items the document
rescues:

    gold / filler / none        the behavioural baselines
    last_replace                replace the LAST PROMPT POSITION with the
                                with-document state, every fourth layer
    last_add_d                  the same position, h_none + (h_gold - h_filler)
    span_replace                the document's own token span, length-matched

`copy` has an identity mapping, so a single vector is not rank-limited in Dong
et al.'s sense; `cipher` is a ten-symbol bijection, which is exactly the case
their Proposition 4 rules out. If `last_replace` falls off with answer length in
BOTH families, length binds independently of rank. If it only falls off in
cipher, what the main paper calls a length limit is a rank limit.

Grading is exact string match on the decoded answer, which is why the
vocabulary is invented: there is nothing to partially credit and no floor.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "howskill"))

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, "tasks", "tier_c")

SYSTEM = "You are a helpful assistant. Follow the instructions exactly."
SUFFIX = ("\n\nWrite only the answer, on one line, with no explanation and no "
          "punctuation.")


def user_text(skill_md: str | None, question: str) -> str:
    q = question + SUFFIX
    if skill_md:
        return f"Relevant Skill:\n{skill_md}\n\n{q}"
    return q


def spans_of(skill_md: str | None, question: str):
    """Character spans of the document and the question inside the user text."""
    u = user_text(skill_md, question)
    if skill_md:
        a = len("Relevant Skill:\n")
        return u, (a, a + len(skill_md))
    return u, None


def graded(text: str, answer: str) -> bool:
    got = text.strip().splitlines()[0].strip() if text.strip() else ""
    return " ".join(got.split()) == " ".join(answer.split())


def main(argv=None):
    from howskill.wb_replay import limit_threads
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--per-cell", type=int, default=20)
    p.add_argument("--layers", default="0,4,8,12,16,20,24,28,32,35")
    p.add_argument("--span-layers", default="0,8,16")
    p.add_argument("--max-new", type=int, default=80)
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--families", default="copy,cipher")
    p.add_argument("--lengths", default="1,2,4,8,16")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    from howskill.wb_spanpatch import SpanScorer
    from howskill.wb_spans import char_to_token_span

    items = [json.loads(l) for l in open(os.path.join(TASKS, "tasks.jsonl"),
                                         encoding="utf-8") if l.strip()]
    fams = a.families.split(",")
    lens = [int(x) for x in a.lengths.split(",")]
    layers = [int(x) for x in a.layers.split(",")]
    span_layers = [int(x) for x in a.span_layers.split(",")]
    filler = open(os.path.join(HERE, "tasks", "filler-neutral.md"),
                  encoding="utf-8").read()

    sc = SpanScorer(a.model, attn=a.attn)
    sc.cue = ""
    print(f"model {os.path.basename(a.model.rstrip('/'))}, "
          f"{sc.model.config.num_hidden_layers} layers, prompt_mode pending",
          flush=True)

    by_cell = collections.defaultdict(list)
    for it in items:
        if it["family"] in fams and it["answer_len"] in lens:
            by_cell[(it["family"], it["answer_len"])].append(it)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    fh = open(a.out, "w", encoding="utf-8")
    for (fam, n), pool in sorted(by_cell.items()):
        skill = open(os.path.join(TASKS, f"SKILL.{it_skill(fam, n)}.md"),
                     encoding="utf-8").read()
        picked = pool[:a.per_cell]
        agg = collections.defaultdict(list)
        for it in picked:
            ug, sp = spans_of(skill, it["question"])
            uf, spf = spans_of(filler, it["question"])
            u0, _ = spans_of(None, it["question"])
            ids_g = sc.prompt_ids(SYSTEM, ug)
            ids_f = sc.prompt_ids(SYSTEM, uf)
            ids_0 = sc.prompt_ids(SYSTEM, u0)
            ok_g = graded(sc.decode_ids(ids_g, max_new=a.max_new), it["answer"])
            ok_f = graded(sc.decode_ids(ids_f, max_new=a.max_new), it["answer"])
            ok_0 = graded(sc.decode_ids(ids_0, max_new=a.max_new), it["answer"])
            rec = {"id": it["id"], "family": fam, "answer_len": n,
                   "model": os.path.basename(a.model.rstrip("/")),
                   "prompt_mode": sc.prompt_mode,
                   "ok_gold": ok_g, "ok_filler": ok_f, "ok_none": ok_0,
                   "cell": "R" if (ok_g and not ok_0) else
                           "K" if (ok_g and ok_0) else
                           "B" if (not ok_g and ok_0) else "F"}
            if rec["cell"] == "R":
                # the single-position channel: replace the last prompt position
                for L in layers:
                    donor = sc.capture_ids(ids_g, L, [int(ids_g.shape[1]) - 1])
                    ok = graded(sc.decode_ids(
                        ids_0, L, [int(ids_0.shape[1]) - 1], donor,
                        a.max_new), it["answer"])
                    rec[f"ok_last_replace_L{L}"] = ok
                    agg[f"last_replace_L{L}"].append(ok)
                # the document's own span, length-matched
                enc = sc.tok(sc._prompt(SYSTEM, ug),
                             return_offsets_mapping=True, return_tensors="pt")
                offs = enc["offset_mapping"][0].tolist()
                base = sc._prompt(SYSTEM, ug).rindex(ug)
                lo, hi = char_to_token_span(offs, *sp, base=base)
                ids_r = sc.matched_receiver(ids_g, (lo, hi), ids_f)
                pos = list(range(lo, hi))
                rec["ok_recv"] = graded(sc.decode_ids(ids_r, max_new=a.max_new),
                                        it["answer"])
                agg["recv"].append(rec["ok_recv"])
                for L in span_layers:
                    donor = sc.capture_ids(ids_g, L, pos)
                    ok = graded(sc.decode_ids(ids_r, L, pos, donor, a.max_new),
                                it["answer"])
                    rec[f"ok_span_L{L}"] = ok
                    agg[f"span_L{L}"].append(ok)
            for k in ("gold", "filler", "none"):
                agg[k].append(rec["ok_" + k])
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
        nR = len(agg.get("recv", []))   # the rescued cell for this cell
        line = "  ".join(f"{k}={sum(v)/len(v):.2f}" for k, v in sorted(agg.items())
                         if k in ("gold", "filler", "none", "recv"))
        best = max((sum(v) / len(v) for k, v in agg.items()
                    if k.startswith("last_replace")), default=float("nan"))
        bspan = max((sum(v) / len(v) for k, v in agg.items()
                     if k.startswith("span_")), default=float("nan"))
        print(f"  {fam:7s} len={n:2d}  n={len(picked):3d} R={nR:3d}  {line}"
              f"  last(best)={best:.2f}  span(best)={bspan:.2f}", flush=True)
    fh.close()
    print(f"\n-> {a.out}")
    return 0


def it_skill(fam: str, n: int) -> str:
    return f"copy{n}" if fam == "copy" else "cipher"


if __name__ == "__main__":
    raise SystemExit(main())
