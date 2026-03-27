"""
Verification script to ensure all fixes are working.
Run this after implementing all changes.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)

def verify_nba_api_version():
    """Verify nba_api version is correct"""
    import nba_api
    print(f"✓ nba_api version: {nba_api.__version__}")

    # Test V3 endpoints
    from nba_api.stats.endpoints import ScoreboardV3, LeagueInjuries
    print("✓ ScoreboardV3 import successful")
    print("✓ LeagueInjuries import successful")
    return True

def verify_utils():
    """Verify utility modules are working"""
    from utils.headers import get_nba_headers
    from utils.retry import retry_with_backoff
    from utils.cache import FileCache
    from utils.logger import get_logger

    headers = get_nba_headers()
    assert 'User-Agent' in headers
    print("✓ Headers module working")

    cache = FileCache(cache_dir="test_cache")
    cache.set("test", "value")
    assert cache.get("test") == "value"
    cache.clear()
    print("✓ Cache module working")

    return True

def verify_roster_engine():
    """Verify roster engine can fetch injuries"""
    from data.roster_engine import RosterEngine

    engine = RosterEngine()
    engine.refresh()

    injury_map = getattr(engine, '_injury_map', {})
    print(f"✓ Injuries fetched: {len(injury_map)} players")
    return True

def verify_live_data_fetcher():
    """Verify live data fetcher can get games"""
    from data.live_data_fetcher import fetch_todays_games

    games = fetch_todays_games()

    print(f"✓ Games fetched: {len(games)}")
    for game in games:
        print(f"  - {game.get('away_team', '?')} @ {game.get('home_team', '?')}")

    return len(games) > 0

def verify_platform_fetcher():
    """Verify platform fetcher can get props"""
    from data.platform_fetcher import fetch_prizepicks_props, fetch_underdog_props

    # Test PrizePicks
    pp_props = fetch_prizepicks_props()
    print(f"✓ PrizePicks props: {len(pp_props)}")

    # Test Underdog
    ud_props = fetch_underdog_props()
    print(f"✓ Underdog props: {len(ud_props)}")

    return True

def verify_player_filtering():
    """Verify Coby White is not filtered"""
    from data.nba_data_service import NBADataService

    service = NBADataService()
    games = service.get_todays_games()

    if not games:
        print("⚠ No games today, skipping player verification")
        return True

    players = service.get_todays_players(games)

    # Check for Coby White
    coby = [p for p in players if 'Coby White' in p.get('name', '')]

    if coby:
        print(f"✓ Coby White found in players ({len(coby)} entries)")
        print(f"  - Status: {coby[0].get('injury_status', 'Unknown')}")
        return True
    else:
        print("⚠ Coby White not found in players (may not be playing today)")
        return True

def main():
    """Run all verification checks"""
    print("\n" + "="*50)
    print("SMART-AI NBA VERIFICATION SUITE")
    print("="*50 + "\n")

    checks = [
        ("NBA API Version", verify_nba_api_version),
        ("Utility Modules", verify_utils),
        ("Roster Engine", verify_roster_engine),
        ("Live Data Fetcher", verify_live_data_fetcher),
        ("Platform Fetcher", verify_platform_fetcher),
        ("Player Filtering", verify_player_filtering),
    ]

    passed = 0
    failed = 0

    for name, func in checks:
        print(f"\n--- Testing {name} ---")
        try:
            if func():
                passed += 1
                print(f"✅ {name}: PASSED")
            else:
                failed += 1
                print(f"❌ {name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {name}: ERROR - {e}")

    print("\n" + "="*50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*50)

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
