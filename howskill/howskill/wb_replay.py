"""Teacher-forced replay on HF transformers, and the M1/M2/M3 readouts.

    python -m howskill.wb_replay --results results/p8-step \
        --cells data/cells.json --model $BASE/models/Qwen3-8B \
        --out results/p8-wb/profiles.jsonl

Two-stage by design (PROTOCOL.md §3, P8): vLLM generates, transformers replays
the same tokens in a single forward pass. Nothing here generates text. The
replay must reproduce what vLLM produced, and GATE-W0 checks that before any
internal number is believed — a chat template that differs by one token, or a
thinking flag that differs, shifts every position by one and every span-indexed
measurement silently describes the wrong tokens.

What one instance costs: two forwards, with the skill and without. Hidden
states are sliced to the spans and reduced to scalars layer by layer, never
held whole — 36 layers x 2k tokens x 4096 dims is over a gigabyte per run in
float32, and two of those do not fit next to an 8B model on a 4090.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

import numpy as np

from howskill import arms as arms_mod
from howskill.prompts import build_prompt_spans
from howskill.wb_metrics import kl_divergence, linear_cka, span_profile
from howskill.wb_spans import char_to_token_span, subsample

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


# ---------------------------------------------------------------------------
# model side
# ---------------------------------------------------------------------------

class Replayer:
    def __init__(self, model_path: str, thinking: bool = False,
                 device: str = "cuda", dtype: str = "bfloat16"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.thinking = thinking
        self.tok = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=getattr(torch, dtype),
            device_map=device, attn_implementation="eager")
        self.model.eval()
        self.device = device

    def build_inputs(self, system: str, user: str, assistant: str):
        """Templated prompt + the recorded completion, and the offset mapping.

        ``add_generation_prompt=True`` then concatenating the assistant text is
        what makes this teacher forcing rather than a fresh conversation: the
        model sees exactly the tokens it produced under vLLM.
        """
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        prompt = self.tok.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True,
            enable_thinking=self.thinking)
        full = prompt + assistant
        enc = self.tok(full, return_offsets_mapping=True, return_tensors="pt")
        base = prompt.rindex(user)
        n_prompt = len(self.tok(prompt)["input_ids"])
        return enc, base, n_prompt

    def forward(self, enc):
        t = self.torch
        with t.no_grad():
            out = self.model(
                input_ids=enc["input_ids"].to(self.device),
                attention_mask=enc["attention_mask"].to(self.device),
                output_hidden_states=True, use_cache=False)
        return out

    def layer_span(self, out, layer: int, idx: list[int]) -> np.ndarray:
        """One layer's hidden states at the given positions, as float64 numpy."""
        h = out.hidden_states[layer][0, idx, :]
        return h.to(self.torch.float32).cpu().numpy().astype(np.float64)

    def token_logprobs(self, out, enc, start: int) -> np.ndarray:
        """Log-probability of each actually-present token from ``start`` on."""
        t = self.torch
        logits = out.logits[0].float()
        ids = enc["input_ids"][0].to(logits.device)
        lp = t.log_softmax(logits[:-1], dim=-1)
        got = lp.gather(1, ids[1:].unsqueeze(1)).squeeze(1)
        return got[start - 1:].cpu().numpy().astype(np.float64)


# ---------------------------------------------------------------------------
# GATE-W0
# ---------------------------------------------------------------------------

def vllm_logprobs(row: dict) -> list[float] | None:
    """Pull the per-token logprobs vLLM recorded, if the run asked for them."""
    for turn in (row.get("trajectory") or {}).get("turns", []):
        lp = (turn.get("meta") or {}).get("logprobs")
        if lp and lp.get("content"):
            return [c["logprob"] for c in lp["content"]]
    return None


def gate_w0(ours: np.ndarray, theirs: list[float]) -> dict:
    """Compare replayed logprobs against the generator's.

    Correlation alone is too forgiving — a one-token shift still correlates
    highly on smooth sequences — so the mean absolute difference is reported
    with it, and both have to pass.
    """
    n = min(len(ours), len(theirs))
    if n < 5:
        return {"n": n, "ok": False, "reason": "too few tokens to compare"}
    a = np.asarray(ours[:n], dtype=np.float64)
    b = np.asarray(theirs[:n], dtype=np.float64)
    if np.std(a) < 1e-9 or np.std(b) < 1e-9:
        corr = float("nan")
    else:
        corr = float(np.corrcoef(a, b)[0, 1])
    mad = float(np.mean(np.abs(a - b)))
    return {"n": n, "corr": corr, "mad": mad,
            "ok": bool(corr >= 0.99 and mad <= 0.05)}


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def load_rows(results_dir: str, needle: str) -> dict:
    hits = [f for f in sorted(glob.glob(os.path.join(results_dir, "*.jsonl")))
            if needle in os.path.basename(f)]
    if not hits:
        raise SystemExit(f"no arm matching {needle!r} in {results_dir}")
    rows = {}
    with open(hits[0], encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                if "error" not in r:
                    rows[r["instance_id"]] = r
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True)
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--without", default="no_skill")
    p.add_argument("--with", dest="with_", default="gold_no_tool")
    p.add_argument("--arm", default="gold_no_tool",
                   help="arm name for rebuilding the with-skill prompt")
    p.add_argument("--cells-keep", default="R,F",
                   help="which cells to replay (default the core contrast)")
    p.add_argument("--n-per-cell", type=int, default=150)
    p.add_argument("--max-span-tokens", type=int, default=256)
    p.add_argument("--thinking", action="store_true")
    p.add_argument("--layer-stride", type=int, default=1)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    a0 = load_rows(a.results, a.without)
    a1 = load_rows(a.results, a.with_)
    instances = {i["instance_id"]: i for i in json.load(
        open(os.path.join(DATA, "medcalcbench.json"), encoding="utf-8"))}
    skills = {s["skill_id"]: s for s in json.load(
        open(os.path.join(DATA, "medcalc_skills.json"), encoding="utf-8"))}
    pairs = json.load(open(os.path.join(DATA, "neutral_pairs.json"),
                           encoding="utf-8"))

    rep = Replayer(a.model, thinking=a.thinking)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)

    want = [c.strip() for c in a.cells_keep.split(",") if c.strip()]
    todo = [(c, iid) for c in want for iid in cells.get(c, [])[:a.n_per_cell]]
    print(f"replaying {len(todo)} instances from cells {want}")

    n_gate_fail = 0
    with open(a.out, "w", encoding="utf-8") as fh:
        for k, (cell, iid) in enumerate(todo, 1):
            inst = instances[iid]
            sid = inst["skill_annotations"][0]
            gold = skills.get(sid)
            neutral = skills.get(pairs.get(sid))
            payload = arms_mod.build(a.arm, gold, neutral_for=neutral, seed=0)

            sys1, user1, sp1 = build_prompt_spans(inst, skills=payload,
                                                  tool_protocol=False)
            sys0, user0, sp0 = build_prompt_spans(inst, skills=[],
                                                  tool_protocol=False)

            rec = {"instance_id": iid, "cell": cell,
                   "calculator_id": inst["eval_data"]["calculator_id"]}

            # The prompt we rebuild must be the prompt that was run.
            import hashlib
            if a1[iid].get("user_sha1") and hashlib.sha1(
                    user1.encode("utf-8")).hexdigest() != a1[iid]["user_sha1"]:
                rec["error"] = "prompt digest mismatch — rebuilt prompt differs"
                fh.write(json.dumps(rec) + "\n")
                continue

            out_rows = {}
            keep_task = None
            for tag, (sysm, user, sp, row) in {
                    "with": (sys1, user1, sp1, a1[iid]),
                    "without": (sys0, user0, sp0, a0[iid])}.items():
                text = (row.get("trajectory") or {}).get("model_output") or ""
                enc, base, n_prompt = rep.build_inputs(sysm, user, text)
                offs = enc["offset_mapping"][0].tolist()
                out = rep.forward(enc)

                g = gate_w0(rep.token_logprobs(out, enc, n_prompt),
                            vllm_logprobs(row) or [])
                rec[f"gate_w0_{tag}"] = g
                if not g["ok"]:
                    n_gate_fail += 1

                t_lo, t_hi = char_to_token_span(offs, *sp["task"], base=base)
                idx_task = subsample(t_lo, t_hi, a.max_span_tokens)
                if keep_task is None:
                    keep_task = len(idx_task)
                else:
                    # both conditions must contribute the same number of aligned
                    # positions, or CKA is comparing different token counts
                    idx_task = idx_task[:keep_task]

                n_layers = len(out.hidden_states)
                layers = list(range(0, n_layers, a.layer_stride))
                prof, acts = [], []
                for L in layers:
                    Z = rep.layer_span(out, L, idx_task)
                    prof.append(span_profile(Z))
                    acts.append(Z.astype(np.float32))
                rec[f"task_profile_{tag}"] = prof

                if sp["skill"]:
                    s_lo, s_hi = char_to_token_span(offs, *sp["skill"], base=base)
                    idx_sk = subsample(s_lo, s_hi, a.max_span_tokens)
                    rec["skill_profile"] = [
                        span_profile(rep.layer_span(out, L, idx_sk))
                        for L in layers]
                    rec["skill_n_tokens"] = s_hi - s_lo

                out_rows[tag] = acts
                rec["layers"] = layers
                del out

            if "with" in out_rows and "without" in out_rows:
                rec["cka_task"] = [
                    linear_cka(x, y)
                    for x, y in zip(out_rows["with"], out_rows["without"])]

            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if k % 10 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)}  gate_w0 failures so far: {n_gate_fail}",
                      flush=True)

    print(f"\n-> {a.out}")
    if n_gate_fail:
        print(f"[FAIL] GATE-W0 failed on {n_gate_fail} forwards. The replay does "
              f"not reproduce generation; every internal number above is "
              f"suspect. Check the chat template, --thinking, and whether the "
              f"run was made with --logprobs.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
