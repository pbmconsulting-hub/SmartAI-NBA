"""
data/etl_data_service.py
=========================
Bridge between the ETL SQLite database (db/etl_data.db) and
SmartAI-NBA's data layer.

All functions connect to the database read-only for queries and return
plain Python dicts/lists.  No live API calls are made here — those happen
only in scripts/initial_pull.py and scripts/data_updater.py.

If the database does not exist yet (fresh install, before running
initial_pull.py), every function degrades gracefully and returns an
empty result so the rest of the app keeps working.
"""

from __future__ import annotations

import datetime
import logging
import os
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
DB_PATH = _REPO_ROOT / "db" / "etl_data.db"


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
                "spg": 0.0, "bpg": 0.0, "topg": 0.0, "mpg": 0.0}

    def _r(val, decimals: int = 1) -> float:
        try:
            return round(float(val or 0), decimals)
        except (TypeError, ValueError):
            return 0.0

    return {
        "gp":   int(row["gp"]),
        "ppg":  _r(row["ppg"]),
        "rpg":  _r(row["rpg"]),
        "apg":  _r(row["apg"]),
        "spg":  _r(row["spg"]),
        "bpg":  _r(row["bpg"]),
        "topg": _r(row["topg"]),
        "mpg":  _r(row["mpg"]),
    }


# ── Public API ─────────────────────────────────────────────────────────────────


def get_all_players() -> list[dict]:
    """
    Return all players with season averages computed from game logs.

    Each dict has:
        player_id, first_name, last_name, team_id, team_abbreviation,
        gp, ppg, rpg, apg, spg, bpg, topg, mpg
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

        result = []
        for row in rows:
            result.append({
                "player_id":         int(row["player_id"]),
                "first_name":        row["first_name"] or "",
                "last_name":         row["last_name"] or "",
                "team_id":           int(row["team_id"]) if row["team_id"] else None,
                "team_abbreviation": row["team_abbreviation"] or "",
                "gp":    int(row["gp"] or 0),
                "ppg":   _r(row["ppg"]),
                "rpg":   _r(row["rpg"]),
                "apg":   _r(row["apg"]),
                "spg":   _r(row["spg"]),
                "bpg":   _r(row["bpg"]),
                "topg":  _r(row["topg"]),
                "mpg":   _r(row["mpg"]),
            })
        return result
    except Exception as exc:
        _logger.warning("get_all_players failed: %s", exc)
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
            SELECT player_id, first_name, last_name, team_id, team_abbreviation
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
                l.min
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
                   l.pts, l.reb, l.ast, l.stl, l.blk, l.tov, l.min
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

    Returns dict with: team_id, gp, ppg, rpg, apg, spg, bpg, topg
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

        return {
            "team_id": team_id,
            "gp":   int(row["gp"] or 0),
            "ppg":  _r(row["ppg"]),
            "rpg":  _r(row["rpg"]),
            "apg":  _r(row["apg"]),
            "spg":  _r(row["spg"]),
            "bpg":  _r(row["bpg"]),
            "topg": _r(row["topg"]),
        }
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
        from scripts.data_updater import run_update
        return run_update()
    except Exception as exc:
        _logger.error("refresh_data failed: %s", exc)
        return {"new_games": 0, "new_logs": 0, "new_players": 0, "error": str(exc)}


def get_db_counts() -> dict:
    """Return row counts for each table — useful for status display."""
    conn = _get_conn()
    if conn is None:
        return {"players": 0, "games": 0, "logs": 0}
    try:
        return {
            "players": conn.execute("SELECT COUNT(*) FROM Players").fetchone()[0],
            "games":   conn.execute("SELECT COUNT(*) FROM Games").fetchone()[0],
            "logs":    conn.execute("SELECT COUNT(*) FROM Player_Game_Logs").fetchone()[0],
        }
    except Exception:
        return {"players": 0, "games": 0, "logs": 0}
    finally:
        conn.close()
