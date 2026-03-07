# ============================================================
# FILE: data/data_manager.py
# PURPOSE: Load, save, and manage all CSV data files for the app.
#          Handles player stats, prop lines, and team data.
# CONNECTS TO: All pages use this to load data
# CONCEPTS COVERED: CSV reading/writing, file paths, caching
# ============================================================

# Standard library imports only
import csv        # Built-in CSV reader/writer
import os         # File path operations
import json       # For session state persistence
import datetime   # For timestamp handling
import unicodedata  # For normalizing unicode characters in names
import re           # For regex-based suffix stripping
from pathlib import Path  # Modern file path handling


# ============================================================
# SECTION: File Path Constants
# Define paths to all data files relative to the project root.
# Using pathlib.Path makes this work on Windows, Mac, and Linux.
# ============================================================

# Get the directory where this file lives (the 'data' folder)
DATA_DIRECTORY = Path(__file__).parent

# Build full paths to each CSV file
PLAYERS_CSV_PATH = DATA_DIRECTORY / "sample_players.csv"
PROPS_CSV_PATH = DATA_DIRECTORY / "sample_props.csv"
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"

# Path to the live data timestamp file
# BEGINNER NOTE: This JSON file is created by live_data_fetcher.py
# when real data is downloaded. Its existence tells us if live data is loaded.
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"

# ============================================================
# END SECTION: File Path Constants
# ============================================================


# ============================================================
# SECTION: CSV Loading Functions
# ============================================================

def load_players_data():
    """
    Load all player data from the sample_players.csv file.

    Returns a list of dictionaries, where each dictionary
    represents one player with all their stats as keys.

    Returns:
        list of dict: Player rows, e.g.:
            [{'name': 'LeBron James', 'team': 'LAL', ...}, ...]

    Example:
        players = load_players_data()
        lebron = players[0]
        print(lebron['points_avg'])  # → '24.8'
    """
    return _load_csv_file(PLAYERS_CSV_PATH)


def load_props_data():
    """
    Load all prop lines from the sample_props.csv file.

    Returns:
        list of dict: Prop rows, e.g.:
            [{'player_name': 'LeBron James', 'stat_type': 'points',
              'line': '24.5', 'platform': 'PrizePicks', ...}, ...]
    """
    return _load_csv_file(PROPS_CSV_PATH)


def load_teams_data():
    """
    Load all 30 NBA teams from teams.csv.

    Returns:
        list of dict: Team rows with pace, ortg, drtg, etc.
    """
    return _load_csv_file(TEAMS_CSV_PATH)


def load_defensive_ratings_data():
    """
    Load team defensive ratings by position from defensive_ratings.csv.

    Returns:
        list of dict: Defensive rating rows with vs_PG_pts, etc.
    """
    return _load_csv_file(DEFENSIVE_RATINGS_CSV_PATH)


def _load_csv_file(file_path):
    """
    Internal helper: load any CSV file and return list of dicts.

    Each row becomes a dictionary mapping column name → value.
    CSV headers become the dictionary keys.

    Args:
        file_path (Path or str): Path to the CSV file

    Returns:
        list of dict: Rows as dictionaries, or empty list if error
    """
    # Convert to Path object if it's a string
    file_path = Path(file_path)

    # Check if the file exists before trying to open it
    if not file_path.exists():
        # Return empty list instead of crashing
        return []

    rows = []  # Will hold all the row dictionaries

    try:
        # Open the file for reading
        # encoding='utf-8' handles special characters
        # newline='' is required by Python's csv module
        with open(file_path, encoding="utf-8", newline="") as csv_file:
            # DictReader automatically uses the first row as column names
            # BEGINNER NOTE: csv.DictReader is like a spreadsheet reader —
            # it maps each row's values to its column header names
            reader = csv.DictReader(csv_file)

            for row in reader:
                # Strip whitespace from all values
                # BEGINNER NOTE: dict comprehension builds a new dict
                # by looping over key-value pairs and stripping spaces
                cleaned_row = {
                    key.strip(): value.strip()
                    for key, value in row.items()
                    if key is not None  # Skip None keys (empty columns)
                }
                rows.append(cleaned_row)

    except Exception as error:
        # If anything goes wrong, return empty list
        # The app will show a message asking user to check the file
        print(f"Error loading {file_path}: {error}")
        return []

    return rows


# ============================================================
# END SECTION: CSV Loading Functions
# ============================================================


# ============================================================
# SECTION: Player Lookup Functions
# ============================================================

def find_player_by_name(players_list, player_name):
    """
    Find a player by their name in the players list.

    Uses fuzzy/normalized matching so slight name differences
    (suffixes, unicode, nicknames) are handled automatically.

    Args:
        players_list (list of dict): Loaded player data
        player_name (str): Player name to search for

    Returns:
        dict or None: Player data dict, or None if not found

    Example:
        player = find_player_by_name(players, "LeBron James")
        print(player['points_avg'])  # → '24.8'
    """
    # Delegate to the fuzzy matcher which handles all matching strategies
    return find_player_by_name_fuzzy(players_list, player_name)


# ============================================================
# SECTION: Player Name Normalization & Fuzzy Matching
# These helpers ensure props from PrizePicks/Underdog/DraftKings
# match our internal player database even when names differ in
# capitalization, unicode accents, Jr./III suffixes, or nicknames.
# ============================================================

# Common nickname / alias mismatches between prop platforms and nba_api.
# Key = variant used by prop sites, Value = canonical name in our DB.
NAME_ALIASES = {
    "nic claxton": "nicolas claxton",
    "nicolas claxton": "nicolas claxton",
    "og anunoby": "o.g. anunoby",
    "o.g. anunoby": "o.g. anunoby",
    "mo bamba": "mohamed bamba",
    "tj mcconnell": "t.j. mcconnell",
    "t.j. mcconnell": "t.j. mcconnell",
    "tj warren": "t.j. warren",
    "cj mccollum": "c.j. mccollum",
    "c.j. mccollum": "c.j. mccollum",
    "pj tucker": "p.j. tucker",
    "p.j. tucker": "p.j. tucker",
    "rj barrett": "r.j. barrett",
    "r.j. barrett": "r.j. barrett",
    "aj green": "a.j. green",
    "nah'shon hyland": "bones hyland",
    "bones hyland": "bones hyland",
    "gary trent jr": "gary trent jr.",
    "gary trent jr.": "gary trent jr.",
    "wendell carter jr": "wendell carter jr.",
    "wendell carter jr.": "wendell carter jr.",
    "jaren jackson jr": "jaren jackson jr.",
    "jaren jackson jr.": "jaren jackson jr.",
    "kenyon martin jr": "kenyon martin jr.",
    "kenyon martin jr.": "kenyon martin jr.",
    "kevin porter jr": "kevin porter jr.",
    "larry nance jr": "larry nance jr.",
    "otto porter jr": "otto porter jr.",
    "derrick jones jr": "derrick jones jr.",
    "marcus morris sr": "marcus morris sr.",
    "naji marshall": "naji marshall",
    "alex len": "alex len",
    "alexandre sarr": "alexandre sarr",
    "goga bitadze": "goga bitadze",
    "giddey": "josh giddey",
    "josh giddey": "josh giddey",
    "sga": "shai gilgeous-alexander",
    "shai": "shai gilgeous-alexander",
    "shai gilgeous-alexander": "shai gilgeous-alexander",
    "kt": "karl-anthony towns",
    "karl-anthony towns": "karl-anthony towns",
    "zion": "zion williamson",
    "zion williamson": "zion williamson",
    "kd": "kevin durant",
    "kevin durant": "kevin durant",
    "kyrie": "kyrie irving",
    "kyrie irving": "kyrie irving",
    "steph": "stephen curry",
    "stephen curry": "stephen curry",
    "lebron": "lebron james",
    "lebron james": "lebron james",
    "bron": "lebron james",
    "ad": "anthony davis",
    "anthony davis": "anthony davis",
    "joker": "nikola jokic",
    "nikola jokic": "nikola jokic",
    "embiid": "joel embiid",
    "joel embiid": "joel embiid",
    "luka": "luka doncic",
    "luka doncic": "luka doncic",
    "tatum": "jayson tatum",
    "jayson tatum": "jayson tatum",
    "ja": "ja morant",
    "ja morant": "ja morant",
    "jrue holiday": "jrue holiday",
    "demar derozan": "demar derozan",
    "pascal siakam": "pascal siakam",
    "darius garland": "darius garland",
    "donovan mitchell": "donovan mitchell",
    "damian lillard": "damian lillard",
    "dam lillard": "damian lillard",
    "dame": "damian lillard",
    "khris middleton": "khris middleton",
    "giannis": "giannis antetokounmpo",
    "giannis antetokounmpo": "giannis antetokounmpo",
    "bam": "bam adebayo",
    "bam adebayo": "bam adebayo",
    "jimmy butler": "jimmy butler",
    "jimmy": "jimmy butler",
    "trae": "trae young",
    "trae young": "trae young",
    "devin booker": "devin booker",
    "book": "devin booker",
    "ayton": "deandre ayton",
    "deandre ayton": "deandre ayton",
}

# Suffixes to strip when normalizing player names for matching
_NAME_SUFFIXES_TO_STRIP = re.compile(
    r'\s+(jr\.?|sr\.?|ii|iii|iv|v)$',
    flags=re.IGNORECASE,
)


def normalize_player_name(name):
    """
    Normalize a player name for fuzzy matching.

    Steps:
    1. Strip leading/trailing whitespace
    2. Lowercase
    3. Normalize unicode (NFD → ASCII where possible, e.g., é → e)
    4. Remove trailing suffixes (Jr., Sr., II, III, IV)
    5. Collapse multiple spaces

    Args:
        name (str): Raw player name (e.g., "LeBron James Jr.")

    Returns:
        str: Normalized name (e.g., "lebron james")

    Example:
        normalize_player_name("Nikola Jokić") → "nikola jokic"
        normalize_player_name("Jaren Jackson Jr.") → "jaren jackson"
    """
    if not name:
        return ""

    # Step 1: Strip and lowercase
    name = name.strip().lower()

    # Step 2: Normalize unicode characters (e.g., ć → c, é → e)
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Step 3: Strip common suffixes (Jr., Sr., II, III, etc.)
    name = _NAME_SUFFIXES_TO_STRIP.sub("", name).strip()

    # Step 4: Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def find_player_by_name_fuzzy(players_list, player_name):
    """
    Find a player using fuzzy / normalized name matching.

    Matching order (first match wins):
    1. Exact case-insensitive match
    2. Alias lookup (common nickname / platform name variants)
    3. Normalized name match (strip suffixes + unicode)
    4. Partial / substring match on normalized names

    Args:
        players_list (list of dict): Loaded player data
        player_name (str): Player name from prop (may be a nickname/alias)

    Returns:
        dict or None: Player data dict, or None if not found

    Example:
        find_player_by_name_fuzzy(players, "Nic Claxton")
        → same result as find_player_by_name(players, "Nicolas Claxton")
    """
    if not player_name:
        return None

    search_lower = player_name.lower().strip()

    # --- Pass 1: Exact case-insensitive ---
    for player in players_list:
        if player.get("name", "").lower().strip() == search_lower:
            return player

    # --- Pass 2: Alias lookup ---
    alias_target = NAME_ALIASES.get(search_lower)
    if alias_target:
        for player in players_list:
            if player.get("name", "").lower().strip() == alias_target:
                return player

    # --- Pass 3: Normalized name match (strip suffixes + unicode) ---
    search_normalized = normalize_player_name(player_name)
    for player in players_list:
        stored_normalized = normalize_player_name(player.get("name", ""))
        if stored_normalized == search_normalized and search_normalized:
            return player

    # --- Pass 4: Partial / substring match on normalized names ---
    for player in players_list:
        stored_normalized = normalize_player_name(player.get("name", ""))
        if (search_normalized in stored_normalized or stored_normalized in search_normalized) \
                and len(search_normalized) > 3:
            return player

    return None


def get_roster_health_report(props_list, players_list):
    """
    Check which props have matching players in the database.

    Returns a report showing matched vs unmatched props so the user
    can identify name mismatches before running analysis.

    Args:
        props_list (list of dict): Current props (with 'player_name')
        players_list (list of dict): Loaded player data

    Returns:
        dict: {
            'matched': list of str (player names that matched),
            'unmatched': list of str (player names not found),
            'match_count': int,
            'total_count': int,
            'match_rate': float (0.0–1.0),
        }

    Example:
        report = get_roster_health_report(props, players)
        if report['unmatched']:
            st.warning(f"Unmatched: {report['unmatched']}")
    """
    matched = []
    unmatched = []
    seen = set()  # Deduplicate player names in report

    for prop in props_list:
        name = prop.get("player_name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)

        player = find_player_by_name_fuzzy(players_list, name)
        if player:
            matched.append(name)
        else:
            unmatched.append(name)

    total = len(matched) + len(unmatched)
    match_rate = len(matched) / total if total > 0 else 1.0

    return {
        "matched": sorted(matched),
        "unmatched": sorted(unmatched),
        "match_count": len(matched),
        "total_count": total,
        "match_rate": round(match_rate, 3),
    }


def validate_props_against_roster(props_list, players_list):
    """
    Validate every prop against the player database with detailed status.

    Returns three categories:
    - matched:       props with a definitive name match (exact or normalized)
    - fuzzy_matched: props where we found a probable match (partial/alias)
    - unmatched:     props where no match was found

    For each unmatched prop, a suggestion is provided (closest player name).

    Args:
        props_list (list of dict): Prop dicts with 'player_name'
        players_list (list of dict): Player dicts with 'name'

    Returns:
        dict: {
            'matched':       list of {prop, matched_name},
            'fuzzy_matched': list of {prop, matched_name, suggestion},
            'unmatched':     list of {prop, suggestion or None},
            'total':         int,
            'matched_count': int,
        }

    Example:
        report = validate_props_against_roster(props, players)
        for item in report['unmatched']:
            print(f"No match: {item['prop']['player_name']} → suggest: {item['suggestion']}")
    """
    matched = []
    fuzzy_matched = []
    unmatched = []

    # Build a quick exact-name index for fast lookup
    exact_name_index = {
        p.get("name", "").lower().strip(): p.get("name", "")
        for p in players_list
        if p.get("name")
    }

    all_player_names_list = [p.get("name", "") for p in players_list if p.get("name")]

    for prop in props_list:
        raw_name = prop.get("player_name", "").strip()
        if not raw_name:
            continue

        # --- Try exact match ---
        if raw_name.lower() in exact_name_index:
            matched.append({
                "prop": prop,
                "matched_name": exact_name_index[raw_name.lower()],
                "match_type": "exact",
            })
            continue

        # --- Try alias lookup ---
        alias_target = NAME_ALIASES.get(raw_name.lower())
        if alias_target and alias_target in exact_name_index:
            matched.append({
                "prop": prop,
                "matched_name": exact_name_index[alias_target],
                "match_type": "alias",
            })
            continue

        # --- Try normalized match ---
        normalized_search = normalize_player_name(raw_name)
        normalized_match = None
        for p_name in all_player_names_list:
            if normalize_player_name(p_name) == normalized_search and normalized_search:
                normalized_match = p_name
                break

        if normalized_match:
            # Treat normalized as a confident match (same player, different formatting)
            matched.append({
                "prop": prop,
                "matched_name": normalized_match,
                "match_type": "normalized",
            })
            continue

        # --- Try partial / substring match ---
        partial_match = None
        for p_name in all_player_names_list:
            stored_norm = normalize_player_name(p_name)
            if (normalized_search in stored_norm or stored_norm in normalized_search) \
                    and len(normalized_search) > 3:
                partial_match = p_name
                break

        if partial_match:
            fuzzy_matched.append({
                "prop": prop,
                "matched_name": partial_match,
                "match_type": "partial",
                "suggestion": f"Did you mean '{partial_match}'?",
            })
            continue

        # --- No match: find closest suggestion via simple edit distance ---
        suggestion = _find_closest_name(raw_name, all_player_names_list)
        unmatched.append({
            "prop": prop,
            "suggestion": suggestion,
        })

    total = len(matched) + len(fuzzy_matched) + len(unmatched)
    return {
        "matched": matched,
        "fuzzy_matched": fuzzy_matched,
        "unmatched": unmatched,
        "total": total,
        "matched_count": len(matched) + len(fuzzy_matched),
    }


def _find_closest_name(search_name, candidates_list, max_results=1):
    """
    Find the closest player name using simple edit-distance scoring.

    Implements a lightweight similarity metric without external libraries:
    - Letter overlap ratio (Dice coefficient)

    Args:
        search_name (str): The name to search for
        candidates_list (list of str): All known player names
        max_results (int): How many candidates to return (default 1)

    Returns:
        str or None: Best matching name, or None if list is empty
    """
    if not candidates_list:
        return None

    search_norm = normalize_player_name(search_name)
    if not search_norm:
        return None

    def _dice_similarity(a, b):
        """Dice coefficient: 2 * |bigrams(a) ∩ bigrams(b)| / (|bigrams(a)| + |bigrams(b)|)"""
        if not a or not b:
            return 0.0
        bigrams_a = {a[i:i+2] for i in range(len(a) - 1)}
        bigrams_b = {b[i:i+2] for i in range(len(b) - 1)}
        intersection = bigrams_a & bigrams_b
        total = len(bigrams_a) + len(bigrams_b)
        return 2.0 * len(intersection) / total if total > 0 else 0.0

    scored = []
    for name in candidates_list:
        norm = normalize_player_name(name)
        score = _dice_similarity(search_norm, norm)
        scored.append((score, name))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored or scored[0][0] < 0.3:
        return None
    return scored[0][1]

# ============================================================
# END SECTION: Player Name Normalization & Fuzzy Matching
# ============================================================


def get_all_player_names(players_list):
    """
    Get a sorted list of all player names.

    Args:
        players_list (list of dict): Loaded player data

    Returns:
        list of str: Sorted player names

    Example:
        names = get_all_player_names(players)
        # → ['Anthony Davis', 'Bam Adebayo', ...]
    """
    # Extract the 'name' field from each player dictionary
    # BEGINNER NOTE: List comprehension = compact way to build a list
    names = [player.get("name", "") for player in players_list if player.get("name")]
    return sorted(names)  # Sort alphabetically


def get_all_team_abbreviations(teams_list):
    """
    Get all 30 NBA team abbreviations.

    Args:
        teams_list (list of dict): Loaded teams data

    Returns:
        list of str: Team abbreviations like ['ATL', 'BOS', ...]
    """
    abbreviations = [
        team.get("abbreviation", "") for team in teams_list
        if team.get("abbreviation")
    ]
    return sorted(abbreviations)


def get_team_by_abbreviation(teams_list, abbreviation):
    """
    Find a team by its abbreviation (e.g., 'LAL', 'BOS').

    Args:
        teams_list (list of dict): Loaded teams data
        abbreviation (str): 3-letter team code

    Returns:
        dict or None: Team data, or None if not found
    """
    for team in teams_list:
        if team.get("abbreviation", "").upper() == abbreviation.upper():
            return team
    return None


def find_players_by_team(players_list, team_abbrev):
    """
    Return all players on a given team.

    Args:
        players_list (list of dict): Loaded player data
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        list of dict: All players on that team, sorted by points avg (desc)
    """
    abbrev_upper = team_abbrev.upper().strip()
    matches = [p for p in players_list if p.get("team", "").upper() == abbrev_upper]
    # Sort by points average descending (stars first)
    try:
        matches.sort(key=lambda p: float(p.get("points_avg", 0) or 0), reverse=True)
    except Exception:
        pass
    return matches


def get_todays_active_players(players_list, todays_games):
    """
    Return only players whose team is playing today.

    Args:
        players_list (list of dict): Loaded player data
        todays_games (list of dict): Tonight's games (from session state)

    Returns:
        list of dict: Players on teams playing today
    """
    if not todays_games:
        return players_list  # Fall back to all players if no games set

    # Build set of teams playing today
    playing_teams = set()
    for game in todays_games:
        playing_teams.add(game.get("home_team", "").upper())
        playing_teams.add(game.get("away_team", "").upper())
    playing_teams.discard("")

    return [p for p in players_list if p.get("team", "").upper() in playing_teams]


def enrich_prop_with_player_data(prop, players_list):
    """
    Add player season averages and team info to a prop dictionary.

    Looks up the player in the players list and adds season stats
    as extra fields on the prop dict for display purposes.

    Args:
        prop (dict): A prop dict with at least 'player_name'
        players_list (list of dict): Loaded player data

    Returns:
        dict: The prop dict with added player stats (non-destructive copy)
    """
    enriched = dict(prop)  # Copy so we don't mutate the original

    player = find_player_by_name(players_list, prop.get("player_name", ""))
    if player:
        enriched["player_team"] = player.get("team", prop.get("team", ""))
        enriched["player_position"] = player.get("position", "")
        enriched["season_pts_avg"] = float(player.get("points_avg", 0) or 0)
        enriched["season_reb_avg"] = float(player.get("rebounds_avg", 0) or 0)
        enriched["season_ast_avg"] = float(player.get("assists_avg", 0) or 0)
        enriched["season_threes_avg"] = float(player.get("threes_avg", 0) or 0)
        enriched["season_minutes_avg"] = float(player.get("minutes_avg", 0) or 0)

        # Calculate how the prop line compares to the season average
        stat_type = prop.get("stat_type", "").lower()
        stat_avg_map = {
            "points": enriched["season_pts_avg"],
            "rebounds": enriched["season_reb_avg"],
            "assists": enriched["season_ast_avg"],
            "threes": enriched["season_threes_avg"],
        }
        season_avg = stat_avg_map.get(stat_type, 0)
        prop_line = float(prop.get("line", 0) or 0)

        if season_avg > 0 and prop_line > 0:
            diff_pct = round((prop_line - season_avg) / season_avg * 100, 1)
            enriched["line_vs_avg_pct"] = diff_pct  # + means line is higher than avg
        else:
            enriched["line_vs_avg_pct"] = 0.0

    return enriched

# ============================================================
# END SECTION: Player Lookup Functions
# ============================================================


# ============================================================
# SECTION: Props Management
# ============================================================

def save_props_to_session(props_list, session_state):
    """
    Save a list of props to Streamlit's session state.

    Streamlit session state persists data between page interactions.
    This lets us keep the prop list as the user navigates pages.

    Args:
        props_list (list of dict): The props to save
        session_state: Streamlit's st.session_state object
    """
    # Store the list under a known key in session state
    session_state["current_props"] = props_list


def load_props_from_session(session_state):
    """
    Load props from Streamlit's session state.

    Returns sample props if no props have been entered yet,
    so the user sees something immediately.

    Args:
        session_state: Streamlit's st.session_state object

    Returns:
        list of dict: Current props (entered or sample)
    """
    # Check if user has entered their own props
    if "current_props" in session_state and session_state["current_props"]:
        return session_state["current_props"]

    # Fall back to sample props from the CSV
    return load_props_data()


def parse_props_from_csv_text(csv_text):
    """
    Parse prop lines from CSV text (uploaded by user).

    Handles files uploaded via Streamlit's file uploader.
    Expected columns: player_name, team, stat_type, line, platform

    Args:
        csv_text (str): Raw CSV text content

    Returns:
        tuple: (list of valid prop dicts, list of error messages)

    Example:
        text = "LeBron James,LAL,points,24.5,PrizePicks"
        props, errors = parse_props_from_csv_text(text)
    """
    parsed_props = []   # Successfully parsed props
    error_messages = []  # Any parsing errors

    # Required columns that must be present
    required_columns = {"player_name", "stat_type", "line", "platform"}

    try:
        # Use csv.DictReader to parse the text
        # io.StringIO lets us treat a string as a file
        import io
        reader = csv.DictReader(io.StringIO(csv_text))

        for row_number, row in enumerate(reader, start=2):  # Start at 2 (row 1 = header)
            # Check that required columns are present
            row_lower = {k.lower().strip(): v.strip() for k, v in row.items()}

            missing_columns = required_columns - set(row_lower.keys())
            if missing_columns:
                error_messages.append(
                    f"Row {row_number}: Missing columns: {missing_columns}"
                )
                continue

            # Validate the line value is a number
            try:
                line_value = float(row_lower["line"])
            except ValueError:
                error_messages.append(
                    f"Row {row_number}: 'line' must be a number, got '{row_lower['line']}'"
                )
                continue

            # Build a clean prop dictionary
            prop = {
                "player_name": row_lower.get("player_name", ""),
                "team": row_lower.get("team", ""),
                "stat_type": row_lower.get("stat_type", "points").lower(),
                "line": line_value,
                "platform": row_lower.get("platform", "PrizePicks"),
                "game_date": row_lower.get("game_date", ""),
            }
            parsed_props.append(prop)

    except Exception as error:
        error_messages.append(f"CSV parsing error: {error}")

    return parsed_props, error_messages


def get_csv_template():
    """
    Return a CSV template string for users to download.

    Returns:
        str: CSV content with headers and one example row
    """
    # Template with headers and one example row
    template_lines = [
        "player_name,team,stat_type,line,platform,game_date",
        "LeBron James,LAL,points,24.5,PrizePicks,2026-03-05",
        "Stephen Curry,GSW,threes,3.5,Underdog,2026-03-05",
    ]
    return "\n".join(template_lines)

# ============================================================
# END SECTION: Props Management
# ============================================================


# ============================================================
# SECTION: Live Data Detection Functions
# Check if live data has been loaded, and when it was last updated.
# ============================================================

def is_using_live_data():
    """
    Check whether the app is currently using live NBA data or sample data.

    Looks for the last_updated.json file created by live_data_fetcher.py.
    If the file exists and has the 'is_live' flag, we're using live data.

    Returns:
        bool: True if live data is loaded, False if using sample data.

    Example:
        if is_using_live_data():
            st.success("Using live data!")
        else:
            st.info("Using sample data.")
    """
    # Check if the timestamp file exists
    if not LAST_UPDATED_JSON_PATH.exists():
        return False  # File doesn't exist = no live data has been fetched

    try:
        # Read the JSON file
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            timestamps = json.load(json_file)  # Parse JSON into dict

        # Check the 'is_live' flag
        # BEGINNER NOTE: .get() returns False if 'is_live' key doesn't exist
        return bool(timestamps.get("is_live", False))

    except Exception:
        return False  # If file is broken, assume sample data


def get_data_last_updated(data_type="players"):
    """
    Get the timestamp when a specific data type was last updated.

    Args:
        data_type (str): Which data to check. One of:
                         'players', 'teams', or 'games'

    Returns:
        str or None: ISO format timestamp string if available, None if never updated.

    Example:
        timestamp = get_data_last_updated("players")
        if timestamp:
            print(f"Players last updated: {timestamp}")
    """
    # Check if the timestamp file exists
    if not LAST_UPDATED_JSON_PATH.exists():
        return None  # Never been updated

    try:
        # Read and parse the JSON file
        with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
            timestamps = json.load(json_file)

        # Return the timestamp for the requested data type
        # Returns None if this data type was never updated
        return timestamps.get(data_type, None)

    except Exception:
        return None  # If any error, return None


def save_last_updated_timestamp(data_type):
    """
    Save the current time as the last-updated timestamp for a data type.

    This is called by live_data_fetcher.py after each successful fetch,
    but can also be called manually if data is updated another way.

    Args:
        data_type (str): Which data was updated, e.g. 'players', 'teams'
    """
    # Load existing timestamps if the file exists
    existing_timestamps = {}  # Start empty

    if LAST_UPDATED_JSON_PATH.exists():
        try:
            with open(LAST_UPDATED_JSON_PATH, "r") as json_file:
                existing_timestamps = json.load(json_file)
        except Exception:
            existing_timestamps = {}  # If broken, start fresh

    # Set the current time as the timestamp for this data type
    existing_timestamps[data_type] = datetime.datetime.now().isoformat()
    existing_timestamps["is_live"] = True  # Mark that live data is loaded

    # Save back to the file
    try:
        with open(LAST_UPDATED_JSON_PATH, "w") as json_file:
            json.dump(existing_timestamps, json_file, indent=2)
    except Exception as error:
        print(f"Warning: Could not save timestamp: {error}")

# ============================================================
# END SECTION: Live Data Detection Functions
# ============================================================
