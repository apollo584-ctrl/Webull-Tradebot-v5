import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import discord_collector
from discord_collector import (
    DISCORD_EPOCH_MS,
    EXPECTED_CHANNEL_ID,
    EXPECTED_GUILD_ID,
    SCROLL_TO_LATEST,
    SCROLL_UP,
    collect,
    date_bounds,
    detect_port,
    message_date,
    open_database,
    store_records,
)


URL = f"https://discord.com/channels/{EXPECTED_GUILD_ID}/{EXPECTED_CHANNEL_ID}"


def snowflake(value: str) -> str:
    milliseconds = int(datetime.fromisoformat(value).timestamp() * 1000)
    return str((milliseconds - DISCORD_EPOCH_MS) << 22)


def record(value: str, text: str, *, url: str = URL) -> dict:
    return {"message_id": snowflake(value), "raw_text": text, "page_url": url}


class FakeEdge:
    def __init__(self, payload: dict, *, at_top: bool = True):
        self.payload = payload
        self.at_top = at_top

    def targets(self):
        return [{"type": "page", "url": URL, "id": "target"}]

    def evaluate(self, target_id, expression):
        if expression == SCROLL_TO_LATEST:
            return {"moved": False, "page_url": URL}
        if expression == SCROLL_UP:
            return {"moved": False, "at_top": self.at_top, "page_url": URL}
        return self.payload


def archive_hash(connection) -> str:
    rows = connection.execute("SELECT * FROM messages ORDER BY message_id").fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def test_insert_only_logical_id_dedup_preserves_first_capture(tmp_path: Path):
    connection = open_database(tmp_path / "messages.sqlite3")
    item = record("2026-07-15T14:00:00+00:00", "first")
    compound = {**item, "message_id": f"{EXPECTED_CHANNEL_ID}-{item['message_id']}"}
    edited = {**item, "raw_text": "edited"}

    assert store_records(connection, [compound]) == (1, 0)
    before = archive_hash(connection)
    assert store_records(connection, [edited]) == (0, 1)
    assert archive_hash(connection) == before
    assert connection.execute("SELECT raw_text FROM messages").fetchone()[0] == "first"
    connection.close()


def test_inclusive_boundaries_and_timezone_conversion():
    assert date_bounds(start_date=date(2026, 7, 13), end_date=date(2026, 7, 15)) == (date(2026, 7, 13), date(2026, 7, 15))
    assert message_date("2026-07-15T03:59:59+00:00", "America/New_York") == date(2026, 7, 14)
    assert message_date("2026-07-15T04:00:00+00:00", "America/New_York") == date(2026, 7, 15)
    with pytest.raises(ValueError):
        date_bounds(start_date=date(2026, 7, 15), end_date=date(2026, 7, 13))


def test_range_collects_start_and_end_and_checkpoints_after_storage(tmp_path: Path):
    payload = {"page_url": URL, "page_title": "Casey", "messages": [
        record("2026-07-12T16:00:00+00:00", "before"),
        record("2026-07-13T04:00:00+00:00", "start"),
        record("2026-07-16T03:59:59+00:00", "end"),
        record("2026-07-16T04:00:00+00:00", "after"),
    ]}
    connection = open_database(tmp_path / "messages.sqlite3")
    checkpoints = []
    summary = collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 13), end_date=date(2026, 7, 15), scroll_rounds=0, checkpoint=checkpoints.append)
    assert summary["stopped_on_older"] is True
    assert connection.execute("SELECT raw_text FROM messages ORDER BY raw_text").fetchall() == [("end",), ("start",)]
    assert checkpoints == [{"round": 1, "unique_matching": 2, "inserted": 2, "duplicates": 0}]
    connection.close()


def test_exact_server_and_channel_are_required(tmp_path: Path):
    connection = open_database(tmp_path / "messages.sqlite3")
    wrong_server = f"https://discord.com/channels/1/{EXPECTED_CHANNEL_ID}"
    wrong_channel = f"https://discord.com/channels/{EXPECTED_GUILD_ID}/1"
    with pytest.raises(ValueError, match="expected Discord server"):
        store_records(connection, [record("2026-07-15T14:00:00+00:00", "wrong", url=wrong_server)])
    with pytest.raises(ValueError, match="expected Discord server"):
        store_records(connection, [record("2026-07-15T14:00:00+00:00", "wrong", url=wrong_channel)])
    assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    connection.close()


def test_interruptions_resume_without_missing_duplicates_or_content_change(tmp_path: Path, monkeypatch):
    payload = {"page_url": URL, "page_title": "Casey", "messages": [record("2026-07-15T14:00:00+00:00", "body")]}
    connection = open_database(tmp_path / "messages.sqlite3")
    real_store = discord_collector.store_records

    monkeypatch.setattr(discord_collector, "store_records", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("before durable storage")))
    with pytest.raises(RuntimeError, match="before durable"):
        collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15), scroll_rounds=0)
    assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0

    monkeypatch.setattr(discord_collector, "store_records", real_store)
    with pytest.raises(RuntimeError, match="after durable"):
        collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15), scroll_rounds=0, checkpoint=lambda state: (_ for _ in ()).throw(RuntimeError("after durable storage")))
    assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    before = archive_hash(connection)

    summary = collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15), scroll_rounds=0)
    assert summary["inserted"] == 0 and summary["duplicates"] == 1
    assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    assert archive_hash(connection) == before
    connection.close()


def test_unproven_boundary_is_not_marked_complete(tmp_path: Path):
    payload = {"page_url": URL, "page_title": "Casey", "messages": [record("2026-07-15T14:00:00+00:00", "body")]}
    connection = open_database(tmp_path / "messages.sqlite3")
    with pytest.raises(RuntimeError, match="before proving"):
        collect(FakeEdge(payload, at_top=False), connection, URL, start_date=date(2026, 7, 13), end_date=date(2026, 7, 15), scroll_rounds=0)
    connection.close()


def test_detect_port_accepts_only_expected_channel(monkeypatch):
    class Client:
        def __init__(self, port):
            self.port = port

        def targets(self):
            return [{"type": "page", "url": URL, "id": str(self.port)}]

    monkeypatch.setattr(discord_collector, "EdgeClient", Client)
    assert detect_port(URL, [9227, 9225]) == 9227
    with pytest.raises(ValueError):
        detect_port("https://discord.com/channels/1/2", [9227])


def test_operator_wrapper_remains_collection_only():
    script = Path("collect_messages.bat").read_text(encoding="utf-8")
    assert EXPECTED_GUILD_ID in script and EXPECTED_CHANNEL_ID in script
    assert "--start-date" in script and "--end-date" in script and "--confirm-refresh" in script
    assert "--invoked-by" not in script
    assert all(word not in script.casefold() for word in ("qwen", "broker", "sim"))


def test_scroll_expression_supports_reversed_discord_history():
    assert "node.scrollTop = before - 700" in SCROLL_UP
    assert "Math.max(0" not in SCROLL_UP
    assert "document.querySelectorAll('main *')" in SCROLL_UP
    assert "node.scrollTop = 0" in SCROLL_TO_LATEST
