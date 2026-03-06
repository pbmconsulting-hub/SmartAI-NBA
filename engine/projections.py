# ============================================================
# FILE: engine/projections.py
# PURPOSE: Build stat projections for players given tonight's
#          game context (opponent, pace, home/away, rest).
#          Takes raw player averages and adjusts them for
#          the specific matchup.
# CONNECTS TO: data_manager.py (gets player data),
#              simulation.py (gets the adjusted projections)
# CONCEPTS COVERED: Matchup adjustments, pace adjustments,
#                   per-game rate calculations
# ============================================================

# Standard library only
import math  # For rounding and calculation helpers


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# League average game total (combined score of both teams).
# ~220 points per game as of the 2025-26 NBA season.
# Update this each season as pace/scoring trends shift.
LEAGUE_AVERAGE_GAME_TOTAL = 220.0

# League average possessions per game (pace baseline).
# Used to compute pace adjustment factors.
LEAGUE_AVERAGE_PACE = 98.5

def build_player_projection(
    player_data,
    opponent_team_abbreviation,
    is_home_game,
    rest_days,
    game_total,
    defensive_ratings_data,
    teams_data,
):
    """
    Build a complete stat projection for one player tonight.

    Adjusts their season averages based on:
    - Opponent defensive rating vs their position
    - Game pace (faster game = more possessions = more stats)
    - Home court advantage
    - Rest days (back-to-back fatigue)
    - Vegas total (high total = projected to be high-scoring game)

    Args:
        player_data (dict): Player row from sample_players.csv
            Keys: name, team, position, points_avg, etc.
        opponent_team_abbreviation (str): e.g., "GSW", "BOS"
        is_home_game (bool): True if playing at home tonight
        rest_days (int): Days of rest since last game (0=back-to-back)
        game_total (float): Vegas over/under total for tonight's game
        defensive_ratings_data (list of dict): From defensive_ratings.csv
        teams_data (list of dict): From teams.csv

    Returns:
        dict: Projected stats for tonight with adjustment factors:
            - 'projected_points': float
            - 'projected_rebounds': float
            - 'projected_assists': float
            - 'projected_threes': float
            - 'projected_steals': float
            - 'projected_blocks': float
            - 'projected_turnovers': float
            - 'pace_factor': float (multiplier, ~0.9-1.1)
            - 'defense_factor': float (multiplier, ~0.88-1.12)
            - 'home_away_factor': float (small +/-)
            - 'rest_factor': float (multiplier, ~0.9-1.0)
            - 'blowout_risk': float (0.0-1.0)
            - 'overall_adjustment': float (combined multiplier)

    Example:
        LeBron at home vs weak defense + fast pace →
        projected_points might be 27.1 instead of his 24.8 average
    """
    # ============================================================
    # SECTION: Extract Player's Season Averages
    # ============================================================

    # Get each stat average from the player data dictionary
    season_points_average = float(player_data.get("points_avg", 0))
    season_rebounds_average = float(player_data.get("rebounds_avg", 0))
    season_assists_average = float(player_data.get("assists_avg", 0))
    season_threes_average = float(player_data.get("threes_avg", 0))
    season_steals_average = float(player_data.get("steals_avg", 0))
    season_blocks_average = float(player_data.get("blocks_avg", 0))
    season_turnovers_average = float(player_data.get("turnovers_avg", 0))
    player_position = player_data.get("position", "SF")  # Default to SF if missing

    # ============================================================
    # END SECTION: Extract Player's Season Averages
    # ============================================================

    # ============================================================
    # SECTION: Calculate Adjustment Factors
    # ============================================================

    # --- Factor 1: Opponent Defensive Rating ---
    # How well does the opponent defend this player's position?
    defense_factor = _get_defense_adjustment_factor(
        opponent_team_abbreviation,
        player_position,
        defensive_ratings_data,
    )

    # --- Factor 2: Game Pace ---
    # Faster game = more possessions = more stat opportunities
    pace_factor = _get_pace_adjustment_factor(
        opponent_team_abbreviation,
        player_data.get("team", ""),
        teams_data,
    )

    # --- Factor 3: Home Court Advantage ---
    # Home teams historically shoot better and have more energy
    if is_home_game:
        home_away_factor = 0.025   # +2.5% boost for playing at home
    else:
        home_away_factor = -0.015  # -1.5% penalty for away games

    # --- Factor 4: Rest Adjustment ---
    # Back-to-back games cause fatigue; well-rested players perform better
    rest_factor = _get_rest_adjustment_factor(rest_days)

    # --- Factor 5: Game Total / Scoring Environment ---
    # High-total games (230+ pts projected) are fast-paced, high scoring
    # Neutral total is LEAGUE_AVERAGE_GAME_TOTAL; adjust proportionally
    if game_total > 0:
        # BEGINNER NOTE: This creates a small boost/penalty based on
        # how far the total is from average. Capped at ±5%
        game_total_factor = 1.0 + ((game_total - LEAGUE_AVERAGE_GAME_TOTAL) / LEAGUE_AVERAGE_GAME_TOTAL) * 0.5
        game_total_factor = max(0.95, min(1.05, game_total_factor))  # Cap at ±5%
    else:
        game_total_factor = 1.0  # Neutral if no total provided

    # --- Factor 6: Blowout Risk ---
    # Estimate blowout risk based on opponent quality
    blowout_risk = _estimate_blowout_risk(
        opponent_team_abbreviation, teams_data
    )

    # ============================================================
    # END SECTION: Calculate Adjustment Factors
    # ============================================================

    # ============================================================
    # SECTION: Apply Adjustments to Get Tonight's Projections
    # ============================================================

    # Combine all factors into one multiplier for offensive stats
    offensive_stat_multiplier = (
        defense_factor
        * pace_factor
        * game_total_factor
        * (1.0 + home_away_factor)
        * rest_factor
    )

    # Project each stat by applying the combined multiplier
    projected_points = season_points_average * offensive_stat_multiplier
    projected_rebounds = season_rebounds_average * (
        pace_factor * defense_factor * (1.0 + home_away_factor) * rest_factor
    )
    projected_assists = season_assists_average * offensive_stat_multiplier
    projected_threes = season_threes_average * offensive_stat_multiplier
    projected_steals = season_steals_average * rest_factor * (1.0 + home_away_factor * 0.5)
    projected_blocks = season_blocks_average * rest_factor * (1.0 + home_away_factor * 0.5)
    projected_turnovers = season_turnovers_average * pace_factor  # Turnovers up with pace

    # Round to 1 decimal place for readability
    projections = {
        "projected_points": round(projected_points, 1),
        "projected_rebounds": round(projected_rebounds, 1),
        "projected_assists": round(projected_assists, 1),
        "projected_threes": round(projected_threes, 1),
        "projected_steals": round(projected_steals, 1),
        "projected_blocks": round(projected_blocks, 1),
        "projected_turnovers": round(projected_turnovers, 1),
        # Store all factors for transparency (shown in app)
        "pace_factor": round(pace_factor, 4),
        "defense_factor": round(defense_factor, 4),
        "home_away_factor": round(home_away_factor, 4),
        "rest_factor": round(rest_factor, 4),
        "game_total_factor": round(game_total_factor, 4),
        "blowout_risk": round(blowout_risk, 4),
        "overall_adjustment": round(offensive_stat_multiplier, 4),
    }

    return projections

    # ============================================================
    # END SECTION: Apply Adjustments to Get Tonight's Projections
    # ============================================================


# ============================================================
# SECTION: Individual Adjustment Factor Functions
# ============================================================

def _get_defense_adjustment_factor(
    opponent_team_abbreviation,
    player_position,
    defensive_ratings_data,
):
    """
    Look up how well the opponent defends this player's position.

    A factor of 1.1 means the opponent allows 10% more points
    to this position (weak defense = good for the player).
    A factor of 0.9 means the opponent is 10% tougher than average.

    Args:
        opponent_team_abbreviation (str): 3-letter team code
        player_position (str): PG, SG, SF, PF, or C
        defensive_ratings_data (list of dict): Defensive rating rows

    Returns:
        float: Adjustment multiplier (typically 0.88 to 1.12)
    """
    # Find the opponent's row in defensive ratings data
    for team_row in defensive_ratings_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            # Build the column name: "vs_PG_pts", "vs_C_pts", etc.
            column_name = f"vs_{player_position}_pts"
            factor_value = team_row.get(column_name, "1.0")
            return float(factor_value)

    # If opponent not found, return 1.0 (neutral)
    return 1.0


def _get_pace_adjustment_factor(
    opponent_team_abbreviation,
    player_team_abbreviation,
    teams_data,
):
    """
    Calculate the pace adjustment for tonight's game.

    Game pace = average of both teams' pace ratings.
    League average pace ≈ 98.5 possessions per game.
    Faster pace = more stat opportunities.

    Args:
        opponent_team_abbreviation (str): Opponent 3-letter code
        player_team_abbreviation (str): Player's team 3-letter code
        teams_data (list of dict): Team data rows from teams.csv

    Returns:
        float: Pace multiplier (typically 0.93 to 1.07)
    """
    league_average_pace = LEAGUE_AVERAGE_PACE  # From module-level constant

    player_team_pace = league_average_pace   # Default if not found
    opponent_team_pace = league_average_pace  # Default if not found

    # Find each team's pace rating
    for team_row in teams_data:
        abbreviation = team_row.get("abbreviation", "")
        if abbreviation == player_team_abbreviation:
            player_team_pace = float(team_row.get("pace", league_average_pace))
        if abbreviation == opponent_team_abbreviation:
            opponent_team_pace = float(team_row.get("pace", league_average_pace))

    # Tonight's expected pace = average of both teams
    expected_game_pace = (player_team_pace + opponent_team_pace) / 2.0

    # Convert to a multiplier relative to league average
    pace_factor = expected_game_pace / league_average_pace

    return pace_factor


def _get_rest_adjustment_factor(rest_days):
    """
    Calculate performance adjustment based on rest.

    Back-to-back games (0 rest days) cause fatigue and reduce
    performance. More rest generally helps, up to a point.

    Args:
        rest_days (int): Days of rest (0 = back-to-back, 3+ = well rested)

    Returns:
        float: Multiplier (0.92 for back-to-back, up to 1.02 well rested)
    """
    # BEGINNER NOTE: This dictionary maps rest days to performance multipliers
    rest_to_factor_map = {
        0: 0.92,   # Back-to-back: significant fatigue
        1: 0.97,   # One day rest: minor fatigue
        2: 1.00,   # Two days rest: normal performance
        3: 1.01,   # Three days: slightly better than average
        4: 1.02,   # Four or more: well rested
    }

    # Get factor for the given rest days (cap at 4 since 5 = 4 essentially)
    capped_rest_days = min(rest_days, 4)
    return rest_to_factor_map.get(capped_rest_days, 1.00)


def _estimate_blowout_risk(opponent_team_abbreviation, teams_data):
    """
    Estimate the probability tonight's game becomes a blowout.

    Based on the difference in defensive ratings — if a great
    offense faces a terrible defense (or vice versa), blowout
    risk increases.

    Args:
        opponent_team_abbreviation (str): Opponent 3-letter code
        teams_data (list of dict): Team data rows

    Returns:
        float: Blowout risk probability (0.0 to 0.40)
    """
    # Find the opponent's defensive rating
    opponent_drtg = 115.0  # League average if not found

    for team_row in teams_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            opponent_drtg = float(team_row.get("drtg", 115.0))
            break

    # High defensive rating = leaky defense = less likely to blow out YOUR team
    # But also less likely opponent can control the game
    # Base blowout risk is 15% in any NBA game
    base_blowout_risk = 0.15

    # If opponent has very weak defense (drtg > 117), blowout more likely
    if opponent_drtg > 117:
        extra_risk = (opponent_drtg - 117) * 0.01  # Each extra point = 1% more risk
        blowout_risk = base_blowout_risk + extra_risk
    elif opponent_drtg < 111:
        # If opponent has elite defense, blowout risk is lower (competitive game)
        reduction = (111 - opponent_drtg) * 0.01
        blowout_risk = base_blowout_risk - reduction
    else:
        blowout_risk = base_blowout_risk

    # Cap between 5% and 40%
    return max(0.05, min(0.40, blowout_risk))


def get_stat_standard_deviation(player_data, stat_type):
    """
    Get the pre-stored standard deviation for a stat type.

    The CSV includes std values for main stats. For others,
    we estimate based on the average (coefficient of variation).

    Args:
        player_data (dict): Player row from CSV
        stat_type (str): 'points', 'rebounds', 'assists', etc.

    Returns:
        float: Standard deviation for this stat
    """
    # Try to get the stored std from the CSV first
    std_column = f"{stat_type}_std"
    stored_std = player_data.get(std_column, None)

    if stored_std is not None and stored_std != "":
        return float(stored_std)

    # BEGINNER NOTE: If we don't have a stored std, estimate it
    # using the "coefficient of variation" — most basketball stats
    # have about 30-50% variability relative to their average
    average_column = f"{stat_type}_avg"
    stored_avg = float(player_data.get(average_column, 0))

    # Different stats have different typical variability ratios
    stat_variability_ratios = {
        "points": 0.28,     # Points: ~28% of avg as std
        "rebounds": 0.32,   # Rebounds: ~32% of avg as std
        "assists": 0.38,    # Assists: ~38% of avg as std (more variable)
        "threes": 0.55,     # 3-pointers: very variable (~55%)
        "steals": 0.60,     # Steals: very variable
        "blocks": 0.65,     # Blocks: very variable
        "turnovers": 0.45,  # Turnovers: moderately variable
    }

    variability_ratio = stat_variability_ratios.get(stat_type, 0.35)
    estimated_std = stored_avg * variability_ratio

    # Minimum std of 0.5 to avoid divide-by-zero issues
    return max(0.5, estimated_std)

# ============================================================
# END SECTION: Individual Adjustment Factor Functions
# ============================================================
