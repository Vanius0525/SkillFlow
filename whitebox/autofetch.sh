#!/usr/bin/env bash
# Pull every box's /root/out/*.jsonl every few minutes, forever.
#
# The platform stopped all six instances at once on 2026-09-13 and /root is
# overlay, so six partly-finished runs were lost -- including one that had
# finished. dispatch.sh only fetches when a box goes idle, which never happened
# because they all died at the same time. This fetches on a clock instead.
#
#   nohup ./whitebox/autofetch.sh > logs/autofetch.log 2>&1 &
set -uo pipefail
ROOT=/home/vanius/proj/agent-harness
FETCH="$ROOT/howskill/results/p8-wb/fetched/by-host"
# Local files a rerun would replace are moved here first. Outside by-host on
# purpose: audit.py globs by-host/*/, so nothing in here is ever read by it.
SUPER="$ROOT/howskill/results/p8-wb/fetched/superseded"
HOSTS=(hsw hsw2 hsw3 wb wb2 wb3 wb4 sra1 sra2 sra3 sra4)
INTERVAL="${1:-900}"
while true; do
  for h in "${HOSTS[@]}"; do
    mkdir -p "$FETCH/$h"
    timeout 25 ssh -o ConnectTimeout=12 -o BatchMode=yes "inspire-me-wt-gpu-$h" true 2>/dev/null || continue
    for f in $(timeout 40 ssh "inspire-me-wt-gpu-$h" 'ls /root/out/*.jsonl 2>/dev/null' 2>/dev/null); do
      b=$(basename "$f")
      r=$(timeout 25 ssh "inspire-me-wt-gpu-$h" "wc -l < $f" 2>/dev/null | tr -d ' \r')
      l=0; [ -f "$FETCH/$h/$b" ] && l=$(wc -l < "$FETCH/$h/$b")
      # ONLY ever grow a local file. Syncing on "counts differ" cost five
      # completed runs: a relaunch truncates the remote file, and the next
      # pass faithfully copied the 3-row stub over the 160-row result.
      [ "${r:-0}" -lt "$l" ] 2>/dev/null && continue
      # equal counts: fetch only if the content differs (a same-length rerun --
      # big40-depth reran to exactly its old 120 rows and was never fetched)
      [ "${r:-0}" -eq 0 ] 2>/dev/null && continue
      if [ "${r:-0}" -eq "$l" ] 2>/dev/null; then
        rh=$(timeout 60 ssh "inspire-me-wt-gpu-$h" "sha256sum < $f" 2>/dev/null | cut -c1-64)
        [ -n "$rh" ] || continue
        [ "$rh" = "$(sha256sum < "$FETCH/$h/$b" | cut -c1-64)" ] && continue
      fi
      # Growing is not enough either: a rerun under the same tag with different
      # code (big40-depth, pre- vs post-mask-fix, differs on 4 of its first 7
      # rows) passes the row count once it catches up. Keep the old file unless
      # it is a byte prefix of the remote one.
      if [ "$l" -gt 0 ]; then
        rh=$(timeout 60 ssh "inspire-me-wt-gpu-$h" "head -n $l $f | sha256sum" 2>/dev/null | cut -c1-64)
        [ -n "$rh" ] || continue
        lh=$(sha256sum < "$FETCH/$h/$b" | cut -c1-64)
        if [ "$rh" != "$lh" ]; then
          mkdir -p "$SUPER/$h"
          keep="$SUPER/$h/${b%.jsonl}.superseded-$(date +%m%d_%H%M).jsonl"
          cp -p "$FETCH/$h/$b" "$keep"
          echo "[$(date +%m-%d_%H:%M)] $h/$b diverged from remote; old $l rows kept as ${keep#$ROOT/}"
        fi
      fi
      tmp="$FETCH/$h/.$b.part"
      # head -n r, not cat: a line being written right now is not taken half-way
      if timeout 180 ssh "inspire-me-wt-gpu-$h" "head -n $r $f" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
        mv "$tmp" "$FETCH/$h/$b"
        echo "[$(date +%m-%d_%H:%M)] $h/$b $l -> $r rows"
      else
        rm -f "$tmp"
      fi
    done
  done
  sleep "$INTERVAL"
done
