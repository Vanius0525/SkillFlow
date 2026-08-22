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
    gate = (s["delta_acc_pp"] >= 15 and s["delta_acc_ci95_pp"][0] > 5) or \
           (s["delta_acc_pp"] >= 5 and s["delta_logprob_ci95"][0] > 0)
    if gate:
        out.append("门槛：通过")
    else:
        out.append("门槛：**未通过** —— 这一对不要往下做")
        # Which clause failed decides what to change next: an item pool that is
        # too hard, or a skill that does nothing. Recomputed here rather than
        # read from a key, so runs finished before this existed still say it.
        if s["acc_no_skill"] < 0.10:
            out.append("[!] 基线 {:.3f} 贴着地板（§2 要求上下都有余量）。这**不是**"
                       "可报告的零结果 —— 先按难度重挑题,再谈这份 skill 有没有用"
                       .format(s["acc_no_skill"]))
        elif s["delta_acc_pp"] < 5 and s.get("delta_logprob_ci95", [0])[0] > 0:
            out.append("差在准确率那一档（{:+.1f}pp < 5pp）,而 logprob 的 CI 整段"
                       "在 0 以上 —— 有位移,只是没大到能撑起恢复率的分母"
                       .format(s["delta_acc_pp"]))
    return out


def fmt_errors(s: dict) -> list[str]:
    n = s["n"]
    def dist(d):
        return "  ".join(f"{k} {v}({v/n:.0%})" for k, v in
                         sorted(d.items(), key=lambda kv: -kv[1]))
    fixed = {a.split("->")[0]: v for a, v in s["moves"].items()
             if a.endswith("->correct")}
    tot = sum(fixed.values()) or 1
    return [f"无 skill : {dist(s['no_skill'])}",
            f"有 skill : {dist(s['with_skill'])}",
            f"修好的 {tot} 题来自： " +
            "  ".join(f"{k} {v}({v/tot:.0%})" for k, v in
                      sorted(fixed.items(), key=lambda kv: -kv[1]))]


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


def cross_check(found: dict) -> list[str]:
    """
    The part no single experiment can print: do they agree?

    Only pairs that can actually contradict each other are listed. Agreement is
    weak evidence; a contradiction is strong evidence that one instrument is
    broken, and that is the useful direction.
    """
    out = []
    e2 = [s for k, s in found if k == "e2_patch"]
    e1 = [s for k, s in found if k == "e1_knockout"]
    e6 = [s for k, s in found if k == "e6_counterfactual"]
    e7 = [s for k, s in found if k == "e7_repr"]
    if e2 and e1:
        rec = max(s["best_recovery"] for s in e2)
        net_lo = max(s["best_net_ci95"][0] for s in e1)
        late = any(s["best_layers"][0] > 0.5 * (s["best_layers"][-1] + 1) for s in e1)
        if rec > 0.5 and net_lo > 0 and late:
            out.append("E2 说压得进一个向量,E1 说中后层还在持续依赖原文 —— "
                       "这两个结论互斥,先查 selftest,不要挑一个讲。")
        elif rec > 0.5 and net_lo <= 0:
            out.append("E2 高恢复 + E1 无显著峰：一致,读作「读一次就够」(H2)。")
        elif rec < 0.2 and net_lo > 0:
            out.append("E2 低恢复 + E1 有峰：一致,读作「持续回看原文」(H1)。")
    if e6 and e1:
        fr = max(s["follow_rate"] for s in e6)
        net_lo = max(s["best_net_ci95"][0] for s in e1)
        if fr > 0.8 and net_lo <= 0:
            out.append("E6 证明模型在逐行读表,而 E1 报「没有哪一层依赖 skill」—— "
                       "**E1 坏了**。E6 不用 hook,它说了算。")
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
    notes = cross_check([(k, s) for k, s, _ in found])
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
