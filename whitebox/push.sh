#!/usr/bin/env bash
# Ship the local whitebox/ working copy to a GPU box. tar over ssh, because the
# image has no rsync after a restart and apt is the slower fix.
#   ./push.sh inspire-me-wt-gpu-wb [dest-repo-dir]
set -euo pipefail
HOST="${1:?host}"
DEST="${2:-/inspire/ssd/project/project-public/czxs253130660/agent-harness}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
tar czf - --exclude='__pycache__' --exclude='results' --exclude='logs' . \
  | ssh "$HOST" "mkdir -p $DEST/whitebox && tar xzf - -C $DEST/whitebox && echo pushed to $DEST/whitebox"
