from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo

from operation_control import OperationBusy, OperationStore, append_jsonl_atomic


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "messages.sqlite3"
DEFAULT_LABELS = ROOT / "data" / "human_label_events.jsonl"
EXECUTABLE_ACTIONS = frozenset({"OPEN", "ADD", "TRIM", "SELL"})
SUPPORTED_SYMBOLS = frozenset({"SPY", "QQQ", "IWM"})
SUPPORTED_DIRECTIONS = frozenset({"LONG", "SHORT"})
ALLOWED_ACTIONS = EXECUTABLE_ACTIONS | {"WATCH", "NONE", "REVIEW"}
ALLOWED_STATUSES = frozenset({"actionable", "no_action", "ambiguous", "insufficient_context"})
LABEL_EVENTS = frozenset({"group_decision", "label_confirmed", "label_correction"})
DEFAULT_BATCH_SIZE = 5
MAX_BATCH_SIZE = 10


def read_messages(path: str | Path = DEFAULT_DB, *, start_date: date, end_date: date, timezone_name: str = "America/New_York") -> list[dict[str, object]]:
    if start_date > end_date:
        raise ValueError("beginning date cannot be after ending date")
    database = Path(path).resolve()
    if not database.is_file():
        raise FileNotFoundError(f"shared message database not found: {database}")
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT message_id, timestamp, author_id, author_name, raw_text, page_url FROM messages ORDER BY timestamp, message_id"
        ).fetchall()
    finally:
        connection.close()
    timezone = ZoneInfo(timezone_name)
    messages = []
    for row in rows:
        local_day = _local_date(str(row[1]), timezone)
        if local_day is None or not start_date <= local_day <= end_date:
            continue
        messages.append({
            "message_id": str(row[0]),
            "timestamp": str(row[1]),
            "author_id": str(row[2] or ""),
            "author_name": str(row[3] or ""),
            "raw_text": str(row[4]),
            "page_url": str(row[5]),
        })
    return messages


def load_events(path: str | Path = DEFAULT_LABELS) -> list[dict[str, object]]:
    source = Path(path)
    if not source.exists():
        return []
    events = []
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or value.get("event") not in LABEL_EVENTS or not value.get("event_id"):
                raise ValueError(f"invalid human-label event at {source}:{line_number}")
            events.append(value)
    effective_label_map(events)
    return events


def effective_label_map(events: Iterable[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    effective: dict[str, dict[str, object]] = {}
    for raw_event in events:
        event = dict(raw_event)
        event_type = event.get("event")
        if event_type == "label_confirmed":
            for message_id in event.get("message_ids", []):
                key = str(message_id)
                if key in effective:
                    raise ValueError(f"message {key} was relabeled without a correction event")
                effective[key] = event
        elif event_type == "label_correction":
            corrects = str(event.get("corrects_event_id") or "")
            if not corrects:
                raise ValueError("label correction is missing corrects_event_id")
            for message_id in event.get("message_ids", []):
                key = str(message_id)
                previous = effective.get(key)
                if not previous or previous.get("event_id") != corrects:
                    raise ValueError(f"correction for {key} does not reference its current label event")
                effective[key] = event
    return effective


def build_queue(messages: Iterable[Mapping[str, object]], events: Iterable[Mapping[str, object]]) -> dict[str, object]:
    message_rows = [dict(message) for message in messages]
    event_rows = [dict(event) for event in events]
    effective = effective_label_map(event_rows)
    labeled_ids = set(effective)
    remaining = [message for message in message_rows if str(message.get("message_id") or "") not in labeled_ids]
    decisions = {str(event.get("group_id")): event for event in event_rows if event.get("event") == "group_decision"}
    pending_groups = []
    confirmed_groups = []
    grouped_ids: set[str] = set()
    split_ids: set[str] = set()
    for group in _candidate_groups(remaining):
        ids = {str(message["message_id"]) for message in group["messages"]}
        decision = decisions.get(str(group["group_id"]))
        if decision and decision.get("decision") == "split":
            split_ids.update(ids)
        elif decision and decision.get("decision") == "confirm":
            confirmed_groups.append(group)
            grouped_ids.update(ids)
        else:
            pending_groups.append(group)
            grouped_ids.update(ids)
    individual_messages = [
        message for message in remaining
        if str(message["message_id"]) not in grouped_ids or str(message["message_id"]) in split_ids
    ]
    return {
        "total_messages": len(message_rows),
        "labeled_messages": sum(str(message.get("message_id") or "") in labeled_ids for message in message_rows),
        "unlabeled_messages": len(remaining),
        "group_candidates": pending_groups,
        "confirmed_groups": confirmed_groups,
        "individual_messages": individual_messages,
    }


def prepare_batch(queue: Mapping[str, object], batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, object]:
    if not DEFAULT_BATCH_SIZE <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch size must be between {DEFAULT_BATCH_SIZE} and {MAX_BATCH_SIZE}")
    units = []
    for state, key in (("candidate", "group_candidates"), ("confirmed", "confirmed_groups")):
        for group in queue.get(key, []):
            messages = list(group["messages"])
            units.append((messages, {"group_id": group["group_id"], "state": state, "message_ids": [str(message["message_id"]) for message in messages]}))
    units.extend(([message], None) for message in queue.get("individual_messages", []))
    units.sort(key=lambda unit: min((str(message.get("timestamp") or ""), str(message.get("message_id") or "")) for message in unit[0]))
    selected: list[dict[str, object]] = []
    groups = []
    for messages, group in units:
        if len(messages) > MAX_BATCH_SIZE:
            raise ValueError(f"group {group['group_id']} exceeds the maximum label batch; split it explicitly")
        if selected and len(selected) + len(messages) > batch_size:
            break
        selected.extend(messages)
        if group:
            groups.append(group)
        if len(selected) >= batch_size:
            break
    context = [
        {key: message.get(key) for key in ("message_id", "timestamp", "author_name", "raw_text")}
        for message in selected
    ]
    return {"batch_size": batch_size, "batch_count": len(context), "message_ids": [str(message["message_id"]) for message in context], "groups": groups, "messages": context}


def record_group(path: str | Path, group_id: str, message_ids: Iterable[str], decision: str, rationale: str, confirmed_by: str = "Greg") -> dict[str, object]:
    ids = _ids(message_ids)
    if len(ids) < 2 or decision not in {"confirm", "split"}:
        raise ValueError("group decisions require at least two message IDs and confirm or split")
    event = _base_event("group_decision", ids, rationale, confirmed_by)
    event.update({"group_id": str(group_id).strip(), "decision": decision})
    _append_event(Path(path), event)
    return event


def record_label(path: str | Path, message_ids: Iterable[str], decision: Mapping[str, object], rationale: str, confirmed_by: str = "Greg", group_id: str | None = None) -> dict[str, object]:
    ids = _ids(message_ids)
    if not ids:
        raise ValueError("a human label requires at least one message ID")
    effective = effective_label_map(load_events(path))
    already = [message_id for message_id in ids if message_id in effective]
    if already:
        raise ValueError(f"already labeled: {', '.join(already)}; use correct-label with the current event ID")
    event = _base_event("label_confirmed", ids, rationale, confirmed_by)
    event.update({"group_id": str(group_id).strip() if group_id else None, "decision": validate_decision(decision)})
    _append_event(Path(path), event)
    return event


def record_correction(path: str | Path, message_ids: Iterable[str], corrects_event_id: str, decision: Mapping[str, object], rationale: str, confirmed_by: str = "Greg") -> dict[str, object]:
    ids = _ids(message_ids)
    effective = effective_label_map(load_events(path))
    if not ids:
        raise ValueError("a correction requires at least one message ID")
    wrong = [message_id for message_id in ids if not effective.get(message_id) or effective[message_id].get("event_id") != corrects_event_id]
    if wrong:
        raise ValueError(f"correction does not reference the current label for: {', '.join(wrong)}")
    event = _base_event("label_correction", ids, rationale, confirmed_by)
    event.update({"corrects_event_id": str(corrects_event_id), "decision": validate_decision(decision)})
    _append_event(Path(path), event)
    return event


def validate_decision(decision: Mapping[str, object]) -> dict[str, str | None]:
    action = str(decision.get("action") or "").strip().upper()
    status = str(decision.get("status") or "").strip().lower()
    symbol = _optional_upper(decision.get("symbol"))
    direction = _optional_upper(decision.get("direction"))
    if action not in ALLOWED_ACTIONS or status not in ALLOWED_STATUSES:
        raise ValueError("unsupported human-label action or status")
    if symbol is not None and symbol not in SUPPORTED_SYMBOLS:
        raise ValueError("human-label symbol must be SPY, QQQ, IWM, or empty")
    if direction is not None and direction not in SUPPORTED_DIRECTIONS:
        raise ValueError("human-label direction must be LONG, SHORT, or empty")
    if action in EXECUTABLE_ACTIONS and (status != "actionable" or not symbol or not direction):
        raise ValueError("executable human labels require actionable status, symbol, and direction")
    if action in {"WATCH", "NONE"} and status != "no_action":
        raise ValueError("WATCH and NONE human labels require no_action status")
    if action == "REVIEW" and status not in {"ambiguous", "insufficient_context"}:
        raise ValueError("REVIEW human labels require ambiguous or insufficient_context status")
    return {"action": action, "symbol": symbol, "direction": direction, "status": status}


def session_queue(lock: Mapping[str, object], database: Path, labels: Path) -> dict[str, object]:
    details = lock.get("details", {})
    start = date.fromisoformat(str(details.get("start_date")))
    end = date.fromisoformat(str(details.get("end_date")))
    queue = build_queue(read_messages(database, start_date=start, end_date=end), load_events(labels))
    batch = prepare_batch(queue, int(details.get("batch_size") or DEFAULT_BATCH_SIZE))
    return {key: queue[key] for key in ("total_messages", "labeled_messages", "unlabeled_messages")} | {"batch": batch}


def _candidate_groups(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized = [_normalize_text(str(message.get("raw_text") or "")) for message in messages]
    links = {index: set() for index in range(len(messages))}
    # ponytail: O(n²) is sufficient for daily chat-sized queues; index only if measured archive growth requires it.
    for left in range(len(messages)):
        for right in range(left + 1, len(messages)):
            if _similar(normalized[left], normalized[right]):
                links[left].add(right)
                links[right].add(left)
    groups = []
    visited: set[int] = set()
    for start in range(len(messages)):
        if start in visited or not links[start]:
            continue
        stack = [start]
        component = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(links[current] - visited)
        members = [messages[index] for index in sorted(component)]
        ids = sorted(str(message["message_id"]) for message in members)
        groups.append({"group_id": "group-" + hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12], "messages": members})
    return groups


def _similar(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right or SequenceMatcher(None, left, right).ratio() >= 0.92:
        return True
    left_tokens, right_tokens = _trigrams(left), _trigrams(right)
    union = left_tokens | right_tokens
    return bool(union) and len(left_tokens & right_tokens) / len(union) >= 0.80


def _normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9@]+", " ", value.casefold()).split())


def _trigrams(value: str) -> set[tuple[str, ...]]:
    tokens = value.split()
    return {tuple(tokens[index:index + 3]) for index in range(max(0, len(tokens) - 2))}


def _local_date(value: str, timezone: ZoneInfo) -> date | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone)
        return parsed.astimezone(timezone).date()
    except ValueError:
        return None


def _optional_upper(value: object) -> str | None:
    result = str(value or "").strip().upper()
    return result or None


def _ids(values: Iterable[str]) -> tuple[str, ...]:
    ids = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if any(not re.search(r"\d{16,}", message_id) for message_id in ids):
        raise ValueError("message IDs must contain an immutable Discord snowflake")
    return ids


def _base_event(event_type: str, message_ids: tuple[str, ...], rationale: str, confirmed_by: str) -> dict[str, object]:
    if not str(rationale).strip():
        raise ValueError("rationale is required")
    return {
        "event": event_type,
        "event_id": uuid4().hex,
        "message_ids": list(message_ids),
        "rationale": str(rationale).strip(),
        "confirmed_by": str(confirmed_by).strip(),
        "confirmed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _append_event(path: Path, event: Mapping[str, object]) -> None:
    append_jsonl_atomic(path, dict(event))


def _add_decision_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--action", choices=sorted(ALLOWED_ACTIONS), required=True)
    parser.add_argument("--symbol")
    parser.add_argument("--direction")
    parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--confirmed-by", default="Greg")


def main() -> int:
    parser = argparse.ArgumentParser(description="V5-owned conversational human labeling operated by V6.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--start-date", type=date.fromisoformat, required=True)
    start.add_argument("--end-date", type=date.fromisoformat, required=True)
    start.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    queue = subparsers.add_parser("queue")
    queue.add_argument("--operation-id", required=True)

    group = subparsers.add_parser("record-group")
    group.add_argument("--operation-id", required=True)
    group.add_argument("--group-id", required=True)
    group.add_argument("--message-id", action="append", required=True)
    group.add_argument("--decision", choices=("confirm", "split"), required=True)
    group.add_argument("--rationale", required=True)
    group.add_argument("--confirmed-by", default="Greg")

    label = subparsers.add_parser("record-label")
    label.add_argument("--operation-id", required=True)
    label.add_argument("--message-id", action="append", required=True)
    label.add_argument("--group-id")
    _add_decision_arguments(label)

    correction = subparsers.add_parser("correct-label")
    correction.add_argument("--operation-id", required=True)
    correction.add_argument("--message-id", action="append", required=True)
    correction.add_argument("--corrects-event-id", required=True)
    _add_decision_arguments(correction)

    pause = subparsers.add_parser("pause")
    pause.add_argument("--operation-id", required=True)

    finish = subparsers.add_parser("finish")
    finish.add_argument("--operation-id", required=True)

    args = parser.parse_args()
    store = OperationStore()
    try:
        if args.command == "start":
            if args.start_date > args.end_date:
                parser.error("beginning date cannot be after ending date")
            if not DEFAULT_BATCH_SIZE <= args.batch_size <= MAX_BATCH_SIZE:
                parser.error(f"batch size must be between {DEFAULT_BATCH_SIZE} and {MAX_BATCH_SIZE}")
            lock = store.begin("labeling", "V6", {"start_date": args.start_date.isoformat(), "end_date": args.end_date.isoformat(), "batch_size": args.batch_size}, persistent=True)
            try:
                with store.labeling_step(str(lock["operation_id"])):
                    result = {"operation_id": lock["operation_id"], **session_queue(lock, args.db, args.labels)}
            except Exception as exc:
                store.finish(str(lock["operation_id"]), "failed", error=str(exc))
                raise
        else:
            operation_id = args.operation_id
            with store.labeling_step(operation_id) as lock:
                if args.command == "queue":
                    result = {"operation_id": operation_id, **session_queue(lock, args.db, args.labels)}
                elif args.command == "record-group":
                    result = record_group(args.labels, args.group_id, args.message_id, args.decision, args.rationale, args.confirmed_by)
                elif args.command == "record-label":
                    decision = {"action": args.action, "symbol": args.symbol, "direction": args.direction, "status": args.status}
                    result = record_label(args.labels, args.message_id, decision, args.rationale, args.confirmed_by, args.group_id)
                elif args.command == "correct-label":
                    decision = {"action": args.action, "symbol": args.symbol, "direction": args.direction, "status": args.status}
                    result = record_correction(args.labels, args.message_id, args.corrects_event_id, decision, args.rationale, args.confirmed_by)
                elif args.command == "pause":
                    queue_state = session_queue(lock, args.db, args.labels)
                    result = store.finish(operation_id, "paused", {key: queue_state[key] for key in ("total_messages", "labeled_messages", "unlabeled_messages")})
                else:
                    queue_state = session_queue(lock, args.db, args.labels)
                    if queue_state["unlabeled_messages"]:
                        raise ValueError(f"{queue_state['unlabeled_messages']} messages remain unlabeled; use pause to release the lock")
                    result = store.finish(operation_id, "completed", {key: queue_state[key] for key in ("total_messages", "labeled_messages", "unlabeled_messages")})
    except (OperationBusy, ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
