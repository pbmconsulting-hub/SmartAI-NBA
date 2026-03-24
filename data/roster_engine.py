# ============================================================
# FILE: data/roster_engine.py
# PURPOSE: Centralised active-roster and injury resolution engine.
#          Uses API-NBA API as the primary data source for
#          both roster and injury data.
#
# DATA SOURCES (in priority order):
#   1. API-NBA injury report  — daily injury designations (Out/GTD/Doubtful)
#   2. API-NBA team rosters   — authoritative roster (trades/signings)
#
# FILTERING RULES:
#   - Hard-exclude: Out / Inactive / IR / Injured Reserve / Doubtful (< 25% chance)
#   - Flag (keep with warning): GTD / Day-to-Day / Questionable / Probable
#   - Active: everything else
#   - Two-way / G-League assigned players are always excluded from rosters
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
import datetime
from typing import Optional

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# ============================================================
# SECTION: Module-level constants
# ============================================================

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3


def _current_nba_season():
    """
    Return the current NBA season string in 'YYYY-YY' format.

    The NBA season starts in October. If the current month is October or later,
    the season is current_year-(current_year+1). Otherwise it's (current_year-1)-current_year.
    Example: October 2024 → '2024-25'; April 2025 → '2024-25'.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.month >= 10:
        start_year = now.year
    else:
        start_year = now.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"

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


def _parse_injured_list(injured_list: list, source_name: str) -> dict:
    """
    Convert a raw list of player injury dicts (from any source) into the
    canonical {normalized_name: {status, injury, team, return_date, source}} format.

    The function handles several field-name variants used across NBA CDN,
    stats.nba.com, and nba_api response formats.
    """
    result: dict = {}
    for item in (injured_list or []):
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
            "source":      source_name,
        }
    return result

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
        # {team_abbrev → [player_name, ...]}  — all names from API-NBA roster
        self._full_rosters: dict = {}
        # {team_abbrev → [player_name, ...]}  — filtered active-only
        self._active_rosters: dict = {}
        self._last_refresh: Optional[datetime.datetime] = None

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def get_full_roster(self, team_abbrev: str) -> list:
        """Return ALL player names on a team's roster, regardless of injury status.

        Unlike get_active_roster(), this includes players who are Out, IR,
        or otherwise unavailable.  Use this when you need the complete roster
        for a team (e.g., to retrieve stats for every player before injury
        filtering is applied as a separate step).

        Args:
            team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL').

        Returns:
            list[str]: All player names on the roster.
        """
        return list(self._full_rosters.get(team_abbrev.upper().strip(), []))

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
        Retrieve fresh data from API-NBA API — the single authoritative source.

        Sources used (in order):
            1. API-NBA injury report endpoint — daily injury designations
            2. API-NBA rosters endpoint       — official roster per team

        Args:
            team_abbrevs: List of team abbreviations to retrieve rosters for.
                          If None, only the injury data is refreshed.
        """
        _logger.info("RosterEngine.refresh() — starting data pull (API-NBA)")
        merged: dict = {}

        # ── Source 1: API-NBA injury report ──────────────────
        src1 = self._load_api_injuries()
        for k, v in src1.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        _logger.info(f"  Source 1 (API-NBA injuries): {len(src1)} players")

        self._injury_map = merged

        # ── Source 2: API-NBA rosters ────────────────────────
        if team_abbrevs:
            self._load_api_rosters(team_abbrevs)

        # Invalidate active-roster cache
        self._active_rosters = {}
        self._last_refresh = datetime.datetime.now(datetime.timezone.utc)
        out_count = sum(1 for v in self._injury_map.values() if v.get("status") in EXCLUDE_STATUSES)
        _logger.info(
            f"RosterEngine.refresh() complete: {len(self._injury_map)} injured/flagged players "
            f"({out_count} hard-excluded)"
        )

    # ----------------------------------------------------------
    # Source 1: API-NBA injury report
    # ----------------------------------------------------------

    def _load_api_injuries(self) -> dict:
        """
        Retrieve today's injury report from API-NBA API.

        Falls back to NBA CDN public injury JSON feed if API-NBA fails.
        Returns an empty dict if all sources fail.
        """
        try:
            from data.nba_api_client import get_injury_report as _cs_injuries
            raw_injuries = _cs_injuries()
            if raw_injuries:
                result = {}
                for player_name_lower, info in raw_injuries.items():
                    norm_key = _normalize_name(player_name_lower)
                    raw_status = info.get("status", "Out")
                    status = _normalize_status(raw_status)
                    result[norm_key] = {
                        "status": status,
                        "injury": info.get("injury_note", ""),
                        "team": "",
                        "return_date": info.get("return_date", ""),
                        "source": "API-NBA",
                    }
                return result
        except Exception as err:
            _logger.warning(f"API-NBA injury retrieval failed: {err}")

        # Fallback: NBA CDN public injury JSON
        return self._load_nba_cdn_injuries()

    def _load_nba_cdn_injuries(self) -> dict:
        """
        Fallback: retrieve injury data from NBA's public CDN JSON feed.

        Tries two CDN URLs — the static-data path and the headlineinjuries
        path — in case one is blocked.  Falls back to the stats.nba.com
        ``playerindex`` endpoint as a last resort.
        """
        import requests as _requests

        _NBA_HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate, br",
        }

        result = {}

        # ── Attempt 1: primary CDN static-data URL ────────────────────────
        cdn_urls = [
            "https://cdn.nba.com/static/json/staticData/injuries.json",
            "https://cdn.nba.com/static/json/staticData/headlineinjuries.json",
        ]
        for cdn_url in cdn_urls:
            try:
                resp = _requests.get(cdn_url, headers=_NBA_HEADERS, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                injuries = (
                    data.get("data", {}).get("PlayerInjuries", [])
                    or data.get("data", {}).get("injuries", [])
                    or []
                )
                for player in injuries:
                    player_name = str(player.get("playerName", "") or "").strip()
                    status_raw = str(player.get("injuryStatus", "") or "").strip()
                    injury_note = str(player.get("injuryText", "") or "").strip()
                    team = str(player.get("teamTricode", "") or "").strip().upper()

                    if not player_name:
                        continue

                    norm_key = _normalize_name(player_name)
                    status = _normalize_status(status_raw)

                    result[norm_key] = {
                        "status": status,
                        "injury": injury_note,
                        "team": team,
                        "return_date": "",
                        "source": "NBA CDN",
                    }

                if result:
                    _logger.info(f"  NBA CDN injuries: {len(result)} players")
                    return result
            except Exception as cdn_err:
                _logger.warning(f"NBA CDN injury URL failed ({cdn_url}): {cdn_err}")

        # ── Attempt 2: stats.nba.com playerindex (more reliable) ──────────
        try:
            _stats_headers = dict(_NBA_HEADERS)
            _stats_headers.update({
                "x-nba-stats-origin": "stats",
                "x-nba-stats-token": "true",
                "Host": "stats.nba.com",
            })
            from data.nba_stats_backup import _current_season_str
            season = _current_season_str()
            resp = _requests.get(
                "https://stats.nba.com/stats/playerindex",
                headers=_stats_headers,
                params={
                    "Season": season,
                    "LeagueID": "00",
                    "IsOnlyCurrentSeason": "1",
                },
                timeout=45,
            )
            if resp.status_code == 200:
                data = resp.json()
                rs = data.get("resultSets", [{}])[0]
                headers_list = [h.lower() for h in (rs.get("headers") or [])]
                for row_vals in (rs.get("rowSet") or []):
                    row = dict(zip(headers_list, row_vals))
                    # Only include players that have an injury indicator
                    injury_col = row.get("injury_indicator") or ""
                    if not injury_col:
                        continue
                    first = str(row.get("player_first_name", "") or "")
                    last = str(row.get("player_last_name", "") or "")
                    pname = f"{first} {last}".strip()
                    if not pname:
                        continue
                    norm_key = _normalize_name(pname)
                    result[norm_key] = {
                        "status": _normalize_status(injury_col),
                        "injury": "",
                        "team": str(row.get("team_abbreviation", "") or "").upper(),
                        "return_date": "",
                        "source": "NBA stats",
                    }
                if result:
                    _logger.info(f"  NBA stats.nba.com playerindex injuries: {len(result)} players")
        except Exception as stats_err:
            _logger.warning(f"stats.nba.com playerindex injury fallback failed: {stats_err}")

        if not result:
            _logger.warning("All NBA CDN/stats injury fallbacks returned 0 players")

        return result

    # ----------------------------------------------------------
    # Source 2: API-NBA rosters endpoint
    # ----------------------------------------------------------

    def _load_api_rosters(self, team_abbrevs: list):
        """
        Retrieve full rosters from API-NBA API, store in _full_rosters.
        """
        try:
            from data.nba_api_client import get_rosters as _cs_rosters
            rosters = _cs_rosters(list(team_abbrevs))
            for abbrev, players in rosters.items():
                self._full_rosters[abbrev.upper()] = players
                _logger.info(f"  RosterEngine API-NBA: {abbrev} → {len(players)} players")
        except Exception as err:
            _logger.warning(f"API-NBA roster retrieval failed: {err}")

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
