#!/usr/bin/env python3
"""Import an EmotiBit SD-card recording (parsed by EmotiBit DataParser) into Tiger Cloud.

EmotiBit can record to its microSD card with no computer nearby. Afterward, the
official EmotiBit DataParser splits the raw file into one CSV per channel. The
EDA file ends in `_EA.csv` and looks like:

    LocalTimestamp,EmotiBitTimestamp,PacketNumber,DataLength,TypeTag,ProtocolVersion,DataReliability,EA
    1760745600.123,123456,42,1,EA,1,100,2.3451

This script reads that file and stores each EA value in the same
`biometric_sample` table the live bridge uses, so every later query and plot
works the same way for recorded and live sessions.

It is SAFE BY DEFAULT: without --write it only previews what it would insert.

Usage:

    uv run python examples/import_emotibit_csv.py path/to/recording_EA.csv
    uv run python examples/import_emotibit_csv.py path/to/recording_EA.csv --session walk-01 --write
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CHANNELS = {
    # DataParser type tag -> (channel name, unit) as stored in biometric_sample
    "EA": ("eda", "microsiemens"),
    "T1": ("temperature", "celsius"),
    "PI": ("ppg_infrared", "raw"),
    "PR": ("ppg_red", "raw"),
    "PG": ("ppg_green", "raw"),
    "HR": ("heart_rate", "bpm"),
}


@dataclass(frozen=True)
class Row:
    time: datetime
    channel: str
    value: float
    unit: str


def detect_type_tag(fieldnames: list[str]) -> str:
    """The DataParser names the last column after the type tag (EA, T1, PI...)."""
    for name in reversed(fieldnames):
        if name in CHANNELS:
            return name
    raise ValueError(
        f"No known channel column in header {fieldnames}; expected one of {sorted(CHANNELS)}"
    )


def parse_file(path: Path) -> tuple[str, list[Row], int]:
    """Return (type_tag, rows, skipped_count) for one DataParser CSV."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "LocalTimestamp" not in reader.fieldnames:
            raise ValueError("Expected a DataParser CSV with a LocalTimestamp column")
        tag = detect_type_tag(list(reader.fieldnames))
        channel, unit = CHANNELS[tag]
        rows: list[Row] = []
        skipped = 0
        for record in reader:
            try:
                stamp = float(record["LocalTimestamp"])
                value = float(record[tag])
            except (TypeError, ValueError):
                skipped += 1
                continue
            # LocalTimestamp is 0 when the recording had no time sync.
            if stamp <= 0 or not math.isfinite(stamp) or not math.isfinite(value):
                skipped += 1
                continue
            rows.append(Row(datetime.fromtimestamp(stamp, tz=timezone.utc), channel, value, unit))
    return tag, rows, skipped


def load_environment(env_file: Path | None) -> None:
    from dotenv import load_dotenv

    if env_file:
        if not env_file.is_file():
            raise SystemExit(f"Environment file not found: {env_file}")
        load_dotenv(env_file)
        return
    here = Path(__file__).resolve().parent
    for candidate in (Path.cwd() / ".env", here / ".env", here.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            return


def insert_rows(database_url: str, rows: list[Row], session_id: str, device_id: str) -> int:
    import psycopg

    inserted = 0
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for start in range(0, len(rows), 1000):
                batch = rows[start : start + 1000]
                cursor.executemany(
                    """INSERT INTO biometric_sample
                       (time, session_id, device_id, channel, value, unit, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, '{"source": "sd-card"}'::jsonb)""",
                    [(r.time, session_id, device_id, r.channel, r.value, r.unit) for r in batch],
                )
                inserted += len(batch)
                print(f"inserted {inserted}/{len(rows)}", end="\r", flush=True)
        connection.commit()
    print()
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="a DataParser output file such as ..._EA.csv")
    parser.add_argument("--session", help="opaque session label (default: file name)")
    parser.add_argument("--device", default=os.getenv("DEVICE_ID", "emotibit-01"))
    parser.add_argument("--write", action="store_true", help="actually insert into Tiger Cloud")
    parser.add_argument("--env-file", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_environment(args.env_file)
    if not args.csv.is_file():
        raise SystemExit(f"File not found: {args.csv}")

    tag, rows, skipped = parse_file(args.csv)
    session_id = args.session or args.csv.stem
    channel, unit = CHANNELS[tag]

    print(f"file:     {args.csv}")
    print(f"channel:  {tag} -> {channel} ({unit})")
    print(f"rows:     {len(rows)} usable, {skipped} skipped")
    if rows:
        print(f"from:     {rows[0].time:%Y-%m-%d %H:%M:%S} UTC")
        print(f"to:       {rows[-1].time:%Y-%m-%d %H:%M:%S} UTC")
        print(f"session:  {session_id}")
        print(f"device:   {args.device}")
        print("first 3 rows:")
        for row in rows[:3]:
            print(f"  {row.time.isoformat()}  {row.value:.4f} {row.unit}")
    if not rows:
        raise SystemExit("nothing to import; if LocalTimestamp is all zero, the recording had no time sync")
    if not args.write:
        print("\npreview only. Re-run with --write to insert these rows.")
        return 0

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL missing; copy .env.example to .env and fill it in")
    inserted = insert_rows(database_url, rows, session_id, args.device)
    print(f"done; inserted={inserted} session={session_id}")
    print("plot it with: uv run python examples/plot_session.py --session " + session_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
