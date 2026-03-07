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
