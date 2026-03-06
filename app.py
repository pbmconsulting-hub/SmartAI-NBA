# ============================================================
# FILE: app.py
# PURPOSE: Main entry point for the SmartAI-NBA v7 Streamlit app.
#          Professional dark-themed dashboard with today's slate,
#          status cards, and quick-start guide.
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

# ─── Dark Theme CSS ───────────────────────────────────────────
st.markdown("""
<style>
/* Hero banner gradient */
.hero-banner {
    background: linear-gradient(135deg, #0f3460 0%, #533483 50%, #e94560 100%);
    border-radius: 14px;
    padding: 28px 36px;
    margin-bottom: 24px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    color: #ffffff;
    margin: 0;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}
.hero-subtitle {
    font-size: 1.05rem;
    color: rgba(255,255,255,0.85);
    margin-top: 6px;
}
.hero-date {
    font-size: 0.95rem;
    color: rgba(255,255,255,0.7);
    margin-top: 4px;
}
/* Status card */
.status-card {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid #0f3460;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.status-card-value {
    font-size: 2rem;
    font-weight: 800;
    color: #e2e8f0;
}
.status-card-label {
    font-size: 0.8rem;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
}
/* Tonight's slate team chips */
.team-chip {
    display: inline-block;
    background: #0f3460;
    color: #e2e8f0;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    margin: 3px;
}
/* Tier badge pill */
.live-badge {
    display: inline-block;
    background: #276749;
    color: #9ae6b4;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
}
.sample-badge {
    display: inline-block;
    background: #744210;
    color: #fbd38d;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Configuration
# ============================================================

# ============================================================
# SECTION: Initialize App on Startup
# ============================================================

initialize_database()

if "simulation_depth" not in st.session_state:
    st.session_state["simulation_depth"] = 1000
if "minimum_edge_threshold" not in st.session_state:
    st.session_state["minimum_edge_threshold"] = 5.0
if "entry_fee" not in st.session_state:
    st.session_state["entry_fee"] = 10.0
if "selected_platforms" not in st.session_state:
    st.session_state["selected_platforms"] = ["PrizePicks", "Underdog", "DraftKings"]
if "todays_games" not in st.session_state:
    st.session_state["todays_games"] = []
if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = []

# ============================================================
# END SECTION: Initialize App on Startup
# ============================================================

# ============================================================
# SECTION: Hero Banner
# ============================================================

today_str = datetime.date.today().strftime("%A, %B %d, %Y")
todays_games = st.session_state.get("todays_games", [])
game_count = len(todays_games)
game_count_text = f"{game_count} game{'s' if game_count != 1 else ''} loaded" if game_count else "No games loaded yet"

st.markdown(f"""
<div class="hero-banner">
  <div class="hero-title">🏀 SmartAI-NBA <span style="font-size:1.4rem; font-weight:600; opacity:0.8;">v7</span></div>
  <div class="hero-subtitle">Your Personal NBA Prop Betting Analysis Engine</div>
  <div class="hero-date">📅 {today_str} &nbsp;•&nbsp; 🏟️ {game_count_text}</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION: Hero Banner
# ============================================================

# ============================================================
# SECTION: Tonight's Slate
# ============================================================

if todays_games:
    st.subheader("🏟️ Tonight's Slate")

    # Build team chips
    chips_html = ""
    for game in todays_games:
        away = game.get("away_team", "")
        home = game.get("home_team", "")
        aw = game.get("away_wins", 0)
        al = game.get("away_losses", 0)
        hw = game.get("home_wins", 0)
        hl = game.get("home_losses", 0)
        rec_a = f" ({aw}-{al})" if aw or al else ""
        rec_h = f" ({hw}-{hl})" if hw or hl else ""
        chips_html += f'<span class="team-chip">🚌 {away}{rec_a}</span> '
        chips_html += f'<span style="color:#e94560; font-weight:700; font-size:0.9rem;">vs</span> '
        chips_html += f'<span class="team-chip">🏠 {home}{rec_h}</span> &nbsp;&nbsp;&nbsp;'

    st.markdown(f'<div style="margin:8px 0 4px 0;">{chips_html}</div>', unsafe_allow_html=True)
    st.caption("Go to 🏀 Today's Games to update spreads/totals")
    st.divider()

# ============================================================
# END SECTION: Tonight's Slate
# ============================================================

# ============================================================
# SECTION: Status Dashboard
# ============================================================

players_data = load_players_data()
props_data = load_props_data()
teams_data = load_teams_data()

current_props = st.session_state.get("current_props", props_data)
number_of_current_props = len(current_props)
number_of_analysis_results = len(st.session_state.get("analysis_results", []))

# Live data status
live_data_timestamps = load_last_updated()
is_using_live_data = live_data_timestamps.get("is_live", False)
data_badge = '<span class="live-badge">✅ LIVE</span>' if is_using_live_data else '<span class="sample-badge">📊 SAMPLE</span>'

st.subheader("📊 Status")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="status-card">
      <div class="status-card-value">{len(players_data)}</div>
      <div class="status-card-label">👤 Players</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="status-card">
      <div class="status-card-value">{number_of_current_props}</div>
      <div class="status-card-label">🎯 Props</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    val3 = str(game_count) if game_count else "—"
    st.markdown(f"""
    <div class="status-card">
      <div class="status-card-value">{val3}</div>
      <div class="status-card-label">🏟️ Games Tonight</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    val4 = str(number_of_analysis_results) if number_of_analysis_results else "—"
    st.markdown(f"""
    <div class="status-card">
      <div class="status-card-value">{val4}</div>
      <div class="status-card-label">📈 Analyzed</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="status-card">
      <div class="status-card-value" style="font-size:1.1rem; padding-top:8px;">{data_badge}</div>
      <div class="status-card-label">Data Source</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ============================================================
# END SECTION: Status Dashboard
# ============================================================

# ============================================================
# SECTION: Live Data Status Banner
# ============================================================

if is_using_live_data:
    player_ts = live_data_timestamps.get("players")
    team_ts = live_data_timestamps.get("teams")

    def format_timestamp(ts_string):
        if not ts_string:
            return "never"
        try:
            dt = datetime.datetime.fromisoformat(ts_string)
            return dt.strftime("%b %d at %I:%M %p")
        except Exception:
            return "unknown"

    st.success(
        f"✅ **Using Live NBA Data** — "
        f"Players: {format_timestamp(player_ts)} | "
        f"Teams: {format_timestamp(team_ts)}"
    )
else:
    st.info(
        "📊 **Using Sample Data** — Go to the **🔄 Update Data** page to pull "
        "real, up-to-date NBA stats for more accurate predictions!"
    )

# ============================================================
# END SECTION: Live Data Status Banner
# ============================================================

st.divider()

# ============================================================
# SECTION: Quick Start Guide
# ============================================================

left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("🚀 Quick Start Guide")
    st.markdown("""
    **Follow these steps to find tonight's best bets:**

    **Step 0** → 🏀 **Today's Games** — Click
    "**Auto-Load Tonight's Games**" for a ONE-CLICK setup:
    fetches tonight's matchups + current rosters + player stats + team stats.
    Everything you need in a single button press!

    **Step 1** → 📥 **Import Props** — Enter prop lines manually or upload a CSV.
    Sample props are pre-loaded so you can start immediately.

    **Step 2** → 🏆 **Analysis** — Click "Run Analysis" to run Monte Carlo
    simulation. See probability gauges, tier badges, and force breakdowns.

    **Step 3** → 🎰 **Entry Builder** — Build optimal parlays with exact EV
    calculations for PrizePicks, Underdog, and DraftKings.

    **Step 4** → 📊 **Model Health** — After games, log results to track
    how accurate the model is over time.
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

# ============================================================
# END SECTION: Quick Start Guide
# ============================================================

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

    #### 5. 💰 EV Calculation
    For parlays, we calculate **Expected Value** = exactly how much
    you'd win (or lose) on average per dollar wagered.

    ---

    #### 🎯 Smart Data Fetching (New!)
    The "Update Data" page now has a **Smart Update** option that only fetches
    players on today's teams using `CommonTeamRoster` — which reflects all
    trades and signings. This is 10x faster than the full update!
    """)

st.divider()
st.caption(
    f"SmartAI-NBA v7 | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | "
    f"{len(players_data)} players, {len(teams_data)} teams"
)
