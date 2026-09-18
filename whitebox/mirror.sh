#!/usr/bin/env bash
# Runs ON a GPU box: mirror /root/out to the shared fileset, forever.
#
# WHY. /root is overlay and is wiped when the platform reclaims the instance --
# that is how six partly-finished runs were lost on 2026-09-13. autofetch.sh
# pulls results to the laptop every 15 minutes, but only while the laptop is
# awake and the tunnel is up, and a run can be watched for many hours. The
# shared fileset survives a rebuild, and a box left idle after its job finishes
# is then harmless: the rows are already on durable storage.
#
# The hdd fileset is at its ~370 MB quota; the ssd one is not (525 G free,
# 60 MB probe wrote in full on 2026-09-16), so it is the one used here.
#
#   setsid nohup bash /root/mirror.sh >/dev/null 2>&1 &
set -u
B=/inspire/ssd/project/project-public/czxs253130660
H=$(hostname)
DEST="$B/wbout/$H"
mkdir -p "$DEST"
while true; do
  # *.done: qrun.sh's completion markers, so a rebuilt box does not redo a
  # finished job; tA/: e14_decomp's per-layer directories
  [ -d /root/out/tA ] && cp -ru /root/out/tA "$DEST/" 2>/dev/null
  for f in /root/out/*.jsonl /root/out/*.log /root/out/*.done; do
    [ -e "$f" ] || continue
    b=$(basename "$f")
    # only ever grow the mirror: a relaunch that truncates the local file must
    # not take the finished copy down with it (the autofetch.sh lesson)
    if [ -f "$DEST/$b" ] && [ "$(stat -c %s "$f")" -lt "$(stat -c %s "$DEST/$b")" ]; then
      mv "$DEST/$b" "$DEST/$b.superseded-$(date +%m%d_%H%M)" 2>/dev/null
    fi
    cp -f "$f" "$DEST/.$b.part" 2>/dev/null && mv -f "$DEST/.$b.part" "$DEST/$b" 2>/dev/null
  done
  date +%s > "$DEST/.heartbeat"
  sleep 180
done
