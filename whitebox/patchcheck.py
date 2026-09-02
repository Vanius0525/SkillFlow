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
    args = ap.parse_args()

    items = load_items(args.tasks, args.limit)
    skill = M.load_skill(args.skill)
    r = M.load(args.model, device=args.device)
    L = r.n_layers - 1
    print(f"model {args.model}   n_layers {r.n_layers}   last block {L}")
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
        print("    -> 有正有负：多半是 bf16 的数值差,被 0.641 的小分母放大了。"
              "确认的办法是把 model.load 的 dtype 临时改成 float32 再跑一次这个"
              "脚本 —— 差应当塌到 1e-5 量级。")

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
    print(f"
[{'OK ' if same else 'BAD'}] 4b. 补丁位置上的 logits 与源前向相同: "
          f"{same}   max|diff| {dmax:.4g}")
    if not same:
        print("     -> 补丁没有把那个位置变成源前向的状态。捕获点和写入点仍然"
              "不是同一个东西,先查这里,check 4 只是它的症状。")
    else:
        print("     -> 补丁生效了。那么差在 answer_logprob 读的位置或聚合方式上。")

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
