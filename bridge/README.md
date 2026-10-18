# EmotiBit EDA Bridge

[`bridge.py`](bridge.py) is the program between EmotiBit Oscilloscope and Tiger
Cloud. It can generate fake EDA for testing or receive real EDA through OSC. It
prints a local “skin weather” display and can save every valid reading.

You should test the program in three stages:

1. fake data without a database;
2. fake data with the database; and
3. real EmotiBit data.

Testing one layer at a time makes errors easier to identify.

For a guided lesson that walks through all three stages with checkpoints and
cleanup, complete [`TUTORIAL.md`](TUTORIAL.md). Use this README as the complete
command and troubleshooting reference.

## What the Bridge Does

For every numeric value received at `/emotibit/eda`, the bridge:

1. records the current UTC time;
2. attaches a session ID and device ID;
3. labels the channel as `eda` and its unit as `microsiemens`;
4. updates a fast and a slow moving average for the local display; and
5. places the reading in a background database-write queue unless `--no-db`
   was selected.

The database writer commits readings in batches. A clean `Ctrl-C` shutdown gives
it time to write the last batch.

## Understanding the “Skin Weather” Display

After a warm-up period, the bridge compares recent EDA with a slower baseline
and converts their relative difference to a score from 0 through 100:

- `. quiet`: score below 12;
- `~ breezy`: score from 12 through 34;
- `* stormy`: score from 35 through 69; and
- `! electric`: score 70 or above.

The warm-up is 20 seconds by default. During warm-up the score remains quiet so
the baseline can begin adapting.

These labels are deliberately non-clinical. EDA changes with motion, electrode
contact, temperature, and sweat. The program does not detect emotion, stress,
truthfulness, or health conditions.

## Step 1: Install and Verify the Command

From the repository root, run:

```bash
uv sync --locked
uv run python bridge/bridge.py --help
```

The first command creates the project’s Python environment. The second loads the
program and prints its command-line options.

Success looks like: the help output lists options such as `--simulate`,
`--no-db`, and `--osc-port`. Neither command connects to a sensor or writes
sensor data.

## Step 2: Test Fake Data Without Tiger Cloud

Run:

```bash
uv run python bridge/bridge.py --simulate --no-db --warmup-seconds 5
```

What each option means:

- `--simulate` generates a changing fake EDA signal instead of listening for
  Oscilloscope.
- `--no-db` disables database setup and writes.
- `--warmup-seconds 5` shortens the display warm-up for this quick test.

Success looks like: the sample count grows by roughly 15 per second, the EDA
value changes, and the weather begins changing after five seconds. Press
`Ctrl-C` to stop.

If this fails, the problem is local Python code or dependencies. Hardware,
Oscilloscope, and Tiger Cloud are not involved yet.

## Step 3: Prepare Tiger Cloud

Follow [`sql/README.md`](../sql/README.md) to:

1. create the `biometric_sample` hypertable and `biometric_5m` view;
2. copy `.env.example` to a private `.env`; and
3. place the Tiger Cloud Service URL in `DATABASE_URL`.

The bridge chooses its database configuration in this order:

1. `--database-url` from the command line;
2. `DATABASE_URL` already set in the shell;
3. the file passed to `--env-file`; or
4. the first `.env` found in the working directory, beside `bridge.py`, or one
   directory above `bridge.py`.

Prefer a private environment file. A URL passed directly on the command line can
be saved in shell history, including its password.

## Step 4: Test Fake Data With Tiger Cloud

Run:

```bash
uv run python bridge/bridge.py --simulate --session test-simulation
```

This time, omit `--no-db`. The bridge reads `DATABASE_URL`, opens a database
connection in the background, and stores the generated readings under the exact
session ID `test-simulation`.

Let it run for about ten seconds, then press `Ctrl-C`. In Tiger Cloud’s SQL
editor, run:

```sql
SELECT time, value, unit, session_id, device_id
FROM biometric_sample
WHERE session_id = 'test-simulation'
ORDER BY time DESC
LIMIT 10;
```

This is a read-only query. Ten returned rows confirm that Python, TLS credentials,
database permissions, and the schema are working together.

If the test data is no longer useful, first confirm its count:

```sql
SELECT count(*) FROM biometric_sample WHERE session_id = 'test-simulation';
```

Then delete only that test session:

```sql
DELETE FROM biometric_sample WHERE session_id = 'test-simulation';
```

`DELETE` is permanent, so verify the exact session ID first.

## Step 5: Configure the Physical EmotiBit

Complete [the EmotiBit Oscilloscope guide](../emotibit/README.md). That guide
installs an XML route that maps EmotiBit’s `EA` channel to
`/emotibit/eda` on UDP port `12345`.

Use its `--no-db` verification before continuing. An increasing sample count
proves that the hardware and OSC route work without involving the database.

## Step 6: Collect a Real Session

1. Power EmotiBit from its battery and connect it in Oscilloscope.
2. Enable OSC in Oscilloscope’s Output List.
3. Choose an opaque session ID. Do not use a person’s name or email.
4. Run:

   ```bash
   uv run python bridge/bridge.py --session session-2026-10-18
   ```

5. Stay reasonably still during the default 20-second warm-up.
6. Observe the sample count and EDA value.
7. Press `Ctrl-C` once to stop and flush the final database batch.

If you omit `--session`, the program makes a random ID such as
`session-a1b2c3d4e5`. The device defaults to `DEVICE_ID` from configuration,
or `emotibit-01` when no value is configured.

## Command Options

| Option | What it changes | Example use |
|---|---|---|
| `--simulate` | Generates fake EDA instead of listening for OSC | Test Python and the database without hardware |
| `--no-db` | Disables all database writes | Test the display or physical OSC route locally |
| `--osc-port PORT` | Changes the UDP listening port from `12345` | Match a custom Oscilloscope XML route |
| `--session ID` | Sets the stored grouping label | Separate experiments and make later queries easier |
| `--device ID` | Sets the stored source-device label | Distinguish multiple EmotiBits |
| `--warmup-seconds N` | Changes how long the score learns its initial baseline | Short demo or longer stabilization |
| `--env-file PATH` | Loads settings from a chosen file | Keep configuration outside the repository |
| `--database-url URL` | Overrides all other database settings | Temporary use; avoid because passwords may enter history |

## Step 7: Review Stored Data

Read raw values for one session:

```sql
SELECT time, value, unit
FROM biometric_sample
WHERE session_id = 'session-2026-10-18' AND channel = 'eda'
ORDER BY time;
```

Read five-minute summaries:

```sql
SELECT bucket, mean, minimum, maximum, samples
FROM biometric_5m
WHERE session_id = 'session-2026-10-18' AND channel = 'eda'
ORDER BY bucket;
```

The first query preserves every sample. The second is easier for a quick trend
review because it groups many samples into five-minute buckets.

## Run Offline Tests

```bash
uv run python -m unittest discover -s bridge -p 'test_*.py' -v
```

These tests check the scoring logic using local generated values. They do not
open a network connection, receive OSC, or write to Tiger Cloud.

## Troubleshooting

- **No live samples:** first confirm that simulation works, then check the
  Oscilloscope connection, OSC enablement, `/emotibit/eda` address, and port.
- **Database URL missing:** create `.env`, pass `--env-file`, export
  `DATABASE_URL`, or use `--no-db`.
- **Database connection fails:** check `sslmode=require`, the Tiger Cloud
  allowed-IP list, credentials, service status, and whether the SQL schema ran.
- **Weather stays quiet:** wait until warm-up ends and confirm the EDA value is
  actually changing.
- **The final readings are missing:** stop with `Ctrl-C`. Force-killing the
  process can prevent the in-memory batch from being flushed.

