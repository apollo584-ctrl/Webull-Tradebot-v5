from __future__ import annotations

import argparse
from datetime import date
import json

from operation_control import OperationBusy, OperationStore


def main() -> int:
    parser = argparse.ArgumentParser(description="V5-owned operation status and collection-range checks for the V6 operator.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")

    check = subparsers.add_parser("collection-check")
    check.add_argument("--start-date", type=date.fromisoformat, required=True)
    check.add_argument("--end-date", type=date.fromisoformat, required=True)

    args = parser.parse_args()
    store = OperationStore()
    try:
        if args.command == "status":
            result = store.status()
            exit_code = 0
        else:
            if args.start_date > args.end_date:
                parser.error("beginning date cannot be after ending date")
            overlaps = store.overlapping_completed_ranges(args.start_date, args.end_date)
            result = {"start_date": args.start_date.isoformat(), "end_date": args.end_date.isoformat(), "refresh_confirmation_required": bool(overlaps), "overlapping_completed_ranges": overlaps}
            exit_code = 3 if overlaps else 0
    except (OperationBusy, ValueError, OSError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
