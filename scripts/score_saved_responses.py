from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import load_jsonl
from v5_eval.freeze import verify_candidate_lock
from v5_eval.scoring import bind_locked_labels, bind_v4_baseline, score_records
from v5_eval.v4_baseline import load_lock, verify_label_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Score saved V5 model responses without calling a model.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--label-lock", type=Path, required=True)
    parser.add_argument("--candidate-lock", type=Path, required=True)
    parser.add_argument("--v4-baseline", type=Path, required=True)
    args = parser.parse_args()
    lock = load_lock(args.label_lock)
    verify_label_lock(lock, ROOT / lock["case_file"], ROOT)
    cases = load_jsonl(ROOT / lock["case_file"])
    labels = load_jsonl(ROOT / lock["label_file"])
    protocol = json.loads((ROOT / "data" / "holdout" / "protocol.json").read_text(encoding="utf-8"))
    candidate_path = args.candidate_lock.resolve()
    if not candidate_path.is_relative_to(ROOT / "data" / "holdout"):
        raise ValueError("candidate lock must be inside V5 holdout data")
    candidate_file = candidate_path.relative_to(ROOT).as_posix()
    if protocol.get("primary_candidate_locked") is not True or protocol.get("candidate_lock_file") != candidate_file:
        raise ValueError("protocol does not identify this locked primary candidate")
    protocol_lock = load_lock(ROOT / "data" / "holdout" / "protocol.lock.json")
    expected_candidate_hash = protocol_lock.get("files", {}).get(candidate_file)
    if not expected_candidate_hash or hashlib.sha256(candidate_path.read_bytes()).hexdigest().casefold() != str(expected_candidate_hash).casefold():
        raise ValueError("candidate lock is not included in the protocol lock")
    records = bind_locked_labels(load_jsonl(args.input), cases, labels)
    records = bind_v4_baseline(records, load_jsonl(args.v4_baseline), load_lock(ROOT / "data" / "baseline" / "v4_parser_lock.json"))
    verify_candidate_lock(load_lock(candidate_path), ROOT, records)
    report = score_records(records, protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
