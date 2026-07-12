"""Offline V5 case preparation and blind-request validation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
import unicodedata

ALLOWED_ACTIONS = ("OPEN", "ADD", "TRIM", "SELL", "WATCH", "NONE", "REVIEW")
EXECUTABLE_ACTIONS = ("OPEN", "ADD", "TRIM", "SELL")
ALLOWED_SYMBOLS = ("SPY", "QQQ", "IWM")
ALLOWED_DIRECTIONS = ("LONG", "SHORT")
ALLOWED_STATUSES = ("actionable", "no_action", "ambiguous", "insufficient_context")
SOURCE_CHANNEL_URL_SHA256 = "B585176665DD638BB6E8682C48F8469131AF9A5101D64619B8AD323117BE15BA"
STRESS_CHANNEL_URL_SHA256 = "A25E5AC4EB5DAA89FAE3B915289C60A5D33978F4B638DE89CC0B3E48D9E3E128"
RAW_RECORD_KEYS = {"browser_time", "event", "has_everyone", "message_id", "page_title", "page_url", "raw_text", "timestamp"}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"record is not an object at {path}:{line_number}")
            records.append(value)
    return records


def _text_ngrams(value: str, size: int = 3) -> set[str]:
    padded = f"  {value}  "
    return {padded[index : index + size] for index in range(len(padded) - size + 1)}


def _near_duplicate(left: str, right: str) -> bool:
    if SequenceMatcher(None, left, right).ratio() >= 0.92:
        return True
    a, b = _text_ngrams(left), _text_ngrams(right)
    return bool(a and b) and len(a & b) / len(a | b) >= 0.80


def _source_hash(record: Mapping[str, Any]) -> str | None:
    page_url = record.get("page_url")
    return sha256_text(str(page_url)) if page_url else None


def canonicalize_records(
    records: Iterable[Mapping[str, Any]],
    *,
    confirmation_start: datetime | None = None,
    source_channel_url_sha256: str = SOURCE_CHANNEL_URL_SHA256,
    manifest_verified: bool = False,
) -> list[dict[str, Any]]:
    """Create deterministic cases from raw messages without parser/model fields."""
    prepared: list[dict[str, Any]] = []
    for record in records:
        unknown_keys = set(record) - RAW_RECORD_KEYS
        if unknown_keys:
            raise ValueError(f"raw snapshot contains unsupported fields: {', '.join(sorted(unknown_keys))}")
        message_id = str(record.get("message_id", "")).strip()
        raw_text = str(record.get("raw_text", "")).strip()
        timestamp_value = str(record.get("timestamp", "")).strip()
        if not message_id or not raw_text or not timestamp_value:
            continue
        timestamp = parse_timestamp(timestamp_value)
        if confirmation_start and timestamp < confirmation_start:
            continue
        observed_source_hash = _source_hash(record)
        if observed_source_hash and observed_source_hash.casefold() != source_channel_url_sha256.casefold():
            if observed_source_hash.casefold() == STRESS_CHANNEL_URL_SHA256.casefold():
                continue
            raise ValueError(f"unexpected source channel for message {message_id}")
        if not observed_source_hash and not manifest_verified:
            raise ValueError("source verification requires page_url or a verified capture manifest")
        prepared.append({
            "message_id": message_id,
            "timestamp": timestamp,
            "raw_text": raw_text,
            "normalized_text": normalize_text(raw_text),
            "source_channel_url_sha256": source_channel_url_sha256,
        })

    # ponytail: the V5 source is small enough for deterministic O(n²) clustering.
    prepared.sort(key=lambda item: (item["timestamp"], item["message_id"]))
    canonical_by_id: dict[str, dict[str, Any]] = {}
    for item in prepared:
        canonical_by_id.setdefault(item["message_id"], item)

    items = list(canonical_by_id.values())
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(items)):
        for right in range(left + 1, len(items)):
            if _near_duplicate(items[left]["normalized_text"], items[right]["normalized_text"]):
                union(left, right)
    root_to_cluster: dict[int, str] = {}
    for index in range(len(items)):
        root = find(index)
        root_to_cluster.setdefault(root, f"cluster-{len(root_to_cluster) + 1:04d}")

    cases: list[dict[str, Any]] = []
    prior_messages: list[dict[str, str]] = []
    for index, item in enumerate(items):
        normalized = item["normalized_text"]
        cluster_id = root_to_cluster[find(index)]
        case_id = f"v5-{sha256_text(item['source_channel_url_sha256'] + ':' + item['message_id'])[:16]}"
        cases.append({
            "case_id": case_id,
            "cluster_id": cluster_id,
            "source_message_id": item["message_id"],
            "message_timestamp": item["timestamp"].isoformat(),
            "raw_text": item["raw_text"],
            "normalized_text": normalized,
            "input_hash": sha256_text(item["message_id"] + "\n" + item["timestamp"].isoformat() + "\n" + item["raw_text"]),
            "source_channel_url_sha256": source_channel_url_sha256,
            "recent_messages": prior_messages[-10:],
            "cluster_review_status": "pending_review",
            "contamination_status": "unresolved",
            "contamination_flags": ["unresolved_provenance"],
        })
        prior_messages.append({
            "source_message_id": item["message_id"],
            "message_timestamp": item["timestamp"].isoformat(),
            "raw_text": item["raw_text"],
        })
    return cases


def validate_capture_manifest(manifest: Mapping[str, Any]) -> None:
    required = ("capture_id", "imported_at", "snapshot_path", "snapshot_sha256", "source_channel_url_sha256", "time_start", "time_end", "record_count", "parser_or_model_fields_absent", "capture_audit")
    if any(key not in manifest for key in required):
        raise ValueError("capture manifest is missing required fields")
    for key in ("imported_at", "time_start", "time_end"):
        parse_timestamp(str(manifest[key]))
    if not str(manifest["capture_id"]).strip() or not isinstance(manifest["record_count"], int) or manifest["record_count"] < 1:
        raise ValueError("capture manifest has invalid identity or record count")
    audit = manifest["capture_audit"]
    audit_keys = ("input_records", "selected_records", "stress_channel_excluded", "wrong_or_missing_source_excluded", "pre_boundary_excluded", "malformed_or_empty_excluded")
    if not isinstance(audit, Mapping) or any(key not in audit for key in audit_keys) or any(not isinstance(audit[key], int) or audit[key] < 0 for key in audit_keys):
        raise ValueError("capture manifest has invalid audit counters")
    if audit["selected_records"] != manifest["record_count"] or audit["selected_records"] > audit["input_records"]:
        raise ValueError("capture manifest audit does not match record count")
    snapshot_path = Path(str(manifest["snapshot_path"]))
    if snapshot_path.is_absolute() or ".." in snapshot_path.parts or not str(manifest["snapshot_path"]).startswith("data/raw/prospective/"):
        raise ValueError("capture snapshot must be V5-owned prospective data")
    if str(manifest["source_channel_url_sha256"]).casefold() != SOURCE_CHANNEL_URL_SHA256.casefold():
        raise ValueError("capture manifest is for the wrong source channel")
    if manifest["parser_or_model_fields_absent"] is not True:
        raise ValueError("capture manifest does not declare a blind raw snapshot")


def _valid_decision(decision: Mapping[str, Any]) -> bool:
    action = decision.get("action")
    symbol = decision.get("symbol")
    direction = decision.get("direction")
    status = decision.get("status")
    if action not in ALLOWED_ACTIONS or status not in ALLOWED_STATUSES:
        return False
    if action in EXECUTABLE_ACTIONS:
        return status == "actionable" and symbol in ALLOWED_SYMBOLS and direction in ALLOWED_DIRECTIONS
    if action in ("WATCH", "NONE"):
        return status == "no_action" and (symbol is None or symbol in ALLOWED_SYMBOLS) and (direction is None or direction in ALLOWED_DIRECTIONS)
    return status in ("ambiguous", "insufficient_context") and (symbol is None or symbol in ALLOWED_SYMBOLS) and (direction is None or direction in ALLOWED_DIRECTIONS)


def validate_decision(decision: Any) -> dict[str, Any]:
    if not isinstance(decision, dict) or not _valid_decision(decision):
        raise ValueError("invalid action/status/symbol/direction combination")
    return {key: decision.get(key) for key in ("action", "symbol", "direction", "status")}


def build_blind_request(
    case: Mapping[str, Any],
    *,
    recent_messages: Iterable[str] = (),
    position_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the only model-facing payload; parser and expected-answer fields are never copied."""
    if not recent_messages and case.get("recent_messages"):
        recent_messages = [str(item.get("raw_text", "")) for item in case["recent_messages"]]
    safe_position = dict(position_state or {})
    allowed_position_keys = {"symbol", "direction", "quantity", "as_of"}
    if set(safe_position) - allowed_position_keys:
        raise ValueError("position_state contains a prohibited or unknown field")
    return {
        "message": str(case["raw_text"]),
        "message_timestamp": str(case["message_timestamp"]),
        "recent_messages": [str(message) for message in recent_messages],
        "position_state": safe_position,
        "allowed_actions": list(ALLOWED_ACTIONS),
        "allowed_symbols": list(ALLOWED_SYMBOLS),
        "allowed_directions": list(ALLOWED_DIRECTIONS),
        "required_output": ["action", "symbol", "direction", "status"],
    }


def validate_model_output(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {"parse_status": "invalid_json", "decision": None}
    if not isinstance(value, dict):
        return {"parse_status": "invalid_decision", "decision": None}
    decision = value.get("decision", value)
    try:
        return {"parse_status": "ok", "decision": validate_decision(decision)}
    except ValueError:
        return {"parse_status": "invalid_decision", "decision": None}
