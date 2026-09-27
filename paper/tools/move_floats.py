#!/usr/bin/env python3
"""Move named float environments into the appendix.

    python move_floats.py fig:decomp fig:windows tab:windows2 ...

The main text has to fit nine pages, and floats are what fills them: eight
figures and eleven tables is already more than nine pages of float area before a
word of text. Doing this by hand invites a half-moved environment that still
compiles because LaTeX is forgiving about stray \\end{table}, so it is a script:
it finds the \\begin{...}...\\end{...} that contains the given \\label, cuts it,
and appends it under a heading in the appendix.
"""
import pathlib
import re
import sys


def find_float(s: str, label: str):
    m = re.search(r"\\label\{" + re.escape(label) + r"\}", s)
    if not m:
        return None
    # walk back to the nearest \begin{figure|table}[...] and forward to its \end
    starts = [mm for mm in re.finditer(r"\\begin\{(figure|table)\*?\}", s)
              if mm.start() < m.start()]
    if not starts:
        return None
    b = starts[-1]
    env = b.group(1)
    e = re.search(r"\\end\{" + env + r"\*?\}", s[b.start():])
    if not e:
        return None
    return b.start(), b.start() + e.end()


def main(labels):
    p = pathlib.Path("skillvector.tex")
    s = p.read_text(encoding="utf-8")
    moved = []
    for label in labels:
        span = find_float(s, label)
        if span is None:
            print(f"  [skip] {label}: not found")
            continue
        a, b = span
        block = s[a:b]
        s = s[:a] + s[b:]
        # a moved float stops being [t]-placed at the top of a page it is no
        # longer near; [h] in the appendix keeps it next to its heading
        block = re.sub(r"\\begin\{(figure|table)(\*?)\}\[[^\]]*\]",
                       r"\\begin{\1\2}[h]", block, count=1)
        moved.append(block)
        print(f"  moved {label}")
    if moved:
        # append into the existing holding section when there is one; creating a
        # second section with the same label compiles and then silently breaks
        # every \ref to it
        head = r"\section{Figures and tables moved from the main text}"
        if head in s:
            k = s.index(head)
            k = s.index("\n", s.index(r"\label{app:moved}", k)) + 1
            s = s[:k] + "\n" + "\n\n".join(moved) + "\n" + s[k:]
        else:
            k = s.index(r"\section{Additional tables}")
            s = (s[:k] + head + "\n\\label{app:moved}\n\n"
                 + "\n\n".join(moved) + "\n\n\\clearpage\n\n" + s[k:])
    p.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
