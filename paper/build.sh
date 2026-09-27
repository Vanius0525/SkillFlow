#!/usr/bin/env bash
# Compile with the Windows MiKTeX visible from WSL. There is no TeX in this WSL
# image; pdflatex.exe reads /mnt/c paths fine, so the source lives in the repo
# and only the build staging is on C:.
#
#   ./build.sh            -- full technical report (extended appendix)
#   ./build.sh submission -- WWW 2027 build, extended appendix left out
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE="/mnt/c/Users/12970/Desktop/WWW2027/build-skillvector"
BIN="/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64"
PDFLATEX="$BIN/pdflatex.exe"
BIBTEX="$BIN/bibtex.exe"
JOB=main
MODE="${1:-full}"

# The staging tree is rebuilt from scratch every time. A stale copy left behind
# once let \input{tables/tab-battery} compile here while the file did not exist
# in the repository, so the PDF showed an old table and Overleaf would have failed.
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp "$HERE"/main.tex "$HERE"/*.bib "$STAGE"/
cp -r "$HERE"/sections "$HERE"/appendix "$HERE"/tables "$STAGE"/
mkdir -p "$STAGE/figures" && cp "$HERE"/figures/*.pdf "$STAGE/figures/"

if [ "$MODE" = submission ]; then
  sed -i 's/^\\extendedappendixtrue$/\\extendedappendixfalse/' "$STAGE/main.tex"
fi

cd "$STAGE"
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
"$BIBTEX"   "$JOB"                    > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
# a second bibtex pass: the bibliography sits before the appendix, so citations
# that first appear after it are only in the .aux of the run that follows
"$BIBTEX"   "$JOB"                    > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true

# A slice edit once deleted an entire section, its figure and its table without
# changing the page count enough to notice, and the build stayed clean because
# LaTeX does not miss what is not there. So the structure is printed every time.
echo "--- structure ($MODE) ---"
grep -hnE '^\\(section|subsection)\{' "$HERE"/sections/*.tex "$HERE"/appendix/*.tex \
  | sed 's/^[0-9]*:\\section{/  /; s/^[0-9]*:\\subsection{/    /; s/}$//' | sed 's/^/  /'
echo "  paragraphs: $(cat "$HERE"/sections/*.tex "$HERE"/appendix/*.tex | grep -c '\\paragraph{')"
echo "  floats: $(cat "$HERE"/sections/*.tex "$HERE"/appendix/*.tex | grep -c '\\begin{figure') figures,"\
     "$(cat "$HERE"/sections/*.tex "$HERE"/appendix/*.tex | grep -c '\\begin{table') tables"
dups=$(cat "$HERE"/sections/*.tex "$HERE"/appendix/*.tex | grep -oE '\\label\{[^}]+\}' | sort | uniq -d)
[ -n "$dups" ] && echo "  DUPLICATE LABELS: $dups"
echo "--- placeholders that must not survive submission ---"
echo "  \\PEND markers: $(cat "$HERE"/sections/*.tex "$HERE"/appendix/*.tex | grep -c 'PEND' || true)"
echo "--- errors ---"
grep -E "^! |^l\.[0-9]+" "$JOB.log" | head -20 || echo "  none"
echo "--- undefined references / citations ---"
undef=$(grep -E "LaTeX Warning: (Reference|Citation) .* undefined" "$JOB.log" | sort -u || true)
if [ -n "$undef" ]; then echo "$undef" | sed 's/^/  /'; else echo "  0"; fi
# hbox and vbox are counted apart: an overfull hbox runs into the gutter and
# has to be fixed, an overfull vbox of a point or two is a page-break artefact.
echo "--- overfull ---"
echo "  hbox: $(grep -c 'Overfull \\hbox' "$JOB.log" || true)   vbox: $(grep -c 'Overfull \\vbox' "$JOB.log" || true)"
echo "--- main text pages (WWW limit 8) ---"
python3 -c "
import re,sys
try: a=open(r'$STAGE/$JOB.aux',encoding='utf-8',errors='ignore').read()
except OSError: sys.exit()
m=re.search(r'newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}', a)
print('  '+(m.group(1) if m else '?'))"
echo "--- total pages (WWW limit 12) ---"
grep -oE "\([0-9]+ pages" "$JOB.log" | tail -1 | sed 's/(/  /' || true
# the two builds keep separate PDFs so both are on disk at once
if [ "$MODE" = submission ]; then DEST=skillvector-www2027.pdf; else DEST=skillvector.pdf; fi
cp "$JOB.pdf" "$HERE/$DEST" 2>/dev/null && echo "pdf -> $HERE/$DEST"
