"""
tests/test_nba_stats_fallback.py
---------------------------------
Tests for the free NBA stats fallback module (data/nba_stats_fallback.py).

Verifies:
  1. Module structure and public API surface
  2. _rows_to_dicts helper correctness
  3. Each fallback function returns correct schema on mock success
  4. Each fallback function returns [] on mock failure
  5. Caching prevents duplicate HTTP calls
  6. ClearSports functions fall back when primary returns empty
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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
        """data.nba_stats_fallback must be importable."""
        import data.nba_stats_fallback  # noqa: F401

    def test_fetch_team_stats_fallback_exists(self):
        from data.nba_stats_fallback import fetch_team_stats_fallback
        self.assertTrue(callable(fetch_team_stats_fallback))

    def test_fetch_players_fallback_exists(self):
        from data.nba_stats_fallback import fetch_players_fallback
        self.assertTrue(callable(fetch_players_fallback))

    def test_fetch_player_stats_fallback_exists(self):
        from data.nba_stats_fallback import fetch_player_stats_fallback
        self.assertTrue(callable(fetch_player_stats_fallback))

    def test_fetch_nba_team_stats_fallback_exists(self):
        from data.nba_stats_fallback import fetch_nba_team_stats_fallback
        self.assertTrue(callable(fetch_nba_team_stats_fallback))

    def test_fetch_nba_player_stats_fallback_exists(self):
        from data.nba_stats_fallback import fetch_nba_player_stats_fallback
        self.assertTrue(callable(fetch_nba_player_stats_fallback))


# ── Section 2a: _normalize_season helper ─────────────────────────────────────

class TestNormalizeSeason(unittest.TestCase):
    """Verify season format conversion for NBA.com stats API."""

    def test_none_returns_current_season(self):
        from data.nba_stats_fallback import _normalize_season, _current_season_str
        result = _normalize_season(None)
        self.assertEqual(result, _current_season_str())

    def test_nba_format_passthrough(self):
        from data.nba_stats_fallback import _normalize_season
        self.assertEqual(_normalize_season("2024-25"), "2024-25")
        self.assertEqual(_normalize_season("2023-24"), "2023-24")

    def test_year_string_converted(self):
        from data.nba_stats_fallback import _normalize_season
        self.assertEqual(_normalize_season("2024"), "2024-25")
        self.assertEqual(_normalize_season("2023"), "2023-24")

    def test_year_int_converted(self):
        from data.nba_stats_fallback import _normalize_season
        self.assertEqual(_normalize_season(2024), "2024-25")
        self.assertEqual(_normalize_season(2023), "2023-24")

    def test_unknown_string_passthrough(self):
        from data.nba_stats_fallback import _normalize_season
        self.assertEqual(_normalize_season("current"), "current")


# ── Section 2b: _rows_to_dicts helper ────────────────────────────────────────

class TestRowsToDicts(unittest.TestCase):
    """Verify the NBA stats resultSet → list[dict] conversion."""

    def test_converts_result_set(self):
        from data.nba_stats_fallback import _rows_to_dicts
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
        from data.nba_stats_fallback import _rows_to_dicts
        result_set = {"headers": ["A", "B"], "rowSet": []}
        self.assertEqual(_rows_to_dicts(result_set), [])

    def test_missing_headers(self):
        from data.nba_stats_fallback import _rows_to_dicts
        result_set = {"rowSet": [[1, 2]]}
        # With no headers, should produce empty dicts
        dicts = _rows_to_dicts(result_set)
        self.assertEqual(len(dicts), 1)
        self.assertEqual(dicts[0], {})


# ── Section 3: fetch_team_stats_fallback ─────────────────────────────────────

class TestFetchTeamStatsFallback(unittest.TestCase):
    """Verify fetch_team_stats_fallback returns correct schema."""

    def setUp(self):
        # Clear fallback cache before each test
        import data.nba_stats_fallback as fb
        fb._cache.clear()

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_returns_team_stats_on_success(self, mock_fetch):
        from data.nba_stats_fallback import fetch_team_stats_fallback

        # Basic stats response
        mock_fetch.side_effect = [
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

        result = fetch_team_stats_fallback(season="2024-25")
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

    @patch("data.nba_stats_fallback._fetch_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_fetch):
        from data.nba_stats_fallback import fetch_team_stats_fallback
        result = fetch_team_stats_fallback()
        self.assertEqual(result, [])


# ── Section 4: fetch_players_fallback ────────────────────────────────────────

class TestFetchPlayersFallback(unittest.TestCase):
    """Verify fetch_players_fallback returns correct schema."""

    def setUp(self):
        import data.nba_stats_fallback as fb
        fb._cache.clear()

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_returns_players_on_success(self, mock_fetch):
        from data.nba_stats_fallback import fetch_players_fallback

        mock_fetch.return_value = {
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

        result = fetch_players_fallback()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 10)
        self.assertEqual(result[0]["name"], "LeBron James")
        self.assertEqual(result[1]["team_abbreviation"], "BOS")

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_filters_by_team_id(self, mock_fetch):
        from data.nba_stats_fallback import fetch_players_fallback

        mock_fetch.return_value = {
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

        result = fetch_players_fallback(team_id=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "LeBron James")

    @patch("data.nba_stats_fallback._fetch_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_fetch):
        from data.nba_stats_fallback import fetch_players_fallback
        result = fetch_players_fallback()
        self.assertEqual(result, [])


# ── Section 5: fetch_player_stats_fallback ───────────────────────────────────

class TestFetchPlayerStatsFallback(unittest.TestCase):
    """Verify fetch_player_stats_fallback returns correct schema."""

    def setUp(self):
        import data.nba_stats_fallback as fb
        fb._cache.clear()

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_returns_player_stats_on_success(self, mock_fetch):
        from data.nba_stats_fallback import fetch_player_stats_fallback

        mock_fetch.return_value = {
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

        result = fetch_player_stats_fallback()
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

    @patch("data.nba_stats_fallback._fetch_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_fetch):
        from data.nba_stats_fallback import fetch_player_stats_fallback
        result = fetch_player_stats_fallback()
        self.assertEqual(result, [])


# ── Section 6: fetch_nba_team_stats_fallback ─────────────────────────────────

class TestFetchNbaTeamStatsFallback(unittest.TestCase):
    """Verify fetch_nba_team_stats_fallback returns correct schema."""

    def setUp(self):
        import data.nba_stats_fallback as fb
        fb._cache.clear()

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_returns_team_stats_on_success(self, mock_fetch):
        from data.nba_stats_fallback import fetch_nba_team_stats_fallback

        mock_fetch.return_value = {
            "resultSets": [{
                "headers": ["TEAM_ID", "TEAM_NAME", "W", "L", "PTS"],
                "rowSet": [[1, "Lakers", 30, 20, 115.5]],
            }],
        }

        result = fetch_nba_team_stats_fallback()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["team_name"], "Lakers")

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_filters_by_team_id(self, mock_fetch):
        from data.nba_stats_fallback import fetch_nba_team_stats_fallback

        mock_fetch.return_value = {
            "resultSets": [{
                "headers": ["TEAM_ID", "TEAM_NAME"],
                "rowSet": [[1, "Lakers"], [2, "Celtics"]],
            }],
        }

        result = fetch_nba_team_stats_fallback(team_id=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["team_name"], "Lakers")

    @patch("data.nba_stats_fallback._fetch_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_fetch):
        from data.nba_stats_fallback import fetch_nba_team_stats_fallback
        result = fetch_nba_team_stats_fallback()
        self.assertEqual(result, [])


# ── Section 7: fetch_nba_player_stats_fallback ───────────────────────────────

class TestFetchNbaPlayerStatsFallback(unittest.TestCase):
    """Verify fetch_nba_player_stats_fallback returns correct schema."""

    def setUp(self):
        import data.nba_stats_fallback as fb
        fb._cache.clear()

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_returns_player_stats_on_success(self, mock_fetch):
        from data.nba_stats_fallback import fetch_nba_player_stats_fallback

        mock_fetch.return_value = {
            "resultSets": [{
                "headers": ["PLAYER_ID", "PLAYER_NAME", "PTS"],
                "rowSet": [[10, "LeBron James", 28.5]],
            }],
        }

        result = fetch_nba_player_stats_fallback()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["player_name"], "LeBron James")

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_filters_by_player_id(self, mock_fetch):
        from data.nba_stats_fallback import fetch_nba_player_stats_fallback

        mock_fetch.return_value = {
            "resultSets": [{
                "headers": ["PLAYER_ID", "PLAYER_NAME"],
                "rowSet": [[10, "LeBron"], [20, "Tatum"]],
            }],
        }

        result = fetch_nba_player_stats_fallback(player_id=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["player_name"], "LeBron")

    @patch("data.nba_stats_fallback._fetch_nba_stats", return_value=None)
    def test_returns_empty_on_failure(self, mock_fetch):
        from data.nba_stats_fallback import fetch_nba_player_stats_fallback
        result = fetch_nba_player_stats_fallback()
        self.assertEqual(result, [])


# ── Section 8: Caching ──────────────────────────────────────────────────────

class TestFallbackCaching(unittest.TestCase):
    """Verify that fallback functions cache results."""

    def setUp(self):
        import data.nba_stats_fallback as fb
        fb._cache.clear()

    @patch("data.nba_stats_fallback._fetch_nba_stats")
    def test_second_call_uses_cache(self, mock_fetch):
        from data.nba_stats_fallback import fetch_player_stats_fallback

        mock_fetch.return_value = {
            "resultSets": [{
                "headers": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION",
                            "MIN", "PTS", "REB", "AST", "FG3M",
                            "STL", "BLK", "TOV", "FT_PCT"],
                "rowSet": [[10, "LeBron", "LAL", 35, 28, 7, 8, 2, 1, 1, 3, 0.75]],
            }],
        }

        # First call hits the API
        result1 = fetch_player_stats_fallback()
        self.assertEqual(len(result1), 1)

        # Second call should use cache — mock won't be called again
        mock_fetch.reset_mock()
        mock_fetch.return_value = None  # If called, would return empty
        result2 = fetch_player_stats_fallback()
        self.assertEqual(len(result2), 1)
        mock_fetch.assert_not_called()


# ── Section 9: ClearSports fallback integration ─────────────────────────────

class TestClearSportsFallbackIntegration(unittest.TestCase):
    """Verify ClearSports functions fall back to free API when primary fails."""

    @patch("data.nba_stats_fallback.fetch_player_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_fetch_player_stats_falls_back(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_player_stats
        mock_fallback.return_value = [{"player_id": "10", "name": "LeBron", "team": "LAL"}]
        result = fetch_player_stats()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_called_once()

    @patch("data.nba_stats_fallback.fetch_team_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_fetch_team_stats_falls_back(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_team_stats
        mock_fallback.return_value = [{"team_abbreviation": "LAL", "wins": 30}]
        result = fetch_team_stats()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_called_once()

    @patch("data.nba_stats_fallback.fetch_players_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_fetch_players_falls_back(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_players
        mock_fallback.return_value = [{"id": 10, "name": "LeBron"}]
        result = fetch_players()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_called_once()

    @patch("data.nba_stats_fallback.fetch_nba_team_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_fetch_nba_team_stats_falls_back(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_nba_team_stats
        mock_fallback.return_value = [{"team_id": 1, "w": 30}]
        result = fetch_nba_team_stats()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_called_once()

    @patch("data.nba_stats_fallback.fetch_nba_team_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_fetch_nba_team_stats_forwards_season(self, mock_fetch, mock_key, mock_fallback):
        """Season parameter must be forwarded to fallback (not hardcoded None)."""
        from data.clearsports_client import fetch_nba_team_stats
        mock_fallback.return_value = [{"team_id": 1, "w": 30}]
        fetch_nba_team_stats(team_id=5, season="2024")
        mock_fallback.assert_called_once_with(team_id=5, season="2024")

    @patch("data.nba_stats_fallback.fetch_nba_player_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_fetch_nba_player_stats_falls_back(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_nba_player_stats
        mock_fallback.return_value = [{"player_id": 10, "pts": 28.5}]
        result = fetch_nba_player_stats()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_called_once()


# ── Section 10: ClearSports primary still works when not broken ──────────────

class TestClearSportsPrimaryStillWorks(unittest.TestCase):
    """When ClearSports returns valid data, fallback should NOT be called."""

    @patch("data.nba_stats_fallback.fetch_player_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_player_stats_uses_primary(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_player_stats
        mock_fetch.return_value = [{"id": 10, "name": "LeBron", "team": "LAL"}]
        result = fetch_player_stats()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_not_called()

    @patch("data.nba_stats_fallback.fetch_team_stats_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_team_stats_uses_primary(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_team_stats
        mock_fetch.return_value = [{"abbreviation": "LAL", "name": "Lakers", "wins": 30}]
        result = fetch_team_stats()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_not_called()

    @patch("data.nba_stats_fallback.fetch_players_fallback")
    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_players_uses_primary(self, mock_fetch, mock_key, mock_fallback):
        from data.clearsports_client import fetch_players
        mock_fetch.return_value = [{"id": 10, "name": "LeBron"}]
        result = fetch_players()
        self.assertEqual(len(result), 1)
        mock_fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
