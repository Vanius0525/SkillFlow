"""Where the paper's generated artefacts live.

The LaTeX project is split into sections/, appendix/, tables/ and figures/ so
that it can be dropped into Overleaf as it stands; the generators live here in
tools/ and write into tables/ and figures/.
"""
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PAPER = TOOLS.parent
ROOT = PAPER.parent
TABLES = PAPER / "tables"
FIGURES = PAPER / "figures"
VALUES = PAPER / "values"
AUDIT = PAPER / "audit"
SECTIONS = PAPER / "sections"
APPENDIX = PAPER / "appendix"

# The main text, in the order main.tex inputs it. check_main_data.py greps this
# for prose claims, which used to be one \input-free skillvector.tex.
MAIN_TEXT = [
    SECTIONS / "00-abstract.tex",
    SECTIONS / "01-introduction.tex",
    SECTIONS / "02-related-work.tex",
    SECTIONS / "03-problem-formulation.tex",
    SECTIONS / "04-experiment.tex",
    SECTIONS / "05-conclusion.tex",
]


def main_text() -> str:
    """The main text as one string, whitespace-collapsed."""
    import re
    return re.sub(r"\s+", " ", "\n".join(p.read_text() for p in MAIN_TEXT))
