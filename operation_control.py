from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
import json
import os
from pathlib import Path
import socket
from typing import Iterator
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOCK_PATH = DATA_DIR / "operation.lock"
STEP_LOCK_PATH = DATA_DIR / "operation_step.lock"
LEDGER_PATH = DATA_DIR / "operation_runs.jsonl"


class OperationBusy(RuntimeError):
    pass


class OperationStore:
    def __init__(self, data_dir: str | Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.lock_path = self.data_dir / "operation.lock"
        self.step_lock_path = self.data_dir / "operation_step.lock"
        self.ledger_path = self.data_dir / "operation_runs.jsonl"

    def begin(self, operation: str, invoked_by: str, details: dict[str, object], *, persistent: bool = False) -> dict[str, object]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._clear_stale(self.lock_path)
        record = {
            "operation_id": uuid4().hex,
            "operation": str(operation),
            "invoked_by": str(invoked_by),
            "details": dict(details),
            "persistent": bool(persistent),
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "started_at": _now(),
        }
        try:
            self._create_lock(self.lock_path, record)
        except FileExistsError as exc:
            active = self.active_lock()
            raise OperationBusy(f"operation already active: {json.dumps(active, sort_keys=True)}") from exc
        try:
            self._append({"event": "operation_started", **record})
        except Exception:
            self.lock_path.unlink(missing_ok=True)
            raise
        return record

    def finish(self, operation_id: str, status: str, result: dict[str, object] | None = None, error: str = "") -> dict[str, object]:
        lock = self.require(operation_id)
        event = {
            "event": f"operation_{status}",
            **lock,
            "finished_at": _now(),
            "result": dict(result or {}),
            "error": str(error),
        }
        self._append(event)
        self.lock_path.unlink(missing_ok=True)
        return event

    def checkpoint(self, operation_id: str, result: dict[str, object]) -> dict[str, object]:
        lock = self.require(operation_id, "collection")
        event = {"event": "operation_checkpoint", **lock, "checkpointed_at": _now(), "result": dict(result)}
        self._append(event)
        return event

    def require(self, operation_id: str, operation: str | None = None) -> dict[str, object]:
        lock = self.active_lock()
        if not lock or lock.get("operation_id") != operation_id:
            raise OperationBusy("the requested operation session is not active")
        if operation and lock.get("operation") != operation:
            raise OperationBusy(f"active operation is {lock.get('operation')}, not {operation}")
        return lock

    def active_lock(self) -> dict[str, object] | None:
        self._clear_stale(self.lock_path)
        return self._read_json(self.lock_path)

    @contextmanager
    def labeling_step(self, operation_id: str) -> Iterator[dict[str, object]]:
        lock = self.require(operation_id, "labeling")
        self._clear_stale(self.step_lock_path)
        step = {"operation_id": operation_id, "pid": os.getpid(), "host": socket.gethostname(), "started_at": _now()}
        try:
            self._create_lock(self.step_lock_path, step)
        except FileExistsError as exc:
            raise OperationBusy("another labeling command is already running") from exc
        try:
            yield self.require(operation_id, "labeling")
        finally:
            self.step_lock_path.unlink(missing_ok=True)

    def completed_collection_ranges(self) -> list[dict[str, object]]:
        return [
            {
                "operation_id": event.get("operation_id"),
                "start_date": event.get("details", {}).get("start_date"),
                "end_date": event.get("details", {}).get("end_date"),
                "invoked_by": event.get("invoked_by"),
                "completed_at": event.get("finished_at"),
                "result": event.get("result", {}),
            }
            for event in self.events()
            if event.get("event") == "operation_completed" and event.get("operation") == "collection"
        ]

    def overlapping_completed_ranges(self, start_date: date, end_date: date) -> list[dict[str, object]]:
        overlaps = []
        for item in self.completed_collection_ranges():
            try:
                old_start = date.fromisoformat(str(item["start_date"]))
                old_end = date.fromisoformat(str(item["end_date"]))
            except (TypeError, ValueError):
                continue
            if start_date <= old_end and end_date >= old_start:
                overlaps.append(item)
        return overlaps

    def events(self) -> list[dict[str, object]]:
        if not self.ledger_path.exists():
            return []
        events = []
        with self.ledger_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict) or "event" not in value:
                    raise ValueError(f"invalid operation ledger event at {self.ledger_path}:{line_number}")
                events.append(value)
        return events

    def status(self) -> dict[str, object]:
        checkpoints = [event for event in self.events() if event.get("event") == "operation_checkpoint"]
        return {
            "active_operation": self.active_lock(),
            "completed_collection_ranges": self.completed_collection_ranges(),
            "latest_checkpoint": checkpoints[-1] if checkpoints else None,
            "ledger": str(self.ledger_path.resolve()),
            "lock": str(self.lock_path.resolve()),
        }

    def _append(self, event: dict[str, object]) -> None:
        append_jsonl_atomic(self.ledger_path, event)

    @staticmethod
    def _create_lock(path: Path, value: dict[str, object]) -> None:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(descriptor, json.dumps(value, separators=(",", ":")).encode("utf-8"))
        finally:
            os.close(descriptor)

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _clear_stale(self, path: Path) -> None:
        value = self._read_json(path)
        if not value:
            if path.exists():
                path.unlink(missing_ok=True)
            return
        if path == self.lock_path and value.get("persistent"):
            return
        if value.get("host") == socket.gethostname() and not _pid_alive(int(value.get("pid") or 0)):
            path.unlink(missing_ok=True)
            if path == self.lock_path:
                self._append({"event": "operation_abandoned", **value, "finished_at": _now(), "error": "stale process lock recovered"})


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def append_jsonl_atomic(path: str | Path, event: dict[str, object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = target.read_bytes() if target.exists() else b""
    if previous and not previous.endswith(b"\n"):
        raise ValueError(f"refusing to append to partial JSONL file: {target}")
    temporary = target.with_name(target.name + ".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(previous)
            handle.write((json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
