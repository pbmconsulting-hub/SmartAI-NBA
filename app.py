# ============================================================
# FILE: app.py
# PURPOSE: Main entry point for the SmartAI-NBA v7 Streamlit app.
#          Shows the welcome screen, quick-start guide, and status
#          dashboard. All other pages are in the pages/ folder.
# HOW TO RUN: streamlit run app.py
# ============================================================

import streamlit as st
import datetime
import os
from data.data_manager import load_players_data, load_props_data, load_teams_data
from data.live_data_fetcher import load_last_updated
from tracking.database import initialize_database

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="SmartAI-NBA v7",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# SECTION: Global CSS Theme
# ============================================================

st.markdown("""
<style>
/* Dark gradient header banner */
.hero-banner {
    background: linear-gradient(135deg, #0f3460 0%, #16213e 50%, #1a1a2e 100%);
    border-radius: 14px;
    padding: 32px 40px;
    margin-bottom: 24px;
    border: 1px solid #e94560;
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: "🏀";
    position: absolute;
    right: 30px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 5rem;
    opacity: 0.12;
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    color: #ffffff;
    margin: 0;
    line-height: 1.2;
}
.hero-subtitle {
    color: #a0aec0;
    font-size: 1.05rem;
    margin-top: 6px;
}
.hero-date {
    color: #e94560;
    font-size: 1rem;
    font-weight: 600;
    margin-top: 8px;
}

/* Status cards */
.status-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
    color: #ffffff;
}
.status-card .sc-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f6e58d;
    display: block;
}
.status-card .sc-label {
    font-size: 0.8rem;
    color: #a0aec0;
    margin-top: 2px;
}
.status-card .sc-live {
    font-size: 0.72rem;
    color: #68d391;
    margin-top: 4px;
}

/* Slate section */
.slate-card {
    background: rgba(15, 52, 96, 0.4);
    border: 1px solid rgba(99, 179, 237, 0.25);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 8px;
    color: #e2e8f0;
    font-size: 0.95rem;
}
.slate-card .sc-matchup { font-weight: 600; color: #ffffff; }
.slate-card .sc-meta { color: #a0aec0; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Initialize App on Startup
# ============================================================

initialize_database()

defaults = {
    "simulation_depth": 1000,
    "minimum_edge_threshold": 5.0,
    "entry_fee": 10.0,
    "selected_platforms": ["PrizePicks", "Underdog", "DraftKings"],
    "todays_games": [],
    "analysis_results": [],
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ============================================================
# SECTION: Hero Banner
# ============================================================

today_str = datetime.date.today().strftime("%A, %B %d, %Y")
st.markdown(f"""
<div class="hero-banner">
  <div class="hero-title">SmartAI-NBA v7</div>
  <div class="hero-subtitle">Your Personal NBA Prop Betting Analysis Engine</div>
  <div class="hero-date">📅 {today_str}</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Status Dashboard
# ============================================================

players_data = load_players_data()
props_data = load_props_data()
teams_data = load_teams_data()

number_of_todays_games = len(st.session_state.get("todays_games", []))
current_props = st.session_state.get("current_props", props_data)
number_of_current_props = len(current_props)
number_of_analysis_results = len(st.session_state.get("analysis_results", []))

live_data_timestamps = load_last_updated()
is_using_live_data = live_data_timestamps.get("is_live", False)

data_status_label = "🟢 Live" if is_using_live_data else "🟡 Sample"

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
<div class="status-card">
  <span class="sc-value">{len(players_data)}</span>
  <div class="sc-label">Players in Database</div>
  <div class="sc-live">{data_status_label} data</div>
</div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
<div class="status-card">
  <span class="sc-value">{number_of_current_props}</span>
  <div class="sc-label">Props Loaded</div>
  <div class="sc-live">Ready for analysis</div>
</div>""", unsafe_allow_html=True)

with col3:
    games_val = number_of_todays_games if number_of_todays_games > 0 else "—"
    st.markdown(f"""
<div class="status-card">
  <span class="sc-value">{games_val}</span>
  <div class="sc-label">Games Tonight</div>
  <div class="sc-live">Go to Today's Games</div>
</div>""", unsafe_allow_html=True)

with col4:
    results_val = number_of_analysis_results if number_of_analysis_results > 0 else "—"
    st.markdown(f"""
<div class="status-card">
  <span class="sc-value">{results_val}</span>
  <div class="sc-label">Analysis Results</div>
  <div class="sc-live">Go to Analysis page</div>
</div>""", unsafe_allow_html=True)

with col5:
    team_count = len(teams_data)
    st.markdown(f"""
<div class="status-card">
  <span class="sc-value">{team_count}</span>
  <div class="sc-label">Teams Loaded</div>
  <div class="sc-live">{data_status_label} data</div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# SECTION: Live Data Status
# ============================================================

if is_using_live_data:
    def format_timestamp(ts_string):
        if not ts_string:
            return "never"
        try:
            dt = datetime.datetime.fromisoformat(ts_string)
            return dt.strftime("%b %d at %I:%M %p")
        except Exception:
            return "unknown"

    player_ts = live_data_timestamps.get("players")
    team_ts = live_data_timestamps.get("teams")
    st.success(
        f"✅ **Using Live NBA Data** — "
        f"Players: {format_timestamp(player_ts)} | "
        f"Teams: {format_timestamp(team_ts)}"
    )
else:
    st.info(
        "📊 **Using Sample Data** — Go to **🔄 Update Data** to pull real, up-to-date "
        "NBA stats, or use **🏀 Today's Games → ⚡ Fetch Players (Today Only)** for a "
        "fast targeted update (1-2 min)!"
    )

st.divider()

# ============================================================
# SECTION: Tonight's Slate Preview
# ============================================================

todays_games = st.session_state.get("todays_games", [])
if todays_games:
    st.subheader(f"🏟️ Tonight's Slate — {len(todays_games)} Game(s)")
    for game in todays_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_name = game.get("home_team_name", home)
        away_name = game.get("away_team_name", away)
        home_record = game.get("home_record", "")
        away_record = game.get("away_record", "")
        total = game.get("game_total", 220.0)
        spread = game.get("vegas_spread", 0.0)

        home_str = f"{home_name} ({home_record})" if home_record else home_name
        away_str = f"{away_name} ({away_record})" if away_record else away_name

        if spread > 0:
            spread_str = f"Spread: {home} -{spread}"
        elif spread < 0:
            spread_str = f"Spread: {away} -{abs(spread)}"
        else:
            spread_str = "PK"
        st.markdown(
            f'<div class="slate-card">'
            f'<span class="sc-matchup">🏠 {home_str} vs {away_str}</span>'
            f'<span class="sc-meta"> &nbsp;|&nbsp; {spread_str} &nbsp;|&nbsp; O/U: {total}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("👆 Go to **🏀 Today's Games** to load tonight's matchups.")

st.divider()

# ============================================================
# SECTION: Quick Start Guide
# ============================================================

left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("🚀 Quick Start Guide")
    st.markdown("""
    **Follow these steps to find tonight's best bets:**

    **Step 0** → 🏀 **Today's Games** — Click **🔄 Auto-Load Tonight's Games** to fetch
    real matchups. Then click **⚡ Fetch Players (Today Only)** to pull current rosters
    fast (1-2 min, only today's teams, no traded players).

    **Step 1** → 📥 **Import Props** — Enter prop lines manually or upload a CSV.
    Sample props are pre-loaded so you can start immediately!

    **Step 2** → 🏆 **Analysis** — Click "Run Analysis" to run the Monte Carlo simulation.
    See probability, edge, tier, and direction for every prop.

    **Step 3** → 🎰 **Entry Builder** — Build optimal parlays for PrizePicks, Underdog,
    and DraftKings with exact EV calculations.

    **Step 4** → 📊 **Model Health** — After games, log results to track accuracy.
    """)

with right_column:
    st.subheader("⚙️ Current Settings")
    st.info(f"""
    **Simulations:** {st.session_state['simulation_depth']:,}

    **Min Edge:** {st.session_state['minimum_edge_threshold']}%

    **Entry Fee:** ${st.session_state['entry_fee']:.2f}

    **Platforms:** {', '.join(st.session_state['selected_platforms'])}
    """)
    st.caption("Change these on the ⚙️ Settings page")

st.divider()

# ============================================================
# SECTION: How It Works
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

    #### 5. ⚡ Targeted Data Fetching
    The new **Fetch Players (Today Only)** mode uses `commonteamroster`
    to get CURRENT rosters (reflecting trades/signings) for tonight's teams only.
    This runs in 1-2 minutes and ensures no traded players appear.

    ---

    *All math is built from scratch using Python's standard library.
    No external dependencies except Streamlit and nba_api!*
    """)

st.divider()
st.caption(
    f"SmartAI-NBA v7 | Built for personal use | "
    f"Last loaded: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | "
    f"Data: {len(players_data)} players, {len(teams_data)} teams"
)
