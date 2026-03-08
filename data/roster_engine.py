# ============================================================
# FILE: data/roster_engine.py
# PURPOSE: Centralised active-roster and injury resolution engine.
#          Replaces scattered scraping logic across web_scraper.py /
#          web_scrapers.py / live_data_fetcher.py with a single class
#          that aggregates four independent data sources and applies
#          consistent filtering rules.
#
# DATA SOURCES (in priority order):
#   1. NBA.com CDN JSON       — static schedule + injury feed (no rate-limit)
#   2. Live Injury JSON       — cdn.nba.com daily injury file
#   3. RotoWire scraper       — four CSS-selector fallback strategies
#   4. ESPN scraper           — ResponsiveTable selector
#   5. nba_api CommonTeamRoster — validation layer only
#
# FILTERING RULES:
#   - Hard-exclude: Out / Inactive / IR / Injured Reserve / Doubtful (< 25% chance)
#   - Flag (keep with warning): GTD / Day-to-Day / Questionable / Probable
#   - Active: everything else
#
# USAGE:
#   from data.roster_engine import RosterEngine
#   engine = RosterEngine()
#   engine.refresh(["LAL", "BOS"])
#   active = engine.get_active_roster("LAL")   # → ["LeBron James", ...]
#   ok, reason = engine.is_player_active("LeBron James", "LAL")
# ============================================================

import re
import time
import json
import datetime
import os
from pathlib import Path
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPER_DEPS_AVAILABLE = True
except ImportError:
    _SCRAPER_DEPS_AVAILABLE = False

# ============================================================
# SECTION: Module-level constants
# ============================================================

# CDN / API endpoints
NBA_CDN_SCHEDULE_URL = (
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
)
NBA_STATS_TEAM_ROSTER_URL = (
    "https://stats.nba.com/stats/commonteamroster"
)
NBA_HTML_INJURY_URL = "https://www.nba.com/players/injuries"

# Daily live-injury CDN file (YYYYMMDD)
def _today_cdn_injury_url():
    date_str = datetime.date.today().strftime("%Y%m%d")
    return f"https://cdn.nba.com/static/json/liveData/injuries/injuries_{date_str}.json"

# RotoWire
ROTOWIRE_INJURY_URL = "https://www.rotowire.com/basketball/injury-report.php"

# ESPN
ESPN_INJURIES_URL = "https://www.espn.com/nba/injuries"

# HTTP headers
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}
_NBA_STATS_HEADERS = {
    **_HEADERS,
    "Host": "stats.nba.com",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

# ── Exclusion/flag status sets ────────────────────────────────────

# Players with these statuses are fully removed from the active roster
EXCLUDE_STATUSES = frozenset({
    "Out",
    "Inactive",
    "IR",
    "Injured Reserve",
    "Doubtful",
    "Suspended",
    "Not With Team",
    "G League - Two-Way",
    "G League - On Assignment",
    "G League",
    "Out (No Recent Games)",
})

# Players with these statuses are KEPT but flagged (warning badge)
FLAG_STATUSES = frozenset({
    "GTD",
    "Game Time Decision",
    "Day-to-Day",
    "Questionable",
})

# Players with these statuses are treated as fully active
ACTIVE_STATUSES = frozenset({
    "Active",
    "Probable",
    "Available",
})

# Canonical normalisation map for raw status strings from scrapers
_STATUS_NORM = {
    "out":                "Out",
    "out for season":     "Out",
    "inactive":           "Inactive",
    "ir":                 "Injured Reserve",
    "injured reserve":    "Injured Reserve",
    "suspended":          "Suspended",
    "not with team":      "Not With Team",
    "g league":           "G League",
    "g league - two-way": "G League - Two-Way",
    "g league - on assignment": "G League - On Assignment",
    "doubtful":           "Doubtful",
    "game time decision": "GTD",
    "gtd":                "GTD",
    "day-to-day":         "Day-to-Day",
    "day to day":         "Day-to-Day",
    "dtd":                "Day-to-Day",
    "questionable":       "Questionable",
    "probable":           "Probable",
    "active":             "Active",
    "available":          "Active",
}

# Severity ordering for conflict resolution (higher = more severe)
_SEVERITY = {
    "Out": 9, "Injured Reserve": 9, "Inactive": 9, "Suspended": 8,
    "Not With Team": 8, "G League - Two-Way": 8, "G League - On Assignment": 8,
    "G League": 8, "Out (No Recent Games)": 9,
    "Doubtful": 7,
    "Questionable": 5, "GTD": 5, "Game Time Decision": 5,
    "Day-to-Day": 4,
    "Probable": 2,
    "Active": 1,
    "Unknown": 0,
}

# Name-suffix regex for normalisation
_SUFFIX_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)\s*$", re.IGNORECASE
)

# ============================================================
# END SECTION: Module-level constants
# ============================================================


# ============================================================
# SECTION: Internal helpers
# ============================================================

def _normalize_name(name: str) -> str:
    """Lowercase, strip whitespace and common suffixes for fuzzy matching."""
    n = name.lower().strip()
    n = _SUFFIX_RE.sub("", n).strip()
    return n


def _normalize_status(raw: str) -> str:
    """Map a raw status string to our canonical label."""
    key = (raw or "").lower().strip()
    return _STATUS_NORM.get(key, raw.title() if raw else "Active")


def _severity(status: str) -> int:
    return _SEVERITY.get(status, 0)


def _get_with_retry(url, params=None, headers=None, timeout=REQUEST_TIMEOUT):
    """HTTP GET with exponential-backoff retry.  Returns Response or None."""
    if not _SCRAPER_DEPS_AVAILABLE:
        return None
    hdrs = headers or _HEADERS
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
        except requests.RequestException as exc:
            wait = 2 ** attempt
            print(f"RosterEngine: GET {url} attempt {attempt + 1} failed: {exc}. Retry in {wait}s")
            time.sleep(wait)
    return None


def _merge_entry(target: dict, incoming: dict) -> dict:
    """Merge *incoming* into *target*, keeping the more-severe status."""
    if not target:
        return incoming.copy()
    if _severity(incoming.get("status", "Active")) > _severity(target.get("status", "Active")):
        target["status"]  = incoming["status"]
        target["injury"]  = incoming.get("injury", "") or target.get("injury", "")
        target["source"]  = incoming.get("source", target.get("source", ""))
    target["team"]        = target.get("team") or incoming.get("team", "")
    target["return_date"] = target.get("return_date") or incoming.get("return_date", "")
    return target

# ============================================================
# END SECTION: Internal helpers
# ============================================================


# ============================================================
# SECTION: RosterEngine class
# ============================================================

class RosterEngine:
    """
    Single-responsibility class for active-roster and injury resolution.

    Usage pattern (called once per analysis session):
        engine = RosterEngine()
        engine.refresh(["LAL", "BOS"])          # populate caches
        active = engine.get_active_roster("LAL") # list of active names
        ok, reason = engine.is_player_active("LeBron James", "LAL")
        report = engine.get_injury_report()      # full injury dict
    """

    def __init__(self):
        # {normalized_player_name → {status, injury, team, return_date, source}}
        self._injury_map: dict = {}
        # {team_abbrev → [player_name, ...]}  — all names from nba_api roster
        self._full_rosters: dict = {}
        # {team_abbrev → [player_name, ...]}  — filtered active-only
        self._active_rosters: dict = {}
        self._last_refresh: Optional[datetime.datetime] = None

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def get_active_roster(self, team_abbrev: str) -> list:
        """Return ONLY confirmed-active player names for a team."""
        team = team_abbrev.upper().strip()
        if team in self._active_rosters:
            return list(self._active_rosters[team])
        # Build from full roster + injury map on-demand
        full = self._full_rosters.get(team, [])
        active = [
            p for p in full
            if self.is_player_active(p, team)[0]
        ]
        self._active_rosters[team] = active
        return active

    def is_player_active(self, player_name: str, team_abbrev: str = None) -> tuple:
        """
        Returns (is_active: bool, reason_if_not: str).

        A player is inactive if ANY source marks them as Out / IR / Doubtful etc.
        GTD / Questionable players return (True, "GTD: <reason>") — kept but flagged.
        """
        norm_key = _normalize_name(player_name)
        entry = self._injury_map.get(norm_key, {})
        status = entry.get("status", "Active")

        if status in EXCLUDE_STATUSES:
            reason = entry.get("injury", status)
            src = entry.get("source", "")
            return False, f"{status}: {reason}" + (f" [{src}]" if src else "")

        if status in FLAG_STATUSES:
            reason = entry.get("injury", status)
            return True, f"{status}: {reason}"

        return True, ""

    def get_injury_report(self) -> dict:
        """
        Return the full merged injury map.

        Format: {player_name_lower: {status, injury, team, return_date, source}}
        """
        return dict(self._injury_map)

    def refresh(self, team_abbrevs: list = None):
        """
        Fetch fresh data from all sources.

        Args:
            team_abbrevs: List of team abbreviations to fetch rosters for.
                          If None, only the injury data sources are refreshed.
        """
        print("RosterEngine.refresh() — starting multi-source data pull")
        merged: dict = {}

        # ── Source 1: NBA.com CDN injury report (JSON) ─────────────
        src1 = self._fetch_nba_cdn_injury()
        for k, v in src1.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        print(f"  Source 1 (NBA CDN):  {len(src1)} players")

        # ── Source 2: Live daily CDN injury file ──────────────────
        src2 = self._fetch_live_cdn_injury()
        for k, v in src2.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        print(f"  Source 2 (Live CDN): {len(src2)} players")

        # ── Source 3: RotoWire ────────────────────────────────────
        src3 = self._fetch_rotowire()
        for k, v in src3.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        print(f"  Source 3 (RotoWire): {len(src3)} players")

        # ── Source 4: ESPN ────────────────────────────────────────
        src4 = self._fetch_espn()
        for k, v in src4.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        print(f"  Source 4 (ESPN):     {len(src4)} players")

        self._injury_map = merged

        # ── Source 5 (validation): nba_api CommonTeamRoster ──────
        if team_abbrevs:
            self._fetch_nba_api_rosters(team_abbrevs)

        # Invalidate active-roster cache
        self._active_rosters = {}
        self._last_refresh = datetime.datetime.now()
        out_count = sum(1 for v in merged.values() if v.get("status") in EXCLUDE_STATUSES)
        print(
            f"RosterEngine.refresh() complete: {len(merged)} injured players "
            f"({out_count} hard-excluded)"
        )

    # ----------------------------------------------------------
    # Source 1: NBA.com CDN static injury JSON
    # ----------------------------------------------------------

    def _fetch_nba_cdn_injury(self) -> dict:
        result: dict = {}
        try:
            resp = _get_with_retry(
                "https://cdn.nba.com/static/json/staticData/InjuryReport.json",
                headers=_HEADERS,
            )
            if not resp:
                return {}
            data = resp.json()
            # The InjuryReport JSON has different possible shapes depending on feed version
            # Try multiple common shapes
            report = data if isinstance(data, dict) else {}
            injury_list = (
                report.get("InjuryList", [])
                or report.get("players", [])
                or (report.get("resultSets", [{}])[0].get("rowSet", []) if report.get("resultSets") else [])
            )
            for item in injury_list:
                if isinstance(item, dict):
                    name = item.get("Name", item.get("PLAYER_NAME", item.get("playerName", "")))
                    status = _normalize_status(
                        item.get("Status", item.get("PLAYER_STATUS", item.get("status", "")))
                    )
                    injury = item.get("Comment", item.get("Injury", item.get("injury", "")))
                    team = item.get("TeamAbbreviation", item.get("TEAM_ABBREVIATION", item.get("team", "")))
                elif isinstance(item, list):
                    # rowSet format: [team_abbrev, ..., player_name, ..., status]
                    name   = item[2] if len(item) > 2 else ""
                    status = _normalize_status(item[4] if len(item) > 4 else "")
                    injury = item[5] if len(item) > 5 else ""
                    team   = item[0] if len(item) > 0 else ""
                else:
                    continue

                if not name:
                    continue
                key = _normalize_name(name)
                result[key] = {
                    "status":      status,
                    "injury":      str(injury or ""),
                    "team":        str(team or ""),
                    "return_date": "",
                    "source":      "NBA-CDN",
                }
        except Exception as exc:
            print(f"RosterEngine._fetch_nba_cdn_injury: {exc}")
        return result

    # ----------------------------------------------------------
    # Source 2: Live daily CDN injury file
    # ----------------------------------------------------------

    def _fetch_live_cdn_injury(self) -> dict:
        result: dict = {}
        try:
            url = _today_cdn_injury_url()
            resp = _get_with_retry(url, headers=_HEADERS)
            if not resp:
                return {}
            data = resp.json()
            # Shape: {"injuryReport": {"injuredPlayers": [...]}}
            injured = (
                data.get("injuryReport", {}).get("injuredPlayers", [])
                or data.get("injuredPlayers", [])
                or data.get("players", [])
            )
            for item in (injured or []):
                name   = item.get("playerName", item.get("name", ""))
                status = _normalize_status(item.get("status", item.get("playerStatus", "")))
                injury = item.get("injuryDescription", item.get("injury", item.get("comment", "")))
                team   = item.get("teamAbbreviation", item.get("teamTricode", item.get("team", "")))
                if not name:
                    continue
                key = _normalize_name(name)
                result[key] = {
                    "status":      status,
                    "injury":      str(injury or ""),
                    "team":        str(team or ""),
                    "return_date": "",
                    "source":      "NBA-Live-CDN",
                }
        except Exception as exc:
            print(f"RosterEngine._fetch_live_cdn_injury: {exc}")
        return result

    # ----------------------------------------------------------
    # Source 3: RotoWire — four CSS-selector fallback strategies
    # ----------------------------------------------------------

    def _fetch_rotowire(self) -> dict:
        result: dict = {}
        if not _SCRAPER_DEPS_AVAILABLE:
            return result
        try:
            resp = _get_with_retry(ROTOWIRE_INJURY_URL, headers=_HEADERS)
            if not resp:
                return result
            soup = BeautifulSoup(resp.text, "html.parser")

            # Strategy A: ul.injury-report li items
            found = self._rw_strategy_a(soup)
            if found:
                return found

            # Strategy B: div[class*="injury"] containers
            found = self._rw_strategy_b(soup)
            if found:
                return found

            # Strategy C: table with Player/Team/Status headers
            found = self._rw_strategy_c(soup)
            if found:
                return found

            # Strategy D: tr rows containing Out / GTD / Questionable
            found = self._rw_strategy_d(soup)
            return found

        except Exception as exc:
            print(f"RosterEngine._fetch_rotowire: {exc}")
        return result

    def _rw_strategy_a(self, soup) -> dict:
        """Strategy A: ul.injury-report li items."""
        result = {}
        items = soup.select("ul.injury-report li")
        for li in items:
            name_el   = li.select_one(".player-name, .name, [class*='player']")
            status_el = li.select_one(".status, [class*='status']")
            team_el   = li.select_one(".team, [class*='team']")
            injury_el = li.select_one(".injury, [class*='injury'], .detail")
            name   = name_el.get_text(strip=True) if name_el else ""
            status = _normalize_status(status_el.get_text(strip=True) if status_el else "")
            team   = team_el.get_text(strip=True) if team_el else ""
            injury = injury_el.get_text(strip=True) if injury_el else ""
            if name and status:
                result[_normalize_name(name)] = {
                    "status": status, "injury": injury,
                    "team": team, "return_date": "", "source": "RotoWire-A",
                }
        return result

    def _rw_strategy_b(self, soup) -> dict:
        """Strategy B: div[class*='injury'] containers."""
        result = {}
        containers = soup.select("div[class*='injury']")
        for div in containers:
            rows = div.select("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.select("td")]
                if len(cells) < 3:
                    continue
                # Heuristic: last cell or cell containing Out/GTD is status
                name = cells[0]
                status_raw = next(
                    (c for c in cells if c.lower() in _STATUS_NORM), cells[-1]
                )
                status = _normalize_status(status_raw)
                injury = cells[2] if len(cells) > 2 else ""
                team   = cells[1] if len(cells) > 1 else ""
                if name and status not in ("Active", "Unknown"):
                    result[_normalize_name(name)] = {
                        "status": status, "injury": injury,
                        "team": team, "return_date": "", "source": "RotoWire-B",
                    }
        return result

    def _rw_strategy_c(self, soup) -> dict:
        """Strategy C: any <table> with Player/Team/Status headers."""
        result = {}
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.select("th")]
            if not any(h in ("player", "name") for h in headers):
                continue
            try:
                name_idx   = next(i for i, h in enumerate(headers) if h in ("player", "name"))
                status_idx = next(i for i, h in enumerate(headers) if "status" in h)
                team_idx   = next((i for i, h in enumerate(headers) if "team" in h), None)
                injury_idx = next((i for i, h in enumerate(headers) if "injury" in h or "detail" in h), None)
            except StopIteration:
                continue
            for row in table.select("tr"):
                cells = [td.get_text(strip=True) for td in row.select("td")]
                if len(cells) <= max(i for i in [name_idx, status_idx] if i is not None):
                    continue
                name   = cells[name_idx]
                status = _normalize_status(cells[status_idx])
                team   = cells[team_idx] if team_idx is not None and team_idx < len(cells) else ""
                injury = cells[injury_idx] if injury_idx is not None and injury_idx < len(cells) else ""
                if name and status not in ("Active",):
                    result[_normalize_name(name)] = {
                        "status": status, "injury": injury,
                        "team": team, "return_date": "", "source": "RotoWire-C",
                    }
        return result

    def _rw_strategy_d(self, soup) -> dict:
        """Strategy D: any <tr> rows where a cell contains Out/GTD/Questionable."""
        result = {}
        _TARGET = {"out", "gtd", "questionable", "doubtful", "day-to-day"}
        for row in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            matching = [c for c in cells if c.lower() in _TARGET or c.lower() in _STATUS_NORM]
            if not matching:
                continue
            status = _normalize_status(matching[0])
            # First cell is usually the player name
            name = cells[0] if cells else ""
            if name and name.lower() not in _STATUS_NORM and status not in ("Active",):
                result[_normalize_name(name)] = {
                    "status": status, "injury": "",
                    "team": "", "return_date": "", "source": "RotoWire-D",
                }
        return result

    # ----------------------------------------------------------
    # Source 4: ESPN — ResponsiveTable selector (primary)
    # ----------------------------------------------------------

    def _fetch_espn(self) -> dict:
        result: dict = {}
        if not _SCRAPER_DEPS_AVAILABLE:
            return result
        try:
            resp = _get_with_retry(ESPN_INJURIES_URL, headers=_HEADERS)
            if not resp:
                return result
            soup = BeautifulSoup(resp.text, "html.parser")

            # Primary: div.ResponsiveTable
            tables = soup.select("div.ResponsiveTable")
            for table_div in tables:
                # Team name is usually in a heading above the table
                team_heading = table_div.find_previous(["h3", "h4", "span"], class_=re.compile(r"team|title|headline", re.I))
                team = team_heading.get_text(strip=True) if team_heading else ""

                rows = table_div.select("tr")
                headers = [th.get_text(strip=True).lower() for th in table_div.select("th")]
                try:
                    name_idx   = next(i for i, h in enumerate(headers) if "name" in h or "athlete" in h)
                    status_idx = next(i for i, h in enumerate(headers) if "status" in h)
                    injury_idx = next((i for i, h in enumerate(headers) if "injury" in h or "comment" in h), None)
                except StopIteration:
                    # Fallback: use column positions 0=name, 1=pos, 2=date, 3=injury, 4=status
                    for row in rows:
                        cells = [td.get_text(strip=True) for td in row.select("td")]
                        if len(cells) < 3:
                            continue
                        name   = cells[0]
                        status_raw = cells[-1] if cells else ""
                        injury = cells[3] if len(cells) > 3 else ""
                        status = _normalize_status(status_raw)
                        if name and status not in ("Active", "Unknown", ""):
                            result[_normalize_name(name)] = {
                                "status": status, "injury": injury,
                                "team": team, "return_date": "", "source": "ESPN",
                            }
                    continue

                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.select("td")]
                    if len(cells) <= max(i for i in [name_idx, status_idx] if i is not None):
                        continue
                    name   = cells[name_idx]
                    status = _normalize_status(cells[status_idx])
                    injury = cells[injury_idx] if injury_idx is not None and injury_idx < len(cells) else ""
                    if name and status not in ("Active", "Unknown", ""):
                        result[_normalize_name(name)] = {
                            "status": status, "injury": injury,
                            "team": team, "return_date": "", "source": "ESPN",
                        }
        except Exception as exc:
            print(f"RosterEngine._fetch_espn: {exc}")
        return result

    # ----------------------------------------------------------
    # Source 5 (validation): nba_api CommonTeamRoster
    # ----------------------------------------------------------

    def _fetch_nba_api_rosters(self, team_abbrevs: list):
        """
        Fetch full rosters from nba_api and store them.
        Cross-check against injury map: remove excluded players.
        """
        try:
            from nba_api.stats.endpoints import CommonTeamRoster
            from nba_api.stats.static import teams as nba_static_teams
        except ImportError:
            print("RosterEngine._fetch_nba_api_rosters: nba_api not available")
            return

        all_teams = {t["abbreviation"]: t["id"] for t in nba_static_teams.get_teams()}

        for abbrev in (team_abbrevs or []):
            team_id = all_teams.get(abbrev.upper())
            if not team_id:
                print(f"  RosterEngine: no team_id for {abbrev}")
                continue
            try:
                time.sleep(1.0)
                resp = CommonTeamRoster(team_id=team_id)
                df = resp.get_data_frames()[0]
                players = df["PLAYER"].tolist() if "PLAYER" in df.columns else []
                self._full_rosters[abbrev.upper()] = players
                print(f"  RosterEngine nba_api: {abbrev} → {len(players)} players")
            except Exception as exc:
                print(f"  RosterEngine nba_api error for {abbrev}: {exc}")

# ============================================================
# END SECTION: RosterEngine class
# ============================================================


# ============================================================
# SECTION: Convenience function
# ============================================================

def get_active_players_for_tonight(todays_games: list) -> dict:
    """
    Convenience wrapper: refresh RosterEngine for tonight's teams and
    return {team_abbrev: [active_player_names]} for every team playing.

    Args:
        todays_games (list): List of game dicts with 'home_team'/'away_team'.

    Returns:
        dict: {team_abbrev: [player_name, ...]}  — injured players excluded.
    """
    team_abbrevs = set()
    for game in (todays_games or []):
        ht = game.get("home_team", "").upper().strip()
        at = game.get("away_team", "").upper().strip()
        if ht:
            team_abbrevs.add(ht)
        if at:
            team_abbrevs.add(at)
    team_abbrevs.discard("")

    engine = RosterEngine()
    engine.refresh(list(team_abbrevs))

    result = {}
    for abbrev in team_abbrevs:
        result[abbrev] = engine.get_active_roster(abbrev)
    return result

# ============================================================
# END SECTION: Convenience function
# ============================================================
