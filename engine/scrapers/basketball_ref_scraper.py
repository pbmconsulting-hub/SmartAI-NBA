"""engine/scrapers/basketball_ref_scraper.py – Basketball Reference scraper.

Uses requests + beautifulsoup4. Rate-limited (3s delay) with exponential backoff retry.
Replaces the basketball_reference_web_scraper package dependency.
"""
import time
import random
from utils.logger import get_logger

_logger = get_logger(__name__)

_BASE_URL = "https://www.basketball-reference.com"
_DELAY = 3.0  # seconds between requests
_MAX_RETRIES = 3
_USER_AGENT = (
    "Mozilla/5.0 (compatible; SmartAI-NBA/1.0; +https://github.com/pbmconsulting-hub/SmartAI-NBA)"
)

try:
    import requests
    from bs4 import BeautifulSoup
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False
    _logger.debug("requests/beautifulsoup4 not installed; basketball_ref_scraper unavailable")


def _fetch(url: str) -> str:
    """Fetch a URL with rate limiting and exponential backoff.

    Args:
        url: Target URL.

    Returns:
        Response text, or empty string on failure.
    """
    if not _DEPS_AVAILABLE:
        _logger.warning("requests/beautifulsoup4 not available")
        return ""

    time.sleep(_DELAY)
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            wait = (2 ** attempt) + random.uniform(0, 1)
            _logger.debug("Fetch attempt %d failed for %s: %s — retrying in %.1fs", attempt + 1, url, exc, wait)
            time.sleep(wait)

    _logger.error("All %d fetch attempts failed for %s", _MAX_RETRIES, url)
    return ""


def _player_url_slug(player_name: str) -> str:
    """Convert a player name to a Basketball Reference URL slug.

    Args:
        player_name: Full player name (e.g. "LeBron James").

    Returns:
        URL slug (e.g. "j/jamesle01").
    """
    parts = player_name.lower().split()
    if len(parts) < 2:
        return ""
    last = parts[-1][:5]
    first = parts[0][:2]
    slug = f"{last[0]}/{last}{first}01"
    return slug


def get_player_game_log(player_name: str, season: str) -> list:
    """Scrape a player's game log for a given season.

    Args:
        player_name: Full player name.
        season: Season string (e.g. "2024").

    Returns:
        List of game log dicts, or empty list on failure.
    """
    slug = _player_url_slug(player_name)
    if not slug:
        return []

    url = f"{_BASE_URL}/players/{slug}/gamelog/{season}"
    html = _fetch(url)
    if not html:
        return []

    rows = []
    try:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "pgl_basic"})
        if table is None:
            return []

        headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]
        for tr in table.find("tbody").find_all("tr"):
            if tr.get("class") and "thead" in tr.get("class", []):
                continue
            cells = tr.find_all(["td", "th"])
            if len(cells) < 5:
                continue
            row = {headers[i]: cells[i].get_text(strip=True) for i in range(min(len(headers), len(cells)))}
            if row.get("Rk") and row["Rk"].isdigit():
                rows.append(row)
    except Exception as exc:
        _logger.error("parse error for %s game log: %s", player_name, exc)

    return rows


def get_player_season_stats(player_name: str, season: str) -> dict:
    """Scrape season averages for a player.

    Args:
        player_name: Full player name.
        season: Season string (e.g. "2024").

    Returns:
        Dict of stat averages, or empty dict on failure.
    """
    slug = _player_url_slug(player_name)
    if not slug:
        return {}

    url = f"{_BASE_URL}/players/{slug}.html"
    html = _fetch(url)
    if not html:
        return {}

    try:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "per_game"})
        if table is None:
            return {}

        headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]
        for tr in table.find("tbody").find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            row = {headers[i]: cells[i].get_text(strip=True) for i in range(min(len(headers), len(cells)))}
            if str(season) in row.get("Season", ""):
                return row
    except Exception as exc:
        _logger.error("parse error for %s season stats: %s", player_name, exc)

    return {}


def get_team_standings(season: str) -> list:
    """Scrape NBA standings for a given season.

    Args:
        season: Season string (e.g. "2024").

    Returns:
        List of team standing dicts.
    """
    url = f"{_BASE_URL}/leagues/NBA_{season}_standings.html"
    html = _fetch(url)
    if not html:
        return []

    standings = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for conf in ["divs_standings_E", "divs_standings_W"]:
            table = soup.find("table", {"id": conf})
            if table is None:
                continue
            headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]
            for tr in table.find("tbody").find_all("tr"):
                if tr.get("class") and "thead" in tr.get("class", []):
                    continue
                cells = tr.find_all(["td", "th"])
                if len(cells) < 3:
                    continue
                row = {headers[i]: cells[i].get_text(strip=True) for i in range(min(len(headers), len(cells)))}
                if row:
                    standings.append(row)
    except Exception as exc:
        _logger.error("standings parse error for season %s: %s", season, exc)

    return standings
