from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.v4_baseline import load_lock, load_v4_parser, normalize_parsed_signal


def _expected(value: str) -> str | None:
    value = str(value or "").strip()
    return None if value in ("", "-") else value


def main() -> None:
    parser = argparse.ArgumentParser(description="Development-only V4 parser reproducibility benchmark.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--v4-repository", type=Path, default=Path(r"C:\Users\gregd\Codex Projects\Webull Tradebot v4 Qwen"))
    parser.add_argument("--lock", type=Path, default=ROOT / "data" / "baseline" / "v4_parser_lock.json")
    args = parser.parse_args()
    lock = load_lock(args.lock)
    v4_parser = load_v4_parser(args.v4_repository, lock)
    with args.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    action_matches = symbol_matches = direction_matches = 0
    for row in rows:
        result = normalize_parsed_signal(v4_parser.parse(row["raw_message"]))["parser_audit"]
        action_matches += result["action"] == _expected(row["expected_action"])
        symbol_matches += result["symbol"] == _expected(row["expected_symbol"])
        direction_matches += result["direction"] == _expected(row["expected_direction"])

    total = len(rows)
    report = {
        "classification": "development_only_not_independent_evidence",
        "baseline_id": lock["baseline_id"],
        "v4_git_commit": lock["git_commit"],
        "source_csv_sha256": __import__("hashlib").sha256(args.csv_path.read_bytes()).hexdigest(),
        "cases": total,
        "parser_action_match_rate": action_matches / total if total else None,
        "parser_symbol_match_rate": symbol_matches / total if total else None,
        "parser_direction_match_rate": direction_matches / total if total else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
