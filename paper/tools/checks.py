#!/usr/bin/env python3
"""Structural checks the LaTeX log will not make.

A duplicate \\label compiles cleanly and silently redirects every \\ref to the
last definition, which is how a main-text figure reference once pointed at its
own copy in the appendix. A float environment opened and not closed is the other
failure that survives a clean build.
"""
import collections
import pathlib
import re
import sys

s = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
dup = [l for l, c in collections.Counter(
    re.findall(r"\\label\{([^}]*)\}", s)).items() if c > 1]
print("  duplicate labels:", ", ".join(dup) if dup else "none")
nb = len(re.findall(r"\\begin\{(?:figure|table)\}", s))
ne = len(re.findall(r"\\end\{(?:figure|table)\}", s))
print(f"  float begin/end: {nb}/{ne}" + ("  MISMATCH" if nb != ne else "  ok"))
i = s.find("\\label{endmain}")
if i > 0:
    main = s[:i]
    refs = set(re.findall(r"\\ref\{([^}]*)\}", main))
    labs = set(re.findall(r"\\label\{([^}]*)\}", main))
    fwd = sorted(r for r in refs - labs if r.startswith(("fig:", "tab:")))
    print("  main-text floats referenced but defined in the appendix:",
          ", ".join(fwd) if fwd else "none")
