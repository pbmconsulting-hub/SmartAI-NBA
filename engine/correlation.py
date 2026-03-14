# ============================================================
# FILE: engine/correlation.py
# PURPOSE: Player correlation modeling for parlay construction.
#          Models positive/negative teammate correlations, game-level
#          correlations from pace/total, and usage cannibalization.
# CONNECTS TO: engine/entry_optimizer.py, pages/4 (Entry Builder)
# CONCEPTS COVERED: Pearson correlation, Gaussian copula (simplified),
#                   usage rate, game environment correlation
# ============================================================

# BEGINNER NOTE: Correlation in parlays matters because if two players
# are positively correlated (e.g. both benefit from a fast-paced game),
# the joint probability of both going over is HIGHER than multiplying
# their individual probabilities. Negative correlation means one player's
# success hurts the other's chances (usage competition).

import math
import statistics

# Maximum correlation adjustment magnitude (conservative cap)
MAX_CORRELATION_ADJUSTMENT = 0.15  # 15% max adjustment to joint probability

# Platform-specific default implied probabilities
# BEGINNER NOTE: These are the breakeven win rates for each platform's payout structure
PLATFORM_IMPLIED_PROB = {
    "PrizePicks": 0.526,   # Based on PrizePicks power/flex payout tables
    "Underdog":   0.500,   # Underdog uses ~50/50 payouts
    "DraftKings": 0.5238,  # Standard -110 vig (52.38% breakeven)
    "default":    0.526,   # Conservative default
}


def calculate_pearson_correlation(values_a, values_b):
    """
    Calculate the Pearson correlation coefficient between two lists of values.

    BEGINNER NOTE: Pearson correlation ranges from -1 (perfectly opposite)
    to +1 (perfectly aligned). 0 = no linear relationship.
    We use this to see if two players' stats move together.

    Args:
        values_a (list of float): Player A's stat values across games
        values_b (list of float): Player B's stat values across games

    Returns:
        float: Pearson r (-1 to 1), or 0.0 if insufficient data
    """
    if len(values_a) < 3 or len(values_b) < 3:
        return 0.0

    n = min(len(values_a), len(values_b))
    if n < 3:
        return 0.0

    a = values_a[:n]
    b = values_b[:n]

    try:
        mean_a = statistics.mean(a)
        mean_b = statistics.mean(b)

        num = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
        den_a = math.sqrt(sum((v - mean_a) ** 2 for v in a))
        den_b = math.sqrt(sum((v - mean_b) ** 2 for v in b))

        if den_a < 1e-9 or den_b < 1e-9:
            return 0.0

        r = num / (den_a * den_b)
        return max(-1.0, min(1.0, r))
    except (ValueError, ZeroDivisionError, statistics.StatisticsError):
        return 0.0


def calculate_player_correlation(player1_logs, player2_logs, stat_type):
    """
    Compute empirical correlation between two players' stats from game logs.

    Args:
        player1_logs (list of dict): Game logs for player 1 (must have 'GAME_DATE')
        player2_logs (list of dict): Game logs for player 2
        stat_type (str): Stat to correlate ('points', 'rebounds', etc.)

    Returns:
        float: Pearson correlation coefficient (-1 to 1)
    """
    # BEGINNER NOTE: We need to match games where BOTH players played.
    # Map by game date so we only include shared games.
    stat_key_map = {
        "points": "PTS", "rebounds": "REB", "assists": "AST",
        "steals": "STL", "blocks": "BLK", "threes": "FG3M",
        "turnovers": "TOV",
    }
    api_key = stat_key_map.get(stat_type.lower(), stat_type.upper())

    def _get_date_stat_map(logs, key):
        result = {}
        for g in (logs or []):
            date = g.get("GAME_DATE", g.get("game_date", ""))
            if date:
                try:
                    val = float(g.get(key, 0) or 0)
                    result[date] = val
                except (ValueError, TypeError):
                    pass
        return result

    p1_map = _get_date_stat_map(player1_logs, api_key)
    p2_map = _get_date_stat_map(player2_logs, api_key)

    shared_dates = sorted(set(p1_map.keys()) & set(p2_map.keys()))

    if len(shared_dates) < 3:
        return 0.0

    a = [p1_map[d] for d in shared_dates]
    b = [p2_map[d] for d in shared_dates]
    return calculate_pearson_correlation(a, b)


def calculate_game_environment_correlation(game_total, stat_type):
    """
    Estimate how a game's over/under total affects players' stat probabilities.

    BEGINNER NOTE: High-scoring (high total) games benefit scorers and assist
    men. Low-total games tend to suppress counting stats across the board.
    This is a "game-environment" correlation factor.

    Args:
        game_total (float or None): The game's over/under total (e.g. 228.5)
        stat_type (str): The prop stat type ('points', 'assists', etc.)

    Returns:
        float: Correlation boost/penalty per player in this game (-MAX_CORRELATION_ADJUSTMENT to +MAX_CORRELATION_ADJUSTMENT)
    """
    if game_total is None:
        return 0.0

    # BEGINNER NOTE: League average game total is ~220-225. High totals (230+)
    # create positive environment for scorers; low totals (210-) hurt them.
    LEAGUE_AVG_TOTAL = 222.0

    deviation = game_total - LEAGUE_AVG_TOTAL
    # Scale: ±10 pts from average → ±0.05 correlation factor
    factor = deviation * 0.005

    # Defense/hustle stats are less affected by game total
    low_impact_stats = {"steals", "blocks", "turnovers"}
    if stat_type.lower() in low_impact_stats:
        factor *= 0.3

    return max(-0.12, min(0.12, factor))


def calculate_usage_cannibalization(player1_usage_rate, player2_usage_rate, stat_type, is_teammate):
    """
    Model negative correlation where one player's high usage reduces teammate's.

    BEGINNER NOTE: A team's total possessions are finite. If Player A uses 30%
    of possessions, Player B has fewer left. When both players have high usage
    rates and play the same position, there's "cannibalization" — if A goes
    huge (high usage game), B likely gets fewer touches.

    Args:
        player1_usage_rate (float): Player 1 usage rate (0-1, e.g. 0.28 for 28%)
        player2_usage_rate (float): Player 2 usage rate (0-1)
        stat_type (str): Stat type being analyzed
        is_teammate (bool): Whether the two players are on the same team

    Returns:
        float: Negative correlation factor (negative means their props are negatively correlated)
    """
    if not is_teammate:
        return 0.0

    # Only scoring-related stats have usage competition
    scoring_stats = {"points", "assists", "threes", "fantasy_score"}
    if stat_type.lower() not in scoring_stats:
        return 0.0

    # Combined usage > 50% = significant cannibalization risk
    combined = (player1_usage_rate or 0.20) + (player2_usage_rate or 0.20)
    if combined > 0.50:
        # Strong negative correlation when total usage is high
        cannibalization = -(combined - 0.50) * 0.4
        return max(-MAX_CORRELATION_ADJUSTMENT, cannibalization)

    return 0.0


def get_teammate_correlation(stat_type):
    """
    Return estimated correlation for two teammates' prop outcomes based on stat type.

    Uses heuristic values based on NBA positional and usage patterns.
    These represent empirical estimates when historical log data is unavailable.

    BEGINNER NOTE: Points is highly competitive between teammates (negative),
    while rebounds can be complementary (one's miss can become another's board).
    Assists correlate positively with scorers (need each other).

    Args:
        stat_type (str): Prop stat type

    Returns:
        float: Estimated correlation (-1 to 1)
    """
    # BEGINNER NOTE: These heuristics are based on NBA research:
    # - Points: teammates compete for shots → mild negative
    # - Rebounds: one player's missed shot = another's opportunity → mild positive
    # - Assists: playmaker + scorer are positively linked
    # - Steals/blocks: mostly independent, slight positive (team effort)
    heuristics = {
        "points":               -0.08,   # Mild negative (shot competition)
        "rebounds":              0.05,   # Mild positive (team rebounding)
        "assists":               0.12,   # Positive (playmakers feed scorers)
        "threes":               -0.05,   # Mild negative (shot competition)
        "steals":                0.04,   # Slight positive (team defense)
        "blocks":                0.03,   # Slight positive
        "turnovers":             0.06,   # Mild positive (high usage = more TOV for both)
        "fantasy_score":        -0.06,   # Overall mild negative
        "points_rebounds":       0.01,   # Near-zero
        "points_assists":        0.08,   # Positive (scorer and playmaker feed each other)
        "rebounds_assists":      0.04,   # Slight positive
        "points_rebounds_assists": 0.02, # Near-zero (complex combo)
    }
    return heuristics.get(stat_type.lower(), 0.0)


def adjust_parlay_probability(individual_probs, correlation_matrix):
    """
    Adjust the joint probability of a parlay using a simplified Gaussian copula.

    BEGINNER NOTE: For independent props, parlay probability = p1 * p2 * p3 * ...
    But correlated props need adjustment. Positive correlation means the joint
    probability is HIGHER than the product. Negative correlation = LOWER.
    We use a simplified linear correction capped at ±15%.

    Args:
        individual_probs (list of float): Individual win probabilities for each leg
        correlation_matrix (list of list of float): Square matrix of pairwise correlations
            e.g. [[1.0, 0.1], [0.1, 1.0]] for two props with 0.1 correlation

    Returns:
        float: Adjusted joint probability (0.0 to 1.0)

    Example:
        Two players, p=[0.65, 0.60], correlation=0.2
        → base prob: 0.39, correlation boost: ~+0.01 → 0.40
    """
    if not individual_probs:
        return 0.0

    if len(individual_probs) == 1:
        return individual_probs[0]

    # Base: independent product
    base_prob = 1.0
    for p in individual_probs:
        base_prob *= max(0.001, min(0.999, p))

    n = len(individual_probs)
    if not correlation_matrix or len(correlation_matrix) < n:
        return base_prob

    # Compute weighted average pairwise correlation
    total_corr = 0.0
    pair_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            try:
                c = float(correlation_matrix[i][j])
            except (IndexError, TypeError, ValueError):
                c = 0.0
            total_corr += c
            pair_count += 1

    if pair_count == 0:
        return base_prob

    avg_corr = total_corr / pair_count

    # BEGINNER NOTE: Adjustment formula (simplified linear copula correction):
    # positive corr → multiply base_prob by (1 + corr * avg_prob_factor)
    # negative corr → multiply base_prob by (1 - |corr| * avg_prob_factor)
    avg_prob = sum(individual_probs) / n
    # The adjustment is proportional to both correlation and how extreme the probs are
    prob_factor = avg_prob * (1 - avg_prob)  # maximized at p=0.5
    # BEGINNER NOTE: Scale factor of 2.0 normalizes the prob_factor (max 0.25 at p=0.5)
    # so that full correlation (r=1) with average probability gives a meaningful adjustment.
    # Without this factor, the adjustment would be too small to matter.
    _COPULA_SCALE = 2.0
    adjustment = avg_corr * prob_factor * _COPULA_SCALE

    # Cap adjustment to MAX_CORRELATION_ADJUSTMENT
    adjustment = max(-MAX_CORRELATION_ADJUSTMENT, min(MAX_CORRELATION_ADJUSTMENT, adjustment))

    adjusted = base_prob * (1.0 + adjustment)
    return max(0.0001, min(0.9999, adjusted))


def build_correlation_matrix(picks, game_logs_by_player=None):
    """
    Build a pairwise correlation matrix for a list of picks.

    For each pair of picks, compute correlation using historical game log data
    if available, otherwise use heuristic values.

    BEGINNER NOTE: The matrix entry [i][j] is the correlation between pick i
    and pick j. Same player = 1.0. Teammates = heuristic or empirical.
    Opponents = game-environment correlation.

    Args:
        picks (list of dict): Pick dicts with 'player_name', 'team', 'stat_type'
        game_logs_by_player (dict or None): {player_name: [game_log_dicts]}

    Returns:
        list of list of float: n×n correlation matrix
    """
    n = len(picks)
    if n == 0:
        return []

    # Identity matrix as baseline
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0

    for i in range(n):
        for j in range(i + 1, n):
            p1 = picks[i]
            p2 = picks[j]

            p1_name = str(p1.get("player_name", "")).lower()
            p2_name = str(p2.get("player_name", "")).lower()
            p1_team = str(p1.get("team", "")).upper()
            p2_team = str(p2.get("team", "")).upper()
            stat1   = str(p1.get("stat_type", "points")).lower()
            stat2   = str(p2.get("stat_type", "points")).lower()

            # Same player — identical prop (high correlation)
            if p1_name == p2_name:
                corr = 0.85
            # Teammates
            elif p1_team and p2_team and p1_team == p2_team:
                # Try empirical first
                if game_logs_by_player:
                    logs1 = game_logs_by_player.get(p1_name, [])
                    logs2 = game_logs_by_player.get(p2_name, [])
                    if stat1 == stat2 and len(logs1) >= 5 and len(logs2) >= 5:
                        corr = calculate_player_correlation(logs1, logs2, stat1)
                    else:
                        corr = get_teammate_correlation(stat1)
                else:
                    corr = get_teammate_correlation(stat1)
            else:
                # Opponents — low correlation
                # Game-environment correlation applies when same game
                # For now: 0 unless game-level context provided
                corr = 0.0

            # Cap
            corr = max(-MAX_CORRELATION_ADJUSTMENT, min(MAX_CORRELATION_ADJUSTMENT, corr))
            matrix[i][j] = corr
            matrix[j][i] = corr

    return matrix


def get_correlation_summary(picks, correlation_matrix):
    """
    Produce a human-readable summary of correlation risk for a set of picks.

    Args:
        picks (list of dict): Picks with player_name, team, stat_type
        correlation_matrix (list of list of float): Pairwise correlation matrix

    Returns:
        dict: {
            'risk_level': str,      # 'low', 'medium', 'high'
            'avg_correlation': float,
            'correlated_pairs': list of dict,
            'description': str,
        }
    """
    n = len(picks)
    if n < 2 or not correlation_matrix:
        return {
            "risk_level": "low",
            "avg_correlation": 0.0,
            "correlated_pairs": [],
            "description": "Single pick — no correlation risk.",
        }

    pairs = []
    total_corr = 0.0
    pair_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            try:
                c = float(correlation_matrix[i][j])
            except (IndexError, TypeError, ValueError):
                c = 0.0
            total_corr += c
            pair_count += 1

            if abs(c) > 0.05:
                pairs.append({
                    "player1": picks[i].get("player_name", "?"),
                    "player2": picks[j].get("player_name", "?"),
                    "correlation": round(c, 3),
                    "direction": "positive" if c > 0 else "negative",
                })

    avg = total_corr / max(pair_count, 1)

    if avg > 0.10:
        risk_level = "high"
        desc = "⚠️ High positive correlation — these players likely go over/under together. Parlay probability is boosted but also means all can fail together."
    elif avg < -0.05:
        risk_level = "medium"
        desc = "⚡ Negative correlation detected — some players compete for usage. If one goes huge, another may underperform."
    elif abs(avg) < 0.03:
        risk_level = "low"
        desc = "✅ Low correlation — picks are relatively independent. Good for parlay construction."
    else:
        risk_level = "medium"
        desc = "ℹ️ Moderate correlation — some relationship between picks. Consider diversifying."

    return {
        "risk_level": risk_level,
        "avg_correlation": round(avg, 4),
        "correlated_pairs": pairs,
        "description": desc,
    }
