"""
data/db_service.py
==================
Single gateway to the local SmartPicks ETL database (db/smartpicks.db).

Replaces: live_data_fetcher.py, nba_live_fetcher.py, nba_stats_service.py,
          nba_data_service.py, data_manager.py, bdl_bridge.py

All functions read directly from the local SQLite database — no live API
calls are made.  If the database does not exist yet (fresh install), every
function degrades gracefully and returns an empty result so the rest of
the app keeps working.
"""

from __future__ import annotations

import datetime
import logging
import math
import sqlite3
from pathlib import Path
from typing import Any

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── DB path ───────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "db" / "smartpicks.db"


# ── Connection helper ─────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection | None:
    """Return a read-only SQLite connection, or *None* if the DB doesn't exist."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as exc:
            _logger.warning("db_service: cannot open DB: %s", exc)
            return None


def _rows_to_dicts(rows) -> list[dict]:
    """Convert ``sqlite3.Row`` objects to plain dicts."""
    return [dict(row) for row in rows]


def _r(val, decimals: int = 1) -> float:
    """Safely round a value that may be ``None``."""
    try:
        return round(float(val or 0), decimals)
    except (TypeError, ValueError):
        return 0.0


def _safe_float(val) -> float:
    """Coerce to float, returning 0.0 on failure."""
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _parse_minutes(m) -> float:
    """Parse a minutes value that may be ``'MM:SS'`` or numeric."""
    if m is None:
        return 0.0
    m_str = str(m)
    try:
        if ":" in m_str:
            parts = m_str.split(":")
            return float(parts[0]) + float(parts[1]) / 60.0
        return float(m_str)
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE DATA FUNCTIONS (the new clean API)
# ═══════════════════════════════════════════════════════════════════════════════


def get_player_last_n_games(player_id: int, n: int = 10) -> list[dict]:
    """
    Return the last *n* game-log rows for a player, most-recent first.

    Each dict contains: game_date, matchup, pts, reb, ast, stl, blk, tov,
    min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct, oreb,
    dreb, pf, plus_minus, wl.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                g.game_date, g.matchup,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
            LIMIT ?
            """,
            (int(player_id), int(n)),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_player_last_n_games(%s, %s) failed: %s", player_id, n, exc)
        return []
    finally:
        conn.close()


def get_player_averages(player_id: int) -> dict:
    """
    Return season averages for a player from their game logs.

    Keys: gp, ppg, rpg, apg, spg, bpg, topg, mpg, fg3_avg, ftm_avg,
    fta_avg, ft_pct_avg, fgm_avg, fga_avg, fg_pct_avg, oreb_avg, dreb_avg,
    pf_avg, plus_minus_avg, points_std, rebounds_std, assists_std, threes_std.
    """
    from data.etl_data_service import _compute_averages, _get_conn as _etl_conn

    conn = _etl_conn()
    if conn is None:
        return {}
    try:
        return _compute_averages(int(player_id), conn)
    except Exception as exc:
        _logger.warning("get_player_averages(%s) failed: %s", player_id, exc)
        return {}
    finally:
        conn.close()


def get_team(team_id: int) -> dict:
    """
    Return team metadata from the Teams table.

    Keys: team_id, abbreviation, team_name, conference, division, pace,
    ortg, drtg.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        row = conn.execute(
            "SELECT * FROM Teams WHERE team_id = ?", (int(team_id),)
        ).fetchone()
        return dict(row) if row else {}
    except Exception as exc:
        _logger.warning("get_team(%s) failed: %s", team_id, exc)
        return {}
    finally:
        conn.close()


def get_defense_vs_position(
    team_abbrev: str,
    position: str | None = None,
    season: str | None = None,
) -> list[dict]:
    """
    Return defensive multipliers for a team from the Defense_Vs_Position table.

    If *position* is given only that row is returned; otherwise all positions
    for the team.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        if position:
            rows = conn.execute(
                """
                SELECT * FROM Defense_Vs_Position
                WHERE team_abbreviation = ? AND season = ? AND pos = ?
                """,
                (team_abbrev, season, position),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM Defense_Vs_Position
                WHERE team_abbreviation = ? AND season = ?
                """,
                (team_abbrev, season),
            ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_defense_vs_position(%s) failed: %s", team_abbrev, exc)
        return []
    finally:
        conn.close()


def get_team_recent_stats(team_id: int, n: int = 10) -> list[dict]:
    """
    Return the last *n* Team_Game_Stats rows for a team, most-recent first.

    Keys: game_id, team_id, opponent_team_id, is_home, points_scored,
    points_allowed, pace_est, ortg_est, drtg_est, game_date.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT tgs.*, g.game_date
            FROM Team_Game_Stats tgs
            JOIN Games g ON tgs.game_id = g.game_id
            WHERE tgs.team_id = ?
            ORDER BY g.game_date DESC
            LIMIT ?
            """,
            (int(team_id), int(n)),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_team_recent_stats(%s) failed: %s", team_id, exc)
        return []
    finally:
        conn.close()


def get_team_roster(team_id: int) -> list[dict]:
    """
    Return all players on a team's roster.

    Keys: team_id, player_id, first_name, last_name, position,
    is_two_way, is_g_league.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                tr.team_id, tr.player_id,
                p.first_name, p.last_name, p.position,
                tr.is_two_way, tr.is_g_league
            FROM Team_Roster tr
            JOIN Players p ON tr.player_id = p.player_id
            WHERE tr.team_id = ?
              AND tr.effective_end_date IS NULL
            ORDER BY p.last_name
            """,
            (int(team_id),),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_team_roster(%s) failed: %s", team_id, exc)
        return []
    finally:
        conn.close()


def get_injured_players(team_id: int | None = None) -> list[dict]:
    """
    Return current injury reports.

    If *team_id* is given, only that team's injuries are returned.
    Keys: player_id, first_name, last_name, team_id, status, reason, report_date.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if team_id is not None:
            rows = conn.execute(
                """
                SELECT i.player_id, p.first_name, p.last_name,
                       i.team_id, i.status, i.reason, i.report_date
                FROM Injury_Status i
                JOIN Players p ON i.player_id = p.player_id
                WHERE i.team_id = ?
                ORDER BY i.report_date DESC
                """,
                (int(team_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT i.player_id, p.first_name, p.last_name,
                       i.team_id, i.status, i.reason, i.report_date
                FROM Injury_Status i
                JOIN Players p ON i.player_id = p.player_id
                ORDER BY i.report_date DESC
                """,
            ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_injured_players failed: %s", exc)
        return []
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY WRAPPERS
#  Match the signatures of the old fetcher modules so engine code can switch
#  imports without any other changes.
# ═══════════════════════════════════════════════════════════════════════════════


# ── from data.nba_stats_service ──────────────────────────────────────────────

def get_player_game_logs(player_id: int, season: str | None = None) -> list[dict]:
    """
    Replacement for ``nba_stats_service.get_player_game_logs``.

    Returns game logs with **UPPERCASE** column names to match the nba_api
    ``PlayerGameLog`` format that engine code expects.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                g.game_date, g.matchup,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
            """,
            (int(player_id),),
        ).fetchall()
        # Map to UPPERCASE keys matching nba_api PlayerGameLog format
        result = []
        for row in rows:
            d = dict(row)
            result.append({
                "GAME_DATE": d.get("game_date", ""),
                "MATCHUP":   d.get("matchup", ""),
                "PTS":       d.get("pts", 0),
                "REB":       d.get("reb", 0),
                "AST":       d.get("ast", 0),
                "STL":       d.get("stl", 0),
                "BLK":       d.get("blk", 0),
                "TOV":       d.get("tov", 0),
                "MIN":       d.get("min", "0"),
                "FGM":       d.get("fgm", 0),
                "FGA":       d.get("fga", 0),
                "FG_PCT":    d.get("fg_pct", 0.0),
                "FG3M":      d.get("fg3m", 0),
                "FG3A":      d.get("fg3a", 0),
                "FG3_PCT":   d.get("fg3_pct", 0.0),
                "FTM":       d.get("ftm", 0),
                "FTA":       d.get("fta", 0),
                "FT_PCT":    d.get("ft_pct", 0.0),
                "OREB":      d.get("oreb", 0),
                "DREB":      d.get("dreb", 0),
                "PF":        d.get("pf", 0),
                "PLUS_MINUS": d.get("plus_minus", 0),
                "WL":        d.get("wl", ""),
            })
        return result
    except Exception as exc:
        _logger.warning("get_player_game_logs(%s) failed: %s", player_id, exc)
        return []
    finally:
        conn.close()


def get_defensive_matchup_data(
    season: str | None = None,
    per_mode: str = "PerGame",
) -> list[dict]:
    """
    Replacement for ``nba_stats_service.get_defensive_matchup_data``.

    Returns rows from the Defense_Vs_Position table formatted to resemble
    the nba_api ``LeagueDashPtDefend`` output.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        if season is None:
            season = _current_season()
        rows = conn.execute(
            "SELECT * FROM Defense_Vs_Position WHERE season = ?",
            (season,),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_defensive_matchup_data failed: %s", exc)
        return []
    finally:
        conn.close()


def get_player_splits(player_id: int, season: str | None = None) -> dict:
    """
    Replacement for ``nba_stats_service.get_player_splits``.

    Computes home/away and last-N splits from the local Player_Game_Logs
    table.  Returns a dict with keys: last_5_games, last_10_games, home,
    away — each a list of stat-summary dicts.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        all_logs = conn.execute(
            """
            SELECT
                g.game_date, g.matchup, g.home_team_id, g.away_team_id,
                p.team_id,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
            """,
            (int(player_id),),
        ).fetchall()

        logs = [dict(r) for r in all_logs]
        if not logs:
            return {}

        def _summarise(subset: list[dict]) -> list[dict]:
            if not subset:
                return []
            n = len(subset)
            return [{
                "GP":   n,
                "PTS":  _r(sum(_safe_float(g.get("pts")) for g in subset) / n),
                "REB":  _r(sum(_safe_float(g.get("reb")) for g in subset) / n),
                "AST":  _r(sum(_safe_float(g.get("ast")) for g in subset) / n),
                "STL":  _r(sum(_safe_float(g.get("stl")) for g in subset) / n),
                "BLK":  _r(sum(_safe_float(g.get("blk")) for g in subset) / n),
                "TOV":  _r(sum(_safe_float(g.get("tov")) for g in subset) / n),
                "FG3M": _r(sum(_safe_float(g.get("fg3m")) for g in subset) / n),
                "FTM":  _r(sum(_safe_float(g.get("ftm")) for g in subset) / n),
                "FTA":  _r(sum(_safe_float(g.get("fta")) for g in subset) / n),
                "FGM":  _r(sum(_safe_float(g.get("fgm")) for g in subset) / n),
                "FGA":  _r(sum(_safe_float(g.get("fga")) for g in subset) / n),
            }]

        # Determine home/away by comparing player's team_id to game's home/away
        player_team_id = logs[0].get("team_id")
        home_logs = [g for g in logs if g.get("home_team_id") == player_team_id]
        away_logs = [g for g in logs if g.get("away_team_id") == player_team_id]

        return {
            "last_5_games":  _summarise(logs[:5]),
            "last_10_games": _summarise(logs[:10]),
            "home":          _summarise(home_logs),
            "away":          _summarise(away_logs),
        }
    except Exception as exc:
        _logger.warning("get_player_splits(%s) failed: %s", player_id, exc)
        return {}
    finally:
        conn.close()


def get_advanced_box_score(game_id: str) -> dict:
    """
    Replacement for ``nba_stats_service.get_advanced_box_score``.

    Computes approximate advanced stats from the local Player_Game_Logs.
    Returns dict with keys: player_stats, team_stats.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT
                l.player_id, p.first_name, p.last_name, p.team_id,
                l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                l.fgm, l.fga, l.fg_pct, l.fg3m, l.fg3a, l.fg3_pct,
                l.ftm, l.fta, l.ft_pct, l.oreb, l.dreb,
                l.pf, l.plus_minus
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.game_id = ?
            """,
            (str(game_id),),
        ).fetchall()

        if not rows:
            return {}

        player_stats = []
        for row in rows:
            d = dict(row)
            mins = _parse_minutes(d.get("min"))
            fga = _safe_float(d.get("fga"))
            fgm = _safe_float(d.get("fgm"))
            fg3m = _safe_float(d.get("fg3m"))
            fta = _safe_float(d.get("fta"))
            ftm = _safe_float(d.get("ftm"))
            pts = _safe_float(d.get("pts"))
            tov = _safe_float(d.get("tov"))

            # Approximate advanced metrics
            efg_pct = ((fgm + 0.5 * fg3m) / fga) if fga > 0 else 0.0
            ts_denom = 2 * (fga + 0.44 * fta)
            ts_pct = (pts / ts_denom) if ts_denom > 0 else 0.0
            # Usage estimate: (FGA + 0.44*FTA + TOV) / minutes-share
            # Simplified: we don't have team totals per-game so just store raw
            usg_pct = 0.0

            player_stats.append({
                "PLAYER_NAME": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "playerName":  f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "PLAYER_ID":   d.get("player_id"),
                "TEAM_ID":     d.get("team_id"),
                "MIN":         mins,
                "EFG_PCT":     round(efg_pct, 3),
                "efgPct":      round(efg_pct, 3),
                "TS_PCT":      round(ts_pct, 3),
                "tsPct":       round(ts_pct, 3),
                "USG_PCT":     usg_pct,
                "usgPct":      usg_pct,
                "PTS":         pts,
                "REB":         _safe_float(d.get("reb")),
                "AST":         _safe_float(d.get("ast")),
            })

        # Aggregate team-level stats
        from collections import defaultdict
        team_agg: dict[int, dict] = defaultdict(lambda: {
            "pts": 0.0, "fgm": 0.0, "fga": 0.0, "fg3m": 0.0,
            "fta": 0.0, "ftm": 0.0, "tov": 0.0, "count": 0,
        })
        for row in rows:
            d = dict(row)
            tid = d.get("team_id")
            if tid is None:
                continue
            agg = team_agg[tid]
            agg["pts"] += _safe_float(d.get("pts"))
            agg["fgm"] += _safe_float(d.get("fgm"))
            agg["fga"] += _safe_float(d.get("fga"))
            agg["fg3m"] += _safe_float(d.get("fg3m"))
            agg["fta"] += _safe_float(d.get("fta"))
            agg["ftm"] += _safe_float(d.get("ftm"))
            agg["tov"] += _safe_float(d.get("tov"))
            agg["count"] += 1

        team_stats = []
        for tid, agg in team_agg.items():
            fga_t = agg["fga"]
            fgm_t = agg["fgm"]
            fg3m_t = agg["fg3m"]
            fta_t = agg["fta"]
            efg = ((fgm_t + 0.5 * fg3m_t) / fga_t) if fga_t > 0 else 0.0
            to_rate = (agg["tov"] / (fga_t + 0.44 * fta_t + agg["tov"])) if (fga_t + agg["tov"]) > 0 else 0.0
            team_stats.append({
                "TEAM_ID":  tid,
                "EFG_PCT":  round(efg, 3),
                "TOV_PCT":  round(to_rate, 3),
                "FTA_RATE": round(fta_t / fga_t, 3) if fga_t > 0 else 0.0,
                "PTS":      agg["pts"],
            })

        return {"player_stats": player_stats, "team_stats": team_stats}
    except Exception as exc:
        _logger.warning("get_advanced_box_score(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


# ── from data.nba_data_service ───────────────────────────────────────────────

def get_player_estimated_metrics(season: str | None = None) -> list:
    """
    Replacement for ``nba_data_service.get_player_estimated_metrics``.

    Returns estimated advanced metrics from the Player_Bio table.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT * FROM Player_Bio"
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            result.append({
                "PLAYER_ID":   d.get("player_id"),
                "PLAYER_NAME": d.get("player_name", ""),
                "TEAM_ID":     d.get("team_id"),
                "GP":          d.get("gp", 0),
                "E_PACE":      d.get("pts", 0),  # Approximate pace proxy
                "e_pace":      d.get("pts", 0),
                "E_OFF_RATING": d.get("net_rating", 0),
                "E_DEF_RATING": 0,
                "USG_PCT":     d.get("usg_pct", 0),
                "TS_PCT":      d.get("ts_pct", 0),
                "AST_PCT":     d.get("ast_pct", 0),
            })
        return result
    except Exception as exc:
        _logger.warning("get_player_estimated_metrics failed: %s", exc)
        return []
    finally:
        conn.close()


def get_rotations(game_id: str) -> dict:
    """
    Replacement for ``nba_data_service.get_rotations``.

    Returns rotation stint data from the Play_By_Play table.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM Play_By_Play
            WHERE game_id = ?
            ORDER BY period, action_number
            """,
            (str(game_id),),
        ).fetchall()
        if not rows:
            return {}
        return {"play_by_play": _rows_to_dicts(rows)}
    except Exception as exc:
        _logger.warning("get_rotations(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_team_game_logs(
    team_id: int,
    season: str | None = None,
    last_n: int = 0,
) -> list:
    """
    Replacement for ``nba_data_service.get_team_game_logs``.

    Returns per-game stats for a team from Team_Game_Stats joined with Games.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        query = """
            SELECT
                tgs.game_id, g.game_date, g.matchup,
                tgs.points_scored, tgs.points_allowed,
                tgs.pace_est, tgs.ortg_est, tgs.drtg_est,
                tgs.is_home, tgs.opponent_team_id
            FROM Team_Game_Stats tgs
            JOIN Games g ON tgs.game_id = g.game_id
            WHERE tgs.team_id = ?
            ORDER BY g.game_date DESC
        """
        params: list[Any] = [int(team_id)]
        if last_n and last_n > 0:
            query += " LIMIT ?"
            params.append(int(last_n))

        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_team_game_logs(%s) failed: %s", team_id, exc)
        return []
    finally:
        conn.close()


def get_four_factors_box_score(game_id: str) -> dict:
    """
    Replacement for ``nba_data_service.get_four_factors_box_score``.

    Computes four-factors (eFG%, TO%, ORB%, FT rate) from Team_Game_Stats
    or Player_Game_Logs.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        # Try Team_Game_Stats first
        rows = conn.execute(
            """
            SELECT team_id, points_scored, points_allowed,
                   pace_est, ortg_est, drtg_est
            FROM Team_Game_Stats
            WHERE game_id = ?
            """,
            (str(game_id),),
        ).fetchall()

        if rows:
            team_stats = []
            for row in rows:
                d = dict(row)
                team_stats.append({
                    "TEAM_ID":  d.get("team_id"),
                    "PTS":      d.get("points_scored", 0),
                    "PACE":     d.get("pace_est", 0),
                    "EFG_PCT":  0.0,  # Not directly available without shot data
                    "FTA_RATE": 0.0,
                    "TM_TOV_PCT": 0.0,
                    "OREB_PCT": 0.0,
                })
            return {"team_stats": team_stats}

        # Fallback: compute from Player_Game_Logs
        plogs = conn.execute(
            """
            SELECT p.team_id,
                   SUM(l.fgm) AS fgm, SUM(l.fga) AS fga,
                   SUM(l.fg3m) AS fg3m,
                   SUM(l.ftm) AS ftm, SUM(l.fta) AS fta,
                   SUM(l.tov) AS tov, SUM(l.oreb) AS oreb,
                   SUM(l.dreb) AS dreb, SUM(l.pts) AS pts
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.game_id = ?
            GROUP BY p.team_id
            """,
            (str(game_id),),
        ).fetchall()

        if not plogs:
            return {}

        team_stats = []
        for row in plogs:
            d = dict(row)
            fga = _safe_float(d.get("fga"))
            fgm = _safe_float(d.get("fgm"))
            fg3m = _safe_float(d.get("fg3m"))
            fta = _safe_float(d.get("fta"))
            tov = _safe_float(d.get("tov"))
            oreb = _safe_float(d.get("oreb"))
            dreb = _safe_float(d.get("dreb"))

            efg = ((fgm + 0.5 * fg3m) / fga) if fga > 0 else 0.0
            fta_rate = (fta / fga) if fga > 0 else 0.0
            possessions = fga + 0.44 * fta + tov
            tov_pct = (tov / possessions) if possessions > 0 else 0.0
            total_reb = oreb + dreb
            oreb_pct = (oreb / total_reb) if total_reb > 0 else 0.0

            team_stats.append({
                "TEAM_ID":     d.get("team_id"),
                "PTS":         _safe_float(d.get("pts")),
                "EFG_PCT":     round(efg, 3),
                "FTA_RATE":    round(fta_rate, 3),
                "TM_TOV_PCT":  round(tov_pct, 3),
                "OREB_PCT":    round(oreb_pct, 3),
            })
        return {"team_stats": team_stats}
    except Exception as exc:
        _logger.warning("get_four_factors_box_score(%s) failed: %s", game_id, exc)
        return {}
    finally:
        conn.close()


def get_todays_games():
    """
    Replacement for ``nba_data_service.get_todays_games``.

    Reads from the Games table for today's date.
    """
    from data.etl_data_service import get_todays_games as _etl_todays

    return _etl_todays()


def get_player_stats(progress_callback=None) -> list:
    """
    Replacement for ``nba_data_service.get_player_stats``.

    Returns all players with season averages from the local DB.
    """
    from data.etl_data_service import get_all_players

    return get_all_players()


# ── from data.data_manager ───────────────────────────────────────────────────

def load_players_data() -> list:
    """
    Replacement for ``data_manager.load_players_data``.

    Delegates to data_manager to preserve Streamlit caching behaviour.
    """
    try:
        from data.data_manager import load_players_data as _dm_load
        return _dm_load()
    except Exception as exc:
        _logger.warning("load_players_data delegation failed: %s", exc)
        return []


def load_teams_data() -> list:
    """
    Replacement for ``data_manager.load_teams_data``.

    Delegates to data_manager to preserve Streamlit caching behaviour.
    """
    try:
        from data.data_manager import load_teams_data as _dm_load
        return _dm_load()
    except Exception as exc:
        _logger.warning("load_teams_data delegation failed: %s", exc)
        return []


def find_player_by_name(players_list, player_name):
    """
    Replacement for ``data_manager.find_player_by_name``.

    Delegates to data_manager's fuzzy matcher.
    """
    try:
        from data.data_manager import find_player_by_name as _dm_find
        return _dm_find(players_list, player_name)
    except Exception as exc:
        _logger.warning("find_player_by_name delegation failed: %s", exc)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _current_season() -> str:
    """Return the current NBA season string, e.g. ``'2025-26'``."""
    today = datetime.date.today()
    year = today.year if today.month >= 10 else today.year - 1
    return f"{year}-{str(year + 1)[-2:]}"
