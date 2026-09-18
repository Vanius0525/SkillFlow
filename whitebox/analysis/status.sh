#!/usr/bin/env bash
# One-line status per GPU box. The five boxes hold different repo copies, so the
# path is derived rather than repeated at every call site.
S=/inspire/ssd/project/project-public/czxs253130660
for h in wb wb2 wb3 hsw hsw2 hsw3; do
  case $h in
    wb)   d=$S/agent-harness ;;
    *)    d=$S/agent-harness-$h ;;
  esac
  printf '=== %-5s ' "$h"
  timeout 40 ssh -n -o ConnectTimeout=12 inspire-me-wt-gpu-$h \
    "n=\$(pgrep -fc 'e14_decomp|wb_replay|wb_diffvec|wb_knockout' 2>/dev/null || echo 0); \
     echo \"procs=\$n\"; \
     for f in \$(ls -t $d/*/logs/*.log 2>/dev/null | head -2); do \
       echo \"  \$(basename \$f): \$(tail -1 \$f | cut -c1-110)\"; done" 2>&1 | tail -4
done
