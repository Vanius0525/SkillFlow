#!/usr/bin/env bash
# Pull the e14 runs -- one file per layer under tA/<tag>/ -- back to
# whitebox/results/fetched/tA/.
#
#   ./whitebox/fetch_ta.sh [host ...]          live /root/out on each box
#   ./whitebox/fetch_ta.sh --mirror [host]     the shared-disk mirror, via one box
#
# autofetch.sh only knows about /root/out/*.jsonl, so these were fetched by hand
# every campaign. Same rule as autofetch: a local file is only ever replaced by
# a strictly longer remote one, because a relaunch truncates the remote file and
# a faithful copy of a stub destroys a finished layer.
#
# --mirror exists because that stub can also reach the shared disk: the old
# mirror.sh copied a file being written as 0 bytes and never refreshed it
# (HANDOFF-TAKEOVER-2026-09-20 §3.3), so $B/wbout holds several copies of the
# same tag and only one of them is whole. It takes the longest copy of each
# file across every instance directory, which is what qrun.sh does on restore.
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
DEST="$ROOT/whitebox/results/fetched/tA"
B=/inspire/ssd/project/project-public/czxs253130660
MIRROR=0
[ "${1:-}" = --mirror ] && { MIRROR=1; shift; }
if [ $# -gt 0 ]; then HOSTS=("$@"); else
  mapfile -t HOSTS < <(ls "$ROOT"/whitebox/queues/*.txt 2>/dev/null |
                       sed 's#.*/##; s#\.2\.txt$##; s#\.txt$##' | sort -u)
fi
[ "$MIRROR" = 1 ] && HOSTS=("${HOSTS[0]}")

# "<relative path> <lines> <absolute path on the box>", one line per file
inventory_live='cd /root/out/tA 2>/dev/null && find . -name "*.json*" -printf "%P\n" |
  while read -r f; do echo "$f $(wc -l < "$f" | tr -d " ") /root/out/tA/$f"; done'
inventory_mirror='for p in '"$B"'/wbout/*/tA/*/*.json*; do
    [ -e "$p" ] || continue
    rel=${p#*/tA/}; echo "$rel $(wc -l < "$p" | tr -d " ") $p"
  done | sort -k1,1 -k2,2nr | awk "!seen[\$1]++"'

for h in "${HOSTS[@]}"; do
  H="inspire-me-wt-gpu-$h"
  timeout 25 ssh -o ConnectTimeout=12 -o BatchMode=yes "$H" true 2>/dev/null || continue
  inv=$(timeout 900 ssh "$H" "$([ "$MIRROR" = 1 ] && echo "$inventory_mirror" || echo "$inventory_live")" \
        2>/dev/null | tr -d '\r')
  [ -n "$inv" ] || continue
  while read -r rel rows path; do
    [ -n "$rel" ] && [ -n "$path" ] || continue
    loc="$DEST/$rel"
    l=0; [ -f "$loc" ] && l=$(wc -l < "$loc")
    [ "${rows:-0}" -le "$l" ] 2>/dev/null && continue
    mkdir -p "$(dirname "$loc")"
    tmp="$loc.part"
    # </dev/null or ssh eats the rest of the inventory off this loop's stdin
    if timeout 180 ssh "$H" "head -n $rows '$path'" </dev/null > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
      mv "$tmp" "$loc"
      echo "[$(date +%m-%d_%H:%M)] $h tA/$rel $l -> $rows rows"
    else
      rm -f "$tmp"
    fi
  done <<< "$inv"
done
