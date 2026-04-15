# ============================================================
# FILE: data/roster_engine.py
# PURPOSE: Centralised active-roster and injury resolution engine.
#          Uses the RotoWire injury report ETL (etl/rotowire_injuries.py)
#          as the **sole** injury data source, with nba_api
#          CommonTeamRoster for roster data, retry logic, circuit
#          breakers, caching, and unified header management.
#
# INJURY DATA SOURCE:
#   RotoWire injury report — scraped by etl/rotowire_injuries.py,
#   stored in the Injury_Status table in db/smartpicks.db.
#   The RosterEngine reads from this DB table first; if unavailable,
#   it falls back to a live RotoWire scrape via the ETL module.
#
# ROSTER DATA SOURCE:
#   nba_api CommonTeamRoster — authoritative roster (trades/signings)
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
from typing import Any, Optional

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

try:
    from utils.headers import get_nba_headers, get_cdn_headers
    _HAS_HEADERS = True
except ImportError:
    _HAS_HEADERS = False

try:
    from utils.retry import retry_with_backoff, CircuitBreaker
    _HAS_RETRY = True
except ImportError:
    _HAS_RETRY = False

try:
    from utils.cache import FileCache
    _HAS_FILE_CACHE = True
except ImportError:
    _HAS_FILE_CACHE = False

# curl_cffi provides TLS browser-impersonation; kept for potential roster
# fetch use but no longer needed for injury data (now sourced from RotoWire ETL).
try:
    from curl_cffi import requests as _curl_requests
    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _curl_requests = None  # type: ignore[assignment]
    _CURL_CFFI_AVAILABLE = False

# ============================================================
# SECTION: Module-level constants
# ============================================================

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

# Circuit breakers for failing endpoints
if _HAS_RETRY:
    _cdn_circuit = CircuitBreaker(name="cdn_injuries", failure_threshold=3, timeout=60)
    _stats_circuit = CircuitBreaker(name="stats_injuries", failure_threshold=3, timeout=60)
else:
    _cdn_circuit = None
    _stats_circuit = None


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

    # Team ID mapping for NBA.com
    TEAM_IDS = {
        'ATL': '1610612737', 'BOS': '1610612738', 'BKN': '1610612751',
        'CHA': '1610612766', 'CHI': '1610612741', 'CLE': '1610612739',
        'DAL': '1610612742', 'DEN': '1610612743', 'DET': '1610612765',
        'GSW': '1610612744', 'HOU': '1610612745', 'IND': '1610612754',
        'LAC': '1610612746', 'LAL': '1610612747', 'MEM': '1610612763',
        'MIA': '1610612748', 'MIL': '1610612749', 'MIN': '1610612750',
        'NOP': '1610612740', 'NYK': '1610612752', 'OKC': '1610612760',
        'ORL': '1610612753', 'PHI': '1610612755', 'PHX': '1610612756',
        'POR': '1610612757', 'SAC': '1610612758', 'SAS': '1610612759',
        'TOR': '1610612761', 'UTA': '1610612762', 'WAS': '1610612764',
        # ESPN aliases
        'UTAH': '1610612762', 'WSH': '1610612764',
    }

    def __init__(self):
        # {normalized_player_name → {status, injury, team, return_date, source}}
        self._injury_map: dict = {}
        # {team_abbrev → [player_name, ...]}  — all names from nba_api roster
        self._full_rosters: dict = {}
        # {team_abbrev → [player_name, ...]}  — filtered active-only
        self._active_rosters: dict = {}
        self._last_refresh: Optional[datetime.datetime] = None
        self._file_cache: Any = None  # Optional[FileCache] when utils.cache available
        if _HAS_FILE_CACHE:
            try:
                self._file_cache = FileCache(cache_dir="cache/roster", ttl_hours=1)
            except Exception:
                pass

    # ----------------------------------------------------------
    # Team ID helper
    # ----------------------------------------------------------

    def get_team_id(self, team_abbrev: str) -> Optional[str]:
        """Get NBA.com team ID from abbreviation."""
        return self.TEAM_IDS.get(team_abbrev.upper().strip())

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
        Fetch fresh data from the RotoWire injury ETL and nba_api rosters.

        Sources used:
            1. RotoWire injury report (DB table or live scrape fallback)
            2. nba_api CommonTeamRoster — official roster + two-way status

        Args:
            team_abbrevs: List of team abbreviations to fetch rosters for.
                          If None, only the injury data is refreshed.
        """
        _logger.info("RosterEngine.refresh() — starting data pull")
        merged: dict = {}

        # ── Single injury source: RotoWire ETL ───────────────────
        src = self._fetch_rotowire_injuries()
        for k, v in src.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        _logger.info(f"  RotoWire injury source: {len(src)} players")

        self._injury_map = merged

        # ── nba_api CommonTeamRoster (primary roster) ────────────
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
    # Single injury source: RotoWire ETL (DB + live fallback)
    # ----------------------------------------------------------

    def _fetch_rotowire_injuries(self) -> dict:
        """
        Fetch injury data from the RotoWire-populated ``Injury_Status``
        database table.  If the DB is unavailable or empty, falls back to
        a live RotoWire scrape via ``etl.rotowire_injuries``.

        Returns:
            Dict of {normalized_name: {status, injury, team, return_date,
            source}} entries, or ``{}`` on any failure.
        """
        # ── Try 1: Read from the Injury_Status DB table ──────────
        try:
            from data.etl_data_service import _get_conn as _etl_conn
            _db = _etl_conn()
            if _db is not None:
                try:
                    _tbl_check = _db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='Injury_Status'"
                    ).fetchone()
                    if _tbl_check:
                        # Get only the latest report_date's records
                        _latest = _db.execute(
                            "SELECT MAX(report_date) FROM Injury_Status"
                        ).fetchone()
                        _latest_date = _latest[0] if _latest else None
                        if _latest_date:
                            _inj_rows = _db.execute(
                                "SELECT COALESCE(p.full_name, p.first_name || ' ' || p.last_name) AS player_name, "
                                "       i.status, "
                                "       i.reason     AS injury, "
                                "       COALESCE(t.abbreviation, p.team_abbreviation) AS team "
                                "FROM Injury_Status i "
                                "JOIN Players p ON p.player_id = i.player_id "
                                "LEFT JOIN Teams t ON t.team_id = i.team_id "
                                "WHERE i.report_date = ?",
                                (_latest_date,),
                            ).fetchall()
                            if _inj_rows:
                                result: dict = {}
                                for _ir in _inj_rows:
                                    _name = str(_ir["player_name"] or "")
                                    if not _name:
                                        continue
                                    _key = _normalize_name(_name)
                                    result[_key] = {
                                        "status":      _normalize_status(str(_ir["status"] or "")),
                                        "injury":      str(_ir["injury"] or ""),
                                        "team":        str(_ir["team"] or ""),
                                        "return_date": "",
                                        "source":      "rotowire",
                                    }
                                if result:
                                    _logger.info(
                                        f"  RosterEngine._fetch_rotowire_injuries: "
                                        f"DB source returned {len(result)} players "
                                        f"(report_date={_latest_date})"
                                    )
                                    return result
                finally:
                    _db.close()
        except Exception as db_exc:
            _logger.info(f"  RosterEngine._fetch_rotowire_injuries DB: {db_exc}")

        # ── Try 2: Live RotoWire scrape via ETL module ───────────
        try:
            from etl.rotowire_injuries import (
                fetch_injury_page,
                parse_injury_table,
            )
            html = fetch_injury_page()
            raw_rows = parse_injury_table(html)
            if raw_rows:
                result2: dict = {}
                for row in raw_rows:
                    _name = row.get("player_name", "")
                    if not _name:
                        continue
                    _key = _normalize_name(_name)
                    result2[_key] = {
                        "status":      _normalize_status(row.get("status", "")),
                        "injury":      str(row.get("reason", "") or ""),
                        "team":        str(row.get("team_abbrev", "") or ""),
                        "return_date": str(row.get("est_return", "") or ""),
                        "source":      "rotowire",
                    }
                if result2:
                    _logger.info(
                        f"  RosterEngine._fetch_rotowire_injuries: "
                        f"live scrape returned {len(result2)} players"
                    )
                    return result2
        except Exception as scrape_exc:
            _logger.info(f"  RosterEngine._fetch_rotowire_injuries live scrape: {scrape_exc}")

        _logger.info("  RosterEngine._fetch_rotowire_injuries: all sources returned 0 players")
        return {}

    # ----------------------------------------------------------
    # Roster source: nba_api CommonTeamRoster (primary roster)
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
        # ── DB first ──────────────────────────────────────────
        db_hit = False
        try:
            from data.etl_data_service import _get_conn
            conn = _get_conn()
            if conn is not None:
                try:
                    for abbrev in (team_abbrevs or []):
                        rows = conn.execute(
                            "SELECT COALESCE(p.full_name, p.first_name || ' ' || p.last_name) AS full_name, "
                            "       tr.is_two_way "
                            "FROM Team_Roster tr "
                            "JOIN Players p ON p.player_id = tr.player_id "
                            "JOIN Teams  t ON t.team_id   = tr.team_id "
                            "WHERE t.abbreviation = ? "
                            "  AND tr.effective_end_date IS NULL",
                            (abbrev.upper(),),
                        ).fetchall()
                        if rows:
                            all_players = []
                            for r in rows:
                                name = str(r["full_name"] or "")
                                if not name:
                                    continue
                                all_players.append(name)
                                if r["is_two_way"]:
                                    key = _normalize_name(name)
                                    existing = self._injury_map.get(key, {})
                                    if _severity(existing.get("status", "Active")) < _severity("G League - Two-Way"):
                                        self._injury_map[key] = {
                                            "status":      "G League - Two-Way",
                                            "injury":      "Two-way contract",
                                            "team":        abbrev.upper(),
                                            "return_date": "",
                                            "source":      "db-roster",
                                        }
                            self._full_rosters[abbrev.upper()] = all_players
                            db_hit = True
                            _logger.info("  RosterEngine DB: %s → %d players", abbrev, len(all_players))
                finally:
                    conn.close()
            if db_hit and all(
                a.upper() in self._full_rosters for a in (team_abbrevs or [])
            ):
                _logger.info("RosterEngine: all %d teams loaded from DB.", len(team_abbrevs or []))
                return
        except Exception as db_err:
            _logger.debug("RosterEngine DB roster fallback failed: %s", db_err)

        # ── Live API fallback ─────────────────────────────────
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

    # ----------------------------------------------------------
    # get_team_roster: convenience wrapper for CommonTeamRoster
    # ----------------------------------------------------------

    def get_team_roster(self, team_abbrev: str) -> list:
        """Get full roster for a team via CommonTeamRoster API.

        Returns a list of dicts with keys: name, id, position, number, team.
        """
        try:
            from nba_api.stats.endpoints import CommonTeamRoster
            from nba_api.stats.static import teams as nba_static_teams
        except ImportError:
            _logger.warning("RosterEngine.get_team_roster: nba_api not available")
            return []

        team_id = self.get_team_id(team_abbrev)
        if not team_id:
            all_teams = {t["abbreviation"]: t["id"] for t in nba_static_teams.get_teams()}
            team_id = all_teams.get(team_abbrev.upper())
        if not team_id:
            _logger.warning(f"Could not find team ID for {team_abbrev}")
            return []

        try:
            roster = CommonTeamRoster(team_id=team_id)
            df = roster.get_data_frames()[0]

            players = []
            for _, row in df.iterrows():
                players.append({
                    'name': row.get('PLAYER', ''),
                    'id': row.get('PLAYER_ID', ''),
                    'position': row.get('POSITION', ''),
                    'number': row.get('NUM', ''),
                    'team': team_abbrev.upper(),
                })
            return players
        except Exception as e:
            _logger.error(f"Failed to fetch roster for {team_abbrev}: {e}")
            return []

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
