# Discord Message Collection

This workspace is the shared local source of truth for collected Discord messages and confirmed human labels. It reads messages from a logged-in Microsoft Edge tab through Edge's local debug port and stores them in SQLite. It never types, posts, interprets trades, or connects to a broker.

The previous V5 evaluation code and holdout artifacts remain in place as historical evidence. They are not part of collection runtime.

## Setup

```powershell
python -m pip install -r requirements.txt
```

V6 is the operator for normal collection and conversational labeling. Its launcher calls this workspace's guarded collector; this workspace remains the storage and integrity owner.

The V5-owned collector can also be started directly for recovery or diagnosis:

```powershell
.\collect_messages.bat
```

It prompts for an inclusive beginning and ending date, opens the shared Edge profile, pauses for login/channel confirmation, runs the guarded sweep, retries safely after errors, and reports database counts. Enter the same date twice for a single-day sweep. Sign in to Discord once in that Edge profile; the profile remains local and ignored by Git.

The underlying command remains available for automation:

```powershell
$env:DISCORD_CHANNEL_URL = "https://discord.com/channels/SERVER_ID/CHANNEL_ID"
python discord_collector.py collect --date 2026-07-15
```

For a range from July 13 through July 15:

```powershell
python discord_collector.py collect --start-date 2026-07-13 --end-date 2026-07-15
```

The database is `data/messages.sqlite3`. Other projects should open it read-only and query the `messages` table:

```python
import sqlite3

db = sqlite3.connect(r"file:C:\Users\gregd\Codex Projects\Webull Tradebot v5\data\messages.sqlite3?mode=ro", uri=True)
rows = db.execute("SELECT timestamp, raw_text FROM messages ORDER BY timestamp").fetchall()
```

Confirmed human labels are append-only JSONL at `data/human_label_events.jsonl`. V6 records Greg's confirmations only through `human_labeling.py`; it reads both source files directly in read-only mode.

Existing JSONL captures can be imported without running Discord:

```powershell
python discord_collector.py import-jsonl data/raw/prospective/2026-07-13-final.jsonl data/raw/prospective/2026-07-14-capture.jsonl
```
