"""Offline API contract checks: uv run python -m unittest discover -s oura -v."""

import unittest
from datetime import date
from unittest.mock import Mock

from read_oura import API_URL, ENDPOINTS, fetch_data, query_params


class ReadOuraTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2026, 10, 1)
        self.end = date(2026, 10, 2)
        self.session = Mock()

    def response(self, payload, code=200, headers=None):
        return Mock(status_code=code, headers=headers or {}, json=Mock(return_value=payload))

    def test_date_filters_for_daily_collections(self):
        for endpoint in set(ENDPOINTS) - {
            "personal_info", "ring_configuration", "heartrate", "ring_battery_level"
        }:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(query_params(endpoint, self.start, self.end), {
                    "start_date": "2026-10-01", "end_date": "2026-10-02",
                })

    def test_time_series_use_utc_timestamps_including_end_day(self):
        for endpoint in ("heartrate", "ring_battery_level"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(query_params(endpoint, self.start, self.end), {
                    "start_datetime": "2026-10-01T00:00:00+00:00",
                    "end_datetime": "2026-10-02T23:59:59.999999+00:00",
                })

    def test_pagination_preserves_filters(self):
        self.session.get.side_effect = [
            self.response({"data": [{"score": 85}], "next_token": "page-2"}),
            self.response({"data": [{"score": 90}], "next_token": None}),
        ]
        result = fetch_data(self.session, "daily_sleep", self.start, self.end)
        self.assertEqual(result, [{"score": 85}, {"score": 90}])
        self.session.get.assert_called_with(f"{API_URL}/daily_sleep", params={
            "start_date": "2026-10-01", "end_date": "2026-10-02", "next_token": "page-2",
        }, timeout=30)
        self.assertNotIn("next_token", self.session.get.call_args_list[0].kwargs["params"])

    def test_personal_info_is_an_object_without_filters(self):
        self.session.get.return_value = self.response({"id": "sample-user"})
        self.assertEqual(fetch_data(self.session, "personal_info", self.start, self.end),
                         {"id": "sample-user"})
        self.session.get.assert_called_once_with(f"{API_URL}/personal_info", params={}, timeout=30)

    def test_ring_configuration_is_paginated_without_date_filters(self):
        self.session.get.side_effect = [
            self.response({"data": [{"size": 8}], "next_token": "next"}),
            self.response({"data": [], "next_token": None}),
        ]
        self.assertEqual(fetch_data(self.session, "ring_configuration", self.start, self.end),
                         [{"size": 8}])
        self.assertEqual(self.session.get.call_args.kwargs["params"], {"next_token": "next"})

    def test_api_errors_have_actionable_messages(self):
        for code, message in ((401, "expired"), (403, "scopes"), (429, "Retry-After: 60")):
            with self.subTest(code=code):
                self.session.get.return_value = self.response({}, code, {"Retry-After": "60"})
                with self.assertRaisesRegex(RuntimeError, message):
                    fetch_data(self.session, "sleep", self.start, self.end)

    def test_repeated_pagination_token_is_rejected(self):
        self.session.get.return_value = self.response({"data": [], "next_token": "same"})
        with self.assertRaisesRegex(ValueError, "repeated"):
            fetch_data(self.session, "sleep", self.start, self.end)
        self.assertEqual(self.session.get.call_count, 2)

    def test_invalid_date_range_is_rejected_before_request(self):
        with self.assertRaisesRegex(ValueError, "Start date"):
            fetch_data(self.session, "sleep", self.end, self.start)
        self.session.get.assert_not_called()

    def test_empty_collection(self):
        self.session.get.return_value = self.response({"data": [], "next_token": None})
        self.assertEqual(fetch_data(self.session, "sleep", self.start, self.end), [])

    def test_malformed_collection_is_rejected(self):
        self.session.get.return_value = self.response({"data": {}})
        with self.assertRaisesRegex(ValueError, "data array"):
            fetch_data(self.session, "sleep", self.start, self.end)


if __name__ == "__main__":
    unittest.main()