# V5 Handoff — Blind Qwen Evaluation

Last updated: 2026-07-12

## Purpose

V5 is a scientific readiness test for whether a local model can interpret Discord trade messages without being shown the V4 parser's answer. It is not a replacement trading bot.

Qwen is not considered better merely because it disagrees with V4. Qwen and the V4 parser must be compared against independent labels from an unseen, time-separated holdout set.

## Active Workspace

- V5 directory: `C:\Users\gregd\Codex Projects\Webull Tradebot v5`
- V4 stable, read-only reference: `C:\Users\gregd\Codex Projects\Webull Tradebot v4 Qwen`
- V4 tag: `v4-stable-2026-07-11`
- V4 baseline commit: `a19db80`

Do not edit, run, restart, or use V4 while working in this folder unless explicitly asked.

## Safety and Evaluation Boundaries

- Qwen receives no V4 parser answer, action, symbol, direction, or executable/review classification.
- Deterministic safety, sizing, broker, reconciliation, SIM/LIVE, and fail-closed execution gates remain outside Qwen.
- Curated corrections and hand-picked examples are not fresh independent evidence.
- No unattended SIM autonomy, paper autonomy, LIVE Qwen control, broker connection, or Webull runtime is allowed during evaluation.
- The deferred approval-session redesign must be completed before broader SIM testing.

## Current Checkpoint

- The V5 protocol, labels, contamination, clustering, candidate, and scoring controls are locked.
- The primary candidate is frozen as `qwen3:8b@500a1f067a9f` with the locked prompt and runtime settings in `config/candidate-qwen3-8b.json`, `prompts/blind_trade_classifier.txt`, and `data/holdout/candidate.lock.json`.
- The V4 parser comparator is frozen separately; its result is not an input to Qwen.
- Historical and curated data remain development evidence only.
- No prospective July 13 confirmation snapshot, independent label lock, official V4 baseline, or Qwen benchmark exists yet.

## Next Exact Step

On or after the July 13 boundary, import a V5-owned Casey raw snapshot, prepare and review clusters, create the blind label queue, complete independent labels without viewing model outcomes, lock the labels, run the frozen V4 baseline, and then benchmark the frozen candidate.

Use `docs/PROSPECTIVE_CAPTURE_RUNBOOK.md` for the commands and stop conditions. Do not alter the candidate or prompt after confirmation outcomes are visible.

## Verification

Latest preparation checks: 21 focused tests passed, Python compilation passed, JSON parsing passed, candidate-lock dry run passed, CLI help checks passed, and the protocol verifier passed.

No Discord, Qwen, Webull, broker, SIM, paper, or LIVE process was started for this phase.
