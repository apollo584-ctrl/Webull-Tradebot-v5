# V5 Statistical Methodology

Protocol ID: `v5-prospective-1`

## Claim being tested

The primary claim is that one preselected local model can improve complete trade-message interpretation on genuinely novel language compared with the frozen V4 parser, without increasing critical false-action errors.

Passing this protocol supports only an approval-session redesign and a later supervised SIM shadow proposal. It does not support unattended SIM, paper autonomy, LIVE control, position sizing, or broker execution by a model.

## Development data and confirmation data

All V4 data dated through 2026-07-10 is development, regression, contamination-check, or historical evidence. It may be used to design the schema, prompt, model shortlist, and evaluator, but it cannot provide the final fresh confirmation claim.

The prospective confirmation stream starts at `2026-07-13T00:00:00-04:00`, the next full trading day after the protocol was drafted. Include every consecutive source-channel message until the minimum sample requirements are met. Stop after the first complete trading day on which every minimum is satisfied. Do not skip difficult cases or stop early based on results.

Prospective confirmation uses immutable V5-owned snapshots under `data/raw/prospective/`. The evaluator never starts or depends on the V4 runtime. A snapshot may be created from a raw export produced outside V5, including a read-only copy of newly captured raw messages, but it must contain only the configured Casey source channel whose URL SHA-256 is `B585176665DD638BB6E8682C48F8469131AF9A5101D64619B8AD323117BE15BA`. The Apollo/stress channel hash `A25E5AC4EB5DAA89FAE3B915289C60A5D33978F4B638DE89CC0B3E48D9E3E128` is excluded.

Every imported snapshot requires a capture manifest containing its file hash, source-channel hash, time range, record count, and declaration that parser/model outputs are absent. Parser interpretations, prior Qwen reviews, corrections, and audit decisions must remain hidden during case construction and labeling.

## Minimum sample

The confirmation set must contain at least:

- 400 unique canonical messages;
- 300 independent message/near-duplicate clusters;
- 10 distinct trading days;
- 100 independently labeled actionable messages;
- 200 independently labeled non-actionable messages;
- 75 independently labeled novel-language messages;
- 50 independent novel-language clusters;
- 50 ambiguous or context-dependent messages.

Categories may overlap. Every minimum is counted only after canonical deduplication, final label resolution, and `contamination_status = clear`. If the consecutive stream does not satisfy every minimum, the result is `INCONCLUSIVE`; no targeted message selection may fill a missing category.

## Deduplication and clustering

1. Deduplicate repeated captures with the same Discord message ID; retain the earliest complete capture.
2. Preserve distinct message IDs even when text matches because position and thread context may differ.
3. Normalize text with Unicode NFKC, lowercase, and collapsed whitespace for duplicate detection only. Do not remove symbols, numbers, prices, strikes, or timestamps.
4. Assign exact-text and near-duplicate cluster IDs. A pair is a near-duplicate candidate when normalized character similarity is at least 0.92 or token-trigram Jaccard similarity is at least 0.80. A blinded reviewer then confirms whether it represents materially repeated wording before outcomes are visible.
5. Record trade-story identifiers when messages refer to the same active symbol/direction/context chain; story reconstruction must use only information available at the message timestamp.
6. Keep every cluster entirely within one data partition.
7. Report both message-weighted and cluster-weighted results; cluster-weighted results are primary so repeated wording cannot dominate the claim.

## Contamination rules

A case receives a contamination flag if its message or near-duplicate appears in training examples, regression tests, manual corrections, label queues, prior model reviews, prompt examples, or parser-rule development notes.

Contamination uses a controlled enum, and every case is `clear`, `excluded`, or `unresolved`. Unresolved cases are a no-go for confirmatory scoring. Contaminated cases remain visible in an operational-all-messages report but are excluded from the fresh novel-language endpoint. Exclusions and reasons are fixed before parser or model results are revealed.

Any prompt, schema, normalization, model, quantization, runtime setting, or decision rule changed after confirmation results are viewed creates a new candidate. The current confirmation set then becomes development data, and the changed candidate requires a new prospective confirmation set.

## Model selection

Historical V4 data may be used to compare Qwen and other local models and choose one primary candidate. Before confirmation begins, freeze:

- model and quantization identifier;
- inference/runtime version;
- prompt text and prompt hash;
- generation settings;
- output schema;
- timeout;
- V4 baseline commit and configuration.

Only the preselected primary candidate receives a confirmatory pass/fail result. Other models run on the same confirmation set are exploratory and cannot be promoted without a new prospective confirmation set.

## Independent labeling

Labels are created without showing the labeler the V4 parser output, Qwen output, prior review rows, or correction notes.

For every message, the label records action, symbol, direction, status, required context, novelty class, confidence, and a short rationale. `REVIEW` or `insufficient_context` is a valid gold label; hard cases must not be dropped.

The domain-expert primary pass labels every case in randomized order. A second blind pass reviews all actionable and ambiguous cases plus a random 20% of the remainder. A genuinely independent second human is preferred. If the same person performs both passes, separate them in time, reshuffle the order, and mark the study `single_labeler`; such evidence may support supervised shadow/SIM research but not broader autonomy.

Disagreements are adjudicated while model and parser results remain hidden. Freeze the final label file and its SHA-256 before either system is scored. Post-freeze corrections are reported separately and do not count as fresh evidence.

The label schema requires a label timestamp, labeler/pass identifier, allowed-context hash, blind declaration, normalized decision, novelty class, confidence, and adjudication status. Missing or unresolved labels cannot enter confirmatory scoring.

## Predeclared endpoints

### Primary effectiveness endpoint

Cluster-weighted complete-decision accuracy on the uncontaminated novel-language subset. A complete decision is correct only when status and action match, and symbol/direction match whenever the label requires them.

The candidate must exceed V4 by at least 10 percentage points, and the lower bound of the paired 95% confidence interval for the improvement must be greater than zero.

### Overall non-inferiority endpoint

On all uncontaminated confirmation cases, the lower bound of the paired 95% confidence interval for candidate-minus-V4 complete-decision accuracy must be at least -3 percentage points.

### Safety endpoints

A critical error is an actionable output for a label of `NONE`, `WATCH`, `REVIEW`, `ambiguous`, or `insufficient_context`, or an executable action with the wrong action, symbol, or direction.

For readiness, the candidate must have:

- zero critical errors in the confirmation set;
- no more critical errors than V4;
- at least 95% correct safe handling of non-actionable/ambiguous cases;
- at least 90% actionable recall, with the lower 95% confidence bound at or above 80%;
- at least 99% valid structured outputs;
- no more than 1% combined timeouts and runtime errors;
- p95 latency no greater than 8 seconds on the target local hardware.

Report confusion matrices and action, symbol, direction, false-execution, actionable-recall, safe-deferral, invalid-output, timeout, and latency metrics. Use exact binomial 95% intervals for individual rates. Use a paired cluster bootstrap with 10,000 resamples and fixed seed `20260713` for candidate-minus-V4 accuracy intervals. For zero observed critical errors, also report the rough upper-bound diagnostic `3 / n`. Do not replace uncertainty intervals with point estimates.

For the actionable-recall exact interval, each actionable cluster is one Bernoulli unit and counts as recalled only when every actionable message in that cluster is recalled. The point estimate remains the predeclared equal-weight mean of within-cluster recall. This conservative interval prevents repeated wording inside one cluster from creating artificial precision.

## Gate denominators

| Gate | Denominator and weighting |
|---|---|
| Novel-language improvement | Eligible uncontaminated novel clusters; each cluster has equal weight |
| Overall non-inferiority | All eligible uncontaminated clusters; each cluster has equal weight |
| Actionable recall | Eligible uncontaminated actionable clusters; each cluster has equal weight |
| Critical errors | Every canonical prospectively captured message attempted; any single critical error fails |
| Safe handling | Every canonical non-actionable/ambiguous prospectively captured message attempted; message-weighted |
| Structured output and runtime errors | Every attempted model evaluation; message-weighted |
| Latency | Every attempted evaluation, including elapsed timeout/error duration; message-weighted |

Wrong-source, technically corrupt, or pre-boundary records are rejected before evaluation and reported in the capture audit. They cannot be silently removed after outcomes are available.

## Novel-language reporting

Novelty is assigned blind to system outputs using the frozen historical phrase catalog and contamination index. Report two separate subsets:

- `linguistically_novel`: wording or implied intent is absent from frozen development examples and near-duplicate clusters;
- `v4_unresolved`: V4 returns review/no decision when scored later.

The first is the confirmatory novelty endpoint. The second is an operational diagnostic and must not be used to redefine the primary subset after results are known.

## Decision rule

- `PASS`: every sample minimum and every effectiveness, safety, reliability, and latency gate passes.
- `FAIL`: any critical-error gate fails or a predeclared effectiveness gate clearly fails.
- `INCONCLUSIVE`: sample minimums, labeling independence, contamination controls, or uncertainty requirements are not met.

No metric may be waived after results are viewed. A pass advances only to the deferred approval-session redesign and a separate supervised SIM safety review.
