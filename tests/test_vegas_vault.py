"""
tests/test_vegas_vault.py
-------------------------
Tests for the Vegas Vault feature:
  - calculate_implied_probability (appended to odds_client)
  - find_ev_discrepancies (engine/arbitrage_matcher)
  - joseph_vault_reaction (appended to joseph_brain)
  - pages/15_🎰_Vegas_Vault.py (file structure)
  - implied_probability_to_american_odds (reverse converter)
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
        from data.odds_client import calculate_implied_probability
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

    def test_minus_300_is_75(self):
        # -300 => 75%
        result = self.calc(-300)
        self.assertAlmostEqual(result, 75.0, delta=0.1)

    def test_plus_200_is_33(self):
        # +200 => 33.33%
        result = self.calc(+200)
        self.assertAlmostEqual(result, 33.33, delta=0.1)


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

    def test_missing_fields_skipped(self):
        """Props with missing required fields should be silently skipped."""
        props = [
            {"player_name": "", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +100},
            {"stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -200, "under_odds": +100},
            {"player_name": "Test", "stat_type": "", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +100},
        ]
        # Should not crash, just skip invalid props
        result = self.find(props)
        self.assertIsInstance(result, list)

    def test_ev_edge_value(self):
        """Verify ev_edge is computed as max(implied_probs) - 50."""
        props = [
            {"player_name": "Star", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        if result:
            d = result[0]
            max_prob = max(d["best_over_implied_prob"], d["best_under_implied_prob"])
            expected_edge = round(max_prob - 50.0, 2)
            self.assertAlmostEqual(d["ev_edge"], expected_edge, places=1)


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

    def test_joseph_no_god_mode_still_works(self):
        """Joseph mode without any god mode locks should still produce a rant."""
        mock = [
            {"ev_edge": 8.0, "is_god_mode_lock": False,
             "best_over_implied_prob": 58.0, "best_under_implied_prob": 47.0},
        ]
        result = self.react(mock, mode="joseph")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 20)
        # Should NOT mention GOD MODE since none present
        self.assertNotIn("GOD MODE", result)

    def test_professor_references_top_edge(self):
        """Professor mode should reference the top finding's probability."""
        mock = [
            {"ev_edge": 11.5, "is_god_mode_lock": True,
             "best_over_implied_prob": 61.5, "best_under_implied_prob": 47.6},
        ]
        result = self.react(mock, mode="professor")
        # Should mention the top probability or edge
        self.assertTrue(
            "61.5" in result or "11.5" in result,
            f"Professor should reference specific numbers: {result}",
        )

    def test_multiple_discrepancies_count(self):
        """Joseph mode should reference the count of discrepancies."""
        mock = [
            {"ev_edge": 11.0, "is_god_mode_lock": True,
             "best_over_implied_prob": 61.0, "best_under_implied_prob": 47.0},
            {"ev_edge": 9.0, "is_god_mode_lock": False,
             "best_over_implied_prob": 59.0, "best_under_implied_prob": 46.0},
            {"ev_edge": 8.0, "is_god_mode_lock": False,
             "best_over_implied_prob": 58.0, "best_under_implied_prob": 45.0},
        ]
        result = self.react(mock, mode="joseph")
        self.assertIn("3", result, f"Should mention count of 3: {result}")


# ============================================================
# 4. Reverse odds converter tests
# ============================================================

class TestImpliedProbToAmericanOdds(unittest.TestCase):
    """Tests for implied_probability_to_american_odds in odds_engine.py."""

    def setUp(self):
        from engine.odds_engine import implied_probability_to_american_odds
        self.convert = implied_probability_to_american_odds

    def test_favourite_60_pct(self):
        # 60% => -150
        result = self.convert(0.60)
        self.assertAlmostEqual(result, -150.0, delta=1.0)

    def test_underdog_40_pct(self):
        # 40% => +150
        result = self.convert(0.40)
        self.assertAlmostEqual(result, 150.0, delta=1.0)

    def test_even_50_pct(self):
        # 50% should be around -100 or +100
        result = self.convert(0.50)
        self.assertAlmostEqual(abs(result), 100.0, delta=1.0)

    def test_heavy_favourite(self):
        # 75% => -300
        result = self.convert(0.75)
        self.assertAlmostEqual(result, -300.0, delta=1.0)

    def test_roundtrip(self):
        """Converting probability back to odds should be inverse of odds→prob."""
        from data.odds_client import calculate_implied_probability
        original_odds = -145
        prob = calculate_implied_probability(original_odds) / 100.0
        recovered_odds = self.convert(prob)
        self.assertAlmostEqual(recovered_odds, float(original_odds), delta=1.0)


# ============================================================
# 5. Vegas Vault page file structure tests
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
        self.assertIn("get_player_props", source)
        self.assertIn("find_ev_discrepancies", source)
        self.assertIn("joseph_vault_reaction", source)
        self.assertIn("calculate_implied_probability", source)

    def test_has_section_0_css(self):
        """Page must have Section 0 with custom CSS."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("SECTION 0", source)
        self.assertIn("<style>", source)
        self.assertIn("god-mode-card", source)
        self.assertIn("ev-card", source)

    def test_has_section_1_header(self):
        """Page must have Section 1 header."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("SECTION 1", source)
        self.assertIn("vault-header", source)

    def test_has_section_2_controls(self):
        """Page must have Section 2 with sidebar controls."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("SECTION 2", source)
        self.assertIn("st.sidebar", source)
        self.assertIn("st.slider", source)

    def test_has_section_3_results(self):
        """Page must have Section 3 with scan logic and results."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("SECTION 3", source)
        self.assertIn("find_ev_discrepancies", source)
        self.assertIn("God Mode Locks", source)

    def test_has_section_4_tools(self):
        """Page must have Section 4 with implied probability calculator."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("SECTION 4", source)
        self.assertIn("Calculator", source)
        self.assertIn("st.tabs", source)

    def test_has_premium_gate(self):
        """Page must have premium gate."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("premium", source.lower())

    def test_has_education_section(self):
        """Page must have education/how-to section."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("How to Use", source)

    def test_has_sidebar_filters(self):
        """Page must have sidebar filter controls."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("Min EV Edge", source)
        self.assertIn("Stat Type Filter", source)
        self.assertIn("God Mode Locks Only", source)

    def test_has_download_export(self):
        """Page must have data export capability."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("download_button", source)

    def test_has_data_table(self):
        """Page must have tabular data display."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("st.dataframe", source)

    def test_has_joseph_hero_banner(self):
        """Page must render Joseph hero banner."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("render_joseph_hero_banner", source)

    def test_has_reverse_odds_converter(self):
        """Page must import the reverse odds converter."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("implied_probability_to_american_odds", source)

    def test_has_ev_formula_reference(self):
        """Page must have EV formula reference section."""
        with open(self._PAGE_PATH, "r") as f:
            source = f.read()
        self.assertIn("EV Formula", source)


# ============================================================
# 6. arbitrage_matcher file structure tests
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

    def test_name_helpers_exist(self):
        """Internal name normalization helpers should exist."""
        from engine.arbitrage_matcher import _normalise_name, _names_match
        self.assertTrue(callable(_normalise_name))
        self.assertTrue(callable(_names_match))

    def test_normalise_name(self):
        from engine.arbitrage_matcher import _normalise_name
        self.assertEqual(_normalise_name("LeBron James"), "lebron james")
        self.assertEqual(_normalise_name("  L. James  "), "l james")

    def test_names_match_exact(self):
        from engine.arbitrage_matcher import _names_match
        self.assertTrue(_names_match("LeBron James", "lebron james"))

    def test_names_match_abbreviated(self):
        from engine.arbitrage_matcher import _names_match
        self.assertTrue(_names_match("LeBron James", "L. James"))

    def test_names_no_match(self):
        from engine.arbitrage_matcher import _names_match
        self.assertFalse(_names_match("LeBron James", "Stephen Curry"))


# ============================================================
# 6. Devig-Enhanced Fields tests
# ============================================================

class TestDevigEnhancedFields(unittest.TestCase):
    """Tests for devig-enhanced fields: recommended_side, fair_probability, etc."""

    def setUp(self):
        from engine.arbitrage_matcher import find_ev_discrepancies
        self.find = find_ev_discrepancies

    def test_recommended_side_present(self):
        """Discrepancies should include recommended_side."""
        props = [
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "DraftKings", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "FanDuel", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        self.assertIn("recommended_side", d)
        self.assertIn(d["recommended_side"], ("OVER", "UNDER"))

    def test_recommended_book_present(self):
        """Discrepancies should include recommended_book."""
        props = [
            {"player_name": "Star", "stat_type": "rebounds", "line": 10.5,
             "platform": "DraftKings", "over_odds": -170, "under_odds": +100},
            {"player_name": "Star", "stat_type": "rebounds", "line": 10.5,
             "platform": "FanDuel", "over_odds": -160, "under_odds": +110},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        self.assertIn("recommended_book", d)
        self.assertIsInstance(d["recommended_book"], str)
        self.assertGreater(len(d["recommended_book"]), 0)

    def test_fair_probability_present(self):
        """Discrepancies should include fair_probability (devigged)."""
        props = [
            {"player_name": "Star", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        self.assertIn("fair_probability", d)
        self.assertGreater(d["fair_probability"], 0.0)
        self.assertLessEqual(d["fair_probability"], 100.0)

    def test_true_ev_edge_present(self):
        """Discrepancies should include true_ev_edge (devig-adjusted)."""
        props = [
            {"player_name": "Star", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        self.assertIn("true_ev_edge", d)
        # true_ev_edge should be <= ev_edge (devig removes vig inflation)
        self.assertLessEqual(d["true_ev_edge"], d["ev_edge"] + 0.1)

    def test_fair_over_under_probs_present(self):
        """Discrepancies should include fair_over_prob and fair_under_prob."""
        props = [
            {"player_name": "Star", "stat_type": "assists", "line": 8.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star", "stat_type": "assists", "line": 8.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        self.assertIn("fair_over_prob", d)
        self.assertIn("fair_under_prob", d)
        self.assertGreater(d["fair_over_prob"], 0.0)
        self.assertGreater(d["fair_under_prob"], 0.0)
        # Fair probs should sum closer to 100 than vigged probs
        fair_sum = d["fair_over_prob"] + d["fair_under_prob"]
        self.assertAlmostEqual(fair_sum, 100.0, delta=5.0)

    def test_consensus_fair_probs_present(self):
        """Discrepancies should include consensus fair probabilities."""
        props = [
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        if result:
            d = result[0]
            self.assertIn("consensus_fair_over", d)
            self.assertIn("consensus_fair_under", d)

    def test_vig_pct_present(self):
        """Discrepancies should include vig_pct."""
        props = [
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "P", "stat_type": "points", "line": 20.5,
             "platform": "FD", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        if result:
            d = result[0]
            self.assertIn("vig_pct", d)
            self.assertGreaterEqual(d["vig_pct"], 0.0)

    def test_recommended_side_matches_highest_fair_prob(self):
        """Recommended side should match the side with higher fair probability."""
        props = [
            {"player_name": "Test", "stat_type": "points", "line": 24.5,
             "platform": "DK", "over_odds": -200, "under_odds": +120},
            {"player_name": "Test", "stat_type": "points", "line": 24.5,
             "platform": "FD", "over_odds": -180, "under_odds": +130},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        # Over odds are more aggressive => recommended_side should be OVER
        self.assertEqual(d["recommended_side"], "OVER")
        self.assertGreater(d["fair_probability"], 50.0)

    def test_recommended_side_under(self):
        """When under odds are more aggressive, recommended_side should be UNDER."""
        props = [
            {"player_name": "Underdog", "stat_type": "rebounds", "line": 9.5,
             "platform": "DK", "over_odds": +120, "under_odds": -200},
            {"player_name": "Underdog", "stat_type": "rebounds", "line": 9.5,
             "platform": "FD", "over_odds": +130, "under_odds": -180},
        ]
        result = self.find(props)
        self.assertGreaterEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d["recommended_side"], "UNDER")
        self.assertGreater(d["fair_probability"], 50.0)

    def test_backward_compatibility(self):
        """New fields must not remove any existing required fields."""
        props = [
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "DraftKings", "over_odds": -200, "under_odds": +120},
            {"player_name": "Star Player", "stat_type": "points", "line": 25.5,
             "platform": "FanDuel", "over_odds": -190, "under_odds": +130},
        ]
        result = self.find(props)
        if result:
            d = result[0]
            # All original keys must still be present
            original_keys = {
                "player_name", "stat_type", "true_line",
                "best_over_odds", "best_over_book",
                "best_under_odds", "best_under_book",
                "best_over_implied_prob", "best_under_implied_prob",
                "ev_edge", "is_god_mode_lock", "book_count",
            }
            self.assertTrue(original_keys.issubset(d.keys()))
            # New keys must also be present
            new_keys = {
                "recommended_side", "recommended_book",
                "fair_probability", "true_ev_edge",
                "fair_over_prob", "fair_under_prob",
                "consensus_fair_over", "consensus_fair_under",
                "vig_pct",
            }
            self.assertTrue(new_keys.issubset(d.keys()))
            # Win-rate enhancement keys must also be present
            win_rate_keys = {
                "kelly_fraction", "convergence_score",
                "edge_grade", "edge_grade_label",
            }
            self.assertTrue(win_rate_keys.issubset(d.keys()))


# ============================================================
# 6. Kelly Criterion Bet Sizing tests
# ============================================================

class TestKellyFractionForEdge(unittest.TestCase):
    """Tests for calculate_kelly_fraction_for_edge."""

    def setUp(self):
        from engine.arbitrage_matcher import calculate_kelly_fraction_for_edge
        self.kelly = calculate_kelly_fraction_for_edge

    def test_positive_edge_returns_positive(self):
        """A 62.5% fair prob at -145 should yield a positive Kelly fraction."""
        result = self.kelly(62.5, -145)
        self.assertGreater(result, 0.0)
        self.assertLessEqual(result, 0.05)

    def test_no_edge_returns_zero(self):
        """50% fair prob at -110 should yield 0 (no edge)."""
        result = self.kelly(50.0, -110)
        self.assertEqual(result, 0.0)

    def test_none_inputs_return_zero(self):
        """None inputs should gracefully return 0."""
        self.assertEqual(self.kelly(None, -110), 0.0)
        self.assertEqual(self.kelly(62.5, None), 0.0)
        self.assertEqual(self.kelly(None, None), 0.0)

    def test_positive_odds(self):
        """Test with underdog odds (+130)."""
        result = self.kelly(60.0, 130)
        self.assertGreater(result, 0.0)
        self.assertLessEqual(result, 0.05)

    def test_capped_at_five_percent(self):
        """Even extreme edges should be capped at 5% of bankroll."""
        result = self.kelly(90.0, -110)
        self.assertLessEqual(result, 0.05)

    def test_zero_odds_returns_zero(self):
        """Zero odds = invalid, should return 0."""
        self.assertEqual(self.kelly(60.0, 0), 0.0)

    def test_boundary_probability_100(self):
        """100% fair prob = invalid, should return 0."""
        self.assertEqual(self.kelly(100.0, -110), 0.0)

    def test_boundary_probability_0(self):
        """0% fair prob should return 0."""
        self.assertEqual(self.kelly(0.0, -110), 0.0)

    def test_higher_edge_yields_larger_kelly(self):
        """Higher fair probability should yield larger Kelly fraction."""
        low = self.kelly(57.0, -130)
        high = self.kelly(65.0, -130)
        self.assertGreater(high, low)

    def test_return_type_is_float(self):
        """Kelly fraction should always be a float."""
        result = self.kelly(62.5, -145)
        self.assertIsInstance(result, float)


# ============================================================
# 7. Convergence Score tests
# ============================================================

class TestConvergenceScore(unittest.TestCase):
    """Tests for calculate_convergence_score."""

    def setUp(self):
        from engine.arbitrage_matcher import calculate_convergence_score
        self.conv = calculate_convergence_score

    def test_single_book_low_score(self):
        """1 book with no devig should score low."""
        result = self.conv(1, 0, 5.0)
        self.assertLess(result, 30)

    def test_many_books_high_score(self):
        """5 books, 4 devig pairs, low vig should score high."""
        result = self.conv(5, 4, 1.0)
        self.assertGreater(result, 80)

    def test_medium_scenario(self):
        """3 books, 2 devig pairs, 3% vig should be medium."""
        result = self.conv(3, 2, 3.0)
        self.assertGreater(result, 40)
        self.assertLess(result, 90)

    def test_range_0_to_100(self):
        """Score should always be 0-100."""
        for books in range(1, 8):
            for devig in range(0, books + 1):
                for vig in [0, 2, 5, 10]:
                    score = self.conv(books, devig, vig)
                    self.assertGreaterEqual(score, 0)
                    self.assertLessEqual(score, 100)

    def test_more_books_increases_score(self):
        """More books should generally increase score."""
        low = self.conv(1, 1, 3.0)
        high = self.conv(5, 1, 3.0)
        self.assertGreater(high, low)

    def test_more_devig_increases_score(self):
        """More deviggable pairs should increase score."""
        low = self.conv(3, 0, 3.0)
        high = self.conv(3, 3, 3.0)
        self.assertGreater(high, low)

    def test_lower_vig_increases_score(self):
        """Lower vig should increase score."""
        low = self.conv(3, 2, 10.0)
        high = self.conv(3, 2, 1.0)
        self.assertGreater(high, low)

    def test_return_type_is_int(self):
        """Convergence score should be an integer."""
        result = self.conv(3, 2, 3.0)
        self.assertIsInstance(result, int)


# ============================================================
# 8. Edge Quality Grade tests
# ============================================================

class TestEdgeQualityGrade(unittest.TestCase):
    """Tests for grade_edge_quality."""

    def setUp(self):
        from engine.arbitrage_matcher import grade_edge_quality
        self.grade = grade_edge_quality

    def test_returns_dict_with_required_keys(self):
        """Grade output must have grade, label, score keys."""
        result = self.grade(10.0, 8.0, 3, False, 0.01, 3.0)
        self.assertIn("grade", result)
        self.assertIn("label", result)
        self.assertIn("score", result)

    def test_high_edge_gets_premium_grade(self):
        """Strong edge with god mode should get A or A+."""
        result = self.grade(15.0, 12.0, 4, True, 0.02, 3.0)
        self.assertIn(result["grade"], ("A+", "A"))

    def test_moderate_edge_gets_C(self):
        """Moderate edge should get around C."""
        result = self.grade(8.0, 6.0, 2, False, 0.005, 5.0)
        self.assertIn(result["grade"], ("C", "D"))

    def test_perfect_edge_gets_A_plus(self):
        """Maximum signals should get A+."""
        result = self.grade(20.0, 18.0, 5, True, 0.04, 2.0)
        self.assertEqual(result["grade"], "A+")

    def test_marginal_edge_gets_D_or_F(self):
        """Minimal edge with 1 book and high vig should be D or F."""
        result = self.grade(7.0, 5.0, 1, False, 0.0, 8.0)
        self.assertIn(result["grade"], ("D", "F"))

    def test_god_mode_boosts_grade(self):
        """God Mode should boost the grade vs identical non-God-Mode."""
        no_god = self.grade(10.0, 8.0, 3, False, 0.01, 3.0)
        with_god = self.grade(10.0, 8.0, 3, True, 0.01, 3.0)
        self.assertGreaterEqual(with_god["score"], no_god["score"])

    def test_score_range_0_to_100(self):
        """Score should always be 0-100."""
        for ev in [7, 10, 15, 20, 25]:
            for true_ev in [5, 8, 12, 15]:
                for books in [1, 2, 3, 5]:
                    result = self.grade(ev, true_ev, books, False, 0.01, 3.0)
                    self.assertGreaterEqual(result["score"], 0)
                    self.assertLessEqual(result["score"], 100)

    def test_grade_label_matches_grade(self):
        """Grade and label should be consistent."""
        grade_to_label = {
            "A+": "Elite Edge",
            "A": "Premium Edge",
            "B+": "Strong Edge",
            "B": "Solid Edge",
            "C": "Moderate Edge",
            "D": "Marginal Edge",
            "F": "Weak Edge",
        }
        result = self.grade(15.0, 12.0, 4, True, 0.02, 3.0)
        expected_label = grade_to_label.get(result["grade"])
        if expected_label:
            self.assertEqual(result["label"], expected_label)

    def test_invalid_inputs_return_unknown(self):
        """Invalid inputs should return ? grade gracefully."""
        result = self.grade("invalid", "bad", "x", False, 0.0, 0.0)
        self.assertEqual(result["grade"], "?")


# ============================================================
# 9. Integration: new fields in find_ev_discrepancies output
# ============================================================

class TestFindEvDiscrepanciesNewFields(unittest.TestCase):
    """Verify the new win-rate enhancement fields in discrepancy output."""

    def setUp(self):
        from engine.arbitrage_matcher import find_ev_discrepancies
        self.find = find_ev_discrepancies

    def _make_strong_props(self):
        """Create props guaranteed to produce a discrepancy."""
        return [
            {"player_name": "Big Star", "stat_type": "points", "line": 25.5,
             "platform": "DraftKings", "over_odds": -200, "under_odds": +120},
            {"player_name": "Big Star", "stat_type": "points", "line": 25.5,
             "platform": "FanDuel", "over_odds": -190, "under_odds": +130},
            {"player_name": "Big Star", "stat_type": "points", "line": 25.5,
             "platform": "BetMGM", "over_odds": -180, "under_odds": +140},
        ]

    def test_kelly_fraction_present(self):
        """Discrepancies must contain kelly_fraction field."""
        result = self.find(self._make_strong_props())
        if result:
            self.assertIn("kelly_fraction", result[0])
            self.assertIsInstance(result[0]["kelly_fraction"], float)
            self.assertGreaterEqual(result[0]["kelly_fraction"], 0.0)
            self.assertLessEqual(result[0]["kelly_fraction"], 0.05)

    def test_convergence_score_present(self):
        """Discrepancies must contain convergence_score field."""
        result = self.find(self._make_strong_props())
        if result:
            self.assertIn("convergence_score", result[0])
            self.assertIsInstance(result[0]["convergence_score"], int)
            self.assertGreaterEqual(result[0]["convergence_score"], 0)
            self.assertLessEqual(result[0]["convergence_score"], 100)

    def test_edge_grade_present(self):
        """Discrepancies must contain edge_grade and edge_grade_label fields."""
        result = self.find(self._make_strong_props())
        if result:
            self.assertIn("edge_grade", result[0])
            self.assertIn("edge_grade_label", result[0])
            self.assertIn(result[0]["edge_grade"],
                          ("A+", "A", "B+", "B", "C", "D", "F", "?"))

    def test_multi_book_convergence_higher(self):
        """3-book props should have higher convergence than 2-book."""
        two_book = [
            {"player_name": "Player X", "stat_type": "rebounds", "line": 8.5,
             "platform": "DraftKings", "over_odds": -190, "under_odds": +130},
            {"player_name": "Player X", "stat_type": "rebounds", "line": 8.5,
             "platform": "FanDuel", "over_odds": -185, "under_odds": +135},
        ]
        three_book = two_book + [
            {"player_name": "Player X", "stat_type": "rebounds", "line": 8.5,
             "platform": "BetMGM", "over_odds": -195, "under_odds": +125},
        ]
        r2 = self.find(two_book)
        r3 = self.find(three_book)
        if r2 and r3:
            self.assertGreaterEqual(
                r3[0]["convergence_score"],
                r2[0]["convergence_score"],
            )


if __name__ == "__main__":
    unittest.main()

