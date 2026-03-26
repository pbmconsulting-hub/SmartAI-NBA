# ============================================================
# FILE: utils/time_helpers.py
# PURPOSE: Shared timezone-aware date helpers for NBA game-date
#          anchoring.  NBA defines game dates in US/Eastern time,
#          so all modules that resolve "today's games" must agree
#          on the same Eastern-time boundary.
#
# Previously duplicated in:
#   - tracking/bet_tracker.py  (_get_eastern_tz, _nba_today_et)
#   - data/live_data_fetcher.py (_nba_today_et)
# ============================================================

import datetime


def get_eastern_tz():
    """Return a US/Eastern timezone object for NBA game-date anchoring.

    NBA defines game dates in Eastern Time. This function prefers
    ``zoneinfo.ZoneInfo`` (DST-aware) and falls back to a fixed UTC-5
    offset when zoneinfo is unavailable.

    NOTE: The fixed UTC-5 fallback does NOT account for daylight saving
    time (EDT = UTC-4, roughly March–November). During EDT, dates
    derived from this fallback may be one hour off near the midnight
    boundary. If your server runs in UTC and processes games near
    midnight ET, install ``tzdata`` (``pip install tzdata``) to ensure
    ``zoneinfo`` is available.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")
    except ImportError:
        return datetime.timezone(datetime.timedelta(hours=-5))


def nba_today_et() -> datetime.date:
    """Return today's date anchored to US/Eastern time."""
    return datetime.datetime.now(get_eastern_tz()).date()
