# Tutorial: The Whole EmotiBit Pipeline With No Hardware

## What You Will Learn

In this tutorial you will run every part of the EmotiBit path using fake data,
so you can see how the pieces fit together before a real sensor is involved.

By the end, you will be able to:

- explain the three stages: a sender, the bridge, and the database;
- prove that OSC messages travel across the network to the bridge;
- store a session in Tiger Cloud and look at it as a picture; and
- find and safely delete a test session.

Estimated time: 10 minutes without a database, 25 minutes with one.

## Before You Begin

- Install the environment from the repository root with `uv sync --locked`.
- For Lessons 3 to 5, complete the [SQL tutorial](../sql/TUTORIAL.md) so that
  `biometric_sample` exists and `.env` contains your `DATABASE_URL`.
- You will need two terminal windows open in the repository root.

No EmotiBit, Oscilloscope, or electrodes are used anywhere in this tutorial.

## Lesson 1: Meet the Three Stages

```text
sender  ->  OSC message over UDP port 12345  ->  bridge.py  ->  Tiger Cloud
```

In real life the sender is EmotiBit Oscilloscope. Today the sender is
`examples/send_fake_osc.py`. Everything downstream of the sender is identical,
which is the whole point: when a real sensor misbehaves later, you will already
know the rest of the chain works.

Checkpoint: say out loud which stage you would blame if the bridge shows zero
samples but the sender says it sent hundreds. (Answer: the network between them.)

## Lesson 2: Send Fake Messages Across the Network

Terminal 1, start the bridge in listen-only mode:

```bash
uv run python bridge/bridge.py --no-db --warmup-seconds 5
```

You should see `listening for OSC on 0.0.0.0:12345` and a counter at zero.

Terminal 2, start the fake sender for thirty seconds:

```bash
uv run python examples/send_fake_osc.py --seconds 30
```

Watch terminal 1. The `samples:` number climbs, the EDA value changes, and after
five seconds the "skin weather" label starts moving. When the sender finishes,
press `Ctrl-C` in terminal 1.

Success checkpoint: the bridge's final line reports roughly 450 samples
(15 per second for 30 seconds).

If the counter stayed at zero, something between the two programs is blocking
UDP port 12345. Try `--port 12346` on the sender and `--osc-port 12346` on the
bridge together.

## Lesson 3: Store a Fake Session

Now remove `--no-db` and give the session a clear test name.

Terminal 1:

```bash
uv run python bridge/bridge.py --session tutorial-fake --warmup-seconds 5
```

Terminal 2:

```bash
uv run python examples/send_fake_osc.py --seconds 30
```

When the sender finishes, press `Ctrl-C` once in terminal 1 and wait for it to
print `stopped`. That pause lets the last batch of rows reach the database.

What changed: the bridge opened a connection using `DATABASE_URL` and inserted
each reading into `biometric_sample` under `session_id = 'tutorial-fake'`.

## Lesson 4: Look at the Data Two Ways

List what is stored:

```bash
uv run python examples/plot_session.py --list
```

You should see `tutorial-fake` with about 450 samples. Now draw it:

```bash
uv run python examples/plot_session.py --session tutorial-fake
```

Open `examples/output/tutorial-fake.png`. You should see a gentle wave with one
or two bumps, which are the fake "flares" the sender adds every 22 seconds.

Then open `examples/queries.sql`, copy query 3 (ten-second averages) into the
Tiger Cloud SQL editor, replace the session ID, and run it. The numbers in the
`mean` column should match the shape of the picture.

Checkpoint: you have now seen the same data as rows and as a line, which is the
daily rhythm of time-series work.

## Lesson 5: Clean Up Safely

In the SQL editor, preview first:

```sql
SELECT count(*) FROM biometric_sample WHERE session_id = 'tutorial-fake';
```

If the count is what you expect, delete only that session:

```sql
DELETE FROM biometric_sample WHERE session_id = 'tutorial-fake';
```

Never run a `DELETE` without a `WHERE` clause. Rerun the `--list` command to
confirm the session is gone.

## What You Accomplished

You ran a sender, a receiver, and a database as three separate programs, proved
the network path with fake data, stored and plotted a session, and removed it.

Next steps:

- Plug in the real sensor with the [EmotiBit tutorial](../emotibit/TUTORIAL.md).
  Only the sender changes.
- Load an SD-card recording with `import_emotibit_csv.py`; see
  [`README.md`](README.md).
