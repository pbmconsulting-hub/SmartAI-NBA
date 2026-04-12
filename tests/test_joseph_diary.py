"""Tests for tracking/joseph_diary.py — win_rate scale and mood classification."""

import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestDiaryUpdateMoodClassification(unittest.TestCase):
    """Verify diary_update_from_track_record() maps win_rate (0-100) to mood."""

    def setUp(self):
        # Use a temporary diary file so tests don't touch real data
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        self._tmp.write("{}")
        self._tmp.close()
        self._patch = patch(
            "tracking.joseph_diary._DIARY_FILE", self._tmp.name
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def _update(self, win_rate):
        from tracking.joseph_diary import diary_update_from_track_record
        diary_update_from_track_record({"win_rate": win_rate, "wins": 5, "losses": 3})
        with open(self._tmp.name) as fh:
            data = json.load(fh)
        today = datetime.date.today().isoformat()
        return data.get("entries", {}).get(today, {}).get("mood", "")

    def test_hot_mood_above_60(self):
        self.assertEqual(self._update(61.0), "hot")
        self.assertEqual(self._update(80.0), "hot")

    def test_cold_mood_below_40(self):
        self.assertEqual(self._update(39.0), "cold")
        self.assertEqual(self._update(10.0), "cold")

    def test_neutral_mood_between_40_and_60(self):
        self.assertEqual(self._update(50.0), "neutral")
        self.assertEqual(self._update(40.0), "neutral")
        self.assertEqual(self._update(60.0), "neutral")

    def test_boundary_60_is_neutral(self):
        """Exactly 60.0 should be neutral (threshold is >60, not >=60)."""
        self.assertEqual(self._update(60.0), "neutral")

    def test_boundary_40_is_neutral(self):
        """Exactly 40.0 should be neutral (threshold is <40, not <=40)."""
        self.assertEqual(self._update(40.0), "neutral")


class TestDiaryWeekSummaryWinRateScale(unittest.TestCase):
    """Verify diary_get_week_summary() returns win_rate on 0-100 scale."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        )
        self._tmp.write("{}")
        self._tmp.close()
        self._patch = patch(
            "tracking.joseph_diary._DIARY_FILE", self._tmp.name
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def _seed_week(self, wins_per_day, losses_per_day):
        """Seed diary entries for every day this week."""
        from tracking.joseph_diary import diary_log_entry
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        for i in range(7):
            day = (monday + datetime.timedelta(days=i)).isoformat()
            diary_log_entry(date_str=day, entry={
                "wins": wins_per_day, "losses": losses_per_day,
            })

    def test_win_rate_is_percentage_not_decimal(self):
        from tracking.joseph_diary import diary_get_week_summary
        self._seed_week(3, 1)  # 75% win rate
        summary = diary_get_week_summary()
        # win_rate should be on 0-100 scale
        self.assertGreaterEqual(summary["win_rate"], 1.0,
                                "win_rate should be percentage (0-100), not decimal")
        self.assertEqual(summary["win_rate"], 75.0)

    def test_empty_week_returns_zero(self):
        from tracking.joseph_diary import diary_get_week_summary
        summary = diary_get_week_summary()
        self.assertEqual(summary["win_rate"], 0.0)

    def test_all_wins_returns_100(self):
        from tracking.joseph_diary import diary_get_week_summary
        self._seed_week(5, 0)
        summary = diary_get_week_summary()
        self.assertEqual(summary["win_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()
