# ============================================================
# FILE: data/roster_engine.py
# PURPOSE: Centralised active-roster and injury resolution engine.
#          Aggregates data from official free sources and applies
#          consistent filtering rules.
#
# DATA SOURCES (in priority order):
#   1. NBA.com CDN JSON       — static injury feed (no rate-limit, free)
#   2. Live Injury JSON       — cdn.nba.com daily injury file (free)
#   3. nba_api CommonTeamRoster — official roster + G-League/two-way status
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
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

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
    if not _REQUESTS_AVAILABLE:
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
        # {team_abbrev → [{player_id, player_name, position}, ...]}  — full roster details
        self._full_roster_details: dict = {}
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

    def get_full_roster_details(self, team_abbrev: str) -> list:
        """
        Return full roster details for a team, including player_id and position.

        Returns:
            list of dict: [{player_id, player_name, position}, ...]
                          Two-way / G-League players are included here; callers
                          should use is_player_active() to filter if needed.
        """
        return list(self._full_roster_details.get(team_abbrev.upper(), []))

    def refresh(self, team_abbrevs: list = None):
        """
        Fetch fresh data from official free sources.

        Sources used (in order):
            1. NBA.com CDN static injury JSON  — no rate-limit, always free
            2. Live daily CDN injury JSON      — no rate-limit, always free
            3. nba_api CommonTeamRoster        — official roster + status filter

        Args:
            team_abbrevs: List of team abbreviations to fetch rosters for.
                          If None, only the injury data sources are refreshed.
        """
        print("RosterEngine.refresh() — starting data pull")
        merged: dict = {}

        # ── Source 1: NBA.com CDN static injury JSON ───────────────
        src1 = self._fetch_nba_cdn_injury()
        for k, v in src1.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        print(f"  Source 1 (NBA CDN):      {len(src1)} players")

        # ── Source 2: Live daily CDN injury file ──────────────────
        src2 = self._fetch_live_cdn_injury()
        for k, v in src2.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        print(f"  Source 2 (Live CDN):     {len(src2)} players")

        self._injury_map = merged

        # ── Source 3: nba_api CommonTeamRoster (primary) ──────────
        # Fetches official rosters and also flags G-League / two-way players.
        if team_abbrevs:
            self._fetch_nba_api_rosters(team_abbrevs)

        # Invalidate active-roster cache
        self._active_rosters = {}
        self._last_refresh = datetime.datetime.now()
        out_count = sum(1 for v in self._injury_map.values() if v.get("status") in EXCLUDE_STATUSES)
        print(
            f"RosterEngine.refresh() complete: {len(self._injury_map)} injured players "
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
    # Source 3: nba_api CommonTeamRoster (primary roster source)
    # ----------------------------------------------------------

    def _fetch_nba_api_rosters(self, team_abbrevs: list):
        """
        Fetch full rosters from nba_api, store them in _full_rosters,
        and update the injury map for G-League / two-way contract players.

        CommonTeamRoster is the authoritative source for who is currently
        on an NBA roster (reflects all trades and signings).  Players
        on two-way contracts who are on G-League assignment are flagged
        as inactive so they are excluded from tonight's active roster.
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

                all_players = []
                all_player_details = []
                _POSITION_MAP = {
                    "G": "PG", "F": "SF", "C": "C",
                    "G-F": "SF", "F-G": "SG", "F-C": "PF", "C-F": "PF",
                    "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF",
                    "": "SF",
                }
                for _, row in df.iterrows():
                    player_name = row.get("PLAYER", "")
                    if not player_name:
                        continue

                    player_id = row.get("PLAYER_ID")
                    raw_pos   = str(row.get("POSITION", "") or "")
                    position  = _POSITION_MAP.get(raw_pos, raw_pos if raw_pos else "SF")

                    all_players.append(player_name)
                    all_player_details.append({
                        "player_id":   player_id,
                        "player_name": player_name,
                        "position":    position,
                    })

                    # Flag two-way / G-League players as inactive
                    player_type  = str(row.get("PLAYER_TYPE",  "") or "").lower()
                    how_acquired = str(row.get("HOW_ACQUIRED", "") or "").lower()
                    if "two-way" in player_type or "two-way" in how_acquired:
                        key = _normalize_name(player_name)
                        existing = self._injury_map.get(key, {})
                        if _severity(existing.get("status", "Active")) < _severity("G League - Two-Way"):
                            self._injury_map[key] = {
                                "status":      "G League - Two-Way",
                                "injury":      "Two-way contract",
                                "team":        abbrev.upper(),
                                "return_date": "",
                                "source":      "nba_api",
                            }
                        print(f"  Flagged two-way player: {player_name} ({abbrev})")

                self._full_rosters[abbrev.upper()] = all_players
                self._full_roster_details[abbrev.upper()] = all_player_details
                print(f"  RosterEngine nba_api: {abbrev} → {len(all_players)} players")
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
