# Tutorial: Synchronize Oura Data and Verify It in Tiger Cloud

## What You Will Learn

This tutorial uses a small date range first, synchronizes two common Oura
collections directly into Tiger Cloud, verifies the audit and data tables, then
demonstrates an incremental rerun and a local JSON export.

By the end, you will understand OAuth credentials, participant aliases, sync
runs, current records, versions, and cursors.

Estimated time: 30–45 minutes after an OAuth application is registered.

## Before You Begin

You need:

- an Oura account and ring data already synchronized through the Oura app;
- an Oura OAuth application;
- consent to collect the selected account data;
- a Tiger Cloud service and private Service URL; and
- this repository’s Python environment.

The tutorial begins with `daily_sleep` and `daily_readiness` over seven days.
It does not begin with all collections or a full historical backfill.

## Lesson 1: Prepare the Commands

From the repository root:

```bash
uv sync --locked
uv run python oura/read_oura.py --help
uv run python oura/sync_to_tiger.py --help
```

These commands install dependencies and print options. They do not request Oura
data or connect to Tiger Cloud.

Success checkpoint: both help commands exit without an error.

## Lesson 2: Create the Private OAuth File

```bash
cp oura/.env.example oura/.env
```

Open `oura/.env`. You will eventually replace all four placeholders:

```dotenv
OURA_CLIENT_ID=YOUR_OAUTH2_CLIENT_ID
OURA_CLIENT_SECRET=YOUR_OAUTH2_CLIENT_SECRET
OURA_ACCESS_TOKEN=YOUR_OAUTH2_ACCESS_TOKEN
OURA_REFRESH_TOKEN=YOUR_OAUTH2_REFRESH_TOKEN
```

The access token authorizes current requests. The client credentials and
single-use refresh token allow the direct sync to obtain and save new tokens
after expiration.

This file is ignored by Git. Never share or commit it.

## Lesson 3: Authorize Daily Data

Follow the detailed authorization steps in
[`README.md#step-3-authorize-the-oura-account`](README.md#step-3-authorize-the-oura-account).
For this tutorial, request the `daily` scope.

The authorization sequence is:

1. register the exact callback URL;
2. generate and save a random state value;
3. open the authorization URL;
4. grant the `daily` scope;
5. verify that the returned state matches;
6. exchange the one-time code for tokens; and
7. copy the four real values into `oura/.env`.

Checkpoint: `oura/.env` contains no `YOUR_...` placeholders. Do not print the
file to a shared terminal or include it in troubleshooting logs.

## Lesson 4: Configure Tiger Cloud Privately

Use one of these supported approaches:

- set `DATABASE_URL` in private configuration; or
- place the Tiger Cloud Service URL after `Service URL:` in the ignored
  repository-root `tiger-cloud-credentials.txt`.

The URL must use `sslmode=require`, `verify-ca`, or `verify-full`.

This step supplies an address and password. It does not open the connection or
create tables yet.

## Lesson 5: Choose a Safe Participant Alias and Date Range

Use a stable non-identifying alias. This tutorial uses:

```text
oura-tutorial
```

Choose a recent seven-day range in which the ring was worn and synchronized.
The example uses October 1–7, 2026. Replace it if your available data uses other
dates.

Using a separate tutorial alias keeps these rows logically separate from an
existing production alias such as `oura-self`.

## Lesson 6: Run the First Bounded Direct Sync

```bash
uv run python oura/sync_to_tiger.py +  --participant oura-tutorial +  --start-date 2026-10-01 +  --end-date 2026-10-07 +  --data daily_sleep daily_readiness
```

This command:

1. reads OAuth and database credentials;
2. connects to Tiger Cloud over TLS;
3. creates missing Oura schema objects;
4. starts an auditable sync run;
5. requests only the two collections and seven-day range;
6. writes current records and distinct payload versions;
7. saves per-collection cursors; and
8. finishes the run with counts and status.

Expected completion resembles:

```text
Done: sync run ... is completed.
  daily_sleep: ... records read
  daily_readiness: ... records read
```

Zero records can be valid if the selected range has no Oura data.

## Lesson 7: Inspect the Sync Audit

In Tiger Cloud’s SQL editor:

```sql
SELECT sync_run_id, started_at, completed_at, status,
       requested_start_date, requested_end_date,
       endpoint_counts, errors
FROM oura_sync_run
WHERE participant_id = 'oura-tutorial'
ORDER BY sync_run_id DESC
LIMIT 5;
```

This read-only query shows what was requested, how the run ended, how many
records each endpoint returned, and any skipped permissions.

Success checkpoint: the latest row has a completion time and status
`completed`. A `partial` status is also understandable when a requested
collection was unavailable; inspect `errors`.

## Lesson 8: Inspect Current Records and Versions

Count current records:

```sql
SELECT data_type, count(*) AS current_records,
       min(record_date) AS first_date,
       max(record_date) AS last_date
FROM oura_record
WHERE participant_id = 'oura-tutorial'
GROUP BY data_type
ORDER BY data_type;
```

Count stored payload versions:

```sql
SELECT data_type, count(*) AS versions
FROM oura_record_version
WHERE participant_id = 'oura-tutorial'
GROUP BY data_type
ORDER BY data_type;
```

`oura_record` represents the latest known state of each identity.
`oura_record_version` preserves each distinct payload observed by direct sync.
On a first run, the counts are often similar.

## Lesson 9: Inspect Saved Cursors

```sql
SELECT data_type, through_date, updated_at
FROM oura_sync_cursor
WHERE participant_id = 'oura-tutorial'
ORDER BY data_type;
```

A cursor records the end date successfully processed for a collection. A normal
future sync starts seven days before the cursor so late Oura changes are seen.

Checkpoint: both selected collections should have a cursor through the tutorial
end date.

## Lesson 10: Repeat the Sync to Observe Idempotence

Run the exact Lesson 6 command again.

The code rereads the bounded range, but identical current identities are not
duplicated and identical payload hashes do not create duplicate versions.

Rerun the current-record and version-count queries. If Oura did not change the
source payloads, counts should remain stable even though a new audit run exists.

This is what “idempotent” means in this workflow.

## Lesson 11: Make a Local JSON Export

```bash
uv run python oura/read_oura.py +  --start-date 2026-10-01 +  --end-date 2026-10-07 +  --data daily_sleep daily_readiness +  --output oura/exports/tutorial-week.json
```

This path calls Oura and writes one local JSON file. It does not connect to Tiger
Cloud or create a sync audit row.

Expected completion:

```text
Done: saved 2 data types to oura/exports/tutorial-week.json.
```

The export directory is ignored by Git, but the file still contains sensitive
health data.

## Lesson 12: Validate the JSON Without a Database

```bash
uv run python oura/export_to_tiger.py +  oura/exports/tutorial-week.json +  --participant oura-tutorial +  --dry-run
```

`--dry-run` validates collection names, object shapes, dates, timestamps,
numeric values, and record keys. It does not load database credentials or make a
network connection.

Expected output begins with:

```text
Dry run: validated
```

This demonstrates the difference between inspecting a portable file and running
the cursor-based direct synchronizer.

## Lesson 13: Query Daily Scores

```sql
SELECT data_type, record_date, score
FROM oura_daily_scores
WHERE participant_id = 'oura-tutorial'
ORDER BY record_date, data_type;
```

The view exposes records containing a top-level `score`. It does not calculate
new Oura scores and does not modify the stored JSON payload.

## Lesson 14: Run Offline Tests

```bash
uv run python -m unittest discover -s oura -p 'test_*.py' -v
```

The tests use mocks and do not contact Oura or Tiger Cloud. They cover date
parameters, pagination, errors, JSON validation, stable keys, schema SQL, sync
windows, and version hashing.

Expected final result: `OK`.

## Lesson 15: Decide Whether to Keep Tutorial Data

Preview the database rows:

```sql
SELECT data_type, count(*)
FROM oura_record
WHERE participant_id = 'oura-tutorial'
GROUP BY data_type;
```

If you need to remove the tutorial alias, review the schema relationships and
delete only rows for `oura-tutorial` in a controlled transaction. Do not run a
broad `DELETE` from a tutorial without first backing up required data and
confirming all dependent version, cursor, and audit rows.

Also move the local JSON export into approved storage or delete the exact file
when it is no longer needed.

## Continue to a Normal Sync

After the tutorial works, choose the production alias you will consistently use
for that account and run:

```bash
uv run python oura/sync_to_tiger.py --participant oura-self
```

With no cursor for that alias, this attempts all supported collections and scans
available history from 2015 through today in bounded windows. Read the full
[direct-sync reference](README.md#path-a-synchronize-directly-to-tiger-cloud)
before starting it.

## What You Accomplished

You performed a bounded direct sync, inspected audit/current/version/cursor
state, verified idempotence, created a local JSON export, and validated it
without a database.

For OAuth details, all command options, schema definitions, full sync behavior,
privacy guidance, and troubleshooting, read [`README.md`](README.md). Return to
the [repository tutorial index](../README.md#hands-on-tutorials) to choose another
workflow.

