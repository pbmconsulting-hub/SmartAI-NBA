# ============================================================
# FILE: data/web_scraper.py
# PURPOSE: Fetch real-time NBA injury and roster data using
#          nba_api as the single authoritative source.
#          Provides Layer 5 of the player availability pipeline.
#
# DATA SOURCES:
#   1. nba_api live Injuries endpoint  — today's official designations
#   2. nba_api CommonAllPlayers        — active roster validation
#
# USAGE:
#   from data.web_scraper import fetch_all_injury_data
#   injury_data = fetch_all_injury_data()
#   # Returns {player_name_lower: {status, injury_note, source, ...}}
#
# RATE-LIMITING NOTES:
#   - nba_api enforces built-in delays; no additional waits required
# ============================================================

import re
import time
import json

# Third-party imports (listed in requirements.txt)
try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPER_DEPS_AVAILABLE = True
except ImportError:
    _SCRAPER_DEPS_AVAILABLE = False

# ============================================================
# SECTION: Constants
# ============================================================

# Browser-like User-Agent to avoid being blocked by sites that
# reject requests from scripts/bots with no User-Agent header.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

# Network timeouts and retry settings
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # exponential backoff: 2, 4, 8 seconds

# Basketball-Reference rate limit: 20 requests/min → 3 s between requests
BREF_REQUEST_DELAY_SECONDS = 3.0

# Source URLs
BREF_ROSTER_URL_TEMPLATE = (
    "https://www.basketball-reference.com/teams/{team}/2026.html"
)

# Status normaliser — maps raw status strings → canonical labels
_STATUS_NORMALIZER = {
    # Out variants
    "out": "Out",
    "out for season": "Out",
    "suspended": "Out",
    # GTD / Day-to-Day variants
    "game time decision": "GTD",
    "gtd": "GTD",
    "day-to-day": "Day-to-Day",
    "day to day": "Day-to-Day",
    "dtd": "Day-to-Day",
    # Doubtful
    "doubtful": "Doubtful",
    # Questionable
    "questionable": "Questionable",
    # Probable
    "probable": "Probable",
}

# ============================================================
# END SECTION: Constants
# ============================================================


# ============================================================
# SECTION: Internal Helpers
# ============================================================

# Common name suffixes to strip for normalised key comparison
_NAME_SUFFIXES_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)\s*$",
    re.IGNORECASE,
)

# Strategy C thresholds
_MAX_CONTAINER_ELEMENTS = 500  # Prefer smaller containers (direct row-level parents)
_MIN_PLAYER_NAME_LENGTH = 3    # Minimum characters to treat a cell as a player name
_MIN_TEAM_ABBREV_LENGTH = 2    # NBA team abbreviations are 2–4 uppercase letters
_MAX_TEAM_ABBREV_LENGTH = 4


def _normalize_player_key(name):
    """
    Return a consistent lowercase key for a player name.

    Strips leading/trailing whitespace, collapses internal whitespace,
    and removes common generational suffixes (Jr., Sr., II, III, IV, V)
    so that "Jaren Jackson Jr." and "Jaren Jackson" map to the same key.

    Args:
        name (str): Raw player name.

    Returns:
        str: Normalised lowercase key.
    """
    if not name:
        return ""
    key = name.lower().strip()
    key = re.sub(r"\s+", " ", key)         # collapse internal whitespace
    key = _NAME_SUFFIXES_RE.sub("", key)   # strip generational suffixes
    return key.strip()


def _get_with_retry(url, params=None, timeout=REQUEST_TIMEOUT_SECONDS):
    """
    Perform an HTTP GET with exponential-backoff retries.

    Args:
        url (str): URL to fetch.
        params (dict, optional): Query parameters.
        timeout (int): Per-attempt timeout in seconds.

    Returns:
        requests.Response: The successful response object.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        raise RuntimeError(
            "requests/beautifulsoup4 not installed. "
            "Run: pip install requests beautifulsoup4 lxml"
        )

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=_HEADERS,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                sleep_secs = RETRY_BACKOFF_BASE ** attempt
                print(
                    f"  web_scraper: attempt {attempt}/{MAX_RETRIES} failed "
                    f"for {url} ({exc}). Retrying in {sleep_secs}s…"
                )
                time.sleep(sleep_secs)
            else:
                print(
                    f"  web_scraper: all {MAX_RETRIES} attempts failed for {url}: {exc}"
                )

    raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts: {last_exc}")


def _normalize_status(raw_status):
    """
    Normalise a raw status string from an external source to our
    canonical vocabulary.

    Args:
        raw_status (str): Raw status string from the scraper.

    Returns:
        str: Canonical status string, e.g. "Out", "GTD", "Day-to-Day".
             Falls back to the input (title-cased) if unrecognised.
    """
    if not raw_status:
        return "Unknown"
    normalised = _STATUS_NORMALIZER.get(raw_status.lower().strip())
    return normalised if normalised else raw_status.strip().title()

# ============================================================
# END SECTION: Internal Helpers
# ============================================================



# ============================================================
# NOTE: Injury data is now fetched via nba_api through RosterEngine.
# See: data/roster_engine.py and data/web_scraper.fetch_all_injury_data()
# ============================================================




# ============================================================
# SECTION: Scraper 3 — Basketball-Reference Team Rosters
# ============================================================

# Module-level throttle timestamp to enforce the 3-second minimum
# gap between successive Basketball-Reference requests, even when
# this function is called multiple times in one session.
_bref_last_request_time = 0.0


def scrape_basketball_reference_roster(team_abbrev):
    """
    Scrape a team's current roster from Basketball-Reference.

    ⚠️ RATE LIMIT: Basketball-Reference enforces a hard limit of
    20 requests per minute. Exceeding it results in a 24-hour IP
    ban. This function enforces a minimum 3-second gap between
    requests using a module-level timestamp.

    Target page: https://www.basketball-reference.com/teams/{ABBREV}/2026.html

    The roster table has id="roster" (or class="stats_table") with columns:
        No. | Player | Pos | Ht | Wt | Birth Date | Nationality | Exp | College

    We target the <table id="roster"> element specifically to avoid
    accidentally parsing other tables on the page (team stats, etc.).

    Args:
        team_abbrev (str): Basketball-Reference team abbreviation,
                           e.g. "LAL", "BOS", "GSW".

    Returns:
        list of dict: [
            {
                "name":     str,   # Player display name
                "number":   str,   # Jersey number
                "position": str,   # e.g. "PG", "SF"
                "height":   str,   # e.g. "6-9"
                "weight":   str,   # lbs
            },
            …
        ]
        Empty list on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print("scrape_basketball_reference_roster: missing dependencies (requests/bs4)")
        return []

    global _bref_last_request_time

    # Enforce the 3-second rate limit between requests
    elapsed = time.time() - _bref_last_request_time
    if elapsed < BREF_REQUEST_DELAY_SECONDS:
        wait = BREF_REQUEST_DELAY_SECONDS - elapsed
        print(
            f"scrape_basketball_reference_roster: rate-limit sleep {wait:.1f}s "
            f"before fetching {team_abbrev}"
        )
        time.sleep(wait)

    url = BREF_ROSTER_URL_TEMPLATE.format(team=team_abbrev.upper())
    print(f"scrape_basketball_reference_roster: fetching {url}")

    roster = []
    try:
        response = _get_with_retry(url)
        _bref_last_request_time = time.time()

        soup = BeautifulSoup(response.text, "lxml")

        # Primary target: <table id="roster">
        # Fallback: first <table class="stats_table"> on the page
        table = soup.find("table", id="roster")
        if table is None:
            table = soup.find("table", class_="stats_table")
        if table is None:
            table = soup.find("table")

        if table is None:
            print(
                f"scrape_basketball_reference_roster: no table found for {team_abbrev}"
            )
            return []

        # Determine header column positions dynamically
        headers = [
            th.get_text(strip=True).lower().replace(".", "")
            for th in table.select("thead th")
        ]
        col = {}
        for i, h in enumerate(headers):
            if h in ("no", "#", "number"):
                col["number"] = i
            elif h in ("player",):
                col["name"] = i
            elif h in ("pos", "position"):
                col["position"] = i
            elif h in ("ht", "height"):
                col["height"] = i
            elif h in ("wt", "weight"):
                col["weight"] = i

        for tr in table.select("tbody tr"):
            # Skip header repeat rows that Basketball-Reference injects
            if tr.get("class") and "thead" in " ".join(tr.get("class", [])):
                continue

            cells = [td.get_text(strip=True) for td in tr.select("td")]
            th_cells = [th.get_text(strip=True) for th in tr.select("th")]

            if not cells and not th_cells:
                continue

            # th_cells holds the row header (jersey number in bref layout)
            number = th_cells[0] if th_cells else ""

            try:
                # In Basketball-Reference tables the row header (<th scope="row">)
                # is the jersey number and is already in th_cells. The <td> data
                # cells therefore correspond to header column index - 1 (since the
                # "No." header at index 0 has no matching <td>).
                # We build a safe mapping to avoid negative indexing.
                _data = {}
                for _col_name, _col_idx in col.items():
                    _td_idx = _col_idx - 1  # skip the "No." header column
                    if 0 <= _td_idx < len(cells):
                        _data[_col_name] = cells[_td_idx]

                name     = _data.get("name",     cells[0] if cells else "")
                position = _data.get("position", cells[1] if len(cells) > 1 else "")
                height   = _data.get("height",   cells[2] if len(cells) > 2 else "")
                weight   = _data.get("weight",   cells[3] if len(cells) > 3 else "")
            except IndexError:
                name, position, height, weight = "", "", "", ""

            if not name:
                continue

            roster.append({
                "name":     name,
                "number":   number,
                "position": position,
                "height":   height,
                "weight":   weight,
            })

        print(
            f"scrape_basketball_reference_roster: found {len(roster)} players "
            f"for {team_abbrev}"
        )

    except Exception as exc:
        print(
            f"scrape_basketball_reference_roster: error for {team_abbrev} — {exc}"
        )

    return roster

# ============================================================
# END SECTION: Scraper 3 — Basketball-Reference
# ============================================================


# ============================================================
# SECTION: Master Aggregator
# ============================================================

def fetch_all_injury_data():
    """
    Fetch and merge injury status from the official NBA data source (nba_api).

    Delegates to RosterEngine which uses:
        1. nba_api live Injuries endpoint  — today's official designations
        2. nba_api CommonAllPlayers        — active roster validation

    The function signature and return schema are unchanged so all callers
    (Neural Analysis, Data Feed, live_data_fetcher) continue to work.

    Returns:
        dict: {player_name_lower: {
                  "status":      str,   # "Active"|"Out"|"GTD"|"Day-to-Day"|…
                  "injury":      str,   # body part / reason (may be "")
                  "injury_note": str,   # same as injury (legacy compat)
                  "team":        str,   # team abbreviation (may be "")
                  "return_date": str,   # expected return date (may be "")
                  "comment":     str,   # additional notes (may be "")
                  "source":      str,   # "nba_api"
              }}
        Empty dict if the nba_api call fails.
    """
    try:
        from data.roster_engine import RosterEngine
        engine = RosterEngine()
        engine.refresh()
        raw = engine.get_injury_report()

        merged = {}
        for key, entry in raw.items():
            injury_val = entry.get("injury", "")
            merged[key] = {
                "status":      entry.get("status", "Unknown"),
                "injury":      injury_val,
                "injury_note": injury_val,
                "team":        entry.get("team", ""),
                "return_date": entry.get("return_date", ""),
                "comment":     entry.get("comment", injury_val),
                "source":      entry.get("source", "nba_api"),
            }

        total     = len(merged)
        out_count = sum(1 for v in merged.values() if v["status"] == "Out")
        gtd_count = sum(
            1 for v in merged.values()
            if v["status"] in ("GTD", "Questionable", "Doubtful", "Day-to-Day")
        )
        print(
            f"fetch_all_injury_data complete: {total} players — "
            f"{out_count} Out, {gtd_count} GTD/Questionable/Doubtful"
        )
        return merged
    except Exception as exc:
        print(f"fetch_all_injury_data: error — {exc}")
        return {}

# ============================================================
# END SECTION: Master Aggregator
# ============================================================


# ============================================================
# SECTION: Convenience function for tonight's active players
# ============================================================

def get_active_players_for_tonight(todays_games: list) -> dict:
    """
    Convenience wrapper: uses RosterEngine to return active (non-injured)
    players for every team playing tonight.

    Delegates to data.roster_engine.get_active_players_for_tonight() so
    there is a single source of truth for roster + injury logic.

    Args:
        todays_games (list): List of game dicts with 'home_team'/'away_team'.

    Returns:
        dict: {team_abbrev: [player_name, ...]}  — injured players excluded.
    """
    try:
        from data.roster_engine import get_active_players_for_tonight as _re_fn
        return _re_fn(todays_games)
    except Exception as exc:
        print(f"get_active_players_for_tonight (web_scraper): {exc}")
        return {}

# ============================================================
# END SECTION: Convenience function for tonight's active players
# ============================================================
