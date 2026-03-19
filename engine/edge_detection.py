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

# Per-stat minimum edge thresholds (2D).
# Different stats have different variance levels — require proportionally more edge.
# Higher-variance stats need larger edges to overcome noise.
STAT_EDGE_THRESHOLDS = {
    "points": 2.5,
    "rebounds": 3.0,
    "assists": 3.0,
    "threes": 4.0,
    "steals": 5.0,
    "blocks": 5.0,
    "turnovers": 4.0,
    "points_rebounds_assists": 2.0,
    "points_rebounds": 2.0,
    "points_assists": 2.0,
    "rebounds_assists": 2.5,
    "blocks_steals": 4.0,
    "fantasy_score_pp": 2.0,
    "fantasy_score_dk": 2.0,
    "fantasy_score_ud": 2.0,
}

# Low-volume stat types with inherently higher variance.
# These require a larger raw edge to overcome uncertainty.
LOW_VOLUME_STATS = {"steals", "blocks", "turnovers", "threes"}

# Uncertainty multiplier applied to low-volume stats' edge calculations.
# 1.3x means a steal prop needs effectively 1.3x more edge to qualify.
LOW_VOLUME_UNCERTAINTY_MULTIPLIER = 1.3  # softened from 1.5 to reduce over-penalizing secondary stats

# Conflict severity threshold for "high conflict" force detection (2E).
# When min(over, under) / max(over, under) exceeds this, forces are considered
# in high conflict (both sides nearly equal strength with significant magnitude).
CONFLICT_SEVERITY_HIGH_THRESHOLD = 0.7  # was inline magic number 0.7


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
    platform_lines=None,
    recent_form_ratio=None,
) -> dict:
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
        platform_lines (dict or None): Optional mapping of platform name
            to posted line (e.g. {'DraftKings': 24.5, 'FanDuel': 25.0}).
            Used for Market Consensus force (2A).
        recent_form_ratio (float or None): Ratio of recent-game average to
            season average (e.g. 1.25 = running 25% above average).
            Used for Regression-to-Mean force (2F).

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
            'conflict_severity': float (0-1, 1=perfectly balanced forces)
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

    # --- Force 9: Market Consensus (2A) ---
    # When multiple platforms post different lines, consensus shows the "true" line.
    # A prop line far below consensus = OVER value; far above consensus = UNDER value.
    if platform_lines and len(platform_lines) >= 2:
        platform_values = [float(v) for v in platform_lines.values() if v is not None]
        if len(platform_values) >= 2:
            consensus_line = sum(platform_values) / len(platform_values)
            if consensus_line > 0:
                gap_pct = (consensus_line - prop_line) / consensus_line * 100.0
                if gap_pct > 5.0:
                    # Prop line is more than 5% BELOW consensus → OVER value
                    strength = min(2.0, gap_pct / 5.0)
                    all_over_forces.append({
                        "name": "Market Consensus",
                        "description": (
                            f"Line ({prop_line}) is {gap_pct:.1f}% below cross-platform "
                            f"consensus ({consensus_line:.2f}) — potential mispriced line"
                        ),
                        "strength": round(strength, 2),
                        "direction": "OVER",
                    })
                elif gap_pct < -5.0:
                    # Prop line is more than 5% ABOVE consensus → UNDER value
                    strength = min(2.0, abs(gap_pct) / 5.0)
                    all_under_forces.append({
                        "name": "Market Consensus",
                        "description": (
                            f"Line ({prop_line}) is {abs(gap_pct):.1f}% above cross-platform "
                            f"consensus ({consensus_line:.2f}) — line may be inflated"
                        ),
                        "strength": round(strength, 2),
                        "direction": "UNDER",
                    })

    # --- Force 10: Regression to Mean (2F) ---
    # Players running significantly above/below their season average tend to revert.
    # This is one of the most reliable phenomena in sports statistics.
    _recent_form = recent_form_ratio if recent_form_ratio is not None else projection_result.get("recent_form_ratio", None)
    if _recent_form is not None:
        try:
            _recent_form = float(_recent_form)
        except (TypeError, ValueError):
            _recent_form = None
    if _recent_form is not None:
        if _recent_form > 1.20:
            # Running 20%+ above average — regression to mean is likely
            strength = min(1.5, (_recent_form - 1.0) * 3.0)
            all_under_forces.append({
                "name": "Regression Risk",
                "description": (
                    f"Running {(_recent_form - 1.0) * 100:.0f}% above season average — "
                    "regression to the mean is likely"
                ),
                "strength": round(strength, 2),
                "direction": "UNDER",
            })
        elif _recent_form < 0.80:
            # Running 20%+ below average — bounce-back expected
            strength = min(1.2, (1.0 - _recent_form) * 2.5)
            all_over_forces.append({
                "name": "Bounce-Back",
                "description": (
                    f"Running {(1.0 - _recent_form) * 100:.0f}% below season average — "
                    "bounce-back toward average expected"
                ),
                "strength": round(strength, 2),
                "direction": "OVER",
            })

    # ============================================================
    # SECTION: Summarize Forces
    # ============================================================

    # Count and sum strength of over/under forces
    over_count = len(all_over_forces)
    under_count = len(all_under_forces)
    over_total_strength = sum(f["strength"] for f in all_over_forces)
    under_total_strength = sum(f["strength"] for f in all_under_forces)

    # --- Conflict Severity Score (2E) ---
    # Measures how evenly matched the opposing forces are.
    # 1.0 = perfectly balanced (maximum conflict), 0 = one-sided
    if over_total_strength > 0 and under_total_strength > 0:
        conflict_severity = min(over_total_strength, under_total_strength) / max(over_total_strength, under_total_strength)
    else:
        conflict_severity = 0.0

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
        "conflict_severity": round(conflict_severity, 3),
    }

    # ============================================================
    # END SECTION: Summarize Forces
    # ============================================================


# ============================================================
# SECTION: Closing Line Value (2B)
# ============================================================

def estimate_closing_line_value(current_line, model_projection, hours_to_game=None):
    """
    Estimate the closing line value (CLV) for a prop bet. (2B)

    CLV is the gold standard of sharp betting: did your line beat where
    the market eventually closed? A positive CLV means you got a better
    number than the closing line — a strong indicator of long-term edge.

    BEGINNER NOTE: Lines move as sharp bettors place wagers. The closing
    line is the final line right before tip-off, after all professional
    money has been processed. If you got 24.5 and it closes at 26.0,
    you "beat the closing line" — you had better information than the
    eventual market consensus.

    Args:
        current_line (float): The line you can bet right now
        model_projection (float): Our model's projected value for the stat
        hours_to_game (float or None): Hours until tip-off. When < 2,
            less line movement is expected (market more locked in).

    Returns:
        dict: {
            'estimated_closing_line': float,
            'clv_edge': float,    # positive = you beat the close
            'is_positive_clv': bool,
        }

    Example:
        current_line=24.5, model_projection=27.0, hours_to_game=6
        → estimated_close = 24.5*0.3 + 27.0*0.7 = 26.25
        → clv_edge = 24.5 - 26.25 = -1.75  (negative = you DON'T beat close)
        Flip: current_line=27.0, model_projection=24.5
        → clv_edge = 27.0 - 25.25 = +1.75  (positive CLV — you beat close)
    """
    if current_line <= 0 or model_projection <= 0:
        return {
            "estimated_closing_line": current_line,
            "clv_edge": 0.0,
            "is_positive_clv": False,
        }

    if hours_to_game is not None and hours_to_game < 2:
        # Close to game — less line movement expected
        estimated_close = current_line * 0.6 + model_projection * 0.4
    else:
        # Standard: lines move significantly toward the true value
        estimated_close = current_line * 0.3 + model_projection * 0.7

    # CLV edge: positive = you're getting a better line than where it will close
    clv_edge = current_line - estimated_close

    return {
        "estimated_closing_line": round(estimated_close, 3),
        "clv_edge": round(clv_edge, 3),
        "is_positive_clv": clv_edge > 0,
    }


# ============================================================
# SECTION: Dynamic Vig (2C)
# ============================================================

def calculate_dynamic_vig(over_odds=None, under_odds=None, platform=None):
    """
    Calculate the dynamic vig percentage for a prop bet. (2C)

    Different platforms have different vig structures:
    - PrizePicks/Underdog: 0% per-leg vig (profit is in payout structure)
    - DraftKings with real odds: actual vig from the juice
    - Default: 2.38% (standard -110/-110 lines)

    BEGINNER NOTE: Vig (or "juice") is the sportsbook's fee. At -110/-110,
    the breakeven is 52.38% (not 50%). Subtracting the vig from our edge
    gives the TRUE edge we need to overcome to be profitable.

    Args:
        over_odds (float or None): American odds on the over (e.g. -110, +120)
        under_odds (float or None): American odds on the under
        platform (str or None): Platform name ('PrizePicks', 'Underdog',
            'DraftKings', etc.)

    Returns:
        float: Vig percentage (0.0 to ~5.0)

    Example:
        calculate_dynamic_vig(platform="PrizePicks") → 0.0
        calculate_dynamic_vig(-110, -110, "DraftKings") → 2.38
        calculate_dynamic_vig(-130, +110, "DraftKings") → ~3.5
    """
    _NO_VIG_PLATFORMS = {"PrizePicks", "Underdog", "Underdog Fantasy"}
    if platform and platform in _NO_VIG_PLATFORMS:
        return 0.0

    if over_odds is not None and under_odds is not None:
        try:
            o = float(over_odds)
            u = float(under_odds)
            # Convert American odds to implied probabilities
            def _implied(odds):
                if odds < 0:
                    return abs(odds) / (abs(odds) + 100.0)
                else:
                    return 100.0 / (odds + 100.0)
            total_implied = _implied(o) + _implied(u)
            # Vig = excess implied probability above 1.0, expressed as a percentage
            return round(max(0.0, (total_implied - 1.0) * 100.0), 3)
        except (ValueError, TypeError):
            pass

    # Fallback: standard -110/-110 vig = 2.38%
    return 2.38


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
) -> dict:
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
    elif platform is None:
        # No platform specified → treat as DFS (no per-leg vig)
        effective_vig = 0.0
    elif over_odds is not None and over_odds != -110:
        # Derive vig from actual DraftKings odds (e.g. -130 → breakeven 56.5%)
        # Vig = implied_prob - 0.5 (excess above fair 50/50)
        try:
            _odds = float(over_odds)
            _implied = abs(_odds) / (abs(_odds) + 100.0) if _odds < 0 else 100.0 / (_odds + 100.0)
            effective_vig = max(0.0, (_implied - 0.5) * 100.0)
        except (ValueError, TypeError):
            effective_vig = VIG_ADJUSTMENT_PCT
    elif over_odds == -110:
        # Standard -110 odds → standard vig
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
    # Use per-stat threshold if available, else fall back to MIN_EDGE_AFTER_VIG
    _stat_min_edge = STAT_EDGE_THRESHOLDS.get(stat_type_lower, MIN_EDGE_AFTER_VIG)
    if effective_edge < _stat_min_edge:
        _vig_adj_display = max(0.0, vig_adjusted_edge)  # show 0 if negative to avoid confusion
        _vig_label = f"{effective_vig:.1f}% vig" if effective_vig > 0 else "no vig (PrizePicks/Underdog)"
        avoid_reasons.append(
            f"Insufficient edge after vig ({edge_percentage:.1f}% raw → "
            f"{_vig_adj_display:.1f}% after {_vig_label}) — "
            f"below {_stat_min_edge:.1f}% minimum for {stat_type_lower or 'this stat'}"
        )

    # Reason 2: High variance relative to line (too unpredictable)
    if stat_average > 0:
        coefficient_of_variation = stat_standard_deviation / stat_average
        if coefficient_of_variation > HIGH_VARIANCE_CV_THRESHOLD:
            avoid_reasons.append(
                f"High variance stat (CV={coefficient_of_variation:.2f}) — very unpredictable"
            )

    # Reason 3: Conflicting forces (2E enhanced)
    over_strength = directional_forces_result.get("over_strength", 0)
    under_strength = directional_forces_result.get("under_strength", 0)
    conflict_severity = directional_forces_result.get("conflict_severity", 0.0)
    if over_strength > 0 and under_strength > 0:
        if conflict_severity > CONFLICT_SEVERITY_HIGH_THRESHOLD and over_strength > 1.0 and under_strength > 1.0:
            avoid_reasons.append(
                f"High conflict severity ({conflict_severity:.2f}) — strong opposing signals "
                "on both sides with no clear direction"
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

def detect_line_sharpness(prop_line, season_average, stat_type="points") -> dict:
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
) -> dict:
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
# SECTION: Goblin / 50_50 / Demon Bet Classification
# BEGINNER NOTE:
# "Goblin bets" = alt lines BELOW the standard O/U — safe floor bets.
# "50/50 bets" = the standard Over/Under line itself — the baseline.
# "Demon bets" = alt lines ABOVE the standard O/U — high ceiling bets.
# Risk flags (conflicting forces, variance, fatigue, regression) are
# separate from classification and feed into the avoid-list system.
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

# Thresholds for Uncertain (risk-flag) detection
# These replace the old "Demon" classification thresholds — conflicting
# forces / variance / fatigue / regression are RISK FLAGS, not bet types.
UNCERTAIN_CONFLICT_RATIO_THRESHOLD = 0.80   # Forces within 20% of each other = conflicting
UNCERTAIN_HIGH_VAR_MAX_EDGE        = 8.0    # High-variance stats with edge <8% = uncertain
UNCERTAIN_HIGH_VAR_STATS           = {"threes", "steals", "blocks"}
UNCERTAIN_BLOWOUT_SPREAD_THRESHOLD = 10.0   # Spread >10 pts on a back-to-back = uncertain
UNCERTAIN_HOT_STREAK_RATIO         = 1.25   # Line at 125%+ of season avg = likely regressing

# Backward-compat aliases — old "DEMON_*" names still importable
DEMON_CONFLICT_RATIO_THRESHOLD = UNCERTAIN_CONFLICT_RATIO_THRESHOLD
DEMON_HIGH_VAR_MAX_EDGE        = UNCERTAIN_HIGH_VAR_MAX_EDGE
DEMON_HIGH_VAR_STATS           = UNCERTAIN_HIGH_VAR_STATS
DEMON_BLOWOUT_SPREAD_THRESHOLD = UNCERTAIN_BLOWOUT_SPREAD_THRESHOLD
DEMON_HOT_STREAK_RATIO         = UNCERTAIN_HOT_STREAK_RATIO


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
    # Optional threshold overrides — pulled from Settings page session state
    # when provided via st.session_state (pass None to use module constants).
    goblin_min_std_devs=None,
    goblin_min_probability=None,
    goblin_min_edge=None,
    demon_conflict_ratio=None,
    demon_regression_pct=None,
    # Line-position category from the ingestion layer (parse_alt_lines_from_platform_props).
    # PRIMARY classification driver when set:
    #   "goblin"   → line BELOW standard O/U  (safe floor)
    #   "50_50"    → the standard O/U line itself
    #   "standard" → alias for "50_50"
    #   "demon"    → line ABOVE standard O/U  (high ceiling)
    #   None       → no category available; fall back to statistical-only logic
    line_category=None,
    # Simulation percentile cutoffs — used to compute absolute floor/ceiling
    # boundaries that must NOT be bet past.  Populated from the Quantum Matrix
    # Engine output (percentile_10, percentile_90).
    sim_percentile_10=None,
    sim_percentile_90=None,
) -> dict:
    """
    Classify a prop bet as Goblin, 50/50, Demon, or Normal.

    Three-tier system (driven by line_category when provided):
      Goblin  — alternate line set BELOW the standard O/U (safe floor, high
                probability, lower payout).  Can also be awarded via
                statistical overlay when the model shows 2σ+, ≥80% prob,
                ≥25% edge on a standard line.
      50/50   — the standard Over/Under line itself (the baseline).
      Demon   — alternate line set ABOVE the standard O/U (high ceiling,
                lower probability, higher payout).

    Risk flags (conflicting forces, high variance, fatigue, regression) are
    computed independently and returned as ``risk_flags`` / ``is_uncertain``.
    They do NOT change the ``bet_type`` — they feed into the avoid-list system.

    A Goblin statistical overlay is BLOCKED when the prop_line looks
    synthetic or unreliable (zero, wildly below/above the player's season
    average) to prevent garbage-in/garbage-out misclassifications.

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
            a suspicious line) will block Goblin statistical overlay.
        line_category (str or None): Position of this line relative to the
            standard O/U — 'goblin', '50_50', 'standard', 'demon', or None.
        sim_percentile_10 (float or None): 10th-percentile simulation output
            (bad-game floor).  Used to compute the Goblin absolute floor.
        sim_percentile_90 (float or None): 90th-percentile simulation output
            (great-game ceiling).  Used to compute the Demon absolute ceiling.

    Returns:
        dict: {
            'bet_type': 'goblin' | '50_50' | 'demon' | 'normal',
            'bet_type_emoji': str,
            'bet_type_label': str,
            'goblin': bool,
            'demon': bool,   # True when bet_type == 'demon' (line above standard)
            '50_50': bool,
            'line_category': str | None,
            'risk_flags': list[str],   # conflicting-forces / uncertainty reasons
            'is_uncertain': bool,      # True when any risk flag is triggered
            'reasons': list[str],
            'std_devs_from_line': float,
            'line_verified': bool,
            'line_reliability_warning': str | None,
            'goblin_floor': float | None,   # Absolute floor — do NOT bet Goblin past this
            'demon_ceiling': float | None,  # Absolute ceiling — do NOT bet Demon past this
        }

    Example (Goblin via line_category):
        line_category='goblin' → Goblin Bet — Safe Floor immediately.

    Example (Demon via line_category):
        line_category='demon' → Demon Bet — High Ceiling immediately.

    Example (Goblin via statistical overlay):
        Standard line, projection 2.5σ above, probability 88%, edge 38%
        → statistical Goblin overlay triggered.

    Example (50/50 with risk flags):
        Standard line, back-to-back + spread 14 pts → is_uncertain=True,
        risk_flags populated, bet_type='50_50'.
    """
    stat_type_lower = str(stat_type).lower() if stat_type else ""

    # ── Apply optional threshold overrides from Settings page ────
    _goblin_std_thresh  = goblin_min_std_devs if goblin_min_std_devs is not None else GOBLIN_MIN_STD_DEVS_FROM_LINE
    _goblin_prob_thresh = goblin_min_probability if goblin_min_probability is not None else GOBLIN_MIN_PROBABILITY
    _goblin_edge_thresh = goblin_min_edge if goblin_min_edge is not None else GOBLIN_MIN_EDGE
    _uncertain_conflict  = demon_conflict_ratio if demon_conflict_ratio is not None else UNCERTAIN_CONFLICT_RATIO_THRESHOLD
    _uncertain_regression = demon_regression_pct if demon_regression_pct is not None else (UNCERTAIN_HOT_STREAK_RATIO * 100.0)

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

    # Normalise line_source; treat None / missing as unverified
    _line_source_lower = str(line_source).lower() if line_source is not None else ""
    _is_synthetic_source = _line_source_lower in (
        "", "synthetic", "estimated", "default", "none"
    )

    def _line_ratio_warning(ratio, avg, is_synthetic):
        """Return a human-readable warning for an out-of-range line ratio."""
        qualifier = "likely a synthetic/default line" if is_synthetic else "unreliable line"
        if ratio < GOBLIN_LINE_MIN_RATIO:
            return (
                f"Prop line ({prop_line}) is only {ratio*100:.0f}% of season "
                f"average ({avg:.1f}) — {qualifier}; "
                "Goblin classification withheld"
            )
        if ratio > GOBLIN_LINE_MAX_RATIO:
            return (
                f"Prop line ({prop_line}) is {ratio:.1f}× the season "
                f"average ({avg:.1f}) — {qualifier}; "
                "Goblin classification withheld"
            )
        return None  # Within acceptable bounds

    if prop_line <= 0:
        line_verified = False
        line_reliability_warning = (
            "Prop line is zero or missing — cannot verify Goblin classification"
        )
    elif season_average is not None and season_average > 0:
        # Check ratio for both synthetic and real-platform lines.
        # Synthetic sources get an additional benefit-of-the-doubt block
        # even if the ratio looks okay (we can't confirm it's real data).
        line_ratio = prop_line / season_average
        _ratio_warn = _line_ratio_warning(line_ratio, season_average, _is_synthetic_source)
        if _ratio_warn:
            line_verified = False
            line_reliability_warning = _ratio_warn

    # ============================================================
    # GOBLIN CHECK (statistical overlay for standard-line picks)
    # A "Goblin bet" requires ALL three conditions to be met:
    #   1. Projection is ≥2 std devs from the line in favorable direction
    #   2. Probability is ≥80%
    #   3. Edge is ≥25%
    #   4. The prop_line must be verified (not synthetic/default)
    # This check is applied for standard-line picks (line_category in
    # ("50_50", "standard", None)) and also for bare-goblin line_category
    # picks to confirm the badge. For line_category="goblin" the badge is
    # awarded by line position — stats criteria are not required.
    # ============================================================
    is_goblin = False
    goblin_reasons = []

    prob_for_direction = probability_over if direction == "OVER" else (1.0 - probability_over)
    abs_edge = abs(edge_percentage)

    if (
        line_verified
        and favorable_std_devs >= _goblin_std_thresh
        and prob_for_direction >= _goblin_prob_thresh
        and abs_edge >= _goblin_edge_thresh
    ):
        is_goblin = True
        goblin_reasons.append(
            f"Projection ({projected_stat:.1f}) is {favorable_std_devs:.1f}σ "
            f"beyond the line ({prop_line}) — extreme separation"
        )
        goblin_reasons.append(
            f"Model probability: {prob_for_direction*100:.0f}% "
            f"(threshold: {_goblin_prob_thresh*100:.0f}%)"
        )
        goblin_reasons.append(
            f"Edge: {abs_edge:.1f}% (threshold: {_goblin_edge_thresh:.0f}%)"
        )

    # ============================================================
    # RISK FLAGS (formerly "Demon check")
    # These four patterns detect structural uncertainty and are attached
    # to the result as `risk_flags` / `is_uncertain`. They do NOT change
    # `bet_type` — they feed into the avoid-list system via callers.
    # ============================================================
    risk_flags = []

    # Pattern 1: Conflicting directional forces (nearly 50/50 split)
    over_strength  = directional_forces_result.get("over_strength",  0)
    under_strength = directional_forces_result.get("under_strength", 0)
    if over_strength > 0 and under_strength > 0:
        conflict_ratio = min(over_strength, under_strength) / max(over_strength, under_strength)
        if conflict_ratio >= _uncertain_conflict:
            risk_flags.append(
                f"Conflicting forces: OVER ({over_strength:.1f}) vs UNDER ({under_strength:.1f}) "
                f"are nearly balanced ({conflict_ratio*100:.0f}% overlap) — no clear edge direction"
            )

    # Pattern 2: High-variance stat type with low edge
    if stat_type_lower in UNCERTAIN_HIGH_VAR_STATS and abs_edge < UNCERTAIN_HIGH_VAR_MAX_EDGE:
        risk_flags.append(
            f"{stat_type_lower.title()} is a high-variance stat with only {abs_edge:.1f}% edge "
            f"(threshold: {UNCERTAIN_HIGH_VAR_MAX_EDGE:.0f}%) — too unpredictable to bet with low edge"
        )

    # Pattern 3: Back-to-back with large blowout spread
    is_back_to_back = rest_days == 0
    abs_spread = abs(vegas_spread)
    if is_back_to_back and abs_spread > UNCERTAIN_BLOWOUT_SPREAD_THRESHOLD:
        risk_flags.append(
            f"Back-to-back game (rest_days=0) with a {abs_spread:.0f}-pt spread — "
            "blowout + fatigue combo is a significant risk for missing this stat"
        )

    # Pattern 4: Line set at recent hot streak value likely to regress
    _hot_streak_ratio_threshold = _uncertain_regression / 100.0  # convert pct → ratio
    if (
        recent_form_ratio is not None
        and recent_form_ratio >= _hot_streak_ratio_threshold
        and season_average is not None
        and season_average > 0
        and prop_line > 0
    ):
        line_vs_avg_ratio = prop_line / season_average if season_average > 0 else 1.0
        if line_vs_avg_ratio >= _hot_streak_ratio_threshold:
            risk_flags.append(
                f"Line ({prop_line}) inflated to match recent hot streak "
                f"(recent form {recent_form_ratio:.2f}x, season avg {season_average:.1f}) — "
                f"hot streaks regress; line is priced at peak, not true average"
            )

    is_uncertain = len(risk_flags) > 0

    # ============================================================
    # SIMULATOR CUTOFF COMPUTATION — Goblin Floor & Demon Ceiling
    # ============================================================
    # Goblin floor = p10 − 1σ  (the absolute mathematical floor;
    #   a Goblin line below this value is statistically unsafe).
    # Demon ceiling = p90 + 1σ  (the absolute mathematical ceiling;
    #   a Demon line above this value requires near-impossible performance).
    _goblin_floor = None
    _demon_ceiling = None
    _safe_std = stat_standard_deviation if stat_standard_deviation > 0 else 0.0
    if sim_percentile_10 is not None:
        _goblin_floor = round(sim_percentile_10 - _safe_std, 1)
        if _goblin_floor < 0:
            _goblin_floor = 0.0
    if sim_percentile_90 is not None:
        _demon_ceiling = round(sim_percentile_90 + _safe_std, 1)

    # ============================================================
    # PRIMARY CLASSIFICATION — driven by line_category
    # ============================================================
    _norm_category = str(line_category).lower() if line_category is not None else None

    if _norm_category == "goblin":
        # Alt line BELOW standard O/U — Goblin Bet (safe floor)
        return {
            "bet_type":        "goblin",
            "bet_type_emoji":  "Goblin",
            "bet_type_label":  "Goblin Bet — Safe Floor",
            "goblin":          True,
            "demon":           False,
            "50_50":           False,
            "line_category":   line_category,
            "risk_flags":      risk_flags,
            "is_uncertain":    is_uncertain,
            "reasons":         goblin_reasons if goblin_reasons else ["Alt line set BELOW the standard O/U — safe floor"],
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   line_verified,
            "line_reliability_warning": line_reliability_warning,
            "goblin_floor":    _goblin_floor,
            "demon_ceiling":   _demon_ceiling,
        }

    if _norm_category == "demon":
        # Alt line ABOVE standard O/U — Demon Bet (high ceiling)
        return {
            "bet_type":        "demon",
            "bet_type_emoji":  "Demon",
            "bet_type_label":  "Demon Bet — High Ceiling",
            "goblin":          False,
            "demon":           True,  # True = real Demon (line above standard O/U)
            "50_50":           False,
            "line_category":   line_category,
            "risk_flags":      risk_flags,
            "is_uncertain":    is_uncertain,
            "reasons":         ["Alt line set ABOVE the standard O/U — high ceiling"],
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   line_verified,
            "line_reliability_warning": line_reliability_warning,
            "goblin_floor":    _goblin_floor,
            "demon_ceiling":   _demon_ceiling,
        }

    # line_category is "50_50", "standard", or None —
    # standard-line pick.  Goblin statistical overlay applies here.
    if is_goblin:
        return {
            "bet_type":        "goblin",
            "bet_type_emoji":  "Goblin",
            "bet_type_label":  "Goblin Bet — Safe Floor",
            "goblin":          True,
            "demon":           False,
            "50_50":           False,
            "line_category":   line_category,
            "risk_flags":      risk_flags,
            "is_uncertain":    is_uncertain,
            "reasons":         goblin_reasons,
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   True,
            "line_reliability_warning": None,
            "goblin_floor":    _goblin_floor,
            "demon_ceiling":   _demon_ceiling,
        }

    if _norm_category in ("50_50", "standard"):
        # Standard sportsbook line — 50/50 Bet
        return {
            "bet_type":        "50_50",
            "bet_type_emoji":  "50/50",
            "bet_type_label":  "50/50 Bet — Standard Line",
            "goblin":          False,
            "demon":           False,
            "50_50":           True,
            "line_category":   line_category,
            "risk_flags":      risk_flags,
            "is_uncertain":    is_uncertain,
            "reasons":         risk_flags,
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   line_verified,
            "line_reliability_warning": line_reliability_warning,
            "goblin_floor":    _goblin_floor,
            "demon_ceiling":   _demon_ceiling,
        }

    # line_category is None — backward-compatible path (synthetic / no category).
    # Return "50_50" when risk flags present (old behavior), else "normal".
    # Note: label is "Standard Line" for consistency with the explicit 50_50/standard
    # path; is_uncertain=True signals the risk flags via the separate risk_flags key.
    if is_uncertain:
        return {
            "bet_type":        "50_50",
            "bet_type_emoji":  "50/50",
            "bet_type_label":  "50/50 Bet — Standard Line",
            "goblin":          False,
            "demon":           False,
            "50_50":           True,
            "line_category":   line_category,
            "risk_flags":      risk_flags,
            "is_uncertain":    True,
            "reasons":         risk_flags,
            "std_devs_from_line": round(std_devs_from_line, 2),
            "line_verified":   line_verified,
            "line_reliability_warning": line_reliability_warning,
            "goblin_floor":    _goblin_floor,
            "demon_ceiling":   _demon_ceiling,
        }

    # Normal bet — no special classification
    return {
        "bet_type":        "normal",
        "bet_type_emoji":  "",
        "bet_type_label":  "Normal Bet",
        "goblin":          False,
        "demon":           False,
        "50_50":           False,
        "line_category":   line_category,
        "risk_flags":      [],
        "is_uncertain":    False,
        "reasons":         [],
        "std_devs_from_line": round(std_devs_from_line, 2),
        "line_verified":   line_verified,
        "line_reliability_warning": line_reliability_warning,
        "goblin_floor":    _goblin_floor,
        "demon_ceiling":   _demon_ceiling,
    }


def categorize_alt_lines(standard_line, available_lines):
    """
    Categorize alternate sportsbook prop lines relative to the Standard_Line.

    Sportsbooks offer a primary "standard" Over/Under line plus a set of
    alternate lines at higher or lower thresholds.  This function splits
    those alternate lines into two categories:

    * **Goblin_Bets** — lines BELOW the standard line.
      These are safer floor bets; the player only needs to exceed a lower
      threshold to win.  High-probability, lower payout.

    * **Demon_Bets** — lines ABOVE the standard line.
      These are high-risk / high-reward bets; the player must exceed a
      higher threshold.  Lower probability, higher payout.

    Analysis should only be triggered on ACTUAL bookmaker lines — never
    on hypothetical or generated lines.  Feed the output of this function
    directly to the statistical analysis pipeline to ensure only real
    sportsbook lines are evaluated.

    Args:
        standard_line (float): The primary median O/U projection set by the
            sportsbook for this player prop (e.g. SGA Points O/U = 31.5).
        available_lines (list of float): The remaining alternate lines
            offered by the bookmaker for the same player prop.  Do NOT
            include the standard_line itself in this list.

    Returns:
        dict: {
            'standard_line': float,
            'goblin_bets':   list[float],  # Lines < standard_line, sorted asc
            'demon_bets':    list[float],  # Lines > standard_line, sorted asc
        }

    Example:
        # SGA Points — standard 31.5, alternates [28.5, 29.5, 33.5, 36.5]
        result = categorize_alt_lines(31.5, [28.5, 29.5, 33.5, 36.5])
        # → {
        #     'standard_line': 31.5,
        #     'goblin_bets':   [28.5, 29.5],  # below 31.5 → safe floor
        #     'demon_bets':    [33.5, 36.5],  # above 31.5 → high risk
        # }

        # Paolo Banchero PRA — standard 33.5, alternates [39.5, 41.5, 44.5]
        result = categorize_alt_lines(33.5, [39.5, 41.5, 44.5])
        # → {
        #     'standard_line': 33.5,
        #     'goblin_bets':   [],
        #     'demon_bets':    [39.5, 41.5, 44.5],
        # }
    """
    if not standard_line or standard_line <= 0:
        return {
            "standard_line": standard_line,
            "goblin_bets":   [],
            "demon_bets":    [],
        }

    goblin_bets = []
    demon_bets  = []

    for raw in available_lines:
        try:
            line_val = float(raw)
        except (ValueError, TypeError):
            continue  # Skip non-numeric entries

        # Lines below the standard line are Goblin_Bets (safe floor)
        if line_val < standard_line:
            goblin_bets.append(line_val)
        # Lines above the standard line are Demon_Bets (high risk/reward)
        elif line_val > standard_line:
            demon_bets.append(line_val)
        # Lines exactly equal to the standard are neither (they ARE the standard)

    return {
        "standard_line": standard_line,
        "goblin_bets":   sorted(goblin_bets),  # lowest first (safest first)
        "demon_bets":    sorted(demon_bets),   # lowest first (closest to std first)
    }


def format_goblin_demon_prediction(bet_type, line):
    """
    Strict prediction string formatter for Goblin/Demon bets.

    Goblin (lowered line) → "I predict the stat will do at LEAST {line}"
    Demon  (raised line)  → "I predict the stat will do at MOST {line}"
    Other                 → "" (empty string)

    Args:
        bet_type (str): One of 'goblin', 'demon', '50_50', 'normal'.
        line (float): The prop line value.

    Returns:
        str: The prediction string, or empty if not a Goblin/Demon bet.
    """
    if bet_type == "goblin":
        return f"I predict the stat will do at LEAST {line}"
    elif bet_type == "demon":
        return f"I predict the stat will do at MOST {line}"
    return ""


# ============================================================
# END SECTION: Goblin / Demon Bet Classification
# ============================================================


def _normalize_force_strength(raw_value: float, method: str = "ratio") -> float:
    """
    Normalize a raw force-strength signal to the [0, 100] scale.

    Two standardised methods are supported:

    * ``"ratio"``  — interprets *raw_value* as a ratio where 1.0 = neutral.
      Uses ``(factor - 1) * 100`` capped to [0, 100].  Best for
      factors like pace multipliers and matchup multipliers.
    * ``"gap"``    — interprets *raw_value* as an absolute gap (e.g. the
      difference between projected value and prop line measured in the
      same units as the stat).  Uses ``gap / 3`` capped to [0, 100].
      Best for raw numerical differences.

    Args:
        raw_value: The un-normalised signal value.
        method:    ``"ratio"`` (default) or ``"gap"``.

    Returns:
        float: Normalised strength in [0.0, 100.0].
    """
    if method == "gap":
        return min(max(raw_value / 3.0, 0.0), 100.0)
    # Default: "ratio" method
    return min(max((raw_value - 1.0) * 100.0, 0.0), 100.0)


def _reconcile_line_signals(
    sharpness_signal: dict,
    trap_signal: dict,
) -> dict:
    """
    Reconcile conflicting signals from line sharpness (W1) and trap line
    detection (W5).

    When both fire, the higher-confidence signal wins.  If confidence is
    equal the trap signal is given priority (conservative approach: when
    in doubt, don't bet).

    Args:
        sharpness_signal: Dict from ``detect_line_sharpness()`` with at
            minimum ``{"is_sharp": bool, "confidence": float}``.
        trap_signal: Dict from ``detect_trap_line()`` with at minimum
            ``{"is_trap": bool, "confidence": float}``.

    Returns:
        dict:
            ``{"winner": "sharpness" | "trap" | "neutral",
               "is_sharp": bool, "is_trap": bool,
               "note": str}``
    """
    sharp_conf = float(sharpness_signal.get("confidence", 0.0))
    trap_conf  = float(trap_signal.get("confidence",  0.0))
    is_sharp   = bool(sharpness_signal.get("is_sharp", False))
    is_trap    = bool(trap_signal.get("is_trap",   False))

    if not is_sharp and not is_trap:
        return {"winner": "neutral", "is_sharp": False, "is_trap": False,
                "note": "Neither signal active."}

    if is_sharp and not is_trap:
        return {"winner": "sharpness", "is_sharp": True, "is_trap": False,
                "note": "Only sharpness active."}

    if is_trap and not is_sharp:
        return {"winner": "trap", "is_sharp": False, "is_trap": True,
                "note": "Only trap active."}

    # Both fire — resolve by confidence
    if sharp_conf > trap_conf:
        return {
            "winner": "sharpness",
            "is_sharp": True,
            "is_trap": False,
            "note": (
                f"Both W1+W5 fired; sharpness confidence ({sharp_conf:.2f}) "
                f"> trap confidence ({trap_conf:.2f}) — treating as sharp line."
            ),
        }
    else:
        return {
            "winner": "trap",
            "is_sharp": False,
            "is_trap": True,
            "note": (
                f"Both W1+W5 fired; trap confidence ({trap_conf:.2f}) "
                f">= sharpness confidence ({sharp_conf:.2f}) — treating as trap (conservative)."
            ),
        }
