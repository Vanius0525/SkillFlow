"""M8 -- which attention heads read the document span, what they read, and
whether that read-out explains the depth window of the transplant.

    python -m howskill.wb_heads --model $BASE/models/Qwen3-8B \
        --per-calc 4 --max-calcs 6 --inject-layers 8,16 --out results/heads.jsonl

WHY THIS FILE EXISTS

Writing the document's content vector over its own token span recovers the
whole behavioural effect through layer 12 and dies past layer 14 (rho = 0.14 at
15 and 16, 0.00 at 24 and 30), yet writing it at EVERY layer at once returns it
to 1.00. So the thing that fails past layer 14 is a handover at one depth, not
the mechanism. Nothing in the paper says what the handover IS.

The obvious candidate is that the span is read out by attention. If the heads
that carry the document into the rest of the computation sit in some band of
layers, then an injection is useful only if it lands UPSTREAM of that band:
inject at 8 and the readers see the content, inject at 16 and they have already
fired on filler. That predicts the depth curve from a quantity measured with no
decoding at all, which is the point.

  H1  the span's content leaves the span through a small set of heads
      concentrated in a band of layers.
  P1  read-out mass, by layer, is concentrated rather than uniform.
  P2  the fraction of the gold run's head read-out that an injection at layer
      L0 reproduces falls off at the same depth as behavioural rho.
  P3  (mode knockout) blocking the top-k reader heads' attention to the span
      costs more than blocking k random heads matched on layer.

H1 is falsifiable here. If read-out is spread evenly over all 36 layers, or if
plenty of it still happens past layer 20, the account is wrong and the depth
window has to come from somewhere else -- the rank collapse (participation
ratio 95 -> 17 between layers 8 and 16) being the standing alternative.

WHAT IS MEASURED, PER (LAYER, HEAD) AND PER ITEM

Three forward passes over the prompt -- gold (document present), recv (the
length-matched filler receiver), and one patched run per injection layer -- with
every self_attn hooked. For a set of CONSUMER rows t (positions after the span,
where the model has to use the document), we record

    att      sum_{s in span} a[t,s]            how much of the row's attention
                                               the span gets at all
    c        W_O^h ( sum_{s in span} a[t,s] v_s )    what the head actually
                                               writes into the residual stream
                                               on account of the span

and then, per head, dg = c_gold - c_recv (the read-out the real document causes)
and dp = c_patch - c_recv (the read-out the injection causes). The scalar that
answers P2 is the projection sum <dp,dg> / sum ||dg||^2 over layers past the
injection point.

    ov       W_O^h sum_s a_recv[t,s] (v_gold_s - v_recv_s)   read as a VALUE
    qk       W_O^h sum_s (a_gold - a_recv)[t,s] v_recv_s     read by CHANGING
                                                             what is attended to

separates "the document changes what the head fetches" from "the document
changes where the head looks". They sum to dg up to the interaction term.

EAGER IS MANDATORY. sdpa returns no attention weights, so every number here
would be silently absent. The behavioural runs use sdpa and the two kernels
disagree by ~1% of a state's magnitude at layer 8 (see SpanScorer.capture_ids),
so the three runs here are all eager and are only ever compared to each other.

INSTRUMENT CHECK. Captured (a, v) and o_proj are used to reconstruct the
module's own attention output on the consumer rows, over ALL key positions, and
the first item asserts the reconstruction matches to 1e-2 relative. A silent
mismatch -- a GQA head mapped the wrong way, RoPE, a transposed reshape -- would
produce a clean-looking map of nothing, which is the failure mode this file is
most exposed to.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random

from howskill.wb_diffvec import graded, pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spanpatch import SpanScorer, _OutputLock, resume_done
from howskill.wb_spanvec import build_item, capture_d, family_of

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
NEG = -1e30


def consumer_rows(lo, hi, n, mode, k):
    """Positions whose attention to the span is the read-out we care about.

    `post`: k positions evenly spaced over everything after the span -- the
    question text and the template's generation preamble, i.e. every place the
    document could still be consulted during the prefill. `tail`: the last k
    positions, which is where the first generated token is decided.

    The final prompt position is always included: under greedy decoding it is
    the only row that directly produces a token.
    """
    if mode == "tail":
        rows = list(range(max(hi, n - k), n))
    else:
        span = list(range(hi, n))
        if len(span) <= k:
            rows = span
        else:
            step = len(span) / k
            rows = sorted({span[int(i * step)] for i in range(k)})
    if n - 1 not in rows:
        rows.append(n - 1)
    return rows


class HeadCapture:
    """Hooks every self_attn and reduces its attention to per-head quantities.

    The attention weight tensor is [1, H, n, n] and is 0.9 GB at n = 2700, so
    the hook slices out the consumer rows and returns `(out[0], None)` in place
    of the full tensor: the decoder layer then holds nothing and only one
    layer's worth is alive at a time.
    """

    def __init__(self, sc, lo, hi, rows, keep_av=False, check=False):
        self.sc, self.lo, self.hi, self.rows = sc, lo, hi, rows
        self.keep_av, self.check = keep_av, check
        cfg = sc.model.config
        self.nL = cfg.num_hidden_layers
        self.H = cfg.num_attention_heads
        self.KV = cfg.num_key_value_heads
        self.dh = getattr(cfg, "head_dim", cfg.hidden_size // self.H)
        self.rep = self.H // self.KV
        self.att = {}      # layer -> [H]        span attention mass, mean over rows
        self.c = {}        # layer -> [H, d]     what the span writes via this head
        self.a_span = {}   # layer -> [H, R, m]  kept only when keep_av
        self.v_span = {}   # layer -> [KV, m, dh]
        self.resid = {}    # layer -> float      ||h[t]|| on the consumer rows
        self.hrow = {}     # layer -> [R, d]     the consumer rows themselves
        self._v = None
        self.err = 0.0

    def _wo(self, blk):
        w = blk.self_attn.o_proj.weight            # [d_model, H*dh]
        return w.view(w.shape[0], self.H, self.dh).float()

    def _mk_v(self, L):
        def fn(_mod, _inp, out):
            # [1, n, KV*dh] -> [KV, n, dh]; kept for the attention hook of the
            # SAME layer, which fires immediately after, then dropped
            self._v = out[0].view(out.shape[1], self.KV, self.dh
                                  ).transpose(0, 1).float()
        return fn

    def _mk_a(self, L, blk):
        torch = self.sc.torch

        def fn(_mod, _inp, out):
            w = out[1] if isinstance(out, tuple) else None
            if w is None:
                raise SystemExit(
                    "no attention weights: wb_heads needs --attn eager "
                    "(sdpa and flash return None and every head would read 0)")
            v = self._v
            self._v = None
            idx = torch.tensor(self.rows, device=w.device)
            a = w[0].index_select(1, idx).float()          # [H, R, n]
            vr = v.repeat_interleave(self.rep, dim=0)      # [H, n, dh]
            if self.check:
                z_all = torch.einsum("hrn,hnd->hrd", a, vr)
                recon = torch.einsum("dhk,hrk->rd", self._wo(blk), z_all)
                ref = (out[0] if isinstance(out, tuple) else out)[0
                                                                 ].index_select(0, idx).float()
                self.err = max(self.err, float(
                    (recon - ref).norm() / ref.norm().clamp_min(1e-9)))
                del z_all, recon, ref
            a_s = a[:, :, self.lo:self.hi]                 # [H, R, m]
            v_s = vr[:, self.lo:self.hi]                   # [H, m, dh]
            self.att[L] = a_s.sum(-1).mean(1).cpu()
            z = torch.einsum("hrm,hmd->hd", a_s, v_s) / a_s.shape[1]
            self.c[L] = torch.einsum("dhk,hk->hd", self._wo(blk), z).cpu()
            if self.keep_av:
                # kept on the GPU: the ov/qk einsums are 17 GFLOP per item and
                # take minutes on ten CPU cores, milliseconds here, and the two
                # runs together are under 1 GB at n = 2700
                self.a_span[L] = a_s.clone()
                self.v_span[L] = v[:, self.lo:self.hi].clone()
            del a, vr, a_s, v_s, z, v
            return (out[0], None) if isinstance(out, tuple) else out
        return fn

    def _mk_r(self, L):
        """Residual-stream norm on the consumer rows.

        Without it ||dg|| is not comparable across layers: the stream grows by
        more than an order of magnitude with depth, so a ranking on the raw
        write would find "reader heads" wherever the norms happen to be largest.
        """
        torch = self.sc.torch

        def fn(_mod, _inp, out):
            h = out[0] if isinstance(out, tuple) else out
            idx = torch.tensor(self.rows, device=h.device)
            r = h[0].index_select(0, idx).float()
            self.resid[L] = float(r.norm(dim=-1).mean())
            self.hrow[L] = r
        return fn

    def run(self, ids, patch=None):
        """One forward with every layer hooked. `patch` is (layer, positions, donor)."""
        torch = self.sc.torch
        m = self.sc.model
        handles = []
        try:
            for L, blk in enumerate(m.model.layers):
                handles.append(blk.self_attn.v_proj.register_forward_hook(
                    self._mk_v(L)))
                handles.append(blk.self_attn.register_forward_hook(
                    self._mk_a(L, blk)))
                handles.append(blk.register_forward_hook(self._mk_r(L)))
            if patch is not None:
                handles.append(self.sc.patch_hook(*patch)(m))
            ids = ids.to(self.sc.device)
            with torch.no_grad():
                m(input_ids=ids, attention_mask=torch.ones_like(ids),
                  use_cache=False)
        finally:
            for h in handles:
                h.remove()
        return self


def stack(d, nL, torch):
    return torch.stack([d[L] for L in range(nL)])


def decomp(gold, recv, torch):
    """(ov, qk) per (layer, head): the value path and the attention path."""
    ov, qk = [], []
    for L in range(gold.nL):
        wo = gold._wo(gold.sc.model.model.layers[L])
        ag = gold.a_span[L].float()
        ar = recv.a_span[L].float()
        vg = gold.v_span[L].float().repeat_interleave(gold.rep, dim=0)
        vr = recv.v_span[L].float().repeat_interleave(gold.rep, dim=0)
        mp = min(ag.shape[2], ar.shape[2], vg.shape[1], vr.shape[1])
        R = ag.shape[1]
        z_ov = torch.einsum("hrm,hmd->hd", ar[:, :, :mp],
                            (vg[:, :mp] - vr[:, :mp])) / R
        z_qk = torch.einsum("hrm,hmd->hd", (ag[:, :, :mp] - ar[:, :, :mp]),
                            vr[:, :mp]) / R
        ov.append(torch.einsum("dhk,hk->hd", wo, z_ov).cpu())
        qk.append(torch.einsum("dhk,hk->hd", wo, z_qk).cpu())
    return torch.stack(ov), torch.stack(qk)


def r4(x):
    return [[round(float(v), 6) for v in row] for row in x.tolist()]


def ko_hook(sc, layer_heads, lo, hi):
    """Block attention to the span for named heads only.

    A 4D mask is broadcast over heads by HF, so it is expanded to [B,H,q,k]
    inside the hook and rebuilt per layer rather than held for all of them --
    at n = 2700 one copy is 0.9 GB. Eager only: sdpa ignores a 4D mask, which
    would report every knockout as its own baseline (the same trap wb_knockout
    documents).
    """
    handles = []
    by_layer = collections.defaultdict(list)
    for L, h in layer_heads:
        by_layer[L].append(h)

    def mk(heads):
        def fn(module, args, kwargs):
            m = kwargs.get("attention_mask")
            if m is None or m.dim() != 4:
                return None
            H = sc.model.config.num_attention_heads
            m = m.expand(m.shape[0], H, m.shape[2], m.shape[3]).clone()
            m[:, heads, :, lo:hi] = NEG
            kwargs["attention_mask"] = m
            return args, kwargs
        return fn

    for L, heads in by_layer.items():
        handles.append(sc.model.model.layers[L].self_attn
                       .register_forward_pre_hook(mk(heads), with_kwargs=True))
    return handles


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["map", "knockout"], default="map")
    p.add_argument("--dataset", default="medcalcbench")
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", required=True)
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--cells-keep", default="R")
    p.add_argument("--per-calc", type=int, default=4)
    p.add_argument("--max-calcs", type=int, default=6)
    p.add_argument("--min-group", type=int, default=2)
    p.add_argument("--filler", choices=["fixedskill", "fixed", "ctrl"],
                   default="fixedskill")
    p.add_argument("--inject-layers", default="8,16",
                   help="layers to write the content vector at, for P2")
    p.add_argument("--row-mode", choices=["post", "tail"], default="post")
    p.add_argument("--n-rows", type=int, default=64)
    p.add_argument("--attn", default="eager")
    p.add_argument("--no-decomp", action="store_true",
                   help="skip the ov/qk split (halves the CPU memory)")
    p.add_argument("--ko-heads", default="",
                   help="knockout mode: L:h,L:h,... to make unattendable")
    p.add_argument("--ko-random", type=int, default=0,
                   help="knockout mode: instead, k random heads at the same "
                        "layers as --ko-heads (the matched control)")
    p.add_argument("--ko-tag", default="ko")
    p.add_argument("--max-new", type=int, default=900)
    p.add_argument("--baselines", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)

    if a.attn != "eager":
        raise SystemExit("wb_heads requires --attn eager; see the module docstring")

    import torch

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    n_cells = sum(len(v) for v in cells.values())
    from howskill import sra
    instances, skills, pairs, distractor = sra.load(a.dataset)
    import howskill.wb_spanvec as sv
    sv.FIXED_DISTRACTOR_SKILL = distractor

    sc = SpanScorer(a.model, attn=a.attn)
    sc.cue = ""
    inject = [int(x) for x in a.inject_layers.split(",") if x.strip()]
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, {k: v for k, v in instances.items()
                                  if distractor not in v["skill_annotations"]},
                          keep, a.per_calc, a.max_calcs, a.seed,
                          min_group=a.min_group)
    groups = collections.defaultdict(list)
    for calc, cell, iid in todo:
        groups[calc].append((cell, iid))
    order = sorted(groups)

    ko = []
    if a.mode == "knockout":
        spec = [t for t in a.ko_heads.split(",") if t.strip()]
        ko = [(int(t.split(":")[0]), int(t.split(":")[1])) for t in spec]
        if a.ko_random:
            # matched control: the same number of heads at the same layers,
            # drawn from the heads NOT named. "Any k heads hurt" is the null
            # this arm exists to rule out.
            rng = random.Random(a.seed + 1)
            H = sc.model.config.num_attention_heads
            named = collections.defaultdict(set)
            for L, h in ko:
                named[L].add(h)
            ko = [(L, h) for L, hs in named.items()
                  for h in rng.sample([x for x in range(H) if x not in hs],
                                      len(hs))]
        if not ko:
            raise SystemExit("knockout mode needs --ko-heads")
        print(f"knockout {len(ko)} heads: "
              + ",".join(f"{L}:{h}" for L, h in sorted(ko)), flush=True)

    nL = sc.model.config.num_hidden_layers
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    done = resume_done(a.out) if a.resume else set()
    print(f"model {os.path.basename(a.model.rstrip('/'))}, {nL} layers, "
          f"{sc.model.config.num_attention_heads} heads, "
          f"{sc.model.config.num_key_value_heads} kv heads", flush=True)
    print(f"{a.mode}: {sum(len(v) for v in groups.values())} instances over "
          f"{len(order)} calculators, inject={inject}, "
          f"rows={a.row_mode}:{a.n_rows}, attn={a.attn}", flush=True)

    checked = [False]
    with _OutputLock(a.out), \
            open(a.out, "a" if a.resume else "w", encoding="utf-8") as fh:
        for gi, calc in enumerate(order):
            for cell, iid in groups[calc]:
                if iid in done:
                    continue
                it = build_item(sc, instances[iid], skills, pairs, a.arm,
                                a.ctrl_arm, filler=a.filler)
                lo, hi = it["lo"], it["hi"]
                n = int(it["ids_g"].shape[1])
                rows = consumer_rows(lo, hi, n, a.row_mode, a.n_rows)
                rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
                       "dataset": a.dataset, "mode": a.mode,
                       "model": os.path.basename(a.model.rstrip("/")),
                       "cells_n": n_cells, "filler": a.filler,
                       "n_prompt": n, "m": hi - lo, "lo": lo, "hi": hi,
                       "n_rows": len(rows), "row_mode": a.row_mode,
                       "n_layers": nL,
                       "n_heads": sc.model.config.num_attention_heads,
                       "inject_layers": inject, "attn": a.attn}

                if a.mode == "knockout":
                    handles = ko_hook(sc, ko, lo, hi)
                    try:
                        txt = sc.decode_ids(it["ids_g"], max_new=a.max_new)
                    finally:
                        for h in handles:
                            h.remove()
                    rec[f"ok_{a.ko_tag}"] = graded(txt, instances[iid], "cot")
                    rec["ko_heads"] = [f"{L}:{h}" for L, h in sorted(ko)]
                    if a.baselines:
                        rec["ok_gold_in_context"] = graded(
                            sc.decode_ids(it["ids_g"], max_new=a.max_new),
                            instances[iid], "cot")
                        rec["ok_receiver"] = graded(
                            sc.decode_ids(it["ids_r"], max_new=a.max_new),
                            instances[iid], "cot")
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    print(f"  [{gi+1}/{len(order)} {calc}] {iid} "
                          + "  ".join(f"{k[3:]} {v:.2f}" for k, v in rec.items()
                                      if k.startswith("ok_")), flush=True)
                    continue

                keep_av = not a.no_decomp
                gold = HeadCapture(sc, lo, hi, rows, keep_av=keep_av,
                                   check=not checked[0]).run(it["ids_g"])
                recv = HeadCapture(sc, lo, hi, rows, keep_av=keep_av,
                                   check=not checked[0]).run(it["ids_r"])
                if not checked[0]:
                    err = max(gold.err, recv.err)
                    print(f"  [instrument] attention output reconstructed from "
                          f"captured (a, v, W_O) to {err:.2e} relative",
                          flush=True)
                    assert err < 1e-2, (
                        f"reconstruction off by {err:.3g}: the captured "
                        f"attention/value/GQA mapping does not reproduce the "
                        f"module's own output, so every head number below is "
                        f"meaningless")
                    rec["instrument_rel_err"] = err
                    checked[0] = True

                cg = stack(gold.c, nL, torch)
                cr = stack(recv.c, nL, torch)
                dg = cg - cr
                rec["resid_gold"] = [round(gold.resid[L], 4) for L in range(nL)]
                rec["resid_recv"] = [round(recv.resid[L], 4) for L in range(nL)]
                # THE PRIMARY CURVE. How far the consumer positions -- the
                # question text, which has to use the document -- are from the
                # gold run, layer by layer. An injection can only help here by
                # closing this gap, and the gap it cannot touch is the one that
                # opened at layers at or below the injection point.
                gap = [float((gold.hrow[L] - recv.hrow[L]).norm())
                       for L in range(nL)]
                rec["gap_recv"] = [round(g / gold.resid[L] / len(rows) ** .5, 6)
                                   for L, g in enumerate(gap)]
                rec["att_gold"] = r4(stack(gold.att, nL, torch))
                rec["att_recv"] = r4(stack(recv.att, nL, torch))
                rec["c_recv_norm"] = r4(cr.norm(dim=-1))
                rec["dg_norm"] = r4(dg.norm(dim=-1))

                if keep_av:
                    ov, qk = decomp(gold, recv, torch)
                    rec["ov_norm"] = r4(ov.norm(dim=-1))
                    rec["qk_norm"] = r4(qk.norm(dim=-1))
                    rec["ov_dot_dg"] = r4((ov * dg).sum(-1))
                    rec["qk_dot_dg"] = r4((qk * dg).sum(-1))
                    del ov, qk
                gold.a_span.clear(); gold.v_span.clear()
                recv.a_span.clear(); recv.v_span.clear()

                rec["dp_norm"], rec["dp_dot_dg"], rec["recovery"] = {}, {}, {}
                rec["att_patch"] = {}
                for L0 in inject:
                    h_g, h_r, d_i = capture_d(sc, it, L0)
                    donor = h_r.float() + d_i
                    pt = HeadCapture(sc, lo, hi, rows).run(
                        it["ids_r"], patch=(L0, it["pos"], donor))
                    dp = stack(pt.c, nL, torch) - cr
                    rec["att_patch"][str(L0)] = r4(stack(pt.att, nL, torch))
                    rec["dp_norm"][str(L0)] = r4(dp.norm(dim=-1))
                    rec["dp_dot_dg"][str(L0)] = r4((dp * dg).sum(-1))
                    # P2's scalar: of the read-out the real document causes
                    # DOWNSTREAM of the injection point, how much does the
                    # injection reproduce. Layers at or below L0 are excluded --
                    # there the injection has not happened yet, and including
                    # them would credit the arm with read-out it cannot have
                    # caused.
                    lo_l = L0 + 1
                    num = float((dp[lo_l:] * dg[lo_l:]).sum())
                    den = float((dg[lo_l:] * dg[lo_l:]).sum())
                    rec["recovery"][str(L0)] = round(num / den, 6) if den else None
                    # fraction of the receiver-to-gold gap at the consumer
                    # positions that this injection closes, by layer. This is
                    # what has to track behavioural rho: `recovery` above
                    # cannot, because from L0+1 on the SPAN's own states are
                    # identical to gold by construction (the span attends only
                    # to the shared prefix and to itself), so the read-out
                    # downstream of the injection is restored whether or not
                    # anything reached the question.
                    rec.setdefault("closed", {})[str(L0)] = [
                        round(1.0 - float((pt.hrow[L] - gold.hrow[L]).norm())
                              / max(gap[L], 1e-9), 6) for L in range(nL)]
                    del h_g, h_r, d_i, donor, pt, dp

                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                top = dg.norm(dim=-1).flatten().topk(3)
                where = [(int(i) // dg.shape[1], int(i) % dg.shape[1])
                         for i in top.indices]
                print(f"  [{gi+1}/{len(order)} {calc}] {iid} m={hi-lo} "
                      f"rows={len(rows)} top-dg "
                      + " ".join(f"L{L}h{h}:{v:.2f}" for (L, h), v
                                 in zip(where, top.values.tolist()))
                      + "  closed@last "
                      + " ".join(f"L{k}={v[-1]:.3f}" for k, v
                                 in rec["closed"].items()),
                      flush=True)
                del gold, recv, cg, cr, dg
    print("done", flush=True)


if __name__ == "__main__":
    main()
