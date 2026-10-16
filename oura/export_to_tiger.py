#!/usr/bin/env python3
"""Upload JSON from read_oura.py to Tiger Cloud in one transaction.

Run: uv run python oura/export_to_tiger.py oura/exports/week.json --participant self
Run setup_schema.py first. --dry-run validates without connecting to a database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from read_oura import ENDPOINTS
from setup_schema import DEFAULT_CREDENTIALS, database_url


UPSERT_SQL = """
INSERT INTO oura_record
    (participant_id, data_type, record_key, record_date, recorded_at, payload)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (participant_id, data_type, record_key) DO UPDATE
SET record_date = EXCLUDED.record_date,
    recorded_at = EXCLUDED.recorded_at,
    payload = EXCLUDED.payload,
    imported_at = now()
WHERE oura_record.payload IS DISTINCT FROM EXCLUDED.payload
"""


def record_key(data_type: str, record: dict) -> str:
    if data_type == "personal_info":
        return "profile"
    identifier = record.get("id")
    if isinstance(identifier, str) and identifier:
        return f"id:{identifier}"
    if data_type in {"heartrate", "ring_battery_level"} and record.get("timestamp"):
        stamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Timestamp values must include a UTC offset or Z.")
        identity = [stamp.astimezone(timezone.utc).isoformat(), record.get("source")]
        return "time:" + json.dumps(identity, separators=(",", ":"))
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare_records(payload: dict, participant: str) -> list[tuple]:
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Expected a nonempty JSON object produced by read_oura.py.")
    rows = []
    for data_type, records in payload.items():
        if data_type not in ENDPOINTS:
            raise ValueError("Export contains an unsupported Oura data type.")
        if data_type == "personal_info":
            if not isinstance(records, dict):
                raise ValueError("personal_info must be an object.")
            records = [records]
        if not isinstance(records, list):
            raise ValueError("Oura collections must be arrays of objects.")
        for record in records:
            if not isinstance(record, dict) or not record:
                raise ValueError("Every Oura record must be a nonempty object.")
            json.dumps(record, allow_nan=False)
            record_day = record.get("day") or record.get("start_day")
            record_date = date.fromisoformat(record_day) if record_day else None
            stamp = record.get("timestamp") or record.get("bedtime_start") or record.get("start_datetime")
            recorded_at = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None
            if recorded_at is not None and recorded_at.tzinfo is None:
                raise ValueError("Timestamp values must include a UTC offset or Z.")
            rows.append((participant, data_type, record_key(data_type, record),
                         record_date, recorded_at, Jsonb(record)))
    return rows


def upload_records(connection, rows: list[tuple]) -> int:
    if not rows:
        return 0
    with connection.cursor() as cursor:
        cursor.executemany(UPSERT_SQL, rows)
        return cursor.rowcount


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file saved by read_oura.py.")
    parser.add_argument("--participant", required=True, help="Stable local alias, not a name or email.")
    parser.add_argument("--credentials-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--dry-run", action="store_true", help="Validate only; no database connection.")
    args = parser.parse_args(argv)
    participant = args.participant.strip()
    if not participant:
        parser.error("--participant must not be empty.")
    try:
        with args.input.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        rows = prepare_records(payload, participant)
    except (OSError, ValueError, TypeError, AttributeError):
        print("Invalid export. Use read_oura.py JSON with valid dates, zoned timestamps, and finite values.",
              file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"Dry run: validated {len(rows)} records; no database connection made.")
        return 0
    if not rows:
        print("Done: no records to upload.")
        return 0
    try:
        with psycopg.connect(database_url(args.credentials_file), connect_timeout=10,
                             application_name="timescale-sensor-oura") as connection:
            changed = upload_records(connection, rows)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Upload failed; transaction rolled back. Check database access and run oura/setup_schema.py first.",
              file=sys.stderr)
        return 1
    print(f"Done: processed {len(rows)} records; inserted or updated {changed} rows in Tiger Cloud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())