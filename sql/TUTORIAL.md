# Tutorial: Create and Verify the EmotiBit Tiger Cloud Schema

## What You Will Learn

In this tutorial, you will create the database objects used by the EmotiBit EDA
bridge, configure a private connection file, write controlled simulated data,
and verify the stored rows.

By the end, you will understand the difference between a table, hypertable,
index, and view.

Estimated time: 20–30 minutes.

## Before You Begin

You need:

- a Tiger Cloud account and running service;
- access to that service’s SQL editor and **Connect** panel;
- permission to create database objects; and
- the repository’s Python environment installed with `uv sync --locked`.

This tutorial creates database objects and test rows. It does not require a
physical EmotiBit.

## Lesson 1: Inspect the Schema Before Running It

Open [`schema.sql`](schema.sql). It defines:

- `biometric_sample`: the table containing every raw sensor reading;
- a TimescaleDB hypertable organized by the `time` column;
- an index that speeds up session-and-time lookups; and
- `biometric_5m`: a view summarizing readings in five-minute buckets.

A hypertable is used like a normal PostgreSQL table but is internally divided
into time-based chunks. A view is a saved query; it does not duplicate the raw
rows.

Checkpoint: locate `CREATE TABLE`, `create_hypertable`, `CREATE INDEX`, and
`CREATE OR REPLACE VIEW` in the file.

## Lesson 2: Run the Schema in Tiger Cloud

1. Open the target Tiger Cloud service.
2. Open its SQL editor.
3. Copy the complete contents of `sql/schema.sql`.
4. Paste the SQL into the editor.
5. Run it.

This creates database structure only. It does not insert biometric data.
`IF NOT EXISTS` makes the schema safe to rerun without erasing existing rows.

Success checkpoint: the SQL editor reports no error.

Verify the hypertable:

```sql
SELECT hypertable_name
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'biometric_sample';
```

Expected result: one row named `biometric_sample`.

## Lesson 3: Create a Private Connection File

From the repository root, run:

```bash
cp .env.example .env
```

This creates a private working copy of the safe template. Open `.env` and
replace the placeholder with the Service URL from Tiger Cloud’s **Connect**
panel:

```dotenv
DATABASE_URL=postgres://USER:PASSWORD@HOST:PORT/tsdb?sslmode=require
DEVICE_ID=emotibit-01
```

The Service URL contains a password. The real `.env` is ignored by Git, but you
must still avoid screenshots, chat messages, and shared logs containing it.

`sslmode=require` tells the database client to use an encrypted connection.
`DEVICE_ID` is the opaque label stored with each reading.

Checkpoint: confirm that the file is named exactly `.env`, not `.env.txt`.

## Lesson 4: Generate Controlled Test Rows

Run:

```bash
uv run python bridge/bridge.py +  --simulate +  --session tutorial-simulation +  --warmup-seconds 5
```

This command:

- generates fake EDA approximately 15 times per second;
- labels the run `tutorial-simulation`;
- reads `DATABASE_URL` from `.env`; and
- inserts readings through the same background writer used for a real sensor.

Let it run for 10–15 seconds, then press `Ctrl-C` once. A clean stop allows the
final in-memory batch to be written.

Success checkpoint: the final terminal line reports a nonzero sample count and
no database error.

## Lesson 5: Verify the Raw Rows

Run this read-only query in Tiger Cloud:

```sql
SELECT time, session_id, device_id, channel, value, unit
FROM biometric_sample
WHERE session_id = 'tutorial-simulation'
ORDER BY time DESC
LIMIT 10;
```

Expected result:

- ten or fewer rows;
- `channel` is `eda`;
- `unit` is `microsiemens`;
- `device_id` matches the configuration; and
- values and timestamps differ across rows.

This proves that configuration, TLS networking, permissions, schema, and Python
writes all work together.

## Lesson 6: Query the Five-Minute View

```sql
SELECT bucket, samples, mean, minimum, maximum
FROM biometric_5m
WHERE session_id = 'tutorial-simulation'
ORDER BY bucket;
```

The view groups raw rows into five-minute buckets. `samples` is the number of
raw values in a bucket; the other columns summarize those values.

Checkpoint: the sample count in the view should be consistent with the number of
raw tutorial rows.

## Lesson 7: Clean Up the Tutorial Data

First count the exact target:

```sql
SELECT count(*)
FROM biometric_sample
WHERE session_id = 'tutorial-simulation';
```

If you no longer need the rows, delete only that session:

```sql
DELETE FROM biometric_sample
WHERE session_id = 'tutorial-simulation';
```

The `WHERE` clause is essential. Deletion is permanent, so always preview the
target first.

Verify cleanup:

```sql
SELECT count(*)
FROM biometric_sample
WHERE session_id = 'tutorial-simulation';
```

Expected result: `0`.

## What You Accomplished

You created the EDA database structure, configured a secure local connection,
wrote controlled data, queried raw and summarized results, and practiced a
targeted cleanup.

Continue with the [bridge tutorial](../bridge/TUTORIAL.md) to learn the complete
simulated and physical-sensor workflow. For schema reference and troubleshooting,
read [`README.md`](README.md).

