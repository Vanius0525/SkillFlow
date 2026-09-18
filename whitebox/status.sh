#!/usr/bin/env bash
# One line per box: reachable? GPU util, running job tag(s), rows of recent outputs,
# and any Traceback/OOM in logs touched in the last 3 hours.
#   ./whitebox/status.sh [host ...]    (default: all ten)
HOSTS=("$@"); [ ${#HOSTS[@]} -eq 0 ] && HOSTS=(hsw hsw2 hsw3 wb wb2 wb3 sra1 sra2 sra3 sra4)
for h in "${HOSTS[@]}"; do
  out=$(timeout 45 ssh -o ConnectTimeout=15 -o BatchMode=yes "inspire-me-wt-gpu-$h" '
    u=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null)
    run=$(ps -eo args | grep -oE "[o]ut/[A-Za-z0-9._-]+\.jsonl" | sed "s#out/##; s#\.jsonl##" | sort -u | tr "\n" ",")
    rows=$(find /root/out -name "*.jsonl" -mmin -240 -printf "%f\n" 2>/dev/null | while read f; do printf "%s=%s " "${f%.jsonl}" "$(wc -l < /root/out/$f)"; done)
    err=$(find /root/out -name "*.log" -mmin -180 -exec grep -lE "Traceback|OutOfMemoryError" {} + 2>/dev/null | xargs -r -n1 basename | tr "\n" ",")
    echo "gpu=${u}% run=[${run%,}] rows: ${rows} ${err:+ERR:[$err]}"' 2>/dev/null | grep -v InspireSkill)
  printf "%-5s %s\n" "$h" "${out:-UNREACHABLE}"
done
