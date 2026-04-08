# ============================================================
# FILE: tests/test_user_settings_persistence.py
# PURPOSE: Tests for user settings persistence across browser reloads.
#   Verifies save_user_settings / load_user_settings round-trip,
#   schema creation, key filtering, and idempotent overwrites.
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


class TestUserSettingsPersistence(unittest.TestCase):
    """Verify save/load of user settings through the SQLite layer."""

    def setUp(self):
        _ensure_streamlit_mock()
        import tracking.database as db
        self.db = db
        # Redirect database to a temp file so tests are isolated
        self._tmp_dir = tempfile.mkdtemp()
        self._tmp_db = os.path.join(self._tmp_dir, "test_settings.db")
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

    def test_user_settings_table_exists(self):
        """The user_settings table should be created by initialize_database."""
        conn = sqlite3.connect(self._tmp_db)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        conn.close()
        self.assertIn("user_settings", tables)

    # ── Round-trip save / load ────────────────────────────────

    def test_save_and_load_round_trip(self):
        """Settings saved with save_user_settings should be returned by load_user_settings."""
        settings = {
            "simulation_depth": 3000,
            "minimum_edge_threshold": 7.5,
            "entry_fee": 25.0,
            "selected_platforms": ["PrizePicks", "Underdog Fantasy"],
            "home_court_boost": 0.03,
            "blowout_sensitivity": 1.5,
            "fatigue_sensitivity": 0.8,
            "pace_sensitivity": 1.2,
            "total_bankroll": 5000.0,
            "kelly_multiplier": 0.5,
        }
        ok = self.db.save_user_settings(settings)
        self.assertTrue(ok)

        loaded = self.db.load_user_settings()
        for key, expected in settings.items():
            self.assertEqual(loaded[key], expected, f"Mismatch on key {key}")

    def test_overwrite_replaces_previous(self):
        """A second save should overwrite the first, not append."""
        self.db.save_user_settings({"simulation_depth": 1000})
        self.db.save_user_settings({"simulation_depth": 5000})
        loaded = self.db.load_user_settings()
        self.assertEqual(loaded["simulation_depth"], 5000)
        # Also verify only one row exists
        conn = sqlite3.connect(self._tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM user_settings").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    # ── Key filtering ─────────────────────────────────────────

    def test_unknown_keys_are_not_saved(self):
        """Keys not in _PERSISTED_SETTINGS_KEYS should be silently ignored."""
        self.db.save_user_settings({
            "simulation_depth": 2000,
            "some_random_key": "should_not_persist",
            "joseph_enabled": True,
        })
        loaded = self.db.load_user_settings()
        self.assertIn("simulation_depth", loaded)
        self.assertNotIn("some_random_key", loaded)
        self.assertNotIn("joseph_enabled", loaded)

    def test_empty_dict_returns_true(self):
        """Saving an empty dict should succeed (no-op)."""
        ok = self.db.save_user_settings({})
        self.assertTrue(ok)

    # ── Load when no settings saved ──────────────────────────

    def test_load_returns_empty_dict_when_no_row(self):
        """load_user_settings should return {} on a fresh database."""
        loaded = self.db.load_user_settings()
        self.assertEqual(loaded, {})

    # ── Constants / keys ──────────────────────────────────────

    def test_persisted_keys_constant_exists(self):
        """The _PERSISTED_SETTINGS_KEYS constant should be a tuple of strings."""
        keys = self.db._PERSISTED_SETTINGS_KEYS
        self.assertIsInstance(keys, tuple)
        self.assertTrue(all(isinstance(k, str) for k in keys))
        # Should include the core settings
        self.assertIn("simulation_depth", keys)
        self.assertIn("minimum_edge_threshold", keys)
        self.assertIn("entry_fee", keys)
        self.assertIn("selected_platforms", keys)
        self.assertIn("total_bankroll", keys)
        self.assertIn("kelly_multiplier", keys)

    # ── Partial save with missing keys ────────────────────────

    def test_partial_save_preserves_only_provided_keys(self):
        """Saving a subset of keys should store only those keys."""
        self.db.save_user_settings({"simulation_depth": 2000, "entry_fee": 50.0})
        loaded = self.db.load_user_settings()
        self.assertEqual(loaded["simulation_depth"], 2000)
        self.assertEqual(loaded["entry_fee"], 50.0)
        # Keys not provided should not be present
        self.assertNotIn("minimum_edge_threshold", loaded)

    # ── SQL table schema ──────────────────────────────────────

    def test_create_sql_constant_exists(self):
        """CREATE_USER_SETTINGS_TABLE_SQL should be defined."""
        self.assertIn("user_settings", self.db.CREATE_USER_SETTINGS_TABLE_SQL)


if __name__ == "__main__":
    unittest.main()
