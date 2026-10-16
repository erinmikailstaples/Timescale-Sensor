# Read Oura Ring Data

Read your synced health data from the [Oura API v2](https://cloud.ouraring.com/v2/docs)
and print or save it as JSON.

## Overview

This is a read-only, on-demand cloud reader, not a Bluetooth connection or a live
sensor stream. Sync your ring in the Oura app before fetching sleep data.
It does not send anything to Tiger Cloud or change your Oura records.

The script follows pagination and preserves the API's full response fields.
Daily scores and detailed sleep are fetched by default; other data types are opt-in.

| File | Purpose |
| --- | --- |
| [read_oura.py](read_oura.py) | Command-line data reader |
| [.env.example](.env.example) | OAuth access-token template |
| [test_read_oura.py](test_read_oura.py) | Offline API contract tests |

## Getting Started

### What You'll Need

- **Python 3.11+** - the repository's uv setup selects Python for you.
- **Oura Ring and account** - sync through the Oura app; API access depends on your membership and available measurements.
- **uv** - use [uv](https://docs.astral.sh/uv/getting-started/installation/) for packages and execution. These instructions use the existing root project, not pip.
- **OAuth application** - register at [Oura applications](https://cloud.ouraring.com/oauth/applications).

### Set Up With uv

Run all commands from the repository root. The project already declares
`requests` and `python-dotenv`, so you do not need to add packages.

**Install dependencies and prepare local configuration:**

```bash
uv sync
cp oura/.env.example oura/.env
uv run python oura/read_oura.py --help
```

You should see the available flags and data types. Next, get an OAuth token.

## Step 1: Authorize Your Oura Account

OAuth2 lets your application read only the data you consent to share.
Personal access tokens were retired in December 2025; do not use an old PAT.
Follow the official [authentication guide](https://cloud.ouraring.com/docs/authentication)
or use this manual local setup:

1. Register an application with redirect URI `http://localhost:8000/callback`.
2. Generate a random state value with the command below.
3. Open the authorization URL below in your browser, replacing `YOUR_CLIENT_ID`
   and `YOUR_RANDOM_STATE`. Request only the scopes you need.
4. Consent, then check that the callback URL's `state` matches your generated
   value. Copy its `code` value. No callback server is included, so the browser
   may report a connection error; the callback URL remains in its address bar.
5. Exchange that single-use code using the next command. Use the same redirect
   URI you registered. Do this promptly before the code expires.

**Generate state to protect the authorization flow:**

```bash
uv run python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

This prints a random value to use in the authorization URL and verify on return.

**Authorize the default data types plus heart rate:**

```text
https://cloud.ouraring.com/oauth/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback&scope=daily%20heartrate&state=YOUR_RANDOM_STATE
```

You should reach Oura's consent screen. For other data types, add their scopes
from the table below, separated by `%20` in this URL.

**Exchange the code locally without putting secrets in shell history:**

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
        "redirect_uri": "http://localhost:8000/callback",
    },
    timeout=30,
)
response.raise_for_status()
print(json.dumps(response.json(), indent=2))
'
```

This prints sensitive tokens locally. Put `access_token` in `oura/.env` as
`OURA_ACCESS_TOKEN=...`; store `refresh_token` securely for renewal. Never commit
either token or your client secret. Environment variables override the local file.

## Step 2: Fetch Data

**Read the last seven calendar days, including today:**

```bash
uv run python oura/read_oura.py
```

JSON contains `daily_sleep`, `daily_readiness`, `daily_activity`, and detailed
`sleep` records. Progress goes to stderr, keeping stdout valid JSON.

**Select metrics and save an explicit date range:**

```bash
uv run python oura/read_oura.py \
  --start-date 2026-10-01 --end-date 2026-10-07 \
  --data sleep heartrate daily_readiness daily_stress \
  --output oura/exports/week.json
```

The output directory is created automatically and ignored by Git. Sleep records
include available HRV, heart rate, breathing rate, and sleep-stage measurements;
readiness includes temperature deviations, not raw body-temperature readings.

**Fetch every supported type after granting the relevant scopes:**

```bash
uv run python oura/read_oura.py --all --output oura/exports/all.json
```

This includes personal information and health data. Keep exports private.

| Data types | OAuth scope |
| --- | --- |
| `daily_sleep`, `daily_readiness`, `daily_activity`, `sleep`, `daily_stress`, `daily_resilience`, `sleep_time`, `rest_mode_period`, `ring_configuration`, `ring_battery_level` | `daily` |
| `heartrate` | `heartrate` |
| `daily_spo2` | `spo2` |
| `daily_cardiovascular_age`, `vO2_max` | `heart_health` |
| `workout` | `workout` |
| `session` | `session` |
| `enhanced_tag` | `tag` |
| `personal_info` | `personal`, plus `email` for email |

`personal_info` returns an object; other result values are arrays. Empty arrays
can mean no synced or supported data, not a script failure. Date filters apply
to daily records in Oura's date semantics; heart rate and battery windows use
UTC from the start day's midnight through the end day's final microsecond.
Personal information and ring configuration have no date filter.

## Going Further

### Refresh an Expired Token

The reader does not refresh tokens automatically. Send a form-encoded POST to
`https://api.ouraring.com/oauth/token` with `grant_type=refresh_token`,
`refresh_token`, `client_id`, and `client_secret`, as shown in the official
[OAuth instructions](https://cloud.ouraring.com/docs/authentication).
Replace your stored access token and refresh token with the returned values;
use `expires_in` to track expiry. Never paste tokens into public issues or chats.

### Run Offline Tests

**Verify the reader without credentials or network access to Oura:**

```bash
uv run python -m unittest discover -s oura -p 'test_read_oura.py' -v
```

All tests should pass. They check query filters, pagination, empty responses,
and common API errors using mocked HTTP responses.

## Current Limitations

- **Not live data:** results depend on ring/app sync and Oura processing.
- **Permissions:** a 403 can mean missing consent or a membership issue. `--all`
  stops if any type fails; select fewer types with `--data` to match consent.
- **Token expiry:** a 401 requires refreshing the token or authorizing again.
- **Rate limits:** a 429 reports `Retry-After`; the script exits without retrying.
- **On-demand export:** all pages are held in memory. Use smaller date ranges
  for large histories. No database ingestion or webhook service is included.
- **Health privacy:** exports are sensitive, and these metrics are not diagnoses.

## What's Next

- Expand from seven days to a month of history with explicit date filters.
- Add another consented data type, such as workouts or SpO2.
- Load selected records into Tiger Cloud using a purpose-built schema.
- Use Oura webhooks for ongoing updates instead of repeated full-history polling.

## Resources

- [Oura API v2](https://cloud.ouraring.com/v2/docs) - endpoint contracts and data models.
- [OAuth authentication](https://cloud.ouraring.com/docs/authentication) - consent and token renewal.
- [Application registration](https://cloud.ouraring.com/oauth/applications) - create and manage credentials.
- [uv documentation](https://docs.astral.sh/uv/) - Python environment and package management.