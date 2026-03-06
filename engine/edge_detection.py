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
# CV of 0.55 means the std is 55% of the average — very noisy.
HIGH_VARIANCE_CV_THRESHOLD = 0.55


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
        strength = min(2.0, (blowout_risk - 0.15) * 10.0)
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

    Returns:
        tuple: (should_avoid: bool, reasons: list of str)

    Example:
        0.51 probability, conflicting forces → avoid=True,
        reasons=['Insufficient edge (<5%)', 'Conflicting forces']
    """
    avoid_reasons = []  # Collect all reasons to avoid

    # Reason 1: Edge too small (under 5%)
    if abs(edge_percentage) < 5.0:
        avoid_reasons.append(
            f"Insufficient edge ({edge_percentage:.1f}%) — coin flip territory"
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
        if conflict_ratio > 0.75:  # Within 25% of each other = conflicting
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
