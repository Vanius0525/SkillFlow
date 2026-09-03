#!/usr/bin/env python3
"""
Why the last-layer identity does not read 1.000.

Patching the final block's output at the last prompt position must reproduce the
source run's logits exactly: for a single-token answer the logprob is read from
the logits at that position, and those are lm_head(norm(that vector)). Both steps
are deterministic functions of the vector, so lp_real must equal lp_yes.

It reads 1.265 (it read 4.09 before capture moved onto the same hook the patch
writes to, so the double-normalisation was real and was most of it). This script
finds where the rest enters, by checking each link separately instead of
reasoning about which one is likeliest.

    python patchcheck.py --model ../models/Qwen3-1.7B \\
        --tasks tasks/tier_a/tasks.jsonl --skill tasks/tier_a/SKILL.zorb-units.md

Prints five checks. The first that fails is the answer; the ones after it are
consequences.
"""

from __future__ import annotations

import argparse
import io
import json

import torch

import model as M


def load_items(path, limit):
    items = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    return items[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", default="bfloat16",
                    choices=("bfloat16", "float16", "float32"))
    args = ap.parse_args()

    items = load_items(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    r = M.load(args.model, device=args.device,
               dtype=getattr(torch, args.dtype))
    L = r.n_layers - 1
    print(f"model {args.model}   n_layers {r.n_layers}   last block {L}   "
          f"dtype {args.dtype}")
    print(f"items {len(items)}\n")

    it = items[0]
    q, gold = it["question_mc"], it["answer_mc"]
    ids_yes = M.encode(r, M.render(r, M.build_messages(q, skill, "mc")))
    ids_no = M.encode(r, M.render(r, M.build_messages(q, None, "mc")))

    # ---- 1. is the answer one token? --------------------------------------
    #
    # If it is not, the logprob is a mean over answer positions and only the
    # first of them is read from the patched position. Everything below assumes
    # it is one.
    ans = r.tok(gold, return_tensors="pt", add_special_tokens=False).input_ids
    n_ans = int(ans.shape[1])
    print(f"[{'OK ' if n_ans == 1 else 'BAD'}] 1. 金答案是单 token: "
          f"{gold!r} -> {n_ans} 个 token {ans[0].tolist()}")

    # ---- 2. is hidden_states[-1] post-norm? -------------------------------
    #
    # The original diagnosis. lm_head reads the normalised state, so if the last
    # hidden_states entry already went through norm, applying lm_head to it
    # reproduces the logits exactly.
    with torch.no_grad():
        cap = M.capture(r, ids_yes)
        hs_last = cap.hidden_states[-1]
        re_logits = r.model.lm_head(hs_last)
        post = torch.allclose(re_logits.float(), cap.logits.float(), atol=5e-2)
    print(f"[{'OK ' if post else 'BAD'}] 2. hidden_states[-1] 是 post-norm: "
          f"{post}   (True 证实原诊断)")

    # ---- 3. does the new capture return the PRE-norm block output? --------
    with torch.no_grad():
        bo = M.capture_block_outputs(r, ids_yes, [L], k=1)[L][-1]
        renorm = r.model.model.norm(bo.unsqueeze(0).unsqueeze(0))[0, 0]
        pre = torch.allclose(renorm.float(), hs_last[0, -1].float(), atol=5e-2)
        gap = (renorm.float() - hs_last[0, -1].float()).abs().max().item()
    print(f"[{'OK ' if pre else 'BAD'}] 3. norm(捕获到的向量) == "
          f"hidden_states[-1]: {pre}   max|diff| {gap:.4g}")

    # ---- 4. the identity itself, per item ---------------------------------
    #
    # A mean of +0.17 over 39 items is not bf16 noise averaging out, so the sign
    # pattern is the thing to look at: scattered around zero is numerical,
    # uniformly one way is structural.
    print("\n[4] 逐题恒等检查   lp_real - lp_yes（应当全 0）")
    diffs = []
    for it in items:
        q, gold = it["question_mc"], it["answer_mc"]
        iy = M.encode(r, M.render(r, M.build_messages(q, skill, "mc")))
        ino = M.encode(r, M.render(r, M.build_messages(q, None, "mc")))
        lp_yes = M.answer_logprob(r, iy, gold)
        v = M.capture_block_outputs(r, iy, [L], k=1)[L]
        pos = [int(ino.shape[1]) - 1]
        with M.patch_layer(r, L, pos, v):
            lp_real = M.answer_logprob(r, ino, gold)
        diffs.append(lp_real - lp_yes)
        print(f"    {it['id']}  lp_yes {lp_yes:+.4f}  lp_real {lp_real:+.4f}  "
              f"diff {lp_real - lp_yes:+.4f}")
    mean = sum(diffs) / len(diffs)
    pos_n = sum(1 for d in diffs if d > 0)
    print(f"\n    mean {mean:+.4f}   同号 {pos_n}/{len(diffs)} 为正")
    if abs(mean) < 1e-3:
        print("    -> 恒等成立。1.265 来自别处,查 e2_patch 的位置或分母。")
    elif pos_n in (0, len(diffs)):
        print("    -> 全部同号：**结构性**,不是数值噪声。捕获和写入还不是同一个"
              "状态,或者读数位置不是被补的那个位置。")
    else:
        print("    -> 有正有负,且大小跟着 |lp| 走：gold 在尾部的题差得多,gold 就是"
              "argmax 的题差≈0。看 6a 和 7 —— 捕获用的前向和打分用的前向不一样长。")

    # ---- 4b. logits, not logprobs -----------------------------------------
    #
    # The decisive split. If the logit vector at the patched position matches
    # the source run's at its last prompt position, the patch took and the
    # discrepancy is in what answer_logprob reads. If it does not match, the
    # patch is not landing where the capture came from, and check 4 is a
    # symptom.
    it = items[0]
    q, gold = it["question_mc"], it["answer_mc"]
    iy = M.encode(r, M.render(r, M.build_messages(q, skill, "mc")))
    ino = M.encode(r, M.render(r, M.build_messages(q, None, "mc")))
    with torch.no_grad():
        ref = r.model(iy, use_cache=False).logits[0, -1].float()
        v = M.capture_block_outputs(r, iy, [L], k=1)[L]
        with M.patch_layer(r, L, [int(ino.shape[1]) - 1], v):
            got = r.model(ino, use_cache=False).logits[0, -1].float()
    dmax = (got - ref).abs().max().item()
    same = dmax < 5e-2
    print(f"\n[{'OK ' if same else 'BAD'}] 4b. 补丁位置上的 logits 与源前向相同: "
          f"{same}   max|diff| {dmax:.4g}")
    if not same:
        print("     -> 补丁没有把那个位置变成源前向的状态。捕获点和写入点仍然"
              "不是同一个东西,先查这里,check 4 只是它的症状。")
    else:
        print("     -> 补丁生效了。那么差在 answer_logprob 读的位置或聚合方式上。")

    # ---- 6. is answer_logprob reading that logit vector? -------------------
    #
    # 4b compares logits and passes; check 4 compares logprobs and fails. The
    # only thing between them is answer_logprob, which appends the answer token
    # and reads the second-to-last row. That must be the same cell 4b just
    # compared. If 6a already disagrees -- no patching anywhere in it -- then
    # the identity was never about the patch at all.
    tok_a = int(ans[0, 0])
    lp_ref = torch.log_softmax(ref, dim=-1)[tok_a].item()
    lp_fn = M.answer_logprob(r, iy, gold)
    ok6a = abs(lp_ref - lp_fn) < 1e-2
    print(f"\n[{'OK ' if ok6a else 'BAD'}] 6a. answer_logprob(yes) == "
          f"log_softmax(源前向最后一行)[金 token]: "
          f"{lp_ref:+.4f} vs {lp_fn:+.4f}")

    lp_got = torch.log_softmax(got, dim=-1)[tok_a].item()
    with M.patch_layer(r, L, [int(ino.shape[1]) - 1], v):
        lp_fn_p = M.answer_logprob(r, ino, gold)
    ok6b = abs(lp_got - lp_fn_p) < 1e-2
    print(f"[{'OK ' if ok6b else 'BAD'}] 6b. answer_logprob(补丁后) == "
          f"log_softmax(补丁后 logits)[金 token]: "
          f"{lp_got:+.4f} vs {lp_fn_p:+.4f}")

    # Deterministic code makes this free. If it is not free, nothing above
    # means anything and the per-item spread in check 4 is just noise.
    lp_again = M.answer_logprob(r, iy, gold)
    ok6c = lp_again == lp_fn
    print(f"[{'OK ' if ok6c else 'BAD'}] 6c. 同一个调用跑两次相同: "
          f"{lp_fn:+.6f} vs {lp_again:+.6f}")

    # 4b again, at the sequence length answer_logprob actually uses. Causal
    # attention means appending the answer token cannot change any row before
    # it, so a failure here is the shape changing the arithmetic -- and check 4
    # runs at exactly this shape while 4b does not.
    with torch.no_grad():
        fy = torch.cat([iy, ans.to(iy.device)], dim=1)
        fn = torch.cat([ino, ans.to(ino.device)], dim=1)
        ref2 = r.model(fy, use_cache=False).logits[0, -2].float()
        with M.patch_layer(r, L, [int(ino.shape[1]) - 1], v):
            got2 = r.model(fn, use_cache=False).logits[0, -2].float()
    d2 = (got2 - ref2).abs().max().item()
    print(f"[{'OK ' if d2 < 5e-2 else 'BAD'}] 6d. 追加答案 token 后同一行仍相同: "
          f"max|diff| {d2:.4g}   (金 token logit "
          f"{ref2[tok_a].item():+.3f} vs {got2[tok_a].item():+.3f})")

    # ---- 7. where does appending one token start to matter? ---------------
    #
    # 6a and 6d both say the last prompt position moves when the answer token
    # is appended after it. Causal attention says it cannot: no row depends on
    # a row after it. So either the arithmetic differs (bf16 GEMMs reduce in a
    # different order at a different sequence length, and Qwen's late layers
    # carry activations big enough to make 0.4% of them matter), or something
    # is genuinely reading forward and that is a real bug.
    #
    # The profile tells them apart: arithmetic grows smoothly from a tiny value
    # at layer 0, because every layer's GEMM is a little different and the
    # residual stream accumulates it. A bug appears at one layer out of nowhere.
    # Confirm with --dtype float32: arithmetic collapses to ~1e-6, a bug does
    # not move.
    fy = torch.cat([iy, ans.to(iy.device)], dim=1)
    rows_a: dict[int, torch.Tensor] = {}
    rows_b: dict[int, torch.Tensor] = {}

    def grab(store, idx):
        def mk(L):
            def hook(_m, _i, o):
                hs = o[0] if isinstance(o, tuple) else o
                store[L] = hs[0, idx].detach().float().clone()
            return hook
        return mk

    for store, seq, idx in ((rows_a, iy, -1), (rows_b, fy, -2)):
        handles = []
        mk = grab(store, idx)
        try:
            for Li in range(r.n_layers):
                handles.append(r.layers[Li].register_forward_hook(mk(Li)))
            with torch.no_grad():
                r.model(seq, use_cache=False)
        finally:
            for h in handles:
                h.remove()

    print("\n[7] 同一位置,追加答案 token 前后的残差差异（因果注意力下应当为 0）")
    print("      层     max|diff|      该行 max|h|    相对")
    step = max(1, r.n_layers // 8)
    shown = sorted(set(list(range(0, r.n_layers, step)) + [r.n_layers - 1]))
    for Li in shown:
        d = (rows_a[Li] - rows_b[Li]).abs().max().item()
        n = rows_a[Li].abs().max().item()
        tail = "  <- 末层" if Li == r.n_layers - 1 else ""
        print(f"    {Li:>4}   {d:>11.4g}   {n:>12.4g}   {d / max(n, 1e-9):>7.2%}"
              f"{tail}")

    # ---- 5. the same thing one layer earlier ------------------------------
    #
    # Not an identity -- block L still runs on top -- so it is only a scale for
    # reading check 4: if L-1 is the same size as L, check 4 is measuring
    # something generic rather than a broken final layer.
    it = items[0]
    q, gold = it["question_mc"], it["answer_mc"]
    iy = M.encode(r, M.render(r, M.build_messages(q, skill, "mc")))
    ino = M.encode(r, M.render(r, M.build_messages(q, None, "mc")))
    lp_yes = M.answer_logprob(r, iy, gold)
    v = M.capture_block_outputs(r, iy, [L - 1], k=1)[L - 1]
    with M.patch_layer(r, L - 1, [int(ino.shape[1]) - 1], v):
        lp_prev = M.answer_logprob(r, ino, gold)
    print(f"\n[5] 倒数第二层（不是恒等,只作参照）: "
          f"lp_real {lp_prev:+.4f}  vs lp_yes {lp_yes:+.4f}  "
          f"diff {lp_prev - lp_yes:+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
