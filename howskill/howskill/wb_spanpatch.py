"""M6 -- span transplants on real skills, scored by decoding the reasoning.

    python -m howskill.wb_spanpatch --cells data/cells.json \
        --model $BASE/models/Qwen3-8B --out results/p8-wb/spanpatch.jsonl

Why this exists. On the synthetic tier the content of a document is readable
from three different position groups at three different depths: the document's
own tokens early, the question's tokens in the middle, and the final prompt
position late. The final-position channel is the one every activation-patching
paper uses, and it is the one that collapses as soon as the answer stops being a
single token -- on this material, where the answer arrives after a few hundred
tokens of arithmetic, replacing the final position with the with-skill state
repairs 1 of 20 rescued items. So if the content is recoverable at all here, it
is recoverable from a span, and that is what this file tests.

WHAT IS TRANSPLANTED

The last `m` tokens of the QUESTION span, from the with-skill forward into the
without-skill forward, at one layer. The two prompts have different lengths (the
skill is 600-odd tokens), so the spans are aligned by their ENDS and truncated to
the shorter of the two -- absolute indices would put the donor's states on the
wrong words. This is the same alignment wb_patch.py uses; what is new is the
dependent variable.

DEPENDENT VARIABLE

The full chain of thought, decoded greedily under the patch and graded by the
run's own deterministic scorer. Not the cue-forced answer: under
"\nANSWER: " this material shows 0.175 accuracy for gold, wrong and no skill
alike, so a patch has nothing to restore (see wb_diffvec's docstring).

CONTROLS, all decoded the same way

    none          no patch                              lower reference
    self          the receiver's OWN states at the same positions -- must be an
                  exact no-op at every layer, and is the check that the patch
                  writes where the capture read
    ctrl          the states from the WRONG-skill forward, same positions
                  -- the presence control, and the one that decides whether a
                  recovery is about content
"""

from __future__ import annotations

import argparse
import collections
import json
import os

from howskill import arms as arms_mod
from howskill.prompts import build_prompt_spans
from howskill.wb_diffvec import VecScorer, graded, pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spans import char_to_token_span

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


class SpanScorer(VecScorer):
    def prompt_and_spans(self, system: str, user: str, spans: dict):
        prompt = self._prompt(system, user)
        enc = self.tok(prompt, return_offsets_mapping=True, return_tensors="pt")
        offs = enc["offset_mapping"][0].tolist()
        base = prompt.rindex(user)
        out = {"n": int(enc["input_ids"].shape[1])}
        for name in ("skill", "task"):
            if spans.get(name):
                out[name] = char_to_token_span(offs, *spans[name], base=base)
        return enc, out

    def capture_span(self, system: str, user: str, layer: int, positions):
        store = {}

        def fn(_mod, _inp, output):
            h = output[0] if isinstance(output, tuple) else output
            store["h"] = h[0, positions, :].detach().clone()
            return output

        handle = self.model.model.layers[layer].register_forward_hook(fn)
        try:
            enc = self.tok(self._prompt(system, user), return_tensors="pt")
            with self.torch.no_grad():
                self.model(input_ids=enc["input_ids"].to(self.device),
                           attention_mask=enc["attention_mask"].to(self.device),
                           use_cache=False)
        finally:
            handle.remove()
        return store["h"]

    def prompt_ids(self, system: str, user: str):
        enc = self.tok(self._prompt(system, user), return_tensors="pt")
        return enc["input_ids"]

    def matched_receiver(self, ids_gold, span, filler_ids):
        """`ids_gold` with the skill span overwritten by filler tokens.

        This is the whole point of the rewrite. The first version of this file
        patched a donor span captured at absolute positions ~919-1812 into a
        receiver at ~0-893, because the no-skill prompt is ~900 tokens shorter.
        RoPE makes those different positions, and both the real and the
        wrong-skill arm read 0.200 -- the signature of two arms broken the same
        way, not of an absent effect. Substituting tokens in place keeps the two
        sequences the same length, identical outside the skill span, and aligned
        in RoPE phase, which is how e10_span.py and e12_taskspan.py have always
        built their receivers.

        A consequence worth stating: with a matched receiver the content
        component and the full transplant coincide, since
        h_recv(span) + (h_gold(span) - h_recv(span)) = h_gold(span). The
        presence control is no longer a separate arm -- it is built into the
        receiver, which already contains a document.
        """
        lo, hi = span
        width = hi - lo
        if filler_ids.shape[1] < width:
            reps = width // filler_ids.shape[1] + 1
            filler_ids = filler_ids.repeat(1, reps)
        out = ids_gold.clone()
        out[0, lo:hi] = filler_ids[0, :width]
        return out

    def capture_ids(self, ids, layer: int, positions):
        """Read the span's states out of one forward pass.

        The attention mask is passed explicitly, and must be: omitting it for a
        single unpadded sequence is mathematically the same but takes a
        different kernel (sdpa's is_causal fast path rather than an explicit
        mask), and the two disagree by up to 1.2% of the state's magnitude at
        layer 8 and 25% at layer 34. Since `decode_ids` does pass a mask, a
        capture without one produced a donor that was not quite the state the
        receiver's own forward would have produced -- which is why writing the
        receiver's states back over themselves, an exact identity on paper,
        changed the answer on 5% of items. `use_cache` was checked at the same
        time and makes no difference (bitwise identical).
        """
        store = {}

        def fn(_mod, _inp, output):
            h = output[0] if isinstance(output, tuple) else output
            store["h"] = h[0, positions, :].detach().clone()
            return output

        ids = ids.to(self.device)
        handle = self.model.model.layers[layer].register_forward_hook(fn)
        try:
            with self.torch.no_grad():
                self.model(input_ids=ids,
                           attention_mask=self.torch.ones_like(ids),
                           use_cache=False)
        finally:
            handle.remove()
        return store["h"]

    def decode_all_layers(self, ids, positions, donors: dict,
                          max_new: int = 900) -> str:
        """Transplant the span at every layer at once, then decode.

        Hooks on all layers simultaneously, so no layer can recompute the span
        from the receiver's own tokens in a gap between patched layers. This is
        the arm that separates "the mechanism does not carry" from "one layer's
        worth of it is not enough", and on the synthetic tier the two answers
        differ: single layers read 0.000 past layer 15 while every-layer-at-once
        recovers +0.769 of the logprob effect.
        """
        t = self.torch
        ids = ids.to(self.device)
        att = t.ones_like(ids)
        handles = []
        try:
            for L, donor in donors.items():
                handles.append(self.patch_hook(L, positions, donor)(self.model))
            with t.no_grad():
                out = self.model(input_ids=ids, attention_mask=att, use_cache=True)
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

    def decode_ids(self, ids, layer=None, positions=None, donor=None,
                   max_new: int = 900) -> str:
        t = self.torch
        ids = ids.to(self.device)
        att = t.ones_like(ids)
        handles = []
        if donor is not None:
            handles.append(self.patch_hook(layer, positions, donor)(self.model))
        try:
            with t.no_grad():
                out = self.model(input_ids=ids, attention_mask=att, use_cache=True)
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

    def decode_span_patch(self, system: str, user: str, layer: int,
                          positions, donor, max_new: int = 900) -> str:
        t = self.torch
        enc = self.tok(self._prompt(system, user), return_tensors="pt")
        ids = enc["input_ids"].to(self.device)
        att = enc["attention_mask"].to(self.device)
        handles = []
        if donor is not None:
            handles.append(self.patch_hook(layer, positions, donor)(self.model))
        try:
            with t.no_grad():
                out = self.model(input_ids=ids, attention_mask=att, use_cache=True)
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
    p.add_argument("--min-group", type=int, default=2)
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--cells-keep", default="R")
    p.add_argument("--per-calc", type=int, default=4)
    p.add_argument("--max-calcs", type=int, default=10)
    p.add_argument("--layers", default="4,10,16,22,28,34")
    p.add_argument("--max-span", type=int, default=0,
                   help="cap on how many span positions to transplant; 0 = the "
                        "whole span. The 128 of the first version was a cost "
                        "guess, and it made the patch cover ~6%% of a MedCalc "
                        "prompt against ~27%% on the synthetic tier -- a "
                        "confound, not a parameter.")
    p.add_argument("--matched", action="store_true",
                   help="length-matched receiver: the gold prompt with the "
                        "skill span overwritten by filler tokens, so donor and "
                        "receiver agree token for token outside that span and "
                        "the transplanted positions keep their RoPE phase. "
                        "Without it the receiver is the no-skill prompt, which "
                        "is ~900 tokens shorter.")
    p.add_argument("--span", choices=["task", "tail", "skill", "both"],
                   default="task",
                   help="which positions to transplant. `skill` is the "
                        "document's own tokens -- on the synthetic tier that "
                        "is the strongest channel by a distance (full recovery "
                        "at layers 0-10, against 0.333 for the question span), "
                        "and it is only well posed with --matched, where the "
                        "receiver has filler tokens in exactly those slots.")
    p.add_argument("--window", action="append", default=[],
                   help="lo:hi, repeatable -- write the span at every layer in "
                        "[lo, hi] and nowhere else")
    p.add_argument("--all-layers", action="store_true",
                   help="additionally transplant the span at EVERY layer at "
                        "once. A single-layer curve measures where one layer's "
                        "worth is enough; this measures whether the mechanism "
                        "carries at all, and it is the arm to read first when "
                        "every single layer reads near zero.")
    p.add_argument("--max-new", type=int, default=900)
    p.add_argument("--no-baselines", action="store_true",
                   help="skip the none / receiver / gold decodes. They do not "
                        "depend on the layer or the window, cost three long "
                        "decodes per item, and a shard that only adds windows "
                        "reads them from the run that has them, merged by "
                        "instance_id (the same rule wb_spanvec's shards use).")
    p.add_argument("--filler", choices=["ctrl", "fixedskill"], default="ctrl",
                   help="what the matched receiver's skill span is overwritten "
                        "with. `ctrl` (the historical default) writes the first "
                        "tokens of the whole control PROMPT -- chat template, "
                        "system text, then the paired neutral document -- which "
                        "is note-dependent and is NOT the receiver wb_spanvec's "
                        "battery uses. `fixedskill` builds the receiver exactly "
                        "as wb_spanvec --filler fixedskill does, so window and "
                        "all-layer arms can be normalised by that battery's "
                        "baselines. Measured on the full set, the two receivers "
                        "agree on only 358/467 items.")
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--decomp", action="store_true",
                   help="also inject the CONTENT half over the span, "
                        "h_none + (h_gold - h_ctrl). The presence half needs no "
                        "extra forward: h_none + g IS h_ctrl, which is already "
                        "an arm.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    p.add_argument("--resume", action="store_true",
                   help="append to --out, skipping instances already in it")
    a = p.parse_args(argv)
    a.windows = [tuple(int(x) for x in w.split(":")) for w in a.window]

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    from howskill import sra
    instances, skills, pairs, distractor = sra.load(a.dataset)
    SV = None
    if a.filler == "fixedskill":
        if not a.matched:
            raise SystemExit("--filler fixedskill only defines a matched receiver")
        from howskill import wb_spanvec as SV
        SV.FIXED_DISTRACTOR_SKILL = distractor
        # an item whose gold skill IS the filler document has donor == receiver
        instances = {k: v for k, v in instances.items()
                     if distractor not in v["skill_annotations"]}

    sc = SpanScorer(a.model, attn=a.attn)
    sc.cue = ""                                   # decode the reasoning
    layers = [int(x) for x in a.layers.split(",") if x.strip()]
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, instances, keep, a.per_calc, a.max_calcs, a.seed,
                          min_group=a.min_group)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    done = resume_done(a.out) if a.resume else set()
    if done:
        todo = [t for t in todo if t[2] not in done]
        print(f"[resume] {len(done)} instances already in {a.out}; "
              f"{len(todo)} left")
    print(f"{len(todo)} instances x {len(layers)} layers, attn={a.attn}, "
          f"max_new={a.max_new}")

    agg = collections.defaultdict(list)
    with _OutputLock(a.out), \
            open(a.out, "a" if a.resume else "w", encoding="utf-8") as fh:
        for k, (calc, cell, iid) in enumerate(todo, 1):
            inst = instances[iid]
            sid = inst["skill_annotations"][0]
            gold = arms_mod.build(a.arm, skills.get(sid),
                                  neutral_for=skills.get(pairs.get(sid)), seed=0)
            ctrl = arms_mod.build(a.ctrl_arm, skills.get(sid),
                                  neutral_for=skills.get(pairs.get(sid)), seed=0)
            sg, ug, spg = build_prompt_spans(inst, skills=gold)
            sc_, uc, spc = build_prompt_spans(inst, skills=ctrl)
            s0, u0, sp0 = build_prompt_spans(inst, skills=[])
            _, tg = sc.prompt_and_spans(sg, ug, spg)
            rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
                   "dataset": a.dataset,
                   "layers": layers, "matched": bool(a.matched),
                   "filler": a.filler if a.matched else None}

            if a.matched:
                ids_g = sc.prompt_ids(sg, ug)
                ids_c = sc.prompt_ids(sc_, uc)           # only for its tokens
                if SV is not None:
                    ids_c = SV.filler_ids_for(sc, ids_c, "fixedskill", skills)
                ids_r = sc.matched_receiver(ids_g, tg["skill"], ids_c)
                tk_lo, tk_hi = tg["task"]
                assert (ids_r[0, tk_lo:tk_hi] == ids_g[0, tk_lo:tk_hi]).all(), \
                    "the question tokens differ between donor and receiver"
                if a.span in ("skill", "both"):
                    sk_lo, sk_hi = tg["skill"]
                    pos = list(range(sk_lo, sk_hi))
                    if a.span == "both":
                        pos = pos + list(range(tk_lo, tk_hi))
                else:
                    m = tk_hi - tk_lo
                    if a.max_span and a.span == "tail":
                        m = min(m, a.max_span)
                    pos = list(range(tk_hi - m, tk_hi))
                m = len(pos)
                rec["n_patched"] = m
                rec["n_prompt"] = int(ids_g.shape[1])
                rec["frac_patched"] = m / int(ids_g.shape[1])
                if not a.no_baselines:
                    rec["ok_none"] = graded(sc.decode_ids(
                        sc.prompt_ids(s0, u0), max_new=a.max_new), inst, "cot")
                    rec["ok_receiver"] = graded(sc.decode_ids(
                        ids_r, max_new=a.max_new), inst, "cot")
                    rec["ok_gold_in_context"] = graded(sc.decode_ids(
                        ids_g, max_new=a.max_new), inst, "cot")
                    for key in ("ok_none", "ok_receiver", "ok_gold_in_context"):
                        agg[key[3:]].append(rec[key])
                for L in layers:
                    for tag, src in (("real", ids_g), ("self", ids_r)):
                        if tag == "self" and L not in (layers[0], layers[-1]):
                            continue          # instrument check, not a curve
                        donor = sc.capture_ids(src, L, pos)
                        ok = graded(sc.decode_ids(ids_r, L, pos, donor,
                                                  a.max_new), inst, "cot")
                        rec[f"ok_{tag}_L{L}"] = ok
                        agg[f"{tag}_L{L}"].append(ok)
                if a.all_layers or a.windows:
                    every = list(range(sc.model.config.num_hidden_layers))
                    donors = {L: sc.capture_ids(ids_g, L, pos) for L in every}
                    if a.all_layers:
                        ok = graded(sc.decode_all_layers(ids_r, pos, donors,
                                                         a.max_new),
                                    inst, "cot")
                        rec["ok_real_alllayers"] = ok
                        agg["real_alllayers"].append(ok)
                    # A single-layer handover dies past layer 14 while writing
                    # every layer at once still recovers everything, so the
                    # question the paper cannot answer is how much of the stack
                    # a deep handover needs. Each window writes the span at
                    # every layer in [lo, hi] and nowhere else; the width at
                    # which recovery returns is that answer, measured.
                    for lo, hi in a.windows:
                        sub = {L: v for L, v in donors.items() if lo <= L <= hi}
                        if not sub:
                            continue
                        ok = graded(sc.decode_all_layers(ids_r, pos, sub,
                                                         a.max_new),
                                    inst, "cot")
                        rec[f"ok_real_w{lo}_{hi}"] = ok
                        agg[f"real_w{lo}_{hi}"].append(ok)
            else:
                _, tc = sc.prompt_and_spans(sc_, uc, spc)
                _, t0 = sc.prompt_and_spans(s0, u0, sp0)
                cap = a.max_span or 10 ** 9
                m = min(tg["task"][1] - tg["task"][0],
                        tc["task"][1] - tc["task"][0],
                        t0["task"][1] - t0["task"][0], cap)
                src_g = list(range(tg["task"][1] - m, tg["task"][1]))
                src_c = list(range(tc["task"][1] - m, tc["task"][1]))
                dst = list(range(t0["task"][1] - m, t0["task"][1]))
                rec["n_patched"] = m
                rec["ok_none"] = graded(sc.decode_span_patch(
                    s0, u0, layers[0], dst, None, a.max_new), inst, "cot")
                rec["ok_gold_in_context"] = graded(sc.decode_span_patch(
                    sg, ug, layers[0], src_g, None, a.max_new), inst, "cot")
                agg["none"].append(rec["ok_none"])
                agg["gold_in_context"].append(rec["ok_gold_in_context"])
                for L in layers:
                    cap_states = {}
                    for tag, (sy, us, src) in (("real", (sg, ug, src_g)),
                                               ("ctrl", (sc_, uc, src_c)),
                                               ("self", (s0, u0, dst))):
                        cap_states[tag] = sc.capture_span(sy, us, L, src)
                        ok = graded(sc.decode_span_patch(
                            s0, u0, L, dst, cap_states[tag], a.max_new),
                            inst, "cot")
                        rec[f"ok_{tag}_L{L}"] = ok
                        agg[f"{tag}_L{L}"].append(ok)
                    if a.decomp:
                        d = cap_states["self"] + (cap_states["real"]
                                                  - cap_states["ctrl"])
                        ok = graded(sc.decode_span_patch(
                            s0, u0, L, dst, d, a.max_new), inst, "cot")
                        rec[f"ok_addd_L{L}"] = ok
                        agg[f"addd_L{L}"].append(ok)

            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if k % 4 == 0 or k == len(todo):
                line = "  ".join(f"{key} {sum(v)/len(v):.2f}" for key, v in
                                 sorted(agg.items())
                                 if key in ("none", "receiver",
                                            "gold_in_context")
                                 or key.startswith("real_"))
                print(f"  {k}/{len(todo)}  {line}", flush=True)

    print("\n=== summary ===")
    for key in sorted(agg):
        v = agg[key]
        print(f"  {key:22s} n={len(v):3d}  {sum(v)/len(v):.3f}")
    print("\n  `self_*` must equal `none` at every layer: donor and receiver are")
    print("  the same forward, so the patch is an exact no-op unless the hook is")
    print("  writing somewhere the capture did not read.")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
