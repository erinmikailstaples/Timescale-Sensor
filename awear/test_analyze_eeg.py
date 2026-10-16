import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from analyze_eeg import load_recording, main, summarize


class AnalyzeEEGTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "eeg.jsonl"
        self.records = []
        start = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)
        for index in range(8):
            times = np.arange(256) / 256 + index
            self.records.append({
                "timestamp": (start + timedelta(seconds=index)).isoformat(),
                "participant_id": "P-A1B2C3", "device_id": "AWR-D001",
                "waveform": (20 * np.sin(2 * np.pi * 10 * times)).tolist(),
            })
        self.write_records()

    def write_records(self):
        self.path.write_text("".join(json.dumps(record) + "\n" for record in self.records))

    def test_ten_hz_signal_peaks_in_alpha(self):
        raw, metadata = load_recording(self.path, "uV")
        report, _, _ = summarize(raw)
        self.assertEqual(report["peak_frequency_hz"], 10.0)
        self.assertGreater(report["relative_band_power_percent"]["alpha"], 99)
        self.assertAlmostEqual(sum(report["relative_band_power_percent"].values()), 100)
        self.assertEqual(report["duration_seconds"], 8)
        self.assertAlmostEqual(report["peak_to_peak_uv"], 40)
        self.assertAlmostEqual(np.max(raw.get_data()), 20e-6)
        self.assertEqual(metadata["device_id"], "AWR-D001")

    def test_csv_and_api_json_match_jsonl(self):
        expected, _ = load_recording(self.path, "uV")
        csv_path = self.path.with_suffix(".csv")
        with csv_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "participant_id", "device_id"]
                            + [f"s{index}" for index in range(256)])
            for record in self.records:
                writer.writerow([record["timestamp"], record["participant_id"], record["device_id"],
                                 *record["waveform"]])
        json_path = self.path.with_suffix(".json")
        json_path.write_text(json.dumps({"data": self.records, "meta": {"participantId": "P-A1B2C3"}}))
        for path in (csv_path, json_path):
            with self.subTest(path=path):
                actual, _ = load_recording(path, "uV")
                np.testing.assert_allclose(actual.get_data(), expected.get_data())

    def test_rejects_gaps_and_mixed_devices(self):
        for field, value in [("timestamp", "2026-10-16T00:00:00Z"),
                             ("device_id", "AWR-D002"), ("participant_id", "P-D4E5F6")]:
            with self.subTest(field=field):
                original = self.records[3][field]
                self.records[3][field] = value
                self.write_records()
                with self.assertRaises(ValueError):
                    load_recording(self.path, "uV")
                self.records[3][field] = original

    def test_rejects_nonfinite_short_and_flat_data(self):
        self.records[0]["waveform"][0] = float("nan")
        self.write_records()
        with self.assertRaisesRegex(ValueError, "finite"):
            load_recording(self.path, "uV")
        for record in self.records:
            record["waveform"] = [0.0] * 256
        self.write_records()
        raw, _ = load_recording(self.path, "uV")
        with self.assertRaisesRegex(ValueError, "flat"):
            summarize(raw)
        self.records = self.records[:2]
        self.write_records()
        with self.assertRaisesRegex(ValueError, "four"):
            load_recording(self.path, "uV")

    def test_cli_writes_report_and_png(self):
        output = self.path.with_suffix(".png")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main([str(self.path), "--units", "uV", "--plot", str(output)]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["peak_frequency_hz"], 10)
        self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()