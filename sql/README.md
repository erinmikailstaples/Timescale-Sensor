# Tiger Cloud Schema for EmotiBit EDA

[`schema.sql`](schema.sql) creates the Tiger Cloud database objects used by
`bridge/bridge.py`. It belongs only to the EmotiBit EDA workflow. Oura uses
different tables created by `oura/setup_schema.py`, and AWEAR EEG uses
[`awear_schema.sql`](awear_schema.sql), which `awear/upload_to_tiger.py` can
apply for you with `--create-schema`.

For ready-made queries against the EmotiBit table, see
[`examples/queries.sql`](../examples/queries.sql).

For a guided exercise that creates the schema, writes simulated rows, verifies
them, and cleans them up, complete [`TUTORIAL.md`](TUTORIAL.md). Use this README
as the schema reference.

## Terms Used in This Guide

- **PostgreSQL:** the database system used by Tiger Cloud.
- **TimescaleDB:** a PostgreSQL extension designed for time-series data.
- **Table:** rows and columns that permanently store data.
- **Hypertable:** a TimescaleDB table automatically organized into time-based
  chunks. The bridge inserts into it like a normal PostgreSQL table.
- **Index:** an additional database structure that speeds up common lookups.
- **View:** a saved query. It presents calculated results without copying the
  underlying readings.
- **SQL editor:** the Tiger Cloud web interface where SQL statements can be run.

## What the Schema Creates

| Object | What it does | Why it exists |
|---|---|---|
| `biometric_sample` | Stores every timestamped value with session, device, channel, unit, and optional metadata | Preserves the raw readings |
| Timescale hypertable | Organizes `biometric_sample` by time | Supports efficient time-series storage and queries |
| `biometric_sample_session_time_idx` | Indexes session and newest time | Speeds up reviewing one session |
| `biometric_5m` | Calculates count, mean, minimum, and maximum in five-minute buckets | Provides a quick summary without changing raw data |

The SQL uses `IF NOT EXISTS`, so it is safe to run again. Re-running it does
not erase existing samples. The view definition is updated to the version in
the file.

## Step 1: Create or Open a Tiger Cloud Service

Create a Tiger Cloud PostgreSQL service or open the service you want this project
to use. Find its web-based SQL editor.

Why this step matters: `schema.sql` calls TimescaleDB functions named
`create_hypertable` and `time_bucket`. A plain PostgreSQL database without
the TimescaleDB extension cannot run the complete file.

Limit the service’s allowed-IP rules to the computers that need access. This
reduces exposure of the database over the internet.

## Step 2: Run the Schema

Pick whichever of these three is easiest for you. They do the same thing.

**Option A, from Python** (after Step 3 below puts `DATABASE_URL` in `.env`):

```bash
uv run python sql/setup_schema.py
```

**Option B, with the Tiger CLI:**

```bash
tiger db query --file sql/schema.sql
```

**Option C, by hand:**

1. Open [`schema.sql`](schema.sql).
2. Copy its entire contents.
3. Paste them into Tiger Cloud's SQL editor.
4. Run the SQL.

What this changes: it creates one table, converts it to a hypertable, creates one
index, and creates one summary view. It does not insert sensor data.

The database user needs permission to create tables, indexes, views, and
hypertables. Success normally means the editor completes without an error.

Verify the hypertable with this read-only query:

```sql
SELECT hypertable_name
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'biometric_sample';
```

Success looks like one row containing `biometric_sample`.

## Step 3: Create the Bridge Configuration File

From the repository root, run:

```bash
cp .env.example .env
```

This copies the safe template to a private local file. Open `.env` in a text
editor and replace the placeholder URL with the **Service URL** from Tiger
Cloud’s **Connect** panel:

```dotenv
DATABASE_URL=postgres://USER:PASSWORD@HOST:PORT/tsdb?sslmode=require
DEVICE_ID=emotibit-01
```

`DATABASE_URL` tells Python which database to open and includes its password.
`sslmode=require` requires encryption while the data travels over the network.
`DEVICE_ID` is an optional, non-identifying label stored with each sample.

The real `.env` is ignored by Git. Never commit it or share its contents.

This step creates configuration only. It does not test the password and does not
write to the database.

## Step 4: Write Controlled Test Data

Use the simulated database test in [the bridge guide](../bridge/README.md):

```bash
uv run python bridge/bridge.py --simulate --session test-simulation
```

This generates fake readings and inserts them through the same database writer
used for real EmotiBit readings. Let it run for about ten seconds, stop it with
`Ctrl-C`, and then continue to the verification query below.

## Step 5: Verify the Stored Rows

Run this in Tiger Cloud’s SQL editor:

```sql
SELECT session_id, device_id, channel, count(*) AS samples,
       min(time) AS started_at, max(time) AS ended_at
FROM biometric_sample
GROUP BY session_id, device_id, channel
ORDER BY ended_at DESC;
```

This query does not change data. It groups rows by session, device, and channel
so you can confirm how many samples arrived and when collection began and ended.

The bridge currently writes:

- `time`: the UTC time the bridge received the value;
- `session_id`: the run label;
- `device_id`: the configured sensor label;
- `channel`: `eda`;
- `value`: the numeric EDA value;
- `unit`: `microsiemens`; and
- `metadata`: an empty JSON object reserved for future context.

## Step 6: Use the Summary View

Run:

```sql
SELECT bucket, session_id, mean, minimum, maximum, samples
FROM biometric_5m
WHERE channel = 'eda'
ORDER BY bucket DESC
LIMIT 20;
```

The view groups raw readings into five-minute periods. `mean` is the average,
`minimum` and `maximum` show the range, and `samples` shows how many raw rows
contributed. Querying the view does not delete or replace the raw data.

## Delete a Test Session Carefully

First preview the target:

```sql
SELECT session_id, count(*) AS samples
FROM biometric_sample
WHERE session_id = 'test-simulation'
GROUP BY session_id;
```

Only after confirming the exact session, delete it:

```sql
DELETE FROM biometric_sample WHERE session_id = 'test-simulation';
```

Deletion is permanent. The condition is essential; a `DELETE` without a
`WHERE` clause would remove every row in the table.

## Troubleshooting

- **`create_hypertable` does not exist:** the database does not have the
  TimescaleDB extension available. Use a Timescale-enabled Tiger Cloud service.
- **Permission denied:** run the schema as the service owner or grant the needed
  creation permissions.
- **Bridge cannot connect:** recopy the Service URL, retain `sslmode=require`,
  check the allowed-IP list, and confirm that the service is running.
- **`biometric_sample` does not exist:** Step 2 did not complete in the same
  database named in `DATABASE_URL`.
- **The view is empty:** the view only returns groups after rows have been
  inserted into `biometric_sample`.

