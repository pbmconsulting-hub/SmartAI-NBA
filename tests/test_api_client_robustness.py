"""
tests/test_api_client_robustness.py
-----------------------------------
Tests for API client robustness improvements:
  1. ClearSports: no duplicate apiKey in query params for game_log/standings/news
  2. ClearSports: 422 status code handled without retry
  3. ClearSports: empty response body handled without JSONDecodeError retry
  4. Odds API: empty response body handled without JSONDecodeError retry
  5. ClearSports: cascading .get() safe when nested record fields are None
"""

import pathlib
import sys
import os
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


_CS_SRC = pathlib.Path(__file__).parent.parent / "data" / "clearsports_client.py"
_OA_SRC = pathlib.Path(__file__).parent.parent / "data" / "odds_api_client.py"


# ── Section 1: ClearSports source-level checks ──────────────────────────────

class TestClearSportsNoApiKeyInParams(unittest.TestCase):
    """Verify that fetch_player_game_log, fetch_standings, and fetch_news
    do NOT put the apiKey into the query params dict.  The Bearer header in
    _fetch_with_retry already handles authentication."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_fetch_player_game_log_no_apikey_in_params(self):
        """params dict for game_log must not contain 'apiKey'."""
        idx = self.src.find("def fetch_player_game_log(")
        self.assertGreater(idx, 0)
        # Use a 1500-char window to reach past the docstring
        snippet = self.src[idx:idx + 1500]
        self.assertIn('"last_n"', snippet)
        self.assertNotIn('"apiKey"', snippet,
                         "fetch_player_game_log params must not include apiKey")

    def test_fetch_standings_no_apikey_in_params(self):
        """params dict for standings must not contain 'apiKey'."""
        idx = self.src.find("def fetch_standings(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertNotIn('"apiKey"', snippet,
                         "fetch_standings params must not include apiKey")

    def test_fetch_news_no_apikey_in_params(self):
        """params dict for news must not contain 'apiKey'."""
        idx = self.src.find("def fetch_news(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertIn('"limit"', snippet)
        self.assertNotIn('"apiKey"', snippet,
                         "fetch_news params must not include apiKey")


# ── Section 2: ClearSports 422 handling ──────────────────────────────────────

class TestClearSports422Handling(unittest.TestCase):
    """Verify that _fetch_with_retry in clearsports_client handles HTTP 422."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_422_status_code_handled(self):
        """_fetch_with_retry should check for 422 status."""
        self.assertIn("status_code == 422", self.src,
                      "ClearSports must handle 422 status code")

    def test_422_returns_none_without_retry(self):
        """422 handler should return None (not continue to retry)."""
        # Find the 422 handling block
        idx = self.src.find("status_code == 422")
        self.assertGreater(idx, 0)
        # Next 200 chars should contain "return None" (immediate exit, no retry)
        snippet = self.src[idx:idx + 200]
        self.assertIn("return None", snippet,
                      "422 should return None immediately without retry")


# ── Section 3: Empty response body handling ──────────────────────────────────

class TestEmptyResponseBodyHandling(unittest.TestCase):
    """Verify both API clients check for empty response bodies before .json()."""

    def test_clearsports_checks_empty_body(self):
        """ClearSports _fetch_with_retry must check resp.text before .json()."""
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("not resp.text", src,
                      "ClearSports must check for empty resp.text")

    def test_odds_api_checks_empty_body(self):
        """Odds API _fetch_with_retry must check resp.text before .json()."""
        src = _OA_SRC.read_text(encoding="utf-8")
        self.assertIn("not resp.text", src,
                      "Odds API must check for empty resp.text")


# ── Section 4: Cascading .get() safety ───────────────────────────────────────

class TestCascadingGetSafety(unittest.TestCase):
    """Verify that nested .get() patterns in fetch_games_today use 'or {}' to
    guard against None values (not just missing keys)."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_home_record_uses_or_fallback(self):
        """home_record .get() must use 'or {}' pattern for None safety."""
        self.assertIn('(g.get("home_record") or {})', self.src,
                      "home_record access must use (x or {}) pattern")

    def test_away_record_uses_or_fallback(self):
        """away_record .get() must use 'or {}' pattern for None safety."""
        self.assertIn('(g.get("away_record") or {})', self.src,
                      "away_record access must use (x or {}) pattern")


# ── Section 5: Runtime test — ClearSports games parsing with None records ────

class TestClearSportsGameParsingEdgeCases(unittest.TestCase):
    """Runtime tests for fetch_games_today parsing logic with edge-case data."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_games_with_none_records(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """Games with home_record: null should not cause AttributeError."""
        from data.clearsports_client import fetch_games_today

        mock_fetch.return_value = [
            {
                "game_id": "g1",
                "home_team": "LAL",
                "away_team": "BOS",
                "home_record": None,
                "away_record": None,
                "vegas_spread": -3.5,
                "game_total": 220,
            }
        ]

        games = fetch_games_today()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_wins"], 0)
        self.assertEqual(games[0]["home_losses"], 0)
        self.assertEqual(games[0]["away_wins"], 0)
        self.assertEqual(games[0]["away_losses"], 0)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_games_with_nested_records(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """Games with nested home_record dicts should parse correctly."""
        from data.clearsports_client import fetch_games_today

        mock_fetch.return_value = [
            {
                "game_id": "g2",
                "home_team": "MIA",
                "away_team": "NYK",
                "home_record": {"wins": 35, "losses": 20},
                "away_record": {"wins": 40, "losses": 15},
                "vegas_spread": -1.5,
                "game_total": 215,
            }
        ]

        games = fetch_games_today()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_wins"], 35)
        self.assertEqual(games[0]["home_losses"], 20)
        self.assertEqual(games[0]["away_wins"], 40)
        self.assertEqual(games[0]["away_losses"], 15)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_games_with_flat_wins_losses(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """Games with flat home_wins/home_losses fields should parse correctly."""
        from data.clearsports_client import fetch_games_today

        mock_fetch.return_value = [
            {
                "game_id": "g3",
                "home_team": "GSW",
                "away_team": "PHX",
                "home_wins": 42,
                "home_losses": 18,
                "away_wins": 38,
                "away_losses": 22,
                "vegas_spread": -5.0,
                "game_total": 230,
            }
        ]

        games = fetch_games_today()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_wins"], 42)
        self.assertEqual(games[0]["home_losses"], 18)
        self.assertEqual(games[0]["away_wins"], 38)
        self.assertEqual(games[0]["away_losses"], 22)


# ── Section 6: Cache key includes params ─────────────────────────────────────

class TestCacheKeyIncludesParams(unittest.TestCase):
    """Verify that _build_cache_key builds unique keys for different params."""

    def test_build_cache_key_exists(self):
        """_build_cache_key function must exist in clearsports_client source."""
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("def _build_cache_key(", src)

    def test_build_cache_key_behavior(self):
        """Different params must produce different cache keys."""
        from data.clearsports_client import _build_cache_key

        key1 = _build_cache_key("https://example.com/games", {"date": "2026-03-23"})
        key2 = _build_cache_key("https://example.com/games", {"date": "2026-03-24"})
        key3 = _build_cache_key("https://example.com/games")

        self.assertNotEqual(key1, key2, "Different date params must produce different keys")
        self.assertNotEqual(key1, key3, "Params vs no params must produce different keys")

    def test_build_cache_key_no_params(self):
        """No params should return the URL as-is."""
        from data.clearsports_client import _build_cache_key

        self.assertEqual(_build_cache_key("https://example.com/games"), "https://example.com/games")


# ── Section 7: _extract_team_abbrev resilience ───────────────────────────────

class TestExtractTeamAbbrev(unittest.TestCase):
    """Verify _extract_team_abbrev handles multiple field naming conventions."""

    def test_direct_home_team_field(self):
        """home_team field should be extracted correctly."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_team": "LAL"}, "home")
        self.assertEqual(result, "LAL")

    def test_abbreviation_field(self):
        """home_abbreviation / away_abbreviation should work."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"away_abbreviation": "bos"}, "away")
        self.assertEqual(result, "BOS")

    def test_tricode_field(self):
        """home_tricode / away_tricode should work."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_tricode": "gsw"}, "home")
        self.assertEqual(result, "GSW")

    def test_team_abbreviation_field(self):
        """home_team_abbreviation / away_team_abbreviation should work."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"away_team_abbreviation": "MIA"}, "away")
        self.assertEqual(result, "MIA")

    def test_nested_dict(self):
        """Nested dict like home: {abbreviation: 'LAL'} should work."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home": {"abbreviation": "LAL"}}, "home")
        self.assertEqual(result, "LAL")

    def test_nested_team_dict(self):
        """Nested dict like home_team: {tricode: 'BOS'} should work."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_team": {"tricode": "BOS"}}, "home")
        self.assertEqual(result, "BOS")

    def test_empty_on_missing_fields(self):
        """Should return empty string when no matching fields found."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"unrelated": "data"}, "home")
        self.assertEqual(result, "")

    def test_empty_string_field_returns_empty(self):
        """Empty string in team field should return empty."""
        from data.clearsports_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_team": ""}, "home")
        self.assertEqual(result, "")


# ── Section 8: fetch_games_today skips empty-team entries ────────────────────

class TestFetchGamesTodaySkipsEmptyTeams(unittest.TestCase):
    """Verify that games with empty team abbreviations are skipped."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_skips_games_with_empty_teams(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """Games missing team abbreviations should be skipped."""
        from data.clearsports_client import fetch_games_today

        mock_fetch.return_value = [
            {"game_id": "g1", "home_team": "LAL", "away_team": "BOS", "vegas_spread": -3.5},
            {"game_id": "g2"},  # no team info at all
            {"game_id": "g3", "home_team": "MIA"},  # missing away_team
        ]

        games = fetch_games_today()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_alternate_field_names_work(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """Games with alternate field names (tricode, nested) should parse."""
        from data.clearsports_client import fetch_games_today

        mock_fetch.return_value = [
            {"game_id": "g1", "home_tricode": "LAL", "away_tricode": "BOS", "vegas_spread": -2.0},
        ]

        games = fetch_games_today()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")
        self.assertEqual(games[0]["away_team"], "BOS")

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_client_side_date_filter(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """When API returns >20 games, client-side date filter should apply."""
        from data.clearsports_client import fetch_games_today, _today_str

        today = _today_str()
        # 25 games total, but only 2 match today's date
        all_games = []
        for i in range(23):
            all_games.append({
                "game_id": f"old_{i}",
                "home_team": "LAL",
                "away_team": "BOS",
                "game_date": "2025-01-01",
            })
        all_games.append({
            "game_id": "today_1",
            "home_team": "MIA",
            "away_team": "NYK",
            "game_date": today,
        })
        all_games.append({
            "game_id": "today_2",
            "home_team": "GSW",
            "away_team": "PHX",
            "game_date": today,
        })

        mock_fetch.return_value = all_games
        games = fetch_games_today()
        self.assertEqual(len(games), 2)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._cache_get", return_value=None)
    @patch("data.clearsports_client._cache_set")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_nested_team_objects(self, mock_fetch, mock_cache_set, mock_cache_get, mock_key):
        """Games with nested team objects should parse correctly."""
        from data.clearsports_client import fetch_games_today

        mock_fetch.return_value = [
            {
                "game_id": "g1",
                "home": {"abbreviation": "CHI"},
                "away": {"abbreviation": "CLE"},
                "vegas_spread": -1.0,
                "game_total": 210,
            }
        ]

        games = fetch_games_today()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "CHI")
        self.assertEqual(games[0]["away_team"], "CLE")


# ── Section 9: fetch_todays_games validates team names ───────────────────────

class TestFetchTodaysGamesValidation(unittest.TestCase):
    """Verify fetch_todays_games validates games have team names."""

    @patch("data.live_data_fetcher._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.live_data_fetcher._enrich_games_with_predictions", side_effect=lambda g: g)
    @patch("data.live_data_fetcher._enrich_games_with_clearsports_odds", side_effect=lambda g: g)
    @patch("data.live_data_fetcher._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.live_data_fetcher._build_games_from_odds_api", return_value=[
        {"game_id": "fallback_1", "home_team": "LAL", "away_team": "BOS", "vegas_spread": -3.0, "game_total": 220}
    ])
    @patch("data.clearsports_client.fetch_games_today")
    def test_falls_back_when_all_teams_empty(
        self, mock_cs, mock_build, mock_enrich_odds, mock_enrich_cs,
        mock_enrich_pred, mock_enrich_stand,
    ):
        """When ClearSports returns games with empty teams, fallback should trigger."""
        from data.live_data_fetcher import fetch_todays_games

        # ClearSports returns games but all have empty team names
        mock_cs.return_value = [
            {"game_id": "g1", "home_team": "", "away_team": ""},
            {"game_id": "g2", "home_team": "", "away_team": ""},
        ]

        games = fetch_todays_games()
        # Should use fallback since ClearSports games had no valid teams
        mock_build.assert_called_once()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")


if __name__ == "__main__":
    unittest.main()
