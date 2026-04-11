"""
cbs_injuries.py
---------------
ETL module for scraping the CBS Sports NBA Injury Report.

Extracts injury data from the CBS Sports injury page, transforms it by
fuzzy-matching player names to player IDs and mapping full team names to
team IDs, and loads the result into the ``Injury_Status`` table using
``upsert_dataframe()``.

Mirrors the structure of :mod:`etl.rotowire_injuries` so both sources
coexist under the ``(player_id, report_date, source)`` composite primary
key.

Exposes a single public function, :func:`sync_cbs_injuries`, which can be
called from ``data_updater.run_update()`` or run standalone.

Usage::

    from etl.cbs_injuries import sync_cbs_injuries
    rows_upserted = sync_cbs_injuries()
"""

import logging
import sqlite3
import time
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from thefuzz import process as fuzz_process

from . import setup_db
from .utils import upsert_dataframe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = setup_db.DB_PATH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CBS_INJURY_URL = "https://www.cbssports.com/nba/injuries/"

# Minimum fuzzy-match score (0–100) to accept a player name match.
_FUZZY_MATCH_THRESHOLD = 85

# Seconds to wait before each HTTP request (rate-limit).
_REQUEST_DELAY = 3.0

# Retry settings for HTTP requests.
_MAX_RETRIES = 3
_MAX_BACKOFF_DELAY = 30

# Source tag stored in the Injury_Status table.
_SOURCE = "cbssports"

# HTTP headers that mimic a browser to avoid being blocked.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# curl_cffi provides TLS browser-impersonation to bypass Cloudflare/Akamai.
try:
    from curl_cffi import requests as _curl_requests

    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _curl_requests = None  # type: ignore[assignment]
    _CURL_CFFI_AVAILABLE = False

# ---------------------------------------------------------------------------
# CBS full team name → canonical 3-letter abbreviation mapping
# ---------------------------------------------------------------------------

_CBS_TEAM_NAME_MAP: dict[str, str] = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "LA Clippers": "LAC",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "LA Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _rate_limited_sleep() -> None:
    """Sleep for :data:`_REQUEST_DELAY` seconds before each HTTP request."""
    time.sleep(_REQUEST_DELAY)


def _call_with_retries(callable_, description: str = "HTTP request"):
    """Call *callable_* up to :data:`_MAX_RETRIES` times with exponential backoff.

    Args:
        callable_: Zero-argument callable that returns a response.
        description: Human-readable label used in log messages.

    Returns:
        The response returned by *callable_* on success.

    Raises:
        Exception: The last exception raised after all retries are exhausted.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return callable_()
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                delay = min(2 ** attempt, _MAX_BACKOFF_DELAY)
                logger.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %ds …",
                    description, attempt, _MAX_RETRIES, exc, delay,
                )
                time.sleep(delay)
    logger.warning("%s failed after %d attempts.", description, _MAX_RETRIES)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def fetch_injury_page(url: str = _CBS_INJURY_URL) -> str:
    """Fetch the CBS Sports injury report page HTML.

    Uses ``curl_cffi`` with Chrome impersonation as primary (CBS has
    Cloudflare protection), falling back to plain ``requests``.

    Args:
        url: URL of the CBS Sports injury report page.

    Returns:
        Raw HTML string of the page.

    Raises:
        requests.HTTPError: If the HTTP response indicates an error.
        Exception: After :data:`_MAX_RETRIES` failed attempts.
    """
    logger.info("Fetching CBS Sports injury report from %s …", url)
    _rate_limited_sleep()

    def _fetch():
        if _CURL_CFFI_AVAILABLE:
            resp = _curl_requests.get(url, impersonate="chrome", timeout=30)
        else:
            resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp

    response = _call_with_retries(_fetch, description=f"GET {url}")
    logger.info("Fetched %d bytes from %s.", len(response.content), url)
    return response.text


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------


def parse_injury_table(html: str) -> list[dict]:
    """Parse the CBS Sports injury report HTML into a list of row dicts.

    CBS uses ``div.TeamCard`` sections with the team name in an ``<a>`` tag
    and player rows in ``<tr>``/``<td>`` within each section.  Columns are:
    player, status, injury, date.

    Args:
        html: Raw HTML string of the CBS Sports injury report page.

    Returns:
        A list of dicts with keys: ``player_name``, ``team_name``,
        ``status``, ``reason``, ``date``.  Returns an empty list if
        the page cannot be parsed.
    """
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    for team_section in soup.find_all(
        "div", class_=lambda c: c and "TeamCard" in c
    ):
        team_tag = team_section.find("a")
        team_name = team_tag.get_text(strip=True) if team_tag else "Unknown"

        for tr in team_section.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue

            player_name = cells[0].get_text(strip=True)
            status = cells[1].get_text(strip=True)
            injury = cells[2].get_text(strip=True)
            injury_date = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            if not player_name or not status:
                continue

            rows.append(
                {
                    "player_name": player_name,
                    "team_name": team_name,
                    "status": status,
                    "reason": injury,
                    "date": injury_date,
                }
            )

    logger.info("Parsed %d injury rows from CBS Sports HTML.", len(rows))
    return rows


def _normalise_team_name(raw: str) -> str:
    """Map a full CBS team name to the canonical three-letter abbreviation.

    Args:
        raw: Full team name as scraped from CBS (e.g. ``'Golden State Warriors'``).

    Returns:
        Canonical abbreviation (e.g. ``'GSW'``), or the raw string upper-cased
        if no mapping is found.
    """
    stripped = raw.strip()
    if stripped in _CBS_TEAM_NAME_MAP:
        return _CBS_TEAM_NAME_MAP[stripped]
    # Try case-insensitive lookup
    for full_name, abbrev in _CBS_TEAM_NAME_MAP.items():
        if full_name.lower() == stripped.lower():
            return abbrev
    logger.warning("CBS team name '%s' not found in mapping; returning as-is.", raw)
    return stripped.upper()


def _build_player_lookup(conn: sqlite3.Connection) -> dict[str, int]:
    """Return a mapping of lowercase full_name → player_id from the Players table.

    Args:
        conn: Open SQLite connection.

    Returns:
        Dict mapping ``full_name.lower()`` to ``player_id``.
    """
    rows = conn.execute("SELECT player_id, full_name FROM Players").fetchall()
    return {row[1].lower(): row[0] for row in rows if row[1]}


def _build_team_lookup(conn: sqlite3.Connection) -> dict[str, int]:
    """Return a mapping of abbreviation (upper) → team_id from the Teams table.

    Args:
        conn: Open SQLite connection.

    Returns:
        Dict mapping ``abbreviation.upper()`` to ``team_id``.
    """
    rows = conn.execute("SELECT team_id, abbreviation FROM Teams").fetchall()
    return {row[1].upper(): row[0] for row in rows if row[1]}


def _match_player(
    name: str,
    lookup: dict[str, int],
    threshold: int = _FUZZY_MATCH_THRESHOLD,
) -> Optional[int]:
    """Resolve *name* to a player_id using exact then fuzzy matching.

    Args:
        name: Player name as scraped from CBS.
        lookup: Mapping of ``full_name.lower()`` to ``player_id``.
        threshold: Minimum fuzzy-match score to accept (0–100).

    Returns:
        Matched ``player_id``, or ``None`` if no match was found.
    """
    normalised = name.strip().lower()

    # 1. Exact match (case-insensitive).
    if normalised in lookup:
        return lookup[normalised]

    # 2. Fuzzy match.
    if not lookup:
        return None

    match = fuzz_process.extractOne(normalised, lookup.keys())
    if match and match[1] >= threshold:
        matched_name, score = match[0], match[1]
        logger.debug(
            "Fuzzy-matched '%s' → '%s' (score=%d).", name, matched_name, score
        )
        return lookup[matched_name]

    logger.warning(
        "Could not match CBS player '%s' to any Players record (best score=%s). Skipping.",
        name,
        match[1] if match else "N/A",
    )
    return None


def transform_injuries(
    raw_rows: list[dict],
    conn: sqlite3.Connection,
) -> pd.DataFrame:
    """Transform scraped CBS injury rows into a DataFrame for ``Injury_Status``.

    Maps player names to ``player_id`` (fuzzy) and full team names to
    ``team_id`` from the database.  Rows whose player cannot be matched are
    dropped with a warning.

    Args:
        raw_rows: List of dicts from :func:`parse_injury_table`.
        conn: Open SQLite connection (used to load Players/Teams lookups).

    Returns:
        DataFrame with columns matching the ``Injury_Status`` table schema:
        ``player_id``, ``team_id``, ``report_date``, ``status``, ``reason``,
        ``source``, ``last_updated_ts``.
    """
    if not raw_rows:
        logger.info("No raw CBS injury rows to transform.")
        return pd.DataFrame(
            columns=[
                "player_id", "team_id", "report_date", "status",
                "reason", "source", "last_updated_ts",
            ]
        )

    player_lookup = _build_player_lookup(conn)
    team_lookup = _build_team_lookup(conn)

    today = date.today().isoformat()
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records: list[dict] = []
    for row in raw_rows:
        player_id = _match_player(row["player_name"], player_lookup)
        if player_id is None:
            continue

        canonical_abbrev = _normalise_team_name(row["team_name"])
        team_id: Optional[int] = team_lookup.get(canonical_abbrev)
        if team_id is None:
            logger.debug(
                "CBS team '%s' (→ '%s') not found in Teams table; storing NULL.",
                row["team_name"], canonical_abbrev,
            )

        records.append(
            {
                "player_id": player_id,
                "team_id": team_id,
                "report_date": today,
                "status": row["status"],
                "reason": row["reason"] or None,
                "source": _SOURCE,
                "last_updated_ts": now_ts,
            }
        )

    df = pd.DataFrame(records)
    if not df.empty:
        # Deduplicate: keep last occurrence per (player_id, report_date, source).
        df = df.drop_duplicates(subset=["player_id", "report_date", "source"], keep="last")
    logger.info("Transformed %d CBS injury records (from %d raw rows).", len(df), len(raw_rows))
    return df


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_injuries(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """Upsert *df* into the ``Injury_Status`` table.

    Args:
        df: Transformed DataFrame (columns matching ``Injury_Status``).
        conn: Open SQLite connection.

    Returns:
        Number of rows upserted.
    """
    if df.empty:
        logger.info("Injury_Status (CBS): no rows to upsert.")
        return 0
    upsert_dataframe(df, "Injury_Status", conn)
    return len(df)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_cbs_injuries(db_path: str = DB_PATH) -> int:
    """Scrape CBS Sports and upsert today's injury data into ``Injury_Status``.

    Full ETL cycle:

    1. Fetches the CBS Sports NBA injury report page.
    2. Parses the HTML into structured rows.
    3. Fuzzy-matches player names and maps team names.
    4. Upserts the result into ``Injury_Status`` via ``upsert_dataframe()``.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Number of rows upserted into ``Injury_Status``.
    """
    logger.info("=== CBS Sports Injury Sync ===")

    try:
        html = fetch_injury_page()
    except Exception:
        logger.exception("Failed to fetch CBS Sports injury report page. Aborting sync.")
        return 0

    raw_rows = parse_injury_table(html)
    if not raw_rows:
        logger.info("No CBS injury rows found on the page. Nothing to load.")
        return 0

    conn = sqlite3.connect(db_path)
    try:
        df = transform_injuries(raw_rows, conn)
        count = load_injuries(df, conn)
        conn.commit()
        logger.info("=== CBS Sports Injury Sync complete. %d rows upserted. ===", count)
        return count
    except Exception:
        logger.exception("Error during CBS Sports injury sync.")
        conn.rollback()
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sync_cbs_injuries()
