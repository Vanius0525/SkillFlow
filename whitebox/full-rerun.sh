#!/usr/bin/env bash
# The full-dataset rerun of every main-text MedCalc x Qwen3-8B experiment.
#
#   ./whitebox/full-rerun.sh plan            # print the job table, launch nothing
#   ./whitebox/full-rerun.sh push            # push code to every host in the table
#   ./whitebox/full-rerun.sh launch [tag...] # launch all jobs, or only the named tags
#   ./whitebox/full-rerun.sh status          # rows written so far, per job
#
# WHY. Until now the MedCalc x Qwen3-8B results sampled 4 rescued instances from
# each of the 40 calculators with the most of them: 160 of 470 rescued items,
# and 60 items over 15 calculators after the restriction. Every job here is the
# same measurement with `--per-calc 20 --max-calcs 55`, which takes every
# rescued item of every calculator that has at least two (469 items, 49
# calculators). Nothing else about the runs changes.
#
# SPLITTING. Jobs are split by ARM, never by item: each run re-derives its donor
# pools (cross / near / far / dall) from its own item set, so two runs over the
# SAME items with disjoint arms are mergeable (`span_summary.py --merge`), while
# two runs over different items are not comparable arm for arm. The `-a` job of
# a pair carries `--baselines`; its partner merges them by instance_id.
#
# The tags are deliberately new (`full-*`): launch.sh refuses to reuse a tag,
# and the old `fixmask-*` / `big40-*` results stay on disk as the subset runs
# the paper currently cites.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
B=/inspire/ssd/project/project-public/czxs253130660
MODEL="$B/models/Qwen3-8B"
FULL="--per-calc 20 --max-calcs 55"          # every rescued item, 469 / 49 calc
COMMON="--model $MODEL $FULL --max-new 900"
SPAN="$COMMON --mode decode --filler fixedskill --layers 8"

# host | tag | module | args
JOBS=(
"hsw|full-battery-a|wb_spanvec|$SPAN --arms real,realm,a0.5,dnear,dfar --baselines"
"hsw2|full-battery-b|wb_spanvec|$SPAN --arms dshuf,drand,dcross"
"hsw3|full-rank-a|wb_spanvec|$SPAN --arms rank4,rank16,rank32"
"wb|full-rank-b|wb_spanvec|$SPAN --arms rank64,rank128,rank16lo,rank64lo"
"wb2|full-depth-a|wb_spanvec|$COMMON --mode decode --filler fixedskill --layers 0,4,8 --arms real"
"wb3|full-depth-b|wb_spanvec|$COMMON --mode decode --filler fixedskill --layers 12,14,15,16,20 --arms real"
"sra1|full-dose|wb_spanvec|$SPAN --arms a0.4,a0.5,a0.55,a0.6,a0.7,a2"
"sra2|full-quarters|wb_spanvec|$SPAN --arms q0,q1,q2,q3"
"sra3|full-ko|wb_knockout|--model $MODEL $FULL --max-new 900 --sweep layers --layer-stride 4 --cells-keep R"
# L13 and L17-19 complete a stride-1 depth sweep from 12 to 20 when merged with
# full-depth-b (12,14,15,16,20). The subset run puts the whole drop between
# layers 12 (rho 0.77) and 14 (rho 0.28) with layer 13 never measured, so this
# is the job that says whether the handover is a step or a two-layer ramp.
# No --baselines: it merges with full-battery-a by instance_id, as -a/-b do.
"wb4|full-depth-c13|wb_spanvec|$COMMON --mode decode --filler fixedskill --layers 13 --arms real"
"sra4|full-window|wb_spanpatch|--model $MODEL $FULL --max-new 900 --matched --span skill --layers 16 --window 8:11 --window 12:15 --window 14:19 --window 16:35"
# queued, launched as soon as a box frees up (doc-last needs its own receiver
# and padding, so it cannot share a run with the doc-first jobs)
"wb4|full-depth-d|wb_spanvec|$COMMON --mode decode --filler fixedskill --layers 17,18,19 --arms real"
"hsw3|full-dl-a|wb_spanvec|$COMMON --mode decode --filler fixedskill --doc-last --layers 8,16 --arms real,dbar --baselines"
"wb|full-dl-b|wb_spanvec|$COMMON --mode decode --filler fixedskill --doc-last --layers 8,16 --arms dother,dpar,dperp"
)

cmd="${1:-plan}"; shift || true
want=("$@")

wanted() {           # no tag arguments means "all of them"
  [ ${#want[@]} -eq 0 ] && return 0
  for t in "${want[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

case "$cmd" in
plan)
  printf '%-6s %-16s %-12s %s\n' HOST TAG MODULE ARGS
  for j in "${JOBS[@]}"; do IFS='|' read -r h t m a <<<"$j"
    printf '%-6s %-16s %-12s %s\n' "$h" "$t" "$m" "${a//$B/\$B}"
  done
  ;;
push)
  for j in "${JOBS[@]}"; do IFS='|' read -r h t m a <<<"$j"
    [ "$h" = "QUEUE" ] && continue
    echo "== push $h"; "$HERE/push_local.sh" "inspire-me-wt-gpu-$h" howskill whitebox
    # /root is wiped when the platform reclaims an instance, so every box also
    # mirrors its results to the shared fileset (see whitebox/mirror.sh)
    "$HERE/mirror_start.sh" "$h"
  done
  ;;
launch)
  for j in "${JOBS[@]}"; do IFS='|' read -r h t m a <<<"$j"
    [ "$h" = "QUEUE" ] && continue
    wanted "$t" || continue
    echo "== launch $t on $h"; "$HERE/launch.sh" "$h" "$t" "$m" "$a"
  done
  ;;
status)
  for j in "${JOBS[@]}"; do IFS='|' read -r h t m a <<<"$j"
    [ "$h" = "QUEUE" ] && continue
    n=$(timeout 40 ssh "inspire-me-wt-gpu-$h" "wc -l < /root/out/$t.jsonl 2>/dev/null || echo 0" 2>/dev/null | tr -d ' \r')
    run=$(timeout 40 ssh "inspire-me-wt-gpu-$h" "pgrep -f '[w]b_span|[w]b_knock' >/dev/null && echo RUN || echo idle" 2>/dev/null | tr -d ' \r')
    printf '%-6s %-16s %5s rows  %s\n' "$h" "$t" "${n:-?}" "${run:-unreachable}"
  done
  ;;
*) echo "usage: $0 {plan|push|launch [tag...]|status}"; exit 2;;
esac
