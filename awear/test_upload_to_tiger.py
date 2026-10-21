"""Offline tests for upload_to_tiger.py. No database or network is used."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock

import upload_to_tiger


def record(second: int, value: float = 0.125) -> dict:
    return {"timestamp": f"2026-10-15T09:00:{second:02d}Z", "participant_id": "P-A1B2C3",
            "device_id": "AWR-D001", "waveform": [value] * 256}


class LoadRecordsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_reads_jsonl(self):
        path = self.root / "eeg.jsonl"
        path.write_text("\n".join(json.dumps(record(s)) for s in range(3)) + "\n")
        records = upload_to_tiger.load_records(path)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].participant_id, "P-A1B2C3")
        self.assertEqual(len(records[0].waveform), 256)
        self.assertIsNotNone(records[0].time.tzinfo)

    def test_reads_csv_from_fetch_data(self):
        path = self.root / "eeg.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "participant_id", "device_id"] + [f"s{i}" for i in range(256)])
            writer.writerow(["2026-10-15T09:00:00Z", "P-A1B2C3", "AWR-D001", *([0.5] * 256)])
        records = upload_to_tiger.load_records(path)
        self.assertEqual(records[0].waveform[0], 0.5)

    def test_rejects_short_waveform(self):
        path = self.root / "eeg.jsonl"
        bad = record(0)
        bad["waveform"] = [0.1] * 10
        path.write_text(json.dumps(bad) + "\n")
        with self.assertRaisesRegex(ValueError, "256"):
            upload_to_tiger.load_records(path)


class UploadTest(unittest.TestCase):
    def test_insert_is_idempotent_and_counts_new_rows(self):
        self.assertIn("ON CONFLICT", upload_to_tiger.INSERT_SQL)
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        records = [upload_to_tiger.Record(r["timestamp"], "P-A1B2C3", "AWR-D001", r["waveform"])
                   for r in (record(0), record(1))]
        with redirect_stderr(io.StringIO()):
            inserted = upload_to_tiger.upload(connection, records, "uV", "eeg.jsonl")
        self.assertEqual(inserted, 2)
        self.assertEqual(cursor.execute.call_count, 2)
        connection.commit.assert_called()

    def test_preview_does_not_need_database(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "eeg.jsonl"
        path.write_text(json.dumps(record(0)) + "\n")
        out = io.StringIO()
        with redirect_stdout(out):
            code = upload_to_tiger.main([str(path), "--units", "uV"])
        self.assertEqual(code, 0)
        self.assertIn("preview only", out.getvalue())


if __name__ == "__main__":
    unittest.main()
