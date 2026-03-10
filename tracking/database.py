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
    auto_logged INTEGER DEFAULT 0,
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

# SQL to create the prediction_history table for model calibration (W7)
# Tracks each prediction made and whether it was correct.
# Used to compute calibration adjustments that self-correct model overconfidence.
CREATE_PREDICTION_HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prediction_history (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_date TEXT NOT NULL,
    player_name TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    prop_line REAL NOT NULL,
    direction TEXT NOT NULL,
    confidence_score REAL,
    probability_predicted REAL,
    was_correct INTEGER,
    actual_value REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# SQL to create the daily_snapshots table for per-day performance tracking.
# Stores aggregated bet outcomes, win rates, and breakdowns per day.
CREATE_DAILY_SNAPSHOTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    total_picks INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    pushes INTEGER DEFAULT 0,
    pending INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.0,
    platform_breakdown TEXT,
    tier_breakdown TEXT,
    stat_type_breakdown TEXT,
    best_pick TEXT,
    worst_pick TEXT,
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
            cursor.execute(CREATE_PREDICTION_HISTORY_TABLE_SQL)  # W7: calibration
            cursor.execute(CREATE_DAILY_SNAPSHOTS_TABLE_SQL)      # daily performance tracking

            # ── Schema migrations for existing databases ──────────────
            # Add auto_logged column if it doesn't exist yet
            # (ALTER TABLE is idempotent-safe via the try/except)
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN auto_logged INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists — safe to ignore

            # Ensure actual_value column exists (older schema may not have it)
            try:
                cursor.execute(
                    "ALTER TABLE bets ADD COLUMN actual_value REAL"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists — safe to ignore

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
            edge_percentage, tier, entry_type, entry_fee, notes,
            auto_logged (optional, default 0)

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
        edge_percentage, tier, entry_type, entry_fee, notes, auto_logged
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        int(bet_data.get("auto_logged", 0)),
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
# SECTION: Prediction History & Calibration (W7)
# Store prediction outcomes and compute calibration adjustments
# so the model can self-correct systematic over/underconfidence.
# ============================================================

def insert_prediction(prediction_data):
    """
    Save a model prediction to the history table. (W7)

    Call this when a bet is placed. Later, update with
    `update_prediction_outcome()` when the result is known.

    Args:
        prediction_data (dict): Prediction data with keys:
            prediction_date (str), player_name (str), stat_type (str),
            prop_line (float), direction (str), confidence_score (float),
            probability_predicted (float), notes (str, optional)

    Returns:
        int or None: The new prediction's ID, or None if error
    """
    initialize_database()  # Ensure prediction_history table exists
    insert_sql = """
    INSERT INTO prediction_history (
        prediction_date, player_name, stat_type, prop_line,
        direction, confidence_score, probability_predicted, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        prediction_data.get("prediction_date", ""),
        prediction_data.get("player_name", ""),
        prediction_data.get("stat_type", ""),
        prediction_data.get("prop_line", 0.0),
        prediction_data.get("direction", "OVER"),
        prediction_data.get("confidence_score", 0.0),
        prediction_data.get("probability_predicted", 0.5),
        prediction_data.get("notes", ""),
    )
    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            cursor = connection.cursor()
            cursor.execute(insert_sql, values)
            connection.commit()
            return cursor.lastrowid
    except sqlite3.Error as database_error:
        print(f"Error inserting prediction: {database_error}")
        return None


def update_prediction_outcome(prediction_id, was_correct, actual_value):
    """
    Record the actual outcome for a prediction. (W7)

    Args:
        prediction_id (int): The prediction's database ID
        was_correct (bool): True if the prediction was correct
        actual_value (float): The actual stat value achieved

    Returns:
        bool: True if updated successfully
    """
    update_sql = """
    UPDATE prediction_history
    SET was_correct = ?, actual_value = ?
    WHERE prediction_id = ?
    """
    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            cursor = connection.cursor()
            cursor.execute(update_sql, (1 if was_correct else 0, actual_value, prediction_id))
            connection.commit()
            return True
    except sqlite3.Error as database_error:
        print(f"Error updating prediction outcome: {database_error}")
        return False


def get_calibration_adjustment(stat_type=None, min_samples=20):
    """
    Compute a calibration adjustment for the confidence model. (W7)

    Compares the model's predicted probability to the actual
    hit rate. If the model says 62% but only 58% of picks hit,
    the calibration adjustment is +4 (subtract 4 from displayed score).

    Args:
        stat_type (str or None): Compute calibration for a specific
            stat type, or overall if None.
        min_samples (int): Minimum number of graded predictions needed
            before returning a non-zero adjustment (default: 20).
            With fewer samples, the adjustment is unreliable.

    Returns:
        float: Calibration adjustment in confidence points.
            Positive = model overestimates (subtract from score).
            Negative = model underestimates (add to score).
            Returns 0.0 if insufficient data.

    Example:
        Model predicts avg 62% probability, actual hit rate is 57%
        → calibration_adjustment = +5.0 points (reduce all scores by 5)
    """
    initialize_database()  # Ensure prediction_history table exists
    if stat_type:
        query_sql = """
        SELECT
            AVG(probability_predicted) as avg_predicted_prob,
            AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
            COUNT(*) as sample_count
        FROM prediction_history
        WHERE was_correct IS NOT NULL AND stat_type = ?
        """
        params = (stat_type,)
    else:
        query_sql = """
        SELECT
            AVG(probability_predicted) as avg_predicted_prob,
            AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
            COUNT(*) as sample_count
        FROM prediction_history
        WHERE was_correct IS NOT NULL
        """
        params = ()

    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(query_sql, params)
            row = cursor.fetchone()

            if row and row["sample_count"] >= min_samples:
                avg_predicted = row["avg_predicted_prob"] or 0.5
                actual_rate = row["actual_hit_rate"] or 0.5
                # Overconfidence = model probability higher than actual hit rate
                # Convert probability gap to confidence score adjustment
                # (1% probability gap ≈ 2 confidence score points)
                prob_gap_pct = (avg_predicted - actual_rate) * 100.0
                adjustment = prob_gap_pct * 2.0  # Scale to confidence score points
                # Cap adjustment to ±15 points to avoid extreme corrections
                return round(max(-15.0, min(15.0, adjustment)), 1)

    except sqlite3.Error as database_error:
        print(f"Error computing calibration: {database_error}")

    return 0.0  # No adjustment if insufficient data


def get_calibration_report():
    """
    Build a human-readable calibration report for the Model Health page. (W7)

    Returns:
        dict: {
            'overall': dict with avg_predicted, actual_hit_rate, sample_count, adjustment
            'by_stat': dict {stat_type: same dict}
            'summary_text': str (human-readable summary)
        }
    """
    initialize_database()  # Ensure prediction_history table exists
    report = {"overall": {}, "by_stat": {}, "summary_text": ""}

    query_overall = """
    SELECT
        stat_type,
        AVG(probability_predicted) as avg_predicted_prob,
        AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
        COUNT(*) as sample_count
    FROM prediction_history
    WHERE was_correct IS NOT NULL
    GROUP BY stat_type
    ORDER BY sample_count DESC
    """

    query_all = """
    SELECT
        AVG(probability_predicted) as avg_predicted_prob,
        AVG(CAST(was_correct AS REAL)) as actual_hit_rate,
        COUNT(*) as sample_count
    FROM prediction_history
    WHERE was_correct IS NOT NULL
    """

    try:
        with sqlite3.connect(str(DB_FILE_PATH)) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()

            # Overall calibration
            cursor.execute(query_all)
            row = cursor.fetchone()
            if row and row["sample_count"]:
                avg_p = row["avg_predicted_prob"] or 0.5
                actual = row["actual_hit_rate"] or 0.5
                report["overall"] = {
                    "avg_predicted_prob": round(avg_p * 100, 1),
                    "actual_hit_rate": round(actual * 100, 1),
                    "sample_count": row["sample_count"],
                    "calibration_adjustment": round((avg_p - actual) * 100 * 2, 1),
                }
                cal_dir = "overconfident" if avg_p > actual else "underconfident"
                report["summary_text"] = (
                    f"Model is {cal_dir}: predicts {avg_p*100:.1f}% avg but "
                    f"hits {actual*100:.1f}% ({row['sample_count']} graded predictions)"
                )

            # By stat type
            cursor.execute(query_overall)
            rows = cursor.fetchall()
            for r in rows:
                if r["sample_count"] and r["sample_count"] >= 5:
                    avg_p = r["avg_predicted_prob"] or 0.5
                    actual = r["actual_hit_rate"] or 0.5
                    report["by_stat"][r["stat_type"]] = {
                        "avg_predicted_prob": round(avg_p * 100, 1),
                        "actual_hit_rate": round(actual * 100, 1),
                        "sample_count": r["sample_count"],
                        "calibration_adjustment": round((avg_p - actual) * 100 * 2, 1),
                    }

    except sqlite3.Error as database_error:
        print(f"Error building calibration report: {database_error}")

    return report

# ============================================================
# END SECTION: Prediction History & Calibration
# ============================================================

# ============================================================
# SECTION: Daily Snapshots
# ============================================================

def save_daily_snapshot(date_str=None):
    """
    Aggregate all bets for *date_str* and write/update the daily_snapshots row.

    Args:
        date_str (str | None): ISO date string (YYYY-MM-DD). Defaults to today.

    Returns:
        bool: True on success, False on error.
    """
    import json
    import datetime as _dt

    if date_str is None:
        date_str = _dt.date.today().isoformat()

    try:
        conn = get_database_connection()
        cursor = conn.cursor()

        # Fetch all bets for that date
        cursor.execute(
            "SELECT * FROM bets WHERE bet_date = ?",
            (date_str,),
        )
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        bets = [dict(zip(cols, row)) for row in rows]

        total = len(bets)
        wins = sum(1 for b in bets if b.get("result") == "WIN")
        losses = sum(1 for b in bets if b.get("result") == "LOSS")
        pushes = sum(1 for b in bets if b.get("result") == "PUSH")
        pending = sum(1 for b in bets if not b.get("result"))
        win_rate = round(wins / max(wins + losses, 1) * 100, 2)

        # Platform breakdown
        platform_breakdown: dict = {}
        for b in bets:
            p = b.get("platform") or "Unknown"
            if p not in platform_breakdown:
                platform_breakdown[p] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            res = b.get("result")
            if res == "WIN":
                platform_breakdown[p]["wins"] += 1
            elif res == "LOSS":
                platform_breakdown[p]["losses"] += 1
            elif res == "PUSH":
                platform_breakdown[p]["pushes"] += 1
            else:
                platform_breakdown[p]["pending"] += 1

        # Tier breakdown
        tier_breakdown: dict = {}
        for b in bets:
            t = b.get("tier") or "Unknown"
            if t not in tier_breakdown:
                tier_breakdown[t] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            res = b.get("result")
            if res == "WIN":
                tier_breakdown[t]["wins"] += 1
            elif res == "LOSS":
                tier_breakdown[t]["losses"] += 1
            elif res == "PUSH":
                tier_breakdown[t]["pushes"] += 1
            else:
                tier_breakdown[t]["pending"] += 1

        # Stat-type breakdown
        stat_type_breakdown: dict = {}
        for b in bets:
            s = b.get("stat_type") or "Unknown"
            if s not in stat_type_breakdown:
                stat_type_breakdown[s] = {"wins": 0, "losses": 0, "pushes": 0, "pending": 0}
            res = b.get("result")
            if res == "WIN":
                stat_type_breakdown[s]["wins"] += 1
            elif res == "LOSS":
                stat_type_breakdown[s]["losses"] += 1
            elif res == "PUSH":
                stat_type_breakdown[s]["pushes"] += 1
            else:
                stat_type_breakdown[s]["pending"] += 1

        # Best / worst pick (by edge_percentage, resolved only)
        resolved = [b for b in bets if b.get("result") in ("WIN", "LOSS")]
        best_pick = ""
        worst_pick = ""
        if resolved:
            best = max(resolved, key=lambda b: float(b.get("edge_percentage") or 0))
            worst = min(resolved, key=lambda b: float(b.get("edge_percentage") or 0))
            best_pick = json.dumps({
                "player": best.get("player_name", ""),
                "stat": best.get("stat_type", ""),
                "edge": best.get("edge_percentage", 0),
                "result": best.get("result", ""),
            })
            worst_pick = json.dumps({
                "player": worst.get("player_name", ""),
                "stat": worst.get("stat_type", ""),
                "edge": worst.get("edge_percentage", 0),
                "result": worst.get("result", ""),
            })

        cursor.execute(
            """
            INSERT INTO daily_snapshots
                (snapshot_date, total_picks, wins, losses, pushes, pending,
                 win_rate, platform_breakdown, tier_breakdown, stat_type_breakdown,
                 best_pick, worst_pick)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date) DO UPDATE SET
                total_picks        = excluded.total_picks,
                wins               = excluded.wins,
                losses             = excluded.losses,
                pushes             = excluded.pushes,
                pending            = excluded.pending,
                win_rate           = excluded.win_rate,
                platform_breakdown = excluded.platform_breakdown,
                tier_breakdown     = excluded.tier_breakdown,
                stat_type_breakdown = excluded.stat_type_breakdown,
                best_pick          = excluded.best_pick,
                worst_pick         = excluded.worst_pick
            """,
            (
                date_str,
                total,
                wins,
                losses,
                pushes,
                pending,
                win_rate,
                json.dumps(platform_breakdown),
                json.dumps(tier_breakdown),
                json.dumps(stat_type_breakdown),
                best_pick,
                worst_pick,
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        print(f"[database] save_daily_snapshot error: {exc}")
        return False


def load_daily_snapshots(days=14):
    """Return the last *days* rows from daily_snapshots, newest first.

    Returns:
        list[dict]
    """
    import json

    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM daily_snapshots
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (days,),
        )
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        conn.close()
        snapshots = []
        for row in rows:
            s = dict(zip(cols, row))
            for field in ("platform_breakdown", "tier_breakdown", "stat_type_breakdown"):
                try:
                    s[field] = json.loads(s.get(field) or "{}")
                except Exception:
                    s[field] = {}
            for field in ("best_pick", "worst_pick"):
                try:
                    s[field] = json.loads(s.get(field) or "{}")
                except Exception:
                    s[field] = {}
            snapshots.append(s)
        return snapshots
    except Exception as exc:
        print(f"[database] load_daily_snapshots error: {exc}")
        return []


def purge_old_snapshots(days=30):
    """Delete snapshots older than *days* days.

    Returns:
        int: Number of rows deleted.
    """
    import datetime as _dt

    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM daily_snapshots WHERE snapshot_date < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted
    except Exception as exc:
        print(f"[database] purge_old_snapshots error: {exc}")
        return 0


def get_rolling_stats(days=14):
    """Compute rolling win rate, current streak, best/worst day from snapshots.

    Returns:
        dict with keys: total_bets, total_wins, total_losses, total_pushes,
                        win_rate, streak (int, positive=win streak, negative=loss streak),
                        best_day (dict), worst_day (dict), snapshots (list)
    """
    snapshots = load_daily_snapshots(days)
    if not snapshots:
        return {
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "total_pushes": 0,
            "win_rate": 0.0,
            "streak": 0,
            "best_day": {},
            "worst_day": {},
            "snapshots": [],
        }

    total_bets = sum(s.get("total_picks", 0) for s in snapshots)
    total_wins = sum(s.get("wins", 0) for s in snapshots)
    total_losses = sum(s.get("losses", 0) for s in snapshots)
    total_pushes = sum(s.get("pushes", 0) for s in snapshots)
    win_rate = round(total_wins / max(total_wins + total_losses, 1) * 100, 1)

    # Current streak: walk from most recent snapshot backward
    streak = 0
    for snap in snapshots:
        w = snap.get("wins", 0)
        l = snap.get("losses", 0)
        if w + l == 0:
            continue
        day_wr = w / (w + l)
        if streak == 0:
            streak = 1 if day_wr >= 0.5 else -1
        elif streak > 0 and day_wr >= 0.5:
            streak += 1
        elif streak < 0 and day_wr < 0.5:
            streak -= 1
        else:
            break

    resolved = [s for s in snapshots if (s.get("wins", 0) + s.get("losses", 0)) > 0]
    best_day = max(resolved, key=lambda s: s.get("win_rate", 0)) if resolved else {}
    worst_day = min(resolved, key=lambda s: s.get("win_rate", 0)) if resolved else {}

    return {
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_pushes": total_pushes,
        "win_rate": win_rate,
        "streak": streak,
        "best_day": best_day,
        "worst_day": worst_day,
        "snapshots": snapshots,
    }

# ============================================================
# END SECTION: Daily Snapshots
# ============================================================

# ============================================================
# END SECTION: Database CRUD Operations
# ============================================================
