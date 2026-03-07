# ============================================================
# FILE: engine/simulation.py
# PURPOSE: Monte Carlo simulation engine — runs thousands of
#          simulated games for each player to build a realistic
#          probability distribution of their stat outcomes.
# CONNECTS TO: math_helpers.py (sampling), projections.py (input)
# CONCEPTS COVERED: Monte Carlo method, simulation loops,
#                   distribution building, blowout risk
# ============================================================

# Standard library imports only
import random   # For randomizing game scenarios (minutes, pace)
import math     # For mathematical rounding and calculations

# Import our custom math helpers (built from scratch)
from engine.math_helpers import (
    sample_from_normal_distribution,  # Draw a random game result
    calculate_mean,                    # Average a list of results
    calculate_standard_deviation,      # Spread of results
    calculate_percentile,              # Find value at percentile
    clamp_probability,                 # Keep probability in 0-1
)


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# Probability of foul trouble in any given game.
# About 12% of games, a player picks up 4-5 fouls and sits.
# This is based on historical NBA foul-out/sit-out data.
FOUL_TROUBLE_PROBABILITY = 0.12

# ============================================================
# SECTION: Game Scenario Probabilities (W3: Ceiling/Floor Games)
# Replaces the old independent blowout + foul trouble rolls with
# a correlated game scenario system. Each scenario applies a
# CORRELATED effect on both minutes AND stats.
# Probabilities must sum to 1.0.
# ============================================================

# Each scenario: (probability, minutes_reduction_min, minutes_reduction_max, stat_multiplier_min, stat_multiplier_max)
# minutes_reduction: fraction of minutes LOST (negative = extra minutes gained)
# stat_multiplier: applied on top of the scaled projection
GAME_SCENARIOS = [
    # (name, probability, minutes_reduction_min, minutes_reduction_max, stat_boost_min, stat_boost_max)
    ("normal",       0.65,  0.00,  0.05,  0.97,  1.03),  # Normal game: minimal impact
    ("blowout_win",  0.10,  0.15,  0.25,  0.90,  0.95),  # Team wins big, star sits late
    ("blowout_loss", 0.08,  0.10,  0.20,  0.88,  0.98),  # Team loses big, garbage time
    ("foul_trouble", 0.07,  0.15,  0.30,  0.92,  1.00),  # Foul trouble limits minutes
    ("close_game",   0.07, -0.15, -0.05,  1.05,  1.15),  # Close game / OT: MORE minutes, stat boost
    ("injury_scare", 0.03,  0.40,  0.60,  0.30,  0.60),  # Injury scare: massive minutes cut
]

# Validate scenario probabilities sum to 1.0
_SCENARIO_PROB_SUM = sum(s[1] for s in GAME_SCENARIOS)
assert abs(_SCENARIO_PROB_SUM - 1.0) < 1e-6, (
    f"GAME_SCENARIOS probabilities must sum to 1.0, got {_SCENARIO_PROB_SUM:.4f}"
)

# ============================================================
# SECTION: Hot Hand / Cold Game Probabilities (W4: Momentum)
# In real NBA games, players have "on fire" nights and "ice cold"
# nights that create fatter tails than a pure normal distribution.
# ============================================================

# Probability and multiplier ranges for momentum games
HOT_HAND_PROBABILITY = 0.15   # 15% chance player is "on fire"
HOT_HAND_MULTIPLIER_MIN = 1.15
HOT_HAND_MULTIPLIER_MAX = 1.30

COLD_GAME_PROBABILITY = 0.10  # 10% chance player is "ice cold"
COLD_GAME_MULTIPLIER_MIN = 0.70
COLD_GAME_MULTIPLIER_MAX = 0.85

# ============================================================
# END SECTION: Module-Level Constants
# ============================================================

# SECTION: Monte Carlo Simulation Core
# Monte Carlo = run the same random experiment thousands of
# times and look at the overall distribution of results.
# Like flipping a coin 10,000 times to verify it's fair.
# ============================================================

def run_monte_carlo_simulation(
    projected_stat_average,
    stat_standard_deviation,
    prop_line,
    number_of_simulations,
    blowout_risk_factor,
    pace_adjustment_factor,
    matchup_adjustment_factor,
    home_away_adjustment,
    rest_adjustment_factor,
):
    """
    Run a full Monte Carlo simulation for one player's one stat.

    Simulates `number_of_simulations` games, each with randomized
    minutes (blowout risk, foul trouble) and stat variance.
    Builds a distribution and calculates P(over line).

    Args:
        projected_stat_average (float): Our projected mean for the stat
        stat_standard_deviation (float): Historical variability (std dev)
        prop_line (float): The betting line to beat
        number_of_simulations (int): How many games to simulate (100-5000)
        blowout_risk_factor (float): 0.0-1.0; higher = more blowout risk
            A blowout (big lead) means stars play fewer garbage-time mins
        pace_adjustment_factor (float): Multiplier for game pace (0.85-1.15)
            Faster game = more possessions = more stat opportunities
        matchup_adjustment_factor (float): Multiplier for opponent defense
            0.9 = tough defense, 1.1 = weak defense
        home_away_adjustment (float): Small home-court boost or penalty
            Typical: home=+0.02, away=-0.02
        rest_adjustment_factor (float): Adjustment for rest days
            Back-to-back game = tired player = slight negative adjustment

    Returns:
        dict: Simulation results containing:
            - 'simulated_results': list of all simulated game stats
            - 'probability_over': float, P(result > line)
            - 'simulated_mean': float, average of simulated results
            - 'simulated_std': float, std dev of simulated results
            - 'percentile_10': float, 10th percentile (bad game)
            - 'percentile_50': float, median game
            - 'percentile_90': float, 90th percentile (great game)

    Example:
        LeBron projects 25 pts, std=6, line=24.5 →
        maybe 55-60% of simulated games go over 24.5
    """
    # ============================================================
    # SECTION: Apply Pre-Simulation Adjustments
    # Adjust the base projection for tonight's specific context
    # ============================================================

    # Combine all adjustment factors into one multiplier
    # Each factor is close to 1.0 (neutral), above = boost, below = penalty
    combined_adjustment_multiplier = (
        pace_adjustment_factor      # Game pace boost/penalty
        * matchup_adjustment_factor  # Opponent defense boost/penalty
        * (1.0 + home_away_adjustment)  # Home court advantage
        * rest_adjustment_factor    # Rest/fatigue adjustment
    )

    # Calculate the final adjusted projection for tonight
    adjusted_stat_projection = projected_stat_average * combined_adjustment_multiplier

    # Adjust standard deviation slightly for extreme multipliers
    # When pace is high, variance also increases (more unpredictable)
    adjusted_standard_deviation = stat_standard_deviation * (
        1.0 + 0.1 * (combined_adjustment_multiplier - 1.0)
    )

    # Make sure std doesn't go below a minimum (always some variability)
    adjusted_standard_deviation = max(adjusted_standard_deviation, 0.5)

    # ============================================================
    # END SECTION: Apply Pre-Simulation Adjustments
    # ============================================================

    # ============================================================
    # SECTION: Run Simulation Loop
    # This is the heart of Monte Carlo — simulate many games!
    # ============================================================

    # List to store every simulated game's result
    all_simulated_game_results = []

    # Counter for games where player goes OVER the prop line
    count_of_games_over_line = 0

    # Run the simulation `number_of_simulations` times
    # BEGINNER NOTE: range(n) creates numbers 0 to n-1
    # We don't care about the index, just need to loop n times
    for _ in range(number_of_simulations):

        # --- Step 1: Pick a Game Scenario (W3: Ceiling/Floor Games) ---
        # Instead of rolling blowout and foul trouble independently,
        # we now pick ONE holistic scenario that determines BOTH minutes
        # AND stats together. This models the real-world correlation:
        # e.g., a player in foul trouble in a blowout DEFINITELY sits.
        scenario_name, minutes_reduction, stat_scenario_multiplier = (
            _simulate_game_scenario(blowout_risk_factor)
        )

        # minutes_reduction can be negative (close game/OT = extra minutes)
        # Cap to [-0.15, 0.60] to avoid negative or impossibly high minutes
        minutes_reduction = max(-0.15, min(0.60, minutes_reduction))
        minutes_multiplier = 1.0 - minutes_reduction

        # --- Step 2: Apply Hot Hand / Cold Game Modifier (W4: Momentum) ---
        # In 15% of games the player is "on fire"; in 10% they're "ice cold".
        # This creates fat tails in the distribution, especially for threes.
        momentum_multiplier = _simulate_hot_cold_modifier()

        # --- Step 3: Simulate the Actual Stat ---
        # Scale projection by minutes played, then add randomness
        effective_mean = (
            adjusted_stat_projection
            * minutes_multiplier
            * stat_scenario_multiplier
            * momentum_multiplier
        )

        # Scale std dev proportionally (less minutes = less variance too)
        scaled_std = adjusted_standard_deviation * math.sqrt(max(0.1, minutes_multiplier))

        # Draw a random sample: this is one simulated game's result
        simulated_game_stat = sample_from_normal_distribution(
            effective_mean, scaled_std
        )

        # Stats can't be negative (can't have -3 assists)
        simulated_game_stat = max(0.0, simulated_game_stat)

        # --- Step 4: Record the Result ---
        all_simulated_game_results.append(simulated_game_stat)

        # Did this simulated game go OVER the prop line?
        if simulated_game_stat > prop_line:
            count_of_games_over_line += 1

    # ============================================================
    # END SECTION: Run Simulation Loop
    # ============================================================

    # ============================================================
    # SECTION: Compile Results
    # Summarize the simulation results into useful statistics
    # ============================================================

    # Raw probability = games over / total games simulated
    raw_probability_over = count_of_games_over_line / number_of_simulations

    # Clamp to [0.01, 0.99] — never 100% certain
    final_probability_over = clamp_probability(raw_probability_over)

    # Build the results dictionary
    simulation_results = {
        "simulated_results": all_simulated_game_results,
        "probability_over": final_probability_over,
        "simulated_mean": calculate_mean(all_simulated_game_results),
        "simulated_std": calculate_standard_deviation(all_simulated_game_results),
        "percentile_10": calculate_percentile(all_simulated_game_results, 10),
        "percentile_25": calculate_percentile(all_simulated_game_results, 25),
        "percentile_50": calculate_percentile(all_simulated_game_results, 50),
        "percentile_75": calculate_percentile(all_simulated_game_results, 75),
        "percentile_90": calculate_percentile(all_simulated_game_results, 90),
        "adjusted_projection": adjusted_stat_projection,
        "combined_adjustment": combined_adjustment_multiplier,
    }

    return simulation_results

    # ============================================================
    # END SECTION: Compile Results
    # ============================================================


# ============================================================
# SECTION: Helper Functions for Game Scenario Randomization
# These internal helpers simulate realistic game situations
# like blowouts and foul trouble.
# ============================================================

def _simulate_game_scenario(blowout_risk_factor):
    """
    Pick a holistic game scenario for this simulated game. (W3)

    Replaces the old independent blowout + foul trouble rolls with
    a single scenario that applies CORRELATED effects on both
    minutes and stats. The blowout scenarios are scaled by the
    incoming `blowout_risk_factor` so high-spread games still
    get more blowout weight.

    Args:
        blowout_risk_factor (float): 0.0-1.0 blowout probability
            from projections.py. Higher → more weight on blowout
            scenarios, less on normal game.

    Returns:
        tuple: (scenario_name: str,
                minutes_reduction: float,   # fraction of mins lost (negative = gained)
                stat_multiplier: float)     # additional stat modifier
    """
    # Scale blowout scenario weights by the actual blowout risk.
    # Base blowout_win + blowout_loss weight is 0.18. If blowout_risk_factor
    # is higher than the base 0.15, shift weight from "normal" to blowout.
    blowout_extra = max(0.0, blowout_risk_factor - 0.15)  # extra risk beyond base

    adjusted_scenarios = []
    for name, prob, min_red_lo, min_red_hi, stat_lo, stat_hi in GAME_SCENARIOS:
        if name in ("blowout_win", "blowout_loss"):
            adjusted_prob = prob + blowout_extra * 0.5  # split extra between win/loss
        elif name == "normal":
            adjusted_prob = prob - blowout_extra  # reduce normal probability
        else:
            adjusted_prob = prob
        adjusted_scenarios.append((name, max(0.0, adjusted_prob), min_red_lo, min_red_hi, stat_lo, stat_hi))

    # Normalize so probabilities sum to 1
    total_weight = sum(s[1] for s in adjusted_scenarios)
    roll = random.random() * total_weight

    cumulative = 0.0
    for name, prob, min_red_lo, min_red_hi, stat_lo, stat_hi in adjusted_scenarios:
        cumulative += prob
        if roll <= cumulative:
            minutes_reduction = random.uniform(min_red_lo, min_red_hi)
            stat_multiplier = random.uniform(stat_lo, stat_hi)
            return name, minutes_reduction, stat_multiplier

    # Fallback: normal game
    return "normal", random.uniform(0.0, 0.05), random.uniform(0.97, 1.03)


def _simulate_hot_cold_modifier():
    """
    Apply a "hot hand" or "cold game" multiplier to the stat mean. (W4)

    In real NBA games, players have momentum nights (three-point
    streaks, every shot dropping) and ice-cold nights. This creates
    a distribution with FATTER TAILS than a pure normal, which is
    especially important for streaky stats like threes.

    Returns:
        float: Multiplier near 1.0 (hot → 1.15-1.30, cold → 0.70-0.85)
    """
    roll = random.random()

    if roll < HOT_HAND_PROBABILITY:
        # "On fire" game — player is in a rhythm
        return random.uniform(HOT_HAND_MULTIPLIER_MIN, HOT_HAND_MULTIPLIER_MAX)
    elif roll < HOT_HAND_PROBABILITY + COLD_GAME_PROBABILITY:
        # "Ice cold" game — nothing going in
        return random.uniform(COLD_GAME_MULTIPLIER_MIN, COLD_GAME_MULTIPLIER_MAX)
    else:
        # Typical game — no hot/cold modifier
        return 1.0


def _simulate_blowout_minutes_reduction(blowout_risk_factor):
    """
    Simulate whether a blowout causes star players to sit.

    NOTE: This function is kept for use by combo/fantasy simulations
    that haven't yet migrated to the scenario system.

    Args:
        blowout_risk_factor (float): 0.0 to 1.0 probability
            that tonight's game becomes a blowout (15+ point margin)

    Returns:
        float: Fraction of minutes reduced (0.0 to 0.30)
    """
    # Roll a random float between 0 and 1
    # If it's below the blowout risk, a blowout occurred
    random_roll = random.random()  # Returns float in [0.0, 1.0)

    if random_roll < blowout_risk_factor:
        # Blowout occurred — how many minutes does the star lose?
        # Stars typically lose 4-10 minutes in a blowout
        # Simulate: uniformly pick a reduction of 10% to 30%
        minutes_reduction = random.uniform(0.10, 0.30)
        return minutes_reduction
    else:
        # No blowout — no reduction from this factor
        return 0.0


def _simulate_foul_trouble_minutes_reduction():
    """
    Simulate whether a player sits due to foul trouble.

    High-usage players (stars) foul out or pick up 4-5 fouls
    and sit in about 12% of games.

    Returns:
        float: Fraction of minutes reduced (0.0 to 0.25)
    """
    # About 12% chance of meaningful foul trouble in any game
    # Using the module constant instead of a magic number
    random_roll = random.random()

    if random_roll < FOUL_TROUBLE_PROBABILITY:
        # Foul trouble: lose 5%-25% of typical minutes
        minutes_reduction = random.uniform(0.05, 0.25)
        return minutes_reduction
    else:
        return 0.0


def build_histogram_from_results(simulated_results, prop_line, number_of_buckets=20):
    """
    Build a histogram (frequency distribution) from simulation results.
    Used by the Analysis page to display a bar chart.

    Args:
        simulated_results (list of float): All simulated game stats
        prop_line (float): The betting line (shown as divider on chart)
        number_of_buckets (int): How many bars in the histogram (default 20)

    Returns:
        list of dict: Each dict has 'bucket_label', 'count', 'is_over_line'
    """
    if not simulated_results:
        return []  # Return empty list if no results

    # Find the range of results (min to max)
    minimum_result = min(simulated_results)
    maximum_result = max(simulated_results)

    # Calculate the width of each histogram bucket
    # BEGINNER NOTE: We divide the range into equal-width buckets
    total_range = maximum_result - minimum_result
    if total_range == 0:
        return []  # All results are identical (no spread)

    bucket_width = total_range / number_of_buckets

    # Initialize buckets as empty
    # Each bucket tracks: start value, end value, count of results
    histogram_buckets = []
    for bucket_index in range(number_of_buckets):
        bucket_start = minimum_result + (bucket_index * bucket_width)
        bucket_end = bucket_start + bucket_width
        bucket_midpoint = (bucket_start + bucket_end) / 2.0

        histogram_buckets.append({
            "bucket_label": f"{bucket_midpoint:.1f}",  # Label = midpoint
            "bucket_start": bucket_start,
            "bucket_end": bucket_end,
            "count": 0,
            "is_over_line": bucket_midpoint > prop_line  # Is this bucket above line?
        })

    # Count how many simulation results fall into each bucket
    for result in simulated_results:
        for bucket in histogram_buckets:
            if bucket["bucket_start"] <= result < bucket["bucket_end"]:
                bucket["count"] += 1
                break  # Found the right bucket, move on
        # Handle the last bucket's upper edge
        if result == maximum_result:
            histogram_buckets[-1]["count"] += 1

    return histogram_buckets


# ============================================================
# SECTION: Combo / Fantasy Stat Simulations
# These extend the Monte Carlo engine to handle multi-stat
# props (Pts+Rebs, PRA, etc.) and fantasy score props.
# ============================================================

def simulate_combo_stat(
    component_projections,
    component_std_devs,
    prop_line,
    number_of_simulations,
    blowout_risk_factor,
    pace_adjustment_factor,
    matchup_adjustment_factor,
    home_away_adjustment,
    rest_adjustment_factor,
):
    """
    Run a correlated Monte Carlo simulation for a combo stat prop.

    Combo stats (Pts+Rebs, PRA, etc.) share a minutes factor —
    a blowout or foul trouble affects ALL component stats together.
    This correlated approach avoids over-counting variance.

    Args:
        component_projections (dict): {stat_key: projected_avg}
            e.g., {"points": 24.0, "rebounds": 8.0}
        component_std_devs (dict): {stat_key: std_dev}
        prop_line (float): Combo prop line (sum of components)
        number_of_simulations (int): Simulations to run
        blowout_risk_factor (float): Blowout probability (0-1)
        pace_adjustment_factor (float): Pace multiplier
        matchup_adjustment_factor (float): Defense multiplier
        home_away_adjustment (float): Home-court additive
        rest_adjustment_factor (float): Rest multiplier

    Returns:
        dict: Same structure as run_monte_carlo_simulation()
    """
    combined_multiplier = (
        pace_adjustment_factor
        * matchup_adjustment_factor
        * (1.0 + home_away_adjustment)
        * rest_adjustment_factor
    )

    # Adjust all component projections by the shared multiplier
    adjusted = {
        k: v * combined_multiplier
        for k, v in component_projections.items()
    }
    adjusted_stds = {
        k: max(v * (1.0 + 0.1 * (combined_multiplier - 1.0)), 0.3)
        for k, v in component_std_devs.items()
    }

    all_combo_results = []
    count_over = 0

    for _ in range(number_of_simulations):
        # Shared minutes multiplier (correlated across all components)
        blowout_reduction = _simulate_blowout_minutes_reduction(blowout_risk_factor)
        foul_reduction = _simulate_foul_trouble_minutes_reduction()
        total_reduction = min(0.40, blowout_reduction + foul_reduction)
        minutes_mult = 1.0 - total_reduction

        combo_value = 0.0
        for stat_key, proj in adjusted.items():
            scaled_proj = proj * minutes_mult
            scaled_std = adjusted_stds.get(stat_key, proj * 0.35) * math.sqrt(minutes_mult)
            sim_val = max(0.0, sample_from_normal_distribution(scaled_proj, scaled_std))
            combo_value += sim_val

        all_combo_results.append(combo_value)
        if combo_value > prop_line:
            count_over += 1

    raw_prob_over = count_over / number_of_simulations
    final_prob_over = clamp_probability(raw_prob_over)

    return {
        "simulated_results": all_combo_results,
        "probability_over": final_prob_over,
        "simulated_mean": calculate_mean(all_combo_results),
        "simulated_std": calculate_standard_deviation(all_combo_results),
        "percentile_10": calculate_percentile(all_combo_results, 10),
        "percentile_25": calculate_percentile(all_combo_results, 25),
        "percentile_50": calculate_percentile(all_combo_results, 50),
        "percentile_75": calculate_percentile(all_combo_results, 75),
        "percentile_90": calculate_percentile(all_combo_results, 90),
        "adjusted_projection": sum(adjusted.values()),
        "combined_adjustment": combined_multiplier,
    }


def simulate_fantasy_score(
    stat_projections,
    stat_std_devs,
    fantasy_formula,
    prop_line,
    number_of_simulations,
    blowout_risk_factor,
    pace_adjustment_factor,
    matchup_adjustment_factor,
    home_away_adjustment,
    rest_adjustment_factor,
):
    """
    Simulate a fantasy score prop using the platform's scoring formula.

    All component stats share a minutes factor (correlated), then the
    platform formula weights each stat to produce a fantasy total.

    Args:
        stat_projections (dict): {stat_key: projected_avg}
        stat_std_devs (dict): {stat_key: std_dev}
        fantasy_formula (dict): {stat_key: multiplier}
            e.g., {"points": 1.0, "rebounds": 1.2, ...}
        prop_line (float): Fantasy score line
        number_of_simulations (int): Simulations to run
        blowout_risk_factor (float): Blowout probability (0-1)
        pace_adjustment_factor (float): Pace multiplier
        matchup_adjustment_factor (float): Defense multiplier
        home_away_adjustment (float): Home-court additive
        rest_adjustment_factor (float): Rest multiplier

    Returns:
        dict: Same structure as run_monte_carlo_simulation()
    """
    combined_multiplier = (
        pace_adjustment_factor
        * matchup_adjustment_factor
        * (1.0 + home_away_adjustment)
        * rest_adjustment_factor
    )

    adjusted = {k: v * combined_multiplier for k, v in stat_projections.items()}
    adjusted_stds = {
        k: max(v * (1.0 + 0.1 * (combined_multiplier - 1.0)), 0.3)
        for k, v in stat_std_devs.items()
    }

    all_fantasy_results = []
    count_over = 0

    for _ in range(number_of_simulations):
        blowout_reduction = _simulate_blowout_minutes_reduction(blowout_risk_factor)
        foul_reduction = _simulate_foul_trouble_minutes_reduction()
        total_reduction = min(0.40, blowout_reduction + foul_reduction)
        minutes_mult = 1.0 - total_reduction

        fantasy_val = 0.0
        for stat_key, multiplier in fantasy_formula.items():
            proj = adjusted.get(stat_key, 0.0)
            std = adjusted_stds.get(stat_key, proj * 0.35)
            scaled_proj = proj * minutes_mult
            scaled_std = std * math.sqrt(minutes_mult)
            sim_val = max(0.0, sample_from_normal_distribution(scaled_proj, scaled_std))
            fantasy_val += sim_val * multiplier

        all_fantasy_results.append(fantasy_val)
        if fantasy_val > prop_line:
            count_over += 1

    raw_prob_over = count_over / number_of_simulations
    final_prob_over = clamp_probability(raw_prob_over)

    # Compute the adjusted projected fantasy score
    projected_fantasy = sum(
        adjusted.get(s, 0.0) * m for s, m in fantasy_formula.items()
    )

    return {
        "simulated_results": all_fantasy_results,
        "probability_over": final_prob_over,
        "simulated_mean": calculate_mean(all_fantasy_results),
        "simulated_std": calculate_standard_deviation(all_fantasy_results),
        "percentile_10": calculate_percentile(all_fantasy_results, 10),
        "percentile_25": calculate_percentile(all_fantasy_results, 25),
        "percentile_50": calculate_percentile(all_fantasy_results, 50),
        "percentile_75": calculate_percentile(all_fantasy_results, 75),
        "percentile_90": calculate_percentile(all_fantasy_results, 90),
        "adjusted_projection": projected_fantasy,
        "combined_adjustment": combined_multiplier,
    }


def simulate_double_double(
    stat_projections,
    stat_std_devs,
    number_of_simulations,
    blowout_risk_factor,
    pace_adjustment_factor,
    matchup_adjustment_factor,
    home_away_adjustment,
    rest_adjustment_factor,
):
    """
    Simulate P(double-double) — 2+ stats each reaching 10+ in a game.

    Double-double is a Yes/No prop. The "line" is always 0.5
    (over 0.5 = Yes = double-double occurs).

    Args:
        stat_projections (dict): {stat_key: projected_avg} for relevant
            stats (points, rebounds, assists, blocks, steals)
        stat_std_devs (dict): {stat_key: std_dev}
        number_of_simulations (int): Simulations to run
        blowout_risk_factor (float): Blowout probability (0-1)
        pace_adjustment_factor (float): Pace multiplier
        matchup_adjustment_factor (float): Defense multiplier
        home_away_adjustment (float): Home-court additive
        rest_adjustment_factor (float): Rest multiplier

    Returns:
        dict: Simulation results where probability_over = P(double-double).
              The "simulated_results" are 0.0/1.0 indicators.
    """
    combined_multiplier = (
        pace_adjustment_factor
        * matchup_adjustment_factor
        * (1.0 + home_away_adjustment)
        * rest_adjustment_factor
    )

    adjusted = {k: v * combined_multiplier for k, v in stat_projections.items()}
    adjusted_stds = {
        k: max(v * (1.0 + 0.1 * (combined_multiplier - 1.0)), 0.3)
        for k, v in stat_std_devs.items()
    }

    all_results = []
    count_double_double = 0
    DOUBLE_DOUBLE_THRESHOLD = 10

    for _ in range(number_of_simulations):
        blowout_reduction = _simulate_blowout_minutes_reduction(blowout_risk_factor)
        foul_reduction = _simulate_foul_trouble_minutes_reduction()
        total_reduction = min(0.40, blowout_reduction + foul_reduction)
        minutes_mult = 1.0 - total_reduction

        stats_at_10_plus = 0
        for stat_key, proj in adjusted.items():
            std = adjusted_stds.get(stat_key, proj * 0.35)
            scaled_proj = proj * minutes_mult
            scaled_std = std * math.sqrt(minutes_mult)
            sim_val = max(0.0, sample_from_normal_distribution(scaled_proj, scaled_std))
            if sim_val >= DOUBLE_DOUBLE_THRESHOLD:
                stats_at_10_plus += 1

        hit = 1.0 if stats_at_10_plus >= 2 else 0.0
        all_results.append(hit)
        if hit:
            count_double_double += 1

    raw_prob = count_double_double / number_of_simulations
    final_prob = clamp_probability(raw_prob)

    return {
        "simulated_results": all_results,
        "probability_over": final_prob,
        "simulated_mean": raw_prob,
        "simulated_std": math.sqrt(raw_prob * (1 - raw_prob)) if 0 < raw_prob < 1 else 0.0,
        "percentile_10": 0.0,
        "percentile_25": 0.0,
        "percentile_50": 1.0 if raw_prob >= 0.5 else 0.0,
        "percentile_75": 1.0 if raw_prob >= 0.25 else 0.0,
        "percentile_90": 1.0 if raw_prob >= 0.1 else 0.0,
        "adjusted_projection": raw_prob,
        "combined_adjustment": combined_multiplier,
    }


def simulate_triple_double(
    stat_projections,
    stat_std_devs,
    number_of_simulations,
    blowout_risk_factor,
    pace_adjustment_factor,
    matchup_adjustment_factor,
    home_away_adjustment,
    rest_adjustment_factor,
):
    """
    Simulate P(triple-double) — 3+ stats each reaching 10+ in a game.

    Args:
        stat_projections (dict): {stat_key: projected_avg}
        stat_std_devs (dict): {stat_key: std_dev}
        number_of_simulations (int): Simulations to run
        blowout_risk_factor (float): Blowout probability (0-1)
        pace_adjustment_factor (float): Pace multiplier
        matchup_adjustment_factor (float): Defense multiplier
        home_away_adjustment (float): Home-court additive
        rest_adjustment_factor (float): Rest multiplier

    Returns:
        dict: Simulation results where probability_over = P(triple-double).
    """
    combined_multiplier = (
        pace_adjustment_factor
        * matchup_adjustment_factor
        * (1.0 + home_away_adjustment)
        * rest_adjustment_factor
    )

    adjusted = {k: v * combined_multiplier for k, v in stat_projections.items()}
    adjusted_stds = {
        k: max(v * (1.0 + 0.1 * (combined_multiplier - 1.0)), 0.3)
        for k, v in stat_std_devs.items()
    }

    all_results = []
    count_triple_double = 0
    TRIPLE_DOUBLE_THRESHOLD = 10

    for _ in range(number_of_simulations):
        blowout_reduction = _simulate_blowout_minutes_reduction(blowout_risk_factor)
        foul_reduction = _simulate_foul_trouble_minutes_reduction()
        total_reduction = min(0.40, blowout_reduction + foul_reduction)
        minutes_mult = 1.0 - total_reduction

        stats_at_10_plus = 0
        for stat_key, proj in adjusted.items():
            std = adjusted_stds.get(stat_key, proj * 0.35)
            scaled_proj = proj * minutes_mult
            scaled_std = std * math.sqrt(minutes_mult)
            sim_val = max(0.0, sample_from_normal_distribution(scaled_proj, scaled_std))
            if sim_val >= TRIPLE_DOUBLE_THRESHOLD:
                stats_at_10_plus += 1

        hit = 1.0 if stats_at_10_plus >= 3 else 0.0
        all_results.append(hit)
        if hit:
            count_triple_double += 1

    raw_prob = count_triple_double / number_of_simulations
    final_prob = clamp_probability(raw_prob)

    return {
        "simulated_results": all_results,
        "probability_over": final_prob,
        "simulated_mean": raw_prob,
        "simulated_std": math.sqrt(raw_prob * (1 - raw_prob)) if 0 < raw_prob < 1 else 0.0,
        "percentile_10": 0.0,
        "percentile_25": 0.0,
        "percentile_50": 1.0 if raw_prob >= 0.5 else 0.0,
        "percentile_75": 1.0 if raw_prob >= 0.25 else 0.0,
        "percentile_90": 1.0 if raw_prob >= 0.1 else 0.0,
        "adjusted_projection": raw_prob,
        "combined_adjustment": combined_multiplier,
    }

# ============================================================
# END SECTION: Combo / Fantasy Stat Simulations
# ============================================================
