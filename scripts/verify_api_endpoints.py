#!/usr/bin/env python3
"""
scripts/verify_api_endpoints.py
-------------------------------
Production-ready API endpoint verification script.

Tests all API-Basketball v1 and The Odds API v4 endpoints using real API keys.
Intended to be run manually to confirm the app can pull data before deployment.

Usage:
    # Using environment variables:
    API_NBA_KEY="your_key" ODDS_API_KEY="your_key" python scripts/verify_api_endpoints.py

    # Or set keys in .streamlit/secrets.toml and run:
    python scripts/verify_api_endpoints.py

    # Or pass keys as arguments:
    python scripts/verify_api_endpoints.py --api-nba-key YOUR_KEY --odds-api-key YOUR_KEY

Requires: requests  (pip install requests)
"""

import argparse
import json
import os
import sys
import time

# Add repo root to path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

API_SPORTS_BASE = "https://v1.basketball.api-sports.io"
ODDS_API_BASE   = "https://api.the-odds-api.com/v4"
SPORT_KEY       = "basketball_nba"

# ── Helpers ───────────────────────────────────────────────────────────────────

_PASS = 0
_FAIL = 0
_RESULTS: list[dict] = []


def _record(name: str, ok: bool, detail: str = ""):
    global _PASS, _FAIL
    if ok:
        _PASS += 1
    else:
        _FAIL += 1
    _RESULTS.append({"name": name, "ok": ok, "detail": detail})


def _test_api_sports(endpoint: str, headers: dict, params: dict | None = None,
                     label: str = "") -> dict | None:
    """Call an API-Sports endpoint and return the parsed response."""
    url = f"{API_SPORTS_BASE}{endpoint}"
    label = label or f"API-Sports {endpoint}"
    print(f"\n  Testing: {label}")
    print(f"    URL: {url}")
    if params:
        print(f"    Params: {params}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
    except Exception as exc:
        print(f"    ❌ Network error: {exc}")
        _record(label, False, f"Network error: {exc}")
        return None

    if resp.status_code != 200:
        print(f"    ❌ HTTP {resp.status_code}: {resp.text[:200]}")
        _record(label, False, f"HTTP {resp.status_code}")
        return None

    data = resp.json()
    errors = data.get("errors", [])
    if errors and errors != [] and errors != {}:
        print(f"    ❌ API errors: {errors}")
        _record(label, False, f"API errors: {errors}")
        return None

    results_count = data.get("results", "?")
    response = data.get("response")

    if isinstance(response, list):
        print(f"    ✅ {results_count} result(s)")
        _record(label, True, f"{results_count} results")
    elif isinstance(response, dict):
        print(f"    ✅ Dict response with keys: {list(response.keys())[:5]}")
        _record(label, True, f"Dict: {list(response.keys())[:5]}")
    else:
        print(f"    ⚠️  Unexpected response type: {type(response)}")
        _record(label, False, f"Unexpected type: {type(response)}")

    return data


def _test_odds_api(endpoint: str, api_key: str, params: dict | None = None,
                   label: str = "") -> list | dict | None:
    """Call an Odds API endpoint and return the parsed response."""
    url = f"{ODDS_API_BASE}{endpoint}"
    label = label or f"Odds API {endpoint}"
    all_params = {"apiKey": api_key}
    if params:
        all_params.update(params)
    print(f"\n  Testing: {label}")
    print(f"    URL: {url}")

    try:
        resp = requests.get(url, params=all_params, timeout=15)
    except Exception as exc:
        print(f"    ❌ Network error: {exc}")
        _record(label, False, f"Network error: {exc}")
        return None

    if resp.status_code == 401:
        print(f"    ❌ Invalid API key (401 Unauthorized)")
        _record(label, False, "Invalid API key (401)")
        return None
    if resp.status_code == 422:
        print(f"    ⚠️  422 — sport may not be in season")
        _record(label, True, "422 — out of season (expected)")
        return None
    if resp.status_code != 200:
        print(f"    ❌ HTTP {resp.status_code}: {resp.text[:200]}")
        _record(label, False, f"HTTP {resp.status_code}")
        return None

    # Show remaining quota from headers
    remaining = resp.headers.get("x-requests-remaining")
    used = resp.headers.get("x-requests-used")
    if remaining:
        print(f"    📊 Quota: {used} used, {remaining} remaining")

    data = resp.json()
    if isinstance(data, list):
        print(f"    ✅ {len(data)} item(s)")
        _record(label, True, f"{len(data)} items")
    elif isinstance(data, dict):
        print(f"    ✅ Dict with keys: {list(data.keys())[:5]}")
        _record(label, True, f"Dict: {list(data.keys())[:5]}")
    else:
        print(f"    ⚠️  Unexpected response type: {type(data)}")
        _record(label, True, "Unexpected type (OK)")

    return data


# ── Main test functions ───────────────────────────────────────────────────────

def test_api_sports(api_key: str):
    """Test all API-Basketball v1 endpoints."""
    print("\n" + "=" * 70)
    print("  API-BASKETBALL v1 ENDPOINT VERIFICATION")
    print("=" * 70)

    headers = {"x-apisports-key": api_key}

    # 1. /status — Free, verifies key
    data = _test_api_sports("/status", headers, label="[1/13] /status (key check)")
    if data:
        resp = data.get("response") or data
        reqs = (resp if isinstance(resp, dict) else {}).get("requests", {})
        print(f"    🔑 Requests today: {reqs.get('current', '?')}/{reqs.get('limit_day', '?')}")
    time.sleep(0.3)

    # 2. /teams
    _test_api_sports("/teams", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[2/13] /teams?league=12&season=2025-2026")
    time.sleep(0.3)

    # 3. /games (with season)
    _test_api_sports("/games", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[3/13] /games?league=12&season=2025-2026")
    time.sleep(0.3)

    # 4. /games (today)
    from datetime import date
    today = date.today().isoformat()
    _test_api_sports("/games", headers,
                     params={"league": "12", "season": "2025-2026", "date": today},
                     label=f"[4/13] /games?league=12&date={today}")
    time.sleep(0.3)

    # 5. /players (with team filter)
    _test_api_sports("/players", headers,
                     params={"league": "12", "season": "2025-2026", "team": "1"},
                     label="[5/13] /players?league=12&season=2025-2026&team=1")
    time.sleep(0.3)

    # 6. /standings
    _test_api_sports("/standings", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[6/13] /standings?league=12&season=2025-2026")
    time.sleep(0.3)

    # 7. /injuries
    _test_api_sports("/injuries", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[7/13] /injuries?league=12&season=2025-2026")
    time.sleep(0.3)

    # 8. /players/statistics (need season + league + player)
    _test_api_sports("/players/statistics", headers,
                     params={"league": "12", "season": "2025-2026", "player": "236"},
                     label="[8/13] /players/statistics?league=12&season=2025-2026&player=236")
    time.sleep(0.3)

    # 9. /games/statistics/teams
    _test_api_sports("/games/statistics/teams", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[9/13] /games/statistics/teams?league=12&season=2025-2026")
    time.sleep(0.3)

    # 10. /games/statistics/players
    _test_api_sports("/games/statistics/players", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[10/13] /games/statistics/players?league=12&season=2025-2026")
    time.sleep(0.3)

    # 11. /odds
    _test_api_sports("/odds", headers,
                     params={"league": "12", "season": "2025-2026"},
                     label="[11/13] /odds?league=12&season=2025-2026")
    time.sleep(0.3)

    # 12. /news
    _test_api_sports("/news", headers,
                     params={"league": "12"},
                     label="[12/13] /news?league=12")
    time.sleep(0.3)

    # 13. /predictions (requires a game_id for full results)
    _test_api_sports("/predictions", headers, label="[13/13] /predictions")


def test_odds_api(api_key: str):
    """Test all The Odds API v4 endpoints."""
    print("\n" + "=" * 70)
    print("  THE ODDS API v4 ENDPOINT VERIFICATION")
    print("=" * 70)

    # 1. /sports — Free endpoint
    data = _test_odds_api("/sports", api_key, label="[1/5] /sports (free, key check)")
    nba_active = False
    if isinstance(data, list):
        nba = [s for s in data if s.get("key") == SPORT_KEY]
        if nba:
            nba_active = nba[0].get("active", False)
            print(f"    🏀 basketball_nba active: {nba_active}")
        else:
            print("    ⚠️  basketball_nba NOT in sports list (NBA off-season)")
    time.sleep(0.3)

    # 2. /events
    data = _test_odds_api(f"/sports/{SPORT_KEY}/events", api_key,
                          params={"dateFormat": "iso"},
                          label="[2/5] /events (upcoming NBA games)")
    event_id = None
    if isinstance(data, list) and data:
        event_id = data[0].get("id")
        home = data[0].get("home_team", "?")
        away = data[0].get("away_team", "?")
        print(f"    🎯 Next game: {away} @ {home}")
    time.sleep(0.3)

    # 3. /odds (featured markets)
    _test_odds_api(f"/sports/{SPORT_KEY}/odds", api_key,
                   params={"regions": "us", "markets": "h2h,spreads,totals",
                           "dateFormat": "iso", "oddsFormat": "american"},
                   label="[3/5] /odds (h2h+spreads+totals)")
    time.sleep(0.3)

    # 4. /events/{id}/odds (per-event, if we have one)
    if event_id:
        _test_odds_api(f"/sports/{SPORT_KEY}/events/{event_id}/odds", api_key,
                       params={"regions": "us", "markets": "h2h",
                               "dateFormat": "iso", "oddsFormat": "american"},
                       label=f"[4/5] /events/{{id}}/odds (event={event_id[:12]}..)")
    else:
        print("\n  ⏭️  Skipping [4/5] event odds (no upcoming events)")
        _record("[4/5] /events/{id}/odds", True, "Skipped — no events")
    time.sleep(0.3)

    # 5. /scores
    _test_odds_api(f"/sports/{SPORT_KEY}/scores", api_key,
                   params={"daysFrom": "1", "dateFormat": "iso"},
                   label="[5/5] /scores (recent results)")


def _test_free_endpoint(url: str, headers: dict | None = None,
                        params: dict | None = None,
                        label: str = "") -> bool:
    """Test a free (no-API-key) HTTP endpoint and return True on success."""
    label = label or f"Free endpoint {url}"
    print(f"\n  Testing: {label}")
    print(f"    URL: {url}")

    try:
        resp = requests.get(url, headers=headers or {}, params=params, timeout=30)
    except Exception as exc:
        print(f"    ❌ Network error: {exc}")
        _record(label, False, f"Network error: {exc}")
        return False

    if resp.status_code == 403:
        print(f"    ⚠️  HTTP 403 (access denied — may need updated headers)")
        _record(label, False, f"HTTP 403")
        return False
    if resp.status_code != 200:
        print(f"    ❌ HTTP {resp.status_code}")
        _record(label, False, f"HTTP {resp.status_code}")
        return False

    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("resultSets"):
            rows = data["resultSets"][0].get("rowSet", [])
            print(f"    ✅ {len(rows)} row(s) returned")
            _record(label, True, f"{len(rows)} rows")
        elif isinstance(data, dict):
            print(f"    ✅ JSON dict with keys: {list(data.keys())[:5]}")
            _record(label, True, f"Dict: {list(data.keys())[:5]}")
        elif isinstance(data, list):
            print(f"    ✅ {len(data)} item(s)")
            _record(label, True, f"{len(data)} items")
        else:
            print(f"    ✅ Response OK (type: {type(data).__name__})")
            _record(label, True, "OK")
    except Exception:
        # Non-JSON response — still OK if status was 200
        print(f"    ✅ HTTP 200 (non-JSON response, {len(resp.content)} bytes)")
        _record(label, True, "HTTP 200 non-JSON")

    return True


def test_nba_stats_fallback():
    """Test the free stats.nba.com fallback endpoints (no API key needed)."""
    print("\n" + "=" * 70)
    print("  NBA.COM STATS FALLBACK ENDPOINT VERIFICATION")
    print("=" * 70)

    nba_stats_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.nba.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate, br",
        "Host": "stats.nba.com",
    }

    # Determine current season
    import datetime as _dt
    now = _dt.date.today()
    year = now.year if now.month >= 10 else now.year - 1
    season = f"{year}-{str(year + 1)[-2:]}"

    # 1. leaguedashteamstats (Base)
    _test_free_endpoint(
        "https://stats.nba.com/stats/leaguedashteamstats",
        headers=nba_stats_headers,
        params={
            "Season": season, "SeasonType": "Regular Season",
            "MeasureType": "Base", "PerMode": "PerGame", "LeagueID": "00",
        },
        label=f"[1/4] stats.nba.com leaguedashteamstats (Base, {season})",
    )
    time.sleep(1.0)

    # 2. leaguedashteamstats (Advanced)
    _test_free_endpoint(
        "https://stats.nba.com/stats/leaguedashteamstats",
        headers=nba_stats_headers,
        params={
            "Season": season, "SeasonType": "Regular Season",
            "MeasureType": "Advanced", "PerMode": "PerGame", "LeagueID": "00",
        },
        label=f"[2/4] stats.nba.com leaguedashteamstats (Advanced, {season})",
    )
    time.sleep(1.0)

    # 3. leaguedashplayerstats
    _test_free_endpoint(
        "https://stats.nba.com/stats/leaguedashplayerstats",
        headers=nba_stats_headers,
        params={
            "Season": season, "SeasonType": "Regular Season",
            "MeasureType": "Base", "PerMode": "PerGame", "LeagueID": "00",
        },
        label=f"[3/4] stats.nba.com leaguedashplayerstats ({season})",
    )
    time.sleep(1.0)

    # 4. commonallplayers
    _test_free_endpoint(
        "https://stats.nba.com/stats/commonallplayers",
        headers=nba_stats_headers,
        params={
            "Season": season, "LeagueID": "00", "IsOnlyCurrentSeason": "1",
        },
        label=f"[4/4] stats.nba.com commonallplayers ({season})",
    )


def test_nba_cdn_injuries():
    """Test the NBA CDN injury data endpoints (no API key needed)."""
    print("\n" + "=" * 70)
    print("  NBA CDN INJURY ENDPOINT VERIFICATION")
    print("=" * 70)

    cdn_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate, br",
    }

    # 1. Primary CDN injury JSON
    _test_free_endpoint(
        "https://cdn.nba.com/static/json/staticData/injuries.json",
        headers=cdn_headers,
        label="[1/2] cdn.nba.com injuries.json",
    )
    time.sleep(0.5)

    # 2. Headline injuries JSON
    _test_free_endpoint(
        "https://cdn.nba.com/static/json/staticData/headlineinjuries.json",
        headers=cdn_headers,
        label="[2/2] cdn.nba.com headlineinjuries.json",
    )


def print_summary():
    """Print the final summary."""
    print("\n" + "=" * 70)
    print("  VERIFICATION SUMMARY")
    print("=" * 70)

    for r in _RESULTS:
        icon = "✅" if r["ok"] else "❌"
        detail = f"  ({r['detail']})" if r["detail"] else ""
        print(f"  {icon} {r['name']}{detail}")

    print(f"\n  Total: {_PASS} passed, {_FAIL} failed, {_PASS + _FAIL} total")

    if _FAIL == 0:
        print("\n  🎉 All endpoints verified successfully!")
        print("  Your app is ready to pull live data.\n")
    else:
        print(f"\n  ⚠️  {_FAIL} endpoint(s) had issues.")
        print("  Check the details above for troubleshooting.\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Verify all API endpoints for SmartAI-NBA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/verify_api_endpoints.py --api-nba-key YOUR_KEY --odds-api-key YOUR_KEY
  API_NBA_KEY=abc ODDS_API_KEY=xyz python scripts/verify_api_endpoints.py
        """,
    )
    parser.add_argument("--api-nba-key", default=None,
                        help="API-Sports NBA key (or set API_NBA_KEY env var)")
    parser.add_argument("--odds-api-key", default=None,
                        help="The Odds API key (or set ODDS_API_KEY env var)")
    args = parser.parse_args()

    api_nba_key = args.api_nba_key or os.environ.get("API_NBA_KEY", "")
    odds_api_key = args.odds_api_key or os.environ.get("ODDS_API_KEY", "")

    # Try secrets.toml if env vars are empty
    if not api_nba_key or not odds_api_key:
        secrets_path = os.path.join(_REPO_ROOT, ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("API_NBA_KEY") and not api_nba_key:
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and "your_" not in val:
                                api_nba_key = val
                        elif line.startswith("ODDS_API_KEY") and not odds_api_key:
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and "your_" not in val:
                                odds_api_key = val
            except Exception:
                pass

    if not api_nba_key:
        print("ERROR: No API-Sports NBA key found.")
        print("  Set API_NBA_KEY env var, pass --api-nba-key, or add to .streamlit/secrets.toml")
        sys.exit(1)
    if not odds_api_key:
        print("ERROR: No Odds API key found.")
        print("  Set ODDS_API_KEY env var, pass --odds-api-key, or add to .streamlit/secrets.toml")
        sys.exit(1)

    print(f"  API-Sports key: {api_nba_key[:8]}...{api_nba_key[-4:]}")
    print(f"  Odds API key:   {odds_api_key[:8]}...{odds_api_key[-4:]}")

    test_api_sports(api_nba_key)
    test_odds_api(odds_api_key)
    test_nba_stats_fallback()
    test_nba_cdn_injuries()
    print_summary()

    sys.exit(1 if _FAIL > 0 else 0)


if __name__ == "__main__":
    main()
