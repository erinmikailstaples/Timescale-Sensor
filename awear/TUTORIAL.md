# Tutorial: Export and Inspect a Short AWEAR EEG Recording

## What You Will Learn

In this tutorial, you will authenticate with AWEAR, identify an authorized
participant, export a short completed recording, validate the saved file, and
produce a basic MNE frequency report and plot.

By the end, you will understand the difference between downloading waveform data
and analyzing a local export.

Estimated time: 30–45 minutes, depending on API response time.

## Before You Begin

You need:

- an AWEAR research-group API key;
- a completed Data Use Agreement and subscribed device;
- an authorized, consented recording already synchronized to AWEAR;
- a known recording time window; and
- confirmation from AWEAR of the waveform amplitude unit.

The API may meter or bill raw-data queries. Start with the narrow five-minute
window in this tutorial and replace it with a time known to contain data.

## Lesson 1: Prepare the Environment

From the repository root:

```bash
uv sync --locked
uv run python awear/fetch_data.py --help
```

The first command installs locked dependencies. The second prints the exporter’s
commands and exits without contacting AWEAR.

Success checkpoint: help lists `members`, `usage`, and `data`.

## Lesson 2: Store the API Key Privately

```bash
cp awear/.env.example awear/.env
```

Open `awear/.env` and replace the placeholder:

```dotenv
AWEAR_API_KEY=awr_sk_your_real_key_here
```

The real file is ignored by Git. Do not place the key directly in a command,
source file, screenshot, or shared log.

This step only creates configuration. It does not verify the key or use API
quota.

## Lesson 3: Verify Authentication and Find a Participant

```bash
uv run python awear/fetch_data.py members
```

The command sends an authenticated request for members visible to the research
group. It does not download EEG waveforms.

Expected output is JSON containing a `members` list, a `count`, and opaque IDs.
Choose one returned participant ID for which you have consent and a known
recording. Do not substitute a person’s name.

Checkpoint: write the selected opaque ID in your private study notes. The
examples below use `P-A1B2C3`; replace it with the real returned ID.

If `count` is zero, stop and check the API key, Data Use Agreement, device
subscription, and active members before attempting a data request.

## Lesson 4: Check API Usage Before Exporting

```bash
uv run python awear/fetch_data.py usage
```

This asks AWEAR for the request-usage buckets associated with the key. It does
not request waveform data.

Record the reported `general` and `raw_data` usage. You can compare them after
the export to learn how the service accounts for this request.

## Lesson 5: Choose a Safe Recording Window

Find a completed five-minute interval known to contain a recording. Both
timestamps must include a timezone:

- `Z` means UTC;
- `-04:00` is an explicit offset four hours behind UTC; and
- a timestamp without `Z` or an offset is rejected.

The example uses:

```text
start: 2026-10-15T09:00:00Z
end:   2026-10-15T09:05:00Z
```

Replace both values with your authorized recording. Do not begin with an entire
day: a narrow request is faster, easier to inspect, and reduces metered data.

## Lesson 6: Export the Window as CSV

Create the ignored output directory:

```bash
mkdir -p awear/exports
```

Then export:

```bash
uv run python awear/fetch_data.py data +  --participant P-A1B2C3 +  --start 2026-10-15T09:00:00Z +  --end 2026-10-15T09:05:00Z +  --output awear/exports/tutorial-eeg.csv
```

Replace the participant and timestamps. The command requests every page in the
window, validates the records, and creates the final file after successful
completion.

Expected completion resembles:

```text
Done! Saved ... records (... samples) ...
```

Each expected record represents one second and contains 256 waveform samples.
The CSV begins with identity and timing columns followed by `s0` through
`s255`.

The exporter will not overwrite an existing destination. This prevents an
accidental repeat from destroying a reviewed export.

## Lesson 7: Inspect the Export Without Analysis

Print only the header and first data row:

```bash
sed -n '1,2p' awear/exports/tutorial-eeg.csv
```

This reads the local file and makes no API request.

Confirm:

- the header begins with timestamp, participant, and device fields;
- sample columns continue through `s255`;
- the participant is the intended opaque ID; and
- there is at least one data row.

Do not paste the full row into public logs. Even without a name, timestamps,
participant IDs, device IDs, and EEG are sensitive.

## Lesson 8: Confirm the Amplitude Unit

Before analysis, confirm whether AWEAR’s exported waveform is in:

- volts (`V`);
- millivolts (`mV`); or
- microvolts (`uV`).

Do not infer the unit from the size of the numbers. MNE uses volts internally,
and the analyzer needs the correct source unit to scale data.

The next example uses `uV` only as an example. Replace it with the unit AWEAR
confirmed for your export.

## Lesson 9: Analyze and Create a Plot

```bash
uv run python awear/analyze_eeg.py awear/exports/tutorial-eeg.csv +  --units uV +  --plot awear/exports/tutorial-spectrum.png +  > awear/exports/tutorial-summary.json
```

This command:

- reads the local CSV;
- validates ordering, continuity, participant, device, and numeric samples;
- scales the confirmed unit to volts for MNE;
- calculates a Welch power spectral density;
- writes a PNG plot; and
- sends a JSON summary through `>` into `tutorial-summary.json`.

It does not contact AWEAR or write to Tiger Cloud.

Important: shell redirection with `>` replaces an existing summary file without
asking. Use a new filename when preserving an earlier result.

Success checkpoint: both output files exist and the command reports no validation
error.

## Lesson 10: Review the Results Carefully

Inspect the summary:

```bash
sed -n '1,120p' awear/exports/tutorial-summary.json
```

Open `tutorial-spectrum.png` in a trusted local image viewer.

Review:

- the strongest frequency bin;
- delta, theta, alpha, beta, and gamma percentages;
- peak-to-peak amplitude and standard deviation; and
- the waveform for flat signal, clipping, abrupt jumps, or strong artifacts.

A peak near 10 Hz describes frequency power. It does not prove relaxation,
attention, emotion, a sleep stage, or a diagnosis. Eye movement, muscle activity,
motion, and poor contact can dominate a single-channel recording.

## Lesson 11: Run Offline Tests

```bash
uv run python -m unittest discover -s awear -p 'test_*.py' -v
```

These tests use mocked API responses and a generated 10 Hz signal. They do not
use your API key or request paid data.

Expected final result: `OK`.

## Lesson 12: Review or Remove Tutorial Files

The tutorial created:

- `awear/exports/tutorial-eeg.csv`;
- `awear/exports/tutorial-spectrum.png`; and
- `awear/exports/tutorial-summary.json`.

The exports directory is ignored by Git, but the files still contain sensitive
local data. Move them into approved storage or delete the three exact files when
they are no longer required. Verify their names before deletion.

## Challenge Exercises

1. Export the same short window as JSONL using `--format jsonl` and a new output
   name.
2. Analyze the JSONL file and compare its summary with the CSV summary.
3. Run `usage` again and compare it with Lesson 4.
4. Choose another short, artifact-reviewed window and compare frequency
   structure without assigning mental-state labels.

## What You Accomplished

You verified authentication, bounded a potentially metered request, downloaded
EEG, inspected its structure, confirmed units, and produced a cautious
descriptive analysis.

For command details, limitations, quota notes, and troubleshooting, read
[`README.md`](README.md). Return to the
[repository tutorial index](../README.md#hands-on-tutorials) to choose another
workflow.

