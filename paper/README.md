# Still Needed, Hard to Transfer — WWW 2027 submission

Title: **Still Needed, Hard to Transfer: Using and Reusing Contextual Skills**.

Only the submission is maintained and exported. Historical extended sources
and snapshots remain archived in the repository; they are not loaded by
`main.tex`, regenerated, or included in the Overleaf ZIP.

## Build and upload

```bash
bash build.sh
python3 tools/make_overleaf_zip.py
```

The build writes `skillvector-www2027.pdf`. Upload `overleaf-skillvector.zip`
to Overleaf, choose `main.tex`, and use pdfLaTeX with BibTeX. The ZIP includes
only reachable TeX inputs, referenced PDF figures, the bibliography and README.
It has no experiment logs, scripts, caches, local paths, or extended-build switch.

## Format

[WWW 2027 Research Track requirements](https://www2027.thewebconf.org/research-track-papers/):
**at most 8 main-content pages excluding references and optional appendix;
at most 12 pages including everything**. The first 8 pages must be self-contained.
Use English, two columns, and `\documentclass[sigconf, anonymous, review]{acmart}`.
The work's Web relevance must be explicit on page one.

The review build remains anonymous and omits unassigned publication DOI/ISBN
and the ACM reference strip. Its standard text margins and font sizes are
unchanged. Check `audit/WWW2027-FORMAT-20261017.json` for the current PDF audit.
Assigned publication metadata belongs to the eventual camera-ready version.

## Current story

Agent Skills follow Anthropic's instruction/script/resource paradigm. Our unit
of analysis is the skill instruction content loaded into context, with skill
selection held fixed. The paper moves from Web-agent skill use to a validated
state-transfer probe, depth-wise separation of transfer and source dependence,
and causal source-history repair and reader recutting. All new mechanism
inference is Qwen3-8B/MedCalc; prior cross-model/task evidence is retained.
The AI Use Statement was removed at the user's request.

The latest Chinese reading guide is
[Three-figure / three-table revision](reports/三图三表修订说明_20261017.md).
Nearest-neighbor distinctions and primary-source links are documented there.

## Figures, tables, and audits

```bash
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/style_main_figures.py
python3 tools/style_main_tables.py
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/fig_two_probes.py
MPLCONFIGDIR=/tmp/paper-mpl python3 tools/fig_mechanism_results.py
python3 tools/audit_citations.py
python3 tools/check_main_data.py --numeric-only
```

Styling reads audited values and preserves point estimates, samples and raw
uncertainty. The default style pass updates only submission figures and tables.
It does not regenerate archived rank/position diagnostics or extended appendices.
`check_main_data.py --numeric-only` checks the underlying numerical records
and plots, including historical diagnostics. Its legacy exact-wording checks
are skipped because the manuscript has been rewritten. The three-figure
format is verified separately by `tools/check_www_format.py`.

The formal full-token mechanism records remain in the remote archive under
`/inspire/ssd/project/project-public/czxs253130660/mechanism-20261017-v1/`.
Retrieve the small archive once, verify `experiments/mechanism_20261017/retrieval-audit.json`,
and extract to that local experiment directory. Raw shards are ignored by Git;
compact manifests, hashes, counts and clustered uncertainty are tracked.
`tools/audit_mechanism.py` independently recounts raw results and figure cells.
