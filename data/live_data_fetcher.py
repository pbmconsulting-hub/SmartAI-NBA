# ============================================================
# FILE: data/live_data_fetcher.py
# PURPOSE: Fetch live, real NBA data from the nba_api library.
#          Pulls today's games, player stats, team stats, and
#          player game logs. Saves everything to CSV files so
#          the rest of the app works without any changes.
# CONNECTS TO: pages/8_🔄_Update_Data.py, data/data_manager.py
# CONCEPTS COVERED: APIs, rate limiting, CSV writing, error handling
#
# BEGINNER NOTE: An API (Application Programming Interface) is a
# way for programs to talk to each other. nba_api is a free Python
# library that talks to the NBA's official stats website for us.
# We never need an API key — it's completely free to use!
# ============================================================

# Standard library imports (no install needed — built into Python)
import csv          # For reading and writing CSV files
import json         # For reading and writing JSON files (timestamps, etc.)
import time         # For adding delays between API calls
import datetime     # For timestamps and date handling
import statistics   # For calculating standard deviations
from pathlib import Path  # Modern, cross-platform file path handling

# ============================================================
# SECTION: File Path Constants
# Same data directory as data_manager.py
# ============================================================

# Get the directory where this file lives (the 'data' folder)
DATA_DIRECTORY = Path(__file__).parent

# Paths to each CSV file we will write
PLAYERS_CSV_PATH = DATA_DIRECTORY / "sample_players.csv"       # Player stats output
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"                   # Team stats output
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"  # Defensive ratings output

# Path to the JSON file that tracks when each data type was last updated
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"

# Path to the JSON file that caches the multi-signal injury/availability status map.
# Written by fetch_player_injury_status() and read by data_manager.get_player_status().
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

# Recent-form trend thresholds: how much above/below season avg to be "hot"/"cold"
HOT_TREND_THRESHOLD = 1.1   # Last 3 games avg ≥ 110% of recent avg = hot
COLD_TREND_THRESHOLD = 0.9  # Last 3 games avg ≤ 90% of recent avg = cold

# ============================================================
# Multi-signal injury detection thresholds (fetch_player_injury_status)
# ============================================================
# GP ratio below this → likely long-term out (Injured Reserve)
INJURED_RESERVE_GP_RATIO = 0.40
# Game count gap above this → likely long-term out (Injured Reserve)
INJURED_RESERVE_GAMES_THRESHOLD = 20
# GP ratio below this → possibly injured (Questionable)
QUESTIONABLE_GP_RATIO = 0.60
# Game count gap above this → possibly injured (Questionable)
QUESTIONABLE_GAMES_THRESHOLD = 10
# Days without a game → "Out (no recent games)"
OUT_DAYS_THRESHOLD = 30
# Days without a game → "Questionable"
QUESTIONABLE_DAYS_THRESHOLD = 14
# Days without a game → "Day-to-Day"
DAY_TO_DAY_DAYS_THRESHOLD = 7
# Number of recent games to fetch for recency check (Layer 3)
RECENT_GAMES_WINDOW = 15
# Maximum players to do a game-log check for (cap to limit API calls)
MAX_GAMELOG_CHECKS = 30

# ============================================================
# Game fetcher defaults (placeholder values used until live odds are added)
# ============================================================
DEFAULT_VEGAS_SPREAD = 0.0   # No live spread data yet; shown as 0 until integrated
DEFAULT_GAME_TOTAL = 220.0   # Typical NBA over/under baseline used as placeholder

# Timeout for the ESPN public scoreboard HTTP request (seconds)
ESPN_API_TIMEOUT_SECONDS = 10

# ============================================================
# END SECTION: File Path Constants
# ============================================================


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

    # Add/update the timestamp for this data type
    # datetime.datetime.now() gets the current date and time
    # .isoformat() converts it to a string like "2026-03-06T14:30:00"
    existing_timestamps[data_type] = datetime.datetime.now().isoformat()

    # Also save an "is_live" flag to indicate real data is loaded
    existing_timestamps["is_live"] = True

    # Write the updated timestamps back to the file
    try:
        with open(LAST_UPDATED_JSON_PATH, "w") as json_file:
            # indent=2 makes the JSON file human-readable with indentation
            json.dump(existing_timestamps, json_file, indent=2)
    except Exception as error:
        # If we can't save, just print a warning — it's not critical
        print(f"Warning: Could not save timestamp: {error}")


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
# SECTION: Today's Games Fetcher
# Fetches which NBA games are being played today using a
# 3-layer fallback system for maximum reliability.
# ============================================================

def _fetch_team_records():
    """
    Fetch team records (W-L, streak, home/away splits) from the NBA standings.

    Shared helper used by all three game-fetching layers so standings are
    only pulled once regardless of which layer succeeds.

    Returns:
        dict: Maps team abbreviation → {wins, losses, streak,
              home_record, away_record, conf_rank}.
              Returns empty dict if the standings API fails.
    """
    team_records = {}
    try:
        from nba_api.stats.endpoints import leaguestandingsv3
        standings_endpoint = leaguestandingsv3.LeagueStandingsV3(
            season_type="Regular Season",
        )
        standings_data = standings_endpoint.get_data_frames()[0].to_dict("records")
        time.sleep(API_DELAY_SECONDS)

        for row in standings_data:
            abbrev = row.get("TeamSlug", "").upper()
            # nba_api standings use TeamAbbreviation
            abbrev = row.get("TeamAbbreviation", abbrev)
            abbrev = NBA_API_ABBREV_TO_OURS.get(abbrev, abbrev)
            if not abbrev:
                continue

            wins = int(row.get("WINS", 0) or 0)
            losses = int(row.get("LOSSES", 0) or 0)

            # Parse streak: e.g. "W 3" or "L 2"
            streak_raw = str(row.get("strCurrentStreak", "") or "")
            if streak_raw and len(streak_raw) >= 2:
                streak_dir = streak_raw[0]   # "W" or "L"
                streak_num = streak_raw[1:].strip()
                streak_display = f"{streak_dir}{streak_num}"
            else:
                streak_display = ""

            # Home and away records — use helper to avoid duplicated parsing
            home_wins_s, home_losses_s = _parse_win_loss_record(row.get("HOME", "0-0"))
            away_wins_s, away_losses_s = _parse_win_loss_record(row.get("ROAD", "0-0"))

            conf_rank = int(row.get("PlayoffRank", 0) or 0)

            team_records[abbrev] = {
                "wins": wins,
                "losses": losses,
                "streak": streak_display,
                "home_record": f"{home_wins_s}-{home_losses_s}",
                "away_record": f"{away_wins_s}-{away_losses_s}",
                "conf_rank": conf_rank,
            }
    except Exception as standings_error:
        print(f"Could not fetch standings (non-fatal): {standings_error}")

    return team_records


def _build_formatted_game(home_abbrev, away_abbrev, home_team_name, away_team_name,
                           game_time_et, arena_display, team_records):
    """
    Build the standardised game dict used throughout the app.

    Args:
        home_abbrev (str): Home team abbreviation (our format).
        away_abbrev (str): Away team abbreviation (our format).
        home_team_name (str): Full display name for the home team.
        away_team_name (str): Full display name for the away team.
        game_time_et (str): Game time in Eastern Time, e.g. "7:30 PM ET".
        arena_display (str): Arena name and city string.
        team_records (dict): Standings data from _fetch_team_records().

    Returns:
        dict: Standardised game record.
    """
    home_rec = team_records.get(home_abbrev, {})
    away_rec = team_records.get(away_abbrev, {})

    return {
        "game_id": f"{home_abbrev}_vs_{away_abbrev}",
        "home_team": home_abbrev,
        "away_team": away_abbrev,
        "home_team_full": f"{home_abbrev} — {home_team_name}",
        "away_team_full": f"{away_abbrev} — {away_team_name}",
        "home_team_name": home_team_name,
        "away_team_name": away_team_name,
        "vegas_spread": DEFAULT_VEGAS_SPREAD,
        "game_total": DEFAULT_GAME_TOTAL,
        "game_date": datetime.date.today().isoformat(),
        "game_time_et": game_time_et,
        "arena": arena_display,
        # Team records
        "home_wins": home_rec.get("wins", 0),
        "home_losses": home_rec.get("losses", 0),
        "home_streak": home_rec.get("streak", ""),
        "home_home_record": home_rec.get("home_record", ""),
        "home_conf_rank": home_rec.get("conf_rank", 0),
        "away_wins": away_rec.get("wins", 0),
        "away_losses": away_rec.get("losses", 0),
        "away_streak": away_rec.get("streak", ""),
        "away_away_record": away_rec.get("away_record", ""),
        "away_conf_rank": away_rec.get("conf_rank", 0),
    }


def _fetch_games_layer1_scoreboard_v2(team_records):
    """
    Layer 1: Fetch today's games via the NBA Stats ScoreboardV2 endpoint.

    ScoreboardV2 is the most reliable source — it uses the same NBA Stats
    API as the rest of nba_api and returns a clean GameHeader data frame.

    Args:
        team_records (dict): Pre-fetched standings data from _fetch_team_records().

    Returns:
        list of dict: Formatted game records, or empty list on failure.
    """
    try:
        from nba_api.stats.endpoints import scoreboardv2
        from nba_api.stats.static import teams as nba_teams_static

        # Build team_id → abbreviation and name mapping
        all_nba_teams = nba_teams_static.get_teams()
        team_id_to_abbrev = {}
        team_id_to_info = {}
        for t in all_nba_teams:
            abbrev = t.get("abbreviation", "")
            abbrev = NBA_API_ABBREV_TO_OURS.get(abbrev, abbrev)
            tid = t.get("id")
            team_id_to_abbrev[tid] = abbrev
            team_id_to_info[tid] = {
                "city": t.get("city", ""),
                "name": t.get("nickname", ""),
            }

        today_str = datetime.date.today().strftime("%m/%d/%Y")
        sb = scoreboardv2.ScoreboardV2(game_date=today_str, day_offset=0)
        dfs = sb.get_data_frames()
        time.sleep(API_DELAY_SECONDS)

        if not dfs:
            return []

        game_header_df = dfs[0]  # First frame is GameHeader
        if game_header_df.empty:
            return []

        formatted_games = []
        for row in game_header_df.to_dict("records"):
            home_team_id = row.get("HOME_TEAM_ID")
            away_team_id = row.get("VISITOR_TEAM_ID")

            home_abbrev = team_id_to_abbrev.get(home_team_id, "")
            away_abbrev = team_id_to_abbrev.get(away_team_id, "")

            if not home_abbrev or not away_abbrev:
                continue

            # GAME_STATUS_TEXT shows "7:30 pm ET" for scheduled games
            game_time_et = str(row.get("GAME_STATUS_TEXT", "") or "").strip()

            home_info = team_id_to_info.get(home_team_id, {})
            away_info = team_id_to_info.get(away_team_id, {})
            home_team_name = f"{home_info.get('city', '')} {home_info.get('name', '')}".strip()
            away_team_name = f"{away_info.get('city', '')} {away_info.get('name', '')}".strip()

            formatted_games.append(_build_formatted_game(
                home_abbrev, away_abbrev,
                home_team_name, away_team_name,
                game_time_et, "",
                team_records,
            ))

        return formatted_games

    except Exception as error:
        print(f"Layer 1 (ScoreboardV2) failed: {error}")
        return []


def _fetch_games_layer2_espn(team_records):
    """
    Layer 2: Fetch today's games via the ESPN public scoreboard API.

    ESPN provides a free, unauthenticated JSON endpoint that returns the
    current day's NBA schedule.  No API key required.

    Args:
        team_records (dict): Pre-fetched standings data from _fetch_team_records().

    Returns:
        list of dict: Formatted game records, or empty list on failure.
    """
    try:
        import requests

        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        resp = requests.get(url, timeout=ESPN_API_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("events", [])
        if not events:
            return []

        formatted_games = []
        for event in events:
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            comp = competitions[0]

            competitors = comp.get("competitors", [])
            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home_comp or not away_comp:
                continue

            home_team = home_comp.get("team", {})
            away_team = away_comp.get("team", {})

            home_abbrev = home_team.get("abbreviation", "")
            away_abbrev = away_team.get("abbreviation", "")

            # Normalise ESPN abbreviations to our internal codes
            home_abbrev = NBA_API_ABBREV_TO_OURS.get(home_abbrev, home_abbrev)
            away_abbrev = NBA_API_ABBREV_TO_OURS.get(away_abbrev, away_abbrev)

            if not home_abbrev or not away_abbrev:
                continue

            # Game time — ESPN uses ISO 8601 UTC in startDate
            start_date = comp.get("startDate", event.get("date", ""))
            game_time_et = _utc_to_et_display(start_date)

            # Venue
            venue = comp.get("venue", {})
            arena_name = venue.get("fullName", "")
            arena_city = venue.get("address", {}).get("city", "")
            arena_display = f"{arena_name}, {arena_city}".strip(", ") if arena_name else ""

            home_team_name = home_team.get("displayName", "")
            away_team_name = away_team.get("displayName", "")

            formatted_games.append(_build_formatted_game(
                home_abbrev, away_abbrev,
                home_team_name, away_team_name,
                game_time_et, arena_display,
                team_records,
            ))

        return formatted_games

    except Exception as error:
        print(f"Layer 2 (ESPN API) failed: {error}")
        return []


def _fetch_games_layer3_live_scoreboard(team_records):
    """
    Layer 3: Fetch today's games via the nba_api live ScoreBoard endpoint.

    This is the original single-source implementation, retained as the
    final fallback when both ScoreboardV2 and the ESPN API are unavailable.

    Args:
        team_records (dict): Pre-fetched standings data from _fetch_team_records().

    Returns:
        list of dict: Formatted game records, or empty list on failure.
    """
    try:
        from nba_api.live.nba.endpoints import scoreboard as live_scoreboard

        board = live_scoreboard.ScoreBoard()
        games_data = board.games.get_dict()

        formatted_games = []

        for game in games_data:
            home_team_info = game.get("homeTeam", {})
            away_team_info = game.get("awayTeam", {})

            home_abbrev = home_team_info.get("teamTricode", "")
            away_abbrev = away_team_info.get("teamTricode", "")

            home_abbrev = NBA_API_ABBREV_TO_OURS.get(home_abbrev, home_abbrev)
            away_abbrev = NBA_API_ABBREV_TO_OURS.get(away_abbrev, away_abbrev)

            if not home_abbrev or not away_abbrev:
                continue

            game_time_et = _utc_to_et_display(game.get("gameTimeUTC", ""))

            arena = game.get("arenaName", "")
            arena_city = game.get("arenaCity", "")
            arena_display = f"{arena}, {arena_city}".strip(", ") if arena else ""

            home_team_name = f"{home_team_info.get('teamCity', '')} {home_team_info.get('teamName', '')}".strip()
            away_team_name = f"{away_team_info.get('teamCity', '')} {away_team_info.get('teamName', '')}".strip()

            formatted_games.append(_build_formatted_game(
                home_abbrev, away_abbrev,
                home_team_name, away_team_name,
                game_time_et, arena_display,
                team_records,
            ))

        time.sleep(API_DELAY_SECONDS)
        return formatted_games

    except Exception as error:
        print(f"Layer 3 (Live ScoreBoard) failed: {error}")
        return []


def fetch_todays_games():
    """
    Fetch tonight's NBA games using a 3-layer fallback system.

    Attempts each source in order, falling through to the next if a layer
    fails or returns no games.  After Layer 1 succeeds, a quick cross-
    validation check against Layer 2 logs a warning if the game counts
    differ (so discrepancies are visible in the logs without blocking the
    primary result).

    Layers:
        1. ScoreboardV2        — NBA Stats API (most reliable)
        2. ESPN Public API     — free unauthenticated endpoint (fallback)
        3. Live ScoreBoard     — nba_api live endpoint (final fallback)

    Returns:
        list of dict: Tonight's games, each with home_team, away_team,
                      team records, streak info, and default Vegas lines.
                      Returns empty list if all layers fail or no games today.
    """
    # Fetch team records once — shared by all layers
    team_records = _fetch_team_records()

    # --------------------------------------------------------
    # Layer 1: ScoreboardV2
    # --------------------------------------------------------
    print("Trying Layer 1: ScoreboardV2...")
    layer1_games = _fetch_games_layer1_scoreboard_v2(team_records)

    if layer1_games:
        print(f"Layer 1 success: {len(layer1_games)} game(s) found.")
        # Cross-validate against Layer 2 — log a warning if counts disagree
        try:
            layer2_games = _fetch_games_layer2_espn(team_records)
            if layer2_games and len(layer2_games) != len(layer1_games):
                print(
                    f"Cross-validation warning: Layer 1 found {len(layer1_games)} game(s), "
                    f"Layer 2 found {len(layer2_games)} game(s). Using Layer 1 result."
                )
        except Exception as cv_error:
            print(f"Cross-validation check failed (non-fatal): {cv_error}")
        return layer1_games

    # --------------------------------------------------------
    # Layer 2: ESPN Public API
    # --------------------------------------------------------
    print("Layer 1 failed. Trying Layer 2: ESPN Public API...")
    layer2_games = _fetch_games_layer2_espn(team_records)

    if layer2_games:
        print(f"Layer 2 success: {len(layer2_games)} game(s) found.")
        return layer2_games

    # --------------------------------------------------------
    # Layer 3: Live ScoreBoard
    # --------------------------------------------------------
    print("Layer 2 failed. Trying Layer 3: Live ScoreBoard...")
    layer3_games = _fetch_games_layer3_live_scoreboard(team_records)

    if layer3_games:
        print(f"Layer 3 success: {len(layer3_games)} game(s) found.")
    else:
        print("All layers failed. No games available.")

    return layer3_games

# ============================================================
# END SECTION: Today's Games Fetcher
# ============================================================


# ============================================================
# SECTION: Targeted Roster-Based Data Fetcher
# Only fetches players on teams that are playing today.
# This is MUCH faster than fetching all 500+ NBA players.
# ============================================================

def fetch_todays_players_only(todays_games, progress_callback=None):
    """
    Fetch player stats ONLY for teams playing today.

    Instead of pulling all ~500 NBA players, this function:
    1. Identifies the teams playing today from todays_games
    2. Uses CommonTeamRoster to get the CURRENT roster for each team
       (reflects all trades and signings — no stale player assignments)
    3. Fetches PlayerGameLog for each active player to get recent stats
       and calculate standard deviations

    This runs in ~1-2 minutes instead of 10-15 minutes.

    Args:
        todays_games (list of dict): Tonight's games from fetch_todays_games()
        progress_callback (callable, optional): Called with (current, total, msg)

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    try:
        from nba_api.stats.endpoints import commonteamroster
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import teams as nba_teams_static
    except ImportError:
        print("ERROR: nba_api is not installed. Run: pip install nba_api")
        return False

    if not todays_games:
        print("No games provided — nothing to fetch.")
        return False

    try:
        # --------------------------------------------------------
        # Step 1: Identify which teams are playing today
        # --------------------------------------------------------
        playing_team_abbrevs = set()
        for game in todays_games:
            playing_team_abbrevs.add(game.get("home_team", ""))
            playing_team_abbrevs.add(game.get("away_team", ""))
        playing_team_abbrevs.discard("")  # Remove empty strings

        print(f"Fetching rosters for {len(playing_team_abbrevs)} teams: {sorted(playing_team_abbrevs)}")

        if progress_callback:
            progress_callback(0, 10, f"Found {len(playing_team_abbrevs)} teams playing today. Fetching rosters...")

        # --------------------------------------------------------
        # Step 2: Build a team abbreviation → team ID mapping from nba_api
        # --------------------------------------------------------
        all_nba_teams = nba_teams_static.get_teams()
        team_abbrev_to_id = {}
        for team in all_nba_teams:
            abbrev = team.get("abbreviation", "")
            abbrev = NBA_API_ABBREV_TO_OURS.get(abbrev, abbrev)
            team_abbrev_to_id[abbrev] = team.get("id")

        # --------------------------------------------------------
        # Step 3: Fetch current roster for each playing team
        # --------------------------------------------------------
        all_roster_players = []  # Will hold (player_id, player_name, team_abbrev, position)

        teams_fetched = 0
        for abbrev in sorted(playing_team_abbrevs):
            team_id = team_abbrev_to_id.get(abbrev)
            if not team_id:
                print(f"  Could not find team ID for {abbrev} — skipping")
                continue

            if progress_callback:
                progress_callback(1 + teams_fetched, 10, f"Fetching current roster for {abbrev}...")

            try:
                roster_endpoint = commonteamroster.CommonTeamRoster(
                    team_id=team_id,
                )
                roster_df = roster_endpoint.get_data_frames()[0]
                roster_rows = roster_df.to_dict("records")
                time.sleep(API_DELAY_SECONDS)

                for player_row in roster_rows:
                    player_id = player_row.get("PLAYER_ID")
                    player_name = player_row.get("PLAYER", "")
                    position = player_row.get("POSITION", "")

                    # Normalize position
                    position_map = {
                        "G": "PG", "F": "SF", "C": "C",
                        "G-F": "SF", "F-G": "SG", "F-C": "PF", "C-F": "PF",
                        "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF",
                        "": "SF",
                    }
                    mapped_position = position_map.get(position, position if position else "SF")

                    if player_id and player_name:
                        all_roster_players.append({
                            "player_id": player_id,
                            "player_name": player_name,
                            "team": abbrev,
                            "position": mapped_position,
                        })

                teams_fetched += 1
                print(f"  {abbrev}: {len(roster_rows)} players on roster")

            except Exception as roster_error:
                print(f"  Error fetching roster for {abbrev}: {roster_error}")

        print(f"Total players on today's rosters: {len(all_roster_players)}")

        if progress_callback:
            progress_callback(3, 10, f"Got {len(all_roster_players)} players. Fetching game logs for stats...")

        # --------------------------------------------------------
        # Step 4: Fetch game logs for each player to get stats + std devs
        # --------------------------------------------------------
        formatted_players = []
        total_players = len(all_roster_players)

        for player_index, player_info in enumerate(all_roster_players):
            player_id = player_info["player_id"]
            player_name = player_info["player_name"]
            team_abbrev = player_info["team"]
            position = player_info["position"]

            if player_index % 5 == 0 and progress_callback:
                pct = int(7 * player_index / max(total_players, 1))
                progress_callback(3 + pct, 10, f"Fetching stats for {player_name} ({player_index + 1}/{total_players})...")

            # Default stats (will be replaced by game log data)
            points_avg = rebounds_avg = assists_avg = threes_avg = 0.0
            steals_avg = blocks_avg = turnovers_avg = ft_pct = minutes_avg = 0.0
            usage_rate = 15.0
            points_std = rebounds_std = assists_std = threes_std = 1.0
            steals_std = blocks_std = turnovers_std = 0.5

            try:
                game_log_endpoint = playergamelog.PlayerGameLog(
                    player_id=player_id,
                    season_type_all_star="Regular Season",
                )
                game_log_data = game_log_endpoint.get_data_frames()[0].to_dict("records")
                time.sleep(API_DELAY_SECONDS)

                # Use last 20 games for averages, last 10 for std devs (recent form)
                recent_20 = game_log_data[:20]
                recent_10 = game_log_data[:10]

                if len(recent_20) >= 3:
                    def safe_avg(lst):
                        return sum(lst) / len(lst) if lst else 0.0

                    pts_20 = [float(g.get("PTS", 0) or 0) for g in recent_20]
                    reb_20 = [float(g.get("REB", 0) or 0) for g in recent_20]
                    ast_20 = [float(g.get("AST", 0) or 0) for g in recent_20]
                    fg3m_20 = [float(g.get("FG3M", 0) or 0) for g in recent_20]
                    stl_20 = [float(g.get("STL", 0) or 0) for g in recent_20]
                    blk_20 = [float(g.get("BLK", 0) or 0) for g in recent_20]
                    tov_20 = [float(g.get("TOV", 0) or 0) for g in recent_20]
                    ft_20 = [float(g.get("FT_PCT", 0) or 0) for g in recent_20]
                    min_20 = [float(g.get("MIN", 0) or 0) for g in recent_20]

                    points_avg = round(safe_avg(pts_20), 1)
                    rebounds_avg = round(safe_avg(reb_20), 1)
                    assists_avg = round(safe_avg(ast_20), 1)
                    threes_avg = round(safe_avg(fg3m_20), 1)
                    steals_avg = round(safe_avg(stl_20), 1)
                    blocks_avg = round(safe_avg(blk_20), 1)
                    turnovers_avg = round(safe_avg(tov_20), 1)
                    ft_pct = round(safe_avg(ft_20), 3)
                    minutes_avg = round(safe_avg(min_20), 1)
                    usage_rate = min(35.0, max(10.0, minutes_avg * 0.8))

                    # Use last 10 games for std devs (recent consistency)
                    pts_10 = [float(g.get("PTS", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else pts_20
                    reb_10 = [float(g.get("REB", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else reb_20
                    ast_10 = [float(g.get("AST", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else ast_20
                    fg3m_10 = [float(g.get("FG3M", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else fg3m_20
                    stl_10 = [float(g.get("STL", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else stl_20
                    blk_10 = [float(g.get("BLK", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else blk_20
                    tov_10 = [float(g.get("TOV", 0) or 0) for g in recent_10] if len(recent_10) >= 2 else tov_20

                    if len(pts_10) >= 2:
                        points_std = round(statistics.stdev(pts_10), 2)
                    else:
                        # W10: Dynamic CV based on player scoring tier
                        points_std = max(1.0, points_avg * _dynamic_cv_for_live_fetch("points", points_avg))
                    if len(reb_10) >= 2:
                        rebounds_std = round(statistics.stdev(reb_10), 2)
                    else:
                        rebounds_std = max(0.5, rebounds_avg * _dynamic_cv_for_live_fetch("rebounds", rebounds_avg))
                    if len(ast_10) >= 2:
                        assists_std = round(statistics.stdev(ast_10), 2)
                    else:
                        assists_std = max(0.5, assists_avg * _dynamic_cv_for_live_fetch("assists", assists_avg))
                    if len(fg3m_10) >= 2:
                        threes_std = round(statistics.stdev(fg3m_10), 2)
                    else:
                        # W10: Three-pointers use minimum 0.55 CV
                        threes_std = max(0.3, threes_avg * _dynamic_cv_for_live_fetch("threes", threes_avg))
                    steals_std = round(statistics.stdev(stl_10), 2) if len(stl_10) >= 2 else max(0.1, steals_avg * FALLBACK_STEALS_STD_RATIO)
                    blocks_std = round(statistics.stdev(blk_10), 2) if len(blk_10) >= 2 else max(0.1, blocks_avg * FALLBACK_BLOCKS_STD_RATIO)
                    turnovers_std = round(statistics.stdev(tov_10), 2) if len(tov_10) >= 2 else max(0.1, turnovers_avg * FALLBACK_TURNOVERS_STD_RATIO)

            except Exception as log_error:
                print(f"  Could not fetch game log for {player_name}: {log_error}")

            # Skip players who haven't played (no meaningful minutes).
            # Players below MIN_MINUTES_THRESHOLD are inactive or garbage-time only.
            if minutes_avg < MIN_MINUTES_THRESHOLD:
                continue

            formatted_player = {
                "player_id": player_id if player_id else "",  # NBA unique player ID
                "name": player_name,
                "team": team_abbrev,
                "position": position,
                "minutes_avg": minutes_avg,
                "points_avg": points_avg,
                "rebounds_avg": rebounds_avg,
                "assists_avg": assists_avg,
                "threes_avg": threes_avg,
                "steals_avg": steals_avg,
                "blocks_avg": blocks_avg,
                "turnovers_avg": turnovers_avg,
                "ft_pct": ft_pct,
                "usage_rate": round(usage_rate, 1),
                "points_std": points_std,
                "rebounds_std": rebounds_std,
                "assists_std": assists_std,
                "threes_std": threes_std,
                "steals_std": steals_std,
                "blocks_std": blocks_std,
                "turnovers_std": turnovers_std,
            }
            formatted_players.append(formatted_player)

        # Sort by points average (stars appear first)
        formatted_players.sort(key=lambda p: p["points_avg"], reverse=True)

        if progress_callback:
            progress_callback(9, 10, f"Saving {len(formatted_players)} players to CSV...")

        # Write to the CSV file (same format as full fetch)
        fieldnames = [
            "player_id", "name", "team", "position", "minutes_avg",
            "points_avg", "rebounds_avg", "assists_avg", "threes_avg",
            "steals_avg", "blocks_avg", "turnovers_avg", "ft_pct",
            "usage_rate", "points_std", "rebounds_std", "assists_std",
            "threes_std", "steals_std", "blocks_std", "turnovers_std",
        ]

        with open(PLAYERS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(formatted_players)

        save_last_updated("players")

        if progress_callback:
            progress_callback(10, 10, f"✅ Saved {len(formatted_players)} players (today's teams only)!")

        print(f"Saved {len(formatted_players)} players for today's games to {PLAYERS_CSV_PATH}")
        return True

    except Exception as error:
        print(f"Error in fetch_todays_players_only: {error}")
        return False

# ============================================================
# END SECTION: Targeted Roster-Based Data Fetcher
# ============================================================


# ============================================================
# SECTION: Recent Form Fetcher
# Fetch the last N games for a player and compute trend/averages.
# ============================================================

def fetch_player_recent_form(player_id, last_n_games=10):
    """
    Fetch recent form data for a specific player.

    Returns the last N game logs along with:
    - Recent averages (last N games)
    - Trend indicator: 'hot' if last 3 games avg > season avg, else 'cold'
    - Game-by-game breakdown for sparkline display

    Args:
        player_id (int or str): The NBA player's unique ID
        last_n_games (int): Number of recent games to analyze (default: 10)

    Returns:
        dict: Recent form data with keys:
              'games' (list), 'recent_pts_avg', 'recent_reb_avg',
              'recent_ast_avg', 'trend', 'game_results'
              Returns empty dict if fetch fails.
    """
    try:
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        return {}

    try:
        game_log_endpoint = playergamelog.PlayerGameLog(
            player_id=player_id,
            season_type_all_star="Regular Season",
        )
        game_log_data = game_log_endpoint.get_data_frames()[0].to_dict("records")
        time.sleep(API_DELAY_SECONDS)

        recent = game_log_data[:last_n_games]

        if not recent:
            return {}

        def safe_avg(values):
            return round(sum(values) / len(values), 1) if values else 0.0

        pts_list = [float(g.get("PTS", 0) or 0) for g in recent]
        reb_list = [float(g.get("REB", 0) or 0) for g in recent]
        ast_list = [float(g.get("AST", 0) or 0) for g in recent]
        fg3m_list = [float(g.get("FG3M", 0) or 0) for g in recent]

        # Trend: compare last 5 games vs prior 5 games
        last_5_pts_vals = pts_list[:5]
        prior_5_pts_vals = pts_list[5:10]
        last5_avg = safe_avg(last_5_pts_vals)
        prev5_avg = safe_avg(prior_5_pts_vals) if prior_5_pts_vals else last5_avg

        if prev5_avg > 0:
            trend = "hot" if last5_avg >= prev5_avg * HOT_TREND_THRESHOLD else (
                "cold" if last5_avg <= prev5_avg * COLD_TREND_THRESHOLD else "neutral"
            )
        else:
            trend = "neutral"

        trend_emoji_map = {"hot": "🔥", "cold": "❄️", "neutral": "➡️"}
        trend_emoji = trend_emoji_map.get(trend, "➡️")

        # Build game-by-game results list (newest first)
        game_results = []
        for g in recent:
            game_results.append({
                "date": g.get("GAME_DATE", ""),
                "matchup": g.get("MATCHUP", ""),
                "wl": g.get("WL", ""),
                "pts": float(g.get("PTS", 0) or 0),
                "reb": float(g.get("REB", 0) or 0),
                "ast": float(g.get("AST", 0) or 0),
                "fg3m": float(g.get("FG3M", 0) or 0),
                "min": float(g.get("MIN", 0) or 0),
            })

        return {
            "games": recent,
            "recent_pts_avg": safe_avg(pts_list),
            "recent_reb_avg": safe_avg(reb_list),
            "recent_ast_avg": safe_avg(ast_list),
            "recent_fg3m_avg": safe_avg(fg3m_list),
            "trend": trend,
            "trend_emoji": trend_emoji,
            "last_5_pts": last_5_pts_vals,
            "last_5_pts_avg": last5_avg,
            "game_results": game_results,
            "games_played": len(recent),
        }

    except Exception as error:
        print(f"Error fetching recent form for player {player_id}: {error}")
        return {}

# ============================================================
# END SECTION: Recent Form Fetcher
# ============================================================


# ============================================================
# SECTION: Player Stats Fetcher
# Fetches current season averages for all NBA players.
# ============================================================

def fetch_player_stats(progress_callback=None):
    """
    Fetch current season player stats for all NBA players.

    Uses LeagueDashPlayerStats to get PPG, RPG, APG, etc. for
    every player who has played this season. Then fetches game logs
    to calculate standard deviations (how consistent each player is).

    BEGINNER NOTE: LeagueDashPlayerStats is the same data you see on
    basketball-reference.com or ESPN — season averages per game.

    Args:
        progress_callback (callable, optional): A function to call with
            progress updates. Called with (current, total, message).
            Used by the Streamlit page to update the progress bar.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    # Import inside the function for graceful failure if not installed
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players as nba_players_static
    except ImportError:
        print("ERROR: nba_api is not installed. Run: pip install nba_api")
        return False

    try:
        # --------------------------------------------------------
        # Step 1: Fetch season averages for all players
        # --------------------------------------------------------

        # Call the LeagueDashPlayerStats endpoint
        # BEGINNER NOTE: PerGame means we get per-game averages (not totals)
        # season_type_all_star is the parameter name in nba_api that controls
        # the season type. Despite the parameter name containing "all_star",
        # it accepts values like "Regular Season", "Playoffs", "Pre Season", etc.
        print("Fetching player season averages from NBA API...")

        # Signal progress to the UI if a callback was provided
        if progress_callback:
            progress_callback(1, 10, "Connecting to NBA API for player stats...")

        # Make the API call — this fetches ALL players' stats at once
        stats_endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
            per_mode_detailed="PerGame",      # We want per-game averages
            season_type_all_star="Regular Season",  # Only regular season
        )

        # Wait a moment before the next call
        time.sleep(API_DELAY_SECONDS)

        # Get the data as a list of dictionaries
        # BEGINNER NOTE: nba_api returns a DataFrame object.
        # .get_data_frames() converts it to a list of DataFrames.
        # [0] gets the first (and only) DataFrame.
        # .to_dict('records') converts rows to a list of dicts.
        player_stats_list = stats_endpoint.get_data_frames()[0].to_dict("records")

        if progress_callback:
            progress_callback(2, 10, f"Got stats for {len(player_stats_list)} players. Calculating standard deviations...")

        print(f"Got stats for {len(player_stats_list)} players.")

        # --------------------------------------------------------
        # Step 2: Map nba_api column names to our column names
        # --------------------------------------------------------

        # BEGINNER NOTE: nba_api uses column names like "PTS" (points),
        # but our app uses "points_avg". We need to map between them.
        # This list will hold our formatted player rows.
        formatted_players = []

        # Process each player — fetch game logs for std dev calculation
        total_players = len(player_stats_list)

        for player_index, player_row in enumerate(player_stats_list):
            # Show progress every 10 players
            if player_index % 10 == 0 and progress_callback:
                progress_message = f"Processing player {player_index + 1} of {total_players}..."
                progress_callback(2 + int(7 * player_index / total_players), 10, progress_message)

            # Extract the player's season averages from the nba_api format
            # BEGINNER NOTE: .get(key, default) returns the value for 'key',
            # or 'default' if the key doesn't exist.
            player_name = player_row.get("PLAYER_NAME", "")          # Full name
            team_abbrev = player_row.get("TEAM_ABBREVIATION", "")    # 3-letter team code
            position = player_row.get("START_POSITION", "G")          # Starting position

            # Skip players with no name or team
            if not player_name or not team_abbrev:
                continue

            # Map position codes (nba_api sometimes uses just "G", "F", "C")
            # Our app uses PG, SG, SF, PF, C — we default to a generic position
            position_map = {
                "G": "PG",   # Guard → Point Guard (best guess)
                "F": "SF",   # Forward → Small Forward (best guess)
                "C": "C",    # Center stays Center
                "G-F": "SF", # Guard-Forward hybrid
                "F-G": "SG", # Forward-Guard hybrid
                "F-C": "PF", # Forward-Center hybrid
                "C-F": "PF", # Center-Forward hybrid
                "": "SF",    # Unknown → Small Forward (safe default)
            }
            mapped_position = position_map.get(position, position)  # Map or keep original

            # Normalize team abbreviation to match our format
            team_abbrev = NBA_API_ABBREV_TO_OURS.get(team_abbrev, team_abbrev)

            # Get season averages (these come as numbers from nba_api)
            points_avg = float(player_row.get("PTS", 0) or 0)        # Points per game
            rebounds_avg = float(player_row.get("REB", 0) or 0)      # Rebounds per game
            assists_avg = float(player_row.get("AST", 0) or 0)       # Assists per game
            threes_avg = float(player_row.get("FG3M", 0) or 0)       # 3-pointers made per game
            steals_avg = float(player_row.get("STL", 0) or 0)        # Steals per game
            blocks_avg = float(player_row.get("BLK", 0) or 0)        # Blocks per game
            turnovers_avg = float(player_row.get("TOV", 0) or 0)     # Turnovers per game
            ft_pct = float(player_row.get("FT_PCT", 0) or 0)         # Free throw percentage (0-1)
            minutes_avg = float(player_row.get("MIN", 0) or 0)       # Minutes per game

            # Usage rate is not directly in LeagueDashPlayerStats basic call
            # We estimate it from minutes played as a rough proxy:
            # NBA average usage rate ≈ 20% (equal sharing across 5 players).
            # Stars who play 35+ min tend to have usage ≈ 28-35%.
            # The 0.8 multiplier maps minutes (10-38 range) to a plausible
            # usage range (8-30%) that correlates with observed NBA data.
            # This estimate is only used if live usage data isn't available.
            usage_rate = min(35.0, max(10.0, minutes_avg * 0.8))  # Rough estimate

            # --------------------------------------------------------
            # Step 3: Calculate standard deviations from game logs
            # --------------------------------------------------------
            # BEGINNER NOTE: Standard deviation measures how consistent
            # a player is. A player who always scores exactly 20 has
            # std dev of 0. A player who scores anywhere from 5-35
            # has a high std dev. Higher std dev = harder to predict.

            # Fetch the player's game log to calculate std dev
            player_id = player_row.get("PLAYER_ID")  # Unique NBA player ID

            # Default std devs if we can't fetch the game log.
            # W10: Use dynamic tier-based CV instead of fixed ratios.
            # Stars (high avg) are more consistent; role players are more volatile.
            points_std = max(1.0, points_avg * _dynamic_cv_for_live_fetch("points", points_avg))
            rebounds_std = max(0.5, rebounds_avg * _dynamic_cv_for_live_fetch("rebounds", rebounds_avg))
            assists_std = max(0.5, assists_avg * _dynamic_cv_for_live_fetch("assists", assists_avg))
            threes_std = max(0.3, threes_avg * _dynamic_cv_for_live_fetch("threes", threes_avg))

            # Initialize steals/blocks/turnovers std devs with CV-based defaults.
            # These will be overwritten with game-log-calculated values if available.
            steals_std_from_log = None    # Will hold game-log std dev if fetched
            blocks_std_from_log = None    # Will hold game-log std dev if fetched
            turnovers_std_from_log = None  # Will hold game-log std dev if fetched

            # Only fetch game log if the player has played meaningful minutes
            # This avoids wasting API calls on end-of-bench players
            if player_id and minutes_avg >= 10.0:
                try:
                    # Fetch the last 20 games for this player
                    # BEGINNER NOTE: The game log shows stats game-by-game,
                    # e.g., "March 1: 22 pts, March 3: 18 pts, March 5: 30 pts"
                    game_log_endpoint = playergamelog.PlayerGameLog(
                        player_id=player_id,        # Which player
                        season_type_all_star="Regular Season",  # Only regular season
                    )

                    # Get the game log data
                    game_log_data = game_log_endpoint.get_data_frames()[0].to_dict("records")

                    # Take only the last 20 games for recency
                    recent_games = game_log_data[:20]

                    # Calculate std dev if we have at least 5 games
                    if len(recent_games) >= 5:
                        # Extract lists of each stat across all games
                        pts_list = [float(g.get("PTS", 0) or 0) for g in recent_games]
                        reb_list = [float(g.get("REB", 0) or 0) for g in recent_games]
                        ast_list = [float(g.get("AST", 0) or 0) for g in recent_games]
                        fg3m_list = [float(g.get("FG3M", 0) or 0) for g in recent_games]
                        stl_list = [float(g.get("STL", 0) or 0) for g in recent_games]
                        blk_list = [float(g.get("BLK", 0) or 0) for g in recent_games]
                        tov_list = [float(g.get("TOV", 0) or 0) for g in recent_games]

                        # statistics.stdev calculates standard deviation
                        # BEGINNER NOTE: We need at least 2 values for stdev
                        if len(pts_list) >= 2:
                            points_std = round(statistics.stdev(pts_list), 2)
                        if len(reb_list) >= 2:
                            rebounds_std = round(statistics.stdev(reb_list), 2)
                        if len(ast_list) >= 2:
                            assists_std = round(statistics.stdev(ast_list), 2)
                        if len(fg3m_list) >= 2:
                            threes_std = round(statistics.stdev(fg3m_list), 2)
                        # Calculate steals/blocks/turnovers std from game logs
                        # This replaces the CV-based defaults for better accuracy
                        steals_std_from_log = round(statistics.stdev(stl_list), 2) if len(stl_list) >= 2 else None
                        blocks_std_from_log = round(statistics.stdev(blk_list), 2) if len(blk_list) >= 2 else None
                        turnovers_std_from_log = round(statistics.stdev(tov_list), 2) if len(tov_list) >= 2 else None
                    else:
                        steals_std_from_log = None
                        blocks_std_from_log = None
                        turnovers_std_from_log = None

                    # IMPORTANT: Always sleep between API calls to avoid rate limiting
                    time.sleep(API_DELAY_SECONDS)

                except Exception as game_log_error:
                    # If game log fetch fails, use the default std devs calculated above
                    # This is not fatal — we just use less accurate std devs
                    print(f"  Could not fetch game log for {player_name}: {game_log_error}")

            # --------------------------------------------------------
            # Step 4: Build the formatted player dictionary
            # --------------------------------------------------------

            # Build the row in our CSV format
            # BEGINNER NOTE: All values are rounded to 2 decimal places
            # for clean CSV output
            formatted_player = {
                "player_id": player_id if player_id else "",  # NBA unique player ID
                "name": player_name,                          # Player full name
                "team": team_abbrev,                          # 3-letter team code
                "position": mapped_position,                  # PG/SG/SF/PF/C
                "minutes_avg": round(minutes_avg, 1),         # Minutes per game
                "points_avg": round(points_avg, 1),           # Points per game
                "rebounds_avg": round(rebounds_avg, 1),       # Rebounds per game
                "assists_avg": round(assists_avg, 1),         # Assists per game
                "threes_avg": round(threes_avg, 1),           # 3PM per game
                "steals_avg": round(steals_avg, 1),           # Steals per game
                "blocks_avg": round(blocks_avg, 1),           # Blocks per game
                "turnovers_avg": round(turnovers_avg, 1),     # Turnovers per game
                "ft_pct": round(ft_pct, 3),                   # Free throw % (0-1)
                "usage_rate": round(usage_rate, 1),           # Usage rate %
                "points_std": round(points_std, 2),           # Points std dev
                "rebounds_std": round(rebounds_std, 2),       # Rebounds std dev
                "assists_std": round(assists_std, 2),         # Assists std dev
                "threes_std": round(threes_std, 2),           # 3PM std dev
                # Use game-log std devs when available; fall back to ratio-based estimates
                "steals_std": round(steals_std_from_log if steals_std_from_log is not None else max(0.1, steals_avg * FALLBACK_STEALS_STD_RATIO), 2),
                "blocks_std": round(blocks_std_from_log if blocks_std_from_log is not None else max(0.1, blocks_avg * FALLBACK_BLOCKS_STD_RATIO), 2),
                "turnovers_std": round(turnovers_std_from_log if turnovers_std_from_log is not None else max(0.1, turnovers_avg * FALLBACK_TURNOVERS_STD_RATIO), 2),
            }

            # Skip players who aren't getting meaningful minutes.
            # They won't have props and pollute the database with noise.
            if minutes_avg < MIN_MINUTES_THRESHOLD:
                continue

            formatted_players.append(formatted_player)

        # --------------------------------------------------------
        # Step 5: Sort by points average (stars appear first)
        # --------------------------------------------------------

        # Sort players so the best scorers appear at the top
        formatted_players.sort(key=lambda p: p["points_avg"], reverse=True)

        if progress_callback:
            progress_callback(9, 10, f"Saving {len(formatted_players)} players to CSV...")

        # --------------------------------------------------------
        # Step 6: Write the CSV file
        # --------------------------------------------------------

        # Define the column order (must match sample_players.csv exactly)
        fieldnames = [
            "player_id", "name", "team", "position", "minutes_avg",
            "points_avg", "rebounds_avg", "assists_avg", "threes_avg",
            "steals_avg", "blocks_avg", "turnovers_avg", "ft_pct",
            "usage_rate", "points_std", "rebounds_std", "assists_std",
            "threes_std", "steals_std", "blocks_std", "turnovers_std",
        ]

        # Write to the CSV file (overwrites any existing data)
        # BEGINNER NOTE: 'w' means write mode (overwrites existing file)
        # newline='' is required by Python's csv module on Windows
        with open(PLAYERS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()      # Write the column names row
            writer.writerows(formatted_players)  # Write all player rows

        # Save timestamp so we know when this was last updated
        save_last_updated("players")

        if progress_callback:
            progress_callback(10, 10, f"✅ Saved {len(formatted_players)} players!")

        print(f"Successfully saved {len(formatted_players)} players to {PLAYERS_CSV_PATH}")
        return True  # Signal success

    except Exception as error:
        # Catch-all error handler — show what went wrong
        print(f"Error fetching player stats: {error}")
        return False  # Signal failure

# ============================================================
# END SECTION: Player Stats Fetcher
# ============================================================


# ============================================================
# SECTION: Team Stats Fetcher
# Fetches current season team stats (pace, ratings, etc.)
# ============================================================

def fetch_team_stats(progress_callback=None):
    """
    Fetch current season team stats using LeagueDashTeamStats.

    Pulls pace, offensive rating (ORTG), and defensive rating (DRTG)
    for all 30 NBA teams. Also builds basic defensive ratings by position.

    BEGINNER NOTE: Pace is how many possessions a team uses per 48 minutes.
    A high pace team (like the Warriors) plays fast, meaning more shots and
    more counting stats. ORTG = points scored per 100 possessions. DRTG =
    points allowed per 100 possessions. Lower DRTG = better defense.

    Args:
        progress_callback (callable, optional): Progress update function.

    Returns:
        bool: True if successful, False if the fetch failed.
    """
    # Import inside the function for graceful failure
    try:
        from nba_api.stats.endpoints import leaguedashteamstats
    except ImportError:
        print("ERROR: nba_api is not installed. Run: pip install nba_api")
        return False

    try:
        if progress_callback:
            progress_callback(1, 6, "Fetching team stats from NBA API...")

        # --------------------------------------------------------
        # Step 1: Fetch team stats (pace, ortg, drtg)
        # --------------------------------------------------------

        # LeagueDashTeamStats with PerPossession gives us ratings
        # BEGINNER NOTE: Per possession stats (like ORTG/DRTG) normalize
        # for pace — they tell you how efficient a team is regardless of
        # whether they play fast or slow.
        team_stats_endpoint = leaguedashteamstats.LeagueDashTeamStats(
            per_mode_detailed="PerGame",          # Get per-game stats
            season_type_all_star="Regular Season",
        )

        # Get the data
        team_stats_list = team_stats_endpoint.get_data_frames()[0].to_dict("records")

        time.sleep(API_DELAY_SECONDS)  # Be polite — wait between calls

        if progress_callback:
            progress_callback(2, 6, "Fetching team advanced stats (pace, ratings)...")

        # Also fetch advanced stats for pace and ratings
        # BEGINNER NOTE: "Advanced" stats include efficiency metrics
        # that regular box scores don't show
        from nba_api.stats.endpoints import leaguedashteamstats as advanced_stats_module

        # Fetch advanced (per-possession) stats for ORTG/DRTG/Pace
        advanced_endpoint = advanced_stats_module.LeagueDashTeamStats(
            per_mode_detailed="Per100Possessions",    # Per 100 possessions = normalized
            measure_type_detailed_defense="Advanced",  # Advanced stats mode
            season_type_all_star="Regular Season",
        )

        advanced_list = advanced_endpoint.get_data_frames()[0].to_dict("records")

        time.sleep(API_DELAY_SECONDS)

        # Build a lookup dict: team_id → advanced stats
        # BEGINNER NOTE: A dictionary lets us quickly look up a team's
        # advanced stats by their team ID
        advanced_by_team_id = {}
        for row in advanced_list:
            team_id = row.get("TEAM_ID")           # Unique team ID number
            if team_id:
                advanced_by_team_id[team_id] = row  # Store advanced stats

        if progress_callback:
            progress_callback(3, 6, "Building team CSV rows...")

        # --------------------------------------------------------
        # Step 2: Build formatted team rows
        # --------------------------------------------------------

        formatted_teams = []

        for team_row in team_stats_list:
            # Get the team name and ID
            team_name = team_row.get("TEAM_NAME", "")   # Full name e.g. "Los Angeles Lakers"
            team_id = team_row.get("TEAM_ID")            # Numeric ID

            # Skip teams with no name
            if not team_name:
                continue

            # Look up abbreviation from our mapping
            team_abbrev = TEAM_NAME_TO_ABBREVIATION.get(team_name, "")
            if not team_abbrev:
                # Try to get abbreviation from the raw data
                team_abbrev = team_row.get("TEAM_ABBREVIATION", "")
                team_abbrev = NBA_API_ABBREV_TO_OURS.get(team_abbrev, team_abbrev)

            # Skip if we still don't have an abbreviation
            if not team_abbrev:
                continue

            # Get conference for this team
            conference = TEAM_CONFERENCE.get(team_abbrev, "West")  # Default to West

            # Get advanced stats for this team (if available)
            advanced_row = advanced_by_team_id.get(team_id, {})

            # Extract pace — PACE is in the advanced stats
            # If not available, use a reasonable NBA average (98-103)
            pace = float(advanced_row.get("PACE", 0) or 0)
            if pace == 0:
                pace = 100.0  # League average default

            # Extract ORTG (offensive rating) from advanced stats
            ortg = float(advanced_row.get("OFF_RATING", 0) or 0)
            if ortg == 0:
                # Fall back to calculating from basic stats
                # Points per game × 100 / pace ≈ rough ORTG estimate
                pts = float(team_row.get("PTS", 110) or 110)
                ortg = round(pts, 1)  # Use raw points as rough proxy

            # Extract DRTG (defensive rating) from advanced stats
            drtg = float(advanced_row.get("DEF_RATING", 0) or 0)
            if drtg == 0:
                drtg = 113.0  # League average default

            # Build the team row in our CSV format
            formatted_team = {
                "team_name": team_name,             # Full name
                "abbreviation": team_abbrev,         # 3-letter code
                "conference": conference,             # East or West
                "division": "",                       # We don't use division in the engine
                "pace": round(pace, 1),              # Possessions per 48 minutes
                "ortg": round(ortg, 1),              # Offensive rating
                "drtg": round(drtg, 1),              # Defensive rating
            }

            formatted_teams.append(formatted_team)

        # Sort by team name alphabetically
        formatted_teams.sort(key=lambda t: t["team_name"])

        if progress_callback:
            progress_callback(4, 6, f"Saving {len(formatted_teams)} teams to CSV...")

        # --------------------------------------------------------
        # Step 3: Write the teams CSV
        # --------------------------------------------------------

        # Column order must match existing teams.csv exactly
        team_fieldnames = [
            "team_name", "abbreviation", "conference", "division",
            "pace", "ortg", "drtg",
        ]

        with open(TEAMS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=team_fieldnames)
            writer.writeheader()
            writer.writerows(formatted_teams)

        # Save timestamp
        save_last_updated("teams")

        if progress_callback:
            progress_callback(5, 6, "Building defensive ratings by position...")

        # --------------------------------------------------------
        # Step 4: Build defensive_ratings.csv
        # --------------------------------------------------------
        # BEGINNER NOTE: The defensive_ratings.csv tracks how good or bad
        # each team is at defending each position (PG, SG, SF, PF, C).
        # A value > 1.0 means the team allows MORE than average to that position
        # (bad defense). A value < 1.0 means they allow LESS (good defense).
        #
        # The nba_api doesn't directly give us position-by-position defensive
        # ratings. So we calculate them from overall defensive rating:
        # - Teams with good overall defense (low drtg) get values below 1.0
        # - Teams with bad defense (high drtg) get values above 1.0
        # - The adjustment varies slightly by position for realism

        defensive_rows = []

        # League average defensive rating (used for normalization)
        # BEGINNER NOTE: We calculate the average drtg across all teams
        all_drtg_values = [t["drtg"] for t in formatted_teams if t["drtg"] > 0]
        avg_drtg = sum(all_drtg_values) / len(all_drtg_values) if all_drtg_values else 113.0

        for team in formatted_teams:
            team_drtg = team["drtg"]              # This team's defensive rating
            team_abbrev = team["abbreviation"]     # 3-letter team code
            team_name_full = team["team_name"]     # Full team name

            # Calculate how much above/below average this team's defense is
            # A team with drtg = avg_drtg gets a ratio of exactly 1.0
            # A team with higher drtg (worse defense) gets ratio > 1.0
            # A team with lower drtg (better defense) gets ratio < 1.0
            if avg_drtg > 0:
                defense_ratio = team_drtg / avg_drtg  # Normalized defense rating
            else:
                defense_ratio = 1.0  # Default if no data

            # Apply small positional adjustments for realism
            # (Better defenses tend to suppress guards more than centers,
            # since most offensive schemes feature guard play)
            pg_factor = round(defense_ratio * 1.01, 3)   # PG: slightly above ratio
            sg_factor = round(defense_ratio * 1.00, 3)   # SG: same as ratio
            sf_factor = round(defense_ratio * 0.99, 3)   # SF: slightly below
            pf_factor = round(defense_ratio * 0.98, 3)   # PF: below
            c_factor = round(defense_ratio * 0.97, 3)    # C: most below (bigs harder to guard)

            # Build the defensive ratings row
            defensive_row = {
                "team_name": team_name_full,    # Full team name
                "abbreviation": team_abbrev,     # 3-letter code
                "vs_PG_pts": pg_factor,          # Multiplier vs PG (pts)
                "vs_SG_pts": sg_factor,          # Multiplier vs SG (pts)
                "vs_SF_pts": sf_factor,          # Multiplier vs SF (pts)
                "vs_PF_pts": pf_factor,          # Multiplier vs PF (pts)
                "vs_C_pts": c_factor,            # Multiplier vs C (pts)
                "vs_PG_reb": round(defense_ratio * 0.99, 3),   # Rebound factors
                "vs_SG_reb": round(defense_ratio * 0.98, 3),
                "vs_SF_reb": round(defense_ratio * 0.97, 3),
                "vs_PF_reb": round(defense_ratio * 1.01, 3),
                "vs_C_reb": round(defense_ratio * 1.02, 3),
                "vs_PG_ast": round(defense_ratio * 1.02, 3),   # Assist factors
                "vs_SG_ast": round(defense_ratio * 1.00, 3),
                "vs_SF_ast": round(defense_ratio * 0.99, 3),
                "vs_PF_ast": round(defense_ratio * 0.97, 3),
                "vs_C_ast": round(defense_ratio * 0.96, 3),
            }

            defensive_rows.append(defensive_row)

        # Write the defensive ratings CSV
        defensive_fieldnames = [
            "team_name", "abbreviation",
            "vs_PG_pts", "vs_SG_pts", "vs_SF_pts", "vs_PF_pts", "vs_C_pts",
            "vs_PG_reb", "vs_SG_reb", "vs_SF_reb", "vs_PF_reb", "vs_C_reb",
            "vs_PG_ast", "vs_SG_ast", "vs_SF_ast", "vs_PF_ast", "vs_C_ast",
        ]

        with open(DEFENSIVE_RATINGS_CSV_PATH, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=defensive_fieldnames)
            writer.writeheader()
            writer.writerows(defensive_rows)

        # Save timestamps
        save_last_updated("teams")

        if progress_callback:
            progress_callback(6, 6, f"✅ Saved {len(formatted_teams)} teams and defensive ratings!")

        print(f"Successfully saved {len(formatted_teams)} teams and defensive ratings.")
        return True  # Signal success

    except Exception as error:
        print(f"Error fetching team stats: {error}")
        return False  # Signal failure

# ============================================================
# END SECTION: Team Stats Fetcher
# ============================================================


# ============================================================
# SECTION: Player Game Log Fetcher
# Fetches the last N games for a specific player.
# ============================================================

def fetch_player_game_log(player_id, last_n_games=20):
    """
    Fetch the last N game logs for a specific player.

    This is useful for analyzing recent form (hot/cold streaks) and
    calculating how consistent (or inconsistent) a player has been lately.

    BEGINNER NOTE: A game log shows a player's stats game-by-game.
    For example: "March 1: 28 pts, March 3: 14 pts, March 5: 31 pts"
    This gives us much more information than just the season average.

    Args:
        player_id (int or str): The NBA player's unique ID
        last_n_games (int): How many recent games to return (default: 20)

    Returns:
        list of dict: Recent game stats, newest game first.
                      Returns empty list if the fetch fails.

    Example return value:
        [
            {'game_date': '2026-03-05', 'pts': 28, 'reb': 7, 'ast': 5, ...},
            {'game_date': '2026-03-03', 'pts': 14, 'reb': 4, 'ast': 8, ...},
        ]
    """
    # Import inside function for graceful failure
    try:
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        print("ERROR: nba_api is not installed. Run: pip install nba_api")
        return []

    try:
        # Fetch the player's game log
        game_log_endpoint = playergamelog.PlayerGameLog(
            player_id=player_id,
            season_type_all_star="Regular Season",
        )

        # Convert to list of dicts
        game_log_data = game_log_endpoint.get_data_frames()[0].to_dict("records")

        # Add API delay
        time.sleep(API_DELAY_SECONDS)

        # Take only the most recent N games
        recent_games = game_log_data[:last_n_games]

        # Build a clean list of game dictionaries
        formatted_games = []
        for game in recent_games:
            # Map nba_api column names to friendly names
            formatted_game = {
                "game_date": game.get("GAME_DATE", ""),     # Date of the game
                "matchup": game.get("MATCHUP", ""),          # e.g. "LAL vs. GSW"
                "win_loss": game.get("WL", ""),              # "W" or "L"
                "minutes": float(game.get("MIN", 0) or 0),  # Minutes played
                "pts": float(game.get("PTS", 0) or 0),       # Points
                "reb": float(game.get("REB", 0) or 0),       # Rebounds
                "ast": float(game.get("AST", 0) or 0),       # Assists
                "stl": float(game.get("STL", 0) or 0),       # Steals
                "blk": float(game.get("BLK", 0) or 0),       # Blocks
                "tov": float(game.get("TOV", 0) or 0),       # Turnovers
                "fg3m": float(game.get("FG3M", 0) or 0),     # 3-pointers made
                "ft_pct": float(game.get("FT_PCT", 0) or 0), # Free throw %
            }
            formatted_games.append(formatted_game)

        return formatted_games  # Return the list of recent games

    except Exception as error:
        print(f"Error fetching game log for player {player_id}: {error}")
        return []  # Return empty list on failure

# ============================================================
# END SECTION: Player Game Log Fetcher
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

    print("Starting full data update...")

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

    print("Player stats update complete. Starting team stats update...")

    # --------------------------------------------------------
    # Step 2: Fetch team stats
    # --------------------------------------------------------

    def team_progress(current, total, message):
        if progress_callback:
            progress_callback(10 + int(10 * current / max(total, 1)), 20, f"[Teams] {message}")

    results["teams"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(20, 20, "✅ All data updated!")

    print(f"Full update complete. Results: {results}")
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
        2. Fetch current rosters + player stats for tonight's teams only
        3. Fetch team stats for the analysis engine
        4. Fetch multi-signal player injury/availability status

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
        progress_callback(0, 40, "Step 1/4 — Fetching tonight's games...")

    games = fetch_todays_games()
    results["games"] = games

    if not games:
        print("fetch_all_todays_data: No games found for tonight.")
        return results

    if progress_callback:
        progress_callback(2, 40, f"Step 1/4 ✅ Found {len(games)} game(s). Fetching player rosters...")

    # --------------------------------------------------------
    # Step 2: Fetch player stats for tonight's teams only
    # --------------------------------------------------------
    def player_progress(current, total, message):
        if progress_callback:
            # Progress range for Step 2: steps 2-22 out of 40
            scaled = 2 + int(20 * current / max(total, 1))
            progress_callback(scaled, 40, f"Step 2/4 — {message}")

    results["players_updated"] = fetch_todays_players_only(
        games, progress_callback=player_progress
    )

    if progress_callback:
        status = "✅" if results["players_updated"] else "⚠️"
        progress_callback(22, 40, f"Step 2/4 {status} Player stats done. Fetching team stats...")

    # --------------------------------------------------------
    # Step 3: Fetch team stats
    # --------------------------------------------------------
    def team_progress(current, total, message):
        if progress_callback:
            # Progress range for Step 3: steps 22-29 out of 40
            scaled = 22 + int(7 * current / max(total, 1))
            progress_callback(scaled, 40, f"Step 3/4 — {message}")

    results["teams_updated"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(29, 40, "Step 3/4 ✅ Team stats done. Fetching injury/availability status...")

    # --------------------------------------------------------
    # Step 4: Fetch multi-signal injury/availability status
    # Pass tonight's games so Layer 4 can cross-reference rosters
    # --------------------------------------------------------
    try:
        injury_map = fetch_player_injury_status(todays_games=games)
        results["injury_status"] = injury_map
    except Exception as inj_err:
        print(f"fetch_all_todays_data: injury status fetch failed: {inj_err}")
        results["injury_status"] = {}

    if progress_callback:
        progress_callback(40, 40, "✅ All done! Games, players, team stats, and injury status loaded.")

    players_updated = results["players_updated"]
    teams_updated = results["teams_updated"]
    games_count = len(results["games"])
    print(f"fetch_all_todays_data complete: players_updated={players_updated}, "
          f"teams_updated={teams_updated}, games={games_count}")
    return results

# ============================================================
# END SECTION: One-Click Today's Data Fetcher
# ============================================================


# ============================================================
# SECTION: Team Roster Cache
# In-memory cache mapping team abbreviation → active player list.
# Populated by fetch_active_rosters() to avoid repeated API calls.
# ============================================================

# Module-level cache (lives as long as the Python process runs)
TEAM_ROSTER_CACHE = {}  # {team_abbrev: [player_name, ...]}


def fetch_active_rosters(team_abbrevs=None, progress_callback=None):
    """
    Fetch current active rosters for the given teams and populate TEAM_ROSTER_CACHE.

    Uses CommonTeamRoster to get the up-to-date roster for each team,
    reflecting all recent trades and signings.

    Args:
        team_abbrevs (list of str, optional): Team abbreviations to fetch.
            If None, fetches all 30 teams (slow, ~3-5 minutes).
        progress_callback (callable, optional): Called with (current, total, msg).

    Returns:
        dict: {team_abbrev: [player_name, ...]} — the populated cache.
    """
    try:
        from nba_api.stats.endpoints import commonteamroster
        from nba_api.stats.static import teams as nba_teams_static
    except ImportError:
        print("ERROR: nba_api is not installed. Run: pip install nba_api")
        return TEAM_ROSTER_CACHE

    all_nba_teams = nba_teams_static.get_teams()
    team_abbrev_to_id = {
        NBA_API_ABBREV_TO_OURS.get(t["abbreviation"], t["abbreviation"]): t["id"]
        for t in all_nba_teams
    }

    if team_abbrevs is None:
        team_abbrevs = list(team_abbrev_to_id.keys())

    total = len(team_abbrevs)
    for idx, abbrev in enumerate(sorted(team_abbrevs)):
        if progress_callback:
            progress_callback(idx, total, f"Fetching roster for {abbrev}...")

        team_id = team_abbrev_to_id.get(abbrev)
        if not team_id:
            continue

        try:
            roster_endpoint = commonteamroster.CommonTeamRoster(team_id=team_id)
            roster_df = roster_endpoint.get_data_frames()[0]
            player_names = roster_df["PLAYER"].tolist()
            TEAM_ROSTER_CACHE[abbrev] = player_names
            time.sleep(API_DELAY_SECONDS)
        except Exception as err:
            print(f"  Could not fetch roster for {abbrev}: {err}")

    return TEAM_ROSTER_CACHE


def get_cached_roster(team_abbrev):
    """
    Return the cached active roster for a team, or an empty list.

    Call fetch_active_rosters() first to populate the cache.

    Args:
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        list of str: Player names on the roster, or empty list.
    """
    return TEAM_ROSTER_CACHE.get(team_abbrev.upper(), [])

# ============================================================
# END SECTION: Team Roster Cache
# ============================================================


# ============================================================
# SECTION: Player Injury / Status Detection
# Multi-signal player availability detection using four layers:
#   Layer 1: CommonAllPlayers ROSTER_STATUS filter
#   Layer 2: LeagueDashPlayerStats GP vs Team GP ratio
#   Layer 3: Recent game log check (last 15 games) for recency
#   Layer 4: Cross-reference with CommonTeamRoster for today's teams
# ============================================================


def _save_injury_status(status_map):
    """
    Persist the injury status map to INJURY_STATUS_JSON_PATH.

    Stores the full status map as JSON so the Analysis page can load
    it on startup without an extra API call.

    Args:
        status_map (dict): player_name_lower -> status_dict
    """
    try:
        with open(INJURY_STATUS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(status_map, f, indent=2)
    except Exception as err:
        print(f"_save_injury_status: could not write {INJURY_STATUS_JSON_PATH}: {err}")


def fetch_player_injury_status(todays_games=None):
    """
    Multi-signal player availability detection.

    Uses four complementary signals to flag inactive, injured, or
    recently absent players without relying on a dedicated injury
    endpoint (which nba_api does not provide).

    Layer 1: CommonAllPlayers ROSTER_STATUS
        Players with ROSTERSTATUS == 0 are waived/released/not on any
        current NBA roster and are immediately flagged as "Out".

    Layer 2: LeagueDashPlayerStats GP vs Team GP ratio
        For each team, the maximum GP across all players approximates
        the total games the team has played. A player whose GP is
        significantly lower than that maximum (< 60% or >= 10 games
        behind) is flagged as Questionable / Injured Reserve.

    Layer 3: PlayerGameLog recency check (last 15 games)
        For players flagged in Layer 2, the last game date is checked.
        - No games in last 30 days → "Out (No Recent Games)"
        - No games in last 14 days → "Questionable"
        - No games in last 7 days  → "Day-to-Day"
        API calls are capped to 30 players (higher-priority players
        on today's teams are checked first).

    Layer 4: CommonTeamRoster cross-reference (optional)
        When todays_games is supplied, each playing team's current
        roster is fetched. A player from the stats database who is
        NOT on the current roster for their team is flagged "Out".

    Results are saved to INJURY_STATUS_JSON_PATH for session reuse.

    Args:
        todays_games (list of dict, optional): Tonight's games from
            fetch_todays_games(). When provided, Layer 4 runs and
            Layer 3 prioritises players on today's teams.

    Returns:
        dict: player_name_lower -> {
            "status": str,          # "Active"|"Out"|"Questionable"|"Day-to-Day"|"Injured Reserve"
            "injury_note": str,     # Human-readable reason
            "games_missed": int,    # Consecutive recent games missed (team total − player GP)
            "return_date": str,     # Always "" — not available from nba_api
            "last_game_date": str,  # ISO date of most recent game, or ""
            "gp_ratio": float,      # player GP / team max GP (0.0–1.0)
        }
    """
    try:
        from nba_api.stats.endpoints import (
            commonallplayers,
            leaguedashplayerstats,
            playergamelog,
            commonteamroster,
        )
        from nba_api.stats.static import teams as nba_teams_static
    except ImportError:
        return {}

    try:
        import datetime as _dt

        today = _dt.date.today()

        # --------------------------------------------------------
        # Layer 1: CommonAllPlayers — ROSTER_STATUS
        # Players with ROSTERSTATUS == 0 are no longer on any roster.
        # --------------------------------------------------------
        print("fetch_player_injury_status: Layer 1 — CommonAllPlayers ROSTER_STATUS")
        all_players_ep = commonallplayers.CommonAllPlayers(
            is_only_current_season=1,
            league_id="00",
        )
        time.sleep(API_DELAY_SECONDS)
        all_players_rows = all_players_ep.get_data_frames()[0].to_dict("records")

        roster_status_by_id = {}   # player_id (int) → 0 or 1
        for row in all_players_rows:
            pid = row.get("PERSON_ID")
            if pid is not None:
                roster_status_by_id[int(pid)] = int(row.get("ROSTERSTATUS", 1) or 1)

        # --------------------------------------------------------
        # Layer 2: LeagueDashPlayerStats — GP vs Team GP ratio
        # --------------------------------------------------------
        print("fetch_player_injury_status: Layer 2 — LeagueDashPlayerStats GP ratio")
        stats_ep = leaguedashplayerstats.LeagueDashPlayerStats(
            per_mode_detailed="PerGame",
            season_type_all_star="Regular Season",
        )
        time.sleep(API_DELAY_SECONDS)
        player_stats = stats_ep.get_data_frames()[0].to_dict("records")

        # Compute team maximum GP as a proxy for total team games played
        team_max_gp = {}
        for row in player_stats:
            team = row.get("TEAM_ABBREVIATION", "")
            gp = int(row.get("GP", 0) or 0)
            if team and gp > team_max_gp.get(team, 0):
                team_max_gp[team] = gp

        # Build initial status map; identify players needing Layer 3 check
        status_map = {}
        needs_gamelog_check = []   # [(priority_score, player_id, name_key)]

        # Determine today's playing teams to prioritise Layer 3 checks
        today_team_abbrevs = set()
        if todays_games:
            for game in todays_games:
                today_team_abbrevs.add(game.get("home_team", ""))
                today_team_abbrevs.add(game.get("away_team", ""))
            today_team_abbrevs.discard("")

        for row in player_stats:
            name = row.get("PLAYER_NAME", "")
            if not name:
                continue

            pid_raw = row.get("PLAYER_ID")
            pid = int(pid_raw) if pid_raw is not None else None
            team = row.get("TEAM_ABBREVIATION", "")
            team = NBA_API_ABBREV_TO_OURS.get(team, team)
            gp = int(row.get("GP", 0) or 0)

            key = name.lower().strip()

            # Layer 1 verdict
            on_current_roster = roster_status_by_id.get(pid, 1) == 1 if pid else True

            # Layer 2 verdict — GP vs team max GP
            team_total = team_max_gp.get(row.get("TEAM_ABBREVIATION", ""), gp)
            games_missed = max(0, team_total - gp)
            gp_ratio = gp / team_total if team_total > 0 else 1.0

            if not on_current_roster:
                status = "Out"
                note = "Not on current roster"
            elif gp == 0:
                status = "Out"
                note = "0 games played this season"
            elif gp_ratio < INJURED_RESERVE_GP_RATIO or games_missed >= INJURED_RESERVE_GAMES_THRESHOLD:
                # Very likely long-term out — needs recency confirmation
                status = "Injured Reserve"
                note = f"Only {gp_ratio:.0%} of team games played ({gp}/{team_total})"
                priority = 2 if team in today_team_abbrevs else 1
                needs_gamelog_check.append((priority, pid, key))
            elif gp_ratio < QUESTIONABLE_GP_RATIO or games_missed >= QUESTIONABLE_GAMES_THRESHOLD:
                # Suspicious absence — may be recent injury
                status = "Questionable"
                note = f"Missed {games_missed} of {team_total} team games"
                priority = 2 if team in today_team_abbrevs else 1
                needs_gamelog_check.append((priority, pid, key))
            else:
                status = "Active"
                note = ""

            status_map[key] = {
                "status": status,
                "injury_note": note,
                "games_missed": games_missed,
                "return_date": "",
                "last_game_date": "",
                "gp_ratio": round(gp_ratio, 3),
                "_player_id_int": pid,  # internal — used by Layer 3/4, stripped later
            }

        # --------------------------------------------------------
        # Layer 3: PlayerGameLog — recency check for flagged players
        # Cap at MAX_GAMELOG_CHECKS API calls; prioritise today's team players
        # --------------------------------------------------------
        print(f"fetch_player_injury_status: Layer 3 — GameLog recency ({len(needs_gamelog_check)} flagged)")
        needs_gamelog_check.sort(key=lambda x: x[0], reverse=True)  # high priority first
        checked = 0
        for priority, pid, name_key in needs_gamelog_check:
            if checked >= MAX_GAMELOG_CHECKS or pid is None:
                break
            try:
                log_ep = playergamelog.PlayerGameLog(
                    player_id=pid,
                    season_type_all_star="Regular Season",
                    last_n_games=RECENT_GAMES_WINDOW,
                )
                time.sleep(API_DELAY_SECONDS)
                log_data = log_ep.get_data_frames()[0].to_dict("records")
                checked += 1

                if not log_data:
                    # No games at all in recent log → definitively Out
                    if name_key in status_map:
                        status_map[name_key]["status"] = "Out"
                        status_map[name_key]["injury_note"] = "No games in recent game log"
                    continue

                # Parse the last game date (nba_api format: "MMM DD, YYYY" or "YYYY-MM-DD")
                last_date = None
                game_date_str = log_data[0].get("GAME_DATE", "")
                for fmt in ("%b %d, %Y", "%Y-%m-%d", "%B %d, %Y"):
                    try:
                        last_date = _dt.datetime.strptime(game_date_str, fmt).date()
                        break
                    except ValueError:
                        continue

                if last_date and name_key in status_map:
                    status_map[name_key]["last_game_date"] = str(last_date)
                    days_ago = (today - last_date).days
                    entry = status_map[name_key]
                    if days_ago >= OUT_DAYS_THRESHOLD:
                        entry["status"] = "Out"
                        entry["injury_note"] = f"No games in last {days_ago} days"
                    elif days_ago >= QUESTIONABLE_DAYS_THRESHOLD:
                        # Downgrade Injured Reserve to Questionable when recency is moderate
                        if entry["status"] == "Injured Reserve":
                            entry["status"] = "Questionable"
                        entry["injury_note"] = f"Last played {days_ago} days ago"
                    elif days_ago >= DAY_TO_DAY_DAYS_THRESHOLD:
                        if entry["status"] in ("Injured Reserve", "Questionable"):
                            entry["status"] = "Day-to-Day"
                        entry["injury_note"] = f"Last played {days_ago} days ago"
                    else:
                        # Played within DAY_TO_DAY_DAYS_THRESHOLD → Active despite low GP ratio
                        entry["status"] = "Active"
                        entry["injury_note"] = f"Last played {days_ago} days ago (low game count)"

            except Exception as log_err:
                print(f"  Layer 3 game log check failed for player_id={pid}: {log_err}")

        # --------------------------------------------------------
        # Layer 4: CommonTeamRoster cross-reference (today's teams only)
        # Players whose listed team is playing today but who are NOT
        # on the current roster are marked Out.
        # --------------------------------------------------------
        if todays_games and today_team_abbrevs:
            print(f"fetch_player_injury_status: Layer 4 — Roster cross-reference ({len(today_team_abbrevs)} teams)")
            all_nba_teams = nba_teams_static.get_teams()
            abbrev_to_id = {
                NBA_API_ABBREV_TO_OURS.get(t["abbreviation"], t["abbreviation"]): t["id"]
                for t in all_nba_teams
            }
            # Build set of player_ids currently on today's active rosters
            current_roster_ids = set()
            for abbrev in sorted(today_team_abbrevs):
                team_id = abbrev_to_id.get(abbrev)
                if not team_id:
                    continue
                try:
                    roster_ep = commonteamroster.CommonTeamRoster(team_id=team_id)
                    roster_df = roster_ep.get_data_frames()[0]
                    for pid_val in roster_df["PLAYER_ID"].tolist():
                        current_roster_ids.add(int(pid_val))
                    time.sleep(API_DELAY_SECONDS)
                except Exception as roster_err:
                    print(f"  Layer 4 roster fetch failed for {abbrev}: {roster_err}")

            # Flag players on today's teams who are not on the current roster
            for row in player_stats:
                team = NBA_API_ABBREV_TO_OURS.get(
                    row.get("TEAM_ABBREVIATION", ""), row.get("TEAM_ABBREVIATION", "")
                )
                if team not in today_team_abbrevs:
                    continue
                pid_raw = row.get("PLAYER_ID")
                pid = int(pid_raw) if pid_raw is not None else None
                name = row.get("PLAYER_NAME", "")
                key = name.lower().strip()
                if pid and pid not in current_roster_ids and key in status_map:
                    entry = status_map[key]
                    if entry["status"] == "Active":
                        entry["status"] = "Out"
                        entry["injury_note"] = "Not on current team roster"

        # --------------------------------------------------------
        # Layer 5: External web scraping (RotoWire + NBA.com)
        # Provides real-time GTD/Out/Doubtful designations, specific
        # injury details, and expected return dates that nba_api cannot
        # supply.  Runs AFTER the nba_api layers so it can OVERRIDE
        # stale nba_api data when authoritative scraped data is available.
        # If ALL scrapers fail the status_map is left untouched.
        # --------------------------------------------------------
        print("fetch_player_injury_status: Layer 5 — external web scraping (RotoWire + NBA.com + ESPN)")
        try:
            # Prefer the consolidated multi-source fetcher (web_scrapers.py);
            # fall back to the original single-module fetcher if unavailable.
            try:
                from data.web_scrapers import fetch_multi_source_injury_status
                scraped = fetch_multi_source_injury_status(todays_games=todays_games)
            except ImportError:
                from data.web_scraper import fetch_all_injury_data
                scraped = fetch_all_injury_data()

            if scraped:
                overrides = 0
                new_entries = 0
                for scraped_key, scraped_entry in scraped.items():
                    scraped_status = scraped_entry.get("status", "")
                    # Severity rankings — higher value = more severe / authoritative
                    _SEVERITY = {
                        "Out": 5,
                        "Injured Reserve": 5,
                        "Doubtful": 4,
                        "GTD": 3,
                        "Questionable": 3,
                        "Day-to-Day": 2,
                        "Probable": 1,
                        "Active": 0,
                        "Unknown": -1,
                    }
                    scraped_severity = _SEVERITY.get(scraped_status, -1)

                    if scraped_key in status_map:
                        existing = status_map[scraped_key]
                        existing_severity = _SEVERITY.get(existing.get("status", ""), 0)
                        # Override when scraped data is MORE severe (or is authoritative Out)
                        # and NOT "Unknown" (which would represent a scraper parse error)
                        if scraped_severity > existing_severity and scraped_severity >= 0:
                            existing["status"] = scraped_status
                            # injury_note preserves the nba_api-generated signal for
                            # backward compat; injury holds the scraped body-part detail.
                            existing["return_date"] = (
                                scraped_entry.get("return_date", "") or
                                existing.get("return_date", "")
                            )
                            existing["injury"] = scraped_entry.get("injury", "")
                            existing["source"] = scraped_entry.get("source", "")
                            existing["comment"] = scraped_entry.get("comment", "")
                            overrides += 1
                        else:
                            # Still capture injury detail even without status override
                            if not existing.get("injury"):
                                existing["injury"] = scraped_entry.get("injury", "")
                            if not existing.get("return_date"):
                                existing["return_date"] = scraped_entry.get("return_date", "")
                            if not existing.get("source"):
                                existing["source"] = scraped_entry.get("source", "")
                    else:
                        # Player found by scraper but not in nba_api data — add entry
                        status_map[scraped_key] = {
                            "status":      scraped_status if scraped_severity > 0 else "Active",
                            "injury_note": scraped_entry.get("injury", ""),
                            "games_missed": 0,
                            "return_date":  scraped_entry.get("return_date", ""),
                            "last_game_date": "",
                            "gp_ratio":    1.0,
                            "injury":      scraped_entry.get("injury", ""),
                            "source":      scraped_entry.get("source", ""),
                            "comment":     scraped_entry.get("comment", ""),
                        }
                        new_entries += 1

                print(
                    f"fetch_player_injury_status Layer 5: {overrides} overrides, "
                    f"{new_entries} new entries from web scraping"
                )
            else:
                print("fetch_player_injury_status Layer 5: no scraped data returned — keeping nba_api results")

        except Exception as layer5_err:
            # Layer 5 failure must never break the existing pipeline
            print(f"fetch_player_injury_status Layer 5 error (ignored): {layer5_err}")

        # Strip the internal helper field before returning / saving
        for entry in status_map.values():
            entry.pop("_player_id_int", None)

        # Persist to disk for session reuse
        _save_injury_status(status_map)

        active_count = sum(1 for v in status_map.values() if v["status"] == "Active")
        out_count    = sum(1 for v in status_map.values() if v["status"] in ("Out", "Injured Reserve"))
        print(f"fetch_player_injury_status complete: {active_count} active, {out_count} out/IR, "
              f"{len(status_map)} total")
        return status_map

    except Exception as error:
        print(f"fetch_player_injury_status error: {error}")
        return {}

# ============================================================
# END SECTION: Player Injury / Status Detection
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
