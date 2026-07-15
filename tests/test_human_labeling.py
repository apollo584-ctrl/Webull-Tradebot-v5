from datetime import date
import sqlite3
from pathlib import Path

import pytest

from human_labeling import DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE, build_queue, effective_label_map, load_events, prepare_batch, read_messages, record_correction, record_label, session_queue


IDS = [f"15269628800780206{index:02d}" for index in range(12)]
TEXTS = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet", "kilo", "lima")


def database(path: Path, count: int = 12) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE messages (message_id TEXT PRIMARY KEY, timestamp TEXT, author_id TEXT, author_name TEXT, raw_text TEXT, page_url TEXT)")
    connection.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)",
        [(IDS[index], f"2026-07-15T14:{index:02d}:00+00:00", "a", "Casey", TEXTS[index], "https://discord.com/channels/1/2") for index in range(count)],
    )
    connection.commit()
    connection.close()


def decision(action: str = "NONE") -> dict:
    return {"action": action, "status": "no_action"}


def test_queue_resumes_and_duplicate_label_requires_correction(tmp_path: Path):
    db = tmp_path / "messages.sqlite3"
    labels = tmp_path / "labels.jsonl"
    database(db, 3)
    messages = read_messages(db, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15))

    first = record_label(labels, [IDS[0]], decision(), "Confirmed in chat")
    resumed = build_queue(messages, load_events(labels))
    assert resumed["labeled_messages"] == 1
    assert {message["message_id"] for message in resumed["individual_messages"]} == set(IDS[1:3])
    with pytest.raises(ValueError, match="use correct-label"):
        record_label(labels, [IDS[0]], decision("WATCH"), "Duplicate")

    correction = record_correction(labels, [IDS[0]], str(first["event_id"]), decision("WATCH"), "Explicit correction")
    assert effective_label_map(load_events(labels))[IDS[0]]["event_id"] == correction["event_id"]


def test_batches_use_default_and_maximum_with_only_needed_context(tmp_path: Path):
    db = tmp_path / "messages.sqlite3"
    database(db)
    queue = build_queue(read_messages(db, start_date=date(2026, 7, 15), end_date=date(2026, 7, 15)), [])
    default = prepare_batch(queue)
    maximum = prepare_batch(queue, MAX_BATCH_SIZE)

    assert DEFAULT_BATCH_SIZE == 5
    assert default["batch_count"] == 5 and maximum["batch_count"] == 10
    assert all(set(message) == {"message_id", "timestamp", "author_name", "raw_text"} for message in default["messages"])
    with pytest.raises(ValueError, match="between 5 and 10"):
        prepare_batch(queue, 11)


def test_session_batch_resumes_after_partial_completion(tmp_path: Path):
    db = tmp_path / "messages.sqlite3"
    labels = tmp_path / "labels.jsonl"
    database(db, 7)
    lock = {"details": {"start_date": "2026-07-15", "end_date": "2026-07-15", "batch_size": 5}}
    first = session_queue(lock, db, labels)
    assert first["batch"]["message_ids"] == IDS[:5]

    record_label(labels, IDS[:2], decision(), "Confirmed first two")
    resumed = session_queue(lock, db, labels)
    assert resumed["labeled_messages"] == 2
    assert resumed["batch"]["message_ids"] == IDS[2:7]


def test_correction_must_reference_current_event(tmp_path: Path):
    labels = tmp_path / "labels.jsonl"
    record_label(labels, [IDS[0]], decision(), "Confirmed")
    with pytest.raises(ValueError, match="current label"):
        record_correction(labels, [IDS[0]], "wrong-event", decision("WATCH"), "Correction")
