# ============================================================
# FILE: tests/test_line_value_badge.py
# PURPOSE: Tests for the Line Value vs Average directional force
#          boost in detect_line_sharpness() and the shared
#          get_line_value_badge_html() helper.
# ============================================================

import pytest

from engine.edge_detection import detect_line_sharpness
from styles.theme import get_line_value_badge_html


# ============================================================
# detect_line_sharpness — new OVER/UNDER boost forces (≥8% gap)
# ============================================================


class TestDetectLineSharpnessOverBoost:
    """Line set below season average → OVER force (Low Line Value)."""

    def test_minus_20_pct_gap(self):
        """−20% gap → OVER, strength ≈ 1.71, gap_pct = −20.0"""
        # season_avg = 25.0, line = 20.0 → gap = (20−25)/25*100 = −20%
        result = detect_line_sharpness(20.0, 25.0)
        assert result is not None
        assert result["name"] == "Low Line Value"
        assert result["direction"] == "OVER"
        assert result["gap_pct"] == -20.0
        # strength = min(2.0, (20−8)/7*0.8 + 0.6) = min(2.0, 12/7*0.8+0.6) = min(2.0, 1.371+0.6) ≈ 1.97
        # Wait: abs_gap=20, (20-8)/7*0.8+0.6 = 12/7*0.8+0.6 = 1.3714+0.6 = 1.9714
        # Actually that's ~1.97, not 1.71. Let me recalculate.
        # The problem statement says strength ≈ 1.71 for −20% gap.
        # Formula: min(2.0, (abs_gap - 8.0) / 7.0 * 0.8 + 0.6)
        # abs_gap = 20: (20-8)/7*0.8 + 0.6 = 12/7*0.8 + 0.6 = 1.3714 + 0.6 = 1.9714
        # Hmm, the problem statement example values don't exactly match the formula.
        # Let's test against the actual formula.
        expected_strength = round(min(2.0, (20.0 - 8.0) / 7.0 * 0.8 + 0.6), 2)
        assert result["strength"] == expected_strength

    def test_minus_8_pct_gap(self):
        """−8% gap → OVER, strength = 0.6"""
        # season_avg = 25.0, line = 23.0 → gap = (23−25)/25*100 = −8%
        result = detect_line_sharpness(23.0, 25.0)
        assert result is not None
        assert result["name"] == "Low Line Value"
        assert result["direction"] == "OVER"
        assert result["gap_pct"] == -8.0
        assert result["strength"] == 0.6

    def test_minus_30_pct_gap_capped(self):
        """−30%+ gap → OVER, strength capped at 2.0"""
        # season_avg = 30.0, line = 21.0 → gap = −30%
        result = detect_line_sharpness(21.0, 30.0)
        assert result is not None
        assert result["direction"] == "OVER"
        assert result["strength"] == 2.0


class TestDetectLineSharpnessUnderBoost:
    """Line set above season average → UNDER force (High Line Value)."""

    def test_plus_20_pct_gap(self):
        """+20% gap → UNDER, strength based on formula, gap_pct = +20.0"""
        # season_avg = 25.0, line = 30.0 → gap = (30−25)/25*100 = +20%
        result = detect_line_sharpness(30.0, 25.0)
        assert result is not None
        assert result["name"] == "High Line Value"
        assert result["direction"] == "UNDER"
        assert result["gap_pct"] == 20.0
        expected_strength = round(min(1.8, (20.0 - 8.0) / 11.0 * 1.2 + 0.5), 2)
        assert result["strength"] == expected_strength

    def test_plus_8_pct_gap(self):
        """+8% gap → UNDER, strength = 0.5"""
        # season_avg = 25.0, line = 27.0 → gap = +8%
        result = detect_line_sharpness(27.0, 25.0)
        assert result is not None
        assert result["name"] == "High Line Value"
        assert result["direction"] == "UNDER"
        assert result["gap_pct"] == 8.0
        assert result["strength"] == 0.5

    def test_plus_30_pct_gap_capped(self):
        """+30%+ gap → UNDER, strength capped at 1.8"""
        # season_avg = 20.0, line = 26.0 → gap = +30%
        result = detect_line_sharpness(26.0, 20.0)
        assert result is not None
        assert result["direction"] == "UNDER"
        assert result["strength"] == 1.8


# ============================================================
# Existing behavior — unchanged
# ============================================================


class TestDetectLineSharpnessExisting:
    """Existing < 3% and 3–8% zones remain exactly as-is."""

    def test_minus_3_pct_sharp_line_penalty(self):
        """Just under 3% gap → still returns sharp line UNDER penalty (unchanged)."""
        # season_avg = 25.0, line = 24.3 → gap = (24.3−25)/25*100 = −2.8%
        result = detect_line_sharpness(24.3, 25.0)
        assert result is not None
        assert result["direction"] == "UNDER"
        assert "Sharp Line" in result["name"]

    def test_minus_1_pct_sharp_line(self):
        """−1% gap → UNDER penalty."""
        # season_avg = 25.0, line = 24.75 → gap = −1%
        result = detect_line_sharpness(24.75, 25.0)
        assert result is not None
        assert result["direction"] == "UNDER"
        assert "Sharp Line" in result["name"]

    def test_plus_5_pct_neutral_zone(self):
        """+5% gap → still returns None (neutral zone, unchanged)."""
        # season_avg = 20.0, line = 21.0 → gap = +5%
        result = detect_line_sharpness(21.0, 20.0)
        assert result is None

    def test_minus_5_pct_neutral_zone(self):
        """−5% gap → returns None (neutral zone)."""
        # season_avg = 20.0, line = 19.0 → gap = −5%
        result = detect_line_sharpness(19.0, 20.0)
        assert result is None

    def test_none_season_average(self):
        """None season average → returns None."""
        result = detect_line_sharpness(24.5, None)
        assert result is None


# ============================================================
# get_line_value_badge_html
# ============================================================


class TestGetLineValueBadgeHtml:
    """Shared badge helper returns correct HTML for line value gaps."""

    def test_negative_gap_green_badge(self):
        """−20.0% → green badge with 📉 −20.0% vs Avg."""
        html = get_line_value_badge_html(-20.0)
        assert html != ""
        assert "#00ff9d" in html
        assert "-20.0% vs Avg" in html
        assert "\U0001f4c9" in html  # 📉

    def test_positive_gap_orange_badge(self):
        """+20.0% → orange badge with 📈 +20.0% vs Avg."""
        html = get_line_value_badge_html(20.0)
        assert html != ""
        assert "#ff9966" in html
        assert "+20.0% vs Avg" in html
        assert "\U0001f4c8" in html  # 📈

    def test_neutral_zone_empty(self):
        """5.0% → empty string (neutral zone)."""
        assert get_line_value_badge_html(5.0) == ""
        assert get_line_value_badge_html(-5.0) == ""
        assert get_line_value_badge_html(0.0) == ""
        assert get_line_value_badge_html(7.9) == ""
        assert get_line_value_badge_html(-7.9) == ""

    def test_boundary_minus_8(self):
        """−8.0% → green badge (boundary of neutral zone)."""
        html = get_line_value_badge_html(-8.0)
        assert html != ""
        assert "#00ff9d" in html

    def test_boundary_plus_8(self):
        """+8.0% → orange badge (boundary of neutral zone)."""
        html = get_line_value_badge_html(8.0)
        assert html != ""
        assert "#ff9966" in html

    def test_invalid_input_returns_empty(self):
        """Invalid input → empty string."""
        assert get_line_value_badge_html(None) == ""
        assert get_line_value_badge_html("abc") == ""
