from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.workflow import build_label_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock final blind labels before any parser/model scoring.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "holdout" / "label.lock.json")
    args = parser.parse_args()
    lock = build_label_lock(cases_path=args.cases, labels_path=args.labels, root=ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"labels_locked={lock['labels_locked']} output={args.output}")


if __name__ == "__main__":
    main()
