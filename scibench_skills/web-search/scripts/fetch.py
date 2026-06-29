#!/usr/bin/env python3
"""
fetch — download a URL and extract the main readable text using trafilatura.

Usage:
  python3 fetch.py <url> [--max-chars 8000] [--raw]

By default emits cleaned article text. With --raw, emits the full HTML.
"""
import argparse
import sys
import urllib.request


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        enc = resp.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def extract(html: str, url: str) -> str:
    try:
        import trafilatura
    except ImportError:
        return html  # fall back to raw HTML if trafilatura missing
    text = trafilatura.extract(html, url=url, include_links=False,
                               include_tables=True, favor_recall=True)
    return text or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--max-chars", type=int, default=8000)
    ap.add_argument("--raw", action="store_true", help="print raw HTML, no extraction")
    args = ap.parse_args()
    try:
        html = fetch_html(args.url)
    except Exception as e:
        print(f"[error] fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if args.raw:
        out = html
    else:
        out = extract(html, args.url)
        if not out.strip():
            out = "[trafilatura returned empty — try --raw or another URL]"
    if args.max_chars and len(out) > args.max_chars:
        out = out[: args.max_chars] + f"\n\n[...truncated, {len(out) - args.max_chars} more chars]"
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
