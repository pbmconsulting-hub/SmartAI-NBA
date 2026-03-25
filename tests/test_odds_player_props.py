"""
tests/test_odds_player_props.py
---------------------------------
Tests for the comprehensive NBA player-props features in odds_client.py:
  1. US_BOOKMAKER_KEYS configuration constant
  2. PLAYER_PROP_MARKETS configuration constant
  3. Expanded _ODDS_API_STAT_MAP (standard + alternate markets)
  4. ENDPOINT_EVENT_MARKETS constant
  5. get_nba_events() — date-filtered event discovery
  6. get_event_markets() — per-event market/bookmaker discovery
  7. get_event_odds() — bookmaker filtering and recommended API flags
  8. get_player_props() — bookmaker filtering and market_key field
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

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

import pathlib

_OA_SRC = pathlib.Path(__file__).parent.parent / "data" / "odds_client.py"


# ── Section 1: US_BOOKMAKER_KEYS constant ─────────────────────────────────────

class TestUSBookmakerKeys(unittest.TestCase):
    """Verify the US_BOOKMAKER_KEYS constant is present and correct."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_constant_exists(self):
        """US_BOOKMAKER_KEYS must be defined in odds_client."""
        self.assertIn("US_BOOKMAKER_KEYS", self.src)

    def test_contains_all_required_keys(self):
        """US_BOOKMAKER_KEYS must contain all 11 specified US bookmaker keys."""
        from data.odds_client import US_BOOKMAKER_KEYS
        expected = {
            "betonlineag", "betmgm", "betrivers", "betus", "bovada",
            "williamhill_us", "draftkings", "fanatics", "fanduel",
            "lowvig", "mybookieag",
        }
        self.assertEqual(set(US_BOOKMAKER_KEYS), expected)

    def test_is_list(self):
        """US_BOOKMAKER_KEYS must be a list (not set/tuple)."""
        from data.odds_client import US_BOOKMAKER_KEYS
        self.assertIsInstance(US_BOOKMAKER_KEYS, list)

    def test_no_duplicates(self):
        """US_BOOKMAKER_KEYS must not contain duplicates."""
        from data.odds_client import US_BOOKMAKER_KEYS
        self.assertEqual(len(US_BOOKMAKER_KEYS), len(set(US_BOOKMAKER_KEYS)))


# ── Section 2: PLAYER_PROP_MARKETS constant ──────────────────────────────────

class TestPlayerPropMarkets(unittest.TestCase):
    """Verify the PLAYER_PROP_MARKETS constant is present and correct."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_constant_exists(self):
        """PLAYER_PROP_MARKETS must be defined in odds_client."""
        self.assertIn("PLAYER_PROP_MARKETS", self.src)

    def test_contains_standard_markets(self):
        """PLAYER_PROP_MARKETS must contain all 16 standard prop market keys."""
        from data.odds_client import PLAYER_PROP_MARKETS
        standard = [
            "player_points", "player_rebounds", "player_assists",
            "player_threes", "player_blocks", "player_steals",
            "player_blocks_steals", "player_turnovers",
            "player_points_rebounds_assists", "player_points_rebounds",
            "player_points_assists", "player_rebounds_assists",
            "player_field_goals", "player_frees_made",
            "player_frees_attempts", "player_fantasy_points",
        ]
        for mkt in standard:
            self.assertIn(mkt, PLAYER_PROP_MARKETS,
                          f"Standard market {mkt} missing from PLAYER_PROP_MARKETS")

    def test_contains_alternate_markets(self):
        """PLAYER_PROP_MARKETS must contain all 12 alternate prop market keys."""
        from data.odds_client import PLAYER_PROP_MARKETS
        alternates = [
            "player_points_alternate", "player_rebounds_alternate",
            "player_assists_alternate", "player_blocks_alternate",
            "player_steals_alternate", "player_turnovers_alternate",
            "player_threes_alternate", "player_points_assists_alternate",
            "player_points_rebounds_alternate",
            "player_rebounds_assists_alternate",
            "player_points_rebounds_assists_alternate",
            "player_fantasy_points_alternate",
        ]
        for mkt in alternates:
            self.assertIn(mkt, PLAYER_PROP_MARKETS,
                          f"Alternate market {mkt} missing from PLAYER_PROP_MARKETS")

    def test_total_count(self):
        """PLAYER_PROP_MARKETS must contain exactly 28 markets (16 standard + 12 alternate)."""
        from data.odds_client import PLAYER_PROP_MARKETS
        self.assertEqual(len(PLAYER_PROP_MARKETS), 28)

    def test_no_quarter_props(self):
        """PLAYER_PROP_MARKETS must not contain any quarter-based props."""
        from data.odds_client import PLAYER_PROP_MARKETS
        for mkt in PLAYER_PROP_MARKETS:
            self.assertNotIn("quarter", mkt.lower(),
                             f"Quarter prop {mkt} should not be in PLAYER_PROP_MARKETS")
            self.assertNotIn("_q1", mkt.lower())
            self.assertNotIn("_q2", mkt.lower())
            self.assertNotIn("_q3", mkt.lower())
            self.assertNotIn("_q4", mkt.lower())

    def test_is_list(self):
        """PLAYER_PROP_MARKETS must be a list."""
        from data.odds_client import PLAYER_PROP_MARKETS
        self.assertIsInstance(PLAYER_PROP_MARKETS, list)


# ── Section 3: Expanded _ODDS_API_STAT_MAP ───────────────────────────────────

class TestExpandedStatMap(unittest.TestCase):
    """Verify _ODDS_API_STAT_MAP covers all PLAYER_PROP_MARKETS."""

    def test_all_markets_have_stat_mapping(self):
        """Every key in PLAYER_PROP_MARKETS must exist in _ODDS_API_STAT_MAP."""
        from data.odds_client import PLAYER_PROP_MARKETS, _ODDS_API_STAT_MAP
        for mkt in PLAYER_PROP_MARKETS:
            self.assertIn(mkt, _ODDS_API_STAT_MAP,
                          f"Market {mkt} missing from _ODDS_API_STAT_MAP")

    def test_new_standard_mappings(self):
        """New standard markets must map to correct internal stat keys."""
        from data.odds_client import _ODDS_API_STAT_MAP
        self.assertEqual(_ODDS_API_STAT_MAP["player_blocks_steals"], "blocks_steals")
        self.assertEqual(_ODDS_API_STAT_MAP["player_field_goals"], "field_goals")
        self.assertEqual(_ODDS_API_STAT_MAP["player_frees_made"], "frees_made")
        self.assertEqual(_ODDS_API_STAT_MAP["player_frees_attempts"], "frees_attempts")
        self.assertEqual(_ODDS_API_STAT_MAP["player_fantasy_points"], "fantasy_points")

    def test_alternate_maps_to_same_stat(self):
        """Alternate markets must map to the same internal stat as standard."""
        from data.odds_client import _ODDS_API_STAT_MAP
        pairs = [
            ("player_points", "player_points_alternate"),
            ("player_rebounds", "player_rebounds_alternate"),
            ("player_assists", "player_assists_alternate"),
            ("player_threes", "player_threes_alternate"),
            ("player_blocks", "player_blocks_alternate"),
            ("player_steals", "player_steals_alternate"),
            ("player_turnovers", "player_turnovers_alternate"),
            ("player_fantasy_points", "player_fantasy_points_alternate"),
        ]
        for standard, alternate in pairs:
            self.assertEqual(
                _ODDS_API_STAT_MAP[standard],
                _ODDS_API_STAT_MAP[alternate],
                f"{alternate} must map to same stat as {standard}",
            )


# ── Section 4: ENDPOINT_EVENT_MARKETS constant ──────────────────────────────

class TestEndpointEventMarkets(unittest.TestCase):
    """Verify the ENDPOINT_EVENT_MARKETS constant exists."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_constant_defined(self):
        """ENDPOINT_EVENT_MARKETS must be defined."""
        self.assertIn("ENDPOINT_EVENT_MARKETS", self.src)

    def test_references_events_path(self):
        """ENDPOINT_EVENT_MARKETS must reference the events path."""
        from data.odds_client import ENDPOINT_EVENT_MARKETS
        self.assertIn("/events", ENDPOINT_EVENT_MARKETS)


# ── Section 5: get_nba_events() function ──────────────────────────────────────

class TestGetNbaEventsEndpoint(unittest.TestCase):
    """Verify get_nba_events() exists and uses the correct endpoint."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_function_exists(self):
        """get_nba_events must exist."""
        self.assertIn("def get_nba_events(", self.src)

    def test_accepts_start_datetime(self):
        """get_nba_events must accept a start_datetime parameter."""
        idx = self.src.find("def get_nba_events(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("start_datetime", snippet)

    def test_accepts_end_datetime(self):
        """get_nba_events must accept an end_datetime parameter."""
        idx = self.src.find("def get_nba_events(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("end_datetime", snippet)

    def test_uses_events_endpoint(self):
        """get_nba_events must use the ENDPOINT_EVENTS URL."""
        idx = self.src.find("def get_nba_events(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 1500]
        self.assertIn("ENDPOINT_EVENTS", snippet)


class TestGetNbaEventsRuntime(unittest.TestCase):
    """Runtime tests for get_nba_events()."""

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.odds_client import get_nba_events
        mock_request.return_value = [
            {
                "id": "evt1",
                "sport_key": "basketball_nba",
                "commence_time": "2025-03-25T02:00:00Z",
                "home_team": "Los Angeles Lakers",
                "away_team": "Boston Celtics",
            }
        ]
        result = get_nba_events(
            start_datetime="2025-03-25T00:00:00Z",
            end_datetime="2025-03-26T00:00:00Z",
        )
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["home_team"], "Los Angeles Lakers")

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_passes_date_params(self, mock_request, mock_key):
        """Date parameters should be included in the API call."""
        from data.odds_client import get_nba_events
        mock_request.return_value = []
        get_nba_events(
            start_datetime="2025-03-25T00:00:00Z",
            end_datetime="2025-03-26T00:00:00Z",
        )
        call_args = mock_request.call_args
        params = call_args[1].get("params") or call_args[0][1]
        self.assertEqual(params["commenceTimeFrom"], "2025-03-25T00:00:00Z")
        self.assertEqual(params["commenceTimeTo"], "2025-03-26T00:00:00Z")

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_omits_date_params_when_none(self, mock_request, mock_key):
        """When no date params are given, they should not appear in API call."""
        from data.odds_client import get_nba_events
        mock_request.return_value = []
        get_nba_events()
        call_args = mock_request.call_args
        params = call_args[1].get("params") or call_args[0][1]
        self.assertNotIn("commenceTimeFrom", params)
        self.assertNotIn("commenceTimeTo", params)

    @patch("data.odds_client._resolve_api_key", return_value=None)
    def test_returns_empty_list_when_no_key(self, mock_key):
        from data.odds_client import get_nba_events
        result = get_nba_events()
        self.assertEqual(result, [])

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.odds_client import get_nba_events
        result = get_nba_events()
        self.assertEqual(result, [])


# ── Section 6: get_event_markets() function ──────────────────────────────────

class TestGetEventMarketsEndpoint(unittest.TestCase):
    """Verify get_event_markets() exists and uses the correct endpoint."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_function_exists(self):
        """get_event_markets must exist."""
        self.assertIn("def get_event_markets(", self.src)

    def test_accepts_event_id(self):
        """get_event_markets must accept an event_id parameter."""
        idx = self.src.find("def get_event_markets(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 300]
        self.assertIn("event_id", snippet)

    def test_uses_event_markets_endpoint(self):
        """get_event_markets must use the ENDPOINT_EVENT_MARKETS URL."""
        idx = self.src.find("def get_event_markets(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2000]
        self.assertIn("ENDPOINT_EVENT_MARKETS", snippet)

    def test_filters_by_us_bookmakers(self):
        """get_event_markets must reference US_BOOKMAKER_KEYS for filtering."""
        idx = self.src.find("def get_event_markets(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2500]
        self.assertIn("US_BOOKMAKER_KEYS", snippet)

    def test_filters_by_prop_markets(self):
        """get_event_markets must reference PLAYER_PROP_MARKETS for filtering."""
        idx = self.src.find("def get_event_markets(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 2500]
        self.assertIn("PLAYER_PROP_MARKETS", snippet)


class TestGetEventMarketsRuntime(unittest.TestCase):
    """Runtime tests for get_event_markets()."""

    SAMPLE_EVENT_ODDS = {
        "id": "evt1",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {"key": "player_points", "outcomes": []},
                    {"key": "player_rebounds", "outcomes": []},
                    {"key": "player_assists", "outcomes": []},
                ],
            },
            {
                "key": "fanduel",
                "title": "FanDuel",
                "markets": [
                    {"key": "player_points", "outcomes": []},
                    {"key": "player_threes", "outcomes": []},
                ],
            },
            {
                "key": "pinnacle",  # NOT in US_BOOKMAKER_KEYS
                "title": "Pinnacle",
                "markets": [
                    {"key": "player_points", "outcomes": []},
                ],
            },
        ],
    }

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_returns_list_on_success(self, mock_request, mock_key):
        from data.odds_client import get_event_markets
        mock_request.return_value = self.SAMPLE_EVENT_ODDS
        result = get_event_markets("evt1")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_filters_to_us_bookmakers_only(self, mock_request, mock_key):
        """Only bookmakers in US_BOOKMAKER_KEYS should be returned."""
        from data.odds_client import get_event_markets
        mock_request.return_value = self.SAMPLE_EVENT_ODDS
        result = get_event_markets("evt1")
        bm_keys = {r["bookmaker_key"] for r in result}
        self.assertIn("draftkings", bm_keys)
        self.assertIn("fanduel", bm_keys)
        self.assertNotIn("pinnacle", bm_keys)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_lists_offered_markets(self, mock_request, mock_key):
        """Each bookmaker entry should list the markets they offer."""
        from data.odds_client import get_event_markets
        mock_request.return_value = self.SAMPLE_EVENT_ODDS
        result = get_event_markets("evt1")
        dk = [r for r in result if r["bookmaker_key"] == "draftkings"][0]
        self.assertIn("player_points", dk["markets"])
        self.assertIn("player_rebounds", dk["markets"])
        self.assertIn("player_assists", dk["markets"])

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_includes_display_name(self, mock_request, mock_key):
        """Each entry should have a human-readable bookmaker_title."""
        from data.odds_client import get_event_markets
        mock_request.return_value = self.SAMPLE_EVENT_ODDS
        result = get_event_markets("evt1")
        dk = [r for r in result if r["bookmaker_key"] == "draftkings"][0]
        self.assertEqual(dk["bookmaker_title"], "DraftKings")

    @patch("data.odds_client._resolve_api_key", return_value=None)
    def test_returns_empty_list_when_no_key(self, mock_key):
        from data.odds_client import get_event_markets
        result = get_event_markets("evt1")
        self.assertEqual(result, [])

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry", return_value=None)
    def test_returns_empty_list_on_failure(self, mock_request, mock_key):
        from data.odds_client import get_event_markets
        result = get_event_markets("evt1")
        self.assertEqual(result, [])

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_skips_non_prop_markets(self, mock_request, mock_key):
        """Markets not in PLAYER_PROP_MARKETS should be excluded."""
        from data.odds_client import get_event_markets
        mock_request.return_value = {
            "id": "evt1",
            "bookmakers": [{
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {"key": "h2h", "outcomes": []},
                    {"key": "spreads", "outcomes": []},
                    {"key": "player_points", "outcomes": []},
                ],
            }],
        }
        result = get_event_markets("evt1")
        dk = [r for r in result if r["bookmaker_key"] == "draftkings"][0]
        self.assertNotIn("h2h", dk["markets"])
        self.assertNotIn("spreads", dk["markets"])
        self.assertIn("player_points", dk["markets"])

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_bookmaker_with_no_prop_markets_excluded(self, mock_request, mock_key):
        """A bookmaker that offers only featured markets should be excluded."""
        from data.odds_client import get_event_markets
        mock_request.return_value = {
            "id": "evt1",
            "bookmakers": [{
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {"key": "h2h", "outcomes": []},
                    {"key": "spreads", "outcomes": []},
                ],
            }],
        }
        result = get_event_markets("evt1")
        self.assertEqual(result, [])


# ── Section 7: get_event_odds() — bookmaker filtering and flags ──────────────

class TestGetEventOddsBookmakers(unittest.TestCase):
    """Verify get_event_odds() supports bookmaker filtering and recommended flags."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_accepts_bookmakers_param(self):
        """get_event_odds must accept a bookmakers parameter."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 500]
        self.assertIn("bookmakers", snippet)

    def test_includes_links_flag(self):
        """get_event_odds must send includeLinks=true."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn('"includeLinks"', snippet)

    def test_includes_sids_flag(self):
        """get_event_odds must send includeSids=true."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn('"includeSids"', snippet)

    def test_includes_bet_limits_flag(self):
        """get_event_odds must send includeBetLimits=true."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn('"includeBetLimits"', snippet)

    def test_includes_multipliers_flag(self):
        """get_event_odds must send includeMultipliers=true."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn('"includeMultipliers"', snippet)

    def test_includes_rotation_numbers_flag(self):
        """get_event_odds must send includeRotationNumbers=true."""
        idx = self.src.find("def get_event_odds(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn('"includeRotationNumbers"', snippet)


class TestGetEventOddsBookmakersRuntime(unittest.TestCase):
    """Runtime tests for get_event_odds() bookmaker filtering."""

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_passes_bookmakers_param(self, mock_request, mock_key):
        """Bookmakers string should be passed to API params."""
        from data.odds_client import get_event_odds
        mock_request.return_value = {"id": "x", "bookmakers": []}
        get_event_odds("x", markets="player_points",
                       bookmakers="draftkings,fanduel")
        call_args = mock_request.call_args
        params = call_args[1].get("params") or call_args[0][1]
        self.assertEqual(params["bookmakers"], "draftkings,fanduel")

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_omits_bookmakers_when_none(self, mock_request, mock_key):
        """When bookmakers is None, the param should not appear."""
        from data.odds_client import get_event_odds
        mock_request.return_value = {"id": "x", "bookmakers": []}
        get_event_odds("x", markets="h2h")
        call_args = mock_request.call_args
        params = call_args[1].get("params") or call_args[0][1]
        self.assertNotIn("bookmakers", params)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    def test_includes_all_recommended_flags(self, mock_request, mock_key):
        """All recommended flags should be in the API params."""
        from data.odds_client import get_event_odds
        mock_request.return_value = {"id": "x", "bookmakers": []}
        get_event_odds("x")
        call_args = mock_request.call_args
        params = call_args[1].get("params") or call_args[0][1]
        self.assertEqual(params["includeLinks"], "true")
        self.assertEqual(params["includeSids"], "true")
        self.assertEqual(params["includeBetLimits"], "true")
        self.assertEqual(params["includeMultipliers"], "true")
        self.assertEqual(params["includeRotationNumbers"], "true")


# ── Section 8: get_player_props() — bookmaker filtering + market_key ─────────

class TestGetPlayerPropsBookmakerFiltering(unittest.TestCase):
    """Verify get_player_props() filters by US bookmaker keys."""

    def setUp(self):
        self.src = _OA_SRC.read_text(encoding="utf-8")

    def test_references_us_bookmaker_keys(self):
        """get_player_props must reference US_BOOKMAKER_KEYS for filtering."""
        idx = self.src.find("def get_player_props(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn("US_BOOKMAKER_KEYS", snippet)

    def test_sends_bookmakers_param(self):
        """get_player_props must send bookmakers param in API call."""
        idx = self.src.find("def get_player_props(")
        self.assertGreater(idx, 0)
        snippet = self.src[idx:idx + 3000]
        self.assertIn('"bookmakers"', snippet)


class TestGetPlayerPropsRuntimeFiltering(unittest.TestCase):
    """Runtime tests for get_player_props() bookmaker filtering and market_key."""

    SAMPLE_EVENT_ODDS = {
        "id": "evt1",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [{
                    "key": "player_points",
                    "outcomes": [
                        {"name": "LeBron James", "description": "Over",
                         "price": -115, "point": 25.5},
                        {"name": "LeBron James", "description": "Under",
                         "price": -105, "point": 25.5},
                    ],
                }],
            },
            {
                "key": "pinnacle",  # NOT in US_BOOKMAKER_KEYS
                "title": "Pinnacle",
                "markets": [{
                    "key": "player_points",
                    "outcomes": [
                        {"name": "LeBron James", "description": "Over",
                         "price": -110, "point": 25.5},
                        {"name": "LeBron James", "description": "Under",
                         "price": -110, "point": 25.5},
                    ],
                }],
            },
        ],
    }

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    @patch("data.odds_client.time.sleep")
    def test_filters_to_us_bookmakers(self, mock_sleep, mock_request, mock_key):
        """Props should only come from US_BOOKMAKER_KEYS bookmakers."""
        from data.odds_client import get_player_props
        # First call returns events, second returns odds
        mock_request.side_effect = [
            [{"id": "evt1", "home_team": "Lakers", "away_team": "Celtics"}],
            self.SAMPLE_EVENT_ODDS,
        ]
        result = get_player_props()
        platforms = {p["platform"] for p in result}
        self.assertIn("DraftKings", platforms)
        self.assertNotIn("Pinnacle", platforms)

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    @patch("data.odds_client.time.sleep")
    def test_includes_market_key(self, mock_sleep, mock_request, mock_key):
        """Each prop dict should include the raw market_key."""
        from data.odds_client import get_player_props
        mock_request.side_effect = [
            [{"id": "evt1", "home_team": "Lakers", "away_team": "Celtics"}],
            self.SAMPLE_EVENT_ODDS,
        ]
        result = get_player_props()
        self.assertGreater(len(result), 0)
        for prop in result:
            self.assertIn("market_key", prop)
            self.assertEqual(prop["market_key"], "player_points")

    @patch("data.odds_client._resolve_api_key", return_value="test-key")
    @patch("data.odds_client._request_with_retry")
    @patch("data.odds_client.time.sleep")
    def test_prop_dict_has_required_fields(self, mock_sleep, mock_request, mock_key):
        """Each prop dict must have all expected keys."""
        from data.odds_client import get_player_props
        mock_request.side_effect = [
            [{"id": "evt1", "home_team": "Lakers", "away_team": "Celtics"}],
            self.SAMPLE_EVENT_ODDS,
        ]
        result = get_player_props()
        self.assertGreater(len(result), 0)
        required_keys = {
            "player_name", "team", "stat_type", "market_key", "line",
            "platform", "game_date", "retrieved_at", "over_odds", "under_odds",
        }
        for prop in result:
            self.assertTrue(
                required_keys.issubset(prop.keys()),
                f"Missing keys: {required_keys - prop.keys()}",
            )


# ── Section 9: _PROP_MARKETS uses PLAYER_PROP_MARKETS ────────────────────────

class TestPropMarketsBackedByConfig(unittest.TestCase):
    """Verify _PROP_MARKETS is derived from PLAYER_PROP_MARKETS."""

    def test_prop_markets_matches_config(self):
        """_PROP_MARKETS must equal PLAYER_PROP_MARKETS."""
        from data.odds_client import _PROP_MARKETS, PLAYER_PROP_MARKETS
        self.assertEqual(_PROP_MARKETS, list(PLAYER_PROP_MARKETS))


if __name__ == "__main__":
    unittest.main()
