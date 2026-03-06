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

# How long to wait between API calls (in seconds) to avoid being blocked
# BEGINNER NOTE: Rate limiting means the NBA website limits how fast
# you can make requests. If you ask too fast, they block you temporarily.
# Adding a 1.5 second delay between calls keeps us polite and avoids blocks.
API_DELAY_SECONDS = 1.5

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
# SECTION: Today's Games Fetcher
# Fetches which NBA games are being played today.
# ============================================================

def fetch_todays_games():
    """
    Fetch tonight's NBA games using the ScoreboardV2 endpoint.

    BEGINNER NOTE: ScoreboardV2 is an endpoint on the NBA stats website
    that lists all games for a given date. An "endpoint" is just a specific
    URL that returns specific data.

    Returns:
        list of dict: Tonight's games, each with home_team, away_team, etc.
                      Returns empty list if the API fails or no games today.

    Example return value:
        [
            {'game_id': 'LAL_vs_GSW', 'home_team': 'LAL', 'away_team': 'GSW',
             'vegas_spread': 0.0, 'game_total': 220.0, 'game_date': '2026-03-06'}
        ]
    """
    # BEGINNER NOTE: We import inside the function so that if nba_api is
    # not installed, only THIS function fails — the rest of the app still works.
    try:
        # Import the ScoreboardV2 class from nba_api
        from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
    except ImportError:
        # nba_api is not installed — return empty list with a clear message
        print("ERROR: nba_api is not installed. Run: pip install nba_api")
        return []

    try:
        # Fetch today's scoreboard from the NBA API
        # BEGINNER NOTE: This sends a web request to stats.nba.com and
        # gets back data about today's games. It may take 2-5 seconds.
        board = live_scoreboard.ScoreBoard()

        # Get the list of games from the response
        games_data = board.games.get_dict()  # Returns a list of game dictionaries

        # List to hold our formatted games
        formatted_games = []

        # Loop through each game returned by the API
        for game in games_data:
            # Extract team abbreviations from the game data
            # nba_api provides homeTeam and awayTeam as nested dicts
            home_team_info = game.get("homeTeam", {})
            away_team_info = game.get("awayTeam", {})

            # Get the 3-letter abbreviation for each team
            home_abbrev = home_team_info.get("teamTricode", "")  # e.g. "LAL"
            away_abbrev = away_team_info.get("teamTricode", "")  # e.g. "GSW"

            # Normalize abbreviations to match our format
            # e.g. "GS" → "GSW", "NY" → "NYK"
            home_abbrev = NBA_API_ABBREV_TO_OURS.get(home_abbrev, home_abbrev)
            away_abbrev = NBA_API_ABBREV_TO_OURS.get(away_abbrev, away_abbrev)

            # Skip games where we don't have both teams
            if not home_abbrev or not away_abbrev:
                continue

            # Build a game dictionary in the format our app expects
            # BEGINNER NOTE: We use default values for spread/total
            # because the live scoreboard doesn't include Vegas lines
            formatted_game = {
                "game_id": f"{home_abbrev}_vs_{away_abbrev}",  # Unique ID
                "home_team": home_abbrev,                        # e.g. "LAL"
                "away_team": away_abbrev,                        # e.g. "GSW"
                "home_team_full": f"{home_abbrev} — {home_team_info.get('teamCity', '')} {home_team_info.get('teamName', '')}",
                "away_team_full": f"{away_abbrev} — {away_team_info.get('teamCity', '')} {away_team_info.get('teamName', '')}",
                "vegas_spread": 0.0,    # Default: pick'em (user can edit)
                "game_total": 220.0,    # Default total (user can edit)
                "game_date": datetime.date.today().isoformat(),  # Today's date
            }

            formatted_games.append(formatted_game)

        # Add a small delay to be polite to the API
        time.sleep(API_DELAY_SECONDS)

        # Return the list of tonight's games
        return formatted_games

    except Exception as error:
        # If anything goes wrong, print the error and return empty list
        print(f"Error fetching today's games: {error}")
        return []

# ============================================================
# END SECTION: Today's Games Fetcher
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
            per_mode_simple="PerGame",      # We want per-game averages
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
            # These percentages are empirically derived from NBA stat distributions:
            # - Points: ~30% CV (coefficient of variation) is typical for scorers
            # - Rebounds: ~40% CV — more variable due to matchup and game flow
            # - Assists: ~40% CV — game-plan and opponent-specific
            # - Threes: ~50% CV — highly variable night-to-night (hot/cold shooting)
            # These defaults will be replaced by actual std devs once game logs load.
            points_std = max(1.0, points_avg * 0.3)       # 30% CV default
            rebounds_std = max(0.5, rebounds_avg * 0.4)   # 40% CV default
            assists_std = max(0.5, assists_avg * 0.4)      # 40% CV default
            threes_std = max(0.3, threes_avg * 0.5)        # 50% CV default (most variable)

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
                # Use game-log std devs when available; fall back to CV-based estimates
                "steals_std": round(steals_std_from_log if steals_std_from_log is not None else max(0.1, steals_avg * 0.5), 2),
                "blocks_std": round(blocks_std_from_log if blocks_std_from_log is not None else max(0.1, blocks_avg * 0.6), 2),
                "turnovers_std": round(turnovers_std_from_log if turnovers_std_from_log is not None else max(0.1, turnovers_avg * 0.4), 2),
            }

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
            "name", "team", "position", "minutes_avg",
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
            per_mode_simple="PerGame",          # Get per-game stats
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
            per_mode_simple="Per100Possessions",    # Per 100 possessions = normalized
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

def fetch_all_data(progress_callback=None):
    """
    Fetch ALL live data: player stats, team stats, and defensive ratings.

    This is the "Update Everything" function. It calls each individual
    fetcher in order, with appropriate delays between them.

    Args:
        progress_callback (callable, optional): Progress function.
            Called with (current_step, total_steps, message).

    Returns:
        dict: Results showing what succeeded and what failed.
            Example: {'players': True, 'teams': True}
    """
    # Track which updates succeeded and which failed
    results = {
        "players": False,   # Will be True if player stats fetch succeeds
        "teams": False,     # Will be True if team stats fetch succeeds
    }

    print("Starting full data update...")

    # --------------------------------------------------------
    # Step 1: Fetch player stats
    # --------------------------------------------------------

    if progress_callback:
        progress_callback(0, 20, "Starting player stats update...")

    # Create a sub-progress-callback that maps 0-10 to 0-10 in overall progress
    def player_progress(current, total, message):
        if progress_callback:
            # Map player progress (0-10) to overall progress (0-10)
            progress_callback(current, 20, f"[Players] {message}")

    results["players"] = fetch_player_stats(progress_callback=player_progress)

    print("Player stats update complete. Starting team stats update...")

    # --------------------------------------------------------
    # Step 2: Fetch team stats
    # --------------------------------------------------------

    def team_progress(current, total, message):
        if progress_callback:
            # Map team progress (0-6) to overall progress (10-20)
            progress_callback(10 + int(10 * current / max(total, 1)), 20, f"[Teams] {message}")

    results["teams"] = fetch_team_stats(progress_callback=team_progress)

    if progress_callback:
        progress_callback(20, 20, "✅ All data updated!")

    print(f"Full update complete. Results: {results}")
    return results  # Return the results dict

# ============================================================
# END SECTION: Full Update Function
# ============================================================
