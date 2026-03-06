# ============================================================
# FILE: engine/math_helpers.py
# PURPOSE: All mathematical and statistical functions needed
#          by the SmartAI-NBA engine — built from scratch using
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


# ============================================================
# END SECTION: Edge and Probability Utilities
# ============================================================
