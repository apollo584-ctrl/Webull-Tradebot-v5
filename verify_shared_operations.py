from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sqlite3

import discord_collector
import operation_control
from discord_collector import DISCORD_EPOCH_MS, EXPECTED_CHANNEL_ID, EXPECTED_GUILD_ID, SCROLL_TO_LATEST, SCROLL_UP, collect, date_bounds, message_date, open_database, store_records
from human_labeling import DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE, build_queue, load_events, prepare_batch, read_messages, record_correction, record_label, session_queue
from operation_control import OperationStore, append_jsonl_atomic


ROOT = Path(__file__).resolve().parent
CHECK_DIR = ROOT / "tests"
CHECK_DB = CHECK_DIR / "verify_messages.sqlite3"
LABEL_DB = CHECK_DIR / "verify_label_messages.sqlite3"
CHECK_LABELS = CHECK_DIR / "verify_labels.jsonl"
ATOMIC_LOG = CHECK_DIR / "verify_atomic.jsonl"
TXN_DB = CHECK_DIR / "verify_transaction.sqlite3"
OP_FILES = tuple(CHECK_DIR / name for name in ("operation.lock", "operation_step.lock", "operation_runs.jsonl", "operation_runs.jsonl.tmp"))
CHECK_FILES = (CHECK_DB, LABEL_DB, CHECK_LABELS, CHECK_LABELS.with_name(CHECK_LABELS.name + ".tmp"), ATOMIC_LOG, ATOMIC_LOG.with_name(ATOMIC_LOG.name + ".tmp"), TXN_DB, *OP_FILES)
SQLITE_SIDECARS = tuple(Path(str(path) + suffix) for path in (CHECK_DB, LABEL_DB, TXN_DB) for suffix in ("-wal", "-shm"))
URL = f"https://discord.com/channels/{EXPECTED_GUILD_ID}/{EXPECTED_CHANNEL_ID}"


def main() -> int:
    all_files = CHECK_FILES + SQLITE_SIDECARS
    if any(path.exists() for path in all_files):
        raise RuntimeError("verification scratch files already exist; remove only the named verify files and retry")
    try:
        check_collection_boundaries_and_identity()
        check_interruption_resume_and_idempotence()
        check_operation_checkpoint_and_recovery()
        check_label_batches_and_resume()
        print("stability-refactor=ok checks=17")
        return 0
    finally:
        for path in all_files:
            path.unlink(missing_ok=True)


def snowflake(value: str) -> str:
    milliseconds = int(datetime.fromisoformat(value).timestamp() * 1000)
    return str((milliseconds - DISCORD_EPOCH_MS) << 22)


def record(value: str, text: str, url: str = URL) -> dict[str, str]:
    return {"message_id": snowflake(value), "raw_text": text, "page_url": url}


class FakeEdge:
    def __init__(self, payload: dict[str, object], *, at_top: bool = True):
        self.payload = payload
        self.at_top = at_top

    def targets(self) -> list[dict[str, str]]:
        return [{"type": "page", "url": URL, "id": "target"}]

    def evaluate(self, target_id: str, expression: str) -> object:
        if expression == SCROLL_TO_LATEST:
            return {"moved": False, "page_url": URL}
        if expression == SCROLL_UP:
            return {"moved": False, "at_top": self.at_top, "page_url": URL}
        return self.payload


def archive_hash(connection: sqlite3.Connection) -> str:
    rows = connection.execute("SELECT * FROM messages ORDER BY message_id").fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def expect(error_type: type[BaseException], action, text: str = "") -> None:
    try:
        action()
    except error_type as exc:
        assert not text or text in str(exc)
    else:
        raise AssertionError(f"expected {error_type.__name__}")


def check_collection_boundaries_and_identity() -> None:
    assert "node.scrollTop = before - 700" in SCROLL_UP
    assert "Math.max(0" not in SCROLL_UP
    assert "node.scrollTop = 0" in SCROLL_TO_LATEST
    assert date_bounds(start_date=date(2026, 7, 13), end_date=date(2026, 7, 15)) == (date(2026, 7, 13), date(2026, 7, 15))
    assert message_date("2026-07-15T03:59:59+00:00", "America/New_York") == date(2026, 7, 14)
    assert message_date("2026-07-15T04:00:00+00:00", "America/New_York") == date(2026, 7, 15)

    connection = open_database(CHECK_DB)
    payload = {"page_url": URL, "page_title": "Casey", "messages": [
        record("2026-07-12T16:00:00+00:00", "before"),
        record("2026-07-13T04:00:00+00:00", "start"),
        record("2026-07-16T03:59:59+00:00", "end"),
        record("2026-07-16T04:00:00+00:00", "after"),
    ]}
    checkpoints: list[dict[str, object]] = []
    summary = collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 13), end_date=date(2026, 7, 15), scroll_rounds=0, checkpoint=checkpoints.append)
    assert summary["stopped_on_older"] and checkpoints[0]["inserted"] == 2
    assert {row[0] for row in connection.execute("SELECT raw_text FROM messages")} == {"start", "end"}

    wrong_server = f"https://discord.com/channels/1/{EXPECTED_CHANNEL_ID}"
    wrong_channel = f"https://discord.com/channels/{EXPECTED_GUILD_ID}/1"
    expect(ValueError, lambda: store_records(connection, [record("2026-07-15T14:00:00+00:00", "wrong", wrong_server)]), "expected Discord server")
    expect(ValueError, lambda: store_records(connection, [record("2026-07-15T14:01:00+00:00", "wrong", wrong_channel)]), "expected Discord server")

    item = record("2026-07-15T14:02:00+00:00", "first")
    compound = {**item, "message_id": f"{EXPECTED_CHANNEL_ID}-{item['message_id']}"}
    assert store_records(connection, [compound]) == (1, 0)
    before = archive_hash(connection)
    assert store_records(connection, [{**item, "raw_text": "edited"}]) == (0, 1)
    assert archive_hash(connection) == before
    connection.close()


def check_interruption_resume_and_idempotence() -> None:
    connection = open_database(CHECK_DB)
    payload = {"page_url": URL, "page_title": "Casey", "messages": [record("2026-07-15T15:00:00+00:00", "resume body")]}
    real_store = discord_collector.store_records
    try:
        discord_collector.store_records = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("before durable storage"))
        expect(RuntimeError, lambda: collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15), scroll_rounds=0), "before durable")
    finally:
        discord_collector.store_records = real_store
    assert connection.execute("SELECT COUNT(*) FROM messages WHERE raw_text = 'resume body'").fetchone()[0] == 0

    expect(RuntimeError, lambda: collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15), scroll_rounds=0, checkpoint=lambda state: (_ for _ in ()).throw(RuntimeError("after durable storage"))), "after durable")
    assert connection.execute("SELECT COUNT(*) FROM messages WHERE raw_text = 'resume body'").fetchone()[0] == 1
    before_count = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    before_hash = archive_hash(connection)
    summary = collect(FakeEdge(payload), connection, URL, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15), scroll_rounds=0)
    assert summary["inserted"] == 0 and summary["duplicates"] == 1
    assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == before_count
    assert archive_hash(connection) == before_hash
    connection.close()


def check_operation_checkpoint_and_recovery() -> None:
    store = OperationStore(CHECK_DIR)
    operation = store.begin("collection", "V5", {"start_date": "2026-07-13", "end_date": "2026-07-15"})
    checkpoint = store.checkpoint(str(operation["operation_id"]), {"inserted": 3, "unique_matching": 3})
    assert store.status()["latest_checkpoint"] == checkpoint
    assert "raw_text" not in json.dumps(store.status())
    store.finish(str(operation["operation_id"]), "completed", {"inserted": 3})

    append_jsonl_atomic(ATOMIC_LOG, {"event": "first"})
    before = ATOMIC_LOG.read_bytes()
    real_replace = operation_control.os.replace
    try:
        operation_control.os.replace = lambda *args: (_ for _ in ()).throw(OSError("interrupted replace"))
        expect(OSError, lambda: append_jsonl_atomic(ATOMIC_LOG, {"event": "second"}), "interrupted replace")
    finally:
        operation_control.os.replace = real_replace
    assert ATOMIC_LOG.read_bytes() == before

    connection = sqlite3.connect(TXN_DB)
    connection.execute("CREATE TABLE records (value TEXT)")
    connection.commit()
    connection.execute("BEGIN")
    connection.execute("INSERT INTO records VALUES ('uncommitted')")
    connection.close()
    connection = sqlite3.connect(TXN_DB)
    assert connection.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
    connection.close()


def check_label_batches_and_resume() -> None:
    ids = [f"15269628800780206{index:02d}" for index in range(12)]
    texts = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet", "kilo", "lima")
    connection = sqlite3.connect(LABEL_DB)
    connection.execute("CREATE TABLE messages (message_id TEXT PRIMARY KEY, timestamp TEXT, author_id TEXT, author_name TEXT, raw_text TEXT, page_url TEXT)")
    connection.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", [(ids[index], f"2026-07-15T14:{index:02d}:00+00:00", "a", "Casey", texts[index], URL) for index in range(12)])
    connection.commit()
    connection.close()

    messages = read_messages(LABEL_DB, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15))
    queue = build_queue(messages, [])
    assert DEFAULT_BATCH_SIZE == 5 and prepare_batch(queue)["batch_count"] == 5
    assert MAX_BATCH_SIZE == 10 and prepare_batch(queue, MAX_BATCH_SIZE)["batch_count"] == 10
    expect(ValueError, lambda: prepare_batch(queue, 11), "between 5 and 10")
    assert all(set(message) == {"message_id", "timestamp", "author_name", "raw_text"} for message in prepare_batch(queue)["messages"])

    decision = {"action": "NONE", "status": "no_action"}
    first = record_label(CHECK_LABELS, ids[:2], decision, "Confirmed first two")
    expect(ValueError, lambda: record_label(CHECK_LABELS, [ids[0]], decision, "Duplicate"), "use correct-label")
    lock = {"details": {"start_date": "2026-07-15", "end_date": "2026-07-15", "batch_size": 5}}
    resumed = session_queue(lock, LABEL_DB, CHECK_LABELS)
    assert resumed["labeled_messages"] == 2 and resumed["batch"]["message_ids"] == ids[2:7]
    correction = record_correction(CHECK_LABELS, ids[:2], str(first["event_id"]), {"action": "WATCH", "status": "no_action"}, "Explicit correction")
    assert load_events(CHECK_LABELS)[-1]["event_id"] == correction["event_id"]


if __name__ == "__main__":
    raise SystemExit(main())
