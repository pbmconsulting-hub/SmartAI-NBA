# ============================================================
# FILE: tests/test_pick_pipeline_audit.py
# PURPOSE: Tests for the Quantum Analysis Matrix pick pipeline
#          audit fixes:
#   Bug 1: "Doubtful" removed from pre-analysis _INACTIVE_STATUSES
#   Bug 2: smart_filter_props injury filter handles dict-valued maps
#   Bug 3: injury_status_penalty passed to confidence scoring
#   Bug 4: should_avoid hidden count transparency
# ============================================================
import unittest


class TestPreAnalysisInactiveStatuses(unittest.TestCase):
    """Bug 1: Verify 'Doubtful' is NOT in the pre-analysis inactive set."""

    def _get_inactive_statuses(self):
        """Extract the _INACTIVE_STATUSES frozenset from page source."""
        import ast
        import re

        page_path = "pages/3_⚡_Quantum_Analysis_Matrix.py"
        with open(page_path, "r") as f:
            source = f.read()

        # Find the _INACTIVE_STATUSES frozenset definition in the
        # pre-analysis injury filter section.
        pattern = re.compile(
            r"# ── Also skip confirmed Out/IR.*?_INACTIVE_STATUSES\s*=\s*frozenset\(\{(.*?)\}\)",
            re.DOTALL,
        )
        match = pattern.search(source)
        self.assertIsNotNone(match, "_INACTIVE_STATUSES definition not found")
        raw_set_content = match.group(1)

        # Parse individual quoted strings
        statuses = set(re.findall(r'"([^"]+)"', raw_set_content))
        return statuses

    def test_doubtful_not_in_inactive(self):
        """Doubtful players should NOT be dropped by the pre-analysis filter."""
        statuses = self._get_inactive_statuses()
        self.assertNotIn("Doubtful", statuses,
                         "Doubtful should not be in pre-analysis _INACTIVE_STATUSES")

    def test_out_still_filtered(self):
        """'Out' players should still be filtered by the pre-analysis filter."""
        statuses = self._get_inactive_statuses()
        self.assertIn("Out", statuses)

    def test_injured_reserve_still_filtered(self):
        """'Injured Reserve' should still be filtered."""
        statuses = self._get_inactive_statuses()
        self.assertIn("Injured Reserve", statuses)

    def test_in_analysis_gate_matches(self):
        """The in-analysis injury gate should NOT include Doubtful either."""
        page_path = "pages/3_⚡_Quantum_Analysis_Matrix.py"
        with open(page_path, "r") as f:
            source = f.read()

        # The in-analysis gate is a tuple check, not a frozenset
        self.assertIn('"Out", "Injured Reserve"', source)
        # Doubtful should NOT be in the in-analysis gate
        # (find the specific section)
        import re
        in_analysis = re.search(
            r'if player_status in \((.*?)\):',
            source, re.DOTALL,
        )
        self.assertIsNotNone(in_analysis, "In-analysis injury gate not found")
        self.assertNotIn("Doubtful", in_analysis.group(1),
                         "Doubtful should not be in the in-analysis injury gate")


class TestSmartFilterPropsInjuryMap(unittest.TestCase):
    """Bug 2: smart_filter_props should handle both dict and string injury maps."""

    def test_dict_valued_injury_map_filters_out(self):
        """Dict-valued injury map with status='Out' should filter the player."""
        from data.sportsbook_service import smart_filter_props

        props = [
            {"player_name": "Test Player", "stat_type": "points",
             "line": 20.5, "over_odds": -110, "under_odds": -110, "platform": "PrizePicks"},
        ]
        injury_map = {
            "test player": {"status": "Out", "injury_note": "Knee"},
        }
        result, summary = smart_filter_props(props, injury_map=injury_map)
        self.assertEqual(len(result), 0,
                         "Out player with dict injury map should be filtered")

    def test_dict_valued_injury_map_keeps_active(self):
        """Dict-valued injury map with status='Active' should keep the player."""
        from data.sportsbook_service import smart_filter_props

        props = [
            {"player_name": "Test Player", "stat_type": "points",
             "line": 20.5, "over_odds": -110, "under_odds": -110, "platform": "PrizePicks"},
        ]
        injury_map = {
            "test player": {"status": "Active", "injury_note": ""},
        }
        result, summary = smart_filter_props(props, injury_map=injury_map)
        self.assertEqual(len(result), 1,
                         "Active player with dict injury map should not be filtered")

    def test_dict_valued_injury_map_keeps_questionable(self):
        """Dict-valued injury map with status='Questionable' should keep the player."""
        from data.sportsbook_service import smart_filter_props

        props = [
            {"player_name": "Test Player", "stat_type": "points",
             "line": 20.5, "over_odds": -110, "under_odds": -110, "platform": "PrizePicks"},
        ]
        injury_map = {
            "test player": {"status": "Questionable", "injury_note": "Ankle"},
        }
        result, summary = smart_filter_props(props, injury_map=injury_map)
        self.assertEqual(len(result), 1,
                         "Questionable player should not be filtered")

    def test_dict_valued_injury_map_doubtful_passes_through(self):
        """Dict-valued injury map with status='Doubtful' should NOT be filtered.

        Doubtful players pass through smart_filter_props and receive an
        injury_status_penalty in confidence scoring instead of being dropped.
        """
        from data.sportsbook_service import smart_filter_props

        props = [
            {"player_name": "Test Player", "stat_type": "points",
             "line": 20.5, "over_odds": -110, "under_odds": -110, "platform": "PrizePicks"},
        ]
        injury_map = {
            "test player": {"status": "Doubtful", "injury_note": "Knee"},
        }
        result, summary = smart_filter_props(props, injury_map=injury_map)
        self.assertEqual(len(result), 1,
                         "Doubtful player should NOT be filtered by smart_filter_props")

    def test_string_valued_injury_map_still_works(self):
        """String-valued injury map should still work correctly."""
        from data.sportsbook_service import smart_filter_props

        props = [
            {"player_name": "Test Player", "stat_type": "points",
             "line": 20.5, "over_odds": -110, "under_odds": -110, "platform": "PrizePicks"},
        ]
        injury_map = {
            "test player": "out",
        }
        result, summary = smart_filter_props(props, injury_map=injury_map)
        self.assertEqual(len(result), 0,
                         "Out player with string injury map should be filtered")

    def test_missing_player_in_injury_map_kept(self):
        """Players not in injury map should be kept (assumed active)."""
        from data.sportsbook_service import smart_filter_props

        props = [
            {"player_name": "Unknown Player", "stat_type": "points",
             "line": 20.5, "over_odds": -110, "under_odds": -110, "platform": "PrizePicks"},
        ]
        injury_map = {
            "other player": {"status": "Out", "injury_note": "Knee"},
        }
        result, summary = smart_filter_props(props, injury_map=injury_map)
        self.assertEqual(len(result), 1,
                         "Player not in injury map should be kept")


class TestInjuryStatusPenalty(unittest.TestCase):
    """Bug 3: Verify injury_status_penalty is passed for Doubtful/Questionable."""

    def test_page_source_passes_injury_penalty(self):
        """The Quantum Analysis page should pass injury_status_penalty."""
        page_path = "pages/3_⚡_Quantum_Analysis_Matrix.py"
        with open(page_path, "r") as f:
            source = f.read()

        self.assertIn("injury_status_penalty=_injury_penalty", source,
                      "calculate_confidence_score should receive injury_status_penalty")

    def test_doubtful_penalty_value(self):
        """Doubtful players should receive an 8-point penalty."""
        page_path = "pages/3_⚡_Quantum_Analysis_Matrix.py"
        with open(page_path, "r") as f:
            source = f.read()

        self.assertIn("_DOUBTFUL_INJURY_PENALTY", source,
                      "Should have a named constant for Doubtful injury penalty")
        self.assertIn("_DOUBTFUL_INJURY_PENALTY = 8.0", source,
                      "Doubtful injury penalty constant should be 8.0")
        self.assertIn("_injury_penalty = _DOUBTFUL_INJURY_PENALTY", source,
                      "Doubtful case should use the named constant")

    def test_questionable_penalty_value(self):
        """Questionable/GTD players should receive a 4-point penalty."""
        page_path = "pages/3_⚡_Quantum_Analysis_Matrix.py"
        with open(page_path, "r") as f:
            source = f.read()

        self.assertIn("_QUESTIONABLE_INJURY_PENALTY", source,
                      "Should have a named constant for Questionable injury penalty")
        self.assertIn("_QUESTIONABLE_INJURY_PENALTY = 4.0", source,
                      "Questionable injury penalty constant should be 4.0")
        self.assertIn("_injury_penalty = _QUESTIONABLE_INJURY_PENALTY", source,
                      "Questionable case should use the named constant")

    def test_confidence_engine_accepts_injury_penalty(self):
        """The confidence engine should accept injury_status_penalty parameter."""
        from engine.confidence import calculate_confidence_score
        import inspect
        sig = inspect.signature(calculate_confidence_score)
        self.assertIn("injury_status_penalty", sig.parameters,
                      "calculate_confidence_score must have injury_status_penalty param")


class TestShouldAvoidTransparency(unittest.TestCase):
    """Bug 4: Verify hidden should_avoid picks are counted and shown."""

    def test_page_source_has_avoid_count_message(self):
        """The page should display how many picks were hidden by should_avoid."""
        page_path = "pages/3_⚡_Quantum_Analysis_Matrix.py"
        with open(page_path, "r") as f:
            source = f.read()

        self.assertIn("_avoid_count", source,
                      "Should count avoid picks before filtering them")
        self.assertIn("pick(s) hidden", source,
                      "Should show a message about hidden picks")
        self.assertIn("Hide Avoids", source,
                      "Should reference the Hide Avoids toggle")


if __name__ == "__main__":
    unittest.main()
