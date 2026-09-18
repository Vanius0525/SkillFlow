"""Replace a main-text span with a tighter version and park the original.

The main text has to fit nine pages and the long version of every argument is
worth keeping, so nothing is deleted: the original prose goes to a labelled
appendix subsection and its floats go with it.

    python compress.py <json spec file>

spec: [{"start":..., "end":..., "new":..., "title":..., "label":...}, ...]
"""
import json, re, sys, pathlib

P = pathlib.Path("/home/vanius/proj/agent-harness/paper/skillvector.tex")
s = P.read_text(encoding="utf-8")
HEAD = "\\section{Figures and tables moved from the main text}"

for spec in json.load(open(sys.argv[1], encoding="utf-8")):
    a = s.index(spec["start"]); b = s.index(spec["end"])
    old = s[a:b]
    # NOT `\\begin{table}.*?\\end{table}`: with re.S that spans from the first
    # table in the file to the requested one and swallows everything between,
    # which is how a 6k-character replacement once became 36k and duplicated
    # three floats. The (?!\\begin) guard keeps each match inside one environment.
    FLOAT = re.compile(
        r"\\begin\{(figure|table)\}(?:(?!\\begin\{\1\}).)*?\\end\{\1\}", re.S)
    floats = [m.group(0) for m in FLOAT.finditer(old)]
    s = s[:a] + spec["new"] + s[b:]
    k = s.index("\n", s.index("\\label{app:moved}", s.index(HEAD))) + 1
    body = FLOAT.sub("", old)
    body = re.sub(r"^\\(sub)?section\{[^}]*\}\s*", "", body)
    body = re.sub(r"\\label\{[^}]*\}\s*", "", body, count=1)
    s = (s[:k] + f"\n\\subsection{{{spec['title']}}}\n"
         f"\\label{{{spec['label']}}}\n\n" + body.strip() + "\n\n"
         + "\n\n".join(floats) + "\n\n" + s[k:])
    print(f"  {spec['label']}: {len(old)} -> {len(spec['new'])}")

P.write_text(s, encoding="utf-8")
