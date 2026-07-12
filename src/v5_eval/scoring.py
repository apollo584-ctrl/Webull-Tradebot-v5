"""Offline scoring for saved V5 model responses."""

from __future__ import annotations

from collections import defaultdict
import random
from statistics import mean
from datetime import datetime
import re
from typing import Any, Iterable, Mapping

from .core import EXECUTABLE_ACTIONS, parse_timestamp, validate_decision, validate_model_output


def _decision(value: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not value:
        return None
    return value.get("decision", value) if isinstance(value, Mapping) else None


def _exact(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> bool:
    if not left or not right:
        return False
    if left.get("action") != right.get("action") or left.get("status") != right.get("status"):
        return False
    if left.get("status") == "actionable":
        return left.get("symbol") == right.get("symbol") and left.get("direction") == right.get("direction")
    return True


def _critical(label: Mapping[str, Any], model: Mapping[str, Any] | None) -> bool:
    gold = _decision(label)
    if not gold or not model:
        return False
    if gold.get("status") == "actionable":
        return model.get("action") in EXECUTABLE_ACTIONS and not _exact(gold, model)
    return model.get("action") in EXECUTABLE_ACTIONS or model.get("status") == "actionable"


def _false_execution(label: Mapping[str, Any], decision: Mapping[str, Any] | None) -> bool:
    gold = _decision(label)
    return bool(gold and gold.get("status") != "actionable" and decision and decision.get("action") in EXECUTABLE_ACTIONS)


def label_ready(label: Any) -> bool:
    if not isinstance(label, Mapping) or label.get("blind_declaration") is not True:
        return False
    if not str(label.get("case_id", "")).strip() or not str(label.get("source_message_id", "")).strip():
        return False
    if not isinstance(label.get("label_version"), int) or label.get("label_version") < 1:
        return False
    try:
        parse_timestamp(str(label["labeled_at"]))
    except (KeyError, ValueError):
        return False
    if not str(label.get("labeler_id", "")).strip() or label.get("label_pass") not in ("primary", "secondary", "adjudication"):
        return False
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", str(label.get("allowed_context_hash", ""))):
        return False
    if label.get("confidence") not in ("high", "medium", "low") or not str(label.get("rationale", "")).strip():
        return False
    context = label.get("required_context")
    if not isinstance(context, Mapping) or context.get("position_state") not in ("flat", "long", "short", "unknown") or not isinstance(context.get("prior_message_ids"), list):
        return False
    if label.get("adjudication_status") not in ("not_required", "resolved"):
        return False
    if label.get("novelty_class") == "unresolved":
        return False
    try:
        validate_decision(label["decision"])
    except (KeyError, ValueError):
        return False
    return True


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(fraction * (len(values) - 1)))]


def _cluster_accuracy(records: Iterable[Mapping[str, Any]]) -> float | None:
    clusters: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        clusters[str(record["cluster_id"])].append(bool(record["model_correct"]))
    if not clusters:
        return None
    return mean(mean(values) for values in clusters.values())


def paired_cluster_bootstrap(records: list[Mapping[str, Any]], *, seed: int = 20260713, resamples: int = 10000) -> dict[str, float | None]:
    clusters: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for record in records:
        if record.get("v4_correct") is not None:
            clusters[str(record["cluster_id"])].append((bool(record["model_correct"]), bool(record["v4_correct"])))
    cluster_values = list(clusters.values())
    if not cluster_values:
        return {"lower": None, "upper": None}
    rng = random.Random(seed)
    differences: list[float] = []
    for _ in range(resamples):
        sample = [cluster_values[rng.randrange(len(cluster_values))] for _ in cluster_values]
        model = mean(mean(int(pair[0]) for pair in cluster) for cluster in sample)
        baseline = mean(mean(int(pair[1]) for pair in cluster) for cluster in sample)
        differences.append(model - baseline)
    return {"lower": _percentile(differences, 0.025), "upper": _percentile(differences, 0.975)}


def score_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    evaluated: list[dict[str, Any]] = []
    attempted = 0
    critical_errors = v4_critical_errors = 0
    false_executions = v4_false_executions = 0
    safe_total = safe_correct = actionable_total = actionable_recalled = 0
    v4_safe_correct = v4_actionable_recalled = 0
    for source in records:
        attempted += 1
        saved_status = source.get("parse_status")
        if saved_status in ("timeout", "error", "invalid_json", "invalid_decision"):
            parsed = {"parse_status": saved_status, "decision": None}
        elif source.get("normalized_decision") is not None:
            try:
                parsed = {"parse_status": "ok", "decision": validate_decision(source["normalized_decision"])}
            except ValueError:
                parsed = {"parse_status": "invalid_decision", "decision": None}
        else:
            parsed = validate_model_output(source.get("model_output"))
        model = parsed["decision"]
        label = _decision(source.get("independent_label"))
        model_correct = bool(label and model and _exact(label, model))
        v4 = _decision(source.get("v4_baseline"))
        row = dict(source)
        row.update({"parse_status": parsed["parse_status"], "normalized_decision": model, "model_correct": model_correct})
        row["v4_correct"] = bool(label and v4 and _exact(label, v4)) if v4 else None
        evaluated.append(row)
        if label and model and _critical(label, model):
            critical_errors += 1
        if label and v4 and _critical(label, v4):
            v4_critical_errors += 1
        if label and _false_execution(label, model):
            false_executions += 1
        if label and _false_execution(label, v4):
            v4_false_executions += 1
        if label and label.get("status") in ("no_action", "ambiguous", "insufficient_context"):
            safe_total += 1
            if model and model.get("status") != "actionable":
                safe_correct += 1
            if v4 and v4.get("status") != "actionable":
                v4_safe_correct += 1
        if label and label.get("status") == "actionable":
            actionable_total += 1
            if model and model.get("status") == "actionable":
                actionable_recalled += 1
            if v4 and v4.get("status") == "actionable":
                v4_actionable_recalled += 1

    eligible = [row for row in evaluated if row.get("contamination_status") == "clear" and row.get("cluster_review_status") in ("confirmed", "confirmed_split") and label_ready(row.get("independent_label"))]
    novel = [row for row in eligible if row["independent_label"].get("novelty_class") == "linguistically_novel"]
    actionable_clusters: dict[str, list[bool]] = defaultdict(list)
    v4_actionable_clusters: dict[str, list[bool]] = defaultdict(list)
    for row in eligible:
        label = _decision(row["independent_label"])
        if label and label.get("status") == "actionable":
            actionable_clusters[str(row["cluster_id"])].append(bool(row["normalized_decision"] and row["normalized_decision"].get("status") == "actionable"))
            v4 = _decision(row.get("v4_baseline"))
            v4_actionable_clusters[str(row["cluster_id"])].append(bool(v4 and v4.get("status") == "actionable"))
    actionable_cluster_values = [mean(values) for values in actionable_clusters.values()]
    v4_actionable_cluster_values = [mean(values) for values in v4_actionable_clusters.values()]
    return {
        "attempted": attempted,
        "eligible_clear": len(eligible),
        "novel_eligible": len(novel),
        "message_weighted_accuracy": mean(row["model_correct"] for row in eligible) if eligible else None,
        "cluster_weighted_accuracy": _cluster_accuracy(eligible),
        "novel_cluster_weighted_accuracy": _cluster_accuracy(novel),
        "critical_errors": critical_errors,
        "v4_critical_errors": v4_critical_errors,
        "false_execution_rate": false_executions / safe_total if safe_total else None,
        "v4_false_execution_rate": v4_false_executions / safe_total if safe_total else None,
        "safe_handling_rate": safe_correct / safe_total if safe_total else None,
        "v4_safe_handling_rate": v4_safe_correct / safe_total if safe_total else None,
        "actionable_recall": mean(actionable_cluster_values) if actionable_cluster_values else None,
        "v4_actionable_recall": mean(v4_actionable_cluster_values) if v4_actionable_cluster_values else None,
        "structured_output_rate": sum(row["parse_status"] == "ok" for row in evaluated) / attempted if attempted else None,
        "timeout_or_runtime_error_rate": sum(row["parse_status"] in ("timeout", "error") for row in evaluated) / attempted if attempted else None,
        "p95_latency_ms": _percentile([float(row["latency_ms"]) for row in evaluated if row.get("latency_ms") is not None], 0.95),
        "paired_cluster_bootstrap": paired_cluster_bootstrap(eligible),
    }
