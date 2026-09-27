#!/usr/bin/env bash
# Build the Overleaf upload: the LaTeX project and nothing else.
# No Python, no PNG twins of the figures, no audit logs, no legacy sources.
# (zip(1) is not in this WSL image, so the archive is written by Python.)
set -euo pipefail
PAPER="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$(dirname "$0")/make_overleaf_zip.py" "$PAPER"
