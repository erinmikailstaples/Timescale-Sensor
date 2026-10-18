import unittest
from datetime import date
from unittest.mock import MagicMock

from sync_to_tiger import date_windows, payload_hash, sync_rows


class SyncToTigerTests(unittest.TestCase):
    def test_date_windows_cover_range_without_gaps(self):
        windows = list(date_windows(date(2026, 1, 1), date(2026, 7, 1)))
        self.assertEqual(windows[0][0], date(2026, 1, 1))
        self.assertEqual(windows[-1][1], date(2026, 7, 1))
        for previous, current in zip(windows, windows[1:]):
            self.assertEqual(previous[1].toordinal() + 1, current[0].toordinal())

    def test_custom_time_series_windows_are_shorter(self):
        windows = list(date_windows(date(2026, 1, 1), date(2026, 3, 1), 30))
        self.assertEqual(windows[0], (date(2026, 1, 1), date(2026, 1, 30)))
        self.assertEqual(windows[-1][1], date(2026, 3, 1))

    def test_window_size_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            list(date_windows(date(2026, 1, 1), date(2026, 1, 2), 0))

    def test_payload_hash_is_canonical(self):
        self.assertEqual(payload_hash({"score": 80, "day": "2026-01-01"}),
                         payload_hash({"day": "2026-01-01", "score": 80}))
        self.assertNotEqual(payload_hash({"score": 80}), payload_hash({"score": 81}))

    def test_sync_writes_version_and_current_record(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        from psycopg.types.json import Jsonb
        rows = [("person", "daily_sleep", "id:one", date(2026, 1, 1), None,
                 Jsonb({"id": "one", "score": 80}))]
        self.assertEqual(sync_rows(connection, rows, 7), 1)
        self.assertEqual(cursor.executemany.call_count, 2)
        version_parameters = cursor.executemany.call_args_list[0].args[1]
        current_parameters = cursor.executemany.call_args_list[1].args[1]
        self.assertEqual(version_parameters[0][0:3], ("person", "daily_sleep", "id:one"))
        self.assertEqual(current_parameters[0][-1], 7)


if __name__ == "__main__":
    unittest.main()
