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

        # W2: Apply correlation discount to expected value
        # If multiple legs share a game, their outcomes are correlated.
        correlation_risk = calculate_correlation_risk(combo_picks)
        discount = correlation_risk["discount_multiplier"]
        if discount < 1.0:
            # Scale down the EV to reflect correlation penalty.
            # Shallow copy is safe here because we only modify top-level float fields,
            # not the nested probability_per_hits / payout_per_hits dicts.
            discounted_ev = ev_result["expected_value_dollars"] * discount
            discounted_return = ev_result["total_expected_return"] * discount
            discounted_roi = discounted_ev / entry_fee if entry_fee > 0 else 0.0
            ev_result = dict(ev_result)  # copy
            ev_result["expected_value_dollars"] = round(discounted_ev, 2)
            ev_result["total_expected_return"] = round(discounted_return, 2)
            ev_result["return_on_investment"] = round(discounted_roi, 4)
            ev_result["correlation_discount_applied"] = True
        else:
            ev_result = dict(ev_result)
            ev_result["correlation_discount_applied"] = False

        # Average confidence score of all picks in this combo
        average_confidence = sum(
            p.get("confidence_score", 50) for p in combo_picks
        ) / len(combo_picks)

        # W9: Identify the weakest link in this combo
        weakest = identify_weakest_link(combo_picks)
        weakest_prob = 0.5
        weakest_label = ""
        if weakest:
            wp = weakest.get("probability_over", 0.5)
            weakest_prob = wp if weakest.get("direction", "OVER") == "OVER" else 1.0 - wp
            weakest_label = (
                f"{weakest.get('player_name','?')} "
                f"{weakest.get('stat_type','').capitalize()} "
                f"({weakest_prob*100:.0f}%)"
            )

        all_entries_with_scores.append({
            "picks": combo_picks,
            "ev_result": ev_result,
            "combined_confidence": round(average_confidence, 1),
            "pick_probabilities": pick_probabilities,
            "correlation_risk": correlation_risk,
            "weakest_link": weakest,
            "weakest_link_probability": round(weakest_prob, 4),
            "weakest_link_label": weakest_label,
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


# ============================================================
# SECTION: Correlation Risk Calculator (W2)
# When multiple legs come from the SAME game, all are affected
# simultaneously by game-level events (blowout, OT, foul trouble).
# This is a hidden parlay risk that must be disclosed and penalized.
# ============================================================

def calculate_correlation_risk(selected_picks):
    """
    Calculate the correlation risk discount for a set of picks. (W2)

    When 2+ picks come from the same game, their outcomes are
    correlated — a blowout or overtime affects ALL of them.
    We apply a probability discount to account for this hidden risk.

    Args:
        selected_picks (list of dict): Picks to check, each with
            'player_team' (or 'team') and 'opponent' keys.

    Returns:
        dict: {
            'discount_multiplier': float  (1.0 = no discount, 0.88 = 12% penalty)
            'max_same_game_picks': int    (highest count from any single game)
            'game_groups': dict           {game_key: [player_names]}
            'warnings': list of str       (human-readable warnings)
            'correlation_level': str      ('none', 'low', 'high')
        }

    Example:
        3 picks from LAL vs GSW → discount_multiplier=0.88, level='high'
    """
    # Group picks by game (same two teams)
    game_groups = {}  # game_key (frozenset of teams) → list of pick dicts

    for pick in selected_picks:
        team = pick.get("player_team", pick.get("team", "")).upper().strip()
        opponent = pick.get("opponent", "").upper().strip()
        if team and opponent:
            game_key = frozenset([team, opponent])
        elif team:
            game_key = frozenset([team])
        else:
            continue
        game_key_str = " vs ".join(sorted(game_key))
        if game_key_str not in game_groups:
            game_groups[game_key_str] = []
        game_groups[game_key_str].append(pick)

    # Find the game with the most picks
    max_same_game = max((len(v) for v in game_groups.values()), default=0)

    # Build warnings and determine discount
    warnings = []
    correlation_level = "none"
    discount_multiplier = 1.0

    for game_key_str, picks_in_game in game_groups.items():
        n = len(picks_in_game)
        if n < 2:
            continue  # Single pick from a game — no correlation

        names = [p.get("player_name", "?") for p in picks_in_game]
        names_str = ", ".join(names)

        if n >= 3:
            # 12% penalty for 3+ picks from same game
            discount_multiplier = min(discount_multiplier, 0.88)
            correlation_level = "high"
            warnings.append(
                f"🚨 HIGH CORRELATION: {n} picks from {game_key_str} "
                f"({names_str}) — 12% EV penalty applied. "
                f"A blowout or foul-out affects ALL {n} legs simultaneously."
            )
        else:
            # 5% penalty for 2 picks from same game
            discount_multiplier = min(discount_multiplier, 0.95)
            if correlation_level != "high":
                correlation_level = "low"
            warnings.append(
                f"⚠️ CORRELATION: 2 picks from {game_key_str} "
                f"({names_str}) — 5% EV penalty applied. "
                f"Same-game events (blowout, OT) affect both legs."
            )

    return {
        "discount_multiplier": round(discount_multiplier, 4),
        "max_same_game_picks": max_same_game,
        "game_groups": {k: [p.get("player_name", "?") for p in v]
                        for k, v in game_groups.items()},
        "warnings": warnings,
        "correlation_level": correlation_level,
    }

# ============================================================
# END SECTION: Correlation Risk Calculator
# ============================================================


# ============================================================
# SECTION: Weakest Link Detection + Swap Suggestions (W9)
# The entry is only as strong as its weakest pick.
# Identify it, then suggest better alternatives.
# ============================================================

def identify_weakest_link(picks):
    """
    Find the weakest pick in an entry by probability. (W9)

    The weakest link is the pick with the LOWEST win probability,
    since a parlay fails if any single leg misses.

    Args:
        picks (list of dict): Entry picks, each with 'probability_over',
            'direction', 'player_name', 'stat_type', 'line'

    Returns:
        dict or None: The weakest pick dict, or None if picks is empty.
    """
    if not picks:
        return None

    def _win_prob(pick):
        """Get the win probability for the betted direction."""
        p = pick.get("probability_over", 0.5)
        return p if pick.get("direction", "OVER") == "OVER" else 1.0 - p

    return min(picks, key=_win_prob)


def suggest_swap(weakest_pick, available_picks, entry_picks):
    """
    Suggest a stronger alternative for the weakest pick in an entry. (W9)

    Finds the available pick (not already in the entry) with the
    highest win probability that could replace the weakest link.

    Args:
        weakest_pick (dict): The lowest-probability pick in the entry
        available_picks (list of dict): All qualifying picks
        entry_picks (list of dict): Current entry picks (to exclude from suggestions)

    Returns:
        dict or None: The best swap candidate, or None if no better option exists.
            Includes the pick dict plus a 'swap_reason' key explaining the swap.
    """
    # Collect player+stat combos already in the entry (to avoid duplicates)
    in_entry = set()
    for p in entry_picks:
        key = (p.get("player_name", ""), p.get("stat_type", ""))
        in_entry.add(key)

    weakest_prob = (
        weakest_pick.get("probability_over", 0.5)
        if weakest_pick.get("direction", "OVER") == "OVER"
        else 1.0 - weakest_pick.get("probability_over", 0.5)
    )

    best_candidate = None
    best_prob = weakest_prob  # Only suggest if it's actually better

    for pick in available_picks:
        key = (pick.get("player_name", ""), pick.get("stat_type", ""))
        if key in in_entry:
            continue  # Already in the entry

        p = pick.get("probability_over", 0.5)
        win_prob = p if pick.get("direction", "OVER") == "OVER" else 1.0 - p

        if win_prob > best_prob:
            best_prob = win_prob
            best_candidate = pick

    if best_candidate is None:
        return None

    improvement = (best_prob - weakest_prob) * 100.0
    best_candidate = dict(best_candidate)  # copy to avoid mutating original
    best_candidate["swap_reason"] = (
        f"Replaces {weakest_pick.get('player_name','?')} "
        f"{weakest_pick.get('stat_type','').capitalize()} "
        f"({weakest_prob*100:.0f}% → {best_prob*100:.0f}%, "
        f"+{improvement:.1f}% stronger)"
    )
    return best_candidate

# ============================================================
# END SECTION: Weakest Link Detection + Swap Suggestions
# ============================================================


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
