import unittest
import pandas as pd

from stryder_core.config import COMMON_TIMEZONES
from stryder_core.file_parsing import get_matched_garmin_row


class TestGetMatchedGarminRow(unittest.TestCase):
    
    def test_diff_greater_than_tol(self):
        stryd_df = self._create_df("ts_local", ["2026-01-01 00:00:00"])
        garmin_df = self._create_df("date", ["2026-01-01 00:01:01"])

        matched_row = get_matched_garmin_row(stryd_df, garmin_df, timezone_str=COMMON_TIMEZONES[0], tolerance_sec=60)
        self.assertIsNone(matched_row)

    def test_diff_equals_tol(self):
        stryd_df = self._create_df("ts_local", ["2026-01-01 00:00:00"])
        garmin_df = self._create_df("date", ["2026-01-01 00:01:00"])

        matched_row = get_matched_garmin_row(stryd_df, garmin_df, timezone_str=COMMON_TIMEZONES[0], tolerance_sec=60)
        self.assertIsNotNone(matched_row)
        self.assertEqual(str(matched_row['date']), "2026-01-01 00:01:00")

    def test_diff_less_than_tol(self):
        stryd_df = self._create_df("ts_local", ["2026-01-01 00:00:01"])
        garmin_df = self._create_df("date", ["2026-01-01 00:01:00"])

        matched_row = get_matched_garmin_row(stryd_df, garmin_df, timezone_str=COMMON_TIMEZONES[0], tolerance_sec=60)
        self.assertIsNotNone(matched_row)
        self.assertEqual(str(matched_row['date']), "2026-01-01 00:01:00")

    def test_multiple_matches_returns_closest_row(self):
        stryd_df = self._create_df("ts_local", ["2026-01-01 00:00:00"])
        garmin_df = self._create_df("date", ["2026-01-01 00:01:00", "2026-01-01 00:00:30"])

        matched_row = get_matched_garmin_row(stryd_df, garmin_df, timezone_str=COMMON_TIMEZONES[0], tolerance_sec=60)
        self.assertIsNotNone(matched_row)
        self.assertEqual(str(matched_row['date']), "2026-01-01 00:00:30")

    def _create_df(self, col_name, values):
        return pd.DataFrame({col_name: values})