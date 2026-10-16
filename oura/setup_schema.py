#!/usr/bin/env python3
"""Create the Oura tables in Tiger Cloud.

Run: uv run python oura/setup_schema.py
Uses DATABASE_URL from the environment/oura/.env, otherwise the repository's
ignored tiger-cloud-credentials.txt. Never prints connection credentials.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict


DEFAULT_CREDENTIALS = Path(__file__).resolve().parents[1] / "tiger-cloud-credentials.txt"
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS oura_record (
    participant_id text NOT NULL CHECK (participant_id <> ''),
    data_type text NOT NULL CHECK (data_type <> ''),
    record_key text NOT NULL CHECK (record_key <> ''),
    record_date date,
    recorded_at timestamptz,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    imported_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (participant_id, data_type, record_key)
);
CREATE INDEX IF NOT EXISTS oura_record_date_idx
    ON oura_record (participant_id, data_type, record_date DESC);
CREATE INDEX IF NOT EXISTS oura_record_time_idx
    ON oura_record (participant_id, data_type, recorded_at DESC)
    WHERE recorded_at IS NOT NULL;
"""


def database_url(credentials_file: Path = DEFAULT_CREDENTIALS) -> str:
    load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        try:
            for line in credentials_file.read_text(encoding="utf-8").splitlines():
                label, separator, content = line.partition(":")
                if separator and label.strip() == "Service URL":
                    value = content.strip()
                    break
        except OSError:
            raise ValueError("Cannot read credentials file. Pass --credentials-file or set DATABASE_URL.") from None
    if not value:
        raise ValueError("No Service URL found in credentials file; alternatively set DATABASE_URL.")
    try:
        settings = conninfo_to_dict(value)
    except psycopg.Error:
        raise ValueError("Invalid database connection configuration.") from None
    if settings.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("Database connection must use sslmode=require or certificate verification.")
    return value


def create_schema(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_SQL)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", type=Path, default=DEFAULT_CREDENTIALS)
    args = parser.parse_args(argv)
    try:
        with psycopg.connect(database_url(args.credentials_file), connect_timeout=10,
                             application_name="timescale-sensor-oura") as connection:
            create_schema(connection)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Schema setup failed. Check database access, credentials, and CREATE permissions.", file=sys.stderr)
        return 1
    print("Done: Oura table and indexes are ready in Tiger Cloud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())