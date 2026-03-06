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
    fetch_todays_games,     # Fetch tonight's NBA games
    fetch_player_stats,     # Fetch all player season averages
    fetch_team_stats,       # Fetch all team stats + defensive ratings
    fetch_all_data,         # Fetch everything at once
    load_last_updated,      # Load timestamps from last_updated.json
)

# ============================================================
# SECTION: Page Setup
# ============================================================

# Configure the page (MUST be the first streamlit call)
st.set_page_config(
    page_title="Update Data — SmartAI-NBA",
    page_icon="🔄",
    layout="wide",  # Use full-width layout
)

# Page title and description
st.title("🔄 Update Live NBA Data")
st.markdown(
    "Pull real, up-to-date NBA stats from the **nba_api** library "
    "(free, no API key required). Update before each betting session "
    "for the most accurate predictions!"
)
st.divider()

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

# BEGINNER NOTE: st.columns() creates side-by-side layout.
# Here we make 4 equal-width columns for the 4 buttons.
btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

# Track which action the user clicked
# BEGINNER NOTE: We use session state to remember what button was pressed
# even after the page reruns (Streamlit reruns the script on every interaction)
if "update_action" not in st.session_state:
    st.session_state["update_action"] = None  # No action yet

with btn_col1:
    # Button to fetch tonight's games
    if st.button(
        "🏟️ Fetch Tonight's Games",
        use_container_width=True,  # Fill the column width
        help="Pull tonight's real NBA matchups automatically",
    ):
        st.session_state["update_action"] = "games"  # Mark which action to run

with btn_col2:
    # Button to update player stats
    if st.button(
        "👤 Update Player Stats",
        use_container_width=True,
        help="Pull current season averages for all NBA players",
    ):
        st.session_state["update_action"] = "players"

with btn_col3:
    # Button to update team stats
    if st.button(
        "🏆 Update Team Stats",
        use_container_width=True,
        help="Pull team pace, offensive rating, and defensive rating",
    ):
        st.session_state["update_action"] = "teams"

with btn_col4:
    # Button to update everything at once
    if st.button(
        "🔄 Update Everything",
        use_container_width=True,
        type="primary",  # Highlighted button style
        help="Update all data: games, players, and teams",
    ):
        st.session_state["update_action"] = "all"

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
    # Action: Fetch Tonight's Games
    # --------------------------------------------------------
    if current_action == "games":
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
