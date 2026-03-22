"""
tests/test_vegas_vault.py
-------------------------
Tests for the Vegas Vault feature:
  - calculate_implied_probability (appended to odds_api_client)
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
        from data.odds_api_client import calculate_implied_probability
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
        self.assertIn("fetch_player_props", source)
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


if __name__ == "__main__":
    unittest.main()
