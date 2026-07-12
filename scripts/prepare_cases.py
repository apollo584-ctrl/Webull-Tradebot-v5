from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from v5_eval.core import SOURCE_CHANNEL_URL_SHA256, canonicalize_records, load_jsonl, validate_capture_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare V5 canonical cases from a raw JSONL snapshot.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--confirmation-start", type=datetime.fromisoformat)
    parser.add_argument("--source-channel-url-sha256", default=SOURCE_CHANNEL_URL_SHA256)
    parser.add_argument("--capture-manifest", type=Path)
    args = parser.parse_args()
    manifest_verified = False
    source_hash = args.source_channel_url_sha256
    if args.capture_manifest:
        manifest = json.loads(args.capture_manifest.read_text(encoding="utf-8"))
        validate_capture_manifest(manifest)
        input_path = args.input.resolve()
        root = Path(__file__).resolve().parents[1]
        expected_path = (root / manifest["snapshot_path"]).resolve()
        if input_path != expected_path:
            raise ValueError("input snapshot does not match capture manifest snapshot_path")
        digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
        if digest.casefold() != str(manifest["snapshot_sha256"]).casefold():
            raise ValueError("input snapshot hash does not match capture manifest")
        record_count = len(load_jsonl(args.input))
        if record_count != int(manifest["record_count"]):
            raise ValueError("input record count does not match capture manifest")
        if source_hash.casefold() != str(manifest["source_channel_url_sha256"]).casefold():
            raise ValueError("source hash override does not match capture manifest")
        source_hash = str(manifest["source_channel_url_sha256"])
        manifest_verified = True
    cases = canonicalize_records(load_jsonl(args.input), confirmation_start=args.confirmation_start, source_channel_url_sha256=source_hash, manifest_verified=manifest_verified)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, sort_keys=True) + "\n")
    print(f"prepared={len(cases)} output={args.output}")


if __name__ == "__main__":
    main()
