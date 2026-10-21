#!/usr/bin/env python3
"""Read EmotiBit EDA with BrainFlow (OpenBCI's library) and forward it to the bridge.

This is an OPTIONAL, more advanced route that does not need EmotiBit Oscilloscope.
BrainFlow talks to the EmotiBit over Wi-Fi directly, and this script re-sends
each EDA value as an OSC message to /emotibit/eda, so bridge.py works unchanged.

    EmotiBit -> BrainFlow (this script) -> OSC/UDP -> bridge.py -> Tiger Cloud

BrainFlow is not in this project's locked dependencies because it ships large
native binaries. Run it with uv's one-off --with flag:

    uv run --with brainflow python examples/emotibit_brainflow.py
    uv run --with brainflow python examples/emotibit_brainflow.py --ip-address 192.168.1.255

Close Oscilloscope first: only one program can talk to the EmotiBit at a time.
This script has not been exercised against hardware in this repository; treat
it as a starting point and check the BrainFlow EmotiBit docs if it misbehaves:
https://brainflow.readthedocs.io/en/stable/SupportedBoards.html#emotibit
"""

from __future__ import annotations

import argparse
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ip-address",
        default="",
        help="broadcast address of the EmotiBit's Wi-Fi network, e.g. 192.168.1.255 "
        "(leave empty to let BrainFlow search, which is slower)",
    )
    parser.add_argument("--serial-number", default="", help="pick one EmotiBit when several exist")
    parser.add_argument("--osc-host", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=12345)
    parser.add_argument("--no-forward", action="store_true", help="print values only; send no OSC")
    parser.add_argument("--timeout", type=int, default=15, help="seconds to wait for the device")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        from brainflow.board_shim import (
            BoardIds,
            BoardShim,
            BrainFlowInputParams,
            BrainFlowPresets,
        )
    except ModuleNotFoundError:
        raise SystemExit("brainflow is not installed; run with: uv run --with brainflow python ...")

    client = None
    if not args.no_forward:
        from pythonosc.udp_client import SimpleUDPClient

        client = SimpleUDPClient(args.osc_host, args.osc_port)

    board_id = BoardIds.EMOTIBIT_BOARD
    preset = BrainFlowPresets.ANCILLARY_PRESET  # EDA and temperature live here
    params = BrainFlowInputParams()
    params.ip_address = args.ip_address
    params.serial_number = args.serial_number
    params.timeout = args.timeout

    eda_channel = BoardShim.get_eda_channels(board_id, preset)[0]
    rate = BoardShim.get_sampling_rate(board_id, preset)
    print(f"EDA sampling rate reported by BrainFlow: {rate} Hz")

    board = BoardShim(board_id, params)
    board.prepare_session()
    board.start_stream()
    print("streaming; press Ctrl-C to stop")
    sent = 0
    try:
        while True:
            time.sleep(0.25)
            data = board.get_board_data(preset=preset)  # returns and clears the buffer
            if data.size == 0:
                continue
            for value in data[eda_channel]:
                if client is not None:
                    client.send_message("/emotibit/eda", float(value))
                sent += 1
            print(f"latest EDA: {data[eda_channel][-1]:.4f} uS  forwarded: {sent}", end="\r", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        board.stop_stream()
        board.release_session()
        print(f"\nstopped; values={sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
