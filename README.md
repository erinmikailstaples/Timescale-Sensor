# The Skin Weather Station

A deliberately tiny first project:

```text
EmotiBit EDA sensor -> EmotiBit Oscilloscope -> Python -> Tiger Cloud
```

It stores one signal—electrodermal activity (EDA)—and prints a playful local
"skin weather" such as `quiet`, `breezy`, or `electric`. Those words are art,
not emotion detection or medical interpretation.

You do **not** need the AWEAR, Arduino boards, servo, NFC tags, or Modulinos for
this version. Save those for version 2.

For AWEAR EEG cloud exports and MNE analysis, see [the AWEAR guide](awear/README.md).

For Oura Ring cloud data and JSON exports, see [the Oura guide](oura/README.md).

## What you need

- EmotiBit, its compatible Feather, battery, microSD card, and two electrodes
- EmotiBit Oscilloscope
- A laptop with Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for environments and packages
- A Tiger Cloud account and database service

## Step 1: make sure EmotiBit works

1. Follow the official EmotiBit setup to configure its microSD card and Wi-Fi.
2. Open EmotiBit Oscilloscope and connect to the device.
3. Confirm the **EDA** graph moves when the electrodes have good skin contact.

**Safety:** whenever EmotiBit is touching a person, power it only from its
battery. Never wear it while USB or any other wire connects it to equipment
attached to wall power.

## Step 2: send EDA to this project

Close Oscilloscope. Find its `oscOutputSettings.xml` file:

- macOS: right-click the Oscilloscope app, choose **Show Package Contents**, and
  look in `Contents/Resources/`
- Windows: look in the application's `data` directory
- Linux: look in `EmotiBit Oscilloscope/bin/data/`

Back up that file, then replace it with
[`emotibit/oscOutputSettings.xml`](emotibit/oscOutputSettings.xml). Reopen
Oscilloscope, connect to EmotiBit, open **Output List**, and enable **OSC**.

Oscilloscope will now relay EDA to `127.0.0.1:12345` as `/emotibit/eda`.

## Step 3: create the Tiger Cloud table

1. Create a Tiger Cloud service.
2. Open its SQL editor and run [`sql/schema.sql`](sql/schema.sql).
3. In the service's **Connect** panel, copy the PostgreSQL connection URI.
4. Keep the allowed-IP rules limited to your current computer when possible.

On the laptop, run these commands from the repository folder:

```bash
uv sync
cp .env.example .env
```

`uv sync` uses Python 3.12 from `.python-version`, creates `.venv`, and installs
the locked dependencies. uv downloads Python if needed. Use `uv add PACKAGE`
to manage dependencies in `pyproject.toml` and `uv.lock`; `requirements.txt`
is retained for compatibility with older setups, not used by uv.

Open `.env` and replace the example `DATABASE_URL` with your Tiger Cloud URI.
Make sure it contains `sslmode=require`. The `.env` file is ignored by Git.

## Step 4: test without wearing anything

Run the built-in fake sensor first:

```bash
uv run python bridge/bridge.py --simulate
```

You should see something like:

```text
skin weather: ~ breezy    EDA: 2.413 uS    samples: 75
```

Let it run for 10 seconds, then press Ctrl-C. In Tiger Cloud's SQL editor run:

```sql
SELECT time, value, session_id
FROM biometric_sample
ORDER BY time DESC
LIMIT 10;
```

If rows appear, the cloud part works. To test the program without writing to
the cloud, use `uv run python bridge/bridge.py --simulate --no-db`.

## Step 5: use the real sensor

1. Start EmotiBit Oscilloscope and connect to your battery-powered EmotiBit.
2. Enable **OSC** in its Output List.
3. In the terminal, run:

   ```bash
  uv run python bridge/bridge.py
   ```

4. Stay fairly still for the first 20 seconds while it learns a baseline.
5. Try a long exhale, tell a ridiculous story, or hold an ice cube in your
   other hand. Watch the weather drift.
6. Press Ctrl-C to stop. The remaining readings are flushed to Tiger Cloud.

Each run gets a random session ID. Do not put a person's name in it. Ask for
consent before collecting anyone else's data, and delete sessions you no longer
need:

```sql
DELETE FROM biometric_sample WHERE session_id = 'session-id-here';
```

## What the strange words mean

The program compares a quick moving average with a slow personal baseline:

- `quiet`: little relative change
- `breezy`: small change
- `stormy`: medium change
- `electric`: larger change

Motion, electrode contact, temperature, and sweat can all move EDA. The labels
do not mean calm, stressed, truthful, or unhealthy.

## If something fails

- **No samples:** check that OSC is enabled and UDP port 12345 is not blocked.
- **Flat EDA:** improve electrode contact and check the EDA plot in Oscilloscope.
- **Database error:** re-copy the URI, check `sslmode=require`, confirm your IP
  is allowed, and make sure you ran `sql/schema.sql`.
- **Want to see it work with no database:** add `--no-db`.

Once this version works reliably, a good version 2 is the UNO R4 WiFi + Pixel
Modulino glowing with the weather. Keep that as a separate win.

## Moving the files into other folders

The runtime pieces are intentionally independent. None of them relies on the
repository having a particular name or absolute location:

| File | May be moved? | What it needs |
|---|---|---|
| `bridge/bridge.py` | Yes | Installed Python packages and configuration |
| `.env` | Yes | Pass its new location with `--env-file` |
| `sql/schema.sql` | Yes | Run it once in the Tiger Cloud SQL editor |
| `emotibit/oscOutputSettings.xml` | Yes | Copy it into Oscilloscope's required folder |
| `requirements.txt` | Yes | Only used while installing packages |

For example, the bridge can live in one folder while its private configuration
lives somewhere else:

```bash
uv run --project /path/to/Timescale-Sensor python /any/folder/bridge.py \
  --env-file /another/private/folder/skin-weather.env
```

You can also avoid a configuration file entirely:

```bash
uv run --project /path/to/Timescale-Sensor python /any/folder/bridge.py \
  --database-url 'postgres://USER:PASSWORD@HOST:PORT/tsdb?sslmode=require'
```

Be aware that the second form may save the database password in shell history;
`--env-file` is preferable. Without `--env-file`, the bridge searches for
`.env` in the current working directory, beside `bridge.py`, and one directory
above `bridge.py`, in that order.

The simulator has no file-location dependency and can run without third-party
packages:

```bash
cd /tmp
uv run --project /path/to/Timescale-Sensor python /any/folder/bridge.py --simulate --no-db
```

## References

- [EmotiBit getting started](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/Getting_Started.md)
- [EmotiBit Oscilloscope OSC output](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/EmotiBitOscilloscope_reference_manual.md)
- [EmotiBit EDA TypeTag](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/Working_with_emotibit_data.md)
- [Tiger Data documentation](https://docs.tigerdata.com/)
