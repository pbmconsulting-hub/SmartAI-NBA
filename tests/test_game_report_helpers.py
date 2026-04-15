# ============================================================
# FILE: tests/test_game_report_helpers.py
# PURPOSE: Tests for pages/helpers/game_report_helpers.py
# ============================================================

import pytest

from pages.helpers.game_report_helpers import (
    get_matchup_card_html,
    get_summary_dashboard_html,
    get_h2h_bars_html,
    get_parlay_card_html,
    get_builder_prop_card_html,
    get_narrative_card_html,
    ESPN_NBA,
    NBA_LOGO_FALLBACK,
)


# ── get_matchup_card_html ────────────────────────────────────

class TestGetMatchupCardHtml:
    def test_returns_string(self):
        result = get_matchup_card_html("BOS", "LAL")
        assert isinstance(result, str)

    def test_contains_team_logos(self):
        result = get_matchup_card_html("BOS", "LAL")
        assert f"{ESPN_NBA}/bos.png" in result
        assert f"{ESPN_NBA}/lal.png" in result

    def test_contains_team_abbreviations(self):
        result = get_matchup_card_html("BOS", "LAL")
        assert "BOS" in result
        assert "LAL" in result

    def test_contains_at_divider(self):
        result = get_matchup_card_html("BOS", "LAL")
        assert ">@<" in result

    def test_contains_records_when_provided(self):
        result = get_matchup_card_html("BOS", "LAL", away_record="42-18", home_record="38-22")
        assert "42-18" in result
        assert "38-22" in result

    def test_no_records_when_empty(self):
        result = get_matchup_card_html("BOS", "LAL", away_record="", home_record="")
        # Just verify it doesn't crash
        assert "BOS" in result

    def test_props_badges_shown(self):
        result = get_matchup_card_html("BOS", "LAL", n_props=12, n_high_conf=5)
        assert "12 props" in result
        assert "5 high-conf" in result

    def test_no_props_message(self):
        result = get_matchup_card_html("BOS", "LAL", n_props=0)
        assert "No props analyzed yet" in result

    def test_escapes_html_in_teams(self):
        result = get_matchup_card_html("<script>", "LAL")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_fallback_url_present(self):
        result = get_matchup_card_html("BOS", "LAL")
        assert NBA_LOGO_FALLBACK in result

    def test_team_colors_applied(self):
        # BOS primary is #007A33, LAL primary is #552583
        result = get_matchup_card_html("BOS", "LAL")
        assert "#007A33" in result
        assert "#552583" in result


# ── get_summary_dashboard_html ───────────────────────────────

class TestGetSummaryDashboardHtml:
    def test_returns_string(self):
        result = get_summary_dashboard_html(10, 5, 72.3, "LeBron · Points")
        assert isinstance(result, str)

    def test_contains_total_props(self):
        result = get_summary_dashboard_html(10, 5, 72.3, "LeBron · Points")
        assert "10" in result
        assert "Total Props" in result

    def test_contains_high_conf(self):
        result = get_summary_dashboard_html(10, 5, 72.3, "LeBron · Points")
        assert "5" in result
        assert "High-Conf Picks" in result

    def test_contains_avg_safe(self):
        result = get_summary_dashboard_html(10, 5, 72.3, "LeBron · Points")
        assert "72.3" in result

    def test_contains_best_pick(self):
        result = get_summary_dashboard_html(10, 5, 72.3, "LeBron · Points")
        assert "LeBron" in result

    def test_escapes_html_in_best_pick(self):
        result = get_summary_dashboard_html(1, 0, 50.0, "<b>XSS</b>")
        assert "<b>XSS</b>" not in result
        assert "&lt;b&gt;XSS&lt;/b&gt;" in result

    def test_uses_metrics_grid_class(self):
        result = get_summary_dashboard_html(10, 5, 72.3, "LeBron · Points")
        assert "qds-na-metrics-grid" in result

    def test_zero_props_renders(self):
        result = get_summary_dashboard_html(0, 0, 0.0, "—")
        assert "0" in result


# ── get_h2h_bars_html ────────────────────────────────────────

class TestGetH2hBarsHtml:
    def _sample_stats(self):
        return [
            ("Pace", 102.5, 98.3, 85, 115, False),
            ("ORtg", 115.2, 112.0, 105, 125, False),
            ("DRtg", 110.5, 108.2, 105, 125, True),
        ]

    def test_returns_string(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert isinstance(result, str)

    def test_contains_team_names(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert "BOS" in result
        assert "LAL" in result

    def test_contains_stat_labels(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert "Pace" in result
        assert "ORtg" in result
        assert "DRtg" in result

    def test_contains_stat_values(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert "102.5" in result
        assert "98.3" in result

    def test_animated_transitions_present(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert "cubic-bezier" in result
        assert "transition" in result

    def test_team_logos_present(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert f"{ESPN_NBA}/bos.png" in result
        assert f"{ESPN_NBA}/lal.png" in result

    def test_four_factors_header(self):
        result = get_h2h_bars_html("BOS", "LAL", self._sample_stats())
        assert "FOUR FACTORS" in result

    def test_color_coding_higher_is_better(self):
        # Pace: 102.5 vs 98.3 — BOS is better (higher)
        result = get_h2h_bars_html("BOS", "LAL", [("Pace", 102.5, 98.3, 85, 115, False)])
        assert "#00ff9d" in result

    def test_color_coding_lower_is_better(self):
        # DRtg: 110.5 vs 108.2 — LAL is better (lower)
        result = get_h2h_bars_html("BOS", "LAL", [("DRtg", 110.5, 108.2, 105, 125, True)])
        assert "#00ff9d" in result

    def test_empty_stats_list(self):
        result = get_h2h_bars_html("BOS", "LAL", [])
        assert "BOS" in result  # Still shows header

    def test_escapes_team_names(self):
        result = get_h2h_bars_html("<script>", "LAL", self._sample_stats())
        assert "<script>" not in result


# ── get_parlay_card_html ─────────────────────────────────────

class TestGetParlayCardHtml:
    def test_returns_string(self):
        result = get_parlay_card_html("Power Play (2)", ["Pick 1", "Pick 2"], "78.5", "Top 2 picks")
        assert isinstance(result, str)

    def test_contains_combo_type(self):
        result = get_parlay_card_html("Power Play (2)", ["Pick 1"], "78.5", "Top 2")
        assert "Power Play (2)" in result

    def test_contains_picks(self):
        result = get_parlay_card_html("Power Play (2)", ["LeBron OVER 24.5 Points", "Curry OVER 4.5 Threes"], "78.5", "")
        assert "LeBron OVER 24.5 Points" in result
        assert "Curry OVER 4.5 Threes" in result

    def test_contains_safe_avg(self):
        result = get_parlay_card_html("Triple Threat (3)", ["A", "B", "C"], "82.1", "")
        assert "82.1" in result
        assert "SAFE" in result

    def test_power_play_accent(self):
        result = get_parlay_card_html("Power Play (2)", ["A"], "80", "")
        assert "#ff5e00" in result

    def test_triple_threat_accent(self):
        result = get_parlay_card_html("Triple Threat (3)", ["A"], "80", "")
        assert "#ffcc00" in result

    def test_max_parlay_accent(self):
        result = get_parlay_card_html("Max Parlay (5)", ["A"], "80", "")
        assert "#00ffd5" in result

    def test_leg_numbering(self):
        result = get_parlay_card_html("Power Play (2)", ["A", "B"], "80", "")
        assert "Leg 1" in result
        assert "Leg 2" in result

    def test_strategy_shown(self):
        result = get_parlay_card_html("Power Play (2)", ["A"], "80", "Highest-confidence 2-leg.")
        assert "Highest-confidence 2-leg." in result

    def test_escapes_html(self):
        result = get_parlay_card_html("<b>", ["<script>"], "80", "")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_hover_effects_present(self):
        result = get_parlay_card_html("Power Play (2)", ["A"], "80", "")
        assert "onmouseenter" in result
        assert "onmouseleave" in result


# ── get_builder_prop_card_html ───────────────────────────────

class TestGetBuilderPropCardHtml:
    def _sample_card(self, **overrides):
        defaults = dict(
            player_name="LeBron James",
            team="LAL",
            stat_type="points",
            direction="OVER",
            prop_line=24.5,
            projected=27.3,
            over_prob=0.682,
            confidence=78.5,
            minutes=36,
        )
        defaults.update(overrides)
        return get_builder_prop_card_html(**defaults)

    def test_returns_string(self):
        result = self._sample_card()
        assert isinstance(result, str)

    def test_contains_player_name(self):
        assert "LeBron James" in self._sample_card()

    def test_contains_team(self):
        assert "LAL" in self._sample_card()

    def test_contains_stat_type(self):
        assert "POINTS" in self._sample_card()

    def test_contains_direction_over(self):
        result = self._sample_card(direction="OVER")
        assert "OVER" in result
        assert "📈" in result

    def test_contains_direction_under(self):
        result = self._sample_card(direction="UNDER", over_prob=0.3)
        assert "UNDER" in result
        assert "📉" in result

    def test_contains_prop_line(self):
        assert "24.5" in self._sample_card()

    def test_contains_projected(self):
        assert "27.3" in self._sample_card()

    def test_confidence_bar_present(self):
        result = self._sample_card()
        assert "qds-na-conf-bar" in result

    def test_metrics_grid_present(self):
        result = self._sample_card()
        assert "qds-na-metrics-grid" in result

    def test_safe_score_display(self):
        # confidence=78.5, SAFE score = 78.5/10 = 7.85, rendered as 7.8 (one decimal)
        result = self._sample_card(confidence=78.5)
        assert "7.8" in result

    def test_platinum_tier(self):
        result = self._sample_card(confidence=90)
        assert "QUANTUM PICK" in result
        assert "💎" in result

    def test_gold_tier(self):
        result = self._sample_card(confidence=75)
        assert "STRONG PICK" in result

    def test_silver_tier(self):
        result = self._sample_card(confidence=60)
        assert "SAFE PICK" in result

    def test_bronze_tier(self):
        result = self._sample_card(confidence=40)
        assert "PICK" in result

    def test_card_class(self):
        assert "qds-na-card" in self._sample_card()

    def test_escapes_player_name(self):
        result = self._sample_card(player_name="<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_minutes_displayed(self):
        result = self._sample_card(minutes=36)
        assert "36" in result

    def test_probability_displayed(self):
        result = self._sample_card(over_prob=0.682)
        assert "68.2" in result


# ── get_narrative_card_html ──────────────────────────────────

class TestGetNarrativeCardHtml:
    def test_returns_string(self):
        result = get_narrative_card_html("BOS", "LAL")
        assert isinstance(result, str)

    def test_contains_team_logos(self):
        result = get_narrative_card_html("BOS", "LAL")
        assert f"{ESPN_NBA}/bos.png" in result
        assert f"{ESPN_NBA}/lal.png" in result

    def test_contains_team_colors_in_borders(self):
        result = get_narrative_card_html("BOS", "LAL")
        # BOS primary: #007A33, LAL primary: #552583
        assert "#552583" in result  # LAL home = border-left
        assert "#007A33" in result  # BOS away = border-right

    def test_watermark_logos_present(self):
        result = get_narrative_card_html("BOS", "LAL")
        assert "opacity:0.06" in result  # watermark opacity

    def test_at_symbol_in_header(self):
        result = get_narrative_card_html("BOS", "LAL")
        assert ">@<" in result

    def test_escapes_html_in_teams(self):
        result = get_narrative_card_html("<script>", "LAL")
        assert "<script>" not in result

    def test_fallback_for_logos(self):
        result = get_narrative_card_html("BOS", "LAL")
        assert NBA_LOGO_FALLBACK in result
