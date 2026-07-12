"""Frozen, parser-only V4 comparison baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping

from .core import EXECUTABLE_ACTIONS


def load_lock(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_label_lock(label_lock: Mapping[str, Any], cases_path: str | Path, project_root: str | Path) -> None:
    if label_lock.get("protocol_id") != "v5-prospective-1":
        raise ValueError("label lock uses an unexpected protocol")
    if label_lock.get("labels_locked") is not True:
        raise ValueError("independent labels are not locked")
    if label_lock.get("outcomes_viewed") is not False:
        raise ValueError("label lock was created after outcomes were viewed")
    root = Path(project_root).resolve()
    cases = Path(cases_path).resolve()
    allowed_case_roots = (root / "data" / "holdout", root / "data" / "raw" / "prospective")
    if not any(cases.is_relative_to(allowed_root) for allowed_root in allowed_case_roots):
        raise ValueError("case file is outside approved V5 holdout/prospective directories")
    expected_cases = (root / str(label_lock.get("case_file", ""))).resolve()
    if cases != expected_cases:
        raise ValueError("case path does not match the independent-label lock")
    digest = hashlib.sha256(cases.read_bytes()).hexdigest()
    if digest.casefold() != str(label_lock.get("case_file_sha256", "")).casefold():
        raise ValueError("case file does not match the independent-label lock")
    label_file = (root / str(label_lock.get("label_file", ""))).resolve()
    try:
        label_file.relative_to(root / "data" / "labels")
    except ValueError as exc:
        raise ValueError("label file is outside the V5 labels directory") from exc
    label_hash = hashlib.sha256(label_file.read_bytes()).hexdigest()
    if label_hash.casefold() != str(label_lock.get("label_file_sha256", "")).casefold():
        raise ValueError("label file does not match the independent-label lock")


def verify_v4_source(v4_repository: str | Path, lock: Mapping[str, Any]) -> None:
    repository = Path(v4_repository).resolve()
    head = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head.casefold() != str(lock["git_commit"]).casefold():
        raise ValueError(f"V4 HEAD {head} does not match frozen baseline commit")
    tracked_changes = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    untracked_package_files = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "--others", "--exclude-standard", "--", "BOT_PROJECT/tradebot_v4"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tracked_changes or untracked_package_files:
        raise ValueError("V4 parser package is not a clean frozen checkout")
    for relative_path, expected_hash in lock["files"].items():
        digest = hashlib.sha256((repository / relative_path).read_bytes()).hexdigest()
        if digest.casefold() != str(expected_hash).casefold():
            raise ValueError(f"V4 baseline file changed: {relative_path}")


def load_v4_parser(v4_repository: str | Path, lock: Mapping[str, Any]):
    verify_v4_source(v4_repository, lock)
    bot_project = Path(v4_repository).resolve() / "BOT_PROJECT"
    sys.path.insert(0, str(bot_project))
    try:
        from tradebot_v4.signals.parser import SignalParser

        return SignalParser(ticker_corrections=dict(lock["ticker_corrections"]))
    finally:
        sys.path.pop(0)


def normalize_parsed_signal(parsed: Any) -> dict[str, Any]:
    parser_action = parsed.action.value if parsed.action else None
    if parsed.option:
        symbol = parsed.option.symbol
        direction = parsed.option.stock_direction.value
    else:
        symbol = parsed.target_symbol or None
        direction = parsed.target_direction.value if parsed.target_direction else None

    if not parsed.dispatchable:
        decision = {"action": "NONE", "symbol": None, "direction": None, "status": "no_action"}
    elif parser_action in EXECUTABLE_ACTIONS:
        decision = (
            {"action": parser_action, "symbol": symbol, "direction": direction, "status": "actionable"}
            if symbol and direction
            else {"action": "REVIEW", "symbol": symbol, "direction": direction, "status": "insufficient_context"}
        )
    elif parser_action == "WATCH":
        decision = {"action": "WATCH", "symbol": symbol, "direction": direction, "status": "no_action"}
    elif parsed.option:
        decision = {"action": "REVIEW", "symbol": symbol, "direction": direction, "status": "ambiguous"}
    else:
        decision = {"action": "NONE", "symbol": None, "direction": None, "status": "no_action"}

    return {
        "decision": decision,
        "parser_audit": {
            "action": parser_action,
            "symbol": symbol,
            "direction": direction,
            "dispatchable": bool(parsed.dispatchable),
        },
    }


def run_v4_parser(cases: Iterable[Mapping[str, Any]], parser: Any, *, baseline_id: str, git_commit: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        normalized = normalize_parsed_signal(parser.parse(str(case["raw_text"])))
        results.append({
            "case_id": case["case_id"],
            "cluster_id": case["cluster_id"],
            "source_message_id": case["source_message_id"],
            "input_hash": case["input_hash"],
            "baseline_id": baseline_id,
            "v4_git_commit": git_commit,
            "v4_baseline": normalized["decision"],
            "parser_audit": normalized["parser_audit"],
        })
    return results
