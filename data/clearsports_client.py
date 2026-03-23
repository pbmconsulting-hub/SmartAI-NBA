"""
data/clearsports_client.py
--------------------------
ClearSports API client for NBA data.

Provides:
  - fetch_games_today()    → today's scheduled games with lines
  - fetch_player_stats()   → season-average player stats with std-dev fields
  - fetch_team_stats()     → team pace / ratings / record
  - fetch_injury_report()  → player injury status keyed by lowercased name
  - fetch_live_scores()    → live / recent game scores
  - fetch_rosters()        → team rosters keyed by team abbreviation
  - lookup_player_id()     → NBA player-ID integer or None

API key resolution (first match wins):
  1. st.session_state["clearsports_api_key"]
  2. st.secrets["CLEARSPORTS_API_KEY"]  (via .streamlit/secrets.toml)
  3. CLEARSPORTS_API_KEY environment variable

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

_BASE_URL = "https://api.clearsportsapi.com/v1"

MAX_API_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 10

# ── Time-based response cache (mirrors platform_fetcher._API_CACHE) ───────────

_API_CACHE: dict = {}
_API_CACHE_TTL: int = int(os.environ.get("API_CACHE_TTL_SECONDS", "300"))

# Module-level player-ID lookup cache: name (str) → player_id (int | None)
_PLAYER_ID_CACHE: dict = {}


def _cache_get(url: str):
    """Return cached payload for *url* if still within TTL, else None."""
    entry = _API_CACHE.get(url)
    if entry is None:
        return None
    payload, ts = entry
    if time.time() - ts > _API_CACHE_TTL:
        del _API_CACHE[url]
        return None
    return payload


def _cache_set(url: str, payload) -> None:
    """Store *payload* in the cache keyed by *url*."""
    _API_CACHE[url] = (payload, time.time())


# ── API key resolution ────────────────────────────────────────────────────────

def _resolve_api_key() -> str | None:
    """Return the ClearSports API key from session state, secrets, or environment."""
    if _ST_AVAILABLE:
        try:
            key = st.session_state.get("clearsports_api_key")
            if key:
                return key
        except Exception:
            pass
        try:
            key = st.secrets.get("CLEARSPORTS_API_KEY")
            if key:
                return key
        except Exception:
            pass
    return os.environ.get("CLEARSPORTS_API_KEY")


# ── HTTP helper with retry / caching ─────────────────────────────────────────

def _fetch_with_retry(url: str, params: dict | None = None) -> dict | list | None:
    """
    GET *url* with exponential-backoff retry and response caching.

    Returns parsed JSON on success, or None if all attempts fail.
    Results are cached for _API_CACHE_TTL seconds.
    """
    if not REQUESTS_AVAILABLE:
        _logger.warning("requests library is not available — cannot call ClearSports API")
        return None

    cached = _cache_get(url)
    if cached is not None:
        return cached

    api_key = _resolve_api_key()
    if not api_key:
        _logger.warning("No ClearSports API key found — skipping request to %s", url)
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
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
                _logger.error("ClearSports API key is invalid or unauthorised (401) for %s", url)
                return None

            if resp.status_code == 404:
                _logger.warning("ClearSports endpoint not found (404): %s", url)
                return None

            if resp.status_code == 422:
                _logger.warning("ClearSports 422 (unsupported request) for %s", url)
                return None

            resp.raise_for_status()

            if not resp.text:
                _logger.warning("Empty response body from %s", url)
                return None

            data = resp.json()
            _cache_set(url, data)
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
    url = f"{_BASE_URL}/nba/games"
    params = {"date": _today_str()}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        games_raw = raw if isinstance(raw, list) else raw.get("games", raw.get("data", []))
        if not isinstance(games_raw, list):
            _logger.warning("fetch_games_today: unexpected response shape, returning []")
            return []

        games: list[dict] = []
        for g in games_raw:
            if not isinstance(g, dict):
                continue
            games.append({
                "game_id":     _safe_str(g.get("game_id") or g.get("id")),
                "home_team":   _safe_str(g.get("home_team") or g.get("home_abbreviation")),
                "away_team":   _safe_str(g.get("away_team") or g.get("away_abbreviation")),
                "home_wins":   int(_safe_float(g.get("home_wins", (g.get("home_record") or {}).get("wins", 0)))),
                "home_losses": int(_safe_float(g.get("home_losses", (g.get("home_record") or {}).get("losses", 0)))),
                "away_wins":   int(_safe_float(g.get("away_wins", (g.get("away_record") or {}).get("wins", 0)))),
                "away_losses": int(_safe_float(g.get("away_losses", (g.get("away_record") or {}).get("losses", 0)))),
                "vegas_spread": _safe_float(g.get("vegas_spread") or g.get("spread", 0)),
                "game_total":  _safe_float(g.get("game_total") or g.get("total", 220)),
            })
        return games

    except Exception as exc:
        _logger.warning("fetch_games_today failed: %s", exc)
        return []


def fetch_player_stats() -> list[dict]:
    """
    Fetch current-season player averages and standard deviations.

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
    url = f"{_BASE_URL}/nba/players"
    params = {"season": "2025"}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        players_raw = raw if isinstance(raw, list) else raw.get("players", raw.get("data", []))
        if not isinstance(players_raw, list):
            _logger.warning("fetch_player_stats: unexpected response shape, returning []")
            return []

        players: list[dict] = []
        for p in players_raw:
            if not isinstance(p, dict):
                continue
            stats = p.get("stats") or p.get("averages") or p  # allow flat or nested shape
            players.append({
                "player_id":     _safe_str(p.get("player_id") or p.get("id")),
                "name":          _safe_str(p.get("name") or p.get("full_name")),
                "team":          _safe_str(p.get("team") or p.get("team_abbreviation")),
                "position":      _safe_str(p.get("position") or p.get("pos")),
                # Averages
                "minutes_avg":   _safe_float(stats.get("minutes") or stats.get("min", 0)),
                "points_avg":    _safe_float(stats.get("points") or stats.get("pts", 0)),
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
        return players

    except Exception as exc:
        _logger.warning("fetch_player_stats failed: %s", exc)
        return []


def fetch_team_stats() -> list[dict]:
    """
    Fetch current-season team pace, ratings, and win/loss record.

    Returns:
        list[dict]: Each dict has keys:
            team_abbreviation, team_name,
            pace, offensive_rating, defensive_rating,
            wins, losses
        Returns [] on failure.
    """
    url = f"{_BASE_URL}/nba/teams"
    params = {"season": "2025"}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        teams_raw = raw if isinstance(raw, list) else raw.get("teams", raw.get("data", []))
        if not isinstance(teams_raw, list):
            _logger.warning("fetch_team_stats: unexpected response shape, returning []")
            return []

        teams: list[dict] = []
        for t in teams_raw:
            if not isinstance(t, dict):
                continue
            stats = t.get("stats") or t.get("advanced") or t
            record = t.get("record") or {}
            teams.append({
                "team_abbreviation":  _safe_str(t.get("abbreviation") or t.get("team_abbreviation")),
                "team_name":          _safe_str(t.get("name") or t.get("team_name")),
                "pace":               _safe_float(stats.get("pace", 0)),
                "offensive_rating":   _safe_float(stats.get("offensive_rating") or stats.get("off_rtg", 0)),
                "defensive_rating":   _safe_float(stats.get("defensive_rating") or stats.get("def_rtg", 0)),
                "wins":               int(_safe_float(t.get("wins") or record.get("wins", 0))),
                "losses":             int(_safe_float(t.get("losses") or record.get("losses", 0))),
            })
        return teams

    except Exception as exc:
        _logger.warning("fetch_team_stats failed: %s", exc)
        return []


def fetch_injury_report() -> dict:
    """
    Fetch the current NBA injury report.

    Returns:
        dict: Keyed by player_name.lower().  Each value is a dict with:
            status       – e.g. "Out", "Questionable", "Day-To-Day"
            injury_note  – short description, e.g. "Knee"
            return_date  – estimated return date string or ""
        Returns {} on failure.
    """
    url = f"{_BASE_URL}/nba/injuries"

    try:
        raw = _fetch_with_retry(url)
        if not raw:
            return {}

        injuries_raw = raw if isinstance(raw, list) else raw.get("injuries", raw.get("data", []))
        if not isinstance(injuries_raw, list):
            _logger.warning("fetch_injury_report: unexpected response shape, returning {}")
            return {}

        report: dict = {}
        for entry in injuries_raw:
            if not isinstance(entry, dict):
                continue
            name = _safe_str(entry.get("player") or entry.get("player_name") or entry.get("name"))
            if not name:
                continue
            report[name.lower()] = {
                "status":      _safe_str(entry.get("status", "Unknown")),
                "injury_note": _safe_str(entry.get("injury") or entry.get("injury_note") or entry.get("description")),
                "return_date": _safe_str(entry.get("return_date") or entry.get("expected_return", "")),
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
    url = f"{_BASE_URL}/nba/scores"
    params = {"date": _today_str()}

    try:
        raw = _fetch_with_retry(url, params=params)
        if not raw:
            return []

        scores_raw = raw if isinstance(raw, list) else raw.get("scores", raw.get("games", raw.get("data", [])))
        if not isinstance(scores_raw, list):
            _logger.warning("fetch_live_scores: unexpected response shape, returning []")
            return []

        scores: list[dict] = []
        for g in scores_raw:
            if not isinstance(g, dict):
                continue
            scores.append({
                "game_id":    _safe_str(g.get("game_id") or g.get("id")),
                "home_team":  _safe_str(g.get("home_team") or g.get("home_abbreviation")),
                "away_team":  _safe_str(g.get("away_team") or g.get("away_abbreviation")),
                "home_score": int(_safe_float(g.get("home_score", 0))),
                "away_score": int(_safe_float(g.get("away_score", 0))),
                "period":     _safe_str(g.get("period") or g.get("quarter", "")),
                "game_clock": _safe_str(g.get("game_clock") or g.get("clock", "")),
                "status":     _safe_str(g.get("status", "")),
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
        url = f"{_BASE_URL}/nba/rosters"
        params = {"team": abbrev}

        try:
            raw = _fetch_with_retry(url, params=params)
            if not raw:
                continue

            roster_raw = (
                raw if isinstance(raw, list)
                else raw.get("roster", raw.get("players", raw.get("data", [])))
            )
            if not isinstance(roster_raw, list):
                _logger.warning("fetch_rosters: unexpected shape for team %s", abbrev)
                continue

            names: list[str] = []
            for player in roster_raw:
                if isinstance(player, str):
                    names.append(player)
                elif isinstance(player, dict):
                    name = _safe_str(
                        player.get("name") or player.get("full_name") or player.get("player_name")
                    )
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
      2. ClearSports /nba/players endpoint (player_id field)

    The result (including None) is cached to avoid redundant API calls.
    """
    if not player_name:
        return None

    name_key = player_name.strip().lower()

    # 1. Check module-level cache (None sentinel is also valid / cached)
    if name_key in _PLAYER_ID_CACHE:
        return _PLAYER_ID_CACHE[name_key]

    # 2. Try to resolve via ClearSports player data
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
    Fetch the last N game logs for a specific player from ClearSports API.

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
        _logger.warning("ClearSports API key not configured — cannot fetch player game log.")
        return []

    url = f"{_BASE_URL}/nba/players/{player_id}/game_log"
    params = {"last_n": last_n_games}
    cache_key = f"{url}?player_id={player_id}&last_n={last_n_games}"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _fetch_with_retry(url, params=params)
        if not data:
            _PLAYER_ID_CACHE[str(player_id)] = None
            return []

        games = []
        for g in (data if isinstance(data, list) else data.get("games", data.get("data", []))):
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
    Fetch current NBA standings from ClearSports API.

    Returns a list of team standing entries including conference rank,
    win-loss record, home/away splits, last-10 record, and streak.
    Falls back to an empty list if the API is unavailable.

    Returns:
        list[dict]: Each entry has (at minimum):
            {
                "team_abbreviation": str,
                "conference": "East"|"West",
                "conference_rank": int,
                "wins": int,
                "losses": int,
                "win_pct": float,
                "home_wins": int, "home_losses": int,
                "away_wins": int, "away_losses": int,
                "last_10_wins": int, "last_10_losses": int,
                "streak": str,          # e.g. "W3" or "L1"
                "games_back": float,
            }
    """
    api_key = _resolve_api_key()
    if not api_key:
        _logger.debug("fetch_standings: no ClearSports API key — returning []")
        return []

    url = f"{_BASE_URL}/nba/standings"
    params = {}
    cache_key = f"{url}?season=current"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _fetch_with_retry(url, params=params)
        if not data:
            return []

        rows_raw = (
            data if isinstance(data, list)
            else data.get("standings", data.get("data", []))
        )

        standings = []
        for row in rows_raw:
            abbrev = _safe_str(
                row.get("teamAbbreviation", row.get("team_abbreviation",
                row.get("abbreviation", row.get("team", ""))))
            ).upper().strip()

            if not abbrev:
                continue

            def _wl(field, default=0):
                raw = row.get(field, default)
                try:
                    return int(float(str(raw))) if raw is not None else default
                except (ValueError, TypeError):
                    return default

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

            standings.append({
                "team_abbreviation": abbrev,
                "conference": _safe_str(row.get("conference", row.get("conf", ""))),
                "conference_rank": _wl("conferenceRank", _wl("rank", 0)),
                "wins": w,
                "losses": l,
                "win_pct": win_pct,
                "home_wins": hw,
                "home_losses": hl,
                "away_wins": aw,
                "away_losses": al,
                "last_10_wins": l10w,
                "last_10_losses": l10l,
                "streak": _safe_str(row.get("streak", "")),
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
    Fetch recent NBA player/team news from ClearSports API.

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
        _logger.debug("fetch_news: no ClearSports API key — returning []")
        return []

    url = f"{_BASE_URL}/nba/news"
    params = {"limit": limit}
    cache_key = f"{url}?limit={limit}"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = _fetch_with_retry(url, params=params)
        if not data:
            return []

        items_raw = (
            data if isinstance(data, list)
            else data.get("news", data.get("articles", data.get("data", [])))
        )

        news = []
        for item in items_raw[:limit]:
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
    Batch-fetch game logs for multiple players from ClearSports API.

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
