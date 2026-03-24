# ============================================================
# FILE: tracking/bet_tracker.py
# PURPOSE: High-level interface for logging and reviewing bets.
#          Uses database.py for storage, adds business logic.
# CONNECTS TO: database.py (storage), pages/6_Model_Health.py
# CONCEPTS COVERED: Data validation, aggregation, reporting
# ============================================================

# Standard library imports only
import datetime  # For getting today's date
import time      # For retry delays in resolve_todays_bets
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# Import our database module (sibling file in tracking/)
from tracking.database import (
    insert_bet,
    update_bet_result,
    load_all_bets,
    get_performance_summary,
    initialize_database,
)

# Import shared constants from the engine package
# BEGINNER NOTE: We import from engine/__init__.py so there's
# only ONE place that defines what stat types are valid.
from engine import VALID_STAT_TYPES


# ============================================================
# SECTION: Valid Values for Validation
# ============================================================

# Valid bet directions
VALID_DIRECTIONS = {"OVER", "UNDER"}

# Valid result values
VALID_RESULTS = {"WIN", "LOSS", "PUSH"}

# Valid platforms
VALID_PLATFORMS = {
    "FanDuel", "DraftKings", "BetMGM", "Caesars", "Fanatics",
    "ESPN Bet", "Hard Rock Bet", "BetRivers",
    # Legacy DFS platforms (backward compat)
    "PrizePicks", "Underdog",
}

# Valid tier names
VALID_TIERS = {"Platinum", "Gold", "Silver", "Bronze"}

# Retry configuration for API calls in resolve_todays_bets
RESOLVE_MAX_RETRIES = 3
RESOLVE_RETRY_DELAY = 2  # seconds between retries

# NBA API call configuration
NBA_API_TIMEOUT = 60       # seconds — increased from default 30 to handle slow endpoints
_BACKOFF_BASE = 1.2        # initial delay in seconds between API attempts
_BACKOFF_INCREMENT = 0.8   # additional seconds per retry (1.2s, 2.0s, 2.8s)

# ============================================================
# END SECTION: Valid Values for Validation
# ============================================================


def _get_eastern_tz():
    """Return a US/Eastern timezone object for NBA game-date anchoring.

    NBA defines game dates in Eastern Time. This function prefers
    ``zoneinfo.ZoneInfo`` (DST-aware) and falls back to a fixed UTC-5
    offset when zoneinfo is unavailable.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    time (EDT = UTC-4, roughly March–November). During EDT, dates
    derived from this fallback may be one hour off near the midnight
    boundary. If your server runs in UTC and processes games near
    midnight ET, install ``tzdata`` (``pip install tzdata``) to ensure
    ``zoneinfo`` is available.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except ImportError:
        return datetime.timezone(datetime.timedelta(hours=-5))


def _nba_today_et():
    """Return today's date anchored to US/Eastern time."""
    return datetime.datetime.now(_get_eastern_tz()).date()


# ============================================================
# SECTION: Unified Stat Column Mapping
# Maps ALL known internal stat keys AND platform-native aliases
# to API-NBA game log field names (lowercase).
# ============================================================

# API-NBA game log uses lowercase keys: pts, reb, ast, stl, blk, tov, fg3m, minutes
_STAT_COL = {
    # ── Internal canonical keys ────────────────────────────────
    "points":           "pts",
    "rebounds":         "reb",
    "assists":          "ast",
    "threes":           "fg3m",
    "steals":           "stl",
    "blocks":           "blk",
    "turnovers":        "tov",
    "three_pointers":   "fg3m",
    "minutes":          "minutes",
    # ── Platform name aliases ─────────────────────────────────────
    "pts":              "pts",
    "rebs":             "reb",
    "asts":             "ast",
    "blks":             "blk",
    "stls":             "stl",
    "tovs":             "tov",
    "3-pt made":        "fg3m",
    "3pm":              "fg3m",
    "blocked shots":    "blk",
    "free throws made": "ftm",
    "ftm":              "ftm",
    # ── Platform name aliases ──────────────────────────
    "three pointers":   "fg3m",
    "3-pointers":       "fg3m",
    "three_point":      "fg3m",
    "fg3m":             "fg3m",
    "tov":              "tov",
    "stl":              "stl",
    "blk":              "blk",
    "reb":              "reb",
    "ast":              "ast",
    "min":              "minutes",
}

# Game-segment prop patterns that CANNOT be resolved from PlayerGameLog
# (which only has full-game totals). These are flagged gracefully instead
# of dumped into the generic "unknown stat" error bucket.
_SEGMENT_PROP_PATTERNS = [
    "1st half",
    "2nd half",
    "1st quarter",
    "2nd quarter",
    "3rd quarter",
    "4th quarter",
    "1st 3 minutes",
    "1st 5 minutes",
    "1st 10 minutes",
]


def _is_segment_prop(stat_type: str) -> bool:
    """Return True if stat_type is a game-segment prop that can't be resolved."""
    lower = stat_type.lower()
    return any(pattern in lower for pattern in _SEGMENT_PROP_PATTERNS)

# ============================================================
# END SECTION: Unified Stat Column Mapping
# ============================================================


# ============================================================
# SECTION: Bet Logging
# ============================================================

def log_new_bet(
    player_name,
    stat_type,
    prop_line,
    direction,
    platform,
    confidence_score,
    probability_over,
    edge_percentage,
    tier,
    entry_fee=0.0,
    team="",
    notes="",
    auto_logged=0,
    bet_type="normal",
    std_devs_from_line=0.0,
):
    """
    Log a new bet to track its outcome later.

    Validates input, adds today's date, and saves to database.

    Args:
        player_name (str): Player name (e.g., 'LeBron James')
        stat_type (str): 'points', 'rebounds', etc.
        prop_line (float): The line being bet (e.g., 24.5)
        direction (str): 'OVER' or 'UNDER'
        platform (str): Sportsbook name (e.g., 'FanDuel', 'DraftKings')
        confidence_score (float): 0-100 model confidence
        probability_over (float): Model's P(over), 0-1
        edge_percentage (float): Edge in percentage points
        tier (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'
        entry_fee (float): Dollar amount (default 0)
        team (str): Player's team abbreviation
        notes (str): Optional notes about this pick
        auto_logged (int): 1 if logged automatically by the engine, 0 if manual
        bet_type (str): 'goblin', '50_50', 'demon' (legacy), or 'normal'
        std_devs_from_line (float): How many std devs projection is from line

    Returns:
        tuple: (success: bool, message: str)

    Example:
        success, msg = log_new_bet('LeBron James', 'points',
                                    24.5, 'OVER', 'FanDuel',
                                    72.3, 0.58, 8.0, 'Gold')
    """
    # ============================================================
    # SECTION: Validate Input
    # ============================================================

    errors = []  # Collect validation errors

    # Check player name
    if not player_name or not player_name.strip():
        errors.append("Player name cannot be empty")

    # Check stat type
    if stat_type not in VALID_STAT_TYPES:
        errors.append(f"Invalid stat type '{stat_type}'. Must be one of: {VALID_STAT_TYPES}")

    # Check prop line
    if prop_line <= 0:
        errors.append("Prop line must be greater than 0")

    # Check direction
    if direction not in VALID_DIRECTIONS:
        errors.append(f"Direction must be 'OVER' or 'UNDER'")

    # If any validation errors, return failure
    if errors:
        return False, " | ".join(errors)

    # ============================================================
    # END SECTION: Validate Input
    # ============================================================

    # ============================================================
    # SECTION: Build and Save the Bet
    # ============================================================

    # Get today's date as a string in YYYY-MM-DD format.
    # Anchor to US/Eastern: NBA game dates are defined in ET, so a bet
    # logged at 1 AM UTC for a late West Coast game is still "today" in ET.
    today_date_string = _nba_today_et().isoformat()

    # Build the bet data dictionary
    bet_data = {
        "bet_date": today_date_string,
        "player_name": player_name.strip(),
        "team": team.strip(),
        "stat_type": stat_type.lower(),
        "prop_line": float(prop_line),
        "direction": direction.upper(),
        "platform": platform,
        "confidence_score": float(confidence_score),
        "probability_over": float(probability_over),
        "edge_percentage": float(edge_percentage),
        "tier": tier,
        "entry_fee": float(entry_fee),
        "notes": notes.strip(),
        "auto_logged": int(auto_logged),
        "bet_type": str(bet_type) if bet_type else "normal",
        "std_devs_from_line": float(std_devs_from_line or 0.0),
    }

    # Save to database
    new_bet_id = insert_bet(bet_data)

    if new_bet_id:
        return True, f"Bet logged successfully! Bet ID: {new_bet_id}"
    else:
        return False, "Database error — could not save bet"

    # ============================================================
    # END SECTION: Build and Save the Bet
    # ============================================================


def record_bet_result(bet_id, result, actual_value):
    """
    Record the outcome of a previously logged bet.

    Call this after the game to track model performance.

    Args:
        bet_id (int): The bet's database ID
        result (str): 'WIN', 'LOSS', or 'PUSH'
        actual_value (float): What the player actually scored

    Returns:
        tuple: (success: bool, message: str)

    Example:
        record_bet_result(42, 'WIN', 27.3)
        # LeBron scored 27.3 vs 24.5 line → WIN!
    """
    # Validate the result value
    if result.upper() not in VALID_RESULTS:
        return False, f"Result must be WIN, LOSS, or PUSH (got '{result}')"

    success = update_bet_result(bet_id, result.upper(), float(actual_value))

    if success:
        return True, f"Result recorded: Bet #{bet_id} → {result.upper()}"
    else:
        return False, f"Could not update bet #{bet_id} — not found?"


# ============================================================
# END SECTION: Bet Logging
# ============================================================


# ============================================================
# SECTION: Performance Analytics
# ============================================================

def get_model_performance_stats():
    """
    Get comprehensive model performance statistics.

    Analyzes win rates by tier, platform, and stat type.

    Returns:
        dict: Performance data with multiple breakdowns
    """
    # Get all bets from the database
    all_bets = load_all_bets(limit=500)

    # Overall summary
    overall_summary = get_performance_summary()

    # Break down win rate by tier
    tier_performance = _calculate_win_rate_by_field(all_bets, "tier")

    # Break down win rate by platform
    platform_performance = _calculate_win_rate_by_field(all_bets, "platform")

    # Break down win rate by stat type
    stat_performance = _calculate_win_rate_by_field(all_bets, "stat_type")

    # Break down win rate by direction (OVER vs UNDER)
    direction_performance = _calculate_win_rate_by_field(all_bets, "direction")

    # Break down win rate by Goblin / Demon / Normal bet classification
    bet_type_performance = _calculate_win_rate_by_field(all_bets, "bet_type")

    return {
        "overall": overall_summary,
        "by_tier": tier_performance,
        "by_platform": platform_performance,
        "by_bet_type": bet_type_performance,
        "by_stat_type": stat_performance,
        "by_direction": direction_performance,
        "all_bets": all_bets,
    }


def _calculate_win_rate_by_field(bets_list, field_name):
    """
    Calculate win rate broken down by a specific field.

    For example, win rate per tier (Platinum, Gold, Silver, Bronze).

    Args:
        bets_list (list of dict): All bets from database
        field_name (str): The field to group by (e.g., 'tier')

    Returns:
        dict: {field_value: {'wins': int, 'total': int, 'win_rate': float}}
    """
    performance_by_group = {}  # Will hold stats for each group

    # Only consider bets that have results (skip pending bets)
    bets_with_results = [
        bet for bet in bets_list
        if bet.get("result") and bet["result"] in VALID_RESULTS
    ]

    for bet in bets_with_results:
        field_value = bet.get(field_name, "Unknown")

        # Initialize this group if we haven't seen it
        if field_value not in performance_by_group:
            performance_by_group[field_value] = {"wins": 0, "losses": 0, "total": 0}

        performance_by_group[field_value]["total"] += 1

        if bet["result"] == "WIN":
            performance_by_group[field_value]["wins"] += 1
        elif bet["result"] == "LOSS":
            performance_by_group[field_value]["losses"] += 1

    # Calculate win rates for each group
    for group_data in performance_by_group.values():
        total = group_data["total"]
        if total > 0:
            group_data["win_rate"] = round(group_data["wins"] / total * 100, 1)
        else:
            group_data["win_rate"] = 0.0

    return performance_by_group

# ============================================================
# END SECTION: Performance Analytics
# ============================================================


# ============================================================
# SECTION: Auto-Log Analysis Results
# ============================================================

_MAX_UNCERTAIN_REASONS = 2   # max risk_flags to include in notes for uncertain picks
_MAX_DEMON_REASONS = _MAX_UNCERTAIN_REASONS  # backward-compat alias
_MAX_GOBLIN_REASONS = 1  # max bet_type_reasons to include in notes for Goblin bets

def auto_log_analysis_bets(analysis_results, minimum_edge=5.0, max_bets=15):
    """
    Automatically log bet records for analysis results that have a positive
    edge in the model's recommended direction.

    Call this after Neural Analysis completes to populate the Bet Tracker
    with tonight's picks without any manual entry.

    Deduplication: a bet for the same (player, stat, line, direction, date)
    that was already logged today is skipped so re-running analysis does
    not create duplicate rows.  Only today's bets are loaded for the
    deduplication check to keep the query fast regardless of history size.

    Args:
        analysis_results (list[dict]): Full analysis result list from the
            Neural Analysis engine (as stored in session_state).
        minimum_edge (float): Skip picks whose edge_percentage is below
            this value for Gold/Platinum tiers. Silver picks only require
            ≥3% edge. Bronze picks require ≥8% edge AND ≥60 confidence.
            Defaults to 5.0.  Only picks with edge > 0
            (model favours the recommended direction) are ever logged.
        max_bets (int): Maximum number of new bets to log in a single
            analysis run. Defaults to 15.

    Returns:
        int: Number of new bets logged.
    """
    import sqlite3 as _sqlite3
    import datetime as _dt
    from tracking.database import DB_FILE_PATH as _DB_PATH

    if not analysis_results:
        return 0

    today_str = _dt.date.today().isoformat()

    # Build today-scoped deduplication set using a direct, date-filtered query
    # to avoid loading the entire bet history.
    existing_keys: set = set()
    try:
        with _sqlite3.connect(str(_DB_PATH)) as _conn:
            _rows = _conn.execute(
                "SELECT player_name, stat_type, prop_line, direction FROM bets WHERE bet_date = ?",
                (today_str,),
            ).fetchall()
        existing_keys = {
            (row[0].lower(), row[1], float(row[2] or 0), row[3])
            for row in _rows
        }
    except Exception:
        pass  # If query fails, log without dedup (safe — unique constraint absent)

    logged = 0
    # Silver, Gold, and Platinum tiers qualify for auto-logging.
    # Bronze qualifies only with edge >= 8% AND confidence score >= 60/100.
    AUTO_LOG_TIERS = {"Gold", "Platinum", "Silver", "Bronze"}
    # Silver picks only need 3% edge; Gold/Platinum use the minimum_edge parameter
    SILVER_MIN_EDGE = 5.0
    BRONZE_MIN_EDGE = 8.0
    BRONZE_MIN_CONFIDENCE = 60.0  # out of 100

    # Sort by confidence score descending so the highest-quality picks are logged first
    sorted_results = sorted(
        analysis_results,
        key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )

    for res in sorted_results:
        if logged >= max_bets:
            break
        edge = res.get("edge_percentage", 0)
        tier = res.get("tier", "Bronze")
        confidence = res.get("confidence_score", 0)
        bet_type = res.get("bet_type", "normal")
        # Goblin and Demon bets bypass the minimum edge threshold filter to
        # ensure they are always tracked.  Goblin bets use alt lines set below
        # the standard O/U (higher probability, but may not hit the minimum_edge
        # parameter).  Demon bets use alt lines set above the standard O/U so
        # negative edge is expected and they must bypass the positive-edge check.
        is_special_bet = bet_type in ("goblin", "demon")
        # Only log picks where edge is positive (goblin/demon exempt)
        if edge <= 0 and not is_special_bet:
            continue
        # Only auto-log recognised tiers
        if tier not in AUTO_LOG_TIERS:
            continue
        # Apply tier-specific minimum edge thresholds (goblin/demon bypass all filters)
        if not is_special_bet:
            if tier == "Silver":
                min_required_edge = SILVER_MIN_EDGE
            elif tier == "Bronze":
                # Bronze needs high edge AND high confidence to qualify
                if edge < BRONZE_MIN_EDGE or confidence < BRONZE_MIN_CONFIDENCE:
                    continue
                min_required_edge = BRONZE_MIN_EDGE
            else:
                min_required_edge = minimum_edge
            if edge < min_required_edge:
                continue
        if res.get("player_is_out", False):
            continue

        dedup_key = (
            res.get("player_name", "").lower(),
            res.get("stat_type", ""),
            float(res.get("line", 0) or 0),
            res.get("direction", "OVER"),
        )
        if dedup_key in existing_keys:
            continue

        ok, _msg = log_new_bet(
            player_name=res.get("player_name", ""),
            stat_type=res.get("stat_type", "points"),
            prop_line=float(res.get("line", 0) or 0),
            direction=res.get("direction", "OVER"),
            platform="SmartAI-Auto",
            confidence_score=float(res.get("confidence_score", 0) or 0),
            probability_over=float(res.get("probability_over", 0.5) or 0.5),
            edge_percentage=float(edge),
            tier=res.get("tier", "Bronze"),
            team=res.get("player_team", res.get("team", "")),
            notes=(
                f"Auto-logged by SmartAI. "
                f"SAFE Score: {res.get('confidence_score', 0):.0f}. "
                + (
                    # Goblin / 50_50 / Demon / Normal classification notes
                    "Goblin: " + " | ".join(res.get("bet_type_reasons", [])[:_MAX_GOBLIN_REASONS])
                    if res.get("bet_type") == "goblin" and res.get("bet_type_reasons")
                    else (
                        "50/50 reasons: " + " | ".join(
                            (res.get("risk_flags") or res.get("bet_type_reasons") or [])[:_MAX_UNCERTAIN_REASONS]
                        )
                        if res.get("bet_type") == "50_50" and (res.get("risk_flags") or res.get("bet_type_reasons"))
                        else (
                            "Demon (high ceiling): alt line above standard O/U"
                            if res.get("bet_type") == "demon"
                            else ""
                        )
                    )
                )
            ),
            auto_logged=1,
            bet_type=res.get("bet_type", "normal"),
            std_devs_from_line=float(res.get("std_devs_from_line", 0.0)),
        )
        if ok:
            existing_keys.add(dedup_key)
            logged += 1

    return logged

# ============================================================
# END SECTION: Auto-Log Analysis Results
# ============================================================



def auto_resolve_bet_results(date_str=None):
    """
    For all pending bets on date_str (default: yesterday), fetch actual
    player stats from API-NBA API and automatically mark WIN/LOSS/PUSH.

    Uses data.nba_data_service.get_player_game_log() to get actual stat
    values from API-NBA. Falls back to game_log_cache if the API is
    unavailable. Player IDs are resolved via data.player_profile_service.get_player_id().

    Args:
        date_str (str|None): ISO date string "YYYY-MM-DD".
                             Defaults to yesterday if None.

    Returns:
        tuple: (resolved_count: int, errors_list: list[str])
    """
    import datetime as _dt

    if date_str is None:
        # Anchor to US/Eastern — NBA game dates are defined in ET.
        _today_et = _nba_today_et()
        date_str = (_today_et - _dt.timedelta(days=1)).isoformat()

    resolved_count = 0
    errors_list = []

    # Load all pending bets for the target date
    all_bets = load_all_bets(limit=500)
    pending_bets = [
        b for b in all_bets
        if b.get("bet_date", "") == date_str and not b.get("result")
    ]

    if not pending_bets:
        return 0, [f"No pending bets found for {date_str}"]

    # Import combo/fantasy stat definitions and name normalizer
    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None
    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    # Player ID lookup: API-NBA API → nba_api static list (local, no network)
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    # Target date as a date object (for robust date comparison)
    target_date = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()

    # ── Pre-validate bets and collect unique player names ─────
    _bet_prep = []  # (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, direction, prop_line)
    _names_to_fetch: set = set()

    for bet in pending_bets:
        bet_id      = bet.get("bet_id")
        player_name = bet.get("player_name", "")
        stat_type   = bet.get("stat_type", "").lower()
        prop_line   = float(bet.get("prop_line", 0) or 0)
        direction   = (bet.get("direction") or "OVER").upper()

        # Determine how to compute actual_value for this stat_type
        is_combo   = stat_type in COMBO_STATS
        is_fantasy = stat_type in FANTASY_SCORING
        stat_col   = _STAT_COL.get(stat_type)

        # Fallback: try normalizing the platform-native name to an internal key
        if not stat_col and not is_combo and not is_fantasy and _norm_stat_type is not None:
            normalized = _norm_stat_type(stat_type)
            stat_col = _STAT_COL.get(normalized)
            if stat_col:
                stat_type = normalized

        if not stat_col and not is_combo and not is_fantasy:
            if _is_segment_prop(stat_type):
                errors_list.append(
                    f"#{bet_id} {player_name}: '{stat_type}' is a game-segment prop — "
                    f"cannot resolve from full-game box score"
                )
                continue
            errors_list.append(f"#{bet_id} {player_name}: unknown stat type '{stat_type}'")
            continue

        _names_to_fetch.add(player_name)
        _bet_prep.append((bet, player_name, stat_type, stat_col, is_combo, is_fantasy, direction, prop_line))

    if not _bet_prep:
        return resolved_count, errors_list

    # ── Resolve player names → API-NBA player IDs ────────
    # get_player_id() checks: cache → API-NBA API → nba_api static (local)
    _name_to_pid: dict = {}
    for pname in _names_to_fetch:
        if _lookup_pid is not None:
            pid = _lookup_pid(pname)
            # Also try normalized form (handles unicode/suffix differences)
            if not pid:
                pid = _lookup_pid(_normalize_name(pname))
        else:
            pid = None
        _name_to_pid[pname] = pid

    # ── Fetch game logs in parallel using ThreadPoolExecutor ──
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time

    # Group: player_name → player_id (or None)
    _ids_to_fetch = {
        pid for pid in _name_to_pid.values() if pid
    }
    _game_log_cache: dict = {}  # player_id → list[dict] of API-NBA game log rows

    def _fetch_player_log(pid):
        """Fetch a single player's API-NBA game log with retry + backoff."""
        for _attempt in range(RESOLVE_MAX_RETRIES):
            try:
                if _attempt > 0:
                    _time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                from data.nba_data_service import get_player_game_log as _ldf_gl
                logs = _ldf_gl(pid, last_n_games=5)
                return pid, logs
            except Exception:
                if _attempt == RESOLVE_MAX_RETRIES - 1:
                    return pid, []
        return pid, []

    _unique_ids = list(_ids_to_fetch)
    with ThreadPoolExecutor(max_workers=min(8, len(_unique_ids) or 1)) as executor:
        futures = {executor.submit(_fetch_player_log, pid): pid for pid in _unique_ids}
        for future in as_completed(futures):
            pid = futures[future]
            try:
                _, logs_result = future.result()
                _game_log_cache[pid] = logs_result or []
            except Exception:
                _game_log_cache[pid] = []

    # ── Resolve bets from cached game logs ────────────────────
    for (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, direction, prop_line) in _bet_prep:
        bet_id = bet.get("bet_id")

        try:
            player_id = _name_to_pid.get(player_name)
            if not player_id:
                errors_list.append(f"#{bet_id} {player_name}: player ID not found")
                continue

            logs = _game_log_cache.get(player_id, [])
            if not logs:
                errors_list.append(f"#{bet_id} {player_name}: no game log found")
                continue

            # Find the game on target date (API-NBA returns "YYYY-MM-DD")
            matching_log = None
            for log_row in logs:
                raw_date = log_row.get("game_date", "")
                try:
                    log_date = _dt.datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                    if log_date == target_date:
                        matching_log = log_row
                        break
                except (ValueError, TypeError):
                    continue

            if matching_log is None:
                last_date = logs[0].get("game_date", "N/A") if logs else "N/A"
                errors_list.append(
                    f"#{bet_id} {player_name}: no game found on {date_str} "
                    f"(last game: {last_date})"
                )
                continue

            # Compute actual_value based on stat type
            if is_combo:
                components = COMBO_STATS[stat_type]
                actual_value = sum(
                    float(matching_log.get(_STAT_COL.get(comp, comp), 0) or 0)
                    for comp in components
                    if comp in _STAT_COL
                )
            elif is_fantasy:
                formula = FANTASY_SCORING[stat_type]
                actual_value = sum(
                    weight * float(matching_log.get(_STAT_COL.get(comp, comp), 0) or 0)
                    for comp, weight in formula.items()
                    if comp in _STAT_COL
                )
                actual_value = round(actual_value, 2)
            else:
                actual_value = float(matching_log.get(stat_col, 0) or 0)

            # Determine WIN / LOSS / PUSH
            if actual_value == prop_line:
                result = "PUSH"
            elif direction == "OVER":
                result = "WIN" if actual_value > prop_line else "LOSS"
            else:  # UNDER
                result = "WIN" if actual_value < prop_line else "LOSS"

            success, msg = record_bet_result(bet_id, result, actual_value)
            if success:
                resolved_count += 1
            else:
                errors_list.append(f"#{bet_id} {player_name}: DB update failed — {msg}")

        except Exception as exc:
            errors_list.append(f"#{bet_id} {player_name}: {exc}")

    return resolved_count, errors_list

# ============================================================
# END SECTION: Auto-Resolve
# ============================================================

# Tolerance for declaring a bet result as PUSH (exact tie within float epsilon)
PUSH_THRESHOLD_EPSILON = 0.01


def resolve_todays_bets():
    """
    Resolve today's pending bets by checking live game status via API-NBA API.

    Uses API-NBA get_live_scores() to detect finished games,
    then fetches player game logs via data.nba_data_service.get_player_game_log().
    Player IDs are resolved via data.player_profile_service.get_player_id().
    Only resolves bets where the game has a FINAL status.

    Returns:
        dict: {
            "resolved": int,
            "wins": int,
            "losses": int,
            "pushes": int,
            "pending": int,
            "errors": list[str],
        }
    """
    import datetime as _dt
    from tracking.database import (
        load_all_bets,
        update_bet_result,
        save_daily_snapshot,
    )

    today_str = _dt.date.today().isoformat()
    summary = {"resolved": 0, "wins": 0, "losses": 0, "pushes": 0, "pending": 0, "errors": []}

    try:
        all_bets = load_all_bets(limit=500)
        todays_pending = [
            b for b in all_bets
            if b.get("bet_date") == today_str and not b.get("result")
        ]
    except Exception as exc:
        summary["errors"].append(f"Failed to load bets: {exc}")
        return summary

    if not todays_pending:
        return summary

    # Import combo/fantasy stat definitions
    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    # Normalizer for fuzzy matching
    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return str(n).lower().strip()

    # Player ID lookup via API-NBA → nba_api static list (local)
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    # ── Check API-NBA live scores for finished games ──────
    _scoreboard_available = False
    has_final_games = False
    try:
        from data.nba_api_client import get_live_scores as _cs_live
        live_scores = _cs_live()
        if live_scores:
            _scoreboard_available = True
            has_final_games = any(
                "final" in str(g.get("status", "")).lower()
                for g in live_scores
            )
    except Exception as exc:
        summary["errors"].append(f"API-NBA live scores unavailable: {exc}")

    # Short-circuit: if the scoreboard responded but no games are Final yet,
    # skip the expensive per-player API calls and tell the user clearly.
    if _scoreboard_available and not has_final_games:
        summary["pending"] = len(todays_pending)
        summary["errors"].append(
            "No games are Final yet today — try again after today's games finish."
        )
        return summary

    target_date = _dt.datetime.strptime(today_str, "%Y-%m-%d").date()

    # ── Pre-validate bets and collect unique player names ─────
    _bet_prep = []  # (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, direction, prop_line)
    _names_to_fetch: set = set()

    for bet in todays_pending:
        bet_id      = bet.get("id") or bet.get("bet_id")
        player_name = bet.get("player_name", "")
        stat_type   = str(bet.get("stat_type", "")).lower()
        prop_line   = float(bet.get("prop_line") or 0)
        direction   = str(bet.get("direction") or "OVER").upper()

        is_combo   = stat_type in COMBO_STATS
        is_fantasy = stat_type in FANTASY_SCORING
        stat_col   = _STAT_COL.get(stat_type)

        # Fallback: try normalizing the platform-native name to an internal key
        if not stat_col and not is_combo and not is_fantasy and _norm_stat_type is not None:
            normalized = _norm_stat_type(stat_type)
            stat_col = _STAT_COL.get(normalized)
            if stat_col:
                stat_type = normalized

        if not stat_col and not is_combo and not is_fantasy:
            if _is_segment_prop(stat_type):
                summary["errors"].append(
                    f"#{bet_id} {player_name}: '{stat_type}' is a game-segment prop — "
                    f"cannot resolve from full-game box score"
                )
            else:
                summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
            summary["pending"] += 1
            continue

        _names_to_fetch.add(player_name)
        _bet_prep.append((bet, player_name, stat_type, stat_col, is_combo, is_fantasy, direction, prop_line))

    if not _bet_prep:
        return summary

    # ── Resolve player names → player IDs ────────────────────
    _name_to_pid: dict = {}
    for pname in _names_to_fetch:
        pid = None
        if _lookup_pid is not None:
            pid = _lookup_pid(pname)
            if not pid:
                pid = _lookup_pid(_normalize_name(pname))
        _name_to_pid[pname] = pid

    # ── Fetch game logs in parallel using ThreadPoolExecutor ──
    from concurrent.futures import ThreadPoolExecutor, as_completed

    _ids_to_fetch = {pid for pid in _name_to_pid.values() if pid}
    _game_log_cache: dict = {}  # player_id → list[dict] of API-NBA game log rows

    def _fetch_player_log(pid):
        """Fetch a single player's API-NBA game log with retry + backoff."""
        for _attempt in range(RESOLVE_MAX_RETRIES):
            try:
                if _attempt > 0:
                    time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                from data.nba_data_service import get_player_game_log as _ldf_gl
                logs = _ldf_gl(pid, last_n_games=5)
                return pid, logs
            except Exception as _retry_exc:
                _logger.warning(
                    f"  resolve_todays_bets: attempt {_attempt+1}/{RESOLVE_MAX_RETRIES} "
                    f"failed for player_id={pid}: {_retry_exc}"
                )
                if _attempt == RESOLVE_MAX_RETRIES - 1:
                    return pid, []
        return pid, []

    _unique_ids = list(_ids_to_fetch)
    if _unique_ids:
        with ThreadPoolExecutor(max_workers=min(8, len(_unique_ids))) as executor:
            futures = {executor.submit(_fetch_player_log, pid): pid for pid in _unique_ids}
            for future in as_completed(futures):
                pid = futures[future]
                try:
                    _, log_data = future.result()
                    _game_log_cache[pid] = log_data or []
                except Exception:
                    _game_log_cache[pid] = []

    # ── Resolve bets from cached game logs ────────────────────
    for (bet, player_name, stat_type, stat_col, is_combo, is_fantasy, direction, prop_line) in _bet_prep:
        bet_id = bet.get("id") or bet.get("bet_id")

        try:
            player_id = _name_to_pid.get(player_name)
            if not player_id:
                summary["errors"].append(f"#{bet_id} {player_name}: player ID not found")
                summary["pending"] += 1
                continue

            logs = _game_log_cache.get(player_id, [])
            if not logs:
                summary["pending"] += 1
                continue

            # Find the game log entry for today (API-NBA returns "YYYY-MM-DD")
            latest = None
            for log_row in logs:
                raw_date = log_row.get("game_date", "")
                try:
                    log_date = _dt.datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                    if log_date == target_date:
                        latest = log_row
                        break
                except (ValueError, TypeError):
                    continue

            if latest is None:
                summary["pending"] += 1
                continue

            # ── Compute actual value ─────────────────────────────────
            if is_combo:
                component_keys = COMBO_STATS.get(stat_type, [])
                actual_value = sum(
                    float(latest.get(_STAT_COL.get(k, k), 0) or 0)
                    for k in component_keys
                    if _STAT_COL.get(k)
                )
            elif is_fantasy:
                scoring_weights = FANTASY_SCORING.get(stat_type, {})
                actual_value = sum(
                    float(latest.get(_STAT_COL.get(col, col), 0) or 0) * mult
                    for col, mult in scoring_weights.items()
                    if _STAT_COL.get(col)
                )
            else:
                actual_value = float(latest.get(stat_col, 0) or 0)

            # ── Determine WIN / LOSS / PUSH ──────────────────────────
            if abs(actual_value - prop_line) < PUSH_THRESHOLD_EPSILON:
                result = "PUSH"
            elif direction == "OVER":
                result = "WIN" if actual_value > prop_line else "LOSS"
            else:  # UNDER
                result = "WIN" if actual_value < prop_line else "LOSS"

            update_bet_result(bet_id, result, actual_value)
            summary["resolved"] += 1
            if result == "WIN":
                summary["wins"] += 1
            elif result == "LOSS":
                summary["losses"] += 1
            else:
                summary["pushes"] += 1

        except Exception as exc:
            summary["errors"].append(f"{player_name}: {exc}")
            summary["pending"] += 1

    # Auto-save daily snapshot after resolving
    if summary["resolved"] > 0:
        try:
            save_daily_snapshot(today_str)
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    # Count remaining unresolved bets
    try:
        remaining = load_all_bets(limit=500)
        summary["pending"] = sum(
            1 for b in remaining
            if b.get("bet_date") == today_str and not b.get("result")
        )
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    return summary


def resolve_all_pending_bets():
    """
    Resolve ALL pending bets regardless of date — manual bets, AI picks, any platform.

    Queries every bet with no ``result`` set, groups them by date for efficient
    API calls, and resolves WIN/LOSS/PUSH for each using API-NBA game logs.
    Has rate limiting (1 second between API calls per player).

    Returns:
        dict: {
            "resolved": int,
            "wins": int,
            "losses": int,
            "pushes": int,
            "pending": int,
            "errors": list[str],
            "by_date": dict[str, int],  # resolved count per date
        }
    """
    import datetime as _dt
    import time as _time

    summary = {
        "resolved": 0, "wins": 0, "losses": 0,
        "pushes": 0, "pending": 0, "errors": [], "by_date": {},
    }

    # Try importing required modules
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    # Load all pending bets (no result set) regardless of date
    try:
        all_bets = load_all_bets(limit=2000)
    except Exception as exc:
        summary["errors"].append(f"Failed to load bets: {exc}")
        return summary

    pending_bets = [b for b in all_bets if not b.get("result")]
    if not pending_bets:
        return summary

    # Group by date for efficient caching
    from collections import defaultdict as _defaultdict
    by_date = _defaultdict(list)
    for bet in pending_bets:
        d = bet.get("bet_date") or bet.get("game_date") or ""
        by_date[d].append(bet)

    # Player game log cache: player_id → list[dict]
    _log_cache: dict = {}

    for date_str, bets in sorted(by_date.items()):
        if not date_str:
            summary["pending"] += len(bets)
            continue

        try:
            target_date = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            summary["pending"] += len(bets)
            continue

        date_resolved = 0
        for bet in bets:
            bet_id      = bet.get("bet_id") or bet.get("id")
            player_name = bet.get("player_name", "")
            stat_type   = str(bet.get("stat_type", "")).lower()
            prop_line   = float(bet.get("prop_line") or 0)
            direction   = str(bet.get("direction") or "OVER").upper()

            is_combo   = stat_type in COMBO_STATS
            is_fantasy = stat_type in FANTASY_SCORING
            stat_col   = _STAT_COL.get(stat_type)

            # Fallback: try normalizing the platform-native name to an internal key
            if not stat_col and not is_combo and not is_fantasy and _norm_stat_type is not None:
                normalized = _norm_stat_type(stat_type)
                stat_col = _STAT_COL.get(normalized)
                if stat_col:
                    stat_type = normalized

            if not stat_col and not is_combo and not is_fantasy:
                if _is_segment_prop(stat_type):
                    summary["errors"].append(
                        f"#{bet_id} {player_name}: '{stat_type}' is a game-segment prop — "
                        f"cannot resolve from full-game box score"
                    )
                else:
                    summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
                summary["pending"] += 1
                continue

            # Player ID lookup: API-NBA → nba_api static (local)
            player_id = None
            if _lookup_pid is not None:
                player_id = _lookup_pid(player_name)
                if not player_id:
                    player_id = _lookup_pid(_normalize_name(player_name))
            if not player_id:
                summary["errors"].append(f"#{bet_id} {player_name}: player ID not found")
                summary["pending"] += 1
                continue

            if player_id not in _log_cache:
                _api_exc = None
                for _attempt in range(RESOLVE_MAX_RETRIES):
                    try:
                        if _attempt > 0:
                            _time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                        from data.nba_data_service import get_player_game_log as _ldf_gl
                        logs = _ldf_gl(player_id, last_n_games=10)
                        _log_cache[player_id] = logs or []
                        _api_exc = None
                        break
                    except Exception as exc:
                        _api_exc = exc
                        continue
                if _api_exc is not None:
                    summary["errors"].append(f"#{bet_id} {player_name}: API error — {_api_exc}")
                    summary["pending"] += 1
                    continue

            logs = _log_cache.get(player_id, [])
            if not logs:
                summary["errors"].append(f"#{bet_id} {player_name}: no game log available")
                summary["pending"] += 1
                continue

            # Find the game on target date (API-NBA returns "YYYY-MM-DD")
            matching_log = None
            for log_row in logs:
                raw_date = log_row.get("game_date", "")
                try:
                    log_date = _dt.datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                    if log_date == target_date:
                        matching_log = log_row
                        break
                except (ValueError, TypeError):
                    continue

            if matching_log is None:
                summary["pending"] += 1
                continue

            try:
                if is_combo:
                    actual_value = sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0)
                        for c in COMBO_STATS[stat_type]
                        if _STAT_COL.get(c)
                    )
                elif is_fantasy:
                    actual_value = round(sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0) * w
                        for c, w in FANTASY_SCORING[stat_type].items()
                        if _STAT_COL.get(c)
                    ), 2)
                else:
                    actual_value = float(matching_log.get(stat_col, 0) or 0)

                if abs(actual_value - prop_line) < PUSH_THRESHOLD_EPSILON:
                    result = "PUSH"
                elif direction == "OVER":
                    result = "WIN" if actual_value > prop_line else "LOSS"
                else:
                    result = "WIN" if actual_value < prop_line else "LOSS"

                success, msg = record_bet_result(bet_id, result, actual_value)
                if success:
                    summary["resolved"] += 1
                    date_resolved += 1
                    if result == "WIN":
                        summary["wins"] += 1
                    elif result == "LOSS":
                        summary["losses"] += 1
                    else:
                        summary["pushes"] += 1
                else:
                    summary["errors"].append(f"#{bet_id} {player_name}: DB update failed — {msg}")
                    summary["pending"] += 1
            except Exception as exc:
                summary["errors"].append(f"#{bet_id} {player_name}: {exc}")
                summary["pending"] += 1

        if date_resolved > 0:
            summary["by_date"][date_str] = date_resolved
            try:
                from tracking.database import save_daily_snapshot
                save_daily_snapshot(date_str)
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    return summary


def resolve_all_analysis_picks(date_str=None, include_today=False):
    """
    Resolve pending rows in the ``all_analysis_picks`` table.

    This is the counterpart to ``resolve_all_pending_bets()`` for the
    **All Picks** tab, which displays data from ``all_analysis_picks``
    (not the ``bets`` table).  Without this function the "Resolve All
    Picks" button would never actually update what the user sees.

    Uses the same API-NBA game log approach as
    ``resolve_all_pending_bets()``:
      - Loads every row in ``all_analysis_picks`` where result is NULL
      - Groups by date, fetches game logs per player per season
      - Computes WIN / LOSS / PUSH using prop_line + direction
      - Writes result & actual_value back via
        ``update_analysis_pick_result()``

    Args:
        date_str (str | None): When provided (ISO "YYYY-MM-DD"), only picks
            for that specific date are processed — even if they were already
            resolved (allows re-checking a past night's results).
            When ``None`` (default), all pending picks across all dates are
            resolved.
        include_today (bool): When ``True`` and ``date_str`` is ``None``,
            today's picks are included even if games may not be final yet.
            Defaults to ``False`` (today is skipped on automatic runs).

    Returns:
        dict: {
            "resolved": int,
            "wins": int,
            "losses": int,
            "pushes": int,
            "pending": int,
            "errors": list[str],
            "by_date": dict[str, int],
        }
    """
    import datetime as _dt
    import time as _time

    summary = {
        "resolved": 0, "wins": 0, "losses": 0,
        "pushes": 0, "pending": 0, "errors": [], "by_date": {},
    }

    # ── Import dependencies ────────────────────────────────────────────
    try:
        from data.player_profile_service import get_player_id as _lookup_pid
    except ImportError:
        _lookup_pid = None

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING, normalize_stat_type as _norm_stat_type
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
        _norm_stat_type = None

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    from tracking.database import (
        load_pending_analysis_picks,
        update_analysis_pick_result,
    )

    # ── Load picks from all_analysis_picks ────────────────────────────
    try:
        if date_str:
            from tracking.database import load_analysis_picks_for_date
            pending_picks = load_analysis_picks_for_date(date_str)
        else:
            pending_picks = load_pending_analysis_picks(limit=2000)
    except Exception as exc:
        summary["errors"].append(f"Failed to load pending picks: {exc}")
        return summary

    if not pending_picks:
        return summary

    # ── Group by date ─────────────────────────────────────────────────
    from collections import defaultdict as _defaultdict
    by_date = _defaultdict(list)
    for pick in pending_picks:
        d = pick.get("pick_date") or ""
        by_date[d].append(pick)

    # Player game log cache: player_id → list[dict]
    _log_cache: dict = {}

    for _loop_date, picks in sorted(by_date.items()):
        if not _loop_date:
            summary["pending"] += len(picks)
            continue

        try:
            target_date = _dt.datetime.strptime(_loop_date, "%Y-%m-%d").date()
        except ValueError:
            summary["pending"] += len(picks)
            continue

        # When no specific date was requested, skip today — games may not
        # be final yet.  When the user explicitly asks for a date (even
        # today) we trust them and proceed.  The `include_today` flag
        # allows callers (e.g. an explicit "Resolve All" button) to opt in.
        should_skip_today = date_str is None and not include_today and target_date >= _dt.date.today()
        if should_skip_today:
            summary["pending"] += len(picks)
            continue

        date_resolved = 0
        for pick in picks:
            pick_id     = pick.get("pick_id")
            player_name = pick.get("player_name", "")
            stat_type   = str(pick.get("stat_type", "")).lower()
            prop_line   = float(pick.get("prop_line") or 0)
            direction   = str(pick.get("direction") or "OVER").upper()

            is_combo   = stat_type in COMBO_STATS
            is_fantasy = stat_type in FANTASY_SCORING
            stat_col   = _STAT_COL.get(stat_type)

            # Fallback: try normalizing the platform-native name to an internal key
            if not stat_col and not is_combo and not is_fantasy and _norm_stat_type is not None:
                normalized = _norm_stat_type(stat_type)
                stat_col = _STAT_COL.get(normalized)
                if stat_col:
                    stat_type = normalized

            if not stat_col and not is_combo and not is_fantasy:
                if _is_segment_prop(stat_type):
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: '{stat_type}' is a game-segment prop — "
                        f"cannot resolve from full-game box score"
                    )
                else:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: unknown stat '{stat_type}'"
                    )
                summary["pending"] += 1
                continue

            # ── Player ID lookup: API-NBA → nba_api static (local) ──
            player_id = None
            if _lookup_pid is not None:
                player_id = _lookup_pid(player_name)
                if not player_id:
                    player_id = _lookup_pid(_normalize_name(player_name))
            if not player_id:
                summary["errors"].append(
                    f"#{pick_id} {player_name}: player ID not found"
                )
                summary["pending"] += 1
                continue

            # ── Fetch game log (cached per player) ────────────────────
            if player_id not in _log_cache:
                _api_exc = None
                for _attempt in range(RESOLVE_MAX_RETRIES):
                    try:
                        if _attempt > 0:
                            _time.sleep(_BACKOFF_BASE + _attempt * _BACKOFF_INCREMENT)
                        from data.nba_data_service import get_player_game_log as _ldf_gl
                        logs = _ldf_gl(player_id, last_n_games=10)
                        _log_cache[player_id] = logs or []
                        _api_exc = None
                        break
                    except Exception as exc:
                        _api_exc = exc
                        continue
                if _api_exc is not None:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: API error — {_api_exc}"
                    )
                    summary["pending"] += 1
                    continue

            logs = _log_cache.get(player_id, [])
            if not logs:
                summary["errors"].append(
                    f"#{pick_id} {player_name}: no game log available"
                )
                summary["pending"] += 1
                continue

            # ── Match game by date (API-NBA: "YYYY-MM-DD") ────────
            matching_log = None
            for log_row in logs:
                raw_date = log_row.get("game_date", "")
                try:
                    log_date = _dt.datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
                    if log_date == target_date:
                        matching_log = log_row
                        break
                except (ValueError, TypeError):
                    continue

            if matching_log is None:
                summary["pending"] += 1
                continue

            # ── Compute actual stat value ──────────────────────────────
            try:
                if is_combo:
                    actual_value = sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0)
                        for c in COMBO_STATS[stat_type]
                        if _STAT_COL.get(c)
                    )
                elif is_fantasy:
                    actual_value = round(sum(
                        float(matching_log.get(_STAT_COL.get(c, c), 0) or 0) * w
                        for c, w in FANTASY_SCORING[stat_type].items()
                        if _STAT_COL.get(c)
                    ), 2)
                else:
                    actual_value = float(matching_log.get(stat_col, 0) or 0)

                # ── Determine WIN / LOSS / PUSH ────────────────────────
                if abs(actual_value - prop_line) < PUSH_THRESHOLD_EPSILON:
                    result = "PUSH"
                elif direction == "OVER":
                    result = "WIN" if actual_value > prop_line else "LOSS"
                else:
                    result = "WIN" if actual_value < prop_line else "LOSS"

                # ── Write result to all_analysis_picks ─────────────────
                ok = update_analysis_pick_result(pick_id, result, actual_value)
                if ok:
                    summary["resolved"] += 1
                    date_resolved += 1
                    if result == "WIN":
                        summary["wins"] += 1
                    elif result == "LOSS":
                        summary["losses"] += 1
                    else:
                        summary["pushes"] += 1
                else:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: DB update failed"
                    )
                    summary["pending"] += 1

            except Exception as exc:
                summary["errors"].append(f"#{pick_id} {player_name}: {exc}")
                summary["pending"] += 1

        if date_resolved > 0:
            summary["by_date"][_loop_date] = date_resolved

    return summary


def get_live_bet_status(bets_list):
    """
    Check live box scores for today's pending bets via API-NBA live scores.

    Args:
        bets_list (list[dict]): Today's pending bets from the database.

    Returns:
        list[dict]: Each bet dict augmented with:
            - current_value (float | None)
            - live_status ("🟢 Winning" | "🔴 Losing" | "⏳ In Progress" |
                           "🕐 Not Started" | "✅ Final")
    """
    augmented = []

    # Fetch live box scores from API-NBA
    live_box: dict = {}  # player_name_lower → current stat totals
    try:
        from data.nba_api_client import get_live_scores as _cs_live
        live_scores = _cs_live()
        for g in (live_scores or []):
            status_text = str(g.get("status", "")).lower()
            is_final = "final" in status_text
            is_live  = "in progress" in status_text or "live" in status_text or "q" in status_text

            if not (is_final or is_live):
                continue

            # API-NBA may include player stats in the game object
            for team_key in ("home_players", "away_players", "players"):
                for player in g.get(team_key, []):
                    stats = player.get("statistics", player)
                    pname = str(player.get("name", player.get("player_name", ""))).lower()
                    if not pname:
                        continue
                    live_box[pname] = {
                        "pts": float(stats.get("pts", stats.get("points", 0))),
                        "reb": float(stats.get("reb", stats.get("rebounds", 0))),
                        "ast": float(stats.get("ast", stats.get("assists", 0))),
                        "stl": float(stats.get("stl", stats.get("steals", 0))),
                        "blk": float(stats.get("blk", stats.get("blocks", 0))),
                        "tov": float(stats.get("tov", stats.get("turnovers", 0))),
                        "fg3m": float(stats.get("fg3m", stats.get("threes_made", 0))),
                        "is_final": is_final,
                        "is_live": is_live,
                    }
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[BetTracker] Live box score fetch failed: {_exc}")

    STAT_TO_BOX = {
        "points": "pts",
        "rebounds": "reb",
        "assists": "ast",
        "steals": "stl",
        "blocks": "blk",
        "turnovers": "tov",
        "threes": "fg3m",
        "three_pointers": "fg3m",
    }

    for bet in bets_list:
        bet_copy = dict(bet)
        player_name = bet.get("player_name", "")
        stat_type   = str(bet.get("stat_type") or "").lower()
        prop_line   = float(bet.get("prop_line") or 0)
        direction   = str(bet.get("direction") or "OVER").upper()

        pname_lower = player_name.lower()
        box_entry = live_box.get(pname_lower)

        if box_entry is None:
            bet_copy["current_value"] = None
            bet_copy["live_status"] = "🕐 Not Started"
        else:
            box_key = STAT_TO_BOX.get(stat_type)
            if box_key:
                current_value = box_entry.get(box_key, 0.0)
            elif stat_type == "points_rebounds":
                current_value = box_entry["pts"] + box_entry["reb"]
            elif stat_type == "points_assists":
                current_value = box_entry["pts"] + box_entry["ast"]
            elif stat_type == "rebounds_assists":
                current_value = box_entry["reb"] + box_entry["ast"]
            elif stat_type == "points_rebounds_assists":
                current_value = box_entry["pts"] + box_entry["reb"] + box_entry["ast"]
            else:
                current_value = None

            bet_copy["current_value"] = current_value

            if box_entry.get("is_final"):
                bet_copy["live_status"] = "✅ Final"
            elif box_entry.get("is_live") and current_value is not None:
                if direction == "OVER":
                    bet_copy["live_status"] = "🟢 Winning" if current_value > prop_line else "🔴 Losing"
                else:
                    bet_copy["live_status"] = "🟢 Winning" if current_value < prop_line else "🔴 Losing"
            else:
                bet_copy["live_status"] = "⏳ In Progress"

        augmented.append(bet_copy)

    return augmented


# ============================================================
# SECTION: Auto-Save Top Picks from Neural Analysis
# ============================================================

def save_top_picks_from_analysis(analysis_results):
    """
    Save top picks from Neural Analysis into the bet tracker as AI-logged picks.

    Uses log_new_bet() for schema compliance. Only saves Platinum/Gold picks
    with probability_over >= 0.60.

    Args:
        analysis_results (list of dict): Results from Neural Analysis.

    Returns:
        int: Number of picks successfully saved.
    """
    if not analysis_results:
        return 0

    AUTO_TIERS = {"Platinum", "Gold"}
    MIN_PROBABILITY = 0.60

    import datetime as _dt
    # Anchor to US/Eastern — NBA game dates are defined in ET.
    today_str = _nba_today_et().isoformat()

    existing_bets = load_all_bets(limit=500)
    existing_keys = set()
    for b in existing_bets:
        key = (
            str(b.get("player_name", "")).lower(),
            str(b.get("stat_type", "")).lower(),
            str(b.get("bet_date", ""))[:10],
        )
        existing_keys.add(key)

    saved_count = 0
    for result in analysis_results:
        tier = result.get("tier", "")
        prob = float(result.get("probability_over", 0) or 0)

        if tier not in AUTO_TIERS or prob < MIN_PROBABILITY:
            continue

        player_name = str(result.get("player_name", "")).strip()
        stat_type = str(result.get("stat_type", "")).strip().lower()
        if not player_name or not stat_type:
            continue

        dup_key = (player_name.lower(), stat_type, today_str)
        if dup_key in existing_keys:
            continue

        direction = str(result.get("direction", "OVER")).upper()
        prop_line = float(result.get("line", 0) or 0)
        platform = str(result.get("platform", "FanDuel"))
        edge = float(result.get("edge_percentage", result.get("edge", 0)) or 0)
        confidence = float(result.get("confidence_score", 0) or 0)
        bet_type = str(result.get("bet_type", "normal"))
        std_devs = float(result.get("std_devs_from_line", 0.0))
        team = str(result.get("player_team", result.get("team", "")))

        try:
            ok, _msg = log_new_bet(
                player_name=player_name,
                stat_type=stat_type,
                prop_line=prop_line,
                direction=direction,
                platform=platform,
                confidence_score=confidence,
                probability_over=prob,
                edge_percentage=edge,
                tier=tier,
                entry_fee=0.0,
                team=team,
                notes=f"AI auto-logged | edge={edge:.1f}% | prob={prob:.1%}",
                auto_logged=1,
                bet_type=bet_type,
                std_devs_from_line=std_devs,
            )
            if ok:
                existing_keys.add(dup_key)
                saved_count += 1
        except Exception as _exc:
            logging.getLogger(__name__).warning(
                f"[BetTracker] save_top_picks error for {player_name}: {_exc}"
            )

    return saved_count


# ============================================================
# SECTION: Bulk-Log Platform Props
# ============================================================

def log_props_to_tracker(props_list, direction="OVER"):
    """
    Bulk-log a list of platform props into the bet tracker as PENDING bets.

    Each prop becomes one bet entry with:
      - direction defaulting to OVER (unless the prop dict already has
        a "direction" key, e.g. from DraftKings odds data)
      - confidence_score / probability_over / edge_percentage = 0 / 0.5 / 0.0
        (no model output available — user can update after analysis)
      - tier = "Bronze" (lowest tier since no model output)
      - auto_logged = 1 (flagged as system-added, not manually entered)

    Duplicate detection: skips any prop whose (player_name, stat_type,
    today) triple is already in the ``bets`` table.

    Stat-type normalisation: platform prop stat_type values are already
    normalised to internal keys by ``data.platform_fetcher`` (e.g.
    "3-Point Made" → "threes"). If a value is still unrecognised it is
    skipped and reported in ``errors``.

    Args:
        props_list (list[dict]): Props from ``platform_props`` session
            state or ``data/live_props.csv``. Each dict must have at
            least ``player_name``, ``stat_type``, ``line``, and
            ``platform``.
        direction (str): Default direction ("OVER" or "UNDER") to use
            when the prop dict has no "direction" key. Defaults to
            "OVER".

    Returns:
        tuple[int, int, list[str]]: (saved, skipped, errors)
            saved   — number of props successfully logged
            skipped — number of duplicates skipped
            errors  — list of human-readable error strings
    """
    if not props_list:
        return 0, 0, []

    import datetime as _dt

    today_str = _dt.date.today().isoformat()

    # Load existing bets to detect duplicates
    existing_bets = load_all_bets(limit=2000)
    existing_keys: set = set()
    for b in existing_bets:
        key = (
            str(b.get("player_name", "")).lower(),
            str(b.get("stat_type", "")).lower(),
            str(b.get("bet_date", ""))[:10],
        )
        existing_keys.add(key)

    # Normaliser: convert any un-normalised platform name to internal key
    try:
        from data.platform_mappings import normalize_stat_type as _norm_stat_type
    except ImportError:
        _norm_stat_type = None

    saved = 0
    skipped = 0
    errors: list = []

    for prop in props_list:
        player_name = str(prop.get("player_name", "")).strip()
        if not player_name:
            errors.append("Skipped prop with missing player name")
            continue

        # Normalise stat_type: platform_fetcher already does this, but guard
        # against manually-built or CSV-loaded props that may still be raw.
        stat_type = str(prop.get("stat_type", "")).strip().lower()
        if not stat_type:
            errors.append(f"{player_name}: missing stat_type — skipped")
            continue
        if stat_type not in VALID_STAT_TYPES and _norm_stat_type is not None:
            stat_type = _norm_stat_type(stat_type).lower()
        if stat_type not in VALID_STAT_TYPES:
            errors.append(
                f"{player_name}: unrecognised stat type '{prop.get('stat_type', '')}' — skipped"
            )
            continue

        prop_line = float(prop.get("line", prop.get("prop_line", 0)) or 0)
        if prop_line <= 0:
            errors.append(f"{player_name} ({stat_type}): invalid line {prop_line!r} — skipped")
            continue

        # Duplicate check
        dup_key = (player_name.lower(), stat_type, today_str)
        if dup_key in existing_keys:
            skipped += 1
            continue

        bet_direction = str(prop.get("direction", direction)).upper()
        if bet_direction not in VALID_DIRECTIONS:
            bet_direction = direction.upper()

        platform = str(prop.get("platform", "FanDuel"))
        team = str(prop.get("team", prop.get("player_team", "")))
        game_date = str(prop.get("game_date", today_str))

        try:
            ok, msg = log_new_bet(
                player_name=player_name,
                stat_type=stat_type,
                prop_line=prop_line,
                direction=bet_direction,
                platform=platform,
                confidence_score=0.0,
                probability_over=0.5,
                edge_percentage=0.0,
                tier="Bronze",
                entry_fee=0.0,
                team=team,
                notes=f"Added from platform props | game: {game_date}",
                auto_logged=1,
                bet_type="normal",
                std_devs_from_line=0.0,
            )
            if ok:
                existing_keys.add(dup_key)
                saved += 1
            else:
                errors.append(f"{player_name} ({stat_type}): {msg}")
        except Exception as _exc:
            errors.append(f"{player_name} ({stat_type}): {_exc}")
            logging.getLogger(__name__).warning(
                f"[BetTracker] log_props_to_tracker error for {player_name}: {_exc}"
            )

    return saved, skipped, errors

# ============================================================
# END SECTION: Bulk-Log Platform Props
# ============================================================
