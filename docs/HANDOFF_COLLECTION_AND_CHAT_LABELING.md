# Discord Collection, Chat Labeling, and Shared Profile Handoff

> Superseded operating note: V6 is now the sole collection and labeling operator. V5 remains the command, database, deduplication, checkpoint, and label-event owner. Use `docs/HANDOFF.md` for the active workflow.

Last updated: 2026-07-15

## Outcome

Discord collection is now a standalone read-only service with one shared SQLite archive. V6 can read that archive offline for blind, chat-driven human labeling. Automatic V6 interpretations remain separate and hidden until human labels are confirmed.

## Collection workspace

Path: `C:\Users\gregd\Codex Projects\Webull Tradebot v5`

Despite the physical folder name, the project identity is now **Discord Message Collection**.

Runtime files:

- `discord_collector.py` — Edge DOM sweep, exact-channel guard, SQLite storage, JSONL import.
- `launch_discord.bat` — the same persistent authenticated Edge profile used by V6, normally on port `9227`.
- `collect_messages.bat` — V4-style daily operator wrapper with today's-date default, login pause, retry, and count reporting.
- `data/messages.sqlite3` — ignored shared archive; Discord message ID is the primary key.

Current archive after the latest V6 inbox sync:

- July 13: 19 messages.
- July 14: 38 messages. The 38th row came from the later V6 inbox and is not part of the frozen 37-message July 14 holdout.
- July 15: 20 messages.
- Total: 77 messages from one guarded Discord channel.

The V6 inbox import read 51 rows: 50 valid Discord rows and one invalid local dashboard fixture, which the channel guard rejected. A second import inserted zero rows, confirming deduplication.

Collection now detects the exact Casey tab on port `9227` first and legacy port `9225` second. It does not open a second browser when either port already exposes that channel. A historical sweep blocks while V6's listener PID belongs to a running process, so the continuous listener and scroll-back sweep do not compete for the same page.

The sweep accepts an inclusive beginning and ending date. The batch prompts for both dates; use the same date twice for a single day. The command-line equivalent is `discord_collector.py collect --start-date YYYY-MM-DD --end-date YYYY-MM-DD`. The legacy `--date YYYY-MM-DD` command remains compatible.

## Shared Edge profile and ports

Both workspaces use this authenticated Edge profile:

`C:\Users\gregd\Codex Projects\Webull Tradebot v6\local_state\edge_discord_profile_v6_readonly`

- `9227` is the standard V6/operator port.
- `9225` is supported as a legacy fallback when the exact Casey tab is already there.
- The same profile must not be opened on both ports at once because Edge locks its user-data directory.
- `collect_messages.bat` blocks if the V6 listener is running. For a historical sweep, stop V6 first, collect, then restart V6.
- If neither port has the exact Casey tab, the collector opens the shared profile on `9227`.
- The collector remains read-only toward Discord and writes only to the shared SQLite archive.

## V6 workspace

Path: `C:\Users\gregd\Codex Projects\Webull Tradebot v6`

Added files:

- `tradebot_v6/human_labeling.py` — read-only shared-message adapter, deterministic group suggestions, append-only label events, resume queue, and post-label comparison.
- `tests/test_human_labeling.py` — grouping, resume, separate provenance, and comparison checks.
- `docs/HANDOFF_CHAT_LABELING.md` — exact conversational operating procedure.

Human confirmations are stored beside the shared archive in ignored `data/human_label_events.jsonl`. V6's labeling helper points there by default, so collection and confirmed labels have one owning workspace. The file does not exist yet because no July 15 human label has been confirmed.

The existing uncommitted V6 replay-session changes in `app.py` and `tests/test_dashboard.py` belong to the prior V6 work and were preserved without modification by this phase.

## Chat workflow

This labeling process happens directly in this project's Codex chat. It is not a dashboard workflow and does not require a labeling UI with many options. Codex proposes groups, asks Greg to confirm or split them, and then reviews remaining messages one at a time.

1. Read a date's messages from SQLite using read-only mode.
2. Exclude messages already covered by saved human-label events.
3. In this Codex chat, show proposed groups using only raw wording; never show V6 automatic answers.
4. Ask Greg to confirm or split each group in chat.
5. Ask one conversational labeling question for a confirmed group.
6. Review remaining messages chronologically in chat, one at a time.
7. Save Greg's confirmed decision and rationale with timestamp and provenance.
8. Resume after interruptions by rebuilding the queue from the message database plus saved events.
9. Compare against V6 automatic history only after human labels are saved.

## Consumer contract for newer projects

The standalone handoff for another project is `docs/HANDOFF_TO_MESSAGE_CONSUMER_PROJECT.md`.

- Treat this collection workspace as authoritative for both files.
- Open `data/messages.sqlite3` with SQLite `mode=ro`.
- Read confirmed labels from `data/human_label_events.jsonl`; an absent file means no human labels have been confirmed yet.
- Match label events to source messages through each event's `message_ids` values.
- Do not collect Discord, relabel messages, write either source file, or copy this machinery into the consuming project.
- Keep automatic model output separate and compare it with confirmed labels only after loading both sources.

Decision contract:

- `OPEN`, `ADD`, `TRIM`, `SELL` → `actionable`, supported symbol, and `LONG` or `SHORT`.
- `WATCH`, `NONE` → `no_action`; symbol and direction are optional.
- `REVIEW` → `ambiguous` or `insufficient_context`; include only fields Greg establishes clearly.

## Verification

- Collector syntax check passed.
- Collector focused suite: `4 passed`.
- Live read-only port probe found the exact Casey channel on `9227`.
- V6 full suite: `93 passed, 68 subtests passed`.
- V6 compile check passed.
- Both workspaces passed `git diff --check` apart from normal Windows LF/CRLF notices.
- Shared-database before/after hash was unchanged by the V6 queue read.
- Real July 15 queue: 20 unlabeled messages, zero strict exact/near-text groups, 20 individual messages.
- All 20 July 15 message IDs have matching V6 automatic history records for later comparison.

## Boundaries and unresolved risks

- No Discord write, Qwen, Ollama, Webull, broker, paper, or LIVE path was added.
- Human labeling cannot modify the collector database, live V6 audit history, live SIM positions, or receipts.
- V6's live runtime still consumes its existing JSONL inbox. SQLite is currently the offline human-label source; replacing live intake would be a separate SIM-boundary phase requiring stronger review.
- July 15 is still in progress. Reimport the V6 inbox before labeling if additional Casey messages arrive.
- The collection folder has not been physically renamed.
- Nothing was staged, committed, pushed, or published during this work.
- One Edge user-data directory cannot safely run as two simultaneous Edge instances. Port `9227` is the standard; `9225` exists only as a compatibility fallback.

## Next exact step

If more July 15 messages are needed, run `C:\Users\gregd\Codex Projects\Webull Tradebot v6\STOP_V6_OPERATOR.bat`, then `C:\Users\gregd\Codex Projects\Webull Tradebot v5\collect_messages.bat`, and restart V6 with `START_V6_OPERATOR.bat`.

Then rebuild the July 15 queue and begin the blind chat pass. Since strict text similarity found no safe groups, first ask Greg whether any messages should be grouped by equivalent meaning; otherwise proceed chronologically one message at a time.

Recommended configuration: GPT-5.6 Sol, Medium reasoning, main thread only. Escalate to Sol High only if the work expands into live/SIM intake replacement or execution boundaries.
