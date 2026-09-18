#!/usr/bin/env bash
# Runs ON a GPU box: work through /root/q/jobs.txt one job at a time, forever.
#
#   setsid nohup bash /root/wb/whitebox/qrun.sh [name] >/root/q/<name>.out 2>&1 &
#
# [name] (default `jobs`) selects /root/q/<name>.txt, so a box with a small
# model can run two queues side by side (e.g. `jobs` and `jobs2`).
#
# WHY. A box whose job finished sits at 0% GPU until somebody looks, and the
# periodic check is hours apart; the platform does not tolerate idle GPUs. The
# queue is read afresh after every job, so appending a line is how a box gets
# more work, and a box with nothing left writes /root/q/idle, which the local
# fleet daemon (whitebox/fleet.sh) turns into `inspire notebook stop`.
#
# Queue lines:   tag|module|args
#   module wb_*  -> python -m howskill.<module> <args> --out /root/out/<tag>.jsonl --resume
#   module e14   -> whitebox/e14_decomp.py <args> --run-id tA/<tag> --resume
#                   (whitebox/results/tA is a symlink into /root/out/tA, so the
#                   per-layer files land where mirror.sh copies from)
#
# Every module here resumes by instance (or by layer, for e14), so a job that a
# reclaim cut short is simply started again. If /root was wiped, the longest
# copy of the tag on the shared mirror is restored first.
set -u
B=/inspire/ssd/project/project-public/czxs253130660
NAME="${1:-jobs}"
Q=/root/q/$NAME.txt
IDLE=/root/q/$NAME.idle
OUT=/root/out
PY=$B/venvs/whitebox/bin/python
mkdir -p /root/q "$OUT/tA" /root/wb/whitebox/results
[ -e /root/wb/whitebox/results/tA ] || ln -s "$OUT/tA" /root/wb/whitebox/results/tA
touch "$Q"
log() { echo "$(date +%m-%d_%H:%M:%S) [$NAME] $*" >> /root/q/qrun.log; }
log "runner up, pid $$"
while true; do
  next=""
  while IFS='|' read -r tag mod args; do
    [ -z "${tag// /}" ] && continue
    case "$tag" in \#*) continue;; esac
    # a done marker survives a rebuild on the shared mirror, not in /root
    if [ ! -e "$OUT/$tag.done" ] && ls $B/wbout/*/"$tag".done >/dev/null 2>&1; then
      touch "$OUT/$tag.done"
    fi
    [ -e "$OUT/$tag.done" ] || [ -e "$OUT/$tag.failed" ] && continue
    next="$tag|$mod|$args"; break
  done < "$Q"
  if [ -z "$next" ]; then
    [ -e "$IDLE" ] || { date +%s > "$IDLE"; log "queue empty"; }
    sleep 60; continue
  fi
  rm -f "$IDLE"
  IFS='|' read -r tag mod args <<<"$next"
  if [ "$mod" = e14 ]; then
    if [ ! -d "$OUT/tA/$tag" ]; then
      src=$(ls -d $B/wbout/*/tA/$tag 2>/dev/null | head -1)
      [ -n "$src" ] && cp -r "$src" "$OUT/tA/$tag" && log "restored $tag from $src"
    fi
  elif [ ! -s "$OUT/$tag.jsonl" ]; then
    src=$(ls -S $B/wbout/*/"$tag".jsonl 2>/dev/null | head -1)
    [ -n "$src" ] && cp "$src" "$OUT/$tag.jsonl" && log "restored $tag from $src"
  fi
  n=$(cat "$OUT/$tag.attempts" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$OUT/$tag.attempts"
  log "start $tag (attempt $n)"
  if [ "$mod" = e14 ]; then
    (cd /root/wb/whitebox && exec $PY -u e14_decomp.py $args --run-id "tA/$tag" --resume) >> "$OUT/$tag.log" 2>&1
  else
    (cd /root/wb/howskill && exec $PY -u -m "howskill.$mod" $args --out "$OUT/$tag.jsonl" --resume) >> "$OUT/$tag.log" 2>&1
  fi
  rc=$?
  if [ $rc -eq 0 ]; then
    touch "$OUT/$tag.done"; log "done $tag"
  elif [ $n -ge 3 ]; then
    touch "$OUT/$tag.failed"; log "FAILED $tag rc=$rc after $n attempts"
  else
    log "exit $tag rc=$rc, will retry"; sleep 30
  fi
done
