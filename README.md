# Membrane Colony Model

Artifact for the paper *Independence by Access: A Colony Model of Separation of Duties in Autonomous AI Pipelines*.

## Contents

| File | What it does |
|------|-------------|
| `proofs/Membrane.lean` | Lean 4 formalization of Theorems 1–6 (core library only) |
| `independence_check.py` | Static checker: influence graph, properties P1–P8, obedience gap, admission test |
| `dynamic.py` | Run-level model: executes the colony under worst-case workers |
| `verify_theorems.py` | Cross-checks the static checker against the run model |

## Reproducing

**Lean proofs** (requires [Lean 4.35.0](https://github.com/leanprover/lean4/releases/tag/v4.35.0)):

```
lean proofs/Membrane.lean
```

Compiles without warning and contains no `sorry`.

**Python programs** (standard library only, Python 3.10+):

```
python3 independence_check.py
python3 dynamic.py
python3 verify_theorems.py
```

All three use fixed seeds and produce deterministic output.
