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

# Import nba_api injury fetcher for the injury report refresh button.
# Available whenever nba_api is installed (listed in requirements.txt).
_web_scraper_available = False
try:
    from data.web_scraper import fetch_all_injury_data  # noqa: F401
    _web_scraper_available = True
except ImportError:
    pass

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
    <strong>Live vs Sample data</strong>: Live data = real current season stats from NBA.com. 
    Sample data = pre-loaded example data for demonstration.<br><br>
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


# ============================================================
# SECTION: Data Status Display
# Show when each data type was last updated (so user knows
# if data is fresh or stale).
# ============================================================

st.subheader("📅 Data Status")

# Load the timestamps from the JSON file
# BEGINNER NOTE: load_last_updated() reads last_updated.json
# and returns a dict like {'players': '2026-03-06T14:30:00', ...}
timestamps = load_last_updated()

# Display status in three columns (one for each data type)
col_players_status, col_teams_status, col_games_status = st.columns(3)

with col_players_status:
    # Show when player stats were last updated
    player_timestamp = timestamps.get("players", None)  # None = never updated
    if player_timestamp:
        # Parse the ISO format string back into a datetime object
        dt = datetime.datetime.fromisoformat(player_timestamp)
        # Format as human-readable string
        formatted_time = dt.strftime("%b %d, %Y at %I:%M %p")
        st.success(f"✅ **Players**\nLast updated: {formatted_time}")
    else:
        # No timestamp = using sample data
        st.warning("⚠️ **Players**\nUsing sample data")

with col_teams_status:
    # Show when team stats were last updated
    team_timestamp = timestamps.get("teams", None)
    if team_timestamp:
        dt = datetime.datetime.fromisoformat(team_timestamp)
        formatted_time = dt.strftime("%b %d, %Y at %I:%M %p")
        st.success(f"✅ **Teams**\nLast updated: {formatted_time}")
    else:
        st.warning("⚠️ **Teams**\nUsing sample data")

with col_games_status:
    # Show tonight's game count from session state
    todays_games = st.session_state.get("todays_games", [])  # Get from session
    if todays_games:
        st.success(f"✅ **Tonight's Games**\n{len(todays_games)} game(s) loaded")
    else:
        st.warning("⚠️ **Tonight's Games**\nNo games loaded yet")

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
        use_container_width=True,
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
        use_container_width=True,
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
        use_container_width=True,
        help="Pull tonight's real NBA matchups automatically",
    ):
        st.session_state["update_action"] = "games"

with btn_col2:
    if st.button(
        "👤 Update Player Stats (All — Slow)",
        use_container_width=True,
        help="Pull current season averages for ALL NBA players (~500, 5-15 min)",
    ):
        st.session_state["update_action"] = "players"

with btn_col3:
    if st.button(
        "🏆 Update Team Stats",
        use_container_width=True,
        help="Pull team pace, offensive rating, and defensive rating",
    ):
        st.session_state["update_action"] = "teams"

with btn_col4:
    if st.button(
        "🔄 Update Everything (Full)",
        use_container_width=True,
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
    _injury_btn_disabled = not _web_scraper_available
    if st.button(
        "🔄 Refresh Injury Report",
        use_container_width=True,
        help="Fetch live GTD/Out/injury data from the official NBA API (requires nba_api)",
        disabled=_injury_btn_disabled,
    ):
        st.session_state["update_action"] = "injury_report"

with injury_btn_col2:
    if _web_scraper_available:
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
            st.dataframe(games_display, use_container_width=True, hide_index=True)

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

                st.dataframe(players_display, use_container_width=True, hide_index=True)
                st.caption(f"Showing 20 of {len(updated_players)} players. Full data saved to sample_players.csv")
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

                st.dataframe(teams_display, use_container_width=True, hide_index=True)
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
                help="Players now in sample_players.csv"
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
                from data.web_scraper import fetch_all_injury_data
                scraped_data = fetch_all_injury_data()
            except ImportError:
                scraped_data = {}
                st.error(
                    "❌ **Missing dependencies.** "
                    "Run `pip install nba_api` then restart the app."
                )
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

    **Q: I see 'sample data' even after updating. Why?**
    A: The sample_players.csv file gets **overwritten** with live data when you
    click Update. If you still see "sample data" in the status, try refreshing
    the page or running the update again.
    """)

# ============================================================
# END SECTION: Help and Tips
# ============================================================
