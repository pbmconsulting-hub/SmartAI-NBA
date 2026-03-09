# ============================================================
# FILE: engine/projections.py
# PURPOSE: Build stat projections for players given tonight's
#          game context (opponent, pace, home/away, rest).
#          Takes raw player averages and adjusts them for
#          the specific matchup.
# CONNECTS TO: data_manager.py (gets player data),
#              simulation.py (gets the adjusted projections)
# CONCEPTS COVERED: Matchup adjustments, pace adjustments,
#                   per-game rate calculations
# ============================================================

# Standard library only
import math  # For rounding and calculation helpers


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# League average game total (combined score of both teams).
# ~220 points per game as of the 2025-26 NBA season.
# Update this each season as pace/scoring trends shift.
LEAGUE_AVERAGE_GAME_TOTAL = 220.0

# League average possessions per game (pace baseline).
# Used to compute pace adjustment factors.
LEAGUE_AVERAGE_PACE = 98.5

# Recent form blending thresholds.
# When game log data is available the projection uses decay-weighted recency
# averaging instead of a flat season-average blend.
#
# ≥ RECENCY_FULL_THRESHOLD games  → use decay-weighted avg (75%) + season avg (25%)
# ≥ RECENCY_FALLBACK_THRESHOLD games → plain recent avg (60%) + season avg (40%)
# < RECENCY_FALLBACK_THRESHOLD games → season average only (Bayesian shrinkage still applies)
RECENCY_FULL_THRESHOLD   = 10   # games needed for full decay-weighted model
RECENCY_FALLBACK_THRESHOLD = 5  # games needed for simple recent-form blend
RECENCY_WEIGHT   = 0.75   # weight of decay-weighted recent avg when ≥10 games
SEASON_WEIGHT_HI = 0.25   # weight of season avg when ≥10 games
SEASON_AVG_WEIGHT = 0.60  # weight of season avg when 5–9 games (legacy fallback)
RECENT_FORM_WEIGHT = 0.40 # weight of simple recent avg when 5–9 games

# Exponential decay factor for recency weighting.
# Decay of 0.85 means each additional game back is weighted 15% less than the game
# immediately after it.  A value of 1.0 would give equal weight to all games.
RECENCY_DECAY = 0.85

# Streak detection constants.
# If the last STREAK_WINDOW games are all above/below the weighted recent average
# by more than STREAK_THRESHOLD, apply a small multiplier to the projection.
STREAK_WINDOW    = 3     # consecutive games to confirm a streak
STREAK_THRESHOLD = 0.15  # 15% above/below triggers streak detection
STREAK_MULTIPLIER_HOT  = 1.04  # +4% for a confirmed hot streak
STREAK_MULTIPLIER_COLD = 0.96  # −4% for a confirmed cold streak

# Back-to-back fatigue: applied to rest_factor when player played yesterday.
BACK_TO_BACK_FATIGUE_MULTIPLIER = 0.94  # 6% performance reduction

# Spread threshold above which a blowout minutes-risk note is added.
BLOWOUT_SPREAD_THRESHOLD = 10  # points

# Injury-status stat reduction multipliers
QUESTIONABLE_REDUCTION = 0.92    # 8% reduction for Questionable
DOUBTFUL_REDUCTION = 0.75        # 25% reduction for Doubtful
RUST_FACTOR_REDUCTION = 0.94     # 6% reduction for first game back after extended absence
RUST_FACTOR_GAMES_THRESHOLD = 3  # Minimum games missed to trigger rust factor

# ============================================================
# SECTION: Team Blowout Tendency Dictionary (W6)
# Different coaches have very different policies on when to pull
# starters in blowout games. Some teams (e.g., SAS) pull starters
# early at +15; others (e.g., OKC under SGA) keep them in longer.
# Values > 1.0 = team blows out MORE than average (increases risk)
# Values < 1.0 = team manages leads conservatively (star sits earlier)
# ============================================================

TEAM_BLOWOUT_TENDENCY = {
    # Teams that tend to keep starters in / run up scores (higher risk)
    "OKC": 1.15,   # SGA era: aggressive, plays to win big
    "BOS": 1.10,   # Aggressive offensive rotations
    "DEN": 1.10,   # Jokic+ keeps stats up in wins
    "MIL": 1.08,   # Giannis plays heavy minutes
    "PHX": 1.05,   # Up-tempo, doesn't coast
    # Teams that pull starters early / manage load (lower blowout risk for stars)
    "SAS": 0.82,   # Popovich coaching philosophy: rest early
    "MEM": 0.85,   # Development-first, rests stars
    "DET": 0.88,   # Rebuilding team — load management
    "UTA": 0.88,   # Building, rests stars
    "WAS": 0.90,   # Similar rebuilding approach
    # Neutral teams (most of the league)
    "LAL": 1.00, "GSW": 1.00, "LAC": 1.00, "PHI": 1.00,
    "BKN": 1.00, "NYK": 1.00, "MIA": 1.00, "ATL": 1.00,
    "CHI": 1.00, "CLE": 1.00, "IND": 1.00, "TOR": 1.00,
    "NOP": 1.00, "HOU": 1.00, "DAL": 1.00, "MIN": 1.00,
    "POR": 1.00, "SAC": 1.00, "CHA": 1.00, "ORL": 1.00,
}

# ============================================================
# END SECTION: Team Blowout Tendency Dictionary
# ============================================================


# ============================================================
# SECTION: Bayesian Positional Priors (C6)
# When a player has fewer than 25 games, blend their stats
# toward these positional league averages.
# ============================================================

BAYESIAN_SMALL_SAMPLE_THRESHOLD = 25  # games played below which to blend

POSITION_PRIORS = {
    "PG": {"points": 18.5, "rebounds": 4.0, "assists": 6.5, "threes": 2.2,
           "steals": 1.3, "blocks": 0.4, "turnovers": 2.5},
    "SG": {"points": 17.0, "rebounds": 3.8, "assists": 4.0, "threes": 2.0,
           "steals": 1.1, "blocks": 0.4, "turnovers": 1.8},
    "SF": {"points": 16.0, "rebounds": 5.5, "assists": 3.5, "threes": 1.5,
           "steals": 1.0, "blocks": 0.6, "turnovers": 1.5},
    "PF": {"points": 15.5, "rebounds": 7.0, "assists": 3.0, "threes": 1.0,
           "steals": 0.8, "blocks": 0.8, "turnovers": 1.5},
    "C":  {"points": 14.0, "rebounds": 9.0, "assists": 2.5, "threes": 0.5,
           "steals": 0.7, "blocks": 1.4, "turnovers": 1.8},
}
# Default prior for unknown positions
_DEFAULT_POSITION_PRIOR = POSITION_PRIORS["SF"]

# ============================================================
# END SECTION: Bayesian Positional Priors
# ============================================================


# ============================================================
# SECTION: Teammate-Out Usage Adjustment Constants (C4)
# When a high-usage teammate is OUT, remaining players absorb
# that usage. These bumps are applied before the simulation.
# ============================================================

# Bump factors for teammate absence
TEAMMATE_OUT_PRIMARY_BUMP = 0.08    # +8% for primary option (top scorer/assister) out
TEAMMATE_OUT_SECONDARY_BUMP = 0.05  # +5% for secondary option out
TEAMMATE_OUT_MAX_BOOST = 0.15       # Cap total teammate-out boost at +15%

# ============================================================
# END SECTION: Teammate-Out Usage Adjustment Constants
# ============================================================


# ============================================================
# SECTION: Recency Weighting Helpers
# ============================================================

def calculate_recency_weighted_average(game_log_values, decay=RECENCY_DECAY):
    """
    Compute an exponentially decay-weighted average of recent game values.

    More recent games receive higher weight.  The most recent game (index 0)
    has weight 1.0; each subsequent older game is multiplied by *decay*.

    Args:
        game_log_values (list[float]): Stat values ordered most-recent-first.
            Must contain at least one element.
        decay (float): Per-game decay factor in (0, 1].  Default: RECENCY_DECAY.

    Returns:
        float: Weighted average.  Falls back to the arithmetic mean if all
        weights are zero (should only happen with decay=0).
    """
    if not game_log_values:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    for i, val in enumerate(game_log_values):
        w = decay ** i
        weighted_sum += val * w
        total_weight += w

    if total_weight == 0:
        return sum(game_log_values) / len(game_log_values)
    return weighted_sum / total_weight


def detect_streak(game_log_values, reference_avg, threshold=STREAK_THRESHOLD):
    """
    Detect a hot or cold streak in the last STREAK_WINDOW game log values.

    A streak is confirmed when ALL of the last *STREAK_WINDOW* games are
    above (hot) or below (cold) *reference_avg* by more than *threshold*.

    Args:
        game_log_values (list[float]): Stat values ordered most-recent-first.
        reference_avg (float): The baseline to compare against (e.g., decay-
            weighted recent average).
        threshold (float): Fractional deviation required. Default: STREAK_THRESHOLD.

    Returns:
        float: STREAK_MULTIPLIER_HOT for hot, STREAK_MULTIPLIER_COLD for cold,
        or 1.0 if no streak is detected or data is insufficient.
    """
    if not game_log_values or reference_avg <= 0:
        return 1.0

    window = game_log_values[:STREAK_WINDOW]
    if len(window) < STREAK_WINDOW:
        return 1.0

    hot_threshold  = reference_avg * (1.0 + threshold)
    cold_threshold = reference_avg * (1.0 - threshold)

    if all(v > hot_threshold for v in window):
        return STREAK_MULTIPLIER_HOT
    if all(v < cold_threshold for v in window):
        return STREAK_MULTIPLIER_COLD
    return 1.0


# ============================================================
# END SECTION: Recency Weighting Helpers
# ============================================================


def build_player_projection(
    player_data,
    opponent_team_abbreviation,
    is_home_game,
    rest_days,
    game_total,
    defensive_ratings_data,
    teams_data,
    recent_form_games=None,
    vegas_spread=0.0,
    minutes_adjustment_factor=1.0,
    teammate_out_notes=None,
    played_yesterday=False,
    rolling_defensive_data=None,
):
    """
    Build a complete stat projection for one player tonight.

    Adjusts their season averages based on:
    - Opponent defensive rating vs their position
    - Game pace (faster game = more possessions = more stats)
    - Home court advantage
    - Rest days (back-to-back fatigue)
    - Vegas total (high total = projected to be high-scoring game)
    - Vegas spread (used for smart blowout risk calculation)
    - Recent form: last 5 game averages weighted more heavily
    - Minutes adjustment for teammate injuries (W8/C4)
    - Rolling opponent defensive window (C9): blends 10-game rolling
      defensive data with season averages when available

    Args:
        player_data (dict): Player row from players.csv
            Keys: name, team, position, points_avg, etc.
        opponent_team_abbreviation (str): e.g., "GSW", "BOS"
        is_home_game (bool): True if playing at home tonight
        rest_days (int): Days of rest since last game (0=back-to-back)
        game_total (float): Vegas over/under total for tonight's game
        defensive_ratings_data (list of dict): From defensive_ratings.csv
        teams_data (list of dict): From teams.csv
        recent_form_games (list of dict, optional): Last N game log rows.
            Each row should have numeric keys matching stat names
            (e.g., 'pts', 'reb', 'ast'). When provided, projections
            blend season averages 60% + recent-form averages 40%.
        vegas_spread (float, optional): Vegas point spread for tonight.
            Positive = player's team is favored by this many points.
            Used by the smart blowout risk formula (W6).
        minutes_adjustment_factor (float, optional): Multiplier for
            projected minutes due to teammate injury/absence (W8).
            > 1.0 = more minutes (teammate out), 1.0 = normal.
            Passed in from injury report analysis.
        teammate_out_notes (list of str, optional): Human-readable notes
            about which teammates are out and how it affects this player (W8).
            Included in the returned projection for display purposes.
        played_yesterday (bool, optional): True if this is a back-to-back
            game (player played yesterday). Applies a 0.94 fatigue multiplier
            to the rest adjustment factor. Default False.
        rolling_defensive_data (dict, optional): Rolling 10-game defensive
            window data keyed by team abbreviation. (C9)
            Format: {team_abbrev: {position: rolling_factor}}
            e.g., {"BOS": {"PG": 0.88, "SG": 0.91, ...}}
            When provided, blends rolling factor with season average factor:
              defense_factor = 0.5 * season_factor + 0.5 * rolling_factor
            When None or opponent not found, falls back to season average
            from defensive_ratings_data (current default behavior).

    Returns:
        dict: Projected stats for tonight with adjustment factors:
            - 'projected_points': float
            - 'projected_rebounds': float
            - 'projected_assists': float
            - 'projected_threes': float
            - 'projected_steals': float
            - 'projected_blocks': float
            - 'projected_turnovers': float
            - 'projected_minutes': float (C1: estimated minutes for tonight)
            - 'pace_factor': float (multiplier, ~0.9-1.1)
            - 'defense_factor': float (multiplier, ~0.88-1.12)
            - 'home_away_factor': float (small +/-)
            - 'rest_factor': float (multiplier, ~0.9-1.0)
            - 'blowout_risk': float (0.0-1.0)
            - 'overall_adjustment': float (combined multiplier)
            - 'recent_form_ratio': float or None (last5_avg / season_avg)
            - 'minutes_adjustment_factor': float (W8: teammate injury impact)
            - 'teammate_out_notes': list of str (W8/C4: teammate impact notes)
            - 'notes': list of str (game-context warnings, e.g. back-to-back)
            - 'bayesian_shrinkage_applied': bool (C6: True if sample < 25 games)

    Example:
        LeBron at home vs weak defense + fast pace →
        projected_points might be 27.1 instead of his 24.8 average
    """
    # ============================================================
    # SECTION: Extract Player's Season Averages
    # ============================================================

    # Get each stat average from the player data dictionary
    season_points_average = float(player_data.get("points_avg", 0))
    season_rebounds_average = float(player_data.get("rebounds_avg", 0))
    season_assists_average = float(player_data.get("assists_avg", 0))
    season_threes_average = float(player_data.get("threes_avg", 0))
    season_steals_average = float(player_data.get("steals_avg", 0))
    season_blocks_average = float(player_data.get("blocks_avg", 0))
    season_turnovers_average = float(player_data.get("turnovers_avg", 0))
    player_position = player_data.get("position", "SF")  # Default to SF if missing
    games_played = int(player_data.get("games_played", player_data.get("gp", 82)) or 82)
    season_minutes_average = float(player_data.get("minutes_avg", player_data.get("min", 30.0)) or 30.0)

    # ============================================================
    # END SECTION: Extract Player's Season Averages
    # ============================================================

    # ============================================================
    # SECTION: Bayesian Shrinkage for Small Samples (C6)
    # When games_played < 25, blend player stats toward positional
    # league averages to avoid over-fitting to a small sample.
    # ============================================================

    bayesian_shrinkage_applied = False
    if games_played < BAYESIAN_SMALL_SAMPLE_THRESHOLD:
        # Weight formula: w = min(games_played / 25, 1.0)
        # At 0 games: 0% player, 100% prior
        # At 25+ games: 100% player, 0% prior
        w = min(games_played / BAYESIAN_SMALL_SAMPLE_THRESHOLD, 1.0)
        prior = POSITION_PRIORS.get(player_position, _DEFAULT_POSITION_PRIOR)

        season_points_average   = w * season_points_average   + (1 - w) * prior["points"]
        season_rebounds_average = w * season_rebounds_average + (1 - w) * prior["rebounds"]
        season_assists_average  = w * season_assists_average  + (1 - w) * prior["assists"]
        season_threes_average   = w * season_threes_average   + (1 - w) * prior["threes"]
        season_steals_average   = w * season_steals_average   + (1 - w) * prior["steals"]
        season_blocks_average   = w * season_blocks_average   + (1 - w) * prior["blocks"]
        season_turnovers_average= w * season_turnovers_average+ (1 - w) * prior["turnovers"]
        bayesian_shrinkage_applied = True

    # ============================================================
    # END SECTION: Bayesian Shrinkage for Small Samples
    # ============================================================

    # ============================================================
    # SECTION: Recent Form Blending
    # When game log data is available, use decay-weighted recency
    # averaging for a more responsive projection.
    #
    # ≥ RECENCY_FULL_THRESHOLD (10) games:
    #   decay-weighted recent avg (75%) + season avg (25%)
    #   + streak multiplier if last 3 games all above/below baseline by >15%
    # ≥ RECENCY_FALLBACK_THRESHOLD (5) games:
    #   plain recent avg (40%) + season avg (60%)  — legacy fallback
    # < RECENCY_FALLBACK_THRESHOLD games:
    #   season average only (Bayesian shrinkage still applies above)
    # ============================================================

    recent_form_ratio = None  # Will be set if we have game log data

    if recent_form_games and len(recent_form_games) >= RECENCY_FALLBACK_THRESHOLD:
        # Map game-log keys to stat names
        form_key_map = {
            "points": "pts",
            "rebounds": "reb",
            "assists": "ast",
            "threes": "fg3m",
            "steals": "stl",
            "blocks": "blk",
            "turnovers": "tov",
        }

        def _extract_vals(games, log_key):
            """Extract numeric values for a stat from game logs (most-recent first)."""
            vals = []
            for g in games:
                v = g.get(log_key, g.get(log_key.lower(), None))
                if v is not None:
                    try:
                        vals.append(float(v))
                    except (TypeError, ValueError):
                        pass
            return vals

        def _recent_avg(games, log_key, fallback):
            """Simple arithmetic average for fallback use."""
            vals = _extract_vals(games, log_key)
            return sum(vals) / len(vals) if vals else fallback

        n_games = len(recent_form_games)

        if n_games >= RECENCY_FULL_THRESHOLD:
            # Full decay-weighted model
            def _blend_stat(season_val, log_key):
                vals = _extract_vals(recent_form_games, log_key)
                if not vals:
                    return season_val
                decay_avg = calculate_recency_weighted_average(vals)
                streak_mult = detect_streak(vals, decay_avg)
                blended = RECENCY_WEIGHT * decay_avg + SEASON_WEIGHT_HI * season_val
                return blended * streak_mult

            # Use decay-weighted points to compute recent-form ratio
            pts_vals = _extract_vals(recent_form_games, form_key_map["points"])
            if pts_vals and season_points_average > 0:
                decay_pts = calculate_recency_weighted_average(pts_vals)
                recent_form_ratio = round(decay_pts / season_points_average, 3)

            season_points_average   = _blend_stat(season_points_average,   form_key_map["points"])
            season_rebounds_average = _blend_stat(season_rebounds_average, form_key_map["rebounds"])
            season_assists_average  = _blend_stat(season_assists_average,  form_key_map["assists"])
            season_threes_average   = _blend_stat(season_threes_average,   form_key_map["threes"])
            season_steals_average   = _blend_stat(season_steals_average,   form_key_map["steals"])
            season_blocks_average   = _blend_stat(season_blocks_average,   form_key_map["blocks"])
            season_turnovers_average= _blend_stat(season_turnovers_average,form_key_map["turnovers"])

        else:
            # Fallback: simple recent-average blend (5–9 games)
            pts_key = form_key_map["points"]
            recent_pts = _recent_avg(recent_form_games, pts_key, season_points_average)

            if season_points_average > 0:
                recent_form_ratio = round(recent_pts / season_points_average, 3)

            _blend = lambda season, recent: season * SEASON_AVG_WEIGHT + recent * RECENT_FORM_WEIGHT
            season_points_average   = _blend(season_points_average,   recent_pts)
            season_rebounds_average = _blend(season_rebounds_average,
                                             _recent_avg(recent_form_games, form_key_map["rebounds"], season_rebounds_average))
            season_assists_average  = _blend(season_assists_average,
                                             _recent_avg(recent_form_games, form_key_map["assists"],  season_assists_average))
            season_threes_average   = _blend(season_threes_average,
                                             _recent_avg(recent_form_games, form_key_map["threes"],   season_threes_average))
            season_steals_average   = _blend(season_steals_average,
                                             _recent_avg(recent_form_games, form_key_map["steals"],   season_steals_average))
            season_blocks_average   = _blend(season_blocks_average,
                                             _recent_avg(recent_form_games, form_key_map["blocks"],   season_blocks_average))
            season_turnovers_average= _blend(season_turnovers_average,
                                             _recent_avg(recent_form_games, form_key_map["turnovers"],season_turnovers_average))

    # ============================================================
    # END SECTION: Recent Form Blending
    # ============================================================

    # ============================================================
    # SECTION: Calculate Adjustment Factors
    # ============================================================

    # --- Factor 1: Opponent Defensive Rating (C9: Rolling Window blend) ---
    # Season-long defensive factor from defensive_ratings.csv
    season_defense_factor = _get_defense_adjustment_factor(
        opponent_team_abbreviation,
        player_position,
        defensive_ratings_data,
    )

    # C9: If rolling_defensive_data is provided, blend 50/50 with season avg.
    # This captures teams on hot/cold defensive streaks over their last 10 games.
    # If rolling data is unavailable, fall back to season average (unchanged behavior).
    rolling_defense_factor = _get_rolling_defense_factor(
        opponent_team_abbreviation,
        player_position,
        rolling_defensive_data,
    )
    if rolling_defense_factor is not None:
        # 50% season-long, 50% rolling (last-10 game) defensive factor
        defense_factor = 0.5 * season_defense_factor + 0.5 * rolling_defense_factor
    else:
        defense_factor = season_defense_factor  # Fall back to season average

    # --- Factor 2: Game Pace ---
    # Faster game = more possessions = more stat opportunities
    pace_factor = _get_pace_adjustment_factor(
        opponent_team_abbreviation,
        player_data.get("team", ""),
        teams_data,
    )

    # --- Factor 3: Home Court Advantage ---
    # Home teams historically shoot better and have more energy
    if is_home_game:
        home_away_factor = 0.025   # +2.5% boost for playing at home
    else:
        home_away_factor = -0.015  # -1.5% penalty for away games

    # --- Factor 4: Rest Adjustment ---
    # Back-to-back games cause fatigue; well-rested players perform better
    rest_factor = _get_rest_adjustment_factor(rest_days)

    # Back-to-back override: if the player literally played yesterday, apply
    # an additional 6% fatigue reduction on top of the rest-day factor.
    notes = []
    if played_yesterday:
        rest_factor *= BACK_TO_BACK_FATIGUE_MULTIPLIER  # 6% fatigue penalty for back-to-back
        notes.append("⚠️ Back-to-back game — fatigue factor applied")

    # --- Factor 5: Game Total / Scoring Environment ---
    # High-total games (230+ pts projected) are fast-paced, high scoring
    # Neutral total is LEAGUE_AVERAGE_GAME_TOTAL; adjust proportionally
    if game_total > 0:
        # BEGINNER NOTE: This creates a small boost/penalty based on
        # how far the total is from average. Capped at ±5%
        game_total_factor = 1.0 + ((game_total - LEAGUE_AVERAGE_GAME_TOTAL) / LEAGUE_AVERAGE_GAME_TOTAL) * 0.5
        game_total_factor = max(0.95, min(1.05, game_total_factor))  # Cap at ±5%
    else:
        game_total_factor = 1.0  # Neutral if no total provided

    # --- Factor 6: Blowout Risk (W6: Smart Blowout Risk) ---
    # Now uses BOTH spread AND game total, plus team tendency,
    # instead of just the defensive rating.
    player_team = player_data.get("team", "")
    blowout_risk = _estimate_blowout_risk(
        player_team,
        opponent_team_abbreviation,
        teams_data,
        vegas_spread=vegas_spread,
        game_total=game_total,
    )

    # Warn when a large spread creates meaningful reduced-minutes risk.
    if abs(vegas_spread) > BLOWOUT_SPREAD_THRESHOLD:
        notes.append(
            f"⚠️ Spread > 10 ({vegas_spread:+.1f}) — star player may face reduced minutes in blowout"
        )

    # ============================================================
    # END SECTION: Calculate Adjustment Factors
    # ============================================================

    # ============================================================
    # SECTION: Per-Minute Rate Decomposition (C1)
    # Project tonight's minutes, then derive stats as
    #   projected_stat = per_minute_rate × projected_minutes × matchup_factor × pace_factor
    # This is more physically meaningful than applying a flat multiplier
    # to season averages, and enables the C8 minutes-first simulation.
    # ============================================================

    # Project tonight's minutes
    # Base: season average minutes, adjusted by rest/back-to-back, blowout risk,
    # and spread (potential blowout → reduced minutes for starters).
    spread_minutes_factor = 1.0
    if abs(vegas_spread) > 12:
        # High spread → genuine blowout risk → starters may sit garbage time
        spread_minutes_factor = 0.94
    elif abs(vegas_spread) > 8:
        spread_minutes_factor = 0.97

    projected_minutes = round(
        season_minutes_average
        * rest_factor                # Back-to-back reduces minutes too
        * minutes_adjustment_factor  # Teammate injury (W8): more/fewer mins
        * spread_minutes_factor,     # Blowout risk (C1)
        1
    )
    # Clamp to realistic range
    projected_minutes = max(5.0, min(44.0, projected_minutes))

    # ============================================================
    # SECTION: Apply Adjustments to Get Tonight's Projections
    # ============================================================

    # Combine all factors into one multiplier for offensive stats
    # W8/C1: minutes_adjustment_factor boosts projections when a key
    # teammate is OUT (more usage) or applies a slight discount when
    # the player themselves is on a restriction.
    offensive_stat_multiplier = (
        defense_factor
        * pace_factor
        * game_total_factor
        * (1.0 + home_away_factor)
        * rest_factor
        * minutes_adjustment_factor  # W8/C4: teammate injury / minutes restriction
    )

    # Project each stat by applying the combined multiplier
    projected_points = season_points_average * offensive_stat_multiplier
    projected_rebounds = season_rebounds_average * (
        pace_factor * defense_factor * (1.0 + home_away_factor) * rest_factor
        * minutes_adjustment_factor
    )
    projected_assists = season_assists_average * offensive_stat_multiplier
    projected_threes = season_threes_average * offensive_stat_multiplier
    projected_steals = season_steals_average * rest_factor * (1.0 + home_away_factor * 0.5)
    projected_blocks = season_blocks_average * rest_factor * (1.0 + home_away_factor * 0.5)
    projected_turnovers = season_turnovers_average * pace_factor  # Turnovers up with pace

    # Round to 1 decimal place for readability
    projections = {
        "projected_points": round(projected_points, 1),
        "projected_rebounds": round(projected_rebounds, 1),
        "projected_assists": round(projected_assists, 1),
        "projected_threes": round(projected_threes, 1),
        "projected_steals": round(projected_steals, 1),
        "projected_blocks": round(projected_blocks, 1),
        "projected_turnovers": round(projected_turnovers, 1),
        # C1: Projected minutes for tonight (used by C8 minutes-first sim)
        "projected_minutes": projected_minutes,
        # Store all factors for transparency (shown in app)
        "pace_factor": round(pace_factor, 4),
        "defense_factor": round(defense_factor, 4),
        "home_away_factor": round(home_away_factor, 4),
        "rest_factor": round(rest_factor, 4),
        "game_total_factor": round(game_total_factor, 4),
        "blowout_risk": round(blowout_risk, 4),
        "overall_adjustment": round(offensive_stat_multiplier, 4),
        "recent_form_ratio": recent_form_ratio,
        # W8/C4: Minutes adjustment factors for injury/restriction transparency
        "minutes_adjustment_factor": round(minutes_adjustment_factor, 4),
        "teammate_out_notes": teammate_out_notes or [],
        "notes": notes,
        # C6: Bayesian shrinkage metadata
        "bayesian_shrinkage_applied": bayesian_shrinkage_applied,
        "games_played": games_played,
    }

    return projections

    # ============================================================
    # END SECTION: Apply Adjustments to Get Tonight's Projections
    # ============================================================


# ============================================================
# SECTION: Individual Adjustment Factor Functions
# ============================================================

def _get_defense_adjustment_factor(
    opponent_team_abbreviation,
    player_position,
    defensive_ratings_data,
):
    """
    Look up how well the opponent defends this player's position.

    A factor of 1.1 means the opponent allows 10% more points
    to this position (weak defense = good for the player).
    A factor of 0.9 means the opponent is 10% tougher than average.

    Args:
        opponent_team_abbreviation (str): 3-letter team code
        player_position (str): PG, SG, SF, PF, or C
        defensive_ratings_data (list of dict): Defensive rating rows

    Returns:
        float: Adjustment multiplier (typically 0.88 to 1.12)
    """
    # Find the opponent's row in defensive ratings data
    for team_row in defensive_ratings_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            # Build the column name: "vs_PG_pts", "vs_C_pts", etc.
            column_name = f"vs_{player_position}_pts"
            factor_value = team_row.get(column_name, "1.0")
            return float(factor_value)

    # If opponent not found, return 1.0 (neutral)
    return 1.0


def _get_rolling_defense_factor(
    opponent_team_abbreviation,
    player_position,
    rolling_defensive_data,
):
    """
    Look up the rolling 10-game defensive factor for an opponent. (C9)

    This captures teams on hot/cold defensive streaks that the season-long
    rating doesn't reflect. For example, if a team has been defending PGs
    much better over the last 10 games, this factor will be < 1.0.

    Falls back gracefully (returns None) when:
    - rolling_defensive_data is None (caller will use season average)
    - The opponent is not found in the rolling data
    - The position is not in the rolling data

    Args:
        opponent_team_abbreviation (str): 3-letter team code
        player_position (str): PG, SG, SF, PF, or C
        rolling_defensive_data (dict or None): Rolling data dict.
            Format: {team_abbrev: {position_key: factor}}
            Supported position key formats:
              - Simple: {"BOS": {"PG": 0.88, "SG": 0.92}}
              - CSV-style: {"BOS": {"vs_PG_pts": 0.88, "vs_SG_pts": 0.92}}
            Both formats are handled transparently.
            When None, always returns None.

    Returns:
        float or None: Rolling defensive factor, or None if unavailable.
    """
    if not rolling_defensive_data:
        return None

    team_rolling = rolling_defensive_data.get(opponent_team_abbreviation)
    if not team_rolling:
        return None

    # Support both direct position key and full column key
    factor = team_rolling.get(player_position)
    if factor is None:
        factor = team_rolling.get(f"vs_{player_position}_pts")
    if factor is None:
        return None

    try:
        return float(factor)
    except (TypeError, ValueError):
        return None


def _get_pace_adjustment_factor(
    opponent_team_abbreviation,
    player_team_abbreviation,
    teams_data,
):
    """
    Calculate the pace adjustment for tonight's game.

    Game pace = average of both teams' pace ratings.
    League average pace ≈ 98.5 possessions per game.
    Faster pace = more stat opportunities.

    Args:
        opponent_team_abbreviation (str): Opponent 3-letter code
        player_team_abbreviation (str): Player's team 3-letter code
        teams_data (list of dict): Team data rows from teams.csv

    Returns:
        float: Pace multiplier (typically 0.93 to 1.07)
    """
    league_average_pace = LEAGUE_AVERAGE_PACE  # From module-level constant

    player_team_pace = league_average_pace   # Default if not found
    opponent_team_pace = league_average_pace  # Default if not found

    # Find each team's pace rating
    for team_row in teams_data:
        abbreviation = team_row.get("abbreviation", "")
        if abbreviation == player_team_abbreviation:
            player_team_pace = float(team_row.get("pace", league_average_pace))
        if abbreviation == opponent_team_abbreviation:
            opponent_team_pace = float(team_row.get("pace", league_average_pace))

    # Tonight's expected pace = average of both teams
    expected_game_pace = (player_team_pace + opponent_team_pace) / 2.0

    # Convert to a multiplier relative to league average
    pace_factor = expected_game_pace / league_average_pace

    return pace_factor


def _get_rest_adjustment_factor(rest_days):
    """
    Calculate performance adjustment based on rest.

    Back-to-back games (0 rest days) cause fatigue and reduce
    performance. More rest generally helps, up to a point.

    Args:
        rest_days (int): Days of rest (0 = back-to-back, 3+ = well rested)

    Returns:
        float: Multiplier (0.92 for back-to-back, up to 1.02 well rested)
    """
    # BEGINNER NOTE: This dictionary maps rest days to performance multipliers
    rest_to_factor_map = {
        0: 0.92,   # Back-to-back: significant fatigue
        1: 0.97,   # One day rest: minor fatigue
        2: 1.00,   # Two days rest: normal performance
        3: 1.01,   # Three days: slightly better than average
        4: 1.02,   # Four or more: well rested
    }

    # Get factor for the given rest days (cap at 4 since 5 = 4 essentially)
    capped_rest_days = min(rest_days, 4)
    return rest_to_factor_map.get(capped_rest_days, 1.00)


def _estimate_blowout_risk(
    player_team_abbreviation,
    opponent_team_abbreviation,
    teams_data,
    vegas_spread=0.0,
    game_total=0.0,
):
    """
    Estimate the probability tonight's game becomes a blowout. (W6)

    Now uses a three-factor formula that combines:
    1. Vegas spread — the primary blowout predictor
    2. Game total — high spread + low total = slow blowout (maximum risk)
    3. Team blowout tendency — some coaches pull stars early, others don't

    Formula:
        blowout_risk = base_risk × spread_factor × total_factor × team_tendency

    Args:
        player_team_abbreviation (str): Player's team 3-letter code
        opponent_team_abbreviation (str): Opponent 3-letter code
        teams_data (list of dict): Team data rows
        vegas_spread (float): Today's point spread (positive = player's team favored)
        game_total (float): Vegas over/under total for tonight's game

    Returns:
        float: Blowout risk probability (0.05 to 0.45)
    """
    # ---- Base blowout risk from defensive ratings (legacy fallback) ----
    # Find the opponent's defensive rating for spread-independent baseline
    opponent_drtg = 115.0  # League average if not found
    for team_row in teams_data:
        if team_row.get("abbreviation", "") == opponent_team_abbreviation:
            opponent_drtg = float(team_row.get("drtg", 115.0))
            break

    base_blowout_risk = 0.15  # 15% base in any NBA game

    # ---- Factor 1: Spread Factor ----
    # Larger spread → higher blowout probability
    # Use abs() to treat both favorite and underdog scenarios equally
    # (a 14-point favorite or 14-point underdog both imply a lopsided game)
    abs_spread = abs(vegas_spread) if vegas_spread != 0.0 else abs(
        (opponent_drtg - 115.0) * 0.8  # Estimate from drtg if no spread
    )
    if abs_spread <= 3.0:
        # Close game — very low blowout risk
        spread_factor = 0.6
    elif abs_spread <= 7.0:
        # Moderate favorite/underdog
        spread_factor = 0.85
    elif abs_spread <= 12.0:
        # Clear favorite — moderate blowout risk
        spread_factor = 1.2
    elif abs_spread <= 18.0:
        # Heavy favorite — high blowout risk
        spread_factor = 1.6
    else:
        # Massive favorite — very high blowout risk
        spread_factor = 2.0

    # ---- Factor 2: Game Total Factor (W6: high spread + low total = max blowout risk) ----
    # High spread + low total = one team wins a slow, controlled game = worst case
    # High spread + high total = fast game but still one-sided = moderate risk
    if game_total <= 0:
        total_factor = 1.0  # No data — neutral
    elif game_total < 210:
        total_factor = 1.25  # Very low total = defensive slog = blowout stays close
    elif game_total < 218:
        total_factor = 1.10  # Below-average pace = slightly higher blowout risk
    elif game_total <= 226:
        total_factor = 1.00  # Average game total — neutral
    elif game_total <= 232:
        total_factor = 0.88  # High-scoring game — blowouts less frequent
    else:
        total_factor = 0.78  # Very high total — run-and-gun, close games common

    # ---- Factor 3: Team Blowout Tendency ----
    # Some coaches pull starters early (low tendency = lower risk for the PLAYER
    # because coach pulls them sooner = less stats, but that's already captured
    # in the minutes model). Here we track the OPPONENT's tendency to collapse.
    # Use the PLAYER's team tendency (affects whether the player gets full mins).
    team_tendency = TEAM_BLOWOUT_TENDENCY.get(player_team_abbreviation, 1.0)

    # ---- Combine ----
    blowout_risk = base_blowout_risk * spread_factor * total_factor * team_tendency

    # Cap between 5% and 45%
    return max(0.05, min(0.45, blowout_risk))


def get_stat_standard_deviation(player_data, stat_type):
    """
    Get the pre-stored standard deviation for a stat type.

    The CSV includes std values for main stats. For others,
    we estimate based on the average (coefficient of variation).
    CV estimates are now DYNAMIC based on the player's tier (W10):
    - Stars (high avg) have LOWER CV — they always get their shots
    - Role players have HIGHER CV — usage is more situational
    - Threes always get at least 0.55 CV (most streaky stat)

    Args:
        player_data (dict): Player row from CSV
        stat_type (str): 'points', 'rebounds', 'assists', etc.

    Returns:
        float: Standard deviation for this stat
    """
    # Try to get the stored std from the CSV first
    std_column = f"{stat_type}_std"
    stored_std = player_data.get(std_column, None)

    if stored_std is not None and stored_std != "":
        return float(stored_std)

    # BEGINNER NOTE: If we don't have a stored std, estimate it
    # using the "coefficient of variation" — most basketball stats
    # have about 30-50% variability relative to their average
    average_column = f"{stat_type}_avg"
    stored_avg = float(player_data.get(average_column, 0))

    # W10: Dynamic CV based on player tier and stat type
    # Stars (25+ PPG) are more consistent; role players are more volatile
    cv = _get_dynamic_cv(stat_type, stored_avg)

    estimated_std = stored_avg * cv

    # Minimum std of 0.5 to avoid divide-by-zero issues
    return max(0.5, estimated_std)


def _get_dynamic_cv(stat_type, stat_avg):
    """
    Get a dynamic coefficient of variation based on player tier and stat type. (W10)

    High-usage stars have LOWER CV% because they always get their shots
    and their production floor is higher. Low-usage role players have
    HIGHER CV% because their production is more situational.
    Three-point shooting is inherently streaky — always use at least 0.55 CV.

    Args:
        stat_type (str): 'points', 'rebounds', 'assists', 'threes', etc.
        stat_avg (float): The player's average for this stat

    Returns:
        float: Coefficient of variation (0.0-1.0)

    Example:
        'points', avg=28.0 → 0.25 (star, very consistent)
        'points', avg=5.0  → 0.50 (deep bench, very unpredictable)
        'threes', avg=2.5  → 0.60 (minimum 0.55 always applied)
    """
    if stat_type == "points":
        # Stars get guaranteed shots → lower variability
        if stat_avg >= 25.0:
            cv = 0.25   # Elite scorer — very consistent
        elif stat_avg >= 15.0:
            cv = 0.30   # Regular starter
        elif stat_avg >= 8.0:
            cv = 0.40   # Role player — situational production
        else:
            cv = 0.50   # Deep bench — very unpredictable

    elif stat_type == "rebounds":
        if stat_avg >= 10.0:
            cv = 0.28   # Elite rebounder — positional, very consistent
        elif stat_avg >= 6.0:
            cv = 0.35
        elif stat_avg >= 3.0:
            cv = 0.42
        else:
            cv = 0.50

    elif stat_type == "assists":
        if stat_avg >= 8.0:
            cv = 0.32   # Primary playmaker — fairly consistent
        elif stat_avg >= 4.0:
            cv = 0.40
        else:
            cv = 0.50

    elif stat_type == "threes":
        # Three-point shooting is inherently streaky — always minimum 0.55
        # A 3-point specialist has slightly lower CV than a non-shooter
        if stat_avg >= 3.0:
            cv = 0.58   # Volume shooter — streaky but consistent volume
        elif stat_avg >= 1.5:
            cv = 0.65
        else:
            cv = 0.75   # Non-shooter attempting threes — very unpredictable
        # Minimum 0.55 for all three-point props
        cv = max(cv, 0.55)

    elif stat_type == "steals":
        cv = 0.60  # Steals are always high variance

    elif stat_type == "blocks":
        cv = 0.65  # Blocks are always high variance

    elif stat_type == "turnovers":
        if stat_avg >= 3.0:
            cv = 0.42   # High-usage players have somewhat predictable turnovers
        else:
            cv = 0.50

    else:
        cv = 0.40  # Default for unknown stat types

    return cv

# ============================================================
# END SECTION: Individual Adjustment Factor Functions
# ============================================================


# ============================================================
# SECTION: Teammate-Out Usage Adjustment (C4)
# When a high-usage teammate is OUT, boost the current player's
# projection by a configurable usage bump factor.
# ============================================================

def calculate_teammate_out_boost(
    player_data,
    injury_status_map,
    teammates_data=None,
):
    """
    Calculate a usage-boost multiplier for when key teammates are OUT. (C4)

    Checks the injury status map for teammates on the same team.
    If a high-usage teammate is OUT (top 3 scorer/assist leader),
    boosts the current player's projection.

    Args:
        player_data (dict): Current player's data row.
        injury_status_map (dict): {player_name_lower: {status, ...}}
            Typically from RosterEngine.get_injury_report() or session state.
        teammates_data (list of dict, optional): Rows of all players on the
            same team from players CSV. When None, no teammate analysis is done.

    Returns:
        tuple: (boost_multiplier: float, notes: list of str)
            boost_multiplier: 1.0 (no boost) to 1.15 (max +15%)
            notes: Human-readable explanations of any boosts applied
    """
    if not teammates_data or not injury_status_map:
        return 1.0, []

    player_name = player_data.get("name", "").lower()
    player_team = player_data.get("team", "").upper()

    # Find teammates on the same team
    team_players = [
        p for p in (teammates_data or [])
        if p.get("team", "").upper() == player_team
        and p.get("name", "").lower() != player_name
    ]

    if not team_players:
        return 1.0, []

    # Sort teammates by points average (primary usage metric)
    team_players_sorted = sorted(
        team_players,
        key=lambda p: float(p.get("points_avg", 0) or 0),
        reverse=True,
    )

    # Check top 3 scorers / assist leaders for OUT status
    top_options = team_players_sorted[:3]
    total_boost = 0.0
    notes = []

    for rank, teammate in enumerate(top_options):
        t_name = teammate.get("name", "")
        t_name_lower = t_name.lower()
        t_status_entry = injury_status_map.get(t_name_lower, {})
        t_status = t_status_entry.get("status", "Active")

        if t_status in ("Out", "Injured Reserve", "IR", "Inactive"):
            if rank == 0:
                bump = TEAMMATE_OUT_PRIMARY_BUMP    # +8%
                tier_label = "primary option"
            else:
                bump = TEAMMATE_OUT_SECONDARY_BUMP  # +5%
                tier_label = "secondary option"

            total_boost = min(total_boost + bump, TEAMMATE_OUT_MAX_BOOST)
            notes.append(
                f"📈 {t_name} ({tier_label}, {t_status}) OUT → "
                f"+{bump*100:.0f}% usage boost"
            )

    boost_multiplier = 1.0 + total_boost
    return round(boost_multiplier, 4), notes

# ============================================================
# END SECTION: Teammate-Out Usage Adjustment
# ============================================================


# ============================================================
# SECTION: Injury / Status Adjustment
# ============================================================

def apply_injury_status_adjustment(projection_dict, player_status, games_missed=0):
    """
    Apply injury/status impact factors to a player projection.

    Reduces projected stats based on the player's availability status
    and, if they missed several games, applies a rust-factor penalty
    for the first game back.

    Args:
        projection_dict (dict): Return value of build_player_projection().
            Modified in-place (via a shallow copy) and returned.
        player_status (str): Player availability label, e.g.:
            'Active', 'Questionable', 'Doubtful', 'Out', 'Injured Reserve'
        games_missed (int, optional): Consecutive games missed before
            tonight. If > 3, a 6% rust-factor reduction is applied.
            Default 0 (no games missed).

    Returns:
        dict or None:
            - None if player_status is 'Out' or 'Injured Reserve'
            - Adjusted projection_dict otherwise (shallow copy, not mutated)

    Examples:
        apply_injury_status_adjustment(proj, "Questionable")   → -8%
        apply_injury_status_adjustment(proj, "Doubtful")        → -25%
        apply_injury_status_adjustment(proj, "Out")             → None
        apply_injury_status_adjustment(proj, "Active", 4)       → -6% rust
        apply_injury_status_adjustment(proj, "Questionable", 5) → -8% + -6%
    """
    if player_status in ("Out", "Injured Reserve"):
        return None

    if projection_dict is None:
        return None

    # Work on a shallow copy so the original is not mutated
    adjusted = dict(projection_dict)
    notes = list(adjusted.get("notes", []))

    # Stat keys that represent player output (not factors/metadata)
    _STAT_KEYS = [
        "projected_points",
        "projected_rebounds",
        "projected_assists",
        "projected_threes",
        "projected_steals",
        "projected_blocks",
        "projected_turnovers",
    ]

    # Determine status-based reduction factor
    reduction = 1.0
    if player_status == "Questionable":
        reduction *= QUESTIONABLE_REDUCTION  # 8% reduction
        notes.append("⚠️ Questionable status — projected stats reduced 8%")
    elif player_status == "Doubtful":
        reduction *= DOUBTFUL_REDUCTION  # 25% reduction
        notes.append("⚠️ Doubtful status — projected stats reduced 25%")

    # Rust factor: reduction for first game back after missing 3+ games
    if games_missed > RUST_FACTOR_GAMES_THRESHOLD:
        reduction *= RUST_FACTOR_REDUCTION
        notes.append(
            f"⚠️ Rust factor — {games_missed} games missed, first game back (−6%)"
        )

    # Apply reduction to all output stats
    for key in _STAT_KEYS:
        if key in adjusted:
            adjusted[key] = round(adjusted[key] * reduction, 1)

    adjusted["notes"] = notes
    return adjusted

# ============================================================
# END SECTION: Injury / Status Adjustment
# ============================================================
