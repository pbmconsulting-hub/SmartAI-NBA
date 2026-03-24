"""
tests/test_odds_api_game_fallback.py
------------------------------------
Tests for the Odds API fallback in get_todays_games().

When ApiNba returns no games, the app should fall back to building
the game list from The Odds API's get_game_odds() data.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-mock streamlit before importing application modules
_mock_st = MagicMock()
_mock_st.cache_data = lambda *a, **kw: (lambda f: f)
sys.modules.setdefault("streamlit", _mock_st)
sys.modules.setdefault("streamlit.components", MagicMock())
sys.modules.setdefault("streamlit.components.v1", MagicMock())


# ── Sample Odds API responses for testing ────────────────────────────────────

SAMPLE_ODDS_API_GAMES = [
    {
        "game_id": "abc123",
        "home_team": "Los Angeles Lakers",
        "away_team": "Boston Celtics",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": {
                    "spreads": {"Los Angeles Lakers": -3.5, "Boston Celtics": 3.5},
                    "totals": {"Over": 224.5, "Under": 224.5},
                    "h2h": {"Los Angeles Lakers": -150, "Boston Celtics": 130},
                },
            },
            {
                "key": "fanduel",
                "markets": {
                    "spreads": {"Los Angeles Lakers": -4.0, "Boston Celtics": 4.0},
                    "totals": {"Over": 225.0, "Under": 225.0},
                    "h2h": {"Los Angeles Lakers": -155, "Boston Celtics": 135},
                },
            },
        ],
    },
    {
        "game_id": "def456",
        "home_team": "Golden State Warriors",
        "away_team": "Miami Heat",
        "bookmakers": [
            {
                "key": "betmgm",
                "markets": {
                    "spreads": {"Golden State Warriors": -6.0, "Miami Heat": 6.0},
                    "totals": {"Over": 218.0, "Under": 218.0},
                    "h2h": {"Golden State Warriors": -240, "Miami Heat": 200},
                },
            },
        ],
    },
]


class TestBuildGamesFromOddsApi(unittest.TestCase):
    """Test _build_games_from_odds_api() helper function."""

    def setUp(self):
        from data.nba_data_service import _build_games_from_odds_api
        self.fn = _build_games_from_odds_api

    @patch("data.odds_client.get_game_odds", return_value=SAMPLE_ODDS_API_GAMES)
    def test_returns_games_with_abbreviations(self, mock_odds):
        """Odds API full team names should be converted to abbreviations."""
        games = self.fn()
        self.assertEqual(len(games), 2)
        # First game: LAL vs BOS
        self.assertEqual(games[0]["home_team"], "LAL")
        self.assertEqual(games[0]["away_team"], "BOS")
        # Second game: GSW vs MIA
        self.assertEqual(games[1]["home_team"], "GSW")
        self.assertEqual(games[1]["away_team"], "MIA")

    @patch("data.odds_client.get_game_odds", return_value=SAMPLE_ODDS_API_GAMES)
    def test_returns_consensus_fields(self, mock_odds):
        """Games should include consensus spread, total, and moneyline."""
        games = self.fn()
        self.assertTrue(len(games) > 0)
        game = games[0]  # LAL vs BOS
        # Consensus spread should be median of -3.5 and -4.0 = -3.75
        self.assertIsNotNone(game.get("consensus_spread"))
        self.assertIsNotNone(game.get("consensus_total"))
        self.assertIn("vegas_spread", game)
        self.assertIn("game_total", game)
        self.assertIn("moneyline_home", game)
        self.assertIn("moneyline_away", game)
        self.assertIn("bookmaker_count", game)

    @patch("data.odds_client.get_game_odds", return_value=SAMPLE_ODDS_API_GAMES)
    def test_game_format_matches_clearsports(self, mock_odds):
        """Game dicts must have all keys that ApiNba would provide."""
        games = self.fn()
        required_keys = [
            "game_id", "home_team", "away_team",
            "home_wins", "home_losses", "away_wins", "away_losses",
            "vegas_spread", "game_total",
        ]
        for game in games:
            for key in required_keys:
                self.assertIn(key, game, f"Missing required key: {key}")

    @patch("data.odds_client.get_game_odds", return_value=[])
    def test_returns_empty_when_no_odds(self, mock_odds):
        """Should return empty list when Odds API returns no games."""
        games = self.fn()
        self.assertEqual(games, [])

    @patch("data.odds_client.get_game_odds", side_effect=Exception("API Error"))
    def test_returns_empty_on_exception(self, mock_odds):
        """Should return empty list on exception (graceful degradation)."""
        games = self.fn()
        self.assertEqual(games, [])

    @patch("data.odds_client.get_game_odds", return_value=[
        {
            "game_id": "xyz",
            "home_team": "Unknown Team A",
            "away_team": "Unknown Team B",
            "bookmakers": [],
        }
    ])
    def test_skips_unrecognised_teams(self, mock_odds):
        """Games with unrecognised team names should be skipped."""
        games = self.fn()
        self.assertEqual(len(games), 0)

    @patch("data.odds_client.get_game_odds", return_value=SAMPLE_ODDS_API_GAMES)
    def test_wins_losses_default_to_zero(self, mock_odds):
        """Wins/losses should default to 0 (no standings from Odds API)."""
        games = self.fn()
        for game in games:
            self.assertEqual(game["home_wins"], 0)
            self.assertEqual(game["home_losses"], 0)
            self.assertEqual(game["away_wins"], 0)
            self.assertEqual(game["away_losses"], 0)


class TestFetchTodaysGamesFallback(unittest.TestCase):
    """Test that get_todays_games() falls back to Odds API when ApiNba fails."""

    def setUp(self):
        from data.nba_data_service import get_todays_games
        self.fn = get_todays_games

    @patch("data.nba_data_service._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.nba_data_service._build_games_from_odds_api")
    @patch("data.nba_api_client.get_todays_games", return_value=[])
    def test_fallback_called_when_clearsports_empty(
        self, mock_cs, mock_build, mock_enrich_odds, mock_enrich_standings
    ):
        """When ApiNba returns [], the Odds API fallback should be invoked."""
        mock_build.return_value = [
            {"home_team": "LAL", "away_team": "BOS", "game_id": "1",
             "home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0,
             "vegas_spread": -3.5, "game_total": 224.5},
        ]
        games = self.fn()
        mock_build.assert_called_once()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_team"], "LAL")

    @patch("data.nba_data_service._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.nba_data_service._build_games_from_odds_api")
    @patch("data.nba_api_client.get_todays_games")
    def test_fallback_not_called_when_clearsports_succeeds(
        self, mock_cs, mock_build, mock_enrich_odds, mock_enrich_standings
    ):
        """When ApiNba returns games, Odds API fallback should NOT be called."""
        mock_cs.return_value = [
            {"home_team": "LAL", "away_team": "BOS", "game_id": "1",
             "home_wins": 40, "home_losses": 20, "away_wins": 38, "away_losses": 22,
             "vegas_spread": -2.0, "game_total": 222.0},
        ]
        games = self.fn()
        mock_build.assert_not_called()
        self.assertEqual(len(games), 1)

    @patch("data.nba_data_service._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.nba_data_service._build_games_from_odds_api", return_value=[])
    @patch("data.nba_api_client.get_todays_games", side_effect=Exception("Network error"))
    def test_returns_empty_when_both_fail(
        self, mock_cs, mock_build, mock_enrich_odds, mock_enrich_standings
    ):
        """When both ApiNba and Odds API fail, return empty list."""
        games = self.fn()
        self.assertEqual(games, [])


if __name__ == "__main__":
    unittest.main()
