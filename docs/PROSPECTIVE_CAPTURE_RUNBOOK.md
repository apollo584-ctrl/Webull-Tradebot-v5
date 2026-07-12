# V5 Prospective Capture Runbook

Use this on or after `2026-07-13 00:00 America/New_York`.

## Raw export requirements

The external export must be JSON Lines (`.jsonl`), one raw message per line. Each record may contain only:

```text
browser_time, event, has_everyone, message_id, page_title,
page_url, raw_text, timestamp
```

`page_url` must identify the configured Casey source channel. The importer excludes the Apollo/stress channel, other channels, malformed records, empty messages, and messages before the locked start time.

Do not include parser fields, model output, labels, expected answers, corrections, interpretations, or execution decisions. Keep the original message ID, message text, and timezone-aware timestamp unchanged.

## July 13 procedure

From the V5 folder:

```powershell
python scripts/import_prospective_snapshot.py <raw-export.jsonl> 2026-07-13-capture
python scripts/prepare_cases.py data/raw/prospective/2026-07-13-capture.jsonl data/holdout/cases.jsonl --capture-manifest data/holdout/captures/2026-07-13-capture.json
python scripts/review_clusters.py data/holdout/cases.jsonl data/holdout/cases.reviewed.jsonl
python scripts/create_label_queue.py data/holdout/cases.reviewed.jsonl data/labels/label-queue.jsonl
```

Review clusters before labeling. Confirm true near-duplicates; split cases that only look similar but require different interpretation. Do not delete hard cases.

Label the queue without opening V4 parser output, Qwen/model output, prior reviews, correction notes, or outcome information. Use `docs/LABELING_GUIDE.md`. When labels are complete, save the final file under `data/labels/`, then run:

```powershell
python scripts/lock_labels.py data/holdout/cases.reviewed.jsonl data/labels/labels.final.jsonl data/holdout/label.lock.json
python scripts/run_v4_baseline.py data/holdout/cases.reviewed.jsonl data/results/v4-confirmation.jsonl --label-lock data/holdout/label.lock.json
```

Stop if the importer reports no eligible Casey messages, the raw export contains unsupported fields, labels cannot be completed blind, or the protocol minimums cannot be met. Do not start Discord, Qwen, Webull, broker, SIM, or LIVE processes during capture and labeling.
