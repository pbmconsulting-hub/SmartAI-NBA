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


# ── Section 10: Odds API cache key includes params ───────────────────────────

class TestOddsApiCacheKeyIncludesParams(unittest.TestCase):
    """Verify that the Odds API client builds cache keys including params."""

    def test_build_cache_key_exists(self):
        """_build_cache_key function must exist in odds_api_client source."""
        src = _OA_SRC.read_text(encoding="utf-8")
        self.assertIn("def _build_cache_key(", src)

    def test_build_cache_key_behavior(self):
        """Different params must produce different cache keys."""
        from data.odds_api_client import _build_cache_key

        key1 = _build_cache_key("https://api.example.com/odds", {"markets": "h2h", "regions": "us"})
        key2 = _build_cache_key("https://api.example.com/odds", {"markets": "player_points", "regions": "us2"})
        key3 = _build_cache_key("https://api.example.com/odds")

        self.assertNotEqual(key1, key2, "Different market params must produce different keys")
        self.assertNotEqual(key1, key3, "Params vs no params must produce different keys")

    def test_build_cache_key_excludes_api_key(self):
        """apiKey must NOT appear in the cache key (different users = same data)."""
        from data.odds_api_client import _build_cache_key

        key_a = _build_cache_key("https://api.example.com/odds", {"apiKey": "key1", "markets": "h2h"})
        key_b = _build_cache_key("https://api.example.com/odds", {"apiKey": "key2", "markets": "h2h"})

        self.assertEqual(key_a, key_b, "Different API keys should produce the same cache key")
        self.assertNotIn("key1", key_a, "apiKey value should not appear in cache key")

    def test_build_cache_key_no_params(self):
        """No params should return the URL as-is."""
        from data.odds_api_client import _build_cache_key

        self.assertEqual(
            _build_cache_key("https://api.example.com/odds"),
            "https://api.example.com/odds",
        )

    def test_fetch_with_retry_uses_cache_key(self):
        """_fetch_with_retry must use _build_cache_key, not raw url for caching."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def _fetch_with_retry(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1200]
        self.assertIn("_build_cache_key(", snippet,
                       "_fetch_with_retry must call _build_cache_key for cache keying")
        self.assertIn("cache_key", snippet,
                       "_fetch_with_retry must use cache_key variable")


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
        # In fetch_game_odds and fetch_player_props, markets are iterated
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
    """Verify that outcome dict comprehensions in fetch_game_odds guard
    against non-dict elements in the outcomes list."""

    def test_fetch_game_odds_checks_outcome_type(self):
        """fetch_game_odds outcome comprehension must check isinstance(o, dict)."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def fetch_game_odds(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 2500]
        self.assertIn("isinstance(o, dict)", snippet,
                       "outcomes comprehension must guard against non-dict elements")


# ── Section 14: Double-caching elimination ───────────────────────────────────

class TestDoubleCachingEliminated(unittest.TestCase):
    """Verify that functions with manual cache keys use _build_cache_key
    consistently so inner/outer cache keys match."""

    def test_fetch_recent_scores_uses_build_cache_key(self):
        """fetch_recent_scores must use _build_cache_key for its cache key."""
        src = _OA_SRC.read_text(encoding="utf-8")
        idx = src.find("def fetch_recent_scores(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 2000]
        self.assertIn("_build_cache_key(", snippet,
                       "fetch_recent_scores must use _build_cache_key")
        # Must NOT contain a manually-built cache_key string
        self.assertNotIn('f"{url}?daysFrom=', snippet,
                          "fetch_recent_scores must not use manual cache key string")

    def test_fetch_standings_uses_build_cache_key(self):
        """fetch_standings must use _build_cache_key for its cache key."""
        src = _CS_SRC.read_text(encoding="utf-8")
        idx = src.find("def fetch_standings(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("_build_cache_key(", snippet,
                       "fetch_standings must use _build_cache_key")
        self.assertNotIn('f"{url}?season=', snippet,
                          "fetch_standings must not use manual cache key string")

    def test_fetch_player_game_log_uses_build_cache_key(self):
        """fetch_player_game_log must use _build_cache_key for its cache key."""
        src = _CS_SRC.read_text(encoding="utf-8")
        idx = src.find("def fetch_player_game_log(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("_build_cache_key(", snippet,
                       "fetch_player_game_log must use _build_cache_key")
        self.assertNotIn('f"{url}?player_id=', snippet,
                          "fetch_player_game_log must not use manual cache key string")

    def test_fetch_news_uses_build_cache_key(self):
        """fetch_news must use _build_cache_key for its cache key."""
        src = _CS_SRC.read_text(encoding="utf-8")
        idx = src.find("def fetch_news(")
        self.assertGreater(idx, 0)
        snippet = src[idx:idx + 1500]
        self.assertIn("_build_cache_key(", snippet,
                       "fetch_news must use _build_cache_key")
        self.assertNotIn('f"{url}?limit=', snippet,
                          "fetch_news must not use manual cache key string")


# ── Section 15: platform_fetcher dead code removed ───────────────────────────

class TestPlatformFetcherDeadCodeRemoved(unittest.TestCase):
    """Verify that unused _cache_get / _cache_set dead code has been
    removed from platform_fetcher.py."""

    def setUp(self):
        self.src_path = pathlib.Path(__file__).parent.parent / "data" / "platform_fetcher.py"
        self.src = self.src_path.read_text(encoding="utf-8")

    def test_no_cache_get_function(self):
        """platform_fetcher must not define _cache_get (dead code removed)."""
        self.assertNotIn("def _cache_get(", self.src,
                          "_cache_get should be removed from platform_fetcher")

    def test_no_cache_set_function(self):
        """platform_fetcher must not define _cache_set (dead code removed)."""
        self.assertNotIn("def _cache_set(", self.src,
                          "_cache_set should be removed from platform_fetcher")

    def test_no_api_cache_dict(self):
        """platform_fetcher must not have unused _API_CACHE dict."""
        self.assertNotIn("_API_CACHE:", self.src,
                          "_API_CACHE should be removed from platform_fetcher")

    def test_no_api_cache_ttl(self):
        """platform_fetcher must not have unused _API_CACHE_TTL."""
        self.assertNotIn("_API_CACHE_TTL", self.src,
                          "_API_CACHE_TTL should be removed from platform_fetcher")


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


# ── Section 17: ClearSports null-safe 'or' chain patterns ───────────────────

class TestClearSportsNullSafeOrChainPatterns(unittest.TestCase):
    """Verify that ClearSports endpoint functions use (x or y or []) instead
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

    def test_fetch_games_today_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_games_today",
            'raw.get("games", raw.get("data"',
        )

    def test_fetch_player_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_player_stats",
            'raw.get("players", raw.get("data"',
        )

    def test_fetch_team_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_team_stats",
            'raw.get("teams", raw.get("data"',
        )

    def test_fetch_injury_report_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_injury_report",
            'raw.get("injuries", raw.get("data"',
        )

    def test_fetch_live_scores_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_live_scores",
            'raw.get("scores", raw.get("games"',
        )

    def test_fetch_rosters_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_rosters",
            'raw.get("roster", raw.get("players"',
        )

    def test_fetch_player_game_log_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_player_game_log",
            'data.get("games", data.get("data"',
        )

    def test_fetch_standings_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_standings",
            'data.get("standings", data.get("data"',
        )

    def test_fetch_news_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_news",
            'data.get("news", data.get("articles"',
        )

    def test_fetch_api_key_usage_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_api_key_usage",
            'raw.get("usage", raw.get("data"',
        )

    def test_fetch_game_odds_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_game_odds",
            'raw.get("odds", raw.get("data"',
        )

    def test_fetch_nba_team_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_nba_team_stats",
            'raw.get("stats", raw.get("data"',
        )

    def test_fetch_nba_player_stats_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_nba_player_stats",
            'raw.get("stats", raw.get("data"',
        )

    def test_fetch_predictions_uses_or_chain(self):
        self._assert_no_envelope_nested_get(
            "fetch_predictions",
            'raw.get("predictions", raw.get("data"',
        )


# ── Section 18: Runtime crash-safety with explicit null values ───────────────

class TestClearSportsExplicitNullCrashSafety(unittest.TestCase):
    """Runtime tests proving that fetch_player_game_log, fetch_standings,
    and fetch_news do NOT crash when the API returns an explicit null for
    the expected data key (e.g. {"games": null}).

    These three functions previously lacked the isinstance(list) guard that
    other endpoints had, making them vulnerable to TypeError crashes.
    """

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_fetch_player_game_log_null_games_key(self, mock_fetch, mock_key):
        """fetch_player_game_log must not crash when API returns {"games": null}."""
        from data.clearsports_client import fetch_player_game_log
        mock_fetch.return_value = {"games": None}
        result = fetch_player_game_log(player_id=123)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_fetch_player_game_log_null_data_key(self, mock_fetch, mock_key):
        """fetch_player_game_log must not crash when API returns {"data": null}."""
        from data.clearsports_client import fetch_player_game_log
        mock_fetch.return_value = {"data": None}
        result = fetch_player_game_log(player_id=123)
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_fetch_standings_null_standings_key(self, mock_fetch, mock_key):
        """fetch_standings must not crash when API returns {"standings": null}."""
        from data.clearsports_client import fetch_standings
        mock_fetch.return_value = {"standings": None}
        result = fetch_standings()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_fetch_standings_null_data_key(self, mock_fetch, mock_key):
        """fetch_standings must not crash when API returns {"data": null}."""
        from data.clearsports_client import fetch_standings
        mock_fetch.return_value = {"data": None}
        result = fetch_standings()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_fetch_news_null_news_key(self, mock_fetch, mock_key):
        """fetch_news must not crash when API returns {"news": null}."""
        from data.clearsports_client import fetch_news
        mock_fetch.return_value = {"news": None}
        result = fetch_news()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_fetch_news_null_articles_key(self, mock_fetch, mock_key):
        """fetch_news must not crash when API returns {"articles": null}."""
        from data.clearsports_client import fetch_news
        mock_fetch.return_value = {"articles": None}
        result = fetch_news()
        self.assertIsInstance(result, list)
        self.assertEqual(result, [])


# ── Section 19: ClearSports _cache_get/_cache_set param name ─────────────────

class TestClearSportsCacheParamNaming(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
