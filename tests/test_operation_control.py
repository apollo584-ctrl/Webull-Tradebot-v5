import json
from datetime import date
from pathlib import Path

import pytest

import operation_control
from operation_control import OperationBusy, OperationStore, append_jsonl_atomic


def test_shared_lock_checkpoint_and_completed_range(tmp_path: Path):
    store = OperationStore(tmp_path)
    first = store.begin("collection", "V5", {"start_date": "2026-07-13", "end_date": "2026-07-15"})
    operation_id = str(first["operation_id"])
    with pytest.raises(OperationBusy):
        store.begin("labeling", "V6", {"start_date": "2026-07-15", "end_date": "2026-07-15"}, persistent=True)

    checkpoint = store.checkpoint(operation_id, {"inserted": 3, "unique_matching": 3})
    assert store.status()["latest_checkpoint"] == checkpoint
    store.finish(operation_id, "completed", {"inserted": 3})
    completed = store.completed_collection_ranges()
    assert store.overlapping_completed_ranges(date(2026, 7, 15), date(2026, 7, 16)) == completed

    status_text = json.dumps(store.status())
    assert "raw_text" not in status_text and "message body" not in status_text


def test_persistent_label_session_allows_only_serial_steps(tmp_path: Path):
    store = OperationStore(tmp_path)
    session = store.begin("labeling", "V6", {"start_date": "2026-07-15", "end_date": "2026-07-15", "batch_size": 5}, persistent=True)
    operation_id = str(session["operation_id"])
    with store.labeling_step(operation_id):
        with pytest.raises(OperationBusy):
            with store.labeling_step(operation_id):
                pass
    store.finish(operation_id, "paused", {"unlabeled_messages": 2})
    assert store.active_lock() is None


def test_atomic_jsonl_failure_preserves_complete_original(tmp_path: Path, monkeypatch):
    path = tmp_path / "events.jsonl"
    append_jsonl_atomic(path, {"event": "first"})
    before = path.read_bytes()
    monkeypatch.setattr(operation_control.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("interrupted replace")))
    with pytest.raises(OSError, match="interrupted replace"):
        append_jsonl_atomic(path, {"event": "second"})
    assert path.read_bytes() == before
    assert not path.with_name(path.name + ".tmp").exists()


def test_partial_jsonl_is_rejected_without_truncation(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"event":"partial"')
    before = path.read_bytes()
    with pytest.raises(ValueError, match="partial JSONL"):
        append_jsonl_atomic(path, {"event": "next"})
    assert path.read_bytes() == before
