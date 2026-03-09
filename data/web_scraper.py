# ============================================================
# FILE: data/web_scraper.py
# PURPOSE: Scrape real-time NBA injury and roster data from
#          authoritative external sources to supplement nba_api.
#          Provides Layer 5 of the player availability pipeline.
#
# DATA SOURCES (in priority order):
#   1. NBA.com Official Injury Report — JSON CDN (highest authority)
#   2. RotoWire NBA Injury Report     — HTML scrape (most up-to-date)
#   3. Basketball-Reference Rosters   — HTML scrape (roster validation)
#
# USAGE:
#   from data.web_scraper import fetch_all_injury_data
#   injury_data = fetch_all_injury_data()
#   # Returns {player_name_lower: {status, injury_note, source, ...}}
#
# RATE-LIMITING NOTES:
#   - Basketball-Reference: max 20 requests/min → 3 s delay enforced
#   - RotoWire / NBA.com: no published limit; one request per call
#   - All requests include a User-Agent header to avoid auto-blocks
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
ROTOWIRE_INJURY_URL = "https://www.rotowire.com/basketball/injury-report.php"
NBA_CDN_INJURY_JSON_URL = (
    "https://cdn.nba.com/static/json/staticData/InjuryReport.json"
)
NBA_CDN_INJURY_JSON_URL_ALT = (
    "https://cdn.nba.com/static/json/liveData/injuries/injuries_all.json"
)
NBA_HTML_INJURY_URL = "https://www.nba.com/players/injuries"
BREF_ROSTER_URL_TEMPLATE = (
    "https://www.basketball-reference.com/teams/{team}/2026.html"
)

# Map RotoWire/NBA.com status strings → our canonical status labels
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
# SECTION: Scraper 1 — RotoWire NBA Injury Report
# ============================================================

def scrape_rotowire_injury_report():
    """
    Scrape RotoWire NBA injury report page.

    RotoWire uses a predictable table structure:
    - Each player row is a <div class="rt-inner-table"> or similar container
    - Columns: Player, Team, Pos, Injury, Status, Expected Return

    As of the 2024-25 season the markup looks like:
        <ul class="injury-report"> (one per player)
            <li class="injury-report__player-name">
            <li class="injury-report__team">
            <li class="injury-report__pos">
            <li class="injury-report__injury">
            <li class="injury-report__status">
            <li class="injury-report__est-return">

    We use flexible CSS class-substring matching so minor markup
    changes don't immediately break parsing.

    Returns:
        dict: {player_name_lower: {
                  "status":      str,   # "Out", "GTD", "Day-to-Day", …
                  "injury":      str,   # e.g. "Knee", "Ankle – surgery"
                  "team":        str,   # e.g. "LAL"
                  "return_date": str,   # Expected return or ""
                  "source":      str,   # "RotoWire"
              }}
        Empty dict on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print("scrape_rotowire_injury_report: missing dependencies (requests/bs4)")
        return {}

    print("scrape_rotowire_injury_report: fetching", ROTOWIRE_INJURY_URL)
    result = {}

    try:
        response = _get_with_retry(ROTOWIRE_INJURY_URL)
        soup = BeautifulSoup(response.text, "lxml")

        # ── Strategy A: structured <ul class="injury-report"> rows ──────
        #
        # RotoWire renders one <ul class="injury-report"> per player
        # inside a section scoped to NBA/Basketball.
        #
        # The CSS classes we target (using partial-match via [class*=]):
        #   injury-report__player-name → player display name
        #   injury-report__team        → team abbreviation
        #   injury-report__injury      → injury description
        #   injury-report__status      → designation string
        #   injury-report__est-return  → return-date text

        rows = soup.select("ul.injury-report")
        if rows:
            for row in rows:
                try:
                    name_el   = row.select_one("[class*='player-name']")
                    team_el   = row.select_one("[class*='__team']")
                    injury_el = row.select_one("[class*='__injury']")
                    status_el = row.select_one("[class*='__status']")
                    return_el = row.select_one("[class*='est-return']")

                    name   = name_el.get_text(strip=True)   if name_el   else ""
                    team   = team_el.get_text(strip=True)   if team_el   else ""
                    injury = injury_el.get_text(strip=True) if injury_el else ""
                    status = status_el.get_text(strip=True) if status_el else ""
                    ret    = return_el.get_text(strip=True) if return_el else ""

                    if not name:
                        continue

                    key = name.lower().strip()
                    result[key] = {
                        "status":      _normalize_status(status),
                        "injury":      injury,
                        "team":        team,
                        "return_date": ret,
                        "source":      "RotoWire",
                    }
                except Exception as row_err:
                    print(f"  scrape_rotowire: row parse error: {row_err}")
                    continue

            print(f"scrape_rotowire_injury_report: found {len(result)} players (Strategy A)")
            return result

        # ── Strategy B: generic <table> fallback ────────────────────────
        #
        # Some RotoWire page variants use a plain HTML <table>.
        # Column order: Player | Team | Pos | Injury | Status | Est. Return
        #
        table = soup.find("table")
        if table:
            headers = [th.get_text(strip=True).lower() for th in table.select("th")]
            # Build column-index map
            col = {}
            for i, h in enumerate(headers):
                if "player" in h:
                    col["name"] = i
                elif "team" in h:
                    col["team"] = i
                elif "injury" in h:
                    col["injury"] = i
                elif "status" in h:
                    col["status"] = i
                elif "return" in h:
                    col["return_date"] = i

            for tr in table.select("tbody tr"):
                cells = [td.get_text(strip=True) for td in tr.select("td")]
                if not cells:
                    continue
                try:
                    name       = cells[col.get("name",   0)] if "name"        in col else ""
                    team       = cells[col.get("team",   1)] if "team"        in col else ""
                    injury     = cells[col.get("injury", 3)] if "injury"      in col else ""
                    status     = cells[col.get("status", 4)] if "status"      in col else ""
                    return_date = cells[col.get("return_date", 5)] if "return_date" in col else ""

                    if not name:
                        continue

                    key = name.lower().strip()
                    result[key] = {
                        "status":      _normalize_status(status),
                        "injury":      injury,
                        "team":        team,
                        "return_date": return_date,
                        "source":      "RotoWire",
                    }
                except (IndexError, KeyError) as cell_err:
                    print(f"  scrape_rotowire: cell parse error: {cell_err}")
                    continue

            print(f"scrape_rotowire_injury_report: found {len(result)} players (Strategy B)")
            return result

        # ── Strategy C: broad regex/class partial matching ──────────────
        #
        # Last-resort fallback for markup that doesn't match Strategy A or B.
        # Searches for any <div> or <table> that contains the column header
        # text that RotoWire typically uses: "Player", "Status", "Injury",
        # "Est. Return".  This is intentionally broader so that minor
        # markup rewrites don't immediately break the scraper.
        #
        _ROTOWIRE_HEADER_RE = re.compile(
            r"\b(player|status|injury|est\.?\s*return)\b",
            re.IGNORECASE,
        )

        # Find any container whose text mentions at least two of the
        # known RotoWire column headers.
        candidate_containers = []
        for tag in soup.find_all(["div", "table", "section"]):
            text = tag.get_text(" ", strip=True)
            if len(_ROTOWIRE_HEADER_RE.findall(text)) >= 2:
                # Prefer smaller containers (direct row-level parents)
                if len(tag.find_all(True)) < _MAX_CONTAINER_ELEMENTS:
                    candidate_containers.append(tag)

        for container in candidate_containers:
            rows_c = container.find_all("tr")
            if not rows_c:
                # Try div rows — each row sibling containing a player name
                rows_c = [
                    el for el in container.find_all(True)
                    if el.get("class") and any(
                        "player" in c.lower() for c in el.get("class", [])
                    )
                ]
            if not rows_c:
                continue

            tmp_result = {}
            for row in rows_c:
                try:
                    cells = row.find_all(["td", "li", "span", "div"])
                    texts = [c.get_text(strip=True) for c in cells]
                    if len(texts) < 2:
                        continue
                    # Heuristic: first non-empty cell is often the player name
                    name = texts[0] if texts[0] else ""
                    if not name or len(name) < _MIN_PLAYER_NAME_LENGTH:
                        continue
                    # Try to locate status/injury from the remaining cells
                    status = ""
                    injury = ""
                    team = ""
                    ret = ""
                    for cell_text in texts[1:]:
                        lower_ct = cell_text.lower()
                        if not status and any(
                            kw in lower_ct for kw in
                            ("out", "gtd", "doubtful", "questionable",
                             "day-to-day", "probable", "active")
                        ):
                            status = cell_text
                        elif not injury and len(cell_text) > 2:
                            injury = cell_text
                        elif not team and _MIN_TEAM_ABBREV_LENGTH <= len(cell_text) <= _MAX_TEAM_ABBREV_LENGTH and cell_text.isupper():
                            team = cell_text
                        elif not ret and any(
                            c.isdigit() for c in cell_text
                        ):
                            ret = cell_text
                    if name and status:
                        key = name.lower().strip()
                        tmp_result[key] = {
                            "status":      _normalize_status(status),
                            "injury":      injury,
                            "team":        team,
                            "return_date": ret,
                            "source":      "RotoWire",
                        }
                except Exception:
                    continue

            if tmp_result:
                result.update(tmp_result)
                print(
                    f"scrape_rotowire_injury_report: found {len(result)} players "
                    f"(Strategy C)"
                )
                return result

        print("scrape_rotowire_injury_report: no recognisable HTML structure found")

    except Exception as exc:
        print(f"scrape_rotowire_injury_report: error — {exc}")

    # ── Strategy D: JSON API endpoint fallback ──────────────────────
    #
    # RotoWire sometimes exposes player injury data via an internal JSON
    # endpoint.  We attempt this only when all HTML strategies have failed
    # (result is still empty).  If the endpoint returns non-JSON or an
    # error status we silently return whatever result we have so far.
    #
    if not result:
        _ROTOWIRE_JSON_URL = (
            "https://www.rotowire.com/basketball/tables/injury-report.php"
            "?team=ALL&pos=ALL"
        )
        try:
            print(
                "scrape_rotowire_injury_report: trying JSON endpoint (Strategy D) →",
                _ROTOWIRE_JSON_URL,
            )
            json_response = _get_with_retry(_ROTOWIRE_JSON_URL)
            rows_json = json_response.json()
            if isinstance(rows_json, list) and rows_json:
                for item in rows_json:
                    if not isinstance(item, dict):
                        continue
                    name = (
                        item.get("player")
                        or item.get("playerName")
                        or ""
                    )
                    if not name:
                        continue
                    team   = item.get("team", "")
                    injury = item.get("injury", "")
                    status = item.get("status", "")
                    ret    = item.get("expectedReturn", "")
                    key = name.lower().strip()
                    result[key] = {
                        "status":      _normalize_status(status),
                        "injury":      injury,
                        "team":        team,
                        "return_date": ret,
                        "source":      "RotoWire",
                    }
                print(
                    f"scrape_rotowire_injury_report: found {len(result)} players "
                    f"(Strategy D)"
                )
        except Exception:
            # Non-JSON response or network error — silently fall through
            pass

    return result

# ============================================================
# END SECTION: Scraper 1 — RotoWire
# ============================================================


# ============================================================
# SECTION: Scraper 2 — NBA.com Official Injury Report
# ============================================================

def scrape_nba_official_injury_report():
    """
    Fetch the official NBA injury report data.

    Tries the JSON CDN endpoint first (fast, structured).
    Falls back to HTML scraping of the NBA injuries page if the CDN
    endpoint is unavailable or returns unexpected data.

    CDN JSON structure (InjuryReport.json):
        {
          "InjuryList": [
            {
              "TeamID":         int,
              "TeamAbbreviation": str,   # e.g. "LAL"
              "FirstName":      str,
              "LastName":       str,
              "PersonID":       int,
              "StatusCategory": str,     # "Out", "Game Time Decision", …
              "StatusType":     str,     # more granular, e.g. "Rest"
              "Injury":         str,     # body-part / reason
              "Comment":        str,
            },
            …
          ]
        }

    Returns:
        dict: {player_name_lower: {
                  "status":      str,
                  "injury":      str,
                  "team":        str,
                  "comment":     str,
                  "source":      str,   # "NBA.com"
              }}
        Empty dict on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print("scrape_nba_official_injury_report: missing dependencies (requests/bs4)")
        return {}

    result = {}

    # ── Attempt 1: JSON CDN endpoint ────────────────────────────────────
    print("scrape_nba_official_injury_report: trying JSON CDN →", NBA_CDN_INJURY_JSON_URL)
    try:
        response = _get_with_retry(NBA_CDN_INJURY_JSON_URL)
        data = response.json()
        injury_list = data.get("InjuryList") or data.get("injuryList") or []

        # Also handle wrapper like {"LeagueInjuries": [...]}
        if not injury_list:
            for value in data.values():
                if isinstance(value, list) and len(value) > 0:
                    injury_list = value
                    break

        if injury_list:
            for entry in injury_list:
                first = entry.get("FirstName", "") or entry.get("firstName", "")
                last  = entry.get("LastName",  "") or entry.get("lastName",  "")
                name  = f"{first} {last}".strip()
                if not name:
                    continue

                team    = (entry.get("TeamAbbreviation", "") or
                           entry.get("teamAbbreviation", "") or
                           entry.get("teamTricode", ""))
                status  = (entry.get("StatusCategory", "") or
                           entry.get("statusCategory", "") or
                           entry.get("gameStatus", ""))
                injury  = (entry.get("Injury", "") or
                           entry.get("injury", "") or
                           entry.get("bodyPartCategory", ""))
                comment = entry.get("Comment", "") or entry.get("comment", "")

                key = name.lower().strip()
                result[key] = {
                    "status":  _normalize_status(status),
                    "injury":  injury,
                    "team":    team,
                    "comment": comment,
                    "source":  "NBA.com",
                }

            print(
                f"scrape_nba_official_injury_report: found {len(result)} players "
                f"from JSON CDN"
            )
            return result

        print("scrape_nba_official_injury_report: JSON CDN returned empty injury list")

    except Exception as cdn_err:
        print(f"scrape_nba_official_injury_report: JSON CDN failed — {cdn_err}")

    # ── Attempt 1b: Alternate CDN URL ────────────────────────────────────
    #
    # If the primary CDN returned an empty list or raised, try the alternate
    # CDN URL before falling through to the HTML scrape.
    #
    print(
        "scrape_nba_official_injury_report: trying alternate CDN →",
        NBA_CDN_INJURY_JSON_URL_ALT,
    )
    try:
        alt_response = _get_with_retry(NBA_CDN_INJURY_JSON_URL_ALT)
        alt_data = alt_response.json()
        alt_injury_list = alt_data.get("InjuryList") or alt_data.get("injuryList") or []

        if not alt_injury_list:
            for value in alt_data.values():
                if isinstance(value, list) and len(value) > 0:
                    alt_injury_list = value
                    break

        if alt_injury_list:
            for entry in alt_injury_list:
                first = entry.get("FirstName", "") or entry.get("firstName", "")
                last  = entry.get("LastName",  "") or entry.get("lastName",  "")
                name  = f"{first} {last}".strip()
                if not name:
                    continue

                team    = (entry.get("TeamAbbreviation", "") or
                           entry.get("teamAbbreviation", "") or
                           entry.get("teamTricode", ""))
                status  = (entry.get("StatusCategory", "") or
                           entry.get("statusCategory", "") or
                           entry.get("gameStatus", ""))
                injury  = (entry.get("Injury", "") or
                           entry.get("injury", "") or
                           entry.get("bodyPartCategory", ""))
                comment = entry.get("Comment", "") or entry.get("comment", "")

                key = name.lower().strip()
                result[key] = {
                    "status":  _normalize_status(status),
                    "injury":  injury,
                    "team":    team,
                    "comment": comment,
                    "source":  "NBA.com",
                }

            print(
                f"scrape_nba_official_injury_report: found {len(result)} players "
                f"from alternate CDN"
            )
            return result

        print("scrape_nba_official_injury_report: alternate CDN returned empty injury list")

    except Exception as alt_err:
        print(f"scrape_nba_official_injury_report: alternate CDN failed — {alt_err}")

    # ── Attempt 2: HTML fallback ─────────────────────────────────────────
    #
    # The NBA injuries HTML page renders a table or a series of <div> cards.
    # We look for any <table> element, then the columns:
    #   Player | Team | Status | Injury | Comment
    #
    print("scrape_nba_official_injury_report: falling back to HTML →", NBA_HTML_INJURY_URL)
    try:
        response = _get_with_retry(NBA_HTML_INJURY_URL)
        soup = BeautifulSoup(response.text, "lxml")

        table = soup.find("table")
        if table:
            headers = [th.get_text(strip=True).lower() for th in table.select("th")]
            col = {}
            for i, h in enumerate(headers):
                if "player" in h or "name" in h:
                    col["name"] = i
                elif "team" in h:
                    col["team"] = i
                elif "status" in h or "designation" in h:
                    col["status"] = i
                elif "injury" in h or "type" in h:
                    col["injury"] = i
                elif "comment" in h or "note" in h:
                    col["comment"] = i

            for tr in table.select("tbody tr"):
                cells = [td.get_text(strip=True) for td in tr.select("td")]
                if not cells:
                    continue
                try:
                    name    = cells[col.get("name",    0)] if "name"    in col else ""
                    team    = cells[col.get("team",    1)] if "team"    in col else ""
                    status  = cells[col.get("status",  2)] if "status"  in col else ""
                    injury  = cells[col.get("injury",  3)] if "injury"  in col else ""
                    comment = cells[col.get("comment", 4)] if "comment" in col else ""

                    if not name:
                        continue

                    key = name.lower().strip()
                    result[key] = {
                        "status":  _normalize_status(status),
                        "injury":  injury,
                        "team":    team,
                        "comment": comment,
                        "source":  "NBA.com",
                    }
                except (IndexError, KeyError) as cell_err:
                    print(f"  scrape_nba_html: cell parse error: {cell_err}")
                    continue

            print(
                f"scrape_nba_official_injury_report: found {len(result)} players "
                f"from HTML fallback"
            )
        else:
            print("scrape_nba_official_injury_report: no table found in HTML page")

    except Exception as html_err:
        print(f"scrape_nba_official_injury_report: HTML fallback failed — {html_err}")

    return result

# ============================================================
# END SECTION: Scraper 2 — NBA.com Official
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
    Master function: call all scrapers, merge results with priority ordering.

    Priority (highest wins):
        1. NBA.com Official   — authoritative designation
        2. RotoWire           — fastest updates, GTD granularity
        3. (Basketball-Reference is roster-only; used for validation, not
           direct injury data and is NOT called here by default to avoid
           its strict rate limits during routine refreshes.)

    Override rules applied during merge:
        - If NBA.com says "Out" and local nba_api data says "Active" → Out
        - If RotoWire says "GTD" and nothing better → GTD
        - If both sources agree → keep the stricter status

    Returns:
        dict: {player_name_lower: {
                  "status":      str,   # "Active"|"Out"|"GTD"|"Day-to-Day"|…
                  "injury":      str,   # body part / reason (may be "")
                  "team":        str,   # team abbreviation (may be "")
                  "return_date": str,   # expected return date (may be "")
                  "comment":     str,   # additional notes (may be "")
                  "source":      str,   # which scraper provided this entry
              }}
        Empty dict if all scrapers fail.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print(
            "fetch_all_injury_data: requests/beautifulsoup4 not installed — "
            "Layer 5 skipped. Run: pip install requests beautifulsoup4 lxml"
        )
        return {}

    # ── Run each scraper independently; failures are isolated ───────────
    rotowire_data = {}
    nba_official_data = {}

    try:
        rotowire_data = scrape_rotowire_injury_report()
    except Exception as exc:
        print(f"fetch_all_injury_data: RotoWire scraper raised: {exc}")

    try:
        nba_official_data = scrape_nba_official_injury_report()
    except Exception as exc:
        print(f"fetch_all_injury_data: NBA.com scraper raised: {exc}")

    # ── Merge: start with RotoWire, then let NBA.com override ────────────
    merged = {}

    for key, entry in rotowire_data.items():
        injury_val = entry.get("injury", "")
        merged[key] = {
            "status":      entry.get("status", "Unknown"),
            "injury":      injury_val,
            "injury_note": injury_val,
            "team":        entry.get("team", ""),
            "return_date": entry.get("return_date", ""),
            "comment":     "",
            "source":      entry.get("source", "RotoWire"),
        }

    for key, entry in nba_official_data.items():
        if key in merged:
            # NBA.com overrides RotoWire for status and injury detail
            existing = merged[key]
            existing["status"]  = entry.get("status", existing["status"])
            new_injury = entry.get("injury", "") or existing["injury"]
            existing["injury"]       = new_injury
            existing["injury_note"]  = new_injury
            existing["comment"] = entry.get("comment", "")
            existing["source"]  = "NBA.com+RotoWire" if existing["source"] == "RotoWire" else "NBA.com"
        else:
            injury_val = entry.get("injury", "")
            merged[key] = {
                "status":      entry.get("status", "Unknown"),
                "injury":      injury_val,
                "injury_note": injury_val,
                "team":        entry.get("team", ""),
                "return_date": "",
                "comment":     entry.get("comment", ""),
                "source":      entry.get("source", "NBA.com"),
            }

    # ── Final normalization pass: collapse suffix variants + deduplicate ──
    normalized_merged = {}
    _SEV = {
        "Out": 5, "Injured Reserve": 5, "Doubtful": 4,
        "GTD": 3, "Questionable": 3, "Day-to-Day": 2,
        "Probable": 1, "Active": 0, "Unknown": -1,
    }
    for raw_key, entry in merged.items():
        norm_key = _normalize_player_key(raw_key)
        if not norm_key:
            continue
        if norm_key not in normalized_merged:
            normalized_merged[norm_key] = entry
        else:
            existing_sev = _SEV.get(normalized_merged[norm_key]["status"], -1)
            new_sev      = _SEV.get(entry["status"], -1)
            if new_sev > existing_sev:
                normalized_merged[norm_key] = entry
    merged = normalized_merged

    total = len(merged)
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
