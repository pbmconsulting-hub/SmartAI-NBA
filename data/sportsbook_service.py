# ============================================================
# FILE: data/sportsbook_service.py
# PURPOSE: Thin delegation layer that routes all sportsbook /
#          player-prop retrieval through data/platform_fetcher.py.
#
#          platform_fetcher.py fetches live prop lines directly
#          from PrizePicks, Underdog Fantasy, and DraftKings
#          Pick6 (via The Odds API).
#
# PLATFORMS:
#   - PrizePicks  : public JSON API, no key required
#   - Underdog    : public JSON API, no key required
#   - DraftKings  : via The Odds API (free key, 500 req/month)
#
# USAGE:
#   from data.sportsbook_service import get_all_sportsbook_props
#   props = get_all_sportsbook_props()
# ============================================================

import logging as _logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = _logging.getLogger(__name__)

# ── Re-export every public symbol from platform_fetcher ──────
from data.platform_fetcher import (            # noqa: F401 – re-exports
    build_cross_platform_comparison,
    recommend_best_platform,
    match_platform_player_to_csv,
    enrich_props_with_csv_names,
    find_new_players_from_props,
    extract_active_players_from_props,
    cross_reference_with_player_data,
    get_platform_confirmed_injuries,
    summarize_props_by_platform,
    quarantine_props,
    smart_filter_props,
    parse_alt_lines_from_platform_props,
    # Async infrastructure
    AIOHTTP_AVAILABLE,
    _ASYNC_SEMAPHORE_LIMIT,
    fetch_all_platforms_async as get_all_sportsbooks_async,
    # Quarantine constants
    QUARANTINE_ODDS_FLOOR,
    QUARANTINE_ODDS_CEILING,
    _EQUILIBRIUM_ODDS,
)

# Import platform_fetcher functions under private names for
# get_* wrapper compatibility.
from data.platform_fetcher import (
    fetch_prizepicks_props as _pf_prizepicks,
    fetch_underdog_props as _pf_underdog,
    fetch_draftkings_props as _pf_draftkings,
    fetch_all_platform_props as _pf_all,
)


# ============================================================
# Public API — name-compatible wrappers
# ============================================================

def get_prizepicks_props(league="NBA"):
    """Fetch live PrizePicks NBA prop lines."""
    return _pf_prizepicks(league=league)


def get_underdog_props(league="NBA"):
    """Fetch live Underdog Fantasy NBA prop lines."""
    return _pf_underdog(league=league)


def get_draftkings_props(api_key=None):
    """Fetch DraftKings Pick6 NBA prop lines via The Odds API."""
    return _pf_draftkings(api_key=api_key)


def get_all_sportsbook_props(
    include_prizepicks=True,
    include_underdog=True,
    include_draftkings=True,
    odds_api_key=None,
    progress_callback=None,
):
    """
    Fetch live prop lines from PrizePicks, Underdog Fantasy, and
    DraftKings Pick6 (via The Odds API).

    Args:
        include_prizepicks: Include PrizePicks props.
        include_underdog:   Include Underdog Fantasy props.
        include_draftkings: Include DraftKings Pick6 props.
        odds_api_key:       Odds API key for DraftKings.
        progress_callback:  Optional callable(current, total, message).

    Returns:
        list[dict]: Merged prop line dicts from all platforms.
    """
    return _pf_all(
        include_prizepicks=include_prizepicks,
        include_underdog=include_underdog,
        include_draftkings=include_draftkings,
        odds_api_key=odds_api_key,
        progress_callback=progress_callback,
    )


# ============================================================
# Auto-refresh: keep session props fresh without manual clicks
# ============================================================

import os as _os
import datetime as _dt

# Configurable staleness thresholds (minutes)
_STALE_GAME_WINDOW_MIN = int(_os.environ.get("PROP_STALE_GAME_MIN", "10"))
_STALE_OFF_WINDOW_MIN = int(_os.environ.get("PROP_STALE_OFF_MIN", "30"))


def _props_age_minutes(props_list: list) -> float | None:
    """Return how many minutes ago the newest prop was fetched, or None."""
    if not props_list:
        return None
    newest = None
    for p in props_list:
        ts = p.get("fetched_at") or p.get("retrieved_at") or ""
        if not ts:
            continue
        try:
            dt = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if newest is None or dt > newest:
                newest = dt
        except (ValueError, TypeError):
            continue
    if newest is None:
        return None
    now = _dt.datetime.now(_dt.timezone.utc)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=_dt.timezone.utc)
    return (now - newest).total_seconds() / 60.0


def _is_game_window() -> bool:
    """Return True if current ET hour is inside the NBA game window (6 PM–2 AM)."""
    try:
        from zoneinfo import ZoneInfo
        _eastern = ZoneInfo("America/New_York")
    except ImportError:
        _eastern = _dt.timezone(_dt.timedelta(hours=-5))
    et_hour = _dt.datetime.now(_eastern).hour
    return et_hour >= 18 or et_hour < 2


def refresh_props_if_stale(session_state) -> list:
    """Check session-cached props and auto-refresh if stale.

    * During game window (6 PM–2 AM ET): stale after 10 min
    * Outside game window: stale after 30 min
    * Only fetches PrizePicks + Underdog (free, unlimited).
      DraftKings is never auto-refreshed — uses 500 req/month Odds API.
    * Falls back to ``data/live_props.csv`` (written by the background
      scheduler) if the live fetch fails.

    Args:
        session_state: ``st.session_state`` object.

    Returns:
        list[dict]: The current (possibly refreshed) props.
    """
    from data.data_manager import (
        load_platform_props_from_session,
        save_platform_props_to_session,
        save_platform_props_to_csv,
        load_platform_props_from_csv,
    )

    existing = load_platform_props_from_session(session_state)
    age = _props_age_minutes(existing)
    threshold = _STALE_GAME_WINDOW_MIN if _is_game_window() else _STALE_OFF_WINDOW_MIN

    if age is not None and age < threshold:
        return existing  # Still fresh

    # ── Try live fetch (PP + UD only — free platforms) ────────────
    try:
        fresh = _pf_all(
            include_prizepicks=True,
            include_underdog=True,
            include_draftkings=False,
        )
        if fresh:
            save_platform_props_to_session(fresh, session_state)
            save_platform_props_to_csv(fresh)
            _logger.info(
                "[AutoRefresh] %d fresh props loaded (age was %s min, threshold %d min)",
                len(fresh),
                f"{age:.0f}" if age is not None else "N/A",
                threshold,
            )
            return fresh
    except Exception as exc:
        _logger.warning("[AutoRefresh] live fetch failed: %s — trying CSV fallback", exc)

    # ── Fallback: load from disk (background scheduler may have fresh data) ──
    csv_props = load_platform_props_from_csv()
    if csv_props:
        csv_age = _props_age_minutes(csv_props)
        if csv_age is not None and (age is None or csv_age < age):
            save_platform_props_to_session(csv_props, session_state)
            _logger.info("[AutoRefresh] loaded %d props from CSV (age %.0f min)", len(csv_props), csv_age)
            return csv_props

    return existing  # Return whatever we have
