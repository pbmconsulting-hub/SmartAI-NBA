"""
tests/test_odds_historical_wiring.py
-------------------------------------
Tests for the odds and historical data endpoint wiring:
  1. _enrich_games_with_nba_api_odds fills missing odds from NBA API
  2. _enrich_games_with_predictions adds ApiNba predictions to games
  3. get_todays_games calls new enrichment functions
  4. refresh_historical_data_for_tonight retrieves ApiNba player stats
  5. get_all_todays_data stores ApiNba odds/predictions in session state
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call

# Add repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-mock streamlit before importing application modules
_mock_st = MagicMock()
_mock_st.cache_data = lambda *a, **kw: (lambda f: f)
_mock_st.session_state = {}
_mock_st.secrets = {}
sys.modules.setdefault("streamlit", _mock_st)
sys.modules.setdefault("streamlit.components", MagicMock())
sys.modules.setdefault("streamlit.components.v1", MagicMock())


# ── Sample test data ─────────────────────────────────────────────────────────

SAMPLE_GAMES = [
    {
        "game_id": "g1",
        "home_team": "LAL",
        "away_team": "BOS",
        "vegas_spread": 0,
        "game_total": 220,
        "bookmaker_count": 0,
    },
    {
        "game_id": "g2",
        "home_team": "GSW",
        "away_team": "MIA",
        "vegas_spread": -5.0,
        "game_total": 225.5,
        "bookmaker_count": 3,
    },
]

SAMPLE_CS_ODDS = [
    {
        "game_id": "g1",
        "spread": -3.5,
        "total": 218.0,
    },
    {
        "game_id": "g3",
        "spread": -1.0,
        "total": 210.0,
    },
]

SAMPLE_CS_PREDICTIONS = [
    {
        "game_id": "g1",
        "predicted_winner": "LAL",
        "predicted_spread": -4.0,
        "predicted_total": 219.5,
        "win_probability": 0.62,
    },
    {
        "game_id": "g2",
        "predicted_winner": "GSW",
        "predicted_spread": -5.5,
        "predicted_total": 224.0,
        "win_probability": 0.71,
    },
]


# ── Section 1: _enrich_games_with_nba_api_odds ───────────────────────────

class TestEnrichWithApiNbaOdds(unittest.TestCase):
    """Test that ApiNba odds fill in missing game-level odds."""

    def setUp(self):
        from data.nba_data_service import _enrich_games_with_nba_api_odds
        self.fn = _enrich_games_with_nba_api_odds

    @patch("data.nba_api_client.get_game_odds", return_value=SAMPLE_CS_ODDS)
    def test_fills_missing_spread_and_total(self, mock_cs_odds):
        """When Odds API left spread=0 and total=220, ApiNba should fill them."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)

        # Game g1 had spread=0, total=220 — should be filled from ApiNba
        self.assertAlmostEqual(result[0]["vegas_spread"], -3.5)
        self.assertAlmostEqual(result[0]["game_total"], 218.0)

    @patch("data.nba_api_client.get_game_odds", return_value=SAMPLE_CS_ODDS)
    def test_does_not_overwrite_existing_odds(self, mock_cs_odds):
        """When Odds API already set non-zero odds, ApiNba should NOT overwrite."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)

        # Game g2 already had spread=-5.0, total=225.5 — should remain unchanged
        self.assertAlmostEqual(result[1]["vegas_spread"], -5.0)
        self.assertAlmostEqual(result[1]["game_total"], 225.5)

    @patch("data.nba_api_client.get_game_odds", return_value=[])
    def test_returns_unchanged_when_no_cs_odds(self, mock_cs_odds):
        """When ApiNba returns no odds, games should be unchanged."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)
        self.assertEqual(result[0]["vegas_spread"], 0)
        self.assertEqual(result[0]["game_total"], 220)

    @patch("data.nba_api_client.get_game_odds", side_effect=Exception("API error"))
    def test_returns_unchanged_on_exception(self, mock_cs_odds):
        """On exception, the original games list should be returned unchanged."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)
        self.assertEqual(result[0]["vegas_spread"], 0)

    def test_returns_empty_for_empty_input(self):
        """Empty input should return empty output."""
        result = self.fn([])
        self.assertEqual(result, [])


# ── Section 2: _enrich_games_with_predictions ─────────────────────────────────

class TestEnrichWithPredictions(unittest.TestCase):
    """Test that ApiNba predictions are added to game dicts."""

    def setUp(self):
        from data.nba_data_service import _enrich_games_with_predictions
        self.fn = _enrich_games_with_predictions

    @patch("data.nba_api_client.get_predictions", return_value=SAMPLE_CS_PREDICTIONS)
    def test_adds_prediction_fields(self, mock_preds):
        """Prediction fields should be added to matching games."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)

        self.assertEqual(result[0]["cs_predicted_winner"], "LAL")
        self.assertAlmostEqual(result[0]["cs_predicted_spread"], -4.0)
        self.assertAlmostEqual(result[0]["cs_predicted_total"], 219.5)
        self.assertAlmostEqual(result[0]["cs_win_probability"], 0.62)

    @patch("data.nba_api_client.get_predictions", return_value=SAMPLE_CS_PREDICTIONS)
    def test_enriches_all_matching_games(self, mock_preds):
        """All games with matching IDs should be enriched."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)

        self.assertEqual(result[1]["cs_predicted_winner"], "GSW")
        self.assertAlmostEqual(result[1]["cs_win_probability"], 0.71)

    @patch("data.nba_api_client.get_predictions", return_value=[])
    def test_returns_unchanged_when_no_predictions(self, mock_preds):
        """When no predictions available, games should be unchanged."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)
        self.assertNotIn("cs_predicted_winner", result[0])

    @patch("data.nba_api_client.get_predictions", side_effect=Exception("API down"))
    def test_returns_unchanged_on_exception(self, mock_preds):
        """On exception, games should be returned unchanged."""
        import copy
        games = copy.deepcopy(SAMPLE_GAMES)
        result = self.fn(games)
        self.assertNotIn("cs_predicted_winner", result[0])

    def test_returns_empty_for_empty_input(self):
        """Empty input should return empty output."""
        result = self.fn([])
        self.assertEqual(result, [])


# ── Section 3: get_todays_games calls new enrichment ───────────────────────

class TestFetchTodaysGamesNewEnrichment(unittest.TestCase):
    """Verify get_todays_games calls the new enrichment functions."""

    def setUp(self):
        from data.nba_data_service import get_todays_games
        self.fn = get_todays_games

    @patch("data.nba_data_service._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_predictions", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_nba_api_odds", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.nba_api_client.get_todays_games")
    def test_calls_nba_api_odds_enrichment(
        self, mock_cs, mock_odds, mock_cs_odds, mock_preds, mock_standings
    ):
        """get_todays_games should call _enrich_games_with_nba_api_odds."""
        mock_cs.return_value = SAMPLE_GAMES
        self.fn()
        mock_cs_odds.assert_called_once()

    @patch("data.nba_data_service._enrich_games_with_standings", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_predictions", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_nba_api_odds", side_effect=lambda g: g)
    @patch("data.nba_data_service._enrich_games_with_odds_api", side_effect=lambda g: g)
    @patch("data.nba_api_client.get_todays_games")
    def test_calls_predictions_enrichment(
        self, mock_cs, mock_odds, mock_cs_odds, mock_preds, mock_standings
    ):
        """get_todays_games should call _enrich_games_with_predictions."""
        mock_cs.return_value = SAMPLE_GAMES
        self.fn()
        mock_preds.assert_called_once()


# ── Section 4: refresh_historical_data_for_tonight retrieves CS player stats ───

class TestHistoricalDataRefresherWiring(unittest.TestCase):
    """Verify refresh_historical_data_for_tonight uses new endpoints."""

    @patch("data.odds_client.get_recent_scores", return_value=[
        {"game_id": "s1", "home_team": "LAL", "away_team": "BOS", "completed": True,
         "home_score": 110, "away_score": 105, "commence_time": "2025-01-01"}
    ])
    @patch("data.nba_api_client.get_nba_player_stats", return_value=[
        {"player_id": 1, "player_name": "Test Player", "pts": 25}
    ])
    @patch("engine.clv_tracker.auto_update_closing_lines", return_value={"updated": 0})
    @patch("data.nba_api_client.get_season_game_logs_batch", return_value={})
    @patch("data.game_log_cache.save_game_logs_to_cache")
    @patch("data.data_manager.load_players_data", return_value=[
        {"name": "Test Player", "team": "LAL", "player_id": 1}
    ])
    def test_retrieves_cs_player_stats(
        self, mock_load, mock_save, mock_batch, mock_clv,
        mock_cs_pstats, mock_scores
    ):
        """Historical refresh should retrieve ApiNba player stats."""
        from data.nba_data_service import refresh_historical_data_for_tonight
        result = refresh_historical_data_for_tonight(
            games=[{"home_team": "LAL", "away_team": "BOS"}]
        )
        mock_cs_pstats.assert_called_once()
        self.assertEqual(result.get("cs_player_stats_count"), 1)

    @patch("data.odds_client.get_recent_scores", return_value=[
        {"game_id": "s1", "home_team": "LAL", "away_team": "BOS", "completed": True,
         "home_score": 110, "away_score": 105, "commence_time": "2025-01-01"}
    ])
    @patch("data.nba_api_client.get_nba_player_stats", return_value=[])
    @patch("engine.clv_tracker.auto_update_closing_lines", return_value={"updated": 0})
    @patch("data.nba_api_client.get_season_game_logs_batch", return_value={})
    @patch("data.game_log_cache.save_game_logs_to_cache")
    @patch("data.data_manager.load_players_data", return_value=[
        {"name": "Test Player", "team": "LAL", "player_id": 1}
    ])
    def test_retrieves_recent_scores(
        self, mock_load, mock_save, mock_batch, mock_clv,
        mock_cs_pstats, mock_scores
    ):
        """Historical refresh should retrieve Odds API recent scores."""
        from data.nba_data_service import refresh_historical_data_for_tonight
        result = refresh_historical_data_for_tonight(
            games=[{"home_team": "LAL", "away_team": "BOS"}]
        )
        mock_scores.assert_called_once_with(days_from=1)
        self.assertEqual(result.get("recent_scores_count"), 1)


# ── Section 5: get_all_todays_data stores odds/predictions ─────────────────

class TestFetchAllTodaysDataStoresOdds(unittest.TestCase):
    """Verify get_all_todays_data stores ApiNba odds/predictions."""

    @patch("data.nba_data_service.get_player_news", return_value=[])
    @patch("data.nba_data_service.get_standings", return_value=[])
    @patch("data.nba_data_service.refresh_historical_data_for_tonight", return_value={})
    @patch("data.nba_data_service._record_odds_api_snapshots")
    @patch("data.nba_data_service.get_team_stats", return_value=True)
    @patch("data.nba_data_service.get_todays_players", return_value=True)
    @patch("data.nba_data_service.get_todays_games")
    @patch("data.nba_api_client.get_predictions", return_value=SAMPLE_CS_PREDICTIONS)
    @patch("data.nba_api_client.get_game_odds", return_value=SAMPLE_CS_ODDS)
    def test_stores_cs_odds_in_results(
        self, mock_cs_odds, mock_preds, mock_games, mock_players,
        mock_teams, mock_snapshots, mock_hist, mock_standings, mock_news
    ):
        """get_all_todays_data should include cs_game_odds in results."""
        mock_games.return_value = SAMPLE_GAMES
        from data.nba_data_service import get_all_todays_data
        result = get_all_todays_data()
        self.assertIn("cs_game_odds", result)
        self.assertEqual(len(result["cs_game_odds"]), 2)

    @patch("data.nba_data_service.get_player_news", return_value=[])
    @patch("data.nba_data_service.get_standings", return_value=[])
    @patch("data.nba_data_service.refresh_historical_data_for_tonight", return_value={})
    @patch("data.nba_data_service._record_odds_api_snapshots")
    @patch("data.nba_data_service.get_team_stats", return_value=True)
    @patch("data.nba_data_service.get_todays_players", return_value=True)
    @patch("data.nba_data_service.get_todays_games")
    @patch("data.nba_api_client.get_predictions", return_value=SAMPLE_CS_PREDICTIONS)
    @patch("data.nba_api_client.get_game_odds", return_value=SAMPLE_CS_ODDS)
    def test_stores_cs_predictions_in_results(
        self, mock_cs_odds, mock_preds, mock_games, mock_players,
        mock_teams, mock_snapshots, mock_hist, mock_standings, mock_news
    ):
        """get_all_todays_data should include cs_predictions in results."""
        mock_games.return_value = SAMPLE_GAMES
        from data.nba_data_service import get_all_todays_data
        result = get_all_todays_data()
        self.assertIn("cs_predictions", result)
        self.assertEqual(len(result["cs_predictions"]), 2)


# ── Section 6: Source-level validation ────────────────────────────────────────

class TestOddsWiringSourceLevel(unittest.TestCase):
    """Source-level checks that wiring code exists in nba_data_service.py."""

    def setUp(self):
        import pathlib
        self.src = (
            pathlib.Path(__file__).parent.parent / "data" / "nba_data_service.py"
        ).read_text(encoding="utf-8")

    def test_nba_api_odds_enrichment_exists(self):
        """_enrich_games_with_nba_api_odds function must exist."""
        self.assertIn("def _enrich_games_with_nba_api_odds(", self.src)

    def test_predictions_enrichment_exists(self):
        """_enrich_games_with_predictions function must exist."""
        self.assertIn("def _enrich_games_with_predictions(", self.src)

    def test_get_todays_games_calls_cs_odds(self):
        """get_todays_games must call _enrich_games_with_nba_api_odds."""
        idx = self.src.find("def get_todays_games(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn("_enrich_games_with_nba_api_odds", snippet)

    def test_get_todays_games_calls_predictions(self):
        """get_todays_games must call _enrich_games_with_predictions."""
        idx = self.src.find("def get_todays_games(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn("_enrich_games_with_predictions", snippet)

    def test_historical_refresher_uses_cs_player_stats(self):
        """refresh_historical_data_for_tonight must reference get_nba_player_stats."""
        idx = self.src.find("def refresh_historical_data_for_tonight(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 5000]
        self.assertIn("get_nba_player_stats", snippet)

    def test_historical_refresher_uses_recent_scores(self):
        """refresh_historical_data_for_tonight must reference get_recent_scores."""
        idx = self.src.find("def refresh_historical_data_for_tonight(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 7000]
        self.assertIn("get_recent_scores", snippet)

    def test_get_all_stores_cs_odds(self):
        """get_all_todays_data must reference get_game_odds from ApiNba."""
        idx = self.src.find("def get_all_todays_data(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 8000]
        self.assertIn("cs_game_odds", snippet)

    def test_get_all_stores_cs_predictions(self):
        """get_all_todays_data must reference get_predictions."""
        idx = self.src.find("def get_all_todays_data(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 8000]
        self.assertIn("cs_predictions", snippet)

    def test_module_docstring_mentions_odds_api(self):
        """Module header should mention The Odds API as a data source."""
        header = self.src[:800]
        self.assertIn("Odds API", header)

    def test_module_docstring_mentions_predictions(self):
        """Module header should mention predictions."""
        header = self.src[:800]
        self.assertIn("predictions", header)


if __name__ == "__main__":
    unittest.main()
