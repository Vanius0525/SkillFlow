#!/usr/bin/env python3
"""
web_search — query the local SearXNG instance and emit JSON results.

Usage:
  python3 search.py "<query>" [-n 5] [--category general|news|academic|social]

Returns a JSON array on stdout: [{title, url, snippet, engine}, ...]
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CATEGORIES = {"general", "news", "academic", "social", "images", "videos"}

# Every location is overridable, so the skill travels between machines. The
# defaults describe the original workstation install; a deployment elsewhere
# sets SEARXNG_HOME (or the individual vars) instead of editing this file.
SEARXNG_HOST = os.environ.get("SEARXNG_HOST", "127.0.0.1")
SEARXNG_PORT = int(os.environ.get("SEARXNG_PORT", "8888"))
DEFAULT_ENDPOINT = os.environ.get(
    "SEARXNG_ENDPOINT", f"http://{SEARXNG_HOST}:{SEARXNG_PORT}/search"
)

SEARXNG_HOME = os.environ.get("SEARXNG_HOME", "/home/vanius")
SEARXNG_PYTHON = os.environ.get("SEARXNG_PYTHON", f"{SEARXNG_HOME}/searxng-venv/bin/python")
SEARXNG_SRC = os.environ.get("SEARXNG_SRC", f"{SEARXNG_HOME}/searxng")
SEARXNG_SETTINGS = os.environ.get(
    "SEARXNG_SETTINGS", f"{SEARXNG_HOME}/.config/searxng/settings.yml"
)
SEARXNG_LOG = os.environ.get("SEARXNG_LOG", "/tmp/searxng.log")
SEARXNG_PIDFILE = os.environ.get("SEARXNG_PIDFILE", "/tmp/searxng.pid")


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _local_install_present() -> bool:
    return os.path.exists(SEARXNG_PYTHON) and os.path.isdir(SEARXNG_SRC)


def _ensure_searxng(wait_seconds: int = 25) -> None:
    """If SearXNG isn't responding, start it (detached) — when it is installed."""
    if _port_open(SEARXNG_HOST, SEARXNG_PORT):
        return

    if not _local_install_present():
        # Nothing to spawn. Return immediately rather than polling a port that
        # nobody is going to open — that wait used to cost every single search
        # 25s of the task's wall-clock budget on machines without SearXNG.
        return

    # Avoid duplicate spawns when several callers race.
    try:
        if os.path.exists(SEARXNG_PIDFILE):
            with open(SEARXNG_PIDFILE) as f:
                pid = int(f.read().strip() or "0")
            if pid > 0 and os.path.exists(f"/proc/{pid}"):
                # Process exists but port not open yet — just wait.
                pass
            else:
                _spawn_searxng()
        else:
            _spawn_searxng()
    except Exception as e:
        print(f"[web-search] failed to spawn SearXNG: {e}", file=sys.stderr)

    # Wait up to wait_seconds for the port to come up.
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _port_open(SEARXNG_HOST, SEARXNG_PORT):
            return
        time.sleep(0.5)


def _spawn_searxng() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = SEARXNG_SRC
    env["SEARXNG_SETTINGS_PATH"] = SEARXNG_SETTINGS
    log = open(SEARXNG_LOG, "ab")
    p = subprocess.Popen(
        [SEARXNG_PYTHON, "-m", "searx.webapp"],
        stdout=log, stderr=log, env=env,
        start_new_session=True,  # detach: survive parent exit
        close_fds=True,
    )
    try:
        with open(SEARXNG_PIDFILE, "w") as f:
            f.write(str(p.pid))
    except OSError:
        pass


def search(query: str, n: int = 5, category: str = "general",
           endpoint: str = DEFAULT_ENDPOINT, timeout: int = 20) -> list[dict]:
    params = {"q": query, "format": "json", "categories": category}
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "skillflow-web-search/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    out = []
    for r in data.get("results", [])[:n]:
        out.append({
            "title": r.get("title", "").strip(),
            "url": r.get("url", ""),
            "snippet": (r.get("content") or "").strip(),
            "engine": r.get("engine", ""),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-n", type=int, default=5, help="number of results (default 5)")
    ap.add_argument("--category", default="general", choices=sorted(CATEGORIES))
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = ap.parse_args()
    if args.endpoint == DEFAULT_ENDPOINT:
        _ensure_searxng()
    try:
        results = search(args.query, n=args.n, category=args.category, endpoint=args.endpoint)
    except Exception as e:
        if os.environ.get("SEARXNG_ENDPOINT") or args.endpoint != DEFAULT_ENDPOINT:
            hint = (
                f"The configured SearXNG endpoint ({args.endpoint}) is unreachable. "
                f"Web search is unavailable — do not retry, answer from what you "
                f"already have."
            )
        elif _local_install_present():
            hint = f"Is SearXNG running on {SEARXNG_HOST}:{SEARXNG_PORT}?"
        else:
            hint = (
                f"SearXNG is not installed here (looked for {SEARXNG_PYTHON} and "
                f"{SEARXNG_SRC}). Web search is unavailable on this machine — do "
                f"not retry, answer from what you already have. To enable it, set "
                f"SEARXNG_HOME/SEARXNG_ENDPOINT or install SearXNG."
            )
        print(json.dumps({"error": f"{type(e).__name__}: {e}", "hint": hint}),
              file=sys.stderr)
        return 2
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
