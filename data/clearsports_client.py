"""
data/clearsports_client.py
--------------------------
API-NBA client for NBA data (via API-Sports).

Provides:
  NBA Data:
  - fetch_teams()                     → all NBA teams
  - fetch_games(season=None, date=None, team_id=None) → NBA games with optional filters
  - fetch_players(team_id=None)            → NBA players with optional team filter
  - fetch_games_today()               → today's scheduled games with lines
  - fetch_player_stats()              → season-average player stats with std-dev fields
  - fetch_team_stats()                → team pace / ratings / record
  - fetch_team_by_id(team_id)         → a specific NBA team by ID
  - fetch_injury_report(team_id)      → player injury status keyed by lowercased name
  - fetch_live_scores()               → live / recent game scores
  - fetch_rosters()                   → team rosters keyed by team abbreviation
  - lookup_player_id()                → NBA player-ID integer or None
  - fetch_game_odds(game_id)          → betting odds for NBA games
  - fetch_nba_team_stats(team_id, season) → team statistics
  - fetch_nba_player_stats(player_id, game_id) → player statistics
  - fetch_predictions(game_id)        → AI-powered NBA game predictions

  API Key Management:
  - fetch_api_key_info()              → current API key info (credits, status)
  - fetch_api_key_usage(limit, offset) → detailed usage history
  - fetch_api_key_stats(start_date, end_date) → aggregated usage statistics

API key resolution (first match wins):
  1. st.session_state["api_nba_key"]
  2. st.secrets["API_NBA_KEY"]  (via .streamlit/secrets.toml)
  3. API_NBA_KEY environment variable

Caching uses the same TTL-based pattern as platform_fetcher.py.
Retry logic applies exponential backoff (1 s → 2 s → 4 s, capped at 10 s).
All public functions degrade gracefully: they return empty lists / dicts on
failure and log a warning rather than raising.
"""

import time
import datetime
import os
import logging

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import streamlit as st
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_BASE_URL = "https://v1.basketball.api-sports.io"

# Current NBA season (API-Basketball v1 uses "YYYY-YYYY" format).
_CURRENT_SEASON = "2025-2026"

# NBA league ID in the API-Basketball v1 system.
_NBA_LEAGUE_ID = "12"

MAX_API_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 10

# Valid NBA team abbreviations — canonical 30 plus common API aliases.
# Used to discard non-NBA entries (e.g. All-Star "STARS", "STRIPES", "WORLD", "TBD").
_VALID_NBA_ABBREVS = frozenset({
    # Canonical 30
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
    # Common API aliases
    "GS", "NY", "NO", "SA", "UTAH", "WSH", "BRK", "PHO", "CHO",
})

# ── Full team-name → abbreviation mapping for API-Basketball v1 ───────────────
# API-Basketball v1 returns full names (e.g. "Los Angeles Lakers") rather than
# abbreviations.  This lookup converts them to our canonical 3-letter codes.
_TEAM_FULL_NAME_TO_ABBREV: dict[str, str] = {
    "atlanta hawks": "ATL",
    "boston celtics": "BOS",
    "brooklyn nets": "BKN",
    "charlotte hornets": "CHA",
    "chicago bulls": "CHI",
    "cleveland cavaliers": "CLE",
    "dallas mavericks": "DAL",
    "denver nuggets": "DEN",
    "detroit pistons": "DET",
    "golden state warriors": "GSW",
    "houston rockets": "HOU",
    "indiana pacers": "IND",
    "los angeles clippers": "LAC",
    "la clippers": "LAC",
    "los angeles lakers": "LAL",
    "la lakers": "LAL",
    "memphis grizzlies": "MEM",
    "miami heat": "MIA",
    "milwaukee bucks": "MIL",
    "minnesota timberwolves": "MIN",
    "new orleans pelicans": "NOP",
    "new york knicks": "NYK",
    "oklahoma city thunder": "OKC",
    "orlando magic": "ORL",
    "philadelphia 76ers": "PHI",
    "phoenix suns": "PHX",
    "portland trail blazers": "POR",
    "sacramento kings": "SAC",
    "san antonio spurs": "SAS",
    "toronto raptors": "TOR",
    "utah jazz": "UTA",
    "washington wizards": "WAS",
}

# ── Dynamic team-abbreviation → numeric ID cache ─────────────────────────────
# Populated lazily from fetch_teams() the first time it's needed.
_TEAM_ABBREV_TO_ID: dict[str, int] = {}

# ── Time-based response cache (mirrors platform_fetcher._API_CACHE) ───────────

_API_CACHE: dict = {}
_API_CACHE_TTL: int = int(os.environ.get("API_CACHE_TTL_SECONDS", "300"))

# Module-level player-ID lookup cache: name (str) → player_id (int | None)
_PLAYER_ID_CACHE: dict = {}


def _cache_get(key: str):
    """Return cached payload for *key* if still within TTL, else None."""
    entry = _API_CACHE.get(key)
    if entry is None:
        return None
    payload, ts = entry
    if time.time() - ts > _API_CACHE_TTL:
        del _API_CACHE[key]
        return None
    return payload


def _cache_set(key: str, payload) -> None:
    """Store *payload* in the cache keyed by *key*."""
    _API_CACHE[key] = (payload, time.time())


# ── Team name / ID resolution helpers ─────────────────────────────────────────

def _team_name_to_abbrev(name: str) -> str:
    """Convert a full team name (e.g. 'Los Angeles Lakers') to abbreviation."""
    if not name:
        return ""
    return _TEAM_FULL_NAME_TO_ABBREV.get(name.strip().lower(), "")


def _ensure_team_id_map() -> None:
    """Populate ``_TEAM_ABBREV_TO_ID`` from ``fetch_teams()`` if empty."""
    global _TEAM_ABBREV_TO_ID  # noqa: PLW0603
    if _TEAM_ABBREV_TO_ID:
        return
    try:
        teams = fetch_teams()
        for t in teams:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            if tid is None:
                continue
            # Try direct abbreviation first, then resolve from name
            abbrev = _safe_str(
                t.get("abbreviation") or t.get("team_abbreviation")
            ).upper().strip()
            if not abbrev:
                name = _safe_str(t.get("name") or t.get("team_name"))
                abbrev = _team_name_to_abbrev(name)
            if abbrev:
                _TEAM_ABBREV_TO_ID[abbrev] = int(tid)
    except Exception as exc:
        _logger.debug("_ensure_team_id_map: could not build map — %s", exc)


def _get_team_id(abbrev: str) -> int | None:
    """Resolve a team abbreviation to its API-Basketball v1 numeric team ID."""
    _ensure_team_id_map()
    return _TEAM_ABBREV_TO_ID.get(abbrev.upper().strip())


# ── API key resolution ────────────────────────────────────────────────────────

def validate_api_key(key: str | None) -> tuple[bool, str]:
    """Check whether *key* looks like a valid API-NBA key.

    Returns:
        (is_valid, message): True with a success message when the format
        is acceptable, False with a reason when it is not.
    """
    if not key or not isinstance(key, str):
        return False, "API key is empty or missing."
    key = key.strip()
    if len(key) < 10:
        return False, "API key is too short."
    if " " in key:
        return False, "API key must not contain spaces."
    return True, "API key format looks valid."


def _resolve_api_key() -> str | None:
    """Return the API-NBA key from session state, secrets, or environment."""
    if _ST_AVAILABLE:
        try:
            key = st.session_state.get("api_nba_key")
            if key:
                return key
        except Exception:
            pass
        try:
            key = st.secrets.get("API_NBA_KEY")
            if key:
                return key
        except Exception:
            pass
    return os.environ.get("API_NBA_KEY")


# ── HTTP helper with retry / caching ─────────────────────────────────────────

def _build_cache_key(url: str, params: dict | None = None) -> str:
    """Build a cache key from *url* and optional *params*."""
    if not params:
        return url
    sorted_items = sorted(params.items())
    qs = "&".join(f"{k}={v}" for k, v in sorted_items)
    return f"{url}?{qs}"


def _fetch_with_retry(url: str, params: dict | None = None) -> dict | list | None:
    """
    GET *url* with exponential-backoff retry and response caching.

    Returns parsed JSON on success, or None if all attempts fail.
    Results are cached for _API_CACHE_TTL seconds.
    """
    if not REQUESTS_AVAILABLE:
        _logger.warning("requests library is not available — cannot call API-NBA")
        return None

    cache_key = _build_cache_key(url, params)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    api_key = _resolve_api_key()
    if not api_key:
        _logger.warning("No API-NBA key found — skipping request to %s", url)
        return None

    headers = {
        "x-apisports-key": api_key,
    }

    for attempt in range(MAX_API_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_API_RETRIES:
                    delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)
                    _logger.warning(
                        "HTTP %d on attempt %d/%d for %s — retrying in %.1fs",
                        resp.status_code, attempt + 1, MAX_API_RETRIES + 1, url, delay,
                    )
                    time.sleep(delay)
                    continue
                _logger.error("All retries exhausted for %s (HTTP %d)", url, resp.status_code)
                return None

            if resp.status_code == 401:
                _logger.error("API-NBA key is invalid or unauthorised (401) for %s", url)
                return None

            if resp.status_code == 403:
                _logger.error("API-NBA access denied (403) for %s — credits may be exhausted", url)
                return None

            if resp.status_code == 404:
                _logger.warning("API-NBA endpoint not found (404): %s", url)
                return None

            if resp.status_code == 422:
                _logger.warning("API-NBA 422 (unsupported request) for %s", url)
                return None

            resp.raise_for_status()

            if not resp.text:
                _logger.warning("Empty response body from %s", url)
                return None

            data = resp.json()
            _cache_set(cache_key, data)
            return data

        except Exception as exc:
            if attempt < MAX_API_RETRIES:
                delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)
                _logger.warning(
                    "Request error on attempt %d/%d for %s: %s — retrying in %.1fs",
                    attempt + 1, MAX_API_RETRIES + 1, url, exc, delay,
                )
                time.sleep(delay)
            else:
                _logger.error("All retries exhausted for %s: %s", url, exc)

    return None


# ── Private data-extraction helpers ──────────────────────────────────────────

def _safe_float(value, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value, default: str = "") -> str:
    """Coerce *value* to str, returning *default* on None."""
    if value is None:
        return default
    return str(value)


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.date.today().isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

def _extract_team_abbrev(g: dict, side: str) -> str:
    """
    Extract team abbreviation from a game dict for *side* ('home' or 'away').

    Tries multiple field-name conventions that different API versions use:
      - home_team / away_team                     (original)
      - home_abbreviation / away_abbreviation     (original fallback)
      - home_team_abbreviation / away_team_abbreviation
      - home_tricode / away_tricode
      - home_team_tricode / away_team_tricode
      - Nested: home.abbreviation / away.abbreviation
      - Nested: home_team.abbreviation / away_team.abbreviation
      - API-Basketball v1: teams.home.name / teams.away.name (full name → abbrev)

    Returns the abbreviation string (upper-cased) or empty string.
    """
    # Direct field names
    for key in (
        f"{side}_team",
        f"{side}_abbreviation",
        f"{side}_team_abbreviation",
        f"{side}_tricode",
        f"{side}_team_tricode",
    ):
        val = g.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip().upper()

    # Nested objects: e.g. {"home": {"abbreviation": "LAL"}} or
    #                      {"home_team": {"abbreviation": "LAL"}}
    for key in (side, f"{side}_team", f"{side}Team"):
        nested = g.get(key)
        if isinstance(nested, dict):
            for sub in ("abbreviation", "tricode", "teamTricode", "team_abbreviation"):
                val = nested.get(sub)
                if val and isinstance(val, str) and val.strip():
                    return val.strip().upper()
            # Resolve full team name → abbreviation (API-Basketball v1)
            name = nested.get("name") or nested.get("team_name") or ""
            if name:
                abbrev = _team_name_to_abbrev(name)
                if abbrev:
                    return abbrev.upper()

    # API-Basketball v1: {"teams": {"home": {"name": "Los Angeles Lakers"}}}
    teams_obj = g.get("teams")
    if isinstance(teams_obj, dict):
        side_obj = teams_obj.get(side)
        if isinstance(side_obj, dict):
            for sub in ("abbreviation", "tricode", "teamTricode", "team_abbreviation"):
                val = side_obj.get(sub)
                if val and isinstance(val, str) and val.strip():
                    return val.strip().upper()
            name = side_obj.get("name") or side_obj.get("team_name") or ""
            if name:
                abbrev = _team_name_to_abbrev(name)
                if abbrev:
                    return abbrev.upper()

    return ""


# ── Core NBA resource endpoints ──────────────────────────────────────────────

def fetch_teams() -> list[dict]:
    """
    Retrieve all NBA teams.

    Endpoint: GET /teams

    Returns:
        list[dict]: Team entries.
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/teams"
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        teams_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("teams") or raw.get("data") or [])
        if not isinstance(teams_raw, list):
            _logger.warning("fetch_teams: unexpected response shape, returning []")
            return []
        return [t for t in teams_raw if isinstance(t, dict)]

    except Exception as exc:
        _logger.warning("fetch_teams failed: %s", exc)
        return []


def fetch_games(season=None, date=None, team_id=None) -> list[dict]:
    """
    Retrieve NBA games.

    Endpoint: GET /games

    Args:
        season:  Optional season year (e.g. 2024).
        date:    Optional game date in YYYY-MM-DD format (e.g. "2024-12-25").
        team_id: Optional team ID to filter by.

    Returns:
        list[dict]: Game entries.
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/games"
    params: dict = {"league": _NBA_LEAGUE_ID}
    if season is not None:
        params["season"] = season
    else:
        params["season"] = _CURRENT_SEASON
    if date is not None:
        params["date"] = date
    if team_id is not None:
        params["team"] = team_id

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        games_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("games") or raw.get("data") or [])
        if not isinstance(games_raw, list):
            _logger.warning("fetch_games: unexpected response shape, returning []")
            return []
        return [g for g in games_raw if isinstance(g, dict)]

    except Exception as exc:
        _logger.warning("fetch_games failed: %s", exc)
        return []


def fetch_players(team_id=None) -> list[dict]:
    """
    Retrieve NBA players.

    Endpoint: GET /players
    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    Args:
        team_id: Optional team ID to filter by.

    Returns:
        list[dict]: Player entries.
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/players"
    params: dict = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
    if team_id is not None:
        params["team"] = team_id

    try:
        raw = _fetch_with_retry(url, params=params)
        if raw:
            players_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("players") or raw.get("data") or [])
            if isinstance(players_raw, list):
                result = [p for p in players_raw if isinstance(p, dict)]
                if result:
                    return result
            else:
                _logger.warning("fetch_players: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("fetch_players API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_fallback import fetch_players_fallback
        _logger.info("fetch_players: falling back to free NBA.com stats endpoint")
        return fetch_players_fallback(team_id=team_id)
    except Exception as exc:
        _logger.warning("fetch_players fallback also failed: %s", exc)
        return []


def fetch_games_today() -> list[dict]:
    """
    Fetch today's NBA games with team records and betting lines.

    Returns:
        list[dict]: Each dict has keys:
            home_team, away_team, game_id,
            home_wins, home_losses, away_wins, away_losses,
            vegas_spread, game_total
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/games"
    today = _today_str()
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON, "date": today}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        games_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("games") or raw.get("data") or [])
        if not isinstance(games_raw, list):
            _logger.warning("fetch_games_today: unexpected response shape, returning []")
            return []

        # ── Client-side date filter ──────────────────────────────────────
        # If the API returns more games than a single NBA day can have
        # (max ~15), it likely returned the full season.  Filter to today.
        if len(games_raw) > 20:
            filtered: list[dict] = []
            for g in games_raw:
                if not isinstance(g, dict):
                    continue
                # Try many date-field variants the API may use
                g_date = str(
                    g.get("game_date")
                    or g.get("date")
                    or g.get("scheduled")
                    or g.get("start_time")
                    or g.get("gameDate")
                    or g.get("startDate")
                    or g.get("start_date")
                    or g.get("datetime")
                    or g.get("game_datetime")
                    or g.get("gameDateTime")
                    or ""
                ).strip()
                # Accept if the date field starts with today's YYYY-MM-DD
                if g_date.startswith(today):
                    filtered.append(g)
            if filtered:
                _logger.info(
                    "fetch_games_today: API returned %d games, filtered to %d for %s.",
                    len(games_raw), len(filtered), today,
                )
                games_raw = filtered
            else:
                _logger.warning(
                    "fetch_games_today: API returned %d games but none matched today (%s). "
                    "Proceeding with unfiltered list.",
                    len(games_raw), today,
                )

        games: list[dict] = []
        skipped = 0
        non_nba = 0
        for g in games_raw:
            if not isinstance(g, dict):
                continue

            home_abbrev = _extract_team_abbrev(g, "home")
            away_abbrev = _extract_team_abbrev(g, "away")

            if not home_abbrev or not away_abbrev:
                skipped += 1
                continue

            # Skip non-NBA teams (All-Star, Rising Stars, TBD, etc.)
            if home_abbrev not in _VALID_NBA_ABBREVS or away_abbrev not in _VALID_NBA_ABBREVS:
                non_nba += 1
                continue

            games.append({
                "game_id":     _safe_str(g.get("game_id") or g.get("id")),
                "home_team":   home_abbrev,
                "away_team":   away_abbrev,
                "home_wins":   int(_safe_float(g.get("home_wins", (g.get("home_record") or {}).get("wins", 0)))),
                "home_losses": int(_safe_float(g.get("home_losses", (g.get("home_record") or {}).get("losses", 0)))),
                "away_wins":   int(_safe_float(g.get("away_wins", (g.get("away_record") or {}).get("wins", 0)))),
                "away_losses": int(_safe_float(g.get("away_losses", (g.get("away_record") or {}).get("losses", 0)))),
                "vegas_spread": _safe_float(g.get("vegas_spread") or g.get("spread", 0)),
                "game_total":  _safe_float(g.get("game_total") or g.get("total", 220)),
            })

        if non_nba:
            _logger.info(
                "fetch_games_today: filtered out %d game(s) with non-NBA teams.", non_nba
            )
        if skipped:
            _logger.warning(
                "fetch_games_today: skipped %d game(s) with missing team abbreviations.", skipped
            )

        return games

    except Exception as exc:
        _logger.warning("fetch_games_today failed: %s", exc)
        return []


def fetch_player_stats() -> list[dict]:
    """
    Fetch current-season player averages and standard deviations.

    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    Returns:
        list[dict]: Each dict has keys:
            player_id, name, team, position,
            minutes_avg, points_avg, rebounds_avg, assists_avg,
            threes_avg, steals_avg, blocks_avg, turnovers_avg,
            ft_pct, usage_rate,
            points_std, rebounds_std, assists_std, threes_std,
            steals_std, blocks_std, turnovers_std
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/players"
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}

    try:
        raw = _fetch_with_retry(url, params=params)
        if raw:
            players_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("players") or raw.get("data") or [])
            if isinstance(players_raw, list):
                players: list[dict] = []
                has_real_stats = False
                for p in players_raw:
                    if not isinstance(p, dict):
                        continue
                    stats = p.get("stats") or p.get("averages") or p  # allow flat or nested shape

                    # ── Resolve player name ──
                    # API-Basketball v1 may return firstname/lastname
                    # instead of a single "name" field.
                    name = _safe_str(p.get("name") or p.get("full_name"))
                    if not name:
                        first = _safe_str(p.get("firstname") or p.get("first_name"))
                        last = _safe_str(p.get("lastname") or p.get("last_name"))
                        name = f"{first} {last}".strip()

                    # ── Resolve team abbreviation ──
                    # API-Basketball v1 nests team as a dict:
                    #   {"team": {"id": 145, "name": "Los Angeles Lakers"}}
                    team_val = p.get("team") or p.get("team_abbreviation") or ""
                    if isinstance(team_val, dict):
                        team_abbrev = _safe_str(
                            team_val.get("abbreviation")
                            or team_val.get("tricode")
                        )
                        if not team_abbrev:
                            team_abbrev = _team_name_to_abbrev(
                                _safe_str(team_val.get("name"))
                            )
                    else:
                        team_abbrev = _safe_str(team_val)

                    pts = _safe_float(stats.get("points") or stats.get("pts", 0))
                    if pts > 0:
                        has_real_stats = True
                    # If the team value is a plain string, the data is in
                    # the processed/flat format (or test data), not the
                    # metadata-only /players response from API-Basketball v1.
                    if isinstance(team_val, str) and team_val:
                        has_real_stats = True

                    players.append({
                        "player_id":     _safe_str(p.get("player_id") or p.get("id")),
                        "name":          name,
                        "team":          team_abbrev,
                        "position":      _safe_str(p.get("position") or p.get("pos")),
                        # Averages
                        "minutes_avg":   _safe_float(stats.get("minutes") or stats.get("min", 0)),
                        "points_avg":    pts,
                        "rebounds_avg":  _safe_float(stats.get("rebounds") or stats.get("reb", 0)),
                        "assists_avg":   _safe_float(stats.get("assists") or stats.get("ast", 0)),
                        "threes_avg":    _safe_float(stats.get("threes") or stats.get("three_pm") or stats.get("fg3m", 0)),
                        "steals_avg":    _safe_float(stats.get("steals") or stats.get("stl", 0)),
                        "blocks_avg":    _safe_float(stats.get("blocks") or stats.get("blk", 0)),
                        "turnovers_avg": _safe_float(stats.get("turnovers") or stats.get("tov", 0)),
                        "ft_pct":        _safe_float(stats.get("ft_pct") or stats.get("ftm_pct", 0)),
                        "usage_rate":    _safe_float(stats.get("usage_rate") or stats.get("usg_pct", 0)),
                        # Standard deviations (may not be present in all responses)
                        "points_std":    _safe_float(stats.get("points_std", 0)),
                        "rebounds_std":  _safe_float(stats.get("rebounds_std", 0)),
                        "assists_std":   _safe_float(stats.get("assists_std", 0)),
                        "threes_std":    _safe_float(stats.get("threes_std", 0)),
                        "steals_std":    _safe_float(stats.get("steals_std", 0)),
                        "blocks_std":    _safe_float(stats.get("blocks_std", 0)),
                        "turnovers_std": _safe_float(stats.get("turnovers_std", 0)),
                    })
                # Only return if we got real stat data (not just metadata-only
                # responses from /players that have names but zero stats).
                if players and has_real_stats:
                    return players
                if players and not has_real_stats:
                    _logger.info(
                        "fetch_player_stats: API returned %d player(s) but no "
                        "stat fields — treating as metadata-only response.",
                        len(players),
                    )
            else:
                _logger.warning("fetch_player_stats: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("fetch_player_stats API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_fallback import fetch_player_stats_fallback
        _logger.info("fetch_player_stats: falling back to free NBA.com stats endpoint")
        return fetch_player_stats_fallback()
    except Exception as exc:
        _logger.warning("fetch_player_stats fallback also failed: %s", exc)
        return []


def fetch_team_stats() -> list[dict]:
    """
    Fetch current-season team pace, ratings, and win/loss record.

    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    Returns:
        list[dict]: Each dict has keys:
            team_abbreviation, team_name,
            pace, offensive_rating, defensive_rating,
            wins, losses
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/teams"
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}

    try:
        raw = _fetch_with_retry(url, params=params)
        if raw:
            teams_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("teams") or raw.get("data") or [])
            if isinstance(teams_raw, list):
                teams: list[dict] = []
                for t in teams_raw:
                    if not isinstance(t, dict):
                        continue
                    stats = t.get("stats") or t.get("advanced") or t
                    record = t.get("record") or {}
                    # Resolve abbreviation: try direct field, then from name
                    abbrev = _safe_str(t.get("abbreviation") or t.get("team_abbreviation"))
                    name = _safe_str(t.get("name") or t.get("team_name"))
                    if not abbrev and name:
                        abbrev = _team_name_to_abbrev(name)
                    teams.append({
                        "team_abbreviation":  abbrev,
                        "team_name":          name,
                        "pace":               _safe_float(stats.get("pace", 0)),
                        "offensive_rating":   _safe_float(stats.get("offensive_rating") or stats.get("off_rtg", 0)),
                        "defensive_rating":   _safe_float(stats.get("defensive_rating") or stats.get("def_rtg", 0)),
                        "wins":               int(_safe_float(t.get("wins") or record.get("wins", 0))),
                        "losses":             int(_safe_float(t.get("losses") or record.get("losses", 0))),
                    })
                if teams:
                    return teams
            else:
                _logger.warning("fetch_team_stats: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("fetch_team_stats API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_fallback import fetch_team_stats_fallback
        _logger.info("fetch_team_stats: falling back to free NBA.com stats endpoint")
        return fetch_team_stats_fallback()
    except Exception as exc:
        _logger.warning("fetch_team_stats fallback also failed: %s", exc)
        return []


def fetch_injury_report(team_id=None) -> dict:
    """
    Fetch the current NBA injury report.

    Endpoint: GET /injuries

    Args:
        team_id: Optional team ID to filter by.

    Returns:
        dict: Keyed by player_name.lower().  Each value is a dict with:
            status       – e.g. "Out", "Questionable", "Day-To-Day"
            injury_note  – short description, e.g. "Knee"
            return_date  – estimated return date string or ""
        Returns {} on failure.
    """
    url = f"{_BASE_URL}/injuries"
    params: dict = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
    if team_id is not None:
        params["team"] = team_id

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return {}

        injuries_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("injuries") or raw.get("data") or [])
        if not isinstance(injuries_raw, list):
            _logger.warning("fetch_injury_report: unexpected response shape, returning {}")
            return {}

        report: dict = {}
        for entry in injuries_raw:
            if not isinstance(entry, dict):
                continue
            # API-Sports v2 nests player info: {"player": {"id": N, "name": "..."}}
            player = entry.get("player")
            if isinstance(player, dict):
                name = _safe_str(player.get("name"))
            else:
                name = _safe_str(player or entry.get("player_name") or entry.get("name"))
            if not name:
                continue
            report[name.lower()] = {
                "status":      _safe_str(entry.get("status", "Unknown")),
                # API-Sports uses "type" for injury category (e.g. "Ankle")
                # and "description" for detail (e.g. "Left ankle soreness")
                "injury_note": _safe_str(entry.get("type") or entry.get("description") or entry.get("injury") or entry.get("injury_note")),
                "return_date": _safe_str(entry.get("return_date") or entry.get("date") or entry.get("expected_return", "")),
            }
        return report

    except Exception as exc:
        _logger.warning("fetch_injury_report failed: %s", exc)
        return {}


def fetch_live_scores() -> list[dict]:
    """
    Fetch live / recently completed NBA game scores.

    Returns:
        list[dict]: Each dict has keys:
            game_id, home_team, away_team,
            home_score, away_score,
            period, game_clock, status
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/games"
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON, "date": _today_str()}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        scores_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("scores") or raw.get("games") or raw.get("data") or [])
        if not isinstance(scores_raw, list):
            _logger.warning("fetch_live_scores: unexpected response shape, returning []")
            return []

        scores: list[dict] = []
        for g in scores_raw:
            if not isinstance(g, dict):
                continue

            # ── Resolve team abbreviations ────────────────────────
            home_team = _extract_team_abbrev(g, "home")
            away_team = _extract_team_abbrev(g, "away")

            # ── Resolve scores ────────────────────────────────────
            # API-Basketball v1: {"scores": {"home": {"total": 105}, "away": {"total": 99}}}
            home_score = int(_safe_float(g.get("home_score", 0)))
            away_score = int(_safe_float(g.get("away_score", 0)))
            scores_obj = g.get("scores")
            if isinstance(scores_obj, dict) and home_score == 0 and away_score == 0:
                home_sc = scores_obj.get("home")
                away_sc = scores_obj.get("away")
                if isinstance(home_sc, dict):
                    home_score = int(_safe_float(home_sc.get("total", 0)))
                elif home_sc is not None:
                    home_score = int(_safe_float(home_sc))
                if isinstance(away_sc, dict):
                    away_score = int(_safe_float(away_sc.get("total", 0)))
                elif away_sc is not None:
                    away_score = int(_safe_float(away_sc))

            # ── Resolve status ────────────────────────────────────
            status_val = g.get("status", "")
            if isinstance(status_val, dict):
                status_val = _safe_str(status_val.get("long") or status_val.get("short", ""))
            else:
                status_val = _safe_str(status_val)

            scores.append({
                "game_id":    _safe_str(g.get("game_id") or g.get("id")),
                "home_team":  home_team,
                "away_team":  away_team,
                "home_score": home_score,
                "away_score": away_score,
                "period":     _safe_str(g.get("period") or g.get("quarter", "")),
                "game_clock": _safe_str(g.get("game_clock") or g.get("clock", "")),
                "status":     status_val,
            })
        return scores

    except Exception as exc:
        _logger.warning("fetch_live_scores failed: %s", exc)
        return []


def fetch_rosters(team_abbrevs: list[str]) -> dict[str, list[str]]:
    """
    Fetch player rosters for the given team abbreviations.

    Args:
        team_abbrevs: List of NBA team abbreviation strings, e.g. ["LAL", "BOS"].

    Returns:
        dict: {team_abbrev: [player_name, ...]}
        Entries for teams whose roster could not be fetched are omitted.
    """
    rosters: dict[str, list[str]] = {}

    for abbrev in team_abbrevs:
        url = f"{_BASE_URL}/players"
        # API-Basketball v1 requires numeric team IDs for the "team" param.
        # Resolve abbreviation → numeric ID; fall back to abbreviation string
        # so the call still works if the ID map cannot be built.
        team_param = _get_team_id(abbrev) or abbrev
        params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON, "team": team_param}

        try:
            raw = _fetch_with_retry(url, params=params)
            if not raw:
                continue

            roster_raw = (
                raw if isinstance(raw, list)
                else (raw.get("response") or raw.get("roster") or raw.get("players") or raw.get("data") or [])
            )
            if not isinstance(roster_raw, list):
                _logger.warning("fetch_rosters: unexpected shape for team %s", abbrev)
                continue

            names: list[str] = []
            for player in roster_raw:
                if isinstance(player, str):
                    names.append(player)
                elif isinstance(player, dict):
                    # Try "name", then build from "firstname"/"lastname"
                    name = _safe_str(
                        player.get("name") or player.get("full_name") or player.get("player_name")
                    )
                    if not name:
                        first = _safe_str(player.get("firstname") or player.get("first_name"))
                        last = _safe_str(player.get("lastname") or player.get("last_name"))
                        name = f"{first} {last}".strip()
                    if name:
                        names.append(name)

            rosters[abbrev] = names

        except Exception as exc:
            _logger.warning("fetch_rosters failed for team %s: %s", abbrev, exc)

    return rosters


def lookup_player_id(player_name: str) -> int | None:
    """
    Return the NBA integer player ID for *player_name*, or None if not found.

    Lookup order:
      1. Module-level _PLAYER_ID_CACHE (name → id)
      2. API-NBA /players endpoint (player_id field)

    The result (including None) is cached to avoid redundant API calls.
    """
    if not player_name:
        return None

    name_key = player_name.strip().lower()

    # 1. Check module-level cache (None sentinel is also valid / cached)
    if name_key in _PLAYER_ID_CACHE:
        return _PLAYER_ID_CACHE[name_key]

    # 2. Try to resolve via API-NBA player data
    player_id: int | None = None
    try:
        players = fetch_player_stats()
        for p in players:
            candidate = _safe_str(p.get("name")).strip().lower()
            raw_id = p.get("player_id")
            if raw_id:
                try:
                    _PLAYER_ID_CACHE[candidate] = int(raw_id)
                except (TypeError, ValueError):
                    _PLAYER_ID_CACHE[candidate] = None

        # Retrieve the just-populated cache entry
        player_id = _PLAYER_ID_CACHE.get(name_key)

    except Exception as exc:
        _logger.warning("lookup_player_id failed for '%s': %s", player_name, exc)

    # Cache the result (even if None) to prevent repeated failed lookups
    _PLAYER_ID_CACHE[name_key] = player_id
    return player_id


def fetch_player_game_log(player_id, last_n_games: int = 20) -> list:
    """
    Fetch the last N game logs for a specific player from API-NBA.

    Args:
        player_id (int or str): The NBA player's unique ID.
        last_n_games (int): How many recent games to return (default: 20).

    Returns:
        list of dict: Recent game stats, newest game first.
                      Each dict has: game_date, matchup, win_loss, minutes,
                      pts, reb, ast, stl, blk, tov, fg3m, ft_pct.
                      Returns empty list if the fetch fails.
    """
    api_key = _resolve_api_key()
    if not api_key:
        _logger.warning("API-NBA key not configured — cannot fetch player game log.")
        return []

    url = f"{_BASE_URL}/players/statistics"
    params = {"player": player_id, "league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
    # Use _build_cache_key so the outer cache key matches the one
    # _fetch_with_retry uses internally — avoids duplicate cache entries.
    cache_key = _build_cache_key(url, params)

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _fetch_with_retry(url, params=params)
        if not data:
            _PLAYER_ID_CACHE[str(player_id)] = None
            return []

        games = []
        for g in (data if isinstance(data, list) else (data.get("response") or data.get("games") or data.get("data") or [])):
            if not isinstance(g, dict):
                continue
            games.append({
                "game_date": _safe_str(g.get("date", g.get("game_date", ""))),
                "matchup": _safe_str(g.get("matchup", g.get("opponent", ""))),
                "win_loss": _safe_str(g.get("result", g.get("win_loss", g.get("wl", "")))),
                "minutes": _safe_float(g.get("minutes", g.get("min", 0))),
                "pts": _safe_float(g.get("points", g.get("pts", 0))),
                "reb": _safe_float(g.get("rebounds", g.get("reb", 0))),
                "ast": _safe_float(g.get("assists", g.get("ast", 0))),
                "stl": _safe_float(g.get("steals", g.get("stl", 0))),
                "blk": _safe_float(g.get("blocks", g.get("blk", 0))),
                "tov": _safe_float(g.get("turnovers", g.get("tov", 0))),
                "fg3m": _safe_float(g.get("threes_made", g.get("fg3m", 0))),
                "ft_pct": _safe_float(g.get("ft_pct", g.get("free_throw_pct", 0))),
            })

        result = games[:last_n_games]
        _cache_set(cache_key, result)
        return result

    except Exception as exc:
        _logger.warning("fetch_player_game_log failed for player_id=%s: %s", player_id, exc)
        return []


def fetch_standings() -> list[dict]:
    """
    Fetch current NBA standings from API-NBA.

    Returns a list of team standing entries including conference rank,
    win-loss record, home/away splits, last-10 record, and streak.
    Falls back to an empty list if the API is unavailable.
    """
    api_key = _resolve_api_key()
    if not api_key:
        _logger.debug("fetch_standings: no API-NBA key — returning []")
        return []

    url = f"{_BASE_URL}/standings"
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
    # Use _build_cache_key so the outer cache key matches the one
    # _fetch_with_retry uses internally — avoids duplicate cache entries.
    cache_key = _build_cache_key(url, params)

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _fetch_with_retry(url, params=params)
        if not data:
            return []

        rows_raw = (
            data if isinstance(data, list)
            else (data.get("response") or data.get("standings") or data.get("data") or [])
        )

        # ── Flatten nested groups (API-Basketball v1) ─────────────────
        # /standings may return [[{team1}, ...], [{team3}, ...]] per conference
        flat_rows: list = []
        for item in rows_raw:
            if isinstance(item, list):
                flat_rows.extend(item)
            elif isinstance(item, dict):
                flat_rows.append(item)
        if flat_rows:
            rows_raw = flat_rows

        standings = []
        for row in rows_raw:
            if not isinstance(row, dict):
                continue

            # ── Resolve team abbreviation ─────────────────────────────
            abbrev = _safe_str(
                row.get("teamAbbreviation", row.get("team_abbreviation",
                row.get("abbreviation", "")))
            ).upper().strip()

            # API-Basketball v1: team info nested under "team" key
            if not abbrev:
                team_obj = row.get("team")
                if isinstance(team_obj, dict):
                    abbrev = _safe_str(
                        team_obj.get("abbreviation") or team_obj.get("tricode")
                    ).upper().strip()
                    if not abbrev:
                        abbrev = _team_name_to_abbrev(
                            _safe_str(team_obj.get("name"))
                        ).upper()
                elif isinstance(team_obj, str):
                    abbrev = team_obj.upper().strip()

            if not abbrev:
                continue

            def _wl(field, default=0):
                raw_val = row.get(field, default)
                try:
                    return int(float(str(raw_val))) if raw_val is not None else default
                except (ValueError, TypeError):
                    return default

            # ── Extract win/loss from flat or nested structures ────────
            # API-Basketball v1 nests: {"games": {"win": {"total": N}, "lose": {"total": N}}}
            games_obj = row.get("games")
            if isinstance(games_obj, dict):
                win_obj = games_obj.get("win") or {}
                lose_obj = games_obj.get("lose") or {}
                w = int(_safe_float(win_obj.get("total", 0)))
                l = int(_safe_float(lose_obj.get("total", 0)))
            else:
                w  = _wl("wins",  _wl("W", 0))
                l  = _wl("losses", _wl("L", 0))

            hw = _wl("homeWins",  _wl("home_wins", 0))
            hl = _wl("homeLosses", _wl("home_losses", 0))
            aw = _wl("awayWins",  _wl("away_wins", 0))
            al = _wl("awayLosses", _wl("away_losses", 0))
            l10w = _wl("last10Wins",   _wl("last_10_wins", 0))
            l10l = _wl("last10Losses", _wl("last_10_losses", 0))
            total = w + l
            win_pct = round(w / total, 3) if total else 0.0

            # ── Conference ────────────────────────────────────────────
            conference = _safe_str(row.get("conference", row.get("conf", "")))
            if not conference:
                group_obj = row.get("group")
                if isinstance(group_obj, dict):
                    group_name = _safe_str(group_obj.get("name", "")).lower()
                    if "east" in group_name:
                        conference = "East"
                    elif "west" in group_name:
                        conference = "West"

            # ── Streak / form ─────────────────────────────────────────
            streak = _safe_str(row.get("streak", ""))
            if not streak:
                form = _safe_str(row.get("form", ""))
                if form:
                    # API-Basketball v1 "form" is e.g. "WWLWW" — derive streak
                    last_char = form[-1] if form else ""
                    run = 0
                    for ch in reversed(form):
                        if ch == last_char:
                            run += 1
                        else:
                            break
                    streak = f"{last_char}{run}" if last_char else ""

            standings.append({
                "team_abbreviation": abbrev,
                "conference": conference,
                "conference_rank": _wl("conferenceRank", _wl("rank", _wl("position", 0))),
                "wins": w,
                "losses": l,
                "win_pct": win_pct,
                "home_wins": hw,
                "home_losses": hl,
                "away_wins": aw,
                "away_losses": al,
                "last_10_wins": l10w,
                "last_10_losses": l10l,
                "streak": streak,
                "games_back": _safe_float(row.get("gamesBack", row.get("games_back", 0.0))),
            })

        _cache_set(cache_key, standings)
        _logger.info("fetch_standings: %d teams returned.", len(standings))
        return standings

    except Exception as exc:
        _logger.warning("fetch_standings failed: %s", exc)
        return []


def fetch_news(limit: int = 20) -> list[dict]:
    """
    Fetch recent NBA player/team news from API-NBA.

    Useful for Joseph M. Smith's contextual commentary and for
    surfacing injury updates, trade news, and performance notes.

    Args:
        limit: Maximum number of news items to return (default: 20).

    Returns:
        list[dict]: News items, each with (at minimum):
            {
                "title": str,
                "body": str,
                "player_name": str,     # Empty if team-level news
                "team_abbreviation": str,
                "published_at": str,    # ISO datetime
                "category": str,        # "injury", "trade", "performance", etc.
                "impact": str,          # "high", "medium", "low" or empty
            }
    """
    api_key = _resolve_api_key()
    if not api_key:
        _logger.debug("fetch_news: no API-NBA key — returning []")
        return []

    url = f"{_BASE_URL}/news"
    params = {"limit": limit}
    # Use _build_cache_key so the outer cache key matches the one
    # _fetch_with_retry uses internally — avoids duplicate cache entries.
    cache_key = _build_cache_key(url, params)

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _fetch_with_retry(url, params=params)
        if not data:
            return []

        items_raw = (
            data if isinstance(data, list)
            else (data.get("response") or data.get("news") or data.get("articles") or data.get("data") or [])
        )

        news = []
        for item in items_raw[:limit]:
            if not isinstance(item, dict):
                continue
            news.append({
                "title":            _safe_str(item.get("title", item.get("headline", ""))),
                "body":             _safe_str(item.get("body", item.get("description", item.get("content", "")))),
                "player_name":      _safe_str(item.get("playerName", item.get("player_name", item.get("player", "")))),
                "team_abbreviation":_safe_str(item.get("teamAbbreviation", item.get("team", ""))).upper(),
                "published_at":     _safe_str(item.get("publishedAt", item.get("published_at", item.get("date", "")))),
                "category":         _safe_str(item.get("category", item.get("type", ""))).lower(),
                "impact":           _safe_str(item.get("impact", item.get("severity", ""))).lower(),
            })

        _cache_set(cache_key, news)
        _logger.info("fetch_news: %d items returned.", len(news))
        return news

    except Exception as exc:
        _logger.warning("fetch_news failed: %s", exc)
        return []


def fetch_season_game_logs_batch(
    player_ids: list,
    last_n_games: int = 30,
) -> dict:
    """
    Batch-fetch game logs for multiple players from API-NBA.

    Fetches each player's game log sequentially with a short pause to
    respect rate limits, then returns a name-keyed dict suitable for
    direct use by the Backtester and the matchup history engine.

    Args:
        player_ids: List of ``(player_name, player_id)`` tuples.
                    ``player_id`` may be an int or string; ``player_name``
                    is used as the dict key in the result.
        last_n_games: How many recent games to fetch per player (default 30).

    Returns:
        dict: ``{player_name: [game_log_dict, ...]}``
              Empty inner list when a player's fetch fails.
              Returns ``{}`` when the API key is not configured.
    """
    api_key = _resolve_api_key()
    if not api_key:
        _logger.debug("fetch_season_game_logs_batch: no API key — returning {}")
        return {}

    result: dict = {}
    for player_name, player_id in (player_ids or []):
        if not player_id:
            result[player_name] = []
            continue
        try:
            logs = fetch_player_game_log(player_id, last_n_games=last_n_games)
            result[player_name] = logs
            # Small pause to respect rate limits (same as odds_api_client pattern)
            time.sleep(0.15)
        except Exception as exc:
            _logger.debug(
                "fetch_season_game_logs_batch: failed for %s (id=%s): %s",
                player_name, player_id, exc,
            )
            result[player_name] = []

    _logger.info(
        "fetch_season_game_logs_batch: fetched logs for %d player(s).",
        sum(1 for v in result.values() if v),
    )
    return result


# ── API Key Management ────────────────────────────────────────────────────────

def fetch_api_key_info() -> dict:
    """
    Retrieve information about the current API key.

    Endpoint: GET /status

    Returns:
        dict: API key info with keys:
            credits_remaining, credits_total, is_active, plan, email
        Returns {} on failure.
    """
    url = f"{_BASE_URL}/status"

    try:
        raw = _fetch_with_retry(url)
        if not raw or not isinstance(raw, dict):
            return {}

        # API-Sports wraps status in {"response": {...}} envelope
        response = raw.get("response") or raw

        # Parse the API-Sports status response format:
        # {"account": {"firstname": ..., "email": ...},
        #  "subscription": {"plan": ..., "end": ...},
        #  "requests": {"current": N, "limit_day": N}}
        account = response.get("account") or {}
        subscription = response.get("subscription") or {}
        requests_info = response.get("requests") or {}

        current = requests_info.get("current", 0)
        limit_day = requests_info.get("limit_day", 0)
        try:
            remaining = int(limit_day) - int(current)
        except (TypeError, ValueError):
            remaining = None

        return {
            "credits_remaining": remaining,
            "credits_total":     limit_day,
            "is_active":         bool(subscription.get("plan")),
            "plan":              subscription.get("plan", ""),
            "email":             account.get("email", ""),
        }

    except Exception as exc:
        _logger.warning("fetch_api_key_info failed: %s", exc)
        return {}


def fetch_api_key_usage(limit: int = 50, offset: int = 0) -> list[dict]:
    """
    Retrieve usage history for the current API key.

    API-Sports does not have a dedicated usage-history endpoint;
    this fetches the ``/status`` response and returns a single-item
    list with the current day's usage for callers that expect a list.

    Endpoint: GET /status

    Args:
        limit:  Accepted for API compatibility (unused).
        offset: Accepted for API compatibility (unused).

    Returns:
        list[dict]: A single-item list with keys:
            endpoint, current, limit_day, timestamp
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/status"

    try:
        raw = _fetch_with_retry(url)
        if not raw or not isinstance(raw, dict):
            return []

        response = raw.get("response") or raw
        requests_info = response.get("requests") or {}
        current = requests_info.get("current", 0)
        limit_day = requests_info.get("limit_day", 0)

        return [{
            "endpoint":  "/status",
            "current":   current,
            "limit_day": limit_day,
            "timestamp": _today_str(),
        }]

    except Exception as exc:
        _logger.warning("fetch_api_key_usage failed: %s", exc)
        return []


def fetch_api_key_stats(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    Get aggregated usage statistics for the current API key.

    API-Sports does not have a dedicated stats endpoint;
    this fetches ``/status`` and returns the account/subscription/
    requests information as a stats dict.

    Endpoint: GET /status

    Args:
        start_date: Accepted for API compatibility (unused).
        end_date:   Accepted for API compatibility (unused).

    Returns:
        dict: Aggregated usage statistics with keys:
            current, limit_day, plan, is_active, email,
            start_date, end_date
        Returns {} on failure.
    """
    url = f"{_BASE_URL}/status"

    try:
        raw = _fetch_with_retry(url)
        if not raw or not isinstance(raw, dict):
            return {}

        response = raw.get("response") or raw
        account = response.get("account") or {}
        subscription = response.get("subscription") or {}
        requests_info = response.get("requests") or {}

        return {
            "current":    requests_info.get("current", 0),
            "limit_day":  requests_info.get("limit_day", 0),
            "plan":       subscription.get("plan", ""),
            "is_active":  bool(subscription.get("plan")),
            "email":      account.get("email", ""),
            "start_date": start_date or "",
            "end_date":   end_date or "",
        }

    except Exception as exc:
        _logger.warning("fetch_api_key_stats failed: %s", exc)
        return {}


# ── Additional NBA Endpoints ──────────────────────────────────────────────────

def fetch_team_by_id(team_id) -> dict:
    """
    Retrieve a specific NBA team by its ID.

    Endpoint: GET /teams?id={team_id}

    Args:
        team_id: The team ID (int or str).

    Returns:
        dict: Team details.
        Returns {} on failure.
    """
    url = f"{_BASE_URL}/teams"
    params = {"id": team_id}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw or not isinstance(raw, dict):
            return {}
        # API-Sports wraps responses in "response" key
        response = raw.get("response")
        if isinstance(response, list) and response:
            return response[0] if isinstance(response[0], dict) else {}
        if isinstance(response, dict):
            return response
        return raw

    except Exception as exc:
        _logger.warning("fetch_team_by_id failed for team_id=%s: %s", team_id, exc)
        return {}


def fetch_game_odds(game_id=None) -> list[dict]:
    """
    Retrieve betting odds for NBA games.

    Endpoint: GET /odds

    Args:
        game_id: Optional game ID to filter odds for a specific game.

    Returns:
        list[dict]: Game odds entries.
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/odds"
    params: dict = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
    if game_id is not None:
        params["game"] = game_id

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        odds_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("odds") or raw.get("data") or [])
        if not isinstance(odds_raw, list):
            _logger.warning("fetch_game_odds: unexpected response shape, returning []")
            return []
        return odds_raw

    except Exception as exc:
        _logger.warning("fetch_game_odds failed: %s", exc)
        return []


def fetch_nba_team_stats(team_id=None, season=None) -> list[dict]:
    """
    Retrieve team statistics for NBA games.

    Endpoint: GET /games/statistics/teams
    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    Args:
        team_id: Optional team ID to filter by.
        season:  Optional season year to filter by.

    Returns:
        list[dict]: Team statistics entries.
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/games/statistics/teams"
    params: dict = {}
    if team_id is not None:
        params["team"] = team_id
    if season is not None:
        params["season"] = season

    try:
        raw = _fetch_with_retry(url, params=params)
        if raw:
            stats_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("stats") or raw.get("data") or [])
            if isinstance(stats_raw, list) and stats_raw:
                return stats_raw
            elif not isinstance(stats_raw, list):
                _logger.warning("fetch_nba_team_stats: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("fetch_nba_team_stats API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_fallback import fetch_nba_team_stats_fallback
        _logger.info("fetch_nba_team_stats: falling back to free NBA.com stats endpoint")
        return fetch_nba_team_stats_fallback(team_id=team_id, season=season)
    except Exception as exc:
        _logger.warning("fetch_nba_team_stats fallback also failed: %s", exc)
        return []


def fetch_nba_player_stats(player_id=None, game_id=None) -> list[dict]:
    """
    Retrieve player statistics for NBA games.

    When *game_id* is provided, uses GET /games/statistics/players to fetch
    in-game player stats.  When only *player_id* is given, uses
    GET /players/statistics for season-level stats.
    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    Args:
        player_id: Optional player ID to filter by.
        game_id:   Optional game ID to filter by.

    Returns:
        list[dict]: Player statistics entries.
        Returns [] on failure.
    """
    if game_id is not None:
        url = f"{_BASE_URL}/games/statistics/players"
        params: dict = {"game": game_id}
    else:
        url = f"{_BASE_URL}/players/statistics"
        params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
        if player_id is not None:
            params["player"] = player_id

    try:
        raw = _fetch_with_retry(url, params=params)
        if raw:
            stats_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("stats") or raw.get("data") or [])
            if isinstance(stats_raw, list) and stats_raw:
                return stats_raw
            elif not isinstance(stats_raw, list):
                _logger.warning("fetch_nba_player_stats: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("fetch_nba_player_stats API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_fallback import fetch_nba_player_stats_fallback
        _logger.info("fetch_nba_player_stats: falling back to free NBA.com stats endpoint")
        return fetch_nba_player_stats_fallback(player_id=player_id, game_id=game_id)
    except Exception as exc:
        _logger.warning("fetch_nba_player_stats fallback also failed: %s", exc)
        return []


def fetch_predictions(game_id=None) -> list[dict]:
    """
    Retrieve AI-powered NBA game predictions.

    Endpoint: GET /predictions

    Args:
        game_id: Optional game ID to filter predictions for a specific game.

    Returns:
        list[dict]: Prediction entries.
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/predictions"
    params: dict = {}
    if game_id is not None:
        params["game"] = game_id

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        predictions_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("predictions") or raw.get("data") or [])
        if not isinstance(predictions_raw, list):
            _logger.warning("fetch_predictions: unexpected response shape, returning []")
            return []
        return predictions_raw

    except Exception as exc:
        _logger.warning("fetch_predictions failed: %s", exc)
        return []
