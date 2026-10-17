# Mechanism experiments, 2026-10-16

Run only after inspecting the startup report. New results are not yet paper claims.

- `run.py`: eager attention; same-length wrong-skill receiver; baseline, edge/phase cuts, residual/cache factorial and optional reader patch. Layers are zero-based.
- `ids-qwen8-medcalc.json`: 124 previously joint-baseline-valid items, 14 groups, interleaved by fixed group ID. Fresh eager/split baselines are always rerun.
- `test_instruments.py`: CPU mask-direction, absolute-position, no-mutation and fail-closed checks.
- `analyze.py`: validates declared complete arm/layer coverage; renders measured cells only. Incomplete plots require explicit opt-in and carry a DEVELOPMENT watermark.

Cache intervention C replaces source-position KV at blocks 0 through L after prefill of tokens 0 through N-2. The final prompt token N-1 is then recomputed. Earlier reader states/caches are deliberately left unchanged. This estimates a checkpoint repair, not an earlier edit that recomputes all downstream history. S replaces block-L source residual during that prefix pass. R covers only task-span positions, excluding the final prompt token. SC_recut masks reader-to-source from L+1 in that same execution.

Every output stores text, token IDs, grading, truncation, first-token top-5 log probabilities and hook counters. A configuration/source hash prevents incompatible resume. Output flock prevents duplicate writers; malformed records fail closed. Completed runs write `.done.json`. Never interpret a missing done file as an instruction to launch another writer.

Probe must establish own-state+own-cache identity and inspect full-vs-split drift. Backend/hardware drift from historical experiments must be reported, not hidden by copying old baselines. New primary effects use fixed complete items and new baseline eligibility. Historical 124-item outcomes remain available as a separate denominator.

Example (paths are explicitly supplied, no model download):

```sh
python run.py --repo /path/to/agent-harness --model /path/to/Qwen3-8B \
  --ids ids-qwen8-medcalc.json --out /path/to/unique-run/probe.jsonl \
  --suite probe --layers 8,16 --limit 2 --phases both --max-new 900
```

Formal schedules and remote status are recorded in `paper/HANDOFF.md` and run manifests.
