#!/usr/bin/env bash
# Block until a watched job changes state, then print what changed and exit.
#
#   ./whitebox/watch_jobs.sh host:tag [host:tag ...]
#
# Meant to run in the background from the local session: it exits -- and so
# wakes whoever started it -- when a job's process is gone (finished or died) or
# its box stops answering twice in a row (the 2026-09-13 reclaim). Polls every
# WATCH_INTERVAL seconds (default 600). Row counts are printed on exit so a
# death can be told from a completion. The pgrep pattern is written [o]ut/ so it
# cannot match the ssh command line that carries it -- `pgrep -f out/x` always
# finds itself, which kept an earlier wait loop alive for good -- and so does
# any other literal out/<tag>.jsonl in the same command, hence o''ut below.
set -uo pipefail
INTERVAL="${WATCH_INTERVAL:-600}"
declare -A miss
while true; do
  for ht in "$@"; do
    h="${ht%%:*}"; t="${ht#*:}"
    out=$(timeout 40 ssh -o ConnectTimeout=15 -o BatchMode=yes "inspire-me-wt-gpu-$h" \
      "d=/root/o''ut; n=\$(wc -l < \$d/$t.jsonl 2>/dev/null || echo 0); \
       if pgrep -f '[o]ut/$t.jsonl' >/dev/null; then echo RUN \$n; else echo DONE \$n; fi" \
      2>/dev/null | grep -E '^(RUN|DONE) ')
    if [ -z "$out" ]; then
      miss[$ht]=$(( ${miss[$ht]:-0} + 1 ))
      if [ "${miss[$ht]}" -ge 2 ]; then
        echo "[$(date +%m-%d_%H:%M)] UNREACHABLE $ht (twice) -- reclaimed?"; exit 0
      fi
      continue
    fi
    miss[$ht]=0
    read -r state rows <<< "$out"
    if [ "$state" = DONE ]; then
      tail=$(timeout 30 ssh "inspire-me-wt-gpu-$h" "tail -3 /root/out/$t.log" 2>/dev/null | tr '\n' ' ' | cut -c1-300)
      echo "[$(date +%m-%d_%H:%M)] DONE $ht rows=$rows | $tail"; exit 0
    fi
  done
  sleep "$INTERVAL"
done
