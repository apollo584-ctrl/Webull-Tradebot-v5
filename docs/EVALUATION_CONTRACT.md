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

## Comparison-only fields

The scorer may separately attach the independent label, V4 parser result, model result, latency, and error state. These fields are for evaluation and must not be included in the blind model request.

## Required result fields

Every case should preserve:

`case_id`, `source_message_id`, `message_timestamp`, `input_hash`, `model_id`, `provider`, `model_output`, `normalized_decision`, `latency_ms`, `parse_status`, `independent_label`, `v4_baseline`, and `contamination_flags`.
