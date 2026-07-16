# Discord Message Collection Handoff

Last updated: 2026-07-15

## Current role

This workspace is now the standalone source of truth for read-only Discord collection and confirmed human labels. It has no Qwen, automatic trade interpretation, Webull, broker, SIM, paper, or LIVE responsibility.

The previous V5 evaluation implementation and July 13–14 holdout artifacts remain preserved as legacy evidence. They are not collection runtime.

## Runtime

- Collector: `discord_collector.py`
- Edge launcher: `launch_discord.bat`
- Daily operator workflow: `collect_messages.bat`
- Local database: `data/messages.sqlite3` (ignored by Git)
- Human label log: `data/human_label_events.jsonl` (ignored by Git; created on first confirmation)
- Required package: `websocket-client`
- Standard Edge debug port: `9227`; legacy `9225` is detected as a fallback
- Shared Edge profile: `C:\Users\gregd\Codex Projects\Webull Tradebot v6\local_state\edge_discord_profile_v6_readonly`
- Default timezone: `America/New_York`

The batch sweep prompts for an inclusive beginning and ending date in `MM-DD-YYYY` format. Use the same date for both prompts to collect one day. The launcher validates and converts those operator-facing dates to the command-line collector's existing internal `--start-date YYYY-MM-DD --end-date YYYY-MM-DD` format; the older single-day `--date` form remains supported.

The collector requires an exact `DISCORD_CHANNEL_URL` or `--channel-url`. The channel guard rejects every other Discord tab. Discord is read through the visible page DOM; the collector never posts or modifies messages.

SQLite uses the Discord message ID as the primary key. Repeated collection updates the existing row instead of creating a duplicate. Other projects can open the database with SQLite read-only mode.

## Legacy data

- July 13: 19 unique messages, labels locked.
- July 14: 37 unique messages, not labeled.
- Existing snapshots remain under `data/raw/prospective/`.
- Existing capture manifests remain under `data/holdout/captures/`.
- Do not commit raw captures, labels, browser profiles, or the SQLite database without explicit authorization.

## Current phase checks

- Imported the July 13–14 snapshots: 56 total rows (19 plus 37), one channel.
- Added the V4-style daily wrapper with today's-date default, login/channel pause, exact-channel guard, retry handling, and SQLite count reporting.
- Added support for V6 compound message IDs and passed three focused tests.
- Confirmed `START_V6_OPERATOR.bat` uses its read-only Edge profile on port `9227` and continuously captures Casey messages.
- Imported the V6 raw inbox into SQLite: 20 unique July 15 messages were added; one invalid local dashboard fixture was rejected.
- Current archive: 77 messages, one channel — July 13: 19, July 14: 38, July 15: 20.
- The extra July 14 row came from V6's later raw inbox rather than the frozen 37-message July 14 holdout.
- Unified collection and V6 on the same authenticated Edge profile. The collector prefers port `9227`, accepts an already-open exact Casey tab on legacy port `9225`, and refuses to sweep while the V6 listener PID is active.
- Shared-profile implementation handoff: `docs/HANDOFF_SHARED_DISCORD_PROFILE.md`.
- Centralized human-label ownership here; V6's labeling helper now defaults to this workspace's `data/human_label_events.jsonl`. No label file existed to migrate, and the focused labeling suite passed (`3 passed`).
- Consumer-project handoff: `docs/HANDOFF_TO_MESSAGE_CONSUMER_PROJECT.md`.

## Next exact step

If another historical sweep is needed, use V6's collection launcher; it stops at V5's guarded collector and authoritative database. Conversational labeling is also operated from V6 through V5-owned commands.

## Superseded cross-chat checkpoint

This earlier plan allowed either project chat to operate collection and labeling. It is retained only as history and is no longer active. V6 is now the sole operator; V5 continues to own commands, messages, labels, locks, deduplication, and operation history.

### Codex stability checkpoint

- The repeated desktop crash was traced to this Codex task's saved history, not to V5 code, Python, pytest, or `config.toml`.
- Four interrupted `exec` calls were saved without matching `custom_tool_call_output` records. Reloading or revalidating this task can make `codex_core::util` terminate the local app server with `Custom tool call output is missing for call id`.
- V5's root `AGENTS.md` is already project-only (818 bytes). V6's root `AGENTS.md` is also short and contains only its project gates and reference boundaries. Codex normally combines the global and project instruction files in the task prompt; that display is not duplicate files on disk.
- Do not manually edit Codex's internal session JSONL. Update the desktop app, open a fresh task in this V5 project, and have it read this handoff before verification.
- In the fresh task, use short one-shot checks and keep command output bounded. Do not resume verification in the damaged task.

V5 owns the commands and state for collection and conversational labeling. V6 is the sole operator and invokes those V5-owned commands; no operation state is stored in V6.

V5-owned runtime state:

- Messages: `data/messages.sqlite3`
- Human labels and corrections: `data/human_label_events.jsonl`
- Shared operation lock: `data/operation.lock`
- Per-command labeling lock: `data/operation_step.lock`
- Append-only run ledger: `data/operation_runs.jsonl`

V5-owned commands:

- `message_operations.py status` reports the active operation and completed collection ranges.
- `discord_collector.py collect ...` holds the operation lock for collection and records completion or failure in the ledger; V6 is recorded as the operator.
- A collection range overlapping a completed range is blocked unless Greg explicitly confirms refresh; the command then receives `--confirm-refresh`.
- `human_labeling.py start --start-date ... --end-date ...` starts a persistent V6-operated chat-labeling session and returns its operation ID.
- `VERIFY_SHARED_OPERATIONS.bat` runs the short standard-library self-check in `verify_shared_operations.py` and writes output to ignored `data/shared_operations_verify.log`, keeping Codex tool output short.
- `human_labeling.py queue --operation-id ...` rebuilds the queue from SQLite and excludes message IDs already covered by effective confirmed labels.
- `record-group`, `record-label`, `correct-label`, `pause`, and `finish` all require the active labeling operation ID.
- `record-label` refuses an already-labeled message. Relabeling requires `correct-label --corrects-event-id <current-event-id>`, producing an append-only `label_correction` event.

Important behavior:

- Only one collection or labeling session may be active.
- Labeling remains conversational in Codex chat; no labeling dashboard was added.
- Discord remains read-only and the exact-channel guard remains in place.
- SQLite still uses Discord message ID as the primary key, preserving deduplication.
- An interrupted labeling session remains visible through `message_operations.py status`; another chat can continue using the reported operation ID.

Files added or changed for this checkpoint:

- Added `operation_control.py`, `message_operations.py`, and V5-owned `human_labeling.py`.
- Added focused checks in `tests/test_operation_control.py` and `tests/test_human_labeling.py`.
- Integrated locking and ledger recording into `discord_collector.py` and refresh confirmation into `collect_messages.bat`.
- Updated `.gitignore` so lock, ledger, and label runtime files remain local.

Verification state:

- All four Python command files compiled successfully with direct `compile()` checks.
- The direct operation-control assertions completed and produced the expected started/completed and started/paused test ledger events before the Codex app lost the tool response.
- `VERIFY_SHARED_OPERATIONS.bat` was run outside Codex on 2026-07-15 at 17:11 local time. Its log contains `shared-operations=ok`.
- The shared lock, completed-range protection, label resume behavior, correction events, Discord read-only guard, and message-ID deduplication are verified for this checkpoint.
- Codex's `Custom tool call output is missing for call id` crashes remain an app/tool-transport issue. They do not indicate a V5 implementation failure.

Next exact step: begin a collection or conversational labeling session from V6. V5 remains the owner of messages, labels, locks, and operation history.

## Collection and labeling stability refactor — Phase 2 implementation

Approved 2026-07-15. Verification is pending.

- Collection now requires server `988680941406912512` and channel `1026241985444593724` at every input boundary.
- Inclusive date ranges remain interpreted in `America/New_York` unless an explicit timezone is supplied.
- Message storage is insert-only and transaction-backed. Existing logical Discord IDs, including plain/legacy compound aliases, are no-ops and existing archive rows are not rewritten.
- A sweep starts from the newest channel position and can complete only after crossing the requested start boundary or proving channel-history top. A stall or round limit before that point fails incomplete.
- Each durably committed batch is followed by an append-only checkpoint event. Retry safely replays the range and relies on logical-ID deduplication.
- SQLite is closed before the completed operation event is recorded.
- Operation and label JSONL updates preserve prior bytes using a flushed temporary file plus atomic replacement. A partial existing JSONL file is rejected without truncation.
- Conversational labeling defaults to 5 messages, accepts 5–10, preserves grouping/correction behavior, and returns only the next bounded context batch.

Files changed in this phase: `.gitignore`, `discord_collector.py`, `operation_control.py`, `human_labeling.py`, `verify_shared_operations.py`, the three focused test files, and this handoff.

Authority remains unchanged: `data/messages.sqlite3` owns historical messages and `data/human_label_events.jsonl` owns confirmed human labels. `data/operation_runs.jsonl` is append-only operational state; lock and temporary files are derived state. No runtime data, legacy evaluation file, V6 file, dependency, commit, or remote was changed.

Tests run: none yet. Next exact step: run only the approved bounded compile check and three focused test files using temporary data.

## V6-operated collection and labeling contract

- V6 is the sole operator for historical sweeps and conversational labeling.
- V5 remains the implementation and integrity owner for collection, SQLite storage, Discord-ID deduplication, checkpoints, locks, and append-only human-label events.
- V6 invokes V5-owned commands and never edits either authoritative data file directly.
- The old cross-chat caller choice was removed; operation events identify V6 as the operator.
- The V5 scroller now supports Discord's reversed message list by allowing negative `scrollTop` values and retaining the V4-style fallback scroller discovery.
- V4 remains read-only and is not a runtime dependency.
- No archive row, label event, browser session, or Discord state was changed during implementation.
- Verification: the compact standard-library verifier passed all `17` stability checks after adding explicit reversed-scroll assertions. V6's focused message-consumer suite passed (`3 passed`).
- The ordinary V5 pytest attempt was not accepted as a result because Windows denied pytest access to its generated temporary directory. No test process or named scratch file remained afterward.
- The authoritative SQLite SHA-256 remains `BA9FA78EC6ADBE9DD743D6E9A67B86AAEC13A62AD6DAAEB3DB6D686884DE71EB`; the human-label event file remains absent.
- Files changed for this workflow: `discord_collector.py`, `collect_messages.bat`, `human_labeling.py`, `message_operations.py`, `verify_shared_operations.py`, `tests/test_discord_collector.py`, `AGENTS.md`, `README.md`, the active handoff, and superseded workflow notices. Existing unrelated V5 worktree changes were preserved.
- No commit or push was performed.
- Next manual step: from V6, run one controlled historical sweep through `COLLECT_MESSAGES.bat`, then begin one 5-message conversational labeling batch.

## Controlled July 15 sweep — 2026-07-15

- The Edge-only V6 helper verified the exact Casey channel on port `9227`.
- Corrected V5 target discovery to use Edge's `/json/list` page-target endpoint.
- The July 15 inclusive sweep completed successfully: `20` messages read, `0` inserted, `20` duplicates, archive total `86`.
- The authoritative database hash remained `BA9FA78EC6ADBE9DD743D6E9A67B86AAEC13A62AD6DAAEB3DB6D686884DE71EB`.
- No Discord write, listener start, label write, or SIM/dashboard action occurred.
