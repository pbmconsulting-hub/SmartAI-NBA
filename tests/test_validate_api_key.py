"""
tests/test_validate_api_key.py
------------------------------
Tests for validate_api_key() in both ClearSports and Odds API clients.
"""

import sys
import os
import pathlib
import unittest

# ── Ensure project root is on sys.path ────────────────────────────────────────
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ── Source-level tests: function existence ────────────────────────────────────

_CS_SRC = pathlib.Path(__file__).parent.parent / "data" / "clearsports_client.py"
_OA_SRC = pathlib.Path(__file__).parent.parent / "data" / "odds_api_client.py"


class TestValidateApiKeyFunctionExists(unittest.TestCase):
    """validate_api_key must be defined in both API clients."""

    def test_clearsports_has_validate_api_key(self):
        src = _CS_SRC.read_text(encoding="utf-8")
        self.assertIn("def validate_api_key(", src)

    def test_odds_api_has_validate_api_key(self):
        src = _OA_SRC.read_text(encoding="utf-8")
        self.assertIn("def validate_api_key(", src)


# ── ClearSports validate_api_key runtime tests ───────────────────────────────

class TestClearSportsValidateApiKey(unittest.TestCase):
    """Runtime tests for clearsports_client.validate_api_key."""

    def setUp(self):
        from data.clearsports_client import validate_api_key
        self.validate = validate_api_key

    def test_valid_key_returns_true(self):
        ok, msg = self.validate("sk_test_AAAAAAAAAA-BBBBBBBB-fake-key-000")
        self.assertTrue(ok)
        self.assertIn("valid", msg.lower())

    def test_none_returns_false(self):
        ok, msg = self.validate(None)
        self.assertFalse(ok)

    def test_empty_string_returns_false(self):
        ok, msg = self.validate("")
        self.assertFalse(ok)

    def test_short_key_returns_false(self):
        ok, msg = self.validate("abc")
        self.assertFalse(ok)
        self.assertIn("short", msg.lower())

    def test_key_with_spaces_returns_false(self):
        ok, msg = self.validate("sk live abc123def456")
        self.assertFalse(ok)
        self.assertIn("space", msg.lower())

    def test_returns_tuple(self):
        result = self.validate("valid_key_1234567890")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_whitespace_only_returns_false(self):
        ok, _ = self.validate("   ")
        self.assertFalse(ok)


# ── Odds API validate_api_key runtime tests ───────────────────────────────────

class TestOddsApiValidateApiKey(unittest.TestCase):
    """Runtime tests for odds_api_client.validate_api_key."""

    def setUp(self):
        from data.odds_api_client import validate_api_key
        self.validate = validate_api_key

    def test_valid_key_returns_true(self):
        ok, msg = self.validate("00000000aaaa1111bbbb2222cccc3333")
        self.assertTrue(ok)
        self.assertIn("valid", msg.lower())

    def test_none_returns_false(self):
        ok, msg = self.validate(None)
        self.assertFalse(ok)

    def test_empty_string_returns_false(self):
        ok, msg = self.validate("")
        self.assertFalse(ok)

    def test_short_key_returns_false(self):
        ok, msg = self.validate("abc")
        self.assertFalse(ok)
        self.assertIn("short", msg.lower())

    def test_key_with_spaces_returns_false(self):
        ok, msg = self.validate("90e90e97 ab094783")
        self.assertFalse(ok)
        self.assertIn("space", msg.lower())

    def test_returns_tuple(self):
        result = self.validate("valid_key_1234567890")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


# ── Settings page structure tests ─────────────────────────────────────────────

_SETTINGS_SRC = pathlib.Path(__file__).parent.parent / "pages" / "13_⚙️_Settings.py"


class TestSettingsPageApiKeySection(unittest.TestCase):
    """Verify the Settings page includes API key management UI elements."""

    def setUp(self):
        self.src = _SETTINGS_SRC.read_text(encoding="utf-8")

    def test_has_test_connection_button(self):
        """Settings page must have a Test Connection button."""
        self.assertIn("Test Connection", self.src)

    def test_has_save_keys_button(self):
        """Settings page must have a Save Keys button."""
        self.assertIn("Save Keys", self.src)

    def test_has_clear_keys_button(self):
        """Settings page must have a Clear Keys button."""
        self.assertIn("Clear Keys", self.src)

    def test_imports_validate_api_key(self):
        """Settings page must import validate_api_key for key format checking."""
        self.assertIn("validate_api_key", self.src)

    def test_calls_fetch_api_key_info(self):
        """Test Connection must call fetch_api_key_info for ClearSports."""
        self.assertIn("fetch_api_key_info", self.src)

    def test_calls_fetch_events(self):
        """Test Connection must call fetch_events for Odds API."""
        self.assertIn("fetch_events", self.src)


if __name__ == "__main__":
    unittest.main()
