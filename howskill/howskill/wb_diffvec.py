"""M5 -- the skill vector on real skills: decompose the injection, then move it.

    python -m howskill.wb_diffvec --cells data/cells.json \
        --model $BASE/models/Qwen3-8B --out results/p8-wb/diffvec.jsonl

This is `whitebox/e14_decomp.py` carried over to the MedCalc/SRA-Bench material,
where the skills and the tasks are other people's. Same decomposition, at the
last prompt position, per instance i and layer L:

    t_i = h_gold(i) - h_none(i)        total displacement from reading a skill
    g_i = h_neutral(i) - h_none(i)     presence: a length-matched WRONG skill
    d_i = h_gold(i) - h_neutral(i)     content: what is left when presence cancels

and t_i = g_i + d_i exactly.

Why this material adds something the synthetic tier cannot. Tier A has one skill
document, so "does the content vector transfer between tasks" can only be asked
across items of the same document. Here there are 55 distinct gold skills with
20 instances each, so the donor structure has two levels that matter:

    same-calculator donor   d from another patient note, SAME skill document
                            -> is the content vector a property of the skill,
                               or of the (skill, note) pair?
    cross-calculator donor  d from a different skill entirely
                            -> the negative control for the above

and the four-cell split (R rescued / F persistent / K kept / B broken) is already
built from the behavioural run, so "do the items the skill rescues have a
different d from the ones it does not" is a groupby rather than a new run.

DEPENDENT VARIABLES. Two, because they fail differently and this study has
already been burned by reading only the first:

  lp(gold answer)  teacher-forced under the "\\nANSWER: " cue, as in wb_patch.
  generated answer decoded greedily under the same cue and graded by the same
                   deterministic scorer the behavioural run used. The answers
                   here are free-form numbers, not option letters, so this is a
                   real accuracy channel and no item had to be rewritten into
                   multiple choice to get one.

The cue matters and is a deliberate limitation: MedCalc answers normally come
after a chain of thought, and scoring under "\\nANSWER: " asks for the answer
without one. That makes every number here lower than the behavioural run's, and
makes the comparison between conditions -- which is what the experiment is about
-- affordable. It is the same cue wb_patch.py uses, so the two are comparable.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random

import numpy as np

from howskill import arms as arms_mod
from howskill import grade
from howskill.prompts import build_prompt_spans
from howskill.sra import group_key, single_skill
from howskill.wb_patch import ANSWER_CUE, Scorer
from howskill.wb_replay import limit_threads

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


class VecScorer(Scorer):
    """Scorer plus: capture every layer in one forward, and decode under a patch."""

    cue: str = ANSWER_CUE
    prompt_mode: str = "?"

    def __init__(self, model_path: str, thinking: bool = False,
                 device: str = "cuda", dtype: str = "bfloat16",
                 attn: str = "sdpa"):
        """Same as Replayer, but the attention implementation is a knob.

        Replayer pins eager because the knockout interventions pass a 4D
        attention mask, which sdpa and flash silently ignore. Nothing in this
        file does that: every intervention here is a forward hook on a decoder
        layer's OUTPUT, which is implementation-independent. cot mode decodes
        ~400 tokens per condition over a ~2k-token prompt, where eager costs
        roughly 2.5x, so pinning it would have bought nothing and cost hours.
        Capture and patched forward always use the same implementation, so the
        comparison is internally consistent either way.
        """
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.thinking = thinking
        self.tok = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=getattr(torch, dtype),
            device_map=device, attn_implementation=attn)
        self.model.eval()
        self.device = device
        self.attn = attn

    def _prompt(self, system: str, user: str) -> str:
        """Chat-formatted prompt, portable across model families.

        Two things are Qwen-specific and have to degrade rather than crash when
        the same experiment is run on another family. `enable_thinking` is a
        Qwen template kwarg; templates that do not take it raise. And several
        families (Mistral among them) have no system role in their template and
        raise on one -- there the system text is prefixed to the user turn,
        which is what those templates do internally anyway.

        The fallbacks are recorded on the instance so a run can report which
        path it took; a silent difference in prompt construction between models
        would make a cross-model comparison meaningless.
        """
        # an empty system prompt (SR-Agents' LogicBench builder) is omitted, as
        # a chat API caller would, rather than rendered as an empty system turn
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": user}]
        merged = system + "\n\n" + user if system else user
        for kw, ms in (({"enable_thinking": self.thinking}, msgs),
                       ({}, msgs),
                       ({}, [{"role": "user", "content": merged}])):
            try:
                out = self.tok.apply_chat_template(
                    ms, tokenize=False, add_generation_prompt=True, **kw)
            except Exception:                      # noqa: BLE001
                continue
            self.prompt_mode = ("thinking-kwarg" if kw else
                                "plain" if ms is msgs else "system-in-user")
            return out + self.cue
        raise SystemExit("no usable chat template for this tokenizer")

    def score_answer(self, system: str, user: str, answer: str,
                     hooks=None, mask_spans=None) -> float:
        """As Scorer.score_answer, but honouring self.cue.

        Scorer hard-codes ANSWER_CUE. In cot mode the capture position is the
        end of the plain prompt, and scoring at a DIFFERENT position than the
        one being patched would silently measure the wrong thing -- so the cue
        is one attribute used by every method here.
        """
        t = self.torch
        prompt = self._prompt(system, user)
        enc = self.tok(prompt + str(answer), return_tensors="pt")
        n_prompt = len(self.tok(prompt)["input_ids"])
        ids = enc["input_ids"].to(self.device)
        att = enc["attention_mask"].to(self.device)
        if mask_spans:
            att = att.clone()
            for lo, hi in mask_spans:
                att[0, lo:hi] = 0
        handles = []
        try:
            for h in (hooks or []):
                handles.append(h(self.model))
            with t.no_grad():
                out = self.model(input_ids=ids, attention_mask=att,
                                 use_cache=False)
        finally:
            for h in handles:
                h.remove()
        lp = t.log_softmax(out.logits[0].float()[:-1], dim=-1)
        got = lp.gather(1, ids[0][1:].unsqueeze(1)).squeeze(1)
        return float(got[n_prompt - 1:].mean().item())

    def capture_all_layers(self, system: str, user: str, layers: list[int]):
        """Residual state at the LAST prompt position, for each wanted layer.

        Registered as forward hooks on ``model.model.layers[L]`` rather than
        read off ``output_hidden_states``, because that is the object
        ``patch_hook`` overwrites. hidden_states[L] is the INPUT of layer L,
        so reading one and writing the other would be an off-by-one that no
        assertion in this file would catch.
        """
        t = self.torch
        prompt = self._prompt(system, user)
        enc = self.tok(prompt, return_tensors="pt")
        ids = enc["input_ids"].to(self.device)
        store, handles = {}, []

        def mk(L):
            def fn(_mod, _inp, output):
                h = output[0] if isinstance(output, tuple) else output
                store[L] = h[0, -1, :].detach().float().cpu().clone()
                return output
            return fn

        try:
            for L in layers:
                handles.append(self.model.model.layers[L]
                               .register_forward_hook(mk(L)))
            with t.no_grad():
                self.model(input_ids=ids,
                           attention_mask=enc["attention_mask"].to(self.device),
                           use_cache=False)
        finally:
            for h in handles:
                h.remove()
        return store, int(ids.shape[1])

    def score_with_vector(self, system: str, user: str, answer: str,
                          layer: int | None = None, vector=None) -> float:
        """lp(answer) with the LAST PROMPT position overwritten.

        The index has to be absolute. `score_answer` runs one forward over
        prompt+answer, so position -1 is the last token of the ANSWER, and a
        patch there lands after every position whose logits are scored -- it
        changes nothing and reads as a perfect null. The first version of this
        file made exactly that mistake, and it was visible only because every
        arm returned the untouched baseline to six decimals.
        """
        if vector is None:
            return self.score_answer(system, user, answer)
        n_prompt = len(self.tok(self._prompt(system, user))["input_ids"])
        return self.score_answer(
            system, user, answer,
            hooks=[self.patch_hook(layer, [n_prompt - 1], vector)])

    def decode_with_vector(self, system: str, user: str, layer: int | None = None,
                           vector=None, max_new: int = 12) -> str:
        """Greedy decode after the cue, with the patch applied to the prefill.

        The hook fires on every forward, so it has to be removed after the
        prefill: leaving it on would rewrite the last position of every decode
        step, which is a different intervention (a clamped state) and not the
        one this file is about. `use_cache=True` plus a manual loop is the
        cheapest way to get that boundary exactly right.
        """
        t = self.torch
        enc = self.tok(self._prompt(system, user), return_tensors="pt")
        ids = enc["input_ids"].to(self.device)
        att = enc["attention_mask"].to(self.device)

        handles = []
        try:
            if vector is not None:
                handles.append(self.patch_hook(layer, [-1], vector)(self.model))
            with t.no_grad():
                out = self.model(input_ids=ids, attention_mask=att,
                                 use_cache=True)
        finally:
            for h in handles:
                h.remove()

        past, new = out.past_key_values, []
        nxt = out.logits[0, -1].argmax().view(1, 1)
        for _ in range(max_new):
            new.append(int(nxt.item()))
            if nxt.item() == self.tok.eos_token_id:
                break
            att = t.cat([att, t.ones_like(nxt)], dim=1)
            with t.no_grad():
                out = self.model(input_ids=nxt, attention_mask=att,
                                 past_key_values=past, use_cache=True)
            past = out.past_key_values
            nxt = out.logits[0, -1].argmax().view(1, 1)
        return self.tok.decode(new, skip_special_tokens=True)


def graded(text: str, instance: dict, task_mode: str) -> bool:
    """Correctness of a decoded answer, under whichever protocol produced it.

    In cue mode the decode IS the answer, so it goes straight to the scorer. In
    cot mode it is a reasoning trace ending in an "ANSWER:" line, which is what
    `grade.evaluate` was written to parse -- the same function the behavioural
    run used, so the two numbers mean the same thing.
    """
    if instance.get("dataset", "medcalcbench") != "medcalcbench":
        from howskill import sra_eval
        return bool(sra_eval.evaluate(text, instance)["correct"])
    if task_mode == "cot":
        return bool(grade.evaluate(text, instance)["correct"])
    head = text.strip().splitlines()[0] if text.strip() else ""
    return bool(grade.score(head, instance["eval_data"])["correct"])


def norm_match(v, target):
    return v / (v.norm() + 1e-6) * target.norm()


def cosine(a, b) -> float:
    import torch
    return float(torch.nn.functional.cosine_similarity(
        a.flatten(), b.flatten(), dim=0))


def participation_ratio(mat, centre: bool = False) -> float:
    """Effective number of directions the rows occupy.

    NOTE the default differs from wb_vecstats.participation_ratio, which centres
    by default. Uncentred, this reads ~2 for any set of residual-stream vectors,
    because they share a large common component -- it once reported 2.3 for a set
    whose 42 classes were 92% linearly separable, which is geometrically
    impossible. Pass centre=True whenever the question is how the rows DIFFER,
    which is almost always. Every call site here passes it explicitly for that
    reason.
    """
    import torch
    m = mat.float()
    if centre:
        m = m - m.mean(0, keepdim=True)
    s = torch.linalg.svdvals(m)
    s2 = (s ** 2).sum()
    return float(s2 * s2 / ((s ** 4).sum() + 1e-12))


def pick_instances(cells: dict, instances: dict, keep: list[str],
                   per_calc: int, max_calcs: int, seed: int = 0,
                   min_group: int = 2):
    """Instances grouped by calculator, so a same-skill donor always exists.

    Sampling instance-wise instead would leave most calculators with one
    instance in the set, and the same-calculator donor arm -- the one that
    separates "a property of the skill" from "a property of this note" -- would
    be undefined for them.
    """
    rng = random.Random(seed)
    by_calc: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for cell in keep:
        for iid in cells.get(cell, []):
            inst = instances.get(iid)
            if inst is None:
                continue
            if not single_skill(inst):     # span runs need ONE document per item
                continue
            by_calc[group_key(inst)].append((cell, iid))

    # Balanced across cells inside each calculator. Taking the first
    # `per_calc` of a shuffled mixed list looked fine and produced a sample
    # with R=0 on the first smoke run: the cells are not equally sized (R=366,
    # F=152 overall) and some calculators contribute to only one of them.
    # The R vs F contrast is the point of the file, so the split is enforced.
    usable = {c: v for c, v in by_calc.items() if len(v) >= min_group}
    have_both = [c for c in usable
                 if len({cell for cell, _ in usable[c]}) >= len(keep)]
    order = (sorted(have_both, key=lambda c: -len(usable[c]))
             + sorted(set(usable) - set(have_both),
                      key=lambda c: -len(usable[c])))[:max_calcs]
    out = []
    per_cell = max(1, per_calc // max(1, len(keep)))
    for c in order:
        got = []
        for cell in keep:
            pool = [(cell, i) for cl, i in usable[c] if cl == cell]
            rng.shuffle(pool)
            got.extend(pool[:per_cell])
        out.extend((c, cell, iid) for cell, iid in got)
    return out


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--results", default=None,
                   help="unused; accepted so the command line matches the "
                        "other wb_* tools. The cell lists are read from "
                        "--cells and every prompt is rebuilt from the raw "
                        "data, so no behavioural output is needed here.")
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--cells-keep", default="R,F")
    p.add_argument("--per-calc", type=int, default=4)
    p.add_argument("--max-calcs", type=int, default=18)
    p.add_argument("--layers", default=None,
                   help="explicit comma-separated list; default is a stride")
    p.add_argument("--layer-stride", type=int, default=4)
    p.add_argument("--max-new", type=int, default=12)
    p.add_argument("--task-mode", choices=["cue", "cot"], default="cue",
                   help="cue: score/decode after a forced 'ANSWER: ' (cheap, "
                        "lp only -- the accuracy channel is flat, see the "
                        "module docstring). cot: no cue, decode the whole "
                        "reasoning and grade it (the only channel with an "
                        "effect in it, ~25x the cost).")
    p.add_argument("--no-decode", action="store_true")
    p.add_argument("--gen-cells", default=None,
                   help="only decode for instances in these cells (e.g. R). "
                        "The count channel lives on R -- an F item is wrong "
                        "under every condition by construction, so decoding it "
                        "buys a row of zeros at full price. F instances stay in "
                        "the run: they carry the geometry and the logprob, both "
                        "of which come free with the captures.")
    p.add_argument("--gen-arms", default=None,
                   help="comma-separated arms that get a decode as well as a "
                        "teacher-forced logprob. In cot mode a decode is ~20x "
                        "the cost of a score, so this is what makes the run "
                        "fit. Default: every arm.")
    p.add_argument("--thinking", action="store_true")
    p.add_argument("--attn", default="sdpa", choices=["sdpa", "eager"])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    import torch

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    instances = {i["instance_id"]: i for i in json.load(
        open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
    skills = {s["skill_id"]: s for s in json.load(
        open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}
    pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"),
                          encoding="utf-8"))

    sc = VecScorer(a.model, thinking=a.thinking, attn=a.attn)
    if a.task_mode == "cot":
        sc.cue = ""
        if a.max_new < 64:
            a.max_new = 320
    print(f"task mode: {a.task_mode}   cue={sc.cue!r}   max_new={a.max_new}"
          f"   attn={a.attn}")
    n_layers = sc.model.config.num_hidden_layers
    layers = ([int(x) for x in a.layers.split(",") if x.strip()] if a.layers
              else list(range(0, n_layers, a.layer_stride)))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)

    gen_arms = ({x.strip() for x in a.gen_arms.split(",") if x.strip()}
                if a.gen_arms else None)
    gen_cells = ({x.strip() for x in a.gen_cells.split(",") if x.strip()}
                 if a.gen_cells else None)
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, instances, keep, a.per_calc, a.max_calcs, a.seed)
    print(f"{len(todo)} instances over "
          f"{len({c for c, _, _ in todo})} calculators x {len(layers)} layers")
    print(f"cells: " + "  ".join(
        f"{c}={sum(1 for _, cc, _ in todo if cc == c)}" for c in keep))

    # ---- pass 1: three prompts per instance, three captures ----------------
    rows = []
    for k, (calc, cell, iid) in enumerate(todo, 1):
        inst = instances[iid]
        sid = inst["skill_annotations"][0]
        gold_payload = arms_mod.build(a.arm, skills.get(sid),
                                      neutral_for=skills.get(pairs.get(sid)),
                                      seed=0)
        ctrl_payload = arms_mod.build(a.ctrl_arm, skills.get(sid),
                                      neutral_for=skills.get(pairs.get(sid)),
                                      seed=0)
        sys_g, user_g, _ = build_prompt_spans(inst, skills=gold_payload)
        sys_c, user_c, _ = build_prompt_spans(inst, skills=ctrl_payload)
        sys_0, user_0, _ = build_prompt_spans(inst, skills=[])
        ans = str(inst["eval_data"]["answer"])

        h_g, n_g = sc.capture_all_layers(sys_g, user_g, layers)
        h_c, n_c = sc.capture_all_layers(sys_c, user_c, layers)
        h_0, n_0 = sc.capture_all_layers(sys_0, user_0, layers)

        rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
               "skill_id": sid, "answer": ans,
               "n_tok": {"gold": n_g, "ctrl": n_c, "none": n_0},
               "lp_gold": sc.score_answer(sys_g, user_g, ans),
               "lp_ctrl": sc.score_answer(sys_c, user_c, ans),
               "lp_none": sc.score_answer(sys_0, user_0, ans)}
        if not a.no_decode and (gen_cells is None or cell in gen_cells):
            for tag, (s_, u_) in (("gold", (sys_g, user_g)),
                                  ("ctrl", (sys_c, user_c)),
                                  ("none", (sys_0, user_0))):
                txt = sc.decode_with_vector(s_, u_, max_new=a.max_new)
                rec[f"gen_{tag}"] = txt if a.task_mode == "cue" else txt[-400:]
                rec[f"ok_{tag}"] = graded(txt, inst, a.task_mode)
        rows.append({**rec, "_prompts": (sys_g, user_g, sys_c, user_c,
                                         sys_0, user_0),
                     "_h": (h_g, h_c, h_0), "_inst": inst})
        if k % 5 == 0 or k == len(todo):
            print(f"  captured {k}/{len(todo)}", flush=True)

    n = len(rows)
    if not a.no_decode and any("ok_gold" in r for r in rows):
        for tag in ("none", "ctrl", "gold"):
            v = [r[f"ok_{tag}"] for r in rows if f"ok_{tag}" in r]
            by_cell = {c: [r[f"ok_{tag}"] for r in rows
                           if r["cell"] == c and f"ok_{tag}" in r]
                       for c in keep}
            extra = "  ".join(f"{c} {sum(x)/len(x):.3f} (n={len(x)})"
                              for c, x in by_cell.items() if x)
            what = ("under the ANSWER cue" if a.task_mode == "cue"
                    else "from the full decoded reasoning")
            print(f"  decoded accuracy {what}, {tag:5s}: "
                  f"{sum(v)/len(v):.3f}   [{extra}]")
        if a.task_mode == "cue":
            print("  NOTE: the cue suppresses chain of thought, so these "
                  "numbers are not the behavioural run's and the cells were "
                  "not defined by them. If gold does not beat none HERE, the "
                  "decoded channel cannot carry this experiment.")
        else:
            print("  NOTE: these should reproduce the behavioural cells -- R "
                  "is by definition 0 without the skill and 1 with it. A large "
                  "gap from that is a harness mismatch, not a finding.")
    for tag in ("none", "ctrl", "gold"):
        v = [r[f"lp_{tag}"] for r in rows]
        print(f"  lp(gold answer), {tag:5s}: {sum(v)/len(v):+.4f}")

    # ---- donors ------------------------------------------------------------
    rng = random.Random(a.seed + 1)
    by_calc: dict[str, list[int]] = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by_calc[r["calculator_id"]].append(i)
    same, cross = [None] * n, [None] * n
    for idxs in by_calc.values():
        if len(idxs) >= 2:
            rot = idxs[1:] + idxs[:1]
            for x, y in zip(idxs, rot):
                same[x] = y
    for i, r in enumerate(rows):
        pool = [j for c, ii in by_calc.items() if c != r["calculator_id"]
                for j in ii]
        cross[i] = rng.choice(pool) if pool else None
    print(f"  donors: same-calculator {sum(x is not None for x in same)}/{n}, "
          f"cross-calculator {sum(x is not None for x in cross)}/{n}")

    # ---- pass 2: geometry + injection --------------------------------------
    out_rows, geom = [], {}
    for L in layers:
        D = torch.stack([r["_h"][0][L] - r["_h"][1][L] for r in rows])
        G = torch.stack([r["_h"][1][L] - r["_h"][2][L] for r in rows])
        T = torch.stack([r["_h"][0][L] - r["_h"][2][L] for r in rows])
        H = torch.stack([r["_h"][2][L] for r in rows])
        Dn = torch.nn.functional.normalize(D, dim=-1)
        C = Dn @ Dn.T
        samec = torch.zeros(n, n, dtype=torch.bool)
        for idxs in by_calc.values():
            for x in idxs:
                for y in idxs:
                    if x != y:
                        samec[x, y] = True
        off = ~torch.eye(n, dtype=torch.bool)
        geom[L] = {
            "norm_d": float(D.norm(dim=-1).mean()),
            "norm_g": float(G.norm(dim=-1).mean()),
            "norm_t": float(T.norm(dim=-1).mean()),
            "norm_h_none": float(H.norm(dim=-1).mean()),
            "ratio_d_over_t": float((D.norm(dim=-1) / (T.norm(dim=-1) + 1e-9)).mean()),
            "cos_d_g": float(torch.nn.functional.cosine_similarity(D, G, dim=-1).mean()),
            "cos_dd_same_calc": float(C[samec].mean()) if samec.any() else float("nan"),
            "cos_dd_cross_calc": float(C[off & ~samec].mean()),
            "pr_d_centred": participation_ratio(D, centre=True),
            "pr_g_centred": participation_ratio(G, centre=True),
        }
        for cell in set(r["cell"] for r in rows):
            m = torch.tensor([r["cell"] == cell for r in rows])
            geom[L][f"norm_d_{cell}"] = float(D[m].norm(dim=-1).mean())
            geom[L][f"norm_g_{cell}"] = float(G[m].norm(dim=-1).mean())
            geom[L][f"cos_d_g_{cell}"] = float(
                torch.nn.functional.cosine_similarity(D[m], G[m], dim=-1).mean())

        dbar = D.mean(0)
        dbar = dbar / (dbar.norm() + 1e-6) * D.norm(dim=-1).mean()

        for i, r in enumerate(rows):
            sys_g, user_g, sys_c, user_c, sys_0, user_0 = r["_prompts"]
            ans, inst = r["answer"], r["_inst"]
            h_g, h_c, h_0 = (r["_h"][0][L], r["_h"][1][L], r["_h"][2][L])
            d, g, t = h_g - h_c, h_c - h_0, h_g - h_0

            arms = {"replace_gold": h_g,
                    "add_d": h_0 + d,
                    "add_g": h_0 + g,
                    "add_t": h_0 + t,
                    "add_dbar": h_0 + dbar,
                    "add_d_renorm": norm_match(h_0 + d, h_0)}
            if same[i] is not None:
                arms["add_d_samecalc"] = h_0 + (rows[same[i]]["_h"][0][L]
                                                - rows[same[i]]["_h"][1][L])
            if cross[i] is not None:
                arms["add_d_crosscalc"] = h_0 + (rows[cross[i]]["_h"][0][L]
                                                 - rows[cross[i]]["_h"][1][L])

            rec = {"instance_id": r["instance_id"], "cell": r["cell"],
                   "calculator_id": r["calculator_id"], "layer": L,
                   "lp_gold": r["lp_gold"], "lp_ctrl": r["lp_ctrl"],
                   "lp_none": r["lp_none"],
                   "norm_d": float(d.norm()), "norm_g": float(g.norm()),
                   "norm_t": float(t.norm()), "cos_d_g": cosine(d, g),
                   "cos_d_hnone": cosine(d, h_0)}
            for tag in ("gold", "ctrl", "none"):
                if f"ok_{tag}" in r:
                    rec[f"ok_{tag}"] = r[f"ok_{tag}"]
            for name, vec in arms.items():
                rec[f"lp_{name}"] = sc.score_with_vector(sys_0, user_0, ans, L, vec)
                if (not a.no_decode
                        and (gen_arms is None or name in gen_arms)
                        and (gen_cells is None or r["cell"] in gen_cells)):
                    txt = sc.decode_with_vector(sys_0, user_0, L, vec, a.max_new)
                    rec[f"ok_{name}"] = graded(txt, inst, a.task_mode)
            # receiver = the WRONG-skill prompt, same vectors
            rec["lp_ctrlrx_replace_gold"] = sc.score_with_vector(
                sys_c, user_c, ans, L, h_g)
            rec["lp_ctrlrx_add_dbar"] = sc.score_with_vector(
                sys_c, user_c, ans, L, h_c + dbar)
            if not a.no_decode:
                for nm, vec in (("ctrlrx_replace_gold", h_g),
                                ("ctrlrx_add_dbar", h_c + dbar)):
                    if gen_arms is not None and nm not in gen_arms:
                        continue
                    if gen_cells is not None and r["cell"] not in gen_cells:
                        continue
                    txt = sc.decode_with_vector(sys_c, user_c, L, vec, a.max_new)
                    rec[f"ok_{nm}"] = graded(txt, inst, a.task_mode)
            out_rows.append(rec)
        print(f"  layer {L:3d} done ({len(out_rows)} rows)", flush=True)

    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "meta", "layers": layers,
                             "n": n, "arm": a.arm, "ctrl_arm": a.ctrl_arm,
                             "geometry": {str(L): geom[L] for L in layers}}) + "\n")
        for rec in out_rows:
            fh.write(json.dumps(rec) + "\n")

    print("\n  L   ||d||   ||g||  d/t  cos(d,g)  cos_dd_same cos_dd_cross  PRc_d")
    for L in layers:
        z = geom[L]
        print(f"  {L:3d} {z['norm_d']:7.1f} {z['norm_g']:7.1f} "
              f"{z['ratio_d_over_t']:5.2f} {z['cos_d_g']:8.3f} "
              f"{z['cos_dd_same_calc']:11.3f} {z['cos_dd_cross_calc']:12.3f} "
              f"{z['pr_d_centred']:6.1f}")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
