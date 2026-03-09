# ============================================================
# FILE: engine/math_helpers.py
# PURPOSE: All mathematical and statistical functions needed
#          by the SmartBetPro NBA engine — built from scratch using
#          ONLY Python's standard library (math, statistics).
#          No numpy, no scipy, no pandas.
# CONNECTS TO: simulation.py, projections.py, confidence.py,
#              edge_detection.py
# CONCEPTS COVERED: Normal distribution, Poisson distribution,
#                   standard deviation, z-scores, percentiles,
#                   probability calculations
# ============================================================

# Import only standard-library modules (these ship with Python)
import math        # math.sqrt, math.exp, math.pi, math.erf, etc.
import statistics  # statistics.mean, statistics.stdev
import random      # random.gauss for Monte Carlo sampling


# ============================================================
# SECTION: Normal Distribution Helpers
# A normal distribution (bell curve) is the most common
# statistical shape. We use it to model player stat variability.
# ============================================================

def calculate_normal_cdf(value, mean, standard_deviation):
    """
    Calculate the probability that a normally-distributed
    random variable is LESS THAN OR EQUAL TO `value`.

    This is the "cumulative distribution function" (CDF).
    Think of it as: given a player averages 25 points with
    some spread, what % of games do they score <= 24.5?

    Args:
        value (float): The threshold we're checking (e.g., 24.5)
        mean (float): The average (center of the bell curve)
        standard_deviation (float): How spread out the curve is

    Returns:
        float: Probability between 0.0 and 1.0

    Example:
        If LeBron averages 24.8 pts with std 6.2, and the line
        is 24.5, then P(score <= 24.5) ≈ 0.48 (just under 50%)
    """
    # Guard against zero or negative standard deviation
    # (A player can't have zero variability — games differ)
    if standard_deviation <= 0:
        # If no variability, either certainly under or certainly over
        if value >= mean:
            return 1.0  # Always under or at line
        else:
            return 0.0  # Always over

    # BEGINNER NOTE: The z-score tells us how many standard
    # deviations away from the mean our value is.
    # z = 0  means value == mean (50% probability)
    # z = 1  means value is 1 std above mean (~84% probability)
    # z = -1 means value is 1 std below mean (~16% probability)
    z_score = (value - mean) / standard_deviation

    # BEGINNER NOTE: math.erf is the "error function" — a
    # mathematical tool that lets us compute normal probabilities
    # using only Python's math module. The formula below converts
    # z-score to a probability (0 to 1).
    # This is equivalent to scipy.stats.norm.cdf(value, mean, std)
    probability = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))

    return probability


def calculate_probability_over_line(mean, standard_deviation, line):
    """
    Calculate the probability that a player EXCEEDS a prop line.

    This is the core of our prediction: "What is the chance
    LeBron scores MORE THAN 24.5 points tonight?"

    Args:
        mean (float): Player's projected stat average
        standard_deviation (float): Variability of that stat
        line (float): The prop line to beat

    Returns:
        float: Probability (0.0 to 1.0) of going OVER the line

    Example:
        LeBron projects 25.8 pts with std 6.2, line is 24.5
        → returns ~0.58 (58% chance to go over)
    """
    # P(over) = 1 - P(under or equal)
    # Because all probabilities must sum to 1
    probability_under = calculate_normal_cdf(line, mean, standard_deviation)
    probability_over = 1.0 - probability_under

    return probability_over


# ============================================================
# END SECTION: Normal Distribution Helpers
# ============================================================


# ============================================================
# SECTION: Poisson Distribution Helpers
# Poisson models count events (like assists or steals) that
# happen with a known average rate. Great for low-count stats.
# ============================================================

def calculate_poisson_probability(count, average_rate):
    """
    Calculate the probability of exactly `count` events
    given an average rate, using the Poisson distribution.

    Args:
        count (int): The exact number of events (e.g., 3 assists)
        average_rate (float): Average events per game (e.g., 5.6)

    Returns:
        float: Probability of exactly `count` events

    Example:
        If a player averages 2.1 steals, what's P(exactly 3)?
        → calculate_poisson_probability(3, 2.1) ≈ 0.189
    """
    # Guard: count must be a non-negative integer
    if count < 0:
        return 0.0
    if average_rate <= 0:
        # If average is 0, only P(0 events) = 1, everything else = 0
        return 1.0 if count == 0 else 0.0

    # BEGINNER NOTE: The Poisson formula is:
    # P(k events) = (e^(-λ) * λ^k) / k!
    # Where λ (lambda) = average_rate, k = count
    # math.factorial(k) computes k! (e.g., 5! = 120)
    try:
        probability = (
            (math.exp(-average_rate) * (average_rate ** count))
            / math.factorial(count)
        )
    except OverflowError:
        # For very large counts, factorial overflows → probability ≈ 0
        probability = 0.0

    return probability


def calculate_poisson_over_probability(line, average_rate):
    """
    Calculate the probability of exceeding `line` using Poisson.

    Sums P(k) for all k from ceil(line)+1 to a large number.

    Args:
        line (float): The prop line (e.g., 4.5 assists)
        average_rate (float): Player's average for this stat

    Returns:
        float: Probability of exceeding the line
    """
    # We need to check integer values above the line
    # e.g., line = 4.5 → we need count >= 5
    minimum_count_to_exceed = math.floor(line) + 1

    # Sum up probabilities for counts from min to a large ceiling
    # We stop at 3x the average rate + 20 to capture the tail
    # BEGINNER NOTE: The "+20" ensures we capture rare high-count games
    maximum_count_to_check = int(average_rate * 3) + 20

    total_probability_over = 0.0  # Start with zero, add each count's prob

    for count in range(minimum_count_to_exceed, maximum_count_to_check + 1):
        total_probability_over += calculate_poisson_probability(count, average_rate)

    return min(total_probability_over, 1.0)  # Cap at 1.0 just in case


# ============================================================
# END SECTION: Poisson Distribution Helpers
# ============================================================


# ============================================================
# SECTION: Descriptive Statistics
# Functions to summarize a list of numbers (e.g., simulation
# results or historical game logs).
# ============================================================

def calculate_mean(numbers_list):
    """
    Calculate the arithmetic mean (average) of a list of numbers.

    Args:
        numbers_list (list of float): The numbers to average

    Returns:
        float: The mean, or 0.0 if the list is empty

    Example:
        calculate_mean([20, 25, 30, 15]) → 22.5
    """
    if not numbers_list:
        return 0.0  # Avoid division by zero on empty list

    # Add up all values and divide by the count
    total = sum(numbers_list)
    count = len(numbers_list)
    return total / count


def calculate_standard_deviation(numbers_list):
    """
    Calculate how spread out a list of numbers is.
    A higher std means more variability (unpredictable player).

    Uses the sample standard deviation formula (divides by N-1)
    which is more accurate for small sample sizes.

    Args:
        numbers_list (list of float): Data points (game scores)

    Returns:
        float: Standard deviation, or 0.0 if fewer than 2 values

    Example:
        calculate_standard_deviation([20, 25, 30, 15]) → 6.45
    """
    if len(numbers_list) < 2:
        return 0.0  # Need at least 2 data points for variability

    # Use Python's built-in statistics module for accuracy
    # statistics.stdev uses the sample formula (N-1 denominator)
    return statistics.stdev(numbers_list)


def calculate_percentile(numbers_list, percentile):
    """
    Find the value at a given percentile in a sorted list.

    Args:
        numbers_list (list of float): Unsorted data points
        percentile (float): 0-100, e.g., 25 = 25th percentile

    Returns:
        float: The value at that percentile

    Example:
        calculate_percentile([10,20,30,40,50], 25) → 17.5
    """
    if not numbers_list:
        return 0.0  # Nothing to compute

    # Sort a copy (don't modify the original list)
    sorted_list = sorted(numbers_list)
    total_count = len(sorted_list)

    # Calculate the exact position in the sorted list
    # BEGINNER NOTE: index = (percentile / 100) * (N - 1)
    # This gives a fractional position we can interpolate between
    position = (percentile / 100.0) * (total_count - 1)

    # Get the integer index below and above our position
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))

    # If they're the same (exact integer position), return that value
    if lower_index == upper_index:
        return sorted_list[lower_index]

    # Otherwise, interpolate (average) between the two surrounding values
    # The fraction tells us how far between the two we are
    fraction = position - lower_index
    interpolated_value = (
        sorted_list[lower_index] * (1.0 - fraction)
        + sorted_list[upper_index] * fraction
    )
    return interpolated_value


def calculate_median(numbers_list):
    """
    Find the middle value of a list (50th percentile).
    Less sensitive to outliers than the mean.

    Args:
        numbers_list (list of float): Data points

    Returns:
        float: The median value
    """
    return calculate_percentile(numbers_list, 50)


# ============================================================
# END SECTION: Descriptive Statistics
# ============================================================


# ============================================================
# SECTION: Edge and Probability Utilities
# These helpers translate raw probabilities into
# meaningful edge percentages and labels.
# ============================================================

def calculate_edge_percentage(probability_over):
    """
    Convert a probability (0-1) into an "edge" value showing
    how much better than 50/50 our prediction is.

    Edge = (probability - 0.5) * 100
    So 60% probability = +10% edge (10 points better than coin flip)

    Args:
        probability_over (float): Probability of going over (0-1)

    Returns:
        float: Edge in percentage points (-50 to +50)

    Example:
        0.63 probability → +13.0% edge (lean OVER)
        0.42 probability → -8.0% edge (lean UNDER)
    """
    # Subtract 50% baseline (fair coin flip) and multiply to percentage
    edge = (probability_over - 0.5) * 100.0
    return edge


def clamp_probability(probability):
    """
    Ensure a probability stays between 0.01 and 0.99.
    We never want to say something is 100% certain.

    Args:
        probability (float): Any probability value

    Returns:
        float: Clamped between 0.01 and 0.99
    """
    return max(0.01, min(0.99, probability))


def round_to_decimal(value, decimal_places):
    """
    Round a number to a specified number of decimal places.

    Args:
        value (float): Number to round
        decimal_places (int): How many decimal places to keep

    Returns:
        float: Rounded value

    Example:
        round_to_decimal(3.14159, 2) → 3.14
    """
    multiplier = 10 ** decimal_places
    return math.floor(value * multiplier + 0.5) / multiplier


def sample_from_normal_distribution(mean, standard_deviation):
    """
    Draw a single random sample from a normal distribution.
    Used in Monte Carlo simulation to simulate one game's result.

    Args:
        mean (float): Center of the distribution
        standard_deviation (float): Spread of the distribution

    Returns:
        float: A random value, most likely near the mean

    Example:
        If mean=25.0 and std=6.0, might return 22.3 or 28.7
        Most results will be within 1-2 standard deviations
    """
    # Guard against invalid std
    if standard_deviation <= 0:
        return mean

    # random.gauss draws from a normal distribution
    # BEGINNER NOTE: This is the core randomness of Monte Carlo!
    # Each call gives a different number, simulating one game
    raw_sample = random.gauss(mean, standard_deviation)

    # Stats can't be negative (can't score -5 points)
    return max(0.0, raw_sample)


def sample_skew_normal(mean, standard_deviation, skew_param=0.0):
    """
    Draw a single random sample from a skew-normal distribution.

    NBA stats are right-skewed (hard floor at 0, occasional explosion games
    that pull the distribution right). Standard normal sampling underestimates
    the probability of big games and overestimates the floor.

    This implementation uses the standard composition method:
        1. Draw two independent standard normals u, v
        2. If skew_param == 0, return the standard normal (reduces to Gaussian)
        3. Else, compute the skew-normal variate using the sign trick

    Reference: Azzalini (1985) — "A class of distributions which includes
    the normal ones", Scandinavian Journal of Statistics.

    Args:
        mean (float): Center of the distribution (projected stat average)
        standard_deviation (float): Spread of the distribution
        skew_param (float): Skewness parameter α.
            0.0  = symmetric normal (no skew)
            > 0  = right skew (long tail toward larger values — NBA typical)
            < 0  = left skew (rare for sports stats)
            Practical range for NBA: 0.5–1.5

    Returns:
        float: A random sample, clamped to ≥ 0.0 (stats can't be negative)

    Example:
        Points: sample_skew_normal(22.0, 5.5, skew_param=0.8)
        Threes: sample_skew_normal(2.5, 1.5, skew_param=1.2)
    """
    if standard_deviation <= 0:
        return max(0.0, mean)

    if abs(skew_param) < 1e-9:
        # No skew: fall back to standard normal
        return max(0.0, random.gauss(mean, standard_deviation))

    # Skew-normal composition:
    # delta = skew_param / sqrt(1 + skew_param^2)
    # Compute two independent standard normals
    delta = skew_param / math.sqrt(1.0 + skew_param * skew_param)
    u0 = random.gauss(0.0, 1.0)
    v  = random.gauss(0.0, 1.0)

    # The skew-normal variate z (zero mean, unit variance):
    z = delta * abs(u0) + math.sqrt(1.0 - delta * delta) * v

    # Scale to the desired mean and std
    # Note: The skew-normal mean is mu + omega * delta * sqrt(2/pi)
    # We shift so that the output is centred at `mean` exactly.
    skew_mean_shift = delta * math.sqrt(2.0 / math.pi)
    raw_sample = mean + standard_deviation * (z - skew_mean_shift)

    return max(0.0, raw_sample)


# Default skew parameters by NBA stat type (C5)
# These reflect the right-skewed nature of each stat category.
# Higher skew_param = more right-skewed = more explosion-game probability.
STAT_SKEW_PARAMS = {
    "points":    0.8,   # Moderate right skew (star can always go nuclear)
    "rebounds":  0.6,   # Moderate skew (rebounding is position-dependent)
    "assists":   0.5,   # Mild skew (playmakers are somewhat consistent)
    "threes":    1.2,   # Highly right-skewed (shooting is very streaky)
    "steals":    1.0,   # Right-skewed (rare stat, can spike)
    "blocks":    1.0,   # Right-skewed (rare stat, can spike)
    "turnovers": 0.4,   # Mild skew (more predictable for high-usage players)
}


def get_stat_skew_param(stat_type):
    """
    Return the default skew parameter for a given stat type. (C5)

    Args:
        stat_type (str): e.g. 'points', 'threes', 'rebounds'

    Returns:
        float: Skew parameter α for sample_skew_normal()
    """
    return STAT_SKEW_PARAMS.get(stat_type.lower() if stat_type else "", 0.6)


# ============================================================
# SECTION: KDE Sampling from Game Logs (C11)
# When a player has 15+ recent game log entries, build a
# non-parametric Kernel Density Estimate and sample from it
# instead of using the parametric skew-normal distribution.
# This captures player-specific distribution shapes — e.g., a
# player who tends to score either 15 or 30 but never 22.
# ============================================================

# Minimum game log entries required to use KDE instead of skew-normal
KDE_MIN_GAME_LOGS = 15


def _kde_bandwidth(data):
    """
    Estimate KDE bandwidth using Silverman's rule of thumb.

    Bandwidth h = 1.06 * std * n^(-1/5)
    This is a standard automatic bandwidth selector for unimodal data.

    Args:
        data (list of float): Sample data points

    Returns:
        float: Bandwidth h (always > 0)
    """
    n = len(data)
    if n < 2:
        return 1.0
    try:
        std = statistics.stdev(data)
    except statistics.StatisticsError:
        std = 1.0
    if std < 1e-6:
        return 0.5
    return 1.06 * std * (n ** (-0.2))


def sample_from_kde(game_log_values, bandwidth=None):
    """
    Draw a single sample from a Kernel Density Estimate built from game logs. (C11)

    Algorithm (simple KDE sampling):
    1. Pick a random data point from the game logs (uniform selection)
    2. Add Gaussian noise with std = bandwidth
    3. Clamp result to >= 0.0 (stats can't be negative)

    This preserves the empirical distribution shape — if a player has a
    bimodal distribution (either goes big or goes quiet), the KDE captures
    that, unlike a parametric normal/skew-normal which would smooth it out.

    Args:
        game_log_values (list of float): Recent game stat values
            e.g., [22.0, 15.0, 31.0, 8.0, 27.0, ...]
            Must have at least KDE_MIN_GAME_LOGS (15) entries.
        bandwidth (float, optional): KDE bandwidth (kernel width).
            When None, computed automatically via Silverman's rule.

    Returns:
        float: A sampled value >= 0.0, or None if insufficient data.

    Example:
        Player has recent logs [8, 15, 32, 11, 28, 14, 9, 33, 12, 27, 10, 30, 13, 25, 16]
        → sample_from_kde(...) might return ~10.8 or ~29.3 (bimodal-shaped)
    """
    if not game_log_values or len(game_log_values) < KDE_MIN_GAME_LOGS:
        return None  # Caller should fall back to skew-normal

    if bandwidth is None:
        bandwidth = _kde_bandwidth(game_log_values)

    # Pick a random kernel center from the data, then perturb
    center = random.choice(game_log_values)
    noise = random.gauss(0.0, bandwidth)
    return max(0.0, center + noise)


def should_use_kde(game_log_values):
    """
    Return True if there are enough game logs to use KDE sampling. (C11)

    Args:
        game_log_values (list of float): Recent game stat values

    Returns:
        bool: True if len(game_log_values) >= KDE_MIN_GAME_LOGS
    """
    return bool(game_log_values) and len(game_log_values) >= KDE_MIN_GAME_LOGS

# ============================================================
# END SECTION: KDE Sampling from Game Logs
# ============================================================


# ============================================================
# END SECTION: Edge and Probability Utilities
# ============================================================


# ============================================================
# SECTION: Flex EV and Correlation Helpers (W2, W9)
# Additional math utilities for the entry optimizer.
# ============================================================

def calculate_flex_ev(pick_probabilities, payout_table, entry_fee):
    """
    Calculate the expected value (EV) of a flex-play entry. (W9)

    Convenience wrapper around the full EV calculation, returning
    just the essential numbers for quick comparison across entries.

    Args:
        pick_probabilities (list of float): Win probability for each pick (0-1)
        payout_table (dict): {hits: multiplier} for this entry size
        entry_fee (float): Dollar amount bet

    Returns:
        dict: {
            'ev_dollars': float (net EV),
            'roi': float (net EV / entry_fee),
            'all_hit_prob': float (P of hitting all picks),
            'prob_at_least_one_miss': float (P of missing at least one)
        }

    Example:
        6 picks at 62% each, $10 entry → ev_dollars, roi, all-hit-prob
    """
    import itertools as _itertools

    n = len(pick_probabilities)
    if n == 0:
        return {"ev_dollars": 0.0, "roi": 0.0, "all_hit_prob": 0.0,
                "prob_at_least_one_miss": 1.0}

    # --- Probability of exactly k hits ---
    prob_for_k = {}
    for k in range(n + 1):
        total_p = 0.0
        for winning_idx in _itertools.combinations(range(n), k):
            winning_set = set(winning_idx)
            combo_p = 1.0
            for i in range(n):
                combo_p *= (pick_probabilities[i] if i in winning_set
                            else 1.0 - pick_probabilities[i])
            total_p += combo_p
        prob_for_k[k] = total_p

    # --- Expected return ---
    total_return = sum(prob_for_k[k] * payout_table.get(k, 0.0) * entry_fee
                       for k in range(n + 1))
    net_ev = total_return - entry_fee
    roi = net_ev / entry_fee if entry_fee > 0 else 0.0

    # --- All-hit probability ---
    all_hit_prob = prob_for_k.get(n, 0.0)

    return {
        "ev_dollars": round(net_ev, 2),
        "roi": round(roi, 4),
        "all_hit_prob": round(all_hit_prob, 6),
        "prob_at_least_one_miss": round(1.0 - all_hit_prob, 6),
    }


def calculate_correlation_discount(same_game_pick_count):
    """
    Compute the EV discount multiplier for correlated same-game picks. (W2)

    When picks share a game, their outcomes are correlated — a blowout
    or overtime hit affects ALL legs simultaneously.

    Args:
        same_game_pick_count (int): How many picks from the same game

    Returns:
        float: Multiplier to apply to entry EV (1.0 = no discount)

    Example:
        2 picks same game → 0.95 (5% penalty)
        3+ picks same game → 0.88 (12% penalty)
    """
    if same_game_pick_count <= 1:
        return 1.0   # No correlation discount
    elif same_game_pick_count == 2:
        return 0.95  # 5% penalty — moderate correlation
    else:
        return 0.88  # 12% penalty — high correlation (3+ same-game legs)

# ============================================================
# END SECTION: Flex EV and Correlation Helpers
# ============================================================
