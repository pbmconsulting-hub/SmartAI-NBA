# ============================================================
# FILE: tests/test_joseph_loading.py
# PURPOSE: Tests for utils/joseph_loading.py — Joseph's animated
#          loading screen with rotating NBA fun facts.
# ============================================================
"""Tests for :mod:`utils.joseph_loading` — animated loading screen.

Validates the NBA fun-facts pool (uniqueness, length, count),
CSS animations, ``st.html()`` rendering path, and avatar fallback
behaviour.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure repo root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock streamlit before importing the module
_mock_st = MagicMock()
_mock_st.cache_data = lambda *a, **kw: (lambda f: f)
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)
sys.modules.setdefault("streamlit.components", MagicMock())
sys.modules.setdefault("streamlit.components.v1", MagicMock())


# ============================================================
# SECTION 1: Module imports
# ============================================================

class TestModuleImports(unittest.TestCase):
    """Verify the module imports cleanly and exposes expected symbols."""

    def test_import_module(self):
        import utils.joseph_loading as jl
        self.assertIsNotNone(jl)

    def test_has_nba_fun_facts(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        self.assertIsInstance(NBA_FUN_FACTS, tuple)

    def test_has_render_function(self):
        from utils.joseph_loading import render_joseph_loading_screen
        self.assertTrue(callable(render_joseph_loading_screen))

    def test_has_placeholder_function(self):
        from utils.joseph_loading import joseph_loading_placeholder
        self.assertTrue(callable(joseph_loading_placeholder))

    def test_has_get_random_facts(self):
        from utils.joseph_loading import get_random_facts
        self.assertTrue(callable(get_random_facts))

    def test_has_loading_css(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIsInstance(JOSEPH_LOADING_CSS, str)
        self.assertIn("<style>", JOSEPH_LOADING_CSS)


# ============================================================
# SECTION 2: NBA Fun Facts pool
# ============================================================

class TestNBAFunFacts(unittest.TestCase):
    """Verify the NBA fun facts pool has enough variety and quality."""

    def test_minimum_520_facts(self):
        """Pool should have at least 520 unique facts (currently 524)."""
        from utils.joseph_loading import NBA_FUN_FACTS
        self.assertGreaterEqual(len(NBA_FUN_FACTS), 520)

    def test_all_facts_are_strings(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        for fact in NBA_FUN_FACTS:
            self.assertIsInstance(fact, str)

    def test_all_facts_are_non_empty(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        for fact in NBA_FUN_FACTS:
            self.assertTrue(len(fact.strip()) > 0)

    def test_no_duplicate_facts(self):
        from utils.joseph_loading import NBA_FUN_FACTS
        self.assertEqual(len(NBA_FUN_FACTS), len(set(NBA_FUN_FACTS)))

    def test_facts_reasonable_length(self):
        """Each fact should be between 20 and 300 characters."""
        from utils.joseph_loading import NBA_FUN_FACTS
        for fact in NBA_FUN_FACTS:
            self.assertGreaterEqual(len(fact), 20, f"Fact too short: {fact}")
            self.assertLessEqual(len(fact), 300, f"Fact too long: {fact}")


# ============================================================
# SECTION 3: get_random_facts
# ============================================================

class TestGetRandomFacts(unittest.TestCase):
    """Verify get_random_facts returns correct number of unique facts."""

    def test_default_count(self):
        from utils.joseph_loading import get_random_facts, _FACTS_PER_SCREEN
        facts = get_random_facts()
        self.assertEqual(len(facts), _FACTS_PER_SCREEN)

    def test_custom_count(self):
        from utils.joseph_loading import get_random_facts
        facts = get_random_facts(5)
        self.assertEqual(len(facts), 5)

    def test_returns_unique_facts(self):
        from utils.joseph_loading import get_random_facts
        facts = get_random_facts(20)
        self.assertEqual(len(facts), len(set(facts)))

    def test_returns_list(self):
        from utils.joseph_loading import get_random_facts
        facts = get_random_facts(3)
        self.assertIsInstance(facts, list)

    def test_randomness(self):
        """get_random_facts returns a permutation of the source pool."""
        import random as _rng
        from utils.joseph_loading import get_random_facts, NBA_FUN_FACTS
        _rng.seed(42)
        a = tuple(get_random_facts(20))
        _rng.seed(99)
        b = tuple(get_random_facts(20))
        # Different seeds ⇒ different orderings
        self.assertNotEqual(a, b)
        # Every returned fact comes from the pool
        for fact in a + b:
            self.assertIn(fact, NBA_FUN_FACTS)


# ============================================================
# SECTION 4: CSS content checks
# ============================================================

class TestLoadingCSS(unittest.TestCase):
    """Verify the CSS contains key animation and style rules."""

    def test_bounce_in_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("josephBounceIn", JOSEPH_LOADING_CSS)

    def test_pulse_glow_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("josephPulseGlow", JOSEPH_LOADING_CSS)

    def test_basketball_spin_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("basketballSpin", JOSEPH_LOADING_CSS)

    def test_fact_fade_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("factFadeIn", JOSEPH_LOADING_CSS)

    def test_loading_overlay_class(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("joseph-loading-overlay", JOSEPH_LOADING_CSS)

    def test_loading_avatar_class(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("joseph-loading-avatar", JOSEPH_LOADING_CSS)

    def test_loading_fact_class(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("joseph-loading-fact", JOSEPH_LOADING_CSS)

    def test_court_line_glow(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("courtLineGlow", JOSEPH_LOADING_CSS)

    def test_particle_drift_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("particleDrift", JOSEPH_LOADING_CSS)

    def test_shimmer_slide_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("shimmerSlide", JOSEPH_LOADING_CSS)

    def test_progress_pulse_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("progressPulse", JOSEPH_LOADING_CSS)

    def test_avatar_ring_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("avatarRingRotate", JOSEPH_LOADING_CSS)

    def test_glassmorphic_backdrop_blur(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("backdrop-filter", JOSEPH_LOADING_CSS)

    def test_responsive_media_query(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("@media", JOSEPH_LOADING_CSS)

    def test_glow_breath_animation(self):
        from utils.joseph_loading import JOSEPH_LOADING_CSS
        self.assertIn("glowBreath", JOSEPH_LOADING_CSS)


# ============================================================
# SECTION 5: render_joseph_loading_screen
# ============================================================

class TestRenderJosephLoadingScreen(unittest.TestCase):
    """Verify render_joseph_loading_screen generates correct HTML."""

    def setUp(self):
        _mock_st.html.reset_mock()

    def test_calls_st_html(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        render_joseph_loading_screen()
        _mock_st.html.assert_called_once()

    def test_html_has_avatar_section(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-avatar", html)

    def test_html_has_fact_section(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-fact", html)

    def test_html_has_name(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("Joseph M. Smith", html)

    def test_html_has_did_you_know(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("Did You Know?", html)

    def test_custom_status_text(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen(status_text="Testing analysis")
        html = _mock_st.html.call_args[0][0]
        self.assertIn("Testing analysis", html)

    def test_html_has_basketball_spinner(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-ball", html)

    def test_html_has_avatar_ring(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-avatar-ring", html)

    def test_html_has_particles(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-particles", html)

    def test_html_has_progress_bar(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-progress-bar", html)

    def test_html_has_ambient_glow(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("joseph-loading-ambient-glow", html)

    def test_html_has_subtitle(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("Your NBA Analytics Expert", html)

    def test_html_has_js_rotation_script(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        self.assertIn("setInterval", html)

    def test_uses_st_html_for_script_execution(self):
        """st.html() is used instead of st.markdown() so <script> tags execute."""
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        _mock_st.markdown.reset_mock()
        render_joseph_loading_screen()
        _mock_st.html.assert_called_once()
        _mock_st.markdown.assert_not_called()

    def test_st_html_passes_unsafe_allow_javascript(self):
        """unsafe_allow_javascript=True is required so DOMPurify preserves <style>/<script>."""
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen()
        _mock_st.html.assert_called_once()
        _, kwargs = _mock_st.html.call_args
        self.assertTrue(
            kwargs.get("unsafe_allow_javascript", False),
            "st.html must be called with unsafe_allow_javascript=True "
            "so that DOMPurify preserves <style> and <script> tags",
        )


# ============================================================
# SECTION 6: joseph_loading_placeholder
# ============================================================

class TestJosephLoadingPlaceholder(unittest.TestCase):
    """Verify joseph_loading_placeholder uses st.empty correctly."""

    def test_returns_placeholder(self):
        from utils.joseph_loading import joseph_loading_placeholder
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.empty.reset_mock()
        placeholder = joseph_loading_placeholder()
        _mock_st.empty.assert_called_once()
        self.assertIsNotNone(placeholder)

    def test_placeholder_container_called(self):
        from utils.joseph_loading import joseph_loading_placeholder
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.empty.reset_mock()
        placeholder = joseph_loading_placeholder("Running analysis")
        # The placeholder's .container() context should be called
        placeholder.container.assert_called()


# ============================================================
# SECTION 7: Avatar fallback
# ============================================================

class TestAvatarFallback(unittest.TestCase):
    """Verify the loading screen degrades gracefully without avatar."""

    def test_no_avatar_uses_fallback(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()

        # Force avatar to be unavailable
        original_fn = jl.get_joseph_avatar_b64
        jl.get_joseph_avatar_b64 = lambda: ""
        jl._AVATAR_AVAILABLE = True

        render_joseph_loading_screen()
        html = _mock_st.html.call_args[0][0]
        # Should still have the avatar class (with basketball fallback)
        self.assertIn("joseph-loading-avatar", html)

        # Restore
        jl.get_joseph_avatar_b64 = original_fn


# ============================================================
# SECTION 8: Status text HTML escaping
# ============================================================

class TestStatusTextEscaping(unittest.TestCase):
    """Verify status text is properly HTML-escaped to prevent XSS."""

    def test_html_entities_escaped(self):
        from utils.joseph_loading import render_joseph_loading_screen
        import utils.joseph_loading as jl
        jl.st = _mock_st
        _mock_st.html.reset_mock()
        render_joseph_loading_screen(status_text="<script>alert('xss')</script>")
        html = _mock_st.html.call_args[0][0]
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
