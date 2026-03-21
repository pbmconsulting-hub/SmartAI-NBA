# ============================================================
# FILE: tests/test_the_studio.py
# PURPOSE: Tests for pages/14_🎙️_The_Studio.py
#          (Joseph's dedicated interactive page — Layer 7)
# ============================================================
import sys, os, unittest, ast
from unittest.mock import MagicMock

# Ensure repo root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestStudioFileSyntax(unittest.TestCase):
    """Verify the Studio page file parses without syntax errors."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "14_🎙️_The_Studio.py",
        )

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self.filepath), "Studio page file should exist")

    def test_valid_python_syntax(self):
        with open(self.filepath, "r") as fh:
            source = fh.read()
        # Should not raise SyntaxError
        tree = ast.parse(source)
        self.assertIsInstance(tree, ast.Module)

    def test_file_not_empty(self):
        with open(self.filepath, "r") as fh:
            source = fh.read()
        self.assertGreater(len(source), 1000, "Studio page should be substantial")


class TestStudioFileStructure(unittest.TestCase):
    """Verify key structural elements exist in the Studio page source."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "14_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_page_config_present(self):
        self.assertIn("set_page_config", self.source)

    def test_page_title(self):
        self.assertIn("The Studio", self.source)

    def test_page_icon(self):
        self.assertIn("🎙️", self.source)

    def test_layout_wide(self):
        self.assertIn('layout="wide"', self.source)

    def test_global_css_import(self):
        self.assertIn("get_global_css", self.source)

    def test_qds_css_import(self):
        self.assertIn("get_qds_css", self.source)

    def test_premium_gate(self):
        self.assertIn("premium_gate", self.source)

    def test_render_global_settings(self):
        self.assertIn("render_global_settings", self.source)

    def test_hero_banner(self):
        self.assertIn("studio-hero", self.source)
        self.assertIn("God-Mode Analyst", self.source)

    def test_three_modes(self):
        self.assertIn("GAMES TONIGHT", self.source)
        self.assertIn("SCOUT A PLAYER", self.source)
        self.assertIn("BUILD MY BETS", self.source)

    def test_games_mode_imports(self):
        self.assertIn("joseph_analyze_game", self.source)

    def test_player_mode_imports(self):
        self.assertIn("joseph_analyze_player", self.source)

    def test_bets_mode_imports(self):
        self.assertIn("joseph_generate_best_bets", self.source)

    def test_leg_buttons(self):
        self.assertIn("POWER PLAY", self.source)
        self.assertIn("TRIPLE THREAT", self.source)
        self.assertIn("THE QUAD", self.source)
        self.assertIn("HIGH FIVE", self.source)
        self.assertIn("THE FULL SEND", self.source)

    def test_platform_selector(self):
        self.assertIn("PrizePicks", self.source)
        self.assertIn("Underdog", self.source)
        self.assertIn("DraftKings", self.source)

    def test_dawg_board_section(self):
        self.assertIn("DAWG BOARD", self.source)
        self.assertIn("render_dawg_board", self.source)

    def test_override_report_section(self):
        self.assertIn("OVERRIDE REPORT", self.source)
        self.assertIn("render_override_report", self.source)

    def test_track_record_section(self):
        self.assertIn("TRACK RECORD", self.source)
        self.assertIn("joseph_get_track_record", self.source)

    def test_accuracy_by_verdict(self):
        self.assertIn("joseph_get_accuracy_by_verdict", self.source)

    def test_bet_history_section(self):
        self.assertIn("BET HISTORY", self.source)

    def test_signoff_section(self):
        self.assertIn("SIGN-OFF", self.source.upper())

    def test_payout_table(self):
        self.assertIn("PLATFORM_FLEX_TABLES", self.source)

    def test_regenerate_button(self):
        self.assertIn("Regenerate", self.source)

    def test_alternatives_expander(self):
        self.assertIn("get_alternative_tickets", self.source)

    def test_team_colors(self):
        self.assertIn("get_team_colors", self.source)

    def test_bet_card_html(self):
        self.assertIn("get_bet_card_html", self.source)

    def test_override_accuracy(self):
        self.assertIn("joseph_get_override_accuracy", self.source)

    def test_joseph_commentary(self):
        self.assertIn("joseph_commentary", self.source)

    def test_nerd_stats_expanders(self):
        self.assertIn("Nerd Stats", self.source)


class TestStudioCSS(unittest.TestCase):
    """Verify the Studio page contains all required CSS classes."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "14_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_studio_hero_css(self):
        self.assertIn("studio-hero", self.source)

    def test_studio_avatar_css(self):
        self.assertIn("studio-avatar-lg", self.source)
        self.assertIn("120px", self.source)

    def test_studio_game_card_css(self):
        self.assertIn("studio-game-card", self.source)

    def test_studio_ticket_card_css(self):
        self.assertIn("studio-ticket-card", self.source)

    def test_studio_metric_card_css(self):
        self.assertIn("studio-metric-card", self.source)

    def test_studio_payout_table_css(self):
        self.assertIn("studio-payout-table", self.source)

    def test_glassmorphic_styling(self):
        self.assertIn("backdrop-filter", self.source)

    def test_orange_accent(self):
        self.assertIn("#ff5e00", self.source)

    def test_orbitron_font(self):
        self.assertIn("Orbitron", self.source)


class TestStudioImports(unittest.TestCase):
    """Verify the Studio page imports all required modules."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "14_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_imports_joseph_brain(self):
        self.assertIn("from engine.joseph_brain import", self.source)

    def test_imports_joseph_tickets(self):
        self.assertIn("from engine.joseph_tickets import", self.source)

    def test_imports_joseph_bets(self):
        self.assertIn("from engine.joseph_bets import", self.source)

    def test_imports_joseph_live_desk(self):
        self.assertIn("from pages.helpers.joseph_live_desk import", self.source)

    def test_imports_theme(self):
        self.assertIn("from styles.theme import", self.source)

    def test_imports_premium_gate(self):
        self.assertIn("from utils.premium_gate import", self.source)

    def test_imports_components(self):
        self.assertIn("from utils.components import", self.source)

    def test_imports_data_manager(self):
        self.assertIn("from data.data_manager import", self.source)

    def test_imports_entry_optimizer(self):
        self.assertIn("from engine.entry_optimizer import", self.source)

    def test_safe_import_pattern(self):
        """All major imports should use try/except for resilience."""
        # Count try blocks (should be >= 8 for all the import sections)
        try_count = self.source.count("except ImportError")
        self.assertGreaterEqual(try_count, 8, "Should have many safe import blocks")


class TestLiveDeskFileExists(unittest.TestCase):
    """Verify the live desk helper file exists."""

    def test_helper_file_exists(self):
        filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "helpers", "joseph_live_desk.py",
        )
        self.assertTrue(os.path.isfile(filepath))

    def test_helper_valid_syntax(self):
        filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "helpers", "joseph_live_desk.py",
        )
        with open(filepath, "r") as fh:
            source = fh.read()
        tree = ast.parse(source)
        self.assertIsInstance(tree, ast.Module)


if __name__ == "__main__":
    unittest.main()
