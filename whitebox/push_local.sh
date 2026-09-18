#!/usr/bin/env bash
# Ship code to the container's OWN disk instead of the shared fileset.
#
# Both shared filesets are at their quota: a 50 MB dd writes 0 bytes, and a
# truncated tar extraction is how a half-written e14_decomp.py appeared on one
# box (SyntaxError at the line the transfer stopped on). /root is overlay with
# 765 GB free. It is lost when the platform reclaims the instance, so anything
# written there has to be copied off promptly -- which is why `fetch_local.sh`
# exists next to this.
#
#   ./push_local.sh inspire-me-wt-gpu-hsw3 [subdir-of-repo ...]
set -euo pipefail
HOST="${1:?host}"; shift
ROOT="/home/vanius/proj/agent-harness"
DIRS=("$@")
[ ${#DIRS[@]} -eq 0 ] && DIRS=(whitebox howskill)
cd "$ROOT"
tar czf - --exclude='__pycache__' --exclude='results' --exclude='logs' \
    --exclude='*.pdf' "${DIRS[@]}" \
  | ssh "$HOST" "mkdir -p /root/wb /root/out && tar xzf - -C /root/wb && \
      echo 'pushed to /root/wb:' && ls /root/wb"
