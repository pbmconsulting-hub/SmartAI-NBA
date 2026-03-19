# ============================================================
# FILE: tests/test_alt_line_logic.py
# PURPOSE: Tests for the Alt-Line Singularity (Goblin & Demon)
#          logic — engine layer, prediction layer, and formatters.
# ============================================================

import unittest


class TestGenerateAltLineProbabilities(unittest.TestCase):
    """Tests for engine/simulation.py generate_alt_line_probabilities()."""

    def setUp(self):
        from engine.simulation import generate_alt_line_probabilities
        self.gen = generate_alt_line_probabilities

    def _mock_sim_output(self, results, prob_over=0.5):
        return {
            "simulated_results": results,
            "probability_over": prob_over,
        }

    def test_goblin_lines_are_below_base(self):
        sim = self._mock_sim_output([float(x) for x in range(5, 15)], 0.6)
        result = self.gen(sim, 7.5)
        for g in result["goblin_lines"]:
            self.assertLess(g["line"], 7.5)

    def test_demon_lines_are_above_base(self):
        sim = self._mock_sim_output([float(x) for x in range(5, 15)], 0.6)
        result = self.gen(sim, 7.5)
        for d in result["demon_lines"]:
            self.assertGreater(d["line"], 7.5)

    def test_goblin_offsets_correct(self):
        sim = self._mock_sim_output([10.0] * 100, 0.8)
        result = self.gen(sim, 10.0)
        goblin_lines = [g["line"] for g in result["goblin_lines"]]
        self.assertEqual(goblin_lines, [9.0, 8.0, 7.0])

    def test_demon_offsets_correct(self):
        sim = self._mock_sim_output([10.0] * 100, 0.8)
        result = self.gen(sim, 10.0)
        demon_lines = [d["line"] for d in result["demon_lines"]]
        self.assertEqual(demon_lines, [12.0, 14.0, 16.0])

    def test_three_goblin_three_demon(self):
        sim = self._mock_sim_output([10.0] * 50, 0.5)
        result = self.gen(sim, 10.0)
        self.assertEqual(len(result["goblin_lines"]), 3)
        self.assertEqual(len(result["demon_lines"]), 3)

    def test_goblin_probability_is_gte(self):
        """Goblin probability = P(stat >= goblin_line)."""
        # 10 results: 5,6,7,8,9,10,11,12,13,14
        sim = self._mock_sim_output([float(x) for x in range(5, 15)], 0.6)
        result = self.gen(sim, 7.5)
        # Goblin L-1 = 6.5 → values >= 6.5 are: 7,8,9,10,11,12,13,14 = 8/10 = 0.8
        g1 = result["goblin_lines"][0]
        self.assertEqual(g1["line"], 6.5)
        self.assertAlmostEqual(g1["probability"], 0.8, places=2)

    def test_demon_probability_is_lte(self):
        """Demon probability = P(stat <= demon_line)."""
        # 10 results: 5,6,7,8,9,10,11,12,13,14
        sim = self._mock_sim_output([float(x) for x in range(5, 15)], 0.6)
        result = self.gen(sim, 7.5)
        # Demon L+2 = 9.5 → values <= 9.5 are: 5,6,7,8,9 = 5/10 = 0.5
        d1 = result["demon_lines"][0]
        self.assertEqual(d1["line"], 9.5)
        self.assertAlmostEqual(d1["probability"], 0.5, places=2)

    def test_best_alt_has_highest_probability(self):
        sim = self._mock_sim_output([float(x) for x in range(5, 15)], 0.6)
        result = self.gen(sim, 7.5)
        best = result["best_alt"]
        all_probs = (
            [g["probability"] for g in result["goblin_lines"]]
            + [d["probability"] for d in result["demon_lines"]]
            + [result["base_probability"]]
        )
        self.assertEqual(best["probability"], max(all_probs))

    def test_best_alt_goblin_has_at_least_prediction(self):
        sim = self._mock_sim_output([float(x) for x in range(5, 15)], 0.3)
        result = self.gen(sim, 7.5)
        best = result["best_alt"]
        if best["type"] == "goblin":
            self.assertIn("at LEAST", best["prediction"])

    def test_empty_simulation_returns_empty_structure(self):
        sim = self._mock_sim_output([], 0.5)
        result = self.gen(sim, 10.0)
        self.assertEqual(result["goblin_lines"], [])
        self.assertEqual(result["demon_lines"], [])
        self.assertEqual(result["best_alt"]["type"], "base")

    def test_negative_goblin_line_floors_at_half(self):
        """If base line is very low, goblin lines floor at 0.5."""
        sim = self._mock_sim_output([1.0, 2.0, 3.0], 0.5)
        result = self.gen(sim, 1.5)
        # L-2.0 = -0.5 → should floor at 0.5
        g2 = result["goblin_lines"][1]
        self.assertGreaterEqual(g2["line"], 0.5)
        # L-3.0 = -1.5 → should floor at 0.5
        g3 = result["goblin_lines"][2]
        self.assertGreaterEqual(g3["line"], 0.5)

    def test_probabilities_clamped(self):
        """All probabilities should be in [0.01, 0.99]."""
        sim = self._mock_sim_output([100.0] * 100, 0.99)
        result = self.gen(sim, 10.0)
        for g in result["goblin_lines"]:
            self.assertGreaterEqual(g["probability"], 0.01)
            self.assertLessEqual(g["probability"], 0.99)
        for d in result["demon_lines"]:
            self.assertGreaterEqual(d["probability"], 0.01)
            self.assertLessEqual(d["probability"], 0.99)


class TestFormatAltLinePrediction(unittest.TestCase):
    """Tests for engine/simulation.py format_alt_line_prediction()."""

    def setUp(self):
        from engine.simulation import format_alt_line_prediction
        self.fmt = format_alt_line_prediction

    def test_goblin_prediction_string(self):
        result = self.fmt(6.5, "goblin")
        self.assertEqual(result, "I predict the stat will do at LEAST 6.5")

    def test_demon_prediction_string(self):
        result = self.fmt(9.5, "demon")
        self.assertEqual(result, "I predict the stat will do at MOST 9.5")

    def test_base_returns_empty(self):
        result = self.fmt(7.5, "base")
        self.assertEqual(result, "")

    def test_unknown_type_returns_empty(self):
        result = self.fmt(7.5, "foobar")
        self.assertEqual(result, "")


class TestFormatGoblinDemonPrediction(unittest.TestCase):
    """Tests for engine/edge_detection.py format_goblin_demon_prediction()."""

    def setUp(self):
        from engine.edge_detection import format_goblin_demon_prediction
        self.fmt = format_goblin_demon_prediction

    def test_goblin_string(self):
        self.assertEqual(
            self.fmt("goblin", 12.5),
            "I predict the stat will do at LEAST 12.5",
        )

    def test_demon_string(self):
        self.assertEqual(
            self.fmt("demon", 34.5),
            "I predict the stat will do at MOST 34.5",
        )

    def test_normal_returns_empty(self):
        self.assertEqual(self.fmt("normal", 20.0), "")

    def test_50_50_returns_empty(self):
        self.assertEqual(self.fmt("50_50", 20.0), "")


class TestAltLineConstants(unittest.TestCase):
    """Verify the Goblin and Demon offset constants."""

    def test_goblin_offsets(self):
        from engine.simulation import GOBLIN_OFFSETS
        self.assertEqual(GOBLIN_OFFSETS, [-1.0, -2.0, -3.0])

    def test_demon_offsets(self):
        from engine.simulation import DEMON_OFFSETS
        self.assertEqual(DEMON_OFFSETS, [2.0, 4.0, 6.0])

    def test_goblin_lines_subtract(self):
        """Goblin lines should always be base - offset."""
        from engine.simulation import GOBLIN_OFFSETS
        base = 20.0
        for offset in GOBLIN_OFFSETS:
            self.assertLess(base + offset, base)

    def test_demon_lines_add(self):
        """Demon lines should always be base + offset."""
        from engine.simulation import DEMON_OFFSETS
        base = 20.0
        for offset in DEMON_OFFSETS:
            self.assertGreater(base + offset, base)


if __name__ == "__main__":
    unittest.main()
