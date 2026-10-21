# Examples: Small Scripts for Everyday Tasks

This folder contains short, single-purpose scripts that sit around the main
workflows. Each one does exactly one thing, prints what it is doing, and is safe
to run while you are learning. None of them delete data.

If you have never used this repository before, start with
[`TUTORIAL.md`](TUTORIAL.md). It walks you through the whole EmotiBit pipeline
in about ten minutes **with no sensor at all**, using fake data.

## What Is Here

| Script | What it does | Needs hardware? | Needs Tiger Cloud? |
|---|---|---|---|
| [`send_fake_osc.py`](send_fake_osc.py) | Pretends to be EmotiBit Oscilloscope and sends fake EDA over the network to the bridge | No | No |
| [`plot_session.py`](plot_session.py) | Lists stored sessions, or draws one session's EDA as a PNG image | No | Yes (read-only) |
| [`import_emotibit_csv.py`](import_emotibit_csv.py) | Loads an EmotiBit SD-card recording (after the DataParser) into Tiger Cloud | No (uses a file) | Yes (with `--write`) |
| [`emotibit_brainflow.py`](emotibit_brainflow.py) | Reads EDA straight from the EmotiBit with OpenBCI's BrainFlow library, no Oscilloscope needed | Yes | No (it feeds the bridge) |
| [`queries.sql`](queries.sql) | Copy-and-paste SQL for looking at stored EDA data | No | Yes (read-only) |
| [`test_examples.py`](test_examples.py) | Offline tests for the scripts above | No | No |

All commands below assume you are in the repository root and have already run
`uv sync --locked` once.

## `send_fake_osc.py`: Test the Network Path Without a Sensor

The bridge's own `--simulate` flag generates fake values *inside* the bridge, so
it never touches the network. This script sends real OSC messages over UDP, the
same way Oscilloscope does, which proves the listener and port work.

Terminal 1:

```bash
uv run python bridge/bridge.py --no-db --warmup-seconds 5
```

Terminal 2:

```bash
uv run python examples/send_fake_osc.py --seconds 30
```

Success looks like: the sample counter in terminal 1 climbs by about 15 per
second while terminal 2 runs. If it stays at zero, the problem is the port or a
firewall, not the EmotiBit.

Options: `--port` (match `--osc-port` on the bridge), `--rate` (messages per
second), `--seconds` (0 means run until `Ctrl-C`).

## `plot_session.py`: See Your Data

```bash
uv run python examples/plot_session.py --list
uv run python examples/plot_session.py --session test-simulation
```

The first command prints every stored session with its sample count and start
time. The second prints a short summary and saves
`examples/output/test-simulation.png`. Open that file with any image viewer.

The script reads `DATABASE_URL` from the same `.env` file the bridge uses. It
runs only `SELECT` statements.

## `import_emotibit_csv.py`: Load an SD-Card Recording

EmotiBit can record to its microSD card with no computer nearby. The official
[EmotiBit DataParser](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/Working_with_emotibit_data.md)
turns the raw file into one CSV per channel. The EDA file's name ends in
`_EA.csv`.

```bash
# preview only: nothing is written
uv run python examples/import_emotibit_csv.py ~/Desktop/2026-10-18_walk_EA.csv

# happy with the preview? add a session label and --write
uv run python examples/import_emotibit_csv.py ~/Desktop/2026-10-18_walk_EA.csv --session walk-01 --write
```

The rows land in the same `biometric_sample` table the live bridge uses, tagged
with `{"source": "sd-card"}` in the metadata column, so `plot_session.py` and
every SQL query work the same way for recorded and live data.

Note: `LocalTimestamp` is only meaningful if the recording had at least one
time sync with Oscilloscope. Rows with a zero timestamp are skipped and counted.

## `emotibit_brainflow.py`: Skip Oscilloscope (Optional, Advanced)

[BrainFlow](https://brainflow.org/) is the library OpenBCI maintains for talking
to biosensors from code, and it supports EmotiBit directly over Wi-Fi. This
script reads EDA with BrainFlow and forwards each value as an OSC message, so
the bridge does not need to change at all.

```bash
# terminal 1
uv run python bridge/bridge.py --no-db
# terminal 2 (close Oscilloscope first; only one program can own the EmotiBit)
uv run --with brainflow python examples/emotibit_brainflow.py
```

`--with brainflow` installs BrainFlow for that one command only, because its
native binaries are large and most users never need it. If discovery is slow,
pass your network's broadcast address, for example `--ip-address 192.168.1.255`.

This script was written from the BrainFlow documentation and has not been run
against hardware inside this repository. Treat it as a starting point.

## `queries.sql`: SQL Cookbook

Open the file, pick a numbered query, paste it into the Tiger Cloud SQL editor,
and swap in your session ID. The queries introduce `time_bucket()`, which is the
TimescaleDB way of saying "one row per N seconds", and `time_bucket_gapfill()`,
which makes gaps visible. The only destructive query is commented out and
clearly labelled.

## Run the Example Tests

```bash
uv run python -m unittest discover -s examples -p 'test_*.py' -v
```
