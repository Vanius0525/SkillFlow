# 2026-10-17: one-day mechanism schedule

## Completed and audited, 2026-10-17

All four workers completed identity, repair and edges. The 2,478,098-byte
archive was retrieved once and SHA256-verified (see retrieval-audit.json).
Formal raw shards remain under local ignored `parallel/` and the remote root;
no raw records were deleted. There are 114 primary rescued items from all
14 calculators, with token-identical baselines between repair and edges.
48 worker own-state controls are exact. `tools/audit_mechanism.py` independently
passes 8,438 checks. Layer-16 S/C/SC/SC_recut counts are 4/8/48/8 out of 114.
Layer-24 donor reader/self/both cut counts are 29/110/29 out of 114.
All measured panels are integrated into the paper; no additional inference
is needed for the current manuscript. Reader-state repair is a future test,
not an established explanation. See figures/fig-mechanism-{repair,edges}.json
for skill-cluster uncertainty and truncation bounds.

## Update at 00:55: four GPU item shards

The user authorized parallel GPU work. `pipeline.py` is superseded as an
orchestrator; do not restart it. Its live bridge child was preserved.
`parallel_orchestrator.py` validates the completed 14-item bridge and starts
worker 0 on the original notebook. Three single-GPU Jobs execute workers 1–3.
`worker.py` partitions the same 124 fixed IDs as ids[shard::4], validates own
state at all four layers on its first item, runs repair, then a compact edge
experiment (reader/self/both, phase=both, layers 8/16/24). New sampling can run
concurrently with the global bridge; final interpretation requires all controls
to pass. No inference source or outcome-based sample selection changed.

Outputs: remote `parallel/{identity,repair,edges}-s4-{0,1,2,3}.jsonl`, plus
manifest/done/log files. `analyze.py` accepts all four repair files and refuses
missing, duplicate or incompatible shards. Repair is 2356 generations total;
compact edge tests are 1488. Full prefill/decode dissection remains deferred.

## Original serial schedule (historical)

Priority: obtain an auditable main-text repair matrix using the existing model
on one internet-enabled 48-GiB RTX 4090. No new model download.

Predeclared before any new inference:

1. First two fixed IDs: full/split prefill bridge, eager then SDPA, layers 8/16.
2. First fixed ID from each of 14 historical groups: eager bridge, layers 8/16.
   These IDs are selected from the pre-existing interleaved 124-ID list without
   inspecting any new outcomes. Both S identities and split SC identity must
   produce identical token IDs to their corresponding receiver baseline.
3. If identities pass and at least one baseline-valid early S control repairs,
   run all 124 fixed items, four layers 8/12/16/24, S/C/SC/SC_recut. Layer 28 and
   the full phase-by-edge grid are deprioritized for time, before results.

All stages use max_new=1536 (previous probe: 900). Truncation remains explicitly
recorded. A new no-skill baseline is included on every item; final eligibility
and the term “rescued” must use these new baselines. New results are a separate
protocol; token drift must be reported and cannot be silently mixed into old
curves. The bridge positive control is a deployment check, not a test of the
mechanism hypothesis. All items and outcomes, including failed baseline screens,
are retained. Four-layer repair requires 124*(3+4*4)=2356 generations.

`run.py` is a new version; the 2026-10-16 source and results remain intact.
It records hashes for all dependency Python/JSON files, runtime versions, GPU,
backend, IDs and its own source. `pipeline.py` runs serially with a process lock,
per-stage logs, completion markers, and an explicit failure marker. Never launch
a second pipeline while the first is running.

Primary descriptive mechanism contrast: SC minus S at the preselected middle
layer 16 on new-protocol rescued items. Recut at 16 and other layers/contrasts
are secondary diagnostics. Cluster bootstrap intervals are retained in JSON;
figures show point estimates as requested. No claim is made from a single
item or from an uncompleted arm.
