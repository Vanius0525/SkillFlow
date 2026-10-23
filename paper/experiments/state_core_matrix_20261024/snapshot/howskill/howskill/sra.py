"""SRA-Bench beyond MedCalc: data, grouping and the official prompts.

The whitebox pipeline was written for MedCalc-Bench. SRA-Bench ships five more
task families in the same instance/skill format; three of them can be graded
without tools or code execution and are wired in here:

    theoremqa   747 instances, 320 skills, numeric/bool/list answers
    logicbench  760 instances,  19 skills, yes/no and choice_k answers
    champ       223 instances,  89 skills (114 single-skill), free-form math

ToolQA is left out because its answers come from tool calls over external
databases -- without the tools neither arm can answer, so there is no rescued
cell to study. BigCodeBench is left out because grading executes unit tests
against ~70 third-party libraries.

MedCalc keeps its original files, prompt strings and grader byte for byte, so
every number already in the paper is unaffected. The prompt builders below are
VERBATIM from SR-Agents ``src/sragents/prompts.py`` (MIT), fetched 2026-09-14;
accuracy under them is comparable with the SRA-Bench paper's.

    data/sra/<dataset>_instances.json   SRA-Bench instances/<dataset>.json
    data/sra/<dataset>_skills.json      that dataset's gold skills from corpus.json
    data/sra/<dataset>_pairs.json       each skill -> the same-dataset skill of
                                        nearest length (the behavioural wrong-skill arm)
    data/sra/meta.json                  counts, and the fixed distractor skill
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SRA = os.path.join(DATA, "sra")
DATASETS = ("medcalcbench", "theoremqa", "logicbench", "champ")


def load(dataset: str):
    """(instances by id, skills by id, wrong-skill pairs, distractor skill id)."""
    if dataset == "medcalcbench":
        inst = json.load(open(os.path.join(DATA, "medcalcbench.json"),
                              encoding="utf-8"))
        sk = json.load(open(os.path.join(DATA, "medcalc_skills.json"),
                            encoding="utf-8"))
        pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"),
                               encoding="utf-8"))
        distractor = "medcalcbench_043"      # wb_spanvec.FIXED_DISTRACTOR_SKILL
    else:
        inst = json.load(open(os.path.join(SRA, f"{dataset}_instances.json"),
                              encoding="utf-8"))
        sk = json.load(open(os.path.join(SRA, f"{dataset}_skills.json"),
                            encoding="utf-8"))
        pairs = json.load(open(os.path.join(SRA, f"{dataset}_pairs.json"),
                               encoding="utf-8"))
        distractor = json.load(open(os.path.join(SRA, "meta.json"),
                                    encoding="utf-8"))[dataset]["distractor_skill"]
    return ({i["instance_id"]: i for i in inst},
            {s["skill_id"]: s for s in sk}, pairs, distractor)


def group_key(inst: dict) -> str:
    """What "same document" means: the calculator on MedCalc, else the skill set.

    MedCalc keys on calculator_id, as it always has. Elsewhere an instance's
    document is its annotated skill list; multi-skill CHAMP items get a key of
    their own and are dropped by the span runs (see `single_skill`).
    """
    ed = inst.get("eval_data") or {}
    if isinstance(ed, dict) and ed.get("calculator_id") is not None:
        return str(ed["calculator_id"])
    return "+".join(inst["skill_annotations"])


def single_skill(inst: dict) -> bool:
    return len(inst["skill_annotations"]) == 1


# ---- official prompt builders (SR-Agents prompts.py, verbatim) --------------

def _build_theoremqa(instance: dict) -> tuple[str, str]:
    system = (
        "You are a science teacher, you are supposed to provide a solution to a "
        "given problem. You need to output the answer in your final sentence like "
        '"Therefore, the answer is ...". The answer can only be one of the following '
        "forms:\n"
        "1. a numerical value like 0.1, no symbol at all.\n"
        "2. a list of number like [2, 3, 4].\n"
        "3. True/False.\n"
        "4. an option like (a), (b), (c), (d)"
    )
    user = f"Problem:{instance['question']}\nSolution:"
    return system, user


def _build_logicbench(instance: dict) -> tuple[str, str]:
    return "", instance["question"]


def _build_champ(instance: dict) -> tuple[str, str]:
    system = "You are an expert on mathematics."
    user = (
        "Solve the following problem. Make sure to show your work before giving "
        "the final answer.\n\n"
        f"{instance['question']}\n\n"
        "After your solution, write your final answer on its own line in "
        "exactly this format:\n"
        "ANSWER: <your answer>\n\n"
        "The answer should be concise: a number, mathematical expression, "
        "Yes/No, or a brief phrase. Do not include explanations in the "
        "ANSWER line. Use plain text only — do not use LaTeX, dollar signs, "
        "or any other formatting (e.g., write n! not \\(n!\\) or $n!$)."
    )
    return system, user


BUILDERS = {"theoremqa": _build_theoremqa, "logicbench": _build_logicbench,
            "champ": _build_champ}
