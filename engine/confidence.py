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
# NOTE (W2): Redistributed weights to improve accuracy — reduced raw probability
#            over-reliance, increased historical consistency, recent form, and
#            directional agreement which are stronger predictors of actual outcomes.
WEIGHT_PROBABILITY_STRENGTH = 0.20    # Raw probability (20% of score) — reduced; circular vs Monte Carlo
WEIGHT_EDGE_MAGNITUDE = 0.22          # How big the edge is (22%)
WEIGHT_DIRECTIONAL_AGREEMENT = 0.20  # Multiple factors agree (20%) — increased; strong predictor
WEIGHT_MATCHUP_FAVORABILITY = 0.10   # How good the matchup is (10%)
WEIGHT_HISTORICAL_CONSISTENCY = 0.12  # Player's track record (12%) — increased; consistency wins
WEIGHT_SAMPLE_SIZE = 0.06             # How many games played (6%)
WEIGHT_RECENT_FORM = 0.10             # Recent 5-game trend vs season (10%) — increased; recency matters

# Validate that weights sum to exactly 1.0 (they must — that's the rule for weights).
# This assertion catches any accidental edits that would break the model silently.
_ALL_WEIGHTS = (
    WEIGHT_PROBABILITY_STRENGTH
    + WEIGHT_EDGE_MAGNITUDE
    + WEIGHT_DIRECTIONAL_AGREEMENT
    + WEIGHT_MATCHUP_FAVORABILITY
    + WEIGHT_HISTORICAL_CONSISTENCY
    + WEIGHT_SAMPLE_SIZE
    + WEIGHT_RECENT_FORM
)
assert abs(_ALL_WEIGHTS - 1.0) < 1e-9, (
    f"Confidence weights must sum to 1.0, but got {_ALL_WEIGHTS:.4f}. "
    "Check the WEIGHT_* constants in confidence.py."
)

# Tier thresholds (0-100 scale) — W2: Recalibrated to match new weight distribution
# The reduced probability weight (0.30→0.20) lowers all scores by ~5-8 pts vs old weights,
# so thresholds are set to produce the correct tier distribution for real NBA prop scenarios.
# Target distribution: Platinum ~top 3%, Gold ~top 12%, Silver ~top 30%, rest Bronze/Avoid.
PLATINUM_TIER_MINIMUM_SCORE = 84  # Near-perfect conditions (raised from 80 pre-PR)
GOLD_TIER_MINIMUM_SCORE = 65      # Very strong clear edge (lowered from 69 to increase Gold-tier picks)
SILVER_TIER_MINIMUM_SCORE = 57    # Solid evidence above average (raised from 50 pre-PR)
# Anything below 57 = Bronze (lower confidence)

# Minimum edge gate (W2): picks below these thresholds get auto-demoted
PLATINUM_MIN_EDGE_PCT = 10.0   # Platinum requires ≥10% edge (lowered from 12%)
GOLD_MIN_EDGE_PCT = 7.0        # Gold requires ≥7% edge (lowered from 10%)
SILVER_MIN_EDGE_PCT = 3.0      # Silver requires ≥3% edge (lowered from 5%)
LOW_EDGE_THRESHOLD = 3.0       # Below 3% → add "Low edge" to avoid reasons (lowered from 5%)

# Hard kill-switch probability thresholds (C2)
PLATINUM_MIN_PROBABILITY = 0.62   # No Platinum below 62% win probability (was 0.60)
GOLD_MIN_PROBABILITY = 0.57       # No Gold below 57% win probability (was 0.55)

# Auto-AVOID: coefficient of variation above this → automatically avoid
AUTO_AVOID_CV_THRESHOLD = 0.45    # CV > 0.45 → auto-AVOID (loosened from 0.40 to reduce over-filtering)

# Score below this threshold → "Do Not Bet" / Avoid tier.
# 35/100 corresponds roughly to a coin-flip bet with marginal edge that is unlikely
# to be profitable long-term after accounting for vig deduction. Based on analysis
# of historical pick performance where scores below 35 showed negative expected value.
DO_NOT_BET_SCORE_THRESHOLD = 35

# Combo-stat confidence penalty multiplier.
# Combo stats (points_rebounds, etc.) have more variance than simple stats.
COMBO_STAT_CONFIDENCE_MULTIPLIER = 0.90  # was 0.85 — softened penalty so combo stats aren't over-penalized

# Stats considered "combo" or "fantasy" for penalty purposes
COMBO_STAT_TYPES = {
    "points_rebounds", "points_assists", "rebounds_assists",
    "points_rebounds_assists", "fantasy_score", "double_double", "triple_double",
}

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
    games_played=None,
    recent_form_ratio=None,
    line_sharpness_penalty=0.0,
    trap_line_penalty=0.0,
    calibration_adjustment=0.0,
    injury_status_penalty=0.0,
    stat_type=None,
):
    """
    Calculate a 0-100 confidence score for a prop pick.

    Combines eight factors into a weighted score, then assigns
    a tier label: Platinum, Gold, Silver, or Bronze.
    Post-scoring penalties for line sharpness (W1), trap lines (W5),
    calibration (W7), and injury status are applied additively.

    Phase 1 C2/C3 additions:
    - Hard kill switches (C2): override tier after scoring based on
      probability and CV thresholds.
    - Raised tier thresholds + min edge gate (C3): higher bars for
      Platinum/Gold/Silver, and low-edge picks auto-flagged as avoid.

    Args:
        probability_over (float): P(over line), from simulation
        edge_percentage (float): How far from 50% in percentage
        directional_forces (dict): Forces pushing MORE vs LESS
            Keys: 'over_count', 'under_count', 'over_forces', 'under_forces'
        defense_factor (float): Opponent defense multiplier (< 1 = tough)
        stat_standard_deviation (float): Stat variability
        stat_average (float): Player's season average for this stat
        simulation_results (dict): Full Monte Carlo output dict
        games_played (int, optional): Games in season (higher = more reliable)
        recent_form_ratio (float, optional): Last-5-game avg / season avg.
            > 1.0 means hot streak, < 1.0 means cold streak.
        line_sharpness_penalty (float, optional): Points to subtract when
            the line is set at the player's true average (W1 — sharp line).
            Typically 0-8 points. Passed in from edge_detection results.
        trap_line_penalty (float, optional): Points to subtract when a
            trap line is detected (W5 — bait line). Typically 0-15 points.
        calibration_adjustment (float, optional): Historical calibration
            offset in percentage points (W7). Positive = model overestimates,
            scores get reduced. Negative = model underestimates, scores go up.
        injury_status_penalty (float, optional): Points to subtract when the
            player has a concerning injury/availability status (e.g. Questionable,
            Doubtful). Typically 0-10 points. Default 0.0 (no penalty).
        stat_type (str, optional): The stat being evaluated (e.g. 'points',
            'points_rebounds'). Used to apply combo-stat confidence penalty.

    Returns:
        dict: {
            'confidence_score': float (0-100),
            'tier': str ('Platinum', 'Gold', 'Silver', 'Bronze', 'Avoid'),
            'tier_emoji': str ('💎', '🥇', '🥈', '🥉', '⛔'),
            'score_breakdown': dict with individual factor scores,
            'direction': str ('OVER' or 'UNDER'),
            'recommendation': str (e.g., "Strong OVER play"),
            'should_avoid': bool (C2: auto-AVOID flag),
            'avoid_reasons': list of str (C2/C3: reasons for avoid flag),
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

    # --- Factor 6: Sample Size (0-100) ---
    # More games played = more reliable season averages.
    # 0 games = 0 score, 41+ games = 100 score
    sample_size_score = _calculate_sample_size_score(games_played)

    # --- Factor 7: Recent Form (0-100) ---
    # Recent hot/cold streaks adjust the prediction reliability.
    # ratio ≈ 1.0 = neutral (50), >> 1 = hot (high score), << 1 = cold (low)
    recent_form_score = _calculate_recent_form_score(
        recent_form_ratio, probability_over
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
        + sample_size_score * WEIGHT_SAMPLE_SIZE
        + recent_form_score * WEIGHT_RECENT_FORM
    )

    # --- Apply Post-Scoring Penalties ---
    # W1: Line Sharpness Penalty — deduct when book has accurately priced the line
    # W5: Trap Line Penalty — deduct when a bait line is detected
    # W7: Calibration Adjustment — correct for systematic model over/underconfidence
    # Injury Status Penalty — deduct when player has a concerning availability status
    combined_score -= line_sharpness_penalty
    combined_score -= trap_line_penalty
    combined_score -= calibration_adjustment  # positive = historically overconfident
    combined_score -= injury_status_penalty

    # Apply combo-stat confidence penalty — combo/fantasy stats have more variance
    _stat_type_lower = str(stat_type).lower() if stat_type else ""
    if _stat_type_lower in COMBO_STAT_TYPES:
        combined_score *= COMBO_STAT_CONFIDENCE_MULTIPLIER

    # W2: Recency Regression-to-Mean Correction
    # Extreme recent performance (hot or cold streaks) tends to revert to the season
    # average. If the last 5 games show >25% deviation from the season average,
    # apply a regression penalty — the model should not be highly confident on
    # predictions driven by temporary streaks that are likely to normalize.
    if recent_form_ratio is not None:
        form_deviation_abs = abs(recent_form_ratio - 1.0)
        if form_deviation_abs > 0.25:
            # Penalty: 20 points per 1.0 (100%) deviation beyond the 25% threshold.
            # Equivalently, 2 pts per 10% excess deviation.
            # E.g., ratio=1.40 → excess=0.15 → 20*0.15 = 3.0 point penalty
            #        ratio=1.60 → excess=0.35 → 20*0.35 = 7.0 point penalty (capped at 8)
            excess = form_deviation_abs - 0.25
            regression_penalty = min(8.0, excess * 20.0)
            combined_score -= regression_penalty

    # Round to nearest whole number, clamped to 0-100
    final_score = round(max(0.0, min(100.0, combined_score)), 1)

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

    # Effective probability in the recommended direction (always ≥ 0.5)
    prob_in_direction = probability_over if bet_direction == "OVER" else (1.0 - probability_over)
    abs_edge = abs(edge_percentage)

    # ── C2: Hard Kill Switches (applied AFTER weighted score) ────
    # These are non-negotiable overrides that fire regardless of the score.
    should_avoid = False
    avoid_reasons = []

    # Kill switch 1: coefficient of variation > 0.50 → auto-AVOID
    if stat_average > 0:
        cv = stat_standard_deviation / stat_average
        if cv > AUTO_AVOID_CV_THRESHOLD:
            should_avoid = True
            avoid_reasons.append(f"High variance (CV={cv:.2f} > {AUTO_AVOID_CV_THRESHOLD})")

    # Kill switch 2: edge < SILVER_MIN_EDGE_PCT → auto-Bronze
    # (Force the score down to Bronze range if edge is too small to warrant higher tier)
    # Uses SILVER_MIN_EDGE_PCT (4%) to be consistent with tier gating logic.
    if abs_edge < SILVER_MIN_EDGE_PCT:
        final_score = min(final_score, SILVER_TIER_MINIMUM_SCORE - 1)

    # ── C3: Min Edge Gate — Low edge flag ────────────────────────
    if abs_edge < LOW_EDGE_THRESHOLD:
        avoid_reasons.append(f"Low edge ({abs_edge:.1f}% < {LOW_EDGE_THRESHOLD}% minimum)")

    # ── Assign tier with C3 raised thresholds + edge gates ───────
    if (
        final_score >= PLATINUM_TIER_MINIMUM_SCORE
        and prob_in_direction >= PLATINUM_MIN_PROBABILITY  # C2: min 60%
        and abs_edge >= PLATINUM_MIN_EDGE_PCT              # C3: min 10% edge
    ):
        tier_name = "Platinum"
        tier_emoji = "💎"
        recommendation = f"Elite {bet_direction} play — highest confidence"
    elif (
        final_score >= GOLD_TIER_MINIMUM_SCORE
        and prob_in_direction >= GOLD_MIN_PROBABILITY      # C2: min 55%
        and abs_edge >= GOLD_MIN_EDGE_PCT                  # C3: min 7% edge
    ):
        tier_name = "Gold"
        tier_emoji = "🥇"
        recommendation = f"Strong {bet_direction} play — good confidence"
    elif final_score >= SILVER_TIER_MINIMUM_SCORE and abs_edge >= SILVER_MIN_EDGE_PCT:
        tier_name = "Silver"
        tier_emoji = "🥈"
        recommendation = f"Moderate {bet_direction} lean — use with others"
    else:
        tier_name = "Bronze"
        tier_emoji = "🥉"
        recommendation = f"Weak {bet_direction} signal — consider avoiding"

    # Do Not Bet: scores below DO_NOT_BET_SCORE_THRESHOLD are explicitly flagged as Avoid
    if final_score < DO_NOT_BET_SCORE_THRESHOLD:
        tier_name = "Avoid"
        tier_emoji = "⛔"
        recommendation = f"Do not bet — very low confidence ({final_score:.0f}/100)"
        should_avoid = True
        avoid_reasons.append(f"Score {final_score:.0f} below Do-Not-Bet threshold ({DO_NOT_BET_SCORE_THRESHOLD})")

    # ── C2: Kill switch — downgrade Platinum/Gold below probability floor ─
    # If the tier is Platinum but probability is below 60%, force to Gold.
    # If the tier is Gold but probability is below 55%, force to Silver.
    if tier_name == "Platinum" and prob_in_direction < PLATINUM_MIN_PROBABILITY:
        tier_name = "Gold"
        tier_emoji = "🥇"
        recommendation = f"Strong {bet_direction} play — good confidence"
        avoid_reasons.append(f"Downgraded Platinum→Gold (prob {prob_in_direction:.1%} < {PLATINUM_MIN_PROBABILITY:.0%})")
    if tier_name == "Gold" and prob_in_direction < GOLD_MIN_PROBABILITY:
        tier_name = "Silver"
        tier_emoji = "🥈"
        recommendation = f"Moderate {bet_direction} lean — use with others"
        avoid_reasons.append(f"Downgraded Gold→Silver (prob {prob_in_direction:.1%} < {GOLD_MIN_PROBABILITY:.0%})")

    # ============================================================
    # END SECTION: Assign Tier and Direction
    # ============================================================

    return {
        "confidence_score": final_score,
        "tier": tier_name,
        "tier_emoji": tier_emoji,
        "direction": bet_direction,
        "recommendation": recommendation,
        "should_avoid": should_avoid,
        "avoid_reasons": avoid_reasons,
        "score_breakdown": {
            "probability_score": round(probability_score, 1),
            "edge_score": round(edge_score, 1),
            "directional_score": round(directional_score, 1),
            "matchup_score": round(matchup_score, 1),
            "historical_score": round(historical_score, 1),
            "sample_size_score": round(sample_size_score, 1),
            "recent_form_score": round(recent_form_score, 1),
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


def _calculate_sample_size_score(games_played):
    """
    Score the reliability of season averages based on games played.

    More games = more reliable data = higher score.
    Uses a logistic-style curve so the score grows quickly early
    (0-20 games) and levels off after ~41 games (half a season).

    Args:
        games_played (int or None): Number of games played this season.
            None or 0 returns a neutral score of 50.

    Returns:
        float: Score 0-100 (higher = more reliable sample)
    """
    if not games_played or games_played <= 0:
        return 50.0  # No data — neutral

    # Cap benefit at 82 games (full season)
    games = min(games_played, 82)

    # Linearly scale: 0 games → 10, 41 games → 70, 82 games → 100
    # We use 41 as the "good enough" midpoint (half season)
    if games <= 41:
        score = 10.0 + (games / 41.0) * 60.0
    else:
        score = 70.0 + ((games - 41) / 41.0) * 30.0

    return max(0.0, min(100.0, score))


def _calculate_recent_form_score(recent_form_ratio, probability_over):
    """
    Score how recent form aligns with the predicted direction.

    A hot player (ratio > 1) boosts confidence in OVER picks.
    A cold player (ratio < 1) boosts confidence in UNDER picks.
    A player whose recent form contradicts the pick reduces confidence.

    Args:
        recent_form_ratio (float or None): last_5_avg / season_avg.
            > 1.0 = hot streak, < 1.0 = cold streak, 1.0 = neutral.
            None means no recent form data available.
        probability_over (float): P(over), used to determine direction.

    Returns:
        float: Score 0-100
    """
    if recent_form_ratio is None:
        return 50.0  # No recent form data — neutral

    bet_direction_is_over = probability_over >= 0.5

    # How far from neutral (1.0) is the recent form?
    form_deviation = recent_form_ratio - 1.0  # positive = hot, negative = cold

    if bet_direction_is_over:
        # OVER pick: hot streak is good, cold streak is bad
        alignment = form_deviation  # positive when aligned
    else:
        # UNDER pick: cold streak is good, hot streak is bad
        alignment = -form_deviation  # positive when aligned

    # Scale to 0-100: strong alignment → high score, misalignment → low score
    # The multiplier 200.0 maps the alignment range of [-0.25, +0.25] to [-50, +50],
    # which when added to the base 50 gives a final score in [0, 100].
    # A ±25% recent form deviation is considered a strong signal.
    scaled = 50.0 + (alignment * 200.0)
    return max(0.0, min(100.0, scaled))


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
