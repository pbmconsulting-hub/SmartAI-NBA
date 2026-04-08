"""
data/etl_data_service.py
=========================
Bridge between the ETL SQLite database (db/smartpicks.db) and
SmartAI-NBA's data layer.

All functions connect to the database read-only for queries and return
plain Python dicts/lists.  No live API calls are made here — those happen
only in etl/initial_pull.py and etl/data_updater.py.

If the database does not exist yet (fresh install, before running
initial_pull.py), every function degrades gracefully and returns an
empty result so the rest of the app keeps working.
"""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import statistics
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
    """Return a read-only SQLite connection, or None if the DB doesn't exist."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        # Fallback: open read-write (needed when the DB was just created)
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as exc:
            _logger.warning("etl_data_service: cannot open DB: %s", exc)
            return None


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def is_db_available() -> bool:
    """Return True if the ETL database exists and has player data."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        count = conn.execute("SELECT COUNT(*) FROM Players").fetchone()[0]
        return count > 0
    except Exception:
        return False
    finally:
        conn.close()


# ── Season averages helper ────────────────────────────────────────────────────


def _compute_averages(player_id: int, conn: sqlite3.Connection) -> dict:
    """Compute season averages for a single player from their game logs."""
    row = conn.execute(
        """
        SELECT
            COUNT(*)       AS gp,
            AVG(pts)       AS ppg,
            AVG(reb)       AS rpg,
            AVG(ast)       AS apg,
            AVG(stl)       AS spg,
            AVG(blk)       AS bpg,
            AVG(tov)       AS topg,
            AVG(
                CAST(
                    CASE
                        WHEN instr(min, ':') > 0
                        THEN CAST(substr(min, 1, instr(min, ':') - 1) AS REAL)
                             + CAST(substr(min, instr(min, ':') + 1) AS REAL) / 60.0
                        ELSE CAST(min AS REAL)
                    END
                AS REAL)
            )               AS mpg
        FROM Player_Game_Logs
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()

    if row is None or row["gp"] == 0:
        return {"gp": 0, "ppg": 0.0, "rpg": 0.0, "apg": 0.0,
                "spg": 0.0, "bpg": 0.0, "topg": 0.0, "mpg": 0.0,
                "fg3_avg": 0.0, "ftm_avg": 0.0, "fta_avg": 0.0,
                "ft_pct_avg": 0.0, "fgm_avg": 0.0, "fga_avg": 0.0,
                "fg_pct_avg": 0.0, "oreb_avg": 0.0, "dreb_avg": 0.0,
                "pf_avg": 0.0, "plus_minus_avg": 0.0,
                "points_std": 0.0, "rebounds_std": 0.0,
                "assists_std": 0.0, "threes_std": 0.0,
                "steals_std": 0.0, "blocks_std": 0.0,
                "turnovers_std": 0.0, "ftm_std": 0.0,
                "oreb_std": 0.0, "plus_minus_std": 0.0}

    def _r(val, decimals: int = 1) -> float:
        try:
            return round(float(val or 0), decimals)
        except (TypeError, ValueError):
            return 0.0

    averages: dict = {
        "gp":   int(row["gp"]),
        "ppg":  _r(row["ppg"]),
        "rpg":  _r(row["rpg"]),
        "apg":  _r(row["apg"]),
        "spg":  _r(row["spg"]),
        "bpg":  _r(row["bpg"]),
        "topg": _r(row["topg"]),
        "mpg":  _r(row["mpg"]),
    }

    # Extended averages — gracefully skip if columns don't exist in old DBs
    try:
        ext = conn.execute(
            """
            SELECT
                AVG(fg3m)       AS fg3_avg,
                AVG(ftm)        AS ftm_avg,
                AVG(fta)        AS fta_avg,
                AVG(ft_pct)     AS ft_pct_avg,
                AVG(fgm)        AS fgm_avg,
                AVG(fga)        AS fga_avg,
                AVG(fg_pct)     AS fg_pct_avg,
                AVG(oreb)       AS oreb_avg,
                AVG(dreb)       AS dreb_avg,
                AVG(pf)         AS pf_avg,
                AVG(plus_minus) AS plus_minus_avg
            FROM Player_Game_Logs
            WHERE player_id = ?
            """,
            (player_id,),
        ).fetchone()
        averages.update({
            "fg3_avg":        _r(ext["fg3_avg"]),
            "ftm_avg":        _r(ext["ftm_avg"]),
            "fta_avg":        _r(ext["fta_avg"]),
            "ft_pct_avg":     _r(ext["ft_pct_avg"], 3),
            "fgm_avg":        _r(ext["fgm_avg"]),
            "fga_avg":        _r(ext["fga_avg"]),
            "fg_pct_avg":     _r(ext["fg_pct_avg"], 3),
            "oreb_avg":       _r(ext["oreb_avg"]),
            "dreb_avg":       _r(ext["dreb_avg"]),
            "pf_avg":         _r(ext["pf_avg"]),
            "plus_minus_avg": _r(ext["plus_minus_avg"]),
        })
    except Exception:
        averages.update({
            "fg3_avg": 0.0, "ftm_avg": 0.0, "fta_avg": 0.0,
            "ft_pct_avg": 0.0, "fgm_avg": 0.0, "fga_avg": 0.0,
            "fg_pct_avg": 0.0, "oreb_avg": 0.0, "dreb_avg": 0.0,
            "pf_avg": 0.0, "plus_minus_avg": 0.0,
        })

    def _estimate_std(avgs: dict) -> None:
        """Fill std fields with heuristic estimates based on averages."""
        avgs["points_std"]      = _r(avgs.get("ppg", 0) * 0.30, 2)
        avgs["rebounds_std"]    = _r(avgs.get("rpg", 0) * 0.40, 2)
        avgs["assists_std"]     = _r(avgs.get("apg", 0) * 0.40, 2)
        avgs["threes_std"]      = 0.0
        avgs["steals_std"]      = _r(avgs.get("spg", 0) * 0.40, 2)
        avgs["blocks_std"]      = _r(avgs.get("bpg", 0) * 0.40, 2)
        avgs["turnovers_std"]   = _r(avgs.get("topg", 0) * 0.40, 2)
        avgs["ftm_std"]         = 0.0
        avgs["oreb_std"]        = 0.0
        avgs["plus_minus_std"]  = 0.0

    # Real standard deviations from game logs — gracefully fall back to estimates
    try:
        logs = conn.execute(
            "SELECT pts, reb, ast, fg3m, stl, blk, tov, ftm, oreb, plus_minus"
            " FROM Player_Game_Logs WHERE player_id = ?",
            (player_id,),
        ).fetchall()
        if len(logs) >= 2:
            pts_list  = [float(r[0] or 0) for r in logs]
            reb_list  = [float(r[1] or 0) for r in logs]
            ast_list  = [float(r[2] or 0) for r in logs]
            fg3m_list = [float(r[3] or 0) for r in logs]
            stl_list  = [float(r[4] or 0) for r in logs]
            blk_list  = [float(r[5] or 0) for r in logs]
            tov_list  = [float(r[6] or 0) for r in logs]
            ftm_list  = [float(r[7] or 0) for r in logs]
            oreb_list = [float(r[8] or 0) for r in logs]
            pm_list   = [float(r[9] or 0) for r in logs]
            averages["points_std"]      = _r(statistics.stdev(pts_list),  2)
            averages["rebounds_std"]    = _r(statistics.stdev(reb_list),  2)
            averages["assists_std"]     = _r(statistics.stdev(ast_list),  2)
            averages["threes_std"]      = _r(statistics.stdev(fg3m_list), 2)
            averages["steals_std"]      = _r(statistics.stdev(stl_list),  2)
            averages["blocks_std"]      = _r(statistics.stdev(blk_list),  2)
            averages["turnovers_std"]   = _r(statistics.stdev(tov_list),  2)
            averages["ftm_std"]         = _r(statistics.stdev(ftm_list),  2)
            averages["oreb_std"]        = _r(statistics.stdev(oreb_list), 2)
            averages["plus_minus_std"]  = _r(statistics.stdev(pm_list),   2)
        else:
            _estimate_std(averages)
    except Exception:
        _estimate_std(averages)

    return averages


# ── Public API ─────────────────────────────────────────────────────────────────


def get_all_players() -> list[dict]:
    """
    Return all players with season averages computed from game logs.

    Each dict has:
        player_id, first_name, last_name, team_id, team_abbreviation, position,
        gp, ppg, rpg, apg, spg, bpg, topg, mpg,
        fg3_avg, ftm_avg, fta_avg, ft_pct_avg, fgm_avg, fga_avg,
        fg_pct_avg, oreb_avg, dreb_avg, pf_avg, plus_minus_avg,
        points_std, rebounds_std, assists_std, threes_std
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                p.player_id,
                p.first_name,
                p.last_name,
                p.team_id,
                p.team_abbreviation,
                p.position,
                COUNT(l.game_id)  AS gp,
                AVG(l.pts)        AS ppg,
                AVG(l.reb)        AS rpg,
                AVG(l.ast)        AS apg,
                AVG(l.stl)        AS spg,
                AVG(l.blk)        AS bpg,
                AVG(l.tov)        AS topg,
                AVG(
                    CASE
                        WHEN instr(l.min, ':') > 0
                        THEN CAST(substr(l.min, 1, instr(l.min, ':') - 1) AS REAL)
                             + CAST(substr(l.min, instr(l.min, ':') + 1) AS REAL) / 60.0
                        ELSE CAST(l.min AS REAL)
                    END
                ) AS mpg
            FROM Players p
            LEFT JOIN Player_Game_Logs l ON p.player_id = l.player_id
            GROUP BY p.player_id
            ORDER BY ppg DESC
            """
        ).fetchall()

        def _r(val, d=1):
            try:
                return round(float(val or 0), d)
            except (TypeError, ValueError):
                return 0.0

        # Also try to pull extended averages in one bulk query
        try:
            ext_rows = conn.execute(
                """
                SELECT
                    player_id,
                    AVG(fg3m)       AS fg3_avg,
                    AVG(ftm)        AS ftm_avg,
                    AVG(fta)        AS fta_avg,
                    AVG(ft_pct)     AS ft_pct_avg,
                    AVG(fgm)        AS fgm_avg,
                    AVG(fga)        AS fga_avg,
                    AVG(fg_pct)     AS fg_pct_avg,
                    AVG(oreb)       AS oreb_avg,
                    AVG(dreb)       AS dreb_avg,
                    AVG(pf)         AS pf_avg,
                    AVG(plus_minus) AS plus_minus_avg
                FROM Player_Game_Logs
                GROUP BY player_id
                """
            ).fetchall()
            ext_map = {int(r["player_id"]): r for r in ext_rows}
        except Exception:
            ext_map = {}

        # Bulk std-dev query — one pass over all game logs
        try:
            _all_logs = conn.execute(
                """
                SELECT player_id, pts, reb, ast, fg3m, stl, blk, tov, ftm, oreb, plus_minus
                FROM Player_Game_Logs
                ORDER BY player_id
                """
            ).fetchall()
            # Group by player_id
            from collections import defaultdict
            _logs_by_player: dict[int, list] = defaultdict(list)
            for _log in _all_logs:
                _logs_by_player[int(_log["player_id"])].append(_log)

            def _std(values):
                if len(values) >= 2:
                    return round(statistics.stdev(values), 2)
                return 0.0

            std_map: dict[int, dict] = {}
            for _pid, _plogs in _logs_by_player.items():
                std_map[_pid] = {
                    "points_std":     _std([float(lg["pts"] or 0) for lg in _plogs]),
                    "rebounds_std":   _std([float(lg["reb"] or 0) for lg in _plogs]),
                    "assists_std":    _std([float(lg["ast"] or 0) for lg in _plogs]),
                    "threes_std":     _std([float(lg["fg3m"] or 0) for lg in _plogs]),
                    "steals_std":     _std([float(lg["stl"] or 0) for lg in _plogs]),
                    "blocks_std":     _std([float(lg["blk"] or 0) for lg in _plogs]),
                    "turnovers_std":  _std([float(lg["tov"] or 0) for lg in _plogs]),
                    "ftm_std":        _std([float(lg["ftm"] or 0) for lg in _plogs]),
                    "oreb_std":       _std([float(lg["oreb"] or 0) for lg in _plogs]),
                    "plus_minus_std": _std([float(lg["plus_minus"] or 0) for lg in _plogs]),
                }
        except Exception:
            std_map = {}

        result = []
        for row in rows:
            pid = int(row["player_id"])
            ext = ext_map.get(pid)
            result.append({
                "player_id":         pid,
                "first_name":        row["first_name"] or "",
                "last_name":         row["last_name"] or "",
                "team_id":           int(row["team_id"]) if row["team_id"] else None,
                "team_abbreviation": row["team_abbreviation"] or "",
                "position":          row["position"] or None,
                "gp":    int(row["gp"] or 0),
                "ppg":   _r(row["ppg"]),
                "rpg":   _r(row["rpg"]),
                "apg":   _r(row["apg"]),
                "spg":   _r(row["spg"]),
                "bpg":   _r(row["bpg"]),
                "topg":  _r(row["topg"]),
                "mpg":   _r(row["mpg"]),
                # Extended averages (0.0 if columns not present in old DB)
                "fg3_avg":        _r(ext["fg3_avg"])        if ext else 0.0,
                "ftm_avg":        _r(ext["ftm_avg"])        if ext else 0.0,
                "fta_avg":        _r(ext["fta_avg"])        if ext else 0.0,
                "ft_pct_avg":     _r(ext["ft_pct_avg"], 3) if ext else 0.0,
                "fgm_avg":        _r(ext["fgm_avg"])        if ext else 0.0,
                "fga_avg":        _r(ext["fga_avg"])        if ext else 0.0,
                "fg_pct_avg":     _r(ext["fg_pct_avg"], 3) if ext else 0.0,
                "oreb_avg":       _r(ext["oreb_avg"])       if ext else 0.0,
                "dreb_avg":       _r(ext["dreb_avg"])       if ext else 0.0,
                "pf_avg":         _r(ext["pf_avg"])         if ext else 0.0,
                "plus_minus_avg": _r(ext["plus_minus_avg"]) if ext else 0.0,
                # Standard deviations (real, computed from game logs)
                "points_std":     std_map.get(pid, {}).get("points_std", 0.0),
                "rebounds_std":   std_map.get(pid, {}).get("rebounds_std", 0.0),
                "assists_std":    std_map.get(pid, {}).get("assists_std", 0.0),
                "threes_std":     std_map.get(pid, {}).get("threes_std", 0.0),
                "steals_std":     std_map.get(pid, {}).get("steals_std", 0.0),
                "blocks_std":     std_map.get(pid, {}).get("blocks_std", 0.0),
                "turnovers_std":  std_map.get(pid, {}).get("turnovers_std", 0.0),
                "ftm_std":        std_map.get(pid, {}).get("ftm_std", 0.0),
                "oreb_std":       std_map.get(pid, {}).get("oreb_std", 0.0),
                "plus_minus_std": std_map.get(pid, {}).get("plus_minus_std", 0.0),
            })
        return result
    except Exception as exc:
        _logger.warning("get_all_players failed: %s", exc)
        return []
    finally:
        conn.close()


def get_all_teams() -> list[dict]:
    """
    Return all 30 NBA teams with pace/ORTG/DRTG from Team_Game_Stats.

    Falls back to static Teams-table columns when Team_Game_Stats is empty.
    Each dict mirrors the CSV format expected by engine/projections.py:
        abbreviation, team_name, pace, ortg, drtg
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT
                t.team_id,
                t.abbreviation,
                t.team_name,
                COALESCE(AVG(tgs.pace_est), t.pace)  AS pace,
                COALESCE(AVG(tgs.ortg_est), t.ortg)  AS ortg,
                COALESCE(AVG(tgs.drtg_est), t.drtg)  AS drtg
            FROM Teams t
            LEFT JOIN Team_Game_Stats tgs ON t.team_id = tgs.team_id
            GROUP BY t.team_id
            ORDER BY t.abbreviation
            """
        ).fetchall()

        def _r(val, d=1):
            try:
                return round(float(val or 0), d)
            except (TypeError, ValueError):
                return 0.0

        return [
            {
                "team_id":      int(r["team_id"]),
                "abbreviation": r["abbreviation"] or "",
                "team_name":    r["team_name"] or "",
                "pace":         _r(r["pace"]),
                "ortg":         _r(r["ortg"]),
                "drtg":         _r(r["drtg"]),
            }
            for r in rows
        ]
    except Exception as exc:
        _logger.warning("get_all_teams failed: %s", exc)
        return []
    finally:
        conn.close()


def get_all_defense_vs_position() -> list[dict]:
    """
    Return defense-vs-position multipliers pivoted into the format that
    engine/projections.py expects (one row per team).

    Each dict has:
        abbreviation, vs_PG_pts, vs_PG_reb, vs_SG_pts, vs_SG_reb, ...
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT team_abbreviation, pos,
                   vs_pts_mult, vs_reb_mult, vs_ast_mult,
                   vs_stl_mult, vs_blk_mult, vs_3pm_mult
            FROM Defense_Vs_Position
            """
        ).fetchall()
        if not rows:
            return []

        # Pivot: group by team_abbreviation, then spread pos columns
        team_map: dict[str, dict] = {}
        for r in rows:
            abbr = r["team_abbreviation"] or ""
            if abbr not in team_map:
                team_map[abbr] = {"abbreviation": abbr}
            pos = r["pos"] or ""
            team_map[abbr][f"vs_{pos}_pts"] = float(r["vs_pts_mult"] or 1.0)
            team_map[abbr][f"vs_{pos}_reb"] = float(r["vs_reb_mult"] or 1.0)
            team_map[abbr][f"vs_{pos}_ast"] = float(r["vs_ast_mult"] or 1.0)
            team_map[abbr][f"vs_{pos}_stl"] = float(r["vs_stl_mult"] or 1.0)
            team_map[abbr][f"vs_{pos}_blk"] = float(r["vs_blk_mult"] or 1.0)
            team_map[abbr][f"vs_{pos}_3pm"] = float(r["vs_3pm_mult"] or 1.0)
        return list(team_map.values())
    except Exception as exc:
        _logger.warning("get_all_defense_vs_position failed: %s", exc)
        return []
    finally:
        conn.close()


def get_player_by_id(player_id: int) -> dict | None:
    """Return a single player dict (with averages), or None if not found."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT * FROM Players WHERE player_id = ?", (int(player_id),)
        ).fetchone()
        if row is None:
            return None
        player = dict(row)
        player.update(_compute_averages(player_id, conn))
        return player
    except Exception as exc:
        _logger.warning("get_player_by_id(%s) failed: %s", player_id, exc)
        return None
    finally:
        conn.close()


def get_player_by_name(name: str) -> dict | None:
    """
    Fuzzy match *name* against first_name + last_name.

    Returns the best match dict (with averages) or None.
    """
    if not name:
        return None
    conn = _get_conn()
    if conn is None:
        return None
    try:
        name_lower = name.strip().lower()
        rows = conn.execute(
            """
            SELECT player_id, first_name, last_name, team_id, team_abbreviation, position
            FROM Players
            """
        ).fetchall()
        if not rows:
            return None

        # Try exact match first
        for row in rows:
            full = f"{row['first_name']} {row['last_name']}".strip().lower()
            if full == name_lower:
                player = dict(row)
                player.update(_compute_averages(row["player_id"], conn))
                return player

        # Partial / fuzzy match
        best_row = None
        best_score = 0
        for row in rows:
            full = f"{row['first_name']} {row['last_name']}".strip().lower()
            # Simple overlap score
            score = 0
            for part in name_lower.split():
                if part in full:
                    score += len(part)
            if score > best_score:
                best_score = score
                best_row = row

        if best_row and best_score > 2:
            player = dict(best_row)
            player.update(_compute_averages(best_row["player_id"], conn))
            return player

        return None
    except Exception as exc:
        _logger.warning("get_player_by_name(%r) failed: %s", name, exc)
        return None
    finally:
        conn.close()


def get_player_game_logs(player_id: int, limit: int | None = None) -> list[dict]:
    """
    Return game-by-game stats for a player, ordered by date descending.

    Parameters
    ----------
    player_id : int
    limit : int | None
        If given, only the most recent *limit* games are returned.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        base_query = """
            SELECT
                g.game_date,
                g.matchup,
                l.pts,
                l.reb,
                l.ast,
                l.stl,
                l.blk,
                l.tov,
                l.min,
                l.fgm,
                l.fga,
                l.fg_pct,
                l.fg3m,
                l.fg3a,
                l.fg3_pct,
                l.ftm,
                l.fta,
                l.ft_pct,
                l.oreb,
                l.dreb,
                l.pf,
                l.plus_minus,
                l.wl
            FROM Player_Game_Logs l
            JOIN Games g ON l.game_id = g.game_id
            WHERE l.player_id = ?
            ORDER BY g.game_date DESC
        """
        if limit is not None and limit > 0:
            base_query += f" LIMIT {int(limit)}"

        rows = conn.execute(base_query, (int(player_id),)).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_player_game_logs(%s) failed: %s", player_id, exc)
        return []
    finally:
        conn.close()


def get_player_last_n(player_id: int, n: int = 5) -> dict:
    """
    Return the last *n* games plus their averages.

    Returns
    -------
    dict with keys:
        games (list[dict]), averages (dict with ppg/rpg/apg/spg/bpg/topg/mpg)
    """
    logs = get_player_game_logs(player_id, limit=n)
    if not logs:
        return {"games": [], "averages": {}}

    def _avg(key: str) -> float:
        vals = [float(g.get(key, 0) or 0) for g in logs]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    def _avg_min() -> float:
        total = 0.0
        for g in logs:
            m = g.get("min", "0:00") or "0:00"
            try:
                if ":" in str(m):
                    parts = str(m).split(":")
                    total += float(parts[0]) + float(parts[1]) / 60.0
                else:
                    total += float(m)
            except (ValueError, TypeError):
                pass
        return round(total / len(logs), 1) if logs else 0.0

    averages = {
        "ppg":  _avg("pts"),
        "rpg":  _avg("reb"),
        "apg":  _avg("ast"),
        "spg":  _avg("stl"),
        "bpg":  _avg("blk"),
        "topg": _avg("tov"),
        "mpg":  _avg_min(),
    }
    return {"games": logs, "averages": averages}


def get_todays_games() -> list[dict]:
    """
    Return tonight's games from the Games table.

    Falls back to nba_api.stats.endpoints.ScoreboardV2 if no games
    are found for today's date in the DB.
    """
    today = datetime.date.today().strftime("%Y-%m-%d")

    conn = _get_conn()
    db_games: list[dict] = []
    if conn is not None:
        try:
            rows = conn.execute(
                """SELECT game_id, game_date, matchup, home_score, away_score
                   FROM Games WHERE game_date = ?""",
                (today,),
            ).fetchall()
            db_games = _rows_to_dicts(rows)
        except Exception:
            # home_score/away_score may not exist in old DBs — fall back to basic columns
            try:
                rows = conn.execute(
                    "SELECT game_id, game_date, matchup FROM Games WHERE game_date = ?",
                    (today,),
                ).fetchall()
                db_games = _rows_to_dicts(rows)
            except Exception as exc:
                _logger.warning("get_todays_games DB query failed: %s", exc)
        finally:
            conn.close()

    if db_games:
        return db_games

    # Fallback: live nba_api call
    try:
        from nba_api.stats.endpoints import ScoreboardV2
        import time
        time.sleep(0.5)
        sb = ScoreboardV2(game_date=today, timeout=15)
        df = sb.get_data_frames()[0]
        games = []
        for _, row in df.iterrows():
            games.append({
                "game_id":   str(row.get("GAME_ID", "")),
                "game_date": today,
                "matchup":   f"{row.get('VISITOR_TEAM_ABBREVIATION','')} vs {row.get('HOME_TEAM_ABBREVIATION','')}",
                "home_team": str(row.get("HOME_TEAM_ABBREVIATION", "")),
                "away_team": str(row.get("VISITOR_TEAM_ABBREVIATION", "")),
            })
        return games
    except Exception as exc:
        _logger.warning("get_todays_games fallback (nba_api) failed: %s", exc)
        return []


def get_players_for_game(game_id: str) -> list[dict]:
    """Return all players who have logs for a given game."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT p.player_id, p.first_name, p.last_name,
                   p.team_id, p.team_abbreviation,
                   l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min,
                   l.fgm, l.fga, l.fg_pct,
                   l.fg3m, l.fg3a, l.fg3_pct,
                   l.ftm, l.fta, l.ft_pct,
                   l.oreb, l.dreb, l.pf, l.plus_minus, l.wl
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE l.game_id = ?
            """,
            (game_id,),
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_players_for_game(%r) failed: %s", game_id, exc)
        return []
    finally:
        conn.close()


def get_team_stats(team_id: int) -> dict:
    """
    Return aggregate offensive/defensive stats for a team computed
    from game logs.

    Returns dict with: team_id, gp, ppg, rpg, apg, spg, bpg, topg,
                       fg3_avg, ftm_avg, ft_pct_avg, fgm_avg, fga_avg, fg_pct_avg
    """
    conn = _get_conn()
    if conn is None:
        return {"team_id": team_id}
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(DISTINCT l.game_id) AS gp,
                AVG(l.pts)  AS ppg,
                AVG(l.reb)  AS rpg,
                AVG(l.ast)  AS apg,
                AVG(l.stl)  AS spg,
                AVG(l.blk)  AS bpg,
                AVG(l.tov)  AS topg
            FROM Player_Game_Logs l
            JOIN Players p ON l.player_id = p.player_id
            WHERE p.team_id = ?
            """,
            (int(team_id),),
        ).fetchone()

        def _r(val, d=1):
            try:
                return round(float(val or 0), d)
            except (TypeError, ValueError):
                return 0.0

        if row is None:
            return {"team_id": team_id, "gp": 0}

        result: dict = {
            "team_id": team_id,
            "gp":   int(row["gp"] or 0),
            "ppg":  _r(row["ppg"]),
            "rpg":  _r(row["rpg"]),
            "apg":  _r(row["apg"]),
            "spg":  _r(row["spg"]),
            "bpg":  _r(row["bpg"]),
            "topg": _r(row["topg"]),
        }

        # Extended shooting stats — gracefully skip if columns don't exist
        try:
            ext = conn.execute(
                """
                SELECT
                    AVG(l.fg3m)   AS fg3_avg,
                    AVG(l.ftm)    AS ftm_avg,
                    AVG(l.ft_pct) AS ft_pct_avg,
                    AVG(l.fgm)    AS fgm_avg,
                    AVG(l.fga)    AS fga_avg,
                    AVG(l.fg_pct) AS fg_pct_avg
                FROM Player_Game_Logs l
                JOIN Players p ON l.player_id = p.player_id
                WHERE p.team_id = ?
                """,
                (int(team_id),),
            ).fetchone()
            result.update({
                "fg3_avg":    _r(ext["fg3_avg"]),
                "ftm_avg":    _r(ext["ftm_avg"]),
                "ft_pct_avg": _r(ext["ft_pct_avg"], 3),
                "fgm_avg":    _r(ext["fgm_avg"]),
                "fga_avg":    _r(ext["fga_avg"]),
                "fg_pct_avg": _r(ext["fg_pct_avg"], 3),
            })
        except Exception:
            result.update({
                "fg3_avg": 0.0, "ftm_avg": 0.0, "ft_pct_avg": 0.0,
                "fgm_avg": 0.0, "fga_avg": 0.0, "fg_pct_avg": 0.0,
            })

        return result
    except Exception as exc:
        _logger.warning("get_team_stats(%s) failed: %s", team_id, exc)
        return {"team_id": team_id}
    finally:
        conn.close()


def refresh_data() -> dict:
    """
    Run the incremental data updater to pull new games since the last
    stored date.

    Returns dict with: new_games, new_logs, new_players
    """
    try:
        from etl.data_updater import run_update
        result = run_update()
        # etl.data_updater.run_update() returns an int (new log count).
        # Wrap it in the dict format callers expect.  Also query actual
        # game counts so the UI can report them accurately.
        if isinstance(result, int):
            new_logs = result
            conn = _get_conn()
            new_games = 0
            if conn is not None:
                try:
                    new_games = conn.execute(
                        "SELECT COUNT(*) FROM Games"
                    ).fetchone()[0]
                except Exception:
                    pass
                finally:
                    conn.close()
            return {
                "new_games": new_games,
                "new_logs": new_logs,
                "new_players": 0,
            }
        return result
    except Exception as exc:
        _logger.error("refresh_data failed: %s", exc)
        return {"new_games": 0, "new_logs": 0, "new_players": 0, "error": str(exc)}


def get_db_counts() -> dict:
    """Return row counts for each table — useful for status display."""
    conn = _get_conn()
    if conn is None:
        return {"players": 0, "games": 0, "logs": 0}
    # Table names are hardcoded constants — not user input — but use explicit
    # per-query strings (no interpolation) to satisfy static-analysis tooling.
    _table_queries: list[tuple[str, str]] = [
        ("players", "SELECT COUNT(*) FROM Players"),
        ("games",   "SELECT COUNT(*) FROM Games"),
        ("logs",    "SELECT COUNT(*) FROM Player_Game_Logs"),
    ]
    try:
        counts: dict = {}
        for key, sql in _table_queries:
            try:
                counts[key] = conn.execute(sql).fetchone()[0]
            except Exception:
                counts[key] = 0
        return counts
    finally:
        conn.close()


# ── Standings ─────────────────────────────────────────────────────────────────


def get_standings() -> list[dict]:
    """
    Read current NBA standings from the Standings table.

    Returns a list of dicts with keys: team_abbreviation, conference,
    conference_rank, wins, losses, win_pct, streak, last_10.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT t.abbreviation AS team_abbreviation,
                   s.conference,
                   s.playoff_rank AS conference_rank,
                   s.wins,
                   s.losses,
                   s.win_pct,
                   s.str_current_streak AS streak,
                   s.l10 AS last_10
            FROM Standings s
            JOIN Teams t ON t.team_id = s.team_id
            """
        ).fetchall()
        return _rows_to_dicts(rows)
    except Exception as exc:
        _logger.warning("get_standings failed: %s", exc)
        return []
    finally:
        conn.close()


# ── Roster helpers ────────────────────────────────────────────────────────────


def get_rosters_for_teams(team_abbrevs: list[str]) -> dict[str, list[dict]]:
    """
    Return rosters from Team_Roster + Players for the given team abbreviations.

    Returns ``{team_abbrev: [player_dict, ...]}``.
    Each player_dict has: player_id, first_name, last_name,
    team_abbreviation, position.
    """
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        result: dict[str, list[dict]] = {}
        for abbrev in (team_abbrevs or []):
            rows = conn.execute(
                """
                SELECT p.player_id, p.first_name, p.last_name,
                       p.team_abbreviation, p.position
                FROM Team_Roster tr
                JOIN Players p ON p.player_id = tr.player_id
                JOIN Teams   t ON t.team_id   = tr.team_id
                WHERE t.abbreviation = ?
                """,
                (abbrev.upper(),),
            ).fetchall()
            result[abbrev.upper()] = _rows_to_dicts(rows)
        return result
    except Exception as exc:
        _logger.warning("get_rosters_for_teams failed: %s", exc)
        return {}
    finally:
        conn.close()


def get_players_for_teams(team_abbrevs: list[str]) -> list[dict]:
    """
    Return players (with season averages) filtered to only the given teams.

    Same schema as :func:`get_all_players` but limited to players whose
    ``team_abbreviation`` is in *team_abbrevs*.
    """
    all_players = get_all_players()
    if not all_players:
        return []
    if not team_abbrevs:
        return []
    upper_abbrevs = {a.upper() for a in team_abbrevs}
    return [
        p for p in all_players
        if (p.get("team_abbreviation") or "").upper() in upper_abbrevs
    ]
