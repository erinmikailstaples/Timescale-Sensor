import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg

from export_to_tiger import main, prepare_records, record_key, upload_records
from setup_schema import SCHEMA_SQL, create_schema, database_url


class ExportToTigerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "export.json"
        self.payload = {"daily_sleep": [{"id": "sample-record", "day": "2026-10-15", "score": 85}]}
        self.path.write_text(json.dumps(self.payload))

    def test_oura_fields_are_preserved(self):
        rows = prepare_records(self.payload, "participant-01")
        self.assertEqual(rows[0][:4], ("participant-01", "daily_sleep", "id:sample-record", date(2026, 10, 15)))
        self.assertEqual(rows[0][5].obj, self.payload["daily_sleep"][0])

    def test_keys_are_stable_when_mutable_metrics_change(self):
        self.assertEqual(record_key("daily_sleep", {"id": "same", "score": 80}),
                         record_key("daily_sleep", {"id": "same", "score": 90}))
        self.assertEqual(record_key("personal_info", {"weight": 70}),
                         record_key("personal_info", {"weight": 71}))
        self.assertEqual(record_key("heartrate", {"timestamp": "2026-10-15T09:00:00Z", "bpm": 60}),
                         record_key("heartrate", {"timestamp": "2026-10-15T11:00:00+02:00", "bpm": 65}))
        self.assertNotEqual(record_key("heartrate", {"timestamp": "2026-10-15T09:00:00Z", "source": "awake"}),
                            record_key("heartrate", {"timestamp": "2026-10-15T09:00:00Z", "source": "sleep"}))

    def test_idless_fallback_is_independent_of_field_order(self):
        self.assertEqual(record_key("ring_configuration", {"size": 8, "color": "silver"}),
                         record_key("ring_configuration", {"color": "silver", "size": 8}))

    def test_personal_information_and_empty_collections(self):
        rows = prepare_records({"personal_info": {"id": "sample-user"}, "sleep": []}, "participant-01")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "profile")
        self.assertEqual(prepare_records({"heartrate": []}, "participant-01"), [])

    def test_invalid_shapes_dates_and_nonfinite_values(self):
        invalid = [[], {}, {"unknown": []}, {"sleep": {}}, {"personal_info": []},
                   {"sleep": [None]}, {"sleep": [{"day": "not-a-date"}]},
                   {"heartrate": [{"timestamp": "2026-10-15T09:00:00"}]},
                   {"sleep": [{"score": float("nan")}]}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises((ValueError, TypeError)):
                prepare_records(payload, "participant-01")

    @patch("export_to_tiger.psycopg.connect")
    @patch("export_to_tiger.database_url")
    def test_dry_run_does_not_load_credentials_or_connect(self, database, connect):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.path), "--participant", "participant-01", "--dry-run"]), 0)
        database.assert_not_called()
        connect.assert_not_called()

    @patch("export_to_tiger.psycopg.connect")
    def test_invalid_file_does_not_connect(self, connect):
        self.path.write_text("not JSON")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.path), "--participant", "participant-01"]), 1)
        connect.assert_not_called()

    @patch("export_to_tiger.upload_records", return_value=1)
    @patch("export_to_tiger.psycopg.connect")
    @patch("export_to_tiger.database_url", return_value="postgresql://localhost/sample?sslmode=require")
    def test_cli_upload_uses_connection_transaction(self, database, connect, upload):
        connection = connect.return_value.__enter__.return_value
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main([str(self.path), "--participant", "participant-01"]), 0)
        upload.assert_called_once()
        self.assertIs(upload.call_args.args[0], connection)
        self.assertEqual(upload.call_args.args[1][0][0], "participant-01")
        connect.return_value.__exit__.assert_called_once_with(None, None, None)
        self.assertIn("inserted or updated 1 rows", stdout.getvalue())

    @patch("export_to_tiger.upload_records", side_effect=psycopg.DataError("private payload"))
    @patch("export_to_tiger.psycopg.connect")
    @patch("export_to_tiger.database_url", return_value="postgresql://localhost/sample?sslmode=require")
    def test_upload_failure_exits_transaction_without_exposing_payload(self, database, connect, upload):
        connect.return_value.__exit__.return_value = False
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(main([str(self.path), "--participant", "participant-01"]), 1)
        self.assertIs(connect.return_value.__exit__.call_args.args[0], psycopg.DataError)
        self.assertIn("rolled back", stderr.getvalue())
        self.assertNotIn("private payload", stderr.getvalue())

    def test_parameterized_upsert_and_idempotent_schema(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        rows = prepare_records(self.payload, "participant-01")
        self.assertEqual(upload_records(connection, rows), 1)
        statement, parameters = cursor.executemany.call_args.args
        self.assertIn("ON CONFLICT", statement)
        self.assertIn("IS DISTINCT FROM", statement)
        self.assertEqual(parameters, rows)
        create_schema(connection)
        cursor.execute.assert_called_once_with(SCHEMA_SQL)
        self.assertIn("CREATE TABLE IF NOT EXISTS", SCHEMA_SQL)
        self.assertIn("oura_sync_run", SCHEMA_SQL)
        self.assertIn("oura_record_version", SCHEMA_SQL)
        self.assertIn("oura_sync_cursor", SCHEMA_SQL)
        self.assertIn("jsonb_path_ops", SCHEMA_SQL)

    @patch("setup_schema.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_credentials_file_is_parsed_without_hardcoded_secrets(self, dotenv):
        credentials = Path(self.directory.name) / "credentials.txt"
        url = "postgresql://sample-user@localhost/sample?sslmode=require"
        credentials.write_text(f"Service name: sample\nService URL: {url}\n")
        self.assertEqual(database_url(credentials), url)
        credentials.write_text("Service URL: postgresql://localhost/sample?sslmode=disable\n")
        with self.assertRaisesRegex(ValueError, "sslmode"):
            database_url(credentials)

    @patch("setup_schema.load_dotenv")
    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/sample?sslmode=require"}, clear=True)
    def test_environment_overrides_credentials_file(self, dotenv):
        self.assertEqual(database_url(Path("missing-file")), "postgresql://localhost/sample?sslmode=require")

    @patch("export_to_tiger.database_url", return_value="postgresql://localhost/sample?sslmode=require")
    @patch("export_to_tiger.psycopg.connect", side_effect=psycopg.OperationalError("private server details"))
    def test_database_errors_do_not_print_connection_details(self, connect, database):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(main([str(self.path), "--participant", "participant-01"]), 1)
        self.assertNotIn("private server details", stderr.getvalue())
        self.assertNotIn("postgresql://", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
