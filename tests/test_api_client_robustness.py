"""
tests/test_api_client_robustness.py
-----------------------------------
Tests for API client robustness improvements:
  1. ApiNba: no duplicate apiKey in query params for game_log/standings/news
  2. ApiNba: 422 status code handled without retry
  3. ApiNba: empty response body handled without JSONDecodeError retry
  4. Odds API: empty response body handled without JSONDecodeError retry
  5. ApiNba: cascading .get() safe when nested record fields are None
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


_CS_SRC = pathlib.Path(__file__).parent.parent / "data" / "nba_api_client.py"
_OA_SRC = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"


# ── Section 1: ApiNba source-level checks ──────────────────────────────

class TestApiNbaNoApiKeyInParams(unittest.TestCase):
    """Verify that get_player_game_log, get_standings, and get_news
    do NOT put the apiKey into the query params dict.  The Bearer header in
    _request_with_retry already handles authentication."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_get_player_game_log_no_apikey_in_params(self):
        """params dict for game_log must not contain 'apiKey'."""
        idx = self.src.find("def get_player_game_log(")
        self.assertGreater(idx, 0)
        # Use a 1500-char window to reach past the docstring
        snippet = self.src[idx:idx + 1500]
        self.assertIn('"player"', snippet)
        self.assertNotIn('"apiKey"', snippet,
                         "get_player_game_log params must not include apiKey")

    def test_get_standings_no_apikey_in_params(self):
        """params dict for standings must not contain 'apiKey'."""
        idx = self.src.find("def get_standings(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertNotIn('"apiKey"', snippet,
                         "get_standings params must not include apiKey")

    def test_get_news_no_apikey_in_params(self):
        """params dict for news must not contain 'apiKey'."""
        idx = self.src.find("def get_news(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertIn('"limit"', snippet)
        self.assertNotIn('"apiKey"', snippet,
                         "get_news params must not include apiKey")


# ── Section 2: ApiNba 422 handling ──────────────────────────────────────

class TestApiNba422Handling(unittest.TestCase):
    """Verify that _request_with_retry in nba_api_client handles HTTP 422."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_422_status_code_handled(self):
        """_request_with_retry should check for 422 status."""
        self.assertIn("status_code == 422", self.src,
                      "ApiNba must handle 422 status code")

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

    def test_nba_api_checks_empty_body(self):
        """ApiNba _request_with_retry must check resp.text before .json()."""
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("not resp.text", src,
                      "ApiNba must check for empty resp.text")

    def test_odds_api_checks_empty_body(self):
        """Odds API _request_with_retry must check resp.text before .json()."""
        src = _OA_SRC.read_text(encoding="utf-8")
        self.assertIn("not resp.text", src,
                      "Odds API must check for empty resp.text")


# ── Section 4: Cascading .get() safety ───────────────────────────────────────

class TestCascadingGetSafety(unittest.TestCase):
    """Verify that nested .get() patterns in get_todays_games use 'or {}' to
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


# ── Section 5: Runtime test — ApiNba games parsing with None records ────

class TestApiNbaGameParsingEdgeCases(unittest.TestCase):
    """Runtime tests for get_todays_games parsing logic with edge-case data."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_games_with_none_records(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games with home_record: null should not cause AttributeError."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
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

        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_wins"], 0)
        self.assertEqual(games[0]["home_losses"], 0)
        self.assertEqual(games[0]["away_wins"], 0)
        self.assertEqual(games[0]["away_losses"], 0)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_games_with_nested_records(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games with nested home_record dicts should parse correctly."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
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

        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_wins"], 35)
        self.assertEqual(games[0]["home_losses"], 20)
        self.assertEqual(games[0]["away_wins"], 40)
        self.assertEqual(games[0]["away_losses"], 15)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_games_with_flat_wins_losses(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games with flat home_wins/home_losses fields should parse correctly."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
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

        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_wins"], 42)
        self.assertEqual(games[0]["home_losses"], 18)
        self.assertEqual(games[0]["away_wins"], 38)
        self.assertEqual(games[0]["away_losses"], 22)


# ── Section 6: Cache key includes params ─────────────────────────────────────

class TestCacheKeyIncludesParams(unittest.TestCase):
    """Verify that _build_cache_key builds unique keys for different params."""

    def test_build_cache_key_exists(self):
        """_build_cache_key function must exist in nba_api_client source."""
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("def _build_cache_key(", src)

    def test_build_cache_key_behavior(self):
        """Different params must produce different cache keys."""
        from data.nba_api_client import _build_cache_key

        key1 = _build_cache_key("https://example.com/games", {"date": "2026-03-23"})
        key2 = _build_cache_key("https://example.com/games", {"date": "2026-03-24"})
        key3 = _build_cache_key("https://example.com/games")

        self.assertNotEqual(key1, key2, "Different date params must produce different keys")
        self.assertNotEqual(key1, key3, "Params vs no params must produce different keys")

    def test_build_cache_key_no_params(self):
        """No params should return the URL as-is."""
        from data.nba_api_client import _build_cache_key

        self.assertEqual(_build_cache_key("https://example.com/games"), "https://example.com/games")


# ── Section 7: _extract_team_abbrev resilience ───────────────────────────────

class TestExtractTeamAbbrev(unittest.TestCase):
    """Verify _extract_team_abbrev handles multiple field naming conventions."""

    def test_direct_home_team_field(self):
        """home_team field should be extracted correctly."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_team": "LAL"}, "home")
        self.assertEqual(result, "LAL")

    def test_abbreviation_field(self):
        """home_abbreviation / away_abbreviation should work."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"away_abbreviation": "bos"}, "away")
        self.assertEqual(result, "BOS")

    def test_tricode_field(self):
        """home_tricode / away_tricode should work."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_tricode": "gsw"}, "home")
        self.assertEqual(result, "GSW")

    def test_team_abbreviation_field(self):
        """home_team_abbreviation / away_team_abbreviation should work."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"away_team_abbreviation": "MIA"}, "away")
        self.assertEqual(result, "MIA")

    def test_nested_dict(self):
        """Nested dict like home: {abbreviation: 'LAL'} should work."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home": {"abbreviation": "LAL"}}, "home")
        self.assertEqual(result, "LAL")

    def test_nested_team_dict(self):
        """Nested dict like home_team: {tricode: 'BOS'} should work."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_team": {"tricode": "BOS"}}, "home")
        self.assertEqual(result, "BOS")

    def test_empty_on_missing_fields(self):
        """Should return empty string when no matching fields found."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"unrelated": "data"}, "home")
        self.assertEqual(result, "")

    def test_empty_string_field_returns_empty(self):
        """Empty string in team field should return empty."""
        from data.nba_api_client import _extract_team_abbrev

        result = _extract_team_abbrev({"home_team": ""}, "home")
        self.assertEqual(result, "")


# ── Section 8: get_todays_games skips empty-team entries ────────────────────

class TestFetchGamesTodaySkipsEmptyTeams(unittest.TestCase):
    """Verify that games with empty team abbreviations are skipped."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_skips_games_with_empty_teams(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games missing team abbreviations should be skipped."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
            {"game_id": "g1", "home_team": "LAL", "away_team": "BOS", "vegas_spread": -3.5},
            {"game_id": "g2"},  # no team info at all
            {"game_id": "g3", "home_team": "MIA"},  # missing away_team
        ]

        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_alternate_field_names_work(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games with alternate field names (tricode, nested) should parse."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
            {"game_id": "g1", "home_tricode": "LAL", "away_tricode": "BOS", "vegas_spread": -2.0},
        ]

        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")
        self.assertEqual(games[0]["away_team"], "BOS")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_client_side_date_filter(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """When API returns >20 games, client-side date filter should apply."""
        from data.nba_api_client import get_todays_games, _today_str

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

        mock_request.return_value = all_games
        games = get_todays_games()
        self.assertEqual(len(games), 2)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_nested_team_objects(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games with nested team objects should parse correctly."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
            {
                "game_id": "g1",
                "home": {"abbreviation": "CHI"},
                "away": {"abbreviation": "CLE"},
                "vegas_spread": -1.0,
                "game_total": 210,
            }
        ]

        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "CHI")
        self.assertEqual(games[0]["away_team"], "CLE")


# ── Section 9: get_todays_games validates team names ───────────────────────

class TestFetchTodaysGamesValidation(unittest.TestCase):
    """Verify get_todays_games validates games have team names."""

    @patch("data.nba_data_service._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_predictions", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_nba_api_odds", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.nba_data_service._build_games_from_odds_api", return_value=[
        {"game_id": "fallback_1", "home_team": "LAL", "away_team": "BOS", "vegas_spread": -3.0, "game_total": 220}
    ])
    @patch("data.nba_api_client.get_todays_games")
    def test_falls_back_when_all_teams_empty(
        self, mock_cs, mock_build, mock_enrich_odds, mock_enrich_cs,
        mock_enrich_pred, mock_enrich_stand,
    ):
        """When ApiNba returns games with empty teams, fallback should trigger."""
        from data.nba_data_service import get_todays_games

        # ApiNba returns games but all have empty team names
        mock_cs.return_value = [
            {"game_id": "g1", "home_team": "", "away_team": ""},
            {"game_id": "g2", "home_team": "", "away_team": ""},
        ]

        games = get_todays_games()
        # Should use fallback since ApiNba games had no valid teams
        mock_build.assert_called_once()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")


# ── Section 10: Odds API cache key includes params ───────────────────────────

class TestOddsApiCacheKeyIncludesParams(unittest.TestCase):
    """Verify that the Odds API client builds cache keys including params."""

    def test_build_cache_key_exists(self):
        """_build_cache_key function must exist in odds_client source."""
        src = _OA_SRC.read_text(encoding="utf-8")
        self.assertIn("def _build_cache_key(", src)

    def test_build_cache_key_behavior(self):
        """Different params must produce different cache keys."""
        from data.odds_client import _build_cache_key

        key1 = _build_cache_key("https://api.example.com/odds", {"markets": "h2h", "regions": "us"})
        key2 = _build_cache_key("https://api.example.com/odds", {"markets": "player_points", "regions": "us2"})
        key3 = _build_cache_key("https://api.example.com/odds")

        self.assertNotEqual(key1, key2, "Different market params must produce different keys")
        self.assertNotEqual(key1, key3, "Params vs no params must produce different keys")

    def test_build_cache_key_excludes_api_key(self):
        """apiKey must NOT appear in the cache key (different users = same data)."""
        from data.odds_client import _build_cache_key

        key_a = _build_cache_key("https://api.example.com/odds", {"apiKey": "key1", "markets": "h2h"})
        key_b = _build_cache_key("https://api.example.com/odds", {"apiKey": "key2", "markets": "h2h"})

        self.assertEqual(key_a, key_b, "Different API keys should produce the same cache key")
        self.assertNotIn("key1", key_a, "apiKey value should not appear in cache key")

    def test_build_cache_key_no_params(self):
        """No params should return the URL as-is."""
        from data.odds_client import _build_cache_key

        self.assertEqual(
            _build_cache_key("https://api.example.com/odds"),
            "https://api.example.com/odds",
        )

    def test_request_with_retry_uses_cache_key(self):
        """_request_with_retry must use _build_cache_key, not raw url for caching."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def _request_with_retry(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1200]
        self.assertIn("_build_cache_key(", snippet,
                       "_request_with_retry must call _build_cache_key for cache keying")
        self.assertIn("cache_key", snippet,
                       "_request_with_retry must use cache_key variable")


# ── Section 11: Player Simulator safe float handling ─────────────────────────

class TestPlayerSimulatorGameContext(unittest.TestCase):
    """Verify _find_game_context handles None and invalid spread/total values."""

    def test_source_uses_safe_float_pattern(self):
        """_find_game_context must not use raw float() on game dict values."""
        src_path = pathlib.Path(__file__).parent.parent / "pages" / "5_🔮_Player_Simulator.py"
        src = src_path.read_text(encoding="utf-8")
        idx = src.find("def _find_game_context(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        # Must NOT have raw float(g.get("vegas_spread", ...)) without None check
        self.assertNotIn('float(g.get("vegas_spread', snippet,
                          "_find_game_context must use safe float conversion")
        self.assertNotIn('-float(g.get("vegas_spread', snippet,
                          "_find_game_context must not negate raw float(g.get(...))")

    def test_source_uses_none_check(self):
        """_find_game_context must check for None before float conversion."""
        src_path = pathlib.Path(__file__).parent.parent / "pages" / "5_🔮_Player_Simulator.py"
        src = src_path.read_text(encoding="utf-8")
        idx = src.find("def _find_game_context(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("is not None", snippet,
                       "_find_game_context must use 'is not None' pattern for safety")


# ── Section 12: Live Games page None-safe string slicing ─────────────────────

class TestLiveGamesNoneSafeSlicing(unittest.TestCase):
    """Verify game card rendering handles None in conference/streak fields."""

    def test_conference_field_none_safe(self):
        """home_conference .get() must use 'or' pattern to handle explicit None."""
        src_path = pathlib.Path(__file__).parent.parent / "pages" / "1_📡_Live_Games.py"
        src = src_path.read_text(encoding="utf-8")
        # The pattern (game.get("home_conference") or "")[:1] is safe
        # The pattern game.get("home_conference", "")[:1] is NOT safe when value is None
        self.assertIn('(game.get("home_conference") or "")[:1]', src,
                       "home_conference must use (x or '') pattern for None-safe slicing")
        self.assertIn('(game.get("away_conference") or "")[:1]', src,
                       "away_conference must use (x or '') pattern for None-safe slicing")

    def test_game_context_uses_safe_float(self):
        """Game context construction must use safe float (not 'or' falsy pattern)."""
        src_path = pathlib.Path(__file__).parent.parent / "pages" / "1_📡_Live_Games.py"
        src = src_path.read_text(encoding="utf-8")
        # Must NOT have: float(g.get("vegas_spread", 0) or 0)  (treats 0.0 as falsy)
        self.assertNotIn('float(g.get("vegas_spread", 0) or 0)', src,
                          "Must not use 'or 0' pattern which treats 0.0 as falsy")
        self.assertNotIn('float(g.get("game_total", 220) or 220)', src,
                          "Must not use 'or 220' pattern which treats 0 as falsy")


# ── Section 13: Odds API null-safe .get() patterns ───────────────────────────

class TestOddsApiNullSafeGet(unittest.TestCase):
    """Verify that the Odds API client uses 'or []' / 'or {}' instead of
    .get(key, []) / .get(key, {}) for nested API data that may be null."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_bookmakers_uses_or_pattern(self):
        """bookmakers access must use 'or []' pattern for null safety."""
        # Find all bookmaker accesses that use the unsafe .get("bookmakers", [])
        self.assertNotIn('.get("bookmakers", [])', self.src,
                         "bookmakers access must use (x or []) pattern, not .get(key, [])")

    def test_markets_list_uses_or_pattern(self):
        """markets list access in for-loops must use 'or []' for null safety."""
        # In get_game_odds and get_player_props, markets are iterated
        self.assertNotIn('bm.get("markets", [])', self.src,
                         "markets list access must use (x or []) pattern")

    def test_outcomes_uses_or_pattern(self):
        """outcomes access must use 'or []' for null safety."""
        self.assertNotIn('mkt.get("outcomes", [])', self.src,
                         "outcomes access must use (x or []) pattern")

    def test_markets_dict_uses_or_pattern(self):
        """markets dict access in get_consensus_odds must use 'or {}' for null safety."""
        self.assertNotIn('bm.get("markets", {})', self.src,
                         "markets dict access must use (x or {}) pattern")

    def test_spreads_uses_or_pattern(self):
        """spreads access must use 'or {}' for null safety."""
        self.assertNotIn('mkts.get("spreads", {})', self.src,
                         "spreads access must use (x or {}) pattern")

    def test_totals_uses_or_pattern(self):
        """totals access must use 'or {}' for null safety."""
        self.assertNotIn('mkts.get("totals", {})', self.src,
                         "totals access must use (x or {}) pattern")

    def test_h2h_uses_or_pattern(self):
        """h2h access must use 'or {}' for null safety."""
        self.assertNotIn('mkts.get("h2h", {})', self.src,
                         "h2h access must use (x or {}) pattern")


class TestOddsApiOutcomeTypeCheck(unittest.TestCase):
    """Verify that outcome dict comprehensions in get_game_odds guard
    against non-dict elements in the outcomes list."""

    def test_get_game_odds_checks_outcome_type(self):
        """get_game_odds outcome comprehension must check isinstance(o, dict)."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def get_game_odds(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 2500]
        self.assertIn("isinstance(o, dict)", snippet,
                       "outcomes comprehension must guard against non-dict elements")


# ── Section 14: Double-caching elimination ───────────────────────────────────

class TestDoubleCachingEliminated(unittest.TestCase):
    """Verify that functions with manual cache keys use _build_cache_key
    consistently so inner/outer cache keys match."""

    def test_get_recent_scores_uses_build_cache_key(self):
        """get_recent_scores must use _build_cache_key for its cache key."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def get_recent_scores(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 2000]
        self.assertIn("_build_cache_key(", snippet,
                       "get_recent_scores must use _build_cache_key")
        # Must NOT contain a manually-built cache_key string
        self.assertNotIn('f"{url}?daysFrom=', snippet,
                          "get_recent_scores must not use manual cache key string")

    def test_get_standings_uses_build_cache_key(self):
        """get_standings must use _build_cache_key for its cache key."""
        src = _CS_SRC.read_text(encoding="utf-8")
        idx = src.find("def get_standings(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("_build_cache_key(", snippet,
                       "get_standings must use _build_cache_key")
        self.assertNotIn('f"{url}?season=', snippet,
                          "get_standings must not use manual cache key string")

    def test_get_player_game_log_uses_build_cache_key(self):
        """get_player_game_log must use _build_cache_key for its cache key."""
        src = _CS_SRC.read_text(encoding="utf-8")
        idx = src.find("def get_player_game_log(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("_build_cache_key(", snippet,
                       "get_player_game_log must use _build_cache_key")
        self.assertNotIn('f"{url}?player_id=', snippet,
                          "get_player_game_log must not use manual cache key string")

    def test_get_news_uses_build_cache_key(self):
        """get_news must use _build_cache_key for its cache key."""
        src = _CS_SRC.read_text(encoding="utf-8")
        idx = src.find("def get_news(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("_build_cache_key(", snippet,
                       "get_news must use _build_cache_key")
        self.assertNotIn('f"{url}?limit=', snippet,
                          "get_news must not use manual cache key string")


# ── Section 15: sportsbook_service dead code removed ───────────────────────────

class TestPlatformFetcherDeadCodeRemoved(unittest.TestCase):
    """Verify that unused _cache_get / _cache_set dead code has been
    removed from sportsbook_service.py."""

    def setUp(self):
        self.src_path = pathlib.Path(__file__).parent.parent / "data" / "sportsbook_service.py"
        self.src = self.src_path.read_text(encoding="utf-8")

    def test_no_cache_get_function(self):
        """sportsbook_service must not define _cache_get (dead code removed)."""
        self.assertNotIn("def _cache_get(", self.src,
                          "_cache_get should be removed from sportsbook_service")

    def test_no_cache_set_function(self):
        """sportsbook_service must not define _cache_set (dead code removed)."""
        self.assertNotIn("def _cache_set(", self.src,
                          "_cache_set should be removed from sportsbook_service")

    def test_no_api_cache_dict(self):
        """sportsbook_service must not have unused _API_CACHE dict."""
        self.assertNotIn("_API_CACHE:", self.src,
                          "_API_CACHE should be removed from sportsbook_service")

    def test_no_api_cache_ttl(self):
        """sportsbook_service must not have unused _API_CACHE_TTL."""
        self.assertNotIn("_API_CACHE_TTL", self.src,
                          "_API_CACHE_TTL should be removed from sportsbook_service")


# ── Section 16: get_consensus_odds bookmaker type check ──────────────────────

class TestConsensusOddsBookmakerTypeCheck(unittest.TestCase):
    """Verify that get_consensus_odds checks isinstance(bm, dict) for
    each bookmaker entry to avoid crashes on unexpected data."""

    def test_bookmaker_type_checked(self):
        """get_consensus_odds must check isinstance(bm, dict) for bookmakers."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def get_consensus_odds(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 2500]
        self.assertIn("isinstance(bm, dict)", snippet,
                       "get_consensus_odds must type-check bookmaker entries")


# ── Section 17: ApiNba null-safe 'or' chain patterns ───────────────────

class TestApiNbaNullSafeOrChainPatterns(unittest.TestCase):
    """Verify that ApiNba endpoint functions use (x or y or []) instead
    of .get("key", .get("key2", [])) for extracting the top-level response
    data list from API response envelopes.

    The .get("key", default) pattern returns None when the key EXISTS with
    an explicit null value — only returns the default when the key is MISSING.
    The (x or y or []) pattern handles both cases correctly.

    NOTE: We only check the response-envelope extraction (e.g.
    ``raw.get("games") or raw.get("data") or []``).  Individual field-level
    nesting like ``g.get("date", g.get("game_date", ""))`` is safe because
    those values are wrapped in _safe_str/_safe_float helpers.
    """

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def _assert_no_envelope_nested_get(self, func_name: str, old_pattern: str):
        """Assert *func_name* does NOT contain the specified nested-get envelope pattern."""
        idx = self.src.find(f"def {func_name}(")
        self.assertGreater(idx, 0, f"Cannot find def {func_name}(")
        snippet = self.src[idx:idx + 2500]
        self.assertNotIn(
            old_pattern, snippet,
            f"{func_name} still uses unsafe nested .get() for response envelope extraction"
        )

    def test_get_todays_games_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_todays_games",
            'raw.get("games", raw.get("data"',
        )

    def test_get_player_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_player_stats",
            'raw.get("players", raw.get("data"',
        )

    def test_get_team_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_team_stats",
            'raw.get("teams", raw.get("data"',
        )

    def test_get_injury_report_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_injury_report",
            'raw.get("injuries", raw.get("data"',
        )

    def test_get_live_scores_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_live_scores",
            'raw.get("scores", raw.get("games"',
        )

    def test_get_rosters_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_rosters",
            'raw.get("roster", raw.get("players"',
        )

    def test_get_player_game_log_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_player_game_log",
            'data.get("games", data.get("data"',
        )

    def test_get_standings_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_standings",
            'data.get("standings", data.get("data"',
        )

    def test_get_news_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_news",
            'data.get("news", data.get("articles"',
        )

    def test_get_api_key_usage_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_api_key_usage",
            'raw.get("usage", raw.get("data"',
        )

    def test_get_game_odds_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_game_odds",
            'raw.get("odds", raw.get("data"',
        )

    def test_get_nba_team_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_nba_team_stats",
            'raw.get("stats", raw.get("data"',
        )

    def test_get_nba_player_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_nba_player_stats",
            'raw.get("stats", raw.get("data"',
        )

    def test_get_predictions_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "get_predictions",
            'raw.get("predictions", raw.get("data"',
        )


# ── Section 18: Runtime crash-safety with explicit null values ───────────────

class TestApiNbaExplicitNullCrashSafety(unittest.TestCase):
    """Runtime tests proving that get_player_game_log, get_standings,
    and get_news do NOT crash when the API returns an explicit null for
    the expected data key (e.g. {"games": null}).

    These three functions previously lacked the isinstance(list) guard that
    other endpoints had, making them vulnerable to TypeError crashes.
    """

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_get_player_game_log_null_games_key(self, mock_request, mock_key):
        """get_player_game_log must not crash when API returns {"games": null}."""
        from data.nba_api_client import get_player_game_log
        mock_request.return_value = {"games": None}
        result = get_player_game_log(player_id=123)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_get_player_game_log_null_data_key(self, mock_request, mock_key):
        """get_player_game_log must not crash when API returns {"data": null}."""
        from data.nba_api_client import get_player_game_log
        mock_request.return_value = {"data": None}
        result = get_player_game_log(player_id=123)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_get_standings_null_standings_key(self, mock_request, mock_key):
        """get_standings must not crash when API returns {"standings": null}."""
        from data.nba_api_client import get_standings
        mock_request.return_value = {"standings": None}
        result = get_standings()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_get_standings_null_data_key(self, mock_request, mock_key):
        """get_standings must not crash when API returns {"data": null}."""
        from data.nba_api_client import get_standings
        mock_request.return_value = {"data": None}
        result = get_standings()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_get_news_null_news_key(self, mock_request, mock_key):
        """get_news must not crash when API returns {"news": null}."""
        from data.nba_api_client import get_news
        mock_request.return_value = {"news": None}
        result = get_news()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_get_news_null_articles_key(self, mock_request, mock_key):
        """get_news must not crash when API returns {"articles": null}."""
        from data.nba_api_client import get_news
        mock_request.return_value = {"articles": None}
        result = get_news()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])


# ── Section 19: ApiNba _cache_get/_cache_set param name ─────────────────

class TestApiNbaCacheParamNaming(unittest.TestCase):
    """Verify that _cache_get and _cache_set use 'key' as the parameter name
    (not 'url') to match the Odds API convention and reflect actual usage."""

    def test_cache_get_param_named_key(self):
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("def _cache_get(key:", src,
                       "_cache_get parameter should be named 'key' not 'url'")

    def test_cache_set_param_named_key(self):
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("def _cache_set(key:", src,
                       "_cache_set parameter should be named 'key' not 'url'")


# ── Section 16: isinstance(dict) guard in iteration loops ─────────────────────

_LDF_SRC = pathlib.Path(__file__).parent.parent / "data" / "nba_data_service.py"


class TestIsinstanceDictGuardsSource(unittest.TestCase):
    """Verify that iteration loops over API list data include isinstance(item, dict)
    guards to prevent AttributeError when the list contains None or non-dict items.
    
    This is the defensive counterpart to the (x or []) envelope extraction pattern:
    even after extracting a list from the response, individual items may be null or
    non-dict types if the API returns heterogeneous data.
    """

    def setUp(self):
        self.cs_src = _CS_SRC.read_text(encoding="utf-8")
        self.ldf_src = _LDF_SRC.read_text(encoding="utf-8")

    def test_get_standings_has_isinstance_guard(self):
        """get_standings must check isinstance(row, dict) before row.get()."""
        idx = self.cs_src.find("def get_standings(")
        self.assertGreater(idx, 0)
        snippet = self.cs_src[idx:idx + 2000]
        self.assertIn("isinstance(row, dict)", snippet,
                      "get_standings must guard iteration with isinstance(row, dict)")

    def test_get_news_has_isinstance_guard(self):
        """get_news must check isinstance(item, dict) before item.get()."""
        idx = self.cs_src.find("def get_news(")
        self.assertGreater(idx, 0)
        snippet = self.cs_src[idx:idx + 2000]
        self.assertIn("isinstance(item, dict)", snippet,
                      "get_news must guard iteration with isinstance(item, dict)")

    def test_get_player_game_log_has_isinstance_guard(self):
        """get_player_game_log must check isinstance(g, dict) before g.get()."""
        idx = self.cs_src.find("def get_player_game_log(")
        self.assertGreater(idx, 0)
        snippet = self.cs_src[idx:idx + 2000]
        self.assertIn("isinstance(g, dict)", snippet,
                      "get_player_game_log must guard iteration with isinstance(g, dict)")

    def test_enrich_standings_has_isinstance_guard(self):
        """_enrich_games_with_standings dict comprehension must guard with isinstance(s, dict)."""
        idx = self.ldf_src.find("def _enrich_games_with_standings(")
        self.assertGreater(idx, 0)
        snippet = self.ldf_src[idx:idx + 1500]
        self.assertIn("isinstance(s, dict)", snippet,
                      "_enrich_games_with_standings must guard dict comprehension with isinstance(s, dict)")


class TestStandingsNonDictItemRuntime(unittest.TestCase):
    """Runtime test: get_standings must skip non-dict items without crashing."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_skips_none_items_in_standings_list(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """If the standings list contains None items, they should be skipped."""
        from data.nba_api_client import get_standings

        mock_request.return_value = {
            "standings": [
                None,
                {"team": "LAL", "wins": 45, "losses": 20},
                "not-a-dict",
                {"team": "BOS", "wins": 50, "losses": 15},
            ]
        }

        result = get_standings()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        abbrevs = {s["team_abbreviation"] for s in result}
        self.assertIn("LAL", abbrevs)
        self.assertIn("BOS", abbrevs)


class TestNewsNonDictItemRuntime(unittest.TestCase):
    """Runtime test: get_news must skip non-dict items without crashing."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_skips_none_items_in_news_list(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """If the news list contains None items, they should be skipped."""
        from data.nba_api_client import get_news

        mock_request.return_value = {
            "news": [
                None,
                {"title": "LeBron 40pts", "body": "Great game"},
                42,
                {"title": "Celtics win", "body": "Banner 19"},
            ]
        }

        result = get_news(limit=10)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "LeBron 40pts")
        self.assertEqual(result[1]["title"], "Celtics win")


class TestGameLogNonDictItemRuntime(unittest.TestCase):
    """Runtime test: get_player_game_log must skip non-dict items without crashing."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_skips_none_items_in_game_log_list(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """If the game log list contains None items, they should be skipped."""
        from data.nba_api_client import get_player_game_log

        mock_request.return_value = {
            "games": [
                None,
                {"date": "2026-03-20", "pts": 28, "reb": 7, "ast": 10},
                "garbage",
                {"date": "2026-03-18", "pts": 15, "reb": 3, "ast": 5},
            ]
        }

        result = get_player_game_log(player_id=12345, last_n_games=10)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0]["pts"], 28.0)
        self.assertAlmostEqual(result[1]["pts"], 15.0)


class TestEnrichStandingsNonDictItemRuntime(unittest.TestCase):
    """Runtime test: _enrich_games_with_standings must skip non-dict standings."""

    @patch("data.nba_api_client.get_standings")
    def test_skips_non_dict_standings_entries(self, mock_standings):
        """If standings list contains non-dict items, they should be skipped."""
        from data.nba_data_service import _enrich_games_with_standings

        mock_standings.return_value = [
            None,
            {"team_abbreviation": "LAL", "wins": 45, "losses": 20, "streak": "W3"},
            "not-a-dict",
            {"team_abbreviation": "BOS", "wins": 50, "losses": 15, "streak": "L1"},
        ]

        games = [
            {"game_id": "g1", "home_team": "LAL", "away_team": "BOS",
             "home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0},
        ]

        result = _enrich_games_with_standings(games)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["home_wins"], 45)
        self.assertEqual(result[0]["away_wins"], 50)


# ── Section: Non-NBA team filtering in get_todays_games ──────────────────────

class TestNonNbaTeamFiltering(unittest.TestCase):
    """Verify that non-NBA teams (All-Star, Rising Stars, TBD) are filtered out."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_non_nba_teams_filtered(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Games with non-NBA teams like STARS, STRIPES, TBD, WORLD should be excluded."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
            {"game_id": "real_1", "home_team": "LAL", "away_team": "BOS"},
            {"game_id": "allstar", "home_team": "STARS", "away_team": "STRIPES"},
            {"game_id": "real_2", "home_team": "MIA", "away_team": "NYK"},
            {"game_id": "tbd", "home_team": "TBD", "away_team": "TBD"},
            {"game_id": "rising", "home_team": "WORLD", "away_team": "USA"},
        ]

        games = get_todays_games()
        team_pairs = {(g["home_team"], g["away_team"]) for g in games}
        self.assertEqual(len(games), 2)
        self.assertIn(("LAL", "BOS"), team_pairs)
        self.assertIn(("MIA", "NYK"), team_pairs)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_common_aliases_accepted(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """Common NBA abbreviation aliases (GS, NY, SA, etc.) should be accepted."""
        from data.nba_api_client import get_todays_games

        mock_request.return_value = [
            {"game_id": "g1", "home_team": "GS", "away_team": "NY"},
            {"game_id": "g2", "home_team": "SA", "away_team": "NO"},
            {"game_id": "g3", "home_team": "UTAH", "away_team": "WSH"},
        ]

        games = get_todays_games()
        self.assertEqual(len(games), 3)


class TestExpandedDateFieldMatching(unittest.TestCase):
    """Verify that the date filter tries additional date field names."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_gameDate_field_matched(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """gameDate field should be recognized for date filtering."""
        from data.nba_api_client import get_todays_games, _today_str

        today = _today_str()
        all_games = []
        # Need >20 games to trigger client-side date filtering
        for i in range(23):
            all_games.append({
                "game_id": f"old_{i}", "home_team": "LAL", "away_team": "BOS",
                "gameDate": "2025-01-01",
            })
        all_games.append({
            "game_id": "today_1", "home_team": "MIA", "away_team": "CHI",
            "gameDate": today,
        })

        mock_request.return_value = all_games
        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "MIA")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._cache_get", return_value=None)
    @patch("data.nba_api_client._cache_set")
    @patch("data.nba_api_client._request_with_retry")
    def test_startDate_field_matched(self, mock_request, mock_cache_set, mock_cache_get, mock_key):
        """startDate field should be recognized for date filtering."""
        from data.nba_api_client import get_todays_games, _today_str

        today = _today_str()
        all_games = []
        # Need >20 games to trigger client-side date filtering
        for i in range(23):
            all_games.append({
                "game_id": f"old_{i}", "home_team": "LAL", "away_team": "BOS",
                "startDate": "2025-02-15",
            })
        all_games.append({
            "game_id": "today_1", "home_team": "PHX", "away_team": "DEN",
            "startDate": today,
        })

        mock_request.return_value = all_games
        games = get_todays_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "PHX")


class TestValidNbaAbbrevs(unittest.TestCase):
    """Verify the _VALID_NBA_ABBREVS set covers all 30 teams and aliases."""

    def test_contains_all_30_canonical(self):
        from data.nba_api_client import _VALID_NBA_ABBREVS
        canonical = {
            "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
            "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
            "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
        }
        self.assertTrue(canonical.issubset(_VALID_NBA_ABBREVS))

    def test_excludes_non_nba(self):
        from data.nba_api_client import _VALID_NBA_ABBREVS
        for fake in ("STARS", "STRIPES", "TBD", "WORLD", "USA", "TEAM"):
            self.assertNotIn(fake, _VALID_NBA_ABBREVS)

    def test_includes_common_aliases(self):
        from data.nba_api_client import _VALID_NBA_ABBREVS
        for alias in ("GS", "NY", "NO", "SA", "UTAH", "WSH"):
            self.assertIn(alias, _VALID_NBA_ABBREVS)


class TestNbaStatsFallbackTimeout(unittest.TestCase):
    """Verify that the NBA stats fallback timeout is reasonable."""

    def test_timeout_at_least_30(self):
        from data.nba_stats_backup import _REQUEST_TIMEOUT
        self.assertGreaterEqual(_REQUEST_TIMEOUT, 30)


if __name__ == "__main__":
    unittest.main()
