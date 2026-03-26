"""engine/scrapers/balldontlie_client.py – BallDontLie API REST client (backup data source)."""
import time
from utils.logger import get_logger

_logger = get_logger(__name__)

_BASE_URL = "https://api.balldontlie.io/v1"
_DELAY = 1.0  # free tier: 1 request/second

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False
    _logger.debug("requests not installed; balldontlie_client unavailable")


def _get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to BallDontLie API.

    Args:
        endpoint: API endpoint path (e.g. "/players").
        params: Query parameters.

    Returns:
        Parsed JSON response dict, or empty dict on failure.
    """
    if not _REQUESTS_AVAILABLE:
        return {}

    time.sleep(_DELAY)
    url = f"{_BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, params=params or {}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        _logger.error("BallDontLie API error [%s]: %s", endpoint, exc)
        return {}


def get_player_stats(player_id: int, season: int) -> list:
    """Fetch season averages for a player from BallDontLie.

    Args:
        player_id: BallDontLie player ID.
        season: Season year (e.g. 2024).

    Returns:
        List of season average stat dicts.
    """
    data = _get("/season_averages", params={"season": season, "player_ids[]": player_id})
    return data.get("data", [])


def get_games(date: str) -> list:
    """Fetch games scheduled for a given date.

    Args:
        date: Date string in YYYY-MM-DD format.

    Returns:
        List of game dicts.
    """
    data = _get("/games", params={"dates[]": date, "per_page": 100})
    return data.get("data", [])


def search_players(name: str) -> list:
    """Search for players by name.

    Args:
        name: Partial or full player name.

    Returns:
        List of matching player dicts.
    """
    data = _get("/players", params={"search": name, "per_page": 25})
    return data.get("data", [])
