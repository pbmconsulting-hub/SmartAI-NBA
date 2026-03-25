# ============================================================
# FILE: data/roster_engine.py
# PURPOSE: Centralised active-roster and injury resolution engine.
#          Uses nba_api as the single authoritative data source for
#          both roster and injury data.
#
# DATA SOURCES (in priority order):
#   1. nba_api live Injuries      — daily injury designations (Out/GTD/Doubtful)
#   2. nba_api CommonTeamRoster   — authoritative roster (trades/signings)
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
        # {team_abbrev → [player_name, ...]}  — all names from nba_api roster
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
        for a team (e.g., to fetch stats for every player before injury
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
        Fetch fresh data from nba_api — the single authoritative source.

        Sources used (in order):
            1. nba_api live Injuries endpoint — daily injury designations
            2. nba_api CommonTeamRoster       — official roster + two-way status

        Args:
            team_abbrevs: List of team abbreviations to fetch rosters for.
                          If None, only the injury data is refreshed.
        """
        _logger.info("RosterEngine.refresh() — starting data pull (nba_api sources only)")
        merged: dict = {}

        # ── Source 1: nba_api live Injuries endpoint ──────────────
        src1 = self._fetch_nba_api_injuries()
        for k, v in src1.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        _logger.info(f"  Source 1 (nba_api live injuries): {len(src1)} players")

        self._injury_map = merged

        # ── Source 2: nba_api CommonTeamRoster (primary roster) ───
        if team_abbrevs:
            self._fetch_nba_api_rosters(team_abbrevs)

        # Invalidate active-roster cache
        self._active_rosters = {}
        self._last_refresh = datetime.datetime.now(datetime.timezone.utc)
        out_count = sum(1 for v in self._injury_map.values() if v.get("status") in EXCLUDE_STATUSES)
        _logger.info(
            f"RosterEngine.refresh() complete: {len(self._injury_map)} injured/flagged players "
            f"({out_count} hard-excluded)"
        )

    # ----------------------------------------------------------
    # Source 1: nba_api live Injuries endpoint
    # ----------------------------------------------------------

    def _fetch_nba_api_injuries(self) -> dict:
        """
        Fetch today's injury report via multiple sources with fallback.

        Sources tried in order:
          1. NBA CDN public injury JSON feed
          2. stats.nba.com leagueinjuries endpoint with NBA headers
          3. nba_api Injuries endpoint (if available)

        Falls back to an empty dict if all sources fail.
        """
        import requests as _requests  # local import to avoid top-level dep for optional feature

        # User-Agent kept generic enough to work across NBA endpoints;
        # update the Chrome version string if NBA API starts rejecting requests.
        _NBA_HEADERS = {
            "Host": "stats.nba.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true",
            "Connection": "keep-alive",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
        }

        # ── Source 1: NBA CDN ──────────────────────────────────
        try:
            resp = _requests.get(
                "https://cdn.nba.com/static/json/liveData/injuries/injuries.json",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            injured_list = (
                data.get("league", {}).get("standard", [])
                or data.get("injuries", {}).get("injuredPlayers", [])
                or data.get("injuredPlayers", [])
                or data.get("players", [])
            )
            result = _parse_injured_list(injured_list, "nba-cdn-injuries")
            if result:
                _logger.info(f"  RosterEngine._fetch_nba_api_injuries: CDN source returned {len(result)} players")
                return result
            _logger.info("  RosterEngine._fetch_nba_api_injuries: CDN returned 0 players, trying fallback")
        except Exception as exc:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries CDN: {exc}")

        # ── Source 2: stats.nba.com leagueinjuries ────────────
        try:
            _current_season = _current_nba_season()
            _url = f"https://stats.nba.com/stats/leagueinjuries?LeagueID=00&Season={_current_season}"
            resp2 = _requests.get(_url, headers=_NBA_HEADERS, timeout=12)
            resp2.raise_for_status()
            data2 = resp2.json()
            # Try common response structures
            injured_list2 = (
                data2.get("resultSets", [{}])[0].get("rowSet", [])
                if data2.get("resultSets")
                else data2.get("players", [])
            )
            # If rowSet format, parse columns
            if data2.get("resultSets") and data2["resultSets"][0].get("headers"):
                headers = data2["resultSets"][0]["headers"]
                rows    = data2["resultSets"][0].get("rowSet", [])
                injured_list2 = [dict(zip(headers, row)) for row in rows]
            result2 = _parse_injured_list(injured_list2, "nba-stats-leagueinjuries")
            if result2:
                _logger.info(f"  RosterEngine._fetch_nba_api_injuries: stats.nba.com source returned {len(result2)} players")
                return result2
            _logger.info("  RosterEngine._fetch_nba_api_injuries: stats.nba.com returned 0 players, trying nba_api")
        except Exception as exc2:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries stats.nba.com: {exc2}")

        # ── Source 3: nba_api Injuries endpoint ───────────────
        try:
            from nba_api.stats.endpoints import injuries as _injuries_ep
            inj = _injuries_ep.Injuries(timeout=12)
            inj_df = inj.get_data_frames()[0] if inj.get_data_frames() else None
            if inj_df is not None and not inj_df.empty:
                result3: dict = {}
                for _, row in inj_df.iterrows():
                    name   = str(row.get("Player_Name", row.get("PLAYER_NAME", "")) or "")
                    status = _normalize_status(str(row.get("Status", row.get("STATUS", "")) or ""))
                    injury = str(row.get("Injury", row.get("INJURY", row.get("Comment", "")) or "") or "")
                    team   = str(row.get("Team", row.get("TEAM", "") or "") or "")
                    if not name:
                        continue
                    key = _normalize_name(name)
                    result3[key] = {
                        "status":      status,
                        "injury":      injury,
                        "team":        team,
                        "return_date": "",
                        "source":      "nba_api-injuries",
                    }
                if result3:
                    _logger.info(f"  RosterEngine._fetch_nba_api_injuries: nba_api source returned {len(result3)} players")
                    return result3
        except Exception as exc3:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries nba_api: {exc3}")

        _logger.info("  RosterEngine._fetch_nba_api_injuries: all sources returned 0 players")
        return {}

    # ----------------------------------------------------------
    # Source 2: nba_api CommonTeamRoster (primary roster source)
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
            _logger.warning("RosterEngine._fetch_nba_api_rosters: nba_api not available")
            return

        all_teams = {t["abbreviation"]: t["id"] for t in nba_static_teams.get_teams()}

        for abbrev in (team_abbrevs or []):
            team_id = all_teams.get(abbrev.upper())
            if not team_id:
                _logger.info(f"  RosterEngine: no team_id for {abbrev}")
                continue
            try:
                time.sleep(0.4)
                resp = CommonTeamRoster(team_id=team_id)
                df = resp.get_data_frames()[0]

                all_players = []
                for _, row in df.iterrows():
                    player_name = row.get("PLAYER", "")
                    if not player_name:
                        continue

                    all_players.append(player_name)

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
                        _logger.info(f"  Flagged two-way player: {player_name} ({abbrev})")

                self._full_rosters[abbrev.upper()] = all_players
                _logger.info(f"  RosterEngine nba_api: {abbrev} → {len(all_players)} players")
            except Exception as exc:
                _logger.warning(f"  RosterEngine nba_api error for {abbrev}: {exc}")

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
