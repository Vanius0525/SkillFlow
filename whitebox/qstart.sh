#!/usr/bin/env bash
# Install a box's queue(s) and make sure one qrun.sh per queue is running.
#
#   ./whitebox/qstart.sh <host> [--push]
#
# Queues live in whitebox/queues/<host>.txt (runner `jobs`) and, optionally,
# whitebox/queues/<host>.2.txt (runner `jobs2`). Re-running this after editing a
# queue file is how a box gets more work: the runner re-reads its queue after
# every job, so nothing needs restarting. --push also ships the code first.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
h="${1:?host}"; H="inspire-me-wt-gpu-$h"
if [ "${2:-}" = --push ]; then
  "$HERE/push_local.sh" "$H" howskill whitebox >/dev/null || { echo "$h push failed"; exit 1; }
  "$HERE/mirror_start.sh" "$h"
fi
ssh "$H" "mkdir -p /root/q" </dev/null || { echo "$h unreachable"; exit 1; }
for pair in "jobs:$HERE/queues/$h.txt" "jobs2:$HERE/queues/$h.2.txt"; do
  name=${pair%%:*}; f=${pair#*:}
  [ -f "$f" ] || continue
  scp -q "$f" "$H:/root/q/$name.txt" || { echo "$h scp $name failed"; continue; }
  # anchored: an unanchored pattern matches this very ssh command line
  st=$(ssh "$H" "pgrep -f '^bash /root/wb/whitebox/qrun.sh $name\$' >/dev/null && echo running || \
        { (setsid nohup bash /root/wb/whitebox/qrun.sh $name >/root/q/$name.out 2>&1 </dev/null &); sleep 2; \
          pgrep -f '^bash /root/wb/whitebox/qrun.sh $name\$' >/dev/null && echo started || echo FAILED; }" </dev/null | tr -d '\r')
  echo "$h $name: $st"
done
