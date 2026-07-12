from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from v5_eval.core import SOURCE_CHANNEL_URL_SHA256, load_jsonl
from v5_eval.workflow import select_prospective_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a raw Casey snapshot into the V5-owned prospective pool.")
    parser.add_argument("source", type=Path, help="Raw JSONL export; may contain other channels, which are excluded.")
    parser.add_argument("name", help="Safe snapshot name, such as 2026-07-13-capture.")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        raise ValueError("snapshot name may contain only letters, numbers, underscore, and hyphen")
    protocol = json.loads((ROOT / "data" / "holdout" / "protocol.json").read_text(encoding="utf-8"))
    start = datetime.fromisoformat(protocol["confirmation_start"])
    source_records = load_jsonl(args.source)
    selected, audit = select_prospective_records(source_records, start, with_audit=True)
    if not selected:
        raise ValueError("no eligible prospective Casey messages were found")
    snapshot = ROOT / "data" / "raw" / "prospective" / f"{args.name}.jsonl"
    manifest_path = ROOT / "data" / "holdout" / "captures" / f"{args.name}.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot.open("w", encoding="utf-8", newline="\n") as handle:
        for record in selected:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    snapshot_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    timestamps = [str(record["timestamp"]) for record in selected]
    manifest = {
        "capture_id": args.name,
        "imported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "snapshot_path": f"data/raw/prospective/{args.name}.jsonl",
        "snapshot_sha256": snapshot_hash,
        "source_channel_url_sha256": SOURCE_CHANNEL_URL_SHA256,
        "time_start": min(timestamps),
        "time_end": max(timestamps),
        "record_count": len(selected),
        "parser_or_model_fields_absent": True,
        "capture_audit": audit,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"snapshot={snapshot} records={len(selected)} manifest={manifest_path}")


if __name__ == "__main__":
    main()
