# howskill — MedCalc skill-mechanism experiments

Runs the protocol in `../HOWSKILLWORK/PROTOCOL.md` on a single 4090.
Everything not needing a GPU is already done; the data is committed, so the
server never has to fight the network (the 232 MB corpus took 12 resumed
attempts to partially fetch — don't try again, the 55 skills we need are in
`data/`).

## What's here

```
data/medcalc_skills.json   55 gold calculator skills (from SRA-Bench corpus)
data/medcalcbench.json     1,100 task instances (55 calculators x 20)
data/stepgt.json           1,098 joined step-level GT (Relevant Entities +
                           Ground Truth Explanation from MedCalc-Bench v1.0)
data/neutral_pairs.json    ctrl_neutral pairing, audited: 0 same-family,
                           0 answer leaks, length ratio median 0.98

howskill/modules.py   split a skill into M1-M7; build ablated variants
howskill/arms.py      the 13 experiment arms + neutral pairing/audit
howskill/prompts.py   SR-Agents prompt format (faithful port)
howskill/grade.py     SR-Agents MedCalc extraction + scoring (faithful port)
howskill/loop.py      SR-Agents tool loop + 4 hooks (prefix/schedule/log/determinism)
howskill/steps.py     S1-S5 first-failure classifier, transition matrix
howskill/run.py       runner CLI
howskill/analyze.py   per-arm table, clustered bootstrap CI, transition matrix
howskill/selftest.py  offline validation, no GPU
```

`grade.py` and `prompts.py` are **faithful ports** of SR-Agents
(`oneal2000/SR-Agents` @ main, fetched 2026-08-29). Do not "improve" them:
P1 reproduces that paper's published numbers, which only means something if
extraction and scoring are theirs bit-for-bit.

## Setup on the server

```bash
source $BASE/env.sh          # restores venv, models, QWEN_* vars
$BASE/run-server.sh start    # vLLM
python -m howskill.selftest  # must print ALL SELFTESTS PASSED first
```

Only extra dependency is `requests`.

## P1 — calibration gate (do this first)

Reproduce SRA-Bench's published **Qwen3-4B on MedCalc: Direct 22.0 / Oracle 73.5**.
This is the only external check that our harness is correct. Match their
settings: temperature 0.7, no explicit tool-protocol note.

```bash
python -m howskill.run --arm no_skill --model Qwen/Qwen3-4B \
    --temperature 0.7 --no-tool-protocol --out results/p1 --tag p1-direct
python -m howskill.run --arm gold --model Qwen/Qwen3-4B \
    --temperature 0.7 --no-tool-protocol --out results/p1 --tag p1-oracle
python -m howskill.analyze results/p1
```

**GATE-1: both within ±5pp of 22.0 / 73.5.** If not, stop and debug — do not
proceed. Check in this order:

1. **`--thinking`** — upstream defaults `thinking=False` but also strips
   `<think>` tags, so the setting may vary by experiment. Try both.
2. answer extraction — dump `extracted_answer` for 20 failures and eyeball it
3. `max_tokens` truncation — check `finish_reason` is `stop`, not `length`
4. tool loop firing at all — `n_tool_calls` should be > 0 on the Oracle arm

## P2 — main effect + H6 gate

```bash
for arm in no_skill gold ctrl_neutral; do
  python -m howskill.run --arm $arm --temperature 0 --out results/p2
done
python -m howskill.analyze results/p2
```

**GATE-2 (H6): `gold - ctrl_neutral` must be clearly positive.** If the
neutral skill does as well as the gold one, the effect is presence, not
content, and the content ablations below are meaningless. That result is
worth writing up on its own — but stop and redesign rather than running P3.

## P3-P5 — ablations (only after GATE-2)

Pick the deep subset first: calculators whose `no_skill` accuracy is in
15-75% (avoid floor and ceiling), then

```bash
for arm in drop_M1 drop_M2 drop_M3 drop_M4 drop_M5 m5_clinical \
           ctrl_shuffled ctrl_corrupted no_tool no_tool_no_M4; do
  python -m howskill.run --arm $arm --temperature 0 --n-per-calc 8 --out results/p3
done

# P4 temporal
python -m howskill.run --arm gold --schedule first --n-per-calc 8 --out results/p4
python -m howskill.run --arm gold --schedule late  --n-per-calc 8 --out results/p4

python -m howskill.analyze results/p3 --steps
```

## P7 — trajectory grafting

Build prefixes from discordant instances (gold correct, no_skill wrong), then

```bash
python -m howskill.run --arm no_skill --prefixes grafts/t1.json --out results/p7
```

`grafts/*.json` is `{instance_id: {"trajectory": <recorded traj>, "upto_turn": k}}`.
`loop.make_prefix` turns a recorded trajectory into forced messages.

**Verify the prefix reproduces.** vLLM is not bitwise deterministic across
batch compositions; count and report grafts where it doesn't, don't hide them.

## Reporting rules

- Headline number is **`gold - ctrl_neutral`** (presence effect removed);
  report `gold - no_skill` alongside it for comparability with the papers.
- CIs are bootstrapped over **calculators**, not instances — the 20 sharing a
  calculator are not independent.
- Our Oracle numbers are **not comparable** to SkillsBench's +16.2pp: different
  delivery protocol (forced injection vs. agent-discovers-files). See
  `../HOWSKILLWORK/HANDOFF.md` §4.5.2.
- Always report token cost per arm — the skill arms have much longer prompts.
