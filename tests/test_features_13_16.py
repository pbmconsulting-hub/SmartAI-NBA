# ============================================================
# FILE: tests/test_features_13_16.py
# PURPOSE: Tests for Features 13–16:
#          - 13: Sticky Summary Dashboard CSS
#          - 14: Quick Filter Chips CSS
#          - 15: Sort Controls CSS
#          - 16: Collapsible Game Groups CSS
# ============================================================

import unittest


class TestStickySummaryCSS(unittest.TestCase):
    """Feature 13: Verify sticky summary CSS class exists."""

    def test_sticky_summary_class_exists(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-sticky-summary", QUANTUM_CARD_MATRIX_CSS)

    def test_sticky_position(self):
        """qam-sticky-summary should NOT use position:sticky (removed to
        prevent scroll-triggered layout thrashing on mobile)."""
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertNotIn("position: sticky", QUANTUM_CARD_MATRIX_CSS)

    def test_sticky_z_index(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("z-index: 10", QUANTUM_CARD_MATRIX_CSS)

    def test_sticky_backdrop_blur(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("backdrop-filter: blur", QUANTUM_CARD_MATRIX_CSS)


class TestFilterChipCSS(unittest.TestCase):
    """Feature 14: Verify filter chip CSS classes exist."""

    def test_filter_bar_class(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-filter-bar", QUANTUM_CARD_MATRIX_CSS)

    def test_filter_chip_class(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-filter-chip", QUANTUM_CARD_MATRIX_CSS)

    def test_filter_chip_active_class(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-filter-chip-active", QUANTUM_CARD_MATRIX_CSS)

    def test_chip_tier_variants(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-filter-chip-platinum", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn(".qam-filter-chip-gold", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn(".qam-filter-chip-edge", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn(".qam-filter-chip-form", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn(".qam-filter-chip-avoid", QUANTUM_CARD_MATRIX_CSS)

    def test_chip_has_hover(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-filter-chip:hover", QUANTUM_CARD_MATRIX_CSS)

    def test_chip_has_border_radius(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("border-radius: 20px", QUANTUM_CARD_MATRIX_CSS)


class TestSortControlCSS(unittest.TestCase):
    """Feature 15: Verify sort control CSS classes exist."""

    def test_sort_bar_class(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-sort-bar", QUANTUM_CARD_MATRIX_CSS)

    def test_sort_bar_label_class(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-sort-bar-label", QUANTUM_CARD_MATRIX_CSS)


class TestGameGroupCSS(unittest.TestCase):
    """Feature 16: Verify collapsible game group CSS classes exist."""

    def test_game_group_class(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group", QUANTUM_CARD_MATRIX_CSS)

    def test_game_group_header(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group-header", QUANTUM_CARD_MATRIX_CSS)

    def test_game_group_matchup(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group-matchup", QUANTUM_CARD_MATRIX_CSS)

    def test_game_group_meta(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group-meta", QUANTUM_CARD_MATRIX_CSS)

    def test_game_group_badge(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group-badge", QUANTUM_CARD_MATRIX_CSS)

    def test_game_group_body(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group-body", QUANTUM_CARD_MATRIX_CSS)

    def test_game_group_header_hover(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn(".qam-game-group-header:hover", QUANTUM_CARD_MATRIX_CSS)


class TestDataGrouperIntegration(unittest.TestCase):
    """Test the data grouper still works for game grouping."""

    def test_group_props_by_player_basic(self):
        from utils.data_grouper import group_props_by_player
        results = [
            {"player_name": "LeBron James", "team": "LAL"},
            {"player_name": "LeBron James", "team": "LAL"},
            {"player_name": "Anthony Davis", "team": "LAL"},
        ]
        grouped = group_props_by_player(results)
        self.assertIn("LeBron James", grouped)
        self.assertIn("Anthony Davis", grouped)
        self.assertEqual(len(grouped["LeBron James"]["props"]), 2)
        self.assertEqual(len(grouped["Anthony Davis"]["props"]), 1)

    def test_group_props_empty(self):
        from utils.data_grouper import group_props_by_player
        self.assertEqual(group_props_by_player([]), {})

    def test_group_props_skips_no_name(self):
        from utils.data_grouper import group_props_by_player
        results = [
            {"player_name": "", "team": "LAL"},
            {"player_name": "LeBron James", "team": "LAL"},
        ]
        grouped = group_props_by_player(results)
        self.assertNotIn("", grouped)
        self.assertIn("LeBron James", grouped)


if __name__ == "__main__":
    unittest.main()
