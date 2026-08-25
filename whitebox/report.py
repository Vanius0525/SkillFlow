#!/usr/bin/env python3
"""
Collect one run's summary.json files into a single readable page.

    python report.py results/20260821-1200
    python report.py results/20260821-1200 --json      # machine-readable

Written because the experiments print their own verdicts as they go, and over ssh
those scroll away. More importantly, the results only mean something TOGETHER:
E2 saying the effect compresses and E1 saying no layer reads the skill is a
contradiction, and a contradiction is only visible when the two numbers are on
the same page.

Each line carries the question the experiment answers, so the page is readable
by someone who has not memorised the design.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

QUESTION = {
    "e0": "有没有值得解释的效应？（不过门槛,后面全是在解释噪声）",
    "errors": "skill 消掉的是哪一类错？（格式 / 选择 / 检索）",
    "e7_repr": "注入之后表示层出现了什么 pattern？（一个方向还是逐题内容）",
    "e6_counterfactual": "模型真的在读那张表吗？（改掉一个值,答案跟谁走）",
    "e2_patch": "效应能不能压进一个向量？（能=H2 选择,不能=H1 检索）",
    "e1_knockout": "哪些层在读 skill？（早层=读一次,中后层持续=反复回看）",
}


def kind(s: dict) -> str:
    """
    Identify a summary.json.

    The structural fallbacks are not decoration. Three of the scripts wrote
    "experiment" into run-info.json and not into summary.json, so this function
    returned "unknown" for E1, E2 and E7 -- and an unknown summary takes every
    cross-check that needs it out of the report without saying so. The key is
    written into both files now; these clauses keep already-finished runs
    readable without rerunning them.
    """
    if "experiment" in s:
        return s["experiment"]
    if "acc_no_skill" in s:
        return "e0"
    if "no_skill" in s and "with_skill" in s and "moves" in s:
        return "errors"
    if "follow_rate" in s:
        return "e6_counterfactual"
    if "recovery_real" in s and "best_layer" in s:
        return "e2_patch"
    if "net" in s and "best_layers" in s:
        return "e1_knockout"
    if "per_skill" in s and "layers" in s:
        return "e7_repr"
    return "unknown"


def e0_gate(s: dict) -> bool:
    """
    The Phase 0 gate, per HANDOFF-whitebox.md section 2.

    Lifted out of fmt_e0 because cross_check needs it too: an axis split
    computed from a pair that never cleared the gate is a split of an effect
    nobody has confirmed exists, and saying that out loud is the difference
    between a finding and a story.
    """
    lp_lo = s.get("delta_logprob_ci95", [0.0, 0.0])[0]
    return (s["delta_acc_pp"] >= 15 and s["delta_acc_ci95_pp"][0] > 5) or \
           (s["delta_acc_pp"] >= 5 and lp_lo > 0)


def fmt_e0(s: dict) -> list[str]:
    lo, hi = s["delta_acc_ci95_pp"]
    out = [f"n={s['n']}   准确率 {s['acc_no_skill']:.3f} -> {s['acc_with_skill']:.3f}"
           f"  ({s['delta_acc_pp']:+.1f}pp, CI95 [{lo:+.1f},{hi:+.1f}])",
           # Section 2 makes logprob the primary DV and accuracy the readable
           # one, so its CI belongs on the page too -- especially when the gate
           # fails on the accuracy precondition, where this is the number that
           # says whether anything moved at all.
           f"logprob {s['mean_logprob_no_skill']:.3f} -> "
           f"{s['mean_logprob_with_skill']:.3f}  ({s['delta_logprob']:+.3f}"
           + (", CI95 [{:+.3f},{:+.3f}]".format(*s["delta_logprob_ci95"])
              if "delta_logprob_ci95" in s else "")
           + f")   配对 +{s['mcnemar_gained']}/-{s['mcnemar_lost']}"]
    pr = s.get("parse_rate_no_skill")
    ch = s.get("chance_level")
    if pr is not None:
        line = f"可解析率 {pr:.0%} / {s['parse_rate_with_skill']:.0%}"
        if ch:
            line += f"   随机水平 {ch:.2f}"
            if s["acc_no_skill"] < ch * 0.8:
                line += "   [!] 基线低于随机 —— 先查格式再谈机制"
        out.append(line)
    acc_no, d_acc = s["acc_no_skill"], s["delta_acc_pp"]
    lp_lo = s.get("delta_logprob_ci95", [0.0, 0.0])[0]
    head_pp = (1.0 - acc_no) * 100
    if s.get("is_control"):
        # A control is run to fail. Rendering it with the candidate-pair verdict
        # reads its success as a failure -- see HANDOFF 12.3j 第 2 条.
        if e0_gate(s):
            out.append("**这是负对照,而它过了门槛** —— 不该起作用的文档动了因变量,"
                       "主效应不能再当成内容特异的。先报这一条")
        else:
            out.append("负对照：**符合预期**（不该有效应,也确实没有）。"
                       "注意它自己的基线：贴地板或贴天花板时它本来也动不了,"
                       "排除掉的东西比看上去少")
    elif e0_gate(s):
        out.append("门槛：通过")
    else:
        out.append("门槛：**未通过** —— 这一对不要往下做")
        # Which clause failed decides what to change next: an item pool that is
        # too hard, one that is too easy, or a skill that does nothing.
        # Recomputed here rather than read from a key, so runs finished before
        # this existed still say it.
        if acc_no < 0.10:
            out.append("[!] 基线 {:.3f} 贴着地板（§2 要求上下都有余量）。这**不是**"
                       "可报告的零结果 —— 先按难度重挑题,再谈这份 skill 有没有用"
                       .format(acc_no))
        elif head_pp < 20:
            # The ceiling side had no line at all, and Tier B v2 landed on it:
            # a 0.819 baseline leaves 18.1pp of headroom, so the accuracy arm
            # (>=15pp, CI lower bound >5pp) asks the skill to fix 83% of
            # everything still wrong. A failure there is a fact about the item
            # pool, exactly as it was at the floor -- and the two get written
            # up the same way, which is why the same warning has to exist.
            out.append("[!] 基线 {:.3f},余量只有 {:.1f}pp。准确率那一档要 Δ≥15pp,"
                       "在这个基线上等于要求 skill 修好剩下错题的 {:.0%} —— 够不着。"
                       "这和 v1 贴地板是同一类问题（§2：要地板也要天花板）,"
                       "「未通过」在这里首先是关于题的事实"
                       .format(acc_no, head_pp, min(1.0, 15.0 / head_pp)))
        # Then which arm of the gate it missed, and by how much. -0.008 on the
        # logprob CI reads very differently from -0.405, and the point estimate
        # on the line above cannot tell them apart.
        if d_acc >= 5 and lp_lo <= 0:
            out.append("差在 logprob 那一档：CI 下界 {:+.3f}（要 >0）。方向对,"
                       "但还压不住 0 —— 不能当作确认了的效应往下用".format(lp_lo))
        elif d_acc < 5 and lp_lo > 0:
            out.append("差在准确率那一档（{:+.1f}pp < 5pp）,而 logprob 的 CI 整段"
                       "在 0 以上 —— 有位移,只是没大到能撑起恢复率的分母"
                       .format(d_acc))
        elif d_acc < 5 and "delta_logprob_ci95" not in s:
            # Old summaries have no logprob CI at all. Printing the 0.0 default
            # as if it were a measured bound invents a number.
            out.append("准确率那一档没够（{:+.1f}pp < 5pp）,而这份 summary 里没有"
                       " logprob 的 CI（旧版产物）—— 另一档判不了".format(d_acc))
        elif d_acc < 5:
            out.append("两档都没够：准确率 {:+.1f}pp < 5pp,logprob 的 CI 下界 "
                       "{:+.3f} 也含 0 —— 这一对上没有可解释的位移"
                       .format(d_acc, lp_lo))
    return out


def fmt_errors(s: dict) -> list[str]:
    n = s["n"]
    def dist(d):
        return "  ".join(f"{k} {v}({v/n:.0%})" for k, v in
                         sorted(d.items(), key=lambda kv: -kv[1]))
    fixed = {a.split("->")[0]: v for a, v in s["moves"].items()
             if a.endswith("->correct")}
    tot = sum(fixed.values()) or 1
    head = []
    if s.get("label"):
        head = [f"这一份用的是 skill: {s['label']}"]
    out = head + [f"无 skill : {dist(s['no_skill'])}",
            f"有 skill : {dist(s['with_skill'])}",
            f"修好的 {tot} 题来自： " +
            "  ".join(f"{k} {v}({v/tot:.0%})" for k, v in
                      sorted(fixed.items(), key=lambda kv: -kv[1]))]
    # Engagement vs mechanism. On Tier A 84% of the fixed items had been echoing
    # the question, so the headline delta was mostly the model starting to answer
    # at all -- upstream of anything the layer sweeps separate (§12.3j 第 3 条).
    st = s.get("strata")
    if st:
        a, e = st["attempted"], st["echoed"]
        out.append(f"分层： 本来就作答 n={a['n']} {a['acc_no']:.0%}->"
                   f"{a['acc_with']:.0%}   抄题干 n={e['n']} "
                   f"{e['acc_no']:.0%}->{e['acc_with']:.0%}")
        if e["n"] > a["n"]:
            out.append("[!] 半数以上的题本来就是「抄题干」—— 主效应是 engagement,"
                       "不是检索或选择。机制结论只能引「本来就作答」那一行,"
                       "而且要说明它的样本量")
    return out


def fmt_e7(s: dict) -> list[str]:
    out = []
    for name, rep in s["per_skill"].items():
        rel = rep["rel_norm"]
        pk = max(range(len(rel)), key=lambda i: rel[i])
        L = s["layers"][pk]
        out.append(f"{name}: 峰值层 {L}  ||d||/||h|| {rel[pk]:.3f}   "
                   f"逐题余弦 {rep['mean_pairwise_cos'][pk]:+.2f}   "
                   f"有效维数 {rep['participation_ratio'][pk]:.1f}/{s['n_items']}")
    for pair, cs in s.get("cross_skill_cosine", {}).items():
        out.append(f"{pair} 平均方向夹角余弦 最大 {max(cs):+.2f}"
                   f"（>0.5 = 注入有通用签名,与是哪份 skill 无关）")
    for cond, p in (s.get("probe") or {}).items():
        acc = p["acc"]
        bi = max(range(len(acc)), key=lambda i: acc[i])
        out.append(f"探针 {cond}: 最好 {acc[bi]:.2f} @层 {s['layers'][bi]}"
                   f"（打乱标签 {p['permuted'][bi]:.2f}）")
    return out


def fmt_e6(s: dict) -> list[str]:
    sh = s["shares"]["cf"]
    out = [f"n={s['n']}  扰动口味 {s['flavour']}",
           f"反事实条件下： 跟改过的值 {sh['cf']:.0%}   跟原值 {sh['true']:.0%}   "
           f"都不是 {sh['neither']:.0%}   没答案 {sh['unparsed']:.0%}"]

    # The logprob gap needs no answer extraction, so it survives the case below
    # -- print it always, and print all three conditions: the no_skill and true
    # rows are what say whether the generation-side numbers can be trusted.
    gaps = s.get("lp_gap") or {}
    if gaps:
        out.append("mean lp(cf) - lp(true)： "
                   + "   ".join(f"{c} {gaps[c]:+.3f}" for c in
                                ("no_skill", "true", "cf") if c in gaps)
                   + "   （>0 = 更想说反事实值）")

    fr = s["follow_rate"]
    decided = sh["cf"] + sh["true"]
    if decided < 0.2 or fr != fr:                       # fr != fr catches nan
        out.append(f"follow rate 无定义（只有 {decided:.0%} 的题选了两个值之一）"
                   " —— 分母就是这两类的和")
        out.append("[!] 反事实条件下模型基本两个值都不答。两种读法：H5（冲突把计算"
                   "打乱了），或者答案根本没被正确抽出来。**先看 per_item.jsonl 的"
                   "`raw` 字段**,再谈机制。")
    else:
        out.append(f"follow rate {fr:.0%}"
                   + ("   高 = 模型逐行读表 -> H1" if fr > 0.8 else
                      "   低 = 没在读这一行,效应来自别处" if fr < 0.2 else
                      "   混合 —— 用逐题标签切分 E1/E2 的曲线"))
    return out


def fmt_e2(s: dict) -> list[str]:
    lo, hi = s["best_recovery_ci95"]
    out = [f"n={s['n_items']}  K={s.get('tail_k', 1)}  分母(有-无 skill logprob) "
           f"{s['mean_logprob_delta']:+.3f}",
           f"最佳层 {s['best_layer']}  恢复率 {s['best_recovery']:+.3f} "
           f"CI95 [{lo:+.3f},{hi:+.3f}]",
           f"同层对照： 别题向量 {s['best_layer_mismatched']:+.3f}   "
           f"平均向量 {s['best_layer_meanvec']:+.3f}"]
    if s["best_layer_mismatched"] > 0.4:
        out.append("[!] 别题的向量也能恢复 —— 这一层测到的是扰动,不是 skill")
    # The filler condition is the one that decides whether any of the above is
    # about content. E7 found the injection direction is generic (§12.3j), and
    # if that carries into patching then recovery measures document-presence.
    fl = s.get("best_layer_filler")
    if fl is None:
        out.append("[!] **没有中性文档对照** —— E7 已经证明注入方向是通用的,"
                   "所以这个恢复率分不开「内容」和「上下文里有份长文档」。"
                   "加 --filler tasks/filler-neutral.md 重跑再读")
    else:
        margin = s["best_recovery"] - fl
        out.append(f"中性文档对照： {fl:+.3f}   内容余量 {margin:+.3f}")
        if margin < 0.15:
            out.append("[!] **中性文档恢复得一样多** —— 补丁送进去的是"
                       "「上下文里有份长文档」,不是这份 skill 的内容。"
                       "这个恢复率不能当 H1/H2 的证据用（§12.3j）")
        else:
            out.append(f"中性文档恢复得少 {margin:+.3f} —— 高出去的这部分才是"
                       "内容特异的,上面的判读要对着它读,不是对着 0")
    fcd = s.get("filler_ctx_delta")
    if fcd is not None and fcd == fcd:
        out.append(f"（参考）中性文档放进上下文本身的 logprob 位移 {fcd:+.3f},"
                   f"skill 是 {s['mean_logprob_delta']:+.3f}")
    return out


def fmt_e1(s: dict) -> list[str]:
    lo, hi = s["best_net_ci95"]
    out = [f"n={s['n_items']}  每组 {s['group']} 层  屏蔽宽度 "
           f"{s['blocked_width_tokens']} token（skill 全文）",
           f"峰值 层 {s['best_layers'][0]}-{s['best_layers'][-1]}  "
           f"net {s['best_net']:+.3f} CI95 [{lo:+.3f},{hi:+.3f}]"]
    bo = s.get("best_net_by_order") or {}
    if bo:
        sf, ff = bo.get("skill_first"), bo.get("filler_first")
        out.append(f"按文档顺序拆开： skill 在前 {sf:+.3f}   filler 在前 {ff:+.3f}")
        if sf is not None and ff is not None and sf == sf and ff == ff \
                and (sf > 0) != (ff > 0):
            out.append("[!] 两种顺序符号相反 —— 测到的是位置,不是内容")
    if lo <= 0:
        out.append("峰值 CI 含 0 —— 没有哪一层的依赖超过「挡住同样长度的任意片段」")
    return out


FMT = {"e0": fmt_e0, "errors": fmt_errors, "e7_repr": fmt_e7,
       "e6_counterfactual": fmt_e6, "e2_patch": fmt_e2, "e1_knockout": fmt_e1}
ORDER = ["e0", "errors", "e7_repr", "e6_counterfactual", "e2_patch", "e1_knockout"]


def cross_check(found: list) -> list[str]:
    """
    The part no single experiment can print: do they agree?

    Only pairs that can actually contradict each other are listed. Agreement is
    weak evidence; a contradiction is strong evidence that one instrument is
    broken, and that is the useful direction.

    Takes (kind, summary, path) triples: the Tier B v2 check below has to pair
    each errors.json with the e0 that produced its per-item file, and the stage
    directory name (`errors-tierB-const` <-> `e0-tierB-const`) is what records
    that pairing.
    """
    out = []
    e2 = [s for k, s, _ in found if k == "e2_patch"]
    e1 = [s for k, s, _ in found if k == "e1_knockout"]
    e6 = [s for k, s, _ in found if k == "e6_counterfactual"]
    e7 = [s for k, s, _ in found if k == "e7_repr"]
    e0_by_stage = {p.parent.name: s for k, s, p in found if k == "e0"}
    # E6 first: it is the only one of the three that uses no hooks, so when it
    # disagrees with E1 or E2 it is the one that decides. Computed up here so
    # the E2 x E1 reading below can refuse to draw a conclusion that E6 has
    # already contradicted.
    rates = [s["follow_rate"] for s in e6
             if s.get("follow_rate") == s.get("follow_rate") is not None]
    fr = max(rates) if rates else float("nan")
    swing = max((s["lp_gap"]["cf"] - s["lp_gap"]["true"] for s in e6
                 if "lp_gap" in s), default=float("nan"))
    e6_tracks = (fr > 0.8) or (swing > 0.5)

    if e2 and e1:
        rec = max(s["best_recovery"] for s in e2)
        mean_rec = max((s["best_layer_meanvec"] for s in e2
                        if "best_layer_meanvec" in s), default=float("nan"))
        net_lo = max(s["best_net_ci95"][0] for s in e1)
        late = any(s["best_layers"][0] > 0.5 * (s["best_layers"][-1] + 1) for s in e1)
        if rec > 0.5 and net_lo > 0 and late:
            out.append("E2 说压得进一个向量,E1 说中后层还在持续依赖原文 —— "
                       "这两个结论互斥,先查 selftest,不要挑一个讲。")
        elif rec > 0.5 and net_lo <= 0 and e6_tracks:
            # "E1 found nothing" is only evidence of read-once when E1 could
            # have found something. E6 saying the model tracks the document
            # turns the same silence into an instrument failure.
            out.append("E2 高恢复 + E1 无显著峰 本来读作「读一次就够」(H2),"
                       "但 E6 说模型在跟着文档走 —— 先把 E1 的功效问题解决,"
                       "这里不能下 H2 的结论。")
        elif rec > 0.5 and net_lo <= 0:
            out.append("E2 高恢复 + E1 无显著峰：一致,读作「读一次就够」(H2)。")
        elif rec < 0.2 and net_lo > 0:
            out.append("E2 低恢复 + E1 有峰：一致,读作「持续回看原文」(H1)。")
        # A mean vector that beats the real one is not a compression result.
        # Whatever the patch delivers, it is not this item's skill content --
        # it cannot be, the mean has none. Reported here rather than in
        # e2_patch.py as well because the two files answer to different
        # readers and this is the reading that gets copied into a writeup.
        if mean_rec == mean_rec and mean_rec > rec + 0.1:
            out.append(f"E2 的平均向量({mean_rec:+.2f})比真向量({rec:+.2f})还好 —— "
                       f"被补进去的不是这道题的 skill 内容。这是「注入了某个通用"
                       f"状态」,不是 H2 的证据。")

    # The E6 note itself. The nan case gets its own line: "the extractor
    # failed" and "the conflict disorganised the computation" produce the
    # same follow_rate and opposite conclusions, and only the swing separates
    # them.
    if e6:
        if not rates and swing > 0.5:
            out.append(f"E6 的 follow rate 是 nan（没有一题答出两个值之一）,"
                       f"但 lp 偏好的 swing 是 {swing:+.2f} —— 坏的是答案抽取,"
                       f"不是机制。跑 e6_diagnose.py 看 raw,别读成 H5。")
        elif not rates:
            out.append("E6 的 follow rate 是 nan,lp swing 也没有定论 —— 这一对"
                       "既不支持也不反驳 E1,别当成证据用。")
    if e6 and e1:
        net_lo = max(s["best_net_ci95"][0] for s in e1)
        if e6_tracks and net_lo <= 0:
            how = "生成的答案" if fr > 0.8 else f" lp 偏好(swing {swing:+.2f})"
            out.append(f"E6 按{how}判定模型在跟着文档走,而 E1 报「没有哪一层"
                       f"依赖 skill」—— **E1 坏了**。E6 不用 hook,它说了算。")
    # ---- Tier B v2: the double dissociation -------------------------------
    #
    # This is the one cross-check that IS the result rather than a consistency
    # test. Each errors.json says which column of the 2x2 its document moved;
    # the claim is that pchem-constants moves the units column and
    # pchem-procedure moves the relation column. One file cannot show that --
    # only the pair can -- so it lives here and nowhere else.
    errs = [(s, p) for k, s, p in found if k == "errors" and s.get("tier_b2")]
    by_label = {s.get("label", ""): (s, p) for s, p in errs}
    if len(by_label) >= 2:
        def axes(s):
            mv = s["moves"]
            wc = sum(v for a, v in mv.items() if a == "wrong_const->correct")
            wr = sum(v for a, v in mv.items() if a == "wrong_rel->correct")
            return wc, wr
        rows = {lab: axes(s) for lab, (s, _) in by_label.items()}
        out.append("Tier B v2 修好的题按轴拆开： " + "   ".join(
            f"{lab}: 单位轴 {wc}, 关系式轴 {wr}" for lab, (wc, wr) in rows.items()))
        # Whether each document's own e0 cleared the gate. Without this the
        # split below reads as a result; with it, an axis split of an
        # unconfirmed effect is labelled as what it is. `errors-tierB-const`
        # was produced from `e0-tierB-const/per_item.jsonl`, so the stage name
        # is the join key.
        gated = {}
        for lab, (_, p) in by_label.items():
            stage = p.parent.name
            e0s = e0_by_stage.get("e0-" + stage.split("-", 1)[1]) \
                if "-" in stage else None
            gated[lab] = e0_gate(e0s) if e0s else None
        ungated = [lab for lab, ok in gated.items() if ok is False]
        if len(ungated) == len(gated):
            out.append("[!] 这几对的 e0 都没过门槛（" + "、".join(ungated) +
                       "）—— 上面这个拆分是在拆一个还没被确认的效应。它可以当线索,"
                       "不能当分离的证据；先解决门槛（余量 / 题目难度）。")
        elif ungated:
            out.append("[!] " + "、".join(ungated) + " 的 e0 没过门槛,另一份过了 —— "
                       "两边的轴不在同一个证据等级上,不要并排读。")
        con = rows.get("pchem-constants")
        pro = rows.get("pchem-procedure")
        # Which axis each document's fixes actually landed on, per document.
        # The joint verdict below can say "half" while hiding the case that
        # matters most: a document whose fixes land on the axis it cannot
        # touch by construction (pchem-procedure contains no numbers at all).
        for lab, pair, idx in (("pchem-constants", con, 0),
                               ("pchem-procedure", pro, 1)):
            if not pair or sum(pair) == 0:
                continue
            tot = sum(pair)
            if pair[1 - idx] > 0.6 * tot:
                other = "关系式轴" if idx == 0 else "单位轴"
                out.append(f"{lab} 修好的 {tot} 题里,多数落在**{other}** —— 那是它"
                           f"按构造碰不到的轴。要么这些修复是噪声,要么效应不是"
                           f"内容特异的。")
            if tot < 10:
                out.append(f"{lab} 只修好了 {tot} 题,轴的比例在这个 n 上不稳定 —— "
                           f"当成方向,不要当成比例。")

        def own(pair, idx):
            """Did this document's fixes land mostly on the axis it owns?

            A bare > comparison is not enough: 18 against 17 satisfies it and
            means nothing. 60% of the document's own fixes is the smallest
            margin that still reads as 'this column and not the other'."""
            return sum(pair) > 0 and pair[idx] > 0.6 * sum(pair)

        if con and pro:
            if sum(con) == 0 or sum(pro) == 0:
                out.append("其中一份 skill 一题都没修好 —— 双重分离没有分母,"
                           "先看 e0 的门槛。")
            elif own(con, 0) and own(pro, 1):
                out.append("**双重分离成立**：常数那份主要修单位轴,方法那份主要"
                           "修关系式轴。两份文档在做不同的事,E2 的 example/"
                           "principle 对照有了行为层面的依据。")
            elif own(con, 0) or own(pro, 1):
                who = "常数那份" if own(con, 0) else "方法那份"
                out.append(f"只分离了一半：{who}落在自己的轴上,另一份没有。"
                           "报这个不对称,不要报「分离」。")
            else:
                # The cosine is read out of this run's E7 when it is here.
                # It was a literal in the source once, which meant the sentence
                # would keep asserting 0.97 on a run that measured something
                # else entirely.
                cos = max((max(c) for s in e7
                           for c in s.get("cross_skill_cosine", {}).values()),
                          default=float("nan"))
                out.append("**没有分离**：两份 skill 修的是同一批错。这直接反驳"
                           "「内容不同的 skill 走不同机制」—— 剩下的解释是"
                           "「上下文里有份长文档」"
                           + (f",和 E7 两份 skill 的方向余弦 {cos:+.2f} 一致。"
                              if cos == cos else "。E7 没在这个 run 里,"
                              "跑一次 e7 就能看这两条证据指不指向同一件事。"))

    # E7 on its own. A direction shared by two documents whose contents do not
    # overlap is only evidence about *skills* if a document that is not a skill
    # fails to produce the same direction. The neutral filler is that control,
    # and e7_repr.py accepts --skill more than once, so it costs one extra pass
    # over the same items -- the cheapest missing control in the whole ladder.
    if e7:
        pairs = {p: max(c) for s in e7
                 for p, c in (s.get("cross_skill_cosine") or {}).items()}
        ctrl = {p: v for p, v in pairs.items() if "filler" in p}
        real = {p: v for p, v in pairs.items() if "filler" not in p}
        hi_real = max(real.values()) if real else float("nan")
        if ctrl:
            hi = max(ctrl.values())
            line = f"E7 中性对照（filler）的方向余弦 {hi:+.2f}"
            if hi_real == hi_real:
                line += f",两份 skill 之间 {hi_real:+.2f} —— " + (
                    "对照一样高,那么测到的是「上下文里多了一份长文档」,"
                    "不是 skill 的签名。" if hi > 0.5 * hi_real else
                    "对照明显更低,共享方向确实来自 skill 这一类文档。")
            else:
                # One skill plus the control: there is no skill-skill pair to
                # compare against, but the control alone still decides whether
                # the direction is about documents or about this document.
                line += " —— " + (
                    "中性文档走的是同一个方向,那么这个方向是「上下文里多了一份"
                    "长文档」,不是 skill 的签名。" if hi > 0.5 else
                    "中性文档走不出这个方向,所以它不是「多了一段长文本」的普遍"
                    "扰动。")
            out.append(line)
        elif hi_real == hi_real and hi_real > 0.5:
            out.append(f"E7 说两份内容互斥的 skill 走同一个方向（余弦 "
                       f"{hi_real:+.2f}）,但这个 run 里**没有中性对照** —— "
                       f"「注入有通用签名」和「上下文里多了一份长文档」现在分不开。"
                       f"把 tasks/filler-neutral.md 当第三个 --skill 再跑一次 e7 "
                       f"就能分开,不用重跑别的阶段。")

    if e7 and e2:
        rec_mean = max(s["best_layer_meanvec"] for s in e2)
        cos = max((max(r["mean_pairwise_cos"]) for s in e7
                   for r in s["per_skill"].values()), default=float("nan"))
        if rec_mean > 0.5 and cos < 0.2:
            out.append("E2 说一个平均向量就够,而 E7 说各题的位移方向几乎不相关 —— "
                       "两者不可能同时对。")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.run_dir)
    if not root.is_dir():
        print(f"[FAIL] not a directory: {root}"); sys.exit(1)

    found = []
    for f in sorted(root.rglob("summary.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        found.append((kind(s), s, f))
    # errors.py writes its report under whatever --out was given
    for f in sorted(root.rglob("errors*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if kind(s) == "errors":
            found.append(("errors", s, f))

    if args.json:
        print(json.dumps([{"kind": k, "path": str(p), "summary": s}
                          for k, s, p in found], indent=2, ensure_ascii=False))
        return

    print("=" * 70)
    print(f" 白盒实验汇总   {root}")
    print("=" * 70)
    if not found:
        print("\n 这个目录里没有 summary.json。跑过了吗？")
        return

    found.sort(key=lambda x: (ORDER.index(x[0]) if x[0] in ORDER else 99, str(x[2])))
    for k, s, f in found:
        name = f.parent.name
        print(f"\n[{k}]  {name}")
        print(f"  问题: {QUESTION.get(k, '?')}")
        def unknown(_s: dict) -> list[str]:
            # Naming the keys turns "unknown format" into something diagnosable
            # without opening the file: the mismatch is always a key mismatch.
            return ["(未知的 summary 格式)",
                    "  它有这些键: " + ", ".join(sorted(_s)[:12])]

        for line in FMT.get(k, unknown)(s):
            print(f"  {line}")

    # A cross-check that cannot run is reported, not skipped. An empty section
    # reads as "nothing contradicts", which is the one thing it must never mean
    # when the reason is that a summary was not recognised.
    kinds = {k for k, _, _ in found}
    notes = cross_check(found)
    missing = [n for n, k in (("E1", "e1_knockout"), ("E2", "e2_patch"),
                              ("E6", "e6_counterfactual"), ("E7", "e7_repr"))
               if k not in kinds]
    print("\n" + "-" * 70)
    print(" 交叉校验（单看任何一条曲线都看不出来的部分）")
    for nline in notes:
        print(f"  - {nline}")
    if missing:
        print(f"  - 用到 {'/'.join(missing)} 的检查没做：这个 run 里没有它们,"
              "或者没认出它们的 summary。")
    if not notes and not missing:
        print("  - 几个实验之间没有互相矛盾的地方。")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
