# AWEAR EEG Export and MNE Analysis

Download AWEAR cloud recordings and inspect their waveform and frequency content with MNE-Python.

## Overview

[fetch_data.py](fetch_data.py) exports every page of a specified recording window
from `https://awearlabs.com/api/v1`. This is cloud access, not a direct Bluetooth
or USB connection to the wearable. Recordings must already be uploaded to AWEAR.

[analyze_eeg.py](analyze_eeg.py) uses MNE's `RawArray` and Welch power spectral
density (PSD) to describe the signal. PSD measures how signal power is distributed
across frequencies. The script reports a frequency peak and conventional band
percentages, not emotions, attention, sleep stages, diagnoses, or brain locations.

This workflow has two separate parts:

1. **Export:** copy a bounded recording window from AWEAR's cloud into a local
   CSV or JSONL file.
2. **Analyze:** read that local file, calculate a descriptive frequency summary,
   and optionally create a PNG image.

Exporting does not automatically analyze or upload data. Analyzing does not call
the AWEAR API or change the source recording.

For a guided five-minute export and analysis exercise, complete
[`TUTORIAL.md`](TUTORIAL.md). Use this README as the detailed command,
limitation, and troubleshooting reference.

## Terms Used in This Guide

- **EEG:** electroencephalography, a measurement of electrical activity recorded
  at the scalp.
- **API:** a web interface through which this code requests authorized data from
  AWEAR.
- **API key:** a secret that identifies and authorizes the research group.
- **Participant ID:** an opaque AWEAR identifier. It is safer than a name but is
  still linkable information and must be protected.
- **Recording window:** an explicit start and end time requested from the API.
- **CSV:** a table stored as comma-separated text. This export uses one waveform
  sample per column.
- **JSONL:** newline-delimited JSON. This export stores one record, including its
  waveform array, on each line.
- **MNE:** a Python toolkit for processing neurophysiology data.
- **Power spectral density (PSD):** a calculation describing how signal power is
  distributed across frequencies.
- **Sampling rate:** the number of waveform samples measured per second. These
  exports are expected to contain 256 samples per second.

| File | Purpose |
|---|---|
| [fetch_data.py](fetch_data.py) | Authenticated API access and CSV/JSONL export |
| [analyze_eeg.py](analyze_eeg.py) | MNE analysis, JSON summary, and optional PNG |
| [.env.example](.env.example) | API-key template |
| [test_fetch_data.py](test_fetch_data.py) | Mocked API tests, no paid requests |
| [test_analyze_eeg.py](test_analyze_eeg.py) | Synthetic-signal analysis tests |

## Getting Started

### What You'll Need

- **uv** - Install the environment and package manager from
	[Astral's instructions](https://docs.astral.sh/uv/getting-started/installation/).
	It can download the project's selected Python 3.12 automatically.
- **AWEAR API key** - Obtain an `awr_sk_...` research-group key from
	[AWEAR](https://awearlabs.com/).
- **Data access** - Sign your group's Data Use Agreement and subscribe the
	recording device on the [Devices page](https://awearlabs.com/devices).
- **Authorized recordings** - Use consented data already synced to AWEAR.
	De-identified participant IDs are still linkable identifiers.
- **Confirmed waveform units** - Ask AWEAR whether exported amplitudes are volts,
	millivolts, or microvolts. The supplied API documentation does not specify units.

### Set Up the Environment

Run commands from the repository root. uv manages `.venv` and packages using
[pyproject.toml](../pyproject.toml) and [uv.lock](../uv.lock); no activation or pip is needed.

**Install and verify** - Resolve the locked environment and check the export CLI:

```bash
uv sync --locked
uv run python awear/fetch_data.py --help
```

Help should list `members`, `usage`, and `data`. If `uv` is not found after
installation, open a new terminal or use `~/.local/bin/uv` on macOS/Linux.
Use `uv add PACKAGE` for future dependency changes. Next, configure API access.

What this step changes: `uv sync --locked` creates or updates the repository's
private `.venv` with the exact dependencies in `uv.lock`. The `--help` command
only prints instructions. Neither command contacts AWEAR or downloads EEG.

## Step 1: Configure Authentication

**Create local configuration** - Copy the template, then edit the resulting
`awear/.env` file to replace its placeholder with your real key:

```bash
cp awear/.env.example awear/.env
```

An existing `AWEAR_API_KEY` environment variable takes precedence over the file.
Never put the key in source code, shell commands, or shared logs. `.env` files
are gitignored. For another location, place `--env-file /path/to/awear.env`
before the subcommand. Now discover the participant you want to export.

What this step changes: it creates a private local configuration file and you
place the key in it. Copying the template does not test the key or make an API
request. The first real authentication test happens in Step 2.

## Step 2: Find Your Participant

**List active members** - Retrieve opaque participant IDs, not email addresses:

```bash
uv run python awear/fetch_data.py members
```

Expect JSON with `members`, `count`, and IDs such as `P-A1B2C3`. Use an actual
returned ID below. A participant may have multiple recording devices; normal
API access returns only rows from your group's subscribed devices.

What this command does: it authenticates with the configured key and asks AWEAR
for the active participants visible to the research group. It prints the result
but does not create a file or download waveform samples.

Success looks like valid JSON and a nonnegative `count`. A count of zero means
authentication worked but no active members are currently available to this
key; check the group, agreement, and device subscription before Step 3.

## Step 3: Export a Short Window

Each RIGHT_TEMP (TP10, right temporal) record contains 256 samples at 256 Hz,
equivalent to one second of data. Both time boundaries are required and must
include `Z` or an explicit UTC offset. Replace the example ID and dates with a
completed, fully synced recording window that contains your data.

**Export CSV** - Fetch all pages and retain timestamps, participant IDs, and device IDs:

```bash
mkdir -p awear/exports
uv run python awear/fetch_data.py data \
	--participant P-A1B2C3 \
	--start 2026-10-15T09:00:00Z \
	--end 2026-10-15T09:05:00Z \
	--output awear/exports/eeg.csv
```

Expect page progress followed by `Done! Saved ... records (... samples) ...`.
CSV columns are `timestamp,participant_id,device_id,s0,...,s255`. Add
`--format jsonl` and choose a `.jsonl` output to preserve a waveform array per
line instead. The analyzer accepts either format, or a saved JSON API response
containing `data`. Export timestamps are requested in UTC; samples are unmodified.

`--page-size` defaults to 5000 and accepts 1-50000; it is not a total export limit.
The destination directory must exist, and existing files are not overwritten.
An empty window produces a header-only CSV or empty JSONL. Failures remove the
temporary export; forced termination may leave a hidden `.part` file to delete.

What the two commands change: `mkdir -p` creates the ignored local export
directory if it does not exist. `fetch_data.py data` makes one or more metered
API requests, validates each page, and creates the requested output file only
after the export completes. It does not analyze the waveform or write to Tiger
Cloud.

Why start with five minutes: a narrow known window limits cost, waiting time,
memory use, and the amount of sensitive data created while setup is still being
verified. After confirming the file, expand the window deliberately.

**What export is good at:** bounded, repeatable downloads for offline analysis.
**Where it falls short:** no live streaming, automatic resume, or database loading.
Next, check units and analyze one contiguous device recording.

## Step 4: Analyze With MNE

MNE expects EEG in volts internally. `--units` is mandatory and accepts `V`,
`mV`, or `uV`; do not guess it from waveform magnitude. If AWEAR confirms a
different scaling or raw ADC counts, obtain the conversion before using this script.

**Analyze and plot** - This example is valid only if AWEAR confirms microvolts:

```bash
uv run python awear/analyze_eeg.py awear/exports/eeg.csv \
	--units uV \
	--plot awear/exports/eeg-spectrum.png \
	> awear/exports/eeg-summary.json
```

Expect a JSON report and a PNG showing the first ten seconds and the spectrum.
Omit `--plot` to produce only the JSON report; it does not require a GUI. The
plot filename must be new. Shell redirection can overwrite a summary file, so
choose summary filenames carefully and check the command's exit status.

What this command changes: it reads the existing CSV, writes the optional PNG,
and sends the JSON summary to standard output. The `>` operator is handled by
the shell and creates or replaces `eeg-summary.json`; it can overwrite an
existing file without asking. The command makes no AWEAR request and no database
write.

Success looks like both files existing, a JSON object in the summary, and a PNG
containing a short waveform panel and a spectrum panel. Review the plot for
obvious clipping, large motion artifacts, flat signal, or unexpected gaps before
interpreting the frequency percentages.

The script requires at least four ordered, contiguous one-second records from
one participant and one device. It rejects gaps, duplicate/overlapping records,
missing timezone information, non-finite samples, and zero band power. Timestamp
steps must be one second within one sample period (1/256 s). This assumes each
record timestamp has the same relationship to its sample block; confirm that
timing convention with AWEAR for precise time-aligned analysis. No automatic
sorting, interpolation, artifact removal, filtering, or re-referencing is applied.

The spectrum uses four-second Hamming windows, 50% overlap, and 0.25 Hz bins.
Band percentages sum to 100% of the measured 0.5-45 Hz power, not all recorded
power. Bands are lower-inclusive and upper-exclusive:

| Band | Frequency range |
|---|---|
| Delta | 0.5-4 Hz |
| Theta | 4-8 Hz |
| Alpha | 8-13 Hz |
| Beta | 13-30 Hz |
| Gamma | 30-45 Hz |

The JSON also includes the strongest spectral bin, raw peak-to-peak amplitude,
and standard deviation in microvolts. These amplitude measures help inspection
but are not validated quality scores. A peak in the alpha band means energy
near 8-13 Hz, not that someone is relaxed. Motion, poor electrode contact, eye
movements, and muscle activity can dominate single-channel EEG.

**What MNE analysis is good at:** inspecting signal structure and comparing
frequency content across comparable recordings.
**Where it falls short:** this single-channel export does not support the MNE
tutorial's multi-channel ICA, scalp maps, source localization, or event-related
analysis without additional sensors, metadata, and experimental event markers.

## Going Further

**Check request usage** - Inspect API-key request buckets, not monthly GB allowance:

```bash
uv run python awear/fetch_data.py usage
```

Expect `general` and `raw_data` usage. For future window discovery, the supplied
API also documents member `stats` and `sessions`; those are not CLI commands here.

This command contacts AWEAR but does not request waveform data or change the
account. Use it before and after larger exports to understand the usage reported
by the service.

**Run offline tests** - Validate exports and analyze a known synthetic 10 Hz signal:

```bash
uv run python -m unittest discover -s awear -p 'test_*.py' -v
```

Tests require no key and do not scan paid data. The synthetic 10 Hz example
should peak at 10 Hz with over 99% of its band power in alpha.

## Current Limitations

- **Billing:** the supplied docs state 500 GB per subscribed device, $0.02 per
	extra GB, a $40 monthly overage cap, and a 10 GB per-query scan cap. A smaller
	page size does not guarantee a smaller scan. Start with narrow windows.
- **Throttling:** the docs list 500/min general and 60/min raw data, but also
	mention a rolling hour and show a usage example with raw limit 100. These
	conflict; follow actual server usage and `Retry-After`. Pages pause 1.1 seconds
	apart, but other clients sharing your key can still cause throttling.
- **No retries:** errors stop the export to avoid repeating metered queries.
	`NO_PLAN` requires a device subscription; `DUA_REQUIRED` requires an agreement;
	`QUOTA_EXCEEDED` requires resolving quota/overage limits; `INVALID_KEY` and
	`KEY_REVOKED` require valid credentials. Rerunning starts from offset zero.
- **Offset pagination:** prefer completed recording windows; changes during
	export can cause missing or duplicate rows. Exports may include multiple devices;
	choose a single-device window for this analyzer.
- **Memory:** the analyzer loads the selected file into memory; start small.
	Four seconds is a computational minimum, not a validated recording duration.
- **Privacy:** `awear/exports/` is gitignored, but files elsewhere are not.
	Restrict access to these biometric files and delete data no longer needed.

## What's Next

- Visually inspect short recordings before comparing spectral summaries.
- Export additional consented participants into separate files.
- Compare consistent, artifact-reviewed recording windows rather than assigning mental-state labels.
- Integrate results into an analysis application, keeping device provenance and confirmed units.
- Add a dedicated EEG database schema; the existing EmotiBit bridge stores EDA, not EEG.

## Resources

- [MNE overview tutorial](https://mne.tools/stable/auto_tutorials/intro/10_overview.html) - The requested introduction to MNE's workflow.
- [MNE RawArray](https://mne.tools/stable/generated/mne.io.RawArray.html) - Constructing recordings from arrays.
- [AWEAR](https://awearlabs.com/) - Account access and source of the supplied API documentation.
- [uv documentation](https://docs.astral.sh/uv/) - Environment and package management.
- [Project overview](../README.md) - Choose among the EmotiBit, AWEAR, and Oura workflows.
