# ============================================================
# FILE: engine/simulation/__init__.py
# PURPOSE: Backward-compatible re-exports for the simulation package.
#
#          The original engine/simulation.py monolith (2,134 lines) has been
#          converted into a package.  All public names are re-exported here
#          so that existing imports continue to work unchanged:
#
#              from engine.simulation import run_quantum_matrix_simulation
#              from engine.simulation import simulate_combo_stat
#              etc.
#
#          Internal sub-modules:
#              _monolith.py  — original code (to be split further)
# ============================================================

# Re-export everything from the monolith so existing imports work
from engine.simulation._monolith import (
    # Module-level constants
    FOUL_TROUBLE_PROBABILITY,
    GAME_SCENARIOS,
    HOT_HAND_PROBABILITY,
    HOT_HAND_MULTIPLIER_MIN,
    HOT_HAND_MULTIPLIER_MAX,
    COLD_GAME_PROBABILITY,
    COLD_GAME_MULTIPLIER_MIN,
    COLD_GAME_MULTIPLIER_MAX,
    HOT_COLD_CV_BASELINE,
    HOT_COLD_CV_RATIO_MIN,
    HOT_COLD_CV_RATIO_MAX,
    HOT_COLD_MAX_HOT_PROB,
    HOT_COLD_MAX_COLD_PROB,
    CONVERGENCE_THRESHOLD,
    CONVERGENCE_CHECK_INTERVAL,
    Z_SCORE_90_CI,
    THREE_POINT_CV_FLOOR,
    DEFAULT_PROJECTED_MINUTES,
    MINUTES_STD_DEFAULT,
    STAT_CORRELATION,
    QUARTER_FATIGUE_RATES,
    BACK_TO_BACK_FATIGUE_MULTIPLIER,
    MOMENTUM_HOT_THRESHOLD,
    MOMENTUM_COLD_THRESHOLD,
    MOMENTUM_HOT_CAP,
    MOMENTUM_COLD_FLOOR,
    # Core QME function
    run_quantum_matrix_simulation,
    # Alt-line / histogram helpers
    generate_alt_line_probabilities,
    run_monte_carlo_simulation,
    build_histogram_from_results,
    # Combo / fantasy / binary simulations
    simulate_combo_stat,
    simulate_fantasy_score,
    simulate_double_double,
    simulate_triple_double,
    # Enhanced simulation (blended QME + game-script)
    run_enhanced_simulation,
    # Sensitivity analysis
    run_sensitivity_analysis,
    # Advanced stats enrichment
    enrich_simulation_with_advanced_stats,
)

# Also expose internal helpers that some modules import directly
from engine.simulation._monolith import (
    _simulate_game_scenario,
    _simulate_hot_cold_modifier,
    _simulate_blowout_minutes_reduction,
    _simulate_foul_trouble_minutes_reduction,
    _apply_garbage_time_adjustment,
    _enrich_scenarios_from_context,
    _cholesky_2x2,
    _sample_correlated_pair,
)

__all__ = [
    # Constants
    "FOUL_TROUBLE_PROBABILITY",
    "GAME_SCENARIOS",
    "HOT_HAND_PROBABILITY",
    "COLD_GAME_PROBABILITY",
    "CONVERGENCE_THRESHOLD",
    "DEFAULT_PROJECTED_MINUTES",
    "MINUTES_STD_DEFAULT",
    "STAT_CORRELATION",
    "QUARTER_FATIGUE_RATES",
    # Public functions
    "run_quantum_matrix_simulation",
    "generate_alt_line_probabilities",
    "run_monte_carlo_simulation",
    "build_histogram_from_results",
    "simulate_combo_stat",
    "simulate_fantasy_score",
    "simulate_double_double",
    "simulate_triple_double",
    "run_enhanced_simulation",
    "run_sensitivity_analysis",
    "enrich_simulation_with_advanced_stats",
]
