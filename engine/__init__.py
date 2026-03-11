# ============================================================
# FILE: engine/__init__.py
# PURPOSE: Shared constants for the SmartBetPro NBA engine.
#          Import these in any module that needs them.
# ============================================================

# Simple (single-stat) stat types.
SIMPLE_STAT_TYPES = frozenset({
    "points",
    "rebounds",
    "assists",
    "threes",
    "steals",
    "blocks",
    "turnovers",
})

# Combo stat types (sum of 2+ simple stats).
COMBO_STAT_TYPES = frozenset({
    "points_rebounds",
    "points_assists",
    "rebounds_assists",
    "points_rebounds_assists",
    "blocks_steals",
})

# Fantasy score stat types (weighted sum using platform formula).
FANTASY_STAT_TYPES = frozenset({
    "fantasy_score_pp",   # PrizePicks fantasy scoring
    "fantasy_score_dk",   # DraftKings fantasy scoring
    "fantasy_score_ud",   # Underdog fantasy scoring
})

# Yes/No prop types.
YESNO_STAT_TYPES = frozenset({
    "double_double",
    "triple_double",
})

# All supported stat types across the app.
# This is the single source of truth — don't define this elsewhere.
VALID_STAT_TYPES = SIMPLE_STAT_TYPES | COMBO_STAT_TYPES | FANTASY_STAT_TYPES | YESNO_STAT_TYPES

# ============================================================
# SECTION: New High-Impact Feature Modules (v8)
# These modules are imported directly by pages; they are not
# re-exported from __init__.py to keep the namespace clean.
# Available modules:
#   engine.matchup_history       — Feature 2: Player-vs-team history
#   engine.platform_line_compare — Feature 3: Cross-platform line comparison
#   engine.bankroll              — Feature 5: Kelly Criterion sizing
#   engine.minutes_model         — Feature 6: Dedicated minutes projection
#   engine.game_script           — Feature 7: Quarter-by-quarter simulation
#   engine.market_movement       — Feature 9: Sharp money line movement
# ============================================================
