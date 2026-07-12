# V5 Evaluation Contract

## Normalized decision

The evaluator uses these values:

- `action`: `OPEN`, `ADD`, `TRIM`, `SELL`, `WATCH`, `NONE`, or `REVIEW`
- `symbol`: `SPY`, `QQQ`, `IWM`, or `null`
- `direction`: `LONG`, `SHORT`, or `null`
- `status`: `actionable`, `no_action`, `ambiguous`, or `insufficient_context`

`REVIEW` is a safe model output for uncertainty. It is not an execution instruction.

## Blind input contract

The model may receive:

- raw message text;
- source message ID and timestamp;
- recent permitted trade-story context;
- position state available at that timestamp;
- the definitions of allowed output values.

The model must not receive:

- V4 parser output;
- V4 action, symbol, direction, or executable/review classification;
- prior Qwen output;
- an expected label;
- post-hoc correction notes.

The candidate lock must point to `schemas/model_output.schema.json`, which contains only the normalized decision fields. The full evaluation-record schema is scorer-side and must never be used as the model output contract because it contains labels and comparison fields.

## Comparison-only fields

The scorer may separately attach the independent label, V4 parser result, model result, latency, and error state. These fields are for evaluation and must not be included in the blind model request.

## Required result fields

Every case should preserve:

`case_id`, `source_message_id`, `message_timestamp`, `input_hash`, `model_id`, `provider`, `model_output`, `normalized_decision`, `latency_ms`, `parse_status`, `independent_label`, `v4_baseline`, and `contamination_flags`.

Invalid JSON, invalid decisions, timeouts, and runtime errors preserve `normalized_decision = null` and remain in every applicable denominator.
