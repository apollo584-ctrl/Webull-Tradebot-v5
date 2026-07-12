from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import load_jsonl
from v5_eval.scoring import bind_locked_labels, score_records
from v5_eval.v4_baseline import load_lock, verify_label_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Score saved V5 model responses without calling a model.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--label-lock", type=Path, required=True)
    args = parser.parse_args()
    lock = load_lock(args.label_lock)
    verify_label_lock(lock, ROOT / lock["case_file"], ROOT)
    cases = load_jsonl(ROOT / lock["case_file"])
    labels = load_jsonl(ROOT / lock["label_file"])
    report = score_records(bind_locked_labels(load_jsonl(args.input), cases, labels))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
