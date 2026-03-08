# ============================================================
# FILE: tracking/bet_tracker.py
# PURPOSE: High-level interface for logging and reviewing bets.
#          Uses database.py for storage, adds business logic.
# CONNECTS TO: database.py (storage), pages/6_Model_Health.py
# CONCEPTS COVERED: Data validation, aggregation, reporting
# ============================================================

# Standard library imports only
import datetime  # For getting today's date

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

    return {
        "overall": overall_summary,
        "by_tier": tier_performance,
        "by_platform": platform_performance,
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
# SECTION: Auto-Resolve
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

    # Build player name → nba_api player_id map (case-insensitive)
    _all_nba_players = nba_players_static.get_players()
    _name_to_id = {
        p["full_name"].lower(): p["id"]
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

    for bet in pending_bets:
        bet_id      = bet.get("bet_id")
        player_name = bet.get("player_name", "")
        stat_type   = bet.get("stat_type", "").lower()
        prop_line   = float(bet.get("prop_line", 0) or 0)
        direction   = (bet.get("direction") or "OVER").upper()

        stat_col = _STAT_COL.get(stat_type)
        if not stat_col:
            errors_list.append(f"#{bet_id} {player_name}: unknown stat type '{stat_type}'")
            continue

        player_id = _name_to_id.get(player_name.lower())
        if not player_id:
            # Try partial match (first + last name)
            parts = player_name.lower().split()
            if len(parts) >= 2:
                player_id = next(
                    (
                        pid
                        for pname, pid in _name_to_id.items()
                        if parts[0] in pname and parts[-1] in pname
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

            # Find the game on target date (GAME_DATE format: "MMM DD, YYYY" or "MMM D, YYYY")
            df["GAME_DATE"] = df["GAME_DATE"].astype(str)
            target_dt = _dt.datetime.strptime(date_str, "%Y-%m-%d")
            # Zero-padded format (e.g. "Mar 08, 2025")
            target_fmt = target_dt.strftime("%b %d, %Y")
            # Non-zero-padded format (e.g. "Mar 8, 2025") — cross-platform approach
            target_fmt_alt = target_fmt.replace(
                f" 0{target_dt.day},", f" {target_dt.day},"
            ) if target_dt.day < 10 else target_fmt

            matching = df[
                df["GAME_DATE"].str.strip() == target_fmt
            ]
            if matching.empty:
                # Try alternative format
                matching = df[
                    df["GAME_DATE"].str.strip() == target_fmt_alt
                ]
            if matching.empty:
                errors_list.append(
                    f"#{bet_id} {player_name}: no game found on {date_str} "
                    f"(last game: {df['GAME_DATE'].iloc[0]})"
                )
                continue

            actual_value = float(matching.iloc[0].get(stat_col, 0) or 0)

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
