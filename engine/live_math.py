# ============================================================
# FILE: engine/live_math.py
# PURPOSE: Pacing Engine & Risk Flags for the Live Sweat
#          dashboard.  Projects a player's final stat line from
#          current in-game stats, minutes played, and pace.
# ============================================================

import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
REGULATION_MINUTES = 48
HALF_MINUTES = 24
BLOWOUT_THRESHOLD = 20
FOUL_TROUBLE_THRESHOLD = 3
BLOWOUT_PACE_SLASH = 0.70  # multiply projected pace by 70% in blowouts


def calculate_live_pace(
    current_stat: float,
    minutes_played: float,
    target_stat: float,
    live_score_diff: float = 0.0,
    current_fouls: int = 0,
    period: str = "",
) -> dict:
    """
    Project the final stat line and return risk flags.

    Parameters
    ----------
    current_stat : float
        The player's current accumulated stat value (e.g. 14 points).
    minutes_played : float
        Minutes the player has played so far.
    target_stat : float
        The prop line / target the user bet on (e.g. 24.5 points).
    live_score_diff : float
        Absolute score differential (always positive = leading margin).
        A positive value > 20 triggers blowout risk in 3rd/4th quarters.
    current_fouls : int
        The player's current personal foul count.
    period : str
        Current game period indicator (e.g. "1", "2", "3", "4", "Q1", "OT").

    Returns
    -------
    dict with keys:
        current_stat        – echoed back
        target_stat         – echoed back
        distance            – how many more needed (target − current)
        minutes_played      – echoed back
        pace_per_minute     – current_stat / max(1, minutes_played)
        projected_final     – projected total over 48 min (adjusted)
        pct_of_target       – projected_final / target as a 0-100 float
        blowout_risk        – True if blowout detected in late quarters
        foul_trouble        – True if ≥3 fouls in the first half
        on_pace             – True when projected_final ≥ target
        cashed              – True when current_stat ≥ target already
    """
    # Sanitise inputs
    current_stat = max(0.0, float(current_stat))
    minutes_played = max(0.0, float(minutes_played))
    target_stat = max(0.01, float(target_stat))  # avoid division by zero
    live_score_diff = abs(float(live_score_diff))
    current_fouls = max(0, int(current_fouls))

    # Already cashed?
    cashed = current_stat >= target_stat

    # Per-minute pace
    safe_minutes = max(1.0, minutes_played)
    pace_per_minute = current_stat / safe_minutes

    # Raw projected final over 48 regulation minutes
    projected_final = pace_per_minute * REGULATION_MINUTES

    # ── Risk flags ────────────────────────────────────────────
    period_str = str(period).upper().replace("Q", "").strip()
    try:
        period_num = int(period_str) if period_str.isdigit() else 0
    except (ValueError, TypeError):
        period_num = 0

    is_second_half = period_num >= 3

    blowout_risk = False
    if is_second_half and live_score_diff > BLOWOUT_THRESHOLD:
        blowout_risk = True
        projected_final *= BLOWOUT_PACE_SLASH

    is_first_half = minutes_played <= HALF_MINUTES
    foul_trouble = is_first_half and current_fouls >= FOUL_TROUBLE_THRESHOLD

    if foul_trouble:
        projected_final *= 0.85  # mild reduction for foul trouble

    # ── Computed fields ───────────────────────────────────────
    distance = max(0.0, target_stat - current_stat)
    on_pace = projected_final >= target_stat
    pct_of_target = min(200.0, (projected_final / target_stat) * 100)

    return {
        "current_stat":    current_stat,
        "target_stat":     target_stat,
        "distance":        round(distance, 1),
        "minutes_played":  round(minutes_played, 1),
        "pace_per_minute": round(pace_per_minute, 2),
        "projected_final": round(projected_final, 1),
        "pct_of_target":   round(pct_of_target, 1),
        "blowout_risk":    blowout_risk,
        "foul_trouble":    foul_trouble,
        "on_pace":         on_pace,
        "cashed":          cashed,
    }


def pace_color_tier(pct_of_target: float) -> str:
    """
    Return the CSS class suffix for the progress bar fill color.

    * 0-50 %   → ``blue``
    * 51-85 %  → ``orange``
    * 86-99 %  → ``red``   (pulsing)
    * 100 % +  → ``green`` (glowing)
    """
    if pct_of_target >= 100:
        return "green"
    if pct_of_target >= 86:
        return "red"
    if pct_of_target >= 51:
        return "orange"
    return "blue"
