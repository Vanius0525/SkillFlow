#!/usr/bin/env bash
# Watch the full-rerun jobs and EXIT as soon as one genuinely needs attention.
#
# Exiting is the point: the shell that started this in the background is told
# when it finishes, so a job that dies at 03:00 surfaces then instead of at the
# next time somebody remembers to look. A quiet run just keeps logging.
#
#   (nohup setsid ./whitebox/watch.sh 600 >> logs/watch.log 2>&1 </dev/null &)
#
# RUN IT DETACHED, not as a harness background task. Twice on 2026-09-17 the
# harness killed it under memory pressure (head_map.py was holding the 147 MB
# full-heads file as parsed objects); autofetch.sh, started with setsid, was
# never touched. A detached daemon also survives the session. It writes
# logs/watch.alert on an alert so a poller with no memory footprint -- or the
# next scheduled check -- can pick it up.
#
# Exit 0 = every job finished. Exit 3 = something stopped early or a box went
# away for STRIKES consecutive rounds; the log's last lines say which.
#
# TWO THINGS THE FIRST VERSION GOT WRONG (2026-09-16, both seen within an hour):
#
#   * timeouts of 25s/12s reported six live boxes as unreachable the moment a
#     few `inspire notebook list` calls ran alongside it -- every ssh here goes
#     through the same `notebook ssh-proxy` ProxyCommand, and it queues. The
#     budget is now 90s/40s and one failure is a strike, not a verdict.
#   * an ssh failure left the state as "?", which counted as neither running
#     nor finished, so a round in which EVERY box was briefly unreachable would
#     have reported "all jobs finished" and exited 0. Unknown is now explicitly
#     not-finished.
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
LOG=$ROOT/logs/watch.log
INTERVAL="${1:-600}"
TARGET="${2:-469}"          # rows a finished job should have
STRIKES="${3:-3}"           # consecutive bad rounds before it is real
JOBS="hsw:full-battery-a hsw2:pc-lpcot hsw3:full-dl-a wb:full-dl-b \
wb2:heads-ko wb3:full-depth-b wb4:full-depth-d sra1:full-dose \
sra3:full-ko sra4:full-window"
declare -A LAST BAD
while true; do
  line="$(date +%m-%d_%H:%M)"; alert=""; live=0; donec=0
  for j in $JOBS; do
    h=${j%%:*}; t=${j##*:}
    out=$(timeout 90 ssh -o ConnectTimeout=40 -o BatchMode=yes "inspire-me-wt-gpu-$h" \
          "echo \$(wc -l < /root/out/$t.jsonl 2>/dev/null || echo 0) \
              \$(pgrep -f '[w]b_span|[w]b_knock|[w]b_heads|[w]b_lpcot' >/dev/null && echo R || echo i)" \
          </dev/null 2>/dev/null | tr -d '\r' | tail -1)
    n=$(echo "$out" | awk '{print $1}'); r=$(echo "$out" | awk '{print $2}')
    case "$r" in
      R|i) ;;
      *)   # unknown: a strike, never a verdict, and never "finished"
           BAD[$h]=$(( ${BAD[$h]:-0} + 1 ))
           line="$line  $h:??(${BAD[$h]}/$STRIKES)"
           [ "${BAD[$h]}" -ge "$STRIKES" ] && alert="$alert $h-unreachable-x${BAD[$h]}"
           live=$((live+1))          # assume still working until proven otherwise
           continue;;
    esac
    BAD[$h]=0
    n=${n:-0}
    d=$(( n - ${LAST[$h]:-0} )); LAST[$h]=$n
    line="$line  $h:$n$r(+$d)"
    if [ "$r" = i ]; then
      if [ "$n" -ge "$TARGET" ] 2>/dev/null; then donec=$((donec+1))
      else alert="$alert $h/$t-stopped-at-$n"; fi
    else
      live=$((live+1))
    fi
  done
  echo "$line" >> "$LOG"
  if [ -n "$alert" ]; then
    echo "[$(date +%m-%d_%H:%M)] ATTENTION:$alert" >> "$LOG"
    echo "[$(date +%m-%d_%H:%M)] ATTENTION:$alert" > "$ROOT/logs/watch.alert"
    exit 3
  fi
  if [ "$live" -eq 0 ]; then
    echo "[$(date +%m-%d_%H:%M)] all $donec jobs finished" >> "$LOG"
    echo "[$(date +%m-%d_%H:%M)] all $donec jobs finished" > "$ROOT/logs/watch.alert"
    exit 0
  fi
  sleep "$INTERVAL"
done
