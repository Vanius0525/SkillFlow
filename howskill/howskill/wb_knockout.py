"""M4a -- necessity on real skills: make the document unattendable and decode.

    python -m howskill.wb_knockout --cells data/cells.json \
        --model $BASE/models/Qwen3-8B --out results/p8-wb/knockout.jsonl

wb_patch.py already has a knockout, but it scores under the "\nANSWER: " cue,
and on this material that cue removes the behavioural effect entirely (40
instances, Qwen3-8B: 0.175 accuracy for no-skill, wrong-skill AND gold-skill
alike, while lp(gold) still moves by +0.60 nats). A necessity test whose
dependent variable does not move when the skill is added cannot detect the
skill being taken away. So this file decodes the full chain of thought and
grades it with the run's own scorer.

Two questions, two knockout families:

  span      zero the attention mask over the skill's token span for the whole
            forward. Answers "is the document read at all". A length-matched
            control span inside the task text is masked alongside, because
            removing any 600 tokens changes the answer somewhat -- without it
            the arm measures prompt length.

  by-layer  block attention TO the skill span from layer L onward (cumulative),
            with a 4D additive mask. Answers "after which layer does the model
            no longer need the document". On the synthetic tier that answer was
            layer 21 of 28, and it lined up with the layer at which the
            final-position transplant became item-specific. Whether the same
            structure exists on real skills is the point of this file.

Cumulative rather than single-layer, deliberately. A single-layer knockout on a
600-token span measures nothing: the layer denied the read recovers it one layer
later, and the synthetic tier measured exactly that null with a matched
query-side control confirming the instrument was live.

REQUIRES eager attention for --sweep layers: sdpa and flash silently ignore a
4D mask, which would make every layer report the unmasked baseline and look
like a clean null.
"""

from __future__ import annotations

import argparse
import collections
import json
import os

from howskill import arms as arms_mod
from howskill import grade
from howskill.prompts import build_prompt_spans
from howskill.wb_diffvec import VecScorer, graded, pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spans import char_to_token_span

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
NEG = -1e30


class KnockoutScorer(VecScorer):
    def spans_for(self, system: str, user: str, spans: dict):
        """Token spans of the skill block and the task text in the full prompt."""
        prompt = self._prompt(system, user)
        enc = self.tok(prompt, return_offsets_mapping=True, return_tensors="pt")
        offs = enc["offset_mapping"][0].tolist()
        base = prompt.rindex(user)
        out = {}
        for name in ("skill", "task"):
            if spans.get(name):
                out[name] = char_to_token_span(offs, *spans[name], base=base)
        out["n_prompt"] = int(enc["input_ids"].shape[1])
        return out

    def decode_masked(self, system: str, user: str, mask_spans=None,
                      block_from_layer=None, key_span=None, max_new=400) -> str:
        """Greedy decode with a span made unattendable.

        `mask_spans` uses the 2D attention mask, which every attention
        implementation honours and which also removes the positions from the
        KV cache's effective content for the generated tokens. `block_from_layer`
        needs a 4D additive mask, hence eager.
        """
        t = self.torch
        enc = self.tok(self._prompt(system, user), return_tensors="pt")
        ids = enc["input_ids"].to(self.device)
        att = enc["attention_mask"].to(self.device).clone()
        for lo, hi in (mask_spans or []):
            att[0, lo:hi] = 0

        handles = []
        if block_from_layer is not None:
            lo, hi = key_span
            n_layers = self.model.config.num_hidden_layers

            def mk():
                def fn(module, args, kwargs):
                    m = kwargs.get("attention_mask")
                    if m is None or m.dim() != 4:
                        return None
                    m = m.clone()
                    m[..., lo:hi] = NEG
                    kwargs["attention_mask"] = m
                    return args, kwargs
                return fn

            for L in range(block_from_layer, n_layers):
                handles.append(self.model.model.layers[L].self_attn
                               .register_forward_pre_hook(mk(), with_kwargs=True))
        try:
            with t.no_grad():
                out = self.model(input_ids=ids, attention_mask=att, use_cache=True)
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
        finally:
            for h in handles:
                h.remove()
        return self.tok.decode(new, skip_special_tokens=True)



def resume_done(path: str) -> set:
    """instance_ids already written to `path`, for --resume.

    The platform reclaims these boxes on its own schedule, so a multi-hour run
    is expected to be interrupted rather than merely at risk of it. Every writer
    here flushes per instance, so the file is always a valid prefix; resuming
    means skipping those ids and appending. Without this a reclaim at 24/40
    costs the whole run.
    """
    done = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue          # a half-written last line
                if r.get("instance_id"):
                    done.add(r["instance_id"])
    except FileNotFoundError:
        pass
    return done



class _OutputLock:
    """Exclusive lock on an output file, so two copies of a run cannot both
    append to it.

    --resume reads the file once, at startup. If the same command is launched
    twice -- easy to do when an ssh call times out before printing its
    acknowledgement, which happens routinely on this cluster's proxy -- both
    copies see the same set of finished instances and both write all the rest.
    It produced 25 duplicate rows before anyone noticed, and duplicates weight
    some instances more than others in every mean computed downstream.

    flock is advisory and process-local to this file, which is exactly the
    scope needed: the second copy exits with a message instead of silently
    doubling the data.
    """

    def __init__(self, path: str):
        self.path = path + ".lock"
        self.fh = None

    def __enter__(self):
        import fcntl
        self.fh = open(self.path, "w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit(
                f"[FAIL] another run already holds {self.path}. Two writers "
                f"appending to one output file produce duplicate rows that no "
                f"downstream mean can distinguish from real ones. Wait for it, "
                f"or use a different --out.")
        self.fh.write(str(os.getpid()))
        self.fh.flush()
        return self

    def __exit__(self, *exc):
        import fcntl
        if self.fh:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()
        return False


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--dataset", default="medcalcbench",
                   help="an SRA-Bench family wired in howskill/sra.py")
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--cells-keep", default="R,F")
    p.add_argument("--per-calc", type=int, default=4)
    p.add_argument("--min-group", type=int, default=2,
                   help="smallest group of same-document items kept; 1 admits "
                        "singleton skills (TheoremQA), where no same-document "
                        "donor arm is defined and the restriction is per item")
    p.add_argument("--max-calcs", type=int, default=10)
    p.add_argument("--max-new", type=int, default=400)
    p.add_argument("--sweep", choices=["span", "layers", "both"], default="span")
    p.add_argument("--layer-stride", type=int, default=4)
    p.add_argument("--layers", default="",
                   help="explicit comma-separated block-from layers, overriding "
                        "--layer-stride (used to fill a stride-4 sweep to one-"
                        "layer resolution without redoing the layers it has)")
    p.add_argument("--calcs", default="",
                   help="comma-separated group ids to keep (calculators, or "
                        "skills on TheoremQA)")
    p.add_argument("--ids-from", default="",
                   help="a previous knockout jsonl: keep only its items with "
                        "ok_with and not ok_without -- the items the reading "
                        "curve is computed on -- so a fill-in run decodes "
                        "nothing that cannot enter the curve")
    p.add_argument("--no-baselines", action="store_true",
                   help="skip ok_with / ok_without; they are merged by "
                        "instance_id from the run named in --ids-from")
    p.add_argument("--attn", default=None,
                   help="default: sdpa for --sweep span, eager for layers")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    p.add_argument("--resume", action="store_true",
                   help="append to --out, skipping instances already in it")
    a = p.parse_args(argv)

    need_eager = a.sweep in ("layers", "both")
    attn = a.attn or ("eager" if need_eager else "sdpa")
    if need_eager and attn != "eager":
        raise SystemExit("[FAIL] --sweep layers needs eager attention: sdpa and "
                         "flash ignore the 4D mask and every layer would report "
                         "the unmasked baseline.")

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    from howskill import sra
    instances, skills, pairs, _ = sra.load(a.dataset)

    sc = KnockoutScorer(a.model, attn=attn)
    sc.cue = ""                                  # cot: the effect lives here
    n_layers = sc.model.config.num_hidden_layers
    layers = ([int(x) for x in a.layers.split(",") if x.strip()] if a.layers
              else list(range(0, n_layers, a.layer_stride)))
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, instances, keep, a.per_calc, a.max_calcs, a.seed, min_group=a.min_group)
    if a.calcs:
        only = {c.strip() for c in a.calcs.split(",") if c.strip()}
        todo = [t for t in todo if t[0] in only]
    if a.ids_from:
        keep_ids = set()
        for line in open(a.ids_from, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("ok_with") and not r.get("ok_without"):
                    keep_ids.add(r["instance_id"])
        todo = [t for t in todo if t[2] in keep_ids]
    if a.no_baselines and not a.ids_from:
        raise SystemExit("--no-baselines needs --ids-from to say which run has them")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    done = resume_done(a.out) if a.resume else set()
    if done:
        todo = [t for t in todo if t[2] not in done]
        print(f"[resume] {len(done)} instances already in {a.out}; "
              f"{len(todo)} left")
    print(f"{len(todo)} instances, attn={attn}, sweep={a.sweep}, "
          f"layers={layers if need_eager else '-'}")

    agg = collections.defaultdict(list)
    with _OutputLock(a.out), \
            open(a.out, "a" if a.resume else "w", encoding="utf-8") as fh:
        for k, (calc, cell, iid) in enumerate(todo, 1):
            inst = instances[iid]
            sid = inst["skill_annotations"][0]
            payload = arms_mod.build(a.arm, skills.get(sid),
                                     neutral_for=skills.get(pairs.get(sid)),
                                     seed=0)
            sys1, user1, sp1 = build_prompt_spans(inst, skills=payload)
            sys0, user0, _ = build_prompt_spans(inst, skills=[])
            sp = sc.spans_for(sys1, user1, sp1)
            sk_lo, sk_hi = sp["skill"]
            tk_lo, tk_hi = sp["task"]
            m = min(sk_hi - sk_lo, tk_hi - tk_lo)

            rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
                   "dataset": a.dataset,
                   "skill_tokens": sk_hi - sk_lo, "task_tokens": tk_hi - tk_lo}
            if not a.no_baselines:
                rec["ok_with"] = graded(sc.decode_masked(
                    sys1, user1, max_new=a.max_new), inst, "cot")
                rec["ok_without"] = graded(sc.decode_masked(
                    sys0, user0, max_new=a.max_new), inst, "cot")
            if a.sweep in ("span", "both"):
                rec["ok_mask_skill"] = graded(sc.decode_masked(
                    sys1, user1, mask_spans=[(sk_lo, sk_hi)],
                    max_new=a.max_new), inst, "cot")
                rec["ok_mask_ctrl"] = graded(sc.decode_masked(
                    sys1, user1, mask_spans=[(tk_lo, tk_lo + m)],
                    max_new=a.max_new), inst, "cot")
            if a.sweep in ("layers", "both"):
                rec["layers"] = layers
                rec["ok_block_from"] = [
                    graded(sc.decode_masked(
                        sys1, user1, block_from_layer=L,
                        key_span=(sk_lo, sk_hi), max_new=a.max_new), inst, "cot")
                    for L in layers]
            for key, v in rec.items():
                if key.startswith("ok_") and isinstance(v, bool):
                    agg[key].append(v)
                    agg[f"{key}|{cell}"].append(v)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if k % 5 == 0 or k == len(todo):
                base = ("  ".join(f"{key.replace('ok_',''):>11} "
                                  f"{sum(agg[key])/len(agg[key]):.3f}"
                                  for key in sorted(agg) if "|" not in key))
                print(f"  {k}/{len(todo)}   {base}", flush=True)

    print("\n=== summary ===")
    for key in sorted(agg):
        v = agg[key]
        print(f"  {key:26s} n={len(v):3d}  {sum(v)/len(v):.3f}")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
