# Tutorial: Send Live EmotiBit EDA to the Python Bridge

## What You Will Learn

In this tutorial, you will configure EmotiBit Oscilloscope to forward one live
sensor channel—electrodermal activity (EDA)—to the Python bridge in this
repository.

By the end, you will be able to:

- identify the EDA signal in Oscilloscope;
- explain what OSC, an OSC address, and a UDP port are;
- install the supplied routing file safely; and
- prove that live EDA messages reach Python without using a database.

Estimated time: 20–30 minutes after the EmotiBit is already assembled and
connected to Wi-Fi.

## Before You Begin

You need:

- an EmotiBit with compatible Feather board;
- a charged battery, configured microSD card, and two electrodes;
- EmotiBit Oscilloscope installed;
- this repository and its Python environment; and
- the EmotiBit and laptop on compatible networks.

Complete the official EmotiBit hardware and Wi-Fi setup first. This tutorial
does not install firmware or configure the microSD card.

> Safety: whenever EmotiBit touches a person, power it only from its battery.
> Do not wear it while USB or another cable connects it to wall-powered equipment.

## Lesson 1: Understand the Data Route

The finished route will be:

```text
EmotiBit EA channel
        |
        v
EmotiBit Oscilloscope
        |
        | OSC message named /emotibit/eda
        | UDP port 12345
        v
bridge/bridge.py
```

OSC is a message format for sending live numeric values between programs. The
OSC address `/emotibit/eda` is the message’s name. UDP port `12345` is the
numbered network destination where the Python bridge listens.

Checkpoint: you should be able to state that the OSC address and port must match
on both the Oscilloscope and Python sides.

## Lesson 2: Confirm the Raw EDA Signal

1. Power EmotiBit from its battery.
2. Open EmotiBit Oscilloscope.
3. Connect Oscilloscope to the EmotiBit.
4. Attach the EDA electrodes according to the official device instructions.
5. Locate the EDA graph in Oscilloscope.
6. Remain still and confirm that the graph is receiving values.

Why this comes first: it tests the sensor, electrode contact, Wi-Fi, and
Oscilloscope before custom routing is introduced.

Success checkpoint: a live EDA trace is visible. If it is missing or flat, stop
here and correct the device connection or electrode contact.

## Lesson 3: Back Up the Existing OSC Configuration

1. Close EmotiBit Oscilloscope.
2. Find Oscilloscope’s active `oscOutputSettings.xml`:
   - macOS: right-click the application, choose **Show Package Contents**, and
     look in `Contents/Resources/`;
   - Windows: look in the application’s `data` directory;
   - Linux: look in `EmotiBit Oscilloscope/bin/data/`.
3. Copy the original file to a clearly named backup such as
   `oscOutputSettings-before-timescale-sensor.xml`.

Why this matters: the original file may contain routes used by another project.
The backup makes the change reversible.

Checkpoint: verify that both the original and backup files exist before
continuing.

## Lesson 4: Install the Project Route

Copy [`oscOutputSettings.xml`](oscOutputSettings.xml) from this folder over
Oscilloscope’s active file, then reopen Oscilloscope.

Open the project file in a text editor and locate:

```xml
<ipAddress>127.0.0.1</ipAddress>
<port>12345</port>
```

Also locate the route:

```xml
<patch><input>EA</input><output>/emotibit/eda</output></patch>
```

These lines mean:

- send to `127.0.0.1`, which is the same computer;
- use UDP port `12345`; and
- rename the EmotiBit `EA` channel to `/emotibit/eda`.

Do not edit these values for the first tutorial.

## Lesson 5: Enable OSC Transmission

1. Reconnect Oscilloscope to EmotiBit.
2. Open Oscilloscope’s **Output List**.
3. Enable **OSC**.

Installing the XML defines the route, while enabling OSC starts transmission.
UDP does not show a connected/not-connected indicator, so you will verify it
with Python next.

## Lesson 6: Listen Without Saving Data

Open a terminal at the repository root and run:

```bash
uv run python bridge/bridge.py --no-db
```

`--no-db` prevents all Tiger Cloud connections and writes. This exercise tests
only EmotiBit, Oscilloscope, OSC, and the Python receiver.

Expected startup output includes:

```text
listening for OSC on 0.0.0.0:12345
```

Success checkpoint:

- the sample count increases continuously;
- the displayed EDA value is not permanently zero; and
- pressing `Ctrl-C` prints a final nonzero sample count.

## Troubleshooting Exercise

If the sample count stays at zero, check the route from left to right:

1. Is the EDA graph live in Oscilloscope?
2. Is OSC enabled in the Output List?
3. Is the supplied XML in Oscilloscope’s active directory?
4. Does the XML use port `12345`?
5. Is the bridge listening on port `12345`?
6. Is a firewall or another application blocking that UDP port?

Change only one item at a time, rerun the listener, and record which change
resolved the problem.

## What You Accomplished

You built and verified the live path from the physical EDA channel to Python.
No database was used, so no readings were permanently stored.

Next:

1. complete the [SQL tutorial](../sql/TUTORIAL.md) to prepare Tiger Cloud; then
2. complete the [bridge tutorial](../bridge/TUTORIAL.md) to store simulated and
   real readings.

For reference material and additional troubleshooting, read
[`README.md`](README.md).

