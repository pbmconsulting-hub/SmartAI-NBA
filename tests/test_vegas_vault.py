"""
tests/test_vegas_vault.py
-------------------------
Tests for the Vegas Vault feature:
  - calculate_implied_probability (appended to odds_api_client)
  - find_ev_discrepancies (engine/arbitrage_matcher)
  - joseph_vault_reaction (appended to joseph_brain)
  - pages/15_🎰_Vegas_Vault.py (file structure)
"""

import unittest
import os
import ast


# ============================================================
# 1. calculate_implied_probability tests
# ============================================================

class TestCalculateImpliedProbability(unittest.TestCase):
    """Tests for the calculate_implied_probability helper."""

    def setUp(self):
        from data.odds_api_client import calculate_implied_probability
        self.calc = calculate_implied_probability

    def test_negative_odds(self):
        # -110 => 52.38%
        result = self.calc(-110)
        self.assertAlmostEqual(result, 52.38, delta=0.1)

    def test_heavy_favourite(self):
        # -200 => 66.67%
        result = self.calc(-200)
        self.assertAlmostEqual(result, 66.67, delta=0.1)

    def test_positive_odds(self):
        # +150 => 40%
        result = self.calc(+150)
        self.assertAlmostEqual(result, 40.0, delta=0.1)

    def test_even_odds(self):
        # +100 => 50%
        result = self.calc(+100)
        self.assertAlmostEqual(result, 50.0, delta=0.1)

    def test_returns_percentage_form(self):
        """Result should be 0-100, not 0-1."""
        result = self.calc(-110)
        self.assertGreater(result, 1.0)

    def test_minus_150_is_60(self):
        # -150 => 60%
        result = self.calc(-150)
        self.assertAlmostEqual(result, 60.0, delta=0.1)


# ============================================================
# 2. find_ev_discrepancies tests
# ============================================================

class TestFindEvDiscrepancies(unittest.TestCase):
    """Tests for find_ev_discrepancies in arbitrage_matcher."""

    def setUp(self):
        from engine.arbitrage_matcher import find_ev_discrepancies
        self.find = find_ev_discrepancies

    def test_empty_input(self):
        self.assertEqual(self.find([]), [])

    def test_none_input(self):
        self.assertEqual(self.find(None), [])

    def test_single_book_no_discrepancy(self):
        """Single book at -110 both sides => ~52.4% implied => edge ~2.4% => filtered out."""
        props = [
            {"player_name": "Test Player", "stat_type": "points", "line": 20.5,
             "platform": "DraftKings", "over_odds": -110, "under_odds": -110},
        ]
        result = self.find(props)
        self.assertEqual(result, [])

    def test_high_edge_passes_filter(self):
        """Strongly favoured over (-200 = 66.7%) should pass the >=7% filter."""
        props = [
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "DraftKings", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "FanDuel", "over_odds": -180, "under_odds": +130},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        self.assertGreaterEqual(result[0]["ev_edge"], 7.0)

    def test_output_shape(self):
        """Each discrepancy dict must have the required keys."""
        props = [
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "DraftKings", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "FanDuel", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        if result:
            d = result[0]
            required_keys = {
                "player_name", "stat_type", "true_line",
                "best_over_odds", "best_over_book",
                "best_under_odds", "best_under_book",
                "best_over_implied_prob", "best_under_implied_prob",
                "ev_edge", "is_god_mode_lock", "book_count",
            }
            self.assertTrue(required_keys.issubset(d.keys()))

    def test_god_mode_flag(self):
        """Odds <= -150 (60% implied) should flag is_god_mode_lock."""
        props = [
            {"player_name": "Alpha", "stat_type": "rebounds", "line": 10.5,
             "platform": "DraftKings", "over_odds": -170, "under_odds": +100},
            {"player_name": "Alpha", "stat_type": "rebounds", "line": 10.5,
             "platform": "FanDuel", "over_odds": -160, "under_odds": +110},
        ]
        result = self.find(props)
        self.assertTrue(len(result) >= 1)
        self.assertTrue(result[0]["is_god_mode_lock"])

    def test_sorted_by_edge_descending(self):
        """Results must be sorted by ev_edge descending."""
        props = [
            {"player_name": "A", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -160, "under_odds": +100},
            {"player_name": "A", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -155, "under_odds": +105},
            {"player_name": "B", "stat_type": "assists", "line": 5.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "B", "stat_type": "assists", "line": 5.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        for i in range(len(result) - 1):
            self.assertGreaterEqual(result[i]["ev_edge"], result[i + 1]["ev_edge"])

    def test_name_normalization(self):
        """'LeBron James' and 'L. James' should match."""
        props = [
            {"player_name": "LeBron James", "stat_type": "points", "line": 24.5,
             "platform": "DraftKings", "over_odds": -180, "under_odds": +100},
            {"player_name": "L. James", "stat_type": "points", "line": 24.5,
             "platform": "FanDuel", "over_odds": -170, "under_odds": +110},
        ]
        result = self.find(props)
        # They should merge into a single group.
        names = [d["player_name"] for d in result]
        # Should not have two separate entries for James
        james_count = sum(1 for n in names if "james" in n.lower())
        self.assertLessEqual(james_count, 1)

    def test_different_lines_not_grouped(self):
        """Props with different lines should NOT merge."""
        props = [
            {"player_name": "Test", "stat_type": "points", "line": 24.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "Test", "stat_type": "points", "line": 25.5,
             "platform": "FD", "over_odds": -200, "under_odds": +120},
        ]
        result = self.find(props)
        # Each line is independent; both should be found (or neither, depending on edge).
        lines = [d["true_line"] for d in result]
        if len(lines) > 1:
            self.assertNotEqual(lines[0], lines[1])

    def test_book_count(self):
        """book_count should reflect the number of platforms."""
        props = [
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +100},
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -190, "under_odds": +110},
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "BetMGM", "over_odds": -185, "under_odds": +115},
        ]
        result = self.find(props)
        if result:
            self.assertEqual(result[0]["book_count"], 3)


# ============================================================
# 3. joseph_vault_reaction tests
# ============================================================

class TestJosephVaultReaction(unittest.TestCase):
    """Tests for joseph_vault_reaction in joseph_brain.py."""

    def setUp(self):
        from engine.joseph_brain import joseph_vault_reaction
        self.react = joseph_vault_reaction

    def test_empty_joseph_mode(self):
        result = self.react([], mode="joseph")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 10)

    def test_empty_professor_mode(self):
        result = self.react([], mode="professor")
        self.assertIsInstance(result, str)
        self.assertIn("efficiently priced", result.lower())

    def test_joseph_mentions_sharp_money_or_vegas(self):
        mock = [
            {"ev_edge": 11.0, "is_god_mode_lock": True,
             "best_over_implied_prob": 61.0, "best_under_implied_prob": 47.0},
        ]
        result = self.react(mock, mode="joseph")
        lower = result.lower()
        has_keyword = any(k in lower for k in ["sharp", "vegas", "dfs", "window", "sleep"])
        self.assertTrue(has_keyword, f"Joseph rant missing keywords: {result}")

    def test_joseph_god_mode_reference(self):
        mock = [
            {"ev_edge": 12.0, "is_god_mode_lock": True,
             "best_over_implied_prob": 62.0, "best_under_implied_prob": 45.0},
        ]
        result = self.react(mock, mode="joseph")
        self.assertIn("GOD MODE", result)

    def test_professor_mentions_ev(self):
        mock = [
            {"ev_edge": 8.5, "is_god_mode_lock": False,
             "best_over_implied_prob": 58.5, "best_under_implied_prob": 48.0},
        ]
        result = self.react(mock, mode="professor")
        lower = result.lower()
        has_keyword = any(k in lower for k in ["expected value", "implied probability", "inefficiency", "mathematics"])
        self.assertTrue(has_keyword, f"Professor missing keywords: {result}")

    def test_return_type(self):
        result = self.react([], mode="joseph")
        self.assertIsInstance(result, str)


# ============================================================
# 4. Vegas Vault page file structure tests
# ============================================================

class TestVegasVaultPageFile(unittest.TestCase):
    """Tests that the page file exists and has correct structure."""

    _PAGE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "pages", "15_🎰_Vegas_Vault.py",
    )

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._PAGE_PATH), "Page file missing")

    def test_valid_python_syntax(self):
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        ast.parse(source)

    def test_page_config_present(self):
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("set_page_config", source)
        self.assertIn("Vegas Vault", source)

    def test_imports_guarded(self):
        """Major imports should use try/except guards."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("try:", source)
        self.assertIn("except ImportError:", source)

    def test_imports_required_modules(self):
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("fetch_player_props", source)
        self.assertIn("find_ev_discrepancies", source)
        self.assertIn("joseph_vault_reaction", source)
        self.assertIn("calculate_implied_probability", source)


# ============================================================
# 5. arbitrage_matcher file structure tests
# ============================================================

class TestArbitrageMatcherFileStructure(unittest.TestCase):
    """Tests that the arbitrage matcher module exists and is importable."""

    def test_module_importable(self):
        from engine.arbitrage_matcher import find_ev_discrepancies
        self.assertTrue(callable(find_ev_discrepancies))

    def test_file_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "engine", "arbitrage_matcher.py",
        )
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
