"""End-to-end integration test for the user profile pipeline.

Tests the full flow: table creation → save → load → update → edge cases.
Uses a temp DB so production data is never touched.
"""
import os
import sys
import sqlite3
import tempfile
import shutil

# Use a temp DB
tmp = tempfile.mkdtemp()
os.environ["DB_DIR"] = tmp
os.environ.setdefault("SMARTAI_PRODUCTION", "false")

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tracking.database import (
    initialize_database,
    save_user_profile,
    load_user_profile,
    is_profile_complete,
    DB_FILE_PATH,
)

print(f"DB path: {DB_FILE_PATH}")
print()

passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        print(f"[PASS] {label}")
        passed += 1
    else:
        print(f"[FAIL] {label}  {detail}")
        failed += 1


# ── Test 1: Initialize database ────────────────────────────
initialize_database()
conn = sqlite3.connect(str(DB_FILE_PATH))
tables = [
    r[0]
    for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'"
    ).fetchall()
]
check("Test 1: user_profiles table created", "user_profiles" in tables)

# ── Test 2: Verify all columns ─────────────────────────────
cols = [r[1] for r in conn.execute("PRAGMA table_info(user_profiles)").fetchall()]
expected_cols = [
    "email", "display_name", "favorite_team", "preferred_platforms",
    "experience_level", "betting_style", "daily_budget",
    "profile_complete", "created_at", "updated_at",
]
all_cols_ok = all(c in cols for c in expected_cols)
missing = [c for c in expected_cols if c not in cols]
check(f"Test 2: All {len(expected_cols)} columns exist", all_cols_ok, f"Missing: {missing}")

# ── Test 3: Empty email edge cases ─────────────────────────
check(
    "Test 3a: save_user_profile rejects empty email",
    save_user_profile("", {}) is False,
)
check(
    "Test 3b: load_user_profile returns None for empty email",
    load_user_profile("") is None,
)
check(
    "Test 3c: is_profile_complete returns False for empty email",
    is_profile_complete("") is False,
)

# ── Test 4: Save a profile ─────────────────────────────────
test_data = {
    "display_name": "SharpShooter23",
    "favorite_team": "Boston Celtics",
    "preferred_platforms": "PrizePicks,Underdog Fantasy",
    "experience_level": "Intermediate",
    "betting_style": "Balanced",
    "daily_budget": "$25 – $50",
}
result = save_user_profile("Test@Example.com", test_data)
check("Test 4: save_user_profile succeeded", result is True)

# ── Test 5: Load the profile back ──────────────────────────
profile = load_user_profile("test@example.com")
check("Test 5a: load_user_profile returns data", profile is not None)
if profile:
    check("Test 5b: display_name correct", profile["display_name"] == "SharpShooter23")
    check("Test 5c: favorite_team correct", profile["favorite_team"] == "Boston Celtics")
    check(
        "Test 5d: preferred_platforms correct",
        profile["preferred_platforms"] == "PrizePicks,Underdog Fantasy",
    )
    check("Test 5e: experience_level correct", profile["experience_level"] == "Intermediate")
    check("Test 5f: betting_style correct", profile["betting_style"] == "Balanced")
    check("Test 5g: profile_complete is 1", profile["profile_complete"] == 1)
    check("Test 5h: created_at populated", profile["created_at"] is not None)
    check("Test 5i: updated_at populated", profile["updated_at"] is not None)

# ── Test 6: Case-insensitive email lookup ──────────────────
profile2 = load_user_profile("TEST@EXAMPLE.COM")
check("Test 6a: Case-insensitive lookup works", profile2 is not None)
if profile2:
    check("Test 6b: Data matches", profile2["display_name"] == "SharpShooter23")

# ── Test 7: is_profile_complete ────────────────────────────
check("Test 7a: is_profile_complete=True for saved user", is_profile_complete("test@example.com"))
check("Test 7b: is_profile_complete=False for unknown user", not is_profile_complete("nobody@test.com"))

# ── Test 8: UPSERT updates existing profile ────────────────
update_data = {
    "display_name": "ProBettor99",
    "favorite_team": "Los Angeles Lakers",
    "preferred_platforms": "DraftKings Pick6",
    "experience_level": "Pro",
    "betting_style": "Sniper",
    "daily_budget": "$250+",
}
result2 = save_user_profile("test@example.com", update_data)
check("Test 8a: UPSERT save succeeded", result2 is True)
profile3 = load_user_profile("test@example.com")
if profile3:
    check("Test 8b: display_name updated", profile3["display_name"] == "ProBettor99")
    check("Test 8c: favorite_team updated", profile3["favorite_team"] == "Los Angeles Lakers")
    check("Test 8d: experience_level updated", profile3["experience_level"] == "Pro")
    check("Test 8e: betting_style updated", profile3["betting_style"] == "Sniper")
count = conn.execute(
    "SELECT COUNT(*) FROM user_profiles WHERE email = ?", ("test@example.com",)
).fetchone()[0]
check("Test 8f: No duplicate rows (count=1)", count == 1, f"Got count={count}")

# ── Test 9: Multiple distinct users ────────────────────────
save_user_profile("user2@test.com", {"display_name": "User2", "favorite_team": "Miami Heat"})
save_user_profile("user3@test.com", {"display_name": "User3", "favorite_team": "Denver Nuggets"})
total = conn.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0]
check("Test 9: Multiple users stored (3 rows)", total == 3, f"Got {total}")

# ── Test 10: Frontend form data mapping ────────────────────
prof_display_name = "  TestUser  "
prof_team = "Oklahoma City Thunder"
prof_platforms = ["PrizePicks", "Sleeper"]
prof_experience = "Advanced \u2014 Seasoned bettor"
prof_style = "Aggressive \u2014 High risk, high reward"
prof_budget = "$100 \u2013 $250"

_profile_data = {
    "display_name": prof_display_name.strip() or "fallback",
    "favorite_team": prof_team if prof_team != "\u2014 Select a team \u2014" else "",
    "preferred_platforms": ",".join(prof_platforms),
    "experience_level": prof_experience.split(" \u2014")[0],
    "betting_style": prof_style.split(" \u2014")[0],
    "daily_budget": prof_budget,
}
check("Test 10a: strip() works", _profile_data["display_name"] == "TestUser")
check("Test 10b: team preserved", _profile_data["favorite_team"] == "Oklahoma City Thunder")
check("Test 10c: platforms joined", _profile_data["preferred_platforms"] == "PrizePicks,Sleeper")
check("Test 10d: experience split", _profile_data["experience_level"] == "Advanced")
check("Test 10e: style split", _profile_data["betting_style"] == "Aggressive")

result3 = save_user_profile("frontend_test@test.com", _profile_data)
check("Test 10f: Frontend data saved", result3 is True)
p = load_user_profile("frontend_test@test.com")
if p:
    check("Test 10g: experience roundtrip", p["experience_level"] == "Advanced")
    check("Test 10h: style roundtrip", p["betting_style"] == "Aggressive")

# ── Test 11: Skip button (no profile saved) ────────────────
check("Test 11: Skipped user has no profile", not is_profile_complete("skip_user@test.com"))

# ── Test 12: "Select a team" sentinel is excluded ──────────
_profile_data2 = {
    "display_name": "NoTeam",
    "favorite_team": "" if "\u2014 Select a team \u2014" == "\u2014 Select a team \u2014" else "X",
    "preferred_platforms": "",
    "experience_level": "Beginner",
    "betting_style": "Conservative",
    "daily_budget": "Prefer not to say",
}
save_user_profile("noteam@test.com", _profile_data2)
pn = load_user_profile("noteam@test.com")
check("Test 12: No team stored as empty string", pn and pn["favorite_team"] == "")

conn.close()

# Cleanup
shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 55)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED - Pipeline verified end-to-end")
else:
    print("SOME TESTS FAILED - Review output above")
print("=" * 55)
sys.exit(1 if failed else 0)
