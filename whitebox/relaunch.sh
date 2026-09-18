#!/usr/bin/env bash
# Bring the six boxes back to work after a platform reclaim.
#
# Pushes code (/root/wb is gone with the old container) and starts one job per
# box. Order is by what the paper is waiting on: the recomputed knockout curve
# fills a \PEND, then the two scale-ups, then the post-fix replications.
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
B=/inspire/ssd/project/project-public/czxs253130660
cd "$ROOT"

launch () {  # host tag module args...
  local h="$1" tag="$2" mod="$3"; shift 3
  cat > /tmp/_rl_$tag.sh <<INNER
set -e
cd /root/wb/howskill
mkdir -p /root/out
cp $B/agent-harness-hsw/howskill/data/cells.json data/cells.json
exec $B/venvs/whitebox/bin/python -u -m howskill.$mod $* --out /root/out/$tag.jsonl
INNER
  scp -q /tmp/_rl_$tag.sh "inspire-me-wt-gpu-$h:/root/_rl_$tag.sh" || { echo "scp failed $h"; return 1; }
  ssh "inspire-me-wt-gpu-$h" "setsid nohup bash /root/_rl_$tag.sh </dev/null > /root/out/$tag.log 2>&1 & disown" \
    && echo "launched $tag on $h"
}

for h in hsw hsw2 hsw3 wb wb2 wb3; do
  timeout 25 ssh -o ConnectTimeout=12 -o BatchMode=yes "inspire-me-wt-gpu-$h" true 2>/dev/null \
    || { echo "$h unreachable, skipping"; continue; }
  ./whitebox/push_local.sh "inspire-me-wt-gpu-$h" howskill >/dev/null 2>&1 && echo "pushed $h"
done

launch hsw  ko-8b-fast     wb_knockout "--model $B/models/Qwen3-8B --sweep layers --layer-stride 4 --cells-keep R --per-calc 2 --max-calcs 20 --max-new 900"
launch hsw2 big40-depth    wb_spanvec  "--model $B/models/Qwen3-8B --max-new 900 --mode decode --layers 0,4,8,12,14,15,16,20 --filler fixedskill --baselines --per-calc 3 --max-calcs 40 --arms real"
launch wb2  rank40-l8      wb_spanvec  "--model $B/models/Qwen3-8B --max-new 900 --mode decode --layers 8 --filler fixedskill --baselines --per-calc 4 --max-calcs 40 --arms real,rank4,rank16,rank32,rank64,rank128,rank16lo,rank64lo"
launch wb   fixmask-big40  wb_spanvec  "--model $B/models/Qwen3-8B --max-new 900 --mode decode --layers 8 --filler fixedskill --baselines --per-calc 4 --max-calcs 40 --arms real,drand,dshuf,dfar,realm,a0.5"
launch wb3  fixmask-rank   wb_spanvec  "--model $B/models/Qwen3-8B --max-new 900 --mode decode --layers 8 --filler fixedskill --baselines --per-calc 4 --max-calcs 10 --arms real,rank16,rank32,rank64,rank128,rank64lo"
launch hsw3 fixmask-window wb_spanpatch "--model $B/models/Qwen3-8B --matched --span skill --max-new 900 --per-calc 4 --max-calcs 20 --layers 16 --window 12:15 --window 16:35 --window 14:19 --window 8:11"
