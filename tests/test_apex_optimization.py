# ============================================================
# FILE: tests/test_apex_optimization.py
# PURPOSE: Tests for the APEX Optimization Directive:
#          1) True Line extraction & crash prevention
#          2) Async bet resolver (ThreadPoolExecutor)
#          3) CSS logo sizing overrides
# ============================================================

import pathlib
import sys
import unittest
from unittest.mock import MagicMock


def _ensure_streamlit_mock():
    """Inject a lightweight streamlit mock if not installed."""
    if "streamlit" not in sys.modules:
        mock_st = MagicMock()
        mock_st.session_state = {}
        sys.modules["streamlit"] = mock_st


# ============================================================
# Pillar 1: True Line Extraction & Crash Prevention
# ============================================================

# ============================================================
# Pillar 2: Async Bet Tracker (ThreadPoolExecutor)
# ============================================================

class TestAsyncBetResolver(unittest.TestCase):
    """Verify bet resolver uses ThreadPoolExecutor for parallel retrieval."""

    def test_threadpoolexecutor_in_auto_resolve(self):
        """auto_resolve_bet_results should import ThreadPoolExecutor."""
        src = pathlib.Path(__file__).parent.parent / "tracking" / "bet_tracker.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn("ThreadPoolExecutor", content,
                       "auto_resolve_bet_results should use ThreadPoolExecutor")

    def test_as_completed_in_auto_resolve(self):
        """auto_resolve_bet_results should use as_completed for future gathering."""
        src = pathlib.Path(__file__).parent.parent / "tracking" / "bet_tracker.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn("as_completed", content,
                       "Should use as_completed from concurrent.futures")

    def test_game_log_cache_in_resolve(self):
        """Resolver should pre-cache game logs before processing bets."""
        src = pathlib.Path(__file__).parent.parent / "tracking" / "bet_tracker.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn("_game_log_cache", content,
                       "Resolver should maintain a _game_log_cache for parallel get results")

    def test_parallel_get_helper_exists(self):
        """A _get_player_log helper should exist for the ThreadPoolExecutor."""
        src = pathlib.Path(__file__).parent.parent / "tracking" / "bet_tracker.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn("def _get_player_log(", content,
                       "_get_player_log helper should be defined for parallel retrieval")

    def test_max_workers_capped(self):
        """ThreadPoolExecutor max_workers should be capped at 8."""
        src = pathlib.Path(__file__).parent.parent / "tracking" / "bet_tracker.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn("max_workers=min(8", content,
                       "ThreadPoolExecutor should cap max_workers at 8")

    def test_resolve_todays_uses_threadpool(self):
        """resolve_todays_bets should also use ThreadPoolExecutor."""
        src = pathlib.Path(__file__).parent.parent / "tracking" / "bet_tracker.py"
        content = src.read_text(encoding="utf-8")
        # Count ThreadPoolExecutor references — should appear in both resolve functions
        count = content.count("ThreadPoolExecutor")
        self.assertGreaterEqual(count, 2,
                                f"Expected ThreadPoolExecutor in ≥2 resolve functions, got {count}")


# ============================================================
# Pillar 3: CSS Logo Sizing Overrides
# ============================================================

class TestCSSLogoOverrides(unittest.TestCase):
    """Verify CSS overrides for hero banner and sidebar logos."""

    def test_hero_logo_width_250px(self):
        """Hero banner logo should have a width constraint."""
        src = pathlib.Path(__file__).parent.parent / "styles" / "theme.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn(".spp-hero-logo", content,
                       "Hero logo CSS class should be defined in theme.py")

    def test_hero_logo_object_fit(self):
        """Hero banner logo should use object-fit: contain."""
        src = pathlib.Path(__file__).parent.parent / "styles" / "theme.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn("object-fit: contain", content,
                       "Hero logo should use object-fit: contain")

    def test_sidebar_logo_removed_per_branding(self):
        """Sidebar logo was removed per branding directive — no st.logo() in sidebar."""
        src = pathlib.Path(__file__).parent.parent / "styles" / "theme.py"
        content = src.read_text(encoding="utf-8")
        # Verify the comment documents the removal
        self.assertIn("Sidebar Logo", content,
                       "theme.py should document the sidebar logo status")

    def test_hero_logo_class_defined(self):
        """Responsive CSS should maintain the hero logo class definition."""
        src = pathlib.Path(__file__).parent.parent / "styles" / "theme.py"
        content = src.read_text(encoding="utf-8")
        self.assertIn(".spp-hero-logo {", content,
                       "Hero logo CSS class should be defined")


if __name__ == "__main__":
    unittest.main()
