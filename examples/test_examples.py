"""Offline tests for the example scripts. No network, no database, no hardware."""

from __future__ import annotations

import math
import tempfile
import unittest
from datetime import timezone
from pathlib import Path

import import_emotibit_csv
import send_fake_osc

HEADER = "LocalTimestamp,EmotiBitTimestamp,PacketNumber,DataLength,TypeTag,ProtocolVersion,DataReliability,EA\n"


class FakeEdaTest(unittest.TestCase):
    def test_values_are_finite_and_plausible(self):
        for tenth in range(0, 600):
            value = send_fake_osc.fake_eda(tenth / 10)
            self.assertTrue(math.isfinite(value))
            self.assertGreater(value, 1.0)
            self.assertLess(value, 4.0)


class ImportEmotibitCsvTest(unittest.TestCase):
    def write(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "recording_EA.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_parses_eda_rows_in_utc(self):
        path = self.write(HEADER + "1760745600.5,1000,1,1,EA,1,100,2.25\n"
                                   "1760745600.567,1067,2,1,EA,1,100,2.30\n")
        tag, rows, skipped = import_emotibit_csv.parse_file(path)
        self.assertEqual(tag, "EA")
        self.assertEqual(skipped, 0)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].channel, "eda")
        self.assertEqual(rows[0].unit, "microsiemens")
        self.assertEqual(rows[0].value, 2.25)
        self.assertEqual(rows[0].time.tzinfo, timezone.utc)
        self.assertEqual(rows[0].time.isoformat(), "2025-10-18T00:00:00.500000+00:00")

    def test_skips_rows_without_time_sync_or_bad_values(self):
        path = self.write(HEADER + "0,1000,1,1,EA,1,100,2.25\n"
                                   "1760745600.5,1067,2,1,EA,1,100,oops\n"
                                   "1760745601.5,1134,3,1,EA,1,100,2.40\n")
        _tag, rows, skipped = import_emotibit_csv.parse_file(path)
        self.assertEqual(skipped, 2)
        self.assertEqual([row.value for row in rows], [2.40])

    def test_rejects_unknown_header(self):
        path = self.write("time,value\n1,2\n")
        with self.assertRaisesRegex(ValueError, "LocalTimestamp"):
            import_emotibit_csv.parse_file(path)

    def test_detects_other_channels(self):
        self.assertEqual(import_emotibit_csv.detect_type_tag(HEADER.strip().split(",")[:-1] + ["T1"]), "T1")


if __name__ == "__main__":
    unittest.main()
