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

    If only one side is provided, assumes the other side is the standard
    -110 complement (not a mirror of side 1), which is the correct
    assumption for most NBA prop markets.

    Args:
        odds_side1 (float): American odds for side 1 (e.g. -110)
        odds_side2 (float or None): American odds for side 2 (e.g. -110)
            If None, defaults to -110 (standard market complement).

    Returns:
        float: Vig as a percentage (e.g. 0.0476 = 4.76% for a -110/-110 market)

    Example:
        get_vig_percentage(-110, -110) → 0.0476
        get_vig_percentage(-120)       → uses -110 as complement, not -120 mirror
    """
    try:
        p1 = american_odds_to_implied_probability(float(odds_side1))
        if odds_side2 is None:
            # FIXED: Default to -110 (standard complement) not a mirror of side 1
            # This is the correct assumption for most DraftKings prop markets
            p2 = american_odds_to_implied_probability(-110.0)
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


def devig_probabilities(over_odds, under_odds):
    """
    Remove the bookmaker's vig to get the true fair probabilities for both sides.

    Uses the multiplicative (proportional) devig method, which is considered
    more accurate than the additive method for NBA props.

    BEGINNER NOTE: When a book offers -110 on both sides, the implied
    probabilities sum to 1.048 (not 1.0). This 4.8% excess is the vig.
    Devigging scales both probabilities down proportionally so they sum to 1.0.
    The resulting "fair" probabilities are the book's true assessment.

    Args:
        over_odds (float): American odds for the Over side (e.g. -115)
        under_odds (float): American odds for the Under side (e.g. -105)

    Returns:
        tuple: (fair_over_prob, fair_under_prob) — both float, sum to 1.0

    Examples:
        devig_probabilities(-110, -110) → (0.5, 0.5)
        devig_probabilities(-120, +100) → (0.545, 0.455) approximately
    """
    try:
        p_over_raw  = american_odds_to_implied_probability(float(over_odds))
        p_under_raw = american_odds_to_implied_probability(float(under_odds))
        overround = p_over_raw + p_under_raw

        if overround <= 0:
            return (0.5, 0.5)

        # Multiplicative devig: divide each side by the overround
        fair_over  = p_over_raw  / overround
        fair_under = p_under_raw / overround

        return (round(fair_over, 6), round(fair_under, 6))
    except (ValueError, TypeError):
        return (0.5, 0.5)


def calculate_half_kelly_ev(model_probability, odds, bankroll=1.0):
    """
    Calculate the Half Kelly Criterion stake for a bet.

    BEGINNER NOTE: The Kelly Criterion tells you the optimal fraction of
    your bankroll to bet to maximize long-run growth. Half Kelly (50% of
    the Kelly fraction) reduces variance while capturing most of the edge.

    Formula:
        Kelly fraction f = (b*p - q) / b
        where b = net payout ratio, p = win prob, q = 1-p
        Half Kelly = f / 2

    Args:
        model_probability (float): Model's win probability (0-1)
        odds (float): American odds on the bet (e.g. -110, +150)
        bankroll (float): Total bankroll. Default 1.0 (returns fraction).

    Returns:
        dict: {
            'kelly_fraction': float (full Kelly as fraction of bankroll),
            'half_kelly_fraction': float (recommended 50% Kelly fraction),
            'half_kelly_stake': float (dollar amount at given bankroll),
            'ev': float (expected value per unit staked),
        }

    Example:
        calculate_half_kelly_ev(0.62, -110, bankroll=1000)
        → stake about $44.50 (4.45% of $1000 bankroll)
    """
    try:
        p = max(0.001, min(0.999, float(model_probability)))
        q = 1.0 - p
        b = odds_to_payout_multiplier(float(odds)) - 1.0  # Net payout ratio
        if b <= 0:
            return {"kelly_fraction": 0.0, "half_kelly_fraction": 0.0,
                    "half_kelly_stake": 0.0, "ev": 0.0}

        # Kelly fraction
        kelly_f = (b * p - q) / b

        # Negative Kelly → no edge → don't bet
        kelly_f = max(0.0, kelly_f)
        half_kelly = kelly_f / 2.0

        ev = p * b - q  # Expected value per unit staked

        return {
            "kelly_fraction": round(kelly_f, 6),
            "half_kelly_fraction": round(half_kelly, 6),
            "half_kelly_stake": round(half_kelly * float(bankroll), 2),
            "ev": round(ev, 6),
        }
    except (ValueError, TypeError):
        return {"kelly_fraction": 0.0, "half_kelly_fraction": 0.0,
                "half_kelly_stake": 0.0, "ev": 0.0}


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
