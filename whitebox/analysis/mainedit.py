"""Apply substitutions to the MAIN TEXT only.

Every compressed section also exists verbatim in the appendix, so a plain
str.replace hits both copies -- or refuses, because the pattern is no longer
unique. Split at \label{endmain} and edit only the first half.
"""
import json, pathlib, sys
P = pathlib.Path("/home/vanius/proj/agent-harness/paper/skillvector.tex")
s = P.read_text(encoding="utf-8")
i = s.index("\\label{endmain}")
main, app = s[:i], s[i:]
for old, new in json.load(open(sys.argv[1], encoding="utf-8")):
    n = main.count(old)
    if n != 1:
        print(f"  SKIP ({n} hits): {old[:50]!r}")
        continue
    main = main.replace(old, new)
    print(f"  ok {len(old)} -> {len(new)}: {old[:44]!r}")
P.write_text(main + app, encoding="utf-8")
