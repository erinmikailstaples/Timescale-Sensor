#!/usr/bin/env python3
"""Download AWEAR cloud EEG; this is not a direct device connection.

Run `uv run python awear/fetch_data.py --help`. Set AWEAR_API_KEY in the
environment or awear/.env, or pass --env-file before the command.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE = "https://awearlabs.com/api/v1"
HINTS = {
    "INVALID_KEY": "Check AWEAR_API_KEY.",
    "KEY_REVOKED": "Create a new API key.",
    "DUA_REQUIRED": "Sign your group's Data Use Agreement.",
    "NO_PLAN": "Subscribe the recording device at https://awearlabs.com/devices.",
    "QUOTA_EXCEEDED": "Check your group's data quota and overage cap before retrying.",
    "FORBIDDEN": "Check that this participant belongs to your group.",
}


def get_json(session, path, params=None):
    response = session.get(f"{BASE}{path}", params=params, timeout=(10, 60), allow_redirects=False)
    if not 200 <= response.status_code < 300:
        try:
            code = response.json().get("error", {}).get("code", "UNKNOWN_ERROR")
        except (ValueError, AttributeError):
            code = "UNKNOWN_ERROR"
        hint = HINTS.get(code, "Check API parameters and service availability.")
        retry = response.headers.get("Retry-After")
        if response.status_code == 429 and retry:
            hint += f" Retry-After: {retry}."
        raise ValueError(f"AWEAR HTTP {response.status_code} ({code}). {hint}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected API response: expected a JSON object.")
    return payload


def export_data(session, args):
    output = args.output.expanduser()
    if output.exists():
        raise ValueError(f"Output already exists: {output}. Choose a new filename.")
    offset = 0
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=output.parent,
            prefix=f".{output.name}.", suffix=".part", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.writer(handle) if args.format == "csv" else None
            if writer is not None:
                writer.writerow(["timestamp", "participant_id", "device_id"]
                                + [f"s{index}" for index in range(256)])
            while True:
                payload = get_json(session, f"/members/{args.participant}/data", {
                    "start": args.start, "end": args.end, "tz": "UTC",
                    "limit": args.page_size, "offset": offset, "sort": "asc", "format": "json",
                })
                records = payload.get("data")
                pagination = payload.get("pagination")
                if (not isinstance(records, list) or not isinstance(pagination, dict)
                        or not isinstance(pagination.get("hasMore"), bool)):
                    raise ValueError("Unexpected API data or pagination metadata.")
                for record in records:
                    waveform = record["waveform"]
                    if (not isinstance(record["timestamp"], str)
                            or not isinstance(record["device_id"], str)
                            or not isinstance(waveform, list) or len(waveform) != 256
                            or any(type(value) not in (int, float) or not math.isfinite(value)
                                   for value in waveform)):
                        raise ValueError("Expected timestamp, device_id, and 256 finite EEG samples.")
                    if writer is not None:
                        writer.writerow([record["timestamp"], args.participant,
                                         record["device_id"], *waveform])
                    else:
                        handle.write(json.dumps({
                            "timestamp": record["timestamp"], "participant_id": args.participant,
                            "device_id": record["device_id"], "waveform": waveform,
                        }, allow_nan=False) + "\n")
                offset += len(records)
                print(f"Fetched {offset} EEG records.", file=sys.stderr)
                if not pagination["hasMore"]:
                    break
                if not records:
                    raise ValueError("Empty page with hasMore=true; export stopped.")
                time.sleep(1.1)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Done! Saved {offset} records ({offset * 256} samples) to {output}.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().with_name(".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("members", help="List active participants as JSON.")
    commands.add_parser("usage", help="Check API-key request-limit usage as JSON.")
    data = commands.add_parser("data", help="Export every page in a specified EEG time window.")
    data.add_argument("--participant", required=True)
    data.add_argument("--start", required=True)
    data.add_argument("--end", required=True)
    data.add_argument("--page-size", type=int, default=5000)
    data.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    data.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "data":
        if not re.fullmatch(r"P-[A-Z0-9]{6}", args.participant):
            parser.error("Use a participant ID such as P-A1B2C3, not an email.")
        try:
            start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or start >= end:
                raise ValueError
        except ValueError:
            parser.error("Use ISO 8601 timestamps with Z or UTC offsets, with start earlier than end.")
        if not 1 <= args.page_size <= 50000:
            parser.error("--page-size must be between 1 and 50000.")
    if args.env_file.is_file():
        load_dotenv(args.env_file, override=False)
    elif args.env_file != parser.get_default("env_file"):
        parser.error(f"Environment file not found: {args.env_file}")
    key = os.getenv("AWEAR_API_KEY", "").strip()
    if not key:
        parser.error("Set AWEAR_API_KEY in awear/.env or the environment; see awear/.env.example.")
    try:
        with requests.Session() as session:
            session.headers.update({"Authorization": f"Bearer {key}", "Accept": "application/json"})
            if args.command == "data":
                export_data(session, args)
            else:
                print(json.dumps(get_json(session, f"/{args.command}"), indent=2))
    except requests.RequestException:
        print("AWEAR request failed. Check connectivity and retry with a narrow time window.", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled; incomplete export removed.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())