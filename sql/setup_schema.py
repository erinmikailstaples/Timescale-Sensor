#!/usr/bin/env python3
"""Apply a schema file to Tiger Cloud from Python, so nothing has to be pasted by hand.

    uv run python sql/setup_schema.py            # EmotiBit: sql/schema.sql
    uv run python sql/setup_schema.py --awear    # AWEAR:    sql/awear_schema.sql
    uv run python sql/setup_schema.py --check    # list hypertables; change nothing

Reads DATABASE_URL from .env in the repository root (or --env-file). Both schema
files use IF NOT EXISTS, so running this twice is harmless. It never deletes.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMAS = {"emotibit": HERE / "schema.sql", "awear": HERE / "awear_schema.sql"}


def load_environment(env_file: Path | None) -> None:
    from dotenv import load_dotenv

    if env_file:
        if not env_file.is_file():
            raise SystemExit(f"Environment file not found: {env_file}")
        load_dotenv(env_file)
        return
    for candidate in (Path.cwd() / ".env", HERE.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--awear", action="store_true", help="apply the AWEAR schema instead of EmotiBit")
    parser.add_argument("--check", action="store_true", help="only list existing hypertables")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    load_environment(args.env_file)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL missing; copy .env.example to .env and paste your Tiger Cloud URI")

    import psycopg

    with psycopg.connect(database_url) as connection:
        if not args.check:
            schema = SCHEMAS["awear" if args.awear else "emotibit"]
            with connection.cursor() as cursor:
                cursor.execute(schema.read_text(encoding="utf-8"))
            connection.commit()
            print(f"applied {schema.relative_to(HERE.parent)}")
        with connection.cursor() as cursor:
            cursor.execute("SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY 1")
            names = [row[0] for row in cursor.fetchall()]
    print("hypertables in this database: " + (", ".join(names) if names else "(none yet)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
