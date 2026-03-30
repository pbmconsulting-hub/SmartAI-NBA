"""
scripts/setup_db.py
====================
Creates (or verifies) the SQLite schema for SmartAI-NBA's ETL database.

Database path: db/etl_data.db (relative to repo root)

Tables created:
  - Players          — one row per NBA player
  - Games            — one row per NBA game
  - Player_Game_Logs — one row per player per game (stats)

Usage:
    python scripts/setup_db.py
"""

import logging
import os
import sqlite3
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "db" / "etl_data.db"

# ── Schema ─────────────────────────────────────────────────────────────────────

_DDL_PLAYERS = """
CREATE TABLE IF NOT EXISTS Players (
    player_id       INTEGER PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    team_id         INTEGER,
    team_abbreviation TEXT
);
"""

_DDL_GAMES = """
CREATE TABLE IF NOT EXISTS Games (
    game_id   TEXT PRIMARY KEY,
    game_date TEXT NOT NULL,
    matchup   TEXT
);
"""

_DDL_PLAYER_GAME_LOGS = """
CREATE TABLE IF NOT EXISTS Player_Game_Logs (
    player_id INTEGER NOT NULL,
    game_id   TEXT    NOT NULL,
    pts       INTEGER DEFAULT 0,
    reb       INTEGER DEFAULT 0,
    ast       INTEGER DEFAULT 0,
    blk       INTEGER DEFAULT 0,
    stl       INTEGER DEFAULT 0,
    tov       INTEGER DEFAULT 0,
    min       TEXT    DEFAULT '0:00',
    PRIMARY KEY (player_id, game_id),
    FOREIGN KEY (player_id) REFERENCES Players(player_id),
    FOREIGN KEY (game_id)   REFERENCES Games(game_id)
);
"""

_DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pgl_player ON Player_Game_Logs(player_id);",
    "CREATE INDEX IF NOT EXISTS idx_pgl_game   ON Player_Game_Logs(game_id);",
    "CREATE INDEX IF NOT EXISTS idx_games_date ON Games(game_date);",
]


def create_schema(db_path: Path = DB_PATH) -> None:
    """Create all tables and indexes.  Safe to call on an existing database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to database: %s", db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        for stmt, name in [
            (_DDL_PLAYERS,          "Players"),
            (_DDL_GAMES,            "Games"),
            (_DDL_PLAYER_GAME_LOGS, "Player_Game_Logs"),
        ]:
            logger.info("Creating table: %s", name)
            cur.executescript(stmt)

        for ddl in _DDL_INDEXES:
            cur.executescript(ddl)

        conn.commit()
        logger.info("All tables and indexes created (or already exist) successfully.")
    finally:
        conn.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    create_schema()
