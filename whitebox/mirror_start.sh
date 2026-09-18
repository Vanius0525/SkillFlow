#!/usr/bin/env bash
# Install and (re)start whitebox/mirror.sh on one box, or on all of them.
#   ./whitebox/mirror_start.sh hsw hsw2 ...      # named boxes
#   ./whitebox/mirror_start.sh                   # every box in HOSTS
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
HOSTS=("$@")
[ ${#HOSTS[@]} -eq 0 ] && HOSTS=(hsw hsw2 hsw3 wb wb2 wb3 wb4 sra1 sra2 sra3 sra4)
for h in "${HOSTS[@]}"; do
  H="inspire-me-wt-gpu-$h"
  timeout 20 ssh -o ConnectTimeout=12 -o BatchMode=yes "$H" true 2>/dev/null || {
    echo "$h unreachable"; continue; }
  scp -q "$HERE/mirror.sh" "$H:/root/mirror.sh" || { echo "$h scp failed"; continue; }
  # one call, and the check inside it: a second ssh races the detach, and an
  # `exit 0` straight after the `&` kills the subshell before setsid detaches
  ok=$(ssh "$H" "pkill -f '^bash /root/mirror.sh' >/dev/null 2>&1; \
        (setsid nohup bash /root/mirror.sh >/root/mirror.log 2>&1 &); sleep 2; \
        pgrep -f '^bash /root/mirror.sh' >/dev/null && echo up || echo FAILED" \
       </dev/null 2>/dev/null | tr -d ' \r')
  echo "$h mirror ${ok:-unreachable}"
done
