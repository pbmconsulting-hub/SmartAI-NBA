"""
tests/test_predictor_fixes.py
------------------------------
Tests for the prediction engine fixes:
  - Fix #1 & #6: predictor queries real DB data via _lookup_player_data
  - Fix #2: indexes on tracking DB tables
  - Fix #3: initialize_database caching via _DB_INITIALIZED flag
  - Fix #4: load_all_bets default limit raised from 200 to 10000
  - Fix #5: confidence interval derived from actual stat variance
"""

import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fix #1 & #6: Predictor queries real data ─────────────────────────


class TestLookupPlayerData(unittest.TestCase):
    """_lookup_player_data should bridge to the ETL DB."""

    @patch("data.db_service.get_player_splits", return_value={"home": [{"PTS": 28.0}], "away": [{"PTS": 22.0}]})
    @patch("data.db_service.get_team", return_value={"drtg": 108.5})
    @patch(
        "data.etl_data_service.get_player_game_logs",
        return_value=[{"pts": 28, "reb": 7, "ast": 6}],
    )
    @patch(
        "data.etl_data_service.get_player_by_name",
        return_value={"player_id": 1, "team_id": 10, "ppg": 25.3, "rpg": 7.0},
    )
    def test_returns_averages_team_logs_splits(self, mock_player, mock_logs, mock_team, mock_splits):
        from engine.predict.predictor import _lookup_player_data

        avgs, team, logs, splits = _lookup_player_data("LeBron James")
        mock_player.assert_called_once_with("LeBron James")
        mock_logs.assert_called_once_with(1, limit=30)
        mock_team.assert_called_once_with(10)
        mock_splits.assert_called_once_with(1)
        self.assertIn("ppg", avgs)
        self.assertEqual(team["drtg"], 108.5)
        self.assertEqual(len(logs), 1)
        self.assertIn("home", splits)

    @patch(
        "data.etl_data_service.get_player_by_name",
        return_value=None,
    )
    def test_returns_empty_when_player_not_found(self, mock_player):
        from engine.predict.predictor import _lookup_player_data

        avgs, team, logs, splits = _lookup_player_data("Nonexistent Player")
        self.assertEqual(avgs, {})
        self.assertEqual(team, {})
        self.assertEqual(logs, [])
        self.assertEqual(splits, {})


class TestPredictPlayerStatUsesRealData(unittest.TestCase):
    """predict_player_stat should use real data in feature matrix."""

    @patch("engine.predict.predictor._load_best_model", return_value=None)
    @patch(
        "engine.predict.predictor._lookup_player_data",
        return_value=(
            {"ppg": 27.5, "rpg": 7.2, "apg": 7.1, "points_std": 5.3},
            {"drtg": 109.0},
            [{"pts": 30}, {"pts": 25}, {"pts": 28}],
            {"home": [{"PTS": 29.0}], "away": [{"PTS": 24.0}]},
        ),
    )
    def test_uses_season_average_fallback(self, mock_lookup, mock_model):
        from engine.predict.predictor import predict_player_stat

        result = predict_player_stat("LeBron James", "pts", {})
        self.assertEqual(result["prediction"], 27.5)
        self.assertEqual(result["source"], "season_average")
        # Confidence interval should exist and not be the hardcoded ±15%
        self.assertIsNotNone(result["confidence_interval"])

    @patch("engine.predict.predictor._load_best_model", return_value=None)
    @patch(
        "engine.predict.predictor._lookup_player_data",
        return_value=({}, {}, [], {}),
    )
    def test_falls_back_to_defaults_when_no_data(self, mock_lookup, mock_model):
        from engine.predict.predictor import predict_player_stat

        result = predict_player_stat("Unknown Player", "pts", {})
        self.assertEqual(result["prediction"], 15.0)
        self.assertEqual(result["source"], "default_fallback")

    @patch("engine.predict.predictor._load_best_model", return_value=None)
    @patch(
        "engine.predict.predictor._lookup_player_data",
        return_value=(
            {"ppg": 25.0, "rpg": 6.0, "apg": 5.0},
            {"drtg": 110.0},
            [{"pts": 28}, {"pts": 22}],
            {
                "home": [{"PTS": 28.0, "REB": 7.0, "AST": 6.0, "STL": 1.5}],
                "away": [{"PTS": 22.0, "REB": 5.0, "AST": 4.0, "STL": 0.8}],
            },
        ),
    )
    def test_home_splits_enrich_features(self, mock_lookup, mock_model):
        """When is_home=True, home split averages should appear in features."""
        from engine.predict.predictor import predict_player_stat

        result = predict_player_stat("Test Player", "pts", {"is_home": True})
        # Prediction uses season average (no ML model), so ppg = 25.0
        self.assertEqual(result["prediction"], 25.0)
        self.assertEqual(result["source"], "season_average")

    @patch("engine.predict.predictor._load_best_model", return_value=None)
    @patch(
        "engine.predict.predictor._lookup_player_data",
        return_value=(
            {"ppg": 25.0, "rpg": 6.0, "apg": 5.0},
            {"drtg": 110.0},
            [{"pts": 28}, {"pts": 22}],
            {
                "home": [{"PTS": 28.0, "REB": 7.0}],
                "away": [{"PTS": 22.0, "REB": 5.0}],
            },
        ),
    )
    def test_away_splits_enrich_features(self, mock_lookup, mock_model):
        """When is_home=False, away split averages should appear in features."""
        from engine.predict.predictor import predict_player_stat

        result = predict_player_stat("Test Player", "pts", {"is_home": False})
        self.assertEqual(result["prediction"], 25.0)
        self.assertEqual(result["source"], "season_average")


# ── Fix #5: Confidence interval from real variance ────────────────────


class TestComputeConfidenceInterval(unittest.TestCase):
    """_compute_confidence_interval should use actual stat variance."""

    def test_from_game_logs(self):
        from engine.predict.predictor import _compute_confidence_interval

        game_logs = [
            {"pts": 25},
            {"pts": 30},
            {"pts": 20},
            {"pts": 28},
            {"pts": 22},
        ]
        lower, upper = _compute_confidence_interval(25.0, "pts", game_logs, {})
        # std of [25, 30, 20, 28, 22] ≈ 4.0
        self.assertNotAlmostEqual(lower, 25.0 * 0.85, places=1)
        self.assertGreater(upper, lower)

    def test_from_player_averages_std(self):
        from engine.predict.predictor import _compute_confidence_interval

        # No game logs but player_averages has points_std
        lower, upper = _compute_confidence_interval(
            25.0, "pts", [], {"points_std": 5.0}
        )
        self.assertEqual(lower, 20.0)
        self.assertEqual(upper, 30.0)

    def test_fallback_to_heuristic(self):
        from engine.predict.predictor import _compute_confidence_interval

        # No game logs AND no std key in averages → heuristic
        lower, upper = _compute_confidence_interval(20.0, "stl", [], {})
        # Heuristic: ±15%
        self.assertAlmostEqual(lower, 17.0, places=1)
        self.assertAlmostEqual(upper, 23.0, places=1)

    def test_steals_std_used_when_available(self):
        from engine.predict.predictor import _compute_confidence_interval

        lower, upper = _compute_confidence_interval(
            1.5, "stl", [], {"steals_std": 0.8}
        )
        self.assertAlmostEqual(lower, 0.7, places=2)
        self.assertAlmostEqual(upper, 2.3, places=2)

    def test_blocks_std_used_when_available(self):
        from engine.predict.predictor import _compute_confidence_interval

        lower, upper = _compute_confidence_interval(
            1.0, "blk", [], {"blocks_std": 0.6}
        )
        self.assertAlmostEqual(lower, 0.4, places=2)
        self.assertAlmostEqual(upper, 1.6, places=2)

    def test_turnovers_std_used_when_available(self):
        from engine.predict.predictor import _compute_confidence_interval

        lower, upper = _compute_confidence_interval(
            3.0, "tov", [], {"turnovers_std": 1.2}
        )
        self.assertAlmostEqual(lower, 1.8, places=2)
        self.assertAlmostEqual(upper, 4.2, places=2)

    def test_ftm_std_used_when_available(self):
        from engine.predict.predictor import _compute_confidence_interval

        lower, upper = _compute_confidence_interval(
            5.0, "ftm", [], {"ftm_std": 2.0}
        )
        self.assertAlmostEqual(lower, 3.0, places=2)
        self.assertAlmostEqual(upper, 7.0, places=2)

    def test_oreb_std_used_when_available(self):
        from engine.predict.predictor import _compute_confidence_interval

        lower, upper = _compute_confidence_interval(
            2.0, "oreb", [], {"oreb_std": 1.0}
        )
        self.assertAlmostEqual(lower, 1.0, places=2)
        self.assertAlmostEqual(upper, 3.0, places=2)

    def test_plus_minus_std_used_when_available(self):
        from engine.predict.predictor import _compute_confidence_interval

        lower, upper = _compute_confidence_interval(
            3.0, "plus_minus", [], {"plus_minus_std": 8.0}
        )
        self.assertAlmostEqual(lower, 0.0, places=2)  # max(3.0-8.0, 0)
        self.assertAlmostEqual(upper, 11.0, places=2)


# ── Fix #2: Indexes on tracking DB ───────────────────────────────────


class TestTrackingDBIndexes(unittest.TestCase):
    """initialize_database should create performance indexes."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        import tracking.database as db_mod

        self.db_mod = db_mod
        self._orig_dir = db_mod.DB_DIRECTORY
        self._orig_path = db_mod.DB_FILE_PATH
        self._orig_flag = db_mod._DB_INITIALIZED
        db_mod.DB_DIRECTORY = pathlib.Path(self.temp_dir)
        db_mod.DB_FILE_PATH = pathlib.Path(self.temp_dir) / "test.db"
        db_mod._DB_INITIALIZED = False

    def tearDown(self):
        self.db_mod.DB_DIRECTORY = self._orig_dir
        self.db_mod.DB_FILE_PATH = self._orig_path
        self.db_mod._DB_INITIALIZED = self._orig_flag
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_indexes_created(self):
        self.db_mod.initialize_database()
        db_path = pathlib.Path(self.temp_dir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        indexes = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        ]
        conn.close()
        expected = [
            "idx_pgl_player_id",
            "idx_pgl_game_date",
            "idx_pgl_player_date",
            "idx_bets_player",
            "idx_bets_date",
            "idx_bets_created",
            "idx_bets_stat_type",
            "idx_bets_platform",
            "idx_bets_date_result",
            "idx_ph_date",
            "idx_ph_stat",
            "idx_aap_date",
            "idx_aap_player",
            "idx_aap_stat_type",
            "idx_aap_date_result",
        ]
        for idx_name in expected:
            self.assertIn(idx_name, indexes, f"Missing index: {idx_name}")


# ── Fix #3: initialize_database caching ───────────────────────────────


class TestInitializeDatabaseCaching(unittest.TestCase):
    """initialize_database should skip heavy work on subsequent calls."""

    def test_db_initialized_flag(self):
        import tracking.database as db_mod

        # After first init, flag should be True
        orig = db_mod._DB_INITIALIZED
        db_mod._DB_INITIALIZED = False
        try:
            db_mod.initialize_database()
            self.assertTrue(db_mod._DB_INITIALIZED)
        finally:
            db_mod._DB_INITIALIZED = orig

    def test_returns_true_when_cached(self):
        import tracking.database as db_mod

        orig = db_mod._DB_INITIALIZED
        db_mod._DB_INITIALIZED = True
        try:
            result = db_mod.initialize_database()
            self.assertTrue(result)
        finally:
            db_mod._DB_INITIALIZED = orig


# ── Fix #4: load_all_bets default limit ───────────────────────────────


class TestLoadAllBetsDefaultLimit(unittest.TestCase):
    """load_all_bets should default to limit=10000."""

    def test_default_limit_is_10000(self):
        import inspect
        from tracking.database import load_all_bets

        sig = inspect.signature(load_all_bets)
        default = sig.parameters["limit"].default
        self.assertEqual(default, 10000)


# ── Stat maps ─────────────────────────────────────────────────────────


class TestStatMaps(unittest.TestCase):
    """Verify the stat column / average / std maps are consistent."""

    def test_stat_col_map_covers_common_stats(self):
        from engine.predict.predictor import _STAT_COL_MAP

        for stat in ("pts", "reb", "ast", "stl", "blk"):
            self.assertIn(stat, _STAT_COL_MAP)

    def test_stat_avg_map_covers_common_stats(self):
        from engine.predict.predictor import _STAT_AVG_MAP

        for stat in ("pts", "reb", "ast"):
            self.assertIn(stat, _STAT_AVG_MAP)

    def test_stat_std_map_covers_all_simple_stats(self):
        """_STAT_STD_MAP should have entries for all 10 simple stats."""
        from engine.predict.predictor import _STAT_STD_MAP

        simple_stats = [
            "pts", "reb", "ast", "stl", "blk",
            "tov", "fg3m", "ftm", "oreb", "plus_minus",
        ]
        for stat in simple_stats:
            self.assertIn(stat, _STAT_STD_MAP, f"Missing _STAT_STD_MAP entry for {stat}")


if __name__ == "__main__":
    unittest.main()
