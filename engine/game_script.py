# ============================================================
# FILE: engine/game_script.py
# PURPOSE: Game Script Simulation Engine
#          Simulates within-game quarter-by-quarter dynamics to
#          model how score differentials affect player minutes
#          and stat accumulation. Captures effects that flat
#          multipliers miss: star players sitting in blowouts,
#          faster/slower pace depending on lead size, etc.
#
#          Result is blended with flat Monte Carlo results (70%
#          flat, 30% game-script) since game-script adds signal
#          but is noisier than the proven flat simulation.
#
# CONNECTS TO: engine/simulation.py (blend_with_flat_simulation),
#              engine/minutes_model.py (minutes simulation)
# CONCEPTS COVERED: Game script modeling, score differential,
#                   quarter-by-quarter simulation, star player
#                   usage patterns, blowout substitution
# ============================================================

import math
import random


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# Default number of simulations for game script engine
DEFAULT_GAME_SCRIPT_SIMULATIONS = 500   # Fewer than full Monte Carlo (noisier)

# Blend weight for game-script vs flat simulation results
GAME_SCRIPT_BLEND_WEIGHT = 0.30   # 30% game-script + 70% flat Monte Carlo

# Score differential thresholds for player management (positive = winning)
BLOWOUT_DIFFERENTIAL_MILD = 12     # 12+ point lead: minor reduction
BLOWOUT_DIFFERENTIAL_HEAVY = 20    # 20+ point lead: starters sit

# Quarter-specific baseline minute distributions (out of ~12 per quarter)
# Starters typically play more in Q1/Q2, slightly less in Q3, less in Q4 (blowout risk)
STARTER_QUARTER_BASELINE_MINUTES = {
    1: 10.5,   # Q1: 10.5 of 12 available
    2: 10.0,   # Q2: 10.0 (second stint variations)
    3: 10.0,   # Q3: 10.0 (fatigue creep)
    4:  9.5,   # Q4: 9.5 (late-game management / blowout risk)
}

# Minutes reduction in blowout Q4 based on score differential
BLOWOUT_Q4_REDUCTION_MILD  = 4.0   # Mild blowout: -4 minutes in Q4
BLOWOUT_Q4_REDUCTION_HEAVY = 9.5   # Heavy blowout: effectively DNP in Q4

# Standard deviation for quarter score differential simulation
QUARTER_SCORE_STD = 8.0   # Each quarter's net score is ~N(0, 8)

# ============================================================
# END SECTION: Module-Level Constants
# ============================================================


# ============================================================
# SECTION: Quarter Minutes Estimation
# ============================================================

def estimate_quarter_minutes(avg_quarter_minutes, quarter, score_differential, is_starter=True):
    """
    Estimate minutes in a specific quarter given score differential.

    Args:
        avg_quarter_minutes (float): Player's typical minutes per quarter.
        quarter (int): Quarter number (1-4).
        score_differential (float): Current score difference (positive = leading).
        is_starter (bool): Whether the player is a starter. Default True.

    Returns:
        float: Estimated minutes in this quarter (0.0 to 12.0).

    Example:
        # Starter in Q4 with big lead
        mins = estimate_quarter_minutes(8.5, quarter=4, score_differential=22, is_starter=True)
        # → ~2.5 minutes (starters sit in garbage time)
    """
    # Start with the player's typical quarter minutes, capped at 12
    base = min(avg_quarter_minutes, 12.0)

    # Q4 blowout logic: starters get pulled based on lead size
    if quarter == 4 and abs(score_differential) > BLOWOUT_DIFFERENTIAL_HEAVY:
        if is_starter and score_differential > 0:
            # Winning big → star sits to protect from injury
            base -= BLOWOUT_Q4_REDUCTION_HEAVY
        elif is_starter and score_differential < 0:
            # Losing big → may keep starters in to try comeback, smaller cut
            base -= BLOWOUT_Q4_REDUCTION_MILD
    elif quarter == 4 and abs(score_differential) > BLOWOUT_DIFFERENTIAL_MILD:
        if is_starter and score_differential > 0:
            # Mild winning lead → some rest, partial reduction
            base -= BLOWOUT_Q4_REDUCTION_MILD

    # Add natural game-to-game variation in quarter minutes
    base += random.gauss(0, 1.5)

    # Minutes can't exceed a full quarter or go negative
    return max(0.0, min(12.0, base))

# ============================================================
# END SECTION: Quarter Minutes Estimation
# ============================================================


# ============================================================
# SECTION: Game Script Simulation
# ============================================================

def simulate_game_script(player_projection, game_context, num_simulations=500):
    """
    Simulate a player's stat distribution using quarter-by-quarter game script.

    For each simulation: simulates 4 quarters of score differential,
    determines player court time each quarter based on differential,
    then derives stat accumulation from per-minute rate.

    Args:
        player_projection (dict): Output from projections.py with keys:
            'projected_stat' (float), 'projected_minutes' (float),
            'stat_std' (float, optional).
        game_context (dict): Game info with 'vegas_spread' (float),
            'game_total' (float), 'is_home' (bool).
        num_simulations (int): Number of game-script simulations. Default 500.

    Returns:
        dict: {
            'simulated_values': list of float,   # Raw simulation outputs
            'mean': float,
            'std': float,
            'p10': float,   # 10th percentile (floor)
            'p90': float,   # 90th percentile (ceiling)
            'blowout_game_rate': float,  # Fraction of simulations that became blowouts
        }

    Example:
        results = simulate_game_script(
            player_projection={'projected_stat': 25.0, 'projected_minutes': 34.0},
            game_context={'vegas_spread': 8.0, 'game_total': 228.5, 'is_home': True},
        )
    """
    projected_stat = float(player_projection.get('projected_stat', 20.0))
    projected_minutes = float(player_projection.get('projected_minutes', 32.0))

    vegas_spread = float(game_context.get('vegas_spread', 0.0))
    is_home = bool(game_context.get('is_home', False))

    # Per-minute production rate (stat per minute on the court)
    stat_per_minute = projected_stat / max(1.0, projected_minutes)

    # Average minutes per quarter based on full game projection
    avg_quarter_minutes = projected_minutes / 4.0

    # Vegas spread shifts expected differential per quarter
    # Positive spread means player's team favored to win by that many points
    spread_per_quarter = vegas_spread / 4.0

    # Home court advantage contributes to Q1 differential
    home_bias = 1.5 if is_home else 0.0

    simulated_values = []
    blowout_count = 0

    for _ in range(num_simulations):
        running_differential = 0.0
        total_simulated_minutes = 0.0
        game_became_blowout = False

        for quarter in range(1, 5):
            # Simulate this quarter's net score swing
            # Home bias only applied in Q1 opener; spread distributes evenly
            q1_home_component = home_bias if quarter == 1 else 0.0
            quarter_swing = random.gauss(
                spread_per_quarter + q1_home_component,
                QUARTER_SCORE_STD
            )
            running_differential += quarter_swing

            # Detect blowout at any quarter
            if abs(running_differential) > BLOWOUT_DIFFERENTIAL_HEAVY:
                game_became_blowout = True

            # Estimate how many minutes the player plays this quarter
            quarter_minutes = estimate_quarter_minutes(
                avg_quarter_minutes,
                quarter,
                running_differential,
                True   # Treat as starter for conservative modeling
            )
            total_simulated_minutes += quarter_minutes

        if game_became_blowout:
            blowout_count += 1

        # Derive simulated stat from per-minute rate × actual minutes × game variance
        raw_stat = stat_per_minute * total_simulated_minutes * random.gauss(1.0, 0.15)
        simulated_stat = max(0.0, raw_stat)
        simulated_values.append(simulated_stat)

    # ---- Summarize distribution ----
    n = len(simulated_values)
    mean_val = sum(simulated_values) / n if n > 0 else 0.0

    variance = sum((v - mean_val) ** 2 for v in simulated_values) / max(1, n - 1)
    std_val = math.sqrt(variance)

    sorted_vals = sorted(simulated_values)
    p10_idx = max(0, int(0.10 * n) - 1)
    p90_idx = min(n - 1, int(0.90 * n))
    p10_val = sorted_vals[p10_idx] if sorted_vals else 0.0
    p90_val = sorted_vals[p90_idx] if sorted_vals else 0.0

    blowout_rate = blowout_count / n if n > 0 else 0.0

    return {
        'simulated_values': simulated_values,
        'mean': round(mean_val, 3),
        'std': round(std_val, 3),
        'p10': round(p10_val, 3),
        'p90': round(p90_val, 3),
        'blowout_game_rate': round(blowout_rate, 4),
    }

# ============================================================
# END SECTION: Game Script Simulation
# ============================================================


# ============================================================
# SECTION: Flat Simulation Blending
# ============================================================

def blend_with_flat_simulation(game_script_results, flat_simulation_results, blend_weight=0.30):
    """
    Blend game-script simulation results with flat Monte Carlo results.

    Uses blend_weight for game-script and (1-blend_weight) for flat simulation.
    The mean and std are blended; the combined result is what gets used
    for probability calculation.

    Args:
        game_script_results (dict): Output from simulate_game_script.
        flat_simulation_results (dict): Standard Monte Carlo output (from simulation.py).
            Expected keys: 'mean' (or 'average'), 'std' (or 'standard_deviation').
        blend_weight (float): Weight for game-script component. Default 0.30.

    Returns:
        dict: {
            'blended_mean': float,
            'blended_std': float,
            'game_script_mean': float,
            'flat_mean': float,
            'blend_weight': float,
        }

    Example:
        blended = blend_with_flat_simulation(gs_results, flat_results, blend_weight=0.30)
        # blended['blended_mean'] = 0.30 * gs_mean + 0.70 * flat_mean
    """
    gs_mean = float(game_script_results.get('mean', 0.0))
    gs_std  = float(game_script_results.get('std', 0.0))

    # Support both key naming conventions from simulation.py
    flat_mean = float(
        flat_simulation_results.get('mean',
        flat_simulation_results.get('average', 0.0))
    )
    flat_std = float(
        flat_simulation_results.get('std',
        flat_simulation_results.get('standard_deviation', 0.0))
    )

    flat_weight = 1.0 - blend_weight

    blended_mean = blend_weight * gs_mean + flat_weight * flat_mean
    blended_std  = blend_weight * gs_std  + flat_weight * flat_std

    return {
        'blended_mean':      round(blended_mean, 3),
        'blended_std':       round(blended_std, 3),
        'game_script_mean':  round(gs_mean, 3),
        'flat_mean':         round(flat_mean, 3),
        'blend_weight':      blend_weight,
    }

# ============================================================
# END SECTION: Flat Simulation Blending
# ============================================================
