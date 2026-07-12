# Webull Tradebot V5

V5 is an offline, blind-Qwen evaluation workspace. It tests natural-language trade interpretation without exposing the trusted parser's answer to the model.

## Structure

- `src/v5_eval/` — evaluator package
- `scripts/` — offline dataset and scoring commands
- `tests/fixtures/` — small sanitized checks
- `data/raw/` — local source archives
- `data/labels/` — independent labels
- `data/holdout/` — time-separated evaluation set
- `data/results/` — local reports and model outputs
- `docs/` — plans and handoffs

V5 does not contain broker, Webull, Discord, dashboard, or execution code during this phase.
