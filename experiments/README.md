# Experiments

Experiment validation scripts for EntropyShield.

## Status: In Progress

Full experiment results with attack/defense matrices will be published here
upon completion of the validation phase (estimated: 72 hours from 2026-02-15).

## Experiment Design

- **Models:** Claude Opus 4.6, Gemini 3 Pro
- **Attack categories:** 8+ prompt injection patterns
- **Conditions:** Full prompt (control) vs. HEF-fragmented prompt (treatment)
- **Metric:** Leak detection (full / partial / hint / structural / none)
- **Defense levels:** L0 (no defense), L1 (light), L2 (strong system prompt)

## Files (coming soon)

- `prompt_injection_test.py` — Core experiment: fragment vs. full prompt leak rates
- `multi_level_defense.py` — Testing across different system prompt defense levels
- `results/` — JSONL result logs with full reproducibility data
