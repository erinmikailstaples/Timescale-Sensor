# Timescale Sensor

This repository is a collection of three small projects for reading biometric
sensor data. Each project can be used independently. You do not need to own or
configure every device in order to use one workflow.

| Workflow | What it does | Beginner guide |
|---|---|---|
| EmotiBit EDA | Receives live electrodermal activity, shows a playful local “skin weather” label, and can save the readings to Tiger Cloud | [Start with the EmotiBit guide](emotibit/README.md) |
| AWEAR EEG | Downloads authorized EEG recordings from AWEAR and creates basic waveform and frequency summaries | [Start with the AWEAR guide](awear/README.md) |
| Oura Ring | Downloads authorized Oura cloud data as JSON or synchronizes it directly into Tiger Cloud | [Start with the Oura guide](oura/README.md) |

## Important Terms

- **Repository:** this project folder and all of the files inside it.
- **Terminal:** the command-line application where you run the examples below.
- **uv:** the tool this project uses to install Python and its packages and to
  run Python commands in the correct environment.
- **Tiger Cloud:** a hosted PostgreSQL database with TimescaleDB features. This
  project uses it to store time-series sensor readings.
- **Environment file (`.env`):** a private text file containing secrets or local
  settings. The real `.env` files are ignored by Git and must never be committed.
- **Participant alias:** a stable, non-identifying label such as
  `participant-01`. Do not use a person’s name or email address.

## Step 1: Download the Repository and Open a Terminal

Open a terminal and change into the repository directory. For example:

```bash
cd /path/to/Timescale-Sensor
```

This makes the repository the terminal’s current working directory. All commands
in the documentation assume you are here unless a step explicitly says
otherwise. Running commands from the correct directory lets `uv` find
`pyproject.toml`, `uv.lock`, and the component scripts.

You can confirm your location with:

```bash
pwd
```

The printed path should end in `Timescale-Sensor`.

## Step 2: Install the Python Environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is not
already available. Then run:

```bash
uv sync --locked
```

What this step does:

- reads the dependency list in `pyproject.toml`;
- uses the exact resolved versions recorded in `uv.lock`;
- downloads a compatible Python version if necessary; and
- creates a private `.venv` directory containing the project’s packages.

What this step does not do:

- it does not connect to a sensor;
- it does not contact Tiger Cloud, Oura, or AWEAR; and
- it does not create or upload biometric data.

Success normally means the command exits without an error. You do not need to
activate `.venv`. Use `uv run` before Python commands so uv automatically selects
the correct environment.

## Step 3: Choose One Workflow

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
4. inspect the saved CSV or JSONL file; and
5. analyze one continuous single-channel recording with MNE.

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

## Hands-On Tutorials

The component READMEs are reference guides: they explain options, behavior,
limitations, and troubleshooting. The tutorials are guided lessons: they give
you one small task at a time, explain why it is being done, provide a checkpoint,
and finish with review or cleanup.

### EmotiBit learning path

Complete these tutorials in order:

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
| `bridge/` | Live/simulated EDA receiver and Tiger Cloud writer | EmotiBit workflow |
| `emotibit/` | Oscilloscope OSC routing file | EmotiBit hardware setup |
| `sql/` | EmotiBit database table and summary view | EmotiBit database setup |
| `awear/` | AWEAR API exporter, MNE analyzer, and tests | AWEAR workflow |
| `oura/` | Oura API reader, schema, uploader, synchronizer, and tests | Oura workflow |
| `.env.example` | Safe template for EmotiBit database settings | Before running the bridge with a database |
| `pyproject.toml` | Direct Python dependency requirements | Read by uv |
| `uv.lock` | Exact resolved dependency versions | Read by `uv sync --locked` |

## Step 4: Run Offline Tests

Tests are useful after installing the environment and after changing code. These
commands use mocks or generated data, so they do not require hardware, API keys,
or a live database:

```bash
uv run python -m unittest discover -s bridge -p 'test_*.py' -v
uv run python -m unittest discover -s awear -p 'test_*.py' -v
uv run python -m unittest discover -s oura -p 'test_*.py' -v
```

Each command discovers files named `test_*.py` in one folder and prints each
test result. A final `OK` means those offline checks passed. It does not prove
that your device, network, cloud account, consent scopes, or credentials are
configured; the component guides include separate end-to-end checks.

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
