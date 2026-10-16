import argparse
import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from fetch_data import export_data, get_json, main


def page(has_more=False, records=None):
    return {"data": records if records is not None else [{
        "timestamp": "2026-10-15T09:00:00Z", "device_id": "AWR-D001", "waveform": [0.125] * 256,
    }], "pagination": {"hasMore": has_more}}


class FetchDataTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.args = argparse.Namespace(
            participant="P-A1B2C3", start="2026-10-15T09:00:00Z", end="2026-10-15T09:01:00Z",
            page_size=1, format="csv", output=Path(self.directory.name) / "eeg.csv",
        )
        self.session = Mock()

    @patch("fetch_data.time.sleep")
    def test_csv_export_fetches_all_pages(self, sleep):
        with patch("fetch_data.get_json", side_effect=[page(True), page()]) as get:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                export_data(self.session, self.args)
        with self.args.output.open(newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]), 259)
        self.assertEqual(rows[0][-1], "s255")
        self.assertEqual(rows[1][1:3], ["P-A1B2C3", "AWR-D001"])
        self.assertEqual([call.args[2]["offset"] for call in get.call_args_list], [0, 1])
        sleep.assert_called_once_with(1.1)

    def test_jsonl_preserves_waveform(self):
        self.args.format = "jsonl"
        with patch("fetch_data.get_json", return_value=page()):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                export_data(self.session, self.args)
        record = json.loads(self.args.output.read_text())
        self.assertEqual(record["waveform"], [0.125] * 256)
        self.assertEqual(record["participant_id"], "P-A1B2C3")

    @patch("fetch_data.time.sleep")
    def test_failed_page_removes_partial_export(self, sleep):
        with patch("fetch_data.get_json", side_effect=[page(True), ValueError("QUOTA_EXCEEDED")]):
            with redirect_stderr(io.StringIO()), self.assertRaises(ValueError):
                export_data(self.session, self.args)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_existing_output_is_unchanged(self):
        self.args.output.write_text("existing")
        with self.assertRaisesRegex(ValueError, "already exists"):
            export_data(self.session, self.args)
        self.assertEqual(self.args.output.read_text(), "existing")
        self.session.get.assert_not_called()

    def test_empty_page_with_more_data_is_rejected(self):
        with patch("fetch_data.get_json", return_value=page(True, [])):
            with redirect_stderr(io.StringIO()), self.assertRaisesRegex(ValueError, "Empty page"):
                export_data(self.session, self.args)
        self.assertFalse(self.args.output.exists())

    def test_api_errors_are_not_retried(self):
        for status_code, code in [(402, "NO_PLAN"), (403, "DUA_REQUIRED"), (429, "QUOTA_EXCEEDED")]:
            with self.subTest(code=code):
                response = Mock(status_code=status_code, headers={"Retry-After": "60"})
                response.json.return_value = {"error": {"code": code}}
                self.session.get.reset_mock()
                self.session.get.return_value = response
                with self.assertRaisesRegex(ValueError, code):
                    get_json(self.session, "/members")
                self.session.get.assert_called_once()

    def test_members_uses_bearer_auth_and_timeout(self):
        response = Mock(status_code=200)
        response.json.return_value = {"members": [], "count": 0}
        with patch.dict("os.environ", {"AWEAR_API_KEY": "awr_sk_test_not_real"}):
            with patch("fetch_data.requests.Session") as factory:
                session = factory.return_value.__enter__.return_value
                session.get.return_value = response
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["members"]), 0)
                session.headers.update.assert_called_once_with({
                    "Authorization": "Bearer awr_sk_test_not_real", "Accept": "application/json",
                })
                self.assertEqual(session.get.call_args.kwargs["timeout"], (10, 60))
                self.assertFalse(session.get.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()