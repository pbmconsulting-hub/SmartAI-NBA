"""
data/nba_api_client.py
--------------------------
API-NBA client for NBA data (via API-Sports).

Provides:
  NBA Data:
  - get_players(team_id=None)            → NBA players with optional team filter
  - get_player_stats()              → season-average player stats with std-dev fields
  - get_live_scores()               → live / recent game scores
  - get_player_id()                → NBA player-ID integer or None
  - get_standings()                 → current NBA standings
  - get_news(limit)                 → recent NBA player/team news

  API Key Management:
  - get_api_key_info()              → current API key info (credits, status)

API key resolution (first match wins):
  1. st.session_state["api_nba_key"]
  2. st.secrets["API_NBA_KEY"]  (via .streamlit/secrets.toml)
  3. API_NBA_KEY environment variable

Caching uses the same TTL-based pattern as sportsbook_service.py.
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

# v2 NBA API base URL — used for /games, /players, /players/statistics,
# and /teams/statistics endpoints.
_PLAYERS_BASE_URL = "https://v2.nba.api-sports.io"

# ── API Endpoints ─────────────────────────────────────────────────────────────
# Centralized endpoint constants.
# ENDPOINT_GAMES, ENDPOINT_PLAYERS, ENDPOINT_PLAYER_STATS, and
# ENDPOINT_TEAM_STATS use the v2 NBA API (_PLAYERS_BASE_URL).
# The remaining endpoints use the v1 API-Basketball API (_BASE_URL).
ENDPOINT_TEAMS = "/teams"
ENDPOINT_GAMES = "/games"
ENDPOINT_PLAYERS = "/players"
ENDPOINT_PLAYER_STATS = "/players/statistics"
ENDPOINT_TEAM_STATS = "/teams/statistics"
ENDPOINT_INJURIES = "/injuries"
ENDPOINT_STANDINGS = "/standings"
ENDPOINT_ODDS = "/odds"
ENDPOINT_NEWS = "/news"
ENDPOINT_STATUS = "/status"
ENDPOINT_PREDICTIONS = "/predictions"

# Current NBA season (API-Basketball v1 uses "YYYY-YYYY" format).
_CURRENT_SEASON = "2025-2026"

# Season year for v2 NBA API (uses single-year format, e.g. "2025").
_CURRENT_SEASON_YEAR = _CURRENT_SEASON.split("-")[0]

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

# ── Time-based response cache (mirrors sportsbook_service._API_CACHE) ───────────

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


# ── API key resolution ────────────────────────────────────────────────────────

def validate_nba_api_key(key: str | None) -> tuple[bool, str]:
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
    """Return the API-NBA key from session state, secrets, or environment.

    All key sources are ``.strip()``-ed to tolerate whitespace from
    copy-paste or mis-configured environment variables.
    """
    if _ST_AVAILABLE:
        try:
            key = st.session_state.get("api_nba_key")
            if key and isinstance(key, str) and key.strip():
                return key.strip()
        except Exception:
            pass
        try:
            key = st.secrets.get("API_NBA_KEY")
            if key and isinstance(key, str) and key.strip():
                return key.strip()
        except Exception:
            pass
    env_key = os.environ.get("API_NBA_KEY")
    if env_key and isinstance(env_key, str) and env_key.strip():
        return env_key.strip()
    return None


# ── HTTP helper with retry / caching ─────────────────────────────────────────

def _build_cache_key(url: str, params: dict | None = None) -> str:
    """Build a cache key from *url* and optional *params*."""
    if not params:
        return url
    sorted_items = sorted(params.items())
    qs = "&".join(f"{k}={v}" for k, v in sorted_items)
    return f"{url}?{qs}"


def _request_with_retry(url: str, params: dict | None = None) -> dict | list | None:
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
            _req_start = time.monotonic()
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _req_ms = round((time.monotonic() - _req_start) * 1000, 1)

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_API_RETRIES:
                    delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)
                    # Honor Retry-After header when present (HTTP 429)
                    if resp.status_code == 429:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = max(delay, min(float(retry_after), 60.0))
                            except (ValueError, TypeError):
                                pass
                            _logger.warning(
                                "HTTP 429 rate limited — Retry-After: %s, waiting %.1fs",
                                retry_after, delay,
                            )
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
            _logger.debug(
                "API request: endpoint=%s, status=%d, duration_ms=%.1f",
                url.replace(_BASE_URL, "").replace(_PLAYERS_BASE_URL, ""),
                resp.status_code, _req_ms,
            )
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

def _parse_minutes(value, default: float = 0.0) -> float:
    """Parse a minutes value that may be in ``"MM:SS"`` format.

    The v2 NBA API returns minutes as strings like ``"21:56"`` (21 min 56 sec).
    This helper converts to a decimal float (e.g. 21.93).  Plain numeric
    values are passed through via :func:`_safe_float`.
    """
    if isinstance(value, str) and ":" in value:
        try:
            parts = value.split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        except (ValueError, IndexError):
            return default
    return _safe_float(value, default)


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

def get_players(
    team_id=None,
    player_id=None,
    name: str | None = None,
    country: str | None = None,
    search: str | None = None,
    season: int | str | None = None,
) -> list[dict]:
    """
    Retrieve NBA players.

    Endpoint: GET /players  (v2 NBA API — v2.nba.api-sports.io)
    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    All query parameters supported by the v2 NBA API are accepted:
        player_id: Unique player ID (persists across all seasons).
        name:      Exact player name filter (e.g. ``name="James"``).
        team_id:   Numeric team ID to filter by.
        season:    4-digit season year (e.g. ``2025``).  Defaults to the
                   current season unless *player_id* is given (IDs are
                   unique across seasons, so season is optional then).
        country:   Country filter (e.g. ``"USA"``).
        search:    Partial name search (>= 3 characters, e.g. ``"Jame"``).

    Returns:
        list[dict]: Player entries.
        Returns [] on failure.
    """
    url = f"{_PLAYERS_BASE_URL}{ENDPOINT_PLAYERS}"
    params: dict = {}

    if player_id is not None:
        params["id"] = int(player_id)
    if name is not None:
        params["name"] = name
    if team_id is not None:
        params["team"] = int(team_id)
    if country is not None:
        params["country"] = country
    if search is not None:
        params["search"] = search

    # Season defaults to current year unless a player_id lookup is
    # requested (player IDs are unique across all seasons).
    if season is not None:
        params["season"] = int(season)
    elif player_id is None:
        params["season"] = int(_CURRENT_SEASON_YEAR)

    try:
        raw = _request_with_retry(url, params=params)
        if raw:
            players_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("players") or raw.get("data") or [])
            if isinstance(players_raw, list):
                result = [p for p in players_raw if isinstance(p, dict)]
                if result:
                    return result
            else:
                _logger.warning("get_players: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("get_players API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_backup import get_players_backup
        _logger.info("get_players: falling back to free NBA.com stats endpoint")
        return get_players_backup(team_id=team_id)
    except Exception as exc:
        _logger.warning("get_players fallback also failed: %s", exc)
        return []


def get_player_stats() -> list[dict]:
    """
    Get current-season player averages and standard deviations.

    Endpoint: GET /players/statistics  (v2 NBA API — v2.nba.api-sports.io)
    Fallback: free NBA.com stats endpoint when API-NBA is unavailable.

    The v2 endpoint returns per-game stat rows.  When multiple games are
    returned for the same player we aggregate them into averages and
    standard deviations.

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
    url = f"{_PLAYERS_BASE_URL}{ENDPOINT_PLAYER_STATS}"
    params = {"season": int(_CURRENT_SEASON_YEAR)}

    try:
        raw = _request_with_retry(url, params=params)
        if raw:
            stats_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("data") or [])
            if isinstance(stats_raw, list) and stats_raw:
                result = _aggregate_player_stats(stats_raw)
                if result:
                    return result
            elif not isinstance(stats_raw, list):
                _logger.warning("get_player_stats: unexpected response shape from API-NBA")
    except Exception as exc:
        _logger.warning("get_player_stats API-NBA failed: %s", exc)

    # ── Fallback: free NBA.com stats ──────────────────────────────────────
    try:
        from data.nba_stats_backup import get_player_stats_backup
        _logger.info("get_player_stats: falling back to free NBA.com stats endpoint")
        return get_player_stats_backup()
    except Exception as exc:
        _logger.warning("get_player_stats fallback also failed: %s", exc)
        return []


def _aggregate_player_stats(stats_raw: list) -> list[dict]:
    """Aggregate per-game v2 stat rows into per-player averages/std.

    If the data is already one-row-per-player (no ``game`` field) the
    rows are mapped directly without aggregation.
    """
    import statistics as _stats_mod

    # ── Stat keys we track (v2 field name → output field) ─────────────
    _STAT_FIELDS = {
        "points":    "points",
        "totReb":    "rebounds",
        "assists":   "assists",
        "tpm":       "threes",
        "steals":    "steals",
        "blocks":    "blocks",
        "turnovers": "turnovers",
    }

    # Collect per-player game rows
    per_player: dict[str, dict] = {}   # pid → {"meta": {...}, "games": [...]}
    for entry in stats_raw:
        if not isinstance(entry, dict):
            continue

        # ── Resolve player info ───────────────────────────────────
        player_obj = entry.get("player")
        if isinstance(player_obj, dict):
            pid = _safe_str(player_obj.get("id"))
            name = _safe_str(player_obj.get("name"))
            if not name:
                name = f"{_safe_str(player_obj.get('firstname'))} {_safe_str(player_obj.get('lastname'))}".strip()
        else:
            pid = _safe_str(entry.get("player_id") or entry.get("id"))
            name = _safe_str(entry.get("name") or entry.get("player_name"))

        if not pid:
            continue

        # ── Resolve team abbreviation ─────────────────────────────
        team_obj = entry.get("team")
        if isinstance(team_obj, dict):
            team_abbrev = _safe_str(
                team_obj.get("code")
                or team_obj.get("abbreviation")
                or team_obj.get("tricode")
            )
            if not team_abbrev:
                team_abbrev = _team_name_to_abbrev(_safe_str(team_obj.get("name")))
        else:
            team_abbrev = _safe_str(team_obj)

        # ── Resolve position ──────────────────────────────────────
        pos = _safe_str(entry.get("pos") or entry.get("position"))

        # ── Collect stat values ───────────────────────────────────
        game_row: dict[str, float] = {}
        game_row["minutes"] = _parse_minutes(entry.get("min") or entry.get("minutes", 0))
        for v2_key, out_key in _STAT_FIELDS.items():
            game_row[out_key] = _safe_float(
                entry.get(v2_key)
                or entry.get(out_key)
                or entry.get({"rebounds": "reb", "threes": "fg3m", "turnovers": "tov"}.get(out_key, ""), 0)
            )
        game_row["ft_pct"] = _safe_float(entry.get("ftp") or entry.get("ft_pct") or entry.get("ftm_pct", 0))
        game_row["usage_rate"] = _safe_float(entry.get("usage_rate") or entry.get("usg_pct", 0))

        if pid not in per_player:
            per_player[pid] = {"meta": {"pid": pid, "name": name, "team": team_abbrev, "pos": pos}, "games": []}
        per_player[pid]["games"].append(game_row)

    # ── Build aggregated output ───────────────────────────────────────
    players: list[dict] = []
    _avg_keys = ["minutes", "points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"]
    for pid, info in per_player.items():
        meta = info["meta"]
        games = info["games"]
        n = len(games)

        row: dict = {
            "player_id": meta["pid"],
            "name":      meta["name"],
            "team":      meta["team"],
            "position":  meta["pos"],
        }

        for key in _avg_keys:
            vals = [g[key] for g in games]
            avg = sum(vals) / n if n else 0.0
            row[f"{key}_avg"] = round(avg, 2)
            if n >= 2:
                row[f"{key}_std"] = round(_stats_mod.stdev(vals), 2)
            else:
                row[f"{key}_std"] = 0.0

        # ft_pct and usage_rate are not std-tracked
        ft_vals = [g["ft_pct"] for g in games]
        row["ft_pct"] = round(sum(ft_vals) / n, 2) if n else 0.0
        usage_vals = [g["usage_rate"] for g in games]
        row["usage_rate"] = round(sum(usage_vals) / n, 2) if n else 0.0

        # minutes_std is not part of the output schema
        row.pop("minutes_std", None)

        players.append(row)

    if players:
        _logger.info("get_player_stats: aggregated %d player(s) from v2 /players/statistics", len(players))
    return players


def get_live_scores() -> list[dict]:
    """
    Get live / recently completed NBA game scores.

    Endpoint: GET /games  (v2 NBA API — v2.nba.api-sports.io)

    Returns:
        list[dict]: Each dict has keys:
            game_id, home_team, away_team,
            home_score, away_score,
            period, game_clock, status
        Returns [] on failure.
    """
    url = f"{_PLAYERS_BASE_URL}{ENDPOINT_GAMES}"
    params = {"season": int(_CURRENT_SEASON_YEAR), "date": _today_str()}

    try:
        raw = _request_with_retry(url, params=params)
        if not raw:
            return []

        scores_raw = raw if isinstance(raw, list) else (raw.get("response") or raw.get("scores") or raw.get("games") or raw.get("data") or [])
        if not isinstance(scores_raw, list):
            _logger.warning("get_live_scores: unexpected response shape, returning []")
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
        _logger.warning("get_live_scores failed: %s", exc)
        return []


def get_player_id(player_name: str) -> int | None:
    """
    Return the NBA integer player ID for *player_name*, or None if not found.

    Lookup order:
      1. Module-level _PLAYER_ID_CACHE (name → id)
      2. Targeted v2 NBA API ``/players?search=`` query (>= 3-char substring)
      3. Broad ``get_player_stats()`` scan (full roster, last resort)

    The result (including None) is cached to avoid redundant API calls.
    Player IDs are unique across all seasons.
    """
    if not player_name:
        return None

    name_key = player_name.strip().lower()

    # 1. Check module-level cache (None sentinel is also valid / cached)
    if name_key in _PLAYER_ID_CACHE:
        return _PLAYER_ID_CACHE[name_key]

    # 2. Try a targeted search via the v2 NBA API /players?search= param
    player_id: int | None = None
    try:
        # Use the last name (or the full name if single-word) as the search
        # term — the API requires >= 3 characters.
        search_term = player_name.strip().split()[-1] if player_name.strip() else ""
        if len(search_term) >= 3:
            candidates = get_players(search=search_term)
            for p in candidates:
                first = _safe_str(p.get("firstname") or p.get("first_name") or "")
                last = _safe_str(p.get("lastname") or p.get("last_name") or "")
                full = f"{first} {last}".strip().lower()
                # Also accept a pre-combined "name" field
                alt = _safe_str(p.get("name") or p.get("full_name") or "").strip().lower()
                raw_id = p.get("id") or p.get("player_id")
                if raw_id is not None:
                    try:
                        int_id = int(raw_id)
                    except (TypeError, ValueError):
                        continue
                    if full:
                        _PLAYER_ID_CACHE[full] = int_id
                    if alt:
                        _PLAYER_ID_CACHE[alt] = int_id

            player_id = _PLAYER_ID_CACHE.get(name_key)
    except Exception as exc:
        _logger.warning("get_player_id targeted search failed for '%s': %s", player_name, exc)

    # 3. Fall back to broad player-stats scan if targeted search missed
    if player_id is None and name_key not in _PLAYER_ID_CACHE:
        try:
            players = get_player_stats()
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
            _logger.warning("get_player_id fallback scan failed for '%s': %s", player_name, exc)

    # Cache the result (even if None) to prevent repeated failed lookups
    _PLAYER_ID_CACHE[name_key] = player_id
    return player_id


def get_standings() -> list[dict]:
    """
    Get current NBA standings from API-NBA.

    Returns a list of team standing entries including conference rank,
    win-loss record, home/away splits, last-10 record, and streak.
    Falls back to an empty list if the API is unavailable.
    """
    api_key = _resolve_api_key()
    if not api_key:
        _logger.debug("get_standings: no API-NBA key — returning []")
        return []

    url = f"{_BASE_URL}{ENDPOINT_STANDINGS}"
    params = {"league": _NBA_LEAGUE_ID, "season": _CURRENT_SEASON}
    # Use _build_cache_key so the outer cache key matches the one
    # _request_with_retry uses internally — avoids duplicate cache entries.
    cache_key = _build_cache_key(url, params)

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _request_with_retry(url, params=params)
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
                    if last_char in ("W", "L"):
                        run = 0
                        for ch in reversed(form):
                            if ch == last_char:
                                run += 1
                            else:
                                break
                        streak = f"{last_char}{run}"

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
        _logger.info("get_standings: %d teams returned.", len(standings))
        return standings

    except Exception as exc:
        _logger.warning("get_standings failed: %s", exc)
        return []


def get_news(limit: int = 20) -> list[dict]:
    """
    Get recent NBA player/team news from API-NBA.

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
        _logger.debug("get_news: no API-NBA key — returning []")
        return []

    url = f"{_BASE_URL}{ENDPOINT_NEWS}"
    params = {"limit": limit}
    # Use _build_cache_key so the outer cache key matches the one
    # _request_with_retry uses internally — avoids duplicate cache entries.
    cache_key = _build_cache_key(url, params)

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _request_with_retry(url, params=params)
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
        _logger.info("get_news: %d items returned.", len(news))
        return news

    except Exception as exc:
        _logger.warning("get_news failed: %s", exc)
        return []


# ── API Key Management ────────────────────────────────────────────────────────

def get_api_key_info() -> dict:
    """
    Retrieve information about the current API key.

    Endpoint: GET /status

    Returns:
        dict: API key info with keys:
            credits_remaining, credits_total, is_active, plan, email
        Returns {} on failure.
    """
    url = f"{_BASE_URL}{ENDPOINT_STATUS}"

    try:
        raw = _request_with_retry(url)
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
        _logger.warning("get_api_key_info failed: %s", exc)
        return {}


