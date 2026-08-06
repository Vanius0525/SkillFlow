---
name: web-search
description: "Search the open web via a local SearXNG instance, then fetch and extract clean article text from any URL. Use whenever a question needs up-to-date facts, named entities, schedules, prices, reviews, statistics, or anything beyond training knowledge. Prefer this over raw curl — SearXNG aggregates Google/Bing/DuckDuckGo/Brave/Wikipedia, and the fetch script returns readable text instead of JS shells."
metadata:
  version: "1.0.0"
---

# Web Search Skill

Two shell scripts give you (1) a real search engine and (2) a clean
page-text extractor. Both are local, no API keys.

Skill base directory:
```
~/agent-harness/scibench_skills/web-search/
```

## When to use

Use whenever the answer depends on information you don't already know:
current schedules, opening hours, recent events, named-entity facts,
product specs, reviews, sports/financial data, anything web-shaped.

Do NOT fall back to `curl https://duckduckgo.com/...` or
`curl https://www.google.com/search?...` — both return error pages or
JavaScript shells. Use the scripts below instead.

## Tool 1 — search.py

Queries the local SearXNG (Bing + Mojeek + Yandex + Wikipedia for general
search) and prints a JSON list of `{title, url, snippet, engine}`.

```bash
python3 ~/agent-harness/scibench_skills/web-search/scripts/search.py \
  "yellowstone family hikes tripadvisor reviews" -n 8
```

Flags:
- `-n N`         number of results (default 5; raise to 8–10 when you need to compare sources)
- `--category C` one of `general` (default), `news`, `academic`, `social`, `images`, `videos`
  - `news`     — recent events, breaking news (Bing News, Google News, Mojeek News)
  - `academic` — papers (arXiv, PubMed, Google Scholar, Semantic Scholar, Crossref)
  - `social`   — forum discussion via Boardreader and lobste.rs. **No Reddit** on
    this instance, so coverage of "what do people recommend" is thin. Try it once
    for opinion questions, but fall back to `general` rather than reformulating
    `social` queries repeatedly.

Query style: short keyword phrases beat full sentences.
- Bad: `"what gyms near tompkins square park have early classes"`
- Good: `"gym Tompkins Square Park Manhattan early morning class schedule"`

If a query returns junk, reformulate (add a year, a city, a technical
term) and search again — 2–3 reformulations is normal.

## Tool 2 — fetch.py

Downloads a URL and returns the main readable article text (via
`trafilatura`). Handles encoding and strips boilerplate.

```bash
python3 ~/agent-harness/scibench_skills/web-search/scripts/fetch.py \
  "https://example.com/some-page" --max-chars 6000
```

Flags:
- `--max-chars N` truncate output (default 8000; lower if you only need a snippet)
- `--raw`         print the full HTML instead of extracted text — use when
                  you need to grep for a specific tag, structured data, or
                  a JSON blob embedded in `<script>`.

If `trafilatura` returns empty (rare — pure-JS SPAs), retry with `--raw`
and `grep` / Python parse what you need.

## Recommended pattern (3 commands)

```bash
# 1. Search
python3 ~/agent-harness/scibench_skills/web-search/scripts/search.py \
  "<keywords>" -n 8

# 2. Pick the 2–3 most relevant URLs from the JSON, then fetch each:
python3 ~/agent-harness/scibench_skills/web-search/scripts/fetch.py \
  "<url1>" --max-chars 6000

# 3. Cross-check by searching with a different phrasing if results disagree.
```

## Notes

- The SearXNG instance runs on `http://127.0.0.1:8888` by default. `search.py`
  starts it automatically when it is installed locally.
- If `search.py` reports `"SearXNG is not installed here"`, web search is
  unavailable on this machine. Do **not** retry the search or fall back to
  `curl` against Google/DuckDuckGo — answer from what you already have.
- Deployment (not something the agent does mid-task): the install location is
  read from the environment, so nothing in this skill needs editing per machine.
  ```bash
  export SEARXNG_HOME=/path/to/install      # expects $SEARXNG_HOME/searxng
  #                                         # and  $SEARXNG_HOME/searxng-venv
  export SEARXNG_ENDPOINT=http://host:8888/search   # or point at a running instance
  ```
- For numeric/list answers, fetch the actual source page and extract the
  number yourself rather than trusting the snippet — snippets are often
  truncated mid-sentence.
- Don't burn turns on the same failing query — if 2 attempts return
  nothing useful, change the keywords substantially or try a different
  category (e.g. `--category social` for reviews).
