# ============================================================
# FILE: tests/test_accuracy_optimizer.py
# PURPOSE: Tests for the Accuracy Optimizer upgrade:
#          - Hard-Typed Stat Mapping
#          - Stale Data Kill Switch
#          - Source Triangulation / Validation Engine
#          - Async Buffer (TCPConnector)
#          - Engine Validation Gate
# ============================================================

import datetime
import sys
import os

# Ensure project root is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# SECTION 1: Hard-Typed Stat Mapping
# ============================================================

class TestHardStatMapping:
    """Tests for data/platform_mappings.py HARD_STAT_MAP & hard_normalize_stat_type."""

    def test_points_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("points", "pts", "PTS", "Points", "POINTS", "point"):
            assert hard_normalize_stat_type(variant) == "points", f"Failed for '{variant}'"

    def test_rebounds_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("rebounds", "rebs", "reb", "Rebounds", "REB", "REBOUNDS"):
            assert hard_normalize_stat_type(variant) == "rebounds", f"Failed for '{variant}'"

    def test_assists_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("assists", "asts", "ast", "Assists", "AST", "ASSISTS"):
            assert hard_normalize_stat_type(variant) == "assists", f"Failed for '{variant}'"

    def test_threes_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("threes", "3pm", "3PM", "Threes", "THREES"):
            assert hard_normalize_stat_type(variant) == "threes", f"Failed for '{variant}'"

    def test_steals_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("steals", "stl", "STL", "Steals", "STEALS"):
            assert hard_normalize_stat_type(variant) == "steals", f"Failed for '{variant}'"

    def test_blocks_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("blocks", "blk", "BLK", "Blocks", "BLOCKS"):
            assert hard_normalize_stat_type(variant) == "blocks", f"Failed for '{variant}'"

    def test_turnovers_variants(self):
        from data.platform_mappings import hard_normalize_stat_type
        for variant in ("turnovers", "tov", "TOV", "Turnovers", "TURNOVERS"):
            assert hard_normalize_stat_type(variant) == "turnovers", f"Failed for '{variant}'"

    def test_unknown_returns_none(self):
        from data.platform_mappings import hard_normalize_stat_type
        assert hard_normalize_stat_type("unknown_stat_xyz") is None

    def test_empty_returns_none(self):
        from data.platform_mappings import hard_normalize_stat_type
        assert hard_normalize_stat_type("") is None
        assert hard_normalize_stat_type(None) is None

    def test_combo_stats_pass_through(self):
        from data.platform_mappings import hard_normalize_stat_type
        assert hard_normalize_stat_type("points_rebounds") == "points_rebounds"
        assert hard_normalize_stat_type("points_assists") == "points_assists"
        assert hard_normalize_stat_type("points_rebounds_assists") == "points_rebounds_assists"


class TestNormalizeStatTypeHardMapIntegration:
    """Verify normalize_stat_type falls through to HARD_STAT_MAP."""

    def test_pts_without_platform(self):
        from data.platform_mappings import normalize_stat_type
        assert normalize_stat_type("pts") == "points"

    def test_PTS_without_platform(self):
        from data.platform_mappings import normalize_stat_type
        assert normalize_stat_type("PTS") == "points"

    def test_reb_without_platform(self):
        from data.platform_mappings import normalize_stat_type
        assert normalize_stat_type("reb") == "rebounds"

    def test_ast_without_platform(self):
        from data.platform_mappings import normalize_stat_type
        assert normalize_stat_type("ast") == "assists"

    def test_existing_platform_map_still_works(self):
        from data.platform_mappings import normalize_stat_type
        assert normalize_stat_type("Pts+Rebs", "PrizePicks") == "points_rebounds"
        assert normalize_stat_type("3PM", "DraftKings") == "threes"


# ============================================================
# SECTION 2: Stale Data Kill Switch
# ============================================================

class TestStaleDataKillSwitch:
    """Tests for data/platform_fetcher.py discard_stale_props()."""

    def _make_prop(self, player="Player A", stat="points", line=24.5,
                   fetched_at=None, last_updated=None):
        p = {
            "player_name": player, "stat_type": stat, "line": line,
            "platform": "PrizePicks", "over_odds": -110, "under_odds": -110,
        }
        if fetched_at is not None:
            p["fetched_at"] = fetched_at
        if last_updated is not None:
            p["last_updated"] = last_updated
        return p

    def test_fresh_props_kept(self):
        from data.platform_fetcher import discard_stale_props
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        ts = now.isoformat()
        props = [self._make_prop(fetched_at=ts)]
        fresh, summary = discard_stale_props(props)
        assert len(fresh) == 1
        assert summary["stale"] == 0

    def test_stale_props_discarded(self):
        from data.platform_fetcher import discard_stale_props
        old_time = (
            datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            - datetime.timedelta(seconds=300)
        )
        ts = old_time.isoformat()
        props = [self._make_prop(fetched_at=ts)]
        fresh, summary = discard_stale_props(props)
        assert len(fresh) == 0
        assert summary["stale"] == 1

    def test_no_timestamp_kept(self):
        """Props without timestamps are assumed fresh."""
        from data.platform_fetcher import discard_stale_props
        props = [self._make_prop()]
        fresh, summary = discard_stale_props(props)
        assert len(fresh) == 1
        assert summary["stale"] == 0

    def test_last_updated_preferred_over_fetched_at(self):
        """last_updated takes precedence over fetched_at."""
        from data.platform_fetcher import discard_stale_props
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        fresh_ts = now.isoformat()
        stale_ts = (now - datetime.timedelta(seconds=300)).isoformat()
        # last_updated is stale, fetched_at is fresh → should be discarded
        props = [self._make_prop(fetched_at=fresh_ts, last_updated=stale_ts)]
        fresh, summary = discard_stale_props(props)
        assert len(fresh) == 0
        assert summary["stale"] == 1

    def test_custom_threshold(self):
        from data.platform_fetcher import discard_stale_props
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        ts = (now - datetime.timedelta(seconds=60)).isoformat()
        props = [self._make_prop(fetched_at=ts)]
        # 60s old with 120s threshold → fresh
        fresh, summary = discard_stale_props(props, max_age_seconds=120)
        assert len(fresh) == 1
        # 60s old with 30s threshold → stale
        fresh2, summary2 = discard_stale_props(props, max_age_seconds=30)
        assert len(fresh2) == 0
        assert summary2["stale"] == 1

    def test_empty_input(self):
        from data.platform_fetcher import discard_stale_props
        fresh, summary = discard_stale_props([])
        assert fresh == []
        assert summary["input"] == 0

    def test_invalid_timestamp_kept(self):
        """Props with unparseable timestamps are kept (defensive)."""
        from data.platform_fetcher import discard_stale_props
        props = [self._make_prop(fetched_at="not-a-date")]
        fresh, summary = discard_stale_props(props)
        assert len(fresh) == 1


# ============================================================
# SECTION 3: Source Triangulation / Validation Engine
# ============================================================

class TestValidationEngine:
    """Tests for data/platform_fetcher.py validate_cross_platform_lines()."""

    def _make_prop(self, player="Player A", stat="points", line=24.5,
                   platform="PrizePicks"):
        return {
            "player_name": player, "stat_type": stat, "line": line,
            "platform": platform, "over_odds": -110, "under_odds": -110,
        }

    def test_matching_lines_validated(self):
        from data.platform_fetcher import validate_cross_platform_lines
        props = [
            self._make_prop(line=24.5, platform="PrizePicks"),
            self._make_prop(line=25.0, platform="Underdog"),  # diff=0.5 < 2.0
        ]
        validated, summary = validate_cross_platform_lines(props)
        assert len(validated) == 2
        assert all(p["validation_status"] == "VALIDATED" for p in validated)
        assert summary["validated"] == 2

    def test_divergent_lines_flagged(self):
        from data.platform_fetcher import validate_cross_platform_lines
        props = [
            self._make_prop(line=24.5, platform="PrizePicks"),
            self._make_prop(line=28.0, platform="Underdog"),  # diff=3.5 > 2.0
        ]
        validated, summary = validate_cross_platform_lines(props)
        assert all(p["validation_status"] == "REVIEW" for p in validated)
        assert summary["review_divergence"] == 2
        assert "divergence" in validated[0].get("validation_note", "").lower()

    def test_single_source_flagged(self):
        from data.platform_fetcher import validate_cross_platform_lines
        props = [self._make_prop(line=24.5, platform="PrizePicks")]
        validated, summary = validate_cross_platform_lines(props)
        assert validated[0]["validation_status"] == "REVIEW"
        assert summary["review_single_source"] == 1

    def test_custom_threshold(self):
        from data.platform_fetcher import validate_cross_platform_lines
        props = [
            self._make_prop(line=24.5, platform="PrizePicks"),
            self._make_prop(line=25.5, platform="Underdog"),  # diff=1.0
        ]
        # threshold=0.5 → flag
        validated, summary = validate_cross_platform_lines(props, divergence_threshold=0.5)
        assert all(p["validation_status"] == "REVIEW" for p in validated)
        # threshold=2.0 → validated
        validated2, summary2 = validate_cross_platform_lines(props, divergence_threshold=2.0)
        assert all(p["validation_status"] == "VALIDATED" for p in validated2)

    def test_empty_input(self):
        from data.platform_fetcher import validate_cross_platform_lines
        validated, summary = validate_cross_platform_lines([])
        assert validated == []
        assert summary["input"] == 0

    def test_two_non_pp_ud_platforms_validated(self):
        """Two platforms (neither PP nor UD) should still be VALIDATED."""
        from data.platform_fetcher import validate_cross_platform_lines
        props = [
            self._make_prop(line=24.5, platform="DraftKings"),
            self._make_prop(line=25.0, platform="FanDuel"),
        ]
        validated, summary = validate_cross_platform_lines(props)
        assert all(p["validation_status"] == "VALIDATED" for p in validated)

    def test_mixed_players_independent(self):
        """Different players validated independently."""
        from data.platform_fetcher import validate_cross_platform_lines
        props = [
            self._make_prop(player="A", line=24.5, platform="PrizePicks"),
            self._make_prop(player="A", line=25.0, platform="Underdog"),
            self._make_prop(player="B", line=30.0, platform="PrizePicks"),  # single source
        ]
        validated, summary = validate_cross_platform_lines(props)
        # Player A: both platforms → VALIDATED (diff=0.5 < 2.0)
        a_props = [p for p in validated if p["player_name"] == "A"]
        assert all(p["validation_status"] == "VALIDATED" for p in a_props)
        # Player B: single source → REVIEW
        b_props = [p for p in validated if p["player_name"] == "B"]
        assert all(p["validation_status"] == "REVIEW" for p in b_props)


# ============================================================
# SECTION 4: Async Buffer (TCPConnector)
# ============================================================

class TestAsyncBuffer:
    """Verify the async fetcher uses TCPConnector(limit_per_host=10)."""

    def test_connector_in_source(self):
        """The source code must contain TCPConnector(limit_per_host=10)."""
        import inspect
        from data import platform_fetcher
        source = inspect.getsource(platform_fetcher.fetch_all_platforms_async)
        assert "TCPConnector" in source
        assert "limit_per_host=10" in source


# ============================================================
# SECTION 5: Engine Validation Gate
# ============================================================

class TestEngineValidationGate:
    """Tests for engine/__init__.py accept_validated_props()."""

    def test_validated_accepted(self):
        from engine import accept_validated_props
        props = [
            {"player_name": "A", "validation_status": "VALIDATED"},
            {"player_name": "B", "validation_status": "VALIDATED"},
        ]
        accepted, rejected = accept_validated_props(props)
        assert len(accepted) == 2
        assert rejected == 0

    def test_review_rejected(self):
        from engine import accept_validated_props
        props = [
            {"player_name": "A", "validation_status": "VALIDATED"},
            {"player_name": "B", "validation_status": "REVIEW"},
        ]
        accepted, rejected = accept_validated_props(props)
        assert len(accepted) == 1
        assert accepted[0]["player_name"] == "A"
        assert rejected == 1

    def test_no_status_passes_through(self):
        """Props without validation_status are backward-compatible."""
        from engine import accept_validated_props
        props = [{"player_name": "A", "line": 24.5}]
        accepted, rejected = accept_validated_props(props)
        assert len(accepted) == 1
        assert rejected == 0

    def test_empty_input(self):
        from engine import accept_validated_props
        accepted, rejected = accept_validated_props([])
        assert accepted == []
        assert rejected == 0

    def test_all_review(self):
        from engine import accept_validated_props
        props = [
            {"player_name": "A", "validation_status": "REVIEW"},
            {"player_name": "B", "validation_status": "REVIEW"},
        ]
        accepted, rejected = accept_validated_props(props)
        assert len(accepted) == 0
        assert rejected == 2


# ============================================================
# SECTION 6: smart_filter_props Integration
# ============================================================

class TestSmartFilterIntegration:
    """Verify new steps are integrated into smart_filter_props pipeline."""

    def _make_prop(self, player="Player A", stat="points", line=24.5,
                   platform="PrizePicks"):
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        return {
            "player_name": player, "stat_type": stat, "line": line,
            "platform": platform, "over_odds": -110, "under_odds": -110,
            "fetched_at": now.isoformat(),
        }

    def test_summary_includes_new_keys(self):
        from data.platform_fetcher import smart_filter_props
        props = [self._make_prop()]
        _, summary = smart_filter_props(props)
        assert "after_stale_check" in summary
        assert "after_validation" in summary
        assert "validation_detail" in summary

    def test_stale_props_removed_in_pipeline(self):
        from data.platform_fetcher import smart_filter_props
        old_time = (
            datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            - datetime.timedelta(seconds=300)
        )
        props = [
            {
                "player_name": "Player A", "stat_type": "points", "line": 24.5,
                "platform": "PrizePicks", "over_odds": -110, "under_odds": -110,
                "fetched_at": old_time.isoformat(),
            },
        ]
        filtered, summary = smart_filter_props(props)
        assert summary["after_stale_check"] == 0
        assert len(filtered) == 0
