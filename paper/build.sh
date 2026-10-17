#!/usr/bin/env bash
# Compile with the Windows MiKTeX visible from WSL. There is no TeX in this WSL
# image; pdflatex.exe reads /mnt/c paths fine, so the source lives in the repo
# and only the build staging is on C:.
#
#   ./build.sh            -- WWW 2027 submission only
#   ./build.sh submission -- same submission build
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE_ROOT="/mnt/c/Users/12970/Desktop/WWW2027"
BIN="/mnt/c/Users/12970/AppData/Local/Programs/MiKTeX/miktex/bin/x64"
PDFLATEX="$BIN/pdflatex.exe"
BIBTEX="$BIN/bibtex.exe"
JOB=main
MODE="${1:-submission}"
if [ "$MODE" != submission ]; then echo "Only the submission build is maintained." >&2; exit 2; fi

# A new staging directory prevents stale inputs without deleting previous
# builds or their diagnostic logs.
mkdir -p "$STAGE_ROOT"
STAGE="$(mktemp -d "$STAGE_ROOT/build-skillvector.XXXXXXXX")"
echo "Build stage: $STAGE"
python3 - "$HERE" "$STAGE" <<'COPYPROJECT'
from pathlib import Path
import sys,shutil
paper,stage=map(Path,sys.argv[1:])
sys.path.insert(0,str(paper/'tools'))
from make_overleaf_zip import project_members
for path in project_members(paper):
    target=stage/path.relative_to(paper)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,target)
COPYPROJECT

cd "$STAGE"
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
"$BIBTEX"   "$JOB"                    > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
# a second bibtex pass: the bibliography sits before the appendix, so citations
# that first appear after it are only in the .aux of the run that follows
"$BIBTEX"   "$JOB"                    > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true
"$PDFLATEX" -interaction=nonstopmode "$JOB.tex" > /dev/null 2>&1 || true

echo "--- active submission structure ---"
python3 - "$STAGE" <<'CHECKSTRUCTURE'
from pathlib import Path
import re,sys,collections
stage=Path(sys.argv[1]);text='\n'.join(p.read_text() for p in stage.rglob('*.tex'))
for kind,title in re.findall(r'\\(section|subsection)\{([^}]+)\}',text):
    print(('    ' if kind=='subsection' else '  ')+title)
labels=collections.Counter(re.findall(r'\\label\{([^}]+)\}',text))
assert not [k for k,n in labels.items() if n>1], 'Duplicate labels'
print('  figures:',len(re.findall(r'\\begin\{(?:figure\*?|teaserfigure)\}',text)))
print('  tables:',len(re.findall(r'\\begin\{table\*?\}',text)))
assert not re.search(r'\\PEND\{',text) and '[Draft:' not in text, 'Pending results'
CHECKSTRUCTURE
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
# Only the submission PDF is generated.
DEST=skillvector-www2027.pdf
cp "$JOB.pdf" "$HERE/$DEST" 2>/dev/null && echo "pdf -> $HERE/$DEST"
