#!/usr/bin/env python3
"""Relay EmotiBit EDA samples from OSC to Tiger Cloud."""

from __future__ import annotations

import argparse
import math
import os
import queue
import random
import signal
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CHANNELS = {
    "/emotibit/eda": ("eda", "microsiemens"),
}


@dataclass(frozen=True)
class Sample:
    time: datetime
    session_id: str
    device_id: str
    channel: str
    value: float
    unit: str


class WeatherScore:
    """A deliberately non-clinical, baseline-relative EDA animation control."""

    def __init__(self, warmup_seconds: float = 30.0) -> None:
        self.started = time.monotonic()
        self.warmup_seconds = warmup_seconds
        self.fast: float | None = None
        self.slow: float | None = None

    def update(self, eda: float) -> int:
        if not math.isfinite(eda):
            return 0
        if self.fast is None:
            self.fast = self.slow = eda
            return 0
        self.fast += 0.08 * (eda - self.fast)
        self.slow += 0.003 * (eda - self.slow)
        if time.monotonic() - self.started < self.warmup_seconds:
            return 0
        relative_change = abs(self.fast - self.slow) / max(abs(self.slow), 0.05)
        return max(0, min(100, round(relative_change * 350)))


class TigerWriter(threading.Thread):
    def __init__(self, database_url: str, samples: queue.Queue[Sample | None]) -> None:
        super().__init__(daemon=True)
        self.database_url = database_url
        self.samples = samples
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            import psycopg

            with psycopg.connect(self.database_url) as connection:
                batch: list[Sample] = []
                stopping = False
                while not stopping:
                    try:
                        item = self.samples.get(timeout=1.0)
                        if item is None:
                            stopping = True
                        else:
                            batch.append(item)
                    except queue.Empty:
                        pass
                    if len(batch) >= 100 or (batch and (stopping or self.samples.empty())):
                        with connection.cursor() as cursor:
                            cursor.executemany(
                                """INSERT INTO biometric_sample
                                   (time, session_id, device_id, channel, value, unit)
                                   VALUES (%s, %s, %s, %s, %s, %s)""",
                                [
                                    (s.time, s.session_id, s.device_id, s.channel, s.value, s.unit)
                                    for s in batch
                                ],
                            )
                        connection.commit()
                        batch.clear()
        except Exception as exc:
            self.error = exc


class Bridge:
    def __init__(
        self,
        session_id: str,
        device_id: str,
        sample_queue: queue.Queue[Sample | None] | None,
        warmup_seconds: float,
    ) -> None:
        self.session_id = session_id
        self.device_id = device_id
        self.sample_queue = sample_queue
        self.score = WeatherScore(warmup_seconds)
        self.latest_eda = 0.0
        self.latest_score = 0
        self.sample_count = 0

    def ingest(self, osc_address: str, *values: object) -> None:
        channel_info = CHANNELS.get(osc_address)
        if channel_info is None:
            return
        channel, unit = channel_info
        received = datetime.now(timezone.utc)
        for raw in values:
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                continue
            value = float(raw)
            if not math.isfinite(value):
                continue
            self.sample_count += 1
            if self.sample_queue is not None:
                self.sample_queue.put(
                    Sample(received, self.session_id, self.device_id, channel, value, unit)
                )
            if channel == "eda":
                self.latest_eda = value
                self.latest_score = self.score.update(value)


def simulate(bridge: Bridge, stop: threading.Event) -> None:
    start = time.monotonic()
    while not stop.is_set():
        elapsed = time.monotonic() - start
        flare = 0.9 * math.exp(-((elapsed % 22.0) - 12.0) ** 2 / 5.0)
        eda = 2.2 + 0.15 * math.sin(elapsed / 4.0) + flare + random.gauss(0, 0.025)
        bridge.ingest("/emotibit/eda", eda)
        stop.wait(1 / 15)


def load_environment() -> None:
    """Load config without assuming the process was started from the repo root."""
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--env-file", type=Path)
    preliminary, _ = pre_parser.parse_known_args()

    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        if preliminary.env_file:
            raise SystemExit(
                "--env-file requires python-dotenv; install the dependencies first"
            )
        return

    if preliminary.env_file:
        env_file = preliminary.env_file.expanduser().resolve()
        if not env_file.is_file():
            raise SystemExit(f"Environment file not found: {env_file}")
        load_dotenv(env_file)
        return

    script_dir = Path(__file__).resolve().parent
    candidates = (Path.cwd() / ".env", script_dir / ".env", script_dir.parent / ".env")
    for candidate in candidates:
        if candidate.is_file():
            load_dotenv(candidate)
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        help="path to a .env file; otherwise search the working and script directories",
    )
    parser.add_argument(
        "--database-url",
        help="Tiger Cloud URI; overrides DATABASE_URL from the environment",
    )
    parser.add_argument("--osc-port", type=int, default=12345)
    parser.add_argument("--session", default=f"session-{uuid.uuid4().hex[:10]}")
    parser.add_argument("--device", default=os.getenv("DEVICE_ID", "emotibit-01"))
    parser.add_argument("--warmup-seconds", type=float, default=20.0)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--no-db", action="store_true")
    return parser.parse_args()


def main() -> int:
    load_environment()
    args = parse_args()
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not args.no_db and not database_url:
        raise SystemExit(
            "Tiger Cloud URI missing; use --database-url, --env-file, DATABASE_URL, or --no-db"
        )

    sample_queue: queue.Queue[Sample | None] | None = None
    writer: TigerWriter | None = None
    if not args.no_db:
        sample_queue = queue.Queue(maxsize=10_000)
        writer = TigerWriter(database_url, sample_queue)  # type: ignore[arg-type]
        writer.start()

    bridge = Bridge(args.session, args.device, sample_queue, args.warmup_seconds)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda _sig, _frame: stop.set())

    print(f"session={args.session} device={args.device}")
    print("mode=simulator" if args.simulate else f"listening for OSC on 0.0.0.0:{args.osc_port}")

    server = None
    if args.simulate:
        worker = threading.Thread(target=simulate, args=(bridge, stop), daemon=True)
    else:
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import ThreadingOSCUDPServer

        dispatcher = Dispatcher()
        for address in CHANNELS:
            dispatcher.map(address, bridge.ingest)
        server = ThreadingOSCUDPServer(("0.0.0.0", args.osc_port), dispatcher)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    try:
        while not stop.wait(1.0):
            if writer and writer.error:
                raise writer.error
            if bridge.latest_score < 12:
                weather = ". quiet"
            elif bridge.latest_score < 35:
                weather = "~ breezy"
            elif bridge.latest_score < 70:
                weather = "* stormy"
            else:
                weather = "! electric"
            print(
                f"skin weather: {weather:<10} EDA: {bridge.latest_eda:7.3f} uS "
                f"samples: {bridge.sample_count}",
                end="\r",
                flush=True,
            )
    finally:
        if server:
            server.shutdown()
        if sample_queue is not None:
            sample_queue.put(None)
        if writer:
            writer.join(timeout=10)
        print(f"\nstopped; samples={bridge.sample_count} session={args.session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
