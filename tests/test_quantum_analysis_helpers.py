# ============================================================
# FILE: tests/test_quantum_analysis_helpers.py
# PURPOSE: Tests for pages/helpers/quantum_analysis_helpers.py
# ============================================================
import unittest
import html as _html

from pages.helpers.quantum_analysis_helpers import (
    JOSEPH_DESK_SIZE_CSS,
    IMPACT_COLORS,
    CATEGORY_EMOJI,
    SIGNAL_COLORS,
    SIGNAL_LABELS,
    PARLAY_STARS,
    PARLAY_LABELS,
    render_dfs_flex_edge_html,
    render_tier_distribution_html,
    render_news_alert_html,
    render_market_movement_html,
    render_uncertain_header_html,
    render_uncertain_pick_html,
    render_gold_tier_banner_html,
    render_best_single_bets_header_html,
    render_parlays_header_html,
    render_parlay_card_html,
    render_quantum_edge_gap_banner_html,
    render_quantum_edge_gap_card_html,
    _classify_flag_type,
)


class TestConstants(unittest.TestCase):
    """Verify module-level constants are correctly defined."""

    def test_joseph_css_has_style_tag(self):
        self.assertIn("<style>", JOSEPH_DESK_SIZE_CSS)
        self.assertIn("joseph-live-desk", JOSEPH_DESK_SIZE_CSS)

    def test_impact_colors_keys(self):
        self.assertIn("high", IMPACT_COLORS)
        self.assertIn("medium", IMPACT_COLORS)
        self.assertIn("low", IMPACT_COLORS)

    def test_category_emoji_keys(self):
        self.assertIn("injury", CATEGORY_EMOJI)
        self.assertIn("trade", CATEGORY_EMOJI)

    def test_signal_colors_and_labels(self):
        self.assertIn("sharp_buy", SIGNAL_COLORS)
        self.assertIn("sharp_fade", SIGNAL_LABELS)

    def test_parlay_stars_and_labels(self):
        self.assertEqual(PARLAY_LABELS[2], "Best 2-Leg Parlay")
        self.assertIn(6, PARLAY_STARS)


class TestDfsFlexEdge(unittest.TestCase):
    """Verify DFS Flex Edge card rendering."""

    def test_positive_edge_green(self):
        html = render_dfs_flex_edge_html(3, 5, 4.2)
        self.assertIn("DFS FLEX EDGE", html)
        self.assertIn("3/5 legs beat breakeven", html)
        self.assertIn("#00ff9d", html)  # positive edge color
        self.assertIn("+4.2%", html)

    def test_negative_edge_orange(self):
        html = render_dfs_flex_edge_html(1, 5, -2.5)
        self.assertIn("#ff5e00", html)  # negative edge color
        self.assertIn("-2.5%", html)

    def test_zero_edge(self):
        html = render_dfs_flex_edge_html(0, 0, 0.0)
        self.assertIn("0/0", html)


class TestTierDistribution(unittest.TestCase):
    """Verify tier distribution dashboard rendering."""

    def test_all_tiers_shown(self):
        html = render_tier_distribution_html(2, 3, 5, 1, 12.5, None)
        self.assertIn("2 Platinum", html)
        self.assertIn("3 Gold", html)
        self.assertIn("5 Silver", html)
        self.assertIn("1 Bronze", html)
        self.assertIn("Avg Edge: 12.5%", html)

    def test_best_pick_shown(self):
        best = {
            "player_name": "LeBron James",
            "stat_type": "points",
            "line": 25.5,
            "direction": "OVER",
            "confidence_score": 88,
            "tier": "Platinum",
        }
        html = render_tier_distribution_html(1, 0, 0, 0, 15.0, best)
        self.assertIn("LeBron James", html)
        self.assertIn("More", html)
        self.assertIn("25.5", html)
        self.assertIn("88/100", html)
        self.assertIn("💎", html)

    def test_no_best_pick(self):
        html = render_tier_distribution_html(0, 0, 0, 0, 0.0, None)
        self.assertNotIn("Best Pick", html)

    def test_under_direction(self):
        best = {
            "player_name": "Steph Curry",
            "stat_type": "threes",
            "line": 4.5,
            "direction": "UNDER",
            "confidence_score": 72,
            "tier": "Gold",
        }
        html = render_tier_distribution_html(0, 1, 0, 0, 8.0, best)
        self.assertIn("Less", html)


class TestNewsAlertHtml(unittest.TestCase):
    """Verify player news alert card rendering."""

    def test_basic_news(self):
        item = {
            "title": "Player Injury Update",
            "player_name": "Kevin Durant",
            "body": "Expected to miss 2 games.",
            "category": "injury",
            "impact": "HIGH",
            "published_at": "2026-04-07T12:00:00",
        }
        html = render_news_alert_html(item)
        self.assertIn("Player Injury Update", html)
        self.assertIn("Kevin Durant", html)
        self.assertIn("Expected to miss 2 games.", html)
        self.assertIn("🏥", html)
        self.assertIn("#ff4444", html)  # high impact color
        self.assertIn("2026-04-07", html)

    def test_xss_prevention(self):
        item = {
            "title": '<script>alert("xss")</script>',
            "player_name": "Safe Player",
            "body": "",
            "category": "",
            "impact": "low",
            "published_at": "",
        }
        html = render_news_alert_html(item)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_long_body_truncation(self):
        item = {
            "title": "News",
            "player_name": "Player",
            "body": "A" * 300,
            "category": "",
            "impact": "",
            "published_at": "",
        }
        html = render_news_alert_html(item)
        self.assertIn("…", html)

    def test_empty_body(self):
        item = {
            "title": "News",
            "player_name": "Player",
            "body": "",
            "category": "",
            "impact": "medium",
            "published_at": "",
        }
        html = render_news_alert_html(item)
        self.assertNotIn("font-size:0.82rem", html)  # body div not rendered


class TestMarketMovementHtml(unittest.TestCase):
    """Verify market movement alert card rendering."""

    def test_sharp_buy(self):
        result = {
            "player_name": "Jayson Tatum",
            "stat_type": "points",
            "market_movement": {
                "direction": "OVER",
                "line_shift": 1.5,
                "signal": "sharp_buy",
                "confidence_adjustment": 3.2,
            },
        }
        html = render_market_movement_html(result)
        self.assertIn("Jayson Tatum", html)
        self.assertIn("Points", html)
        self.assertIn("🟢 SHARP BUY", html)
        self.assertIn("+1.5", html)
        self.assertIn("+3.2", html)

    def test_neutral_signal(self):
        result = {
            "player_name": "Player",
            "stat_type": "assists",
            "market_movement": {
                "direction": "",
                "line_shift": 0.0,
                "signal": "neutral",
                "confidence_adjustment": 0,
            },
        }
        html = render_market_movement_html(result)
        self.assertIn("⚪ NEUTRAL", html)
        # No confidence adj when 0
        self.assertNotIn("Confidence adj", html)


class TestUncertainPicks(unittest.TestCase):
    """Verify uncertain pick rendering."""

    def test_header_html(self):
        html = render_uncertain_header_html()
        self.assertIn("UNCERTAIN PICKS", html)
        self.assertIn("Conflicting Signals", html)
        self.assertIn("4 risk patterns", html)

    def test_classify_conflict(self):
        self.assertEqual(_classify_flag_type(["Conflicting directional forces"]), "Conflicting Forces")

    def test_classify_variance(self):
        self.assertEqual(_classify_flag_type(["High-variance stat"]), "High Variance")

    def test_classify_fatigue(self):
        self.assertEqual(_classify_flag_type(["Back-to-back fatigue"]), "Fatigue Risk")

    def test_classify_regression(self):
        self.assertEqual(_classify_flag_type(["Hot streak regression"]), "Regression Risk")

    def test_classify_unknown(self):
        self.assertEqual(_classify_flag_type(["some other flag"]), "Uncertain")

    def test_uncertain_pick_card(self):
        pick = {
            "player_name": "Luka Doncic",
            "player_team": "DAL",
            "stat_type": "assists",
            "direction": "OVER",
            "line": 8.5,
            "adjusted_projection": 7.2,
            "edge_percentage": -3.5,
            "risk_flags": ["Conflicting forces: 52% OVER vs 48% UNDER"],
        }
        html = render_uncertain_pick_html(pick)
        self.assertIn("Luka Doncic", html)
        self.assertIn("DAL", html)
        self.assertIn("Assists", html)
        self.assertIn("8.5", html)
        self.assertIn("7.2", html)
        self.assertIn("-3.5%", html)
        self.assertIn("Conflicting Forces", html)

    def test_uncertain_pick_no_team(self):
        pick = {
            "player_name": "Player",
            "stat_type": "points",
            "direction": "UNDER",
            "line": 20.5,
            "adjusted_projection": 18.0,
            "edge_percentage": 5.0,
            "risk_flags": [],
        }
        html = render_uncertain_pick_html(pick)
        self.assertIn("Player", html)
        # No team badge
        self.assertNotIn("rgba(255,193,7,0.15)", html)

    def test_inline_breakdown_appended(self):
        pick = {
            "player_name": "Player",
            "stat_type": "points",
            "direction": "OVER",
            "line": 20.0,
            "adjusted_projection": 22.0,
            "edge_percentage": 5.0,
            "risk_flags": [],
        }
        breakdown = '<div class="breakdown">test</div>'
        html = render_uncertain_pick_html(pick, inline_breakdown_html=breakdown)
        self.assertIn("test", html)


class TestBannerHeaders(unittest.TestCase):
    """Verify banner and header HTML generators."""

    def test_gold_tier_banner(self):
        html = render_gold_tier_banner_html()
        self.assertIn("Gold Tier Picks", html)
        self.assertIn("qam-gold-banner", html)

    def test_best_single_bets_header(self):
        html = render_best_single_bets_header_html()
        self.assertIn("Best Single Bets", html)
        self.assertIn("SAFE Score", html)

    def test_parlays_header(self):
        html = render_parlays_header_html()
        self.assertIn("Strongly Suggested Parlays", html)
        self.assertIn("EDGE Score", html)


class TestQuantumEdgeGapBanner(unittest.TestCase):
    """Verify Quantum Edge Gap banner rendering."""

    def test_banner_with_picks(self):
        picks = [
            {"edge_percentage": 18.5, "direction": "OVER"},
            {"edge_percentage": -16.2, "direction": "UNDER"},
            {"edge_percentage": 20.0, "direction": "OVER"},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("Quantum Edge Gap", html)
        self.assertIn("qam-edge-gap-banner", html)
        self.assertIn("3", html)  # total picks
        self.assertIn("2", html)  # over count
        self.assertIn("1", html)  # under count
        self.assertIn("18.2%", html)  # avg edge
        self.assertIn("20.0%", html)  # max edge

    def test_banner_empty_picks(self):
        html = render_quantum_edge_gap_banner_html([])
        self.assertIn("Quantum Edge Gap", html)
        self.assertIn("0", html)
        self.assertIn("0.0%", html)

    def test_banner_all_over(self):
        picks = [
            {"edge_percentage": 15.5, "direction": "OVER"},
            {"edge_percentage": 17.0, "direction": "OVER"},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("qeg-stats-row", html)
        self.assertIn("qeg-stat-pill", html)

    def test_banner_all_under(self):
        picks = [
            {"edge_percentage": -18.0, "direction": "UNDER"},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("18.0%", html)  # max and avg


class TestQuantumEdgeGapCard(unittest.TestCase):
    """Verify Quantum Edge Gap individual card rendering."""

    def test_over_card(self):
        result = {
            "player_name": "LeBron James",
            "stat_type": "points",
            "player_team": "LAL",
            "platform": "PrizePicks",
            "tier": "Gold",
            "line": 25.5,
            "confidence_score": 82,
            "probability_over": 0.72,
            "edge_percentage": 18.5,
            "direction": "OVER",
            "adjusted_projection": 28.3,
            "percentile_10": 20.1,
            "percentile_50": 27.5,
            "percentile_90": 35.2,
            "player_id": "2544",
        }
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("LeBron James", html)
        self.assertIn("LAL", html)
        self.assertIn("Points", html)
        self.assertIn("PrizePicks", html)
        self.assertIn("25.5", html)
        self.assertIn("72.0%", html)  # prob
        self.assertIn("+18.5%", html)  # edge
        self.assertIn("OVER", html)
        self.assertIn("28.3", html)  # projection
        self.assertIn("qeg-card-over", html)
        self.assertIn("qeg-dir-over", html)
        self.assertIn("🥇", html)  # Gold tier emoji
        self.assertIn("2544.png", html)  # headshot

    def test_under_card(self):
        result = {
            "player_name": "Steph Curry",
            "stat_type": "threes",
            "player_team": "GSW",
            "platform": "DraftKings",
            "tier": "Platinum",
            "line": 4.5,
            "confidence_score": 90,
            "probability_over": 0.25,
            "edge_percentage": -17.2,
            "direction": "UNDER",
            "adjusted_projection": 3.1,
            "percentile_10": 1.0,
            "percentile_50": 3.0,
            "percentile_90": 5.5,
            "player_id": "201939",
        }
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("Steph Curry", html)
        self.assertIn("UNDER", html)
        self.assertIn("-17.2%", html)
        self.assertIn("qeg-card-under", html)
        self.assertIn("qeg-dir-under", html)
        self.assertIn("💎", html)  # Platinum tier emoji

    def test_xss_prevention(self):
        result = {
            "player_name": '<script>alert("xss")</script>',
            "stat_type": "points",
            "player_team": "LAL",
            "platform": "Test",
            "tier": "Gold",
            "line": 20.0,
            "confidence_score": 50,
            "probability_over": 0.5,
            "edge_percentage": 16.0,
            "direction": "OVER",
            "adjusted_projection": 22.0,
        }
        html = render_quantum_edge_gap_card_html(result)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_missing_fields_defaults(self):
        result = {"player_name": "Test Player"}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("Test Player", html)
        self.assertIn("qeg-card", html)

    def test_no_headshot_without_player_id(self):
        result = {
            "player_name": "No ID Player",
            "stat_type": "rebounds",
            "direction": "OVER",
        }
        html = render_quantum_edge_gap_card_html(result)
        self.assertNotIn("qeg-headshot", html)


class TestQuantumEdgeGapCSS(unittest.TestCase):
    """Verify edge gap CSS is present in the theme."""

    def test_css_has_edge_gap_banner(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qam-edge-gap-banner", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_edge_gap_card(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-card", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_edge_gap_animation(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-border-glow", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-card-pulse", QUANTUM_CARD_MATRIX_CSS)


class TestParlayCard(unittest.TestCase):
    """Verify parlay combo card rendering."""

    def test_basic_parlay(self):
        entry = {
            "num_legs": 3,
            "picks": ["Player1 More 25.5 Points", "Player2 Less 8.5 Assists"],
            "reasons": ["Correlated matchup", "High edge"],
            "combined_prob": 45.2,
            "avg_edge": 8.5,
            "safe_avg": 82,
        }
        html = render_parlay_card_html(entry, card_index=0)
        self.assertIn("Best 3-Leg Parlay", html)
        self.assertIn("⭐⭐", html)
        self.assertIn("Player1", html)
        self.assertIn("Player2", html)
        self.assertIn("45.2%", html)
        self.assertIn("+8.5%", html)
        self.assertIn("82/100", html)
        # First card gets glow (now via CSS class instead of inline style)
        self.assertIn("qam-parlay-card-glow", html)

    def test_no_glow_for_third_card(self):
        entry = {
            "num_legs": 2,
            "picks": [],
            "reasons": [],
            "combined_prob": 0,
            "avg_edge": 0,
            "safe_avg": "—",
        }
        html = render_parlay_card_html(entry, card_index=2)
        self.assertNotIn("qam-parlay-card-glow", html)

    def test_xss_in_picks(self):
        entry = {
            "num_legs": 2,
            "picks": ['<script>alert("x")</script> More 5.0 Points'],
            "reasons": [],
            "strategy": "test",
            "combined_prob": 0,
            "avg_edge": 0,
            "safe_avg": 50,
        }
        html = render_parlay_card_html(entry, card_index=0)
        self.assertNotIn("<script>", html)


class TestPageImportsHelper(unittest.TestCase):
    """Verify the page file imports from the new helper module."""

    def test_page_imports_helper(self):
        import os
        page_path = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "3_⚡_Quantum_Analysis_Matrix.py",
        )
        with open(page_path, "r") as f:
            content = f.read()
        self.assertIn("from pages.helpers.quantum_analysis_helpers import", content)
        self.assertIn("render_dfs_flex_edge_html", content)
        self.assertIn("render_tier_distribution_html", content)
        self.assertIn("render_news_alert_html", content)
        self.assertIn("render_market_movement_html", content)
        self.assertIn("render_uncertain_pick_html", content)
        self.assertIn("render_parlay_card_html", content)
        self.assertIn("render_quantum_edge_gap_banner_html", content)
        self.assertIn("render_quantum_edge_gap_card_html", content)

    def test_page_no_longer_has_inline_dfs_html(self):
        """The DFS FLEX EDGE literal should now only be in the helper."""
        import os
        page_path = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "3_⚡_Quantum_Analysis_Matrix.py",
        )
        with open(page_path, "r") as f:
            content = f.read()
        # The literal "DFS FLEX EDGE" should not appear inline any more
        self.assertNotIn("DFS FLEX EDGE", content)


class TestContainerQueryCSS(unittest.TestCase):
    """Verify the CSS uses container queries."""

    def test_css_has_container_type(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("container-type: inline-size", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("container-name: qcm", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_container_queries(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("@container qcm", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_fallback(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("@supports not (container-type: inline-size)", QUANTUM_CARD_MATRIX_CSS)

    def test_grid_container_wrapper_in_renderers(self):
        import os
        renderer_path = os.path.join(
            os.path.dirname(__file__), "..",
            "utils", "renderers.py",
        )
        with open(renderer_path, "r") as f:
            content = f.read()
        self.assertIn('qcm-grid-container', content)


if __name__ == "__main__":
    unittest.main()
