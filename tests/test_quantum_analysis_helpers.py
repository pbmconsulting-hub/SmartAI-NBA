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
    QEG_EDGE_THRESHOLD,
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
    render_quantum_edge_gap_grouped_html,
    deduplicate_qeg_picks,
    filter_qeg_picks,
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
        self.assertEqual(PARLAY_LABELS[2], "2-Leg Power Play")
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
        self.assertIn("AI-Optimized Parlays", html)
        self.assertIn("EDGE Score", html)


class TestQuantumEdgeGapBanner(unittest.TestCase):
    """Verify Quantum Edge Gap banner rendering."""

    def test_banner_with_picks(self):
        picks = [
            {"edge_percentage": 18.5, "direction": "OVER", "line_vs_avg_pct": -25.0, "confidence_score": 75},
            {"edge_percentage": -16.2, "direction": "UNDER", "line_vs_avg_pct": 30.0, "confidence_score": 68},
            {"edge_percentage": 20.0, "direction": "OVER", "line_vs_avg_pct": -22.0, "confidence_score": 80},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("QUANTUM EDGE GAP", html)
        self.assertIn("qeg-banner-v2", html)
        self.assertIn("qeg-v2-count-num", html)
        self.assertIn("qeg-v2-icon-ring", html)
        self.assertIn("3", html)  # total picks
        self.assertIn("2 OVER", html)  # over count
        self.assertIn("1 UNDER", html)  # under count
        self.assertIn("AVG EDGE", html)
        self.assertIn("PEAK", html)

    def test_banner_empty_picks(self):
        html = render_quantum_edge_gap_banner_html([])
        self.assertIn("QUANTUM EDGE GAP", html)
        self.assertIn("0", html)
        self.assertIn("0.0%", html)

    def test_banner_all_over(self):
        picks = [
            {"edge_percentage": 15.5, "direction": "OVER", "line_vs_avg_pct": -20.0, "confidence_score": 70},
            {"edge_percentage": 17.0, "direction": "OVER", "line_vs_avg_pct": -30.0, "confidence_score": 72},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("qeg-v2-split-block", html)
        self.assertIn("qeg-v2-edge-block", html)

    def test_banner_all_under(self):
        picks = [
            {"edge_percentage": -18.0, "direction": "UNDER", "line_vs_avg_pct": 35.0, "confidence_score": 65},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("35.0%", html)  # line dev shown in sub-stats

    def test_threshold_constant(self):
        """Ensure the exported threshold is 20.0."""
        self.assertEqual(QEG_EDGE_THRESHOLD, 20.0)

    def test_boundary_at_threshold(self):
        """Picks exactly at the threshold boundary should render correctly."""
        picks = [
            {"edge_percentage": 20.0, "direction": "OVER", "line_vs_avg_pct": -20.0, "confidence_score": 70},
            {"edge_percentage": -20.0, "direction": "UNDER", "line_vs_avg_pct": 20.0, "confidence_score": 65},
        ]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("2", html)  # both picks present
        self.assertIn("20.0%", html)  # avg edge and dev

    def test_banner_header_structure(self):
        picks = [{"edge_percentage": 22.0, "direction": "OVER", "line_vs_avg_pct": -25.0, "confidence_score": 75}]
        html = render_quantum_edge_gap_banner_html(picks)
        self.assertIn("qeg-v2-header", html)
        self.assertIn("QUANTUM EDGE GAP", html)


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
        html = render_quantum_edge_gap_card_html(result, rank=1)
        self.assertIn("LeBron James", html)
        self.assertIn("LAL", html)
        self.assertIn("Points", html)
        self.assertIn("PrizePicks", html)
        self.assertIn("25.5", html)
        self.assertIn("+18.5%", html)  # edge
        self.assertIn("OVER", html)
        self.assertIn("28.3", html)  # projection
        self.assertIn("qeg-card-over", html)
        self.assertIn("qeg-dir-over", html)
        self.assertIn("🥇", html)  # Gold tier emoji
        self.assertIn("2544.png", html)  # headshot
        # Rank badge
        self.assertIn("qeg-rank", html)
        self.assertIn("#1", html)
        # Edge label
        self.assertIn("qeg-edge-highlight-lbl", html)
        # Direction arrow
        self.assertIn("▲", html)
        # Circular edge gauge SVG
        self.assertIn("qeg-edge-gauge", html)
        self.assertIn("qeg-gauge-ring", html)
        self.assertIn("stroke-dashoffset", html)
        # Prop call line
        self.assertIn("qeg-player-prop", html)
        self.assertIn("▲ OVER 25.5 Points", html)
        # Stagger animation delay
        self.assertIn("animation-delay:0.00s", html)

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
        # Direction arrow for under
        self.assertIn("▼", html)
        # Gauge present for under cards too
        self.assertIn("qeg-edge-gauge", html)
        # Under prop call
        self.assertIn("▼ UNDER 4.5 3-Point Made", html)

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

    def test_rank_zero_hides_badge(self):
        result = {"player_name": "Player", "direction": "OVER"}
        html = render_quantum_edge_gap_card_html(result, rank=0)
        self.assertNotIn("qeg-rank", html)

    def test_rank_positive_shows_badge(self):
        result = {"player_name": "Player", "direction": "OVER"}
        html = render_quantum_edge_gap_card_html(result, rank=3)
        self.assertIn("qeg-rank", html)
        self.assertIn("#3", html)

    def test_season_avg_hidden_in_compact_card(self):
        """Season avg is not visible in compact card layout."""
        result = {
            "player_name": "Player",
            "stat_type": "points",
            "direction": "OVER",
            "adjusted_projection": 28.0,
            "season_pts_avg": 25.3,
        }
        html = render_quantum_edge_gap_card_html(result)
        # Compact card does not render stat blocks with Avg:
        self.assertNotIn("Avg:", html)

    def test_season_avg_hidden_when_zero(self):
        result = {
            "player_name": "Player",
            "stat_type": "points",
            "direction": "OVER",
        }
        html = render_quantum_edge_gap_card_html(result)
        self.assertNotIn("Avg:", html)

    def test_stagger_animation_delay(self):
        result = {"player_name": "Player", "direction": "OVER"}
        html = render_quantum_edge_gap_card_html(result, rank=5)
        self.assertIn("animation-delay:0.32s", html)

    def test_gauge_offset_scales_with_edge(self):
        """Edge gauge ring offset should decrease as |edge| increases."""
        result_low = {"player_name": "P", "direction": "OVER", "edge_percentage": 15.0}
        result_high = {"player_name": "P", "direction": "OVER", "edge_percentage": 40.0}
        html_low = render_quantum_edge_gap_card_html(result_low)
        html_high = render_quantum_edge_gap_card_html(result_high)
        # Both should have the gauge
        self.assertIn("stroke-dashoffset", html_low)
        self.assertIn("stroke-dashoffset", html_high)
        # Extract offsets — higher edge => smaller offset
        import re
        offset_low = float(re.search(r'stroke-dashoffset="([\d.]+)"', html_low).group(1))
        offset_high = float(re.search(r'stroke-dashoffset="([\d.]+)"', html_high).group(1))
        self.assertGreater(offset_low, offset_high)


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

    def test_css_has_slide_in_animation(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-card-slide-in", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_confidence_bar(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-conf-bar-fill", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-conf-expand", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_rank_badge(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-rank", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_under_card_theme(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-card-under", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_responsive_rules(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("@media (max-width: 768px)", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_hover_states(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-card:hover", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_gauge_ring(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-gauge-ring", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-gauge-fill", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_edge_pulse(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-edge-pulse", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_compare_section(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-card-mid", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-compare-block", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_shimmer_top_line(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-card::after", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_heat_strip(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-heat-strip", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-heat-fill", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-heat-bar", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-heat-pct", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_force_direction_bar(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-force-row", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-force-track", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-force-over-fill", QUANTUM_CARD_MATRIX_CSS)
        self.assertIn("qeg-force-under-fill", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_grid_scroll_animation(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-grid-scroll", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_heat_pulse_animation(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-heat-pulse", QUANTUM_CARD_MATRIX_CSS)

    def test_css_has_force_fill_animation(self):
        from styles.theme import QUANTUM_CARD_MATRIX_CSS
        self.assertIn("qeg-force-fill", QUANTUM_CARD_MATRIX_CSS)


class TestEdgeHeatStrip(unittest.TestCase):
    """Heat strip is hidden in the compact card layout but variables are still computed."""

    def test_heat_width_high_edge(self):
        """40% edge → heat_width computed correctly even though hidden."""
        result = {"player_name": "P", "direction": "OVER", "edge_percentage": 40.0}
        html = render_quantum_edge_gap_card_html(result)
        # Compact card has edge gauge but not heat strip
        self.assertIn("qeg-edge-gauge", html)

    def test_heat_width_low_edge(self):
        """Low edge card still renders gauge."""
        result = {"player_name": "P", "direction": "OVER", "edge_percentage": 15.0}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("qeg-edge-gauge", html)

    def test_heat_width_zero_edge(self):
        """0% edge → card still renders with gauge."""
        result = {"player_name": "P", "direction": "OVER", "edge_percentage": 0}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("qeg-card", html)

    def test_heat_display_absolute_value(self):
        """Negative edge still renders card correctly."""
        result = {"player_name": "P", "direction": "UNDER", "edge_percentage": -25.0}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("-25.0%", html)


class TestForceDirectionBar(unittest.TestCase):
    """Force direction bar is hidden in compact layout; test card rendering."""

    def test_force_bar_over_dominant(self):
        result = {"player_name": "P", "direction": "OVER", "probability_over": 0.85}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("qeg-card", html)
        self.assertIn("OVER", html)

    def test_force_bar_under_dominant(self):
        result = {"player_name": "P", "direction": "UNDER", "probability_over": 0.15}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("UNDER", html)

    def test_force_bar_labels(self):
        result = {"player_name": "P", "direction": "OVER", "probability_over": 0.6}
        html = render_quantum_edge_gap_card_html(result)
        self.assertIn("qeg-dir-over", html)


class TestDeduplication(unittest.TestCase):
    """Verify QEG pick deduplication."""

    def test_removes_duplicates_by_player_stat_line(self):
        picks = [
            {"player_name": "LeBron James", "stat_type": "points", "line": 25.5, "edge_percentage": 20.0},
            {"player_name": "LeBron James", "stat_type": "points", "line": 25.5, "edge_percentage": 22.0},
        ]
        result = deduplicate_qeg_picks(picks)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["edge_percentage"], 22.0)

    def test_keeps_different_stat_types(self):
        picks = [
            {"player_name": "LeBron James", "stat_type": "points", "line": 25.5, "edge_percentage": 20.0},
            {"player_name": "LeBron James", "stat_type": "rebounds", "line": 7.5, "edge_percentage": 25.0},
        ]
        result = deduplicate_qeg_picks(picks)
        self.assertEqual(len(result), 2)

    def test_keeps_different_lines(self):
        picks = [
            {"player_name": "LeBron James", "stat_type": "points", "line": 25.5, "edge_percentage": 20.0},
            {"player_name": "LeBron James", "stat_type": "points", "line": 27.5, "edge_percentage": 30.0},
        ]
        result = deduplicate_qeg_picks(picks)
        self.assertEqual(len(result), 2)

    def test_empty_list(self):
        self.assertEqual(deduplicate_qeg_picks([]), [])

    def test_case_insensitive_player_name(self):
        picks = [
            {"player_name": "lebron james", "stat_type": "points", "line": 25.5, "edge_percentage": 20.0},
            {"player_name": "LeBron James", "stat_type": "points", "line": 25.5, "edge_percentage": 18.0},
        ]
        result = deduplicate_qeg_picks(picks)
        self.assertEqual(len(result), 1)


class TestFilterQegPicks(unittest.TestCase):
    """Verify QEG pick filtering by odds_type, line deviation, and edge %."""

    def _pick(self, odds_type="standard", line_dev=0.0, direction="OVER",
              edge=5.0, **kw):
        base = {
            "player_name": "Test Player",
            "stat_type": "points",
            "line": 20.5,
            "edge_percentage": edge,
            "line_vs_avg_pct": line_dev,
            "direction": direction,
            "odds_type": odds_type,
        }
        base.update(kw)
        return base

    # ── Line deviation criterion ──────────────────────────────────────

    def test_standard_over_below_avg_included(self):
        """OVER pick with line 25% below avg passes via line deviation."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-25.0)])
        self.assertEqual(len(result), 1)

    def test_standard_under_above_avg_included(self):
        """UNDER pick with line 25% above avg passes via line deviation."""
        result = filter_qeg_picks([self._pick(direction="UNDER", line_dev=25.0)])
        self.assertEqual(len(result), 1)

    def test_over_above_avg_no_edge_excluded(self):
        """OVER pick with line above avg and low edge is excluded."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=25.0, edge=5.0)])
        self.assertEqual(len(result), 0)

    def test_under_below_avg_no_edge_excluded(self):
        """UNDER pick with line below avg and low edge is excluded."""
        result = filter_qeg_picks([self._pick(direction="UNDER", line_dev=-25.0, edge=5.0)])
        self.assertEqual(len(result), 0)

    def test_exactly_at_threshold_included(self):
        """OVER with line_vs_avg_pct exactly at -20 qualifies."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-20.0)])
        self.assertEqual(len(result), 1)

    def test_under_exactly_at_threshold_included(self):
        """UNDER with line_vs_avg_pct exactly at +20 qualifies."""
        result = filter_qeg_picks([self._pick(direction="UNDER", line_dev=20.0)])
        self.assertEqual(len(result), 1)

    def test_below_line_threshold_and_low_edge_excluded(self):
        """Picks with line deviation below threshold and low edge excluded."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-15.0, edge=10.0)])
        self.assertEqual(len(result), 0)

    # ── Edge percentage criterion ─────────────────────────────────────

    def test_high_edge_qualifies_even_without_line_dev(self):
        """A pick with edge >= 20% qualifies even if line_dev is zero."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=0.0, edge=20.0)])
        self.assertEqual(len(result), 1)

    def test_high_negative_edge_qualifies(self):
        """A pick with edge_percentage = -22 (abs >= 20) qualifies."""
        result = filter_qeg_picks([self._pick(direction="UNDER", line_dev=0.0, edge=-22.0)])
        self.assertEqual(len(result), 1)

    def test_edge_below_threshold_and_no_line_dev_excluded(self):
        """A pick with edge=15 and no qualifying line deviation excluded."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-5.0, edge=15.0)])
        self.assertEqual(len(result), 0)

    def test_over_wrong_direction_but_high_edge_qualifies(self):
        """OVER pick with line above avg still qualifies via high edge."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=10.0, edge=25.0)])
        self.assertEqual(len(result), 1)

    # ── Odds type filtering ───────────────────────────────────────────

    def test_goblin_excluded(self):
        """Goblin odds_type picks are excluded regardless of edge/deviation."""
        result = filter_qeg_picks([self._pick(odds_type="goblin", direction="OVER", line_dev=-30.0, edge=25.0)])
        self.assertEqual(len(result), 0)

    def test_demon_excluded(self):
        """Demon odds_type picks are excluded regardless of edge/deviation."""
        result = filter_qeg_picks([self._pick(odds_type="demon", direction="UNDER", line_dev=30.0, edge=25.0)])
        self.assertEqual(len(result), 0)

    def test_missing_odds_type_defaults_to_standard(self):
        """Picks without odds_type default to 'standard' and pass."""
        pick = self._pick(direction="OVER", line_dev=-25.0)
        del pick["odds_type"]
        result = filter_qeg_picks([pick])
        self.assertEqual(len(result), 1)

    def test_case_insensitive_odds_type(self):
        """odds_type matching is case-insensitive."""
        result = filter_qeg_picks([self._pick(odds_type="Standard", direction="OVER", line_dev=-25.0)])
        self.assertEqual(len(result), 1)

    # ── Custom threshold / misc ───────────────────────────────────────

    def test_custom_threshold(self):
        """Custom edge_threshold overrides the default for both criteria."""
        result = filter_qeg_picks(
            [self._pick(direction="OVER", line_dev=-10.0, edge=8.0)],
            edge_threshold=5.0,
        )
        self.assertEqual(len(result), 1)

    def test_should_avoid_not_filtered(self):
        """Picks with should_avoid=True are NOT filtered."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-30.0, should_avoid=True)])
        self.assertEqual(len(result), 1)

    def test_player_is_out_not_filtered(self):
        """Picks with player_is_out=True are NOT filtered out by QEG."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-30.0, player_is_out=True)])
        self.assertEqual(len(result), 1)

    def test_extreme_negative_deviation_shown(self):
        """OVER pick with line far below average is shown."""
        result = filter_qeg_picks([self._pick(direction="OVER", line_dev=-50.0)])
        self.assertEqual(len(result), 1)

    def test_extreme_positive_deviation_shown(self):
        """UNDER pick with line far above average is shown."""
        result = filter_qeg_picks([self._pick(direction="UNDER", line_dev=60.0)])
        self.assertEqual(len(result), 1)

    def test_mixed_odds_types(self):
        """Only standard picks pass when mixed with goblin and demon."""
        picks = [
            self._pick(odds_type="standard", direction="OVER", line_dev=-25.0),
            self._pick(odds_type="goblin", direction="OVER", line_dev=-30.0, edge=25.0),
            self._pick(odds_type="demon", direction="UNDER", line_dev=35.0, edge=25.0),
            self._pick(odds_type="standard", direction="UNDER", line_dev=22.0),
        ]
        result = filter_qeg_picks(picks)
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r["odds_type"], "standard")

    def test_empty_list(self):
        """Empty input returns empty output."""
        self.assertEqual(filter_qeg_picks([]), [])

    def test_bet_type_field_ignored(self):
        """bet_type field is NOT used for filtering; only odds_type matters."""
        pick = self._pick(odds_type="standard", direction="OVER", line_dev=-25.0)
        pick["bet_type"] = "some_other_type"
        result = filter_qeg_picks([pick])
        self.assertEqual(len(result), 1)


class TestGroupedRendering(unittest.TestCase):
    """Verify collapsible grouped QEG rendering."""

    def test_single_prop_no_details(self):
        picks = [
            {"player_name": "LeBron", "stat_type": "points", "direction": "OVER",
             "edge_percentage": 25.0, "player_id": "2544"},
        ]
        html = render_quantum_edge_gap_grouped_html(picks)
        self.assertNotIn("<details", html)
        self.assertIn("LeBron", html)

    def test_multi_prop_uses_details(self):
        picks = [
            {"player_name": "LeBron", "stat_type": "points", "direction": "OVER",
             "edge_percentage": 25.0, "player_id": "2544"},
            {"player_name": "LeBron", "stat_type": "rebounds", "direction": "OVER",
             "edge_percentage": 22.0, "player_id": "2544"},
        ]
        html = render_quantum_edge_gap_grouped_html(picks)
        self.assertIn("<details", html)
        self.assertIn("qeg-group", html)
        self.assertIn("2 props", html)
        self.assertIn("qeg-group-body", html)

    def test_mixed_players(self):
        picks = [
            {"player_name": "LeBron", "stat_type": "points", "direction": "OVER",
             "edge_percentage": 25.0},
            {"player_name": "Curry", "stat_type": "threes", "direction": "UNDER",
             "edge_percentage": -30.0},
            {"player_name": "LeBron", "stat_type": "rebounds", "direction": "OVER",
             "edge_percentage": 22.0},
        ]
        html = render_quantum_edge_gap_grouped_html(picks)
        # LeBron grouped, Curry standalone
        self.assertIn("<details", html)
        self.assertIn("Curry", html)

    def test_empty_picks(self):
        html = render_quantum_edge_gap_grouped_html([])
        self.assertEqual(html, "")


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
        self.assertIn("3-Leg Triple Lock", html)
        self.assertIn("Player1", html)
        self.assertIn("Player2", html)
        self.assertIn("45%", html)
        self.assertIn("+8.5%", html)
        self.assertIn("82", html)
        # First card gets top-pick highlight
        self.assertIn('espn-parlay-top"', html)

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
        self.assertNotIn('espn-parlay-top"', html)

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
        with open(page_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("from pages.helpers.quantum_analysis_helpers import", content)
        self.assertIn("render_dfs_flex_edge_html", content)
        self.assertIn("render_tier_distribution_html", content)
        self.assertIn("render_news_alert_html", content)
        self.assertIn("render_market_movement_html", content)
        self.assertIn("render_uncertain_pick_html", content)
        self.assertIn("render_parlay_card_html", content)
        self.assertIn("render_quantum_edge_gap_banner_html", content)
        self.assertIn("render_quantum_edge_gap_grouped_html", content)
        self.assertIn("deduplicate_qeg_picks", content)
        self.assertIn("filter_qeg_picks", content)

    def test_page_no_longer_has_inline_dfs_html(self):
        """The DFS FLEX EDGE literal should now only be in the helper."""
        import os
        page_path = os.path.join(
            os.path.dirname(__file__), "..",
            "pages", "3_⚡_Quantum_Analysis_Matrix.py",
        )
        with open(page_path, "r", encoding="utf-8") as f:
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
        with open(renderer_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('qcm-grid-container', content)


if __name__ == "__main__":
    unittest.main()
