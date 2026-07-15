from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from operation_control import OperationBusy, OperationStore


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "messages.sqlite3"
EXPECTED_GUILD_ID = "988680941406912512"
EXPECTED_CHANNEL_ID = "1026241985444593724"
DISCORD_EPOCH_MS = 1420070400000
CHANNEL_RE = re.compile(r"^https://(?:www\.)?discord\.com/channels/(\d+)/(\d+)(?:[/?#].*)?$")
SNOWFLAKE_RE = re.compile(r"(\d{16,})")


def channel_ids(url: str) -> tuple[str, str]:
    match = CHANNEL_RE.fullmatch(str(url).strip())
    if not match:
        raise ValueError("channel URL must be https://discord.com/channels/<server>/<channel>")
    return match.group(1), match.group(2)


def same_channel(left: str, right: str) -> bool:
    try:
        return channel_ids(left) == channel_ids(right)
    except ValueError:
        return False


def require_expected_channel(url: str) -> tuple[str, str]:
    ids = channel_ids(url)
    if ids != (EXPECTED_GUILD_ID, EXPECTED_CHANNEL_ID):
        raise ValueError(f"expected Discord server {EXPECTED_GUILD_ID} and channel {EXPECTED_CHANNEL_ID}")
    return ids


def logical_message_id(value: object) -> str:
    matches = SNOWFLAKE_RE.findall(str(value))
    if not matches:
        raise ValueError("message ID must contain an immutable Discord snowflake")
    return matches[-1]


def snowflake_timestamp(message_id: str) -> str:
    try:
        milliseconds = (int(logical_message_id(message_id)) >> 22) + DISCORD_EPOCH_MS
        return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat(timespec="milliseconds")
    except (ValueError, OSError, OverflowError):
        return ""


def message_date(timestamp: str, timezone_name: str) -> date | None:
    raw = str(timestamp or "").strip().replace("Z", "+00:00")
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(timezone_name))
        return value.astimezone(ZoneInfo(timezone_name)).date()
    except (ValueError, KeyError):
        return None


def open_database(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            guild_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            author_id TEXT,
            author_name TEXT,
            timestamp TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            page_url TEXT NOT NULL,
            page_title TEXT,
            first_collected_at TEXT NOT NULL,
            last_collected_at TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_channel_time
            ON messages(channel_id, timestamp);
        """
    )
    return connection


def store_records(connection: sqlite3.Connection, records: list[dict], fallback_url: str = "") -> tuple[int, int]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if fallback_url:
        require_expected_channel(fallback_url)
    prepared = []
    for record in records:
        message_id = str(record.get("message_id") or "").strip()
        raw_text = str(record.get("raw_text") or "")
        page_url = str(record.get("page_url") or fallback_url).strip()
        if not message_id or not raw_text.strip():
            raise ValueError("message records require message_id and raw_text")
        logical_id = logical_message_id(message_id)
        guild_id, channel_id = require_expected_channel(page_url)
        timestamp = snowflake_timestamp(message_id) or str(record.get("timestamp") or record.get("browser_time") or "").strip()
        if not timestamp:
            raise ValueError(f"message {message_id} has no usable timestamp")
        prepared.append((logical_id, message_id, guild_id, channel_id, raw_text, page_url, timestamp, record))

    existing = {logical_message_id(row[0]) for row in connection.execute("SELECT message_id FROM messages")}
    inserted = duplicates = 0
    with connection:
        for logical_id, message_id, guild_id, channel_id, raw_text, page_url, timestamp, record in prepared:
            if logical_id in existing:
                duplicates += 1
                continue
            connection.execute(
                """
                INSERT INTO messages (
                    message_id, guild_id, channel_id, author_id, author_name, timestamp,
                    raw_text, page_url, page_title, first_collected_at, last_collected_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO NOTHING
                """,
                (
                    message_id,
                    guild_id,
                    channel_id,
                    str(record.get("author_id") or ""),
                    str(record.get("author_name") or ""),
                    timestamp,
                    raw_text,
                    page_url,
                    str(record.get("page_title") or ""),
                    now,
                    now,
                    json.dumps(record, ensure_ascii=False, sort_keys=True),
                ),
            )
            existing.add(logical_id)
            inserted += 1
    return inserted, duplicates


class EdgeClient:
    def __init__(self, port: int):
        self.port = int(port)
        self.request_id = 0

    def json_endpoint(self, path: str) -> object:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def targets(self) -> list[dict]:
        value = self.json_endpoint("/json")
        return value if isinstance(value, list) else []

    def evaluate(self, target_id: str, expression: str) -> object:
        try:
            from websocket import create_connection
        except ImportError as exc:
            raise RuntimeError("install websocket-client first: python -m pip install -r requirements.txt") from exc
        version = self.json_endpoint("/json/version")
        socket_url = str(version.get("webSocketDebuggerUrl") or "") if isinstance(version, dict) else ""
        if not socket_url:
            raise RuntimeError("Edge did not expose its debug websocket")
        socket = create_connection(socket_url, timeout=8, suppress_origin=True)
        session_id = ""
        try:
            attached = self._request(socket, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
            session_id = str(attached.get("sessionId") or "")
            result = self._request(
                socket,
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
                session_id,
            )
            return result.get("result", {}).get("value")
        finally:
            if session_id:
                try:
                    self._request(socket, "Target.detachFromTarget", {"sessionId": session_id})
                except Exception:
                    pass
            socket.close()

    def _request(self, socket, method: str, params: dict, session_id: str = "") -> dict:
        self.request_id += 1
        request = {"id": self.request_id, "method": method, "params": params}
        if session_id:
            request["sessionId"] = session_id
        socket.send(json.dumps(request))
        while True:
            response = json.loads(socket.recv())
            if response.get("id") != self.request_id:
                continue
            if response.get("error"):
                raise RuntimeError(str(response["error"].get("message") or response["error"]))
            return response.get("result", {})


def find_target(client: EdgeClient, expected_url: str) -> dict:
    matches = [
        target
        for target in client.targets()
        if target.get("type") == "page" and same_channel(str(target.get("url") or ""), expected_url)
    ]
    if not matches:
        raise RuntimeError("the expected Discord channel is not open on the Edge debug port")
    return matches[0]


def detect_port(channel_url: str, ports: list[int]) -> int | None:
    """Return the first debug port exposing the exact requested Discord channel."""
    require_expected_channel(channel_url)
    for port in ports:
        try:
            find_target(EdgeClient(port), channel_url)
            return port
        except (RuntimeError, ValueError, OSError):
            continue
    return None


def date_bounds(target_day: date | None = None, start_date: date | None = None, end_date: date | None = None) -> tuple[date | None, date | None]:
    if target_day and (start_date or end_date):
        raise ValueError("use either --date or --start-date/--end-date, not both")
    if bool(start_date) != bool(end_date):
        raise ValueError("--start-date and --end-date must be provided together")
    start = target_day or start_date
    end = target_day or end_date
    if start and end and start > end:
        raise ValueError("beginning date cannot be after ending date")
    return start, end


def collect_expression(limit: int) -> str:
    return f"""
(() => {{
  const clean = value => String(value || '').replace(/\\s+/g, ' ').trim();
  const nodes = document.querySelectorAll('li[data-list-item-id^="chat-messages___"], li[id^="chat-messages-"]');
  const messages = [];
  const seen = new Set();
  for (const node of nodes) {{
    const rawId = clean(node.getAttribute('data-list-item-id') || node.id);
    const messageId = rawId.split('chat-messages-').pop();
    if (!messageId || seen.has(messageId)) continue;
    const parts = [...node.querySelectorAll('[id^="message-content-"], [class*="messageContent"]')]
      .map(item => clean(item.innerText || item.textContent)).filter(Boolean);
    if (!parts.length) continue;
    seen.add(messageId);
    const clock = node.querySelector('time');
    const author = node.querySelector('[id^="message-username-"], [class*="username"]');
    const avatar = node.querySelector('img[src*="/avatars/"]');
    const avatarMatch = String(avatar ? avatar.src : '').match(/\\/avatars\\/(\\d+)\\//);
    messages.push({{
      message_id: messageId,
      raw_text: parts.join(' '),
      browser_time: clean(clock ? (clock.getAttribute('datetime') || clock.innerText) : ''),
      author_id: clean(node.getAttribute('data-author-id') || (avatarMatch ? avatarMatch[1] : '')),
      author_name: clean(author ? (author.innerText || author.textContent) : '')
    }});
  }}
  return {{page_url: location.href, page_title: document.title, messages: messages.slice(-{max(1, int(limit))})}};
}})()
""".strip()


SCROLL_UP = """
(() => {
  const scrollable = node => node && /(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.scrollHeight > node.clientHeight;
  let node = document.querySelector('[data-list-id="chat-messages"], ol[data-list-id="chat-messages"], li[id^="chat-messages-"]');
  while (node && !scrollable(node)) node = node.parentElement;
  if (!node) {
    const candidates = [...document.querySelectorAll('main *')].filter(scrollable);
    node = candidates.sort((left, right) => right.scrollHeight - left.scrollHeight)[0];
  }
  if (!node) return {moved: false, at_top: false, page_url: location.href};
  const before = node.scrollTop;
  // Discord's reversed message list starts at 0 and uses negative scrollTop for older history.
  node.scrollTop = before - 700;
  node.dispatchEvent(new WheelEvent('wheel', {deltaY: -700, bubbles: true}));
  const after = node.scrollTop;
  return {moved: after !== before, at_top: after === before && before < 0, page_url: location.href};
})()
""".strip()


SCROLL_TO_LATEST = """
(() => {
  const scrollable = node => node && /(auto|scroll)/.test(getComputedStyle(node).overflowY) && node.scrollHeight > node.clientHeight;
  let node = document.querySelector('[data-list-id="chat-messages"], ol[data-list-id="chat-messages"], li[id^="chat-messages-"]');
  while (node && !scrollable(node)) node = node.parentElement;
  if (!node) {
    const candidates = [...document.querySelectorAll('main *')].filter(scrollable);
    node = candidates.sort((left, right) => right.scrollHeight - left.scrollHeight)[0];
  }
  if (!node) return {moved: false, page_url: location.href};
  const before = node.scrollTop;
  node.scrollTop = 0;
  return {moved: node.scrollTop !== before, page_url: location.href};
})()
""".strip()


def collect(client: EdgeClient, connection: sqlite3.Connection, channel_url: str, target_day: date | None = None, timezone_name: str = "America/New_York", scroll_rounds: int = 200, visible_limit: int = 80, start_date: date | None = None, end_date: date | None = None, checkpoint: Callable[[dict[str, object]], object] | None = None) -> dict:
    start_date, end_date = date_bounds(target_day, start_date, end_date)
    require_expected_channel(channel_url)
    target = find_target(client, channel_url)
    target_id = str(target.get("id") or "")
    latest = client.evaluate(target_id, SCROLL_TO_LATEST)
    if not isinstance(latest, dict) or not same_channel(str(latest.get("page_url") or ""), channel_url):
        raise RuntimeError("channel guard failed before collection")
    if latest.get("moved"):
        time.sleep(0.8)
    seen: set[str] = set()
    total_visible = inserted = duplicates = stagnant = 0
    stopped_on_older = reached_top = False
    for round_number in range(max(1, scroll_rounds + 1)):
        payload = client.evaluate(target_id, collect_expression(visible_limit))
        if not isinstance(payload, dict) or not same_channel(str(payload.get("page_url") or ""), channel_url):
            raise RuntimeError("channel guard failed; no records were written for this round")
        records = []
        saw_older = False
        for item in payload.get("messages") or []:
            if not isinstance(item, dict):
                continue
            item["page_url"] = str(payload.get("page_url") or "")
            item["page_title"] = str(payload.get("page_title") or "")
            timestamp = snowflake_timestamp(str(item.get("message_id") or "")) or str(item.get("browser_time") or "")
            local_day = message_date(timestamp, timezone_name)
            if start_date and local_day and local_day < start_date:
                saw_older = True
            if start_date and (local_day is None or local_day < start_date or local_day > end_date):
                continue
            records.append(item)
        total_visible += len(payload.get("messages") or [])
        before = len(seen)
        seen.update(logical_message_id(item.get("message_id")) for item in records)
        new_count, duplicate_count = store_records(connection, records, channel_url)
        inserted += new_count
        duplicates += duplicate_count
        stagnant = stagnant + 1 if len(seen) == before else 0
        state = {"round": round_number + 1, "unique_matching": len(seen), "inserted": inserted, "duplicates": duplicates}
        if checkpoint:
            checkpoint(state)
        if saw_older:
            stopped_on_older = True
            break
        scroll_state = client.evaluate(target_id, SCROLL_UP)
        if not isinstance(scroll_state, dict) or not same_channel(str(scroll_state.get("page_url") or ""), channel_url):
            raise RuntimeError("channel guard failed while scrolling")
        if scroll_state.get("at_top"):
            reached_top = True
            break
        if round_number >= scroll_rounds or stagnant >= 8:
            raise RuntimeError("collection stopped before proving the requested start boundary")
        time.sleep(0.8)
    return {"visible_reads": total_visible, "unique_matching": len(seen), "inserted": inserted, "duplicates": duplicates, "stopped_on_older": stopped_on_older, "reached_top": reached_top}


def import_jsonl(connection: sqlite3.Connection, paths: list[Path], channel_url: str = "") -> dict:
    records: list[dict] = []
    for path in paths:
        with path.open(encoding="utf-8") as source:
            records.extend(json.loads(line) for line in source if line.strip())
    inserted, duplicates = store_records(connection, records, channel_url)
    return {"rows_read": len(records), "inserted": inserted, "duplicates": duplicates}


def database_counts(connection: sqlite3.Connection, channel_url: str, target_day: date | None = None, timezone_name: str = "America/New_York", start_date: date | None = None, end_date: date | None = None) -> dict:
    start_date, end_date = date_bounds(target_day, start_date, end_date)
    _, channel_id = require_expected_channel(channel_url)
    timestamps = [row[0] for row in connection.execute("SELECT timestamp FROM messages WHERE channel_id = ?", (channel_id,))]
    return {
        "database_day_count": sum(message_date(timestamp, timezone_name) == target_day for timestamp in timestamps) if target_day else None,
        "database_range_count": sum(start_date <= message_date(timestamp, timezone_name) <= end_date for timestamp in timestamps if message_date(timestamp, timezone_name) is not None) if start_date and end_date and not target_day else None,
        "database_channel_total": len(timestamps),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Discord messages from a logged-in Edge tab into SQLite. Never posts to Discord.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--channel-url", default=os.environ.get("DISCORD_CHANNEL_URL", ""))
    collect_parser.add_argument("--port", type=int, default=9225)
    collect_parser.add_argument("--date", type=date.fromisoformat)
    collect_parser.add_argument("--start-date", type=date.fromisoformat)
    collect_parser.add_argument("--end-date", type=date.fromisoformat)
    collect_parser.add_argument("--timezone", default="America/New_York")
    collect_parser.add_argument("--scroll-rounds", type=int, default=200)
    collect_parser.add_argument("--visible-limit", type=int, default=80)
    collect_parser.add_argument("--confirm-refresh", action="store_true")

    detect_parser = subparsers.add_parser("detect-port")
    detect_parser.add_argument("--channel-url", required=True)
    detect_parser.add_argument("--ports", nargs="+", type=int, default=[9227, 9225])

    import_parser = subparsers.add_parser("import-jsonl")
    import_parser.add_argument("paths", nargs="+", type=Path)
    import_parser.add_argument("--channel-url", default="")

    args = parser.parse_args()
    if args.command == "detect-port":
        try:
            port = detect_port(args.channel_url, args.ports)
        except ValueError as exc:
            print(f"BLOCK: {exc}")
            return 2
        if port is None:
            return 1
        print(port)
        return 0

    if args.command == "collect":
        if not args.channel_url:
            parser.error("collect requires --channel-url or DISCORD_CHANNEL_URL")
        try:
            require_expected_channel(args.channel_url)
            start_date, end_date = date_bounds(args.date, args.start_date, args.end_date)
            if start_date is None or end_date is None:
                parser.error("collect requires --date or an explicit --start-date/--end-date range")
        except ValueError as exc:
            parser.error(str(exc))

    store = OperationStore()
    connection = None
    operation_id = ""
    try:
        if args.command == "collect":
            details = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "channel_url": args.channel_url, "port": args.port}
            operation = store.begin("collection", "V6", details)
            operation_id = str(operation["operation_id"])
            overlaps = store.overlapping_completed_ranges(start_date, end_date)
            if overlaps and not args.confirm_refresh:
                store.finish(operation_id, "blocked", {"overlapping_completed_ranges": overlaps}, "refresh confirmation required")
                operation_id = ""
                print("BLOCK: this range overlaps a completed collection range; rerun with --confirm-refresh after Greg confirms")
                print(json.dumps({"overlapping_completed_ranges": overlaps}, indent=2))
                return 3
        else:
            details = {"paths": [str(path.resolve()) for path in args.paths], "channel_url": args.channel_url}
            operation = store.begin("collection_import", "V6", details)
            operation_id = str(operation["operation_id"])

        connection = open_database(args.db)
        if args.command == "collect":
            summary = collect(client=EdgeClient(args.port), connection=connection, channel_url=args.channel_url, timezone_name=args.timezone, scroll_rounds=max(0, args.scroll_rounds), visible_limit=max(1, args.visible_limit), start_date=start_date, end_date=end_date, checkpoint=lambda state: store.checkpoint(operation_id, state))
            if args.date:
                counts = database_counts(connection, args.channel_url, target_day=args.date, timezone_name=args.timezone)
            else:
                counts = database_counts(connection, args.channel_url, timezone_name=args.timezone, start_date=start_date, end_date=end_date)
            summary.update(counts)
        else:
            summary = import_jsonl(connection, args.paths, args.channel_url)
        connection.close()
        connection = None
        store.finish(operation_id, "completed", summary)
        operation_id = ""
    except (OperationBusy, RuntimeError, ValueError, OSError, sqlite3.Error) as exc:
        if operation_id:
            try:
                store.finish(operation_id, "failed", error=str(exc))
            except Exception:
                pass
        print(f"BLOCK: {exc}")
        return 2
    finally:
        if connection is not None:
            connection.close()
    print(json.dumps({"database": str(args.db.resolve()), **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
