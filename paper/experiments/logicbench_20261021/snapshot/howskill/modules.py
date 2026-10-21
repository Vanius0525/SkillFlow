"""Split a MedCalc gold skill into modules, and build ablated variants.

Module structure was derived empirically from all 55 gold skills
(see HOWSKILLWORK/P0-FINDINGS.md §1) — NOT from the paper's stated
A.4.1 template, which does not match the released documents.

    M1 context    intro paragraph before the first '###'      55/55
    M2 inputs     '### Required Inputs'                       55/55
    M3 procedure  '### Computation' | '### Scoring Criteria'  55/55
    M4 tooldoc    '### Calculation Tool(s)'                   55/55
    M5 example    '### Example'                               55/55
    M6 units      '### Unit Conversion' + variants            15/55  (optional)
    M7 notes      '### Key Notes' | '### Important Conventions' 11/55 (optional)
    Mx other      one-off headers (kept, never ablated)
"""

from __future__ import annotations

import random
import re

HEADER_RE = re.compile(r"^(#{2,4})[ \t]+(.+?)[ \t]*$", re.M)

# Header -> module. Matching is case-insensitive on the stripped header text.
_EXACT = {
    "required inputs": "M2",
    "computation": "M3",
    "scoring criteria": "M3",
    "calculation tool": "M4",
    "calculation tools": "M4",
    "example": "M5",
    "key notes": "M7",
    "important conventions": "M7",
}


def classify_header(text: str) -> str:
    t = text.strip().lower()
    if t in _EXACT:
        return _EXACT[t]
    if "unit conversion" in t:
        return "M6"
    return "Mx"


def split_modules(content: str) -> dict:
    """Return {'M1': str, 'M2': [str, ...], ...} where each non-M1 entry is a
    list of (header, body) section strings, kept in document order.

    M1 is everything before the first '###' header (including the leading
    '## Title' line, which is part of the document's identity).
    """
    heads = [
        m for m in HEADER_RE.finditer(content)
        if len(m.group(1)) >= 3          # '###' and deeper are sections
    ]
    out: dict = {"M1": "", "_order": []}
    if not heads:
        out["M1"] = content
        return out

    out["M1"] = content[: heads[0].start()].rstrip()

    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(content)
        section = content[m.start(): end].rstrip()
        mod = classify_header(m.group(2))
        out.setdefault(mod, []).append(section)
        out["_order"].append((mod, section))
    return out


def render(mods: dict, drop: set[str] | None = None) -> str:
    """Reassemble a skill, omitting whole modules named in ``drop``."""
    drop = drop or set()
    parts = []
    if "M1" not in drop and mods.get("M1"):
        parts.append(mods["M1"])
    for mod, section in mods.get("_order", []):
        if mod in drop:
            continue
        parts.append(section)
    return "\n\n".join(parts).strip() + "\n"


# ---------------------------------------------------------------------------
# Special variants
# ---------------------------------------------------------------------------

_TOOLCALL_LINE = re.compile(r"^TOOL_CALL:.*$", re.M)
_TOOLRESULT_LINE = re.compile(r"^TOOL_RESULT:.*$", re.M)


def example_syntax_only(mods: dict) -> str | None:
    """Minimal replacement for the '### Example' section: keeps a bare
    TOOL_CALL/TOOL_RESULT syntax demonstration, drops the clinical worked
    example. Used by the ``-M5-clinical`` arm.

    All 55 Examples demonstrate the TOOL_CALL protocol, so deleting the whole
    section confounds 'lost the worked example' with 'no longer knows how to
    call a tool' (P0-FINDINGS §2.3). Returns None if no TOOL_CALL is present.
    """
    secs = mods.get("M5") or []
    for s in secs:
        call = _TOOLCALL_LINE.search(s)
        if not call:
            continue
        res = _TOOLRESULT_LINE.search(s)
        lines = ["### Example", "", "Tool call format:", "", call.group(0)]
        if res:
            lines.append(res.group(0))
        return "\n".join(lines)
    return None


def render_m5_clinical(mods: dict) -> str:
    """Full skill with the Example section replaced by a syntax-only stub."""
    stub = example_syntax_only(mods)
    parts = []
    if mods.get("M1"):
        parts.append(mods["M1"])
    for mod, section in mods.get("_order", []):
        if mod == "M5":
            if stub is not None:
                parts.append(stub)
                stub = None          # only once, even if several M5 sections
            continue
        parts.append(section)
    return "\n\n".join(parts).strip() + "\n"


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def shuffled(content: str, seed: int) -> str:
    """Shuffle sentence order within each paragraph-ish block, preserving
    tokens but destroying procedural order. Table rows and code-ish lines are
    shuffled as line units so the text stays superficially well-formed.
    """
    rng = random.Random(seed)
    blocks = content.split("\n\n")
    out = []
    for b in blocks:
        lines = b.split("\n")
        if len(lines) > 2 and sum(l.lstrip().startswith("|") or l.lstrip().startswith("-")
                                  for l in lines) >= len(lines) // 2:
            head, rest = lines[:1], lines[1:]
            rng.shuffle(rest)
            out.append("\n".join(head + rest))
        else:
            sents = _SENT_SPLIT.split(b)
            if len(sents) > 1:
                rng.shuffle(sents)
                out.append(" ".join(sents))
            else:
                out.append(b)
    rng.shuffle(out)
    return "\n\n".join(out)


_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")


def corrupted(content: str, seed: int, rate: float = 1.0) -> str:
    """Perturb numeric constants and thresholds in the prose.

    Structure, wording and formatting are untouched — only the numbers change,
    so the document still looks like a correct skill while being wrong. This
    is the analogue of SWE-Skills-Bench's 'version-mismatched guidance'
    hypothesis: the document conflicts with reality, rather than merely
    costing tokens.

    NOTE: the skill's executable ``tools`` are deliberately NOT corrupted here
    — see arms.py for the separate ``corrupted_tool`` option. Keeping tools
    intact isolates 'the prose is wrong' from 'the computation is wrong'.
    """
    rng = random.Random(seed)

    def repl(m):
        if rng.random() > rate:
            return m.group(0)
        s = m.group(1)
        v = float(s)
        # perturb by a visible but plausible amount, never to the same value
        for _ in range(8):
            if "." in s:
                nv = round(v * rng.choice([0.5, 0.7, 1.3, 1.6, 2.0]), len(s.split(".")[1]))
            else:
                nv = int(v) + rng.choice([-3, -2, -1, 1, 2, 3, 5])
                if nv < 0:
                    nv = int(v) + rng.choice([1, 2, 3])
            if nv != v:
                break
        else:
            return m.group(0)
        return str(nv)

    return _NUM.sub(repl, content)
