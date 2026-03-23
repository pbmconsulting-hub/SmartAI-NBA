"""
tests/test_clearsports_endpoints.py
------------------------------------
Tests for API-NBA client endpoint structure:
  1. Base URL correctness (v2.nba.api-sports.io)
  2. Injury endpoint uses /nba/injury-stats
  3. 403 status code handling (credit exhaustion)
  4. API key management endpoints (status, api-keys/me/usage, api-keys/me/stats)
  5. NBA endpoints (teams, players, standings, teams/statistics, players/statistics)
  6. No apiKey leaking into query params for new functions
"""

import pathlib
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-mock streamlit before importing application modules
_mock_st = MagicMock()
_mock_st.session_state = {}
_mock_st.cache_data = lambda *a, **kw: (lambda f: f)
_mock_st.secrets = {}
sys.modules.setdefault("streamlit", _mock_st)
sys.modules.setdefault("streamlit.components", MagicMock())
sys.modules.setdefault("streamlit.components.v1", MagicMock())

_CS_SRC = pathlib.Path(__file__).parent.parent / "data" / "clearsports_client.py"


# ── Section 1: Base URL correctness ──────────────────────────────────────────

class TestBaseURL(unittest.TestCase):
    """Verify the API-NBA base URL uses v2.nba.api-sports.io."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_base_url_has_api_sports_domain(self):
        """_BASE_URL must use v2.nba.api-sports.io."""
        self.assertIn(
            'https://v2.nba.api-sports.io',
            self.src,
            "_BASE_URL must be https://v2.nba.api-sports.io",
        )

    def test_base_url_not_old_clearsports(self):
        """_BASE_URL must NOT use the old clearsportsapi.com domain."""
        for line in self.src.splitlines():
            if line.strip().startswith("_BASE_URL"):
                self.assertNotIn(
                    'clearsportsapi.com',
                    line,
                    "_BASE_URL must not use old clearsportsapi.com domain",
                )


# ── Section 2: Injury endpoint path ──────────────────────────────────────────

class TestInjuryEndpointPath(unittest.TestCase):
    """Verify fetch_injury_report uses /nba/injury-stats (not /nba/injuries)."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_injury_endpoint_uses_injury_stats(self):
        """fetch_injury_report must call /nba/injury-stats."""
        idx = self.src.find("def fetch_injury_report(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("/nba/injury-stats", snippet,
                       "fetch_injury_report must use /nba/injury-stats endpoint")

    def test_injury_endpoint_not_old_path(self):
        """fetch_injury_report must NOT use old /nba/injuries path."""
        idx = self.src.find("def fetch_injury_report(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertNotIn('"/nba/injuries"', snippet,
                         "fetch_injury_report must not use old /nba/injuries path")


# ── Section 3: 403 status code handling ──────────────────────────────────────

class TestClearSports403Handling(unittest.TestCase):
    """Verify that _fetch_with_retry handles HTTP 403 (credit exhaustion)."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_403_status_code_handled(self):
        """_fetch_with_retry should check for 403 status."""
        self.assertIn("status_code == 403", self.src,
                       "ClearSports must handle 403 status code")

    def test_403_returns_none_without_retry(self):
        """403 handler should return None (not continue to retry)."""
        idx = self.src.find("status_code == 403")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 200]
        self.assertIn("return None", snippet,
                       "403 should return None immediately without retry")


# ── Section 4: API Key Management endpoint functions exist ────────────────────

class TestApiKeyManagementEndpoints(unittest.TestCase):
    """Verify API key management endpoint functions exist and use correct paths."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_fetch_api_key_info_exists(self):
        """fetch_api_key_info function must exist."""
        self.assertIn("def fetch_api_key_info(", self.src)

    def test_fetch_api_key_info_url(self):
        """fetch_api_key_info must call /status (API-Sports status endpoint)."""
        idx = self.src.find("def fetch_api_key_info(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/status", snippet)

    def test_fetch_api_key_usage_exists(self):
        """fetch_api_key_usage function must exist."""
        self.assertIn("def fetch_api_key_usage(", self.src)

    def test_fetch_api_key_usage_url(self):
        """fetch_api_key_usage must call /api-keys/me/usage."""
        idx = self.src.find("def fetch_api_key_usage(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/api-keys/me/usage", snippet)

    def test_fetch_api_key_usage_has_limit_param(self):
        """fetch_api_key_usage must accept limit parameter."""
        idx = self.src.find("def fetch_api_key_usage(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"limit"', snippet)

    def test_fetch_api_key_usage_has_offset_param(self):
        """fetch_api_key_usage must accept offset parameter."""
        idx = self.src.find("def fetch_api_key_usage(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"offset"', snippet)

    def test_fetch_api_key_stats_exists(self):
        """fetch_api_key_stats function must exist."""
        self.assertIn("def fetch_api_key_stats(", self.src)

    def test_fetch_api_key_stats_url(self):
        """fetch_api_key_stats must call /api-keys/me/stats."""
        idx = self.src.find("def fetch_api_key_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/api-keys/me/stats", snippet)

    def test_fetch_api_key_stats_has_date_params(self):
        """fetch_api_key_stats must accept start_date and end_date parameters."""
        idx = self.src.find("def fetch_api_key_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"start_date"', snippet)
        self.assertIn('"end_date"', snippet)

    def test_api_key_functions_no_apikey_in_params(self):
        """API key management functions must not put apiKey in query params."""
        for func_name in ("fetch_api_key_info", "fetch_api_key_usage", "fetch_api_key_stats"):
            idx = self.src.find(f"def {func_name}(")
            self.assertGreater(idx, 0, f"{func_name} not found")
            snippet = self.src[idx:idx + 800]
            self.assertNotIn('"apiKey"', snippet,
                             f"{func_name} must not include apiKey in params")


# ── Section 5: New NBA endpoint functions ─────────────────────────────────────

class TestCoreNBAEndpoints(unittest.TestCase):
    """Verify core NBA resource endpoint functions exist and use correct paths."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    # -- fetch_teams --

    def test_fetch_teams_exists(self):
        """fetch_teams function must exist."""
        self.assertIn("def fetch_teams(", self.src)

    def test_fetch_teams_url(self):
        """fetch_teams must call /teams."""
        idx = self.src.find("def fetch_teams(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/teams", snippet)

    # -- fetch_games --

    def test_fetch_games_exists(self):
        """fetch_games function must exist."""
        self.assertIn("def fetch_games(", self.src)

    def test_fetch_games_url(self):
        """fetch_games must call /games."""
        idx = self.src.find("def fetch_games(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/games", snippet)

    def test_fetch_games_has_params(self):
        """fetch_games must accept season, date, and team_id parameters."""
        idx = self.src.find("def fetch_games(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"season"', snippet)
        self.assertIn('"date"', snippet)
        self.assertIn('"team_id"', snippet)

    # -- fetch_players --

    def test_fetch_players_exists(self):
        """fetch_players function must exist."""
        self.assertIn("def fetch_players(", self.src)

    def test_fetch_players_url(self):
        """fetch_players must call /players."""
        idx = self.src.find("def fetch_players(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/players", snippet)

    def test_fetch_players_has_team_id_param(self):
        """fetch_players must accept team_id parameter."""
        idx = self.src.find("def fetch_players(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"team_id"', snippet)

    # -- fetch_injury_report team_id param --

    def test_fetch_injury_report_has_team_id_param(self):
        """fetch_injury_report must accept team_id parameter."""
        idx = self.src.find("def fetch_injury_report(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"team_id"', snippet)

    def test_core_nba_functions_no_apikey_in_params(self):
        """Core NBA endpoint functions must not put apiKey in query params."""
        for func_name in ("fetch_teams", "fetch_games", "fetch_players"):
            idx = self.src.find(f"def {func_name}(")
            self.assertGreater(idx, 0, f"{func_name} not found")
            snippet = self.src[idx:idx + 800]
            self.assertNotIn('"apiKey"', snippet,
                             f"{func_name} must not include apiKey in params")


class TestNewNBAEndpoints(unittest.TestCase):
    """Verify new NBA endpoint functions exist and use correct paths."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    # -- fetch_team_by_id --

    def test_fetch_team_by_id_exists(self):
        """fetch_team_by_id function must exist."""
        self.assertIn("def fetch_team_by_id(", self.src)

    def test_fetch_team_by_id_url(self):
        """fetch_team_by_id must call /teams."""
        idx = self.src.find("def fetch_team_by_id(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/teams", snippet)

    # -- fetch_game_odds --

    def test_fetch_game_odds_exists(self):
        """fetch_game_odds function must exist."""
        self.assertIn("def fetch_game_odds(", self.src)

    def test_fetch_game_odds_url(self):
        """fetch_game_odds must call /odds (API-Sports endpoint)."""
        idx = self.src.find("def fetch_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/odds", snippet)

    def test_fetch_game_odds_has_game_param(self):
        """fetch_game_odds must pass game parameter (API-Sports convention)."""
        idx = self.src.find("def fetch_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"game"', snippet)

    # -- fetch_nba_team_stats --

    def test_fetch_nba_team_stats_exists(self):
        """fetch_nba_team_stats function must exist."""
        self.assertIn("def fetch_nba_team_stats(", self.src)

    def test_fetch_nba_team_stats_url(self):
        """fetch_nba_team_stats must call /teams/statistics."""
        idx = self.src.find("def fetch_nba_team_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/teams/statistics", snippet)

    def test_fetch_nba_team_stats_has_params(self):
        """fetch_nba_team_stats must accept id and season parameters."""
        idx = self.src.find("def fetch_nba_team_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"id"', snippet)
        self.assertIn('"season"', snippet)

    # -- fetch_nba_player_stats --

    def test_fetch_nba_player_stats_exists(self):
        """fetch_nba_player_stats function must exist."""
        self.assertIn("def fetch_nba_player_stats(", self.src)

    def test_fetch_nba_player_stats_url(self):
        """fetch_nba_player_stats must call /players/statistics."""
        idx = self.src.find("def fetch_nba_player_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/players/statistics", snippet)

    def test_fetch_nba_player_stats_has_params(self):
        """fetch_nba_player_stats must accept id and game parameters."""
        idx = self.src.find("def fetch_nba_player_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"id"', snippet)
        self.assertIn('"game"', snippet)

    # -- fetch_predictions --

    def test_fetch_predictions_exists(self):
        """fetch_predictions function must exist."""
        self.assertIn("def fetch_predictions(", self.src)

    def test_fetch_predictions_url(self):
        """fetch_predictions must call /nba/predictions."""
        idx = self.src.find("def fetch_predictions(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/nba/predictions", snippet)

    def test_fetch_predictions_has_game_id_param(self):
        """fetch_predictions must accept game_id parameter."""
        idx = self.src.find("def fetch_predictions(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"game_id"', snippet)

    def test_new_nba_functions_no_apikey_in_params(self):
        """New NBA endpoint functions must not put apiKey in query params."""
        for func_name in (
            "fetch_team_by_id", "fetch_game_odds", "fetch_nba_team_stats",
            "fetch_nba_player_stats", "fetch_predictions",
        ):
            idx = self.src.find(f"def {func_name}(")
            self.assertGreater(idx, 0, f"{func_name} not found")
            snippet = self.src[idx:idx + 800]
            self.assertNotIn('"apiKey"', snippet,
                             f"{func_name} must not include apiKey in params")


# ── Section 6: Runtime tests — new functions with mocked API ──────────────────

class TestFetchTeamsRuntime(unittest.TestCase):
    """Runtime tests for fetch_teams."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_teams
        mock_fetch.return_value = [
            {"id": 1, "name": "Los Angeles Lakers", "abbreviation": "LAL"},
            {"id": 2, "name": "Boston Celtics", "abbreviation": "BOS"},
        ]
        result = fetch_teams()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_teams
        result = fetch_teams()
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_handles_wrapped_response(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_teams
        mock_fetch.return_value = {"teams": [{"id": 1, "name": "Lakers"}]}
        result = fetch_teams()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestFetchGamesRuntime(unittest.TestCase):
    """Runtime tests for fetch_games."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_games
        mock_fetch.return_value = [{"game_id": "g1", "home_team": "LAL", "away_team": "BOS"}]
        result = fetch_games(season=2024, date="2024-12-25", team_id=123)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_games
        result = fetch_games()
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_handles_wrapped_response(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_games
        mock_fetch.return_value = {"games": [{"game_id": "g1"}]}
        result = fetch_games()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestFetchPlayersRuntime(unittest.TestCase):
    """Runtime tests for fetch_players."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_players
        mock_fetch.return_value = [
            {"id": 10, "name": "LeBron James", "team_id": 1},
        ]
        result = fetch_players(team_id=1)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_players
        result = fetch_players()
        self.assertEqual(result, [])

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_handles_wrapped_response(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_players
        mock_fetch.return_value = {"players": [{"id": 10, "name": "LeBron James"}]}
        result = fetch_players()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestApiKeyInfoRuntime(unittest.TestCase):
    """Runtime tests for fetch_api_key_info."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_dict_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_api_key_info
        # API-Sports /status response format
        mock_fetch.return_value = {
            "response": {
                "account": {
                    "firstname": "John",
                    "lastname": "Doe",
                    "email": "user@example.com",
                },
                "subscription": {
                    "plan": "Free",
                    "end": "2026-12-31",
                },
                "requests": {
                    "current": 15,
                    "limit_day": 100,
                },
            }
        }
        result = fetch_api_key_info()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["credits_remaining"], 85)
        self.assertEqual(result["credits_total"], 100)
        self.assertTrue(result["is_active"])
        self.assertEqual(result["email"], "user@example.com")

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_api_key_info
        result = fetch_api_key_info()
        self.assertEqual(result, {})


class TestApiKeyUsageRuntime(unittest.TestCase):
    """Runtime tests for fetch_api_key_usage."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_api_key_usage
        mock_fetch.return_value = [{"endpoint": "/nba/teams", "timestamp": "2025-12-25T10:30:00Z"}]
        result = fetch_api_key_usage(limit=10, offset=0)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_api_key_usage
        result = fetch_api_key_usage()
        self.assertEqual(result, [])


class TestApiKeyStatsRuntime(unittest.TestCase):
    """Runtime tests for fetch_api_key_stats."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_dict_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_api_key_stats
        mock_fetch.return_value = {"total_calls": 15, "period": "2025-12-01 to 2025-12-25"}
        result = fetch_api_key_stats(
            start_date="2025-12-01T00:00:00Z",
            end_date="2025-12-25T23:59:59Z",
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["total_calls"], 15)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_api_key_stats
        result = fetch_api_key_stats()
        self.assertEqual(result, {})


class TestTeamByIdRuntime(unittest.TestCase):
    """Runtime tests for fetch_team_by_id."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_dict_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_team_by_id
        mock_fetch.return_value = {"id": 123, "name": "Los Angeles Lakers", "abbreviation": "LAL"}
        result = fetch_team_by_id(123)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["abbreviation"], "LAL")

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_team_by_id
        result = fetch_team_by_id(999)
        self.assertEqual(result, {})


class TestGameOddsRuntime(unittest.TestCase):
    """Runtime tests for fetch_game_odds."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_game_odds
        mock_fetch.return_value = [{"game_id": "g1", "spread": -3.5}]
        result = fetch_game_odds(game_id="g1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_game_odds
        result = fetch_game_odds()
        self.assertEqual(result, [])


class TestNbaTeamStatsRuntime(unittest.TestCase):
    """Runtime tests for fetch_nba_team_stats."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_nba_team_stats
        mock_fetch.return_value = [{"team_id": 1, "wins": 30, "losses": 15}]
        result = fetch_nba_team_stats(team_id=1, season=2024)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_nba_team_stats
        result = fetch_nba_team_stats()
        self.assertEqual(result, [])


class TestNbaPlayerStatsRuntime(unittest.TestCase):
    """Runtime tests for fetch_nba_player_stats."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_nba_player_stats
        mock_fetch.return_value = [{"player_id": 10, "pts": 28.5}]
        result = fetch_nba_player_stats(player_id=10)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_nba_player_stats
        result = fetch_nba_player_stats()
        self.assertEqual(result, [])


class TestPredictionsRuntime(unittest.TestCase):
    """Runtime tests for fetch_predictions."""

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_predictions
        mock_fetch.return_value = [{"game_id": "g1", "predicted_winner": "LAL", "confidence": 0.72}]
        result = fetch_predictions(game_id="g1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 0.72)

    @patch("data.clearsports_client._resolve_api_key", return_value="test-key")
    @patch("data.clearsports_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.clearsports_client import fetch_predictions
        result = fetch_predictions()
        self.assertEqual(result, [])


# ── Section 7: Authentication structure ───────────────────────────────────────

class TestApiSportsAuthentication(unittest.TestCase):
    """Verify x-apisports-key header is used for authentication."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_apisports_key_in_headers(self):
        """_fetch_with_retry must use x-apisports-key header."""
        self.assertIn('"x-apisports-key"', self.src,
                       "Must use x-apisports-key header for authentication")

    def test_no_bearer_token(self):
        """_fetch_with_retry must not use Bearer token (old auth)."""
        self.assertNotIn('f"Bearer {api_key}"', self.src,
                         "Must not use old Bearer token authentication")


if __name__ == "__main__":
    unittest.main()
