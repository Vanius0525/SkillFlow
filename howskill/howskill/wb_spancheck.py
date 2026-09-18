"""Do the patched positions actually hold the document's tokens?

Every causal claim in the paper is 'we wrote over the document's own span'.
Nothing downstream would look wrong if that span were off by a few tokens, or
were the question instead -- the numbers would simply be smaller. So decode the
positions the battery patches and compare them against the document text.
"""
import sys, json, os
sys.path.insert(0, "/root/wb/howskill")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
from howskill.wb_spanvec import (build_item, DATA, family_of)  # noqa
from howskill.wb_diffvec import pick_instances  # noqa
from howskill.wb_spanpatch import SpanScorer  # noqa

B = "/inspire/ssd/project/project-public/czxs253130660"
instances = {i["instance_id"]: i for i in json.load(
    open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
skills = {s["skill_id"]: s for s in json.load(
    open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}
pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"), encoding="utf-8"))
cells = json.load(open(os.path.join(DATA, "cells.json"), encoding="utf-8"))["cells"]

sc = SpanScorer(f"{B}/models/Qwen3-8B")
todo = pick_instances(cells, instances, ["R"], 1, 4)
for doc_last in (False, True):
    print(f"\n===== doc_last={doc_last}")
    seen = set()
    for calc, _cell, iid in todo:
        if calc in seen:
            continue
        seen.add(calc)
        it = build_item(sc, instances[iid], skills, pairs,
                        "gold_no_tool", "ctrl_neutral_no_tool",
                        doc_last=doc_last, filler="fixedskill")
        pos = it["pos"]
        ids_g = it["ids_g"][0].tolist()
        span_txt = sc.tok.decode([ids_g[p] for p in pos])
        sid = instances[iid]["skill_annotations"][0]
        doc = skills[sid]["content"]
        # how much of the decoded span is the document, and vice versa
        inside = doc[:60].strip() in span_txt
        tail_ok = doc[-60:].strip() in span_txt
        extra = len(span_txt) - len(doc)
        print(f"  {calc:>4} {iid} m={len(pos)} "
              f"doc_head_in_span={inside} doc_tail_in_span={tail_ok} "
              f"len(span)-len(doc)={extra:+d}")
        if not inside or not tail_ok:
            print("     span starts:", repr(span_txt[:90]))
            print("     doc  starts:", repr(doc[:90]))
            print("     span ends  :", repr(span_txt[-90:]))
            print("     doc  ends  :", repr(doc[-90:]))
