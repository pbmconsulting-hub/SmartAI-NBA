# ============================================================
# FILE: data/live_data_fetcher.py
# PURPOSE: Fetch live, real NBA data via the ClearSports API.
#          Pulls today's games, player stats, team stats, and
#          player game logs. Saves everything to CSV files so
#          the rest of the app works without any changes.
# CONNECTS TO: pages/9_📡_Data_Feed.py, data/data_manager.py
# CONCEPTS COVERED: APIs, rate limiting, CSV writing, error handling
#
# BEGINNER NOTE: An API (Application Programming Interface) is a
# way for programs to talk to each other. ClearSports is a real-time
# NBA data provider — configure your API key in the Settings page.
# ============================================================

# Standard library imports (no install needed — built into Python)
import csv          # For reading and writing CSV files
import json         # For reading and writing JSON files (timestamps, etc.)
import math         # For isfinite checks in safe_avg
import time         # For adding delays between API calls
import datetime     # For timestamps and date handling
import statistics   # For calculating standard deviations
from pathlib import Path  # Modern, cross-platform file path handling

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

try:
    from data.game_log_cache import save_game_logs_to_cache, load_game_logs_from_cache
    _GAME_LOG_CACHE_AVAILABLE = True
except ImportError:
    _GAME_LOG_CACHE_AVAILABLE = False

# Feature 12: SQLite game log persistence (write-through alongside JSON cache)
try:
    from tracking.database import (
        save_player_game_logs_to_db,
        load_player_game_logs_from_db,
        is_game_log_cache_stale,
    )
    _DB_GAME_LOG_AVAILABLE = True
except ImportError:
    _DB_GAME_LOG_AVAILABLE = False

try:
    from utils.rate_limiter import RateLimiter
    _rate_limiter = RateLimiter(max_requests_per_minute=15, max_requests_per_hour=150)
    _RATE_LIMITER_AVAILABLE = True
except ImportError:
    _RATE_LIMITER_AVAILABLE = False
    _rate_limiter = None

# ============================================================
# SECTION: File Path Constants
# Same data directory as data_manager.py
# ============================================================

# Get the directory where this file lives (the 'data' folder)
DATA_DIRECTORY = Path(__file__).parent

# Paths to each CSV file we will write
PLAYERS_CSV_PATH = DATA_DIRECTORY / "players.csv"             # Player stats output
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"                   # Team stats output
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"  # Defensive ratings output

# Path to the JSON file that tracks when each data type was last updated
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"

# Path to the JSON file that caches the player injury/availability status map.
# Written by fetch_todays_players_only() via RosterEngine and read by data_manager.get_player_status().
INJURY_STATUS_JSON_PATH = DATA_DIRECTORY / "injury_status.json"

# How long to wait between API calls (in seconds) to avoid being blocked
# BEGINNER NOTE: Rate limiting means the NBA website limits how fast
# you can make requests. If you ask too fast, they block you temporarily.
# Adding a 1.5 second delay between calls keeps us polite and avoids blocks.
API_DELAY_SECONDS = 1.5

# ============================================================
# Standard deviation ratio constants for stat fallback estimates.
# These are used when game log data is unavailable for a player.
# Values are empirically derived from NBA stat distributions.
#
# NOTE (W10): The fixed ratios below are kept for backward compatibility.
# The new _dynamic_cv_for_live_fetch() function uses tier-based CV
# which is called at the point of fallback estimate computation.
# ============================================================
FALLBACK_POINTS_STD_RATIO = 0.3      # Points: ~30% CV is typical for scorers
FALLBACK_REBOUNDS_STD_RATIO = 0.4    # Rebounds: ~40% CV — more variable
FALLBACK_ASSISTS_STD_RATIO = 0.4     # Assists: ~40% CV — game-plan dependent
FALLBACK_THREES_STD_RATIO = 0.55     # 3-pointers: ~55% CV — streaky (minimum)
FALLBACK_STEALS_STD_RATIO = 0.5      # Steals: ~50% CV
FALLBACK_BLOCKS_STD_RATIO = 0.6      # Blocks: ~60% CV
FALLBACK_TURNOVERS_STD_RATIO = 0.4   # Turnovers: ~40% CV

# Minimum minutes threshold to include a player's stats.
# Players below this threshold are considered inactive/garbage-time only.
# Problem statement requires 15+ MPG for live fetch; we keep 10 for fallback.
MIN_MINUTES_THRESHOLD = 15.0

# Games-missed threshold for the recency proxy in fetch_todays_players_only().
# If a player has missed more than this many games relative to their team's max GP,
# they are likely on a long-term absence even if not explicitly in the injury report.
# 12 games ≈ 2-3 weeks of absence; requires the team to have played 20+ games first.
GP_ABSENT_THRESHOLD = 12
MIN_TEAM_GP_FOR_RECENCY_CHECK = 20

# Position map: nba_api START_POSITION codes → our position labels.
# Defined at module level to avoid re-creating the dict on every function call.
_POSITION_MAP = {
    "G":   "PG", "F":   "SF", "C":  "C",
    "G-F": "SF", "F-G": "SG", "F-C": "PF", "C-F": "PF", "": "SF",
}

# Recent-form trend thresholds: how much above/below season avg to be "hot"/"cold"
HOT_TREND_THRESHOLD = 1.1   # Last 3 games avg ≥ 110% of recent avg = hot
COLD_TREND_THRESHOLD = 0.9  # Last 3 games avg ≤ 90% of recent avg = cold

# ============================================================
# Game fetcher defaults (placeholder values used until live odds are added)
# ============================================================
DEFAULT_VEGAS_SPREAD = 0.0   # No live spread data yet; shown as 0 until integrated
DEFAULT_GAME_TOTAL = 220.0   # Typical NBA over/under baseline used as placeholder

# Timeout for the ESPN public scoreboard HTTP request (seconds)
ESPN_API_TIMEOUT_SECONDS = 10

# Injury status values that indicate a player is unavailable.
# Used by fetch_todays_players_only() and fetch_player_stats() to
# filter out inactive players before writing to CSV.
#
# Note: "Doubtful" and "Questionable" are included here because
# players with these designations almost never play and including
# them in simulations/props would produce unreliable predictions.
# GTD (Game Time Decision) and Day-to-Day players are treated
# differently — they remain in the roster but receive a warning
# flag via GTD_INJURY_STATUSES below.
INACTIVE_INJURY_STATUSES = frozenset({
    "Out",
    "Doubtful",
    "Questionable",
    "Injured Reserve",
    "Out (No Recent Games)",
    "Suspended",
    "Not With Team",
    "G League - Two-Way",
    "G League - On Assignment",
    "G League",
})

# Statuses that are not fully removed but should be flagged separately
# (e.g., GTD players remain selectable but show a warning badge).
GTD_INJURY_STATUSES = frozenset({
    "GTD",
    "Day-to-Day",
})

# ============================================================
# END SECTION: File Path Constants
# ============================================================


def _nba_today_et():
    """Return today's date anchored to US/Eastern time.

    NBA defines game dates in Eastern Time. A server running in UTC
    would shift the date boundary by 5 hours, causing late West-Coast
    games (which tip off at 10:30 PM ET / 3:30 AM UTC) to be assigned
    to the wrong calendar day.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    (EDT = UTC-4). Install ``tzdata`` for correct DST handling.
    """
    try:
        from zoneinfo import ZoneInfo
        _eastern = ZoneInfo("America/New_York")
    except ImportError:
        _eastern = datetime.timezone(datetime.timedelta(hours=-5))
    return datetime.datetime.now(_eastern).date()


# ============================================================
# SECTION: NBA Team Abbreviation Mapping
# nba_api uses team IDs internally; we need abbreviations.
# This maps the team full name to our 3-letter abbreviation.
# ============================================================

# Complete mapping of NBA team full names to abbreviations
# BEGINNER NOTE: This dictionary lets us look up an abbreviation
# by giving it the full team name as a key.
TEAM_NAME_TO_ABBREVIATION = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

# Map nba_api's team abbreviations to our abbreviations
# (nba_api sometimes uses slightly different codes, e.g. "GS" vs "GSW")
NBA_API_ABBREV_TO_OURS = {
    "GS": "GSW",   # Golden State Warriors
    "NY": "NYK",   # New York Knicks
    "NO": "NOP",   # New Orleans Pelicans
    "SA": "SAS",   # San Antonio Spurs
    "OKC": "OKC",  # Oklahoma City Thunder (same)
    "PHX": "PHX",  # Phoenix Suns (same)
    "UTA": "UTA",  # Utah Jazz (same)
    "MEM": "MEM",  # Memphis Grizzlies (same)
}

# Conference mapping by abbreviation
TEAM_CONFERENCE = {
    "ATL": "East", "BOS": "East", "BKN": "East", "CHA": "East",
    "CHI": "East", "CLE": "East", "DET": "East", "IND": "East",
    "MIA": "East", "MIL": "East", "NYK": "East", "ORL": "East",
    "PHI": "East", "TOR": "East", "WAS": "East",
    "DAL": "West", "DEN": "West", "GSW": "West", "HOU": "West",
    "LAC": "West", "LAL": "West", "MEM": "West", "MIN": "West",
    "NOP": "West", "OKC": "West", "PHX": "West", "POR": "West",
    "SAC": "West", "SAS": "West", "UTA": "West",
}

# ============================================================
# END SECTION: NBA Team Abbreviation Mapping
# ============================================================

# Pre-built lowercase reverse lookup: "los angeles lakers" → "LAL"
# Built once at module load time to avoid O(n²) lookups in _enrich_games_with_odds_api.
_TEAM_NAME_LOWER_TO_ABBREV: dict = {
    name.lower(): abbr for name, abbr in TEAM_NAME_TO_ABBREVIATION.items()
}


# ============================================================
# SECTION: Timestamp Functions
# Track when each piece of data was last fetched.
# ============================================================

def save_last_updated(data_type):
    """
    Save the current timestamp to last_updated.json for a given data type.

    This lets the app display "Last updated: 2026-03-06 14:30" so the
    user knows how fresh their data is.

    Args:
        data_type (str): What was updated, e.g. 'players', 'teams', 'games'
    """
    # Load existing timestamps if the file exists
    existing_timestamps = {}  # Start with empty dict

    # Check if the file already exists
    if LAST_UPDATED_JSON_PATH.exists():
        try:
            # Open and read the existing JSON file
            with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
                existing_timestamps = json.load(json_file)  # Parse JSON into dict
        except Exception:
            existing_timestamps = {}  # If file is broken, start fresh

    # Add/update the timestamp for this data type (always UTC).
    # Using UTC avoids ambiguity when the server timezone differs from ET.
    existing_timestamps[data_type] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Also save an "is_live" flag to indicate real data is loaded
    existing_timestamps["is_live"] = True

    # Write the updated timestamps back to the file
    try:
        with open(LAST_UPDATED_JSON_PATH, "w") as json_file:
            # indent=2 makes the JSON file human-readable with indentation
            json.dump(existing_timestamps, json_file, indent=2)
    except Exception as error:
        # If we can't save, just print a warning — it's not critical
        _logger.warning(f"Warning: Could not save timestamp: {error}")


def _invalidate_data_caches():
    """
    Bust all st.cache_data caches for CSV loaders in data_manager.py.

    Called after writing fresh data to disk so the next Streamlit read
    picks up the new file content instead of a stale in-memory copy.
    Imported lazily to avoid circular imports (live_data_fetcher is
    loaded early in the Python import chain).

    BEGINNER NOTE: Streamlit's @st.cache_data caches function results
    in memory.  We must call .clear() after writing new CSV data
    so the cache doesn't serve the old data.
    """
    try:
        from data.data_manager import (  # noqa: C0415 (lazy import intentional)
            load_players_data,
            load_teams_data,
            load_defensive_ratings_data,
            load_props_data,
            load_injury_status,
        )
        load_players_data.clear()
        load_teams_data.clear()
        load_defensive_ratings_data.clear()
        load_props_data.clear()
        load_injury_status.clear()
        _logger.debug("Streamlit data caches cleared after CSV update.")
    except Exception:
        pass  # Cache clearing is best-effort — never block a data fetch


def load_last_updated():
    """
    Load all timestamps from last_updated.json.

    Returns:
        dict: Timestamps for each data type, or empty dict if no file.

    Example return value:
        {
            "players": "2026-03-06T14:30:00",
            "teams": "2026-03-06T14:31:30",
            "is_live": True
        }
    """
    # If no file exists, return empty dict (no data has been fetched)
    if not LAST_UPDATED_JSON_PATH.exists():
        return {}  # Empty dict means no live data yet

    try:
        # Open and parse the JSON file
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            return json.load(json_file)  # Returns a dictionary
    except Exception:
        return {}  # If file is broken, return empty dict

# ============================================================
# END SECTION: Timestamp Functions
# ============================================================


# ============================================================
# SECTION: Helper Utilities
# Small internal helpers used by multiple fetcher functions.
# ============================================================

def _parse_win_loss_record(record_str):
    """
    Parse a win-loss record string like '15-8' into (wins, losses).

    Args:
        record_str (str): A string in the format 'W-L', e.g. '15-8'

    Returns:
        tuple: (wins: int, losses: int). Returns (0, 0) on failure.
    """
    try:
        parts = str(record_str or "0-0").split("-")
        wins = int(parts[0]) if parts else 0
        losses = int(parts[1]) if len(parts) > 1 else 0
        return wins, losses
    except (ValueError, IndexError):
        return 0, 0


def _utc_to_et_display(game_time_utc):
    """
    Convert a UTC ISO timestamp string to Eastern Time display string.

    Determines whether to apply EST (-5) or EDT (-4) offset based on
    the current date using Python's time module DST flag.

    Args:
        game_time_utc (str): ISO timestamp like '2026-03-06T23:30:00Z'

    Returns:
        str: Time string like '7:30 PM ET', or '' on failure.
    """
    if not game_time_utc:
        return ""
    try:
        # Determine current ET offset using DST flag
        import time as _time_mod
        dst_active = bool(_time_mod.localtime().tm_isdst)
        et_offset_hours = -4 if dst_active else -5  # EDT or EST

        utc_dt = datetime.datetime.fromisoformat(
            game_time_utc.replace("Z", "+00:00")
        )
        et_dt = utc_dt + datetime.timedelta(hours=et_offset_hours)
        # Use %I:%M %p for cross-platform compatibility (no %-I)
        time_str = et_dt.strftime("%I:%M %p ET").lstrip("0")
        return time_str
    except Exception:
        return ""

# ============================================================
# END SECTION: Helper Utilities
# ============================================================


# ============================================================
# ============================================================
# SECTION: Today's Games Fetcher
# Fetches which NBA games are being played today via ClearSports API.
# ============================================================

def _fetch_team_records():
    """
    Fetch team records (W-L) from ClearSports API team stats.

    Returns:
        dict: Maps team abbreviation → {wins, losses, streak, ...}.
              Returns empty dict if the fetch fails.
    """
    try:
        from data.clearsports_client import fetch_team_stats as _cs_teams
        teams = _cs_teams()
        records = {}
        for t in teams:
            abbrev = str(t.get("team_abbreviation", "")).upper().strip()
            if abbrev:
                records[abbrev] = {
                    "wins": int(t.get("wins", 0) or 0),
                    "losses": int(t.get("losses", 0) or 0),
                    "streak": "",
                    "home_record": "0-0",
                    "away_record": "0-0",
                    "conf_rank": 0,
                }
        return records
    except Exception as err:
        _logger.warning(f"Could not fetch team records (non-fatal): {err}")
        return {}


def _build_formatted_game(home_abbrev, away_abbrev, home_team_name, away_team_name,
                           game_time_et, arena_display, team_records):
    """
    Build the standardised game dict used throughout the app.

    Args:
        home_abbrev (str): Home team abbreviation.
        away_abbrev (str): Away team abbreviation.
        home_team_name (str): Full home team name.
        away_team_name (str): Full away team name.
        game_time_et (str): Game time display string (ET).
        arena_display (str): Arena name.
        team_records (dict): Lookup dict from _fetch_team_records().

    Returns:
        dict: Standardised game dict.
    """
    home_rec = team_records.get(home_abbrev, {})
    away_rec = team_records.get(away_abbrev, {})

    return {
        "home_team":     home_abbrev,
        "away_team":     away_abbrev,
        "home_team_name": home_team_name,
        "away_team_name": away_team_name,
        "game_time_et":  game_time_et,
        "arena":         arena_display,
        "home_wins":     home_rec.get("wins", 0),
        "home_losses":   home_rec.get("losses", 0),
        "away_wins":     away_rec.get("wins", 0),
        "away_losses":   away_rec.get("losses", 0),
        "home_streak":   home_rec.get("streak", ""),
        "away_streak":   away_rec.get("streak", ""),
        "home_record":   home_rec.get("home_record", "0-0"),
        "away_record":   away_rec.get("away_record", "0-0"),
        "home_conf_rank": home_rec.get("conf_rank", 0),
        "away_conf_rank": away_rec.get("conf_rank", 0),
        "game_id":       "",
        "vegas_spread":  0,
        "game_total":    220,
    }


def _deduplicate_games(games: list) -> list:
    """Remove duplicate games by (home_team, away_team) pair."""
    seen = set()
    unique = []
    for g in games:
        key = (g.get("home_team", "").upper(), g.get("away_team", "").upper())
        if key not in seen and key[0] and key[1]:
            seen.add(key)
            unique.append(g)
    return unique


def _enrich_games_with_odds_api(games: list) -> list:
    """
    Enrich a list of game dicts with consensus Vegas lines from The Odds API.

    For each game, computes the median spread/total/moneyline across all
    bookmakers (DraftKings, FanDuel, BetMGM, Caesars, etc.) and:
      - Fills in ``vegas_spread`` when ClearSports returned 0 or None
      - Fills in ``game_total`` when ClearSports returned 0 or 220 (default)
      - Adds ``moneyline_home``, ``moneyline_away``, ``consensus_spread``,
        ``consensus_total``, ``bookmaker_count`` to every game dict

    Falls back gracefully — if The Odds API key is missing or the call
    fails, the original games list is returned unchanged.

    Args:
        games: List of game dicts from ClearSports (or anywhere).

    Returns:
        list: Same games, enriched in-place with consensus odds fields.
    """
    if not games:
        return games

    try:
        from data.odds_api_client import get_consensus_odds as _get_consensus
        consensus_map = _get_consensus()  # uses session state / env key
    except Exception as exc:
        _logger.debug("_enrich_games_with_odds_api: Odds API unavailable — %s", exc)
        return games

    if not consensus_map:
        return games

    # Build abbrev → consensus entry using pre-built lowercase reverse lookup.
    # The Odds API uses full team names (e.g. "Los Angeles Lakers"),
    # so we normalise them through _TEAM_NAME_LOWER_TO_ABBREV (built once at
    # module load time for O(1) lookups).
    abbrev_consensus: dict = {}
    for full_name, entry in consensus_map.items():
        name_lower = full_name.lower().strip()
        abbrev = (_TEAM_NAME_LOWER_TO_ABBREV.get(name_lower) or "").upper().strip()
        if abbrev:
            abbrev_consensus[abbrev] = entry
        else:
            # Try partial-match fallback (rare: Odds API name slightly different)
            for tm_lower, tm_abbr in _TEAM_NAME_LOWER_TO_ABBREV.items():
                if name_lower in tm_lower or tm_lower in name_lower:
                    abbrev_consensus[tm_abbr] = entry
                    break

    for game in games:
        home = str(game.get("home_team", "")).upper().strip()
        entry = abbrev_consensus.get(home)
        if entry is None:
            away = str(game.get("away_team", "")).upper().strip()
            entry = abbrev_consensus.get(away)
        if entry is None:
            continue

        cs = entry.get("consensus_spread")
        ct = entry.get("consensus_total")

        # Always add the consensus/moneyline fields for downstream use
        game["consensus_spread"]  = cs
        game["consensus_total"]   = ct
        game["moneyline_home"]    = entry.get("moneyline_home")
        game["moneyline_away"]    = entry.get("moneyline_away")
        game["bookmaker_count"]   = entry.get("bookmaker_count", 0)
        game["spread_range"]      = entry.get("spread_range", (None, None))
        game["total_range"]       = entry.get("total_range", (None, None))

        # Override ClearSports spread/total when it's missing (0 or default 220)
        current_spread = float(game.get("vegas_spread") or 0)
        current_total  = float(game.get("game_total")  or 0)

        if cs is not None and current_spread == 0.0:
            game["vegas_spread"] = round(float(cs), 1)

        if ct is not None and (current_total == 0.0 or current_total == 220.0):
            game["game_total"] = round(float(ct), 1)

    _logger.info(
        "_enrich_games_with_odds_api: enriched %d game(s) with Odds API consensus.",
        sum(1 for g in games if g.get("bookmaker_count", 0) > 0),
    )
    return games


def _enrich_games_with_standings(games: list) -> list:
    """
    Enrich game dicts with ClearSports standings data (W-L, streak, rank).

    Populates ``home_wins``, ``home_losses``, ``home_streak``,
    ``away_wins``, ``away_losses``, ``away_streak`` on every game dict
    when data is available from ClearSports standings.  Existing non-zero
    values are never overwritten (ClearSports game data takes priority).

    Falls back gracefully — returns the original list unchanged if the
    API key is missing or the fetch fails.

    Args:
        games: List of game dicts.

    Returns:
        list: Same games, enriched in-place with standings fields.
    """
    if not games:
        return games

    try:
        from data.clearsports_client import fetch_standings as _cs_st
        standings_list = _cs_st() or []
    except Exception as exc:
        _logger.debug("_enrich_games_with_standings: standings unavailable — %s", exc)
        return games

    if not standings_list:
        return games

    # Build abbrev → standings entry lookup
    standings_map: dict = {
        str(s.get("team_abbreviation", "")).upper(): s
        for s in standings_list
    }

    enriched = 0
    for game in games:
        for side in ("home", "away"):
            abbrev = str(game.get(f"{side}_team", "")).upper().strip()
            entry  = standings_map.get(abbrev)
            if not entry:
                continue
            # Only fill in if the current value is absent / zero (ClearSports game data wins)
            if not game.get(f"{side}_wins"):
                game[f"{side}_wins"]   = entry.get("wins", 0)
            if not game.get(f"{side}_losses"):
                game[f"{side}_losses"] = entry.get("losses", 0)
            if not game.get(f"{side}_streak"):
                game[f"{side}_streak"] = entry.get("streak", "")
            # Always add extended standings fields for Game Report and other pages
            game[f"{side}_conference_rank"] = entry.get("conference_rank", 0)
            game[f"{side}_conference"]      = entry.get("conference", "")
            game[f"{side}_win_pct"]         = entry.get("win_pct", 0.0)
            game[f"{side}_last_10"]         = (
                f"{entry.get('last_10_wins', 0)}-{entry.get('last_10_losses', 0)}"
            )
        enriched += 1

    _logger.info(
        "_enrich_games_with_standings: enriched %d game(s) with standings.", enriched
    )
    return games


def fetch_todays_games():
    """
    Fetch tonight's NBA games via ClearSports API, then enrich with
    consensus Vegas lines from The Odds API (spread, total, moneyline).

    Returns:
        list of dict: Tonight's games, each with home_team, away_team,
                      team records, and Vegas lines from Odds API consensus.
                      Returns empty list if all fetches fail.
    """
    games = []
    try:
        from data.clearsports_client import fetch_games_today as _cs_games
        games = _cs_games() or []
        if games:
            _logger.info(f"ClearSports: {len(games)} game(s) found.")
            games = _deduplicate_games(games)
    except Exception as err:
        _logger.warning(f"ClearSports games fetch failed: {err}")

    # Enrich every game with Odds API consensus lines (moneyline + spread + total)
    games = _enrich_games_with_odds_api(games)

    # Enrich with ClearSports standings (W-L, streak, conference rank)
    games = _enrich_games_with_standings(games)

    if not games:
        _logger.warning("No games available from any source.")

    return games

# ============================================================
# END SECTION: Today's Games Fetcher
# ============================================================
# ============================================================


# ============================================================
# ============================================================
# SECTION: Targeted Roster-Based Data Fetcher
# Fetches players only for teams playing today via ClearSports API.
# ============================================================

def fetch_todays_players_only(todays_games, progress_callback=None, precomputed_injury_map=None):
    """
    Fetch player stats ONLY for teams playing today via ClearSports API.

    Streamlined pipeline:
    1. Identifies the teams playing today from todays_games
    2. Fetches player stats from ClearSports (filtered to today's teams)
    3. Writes to players.csv in the standard format

    Args:
        todays_games (list of dict): Tonight's games from fetch_todays_games()
        progress_callback (callable, optional): Called with (current, total, msg)
        precomputed_injury_map (dict, optional): Kept for backward compatibility.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    from data.clearsports_client import fetch_player_stats as _cs_players, fetch_rosters as _cs_rosters
    from data.roster_engine import RosterEngine as _RosterEngine

    if not todays_games:
        _logger.info("No games provided — nothing to fetch.")
        return False

    try:
        playing_team_abbrevs = set()
        for game in todays_games:
            playing_team_abbrevs.add(game.get("home_team", ""))
            playing_team_abbrevs.add(game.get("away_team", ""))
        playing_team_abbrevs.discard("")

        _logger.info(f"Fetching players for {len(playing_team_abbrevs)} teams: {sorted(playing_team_abbrevs)}")

        if progress_callback:
            progress_callback(1, 10, f"Found {len(playing_team_abbrevs)} teams. Fetching player stats...")

        # Fetch all player stats from ClearSports
        all_player_stats = _cs_players()

        if progress_callback:
            progress_callback(4, 10, f"Got {len(all_player_stats)} players. Filtering to today's teams...")

        # Filter to only players on today's teams
        filtered_players = [
            p for p in all_player_stats
            if str(p.get("team", "")).upper().strip() in playing_team_abbrevs
        ]

        if not filtered_players and all_player_stats:
            # If no team filter match, return all (may be first run with no games data)
            filtered_players = all_player_stats

        _logger.info(f"Using {len(filtered_players)} players on today's teams.")

        if progress_callback:
            progress_callback(6, 10, f"Writing {len(filtered_players)} players to CSV...")

        # Fetch injury data via RosterEngine
        injury_map = {}
        try:
            _roster_engine = _RosterEngine()
            _roster_engine.refresh(list(playing_team_abbrevs))
            injury_map = _roster_engine.get_injury_report()
        except Exception as roster_err:
            _logger.warning(f"RosterEngine injury fetch failed (non-fatal): {roster_err}")

        # Write injury status JSON
        try:
            import json as _json
            with open(INJURY_STATUS_JSON_PATH, "w") as _f:
                _json.dump(injury_map, _f, indent=2)
            save_last_updated("injuries")
        except Exception as inj_write_err:
            _logger.warning(f"Could not write injury status (non-fatal): {inj_write_err}")

        if not filtered_players:
            _logger.warning("No player stats available from ClearSports.")
            return False

        # Write players CSV
        _write_players_csv(filtered_players)
        save_last_updated("players")

        if progress_callback:
            progress_callback(10, 10, f"Done! {len(filtered_players)} players updated.")

        _logger.info(f"fetch_todays_players_only complete: {len(filtered_players)} players written.")
        return True

    except Exception as error:
        _logger.error(f"fetch_todays_players_only failed: {error}")
        return False


# END SECTION: Targeted Roster-Based Data Fetcher
# ============================================================
# ============================================================


# ============================================================
# ============================================================
# SECTION: Recent Form Fetcher
# Fetches recent game data for trend analysis.
# ============================================================

def fetch_player_recent_form(player_id, last_n_games=10):
    """
    Fetch recent form data for a specific player.

    Returns the last N game logs along with trend analysis.
    Falls back to an empty dict if ClearSports doesn't have game logs.

    Args:
        player_id (int or str): The NBA player's unique ID
        last_n_games (int): Number of recent games to analyze (default: 10)

    Returns:
        dict: Recent form data with keys:
              'games', 'recent_pts_avg', 'recent_reb_avg',
              'recent_ast_avg', 'trend', 'game_results'
              Returns empty dict if fetch fails.
    """
    try:
        from data.clearsports_client import fetch_player_game_log as _cs_log
        game_log = _cs_log(player_id, last_n_games=last_n_games)
    except Exception:
        game_log = []

    # If ClearSports doesn't provide game logs, fall back to cached data
    if not game_log and _GAME_LOG_CACHE_AVAILABLE:
        try:
            game_log = load_game_logs_from_cache(player_id) or []
            if game_log:
                game_log = game_log[:last_n_games]
        except Exception:
            game_log = []

    if not game_log:
        return {}

    try:
        def safe_avg(values):
            clean = [v for v in values if v is not None and isinstance(v, (int, float)) and math.isfinite(float(v))]
            return round(sum(clean) / len(clean), 1) if clean else 0.0

        recent = game_log[:last_n_games]
        pts_list = [float(g.get("pts", g.get("PTS", 0)) or 0) for g in recent]
        reb_list = [float(g.get("reb", g.get("REB", 0)) or 0) for g in recent]
        ast_list = [float(g.get("ast", g.get("AST", 0)) or 0) for g in recent]
        fg3m_list = [float(g.get("fg3m", g.get("FG3M", 0)) or 0) for g in recent]

        last_5_pts = pts_list[:5]
        prior_5_pts = pts_list[5:10]
        last5_avg = safe_avg(last_5_pts)
        prev5_avg = safe_avg(prior_5_pts) if prior_5_pts else last5_avg

        if prev5_avg > 0:
            trend = "hot" if last5_avg >= prev5_avg * HOT_TREND_THRESHOLD else (
                "cold" if last5_avg <= prev5_avg * COLD_TREND_THRESHOLD else "neutral"
            )
        else:
            trend = "neutral"

        trend_emoji_map = {"hot": "🔥", "cold": "❄️", "neutral": "➡️"}

        game_results = []
        for g in recent:
            game_results.append({
                "date": g.get("game_date", g.get("GAME_DATE", "")),
                "matchup": g.get("matchup", g.get("MATCHUP", "")),
                "wl": g.get("win_loss", g.get("WL", "")),
                "pts": float(g.get("pts", g.get("PTS", 0)) or 0),
                "reb": float(g.get("reb", g.get("REB", 0)) or 0),
                "ast": float(g.get("ast", g.get("AST", 0)) or 0),
                "fg3m": float(g.get("fg3m", g.get("FG3M", 0)) or 0),
                "min": float(g.get("minutes", g.get("MIN", 0)) or 0),
            })

        return {
            "games": recent,
            "recent_pts_avg": safe_avg(pts_list),
            "recent_reb_avg": safe_avg(reb_list),
            "recent_ast_avg": safe_avg(ast_list),
            "recent_fg3m_avg": safe_avg(fg3m_list),
            "trend": trend,
            "trend_emoji": trend_emoji_map.get(trend, "➡️"),
            "last_5_pts": last_5_pts,
            "last_5_pts_avg": last5_avg,
            "game_results": game_results,
            "games_played": len(recent),
        }
    except Exception as error:
        _logger.error(f"Error computing recent form for player {player_id}: {error}")
        return {}

# ============================================================
# END SECTION: Recent Form Fetcher
# ============================================================
# ============================================================


# ============================================================
# ============================================================
# SECTION: Player Stats Fetcher
# Fetches current season stats for all NBA players via ClearSports API.
# ============================================================

def fetch_player_stats(progress_callback=None):
    """
    Fetch current season player stats for all NBA players via ClearSports API.

    Writes the results to players.csv in the standard column format.

    Args:
        progress_callback (callable, optional): Called with (current, total, message).

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    from data.clearsports_client import fetch_player_stats as _cs_player_stats

    try:
        if progress_callback:
            progress_callback(1, 10, "Connecting to ClearSports API for player stats...")

        player_stats_list = _cs_player_stats()

        if progress_callback:
            progress_callback(5, 10, f"Got stats for {len(player_stats_list)} players. Writing CSV...")

        _logger.info(f"ClearSports returned {len(player_stats_list)} player stats.")

        if not player_stats_list:
            _logger.warning("ClearSports returned no player stats.")
            return False

        _write_players_csv(player_stats_list)
        save_last_updated("players")

        if progress_callback:
            progress_callback(10, 10, f"Done! {len(player_stats_list)} players saved.")

        _logger.info(f"fetch_player_stats complete: {len(player_stats_list)} players.")
        return True

    except Exception as error:
        _logger.error(f"fetch_player_stats failed: {error}")
        return False


def _write_players_csv(players):
    """Write a list of player stat dicts to players.csv in standard format."""
    if not players:
        return

    fieldnames = [
        "player_id", "name", "team", "position",
        "minutes_avg", "points_avg", "rebounds_avg", "assists_avg",
        "threes_avg", "steals_avg", "blocks_avg", "turnovers_avg",
        "ft_pct", "usage_rate",
        "points_std", "rebounds_std", "assists_std", "threes_std",
        "steals_std", "blocks_std", "turnovers_std",
    ]

    import csv as _csv
    with open(PLAYERS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in players:
            row = {k: p.get(k, "") for k in fieldnames}
            for numeric_field in fieldnames[4:]:
                if not row[numeric_field] and row[numeric_field] != 0:
                    row[numeric_field] = 0.0
            writer.writerow(row)

    _logger.info(f"Wrote {len(players)} players to {PLAYERS_CSV_PATH}")

# ============================================================
# END SECTION: Player Stats Fetcher
# ============================================================
# ============================================================


# ============================================================
# ============================================================
# SECTION: Team Stats Fetcher
# Fetches current season team stats via ClearSports API.
# ============================================================

def fetch_team_stats(progress_callback=None):
    """
    Fetch current season team stats via ClearSports API.

    Pulls pace, offensive rating (ORTG), defensive rating (DRTG),
    and wins/losses for all 30 NBA teams. Writes to teams.csv and
    defensive_ratings.csv.

    Args:
        progress_callback (callable, optional): Progress update function.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    from data.clearsports_client import fetch_team_stats as _cs_team_stats

    try:
        if progress_callback:
            progress_callback(1, 6, "Fetching team stats from ClearSports API...")

        team_stats_list = _cs_team_stats()

        if progress_callback:
            progress_callback(3, 6, f"Got {len(team_stats_list)} teams. Building CSV rows...")

        _logger.info(f"ClearSports returned {len(team_stats_list)} team stats.")

        if not team_stats_list:
            _logger.warning("ClearSports returned no team stats.")
            return False

        # Write teams.csv
        teams_fieldnames = [
            "team_abbreviation", "team_name",
            "wins", "losses", "win_pct",
            "pace", "offensive_rating", "defensive_rating",
            "points_pg", "opponent_points_pg",
            "field_goal_pct", "three_point_pct",
            "rebounds_pg", "assists_pg", "turnovers_pg",
            "home_wins", "home_losses", "away_wins", "away_losses",
        ]

        import csv as _csv
        with open(TEAMS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=teams_fieldnames, extrasaction="ignore")
            writer.writeheader()
            for team in team_stats_list:
                row = {k: team.get(k, "") for k in teams_fieldnames}
                # Compute win_pct if not provided
                if not row.get("win_pct"):
                    wins = int(row.get("wins", 0) or 0)
                    losses = int(row.get("losses", 0) or 0)
                    total = wins + losses
                    row["win_pct"] = round(wins / total, 3) if total else 0.0
                writer.writerow(row)

        save_last_updated("teams")

        # Write defensive_ratings.csv
        if progress_callback:
            progress_callback(5, 6, "Writing defensive ratings CSV...")

        def_fieldnames = [
            "team_abbreviation", "defensive_rating", "pace",
            "opponent_points_pg", "opponent_field_goal_pct",
            "pg_def_rating", "sg_def_rating", "sf_def_rating",
            "pf_def_rating", "c_def_rating",
        ]

        with open(DEFENSIVE_RATINGS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=def_fieldnames, extrasaction="ignore")
            writer.writeheader()
            for team in team_stats_list:
                row = {
                    "team_abbreviation": team.get("team_abbreviation", ""),
                    "defensive_rating": team.get("defensive_rating", 110),
                    "pace": team.get("pace", 100),
                    "opponent_points_pg": team.get("opponent_points_pg", team.get("points_pg", 110)),
                    "opponent_field_goal_pct": team.get("opponent_field_goal_pct", 0.46),
                    "pg_def_rating": team.get("defensive_rating", 110),
                    "sg_def_rating": team.get("defensive_rating", 110),
                    "sf_def_rating": team.get("defensive_rating", 110),
                    "pf_def_rating": team.get("defensive_rating", 110),
                    "c_def_rating": team.get("defensive_rating", 110),
                }
                writer.writerow(row)

        save_last_updated("teams")

        if progress_callback:
            progress_callback(6, 6, f"Done! {len(team_stats_list)} teams saved.")

        _logger.info(f"fetch_team_stats complete: {len(team_stats_list)} teams.")
        return True

    except Exception as error:
        _logger.error(f"fetch_team_stats failed: {error}")
        return False


def fetch_defensive_ratings(force=False, progress_callback=None):
    """
    Auto-update defensive_ratings.csv from team stats.

    Delegates to fetch_team_stats() which now includes defensive ratings.

    Args:
        force (bool): If True, always refresh. If False, skip if recent.
        progress_callback (callable, optional): Progress callback.

    Returns:
        bool: True if successful, False otherwise.
    """
    return fetch_team_stats(progress_callback=progress_callback)


def get_teams_staleness_warning():
    """
    Return a warning string if teams.csv is stale (> 12 hours old).

    Returns:
        str or None: Warning message, or None if data is fresh.
    """
    try:
        timestamps = load_last_updated()
        teams_ts = timestamps.get("teams")
        if not teams_ts:
            return "Team stats have never been fetched. Click Update Teams on the Data Feed page."
        dt = datetime.datetime.fromisoformat(teams_ts)
        age_hours = (datetime.datetime.now() - dt).total_seconds() / 3600
        if age_hours > 12:
            return f"Team stats are {age_hours:.0f} hours old. Consider refreshing on the Data Feed page."
    except Exception:
        pass
    return None

# ============================================================
# END SECTION: Team Stats Fetcher
# ============================================================
# ============================================================


# ============================================================
# ============================================================


# ============================================================
# ============================================================
# SECTION: Player Game Log Fetcher
# Fetches the last N games for a specific player via ClearSports API.
# ============================================================

def fetch_player_game_log(player_id, last_n_games=20):
    """
    Fetch the last N game logs for a specific player.

    Args:
        player_id (int or str): The NBA player's unique ID
        last_n_games (int): How many recent games to return (default: 20)

    Returns:
        list of dict: Recent game stats, newest game first.
                      Returns empty list if the fetch fails.
    """
    try:
        from data.clearsports_client import fetch_player_game_log as _cs_log
        games = _cs_log(player_id, last_n_games=last_n_games)
        if games:
            return games
    except Exception as err:
        _logger.warning(f"ClearSports game log fetch failed for player {player_id}: {err}")

    # Try local cache as fallback
    if _GAME_LOG_CACHE_AVAILABLE:
        try:
            cached = load_game_logs_from_cache(player_id)
            if cached:
                return cached[:last_n_games]
        except Exception:
            pass

    return []

# ============================================================
# END SECTION: Player Game Log Fetcher
# ============================================================
# ============================================================


# ============================================================
# SECTION: Full Update Function
# Runs all fetchers in sequence to update everything at once.
# ============================================================

def fetch_all_data(progress_callback=None, targeted=False, todays_games=None):
    """
    Fetch ALL live data: player stats, team stats, and defensive ratings.

    Args:
        progress_callback (callable, optional): Progress function.
            Called with (current_step, total_steps, message).
        targeted (bool): If True and todays_games is provided, only fetch
            players on teams playing today (faster, uses current rosters).
        todays_games (list, optional): Required when targeted=True.

    Returns:
        dict: Results showing what succeeded and what failed.
            Example: {'players': True, 'teams': True}
    """
    results = {
        "players": False,
        "teams": False,
    }

    _logger.info("Starting full data update...")

    # --------------------------------------------------------
    # Step 1: Fetch player stats (targeted or full)
    # --------------------------------------------------------

    if progress_callback:
        progress_callback(0, 20, "Starting player stats update...")

    if targeted and todays_games:
        # Targeted fetch: only players on today's teams
        def player_progress(current, total, message):
            if progress_callback:
                progress_callback(current, 20, f"[Players] {message}")
        results["players"] = fetch_todays_players_only(
            todays_games, progress_callback=player_progress
        )
    else:
        # Full fetch: all ~500 NBA players
        def player_progress(current, total, message):
            if progress_callback:
                progress_callback(current, 20, f"[Players] {message}")
        results["players"] = fetch_player_stats(progress_callback=player_progress)

    _logger.info("Player stats update complete. Starting team stats update...")

    # --------------------------------------------------------
    # Step 2: Fetch team stats
    # --------------------------------------------------------

    def team_progress(current, total, message):
        if progress_callback:
            progress_callback(10 + int(10 * current / max(total, 1)), 20, f"[Teams] {message}")

    results["teams"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(20, 20, "✅ All data updated!")

    _logger.info(f"Full update complete. Results: {results}")
    return results

# ============================================================
# END SECTION: Full Update Function
# ============================================================


# ============================================================
# SECTION: One-Click Today's Data Fetcher
# Fetches games, today's team rosters+stats, and team stats
# in a single call — the "Auto-Load" button entry point.
# ============================================================

def fetch_all_todays_data(progress_callback=None):
    """
    One-click function: fetch tonight's games, player stats for those
    teams, team stats, and player injury/availability status.

    Steps:
        1. Fetch tonight's games (ScoreBoard)
        2. Fetch current rosters + player stats (includes injury data via
           RosterEngine — no separate injury fetch step needed)
        3. Fetch team stats for the analysis engine

    Args:
        progress_callback (callable, optional): Called with (current, total, msg).

    Returns:
        dict: {
            "games": list of game dicts (empty list if none),
            "players_updated": bool,
            "teams_updated": bool,
            "injury_status": dict,  # player_name_lower → status_dict
        }
    """
    results = {
        "games": [],
        "players_updated": False,
        "teams_updated": False,
        "injury_status": {},
    }

    # --------------------------------------------------------
    # Step 1: Fetch tonight's games
    # --------------------------------------------------------
    if progress_callback:
        progress_callback(0, 40, "Step 1/3 — Fetching tonight's games...")

    games = fetch_todays_games()
    results["games"] = games

    if not games:
        _logger.info("fetch_all_todays_data: No games found for tonight.")
        return results

    if progress_callback:
        progress_callback(2, 40, f"Step 1/3 ✅ Found {len(games)} game(s). Fetching players + injury data...")

    # --------------------------------------------------------
    # Step 2: Fetch player stats for tonight's teams.
    # RosterEngine.refresh() is called inside fetch_todays_players_only(),
    # providing injury data and rosters in one pass.  The injury map is
    # written to INJURY_STATUS_JSON_PATH so it can be loaded after this call.
    # --------------------------------------------------------
    def player_progress(current, total, message):
        if progress_callback:
            # Progress range for Step 2: steps 2-29 out of 40
            scaled = 2 + int(27 * current / max(total, 1))
            progress_callback(scaled, 40, f"Step 2/3 — {message}")

    results["players_updated"] = fetch_todays_players_only(
        games,
        progress_callback=player_progress,
    )

    # Load the injury map written by fetch_todays_players_only
    if results["players_updated"]:
        try:
            from data.data_manager import load_injury_status as _load_inj
            results["injury_status"] = _load_inj()
        except Exception as _inj_load_err:
            _logger.info(f"fetch_all_todays_data: could not load injury map after player fetch: {_inj_load_err}")

    if progress_callback:
        status = "✅" if results["players_updated"] else "⚠️"
        progress_callback(29, 40, f"Step 2/3 {status} Player stats done. Fetching team stats...")

    # --------------------------------------------------------
    # Step 3: Fetch team stats
    # --------------------------------------------------------
    def team_progress(current, total, message):
        if progress_callback:
            # Progress range for Step 3: steps 29-40 out of 40
            scaled = 29 + int(11 * current / max(total, 1))
            progress_callback(scaled, 40, f"Step 3/3 — {message}")

    results["teams_updated"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(40, 40, "✅ All done! Games, players, team stats, and injury status loaded.")

    # --------------------------------------------------------
    # Bonus: Record market movement snapshots from Odds API
    # This runs silently after the main data fetch — it's optional
    # and won't block or fail the main results.
    # --------------------------------------------------------
    _record_odds_api_snapshots(results["games"])

    # --------------------------------------------------------
    # Bonus: Refresh historical game logs + CLV closing lines
    # Runs silently — will skip gracefully if API key is missing.
    # --------------------------------------------------------
    try:
        refresh_historical_data_for_tonight(games=results["games"])
    except Exception as _hist_exc:
        _logger.debug("fetch_all_todays_data: historical refresh skipped — %s", _hist_exc)

    # --------------------------------------------------------
    # Bonus: Pre-load standings and news into session state
    # so Game Report and other pages can display them immediately
    # without a separate user action.
    # --------------------------------------------------------
    try:
        _standings = fetch_standings()
        if _standings:
            results["standings"] = _standings
            try:
                import streamlit as _st_snap
                _st_snap.session_state["league_standings"] = _standings
            except Exception:
                pass
    except Exception as _std_exc:
        _logger.debug("fetch_all_todays_data: standings pre-load skipped — %s", _std_exc)

    try:
        _news = fetch_player_news(limit=30)
        if _news:
            results["news"] = _news
            try:
                import streamlit as _st_news
                _st_news.session_state["player_news"] = _news
            except Exception:
                pass
    except Exception as _news_exc:
        _logger.debug("fetch_all_todays_data: news pre-load skipped — %s", _news_exc)

    players_updated = results["players_updated"]
    teams_updated = results["teams_updated"]
    games_count = len(results["games"])
    _logger.info(f"fetch_all_todays_data complete: players_updated={players_updated}, "
          f"teams_updated={teams_updated}, games={games_count}")
    return results

# ============================================================
# END SECTION: One-Click Today's Data Fetcher
# ============================================================


# ============================================================
# SECTION: Team Roster Cache
# Delegates entirely to RosterEngine — the single authoritative
# source for all roster data (nba_api CommonTeamRoster).
# ============================================================


def fetch_active_rosters(team_abbrevs=None, progress_callback=None):
    """
    Fetch current active rosters for the given teams.

    Delegates to RosterEngine (nba_api CommonTeamRoster) — the single
    authoritative source — replacing the old direct CommonTeamRoster calls.

    Args:
        team_abbrevs (list of str, optional): Team abbreviations to fetch.
            If None, returns an empty dict (caller should specify teams).
        progress_callback (callable, optional): Accepted for API compatibility
            but not used (RosterEngine handles its own progress internally).

    Returns:
        dict: {team_abbrev: [player_name, ...]}
    """
    from data.roster_engine import RosterEngine
    engine = RosterEngine()
    engine.refresh(team_abbrevs)
    result = {}
    for abbrev in (team_abbrevs or []):
        result[abbrev] = engine.get_active_roster(abbrev)
    return result


def get_cached_roster(team_abbrev):
    """
    Return the active roster for a team via RosterEngine.

    Args:
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        list of str: Player names on the active roster, or empty list.
    """
    return fetch_active_rosters([team_abbrev]).get(team_abbrev.upper(), [])

# ============================================================
# END SECTION: Team Roster Cache
# ============================================================


# ============================================================
# SECTION: Dynamic CV Estimation Helper (W10)
# Returns tier-based coefficients of variation for fallback
# std deviation estimates when live game logs are unavailable.
# ============================================================

def _dynamic_cv_for_live_fetch(stat_type, stat_avg):
    """
    Get a dynamic coefficient of variation for fallback std estimation. (W10)

    Delegates to `_get_dynamic_cv()` in projections.py to avoid duplicating
    the tier-threshold logic. This ensures both the live fetcher and the
    projection engine use identical CV tiers.

    Args:
        stat_type (str): 'points', 'rebounds', 'assists', 'threes', etc.
        stat_avg (float): Player's season average for this stat.

    Returns:
        float: Coefficient of variation to multiply against stat_avg.
    """
    # Import here to avoid a circular import at module load time.
    # (live_data_fetcher is imported by data_manager which may be imported
    # before engine.projections, so this lazy import is intentional.)
    from engine.projections import _get_dynamic_cv
    return _get_dynamic_cv(stat_type, stat_avg)

# ============================================================
# END SECTION: Dynamic CV Estimation Helper
# ============================================================


# ============================================================
# SECTION: Odds API Market Movement Snapshot Recorder
# Records prop line snapshots for market movement tracking.
# Called automatically by fetch_all_todays_data() each time
# the data is refreshed, building a historical trail for line
# movement analysis.
# ============================================================

def _record_odds_api_snapshots(games: list | None = None) -> None:
    """
    Record prop line snapshots from The Odds API for market movement tracking.

    Fetches current player props from all bookmakers and stores them via
    engine.market_movement.track_line_snapshot(). These snapshots build
    the historical trail used by engine.market_movement.detect_line_movement()
    to identify sharp money, steam moves, and line drift.

    This function is non-blocking: all errors are caught and logged. It
    will silently skip if no Odds API key is configured.

    Args:
        games: Optional list of game dicts (for logging context only).
    """
    try:
        from data.odds_api_client import fetch_player_props as _fetch_props
        from engine.market_movement import track_line_snapshot as _snapshot
    except ImportError:
        return  # Engine or client not available — skip silently

    try:
        props = _fetch_props()
        if not props:
            return

        recorded = 0
        for prop in props:
            player_name = prop.get("player_name", "")
            stat_type   = prop.get("stat_type", "")
            platform    = prop.get("platform", "")
            line        = prop.get("line")

            if not (player_name and stat_type and line is not None):
                continue

            try:
                line_val = float(line)
                _snapshot(
                    player_name=player_name,
                    stat_type=stat_type,
                    platform=platform,
                    line_value=line_val,
                )
                recorded += 1
            except Exception:
                continue

        _logger.info(
            "_record_odds_api_snapshots: recorded %d prop line snapshots.", recorded
        )
    except Exception as exc:
        _logger.debug("_record_odds_api_snapshots: skipped — %s", exc)


def fetch_standings(progress_callback=None) -> list[dict]:
    """
    Fetch current NBA standings from ClearSports API.

    Returns a list of team standing entries including conference rank,
    win-loss record, home/away splits, last-10 record, and streak.
    Falls back to an empty list if the API is unavailable.

    Args:
        progress_callback: Optional callable(current, total, message).

    Returns:
        list[dict]: Each entry has team_abbreviation, conference,
                    conference_rank, wins, losses, win_pct, streak, etc.
    """
    if progress_callback:
        progress_callback(0, 10, "Fetching NBA standings from ClearSports...")

    try:
        from data.clearsports_client import fetch_standings as _cs_standings
        standings = _cs_standings()
        if progress_callback:
            progress_callback(10, 10, f"Standings loaded ({len(standings)} teams).")
        return standings
    except Exception as exc:
        _logger.warning("fetch_standings failed: %s", exc)
        return []


def fetch_player_news(player_name: str | None = None, limit: int = 20) -> list[dict]:
    """
    Fetch recent NBA news from ClearSports API, optionally filtered to
    a specific player.

    Useful for enriching Joseph M. Smith's contextual commentary with
    the latest injury updates, trade news, and performance notes.

    Args:
        player_name: Optional player name to filter results.
        limit:       Maximum number of news items to return.

    Returns:
        list[dict]: News items with title, body, player_name, team_abbreviation,
                    published_at, category, impact.
    """
    try:
        from data.clearsports_client import fetch_news as _cs_news
        all_news = _cs_news(limit=limit)
        if player_name:
            target = player_name.lower().strip()
            all_news = [
                item for item in all_news
                if target in item.get("player_name", "").lower()
                or target in item.get("title", "").lower()
            ]
        return all_news
    except Exception as exc:
        _logger.warning("fetch_player_news failed: %s", exc)
        return []

# ============================================================
# END SECTION: Odds API Market Movement Snapshot Recorder
# ============================================================


# ============================================================
# SECTION: Historical Data Refresher
# Auto-populates game log cache and updates CLV closing lines
# using ClearSports player game logs + Odds API completed scores.
# ============================================================

def refresh_historical_data_for_tonight(
    games: list | None = None,
    last_n_games: int = 30,
    progress_callback=None,
) -> dict:
    """
    Auto-fetch historical game logs for all players in tonight's lineup
    and update CLV closing lines from recently completed games.

    This function is the "historical data refresh" entry point. It:

    1. Resolves tonight's playing teams from ``games`` (or session state)
    2. Fetches each player's recent game log from ClearSports API
    3. Saves results to ``data/game_log_cache.py`` for the Backtester
    4. Calls ``engine/clv_tracker.auto_update_closing_lines()`` to close
       open CLV records using today's Odds API prop lines (closing lines)

    Args:
        games:             List of tonight's game dicts.  If None, tries
                           ``st.session_state["todays_games"]``.
        last_n_games:      How many recent games to fetch per player (30).
        progress_callback: Optional callable(current, total, message).

    Returns:
        dict: {
            "players_refreshed": int,
            "clv_updated":       int,
            "errors":            int,
        }
    """
    results = {"players_refreshed": 0, "clv_updated": 0, "errors": 0}

    # Resolve tonight's games
    if games is None:
        try:
            import streamlit as _st
            games = _st.session_state.get("todays_games", [])
        except Exception:
            games = []

    if not games:
        _logger.debug("refresh_historical_data_for_tonight: no games — skipping")
        return results

    # Collect all players from tonight's teams
    playing_teams: set = set()
    for g in games:
        for key in ("home_team", "away_team"):
            t = str(g.get(key, "")).upper().strip()
            if t:
                playing_teams.add(t)

    if not playing_teams:
        return results

    # Load player data (from CSV) to get player_ids
    try:
        from data.data_manager import load_players_data as _load_players
        all_players = _load_players()
    except Exception as exc:
        _logger.warning("refresh_historical_data_for_tonight: could not load players — %s", exc)
        return results

    tonight_players = [
        p for p in all_players
        if str(p.get("team", "")).upper().strip() in playing_teams
        and p.get("player_id")
    ]

    if not tonight_players:
        _logger.debug("refresh_historical_data_for_tonight: no players with IDs found")
        return results

    total = len(tonight_players)
    if progress_callback:
        progress_callback(0, total, f"Fetching historical logs for {total} player(s)…")

    # Batch-fetch game logs from ClearSports
    try:
        from data.clearsports_client import fetch_season_game_logs_batch as _batch
        from data.game_log_cache import save_game_logs_to_cache as _save_cache

        player_id_pairs = [
            (p.get("name", ""), p.get("player_id"))
            for p in tonight_players
            if p.get("player_id")
        ]

        logs_map = _batch(player_id_pairs, last_n_games=last_n_games)

        for idx, (player_name, logs) in enumerate(logs_map.items()):
            if logs:
                try:
                    _save_cache(player_name, logs)
                    results["players_refreshed"] += 1
                except Exception as save_exc:
                    _logger.debug(
                        "refresh_historical_data_for_tonight: cache save failed for %s — %s",
                        player_name, save_exc,
                    )
                    results["errors"] += 1
            if progress_callback:
                progress_callback(idx + 1, total, f"Cached logs for {player_name}")

    except Exception as exc:
        _logger.warning("refresh_historical_data_for_tonight: batch fetch failed — %s", exc)
        results["errors"] += 1

    # Auto-update CLV closing lines from Odds API
    try:
        from engine.clv_tracker import auto_update_closing_lines as _clv_update
        clv_result = _clv_update(days_back=1)
        results["clv_updated"] = clv_result.get("updated", 0)
    except Exception as exc:
        _logger.debug("refresh_historical_data_for_tonight: CLV update skipped — %s", exc)

    _logger.info(
        "refresh_historical_data_for_tonight: players_refreshed=%d, clv_updated=%d, errors=%d",
        results["players_refreshed"], results["clv_updated"], results["errors"],
    )
    return results

# ============================================================
# END SECTION: Historical Data Refresher
# ============================================================
