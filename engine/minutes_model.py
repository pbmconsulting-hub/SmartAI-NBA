# ============================================================
# FILE: engine/minutes_model.py
# PURPOSE: Dedicated Minutes Projection Model
#          Minutes played is the #1 driver of all stats.
#          This module builds a comprehensive minutes projection
#          accounting for blowout risk, rest, teammate injuries,
#          game importance, and foul trouble history.
#
#          Better minutes projection → better stat projections
#          for ALL stat types (points, rebounds, assists, etc.).
#
# CONNECTS TO: engine/projections.py (build_player_projection),
#              engine/simulation.py (run_monte_carlo_simulation)
# CONCEPTS COVERED: Minutes model, blowout sensitivity,
#                   back-to-back fatigue, teammate injury impact,
#                   rotation patterns
# ============================================================

import math

try:
    from engine.rotation_tracker import get_trending_minutes
    _HAS_ROTATION_TRACKER = True
except ImportError:
    _HAS_ROTATION_TRACKER = False


# ============================================================
# SECTION: Minutes Model Constants
# ============================================================

# Default season average minutes for typical starters/bench players.
DEFAULT_STARTER_MINUTES = 32.0    # Typical NBA starter average
DEFAULT_BENCH_MINUTES = 18.0      # Typical bench player average

# Back-to-back fatigue: reduce minutes on second night.
BACK_TO_BACK_MINUTES_REDUCTION = 2.5    # Starters typically play ~2.5 fewer mins

# Blowout risk: high-spread games lead to star players sitting in Q4.
# Spread thresholds for minutes adjustments (positive = player's team favored).
BLOWOUT_SPREAD_MILD = 7.0         # 7+ point favorite: mild minutes risk (-1.0 min)
BLOWOUT_SPREAD_MODERATE = 10.0    # 10+ point favorite: moderate risk (-2.5 mins)
BLOWOUT_SPREAD_HEAVY = 15.0       # 15+ point favorite: heavy risk (-4.0 mins)
BLOWOUT_SPREAD_EXTREME = 20.0     # 20+ point favorite: extreme risk (-5.5 mins)

# Teammate injury boost: key teammate out → starter gets more minutes.
# Additive boost when an important rotation player is unavailable.
TEAMMATE_OUT_MINUTES_BOOST = 3.0    # +3 minutes when a key teammate is out

# Minutes variance model: std dev grows with blowout risk.
MINUTES_STD_BASE = 4.0              # Baseline std dev in normal games
MINUTES_STD_BLOWOUT_EXTRA = 2.5     # Additional std dev when blowout risk is high
MINUTES_STD_BACK_TO_BACK_EXTRA = 1.5  # Additional std dev on B2B (coach manages load)

# Game importance and load management thresholds.
LOAD_MANAGE_GAMES_BEFORE_PLAYOFFS = 3   # Last N games before playoffs: may rest stars
MAX_MINUTES_CAP = 44.0              # No simulated game gives > 44 minutes (OT possible)
MIN_MINUTES_FLOOR = 0.0             # DNP risk — can go to 0 in extreme blowout

# ============================================================
# END SECTION: Minutes Model Constants
# ============================================================


# ============================================================
# SECTION: Minutes Projection
# ============================================================

def project_player_minutes(player_data, game_context, teammate_status=None, game_logs=None):
    """
    Project a player's minutes for tonight with all situational adjustments.

    Applies blowout risk, back-to-back fatigue, teammate injury boosts,
    and pace context to produce a comprehensive minutes estimate.

    Args:
        player_data (dict): Player stats dict with 'minutes_avg' (or 'min_avg'),
            'position' (G/F/C), 'team' (team abbreviation), and optionally
            'is_starter' (bool).
        game_context (dict): Tonight's game info with keys:
            'vegas_spread' (float, positive = player's team favored),
            'rest_days' (int, 0 = back-to-back),
            'game_total' (float, over/under total),
            'is_home' (bool).
        teammate_status (dict, optional): {player_name: status} for teammates.
            Status 'Out' or 'Injured Reserve' triggers minutes boost.

    Returns:
        dict: {
            'projected_minutes': float,      # Central projection
            'minutes_std': float,            # Standard deviation
            'minutes_floor': float,          # 10th percentile (low end)
            'minutes_ceiling': float,        # 90th percentile (high end)
            'base_minutes': float,           # Season average (before adjustments)
            'adjustment_notes': list of str, # Human-readable change log
            'blowout_risk': str,             # 'none', 'mild', 'moderate', 'heavy', 'extreme'
        }

    Example:
        result = project_player_minutes(
            player_data={'minutes_avg': 34.5, 'position': 'G', 'is_starter': True},
            game_context={'vegas_spread': 12.0, 'rest_days': 1, 'game_total': 228.5},
        )
        # result['projected_minutes'] → ~32.0 (reduced from 34.5 for blowout risk)
    """
    adjustment_notes = []

    # ── Step 1: Establish base minutes ──────────────────────────────────────
    # Use rotation tracker trending minutes if game logs available
    if _HAS_ROTATION_TRACKER and game_logs:
        try:
            trending = get_trending_minutes(player_data, game_logs)
            base_minutes = trending if trending > 0 else None
            if base_minutes:
                adjustment_notes.append(f"Base: {base_minutes:.1f} min (trending avg)")
        except Exception:
            base_minutes = None
    else:
        base_minutes = None

    if base_minutes is None:
        base_minutes = (
            player_data.get('minutes_avg')
            or player_data.get('min_avg')
        )

    if base_minutes is None:
        # Infer default from position/starter status
        is_starter = player_data.get('is_starter', False)
        position = str(player_data.get('position', '')).upper()
        if is_starter or position in ('G', 'F', 'C', 'PG', 'SG', 'SF', 'PF'):
            base_minutes = DEFAULT_STARTER_MINUTES
            adjustment_notes.append(f"Base: {base_minutes:.1f} min (default starter)")
        else:
            base_minutes = DEFAULT_BENCH_MINUTES
            adjustment_notes.append(f"Base: {base_minutes:.1f} min (default bench)")
    else:
        base_minutes = float(base_minutes)
        adjustment_notes.append(f"Base: {base_minutes:.1f} min (season avg)")

    projected = base_minutes

    # ── Step 2: Back-to-back fatigue ────────────────────────────────────────
    rest_days = int(game_context.get('rest_days', 1))
    std_extra = 0.0

    if rest_days == 0:
        projected -= BACK_TO_BACK_MINUTES_REDUCTION
        std_extra += MINUTES_STD_BACK_TO_BACK_EXTRA
        adjustment_notes.append(
            f"B2B fatigue: -{BACK_TO_BACK_MINUTES_REDUCTION:.1f} min"
        )

    # ── Step 3: Blowout spread adjustment ───────────────────────────────────
    spread = float(game_context.get('vegas_spread', 0.0))
    blowout_risk = 'none'

    if spread >= BLOWOUT_SPREAD_EXTREME:
        blowout_reduction = 5.5
        blowout_risk = 'extreme'
        std_extra += MINUTES_STD_BLOWOUT_EXTRA
    elif spread >= BLOWOUT_SPREAD_HEAVY:
        blowout_reduction = 4.0
        blowout_risk = 'heavy'
        std_extra += MINUTES_STD_BLOWOUT_EXTRA
    elif spread >= BLOWOUT_SPREAD_MODERATE:
        blowout_reduction = 2.5
        blowout_risk = 'moderate'
        std_extra += MINUTES_STD_BLOWOUT_EXTRA
    elif spread >= BLOWOUT_SPREAD_MILD:
        blowout_reduction = 1.0
        blowout_risk = 'mild'
    else:
        blowout_reduction = 0.0

    if blowout_reduction > 0.0:
        projected -= blowout_reduction
        adjustment_notes.append(
            f"Blowout risk ({blowout_risk}, spread={spread:+.1f}): -{blowout_reduction:.1f} min"
        )

    # ── Step 4: Teammate injury boost ───────────────────────────────────────
    if teammate_status:
        out_statuses = {'out', 'injured reserve', 'ir', 'gtd', 'doubtful'}
        injured_teammates = [
            name for name, status in teammate_status.items()
            if str(status).lower() in out_statuses
        ]
        if injured_teammates:
            # Apply diminishing returns: each additional injured teammate adds
            # proportionally less (0.5x factor per teammate beyond the first)
            # to avoid unrealistic projections when many players are out.
            total_boost = 0.0
            for idx in range(len(injured_teammates)):
                total_boost += TEAMMATE_OUT_MINUTES_BOOST * (0.5 ** idx)
            total_boost = round(total_boost, 2)
            projected += total_boost
            adjustment_notes.append(
                f"Teammate(s) out ({', '.join(injured_teammates)}): +{total_boost:.1f} min"
            )

    # ── Step 5: Clamp projection to valid range ──────────────────────────────
    projected = max(MIN_MINUTES_FLOOR, min(MAX_MINUTES_CAP, projected))

    # ── Step 6: Compute variance ─────────────────────────────────────────────
    minutes_std = calculate_minutes_variance(player_data, game_context)

    # 10th/90th percentile approximation: ±1.28 * std (normal distribution)
    minutes_floor = round(max(MIN_MINUTES_FLOOR, projected - 1.5 * minutes_std), 1)
    minutes_ceiling = round(min(MAX_MINUTES_CAP, projected + 1.5 * minutes_std), 1)

    return {
        'projected_minutes': round(projected, 1),
        'minutes_std': minutes_std,
        'minutes_floor': minutes_floor,
        'minutes_ceiling': minutes_ceiling,
        'base_minutes': round(base_minutes, 1),
        'adjustment_notes': adjustment_notes,
        'blowout_risk': blowout_risk,
    }


# ============================================================
# END SECTION: Minutes Projection
# ============================================================


# ============================================================
# SECTION: Minutes Variance
# ============================================================

def calculate_minutes_variance(player_data, game_context):
    """
    Compute minutes standard deviation for simulation use.

    Accounts for blowout risk, back-to-back, and player type (starter vs bench).
    Higher variance when blowout risk is high (star may sit the whole 4th quarter).

    Args:
        player_data (dict): Player stats including 'minutes_avg'.
        game_context (dict): Game context with 'vegas_spread', 'rest_days'.

    Returns:
        float: Minutes standard deviation to use in simulation.

    Example:
        std = calculate_minutes_variance({'minutes_avg': 34.0}, {'vegas_spread': 14.0})
        # Returns ~6.5 (elevated variance due to heavy blowout risk)
    """
    std = MINUTES_STD_BASE

    spread = float(game_context.get('vegas_spread', 0.0))
    rest_days = int(game_context.get('rest_days', 1))

    # Elevated variance when there is a meaningful blowout risk
    if spread >= BLOWOUT_SPREAD_MODERATE:
        std += MINUTES_STD_BLOWOUT_EXTRA

    # Coaches manage minutes more unpredictably on back-to-backs
    if rest_days == 0:
        std += MINUTES_STD_BACK_TO_BACK_EXTRA

    return round(std, 2)


# ============================================================
# END SECTION: Minutes Variance
# ============================================================
