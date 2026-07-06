#!/usr/bin/env python3
"""
Rewrite relative script/resource paths in scibench_skills/*/SKILL.md to the
canonical absolute form used by the harness:

    ~/agent-harness/scibench_skills/<skill>/...

Why: the agent's bash tool runs with cwd = agent_workspace/, so commands like
`python3 wolfram_query.py` or `python scripts/foo.py` copied verbatim from a
SKILL.md can never find the script. The web-search skill already uses the
~/agent-harness/... convention; this script applies it everywhere.

Idempotent: running it a second time changes nothing.

Usage:
    python fix_skill_paths.py [skills_dir] [canonical_prefix]

    # scibench (default prefix):
    python fix_skill_paths.py scibench_skills
    # GAIA / anthropic skills:
    python fix_skill_paths.py anthropic_skills/skills/skills '~/agent-harness/anthropic_skills/skills/skills'
"""
import re
import sys
from pathlib import Path

DEFAULT_CANON = "~/agent-harness/scibench_skills"
SCRIPT_EXTS = {".py", ".sh", ".js", ".mjs", ".ts"}
SKIP_DIRS = {"venv", "node_modules", "__pycache__", ".git"}


def fix_skill(skill_dir: Path, canon: str) -> int:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return 0
    skill = skill_dir.name
    prefix = f"{canon}/{skill}"
    text = orig = md.read_text(encoding="utf-8")

    # 1. Placeholders: <skill_folder> (tex-render) and <skill-name-path>
    #    (anthropic skill-creator style)
    text = text.replace("<skill_folder>", prefix)
    text = text.replace(f"<{skill}-path>", prefix)

    # 2. $SKILL_DIR variable (math-worksheets style). Use $HOME instead of ~
    #    because these usages sit inside double quotes where ~ won't expand.
    home_prefix = prefix.replace("~", "$HOME", 1)
    text = text.replace("$SKILL_DIR", home_prefix)

    # 3. Real subdirectories of the skill (scripts/, references/, src/, ...):
    #    prefix bare or ./-relative references. Longest names first so
    #    "references/" is handled before "reference/" could shadow it.
    subdirs = sorted(
        (d.name for d in skill_dir.iterdir()
         if d.is_dir() and d.name not in SKIP_DIRS),
        key=len, reverse=True,
    )
    for d in subdirs:
        dq = re.escape(d)
        text = re.sub(rf"(?<![\w/$.~-])\./{dq}/", f"{prefix}/{d}/", text)
        text = re.sub(rf"(?<![\w/$.~-]){dq}/", f"{prefix}/{d}/", text)

    # 4. Root-level script files invoked as bare commands
    #    (python3 wolfram_query.py ... -> python3 ~/.../wolfram_query.py ...)
    for f in skill_dir.iterdir():
        if f.is_file() and f.suffix in SCRIPT_EXTS:
            name = re.escape(f.name)
            text = re.sub(
                rf"((?:python3?|bash|sh|node|npx)\s+)(?!\S*/){name}\b",
                rf"\g<1>{prefix}/{f.name}",
                text,
            )

    if text != orig:
        md.write_text(text, encoding="utf-8")
        return 1
    return 0


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "scibench_skills")
    canon = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else DEFAULT_CANON
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    changed = [d.name for d in sorted(root.iterdir()) if d.is_dir() and fix_skill(d, canon)]
    print(f"modified {len(changed)} SKILL.md files:")
    for name in changed:
        print(f"  - {name}")
    if not changed:
        print("  (nothing to change — already canonical)")


if __name__ == "__main__":
    main()
