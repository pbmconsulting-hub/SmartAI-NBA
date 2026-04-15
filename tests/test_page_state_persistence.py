# ============================================================
# FILE: tests/test_page_state_persistence.py
# PURPOSE: Tests for page state persistence across session resets.
#   Verifies save_page_state / load_page_state round-trip,
#   schema creation, key filtering, and empty-container handling.
# ============================================================
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


def _ensure_streamlit_mock():
    """Inject a lightweight streamlit mock if not installed."""
    if "streamlit" not in sys.modules:
        mock_st = MagicMock()
        mock_st.session_state = {}
        mock_st.cache_data = lambda **kw: (lambda f: f)
        sys.modules["streamlit"] = mock_st


class TestPageStatePersistence(unittest.TestCase):
    """Verify save/load of page state through the SQLite layer."""

    def setUp(self):
        _ensure_streamlit_mock()
        import tracking.database as db
        self.db = db
        # Redirect database to a temp file so tests are isolated
        self._tmp_dir = tempfile.mkdtemp()
        self._tmp_db = os.path.join(self._tmp_dir, "test_page_state.db")
        self._orig_path = db.DB_FILE_PATH
        self._orig_dir = db.DB_DIRECTORY
        db.DB_FILE_PATH = type(db.DB_FILE_PATH)(self._tmp_db)
        db.DB_DIRECTORY = type(db.DB_DIRECTORY)(self._tmp_dir)
        # Reset the initialization flag so the table gets created
        db._DB_INITIALIZED = False
        db.initialize_database()

    def tearDown(self):
        # Restore original paths
        self.db.DB_FILE_PATH = self._orig_path
        self.db.DB_DIRECTORY = self._orig_dir
        self.db._DB_INITIALIZED = False
        # Clean up temp files
        try:
            os.remove(self._tmp_db)
            os.rmdir(self._tmp_dir)
        except OSError:
            pass

    # ── Table creation ────────────────────────────────────────

    def test_page_state_table_exists(self):
        """The page_state table should be created by initialize_database."""
        conn = sqlite3.connect(self._tmp_db)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        self.assertIn("page_state", tables)

    # ── Round-trip save / load ────────────────────────────────

    def test_save_and_load_round_trip(self):
        """State saved with save_page_state should be returned by load_page_state."""
        state = {
            "analysis_results": [
                {"player_name": "LeBron James", "stat_type": "pts", "edge_percentage": 8.5},
            ],
            "selected_picks": [
                {"player_name": "Stephen Curry", "stat_type": "fg3m", "confidence_score": 0.75},
            ],
            "todays_games": [
                {"game_id": "0022400001", "home_team": "LAL", "away_team": "BOS"},
            ],
        }
        ok = self.db.save_page_state(state)
        self.assertTrue(ok)

        loaded = self.db.load_page_state()
        self.assertEqual(loaded["analysis_results"], state["analysis_results"])
        self.assertEqual(loaded["selected_picks"], state["selected_picks"])
        self.assertEqual(loaded["todays_games"], state["todays_games"])

    def test_overwrite_replaces_previous(self):
        """A second save should overwrite the first, not append."""
        self.db.save_page_state({
            "analysis_results": [{"player_name": "A"}],
        })
        self.db.save_page_state({
            "analysis_results": [{"player_name": "B"}],
        })
        loaded = self.db.load_page_state()
        self.assertEqual(loaded["analysis_results"][0]["player_name"], "B")
        # Also verify only one row exists
        conn = sqlite3.connect(self._tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM page_state").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    # ── Key filtering ─────────────────────────────────────────

    def test_unknown_keys_are_not_saved(self):
        """Keys not in _PERSISTED_PAGE_STATE_KEYS should be silently ignored."""
        self.db.save_page_state({
            "analysis_results": [{"player_name": "Test"}],
            "some_random_key": "should_not_persist",
            "joseph_enabled": True,
        })
        loaded = self.db.load_page_state()
        self.assertIn("analysis_results", loaded)
        self.assertNotIn("some_random_key", loaded)
        self.assertNotIn("joseph_enabled", loaded)

    def test_empty_containers_are_not_saved(self):
        """Empty lists/dicts should not overwrite previously saved data.

        When save_page_state is called with empty containers, those keys
        are skipped.  The function merges new non-empty values into the
        existing saved state, so previously saved keys are preserved.
        """
        # First save with data
        self.db.save_page_state({
            "analysis_results": [{"player_name": "LeBron"}],
            "selected_picks": [{"player_name": "Curry"}],
        })
        # Save again with empty analysis_results but non-empty picks
        self.db.save_page_state({
            "analysis_results": [],
            "selected_picks": [{"player_name": "Updated Curry"}],
        })
        loaded = self.db.load_page_state()
        # analysis_results should be preserved from the first save
        # because the empty list was skipped during the second save
        self.assertEqual(len(loaded.get("analysis_results", [])), 1)
        self.assertEqual(loaded["analysis_results"][0]["player_name"], "LeBron")
        # selected_picks should be updated from the second save
        self.assertEqual(loaded["selected_picks"][0]["player_name"], "Updated Curry")

    def test_empty_dict_returns_true(self):
        """Saving an empty dict should succeed (no-op)."""
        ok = self.db.save_page_state({})
        self.assertTrue(ok)

    def test_merge_preserves_keys_from_other_pages(self):
        """Saving data for one key should not wipe other previously saved keys."""
        # Simulate page A saving analysis_results
        self.db.save_page_state({
            "analysis_results": [{"player_name": "Page A data"}],
        })
        # Simulate page B saving selected_picks only
        self.db.save_page_state({
            "selected_picks": [{"player_name": "Page B data"}],
        })
        loaded = self.db.load_page_state()
        # Both keys should be present
        self.assertEqual(loaded["analysis_results"][0]["player_name"], "Page A data")
        self.assertEqual(loaded["selected_picks"][0]["player_name"], "Page B data")

    # ── Load when no state saved ──────────────────────────────

    def test_load_returns_empty_dict_when_no_row(self):
        """load_page_state should return {} on a fresh database."""
        loaded = self.db.load_page_state()
        self.assertEqual(loaded, {})

    # ── Constants / keys ──────────────────────────────────────

    def test_persisted_keys_constant_exists(self):
        """The _PERSISTED_PAGE_STATE_KEYS constant should be a tuple of strings."""
        keys = self.db._PERSISTED_PAGE_STATE_KEYS
        self.assertIsInstance(keys, tuple)
        self.assertTrue(all(isinstance(k, str) for k in keys))
        # Should include the core page state keys
        self.assertIn("analysis_results", keys)
        self.assertIn("selected_picks", keys)
        self.assertIn("todays_games", keys)
        self.assertIn("current_props", keys)
        self.assertIn("injury_status_map", keys)

    # ── Injury status map (dict) ──────────────────────────────

    def test_injury_status_map_round_trip(self):
        """Injury status map (dict of dicts) should round-trip correctly."""
        injury_map = {
            "lebron james": {"status": "Active", "games_missed": 0},
            "anthony davis": {"status": "GTD", "games_missed": 2},
        }
        self.db.save_page_state({"injury_status_map": injury_map})
        loaded = self.db.load_page_state()
        self.assertEqual(loaded["injury_status_map"], injury_map)

    # ── SQL table schema ──────────────────────────────────────

    def test_create_sql_constant_exists(self):
        """CREATE_PAGE_STATE_TABLE_SQL should be defined."""
        self.assertIn("page_state", self.db.CREATE_PAGE_STATE_TABLE_SQL)


if __name__ == "__main__":
    unittest.main()
