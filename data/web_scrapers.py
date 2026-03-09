# ============================================================
# FILE: data/web_scrapers.py
# PURPOSE: NBA roster and injury data via nba_api and
#          Basketball-Reference (season stats only).
#
# SOURCES:
#   1. nba_api (via RosterEngine)       — injury designations + roster
#   2. Basketball-Reference             — per-game season stats (HTML)
#
# USAGE:
#   from data.web_scrapers import (
#       fetch_multi_source_injury_status,
#       fetch_verified_rosters,
#       scrape_bref_season_stats,
#   )
#
# RATE-LIMITING NOTES:
#   - Basketball-Reference: max 20 requests/min → 3 s delay enforced
# ============================================================

import re
import time
import json
import os

# Third-party imports (listed in requirements.txt)
try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPER_DEPS_AVAILABLE = True
except ImportError:
    _SCRAPER_DEPS_AVAILABLE = False

# Re-export fetch_all_injury_data so callers only need this module
try:
    from data.web_scraper import fetch_all_injury_data
    _CORE_SCRAPER_AVAILABLE = True
except ImportError:
    _CORE_SCRAPER_AVAILABLE = False
    fetch_all_injury_data = None

# ============================================================
# SECTION: Constants
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_HEADERS_LOCAL = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

_REQUEST_TIMEOUT = 15
_BREF_DELAY = 3.0

BREF_PER_GAME_URL = "https://www.basketball-reference.com/leagues/NBA_2026_per_game.html"

# Injury status JSON path (same as live_data_fetcher uses)
_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
INJURY_STATUS_JSON_PATH = os.path.join(_DATA_DIR, "injury_status.json")

# ============================================================
# END SECTION: Constants
# ============================================================


# ============================================================
# SECTION: Internal Helpers
# ============================================================

def _safe_get(url, headers=None, timeout=_REQUEST_TIMEOUT, retries=3):
    """
    HTTP GET with exponential-backoff retry logic.
    Returns a requests.Response on success, None on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        return None
    _hdrs = headers or _HEADERS_LOCAL
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=_hdrs, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                # Rate-limited — wait longer then retry
                wait = 2 ** attempt
                print(f"_safe_get: rate-limited ({url}), waiting {wait}s")
                time.sleep(wait)
            else:
                print(f"_safe_get: HTTP {resp.status_code} for {url} (attempt {attempt})")
                if resp.status_code in (404, 403):
                    break
        except Exception as exc:
            wait = 2 ** attempt
            print(f"_safe_get: error fetching {url}: {exc} — retry in {wait}s")
            time.sleep(wait)
    return None


def _canonicalize_status(raw):
    """Map raw status strings to canonical labels."""
    _MAP = {
        "out": "Out",
        "out for season": "Out",
        "suspended": "Out",
        "injured reserve": "Injured Reserve",
        "ir": "Injured Reserve",
        "game time decision": "GTD",
        "gtd": "GTD",
        "day-to-day": "Day-to-Day",
        "day to day": "Day-to-Day",
        "dtd": "Day-to-Day",
        "doubtful": "Doubtful",
        "questionable": "Questionable",
        "probable": "Probable",
        "active": "Active",
    }
    return _MAP.get(str(raw).strip().lower(), "Unknown")


# Common name suffixes to strip for normalised key comparison
_NAME_SUFFIXES_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)\s*$",
    re.IGNORECASE,
)


def _normalize_player_key(name):
    """
    Return a consistent lowercase key for a player name.

    Strips leading/trailing whitespace, collapses internal whitespace,
    and removes common generational suffixes (Jr., Sr., II, III, IV, V)
    so that "Jaren Jackson Jr." and "Jaren Jackson" map to the same key.

    Args:
        name (str): Raw player name.

    Returns:
        str: Normalised lowercase key.
    """
    if not name:
        return ""
    key = name.lower().strip()
    key = re.sub(r"\s+", " ", key)          # collapse internal whitespace
    key = _NAME_SUFFIXES_RE.sub("", key)    # strip generational suffixes
    return key.strip()

# ============================================================
# END SECTION: Internal Helpers
# ============================================================


# ============================================================
# SECTION: Scraper 1 — Basketball-Reference Per-Game Stats
# ============================================================

def scrape_bref_season_stats():
    """
    Scrape the Basketball-Reference NBA per-game stats table for the
    current season (2025-26).

    URL: https://www.basketball-reference.com/leagues/NBA_2026_per_game.html

    Rate limiting: enforces a 3-second delay before the request to stay
    within Basketball-Reference's published limit of 20 requests/minute.

    Returns:
        list[dict]: Each dict contains:
            player_name, team, position, games_played, mpg, ppg, rpg,
            apg, threes_pm, spg, bpg, tov, ft_pct, usg_pct
        Empty list on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print("scrape_bref_season_stats: requests/bs4 not installed — skipped")
        return []

    print(f"scrape_bref_season_stats: waiting {_BREF_DELAY}s to respect rate limit")
    time.sleep(_BREF_DELAY)

    resp = _safe_get(BREF_PER_GAME_URL)
    if resp is None:
        print("scrape_bref_season_stats: failed to fetch Basketball-Reference page")
        return []

    results = []
    try:
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="per_game_stats")
        if table is None:
            # Try generic table fallback
            table = soup.find("table", class_=lambda c: c and "stats_table" in c)
        if table is None:
            print("scrape_bref_season_stats: stats table not found on page")
            return []

        def _safe_float(val, default=0.0):
            try:
                return float(val) if val and val != "" else default
            except (ValueError, TypeError):
                return default

        tbody = table.find("tbody")
        if tbody is None:
            return []

        seen_players = set()
        for row in tbody.find_all("tr"):
            # Skip header rows interspersed in the table body
            if row.get("class") and "thead" in row.get("class"):
                continue
            if row.find("th", {"data-stat": "ranker"}) is None and row.find("td") is None:
                continue

            cells = {td["data-stat"]: td.get_text(strip=True)
                     for td in row.find_all("td") if td.get("data-stat")}
            if not cells:
                continue

            player_name = cells.get("player", "").strip()
            if not player_name or player_name == "Player":
                continue

            # Skip duplicate rows (multi-team players appear multiple times)
            # Keep the "TOT" (total) row if present
            team = cells.get("team_id", cells.get("team", ""))
            if player_name in seen_players and team != "TOT":
                continue
            seen_players.add(player_name)

            results.append({
                "player_name": player_name,
                "team": team,
                "position": cells.get("pos", ""),
                "games_played": int(_safe_float(cells.get("g", "0"))),
                "mpg": _safe_float(cells.get("mp_per_g", cells.get("mp", "0"))),
                "ppg": _safe_float(cells.get("pts_per_g", cells.get("pts", "0"))),
                "rpg": _safe_float(cells.get("trb_per_g", cells.get("trb", "0"))),
                "apg": _safe_float(cells.get("ast_per_g", cells.get("ast", "0"))),
                "threes_pm": _safe_float(cells.get("fg3_per_g", cells.get("fg3", "0"))),
                "spg": _safe_float(cells.get("stl_per_g", cells.get("stl", "0"))),
                "bpg": _safe_float(cells.get("blk_per_g", cells.get("blk", "0"))),
                "tov": _safe_float(cells.get("tov_per_g", cells.get("tov", "0"))),
                "ft_pct": _safe_float(cells.get("ft_pct", "0")),
                "usg_pct": _safe_float(cells.get("usg_pct", "0")),
            })

        print(f"scrape_bref_season_stats: {len(results)} player rows parsed")
    except Exception as exc:
        print(f"scrape_bref_season_stats: parse error — {exc}")

    return results

# ============================================================
# END SECTION: Scraper 1 — Basketball-Reference Per-Game Stats
# ============================================================


# ============================================================
# SECTION: Consolidated Multi-Source Injury Fetcher
# ============================================================

def fetch_multi_source_injury_status(todays_games=None):
    """
    Fetch and merge injury status from official NBA CDN sources.

    Uses only free, official NBA data feeds (no third-party HTML scraping):
        1. NBA.com CDN static injury JSON  — authoritative designation
        2. Live daily CDN injury JSON      — latest daily updates

    Both feeds are accessed via RosterEngine which handles retries,
    format variations, and status normalisation.

    Args:
        todays_games (list|None): Tonight's games (used for logging context).

    Returns:
        dict: {player_name_lower: {
                  "status":      str,
                  "injury":      str,
                  "injury_note": str,
                  "team":        str,
                  "return_date": str,
                  "comment":     str,
                  "source":      str,
              }}
        Empty dict if all sources fail.
    """
    try:
        from data.roster_engine import RosterEngine
        engine = RosterEngine()
        # refresh() without team_abbrevs fetches injury + CommonAllPlayers data via nba_api
        engine.refresh()
        raw = engine.get_injury_report()

        # Normalise to the output schema callers expect.
        # 'injury_note' and 'comment' mirror 'injury' for backward
        # compatibility — callers may read either field for the injury description.
        merged = {}
        for key, entry in raw.items():
            merged[key] = {
                "status":      entry.get("status", "Unknown"),
                "injury":      entry.get("injury", ""),
                "injury_note": entry.get("injury", ""),
                "team":        entry.get("team", ""),
                "return_date": entry.get("return_date", ""),
                "comment":     entry.get("injury", ""),
                "source":      entry.get("source", "nba_api"),
            }

        total     = len(merged)
        out_count = sum(1 for v in merged.values() if v["status"] == "Out")
        gtd_count = sum(
            1 for v in merged.values()
            if v["status"] in ("GTD", "Questionable", "Doubtful", "Day-to-Day")
        )
        print(
            f"fetch_multi_source_injury_status complete: {total} players — "
            f"{out_count} Out, {gtd_count} GTD/Questionable/Doubtful"
        )
        return merged
    except Exception as exc:
        print(f"fetch_multi_source_injury_status: error — {exc}")
        return {}

# ============================================================
# END SECTION: Consolidated Multi-Source Injury Fetcher
# ============================================================


# ============================================================
# SECTION: Consolidated Roster Fetcher
# ============================================================

def fetch_verified_rosters(team_abbrevs, todays_games=None):
    """
    Fetch rosters for a list of team abbreviations.

    Delegates entirely to RosterEngine (nba_api CommonTeamRoster) — the
    single authoritative source. Injured and two-way / G-League players
    are excluded by RosterEngine.

    Args:
        team_abbrevs (list[str]): Team abbreviations, e.g. ["LAL", "BOS"]
        todays_games (list|None): Tonight's games (optional, unused).

    Returns:
        dict: {team_abbrev: [player_name, ...]}
    """
    from data.roster_engine import RosterEngine
    engine = RosterEngine()
    engine.refresh(team_abbrevs)
    return {abbrev: engine.get_active_roster(abbrev) for abbrev in (team_abbrevs or [])}

# ============================================================
# END SECTION: Consolidated Roster Fetcher
# ============================================================


# ============================================================
# SECTION: Convenience function for tonight's active players
# ============================================================

def get_active_players_for_tonight(todays_games: list) -> dict:
    """
    Convenience wrapper: uses RosterEngine to return active (non-injured)
    players for every team playing tonight.

    Both web_scraper.py and web_scrapers.py delegate to the same
    RosterEngine so there is a single source of truth for roster + injury
    logic.  This function is the preferred entry-point for callers that
    import from web_scrapers.

    Args:
        todays_games (list): List of game dicts with 'home_team'/'away_team'.

    Returns:
        dict: {team_abbrev: [player_name, ...]}  — injured players excluded.
    """
    try:
        from data.roster_engine import get_active_players_for_tonight as _re_fn
        return _re_fn(todays_games)
    except Exception as exc:
        print(f"get_active_players_for_tonight (web_scrapers): {exc}")
        return {}

# ============================================================
# END SECTION: Convenience function for tonight's active players
# ============================================================
