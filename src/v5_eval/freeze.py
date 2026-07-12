"""Freeze and verify the one preselected confirmatory model candidate."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(path: Path) -> str:
    """Hash text with platform line endings normalized to LF."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _inside(root: Path, path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("candidate files must be inside the V5 workspace")
    return resolved


def build_candidate_lock(config: Mapping[str, Any], prompt_path: str | Path, output_schema_path: str | Path, root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    required = ("model_id", "quantization", "runtime", "runtime_version", "generation_settings", "timeout_ms")
    if any(key not in config for key in required) or any(not str(config[key]).strip() for key in required[:4]):
        raise ValueError("candidate configuration is incomplete")
    if not isinstance(config["generation_settings"], Mapping) or not isinstance(config["timeout_ms"], int) or config["timeout_ms"] < 1:
        raise ValueError("candidate generation settings or timeout are invalid")
    status = subprocess.run(["git", "status", "--porcelain"], cwd=root_path, check=True, capture_output=True, text=True).stdout.strip()
    if status:
        raise ValueError("candidate lock requires a clean committed V5 workspace")
    prompt = _inside(root_path, prompt_path)
    schema = _inside(root_path, output_schema_path)
    if schema.relative_to(root_path).as_posix() != "schemas/model_output.schema.json":
        raise ValueError("candidate output schema must be schemas/model_output.schema.json")
    tracked = subprocess.run(["git", "ls-files", "src/v5_eval", "scripts", "schemas", "data/baseline/v4_parser_lock.json"], cwd=root_path, check=True, capture_output=True, text=True).stdout.splitlines()
    files = {relative.replace("\\", "/"): _sha256(root_path / relative) for relative in tracked}
    config_hash = hashlib.sha256(json.dumps(dict(config), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root_path, check=True, capture_output=True, text=True).stdout.strip()
    return {
        "protocol_id": "v5-prospective-1",
        "candidate_locked": True,
        "locked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": commit,
        "model_id": config["model_id"],
        "quantization": config["quantization"],
        "runtime": config["runtime"],
        "runtime_version": config["runtime_version"],
        "generation_settings": dict(config["generation_settings"]),
        "timeout_ms": config["timeout_ms"],
        "prompt_file": prompt.relative_to(root_path).as_posix(),
        "prompt_hash": _sha256_text(prompt),
        "output_schema_file": schema.relative_to(root_path).as_posix(),
        "output_schema_hash": _sha256(schema),
        "model_config_hash": config_hash,
        "implementation_files": files,
    }


def verify_candidate_lock(lock: Mapping[str, Any], root: str | Path, records: Iterable[Mapping[str, Any]] = ()) -> None:
    root_path = Path(root).resolve()
    if lock.get("protocol_id") != "v5-prospective-1" or lock.get("candidate_locked") is not True:
        raise ValueError("candidate is not locked for this protocol")
    if lock.get("output_schema_file") != "schemas/model_output.schema.json":
        raise ValueError("candidate lock does not use the blind model-output schema")
    for key in ("git_commit", "model_id", "quantization", "runtime", "runtime_version", "generation_settings", "timeout_ms", "prompt_hash", "output_schema_hash", "model_config_hash", "implementation_files"):
        if not lock.get(key):
            raise ValueError("candidate lock is incomplete")
    for key, hash_key in (("prompt_file", "prompt_hash"), ("output_schema_file", "output_schema_hash")):
        path = _inside(root_path, root_path / str(lock.get(key, "")))
        actual_hash = _sha256_text(path) if key == "prompt_file" else _sha256(path)
        if actual_hash.casefold() != str(lock.get(hash_key, "")).casefold():
            raise ValueError(f"candidate lock mismatch: {key}")
    tracked = subprocess.run(["git", "ls-files", "src/v5_eval", "scripts", "schemas", "data/baseline/v4_parser_lock.json"], cwd=root_path, check=True, capture_output=True, text=True).stdout.splitlines()
    if set(lock["implementation_files"]) != {relative.replace("\\", "/") for relative in tracked}:
        raise ValueError("candidate implementation file set changed")
    for relative, expected_hash in lock["implementation_files"].items():
        path = _inside(root_path, root_path / str(relative))
        if _sha256(path).casefold() != str(expected_hash).casefold():
            raise ValueError(f"candidate implementation changed: {relative}")
    for record in records:
        if str(record.get("model_id")) != str(lock["model_id"]) or str(record.get("prompt_hash", "")).casefold() != str(lock["prompt_hash"]).casefold() or str(record.get("model_config_hash", "")).casefold() != str(lock["model_config_hash"]).casefold():
            raise ValueError(f"saved response does not match candidate lock: {record.get('case_id')}")
