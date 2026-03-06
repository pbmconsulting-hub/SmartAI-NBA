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
