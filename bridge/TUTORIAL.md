# Tutorial: Test, Run, and Query the EmotiBit EDA Bridge

## What You Will Learn

This tutorial teaches the bridge in layers. You will first run it entirely
locally, then write simulated readings to Tiger Cloud, and finally receive real
EDA from EmotiBit Oscilloscope.

By the end, you will be able to:

- explain the bridge’s input, display, queue, and database output;
- isolate local, database, and hardware problems;
- collect a session under an opaque ID; and
- query and safely remove one session.

Estimated time: 30–45 minutes, plus physical sensor setup.

## Before You Begin

From the repository root, install dependencies:

```bash
uv sync --locked
```

For database lessons, complete [the SQL tutorial](../sql/TUTORIAL.md). For the
physical-sensor lesson, also complete
[the EmotiBit tutorial](../emotibit/TUTORIAL.md).

## Lesson 1: See What the Program Can Do

Run:

```bash
uv run python bridge/bridge.py --help
```

This prints available options and exits. It does not start a listener, generate
samples, or contact a database.

Find these options in the output:

- `--simulate`: generate fake EDA;
- `--no-db`: disable database connections;
- `--session`: choose the stored session label;
- `--device`: choose the stored device label;
- `--osc-port`: choose the UDP listening port; and
- `--warmup-seconds`: choose the score’s baseline-learning time.

Checkpoint: explain why `--simulate --no-db` is the safest first run.

## Lesson 2: Run a Completely Local Simulation

```bash
uv run python bridge/bridge.py +  --simulate +  --no-db +  --warmup-seconds 5
```

The program generates a changing signal around a few microsiemens. No hardware,
network listener, database credential, or persistent storage is used.

Watch the display for at least ten seconds. It contains:

- the current “skin weather” label;
- the latest simulated EDA value; and
- the total number of accepted samples.

The label stays quiet during the five-second warm-up, then compares a fast moving
average with a slower baseline. It describes relative signal movement, not an
emotion or medical state.

Press `Ctrl-C`.

Success checkpoint: the final count is nonzero and the program stops cleanly.

## Lesson 3: Run the Offline Tests

```bash
uv run python -m unittest discover -s bridge -p 'test_*.py' -v
```

These tests feed controlled numbers into the scoring class. They verify warm-up,
bounded output, and rejection of non-finite values. They do not test OSC or
Tiger Cloud.

Expected final line:

```text
OK
```

## Lesson 4: Write Simulated Data to Tiger Cloud

Confirm that the SQL tutorial succeeded and the repository-root `.env` contains
the correct `DATABASE_URL`. Then run:

```bash
uv run python bridge/bridge.py +  --simulate +  --session bridge-tutorial +  --device simulated-emotibit
```

Notice that `--no-db` is absent. The bridge starts a background writer, connects
to Tiger Cloud, and stores accepted samples in batches.

Let the program run for 10–15 seconds, then press `Ctrl-C`. Do not force-kill
the process: a clean stop gives the writer up to ten seconds to flush.

Checkpoint: there is no database exception and the final count is nonzero.

## Lesson 5: Query the Simulated Session

In Tiger Cloud’s SQL editor:

```sql
SELECT count(*) AS samples,
       min(time) AS first_sample,
       max(time) AS last_sample,
       min(value) AS minimum_eda,
       max(value) AS maximum_eda
FROM biometric_sample
WHERE session_id = 'bridge-tutorial';
```

This read-only query summarizes the exact tutorial session.

Success checkpoint:

- `samples` is greater than zero;
- both timestamps are present; and
- minimum and maximum values are not identical.

## Lesson 6: Receive Physical EmotiBit Data Without Saving It

After completing [the EmotiBit tutorial](../emotibit/TUTORIAL.md):

1. power EmotiBit from its battery;
2. connect the device in Oscilloscope;
3. enable OSC output; and
4. run:

   ```bash
   uv run python bridge/bridge.py --no-db --warmup-seconds 10
   ```

The program now listens on UDP port `12345` instead of generating values.
`--no-db` deliberately keeps this hardware test separate from database storage.

Success checkpoint: the sample count increases and the EDA value changes. Stop
with `Ctrl-C`.

If the count remains zero, do not add the database yet. Return to the EmotiBit
tutorial and verify the OSC route first.

## Lesson 7: Collect a Real Stored Session

Choose a stable, opaque session ID that does not contain a person’s identity:

```bash
uv run python bridge/bridge.py +  --session eda-tutorial-01 +  --device emotibit-01
```

During the default 20-second warm-up:

- remain reasonably still;
- avoid adjusting electrodes; and
- confirm that samples continue arriving.

Continue for the planned observation period, then press `Ctrl-C`. The bridge
timestamps receipt in UTC and writes each numeric EDA value with the session,
device, channel, and unit.

Checkpoint: query the session:

```sql
SELECT time, value, unit
FROM biometric_sample
WHERE session_id = 'eda-tutorial-01'
ORDER BY time
LIMIT 20;
```

## Lesson 8: Compare Raw and Summarized Data

Count raw data:

```sql
SELECT count(*) AS raw_samples
FROM biometric_sample
WHERE session_id = 'eda-tutorial-01';
```

Then view five-minute summaries:

```sql
SELECT bucket, samples, mean, minimum, maximum
FROM biometric_5m
WHERE session_id = 'eda-tutorial-01'
ORDER BY bucket;
```

The raw table is appropriate when each reading matters. The view is appropriate
for quick trend inspection. The view does not modify or remove raw samples.

## Lesson 9: Clean Up Only the Tutorial Sessions

Preview both tutorial IDs:

```sql
SELECT session_id, count(*) AS samples
FROM biometric_sample
WHERE session_id IN ('bridge-tutorial', 'eda-tutorial-01')
GROUP BY session_id;
```

If they are no longer needed:

```sql
DELETE FROM biometric_sample
WHERE session_id IN ('bridge-tutorial', 'eda-tutorial-01');
```

Deletion is permanent. Do not run the `DELETE` until the preview shows only the
intended sessions.

## Challenge Exercises

1. Run a local simulation with a 20-second warm-up and observe how long the label
   remains quiet.
2. Use `--env-file` with a private configuration stored outside the repository.
3. Choose a different OSC port in both the routing XML and `--osc-port`, verify
   it, and then restore port `12345`.
4. Query two sessions side by side without interpreting the values as emotions.

## What You Accomplished

You tested each layer independently, stored both simulated and physical EDA,
reviewed raw and bucketed data, and cleaned up targeted sessions.

For the complete option reference and troubleshooting guide, read
[`README.md`](README.md). Return to the
[repository learning path](../README.md#hands-on-tutorials) for another sensor.

