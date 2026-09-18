"""M7 -- the injection / subtraction / dose / transfer battery, run through the
one channel that carries on this material: the document's own token span.

    python -m howskill.wb_spanvec --mode decode --layers 8 \
        --model $BASE/models/Qwen3-8B --out results/p8-wb/spanvec-L8.jsonl

WHY THIS FILE EXISTS

The vector arms in wb_diffvec -- add d, add g, add t, dose, same-family and
cross-family transfer -- all inject at ONE position (the last prompt position)
and all read the same number on this material: nothing. The synthetic tier says
they are not wrong in principle; there `add d` at alpha=1 repairs 0.812 of the
rescued cell. What differs is the answer. A Tier A answer is one token, so a
single position is the whole bottleneck the answer has to pass through; a
MedCalc answer arrives after a few hundred tokens of arithmetic, and one
position cannot hold that.

wb_spanpatch found the channel that does carry here: substitute the document's
own token span, length-matched, and the rescued cell goes 0.025 -> 1.000 at
layer 8. That arm is not just "a transplant". With a matched receiver the
receiver ALREADY CONTAINS A DOCUMENT (the filler), so

    donor(span) = h_gold(span) = h_recv(span) + [h_gold(span) - h_recv(span)]
                              = h_recv(span) + d(span)

-- it is exactly the content-vector injection of wb_diffvec, at alpha=1, spread
over m positions instead of 1. So the whole battery becomes available here, and
this file runs it: dose in alpha, subtraction into the presence/content halves,
transfer between items of one calculator and between calculators, and the
controls that separate "carries the content" from "looks informative and is
not".

THE ARMS (all patched into the filler receiver at the document's positions)

    self        h_recv                        exact no-op; instrument check
    real        h_recv + d_i                  = the gold states; alpha = 1
    a0.25 a0.5 a2                             dose response in alpha
    dbar        h_recv + mean_{j != i} d_j    same document, other patient notes
                                              -- the skill's part of the vector
    dother      h_recv + d_j                  one other note, not averaged
    dpar        h_recv + proj_{dbar} d_i      the shared-direction half
    dperp       h_recv + (d_i - proj)         the note-specific half
    dshuf       h_recv + d_i[permuted]        same vectors, wrong positions
    drand       h_recv + noise                per-position norm matched to d_i
    dcross      h_recv + d_k (other calc)     transfer, on the first m' shared
    realm       h_recv + d_i, same m'         positions -- dcross's paired control

ALIGNMENT. The document is the FIRST thing in the user message, so its span
starts at the same absolute index in every prompt: system text and chat
template preamble are constant. Within one calculator the document is
byte-identical, so (lo, hi) is identical and a donor from another note needs no
alignment at all. Across calculators the documents differ in length, so the
shared prefix of m' = min(m_i, m_k) positions is used -- from the START, which
is the end that is index-aligned, and therefore RoPE-phase-aligned. Aligning
from the far end instead would reintroduce exactly the phase error that made
the first version of wb_spanpatch report a false 0.200 for every arm.

GEOMETRY MODE (--mode geometry) records, per layer and with no decoding, the
norms and directions the decode arms are testing: ||d||, ||g||, ||h||, the
cosine of d against its calculator's mean, against another note of the same
calculator, and against another calculator, and the participation ratio of the
span's own positions. It is cheap (two forwards per item, all layers hooked)
and it is what says whether a vector that fails to act is failing because it
carries nothing or because what it carries cannot be used.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import random

from howskill import arms as arms_mod
from howskill.prompts import build_prompt_spans
from howskill.wb_diffvec import graded, pick_instances
from howskill.wb_replay import limit_threads
from howskill.wb_spanpatch import SpanScorer, _OutputLock, resume_done

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

DECODE_ARMS = ["real", "a0.25", "a0.5", "a0.75", "a1.5", "a2", "a3",
               "a0.5r", "a2r", "a3r", "dbar", "dother", "dpar", "dperp",
               "dshuf", "drand", "dcross", "realm", "dall", "dnear", "dfar", "head",
               "tail", "normrecv", "q0", "q1", "q2", "q3",
               "rank1", "rank2", "rank4", "rank8", "rank16", "rank32",
               "rank64", "rank128", "rank16lo", "rank64lo",
               "xfer", "xfern"]


def _cos(a, b, torch):
    """Mean cosine over positions, in float32 regardless of model dtype."""
    a = a.float()
    b = b.float()
    n = min(a.shape[0], b.shape[0])
    return float(torch.nn.functional.cosine_similarity(
        a[:n], b[:n], dim=-1).mean())


def _pr(mat, torch):
    """Participation ratio of the span's positions, centred.

    Uncentred this reads ~2 for any set of vectors sharing a large common
    component, which is every residual stream, and it once reported 2.3 for a
    set whose classes were 92% linearly separable -- geometrically impossible.
    What the number is meant to say is how many directions the VARIATION
    occupies, so the mean is removed first.
    """
    x = mat.float()
    x = x - x.mean(0, keepdim=True)
    ev = torch.linalg.svdvals(x) ** 2
    s1 = float(ev.sum())
    s2 = float((ev ** 2).sum())
    return s1 * s1 / s2 if s2 > 0 else 0.0


def _pr_robust(mat, torch, drop_pos=4, drop_dim=8):
    """The same participation ratio, with the usual artefacts removed.

    On Qwen3-8B the centred PR of a document span steps from ~70 at layer 14 to
    ~1.0 at layer 16 for three quarters of items and stays ~75 for the rest, so
    the mean of 17 describes no item. A PR of 1.0 over four hundred positions
    says the centred span is rank one, which is not a plausible statement about
    text. The documented cause in this model family is massive activations: a
    few hidden dimensions that blow up at a few token positions from a fixed
    layer on. Either would dominate a centred spectrum while leaving the
    document's representation untouched, so measure PR again with each removed
    and report all of them.
    """
    x = mat.float()
    out = {}
    n = x.shape[0]
    pn = x.norm(dim=-1)
    out["norm_ratio"] = float(pn.max() / pn.median().clamp_min(1e-9))
    xc = x - x.mean(0, keepdim=True)
    dv = xc.var(0)
    k = min(drop_dim, dv.numel())
    td = torch.topk(dv, k)
    out["top_dim_share"] = float(td.values.sum() / dv.sum().clamp_min(1e-9))
    out["top_dim"] = [int(i) for i in td.indices[:4].tolist()]
    kp = min(drop_pos, n - 2)
    tp = torch.topk(pn, max(kp, 1))
    out["top_pos"] = [int(i) for i in tp.indices[:4].tolist()]
    keep_p = torch.ones(n, dtype=torch.bool, device=x.device)
    keep_p[tp.indices[:kp]] = False
    keep_d = torch.ones(dv.numel(), dtype=torch.bool, device=x.device)
    keep_d[td.indices] = False
    out["pr_droppos"] = _pr(x[keep_p], torch)
    out["pr_dropdim"] = _pr(x[:, keep_d], torch)
    out["pr_unit"] = _pr(x / pn.unsqueeze(-1).clamp_min(1e-9), torch)
    return out


def _frac_par(d, u, torch):
    """Fraction of d's energy lying along u, per position, averaged.

    The decode arms split d into the half that points along the calculator's
    mean and the half that does not; this is the same split measured rather
    than injected, so the two can be read against each other.
    """
    d = d.float()
    u = u.float()
    n = min(d.shape[0], u.shape[0])
    d, u = d[:n], u[:n]
    denom = (u * u).sum(-1, keepdim=True).clamp_min(1e-9)
    par = ((d * u).sum(-1, keepdim=True) / denom) * u
    return float((par.norm(dim=-1) ** 2
                  / (d.norm(dim=-1) ** 2).clamp_min(1e-9)).mean())


FIXED_FILLER = """\
---
name: archive-formatting
description: "Formatting conventions for documents deposited in the Renslow \
institutional archive: file naming, header blocks, revision marks, margin \
widths, and the order of appended material."
---

# Archive formatting

A document deposited in the archive carries a header block, a revision mark, \
and an ordered list of appended material. The header block occupies the first \
four lines and is never wrapped. The revision mark is a single letter followed \
by two digits. Appended material is ordered by the date it was received, \
earliest first, and each entry is indented by two spaces under the heading it \
belongs to. Margins are set at thirty-two millimetres on the binding edge and \
eighteen on the outer edge; a deposited document whose binding margin is \
narrower than thirty-two millimetres is returned to the depositor with the \
margin noted on the returned copy. File names use the depositor's registry \
number, a hyphen, the four-digit year, a hyphen, and a two-digit sequence \
number within that year, with no spaces and no other punctuation. A document \
that supersedes an earlier deposit repeats the earlier file name and appends \
the letter S. Revision marks advance by one letter at each substantive change \
and by one digit at each correction that does not alter meaning. The order of \
appended material is: correspondence, schedules, figures, and finally any \
material the depositor has marked as provisional. Provisional material is \
listed but not paginated with the body. Headers on continuation pages repeat \
the file name and the revision mark and nothing else.
"""


FIXED_DISTRACTOR_SKILL = "medcalcbench_043"   # APACHE II, 6523 chars, ~1500
#   tokens, so it covers the widest document span (807) without tiling, and it
#   is not the gold skill of any calculator in the causal set.


def filler_ids_for(sc, ids_c, mode: str, skills=None):
    """Tokens the document slot is overwritten with.

    `ctrl` takes them from the CONTROL PROMPT, which is what the first version
    of this file and of wb_spanpatch did -- and it is wrong in a way that took
    a numerical check to see. The control prompt is the whole chat-formatted
    string, document AND patient note, so once the neutral document is shorter
    than the gold one the filler runs off the end of the document and into the
    note. The note differs between the instances of a calculator, so the
    receiver's states at the document positions differ between them too:
    measured, h_gold varies across notes by a relative 3e-3 (accumulated bf16
    rounding, since the prompts have different lengths) while h_recv varies by
    0.29-0.40. Every arm built as h_recv + something therefore inherits a
    note-dependent receiver, and the split of d into a shared and a
    note-specific half -- the whole point of the doc-last battery -- would be
    reading that instead of the document.

    `fixed` uses one neutral text, the same for every note and every
    calculator, tokenised once and tiled. It is the span-level version of the
    fixed filler wb_vecstats needs for the same reason: a per-skill neutral
    partner encodes the pairing, and a per-note one encodes the note.
    """
    if mode == "ctrl":
        return ids_c
    if mode == "fixed":
        return sc.tok(FIXED_FILLER, return_tensors="pt")["input_ids"]
    # `fixedskill`: ONE clinical skill document, the same one for every note and
    # every calculator. This is the filler the causal runs use, and the reason
    # is measured rather than aesthetic. With `fixed` -- neutral prose about
    # archive formatting -- the receiver scores 0.80-1.00 on the rescued items:
    # the model knows these formulae, and an off-topic document does not stop
    # it using them. There is then almost no range between the receiver and the
    # document itself for an arm to recover, and an arm at 0.95 would be
    # uninformative. A wrong CLINICAL document is a live distractor instead:
    # faced with a neighbouring calculator the model applies the neighbour's
    # formula and is wrong. That is also the condition the behavioural runs
    # call `ctrl_neutral`, so the receiver baseline here means the same thing
    # the paper's presence effect means.
    txt = (skills or {}).get(FIXED_DISTRACTOR_SKILL, {}).get("content", "")
    if not txt:
        raise SystemExit(f"filler skill {FIXED_DISTRACTOR_SKILL} not in the "
                         f"skill file; --filler fixedskill needs it")
    return sc.tok(txt, return_tensors="pt")["input_ids"]


def doc_last_spans(inst, skills_list):
    """The same prompt with the document AFTER the question, same strings.

    Why this variant exists. With the document first -- the format SR-Agents
    uses and the one every other run here uses -- causal attention makes the
    document's hidden states independent of the patient note: they see the
    system text and the document and nothing else. Within one calculator the
    document is byte-identical, so d(span) is the SAME TENSOR for all of that
    calculator's notes, and every donor arm that swaps notes (dbar, dother,
    dpar, dperp) is an algebraic identity rather than a measurement. The first
    launch of this battery confirmed it numerically: dbar, dpar and real agreed
    to three decimals on every running mean and dperp sat exactly on the
    receiver baseline.

    That is a result about the doc-first format -- the vector that carries the
    effect provably contains no task information -- but it leaves the opposite
    question unasked. Putting the document after the question lets its states
    see the note, so d CAN carry note-specific content, and whether it then
    does, and whether it still transplants, becomes measurable.

    The answer-format suffix stays last: it is the instruction that decides
    what the output looks like, and moving it would change the task rather
    than the document's position.
    """
    from howskill.prompts import (MEDCALC_SYSTEM, MEDCALC_USER_SUFFIX,
                                  SKILL_HEAD)
    q = inst["question"]
    contents = [x["content"] for x in (skills_list or []) if x.get("content")]
    block = "\n---\n".join(contents)
    if block:
        user = f"{q}\n\n{SKILL_HEAD}{block}\n\n{MEDCALC_USER_SUFFIX}"
        a = len(q) + 2 + len(SKILL_HEAD)
        spans = {"skill": [a, a + len(block)], "task": [0, len(q)]}
    else:
        user = f"{q}\n\n{MEDCALC_USER_SUFFIX}"
        spans = {"skill": None, "task": [0, len(q)]}
    s0 = user.index(MEDCALC_USER_SUFFIX)
    spans["suffix"] = [s0, s0 + len(MEDCALC_USER_SUFFIX)]
    return MEDCALC_SYSTEM, user, spans


def pad_question(ids, task_span, skill_span, filler_ids, target):
    """Insert filler tokens after the question so the document starts at
    `target`, the same absolute index for every note of a calculator.

    RoPE is absolute. A donor captured at positions 1200-1900 written into
    positions 1050-1750 is the error that made the first version of
    wb_spanpatch report 0.200 for the real arm and 0.200 for the control -- two
    arms broken the same way, which reads exactly like an absent effect. With
    the document last its start index moves with the length of the note, so
    cross-note donors need the index put back. Padding does that with the same
    filler text the matched receiver is built from, inserted between the
    question and the document, where it is inert: it is a neutral document
    fragment sitting in the middle of a prompt that already contains one.
    """
    lo = skill_span[0]
    need = target - lo
    if need < 0:
        return None
    if need == 0:
        return ids, (skill_span[0], skill_span[1]), task_span
    reps = need // filler_ids.shape[1] + 1
    pad = filler_ids.repeat(1, reps)[:, :need]
    import torch
    new = torch.cat([ids[:, :lo], pad.to(ids.dtype), ids[:, lo:]], dim=1)
    return new, (lo + need, skill_span[1] + need), task_span


def family_of(title: str) -> str:
    """Group the calculators by what they compute, from the skill's own title.

    `dcross` takes its donor from the next calculator in sorted order, and in
    this set that pairing is not neutral: 56 (QTc Fridericia) draws from 58 (QTc
    Hodges), 58 from 59 (QTc Rautaharju) and 63 (Delta Gap) from 64 (Delta
    Ratio) -- three of the ten donors are a different formula for the SAME
    quantity, while the rest are unrelated. Averaged together that arm mixes
    "another skill" with "a near miss", and the plausibility sweep says those
    are not the same condition. Splitting the arm turns the confound into the
    measurement.

    The rule is on the title rather than hand-assigned so that it can be
    audited and extended; the run prints the grouping it derived.
    """
    t = title.lower()
    for key, fam in (("qtc", "qtc"), ("delta", "delta"),
                     ("child-pugh", "liver"), ("fibrosis", "liver"),
                     ("fib-4", "liver"), ("fluid", "fluids"),
                     ("water deficit", "fluids")):
        if key in t:
            return fam
    return "other:" + t.split()[0]


def build_item(sc, inst, skills, pairs, arm, ctrl_arm, doc_last=False,
               pad_to=None, filler="fixed"):
    """Everything about one instance that does not depend on the layer."""
    sid = inst["skill_annotations"][0]
    gold = arms_mod.build(arm, skills.get(sid),
                          neutral_for=skills.get(pairs.get(sid)), seed=0)
    ctrl = arms_mod.build(ctrl_arm, skills.get(sid),
                          neutral_for=skills.get(pairs.get(sid)), seed=0)
    if doc_last:
        sg, ug, spg = doc_last_spans(inst, gold)
        sc_, uc, _ = doc_last_spans(inst, ctrl)
        s0, u0, _ = doc_last_spans(inst, [])
    else:
        sg, ug, spg = build_prompt_spans(inst, skills=gold)
        sc_, uc, _ = build_prompt_spans(inst, skills=ctrl)
        s0, u0, _ = build_prompt_spans(inst, skills=[])
    _, tg = sc.prompt_and_spans(sg, ug, spg)
    ids_g = sc.prompt_ids(sg, ug)
    ids_c = filler_ids_for(sc, sc.prompt_ids(sc_, uc), filler, skills)
    lo, hi = tg["skill"]
    if pad_to is not None:
        padded = pad_question(ids_g, tg["task"], (lo, hi), ids_c, pad_to)
        if padded is None:
            return None
        ids_g, (lo, hi), _ = padded
    ids_r = sc.matched_receiver(ids_g, (lo, hi), ids_c)
    # The receiver must differ from the donor ONLY inside the document span.
    # Everything the paper concludes rests on that: if the question tokens moved
    # too, a recovery would be a recovery of the question, and a null would be
    # two prompts broken in different ways. wb_spanpatch checks the same thing;
    # it belongs here too rather than being inherited by assumption.
    outside = [k for k in range(int(ids_g.shape[1]))
               if not (lo <= k < hi) and
               int(ids_g[0, k]) != int(ids_r[0, k])]
    assert not outside, (
        f"{inst['instance_id']}: donor and receiver differ at "
        f"{len(outside)} positions outside the document span "
        f"(first {outside[:5]}); only the span may change")
    return {"ids_g": ids_g, "ids_r": ids_r, "pos": list(range(lo, hi)),
            "lo": lo, "hi": hi, "s0": s0, "u0": u0,
            "doc_start": lo, "doc_width": hi - lo}


def capture_d(sc, it, layer):
    """d(span) = h_gold(span) - h_receiver(span), at one layer."""
    h_g = sc.capture_ids(it["ids_g"], layer, it["pos"])
    h_r = sc.capture_ids(it["ids_r"], layer, it["pos"])
    return h_g, h_r, (h_g.float() - h_r.float())


def make_donor(arm, torch, h_r, d_i, dbar, d_other, d_cross, rng,
               d_all=None, d_near=None, d_far=None):
    """Return (donor_states, n_positions_to_patch) or None if undefined here."""
    m = h_r.shape[0]
    base = h_r.float()
    if arm == "self":
        return h_r, m
    if arm == "real":
        return base + d_i, m
    if arm.startswith("a") and not arm.endswith("r"):
        return base + float(arm[1:]) * d_i, m
    if arm.startswith("a") and arm.endswith("r"):
        # Same dose, then rescaled per position back to the norm the gold
        # states have. Without this the dose curve confounds how much of the
        # content is injected with how big the resulting state is: at alpha=2
        # the patched state is 2 h_gold - h_recv, which is longer than
        # anything the model ever sees at those positions, and a layer-norm
        # network is not indifferent to that.
        v = base + float(arm[1:-1]) * d_i
        tgt = (base + d_i).norm(dim=-1, keepdim=True)
        return v * (tgt / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)), m
    if arm == "dbar":
        return (base + dbar, m) if dbar is not None else None
    if arm == "dother":
        return (base + d_other, m) if d_other is not None else None
    if arm in ("dpar", "dperp"):
        if dbar is None:
            return None
        u = dbar
        denom = (u * u).sum(-1, keepdim=True).clamp_min(1e-9)
        par = ((d_i * u).sum(-1, keepdim=True) / denom) * u
        return base + (par if arm == "dpar" else d_i - par), m
    if arm == "dshuf":
        perm = list(range(m))
        rng.shuffle(perm)
        return base + d_i[perm], m
    if arm == "drand":
        z = torch.randn(d_i.shape, generator=torch.Generator().manual_seed(
            rng.randrange(1 << 30)), dtype=torch.float32)
        z = z / z.norm(dim=-1, keepdim=True).clamp_min(1e-9)
        return base + z.to(d_i.device) * d_i.norm(dim=-1, keepdim=True), m
    if arm in ("xfer", "xfern"):
        if d_far is None:          # reused slot: the donor-layer content
            return None
        v = d_far
        if arm == "xfern":
            # match the target layer's content scale, so a null cannot be
            # blamed on writing a layer-8-sized vector into layer 16
            v = v * (d_i.norm(dim=-1, keepdim=True)
                     / v.norm(dim=-1, keepdim=True).clamp_min(1e-9))
        mp = min(m, v.shape[0])
        return base[:mp] + v[:mp], mp
    if arm.startswith("rank"):
        # Truncate the content matrix to rank k across the span's positions,
        # then inject. This is the causal test of the rank account: the span's
        # participation ratio falls from ~95 at layer 8 to ~17 at layer 16, and
        # the handover dies in between. If ~17 directions really are too few to
        # reconstruct the computation, then truncating the LAYER 8 donor to
        # k~17 should lose most of the effect while a larger k keeps it. If
        # k=16 is already enough here, the rank account is wrong -- which is
        # the point of running it.
        #
        # The mean over positions is kept and only the variation is truncated,
        # to match the participation ratio, which is computed centred.
        lo = arm.endswith("lo")
        k = int(arm[4:-2] if lo else arm[4:])
        x = d_i.float()
        mu = x.mean(0, keepdim=True)
        U, S, Vh = torch.linalg.svd(x - mu, full_matrices=False)
        r = min(k, S.shape[0])
        if lo:
            # the BOTTOM k directions instead: same rank, the discarded half of
            # the spectrum, so "k is enough" cannot be confused with "any k
            # directions will do"
            trunc = (U[:, -r:] * S[-r:]) @ Vh[-r:]
        else:
            trunc = (U[:, :r] * S[:r]) @ Vh[:r]
        return base + mu + trunc, m
    if arm in ("dnear", "dfar"):
        v = (d_near if arm == "dnear" else d_far)
        if v is None:
            return None
        mp = min(m, v.shape[0])
        return base[:mp] + v[:mp], mp
    if arm == "dall":
        # The common shift: d averaged over EVERY calculator in the set, on the
        # prefix they all share. This is the arm the whole "useful part versus
        # common shift" question reduces to -- if a document's effect were
        # mostly "a document is present and it is about medicine", this is the
        # vector that would carry it.
        if d_all is None:
            return None
        mp = min(m, d_all.shape[0])
        return base[:mp] + d_all[:mp], mp
    if arm.startswith("q") and arm[1:].isdigit():
        # One quarter of the span, the document's own d, the rest left as
        # filler. head/tail say which half matters; this says which quarter,
        # and the documents are written description-first, formula-and-worked-
        # example-last, so the ordering is interpretable.
        k = int(arm[1:])
        w = m // 4
        idx = list(range(k * w, (k + 1) * w if k < 3 else m))
        donor = base.clone()
        donor[idx] = base[idx] + d_i[idx]
        return donor, m
    if arm in ("head", "tail"):
        # Half the span, the document's own d, everything else left as filler.
        # Which half matters says where in the document the content sits: the
        # skills here open with a description and close with the formula and a
        # worked example.
        h = m // 2
        idx = list(range(h)) if arm == "head" else list(range(m - h, m))
        donor = base.clone()
        donor[idx] = base[idx] + d_i[idx]
        return donor, m
    if arm == "normrecv":
        # The gold states, rescaled per position to the norm the RECEIVER has.
        # Separates "the direction the document puts the span in" from "how far
        # along it the document goes".
        v = base + d_i
        tgt = base.norm(dim=-1, keepdim=True)
        return v * (tgt / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)), m
    if arm in ("dcross", "realm"):
        if d_cross is None:
            return None
        mp = min(m, d_cross.shape[0])
        src = d_cross[:mp] if arm == "dcross" else d_i[:mp]
        return base[:mp] + src, mp
    raise SystemExit(f"unknown arm {arm!r}")


def main(argv=None):
    limit_threads()
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["decode", "geometry"], default="decode")
    p.add_argument("--dataset", default="medcalcbench",
                   help="an SRA-Bench family wired in howskill/sra.py; the cells "
                        "file must come from the same dataset and model")
    p.add_argument("--cells", default=os.path.join(DATA, "cells.json"))
    p.add_argument("--model", default=os.environ.get(
        "WB_MODEL", os.path.join(HERE, "..", "models", "Qwen3-8B")))
    p.add_argument("--arm", default="gold_no_tool")
    p.add_argument("--ctrl-arm", default="ctrl_neutral_no_tool")
    p.add_argument("--cells-keep", default="R")
    p.add_argument("--per-calc", type=int, default=4)
    p.add_argument("--min-group", type=int, default=2,
                   help="smallest group of same-document items kept; 1 admits "
                        "singleton skills (TheoremQA), where no same-document "
                        "donor arm is defined and the restriction is per item")
    p.add_argument("--max-calcs", type=int, default=10)
    p.add_argument("--layers", default="8")
    p.add_argument("--donor-layer", type=int, default=-1,
                   help="capture d at THIS layer but inject it at each --layers "
                        "layer. The point is to ask what a late layer is "
                        "missing: at layer 16 the span's representation has "
                        "collapsed to ~17 effective directions and the "
                        "transplant recovers 0.14, while at layer 8 it has ~95 "
                        "and recovers everything. Writing the layer-8 content "
                        "into layer 16 asks whether the missing thing is rank. "
                        "The residual stream also grows with depth (||h|| 51 at "
                        "8, 93 at 16), so the norm-matched arm `xfern` is the "
                        "one that isolates rank from scale.")
    p.add_argument("--arms", default=",".join(DECODE_ARMS),
                   help="comma-separated subset of " + ",".join(DECODE_ARMS))
    p.add_argument("--max-new", type=int, default=900)
    p.add_argument("--attn", default="sdpa")
    p.add_argument("--baselines", action="store_true",
                   help="also decode none / receiver / gold-in-context. They "
                        "cost three long decodes per instance and do not "
                        "depend on the layer or the arm set, so a shard that "
                        "is only adding arms should leave them off and read "
                        "them from the shard that has them.")
    p.add_argument("--filler", choices=["fixedskill", "fixed", "ctrl"],
                   default="fixedskill",
                   help="what the document slot is overwritten with. "
                        "`fixedskill` is one clinical skill document, the same "
                        "for every note; `fixed` is neutral non-clinical prose, "
                        "which the model simply ignores; `ctrl` reproduces the "
                        "older runs and is note-dependent. See filler_ids_for.")
    p.add_argument("--doc-last", action="store_true",
                   help="put the document AFTER the question, so its states "
                        "can see the note. With the document first (the "
                        "default, and the format the behavioural runs use) "
                        "causal attention makes d identical for every note of "
                        "a calculator and every cross-note donor arm an "
                        "identity -- see doc_last_spans.")
    p.add_argument("--geom-step", type=int, default=4,
                   help="geometry mode sweeps every --geom-step-th layer. The "
                        "full span is held on CPU for every layer at once, so "
                        "36 layers x 40 notes x ~900 positions x 4096 is 21 "
                        "GB. d alone in bf16 at every fourth layer is 2.7, and "
                        "the curves are smooth at that resolution.")
    p.add_argument("--baseline-sweep", action="store_true",
                   help="also decode the receiver with three different "
                        "documents in the slot -- neutral prose, a fixed wrong "
                        "clinical skill, and this skill's paired neutral -- to "
                        "measure how much a wrong document costs as a function "
                        "of how plausible it is.")
    p.add_argument("--calcs", default="",
                   help="comma-separated calculator ids to keep after the "
                        "usual selection. Only for arms that read nothing but "
                        "the item's own d (rank*, q*, real, a*): the cross, "
                        "near, far and dall donor pools are built from the "
                        "items in the run, so filtering changes those arms.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args(argv)

    import torch

    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    n_cells = sum(len(v) for v in cells.values())
    from howskill import sra
    instances, skills, pairs, distractor = sra.load(a.dataset)
    # the receiver's filler is one fixed skill of the SAME family; an item whose
    # gold skill IS that document would have donor == receiver, so it is dropped
    global FIXED_DISTRACTOR_SKILL
    FIXED_DISTRACTOR_SKILL = distractor
    unknown = [i for c in cells.values() for i in c if i not in instances]
    if unknown:
        raise SystemExit(f"{len(unknown)} cell ids are not {a.dataset} instances "
                         f"(first {unknown[:3]}): cells file from another dataset?")

    sc = SpanScorer(a.model, attn=a.attn)
    sc.cue = ""
    layers = [int(x) for x in a.layers.split(",") if x.strip()]
    want = [x.strip() for x in a.arms.split(",") if x.strip()]
    keep = [x.strip() for x in a.cells_keep.split(",")]
    todo = pick_instances(cells, {k: v for k, v in instances.items()
                                  if distractor not in v["skill_annotations"]},
                          keep, a.per_calc, a.max_calcs, a.seed, min_group=a.min_group)
    if a.calcs:
        pooled = {"dcross", "dnear", "dfar", "dall"} & set(want)
        if pooled:
            raise SystemExit(f"--calcs changes the donor pools of {sorted(pooled)}; "
                             f"run those arms over the unfiltered item set")
        only = {c.strip() for c in a.calcs.split(",") if c.strip()}
        todo = [t for t in todo if t[0] in only]
        missing = only - {t[0] for t in todo}
        if missing:
            raise SystemExit(f"--calcs names calculators with no selected items: "
                             f"{sorted(missing)}")
    if a.mode == "geometry":
        layers = list(range(0, sc.model.config.num_hidden_layers,
                            a.geom_step))
    cap_layers = sorted(set(layers) | ({a.donor_layer} if a.donor_layer >= 0
                                       else set()))

    # Grouped by calculator so the same-document donors are in hand together;
    # a donor from another calculator is taken from the group processed before
    # this one, which is why the groups are walked in a fixed order.
    groups: dict[str, list] = collections.defaultdict(list)
    for calc, cell, iid in todo:
        groups[calc].append((cell, iid))
    order = sorted(groups)
    family = {}
    for calc in order:
        sid = instances[groups[calc][0][1]]["skill_annotations"][0]
        title = skills.get(sid, {}).get("content", "").splitlines()[0]
        family[calc] = family_of(title.strip("# ").strip())
    fam_groups = collections.defaultdict(list)
    for c, f in family.items():
        fam_groups[f].append(c)
    print("families derived from the skill titles: "
          + "; ".join(f"{f}={sorted(v)}" for f, v in sorted(fam_groups.items())),
          flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    done = resume_done(a.out) if a.resume else set()
    n_todo = sum(len(v) for v in groups.values()) - len(
        [1 for v in groups.values() for _, i in v if i in done])
    print(f"model {os.path.basename(a.model.rstrip('/'))}, "
          f"{sc.model.config.num_hidden_layers} layers, "
          f"d={sc.model.config.hidden_size}", flush=True)
    print(f"{a.mode}: {n_todo} instances over {len(order)} calculators "
          f"x {len(layers)} layers, arms={want}, attn={a.attn}", flush=True)

    rng = random.Random(a.seed)
    agg = collections.defaultdict(list)

    # ---- pass 1: capture d for every note, before anything is decoded -------
    # Deferring this to the decode loop -- taking as donors whatever happened
    # to be captured already -- gives the first note of each calculator no
    # donor at all and the last one three, so the same arm is measured on a
    # different n for every note, and the leave-one-out mean is not leave-one-
    # out. Two forwards per note at the decode layers is a few minutes; it buys
    # a design where every arm is defined for every note.
    built: dict = {}
    D: dict = {L: {} for L in cap_layers}
    HR: dict = {L: {} for L in cap_layers}
    HSTAT: dict = {L: {} for L in cap_layers}
    for gi, calc in enumerate(order):
        pad_to = None
        if a.doc_last:
            # One probe build per note to learn where its document starts,
            # then one common target for the whole calculator. Computing the
            # target from the longest note means every other note is padded
            # OUT, never truncated: no question loses tokens.
            starts = []
            for _, iid in groups[calc]:
                probe = build_item(sc, instances[iid], skills, pairs, a.arm,
                                   a.ctrl_arm, doc_last=True,
                                   filler=a.filler)
                starts.append(probe["doc_start"])
            pad_to = max(starts)
        for cell, iid in groups[calc]:
            built[iid] = build_item(sc, instances[iid], skills, pairs,
                                    a.arm, a.ctrl_arm, doc_last=a.doc_last,
                                    pad_to=pad_to, filler=a.filler)
            assert built[iid] is not None and (
                pad_to is None or built[iid]["doc_start"] == pad_to), (
                f"{iid}: document starts at "
                f"{built[iid] and built[iid]['doc_start']}, not {pad_to}; "
                f"cross-note donors would be written at the wrong RoPE phase")
            for L in cap_layers:
                h_g, h_r, d_i = capture_d(sc, built[iid], L)
                if a.mode == "geometry":
                    # Everything that needs h is scalar and is computed here,
                    # while h is still on the GPU. Holding h as well would put
                    # 18 layers x 40 notes x ~900 x 4096 three times over on
                    # CPU; d alone, in bf16, is 2.7 GB.
                    D[L][iid] = d_i.to(torch.bfloat16).cpu()
                    HSTAT[L][iid] = {
                        "hg_norm": float(h_g.float().norm(dim=-1).mean()),
                        "hr_norm": float(h_r.float().norm(dim=-1).mean()),
                        "d_over_h": float(
                            (d_i.norm(dim=-1)
                             / h_g.float().norm(dim=-1).clamp_min(1e-9)).mean()),
                        "pr_hg": _pr(h_g, torch),
                        **{f"hg_{k}": v for k, v in
                           _pr_robust(h_g, torch).items()}}
                else:
                    D[L][iid] = d_i.cpu()
                    HR[L][iid] = h_r.cpu()
        widths = {iid: len(built[iid]["pos"]) for _, iid in groups[calc]}
        assert len(set(widths.values())) == 1, (
            f"calculator {calc}: the document span is not the same width for "
            f"every note ({widths}); the same-document donor arms assume it "
            f"is, because the document is byte-identical and sits at a fixed "
            f"offset in the prompt")
        print(f"  [capture] {gi+1}/{len(order)} {calc} "
              f"m={list(widths.values())[0]}", flush=True)

    # A calculator's cross-donor is the NEXT calculator's mean, cyclically, so
    # every group has one and no group is its own donor.
    cross = {}
    dall = {}
    near_far = {}
    for L in layers:
        for i, calc in enumerate(order):
            src = order[(i + 1) % len(order)]
            ids = [iid for _, iid in groups[src]]
            n = min(D[L][j].shape[0] for j in ids)
            cross[(L, calc)] = sum(D[L][j][:n] for j in ids) / len(ids)
        for i, calc in enumerate(order):
            same = [c for c in order
                    if c != calc and family[c] == family[calc]]
            other = [c for c in order if family[c] != family[calc]]
            for tag, pool in (("near", same), ("far", other)):
                if not pool:
                    continue
                ids = [j for c in pool for _, j in groups[c]]
                w = min(D[L][j].shape[0] for j in ids)
                near_far[(tag, L, calc)] = sum(D[L][j][:w] for j in ids) / len(ids)
        # The common shift, over every calculator including this one. Excluding
        # the receiver's own calculator would make it a different arm for every
        # note and confound "the shared part" with "leave-one-out denoising",
        # which is what dbar already measures.
        every = [j for c in order for _, j in groups[c]]
        n = min(D[L][j].shape[0] for j in every)
        dall[L] = sum(D[L][j][:n] for j in every) / len(every)

    # ---- pass 2: decode ----------------------------------------------------
    with _OutputLock(a.out), \
            open(a.out, "a" if a.resume else "w", encoding="utf-8") as fh:
        for gi, calc in enumerate(order):
            for cell, iid in groups[calc]:
                if iid in done:
                    continue
                it = built[iid]
                rec = {"instance_id": iid, "cell": cell, "calculator_id": calc,
                       "dataset": a.dataset,
                       "mode": a.mode, "n_patched": len(it["pos"]),
                       "n_prompt": int(it["ids_g"].shape[1]),
                       "doc_start": it["doc_start"],
                       "format": "doc_last" if a.doc_last else "doc_first",
                       "filler": a.filler,
                       "model": os.path.basename(a.model.rstrip("/")),
                       "prompt_mode": sc.prompt_mode,
                       # the cell assignment changed when the no_skill arm was
                       # completed from 839 to 1100 instances (R: 366 -> 470),
                       # so runs drawn from the two versions sample different
                       # item sets and must never be pooled
                       "cells_n": n_cells,
                       "arms": want, "layers": layers}
                if a.mode == "decode" and a.baseline_sweep:
                    # How much a wrong document costs, as a function of how
                    # plausible it is. Four receivers, same length, same
                    # positions, differing only in what sits in the document
                    # slot. This is a behavioural measurement, not an
                    # intervention, and it is here because it decides what the
                    # receiver baseline of every arm above actually means.
                    for tag, mode in (("neutralprose", "fixed"),
                                      ("wrongskill", "fixedskill"),
                                      ("pairedneutral", "ctrl")):
                        alt = build_item(sc, instances[iid], skills, pairs,
                                         a.arm, a.ctrl_arm,
                                         doc_last=a.doc_last, filler=mode)
                        rec[f"ok_recv_{tag}"] = graded(sc.decode_ids(
                            alt["ids_r"], max_new=a.max_new), instances[iid],
                            "cot")
                        agg[f"recv_{tag}"].append(rec[f"ok_recv_{tag}"])
                if a.mode == "decode" and (a.baselines or a.baseline_sweep):
                    rec["ok_none"] = graded(sc.decode_ids(
                        sc.prompt_ids(it["s0"], it["u0"]), max_new=a.max_new),
                        instances[iid], "cot")
                    rec["ok_receiver"] = graded(sc.decode_ids(
                        it["ids_r"], max_new=a.max_new), instances[iid], "cot")
                    rec["ok_gold_in_context"] = graded(sc.decode_ids(
                        it["ids_g"], max_new=a.max_new), instances[iid], "cot")
                    for k in ("none", "receiver", "gold_in_context"):
                        agg[k].append(rec["ok_" + k])

                for L in layers:
                    d_i = D[L][iid]
                    h_r = HR[L].get(iid)
                    others = [D[L][j] for _, j in groups[calc] if j != iid]
                    dbar = (sum(others) / len(others)) if others else None
                    d_other = others[0] if others else None
                    d_cross = cross[(L, calc)]
                    d_all = dall[L]
                    d_near = near_far.get(("near", L, calc))
                    d_far = near_far.get(("far", L, calc))
                    if a.donor_layer >= 0:
                        # the cross-layer arms borrow the d_far slot rather
                        # than widening make_donor's signature again
                        d_far = D[a.donor_layer][iid]
                    rec[f"n_donor_pool_L{L}"] = len(others)

                    if a.mode == "geometry":
                        g = {"layer": L,
                             "d_norm": float(d_i.float().norm(dim=-1).mean()),
                             "d_mean_norm": float(d_i.float().mean(0).norm()),
                             **HSTAT[L][iid],
                             "pr_d": _pr(d_i, torch),
                             **{f"d_{k}": v for k, v in
                                _pr_robust(d_i, torch).items()},
                             "cos_d_same": _cos(d_i, d_other, torch),
                             "maxabs_d_same": float(
                                 (d_i.float() - d_other.float()).abs().max()),
                             "reldiff_d_same": float(
                                 (d_i.float() - d_other.float()).norm()
                                 / d_i.float().norm().clamp_min(1e-9)),
                             "cos_d_bar": _cos(d_i, dbar, torch),
                             "cos_d_cross": _cos(d_i, d_cross, torch),
                             "cos_d_all": _cos(d_i, dall[L], torch),
                             "frac_par_all": _frac_par(d_i, dall[L], torch),
                             "frac_par": _frac_par(d_i, dbar, torch)}
                        rec.setdefault("geom", []).append(g)
                        for k, v in g.items():
                            # the robust-PR helper also returns which positions
                            # and dimensions were dropped, which are lists and
                            # have no mean; they live in the row, not the agg
                            if k != "layer" and isinstance(v, (int, float)):
                                agg[f"{k}@L{L:02d}"].append(v)
                        continue

                    for arm in ["self"] + want:
                        if arm == "self" and L not in (layers[0], layers[-1]):
                            continue
                        made = make_donor(arm, torch, h_r, d_i, dbar, d_other,
                                          d_cross, rng, d_all, d_near, d_far)
                        if made is None:
                            continue
                        donor, mp = made
                        ok = graded(sc.decode_ids(
                            it["ids_r"], L, it["pos"][:mp], donor.to(sc.device),
                            a.max_new), instances[iid], "cot")
                        rec[f"ok_{arm}_L{L}"] = ok
                        agg[f"{arm}_L{L}"].append(ok)

                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                line = "  ".join(
                    f"{k} {sum(v)/len(v):.2f}" for k, v in sorted(agg.items())
                    if k.split("_L")[0] in ("real", "dbar", "dperp", "dpar",
                                            "dcross", "drand", "none",
                                            "receiver", "gold_in_context"))
                print(f"  [{gi+1}/{len(order)} {calc}] {iid} {line}",
                      flush=True)

    # A truncated JSONL looks exactly like a finished one. Three round-4 files
    # were short by one or two instances -- the last group, cut off when the
    # platform reclaimed the box -- and the gap was invisible until a separate
    # completeness pass compared instance sets across files. Say it here.
    written = len(done) + sum(len(v) for v in groups.values()) - len(
        [1 for v in groups.values() for _, i in v if i in done])
    actual = sum(1 for _ in open(a.out, encoding="utf-8")) if os.path.exists(a.out) else 0
    if actual != written:
        print(f"\n  [WARN] {a.out} holds {actual} rows, expected {written}. "
              f"Rerun with --resume to fill the gap before using this file.")
    else:
        print(f"\n  {actual} rows, complete.")

    print("\n=== summary ===")
    for key in sorted(agg):
        v = agg[key]
        if a.mode == "geometry":
            print(f"  {key:24s} n={len(v):3d}  {sum(v)/len(v):+.4f}")
        else:
            m = sum(v) / len(v)
            se = math.sqrt(max(m * (1 - m), 0) / max(len(v), 1))
            print(f"  {key:24s} n={len(v):3d}  {m:.3f}  "
                  f"[{max(0.0, m-1.96*se):.3f},{min(1.0, m+1.96*se):.3f}]")
    if a.mode == "decode":
        print("\n  `self_*` must equal `receiver` at every layer: with a "
              "matched receiver the\n  donor is the receiver's own state, so "
              "the patch is an exact no-op.\n  `real` is h_recv + d at "
              "alpha=1, so the dose arms bracket it.")
    print(f"\n-> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
