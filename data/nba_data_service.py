# ============================================================
# FILE: data/nba_data_service.py
# PURPOSE: Thin delegation layer that routes all NBA data
#          retrieval through the ETL database first, then
#          falls back to data/live_data_fetcher.py (nba_api).
#
#          This module preserves the public API that every page
#          and engine module imports (get_todays_games, etc.)
#          while preferring the local DB for fast startup.
#
# DATA SOURCES (priority order):
#   1. ETL SQLite database (db/smartpicks.db, via etl_data_service.py)
#   2. nba_api / stats.nba.com (via live_data_fetcher.py)
#   3. PrizePicks / Underdog / DraftKings (via platform_fetcher.py)
#      — props only, unchanged
# ============================================================

from pathlib import Path as _Path
import datetime as _datetime
import logging as _logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = _logging.getLogger(__name__)

# Import utility-layer cache helpers for cross-module cache management.
# FileCache provides file-based caching; used by clear_caches() to
# clear downstream caches in live_data_fetcher and roster_engine.
try:
    from utils.cache import FileCache as _FileCache
    _HAS_FILE_CACHE = True
except ImportError:
    _HAS_FILE_CACHE = False

# Import retry helper for the refresh_all_data convenience function.
try:
    from utils.retry import retry_with_backoff as _retry_with_backoff
    _HAS_RETRY = True
except ImportError:
    _HAS_RETRY = False

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
    # Season helper
    _current_season,
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
    refresh_from_etl as _ldf_refresh_from_etl,          # noqa: F401
    full_refresh_from_etl as _ldf_full_refresh_from_etl, # noqa: F401
)


# ============================================================
# ETL Database availability check
# ============================================================

try:
    from data.etl_data_service import is_db_available as _is_db_available
except ImportError:
    def _is_db_available():  # type: ignore[misc]
        return False


# ============================================================
# Format-normalisation helpers  (DB → downstream contract)
# ============================================================

def _normalize_db_games(db_games: list) -> list:
    """Convert etl_data_service game dicts to the format Streamlit pages expect.

    etl_data_service returns::

        {"game_id": "…", "game_date": "…", "matchup": "ATL vs. NYK", …}

    Downstream code expects::

        {"game_id": "…", "home_team": "NYK", "away_team": "ATL",
         "home_team_name": "New York Knicks", …}
    """
    _abbrev_to_name = {v: k for k, v in TEAM_NAME_TO_ABBREVIATION.items()}
    normalised = []
    for g in db_games:
        matchup = str(g.get("matchup", "") or "")
        away_abbr = ""
        home_abbr = ""
        if " vs. " in matchup:
            parts = matchup.split(" vs. ", 1)
            away_abbr = parts[0].strip()
            home_abbr = parts[1].strip()
        elif " @ " in matchup:
            parts = matchup.split(" @ ", 1)
            away_abbr = parts[0].strip()
            home_abbr = parts[1].strip()
        elif " vs " in matchup:
            parts = matchup.split(" vs ", 1)
            away_abbr = parts[0].strip()
            home_abbr = parts[1].strip()

        # If matchup already had home/away keys, prefer them
        home_abbr = g.get("home_team", home_abbr) or home_abbr
        away_abbr = g.get("away_team", away_abbr) or away_abbr

        normalised.append({
            "game_id":        str(g.get("game_id", "")),
            "game_date":      str(g.get("game_date", "")),
            "home_team":      home_abbr,
            "away_team":      away_abbr,
            "home_team_name": _abbrev_to_name.get(home_abbr, home_abbr),
            "away_team_name": _abbrev_to_name.get(away_abbr, away_abbr),
            "vegas_spread":   float(g.get("vegas_spread", 0)),
            "game_total":     float(g.get("game_total", 220)),
            "matchup":        matchup,
        })
    return normalised


def _normalize_db_player(p: dict) -> dict:
    """Convert an etl_data_service player dict to the CSV-format keys
    expected by engine/projections.py, engine/monte_carlo.py, and all
    Streamlit pages.

    The live fetcher (fetch_todays_players_only / fetch_player_stats)
    emits ``offensive_rebounds_avg``, ``defensive_rebounds_avg``,
    ``personal_fouls_avg``, ``usage_rate``, and ``games_played``.
    Engine modules (projections, impact_metrics, joseph_eval,
    advanced_metrics) read those exact keys, so they MUST be present
    here as well.  Short aliases (``oreb_avg``, ``dreb_avg``,
    ``pf_avg``) are kept for data_manager / db_service callers.
    """
    minutes_avg = float(p.get("mpg", 0.0) or 0.0)
    gp = int(p.get("gp", 0) or 0)
    oreb_avg = float(p.get("oreb_avg", 0.0) or 0.0)
    dreb_avg = float(p.get("dreb_avg", 0.0) or 0.0)
    pf_avg = float(p.get("pf_avg", 0.0) or 0.0)
    oreb_std = float(p.get("oreb_std", 0.0) or 0.0)

    return {
        "player_id":       p.get("player_id"),
        "name":            f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
        "team":            p.get("team_abbreviation", ""),
        "position":        p.get("position", ""),
        "gp":              gp,
        "games_played":    str(gp),
        "points_avg":      p.get("ppg", 0.0),
        "rebounds_avg":    p.get("rpg", 0.0),
        "assists_avg":     p.get("apg", 0.0),
        "steals_avg":      p.get("spg", 0.0),
        "blocks_avg":      p.get("bpg", 0.0),
        "turnovers_avg":   p.get("topg", 0.0),
        "minutes_avg":     minutes_avg,
        "threes_avg":      p.get("fg3_avg", 0.0),
        "ftm_avg":         p.get("ftm_avg", 0.0),
        "fta_avg":         p.get("fta_avg", 0.0),
        "ft_pct":          p.get("ft_pct_avg", 0.0),
        "fgm_avg":         p.get("fgm_avg", 0.0),
        "fga_avg":         p.get("fga_avg", 0.0),
        "fg_pct":          p.get("fg_pct_avg", 0.0),
        # Short aliases kept for data_manager / db_service callers
        "oreb_avg":                oreb_avg,
        "dreb_avg":                dreb_avg,
        "pf_avg":                  pf_avg,
        # Full-name aliases required by engine/projections, impact_metrics, etc.
        "offensive_rebounds_avg":  oreb_avg,
        "defensive_rebounds_avg":  dreb_avg,
        "personal_fouls_avg":     pf_avg,
        "plus_minus_avg":         p.get("plus_minus_avg", 0.0),
        # Usage rate estimate (same formula as live_data_fetcher)
        "usage_rate":             round(min(35.0, max(10.0, minutes_avg * 0.8)), 1),
        # Standard deviations
        "points_std":             p.get("points_std", 0.0),
        "rebounds_std":           p.get("rebounds_std", 0.0),
        "assists_std":            p.get("assists_std", 0.0),
        "threes_std":             p.get("threes_std", 0.0),
        "steals_std":             p.get("steals_std", 0.0),
        "blocks_std":             p.get("blocks_std", 0.0),
        "turnovers_std":          p.get("turnovers_std", 0.0),
        "ftm_std":                p.get("ftm_std", 0.0),
        "oreb_std":               oreb_std,
        "plus_minus_std":         p.get("plus_minus_std", 0.0),
        # Extended std fields (match live_data_fetcher output)
        "offensive_rebounds_std": oreb_std,
        "defensive_rebounds_std": 0.0,
        "personal_fouls_std":     0.0,
        "fta_std":                0.0,
        "fga_std":                0.0,
        "fgm_std":                0.0,
    }


# ============================================================
# Public API — DB-first, live-API fallback
# ============================================================

def get_todays_games():
    """Retrieve tonight's NBA games (DB-first, live API fallback)."""
    # 1. Try ETL database first
    if _is_db_available():
        try:
            from data.etl_data_service import get_todays_games as _db_get_games
            db_result = _db_get_games()
            if db_result:
                _logger.info("get_todays_games: loaded %d games from ETL DB", len(db_result))
                return _normalize_db_games(db_result)
        except Exception as exc:
            _logger.debug("get_todays_games: DB read failed (%s), falling back to API", exc)

    # 2. Fall back to live API
    result = _ldf_fetch_todays_games()
    if not result:
        _logger.warning("get_todays_games: all sources returned no games")
    return result


def get_todays_players(todays_games, progress_callback=None,
                       precomputed_injury_map=None):
    """Retrieve players for tonight's games (DB-first, live API fallback)."""
    return _ldf_fetch_todays_players(
        todays_games,
        progress_callback=progress_callback,
        precomputed_injury_map=precomputed_injury_map,
    )


def get_player_recent_form(player_id, last_n_games=10):
    """Get a player's recent-form stats via nba_api."""
    result = _ldf_fetch_player_recent_form(player_id, last_n_games=last_n_games)
    if not result:
        _logger.debug("get_player_recent_form(%s): all sources returned no data", player_id)
    return result


def get_player_stats(progress_callback=None):
    """Retrieve all active player season stats (DB-first, live API fallback)."""
    # 1. Try ETL database first
    if _is_db_available():
        try:
            from data.etl_data_service import get_all_players as _db_get_all_players
            db_players = _db_get_all_players()
            if db_players:
                _logger.info("get_player_stats: loaded %d players from ETL DB", len(db_players))
                return [_normalize_db_player(p) for p in db_players]
        except Exception as exc:
            _logger.debug("get_player_stats: DB read failed (%s), falling back to API", exc)

    # 2. Fall back to live API
    return _ldf_fetch_player_stats(progress_callback=progress_callback)


def get_team_stats(progress_callback=None):
    """Retrieve team-level stats (DB-first, live API fallback)."""
    # 1. Try ETL database first
    if _is_db_available():
        try:
            from data.etl_data_service import get_all_teams as _db_get_all_teams
            db_teams = _db_get_all_teams()
            if db_teams:
                _logger.info("get_team_stats: loaded %d teams from ETL DB", len(db_teams))
                return db_teams
        except Exception as exc:
            _logger.debug("get_team_stats: DB read failed (%s), falling back to API", exc)

    # 2. Fall back to live API
    return _ldf_fetch_team_stats(progress_callback=progress_callback)


def get_defensive_ratings(force=False, progress_callback=None):
    """Retrieve defensive ratings (DB-first, live API fallback)."""
    # 1. Try ETL database first (unless force-refresh requested)
    if not force and _is_db_available():
        try:
            from data.etl_data_service import get_all_defense_vs_position as _db_get_dvp
            db_dvp = _db_get_dvp()
            if db_dvp:
                _logger.info("get_defensive_ratings: loaded %d rows from ETL DB", len(db_dvp))
                return db_dvp
        except Exception as exc:
            _logger.debug("get_defensive_ratings: DB read failed (%s), falling back to API", exc)

    # 2. Fall back to live API
    return _ldf_fetch_defensive_ratings(
        force=force, progress_callback=progress_callback,
    )


def get_player_game_log(player_id, last_n_games=20):
    """Retrieve a player's game log via nba_api."""
    result = _ldf_fetch_player_game_log(player_id, last_n_games=last_n_games)
    if not result:
        _logger.warning("get_player_game_log(%s): all sources returned no game log", player_id)
    return result


def get_all_data(progress_callback=None, targeted=False, todays_games=None):
    """Retrieve all NBA data (games, players, teams) via nba_api."""
    return _ldf_fetch_all_data(
        progress_callback=progress_callback,
        targeted=targeted,
        todays_games=todays_games,
    )


def get_all_todays_data(progress_callback=None):
    """One-click: retrieve games → players → props for tonight (DB-first)."""
    return _ldf_fetch_all_todays_data(progress_callback=progress_callback)


def get_active_rosters(team_abbrevs=None, progress_callback=None):
    """Retrieve active rosters (DB-first, live API fallback)."""
    # 1. Try ETL database first
    if _is_db_available() and team_abbrevs:
        try:
            from data.etl_data_service import get_rosters_for_teams as _db_get_rosters
            db_rosters = _db_get_rosters(list(team_abbrevs))
            if db_rosters:
                _logger.info("get_active_rosters: loaded rosters for %d teams from ETL DB",
                             len(db_rosters))
                return db_rosters
        except Exception as exc:
            _logger.debug("get_active_rosters: DB read failed (%s), falling back to API", exc)

    # 2. Fall back to live API
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
    Retrieve current NBA standings (DB-first, live API fallback).

    Tries the ETL database first.  Falls back to nba_api LeagueStandingsV3.
    Returns an empty list on failure.
    """
    # 1. Try ETL database first
    if _is_db_available():
        try:
            from data.etl_data_service import get_standings as _db_get_standings
            db_standings = _db_get_standings()
            if db_standings:
                _logger.info("get_standings: loaded %d rows from ETL DB", len(db_standings))
                if progress_callback:
                    progress_callback(10, 10, f"Standings loaded ({len(db_standings)} teams) from DB.")
                return db_standings
        except Exception as exc:
            _logger.debug("get_standings: DB read failed (%s), falling back to API", exc)

    if progress_callback:
        progress_callback(0, 10, "Retrieving NBA standings…")

    # ── nba_api ──────────────────────────────────────────────
    try:
        from nba_api.stats.endpoints import leaguestandingsv3
        import time
        time.sleep(API_DELAY_SECONDS)
        raw = leaguestandingsv3.LeagueStandingsV3(season=_current_season())
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


# ============================================================
# nba_live_fetcher.py wrappers — new NBA API Gateway
# These functions delegate to data/nba_live_fetcher.py, which
# wraps the full breadth of stats.nba.com endpoints.
# ============================================================

try:
    from data.nba_live_fetcher import (
        fetch_player_game_logs as _nlf_fetch_player_game_logs,
        fetch_box_score_traditional as _nlf_fetch_box_score_traditional,
        fetch_box_score_advanced as _nlf_fetch_box_score_advanced,
        fetch_box_score_usage as _nlf_fetch_box_score_usage,
        fetch_player_on_off as _nlf_fetch_player_on_off,
        fetch_player_estimated_metrics as _nlf_fetch_player_estimated_metrics,
        fetch_player_fantasy_profile as _nlf_fetch_player_fantasy_profile,
        fetch_rotations as _nlf_fetch_rotations,
        fetch_schedule as _nlf_fetch_schedule,
        fetch_todays_scoreboard as _nlf_fetch_todays_scoreboard,
        fetch_box_score_matchups as _nlf_fetch_box_score_matchups,
        fetch_hustle_box_score as _nlf_fetch_hustle_box_score,
        fetch_defensive_box_score as _nlf_fetch_defensive_box_score,
        fetch_scoring_box_score as _nlf_fetch_scoring_box_score,
        fetch_tracking_box_score as _nlf_fetch_tracking_box_score,
        fetch_four_factors_box_score as _nlf_fetch_four_factors_box_score,
        fetch_player_shooting_splits as _nlf_fetch_player_shooting_splits,
        fetch_shot_chart as _nlf_fetch_shot_chart,
        fetch_player_clutch_stats as _nlf_fetch_player_clutch_stats,
        fetch_team_lineups as _nlf_fetch_team_lineups,
        fetch_team_dashboard as _nlf_fetch_team_dashboard,
        fetch_standings as _nlf_fetch_standings,
        fetch_team_game_logs as _nlf_fetch_team_game_logs,
        fetch_player_year_over_year as _nlf_fetch_player_year_over_year,
        fetch_player_vs_player as _nlf_fetch_player_vs_player,
        fetch_win_probability as _nlf_fetch_win_probability,
        fetch_play_by_play as _nlf_fetch_play_by_play,
        fetch_game_summary as _nlf_fetch_game_summary,
        fetch_league_leaders as _nlf_fetch_league_leaders,
        fetch_team_streak_finder as _nlf_fetch_team_streak_finder,
    )
    _NLF_AVAILABLE = True
except Exception as _nlf_import_err:
    _logger.debug("nba_live_fetcher not available: %s", _nlf_import_err)
    _NLF_AVAILABLE = False


def _nlf_unavailable_list(*_args, **_kwargs):
    return []


def _nlf_unavailable_dict(*_args, **_kwargs):
    return {}


# ── TIER 1: Critical endpoints ───────────────────────────────────────────────

def get_player_game_logs_v2(player_id: int, season: str | None = None, last_n: int = 0) -> list:
    """Return per-game stats from nba_live_fetcher (supports last_n filter)."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_player_game_logs(player_id, season=season, last_n=last_n)


def get_box_score_traditional(game_id: str, period: int = 0) -> dict:
    """Return the traditional box score for a game."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_box_score_traditional(game_id, period=period)


def get_box_score_advanced(game_id: str) -> dict:
    """Return the advanced box score for a game."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_box_score_advanced(game_id)


def get_box_score_usage(game_id: str) -> dict:
    """Return usage statistics box score for a game (USG_PCT, touches, etc.)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_box_score_usage(game_id)


def get_player_on_off(team_id: int, season: str | None = None) -> dict:
    """Return On/Off court differential stats for all players on a team."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_player_on_off(team_id, season=season)


def get_player_estimated_metrics(season: str | None = None) -> list:
    """Return estimated advanced metrics for all players (pace, ortg, drtg, etc.)."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_player_estimated_metrics(season=season)


def get_player_fantasy_profile(player_id: int, season: str | None = None) -> dict:
    """Return fantasy-relevant stat splits for a player (last 5/10/15/20 games)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_player_fantasy_profile(player_id, season=season)


def get_rotations(game_id: str) -> dict:
    """Return in/out rotation data (exact stint times) for a game."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_rotations(game_id)


def get_schedule(game_date: str | None = None) -> list:
    """Return the game schedule for a given date (defaults to today)."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_schedule(game_date=game_date)


def get_todays_scoreboard() -> dict:
    """Return today's full scoreboard (game headers, line scores, standings)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_todays_scoreboard()


# ── TIER 2: High-value endpoints ─────────────────────────────────────────────

def get_box_score_matchups(game_id: str) -> dict:
    """Return defensive matchup data for a game (who guarded whom)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_box_score_matchups(game_id)


def get_hustle_box_score(game_id: str) -> dict:
    """Return hustle stats box score (charges, deflections, loose balls)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_hustle_box_score(game_id)


def get_defensive_box_score(game_id: str) -> dict:
    """Return defensive statistics box score for a game."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_defensive_box_score(game_id)


def get_scoring_box_score(game_id: str) -> dict:
    """Return scoring breakdown box score (FG% by zone, etc.)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_scoring_box_score(game_id)


def get_tracking_box_score(game_id: str) -> dict:
    """Return player-tracking box score (speed, distance, touches)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_tracking_box_score(game_id)


def get_four_factors_box_score(game_id: str) -> dict:
    """Return four-factors box score (eFG%, TO%, ORB%, FT rate)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_four_factors_box_score(game_id)


def get_player_shooting_splits(player_id: int, season: str | None = None) -> dict:
    """Return detailed shooting splits for a player (by zone, distance, etc.)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_player_shooting_splits(player_id, season=season)


def get_shot_chart_v2(player_id: int, season: str | None = None) -> list:
    """Return shot chart data for a player (x/y coords, made/missed, zone)."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_shot_chart(player_id, season=season)


def get_player_clutch_stats(season: str | None = None) -> list:
    """Return clutch-time stats (last 5 min, margin ≤5) for all players."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_player_clutch_stats(season=season)


def get_team_lineups(team_id: int, season: str | None = None) -> list:
    """Return 5-man lineup stats for a specific team."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_team_lineups(team_id, season=season)


def get_team_dashboard(team_id: int, season: str | None = None) -> dict:
    """Return team dashboard stats (home/away splits, days rest, monthly)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_team_dashboard(team_id, season=season)


def get_team_game_logs(team_id: int, season: str | None = None, last_n: int = 0) -> list:
    """Return per-game stats for a team, optionally capped to last_n games."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_team_game_logs(team_id, season=season, last_n=last_n)


def get_player_year_over_year(player_id: int) -> list:
    """Return year-over-year career stats for a player."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_player_year_over_year(player_id)


# ── TIER 3: Reference & context endpoints ────────────────────────────────────

def get_player_vs_player(
    player1_id: int,
    player2_id: int,
    season: str | None = None,
) -> dict:
    """Return head-to-head stats for player1 when matched against player2."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_player_vs_player(player1_id, player2_id, season=season)


def get_win_probability(game_id: str) -> dict:
    """Return real-time win probability at each point in the game."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_win_probability(game_id)


def get_play_by_play_v2(game_id: str) -> list:
    """Return play-by-play events for a game."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_play_by_play(game_id)


def get_game_summary(game_id: str) -> dict:
    """Return high-level game summary (arena, officials, attendance, etc.)."""
    if not _NLF_AVAILABLE:
        return {}
    return _nlf_fetch_game_summary(game_id)


def get_league_leaders(stat_category: str = "PTS", season: str | None = None) -> list:
    """Return top players for a given statistical category via nba_api."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_league_leaders(stat_category=stat_category, season=season)


def get_team_streak_finder(team_id: int, season: str | None = None) -> list:
    """Return full season game log for a team (for streak/form computation)."""
    if not _NLF_AVAILABLE:
        return []
    return _nlf_fetch_team_streak_finder(team_id, season=season)


# ── End nba_live_fetcher.py wrappers ─────────────────────────────────────────


def get_standings_from_nba_api(season: str | None = None) -> list:
    """
    Retrieve NBA standings via nba_stats_service.

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


# ============================================================
# NBADataService — class-based API wrapper
# ============================================================

class NBADataService:
    """
    Class-based service for NBA data operations.

    Wraps the existing module-level functions in an OOP interface,
    providing cache management and bulk-refresh convenience methods.
    All callers can continue using the module-level functions directly;
    this class is offered for callers that prefer dependency injection.
    """

    def __init__(self):
        if _HAS_FILE_CACHE:
            self.cache = _FileCache(cache_dir="cache/service", ttl_hours=1)
        else:
            self.cache = None

        try:
            from data.roster_engine import RosterEngine
            self.roster_engine = RosterEngine()
        except Exception:
            self.roster_engine = None

    # ── Core data methods ─────────────────────────────────────

    def get_todays_games(self):
        """Get today's NBA games."""
        return get_todays_games()

    def get_todays_players(self, games, progress_callback=None,
                           precomputed_injury_map=None):
        """Get players for teams playing today."""
        return get_todays_players(
            games,
            progress_callback=progress_callback,
            precomputed_injury_map=precomputed_injury_map,
        )

    def get_team_stats(self, progress_callback=None):
        """Get team statistics."""
        return get_team_stats(progress_callback=progress_callback)

    def get_injuries(self):
        """Get current injury data via RosterEngine."""
        if self.roster_engine:
            return self.roster_engine.refresh()
        return {}

    # ── Cache & refresh ───────────────────────────────────────

    def clear_caches(self):
        """Clear all caches (delegates to module-level clear_caches)."""
        clear_caches()

    def refresh_all_data(self, progress_callback=None):
        """Refresh all data (delegates to module-level refresh_all_data)."""
        return refresh_all_data(progress_callback=progress_callback)


# ============================================================
# Utility-layer integration — cache management & bulk refresh
# ============================================================

def clear_caches() -> None:
    """
    Clear file-based and in-memory caches across the data layer.

    Clears caches in live_data_fetcher, roster_engine, and the
    in-memory tiered cache used by utils.cache.  Safe to call even
    if some modules are unavailable (graceful no-ops).
    """
    cleared = []

    # 1. In-memory tiered cache (utils.cache.cache_clear)
    try:
        from utils.cache import cache_clear
        cache_clear()
        cleared.append("in-memory")
    except Exception:
        pass

    # 2. File-based cache directories
    if _HAS_FILE_CACHE:
        for cache_dir in ("cache/service", "cache/props", "cache/rosters"):
            try:
                fc = _FileCache(cache_dir=cache_dir, ttl_hours=0)
                fc.clear()
                cleared.append(cache_dir)
            except Exception:
                pass

    _logger.info("clear_caches: cleared %s", ", ".join(cleared) if cleared else "(none)")


def refresh_all_data(progress_callback=None) -> dict:
    """
    Refresh all core data sources with per-source error isolation.

    Fetches games, players, team stats, and injury data.  Each source
    is wrapped in its own try/except so a single failure does not
    block the others.

    Parameters
    ----------
    progress_callback : callable or None
        Called as ``progress_callback(current, total, message)`` to
        report incremental progress (e.g. to a Streamlit progress bar).

    Returns
    -------
    dict
        Keys: ``games``, ``players``, ``team_stats``, ``injuries``,
        ``errors`` (list of error strings for any source that failed).
    """
    result = {
        "games": [],
        "players": [],
        "team_stats": None,
        "injuries": None,
        "errors": [],
    }
    total_steps = 4
    step = 0

    # ── Games ──────────────────────────────────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching today's games…")
    try:
        result["games"] = get_todays_games()
    except Exception as exc:
        _logger.error("refresh_all_data — games failed: %s", exc)
        result["errors"].append(f"Games: {exc}")

    # ── Players (only if games available) ──────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching players…")
    if result["games"]:
        try:
            result["players"] = get_todays_players(result["games"])
        except Exception as exc:
            _logger.error("refresh_all_data — players failed: %s", exc)
            result["errors"].append(f"Players: {exc}")

    # ── Team stats ─────────────────────────────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching team stats…")
    try:
        result["team_stats"] = get_team_stats()
    except Exception as exc:
        _logger.error("refresh_all_data — team stats failed: %s", exc)
        result["errors"].append(f"Team stats: {exc}")

    # ── Injuries ───────────────────────────────────────────────
    step += 1
    if progress_callback:
        progress_callback(step, total_steps, "Fetching injury data…")
    try:
        from data.roster_engine import RosterEngine as _RE
        _re = _RE()
        result["injuries"] = _re.refresh()
    except Exception as exc:
        _logger.error("refresh_all_data — injuries failed: %s", exc)
        result["errors"].append(f"Injuries: {exc}")

    _logger.info(
        "refresh_all_data: games=%d, players=%d, errors=%d",
        len(result["games"]),
        len(result["players"]),
        len(result["errors"]),
    )
    return result


# ============================================================
# ETL refresh helpers — thin wrappers around live_data_fetcher
# ============================================================

def refresh_from_etl(progress_callback=None) -> dict:
    """
    Incremental ETL update — fetch only new game logs since the last
    stored date in db/smartpicks.db.

    Args:
        progress_callback (callable | None): (current, total, message).

    Returns:
        dict: {new_games, new_logs, new_players, error (optional)}
    """
    return _ldf_refresh_from_etl(progress_callback=progress_callback)


def full_refresh_from_etl(season: str | None = None, progress_callback=None) -> dict:
    """
    Full ETL pull — re-fetches the entire season from nba_api and
    repopulates db/smartpicks.db.

    Args:
        season (str | None): Season string, e.g. '2025-26'.
        progress_callback (callable | None): (current, total, message).

    Returns:
        dict: {players_inserted, games_inserted, logs_inserted, error (optional)}
    """
    return _ldf_full_refresh_from_etl(season=season, progress_callback=progress_callback)
