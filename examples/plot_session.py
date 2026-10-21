#!/usr/bin/env python3
"""List stored EmotiBit sessions, or draw one session's EDA as a PNG picture.

This is a read-only helper. It never inserts, updates, or deletes rows.

Usage:

    uv run python examples/plot_session.py --list
    uv run python examples/plot_session.py --session test-simulation
    uv run python examples/plot_session.py --session test-simulation --out my.png

It reads DATABASE_URL from your .env file, exactly like bridge.py does.
"""

from __future__ import annotations

import argparse
import os
import statistics
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def load_environment(env_file: Path | None) -> None:
    """Find a .env file the same way bridge.py does."""
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


def list_sessions(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT session_id, device_id, channel, count(*) AS samples,
                      min(time) AS started_at, max(time) AS ended_at
               FROM biometric_sample
               GROUP BY session_id, device_id, channel
               ORDER BY ended_at DESC
               LIMIT 50"""
        )
        rows = cursor.fetchall()
    if not rows:
        print("no sessions stored yet; run the bridge first")
        return
    print(f"{'session_id':<28} {'device':<14} {'chan':<5} {'samples':>8}  started (UTC)")
    for session_id, device_id, channel, samples, started, _ended in rows:
        print(f"{session_id:<28} {device_id:<14} {channel:<5} {samples:>8}  {started:%Y-%m-%d %H:%M:%S}")


def fetch_session(connection, session_id: str, channel: str):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT time, value, unit
               FROM biometric_sample
               WHERE session_id = %s AND channel = %s
               ORDER BY time""",
            (session_id, channel),
        )
        return cursor.fetchall()


def plot_rows(rows, session_id: str, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")  # draw to a file; no window needed
    import matplotlib.pyplot as plt

    times = [row[0] for row in rows]
    values = [row[1] for row in rows]
    unit = rows[0][2]

    figure, axis = plt.subplots(figsize=(11, 4))
    axis.plot(times, values, linewidth=0.8)
    axis.set_title(f"EDA for session {session_id}")
    axis.set_xlabel("time (UTC)")
    axis.set_ylabel(unit)
    axis.grid(True, alpha=0.3)
    figure.autofmt_xdate()
    figure.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out, dpi=120)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="show stored sessions and exit")
    group.add_argument("--session", help="session_id to plot")
    parser.add_argument("--channel", default="eda")
    parser.add_argument("--out", type=Path, help="PNG path (default examples/output/<session>.png)")
    parser.add_argument("--env-file", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_environment(args.env_file)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL missing; copy .env.example to .env and fill it in")

    import psycopg

    with psycopg.connect(database_url) as connection:
        if args.list:
            list_sessions(connection)
            return 0
        rows = fetch_session(connection, args.session, args.channel)

    if not rows:
        raise SystemExit(f"no rows for session {args.session!r} channel {args.channel!r}")

    values = [row[1] for row in rows]
    duration = (rows[-1][0] - rows[0][0]).total_seconds()
    print(f"session:  {args.session}")
    print(f"samples:  {len(rows)}")
    print(f"duration: {duration:.1f} s")
    print(f"mean:     {statistics.fmean(values):.3f} {rows[0][2]}")
    print(f"min/max:  {min(values):.3f} / {max(values):.3f}")

    out = args.out or OUTPUT_DIR / f"{args.session}.png"
    plot_rows(rows, args.session, out)
    print(f"saved:    {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
