# engine/odds_engine.py
# Odds and implied probability calculations for prop betting.
# Standard library only — no numpy/scipy/pandas.


def american_odds_to_implied_probability(odds):
    """
    Convert American odds to implied probability.

    Args:
        odds (int or float): American odds (e.g. -110, +150, -200)

    Returns:
        float: Implied probability (0.0 to 1.0)

    Examples:
        -110  → 0.5238 (52.38% breakeven)
        +150  → 0.4000 (40.00%)
        -200  → 0.6667 (66.67%)
    """
    try:
        odds = float(odds)
        if odds < 0:
            return abs(odds) / (abs(odds) + 100.0)
        else:
            return 100.0 / (odds + 100.0)
    except (ValueError, TypeError):
        return 0.5238  # Default to -110 breakeven


def implied_probability_to_american_odds(prob):
    """
    Convert implied probability to American odds.

    Args:
        prob (float): Implied probability (0.0 to 1.0)

    Returns:
        float: American odds (negative for favorites, positive for underdogs)

    Examples:
        0.5238 → -110
        0.40   → +150
    """
    try:
        prob = float(prob)
        prob = max(0.001, min(0.999, prob))
        if prob >= 0.5:
            return round(-(prob / (1.0 - prob)) * 100.0, 1)
        else:
            return round(((1.0 - prob) / prob) * 100.0, 1)
    except (ValueError, TypeError):
        return -110.0


def calculate_breakeven_probability(odds):
    """
    Calculate the exact breakeven probability needed to profit at these odds.

    This is the same as implied probability for a single side.
    At breakeven, EV = 0.

    Args:
        odds (int or float): American odds

    Returns:
        float: Breakeven probability (0.0 to 1.0)

    Example:
        -110 → 0.5238 (need to win 52.38% of the time to break even)
    """
    return american_odds_to_implied_probability(odds)


def get_vig_percentage(odds_side1, odds_side2=None):
    """
    Calculate the vig (juice) percentage on a two-sided market.

    If only one side is provided, assumes the other side has symmetric odds.

    Args:
        odds_side1 (float): American odds for side 1 (e.g. -110)
        odds_side2 (float or None): American odds for side 2 (e.g. -110)
            If None, assumes symmetric (both sides same odds).

    Returns:
        float: Vig as a percentage (e.g. 0.0476 = 4.76% for a -110/-110 market)

    Example:
        get_vig_percentage(-110, -110) → 0.0476
    """
    try:
        p1 = american_odds_to_implied_probability(float(odds_side1))
        if odds_side2 is None:
            # Mirror the first side
            p2 = american_odds_to_implied_probability(float(odds_side1))
        else:
            p2 = american_odds_to_implied_probability(float(odds_side2))
        overround = p1 + p2
        return round(max(0.0, overround - 1.0), 6)
    except (ValueError, TypeError):
        return 0.0476  # Default -110/-110 vig


def calculate_true_edge(model_probability, odds):
    """
    Compute the true betting edge as model_probability minus implied probability.

    This is the correct edge calculation — NOT model_prob - 0.50.
    At -110 odds, the implied probability is 52.38%, so you need
    a model probability above 52.38% just to break even.

    Args:
        model_probability (float): Model's estimated win probability (0.0 to 1.0)
        odds (int or float): American odds on the bet (e.g. -110, +100)

    Returns:
        float: True edge as a decimal (e.g. 0.05 = 5% edge)
            Positive = value bet, Negative = no value

    Example:
        calculate_true_edge(0.60, -110) → 0.0762 (7.62% true edge)
        calculate_true_edge(0.52, -110) → -0.0038 (no edge at -110)
    """
    try:
        implied = american_odds_to_implied_probability(float(odds))
        return round(float(model_probability) - implied, 6)
    except (ValueError, TypeError):
        return 0.0


def calculate_expected_value_with_odds(model_probability, odds, stake=1.0):
    """
    Calculate the true expected value of a bet accounting for juice.

    EV = (p_win * net_win) - (p_lose * stake)
    where net_win is derived from the actual odds.

    Args:
        model_probability (float): Model's win probability (0.0 to 1.0)
        odds (int or float): American odds (e.g. -110, +150)
        stake (float): Amount wagered. Default 1.0

    Returns:
        float: Expected value in stake units.
            Positive = profitable bet, Negative = losing bet

    Example:
        calculate_expected_value_with_odds(0.60, -110, stake=100) → 9.09
    """
    try:
        p = float(model_probability)
        stake = float(stake)
        odds = float(odds)
        net_win = odds_to_payout_multiplier(odds) * stake - stake
        ev = p * net_win - (1.0 - p) * stake
        return round(ev, 4)
    except (ValueError, TypeError):
        return 0.0


def odds_to_payout_multiplier(american_odds):
    """
    Convert American odds to a gross payout multiplier.

    The payout multiplier is the total return per unit staked (including stake).

    Args:
        american_odds (int or float): American odds (e.g. -110, +150)

    Returns:
        float: Gross payout multiplier (e.g. 1.909 for -110, 2.50 for +150)

    Examples:
        -110 → 1.9091 (bet $110, get back $210 total → 1.909x)
        +150 → 2.5    (bet $100, get back $250 total → 2.5x)
        -200 → 1.5    (bet $200, get back $300 total → 1.5x)
    """
    try:
        odds = float(american_odds)
        if odds < 0:
            return round(1.0 + (100.0 / abs(odds)), 6)
        else:
            return round(1.0 + (odds / 100.0), 6)
    except (ValueError, TypeError):
        return 1.9091  # Default -110 payout
