# ============================================================
# Tests for utils/joseph_loading.py
# ============================================================

import unittest
from unittest.mock import patch, MagicMock


class TestNBAFunFacts(unittest.TestCase):
    """Tests for the NBA fun facts data."""

    def test_minimum_80_facts(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        self.assertGreaterEqual(len(NBA_FUN_FACTS), 80)

    def test_facts_are_strings(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        for fact in NBA_FUN_FACTS:
            self.assertIsInstance(fact, str)
            self.assertGreater(len(fact), 10)

    def test_no_duplicate_facts(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        self.assertEqual(len(NBA_FUN_FACTS), len(set(NBA_FUN_FACTS)))


class TestGetRandomFacts(unittest.TestCase):
    """Tests for get_random_facts()."""

    def test_returns_list(self):
        from utils.joseph_loading import get_random_facts
        result = get_random_facts()
        self.assertIsInstance(result, list)

    def test_default_count(self):
        from utils.joseph_loading import get_random_facts, _FACTS_PER_SCREEN
        result = get_random_facts()
        self.assertEqual(len(result), _FACTS_PER_SCREEN)

    def test_custom_count(self):
        from utils.joseph_loading import get_random_facts
        result = get_random_facts(5)
        self.assertEqual(len(result), 5)

    def test_clamped_low(self):
        from utils.joseph_loading import get_random_facts
        result = get_random_facts(0)
        self.assertEqual(len(result), 1)

    def test_clamped_high(self):
        from utils.joseph_loading import get_random_facts, NBA_FUN_FACTS
        result = get_random_facts(9999)
        self.assertEqual(len(result), len(NBA_FUN_FACTS))

    def test_unique_results(self):
        from utils.joseph_loading import get_random_facts
        result = get_random_facts(15)
        self.assertEqual(len(result), len(set(result)))

    def test_randomness(self):
        """Two calls should (almost certainly) return different orderings."""
        from utils.joseph_loading import get_random_facts
        a = get_random_facts(15)
        b = get_random_facts(15)
        # Not guaranteed, but extremely unlikely to be identical
        # Just check both are valid
        self.assertEqual(len(a), 15)
        self.assertEqual(len(b), 15)


class TestBuildLoadingHTML(unittest.TestCase):
    """Tests for _build_loading_html()."""

    def test_returns_string(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html("Testing…")
        self.assertIsInstance(html, str)

    def test_contains_status_text(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html("Crunching numbers…")
        self.assertIn("Crunching numbers", html)

    def test_contains_css(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html()
        self.assertIn("<style>", html)
        self.assertIn("jl-container", html)

    def test_contains_js(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html()
        self.assertIn("<script>", html)
        self.assertIn("setInterval", html)

    def test_contains_avatar(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html()
        self.assertIn("jl-avatar", html)

    def test_contains_fun_fact_element(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html()
        self.assertIn("jl-fact-text", html)

    def test_escapes_status_text(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html("<script>alert('xss')</script>")
        self.assertNotIn("<script>alert", html)

    def test_custom_rotation_seconds(self):
        from utils.joseph_loading import _build_loading_html
        html = _build_loading_html(rotation_seconds=10)
        self.assertIn("10s linear infinite", html)
        self.assertIn("10000", html)


class TestAvatarLoader(unittest.TestCase):
    """Tests for _get_joseph_avatar_spinning_b64()."""

    def test_returns_string(self):
        from utils.joseph_loading import _get_joseph_avatar_spinning_b64
        result = _get_joseph_avatar_spinning_b64()
        self.assertIsInstance(result, str)

    @patch("os.path.isfile", return_value=False)
    def test_returns_empty_on_missing(self, _mock):
        from utils.joseph_loading import _get_joseph_avatar_spinning_b64
        result = _get_joseph_avatar_spinning_b64()
        self.assertEqual(result, "")


class TestJosephLoadingPlaceholder(unittest.TestCase):
    """Tests for joseph_loading_placeholder()."""

    @patch("utils.joseph_loading.st")
    def test_returns_placeholder(self, mock_st):
        mock_empty = MagicMock()
        mock_st.empty.return_value = mock_empty
        from utils.joseph_loading import joseph_loading_placeholder
        result = joseph_loading_placeholder("Testing…")
        self.assertEqual(result, mock_empty)
        mock_empty.markdown.assert_called_once()

    @patch("utils.joseph_loading.st", None)
    def test_raises_without_streamlit(self):
        from utils.joseph_loading import joseph_loading_placeholder
        with self.assertRaises(RuntimeError):
            joseph_loading_placeholder()


if __name__ == "__main__":
    unittest.main()
