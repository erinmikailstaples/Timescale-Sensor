#!/usr/bin/env python3
"""Summarize single-channel AWEAR EEG with MNE, without clinical interpretation.

Usage: uv run python awear/analyze_eeg.py awear/exports/eeg.csv --units uV
Input may be API CSV, an API JSON response, or the exporter's JSONL.
Confirm waveform units with AWEAR before choosing --units; no units are assumed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import mne
import numpy as np


SFREQ = 256
SCALES = {"V": 1.0, "mV": 1e-3, "uV": 1e-6}
BANDS = {"delta": (0.5, 4), "theta": (4, 8), "alpha": (8, 13),
         "beta": (13, 30), "gamma": (30, 45)}


def load_recording(path: Path, units: str):
    """Require one device/participant and uninterrupted, ordered one-second records."""
    with path.open(encoding="utf-8", newline="") as handle:
        if path.suffix.lower() == ".csv":
            records = list(csv.DictReader(handle))
            for record in records:
                record["waveform"] = [record[f"s{index}"] for index in range(SFREQ)]
        elif path.suffix.lower() == ".jsonl":
            records = [json.loads(line) for line in handle if line.strip()]
        elif path.suffix.lower() == ".json":
            payload = json.load(handle)
            records = payload["data"]
            participant = payload.get("meta", {}).get("participantId")
            for record in records:
                record.setdefault("participant_id", participant)
        else:
            raise ValueError("Input must be .csv, .json, or .jsonl.")
    if len(records) < 4:
        raise ValueError("Provide at least four contiguous one-second EEG records.")
    devices = {record["device_id"] for record in records}
    participants = {record.get("participant_id") for record in records}
    if len(devices) != 1 or len(participants) != 1:
        raise ValueError("Analyze only one participant and one device at a time.")
    timestamps = [datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                  for record in records]
    if any(stamp.tzinfo is None for stamp in timestamps):
        raise ValueError("Every timestamp must include a UTC offset or Z.")
    for previous, current in zip(timestamps, timestamps[1:]):
        if abs((current - previous).total_seconds() - 1.0) > 1 / SFREQ:
            raise ValueError("Records have gaps, overlaps, or are unordered. Export a contiguous window.")
    samples = np.asarray([record["waveform"] for record in records], dtype=float)
    if samples.shape != (len(records), SFREQ) or not np.isfinite(samples).all():
        raise ValueError("Each EEG record must contain exactly 256 finite numeric samples.")
    samples = samples.reshape(1, -1) * SCALES[units]
    info = mne.create_info(["TP10"], sfreq=SFREQ, ch_types="eeg")
    raw = mne.io.RawArray(samples, info, verbose=False)
    metadata = {"device_id": next(iter(devices)),
                "participant_id": next(iter(participants)),
                "first_record_timestamp": records[0]["timestamp"],
                "input_units": units}
    return raw, metadata


def summarize(raw):
    """Estimate unfiltered Welch power in non-overlapping conventional bands."""
    spectrum = raw.compute_psd(
        method="welch", fmin=0.5, fmax=45, n_fft=1024, n_per_seg=1024,
        n_overlap=512, remove_dc=True, verbose=False,
    )
    power, frequencies = spectrum.get_data(return_freqs=True)
    power = power[0]
    selected = (frequencies >= 0.5) & (frequencies < 45)
    total = float(power[selected].sum())
    if not np.isfinite(total) or total <= 0:
        raise ValueError("No measurable 0.5-45 Hz power; check for a flat or invalid signal.")
    percentages = {
        name: float(100 * power[(frequencies >= low) & (frequencies < high)].sum() / total)
        for name, (low, high) in BANDS.items()
    }
    samples_uv = raw.get_data()[0] * 1e6
    report = {
        "channel": "TP10 (RIGHT_TEMP)", "sampling_rate_hz": SFREQ,
        "duration_seconds": raw.n_times / SFREQ,
        "peak_frequency_hz": float(frequencies[selected][np.argmax(power[selected])]),
        "peak_to_peak_uv": float(np.ptp(samples_uv)),
        "standard_deviation_uv": float(np.std(samples_uv)),
        "relative_band_power_percent": percentages,
        "method": "Unfiltered Welch PSD; 4 s Hamming windows, 50% overlap, 0.25 Hz bins.",
        "band_definition_hz": BANDS,
        "limitations": "Descriptive signal features only, not emotion, attention, sleep, or medical assessment. "
                       "Motion, muscle activity, eye movements, and poor contact can dominate this channel. "
                       "No artifact rejection or reference changes applied. Band limits are lower-inclusive, "
                       "upper-exclusive; percentages are relative to 0.5-45 Hz, excluding 45 Hz.",
    }
    return report, frequencies, power


def save_plot(raw, frequencies, power, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 1, figsize=(10, 6), layout="constrained")
    count = min(raw.n_times, 10 * SFREQ)
    axes[0].plot(np.arange(count) / SFREQ, raw.get_data()[0, :count] * 1e6, linewidth=0.7)
    axes[0].set(xlabel="Time (s)", ylabel="Amplitude (uV)", title="TP10: first 10 seconds (unfiltered)")
    axes[1].semilogy(frequencies, np.maximum(power * 1e12, np.finfo(float).tiny))
    axes[1].set(xlabel="Frequency (Hz)", ylabel="PSD (uV^2/Hz)", title="Welch power spectrum")
    figure.savefig(output, dpi=150)
    plt.close(figure)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--units", required=True, choices=SCALES, help="Confirmed API waveform units.")
    parser.add_argument("--plot", type=Path, help="Optional PNG output; no GUI required.")
    args = parser.parse_args(argv)
    try:
        raw, metadata = load_recording(args.input, args.units)
        report, frequencies, power = summarize(raw)
        if args.plot:
            if args.plot.suffix.lower() != ".png":
                raise ValueError("--plot must end in .png.")
            if args.plot.exists():
                raise ValueError("Plot output already exists; choose a new filename.")
            save_plot(raw, frequencies, power, args.plot)
        print(json.dumps({**metadata, **report}, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot analyze EEG: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())