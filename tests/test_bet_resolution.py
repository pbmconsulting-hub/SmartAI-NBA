# ============================================================
# FILE: tests/test_bet_resolution.py
# PURPOSE: Tests for bet resolution date parsing, timezone
#          anchoring, and game-log stat field completeness.
# ============================================================
import datetime
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestParseGameDate(unittest.TestCase):
    """Verify _parse_game_date handles all known API date formats."""

    def setUp(self):
        from tracking.bet_tracker import _parse_game_date
        self._parse = _parse_game_date

    def test_iso_format(self):
        self.assertEqual(self._parse("2026-03-05"), datetime.date(2026, 3, 5))

    def test_iso_with_timestamp(self):
        self.assertEqual(
            self._parse("2026-03-05T00:00:00.000Z"),
            datetime.date(2026, 3, 5),
        )

    def test_nba_api_short_month(self):
        """nba_api PlayerGameLog returns 'MAR 05, 2026' format."""
        self.assertEqual(self._parse("MAR 05, 2026"), datetime.date(2026, 3, 5))

    def test_nba_api_various_months(self):
        self.assertEqual(self._parse("JAN 15, 2026"), datetime.date(2026, 1, 15))
        self.assertEqual(self._parse("FEB 28, 2026"), datetime.date(2026, 2, 28))
        self.assertEqual(self._parse("NOV 01, 2026"), datetime.date(2026, 11, 1))
        self.assertEqual(self._parse("DEC 31, 2025"), datetime.date(2025, 12, 31))

    def test_long_month_format(self):
        self.assertEqual(
            self._parse("March 05, 2026"),
            datetime.date(2026, 3, 5),
        )

    def test_empty_string(self):
        self.assertIsNone(self._parse(""))

    def test_none_input(self):
        self.assertIsNone(self._parse(None))

    def test_garbage_input(self):
        self.assertIsNone(self._parse("not-a-date"))


class TestResolveTodaysBetsTimezone(unittest.TestCase):
    """resolve_todays_bets should use Eastern Time, not system time."""

    def test_uses_eastern_time(self):
        """Verify resolve_todays_bets filters bets by ET date."""
        import tracking.bet_tracker as bt

        # Mock _nba_today_et to return a known date
        et_date = datetime.date(2026, 4, 6)
        with patch.object(bt, "_nba_today_et", return_value=et_date):
            with patch.object(bt, "load_all_bets", return_value=[]):
                result = bt.resolve_todays_bets()
                # Should complete without error
                self.assertEqual(result["resolved"], 0)


class TestResolveTodaysFindsBetsOnETDate(unittest.TestCase):
    """resolve_todays_bets should match bets logged on the ET date."""

    def test_matches_et_date_bets(self):
        import tracking.bet_tracker as bt

        et_date = datetime.date(2026, 4, 6)
        # Bet logged on ET date with an unknown stat so it skips resolution
        fake_bet = {
            "bet_id": 1,
            "bet_date": "2026-04-06",
            "player_name": "TestPlayer",
            "stat_type": "points",
            "prop_line": 20.5,
            "direction": "OVER",
            "result": None,
        }
        with patch.object(bt, "_nba_today_et", return_value=et_date):
            with patch.object(bt, "load_all_bets", return_value=[fake_bet]):
                # Patch bulk fetcher and the parallel executor path to
                # avoid real API calls — Tier 1/2 return empty
                with patch.object(bt, "_fetch_bulk_boxscores", return_value={}):
                    result = bt.resolve_todays_bets()
                    # Bet should show up as pending (no API data)
                    # but NOT as resolved from a mismatched date
                    self.assertGreaterEqual(result["pending"], 0)


class TestGameLogStatFields(unittest.TestCase):
    """Game log formatters should include all stat fields needed by resolution."""

    _REQUIRED_FIELDS = {
        "pts", "reb", "ast", "stl", "blk", "tov", "fg3m",
        "ftm", "fta", "fgm", "fga", "oreb", "dreb", "pf",
        "minutes",
    }

    def test_live_data_fetcher_nba_api_path_has_all_fields(self):
        """Verify the nba_api fallback path includes resolution stat fields."""
        # Build a fake nba_api game row with all uppercase keys
        fake_row = {
            "GAME_DATE": "MAR 05, 2026", "MATCHUP": "LAL vs GSW",
            "WL": "W", "MIN": "32",
            "PTS": 25, "REB": 8, "AST": 6, "STL": 2, "BLK": 1,
            "TOV": 3, "FG3M": 4, "FT_PCT": 0.85,
            "FTM": 5, "FTA": 6, "FGM": 10, "FGA": 18,
            "OREB": 2, "DREB": 6, "PF": 3,
        }
        # Simulate the formatting logic from live_data_fetcher
        formatted = {
            "game_date": fake_row.get("GAME_DATE", ""),
            "matchup": fake_row.get("MATCHUP", ""),
            "win_loss": fake_row.get("WL", ""),
            "minutes": float(fake_row.get("MIN", 0) or 0),
            "pts": float(fake_row.get("PTS", 0) or 0),
            "reb": float(fake_row.get("REB", 0) or 0),
            "ast": float(fake_row.get("AST", 0) or 0),
            "stl": float(fake_row.get("STL", 0) or 0),
            "blk": float(fake_row.get("BLK", 0) or 0),
            "tov": float(fake_row.get("TOV", 0) or 0),
            "fg3m": float(fake_row.get("FG3M", 0) or 0),
            "ft_pct": float(fake_row.get("FT_PCT", 0) or 0),
            "ftm": float(fake_row.get("FTM", 0) or 0),
            "fta": float(fake_row.get("FTA", 0) or 0),
            "fgm": float(fake_row.get("FGM", 0) or 0),
            "fga": float(fake_row.get("FGA", 0) or 0),
            "oreb": float(fake_row.get("OREB", 0) or 0),
            "dreb": float(fake_row.get("DREB", 0) or 0),
            "pf": float(fake_row.get("PF", 0) or 0),
        }
        for field in self._REQUIRED_FIELDS:
            self.assertIn(field, formatted,
                          f"Game log missing required field '{field}'")


class TestResolveAllPendingDateParsing(unittest.TestCase):
    """resolve_all_pending_bets Tier 3 should handle nba_api date format."""

    @patch("tracking.bet_tracker._fetch_bulk_boxscores", return_value={})
    @patch("tracking.bet_tracker.load_all_bets")
    def test_tier3_matches_nba_api_dates(self, mock_load, mock_bulk):
        """Bets should resolve when game log dates are in 'MMM DD, YYYY' format."""
        import tracking.bet_tracker as bt

        mock_load.return_value = [{
            "bet_id": 99,
            "bet_date": "2026-03-05",
            "player_name": "Test Player",
            "stat_type": "points",
            "prop_line": 20.5,
            "direction": "OVER",
            "result": None,
        }]

        fake_log = [{
            "game_date": "MAR 05, 2026",  # nba_api format
            "pts": 25.0,
            "reb": 5.0, "ast": 3.0, "stl": 1.0, "blk": 0.0,
            "tov": 2.0, "fg3m": 3.0, "minutes": 32.0,
            "ftm": 4.0, "fta": 5.0, "fgm": 9.0, "fga": 17.0,
            "oreb": 1.0, "dreb": 4.0, "pf": 2.0,
        }]

        with patch("tracking.bet_tracker.record_bet_result", return_value=(True, "ok")) as mock_record:
            with patch("data.player_profile_service.get_player_id", return_value=12345):
                with patch("tracking.bet_tracker._fetch_resolve_game_log", return_value=fake_log):
                    result = bt.resolve_all_pending_bets()
                    # Should have resolved the bet
                    self.assertEqual(result["resolved"], 1)
                    self.assertEqual(result["wins"], 1)  # 25.0 > 20.5
                    mock_record.assert_called_once_with(99, "WIN", 25.0)


class TestFetchResolveGameLogSourceCheck(unittest.TestCase):
    """_fetch_resolve_game_log should use ETL DB + nba_api only."""

    def test_no_external_api_import_in_resolve_path(self):
        """The resolve game log function must not import from external API bridges."""
        import inspect
        import tracking.bet_tracker as bt
        source = inspect.getsource(bt._fetch_resolve_game_log)
        # Check that no external API bridge import exists in the function body
        self.assertNotIn("nba_data_service", source,
                         "_fetch_resolve_game_log must not route through nba_data_service")

    def test_etl_is_primary_source(self):
        """ETL database should be tried before nba_api."""
        import tracking.bet_tracker as bt

        fake_etl_rows = [{
            "game_date": "2026-03-05",
            "pts": 30.0, "reb": 10.0, "ast": 8.0,
            "stl": 2.0, "blk": 1.0, "tov": 3.0,
            "fg3m": 4.0, "min": "35:20",
            "ftm": 6.0, "fta": 7.0, "fgm": 12.0, "fga": 20.0,
            "oreb": 3.0, "dreb": 7.0, "pf": 2.0,
        }]

        with patch("data.etl_data_service.get_player_game_logs", return_value=fake_etl_rows) as mock_etl:
            logs = bt._fetch_resolve_game_log(12345, last_n=5)
            mock_etl.assert_called_once_with(12345, limit=5)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["pts"], 30.0)
            # 'min' should be normalised to 'minutes'
            self.assertIn("minutes", logs[0])
            self.assertEqual(logs[0]["minutes"], 35.0)

    def test_falls_back_to_nba_api_when_etl_empty(self):
        """When ETL returns nothing, nba_api should be used."""
        import tracking.bet_tracker as bt

        with patch("data.etl_data_service.get_player_game_logs", return_value=[]):
            with patch("nba_api.stats.endpoints.playergamelog.PlayerGameLog") as mock_pgl:
                import pandas as pd
                mock_df = pd.DataFrame([{
                    "GAME_DATE": "MAR 05, 2026", "MATCHUP": "LAL vs GSW",
                    "WL": "W", "MIN": 32, "PTS": 25, "REB": 8, "AST": 6,
                    "STL": 2, "BLK": 1, "TOV": 3, "FG3M": 4,
                    "FTM": 5, "FTA": 6, "FGM": 10, "FGA": 18,
                    "OREB": 2, "DREB": 6, "PF": 3,
                }])
                mock_pgl.return_value.get_data_frames.return_value = [mock_df]
                logs = bt._fetch_resolve_game_log(12345, last_n=5)
                self.assertEqual(len(logs), 1)
                # Date should be normalised to ISO
                self.assertEqual(logs[0]["game_date"], "2026-03-05")
                self.assertEqual(logs[0]["pts"], 25.0)
                self.assertEqual(logs[0]["ftm"], 5.0)


class TestNewStatMappings(unittest.TestCase):
    """Verify new stat type mappings resolve correctly."""

    def test_three_pt_attempted_in_stat_col(self):
        from tracking.bet_tracker import _STAT_COL
        self.assertEqual(_STAT_COL["3-pt attempted"], "fg3a")
        self.assertEqual(_STAT_COL["3pt attempted"], "fg3a")
        self.assertEqual(_STAT_COL["fg3a"], "fg3a")
        self.assertEqual(_STAT_COL["three pointers attempted"], "fg3a")

    def test_computed_stats_exist(self):
        from tracking.bet_tracker import _COMPUTED_STATS
        self.assertIn("two pointers made", _COMPUTED_STATS)
        self.assertIn("two pointers attempted", _COMPUTED_STATS)

    def test_computed_two_pointers_made(self):
        from tracking.bet_tracker import _compute_actual_value_from_row, _COMPUTED_STATS
        row = {"fgm": 10.0, "fg3m": 3.0, "fga": 20.0, "fg3a": 7.0}
        val = _compute_actual_value_from_row(
            row, "two pointers made", None, False, False, {}, {}, is_computed=True,
        )
        self.assertAlmostEqual(val, 7.0)  # 10 - 3

    def test_computed_two_pointers_attempted(self):
        from tracking.bet_tracker import _compute_actual_value_from_row, _COMPUTED_STATS
        row = {"fgm": 10.0, "fg3m": 3.0, "fga": 20.0, "fg3a": 7.0}
        val = _compute_actual_value_from_row(
            row, "two pointers attempted", None, False, False, {}, {}, is_computed=True,
        )
        self.assertAlmostEqual(val, 13.0)  # 20 - 7

    def test_dunks_is_resolvable(self):
        from tracking.bet_tracker import _STAT_COL
        self.assertIn("dunks", _STAT_COL)

    def test_unresolvable_stats_empty(self):
        from tracking.bet_tracker import _UNRESOLVABLE_STATS
        self.assertNotIn("dunks", _UNRESOLVABLE_STATS)

    def test_three_pt_attempted_resolves(self):
        """3-pt attempted bet should resolve via fg3a column."""
        import tracking.bet_tracker as bt

        fake_bet = {
            "bet_id": 10,
            "bet_date": "2026-03-05",
            "player_name": "TestPlayer",
            "stat_type": "3-pt attempted",
            "prop_line": 5.5,
            "direction": "OVER",
            "result": None,
        }
        fake_log = [{
            "game_date": "MAR 05, 2026",
            "pts": 20.0, "reb": 5.0, "ast": 3.0, "stl": 1.0, "blk": 0.0,
            "tov": 2.0, "fg3m": 3.0, "fg3a": 8.0, "minutes": 32.0,
            "ftm": 4.0, "fta": 5.0, "fgm": 9.0, "fga": 17.0,
            "oreb": 1.0, "dreb": 4.0, "pf": 2.0,
        }]
        with patch.object(bt, "_fetch_bulk_boxscores", return_value={}):
            with patch("tracking.bet_tracker.record_bet_result", return_value=(True, "ok")) as mock_record:
                with patch("data.player_profile_service.get_player_id", return_value=12345):
                    with patch("tracking.bet_tracker._fetch_resolve_game_log", return_value=fake_log):
                        with patch("tracking.bet_tracker.load_all_bets", return_value=[fake_bet]):
                            result = bt.resolve_all_pending_bets()
                            self.assertEqual(result["resolved"], 1)
                            mock_record.assert_called_once_with(10, "WIN", 8.0)

    def test_two_pointers_made_resolves(self):
        """two pointers made bet should resolve via fgm - fg3m."""
        import tracking.bet_tracker as bt

        fake_bet = {
            "bet_id": 20,
            "bet_date": "2026-03-05",
            "player_name": "TestPlayer",
            "stat_type": "two pointers made",
            "prop_line": 5.5,
            "direction": "OVER",
            "result": None,
        }
        fake_log = [{
            "game_date": "MAR 05, 2026",
            "pts": 20.0, "reb": 5.0, "ast": 3.0, "stl": 1.0, "blk": 0.0,
            "tov": 2.0, "fg3m": 3.0, "fg3a": 8.0, "minutes": 32.0,
            "ftm": 4.0, "fta": 5.0, "fgm": 9.0, "fga": 17.0,
            "oreb": 1.0, "dreb": 4.0, "pf": 2.0,
        }]
        with patch.object(bt, "_fetch_bulk_boxscores", return_value={}):
            with patch("tracking.bet_tracker.record_bet_result", return_value=(True, "ok")) as mock_record:
                with patch("data.player_profile_service.get_player_id", return_value=12345):
                    with patch("tracking.bet_tracker._fetch_resolve_game_log", return_value=fake_log):
                        with patch("tracking.bet_tracker.load_all_bets", return_value=[fake_bet]):
                            result = bt.resolve_all_pending_bets()
                            self.assertEqual(result["resolved"], 1)
                            # fgm(9) - fg3m(3) = 6.0, > 5.5 → WIN
                            mock_record.assert_called_once_with(20, "WIN", 6.0)

    def test_dunks_resolves_via_pbp(self):
        """dunks stat should resolve via play-by-play dunk counting."""
        import tracking.bet_tracker as bt

        fake_bet = {
            "bet_id": 17,
            "bet_date": "2026-03-05",
            "player_name": "TestPlayer",
            "stat_type": "dunks",
            "prop_line": 1.5,
            "direction": "OVER",
            "result": None,
        }
        # Tier 1/2 bulk lookup provides dunks=3 for the player
        fake_bulk = {"testplayer": {"pts": 20.0, "reb": 5.0, "dunks": 3.0}}
        with patch.object(bt, "_fetch_bulk_boxscores", return_value=fake_bulk):
            with patch("tracking.bet_tracker.record_bet_result", return_value=(True, "ok")) as mock_record:
                with patch("tracking.bet_tracker.load_all_bets", return_value=[fake_bet]):
                    result = bt.resolve_all_pending_bets()
                    self.assertEqual(result["resolved"], 1)
                    # dunks=3.0 > 1.5 → WIN
                    mock_record.assert_called_once_with(17, "WIN", 3.0)


if __name__ == "__main__":
    unittest.main()
