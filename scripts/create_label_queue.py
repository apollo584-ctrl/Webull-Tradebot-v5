from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import load_jsonl
from v5_eval.workflow import build_label_queue


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a randomized blind label queue from reviewed V5 cases.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    queue = build_label_queue(load_jsonl(args.cases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in queue:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"queue={len(queue)} output={args.output}")


if __name__ == "__main__":
    main()
