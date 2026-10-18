#!/usr/bin/env python3
"""Read synced Oura Cloud data using OURA_ACCESS_TOKEN from oura/.env.

Run from the repository root: uv run python oura/read_oura.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


API_URL = "https://api.ouraring.com/v2/usercollection"
ENDPOINTS = (
    "daily_activity", "daily_sleep", "daily_readiness", "sleep", "heartrate",
    "daily_spo2", "daily_stress", "daily_resilience", "daily_cardiovascular_age",
    "vO2_max", "workout", "session", "tag", "enhanced_tag", "sleep_time",
    "rest_mode_period", "ring_configuration", "ring_battery_level", "personal_info",
)
DEFAULT_ENDPOINTS = ("daily_sleep", "daily_readiness", "daily_activity", "sleep")


class OuraAPIError(RuntimeError):
    """An Oura response error with status metadata for retries and scope skips."""

    def __init__(self, endpoint: str, status_code: int, message: str,
                 retry_after: str | None = None) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code
        self.retry_after = retry_after


def query_params(endpoint: str, start: date, end: date) -> dict[str, str]:
    """Use inclusive calendar days; time-series windows are expressed in UTC."""
    if start > end:
        raise ValueError("Start date must not be after end date.")
    if endpoint in {"personal_info", "ring_configuration"}:
        return {}
    if endpoint in {"heartrate", "ring_battery_level"}:
        return {
            "start_datetime": datetime.combine(start, time.min, timezone.utc).isoformat(),
            "end_datetime": datetime.combine(end, time.max, timezone.utc).isoformat(),
        }
    return {"start_date": start.isoformat(), "end_date": end.isoformat()}


def fetch_data(session: requests.Session, endpoint: str, start: date, end: date):
    """Fetch every page of a collection, or the single personal-info object."""
    if endpoint not in ENDPOINTS:
        raise ValueError(f"Unsupported endpoint: {endpoint}")
    params = query_params(endpoint, start, end)
    records = []
    seen_tokens = set()
    while True:
        response = session.get(f"{API_URL}/{endpoint}", params=params, timeout=30)
        if response.status_code != 200:
            hints = {
                401: "Access token expired or invalid; refresh it or authorize again.",
                403: "Check the granted OAuth scopes and your Oura membership.",
                429: "Rate limited; retry after the Retry-After interval.",
            }
            hint = hints.get(response.status_code, "Check the endpoint and query parameters.")
            if response.status_code == 429:
                hint += f" Retry-After: {response.headers.get('Retry-After', 'not provided')} seconds."
            raise OuraAPIError(
                endpoint,
                response.status_code,
                f"{endpoint}: HTTP {response.status_code}. {hint}",
                response.headers.get("Retry-After"),
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"{endpoint}: expected a JSON object.")
        if endpoint == "personal_info":
            return payload
        page = payload.get("data")
        if not isinstance(page, list):
            raise ValueError(f"{endpoint}: expected a data array.")
        records.extend(page)
        next_token = payload.get("next_token")
        if not next_token:
            return records
        if not isinstance(next_token, str) or next_token in seen_tokens:
            raise ValueError(f"{endpoint}: invalid or repeated pagination token.")
        seen_tokens.add(next_token)
        params = {**params, "next_token": next_token}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read your synced Oura API v2 data as JSON.")
    parser.add_argument("--start-date", type=date.fromisoformat,
                        default=date.today() - timedelta(days=6), metavar="YYYY-MM-DD")
    parser.add_argument("--end-date", type=date.fromisoformat,
                        default=date.today(), metavar="YYYY-MM-DD")
    parser.add_argument("--data", nargs="+", choices=ENDPOINTS, default=DEFAULT_ENDPOINTS,
                        help="Data types to fetch (default: daily scores and detailed sleep).")
    parser.add_argument("--all", action="store_true", help="Fetch all supported data types.")
    parser.add_argument("--output", type=Path, help="Save JSON instead of printing it.")
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("--start-date must not be after --end-date")
    load_dotenv(Path(__file__).resolve().parent / ".env")
    token = os.getenv("OURA_ACCESS_TOKEN", "").strip()
    if not token:
        parser.error("Set OURA_ACCESS_TOKEN in oura/.env or your environment; see oura/README.md.")
    endpoints = ENDPOINTS if args.all else tuple(dict.fromkeys(args.data))
    try:
        results = {}
        with requests.Session() as session:
            session.headers.update({"Authorization": f"Bearer {token}"})
            for endpoint in endpoints:
                print(f"Fetching {endpoint}...", file=sys.stderr)
                results[endpoint] = fetch_data(session, endpoint, args.start_date, args.end_date)
        output = json.dumps(results, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
            print(f"Done: saved {len(results)} data types to {args.output}.", file=sys.stderr)
        else:
            print(output, end="")
    except requests.RequestException:
        print("Oura request failed. Check your network connection and try again.", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Oura error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
