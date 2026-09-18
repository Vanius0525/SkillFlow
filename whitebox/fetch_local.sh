#!/usr/bin/env bash
# Pull /root/out off a box before it is reclaimed.
#   ./fetch_local.sh inspire-me-wt-gpu-hsw3 <local-dir>
set -euo pipefail
HOST="${1:?host}"; DEST="${2:?dest}"
mkdir -p "$DEST"
ssh "$HOST" "cd /root/out 2>/dev/null && tar czf - . || true" | tar xzf - -C "$DEST"
echo "fetched $HOST:/root/out -> $DEST"
ls -R "$DEST" | head -20
