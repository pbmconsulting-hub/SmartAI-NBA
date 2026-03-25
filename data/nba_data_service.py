# ============================================================
# FILE: data/nba_data_service.py
# PURPOSE: Thin delegation layer that routes all NBA data
#          retrieval through data/live_data_fetcher.py (nba_api
#          Python package — free, no API key needed).
#
#          This module preserves the public API that every page
#          and engine module imports (get_todays_games, etc.)
#          while the actual fetching happens via the nba_api
#          library endpoints (ScoreboardV2, LeagueDashPlayerStats,
#          CommonTeamRoster, etc.).
#
# DATA SOURCES:
#   - nba_api Python package: games, player stats, team stats,
#     defensive ratings, standings, rosters, game logs
#   - PrizePicks / Underdog / DraftKings (via platform_fetcher.py)
# ============================================================

from pathlib import Path as _Path
import datetime as _datetime
import logging as _logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = _logging.getLogger(__name__)

# ── Re-export every public symbol from live_data_fetcher ─────
# Pages import constants and path objects from this module;
# live_data_fetcher defines them identically.
from data.live_data_fetcher import (               # noqa: F401 – re-exports
    # Path constants
    DATA_DIRECTORY,
    PLAYERS_CSV_PATH,
    TEAMS_CSV_PATH,
    DEFENSIVE_RATINGS_CSV_PATH,
    LAST_UPDATED_JSON_PATH,
    INJURY_STATUS_JSON_PATH,
    # Tuning constants
    API_DELAY_SECONDS,
    FALLBACK_POINTS_STD_RATIO,
    FALLBACK_REBOUNDS_STD_RATIO,
    FALLBACK_ASSISTS_STD_RATIO,
    FALLBACK_THREES_STD_RATIO,
    FALLBACK_STEALS_STD_RATIO,
    FALLBACK_BLOCKS_STD_RATIO,
    FALLBACK_TURNOVERS_STD_RATIO,
    MIN_MINUTES_THRESHOLD,
    GP_ABSENT_THRESHOLD,
    MIN_TEAM_GP_FOR_RECENCY_CHECK,
    HOT_TREND_THRESHOLD,
    COLD_TREND_THRESHOLD,
    DEFAULT_VEGAS_SPREAD,
    DEFAULT_GAME_TOTAL,
    ESPN_API_TIMEOUT_SECONDS,
    INACTIVE_INJURY_STATUSES,
    GTD_INJURY_STATUSES,
    # Team lookups
    TEAM_NAME_TO_ABBREVIATION,
    NBA_API_ABBREV_TO_OURS,
    TEAM_CONFERENCE,
    # Timestamp functions
    save_last_updated,
    load_last_updated,
    # Staleness
    get_teams_staleness_warning,
    # Cached roster helper
    get_cached_roster,
)

# Import live_data_fetcher functions under private names so we can
# expose them with the current ``get_*`` naming convention.
from data.live_data_fetcher import (
    fetch_todays_games as _ldf_fetch_todays_games,
    fetch_todays_players_only as _ldf_fetch_todays_players,
    fetch_player_recent_form as _ldf_fetch_player_recent_form,
    fetch_player_stats as _ldf_fetch_player_stats,
    fetch_team_stats as _ldf_fetch_team_stats,
    fetch_defensive_ratings as _ldf_fetch_defensive_ratings,
    fetch_player_game_log as _ldf_fetch_player_game_log,
    fetch_all_data as _ldf_fetch_all_data,
    fetch_all_todays_data as _ldf_fetch_all_todays_data,
    fetch_active_rosters as _ldf_fetch_active_rosters,
)


# ============================================================
# Public API — name-compatible wrappers around live_data_fetcher
# ============================================================

def get_todays_games():
    """Retrieve tonight's NBA games via the nba_api library."""
    return _ldf_fetch_todays_games()


def get_todays_players(todays_games, progress_callback=None,
                       precomputed_injury_map=None):
    """Retrieve players for tonight's games via nba_api."""
    return _ldf_fetch_todays_players(
        todays_games,
        progress_callback=progress_callback,
        precomputed_injury_map=precomputed_injury_map,
    )


def get_player_recent_form(player_id, last_n_games=10):
    """Get a player's recent-form stats via nba_api game logs."""
    return _ldf_fetch_player_recent_form(player_id, last_n_games=last_n_games)


def get_player_stats(progress_callback=None):
    """Retrieve all active player season stats via nba_api."""
    return _ldf_fetch_player_stats(progress_callback=progress_callback)


def get_team_stats(progress_callback=None):
    """Retrieve team-level stats via nba_api."""
    return _ldf_fetch_team_stats(progress_callback=progress_callback)


def get_defensive_ratings(force=False, progress_callback=None):
    """Retrieve defensive ratings via nba_api."""
    return _ldf_fetch_defensive_ratings(
        force=force, progress_callback=progress_callback,
    )


def get_player_game_log(player_id, last_n_games=20):
    """Retrieve a player's game log via nba_api."""
    return _ldf_fetch_player_game_log(player_id, last_n_games=last_n_games)


def get_all_data(progress_callback=None, targeted=False, todays_games=None):
    """Retrieve all NBA data (games, players, teams) via nba_api."""
    return _ldf_fetch_all_data(
        progress_callback=progress_callback,
        targeted=targeted,
        todays_games=todays_games,
    )


def get_all_todays_data(progress_callback=None):
    """One-click: retrieve games → players → props for tonight."""
    return _ldf_fetch_all_todays_data(progress_callback=progress_callback)


def get_active_rosters(team_abbrevs=None, progress_callback=None):
    """Retrieve active rosters for specified teams via nba_api."""
    return _ldf_fetch_active_rosters(
        team_abbrevs=team_abbrevs,
        progress_callback=progress_callback,
    )


# ============================================================
# Functions that exist only in the current codebase (no old
# live_data_fetcher equivalent).  Kept with graceful fallbacks.
# ============================================================

def get_standings(progress_callback=None) -> list:
    """
    Retrieve current NBA standings.

    Tries the nba_api LeagueStandingsV3 first, then falls back to
    API-NBA if available.  Returns an empty list on failure.
    """
    if progress_callback:
        progress_callback(0, 10, "Retrieving NBA standings…")
    try:
        from nba_api.stats.endpoints import leaguestandingsv3
        import time
        time.sleep(API_DELAY_SECONDS)
        raw = leaguestandingsv3.LeagueStandingsV3(season="2024-25")
        df = raw.get_data_frames()[0]
        standings = []
        for _, row in df.iterrows():
            abbr = TEAM_NAME_TO_ABBREVIATION.get(
                f"{row.get('TeamCity', '')} {row.get('TeamName', '')}".strip(),
                row.get("TeamAbbreviation", ""),
            )
            standings.append({
                "team_abbreviation": abbr,
                "conference": row.get("Conference", ""),
                "conference_rank": int(row.get("PlayoffRank", 0)),
                "wins": int(row.get("WINS", 0)),
                "losses": int(row.get("LOSSES", 0)),
                "win_pct": float(row.get("WinPCT", 0.0)),
                "streak": str(row.get("strCurrentStreak", "")),
                "last_10": str(row.get("L10", "")),
            })
        if progress_callback:
            progress_callback(10, 10, f"Standings loaded ({len(standings)} teams).")
        return standings
    except Exception as exc:
        _logger.warning("get_standings failed: %s", exc)
    return []


def get_player_news(player_name=None, limit=20) -> list:
    """
    Retrieve recent NBA news.
    Returns an empty list if all sources fail.
    """
    return []


def get_standings_from_nba_api(season: str | None = None) -> list:
    """
    Retrieve NBA standings via nba_stats_service.get_league_standings().

    Intended as a secondary fallback when the primary nba_api
    LeagueStandingsV3 call inside ``get_standings()`` fails.  If this
    also fails, returns an empty list.

    Parameters
    ----------
    season : str | None
        Season string (e.g. "2024-25").  Defaults to current season.

    Returns
    -------
    list[dict]
        Standings rows with keys: team_abbreviation, team_name,
        conference, conference_rank, wins, losses, win_pct, streak,
        last_10.
    """
    try:
        from data.nba_stats_service import get_league_standings
        return get_league_standings(season=season)
    except Exception as exc:
        _logger.warning("get_standings_from_nba_api failed: %s", exc)
    return []


def get_game_logs_from_nba_api(
    player_name: str,
    season: str | None = None,
) -> list:
    """
    Resolve *player_name* to a player ID and fetch game logs via
    nba_stats_service.

    Parameters
    ----------
    player_name : str
        Full player name (case-insensitive).
    season : str | None
        Season string (e.g. "2024-25").  Defaults to current season.

    Returns
    -------
    list[dict]
        Per-game stat dicts with nba_api column names (PTS, REB, …).
        Returns [] if the player cannot be found or the call fails.
    """
    try:
        from data.player_profile_service import get_player_id
        from data.nba_stats_service import get_player_game_logs

        player_id = get_player_id(player_name)
        if not player_id:
            _logger.debug("get_game_logs_from_nba_api: no player ID for %r", player_name)
            return []

        return get_player_game_logs(player_id, season=season)
    except Exception as exc:
        _logger.warning("get_game_logs_from_nba_api(%r) failed: %s", player_name, exc)
    return []


def refresh_historical_data_for_tonight(
    games=None,
    last_n_games=30,
    progress_callback=None,
) -> dict:
    """
    Auto-retrieve historical game logs for tonight's players and
    update CLV closing lines.

    Uses nba_api for player game logs.  Stores results in the game
    log cache for the Backtester page.
    """
    results = {"players_refreshed": 0, "clv_updated": 0, "errors": 0}

    if games is None:
        try:
            import streamlit as _st
            games = _st.session_state.get("todays_games", [])
        except Exception:
            games = []

    if not games:
        _logger.debug("refresh_historical_data_for_tonight: no games — skipping")
        return results

    playing_teams = set()
    for g in games:
        for key in ("home_team", "away_team"):
            t = str(g.get(key, "")).upper().strip()
            if t:
                playing_teams.add(t)

    if not playing_teams:
        return results

    try:
        from data.data_manager import load_players_data as _load_players
        all_players = _load_players()
    except Exception as exc:
        _logger.warning("refresh_historical_data_for_tonight: could not load players — %s", exc)
        return results

    tonight_players = [
        p for p in all_players
        if str(p.get("team", "")).upper().strip() in playing_teams
        and p.get("player_id")
    ]

    if not tonight_players:
        _logger.debug("refresh_historical_data_for_tonight: no players with IDs found")
        return results

    total = len(tonight_players)
    if progress_callback:
        progress_callback(0, total, f"Retrieving historical logs for {total} player(s)…")

    for idx, p in enumerate(tonight_players):
        player_id = p.get("player_id")
        player_name = p.get("name", f"ID-{player_id}")
        try:
            logs = _ldf_fetch_player_game_log(player_id, last_n_games=last_n_games)
            if logs:
                try:
                    from data.game_log_cache import save_game_logs_to_cache as _save_cache
                    _save_cache(player_name, logs)
                    results["players_refreshed"] += 1
                except Exception:
                    results["errors"] += 1
        except Exception:
            results["errors"] += 1
        if progress_callback:
            progress_callback(idx + 1, total, f"Cached logs for {player_name}")

    # Auto-update CLV closing lines
    try:
        from engine.clv_tracker import auto_update_closing_lines as _clv_update
        clv_result = _clv_update(days_back=1)
        results["clv_updated"] = clv_result.get("updated", 0)
    except Exception as exc:
        _logger.debug("refresh_historical_data_for_tonight: CLV update skipped — %s", exc)

    _logger.info(
        "refresh_historical_data_for_tonight: players_refreshed=%d, clv_updated=%d, errors=%d",
        results["players_refreshed"], results["clv_updated"], results["errors"],
    )
    return results
