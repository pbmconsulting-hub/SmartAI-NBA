# ============================================================
# FILE: engine/simulation.py
# PURPOSE: Quantum Matrix Engine 5.6 simulation engine — runs thousands of
#          simulated games for each player to build a realistic
#          probability distribution of their stat outcomes.
# CONNECTS TO: math_helpers.py (sampling), projections.py (input)
# CONCEPTS COVERED: Quantum Matrix Engine 5.6 method, simulation loops,
#                   distribution building, blowout risk
# ============================================================

# Standard library imports only
import random   # For randomizing game scenarios (minutes, pace)
import math     # For mathematical rounding and calculations

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# Import our custom math helpers (built from scratch)
from engine.math_helpers import (
    sample_from_normal_distribution,  # Draw a random game result (normal)
    sample_skew_normal,               # C5: Skew-normal for right-skewed NBA stats
    get_stat_skew_param,              # C5: Default skew params by stat type
    sample_from_kde,                  # C11: KDE sampling from game logs
    should_use_kde,                   # C11: Whether to use KDE vs skew-normal
    calculate_mean,                    # Average a list of results
    calculate_standard_deviation,      # Spread of results
    calculate_percentile,              # Find value at percentile
    clamp_probability,                 # Keep probability in 0-1
    sample_poisson_like,               # Feature 8: Poisson-like for steals/blocks/turnovers
    sample_zero_inflated,              # Feature 8: Zero-inflated for threes
    estimate_zero_probability,         # Feature 8: Estimate zero prob from logs
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
    # Disruption scenarios increased to ~47% to better reflect real NBA game variance.
    # Normal reduced to 0.53, close_game to 0.06 to accommodate 3 new scenario types (1A).
    ("normal",         0.53,  0.00,  0.05,  0.97,  1.03),  # Normal game: minimal impact
    ("blowout_win",    0.13,  0.18,  0.28,  0.88,  0.93),  # Team wins big, star sits late (stricter)
    ("blowout_loss",   0.11,  0.12,  0.22,  0.86,  0.96),  # Team loses big, garbage time (stricter)
    ("foul_trouble",   0.11,  0.15,  0.30,  0.92,  1.00),  # Foul trouble limits minutes
    ("close_game",     0.06, -0.15, -0.05,  1.05,  1.15),  # Close game / OT: MORE minutes, stat boost
    ("injury_scare",   0.03,  0.40,  0.60,  0.30,  0.60),  # Injury scare: massive minutes cut
    ("shootout",       0.01, -0.05,  0.05,  1.05,  1.15),  # High-scoring shootout (1A)
    ("grind_blowout",  0.01,  0.25,  0.40,  0.75,  0.85),  # Slow-paced blowout (1A)
    ("defensive_slug", 0.01,  0.00,  0.08,  0.85,  0.93),  # Defensive low-scorer (1A)
]

# Validate scenario probabilities sum to 1.0
_SCENARIO_PROB_SUM = sum(s[1] for s in GAME_SCENARIOS)
assert abs(_SCENARIO_PROB_SUM - 1.0) < 1e-6, (
    f"GAME_SCENARIOS probabilities must sum to 1.0, got {_SCENARIO_PROB_SUM:.4f}"
)

# Spread-total matrix scenario weight overrides. (1A)
# When |spread| and total match a pattern, override base scenario weights.
# Format: {(spread_abs_threshold, total_threshold, comparison): {scenario_name: weight, ...}}
# These weights are RELATIVE (will be normalized inside _simulate_game_scenario).
_SPREAD_TOTAL_MATRIX = {
    # Tight game + high total → shootout
    "shootout_game": {
        "spread_max": 4.0,
        "total_min": 228.0,
        "weights": {
            "shootout": 0.25, "normal": 0.50, "close_game": 0.10,
            "injury_scare": 0.05, "foul_trouble": 0.05, "blowout_win": 0.025,
            "blowout_loss": 0.025,
        },
    },
    # Blowout + low total → grind blowout
    "grind_blowout_game": {
        "spread_min": 10.0,
        "total_max": 215.0,
        "weights": {
            "grind_blowout": 0.30, "blowout_win": 0.15, "blowout_loss": 0.15,
            "normal": 0.30, "injury_scare": 0.05, "foul_trouble": 0.025,
            "close_game": 0.025,
        },
    },
    # Tight game + low total → defensive slug
    "defensive_slug_game": {
        "spread_max": 4.0,
        "total_max": 215.0,
        "weights": {
            "defensive_slug": 0.20, "normal": 0.55, "foul_trouble": 0.10,
            "injury_scare": 0.05, "close_game": 0.05, "blowout_win": 0.025,
            "blowout_loss": 0.025,
        },
    },
}

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

# Player-specific hot/cold: CV ratio caps relative to the "average" CV baseline (0.35).
# Min cap prevents consistent players from having near-zero hot/cold probability.
# Max cap prevents extreme outliers from dominating the momentum model.
HOT_COLD_CV_BASELINE = 0.35        # CV reference: "average" NBA player variability
HOT_COLD_CV_RATIO_MIN = 0.5        # Minimum CV-based scaling factor
HOT_COLD_CV_RATIO_MAX = 2.0        # Maximum CV-based scaling factor
HOT_COLD_MAX_HOT_PROB  = 0.25      # Hard ceiling on player-specific hot probability
HOT_COLD_MAX_COLD_PROB = 0.20      # Hard ceiling on player-specific cold probability

# Convergence: stop early when the running probability changes by less than this
# between checkpoints.
CONVERGENCE_THRESHOLD = 0.003  # 1E: tightened from 0.005

# Convergence check interval (1E): check every 250 sims after the first 500.
CONVERGENCE_CHECK_INTERVAL = 250

# Wilson score z-value for the 90% confidence interval (P(|Z| > 1.645) ≈ 0.10)
Z_SCORE_90_CI = 1.645

# Three-point props minimum CV floor = 1.3× elite-points CV (0.25).
# Ensures three-point simulations always model adequate shooting streakiness.
# THREE_POINT_CV_FLOOR = 0.325 (32.5%)
# Rationale: NBA 3PT made has inherently high variance. League-average 3PT% is ~36%
# with a game-to-game standard deviation of roughly 30-40% of the mean.
# A CV floor of 32.5% prevents the simulation from underestimating three-point
# volatility for consistent shooters whose sample CV might be artificially low.
THREE_POINT_CV_FLOOR = 1.3 * 0.25  # = 0.325

# ============================================================
# SECTION: Minutes Simulation Constants (C8)
# Simulate player minutes per game before deriving stat output.
# Minutes follow a truncated normal distribution.
# ============================================================

# Default assumed minutes for players without explicit minutes data
DEFAULT_PROJECTED_MINUTES = 30.0

# Standard deviation of minutes (captures blowout/foul trouble variability)
MINUTES_STD_DEFAULT = 5.0   # was 4.0 — increased for more realistic variance in outcomes

# Default correlation matrix for multi-stat props (C7)
# These represent realistic stat co-dependence in NBA games.
STAT_CORRELATION = {
    ("points",   "rebounds"): 0.15,
    ("rebounds", "points"):   0.15,
    ("points",   "assists"):  0.25,
    ("assists",  "points"):   0.25,
    ("rebounds", "assists"):  0.05,
    ("assists",  "rebounds"): 0.05,
}

# Quarter-based fatigue multipliers (1B).
# Each quarter, the stat rate per minute decays slightly due to cumulative fatigue.
# Q1: full rate, Q4: 90% rate. Back-to-back games further multiply by 0.95.
QUARTER_FATIGUE_RATES = (1.00, 0.97, 0.94, 0.90)  # Q1, Q2, Q3, Q4
BACK_TO_BACK_FATIGUE_MULTIPLIER = 0.95  # Additional fatigue on back-to-back nights

# Momentum score thresholds for enhanced hot/cold detection (1D)
MOMENTUM_HOT_THRESHOLD = 0.15    # >15% above average → hot momentum
MOMENTUM_COLD_THRESHOLD = -0.15  # <-15% below average → cold momentum
MOMENTUM_HOT_CAP = 1.12          # Maximum hot streak multiplier
MOMENTUM_COLD_FLOOR = 0.88       # Minimum cold streak multiplier

# ============================================================
# END SECTION: Minutes Simulation Constants
# ============================================================

# ============================================================
# END SECTION: Module-Level Constants
# ============================================================

# SECTION: Quantum Matrix Engine 5.6 Simulation Core
# Quantum Matrix Engine 5.6 = run the same random experiment thousands of
# times and look at the overall distribution of results.
# Like flipping a coin 10,000 times to verify it's fair.
# ============================================================

def run_quantum_matrix_simulation(
    projected_stat_average,
    stat_standard_deviation,
    prop_line,
    number_of_simulations,
    blowout_risk_factor,
    pace_adjustment_factor,
    matchup_adjustment_factor,
    home_away_adjustment,
    rest_adjustment_factor,
    stat_type=None,
    projected_minutes=None,
    minutes_std=None,
    recent_game_logs=None,
    random_seed=None,
    enable_fatigue_curve=True,
    vegas_spread=None,
    game_total=None,
) -> dict:
    """
    Run a full Quantum Matrix Engine 5.6 simulation for one player's one stat.

    Simulates `number_of_simulations` games, each with randomized
    minutes (blowout risk, foul trouble) and stat variance.
    Builds a distribution and calculates P(over line).
    Default recommended simulations: 2000.

    C5: Uses skew-normal distribution sampling instead of normal,
        with stat-type-specific skew parameters (right skew for NBA).
    C8: Optionally simulates minutes first, then scales per-minute rate,
        capturing the natural correlation between minutes and stats.
    1B: Quarter-aware fatigue decay reduces effective stat rate across Q1-Q4.
    1C: Garbage time adjustment recaps star-player minutes in blowouts.

    Args:
        projected_stat_average (float): Our projected mean for the stat
        stat_standard_deviation (float): Historical variability (std dev)
        prop_line (float): The betting line to beat
        number_of_simulations (int): How many games to simulate (default 2000)
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
        stat_type (str, optional): Stat being simulated (e.g. 'threes',
            'fg3m', 'points'). Used for skew-normal param selection (C5)
            and for CV floor enforcement for three-point props.
        projected_minutes (float, optional): Projected minutes for tonight. (C8)
            When provided, enables the minutes-first simulation approach:
            each trial first draws simulated minutes, then scales the
            per-minute stat rate by those minutes.
        minutes_std (float, optional): Std dev of minutes distribution. (C8)
            Defaults to MINUTES_STD_DEFAULT (4.0) when projected_minutes
            is provided but minutes_std is not.
        recent_game_logs (list of float, optional): Player's recent game stat
            values for this stat type. (C11)
            When 15+ entries are provided, each Quantum Matrix Engine 5.6 trial samples
            from a KDE built from these logs (instead of skew-normal).
            This captures player-specific distribution shapes (e.g., a player
            who always scores 15 or 30 but never 22).
            Falls back to skew-normal when None or fewer than 15 logs.
        random_seed (int, optional): Seed for the random number generator.
            When provided, the simulation produces reproducible results
            across runs — useful for debugging and model validation.
            Defaults to None (non-deterministic / different each run).
        enable_fatigue_curve (bool): When True, applies quarter-aware fatigue
            decay (1B). Q4 stats are modestly lower than Q1. Default True.
        vegas_spread (float, optional): Vegas point spread (positive = player's
            team favored). Feeds into spread-total matrix for scenario weighting
            (1A). Defaults to None (neutral).
        game_total (float, optional): Vegas over/under total. Combined with
            vegas_spread for spread-total matrix weighting (1A).
            Defaults to None (uses 225.0 baseline).

    Returns:
        dict: Simulation results containing:
            - 'simulated_results': list of all simulated game stats
            - 'probability_over': float, P(result > line)
            - 'simulated_mean': float, average of simulated results
            - 'simulated_std': float, std dev of simulated results
            - 'percentile_10': float, 10th percentile (bad game)
            - 'percentile_50': float, median game
            - 'percentile_90': float, 90th percentile (great game)
            - 'ci_90_low': float, lower bound of 90% Wilson confidence interval
            - 'ci_90_high': float, upper bound of 90% Wilson confidence interval
            - 'simulations_run': int, actual simulations completed (may be
              fewer than requested if convergence was reached early)

    Example:
        LeBron projects 25 pts, std=6, line=24.5 →
        maybe 55-60% of simulated games go over 24.5
    """
    # Seed the RNG if requested (enables reproducible simulations)
    if random_seed is not None:
        random.seed(random_seed)

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
    # Floor at 0: a negative stat projection is physically meaningless
    adjusted_stat_projection = max(0.0, adjusted_stat_projection)

    # Adjust standard deviation slightly for extreme multipliers
    # When pace is high, variance also increases (more unpredictable)
    adjusted_standard_deviation = stat_standard_deviation * (
        1.0 + 0.1 * (combined_adjustment_multiplier - 1.0)
    )

    # Make sure std doesn't go below a minimum (always some variability)
    adjusted_standard_deviation = max(adjusted_standard_deviation, 0.5)

    # Three-point CV enforcement: threes/fg3m must have at least 1.3x the
    # elite-points CV floor (0.25) to properly model shooting streakiness.
    if stat_type in ("threes", "fg3m") and adjusted_stat_projection > 0:
        current_cv = adjusted_standard_deviation / adjusted_stat_projection
        if current_cv < THREE_POINT_CV_FLOOR:
            adjusted_standard_deviation = adjusted_stat_projection * THREE_POINT_CV_FLOOR

    # C5: Select skew parameter for this stat type
    skew_alpha = get_stat_skew_param(stat_type or "")

    # C11: Determine whether to use KDE sampling from game logs.
    # When the player has 15+ recent game logs, we sample directly from the
    # empirical distribution (KDE) instead of the parametric skew-normal.
    # The KDE logs must first be scaled to align with tonight's adjusted projection
    # so that matchup/pace/rest adjustments are still reflected.
    use_kde = should_use_kde(recent_game_logs or [])
    kde_logs_scaled = None
    if use_kde and recent_game_logs:
        raw_log_mean = sum(recent_game_logs) / len(recent_game_logs)
        if raw_log_mean > 1e-6:
            # Scale logs by the ratio (tonight's adjusted projection / log mean)
            # so that matchup/pace/rest adjustments apply to the KDE distribution too.
            scale = adjusted_stat_projection / raw_log_mean
            kde_logs_scaled = [v * scale for v in recent_game_logs]
        else:
            # Mean of 0 (or near-zero): player's recent logs are all 0 — KDE would
            # be misleading. Fall back to skew-normal for this prop.
            use_kde = False

    # C8: If projected minutes are provided, compute per-minute rate for
    # minutes-first simulation. This naturally captures the correlation
    # between minutes played and stats (blowout → low mins → low stats).
    use_minutes_sim = projected_minutes is not None and projected_minutes > 0
    if use_minutes_sim:
        eff_minutes_std = minutes_std if (minutes_std is not None) else MINUTES_STD_DEFAULT
        # Per-minute stat rate: adjusted projection / projected minutes
        stat_per_minute = adjusted_stat_projection / projected_minutes

    # ============================================================
    # END SECTION: Apply Pre-Simulation Adjustments
    # ============================================================

    # ============================================================
    # SECTION: Run Simulation Loop
    # This is the heart of Quantum Matrix Engine 5.6 — simulate many games!
    # ============================================================

    # List to store every simulated game's result
    all_simulated_game_results = []

    # Counter for games where player goes OVER the prop line
    count_of_games_over_line = 0

    # Convergence tracking variables removed — simulation always runs to completion
    # to guarantee p90 accuracy for high-ceiling alternate lines.
    simulations_completed = number_of_simulations

    # 1E: Running sum for mean+std convergence tracking
    _running_sum = 0.0
    _running_sum_sq = 0.0

    # Run the simulation `number_of_simulations` times
    # BEGINNER NOTE: range(n) creates numbers 0 to n-1
    # We don't care about the index, just need to loop n times
    for sim_index in range(number_of_simulations):

        # --- Step 1: Pick a Game Scenario (W3: Ceiling/Floor Games) ---
        # Instead of rolling blowout and foul trouble independently,
        # we now pick ONE holistic scenario that determines BOTH minutes
        # AND stats together. This models the real-world correlation:
        # e.g., a player in foul trouble in a blowout DEFINITELY sits.
        scenario_name, minutes_reduction, stat_scenario_multiplier = (
            _simulate_game_scenario(
                blowout_risk_factor,
                vegas_spread=vegas_spread,
                game_total=game_total,
            )
        )

        # minutes_reduction can be negative (close game/OT = extra minutes)
        # Cap to [-0.15, 0.60] to avoid negative or impossibly high minutes
        minutes_reduction = max(-0.15, min(0.60, minutes_reduction))
        minutes_multiplier = 1.0 - minutes_reduction

        # --- Step 2: Apply Hot Hand / Cold Game Modifier (W4: Momentum) ---
        # Player-specific hot/cold probabilities are derived from the CV of
        # recent game logs when available (high-variance players like Kyrie
        # have more hot/cold games than consistent players like Jokic).
        momentum_multiplier = _simulate_hot_cold_modifier(recent_game_logs)

        # --- Step 3: Simulate Minutes (C8) OR Use Scenario Multiplier ---
        # C8: When projected_minutes is available, simulate the player's
        # actual minutes for this game, then derive stats from per-min rate.
        # This naturally ties low-minutes games to low stat outputs.
        if use_minutes_sim:
            # Simulate tonight's minutes: sample from normal distribution
            # (minutes are roughly symmetric — small positive skew for overtime
            # games is handled by the scenario multiplier system above).
            # Using sample_from_normal_distribution (symmetric) is appropriate here.
            sim_minutes = max(
                0.0,
                min(48.0, sample_from_normal_distribution(projected_minutes, eff_minutes_std))
            )
            # Apply scenario-level minutes reduction on top
            sim_minutes *= minutes_multiplier

            # 1C: Apply garbage time adjustment for blowout scenarios
            if projected_minutes > 0:
                _is_star = projected_minutes >= 30
                _gt_minutes = _apply_garbage_time_adjustment(projected_minutes, scenario_name, _is_star)
                sim_minutes = min(sim_minutes, _gt_minutes * 1.1)  # don't exceed adjusted ceiling

            effective_mean = (
                stat_per_minute
                * sim_minutes
                * stat_scenario_multiplier
                * momentum_multiplier
            )
            # Std scales with sqrt of minutes fraction
            min_frac = sim_minutes / max(1.0, projected_minutes)
            scaled_std = adjusted_standard_deviation * math.sqrt(max(0.05, min_frac))
        else:
            # Standard approach: scale projection by minutes multiplier
            effective_mean = (
                adjusted_stat_projection
                * minutes_multiplier
                * stat_scenario_multiplier
                * momentum_multiplier
            )
            # Scale std dev proportionally (less minutes = less variance too)
            scaled_std = adjusted_standard_deviation * math.sqrt(max(0.1, minutes_multiplier))

        # --- Step 3b: Apply Quarter-Aware Fatigue Curve (1B) ---
        if enable_fatigue_curve:
            avg_fatigue = sum(QUARTER_FATIGUE_RATES) / 4
            is_back_to_back = rest_adjustment_factor < 0.97
            if is_back_to_back:
                avg_fatigue *= BACK_TO_BACK_FATIGUE_MULTIPLIER
            effective_mean *= avg_fatigue

        # --- Step 4: Draw Sample (C11: KDE when logs available, else C5: skew-normal) ---
        # Priority order:
        #   1. KDE from game logs (C11) — when player has 15+ recent games
        #      KDE is scaled by scenario/minutes multipliers for context-awareness
        #   2. Stat-specific distribution (Feature 8) — Poisson-like for low-count
        #      discrete stats; zero-inflated for three-pointers
        #   3. Skew-normal (C5) — parametric with stat-type-specific right skew
        if use_kde and kde_logs_scaled:
            # C11: Scale KDE logs by scenario/momentum multipliers, then sample
            scenario_scale = minutes_multiplier * stat_scenario_multiplier * momentum_multiplier
            kde_scaled_for_trial = [v * scenario_scale for v in kde_logs_scaled]
            kde_sample = sample_from_kde(kde_scaled_for_trial)
            if kde_sample is not None:
                simulated_game_stat = kde_sample
            else:
                # Fallback: skew-normal if KDE fails for this trial
                simulated_game_stat = sample_skew_normal(effective_mean, scaled_std, skew_alpha)
        elif stat_type in ('threes', 'fg3m'):
            # Feature 8: Zero-inflated distribution captures the "0-three games"
            # mass that neither KDE nor skew-normal handles cleanly.
            zero_prob = estimate_zero_probability(recent_game_logs or [], stat_type)
            simulated_game_stat = sample_zero_inflated(
                effective_mean, scaled_std, zero_prob, recent_game_logs or []
            )
        elif stat_type in ('steals', 'blocks', 'turnovers'):
            # Feature 8: Poisson-like discrete sampler for low-count integer stats
            simulated_game_stat = sample_poisson_like(effective_mean, recent_game_logs or [])
        else:
            # C5: Skew-normal captures the right tail of NBA stat distributions
            # (explosion games, triple-doubles, etc.) better than pure normal.
            simulated_game_stat = sample_skew_normal(effective_mean, scaled_std, skew_alpha)

        # Stats can't be negative (can't have -3 assists)
        simulated_game_stat = max(0.0, simulated_game_stat)

        # --- Step 5: Record the Result ---
        all_simulated_game_results.append(simulated_game_stat)

        # Did this simulated game go OVER the prop line?
        if simulated_game_stat > prop_line:
            count_of_games_over_line += 1

        # 1E: Track running stats for mean+std convergence
        _running_sum += simulated_game_stat
        _running_sum_sq += simulated_game_stat ** 2

    # ============================================================
    # END SECTION: Run Simulation Loop
    # ============================================================

    # ============================================================
    # SECTION: Compile Results
    # Summarize the simulation results into useful statistics
    # ============================================================

    # Raw probability = games over / total games simulated
    if simulations_completed == 0:
        raw_probability_over = 0.5
    else:
        raw_probability_over = count_of_games_over_line / simulations_completed

    # Clamp to [0.01, 0.99] — never 100% certain
    final_probability_over = clamp_probability(raw_probability_over)

    # --- Wilson Score 90% Confidence Interval ---
    # Provides a statistically sound CI around the probability estimate.
    # z = 1.645 for 90% confidence level.
    _n = simulations_completed
    _p = final_probability_over
    _z = Z_SCORE_90_CI
    _z2 = _z * _z
    if _n > 0:
        _center = (_p + _z2 / (2 * _n)) / (1 + _z2 / _n)
        _margin = _z * math.sqrt(_p * (1 - _p) / _n + _z2 / (4 * _n * _n)) / (1 + _z2 / _n)
    else:
        _center = _p
        _margin = 0.5
    ci_90_low = max(0.0, _center - _margin)
    ci_90_high = min(1.0, _center + _margin)

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
        "ci_90_low": round(ci_90_low, 4),
        "ci_90_high": round(ci_90_high, 4),
        "simulations_run": simulations_completed,
    }

    return simulation_results

    # ============================================================
    # END SECTION: Compile Results
    # ============================================================


# ============================================================
# SECTION: Alt-Line Probability Generation (Goblin & Demon)
# Generates alternate lines from a base prop line and evaluates
# win probabilities for each using the existing simulation output.
# ============================================================

# Goblin offsets: subtracted from the base line (lowered thresholds)
GOBLIN_OFFSETS = [-1.0, -2.0, -3.0]
# Demon offsets: added to the base line (raised thresholds)
DEMON_OFFSETS = [2.0, 4.0, 6.0]


def generate_alt_line_probabilities(simulation_output, base_line):
    """
    Generate alternate-line (Goblin & Demon) probabilities from simulation
    output and a base prop line.

    Uses the raw simulated results to compute:
      - 3 Goblin lines (L-1, L-2, L-3): P(stat >= goblin_line)
      - 1 Base line: P(stat > base_line)  [standard over probability]
      - 3 Demon lines (L+2, L+4, L+6): P(stat <= demon_line)

    Args:
        simulation_output (dict): The output dict from
            ``run_quantum_matrix_simulation``, which must contain
            ``simulated_results`` (list of float) and ``probability_over``.
        base_line (float): The primary sportsbook prop line.

    Returns:
        dict: {
            'base_line': float,
            'base_probability': float,
            'goblin_lines': [
                {'line': float, 'offset': float, 'probability': float, 'type': 'goblin'},
                ...
            ],
            'demon_lines': [
                {'line': float, 'offset': float, 'probability': float, 'type': 'demon'},
                ...
            ],
            'best_alt': {
                'line': float, 'probability': float, 'type': 'goblin'|'demon'|'base',
                'prediction': str
            },
        }
    """
    simulated_results = simulation_output.get("simulated_results", [])
    n = len(simulated_results)
    base_prob = simulation_output.get("probability_over", 0.5)

    if n == 0:
        # No simulation data — return empty structure
        return {
            "base_line": base_line,
            "base_probability": base_prob,
            "goblin_lines": [],
            "demon_lines": [],
            "best_alt": {
                "line": base_line,
                "probability": base_prob,
                "type": "base",
                "prediction": "",
            },
        }

    # --- Goblin lines: P(stat >= goblin_line) ---
    goblin_lines = []
    for offset in GOBLIN_OFFSETS:
        g_line = round(base_line + offset, 1)  # offset is negative
        if g_line < 0:
            # NBA prop lines use half-point increments; 0.5 is the lowest
            # meaningful threshold (a player must record at least 1 stat).
            g_line = 0.5
        count_gte = sum(1 for s in simulated_results if s >= g_line)
        prob = count_gte / n
        prob = max(0.01, min(0.99, prob))
        goblin_lines.append({
            "line": g_line,
            "offset": offset,
            "probability": round(prob, 4),
            "type": "goblin",
        })

    # --- Demon lines: P(stat <= demon_line) ---
    demon_lines = []
    for offset in DEMON_OFFSETS:
        d_line = round(base_line + offset, 1)  # offset is positive
        count_lte = sum(1 for s in simulated_results if s <= d_line)
        prob = count_lte / n
        prob = max(0.01, min(0.99, prob))
        demon_lines.append({
            "line": d_line,
            "offset": offset,
            "probability": round(prob, 4),
            "type": "demon",
        })

    # --- Find the best alt-line play (highest probability) ---
    all_candidates = []
    all_candidates.append({
        "line": base_line,
        "probability": base_prob,
        "type": "base",
    })
    for g in goblin_lines:
        all_candidates.append(g)
    for d in demon_lines:
        all_candidates.append(d)

    best = max(all_candidates, key=lambda c: c["probability"])
    best_alt = {
        "line": best["line"],
        "probability": best["probability"],
        "type": best["type"],
        "prediction": format_alt_line_prediction(best["line"], best["type"]),
    }

    return {
        "base_line": base_line,
        "base_probability": round(base_prob, 4),
        "goblin_lines": goblin_lines,
        "demon_lines": demon_lines,
        "best_alt": best_alt,
    }


def format_alt_line_prediction(line, bet_type):
    """
    Generate the strict natural-language prediction string for an alt-line.

    Args:
        line (float): The alternate line value.
        bet_type (str): 'goblin', 'demon', or 'base'.

    Returns:
        str: The prediction string.
              Goblin → "I predict the stat will do at LEAST {line}"
              Demon  → "I predict the stat will do at MOST {line}"
              Base   → "" (empty — no prediction for the standard line)
    """
    if bet_type == "goblin":
        return f"I predict the stat will do at LEAST {line}"
    elif bet_type == "demon":
        return f"I predict the stat will do at MOST {line}"
    return ""

# ============================================================
# END SECTION: Alt-Line Probability Generation
# ============================================================


import warnings as _warnings


def run_monte_carlo_simulation(*args, **kwargs):
    """
    DEPRECATED: Use ``run_quantum_matrix_simulation`` directly.

    This backward-compatibility wrapper logs a deprecation warning and
    delegates to ``run_quantum_matrix_simulation``.  It will be removed
    in a future release.
    """
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "run_monte_carlo_simulation is deprecated; "
        "call run_quantum_matrix_simulation directly."
    )
    return run_quantum_matrix_simulation(*args, **kwargs)


# ============================================================
# SECTION: Helper Functions for Game Scenario Randomization
# These internal helpers simulate realistic game situations
# like blowouts and foul trouble.
# ============================================================

def _simulate_game_scenario(blowout_risk_factor, vegas_spread=0.0, game_total=225.0):
    """
    Pick a holistic game scenario for this simulated game. (W3)

    Replaces the old independent blowout + foul trouble rolls with
    a single scenario that applies CORRELATED effects on both
    minutes and stats. The blowout scenarios are scaled by the
    incoming `blowout_risk_factor` so high-spread games still
    get more blowout weight.

    When vegas_spread and game_total are provided, the spread-total
    matrix (1A) may override the base scenario weights with context-
    specific distributions (e.g., tight game + high total → shootout).

    Args:
        blowout_risk_factor (float): 0.0-1.0 blowout probability
            from projections.py. Higher → more weight on blowout
            scenarios, less on normal game.
        vegas_spread (float): Vegas point spread; abs value used for matrix.
            Defaults to 0.0 (neutral/unknown).
        game_total (float): Vegas over/under; used for matrix matching.
            Defaults to 225.0 (league-average total).

    Returns:
        tuple: (scenario_name: str,
                minutes_reduction: float,   # fraction of mins lost (negative = gained)
                stat_multiplier: float)     # additional stat modifier
    """
    # Check spread-total matrix for context-specific scenario weighting (1A)
    # Thresholds are read directly from _SPREAD_TOTAL_MATRIX (single source of truth).
    abs_spread = abs(vegas_spread or 0.0)
    gt = game_total or 225.0

    matrix_weights = None
    _sg = _SPREAD_TOTAL_MATRIX["shootout_game"]
    _gb = _SPREAD_TOTAL_MATRIX["grind_blowout_game"]
    _ds = _SPREAD_TOTAL_MATRIX["defensive_slug_game"]
    if abs_spread < _sg["spread_max"] and gt > _sg["total_min"]:
        matrix_weights = _sg["weights"]
    elif abs_spread > _gb["spread_min"] and gt < _gb["total_max"]:
        matrix_weights = _gb["weights"]
    elif abs_spread < _ds["spread_max"] and gt < _ds["total_max"]:
        matrix_weights = _ds["weights"]

    if matrix_weights is not None:
        # Use matrix-specific weights (bypass blowout_extra logic)
        adjusted_scenarios = []
        for name, prob, min_red_lo, min_red_hi, stat_lo, stat_hi in GAME_SCENARIOS:
            w = matrix_weights.get(name, 0.0)
            adjusted_scenarios.append((name, w, min_red_lo, min_red_hi, stat_lo, stat_hi))
        total_weight = sum(s[1] for s in adjusted_scenarios)
        _use_matrix = total_weight >= 1e-9
        if _use_matrix:
            roll = random.random() * total_weight
            cumulative = 0.0
            for name, prob, min_red_lo, min_red_hi, stat_lo, stat_hi in adjusted_scenarios:
                cumulative += prob
                if roll <= cumulative:
                    minutes_reduction = random.uniform(min_red_lo, min_red_hi)
                    stat_multiplier = random.uniform(stat_lo, stat_hi)
                    return name, minutes_reduction, stat_multiplier
            # Floating-point guard: return 'normal' params from GAME_SCENARIOS
            _normal = next((s for s in GAME_SCENARIOS if s[0] == "normal"), None)
            if _normal:
                return "normal", random.uniform(_normal[2], _normal[3]), random.uniform(_normal[4], _normal[5])
            return "normal", random.uniform(0.0, 0.05), random.uniform(0.97, 1.03)

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


def _simulate_hot_cold_modifier(recent_game_logs=None):
    """
    Apply a "hot hand" or "cold game" multiplier to the stat mean. (W4 / 1D)

    In real NBA games, players have momentum nights (three-point
    streaks, every shot dropping) and ice-cold nights. This creates
    a distribution with FATTER TAILS than a pure normal, which is
    especially important for streaky stats like threes.

    Enhanced (1D): When 5+ recent game logs AND season_avg context
    are available, uses a weighted momentum score from the last 3
    games (50/30/20 weights) to detect genuine hot/cold streaks
    instead of purely random rolls.

    When recent_game_logs are provided, the hot/cold probabilities are
    scaled by the player's coefficient of variation (CV = std / mean)
    so high-variance players (e.g. Kyrie Irving) have larger hot/cold
    swings than consistent players (e.g. Nikola Jokic).

    Args:
        recent_game_logs (list of float, optional): Player's recent stat
            values. Used to compute player-specific hot/cold frequencies
            and momentum score. Falls back to module-level constants
            when not provided.

    Returns:
        float: Multiplier near 1.0 (hot → up to 1.12, cold → down to 0.88)
    """
    # 1D: Enhanced momentum detection when 5+ logs available
    # (len >= 5 guarantees last3 always has exactly 3 entries)
    if recent_game_logs and len(recent_game_logs) >= 5:
        _mean_all = sum(recent_game_logs) / len(recent_game_logs)
        if _mean_all > 1e-6:
            # Weighted average of last 3 games: 50%, 30%, 20% (most-recent first)
            last3 = recent_game_logs[-3:]  # always exactly 3 items given len >= 5
            _weights = (0.20, 0.30, 0.50)  # oldest→newest: 20%, 30%, 50%
            _wsum = sum(w * v for w, v in zip(_weights, last3))
            _weighted_recent = _wsum  # weights already sum to 1.0
            momentum = (_weighted_recent - _mean_all) / _mean_all
            if momentum > MOMENTUM_HOT_THRESHOLD:
                return min(MOMENTUM_HOT_CAP, 1.0 + momentum * 0.3)
            if momentum < MOMENTUM_COLD_THRESHOLD:
                return max(MOMENTUM_COLD_FLOOR, 1.0 + momentum * 0.3)
            # Near-average momentum: fall through to CV-based random behavior

    # CV-based player-specific hot/cold probabilities (W4 original logic)
    hot_prob  = HOT_HAND_PROBABILITY   # default 0.15
    cold_prob = COLD_GAME_PROBABILITY  # default 0.10
    if recent_game_logs and len(recent_game_logs) >= 5:
        _mean = sum(recent_game_logs) / len(recent_game_logs)
        if _mean > 1e-6:
            _variance = sum((x - _mean) ** 2 for x in recent_game_logs) / len(recent_game_logs)
            _std = _variance ** 0.5
            _cv = _std / _mean
            # Scale probabilities by CV relative to an "average" CV baseline.
            # CV > baseline → more volatile player → higher hot/cold chance.
            # CV < baseline → more consistent player → lower hot/cold chance.
            _cv_ratio = _cv / HOT_COLD_CV_BASELINE
            _cv_ratio = max(HOT_COLD_CV_RATIO_MIN, min(HOT_COLD_CV_RATIO_MAX, _cv_ratio))
            hot_prob  = min(HOT_COLD_MAX_HOT_PROB,  HOT_HAND_PROBABILITY  * _cv_ratio)
            cold_prob = min(HOT_COLD_MAX_COLD_PROB, COLD_GAME_PROBABILITY * _cv_ratio)

    roll = random.random()

    if roll < hot_prob:
        # "On fire" game — player is in a rhythm
        return random.uniform(HOT_HAND_MULTIPLIER_MIN, HOT_HAND_MULTIPLIER_MAX)
    elif roll < hot_prob + cold_prob:
        # "Ice cold" game — nothing going in
        return random.uniform(COLD_GAME_MULTIPLIER_MIN, COLD_GAME_MULTIPLIER_MAX)
    else:
        # Typical game — no hot/cold modifier
        return 1.0


def _apply_garbage_time_adjustment(projected_minutes, scenario_name, is_star_player):
    """
    Adjust projected minutes for garbage time effects in blowout scenarios. (1C)

    In blowout games, star players are rested in Q4 (garbage time),
    while bench players get extended minutes. This function returns
    the adjusted minutes.

    BEGINNER NOTE: "Garbage time" is when the game is decided and
    coaches rest their starters, giving bench players more playing time.
    Stars on winning teams lose minutes; bench players gain minutes.

    Args:
        projected_minutes (float): Player's normal projected minutes
        scenario_name (str): Current game scenario name
        is_star_player (bool): True when projected_minutes >= 30

    Returns:
        float: Adjusted projected minutes

    Example:
        Star player (34 min) in blowout_win → Q4 garbage time reduces by ~70%
        → adjusted ≈ 34 * (1 - 0.70 * 0.25) ≈ 28 minutes
    """
    _BLOWOUT_SCENARIOS = {"blowout_win", "blowout_loss", "grind_blowout"}
    if scenario_name not in _BLOWOUT_SCENARIOS:
        return projected_minutes  # No adjustment for non-blowout scenarios

    if is_star_player:
        # Q4 garbage time: reduce Q4 minutes by 60-80%
        # Q4 is 25% of the game (12 of 48 minutes)
        q4_reduction_pct = random.uniform(0.60, 0.80)
        adjusted = projected_minutes * (1.0 - q4_reduction_pct * 0.25)
    else:
        # Bench player: gets a 30-50% minutes BOOST in garbage time Q4
        q4_boost_pct = random.uniform(0.30, 0.50)
        adjusted = projected_minutes * (1.0 + q4_boost_pct * 0.25)

    return max(0.0, min(48.0, adjusted))


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


def build_histogram_from_results(simulated_results, prop_line, number_of_buckets=20) -> dict:
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

    # Guard: ensure number_of_buckets is at least 1 to prevent ZeroDivisionError
    number_of_buckets = max(1, int(number_of_buckets))

    # Find the range of results (min to max)
    minimum_result = min(simulated_results)
    maximum_result = max(simulated_results)

    # Calculate the width of each histogram bucket
    # BEGINNER NOTE: We divide the range into equal-width buckets
    total_range = maximum_result - minimum_result
    if total_range == 0:
        # All simulations returned the same value (zero variance).
        # Return a single bucket so callers always receive a non-empty histogram.
        return [{
            "bucket_label": f"{minimum_result:.1f}",
            "bucket_start": minimum_result - 0.5,
            "bucket_end": minimum_result + 0.5,
            "count": len(simulated_results),
            "is_over_line": minimum_result > prop_line,
        }]

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
# These extend the Quantum Matrix Engine 5.6 to handle multi-stat
# props (Pts+Rebs, PRA, etc.) and fantasy score props.
# ============================================================

def _cholesky_2x2(corr):
    """
    Compute the 2×2 lower Cholesky factor for a correlation matrix
    with off-diagonal element `corr`.

    For a 2×2 matrix [[1, r], [r, 1]], the Cholesky factor L satisfies
    L @ L.T = [[1, r], [r, 1]]:
        L = [[1, 0], [r, sqrt(1-r^2)]]

    Args:
        corr (float): Correlation coefficient (-1 to 1)

    Returns:
        tuple: (l00, l10, l11) representing the non-zero Cholesky entries
    """
    corr = max(-0.99, min(0.99, corr))
    return (1.0, corr, math.sqrt(max(0.0, 1.0 - corr * corr)))


def _sample_correlated_pair(mean1, std1, mean2, std2, corr, skew1=0.0, skew2=0.0):
    """
    Draw a correlated pair of random samples using Cholesky decomposition. (C7)

    Generates two correlated standard normals via:
        z1 = u1
        z2 = corr * u1 + sqrt(1 - corr^2) * u2

    Then scales each to (mean, std) and applies skew via sample_skew_normal.

    Args:
        mean1, std1 (float): Parameters for stat 1
        mean2, std2 (float): Parameters for stat 2
        corr (float): Desired Pearson correlation between the two samples
        skew1, skew2 (float): Skew parameters for each stat

    Returns:
        tuple: (sample1, sample2), both clamped to ≥ 0.0
    """
    l00, l10, l11 = _cholesky_2x2(corr)

    # Two independent standard normals
    u1 = random.gauss(0.0, 1.0)
    u2 = random.gauss(0.0, 1.0)

    # Correlated standard normals
    z1 = l00 * u1
    z2 = l10 * u1 + l11 * u2

    # Scale correlated normals and apply skew via the canonical implementation
    # in math_helpers.sample_skew_normal (avoids duplicate transformation logic).
    # We achieve correlation by pre-computing correlated z-scores and then
    # feeding them as "pre-standardized" noise into a mean-shift approach.
    skew_delta1 = skew1 / math.sqrt(1.0 + skew1 * skew1) if abs(skew1) > 1e-9 else 0.0
    skew_delta2 = skew2 / math.sqrt(1.0 + skew2 * skew2) if abs(skew2) > 1e-9 else 0.0
    shift1 = skew_delta1 * math.sqrt(2.0 / math.pi)
    shift2 = skew_delta2 * math.sqrt(2.0 / math.pi)

    s1 = max(0.0, mean1 + std1 * (z1 - shift1))
    s2 = max(0.0, mean2 + std2 * (z2 - shift2))
    return s1, s2


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
    random_seed=None,
):
    """
    Run a correlated Quantum Matrix Engine 5.6 simulation for a combo stat prop. (C7)

    Combo stats (Pts+Rebs, PRA, etc.) share a minutes factor AND a
    stat-correlation structure — points and assists are positively correlated,
    rebounds are weakly correlated with both. This function uses Cholesky
    decomposition to generate correlated samples, replacing the previous
    approach of summing independently simulated stats.

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
        random_seed (int, optional): Seed for reproducible results.
            When provided, the simulation produces the same output
            on every run — useful for debugging and validation.

    Returns:
        dict: Same structure as run_quantum_matrix_simulation()
    """
    # Seed the RNG if requested (enables reproducible simulations)
    if random_seed is not None:
        random.seed(random_seed)
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

    stat_keys = list(adjusted.keys())
    all_combo_results = []
    count_over = 0

    for _ in range(number_of_simulations):
        # Shared minutes multiplier (correlated across all components via scenario)
        scenario_name, minutes_reduction, stat_multiplier = _simulate_game_scenario(
            blowout_risk_factor
        )
        minutes_reduction = max(-0.15, min(0.60, minutes_reduction))
        minutes_mult = 1.0 - minutes_reduction
        momentum = _simulate_hot_cold_modifier()

        # Simulate all component stats with inter-stat correlations (C7)
        # For n>2 stats we approximate by sampling each stat pair-wise
        # against the first stat (points, or the first key) for efficiency.
        sim_values = {}

        if len(stat_keys) >= 2:
            # For each stat after the first, use Cholesky to correlate it
            # with the preceding stat in the list.
            anchor_key = stat_keys[0]
            anchor_mean = adjusted[anchor_key] * minutes_mult * stat_multiplier * momentum
            anchor_std = adjusted_stds.get(anchor_key, anchor_mean * 0.35) * math.sqrt(max(0.1, minutes_mult))
            anchor_skew = get_stat_skew_param(anchor_key)

            # Sample the anchor stat first
            anchor_val = sample_skew_normal(anchor_mean, anchor_std, anchor_skew)
            sim_values[anchor_key] = max(0.0, anchor_val)

            for k in stat_keys[1:]:
                corr = STAT_CORRELATION.get((anchor_key, k), 0.0)
                k_mean = adjusted[k] * minutes_mult * stat_multiplier * momentum
                k_std = adjusted_stds.get(k, k_mean * 0.35) * math.sqrt(max(0.1, minutes_mult))
                k_skew = get_stat_skew_param(k)

                if abs(corr) > 0.01:
                    # Use Cholesky correlated sampling
                    _, k_val = _sample_correlated_pair(
                        anchor_mean, anchor_std,
                        k_mean, k_std,
                        corr, anchor_skew, k_skew,
                    )
                    sim_values[k] = max(0.0, k_val)
                else:
                    sim_values[k] = max(0.0, sample_skew_normal(k_mean, k_std, k_skew))
        else:
            # Single component
            for k in stat_keys:
                proj = adjusted[k] * minutes_mult * stat_multiplier * momentum
                std = adjusted_stds.get(k, proj * 0.35) * math.sqrt(max(0.1, minutes_mult))
                sim_values[k] = max(0.0, sample_skew_normal(proj, std, get_stat_skew_param(k)))

        combo_value = sum(sim_values.values())
        all_combo_results.append(combo_value)
        if combo_value > prop_line:
            count_over += 1

    raw_prob_over = count_over / number_of_simulations if number_of_simulations > 0 else 0.5
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
    random_seed=None,
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
        random_seed (int, optional): Seed for reproducible results.
            When provided, the simulation produces the same output
            on every run — useful for debugging and validation.

    Returns:
        dict: Same structure as run_quantum_matrix_simulation()
    """
    # Seed the RNG if requested (enables reproducible simulations)
    if random_seed is not None:
        random.seed(random_seed)
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
        total_reduction = min(0.25, (blowout_reduction * 0.6) + (foul_reduction * 0.6))
        minutes_mult = 1.0 - total_reduction

        fantasy_val = 0.0
        for stat_key, multiplier in fantasy_formula.items():
            proj = adjusted.get(stat_key, 0.0)
            std = adjusted_stds.get(stat_key, proj * 0.35)
            scaled_proj = proj * minutes_mult
            scaled_std = std * math.sqrt(minutes_mult)
            # C5: use skew-normal for better tail modeling
            sim_val = max(0.0, sample_skew_normal(scaled_proj, scaled_std, get_stat_skew_param(stat_key)))
            fantasy_val += sim_val * multiplier

        all_fantasy_results.append(fantasy_val)
        if fantasy_val > prop_line:
            count_over += 1

    raw_prob_over = count_over / number_of_simulations if number_of_simulations > 0 else 0.5
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
    random_seed=None,
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
        random_seed (int, optional): Seed for reproducible results.
            When provided, the simulation produces the same output
            on every run — useful for debugging and validation.

    Returns:
        dict: Simulation results where probability_over = P(double-double).
              The "simulated_results" are 0.0/1.0 indicators.
    """
    # Seed the RNG if requested (enables reproducible simulations)
    if random_seed is not None:
        random.seed(random_seed)
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
        total_reduction = min(0.25, (blowout_reduction * 0.6) + (foul_reduction * 0.6))
        minutes_mult = 1.0 - total_reduction

        stats_at_10_plus = 0
        for stat_key, proj in adjusted.items():
            std = adjusted_stds.get(stat_key, proj * 0.35)
            scaled_proj = proj * minutes_mult
            scaled_std = std * math.sqrt(minutes_mult)
            # C5: use skew-normal for better tail modeling
            sim_val = max(0.0, sample_skew_normal(scaled_proj, scaled_std, get_stat_skew_param(stat_key)))
            if sim_val >= DOUBLE_DOUBLE_THRESHOLD:
                stats_at_10_plus += 1

        hit = 1.0 if stats_at_10_plus >= 2 else 0.0
        all_results.append(hit)
        if hit:
            count_double_double += 1

    raw_prob = count_double_double / number_of_simulations if number_of_simulations > 0 else 0.5
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
    random_seed=None,
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
        random_seed (int, optional): Seed for reproducible results.
            When provided, the simulation produces the same output
            on every run — useful for debugging and validation.

    Returns:
        dict: Simulation results where probability_over = P(triple-double).
    """
    # Seed the RNG if requested (enables reproducible simulations)
    if random_seed is not None:
        random.seed(random_seed)
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
        total_reduction = min(0.25, (blowout_reduction * 0.6) + (foul_reduction * 0.6))
        minutes_mult = 1.0 - total_reduction

        stats_at_10_plus = 0
        for stat_key, proj in adjusted.items():
            std = adjusted_stds.get(stat_key, proj * 0.35)
            scaled_proj = proj * minutes_mult
            scaled_std = std * math.sqrt(minutes_mult)
            # C5: use skew-normal for better tail modeling
            sim_val = max(0.0, sample_skew_normal(scaled_proj, scaled_std, get_stat_skew_param(stat_key)))
            if sim_val >= TRIPLE_DOUBLE_THRESHOLD:
                stats_at_10_plus += 1

        hit = 1.0 if stats_at_10_plus >= 3 else 0.0
        all_results.append(hit)
        if hit:
            count_triple_double += 1

    raw_prob = count_triple_double / number_of_simulations if number_of_simulations > 0 else 0.5
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


def run_enhanced_simulation(
    projected_stat_average,
    stat_standard_deviation,
    prop_line,
    number_of_simulations=2000,
    blowout_risk_factor=0.15,
    pace_adjustment_factor=1.0,
    matchup_adjustment_factor=1.0,
    home_away_adjustment=0.0,
    rest_adjustment_factor=1.0,
    stat_type=None,
    projected_minutes=None,
    minutes_std=None,
    recent_game_logs=None,
    random_seed=None,
    vegas_spread=None,
    game_total=None,
) -> dict:
    """
    Run an enhanced simulation blending QME and game-script results. (1F)

    Convenience wrapper that enables all new features and blends
    Quantum Matrix Engine results with game-script simulation (if available).
    Uses 70% QME weight + 30% game-script weight.

    BEGINNER NOTE: This is the recommended entry point for Neural Analysis.
    It uses every enhancement: fatigue curves, garbage time, momentum,
    spread-total matrix, and game-script blending.

    Args:
        projected_stat_average (float): Projected mean for the stat
        stat_standard_deviation (float): Historical variability (std dev)
        prop_line (float): The betting line to beat
        number_of_simulations (int): Simulations to run (default 2000)
        blowout_risk_factor (float): 0.0-1.0 blowout probability
        pace_adjustment_factor (float): Game pace multiplier
        matchup_adjustment_factor (float): Opponent defense multiplier
        home_away_adjustment (float): Home/away additive adjustment
        rest_adjustment_factor (float): Rest/fatigue multiplier
        stat_type (str, optional): Stat type for distribution selection
        projected_minutes (float, optional): Tonight's projected minutes
        minutes_std (float, optional): Std dev of minutes
        recent_game_logs (list of float, optional): Recent game stat values
        random_seed (int, optional): Seed for reproducible results
        vegas_spread (float, optional): Vegas point spread (positive = player's
            team is favored). Used for spread-total matrix weighting.
        game_total (float, optional): Vegas over/under total. Used for
            spread-total matrix weighting.

    Returns:
        dict: Same structure as run_quantum_matrix_simulation() plus:
            - 'qme_probability': float, QME-only probability
            - 'game_script_probability': float or None
            - 'blend_method': str, describes the blending approach used

    Example:
        result = run_enhanced_simulation(25.0, 6.0, 24.5,
                     vegas_spread=3.5, game_total=231.0)
        # Returns blended probability from QME + game-script
    """
    # Run the full QME simulation with all enhancements
    qme_result = run_quantum_matrix_simulation(
        projected_stat_average=projected_stat_average,
        stat_standard_deviation=stat_standard_deviation,
        prop_line=prop_line,
        number_of_simulations=number_of_simulations,
        blowout_risk_factor=blowout_risk_factor,
        pace_adjustment_factor=pace_adjustment_factor,
        matchup_adjustment_factor=matchup_adjustment_factor,
        home_away_adjustment=home_away_adjustment,
        rest_adjustment_factor=rest_adjustment_factor,
        stat_type=stat_type,
        projected_minutes=projected_minutes,
        minutes_std=minutes_std,
        recent_game_logs=recent_game_logs,
        random_seed=random_seed,
        enable_fatigue_curve=True,
        vegas_spread=vegas_spread,
        game_total=game_total,
    )
    qme_prob = qme_result["probability_over"]

    # Try to blend with game-script simulation
    game_script_prob = None
    blend_method = "qme_only"
    blended_prob = qme_prob

    try:
        from engine.game_script import simulate_game_script, blend_with_flat_simulation
        player_projection = {
            "projected_stat": projected_stat_average,
            "stat_std": stat_standard_deviation,
            "prop_line": prop_line,
            "stat_type": stat_type or "points",
            "projected_minutes": projected_minutes or 30.0,
        }
        game_context = {
            "blowout_risk": blowout_risk_factor,
            "pace_factor": pace_adjustment_factor,
            "is_home": home_away_adjustment >= 0,
            "rest_days": 1 if rest_adjustment_factor >= 0.97 else 0,
            "vegas_spread": vegas_spread or 0.0,
            "game_total": game_total or 225.0,
        }
        gs_result = simulate_game_script(
            player_projection, game_context,
            num_simulations=min(500, number_of_simulations // 4)
        )
        if gs_result and "probability_over" in gs_result:
            game_script_prob = gs_result["probability_over"]
            # Blend: 70% QME + 30% game-script
            blended_prob = blend_with_flat_simulation(
                gs_result, qme_result, blend_weight=0.30
            )
            if isinstance(blended_prob, dict):
                blended_prob = blended_prob.get("probability_over", qme_prob)
            blend_method = "qme_70_gamescript_30"
    except Exception as _exc:
        _logger.warning(f"[Simulation] Game script unavailable, using QME only: {_exc}")

    blended_prob = clamp_probability(float(blended_prob))

    result = dict(qme_result)
    result["probability_over"] = blended_prob
    result["qme_probability"] = qme_prob
    result["game_script_probability"] = game_script_prob
    result["blend_method"] = blend_method
    return result


# ============================================================
# SECTION: Sensitivity Analysis
# ============================================================

def run_sensitivity_analysis(
    projected_stat_average: float,
    stat_standard_deviation: float,
    prop_line: float,
    number_of_simulations: int,
    blowout_risk_factor: float,
    pace_adjustment_factor: float,
    matchup_adjustment_factor: float,
    home_away_adjustment: float,
    rest_adjustment_factor: float,
    stat_type: str = None,
    projected_minutes: float = None,
    blowout_delta: float = 0.10,
    pace_delta: float = 0.05,
    matchup_delta: float = 0.05,
) -> dict:
    """
    Run sensitivity analysis by varying key parameters ±delta and reporting
    how the over-probability changes.

    For each parameter varied, three simulations are run:
      - base: the parameter at its original value
      - low:  the parameter reduced by delta
      - high: the parameter increased by delta

    Args:
        projected_stat_average: Player season average for the stat.
        stat_standard_deviation: Standard deviation of stat across games.
        prop_line: The betting line (over/under threshold).
        number_of_simulations: Number of Monte Carlo iterations per run.
        blowout_risk_factor: Base blowout risk (0–1).
        pace_adjustment_factor: Base pace multiplier.
        matchup_adjustment_factor: Base matchup multiplier.
        home_away_adjustment: Home/away adjustment factor.
        rest_adjustment_factor: Rest days adjustment factor.
        stat_type: Optional stat type string (e.g. 'points').
        projected_minutes: Optional projected minutes.
        blowout_delta: Fractional delta for blowout risk (default ±0.10).
        pace_delta: Fractional delta for pace (default ±0.05).
        matchup_delta: Fractional delta for matchup (default ±0.05).

    Returns:
        dict: Sensitivity results with structure::

            {
                "base_probability": float,
                "parameters": {
                    "blowout_risk": {
                        "base": float,
                        "low":  {"value": float, "probability": float, "delta_pct": float},
                        "high": {"value": float, "probability": float, "delta_pct": float},
                    },
                    "pace": { ... },
                    "matchup": { ... },
                },
            }
    """
    _base_kwargs = dict(
        projected_stat_average=projected_stat_average,
        stat_standard_deviation=stat_standard_deviation,
        prop_line=prop_line,
        number_of_simulations=number_of_simulations,
        blowout_risk_factor=blowout_risk_factor,
        pace_adjustment_factor=pace_adjustment_factor,
        matchup_adjustment_factor=matchup_adjustment_factor,
        home_away_adjustment=home_away_adjustment,
        rest_adjustment_factor=rest_adjustment_factor,
        stat_type=stat_type,
        projected_minutes=projected_minutes,
        random_seed=42,
    )

    base_result = run_quantum_matrix_simulation(**_base_kwargs)
    base_prob = base_result.get("probability_over", 0.5)

    def _vary(param_name, base_val, delta):
        low_val  = max(0.0, base_val - delta)
        high_val = base_val + delta
        low_kwargs  = dict(_base_kwargs); low_kwargs[param_name]  = low_val
        high_kwargs = dict(_base_kwargs); high_kwargs[param_name] = high_val
        low_prob  = run_quantum_matrix_simulation(**low_kwargs).get("probability_over", base_prob)
        high_prob = run_quantum_matrix_simulation(**high_kwargs).get("probability_over", base_prob)
        return {
            "base": base_val,
            "low":  {"value": low_val,  "probability": round(low_prob, 4),
                     "delta_pct": round((low_prob  - base_prob) * 100, 2)},
            "high": {"value": high_val, "probability": round(high_prob, 4),
                     "delta_pct": round((high_prob - base_prob) * 100, 2)},
        }

    return {
        "base_probability": round(base_prob, 4),
        "parameters": {
            "blowout_risk": _vary("blowout_risk_factor",        blowout_risk_factor,        blowout_delta),
            "pace":         _vary("pace_adjustment_factor",     pace_adjustment_factor,     pace_delta),
            "matchup":      _vary("matchup_adjustment_factor",  matchup_adjustment_factor,  matchup_delta),
        },
    }

# ============================================================
# END SECTION: Sensitivity Analysis
# ============================================================
