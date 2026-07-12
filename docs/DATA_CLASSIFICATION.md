# V5 Data Classification

This is a provenance classification, not the final holdout lock. Group 5 must set and freeze the exact time boundary and labeling protocol.

| Category | V4 sources | V5 use |
|---|---|---|
| Development/tuning | `training_examples.jsonl`, parser-derived interpretations, ordinary reviewed examples | Prompt/schema development and debugging only |
| Known regression | `candidate_regression_tests.csv` and promoted V4 cases | Regression diagnostics; never claim fresh independent evidence |
| Curated/excluded | `manual_label_groups.jsonl`, confirmed label queues, corrected examples, prior Qwen review rows | Exclude from final holdout; retain provenance for contamination checks |
| Candidate raw pool | `discord_raw_messages.jsonl` plus carefully matched context | Potential holdout source after deduplication and time-lock |
| Context/baseline lookup | `message_journal.jsonl`, `trade_audit.jsonl`, `discord_message_interpretations.jsonl` | Reconstruct allowed context and run V4 baseline separately; never send parser answer to Qwen |
| Prior model evidence | `shadow_ai_reviews.jsonl` and Qwen experiment reports | Historical reference only; not fresh evidence |

## Required separation

The V5 holdout must be created from a time-separated raw-message slice, then labeled independently before either V4 or any candidate model is scored. A message is not independent merely because it was not in the training file; prior curation, correction, parser tuning, or model review also counts as contamination.

V5 should store source paths, source hashes, message IDs, timestamps, deduplication decisions, and exclusion reasons in its manifest. Raw V4 files remain read-only.
