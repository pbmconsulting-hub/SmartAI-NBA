"""
data/odds_api_client.py
-----------------------
Unified client for The Odds API (https://the-odds-api.com).

Provides:
  - fetch_game_odds(api_key=None)   → list of game-level odds dicts
  - fetch_player_props(api_key=None) → list of prop dicts matching the
                                       platform_fetcher prop format exactly

API key resolution (first match wins):
  1. explicit *api_key* argument
  2. st.session_state["odds_api_key"]
  3. ODDS_API_KEY environment variable

Caching uses the same TTL-based pattern as platform_fetcher.py.
Retry logic applies exponential backoff (1 s → 2 s → 4 s, capped at 10 s).
All public functions degrade gracefully: they return empty lists on failure
and log a warning rather than raising.
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

from data.platform_mappings import normalize_stat_type
from engine.odds_engine import american_odds_to_implied_probability

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_BASE_URL = "https://api.the-odds-api.com/v4"
_SPORT    = "basketball_nba"

MAX_API_RETRIES          = 3
RETRY_BASE_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS  = 15

# Small pause between per-event requests to stay within rate limits
_INTER_REQUEST_DELAY_SECONDS = 0.25

# ── Bookmaker display-name mapping ────────────────────────────────────────────

_BOOKMAKER_DISPLAY: dict[str, str] = {
    "draftkings":      "DraftKings",
    "fanduel":         "FanDuel",
    "betmgm":          "BetMGM",
    "caesars":         "Caesars",
    "pointsbet":       "PointsBet",
    "betrivers":       "BetRivers",
    "williamhill_us":  "William Hill",
    "unibet_us":       "Unibet",
    "betus":           "BetUS",
    "bovada":          "Bovada",
    "mybookieag":      "MyBookie",
    "betonlineag":     "BetOnline",
    "lowvig":          "LowVig",
    "pinnacle":        "Pinnacle",
    "superbook":       "SuperBook",
    "wynnbet":         "WynnBet",
    "twinspires":      "TwinSpires",
    "betfred":         "BetFred",
    "hard_rock_bet":   "Hard Rock Bet",
    "espnbet":         "ESPN Bet",
    "fliff":           "Fliff",
    "fanatics":        "Fanatics",
}

# ── Odds API market key → internal stat key ───────────────────────────────────

_ODDS_API_STAT_MAP: dict[str, str] = {
    "player_points":                  "points",
    "player_rebounds":                "rebounds",
    "player_assists":                 "assists",
    "player_threes":                  "threes",
    "player_blocks":                  "blocks",
    "player_steals":                  "steals",
    "player_turnovers":               "turnovers",
    "player_points_rebounds_assists": "points_rebounds_assists",
    "player_points_rebounds":         "points_rebounds",
    "player_points_assists":          "points_assists",
    "player_rebounds_assists":        "rebounds_assists",
}

# Player prop markets to request from the Odds API
_PROP_MARKETS: list[str] = list(_ODDS_API_STAT_MAP.keys())

# ── Time-based response cache (mirrors platform_fetcher._API_CACHE) ───────────

_API_CACHE: dict = {}
_API_CACHE_TTL: int = int(os.environ.get("API_CACHE_TTL_SECONDS", "300"))


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

def _resolve_api_key(explicit_key: str | None = None) -> str | None:
    """Return the Odds API key, trying (in order): argument → session → env."""
    if explicit_key:
        return explicit_key
    if _ST_AVAILABLE:
        try:
            key = st.session_state.get("odds_api_key")
            if key:
                return key
        except Exception:
            pass
    return os.environ.get("ODDS_API_KEY")


# ── HTTP helper with retry / caching ─────────────────────────────────────────

def _fetch_with_retry(url: str, params: dict | None = None) -> dict | list | None:
    """
    GET *url* with exponential-backoff retry and response caching.

    The API key is appended to *params* automatically if present.
    Returns parsed JSON on success, or None if all attempts fail.
    Results are cached for _API_CACHE_TTL seconds.
    """
    if not REQUESTS_AVAILABLE:
        _logger.warning("requests library is not available — cannot call Odds API")
        return None

    cached = _cache_get(url)
    if cached is not None:
        return cached

    for attempt in range(MAX_API_RETRIES + 1):
        try:
            resp = requests.get(
                url,
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
                _logger.error("Odds API key is invalid or unauthorised (401) for %s", url)
                return None

            if resp.status_code == 422:
                # Unprocessable entity — endpoint/market combo not supported today
                _logger.warning("Odds API 422 (unsupported request) for %s", url)
                return None

            if resp.status_code == 404:
                _logger.warning("Odds API endpoint not found (404): %s", url)
                return None

            resp.raise_for_status()
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


# ── Private helpers ───────────────────────────────────────────────────────────

def _safe_float(value, default: float = 0.0) -> float:
    """Coerce *value* to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bookmaker_display_name(key: str) -> str:
    """Return the human-readable bookmaker name for *key*."""
    return _BOOKMAKER_DISPLAY.get(key.lower(), key.title())


def _normalize_stat(market_key: str) -> str:
    """
    Convert an Odds API market key to our internal stat key.

    Uses the local _ODDS_API_STAT_MAP first, then falls back to
    normalize_stat_type() from platform_mappings.
    """
    if market_key in _ODDS_API_STAT_MAP:
        return _ODDS_API_STAT_MAP[market_key]
    return normalize_stat_type(market_key, "OddsAPI")


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.date.today().isoformat()


def _fetch_events(api_key: str) -> list[dict]:
    """Return all upcoming NBA events from the Odds API."""
    url = f"{_BASE_URL}/sports/{_SPORT}/events"
    params = {
        "apiKey":     api_key,
        "dateFormat": "iso",
    }
    raw = _fetch_with_retry(url, params=params)
    if not isinstance(raw, list):
        _logger.warning("_fetch_events: unexpected response shape")
        return []
    return raw


def _build_team_lookup(events: list[dict]) -> dict[str, str]:
    """
    Build a player-name → team mapping from event home/away team names.

    This is a best-effort lookup; player names are not available at this stage
    so the dict maps team names to their abbreviation for later enrichment.
    Returns a simple home_team/away_team per event_id dict instead.
    """
    lookup: dict[str, dict[str, str]] = {}
    for ev in events:
        eid = ev.get("id", "")
        lookup[eid] = {
            "home_team": ev.get("home_team", ""),
            "away_team": ev.get("away_team", ""),
        }
    return lookup


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_game_odds(api_key: str | None = None) -> list[dict]:
    """
    Fetch NBA game-level odds (moneyline, spread, totals) from The Odds API.

    Args:
        api_key: Optional explicit API key; falls back to session state / env.

    Returns:
        list[dict]: Each dict has keys:
            game_id, home_team, away_team,
            bookmakers – list of dicts with keys:
                key, markets – dict with h2h / spreads / totals sub-dicts
        Returns [] on failure or missing API key.
    """
    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        _logger.warning("fetch_game_odds: no Odds API key found — returning []")
        return []

    url = f"{_BASE_URL}/sports/{_SPORT}/odds"
    params = {
        "apiKey":     resolved_key,
        "regions":    "us",
        "markets":    "h2h,spreads,totals",
        "dateFormat": "iso",
        "oddsFormat": "american",
    }

    try:
        raw = _fetch_with_retry(url, params=params)
        if not isinstance(raw, list):
            _logger.warning("fetch_game_odds: unexpected response shape, returning []")
            return []

        games: list[dict] = []
        for ev in raw:
            if not isinstance(ev, dict):
                continue

            bookmakers_raw = ev.get("bookmakers", [])
            bookmakers: list[dict] = []
            for bm in bookmakers_raw:
                if not isinstance(bm, dict):
                    continue
                markets_parsed: dict[str, dict] = {}
                for mkt in bm.get("markets", []):
                    mkt_key = mkt.get("key", "")
                    outcomes = {o.get("name"): o.get("price") for o in mkt.get("outcomes", [])}
                    markets_parsed[mkt_key] = outcomes
                bookmakers.append({
                    "key":     bm.get("key", ""),
                    "markets": markets_parsed,
                })

            games.append({
                "game_id":    ev.get("id", ""),
                "home_team":  ev.get("home_team", ""),
                "away_team":  ev.get("away_team", ""),
                "bookmakers": bookmakers,
            })

        return games

    except Exception as exc:
        _logger.warning("fetch_game_odds failed: %s", exc)
        return []


def fetch_player_props(api_key: str | None = None) -> list[dict]:
    """
    Fetch NBA player prop lines from The Odds API and normalise them into
    the same format used by platform_fetcher throughout the application.

    Each returned dict has these keys (matching platform_fetcher output):
        player_name, team, stat_type, line, platform,
        game_date, fetched_at, over_odds, under_odds

    Args:
        api_key: Optional explicit API key; falls back to session state / env.

    Returns:
        list[dict]: Normalised prop dicts.  Returns [] on failure or if no
                    API key is available.

    Note:
        The Odds API charges one request per event per market batch.
        A short delay (_INTER_REQUEST_DELAY_SECONDS) is inserted between
        event requests to respect rate limits.
    """
    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        _logger.warning("fetch_player_props: no Odds API key found — returning []")
        return []

    try:
        events = _fetch_events(resolved_key)
        if not events:
            _logger.warning("fetch_player_props: no NBA events returned from Odds API")
            return []

        team_lookup = _build_team_lookup(events)
        markets_param = ",".join(_PROP_MARKETS)
        fetched_at = datetime.datetime.utcnow().isoformat()
        game_date  = _today_str()

        all_props: list[dict] = []

        for ev in events:
            event_id  = ev.get("id", "")
            home_team = ev.get("home_team", "")
            away_team = ev.get("away_team", "")

            url = f"{_BASE_URL}/sports/{_SPORT}/events/{event_id}/odds"
            params = {
                "apiKey":     resolved_key,
                "markets":    markets_param,
                # "us2" is intentional: The Odds API uses it for the secondary US
                # region (BetMGM, Caesars, PointsBet, etc.) which carries most
                # player-prop markets.  "us" covers DraftKings / FanDuel only.
                "regions":    "us2",
                "oddsFormat": "american",
                "dateFormat": "iso",
            }

            try:
                ev_data = _fetch_with_retry(url, params=params)
                if not ev_data or not isinstance(ev_data, dict):
                    continue

                bookmakers_raw = ev_data.get("bookmakers", [])
                for bm in bookmakers_raw:
                    if not isinstance(bm, dict):
                        continue

                    bm_key          = bm.get("key", "")
                    platform_name   = _bookmaker_display_name(bm_key)

                    for mkt in bm.get("markets", []):
                        if not isinstance(mkt, dict):
                            continue

                        market_key = mkt.get("key", "")
                        stat_type  = _normalize_stat(market_key)
                        outcomes   = mkt.get("outcomes", [])

                        # Group Over/Under outcomes by player name
                        # Outcome shape: {"name": "<player>", "description": "Over"/"Under", "price": -115, "point": 25.5}
                        player_outcomes: dict[str, dict] = {}
                        for outcome in outcomes:
                            if not isinstance(outcome, dict):
                                continue
                            name        = outcome.get("name", "")
                            description = outcome.get("description", "")
                            price       = outcome.get("price")
                            point       = outcome.get("point")

                            if not name:
                                continue

                            if name not in player_outcomes:
                                player_outcomes[name] = {
                                    "line":       None,
                                    "over_odds":  None,
                                    "under_odds": None,
                                }

                            if description.lower() == "over":
                                player_outcomes[name]["over_odds"] = price
                                if point is not None:
                                    player_outcomes[name]["line"] = _safe_float(point)
                            elif description.lower() == "under":
                                player_outcomes[name]["under_odds"] = price
                                if point is not None:
                                    player_outcomes[name]["line"] = _safe_float(point)

                        # Determine team for each player (best-effort from game context)
                        # The Odds API does not tag players with team on props;
                        # we leave team as empty string — callers can enrich downstream.
                        for player_name, odds_data in player_outcomes.items():
                            line       = odds_data.get("line")
                            over_odds  = odds_data.get("over_odds")
                            under_odds = odds_data.get("under_odds")

                            # Skip malformed entries with no line or odds
                            if line is None and over_odds is None:
                                continue

                            all_props.append({
                                "player_name": player_name,
                                "team":        "",        # enriched downstream if needed
                                "stat_type":   stat_type,
                                "line":        line if line is not None else 0.0,
                                "platform":    platform_name,
                                "game_date":   game_date,
                                "fetched_at":  fetched_at,
                                "over_odds":   over_odds,
                                "under_odds":  under_odds,
                            })

            except Exception as ev_exc:
                _logger.warning(
                    "fetch_player_props: error processing event %s: %s", event_id, ev_exc
                )

            # Respect Odds API rate limits between per-event calls
            time.sleep(_INTER_REQUEST_DELAY_SECONDS)

        _logger.info(
            "fetch_player_props: collected %d props across %d events",
            len(all_props), len(events),
        )
        return all_props

    except Exception as exc:
        _logger.warning("fetch_player_props failed: %s", exc)
        return []


# ── Consensus odds helpers ────────────────────────────────────────────────────

def _median(values: list) -> float | None:
    """Return median of a numeric list, or None for empty/invalid input."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    s = sorted(clean)
    mid = len(s) // 2
    if len(s) % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return float(s[mid])


def get_consensus_odds(games_odds: list[dict] | None = None,
                       api_key: str | None = None) -> dict:
    """
    Compute consensus Vegas lines from raw Odds API bookmaker data.

    Uses the median across all bookmakers offering each market. Returns a
    dict keyed by a normalised "(away_team) @ (home_team)" matchup string
    *and* by each team abbreviation for easy lookup.

    Args:
        games_odds: Output of fetch_game_odds(). If None, calls
                    fetch_game_odds() internally.
        api_key:    Passed through to fetch_game_odds() if called internally.

    Returns:
        dict: Keyed by ``"HOME_TEAM"`` or ``"AWAY_TEAM"`` abbreviation
              (upper-case, ClearSports-style) with sub-dicts:

            {
                "home_team": str,
                "away_team": str,
                "consensus_spread": float | None,   # home spread, e.g. -3.5
                "consensus_total":  float | None,   # over/under
                "moneyline_home":   float | None,   # american odds
                "moneyline_away":   float | None,
                "bookmaker_count":  int,             # how many books offered
                "spread_range":     tuple,           # (min, max) spread across books
                "total_range":      tuple,           # (min, max) total across books
            }
    """
    if games_odds is None:
        games_odds = fetch_game_odds(api_key=api_key)

    if not games_odds:
        return {}

    result: dict = {}

    for game in games_odds:
        home_full = str(game.get("home_team", "")).strip()
        away_full = str(game.get("away_team", "")).strip()
        bookmakers = game.get("bookmakers", [])

        if not bookmakers:
            continue

        spreads_home: list[float] = []
        totals: list[float] = []
        ml_home: list[float] = []
        ml_away: list[float] = []

        for bm in bookmakers:
            mkts = bm.get("markets", {})

            # Spread: Odds API uses home team name as key
            sp = mkts.get("spreads", {})
            if sp and home_full in sp:
                try:
                    spreads_home.append(float(sp[home_full]))
                except (TypeError, ValueError):
                    pass

            # Totals: sum (over) is the relevant market
            tot = mkts.get("totals", {})
            for val in tot.values():
                try:
                    totals.append(float(val))
                    break  # One "Over" value per book is enough
                except (TypeError, ValueError):
                    pass

            # Moneyline
            h2h = mkts.get("h2h", {})
            if home_full in h2h:
                try:
                    ml_home.append(float(h2h[home_full]))
                except (TypeError, ValueError):
                    pass
            if away_full in h2h:
                try:
                    ml_away.append(float(h2h[away_full]))
                except (TypeError, ValueError):
                    pass

        consensus = {
            "home_team":        home_full,
            "away_team":        away_full,
            "consensus_spread": _median(spreads_home),
            "consensus_total":  _median(totals),
            "moneyline_home":   _median(ml_home),
            "moneyline_away":   _median(ml_away),
            "bookmaker_count":  len(bookmakers),
            "spread_range":     (min(spreads_home), max(spreads_home)) if spreads_home else (None, None),
            "total_range":      (min(totals), max(totals)) if totals else (None, None),
        }

        # Index by both team name components so callers can look up by team abbrev
        # The full team names from Odds API (e.g. "Los Angeles Lakers") will be
        # normalised to abbreviations by the caller using NBA_TEAM_NAME_TO_ABBREV.
        result[home_full] = consensus
        result[away_full] = consensus

    return result


# ── Historical scores ─────────────────────────────────────────────────────────

def fetch_recent_scores(days_from: int = 1,
                        api_key: str | None = None) -> list[dict]:
    """
    Fetch recently completed NBA game scores from The Odds API.

    The Odds API ``/scores`` endpoint returns the results of games that
    finished within the last *days_from* calendar days (1–3 days max on
    the free tier).  These scores are used to:

    * Auto-update CLV records after games complete (closing-line validation)
    * Validate projection accuracy against actual game outcomes
    * Cross-reference injury / rest-day impact on final scores

    Args:
        days_from: How many days back to fetch (1 = yesterday, 2 = 2 days
                   ago, up to 3 on the free tier).
        api_key:   Optional explicit key; falls back to session state / env.

    Returns:
        list[dict]: Each entry has:
            {
                "game_id":      str,
                "home_team":    str,
                "away_team":    str,
                "commence_time": str,   # ISO datetime
                "completed":    bool,
                "home_score":   int | None,
                "away_score":   int | None,
            }
        Returns [] on failure or missing API key.
    """
    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        _logger.debug("fetch_recent_scores: no Odds API key — returning []")
        return []

    days_from = max(1, min(int(days_from), 3))  # clamp to free-tier range
    url = f"{_BASE_URL}/sports/{_SPORT}/scores"
    params = {
        "apiKey":    resolved_key,
        "daysFrom":  days_from,
        "dateFormat": "iso",
    }
    cache_key = f"{url}?daysFrom={days_from}"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        raw = _fetch_with_retry(url, params=params)
        if not isinstance(raw, list):
            _logger.warning("fetch_recent_scores: unexpected response shape")
            return []

        scores: list[dict] = []
        for ev in raw:
            if not isinstance(ev, dict):
                continue

            scores_raw = ev.get("scores") or []
            home_team  = ev.get("home_team", "")
            away_team  = ev.get("away_team", "")
            home_score = None
            away_score = None

            for sc in scores_raw:
                if not isinstance(sc, dict):
                    continue
                name = sc.get("name", "")
                val  = sc.get("score")
                try:
                    val_int = int(val) if val is not None else None
                except (TypeError, ValueError):
                    val_int = None
                if name == home_team:
                    home_score = val_int
                elif name == away_team:
                    away_score = val_int

            scores.append({
                "game_id":       ev.get("id", ""),
                "home_team":     home_team,
                "away_team":     away_team,
                "commence_time": ev.get("commence_time", ""),
                "completed":     bool(ev.get("completed", False)),
                "home_score":    home_score,
                "away_score":    away_score,
            })

        # Cache for 5 minutes (scores don't change once posted)
        _cache_set(cache_key, scores)
        _logger.info("fetch_recent_scores: %d game(s) returned.", len(scores))
        return scores

    except Exception as exc:
        _logger.warning("fetch_recent_scores failed: %s", exc)
        return []
