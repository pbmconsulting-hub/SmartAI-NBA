"""engine/pipeline/step_3_features.py – Phase 3: Feature engineering.

Computes derived features for the ML-ready dataset:
  - True shooting % (TS%)
  - Usage rate estimate
  - Simplified PER
  - Rolling averages (3/5/10/20 game windows)
  - Pace adjustment factor
  - Defensive matchup factor
  - Rest / back-to-back flags
  - Home/away indicator
"""
import os
from utils.logger import get_logger

_logger = get_logger(__name__)
_ML_READY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ml_ready"
)


def _add_player_metrics(df):
    """Add TS%, usage-rate estimate, and simplified PER columns."""
    from engine.features.player_metrics import calculate_true_shooting, calculate_per

    # True Shooting %
    if all(c in df.columns for c in ["pts", "fga", "fta"]):
        df["ts_pct"] = df.apply(
            lambda r: calculate_true_shooting(
                float(r.get("pts") or 0),
                float(r.get("fga") or 0),
                float(r.get("fta") or 0),
            ),
            axis=1,
        )

    # Simplified usage-rate proxy (player-level only – no team totals in
    # this dataset, so we compute an individual-level proxy):
    #   usage_proxy = (FGA + 0.44*FTA + TOV) per minute played.
    if all(c in df.columns for c in ["fga", "fta", "tov"]):
        mp_col = None
        for candidate in ("min", "mp", "minutes"):
            if candidate in df.columns:
                mp_col = candidate
                break

        if mp_col is not None:
            def _usg(r):
                mp = float(r.get(mp_col) or 0)
                if mp <= 0:
                    return 0.0
                # 0.44 is the standard FTA coefficient in NBA usage rate formulas
                return (float(r.get("fga") or 0)
                        + 0.44 * float(r.get("fta") or 0)
                        + float(r.get("tov") or 0)) / mp
            df["usage_proxy"] = df.apply(_usg, axis=1)

    # Simplified PER
    per_cols = {"pts", "reb", "ast", "stl", "blk", "tov", "fga", "fgm", "fta", "ftm"}
    if per_cols.issubset(set(df.columns)):
        mp_col = None
        for candidate in ("min", "mp", "minutes"):
            if candidate in df.columns:
                mp_col = candidate
                break
        if mp_col is not None:
            df["per_estimate"] = df.apply(
                lambda r: calculate_per({**r, "mp": r.get(mp_col, 1)}), axis=1,
            )

    return df


def _add_rolling_averages(df):
    """Add rolling-window averages for key stat columns."""
    import pandas as pd

    stat_cols = [c for c in ["pts", "reb", "ast", "stl", "blk", "tov",
                             "fg3m", "ftm", "fga", "fgm", "oreb", "dreb",
                             "plus_minus"]
                 if c in df.columns]

    windows = [3, 5, 10]
    for col in stat_cols:
        series = pd.to_numeric(df[col], errors="coerce").fillna(0)
        for w in windows:
            df[f"{col}_rolling_{w}"] = series.rolling(window=w, min_periods=1).mean()

    return df


def _add_context_features(df):
    """Add pace, defensive-matchup, rest, and home/away features."""
    from utils.constants import LEAGUE_AVG_PACE, LEAGUE_AVG_DRTG
    from engine.features.feature_engineering import (
        calculate_pace_adjustment,
        calculate_defensive_matchup_factor,
        calculate_days_rest_factor,
    )

    # Pace adjustment (requires team_pace and opponent_pace)
    if "team_pace" in df.columns and "opponent_pace" in df.columns:
        df["pace_adjustment"] = df.apply(
            lambda r: calculate_pace_adjustment(
                float(r.get("team_pace") or LEAGUE_AVG_PACE),
                float(r.get("opponent_pace") or LEAGUE_AVG_PACE),
            ),
            axis=1,
        )

    # Defensive matchup factor
    if "opponent_drtg" in df.columns:
        df["defensive_matchup_factor"] = df["opponent_drtg"].apply(
            lambda v: calculate_defensive_matchup_factor(
                float(v or LEAGUE_AVG_DRTG),
            )
        )

    # Rest factor & back-to-back flag
    if "rest_days" in df.columns:
        df["rest_factor"] = df["rest_days"].apply(
            lambda v: calculate_days_rest_factor(int(v or 1))
        )
        df["is_back_to_back"] = (df["rest_days"].fillna(1).astype(int) == 0).astype(int)

    # Home/away indicator
    if "is_home" in df.columns:
        df["is_home_int"] = df["is_home"].apply(
            lambda v: 1 if v else 0
        )

    return df


def run(context: dict) -> dict:
    """Compute derived features and save ML-ready data.

    Args:
        context: Pipeline context with ``clean_data`` key.

    Returns:
        Updated context with ``feature_data`` key.
    """
    os.makedirs(_ML_READY_DIR, exist_ok=True)
    clean_data = context.get("clean_data", {})
    date_str = context.get("date_str", "unknown")
    feature_data = {}

    # ── Load team pace/DRTG from DB for enrichment ──
    team_lookup: dict = {}
    try:
        from data.etl_data_service import is_db_available, get_all_teams
        if is_db_available():
            teams = get_all_teams()
            for t in (teams or []):
                abbr = t.get("abbreviation", "")
                if abbr:
                    team_lookup[abbr] = {
                        "pace": float(t.get("pace") or 0),
                        "drtg": float(t.get("drtg") or 0),
                    }
            if team_lookup:
                _logger.info("Loaded pace/drtg for %d teams from DB", len(team_lookup))
    except Exception as exc:
        _logger.debug("Team DB enrichment failed: %s", exc)

    try:
        import pandas as pd
        from utils.parquet_helpers import save_parquet

        player_df = clean_data.get("player_stats")
        if player_df is not None and not (hasattr(player_df, "empty") and player_df.empty):
            df = pd.DataFrame(player_df) if isinstance(player_df, list) else player_df.copy()

            # ── Enrich with DB team pace/DRTG if available ──
            if team_lookup:
                team_col = None
                for candidate in ("team", "team_abbreviation", "team_abbrev"):
                    if candidate in df.columns:
                        team_col = candidate
                        break
                if team_col is not None:
                    if "team_pace" not in df.columns:
                        df["team_pace"] = df[team_col].map(
                            lambda a: team_lookup.get(str(a), {}).get("pace", 0)
                        )
                    if "team_drtg" not in df.columns:
                        df["team_drtg"] = df[team_col].map(
                            lambda a: team_lookup.get(str(a), {}).get("drtg", 0)
                        )

            # ── Player-level metrics (TS%, usage proxy, PER) ──
            try:
                df = _add_player_metrics(df)
            except Exception as exc:
                _logger.debug("Player metrics features failed: %s", exc)

            # ── Rolling averages (3/5/10 game windows) ──
            try:
                df = _add_rolling_averages(df)
            except Exception as exc:
                _logger.debug("Rolling average features failed: %s", exc)

            # ── Contextual features (pace, defense, rest, home/away) ──
            try:
                df = _add_context_features(df)
            except Exception as exc:
                _logger.debug("Context features failed: %s", exc)

            feature_data["player_features"] = df
            path = os.path.join(_ML_READY_DIR, f"player_features_{date_str}.parquet")
            save_parquet(df, path)
            _logger.info("Saved player features → %d rows, %d columns", len(df), len(df.columns))
    except Exception as exc:
        _logger.debug("Feature engineering error: %s", exc)
        feature_data = clean_data

    context["feature_data"] = feature_data
    return context
