# ============================================================
# FILE: data/platform_fetcher.py
# PURPOSE: Fetch live player prop lines from all major sportsbooks
#          via The Odds API (DraftKings, FanDuel, BetMGM, Caesars, etc.).
#          Also provides cross-platform comparison logic and best-platform
#          recommendation.
#
# DATA SOURCE:
#   - The Odds API  : unified source for all sportsbook props (API key required)
#
# USAGE:
#   from data.platform_fetcher import fetch_all_platform_props
#   props = fetch_all_platform_props()
#
# RETURN FORMAT for every prop dict:
#   {
#       "player_name": "LeBron James",
#       "team":        "LAL",
#       "stat_type":   "points",          # internal key (normalized)
#       "line":        24.5,
#       "platform":    "DraftKings",
#       "game_date":   "2026-03-10",
#       "fetched_at":  "2026-03-10T01:00:00",
#       "over_odds":   -115,
#       "under_odds":  -105,
#   }
#
# DESIGN PRINCIPLES:
#   - Graceful degradation: if The Odds API fails, returns empty list
#   - Session caching: callers should store result in session state
#   - Backward compatible: all existing public function signatures preserved
# ============================================================

# Standard library imports (built into Python — no install needed)
import time       # For delays between API calls (rate limiting)
import datetime   # For timestamps on fetched props
import os         # For reading environment variables (API keys)
import asyncio    # For concurrent fetching across platforms

# Third-party HTTP library — must be installed (pip install requests)
# 'requests' is used by roster_engine.py already and listed in requirements.
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Async HTTP library for concurrent platform fetching (pip install aiohttp)
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Import our platform stat-name normalizer
# This converts "3-Point Made" → "threes", "Pts+Rebs" → "points_rebounds", etc.
from data.platform_mappings import normalize_stat_type

# Import odds math from the single source of truth — engine/odds_engine.py
from engine.odds_engine import (
    american_odds_to_implied_probability,
    implied_probability_to_american_odds,
    calculate_breakeven_probability,
)

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

import time as _time

# ── Simple time-based API response cache ─────────────────────────────────────
_API_CACHE: dict = {}
# TTL is configurable via API_CACHE_TTL_SECONDS env var; default 5 minutes.
_API_CACHE_TTL: int = int(__import__("os").environ.get("API_CACHE_TTL_SECONDS", "300"))


def _cache_get(url: str):
    """Return cached response for *url* if not expired, else None."""
    entry = _API_CACHE.get(url)
    if entry is None:
        return None
    payload, ts = entry
    if _time.time() - ts > _API_CACHE_TTL:
        del _API_CACHE[url]
        return None
    return payload


def _cache_set(url: str, payload) -> None:
    """Store *payload* in the cache keyed by *url*."""
    _API_CACHE[url] = (payload, _time.time())

# Import the rate limiter for polite API access with circuit breaker
try:
    from utils.rate_limiter import RateLimiter as _RateLimiter
    # Feature 10: 20 req/min, 200/hour — matches existing live_data_fetcher limits
    _platform_rate_limiter = _RateLimiter(max_requests_per_minute=20, max_requests_per_hour=200)
    _RATE_LIMITER_AVAILABLE = True
except ImportError:
    _RATE_LIMITER_AVAILABLE = False
    _platform_rate_limiter = None

# ============================================================
# SECTION: Module-level constants
# ============================================================

# How long to wait between calls to the same platform (seconds).
# BEGINNER NOTE: APIs block you if you call too fast. 1.5s is polite
# and mirrors the pattern in live_data_fetcher.py.
API_DELAY_SECONDS = 1.5

# HTTP timeout for platform API requests (seconds).
REQUEST_TIMEOUT_SECONDS = 15

# Browser-like User-Agent header so APIs don't block automated requests.
# BEGINNER NOTE: Web servers often reject requests without a User-Agent.
# This mimics a real Chrome browser on Windows.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Shared headers used for every platform request
_BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# PrizePicks public projections endpoint (no API key required)
PRIZEPICKS_URL = "https://api.prizepicks.com/projections"

# Underdog Fantasy public over/under lines endpoint (no API key required)
UNDERDOG_URL = "https://api.underdogfantasy.com/beta/v3/over_under_lines"

# The Odds API base URL — used to fetch DraftKings player props
# Documentation: https://the-odds-api.com/liveapi/guides/v4/
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

# Default American odds for platforms without traditional juice (e.g. -110)
# BEGINNER NOTE: -110 is the standard American odds for prop bets on DraftKings.
# Breakeven at -110 = 52.38% win rate. PrizePicks/Underdog don't use odds,
# so we default to -110 for their implied probability calculations.
_DEFAULT_AMERICAN_ODDS = -110

# ── Data Quarantine Thresholds ─────────────────────────────────────────────
# Lines with odds worse than QUARANTINE_ODDS_FLOOR (heavy favorites) or
# better than QUARANTINE_ODDS_CEILING (long-shots) are extreme alternate
# lines — NOT the standard DFS board.  Strip them to prevent the engine
# from hallucinating "fake" bets on lines that no DFS platform actually
# offers as standard plays.
QUARANTINE_ODDS_FLOOR   = -300   # Drop any line with odds < -300
QUARANTINE_ODDS_CEILING = +250   # Drop any line with odds > +250
_EQUILIBRIUM_ODDS       = -110   # The "Main Line" target (closest to this wins)

# Retry configuration for API calls with exponential backoff
# BEGINNER NOTE: Networks fail occasionally. Retrying with increasing delays
# handles temporary blips without hammering the server.
MAX_API_RETRIES = 3          # Max retry attempts before giving up
RETRY_BASE_DELAY_SECONDS = 1.0  # Base delay: 1s, 2s, 4s (exponential backoff)

# ============================================================
# END SECTION: Module-level constants
# ============================================================


# ============================================================
# SECTION: Retry Helper
# ============================================================

def _fetch_with_retry(url, headers=None, params=None, timeout=None):
    """
    Perform an HTTP GET request with exponential backoff retry on failure.

    Retries up to MAX_API_RETRIES times with delays of 1s, 2s, 4s on:
    - Connection errors
    - Timeout errors
    - HTTP 429 (rate limited) or 5xx server errors

    BEGINNER NOTE: Exponential backoff means we wait longer after each
    failure. This avoids overwhelming a struggling API server.

    Args:
        url (str): The URL to GET.
        headers (dict or None): HTTP headers.
        params (dict or None): URL query parameters.
        timeout (int or None): Request timeout in seconds. Uses REQUEST_TIMEOUT_SECONDS if None.

    Returns:
        requests.Response or None: Response on success, None on all retries failed.
    """
    if not REQUESTS_AVAILABLE:
        return None

    timeout = timeout or REQUEST_TIMEOUT_SECONDS
    headers = headers or _BASE_HEADERS.copy()
    last_exc = None

    for attempt in range(MAX_API_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)

            # Retry on rate limit or server error
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < MAX_API_RETRIES:
                    delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)  # Cap at 10s
                    _logger.warning(
                        f"HTTP {response.status_code} on attempt {attempt+1}/{MAX_API_RETRIES+1} "
                        f"for {url} — retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                return None  # All retries exhausted

            return response  # Success (even if status is 404, caller handles it)

        except Exception as exc:
            last_exc = exc
            if attempt < MAX_API_RETRIES:
                delay = min(RETRY_BASE_DELAY_SECONDS * (2 ** attempt), 10.0)  # Cap at 10s
                _logger.warning(
                    f"Request error on attempt {attempt+1}/{MAX_API_RETRIES+1} "
                    f"for {url}: {exc} — retrying in {delay:.1f}s"
                )
                time.sleep(delay)
            else:
                _logger.error(f"All retries exhausted for {url}: {last_exc}")

    return None


# ============================================================
# END SECTION: Retry Helper
# ============================================================


# ============================================================
# SECTION: Helper — today's date string
# ============================================================

def _today_str():
    """Return today's date as an ISO string ('YYYY-MM-DD'), anchored to US/Eastern.

    NBA prop markets are defined in Eastern Time — a server in UTC would
    shift the date boundary, potentially mis-matching props to the wrong day.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    (EDT = UTC-4). Install ``tzdata`` for correct DST handling.
    """
    try:
        from zoneinfo import ZoneInfo
        _eastern = ZoneInfo("America/New_York")
    except ImportError:
        _eastern = datetime.timezone(datetime.timedelta(hours=-5))
    return datetime.datetime.now(_eastern).date().isoformat()


def _now_str():
    """Return the current UTC datetime as an ISO string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ============================================================
# END SECTION: Helper — today's date string
# ============================================================


# ============================================================
# ============================================================
# SECTION: Deprecated Legacy Fetchers (backward compatibility stubs)
# These functions are kept as no-ops to avoid ImportError in any
# code that may still reference them directly.
# ============================================================

def fetch_prizepicks_props(league="NBA"):
    """Deprecated: PrizePicks fetcher removed. Returns empty list."""
    _logger.info("[PrizePicks] Fetcher removed — use fetch_all_platform_props() instead.")
    return []


def fetch_underdog_props(league="NBA"):
    """Deprecated: Underdog fetcher removed. Returns empty list."""
    _logger.info("[Underdog] Fetcher removed — use fetch_all_platform_props() instead.")
    return []


def fetch_draftkings_props(api_key=None):
    """Deprecated: Use fetch_all_platform_props() which now calls odds_api_client."""
    return fetch_all_platform_props(odds_api_key=api_key)


# ============================================================
# END SECTION: Deprecated Legacy Fetchers
# ============================================================


# ============================================================
# SECTION: Master Fetch Function
# ============================================================

def fetch_all_platform_props(
    include_prizepicks=True,
    include_underdog=True,
    include_draftkings=True,
    odds_api_key=None,
    progress_callback=None,
):
    """
    Fetch live prop lines from all major sportsbooks via The Odds API.

    Replaces the old PrizePicks/Underdog/DraftKings individual fetchers with
    a single unified call to The Odds API, which returns props from all
    US bookmakers (DraftKings, FanDuel, BetMGM, Caesars, etc.) in one place.

    The `include_prizepicks`, `include_underdog`, and `include_draftkings`
    parameters are kept for backward compatibility but are no longer used to
    gate individual fetchers — all props now come from The Odds API.

    Args:
        include_prizepicks (bool): Kept for backward compatibility. Ignored.
        include_underdog (bool): Kept for backward compatibility. Ignored.
        include_draftkings (bool): If False, returns empty list (no props source).
        odds_api_key (str, optional): The Odds API key. If None, reads from
            session state ("odds_api_key") or ODDS_API_KEY env var.
        progress_callback (callable, optional): Called as
            progress_callback(current, total, message) to update a UI progress bar.

    Returns:
        list[dict]: All fetched props from all sportsbooks,
                    each with a "fetched_at" timestamp.

    Example:
        props = fetch_all_platform_props()
        # → 100+ props from DraftKings, FanDuel, BetMGM, etc. combined
    """
    from data.odds_api_client import fetch_player_props as _fetch_props

    if progress_callback:
        progress_callback(0, 3, "Connecting to The Odds API...")

    try:
        all_props = _fetch_props(api_key=odds_api_key)
        _logger.info(f"[Master] The Odds API: {len(all_props)} props fetched.")
    except Exception as err:
        _logger.error(f"[Master] The Odds API fetch failed: {err}")
        all_props = []

    if progress_callback:
        progress_callback(2, 3, f"Processing {len(all_props)} props...")

    # Enrich with alt-line categories
    all_props = parse_alt_lines_from_platform_props(all_props)

    if progress_callback:
        progress_callback(3, 3, f"Done! {len(all_props)} props ready.")

    _logger.info(f"[Master] Total props after enrichment: {len(all_props)}")
    return all_props


# ============================================================
# END SECTION: Master Fetch Function
# ============================================================


# ============================================================
# SECTION: Asynchronous Multi-Platform Fetcher (delegated)
# ============================================================

async def fetch_all_platforms_async(
    include_prizepicks=True,
    include_underdog=True,
    include_draftkings=True,
    odds_api_key=None,
):
    """
    Async wrapper — delegates to the synchronous fetch_all_platform_props().

    The Odds API client uses the requests library (synchronous) which is
    sufficient for the current use case. This async stub is kept for
    backward compatibility with any code that awaits this function.

    Args:
        include_prizepicks (bool): Kept for backward compatibility. Ignored.
        include_underdog (bool): Kept for backward compatibility. Ignored.
        include_draftkings (bool): If False, returns empty list.
        odds_api_key (str, optional): The Odds API key.

    Returns:
        list[dict]: All fetched props.
    """
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: fetch_all_platform_props(
            include_prizepicks=include_prizepicks,
            include_underdog=include_underdog,
            include_draftkings=include_draftkings,
            odds_api_key=odds_api_key,
        )
    )


# ============================================================
# END SECTION: Asynchronous Multi-Platform Fetcher
# ============================================================

# Backward-compat constant — kept so existing imports don't break
_ASYNC_SEMAPHORE_LIMIT = 5


# ============================================================
# SECTION: Cross-Platform Comparison
# ============================================================

def build_cross_platform_comparison(all_props):
    """
    Build a cross-platform line comparison from a list of props.

    Groups props by (player_name, stat_type) and stores the line
    from each platform side-by-side so you can compare them at a glance.

    Args:
        all_props (list[dict]): All fetched props (from fetch_all_platform_props).

    Returns:
        dict: Keyed by (player_name, stat_type) tuples.
              Value is a dict mapping platform → line value.

    Example:
        comparison = build_cross_platform_comparison(props)
        # → {
        #     ("LeBron James", "points"): {
        #         "PrizePicks": 24.5,
        #         "Underdog": 25.5,
        #         "DraftKings": 24.5,
        #     },
        #     ...
        # }
    """
    comparison = {}

    for prop in all_props:
        player_name = prop.get("player_name", "").strip()
        stat_type = prop.get("stat_type", "").strip()
        platform = prop.get("platform", "").strip()
        line = prop.get("line")

        if not player_name or not stat_type or not platform or line is None:
            continue  # Skip incomplete props

        key = (player_name, stat_type)

        # Initialize this player+stat entry if it's new
        if key not in comparison:
            comparison[key] = {}

        # Store the line for this platform.
        # BEGINNER NOTE: If the same player+stat appears twice on one platform
        # (e.g., different game slates), we keep the first one we see.
        if platform not in comparison[key]:
            comparison[key][platform] = line

    return comparison


def recommend_best_platform(comparison, projected_value, direction):
    """
    Recommend the best platform to bet on for a given player+stat.

    Logic:
    - OVER bets: best platform has the LOWEST line (easiest to clear)
    - UNDER bets: best platform has the HIGHEST line (most room to fall under)

    Args:
        comparison (dict): Platform → line dict for one (player, stat_type) key.
            e.g., {"PrizePicks": 24.5, "Underdog": 25.5, "DraftKings": 24.5}
        projected_value (float): Model's projected stat value for this player.
        direction (str): "OVER" or "UNDER" (case-insensitive).

    Returns:
        dict: {
            "platform": "PrizePicks",    # Best platform name
            "line": 24.5,                # Best line on that platform
            "edge": 0.3,                 # projected_value - line (OVER) or line - projected_value (UNDER)
            "all_lines": {...}           # All platform lines for reference
        }
        Returns None if comparison is empty.

    Example:
        recommend_best_platform(
            {"PrizePicks": 24.5, "Underdog": 25.5},
            projected_value=25.8,
            direction="OVER"
        )
        # → {"platform": "PrizePicks", "line": 24.5, "edge": 1.3, ...}
    """
    if not comparison:
        return None

    direction_upper = direction.upper()

    # Find the best platform based on direction
    if direction_upper == "OVER":
        # For OVER: lowest line = easiest to beat = best value
        best_platform = min(comparison, key=lambda p: comparison[p])
    else:
        # For UNDER: highest line = most room to fall under = best value
        best_platform = max(comparison, key=lambda p: comparison[p])

    best_line = comparison[best_platform]

    # Calculate the edge: how much cushion does the best line give us?
    if direction_upper == "OVER":
        edge = round(float(projected_value) - float(best_line), 2)
    else:
        edge = round(float(best_line) - float(projected_value), 2)

    return {
        "platform": best_platform,
        "line": best_line,
        "edge": edge,
        "all_lines": dict(comparison),
    }

# ============================================================
# END SECTION: Cross-Platform Comparison
# ============================================================


# ============================================================
# SECTION: Player Name Matching
# ============================================================

def match_platform_player_to_csv(platform_name, players_data):
    """
    Match a player name from a betting platform to our CSV player database.

    Platforms often use shortened or alternate names (e.g., "Nic Claxton"
    instead of "Nicolas Claxton"). This function uses the existing fuzzy
    matching from data_manager.py to find the canonical name.

    Args:
        platform_name (str): Player name as returned by a platform API.
        players_data (list[dict]): Player list from load_players_data().

    Returns:
        str or None: Canonical player name from our CSV, or None if not found.

    Example:
        match_platform_player_to_csv("Nic Claxton", players_data)
        → "Nicolas Claxton"
    """
    if not platform_name or not players_data:
        return None

    # Use the fuzzy name matcher from data_manager.py
    # BEGINNER NOTE: We import here to avoid circular imports at module level.
    try:
        from data.data_manager import find_player_by_name_fuzzy
        player = find_player_by_name_fuzzy(players_data, platform_name)
        if player:
            return player.get("name", None)
    except Exception as err:
        _logger.warning(f"[NameMatch] Error matching '{platform_name}': {err}")

    return None


def enrich_props_with_csv_names(props, players_data):
    """
    Enrich fetched props by matching platform player names to CSV canonical names.

    Also fills in team abbreviation from the CSV if the platform didn't return one.

    Args:
        props (list[dict]): Props from fetch_all_platform_props().
        players_data (list[dict]): Player list from load_players_data().

    Returns:
        list[dict]: Same props with "player_name" replaced by canonical CSV name
                    where a match was found, and "team" filled in if missing.
    """
    enriched = []
    for prop in props:
        prop = dict(prop)  # Copy so we don't mutate the original
        platform_name = prop.get("player_name", "")

        try:
            from data.data_manager import find_player_by_name_fuzzy
            player = find_player_by_name_fuzzy(players_data, platform_name)
            if player:
                prop["player_name"] = player.get("name", platform_name)
                # Fill in team from CSV if missing
                if not prop.get("team"):
                    prop["team"] = player.get("team", "")
        except Exception:
            pass  # Keep original name if matching fails

        enriched.append(prop)

    return enriched

# ============================================================
# END SECTION: Player Name Matching
# ============================================================


# ============================================================
# SECTION: Roster Inference from Props
# ============================================================

def find_new_players_from_props(props, players_data):
    """
    Identify players from platform props who are NOT in our CSV database.

    Since betting platforms only list active players who are playing tonight,
    any player on a platform but NOT in our CSV is either new, traded, or
    a player we haven't fetched yet. These are flagged for a data update.

    Args:
        props (list[dict]): Props from fetch_all_platform_props().
        players_data (list[dict]): Player list from load_players_data().

    Returns:
        list[str]: List of platform player names not found in our CSV.

    Example:
        new_players = find_new_players_from_props(props, players_data)
        # → ["Marcus Morris Sr.", "Patrick Baldwin Jr."]
    """
    if not props or not players_data:
        return []

    try:
        from data.data_manager import find_player_by_name_fuzzy
    except Exception:
        return []

    not_found = []
    seen = set()  # Avoid duplicate names in the output

    for prop in props:
        player_name = prop.get("player_name", "").strip()
        if not player_name or player_name in seen:
            continue
        seen.add(player_name)

        match = find_player_by_name_fuzzy(players_data, player_name)
        if not match:
            not_found.append(player_name)

    return not_found


def extract_active_players_from_props(props):
    """
    Extract the set of active players implied by tonight's platform props.

    Since betting platforms (PrizePicks, Underdog, DraftKings) only list
    props for players who are CONFIRMED active and playing tonight, every
    player who appears in the props list is de-facto confirmed:
      1. Active (not injured/out)
      2. Playing tonight
      3. On an NBA roster

    Args:
        props (list[dict]): Props from fetch_all_platform_props().

    Returns:
        dict: Keyed by lower-cased player name.
              Value: {"name": str, "team": str, "platforms": list[str]}

    Example:
        active = extract_active_players_from_props(props)
        # → {
        #     "lebron james": {"name": "LeBron James", "team": "LAL",
        #                      "platforms": ["PrizePicks", "Underdog"]},
        #     ...
        # }
    """
    active = {}

    for prop in props:
        player_name = prop.get("player_name", "").strip()
        if not player_name:
            continue

        team = prop.get("team", "").strip()
        platform = prop.get("platform", "").strip()
        key = player_name.lower()

        if key not in active:
            active[key] = {
                "name": player_name,
                "team": team,
                "platforms": [],
            }
        else:
            # Update team if we got a better value
            if team and not active[key]["team"]:
                active[key]["team"] = team

        if platform and platform not in active[key]["platforms"]:
            active[key]["platforms"].append(platform)

    return active


def cross_reference_with_player_data(platform_players, players_data):
    """
    Compare platform-confirmed active players against our CSV player database.

    Identifies:
      - Players the platforms have props for that we have stats for (matched)
      - Players on platforms but NOT in our CSV (missing_from_csv) — need data update
      - Players in our CSV but NOT on any platform tonight (in_csv_but_not_on_platforms)
        — these players may be injured, resting, or not playing tonight

    Args:
        platform_players (dict): Output of extract_active_players_from_props().
        players_data (list[dict]): Player records from load_players_data().

    Returns:
        dict with keys:
          "matched"                   : list[dict] — players found in both
          "missing_from_csv"          : list[str]  — platform names not in CSV
          "in_csv_but_not_on_platforms": list[dict] — CSV players absent from platforms

    Example:
        result = cross_reference_with_player_data(active_players, players_data)
        result["missing_from_csv"]  # → ["Marcus Morris Sr."]
        result["matched"]           # → [{"name": "LeBron James", "team": "LAL", ...}]
    """
    try:
        from data.data_manager import normalize_player_name as _norm
    except ImportError:
        def _norm(n):
            return n.lower().strip()

    # Build a normalized-name set from our CSV for fast lookup
    csv_norm_map = {}
    for player in players_data:
        name = player.get("name", "").strip()
        if name:
            csv_norm_map[_norm(name)] = player

    matched = []
    missing_from_csv = []

    for key, info in platform_players.items():
        norm_key = _norm(info["name"])
        if norm_key in csv_norm_map:
            matched.append({
                "name": info["name"],
                "team": info["team"],
                "platforms": info["platforms"],
                "csv_name": csv_norm_map[norm_key].get("name", info["name"]),
            })
        else:
            missing_from_csv.append(info["name"])

    # Players in CSV but NOT confirmed on any platform tonight
    platform_norm_keys = {_norm(info["name"]) for info in platform_players.values()}
    in_csv_but_not_on_platforms = [
        player for player in players_data
        if _norm(player.get("name", "")) not in platform_norm_keys
    ]

    return {
        "matched": matched,
        "missing_from_csv": missing_from_csv,
        "in_csv_but_not_on_platforms": in_csv_but_not_on_platforms,
    }


def get_platform_confirmed_injuries(platform_players, players_data, todays_games):
    """
    Infer potential injuries from platform props — players on tonight's teams
    who do NOT appear in any platform's props may be out/inactive.

    Since platforms only list players who are active, a player who:
      - Is in our CSV database
      - Plays for a team with a game tonight
      - Does NOT appear in any platform props

    ...is likely injured, resting, or sitting out (even if not yet on the
    official injury report).

    Args:
        platform_players (dict): Output of extract_active_players_from_props().
        players_data (list[dict]): Player records from load_players_data().
        todays_games (list): Tonight's game list (each item has "home_team"
                             and "away_team" or similar fields).

    Returns:
        list[dict]: Each item: {"name": str, "team": str,
                                "reason": "Not listed on any platform props"}

    Example:
        possibly_out = get_platform_confirmed_injuries(active, players, games)
        # → [{"name": "Damian Lillard", "team": "MIL",
        #      "reason": "Not listed on any platform props"}, ...]
    """
    try:
        from data.data_manager import normalize_player_name as _norm
    except ImportError:
        def _norm(n):
            return n.lower().strip()

    # Collect team abbreviations playing tonight
    tonight_teams = set()
    for game in todays_games:
        home = game.get("home_team", game.get("homeTeam", ""))
        away = game.get("away_team", game.get("awayTeam", ""))
        if home:
            tonight_teams.add(str(home).upper())
        if away:
            tonight_teams.add(str(away).upper())

    if not tonight_teams:
        return []

    # Build normalized-name set from platform props (computed once)
    platform_norm_keys = {_norm(info["name"]) for info in platform_players.values()}

    # Pre-compute (name, team, norm_name) for players_data to avoid repeated normalization
    possibly_out = []
    for player in players_data:
        player_name = player.get("name", "").strip()
        player_team = str(player.get("team", "")).upper().strip()

        if not player_name or not player_team:
            continue

        # Only check players on teams playing tonight
        if player_team not in tonight_teams:
            continue

        # Flag if not seen on any platform
        if _norm(player_name) not in platform_norm_keys:
            possibly_out.append({
                "name": player_name,
                "team": player_team,
                "reason": "Not listed on any platform props",
            })

    return possibly_out

# ============================================================
# END SECTION: Roster Inference from Props
# ============================================================


# ============================================================
# SECTION: Per-Platform Summary Helper
# ============================================================

def summarize_props_by_platform(props):
    """
    Count how many props were fetched per platform.

    Args:
        props (list[dict]): All fetched props.

    Returns:
        dict: Platform name → count of props.

    Example:
        summarize_props_by_platform(props)
        # → {"PrizePicks": 84, "Underdog": 76, "DraftKings": 32}
    """
    summary = {}
    for prop in props:
        platform = prop.get("platform", "Unknown")
        summary[platform] = summary.get(platform, 0) + 1
    return summary

# ============================================================
# END SECTION: Per-Platform Summary Helper
# ============================================================


# ============================================================
# SECTION: Smart Prop Filter
# ============================================================

# Default stat types to keep when smart filtering is enabled.
# These are the most commonly offered and highest-value prop types.
_DEFAULT_STAT_TYPES = frozenset({
    "points", "rebounds", "assists", "threes",
    "steals", "blocks", "turnovers",
    "points_rebounds_assists", "points_rebounds",
    "points_assists", "rebounds_assists",
})


def quarantine_props(
    props,
    odds_floor=QUARANTINE_ODDS_FLOOR,
    odds_ceiling=QUARANTINE_ODDS_CEILING,
    equilibrium=_EQUILIBRIUM_ODDS,
):
    """
    Apply a strict Data Quarantine to raw props from any platform.

    The quarantine prevents the engine from analysing extreme alternate
    lines that no DFS platform actually offers as standard plays.  It
    enforces three rules:

    1. **Hard Drop** — Remove any line whose ``over_odds`` or
       ``under_odds`` fall outside the ``[odds_floor, odds_ceiling]``
       window (default -300 to +250).  These are extreme alt-lines, not
       standard DFS boards.

    2. **Main Line Lock** — For each unique (player, stat_type) pair,
       select the single line whose ``over_odds`` are closest to
       ``equilibrium`` (default -110).  This is the "Main Line" that
       DFS platforms display as their standard More/Less board.

    3. **prop_target_line** — The surviving line value is stamped on
       each prop as ``prop_target_line`` (float).  All downstream EV,
       simulation, and Kelly calculations MUST use this field.

    If a player+stat has **no** line surviving the hard-drop, the
    player is silently dropped for that stat type (prevents UI
    crashes from missing data).

    Args:
        props (list[dict]): Raw props (each must have ``over_odds``,
            ``under_odds``, ``line``, ``player_name``, ``stat_type``).
        odds_floor (int): Most-negative American odds allowed (default -300).
        odds_ceiling (int): Most-positive American odds allowed (default +250).
        equilibrium (int): Target equilibrium odds for main-line selection
            (default -110).

    Returns:
        tuple: (quarantined_props, quarantine_summary)
            quarantined_props (list[dict]): Props that pass quarantine,
                each enriched with ``prop_target_line``.
            quarantine_summary (dict): Counts at each step.
    """
    summary = {
        "input_count": len(props),
        "after_hard_drop": 0,
        "after_main_line_lock": 0,
        "dropped_no_valid_line": 0,
    }

    if not props:
        return [], summary

    # ── Step 1: Hard Drop — remove extreme odds ─────────────────────────
    surviving = []
    for p in props:
        try:
            over_o = float(p.get("over_odds", _DEFAULT_AMERICAN_ODDS))
        except (ValueError, TypeError):
            over_o = float(_DEFAULT_AMERICAN_ODDS)
        try:
            under_o = float(p.get("under_odds", _DEFAULT_AMERICAN_ODDS))
        except (ValueError, TypeError):
            under_o = float(_DEFAULT_AMERICAN_ODDS)

        # Odds worse than floor (e.g. -400 < -300) → drop
        if over_o < odds_floor or under_o < odds_floor:
            continue
        # Odds better than ceiling (e.g. +300 > +250) → drop
        if over_o > odds_ceiling or under_o > odds_ceiling:
            continue

        surviving.append(p)

    summary["after_hard_drop"] = len(surviving)

    # ── Step 2: Main Line Lock — select the line closest to equilibrium ──
    # Group by (player_name_lower, stat_type_lower)
    groups: dict = {}
    for p in surviving:
        key = (
            str(p.get("player_name", "")).lower().strip(),
            str(p.get("stat_type", "")).lower().strip(),
        )
        groups.setdefault(key, []).append(p)

    quarantined: list = []
    dropped_count = 0

    for _key, group in groups.items():
        # Pick the line whose over_odds are closest to equilibrium
        best = None
        best_distance = float("inf")
        for p in group:
            try:
                over_o = float(p.get("over_odds", _DEFAULT_AMERICAN_ODDS))
            except (ValueError, TypeError):
                over_o = float(_DEFAULT_AMERICAN_ODDS)
            distance = abs(over_o - equilibrium)
            if distance < best_distance:
                best_distance = distance
                best = p

        if best is None:
            dropped_count += 1
            continue

        # Stamp the surviving prop with prop_target_line
        enriched = dict(best)
        try:
            enriched["prop_target_line"] = float(best.get("line", 0))
        except (ValueError, TypeError):
            dropped_count += 1
            continue

        if enriched["prop_target_line"] <= 0:
            dropped_count += 1
            continue

        quarantined.append(enriched)

    summary["after_main_line_lock"] = len(quarantined)
    summary["dropped_no_valid_line"] = dropped_count

    return quarantined, summary


def smart_filter_props(
    all_props,
    players_data=None,
    todays_games=None,
    injury_map=None,
    max_props_per_player=5,
    stat_types=None,
    deduplicate_cross_platform=True,
):
    """
    Intelligently reduce a large prop set to high-signal picks.

    Runs the following pipeline in order:
      1. Filter to tonight's teams only (cross-reference todays_games).
      2. Remove injured/inactive players (cross-reference injury_map).
      3. Deduplicate cross-platform props — keep the best line for each
         player+stat combination (or a single representative if averaging).
         Tags the surviving prop with all platforms that offer it.
      4. Filter to selected stat types (defaults to core stats).
      5. Cap props per player at max_props_per_player (if set).

    Args:
        all_props (list[dict]): Full prop list from fetch_all_platform_props().
        players_data (list[dict], optional): Player records from load_players_data().
            Used to validate players exist in the database.
        todays_games (list[dict], optional): Tonight's game schedule.
            Each entry should have 'home_team' and 'away_team' keys.
        injury_map (dict, optional): Player-name → injury-status mapping.
            Keys are lowercase player names; values are status strings
            (e.g., "Out", "Injured Reserve", "Questionable").
        max_props_per_player (int or None): Maximum stat types to keep per
            player.  Default is 5. Range 1–15.  Pass None to skip the
            per-player cap entirely.
        stat_types (set or list, optional): Stat types to include.
            Defaults to _DEFAULT_STAT_TYPES. Pass None to use defaults.
        deduplicate_cross_platform (bool): If True (default), collapse
            duplicate (player, stat_type) entries from multiple platforms
            into one record and tag it with all offering platforms.

    Returns:
        tuple: (filtered_props, filter_summary)
            filtered_props (list[dict]): Reduced, high-signal prop list.
            filter_summary (dict): Step-by-step count statistics.

    Example:
        filtered, summary = smart_filter_props(
            all_props=raw_props,
            todays_games=st.session_state.get("todays_games", []),
            injury_map=st.session_state.get("injury_status_map", {}),
        )
        print(f"Reduced {summary['original_count']} → {summary['final_count']} props "
              f"({summary['reduction_pct']:.0f}% reduction)")
    """
    # ── Statuses considered inactive/out ───────────────────────────────
    _INACTIVE_STATUSES = frozenset({
        "out", "injured reserve", "ir", "suspended",
        "not with team", "g league - two-way",
        "g league - on assignment", "g league",
        "doubtful",
    })

    # ── Resolve stat type filter set ────────────────────────────────────
    if stat_types is None:
        _allowed_stats = _DEFAULT_STAT_TYPES
    else:
        _allowed_stats = frozenset(str(s).lower().strip() for s in stat_types)

    original_count = len(all_props)
    summary: dict = {
        "original_count": original_count,
        "after_quarantine": original_count,
        "after_team_filter": original_count,
        "after_injury_filter": original_count,
        "after_dedup": original_count,
        "after_stat_filter": original_count,
        "after_per_player_cap": original_count,
        "final_count": original_count,
        "reduction_pct": 0.0,
    }

    if not all_props:
        return [], summary

    # ── Step 0: Data Quarantine — hard-drop extreme odds + lock main line ─
    quarantined, q_summary = quarantine_props(all_props)
    summary["after_quarantine"] = len(quarantined)

    # ── Step 1: Filter to tonight's teams ───────────────────────────────
    # Build the set of teams playing tonight (with common abbreviation aliases)
    _ABBREV_ALIASES = {
        "GS": "GSW", "GSW": "GS",
        "NY": "NYK", "NYK": "NY",
        "NO": "NOP", "NOP": "NO",
        "SA": "SAS", "SAS": "SA",
        "UTAH": "UTA", "UTA": "UTAH",
        "WSH": "WAS", "WAS": "WSH",
        "BKN": "BRK", "BRK": "BKN",
        "PHX": "PHO", "PHO": "PHX",
        "CHA": "CHO", "CHO": "CHA",
    }

    tonight_teams: set = set()
    if todays_games:
        for game in todays_games:
            for side in ("home_team", "away_team", "homeTeam", "awayTeam"):
                abbr = str(game.get(side, "")).upper().strip()
                if abbr:
                    tonight_teams.add(abbr)
                    alias = _ABBREV_ALIASES.get(abbr)
                    if alias:
                        tonight_teams.add(alias)
        tonight_teams.discard("")

    if tonight_teams:
        team_filtered = [
            p for p in quarantined
            if (
                not p.get("team")  # keep props with no team info (can't filter)
                or str(p.get("team", "")).upper().strip() in tonight_teams
            )
        ]
    else:
        # No game data — can't filter by team; keep all
        team_filtered = list(quarantined)

    summary["after_team_filter"] = len(team_filtered)

    # ── Step 2: Remove injured/inactive players ──────────────────────────
    if injury_map:
        def _is_active(prop):
            player_key = str(prop.get("player_name", "")).lower().strip()
            status = str(injury_map.get(player_key, "")).lower().strip()
            if not status:
                return True  # No status known — assume active
            return status not in _INACTIVE_STATUSES

        injury_filtered = [p for p in team_filtered if _is_active(p)]
    else:
        injury_filtered = team_filtered

    summary["after_injury_filter"] = len(injury_filtered)

    # ── Step 3: Deduplicate cross-platform props ─────────────────────────
    if deduplicate_cross_platform:
        # Group by (player_name_lower, stat_type) key
        dedup_map: dict = {}  # key → list of props
        for prop in injury_filtered:
            pkey = (
                str(prop.get("player_name", "")).lower().strip(),
                str(prop.get("stat_type", "")).lower().strip(),
            )
            dedup_map.setdefault(pkey, []).append(prop)

        dedup_filtered: list = []
        for pkey, group in dedup_map.items():
            if len(group) == 1:
                dedup_filtered.append(group[0])
            else:
                # Use the lower median line (floor of midpoint for even-length groups),
                # which biases toward the lower line — better for OVER bettors.
                sorted_group = sorted(group, key=lambda p: float(p.get("line", 0) or 0))
                best = dict(sorted_group[(len(sorted_group) - 1) // 2])  # lower-median line
                all_platforms_for_prop = sorted({
                    str(p.get("platform", "")).strip()
                    for p in group
                    if p.get("platform")
                })
                best["platforms_offering"] = all_platforms_for_prop
                # Keep original platform name from the median entry
                dedup_filtered.append(best)
    else:
        dedup_filtered = injury_filtered

    summary["after_dedup"] = len(dedup_filtered)

    # ── Step 4: Filter to selected stat types ────────────────────────────
    stat_filtered = [
        p for p in dedup_filtered
        if str(p.get("stat_type", "")).lower().strip() in _allowed_stats
    ]
    summary["after_stat_filter"] = len(stat_filtered)

    # ── Step 5: Cap props per player ────────────────────────────────────
    # Priority ordering within each player: prefer core stats first
    _STAT_PRIORITY = {
        "points": 0, "rebounds": 1, "assists": 2,
        "points_rebounds_assists": 3, "threes": 4,
        "points_rebounds": 5, "points_assists": 6,
        "rebounds_assists": 7, "steals": 8,
        "blocks": 9, "turnovers": 10,
    }

    if max_props_per_player is None:
        # No per-player cap — pass all stat-filtered props through
        capped = stat_filtered
    else:
        # Clamp max_props_per_player to a reasonable range (1–100).
        # The docstring documents 1-15 as typical, but we allow up to 100
        # for power users who want to disable the cap without changing code.
        _MAX = min(100, max(1, int(max_props_per_player)))
        player_counts: dict = {}
        capped: list = []

        # Sort to ensure priority stat types come first for each player
        stat_filtered_sorted = sorted(
            stat_filtered,
            key=lambda p: _STAT_PRIORITY.get(
                str(p.get("stat_type", "")).lower().strip(), 99
            ),
        )

        for prop in stat_filtered_sorted:
            player_key = str(prop.get("player_name", "")).lower().strip()
            count = player_counts.get(player_key, 0)
            if count < _MAX:
                capped.append(prop)
                player_counts[player_key] = count + 1

    summary["after_per_player_cap"] = len(capped)
    summary["final_count"] = len(capped)

    # Calculate overall reduction percentage
    if original_count > 0:
        summary["reduction_pct"] = round(
            (1.0 - len(capped) / original_count) * 100.0, 1
        )
    else:
        summary["reduction_pct"] = 0.0

    return capped, summary

# ============================================================
# END SECTION: Smart Prop Filter
# ============================================================


# ============================================================
# SECTION: Alternate Line Categorization
# ============================================================

def parse_alt_lines_from_platform_props(props):
    """
    Parse a flat list of platform props and enrich each record with its
    alternate-line category relative to the standard (primary) O/U line.

    Sportsbooks offer a primary "Standard_Line" O/U for each player prop,
    plus a set of alternate lines at different thresholds.  When the same
    (player_name, stat_type, platform) combination appears more than once
    in the props list, the MEDIAN of all available lines is treated as the
    standard line and the remaining lines are classified as:

        ``'50_50'``    — this entry IS the standard O/U line (the baseline).
        ``'goblin'``   — this line is BELOW the standard (safe floor bet;
                         high probability of hitting even if the player
                         misses the standard line).
        ``'demon'``    — this line is ABOVE the standard (high risk / high
                         reward; the player must exceed a higher threshold).

    Statistical analysis should be triggered ONLY on actual bookmaker lines
    — never on hypothetical or generated values.  Pass the output of this
    function directly to the analysis pipeline to ensure only real lines
    are evaluated.

    Args:
        props (list[dict]): Props as returned by ``fetch_all_platform_props()``.
            Multiple entries for the same (player, stat, platform) tuple
            indicate that alternate lines are available.

    Returns:
        list[dict]: Same props enriched with two new keys on every entry:
            ``'standard_line'``: float — the median line for this
                (player, stat, platform) group (the Standard_Line).
            ``'line_category'``: str — ``'50_50'`` | ``'goblin'`` |
                ``'demon'``.

    Example::

        props = [
            {"player_name": "SGA", "stat_type": "points",
             "line": 28.5, "platform": "PrizePicks"},
            {"player_name": "SGA", "stat_type": "points",
             "line": 31.5, "platform": "PrizePicks"},
            {"player_name": "SGA", "stat_type": "points",
             "line": 34.5, "platform": "PrizePicks"},
        ]
        enriched = parse_alt_lines_from_platform_props(props)
        # → [
        #     {..."line": 28.5, "line_category": "goblin",   "standard_line": 31.5},
        #     {..."line": 31.5, "line_category": "50_50",    "standard_line": 31.5},
        #     {..."line": 34.5, "line_category": "demon",    "standard_line": 31.5},
        # ]
    """
    import statistics as _statistics

    # ── Step 1: Group all lines by (player_name, stat_type) ──────────────
    # Group across ALL platforms so we find the true middle number for
    # each player+stat combination.  This gives the most accurate
    # More/Less (Over/Under) line by taking the median of all
    # available lines regardless of which platform offered them.
    _cross_groups: dict = {}
    for prop in props:
        cross_key = (
            str(prop.get("player_name", "")).lower().strip(),
            str(prop.get("stat_type", "")).lower().strip(),
        )
        _cross_groups.setdefault(cross_key, []).append(prop)

    # ── Step 2: Identify the Standard_Line for each group ────────────────
    # The standard line is the MEDIAN of all lines across platforms.
    # For a single-entry group the only line IS the standard.
    # For multi-entry groups the median is the middle number — the true
    # More/Less or Over/Under line.
    _standard_lines: dict = {}
    for cross_key, group_props in _cross_groups.items():
        valid_lines = []
        for p in group_props:
            try:
                val = float(p.get("line", 0) or 0)
                if val > 0:
                    valid_lines.append(val)
            except (ValueError, TypeError):
                pass
        if valid_lines:
            _standard_lines[cross_key] = _statistics.median(valid_lines)
        else:
            _standard_lines[cross_key] = None

    # ── Step 3: Stamp each prop with standard_line and line_category ─────
    enriched = []
    for prop in props:
        cross_key = (
            str(prop.get("player_name", "")).lower().strip(),
            str(prop.get("stat_type", "")).lower().strip(),
        )
        std_line = _standard_lines.get(cross_key)

        try:
            prop_line = float(prop.get("line", 0) or 0)
        except (ValueError, TypeError):
            prop_line = 0.0

        enriched_prop = dict(prop)
        enriched_prop["standard_line"] = std_line

        # Classify each prop relative to the standard O/U line.
        # The standard_line (median / middle number) is the primary
        # More/Less or Over/Under line that platforms advertise.
        if std_line is None or prop_line <= 0:
            enriched_prop["line_category"] = "standard"
        elif abs(prop_line - std_line) < 0.01:
            # This IS the standard O/U line (the main More/Less line)
            enriched_prop["line_category"] = "50_50"
        elif prop_line < std_line:
            # Below the standard — safer bet (goblin)
            enriched_prop["line_category"] = "goblin"
        else:
            # Above the standard — riskier bet (demon)
            enriched_prop["line_category"] = "demon"

        # Ensure every prop carries a ``prop_line`` field set to the
        # standard (middle) line so downstream consumers always know
        # the primary More/Less threshold.
        if std_line is not None:
            enriched_prop["prop_line"] = std_line

        # Ensure a ``direction`` field exists so downstream bet cards
        # always display the More/Less (Over/Under) side.  For the
        # standard line use OVER as default; for goblin lines the
        # player is likely to clear (OVER); for demon lines the bar
        # is higher (UNDER is the safer play).
        if "direction" not in enriched_prop:
            cat = enriched_prop.get("line_category", "standard")
            if cat == "goblin":
                enriched_prop["direction"] = "OVER"
            elif cat == "demon":
                enriched_prop["direction"] = "UNDER"
            else:
                enriched_prop["direction"] = "OVER"

        enriched.append(enriched_prop)

    return enriched

# ============================================================
# END SECTION: Alternate Line Categorization
# ============================================================

