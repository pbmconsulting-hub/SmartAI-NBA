# ============================================================
# FILE: engine/edge_detection.py
# PURPOSE: Detect betting edges by analyzing directional forces
#          that push a player's actual performance MORE or LESS
#          than the posted prop line.
# CONNECTS TO: projections.py, confidence.py, simulation.py
# CONCEPTS COVERED: Asymmetric forces, edge detection,
#                   directional analysis
# ============================================================

# Standard library only
import math  # For rounding calculations

# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# Coefficient of variation (std / mean) above which a stat is
# considered "too unpredictable" to bet reliably.
# CV of 0.45 means the std is 45% of the average — very noisy.
HIGH_VARIANCE_CV_THRESHOLD = 0.45  # loosened from 0.40 so secondary stats (steals, blocks, threes) aren't auto-avoided

# Sportsbook vig/juice is typically ~4.5%. We subtract 2.0% from raw edge
# to account for this before declaring a qualifying edge.
VIG_ADJUSTMENT_PCT = 2.0

# Minimum edge required AFTER vig deduction for a pick to qualify
MIN_EDGE_AFTER_VIG = 2.0  # lowered from 4.0 (was 3.0 originally) to align with Silver 3% min edge

# Low-volume stat types with inherently higher variance.
# These require a larger raw edge to overcome uncertainty.
LOW_VOLUME_STATS = {"steals", "blocks", "turnovers", "threes"}

# Uncertainty multiplier applied to low-volume stats' edge calculations.
# 1.3x means a steal prop needs effectively 1.3x more edge to qualify.
LOW_VOLUME_UNCERTAINTY_MULTIPLIER = 1.3  # softened from 1.5 to reduce over-penalizing secondary stats


# ============================================================
# SECTION: Force Definitions
# "Forces" are contextual factors that push a player's stat
# outcome OVER or UNDER the prop line.
# Each force has a name, direction, and strength (0-3 scale).
# ============================================================

def analyze_directional_forces(
    player_data,
    prop_line,
    stat_type,
    projection_result,
    game_context,
):
    """
    Identify all forces pushing the stat OVER or UNDER the line.

    Checks multiple factors: projection vs line, matchup,
    pace, blowout risk, rest, home/away, etc.
    Returns a list of active forces and a summary.

    Args:
        player_data (dict): Player season stats from CSV
        prop_line (float): The betting line (e.g., 24.5)
        stat_type (str): 'points', 'rebounds', 'assists', etc.
        projection_result (dict): Output from projections.py
            includes projected values and factors
        game_context (dict): Tonight's game info:
            'opponent', 'is_home', 'rest_days', 'game_total',
            'vegas_spread' (positive = player's team favored)

    Returns:
        dict: {
            'over_forces': list of force dicts (pushing OVER)
            'under_forces': list of force dicts (pushing UNDER)
            'over_count': int
            'under_count': int
            'over_strength': float (total strength of over forces)
            'under_strength': float (total strength of under forces)
            'net_direction': str 'OVER' or 'UNDER'
            'net_strength': float
        }

    Example:
        If projection is 26.8 and line is 24.5,
        "Projection Exceeds Line" → OVER force, strength 2.1
    """
    # Lists to collect forces pushing each direction
    all_over_forces = []   # Forces that suggest going OVER
    all_under_forces = []  # Forces that suggest going UNDER

    # Get the projected value for the relevant stat
    projected_value = projection_result.get(f"projected_{stat_type}", 0)

    # Get contextual values
    defense_factor = projection_result.get("defense_factor", 1.0)
    pace_factor = projection_result.get("pace_factor", 1.0)
    blowout_risk = projection_result.get("blowout_risk", 0.15)
    rest_factor = projection_result.get("rest_factor", 1.0)
    is_home = game_context.get("is_home", True)
    vegas_spread = game_context.get("vegas_spread", 0.0)  # + = player's team favored
    game_total = game_context.get("game_total", 220.0)

    # ============================================================
    # SECTION: Check Each Force
    # ============================================================

    # --- Force 1: Projection vs Line ---
    # Most important force: does our model project OVER or UNDER?
    if projected_value > prop_line:
        projection_gap = projected_value - prop_line
        strength = min(3.0, projection_gap / 3.0)  # 1 point gap = 0.33 strength
        all_over_forces.append({
            "name": "Model Projection Exceeds Line",
            "description": f"Projects {projected_value:.1f} vs line of {prop_line}",
            "strength": round(strength, 2),
            "direction": "OVER",
        })
    elif projected_value < prop_line:
        projection_gap = prop_line - projected_value
        strength = min(3.0, projection_gap / 3.0)
        all_under_forces.append({
            "name": "Model Projection Below Line",
            "description": f"Projects {projected_value:.1f} vs line of {prop_line}",
            "strength": round(strength, 2),
            "direction": "UNDER",
        })

    # --- Force 2: Matchup / Defensive Rating ---
    if defense_factor > 1.05:
        strength = min(2.0, (defense_factor - 1.0) * 10.0)
        all_over_forces.append({
            "name": "Favorable Matchup",
            "description": f"Opponent allows {(defense_factor-1)*100:.0f}% more than avg to this position",
            "strength": round(strength, 2),
            "direction": "OVER",
        })
    elif defense_factor < 0.95:
        strength = min(2.0, (1.0 - defense_factor) * 10.0)
        all_under_forces.append({
            "name": "Tough Matchup",
            "description": f"Opponent allows {(1-defense_factor)*100:.0f}% less than avg to this position",
            "strength": round(strength, 2),
            "direction": "UNDER",
        })

    # --- Force 3: Game Pace ---
    if pace_factor > 1.02:
        strength = min(1.5, (pace_factor - 1.0) * 15.0)
        all_over_forces.append({
            "name": "Fast Pace Game",
            "description": f"Expected game pace {pace_factor*100-100:.1f}% above league average",
            "strength": round(strength, 2),
            "direction": "OVER",
        })
    elif pace_factor < 0.98:
        strength = min(1.5, (1.0 - pace_factor) * 15.0)
        all_under_forces.append({
            "name": "Slow Pace Game",
            "description": f"Expected game pace {(1-pace_factor)*100:.1f}% below league average",
            "strength": round(strength, 2),
            "direction": "UNDER",
        })

    # --- Force 4: Blowout Risk ---
    # High blowout risk = stars may sit in garbage time
    if blowout_risk > 0.25:
        strength = min(2.0, (blowout_risk - 0.25) * 10.0)
        all_under_forces.append({
            "name": "Blowout Risk",
            "description": f"{blowout_risk*100:.0f}% chance of blowout — star may sit late",
            "strength": round(strength, 2),
            "direction": "UNDER",
        })

    # --- Force 5: Rest / Fatigue ---
    if rest_factor < 0.95:
        strength = min(1.5, (1.0 - rest_factor) * 20.0)
        all_under_forces.append({
            "name": "Fatigue / Back-to-Back",
            "description": f"Playing on short rest — performance typically drops {(1-rest_factor)*100:.0f}%",
            "strength": round(strength, 2),
            "direction": "UNDER",
        })
    elif rest_factor > 1.01:
        strength = min(1.0, (rest_factor - 1.0) * 50.0)
        all_over_forces.append({
            "name": "Well Rested",
            "description": "Multiple days of rest — typically improves performance",
            "strength": round(strength, 2),
            "direction": "OVER",
        })

    # --- Force 6: Home Court Advantage ---
    if is_home:
        all_over_forces.append({
            "name": "Home Court Advantage",
            "description": "Playing at home — historically +2.5% performance boost",
            "strength": 0.5,
            "direction": "OVER",
        })
    else:
        all_under_forces.append({
            "name": "Road Game",
            "description": "Playing away — historically -1.5% performance penalty",
            "strength": 0.3,
            "direction": "UNDER",
        })

    # --- Force 7: Vegas Spread (Blowout Angle) ---
    # If player's team is a huge favorite, stars may rest in 4th quarter
    if vegas_spread > 10:
        all_under_forces.append({
            "name": "Heavy Favorite — Garbage Time Risk",
            "description": f"Team favored by {vegas_spread:.1f} — stars may sit late",
            "strength": min(1.5, vegas_spread * 0.08),
            "direction": "UNDER",
        })
    elif vegas_spread < -8:
        # Player's team is a big underdog — may get blown out
        all_under_forces.append({
            "name": "Heavy Underdog — Possible Blowout Loss",
            "description": f"Team is {abs(vegas_spread):.1f}-point underdog",
            "strength": min(1.5, abs(vegas_spread) * 0.06),
            "direction": "UNDER",
        })

    # --- Force 8: High Game Total ---
    # High-total game = fast-paced scoring game = more opportunities
    if game_total > 228:
        all_over_forces.append({
            "name": "High-Scoring Game Environment",
            "description": f"Vegas total of {game_total:.0f} — very high-paced game expected",
            "strength": min(1.5, (game_total - 220) * 0.075),
            "direction": "OVER",
        })
    elif game_total < 214 and game_total > 0:
        all_under_forces.append({
            "name": "Low-Scoring Game Environment",
            "description": f"Vegas total of {game_total:.0f} — slow, defensive game expected",
            "strength": min(1.5, (220 - game_total) * 0.075),
            "direction": "UNDER",
        })

    # ============================================================
    # END SECTION: Check Each Force
    # ============================================================

    # ============================================================
    # SECTION: Line Sharpness Detection (W1)
    # Sharp books set lines RIGHT at the player's true average.
    # A line within 3% of the season avg is essentially a coin-flip —
    # penalize over-confidence. Lines 8%+ away are where real edges live.
    # ============================================================

    season_average = player_data.get(f"{stat_type}_avg", None)
    if season_average is not None:
        try:
            season_average = float(season_average)
        except (TypeError, ValueError):
            season_average = None

    line_sharpness_force = detect_line_sharpness(prop_line, season_average, stat_type)
    if line_sharpness_force is not None:
        if line_sharpness_force["direction"] == "OVER":
            all_over_forces.append(line_sharpness_force)
        else:
            all_under_forces.append(line_sharpness_force)

    # ============================================================
    # END SECTION: Line Sharpness Detection
    # ============================================================

    # ============================================================
    # SECTION: Summarize Forces
    # ============================================================

    # Count and sum strength of over/under forces
    over_count = len(all_over_forces)
    under_count = len(all_under_forces)
    over_total_strength = sum(f["strength"] for f in all_over_forces)
    under_total_strength = sum(f["strength"] for f in all_under_forces)

    # Determine the net direction
    if over_total_strength > under_total_strength:
        net_direction = "OVER"
        net_strength = over_total_strength - under_total_strength
    else:
        net_direction = "UNDER"
        net_strength = under_total_strength - over_total_strength

    return {
        "over_forces": all_over_forces,
        "under_forces": all_under_forces,
        "over_count": over_count,
        "under_count": under_count,
        "over_strength": round(over_total_strength, 2),
        "under_strength": round(under_total_strength, 2),
        "net_direction": net_direction,
        "net_strength": round(net_strength, 2),
    }

    # ============================================================
    # END SECTION: Summarize Forces
    # ============================================================


# ============================================================
# SECTION: Avoid List Logic
# Determine if a prop should go on the "avoid" list
# ============================================================

def should_avoid_prop(
    probability_over,
    directional_forces_result,
    edge_percentage,
    stat_standard_deviation,
    stat_average,
    stat_type=None,
    platform=None,
    over_odds=-110,
):
    """
    Determine whether a prop pick should be avoided.

    A prop goes on the avoid list if:
    1. No clear edge (< 5% edge in either direction)
    2. High variance stat (too unpredictable)
    3. Conflicting forces (equal OVER and UNDER pressure)
    4. Blowout risk forces are present and strong

    Args:
        probability_over (float): P(over), 0-1
        directional_forces_result (dict): Output of analyze_directional_forces
        edge_percentage (float): Edge %, positive = lean over
        stat_standard_deviation (float): Variability
        stat_average (float): Average for this stat
        stat_type (str, optional): Stat type for low-volume check
        platform (str, optional): Platform name — PrizePicks/Underdog have 0%
            structural vig on individual legs (payout baked into table).
            DraftKings uses variable juice from actual odds.
        over_odds (float): American odds on the over side (used for DraftKings
            vig calculation). Default -110.

    Returns:
        tuple: (should_avoid: bool, reasons: list of str)

    Example:
        0.51 probability, conflicting forces → avoid=True,
        reasons=['Insufficient edge (<5%)', 'Conflicting forces']
    """
    avoid_reasons = []  # Collect all reasons to avoid

    # ── Platform-specific vig adjustment ──────────────────────────────────────
    # PrizePicks and Underdog have NO per-leg juice — vig is baked into the
    # multi-leg payout structure, so we apply 0% to individual legs.
    # DraftKings uses actual American odds, so we calculate the real vig.
    _NO_VIG_PLATFORMS = {"PrizePicks", "Underdog", "Underdog Fantasy"}
    if platform and platform in _NO_VIG_PLATFORMS:
        effective_vig = 0.0
    elif over_odds and over_odds != -110:
        # Derive vig from actual DraftKings odds (e.g. -130 → breakeven 56.5%)
        # Vig = implied_prob - 0.5 (excess above fair 50/50)
        try:
            _odds = float(over_odds)
            _implied = abs(_odds) / (abs(_odds) + 100.0) if _odds < 0 else 100.0 / (_odds + 100.0)
            # Vig = implied_prob excess above a fair 50/50 coin flip
            effective_vig = max(0.0, (_implied - 0.5) * 100.0)
        except (ValueError, TypeError):
            effective_vig = VIG_ADJUSTMENT_PCT
    else:
        effective_vig = VIG_ADJUSTMENT_PCT

    # Reason 1: Edge too small after vig adjustment
    stat_type_lower = str(stat_type).lower() if stat_type else ""
    vig_adjusted_edge = abs(edge_percentage) - effective_vig
    # Low-volume stats require a larger effective edge due to higher variance.
    if stat_type_lower in LOW_VOLUME_STATS:
        effective_edge = vig_adjusted_edge / LOW_VOLUME_UNCERTAINTY_MULTIPLIER
    else:
        effective_edge = vig_adjusted_edge
    if effective_edge < MIN_EDGE_AFTER_VIG:
        _vig_adj_display = max(0.0, vig_adjusted_edge)  # show 0 if negative to avoid confusion
        _vig_label = f"{effective_vig:.1f}% vig" if effective_vig > 0 else "no vig (PrizePicks/Underdog)"
        avoid_reasons.append(
            f"Insufficient edge after vig ({edge_percentage:.1f}% raw → "
            f"{_vig_adj_display:.1f}% after {_vig_label}) — "
            f"below {MIN_EDGE_AFTER_VIG}% minimum"
        )

    # Reason 2: High variance relative to line (too unpredictable)
    if stat_average > 0:
        coefficient_of_variation = stat_standard_deviation / stat_average
        if coefficient_of_variation > HIGH_VARIANCE_CV_THRESHOLD:
            avoid_reasons.append(
                f"High variance stat (CV={coefficient_of_variation:.2f}) — very unpredictable"
            )

    # Reason 3: Conflicting forces (roughly equal over/under pressure)
    over_strength = directional_forces_result.get("over_strength", 0)
    under_strength = directional_forces_result.get("under_strength", 0)
    if over_strength > 0 and under_strength > 0:
        conflict_ratio = min(over_strength, under_strength) / max(over_strength, under_strength)
        if conflict_ratio > 0.80:  # Within 20% of each other = conflicting (raised from 0.70)
            avoid_reasons.append(
                "Conflicting forces — OVER and UNDER signals are nearly equal"
            )

    # Reason 4: Strong blowout risk force present
    under_forces = directional_forces_result.get("under_forces", [])
    for force in under_forces:
        if "Blowout" in force.get("name", "") and force.get("strength", 0) > 1.0:
            avoid_reasons.append(
                f"Strong blowout risk — player may not get full minutes"
            )
            break

    # If any reasons found, recommend avoiding
    should_avoid = len(avoid_reasons) > 0

    return should_avoid, avoid_reasons

# ============================================================
# END SECTION: Avoid List Logic
# ============================================================


# ============================================================
# SECTION: Correlation Detection
# Identify correlated props that come from the same game.
# Correlated props carry additional parlay risk.
# ============================================================

def detect_correlated_props(props_with_results):
    """
    Flag props from the same game as correlated bets.

    When two players from the same game are included in a parlay,
    their outcomes are statistically correlated (same pace, scoring
    environment, and blowout risk). This should be disclosed to
    the user so they can make informed parlay decisions.

    Args:
        props_with_results (list of dict): Analysis results. Each dict
            must contain 'player_team' and 'opponent' keys.

    Returns:
        dict: Mapping of prop index (int) to a correlation warning
              string, or an empty dict if no correlations found.

    Example:
        If props[0] is LeBron (LAL vs GSW) and props[2] is Steph
        (GSW vs LAL), both are flagged with a correlation warning.
    """
    # Build a "game key" for each prop: frozenset of the two teams
    # so LAL-vs-GSW and GSW-vs-LAL map to the same key.
    game_key_to_indices = {}  # game_key → list of prop indices

    for idx, result in enumerate(props_with_results):
        team = result.get("player_team", result.get("team", "")).upper().strip()
        opponent = result.get("opponent", "").upper().strip()
        if team and opponent:
            game_key = frozenset([team, opponent])
        elif team:
            game_key = frozenset([team])
        else:
            continue  # No team info — skip

        if game_key not in game_key_to_indices:
            game_key_to_indices[game_key] = []
        game_key_to_indices[game_key].append(idx)

    # Build the correlation warnings dict
    correlation_warnings = {}

    for game_key, indices in game_key_to_indices.items():
        if len(indices) < 2:
            continue  # Only one prop from this game — no correlation

        teams_str = " vs ".join(sorted(game_key))
        player_names = [props_with_results[i].get("player_name", "?") for i in indices]
        others_str = ", ".join(
            props_with_results[j].get("player_name", "?")
            for j in indices
            if j != indices[0]  # Will be customized per-prop below
        )

        for i in indices:
            my_name = props_with_results[i].get("player_name", "?")
            correlated_names = [
                props_with_results[j].get("player_name", "?")
                for j in indices if j != i
            ]
            correlated_str = ", ".join(correlated_names)
            correlation_warnings[i] = (
                f"Correlated with {correlated_str} ({teams_str} game) — "
                "same game props share scoring environment and blowout risk"
            )

    return correlation_warnings

# ============================================================
# END SECTION: Correlation Detection
# ============================================================


# ============================================================
# SECTION: Line Sharpness Detection (W1)
# Detect when books have set a "sharp" line right at the player's
# true average (a trap for bettors) vs. a line with real edge.
# ============================================================

def detect_line_sharpness(prop_line, season_average, stat_type="points"):
    """
    Detect whether a prop line is "sharp" (set close to the true average).

    Sharp lines are set RIGHT at the player's true average, making it
    essentially a 50/50 coin-flip. The engine shouldn't be confident
    on sharp lines — books have accurately priced them.

    Lines set 8%+ away from the average are where real edges exist
    because the book has (intentionally or not) left a gap.

    Args:
        prop_line (float): The betting line (e.g., 24.5)
        season_average (float or None): Player's season average for this stat.
            None means no average available — return None (no force).
        stat_type (str): Stat name for description

    Returns:
        dict or None: A force dict pushing UNDER (sharpness penalty) when
            line is within 3% of average, or None when not applicable.
            Returns an OVER force when line is set far below average (real edge).

    Example:
        season_avg=24.8, line=24.5 → 1.2% below avg → sharp line → UNDER penalty
        season_avg=24.8, line=20.5 → 17.3% below avg → real edge → no penalty (or OVER boost)
    """
    if season_average is None or season_average <= 0 or prop_line <= 0:
        return None  # Can't compute sharpness without a valid average

    # How far is the line from the season average (as percentage)?
    # Positive = line ABOVE average (harder for OVER), negative = line BELOW average
    gap_pct = (prop_line - season_average) / season_average * 100.0

    abs_gap_pct = abs(gap_pct)

    if abs_gap_pct < 3.0:
        # Line is within 3% of season average — this is a SHARP line.
        # Books have set it at the true average → 50/50 coin flip.
        # Penalize confidence by pushing an UNDER force (signal of uncertainty).
        strength = 1.5 - (abs_gap_pct / 3.0) * 1.0  # Closer to avg = stronger penalty
        return {
            "name": "Sharp Line — Books Set at True Average",
            "description": (
                f"Line of {prop_line} is only {abs_gap_pct:.1f}% from season avg "
                f"({season_average:.1f}). Books have accurately priced this — "
                f"edge is minimal."
            ),
            "strength": round(max(0.5, strength), 2),
            "direction": "UNDER",  # Signals caution / reduced confidence
        }
    elif abs_gap_pct >= 8.0:
        # Line is 8%+ away from average — real edge territory.
        # Don't add a force (the Projection vs Line force already captures this),
        # but this confirms the edge is real, not a trap.
        # We return None here because the existing "Model Projection" force handles it.
        return None
    else:
        # Gap between 3% and 8% — moderate zone, no special force needed
        return None


# ============================================================
# END SECTION: Line Sharpness Detection
# ============================================================


# ============================================================
# SECTION: Trap Line Detection (W5)
# Detect when books set a deliberately bait-y line to attract
# public money on the "obvious" side, but hidden factors make
# the obvious side wrong.
# ============================================================

def detect_trap_line(
    prop_line,
    season_average,
    defense_factor,
    rest_factor,
    game_total,
    blowout_risk,
    stat_type="points",
):
    """
    Detect whether a prop line is a potential "trap."

    A trap line is deliberately set to attract public money on
    the obvious side, while hidden factors (tough defense + fatigue
    + low total) make the obvious side a loser.

    Two trap patterns:
    1. Line 10%+ below average + multiple negative factors present
       → Looks like easy OVER but the negative factors will kill it
    2. Line 10%+ above average + multiple positive factors present
       → Looks like a tough OVER but the positive factors will carry it
       (though this pattern is less dangerous)
    3. Line set at an exact common hit number (e.g., 24.5 near 25 avg)
       → Book is using a round number trap to attract action

    Args:
        prop_line (float): The betting line
        season_average (float or None): Player's season average
        defense_factor (float): Defensive multiplier (>1 = weak defense)
        rest_factor (float): Rest multiplier (<1 = fatigued)
        game_total (float): Vegas over/under total
        blowout_risk (float): Estimated blowout probability
        stat_type (str): Stat name for description

    Returns:
        dict or None: Trap detection result with:
            'is_trap': bool
            'trap_type': str ('under_trap' | 'over_trap' | 'round_number_trap' | None)
            'warning_message': str
            'confidence_penalty': float (0-15 points to subtract)
            'negative_factors': list of str
            'positive_factors': list of str

    Example:
        Player avg 26 PPG, line 23.5 (9.6% below), opponent top-5 D,
        back-to-back, game total 208 → under_trap detected
    """
    if season_average is None or season_average <= 0 or prop_line <= 0:
        return {"is_trap": False, "trap_type": None, "warning_message": "",
                "confidence_penalty": 0.0, "negative_factors": [], "positive_factors": []}

    gap_pct = (prop_line - season_average) / season_average * 100.0

    # --- Collect negative factors (push performance DOWN) ---
    negative_factors = []
    if defense_factor < 0.95:
        negative_factors.append(f"Tough opponent defense ({(1-defense_factor)*100:.0f}% suppression)")
    if rest_factor < 0.96:
        negative_factors.append("Short rest / back-to-back fatigue")
    if game_total > 0 and game_total < 214:
        negative_factors.append(f"Low Vegas total ({game_total:.0f}) — slow defensive game")
    if blowout_risk > 0.25:
        negative_factors.append(f"High blowout risk ({blowout_risk*100:.0f}%)")

    # --- Collect positive factors (push performance UP) ---
    positive_factors = []
    if defense_factor > 1.05:
        positive_factors.append(f"Weak opponent defense ({(defense_factor-1)*100:.0f}% boost)")
    if rest_factor > 1.005:
        positive_factors.append("Well rested")
    if game_total > 228:
        positive_factors.append(f"High Vegas total ({game_total:.0f}) — fast pace expected")
    if blowout_risk < 0.10:
        positive_factors.append("Very low blowout risk (likely competitive game)")

    # --- Check Trap Pattern 3: Round Number Trap ---
    # BEGINNER NOTE: Books often set lines at round numbers like 24.5 when a
    # player averages ~25. The psychological "round number" attracts action on
    # the OVER, but the line is really at the player's true average (coin-flip).
    # Common round numbers: 5, 10, 15, 20, 25, 30 for points; 5, 10 for rebounds; etc.
    _COMMON_HIT_NUMBERS = {
        "points":    [5, 10, 15, 20, 25, 30, 35, 40],
        "rebounds":  [5, 8, 10, 12, 15],
        "assists":   [5, 8, 10, 12],
        "threes":    [1, 2, 3, 4, 5],
        "steals":    [1, 2, 3],
        "blocks":    [1, 2, 3],
        "turnovers": [2, 3, 4, 5],
    }
    stat_type_lower = stat_type.lower() if stat_type else "points"
    common_numbers = _COMMON_HIT_NUMBERS.get(stat_type_lower, [])

    for common_num in common_numbers:
        # Check if the line is set within 0.5 of a common round number
        # AND the season average is near that same round number (within 5%)
        line_near_round = abs(prop_line - common_num) <= 0.5
        avg_near_round = abs(season_average - common_num) / max(1, common_num) < 0.05
        if line_near_round and avg_near_round:
            penalty = 5.0  # Moderate penalty for round number trap
            return {
                "is_trap": True,
                "trap_type": "round_number_trap",
                "warning_message": (
                    f"⚠️ Round Number Trap: Line {prop_line} is set at the common "
                    f"hit number {common_num} (player avg {season_average:.1f}) — "
                    f"books use round numbers to attract action at 50/50 lines."
                ),
                "confidence_penalty": round(penalty, 1),
                "negative_factors": negative_factors,
                "positive_factors": positive_factors,
            }

    # --- Check Trap Pattern 1: Line too LOW + multiple negative factors ---
    # "Bait OVER" trap: line looks like easy over, but negatives will sink it
    if gap_pct <= -10.0 and len(negative_factors) >= 2:
        penalty = min(15.0, 8.0 + len(negative_factors) * 2.0)
        return {
            "is_trap": True,
            "trap_type": "under_trap",
            "warning_message": (
                f"⚠️ Possible Trap Line: Line is {abs(gap_pct):.1f}% BELOW season avg "
                f"({season_average:.1f}) — looks like easy OVER, but {len(negative_factors)} "
                f"negative factors may cancel the edge."
            ),
            "confidence_penalty": round(penalty, 1),
            "negative_factors": negative_factors,
            "positive_factors": positive_factors,
        }

    # --- Check Trap Pattern 2: Line too HIGH + multiple positive factors ---
    # "Bait UNDER" trap: line looks hard to exceed, but positives will carry it
    if gap_pct >= 10.0 and len(positive_factors) >= 2:
        penalty = min(10.0, 5.0 + len(positive_factors) * 1.5)
        return {
            "is_trap": True,
            "trap_type": "over_trap",
            "warning_message": (
                f"⚠️ Possible Trap Line: Line is {gap_pct:.1f}% ABOVE season avg "
                f"({season_average:.1f}) — looks tough to hit, but {len(positive_factors)} "
                f"positive factors may carry the OVER."
            ),
            "confidence_penalty": round(penalty, 1),
            "negative_factors": negative_factors,
            "positive_factors": positive_factors,
        }

    return {
        "is_trap": False,
        "trap_type": None,
        "warning_message": "",
        "confidence_penalty": 0.0,
        "negative_factors": negative_factors,
        "positive_factors": positive_factors,
    }

# ============================================================
# END SECTION: Trap Line Detection
# ============================================================


# ============================================================
# SECTION: Confidence-Adjusted Edge and Coin-Flip Detection
# ============================================================

def calculate_confidence_adjusted_edge(raw_edge_pct, confidence_score):
    """
    Calculate the confidence-adjusted edge by scaling raw edge by confidence.

    BEGINNER NOTE: A 15% raw edge from an unreliable model is worth less than
    a 10% edge from a highly confident model. This function scales the edge
    by the model's confidence level to give a more accurate picture.

    Formula: adjusted_edge = raw_edge * (confidence_score / 100)

    Args:
        raw_edge_pct (float): Raw edge percentage (e.g. 12.5 for 12.5%)
        confidence_score (float): Model confidence score 0-100

    Returns:
        float: Confidence-adjusted edge percentage

    Example:
        calculate_confidence_adjusted_edge(15.0, 60) → 9.0%
        calculate_confidence_adjusted_edge(10.0, 85) → 8.5%
    """
    if confidence_score <= 0:
        return 0.0
    adjusted = raw_edge_pct * (max(0.0, min(100.0, confidence_score)) / 100.0)
    return round(adjusted, 3)


def detect_coin_flip(projection, prop_line, stat_std, stat_type=None):
    """
    Detect when a projection is so close to the line that it's essentially a coin flip.

    BEGINNER NOTE: When the model's projection and the betting line are within
    0.3 standard deviations of each other, the outcome is highly uncertain —
    essentially a 50/50 bet that should be avoided regardless of other signals.
    There's no real edge to exploit here.

    Args:
        projection (float): Model's projected stat value
        prop_line (float): The betting line
        stat_std (float): Standard deviation of the stat
        stat_type (str, optional): Stat type for description

    Returns:
        dict: {
            'is_coin_flip': bool,
            'std_devs_from_line': float,
            'message': str,
        }

    Example:
        # Player projects 24.8 points, line is 24.5, std is 6.0
        # Gap = 0.3 / 6.0 = 0.05 std devs → coin flip
        detect_coin_flip(24.8, 24.5, 6.0, 'points')
        → {'is_coin_flip': True, 'std_devs_from_line': 0.05, ...}
    """
    COIN_FLIP_THRESHOLD = 0.3  # Less than 0.3 std devs = coin flip

    if stat_std <= 0 or prop_line <= 0:
        return {"is_coin_flip": False, "std_devs_from_line": 0.0, "message": ""}

    std_devs = abs(projection - prop_line) / stat_std

    if std_devs < COIN_FLIP_THRESHOLD:
        stat_desc = stat_type.title() if stat_type else "Stat"
        msg = (
            f"🪙 COIN FLIP — AVOID: {stat_desc} projection ({projection:.1f}) is only "
            f"{std_devs:.2f}σ from the line ({prop_line}). This is essentially a 50/50 "
            f"flip — no meaningful edge exists at this separation."
        )
        return {
            "is_coin_flip": True,
            "std_devs_from_line": round(std_devs, 3),
            "message": msg,
        }

    return {
        "is_coin_flip": False,
        "std_devs_from_line": round(std_devs, 3),
        "message": "",
    }


def calculate_weighted_net_force(directional_forces_result):
    """
    Calculate a weighted net force score where force strength matters.

    BEGINNER NOTE: The current system counts forces equally, but a
    "Strong OVER force" from game pace should count more than a
    "Weak OVER force" from home court advantage. This function weights
    forces by their impact magnitude.

    Force strength mapping:
        strength >= 2.0 → "strong" (weight 1.0)
        strength >= 1.0 → "moderate" (weight 0.6)
        strength <  1.0 → "weak" (weight 0.3)

    Args:
        directional_forces_result (dict): Output of analyze_directional_forces

    Returns:
        dict: {
            'weighted_over_score': float,
            'weighted_under_score': float,
            'weighted_net': float (positive = OVER favored),
            'dominant_direction': str ('OVER' | 'UNDER'),
        }

    Example:
        Forces: 1 strong OVER (2.5), 1 weak UNDER (0.4)
        weighted_over = 1.0, weighted_under = 0.3 * 0.4 / 1.0 ≈ 0.12
        → net = 0.88 in favor of OVER
    """
    def _strength_weight(s):
        """Convert force strength to a normalized weight."""
        if s >= 2.0:
            return 1.0   # Strong force
        elif s >= 1.0:
            return 0.6   # Moderate force
        else:
            return 0.3   # Weak force

    over_forces  = directional_forces_result.get("over_forces",  [])
    under_forces = directional_forces_result.get("under_forces", [])

    weighted_over = sum(
        _strength_weight(f.get("strength", 0)) * f.get("strength", 0)
        for f in over_forces
    )
    weighted_under = sum(
        _strength_weight(f.get("strength", 0)) * f.get("strength", 0)
        for f in under_forces
    )

    net = weighted_over - weighted_under
    dominant = "OVER" if net >= 0 else "UNDER"

    return {
        "weighted_over_score": round(weighted_over, 3),
        "weighted_under_score": round(weighted_under, 3),
        "weighted_net": round(net, 3),
        "dominant_direction": dominant,
    }


# ============================================================
# END SECTION: Confidence-Adjusted Edge and Coin-Flip Detection
# ============================================================


# ============================================================
# SECTION: Goblin / Demon Bet Classification
# BEGINNER NOTE: "Goblin bets" are slam-dunk easy-money plays
# where the model's projection is FAR above/below the line.
# "Demon bets" are trap plays that LOOK good but have hidden
# risks that make them dangerous to bet.
# ============================================================

# Thresholds for Goblin classification
GOBLIN_MIN_STD_DEVS_FROM_LINE = 2.0   # Projection must be ≥2 std devs from line
GOBLIN_MIN_PROBABILITY        = 0.80   # Model probability must be ≥80%
GOBLIN_MIN_EDGE               = 25.0   # Edge must be ≥25%

# Line-reliability thresholds for Goblin validation.
# A Goblin requires a REAL platform line, not a synthetic/default one.
# If the prop_line is 0, wildly low (< 25% of season avg), or wildly high
# (> 4× season avg), we treat it as an unverified synthetic line and refuse
# to award the Goblin badge — garbage-in/garbage-out prevention.
GOBLIN_LINE_MIN_RATIO = 0.25   # Line must be ≥25% of season average
GOBLIN_LINE_MAX_RATIO = 4.0    # Line must be ≤4× the season average

# Thresholds for Demon classification
DEMON_CONFLICT_RATIO_THRESHOLD = 0.80   # Forces within 20% of each other = conflicting
DEMON_HIGH_VAR_MAX_EDGE        = 8.0    # High-variance stats with edge <8% = demon
DEMON_HIGH_VAR_STATS           = {"threes", "steals", "blocks"}
DEMON_BLOWOUT_SPREAD_THRESHOLD = 10.0   # Spread >10 pts on a back-to-back = demon
DEMON_HOT_STREAK_RATIO         = 1.25   # Line at 125%+ of season avg = likely regressing hot streak


def classify_bet_type(
    probability_over,
    edge_percentage,
    stat_standard_deviation,
    projected_stat,
    prop_line,
    stat_type,
    directional_forces_result,
    rest_days=1,
    vegas_spread=0.0,
    recent_form_ratio=None,
    season_average=None,
    line_source=None,
):
    """
    Classify a prop bet as a Goblin 🧌, Demon 👿, or Normal bet.

    Goblin bets are extreme edges — the model's projection is so far
    from the line that it represents a near-guaranteed outcome.  These
    are the "easy money" plays that books occasionally leave open.

    Demon bets are dangerous traps — they look appealing on the surface
    but have hidden structural risks that make them likely losers.

    A Goblin classification is BLOCKED when the prop_line looks synthetic
    or unreliable (zero, wildly below/above the player's season average).
    This prevents garbage-in/garbage-out misclassifications caused by
    stale, default, or auto-generated lines.

    Args:
        probability_over (float): Model P(over), 0–1
        edge_percentage (float): Edge %, positive = lean OVER
        stat_standard_deviation (float): Distribution width
        projected_stat (float): Model's projected value
        prop_line (float): The betting line
        stat_type (str): 'points', 'rebounds', 'threes', etc.
        directional_forces_result (dict): Output of analyze_directional_forces
        rest_days (int): Days since last game (0 = back-to-back)
        vegas_spread (float): Point spread, positive = team favored
        recent_form_ratio (float or None): Recent form (>1 = hot, <1 = cold)
        season_average (float or None): Player's season average for this stat
        line_source (str or None): Where the line came from (e.g. 'PrizePicks',
            'Underdog', 'DraftKings', 'synthetic').  'synthetic' (or None with
            a suspicious line) will block Goblin classification.

    Returns:
        dict: {
            'bet_type': 'goblin' | 'demon' | 'normal',
            'bet_type_emoji': '🧌' | '👿' | '',
            'bet_type_label': str,
            'goblin': bool,
            'demon': bool,
            'reasons': list[str],    # Why it's a goblin/demon
            'std_devs_from_line': float,   # How many std devs projection is from line
            'line_verified': bool,         # False if line looks synthetic/unreliable
            'line_reliability_warning': str | None,  # Human-readable warning if unverified
        }

    Example (Goblin):
        Line 12.5 pts, projection 28 pts, std 7 → 2.2 std devs above line,
        probability 88%, edge 38% → Goblin 🧌

    Example (Demon):
        Back-to-back + spread 14 pts → blowout + fatigue → Demon 👿
    """
    stat_type_lower = str(stat_type).lower() if stat_type else ""

    # ── Compute how many std devs the projection is from the line ──
    std_devs_from_line = 0.0
    if stat_standard_deviation > 0 and prop_line > 0:
        std_devs_from_line = (projected_stat - prop_line) / stat_standard_deviation

    # ── Determine actual model direction ──
    direction = "OVER" if edge_percentage >= 0 else "UNDER"
    # Correct sign: if recommending UNDER, favorable distance is negative
    favorable_std_devs = std_devs_from_line if direction == "OVER" else -std_devs_from_line

    # ============================================================
    # LINE RELIABILITY CHECK
    # Before classifying as a Goblin we verify that prop_line is a
    # real, fetched line — not a synthetic/default value (e.g. season
    # average rounded to 0.5, or a stale placeholder).
    #
    # A line is considered UNVERIFIED if:
    #   - It is zero or negative (clearly missing/default)
    #   - It is explicitly tagged as 'synthetic' via line_source
    #   - It is < 25% of the season average (implausibly low)
    #   - It is > 4× the season average (implausibly high)
    # ============================================================
    line_verified = True
    line_reliability_warning = None

    _line_source_lower = str(line_source).lower() if line_source else ""
    if prop_line <= 0:
        line_verified = False
        line_reliability_warning = (
            "Prop line is zero or missing — cannot verify Goblin classification"
        )
    elif _line_source_lower in ("synthetic", "estimated", "default", ""):
        # Only flag as unverified if we also have a season average to compare
        if season_average is not None and season_average > 0:
            line_ratio = prop_line / season_average
            if line_ratio < GOBLIN_LINE_MIN_RATIO:
                line_verified = False
                line_reliability_warning = (
                    f"Prop line ({prop_line}) is only {line_ratio*100:.0f}% of season "
                    f"average ({season_average:.1f}) — likely a synthetic/default line; "
                    "Goblin classification withheld"
                )
            elif line_ratio > GOBLIN_LINE_MAX_RATIO:
                line_verified = False
                line_reliability_warning = (
                    f"Prop line ({prop_line}) is {line_ratio:.1f}× the season "
                    f"average ({season_average:.1f}) — implausibly high, likely a "
                    "synthetic/default line; Goblin classification withheld"
                )
    elif season_average is not None and season_average > 0:
        # Even for platform-sourced lines, flag if wildly off from season avg
        line_ratio = prop_line / season_average
        if line_ratio < GOBLIN_LINE_MIN_RATIO:
            line_verified = False
            line_reliability_warning = (
                f"Prop line ({prop_line}) is only {line_ratio*100:.0f}% of season "
                f"average ({season_average:.1f}) — unreliable line; "
                "Goblin classification withheld"
            )
        elif line_ratio > GOBLIN_LINE_MAX_RATIO:
            line_verified = False
            line_reliability_warning = (
                f"Prop line ({prop_line}) is {line_ratio:.1f}× the season "
                f"average ({season_average:.1f}) — unreliable line; "
                "Goblin classification withheld"
            )

    # ============================================================
    # GOBLIN CHECK
    # A "Goblin bet" requires ALL three conditions to be met:
    #   1. Projection is ≥2 std devs from the line in favorable direction
    #   2. Probability is ≥80%
    #   3. Edge is ≥25%
    #   4. The prop_line must be verified (not synthetic/default)
    # ============================================================
    is_goblin = False
    goblin_reasons = []

    prob_for_direction = probability_over if direction == "OVER" else (1.0 - probability_over)
    abs_edge = abs(edge_percentage)

    if (
        line_verified
        and favorable_std_devs >= GOBLIN_MIN_STD_DEVS_FROM_LINE
        and prob_for_direction >= GOBLIN_MIN_PROBABILITY
        and abs_edge >= GOBLIN_MIN_EDGE
    ):
        is_goblin = True
        goblin_reasons.append(
            f"Projection ({projected_stat:.1f}) is {favorable_std_devs:.1f}σ "
            f"beyond the line ({prop_line}) — extreme separation"
        )
        goblin_reasons.append(
            f"Model probability: {prob_for_direction*100:.0f}% "
            f"(threshold: {GOBLIN_MIN_PROBABILITY*100:.0f}%)"
        )
        goblin_reasons.append(
            f"Edge: {abs_edge:.1f}% (threshold: {GOBLIN_MIN_EDGE:.0f}%)"
        )

    if is_goblin:
        return {
            "bet_type":        "goblin",
            "bet_type_emoji":  "🧌",
            "bet_type_label":  "Goblin Bet — Easy Money",
            "goblin":          True,
            "demon":           False,
            "reasons":         goblin_reasons,
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   True,
            "line_reliability_warning": None,
        }

    # ============================================================
    # DEMON CHECK
    # A "Demon bet" qualifies if ANY of the four risk patterns apply.
    # ============================================================
    demon_reasons = []

    # Pattern 1: Conflicting directional forces (nearly 50/50 split)
    over_strength  = directional_forces_result.get("over_strength",  0)
    under_strength = directional_forces_result.get("under_strength", 0)
    if over_strength > 0 and under_strength > 0:
        conflict_ratio = min(over_strength, under_strength) / max(over_strength, under_strength)
        if conflict_ratio >= DEMON_CONFLICT_RATIO_THRESHOLD:
            demon_reasons.append(
                f"Conflicting forces: OVER ({over_strength:.1f}) vs UNDER ({under_strength:.1f}) "
                f"are nearly balanced ({conflict_ratio*100:.0f}% overlap) — no clear edge direction"
            )

    # Pattern 2: High-variance stat type with low edge
    if stat_type_lower in DEMON_HIGH_VAR_STATS and abs_edge < DEMON_HIGH_VAR_MAX_EDGE:
        demon_reasons.append(
            f"{stat_type_lower.title()} is a high-variance stat with only {abs_edge:.1f}% edge "
            f"(threshold: {DEMON_HIGH_VAR_MAX_EDGE:.0f}%) — too unpredictable to bet with low edge"
        )

    # Pattern 3: Back-to-back with large blowout spread
    is_back_to_back = rest_days == 0
    abs_spread = abs(vegas_spread)
    if is_back_to_back and abs_spread > DEMON_BLOWOUT_SPREAD_THRESHOLD:
        demon_reasons.append(
            f"Back-to-back game (rest_days=0) with a {abs_spread:.0f}-pt spread — "
            "blowout + fatigue combo is a significant risk for missing this stat"
        )

    # Pattern 4: Line set at recent hot streak value likely to regress
    # If recent form ratio is very high (player on hot streak) AND the line
    # is already pushed up to match that hot streak, regression is likely.
    if (
        recent_form_ratio is not None
        and recent_form_ratio >= DEMON_HOT_STREAK_RATIO
        and season_average is not None
        and season_average > 0
        and prop_line > 0
    ):
        # The line is inflated to match the hot streak — but the hot streak
        # itself makes it a regression candidate
        line_vs_avg_ratio = prop_line / season_average if season_average > 0 else 1.0
        if line_vs_avg_ratio >= DEMON_HOT_STREAK_RATIO:
            demon_reasons.append(
                f"Line ({prop_line}) inflated to match recent hot streak "
                f"(recent form {recent_form_ratio:.2f}x, season avg {season_average:.1f}) — "
                f"hot streaks regress; line is priced at peak, not true average"
            )

    is_demon = len(demon_reasons) > 0

    if is_demon:
        return {
            "bet_type":        "demon",
            "bet_type_emoji":  "👿",
            "bet_type_label":  "Demon Bet — Dangerous Trap",
            "goblin":          False,
            "demon":           True,
            "reasons":         demon_reasons,
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   line_verified,
            "line_reliability_warning": line_reliability_warning,
        }

    # Normal bet — no special classification
    return {
        "bet_type":        "normal",
        "bet_type_emoji":  "",
        "bet_type_label":  "Normal Bet",
        "goblin":          False,
        "demon":           False,
        "reasons":         [],
        "std_devs_from_line": round(std_devs_from_line, 2),
        "line_verified":   line_verified,
        "line_reliability_warning": line_reliability_warning,
    }


# ============================================================
# END SECTION: Goblin / Demon Bet Classification
# ============================================================
