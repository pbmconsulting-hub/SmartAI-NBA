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
VALID_PLATFORMS = {"PrizePicks", "Underdog", "DraftKings"}

# Valid tier names
VALID_TIERS = {"Platinum", "Gold", "Silver", "Bronze"}

# Retry configuration for API calls in resolve_todays_bets
RESOLVE_MAX_RETRIES = 3
RESOLVE_RETRY_DELAY = 2  # seconds between retries

# ============================================================
# END SECTION: Valid Values for Validation
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
        platform (str): 'PrizePicks', 'Underdog', or 'DraftKings'
        confidence_score (float): 0-100 model confidence
        probability_over (float): Model's P(over), 0-1
        edge_percentage (float): Edge in percentage points
        tier (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'
        entry_fee (float): Dollar amount (default 0)
        team (str): Player's team abbreviation
        notes (str): Optional notes about this pick
        auto_logged (int): 1 if logged automatically by the engine, 0 if manual
        bet_type (str): 'goblin', 'demon', or 'normal'
        std_devs_from_line (float): How many std devs projection is from line

    Returns:
        tuple: (success: bool, message: str)

    Example:
        success, msg = log_new_bet('LeBron James', 'points',
                                    24.5, 'OVER', 'PrizePicks',
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

    # Get today's date as a string in YYYY-MM-DD format
    today_date_string = datetime.date.today().isoformat()

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

def auto_log_analysis_bets(analysis_results, minimum_edge=5.0, max_bets=25):
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
            analysis run. Defaults to 25.

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
    SILVER_MIN_EDGE = 3.0
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
        # Only log picks where edge is positive
        if edge <= 0:
            continue
        # Only auto-log recognised tiers
        if tier not in AUTO_LOG_TIERS:
            continue
        # Apply tier-specific minimum edge thresholds
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
                f"SAFE Score: {res.get('confidence_score', 0):.0f}"
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
    player stats from nba_api and automatically mark WIN/LOSS/PUSH.

    Uses nba_api.stats.endpoints.PlayerGameLog to get actual stat values.
    Compares actual value vs prop_line + direction → WIN/LOSS/PUSH.

    Args:
        date_str (str|None): ISO date string "YYYY-MM-DD".
                             Defaults to yesterday if None.

    Returns:
        tuple: (resolved_count: int, errors_list: list[str])
    """
    import datetime as _dt

    if date_str is None:
        date_str = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()

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

    # Try to import nba_api
    try:
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players as nba_players_static
        import time as _time
    except ImportError:
        return 0, ["nba_api not available — cannot auto-resolve bets"]

    # Import combo/fantasy stat definitions and name normalizer
    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}
    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    # Build player name → nba_api player_id map (normalized for fuzzy matching)
    _all_nba_players = nba_players_static.get_players()
    _name_to_id = {
        p["full_name"].lower(): p["id"]
        for p in _all_nba_players
    }
    # Also build a normalized-name → id map (handles unicode, suffixes)
    _norm_to_id = {
        _normalize_name(p["full_name"]): p["id"]
        for p in _all_nba_players
    }

    # Stat key mapping: our stat_type labels → PlayerGameLog column names
    _STAT_COL = {
        "points":    "PTS",
        "rebounds":  "REB",
        "assists":   "AST",
        "threes":    "FG3M",
        "steals":    "STL",
        "blocks":    "BLK",
        "turnovers": "TOV",
    }

    # Season string for PlayerGameLog (current season)
    current_year = _dt.date.today().year
    current_month = _dt.date.today().month
    season_year = current_year if current_month >= 10 else current_year - 1
    season_str = f"{season_year}-{str(season_year + 1)[-2:]}"

    # Target date as a date object (for robust date comparison)
    target_date = _dt.datetime.strptime(date_str, "%Y-%m-%d").date()

    # Pre-build month abbreviation map once for efficient date parsing
    import calendar as _cal
    _MONTH_ABBREVS = {m[:3].upper(): i for i, m in enumerate(_cal.month_abbr) if m}

    def _parse_game_date(date_val):
        """Parse a GAME_DATE value from nba_api into a date object.

        nba_api may return dates in several formats:
          - "MAR 05, 2026" or "Mar 05, 2026"  (month-abbrev, zero-padded)
          - "MAR 5, 2026"  or "Mar 5, 2026"   (month-abbrev, non-padded)
          - "2026-03-05"                        (ISO format)
        Returns None if parsing fails.
        """
        s = str(date_val).strip()
        for fmt in ("%b %d, %Y", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        # Handle uppercase month abbreviation with non-zero-padded day
        # e.g. "MAR 5, 2026" — strptime %b is case-sensitive on some platforms
        try:
            parts = s.replace(",", "").split()
            if len(parts) == 3:
                month_num = _MONTH_ABBREVS.get(parts[0].upper()[:3])
                if month_num:
                    return _dt.date(int(parts[2]), month_num, int(parts[1]))
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")
        return None

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

        if not stat_col and not is_combo and not is_fantasy:
            errors_list.append(f"#{bet_id} {player_name}: unknown stat type '{stat_type}'")
            continue

        # --- Player lookup: exact → normalized → partial ---
        player_id = _name_to_id.get(player_name.lower())
        if not player_id:
            # Try normalized match (handles unicode, Jr./III suffixes)
            player_id = _norm_to_id.get(_normalize_name(player_name))
        if not player_id:
            # Try partial match on normalized names (first + last name)
            norm_search = _normalize_name(player_name)
            parts = norm_search.split()
            if len(parts) >= 2:
                player_id = next(
                    (
                        pid
                        for norm_name, pid in _norm_to_id.items()
                        if parts[0] in norm_name and parts[-1] in norm_name
                    ),
                    None,
                )
        if not player_id:
            errors_list.append(f"#{bet_id} {player_name}: player not found in nba_api")
            continue

        try:
            _time.sleep(1.0)  # respect nba_api rate limit
            game_log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season_str,
                season_type_all_star="Regular Season",
            )
            df = game_log.get_data_frames()[0]
            if df.empty:
                errors_list.append(f"#{bet_id} {player_name}: no game log found")
                continue

            # Find the game on target date — parse each GAME_DATE to a date object
            # so we're not sensitive to format differences (MAR vs Mar, padded vs not)
            df["_parsed_date"] = df["GAME_DATE"].apply(_parse_game_date)
            matching = df[df["_parsed_date"] == target_date]
            if matching.empty:
                last_game = df["GAME_DATE"].iloc[0] if not df.empty else "N/A"
                errors_list.append(
                    f"#{bet_id} {player_name}: no game found on {date_str} "
                    f"(last game: {last_game})"
                )
                continue

            row = matching.iloc[0]

            # Compute actual_value based on stat type
            if is_combo:
                # Sum the component columns (e.g. points_rebounds = PTS + REB)
                components = COMBO_STATS[stat_type]
                actual_value = sum(
                    float(row.get(_STAT_COL[comp], 0) or 0)
                    for comp in components
                    if comp in _STAT_COL
                )
            elif is_fantasy:
                # Weighted sum of individual stats using platform formula
                formula = FANTASY_SCORING[stat_type]
                actual_value = sum(
                    weight * float(row.get(_STAT_COL[comp], 0) or 0)
                    for comp, weight in formula.items()
                    if comp in _STAT_COL
                )
                actual_value = round(actual_value, 2)
            else:
                actual_value = float(row.get(stat_col, 0) or 0)

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
    Resolve today's pending bets by checking live game status via nba_api.

    Only resolves bets where the game has a FINAL status.
    Uses comprehensive player matching (exact → normalized → fuzzy) and
    handles combo stats, fantasy scoring, and platform name mismatches —
    ported from ``auto_resolve_bet_results()``.

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

    # Try to use nba_api; bail early if unavailable
    try:
        from nba_api.stats.endpoints import PlayerGameLog
        from nba_api.stats.static import players as nba_players_static
    except ImportError:
        summary["errors"].append("nba_api not available — cannot resolve bets")
        summary["pending"] = len(todays_pending)
        return summary

    # Import combo/fantasy stat definitions
    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}

    # Normalizer for fuzzy matching
    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return str(n).lower().strip()

    # Build name → player_id maps once (exact and normalized)
    _all_nba_players = nba_players_static.get_players()
    _name_to_id = {p["full_name"].lower(): p["id"] for p in _all_nba_players}
    _norm_to_id = {_normalize_name(p["full_name"]): p["id"] for p in _all_nba_players}

    # Try to use nba_api live scoreboard to find final games
    final_game_ids: set = set()
    try:
        from nba_api.live.nba.endpoints.scoreboard import ScoreBoard
        sb = ScoreBoard()
        games_data = sb.get_dict().get("scoreboard", {}).get("games", [])
        for g in games_data:
            status = g.get("gameStatus", 0)
            if status == 3 or str(g.get("gameStatusText", "")).strip().lower() == "final":
                gid = str(g.get("gameId", ""))
                if gid:
                    final_game_ids.add(gid)
    except Exception as exc:
        summary["errors"].append(f"Live scoreboard unavailable: {exc}")

    # Fall back to ScoreboardV2 if live endpoint failed
    if not final_game_ids:
        try:
            from nba_api.stats.endpoints import ScoreboardV2
            sb2 = ScoreboardV2(game_date=today_str)
            for row in sb2.get_normalized_dict().get("GameHeader", []):
                if str(row.get("GAME_STATUS_TEXT", "")).strip().lower() in ("final", "final/ot"):
                    gid = str(row.get("GAME_ID", ""))
                    if gid:
                        final_game_ids.add(gid)
        except Exception as exc2:
            summary["errors"].append(f"ScoreboardV2 unavailable: {exc2}")

    # Current NBA season string (e.g. "2024-25")
    _now = _dt.date.today()
    _year = _now.year
    season_str = (
        f"{_year - 1}-{str(_year)[2:]}"
        if _now.month < 10
        else f"{_year}-{str(_year + 1)[2:]}"
    )

    # Pre-build month abbreviation map once for date parsing
    import calendar as _cal
    _MONTH_ABBREVS = {m[:3].upper(): i for i, m in enumerate(_cal.month_abbr) if m}

    def _parse_game_date(date_val):
        s = str(date_val).strip()
        for fmt in ("%b %d, %Y", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        try:
            parts = s.replace(",", "").split()
            if len(parts) == 3:
                month_num = _MONTH_ABBREVS.get(parts[0].upper()[:3])
                if month_num:
                    return _dt.date(int(parts[2]), month_num, int(parts[1]))
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")
        return None

    # Primary stat column map
    _STAT_COL = {
        "points":    "PTS",
        "rebounds":  "REB",
        "assists":   "AST",
        "threes":    "FG3M",
        "steals":    "STL",
        "blocks":    "BLK",
        "turnovers": "TOV",
        "three_pointers": "FG3M",
        "minutes":   "MIN",
    }

    target_date = _dt.datetime.strptime(today_str, "%Y-%m-%d").date()

    for bet in todays_pending:
        bet_id      = bet.get("id") or bet.get("bet_id")
        player_name = bet.get("player_name", "")
        stat_type   = str(bet.get("stat_type", "")).lower()
        prop_line   = float(bet.get("prop_line") or 0)
        direction   = str(bet.get("direction") or "OVER").upper()

        is_combo   = stat_type in COMBO_STATS
        is_fantasy = stat_type in FANTASY_SCORING
        stat_col   = _STAT_COL.get(stat_type)

        if not stat_col and not is_combo and not is_fantasy:
            summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
            summary["pending"] += 1
            continue

        # ── Comprehensive player lookup: exact → normalized → fuzzy ──
        player_id = _name_to_id.get(player_name.lower())
        if not player_id:
            player_id = _norm_to_id.get(_normalize_name(player_name))
        if not player_id:
            norm_search = _normalize_name(player_name)
            parts = norm_search.split()
            if len(parts) >= 2:
                player_id = next(
                    (
                        pid
                        for norm_name, pid in _norm_to_id.items()
                        if parts[0] in norm_name and parts[-1] in norm_name
                    ),
                    None,
                )
        if not player_id:
            summary["errors"].append(f"#{bet_id} {player_name}: player not found in nba_api")
            summary["pending"] += 1
            continue

        # Retry logic: max RESOLVE_MAX_RETRIES attempts with RESOLVE_RETRY_DELAY delay
        logs = []
        _last_retry_exc = None
        for _attempt in range(RESOLVE_MAX_RETRIES):
            try:
                gl = PlayerGameLog(
                    player_id=player_id,
                    season=season_str,
                    season_type_all_star="Regular Season",
                )
                logs = gl.get_normalized_dict().get("PlayerGameLog", [])
                break  # success
            except Exception as _retry_exc:
                _last_retry_exc = _retry_exc
                _logger.warning(f"  resolve_todays_bets: attempt {_attempt+1}/{RESOLVE_MAX_RETRIES} failed for {player_name}: {_retry_exc}")
                if _attempt < RESOLVE_MAX_RETRIES - 1:
                    time.sleep(RESOLVE_RETRY_DELAY)
                else:
                    raise  # re-raise on final attempt

        try:
            if not logs:
                summary["pending"] += 1
                continue

            # Find the game log entry for today
            latest = None
            for log_row in logs:
                log_date = _parse_game_date(log_row.get("GAME_DATE", ""))
                if log_date == target_date:
                    latest = log_row
                    break

            if latest is None:
                summary["pending"] += 1
                continue

            # ── Compute actual value ─────────────────────────────────
            if is_combo:
                # COMBO_STATS maps stat_type → list of component stat keys
                component_keys = COMBO_STATS.get(stat_type, [])
                actual_value = sum(
                    float(latest.get(_STAT_COL.get(k, k.upper()), 0) or 0)
                    for k in component_keys
                )
            elif is_fantasy:
                # FANTASY_SCORING maps stat_type → {col: multiplier}
                scoring_weights = FANTASY_SCORING.get(stat_type, {})
                actual_value = sum(
                    float(latest.get(_STAT_COL.get(col, col.upper()), 0) or 0) * mult
                    for col, mult in scoring_weights.items()
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
    API calls, and resolves WIN/LOSS/PUSH for each using PlayerGameLog stats.
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
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players as nba_players_static
    except ImportError:
        summary["errors"].append("nba_api not available — cannot resolve bets")
        return summary

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    # Build player lookup maps once
    _all_players = nba_players_static.get_players()
    _name_to_id = {p["full_name"].lower(): p["id"] for p in _all_players}
    _norm_to_id = {_normalize_name(p["full_name"]): p["id"] for p in _all_players}

    _STAT_COL = {
        "points": "PTS", "rebounds": "REB", "assists": "AST",
        "threes": "FG3M", "steals": "STL", "blocks": "BLK",
        "turnovers": "TOV", "three_pointers": "FG3M", "minutes": "MIN",
    }

    import calendar as _cal
    _MONTH_ABBREVS = {m[:3].upper(): i for i, m in enumerate(_cal.month_abbr) if m}

    def _parse_date(date_val):
        s = str(date_val).strip()
        for fmt in ("%b %d, %Y", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        try:
            parts = s.replace(",", "").split()
            if len(parts) == 3:
                month_num = _MONTH_ABBREVS.get(parts[0].upper()[:3])
                if month_num:
                    return _dt.date(int(parts[2]), month_num, int(parts[1]))
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")
        return None

    # Load all pending bets (no result set) regardless of date
    try:
        all_bets = load_all_bets(limit=2000)
    except Exception as exc:
        summary["errors"].append(f"Failed to load bets: {exc}")
        return summary

    pending_bets = [b for b in all_bets if not b.get("result")]
    if not pending_bets:
        return summary

    # Group by date for efficient season-string calculation
    from collections import defaultdict as _defaultdict
    by_date = _defaultdict(list)
    for bet in pending_bets:
        d = bet.get("bet_date") or bet.get("game_date") or ""
        by_date[d].append(bet)

    # Player game log cache: (player_id, season_str) → DataFrame
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

        _year = target_date.year
        season_str = (
            f"{_year - 1}-{str(_year)[2:]}"
            if target_date.month < 10
            else f"{_year}-{str(_year + 1)[2:]}"
        )

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

            if not stat_col and not is_combo and not is_fantasy:
                summary["errors"].append(f"#{bet_id} {player_name}: unknown stat '{stat_type}'")
                summary["pending"] += 1
                continue

            # Player lookup: exact → normalized → fuzzy
            player_id = _name_to_id.get(player_name.lower())
            if not player_id:
                player_id = _norm_to_id.get(_normalize_name(player_name))
            if not player_id:
                parts = _normalize_name(player_name).split()
                if len(parts) >= 2:
                    player_id = next(
                        (pid for nk, pid in _norm_to_id.items()
                         if parts[0] in nk and parts[-1] in nk),
                        None,
                    )
            if not player_id:
                summary["errors"].append(f"#{bet_id} {player_name}: not found in nba_api")
                summary["pending"] += 1
                continue

            cache_key = (player_id, season_str)
            if cache_key not in _log_cache:
                try:
                    _time.sleep(1.0)  # Rate limit: 1 second between API calls
                    gl = playergamelog.PlayerGameLog(
                        player_id=player_id,
                        season=season_str,
                        season_type_all_star="Regular Season",
                    )
                    _log_cache[cache_key] = gl.get_data_frames()[0]
                except Exception as exc:
                    summary["errors"].append(f"#{bet_id} {player_name}: API error — {exc}")
                    summary["pending"] += 1
                    continue

            df = _log_cache[cache_key]
            if df.empty:
                summary["errors"].append(f"#{bet_id} {player_name}: no game log for {season_str}")
                summary["pending"] += 1
                continue

            df["_parsed_date"] = df["GAME_DATE"].apply(_parse_date)
            matching = df[df["_parsed_date"] == target_date]
            if matching.empty:
                summary["pending"] += 1
                continue

            row = matching.iloc[0]
            try:
                if is_combo:
                    actual_value = sum(
                        float(row.get(_STAT_COL.get(c, c.upper()), 0) or 0)
                        for c in COMBO_STATS[stat_type]
                    )
                elif is_fantasy:
                    actual_value = round(sum(
                        float(row.get(_STAT_COL.get(c, c.upper()), 0) or 0) * w
                        for c, w in FANTASY_SCORING[stat_type].items()
                    ), 2)
                else:
                    actual_value = float(row.get(stat_col, 0) or 0)

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


def resolve_all_analysis_picks(date_str=None):
    """
    Resolve pending rows in the ``all_analysis_picks`` table.

    This is the counterpart to ``resolve_all_pending_bets()`` for the
    **All Picks** tab, which displays data from ``all_analysis_picks``
    (not the ``bets`` table).  Without this function the "Resolve All
    Picks" button would never actually update what the user sees.

    Uses the same NBA API + PlayerGameLog approach as
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
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players as nba_players_static
    except ImportError:
        summary["errors"].append("nba_api not available — cannot resolve picks")
        return summary

    try:
        from data.platform_mappings import COMBO_STATS, FANTASY_SCORING
    except ImportError:
        COMBO_STATS = {}
        FANTASY_SCORING = {}

    try:
        from data.data_manager import normalize_player_name as _normalize_name
    except ImportError:
        def _normalize_name(n):
            return n.lower().strip()

    from tracking.database import (
        load_pending_analysis_picks,
        update_analysis_pick_result,
    )

    # ── Build player lookup maps (once) ───────────────────────────────
    _all_players = nba_players_static.get_players()
    _name_to_id  = {p["full_name"].lower(): p["id"] for p in _all_players}
    _norm_to_id  = {_normalize_name(p["full_name"]): p["id"] for p in _all_players}

    _STAT_COL = {
        "points": "PTS", "rebounds": "REB", "assists": "AST",
        "threes": "FG3M", "steals": "STL", "blocks": "BLK",
        "turnovers": "TOV", "three_pointers": "FG3M", "minutes": "MIN",
    }

    import calendar as _cal
    _MONTH_ABBREVS = {m[:3].upper(): i for i, m in enumerate(_cal.month_abbr) if m}

    def _parse_date(date_val):
        s = str(date_val).strip()
        for fmt in ("%b %d, %Y", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        try:
            parts = s.replace(",", "").split()
            if len(parts) == 3:
                month_num = _MONTH_ABBREVS.get(parts[0].upper()[:3])
                if month_num:
                    return _dt.date(int(parts[2]), month_num, int(parts[1]))
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")
        return None

    # ── Load picks from all_analysis_picks ────────────────────────────
    # When a specific date is requested we load ALL picks for that date
    # (including already-resolved ones) so the user can re-verify them.
    # When no date is given we only load pending picks to avoid redundant work.
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

    # ── Group by date for efficient season-string reuse ───────────────
    from collections import defaultdict as _defaultdict
    by_date = _defaultdict(list)
    for pick in pending_picks:
        d = pick.get("pick_date") or ""
        by_date[d].append(pick)

    # Player game log cache: (player_id, season_str) → DataFrame
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
        # today) we trust them and proceed.
        if date_str is None and target_date >= _dt.date.today():
            summary["pending"] += len(picks)
            continue

        _year = target_date.year
        season_str = (
            f"{_year - 1}-{str(_year)[2:]}"
            if target_date.month < 10
            else f"{_year}-{str(_year + 1)[2:]}"
        )

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

            if not stat_col and not is_combo and not is_fantasy:
                summary["errors"].append(
                    f"#{pick_id} {player_name}: unknown stat '{stat_type}'"
                )
                summary["pending"] += 1
                continue

            # ── Player lookup: exact → normalized → partial ────────────
            player_id = _name_to_id.get(player_name.lower())
            if not player_id:
                player_id = _norm_to_id.get(_normalize_name(player_name))
            if not player_id:
                parts = _normalize_name(player_name).split()
                if len(parts) >= 2:
                    player_id = next(
                        (pid for nk, pid in _norm_to_id.items()
                         if parts[0] in nk and parts[-1] in nk),
                        None,
                    )
            if not player_id:
                summary["errors"].append(
                    f"#{pick_id} {player_name}: not found in nba_api"
                )
                summary["pending"] += 1
                continue

            # ── Fetch game log (cached per player+season) ─────────────
            cache_key = (player_id, season_str)
            if cache_key not in _log_cache:
                try:
                    _time.sleep(1.0)  # respect nba_api rate limit
                    gl = playergamelog.PlayerGameLog(
                        player_id=player_id,
                        season=season_str,
                        season_type_all_star="Regular Season",
                    )
                    _log_cache[cache_key] = gl.get_data_frames()[0]
                except Exception as exc:
                    summary["errors"].append(
                        f"#{pick_id} {player_name}: API error — {exc}"
                    )
                    summary["pending"] += 1
                    continue

            df = _log_cache[cache_key]
            if df.empty:
                summary["errors"].append(
                    f"#{pick_id} {player_name}: no game log for {season_str}"
                )
                summary["pending"] += 1
                continue

            # ── Match game by date ─────────────────────────────────────
            df["_parsed_date"] = df["GAME_DATE"].apply(_parse_date)
            matching = df[df["_parsed_date"] == target_date]
            if matching.empty:
                summary["pending"] += 1
                continue

            row = matching.iloc[0]

            # ── Compute actual stat value ──────────────────────────────
            try:
                if is_combo:
                    actual_value = sum(
                        float(row.get(_STAT_COL.get(c, c.upper()), 0) or 0)
                        for c in COMBO_STATS[stat_type]
                    )
                elif is_fantasy:
                    actual_value = round(sum(
                        float(row.get(_STAT_COL.get(c, c.upper()), 0) or 0) * w
                        for c, w in FANTASY_SCORING[stat_type].items()
                    ), 2)
                else:
                    actual_value = float(row.get(stat_col, 0) or 0)

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
    Check live box scores for today's pending bets.

    Args:
        bets_list (list[dict]): Today's pending bets from the database.

    Returns:
        list[dict]: Each bet dict augmented with:
            - current_value (float | None)
            - live_status ("🟢 Winning" | "🔴 Losing" | "⏳ In Progress" |
                           "🕐 Not Started" | "✅ Final")
    """
    augmented = []

    # Build player_id cache
    player_id_cache: dict = {}
    try:
        from nba_api.stats.static import players as nba_players_static
        _static_players = nba_players_static.get_active_players()
        for p in _static_players:
            player_id_cache[p["full_name"].lower()] = p["id"]
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    # Fetch live box scores
    live_box: dict = {}  # player_name_lower → current stat totals
    try:
        from nba_api.live.nba.endpoints.scoreboard import ScoreBoard
        sb = ScoreBoard()
        games = sb.get_dict().get("scoreboard", {}).get("games", [])
        for g in games:
            game_status = g.get("gameStatus", 1)
            status_text = str(g.get("gameStatusText", "")).strip()
            is_final = game_status == 3 or status_text.lower() == "final"
            is_live = game_status == 2

            if not (is_final or is_live):
                continue

            gid = g.get("gameId", "")
            try:
                from nba_api.live.nba.endpoints.boxscore import BoxScore
                bs = BoxScore(game_id=gid)
                bs_data = bs.get_dict().get("game", {})
                for team_side in ("homeTeam", "awayTeam"):
                    team_data = bs_data.get(team_side, {})
                    for player in team_data.get("players", []):
                        stats = player.get("statistics", {})
                        pname = player.get("name", "").lower()
                        live_box[pname] = {
                            "pts": float(stats.get("points", 0)),
                            "reb": float(stats.get("reboundsTotal", 0)),
                            "ast": float(stats.get("assists", 0)),
                            "stl": float(stats.get("steals", 0)),
                            "blk": float(stats.get("blocks", 0)),
                            "tov": float(stats.get("turnovers", 0)),
                            "fg3m": float(stats.get("threePointersMade", 0)),
                            "min": str(stats.get("minutesCalculated", "PT0M")),
                            "is_final": is_final,
                            "is_live": is_live,
                        }
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

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

    Iterates analysis_results and inserts picks that meet the minimum quality bar
    (tier is Platinum/Gold, probability_over >= 0.60) as PENDING bets with
    source='AI_AUTO'. Duplicate picks (same player + stat + date) are skipped.

    BEGINNER NOTE: This is how the AI Picks tab in the Bet Tracker gets populated.
    The Neural Analysis page runs models and produces results; this function
    automatically saves the best ones so you can track model performance over time.

    Args:
        analysis_results (list of dict): Results from Neural Analysis. Each dict
            should have keys: player_name, stat_type, line, direction, tier,
            probability_over, platform (optional), edge (optional).

    Returns:
        int: Number of picks successfully saved.
    """
    if not analysis_results:
        return 0

    AUTO_TIERS = {"Platinum", "Gold"}
    MIN_PROBABILITY = 0.60

    import datetime as _dt
    today_str = _dt.datetime.now().strftime("%Y-%m-%d")

    # Load existing bets to avoid duplicates
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

        if tier not in AUTO_TIERS:
            continue
        if prob < MIN_PROBABILITY:
            continue

        player_name = str(result.get("player_name", "")).strip()
        stat_type = str(result.get("stat_type", "")).strip().lower()
        if not player_name or not stat_type:
            continue

        # Check for duplicate
        dup_key = (player_name.lower(), stat_type, today_str)
        if dup_key in existing_keys:
            continue

        direction = str(result.get("direction", "OVER")).upper()
        line = float(result.get("line", 0) or 0)
        platform = str(result.get("platform", "PrizePicks"))
        edge = float(result.get("edge", 0) or 0)
        notes = f"AI auto-logged | edge={edge:.1f}% | prob={prob:.1%}"

        try:
            insert_bet({
                "player_name": player_name,
                "stat_type": stat_type,
                "line": line,
                "direction": direction,
                "tier": tier,
                "platform": platform,
                "result": "PENDING",
                "notes": notes,
                "source": "AI_AUTO",
                "probability": prob,
            })
            existing_keys.add(dup_key)
            saved_count += 1
        except Exception as _exc:
            logging.getLogger(__name__).warning(f"[BetTracker] Unexpected error: {_exc}")

    return saved_count
