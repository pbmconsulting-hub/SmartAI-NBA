"""
tests/test_nba_api_endpoints.py
------------------------------------
Tests for API-Basketball client endpoint structure:
  1. Base URL correctness (v1.basketball.api-sports.io, v2.nba.api-sports.io)
  2. Injury endpoint uses /injuries
  3. 403 status code handling (credit exhaustion)
  4. API key management endpoints (status)
  5. NBA endpoints (teams, games, players, standings, teams/statistics, players/statistics)
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

_CS_SRC = pathlib.Path(__file__).parent.parent / "data" / "nba_api_client.py"


# ── Section 1: Base URL correctness ──────────────────────────────────────────

class TestBaseURL(unittest.TestCase):
    """Verify the API-Basketball base URL uses v1.basketball.api-sports.io."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_base_url_has_api_sports_domain(self):
        """_BASE_URL must use v1.basketball.api-sports.io."""
        self.assertIn(
            'https://v1.basketball.api-sports.io',
            self.src,
            "_BASE_URL must be https://v1.basketball.api-sports.io",
        )

    def test_players_base_url_has_v2_nba_domain(self):
        """_PLAYERS_BASE_URL must use v2.nba.api-sports.io."""
        self.assertIn(
            'https://v2.nba.api-sports.io',
            self.src,
            "_PLAYERS_BASE_URL must be https://v2.nba.api-sports.io",
        )

    def test_base_url_not_old_domain(self):
        """_BASE_URL must NOT use an old or deprecated domain."""
        for line in self.src.splitlines():
            if line.strip().startswith("_BASE_URL"):
                self.assertNotIn(
                    'clearsportsapi.com',
                    line,
                    "_BASE_URL must not use old or deprecated domain",
                )


# ── Section 2: Injury endpoint path ──────────────────────────────────────────

class TestInjuryEndpointPath(unittest.TestCase):
    """Verify get_injury_report uses /injuries (API-Basketball convention)."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_injury_endpoint_uses_injuries(self):
        """get_injury_report must call /injuries."""
        idx = self.src.find("def get_injury_report(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("/injuries", snippet,
                       "get_injury_report must use /injuries endpoint")

    def test_injury_endpoint_not_old_nba_injury_stats_path(self):
        """get_injury_report must NOT use old /nba/injury-stats path."""
        idx = self.src.find("def get_injury_report(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertNotIn("/nba/injury-stats", snippet,
                         "get_injury_report must not use old /nba/injury-stats path")


# ── Section 3: 403 status code handling ──────────────────────────────────────

class TestApiNba403Handling(unittest.TestCase):
    """Verify that _request_with_retry handles HTTP 403 (credit exhaustion)."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_403_status_code_handled(self):
        """_request_with_retry should check for 403 status."""
        self.assertIn("status_code == 403", self.src,
                       "ApiNba must handle 403 status code")

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

    def test_get_api_key_info_exists(self):
        """get_api_key_info function must exist."""
        self.assertIn("def get_api_key_info(", self.src)

    def test_get_api_key_info_url(self):
        """get_api_key_info must call /status (API-Sports status endpoint)."""
        idx = self.src.find("def get_api_key_info(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/status", snippet)

    def test_get_api_key_usage_exists(self):
        """get_api_key_usage function must exist."""
        self.assertIn("def get_api_key_usage(", self.src)

    def test_get_api_key_usage_url(self):
        """get_api_key_usage must call /status (API-Sports status endpoint)."""
        idx = self.src.find("def get_api_key_usage(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("/status", snippet)

    def test_get_api_key_usage_has_limit_param(self):
        """get_api_key_usage must accept limit parameter."""
        idx = self.src.find("def get_api_key_usage(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("limit", snippet)

    def test_get_api_key_usage_has_offset_param(self):
        """get_api_key_usage must accept offset parameter."""
        idx = self.src.find("def get_api_key_usage(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("offset", snippet)

    def test_get_api_key_stats_exists(self):
        """get_api_key_stats function must exist."""
        self.assertIn("def get_api_key_stats(", self.src)

    def test_get_api_key_stats_url(self):
        """get_api_key_stats must call /status (API-Sports status endpoint)."""
        idx = self.src.find("def get_api_key_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("/status", snippet)

    def test_get_api_key_stats_has_date_params(self):
        """get_api_key_stats must accept start_date and end_date parameters."""
        idx = self.src.find("def get_api_key_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('start_date', snippet)
        self.assertIn('end_date', snippet)

    def test_api_key_functions_no_apikey_in_params(self):
        """API key management functions must not put apiKey in query params."""
        for func_name in ("get_api_key_info", "get_api_key_usage", "get_api_key_stats"):
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

    # -- get_teams --

    def test_get_teams_exists(self):
        """get_teams function must exist."""
        self.assertIn("def get_teams(", self.src)

    def test_get_teams_url(self):
        """get_teams must call /teams."""
        idx = self.src.find("def get_teams(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/teams", snippet)

    # -- get_games --

    def test_get_games_exists(self):
        """get_games function must exist."""
        self.assertIn("def get_games(", self.src)

    def test_get_games_url(self):
        """get_games must call /games via v2 NBA API."""
        idx = self.src.find("def get_games(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("/games", snippet)
        self.assertIn("_PLAYERS_BASE_URL", snippet,
                       "get_games must use _PLAYERS_BASE_URL (v2 NBA API)")

    def test_get_games_has_params(self):
        """get_games must accept season, date, team, id, live, and h2h parameters."""
        idx = self.src.find("def get_games(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertIn('"season"', snippet)
        self.assertIn('"date"', snippet)
        self.assertIn('"team"', snippet)
        self.assertIn('"id"', snippet)
        self.assertIn('"live"', snippet)
        self.assertIn('"h2h"', snippet)

    # -- get_players --

    def test_get_players_exists(self):
        """get_players function must exist."""
        self.assertIn("def get_players(", self.src)

    def test_get_players_url(self):
        """get_players must call /players via v2 NBA API."""
        idx = self.src.find("def get_players(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1200]
        self.assertIn("/players", snippet)
        self.assertIn("_PLAYERS_BASE_URL", snippet,
                       "get_players must use _PLAYERS_BASE_URL (v2 NBA API)")

    def test_get_players_has_all_v2_params(self):
        """get_players must wire all v2 NBA API query parameters."""
        idx = self.src.find("def get_players(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1800]
        for param in ('"id"', '"name"', '"team"', '"season"', '"country"', '"search"'):
            self.assertIn(param, snippet,
                          f"get_players must wire the {param} query parameter")

    def test_get_players_id_param_uses_player_id_arg(self):
        """get_players must map player_id argument to 'id' query param."""
        idx = self.src.find("def get_players(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1200]
        self.assertIn("player_id", snippet,
                       "get_players must accept player_id argument")

    # -- get_injury_report team_id param --

    def test_get_injury_report_has_team_param(self):
        """get_injury_report must pass team parameter."""
        idx = self.src.find("def get_injury_report(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"team"', snippet)

    def test_core_nba_functions_no_apikey_in_params(self):
        """Core NBA endpoint functions must not put apiKey in query params."""
        for func_name in ("get_teams", "get_games", "get_players"):
            idx = self.src.find(f"def {func_name}(")
            self.assertGreater(idx, 0, f"{func_name} not found")
            snippet = self.src[idx:idx + 800]
            self.assertNotIn('"apiKey"', snippet,
                             f"{func_name} must not include apiKey in params")


class TestNewNBAEndpoints(unittest.TestCase):
    """Verify new NBA endpoint functions exist and use correct paths."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    # -- get_team_by_id --

    def test_get_team_by_id_exists(self):
        """get_team_by_id function must exist."""
        self.assertIn("def get_team_by_id(", self.src)

    def test_get_team_by_id_url(self):
        """get_team_by_id must call /teams."""
        idx = self.src.find("def get_team_by_id(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/teams", snippet)

    # -- get_game_odds --

    def test_get_game_odds_exists(self):
        """get_game_odds function must exist."""
        self.assertIn("def get_game_odds(", self.src)

    def test_get_game_odds_url(self):
        """get_game_odds must call /odds."""
        idx = self.src.find("def get_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/odds", snippet)

    def test_get_game_odds_has_game_param(self):
        """get_game_odds must pass game parameter."""
        idx = self.src.find("def get_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"game"', snippet)

    # -- get_nba_team_stats --

    def test_get_nba_team_stats_exists(self):
        """get_nba_team_stats function must exist."""
        self.assertIn("def get_nba_team_stats(", self.src)

    def test_get_nba_team_stats_url(self):
        """get_nba_team_stats must call /teams/statistics."""
        idx = self.src.find("def get_nba_team_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/teams/statistics", snippet)

    def test_get_nba_team_stats_has_params(self):
        """get_nba_team_stats must accept team id and season parameters."""
        idx = self.src.find("def get_nba_team_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"id"', snippet)
        self.assertIn('"season"', snippet)

    # -- get_nba_player_stats --

    def test_get_nba_player_stats_exists(self):
        """get_nba_player_stats function must exist."""
        self.assertIn("def get_nba_player_stats(", self.src)

    def test_get_nba_player_stats_url(self):
        """get_nba_player_stats must call /players/statistics."""
        idx = self.src.find("def get_nba_player_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        has_player_stats = "/players/statistics" in snippet
        self.assertTrue(has_player_stats,
                        "get_nba_player_stats must use /players/statistics")

    def test_get_nba_player_stats_has_params(self):
        """get_nba_player_stats must accept player id and game parameters."""
        idx = self.src.find("def get_nba_player_stats(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1200]
        self.assertIn('"id"', snippet)
        self.assertIn('"game"', snippet)

    # -- get_predictions --

    def test_get_predictions_exists(self):
        """get_predictions function must exist."""
        self.assertIn("def get_predictions(", self.src)

    def test_get_predictions_url(self):
        """get_predictions must call /predictions."""
        idx = self.src.find("def get_predictions(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/predictions", snippet)

    def test_get_predictions_has_game_param(self):
        """get_predictions must pass game parameter."""
        idx = self.src.find("def get_predictions(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn('"game"', snippet)

    def test_new_nba_functions_no_apikey_in_params(self):
        """New NBA endpoint functions must not put apiKey in query params."""
        for func_name in (
            "get_team_by_id", "get_game_odds", "get_nba_team_stats",
            "get_nba_player_stats", "get_predictions",
        ):
            idx = self.src.find(f"def {func_name}(")
            self.assertGreater(idx, 0, f"{func_name} not found")
            snippet = self.src[idx:idx + 800]
            self.assertNotIn('"apiKey"', snippet,
                             f"{func_name} must not include apiKey in params")


# ── Section 6: Runtime tests — new functions with mocked API ──────────────────

class TestFetchTeamsRuntime(unittest.TestCase):
    """Runtime tests for get_teams."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_teams
        mock_request.return_value = [
            {"id": 1, "name": "Los Angeles Lakers", "abbreviation": "LAL"},
            {"id": 2, "name": "Boston Celtics", "abbreviation": "BOS"},
        ]
        result = get_teams()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_teams
        result = get_teams()
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_handles_wrapped_response(self, mock_request, mock_key):
        from data.nba_api_client import get_teams
        mock_request.return_value = {"teams": [{"id": 1, "name": "Lakers"}]}
        result = get_teams()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestFetchGamesRuntime(unittest.TestCase):
    """Runtime tests for get_games."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_games
        mock_request.return_value = [{"game_id": "g1", "home_team": "LAL", "away_team": "BOS"}]
        result = get_games(season=2024, date="2024-12-25", team_id=123)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_games
        result = get_games()
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_handles_wrapped_response(self, mock_request, mock_key):
        from data.nba_api_client import get_games
        mock_request.return_value = {"games": [{"game_id": "g1"}]}
        result = get_games()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestFetchPlayersRuntime(unittest.TestCase):
    """Runtime tests for get_players."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_players
        mock_request.return_value = [
            {"id": 10, "name": "LeBron James", "team_id": 1},
        ]
        result = get_players(team_id=1)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_players
        result = get_players()
        self.assertEqual(result, [])

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_handles_wrapped_response(self, mock_request, mock_key):
        from data.nba_api_client import get_players
        mock_request.return_value = {"players": [{"id": 10, "name": "LeBron James"}]}
        result = get_players()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_player_id_param_sent_as_id(self, mock_request, mock_key):
        """player_id argument must be sent as 'id' query param."""
        from data.nba_api_client import get_players, _PLAYERS_BASE_URL, ENDPOINT_PLAYERS
        mock_request.return_value = {"response": [{"id": 265, "firstname": "LeBron", "lastname": "James"}]}
        get_players(player_id=265)
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        params = call_args[1].get("params") if call_args[1] else (call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertEqual(url, f"{_PLAYERS_BASE_URL}{ENDPOINT_PLAYERS}")
        self.assertEqual(params.get("id"), 265)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_search_param_wired(self, mock_request, mock_key):
        """search argument must be sent as 'search' query param."""
        from data.nba_api_client import get_players
        mock_request.return_value = {"response": []}
        get_players(search="Jame")
        call_args = mock_request.call_args
        params = call_args[1].get("params") if call_args[1] else (call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertEqual(params.get("search"), "Jame")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_name_param_wired(self, mock_request, mock_key):
        """name argument must be sent as 'name' query param."""
        from data.nba_api_client import get_players
        mock_request.return_value = {"response": []}
        get_players(name="James")
        call_args = mock_request.call_args
        params = call_args[1].get("params") if call_args[1] else (call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertEqual(params.get("name"), "James")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_country_param_wired(self, mock_request, mock_key):
        """country argument must be sent as 'country' query param."""
        from data.nba_api_client import get_players
        mock_request.return_value = {"response": []}
        get_players(country="USA")
        call_args = mock_request.call_args
        params = call_args[1].get("params") if call_args[1] else (call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertEqual(params.get("country"), "USA")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_season_param_integer(self, mock_request, mock_key):
        """season argument must be sent as integer."""
        from data.nba_api_client import get_players
        mock_request.return_value = {"response": []}
        get_players(season=2024)
        call_args = mock_request.call_args
        params = call_args[1].get("params") if call_args[1] else (call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertEqual(params.get("season"), 2024)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_player_id_skips_default_season(self, mock_request, mock_key):
        """When player_id is given, season should NOT be sent by default."""
        from data.nba_api_client import get_players
        mock_request.return_value = {"response": [{"id": 265}]}
        get_players(player_id=265)
        call_args = mock_request.call_args
        params = call_args[1].get("params") if call_args[1] else (call_args[0][1] if len(call_args[0]) > 1 else {})
        self.assertNotIn("season", params,
                         "player_id lookup should not include default season (IDs are unique across seasons)")


class TestApiKeyInfoRuntime(unittest.TestCase):
    """Runtime tests for get_api_key_info."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_dict_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_api_key_info
        # API-Sports /status response format
        mock_request.return_value = {
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
        result = get_api_key_info()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["credits_remaining"], 85)
        self.assertEqual(result["credits_total"], 100)
        self.assertTrue(result["is_active"])
        self.assertEqual(result["email"], "user@example.com")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_api_key_info
        result = get_api_key_info()
        self.assertEqual(result, {})


class TestApiKeyUsageRuntime(unittest.TestCase):
    """Runtime tests for get_api_key_usage."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_api_key_usage
        # API-Sports /status response format
        mock_request.return_value = {
            "response": {
                "requests": {"current": 15, "limit_day": 100},
            }
        }
        result = get_api_key_usage(limit=10, offset=0)
        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_api_key_usage
        result = get_api_key_usage()
        self.assertEqual(result, [])


class TestApiKeyStatsRuntime(unittest.TestCase):
    """Runtime tests for get_api_key_stats."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_dict_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_api_key_stats
        # API-Sports /status response format
        mock_request.return_value = {
            "response": {
                "account": {"email": "user@example.com"},
                "subscription": {"plan": "Free"},
                "requests": {"current": 15, "limit_day": 100},
            }
        }
        result = get_api_key_stats(
            start_date="2025-12-01T00:00:00Z",
            end_date="2025-12-25T23:59:59Z",
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["current"], 15)
        self.assertEqual(result["limit_day"], 100)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_api_key_stats
        result = get_api_key_stats()
        self.assertEqual(result, {})


class TestTeamByIdRuntime(unittest.TestCase):
    """Runtime tests for get_team_by_id."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_dict_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_team_by_id
        mock_request.return_value = {"id": 123, "name": "Los Angeles Lakers", "abbreviation": "LAL"}
        result = get_team_by_id(123)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["abbreviation"], "LAL")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_team_by_id
        result = get_team_by_id(999)
        self.assertEqual(result, {})


class TestGameOddsRuntime(unittest.TestCase):
    """Runtime tests for get_game_odds."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_game_odds
        mock_request.return_value = [{"game_id": "g1", "spread": -3.5}]
        result = get_game_odds(game_id="g1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_game_odds
        result = get_game_odds()
        self.assertEqual(result, [])


class TestNbaTeamStatsRuntime(unittest.TestCase):
    """Runtime tests for get_nba_team_stats."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_nba_team_stats
        mock_request.return_value = [{"team_id": 1, "wins": 30, "losses": 15}]
        result = get_nba_team_stats(team_id=1, season=2024)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_nba_team_stats
        result = get_nba_team_stats()
        self.assertEqual(result, [])


class TestNbaPlayerStatsRuntime(unittest.TestCase):
    """Runtime tests for get_nba_player_stats."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_nba_player_stats
        mock_request.return_value = [{"player_id": 10, "pts": 28.5}]
        result = get_nba_player_stats(player_id=10)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_nba_player_stats
        result = get_nba_player_stats()
        self.assertEqual(result, [])


class TestPredictionsRuntime(unittest.TestCase):
    """Runtime tests for get_predictions."""

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_predictions
        mock_request.return_value = [{"game_id": "g1", "predicted_winner": "LAL", "confidence": 0.72}]
        result = get_predictions(game_id="g1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 0.72)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_predictions
        result = get_predictions()
        self.assertEqual(result, [])


# ── Section 7: Authentication structure ───────────────────────────────────────

class TestApiSportsAuthentication(unittest.TestCase):
    """Verify x-apisports-key header is used for authentication."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_apisports_key_in_headers(self):
        """_request_with_retry must use x-apisports-key header."""
        self.assertIn('"x-apisports-key"', self.src,
                       "Must use x-apisports-key header for authentication")

    def test_no_bearer_token(self):
        """_request_with_retry must not use Bearer token (old auth)."""
        self.assertNotIn('f"Bearer {api_key}"', self.src,
                         "Must not use old Bearer token authentication")


# ── Section 8: get_standings and get_news endpoint validation ─────────────────

class TestStandingsEndpoint(unittest.TestCase):
    """Verify get_standings uses the correct endpoint."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_get_standings_exists(self):
        """get_standings function must exist."""
        self.assertIn("def get_standings(", self.src)

    def test_get_standings_url(self):
        """get_standings must call /standings."""
        idx = self.src.find("def get_standings(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertTrue(
            "/standings" in snippet or "ENDPOINT_STANDINGS" in snippet,
            "get_standings must use /standings or ENDPOINT_STANDINGS",
        )

    def test_get_standings_uses_endpoint_constant(self):
        """get_standings should reference ENDPOINT_STANDINGS."""
        idx = self.src.find("def get_standings(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("ENDPOINT_STANDINGS", snippet)


class TestStandingsRuntime(unittest.TestCase):
    """Runtime tests for get_standings."""

    def tearDown(self):
        """Clear standings cache entries to avoid polluting other tests."""
        from data.nba_api_client import _API_CACHE
        keys_to_remove = [k for k in _API_CACHE if "/standings" in k]
        for k in keys_to_remove:
            del _API_CACHE[k]

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_standings, _API_CACHE
        # Remove only the standings cache key (not the entire cache)
        keys_to_remove = [k for k in _API_CACHE if "/standings" in k]
        for k in keys_to_remove:
            del _API_CACHE[k]

        mock_request.return_value = {
            "response": [[
                {"team": {"name": "Boston Celtics", "abbreviation": "BOS"},
                 "games": {"win": {"total": 50}, "lose": {"total": 12}},
                 "group": {"name": "Eastern Conference"}},
            ]]
        }
        result = get_standings()
        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_standings, _API_CACHE
        keys_to_remove = [k for k in _API_CACHE if "/standings" in k]
        for k in keys_to_remove:
            del _API_CACHE[k]

        result = get_standings()
        self.assertEqual(result, [])


class TestNewsEndpoint(unittest.TestCase):
    """Verify get_news uses the correct endpoint."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_get_news_exists(self):
        """get_news function must exist."""
        self.assertIn("def get_news(", self.src)

    def test_get_news_url(self):
        """get_news must call /news."""
        idx = self.src.find("def get_news(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1000]
        self.assertTrue(
            "/news" in snippet or "ENDPOINT_NEWS" in snippet,
            "get_news must use /news or ENDPOINT_NEWS",
        )

    def test_get_news_uses_endpoint_constant(self):
        """get_news should reference ENDPOINT_NEWS."""
        idx = self.src.find("def get_news(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1000]
        self.assertIn("ENDPOINT_NEWS", snippet)

    def test_get_news_has_limit_param(self):
        """get_news must accept limit parameter."""
        idx = self.src.find("def get_news(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 300]
        self.assertIn("limit", snippet)


class TestNewsRuntime(unittest.TestCase):
    """Runtime tests for get_news."""

    def tearDown(self):
        """Clear news cache entries to avoid polluting other tests."""
        from data.nba_api_client import _API_CACHE
        keys_to_remove = [k for k in _API_CACHE if "/news" in k]
        for k in keys_to_remove:
            del _API_CACHE[k]

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.nba_api_client import get_news
        mock_request.return_value = [
            {"title": "LeBron rests", "body": "Load management", "playerName": "LeBron James",
             "teamAbbreviation": "LAL", "publishedAt": "2026-03-24T10:00:00Z",
             "category": "injury", "impact": "high"},
        ]
        result = get_news(limit=5)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "LeBron rests")

    @patch("data.nba_api_client._resolve_api_key", return_value="test-key")
    @patch("data.nba_api_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.nba_api_client import get_news
        result = get_news()
        self.assertEqual(result, [])


# ── Section 9: ENDPOINT_* constants are all covered ──────────────────────────

class TestAllEndpointConstantsCovered(unittest.TestCase):
    """Verify every ENDPOINT_* constant in the API client maps to a get function."""

    def setUp(self):
        self.src = _CS_SRC.read_text(encoding="utf-8")

    def test_every_endpoint_has_a_get_function(self):
        """Each ENDPOINT_* constant must be referenced by a get_* function body."""
        import re
        endpoint_pattern = re.compile(r'^(ENDPOINT_\w+)\s*=\s*["\'](.+?)["\']', re.MULTILINE)
        endpoints = endpoint_pattern.findall(self.src)
        self.assertGreater(len(endpoints), 0, "No ENDPOINT_* constants found")

        for const_name, path in endpoints:
            # The constant name must appear in at least one function body
            # (not counting the definition line itself)
            uses = [
                line.strip() for line in self.src.splitlines()
                if const_name in line and not line.strip().startswith(f"{const_name} =")
                and not line.strip().startswith("#")
            ]
            self.assertGreater(
                len(uses), 0,
                f"{const_name} ({path}) is defined but never used in any function",
            )

    def test_verify_script_covers_all_api_sports_endpoints(self):
        """The verify script must test every API-Basketball endpoint path."""
        verify_path = pathlib.Path(__file__).parent.parent / "scripts" / "verify_api_endpoints.py"
        verify_src = verify_path.read_text(encoding="utf-8")

        import re
        endpoint_pattern = re.compile(r'^(ENDPOINT_\w+)\s*=\s*["\'](.+?)["\']', re.MULTILINE)
        endpoints = endpoint_pattern.findall(self.src)

        missing = []
        for const_name, path in endpoints:
            # Verify the path appears in the verify script
            if path not in verify_src:
                missing.append(f"{const_name} ({path})")

        self.assertEqual(
            missing, [],
            f"Verify script missing these API-Basketball endpoints: {missing}",
        )


class TestAllOddsEndpointConstantsCovered(unittest.TestCase):
    """Verify every ENDPOINT_* constant in odds_client.py maps to a get function."""

    def setUp(self):
        oa_path = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"
        self.src = oa_path.read_text(encoding="utf-8")

    def test_every_odds_endpoint_has_a_function(self):
        """Each ENDPOINT_* constant in odds_client must be referenced in a function."""
        import re
        endpoint_pattern = re.compile(r'^(ENDPOINT_\w+)\s*=', re.MULTILINE)
        endpoints = endpoint_pattern.findall(self.src)
        self.assertGreater(len(endpoints), 0, "No ENDPOINT_* constants found in odds_client")

        for const_name in endpoints:
            uses = [
                line.strip() for line in self.src.splitlines()
                if const_name in line and not line.strip().startswith(f"{const_name} =")
                and not line.strip().startswith("#")
            ]
            self.assertGreater(
                len(uses), 0,
                f"{const_name} is defined but never used in odds_client.py",
            )


# ── Section 10: Fallback endpoint URL validation ─────────────────────────────

class TestNbaStatsBackupEndpoints(unittest.TestCase):
    """Verify the nba_stats_backup fallback uses correct stats.nba.com URLs."""

    def setUp(self):
        fb_path = pathlib.Path(__file__).parent.parent / "data" / "nba_stats_backup.py"
        self.src = fb_path.read_text(encoding="utf-8")

    def test_base_url_is_stats_nba_com(self):
        """_NBA_STATS_BASE must be https://stats.nba.com/stats."""
        self.assertIn("https://stats.nba.com/stats", self.src)

    def test_leaguedashteamstats_endpoint(self):
        """Module must call leaguedashteamstats for team stats."""
        self.assertIn("leaguedashteamstats", self.src)

    def test_leaguedashplayerstats_endpoint(self):
        """Module must call leaguedashplayerstats for player stats."""
        self.assertIn("leaguedashplayerstats", self.src)

    def test_commonallplayers_endpoint(self):
        """Module must call commonallplayers for player lists."""
        self.assertIn("commonallplayers", self.src)

    def test_required_headers_present(self):
        """Fallback must include x-nba-stats-origin and x-nba-stats-token headers."""
        self.assertIn("x-nba-stats-origin", self.src)
        self.assertIn("x-nba-stats-token", self.src)


class TestRosterEngineCdnEndpoints(unittest.TestCase):
    """Verify roster_engine CDN injury fallback URLs."""

    def setUp(self):
        re_path = pathlib.Path(__file__).parent.parent / "data" / "roster_engine.py"
        self.src = re_path.read_text(encoding="utf-8")

    def test_cdn_injuries_url(self):
        """RosterEngine must try cdn.nba.com injuries.json."""
        self.assertIn("cdn.nba.com/static/json/staticData/injuries.json", self.src)

    def test_cdn_headline_injuries_url(self):
        """RosterEngine must try cdn.nba.com headlineinjuries.json."""
        self.assertIn("cdn.nba.com/static/json/staticData/headlineinjuries.json", self.src)

    def test_stats_playerindex_fallback(self):
        """RosterEngine must have stats.nba.com playerindex as tertiary fallback."""
        self.assertIn("stats.nba.com/stats/playerindex", self.src)


if __name__ == "__main__":
    unittest.main()
