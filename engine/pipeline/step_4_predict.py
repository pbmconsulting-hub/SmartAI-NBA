"""engine/pipeline/step_4_predict.py – Phase 4: Generate predictions."""
import datetime
import os
import sqlite3
from utils.logger import get_logger

_logger = get_logger(__name__)

_MAX_PLAYERS = 50
_DEFAULT_REST_DAYS = 1
_DEFAULT_DRTG = 110.0
_DEFAULT_PACE = 100.0

# All stat types the pipeline predicts: simple + combo.
_SIMPLE_STATS = ["pts", "reb", "ast", "stl", "blk", "tov", "fg3m", "ftm", "oreb", "plus_minus"]
_COMBO_STATS = ["pts+reb", "pts+ast", "pts+reb+ast", "blk+stl"]
_ALL_STATS = _SIMPLE_STATS + _COMBO_STATS

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_PATH = os.path.join(_REPO_ROOT, "db", "smartpicks.db")


def _build_game_context_map() -> dict:
    """Return a ``{team_id: game_context}`` mapping for today's games.

    Queries the Games and Teams tables to build per-team context dicts
    containing ``is_home``, ``opponent_drtg``, ``team_pace``, and
    ``opponent_pace``.  Returns an empty dict if any DB call fails.
    """
    try:
        from data.db_service import get_team
    except ImportError:
        return {}

    if not os.path.exists(_DB_PATH):
        return {}

    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT home_team_id, away_team_id FROM Games WHERE game_date = ?",
            (today,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        _logger.debug("_build_game_context_map DB query failed: %s", exc)
        return {}

    team_cache: dict = {}
    ctx_map: dict = {}

    for row in rows:
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        if not home_id or not away_id:
            continue

        for tid in (int(home_id), int(away_id)):
            if tid not in team_cache:
                team_cache[tid] = get_team(tid)

        home_t = team_cache.get(int(home_id), {})
        away_t = team_cache.get(int(away_id), {})

        ctx_map[int(home_id)] = {
            "is_home": True,
            "rest_days": _DEFAULT_REST_DAYS,
            "opponent_drtg": float(away_t.get("drtg") or _DEFAULT_DRTG),
            "team_pace": float(home_t.get("pace") or _DEFAULT_PACE),
            "opponent_pace": float(away_t.get("pace") or _DEFAULT_PACE),
        }
        ctx_map[int(away_id)] = {
            "is_home": False,
            "rest_days": _DEFAULT_REST_DAYS,
            "opponent_drtg": float(home_t.get("drtg") or _DEFAULT_DRTG),
            "team_pace": float(away_t.get("pace") or _DEFAULT_PACE),
            "opponent_pace": float(home_t.get("pace") or _DEFAULT_PACE),
        }

    _logger.debug("Built game context map for %d teams", len(ctx_map))
    return ctx_map


def run(context: dict) -> dict:
    """Run predictions using saved ML models.

    Args:
        context: Pipeline context with ``feature_data``.

    Returns:
        Updated context with ``predictions`` key.
    """
    predictions = []
    feature_data = context.get("feature_data", {})

    try:
        from engine.predict.predictor import predict_player_stat

        # Build a team_id → game_context map once for all players.
        game_ctx_map = _build_game_context_map()

        player_df = feature_data.get("player_features")
        if player_df is not None:
            try:
                import pandas as pd
                df = pd.DataFrame(player_df) if isinstance(player_df, list) else player_df
                for _, row in df.head(context.get("max_players", _MAX_PLAYERS)).iterrows():
                    player_name = row.get("player_name") or row.get("name", "Unknown")
                    team_id = row.get("team_id")
                    game_ctx = game_ctx_map.get(int(team_id), {}) if team_id else {}

                    for stat in _ALL_STATS:
                        try:
                            result = predict_player_stat(str(player_name), stat, game_ctx)
                            predictions.append(result)
                        except Exception as exc:
                            _logger.debug("predict %s/%s failed: %s", player_name, stat, exc)
            except Exception as exc:
                _logger.debug("DataFrame iteration failed: %s", exc)
    except ImportError as exc:
        _logger.debug("predictor not available: %s", exc)

    _logger.info("Generated %d predictions", len(predictions))
    context["predictions"] = predictions
    return context
