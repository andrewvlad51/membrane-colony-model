# Independence experiment

Tests two predictions of the paper: (1) the obedience gap — a checker that can
read forbidden material may be influenced by it even when instructed not to be;
(2) Theorem 5 — identity assigned by the environment resists forgery while
identity assigned by content does not.

Scripts and raw logs are released with the paper.

## Runs

### Runs 1–2: verifiable tasks (null result)

**Script:** `run_experiment.py`
**Tasks:** `tasks.py` — 24 code-review tasks (correct + defective implementations).
**Design:** Author's handoff notes contain planted persuasion in five styles. Two
setups: instruction (reviewer sees notes, told they are untrusted) and access
(reviewer sees code only). Run 1: instruction vs access with planted persuasion.
Run 2: adds generic arm and amendment style.
**Result:** 432 planted trials on Claude Haiku 5.5 — 0 false approvals. When the
reviewer can verify the claim against the code, persuasion does not change the
verdict.
**Logs:** `results_haiku.jsonl` (run 1, 360 trials), `results2_haiku.jsonl`
(run 2, 216 trials).

### Run 3: unverifiable tasks (forged evidence)

**Script:** `run3.py`
**Tasks:** 20 tasks whose verdict depends on a fact held in a document the
reviewer cannot open. Four persuasion styles: assert, authority, quote (forged
excerpt), marker (forged "VERIFIED FACTS" header). Three setups: access
(code only), generic (told to be independent), explicit (told notes are untrusted).
**Result (Haiku):** Forged quote scores 70% (generic) / 0% (explicit). Forged
header scores 85% (generic) / 80% (explicit) / 85% (access, in code). Plain
assertion and authority: 0% everywhere. Genuine trusted evidence overrides forgery
(GEN 0/20). AE+ (correct code with trusted evidence): 18/20 correct approvals.
AE- (wrong code with trusted evidence): 0/20 false approvals.
**Result (Fable):** 0 false approvals across all planted conditions (80 planted
trials). AE+ 10/10.
**Logs:** `results3_haiku.jsonl` (320 trials), `results3_fable.jsonl` (160 trials).
**Date:** 2026-11-11.

### Run 4: per-trial verification tokens

**Script:** `run4.py`
**Design:** Pipeline marks its trusted section with a per-trial random token the
author never sees. Forger gets no token or a wrong token. Tests whether
environment-assigned identity (Theorem 5(a)) blocks the forged-header attack.
**Result:** All token conditions: 0/20 false approvals. Tokenless forged header:
GNm 15/20 (75%), INm 15/20 (75%), AWm 2/20 (10%). AE+ 19/20 correct approvals,
AE- 0/20 false approvals.
**Logs:** `results4_haiku.jsonl` (160 trials).
**Date:** 2026-11-11.

### Canary experiment

**Script:** `harness.py`, `config.py`
**Design:** Canary string planted in notes; three arms (explicit instruction,
generic instruction, access control). 10 topics × 5 trials per topic per arm.
**Result:** 0 leaks at n=50 per arm on Claude Haiku 5.5.
**Logs:** `results/results_claude_haiku.jsonl` (150 trials).
**Date:** 2026-11-12.

## Models

- `claude-haiku-5-5` (Claude Haiku 5.5) — all runs
- `claude-fable-5-2` (Claude Fable 5.2) — run 3 only

## Temperature

- Runs 1–2 (Gemini conditions): temperature 0. Claude CLI conditions: provider default.
- Runs 3–4: Claude CLI, provider default (no temperature flag).
- Canary: Claude CLI, provider default.

## Dependencies

Python 3.10+ standard library only. No pip packages required.

## Running

```bash
# Run 3
python3 run3.py

# Run 4
python3 run4.py

# Canary experiment
python3 -I harness.py --backend claude --model haiku --trials 50

# Summarize canary results
python3 -I harness.py --summarize results/results_claude_haiku.jsonl

# Dry run (validate config)
python3 -I harness.py --dry-run
```

Runs are resumable: finished trials in the output file are skipped on restart.

## Output format

Results logged as JSONL. Each line is a JSON object. Confidence intervals are
Wilson score 95% CIs assuming independent trials.
