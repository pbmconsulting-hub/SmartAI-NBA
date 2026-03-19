# ============================================================
# FILE: tests/test_3_pillar_upgrade.py
# PURPOSE: Tests for the 3-Pillar Upgrade:
#          1) Engine Rebrand (JM5 → Quantum Matrix Engine 5.6)
#          2) Global Settings component (render_global_settings)
#          3) Pre-Analysis Prop Funnel (smart_filter_props wiring)
# ============================================================

import sys
import unittest
from unittest.mock import MagicMock


def _ensure_streamlit_mock():
    """Inject a lightweight streamlit mock if not installed."""
    if "streamlit" not in sys.modules:
        mock_st = MagicMock()
        mock_st.session_state = {}
        sys.modules["streamlit"] = mock_st


# ============================================================
# Pillar 1: Engine Rebrand
# ============================================================

class TestEngineRebrand(unittest.TestCase):
    """Verify all JM5 references have been replaced with Quantum Matrix Engine 5.6."""

    def test_no_jm5_in_theme(self):
        """styles/theme.py should contain no 'JM5' references."""
        import pathlib
        theme_path = pathlib.Path(__file__).parent.parent / "styles" / "theme.py"
        content = theme_path.read_text(encoding="utf-8")
        self.assertNotIn("JM5", content, "Found residual 'JM5' reference in styles/theme.py")

    def test_no_jm5_in_neural_analysis(self):
        """pages/3_⚡_Neural_Analysis.py should contain no 'JM5' references."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        content = na_path.read_text(encoding="utf-8")
        self.assertNotIn("JM5", content, "Found residual 'JM5' reference in Neural Analysis page")

    def test_quantum_matrix_in_theme(self):
        """styles/theme.py should mention 'Quantum Matrix Engine 5.6'."""
        import pathlib
        theme_path = pathlib.Path(__file__).parent.parent / "styles" / "theme.py"
        content = theme_path.read_text(encoding="utf-8")
        self.assertIn("Quantum Matrix Engine 5.6", content)

    def test_quantum_matrix_in_neural_analysis(self):
        """pages/3_⚡_Neural_Analysis.py should mention 'Quantum Matrix Engine 5.6'."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        content = na_path.read_text(encoding="utf-8")
        self.assertIn("Quantum Matrix Engine 5.6", content)


# ============================================================
# Pillar 2: Global Settings Component
# ============================================================

class TestGlobalSettingsComponent(unittest.TestCase):
    """Verify the render_global_settings utility exists and is importable."""

    def test_component_module_exists(self):
        """utils/components.py should be importable."""
        import pathlib
        comp_path = pathlib.Path(__file__).parent.parent / "utils" / "components.py"
        self.assertTrue(comp_path.exists(), "utils/components.py does not exist")

    def test_render_global_settings_defined(self):
        """render_global_settings should be a callable in utils/components."""
        import pathlib
        comp_path = pathlib.Path(__file__).parent.parent / "utils" / "components.py"
        source = comp_path.read_text(encoding="utf-8")
        self.assertIn("def render_global_settings()", source)

    def test_sync_callbacks_defined(self):
        """on_change callback functions should be defined in utils/components.py."""
        import pathlib
        comp_path = pathlib.Path(__file__).parent.parent / "utils" / "components.py"
        source = comp_path.read_text(encoding="utf-8")
        self.assertIn("def _sync_sim_depth()", source)
        self.assertIn("def _sync_edge_threshold()", source)

    def test_settings_injected_in_app(self):
        """app.py should import and call render_global_settings."""
        import pathlib
        app_path = pathlib.Path(__file__).parent.parent / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn("from utils.components import render_global_settings", source)
        self.assertIn("render_global_settings()", source)

    def test_settings_injected_in_neural_analysis(self):
        """Neural Analysis page should import and call render_global_settings."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn("from utils.components import render_global_settings", source)
        self.assertIn("render_global_settings()", source)

    def test_settings_injected_in_entry_builder(self):
        """Entry Builder page should import and call render_global_settings."""
        import pathlib
        eb_path = pathlib.Path(__file__).parent.parent / "pages" / "4_🧬_Entry_Builder.py"
        source = eb_path.read_text(encoding="utf-8")
        self.assertIn("from utils.components import render_global_settings", source)
        self.assertIn("render_global_settings()", source)


# ============================================================
# Pillar 3: Pre-Analysis Prop Funnel
# ============================================================

class TestPreAnalysisFunnel(unittest.TestCase):
    """Verify the pre-analysis filter funnel is wired in Neural Analysis."""

    def test_funnel_expander_exists(self):
        """Neural Analysis page should have a Market Filters expander."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn('Market Filters', source)

    def test_funnel_stat_multiselect(self):
        """Neural Analysis page should have a stat type multiselect widget."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn("Stat Types", source)
        self.assertIn("_STAT_TYPE_OPTIONS", source)

    def test_funnel_max_per_player(self):
        """Neural Analysis page should have a max-props-per-player control."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn("Max Props per Player", source)
        self.assertIn("funnel_max_per_player", source)

    def test_funnel_absolute_max(self):
        """Neural Analysis page should have an absolute-max-props control."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn("Absolute Max Props", source)
        self.assertIn("funnel_absolute_max", source)

    def test_funnel_dynamic_metric(self):
        """Neural Analysis page should show a dynamic metric for locked props."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn("PROPS LOCKED FOR QME 5.6 SIMULATION", source)

    def test_smart_filter_wired_in_runner(self):
        """The analysis runner should call smart_filter_props with funnel settings."""
        import pathlib
        na_path = pathlib.Path(__file__).parent.parent / "pages" / "3_⚡_Neural_Analysis.py"
        source = na_path.read_text(encoding="utf-8")
        self.assertIn("smart_filter_props", source)
        self.assertIn("_funnel_stat_keys_run", source)
        self.assertIn("_funnel_max_pp", source)


class TestSmartFilterPropsIntegration(unittest.TestCase):
    """Unit tests for smart_filter_props with funnel parameters."""

    def setUp(self):
        _ensure_streamlit_mock()
        from data.platform_fetcher import smart_filter_props
        self.filter_fn = smart_filter_props

    def test_stat_type_filtering(self):
        """Only props with matching stat types should survive."""
        props = [
            {"player_name": "Player A", "stat_type": "points", "team": "", "line": 20},
            {"player_name": "Player A", "stat_type": "blocks", "team": "", "line": 1.5},
            {"player_name": "Player B", "stat_type": "rebounds", "team": "", "line": 8},
        ]
        filtered, summary = self.filter_fn(
            all_props=props,
            stat_types={"points", "rebounds"},
            max_props_per_player=5,
        )
        stat_types = {p["stat_type"] for p in filtered}
        self.assertNotIn("blocks", stat_types)
        self.assertIn("points", stat_types)
        self.assertIn("rebounds", stat_types)

    def test_per_player_cap(self):
        """Props per player should be capped at max_props_per_player."""
        props = [
            {"player_name": "LeBron", "stat_type": "points", "team": "", "line": 25},
            {"player_name": "LeBron", "stat_type": "rebounds", "team": "", "line": 8},
            {"player_name": "LeBron", "stat_type": "assists", "team": "", "line": 7},
            {"player_name": "LeBron", "stat_type": "threes", "team": "", "line": 2},
        ]
        filtered, summary = self.filter_fn(
            all_props=props,
            max_props_per_player=2,
        )
        lebron_props = [p for p in filtered if p["player_name"] == "LeBron"]
        self.assertLessEqual(len(lebron_props), 2)

    def test_empty_props(self):
        """Empty prop list should return empty result."""
        filtered, summary = self.filter_fn(all_props=[])
        self.assertEqual(len(filtered), 0)
        self.assertEqual(summary["original_count"], 0)

    def test_summary_has_expected_keys(self):
        """Filter summary should contain all expected step counts."""
        props = [
            {"player_name": "Test", "stat_type": "points", "team": "", "line": 20},
        ]
        _, summary = self.filter_fn(all_props=props)
        for key in ("original_count", "after_team_filter", "after_injury_filter",
                     "after_dedup", "after_stat_filter", "after_per_player_cap",
                     "final_count", "reduction_pct"):
            self.assertIn(key, summary, f"Missing key '{key}' in filter summary")


if __name__ == "__main__":
    unittest.main()
