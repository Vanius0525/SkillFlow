#!/usr/bin/env python3
"""Write overleaf-skillvector.zip: the LaTeX project and nothing else."""
import sys, zipfile, pathlib

paper = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                     else pathlib.Path(__file__).resolve().parents[1])
out = paper / "overleaf-skillvector.zip"
members = [paper / n for n in ("main.tex", "README.md", "skillvector.bib")]
for d in ("sections", "appendix", "tables"):
    members += sorted((paper / d).glob("*.tex"))
members += sorted((paper / "figures").glob("*.pdf"))

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for m in members:
        z.write(m, m.relative_to(paper).as_posix())
print(f"-> {out}  ({len(members)} files, {out.stat().st_size/1e6:.2f} MB)")
