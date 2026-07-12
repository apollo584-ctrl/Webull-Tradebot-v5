from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.freeze import build_candidate_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the one preselected V5 confirmatory model candidate.")
    parser.add_argument("config", type=Path, help="JSON model/runtime/generation configuration.")
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "holdout" / "candidate.lock.json")
    args = parser.parse_args()
    lock = build_candidate_lock(json.loads(args.config.read_text(encoding="utf-8")), args.prompt, ROOT / "schemas" / "model_output.schema.json", ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol_path = ROOT / "data" / "holdout" / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["primary_candidate_locked"] = True
    protocol["candidate_lock_file"] = args.output.relative_to(ROOT).as_posix()
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    protocol_lock_path = ROOT / "data" / "holdout" / "protocol.lock.json"
    protocol_lock = json.loads(protocol_lock_path.read_text(encoding="utf-8"))
    protocol_lock["git_commit"] = lock["git_commit"]
    protocol_lock["files"]["data/holdout/protocol.json"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest().upper()
    protocol_lock["files"][args.output.relative_to(ROOT).as_posix()] = hashlib.sha256(args.output.read_bytes()).hexdigest().upper()
    protocol_lock_path.write_text(json.dumps(protocol_lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"candidate_locked={lock['model_id']} commit={lock['git_commit']} output={args.output}")


if __name__ == "__main__":
    main()
