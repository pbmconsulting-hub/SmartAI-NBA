"""
tests/test_joseph_brain.py
Unit-tests for engine/joseph_brain.py — Layer 4, Part A (data pools & stubs).
"""

import sys
import os
import unittest

# Ensure repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Section A: Fragment Pool structure & counts ──────────────


class TestOpenerPool(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import OPENER_POOL
        self.pool = OPENER_POOL

    def test_count(self):
        """OPENER_POOL has exactly 15 entries."""
        self.assertEqual(len(self.pool), 15)

    def test_ids_sequential(self):
        """IDs are opener_01 through opener_15."""
        expected = [f"opener_{i:02d}" for i in range(1, 16)]
        self.assertEqual([e["id"] for e in self.pool], expected)

    def test_all_have_text(self):
        """Every entry has a non-empty 'text' field."""
        for entry in self.pool:
            self.assertIn("text", entry)
            self.assertIsInstance(entry["text"], str)
            self.assertTrue(len(entry["text"]) > 0)


class TestPivotPool(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import PIVOT_POOL
        self.pool = PIVOT_POOL

    def test_count(self):
        """PIVOT_POOL has exactly 10 entries."""
        self.assertEqual(len(self.pool), 10)

    def test_ids_sequential(self):
        expected = [f"pivot_{i:02d}" for i in range(1, 11)]
        self.assertEqual([e["id"] for e in self.pool], expected)


class TestCloserPool(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import CLOSER_POOL
        self.pool = CLOSER_POOL

    def test_count(self):
        """CLOSER_POOL has exactly 10 entries."""
        self.assertEqual(len(self.pool), 10)

    def test_ids_sequential(self):
        expected = [f"closer_{i:02d}" for i in range(1, 11)]
        self.assertEqual([e["id"] for e in self.pool], expected)


class TestCatchphrasePool(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import CATCHPHRASE_POOL
        self.pool = CATCHPHRASE_POOL

    def test_count(self):
        """CATCHPHRASE_POOL has exactly 13 entries."""
        self.assertEqual(len(self.pool), 13)

    def test_ids_sequential(self):
        expected = [f"catch_{i:02d}" for i in range(1, 14)]
        self.assertEqual([e["id"] for e in self.pool], expected)


# ── Body Templates ───────────────────────────────────────────


class TestBodyTemplates(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import BODY_TEMPLATES
        self.templates = BODY_TEMPLATES

    def test_verdict_keys(self):
        """BODY_TEMPLATES contains exactly the 5 verdict keys."""
        expected = {"SMASH", "LEAN", "FADE", "STAY_AWAY", "OVERRIDE"}
        self.assertEqual(set(self.templates.keys()), expected)

    def test_five_templates_per_verdict(self):
        """Each verdict has exactly 5 template strings."""
        for verdict, tpls in self.templates.items():
            self.assertEqual(len(tpls), 5, f"{verdict} has {len(tpls)} templates")

    def test_placeholders_present(self):
        """Every template contains at least {player}."""
        for verdict, tpls in self.templates.items():
            for t in tpls:
                self.assertIn("{player}", t, f"Missing {{player}} in {verdict}")

    def test_templates_are_strings(self):
        for verdict, tpls in self.templates.items():
            for t in tpls:
                self.assertIsInstance(t, str)


# ── Section B: Ambient Colour Pools ─────────────────────────


class TestAmbientContextPool(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import AMBIENT_CONTEXT_POOL
        self.pool = AMBIENT_CONTEXT_POOL

    def test_has_required_contexts(self):
        """Pool covers the essential context keys."""
        for key in ("high_stakes", "rivalry", "blowout_risk", "back_to_back", "neutral"):
            self.assertIn(key, self.pool)

    def test_each_context_has_entries(self):
        for key, lines in self.pool.items():
            self.assertGreaterEqual(len(lines), 5, f"{key} has too few lines")


# ── Section C: Stat Commentary Pools ────────────────────────


class TestStatCommentaryPool(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import STAT_COMMENTARY_POOL
        self.pool = STAT_COMMENTARY_POOL

    def test_has_core_stats(self):
        for stat in ("points", "rebounds", "assists", "threes", "steals", "blocks"):
            self.assertIn(stat, self.pool)

    def test_each_stat_has_entries(self):
        for stat, lines in self.pool.items():
            self.assertGreaterEqual(len(lines), 5, f"{stat} has too few lines")


# ── Section D: Verdict Thresholds & Config ──────────────────


class TestVerdictThresholds(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import VERDICT_THRESHOLDS
        self.thresholds = VERDICT_THRESHOLDS

    def test_all_verdicts_present(self):
        for v in ("SMASH", "LEAN", "FADE", "STAY_AWAY", "OVERRIDE"):
            self.assertIn(v, self.thresholds)

    def test_smash_requires_high_edge(self):
        self.assertGreaterEqual(self.thresholds["SMASH"]["min_edge"], 6.0)


class TestJosephConfig(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import JOSEPH_CONFIG
        self.cfg = JOSEPH_CONFIG

    def test_has_max_picks(self):
        self.assertIn("max_picks_per_slate", self.cfg)
        self.assertIsInstance(self.cfg["max_picks_per_slate"], int)

    def test_has_min_edge(self):
        self.assertIn("min_edge_threshold", self.cfg)


# ── Anti-repetition state ───────────────────────────────────


class TestAntiRepetitionState(unittest.TestCase):
    def test_initial_state_empty(self):
        from engine.joseph_brain import (
            _used_fragments, _used_ambient, _used_commentary, reset_fragment_state
        )
        reset_fragment_state()
        self.assertEqual(len(_used_fragments), 0)
        self.assertEqual(len(_used_ambient), 0)
        self.assertEqual(len(_used_commentary), 0)


# ── Helper functions (implemented) ──────────────────────────


class TestPickFragment(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import (
            _pick_fragment, OPENER_POOL, reset_fragment_state
        )
        self._pick = _pick_fragment
        self.pool = OPENER_POOL
        reset_fragment_state()

    def test_returns_string(self):
        result = self._pick(self.pool, "opener")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_no_immediate_repeat(self):
        """Two consecutive picks from a large pool should differ (probabilistically)."""
        results = {self._pick(self.pool, "opener") for _ in range(15)}
        self.assertEqual(len(results), 15, "All 15 openers should be used before repeating")

    def test_empty_pool_returns_empty(self):
        result = self._pick([], "empty")
        self.assertEqual(result, "")


class TestPickAmbient(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import _pick_ambient, reset_fragment_state
        self._pick = _pick_ambient
        reset_fragment_state()

    def test_known_context(self):
        result = self._pick("rivalry")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_unknown_context(self):
        result = self._pick("nonexistent_context")
        self.assertEqual(result, "")


class TestPickCommentary(unittest.TestCase):
    def setUp(self):
        from engine.joseph_brain import _pick_commentary, reset_fragment_state
        self._pick = _pick_commentary
        reset_fragment_state()

    def test_known_stat(self):
        result = self._pick("points")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_unknown_stat(self):
        result = self._pick("nonexistent_stat")
        self.assertEqual(result, "")


# ── Function stubs return safe defaults ─────────────────────


class TestDetermineVerdictStub(unittest.TestCase):
    def test_returns_string(self):
        from engine.joseph_brain import determine_verdict
        v = determine_verdict(5.0, 60.0)
        self.assertIsInstance(v, str)
        self.assertIn(v, {"SMASH", "LEAN", "FADE", "STAY_AWAY", "OVERRIDE"})

    def test_avoid_returns_stay_away(self):
        from engine.joseph_brain import determine_verdict
        v = determine_verdict(10.0, 80.0, avoid=True)
        self.assertEqual(v, "STAY_AWAY")


class TestBuildRantStub(unittest.TestCase):
    def test_returns_string(self):
        from engine.joseph_brain import build_rant
        r = build_rant("SMASH", player="LeBron", stat="points")
        self.assertIsInstance(r, str)


class TestJosephAnalyzePickStub(unittest.TestCase):
    def test_returns_dict_with_required_keys(self):
        from engine.joseph_brain import joseph_analyze_pick
        result = joseph_analyze_pick({}, 24.5, "points", {})
        self.assertIsInstance(result, dict)
        for key in ("verdict", "edge", "confidence", "rant", "explanation",
                     "grade", "strategy"):
            self.assertIn(key, result)


class TestJosephRankPicksStub(unittest.TestCase):
    def test_returns_list(self):
        from engine.joseph_brain import joseph_rank_picks
        result = joseph_rank_picks([])
        self.assertIsInstance(result, list)


class TestJosephEvaluateParlayStub(unittest.TestCase):
    def test_returns_dict_with_required_keys(self):
        from engine.joseph_brain import joseph_evaluate_parlay
        result = joseph_evaluate_parlay([])
        self.assertIsInstance(result, dict)
        for key in ("expected_value", "correlation_matrix",
                     "adjusted_probability", "rant"):
            self.assertIn(key, result)


class TestJosephFullSlateStub(unittest.TestCase):
    def test_returns_dict_with_required_keys(self):
        from engine.joseph_brain import joseph_generate_full_slate_analysis
        result = joseph_generate_full_slate_analysis([], [], {})
        self.assertIsInstance(result, dict)
        for key in ("picks", "parlays", "top_plays", "summary_rant"):
            self.assertIn(key, result)


class TestJosephCommentaryStub(unittest.TestCase):
    def test_returns_string(self):
        from engine.joseph_brain import joseph_commentary_for_stat
        result = joseph_commentary_for_stat("LeBron", "points")
        self.assertIsInstance(result, str)


class TestJosephBlowoutWarningStub(unittest.TestCase):
    def test_returns_string(self):
        from engine.joseph_brain import joseph_blowout_warning
        result = joseph_blowout_warning(-12.5, 215.0)
        self.assertIsInstance(result, str)


class TestResetFragmentState(unittest.TestCase):
    def test_clears_state(self):
        from engine.joseph_brain import (
            _pick_fragment, OPENER_POOL, reset_fragment_state,
            _used_fragments
        )
        _pick_fragment(OPENER_POOL, "opener")
        self.assertIn("opener", _used_fragments)
        reset_fragment_state()
        self.assertEqual(len(_used_fragments), 0)


# ── Import fallbacks ────────────────────────────────────────


class TestImportFallbacks(unittest.TestCase):
    """Verify the module exposes all expected names even if deps are missing."""

    def test_all_pools_importable(self):
        from engine.joseph_brain import (
            OPENER_POOL, PIVOT_POOL, CLOSER_POOL,
            CATCHPHRASE_POOL, BODY_TEMPLATES,
            AMBIENT_CONTEXT_POOL, STAT_COMMENTARY_POOL,
            VERDICT_THRESHOLDS, JOSEPH_CONFIG,
        )
        self.assertIsInstance(OPENER_POOL, list)
        self.assertIsInstance(PIVOT_POOL, list)
        self.assertIsInstance(CLOSER_POOL, list)
        self.assertIsInstance(CATCHPHRASE_POOL, list)
        self.assertIsInstance(BODY_TEMPLATES, dict)
        self.assertIsInstance(AMBIENT_CONTEXT_POOL, dict)
        self.assertIsInstance(STAT_COMMENTARY_POOL, dict)
        self.assertIsInstance(VERDICT_THRESHOLDS, dict)
        self.assertIsInstance(JOSEPH_CONFIG, dict)

    def test_all_functions_importable(self):
        from engine.joseph_brain import (
            _pick_fragment, _pick_ambient, _pick_commentary,
            determine_verdict, build_rant,
            joseph_analyze_pick, joseph_rank_picks,
            joseph_evaluate_parlay, joseph_generate_full_slate_analysis,
            joseph_commentary_for_stat, joseph_blowout_warning,
            reset_fragment_state,
        )
        self.assertTrue(callable(_pick_fragment))
        self.assertTrue(callable(determine_verdict))
        self.assertTrue(callable(joseph_analyze_pick))
        self.assertTrue(callable(reset_fragment_state))

    def test_blowout_constants_importable(self):
        from engine.joseph_brain import (
            BLOWOUT_DIFFERENTIAL_MILD, BLOWOUT_DIFFERENTIAL_HEAVY
        )
        self.assertEqual(BLOWOUT_DIFFERENTIAL_MILD, 12)
        self.assertEqual(BLOWOUT_DIFFERENTIAL_HEAVY, 20)


if __name__ == "__main__":
    unittest.main()
