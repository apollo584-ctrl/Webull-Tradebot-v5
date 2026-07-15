# V5 Role After Removing Qwen From Runtime

## Purpose

V5 is no longer the active home for Qwen promotion or model-controlled trading decisions.

Its new purpose is to serve as the offline quality-control and improvement lab for V6, the next local deterministic trading bot.

V5 does not connect to Discord, Webull, a broker, SIM execution, paper trading, or LIVE trading.

## What V5 should do now

V5 should preserve and use the valuable evaluation work already created:

- independently labeled real trading messages;
- difficult and previously missed message examples;
- context-dependent message sequences;
- replay and comparison tooling;
- contamination and duplicate checks;
- time-separated evaluation data;
- false-action and missed-action measurements;
- regression reports for changes made to V6.

The main question is now:

> Does the improved V6 local interpreter understand more real messages correctly without creating unsafe false actions?

## How V5 supports V6

The workflow should be:

```text
V6 local interpreter change
        ↓
V5 replay and scoring
        ↓
Compare against independent labels
        ↓
Check missed actions, false actions, ambiguity, and regressions
        ↓
Approve or reject the V6 change
```

V5 should be used whenever V6 changes:

- action interpretation;
- conditional or negation handling;
- context resolution;
- correction or continuation handling;
- position-dependent management language;
- runners or trim interpretation;
- target symbol or direction resolution.

## What is no longer the purpose of V5

These activities are no longer part of the normal project direction:

- promoting Qwen into the live bot;
- running Qwen as an always-on Shadow layer;
- maintaining Qwen pending states in the dashboard;
- relying on Ollama warm-up, leases, retries, or model queues;
- treating Qwen disagreement as a second operational decision;
- preparing Qwen for direct or indirect execution authority;
- using Qwen confirmation results as a reason to enable model-controlled trading.

The existing Qwen-specific code and locks may remain as historical research evidence, but they should not drive V6 design or normal operation.

## What should be retained

Keep the following because they remain useful even without Qwen:

- blind independent labels;
- message identity and stable case IDs;
- context and position-state snapshots;
- near-duplicate and contamination controls;
- time-based train/test separation;
- cluster-aware scoring;
- confusion matrices;
- false-execution detection;
- safe-abstention measurement;
- latency and review-rate measurement;
- immutable replay inputs and reports.

Qwen-generated suggestions may help locate examples, but they are not ground truth. Independent human labels and verified deterministic outcomes remain authoritative.

## V6 comparison targets

V5 should compare, in order:

1. The old V3/V4 parser behavior.
2. The improved V6 deterministic semantic interpreter.
3. Any later optional classifier or retrieval experiment, if one is ever added.

The first V6 goal is improvement over the old local bot without adding another runtime model dependency.

## Acceptance principles

A V6 interpretation change should be accepted only when:

- known correct actions do not regress;
- conditional, historical, negated, and ambiguous messages remain non-executable;
- new semantic coverage is supported by positive and negative tests;
- no critical false-action case is introduced in the reviewed corpus;
- previously missed messages are either correctly resolved or clearly held for review;
- sizing, position state, receipts, reconciliation, and execution gates remain unchanged;
- the result is reproducible from saved inputs.

V5 evidence supports V6 development and supervised SIM readiness. It does not authorize unattended SIM, paper trading, LIVE trading, or model-controlled execution.

## Recommended project boundary

```text
V6
    active local trading bot
    deterministic interpretation
    dashboard, Discord, SIM, and later Webull LIVE capability

V5
    offline replay
    independent labels
    regression scoring
    evidence and quality control

Qwen/Ollama
    optional historical research only
    not required by V6 runtime
```

## Bottom line

V5 still has a purpose, but it is now a test laboratory rather than a Qwen deployment pipeline.

Keep the data, labels, replay tools, and evaluation discipline. Retire the expectation that Qwen must become part of the operating bot. Use V5 to make sure V6 becomes smarter than V3 without becoming less safe or more difficult to operate.
