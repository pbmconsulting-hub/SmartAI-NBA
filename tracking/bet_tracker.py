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
    auto_logged=0,
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
# SECTION: Auto-Log Analysis Results
# ============================================================

def auto_log_analysis_bets(analysis_results, minimum_edge=5.0, max_bets=10):
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
            ≥3% edge. Defaults to 5.0.  Only picks with edge > 0
            (model favours the recommended direction) are ever logged.
            Silver, Gold, and Platinum tier picks are auto-logged;
            Bronze picks are skipped regardless of edge.
        max_bets (int): Maximum number of new bets to log in a single
            analysis run. Defaults to 10.

    Returns:
        int: Number of new bets logged.
    """
    import datetime as _dt
    import sqlite3 as _sqlite3
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
    # Silver, Gold, and Platinum tiers qualify for auto-logging; Bronze is too noisy
    AUTO_LOG_TIERS = {"Gold", "Platinum", "Silver"}
    # Silver picks only need 3% edge; Gold/Platinum use the minimum_edge parameter
    SILVER_MIN_EDGE = 3.0

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
        # Only log picks where edge is positive
        if edge <= 0:
            continue
        # Only auto-log Silver-tier and above; skip Bronze
        if tier not in AUTO_LOG_TIERS:
            continue
        # Apply tier-specific minimum edge: Silver needs ≥3%, Gold/Platinum use minimum_edge
        min_required_edge = SILVER_MIN_EDGE if tier == "Silver" else minimum_edge
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
        except Exception:
            pass
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
        except Exception:
            pass
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

        try:
            gl = PlayerGameLog(
                player_id=player_id,
                season=season_str,
                season_type_all_star="Regular Season",
            )
            logs = gl.get_normalized_dict().get("PlayerGameLog", [])
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
        except Exception:
            pass

    # Count remaining unresolved bets
    try:
        remaining = load_all_bets(limit=500)
        summary["pending"] = sum(
            1 for b in remaining
            if b.get("bet_date") == today_str and not b.get("result")
        )
    except Exception:
        pass

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
    except Exception:
        pass

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
            except Exception:
                pass
    except Exception:
        pass

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
