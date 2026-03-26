"""
data/nba_stats_backup.py
--------------------------
Free NBA stats fallback — supplements API-NBA when its
team-stats, players, and player-stats endpoints are unavailable.

Uses the public stats.nba.com endpoints (no API key required).
These endpoints power nba.com itself and are free to query with
the correct HTTP headers.

All public functions return data in the same dict schema that the
corresponding API-NBA functions produce, so callers are unaware
of the data source.
"""

import time

from engine.math_helpers import _safe_float

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

from utils.log_helper import get_logger
_logger = get_logger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

_NBA_STATS_BASE = "https://stats.nba.com/stats"
_REQUEST_TIMEOUT = 45
_MAX_RETRIES = 2

# Headers required by stats.nba.com to accept non-browser requests.
# stats.nba.com is strict about headers; missing or stale values cause
# timeouts or 403 responses.  The set below mimics a modern Chrome browser.
_NBA_STATS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nba.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
    "Accept-Encoding": "gzip, deflate, br",
    "Host": "stats.nba.com",
}

# Cache to avoid hammering the free endpoints.
_cache: dict = {}
_CACHE_TTL = 600  # 10 minutes


# ── Helpers ───────────────────────────────────────────────────────────────────


def _safe_str(value, default: str = "") -> str:
    """Coerce *value* to str, returning *default* on None."""
    if value is None:
        return default
    return str(value)


def _cache_get(key: str):
    """Return cached payload or None if expired / missing."""
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data):
    """Store *data* in the cache under *key*."""
    _cache[key] = {"data": data, "ts": time.time()}


def _current_season_str() -> str:
    """Return the current NBA season in 'YYYY-YY' format (e.g. '2024-25')."""
    import datetime
    now = datetime.date.today()
    # NBA season starts in October; if before October, use previous year
    year = now.year if now.month >= 10 else now.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


def _normalize_season(season) -> str:
    """
    Normalize a season value to NBA.com 'YYYY-YY' format.

    Accepts:
      - None           → current season via ``_current_season_str()``
      - ``"2024-25"``  → returned as-is (already correct)
      - ``"2024"``     → converted to ``"2024-25"``
      - ``2024`` (int) → converted to ``"2024-25"``
    """
    if season is None:
        return _current_season_str()
    s = str(season).strip()
    # Already in YYYY-YY format?
    if "-" in s and len(s) >= 6:
        return s
    # Year-only (e.g. "2024" or 2024) → "2024-25"
    try:
        year = int(s)
        return f"{year}-{str(year + 1)[-2:]}"
    except (ValueError, TypeError):
        return s


def _request_nba_stats(endpoint: str, params: dict) -> dict | None:
    """
    GET an NBA stats endpoint and return the parsed JSON, or None on error.

    The response shape from stats.nba.com is:
      {"resultSets": [{"headers": [...], "rowSet": [[...], ...]}, ...]}

    Retries up to ``_MAX_RETRIES`` times on timeout or 5xx errors with
    exponential back-off (2 s → 4 s).
    """
    if not _REQUESTS_AVAILABLE:
        _logger.debug("requests library unavailable — cannot call NBA stats fallback")
        return None

    url = f"{_NBA_STATS_BASE}/{endpoint}"
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=_NBA_STATS_HEADERS,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
            if resp.status_code >= 500 and attempt < _MAX_RETRIES:
                delay = 2 ** (attempt + 1)
                _logger.warning(
                    "NBA stats fallback: HTTP %d from %s — retrying in %ds (attempt %d/%d)",
                    resp.status_code, endpoint, delay, attempt + 1, _MAX_RETRIES + 1,
                )
                time.sleep(delay)
                continue

            if resp.status_code != 200:
                _logger.warning(
                    "NBA stats fallback: HTTP %d from %s", resp.status_code, endpoint
                )
                return None
            return resp.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                delay = 2 ** (attempt + 1)
                _logger.warning(
                    "NBA stats fallback: %s request attempt %d/%d failed — %s — retrying in %ds",
                    endpoint, attempt + 1, _MAX_RETRIES + 1, exc, delay,
                )
                time.sleep(delay)
                continue
        except Exception as exc:
            _logger.warning("NBA stats fallback: %s request failed — %s", endpoint, exc)
            return None

    _logger.warning("NBA stats fallback: %s request failed — %s", endpoint, last_exc)
    return None


def _rows_to_dicts(result_set: dict) -> list[dict]:
    """
    Convert an NBA stats resultSet (headers + rowSet) into a list of dicts.
    """
    headers = result_set.get("headers") or []
    rows = result_set.get("rowSet") or []
    lower_headers = [h.lower() for h in headers]
    return [dict(zip(lower_headers, row)) for row in rows]


# ── Public fallback functions ─────────────────────────────────────────────────

def get_team_stats_backup(season: str | None = None) -> list[dict]:
    """
    Retrieve team stats from the free NBA.com stats endpoint.

    Returns data in the same schema as API-NBA ``get_team_stats()``:
        team_abbreviation, team_name, pace, offensive_rating,
        defensive_rating, wins, losses
    """
    cache_key = "fallback:team_stats"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    season = _normalize_season(season)
    basic_data = _request_nba_stats("leaguedashteamstats", {
        "Season": season,
        "SeasonType": "Regular Season",
        "MeasureType": "Base",
        "PerMode": "PerGame",
        "LeagueID": "00",
    })
    # LeagueDashTeamStats with MeasureType=Advanced gives pace/ratings
    adv_data = _request_nba_stats("leaguedashteamstats", {
        "Season": season,
        "SeasonType": "Regular Season",
        "MeasureType": "Advanced",
        "PerMode": "PerGame",
        "LeagueID": "00",
    })

    if not basic_data:
        _logger.warning("get_team_stats_backup: no data from NBA stats")
        return []

    try:
        basic_rows = _rows_to_dicts(basic_data["resultSets"][0])
    except (KeyError, IndexError, TypeError):
        _logger.warning("get_team_stats_backup: unexpected basic response shape")
        return []

    # Build advanced lookup by team_id
    adv_lookup: dict = {}
    if adv_data:
        try:
            for row in _rows_to_dicts(adv_data["resultSets"][0]):
                tid = row.get("team_id")
                if tid is not None:
                    adv_lookup[tid] = row
        except (KeyError, IndexError, TypeError):
            _logger.debug("failed to build advanced stats lookup from result sets")

    teams: list[dict] = []
    for row in basic_rows:
        tid = row.get("team_id")
        adv = adv_lookup.get(tid, {})
        teams.append({
            "team_abbreviation": _safe_str(row.get("team_abbreviation")),
            "team_name": _safe_str(row.get("team_name")),
            "pace": _safe_float(adv.get("pace", 0)),
            "offensive_rating": _safe_float(adv.get("off_rating", 0)),
            "defensive_rating": _safe_float(adv.get("def_rating", 0)),
            "wins": int(_safe_float(row.get("w", 0))),
            "losses": int(_safe_float(row.get("l", 0))),
        })

    _cache_set(cache_key, teams)
    _logger.info("get_team_stats_backup: got %d teams from NBA.com stats", len(teams))
    return teams


def get_players_backup(team_id=None, season: str | None = None) -> list[dict]:
    """
    Retrieve NBA players from the free NBA.com stats endpoint.

    Returns data in the same schema as API-NBA ``get_players()``:
        id, name, team_id (optional filtering)
    """
    cache_key = f"fallback:players:{team_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    season = _normalize_season(season)

    data = _request_nba_stats("commonallplayers", {
        "Season": season,
        "LeagueID": "00",
        "IsOnlyCurrentSeason": "1",
    })

    if not data:
        _logger.warning("get_players_backup: no data from NBA stats")
        return []

    try:
        rows = _rows_to_dicts(data["resultSets"][0])
    except (KeyError, IndexError, TypeError):
        _logger.warning("get_players_backup: unexpected response shape")
        return []

    players: list[dict] = []
    for row in rows:
        # Filter by team_id if specified
        if team_id is not None and row.get("team_id") != team_id:
            continue
        display_name = _safe_str(row.get("display_first_last") or row.get("display_last_comma_first"))
        players.append({
            "id": row.get("person_id"),
            "name": display_name,
            "full_name": display_name,
            "team_id": row.get("team_id"),
            "team_abbreviation": _safe_str(row.get("team_abbreviation")),
        })

    _cache_set(cache_key, players)
    _logger.info("get_players_backup: got %d players from NBA.com stats", len(players))
    return players


def get_player_stats_backup(season: str | None = None) -> list[dict]:
    """
    Retrieve player season averages from the free NBA.com stats endpoint.

    Returns data in the same schema as API-NBA ``get_player_stats()``:
        player_id, name, team, position,
        minutes_avg, points_avg, rebounds_avg, assists_avg,
        threes_avg, steals_avg, blocks_avg, turnovers_avg,
        ft_pct, usage_rate,
        points_std, rebounds_std, assists_std, threes_std,
        steals_std, blocks_std, turnovers_std
    """
    cache_key = "fallback:player_stats"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    season = _normalize_season(season)

    data = _request_nba_stats("leaguedashplayerstats", {
        "Season": season,
        "SeasonType": "Regular Season",
        "MeasureType": "Base",
        "PerMode": "PerGame",
        "LeagueID": "00",
    })

    if not data:
        _logger.warning("get_player_stats_backup: no data from NBA stats")
        return []

    try:
        rows = _rows_to_dicts(data["resultSets"][0])
    except (KeyError, IndexError, TypeError):
        _logger.warning("get_player_stats_backup: unexpected response shape")
        return []

    players: list[dict] = []
    for row in rows:
        players.append({
            "player_id": _safe_str(row.get("player_id")),
            "name": _safe_str(row.get("player_name")),
            "team": _safe_str(row.get("team_abbreviation")),
            "position": "",
            "minutes_avg": _safe_float(row.get("min", 0)),
            "points_avg": _safe_float(row.get("pts", 0)),
            "rebounds_avg": _safe_float(row.get("reb", 0)),
            "assists_avg": _safe_float(row.get("ast", 0)),
            "threes_avg": _safe_float(row.get("fg3m", 0)),
            "steals_avg": _safe_float(row.get("stl", 0)),
            "blocks_avg": _safe_float(row.get("blk", 0)),
            "turnovers_avg": _safe_float(row.get("tov", 0)),
            "ft_pct": _safe_float(row.get("ft_pct", 0)),
            "usage_rate": 0.0,
            # std-dev not available from the basic endpoint
            "points_std": 0.0,
            "rebounds_std": 0.0,
            "assists_std": 0.0,
            "threes_std": 0.0,
            "steals_std": 0.0,
            "blocks_std": 0.0,
            "turnovers_std": 0.0,
        })

    _cache_set(cache_key, players)
    _logger.info(
        "get_player_stats_backup: got %d player stat rows from NBA.com stats",
        len(players),
    )
    return players


def get_nba_team_stats_backup(
    team_id=None, season: str | None = None
) -> list[dict]:
    """
    Retrieve per-team statistics from the free NBA.com stats endpoint.

    Returns raw stat rows (same schema as API-NBA ``get_nba_team_stats()``).
    """
    cache_key = f"fallback:nba_team_stats:{team_id}:{season}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    season = _normalize_season(season)

    data = _request_nba_stats("leaguedashteamstats", {
        "Season": season,
        "SeasonType": "Regular Season",
        "MeasureType": "Base",
        "PerMode": "PerGame",
        "LeagueID": "00",
    })

    if not data:
        _logger.warning("get_nba_team_stats_backup: no data from NBA stats")
        return []

    try:
        rows = _rows_to_dicts(data["resultSets"][0])
    except (KeyError, IndexError, TypeError):
        _logger.warning("get_nba_team_stats_backup: unexpected response shape")
        return []

    if team_id is not None:
        rows = [r for r in rows if r.get("team_id") == team_id]

    _cache_set(cache_key, rows)
    _logger.info(
        "get_nba_team_stats_backup: got %d team stat rows from NBA.com stats",
        len(rows),
    )
    return rows


def get_nba_player_stats_backup(
    player_id=None, game_id=None, season: str | None = None
) -> list[dict]:
    """
    Retrieve per-player statistics from the free NBA.com stats endpoint.

    Returns raw stat rows (same schema as API-NBA ``get_nba_player_stats()``).
    """
    cache_key = f"fallback:nba_player_stats:{player_id}:{game_id}:{season}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    season = _normalize_season(season)

    data = _request_nba_stats("leaguedashplayerstats", {
        "Season": season,
        "SeasonType": "Regular Season",
        "MeasureType": "Base",
        "PerMode": "PerGame",
        "LeagueID": "00",
    })

    if not data:
        _logger.warning("get_nba_player_stats_backup: no data from NBA stats")
        return []

    try:
        rows = _rows_to_dicts(data["resultSets"][0])
    except (KeyError, IndexError, TypeError):
        _logger.warning("get_nba_player_stats_backup: unexpected response shape")
        return []

    if player_id is not None:
        rows = [r for r in rows if r.get("player_id") == player_id]

    _cache_set(cache_key, rows)
    _logger.info(
        "get_nba_player_stats_backup: got %d player stat rows from NBA.com stats",
        len(rows),
    )
    return rows

