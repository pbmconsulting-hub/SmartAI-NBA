# ============================================================
# FILE: engine/__init__.py
# PURPOSE: Shared constants for the SmartAI-NBA engine.
#          Import these in any module that needs them.
# ============================================================

# All supported stat types across the app.
# This is the single source of truth — don't define this elsewhere.
VALID_STAT_TYPES = frozenset({
    "points",
    "rebounds",
    "assists",
    "threes",
    "steals",
    "blocks",
    "turnovers",
})
