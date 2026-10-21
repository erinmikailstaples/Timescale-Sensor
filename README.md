# Timescale Sensor

Three small, independent projects that read biometric sensor data and store it
as time series in [Tiger Cloud](https://www.tigerdata.com/docs) (hosted
PostgreSQL with TimescaleDB). Pick the one that matches the device you have.

| Workflow | What it does | Beginner guide |
|---|---|---|
| EmotiBit EDA | Receives live electrodermal activity, shows a playful local "skin weather" label, and can save the readings to Tiger Cloud | [Start with the EmotiBit guide](emotibit/README.md) |
| AWEAR EEG | Downloads authorized EEG recordings from AWEAR, summarizes them, and uploads them to Tiger Cloud | [Start with the AWEAR guide](awear/README.md) |
| Oura Ring | Downloads authorized Oura cloud data as JSON or synchronizes it directly into Tiger Cloud | [Start with the Oura guide](oura/README.md) |

## Quick Start (No Hardware, No Account)

Three commands, two terminals, about ten minutes.

```bash
# 1. install uv once: https://docs.astral.sh/uv/getting-started/installation/
# 2. from the repository folder, install the Python environment
uv sync --locked
```

Terminal 1, the receiver:

```bash
uv run python bridge/bridge.py --no-db --warmup-seconds 5
```

Terminal 2, a pretend sensor:

```bash
uv run python examples/send_fake_osc.py --seconds 30
```

The sample counter in terminal 1 climbs while terminal 2 runs. You just sent
sensor data across the same network path a real EmotiBit uses. The guided
version that continues into a database and a picture of the data is
[`examples/TUTORIAL.md`](examples/TUTORIAL.md).

## Important Terms

- **Repository:** this project folder and all of the files inside it.
- **Terminal:** the command-line application where you run the commands here.
- **uv:** the tool that installs Python and packages and runs commands in the
  right environment. You never need to "activate" anything; put `uv run` in
  front of a Python command.
- **Tiger Cloud:** a hosted PostgreSQL database with TimescaleDB features. This
  project uses it to store time-series sensor readings.
- **Environment file (`.env`):** a private text file containing secrets or local
  settings. The real `.env` files are ignored by Git and must never be committed.
- **Participant alias:** a stable, non-identifying label such as
  `participant-01`. Do not use a person's name or email address.

More abbreviations are explained in the [glossary](#glossary-of-abbreviations).

## Install the Python Environment

Open a terminal in the repository folder. Every command in every guide assumes
you are here:

```bash
cd /path/to/Timescale-Sensor
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is
not already available, then run:

```bash
uv sync --locked
```

This reads `pyproject.toml`, installs the exact versions in `uv.lock`, downloads
a compatible Python if needed, and creates a private `.venv` folder. It does
not touch any sensor, cloud account, or biometric data. Success means the
command finishes without an error.

## Choose One Workflow

### Option A: Live EmotiBit EDA

Choose this workflow when you have an EmotiBit and want live electrodermal
activity (EDA). EDA measures changes in skin conductance and is reported here in
microsiemens (`uS`).

The data path is:

```text
EmotiBit -> EmotiBit Oscilloscope -> OSC/UDP -> bridge.py -> Tiger Cloud
```

Follow these guides in order:

1. [emotibit/README.md](emotibit/README.md) configures EmotiBit Oscilloscope to
   send the EDA channel to this project.
2. [sql/README.md](sql/README.md) creates the database table used to store EDA.
   You can skip this if you only want a temporary local display.
3. [bridge/README.md](bridge/README.md) tests fake data, receives the real OSC
   messages, displays the score, and optionally writes readings to the database.

The “quiet,” “breezy,” “stormy,” and “electric” labels describe signal movement
relative to a short personal baseline. They are an artful display, not emotion
detection, stress detection, lie detection, or medical interpretation.

### Option B: AWEAR EEG Export and Analysis

Choose this workflow for recordings that have already been uploaded to AWEAR.
This is not a live Bluetooth or USB connection.

Follow [awear/README.md](awear/README.md). It explains how to:

1. configure an AWEAR API key;
2. find an authorized participant ID;
3. download a small, bounded recording window;
4. inspect the saved CSV or JSONL file;
5. analyze one continuous single-channel recording with MNE; and
6. upload the export into the `eeg_record` table in Tiger Cloud.

The guide also explains metered API queries, waveform units, common artifacts,
and why frequency bands should not be treated as emotion or diagnosis labels.

### Option C: Oura API and Tiger Cloud

Choose this workflow for data already synchronized from an Oura Ring to the
Oura cloud. This code communicates with Oura’s web API, not directly with the
ring.

Follow [oura/README.md](oura/README.md). It offers two paths:

- **JSON export:** download a chosen date range to a local file. Use this when
  you want to inspect, archive, or share a bounded snapshot before database use.
- **Direct synchronization:** retrieve authorized collections and save them
  directly to Tiger Cloud. Use this for repeatable updates and historical
  backfills. The synchronizer records run status, remembers progress, and keeps
  versions when an Oura record changes.


## Set Up Tiger Cloud

You need Tiger Cloud only when you want to keep data. Everything else works
without it. There are two ways to get a database and its connection string.

### Path 1: the web console

1. Create a free service at [console.cloud.timescale.com](https://console.cloud.timescale.com/).
   A new service already includes TimescaleDB.
2. Open the service's **Connect** panel and copy the **Service URL**.
3. In the repository root run `cp .env.example .env`, open `.env`, and paste
   the URL as `DATABASE_URL`. Keep `sslmode=require`.
4. Create the tables from Python (no pasting into the SQL editor):

   ```bash
   uv run python sql/setup_schema.py          # EmotiBit tables
   uv run python sql/setup_schema.py --awear  # AWEAR tables, if you use AWEAR
   uv run python sql/setup_schema.py --check  # just list what exists
   ```

### Path 2: the Tiger CLI (fewer clicks)

[Tiger CLI](https://github.com/timescale/tiger-cli) does the same from the
terminal. Install it following the
[CLI and MCP guide](https://www.tigerdata.com/docs/learn/tiger-cli-mcp)
(on macOS: `brew install --cask timescale/tap/tiger-cli`), then:

```bash
tiger auth login
tiger service create --name sensor-lab --addons time-series
tiger db uri --with-password          # paste this into .env as DATABASE_URL
tiger db query --file sql/schema.sql  # apply the EmotiBit schema
tiger db query -c "SELECT hypertable_name FROM timescaledb_information.hypertables"
```

`tiger db query` can run any file in `sql/` or any query from
[`examples/queries.sql`](examples/queries.sql), so you never have to leave
the terminal.

### Optional: let an AI assistant help with the database

- [Tiger MCP](https://www.tigerdata.com/docs/ai/latest/mcp-server/) ships inside
  the CLI. `tiger mcp install claude-code` (or `cursor`, `codex`, `vscode`)
  lets your coding assistant list services, run queries, and read logs for you.
- [pg_aiguide](https://github.com/timescale/pg-aiguide) gives assistants
  Postgres and TimescaleDB knowledge so they write better schemas and queries.
  Use the hosted endpoint `https://mcp.tigerdata.com/docs`, or in Claude Code:

  ```bash
  claude plugin marketplace add timescale/pg-aiguide
  claude plugin install pg@aiguide
  ```

- The [Tiger Data documentation](https://www.tigerdata.com/docs) covers
  hypertables, `time_bucket`, continuous aggregates, compression, and
  retention policies, which are the natural next steps once data is flowing.

## Getting Sensor Data Into Tiger Cloud

Every workflow ends in the same place: a TimescaleDB hypertable in Tiger
Cloud. This table shows each road in, what the data looks like when it lands,
and which guide to follow. A hypertable is a normal PostgreSQL table that
TimescaleDB organizes by time behind the scenes.

| Sensor | Route | Live or after the fact? | Lands in | Guide |
|---|---|---|---|---|
| EmotiBit | Oscilloscope sends OSC to `bridge.py` | Live | `biometric_sample` (one row per reading) | [emotibit/README.md](emotibit/README.md), [bridge/README.md](bridge/README.md) |
| EmotiBit | microSD recording, EmotiBit DataParser, then `examples/import_emotibit_csv.py` | After the fact | `biometric_sample`, tagged `source: sd-card` | [emotibit/README.md](emotibit/README.md#three-ways-to-get-emotibit-data-into-tiger-cloud) |
| EmotiBit | BrainFlow reads the device, forwards OSC to `bridge.py` | Live | `biometric_sample` | [examples/README.md](examples/README.md) |
| AWEAR | `fetch_data.py` export, then `upload_to_tiger.py` | After the fact | `eeg_record` (one row per second, 256 samples in an array) | [awear/README.md](awear/README.md#step-5-upload-the-export-to-tiger-cloud) |
| Oura | `sync_to_tiger.py` reads the Oura API and writes directly | Scheduled or on demand | Oura tables with versions and cursors | [oura/README.md](oura/README.md) |
| Oura | `read_oura.py` JSON export, then `export_to_tiger.py` | After the fact | Same Oura tables | [oura/README.md](oura/README.md) |

Three habits that keep this safe for a beginner:

1. **Preview before writing.** The EmotiBit importer and the AWEAR uploader do
   nothing until you add `--write`. The bridge has `--no-db`.
2. **Label every session** with an opaque ID such as `walk-01`, never a name.
   Every later query and deletion is "where session_id = ...", so a good label
   is the difference between a clean cleanup and a scary one.
3. **One schema file per sensor.** [`sql/schema.sql`](sql/schema.sql) is
   EmotiBit, [`sql/awear_schema.sql`](sql/awear_schema.sql) is AWEAR, and
   `oura/setup_schema.py` is Oura. All of them are safe to run twice.

Once data is in, [`examples/plot_session.py`](examples/plot_session.py) draws
an EmotiBit session as a PNG, and [`examples/queries.sql`](examples/queries.sql)
is a copy-and-paste SQL cookbook.

## Hands-On Tutorials

The component READMEs are reference guides: they explain options, behavior,
limitations, and troubleshooting. The tutorials are guided lessons: they give
you one small task at a time, explain why it is being done, provide a checkpoint,
and finish with review or cleanup.

### EmotiBit learning path

Complete these tutorials in order:

0. [Run the whole pipeline with no hardware](examples/TUTORIAL.md) (optional
   but recommended). You will use a fake sender to learn the three stages
   before any device is involved.
1. [Send live EmotiBit EDA to Python](emotibit/TUTORIAL.md). You will verify the
   physical sensor, install the OSC route, and prove that samples reach the
   bridge without storing anything.
2. [Create and verify the Tiger Cloud schema](sql/TUTORIAL.md). You will create
   the hypertable and view, configure a private database URL, insert simulated
   readings, query them, and remove the tutorial session.
3. [Test and run the EDA bridge](bridge/TUTORIAL.md). You will progress from a
   local simulation to database writes and then to a real stored EmotiBit
   session.

This order separates hardware, database, and application problems. If a
checkpoint fails, stay in that tutorial instead of adding the next layer.

### AWEAR learning path

Complete [Export and inspect a short AWEAR EEG recording](awear/TUTORIAL.md).
You will verify the API key, check usage, make a deliberately narrow export,
inspect its structure, confirm units, generate an MNE summary and plot, and
review the result without assigning mental-state labels.

### Oura learning path

Complete [Synchronize Oura and verify it in Tiger Cloud](oura/TUTORIAL.md).
You will authorize daily data, run a bounded two-collection sync, inspect audit,
record, version, and cursor tables, repeat the sync to observe idempotence, and
create a separate local JSON export.

The tutorial uses a separate `oura-tutorial` participant alias so its database
records remain distinguishable from an existing `oura-self` sync.

## Repository Map

| Path | What is inside | When you use it |
|---|---|---|
| `examples/` | Fake OSC sender, session plotter, SD-card importer, BrainFlow reader, SQL cookbook, and a no-hardware tutorial | Learning, testing, and everyday tasks |
| `bridge/` | Live/simulated EDA receiver and Tiger Cloud writer | EmotiBit workflow |
| `emotibit/` | Oscilloscope OSC routing file | EmotiBit hardware setup |
| `sql/` | EmotiBit schema, AWEAR schema, and `setup_schema.py` to apply either | Database setup |
| `awear/` | AWEAR API exporter, MNE analyzer, Tiger Cloud uploader, and tests | AWEAR workflow |
| `oura/` | Oura API reader, schema, uploader, synchronizer, and tests | Oura workflow |
| `test_all.py` | Runs every offline test suite | After installing or changing code |
| `.env.example` | Safe template for EmotiBit database settings | Before running the bridge with a database |
| `pyproject.toml` | Direct Python dependency requirements | Read by uv |
| `uv.lock` | Exact resolved dependency versions | Read by `uv sync --locked` |

## Run Offline Tests

```bash
uv run python test_all.py
```

This runs every test suite (bridge, AWEAR, Oura, examples) and ends with
`ALL OK`. The tests use mocks and generated data, so they need no hardware,
API keys, or database. They prove the code works; the end-to-end checks in
each guide prove your device, credentials, and cloud service work.

To run one folder on its own:

```bash
uv run python -m unittest discover -s bridge -p 'test_*.py' -v
```

## Frequently Asked Questions

**Do I need all three devices?** No. Each folder stands alone. Most people
start with one.

**Do I need Tiger Cloud to try this?** Not at first. The bridge's `--no-db`
flag, the fake sender, the AWEAR analyzer, and the Oura JSON export all work
without a database. You need Tiger Cloud only when you want to keep data.

**Where do I get a Tiger Cloud service?** Create one at
[tigerdata.com](https://www.tigerdata.com/). A new service already has the
TimescaleDB extension, which `create_hypertable` and `time_bucket` need.

**What is `uv run`?** It runs a command inside the project's private Python
environment so you never have to "activate" anything or fight with `pip`.

**I ran a command and nothing seems to happen.** Most of the long-running
scripts print one updating line and wait for `Ctrl-C`. Check for a line that
says `listening` or `sending`; that means it is working.

**The bridge says `address already in use`.** Another program owns UDP port
12345, often an earlier copy of the bridge still running. Stop it, or pass a
different `--osc-port` on the bridge and `--port` on the sender.

**How do I undo a test upload?** Every table is keyed by a session, participant,
or source file. Run a `SELECT count(*)` with the same `WHERE` clause first, then
the `DELETE`. Examples are in [`examples/queries.sql`](examples/queries.sql) and
the AWEAR README.

**Can I use an OpenBCI EEG board with this?** Not out of the box, but BrainFlow
supports both EmotiBit and OpenBCI boards with the same API, so
[`examples/emotibit_brainflow.py`](examples/emotibit_brainflow.py) is a
reasonable template. See the library list in
[emotibit/README.md](emotibit/README.md#helpful-openbci-and-related-libraries).

**Is the "skin weather" label telling me how someone feels?** No. It only says
how much the signal is moving compared with its own recent average. Sweat,
movement, and loose electrodes all change it.

## Glossary of Abbreviations

| Term | Meaning |
|---|---|
| API | Application programming interface: a web address a program can ask for data |
| CSV | Comma-separated values: a spreadsheet saved as plain text |
| EDA | Electrodermal activity: how well skin conducts electricity, which rises with sweat |
| EEG | Electroencephalography: electrical activity measured at the scalp |
| JSON / JSONL | A text format for structured data; JSONL is one JSON object per line |
| LSL | Lab Streaming Layer: a standard for streaming many sensors on one clock |
| OSC | Open Sound Control: a simple message format for sending live numbers between programs |
| OAuth | A way to let an app read your account data without giving it your password |
| PPG | Photoplethysmography: optical pulse measurement, the green light on a smartwatch |
| PSD | Power spectral density: how much of a signal lives at each frequency |
| SQL | Structured Query Language: how you ask a database questions |
| UDP | A fast, fire-and-forget way to send network packets; OSC rides on it |
| uS | Microsiemens, the unit of EDA |
| UTC | Coordinated Universal Time; every timestamp in this project is stored in UTC |

## Secrets, Consent, and Privacy

The following local files may contain secrets and are ignored by Git:

- `.env` for the EmotiBit bridge database URL;
- `awear/.env` for the AWEAR API key;
- `oura/.env` for Oura OAuth credentials; and
- `tiger-cloud-credentials.txt` for a Tiger Cloud service URL.

Never commit those files or paste their contents into issues, chat, screenshots,
or logs. Biometric data can remain sensitive even when names are removed. Obtain
consent, use opaque participant aliases, grant the minimum account permissions,
restrict database access, and delete data that is no longer required.

## Resources

- [Tiger Data documentation](https://www.tigerdata.com/docs): Tiger Cloud, TimescaleDB, and SQL reference.
- [Tiger CLI](https://github.com/timescale/tiger-cli) and the [CLI and MCP guide](https://www.tigerdata.com/docs/learn/tiger-cli-mcp): manage services and run SQL from the terminal.
- [Tiger MCP server](https://www.tigerdata.com/docs/ai/latest/mcp-server/): give an AI assistant access to your Tiger Cloud account.
- [pg_aiguide](https://github.com/timescale/pg-aiguide): Postgres and TimescaleDB skills for AI coding tools; hosted at `https://mcp.tigerdata.com/docs`.
- [EmotiBit documentation](https://github.com/EmotiBit/EmotiBit_Docs) and [BrainFlow](https://brainflow.readthedocs.io/en/stable/SupportedBoards.html#emotibit).
- [MNE-Python](https://mne.tools/) for EEG analysis.
- [uv documentation](https://docs.astral.sh/uv/).

## License

This project is released under the [MIT License](LICENSE).
