# ============================================================
# FILE: tests/test_live_sweat.py
# PURPOSE: Unit tests for the Live Sweat dashboard modules:
#          data/live_tracker.py, engine/live_math.py,
#          styles/live_theme.py, agent/live_persona.py
# ============================================================

import unittest
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# SECTION 1: engine/live_math tests
# ============================================================

class TestLiveMathPacing(unittest.TestCase):
    """Tests for calculate_live_pace()."""

    def setUp(self):
        from engine.live_math import calculate_live_pace
        self.calc = calculate_live_pace

    def test_basic_pace_projection(self):
        """Pace = (10 pts / 20 min) * 48 = 24.0."""
        result = self.calc(10, 20, 24.5)
        self.assertAlmostEqual(result["projected_final"], 24.0, places=1)
        self.assertTrue(result["on_pace"] is False)  # 24.0 < 24.5

    def test_cashed_flag(self):
        """If current_stat >= target, cashed must be True."""
        result = self.calc(25, 30, 24.5)
        self.assertTrue(result["cashed"])

    def test_not_cashed(self):
        result = self.calc(10, 20, 24.5)
        self.assertFalse(result["cashed"])

    def test_zero_minutes_safe(self):
        """Zero minutes should not cause division-by-zero."""
        result = self.calc(0, 0, 20)
        self.assertEqual(result["projected_final"], 0.0)

    def test_blowout_risk_third_quarter(self):
        """Score diff > 20 in Q3 triggers blowout_risk."""
        result = self.calc(10, 20, 30, live_score_diff=25, period="3")
        self.assertTrue(result["blowout_risk"])
        self.assertLess(result["projected_final"], 24.0)

    def test_no_blowout_first_quarter(self):
        """Blowout risk should not trigger in Q1 even with big diff."""
        result = self.calc(10, 20, 30, live_score_diff=30, period="1")
        self.assertFalse(result["blowout_risk"])

    def test_blowout_risk_fourth_quarter(self):
        result = self.calc(10, 20, 30, live_score_diff=25, period="Q4")
        self.assertTrue(result["blowout_risk"])

    def test_foul_trouble_first_half(self):
        """3+ fouls with < 24 min triggers foul_trouble."""
        result = self.calc(8, 18, 25, current_fouls=3)
        self.assertTrue(result["foul_trouble"])

    def test_no_foul_trouble_second_half(self):
        """3 fouls after 24 min should NOT be foul trouble."""
        result = self.calc(15, 30, 25, current_fouls=3)
        self.assertFalse(result["foul_trouble"])

    def test_distance_calculation(self):
        result = self.calc(10, 20, 25)
        self.assertAlmostEqual(result["distance"], 15.0, places=1)

    def test_distance_when_cashed(self):
        result = self.calc(30, 20, 25)
        self.assertAlmostEqual(result["distance"], 0.0, places=1)

    def test_pct_of_target(self):
        result = self.calc(12, 24, 24)
        self.assertAlmostEqual(result["pct_of_target"], 100.0, places=0)

    def test_pace_per_minute(self):
        result = self.calc(10, 20, 25)
        self.assertAlmostEqual(result["pace_per_minute"], 0.5, places=2)

    def test_negative_inputs_clamped(self):
        result = self.calc(-5, -10, 20)
        self.assertEqual(result["current_stat"], 0.0)
        self.assertEqual(result["minutes_played"], 0.0)

    def test_return_keys(self):
        result = self.calc(10, 20, 25)
        expected_keys = {
            "current_stat", "target_stat", "distance", "minutes_played",
            "pace_per_minute", "projected_final", "pct_of_target",
            "blowout_risk", "foul_trouble", "on_pace", "cashed",
        }
        self.assertEqual(set(result.keys()), expected_keys)


class TestPaceColorTier(unittest.TestCase):
    """Tests for pace_color_tier()."""

    def setUp(self):
        from engine.live_math import pace_color_tier
        self.tier = pace_color_tier

    def test_blue(self):
        self.assertEqual(self.tier(30), "blue")
        self.assertEqual(self.tier(0), "blue")
        self.assertEqual(self.tier(50), "blue")

    def test_orange(self):
        self.assertEqual(self.tier(51), "orange")
        self.assertEqual(self.tier(75), "orange")
        self.assertEqual(self.tier(85), "orange")

    def test_red(self):
        self.assertEqual(self.tier(86), "red")
        self.assertEqual(self.tier(95), "red")
        self.assertEqual(self.tier(99), "red")

    def test_green(self):
        self.assertEqual(self.tier(100), "green")
        self.assertEqual(self.tier(150), "green")


# ============================================================
# SECTION 2: data/live_tracker entity matcher tests
# ============================================================

class TestMatchLivePlayer(unittest.TestCase):
    """Tests for match_live_player()."""

    def setUp(self):
        from data.live_tracker import match_live_player
        self.match = match_live_player
        self.players = [
            {"name": "Shai Gilgeous-Alexander", "pts": 30},
            {"name": "LeBron James", "pts": 22},
            {"name": "Anthony Edwards", "pts": 18},
            {"name": "Nikola Jokic", "pts": 25},
            {"name": "Stephen Curry", "pts": 28},
        ]

    def test_exact_match(self):
        result = self.match("LeBron James", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "LeBron James")

    def test_case_insensitive(self):
        result = self.match("lebron james", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "LeBron James")

    def test_fuzzy_match(self):
        result = self.match("Lebron Jame", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "LeBron James")

    def test_nickname_sga(self):
        result = self.match("SGA", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Shai Gilgeous-Alexander")

    def test_nickname_lbj(self):
        result = self.match("LBJ", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "LeBron James")

    def test_nickname_ant(self):
        result = self.match("ant", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Anthony Edwards")

    def test_nickname_steph(self):
        result = self.match("steph", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Stephen Curry")

    def test_nickname_jokic(self):
        result = self.match("jokic", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Nikola Jokic")

    def test_substring_match(self):
        """Partial name should still match."""
        result = self.match("Gilgeous", self.players)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Shai Gilgeous-Alexander")

    def test_no_match(self):
        result = self.match("zzz_nonexistent", self.players)
        self.assertIsNone(result)

    def test_empty_target(self):
        self.assertIsNone(self.match("", self.players))

    def test_empty_list(self):
        self.assertIsNone(self.match("LeBron James", []))

    def test_none_inputs(self):
        self.assertIsNone(self.match(None, self.players))
        self.assertIsNone(self.match("LeBron", None))


class TestGetAllLivePlayers(unittest.TestCase):

    def test_flattens_players(self):
        from data.live_tracker import get_all_live_players
        games = [
            {
                "home_players": [{"name": "A", "pts": 1}],
                "away_players": [{"name": "B", "pts": 2}],
            },
            {
                "home_players": [{"name": "C", "pts": 3}],
                "away_players": [],
            },
        ]
        result = get_all_live_players(games)
        self.assertEqual(len(result), 3)
        names = {p["name"] for p in result}
        self.assertEqual(names, {"A", "B", "C"})


# ============================================================
# SECTION 3: styles/live_theme tests
# ============================================================

class TestLiveThemeCSS(unittest.TestCase):
    """Tests for the Live Sweat CSS generator."""

    def test_returns_style_tag(self):
        from styles.live_theme import get_live_sweat_css
        css = get_live_sweat_css()
        self.assertIn("<style>", css)
        self.assertIn("</style>", css)

    def test_contains_sweat_card(self):
        from styles.live_theme import get_live_sweat_css
        css = get_live_sweat_css()
        self.assertIn(".sweat-card", css)
        self.assertIn("backdrop-filter", css)
        self.assertIn("blur(12px)", css)

    def test_progress_fill_classes(self):
        from styles.live_theme import get_live_sweat_css
        css = get_live_sweat_css()
        for cls in ("progress-fill-blue", "progress-fill-orange",
                     "progress-fill-red", "progress-fill-green"):
            self.assertIn(cls, css, f"Missing {cls}")

    def test_progress_base(self):
        from styles.live_theme import get_live_sweat_css
        css = get_live_sweat_css()
        self.assertIn(".progress-base", css)

    def test_pulse_animation(self):
        from styles.live_theme import get_live_sweat_css
        css = get_live_sweat_css()
        self.assertIn("pulse-red", css)

    def test_green_glow(self):
        from styles.live_theme import get_live_sweat_css
        css = get_live_sweat_css()
        self.assertIn("box-shadow", css)


class TestRenderProgressBar(unittest.TestCase):

    def test_returns_html(self):
        from styles.live_theme import render_progress_bar
        html = render_progress_bar(50.0, "blue")
        self.assertIn("progress-fill-blue", html)
        self.assertIn("progress-base", html)

    def test_clamps_above_100(self):
        from styles.live_theme import render_progress_bar
        html = render_progress_bar(150, "green")
        self.assertIn("width:100.0%", html)

    def test_clamps_below_0(self):
        from styles.live_theme import render_progress_bar
        html = render_progress_bar(-10, "blue")
        self.assertIn("width:0", html)


class TestRenderSweatCard(unittest.TestCase):

    def test_basic_card(self):
        from styles.live_theme import render_sweat_card
        html = render_sweat_card(
            player_name="LeBron James",
            stat_type="points",
            current_stat=20,
            target_stat=25.5,
            projected_final=28.0,
            pct_of_target=110,
            color_tier="green",
        )
        self.assertIn("LeBron James", html)
        self.assertIn("sweat-card", html)

    def test_cashed_card(self):
        from styles.live_theme import render_sweat_card
        html = render_sweat_card(
            player_name="Test", stat_type="points",
            current_stat=30, target_stat=25,
            projected_final=35, pct_of_target=140,
            color_tier="green", cashed=True,
        )
        self.assertIn("sweat-card-cashed", html)
        self.assertIn("CASHED", html)

    def test_blowout_badge(self):
        from styles.live_theme import render_sweat_card
        html = render_sweat_card(
            player_name="Test", stat_type="points",
            current_stat=10, target_stat=25,
            projected_final=15, pct_of_target=60,
            color_tier="orange", blowout_risk=True,
        )
        self.assertIn("Blowout Risk", html)

    def test_foul_badge(self):
        from styles.live_theme import render_sweat_card
        html = render_sweat_card(
            player_name="Test", stat_type="points",
            current_stat=10, target_stat=25,
            projected_final=15, pct_of_target=60,
            color_tier="orange", foul_trouble=True,
        )
        self.assertIn("Foul Trouble", html)

    def test_html_escape(self):
        """Player name with HTML special chars must be escaped."""
        from styles.live_theme import render_sweat_card
        html = render_sweat_card(
            player_name='<script>alert("xss")</script>',
            stat_type="points", current_stat=10, target_stat=25,
            projected_final=15, pct_of_target=60, color_tier="blue",
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


# ============================================================
# SECTION 4: agent/live_persona tests
# ============================================================

class TestJosephLiveReaction(unittest.TestCase):

    def test_cashed_reaction(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({"cashed": True})
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_blowout_reaction(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "cashed": False, "blowout_risk": True, "foul_trouble": False,
        })
        self.assertIsInstance(result, str)

    def test_foul_reaction(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "cashed": False, "blowout_risk": False, "foul_trouble": True,
        })
        self.assertIsInstance(result, str)

    def test_on_pace_reaction(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "cashed": False, "blowout_risk": False,
            "foul_trouble": False, "on_pace": True,
        })
        self.assertIsInstance(result, str)

    def test_behind_pace_reaction(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({
            "cashed": False, "blowout_risk": False,
            "foul_trouble": False, "on_pace": False,
        })
        self.assertIsInstance(result, str)

    def test_invalid_input(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction(None)
        self.assertIsInstance(result, str)

    def test_empty_dict(self):
        from agent.live_persona import get_joseph_live_reaction
        result = get_joseph_live_reaction({})
        self.assertIsInstance(result, str)

    def test_priority_cashed_over_blowout(self):
        """Cashed takes priority even if blowout_risk is set."""
        from agent.live_persona import (
            get_joseph_live_reaction, _CASHED_BRAGS,
        )
        result = get_joseph_live_reaction({
            "cashed": True, "blowout_risk": True,
        })
        self.assertIn(result, _CASHED_BRAGS)


class TestStreamJosephText(unittest.TestCase):

    def test_yields_characters(self):
        from agent.live_persona import stream_joseph_text
        text = "Hello"
        chars = list(stream_joseph_text(text))
        self.assertEqual(chars, ["H", "e", "l", "l", "o"])

    def test_empty_string(self):
        from agent.live_persona import stream_joseph_text
        chars = list(stream_joseph_text(""))
        self.assertEqual(chars, [])


# ============================================================
# SECTION 5: Live Sweat page file structure tests
# ============================================================

class TestLiveSweatPageFile(unittest.TestCase):
    """Verify the Live Sweat page file exists and has expected structure."""

    @classmethod
    def setUpClass(cls):
        page_path = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "5_💦_Live_Sweat.py",
        )
        with open(page_path, "r", encoding="utf-8") as f:
            cls.source = f.read()

    def test_valid_python_syntax(self):
        compile(self.source, "5_💦_Live_Sweat.py", "exec")

    def test_page_config_present(self):
        self.assertIn("set_page_config", self.source)

    def test_imports_live_tracker(self):
        self.assertIn("from data.live_tracker import", self.source)

    def test_imports_live_math(self):
        self.assertIn("from engine.live_math import", self.source)

    def test_imports_live_theme(self):
        self.assertIn("from styles.live_theme import", self.source)

    def test_imports_live_persona(self):
        self.assertIn("from agent.live_persona import", self.source)

    def test_autorefresh_imported(self):
        self.assertIn("streamlit_autorefresh", self.source)

    def test_autorefresh_interval(self):
        self.assertIn("120_000", self.source)

    def test_global_css(self):
        self.assertIn("get_global_css", self.source)

    def test_live_css(self):
        self.assertIn("get_live_sweat_css", self.source)

    def test_balloons_trigger(self):
        self.assertIn("st.balloons()", self.source)

    def test_vibe_check_section(self):
        self.assertIn("Vibe Check", self.source)

    def test_write_stream(self):
        self.assertIn("st.write_stream", self.source)

    def test_cashed_label(self):
        self.assertIn("Cashed", self.source)


# ============================================================
# SECTION 6: data/live_tracker fetcher tests
# ============================================================

class TestFetchLiveBoxscoresImpl(unittest.TestCase):
    """Test _fetch_live_boxscores_impl with mocked ClearSports data."""

    def test_returns_list(self):
        from data.live_tracker import _fetch_live_boxscores_impl
        # Should return list even when API is unreachable
        result = _fetch_live_boxscores_impl()
        self.assertIsInstance(result, list)

    def test_player_extraction(self):
        """Ensure player stats are parsed from game dicts."""
        from data import live_tracker
        from unittest.mock import patch

        mock_data = [{
            "game_id": "123",
            "home_team": "LAL",
            "away_team": "BOS",
            "home_score": 100,
            "away_score": 95,
            "period": "3",
            "game_clock": "5:30",
            "status": "In Progress",
            "home_players": [
                {
                    "name": "LeBron James",
                    "statistics": {
                        "pts": 22, "reb": 8, "ast": 6,
                        "stl": 1, "blk": 1, "tov": 3,
                        "fg3m": 2, "minutes": 28, "pf": 2,
                    },
                }
            ],
            "away_players": [
                {
                    "name": "Jayson Tatum",
                    "statistics": {
                        "pts": 30, "reb": 7, "ast": 4,
                        "stl": 2, "blk": 0, "tov": 1,
                        "fg3m": 5, "minutes": 30, "pf": 1,
                    },
                }
            ],
        }]

        with patch.object(
            live_tracker, "_fetch_live_boxscores_impl",
            wraps=live_tracker._fetch_live_boxscores_impl,
        ):
            with patch(
                "data.clearsports_client.fetch_live_scores",
                return_value=mock_data,
            ):
                games = live_tracker._fetch_live_boxscores_impl()

        self.assertEqual(len(games), 1)
        home = games[0]["home_players"]
        away = games[0]["away_players"]
        self.assertEqual(len(home), 1)
        self.assertEqual(home[0]["name"], "LeBron James")
        self.assertEqual(home[0]["pts"], 22)
        self.assertEqual(away[0]["name"], "Jayson Tatum")
        self.assertEqual(away[0]["fg3m"], 5)
        self.assertEqual(away[0]["fouls"], 1)


if __name__ == "__main__":
    unittest.main()
