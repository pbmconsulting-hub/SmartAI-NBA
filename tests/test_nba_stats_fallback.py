"""
tests/test_nba_stats_fallback.py
---------------------------------
Tests for the free NBA stats fallback module (data/nba_stats_backup.py).

Verifies:
  1. Module structure and public API surface
  2. _rows_to_dicts helper correctness
  3. Each fallback function returns correct schema on mock success
  4. Each fallback function returns [] on mock failure
  5. Caching prevents duplicate HTTP calls
  6. ApiNba functions fall back when primary returns empty
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import requests as _requests_lib  # for exception classes in retry tests

# Add repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-mock streamlit before importing application modules
_mock_st = MagicMock()
_mock_st.session_state = {}
_mock_st.cache_data = lambda *a, **kw: (lambda f: f)
_mock_st.secrets = {}
sys.modules.setdefault("streamlit", _mock_st)
sys.modules.setdefault("streamlit.components", MagicMock())
sys.modules.setdefault("streamlit.components.v1", MagicMock())


# ── Section 1: Module structure ──────────────────────────────────────────────

class TestModuleStructure(unittest.TestCase):
    """Verify fallback module exists and exports expected functions."""

    def test_module_importable(self):
        """data.nba_stats_backup must be importable."""
        import data.nba_stats_backup  # noqa: F401

    def test_get_team_stats_backup_exists(self):
        from data.nba_stats_backup import get_team_stats_backup
        self.assertTrue(callable(get_team_stats_backup))

    def test_get_players_backup_exists(self):
        from data.nba_stats_backup import get_players_backup
        self.assertTrue(callable(get_players_backup))

    def test_get_player_stats_backup_exists(self):
        from data.nba_stats_backup import get_player_stats_backup
        self.assertTrue(callable(get_player_stats_backup))

    def test_get_nba_team_stats_backup_exists(self):
        from data.nba_stats_backup import get_nba_team_stats_backup
        self.assertTrue(callable(get_nba_team_stats_backup))

    def test_get_nba_player_stats_backup_exists(self):
        from data.nba_stats_backup import get_nba_player_stats_backup
        self.assertTrue(callable(get_nba_player_stats_backup))


# ── Section 2a: _normalize_season helper ─────────────────────────────────────

class TestNormalizeSeason(unittest.TestCase):
    """Verify season format conversion for NBA.com stats API."""

    def test_none_returns_current_season(self):
        from data.nba_stats_backup import _normalize_season, _current_season_str
        result = _normalize_season(None)
        self.assertEqual(result, _current_season_str())

    def test_nba_format_passthrough(self):
        from data.nba_stats_backup import _normalize_season
        self.assertEqual(_normalize_season("2024-25"), "2024-25")
        self.assertEqual(_normalize_season("2023-24"), "2023-24")

    def test_year_string_converted(self):
        from data.nba_stats_backup import _normalize_season
        self.assertEqual(_normalize_season("2024"), "2024-25")
        self.assertEqual(_normalize_season("2023"), "2023-24")

    def test_year_int_converted(self):
        from data.nba_stats_backup import _normalize_season
        self.assertEqual(_normalize_season(2024), "2024-25")
        self.assertEqual(_normalize_season(2023), "2023-24")

    def test_unknown_string_passthrough(self):
        from data.nba_stats_backup import _normalize_season
        self.assertEqual(_normalize_season("current"), "current")


# ── Section 2b: _rows_to_dicts helper ────────────────────────────────────────

class TestRowsToDicts(unittest.TestCase):
    """Verify the NBA stats resultSet → list[dict] conversion."""

    def test_converts_result_set(self):
        from data.nba_stats_backup import _rows_to_dicts
        result_set = {
            "headers": ["TEAM_ID", "TEAM_NAME", "W"],
            "rowSet": [
                [1, "Lakers", 30],
                [2, "Celtics", 35],
            ],
        }
        dicts = _rows_to_dicts(result_set)
        self.assertEqual(len(dicts), 2)
        self.assertEqual(dicts[0]["team_id"], 1)
        self.assertEqual(dicts[0]["team_name"], "Lakers")
        self.assertEqual(dicts[0]["w"], 30)
        self.assertEqual(dicts[1]["team_name"], "Celtics")

    def test_empty_result_set(self):
        from data.nba_stats_backup import _rows_to_dicts
        result_set = {"headers": ["A", "B"], "rowSet": []}
        self.assertEqual(_rows_to_dicts(result_set), [])

    def test_missing_headers(self):
        from data.nba_stats_backup import _rows_to_dicts
        result_set = {"rowSet": [[1, 2]]}
        # With no headers, should produce empty dicts
        dicts = _rows_to_dicts(result_set)
        self.assertEqual(len(dicts), 1)
        self.assertEqual(dicts[0], {})


# ── Section 3: get_team_stats_backup ─────────────────────────────────────

class TestFetchTeamStatsFallback(unittest.TestCase):
    """Verify get_team_stats_backup returns correct schema."""

    def setUp(self):
        # Clear fallback cache before each test
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_returns_team_stats_on_success(self, mock_request):
        from data.nba_stats_backup import get_team_stats_backup

        # Basic stats response
        mock_request.side_effect = [
            {  # basic
                "resultSets": [{
                    "headers": ["TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "W", "L"],
                    "rowSet": [[1, "LAL", "Los Angeles Lakers", 30, 20]],
                }],
            },
            {  # advanced
                "resultSets": [{
                    "headers": ["TEAM_ID", "PACE", "OFF_RATING", "DEF_RATING"],
                    "rowSet": [[1, 100.5, 115.2, 108.7]],
                }],
            },
        ]

        result = get_team_stats_backup(season="2024-25")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        team = result[0]
        self.assertEqual(team["team_abbreviation"], "LAL")
        self.assertEqual(team["team_name"], "Los Angeles Lakers")
        self.assertEqual(team["wins"], 30)
        self.assertEqual(team["losses"], 20)
        self.assertAlmostEqual(team["pace"], 100.5)
        self.assertAlmostEqual(team["offensive_rating"], 115.2)
        self.assertAlmostEqual(team["defensive_rating"], 108.7)

    @patch("data.nba_stats_backup._request_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_request):
        from data.nba_stats_backup import get_team_stats_backup
        result = get_team_stats_backup()
        self.assertEqual(result, [])


# ── Section 4: get_players_backup ────────────────────────────────────────

class TestFetchPlayersFallback(unittest.TestCase):
    """Verify get_players_backup returns correct schema."""

    def setUp(self):
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_returns_players_on_success(self, mock_request):
        from data.nba_stats_backup import get_players_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": [
                    "PERSON_ID", "DISPLAY_FIRST_LAST", "DISPLAY_LAST_COMMA_FIRST",
                    "TEAM_ID", "TEAM_ABBREVIATION",
                ],
                "rowSet": [
                    [10, "LeBron James", "James, LeBron", 1, "LAL"],
                    [20, "Jayson Tatum", "Tatum, Jayson", 2, "BOS"],
                ],
            }],
        }

        result = get_players_backup()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 10)
        self.assertEqual(result[0]["name"], "LeBron James")
        self.assertEqual(result[1]["team_abbreviation"], "BOS")

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_filters_by_team_id(self, mock_request):
        from data.nba_stats_backup import get_players_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": [
                    "PERSON_ID", "DISPLAY_FIRST_LAST", "DISPLAY_LAST_COMMA_FIRST",
                    "TEAM_ID", "TEAM_ABBREVIATION",
                ],
                "rowSet": [
                    [10, "LeBron James", "James, LeBron", 1, "LAL"],
                    [20, "Jayson Tatum", "Tatum, Jayson", 2, "BOS"],
                ],
            }],
        }

        result = get_players_backup(team_id=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "LeBron James")

    @patch("data.nba_stats_backup._request_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_request):
        from data.nba_stats_backup import get_players_backup
        result = get_players_backup()
        self.assertEqual(result, [])


# ── Section 5: get_player_stats_backup ───────────────────────────────────

class TestFetchPlayerStatsFallback(unittest.TestCase):
    """Verify get_player_stats_backup returns correct schema."""

    def setUp(self):
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_returns_player_stats_on_success(self, mock_request):
        from data.nba_stats_backup import get_player_stats_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": [
                    "PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION",
                    "MIN", "PTS", "REB", "AST", "FG3M",
                    "STL", "BLK", "TOV", "FT_PCT",
                ],
                "rowSet": [
                    [10, "LeBron James", "LAL", 35.0, 28.5, 7.2, 8.1, 2.0, 1.3, 0.9, 3.5, 0.75],
                ],
            }],
        }

        result = get_player_stats_backup()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        p = result[0]
        self.assertEqual(p["player_id"], "10")
        self.assertEqual(p["name"], "LeBron James")
        self.assertEqual(p["team"], "LAL")
        self.assertAlmostEqual(p["points_avg"], 28.5)
        self.assertAlmostEqual(p["rebounds_avg"], 7.2)
        self.assertAlmostEqual(p["assists_avg"], 8.1)
        self.assertAlmostEqual(p["ft_pct"], 0.75)
        # std-dev fields should all be 0.0 (not available from fallback)
        for std_field in ("points_std", "rebounds_std", "assists_std",
                          "threes_std", "steals_std", "blocks_std", "turnovers_std"):
            self.assertEqual(p[std_field], 0.0, f"{std_field} should be 0.0")

    @patch("data.nba_stats_backup._request_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_request):
        from data.nba_stats_backup import get_player_stats_backup
        result = get_player_stats_backup()
        self.assertEqual(result, [])


# ── Section 6: get_nba_team_stats_backup ─────────────────────────────────

class TestFetchNbaTeamStatsFallback(unittest.TestCase):
    """Verify get_nba_team_stats_backup returns correct schema."""

    def setUp(self):
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_returns_team_stats_on_success(self, mock_request):
        from data.nba_stats_backup import get_nba_team_stats_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": ["TEAM_ID", "TEAM_NAME", "W", "L", "PTS"],
                "rowSet": [[1, "Lakers", 30, 20, 115.5]],
            }],
        }

        result = get_nba_team_stats_backup()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["team_name"], "Lakers")

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_filters_by_team_id(self, mock_request):
        from data.nba_stats_backup import get_nba_team_stats_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": ["TEAM_ID", "TEAM_NAME"],
                "rowSet": [[1, "Lakers"], [2, "Celtics"]],
            }],
        }

        result = get_nba_team_stats_backup(team_id=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["team_name"], "Lakers")

    @patch("data.nba_stats_backup._request_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_request):
        from data.nba_stats_backup import get_nba_team_stats_backup
        result = get_nba_team_stats_backup()
        self.assertEqual(result, [])


# ── Section 7: get_nba_player_stats_backup ───────────────────────────────

class TestFetchNbaPlayerStatsFallback(unittest.TestCase):
    """Verify get_nba_player_stats_backup returns correct schema."""

    def setUp(self):
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_returns_player_stats_on_success(self, mock_request):
        from data.nba_stats_backup import get_nba_player_stats_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": ["PLAYER_ID", "PLAYER_NAME", "PTS"],
                "rowSet": [[10, "LeBron James", 28.5]],
            }],
        }

        result = get_nba_player_stats_backup()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["player_name"], "LeBron James")

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_filters_by_player_id(self, mock_request):
        from data.nba_stats_backup import get_nba_player_stats_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": ["PLAYER_ID", "PLAYER_NAME"],
                "rowSet": [[10, "LeBron"], [20, "Tatum"]],
            }],
        }

        result = get_nba_player_stats_backup(player_id=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["player_name"], "LeBron")

    @patch("data.nba_stats_backup._request_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_request):
        from data.nba_stats_backup import get_nba_player_stats_backup
        result = get_nba_player_stats_backup()
        self.assertEqual(result, [])


# ── Section 8: Caching ──────────────────────────────────────────────────────

class TestFallbackCaching(unittest.TestCase):
    """Verify that fallback functions cache results."""

    def setUp(self):
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup._request_nba_stats")
    def test_second_call_uses_cache(self, mock_request):
        from data.nba_stats_backup import get_player_stats_backup

        mock_request.return_value = {
            "resultSets": [{
                "headers": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION",
                            "MIN", "PTS", "REB", "AST", "FG3M",
                            "STL", "BLK", "TOV", "FT_PCT"],
                "rowSet": [[10, "LeBron", "LAL", 35, 28, 7, 8, 2, 1, 1, 3, 0.75]],
            }],
        }

        # First call hits the API
        result1 = get_player_stats_backup()
        self.assertEqual(len(result1), 1)

        # Second call should use cache — mock won't be called again
        mock_request.reset_mock()
        mock_request.return_value = None  # If called, would return empty
        result2 = get_player_stats_backup()
        self.assertEqual(len(result2), 1)
        mock_request.assert_not_called()


# ── Section 9: ApiNba fallback integration ─────────────────────────────

# ── Section 11: Retry logic in _request_nba_stats ───────────────────────

class TestRequestNbaStatsRetry(unittest.TestCase):
    """Verify that _request_nba_stats retries on timeout and 5xx errors."""

    def setUp(self):
        import data.nba_stats_backup as fb
        fb._cache.clear()

    @patch("data.nba_stats_backup.time.sleep")
    @patch("data.nba_stats_backup.requests.get")
    def test_retries_on_timeout(self, mock_get, mock_sleep):
        """Should retry up to _MAX_RETRIES times on Timeout."""
        from data.nba_stats_backup import _request_nba_stats, _MAX_RETRIES

        mock_get.side_effect = _requests_lib.exceptions.Timeout("read timed out")
        result = _request_nba_stats("leaguedashteamstats", {"Season": "2025-26"})
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, _MAX_RETRIES + 1)
        # Verify sleep was called between retries
        self.assertEqual(mock_sleep.call_count, _MAX_RETRIES)

    @patch("data.nba_stats_backup.time.sleep")
    @patch("data.nba_stats_backup.requests.get")
    def test_retries_on_connection_error(self, mock_get, mock_sleep):
        """Should retry on ConnectionError."""
        from data.nba_stats_backup import _request_nba_stats, _MAX_RETRIES

        mock_get.side_effect = _requests_lib.exceptions.ConnectionError("connection reset")
        result = _request_nba_stats("leaguedashteamstats", {})
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, _MAX_RETRIES + 1)

    @patch("data.nba_stats_backup.time.sleep")
    @patch("data.nba_stats_backup.requests.get")
    def test_retries_on_5xx(self, mock_get, mock_sleep):
        """Should retry on HTTP 5xx status codes."""
        from data.nba_stats_backup import _request_nba_stats, _MAX_RETRIES

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_get.return_value = mock_resp
        result = _request_nba_stats("leaguedashteamstats", {})
        self.assertIsNone(result)
        # First call + _MAX_RETRIES retries
        self.assertEqual(mock_get.call_count, _MAX_RETRIES + 1)

    @patch("data.nba_stats_backup.time.sleep")
    @patch("data.nba_stats_backup.requests.get")
    def test_succeeds_after_retry(self, mock_get, mock_sleep):
        """Should return data if a retry succeeds."""
        from data.nba_stats_backup import _request_nba_stats

        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.json.return_value = {"resultSets": [{"headers": ["A"], "rowSet": [[1]]}]}

        mock_get.side_effect = [
            _requests_lib.exceptions.Timeout("timed out"),
            good_resp,
        ]
        result = _request_nba_stats("leaguedashteamstats", {})
        self.assertIsNotNone(result)
        self.assertEqual(mock_get.call_count, 2)

    @patch("data.nba_stats_backup.requests.get")
    def test_no_retry_on_4xx(self, mock_get):
        """Should NOT retry on HTTP 4xx errors (client errors)."""
        from data.nba_stats_backup import _request_nba_stats

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp
        result = _request_nba_stats("leaguedashteamstats", {})
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 1)

    def test_max_retries_constant_exists(self):
        """_MAX_RETRIES must be at least 1."""
        from data.nba_stats_backup import _MAX_RETRIES
        self.assertGreaterEqual(_MAX_RETRIES, 1)

    def test_headers_include_nba_stats_origin(self):
        """Headers must include x-nba-stats-origin for stats.nba.com."""
        from data.nba_stats_backup import _NBA_STATS_HEADERS
        self.assertIn("x-nba-stats-origin", _NBA_STATS_HEADERS)
        self.assertEqual(_NBA_STATS_HEADERS["x-nba-stats-origin"], "stats")

    def test_headers_include_nba_stats_token(self):
        """Headers must include x-nba-stats-token for stats.nba.com."""
        from data.nba_stats_backup import _NBA_STATS_HEADERS
        self.assertIn("x-nba-stats-token", _NBA_STATS_HEADERS)
        self.assertEqual(_NBA_STATS_HEADERS["x-nba-stats-token"], "true")


if __name__ == "__main__":
    unittest.main()
