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
import logging
from pathlib import Path  # Modern file path handling

import streamlit as st


# ============================================================
# SECTION: File Path Constants
# Define paths to all data files relative to the project root.
# Using pathlib.Path makes this work on Windows, Mac, and Linux.
# ============================================================

# Get the directory where this file lives (the 'data' folder)
DATA_DIRECTORY = Path(__file__).parent

# Build full paths to each CSV file
PLAYERS_CSV_PATH = DATA_DIRECTORY / "players.csv"
PROPS_CSV_PATH = DATA_DIRECTORY / "props.csv"
TEAMS_CSV_PATH = DATA_DIRECTORY / "teams.csv"
DEFENSIVE_RATINGS_CSV_PATH = DATA_DIRECTORY / "defensive_ratings.csv"

# Path to the live data timestamp file
# BEGINNER NOTE: This JSON file is created by live_data_fetcher.py
# when real data is downloaded. Its existence tells us if live data is loaded.
LAST_UPDATED_JSON_PATH = DATA_DIRECTORY / "last_updated.json"

# Path to the persisted injury/availability status cache written by
# fetch_todays_players_only() via RosterEngine in live_data_fetcher.py.
INJURY_STATUS_JSON_PATH = DATA_DIRECTORY / "injury_status.json"

# ============================================================
# END SECTION: File Path Constants
# ============================================================


# ============================================================
# SECTION: CSV Loading Functions
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_players_data():
    """
    Load all player data from the players.csv file.

    Returns a list of dictionaries, where each dictionary
    represents one player with all their stats as keys.
    Returns an empty list if the file does not exist yet (first run before
    a live data fetch has been performed).

    Returns:
        list of dict: Player rows, e.g.:
            [{'name': 'LeBron James', 'team': 'LAL', ...}, ...]

    Example:
        players = load_players_data()
        if not players:
            # Prompt user to fetch live data from the Data Feed page
            pass
        else:
            lebron = players[0]
            print(lebron['points_avg'])  # → '24.8'
    """
    return _load_csv_file(PLAYERS_CSV_PATH)


def load_props_data():
    """
    Load all prop lines from the props.csv file.

    Returns an empty list if the file does not exist yet (first run before
    a live data fetch has been performed).

    Returns:
        list of dict: Prop rows, e.g.:
            [{'player_name': 'LeBron James', 'stat_type': 'points',
              'line': '24.5', 'platform': 'PrizePicks', ...}, ...]
    """
    return _load_csv_file(PROPS_CSV_PATH)


@st.cache_data(ttl=300, show_spinner=False)
def load_teams_data():
    """
    Load all 30 NBA teams from teams.csv.

    Returns:
        list of dict: Team rows with pace, ortg, drtg, etc.
    """
    return _load_csv_file(TEAMS_CSV_PATH)


@st.cache_data(ttl=300, show_spinner=False)
def load_defensive_ratings_data():
    """
    Load team defensive ratings by position from defensive_ratings.csv.

    Returns:
        list of dict: Defensive rating rows with vs_PG_pts, etc.
    """
    return _load_csv_file(DEFENSIVE_RATINGS_CSV_PATH)


def load_injury_status():
    """
    Load the persisted player injury/availability status map from disk.

    The status map is written by ``fetch_todays_players_only()`` via
    RosterEngine in ``live_data_fetcher.py`` after each data-update cycle.
    This function provides a fast, no-API-call way for the Analysis and
    Prop Scanner pages to check player availability on startup.

    Returns:
        dict: player_name_lower → {
            "status": str,          # "Active"|"Out"|"GTD"|"Questionable"|"Day-to-Day"|"Injured Reserve"
            "injury_note": str,     # human-readable reason from nba_api signals
            "games_missed": int,
            "return_date": str,     # ISO date or "" (populated by web scraper when available)
            "last_game_date": str,
            "gp_ratio": float,
            # Optional fields added by Layer 5 web scraping:
            "injury": str,          # specific body part/reason, e.g. "Knee – soreness"
            "source": str,          # scraper that provided this entry, e.g. "NBA.com"
            "comment": str,         # additional notes from the official injury report
        }
        Returns an empty dict if the file does not exist or cannot be parsed.
    """
    if not INJURY_STATUS_JSON_PATH.exists():
        return {}
    try:
        with open(INJURY_STATUS_JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:
        print(f"load_injury_status: could not read {INJURY_STATUS_JSON_PATH}: {err}")
        return {}


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
    Check which props have matching players in the database and report
    on injury / availability status per matched player.

    Returns a report showing matched vs unmatched props so the user
    can identify name mismatches before running analysis.  Also counts
    unavailable (Out/Doubtful/Questionable/IR) and GTD players so the
    Roster Health widget in Neural Analysis is accurate.

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
            'unavailable_count': int,  # Out / Doubtful / Questionable / IR
            'gtd_count': int,          # GTD / Day-to-Day
            'unavailable_players': list of str,
            'gtd_players': list of str,
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

    # ── Injury status counts ─────────────────────────────────────────
    injury_map = load_injury_status()
    unavailable_players = []
    gtd_players = []
    if injury_map:
        for name in matched:
            status_info = get_player_status(name, injury_map)
            status = status_info.get("status", "Active")
            if status in ("Out", "Doubtful", "Questionable", "Injured Reserve"):
                unavailable_players.append(name)
            elif status in ("GTD", "Day-to-Day"):
                gtd_players.append(name)

    return {
        "matched": sorted(matched),
        "unmatched": sorted(unmatched),
        "match_count": len(matched),
        "total_count": total,
        "match_rate": round(match_rate, 3),
        "unavailable_count": len(unavailable_players),
        "gtd_count": len(gtd_players),
        "unavailable_players": sorted(unavailable_players),
        "gtd_players": sorted(gtd_players),
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

    # Post-process matched/fuzzy_matched to flag any OUT/injured players.
    # Load injury status once for the whole batch.
    # NOTE: These status sets mirror INACTIVE_INJURY_STATUSES and
    # GTD_INJURY_STATUSES defined in data/live_data_fetcher.py.
    # If those constants change, update these checks accordingly.
    _UNAVAILABLE = frozenset({"Out", "Doubtful", "Questionable", "Injured Reserve"})
    _GTD = frozenset({"GTD", "Day-to-Day"})
    injury_map = load_injury_status()
    if injury_map:
        for item in matched + fuzzy_matched:
            matched_name = item.get("matched_name", "")
            status_info = get_player_status(matched_name, injury_map)
            player_status = status_info.get("status", "Active")
            item["player_status"] = player_status
            if player_status in _UNAVAILABLE:
                note = status_info.get("injury_note", "")
                item["out_warning"] = (
                    f"⛔ {matched_name} is {player_status}"
                    + (f" — {note}" if note else "")
                    + " — remove this prop"
                )
            elif player_status in _GTD:
                note = status_info.get("injury_note", "")
                item["status_warning"] = (
                    f"⚠️ {matched_name} is {player_status}"
                    + (f" — {note}" if note else "")
                )

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
        """Dice coefficient: 2 * |bigrams(a) ∩ bigrams(b)| / (|bigrams(a)| + |bigrams(b)|)

        Handles single-character strings by treating the character itself as the bigram.
        """
        if not a or not b:
            return 0.0
        # Exact match short-circuit
        if a == b:
            return 1.0
        # For very short strings (len 1), use character set overlap
        if len(a) == 1 or len(b) == 1:
            return 1.0 if a[0] == b[0] else 0.0
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
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[DataManager] Unexpected error: {_exc}")
    return matches


def get_todays_active_players(players_list, todays_games):
    """
    Return only players whose team is playing today and who are not
    flagged as injured/inactive by the saved injury status data.

    Args:
        players_list (list of dict): Loaded player data
        todays_games (list of dict): Tonight's games (from session state)

    Returns:
        list of dict: Players on teams playing today who are available
    """
    if not todays_games:
        return players_list  # Fall back to all players if no games set

    # Build set of teams playing today
    playing_teams = set()
    for game in todays_games:
        playing_teams.add(game.get("home_team", "").upper())
        playing_teams.add(game.get("away_team", "").upper())
    playing_teams.discard("")

    # Step 1: filter by team membership
    on_tonight = [p for p in players_list if p.get("team", "").upper() in playing_teams]

    # Step 2: apply injury filtering using saved status (best-effort)
    try:
        from data.roster_engine import EXCLUDE_STATUSES as _EXCL
        injury_map = load_injury_status()
        if injury_map:
            def _is_available(p):
                key = p.get("player_name", "").lower().strip()
                entry = injury_map.get(key, {})
                return entry.get("status", "Active") not in _EXCL
            return [p for p in on_tonight if _is_available(p)]
    except Exception:
        pass  # If injury data is unavailable, return team-filtered list

    return on_tonight


def get_player_status(player_name, status_map):
    """
    Look up a player's injury/availability status from a status map.

    If ``status_map`` is empty or None, the function automatically tries
    to load the persisted status from INJURY_STATUS_JSON_PATH so callers
    don't need to manage the file path themselves.

    Args:
        player_name (str): Player name to look up
        status_map (dict): Map from normalize_player_name -> status_dict
                           (as returned by RosterEngine.get_injury_report() via
                           fetch_todays_players_only).
                           Pass an empty dict or None to auto-load from disk.

    Returns:
        dict: Status dict with keys:
            'status', 'injury_note', 'games_missed', 'return_date',
            'last_game_date', 'gp_ratio'
            — plus optional Layer 5 fields when available:
            'injury' (specific body part/reason),
            'source' (which data source provided the entry),
            'comment' (additional notes from the official injury report).
            Returns default "Active" status if not found.
    """
    _default = {
        "status": "Active",
        "injury_note": "",
        "games_missed": 0,
        "return_date": "",
        "last_game_date": "",
        "gp_ratio": 1.0,
        "injury": "",
        "source": "",
        "comment": "",
    }

    if not player_name:
        return _default

    # Auto-load from disk when no in-memory map is provided
    if not status_map:
        status_map = load_injury_status()

    if not status_map:
        return _default

    # Try exact lowercase match first
    key = player_name.lower().strip()
    if key in status_map:
        entry = dict(_default)
        entry.update(status_map[key])
        return entry

    # Try normalized name match
    normalized = normalize_player_name(player_name)
    if normalized in status_map:
        entry = dict(_default)
        entry.update(status_map[normalized])
        return entry

    # Default to Active if not found
    return _default


def get_status_badge_html(status):
    """
    Return an HTML badge string for a player's injury/availability status.

    Args:
        status (str): Player status string (e.g., 'Active', 'Out', 'GTD', etc.)

    Returns:
        str: HTML span element with colored badge for the status.
    """
    badges = {
        "Active":         '<span style="background:#00ff88;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟢 Active</span>',
        "Probable":       '<span style="background:#00cc66;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟢 Probable</span>',
        "Questionable":   '<span style="background:#ffd700;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟡 Questionable</span>',
        "GTD":            '<span style="background:#ffd700;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟡 GTD</span>',
        "Day-to-Day":     '<span style="background:#ffa500;color:#000;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟡 Day-to-Day</span>',
        "Doubtful":       '<span style="background:#ff6600;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🟠 Doubtful</span>',
        "Out":            '<span style="background:#ff3366;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🔴 Out</span>',
        "Injured Reserve":'<span style="background:#cc0033;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">🔴 IR</span>',
    }
    return badges.get(status, '<span style="background:#8b949e;color:#fff;padding:2px 8px;border-radius:8px;font-size:0.75rem;font-weight:700;">⚪ Unknown</span>')


def get_source_attribution_html(source):
    """
    Return a small HTML badge showing which data source provided an
    injury/availability entry (e.g. "Source: Rotowire").

    Args:
        source (str): Data source identifier, e.g. "RotoWire", "NBA.com",
                      "NBA.com+RotoWire", "espn", "nba_api".

    Returns:
        str: HTML span element with source badge, or empty string if source
             is blank.
    """
    if not source:
        return ""

    source_styles = {
        "rotowire":         ("#e8a900", "#000", "RotoWire"),
        "rotoWire":         ("#e8a900", "#000", "RotoWire"),
        "nba.com":          ("#006bb6", "#fff", "NBA.com"),
        "nba_official":     ("#006bb6", "#fff", "NBA.com"),
        "nba.com+rotowire": ("#006bb6", "#fff", "NBA.com+RotoWire"),
        "espn":             ("#c8102e", "#fff", "ESPN"),
        "espn+rotowire":    ("#c8102e", "#fff", "ESPN+RotoWire"),
        "nba_api":          ("#17408b", "#fff", "nba_api"),
    }

    key = source.lower().strip()
    bg, fg, label = source_styles.get(key, ("#555", "#fff", source))
    return (
        f'<span style="background:{bg};color:{fg};padding:1px 6px;'
        f'border-radius:4px;font-size:0.68rem;font-weight:600;'
        f'vertical-align:middle;">Source: {label}</span>'
    )


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

    Checks keys in priority order:
      1. ``current_props``  — user-entered or platform-filtered props
      2. ``platform_props`` — live-fetched platform props (fallback)
      3. Sample CSV         — last resort (stale / demo data)

    Args:
        session_state: Streamlit's st.session_state object

    Returns:
        list of dict: Current props (entered, platform-fetched, or sample)
    """
    # 1. Check user/filtered props
    if session_state.get("current_props"):
        return session_state["current_props"]

    # 2. Fall back to live-fetched platform props saved by Live Games /
    #    Data Feed pages so Neural Analysis always finds real data.
    if session_state.get("platform_props"):
        return session_state["platform_props"]

    # 3. Last resort — stale sample CSV
    return load_props_data()


def generate_props_for_todays_players(players_data, todays_games, platforms=None):
    """
    Auto-generate prop entries for all active players on tonight's teams.

    For each active player whose team is playing tonight, this function
    creates prop entries for the primary stat types offered by each
    selected platform.  Prop lines are derived from the player's season
    averages and rounded to the nearest 0.5.

    Stat types generated per platform:
        PrizePicks  — points, rebounds, assists, threes, steals, blocks, fantasy_score_pp
        DraftKings  — points, rebounds, assists, threes, fantasy_score_dk
        Underdog    — points, rebounds, assists, threes, steals, blocks, fantasy_score_ud

    Players with < 15 minutes average or with Out/IR/Doubtful status are skipped.

    Args:
        players_data (list[dict]): Loaded player rows from players.csv.
        todays_games (list[dict]): Tonight's games, each with home_team / away_team keys.
        platforms (list[str] | None): Platforms to generate for.  Defaults to all three.

    Returns:
        list[dict]: Auto-generated prop dicts ready for session-state storage.
    """
    if platforms is None:
        platforms = ["PrizePicks", "Underdog", "DraftKings"]

    # ── Build set of tonight's teams (with abbreviation variants) ────
    # NBA CDN, nba_api, and prop platforms sometimes use different three-
    # letter codes for the same franchise (e.g. "GS" vs "GSW").  We store
    # canonical → variant(s) pairs and add all of them to tonight_teams so
    # no player is silently dropped by a formatting mismatch.
    # Each tuple is (canonical, *variants).
    _ABBREV_VARIANT_GROUPS = [
        ("GSW", "GS"),        # Golden State Warriors
        ("NYK", "NY"),        # New York Knicks
        ("NOP", "NO"),        # New Orleans Pelicans
        ("SAS", "SA"),        # San Antonio Spurs
        ("UTA", "UTAH"),      # Utah Jazz
        ("WAS", "WSH"),       # Washington Wizards
        ("BKN", "BRK"),       # Brooklyn Nets
        ("PHX", "PHO"),       # Phoenix Suns
        ("CHA", "CHO"),       # Charlotte Hornets
        # Historical: New Jersey Nets (relocated to Brooklyn 2012); some legacy
        # CSV exports or third-party data sources still use "NJ".
        ("BKN", "NJ"),
    ]
    # Build a flat lookup: any variant → frozenset of all siblings in its group
    _alias_lookup: dict = {}
    for group in _ABBREV_VARIANT_GROUPS:
        siblings = frozenset(group)
        for code in group:
            _alias_lookup[code] = siblings

    tonight_teams: set = set()
    for game in (todays_games or []):
        for key in ("home_team", "away_team"):
            abbrev = game.get(key, "").upper().strip()
            if abbrev:
                tonight_teams.add(abbrev)
                # Add all known variants for this abbreviation
                tonight_teams.update(_alias_lookup.get(abbrev, ()))

    # ── Load persisted injury map (best-effort, no API call) ──
    injury_map = load_injury_status()
    _SKIP_STATUSES = frozenset({
        "Out", "Inactive", "IR", "Injured Reserve", "Doubtful", "Suspended",
        "Not With Team", "G League - Two-Way", "G League - On Assignment", "G League",
    })

    # ── Per-platform stat types to generate ────────────────────
    _PLATFORM_STATS = {
        "PrizePicks": [
            "points", "rebounds", "assists", "threes",
            "steals", "blocks", "fantasy_score_pp",
        ],
        "DraftKings": [
            "points", "rebounds", "assists", "threes",
            "fantasy_score_dk",
        ],
        "Underdog": [
            "points", "rebounds", "assists", "threes",
            "steals", "blocks", "fantasy_score_ud",
        ],
    }

    # ── Simple stat → CSV column name ─────────────────────────
    _STAT_AVG_COL = {
        "points":    "points_avg",
        "rebounds":  "rebounds_avg",
        "assists":   "assists_avg",
        "threes":    "threes_avg",
        "steals":    "steals_avg",
        "blocks":    "blocks_avg",
        "turnovers": "turnovers_avg",
    }

    def _pp_ud_fantasy_score(pts, reb, ast, stl, blk, tov):
        """PrizePicks / Underdog Fantasy scoring formula."""
        return pts + 1.2*reb + 1.5*ast + 3.0*stl + 3.0*blk - tov

    today_str = datetime.date.today().isoformat()
    props = []
    seen = set()  # (player_name, stat_type, platform) dedup

    # ── Star-player safety net ────────────────────────────────────
    # Guarantee that the top 8 players per team (by points avg) are
    # always included with core stats even if their minutes_avg is
    # slightly below the 15-min threshold due to load management or
    # recent rest — prevents star players being silently excluded.
    _CORE_STATS      = ["points", "rebounds", "assists", "threes"]
    _star_names_seen: set = set()
    if tonight_teams and players_data:
        _by_team: dict = {}
        for _p in players_data:
            _t = _p.get("team", "").upper().strip()
            if _t and _t in tonight_teams:
                _by_team.setdefault(_t, []).append(_p)
        for _t, _team_players in _by_team.items():
            # Sort by points_avg descending and take top 8
            _top8 = sorted(
                _team_players,
                key=lambda p: float(p.get("points_avg", 0) or 0),
                reverse=True,
            )[:8]
            for _sp in _top8:
                _sname  = (_sp.get("name") or _sp.get("player_name") or "").strip()
                _sstatus = injury_map.get(_sname.lower(), {}).get("status", "Active")
                if not _sname or _sstatus in _SKIP_STATUSES:
                    continue
                _star_names_seen.add(_sname)
                _spts = float(_sp.get("points_avg", 0) or 0)
                _sreb = float(_sp.get("rebounds_avg", 0) or 0)
                _sast = float(_sp.get("assists_avg", 0) or 0)
                _sthr = float(_sp.get("threes_avg", 0) or 0)
                _core_avgs = {
                    "points": _spts, "rebounds": _sreb,
                    "assists": _sast, "threes": _sthr,
                }
                for _platform in platforms:
                    for _stat in _CORE_STATS:
                        _dkey = (_sname, _stat, _platform)
                        if _dkey in seen:
                            continue
                        _avg = _core_avgs.get(_stat, 0)
                        if _avg < 0.3:
                            continue
                        _line = round(_avg * 2) / 2
                        # Books set points lines slightly below average
                        if _stat == "points":
                            _line = max(0.5, _line - 0.5)
                        if _line <= 0:
                            continue
                        props.append({
                            "player_name": _sname,
                            "team":        _t,
                            "stat_type":   _stat,
                            "line":        _line,
                            "platform":    _platform,
                            "game_date":   today_str,
                            "_synthetic":  True,
                            "line_source": "estimated",
                        })
                        seen.add(_dkey)
    # ── End star-player safety net ────────────────────────────────

    for player in (players_data or []):
        name = (
            player.get("name") or player.get("player_name") or ""
        ).strip()
        team = player.get("team", "").upper().strip()
        if not name:
            continue

        # Filter to tonight's teams (or all players if no games are loaded)
        if tonight_teams and team not in tonight_teams:
            continue

        # Filter out injured / inactive players
        pstatus = injury_map.get(name.lower(), {}).get("status", "Active")
        if pstatus in _SKIP_STATUSES:
            continue

        # Filter out bench / DNP players  (< 15 min average)
        minutes = float(player.get("minutes_avg", 0) or 0)
        if minutes < 15.0:
            continue

        # Pre-fetch averages once per player
        pts = float(player.get("points_avg",    0) or 0)
        reb = float(player.get("rebounds_avg",  0) or 0)
        ast = float(player.get("assists_avg",   0) or 0)
        thr = float(player.get("threes_avg",    0) or 0)
        stl = float(player.get("steals_avg",    0) or 0)
        blk = float(player.get("blocks_avg",    0) or 0)
        tov = float(player.get("turnovers_avg", 0) or 0)

        for platform in platforms:
            stat_types = _PLATFORM_STATS.get(platform, [])
            for stat_type in stat_types:
                dedup_key = (name, stat_type, platform)
                if dedup_key in seen:
                    continue

                # ── Derive prop line from season average ──────
                if stat_type in _STAT_AVG_COL:
                    avg_val = float(player.get(_STAT_AVG_COL[stat_type], 0) or 0)
                    if avg_val < 0.3:
                        continue  # Skip effectively 0 averages
                    prop_line = round(avg_val * 2) / 2  # Round to nearest 0.5
                    # Books set points lines slightly below average
                    if stat_type == "points":
                        prop_line = max(0.5, prop_line - 0.5)
                elif stat_type in ("fantasy_score_pp", "fantasy_score_ud"):
                    avg_val = _pp_ud_fantasy_score(pts, reb, ast, stl, blk, tov)
                    if avg_val < 5.0:
                        continue
                    prop_line = round(avg_val * 2) / 2
                elif stat_type == "fantasy_score_dk":
                    avg_val = (
                        pts + 1.25*reb + 1.5*ast + 2.0*stl + 2.0*blk
                        - 0.5*tov + 0.5*thr
                    )
                    if avg_val < 5.0:
                        continue
                    prop_line = round(avg_val * 2) / 2
                else:
                    continue  # Unknown stat type — skip

                if prop_line <= 0:
                    continue

                props.append({
                    "player_name": name,
                    "team":        team,
                    "stat_type":   stat_type,
                    "line":        prop_line,
                    "platform":    platform,
                    "game_date":   today_str,
                    "_synthetic":  True,
                    "line_source": "estimated",
                })
                seen.add(dedup_key)

    return props


def filter_props_to_platform_players(
    generated_props: list,
    platform_props: list,
) -> list:
    """
    Filter auto-generated props to only include players that appear in
    real platform data (PrizePicks / Underdog / DraftKings).

    Players whose name matches one in platform_props will have their
    generated props returned.  Players not found on any platform are
    dropped entirely — we never want synthetic props for players who
    are not active on a betting app today.

    Args:
        generated_props: List of auto-generated prop dicts (may be synthetic).
        platform_props: List of real platform prop dicts fetched from APIs.

    Returns:
        List of props limited to platform-present players. If platform_props
        is empty or None, returns generated_props unchanged (graceful fallback).
    """
    if not platform_props:
        return generated_props

    import logging as _log
    _logger_filter = _log.getLogger(__name__)

    # Build a set of normalised player names present on any platform
    platform_player_names: set = set()
    for p in platform_props:
        raw_name = (p.get("player_name") or "").strip().lower()
        if raw_name:
            platform_player_names.add(raw_name)

    if not platform_player_names:
        return generated_props

    filtered = []
    dropped_names: set = set()
    for prop in generated_props:
        name = (prop.get("player_name") or "").strip()
        if name.lower() in platform_player_names:
            filtered.append(prop)
        else:
            dropped_names.add(name)

    if dropped_names:
        _logger_filter.info(
            f"[DataManager] Filtered out {len(dropped_names)} players not on any betting platform: "
            + ", ".join(sorted(dropped_names)[:10])
            + (" ..." if len(dropped_names) > 10 else "")
        )

    return filtered


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
# SECTION: Platform Props — Save / Load helpers
# These functions save and load live props fetched from betting
# platforms (PrizePicks, Underdog, DraftKings) to/from both
# session state and an optional CSV file on disk.
# ============================================================

# Path for saving live platform-fetched props (separate from sample_props)
LIVE_PROPS_CSV_PATH = DATA_DIRECTORY / "live_props.csv"

# CSV columns for platform props
_PLATFORM_PROPS_COLUMNS = [
    "player_name", "team", "stat_type", "line", "platform", "game_date", "fetched_at",
]


def save_platform_props_to_session(props_list, session_state):
    """
    Save platform-fetched props to Streamlit session state.

    These are separate from the user-entered "current_props" so that
    platform-fetched data can be used for cross-platform comparison
    without overwriting manually entered props.

    Args:
        props_list (list[dict]): Props from fetch_all_platform_props().
        session_state: Streamlit's st.session_state object.
    """
    session_state["platform_props"] = props_list


def load_platform_props_from_session(session_state):
    """
    Load platform-fetched props from Streamlit session state.

    Args:
        session_state: Streamlit's st.session_state object.

    Returns:
        list[dict]: Previously fetched platform props, or [].
    """
    return session_state.get("platform_props", [])


def save_platform_props_to_csv(props_list, file_path=None):
    """
    Save platform-fetched props to a CSV file on disk.

    Overwrites the existing file each time. This is intentional —
    platform props are always "today's live data", so old data
    should be replaced.

    Args:
        props_list (list[dict]): Props from fetch_all_platform_props().
        file_path (Path, optional): Where to save. Defaults to
            data/live_props.csv.

    Returns:
        bool: True if saved successfully, False on error.
    """
    if file_path is None:
        file_path = LIVE_PROPS_CSV_PATH

    if not props_list:
        return False  # Nothing to save

    try:
        with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=_PLATFORM_PROPS_COLUMNS,
                extrasaction="ignore",  # Ignore extra keys in prop dicts
            )
            writer.writeheader()
            writer.writerows(props_list)
        return True
    except Exception as error:
        print(f"Warning: Could not save platform props to CSV: {error}")
        return False


def load_platform_props_from_csv(file_path=None):
    """
    Load platform-fetched props from a CSV file on disk.

    Args:
        file_path (Path, optional): Where to read from. Defaults to
            data/live_props.csv.

    Returns:
        list[dict]: Props loaded from file, or [] if file not found.
    """
    if file_path is None:
        file_path = LIVE_PROPS_CSV_PATH

    if not Path(file_path).exists():
        return []  # File not yet created

    return _load_csv_file(file_path)

# ============================================================
# END SECTION: Platform Props — Save / Load helpers
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


# ============================================================
# SECTION: Cache Management & Data Health
# ============================================================

def clear_all_caches():
    """
    Clear all st.cache_data caches for data loading functions.

    Call this after a successful data fetch to force fresh reads.
    """
    try:
        load_players_data.clear()
        load_teams_data.clear()
        load_defensive_ratings_data.clear()
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[DataManager] Unexpected error: {_exc}")


def get_data_health_report():
    """
    Return a summary of the current data health status.

    Checks file existence, row counts, and data freshness.

    Returns:
        dict: {
            'players_count': int,
            'teams_count': int,
            'props_count': int,
            'is_live': bool,
            'last_updated': str or None,
            'days_old': int,
            'is_stale': bool,
            'files_present': dict,
            'warnings': list of str,
        }
    """
    warnings = []

    # Check file existence
    files_present = {
        "players.csv": PLAYERS_CSV_PATH.exists(),
        "teams.csv": TEAMS_CSV_PATH.exists(),
        "props.csv": PROPS_CSV_PATH.exists(),
        "defensive_ratings.csv": DEFENSIVE_RATINGS_CSV_PATH.exists(),
        "last_updated.json": LAST_UPDATED_JSON_PATH.exists(),
    }

    for fname, exists in files_present.items():
        if not exists:
            warnings.append(f"Missing file: {fname}")

    # Row counts
    try:
        players = load_players_data()
        players_count = len(players)
    except Exception:
        players_count = 0
        warnings.append("Could not load players.csv")

    try:
        teams = load_teams_data()
        teams_count = len(teams)
    except Exception:
        teams_count = 0
        warnings.append("Could not load teams.csv")

    try:
        props = load_props_data()
        props_count = len(props)
    except Exception:
        props_count = 0

    # Freshness
    is_live = is_using_live_data()
    last_updated = get_data_last_updated("players")

    days_old = 0
    is_stale = True
    if last_updated:
        try:
            ts = datetime.datetime.fromisoformat(last_updated)
            now_local = datetime.datetime.now()
            # Strip tzinfo for comparison if naive
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            age = now_local - ts
            days_old = age.days
            is_stale = days_old > 3
            if is_stale:
                warnings.append(f"Data is {days_old} day(s) old — consider refreshing")
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[DataManager] Unexpected error: {_exc}")

    if players_count == 0:
        warnings.append("No players loaded — run Data Feed to populate")
    if teams_count < 30:
        warnings.append(f"Only {teams_count}/30 teams loaded")

    return {
        "players_count": players_count,
        "teams_count": teams_count,
        "props_count": props_count,
        "is_live": is_live,
        "last_updated": last_updated,
        "days_old": days_old,
        "is_stale": is_stale,
        "files_present": files_present,
        "warnings": warnings,
    }

# ============================================================
# END SECTION: Cache Management & Data Health
# ============================================================
