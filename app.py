# ============================================================
# FILE: app.py
# PURPOSE: Main entry point for the SmartAI-NBA v7 Streamlit app.
#          Shows the welcome screen, quick-start guide, and status
#          dashboard. All other pages are in the pages/ folder.
# HOW TO RUN: streamlit run app.py
# CONCEPTS COVERED: Streamlit basics, session state, page config
# ============================================================

# Import streamlit — our main UI framework
import streamlit as st  # st is the standard alias everyone uses

# Standard library imports (no install needed — comes with Python)
import datetime  # To show today's date and time
import os        # For file path checks

# Import our data loading module
from data.data_manager import load_players_data, load_props_data, load_teams_data

# Import our live data status checker
# BEGINNER NOTE: load_last_updated reads a JSON file that tracks when
# live data was last fetched. If the file doesn't exist, it means we
# are still using sample data.
from data.live_data_fetcher import load_last_updated

# Import our database initializer (creates the DB on first run)
from tracking.database import initialize_database

# ============================================================
# SECTION: Page Configuration
# This MUST be the FIRST streamlit call in the file.
# It sets the browser tab title, icon, and layout.
# ============================================================

st.set_page_config(
    page_title="SmartAI-NBA v7",      # Browser tab title
    page_icon="🏀",                    # Browser tab icon
    layout="wide",                     # Use full screen width
    initial_sidebar_state="expanded",  # Show sidebar by default
)

# ============================================================
# END SECTION: Page Configuration
# ============================================================

# ============================================================
# SECTION: Initialize App on Startup
# Run setup tasks that only need to happen once per session.
# ============================================================

# Initialize the SQLite database (creates tables if they don't exist)
initialize_database()

# Set default settings in session state if not already set
# BEGINNER NOTE: Session state persists data between pages.
# Think of it as global variables that survive page changes.
if "simulation_depth" not in st.session_state:
    st.session_state["simulation_depth"] = 1000  # Default: 1000 simulations

if "minimum_edge_threshold" not in st.session_state:
    st.session_state["minimum_edge_threshold"] = 5.0  # Need 5% edge to show

if "entry_fee" not in st.session_state:
    st.session_state["entry_fee"] = 10.0  # Default $10 entry

if "selected_platforms" not in st.session_state:
    st.session_state["selected_platforms"] = ["PrizePicks", "Underdog", "DraftKings"]

if "todays_games" not in st.session_state:
    st.session_state["todays_games"] = []  # Empty until user enters games

if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = []  # Empty until analysis runs

# ============================================================
# END SECTION: Initialize App on Startup
# ============================================================

# ============================================================
# SECTION: Welcome Header
# ============================================================

# Display the main title with emoji and styled text
st.title("🏀 SmartAI-NBA v7")
st.markdown("### *Your Personal NBA Prop Betting Analysis Engine*")

# Horizontal divider line
st.divider()

# ============================================================
# END SECTION: Welcome Header
# ============================================================

# ============================================================
# SECTION: Status Dashboard
# Show a quick overview of the app's current status.
# ============================================================

# Load data to show how many players/props are available
players_data = load_players_data()    # List of player dicts
props_data = load_props_data()        # List of prop dicts
teams_data = load_teams_data()        # List of team dicts

# Count how many games are set up for today
number_of_todays_games = len(st.session_state.get("todays_games", []))

# Count how many props have been entered (from session or sample data)
current_props = st.session_state.get("current_props", props_data)
number_of_current_props = len(current_props)

# Count how many analysis results exist
number_of_analysis_results = len(st.session_state.get("analysis_results", []))

# Display status metrics in columns (side-by-side layout)
# BEGINNER NOTE: st.columns() creates a row of equal-width boxes
column1, column2, column3, column4 = st.columns(4)

with column1:
    # st.metric shows a big number with a label
    st.metric(
        label="📋 Players in Database",
        value=len(players_data),
        help="Total players with stats loaded from sample_players.csv"
    )

with column2:
    st.metric(
        label="🎯 Props Loaded",
        value=number_of_current_props,
        help="Prop lines available for analysis"
    )

with column3:
    st.metric(
        label="🏟️ Games Tonight",
        value=number_of_todays_games if number_of_todays_games > 0 else "—",
        help="Games set up on the Today's Games page"
    )

with column4:
    st.metric(
        label="📊 Analysis Results",
        value=number_of_analysis_results if number_of_analysis_results > 0 else "—",
        help="Props analyzed — go to Analysis page to run"
    )

# ============================================================
# END SECTION: Status Dashboard
# ============================================================

st.divider()

# ============================================================
# SECTION: Live Data Status Indicator
# Show whether the app is using sample data or live data,
# and when data was last updated.
# ============================================================

# Load timestamps from last_updated.json
# BEGINNER NOTE: load_last_updated() returns a dict like:
# {'players': '2026-03-06T14:30:00', 'teams': '...', 'is_live': True}
# If the file doesn't exist yet, it returns an empty dict {}.
live_data_timestamps = load_last_updated()

# Check if we have any live data (is_live flag is set)
is_using_live_data = live_data_timestamps.get("is_live", False)

if is_using_live_data:
    # Show which data types have been updated and when
    player_ts = live_data_timestamps.get("players")   # Player update timestamp
    team_ts = live_data_timestamps.get("teams")        # Team update timestamp

    # Format timestamps for display (convert ISO format to human-readable)
    def format_timestamp(ts_string):
        """Convert ISO timestamp string to friendly format like 'Mar 6, 2:30 PM'."""
        if not ts_string:
            return "never"  # No timestamp = never updated
        try:
            dt = datetime.datetime.fromisoformat(ts_string)
            return dt.strftime("%b %d at %I:%M %p")  # e.g. "Mar 6 at 2:30 PM"
        except Exception:
            return "unknown"  # If parsing fails, show "unknown"

    # Show a success banner with last update times
    st.success(
        f"✅ **Using Live NBA Data** — "
        f"Players: {format_timestamp(player_ts)} | "
        f"Teams: {format_timestamp(team_ts)}"
    )
else:
    # No live data — show a reminder to update
    st.info(
        "📊 **Using Sample Data** — Go to the **🔄 Update Data** page to pull "
        "real, up-to-date NBA stats for more accurate predictions!"
    )

# ============================================================
# END SECTION: Live Data Status Indicator
# ============================================================

st.divider()

# ============================================================
# SECTION: Quick Start Guide
# Show new users exactly how to use the app.
# ============================================================

# Two-column layout: guide on left, tech info on right
left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("🚀 Quick Start Guide")
    st.markdown("""
    **Follow these steps to find tonight's best bets:**

    **Step 0** → 🔄 **Update Data** *(optional but recommended)* — Click
    "Update Everything" to pull real, live NBA stats before you start.
    The app works with sample data, but live data is much more accurate!

    **Step 1** → 🏀 **Today's Games** — Select which teams are playing tonight
    and enter the Vegas spread + total for each game.

    **Step 2** → 📥 **Import Props** — Enter prop lines manually or upload a CSV.
    Sample props are pre-loaded so you can start immediately!

    **Step 3** → 🏆 **Analysis** — Click "Run Analysis" to run the Monte Carlo
    simulation. See probability, edge, tier, and direction for every prop.

    **Step 4** → 🎰 **Entry Builder** — Build optimal parlays for PrizePicks,
    Underdog, and DraftKings with exact EV calculations.

    **Step 5** → 📊 **Model Health** — After games, log results to track
    how accurate the model is over time.
    """)

with right_column:
    st.subheader("⚙️ Current Settings")

    # Show the current simulation settings
    st.info(f"""
    **Simulations:** {st.session_state['simulation_depth']:,}

    **Min Edge:** {st.session_state['minimum_edge_threshold']}%

    **Entry Fee:** ${st.session_state['entry_fee']:.2f}

    **Platforms:** {', '.join(st.session_state['selected_platforms'])}
    """)

    # Link to settings page
    st.caption("Change these on the ⚙️ Settings page")

# ============================================================
# END SECTION: Quick Start Guide
# ============================================================

st.divider()

# ============================================================
# SECTION: How It Works
# Brief explanation of the engine for curious users.
# ============================================================

with st.expander("📖 How Does SmartAI-NBA Work?", expanded=False):
    st.markdown("""
    ### The Engine Under the Hood

    SmartAI-NBA uses **Monte Carlo simulation** to predict player stat outcomes.
    Here's what happens when you click "Run Analysis":

    ---

    #### 1. 📐 Projection Building
    For each player's stat, we take their season average and adjust it for:
    - **Opponent defense** — tough defenders reduce expected output
    - **Game pace** — faster games = more stat opportunities
    - **Home/away** — home court advantage is real
    - **Rest** — back-to-back games cause fatigue

    #### 2. 🎲 Monte Carlo Simulation
    We simulate **1,000+ games** for each player. In each simulated game:
    - Minutes are randomized (blowout risk, foul trouble)
    - Stats are randomly drawn from a normal distribution
    - The result is recorded (over or under the line?)

    After 1,000 games, the % of games that went over the line = our probability.

    #### 3. 🔍 Force Analysis
    We identify all factors pushing the stat **MORE** or **LESS**:
    - Weak defense? → OVER force
    - Back-to-back game? → UNDER force
    - The count and strength of forces determines confidence.

    #### 4. 🏆 Confidence Scoring
    A weighted 0-100 score combines probability strength, edge size,
    directional agreement, matchup quality, and player consistency.
    This gives you **Platinum/Gold/Silver/Bronze** tiers.

    #### 5. 💰 EV Calculation
    For parlays, we calculate **Expected Value** = exactly how much
    you'd win (or lose) on average per dollar wagered.

    ---

    *All math is built from scratch using Python's standard library.
    No external dependencies except Streamlit!*
    """)

# ============================================================
# END SECTION: How It Works
# ============================================================

# ============================================================
# SECTION: Footer
# ============================================================

st.divider()
st.caption(
    f"SmartAI-NBA v7 | Built for personal use | "
    f"Last loaded: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | "
    f"Data: {len(players_data)} players, {len(teams_data)} teams"
)

# ============================================================
# END SECTION: Footer
# ============================================================
