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


if __name__ == "__main__":
    unittest.main()
