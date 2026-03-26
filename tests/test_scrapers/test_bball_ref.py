"""tests/test_scrapers/test_bball_ref.py – Tests for Basketball Reference scraper."""
import pytest
from unittest.mock import patch, MagicMock


class TestPlayerUrlSlug:
    def test_slug_generation(self):
        from engine.scrapers.basketball_ref_scraper import _player_url_slug
        slug = _player_url_slug("LeBron James")
        assert "jamesle" in slug
        assert slug.startswith("j/")

    def test_slug_single_name(self):
        from engine.scrapers.basketball_ref_scraper import _player_url_slug
        slug = _player_url_slug("Madonna")
        assert slug == ""

    def test_slug_three_names(self):
        from engine.scrapers.basketball_ref_scraper import _player_url_slug
        slug = _player_url_slug("Karl Anthony Towns")
        assert "/" in slug


class TestFetchWithMock:
    def test_get_player_game_log_no_deps(self):
        """Should return empty list when deps unavailable."""
        import engine.scrapers.basketball_ref_scraper as mod
        original = mod._DEPS_AVAILABLE
        mod._DEPS_AVAILABLE = False
        try:
            result = mod.get_player_game_log("LeBron James", "2024")
            assert result == []
        finally:
            mod._DEPS_AVAILABLE = original

    def test_get_player_season_stats_no_deps(self):
        import engine.scrapers.basketball_ref_scraper as mod
        original = mod._DEPS_AVAILABLE
        mod._DEPS_AVAILABLE = False
        try:
            result = mod.get_player_season_stats("LeBron James", "2024")
            assert result == {}
        finally:
            mod._DEPS_AVAILABLE = original

    def test_get_team_standings_no_deps(self):
        import engine.scrapers.basketball_ref_scraper as mod
        original = mod._DEPS_AVAILABLE
        mod._DEPS_AVAILABLE = False
        try:
            result = mod.get_team_standings("2024")
            assert result == []
        finally:
            mod._DEPS_AVAILABLE = original
