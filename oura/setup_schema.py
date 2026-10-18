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
CREATE TABLE IF NOT EXISTS oura_sync_run (
    sync_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    participant_id text NOT NULL CHECK (participant_id <> ''),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    requested_start_date date,
    requested_end_date date,
    status text NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'partial', 'failed')),
    endpoint_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    errors jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS oura_record (
    participant_id text NOT NULL CHECK (participant_id <> ''),
    data_type text NOT NULL CHECK (data_type <> ''),
    record_key text NOT NULL CHECK (record_key <> ''),
    record_date date,
    recorded_at timestamptz,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    first_imported_at timestamptz NOT NULL DEFAULT now(),
    imported_at timestamptz NOT NULL DEFAULT now(),
    sync_run_id bigint REFERENCES oura_sync_run(sync_run_id) ON DELETE SET NULL,
    source_deleted_at timestamptz,
    PRIMARY KEY (participant_id, data_type, record_key)
);
ALTER TABLE oura_record
    ADD COLUMN IF NOT EXISTS first_imported_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE oura_record
    ADD COLUMN IF NOT EXISTS sync_run_id bigint REFERENCES oura_sync_run(sync_run_id) ON DELETE SET NULL;
ALTER TABLE oura_record
    ADD COLUMN IF NOT EXISTS source_deleted_at timestamptz;

CREATE TABLE IF NOT EXISTS oura_record_version (
    participant_id text NOT NULL CHECK (participant_id <> ''),
    data_type text NOT NULL CHECK (data_type <> ''),
    record_key text NOT NULL CHECK (record_key <> ''),
    payload_hash text NOT NULL CHECK (payload_hash <> ''),
    record_date date,
    recorded_at timestamptz,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    observed_at timestamptz NOT NULL DEFAULT now(),
    sync_run_id bigint REFERENCES oura_sync_run(sync_run_id) ON DELETE SET NULL,
    PRIMARY KEY (participant_id, data_type, record_key, payload_hash)
);

CREATE TABLE IF NOT EXISTS oura_sync_cursor (
    participant_id text NOT NULL CHECK (participant_id <> ''),
    data_type text NOT NULL CHECK (data_type <> ''),
    through_date date NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (participant_id, data_type)
);

CREATE INDEX IF NOT EXISTS oura_record_date_idx
    ON oura_record (participant_id, data_type, record_date DESC);
CREATE INDEX IF NOT EXISTS oura_record_time_idx
    ON oura_record (participant_id, data_type, recorded_at DESC)
    WHERE recorded_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS oura_record_payload_idx
    ON oura_record USING gin (payload jsonb_path_ops);
CREATE INDEX IF NOT EXISTS oura_record_version_observed_idx
    ON oura_record_version (participant_id, data_type, observed_at DESC);

CREATE OR REPLACE VIEW oura_daily_scores AS
SELECT participant_id, data_type, record_date,
       NULLIF(payload ->> 'score', '')::double precision AS score,
       payload, imported_at
FROM oura_record
WHERE record_date IS NOT NULL AND payload ? 'score' AND source_deleted_at IS NULL;
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
