# ============================================================
# FILE: tests/test_the_studio.py
# PURPOSE: Tests for pages/7_🎙️_The_Studio.py
#          (Joseph's dedicated interactive page — Layer 7)
# ============================================================
import sys, os, unittest, ast
from unittest.mock import MagicMock

# Ensure repo root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _load_studio_combined_source() -> str:
    """Read The Studio page AND the extracted studio_theme CSS module.

    CSS was extracted from inline _STUDIO_CSS into styles/studio_theme.py
    for maintainability.  Tests that verify CSS content should search the
    combined source.
    """
    base = os.path.join(os.path.dirname(__file__), "..")
    page_path = os.path.join(base, "pages", "7_🎙️_The_Studio.py")
    theme_path = os.path.join(base, "styles", "studio_theme.py")
    with open(page_path, "r") as fh:
        source = fh.read()
    if os.path.isfile(theme_path):
        with open(theme_path, "r") as fh:
            source += "\n" + fh.read()
    return source


class TestStudioFileSyntax(unittest.TestCase):
    """Verify the Studio page file parses without syntax errors."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
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
            "pages", "7_🎙️_The_Studio.py",
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
        self.assertIn("Underdog Fantasy", self.source)
        self.assertIn("DraftKings Pick6", self.source)

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
    """Verify the Studio page contains all required CSS classes.

    CSS may live in the page source or in the extracted studio_theme module.
    """

    def setUp(self):
        self.source = _load_studio_combined_source()

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

    # ── Elite NBA ESPN AI theme enhancements ─────────────────

    def test_hero_bottom_broadcast_bar(self):
        """Hero should have a bottom shimmer bar like ESPN broadcast."""
        self.assertIn("studio-hero::after", self.source)

    def test_hero_outer_glow(self):
        """Hero should have an outer glow box-shadow."""
        self.assertIn("box-shadow", self.source)

    def test_hero_title_text_shadow(self):
        """Hero title should have a neon text-shadow."""
        self.assertIn("text-shadow", self.source)

    def test_avatar_animated_pulse(self):
        """120px avatar should have an animated pulse glow ring."""
        self.assertIn("studioAvatarPulse", self.source)

    def test_game_card_left_accent(self):
        """Game cards should have ESPN-style left accent border."""
        self.assertIn("border-left", self.source)

    def test_game_card_hover_lift(self):
        """Game cards should lift on hover."""
        self.assertIn("translateY", self.source)

    def test_ticket_card_top_accent(self):
        """Ticket cards should have a top accent gradient line."""
        self.assertIn("studio-ticket-card::before", self.source)

    def test_metric_value_tabular_nums(self):
        """Metric values should use tabular-nums for scoreboard alignment."""
        self.assertIn("tabular-nums", self.source)

    def test_metric_label_uppercase(self):
        """Metric labels should be uppercase."""
        self.assertIn("text-transform:uppercase", self.source)

    def test_metric_card_hover(self):
        """Metric cards should have hover effects."""
        self.assertIn("studio-metric-card:hover", self.source)

    def test_section_title_left_border(self):
        """Section titles should have ESPN-style left accent border."""
        self.assertIn("border-left:3px solid #ff5e00", self.source)

    def test_montserrat_font(self):
        self.assertIn("Montserrat", self.source)

    def test_jetbrains_mono_font(self):
        self.assertIn("JetBrains Mono", self.source)

    def test_payout_table_tabular_nums(self):
        """Payout table should use tabular-nums for scoreboard numbers."""
        self.assertIn("tabular-nums", self.source)


class TestStudioImports(unittest.TestCase):
    """Verify the Studio page imports all required modules."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
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


class TestStudioPlatformPreference(unittest.TestCase):
    """Tests for Joseph's platform preference selector in The Studio."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_platform_preference_state_key(self):
        """Platform preference should use session state."""
        self.assertIn("joseph_preferred_platform", self.source)

    def test_platform_question_prompt(self):
        """Joseph should ask what betting app the user uses."""
        self.assertIn("What betting app are you using tonight", self.source)

    def test_platform_options_all_three(self):
        """Primary sportsbook platforms should be available."""
        self.assertIn("PrizePicks", self.source)
        self.assertIn("Underdog Fantasy", self.source)
        self.assertIn("DraftKings Pick6", self.source)

    def test_platform_radio_key(self):
        """Platform radio should have a unique key."""
        self.assertIn("joseph_platform_radio", self.source)

    def test_build_bets_uses_platform_preference(self):
        """Build My Bets should use the Joseph platform preference."""
        self.assertIn("joseph_platform", self.source)

    def test_build_bets_no_hard_block(self):
        """Build My Bets should not hard-block without analysis_results."""
        # The old line that hard-blocked: 'if not analysis_results: st.info("Run Neural")'
        # Should now have a fallback to platform_props
        self.assertIn("platform_props", self.source)


class TestFindTeamDataDictSupport(unittest.TestCase):
    """Tests for _find_team_data accepting dict-keyed teams data."""

    def setUp(self):
        from engine.joseph_strategy import _find_team_data
        self.find = _find_team_data
        self.teams_dict = {
            "LAL": {"abbreviation": "LAL", "pace": 100.5, "off_rating": 114.0},
            "BOS": {"abbreviation": "BOS", "pace": 98.5, "off_rating": 116.0},
        }
        self.teams_list = list(self.teams_dict.values())

    def test_dict_exact_key(self):
        result = self.find("LAL", self.teams_dict)
        self.assertEqual(result["pace"], 100.5)

    def test_dict_case_insensitive(self):
        result = self.find("lal", self.teams_dict)
        self.assertEqual(result["pace"], 100.5)

    def test_dict_not_found(self):
        result = self.find("XXX", self.teams_dict)
        self.assertEqual(result, {})

    def test_list_still_works(self):
        result = self.find("BOS", self.teams_list)
        self.assertEqual(result["pace"], 98.5)

    def test_empty_data(self):
        self.assertEqual(self.find("LAL", {}), {})
        self.assertEqual(self.find("LAL", []), {})
        self.assertEqual(self.find("LAL", None), {})


class TestJosephAnalyzePick(unittest.TestCase):
    """Tests for the implemented joseph_analyze_pick function."""

    def setUp(self):
        from engine.joseph_brain import joseph_analyze_pick
        self.analyze = joseph_analyze_pick
        self.player = {
            "name": "Test Player",
            "points_avg": 20.0,
            "rebounds_avg": 8.0,
            "assists_avg": 5.0,
            "games_played": 50,
        }

    def test_returns_dict(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIsInstance(result, dict)

    def test_has_verdict(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIn(result["verdict"], ("SMASH", "LEAN", "FADE", "STAY_AWAY"))

    def test_has_edge(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIsInstance(result["edge"], float)

    def test_has_confidence(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIsInstance(result["confidence"], float)

    def test_has_rant(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIsInstance(result["rant"], str)
        # Rant should not be empty — it was a stub before
        self.assertGreater(len(result["rant"]), 0)

    def test_has_platform(self):
        result = self.analyze(self.player, 18.5, "points", {}, platform="Underdog")
        self.assertEqual(result["platform"], "Underdog")

    def test_has_player_name(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertEqual(result["player_name"], "Test Player")

    def test_has_verdict_emoji(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIn("verdict_emoji", result)

    def test_has_projected_avg(self):
        result = self.analyze(self.player, 18.5, "points", {})
        self.assertIsInstance(result["projected_avg"], float)
        self.assertGreater(result["projected_avg"], 0)

    def test_graceful_empty_player(self):
        result = self.analyze({}, 10.0, "points", {})
        self.assertIn(result["verdict"], ("SMASH", "LEAN", "FADE", "STAY_AWAY"))

    def test_different_stat_types(self):
        for stat in ("points", "rebounds", "assists", "steals", "threes"):
            result = self.analyze(self.player, 5.0, stat, {})
            self.assertIn("verdict", result)


class TestBuildRant(unittest.TestCase):
    """Tests for the build_rant function (was an empty stub)."""

    def setUp(self):
        from engine.joseph_brain import build_rant
        self.build_rant = build_rant

    def test_returns_string(self):
        result = self.build_rant("SMASH", player="Test", stat="points", line="24.5")
        self.assertIsInstance(result, str)

    def test_not_empty(self):
        result = self.build_rant("SMASH", player="Test", stat="points", line="24.5")
        self.assertGreater(len(result), 0)

    def test_all_verdicts_produce_rant(self):
        for v in ("SMASH", "LEAN", "FADE", "STAY_AWAY"):
            result = self.build_rant(v, player="Player", stat="assists")
            self.assertGreater(len(result), 0, f"build_rant({v}) should produce text")


class TestGameAnalysisWithDictTeamsData(unittest.TestCase):
    """Test joseph_analyze_game works with dict-format teams_data."""

    def setUp(self):
        from engine.joseph_brain import joseph_analyze_game
        self.analyze_game = joseph_analyze_game

    def test_game_analysis_with_dict(self):
        teams_data = {
            "LAL": {"abbreviation": "LAL", "team": "LAL",
                     "pace": 100.5, "off_rating": 114.0, "def_rating": 112.0},
            "BOS": {"abbreviation": "BOS", "team": "BOS",
                     "pace": 98.5, "off_rating": 116.0, "def_rating": 107.0},
        }
        game = {"home_team": "LAL", "away_team": "BOS",
                "spread": -3.5, "total": 220.0}
        result = self.analyze_game(game, teams_data, [])
        self.assertTrue(result.get("game_narrative"), "Should produce narrative")
        self.assertTrue(result.get("joseph_game_total_take"), "Should produce total take")

    def test_game_analysis_uses_strategy_narrative(self):
        teams_data = {
            "LAL": {"abbreviation": "LAL", "team": "LAL",
                     "pace": 100.5, "off_rating": 114.0, "def_rating": 112.0},
            "BOS": {"abbreviation": "BOS", "team": "BOS",
                     "pace": 98.5, "off_rating": 116.0, "def_rating": 107.0},
        }
        game = {"home_team": "LAL", "away_team": "BOS",
                "spread": -3.5, "total": 220.0}
        result = self.analyze_game(game, teams_data, [])
        # Strategy narrative includes "visits" when teams are real
        narrative = result.get("game_narrative", "")
        self.assertIn("BOS", narrative)
        self.assertIn("LAL", narrative)

    def test_total_opinion_uses_model_projection(self):
        teams_data = {
            "LAL": {"abbreviation": "LAL", "team": "LAL",
                     "pace": 100.5, "off_rating": 114.0, "def_rating": 112.0},
            "BOS": {"abbreviation": "BOS", "team": "BOS",
                     "pace": 98.5, "off_rating": 116.0, "def_rating": 107.0},
        }
        game = {"home_team": "LAL", "away_team": "BOS",
                "spread": -3.5, "total": 220.0}
        result = self.analyze_game(game, teams_data, [])
        total_take = result.get("joseph_game_total_take", "")
        # Should mention model projection when it differs from line
        self.assertIn("model projects", total_take)

    def test_scheme_not_raw_dict(self):
        teams_data = {
            "LAL": {"abbreviation": "LAL", "team": "LAL",
                     "pace": 100.5, "off_rating": 114.0, "def_rating": 112.0},
            "BOS": {"abbreviation": "BOS", "team": "BOS",
                     "pace": 98.5, "off_rating": 116.0, "def_rating": 107.0},
        }
        game = {"home_team": "LAL", "away_team": "BOS",
                "spread": -3.5, "total": 220.0}
        result = self.analyze_game(game, teams_data, [])
        scheme = result.get("scheme_analysis", "")
        # Should not contain raw dict representation
        self.assertNotIn("primary_scheme", scheme)
        self.assertNotIn("rim_protection", scheme)
        # Should contain the extracted scheme name and both team names
        self.assertIn("LAL", scheme)
        self.assertIn("defense", scheme.lower())

    def test_game_analysis_empty_results_still_works(self):
        teams_data = {
            "LAL": {"abbreviation": "LAL", "team": "LAL",
                     "pace": 100.5, "off_rating": 114.0, "def_rating": 112.0},
        }
        game = {"home_team": "LAL", "away_team": "UNK",
                "spread": 0, "total": 220.0}
        result = self.analyze_game(game, teams_data, [])
        self.assertIsInstance(result, dict)


class TestStudioEnhancement1Avatar(unittest.TestCase):
    """Enhancement 1: Avatar image in hero banner."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_hero_uses_avatar_b64(self):
        """Hero banner should use get_joseph_avatar_b64()."""
        self.assertIn("_hero_avatar_b64", self.source)

    def test_hero_avatar_img_tag(self):
        """Hero should render actual <img> tag with avatar."""
        self.assertIn("studio-avatar-lg", self.source)
        self.assertIn('data:image/png;base64', self.source)

    def test_hero_avatar_fallback(self):
        """Hero should have emoji fallback when avatar is not available."""
        self.assertIn("🎙️", self.source)


class TestStudioEnhancement2OnAir(unittest.TestCase):
    """Enhancement 2: Animated ON AIR indicator."""

    def setUp(self):
        self.source = _load_studio_combined_source()

    def test_on_air_badge_class(self):
        self.assertIn("studio-on-air", self.source)

    def test_on_air_dot_class(self):
        self.assertIn("studio-on-air-dot", self.source)

    def test_on_air_pulse_animation(self):
        self.assertIn("studioOnAirPulse", self.source)

    def test_on_air_dot_pulse_animation(self):
        self.assertIn("studioOnAirDotPulse", self.source)

    def test_on_air_text_in_hero(self):
        self.assertIn("ON AIR", self.source)


class TestStudioEnhancement3ModeCards(unittest.TestCase):
    """Enhancement 3: Styled tab cards for mode selection."""

    def setUp(self):
        self.source = _load_studio_combined_source()

    def test_mode_cards_css(self):
        self.assertIn("studio-mode-cards", self.source)

    def test_mode_card_class(self):
        self.assertIn("studio-mode-card", self.source)

    def test_mode_card_active_class(self):
        self.assertIn("studio-mode-card.active", self.source)

    def test_mode_card_meta(self):
        """Each mode should have icon, title, and tagline."""
        self.assertIn("studio-mode-icon", self.source)
        self.assertIn("studio-mode-title", self.source)
        self.assertIn("studio-mode-tag", self.source)

    def test_mode_taglines_present(self):
        self.assertIn("Full game breakdowns", self.source)
        self.assertIn("Deep dive into any player", self.source)
        self.assertIn("Build optimal parlay tickets", self.source)


class TestStudioEnhancement4GameCards(unittest.TestCase):
    """Enhancement 4 + 19: Game cards with team colors."""

    def setUp(self):
        self.source = _load_studio_combined_source()

    def test_game_card_class_used(self):
        """The .studio-game-card class should be used for game rendering."""
        # Should appear in both CSS definition and usage
        count = self.source.count("studio-game-card")
        self.assertGreaterEqual(count, 3, "studio-game-card should be in CSS + used in rendering")

    def test_team_badge_class(self):
        self.assertIn("team-badge", self.source)

    def test_both_team_colors(self):
        """Both home and away team colors should be fetched."""
        self.assertIn("a_pri, a_sec", self.source)
        self.assertIn("h_pri, h_sec", self.source)


class TestStudioEnhancement5ConfidenceGauge(unittest.TestCase):
    """Enhancement 5: Ticket card confidence gauge."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_confidence_gauge_called(self):
        self.assertIn("render_confidence_gauge_svg", self.source)

    def test_gauge_in_ticket_card(self):
        self.assertIn("_gauge_html", self.source)


class TestStudioEnhancement6TrackRecordCharts(unittest.TestCase):
    """Enhancement 6: Mini charts in Track Record."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_pie_svg(self):
        """SMASH vs LEAN pie chart SVG should exist."""
        self.assertIn("_pie_svg", self.source)

    def test_win_rate_progress_bar(self):
        """Win rate should have a progress bar."""
        self.assertIn("_wr_pct", self.source)


class TestStudioEnhancement7OutcomeBadges(unittest.TestCase):
    """Enhancement 7: Bet history outcome badges."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_outcome_badge_called(self):
        self.assertIn("render_outcome_badge", self.source)

    def test_outcome_badge_in_bet_history(self):
        self.assertIn("_badge_html", self.source)


class TestStudioEnhancement8CSSVars(unittest.TestCase):
    """Enhancement 8: CSS custom properties."""

    def setUp(self):
        self.source = _load_studio_combined_source()

    def test_css_custom_properties_defined(self):
        self.assertIn("--studio-muted", self.source)
        self.assertIn("--studio-accent", self.source)
        self.assertIn("--studio-text", self.source)
        self.assertIn("--studio-bg-deep", self.source)
        self.assertIn("--studio-bg-card", self.source)
        self.assertIn("--studio-green", self.source)
        self.assertIn("--studio-cyan", self.source)
        self.assertIn("--studio-red", self.source)
        self.assertIn("--studio-yellow", self.source)

    def test_css_vars_used_in_rendering(self):
        """CSS vars should be used in inline styles."""
        self.assertIn("var(--studio-muted)", self.source)
        self.assertIn("var(--studio-accent)", self.source)


class TestStudioEnhancement9PersistMode(unittest.TestCase):
    """Enhancement 9: Persist selected mode in session state."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_mode_stored_in_session_state(self):
        self.assertIn('"studio_mode"', self.source)

    def test_mode_radio_has_key(self):
        self.assertIn("studio_mode_radio", self.source)

    def test_mode_session_state_write(self):
        self.assertIn('st.session_state["studio_mode"]', self.source)


class TestStudioEnhancement10PlayerGrouping(unittest.TestCase):
    """Enhancement 10: Players grouped by team."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_sort_by_team_then_name(self):
        self.assertIn("group by team", self.source)


class TestStudioEnhancement11TicketComparison(unittest.TestCase):
    """Enhancement 11: Side-by-side ticket comparison."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_tickets_stored_in_session(self):
        self.assertIn('"studio_tickets"', self.source)

    def test_compare_expander(self):
        self.assertIn("Compare Previous Tickets", self.source)


class TestStudioEnhancement12ClipboardExport(unittest.TestCase):
    """Enhancement 12: Copy ticket to clipboard."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_clipboard_lines_built(self):
        self.assertIn("_clipboard_lines", self.source)

    def test_copy_caption(self):
        self.assertIn("Copy the ticket above", self.source)


class TestStudioEnhancement14DateRangeFilter(unittest.TestCase):
    """Enhancement 14: Track record date range filter."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_date_range_options(self):
        self.assertIn("All Time", self.source)
        self.assertIn("Last 7 Days", self.source)
        self.assertIn("Last 30 Days", self.source)
        self.assertIn("This Season", self.source)

    def test_date_range_key(self):
        self.assertIn("studio_track_record_range", self.source)


class TestStudioEnhancement15EmptyStates(unittest.TestCase):
    """Enhancement 15: Styled empty-state cards."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_render_empty_state_used(self):
        count = self.source.count("render_empty_state")
        self.assertGreaterEqual(count, 5, "render_empty_state should replace most plain st.info calls")


class TestStudioEnhancement16QuickNav(unittest.TestCase):
    """Enhancement 16: Quick navigation links."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_quick_nav_class(self):
        self.assertIn("studio-quick-nav", self.source)

    def test_jump_links(self):
        self.assertIn("Tonight's Bets", self.source)
        self.assertIn("Dawg Board", self.source)
        self.assertIn("Track Record", self.source)
        self.assertIn("Bet History", self.source)


class TestStudioEnhancement17VerdictHeatmap(unittest.TestCase):
    """Enhancement 17: Verdict heatmap on Build My Bets."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_heatmap_called(self):
        self.assertIn("render_verdict_heatmap_html", self.source)


class TestStudioEnhancement18HelperExtraction(unittest.TestCase):
    """Enhancement 18: Inline HTML templates extracted to helpers."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_render_avatar_commentary_used(self):
        count = self.source.count("render_avatar_commentary")
        self.assertGreaterEqual(count, 3, "Should use render_avatar_commentary multiple times")

    def test_render_nerd_stats_used(self):
        count = self.source.count("render_nerd_stats")
        self.assertGreaterEqual(count, 3, "Should use render_nerd_stats for all 3 expanders")


class TestStudioEnhancement20NerdStatsConsolidation(unittest.TestCase):
    """Enhancement 20: Consolidated nerd stats helper."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_render_nerd_stats_imported(self):
        self.assertIn("render_nerd_stats", self.source)

    def test_custom_keys_per_mode(self):
        """Each mode should pass specific keys."""
        self.assertIn("_game_nerd_keys", self.source)
        self.assertIn("_scout_nerd_keys", self.source)
        self.assertIn("_ticket_nerd_keys", self.source)


class TestHelperFunctionsExist(unittest.TestCase):
    """Verify new helper functions exist in joseph_live_desk.py."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "helpers", "joseph_live_desk.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_render_nerd_stats_defined(self):
        self.assertIn("def render_nerd_stats(", self.source)

    def test_render_avatar_commentary_defined(self):
        self.assertIn("def render_avatar_commentary(", self.source)

    def test_render_confidence_gauge_svg_defined(self):
        self.assertIn("def render_confidence_gauge_svg(", self.source)

    def test_render_outcome_badge_defined(self):
        self.assertIn("def render_outcome_badge(", self.source)

    def test_render_empty_state_defined(self):
        self.assertIn("def render_empty_state(", self.source)

    def test_render_verdict_heatmap_html_defined(self):
        self.assertIn("def render_verdict_heatmap_html(", self.source)


class TestHelperFunctionsWork(unittest.TestCase):
    """Unit tests for the new helper functions."""

    def test_render_nerd_stats_default(self):
        from pages.helpers.joseph_live_desk import render_nerd_stats
        result = render_nerd_stats({"edge": 5.0, "confidence": 80})
        self.assertIn("edge", result)
        self.assertIn("5.0", result)

    def test_render_nerd_stats_custom_keys(self):
        from pages.helpers.joseph_live_desk import render_nerd_stats
        result = render_nerd_stats(
            {"gravity": 3.5, "trend": "up", "other": "ignored"},
            keys=["gravity", "trend"],
        )
        self.assertIn("gravity", result)
        self.assertIn("trend", result)
        self.assertNotIn("other", result)

    def test_render_nerd_stats_empty(self):
        from pages.helpers.joseph_live_desk import render_nerd_stats
        result = render_nerd_stats({})
        self.assertEqual(result, "")

    def test_render_avatar_commentary(self):
        from pages.helpers.joseph_live_desk import render_avatar_commentary
        result = render_avatar_commentary("Test commentary")
        self.assertIn("Test commentary", result)
        self.assertIn("display:flex", result)

    def test_render_avatar_commentary_escapes_html(self):
        from pages.helpers.joseph_live_desk import render_avatar_commentary
        result = render_avatar_commentary("<script>alert(1)</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_render_confidence_gauge_svg_basic(self):
        from pages.helpers.joseph_live_desk import render_confidence_gauge_svg
        result = render_confidence_gauge_svg(75.0, 50.0, 60.0)
        self.assertIn("<svg", result)
        self.assertIn("75%", result)

    def test_render_confidence_gauge_svg_green(self):
        from pages.helpers.joseph_live_desk import render_confidence_gauge_svg
        result = render_confidence_gauge_svg(80.0)
        self.assertIn("#22c55e", result)  # green

    def test_render_confidence_gauge_svg_orange(self):
        from pages.helpers.joseph_live_desk import render_confidence_gauge_svg
        result = render_confidence_gauge_svg(50.0)
        self.assertIn("#f59e0b", result)  # orange

    def test_render_confidence_gauge_svg_red(self):
        from pages.helpers.joseph_live_desk import render_confidence_gauge_svg
        result = render_confidence_gauge_svg(20.0)
        self.assertIn("#ef4444", result)  # red

    def test_render_confidence_gauge_svg_clamp(self):
        from pages.helpers.joseph_live_desk import render_confidence_gauge_svg
        result = render_confidence_gauge_svg(150.0)
        self.assertIn("100%", result)
        result2 = render_confidence_gauge_svg(-10.0)
        self.assertIn("0%", result2)

    def test_render_outcome_badge_win(self):
        from pages.helpers.joseph_live_desk import render_outcome_badge
        result = render_outcome_badge("win")
        self.assertIn("✅", result)
        self.assertIn("WIN", result)
        self.assertIn("#34d399", result)

    def test_render_outcome_badge_loss(self):
        from pages.helpers.joseph_live_desk import render_outcome_badge
        result = render_outcome_badge("loss")
        self.assertIn("❌", result)
        self.assertIn("LOSS", result)
        self.assertIn("#fca5a5", result)

    def test_render_outcome_badge_pending(self):
        from pages.helpers.joseph_live_desk import render_outcome_badge
        result = render_outcome_badge("pending")
        self.assertIn("⏳", result)
        self.assertIn("PENDING", result)

    def test_render_outcome_badge_even(self):
        from pages.helpers.joseph_live_desk import render_outcome_badge
        result = render_outcome_badge("even")
        self.assertIn("🔄", result)

    def test_render_empty_state_message(self):
        from pages.helpers.joseph_live_desk import render_empty_state
        result = render_empty_state("Nothing here yet")
        self.assertIn("Nothing here yet", result)
        self.assertIn("📭", result)

    def test_render_empty_state_with_cta(self):
        from pages.helpers.joseph_live_desk import render_empty_state
        result = render_empty_state("No data", cta_text="Go →", cta_page="/live")
        self.assertIn("Go →", result)
        self.assertIn("/live", result)
        self.assertIn("<a", result)

    def test_render_empty_state_without_cta(self):
        from pages.helpers.joseph_live_desk import render_empty_state
        result = render_empty_state("No data")
        self.assertNotIn("<a", result)

    def test_render_empty_state_escapes_html(self):
        from pages.helpers.joseph_live_desk import render_empty_state
        result = render_empty_state("<script>bad</script>")
        self.assertNotIn("<script>", result)

    def test_render_verdict_heatmap_html_basic(self):
        from pages.helpers.joseph_live_desk import render_verdict_heatmap_html
        results = [
            {"verdict": "SMASH"},
            {"verdict": "SMASH"},
            {"verdict": "LEAN"},
            {"verdict": "FADE"},
        ]
        html = render_verdict_heatmap_html(results)
        self.assertIn("SMASH", html)
        self.assertIn("LEAN", html)
        self.assertIn("FADE", html)
        self.assertIn("VERDICT DISTRIBUTION", html)
        self.assertIn("50%", html)  # SMASH is 2/4 = 50%
        self.assertIn("25%", html)  # LEAN/FADE are each 1/4

    def test_render_verdict_heatmap_html_empty(self):
        from pages.helpers.joseph_live_desk import render_verdict_heatmap_html
        self.assertEqual(render_verdict_heatmap_html([]), "")

    def test_render_verdict_heatmap_html_no_verdicts(self):
        from pages.helpers.joseph_live_desk import render_verdict_heatmap_html
        self.assertEqual(render_verdict_heatmap_html([{"edge": 5}]), "")


# ── Tests for new Joseph enhancements ─────────────────────────

class TestStudioNewFeatures(unittest.TestCase):
    """Test new Studio page features: monologue, hot take, voice input."""

    def setUp(self):
        self.filepath = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "7_🎙️_The_Studio.py",
        )
        with open(self.filepath, "r") as fh:
            self.source = fh.read()

    def test_monologue_of_the_night(self):
        """Studio should have Joseph's Monologue of the Night."""
        self.assertIn("MONOLOGUE OF THE NIGHT", self.source)

    def test_monologue_openers_defined(self):
        self.assertIn("_MONOLOGUE_OPENERS", self.source)

    def test_generate_monologue_function(self):
        self.assertIn("_generate_monologue", self.source)

    def test_hot_take_mode_toggle(self):
        """Studio should have a Hot Take Mode toggle."""
        self.assertIn("joseph_hot_take_mode", self.source)
        self.assertIn("Hot Take Mode", self.source)

    def test_voice_to_text_input(self):
        """Studio should have voice-to-text input."""
        self.assertIn("SpeechRecognition", self.source)
        self.assertIn("Ask Joseph a question", self.source)


class TestConditionalAvatar(unittest.TestCase):
    """Test vibe-based avatar selection in joseph_live_desk."""

    def test_get_joseph_avatar_for_vibe_importable(self):
        from pages.helpers.joseph_live_desk import get_joseph_avatar_for_vibe
        self.assertTrue(callable(get_joseph_avatar_for_vibe))

    def test_get_joseph_avatar_panicking_b64_importable(self):
        from pages.helpers.joseph_live_desk import get_joseph_avatar_panicking_b64
        self.assertTrue(callable(get_joseph_avatar_panicking_b64))

    def test_get_joseph_avatar_victory_b64_importable(self):
        from pages.helpers.joseph_live_desk import get_joseph_avatar_victory_b64
        self.assertTrue(callable(get_joseph_avatar_victory_b64))

    def test_vibe_returns_string(self):
        from pages.helpers.joseph_live_desk import get_joseph_avatar_for_vibe
        result = get_joseph_avatar_for_vibe("Victory")
        self.assertIsInstance(result, str)

    def test_vibe_panic_returns_string(self):
        from pages.helpers.joseph_live_desk import get_joseph_avatar_for_vibe
        result = get_joseph_avatar_for_vibe("Panic")
        self.assertIsInstance(result, str)

    def test_vibe_empty_returns_string(self):
        from pages.helpers.joseph_live_desk import get_joseph_avatar_for_vibe
        result = get_joseph_avatar_for_vibe("")
        self.assertIsInstance(result, str)


class TestJosephCompareProps(unittest.TestCase):
    """Test joseph_compare_props in joseph_brain."""

    def setUp(self):
        from engine.joseph_brain import joseph_compare_props
        self.compare = joseph_compare_props

    def test_importable(self):
        self.assertTrue(callable(self.compare))

    def test_empty_lines(self):
        result = self.compare("Test Player", "points", [])
        self.assertIn("best_platform", result)
        self.assertEqual(result["best_platform"], "")

    def test_single_line(self):
        result = self.compare("LeBron James", "points", [
            {"platform": "PrizePicks", "line": 24.5},
        ])
        self.assertEqual(result["best_platform"], "PrizePicks")
        self.assertEqual(result["line_spread"], 0.0)

    def test_multiple_lines_best_value(self):
        result = self.compare("LeBron James", "points", [
            {"platform": "PrizePicks", "line": 24.5},
            {"platform": "DraftKings", "line": 25.5},
            {"platform": "Underdog", "line": 26.0},
        ])
        self.assertEqual(result["best_platform"], "PrizePicks")
        self.assertEqual(result["line_spread"], 1.5)
        self.assertIn("all_lines", result)
        self.assertEqual(len(result["all_lines"]), 3)

    def test_same_lines_no_edge(self):
        result = self.compare("Curry", "three_pointers", [
            {"platform": "PrizePicks", "line": 4.5},
            {"platform": "DraftKings", "line": 4.5},
        ])
        self.assertEqual(result["line_spread"], 0.0)


class TestJosephGutCall(unittest.TestCase):
    """Test joseph_gut_call in joseph_brain."""

    def setUp(self):
        from engine.joseph_brain import joseph_gut_call
        self.gut_call = joseph_gut_call

    def test_importable(self):
        self.assertTrue(callable(self.gut_call))

    def test_no_trigger(self):
        result = self.gut_call({"verdict": "LEAN", "edge": 5.0}, [])
        self.assertFalse(result["is_gut_call"])

    def test_revenge_game_trigger(self):
        result = self.gut_call(
            {"verdict": "FADE", "edge": 1.0},
            ["revenge_game"],
        )
        self.assertTrue(result["is_gut_call"])
        self.assertEqual(result["gut_direction"], "OVER")
        self.assertIn("revenge", result["gut_reason"].lower())

    def test_high_edge_resists_gut(self):
        result = self.gut_call(
            {"verdict": "SMASH", "edge": 10.0},
            ["revenge_game"],
        )
        self.assertFalse(result["is_gut_call"])

    def test_back_to_back_under(self):
        result = self.gut_call(
            {"verdict": "STAY_AWAY", "edge": 1.5},
            ["back_to_back"],
        )
        self.assertTrue(result["is_gut_call"])
        self.assertEqual(result["gut_direction"], "UNDER")


class TestPositionSpecificTake(unittest.TestCase):
    """Test position-specific language in joseph_eval."""

    def test_joseph_take_not_empty(self):
        from engine.joseph_eval import joseph_grade_player
        player = {
            "name": "Test Player", "position": "PG",
            "points_avg": 25.0, "assists_avg": 8.0, "rebounds_avg": 5.0,
            "steals_avg": 1.5, "blocks_avg": 0.5, "turnovers_avg": 3.0,
            "minutes_avg": 35.0, "fg3a": 6.0, "fg3_pct": 0.38,
            "fga": 18.0, "fta": 6.0, "defensive_rebounds_avg": 4.0,
        }
        ctx = {
            "opponent_team": "BOS", "opponent_def_rating": 108,
            "narrative_tags": [], "scheme": {"primary_scheme": "switch_everything"},
            "spread": -3.0, "total": 220, "rest_days": 2,
        }
        result = joseph_grade_player(player, ctx)
        self.assertIn("joseph_take", result)
        self.assertTrue(len(result["joseph_take"]) > 0)

    def test_center_take_different(self):
        from engine.joseph_eval import joseph_grade_player
        player_pg = {"name": "PG", "position": "PG", "points_avg": 20.0,
                     "assists_avg": 7.0, "rebounds_avg": 4.0, "steals_avg": 1.0,
                     "blocks_avg": 0.2, "turnovers_avg": 3.0, "minutes_avg": 32.0,
                     "fg3a": 5.0, "fg3_pct": 0.35, "fga": 15.0, "fta": 4.0,
                     "defensive_rebounds_avg": 3.0}
        player_c = {"name": "C", "position": "C", "points_avg": 20.0,
                    "assists_avg": 3.0, "rebounds_avg": 11.0, "steals_avg": 0.5,
                    "blocks_avg": 2.0, "turnovers_avg": 2.0, "minutes_avg": 32.0,
                    "fg3a": 1.0, "fg3_pct": 0.30, "fga": 14.0, "fta": 5.0,
                    "defensive_rebounds_avg": 8.0}
        ctx = {"opponent_team": "", "opponent_def_rating": 110,
               "narrative_tags": [], "scheme": {}, "spread": 0, "total": 0,
               "rest_days": 2}
        pg_result = joseph_grade_player(player_pg, ctx)
        c_result = joseph_grade_player(player_c, ctx)
        # Different positions should generate different takes
        self.assertNotEqual(pg_result["joseph_take"], c_result["joseph_take"])


class TestJosephDiary(unittest.TestCase):
    """Test the persistent diary module."""

    def test_imports(self):
        from tracking.joseph_diary import (
            diary_log_entry,
            diary_get_entry,
            diary_get_yesterday,
            diary_get_week_summary,
            diary_get_yesterday_reference,
        )
        self.assertTrue(callable(diary_log_entry))
        self.assertTrue(callable(diary_get_entry))
        self.assertTrue(callable(diary_get_yesterday))
        self.assertTrue(callable(diary_get_week_summary))
        self.assertTrue(callable(diary_get_yesterday_reference))

    def test_week_summary_structure(self):
        from tracking.joseph_diary import diary_get_week_summary
        summary = diary_get_week_summary()
        self.assertIn("week_wins", summary)
        self.assertIn("week_losses", summary)
        self.assertIn("brag_intensity", summary)
        self.assertIn("narrative_arc", summary)
        self.assertIsInstance(summary["brag_intensity"], float)

    def test_yesterday_reference_returns_string(self):
        from tracking.joseph_diary import diary_get_yesterday_reference
        result = diary_get_yesterday_reference()
        self.assertIsInstance(result, str)


class TestLivePersonaExpansion(unittest.TestCase):
    """Test expanded live_persona features."""

    def test_record_chase_fragments(self):
        from agent.live_persona import _RECORD_CHASE
        self.assertGreater(len(_RECORD_CHASE), 0)
        # Should have format placeholders
        self.assertIn("{remaining}", _RECORD_CHASE[0])

    def test_redemption_arc_fragments(self):
        from agent.live_persona import _REDEMPTION_ARC
        self.assertGreater(len(_REDEMPTION_ARC), 0)

    def test_quarter_voice_dict(self):
        from agent.live_persona import _QUARTER_VOICE
        self.assertIn("Q1", _QUARTER_VOICE)
        self.assertIn("Q4", _QUARTER_VOICE)
        self.assertGreater(len(_QUARTER_VOICE["Q4"]), 0)

    def test_reaction_with_record_chase(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "record_chase": True,
            "record_remaining": 5,
            "record_stat": "points",
            "direction": "OVER",
        })
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_reaction_with_redemption(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "is_redemption": True,
            "direction": "OVER",
        })
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_reaction_with_quarter(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "quarter": "Q4",
            "direction": "OVER",
        })
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_prompt_includes_record_chase(self):
        from agent.live_persona import LIVE_JOSEPH_PROMPT
        self.assertIn("RECORD_CHASE", LIVE_JOSEPH_PROMPT)

    def test_prompt_includes_redemption(self):
        from agent.live_persona import LIVE_JOSEPH_PROMPT
        self.assertIn("Redemption Arc", LIVE_JOSEPH_PROMPT)


class TestBroadcastTicker(unittest.TestCase):
    """Test the global broadcast ticker in utils/components.py."""

    def test_ticker_css_exists(self):
        from utils.components import _TICKER_CSS
        self.assertIn("joseph-broadcast-ticker", _TICKER_CSS)
        self.assertIn("tickerScroll", _TICKER_CSS)

    def test_render_broadcast_ticker_importable(self):
        from utils.components import _render_broadcast_ticker
        self.assertTrue(callable(_render_broadcast_ticker))


class TestLiveModeCSS(unittest.TestCase):
    """Test Live Mode CSS additions."""

    def test_live_mode_avatar_css(self):
        from styles.live_theme import get_live_mode_avatar_css
        css = get_live_mode_avatar_css()
        self.assertIn("joseph-avatar-live-mode", css)
        self.assertIn("josephLivePulse", css)

    def test_direction_theme_colors(self):
        from styles.live_theme import get_live_mode_avatar_css
        css = get_live_mode_avatar_css()
        self.assertIn("direction-over", css)
        self.assertIn("direction-under", css)
        self.assertIn("#ff5e00", css)
        self.assertIn("#00c8ff", css)


if __name__ == "__main__":
    unittest.main()
