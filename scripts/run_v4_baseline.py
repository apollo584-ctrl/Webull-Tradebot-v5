from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import load_jsonl
from v5_eval.v4_baseline import load_lock, load_v4_parser, run_v4_parser, verify_label_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen V4 parser baseline without runtime services.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--v4-repository", type=Path, default=Path(r"C:\Users\gregd\Codex Projects\Webull Tradebot v4 Qwen"))
    parser.add_argument("--lock", type=Path, default=ROOT / "data" / "baseline" / "v4_parser_lock.json")
    parser.add_argument("--label-lock", type=Path, required=True, help="Locked independent-label manifest for these cases.")
    args = parser.parse_args()
    lock = load_lock(args.lock)
    label_lock = load_lock(args.label_lock)
    verify_label_lock(label_lock, args.cases, ROOT)
    v4_parser = load_v4_parser(args.v4_repository, lock)
    results = run_v4_parser(load_jsonl(args.cases), v4_parser, baseline_id=lock["baseline_id"], git_commit=lock["git_commit"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for result in results:
            handle.write(json.dumps(result, sort_keys=True) + "\n")
    print(f"baseline={lock['baseline_id']} cases={len(results)} output={args.output}")


if __name__ == "__main__":
    main()
