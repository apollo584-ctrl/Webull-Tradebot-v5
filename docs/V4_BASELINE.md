# V4 Comparison Baselines

## Confirmatory comparator

The frozen Group 7 comparator is `v4-raw-text-parser-a19db80`: V4 `SignalParser.parse` at tag `v4-stable-2026-07-11`, commit `a19db80`.

It receives raw message text only. This is intentional because V4's parser does not accept position or recent-story context. Qwen may receive the permitted context defined by the V5 protocol, so this comparison measures whether the proposed model-assisted interpretation system adds value beyond the current raw-text rule parser. It is not an apples-to-apples claim that both systems receive identical inputs.

## Operational comparator

The complete V4 trading service also uses position state, intent context, timeline events, NLP review, and deterministic decision gates. It is a separate operational comparator and must be reported separately when prospective saved decisions are available. Group 7 does not import or run that service because it reads runtime state and can involve model/runtime components.

Neither comparator is input to Qwen. Parser and operational outputs remain hidden until independent labels are frozen.

## Historical diagnostic

The existing 343-row candidate regression set is curated V4 development data. Its report validates that the frozen parser adapter runs reproducibly, but it is not independent performance evidence and cannot support promotion.
