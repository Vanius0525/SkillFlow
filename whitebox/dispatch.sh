#!/usr/bin/env bash
# Keep every GPU box busy, and never lose a finished result.
#
# The platform reclaims an instance whose GPU has been idle for a while, and
# /root is overlay, so an idle box is not just wasted -- it is a box whose
# outputs are about to be deleted. Four were reclaimed that way in one
# afternoon. So the loop is: when a host has no python running, FETCH first,
# then push the current code, then start the next queued job on it.
#
#   ./dispatch.sh queue/round3.txt 2>&1 | tee logs/dispatch.log
#
# The liveness test matches the venv python explicitly. Matching the module
# name alone also matches the `bash -c` wrapper ssh leaves behind, which
# outlives the job and makes a finished box look busy forever. The bracket
# around the first letter stops pgrep matching its OWN wrapper, whose command
# line contains the pattern verbatim -- without it every host reads busy.
#
# Queue lines are:  <tag><TAB><args for wb_spanvec>
# A line is claimed by renaming it into queue/<tag>.claimed, so a restart of
# this script does not double-launch.
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
QUEUE="${1:?queue file}"
HOSTS=(hsw hsw2 hsw3 wb wb2 wb3)
FETCH="$ROOT/howskill/results/p8-wb/fetched/by-host"
BASE=/inspire/ssd/project/project-public/czxs253130660
STATE="$ROOT/whitebox/queue/.claimed"
touch "$STATE"

next_job () {
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \#*) continue;; esac
    tag="${line%%	*}"
    grep -qx "$tag" "$STATE" && continue
    echo "$line"
    return 0
  done < "$QUEUE"
  return 1
}

for round in $(seq 1 400); do
  any_busy=0
  for h in "${HOSTS[@]}"; do
    if timeout 25 ssh -o ConnectTimeout=12 -o BatchMode=yes "inspire-me-wt-gpu-$h" \
         'pgrep -f "[w]hitebox/bin/python.*wb_spanvec" >/dev/null' 2>/dev/null; then
      any_busy=1
      continue
    fi
    # unreachable hosts are left alone; a reclaimed instance needs a start,
    # which is a decision, not something a polling loop should make
    timeout 25 ssh -o ConnectTimeout=12 -o BatchMode=yes "inspire-me-wt-gpu-$h" true 2>/dev/null || {
      echo "[$(date +%H:%M)] $h unreachable"; continue; }

    mkdir -p "$FETCH/$h"
    for f in $(timeout 40 ssh "inspire-me-wt-gpu-$h" 'ls /root/out/*.jsonl 2>/dev/null' 2>/dev/null); do
      b=$(basename "$f")
      [ -s "$FETCH/$h/$b" ] && continue
      timeout 120 ssh "inspire-me-wt-gpu-$h" "cat $f" > "$FETCH/$h/$b" 2>/dev/null
      if [ -s "$FETCH/$h/$b" ]; then
        echo "[$(date +%H:%M)] fetched $h/$b ($(wc -l < "$FETCH/$h/$b") rows)"
      else
        rm -f "$FETCH/$h/$b"
      fi
    done

    job=$(next_job) || { echo "[$(date +%H:%M)] $h free, queue empty"; continue; }
    tag="${job%%	*}"; args="${job#*	}"
    echo "$tag" >> "$STATE"
    "$ROOT/whitebox/push_local.sh" "inspire-me-wt-gpu-$h" howskill >/dev/null 2>&1
    timeout 50 ssh "inspire-me-wt-gpu-$h" "cd /root/wb/howskill && \
      setsid nohup $BASE/venvs/whitebox/bin/python -u -m howskill.wb_spanvec \
        --model $BASE/models/Qwen3-8B --max-new 900 --per-calc 4 --max-calcs 10 \
        $args --out /root/out/$tag.jsonl </dev/null > /root/out/$tag.log 2>&1 & disown" \
      >/dev/null 2>&1
    echo "[$(date +%H:%M)] launched $tag on $h"
    any_busy=1
  done
  sleep 240
done
