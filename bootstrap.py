#!/usr/bin/env python3
"""bootstrap.py – one-command setup for Smart Pick Pro.

Run this script once to pull all NBA historical data and prepare the
database for the application:

    python bootstrap.py

After the bootstrap is complete, start the Streamlit UI:

    streamlit run Smart_Picks_Pro_Home.py

The script performs the following steps in order:

1. **ETL Schema**  – creates the SQLite database and all tables.
2. **Initial Pull** – fetches the full 2025-26 season from the NBA API
   (player game logs, team stats, rosters, advanced analytics).
3. **Daily Update** – runs an incremental update to backfill anything
   that the initial pull may have missed.
4. **Pipeline**     – runs the 6-phase prediction pipeline
   (ingest → clean → features → predict → evaluate → export).

Each phase logs progress and timing.  If a phase fails, the error is
logged but subsequent phases still run so you get as much data as
possible on the first attempt.
"""

import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
_logger = logging.getLogger("bootstrap")


def _run_phase(label: str, func, *args, **kwargs):
    """Run *func* inside a labelled timing block, returning its result."""
    _logger.info("▶ Phase: %s", label)
    t0 = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        _logger.info("  ✓ %s completed in %.1fs", label, elapsed)
        return result
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        _logger.error("  ✗ %s failed after %.1fs: %s", label, elapsed, exc)
        return None


def main():
    """Execute the full Smart Pick Pro bootstrap sequence."""
    _logger.info("=" * 60)
    _logger.info("  Smart Pick Pro Bootstrap")
    _logger.info("=" * 60)
    total_start = time.perf_counter()

    # ── Phase 1: ETL Initial Pull ────────────────────────────────
    # Creates the DB schema and seeds all historical data.
    from etl.initial_pull import run_initial_pull

    _run_phase("ETL Initial Pull (NBA API → SQLite)", run_initial_pull)

    # ── Phase 2: Daily Update ────────────────────────────────────
    # Picks up any games/stats added since the initial pull snapshot.
    try:
        from etl.data_updater import run_daily_update

        _run_phase("Daily Incremental Update", run_daily_update)
    except ImportError:
        _logger.info("  ⏭ Daily updater not available — skipping.")

    # ── Phase 3: Prediction Pipeline ─────────────────────────────
    # Runs the 6-step ML/simulation pipeline on today's slate.
    from engine.pipeline.run_pipeline import run_full_pipeline

    ctx = _run_phase("Prediction Pipeline (6 phases)", run_full_pipeline)
    if ctx and ctx.get("errors"):
        _logger.warning(
            "  Pipeline finished with %d error(s).", len(ctx["errors"])
        )

    # ── Done ─────────────────────────────────────────────────────
    total = time.perf_counter() - total_start
    _logger.info("=" * 60)
    _logger.info("  Bootstrap complete in %.1fs", total)
    _logger.info("  Launch the app:  streamlit run Smart_Picks_Pro_Home.py")
    _logger.info("=" * 60)


if __name__ == "__main__":
    sys.exit(main() or 0)
