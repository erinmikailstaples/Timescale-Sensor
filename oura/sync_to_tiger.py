#!/usr/bin/env python3
"""Fetch all authorized Oura collections and sync them directly to Tiger Cloud."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from export_to_tiger import prepare_records
from read_oura import ENDPOINTS, OuraAPIError, fetch_data
from setup_schema import DEFAULT_CREDENTIALS, create_schema, database_url


ENV_FILE = Path(__file__).resolve().with_name(".env")
FIRST_OURA_DATE = date(2015, 1, 1)
STATIC_ENDPOINTS = {"personal_info", "ring_configuration"}
WINDOW_DAYS = 90
TIME_SERIES_WINDOW_DAYS = 30
TIME_SERIES_ENDPOINTS = {"heartrate", "ring_battery_level"}

CURRENT_UPSERT_SQL = """
INSERT INTO oura_record
    (participant_id, data_type, record_key, record_date, recorded_at, payload, sync_run_id)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (participant_id, data_type, record_key) DO UPDATE
SET record_date = EXCLUDED.record_date,
    recorded_at = EXCLUDED.recorded_at,
    payload = EXCLUDED.payload,
    imported_at = now(),
    sync_run_id = EXCLUDED.sync_run_id,
    source_deleted_at = NULL
WHERE oura_record.payload IS DISTINCT FROM EXCLUDED.payload
   OR oura_record.source_deleted_at IS NOT NULL
"""

VERSION_INSERT_SQL = """
INSERT INTO oura_record_version
    (participant_id, data_type, record_key, payload_hash, record_date,
     recorded_at, payload, sync_run_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (participant_id, data_type, record_key, payload_hash) DO NOTHING
"""


def payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sync_rows(connection, rows: list[tuple], sync_run_id: int) -> int:
    if not rows:
        return 0
    current = [(*row, sync_run_id) for row in rows]
    versions = [
        (row[0], row[1], row[2], payload_hash(row[5].obj), row[3], row[4], row[5], sync_run_id)
        for row in rows
    ]
    with connection.cursor() as cursor:
        cursor.executemany(VERSION_INSERT_SQL, versions)
        cursor.executemany(CURRENT_UPSERT_SQL, current)
        return cursor.rowcount


def date_windows(start: date, end: date, window_days: int = WINDOW_DAYS):
    if window_days < 1:
        raise ValueError("window_days must be positive")
    cursor = start
    while cursor <= end:
        window_end = min(end, cursor + timedelta(days=window_days - 1))
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def update_env_file(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    output = []
    for line in lines:
        key = line.partition("=")[0].strip() if "=" in line else ""
        output.append(f"{key}={remaining.pop(key)}" if key in remaining else line)
    if output and output[-1] != "":
        output.append("")
    output.extend(f"{key}={value}" for key, value in remaining.items())
    descriptor, temporary = tempfile.mkstemp(prefix=".oura-env-", dir=path.parent, text=True)
    try:
        os.fchmod(descriptor, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output) + "\n")
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def refresh_access_token(session: requests.Session) -> None:
    load_dotenv(ENV_FILE, override=True)
    required = {
        "client_id": os.getenv("OURA_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("OURA_CLIENT_SECRET", "").strip(),
        "refresh_token": os.getenv("OURA_REFRESH_TOKEN", "").strip(),
    }
    if not all(required.values()):
        raise RuntimeError("Access token expired and refresh credentials are incomplete in oura/.env.")
    response = requests.post(
        "https://api.ouraring.com/oauth/token",
        data={"grant_type": "refresh_token", **required},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError("Oura token refresh failed; authorize the application again.")
    token = response.json()
    if not token.get("access_token") or not token.get("refresh_token"):
        raise RuntimeError("Oura token refresh returned incomplete credentials.")
    update_env_file(
        ENV_FILE,
        {
            "OURA_ACCESS_TOKEN": token["access_token"],
            "OURA_REFRESH_TOKEN": token["refresh_token"],
        },
    )
    session.headers["Authorization"] = f"Bearer {token['access_token']}"


def fetch_with_recovery(session: requests.Session, endpoint: str, start: date, end: date,
                        refresh_available: list[bool]):
    attempts = 0
    while True:
        try:
            return fetch_data(session, endpoint, start, end)
        except OuraAPIError as error:
            if error.status_code == 401 and refresh_available[0]:
                refresh_access_token(session)
                refresh_available[0] = False
                continue
            if error.status_code == 429 and attempts < 4:
                attempts += 1
                try:
                    delay = min(60, max(1, int(error.retry_after or "5")))
                except ValueError:
                    delay = 5
                time.sleep(delay)
                continue
            raise


def start_run(connection, participant: str, start: date, end: date) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """UPDATE oura_sync_run
               SET completed_at = now(), status = 'failed',
                   errors = errors || '{"sync":"superseded after an interrupted run"}'::jsonb
               WHERE participant_id = %s AND status = 'running'""",
            (participant,),
        )
        cursor.execute(
            """INSERT INTO oura_sync_run
               (participant_id, requested_start_date, requested_end_date)
               VALUES (%s, %s, %s) RETURNING sync_run_id""",
            (participant, start, end),
        )
        return cursor.fetchone()[0]


def finish_run(connection, run_id: int, status_value: str,
               counts: dict[str, int], errors: dict[str, str]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """UPDATE oura_sync_run
               SET completed_at = now(), status = %s,
                   endpoint_counts = %s, errors = %s
               WHERE sync_run_id = %s""",
            (status_value, Jsonb(counts), Jsonb(errors), run_id),
        )


def cursor_start(connection, participant: str, endpoint: str) -> date | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT through_date FROM oura_sync_cursor
               WHERE participant_id = %s AND data_type = %s""",
            (participant, endpoint),
        )
        row = cursor.fetchone()
    return row[0] - timedelta(days=7) if row else None


def save_cursor(connection, participant: str, endpoint: str, through: date) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO oura_sync_cursor (participant_id, data_type, through_date)
               VALUES (%s, %s, %s)
               ON CONFLICT (participant_id, data_type) DO UPDATE
               SET through_date = GREATEST(oura_sync_cursor.through_date, EXCLUDED.through_date),
                   updated_at = now()""",
            (participant, endpoint, through),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant", default="oura-self",
                        help="stable non-identifying local alias")
    parser.add_argument("--start-date", type=date.fromisoformat,
                        help="first date; default is cursor or 2015-01-01")
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--data", nargs="+", choices=ENDPOINTS, default=ENDPOINTS)
    parser.add_argument("--credentials-file", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--full", action="store_true",
                        help="ignore saved cursors and scan from --start-date or 2015-01-01")
    args = parser.parse_args(argv)
    participant = args.participant.strip()
    if not participant:
        parser.error("--participant must not be empty")
    if args.start_date and args.start_date > args.end_date:
        parser.error("--start-date must not be after --end-date")

    load_dotenv(ENV_FILE, override=True)
    token = os.getenv("OURA_ACCESS_TOKEN", "").strip()
    if not token:
        parser.error("OURA_ACCESS_TOKEN is missing from oura/.env")

    try:
        with psycopg.connect(
            database_url(args.credentials_file),
            connect_timeout=15,
            application_name="timescale-sensor-oura-sync",
        ) as connection:
            create_schema(connection)
            requested_start = args.start_date or FIRST_OURA_DATE
            run_id = start_run(connection, participant, requested_start, args.end_date)
            connection.commit()
            counts: dict[str, int] = {}
            errors: dict[str, str] = {}
            refresh_available = [True]
            with requests.Session() as session:
                session.headers["Authorization"] = f"Bearer {token}"
                for endpoint in tuple(dict.fromkeys(args.data)):
                    endpoint_count = 0
                    endpoint_start = requested_start
                    if not args.full and not args.start_date and endpoint not in STATIC_ENDPOINTS:
                        endpoint_start = cursor_start(connection, participant, endpoint) or requested_start
                    window_days = TIME_SERIES_WINDOW_DAYS if endpoint in TIME_SERIES_ENDPOINTS \
                        else WINDOW_DAYS
                    windows = [(requested_start, args.end_date)] if endpoint in STATIC_ENDPOINTS \
                        else date_windows(endpoint_start, args.end_date, window_days)
                    print(f"Syncing {endpoint}...", file=sys.stderr)
                    try:
                        for window_start, window_end in windows:
                            records = fetch_with_recovery(
                                session, endpoint, window_start, window_end, refresh_available
                            )
                            payload = {endpoint: records}
                            rows = prepare_records(payload, participant)
                            sync_rows(connection, rows, run_id)
                            endpoint_count += len(rows)
                            connection.commit()
                        if endpoint not in STATIC_ENDPOINTS:
                            save_cursor(connection, participant, endpoint, args.end_date)
                            connection.commit()
                        counts[endpoint] = endpoint_count
                    except OuraAPIError as error:
                        connection.rollback()
                        if error.status_code in {401, 403}:
                            errors[endpoint] = "not authorized by the token or unavailable for this account"
                            print(f"Skipping {endpoint}: authorization unavailable.", file=sys.stderr)
                            continue
                        raise
            status_value = "partial" if errors else "completed"
            finish_run(connection, run_id, status_value, counts, errors)
            connection.commit()
    except (psycopg.Error, requests.RequestException, RuntimeError, ValueError) as error:
        print(f"Sync failed safely: {error}", file=sys.stderr)
        return 1

    print(f"Done: sync run {run_id} is {status_value}.")
    for endpoint, count in counts.items():
        print(f"  {endpoint}: {count} records read")
    if errors:
        print("Skipped collections require additional Oura consent or account support:")
        for endpoint in errors:
            print(f"  {endpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
