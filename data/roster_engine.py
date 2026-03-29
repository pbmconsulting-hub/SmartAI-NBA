# ============================================================
# FILE: data/roster_engine.py
# PURPOSE: Centralised active-roster and injury resolution engine.
#          Uses nba_api as the single authoritative data source for
#          both roster and injury data, with proper retry logic,
#          circuit breakers, caching, and unified header management.
#
# DATA SOURCES (in priority order):
#   0. Official NBA Injury Report PDF — highest-authority source
#   1. nba-injury-report PyPI package (programmatic NBA injury PDF data)
#   2. ESPN public injury API (site.api.espn.com)
#   3. CBS Sports injury scraper (if available)
#   4. Rotowire HTML injury scraper (final fallback)
#   5. nba_api CommonTeamRoster   — authoritative roster (trades/signings)
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
        Fetch fresh data from multiple sources in priority order.

        Sources used (in order):
            0. Official NBA Injury Report PDF — highest-authority source
            1. nba_api live Injuries endpoint — daily injury designations
            2. nba_api CommonTeamRoster       — official roster + two-way status

        Args:
            team_abbrevs: List of team abbreviations to fetch rosters for.
                          If None, only the injury data is refreshed.
        """
        _logger.info("RosterEngine.refresh() — starting data pull")
        merged: dict = {}

        # ── Source 0: Official NBA Injury Report PDF ──────────────
        src0 = self._fetch_official_pdf_injuries()
        for k, v in src0.items():
            merged[k] = _merge_entry(merged.get(k, {}), v)
        _logger.info(f"  Source 0 (official PDF): {len(src0)} players")

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
    # Source 0: Official NBA Injury Report PDF
    # ----------------------------------------------------------

    def _fetch_official_pdf_injuries(self) -> dict:
        """
        Fetch the official NBA Injury Report PDF and return a normalised
        injury dict compatible with the rest of the RosterEngine pipeline.

        Requires ``pdfplumber`` to be installed.  If the package is absent or
        the report cannot be retrieved the method returns an empty dict so the
        existing Sources 1–3 remain unaffected.

        Returns:
            Dict of {normalized_name: {status, injury, team, return_date,
            source, game_date, game_time, matchup}} entries, or ``{}`` on any
            failure.
        """
        try:
            from data.nba_injury_pdf import get_report
        except ImportError as exc:
            _logger.debug(f"RosterEngine._fetch_official_pdf_injuries: import error — {exc}")
            return {}

        try:
            df = get_report(auto_discover=True)
            if df.empty:
                return {}

            result: dict = {}
            for _, row in df.iterrows():
                name   = str(row.get("Player Name", "") or "").strip()
                status = _normalize_status(str(row.get("Current Status", "") or ""))
                injury = str(row.get("Reason", "") or "").strip()
                team   = str(row.get("Team", "") or "").strip()
                if not name:
                    continue
                key = _normalize_name(name)
                result[key] = {
                    "status":      status,
                    "injury":      injury,
                    "team":        team,
                    "return_date": "",
                    "source":      "nba-official-pdf",
                    "game_date":   str(row.get("Game Date", "") or "").strip(),
                    "game_time":   str(row.get("Game Time", "") or "").strip(),
                    "matchup":     str(row.get("Matchup", "") or "").strip(),
                }
            _logger.info(
                f"  RosterEngine._fetch_official_pdf_injuries: "
                f"PDF source returned {len(result)} players"
            )
            return result
        except Exception as exc:
            _logger.info(f"  RosterEngine._fetch_official_pdf_injuries: {exc}")
            return {}

    # ----------------------------------------------------------
    # Source 1: nba_api live Injuries endpoint
    # ----------------------------------------------------------

    def _fetch_nba_api_injuries(self) -> dict:
        """
        Fetch today's injury report via multiple sources with fallback.

        Sources tried in order:
          1. nba-injury-report PyPI package (programmatic NBA injury PDF data)
          2. ESPN public injury API (site.api.espn.com)
          3. CBS Sports injury scraper (if available)
          4. Rotowire HTML injury scraper (final fallback)

        Falls back to an empty dict if all sources fail.
        """
        import requests as _requests  # local import to avoid top-level dep for optional feature

        # ── Source 1: nba-injury-report PyPI package ──────────
        try:
            from nba_injury_report import get_injury_report as _get_nba_injury_report
            report = _get_nba_injury_report()
            injuries_list = report.to_list()
            if injuries_list:
                result1: dict = {}
                for entry in injuries_list:
                    name = str(entry.get("Player Name", "") or "")
                    if not name:
                        continue
                    key = _normalize_name(name)
                    result1[key] = {
                        "status":      _normalize_status(str(entry.get("Current Status", "") or "")),
                        "injury":      str(entry.get("Reason", "") or ""),
                        "team":        str(entry.get("Team", "") or ""),
                        "return_date": "",
                        "source":      "nba-injury-report-pkg",
                    }
                if result1:
                    _logger.info(f"  RosterEngine._fetch_nba_api_injuries: nba-injury-report-pkg source returned {len(result1)} players")
                    return result1
        except ImportError:
            _logger.debug("  RosterEngine._fetch_nba_api_injuries: nba-injury-report not installed, skipping")
        except Exception as exc1:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries nba-injury-report-pkg: {exc1}")

        # ── Source 2: ESPN public injury API ──────────────────────
        try:
            _espn_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
            resp2 = _requests.get(
                _espn_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
                timeout=10,
            )
            resp2.raise_for_status()
            espn_data = resp2.json()
            result2: dict = {}

            # ESPN may return injuries under several different top-level keys.
            # Priority: "leagues" list (each with "injuries") > "items" / "teams" (each with "injuries")
            league_blocks = espn_data.get("leagues", [])
            if league_blocks:
                # Structure: {"leagues": [{"injuries": [...], ...}, ...]}
                for league_block in league_blocks:
                    for athlete in league_block.get("injuries", []):
                        name = ""
                        athlete_obj = athlete.get("athlete", {})
                        if athlete_obj:
                            name = athlete_obj.get("displayName", athlete_obj.get("fullName", ""))
                        team_abbr = ""
                        team_obj = athlete.get("team", {})
                        if team_obj:
                            team_abbr = team_obj.get("abbreviation", "")
                        raw_status = athlete.get("status", "")
                        if isinstance(raw_status, dict):
                            raw_status = raw_status.get("name", raw_status.get("type", ""))
                        status = _normalize_status(str(raw_status or ""))
                        injury_desc = athlete.get("longComment", athlete.get("comment", athlete.get("shortComment", "")))
                        if not name:
                            continue
                        key = _normalize_name(name)
                        result2[key] = {
                            "status":      status,
                            "injury":      str(injury_desc or ""),
                            "team":        str(team_abbr or ""),
                            "return_date": "",
                            "source":      "espn-injuries",
                        }
            else:
                # Structure: {"items": [...]} or {"teams": [...]} each team block has "injuries"
                for team_block in espn_data.get("items", espn_data.get("teams", [])):
                    team_abbr = ""
                    team_obj = team_block.get("team", {})
                    if team_obj:
                        team_abbr = team_obj.get("abbreviation", "")
                    for athlete in team_block.get("injuries", []):
                        name = ""
                        athlete_obj = athlete.get("athlete", {})
                        if athlete_obj:
                            name = athlete_obj.get("displayName", athlete_obj.get("fullName", ""))
                        raw_status = athlete.get("status", "")
                        if isinstance(raw_status, dict):
                            raw_status = raw_status.get("name", raw_status.get("type", ""))
                        status = _normalize_status(str(raw_status or ""))
                        injury_desc = athlete.get("longComment", athlete.get("comment", athlete.get("shortComment", "")))
                        if not name:
                            continue
                        key = _normalize_name(name)
                        result2[key] = {
                            "status":      status,
                            "injury":      str(injury_desc or ""),
                            "team":        str(team_abbr or ""),
                            "return_date": "",
                            "source":      "espn-injuries",
                        }
            if result2:
                _logger.info(f"  RosterEngine._fetch_nba_api_injuries: ESPN source returned {len(result2)} players")
                return result2
        except Exception as exc2:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries ESPN: {exc2}")

        # ── Source 3: CBS Sports scraper (if available) ───────────
        try:
            from engine.scrapers.cbs_injuries_scraper import get_injury_report
            cbs_list = get_injury_report()
            if cbs_list:
                result3: dict = {}
                for item in cbs_list:
                    name = item.get("player", "")
                    if not name:
                        continue
                    key = _normalize_name(name)
                    result3[key] = {
                        "status":      _normalize_status(item.get("status", "")),
                        "injury":      str(item.get("injury", "") or ""),
                        "team":        str(item.get("team", "") or ""),
                        "return_date": str(item.get("date", "") or ""),
                        "source":      "cbs-injuries",
                    }
                if result3:
                    _logger.info(f"  RosterEngine._fetch_nba_api_injuries: CBS source returned {len(result3)} players")
                    return result3
        except Exception as exc3:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries CBS: {exc3}")

        # ── Source 4: Rotowire HTML scraper (final fallback) ──────
        try:
            from bs4 import BeautifulSoup as _BeautifulSoup
            time.sleep(3)
            _roto_url = "https://www.rotowire.com/basketball/injury-report.php"
            resp4 = _requests.get(
                _roto_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.rotowire.com/",
                },
                timeout=15,
            )
            resp4.raise_for_status()
            soup4 = _BeautifulSoup(resp4.text, "lxml")
            result4: dict = {}
            for row in soup4.select("li.lineup__player") or soup4.select("tr.injury-report__row") or []:
                # Try table row structure first
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name        = cells[0].get_text(strip=True)
                    team_abbr   = cells[1].get_text(strip=True)
                    status_text = cells[2].get_text(strip=True)
                    injury_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    return_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                else:
                    continue
                if not name:
                    continue
                key = _normalize_name(name)
                result4[key] = {
                    "status":      _normalize_status(status_text),
                    "injury":      injury_text,
                    "team":        team_abbr,
                    "return_date": return_text,
                    "source":      "rotowire-injuries",
                }
            if result4:
                _logger.info(f"  RosterEngine._fetch_nba_api_injuries: Rotowire source returned {len(result4)} players")
                return result4
        except ImportError:
            _logger.debug("  RosterEngine._fetch_nba_api_injuries: beautifulsoup4/lxml not installed, skipping Rotowire")
        except Exception as exc4:
            _logger.info(f"  RosterEngine._fetch_nba_api_injuries Rotowire: {exc4}")

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
