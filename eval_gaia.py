"""
GAIA Benchmark Evaluation - Level 1 & 2, No Tools
Tests Claude Haiku 4.5 on GAIA validation set.

File handling:
  - Images (PNG/JPG):  passed as vision input (Haiku 4.5 supports multimodal)
  - Text files (TXT/PY/JSON/JSONLD): content inserted into prompt
  - Other files (XLSX/PDF/MP3/DOCX/...): noted in prompt but not provided
"""

import os
import re
import json
import time
import base64
import string
import argparse
import mimetypes
from datetime import datetime

import pandas as pd
import anthropic

VALIDATION_DIR = os.path.join(os.path.dirname(__file__), "GAIA/2023/validation")
METADATA_FILE = os.path.join(VALIDATION_DIR, "metadata.parquet")
MODEL = "claude-haiku-4-5-20251001"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
TEXT_EXTS  = {".txt", ".py", ".json", ".jsonld", ".csv", ".md"}

SYSTEM_PROMPT = """\
You are a highly capable assistant. Answer the user's question as accurately and concisely as possible.
Your response must end with a line in this exact format:
FINAL ANSWER: <your answer>

The final answer should be a short, direct value (a word, number, name, date, etc.) with no extra explanation."""


# ---------------------------------------------------------------------------
# Answer normalization (adapted from official GAIA scoring)
# ---------------------------------------------------------------------------

def normalize_number(s: str) -> str:
    s = s.replace(",", "").strip()
    try:
        return str(float(s))
    except ValueError:
        return s


def normalize_answer(raw: str) -> str:
    s = raw.strip().lower()
    s = s.rstrip(string.punctuation)
    s = re.sub(r"^(a|an|the)\s+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    num = normalize_number(s)
    if num != s:
        return num
    return s


def extract_final_answer(response_text: str) -> str:
    for line in reversed(response_text.strip().splitlines()):
        m = re.match(r"FINAL ANSWER:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    lines = [l.strip() for l in response_text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def is_correct(predicted: str, gold: str) -> bool:
    return normalize_answer(predicted) == normalize_answer(gold)


# ---------------------------------------------------------------------------
# Build message content with file handling
# ---------------------------------------------------------------------------

def build_user_content(question: str, file_name: str) -> tuple[list | str, str]:
    """
    Returns (content, file_handling_mode).
    content is a string (text-only) or list (multimodal).
    file_handling_mode: 'none' | 'image' | 'text' | 'unsupported'
    """
    if not file_name:
        return question, "none"

    file_path = os.path.join(VALIDATION_DIR, file_name)
    ext = os.path.splitext(file_name)[1].lower()

    if ext in IMAGE_EXTS:
        try:
            with open(file_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
            media_type = mimetypes.guess_type(file_name)[0] or "image/png"
            content = [
                {"type": "text", "text": question},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
            ]
            return content, "image"
        except Exception:
            pass  # fall through to unsupported

    if ext in TEXT_EXTS:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                file_content = f.read()
            text = f"{question}\n\n--- File: {file_name} ---\n{file_content}\n--- End of file ---"
            return text, "text"
        except Exception:
            pass

    # Unsupported format
    text = f"{question}\n\n[Note: This question references '{file_name}' which cannot be read (unsupported format).]"
    return text, "unsupported"


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def make_output_filename(levels: list[int], n_questions: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lvl_str = "".join(str(l) for l in sorted(levels))
    return f"gaia_results_L{lvl_str}_{n_questions}q_{ts}.jsonl"


def evaluate(levels=(1, 2), max_questions=None, output_file=None,
             api_key=None, delay=0.5):
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    df = pd.read_parquet(METADATA_FILE)
    df = df[df["Level"].isin([str(l) for l in levels])].reset_index(drop=True)
    if max_questions:
        df = df.head(max_questions)

    n = len(df)
    if output_file is None:
        output_file = make_output_filename(levels, n)

    print(f"Model   : {MODEL}")
    print(f"Levels  : {levels}")
    print(f"Questions: {n}")
    print(f"Output  : {output_file}\n")

    stats = {str(l): {"correct": 0, "total": 0} for l in levels}
    results = []

    for _, row in df.iterrows():
        task_id  = row["task_id"]
        question = row["Question"]
        gold     = row["Final answer"]
        level    = row["Level"]
        file_name = row.get("file_name", "") or ""

        user_content, file_mode = build_user_content(question, file_name)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            response_text = response.content[0].text
            predicted = extract_final_answer(response_text)
            correct = is_correct(predicted, gold)
        except Exception as e:
            print(f"  [ERROR] task {task_id}: {e}")
            response_text = ""
            predicted = ""
            correct = False

        stats[level]["total"] += 1
        if correct:
            stats[level]["correct"] += 1

        result = {
            "task_id":   task_id,
            "level":     level,
            "file_name": file_name,
            "file_mode": file_mode,
            "question":  question,
            "gold":      gold,
            "predicted": predicted,
            "correct":   correct,
            "response":  response_text,
        }
        results.append(result)

        total_so_far = sum(s["total"] for s in stats.values())
        status = "✓" if correct else "✗"
        file_tag = f"[{file_mode}]" if file_mode != "none" else ""
        print(f"[{total_so_far:3d}/{n}] L{level} {status} {file_tag:<12} "
              f"gold={repr(gold)[:25]}  pred={repr(predicted)[:25]}")

        with open(output_file, "a") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

        if delay > 0:
            time.sleep(delay)

    # Summary
    print("\n" + "=" * 50)
    print("RESULTS SUMMARY")
    print("=" * 50)
    total_correct = total_total = 0
    per_level = {}
    for lvl in sorted(stats):
        c = stats[lvl]["correct"]
        t = stats[lvl]["total"]
        acc = c / t * 100 if t else 0
        total_correct += c
        total_total += t
        per_level[f"level_{lvl}"] = {"correct": c, "total": t, "accuracy": round(acc, 2)}
        print(f"  Level {lvl}: {c}/{t}  ({acc:.1f}%)")
    overall = total_correct / total_total * 100 if total_total else 0
    print(f"  Overall : {total_correct}/{total_total}  ({overall:.1f}%)")
    print("=" * 50)
    print(f"Saved to : {output_file}")

    summary = {
        "_type": "summary",
        "model": MODEL,
        "levels": sorted(str(l) for l in levels),
        "timestamp": datetime.now().isoformat(),
        "per_level": per_level,
        "overall": {"correct": total_correct, "total": total_total, "accuracy": round(overall, 2)},
    }
    with open(output_file, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    return results, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Claude Haiku 4.5 on GAIA")
    parser.add_argument("--levels", nargs="+", type=int, default=[1, 2],
                        help="Levels to evaluate (default: 1 2)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max number of questions (for quick testing)")
    parser.add_argument("--output", default=None,
                        help="Output file (default: auto-named with timestamp and count)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between API calls in seconds (default: 0.5)")
    parser.add_argument("--api-key", default=None,
                        help="Anthropic API key (default: ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    evaluate(
        levels=args.levels,
        max_questions=args.max,
        output_file=args.output,
        api_key=args.api_key,
        delay=args.delay,
    )
