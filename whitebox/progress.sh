#!/usr/bin/env bash
# Progress of the 2026-09-20 fill-in campaign, one line per job.
#
#   ./whitebox/progress.sh
#
# The four gaps of HANDOFF-TAKEOVER-2026-09-20 §5 (items 2, 3, 5, 6). Each job
# is either a wb_spanvec run, whose progress is rows in <tag>.jsonl against the
# item count of the row it extends, or an e14 run, whose progress is complete
# (358-row) layer files against the layers it was asked for.
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
cd "$ROOT"

# tag -> expected, kind, host
JOBS="
tqa-rank-d1     99  rows sra2
tqa-rank-d2     99  rows sra2
tqa06-rank-d1  132  rows hsw
tqa06-rank-d2  132  rows hsw
tqamis-rank-d1 115  rows wb
tqamis-rank-d2 115  rows wb
mis-rank-hi    221  rows sra1
d17-shuffled-b  14  e14  hsw
d17-corrupted-b 14  e14  sra1
tA-num-k32      36  e14  sra4
tA-num-k48      36  e14  sra4
tA-num-k61      36  e14  wb2
"

echo "=== boxes ==="
for h in $(ls whitebox/queues/*.txt | sed 's#.*/##; s#\.2\.txt$##; s#\.txt$##' | sort -u); do
  out=$(timeout 45 ssh -o ConnectTimeout=15 -o BatchMode=yes "inspire-me-wt-gpu-$h" '
    u=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
    cur=$(grep " start " /root/q/qrun.log 2>/dev/null | tail -2 | awk "{print \$4}" | tr "\n" ",")
    dn=$(ls /root/out/*.done 2>/dev/null | xargs -r -n1 basename | sed "s/\.done//" | tr "\n" ",")
    fa=$(ls /root/out/*.failed 2>/dev/null | xargs -r -n1 basename | tr "\n" ",")
    err=$(find /root/out -name "*.log" -mmin -120 -exec grep -lE "Traceback|OutOfMemory" {} + 2>/dev/null |
          xargs -r -n1 basename | tr "\n" ",")
    echo "gpu=${u}% running=[${cur%,}] done=[${dn%,}]${fa:+ FAILED=[${fa%,}]}${err:+ ERR=[${err%,}]}"' \
    </dev/null 2>/dev/null | grep -v InspireSkill)
  printf "%-5s %s\n" "$h" "${out:-UNREACHABLE}"
done

echo
echo "=== jobs (local copies; autofetch pulls every 15 min) ==="
while read -r tag want kind host; do
  [ -n "${tag:-}" ] || continue
  if [ "$kind" = rows ]; then
    f=$(ls -S howskill/results/p8-wb/fetched/by-host/*/"$tag".jsonl 2>/dev/null | head -1)
    have=0; [ -n "$f" ] && have=$(wc -l < "$f")
  else
    d="whitebox/results/fetched/tA/$tag"
    have=0
    [ -d "$d" ] && have=$(for g in "$d"/layer_*.jsonl; do [ -f "$g" ] && [ "$(wc -l < "$g")" -eq 358 ] && echo x; done | wc -l)
  fi
  pct=$(( want > 0 ? have * 100 / want : 0 ))
  printf "%-16s %-5s %4s/%-4s %3s%%  %s\n" "$tag" "$host" "$have" "$want" "$pct" \
    "$([ "$have" -ge "$want" ] && echo COMPLETE || echo ...)"
done <<< "$JOBS"
