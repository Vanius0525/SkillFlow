#!/usr/bin/env bash
# Launch one wb_spanvec job on a box, detached, writing to /root/out.
#
#   ./runjob.sh <host-suffix> <tag> <args...>
#
# Inline ssh quoting ate a $B once and the model path reached HuggingFace as a
# literal "$B/models/Qwen3-8B", which it tried to resolve as a repo id. Every
# launch goes through a file now: the script is written locally, copied, and
# run, so the only quoting that matters is this file's.
set -euo pipefail
H="inspire-me-wt-gpu-${1:?host}"; TAG="${2:?tag}"; shift 2
B=/inspire/ssd/project/project-public/czxs253130660
cat > /tmp/_job.sh <<EOF
set -e
B=$B
cd /root/wb/howskill
mkdir -p /root/out
cp \$B/agent-harness-hsw/howskill/data/cells.json data/cells.json
exec \$B/venvs/whitebox/bin/python -u -m howskill.wb_spanvec \\
  --model \$B/models/Qwen3-8B --max-new 900 $* \\
  --out /root/out/$TAG.jsonl
EOF
scp -q /tmp/_job.sh "$H:/root/_job_$TAG.sh"
ssh "$H" "setsid nohup bash /root/_job_$TAG.sh </dev/null > /root/out/$TAG.log 2>&1 & disown; echo launched $TAG on $1"
