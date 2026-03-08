# ============================================================
# FILE: data/web_scrapers.py
# PURPOSE: Multi-source web scraping for accurate, real-time
#          NBA roster and injury information.
#
# SOURCES (in priority order):
#   1. NBA.com Official — authoritative status designations
#   2. RotoWire         — fastest GTD/Out updates
#   3. ESPN             — broad team injury tables
#   4. Basketball-Reference — per-game season stats
#
# USAGE:
#   from data.web_scrapers import (
#       fetch_multi_source_injury_status,
#       fetch_verified_rosters,
#       scrape_espn_injury_report,
#       scrape_bref_season_stats,
#   )
#
# RATE-LIMITING NOTES:
#   - Basketball-Reference: max 20 requests/min → 3 s delay enforced
#   - All requests include a User-Agent header
# ============================================================

import re
import time
import json
import os

# Third-party imports (listed in requirements.txt)
try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPER_DEPS_AVAILABLE = True
except ImportError:
    _SCRAPER_DEPS_AVAILABLE = False

# Re-export the two existing scrapers so callers only need this module
try:
    from data.web_scraper import (
        fetch_all_injury_data,
        scrape_rotowire_injury_report,
        scrape_nba_official_injury_report,
        _get_with_retry,
        _normalize_status,
        _HEADERS,
        REQUEST_TIMEOUT_SECONDS,
        BREF_REQUEST_DELAY_SECONDS,
        ROTOWIRE_INJURY_URL,
    )
    _CORE_SCRAPER_AVAILABLE = True
except ImportError:
    _CORE_SCRAPER_AVAILABLE = False
    fetch_all_injury_data = None
    scrape_rotowire_injury_report = None
    scrape_nba_official_injury_report = None

# ============================================================
# SECTION: Constants
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_HEADERS_LOCAL = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

_REQUEST_TIMEOUT = 15
_BREF_DELAY = 3.0

ESPN_INJURIES_URL = "https://www.espn.com/nba/injuries"
BREF_PER_GAME_URL = "https://www.basketball-reference.com/leagues/NBA_2026_per_game.html"

# Injury status JSON path (same as live_data_fetcher uses)
_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
INJURY_STATUS_JSON_PATH = os.path.join(_DATA_DIR, "injury_status.json")

# ============================================================
# END SECTION: Constants
# ============================================================


# ============================================================
# SECTION: Internal Helpers
# ============================================================

def _safe_get(url, headers=None, timeout=_REQUEST_TIMEOUT, retries=3):
    """
    HTTP GET with exponential-backoff retry logic.
    Returns a requests.Response on success, None on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        return None
    _hdrs = headers or _HEADERS_LOCAL
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=_hdrs, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                # Rate-limited — wait longer then retry
                wait = 2 ** attempt
                print(f"_safe_get: rate-limited ({url}), waiting {wait}s")
                time.sleep(wait)
            else:
                print(f"_safe_get: HTTP {resp.status_code} for {url} (attempt {attempt})")
                if resp.status_code in (404, 403):
                    break
        except Exception as exc:
            wait = 2 ** attempt
            print(f"_safe_get: error fetching {url}: {exc} — retry in {wait}s")
            time.sleep(wait)
    return None


def _canonicalize_status(raw):
    """Map raw status strings to canonical labels."""
    _MAP = {
        "out": "Out",
        "out for season": "Out",
        "suspended": "Out",
        "injured reserve": "Injured Reserve",
        "ir": "Injured Reserve",
        "game time decision": "GTD",
        "gtd": "GTD",
        "day-to-day": "Day-to-Day",
        "day to day": "Day-to-Day",
        "dtd": "Day-to-Day",
        "doubtful": "Doubtful",
        "questionable": "Questionable",
        "probable": "Probable",
        "active": "Active",
    }
    return _MAP.get(str(raw).strip().lower(), "Unknown")


# Common name suffixes to strip for normalised key comparison
_NAME_SUFFIXES_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)\s*$",
    re.IGNORECASE,
)


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
    key = re.sub(r"\s+", " ", key)          # collapse internal whitespace
    key = _NAME_SUFFIXES_RE.sub("", key)    # strip generational suffixes
    return key.strip()

# ============================================================
# END SECTION: Internal Helpers
# ============================================================


# ============================================================
# SECTION: Scraper 1 — ESPN NBA Injury Report
# ============================================================

def scrape_espn_injury_report():
    """
    Scrape the ESPN NBA injury report page.

    URL: https://www.espn.com/nba/injuries

    Parses HTML tables for each team's injury list.  Each row contains
    player name, position, injury date, status, and a comment.

    Returns:
        dict: {player_name_lower: {
                  "status":      str,
                  "injury":      str,   # body part / injury type
                  "team":        str,   # team name from ESPN
                  "return_date": str,   # always "" (ESPN does not publish)
                  "comment":     str,   # ESPN injury comment
                  "source":      "espn",
              }}
        Empty dict on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print("scrape_espn_injury_report: requests/bs4 not installed — skipped")
        return {}

    resp = _safe_get(ESPN_INJURIES_URL)
    if resp is None:
        print("scrape_espn_injury_report: failed to fetch ESPN injuries page")
        return {}

    results = {}
    try:
        soup = BeautifulSoup(resp.text, "lxml")

        # ESPN injury page structure: sections per team, each with a table
        # Each team section has an <h2> or similar with team name,
        # followed by a <table> with tbody rows.
        team_sections = soup.find_all("div", class_=lambda c: c and "Table__Title" in c)

        for section in team_sections:
            team_name = section.get_text(strip=True)
            # Find the next sibling table
            table = None
            sibling = section.find_next_sibling()
            while sibling:
                if sibling.name == "table" or sibling.find("table"):
                    table = sibling.find("table") if sibling.name != "table" else sibling
                    break
                sibling = sibling.find_next_sibling()

            if table is None:
                continue

            rows = table.find("tbody", recursive=False)
            if rows is None:
                rows = table.find("tbody")
            if rows is None:
                continue

            for row in rows.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                # ESPN columns (may vary): Name | Pos | Date | Status | Comment
                name_cell = cells[0].get_text(strip=True)
                pos_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                date_cell = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                status_cell = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                comment_cell = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                player_name = name_cell.strip()
                if not player_name:
                    continue

                canonical_status = _canonicalize_status(status_cell)
                key = player_name.lower().strip()

                results[key] = {
                    "status": canonical_status,
                    "injury": comment_cell or date_cell,
                    "team": team_name,
                    "return_date": "",
                    "comment": comment_cell,
                    "source": "espn",
                }

        print(f"scrape_espn_injury_report: {len(results)} players found")
    except Exception as exc:
        print(f"scrape_espn_injury_report: parse error — {exc}")

    return results

# ============================================================
# END SECTION: Scraper 1 — ESPN NBA Injury Report
# ============================================================


# ============================================================
# SECTION: Scraper 2 — Basketball-Reference Per-Game Stats
# ============================================================

def scrape_bref_season_stats():
    """
    Scrape the Basketball-Reference NBA per-game stats table for the
    current season (2025-26).

    URL: https://www.basketball-reference.com/leagues/NBA_2026_per_game.html

    Rate limiting: enforces a 3-second delay before the request to stay
    within Basketball-Reference's published limit of 20 requests/minute.

    Returns:
        list[dict]: Each dict contains:
            player_name, team, position, games_played, mpg, ppg, rpg,
            apg, threes_pm, spg, bpg, tov, ft_pct, usg_pct
        Empty list on failure.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print("scrape_bref_season_stats: requests/bs4 not installed — skipped")
        return []

    print(f"scrape_bref_season_stats: waiting {_BREF_DELAY}s to respect rate limit")
    time.sleep(_BREF_DELAY)

    resp = _safe_get(BREF_PER_GAME_URL)
    if resp is None:
        print("scrape_bref_season_stats: failed to fetch Basketball-Reference page")
        return []

    results = []
    try:
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", id="per_game_stats")
        if table is None:
            # Try generic table fallback
            table = soup.find("table", class_=lambda c: c and "stats_table" in c)
        if table is None:
            print("scrape_bref_season_stats: stats table not found on page")
            return []

        def _safe_float(val, default=0.0):
            try:
                return float(val) if val and val != "" else default
            except (ValueError, TypeError):
                return default

        tbody = table.find("tbody")
        if tbody is None:
            return []

        seen_players = set()
        for row in tbody.find_all("tr"):
            # Skip header rows interspersed in the table body
            if row.get("class") and "thead" in row.get("class"):
                continue
            if row.find("th", {"data-stat": "ranker"}) is None and row.find("td") is None:
                continue

            cells = {td["data-stat"]: td.get_text(strip=True)
                     for td in row.find_all("td") if td.get("data-stat")}
            if not cells:
                continue

            player_name = cells.get("player", "").strip()
            if not player_name or player_name == "Player":
                continue

            # Skip duplicate rows (multi-team players appear multiple times)
            # Keep the "TOT" (total) row if present
            team = cells.get("team_id", cells.get("team", ""))
            if player_name in seen_players and team != "TOT":
                continue
            seen_players.add(player_name)

            results.append({
                "player_name": player_name,
                "team": team,
                "position": cells.get("pos", ""),
                "games_played": int(_safe_float(cells.get("g", "0"))),
                "mpg": _safe_float(cells.get("mp_per_g", cells.get("mp", "0"))),
                "ppg": _safe_float(cells.get("pts_per_g", cells.get("pts", "0"))),
                "rpg": _safe_float(cells.get("trb_per_g", cells.get("trb", "0"))),
                "apg": _safe_float(cells.get("ast_per_g", cells.get("ast", "0"))),
                "threes_pm": _safe_float(cells.get("fg3_per_g", cells.get("fg3", "0"))),
                "spg": _safe_float(cells.get("stl_per_g", cells.get("stl", "0"))),
                "bpg": _safe_float(cells.get("blk_per_g", cells.get("blk", "0"))),
                "tov": _safe_float(cells.get("tov_per_g", cells.get("tov", "0"))),
                "ft_pct": _safe_float(cells.get("ft_pct", "0")),
                "usg_pct": _safe_float(cells.get("usg_pct", "0")),
            })

        print(f"scrape_bref_season_stats: {len(results)} player rows parsed")
    except Exception as exc:
        print(f"scrape_bref_season_stats: parse error — {exc}")

    return results

# ============================================================
# END SECTION: Scraper 2 — Basketball-Reference Per-Game Stats
# ============================================================


# ============================================================
# SECTION: Consolidated Multi-Source Injury Fetcher
# ============================================================

def fetch_multi_source_injury_status(todays_games=None):
    """
    Fetch and merge injury status from all available web sources.

    Priority (highest wins):
        1. NBA.com Official — authoritative designation
        2. RotoWire         — fastest updates, GTD granularity
        3. ESPN             — broad coverage

    Args:
        todays_games (list|None): Tonight's games (used for logging context).

    Returns:
        dict: {player_name_lower: {
                  "status":      str,
                  "injury":      str,
                  "injury_note": str,
                  "team":        str,
                  "return_date": str,
                  "comment":     str,
                  "source":      str,
              }}
        Empty dict if all scrapers fail.
    """
    if not _SCRAPER_DEPS_AVAILABLE:
        print(
            "fetch_multi_source_injury_status: requests/bs4 not installed — "
            "Layer 5 skipped.  Run: pip install requests beautifulsoup4 lxml"
        )
        return {}

    # ── Existing core scrapers (NBA.com + RotoWire) ──────────────
    core_data = {}
    if _CORE_SCRAPER_AVAILABLE and fetch_all_injury_data is not None:
        try:
            core_data = fetch_all_injury_data()
            print(
                f"fetch_multi_source_injury_status: core scrapers returned "
                f"{len(core_data)} players"
            )
        except Exception as exc:
            print(f"fetch_multi_source_injury_status: core scrapers raised: {exc}")
    else:
        # Run individual scrapers if the re-export failed
        rotowire_data = {}
        nba_data = {}
        try:
            rotowire_data = scrape_rotowire_injury_report() if scrape_rotowire_injury_report else {}
        except Exception as exc:
            print(f"fetch_multi_source_injury_status: RotoWire raised: {exc}")
        try:
            nba_data = scrape_nba_official_injury_report() if scrape_nba_official_injury_report else {}
        except Exception as exc:
            print(f"fetch_multi_source_injury_status: NBA.com raised: {exc}")
        # Merge: RotoWire first, NBA.com overrides
        core_data = {**rotowire_data, **nba_data}

    # ── ESPN scraper ─────────────────────────────────────────────
    espn_data = {}
    try:
        espn_data = scrape_espn_injury_report()
        print(
            f"fetch_multi_source_injury_status: ESPN returned {len(espn_data)} players"
        )
    except Exception as exc:
        print(f"fetch_multi_source_injury_status: ESPN raised: {exc}")

    # ── Merge: ESPN first (lowest priority), then core (higher priority) ──
    merged = {}

    for key, entry in espn_data.items():
        merged[key] = {
            "status":      entry.get("status", "Unknown"),
            "injury":      entry.get("injury", ""),
            "injury_note": entry.get("comment", entry.get("injury", "")),
            "team":        entry.get("team", ""),
            "return_date": entry.get("return_date", ""),
            "comment":     entry.get("comment", ""),
            "source":      "espn",
        }

    for key, entry in core_data.items():
        if key in merged:
            # Core data overrides ESPN
            existing = merged[key]
            existing["status"]      = entry.get("status", existing["status"])
            existing["injury"]      = entry.get("injury", "") or existing["injury"]
            existing["injury_note"] = entry.get("injury", "") or existing["injury_note"]
            existing["return_date"] = entry.get("return_date", "") or existing["return_date"]
            existing["comment"]     = entry.get("comment", "") or existing["comment"]
            src = entry.get("source", "")
            existing["source"] = f"{src}+espn" if src else "espn"
        else:
            merged[key] = {
                "status":      entry.get("status", "Unknown"),
                "injury":      entry.get("injury", ""),
                "injury_note": entry.get("injury", ""),
                "team":        entry.get("team", ""),
                "return_date": entry.get("return_date", ""),
                "comment":     entry.get("comment", ""),
                "source":      entry.get("source", "unknown"),
            }

    # ── Final deduplication + normalization pass ──────────────
    # Some scrapers return names with suffixes (e.g. "Jr.", "III").
    # Re-key using _normalize_player_key so lookup is consistent
    # regardless of suffix differences between sources.
    normalized_merged = {}
    for raw_key, entry in merged.items():
        norm_key = _normalize_player_key(raw_key)
        if norm_key and norm_key not in normalized_merged:
            normalized_merged[norm_key] = entry
        elif norm_key in normalized_merged:
            # Keep the entry with higher-severity status
            _SEV = {
                "Out": 5, "Injured Reserve": 5, "Doubtful": 4,
                "GTD": 3, "Questionable": 3, "Day-to-Day": 2,
                "Probable": 1, "Active": 0, "Unknown": -1,
            }
            existing_sev = _SEV.get(normalized_merged[norm_key]["status"], -1)
            new_sev = _SEV.get(entry["status"], -1)
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
        f"fetch_multi_source_injury_status complete: {total} players — "
        f"{out_count} Out, {gtd_count} GTD/Questionable/Doubtful"
    )
    return merged

# ============================================================
# END SECTION: Consolidated Multi-Source Injury Fetcher
# ============================================================


# ============================================================
# SECTION: Consolidated Roster Fetcher
# ============================================================

def fetch_verified_rosters(team_abbrevs, todays_games=None):
    """
    Fetch and cross-validate rosters for a list of team abbreviations.

    Primary source: nba_api CommonTeamRoster
    Validation:     Cross-references against RotoWire active roster
                    (players listed as injured on RotoWire are flagged)

    Args:
        team_abbrevs (list[str]): Team abbreviations, e.g. ["LAL", "BOS"]
        todays_games (list|None): Tonight's games (optional context).

    Returns:
        dict: {team_abbrev: [player_name, ...]}
              Players flagged as inactive are excluded from the list.
    """
    verified = {}

    # ── Step 1: Get rosters via nba_api ──────────────────────────
    nba_api_rosters = {}
    try:
        from nba_api.stats.endpoints import CommonTeamRoster
        from nba_api.stats.static import teams as nba_static_teams
        import time as _time

        all_nba_teams = {t["abbreviation"]: t["id"] for t in nba_static_teams.get_teams()}

        for abbrev in (team_abbrevs or []):
            team_id = all_nba_teams.get(abbrev)
            if not team_id:
                continue
            try:
                _time.sleep(1.0)  # respect nba_api rate limits
                roster_resp = CommonTeamRoster(team_id=team_id)
                roster_df = roster_resp.get_data_frames()[0]
                players = roster_df["PLAYER"].tolist() if "PLAYER" in roster_df.columns else []
                nba_api_rosters[abbrev] = players
                print(f"fetch_verified_rosters: {abbrev} → {len(players)} players via nba_api")
            except Exception as exc:
                print(f"fetch_verified_rosters: nba_api failed for {abbrev}: {exc}")
                nba_api_rosters[abbrev] = []
    except ImportError:
        print("fetch_verified_rosters: nba_api not available")

    if not nba_api_rosters:
        return {}

    # ── Step 2: Fetch Rotowire injury list for cross-reference ────
    rotowire_injured = set()
    try:
        if scrape_rotowire_injury_report is not None:
            rw_data = scrape_rotowire_injury_report()
            # Players listed on Rotowire injury report are considered injured/inactive
            for key, entry in rw_data.items():
                if entry.get("status", "") in (
                    "Out", "Injured Reserve", "Doubtful", "GTD", "Day-to-Day", "Questionable"
                ):
                    rotowire_injured.add(key)
    except Exception as exc:
        print(f"fetch_verified_rosters: Rotowire cross-ref failed: {exc}")

    # ── Step 3: Build verified roster — flag discrepancies ────────
    discrepancy_log = []
    for abbrev, players in nba_api_rosters.items():
        active_players = []
        for player in players:
            player_key = player.lower().strip()
            if player_key in rotowire_injured:
                discrepancy_log.append(
                    f"{player} ({abbrev}): on nba_api roster but flagged injured by Rotowire"
                )
            else:
                active_players.append(player)
        verified[abbrev] = active_players

    if discrepancy_log:
        print(
            f"fetch_verified_rosters: {len(discrepancy_log)} discrepancies found:\n  "
            + "\n  ".join(discrepancy_log)
        )

    return verified

# ============================================================
# END SECTION: Consolidated Roster Fetcher
# ============================================================


# ============================================================
# SECTION: Convenience function for tonight's active players
# ============================================================

def get_active_players_for_tonight(todays_games: list) -> dict:
    """
    Convenience wrapper: uses RosterEngine to return active (non-injured)
    players for every team playing tonight.

    Both web_scraper.py and web_scrapers.py delegate to the same
    RosterEngine so there is a single source of truth for roster + injury
    logic.  This function is the preferred entry-point for callers that
    import from web_scrapers.

    Args:
        todays_games (list): List of game dicts with 'home_team'/'away_team'.

    Returns:
        dict: {team_abbrev: [player_name, ...]}  — injured players excluded.
    """
    try:
        from data.roster_engine import get_active_players_for_tonight as _re_fn
        return _re_fn(todays_games)
    except Exception as exc:
        print(f"get_active_players_for_tonight (web_scrapers): {exc}")
        return {}

# ============================================================
# END SECTION: Convenience function for tonight's active players
# ============================================================
