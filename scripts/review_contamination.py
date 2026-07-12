from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import load_jsonl
from v5_eval.workflow import CONTAMINATION_FLAGS, apply_contamination_reviews


def main() -> None:
    parser = argparse.ArgumentParser(description="Record blind contamination decisions before labeling or system scoring.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("decisions", type=Path, help="JSONL rows containing case_id, status, and flags.")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    decision_rows = load_jsonl(args.decisions)
    decision_ids = [str(row["case_id"]) for row in decision_rows]
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("duplicate contamination decision case_id")
    decisions = dict(zip(decision_ids, decision_rows))
    reference_hash = hashlib.sha256((ROOT / "data" / "source_manifest.json").read_bytes()).hexdigest()
    reviewed = apply_contamination_reviews(load_jsonl(args.cases), decisions, reference_hash)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for case in reviewed:
            handle.write(json.dumps(case, sort_keys=True) + "\n")
    print(f"reviewed={len(reviewed)} allowed_flags={','.join(sorted(CONTAMINATION_FLAGS))} output={args.output}")


if __name__ == "__main__":
    main()
