"""
Verification script: NBA Injury Report CDN fetch fix.

Demonstrates that the curl_cffi-based fetch in data/nba_injury_pdf correctly
bypasses Akamai TLS fingerprinting instead of getting HTTP 403.

Usage:
    python scripts/verify_injury_report.py
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_log = logging.getLogger(__name__)


def _check_curl_cffi() -> bool:
    """Return True when curl_cffi is importable."""
    try:
        import curl_cffi  # noqa: F401
        from data.nba_injury_pdf._parser import _CURL_CFFI_AVAILABLE
        if _CURL_CFFI_AVAILABLE:
            print("✓ curl_cffi is installed and active — Akamai bypass enabled")
        else:
            print("⚠ curl_cffi import flag is False despite package being importable")
        return _CURL_CFFI_AVAILABLE
    except ImportError:
        print("⚠ curl_cffi is NOT installed — falling back to plain requests")
        print("  Install with:  pip install 'curl_cffi>=0.7,<0.14'")
        return False


def _check_report_available(ts: datetime.datetime) -> bool:
    """Check if the NBA CDN responds for the given timestamp."""
    from data.nba_injury_pdf import check_report_available
    from data.nba_injury_pdf._url import generate_report_url
    url = generate_report_url(ts)
    print(f"  Checking: {url}")
    available = check_report_available(ts)
    if available:
        print(f"  ✓ Report available (HTTP 200)")
    else:
        print(f"  ✗ Report not available (non-200 or error)")
    return available


def _fetch_report() -> bool:
    """Attempt to fetch the latest NBA injury report and print a sample."""
    from data.nba_injury_pdf import get_report
    print("\nFetching latest injury report (auto-discover)…")
    try:
        df = get_report()
    except Exception as exc:
        print(f"  ✗ Fetch raised an exception: {exc}")
        return False

    if df.empty:
        print("  ✗ Returned empty DataFrame — no report found for today/yesterday")
        return False

    print(f"  ✓ Fetch succeeded — {len(df)} row(s) returned")
    print(f"\n  Sample (first 5 rows):")
    try:
        import pandas as pd
        with pd.option_context("display.max_columns", None, "display.width", 120):
            print(df.head(5).to_string(index=False))
    except Exception:
        for _, row in df.head(5).iterrows():
            print(f"    {dict(row)}")
    return True


def main():
    print("=" * 60)
    print("NBA Injury Report CDN Fix — Verification")
    print("=" * 60)

    curl_ok = _check_curl_cffi()

    # Try a few recent report times to find one that exists on the CDN
    print("\nChecking CDN availability for recent report times…")
    now = datetime.datetime.now()
    # Try today and yesterday at known publication times
    found_available = False
    for delta_days in range(2):
        check_date = (now - datetime.timedelta(days=delta_days)).date()
        for hour, minute in [(17, 0), (13, 30), (11, 30), (9, 30)]:
            ts = datetime.datetime(check_date.year, check_date.month, check_date.day, hour, minute)
            if ts > now:
                continue
            if _check_report_available(ts):
                found_available = True
                break
        if found_available:
            break

    if not found_available:
        print("  (No report was available at checked times — CDN may not have today's report yet)")

    fetch_ok = _fetch_report()

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  curl_cffi active:   {'YES' if curl_ok else 'NO (fallback to requests)'}")
    print(f"  Fetch succeeded:    {'YES' if fetch_ok else 'NO (empty/error)'}")
    print("=" * 60)

    return 0 if fetch_ok else 1


if __name__ == "__main__":
    sys.exit(main())
