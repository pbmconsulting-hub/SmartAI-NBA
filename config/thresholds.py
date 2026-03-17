# ============================================================
# FILE: config/thresholds.py
# PURPOSE: Centralized named constants for all thresholds used
#          in tier classification, edge detection, and confidence scoring.
#
# Usage:
#   from config.thresholds import PLATINUM_THRESHOLD, GOLD_THRESHOLD, ...
# ============================================================

# ── Confidence tier thresholds (0–100 SAFE Score) ────────────────────────────
PLATINUM_THRESHOLD = 84   # Near-perfect conditions
GOLD_THRESHOLD     = 65   # Very strong, clear edge
SILVER_THRESHOLD   = 57   # Solid evidence above average
BRONZE_THRESHOLD   = 35   # Minimum viable confidence (below = Do Not Bet)

DO_NOT_BET_THRESHOLD = 35  # Alias for BRONZE_THRESHOLD floor

# ── Minimum edge % required per tier ──────────────────────────────────────────
PLATINUM_MIN_EDGE_PCT = 10.0
GOLD_MIN_EDGE_PCT     = 7.0
SILVER_MIN_EDGE_PCT   = 3.0
BRONZE_MIN_EDGE_PCT   = 1.0

# ── Minimum win probability per tier ─────────────────────────────────────────
PLATINUM_MIN_PROBABILITY = 0.62
GOLD_MIN_PROBABILITY     = 0.57

# ── Goblin bet classification thresholds ─────────────────────────────────────
GOBLIN_MIN_STD_DEVS   = 2.0    # Projection ≥2 std devs from line
GOBLIN_MIN_PROBABILITY = 0.80  # Model probability ≥80%
GOBLIN_MIN_EDGE       = 25.0   # Edge ≥25%
GOBLIN_LINE_MIN_RATIO = 0.25   # Line ≥25% of season average
GOBLIN_LINE_MAX_RATIO = 4.0    # Line ≤4× season average

# ── Demon bet classification thresholds ──────────────────────────────────────
DEMON_CONFLICT_RATIO_THRESHOLD  = 0.80   # Forces within 20% = conflicting
DEMON_HIGH_VAR_MAX_EDGE         = 8.0    # High-variance stats with edge <8%
DEMON_BLOWOUT_SPREAD_THRESHOLD  = 10.0   # Spread >10 pts on back-to-back
DEMON_HOT_STREAK_RATIO          = 1.25   # Line ≥125% of season avg

# ── Auto-log Bronze thresholds ────────────────────────────────────────────────
BRONZE_AUTO_LOG_MIN_EDGE       = 8.0    # Bronze requires ≥8% edge to auto-log
BRONZE_AUTO_LOG_MIN_CONFIDENCE = 60.0   # Bronze requires ≥60 confidence score

# ── Simulation defaults ───────────────────────────────────────────────────────
DEFAULT_NUM_SIMULATIONS = 2000
CONVERGENCE_THRESHOLD   = 0.001
CONVERGENCE_CHECK_INTERVAL = 200

# ── Sensitivity analysis defaults ────────────────────────────────────────────
SENSITIVITY_BLOWOUT_DELTA = 0.10   # ±10% blowout risk
SENSITIVITY_PACE_DELTA    = 0.05   # ±5% pace adjustment
SENSITIVITY_MATCHUP_DELTA = 0.05   # ±5% matchup adjustment
