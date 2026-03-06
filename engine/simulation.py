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

        # --- Step 1: Simulate Minutes Played ---
        # Players don't always play full minutes. Randomize:
        # - Blowout risk: big leads → stars sit in 4th quarter
        # - Foul trouble: 4-5 fouls → reduced minutes
        minutes_reduction_from_blowout = _simulate_blowout_minutes_reduction(
            blowout_risk_factor
        )
        minutes_reduction_from_fouls = _simulate_foul_trouble_minutes_reduction()

        # Combine minutes reductions (can't reduce more than 40%)
        total_minutes_reduction = min(
            0.40,
            minutes_reduction_from_blowout + minutes_reduction_from_fouls
        )

        # Minutes multiplier: 1.0 = full game, 0.6 = only 60% of minutes
        minutes_multiplier = 1.0 - total_minutes_reduction

        # --- Step 2: Simulate the Actual Stat ---
        # Scale projection by minutes played, then add randomness
        scaled_projection = adjusted_stat_projection * minutes_multiplier

        # Scale std dev proportionally (less minutes = less variance too)
        scaled_std = adjusted_standard_deviation * math.sqrt(minutes_multiplier)

        # Draw a random sample: this is one simulated game's result
        simulated_game_stat = sample_from_normal_distribution(
            scaled_projection, scaled_std
        )

        # Stats can't be negative (can't have -3 assists)
        simulated_game_stat = max(0.0, simulated_game_stat)

        # --- Step 3: Record the Result ---
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

def _simulate_blowout_minutes_reduction(blowout_risk_factor):
    """
    Simulate whether a blowout causes star players to sit.

    In blowout games, coaches rest starters in garbage time,
    reducing their chance to pad stats.

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
# END SECTION: Helper Functions for Game Scenario Randomization
# ============================================================
