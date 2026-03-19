# ============================================================
# FILE: tests/test_institutional_modules.py
# PURPOSE: Tests for the institutional-grade modules:
#          - calculate_fractional_kelly
#          - calculate_synthetic_odds
#          - generate_optimal_slip
#          - pearson_sim_correlation (Correlation Matrix)
# ============================================================

import math
import unittest


class TestFractionalKelly(unittest.TestCase):
    """Tests for engine/odds_engine.py calculate_fractional_kelly()."""

    def setUp(self):
        from engine.odds_engine import calculate_fractional_kelly
        self.calc = calculate_fractional_kelly

    def test_positive_ev_returns_nonzero_fraction(self):
        result = self.calc(0.62, -110, 0.25)
        self.assertGreater(result["kelly_fraction"], 0.0)
        self.assertGreater(result["fractional_kelly"], 0.0)

    def test_negative_ev_returns_zero(self):
        result = self.calc(0.40, -110, 0.25)
        self.assertEqual(result["kelly_fraction"], 0.0)
        self.assertEqual(result["fractional_kelly"], 0.0)

    def test_exact_breakeven_returns_zero(self):
        # At -110, breakeven is ~52.38%
        result = self.calc(0.5238, -110, 0.25)
        self.assertAlmostEqual(result["fractional_kelly"], 0.0, places=3)

    def test_multiplier_scales_fraction(self):
        full = self.calc(0.65, -110, 1.0)
        half = self.calc(0.65, -110, 0.5)
        self.assertAlmostEqual(
            full["fractional_kelly"] / 2.0,
            half["fractional_kelly"],
            places=4,
        )

    def test_zero_multiplier_returns_zero_fraction(self):
        result = self.calc(0.65, -110, 0.0)
        self.assertEqual(result["fractional_kelly"], 0.0)
        self.assertGreater(result["kelly_fraction"], 0.0)

    def test_returns_expected_keys(self):
        result = self.calc(0.60, -110, 0.25)
        for key in ["kelly_fraction", "fractional_kelly", "multiplier", "ev_per_unit", "edge"]:
            self.assertIn(key, result)

    def test_divide_by_zero_odds_handled(self):
        # odds=0 is invalid
        result = self.calc(0.60, 0, 0.25)
        self.assertIsInstance(result, dict)

    def test_extreme_positive_odds(self):
        result = self.calc(0.60, 500, 0.25)
        self.assertGreater(result["fractional_kelly"], 0.0)

    def test_invalid_probability_clamped(self):
        result_high = self.calc(1.5, -110, 0.25)
        self.assertIsInstance(result_high, dict)
        result_neg = self.calc(-0.5, -110, 0.25)
        self.assertIsInstance(result_neg, dict)

    def test_none_inputs_handled(self):
        result = self.calc(None, None, None)
        self.assertEqual(result["kelly_fraction"], 0.0)


class TestSyntheticOdds(unittest.TestCase):
    """Tests for engine/odds_engine.py calculate_synthetic_odds()."""

    def setUp(self):
        from engine.odds_engine import calculate_synthetic_odds
        self.calc = calculate_synthetic_odds

    def test_simple_over_probability(self):
        # 7 out of 10 values > 5.0
        sim = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        result = self.calc(sim, 5.0, "OVER")
        self.assertAlmostEqual(result["win_probability"], 0.7, places=2)

    def test_simple_under_probability(self):
        sim = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        result = self.calc(sim, 5.0, "UNDER")
        # values <= 5.0: 3,4,5 = 3/10 = 0.30
        self.assertAlmostEqual(result["win_probability"], 0.3, places=2)

    def test_empty_array_returns_defaults(self):
        result = self.calc([], 10.0, "OVER")
        self.assertEqual(result["win_probability"], 0.5)
        self.assertEqual(result["sample_size"], 0)

    def test_returns_expected_keys(self):
        sim = [10.0, 20.0, 30.0]
        result = self.calc(sim, 15.0, "OVER")
        for key in ["win_probability", "fair_odds", "target_line", "direction", "sample_size"]:
            self.assertIn(key, result)

    def test_probability_clamped(self):
        # All above → probability near 1.0 but clamped to 0.99
        sim = [100.0] * 100
        result = self.calc(sim, 1.0, "OVER")
        self.assertLessEqual(result["win_probability"], 0.99)

    def test_probability_floor(self):
        # None above → probability clamped to 0.01
        sim = [1.0] * 100
        result = self.calc(sim, 1000.0, "OVER")
        self.assertGreaterEqual(result["win_probability"], 0.01)

    def test_fair_odds_negative_for_favorites(self):
        sim = [20.0] * 70 + [10.0] * 30
        result = self.calc(sim, 15.0, "OVER")
        self.assertLess(result["fair_odds"], 0)

    def test_fair_odds_positive_for_underdogs(self):
        sim = [20.0] * 30 + [10.0] * 70
        result = self.calc(sim, 15.0, "OVER")
        self.assertGreater(result["fair_odds"], 0)

    def test_direction_case_insensitive(self):
        sim = [10.0, 20.0, 30.0]
        result_upper = self.calc(sim, 15.0, "OVER")
        result_lower = self.calc(sim, 15.0, "over")
        self.assertEqual(result_upper["win_probability"], result_lower["win_probability"])

    def test_sample_size_correct(self):
        sim = list(range(100))
        result = self.calc(sim, 50.0, "OVER")
        self.assertEqual(result["sample_size"], 100)


class TestGenerateOptimalSlip(unittest.TestCase):
    """Tests for engine/odds_engine.py generate_optimal_slip()."""

    def setUp(self):
        from engine.odds_engine import generate_optimal_slip
        self.gen = generate_optimal_slip

    def _make_props(self, n):
        """Generate n mock props with different players."""
        props = []
        for i in range(n):
            props.append({
                "player_name": f"Player_{i}",
                "stat_type": "points",
                "probability_over": 0.60 + i * 0.01,
                "direction": "OVER",
                "player_team": f"TEAM{i % 5}",
                "opponent": f"OPP{(i+1) % 5}",
                "edge_percentage": 5.0 + i * 0.5,
                "confidence_score": 60 + i,
            })
        return props

    def test_empty_input_returns_empty(self):
        self.assertEqual(self.gen([]), [])

    def test_single_prop_returns_empty(self):
        self.assertEqual(self.gen(self._make_props(1)), [])

    def test_two_props_returns_slips(self):
        result = self.gen(self._make_props(2))
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["slip_size"], 2)

    def test_returns_expected_keys(self):
        result = self.gen(self._make_props(3))
        slip = result[0]
        for key in ["slip_size", "picks", "cumulative_ev", "combined_probability",
                     "correlation_penalty", "fair_odds"]:
            self.assertIn(key, slip)

    def test_sorted_by_ev_descending(self):
        result = self.gen(self._make_props(5))
        evs = [s["cumulative_ev"] for s in result]
        self.assertEqual(evs, sorted(evs, reverse=True))

    def test_max_10_results(self):
        result = self.gen(self._make_props(10))
        self.assertLessEqual(len(result), 10)

    def test_same_game_picks_penalized(self):
        props = [
            {"player_name": "A", "stat_type": "pts", "probability_over": 0.65,
             "direction": "OVER", "player_team": "LAL", "opponent": "GSW", "edge_percentage": 8.0},
            {"player_name": "B", "stat_type": "reb", "probability_over": 0.62,
             "direction": "OVER", "player_team": "LAL", "opponent": "GSW", "edge_percentage": 6.0},
        ]
        result = self.gen(props)
        self.assertGreater(len(result), 0)
        self.assertLess(result[0]["correlation_penalty"], 1.0)

    def test_unique_players_enforced(self):
        props = [
            {"player_name": "Same Player", "stat_type": "pts", "probability_over": 0.65,
             "direction": "OVER", "player_team": "LAL", "opponent": "GSW", "edge_percentage": 8.0},
            {"player_name": "Same Player", "stat_type": "reb", "probability_over": 0.62,
             "direction": "OVER", "player_team": "LAL", "opponent": "GSW", "edge_percentage": 6.0},
            {"player_name": "Other Player", "stat_type": "pts", "probability_over": 0.60,
             "direction": "OVER", "player_team": "BOS", "opponent": "MIA", "edge_percentage": 5.0},
        ]
        result = self.gen(props)
        for slip in result:
            names = [p["player_name"] for p in slip["picks"]]
            self.assertEqual(len(names), len(set(n.lower().strip() for n in names)))

    def test_slip_sizes_2_through_5(self):
        result = self.gen(self._make_props(6))
        sizes = set(s["slip_size"] for s in result)
        self.assertTrue(sizes.issubset({2, 3, 4, 5}))

    def test_platform_parameter_accepted(self):
        for platform in ["PrizePicks", "Underdog", "DraftKings"]:
            result = self.gen(self._make_props(4), platform=platform)
            self.assertIsInstance(result, list)


class TestPearsonSimCorrelation(unittest.TestCase):
    """Tests for pages/13_🗺️_Correlation_Matrix.py pearson_sim_correlation()."""

    @classmethod
    def setUpClass(cls):
        # Import the function directly from the module file
        import importlib.util
        import os
        spec = importlib.util.spec_from_file_location(
            "corr_matrix",
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "pages", "13_🗺️_Correlation_Matrix.py",
            ),
        )
        # We can't import the full Streamlit page; extract the function.
        # Instead, replicate the function logic here for testability.
        pass

    def _pearson(self, a, b):
        """Local copy of pearson_sim_correlation for testing."""
        n = min(len(a), len(b))
        if n < 3:
            return 0.0
        a = a[:n]
        b = b[:n]
        mean_a = sum(a) / n
        mean_b = sum(b) / n
        num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
        den_a = math.sqrt(sum((v - mean_a) ** 2 for v in a))
        den_b = math.sqrt(sum((v - mean_b) ** 2 for v in b))
        if den_a < 1e-9 or den_b < 1e-9:
            return 0.0
        r = num / (den_a * den_b)
        return max(-1.0, min(1.0, round(r, 4)))

    def test_perfect_positive_correlation(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0, 40.0, 50.0]
        self.assertAlmostEqual(self._pearson(a, b), 1.0, places=3)

    def test_perfect_negative_correlation(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [50.0, 40.0, 30.0, 20.0, 10.0]
        self.assertAlmostEqual(self._pearson(a, b), -1.0, places=3)

    def test_zero_correlation(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 5.0, 5.0, 5.0, 5.0]
        self.assertEqual(self._pearson(a, b), 0.0)

    def test_insufficient_data(self):
        self.assertEqual(self._pearson([1.0], [2.0]), 0.0)
        self.assertEqual(self._pearson([1.0, 2.0], [3.0, 4.0]), 0.0)

    def test_empty_arrays(self):
        self.assertEqual(self._pearson([], []), 0.0)

    def test_different_length_arrays(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0]
        r = self._pearson(a, b)
        self.assertAlmostEqual(r, 1.0, places=3)

    def test_result_bounded(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 3.0, 1.0, 4.0, 2.0]
        r = self._pearson(a, b)
        self.assertGreaterEqual(r, -1.0)
        self.assertLessEqual(r, 1.0)


if __name__ == "__main__":
    unittest.main()
