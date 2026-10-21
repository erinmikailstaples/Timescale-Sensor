# Configure EmotiBit for the EDA Bridge

This folder contains the EmotiBit Oscilloscope routing file used by the project.
It tells Oscilloscope to send electrodermal activity (EDA) to the Python bridge
running on the same computer.

```text
EmotiBit -> Oscilloscope -> 127.0.0.1:12345 /emotibit/eda -> bridge.py
```

This guide configures the hardware and Oscilloscope side only. It does not create
a database or start the Python receiver.

For a guided exercise with checkpoints, complete
[`TUTORIAL.md`](TUTORIAL.md). Use this README afterward as the setup and
troubleshooting reference.

## Terms Used in This Guide

- **EDA:** electrodermal activity, a measurement of skin conductance. EmotiBit
  names this input channel `EA`.
- **OSC:** Open Sound Control, a message format that applications can use to send
  real-time values.
- **UDP port:** a numbered network destination. Oscilloscope and the bridge must
  use the same port. This project uses port `12345`.
- **OSC address:** the name inside an OSC message. This project expects
  `/emotibit/eda`.
- **localhost (`127.0.0.1`):** the computer currently running Oscilloscope.

## What You Need

- An EmotiBit and compatible Feather board
- A charged battery, microSD card, and two electrodes
- EmotiBit Oscilloscope installed and able to connect to the device
- This repository installed on the computer running Oscilloscope

Use the official [EmotiBit documentation](https://github.com/EmotiBit/EmotiBit_Docs/tree/master)
for assembly, firmware, microSD Wi-Fi configuration, and Oscilloscope installation.

> Safety: when EmotiBit is touching a person, power it only from its battery.
> Do not wear it while USB or another wire connects it to wall-powered equipment.

## Step 1: Verify EmotiBit Before Changing Any Files

1. Start EmotiBit Oscilloscope.
2. Connect Oscilloscope to the EmotiBit.
3. Attach the EDA electrodes as described in the official instructions.
4. Find the EDA graph and confirm that it receives values.

Why this step matters: it tests the device, Wi-Fi, and electrode contact before
the custom routing or Python program is involved. If the graph is missing or
flat here, changing this repository will not fix the underlying connection.

Success looks like: Oscilloscope shows a live EDA trace. Natural movement,
contact pressure, temperature, and moisture may all change the trace.

## Step 2: Find and Back Up Oscilloscope’s Routing File

Close Oscilloscope before changing its configuration. Locate its existing
`oscOutputSettings.xml`:

- **macOS:** right-click the Oscilloscope application, choose **Show Package
  Contents**, and look in `Contents/Resources/`.
- **Windows:** look in the application’s `data` directory.
- **Linux:** look in `EmotiBit Oscilloscope/bin/data/`.

Copy the original file to a safe backup location.

Why this step matters: Oscilloscope may already contain routes that another
project needs. A backup lets you restore the exact previous configuration.

This step does not change the EmotiBit itself. It only prepares to change how
the desktop Oscilloscope application forwards data.

## Step 3: Install This Project’s Routing File

Replace Oscilloscope’s active `oscOutputSettings.xml` with
[`emotibit/oscOutputSettings.xml`](oscOutputSettings.xml), then reopen
Oscilloscope.

The supplied file:

1. selects EmotiBit as its input;
2. selects OSC as its output;
3. sends messages to `127.0.0.1` on UDP port `12345`; and
4. maps EmotiBit’s `EA` channel to `/emotibit/eda`.

Why this step matters: `bridge.py` only listens for the exact OSC address
`/emotibit/eda`. The XML translates EmotiBit’s channel name into that address.

This configuration forwards only EDA. It does not forward temperature, heart
rate, accelerometer data, or other EmotiBit channels.

## Step 4: Enable OSC Output

1. Connect Oscilloscope to EmotiBit again.
2. Open Oscilloscope’s **Output List**.
3. Enable **OSC**.

Why this step matters: installing the XML defines the route, but Oscilloscope
does not necessarily transmit on that route until OSC output is enabled.

UDP does not create a visible connected session. The correct way to verify it is
to run a listener in the next step.

## Step 5: Verify Live Messages Without a Database

From the repository root, run:

```bash
uv run python bridge/bridge.py --no-db
```

`--no-db` means “do not connect to Tiger Cloud.” The command only listens for
OSC messages and displays what it receives. It does not permanently save data.

Success looks like:

- the startup message says it is listening on `0.0.0.0:12345`;
- the sample count continually increases; and
- the displayed EDA value changes as messages arrive.

Press `Ctrl-C` once to stop. The final line prints the total sample count.

## When You Would Change the XML

Most users should use the supplied file unchanged. Change it only when:

- another program already uses UDP port `12345`; or
- Oscilloscope and the bridge must run on different computers.

For a different port, update the XML port and start the bridge with the matching
`--osc-port` value. For a different computer, replace `127.0.0.1` with the
bridge computer’s reachable local-network IP address and permit that UDP port
through its firewall.


## Three Ways to Get EmotiBit Data Into Tiger Cloud

Oscilloscope and OSC (the steps above) is the simplest live route, but it is
not the only one. Pick the row that matches your situation.

| Route | When to use it | Live? | Guide |
|---|---|---|---|
| **A. Oscilloscope -> OSC -> bridge** | You have a laptop next to the person and want to watch values arrive | Yes | This README, then [`bridge/README.md`](../bridge/README.md) |
| **B. microSD card -> DataParser -> importer** | The EmotiBit recorded on its own (a walk, a night's sleep) with no computer nearby | No, after the fact | [`examples/import_emotibit_csv.py`](../examples/import_emotibit_csv.py) |
| **C. BrainFlow -> OSC -> bridge** | You write code and would rather skip the Oscilloscope app entirely | Yes | [`examples/emotibit_brainflow.py`](../examples/emotibit_brainflow.py) |

All three routes end in the same `biometric_sample` table, so the plotting
script and every SQL query work the same regardless of how the data arrived.

### Route B in detail: recording to the microSD card

1. Put a formatted microSD card in the EmotiBit and start recording by pressing
   the **Record** button in Oscilloscope, or let it record automatically if
   you configured that in the official docs. Recording to the card needs no
   Wi-Fi once it has started.
2. After the session, copy the raw `.csv` file from the card to your computer.
3. Run the official **EmotiBit DataParser** on that file. It writes one CSV
   per channel next to the raw file. The EDA file ends in `_EA.csv`. Follow
   [Working with EmotiBit data](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/Working_with_emotibit_data.md).
4. Preview, then import:

   ```bash
   uv run python examples/import_emotibit_csv.py path/to/recording_EA.csv
   uv run python examples/import_emotibit_csv.py path/to/recording_EA.csv --session walk-01 --write
   ```

Why the time sync matters: `LocalTimestamp` in the parsed file is real clock
time only if Oscilloscope was connected at least twice during the recording.
Without any sync it is zero, and the importer skips those rows and tells you.

### Route C in detail: BrainFlow instead of Oscilloscope

[BrainFlow](https://brainflow.org/) connects to the EmotiBit over Wi-Fi from
Python and exposes EDA in its "ancillary" data preset. The example script
reads that preset and re-sends every value as `/emotibit/eda`, so the bridge
does not know the difference. See [`examples/README.md`](../examples/README.md)
for the command. Close Oscilloscope first, because the EmotiBit talks to one
host at a time.

## Helpful OpenBCI and Related Libraries

EmotiBit is sold and documented alongside OpenBCI's hardware, and much of the
OpenBCI software ecosystem works with it. Here is what each piece is for, in
plain terms, and whether it is useful for this project.

| Library or tool | What it is | Useful here? |
|---|---|---|
| [BrainFlow](https://brainflow.readthedocs.io/en/stable/SupportedBoards.html#emotibit) | OpenBCI's officially recommended library for reading data from biosensor boards in Python, C++, Java, R, Julia, and more. It has native EmotiBit support (`BoardIds.EMOTIBIT_BOARD`). | **Yes.** Route C above. Also the right starting point if you ever add an OpenBCI EEG board. |
| [BrainFlow Streamer](https://docs.openbci.com/ForDevelopers/SoftwareDevelopment/) | A BrainFlow feature that forwards board data to a file or a network socket while another program reads it. | Handy for recording a raw copy while the bridge runs. |
| [OpenBCI GUI](https://docs.openbci.com/Software/OpenBCISoftware/GUIDocs/) | OpenBCI's desktop app for EEG boards (Cyton, Ganglion). Built on BrainFlow since version 5. | Only if you also own an OpenBCI EEG board; it is not EmotiBit's viewer. For EmotiBit, Oscilloscope is the equivalent app. |
| [pyOpenBCI](https://docs.openbci.com/Deprecated/Python/) and OpenBCI_Python | Older Python libraries for OpenBCI boards. | **No.** OpenBCI marks both as deprecated and points to BrainFlow. Listed so you recognise them in old tutorials. |
| [Lab Streaming Layer (LSL)](https://labstreaminglayer.readthedocs.io/) with [pylsl](https://pypi.org/project/pylsl/) | A standard for streaming and time-aligning data from many devices at once. OpenBCI GUI can publish LSL, and EmotiBit Oscilloscope gained LSL output in ofxEmotiBit v1.11.1. | Yes, if you want EmotiBit and an EEG headset on one clock. A future `bridge.py` could listen to LSL instead of OSC. |
| [EmotiBit DataParser](https://github.com/EmotiBit/EmotiBit_Docs/blob/master/Working_with_emotibit_data.md) | EmotiBit's official tool for turning microSD recordings into per-channel CSVs. | **Yes.** Route B above. |
| [python-osc](https://pypi.org/project/python-osc/) | The OSC library the bridge already uses. | Already installed. |
| [MNE-Python](https://mne.tools/) | Neurophysiology analysis toolkit. Already used by the AWEAR analyzer. | Yes for EEG; EDA analysis is usually simpler. |
| [NeuroKit2](https://neuropsychology.github.io/NeuroKit/) | A friendly Python toolkit for physiological signals, including EDA decomposition into tonic and phasic parts. Not an OpenBCI project. | A good next step once EDA is in the database and you want more than a moving average. |

If you only install one extra thing, make it BrainFlow:

```bash
uv run --with brainflow python -c "from brainflow.board_shim import BoardIds; print(BoardIds.EMOTIBIT_BOARD)"
```

That prints the EmotiBit board number and proves the install worked without
touching any hardware.

## Troubleshooting

- **Sample count remains zero:** confirm the device is connected, OSC is enabled,
  and the XML was copied into Oscilloscope’s active resource directory.
- **Port mismatch:** the XML and `bridge.py --osc-port` must use the same number.
- **EDA stays flat:** inspect the original EDA graph in Oscilloscope, improve
  electrode contact, and reduce movement.
- **Oscilloscope stops sending previous channels:** restore your backup. This
  project’s XML intentionally routes only `EA`.
- **The bridge reports “address already in use”:** another program owns the port.
  Stop that program or select a different port on both sides.

## Next Steps

- Never used this before? Run the whole pipeline with fake data first:
  [`examples/TUTORIAL.md`](../examples/TUTORIAL.md).
- To save readings, create the database objects with
  [the SQL guide](../sql/README.md).
- To understand simulation, scoring, live collection, and database options, read
  [the bridge guide](../bridge/README.md).
- To return to the project overview, read [the root README](../README.md).
