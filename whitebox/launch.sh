#!/usr/bin/env bash
# Start ONE whitebox job on one box, detached, writing /root/out/<tag>.jsonl.
#
#   ./whitebox/launch.sh <host> <tag> <module> "<args>"
#   ./whitebox/launch.sh wb3 mis-depth wb_spanvec "--model $B/models/Mistral-7B-Instruct-v0.3 ..."
#
# Same inner script as relaunch.sh, factored out so new jobs do not need a new
# copy of it. Refuses to reuse a tag that already has rows on the box: a relaunch
# under an old tag truncated five finished runs on 2026-09-13 (HANDOFF §44.3).
set -uo pipefail
h="${1:?host}"; tag="${2:?tag}"; mod="${3:?module}"; args="${4:?args}"
B=/inspire/ssd/project/project-public/czxs253130660
H="inspire-me-wt-gpu-$h"

# RESUME=1: continue an existing tag (the module must be given --resume); the
# log is appended to instead of truncated.
if [ "${RESUME:-0}" != 1 ] && ssh "$H" "test -s /root/out/$tag.jsonl"; then
  echo "refusing: /root/out/$tag.jsonl already has rows on $h; pick a new tag" >&2
  exit 1
fi
tmp=$(mktemp)
cat > "$tmp" <<INNER
set -e
cd /root/wb/howskill
mkdir -p /root/out
cp $B/agent-harness-hsw/howskill/data/cells.json data/cells.json
exec $B/venvs/whitebox/bin/python -u -m howskill.$mod $args --out /root/out/$tag.jsonl
INNER
scp -q "$tmp" "$H:/root/_launch_$tag.sh" && rm -f "$tmp" || { echo "scp failed $h" >&2; exit 1; }
redir='>'; [ "${RESUME:-0}" = 1 ] && redir='>>'
ssh "$H" "setsid nohup bash /root/_launch_$tag.sh </dev/null $redir /root/out/$tag.log 2>&1 & disown" \
  && echo "launched $tag on $h"
