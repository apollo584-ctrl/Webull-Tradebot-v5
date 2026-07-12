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
CONTAMINATION_FLAGS = {"historical_exact_match", "historical_near_duplicate", "prior_model_review", "manual_correction", "prompt_example", "parser_rule_tuning", "threshold_tuning"}


def _contamination_ready(case: Mapping[str, Any], reference_hash: str) -> bool:
    review = case.get("contamination_review")
    if case.get("contamination_status") not in ("clear", "excluded") or not isinstance(review, Mapping):
        return False
    try:
        reviewed_at = datetime.fromisoformat(str(review.get("reviewed_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return False
    flags = set(case.get("contamination_flags", []))
    status_valid = not flags if case["contamination_status"] == "clear" else bool(flags) and flags <= CONTAMINATION_FLAGS
    return bool(status_valid and reviewed_at.tzinfo is not None and str(review.get("reference_hash", "")).casefold() == reference_hash.casefold() and str(review.get("reviewer_id", "")).strip() and str(review.get("rationale", "")).strip())


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


def apply_cluster_reviews(cases: Iterable[Mapping[str, Any]], decisions: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = [dict(case) for case in cases]
    groups: dict[str, list[dict[str, Any]]] = {}
    for case in output:
        groups.setdefault(str(case["cluster_id"]), []).append(case)
    for cluster_id, group in groups.items():
        if cluster_id not in decisions:
            continue
        decision = decisions[cluster_id]
        if decision == "confirm":
            for case in group:
                case["cluster_review_status"] = "confirmed"
        elif isinstance(decision, Mapping):
            case_ids = {str(case["case_id"]) for case in group}
            if set(map(str, decision)) != case_ids or any(not str(value).strip() for value in decision.values()):
                raise ValueError(f"split groups must exactly cover cluster {cluster_id}")
            for case in group:
                subgroup = str(decision[str(case["case_id"])]).strip()
                case["cluster_id"] = f"{cluster_id}-{sha256_text(subgroup)[:16]}"
                case["cluster_review_status"] = "confirmed_split"
        else:
            for case in group:
                case["cluster_review_status"] = "pending_review"
    return output


def apply_contamination_reviews(cases: Iterable[Mapping[str, Any]], decisions: Mapping[str, Mapping[str, Any]], reference_hash: str) -> list[dict[str, Any]]:
    output = [dict(case) for case in cases]
    case_ids = {str(case["case_id"]) for case in output}
    if set(map(str, decisions)) != case_ids:
        raise ValueError("contamination decisions must exactly cover every case")
    for case in output:
        decision = decisions[str(case["case_id"])]
        status = decision.get("status")
        flags = list(decision.get("flags", []))
        try:
            reviewed_at = datetime.fromisoformat(str(decision.get("reviewed_at", "")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid contamination review timestamp for case {case['case_id']}") from exc
        if reviewed_at.tzinfo is None or str(decision.get("reference_hash", "")).casefold() != reference_hash.casefold() or not str(decision.get("reviewer_id", "")).strip() or not str(decision.get("rationale", "")).strip():
            raise ValueError(f"incomplete contamination audit for case {case['case_id']}")
        if status == "clear" and not flags:
            case["contamination_status"] = "clear"
            case["contamination_flags"] = []
        elif status == "excluded" and flags and set(flags) <= CONTAMINATION_FLAGS:
            case["contamination_status"] = "excluded"
            case["contamination_flags"] = sorted(set(flags))
        else:
            raise ValueError(f"invalid contamination decision for case {case['case_id']}")
        case["contamination_review"] = {"reference_hash": reference_hash, "reviewer_id": str(decision["reviewer_id"]), "reviewed_at": reviewed_at.isoformat(), "rationale": str(decision["rationale"])}
    return output


def build_label_queue(cases: Iterable[Mapping[str, Any]], reference_hash: str, *, seed: int = 20260713) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for case in cases:
        if case.get("cluster_review_status") not in ("confirmed", "confirmed_split"):
            raise ValueError("all clusters must be reviewed before label queue creation")
        if not _contamination_ready(case, reference_hash):
            raise ValueError("all cases require final contamination review before labeling")
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
    if any(case.get("contamination_status") not in ("clear", "excluded") for case in case_records):
        raise ValueError("unresolved contamination remains in case file")
    reference_hash = hashlib.sha256((root_path / "data" / "source_manifest.json").read_bytes()).hexdigest()
    if any(not _contamination_ready(case, reference_hash) for case in case_records):
        raise ValueError("contamination review provenance is missing or mismatched")
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
