"""Pre-confirmation import, cluster-review, and label-lock helpers."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Iterable, Mapping

from .core import SOURCE_CHANNEL_URL_SHA256, STRESS_CHANNEL_URL_SHA256, sha256_text
from .scoring import label_ready

RAW_KEYS = {"browser_time", "event", "has_everyone", "message_id", "page_title", "page_url", "raw_text", "timestamp"}
PROHIBITED_RAW_KEYS = {"decision", "parser", "interpretation", "shadow", "model", "label", "expected"}


def select_prospective_records(records: Iterable[Mapping[str, Any]], confirmation_start: datetime, *, with_audit: bool = False):
    selected: list[dict[str, Any]] = []
    audit = {"input_records": 0, "selected_records": 0, "stress_channel_excluded": 0, "wrong_or_missing_source_excluded": 0, "pre_boundary_excluded": 0, "malformed_or_empty_excluded": 0}
    for record in records:
        audit["input_records"] += 1
        unknown = set(record) - RAW_KEYS
        if unknown:
            forbidden = sorted(key for key in unknown if any(term in key.casefold() for term in PROHIBITED_RAW_KEYS))
            label = ", ".join(forbidden or sorted(unknown))
            raise ValueError(f"raw snapshot contains unsupported fields: {label}")
        page_url = str(record.get("page_url", ""))
        if not page_url:
            audit["wrong_or_missing_source_excluded"] += 1
            continue
        if sha256_text(page_url).casefold() != SOURCE_CHANNEL_URL_SHA256.casefold():
            if page_url and sha256_text(page_url).casefold() == STRESS_CHANNEL_URL_SHA256.casefold():
                audit["stress_channel_excluded"] += 1
                continue
            audit["wrong_or_missing_source_excluded"] += 1
            continue
        try:
            timestamp = datetime.fromisoformat(str(record.get("timestamp", "")).replace("Z", "+00:00"))
        except ValueError:
            audit["malformed_or_empty_excluded"] += 1
            continue
        if timestamp.tzinfo is None or timestamp < confirmation_start:
            audit["pre_boundary_excluded"] += 1
            continue
        if not record.get("message_id") or not str(record.get("raw_text", "")).strip():
            audit["malformed_or_empty_excluded"] += 1
            continue
        selected.append(dict(record))
    selected = sorted(selected, key=lambda row: (str(row["timestamp"]), str(row["message_id"])))
    audit["selected_records"] = len(selected)
    return (selected, audit) if with_audit else selected


def apply_cluster_reviews(cases: Iterable[Mapping[str, Any]], decisions: Mapping[str, str]) -> list[dict[str, Any]]:
    output = [dict(case) for case in cases]
    for case in output:
        decision = decisions.get(str(case["cluster_id"]), "pending")
        if decision == "confirm":
            case["cluster_review_status"] = "confirmed"
        elif decision == "split":
            case["cluster_id"] = f"{case['cluster_id']}-{case['case_id']}"
            case["cluster_review_status"] = "confirmed_split"
        else:
            case["cluster_review_status"] = "pending_review"
    return output


def build_label_queue(cases: Iterable[Mapping[str, Any]], *, seed: int = 20260713) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for case in cases:
        if case.get("cluster_review_status") not in ("confirmed", "confirmed_split"):
            raise ValueError("all clusters must be reviewed before label queue creation")
        queue.append({
            "case_id": case["case_id"],
            "cluster_id": case["cluster_id"],
            "source_message_id": case["source_message_id"],
            "message_timestamp": case["message_timestamp"],
            "raw_text": case["raw_text"],
            "recent_messages": case.get("recent_messages", []),
            "label_version": 1,
            "labeler_id": "",
            "label_pass": "primary",
            "blind_declaration": False,
            "allowed_context_hash": "",
            "required_context": {"context_required": False, "position_state": "unknown", "prior_message_ids": [], "notes": None},
            "decision": None,
            "novelty_class": None,
            "confidence": None,
            "adjudication_status": "pending",
            "rationale": "",
        })
    random.Random(seed).shuffle(queue)
    return queue


def build_label_lock(*, cases_path: str | Path, labels_path: str | Path, root: str | Path, protocol_id: str = "v5-prospective-1") -> dict[str, Any]:
    root_path = Path(root).resolve()
    cases = Path(cases_path).resolve()
    labels = Path(labels_path).resolve()
    if not cases.is_relative_to(root_path / "data" / "holdout") and not cases.is_relative_to(root_path / "data" / "raw" / "prospective"):
        raise ValueError("case file must be inside V5 holdout or prospective data")
    if not labels.is_relative_to(root_path / "data" / "labels"):
        raise ValueError("label file must be inside V5 labels data")
    case_records = [json.loads(line) for line in cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    label_records = [json.loads(line) for line in labels.read_text(encoding="utf-8").splitlines() if line.strip()]
    case_id_list = [str(case["case_id"]) for case in case_records]
    if len(case_id_list) != len(set(case_id_list)):
        raise ValueError("duplicate case_id")
    case_ids = set(case_id_list)
    label_ids = [str(label.get("case_id")) for label in label_records]
    if len(label_ids) != len(set(label_ids)):
        raise ValueError("duplicate label case_id")
    labels_by_id = dict(zip(label_ids, label_records))
    if case_ids != set(labels_by_id):
        raise ValueError("labels do not exactly cover the case file")
    if any(str(labels_by_id[case["case_id"]].get("source_message_id")) != str(case.get("source_message_id")) for case in case_records):
        raise ValueError("label source_message_id does not match case")
    if any(case.get("cluster_review_status") not in ("confirmed", "confirmed_split") for case in case_records):
        raise ValueError("unreviewed cluster remains in case file")
    if any(not label_ready(label) for label in labels_by_id.values()):
        raise ValueError("one or more labels are not final blind labels")
    try:
        case_file = cases.relative_to(root_path).as_posix()
        label_file = labels.relative_to(root_path).as_posix()
    except ValueError as exc:
        raise ValueError("case and label files must be inside the V5 workspace") from exc
    return {
        "protocol_id": protocol_id,
        "labels_locked": True,
        "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "case_file": case_file,
        "case_file_sha256": hashlib.sha256(cases.read_bytes()).hexdigest(),
        "label_file": label_file,
        "label_file_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
        "outcomes_viewed": False,
    }
