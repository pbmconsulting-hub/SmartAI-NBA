# ============================================================
# FILE: engine/entry_optimizer.py
# PURPOSE: Build optimal parlay entries for PrizePicks,
#          Underdog Fantasy, and DraftKings Pick6.
#          Calculates exact EV (expected value) for each entry.
# CONNECTS TO: edge_detection.py (picks), math_helpers.py (math)
# CONCEPTS COVERED: Combinatorics, expected value, parlay math
# ============================================================

# Standard library imports only
import math        # For combinations and calculations
import itertools   # For generating combinations of picks


# ============================================================
# SECTION: Platform Payout Tables
# These are the actual payout multipliers for each platform.
# BEGINNER NOTE: "payout table" = if you pick N games and hit K,
# here's your multiplier on your entry fee.
# ============================================================

# PrizePicks Flex Play payout table: {picks: {hits: payout_multiplier}}
# "Flex" means you can win even without hitting all picks
PRIZEPICKS_FLEX_PAYOUT_TABLE = {
    3: {3: 2.25, 2: 1.25, 1: 0.40, 0: 0.0},   # 3-pick flex
    4: {4: 5.0, 3: 1.50, 2: 0.40, 1: 0.0, 0: 0.0},  # 4-pick flex
    5: {5: 10.0, 4: 2.0, 3: 0.40, 2: 0.0, 1: 0.0, 0: 0.0},  # 5-pick flex
    6: {6: 25.0, 5: 2.0, 4: 0.40, 3: 0.0, 2: 0.0, 1: 0.0, 0: 0.0},  # 6-pick flex
}

# PrizePicks Power Play: ALL picks must hit (no partial wins)
PRIZEPICKS_POWER_PAYOUT_TABLE = {
    2: {2: 3.0},   # 2-pick power: 3x payout
    3: {3: 5.0},   # 3-pick power: 5x payout
    4: {4: 10.0},  # 4-pick power: 10x payout
    5: {5: 20.0},  # 5-pick power: 20x payout
    6: {6: 40.0},  # 6-pick power: 40x payout
}

# Underdog Fantasy Flex payout table
UNDERDOG_FLEX_PAYOUT_TABLE = {
    3: {3: 2.25, 2: 1.20, 1: 0.0, 0: 0.0},
    4: {4: 5.0, 3: 1.50, 2: 0.0, 1: 0.0, 0: 0.0},
    5: {5: 10.0, 4: 2.0, 3: 0.50, 2: 0.0, 1: 0.0, 0: 0.0},
    6: {6: 25.0, 5: 2.5, 4: 0.40, 3: 0.0, 2: 0.0, 1: 0.0, 0: 0.0},
}

# DraftKings Pick6 payout table (estimated — DK pools vary)
DRAFTKINGS_PICK6_PAYOUT_TABLE = {
    3: {3: 2.50, 2: 0.0, 1: 0.0, 0: 0.0},
    4: {4: 5.0, 3: 0.0, 2: 0.0, 1: 0.0, 0: 0.0},
    5: {5: 10.0, 4: 1.5, 3: 0.0, 2: 0.0, 1: 0.0, 0: 0.0},
    6: {6: 25.0, 5: 2.0, 4: 0.0, 3: 0.0, 2: 0.0, 1: 0.0, 0: 0.0},
}

# Map platform names to their payout tables
PLATFORM_FLEX_TABLES = {
    "PrizePicks": PRIZEPICKS_FLEX_PAYOUT_TABLE,
    "Underdog": UNDERDOG_FLEX_PAYOUT_TABLE,
    "DraftKings": DRAFTKINGS_PICK6_PAYOUT_TABLE,
}

# ============================================================
# END SECTION: Platform Payout Tables
# ============================================================


# ============================================================
# SECTION: Expected Value Calculator
# ============================================================

def calculate_entry_expected_value(
    pick_probabilities,
    payout_table,
    entry_fee,
):
    """
    Calculate the expected value (EV) of a parlay entry.

    EV = Sum of (probability of each outcome × payout for that outcome)
    EV > 0 means the bet is profitable on average.
    EV < 0 means the house edge wins.

    Args:
        pick_probabilities (list of float): P(over) for each pick
            e.g., [0.62, 0.58, 0.71] for a 3-pick entry
        payout_table (dict): Payout multipliers {hits: multiplier}
        entry_fee (float): Dollar amount bet (e.g., 10.00)

    Returns:
        dict: {
            'expected_value_dollars': float (positive = profitable),
            'return_on_investment': float (e.g., 0.15 = 15% ROI),
            'probability_per_hits': dict {hits: probability},
            'payout_per_hits': dict {hits: payout_dollars},
        }

    Example:
        3-pick entry, probs=[0.62, 0.58, 0.71], $10 entry fee
        → might give EV = $1.23 (12.3% ROI) — profitable!
    """
    number_of_picks = len(pick_probabilities)

    if number_of_picks == 0:
        return {
            "expected_value_dollars": 0.0,
            "return_on_investment": 0.0,
            "probability_per_hits": {},
            "payout_per_hits": {},
        }

    # ============================================================
    # SECTION: Calculate Probability of Each Hit Count
    # BEGINNER NOTE: This uses the binomial distribution.
    # We calculate P(exactly k picks win out of n total)
    # using the formula: C(n,k) * p^k * (1-p)^(n-k)
    # But since probabilities differ per pick, we sum over
    # all combinations of which k picks win.
    # ============================================================

    # Build probabilities for all possible hit counts (0 to n)
    probability_for_hit_count = {}

    # Loop through each possible number of hits (0, 1, 2, ..., n)
    for hit_count in range(number_of_picks + 1):
        # Sum probabilities over ALL combinations of `hit_count` wins
        total_prob_for_this_hit_count = 0.0

        # itertools.combinations gives us all ways to choose
        # `hit_count` picks out of `number_of_picks` total
        # BEGINNER NOTE: If picks are [A, B, C] and hit_count=2,
        # combinations gives us: (A,B), (A,C), (B,C)
        pick_indices = list(range(number_of_picks))

        for winning_indices in itertools.combinations(pick_indices, hit_count):
            # Calculate P(exactly these picks win, all others lose)
            # = product of P(win) for winners × P(lose) for losers
            combination_probability = 1.0
            winning_indices_set = set(winning_indices)

            for pick_index in range(number_of_picks):
                pick_probability = pick_probabilities[pick_index]
                if pick_index in winning_indices_set:
                    combination_probability *= pick_probability  # Win
                else:
                    combination_probability *= (1.0 - pick_probability)  # Lose

            total_prob_for_this_hit_count += combination_probability

        probability_for_hit_count[hit_count] = total_prob_for_this_hit_count

    # ============================================================
    # END SECTION: Calculate Probability of Each Hit Count
    # ============================================================

    # ============================================================
    # SECTION: Calculate EV Using Payout Table
    # ============================================================

    total_expected_value = 0.0
    payout_per_hits = {}

    for hit_count, probability in probability_for_hit_count.items():
        # Look up the payout multiplier for this hit count
        # Default to 0 if not in table (unspecified = no payout)
        payout_multiplier = payout_table.get(hit_count, 0.0)
        payout_dollars = payout_multiplier * entry_fee
        payout_per_hits[hit_count] = round(payout_dollars, 2)

        # Add this outcome's contribution to expected value
        total_expected_value += probability * payout_dollars

    # Net EV subtracts the cost of the entry fee
    net_expected_value = total_expected_value - entry_fee

    # ROI = net EV as a fraction of the entry fee
    return_on_investment = net_expected_value / entry_fee if entry_fee > 0 else 0.0

    return {
        "expected_value_dollars": round(net_expected_value, 2),
        "return_on_investment": round(return_on_investment, 4),
        "probability_per_hits": {k: round(v, 4) for k, v in probability_for_hit_count.items()},
        "payout_per_hits": payout_per_hits,
        "total_expected_return": round(total_expected_value, 2),
    }

    # ============================================================
    # END SECTION: Calculate EV Using Payout Table
    # ============================================================


# ============================================================
# SECTION: Optimal Entry Builder
# ============================================================

def build_optimal_entries(
    analyzed_picks,
    platform,
    entry_size,
    entry_fee,
    max_entries_to_show,
):
    """
    Find the best combination of picks for a given entry size.

    Sorts all possible combinations of picks by Expected Value
    and returns the top entries.

    Args:
        analyzed_picks (list of dict): All analyzed props, each with:
            'player_name', 'stat_type', 'line', 'probability_over',
            'direction', 'confidence_score', 'edge_percentage'
        platform (str): 'PrizePicks', 'Underdog', or 'DraftKings'
        entry_size (int): Number of picks per entry (2-6)
        entry_fee (float): Dollar amount per entry
        max_entries_to_show (int): How many top entries to return

    Returns:
        list of dict: Top entries sorted by EV, each containing:
            'picks': list of pick dicts,
            'ev_result': EV calculation result,
            'combined_confidence': float average confidence
    """
    # Filter to only picks with a clear direction and good confidence
    # We only want picks where our model has a meaningful edge
    qualifying_picks = [
        pick for pick in analyzed_picks
        if abs(pick.get("edge_percentage", 0)) >= 3.0  # At least 3% edge
        and pick.get("confidence_score", 0) >= 40.0    # At least Bronze tier
    ]

    # Get the payout table for this platform and entry size
    platform_flex_table = PLATFORM_FLEX_TABLES.get(platform, PRIZEPICKS_FLEX_PAYOUT_TABLE)
    payout_table_for_size = platform_flex_table.get(entry_size, {})

    if not qualifying_picks or not payout_table_for_size:
        return []  # Nothing to build

    # Cap entry size to what we have available
    actual_entry_size = min(entry_size, len(qualifying_picks))

    # ============================================================
    # SECTION: Generate and Score All Combinations
    # ============================================================

    all_entries_with_scores = []  # Store all combos with their EVs

    # Generate all combinations of `entry_size` picks from qualifying_picks
    # BEGINNER NOTE: itertools.combinations([A,B,C,D], 3) gives
    # (A,B,C), (A,B,D), (A,C,D), (B,C,D) — all 3-pick combos
    pick_index_list = list(range(len(qualifying_picks)))

    for combo_indices in itertools.combinations(pick_index_list, actual_entry_size):
        # Get the actual pick dictionaries for this combination
        combo_picks = [qualifying_picks[i] for i in combo_indices]

        # Extract probabilities: use P(over) if direction=OVER, else P(under)
        pick_probabilities = []
        for pick in combo_picks:
            if pick.get("direction", "OVER") == "OVER":
                prob = pick.get("probability_over", 0.5)
            else:
                # If we're betting UNDER, the probability is 1 - P(over)
                prob = 1.0 - pick.get("probability_over", 0.5)
            pick_probabilities.append(prob)

        # Calculate EV for this combination
        ev_result = calculate_entry_expected_value(
            pick_probabilities,
            payout_table_for_size,
            entry_fee,
        )

        # Average confidence score of all picks in this combo
        average_confidence = sum(
            p.get("confidence_score", 50) for p in combo_picks
        ) / len(combo_picks)

        all_entries_with_scores.append({
            "picks": combo_picks,
            "ev_result": ev_result,
            "combined_confidence": round(average_confidence, 1),
            "pick_probabilities": pick_probabilities,
        })

    # ============================================================
    # END SECTION: Generate and Score All Combinations
    # ============================================================

    # Sort by expected value (highest EV first)
    # BEGINNER NOTE: sorted() with key= lets us sort by any field
    # reverse=True means descending order (highest first)
    all_entries_with_scores.sort(
        key=lambda entry: entry["ev_result"]["expected_value_dollars"],
        reverse=True
    )

    # Return the top N entries
    return all_entries_with_scores[:max_entries_to_show]


def format_ev_display(ev_result, entry_fee):
    """
    Format EV results for display in the UI.

    Args:
        ev_result (dict): Output from calculate_entry_expected_value
        entry_fee (float): Entry fee amount

    Returns:
        dict: Human-readable display values
    """
    ev_dollars = ev_result.get("expected_value_dollars", 0)
    roi = ev_result.get("return_on_investment", 0)
    probability_per_hits = ev_result.get("probability_per_hits", {})

    # Format as percentage for display
    roi_percentage = roi * 100.0

    # Determine if EV is positive or negative
    ev_label = f"+${ev_dollars:.2f}" if ev_dollars >= 0 else f"-${abs(ev_dollars):.2f}"
    roi_label = f"+{roi_percentage:.1f}%" if roi >= 0 else f"{roi_percentage:.1f}%"

    return {
        "ev_label": ev_label,
        "roi_label": roi_label,
        "is_positive_ev": ev_dollars > 0,
        "probability_per_hits": probability_per_hits,
    }

# ============================================================
# END SECTION: Optimal Entry Builder
# ============================================================
