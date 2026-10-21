#!/usr/bin/env python3
"""Send fake EmotiBit EDA over OSC so you can test the bridge without hardware.

This script pretends to be EmotiBit Oscilloscope. It sends OSC messages named
/emotibit/eda to the same computer on UDP port 12345, which is exactly what the
real Oscilloscope does after you install emotibit/oscOutputSettings.xml.

Why this exists: `bridge.py --simulate` skips the network entirely, so it cannot
tell you whether the OSC listener itself works. This script exercises the real
UDP path end to end.

Usage (run in a second terminal while the bridge is listening):

    uv run python examples/send_fake_osc.py
    uv run python examples/send_fake_osc.py --seconds 30 --rate 15
"""

from __future__ import annotations

import argparse
import math
import random
import time


def fake_eda(elapsed: float) -> float:
    """Return a plausible-looking EDA value in microsiemens for a moment in time.

    The shape is a slow sine wave plus a repeating "flare" every 22 seconds and
    a little noise. It is the same recipe the bridge's --simulate mode uses, so
    the skin-weather display reacts to it in a familiar way.
    """
    flare = 0.9 * math.exp(-((elapsed % 22.0) - 12.0) ** 2 / 5.0)
    return 2.2 + 0.15 * math.sin(elapsed / 4.0) + flare + random.gauss(0, 0.025)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1", help="where the bridge runs")
    parser.add_argument("--port", type=int, default=12345, help="bridge --osc-port")
    parser.add_argument("--address", default="/emotibit/eda", help="OSC address")
    parser.add_argument("--rate", type=float, default=15.0, help="messages per second")
    parser.add_argument(
        "--seconds", type=float, default=0, help="stop after N seconds (0 = until Ctrl-C)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from pythonosc.udp_client import SimpleUDPClient

    client = SimpleUDPClient(args.host, args.port)
    print(f"sending {args.address} to {args.host}:{args.port} at {args.rate:g}/s")
    print("press Ctrl-C to stop")

    start = time.monotonic()
    sent = 0
    try:
        while True:
            elapsed = time.monotonic() - start
            if args.seconds and elapsed >= args.seconds:
                break
            client.send_message(args.address, fake_eda(elapsed))
            sent += 1
            if sent % int(args.rate) == 0:
                print(f"sent {sent} messages", end="\r", flush=True)
            time.sleep(1 / args.rate)
    except KeyboardInterrupt:
        pass
    print(f"\nstopped; sent={sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
