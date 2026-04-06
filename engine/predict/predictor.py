"""engine/predict/predictor.py – Load saved models and generate predictions."""
import os
import statistics as _statistics
from utils.logger import get_logger

_logger = get_logger(__name__)

_SAVED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "saved")

# Mapping from prediction stat_type to the game-log column name used for
# standard-deviation / confidence-interval calculations.
_STAT_COL_MAP = {
    "pts": "pts",
    "reb": "reb",
    "ast": "ast",
    "stl": "stl",
    "blk": "blk",
    "tov": "tov",
    "fg3m": "fg3m",
    "threes": "fg3m",
    "ftm": "ftm",
    "oreb": "oreb",
    "plus_minus": "plus_minus",
}

# Mapping from stat_type to the season-average key returned by
# ``etl_data_service._compute_averages`` (used in the statistical fallback).
_STAT_AVG_MAP = {
    "pts": "ppg",
    "reb": "rpg",
    "ast": "apg",
    "stl": "spg",
    "blk": "bpg",
    "tov": "topg",
    "fg3m": "fg3_avg",
    "threes": "fg3_avg",
    "ftm": "ftm_avg",
    "oreb": "oreb_avg",
    "plus_minus": "plus_minus_avg",
}

# Standard-deviation key from etl_data_service averages dict.
_STAT_STD_MAP = {
    "pts": "points_std",
    "reb": "rebounds_std",
    "ast": "assists_std",
    "fg3m": "threes_std",
    "threes": "threes_std",
    "stl": "steals_std",
    "blk": "blocks_std",
    "tov": "turnovers_std",
    "ftm": "ftm_std",
    "oreb": "oreb_std",
    "plus_minus": "plus_minus_std",
}

# Combo stat definitions: maps combo stat key to its component game-log
# column names and season-average keys.
_COMBO_STAT_COLS: dict[str, list[str]] = {
    "pts+reb": ["pts", "reb"],
    "pts+ast": ["pts", "ast"],
    "pts+reb+ast": ["pts", "reb", "ast"],
    "blk+stl": ["blk", "stl"],
}

_COMBO_STAT_AVGS: dict[str, list[str]] = {
    "pts+reb": ["ppg", "rpg"],
    "pts+ast": ["ppg", "apg"],
    "pts+reb+ast": ["ppg", "rpg", "apg"],
    "blk+stl": ["bpg", "spg"],
}

# Maps feature names added to player_data from home/away splits to the
# uppercase keys returned by ``db_service.get_player_splits()._summarise``.
_SPLIT_KEY_MAP = {
    "ha_pts": "PTS", "ha_reb": "REB", "ha_ast": "AST",
    "ha_stl": "STL", "ha_blk": "BLK", "ha_tov": "TOV",
    "ha_fg3m": "FG3M", "ha_ftm": "FTM",
    "ha_oreb": "OREB", "ha_plus_minus": "PLUS_MINUS",
}

# Default prediction values when no data is available.
_STAT_DEFAULTS = {
    "pts": 15.0, "reb": 5.0, "ast": 4.0, "stl": 1.0,
    "blk": 0.5, "tov": 2.0, "fg3m": 1.5, "ftm": 2.0,
    "oreb": 1.0, "plus_minus": 0.0,
    "pts+reb": 20.0, "pts+ast": 19.0,
    "pts+reb+ast": 24.0, "blk+stl": 1.5,
}


def _load_best_model(stat_type: str):
    """Load the best available saved model for a stat type.

    Args:
        stat_type: Target stat (e.g. "pts").

    Returns:
        Loaded model instance, or None if not found.
    """
    try:
        import joblib
        from tracking.model_performance import get_best_model

        best_name = get_best_model(stat_type)
        path = os.path.join(_SAVED_DIR, f"{best_name}_{stat_type}.joblib")
        if os.path.exists(path):
            model = joblib.load(path)
            _logger.debug("Loaded model %s for %s", best_name, stat_type)
            return model

        # Fallback: try any available model
        for fname in os.listdir(_SAVED_DIR) if os.path.isdir(_SAVED_DIR) else []:
            if fname.endswith(f"_{stat_type}.joblib"):
                model = joblib.load(os.path.join(_SAVED_DIR, fname))
                _logger.debug("Loaded fallback model %s", fname)
                return model
    except Exception as exc:
        _logger.debug("_load_best_model failed: %s", exc)
    return None


def _lookup_player_data(player_name: str):
    """Look up player stats from the ETL database (smartpicks.db).

    Bridges the two databases by resolving *player_name* to a
    ``player_id`` and pulling season averages, recent game logs,
    team info, and home/away splits.

    Returns:
        Tuple of (player_averages_dict, team_dict, game_logs_list, splits_dict).
        Any element may be empty if the data is unavailable.
    """
    try:
        from data.etl_data_service import get_player_by_name, get_player_game_logs
        from data.db_service import get_team, get_player_splits
    except ImportError:
        _logger.debug("_lookup_player_data: import failed")
        return {}, {}, [], {}

    player = get_player_by_name(player_name)
    if not player:
        _logger.debug("_lookup_player_data: player '%s' not found", player_name)
        return {}, {}, [], {}

    player_id = player.get("player_id")
    team_id = player.get("team_id")

    # Season averages are already merged into the player dict by
    # get_player_by_name (it calls _compute_averages internally).
    averages = {k: v for k, v in player.items() if isinstance(v, (int, float))}

    game_logs = get_player_game_logs(player_id, limit=30) if player_id else []

    team = get_team(team_id) if team_id else {}

    # Fetch home/away splits so the prediction can use location-specific
    # averages instead of just a binary is_home flag.
    splits = get_player_splits(player_id) if player_id else {}

    return averages, team, game_logs, splits


def _compute_confidence_interval(prediction, stat_type, game_logs, player_averages):
    """Derive a confidence interval from actual stat variance.

    Uses the sample standard deviation of the player's recent game logs
    for the requested stat.  Falls back to the pre-computed std from
    ``etl_data_service._compute_averages``, and only as a last resort
    uses a ±15 % heuristic.

    Supports combo stats (e.g. ``"pts+reb"``) by summing the component
    columns per game before computing the standard deviation.

    Returns:
        Tuple ``(lower, upper)`` rounded to two decimals, or *None*.
    """
    col = _STAT_COL_MAP.get(stat_type)
    combo_cols = _COMBO_STAT_COLS.get(stat_type)
    std = None

    # Strategy 1: compute from recent game logs
    if game_logs:
        values: list[float] = []
        if combo_cols:
            # Sum component columns per game for combo stats
            for g in game_logs:
                values.append(sum(float(g.get(c, 0) or 0) for c in combo_cols))
        elif col:
            values = [float(g.get(col, 0) or 0) for g in game_logs]
        if len(values) >= 2:
            try:
                std = _statistics.stdev(values)
            except _statistics.StatisticsError:
                pass

    # Strategy 2: use pre-computed std from season averages
    if std is None or std == 0:
        std_key = _STAT_STD_MAP.get(stat_type)
        if std_key and player_averages:
            std = float(player_averages.get(std_key, 0) or 0)

    # Strategy 3: heuristic fallback (±15 % of prediction)
    if not std or std == 0:
        return (round(prediction * 0.85, 2), round(prediction * 1.15, 2))

    # Use ±1 standard deviation as the confidence band
    lower = round(max(prediction - std, 0), 2)
    upper = round(prediction + std, 2)
    return (lower, upper)


def predict_player_stat(
    player_name: str,
    stat_type: str,
    game_context: dict,
) -> dict:
    """Generate a prediction for a player stat.

    The function queries the ETL database (``db/smartpicks.db``) to pull
    real player averages, recent game logs, and team stats, then feeds
    those into ``build_feature_matrix`` so predictions are grounded in
    actual data rather than empty dicts.

    Args:
        player_name: Player's full name.
        stat_type: Stat to predict (e.g. "pts", "reb", "ast").
        game_context: Dict with game context (rest_days, is_home, opponent_drtg, etc.).

    Returns:
        Dict with ``player_name``, ``stat_type``, ``prediction``,
        ``confidence_interval``, and ``source``.
    """
    result = {
        "player_name": player_name,
        "stat_type": stat_type,
        "prediction": None,
        "confidence_interval": None,
        "source": "unavailable",
    }

    try:
        from engine.features.feature_engineering import (
            build_feature_matrix,
            calculate_rolling_averages,
        )
        import numpy as np

        # ── Fix #1 & #6: Fetch real data from smartpicks.db ──────────
        player_averages, team_data, game_logs, splits = _lookup_player_data(player_name)

        # Build a richer player_data dict from season averages + rolling
        player_data = dict(player_averages)
        if game_logs:
            rolling = calculate_rolling_averages(game_logs)
            player_data.update(rolling)

        # ── Fix #2: Enrich with home/away split averages ─────────────
        # Instead of just passing is_home as a binary flag, load the
        # player's actual home vs away stat averages so the model can
        # leverage the real location-specific performance signal.
        if splits:
            is_home = game_context.get("is_home")
            loc_key = "home" if is_home else "away"
            loc_rows = splits.get(loc_key, [])
            if loc_rows:
                loc = loc_rows[0]
                for feat, split_key in _SPLIT_KEY_MAP.items():
                    val = loc.get(split_key)
                    if val is not None:
                        player_data[feat] = float(val)

        # Opponent data: use game_context overrides when provided,
        # otherwise fall through to empty (build_feature_matrix handles defaults).
        opponent_data = {}
        opp_drtg = game_context.get("opponent_drtg")
        if opp_drtg is not None:
            opponent_data["drtg"] = float(opp_drtg)
            team_data.setdefault("drtg", 110.0)

        # Build the feature matrix with real data
        features = build_feature_matrix(player_data, team_data, opponent_data, game_context)
        X = np.array([list(features.values())], dtype=float)

        model = _load_best_model(stat_type)
        combo_avg_keys = _COMBO_STAT_AVGS.get(stat_type)

        # ML models are only trained for simple stats; combo stats always
        # use the season-average fallback (sum of component averages).
        if model is not None and combo_avg_keys is None:
            preds = model.predict(X)
            prediction = float(preds[0]) if hasattr(preds, "__len__") else float(preds)
            result["prediction"] = round(prediction, 2)
            # ── Fix #5: data-driven confidence interval ───────────────
            result["confidence_interval"] = _compute_confidence_interval(
                prediction, stat_type, game_logs, player_averages,
            )
            result["source"] = "ml_model"
        else:
            # Statistical fallback: use player's actual season average.
            # For combo stats, sum the component averages.
            avg_val = 0.0
            if combo_avg_keys and player_averages:
                for k in combo_avg_keys:
                    avg_val += float(player_averages.get(k, 0) or 0)
            else:
                avg_key = _STAT_AVG_MAP.get(stat_type)
                avg_val = float(player_averages.get(avg_key, 0) or 0) if avg_key and player_averages else 0

            if avg_val > 0:
                result["prediction"] = round(avg_val, 2)
                result["confidence_interval"] = _compute_confidence_interval(
                    avg_val, stat_type, game_logs, player_averages,
                )
                result["source"] = "season_average"
            else:
                result["prediction"] = _STAT_DEFAULTS.get(stat_type, 5.0)
                result["confidence_interval"] = None
                result["source"] = "default_fallback"
    except Exception as exc:
        _logger.debug("predict_player_stat failed for %s/%s: %s", player_name, stat_type, exc)
        result["source"] = "error"

    return result
