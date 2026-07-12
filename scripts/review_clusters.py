from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import load_jsonl
from v5_eval.workflow import apply_cluster_reviews


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactively confirm or split V5 near-duplicate clusters.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cases = load_jsonl(args.cases)
    groups = defaultdict(list)
    for case in cases:
        if case.get("cluster_review_status") == "pending_review":
            groups[str(case["cluster_id"])].append(case)
    decisions = {}
    for cluster_id, group in groups.items():
        print(f"\nCluster {cluster_id} ({len(group)} cases)")
        for case in group:
            print(f"- {case['source_message_id']}: {case['raw_text']}")
        choice = input("Confirm same cluster [y], assign split groups [s], leave pending [n]: ").strip().lower()
        if choice == "s":
            decisions[cluster_id] = {str(case["case_id"]): input(f"Subgroup for {case['source_message_id']}: ").strip() for case in group}
        else:
            decisions[cluster_id] = "confirm" if choice == "y" else "pending"
    reviewed = apply_cluster_reviews(cases, decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for case in reviewed:
            handle.write(json.dumps(case, sort_keys=True) + "\n")
    print(f"reviewed={len(groups)} output={args.output}")


if __name__ == "__main__":
    main()
