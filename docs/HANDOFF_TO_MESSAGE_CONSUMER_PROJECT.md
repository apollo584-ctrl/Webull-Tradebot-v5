# Handoff: Consumer Project Using Discord Messages and Human Labels

> Superseded operating note: V6 is now the sole collection and labeling operator. V5 still owns all commands and authoritative data. Any older instruction below that assigns operation to either project chat is historical; use `docs/HANDOFF.md` for the active contract.

Last updated: 2026-07-15

## Purpose

The Discord Message Collection workspace is the source of truth for collected Discord messages and confirmed human labels. A newer project may consume those records for analysis or model work without owning Discord collection, browser control, or labeling storage.

## Source workspace

Workspace:

`C:\Users\gregd\Codex Projects\Webull Tradebot v5`

Authoritative files:

- Messages: `C:\Users\gregd\Codex Projects\Webull Tradebot v5\data\messages.sqlite3`
- Confirmed labels: `C:\Users\gregd\Codex Projects\Webull Tradebot v5\data\human_label_events.jsonl`

The label file may not exist yet. That means no human label has been confirmed; it is not an error. It will be created when the first label is saved.

## How to consume the messages

Open the SQLite database read-only:

```python
import sqlite3

database = sqlite3.connect(
    r"file:C:\Users\gregd\Codex Projects\Webull Tradebot v5\data\messages.sqlite3?mode=ro",
    uri=True,
)
messages = database.execute(
    "SELECT message_id, timestamp, author_id, author_name, raw_text, page_url "
    "FROM messages ORDER BY timestamp, message_id"
).fetchall()
database.close()
```

The `message_id` is the stable message identity. The database is guarded to one Discord server/channel and is updated by the collection workflow with deduplication.

## How to consume confirmed labels

Read `human_label_events.jsonl` as append-only JSONL. Each line is one event:

- `group_decision` records whether equivalent-looking messages were confirmed as a group or split apart.
- `label_confirmed` records Greg's confirmed human decision and includes `message_ids`, `decision`, `rationale`, `confirmed_by`, and `confirmed_at`.

Use `message_ids` to join labels to the SQLite `messages.message_id` values. A message is human-labeled when its ID appears in a `label_confirmed` event. Group decisions alone are not trade labels.

The decision contract is:

- `OPEN`, `ADD`, `TRIM`, `SELL`: `status=actionable`, supported symbol, and `LONG` or `SHORT`.
- `WATCH`, `NONE`: `status=no_action`; symbol and direction are optional.
- `REVIEW`: `status=ambiguous` or `insufficient_context`; include only information Greg explicitly established.

Human labels are the ground truth for evaluation. V6 automatic history may be compared against them after labeling, but automatic interpretations must not be presented as human labels or silently replace them.

## Ownership and boundaries

The collection workspace owns both source files. The newer project must:

- read the SQLite database with `mode=ro`;
- read the label JSONL without rewriting it;
- preserve message IDs and label provenance;
- tolerate an absent or partially completed label file;
- keep its model output and derived data separate from the source files.

The newer project must not:

- launch Discord or Edge;
- run a Discord sweep or V6 listener;
- modify `messages.sqlite3`;
- modify, rewrite, or duplicate `human_label_events.jsonl`;
- relabel messages automatically and call those decisions human-confirmed;
- add broker, Webull, SIM, paper, or LIVE behavior as part of this integration.

## Collection and labeling lifecycle

Historical collection is performed here through `collect_messages.bat`. Human labeling is performed directly in this project's Codex chat, not in a dashboard or a large labeling-options UI. V6's labeling helper supports the queue and persistence, but its default label destination is now this workspace's `data\human_label_events.jsonl`.

The normal operating order is:

1. Stop the V6 listener before a historical sweep.
2. Collect or refresh messages here.
3. In this project's Codex chat, review proposed duplicate/equivalent groups using the original message wording.
4. Confirm or split groups in chat, then label remaining messages conversationally one at a time when needed.
5. Save confirmed labels to the centralized JSONL file.
6. Have the newer project read the refreshed database and confirmed labels.

The shared Edge profile is separate from the consumer data contract. It is used only for collection and V6 operation:

`C:\Users\gregd\Codex Projects\Webull Tradebot v6\local_state\edge_discord_profile_v6_readonly`

Port `9227` is standard and `9225` is a legacy fallback. The profile must not be opened on both ports simultaneously.

## Copy-paste instruction for the newer project

> Use `C:\Users\gregd\Codex Projects\Webull Tradebot v5` as the authoritative Discord message and human-label source.
>
> Read `docs\HANDOFF_TO_MESSAGE_CONSUMER_PROJECT.md` first. Read messages from `data\messages.sqlite3` using SQLite `mode=ro`. Read confirmed human labels from `data\human_label_events.jsonl` if it exists. Join labels to messages by `message_id` / `message_ids`.
>
> Human labeling happens in this project's Codex chat: Codex proposes groups, asks Greg to confirm or split them, then asks about remaining messages one at a time. Do not replace this with a dashboard or a large set of labeling controls.
>
> Treat only `label_confirmed` events as confirmed human decisions. Keep automatic model output separate and compare it with human labels only after loading both. Do not collect Discord messages, launch Edge, run the V6 listener, modify either source file, or create a second labeling database. The newer project's scope is only to consume these records for its own analysis or model workflow.

## Next exact step

The newer project should point its read-only data adapter at the two absolute paths above, confirm that it handles an absent label file, and wait for confirmed labels before evaluating model agreement.
