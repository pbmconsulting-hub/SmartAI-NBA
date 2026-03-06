# ============================================================
# FILE: tracking/database.py
# PURPOSE: SQLite database wrapper for storing bet history
#          and tracking model performance over time.
# CONNECTS TO: bet_tracker.py (uses these functions)
# CONCEPTS COVERED: SQLite, database CRUD operations,
#                   context managers, SQL queries
# ============================================================

# Standard library imports only
import sqlite3    # Built-in SQLite database (no install needed!)
import os         # For file path operations
from pathlib import Path  # Modern file path handling


# ============================================================
# SECTION: Database Configuration
# ============================================================

# Path to the SQLite database file
# It will be created automatically on first run
DB_DIRECTORY = Path(__file__).parent.parent / "db"
DB_FILE_PATH = DB_DIRECTORY / "smartai_nba.db"

# SQL to create the bets table (runs once when app starts)
# BEGINNER NOTE: SQL is a language for managing databases.
# CREATE TABLE IF NOT EXISTS = only create if it doesn't exist yet
CREATE_BETS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bets (
    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_date TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT,
    stat_type TEXT NOT NULL,
    prop_line REAL NOT NULL,
    direction TEXT NOT NULL,
    platform TEXT,
    confidence_score REAL,
    probability_over REAL,
    edge_percentage REAL,
    tier TEXT,
    entry_type TEXT,
    entry_fee REAL,
    result TEXT,
    actual_value REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the entries table (for tracking parlay entries)
CREATE_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    platform TEXT NOT NULL,
    entry_type TEXT,
    entry_fee REAL,
    expected_value REAL,
    result TEXT,
    payout REAL,
    pick_count INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# ============================================================
# END SECTION: Database Configuration
# ============================================================


# ============================================================
# SECTION: Database Initialization
# ============================================================

def initialize_database():
    """
    Create the database and tables if they don't exist.

    Call this once when the app starts. It's safe to call
    multiple times — CREATE TABLE IF NOT EXISTS won't
    overwrite existing tables.

    Returns:
        bool: True if successful, False if error occurred
    """
    # Make sure the db directory exists
    # exist_ok=True means don't error if it already exists
    DB_DIRECTORY.mkdir(parents=True, exist_ok=True)

    try:
        # Connect to the SQLite database file
        # BEGINNER NOTE: sqlite3.connect() opens (or creates) the DB file
        # 'with' statement ensures the connection is properly closed
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            cursor = connection.cursor()  # A cursor lets us run SQL commands

            # Create the tables
            cursor.execute(CREATE_BETS_TABLE_SQL)
            cursor.execute(CREATE_ENTRIES_TABLE_SQL)

            # Save the changes
            connection.commit()

        return True

    except sqlite3.Error as database_error:
        print(f"Database initialization error: {database_error}")
        return False


def get_database_connection():
    """
    Get a connection to the SQLite database.

    Returns:
        sqlite3.Connection: Active database connection
        Call .close() when done, or use 'with' statement.
    """
    # Ensure database exists before connecting
    initialize_database()

    # Connect with row_factory so results come back as dictionaries
    # BEGINNER NOTE: row_factory makes results easier to work with —
    # instead of tuples (24, 'LeBron') you get {'points': 24, 'name': 'LeBron'}
    connection = sqlite3.connect(str(DB_FILE_PATH))
    connection.row_factory = sqlite3.Row  # Rows behave like dicts

    return connection

# ============================================================
# END SECTION: Database Initialization
# ============================================================


# ============================================================
# SECTION: Database CRUD Operations
# CRUD = Create, Read, Update, Delete
# ============================================================

def insert_bet(bet_data):
    """
    Save a new bet to the database.

    Args:
        bet_data (dict): Bet information with keys:
            bet_date, player_name, team, stat_type, prop_line,
            direction, platform, confidence_score, probability_over,
            edge_percentage, tier, entry_type, entry_fee, notes

    Returns:
        int or None: The new bet's ID, or None if error
    """
    # SQL INSERT statement — ? placeholders for safety
    # BEGINNER NOTE: Never put values directly in SQL strings!
    # Use ? placeholders to prevent "SQL injection" attacks
    insert_sql = """
    INSERT INTO bets (
        bet_date, player_name, team, stat_type, prop_line,
        direction, platform, confidence_score, probability_over,
        edge_percentage, tier, entry_type, entry_fee, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    values = (
        bet_data.get("bet_date", ""),
        bet_data.get("player_name", ""),
        bet_data.get("team", ""),
        bet_data.get("stat_type", ""),
        bet_data.get("prop_line", 0.0),
        bet_data.get("direction", "OVER"),
        bet_data.get("platform", ""),
        bet_data.get("confidence_score", 0.0),
        bet_data.get("probability_over", 0.5),
        bet_data.get("edge_percentage", 0.0),
        bet_data.get("tier", "Bronze"),
        bet_data.get("entry_type", ""),
        bet_data.get("entry_fee", 0.0),
        bet_data.get("notes", ""),
    )

    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            cursor = connection.cursor()
            cursor.execute(insert_sql, values)
            connection.commit()
            return cursor.lastrowid  # Return the new row's ID

    except sqlite3.Error as database_error:
        print(f"Error inserting bet: {database_error}")
        return None


def update_bet_result(bet_id, result, actual_value):
    """
    Update a bet with its result after the game.

    Args:
        bet_id (int): The bet's database ID
        result (str): 'WIN', 'LOSS', or 'PUSH'
        actual_value (float): What the player actually scored

    Returns:
        bool: True if updated successfully
    """
    update_sql = """
    UPDATE bets
    SET result = ?, actual_value = ?
    WHERE bet_id = ?
    """

    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            cursor = connection.cursor()
            cursor.execute(update_sql, (result, actual_value, bet_id))
            connection.commit()
            return cursor.rowcount > 0  # True if a row was updated

    except sqlite3.Error as database_error:
        print(f"Error updating bet result: {database_error}")
        return False


def load_all_bets(limit=200):
    """
    Load recent bets from the database.

    Args:
        limit (int): Maximum number of bets to return

    Returns:
        list of dict: Bet rows as dictionaries
    """
    select_sql = """
    SELECT * FROM bets
    ORDER BY created_at DESC
    LIMIT ?
    """

    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(select_sql, (limit,))
            rows = cursor.fetchall()
            # Convert sqlite3.Row objects to regular dicts
            return [dict(row) for row in rows]

    except sqlite3.Error as database_error:
        print(f"Error loading bets: {database_error}")
        return []


def get_performance_summary():
    """
    Get win/loss statistics from the database.

    Returns:
        dict: Performance stats including:
            'total_bets', 'wins', 'losses', 'pushes',
            'win_rate', 'roi'
    """
    # SQL aggregation query to count outcomes
    summary_sql = """
    SELECT
        COUNT(*) as total_bets,
        SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN result = 'PUSH' THEN 1 ELSE 0 END) as pushes,
        AVG(CASE WHEN result IS NOT NULL AND result != '' THEN
            CASE WHEN result = 'WIN' THEN 1.0 ELSE 0.0 END
        END) as win_rate
    FROM bets
    WHERE result IS NOT NULL AND result != ''
    """

    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(summary_sql)
            row = cursor.fetchone()

            if row:
                total = row["total_bets"] or 0
                wins = row["wins"] or 0
                losses = row["losses"] or 0
                pushes = row["pushes"] or 0
                win_rate = row["win_rate"] or 0.0

                return {
                    "total_bets": total,
                    "wins": wins,
                    "losses": losses,
                    "pushes": pushes,
                    "win_rate": round(win_rate * 100, 1),
                }

    except sqlite3.Error as database_error:
        print(f"Error getting performance summary: {database_error}")

    return {
        "total_bets": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "win_rate": 0.0,
    }

# ============================================================
# END SECTION: Database CRUD Operations
# ============================================================
