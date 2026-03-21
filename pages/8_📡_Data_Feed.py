# ============================================================
# FILE: pages/8_🔄_Update_Data.py
# PURPOSE: Streamlit page that lets the user fetch live NBA data
#          from the nba_api library. Updates player stats, team stats,
#          and today's games with real, current data.
# CONNECTS TO: data/live_data_fetcher.py, data/data_manager.py
# CONCEPTS COVERED: Progress bars, API calls, session state, error handling
#
# BEGINNER NOTE: This page is your "data refresh" control panel.
# Click a button to pull live stats from the NBA's official website.
# After updating, all the other pages in the app will use the fresh data!
# ============================================================

# Import streamlit — our UI framework
import streamlit as st

# Standard library imports
import datetime  # For formatting timestamps
import json      # For reading the last_updated.json file

# Import our data loading function (to preview data after fetching)
from data.data_manager import (
    load_players_data,     # Load player stats from CSV
    load_teams_data,       # Load team stats from CSV
)

# Import our live data fetcher functions
# BEGINNER NOTE: We import these here, but the actual nba_api calls
# happen inside these functions. If nba_api is not installed, the
# functions will show a friendly error message instead of crashing.
from data.live_data_fetcher import (
    fetch_todays_games,          # Fetch tonight's NBA games
    fetch_player_stats,          # Fetch all player season averages
    fetch_team_stats,            # Fetch all team stats + defensive ratings
    fetch_all_data,              # Fetch everything at once
    fetch_todays_players_only,   # Targeted: only today's team rosters
    fetch_all_todays_data,       # One-click: games + players + teams
    load_last_updated,           # Load timestamps from last_updated.json
)

# RosterEngine is the single source for injury data (replaces web_scraper/web_scrapers).
# It is available whenever nba_api is installed — set after the nba_api availability check below.

# ============================================================
# SECTION: Page Setup
# ============================================================

# Configure the page (MUST be the first streamlit call)
st.set_page_config(
    page_title="Data Feed — SmartBetPro NBA",
    page_icon="📡",
    layout="wide",  # Use full-width layout
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

try:
    from utils.components import inject_joseph_floating
    inject_joseph_floating()
except Exception:
    pass  # Non-critical — never block page load


# Page title and description
st.title("📡 Data Feed")
st.markdown(
    "Pull real, up-to-date NBA stats from the **nba_api** library "
    "(free, no API key required). Update before each betting session "
    "for the most accurate predictions!"
)
st.divider()

st.markdown(get_education_box_html(
    "📖 How Data Updates Work",
    """
    <strong>Smart Update (Recommended)</strong>: Only fetches players on tonight's teams. 
    10x faster than Full Update — use this before each session.<br><br>
    <strong>Full Update</strong>: Fetches all 450+ NBA players. Takes 5-10 minutes. 
    Use once a week to keep historical averages current.<br><br>
    <strong>Live data</strong>: Real current season stats from NBA.com, saved to players.csv and teams.csv. 
    Fetch live data before each session for accurate predictions.<br><br>
    <strong>Rate limiting</strong>: We wait 1.5 seconds between API calls to respect NBA.com's limits.
    """
), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup
# ============================================================


# ============================================================
# SECTION: Check if nba_api is Installed
# If it's not installed, show installation instructions and stop.
# ============================================================

# Try to import nba_api to see if it's available
try:
    import nba_api  # This will succeed if nba_api is installed
    NBA_API_AVAILABLE = True  # Flag: API is available
except ImportError:
    NBA_API_AVAILABLE = False  # Flag: API is NOT available

# If nba_api is not installed, show a clear error and stop
if not NBA_API_AVAILABLE:
    # Show a big red error message
    st.error("⚠️ **nba_api is not installed!**")

    # Explain what to do
    st.markdown("""
    ### How to Install nba_api

    The `nba_api` library is not installed yet. Run this command in your terminal:

    ```bash
    pip install nba_api
    ```

    Or:
    ```bash
    python -m pip install nba_api
    ```

    After installing, **refresh this page** (press F5 or click the browser reload button).

    ---

    **What is nba_api?**
    It's a free Python library that pulls real-time stats from the NBA's official website.
    No API key or account needed — it's completely free!
    """)

    # BEGINNER NOTE: st.stop() stops the page from rendering anything else
    # This prevents errors from the code below that requires nba_api
    st.stop()

# ============================================================
# END SECTION: Check if nba_api is Installed
# ============================================================

# RosterEngine is available when nba_api is installed (guaranteed at this point).
_roster_engine_available = True


# ============================================================
# SECTION: Data Status Display
# Show when each data type was last updated (so user knows
# if data is fresh or stale).
# ============================================================

st.subheader("📅 Data Status")

# Load the timestamps from the JSON file
timestamps = load_last_updated()

# ── Staleness helpers ──────────────────────────────────────────
def _staleness_badge(timestamp_str: str | None, warn_hours: float = 4.0, error_hours: float = 24.0):
    """Return (badge_html, age_hours) for a data timestamp."""
    if not timestamp_str:
        return '<span style="background:#553c9a;color:#e9d8fd;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;">NEVER</span>', None
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str)
        age_h = (datetime.datetime.now() - dt).total_seconds() / 3600
        if age_h < warn_hours:
            color, label = "#276749", f"FRESH ({age_h:.0f}h ago)"
            text_color = "#9ae6b4"
        elif age_h < error_hours:
            color, label = "#744210", f"AGING ({age_h:.0f}h ago)"
            text_color = "#fbd38d"
        else:
            color, label = "#742a2a", f"STALE ({age_h:.1f}h ago)"
            text_color = "#feb2b2"
        badge = f'<span style="background:{color};color:{text_color};padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;">{label}</span>'
        return badge, age_h
    except Exception:
        return '<span style="background:#553c9a;color:#e9d8fd;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;">UNKNOWN</span>', None


def _health_bar(age_h: float | None, max_age: float = 24.0) -> str:
    """Return a colored health bar HTML string."""
    if age_h is None:
        pct, color = 0, "#742a2a"
    else:
        freshness = max(0.0, 1.0 - age_h / max_age)
        pct = round(freshness * 100)
        color = "#00ff9d" if pct > 70 else ("#ffcc00" if pct > 30 else "#ff4444")
    return (
        f'<div style="height:6px;background:#1a2035;border-radius:3px;margin:6px 0;">'
        f'<div style="height:6px;width:{pct}%;background:{color};border-radius:3px;'
        f'transition:width 0.4s ease;"></div>'
        f'</div>'
        f'<div style="font-size:0.72rem;color:#b0bec5;">Health: {pct}%</div>'
    )

# ── Data health cards ──────────────────────────────────────────
todays_games = st.session_state.get("todays_games", [])

_data_sources = [
    ("👤 Players",       timestamps.get("players"),  6.0,  "player stats / game logs"),
    ("🏟️ Teams",        timestamps.get("teams"),     12.0, "team stats / defensive ratings"),
    ("🏀 Tonight's Games", None if not todays_games else datetime.datetime.now().isoformat(), 4.0, f"{len(todays_games)} game(s) in session"),
    ("🏥 Injuries",      timestamps.get("injuries"),  4.0,  "injury report / roster status"),
]

_health_cols = st.columns(4)
for _ci, (_label, _ts, _warn_h, _desc) in enumerate(_data_sources):
    with _health_cols[_ci]:
        badge_html, age_h = _staleness_badge(_ts, warn_hours=_warn_h)
        health_html = _health_bar(age_h, max_age=24.0)
        st.markdown(
            f'<div style="background:#14192b;border-radius:8px;padding:14px 16px;'
            f'border:1px solid rgba(0,240,255,0.15);">'
            f'<div style="font-size:0.95rem;font-weight:700;color:#c0d0e8;margin-bottom:6px;">{_label}</div>'
            f'{badge_html}'
            f'{health_html}'
            f'<div style="color:#8b949e;font-size:0.75rem;margin-top:4px;">{_desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ============================================================
# END SECTION: Data Status Display
# ============================================================


# ============================================================
# SECTION: Update Action Buttons
# Four buttons: players, teams, games, or everything at once.
# ============================================================

st.subheader("🔧 Update Data")

# ─── One-Click Full Setup (recommended) ─────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#0f3460,#533483); border:2px solid #e94560; border-radius:10px; padding:16px 20px; margin-bottom:16px;">
  <div style="font-size:1.1rem; font-weight:700; color:#ffffff;">🏀 One-Click Full Setup (Best Choice)</div>
  <div style="color:rgba(255,255,255,0.8); font-size:0.9rem; margin-top:4px;">
    Fetches tonight's games → current rosters for those teams → player stats → team stats.
    <strong>Everything in one click.</strong> Same as clicking Auto-Load on the Today's Games page.
  </div>
</div>
""", unsafe_allow_html=True)

one_click_col1, one_click_col2 = st.columns([1, 3])
with one_click_col1:
    if st.button(
        "🏀 One-Click Full Setup",
        width="stretch",
        type="primary",
        help="Games + rosters + player stats + team stats — all in one click",
    ):
        st.session_state["update_action"] = "one_click"

with one_click_col2:
    st.caption(
        "Best for first-time setup each day. "
        "Fetches games first, then only the players on tonight's teams (~1-3 min total)."
    )

st.markdown("---")

# ─── Smart Update (recommended) ─────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#1a1a2e,#16213e); border:1px solid #0f3460; border-radius:10px; padding:16px 20px; margin-bottom:16px;">
  <div style="font-size:1.05rem; font-weight:700; color:#e2e8f0;">⚡ Smart Update — Today's Teams Only</div>
  <div style="color:#a0aec0; font-size:0.9rem; margin-top:4px;">
    Fetches team rosters using <code>CommonTeamRoster</code> (current, post-trade) 
    then game logs for only those players. Requires games to already be loaded.
    Takes <strong>1–2 minutes</strong> instead of 10–15.
  </div>
</div>
""", unsafe_allow_html=True)

smart_col1, smart_col2 = st.columns([1, 3])
with smart_col1:
    if st.button(
        "⚡ Smart Update (Today's Teams Only)",
        width="stretch",
        help="Fastest: fetches only players on teams playing tonight using current rosters",
    ):
        st.session_state["update_action"] = "smart"

with smart_col2:
    todays_games_for_hint = st.session_state.get("todays_games", [])
    if todays_games_for_hint:
        teams_playing = set()
        for g in todays_games_for_hint:
            teams_playing.add(g.get("home_team", ""))
            teams_playing.add(g.get("away_team", ""))
        teams_playing.discard("")
        st.caption(f"Tonight's teams: {', '.join(sorted(teams_playing))}")
    else:
        st.caption("⚠️ Load tonight's games first (🏀 Today's Games page) for Smart Update to work.")

st.markdown("---")
st.markdown("**Full Updates (all 30 teams, takes 10–15 minutes):**")

btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

if "update_action" not in st.session_state:
    st.session_state["update_action"] = None

with btn_col1:
    if st.button(
        "🏟️ Fetch Tonight's Games",
        width="stretch",
        help="Pull tonight's real NBA matchups automatically",
    ):
        st.session_state["update_action"] = "games"

with btn_col2:
    if st.button(
        "👤 Update Player Stats (All — Slow)",
        width="stretch",
        help="Pull current season averages for ALL NBA players (~500, 5-15 min)",
    ):
        st.session_state["update_action"] = "players"

with btn_col3:
    if st.button(
        "🏆 Update Team Stats",
        width="stretch",
        help="Pull team pace, offensive rating, and defensive rating",
    ):
        st.session_state["update_action"] = "teams"

with btn_col4:
    if st.button(
        "🔄 Update Everything (Full)",
        width="stretch",
        help="Update all data: games, all players, and teams (slow)",
    ):
        st.session_state["update_action"] = "all"

st.markdown("---")

# ─── Injury Report Section ──────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#1a0a2e,#0f1a2e); border:1px solid #c800ff; border-radius:10px; padding:16px 20px; margin-bottom:16px;">
  <div style="font-size:1.05rem; font-weight:700; color:#e2e8f0;">🏥 Real-Time Injury Report</div>
  <div style="color:#a0aec0; font-size:0.9rem; margin-top:4px;">
    Fetches live injury designations from the <strong>official NBA API</strong> —
    real-time GTD/Out/Doubtful status, specific injury details, and expected return dates.
  </div>
</div>
""", unsafe_allow_html=True)

injury_btn_col1, injury_btn_col2 = st.columns([1, 3])
with injury_btn_col1:
    _injury_btn_disabled = not _roster_engine_available
    if st.button(
        "🔄 Refresh Injury Report",
        width="stretch",
        help="Fetch live GTD/Out/injury data from the official NBA API (requires nba_api)",
        disabled=_injury_btn_disabled,
    ):
        st.session_state["update_action"] = "injury_report"

with injury_btn_col2:
    if _roster_engine_available:
        # Show last-fetched timestamp if available
        _last_scraped = st.session_state.get("injury_report_last_scraped")
        if _last_scraped:
            st.caption(f"Last fetched: {_last_scraped}")
        else:
            st.caption("Click to pull real-time injury designations from the NBA API.")
    else:
        st.caption(
            "⚠️ `nba_api` is required. "
            "Run `pip install nba_api` to enable this feature."
        )

# ============================================================
# END SECTION: Update Action Buttons
# ============================================================


# ============================================================
# SECTION: Execute the Selected Action
# Based on which button was clicked, run the appropriate fetcher.
# ============================================================

# Get the current action (set by button clicks above)
current_action = st.session_state.get("update_action")

# Only run if an action was selected
if current_action:
    st.divider()

    # --------------------------------------------------------
    # Action: One-Click Full Setup
    # --------------------------------------------------------
    if current_action == "one_click":
        st.subheader("🏀 One-Click Full Setup")

        progress_bar = st.progress(0, text="Starting one-click setup...")
        status_text = st.empty()

        def one_click_progress(current, total, message):
            frac = current / max(total, 1)
            progress_bar.progress(frac, text=message)
            status_text.caption(message)

        with st.spinner("🏀 Fetching games + rosters + player stats + team stats..."):
            result = fetch_all_todays_data(progress_callback=one_click_progress)

        st.session_state["update_action"] = None
        progress_bar.empty()
        status_text.empty()

        games = result.get("games", [])
        players_ok = result.get("players_updated", False)
        teams_ok = result.get("teams_updated", False)

        if games:
            st.session_state["todays_games"] = games
            from data.data_manager import load_players_data
            updated_players = load_players_data()
            st.success(
                f"✅ One-Click Setup complete! "
                f"**{len(games)} game(s)** loaded | "
                f"**{len(updated_players)} players** fetched | "
                f"Teams: {'✅' if teams_ok else '⚠️ failed'}"
            )
        else:
            st.warning(
                "⚠️ Could not fetch tonight's games (no games tonight, or API error). "
                "Try again or load games manually on the 🏀 Today's Games page."
            )

    # --------------------------------------------------------
    # Action: Smart Update (today's teams only)
    # --------------------------------------------------------
    elif current_action == "smart":
        st.subheader("⚡ Smart Update — Today's Teams Only")

        todays_games_for_smart = st.session_state.get("todays_games", [])

        if not todays_games_for_smart:
            st.warning(
                "⚠️ No games loaded yet. Please go to 🏀 **Today's Games** first and "
                "click 'Auto-Load Tonight's Games', then come back here."
            )
            st.session_state["update_action"] = None
        else:
            # Show which teams we'll fetch
            teams_set = set()
            for g in todays_games_for_smart:
                teams_set.add(g.get("home_team", ""))
                teams_set.add(g.get("away_team", ""))
            teams_set.discard("")
            st.info(f"Fetching current rosters for: **{', '.join(sorted(teams_set))}**")

            progress_bar = st.progress(0, text="Starting smart update...")
            status_text = st.empty()

            def smart_progress(current, total, message):
                frac = current / max(total, 1)
                progress_bar.progress(frac, text=message)
                status_text.caption(message)

            with st.spinner("Fetching today's team rosters and player stats..."):
                success = fetch_todays_players_only(
                    todays_games_for_smart,
                    progress_callback=smart_progress
                )

            st.session_state["update_action"] = None
            progress_bar.empty()
            status_text.empty()

            if success:
                from data.data_manager import load_players_data
                updated_players = load_players_data()
                st.success(
                    f"✅ Smart Update complete! Loaded **{len(updated_players)} players** "
                    f"from today's {len(todays_games_for_smart)} game(s). "
                    f"Only current roster players — no traded players!"
                )
                st.caption(f"Teams fetched: {', '.join(sorted(teams_set))}")
            else:
                st.error(
                    "❌ Smart Update failed. Check your internet connection or try again.\n"
                    "You can still use the full 'Update Player Stats' button as a fallback."
                )

    # --------------------------------------------------------
    # Action: Fetch Tonight's Games
    # --------------------------------------------------------
    elif current_action == "games":
        st.subheader("🏟️ Fetching Tonight's Games...")

        # Show a spinner while we fetch
        # BEGINNER NOTE: st.spinner() shows a loading animation
        # while the code inside the "with" block runs
        with st.spinner("Connecting to NBA API..."):
            # Call the fetcher function
            todays_games = fetch_todays_games()

        # Check if we got any games
        if todays_games:
            # Save the games to session state so other pages can use them
            st.session_state["todays_games"] = todays_games
            st.session_state["update_action"] = None  # Clear the action

            # Show success message
            st.success(f"✅ Found **{len(todays_games)} game(s)** for tonight!")
            st.info(
                "💡 Vegas lines (spread and total) were set to defaults. "
                "Edit them on the **🏀 Today's Games** page."
            )

            # Show the games in a table
            st.markdown("**Tonight's Matchups:**")

            # Build display data for the table
            games_display = []
            for game in todays_games:
                games_display.append({
                    "Away Team": game.get("away_team", ""),
                    "Home Team": game.get("home_team", ""),
                    "Game Date": game.get("game_date", ""),
                })

            # Display as a clean table
            # BEGINNER NOTE: st.dataframe() creates a scrollable, sortable table
            st.dataframe(games_display, width="stretch", hide_index=True)

        else:
            # No games found or API error
            st.session_state["update_action"] = None  # Clear the action

            st.warning(
                "⚠️ No games found for tonight, or there was an API error. "
                "\n\nPossible reasons:\n"
                "- No NBA games are scheduled today\n"
                "- The NBA API is temporarily unavailable\n"
                "- Check your internet connection\n\n"
                "You can still enter games manually on the **🏀 Today's Games** page."
            )

    # --------------------------------------------------------
    # Action: Update Player Stats
    # --------------------------------------------------------
    elif current_action == "players":
        st.subheader("👤 Updating Player Stats...")

        st.info(
            "⏳ **This takes a few minutes.** We fetch stats for every player "
            "and then download game logs to calculate standard deviations. "
            "Please be patient!"
        )

        # Create a progress bar
        # BEGINNER NOTE: st.progress() shows a loading bar (0.0 to 1.0)
        # We update it as the fetch progresses
        progress_bar = st.progress(0)     # Start at 0%
        status_text = st.empty()           # Placeholder for status messages

        # Create a callback function to update the progress bar
        # BEGINNER NOTE: A callback is a function you pass to another function
        # so it can "call back" to update the UI
        def update_player_progress(current, total, message):
            """Update the progress bar and status text."""
            # Calculate fraction (0.0 to 1.0)
            fraction = min(current / max(total, 1), 1.0)  # Clamp to [0, 1]
            progress_bar.progress(fraction)     # Update the bar
            status_text.text(f"⏳ {message}")   # Update the text

        # Run the player stats fetcher with our progress callback
        success = fetch_player_stats(progress_callback=update_player_progress)

        # Clear the action flag
        st.session_state["update_action"] = None

        if success:
            # Update complete!
            progress_bar.progress(1.0)  # Fill the bar to 100%
            status_text.text("✅ Done!")

            st.success("✅ **Player stats updated successfully!**")

            # Show the updated data
            st.markdown("**Updated Player Data (first 20 rows):**")
            updated_players = load_players_data()  # Reload from the new CSV

            if updated_players:
                # Convert to display format (only show key columns)
                players_display = []
                for player in updated_players[:20]:  # Show first 20
                    players_display.append({
                        "Name": player.get("name", ""),
                        "Team": player.get("team", ""),
                        "Pos": player.get("position", ""),
                        "MIN": player.get("minutes_avg", ""),
                        "PTS": player.get("points_avg", ""),
                        "REB": player.get("rebounds_avg", ""),
                        "AST": player.get("assists_avg", ""),
                        "3PM": player.get("threes_avg", ""),
                    })

                st.dataframe(players_display, width="stretch", hide_index=True)
                st.caption(f"Showing 20 of {len(updated_players)} players. Full data saved to players.csv")
        else:
            # Fetch failed
            st.error(
                "❌ **Failed to update player stats.**\n\n"
                "Possible reasons:\n"
                "- No internet connection\n"
                "- The NBA API is temporarily down\n"
                "- Try again in a few minutes\n\n"
                "The app will continue to use the existing data until a successful update."
            )

    # --------------------------------------------------------
    # Action: Update Team Stats
    # --------------------------------------------------------
    elif current_action == "teams":
        st.subheader("🏆 Updating Team Stats...")

        # Create a progress bar for team stats
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Progress callback for teams
        def update_team_progress(current, total, message):
            """Update the progress bar for team stats."""
            fraction = min(current / max(total, 1), 1.0)
            progress_bar.progress(fraction)
            status_text.text(f"⏳ {message}")

        # Run the team stats fetcher
        with st.spinner("Fetching team data..."):
            success = fetch_team_stats(progress_callback=update_team_progress)

        # Clear the action flag
        st.session_state["update_action"] = None

        if success:
            progress_bar.progress(1.0)
            status_text.text("✅ Done!")

            st.success("✅ **Team stats updated successfully!**")

            # Show the updated team data
            st.markdown("**Updated Team Data:**")
            updated_teams = load_teams_data()  # Reload from the new CSV

            if updated_teams:
                # Build display format
                teams_display = []
                for team in updated_teams:
                    teams_display.append({
                        "Team": team.get("team_name", ""),
                        "Abbrev": team.get("abbreviation", ""),
                        "Conf": team.get("conference", ""),
                        "Pace": team.get("pace", ""),
                        "ORTG": team.get("ortg", ""),
                        "DRTG": team.get("drtg", ""),
                    })

                st.dataframe(teams_display, width="stretch", hide_index=True)
                st.caption(f"All {len(updated_teams)} teams saved to teams.csv and defensive_ratings.csv")
        else:
            st.error(
                "❌ **Failed to update team stats.**\n\n"
                "Check your internet connection and try again."
            )

    # --------------------------------------------------------
    # Action: Update Everything
    # --------------------------------------------------------
    elif current_action == "all":
        st.subheader("🔄 Updating All Data...")

        st.info(
            "⏳ **This may take several minutes.** We're fetching player stats, "
            "team stats, and game logs for standard deviation calculations. "
            "Please wait — don't close the tab!"
        )

        # Progress bar for the full update
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Progress callback for full update
        def update_all_progress(current, total, message):
            """Update progress bar for full update."""
            fraction = min(current / max(total, 1), 1.0)
            progress_bar.progress(fraction)
            status_text.text(f"⏳ {message}")

        # Run the full updater
        results = fetch_all_data(progress_callback=update_all_progress)

        # Clear the action flag
        st.session_state["update_action"] = None

        # Show results
        progress_bar.progress(1.0)
        status_text.text("✅ Update complete!")

        # Check which parts succeeded
        players_ok = results.get("players", False)
        teams_ok = results.get("teams", False)

        if players_ok and teams_ok:
            st.success("✅ **All data updated successfully!**")
        elif players_ok or teams_ok:
            st.warning(
                "⚠️ **Partial update completed.**\n"
                f"Players: {'✅ Success' if players_ok else '❌ Failed'}\n"
                f"Teams: {'✅ Success' if teams_ok else '❌ Failed'}"
            )
        else:
            st.error(
                "❌ **Update failed for all data types.**\n\n"
                "Check your internet connection and try again."
            )

        # Show summary even on partial success
        if players_ok:
            # Show updated player count
            updated_players = load_players_data()
            st.metric(
                label="👤 Players Updated",
                value=len(updated_players),
                help="Players now in players.csv"
            )

        if teams_ok:
            # Show updated team count
            updated_teams = load_teams_data()
            st.metric(
                label="🏆 Teams Updated",
                value=len(updated_teams),
                help="Teams now in teams.csv"
            )

        # Also try to fetch tonight's games
        st.markdown("---")
        st.markdown("**Fetching tonight's games...**")

        with st.spinner("Fetching tonight's games..."):
            todays_games = fetch_todays_games()

        if todays_games:
            st.session_state["todays_games"] = todays_games
            st.success(f"🏟️ Found **{len(todays_games)} game(s)** for tonight!")
        else:
            st.info("No games found for tonight (or no games scheduled). Enter games manually on the 🏀 Today's Games page.")

    # --------------------------------------------------------
    # Action: Refresh Injury Report (nba_api)
    # --------------------------------------------------------
    elif current_action == "injury_report":
        st.subheader("🏥 Refreshing Injury Report…")

        st.info(
            "Fetching real-time injury data from **NBA API** (official source). "
            "This typically takes 5–15 seconds."
        )

        # Clear the action flag immediately so a page reload doesn't re-run it
        st.session_state["update_action"] = None

        with st.spinner("Fetching injury data from NBA API…"):
            try:
                from data.roster_engine import RosterEngine as _RE
                _re = _RE()
                _re.refresh()
                scraped_data = _re.get_injury_report()
            except Exception as scrape_exc:
                scraped_data = {}
                st.error(f"❌ **Fetch failed:** {scrape_exc}")

        if scraped_data:
            # Record the timestamp
            _now_str = datetime.datetime.now().strftime("%b %d, %Y at %I:%M %p")
            st.session_state["injury_report_last_scraped"] = _now_str
            st.session_state["injury_report_data"] = scraped_data

            # Summary metrics
            out_count = sum(1 for v in scraped_data.values() if v.get("status") == "Out")
            gtd_count = sum(
                1 for v in scraped_data.values()
                if v.get("status") in ("GTD", "Questionable", "Doubtful", "Day-to-Day")
            )
            total_count = len(scraped_data)

            if total_count == 0:
                st.warning(
                    "⚠️ **0 injuries found** — all data sources returned empty results. "
                    "The NBA CDN feed and stats.nba.com may be temporarily unavailable. "
                    "Try again in a few minutes."
                )
            else:
                st.success(
                    f"✅ **Injury report refreshed** ({_now_str})  \n"
                    f"Found **{total_count}** players — "
                    f"**{out_count}** Out, **{gtd_count}** GTD/Questionable/Doubtful"
                )

            # Show a summary table
            st.markdown("### 📋 NBA API Injury Data")
            st.caption(
                "Showing players with a non-Active designation from the NBA API. "
                "Run a Smart Update or Full Setup to apply these to the "
                "full injury_status.json."
            )

            # Build display rows — only non-Active players
            _STATUS_ORDER = {
                "Out": 0, "Injured Reserve": 0,
                "Doubtful": 1, "GTD": 2, "Questionable": 2,
                "Day-to-Day": 3, "Probable": 4,
            }
            display_rows = [
                {
                    "Player":       key.title(),
                    "Team":         v.get("team", ""),
                    "Status":       v.get("status", ""),
                    "Injury":       v.get("injury", "") or v.get("comment", ""),
                    "Return Date":  v.get("return_date", ""),
                    "Source":       v.get("source", ""),
                    "_order":       _STATUS_ORDER.get(v.get("status", ""), 99),
                }
                for key, v in scraped_data.items()
                if v.get("status", "Active") not in ("Active", "Unknown")
            ]
            display_rows.sort(key=lambda r: (r["_order"], r["Player"]))

            if display_rows:
                # Render as an HTML table with status badge colours
                _STATUS_COLOURS = {
                    "Out":            ("#ff3366", "#fff"),
                    "Injured Reserve":("#cc0033", "#fff"),
                    "Doubtful":       ("#ff6600", "#fff"),
                    "GTD":            ("#ffd700", "#000"),
                    "Questionable":   ("#ffd700", "#000"),
                    "Day-to-Day":     ("#ffa500", "#000"),
                    "Probable":       ("#00cc66", "#000"),
                }

                def _badge(status):
                    bg, fg = _STATUS_COLOURS.get(status, ("#8b949e", "#fff"))
                    return (
                        f'<span style="background:{bg};color:{fg};padding:2px 7px;'
                        f'border-radius:6px;font-size:0.75rem;font-weight:700;">'
                        f"{status}</span>"
                    )

                table_html = (
                    '<table style="width:100%;border-collapse:collapse;font-size:0.88rem;">'
                    "<thead><tr>"
                    + "".join(
                        f'<th style="text-align:left;padding:6px 10px;border-bottom:1px solid #334;">{h}</th>'
                        for h in ("Player", "Team", "Status", "Injury / Note", "Return", "Source")
                    )
                    + "</tr></thead><tbody>"
                )
                for row in display_rows:
                    table_html += (
                        "<tr>"
                        f'<td style="padding:5px 10px;">{row["Player"]}</td>'
                        f'<td style="padding:5px 10px;">{row["Team"]}</td>'
                        f'<td style="padding:5px 10px;">{_badge(row["Status"])}</td>'
                        f'<td style="padding:5px 10px;">{row["Injury"]}</td>'
                        f'<td style="padding:5px 10px;">{row["Return Date"]}</td>'
                        f'<td style="padding:5px 10px;font-size:0.75rem;color:#8b949e;">{row["Source"]}</td>'
                        "</tr>"
                    )
                table_html += "</tbody></table>"
                st.markdown(table_html, unsafe_allow_html=True)
            else:
                st.info("No injured / non-Active players found in the scraped data.")

        else:
            if scraped_data is not None and not scraped_data:
                st.warning(
                    "⚠️ **No injury data was returned.** "
                    "The external sites may be unreachable or have changed their HTML structure. "
                    "Existing nba_api injury data is preserved."
                )

# ============================================================
# END SECTION: Execute the Selected Action
# ============================================================


# ============================================================
# SECTION: Fetch Platform Props
# Pull live prop lines from PrizePicks, Underdog Fantasy,
# and DraftKings Pick6 (via The Odds API) without needing
# the nba_api at all. Platforms only list players who are
# active and playing tonight, which naturally handles
# the injury/availability problem.
# ============================================================

st.divider()
st.subheader("📊 Fetch Platform Props")

st.markdown(
    "Pull **live prop lines** directly from the betting platforms. "
    "Platforms only list active players playing **tonight** — so this also "
    "acts as a real-time active roster check!"
)

st.markdown(get_education_box_html(
    "📖 How Platform Prop Fetching Works",
    """
    <strong>PrizePicks & Underdog</strong>: Free public APIs — no API key required. 
    Fetches all of tonight's NBA prop lines in seconds.<br><br>
    <strong>DraftKings Pick6</strong>: Fetched via 
    <a href="https://the-odds-api.com" target="_blank" style="color:#00f0ff;">The Odds API</a> 
    (free tier: 500 req/month). Configure your API key on the 
    <a href="/Settings" style="color:#ff5e00;">⚙️ Settings page</a>.<br><br>
    <strong>Cross-platform comparison</strong>: After fetching, the app shows all lines 
    side-by-side so you can see which platform has the best line for each pick.
    """
), unsafe_allow_html=True)

# ── Import platform fetcher ────────────────────────────────────
try:
    from data.platform_fetcher import (
        fetch_all_platform_props,
        summarize_props_by_platform,
        find_new_players_from_props,
        build_cross_platform_comparison,
    )
    from data.data_manager import (
        save_platform_props_to_session,
        load_platform_props_from_session,
        save_platform_props_to_csv,
    )
    _PLATFORM_FETCHER_AVAILABLE = True
except ImportError as _pf_err:
    _PLATFORM_FETCHER_AVAILABLE = False
    st.warning(f"⚠️ Platform fetcher not available: {_pf_err}")

if _PLATFORM_FETCHER_AVAILABLE:

    # ── Read current settings ──────────────────────────────────
    _pp_on = st.session_state.get("fetch_prizepicks_enabled", True)
    _ud_on = st.session_state.get("fetch_underdog_enabled", True)
    _dk_on = st.session_state.get("fetch_draftkings_enabled", True)
    _dk_key = st.session_state.get("odds_api_key", "").strip()

    # Show platform status badges
    _badge_style = (
        "padding:3px 10px;border-radius:6px;font-size:0.82rem;font-weight:700;"
        "margin-right:8px;display:inline-block;"
    )
    _pp_badge = (
        f'<span style="{_badge_style}background:#1a3d2b;color:#9ae6b4;">'
        f'{"✅" if _pp_on else "⏸️"} PrizePicks</span>'
    )
    _ud_badge = (
        f'<span style="{_badge_style}background:#2d1b69;color:#d6bcfa;">'
        f'{"✅" if _ud_on else "⏸️"} Underdog</span>'
    )
    _dk_badge = (
        f'<span style="{_badge_style}background:#1a2f4d;color:#bee3f8;">'
        f'{"✅" if _dk_on else "⏸️"} DraftKings '
        f'{"(key ✓)" if _dk_key else "(no key)"}</span>'
    )
    st.markdown(
        f'<div style="margin-bottom:12px;">{_pp_badge}{_ud_badge}{_dk_badge}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Enable/disable platforms and add DraftKings API key on the ⚙️ Settings page.")

    # ── Check for already-fetched props in session ─────────────
    _cached_platform_props = load_platform_props_from_session(st.session_state)
    if _cached_platform_props:
        _cached_summary = summarize_props_by_platform(_cached_platform_props)
        _total_cached = sum(_cached_summary.values())
        st.info(
            f"📦 **{_total_cached} props cached** from last fetch: "
            + " | ".join(f"{plat}: {cnt}" for plat, cnt in _cached_summary.items())
        )

    # ── Fetch buttons ─────────────────────────────────────────
    _fetch_col1, _fetch_col2, _fetch_col3, _fetch_col4 = st.columns(4)

    with _fetch_col1:
        _fetch_pp = st.button(
            "🟢 Fetch PrizePicks",
            disabled=not _pp_on,
            width="stretch",
            help="Fetch live prop lines from PrizePicks (no key required).",
        )
    with _fetch_col2:
        _fetch_ud = st.button(
            "🟣 Fetch Underdog",
            disabled=not _ud_on,
            width="stretch",
            help="Fetch live prop lines from Underdog Fantasy (no key required).",
        )
    with _fetch_col3:
        _fetch_dk = st.button(
            "🔵 Fetch DraftKings",
            disabled=not (_dk_on and _dk_key),
            width="stretch",
            help="Fetch DraftKings lines via The Odds API (key required).",
        )
    with _fetch_col4:
        _fetch_all = st.button(
            "🔄 Refresh All Props",
            type="primary",
            width="stretch",
            help="Fetch from all enabled platforms at once.",
        )

    # ── Execute fetches ────────────────────────────────────────
    _fetch_triggered = False
    _fetch_pp_only = False
    _fetch_ud_only = False
    _fetch_dk_only = False

    if _fetch_all:
        _fetch_triggered = True
    elif _fetch_pp:
        _fetch_triggered = True
        _fetch_pp_only = True
    elif _fetch_ud:
        _fetch_triggered = True
        _fetch_ud_only = True
    elif _fetch_dk:
        _fetch_triggered = True
        _fetch_dk_only = True

    if _fetch_triggered:
        _progress_bar = st.progress(0, text="Starting fetch...")

        def _progress_cb(current, total, message):
            pct = int((current / max(total, 1)) * 100)
            _progress_bar.progress(pct, text=message)

        with st.spinner("Fetching live props from betting platforms..."):
            _new_props = fetch_all_platform_props(
                include_prizepicks=_pp_on and (_fetch_all or _fetch_pp_only),
                include_underdog=_ud_on and (_fetch_all or _fetch_ud_only),
                include_draftkings=_dk_on and bool(_dk_key) and (_fetch_all or _fetch_dk_only),
                odds_api_key=_dk_key or None,
                progress_callback=_progress_cb,
            )

        _progress_bar.progress(100, text="Done!")

        if _new_props:
            # Save to session state so Prop Scanner and Analysis pages can use it
            save_platform_props_to_session(_new_props, st.session_state)

            # Also save props to session as current_props so they're immediately
            # available on the Prop Scanner page
            from data.data_manager import save_props_to_session
            save_props_to_session(_new_props, st.session_state)

            # Auto-save to disk so data persists across page navigations
            _saved_ok = save_platform_props_to_csv(_new_props)

            # Show per-platform summary
            _new_summary = summarize_props_by_platform(_new_props)
            st.success(
                f"✅ Fetched **{len(_new_props)} props** from "
                + ", ".join(f"**{plat}** ({cnt})" for plat, cnt in _new_summary.items())
                + (". Saved to `data/live_props.csv`." if _saved_ok else ".")
            )

            # Warn about new players not in our database
            _players_data_for_check = load_players_data()
            _new_players = find_new_players_from_props(_new_props, _players_data_for_check)
            if _new_players:
                with st.expander(
                    f"⚠️ {len(_new_players)} players from platforms not in local database",
                    expanded=False,
                ):
                    st.markdown(
                        "These players appear on betting platforms but are not in your "
                        "local player database. Consider running a **Smart Update** above "
                        "to fetch their season stats."
                    )
                    for _np in _new_players[:20]:
                        st.markdown(f"- {_np}")
                    if len(_new_players) > 20:
                        st.caption(f"... and {len(_new_players) - 20} more")

        else:
            st.warning(
                "⚠️ No props were returned. "
                "Check your internet connection and platform API status. "
                "PrizePicks and Underdog should always work without a key."
            )

    # ── Show cached props preview ──────────────────────────────
    _display_props = load_platform_props_from_session(st.session_state)
    if _display_props:
        with st.expander(
            f"📋 Preview Fetched Props ({len(_display_props)} total)",
            expanded=False,
        ):
            _preview_rows = []
            for _p in _display_props:
                _preview_rows.append({
                    "Player": _p.get("player_name", ""),
                    "Team": _p.get("team", ""),
                    "Stat": _p.get("stat_type", ""),
                    "Line": _p.get("line", ""),
                    "Platform": _p.get("platform", ""),
                    "Date": _p.get("game_date", ""),
                })
            st.dataframe(_preview_rows, width="stretch", hide_index=True)

# ============================================================
# END SECTION: Fetch Platform Props
# ============================================================


# ============================================================
# SECTION: Platform Roster Insights
# Cross-reference platform-confirmed active players against
# our player database to find gaps and potential injuries.
# ============================================================

if _PLATFORM_FETCHER_AVAILABLE:
    _roster_props = load_platform_props_from_session(st.session_state)
    if _roster_props:
        st.divider()
        st.subheader("🏥 Platform Roster Insights")
        st.markdown(
            "Cross-reference tonight's platform props against your player database "
            "to spot **missing players** and **potential injuries**."
        )

        try:
            from data.platform_fetcher import (
                extract_active_players_from_props,
                cross_reference_with_player_data,
                get_platform_confirmed_injuries,
            )

            _ri_players_data = load_players_data()
            _ri_active = extract_active_players_from_props(_roster_props)
            _ri_xref = cross_reference_with_player_data(_ri_active, _ri_players_data)

            # ── Summary metrics ──────────────────────────────────────
            _ri_col1, _ri_col2, _ri_col3 = st.columns(3)
            with _ri_col1:
                st.metric(
                    "✅ Platform-Confirmed Active",
                    len(_ri_active),
                    help="Unique players listed on at least one platform tonight.",
                )
            with _ri_col2:
                st.metric(
                    "⚠️ Missing from Your Database",
                    len(_ri_xref["missing_from_csv"]),
                    help="Players on platforms but not in your local players.csv. Run a Smart Update to add them.",
                )
            with _ri_col3:
                st.metric(
                    "🔴 Potentially Out Tonight",
                    len(_ri_xref["in_csv_but_not_on_platforms"]),
                    help="Players in your database on tonight's teams who are NOT listed on any platform (may be injured/sitting).",
                )

            # ── Missing players warning ──────────────────────────────
            if _ri_xref["missing_from_csv"]:
                with st.expander(
                    f"⚠️ {len(_ri_xref['missing_from_csv'])} players on platforms but NOT in your database",
                    expanded=False,
                ):
                    st.markdown(
                        "These players have active props on betting platforms but their stats "
                        "are **not in your local database**. Run a **Smart Update** above to "
                        "fetch their season stats before analyzing their props."
                    )
                    for _mp in _ri_xref["missing_from_csv"][:25]:
                        st.markdown(f"- {_mp}")
                    if len(_ri_xref["missing_from_csv"]) > 25:
                        st.caption(f"... and {len(_ri_xref['missing_from_csv']) - 25} more")

            # ── Platform-inferred injury report ──────────────────────
            _todays_games = st.session_state.get("todays_games", [])
            _ri_injuries = get_platform_confirmed_injuries(
                _ri_active, _ri_players_data, _todays_games
            )
            if _ri_injuries:
                with st.expander(
                    f"🔴 {len(_ri_injuries)} players potentially out (not on any platform)",
                    expanded=False,
                ):
                    st.markdown(
                        "These players are in your database and on a team playing tonight, "
                        "but **no platform has props for them**. They may be injured, resting, "
                        "or sitting out — even if not yet on the official injury report."
                    )
                    _inj_rows = [
                        {"Player": p["name"], "Team": p["team"], "Status": p["reason"]}
                        for p in _ri_injuries[:30]
                    ]
                    st.dataframe(_inj_rows, width="stretch", hide_index=True)
                    if len(_ri_injuries) > 30:
                        st.caption(f"... and {len(_ri_injuries) - 30} more")
            elif _todays_games:
                st.success("✅ All players in your database playing tonight appear on at least one platform.")

        except Exception as _ri_err:
            st.warning(f"⚠️ Could not load roster insights: {_ri_err}")

# ============================================================
# END SECTION: Platform Roster Insights
# ============================================================


# ============================================================
# SECTION: Help and Tips
# ============================================================

st.divider()

with st.expander("💡 Tips & FAQ", expanded=False):
    st.markdown("""
    ### Frequently Asked Questions

    **Q: How often should I update?**
    A: Update **before each betting session**. Player stats change slowly,
    but team and player situations change week-to-week. Updating once per day
    before you bet is ideal.

    ---

    **Q: Why does the update take so long?**
    A: We add a 1.5-second delay between each API call to avoid being blocked
    by the NBA's servers. With 500+ players, fetching game logs takes time.
    This is normal and necessary!

    BEGINNER NOTE: "Rate limiting" means a website limits how many requests
    you can make per minute. If you ask too fast, they block you temporarily.
    The delay prevents this.

    ---

    **Q: What happens if the update fails?**
    A: Nothing breaks! The app just keeps using the existing CSV data.
    Try again in a few minutes — the NBA API is occasionally slow or down.

    ---

    **Q: Where does the data come from?**
    A: The `nba_api` library fetches data from **stats.nba.com** — the NBA's
    official statistics website. It's the same data ESPN and basketball-reference
    use! No account or API key needed.

    ---

    **Q: Does this work during the offseason?**
    A: Player and team stats from the most recent completed season will still
    be available. "Tonight's games" will return nothing during the offseason.

    ---

    **Q: I see 'no data yet' even after updating. Why?**
    A: The players.csv file gets written when you click Update. If you still see "no data"
    in the status, try refreshing the page or running the update again.

    ---

    **Q: How do I get DraftKings props?**
    A: Get a free API key from [the-odds-api.com](https://the-odds-api.com),
    add it on the ⚙️ Settings page, then click "Fetch DraftKings" or "Refresh All Props".
    """)

# ============================================================
# END SECTION: Help and Tips
# ============================================================
