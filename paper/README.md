# Still Needed, Hard to Transfer — LaTeX project (WWW 2027 research track)

Current title: **Still Needed, Hard to Transfer: Using and Reusing Contextual Skills**.

Result-integrated version (2026-10-17): all mechanism panels contain measured
results. On 114 common eligible Qwen3-8B/MedCalc items, layer-16 accuracy is
3.5% with residual-only transfer, 42.1% with residual-plus-source-cache repair,
and 7.0% after subsequent reader recutting. Existing cross-model/task evidence
is retained. See [the final Chinese reading guide](reports/最终版本阅读说明_20261017.md).

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
\extendedappendixfalse   % WWW submission, 12 pages  — appendices A and B  (the default)
\extendedappendixtrue    % technical report, 38 pages — appendices A–H
```

Nothing is deleted by the switch; the extended files simply are not `\input`.
The default is the submission, so a fresh Overleaf upload compiles the version
that has to fit the page limit. Flip the line in Overleaf to read the full one.

```
./build.sh              # technical report -> skillvector.pdf          (38 pages)
./build.sh submission   # WWW submission   -> skillvector-www2027.pdf  (12 pages)
```

`build.sh` sets the switch in its staging copy for whichever target you ask
for, so it does not matter which way the line is left in the repository.

Both print the structure, the undefined references, the overfull boxes, the
main-text page count and the total page count. The structure is printed on
every build because a slice edit once deleted a whole section without changing
the page count enough to notice.

## Overleaf

Upload `overleaf-skillvector.zip` (written by `tools/make_overleaf_zip.py`). It
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

## Story and display revision (2026-10-14)

The title at that revision was *When Skill Transfer Fails but Reading Continues*.
The introduction follows problem → apparent paradox → complementary interventions
→ discovery → validation and three contributions. The main depth comparison
now follows the effective early-transfer probe. See
[the Chinese storyline and evidence audit](reports/论文主线与改写说明_20261014.md).

The four main figures and two evidence tables have a separate presentation pass:

```bash
MPLCONFIGDIR=/tmp/skillvector-mpl python3 tools/style_main_figures.py
python3 tools/style_main_tables.py
```

These read the audited JSON files under `values/` without changing numerical
estimates. `refresh_main_data.py` runs them after its numerical generators.
Transfer and attention-knockout sample sizes are shown separately in the
replication table. Individual legacy generators alone do not apply the new style.

A Linux build can use Tectonic with a writable cache and output directory:

```bash
XDG_CACHE_HOME=/tmp/skillflow-tectonic-cache tectonic -k --keep-logs -o /tmp/skillflow-tex-out main.tex
```

Create the output directory first. Initial use downloads TeX dependencies;
subsequent builds can add `--only-cached`. The Windows `build.sh` is retained
for its original environment. Always inspect the `endmain` page and the PDF's
total page count before copying a build to a delivery filename.

## Focused depth-gap manuscript (2026-10-15)

The main text now keeps the validated span probe, transfer/source-attention
depth separation, common-item checks, joint-failure heatmap, repeated late
replacement and content-sharing controls. Synthetic probe development, rank
and detailed position budgets are retained in the extended appendices.

Figure 2 uses actual layer indices. All figure and table displays use point
estimates; raw uncertainty records remain in `values/` and the numerical
audit still checks them. `tools/point_estimates.py` is the idempotent table
presentation pass. `tools/fig_joint_failure.py` recomputes the same-item
heatmap from raw completed runs; no interpolation or model inference is used.

The current knockout masks skill keys for all query rows, including the skill
queries. Reader-only versus source-internal attention controls were subsequently completed
in the 2026-10-17 experiments; the paragraph above records the older revision. See
[audit/EXTRA-FAMILY-RESUME-20261015.md](audit/EXTRA-FAMILY-RESUME-20261015.md).


## Reproducing the final mechanism figures

The full-token formal records remain in the remote archive under
`/inspire/ssd/project/project-public/czxs253130660/mechanism-20261017-v1/`.
Retrieve the small completed-artifact archive once, verify the SHA256 in
`experiments/mechanism_20261017/retrieval-audit.json`, and extract to that
local experiment directory. Formal raw shards are ignored by Git; manifests,
hashes, counts and uncertainty summaries are tracked. Then run:

```bash
MPLCONFIGDIR=/tmp/paper-mpl python3 experiments/mechanism_20261017/analyze.py experiments/mechanism_20261017/parallel/repair-s4-{0,1,2,3}.jsonl --ids experiments/mechanism_20261017/ids-repair124.json --out-prefix figures/fig-mechanism-repair
MPLCONFIGDIR=/tmp/paper-mpl python3 experiments/mechanism_20261017/analyze_edges.py experiments/mechanism_20261017/parallel/edges-s4-{0,1,2,3}.jsonl --ids experiments/mechanism_20261017/ids-repair124.json --out-prefix figures/fig-mechanism-edges
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/fig_mechanism_results.py
python3 tools/audit_mechanism.py
python3 tools/check_main_data.py
```

The final experiment order is setup → validated reusable-content probe →
depth separation and robustness → source-history and reading-path mechanisms.
