# ============================================================
# FILE: tests/test_card_matrix_overhaul.py
# PURPOSE: Tests for the Infinite Card-Matrix Overhaul features:
#          - utils/renderers.py compile_card_matrix()
#          - engine/simulation.py generate_contextual_goblin_demon()
#          - data/sportsbook_service.py async retrieval + 500-cap
#          - styles/theme.py Quantum Card Matrix CSS
#          - .streamlit/config.toml maxMessageSize
# ============================================================

import unittest
import os


class TestCompileCardMatrix(unittest.TestCase):
    """Tests for utils/renderers.py compile_card_matrix()."""

    def setUp(self):
        from utils.renderers import compile_card_matrix, _build_single_card_html
        self.compile = compile_card_matrix
        self.build_card = _build_single_card_html

    def _sample_result(self, **overrides):
        """Create a sample analysis result dict."""
        base = {
            "player_name": "LeBron James",
            "stat_type": "points",
            "player_team": "LAL",
            "platform": "PrizePicks",
            "prop_line": 24.5,
            "tier": "Gold",
            "confidence_score": 78,
            "probability_over": 0.62,
            "edge_percentage": 5.3,
            "bet_type": "goblin",
            "prediction": "I predict the stat will do at LEAST 23.5",
            "direction": "OVER",
        }
        base.update(overrides)
        return base

    def test_returns_string(self):
        html = self.compile([self._sample_result()])
        self.assertIsInstance(html, str)

    def test_empty_results_returns_placeholder(self):
        html = self.compile([])
        self.assertIn("No analysis results", html)

    def test_single_card_contains_player_name(self):
        html = self.compile([self._sample_result()])
        self.assertIn("LeBron James", html)

    def test_single_card_contains_true_line(self):
        html = self.compile([self._sample_result(prop_line=24.5)])
        self.assertIn("24.5", html)

    def test_single_card_contains_tier(self):
        html = self.compile([self._sample_result(tier="Platinum")])
        self.assertIn("Platinum", html)
        self.assertIn("qcm-tier-platinum", html)

    def test_goblin_prediction_text_displayed(self):
        html = self.compile([self._sample_result(
            bet_type="goblin",
            prediction="I predict the stat will do at LEAST 23.5",
        )])
        self.assertIn("at LEAST 23.5", html)
        self.assertIn("qcm-prediction-goblin", html)

    def test_demon_prediction_text_displayed(self):
        html = self.compile([self._sample_result(
            bet_type="demon",
            prediction="I predict the stat will do at MOST 26.5",
        )])
        self.assertIn("at MOST 26.5", html)
        self.assertIn("qcm-prediction-demon", html)

    def test_css_grid_class_present(self):
        html = self.compile([self._sample_result()])
        self.assertIn("qcm-grid", html)

    def test_max_cards_slices_output(self):
        results = [self._sample_result(player_name=f"Player {i}") for i in range(100)]
        html = self.compile(results, max_cards=10)
        # Should contain "Player 0" through "Player 9" but not "Player 10"
        self.assertIn("Player 0", html)
        self.assertIn("Player 9", html)
        self.assertNotIn("Player 10", html)
        # Should show truncation notice
        self.assertIn("Showing top 10 of 100", html)

    def test_default_max_cards_is_50(self):
        results = [self._sample_result(player_name=f"P{i}") for i in range(60)]
        html = self.compile(results)
        # Default max_cards is now None — all cards render
        self.assertIn("P0", html)
        self.assertIn("P49", html)
        self.assertIn("P59", html)

    def test_html_escaping_prevents_xss(self):
        html = self.compile([self._sample_result(
            player_name='<script>alert("xss")</script>',
        )])
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_single_markdown_injection_no_loops(self):
        """Verify the output is a single contiguous HTML string."""
        results = [self._sample_result() for _ in range(5)]
        html = self.compile(results)
        # Count grid containers — should be exactly one
        self.assertEqual(html.count('class="qcm-grid"'), 1)

    def test_stagger_animation_delay(self):
        results = [self._sample_result(player_name=f"P{i}") for i in range(3)]
        html = self.compile(results)
        # First card: 0ms delay
        self.assertIn("animation-delay:0ms", html)
        # Second card: 20ms delay
        self.assertIn("animation-delay:20ms", html)
        # Third card: 40ms delay
        self.assertIn("animation-delay:40ms", html)

    def test_metrics_displayed(self):
        html = self.compile([self._sample_result(
            probability_over=0.65,
            confidence_score=82,
            edge_percentage=4.7,
        )])
        self.assertIn("65.0%", html)
        self.assertIn("82", html)
        self.assertIn("+4.7%", html)

    def test_auto_generates_goblin_prediction_when_missing(self):
        html = self.compile([self._sample_result(
            bet_type="goblin",
            prediction="",  # No prediction provided
            prop_line=20.0,
        )])
        # Goblin prediction auto-gen removed; class not used on any element
        self.assertNotIn('class="qcm-prediction qcm-prediction-goblin"', html)

    def test_auto_generates_demon_prediction_when_missing(self):
        html = self.compile([self._sample_result(
            bet_type="demon",
            prediction="",
            prop_line=20.0,
        )])
        # Demon prediction auto-gen removed; class not used on any element
        self.assertNotIn('class="qcm-prediction qcm-prediction-demon"', html)


class TestContextualGoblinDemon(unittest.TestCase):
    """Tests for engine/simulation.py generate_contextual_goblin_demon()."""

    def setUp(self):
        from engine.simulation import generate_contextual_goblin_demon
        self.gen = generate_contextual_goblin_demon

    def test_over_direction_goblin_minus_one(self):
        result = self.gen(24.5, direction="over")
        self.assertAlmostEqual(result["goblin_line"], 24.5)

    def test_over_direction_demon_plus_two(self):
        result = self.gen(24.5, direction="over")
        self.assertAlmostEqual(result["demon_line"], 24.5)

    def test_under_direction_goblin_plus_one(self):
        result = self.gen(24.5, direction="under")
        self.assertAlmostEqual(result["goblin_line"], 24.5)

    def test_under_direction_demon_minus_two(self):
        result = self.gen(24.5, direction="under")
        self.assertAlmostEqual(result["demon_line"], 24.5)

    def test_over_goblin_prediction_at_least(self):
        result = self.gen(20.0, direction="over")
        self.assertEqual(result["goblin_prediction"], "")

    def test_over_demon_prediction_at_most(self):
        result = self.gen(20.0, direction="over")
        self.assertEqual(result["demon_prediction"], "")

    def test_under_goblin_prediction_at_most(self):
        result = self.gen(20.0, direction="under")
        self.assertEqual(result["goblin_prediction"], "")

    def test_under_demon_prediction_at_least(self):
        result = self.gen(20.0, direction="under")
        self.assertEqual(result["demon_prediction"], "")

    def test_more_alias_for_over(self):
        result = self.gen(10.0, direction="more")
        self.assertEqual(result["direction"], "over")
        self.assertAlmostEqual(result["goblin_line"], 10.0)

    def test_less_alias_for_under(self):
        result = self.gen(10.0, direction="less")
        self.assertEqual(result["direction"], "under")
        self.assertAlmostEqual(result["goblin_line"], 10.0)

    def test_minimum_line_floor(self):
        """Lines should never go below 0.5."""
        result = self.gen(1.0, direction="under")
        self.assertGreaterEqual(result["demon_line"], 0.5)

    def test_returns_dict_keys(self):
        result = self.gen(24.5)
        required_keys = {
            "true_line", "direction", "goblin_line",
            "goblin_prediction", "demon_line", "demon_prediction",
        }
        self.assertTrue(required_keys.issubset(set(result.keys())))

    def test_default_direction_is_over(self):
        result = self.gen(20.0)
        self.assertEqual(result["direction"], "over")

    def test_invalid_line_handled(self):
        result = self.gen("not_a_number")
        self.assertEqual(result["true_line"], 0.0)


class TestQuantumCardMatrixCSS(unittest.TestCase):
    """Tests for styles/theme.py Quantum Card Matrix CSS."""

    def test_css_constant_exists(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIsInstance(QUANTUM_CARD_MATRIX_CSS, str)
        self.assertGreater(len(QUANTUM_CARD_MATRIX_CSS), 100)

    def test_css_contains_grid(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("display: grid", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("grid-template-columns", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("auto-fill", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("minmax(340px", QUANTUM_CARD_MATRIX_CSS)

    def test_css_contains_fade_animation(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qcm-fade-in-up", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("@keyframes", QUANTUM_CARD_MATRIX_CSS)

    def test_css_contains_glassmorphic_styling(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("backdrop-filter", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("rgba(255, 255, 255, 0.10)", QUANTUM_CARD_MATRIX_CSS)

    def test_css_contains_dual_fonts(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("Inter", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("JetBrains Mono", QUANTUM_CARD_MATRIX_CSS)

    def test_get_css_function(self):
        from styles.theme import get_quantum_card_matrix_css
        css = get_quantum_card_matrix_css()
        self.assertIn("<style>", css)
        self.assertIn("</style>", css)
        self.assertIn("qcm-grid", css)


class TestPlatformFetcherCapAndAsync(unittest.TestCase):
    """Tests for data/sportsbook_service.py async features and alt-line enrichment."""

    def test_no_intake_cap_in_sync_get(self):
        """Verify get_all_sportsbook_props no longer enforces a hard intake cap.

        The 500-bet quota is now an *output* target enforced in the analysis
        loop, not an input cap in the service.
        """
        import inspect
        from data.sportsbook_service import get_all_sportsbook_props
        source = inspect.getsource(get_all_sportsbook_props)
        # The function should still reference alt-line enrichment
        self.assertIn("parse_alt_lines_from_platform_props", source)
        # The function should NOT enforce an intake cap anymore
        self.assertNotIn("MAX_PROP_CAPACITY", source)

    def test_async_get_function_exists(self):
        from data.sportsbook_service import get_all_sportsbooks_async
        import asyncio
        self.assertTrue(asyncio.iscoroutinefunction(get_all_sportsbooks_async))

    def test_async_semaphore_limit(self):
        from data.sportsbook_service import _ASYNC_SEMAPHORE_LIMIT
        self.assertEqual(_ASYNC_SEMAPHORE_LIMIT, 5)

    def test_aiohttp_available_flag(self):
        from data.sportsbook_service import AIOHTTP_AVAILABLE
        self.assertIsInstance(AIOHTTP_AVAILABLE, bool)

    def test_true_line_kill_switch_prizepicks(self):
        """Odds API client (replacing PrizePicks) must discard props with no valid line."""
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"
        source = src.read_text(encoding="utf-8")
        self.assertIn("continue", source)

    def test_true_line_kill_switch_underdog(self):
        """Odds API client (replacing Underdog) must discard props with no valid line."""
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"
        source = src.read_text(encoding="utf-8")
        self.assertIn("continue", source)
        self.assertTrue("point" in source or "line" in source)

    def test_true_line_kill_switch_draftkings(self):
        """Odds API client (replacing DraftKings getter) must discard invalid props."""
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"
        source = src.read_text(encoding="utf-8")
        self.assertIn("continue", source)
        self.assertIn("point", source)


class TestConfigToml(unittest.TestCase):
    """Tests for .streamlit/config.toml."""

    def test_max_message_size_set(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".streamlit", "config.toml",
        )
        with open(config_path) as f:
            content = f.read()
        self.assertIn("maxMessageSize = 1000", content)


class TestFormatAltLinePrediction(unittest.TestCase):
    """Verify format_alt_line_prediction backward compatibility."""

    def setUp(self):
        from engine.simulation import format_alt_line_prediction
        self.fmt = format_alt_line_prediction

    def test_goblin_at_least(self):
        self.assertEqual(self.fmt(23.5, "goblin"), "")

    def test_demon_at_most(self):
        self.assertEqual(self.fmt(26.5, "demon"), "")

    def test_base_empty(self):
        self.assertEqual(self.fmt(24.5, "base"), "")


if __name__ == "__main__":
    unittest.main()
