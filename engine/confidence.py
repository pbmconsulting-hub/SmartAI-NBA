# ============================================================
# FILE: engine/confidence.py
# PURPOSE: Calculate confidence scores and assign tiers
#          (Platinum, Gold, Silver, Bronze) to each prop pick.
#          Combines multiple factors into a single score.
# CONNECTS TO: edge_detection.py (edge values), simulation.py
# CONCEPTS COVERED: Weighted scoring, tier classification
# ============================================================

# No external imports needed — pure Python logic
import math  # For rounding


# ============================================================
# SECTION: Confidence Score Constants
# Define the weights for each factor in our confidence model.
# Weights add up to 1.0 (100%).
# ============================================================

# How much each factor contributes to the overall confidence score
# BEGINNER NOTE: These weights reflect how important each factor is
# You can adjust these in Settings if you want to change the model
WEIGHT_PROBABILITY_STRENGTH = 0.35    # Raw probability (35% of score)
WEIGHT_EDGE_MAGNITUDE = 0.25          # How big the edge is (25%)
WEIGHT_DIRECTIONAL_AGREEMENT = 0.20  # Multiple factors agree (20%)
WEIGHT_MATCHUP_FAVORABILITY = 0.12   # How good the matchup is (12%)
WEIGHT_HISTORICAL_CONSISTENCY = 0.08  # Player's track record (8%)

# Validate that weights sum to exactly 1.0 (they must — that's the rule for weights).
# This assertion catches any accidental edits that would break the model silently.
_ALL_WEIGHTS = (
    WEIGHT_PROBABILITY_STRENGTH
    + WEIGHT_EDGE_MAGNITUDE
    + WEIGHT_DIRECTIONAL_AGREEMENT
    + WEIGHT_MATCHUP_FAVORABILITY
    + WEIGHT_HISTORICAL_CONSISTENCY
)
assert abs(_ALL_WEIGHTS - 1.0) < 1e-9, (
    f"Confidence weights must sum to 1.0, but got {_ALL_WEIGHTS:.4f}. "
    "Check the WEIGHT_* constants in confidence.py."
)

# Tier thresholds (0-100 scale)
PLATINUM_TIER_MINIMUM_SCORE = 80  # Top-tier picks
GOLD_TIER_MINIMUM_SCORE = 65      # Strong picks
SILVER_TIER_MINIMUM_SCORE = 50    # Moderate picks
# Anything below 50 = Bronze (lower confidence)

# ============================================================
# END SECTION: Confidence Score Constants
# ============================================================


# ============================================================
# SECTION: Main Confidence Calculator
# ============================================================

def calculate_confidence_score(
    probability_over,
    edge_percentage,
    directional_forces,
    defense_factor,
    stat_standard_deviation,
    stat_average,
    simulation_results,
):
    """
    Calculate a 0-100 confidence score for a prop pick.

    Combines six factors into a weighted score, then assigns
    a tier label: Platinum, Gold, Silver, or Bronze.

    Args:
        probability_over (float): P(over line), from simulation
        edge_percentage (float): How far from 50% in percentage
        directional_forces (dict): Forces pushing MORE vs LESS
            Keys: 'over_count', 'under_count', 'over_forces', 'under_forces'
        defense_factor (float): Opponent defense multiplier (< 1 = tough)
        stat_standard_deviation (float): Stat variability
        stat_average (float): Player's season average for this stat
        simulation_results (dict): Full Monte Carlo output dict

    Returns:
        dict: {
            'confidence_score': float (0-100),
            'tier': str ('Platinum', 'Gold', 'Silver', 'Bronze'),
            'tier_emoji': str ('💎', '🥇', '🥈', '🥉'),
            'score_breakdown': dict with individual factor scores,
            'direction': str ('OVER' or 'UNDER'),
            'recommendation': str (e.g., "Strong OVER play"),
        }

    Example:
        60% probability, 10% edge, good matchup, consistent player
        → score ≈ 72, tier = Gold, direction = OVER
    """
    # ============================================================
    # SECTION: Calculate Individual Factor Scores
    # Each factor is scored 0-100, then weighted
    # ============================================================

    # --- Factor 1: Probability Strength (0-100) ---
    # How far is the probability from the 50% baseline?
    # 50% = 0 score, 70% = 40 score, 90% = 80 score
    probability_distance_from_50 = abs(probability_over - 0.5)
    probability_score = min(100.0, probability_distance_from_50 * 200.0)

    # --- Factor 2: Edge Magnitude (0-100) ---
    # Larger edge = higher score. Cap at 25% edge = 100 score
    edge_score = min(100.0, abs(edge_percentage) * 4.0)

    # --- Factor 3: Directional Agreement (0-100) ---
    # How many forces agree on the direction vs disagree?
    directional_score = _calculate_directional_agreement_score(directional_forces)

    # --- Factor 4: Matchup Favorability (0-100) ---
    # defense_factor > 1.0 = weak defense = good for player
    # Scale: 1.0 = neutral (50), 1.10 = great (80), 0.90 = bad (20)
    matchup_score = 50.0 + (defense_factor - 1.0) * 300.0
    matchup_score = max(0.0, min(100.0, matchup_score))

    # --- Factor 5: Historical Consistency (0-100) ---
    # Players with low coefficient of variation (low std/avg) are
    # more consistent and their projections are more reliable
    historical_score = _calculate_consistency_score(
        stat_standard_deviation, stat_average
    )

    # ============================================================
    # END SECTION: Calculate Individual Factor Scores
    # ============================================================

    # ============================================================
    # SECTION: Combine Scores with Weights
    # ============================================================

    # Weighted sum of all factor scores
    combined_score = (
        probability_score * WEIGHT_PROBABILITY_STRENGTH
        + edge_score * WEIGHT_EDGE_MAGNITUDE
        + directional_score * WEIGHT_DIRECTIONAL_AGREEMENT
        + matchup_score * WEIGHT_MATCHUP_FAVORABILITY
        + historical_score * WEIGHT_HISTORICAL_CONSISTENCY
    )

    # Round to nearest whole number
    final_score = round(combined_score, 1)

    # ============================================================
    # END SECTION: Combine Scores with Weights
    # ============================================================

    # ============================================================
    # SECTION: Assign Tier and Direction
    # ============================================================

    # Determine the bet direction (over or under)
    if probability_over >= 0.5:
        bet_direction = "OVER"
    else:
        bet_direction = "UNDER"

    # Assign tier based on score thresholds
    if final_score >= PLATINUM_TIER_MINIMUM_SCORE:
        tier_name = "Platinum"
        tier_emoji = "💎"
        recommendation = f"Elite {bet_direction} play — highest confidence"
    elif final_score >= GOLD_TIER_MINIMUM_SCORE:
        tier_name = "Gold"
        tier_emoji = "🥇"
        recommendation = f"Strong {bet_direction} play — good confidence"
    elif final_score >= SILVER_TIER_MINIMUM_SCORE:
        tier_name = "Silver"
        tier_emoji = "🥈"
        recommendation = f"Moderate {bet_direction} lean — use with others"
    else:
        tier_name = "Bronze"
        tier_emoji = "🥉"
        recommendation = f"Weak {bet_direction} signal — consider avoiding"

    # ============================================================
    # END SECTION: Assign Tier and Direction
    # ============================================================

    return {
        "confidence_score": final_score,
        "tier": tier_name,
        "tier_emoji": tier_emoji,
        "direction": bet_direction,
        "recommendation": recommendation,
        "score_breakdown": {
            "probability_score": round(probability_score, 1),
            "edge_score": round(edge_score, 1),
            "directional_score": round(directional_score, 1),
            "matchup_score": round(matchup_score, 1),
            "historical_score": round(historical_score, 1),
        },
    }


# ============================================================
# SECTION: Helper Score Functions
# ============================================================

def _calculate_directional_agreement_score(directional_forces):
    """
    Score how much the directional forces agree on a direction.

    If 5 forces push OVER and 1 pushes UNDER, strong agreement.
    If 3 vs 3, weak agreement (more uncertain).

    Args:
        directional_forces (dict): With keys:
            'over_count' (int): Number of forces pushing OVER
            'under_count' (int): Number of forces pushing UNDER
            'over_strength' (float): Cumulative strength of over forces
            'under_strength' (float): Cumulative strength of under forces

    Returns:
        float: Score 0-100 (higher = more agreement)
    """
    over_count = directional_forces.get("over_count", 0)
    under_count = directional_forces.get("under_count", 0)
    total_count = over_count + under_count

    if total_count == 0:
        return 50.0  # No data = neutral

    # Calculate dominance: how one-sided is the vote?
    # 100% one side = max agreement
    dominant_count = max(over_count, under_count)
    agreement_ratio = dominant_count / total_count  # 0.5 to 1.0

    # Convert to 0-100 score
    # 0.5 ratio (tie) = 0 score, 1.0 ratio (all agree) = 100 score
    directional_score = (agreement_ratio - 0.5) * 200.0

    # Also factor in the strength of the forces
    over_strength = directional_forces.get("over_strength", 0.0)
    under_strength = directional_forces.get("under_strength", 0.0)
    total_strength = over_strength + under_strength

    if total_strength > 0:
        dominant_strength = max(over_strength, under_strength)
        strength_ratio = dominant_strength / total_strength
        strength_score = (strength_ratio - 0.5) * 200.0
        # Blend count-based and strength-based scores
        directional_score = (directional_score * 0.5) + (strength_score * 0.5)

    return max(0.0, min(100.0, directional_score))


def _calculate_consistency_score(stat_standard_deviation, stat_average):
    """
    Score a player's consistency for a given stat.

    Coefficient of variation (CV) = std / avg
    Lower CV = more consistent = more predictable = higher score.

    Args:
        stat_standard_deviation (float): Spread of the stat
        stat_average (float): Average value of the stat

    Returns:
        float: Score 0-100 (higher = more consistent)
    """
    if stat_average <= 0:
        return 50.0  # Can't calculate — return neutral

    # Coefficient of variation: std divided by mean
    coefficient_of_variation = stat_standard_deviation / stat_average

    # Scale: CV of 0.20 = very consistent (85 score)
    #        CV of 0.50 = average consistency (50 score)
    #        CV of 0.80 = very inconsistent (15 score)
    # Formula: score = 100 - (CV * 100)  capped at 0-100
    consistency_score = 100.0 - (coefficient_of_variation * 100.0)

    return max(0.0, min(100.0, consistency_score))


def get_tier_color(tier_name):
    """
    Get the display color for each tier (for Streamlit UI).

    Args:
        tier_name (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'

    Returns:
        str: Hex color code
    """
    # Color map for each tier
    tier_color_map = {
        "Platinum": "#E5E4E2",  # Platinum silver
        "Gold": "#FFD700",      # Gold yellow
        "Silver": "#C0C0C0",    # Silver grey
        "Bronze": "#CD7F32",    # Bronze brown
    }
    return tier_color_map.get(tier_name, "#FFFFFF")  # White default

# ============================================================
# END SECTION: Helper Score Functions
# ============================================================
