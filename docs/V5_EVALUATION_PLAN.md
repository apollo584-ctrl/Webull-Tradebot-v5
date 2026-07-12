# V5 Blind-Qwen Evaluation Plan

## Purpose

Run a scientific readiness test of whether Qwen can independently interpret trade messages without seeing the trusted parser's answer. V5 must not assume Qwen is better merely because it disagrees with the parser.

## Planned flow

```text
message archive + timestamp + prior context + position state
    -> blind evaluator
    -> normalized Qwen decision
    -> independent label comparison for Qwen and V4 parser
    -> scored report
```

## Inputs

- raw message text and stable message ID;
- source and event timestamps;
- recent trade-story context;
- position state available at evaluation time;
- independently created expected decision label.

The evaluation set must be unseen and time-separated from any data used to tune prompts, rules, or model selection. The local parser's action, symbol, direction, and executable/review classification must not enter the Qwen prompt. V4's parser is the comparison baseline, not a Qwen input.

## Outputs

Each evaluation record should preserve the model/provider, latency, normalized decision, ambiguity handling, error state, and scoring result. Raw prompts and responses belong in local ignored runtime data unless deliberately sanitized for a fixture.

Scores must compare both Qwen and the V4 parser against the independent label set. A disagreement is not evidence of correctness. Curated corrections, hand-picked examples, or examples changed after seeing a result must not count as fresh independent evidence.

## Safety boundary

This project evaluates and reports. It does not connect to Discord, Webull, a broker, paper execution, SIM autonomy, or LIVE execution.

Deterministic safety, authorization, sizing, execution, reconciliation, and SIM/LIVE gates remain outside Qwen and remain in charge of any later supervised experiment.

## Phases

1. Define the record schema and blind-prompt contract.
2. Import or create an independently labeled, time-separated holdout set.
3. Implement offline scoring against saved model responses.
4. Add an optional local Qwen adapter behind an explicit evaluator command.
5. Redesign the deferred approval-session lifecycle before any broader SIM testing.
6. Run supervised SIM only if the evidence and a later safety review support it.

## Current exclusion

Do not copy V4 runtime code wholesale. Reuse only reviewed data shapes and test ideas needed by the evaluator.
