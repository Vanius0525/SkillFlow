"""M4 — the causal half: residual patching and skill-span knockout.

    python -m howskill.wb_patch --results results/p8-step \
        --cells data/cells.json --model $BASE/models/Qwen3-8B \
        --out results/p8-wb/patch.jsonl

M1-M3 describe what differs when the skill is present. Only this file argues
that the difference does anything. Two interventions:

  knockout   run the with-skill prompt but make the skill's tokens
             unattendable, and measure what the answer loses. Answers "is the
             skill read at all, or is the gain a side effect of a longer
             prompt". A length-matched control span is run alongside, because
             removing any 600 tokens changes the answer somewhat.

  patch      copy the with-skill run's residual state at layer L and a chosen
             set of positions into the without-skill run, and measure how much
             of the skill's benefit comes back. Sweeping L and the position
             group separates "the answer is read out of the skill's own
             positions" from "the skill changed how the question is read".

The target is the gold answer's log-probability under teacher forcing, not the
model's own generated text: the generated text differs between conditions, and
scoring each condition on its own output would compare two different questions.

Recovery is (patched - without) / (with - without): 1.0 reproduces the whole
behavioural effect of the document, 0.0 reproduces none. Values above 1 are
recorded as they are, not clipped -- an intervention that overshoots is a
finding, and clipping would hide it.
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

from howskill import arms as arms_mod
from howskill.prompts import build_prompt_spans
from howskill.wb_replay import Replayer, load_rows
from howskill.wb_spans import char_to_token_span

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

ANSWER_CUE = "\nANSWER: "


class Scorer(Replayer):
    """Replayer plus a fixed target: the log-probability of the gold answer."""

    def score_answer(self, system: str, user: str, answer: str,
                     hooks=None, mask_spans=None) -> float:
        t = self.torch
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        prompt = self.tok.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
            enable_thinking=self.thinking) + ANSWER_CUE
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

    def capture(self, system: str, user: str, answer: str, layer: int,
                positions: list[int]) -> "np.ndarray":
        """Donor states: layer ``layer`` output at ``positions``."""
        store = {}

        def hook(model):
            def fn(_mod, _inp, output):
                h = output[0] if isinstance(output, tuple) else output
                store["h"] = h[0, positions, :].detach().clone()
                return output
            return model.model.layers[layer].register_forward_hook(fn)

        self.score_answer(system, user, answer, hooks=[hook])
        return store["h"]

    def patch_hook(self, layer: int, positions: list[int], donor):
        """Write donor states into the recipient run at the same layer."""
        def hook(model):
            def fn(_mod, _inp, output):
                tup = isinstance(output, tuple)
                h = output[0] if tup else output
                h = h.clone()
                h[0, positions, :] = donor.to(h.dtype).to(h.device)
                return (h,) + tuple(output[1:]) if tup else h
            return model.model.layers[layer].register_forward_hook(fn)
        return hook


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--cells-keep", default="R,F")
    p.add_argument("--n-per-cell", type=int, default=40)
    p.add_argument("--layer-stride", type=int, default=4)
    p.add_argument("--max-patch-tokens", type=int, default=128)
    p.add_argument("--thinking", action="store_true")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    instances = {i["instance_id"]: i for i in json.load(
        open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
    skills = {s["skill_id"]: s for s in json.load(
        open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}
    pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"),
                           encoding="utf-8"))

    sc = Scorer(a.model, thinking=a.thinking)
    n_layers = sc.model.config.num_hidden_layers
    layers = list(range(0, n_layers, a.layer_stride))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)

    todo = [(c, i) for c in [x.strip() for x in a.cells_keep.split(",")]
            for i in cells.get(c, [])[:a.n_per_cell]]
    print(f"{len(todo)} instances x {len(layers)} layers")

    with open(a.out, "w", encoding="utf-8") as fh:
        for k, (cell, iid) in enumerate(todo, 1):
            inst = instances[iid]
            sid = inst["skill_annotations"][0]
            payload = arms_mod.build(a.arm, skills.get(sid),
                                     neutral_for=skills.get(pairs.get(sid)),
                                     seed=0)
            sys1, user1, sp1 = build_prompt_spans(inst, skills=payload,
                                                  tool_protocol=False)
            sys0, user0, sp0 = build_prompt_spans(inst, skills=[],
                                                  tool_protocol=False)
            ans = str(inst["eval_data"]["answer"])

            s_with = sc.score_answer(sys1, user1, ans)
            s_without = sc.score_answer(sys0, user0, ans)
            denom = s_with - s_without
            rec = {"instance_id": iid, "cell": cell, "layers": layers,
                   "s_with": s_with, "s_without": s_without, "denom": denom}

            # --- knockout: make the skill unattendable in the with-skill run
            enc1 = sc.tok(sc.tok.apply_chat_template(
                [{"role": "system", "content": sys1},
                 {"role": "user", "content": user1}],
                tokenize=False, add_generation_prompt=True,
                enable_thinking=a.thinking) + ANSWER_CUE,
                return_offsets_mapping=True, return_tensors="pt")
            offs1 = enc1["offset_mapping"][0].tolist()
            prompt1 = sc.tok.apply_chat_template(
                [{"role": "system", "content": sys1},
                 {"role": "user", "content": user1}],
                tokenize=False, add_generation_prompt=True,
                enable_thinking=a.thinking)
            base1 = prompt1.rindex(user1)
            sk_lo, sk_hi = char_to_token_span(offs1, *sp1["skill"], base=base1)
            tk_lo, tk_hi = char_to_token_span(offs1, *sp1["task"], base=base1)
            rec["skill_tokens"] = sk_hi - sk_lo
            rec["knockout_skill"] = sc.score_answer(
                sys1, user1, ans, mask_spans=[(sk_lo, sk_hi)])
            # length-matched control: the same number of task tokens
            n = min(sk_hi - sk_lo, tk_hi - tk_lo)
            rec["knockout_ctrl"] = sc.score_answer(
                sys1, user1, ans, mask_spans=[(tk_lo, tk_lo + n)])

            # --- patch: donor states from the with-skill run into the without
            t0, t1 = tk_lo, tk_hi
            prompt0 = sc.tok.apply_chat_template(
                [{"role": "system", "content": sys0},
                 {"role": "user", "content": user0}],
                tokenize=False, add_generation_prompt=True,
                enable_thinking=a.thinking)
            enc0 = sc.tok(prompt0 + ANSWER_CUE, return_offsets_mapping=True,
                          return_tensors="pt")
            base0 = prompt0.rindex(user0)
            u0_lo, u0_hi = char_to_token_span(
                enc0["offset_mapping"][0].tolist(), *sp0["task"], base=base0)

            m = min(t1 - t0, u0_hi - u0_lo, a.max_patch_tokens)
            src = list(range(t1 - m, t1))
            dst = list(range(u0_hi - m, u0_hi))
            rec["n_patched"] = m

            rows = []
            for L in layers:
                donor = sc.capture(sys1, user1, ans, L, src)
                s_p = sc.score_answer(sys0, user0, ans,
                                      hooks=[sc.patch_hook(L, dst, donor)])
                rows.append({"layer": L, "score": s_p,
                             "recovery": (s_p - s_without) / denom
                             if abs(denom) > 1e-6 else float("nan")})
            rec["patch_task_tail"] = rows

            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if k % 5 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)}", flush=True)

    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
