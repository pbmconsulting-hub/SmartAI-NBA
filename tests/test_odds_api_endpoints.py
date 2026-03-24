"""
tests/test_odds_api_endpoints.py
---------------------------------
Tests for Odds API client endpoint structure:
  1. Base URL correctness (/v4 prefix)
  2. 403 status code handling (quota exhaustion)
  3. Public get_events() function
  4. Public get_event_odds() function for any markets on a single event
  5. Existing endpoints still correct (odds, scores)
  6. API key passed via query params (Odds API pattern, not Bearer header)
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

_OA_SRC = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"


# ── Section 1: Base URL correctness ──────────────────────────────────────────

class TestOddsApiBaseURL(unittest.TestCase):
    """Verify the Odds API base URL is correct."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_base_url_v4(self):
        """_BASE_URL must be https://api.the-odds-api.com/v4."""
        self.assertIn(
            'https://api.the-odds-api.com/v4',
            self.src,
            "_BASE_URL must be https://api.the-odds-api.com/v4",
        )

    def test_sport_basketball_nba(self):
        """_SPORT must be basketball_nba."""
        self.assertIn('"basketball_nba"', self.src,
                       "_SPORT must be basketball_nba")


# ── Section 2: 403 status code handling ──────────────────────────────────────

class TestOddsApi403Handling(unittest.TestCase):
    """Verify that _fetch_with_retry handles HTTP 403 (quota exhaustion)."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_403_status_code_handled(self):
        """_fetch_with_retry should check for 403 status."""
        self.assertIn("status_code == 403", self.src,
                       "Odds API must handle 403 status code")

    def test_403_returns_none_without_retry(self):
        """403 handler should return None immediately (not continue to retry)."""
        idx = self.src.find("status_code == 403")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 200]
        self.assertIn("return None", snippet,
                       "403 should return None immediately without retry")


# ── Section 3: get_sports() and get_events() public functions ─────────────

class TestFetchSportsEndpoint(unittest.TestCase):
    """Verify get_sports() exists and uses the correct free endpoint."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_fetch_sports_exists(self):
        """get_sports function must exist as a public function."""
        self.assertIn("def get_sports(", self.src)

    def test_fetch_sports_url(self):
        """get_sports must call /sports (free, no quota cost)."""
        idx = self.src.find("def get_sports(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertIn("/sports", snippet)


class TestFetchSportsRuntime(unittest.TestCase):
    """Runtime tests for get_sports()."""

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.odds_client import get_sports
        mock_fetch.return_value = [
            {
                "key": "basketball_nba",
                "group": "Basketball",
                "title": "NBA",
                "description": "US Basketball",
                "active": True,
                "has_outrights": False,
            },
            {
                "key": "americanfootball_nfl",
                "group": "American Football",
                "title": "NFL",
                "description": "US Football",
                "active": True,
                "has_outrights": False,
            },
        ]
        result = get_sports()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        nba_sport = [s for s in result if s["key"] == "basketball_nba"]
        self.assertEqual(len(nba_sport), 1)
        self.assertTrue(nba_sport[0]["active"])

    @patch("data.odds_client._resolve_api_key", return_value=None)
    def test_returns_none_when_no_key(self, mock_key):
        from data.odds_client import get_sports
        result = get_sports()
        self.assertIsNone(result)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry", return_value=None)
    def test_returns_none_on_failure(self, mock_fetch, mock_key):
        from data.odds_client import get_sports
        result = get_sports()
        self.assertIsNone(result)


class TestFetchEventsEndpoint(unittest.TestCase):
    """Verify get_events() exists and uses the correct endpoint."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_fetch_events_exists(self):
        """get_events function must exist as a public function."""
        self.assertIn("def get_events(", self.src)

    def test_fetch_events_url(self):
        """get_events must call /sports/basketball_nba/events."""
        idx = self.src.find("def get_events(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        # It delegates to _fetch_events which uses the events URL
        self.assertIn("_fetch_events", snippet)

    def test_internal_fetch_events_url(self):
        """_fetch_events must use /sports/{_SPORT}/events URL."""
        idx = self.src.find("def _fetch_events(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("ENDPOINT_EVENTS", snippet)


class TestFetchEventsRuntime(unittest.TestCase):
    """Runtime tests for get_events()."""

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry")
    def test_returns_list_on_success(self, mock_fetch, mock_key):
        from data.odds_client import get_events
        mock_fetch.return_value = [
            {
                "id": "abc123",
                "sport_key": "basketball_nba",
                "sport_title": "NBA",
                "commence_time": "2025-02-12T03:00:00Z",
                "home_team": "Phoenix Suns",
                "away_team": "Memphis Grizzlies",
            }
        ]
        result = get_events()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["home_team"], "Phoenix Suns")

    @patch("data.odds_client._resolve_api_key", return_value=None)
    def test_returns_empty_list_when_no_key(self, mock_key):
        from data.odds_client import get_events
        result = get_events()
        self.assertEqual(result, [])

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_fetch, mock_key):
        from data.odds_client import get_events
        result = get_events()
        self.assertEqual(result, [])


# ── Section 4: get_event_odds() function ───────────────────────────────────

class TestFetchEventOddsEndpoint(unittest.TestCase):
    """Verify get_event_odds() exists and uses the correct endpoint."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_fetch_event_odds_exists(self):
        """get_event_odds function must exist."""
        self.assertIn("def get_event_odds(", self.src)

    def test_fetch_event_odds_url(self):
        """get_event_odds must call /sports/{_SPORT}/events/{event_id}/odds."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn("/events/{event_id}/odds", snippet)

    def test_fetch_event_odds_accepts_markets(self):
        """get_event_odds must accept a markets parameter."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn('"markets"', snippet)

    def test_fetch_event_odds_accepts_regions(self):
        """get_event_odds must accept a regions parameter."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn('"regions"', snippet)

    def test_fetch_event_odds_accepts_odds_format(self):
        """get_event_odds must accept an oddsFormat parameter."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn('"oddsFormat"', snippet)


class TestFetchEventOddsRuntime(unittest.TestCase):
    """Runtime tests for get_event_odds()."""

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry")
    def test_returns_dict_on_success(self, mock_fetch, mock_key):
        from data.odds_client import get_event_odds
        mock_fetch.return_value = {
            "id": "abc123",
            "sport_key": "basketball_nba",
            "home_team": "Phoenix Suns",
            "away_team": "Memphis Grizzlies",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "markets": [
                        {
                            "key": "h2h_h1",
                            "outcomes": [
                                {"name": "Memphis Grizzlies", "price": -170},
                                {"name": "Phoenix Suns", "price": 142},
                            ]
                        }
                    ]
                }
            ]
        }
        result = get_event_odds("abc123", markets="h2h_h1,player_points")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["home_team"], "Phoenix Suns")
        self.assertIn("bookmakers", result)

    @patch("data.odds_client._resolve_api_key", return_value=None)
    def test_returns_empty_dict_when_no_key(self, mock_key):
        from data.odds_client import get_event_odds
        result = get_event_odds("abc123")
        self.assertEqual(result, {})

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry", return_value=None)
    def test_returns_empty_dict_on_failure(self, mock_fetch, mock_key):
        from data.odds_client import get_event_odds
        result = get_event_odds("abc123")
        self.assertEqual(result, {})

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._fetch_with_retry")
    def test_passes_custom_markets(self, mock_fetch, mock_key):
        """Custom markets string should be passed to API params."""
        from data.odds_client import get_event_odds
        mock_fetch.return_value = {"id": "x", "bookmakers": []}
        get_event_odds("x", markets="player_points,player_rebounds", regions="us2")
        # Verify the call args include our custom markets
        call_args = mock_fetch.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params")
        if params is None and len(call_args) >= 2:
            params = call_args[0][1]
        # The params should contain our markets
        self.assertIn("player_points", str(call_args))


# ── Section 5: Existing endpoint correctness ──────────────────────────────────

class TestExistingOddsEndpoints(unittest.TestCase):
    """Verify existing endpoints are correctly structured."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_fetch_game_odds_url(self):
        """get_game_odds must call /sports/{_SPORT}/odds."""
        idx = self.src.find("def get_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn("ENDPOINT_ODDS", snippet)

    def test_fetch_game_odds_featured_markets(self):
        """get_game_odds must request h2h, spreads, and totals markets."""
        idx = self.src.find("def get_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("h2h", snippet)
        self.assertIn("spreads", snippet)
        self.assertIn("totals", snippet)

    def test_fetch_recent_scores_url(self):
        """get_recent_scores must call /sports/{_SPORT}/scores."""
        idx = self.src.find("def get_recent_scores(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("/scores", snippet)

    def test_fetch_recent_scores_has_days_from(self):
        """get_recent_scores must use daysFrom parameter."""
        idx = self.src.find("def get_recent_scores(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn('"daysFrom"', snippet)

    def test_fetch_player_props_uses_event_odds(self):
        """get_player_props must use the per-event /events/{id}/odds endpoint."""
        idx = self.src.find("def get_player_props(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn("/events/{event_id}/odds", snippet)

    def test_get_consensus_odds_exists(self):
        """get_consensus_odds function must exist."""
        self.assertIn("def get_consensus_odds(", self.src)

    def test_get_odds_api_usage_exists(self):
        """get_odds_api_usage function must exist."""
        self.assertIn("def get_odds_api_usage(", self.src)

    def test_calculate_implied_probability_exists(self):
        """calculate_implied_probability function must exist."""
        self.assertIn("def calculate_implied_probability(", self.src)


# ── Section 6: API key via query params (not Bearer header) ──────────────────

class TestOddsApiKeyInParams(unittest.TestCase):
    """Verify the Odds API uses apiKey in query params (not Bearer header)."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_apikey_in_query_params(self):
        """Odds API functions must pass apiKey in query params."""
        # get_game_odds should have "apiKey" in params
        idx = self.src.find("def get_game_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertIn('"apiKey"', snippet)

    def test_no_bearer_header_in_fetch_with_retry(self):
        """Odds API _fetch_with_retry must NOT use Bearer header
        (API key is in query params, not headers)."""
        idx = self.src.find("def _fetch_with_retry(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 800]
        self.assertNotIn("Bearer", snippet,
                         "Odds API should NOT use Bearer auth — key goes in query params")

    def test_quota_headers_captured(self):
        """Odds API must capture x-requests-remaining from response headers."""
        self.assertIn("x-requests-remaining", self.src)
        self.assertIn("x-requests-used", self.src)


# ── Section: Outcome parsing uses point for spreads/totals ────────────────────

class TestFetchGameOddsOutcomeParsing(unittest.TestCase):
    """Verify get_game_odds uses point (not price) for spreads and totals."""

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._cache_get", return_value=None)
    @patch("data.odds_client._cache_set")
    @patch("data.odds_client._fetch_with_retry")
    def test_spreads_use_point_not_price(self, mock_fetch, mock_cs, mock_cg, mock_key):
        """Spreads outcomes should map name → point (spread value), not price (juice)."""
        from data.odds_client import get_game_odds

        mock_fetch.return_value = [{
            "id": "ev1",
            "home_team": "Los Angeles Lakers",
            "away_team": "Boston Celtics",
            "bookmakers": [{
                "key": "draftkings",
                "markets": [{
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": -110, "point": -3.5},
                        {"name": "Boston Celtics", "price": -110, "point": 3.5},
                    ],
                }],
            }],
        }]

        games = get_game_odds()
        spreads = games[0]["bookmakers"][0]["markets"]["spreads"]
        self.assertAlmostEqual(spreads["Los Angeles Lakers"], -3.5)
        self.assertAlmostEqual(spreads["Boston Celtics"], 3.5)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._cache_get", return_value=None)
    @patch("data.odds_client._cache_set")
    @patch("data.odds_client._fetch_with_retry")
    def test_totals_use_point_not_price(self, mock_fetch, mock_cs, mock_cg, mock_key):
        """Totals outcomes should map name → point (total value), not price (juice)."""
        from data.odds_client import get_game_odds

        mock_fetch.return_value = [{
            "id": "ev1",
            "home_team": "Los Angeles Lakers",
            "away_team": "Boston Celtics",
            "bookmakers": [{
                "key": "fanduel",
                "markets": [{
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "price": -110, "point": 224.5},
                        {"name": "Under", "price": -110, "point": 224.5},
                    ],
                }],
            }],
        }]

        games = get_game_odds()
        totals = games[0]["bookmakers"][0]["markets"]["totals"]
        self.assertAlmostEqual(totals["Over"], 224.5)
        self.assertAlmostEqual(totals["Under"], 224.5)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._cache_get", return_value=None)
    @patch("data.odds_client._cache_set")
    @patch("data.odds_client._fetch_with_retry")
    def test_h2h_uses_price(self, mock_fetch, mock_cs, mock_cg, mock_key):
        """h2h (moneyline) outcomes should map name → price (no point field)."""
        from data.odds_client import get_game_odds

        mock_fetch.return_value = [{
            "id": "ev1",
            "home_team": "Los Angeles Lakers",
            "away_team": "Boston Celtics",
            "bookmakers": [{
                "key": "draftkings",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": -150},
                        {"name": "Boston Celtics", "price": 130},
                    ],
                }],
            }],
        }]

        games = get_game_odds()
        h2h = games[0]["bookmakers"][0]["markets"]["h2h"]
        self.assertEqual(h2h["Los Angeles Lakers"], -150)
        self.assertEqual(h2h["Boston Celtics"], 130)


class TestPlayerPropsRegion(unittest.TestCase):
    """Verify get_player_props uses the correct API region."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_player_props_uses_us_region(self):
        """get_player_props must use 'us' region for DraftKings/FanDuel coverage."""
        idx = self.src.find("def get_player_props(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2500]
        # Must contain "us" region assignment
        self.assertIn('"regions"', snippet)
        self.assertIn('"us"', snippet)
        # Must NOT use "us2" only (which lacks DK/FD player props)
        self.assertNotIn('"us2"', snippet)


if __name__ == "__main__":
    unittest.main()
