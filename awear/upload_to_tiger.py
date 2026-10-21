#!/usr/bin/env python3
"""Upload an AWEAR EEG export (CSV, JSONL, or JSON) into Tiger Cloud.

Flow:  fetch_data.py  ->  local export file  ->  this script  ->  eeg_record table

Each AWEAR record is one second of EEG (256 samples). This script stores one
row per record with the samples in an array column. Re-running the same file is
safe: rows that already exist (same time, participant, device, channel) are
skipped, not duplicated.

SAFE BY DEFAULT: without --write it only previews. Create the table once with
--create-schema (it runs sql/awear_schema.sql for you).

Usage:

    uv run python awear/upload_to_tiger.py awear/exports/eeg.csv --units uV
    uv run python awear/upload_to_tiger.py awear/exports/eeg.csv --units uV --create-schema --write

DATABASE_URL is read from awear/.env, then the repository's .env.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SAMPLES_PER_RECORD = 256
UNITS = ("V", "mV", "uV")
SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "awear_schema.sql"

INSERT_SQL = """INSERT INTO eeg_record
    (time, participant_id, device_id, channel, sampling_rate, unit, waveform, metadata)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (time, participant_id, device_id, channel) DO NOTHING"""


@dataclass(frozen=True)
class Record:
    time: datetime
    participant_id: str
    device_id: str
    waveform: list[float]


def load_records(path: Path) -> list[Record]:
    """Read fetch_data.py output. Accepts .csv, .jsonl, or a raw API .json response."""
    with path.open(encoding="utf-8", newline="") as handle:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            raw = list(csv.DictReader(handle))
            for record in raw:
                record["waveform"] = [record[f"s{i}"] for i in range(SAMPLES_PER_RECORD)]
        elif suffix == ".jsonl":
            raw = [json.loads(line) for line in handle if line.strip()]
        elif suffix == ".json":
            payload = json.load(handle)
            raw = payload["data"]
            participant = payload.get("meta", {}).get("participantId")
            for record in raw:
                record.setdefault("participant_id", participant)
        else:
            raise ValueError("Input must be .csv, .json, or .jsonl.")

    records: list[Record] = []
    for index, record in enumerate(raw, start=1):
        participant = record.get("participant_id")
        if not participant:
            raise ValueError(f"Record {index} has no participant_id.")
        stamp = datetime.fromisoformat(str(record["timestamp"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError(f"Record {index} timestamp lacks a UTC offset or Z.")
        waveform = [float(value) for value in record["waveform"]]
        if len(waveform) != SAMPLES_PER_RECORD or not all(math.isfinite(v) for v in waveform):
            raise ValueError(f"Record {index} must contain exactly 256 finite samples.")
        records.append(Record(stamp, str(participant), str(record["device_id"]), waveform))
    if not records:
        raise ValueError("The file contains no records.")
    return records


def summarize(records: list[Record]) -> dict:
    participants = sorted({r.participant_id for r in records})
    devices = sorted({r.device_id for r in records})
    return {
        "records": len(records),
        "seconds_of_eeg": len(records),
        "participants": participants,
        "devices": devices,
        "first": records[0].time.isoformat(),
        "last": records[-1].time.isoformat(),
    }


def load_environment(env_file: Path | None) -> None:
    from dotenv import load_dotenv

    here = Path(__file__).resolve().parent
    candidates = [env_file] if env_file else [here / ".env", here.parent / ".env", Path.cwd() / ".env"]
    for candidate in candidates:
        if candidate and candidate.is_file():
            load_dotenv(candidate, override=False)
    if env_file and not env_file.is_file():
        raise SystemExit(f"Environment file not found: {env_file}")


def create_schema(connection) -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()


def upload(connection, records: list[Record], units: str, source: str, batch_size: int = 500) -> int:
    """Insert records; return how many were actually new."""
    metadata = json.dumps({"source": source, "uploaded_at": datetime.now().astimezone().isoformat()})
    inserted = 0
    with connection.cursor() as cursor:
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            for record in batch:
                cursor.execute(
                    INSERT_SQL,
                    (record.time, record.participant_id, record.device_id, "TP10",
                     SAMPLES_PER_RECORD, units, record.waveform, metadata),
                )
                inserted += cursor.rowcount
            connection.commit()
            print(f"processed {min(start + batch_size, len(records))}/{len(records)}",
                  end="\r", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="export from fetch_data.py")
    parser.add_argument("--units", required=True, choices=UNITS,
                        help="waveform units as confirmed with AWEAR; stored with every row")
    parser.add_argument("--create-schema", action="store_true",
                        help="run sql/awear_schema.sql first (safe to repeat)")
    parser.add_argument("--write", action="store_true", help="actually insert rows")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)

    try:
        records = load_records(args.input)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot read export: {exc}", file=sys.stderr)
        return 1

    summary = summarize(records)
    print(json.dumps({"file": str(args.input), "units": args.units, **summary}, indent=2))
    if len(summary["participants"]) != 1:
        print("Upload one participant at a time; split the export first.", file=sys.stderr)
        return 1
    if not args.write:
        print("\npreview only. Re-run with --write to upload (add --create-schema the first time).")
        return 0

    load_environment(args.env_file)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing; add it to awear/.env or the repository .env.", file=sys.stderr)
        return 1

    import psycopg

    try:
        with psycopg.connect(database_url) as connection:
            if args.create_schema:
                create_schema(connection)
                print("schema ready (eeg_record, eeg_coverage_1h)")
            inserted = upload(connection, records, args.units, args.input.name)
    except psycopg.Error as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        if "eeg_record" in str(exc) and "does not exist" in str(exc):
            print("Hint: add --create-schema.", file=sys.stderr)
        return 1
    print(f"done; new_rows={inserted} already_present={len(records) - inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
