# Oura Ring Data: Read, Export, and Synchronize

This folder reads health and wellness data that has already been synchronized
from an Oura Ring to Oura’s cloud. It does not connect directly to the ring over
Bluetooth, and it does not change data in the Oura account.

There are two ways to use the tools:

| Path | What it does | Choose it when |
|---|---|---|
| **A. Direct sync** | Reads authorized Oura collections and writes them directly to Tiger Cloud | You want repeatable database updates or a historical backfill |
| **B. JSON export** | Saves a selected date range to a local JSON file, which can optionally be validated and uploaded later | You want to inspect or archive a bounded snapshot before database use |

The direct sync is the normal choice for ongoing use. The JSON path is useful
for learning, debugging, portable backups, and review before upload.

For a guided bounded sync, database inspection, idempotence check, and JSON
exercise, complete [`TUTORIAL.md`](TUTORIAL.md). Use this README as the full
OAuth, command, schema, and troubleshooting reference.

## Terms Used in This Guide

- **API:** a web interface that lets this code request data from Oura.
- **Collection or endpoint:** one category of Oura data, such as
  `daily_sleep`, `heartrate`, or `workout`.
- **OAuth:** the authorization process through which an Oura user grants an
  application permission to read selected categories of data.
- **Access token:** a secret used to authenticate API requests.
- **Refresh token:** a single-use secret exchanged for a new access token and a
  new refresh token after the access token expires.
- **Scope:** an OAuth permission such as `daily` or `heartrate`.
- **Backfill:** loading older historical data into a database.
- **Cursor:** the last successfully processed date saved for one collection.
  Later syncs can continue near that date instead of rescanning all history.
- **Idempotent:** safe to repeat without creating duplicate current records.
- **JSONB:** PostgreSQL’s queryable JSON storage type. It preserves complete Oura
  objects even when different collections contain different fields.

## Files in This Folder

| File | Purpose |
|---|---|
| [`read_oura.py`](read_oura.py) | Reads selected collections and prints or saves one JSON document |
| [`sync_to_tiger.py`](sync_to_tiger.py) | Synchronizes Oura directly to Tiger Cloud with cursors and version history |
| [`setup_schema.py`](setup_schema.py) | Creates or updates the Oura database objects without fetching Oura data |
| [`export_to_tiger.py`](export_to_tiger.py) | Validates and uploads a JSON file produced by `read_oura.py` |
| [`.env.example`](.env.example) | Template showing the required OAuth variable names |
| `test_*.py` | Offline tests that do not contact Oura or Tiger Cloud |

## Step 1: Prepare the Python Environment

Run every command in this guide from the repository root:

```bash
uv sync --locked
uv run python oura/read_oura.py --help
uv run python oura/sync_to_tiger.py --help
```

`uv sync --locked` installs the project’s exact locked Python dependencies.
The two `--help` commands load the scripts and show their options.

Success looks like: both help commands display usage text and return without an
error. These commands do not contact Oura, connect to Tiger Cloud, or write data.

## Step 2: Create Private Oura Configuration

Copy the safe template:

```bash
cp oura/.env.example oura/.env
```

Open `oura/.env` in a text editor. It contains placeholders for:

```dotenv
OURA_CLIENT_ID=YOUR_OAUTH2_CLIENT_ID
OURA_CLIENT_SECRET=YOUR_OAUTH2_CLIENT_SECRET
OURA_ACCESS_TOKEN=YOUR_OAUTH2_ACCESS_TOKEN
OURA_REFRESH_TOKEN=YOUR_OAUTH2_REFRESH_TOKEN
```

The real `oura/.env` is ignored by Git. It must never be committed or shared.
At this point the values are still placeholders; the next step obtains the real
values from Oura.

Why all four values are useful:

- the standalone reader needs `OURA_ACCESS_TOKEN`;
- the direct synchronizer also uses the client ID, client secret, and refresh
  token to recover when the access token expires; and
- Oura refresh tokens are single-use, so the synchronizer saves both newly
  returned tokens back into `oura/.env` with owner-only file permissions.

## Step 3: Authorize the Oura Account

Use an Oura account whose data you are allowed to collect. Synchronize the ring
through the Oura mobile app first; the API can only return data already processed
in Oura’s cloud.

Register an OAuth application in Oura’s developer interface and follow the
official [OAuth authentication guide](https://cloud.ouraring.com/docs/authentication).
For the manual local process below, register this exact redirect URI:

```text
http://localhost:8765/callback
```

The redirect may show a browser connection error because this repository does
not start a callback web server. That is expected: the authorization code remains
visible in the browser’s address bar.

### 3.1 Generate a state value

```bash
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

This prints a random value used to associate the request with its callback.
Copy it temporarily. Do not put access or refresh tokens in this command.

### 3.2 Open an authorization URL

Replace `YOUR_CLIENT_ID` and `YOUR_RANDOM_STATE` below, then open the URL in a
browser:

```text
https://cloud.ouraring.com/oauth/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback&scope=daily%20heartrate&state=YOUR_RANDOM_STATE
```

This example requests `daily` and `heartrate` permissions. Request only the
scopes needed for the project. On the consent screen, the user may grant fewer
scopes than requested.

After consent, compare the returned `state` parameter with the random value from
the previous step. If they differ, do not use the code. If they match, copy the
single-use `code` parameter from the callback URL.

### 3.3 Exchange the code for tokens

Run the following command promptly. It asks for secrets interactively so they
are not included directly in shell history:

```bash
uv run python -c '
import getpass
import json
import requests
response = requests.post(
    "https://api.ouraring.com/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": input("Client ID: "),
        "client_secret": getpass.getpass("Client secret: "),
        "code": getpass.getpass("Verified callback code: "),
        "redirect_uri": "http://localhost:8765/callback",
    },
    timeout=30,
)
response.raise_for_status()
print(json.dumps(response.json(), indent=2))
'
```

What this does: it sends the one-time authorization code to Oura and prints an
access token, refresh token, and expiration information in the local terminal.
It does not write the tokens into `oura/.env` automatically.

Copy the client ID, client secret, access token, and refresh token into the
matching variables in `oura/.env`. Then clear the terminal if other people can
see its scrollback. Never paste these values into documentation, chat, or source
code.

## Step 4: Understand Permissions

The script supports these collections. Availability can also depend on Oura
membership, device generation, and whether that measurement exists.

| Collections | Common OAuth scope |
|---|---|
| `daily_sleep`, `daily_readiness`, `daily_activity`, `sleep`, `daily_stress`, `daily_resilience`, `sleep_time`, `rest_mode_period`, `ring_configuration`, `ring_battery_level` | `daily` |
| `heartrate` | `heartrate` |
| `daily_spo2` | `spo2` |
| `daily_cardiovascular_age`, `vO2_max` | `heart_health` |
| `workout` | `workout` |
| `session` | `session` |
| `tag`, `enhanced_tag` | `tag` |
| `personal_info` | `personal`, plus `email` if email is required |

A `403` response usually means the token does not grant the needed scope or
the collection is unavailable for the account. The direct sync records and skips
such collections. The standalone reader stops and reports the error so a partial
JSON file is not mistaken for a complete export.

# Path A: Synchronize Directly to Tiger Cloud

Use this path for repeatable database updates.

## A1: Configure the Tiger Cloud Connection

The Oura database tools look for a connection in this order:

1. `DATABASE_URL` from configuration; or
2. a line beginning with `Service URL:` in the repository-root
   `tiger-cloud-credentials.txt`.

The URL must use TLS with `sslmode=require`, `verify-ca`, or `verify-full`.
Keep the credential file private; it is ignored by Git. A typical service URL has
this shape:

```text
postgres://USER:PASSWORD@HOST:PORT/tsdb?sslmode=require
```

Do not paste the real value into a command because the password may be saved in
shell history.

What this step does: it gives the scripts a database address. It does not test
the connection or create tables yet.

## A2: Run a Small, Bounded First Sync

For a beginner-friendly first test, request a short range and two common
collections:

```bash
uv run python oura/sync_to_tiger.py +  --participant oura-self +  --start-date 2026-10-01 +  --end-date 2026-10-07 +  --data daily_sleep daily_readiness
```

Replace the dates with a recent period after the ring was in use. Keep
`oura-self` or choose another stable opaque alias. Do not use a name or email.

This one command:

1. validates the command options and reads private credentials;
2. connects to Tiger Cloud over TLS;
3. creates or updates all Oura tables, indexes, and the score view;
4. creates an audit row in `oura_sync_run`;
5. requests the selected collections from Oura;
6. validates and converts every returned object;
7. stores its current value in `oura_record`;
8. stores each distinct payload version in `oura_record_version`;
9. records a per-collection cursor through the requested end date; and
10. marks the run `completed` or `partial`.

Data is committed after each date window. If a later request fails, earlier
completed windows remain safely stored and a later run can repeat them without
duplicating current records.

Success looks like:

```text
Done: sync run 1 is completed.
  daily_sleep: ... records read
  daily_readiness: ... records read
```

Zero records can be valid when Oura has no data in the selected dates.

## A3: Run the Normal All-Collection Sync

After the bounded test succeeds, run:

```bash
uv run python oura/sync_to_tiger.py --participant oura-self
```

With no saved cursor, each dated collection is scanned from January 1, 2015
through today in bounded windows. Oura only returns dates available for the
account, so requesting an early start does not manufacture older records.
Heart-rate and battery data use shorter 30-day request windows; most dated
collections use 90-day windows.

The command attempts every supported collection. A run marked `partial` can be
successful for all authorized collections: it means at least one other
collection returned `401` or `403` and was skipped. The final output lists
those skipped collections.

The first historical run can take several minutes and make many API requests.
Do not interrupt it merely because one collection is slow. If interruption is
necessary, use `Ctrl-C`; the next run marks the abandoned audit row as failed
and starts a new run.

## A4: Run Incremental Updates

Use the same command again:

```bash
uv run python oura/sync_to_tiger.py --participant oura-self
```

This time each collection uses its saved cursor and rereads the previous seven
days. The overlap captures late Oura processing or corrections. Unchanged
payloads do not create duplicate versions, while changed payloads update the
current row and add a new historical version.

Use the same participant alias every time for the same Oura account. A different
alias creates a separate logical copy of the data.

## A5: Control the Sync Range

Sync only selected collections:

```bash
uv run python oura/sync_to_tiger.py +  --participant oura-self +  --data daily_sleep heartrate
```

Ignore saved cursors and deliberately rescan a bounded range:

```bash
uv run python oura/sync_to_tiger.py +  --participant oura-self +  --full +  --start-date 2026-01-01 +  --end-date 2026-10-18
```

`--full` does not delete the database. It only ignores cursors when selecting
the API request start. Because writes are idempotent, unchanged current records
remain one row and identical versions remain one version.

Avoid an unbounded `--full` run unless a complete historical rescan is actually
needed; it repeats many API requests.

## A6: Verify the Direct Sync

Run these read-only queries in Tiger Cloud’s SQL editor.

Inspect recent run status:

```sql
SELECT sync_run_id, started_at, completed_at, status,
       requested_start_date, requested_end_date,
       endpoint_counts, errors
FROM oura_sync_run
WHERE participant_id = 'oura-self'
ORDER BY sync_run_id DESC
LIMIT 5;
```

Count current records and review their available date range:

```sql
SELECT data_type, count(*) AS records,
       min(record_date) AS first_date,
       max(record_date) AS last_date
FROM oura_record
WHERE participant_id = 'oura-self'
GROUP BY data_type
ORDER BY data_type;
```

Review daily scores through the convenience view:

```sql
SELECT data_type, record_date, score
FROM oura_daily_scores
WHERE participant_id = 'oura-self'
ORDER BY record_date DESC, data_type
LIMIT 30;
```

These queries do not modify data. A `partial` audit row should have an
`errors` object explaining which collections lacked authorization or account
support.

# Path B: Export JSON, Inspect It, and Optionally Upload It

Use this path when you want a local file before database storage.

## B1: Read the Default Seven Days

```bash
uv run python oura/read_oura.py
```

The reader requests the last seven calendar days, including today, for
`daily_sleep`, `daily_readiness`, `daily_activity`, and detailed `sleep`.
Progress messages go to standard error and the complete JSON document goes to
standard output.

This does not write a file or contact Tiger Cloud. The JSON may scroll through
the terminal, so the next command is usually more practical.

## B2: Save a Specific Export

```bash
uv run python oura/read_oura.py +  --start-date 2026-10-01 +  --end-date 2026-10-07 +  --data sleep heartrate daily_readiness daily_stress +  --output oura/exports/week.json
```

Replace the dates with the required inclusive calendar range. The reader creates
the output directory when necessary and writes one JSON object whose top-level
keys are the requested collections. `oura/exports/` is ignored by Git.

Success looks like progress lines followed by:

```text
Done: saved 4 data types to oura/exports/week.json.
```

The standalone reader follows API pagination but keeps the complete selected
result in memory before writing it. Use smaller ranges for high-volume heart
rate data.

To request every supported collection:

```bash
uv run python oura/read_oura.py --all --output oura/exports/all.json
```

This may include personal information and will stop if any requested collection
is unauthorized. Prefer `--data` with only the categories you need.

## B3: Inspect the Export Before Upload

Open the JSON in a trusted local editor or print only its top-level counts with:

```bash
uv run python -c '
import json
from pathlib import Path
data = json.loads(Path("oura/exports/week.json").read_text())
for name, records in data.items():
    print(name, 1 if isinstance(records, dict) else len(records))
'
```

This reads the local file only. It does not contact Oura or Tiger Cloud. Confirm
that the expected collections and approximate record counts are present without
copying sensitive payloads into logs or public tools.

## B4: Create the Oura Database Schema

```bash
uv run python oura/setup_schema.py
```

This connects to Tiger Cloud and creates missing Oura tables, columns, indexes,
and the `oura_daily_scores` view. It does not call Oura and does not upload the
JSON file. Re-running it is safe and does not erase stored records.

Success looks like:

```text
Done: Oura table and indexes are ready in Tiger Cloud.
```

The database role needs creation permissions. To use a credentials file outside
the repository root, add `--credentials-file /private/path/credentials.txt`.

## B5: Validate Without Connecting

```bash
uv run python oura/export_to_tiger.py oura/exports/week.json +  --participant participant-01 +  --dry-run
```

A dry run reads and validates the JSON structure, supported collection names,
dates, timezone-aware timestamps, finite numeric values, and stable record keys.
It does not load database credentials, open a network connection, create tables,
or upload records.

Success looks like:

```text
Dry run: validated ... records; no database connection made.
```

Fix validation errors before removing `--dry-run`.

## B6: Upload the Validated File

```bash
uv run python oura/export_to_tiger.py oura/exports/week.json +  --participant participant-01
```

This opens one database transaction and inserts new current records or updates
current records whose payload changed. If a database operation fails, the
transaction rolls back. Repeating an unchanged file with the same participant
alias changes zero rows.

Unlike the direct synchronizer, the JSON uploader does not create a sync-run
audit row, advance cursors, or populate `oura_record_version`. Use direct sync
when those features matter.

The uploader does not treat a record missing from a later JSON file as deleted.

## B7: Verify the Upload

```sql
SELECT data_type, count(*) AS records
FROM oura_record
WHERE participant_id = 'participant-01'
GROUP BY data_type
ORDER BY data_type;
```

This read-only query counts unique current records stored under the alias.
Use the same alias for later exports from the same Oura account.

## Understand the Oura Database Objects

| Object | Purpose |
|---|---|
| `oura_record` | Current version of each record identity |
| `oura_record_version` | Each distinct payload observed by direct sync |
| `oura_sync_run` | Start, completion, status, counts, and errors for direct-sync runs |
| `oura_sync_cursor` | Last completed date for each participant and collection |
| `oura_daily_scores` | View exposing top-level daily scores for easier queries |

Important `oura_record` columns:

| Column | Meaning |
|---|---|
| `participant_id` | Stable local alias, not a name or email |
| `data_type` | Collection name such as `sleep` or `heartrate` |
| `record_key` | Stable identity within participant and collection |
| `record_date` | Oura `day` or `start_day`, when supplied |
| `recorded_at` | Timestamp such as heart-rate time or sleep start, when supplied |
| `payload` | Complete Oura object stored as JSONB |
| `first_imported_at` | First time this identity appeared locally |
| `imported_at` | Time the current payload last changed |
| `sync_run_id` | Direct-sync run that last changed the current row |
| `source_deleted_at` | Reserved for future source-deletion handling |

These are regular PostgreSQL tables rather than hypertables because some Oura
objects have a date but no timestamp, while profile and configuration objects
have neither. The schema is separate from the EmotiBit `biometric_sample`
hypertable.

## Run Offline Tests

```bash
uv run python -m unittest discover -s oura -p 'test_*.py' -v
```

The tests check date filters, pagination, error handling, export validation,
stable keys, schema SQL, sync windows, and payload hashing. They use mocks and do
not contact Oura or Tiger Cloud.

A final `OK` means the local code passed these tests. It does not verify live
credentials, consent scopes, network access, or account data availability.

## Troubleshooting

- **`OURA_ACCESS_TOKEN is missing`:** replace the placeholder in
  `oura/.env` and confirm the file name is exactly `.env`.
- **HTTP 401:** the access token is invalid or expired. Direct sync can refresh
  it only when the client ID, client secret, and valid refresh token are present.
- **HTTP 403 or a partial sync:** the token lacks a required scope or the account
  does not support that collection. Reauthorize with the needed scope or sync a
  smaller `--data` list.
- **HTTP 429:** Oura is rate-limiting requests. Direct sync waits and retries a
  bounded number of times; the standalone reader reports the error.
- **Zero records:** the range may precede available data, the ring may not have
  synced, or that measurement may not exist. Zero is not automatically an error.
- **Database configuration error:** confirm the Service URL is present, valid,
  and includes an accepted TLS `sslmode`.
- **Database connection error:** check the service state, password, allowed-IP
  rules, network access, and database permissions.
- **A sync run was left `running`:** the process was interrupted before it
  could finish. Starting the next run for that participant marks the abandoned
  run failed and creates a new audit row.

## Privacy and Current Limitations

- Oura records can contain identifying and sensitive health information even
  when the local participant alias is opaque.
- Request and retain only data covered by informed consent and a valid purpose.
- Restrict database and export-file access. Delete data when it is no longer
  needed.
- This repository does not schedule syncs or receive Oura webhooks.
- The standalone reader holds the selected result in memory.
- Direct sync preserves changed versions but does not currently mark records
  deleted when they disappear from a later API response.
- Oura metrics and scores are not medical diagnoses.

## Official Resources

- [Oura API v2](https://cloud.ouraring.com/v2/docs) — endpoint contracts and data models
- [Oura OAuth authentication](https://cloud.ouraring.com/docs/authentication) — authorization, scopes, tokens, and refresh behavior
- [Oura API error handling](https://cloud.ouraring.com/docs/error-handling) — HTTP and OAuth errors
- [Oura application registration](https://cloud.ouraring.com/oauth/applications) — create and manage OAuth credentials
- [uv documentation](https://docs.astral.sh/uv/) — Python environment and package management
