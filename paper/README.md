# SkillVector — LaTeX project (WWW 2027 research track)

`main.tex` is the whole document. Everything else is either a piece of it or a
generator that writes one of those pieces.

```
main.tex                preamble, ACM metadata, and the \input skeleton
sections/               main text, one file per section (00 abstract … 05 conclusion)
appendix/               appendices, one file per theme (a … g)
tables/                 tabulars, written by tools/ — do not edit by hand
figures/                figures, written by tools/ — do not edit by hand
skillvector.bib         bibliography
build.sh                local build against the Windows MiKTeX
tools/                  the generators and the data checker
values/                 the JSON records the numbers are read back from
audit/                  audit logs from earlier passes
legacy/                 the ICLR one-column sources this replaced; safe to delete
```

## Format

The ACM Web Conference 2027 research track asks for
`\documentclass[sigconf, anonymous, review]{acmart}` and caps a long paper at
**8 pages of main content plus references and an optional appendix, 12 pages in
total**, with the first 8 pages self-contained.
See <https://www2027.thewebconf.org/research-track-papers/>.

Three things in `main.tex` are placeholders and must be replaced before
submission: the `\acmConference`/`\acmDOI`/`\acmISBN` block (the ACM rights form
emails you the real one), the CCS concepts (regenerate at
<https://dl.acm.org/ccs>), and the anonymous author block.

## The two builds

`main.tex` carries one switch:

```latex
\extendedappendixtrue    % full technical report  — appendices A–G
\extendedappendixfalse   % WWW submission         — appendices A, B, D only
```

Nothing is deleted by the switch; the extended files simply are not `\input`.

```
./build.sh              # full report
./build.sh submission   # flips the switch in the staging copy only
```

Both print the structure, the undefined references, the overfull boxes, the
main-text page count and the total page count. The structure is printed on
every build because a slice edit once deleted a whole section without changing
the page count enough to notice.

## Overleaf

Upload `overleaf-skillvector.zip` (written by `tools/make_overleaf_zip.sh`). It
contains `main.tex`, `sections/`, `appendix/`, `tables/`, `figures/*.pdf` and the
`.bib` — no Python, no PNGs, no audit logs. Overleaf resolves `acmart` itself.
Set the compiler to pdfLaTeX.

## Regenerating the numbers

No model inference and no network; everything reads the local run records under
`../howskill/results/` and `../whitebox/results/`.

```
cd paper
MPLCONFIGDIR=/tmp/skillvector-mpl python3 tools/refresh_main_data.py
```

That runs, in order: `main_evidence.py`, `replication.py`, `replication_full.py`,
`fig_channels_full.py`, `fig_rank_full.py`, `fig_posbudget.py`,
`check_main_data.py` and `../whitebox/analysis/audit.py`. It does **not** cover
three generators; run them by hand after changing what they read:

```
python3 tools/controls_table.py                       # tables/tab-controls.tex
python3 tools/decomp_tables.py                        # tab-causal, tab-parperp, tab-geometry-tierA
python3 tools/figs.py --e14 "tierA=../whitebox/results/fetched/tA/d17-neutral" --out figures
```

`tools/check_main_data.py` compares every main-text display against the records
and fails loudly on a drift; `whitebox/analysis/audit.py` does the same for the
historical results. Both must pass before a build is trusted.
