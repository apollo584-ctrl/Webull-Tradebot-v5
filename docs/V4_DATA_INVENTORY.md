# V4 Data Inventory

Read-only inventory completed 2026-07-11 from:

`C:\Users\gregd\Codex Projects\Webull Tradebot v4 Qwen`

V4 was not edited, run, or copied wholesale.

## Authoritative source files

| File | Records | Time range | Role | SHA-256 |
|---|---:|---|---|---|
| `Active Training/data/training_examples.jsonl` | 343 | 2026-05-28 to 2026-06-04 | Existing tuned/training examples; not fresh holdout | `458B5E321824C7485C1C5FDE5BBEDF4B062B19A5A2EF2E093BA4E1C235597EA9` |
| `Active Training/data/manual_label_groups.jsonl` | 29 | reviewed 2026-06-04 to 2026-06-24 | Curated/manual labels; exclude from fresh evidence | `8D72137E1D77A4153F09ACE224C6AED73692ACB38B8D6F479BCC02DD1330B6F5` |
| `Active Training/data/candidate_regression_tests.csv` | 343 | 2026-05-28 to 2026-06-04 | Known regression set; development/evaluation diagnostics only | `A735333A7F913A3C06EE1E4F9DF9ADBE32AD9F1CA215C73B164C120380CD8AC1` |
| `BOT_PROJECT/data/discord_raw_messages.jsonl` | 1,879 | 2026-06-17 to 2026-07-10 | Primary raw message source; candidate pool pending time-lock | `40259A4B3106282F3D4A231B93C883E5791ACDB39A00DF381BE6A7753BBF1E72` |
| `BOT_PROJECT/data/discord_message_interpretations.jsonl` | 1,783 | 2026-06-17 to 2026-07-10 | Parser/stress outputs; comparison context, not blind input | `7A06978AA334336CC9D2DA869E221586216E3598C36B1B79FEC953CD91D79B9E` |
| `BOT_PROJECT/data/message_journal.jsonl` | 8,327 | 2026-06-17 to 2026-07-10 | Mixed runtime journal; provenance/context lookup only | `81DDB49881991471049D22C8393965F9701AFC10D64FA406056C0B7274FE0ED0` |
| `BOT_PROJECT/data/trade_audit.jsonl` | 1,071 | runtime records | Parser/trading decisions; comparison baseline source only | `028736440E4ACA2DE5F53F08549FCD6A8BB1A96941ADBAFBDD1C8302E601EAC1` |
| `BOT_PROJECT/data/shadow_ai_reviews.jsonl` | 977 | 2026-06-17 to 2026-07-10 | Prior Qwen reviews; contaminated for fresh model evidence | `B159CD13017C77DEA95B46C523FE3CB5FB0728CA08ECB2B27A53C96128671239` |

## Findings

- `discord_raw_messages.jsonl` is the best candidate source for novel-language evaluation because it preserves message IDs, text, and timestamps.
- The raw archive has 1,235 unique message IDs across 1,879 records; duplicate records require deterministic deduplication rules.
- `discord_message_interpretations.jsonl` has parser/stress decisions and must not be passed to Qwen.
- `shadow_ai_reviews.jsonl` contains prior Qwen output and must not count as fresh model evidence.
- `message_journal.jsonl` contains mixed events and six malformed JSON lines; it is not a clean dataset source.
- Generated test/runtime folders under `BOT_PROJECT/data` are excluded from the source corpus unless a later provenance review proves a specific file useful.
