# V5 Blind Labeling Guide

Label each case without viewing V4 parser output, Qwen/model output, prior reviews, or correction notes.

## Action rubric

- `OPEN`: establish a new position from flat state.
- `ADD`: increase an existing same-symbol, same-direction position.
- `TRIM`: reduce part of an existing position.
- `SELL`: close the remaining position.
- `WATCH`: setup or observation with no immediate executable action.
- `NONE`: ordinary chat, recap, stale information, or no trade instruction.
- `REVIEW`: potentially actionable intent that cannot be resolved safely from permitted context.

## Status rubric

- `actionable`: action, symbol, and required direction are sufficiently clear.
- `no_action`: the correct response is `WATCH` or `NONE`.
- `ambiguous`: multiple materially different interpretations remain plausible.
- `insufficient_context`: required prior position/story information is unavailable.

## Valid combinations

| Action | Required status | Symbol/direction |
|---|---|---|
| `OPEN`, `ADD`, `TRIM`, `SELL` | `actionable` | Both required |
| `WATCH`, `NONE` | `no_action` | Optional when useful context is explicit |
| `REVIEW` | `ambiguous` or `insufficient_context` | Optional; include only what is unambiguous |

Any other action/status combination is invalid and must fail validation.

## Novelty rubric

- `linguistically_novel`: the intended meaning depends on wording or implication absent from the frozen historical phrase catalog and its near-duplicate clusters.
- `known_or_near_duplicate`: the wording is represented in historical development material.
- `not_applicable`: no trade-language interpretation is required.
- `unresolved`: novelty cannot be determined blind; this blocks confirmatory novelty scoring.

Hard cases stay in the dataset. Use `REVIEW`, `ambiguous`, or `insufficient_context`; do not delete them.
