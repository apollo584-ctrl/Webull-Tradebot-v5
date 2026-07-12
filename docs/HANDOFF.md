# V5 Handoff - Blind Qwen Evaluation

Last updated: 2026-07-11

## Active Workspace

- V5 directory: `C:\Users\gregd\Codex Projects\Webull Tradebot v5`
- V4 stable reference: `C:\Users\gregd\Codex Projects\Webull Tradebot v4 Qwen`
- V4 tag: `v4-stable-2026-07-11`
- V4 baseline commit: `a19db80`
- V5 Git repository baseline is on `main`; the working branch is used for reviewed changes.
- V4 GitHub reference: `https://github.com/apollo584-ctrl/Webull-Trade-Bot-v4`.
- V5 GitHub remote: `https://github.com/apollo584-ctrl/Webull-Tradebot-v5`.

V4 is the stable, read-only baseline. V5 must not edit or run V4.

## Why V5 Exists

V4 uses Qwen as a constrained reviewer. The local parser supplies a trusted decision, Qwen sees that decision, and deterministic execution gates remain in charge. That is safe but does not prove independent natural-language understanding.

V5 will test whether Qwen can interpret Discord trade messages from message text, recent trade-story context, timestamps, and position state without receiving the local parser's answer.

V5 is a scientific readiness test, not a replacement trading bot. Qwen is not considered better merely because it disagrees with the parser; Qwen and the V4 parser must both be compared against independent labels from an unseen, time-separated holdout set.

## V4 Baseline Preserved

- Final V4 regression: `785 passed`.
- Qwen remains SIM-only and cannot control LIVE.
- Exact Discord-message evidence matching is required for the supervised SIM candidate.
- Missing, stale, malformed, or mismatched evidence falls back to local rules.
- V4 authorization reports now require timezone-aware timestamps no more than 24 hours old.
- Real Webull/LIVE behavior remains unproven.
- Deterministic safety and execution gates remain outside Qwen.
- Curated corrections and hand-picked examples are not fresh independent evidence.
- The deferred approval-session lifecycle must be redesigned before broader SIM testing.

## Deferred V4 Risk

The supervised Qwen approval session can renew its 30-minute expiration while the dashboard remains active. Leave it disarmed when unattended. Redesign that approval lifecycle in V5 before any broader SIM experiment.

## V5 Scope

1. Preserve the V4 baseline and create V5-specific project instructions and runtime separation before execution work.
2. Build a blind-Qwen shadow evaluator that does not receive the local parser's action, symbol, direction, or executable/review classification.
3. Create an unseen, time-separated, independently labeled holdout set.
4. Score both Qwen and the V4 parser against the independent labels: action, symbol, direction, context, ambiguity handling, false executions, misses, and latency.
5. Benchmark candidate local models, starting with the configured Qwen baseline, using unseen messages.
6. Redesign the deferred approval-session lifecycle before broader SIM testing.
7. Promote only through supervised SIM stages if the evidence supports it.

## Explicit No-Go Boundaries

- No unattended SIM autonomy.
- No paper autonomy.
- No LIVE Qwen control.
- No broker or Webull connection during the evaluation phase.
- No claim that Qwen has replaced the parser until it passes an independent holdout evaluation without the local answer in its prompt.

## Model Routing

- Documentation and setup checks: GPT-5.4-mini, Light.
- Blind-evaluation design, statistical validity, and executable safety boundaries: GPT-5.6 Sol, High.
- Extra High is not the default; use it only if Sol High leaves a specific unresolved correctness or methodology question.
- Never claim the active model or reasoning level unless platform metadata verifies it.

## Exact Next Step

In a fresh V5 Codex chat, read the global rules, this handoff, and the copy-ready `V5_SETUP_MESSAGE.txt`. Confirm the V5 path, assess the first setup task, and wait for Greg's explicit “go.”

## Setup Checkpoint

- Files added: root `AGENTS.md`, `.gitignore`, `README.md`, V5 evaluation plan, package placeholder, and separated data/script/test folders.
- Checks run: Git root, branch, and working-tree status verified.
- Unresolved risk: Git history is empty; create the first commit only after reviewing the staged project files.
- Unresolved choice: V5 GitHub remote is not configured because no dedicated V5 repository was identified.
- Next exact step: review the completed Groups 1–4 artifacts, then begin Group 5 statistical methodology with GPT-5.6 Sol, High.
- Recommended configuration: GPT-5.6 Sol, High for blind-evaluation design and executable safety-boundary decisions.

## Groups 1–4 Checkpoint

- Completed read-only inventory of V4 training, raw Discord, parser interpretation, journal, audit, label, regression, and prior Qwen files.
- Added `data/source_manifest.json` with record counts, time ranges, categories, and SHA-256 hashes.
- Classified development, known regression, curated/excluded, candidate raw, baseline-context, and prior-model data.
- Added the normalized decision contract and JSON schema under `docs/EVALUATION_CONTRACT.md` and `schemas/evaluation_record.schema.json`.
- No V4 files were edited, run, or copied wholesale. No Discord, Qwen, Webull, broker, SIM, or LIVE runtime was started.
- Open methodological decisions for Group 5: exact time boundary, deduplication policy, independent labeling workflow, contamination audit, and numeric pass thresholds.

## Group 5 Checkpoint

- Locked protocol `v5-prospective-1` at `2026-07-11T22:54:19-04:00`; prospective confirmation starts `2026-07-13T00:00:00-04:00`.
- All V4 data through 2026-07-10 is development/historical evidence, not final fresh confirmation evidence.
- Prospective data must enter as immutable V5-owned raw snapshots from the configured Casey source-channel hash; the Apollo/stress channel is excluded.
- Minimums: 400 canonical messages, 300 clusters, 10 trading days, 100 actionable, 200 non-actionable, 75 linguistically novel, 50 novel clusters, and 50 ambiguous/context-dependent cases. Counts require final labels and clear contamination status.
- Promotion requires novel-language improvement, overall non-inferiority, zero critical errors, safe handling, actionable recall, structured-output reliability, runtime reliability, and latency gates with predeclared uncertainty intervals.
- Added blind labeling, capture-manifest, and evaluation schemas plus a runnable protocol-hash verifier.
- Risk review completed and its source, denominator, label-audit, valid-combination, and latency blockers were resolved before lock.
- Checks run: protocol hashes verified; all JSON parsed; valid schema examples passed; contradictory action/status examples were rejected.
- No V4 runtime, Discord, model, parser, Webull, broker, SIM, or LIVE process was started.
- Open state: no prospective snapshot, labels, prompt, primary model candidate, or V4 baseline result has been locked yet.
- Next exact step: Group 6 implements the offline importer, canonical deduplication/clustering, blind request builder, validators, and saved-response evaluator against the locked protocol.
- Recommended configuration for Group 6: GPT-5.6 Luna, Medium. If the current verified model already meets or exceeds this, do not switch downward merely for a short continuation.

## Group 6 Checkpoint

- Added offline V5 core under `src/v5_eval/`: raw JSONL loading, source validation, canonical message deduplication, connected-component near-duplicate clustering, blind request construction, decision validation, and model-output normalization.
- Added saved-response scoring with clear-contamination eligibility, cluster-weighted accuracy, critical-error detection, actionable recall, safe handling, structured-output/runtime rates, p95 latency, and deterministic paired cluster bootstrap.
- Added `scripts/prepare_cases.py` and `scripts/score_saved_responses.py`; neither calls a model or runtime.
- Added seven focused stdlib tests covering deduplication, clustering, blind-field exclusion, source verification, action/status validation, safe deferral, invalid-output denominators, and scoring.
- Checks run: 7 tests passed, Python compile check passed, protocol lock verified.
- Review findings fixed: safe deferrals are not critical errors, invalid outputs remain in accuracy denominators, saved timeout/error statuses are preserved, source verification is enforced, labels and cluster review status gate eligibility, and capture manifests are matched by path/hash/count.
- No V4 runtime, Discord, Qwen, Webull, broker, SIM, or LIVE process was started.
- Next exact step: Group 7 runs the V4 parser separately against saved labeled cases and produces the frozen comparison baseline; do not run prospective confirmation yet.
- Recommended configuration for Group 7: GPT-5.6 Sol, High if the baseline/scoring result will control promotion; otherwise keep the current adequate model for the small mechanical run.

## Group 7 Checkpoint

- Frozen raw-text parser comparator: `v4-raw-text-parser-a19db80`, tag `v4-stable-2026-07-11`, commit `a19db806a744bb613985d967a47bca828183cc95`.
- The adapter imports only V4 `SignalParser`; it does not import the trading service, dashboard, Discord, Webull, broker, listener, NLP model, or runtime-state modules.
- V4 source verification requires the exact commit, clean tracked parser package, no untracked package files, locked dependency hashes, and frozen ticker corrections.
- Parser outputs are normalized into the V5 decision contract. Non-dispatchable output maps to `NONE`; parser actions without symbol/direction map to safe review.
- Confirmatory baseline runs require a pre-existing independent-label lock with `outcomes_viewed=false`, approved V5 case/label paths, and matching case and label hashes.
- Scoring now reports candidate and V4 critical errors, false-execution rates, safe handling, actionable recall, exact accuracy, and paired cluster uncertainty on the same labels.
- Historical development-only diagnostic completed on 343 curated V4 regression rows: action match `86.0%`, symbol match `61.5%`, direction match `61.5%`. These are parser-field reproducibility diagnostics, not independent performance evidence.
- Added `docs/V4_BASELINE.md` to distinguish the raw-text parser comparator from the future full V4 operational comparator that uses position/timeline/runtime context.
- Checks run: 10 tests passed, Python compile check passed, protocol lock verified, development baseline completed, and risk-review findings resolved.
- No dashboard, Discord, Qwen, Webull, broker, SIM, or LIVE process was started. V4 remained read-only.
- Remaining blocker: prospective confirmation has not started and no independently labeled holdout exists, so the final Group 7 confirmation baseline cannot be produced yet.
- Next exact step: after prospective Casey snapshots begin on 2026-07-13, import consecutive raw messages, confirm clusters, complete blind labels, and freeze the label lock. Then run the frozen Group 7 baseline followed by Group 8 model benchmarking.

## Pre-July13 Checkpoint

- Completed the offline preparation needed before prospective collection: immutable raw-snapshot import, source/time-boundary filtering, capture audit counters, canonicalization, recent-message context, cluster confirmation, randomized blind-label queue creation, strict label validation, and exact-coverage label locking.
- Added `scripts/import_prospective_snapshot.py`, `scripts/review_clusters.py`, `scripts/create_label_queue.py`, and `scripts/lock_labels.py`.
- Preserved the methodological boundaries: Qwen receives no V4 parser answer; deterministic safety and execution gates remain outside Qwen; curated corrections are not fresh evidence; V4 is a separate comparison baseline; approval-session redesign remains deferred before broader SIM testing.
- Checks run: 11 focused tests passed, Python compilation passed, and `scripts/verify_protocol.ps1` passed.
- No prospective July 13 data exists yet. The importer intentionally refuses to create a confirmation set from pre-boundary historical data; final independent labels, label lock, V4 confirmation baseline, and Qwen benchmark must wait for the prospective window.
- Exact next step on July 13: import a V5-owned raw snapshot, prepare cases, review or split clusters, create the blind queue, complete labels without viewing outcomes, lock labels, run the frozen V4 baseline, then begin model benchmarking.
- Recommended configuration for this preparation: GPT-5.6 Luna, Medium. A final promotion or go/no-go statistical review should be routed to GPT-5.6 Sol, High.

## July13 Readiness Checkpoint

- Added `docs/PROSPECTIVE_CAPTURE_RUNBOOK.md` with the raw-export contract, blind-labeling rules, July 13 commands, and stop conditions.
- Reused the existing importer and validators; no new exporter, runtime, broker integration, or model launcher was added.
- Checks run: documentation review completed; the existing 11-test, compile, and protocol-lock checks remain the latest code verification.
- Remaining external dependency: obtain a raw Casey JSONL export beginning at or after the locked confirmation boundary. Do not pre-stage labels or model outputs.
- Next exact step: on July 13, run the importer from the V5 folder and retain its capture manifest with the audit counts.

## Groups 1–2 Fix Checkpoint

- Group 1 corrected the July 13 label-lock command and removed stale setup-only GitHub text from the V5 README and handoff.
- Group 2 now requires strict novelty/context label fields, validates complete capture manifests, binds scoring to the exact locked cases and labels, and permits schema-valid null decisions for invalid model outputs.
- Checks run: 13 focused tests passed, Python compilation passed, protocol lock verified, CLI help checks passed, and `git diff --check` passed.
- Remaining blockers: contamination clearance, candidate/implementation freeze, clustering-method alignment, and complete statistical promotion gates remain Group 3–5 work.
- Next exact step: Group 3, GPT-5.6 Sol with High reasoning, for contamination and candidate-freeze controls.

## Groups 3–5 Fix Checkpoint

- Added auditable contamination decisions bound to the frozen source-manifest hash; unresolved or provenance-free cases cannot enter the label queue or label lock.
- Aligned near-duplicate matching with token-trigram Jaccard and changed cluster splits to preserve reviewer-declared subgroups without inflating every case into an independent cluster.
- Added candidate lock creation and verification for the explicit model, quantization, runtime/version, prompt, model-only output schema, generation settings, timeout, implementation files, and saved-response identity.
- Bound confirmation scoring to exact locked cases, labels, candidate identity, and separately generated frozen V4 baseline results.
- Added exact binomial intervals, candidate/V4 field metrics and confusion matrices, paired overall/novel cluster intervals, denominator checks, sample minimums, and explicit `PASS`, `FAIL`, or `INCONCLUSIVE` output.
- Protocol lock now pins implementation commit `19f764565f57b0c40e4211804f79c161d8f17250` and every tracked evaluator, script, schema, contract, protocol, source-manifest, and V4-baseline lock file.
- Checks run: 21 focused tests passed, Python compilation passed, JSON parsing passed, candidate-lock dry run passed, CLI help checks passed, and protocol lock verified.
- Independent risk review found no P0 issue. Its model-schema bypass, contamination-provenance bypass, and cluster-rerun regression findings were fixed before final lock.
- No Discord, Qwen, Webull, broker, SIM, paper, or LIVE runtime was started. V4 remained read-only.
- Remaining blocker: the actual primary model/configuration and prompt have not been chosen, so `primary_candidate_locked` remains `false` and official prospective confirmation must not start.
- Next exact step: choose and commit one candidate configuration and prompt, run `scripts/lock_candidate.py`, verify the protocol, and commit the resulting candidate/protocol lock updates before collecting the first official confirmation message.

## Main-branch integration checkpoint (2026-07-12)

- PR #2 was merged into V5 `main` at commit `697f553569f96bc7a0ddb818d672483252bbca37`.
- The protocol lock now pins that merged commit so ancestry verification remains valid after the squash merge.
- Checks run from `main`: 21 focused tests passed, Python compilation passed, and the protocol verifier passed after the metadata correction.
- No candidate was selected or frozen. The remaining blocker is the explicit primary model/configuration and prompt choice.
- Next exact step: route candidate selection and freeze to GPT-5.6 Sol with High reasoning, then verify the locked protocol before official prospective collection.
