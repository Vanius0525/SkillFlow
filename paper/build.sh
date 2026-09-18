#!/usr/bin/env bash
# Compile with the Windows MiKTeX visible from WSL. There is no TeX in this
# WSL image and installing one is a gigabyte; pdflatex.exe reads /mnt/c paths
# fine, so the source lives in the repo and only the build staging is on C:.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE="/mnt/c/Users/12970/Desktop/ICLR2027/build-skillvector"
PDFLATEX="/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe"
BIBTEX="/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64/bibtex.exe"
JOB="${1:-skillvector}"

mkdir -p "$STAGE"
# generated tables and figures are copied fresh: a stale copy left in the staging
# directory once let \input{tab-battery} compile here while the file did not
# exist in paper/, so the PDF showed an old table and Overleaf would have failed
rm -f "$STAGE"/tab-*.tex "$STAGE"/fig-*.pdf
cp "$HERE"/*.tex "$HERE"/*.sty "$HERE"/*.bst "$HERE"/*.bib "$STAGE"/ 2>/dev/null || true
cp "$HERE"/fig-*.pdf "$STAGE"/ 2>/dev/null || true
cd "$STAGE"
"$PDFLATEX" -interaction=nonstopmode -halt-on-error "$JOB.tex" > /dev/null 2>&1 || true
"$BIBTEX" "$JOB" > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
# a second bibtex pass: the bibliography now sits before the appendix, and
# citations that first appear after it are only in the .aux of the run that
# follows, so one cycle is not enough
"$BIBTEX" "$JOB" > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true

# A slice edit (s[:i] + s[j:]) once deleted an entire section, its figure and
# its table without changing the page count enough to notice, and the build
# stayed clean because LaTeX does not miss what is not there. So the structure
# is printed every time: a section that vanishes is visible in the diff of two
# consecutive builds even when nothing errors.
echo "--- structure ---"
grep -nE '^\\(section|subsection)\{' "$HERE/$JOB.tex" \
  | sed 's/:\\section{/  /; s/:\\subsection{/    /; s/}$//' \
  | sed 's/^/  /'
echo "  paragraphs: $(grep -c '\\paragraph{' "$HERE/$JOB.tex")"
echo "  floats: $(grep -c '\\begin{figure}' "$HERE/$JOB.tex") figures, "\
     "$(grep -c '\\begin{table}' "$HERE/$JOB.tex") tables"
dups=$(grep -oE '\\label\{[^}]+\}' "$HERE/$JOB.tex" | sort | uniq -d)
[ -n "$dups" ] && echo "  DUPLICATE LABELS: $dups"
echo "--- placeholders that must not survive submission ---"
grep -c "PEND" "$JOB.tex" | sed 's/^/  \\PEND markers: /'
grep -c "author *= *{Anonymous}" *.bib 2>/dev/null | sed 's/^/  bib entries with unknown authors: /' || true
echo "--- duplicate labels / stray floats ---"
python3 "$HERE/checks.py" "$HERE/$JOB.tex"
echo "--- errors ---"
grep -E "^! |^l\.[0-9]+" "$JOB.log" | head -20 || echo "none"
echo "--- undefined references / citations ---"
# LaTeX does not stop on these; it prints "??" into the PDF. Two labels lost in a
# dedup edit rendered as "Eq. ??" on page 4 while this script reported clean.
undef=$(grep -E "LaTeX Warning: (Reference|Citation) .* undefined" "$JOB.log" | sort -u || true)
if [ -n "$undef" ]; then echo "$undef" | sed 's/^/  /'; else echo "  0"; fi
echo "--- overfull ---"
grep -c "Overfull" "$JOB.log" || true
echo "--- main text pages (ICLR limit 9) ---"
python3 -c "
import re,sys
try: a=open(r'$STAGE/skillvector.aux',encoding='utf-8',errors='ignore').read()
except OSError: sys.exit()
m=re.search(r'newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}', a)
print(m.group(1) if m else '?')"
echo "--- pages ---"
grep -oE "\([0-9]+ pages" "$JOB.log" | tail -1 || true
cp "$JOB.pdf" "$HERE/$JOB.pdf" 2>/dev/null && echo "pdf -> $HERE/$JOB.pdf"
