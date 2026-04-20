"""
etl/scheduler.py
----------------
Lightweight in-process scheduler that keeps the ETL database fresh while
the Streamlit app is running.

**How it works**

* A single daemon thread sleeps in a loop and calls
  ``etl.data_updater.run_update()`` at configurable intervals.
* During the NBA window (roughly 6 PM → 2 AM ET, when games are live)
  the refresh runs every **30 minutes** so bet resolution and live pages
  see recent box scores.
* Outside that window (daytime / early morning) it runs every **4 hours**
  — just enough to catch overnight finalizations and injury updates.
* ``start()`` is safe to call multiple times; only one background thread
  is ever created per process.

**Environment knobs** (all optional)

``ETL_FAST_INTERVAL_MIN``  — minutes between refreshes during game window  (default 30)
``ETL_SLOW_INTERVAL_MIN``  — minutes between refreshes outside game window (default 240)
``ETL_GAME_WINDOW_START``  — ET hour when fast cadence begins               (default 18)
``ETL_GAME_WINDOW_END``    — ET hour when fast cadence ends                 (default 2)
``ETL_SCHEDULER_DISABLED`` — set to ``1`` to completely disable             (default off)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Configuration (env-overridable) ───────────────────────────────────────

_FAST_INTERVAL = int(os.environ.get("ETL_FAST_INTERVAL_MIN", "30")) * 60   # seconds
_SLOW_INTERVAL = int(os.environ.get("ETL_SLOW_INTERVAL_MIN", "240")) * 60  # seconds
_GAME_WINDOW_START = int(os.environ.get("ETL_GAME_WINDOW_START", "18"))     # ET hour
_GAME_WINDOW_END = int(os.environ.get("ETL_GAME_WINDOW_END", "2"))         # ET hour
_DISABLED = os.environ.get("ETL_SCHEDULER_DISABLED", "").strip() in ("1", "true", "yes")

# US-Eastern offset (ET).  During DST this is UTC-4; standard is UTC-5.
# We approximate with UTC-5 (close enough for a 6 PM–2 AM window).
_ET = timezone(timedelta(hours=-5))

# ── Singleton guard ───────────────────────────────────────────────────────

_started = False
_lock = threading.Lock()


def _in_game_window() -> bool:
    """Return True if the current ET hour falls inside the NBA game window."""
    et_hour = datetime.now(_ET).hour
    if _GAME_WINDOW_START < _GAME_WINDOW_END:
        # e.g. 10 AM → 6 PM (unlikely but handled)
        return _GAME_WINDOW_START <= et_hour < _GAME_WINDOW_END
    else:
        # Wraps midnight: e.g. 6 PM → 2 AM  ⇒  hour >= 18 OR hour < 2
        return et_hour >= _GAME_WINDOW_START or et_hour < _GAME_WINDOW_END


_PROP_FAST_INTERVAL = int(os.environ.get("PROP_FAST_INTERVAL_MIN", "15")) * 60   # seconds
_PROP_SLOW_INTERVAL = int(os.environ.get("PROP_SLOW_INTERVAL_MIN", "60")) * 60  # seconds


def _refresh_props() -> int:
    """Fetch fresh props from FREE platforms (PrizePicks + Underdog) and
    write to ``data/live_props.csv``.  DraftKings is skipped because The
    Odds API has a 500 req/month cap — DK is refreshed only on user demand.

    Returns the number of props written, or 0 on failure.
    """
    try:
        from data.platform_fetcher import fetch_all_platform_props
        from data.data_manager import save_platform_props_to_csv

        props = fetch_all_platform_props(
            include_prizepicks=True,
            include_underdog=True,
            include_draftkings=False,   # Preserve DK API budget
        )
        if props:
            save_platform_props_to_csv(props)
            return len(props)
        return 0
    except Exception:
        _logger.exception("[ETL Scheduler] prop refresh failed")
        return 0


def _loop() -> None:
    """Infinite loop: sleep → refresh → repeat.  Runs on a daemon thread."""
    # Initial delay — let the app finish booting before the first refresh.
    time.sleep(60)

    _last_prop_refresh = 0.0  # monotonic timestamp of last prop refresh

    while True:
        game_window = _in_game_window()
        interval = _FAST_INTERVAL if game_window else _SLOW_INTERVAL

        # ── ETL database refresh (game logs, standings, injuries) ──
        try:
            from etl.data_updater import run_update
            t0 = time.monotonic()
            new_rows = run_update()
            elapsed = round(time.monotonic() - t0, 1)
            _logger.info(
                "[ETL Scheduler] refresh done — %d new rows in %.1f s "
                "(next in %d min, game_window=%s)",
                new_rows, elapsed, interval // 60, game_window,
            )
        except Exception:
            _logger.exception("[ETL Scheduler] refresh failed — will retry next cycle")

        # ── Live props refresh (PrizePicks + Underdog only) ────────
        prop_interval = _PROP_FAST_INTERVAL if game_window else _PROP_SLOW_INTERVAL
        since_last_prop = time.monotonic() - _last_prop_refresh
        if since_last_prop >= prop_interval:
            t0 = time.monotonic()
            count = _refresh_props()
            elapsed = round(time.monotonic() - t0, 1)
            _last_prop_refresh = time.monotonic()
            _logger.info(
                "[ETL Scheduler] prop refresh — %d props written in %.1f s "
                "(next prop refresh in %d min)",
                count, elapsed, prop_interval // 60,
            )

        time.sleep(interval)


def start() -> bool:
    """Start the background ETL scheduler (idempotent).

    Returns ``True`` if the thread was started for the first time,
    ``False`` if it was already running or is disabled.
    """
    global _started

    if _DISABLED:
        _logger.info("[ETL Scheduler] disabled via ETL_SCHEDULER_DISABLED env var.")
        return False

    with _lock:
        if _started:
            return False
        _started = True

    t = threading.Thread(target=_loop, name="etl-scheduler", daemon=True)
    t.start()
    _logger.info(
        "[ETL Scheduler] started — fast=%d min (game window %d:00–%d:00 ET), "
        "slow=%d min (outside window)",
        _FAST_INTERVAL // 60, _GAME_WINDOW_START, _GAME_WINDOW_END,
        _SLOW_INTERVAL // 60,
    )
    return True
