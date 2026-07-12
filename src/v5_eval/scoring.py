"""Offline scoring for saved V5 model responses."""

from __future__ import annotations

from collections import defaultdict
from math import comb
import random
from statistics import mean
from datetime import datetime
import re
from typing import Any, Iterable, Mapping

from .core import EXECUTABLE_ACTIONS, parse_timestamp, validate_decision, validate_model_output

VALID_NOVELTY_CLASSES = ("linguistically_novel", "known_or_near_duplicate", "not_applicable")


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
    if not isinstance(context, Mapping) or not isinstance(context.get("context_required"), bool) or context.get("position_state") not in ("flat", "long", "short", "unknown") or not isinstance(context.get("prior_message_ids"), list) or any(not str(value).strip() for value in context["prior_message_ids"]):
        return False
    if context.get("notes") is not None and not isinstance(context.get("notes"), str):
        return False
    if label.get("adjudication_status") not in ("not_required", "resolved"):
        return False
    if label.get("novelty_class") not in VALID_NOVELTY_CLASSES:
        return False
    try:
        validate_decision(label["decision"])
    except (KeyError, ValueError):
        return False
    return True


def bind_locked_labels(
    records: Iterable[Mapping[str, Any]],
    cases: Iterable[Mapping[str, Any]],
    labels: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach only the exact locked labels and case metadata to saved responses."""
    response_records = [dict(record) for record in records]
    case_records = [dict(case) for case in cases]
    label_records = [dict(label) for label in labels]
    case_ids = [str(case.get("case_id", "")) for case in case_records]
    response_ids = [str(record.get("case_id", "")) for record in response_records]
    label_ids = [str(label.get("case_id", "")) for label in label_records]
    if any(not value for value in case_ids + response_ids + label_ids):
        raise ValueError("case, response, and label records require case_id")
    if len(case_ids) != len(set(case_ids)) or len(response_ids) != len(set(response_ids)) or len(label_ids) != len(set(label_ids)):
        raise ValueError("duplicate case_id in cases, responses, or labels")
    if set(case_ids) != set(response_ids) or set(case_ids) != set(label_ids):
        raise ValueError("responses and labels must exactly cover the locked cases")
    cases_by_id = {str(case["case_id"]): case for case in case_records}
    labels_by_id = {str(label["case_id"]): label for label in label_records}
    bound: list[dict[str, Any]] = []
    for record in response_records:
        case = cases_by_id[str(record["case_id"])]
        label = labels_by_id[str(record["case_id"])]
        if str(record.get("source_message_id", "")) != str(case.get("source_message_id", "")):
            raise ValueError(f"response source_message_id does not match case {record['case_id']}")
        if str(label.get("source_message_id", "")) != str(case.get("source_message_id", "")):
            raise ValueError(f"label source_message_id does not match case {record['case_id']}")
        if not label_ready(label):
            raise ValueError(f"label is not final and blind for case {record['case_id']}")
        record.update({key: case.get(key) for key in ("cluster_id", "cluster_review_status", "contamination_status", "contamination_flags")})
        record["independent_label"] = label
        bound.append(record)
    return bound


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(fraction * (len(values) - 1)))]


def _cluster_accuracy(records: Iterable[Mapping[str, Any]], field: str = "model_correct") -> float | None:
    clusters: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        if record.get(field) is not None:
            clusters[str(record["cluster_id"])].append(bool(record[field]))
    if not clusters:
        return None
    return mean(mean(values) for values in clusters.values())


def exact_binomial_interval(successes: int, total: int, alpha: float = 0.05) -> dict[str, float | None]:
    if total < 1 or successes < 0 or successes > total:
        return {"lower": None, "upper": None}

    def cdf(k: int, probability: float) -> float:
        return sum(comb(total, index) * probability**index * (1 - probability) ** (total - index) for index in range(k + 1))

    def upper_tail(k: int, probability: float) -> float:
        return sum(comb(total, index) * probability**index * (1 - probability) ** (total - index) for index in range(k, total + 1))

    lower = 0.0
    if successes:
        low, high = 0.0, 1.0
        for _ in range(70):
            middle = (low + high) / 2
            if upper_tail(successes, middle) < alpha / 2:
                low = middle
            else:
                high = middle
        lower = (low + high) / 2
    upper = 1.0
    if successes < total:
        low, high = 0.0, 1.0
        for _ in range(70):
            middle = (low + high) / 2
            if cdf(successes, middle) > alpha / 2:
                low = middle
            else:
                high = middle
        upper = (low + high) / 2
    return {"lower": lower, "upper": upper}


def _confusion(records: Iterable[Mapping[str, Any]], decision_field: str = "normalized_decision") -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in records:
        gold = _decision(row.get("independent_label"))
        predicted = _decision(row.get(decision_field))
        matrix[str(gold.get("action") if gold else "MISSING")][str(predicted.get("action") if predicted else "INVALID")] += 1
    return {gold: dict(values) for gold, values in matrix.items()}


def _field_accuracy(records: list[Mapping[str, Any]], field: str, decision_field: str) -> float | None:
    comparisons = []
    for row in records:
        gold = _decision(row.get("independent_label"))
        predicted = _decision(row.get(decision_field))
        if gold and (field == "action" or gold.get(field) is not None):
            comparisons.append(bool(predicted and predicted.get(field) == gold.get(field)))
    return mean(comparisons) if comparisons else None


def _protocol_decision(report: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict[str, Any]:
    counts = report["sample_counts"]
    minimums = protocol["minimum_sample"]
    minimum_failures = [key for key, minimum in minimums.items() if key != "scope" and counts.get(key, 0) < minimum]
    prerequisites = []
    if report["missing_latency"]:
        prerequisites.append("missing_latency")
    if report["missing_v4_baseline"]:
        prerequisites.append("missing_v4_baseline")
    if report["unresolved_contamination"]:
        prerequisites.append("unresolved_contamination")
    if report["novel_paired_cluster_bootstrap"]["lower"] is None or report["paired_cluster_bootstrap"]["lower"] is None:
        prerequisites.append("missing_paired_comparison")
    if minimum_failures or prerequisites:
        return {"status": "INCONCLUSIVE", "minimum_failures": minimum_failures, "prerequisite_failures": prerequisites, "gates": {}}
    gates_config = protocol["promotion_gates"]
    novel_difference = report["novel_cluster_weighted_accuracy"] - report["v4_novel_cluster_weighted_accuracy"]
    gates = {
        "novel_improvement": novel_difference >= gates_config["novel_accuracy_improvement_percentage_points"] / 100 and report["novel_paired_cluster_bootstrap"]["lower"] > 0,
        "overall_noninferiority": report["paired_cluster_bootstrap"]["lower"] >= gates_config["overall_noninferiority_margin_percentage_points"] / 100,
        "critical_errors": report["critical_errors"] <= gates_config["critical_errors"] and report["critical_errors"] <= report["v4_critical_errors"],
        "safe_handling": report["safe_handling_rate"] is not None and report["safe_handling_rate"] >= gates_config["non_actionable_safe_handling_minimum_rate"],
        "actionable_recall": report["actionable_recall"] is not None and report["actionable_recall"] >= gates_config["actionable_recall_minimum_rate"] and report["intervals"]["actionable_cluster_recall"]["lower"] >= gates_config["actionable_recall_ci_lower_bound_minimum"],
        "structured_output": report["structured_output_rate"] >= gates_config["structured_output_minimum_rate"],
        "runtime_errors": report["timeout_or_runtime_error_rate"] <= gates_config["timeout_and_runtime_error_maximum_rate"],
        "latency": report["p95_latency_ms"] <= gates_config["p95_latency_maximum_ms"],
    }
    return {"status": "PASS" if all(gates.values()) else "FAIL", "minimum_failures": [], "prerequisite_failures": [], "gates": gates}


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


def score_records(records: Iterable[Mapping[str, Any]], protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    actionable_cluster_successes = sum(all(values) for values in actionable_clusters.values())
    eligible_labels = [_decision(row["independent_label"]) for row in eligible]
    novel_bootstrap = paired_cluster_bootstrap(novel)
    report = {
        "attempted": attempted,
        "eligible_clear": len(eligible),
        "novel_eligible": len(novel),
        "message_weighted_accuracy": mean(row["model_correct"] for row in eligible) if eligible else None,
        "v4_message_weighted_accuracy": mean(row["v4_correct"] for row in eligible) if eligible and all(row["v4_correct"] is not None for row in eligible) else None,
        "cluster_weighted_accuracy": _cluster_accuracy(eligible),
        "v4_cluster_weighted_accuracy": _cluster_accuracy(eligible, "v4_correct"),
        "novel_cluster_weighted_accuracy": _cluster_accuracy(novel),
        "v4_novel_cluster_weighted_accuracy": _cluster_accuracy(novel, "v4_correct"),
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
        "missing_latency": sum(row.get("latency_ms") is None for row in evaluated),
        "missing_v4_baseline": sum(row.get("v4_baseline") is None for row in evaluated),
        "unresolved_contamination": sum(row.get("contamination_status") == "unresolved" for row in evaluated),
        "paired_cluster_bootstrap": paired_cluster_bootstrap(eligible),
        "novel_paired_cluster_bootstrap": novel_bootstrap,
        "confusion_matrix_action": _confusion(eligible),
        "v4_confusion_matrix_action": _confusion(eligible, "v4_baseline"),
        "field_accuracy": {
            field: _field_accuracy(eligible, field, "normalized_decision") for field in ("action", "symbol", "direction")
        },
        "v4_field_accuracy": {
            field: _field_accuracy(eligible, field, "v4_baseline") for field in ("action", "symbol", "direction")
        },
        "intervals": {
            "message_accuracy": exact_binomial_interval(sum(row["model_correct"] for row in eligible), len(eligible)),
            "v4_message_accuracy": exact_binomial_interval(sum(bool(row["v4_correct"]) for row in eligible), len(eligible)) if eligible and all(row["v4_correct"] is not None for row in eligible) else {"lower": None, "upper": None},
            "safe_handling": exact_binomial_interval(safe_correct, safe_total),
            "actionable_cluster_recall": exact_binomial_interval(actionable_cluster_successes, len(actionable_clusters)),
            "structured_output": exact_binomial_interval(sum(row["parse_status"] == "ok" for row in evaluated), attempted),
            "runtime_error": exact_binomial_interval(sum(row["parse_status"] in ("timeout", "error") for row in evaluated), attempted),
            "false_execution": exact_binomial_interval(false_executions, safe_total),
        },
        "critical_error_upper_bound_rough": 3 / attempted if attempted and not critical_errors else None,
        "sample_counts": {
            "unique_messages": len(eligible),
            "independent_clusters": len({str(row["cluster_id"]) for row in eligible}),
            "distinct_trading_days": len({parse_timestamp(str(row["message_timestamp"])).date().isoformat() for row in eligible if row.get("message_timestamp")}),
            "actionable": sum(label.get("status") == "actionable" for label in eligible_labels),
            "non_actionable": sum(label.get("status") != "actionable" for label in eligible_labels),
            "linguistically_novel": len(novel),
            "linguistically_novel_clusters": len({str(row["cluster_id"]) for row in novel}),
            "ambiguous_or_context_dependent": sum(label.get("status") in ("ambiguous", "insufficient_context") or label.get("required_context", {}).get("context_required") is True for label in eligible_labels),
        },
    }
    if protocol is not None:
        report["protocol_decision"] = _protocol_decision(report, protocol)
    return report
