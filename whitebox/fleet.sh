#!/usr/bin/env bash
# Local fleet daemon: keep every GPU box either working or stopped.
#
#   (nohup setsid ./whitebox/fleet.sh 600 >> logs/fleet.log 2>&1 </dev/null &)
#
# Every INTERVAL seconds, for each host that has a queue in whitebox/queues/:
#
#   * reachable, every queue idle for > IDLE_MIN minutes and no python running
#       -> `inspire notebook stop`. A box with nothing to do must not sit at 0%
#          GPU; the platform does not tolerate it. Recorded in logs/fleet.stopped
#          so the next rule does not start it again.
#   * reachable, a queue runner missing (container rebuilt under us)
#       -> qstart.sh --push, which restores from the shared mirror and resumes.
#   * unreachable STRIKES rounds running, and the platform says STOPPED, and we
#     did not stop it ourselves
#       -> start, refresh the tunnel (it often takes two tries), forget the old
#          host key, push, restart the runner. Twice the platform stopped every
#          instance at once (09-13, 09-17); without this a stop at 03:00 costs
#          every box the hours until the next manual check.
#
# One line per host per round goes to logs/fleet.log; anything that needs a
# human goes to logs/fleet.alert as well.
#
# Run it detached (setsid), never as a harness background task: the harness
# kills its own tasks under memory pressure (HANDOFF-TAKEOVER-09-18 §5.1).
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
cd "$ROOT"
INTERVAL="${1:-600}"
IDLE_MIN="${IDLE_MIN:-15}"
STRIKES="${STRIKES:-3}"
WS=可上网GPU资源
ALERT=$ROOT/logs/fleet.alert
STOPPED=$ROOT/logs/fleet.stopped
touch "$STOPPED"
declare -A BAD
ts() { date +%m-%d_%H:%M; }

hosts() { ls whitebox/queues/*.txt 2>/dev/null | sed 's#.*/##; s#\.2\.txt$##; s#\.txt$##' | sort -u; }

restart() {
  local h=$1
  echo "[$(ts)] $h: restarting (platform-stopped with unfinished queue)"
  timeout 300 inspire notebook start "wt-gpu-$h" --workspace "$WS" --wait >/dev/null 2>&1
  for try in 1 2 3 4; do
    timeout 300 inspire notebook connection refresh "wt-gpu-$h" --workspace "$WS" 2>&1 \
      | grep -q '^OK' && break
    sleep 30
  done
  ssh-keygen -R "[wt-gpu-$h]:22222" >/dev/null 2>&1
  sleep 20
  if timeout 120 ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
       "inspire-me-wt-gpu-$h" true </dev/null >/dev/null 2>&1; then
    "$ROOT/whitebox/qstart.sh" "$h" --push 2>&1 | grep -v InspireSkill | tr '\n' ' '
    echo
    echo "[$(ts)] $h: restarted" | tee -a "$ALERT"
  else
    echo "[$(ts)] $h: RESTART FAILED, still unreachable" | tee -a "$ALERT"
  fi
}

while true; do
  for h in $(hosts); do
    queues="jobs"; [ -f "whitebox/queues/$h.2.txt" ] && queues="jobs jobs2"
    out=$(timeout 90 ssh -o ConnectTimeout=40 -o BatchMode=yes "inspire-me-wt-gpu-$h" "
      now=\$(date +%s)
      for q in $queues; do
        run=\$(pgrep -f \"^bash /root/wb/whitebox/qrun.sh \$q\\\$\" >/dev/null && echo up || echo DOWN)
        if [ -f /root/q/\$q.idle ]; then idle=\$(( (now - \$(cat /root/q/\$q.idle)) / 60 )); else idle=-1; fi
        cur=\$(grep \" \\[\$q\\] start \" /root/q/qrun.log 2>/dev/null | tail -1 | awk '{print \$4}')
        rows=\$( [ -n \"\$cur\" ] && wc -l < /root/out/\$cur.jsonl 2>/dev/null || echo -)
        echo \"Q \$q \$run \$idle \${cur:-none} \$rows\"
      done
      echo \"G \$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1)\"
      echo \"P \$(pgrep -fc '[p]ython.*(howskill|e14_decomp)' || true)\"
      echo \"F \$(ls /root/out/*.failed 2>/dev/null | xargs -r -n1 basename | tr '\n' ',')\"
    " </dev/null 2>/dev/null | tr -d '\r')
    if ! echo "$out" | grep -q '^G '; then
      BAD[$h]=$(( ${BAD[$h]:-0} + 1 ))
      echo "[$(ts)] $h: unreachable (${BAD[$h]}/$STRIKES)"
      if [ "${BAD[$h]}" -ge "$STRIKES" ]; then
        st=$(timeout 120 inspire notebook list --workspace "$WS" 2>/dev/null \
             | awk -v n="wt-gpu-$h" '$1==n {print $2}')
        if [ "$st" = STOPPED ] && ! grep -qx "$h" "$STOPPED"; then
          restart "$h"; BAD[$h]=0
        elif [ "$st" = STOPPED ]; then
          BAD[$h]=0          # we stopped it; leave it
        else
          echo "[$(ts)] $h: unreachable but status=${st:-?}" | tee -a "$ALERT"
        fi
      fi
      continue
    fi
    BAD[$h]=0
    util=$(echo "$out" | awk '/^G /{print $2}')
    procs=$(echo "$out" | awk '/^P /{print $2}')
    failed=$(echo "$out" | awk '/^F /{print $2}')
    summary=$(echo "$out" | awk '/^Q /{printf "%s:%s/%s/%s(%s) ", $2, $3, $5, $6, $4}')
    echo "[$(ts)] $h gpu=${util}% py=${procs} $summary${failed:+ FAILED=$failed}"
    [ -n "$failed" ] && echo "[$(ts)] $h: failed jobs $failed" >> "$ALERT"
    if echo "$out" | grep -q '^Q .* DOWN '; then
      echo "[$(ts)] $h: runner down, qstart"
      "$ROOT/whitebox/qstart.sh" "$h" 2>&1 | grep -v InspireSkill | tr '\n' ' '; echo
    fi
    # stop only when every queue has been idle long enough AND nothing runs
    all_idle=1
    for q in $queues; do
      m=$(echo "$out" | awk -v q="$q" '$1=="Q" && $2==q {print $4}')
      [ "${m:--1}" -ge "$IDLE_MIN" ] 2>/dev/null || all_idle=0
    done
    if [ "$all_idle" = 1 ] && [ "${procs:-1}" = 0 ]; then
      echo "[$(ts)] $h: idle ${IDLE_MIN}+ min, gpu=${util}% -> stopping" | tee -a "$ALERT"
      echo "$h" >> "$STOPPED"
      timeout 200 inspire notebook stop "wt-gpu-$h" --workspace "$WS" 2>&1 | grep -v InspireSkill | tail -1
    fi
  done
  sleep "$INTERVAL"
done
