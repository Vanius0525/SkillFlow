# Seven-cell expansion of the 24 core state-completeness controls

User authorization: 2026-10-24, execute directly on Inspire and check every three hours. No new paper edits in this task.

The completed Qwen3-8B/MedCalc run is reused. The seven new cells pair Qwen3-8B (TheoremQA only), Mistral-7B, Llama-3.1-8B and DeepSeek-7B with MedCalc/TheoremQA. Historical candidate pools are frozen before new inference (457 candidate questions total); only model-context input-length exclusions are allowed in preflight. This does not run the entire benchmarks.

Each item has exactly 24 formal conditions: donor/wrong/neutral-A/no-skill baselines; SC and explicit all-source SC_exact at L8/16/24 in both receivers; C_all/B_only/full_copy/suffix_replay in both receivers. Layer indices are zero-based, as in the original experiment. No canceled full-depth study or 41/49-condition expansion is included.

`frozen_run.py` preserves the original Engine class exactly (AST checked). New orchestration reuses its prefix, cache write/audit, greedy generation and same neutral-A text. TheoremQA resets the official parser globals before every answer. Runtime source writes and independent full-prefix token identities are audited; SC source coverage is measured rather than assumed exact for unseen models.

A cell's first two items are gate items, chosen before outcomes. Gate evaluates all 24 conditions plus a receiver self-state identity check. Passing gate records for the 24 formal conditions are copied to the formal output, avoiding repeat inference. Every raw record is a flushed, append-only gzip member. Separate CPU-only `audit_core.py` process checks the full key grid, hashes, saved source audits, identity controls, forward/reverse official labels, truncation and paired skill-group intervals. Full raw outputs stay on the remote shared disk; small audit summaries are printed to platform logs and retrieved locally by the watcher.

Deployment does not depend on a CPU Notebook: the command contains a small compressed source payload, checks shared data against frozen hashes, and runs tokenizer preflight under a deployment lock. It copies only matching existing datasets; model weights are never downloaded. Seven unique one-GPU Jobs may run concurrently. A 48-hour per-job bound and seven-day supervision bound are explicit; expiry is reported, never interpreted as completion.

Entrypoints: `HANDOFF.md`, `launch-state.json`, `monitor-state.json`, `jobs.json`. Runtime `watch-config.json` contains the current conversation target and is not a portable experiment input. `watch.py` checks every three hours through platform logs; it does not submit or retry jobs. Do not launch `submit.py` again if an in-flight name is unresolved; reconcile live names and existing records first. No deletion or automatic failed-job rerun.
