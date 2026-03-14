# ============================================================
# FILE: app.py
# PURPOSE: Main entry point for the SmartBetPro NBA Streamlit app.
#          Professional dark-themed dashboard with today's slate,
#          status cards, and quick-start guide.
# HOW TO RUN: streamlit run app.py
# ============================================================

import streamlit as st
import datetime
import os
import base64

from data.data_manager import load_players_data, load_props_data, load_teams_data
from data.live_data_fetcher import load_last_updated
from tracking.database import initialize_database
from styles.theme import get_global_css

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="Smart Pick Pro — NBA Edition",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── App Logo — Smart Pick Pro ───────────────────────────────
# Use the root-level original logo (1.7MB, high-resolution user asset).
# Falls back to the assets/ copy if the root-level file is missing.
_ROOT_LOGO_PATH   = os.path.join(os.path.dirname(__file__), "Smart_Pick_Pro_Logo.png")
_ASSETS_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "Smart_Pick_Pro_Logo.png")
_LOGO_PATH = _ROOT_LOGO_PATH if os.path.exists(_ROOT_LOGO_PATH) else _ASSETS_LOGO_PATH
if os.path.exists(_LOGO_PATH):
    st.logo(_LOGO_PATH, size="large")


@st.cache_data(show_spinner=False)
def _load_logo_b64(path: str) -> str:
    """Read the logo PNG and return a base64-encoded string (cached per session)."""
    try:
        with open(path, "rb") as _f:
            return base64.b64encode(_f.read()).decode()
    except Exception:
        return ""

# ─── Quantum Edge Theme CSS — page-level overrides ───────────
st.markdown("""
<style>
/* Hero banner gradient — vibrant high-tech Quantum Edge teal/blue */
.hero-banner {
    background: linear-gradient(135deg, #00b4ff 0%, #00ffd5 50%, #00e0b8 100%);
    border: 1px solid rgba(0,240,255,0.25);
    border-radius: 14px;
    padding: 28px 36px;
    margin-bottom: 24px;
    box-shadow: 0 0 30px rgba(0,240,255,0.10), 0 6px 28px rgba(0,0,0,0.5);
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00f0ff, #00ff9d, #ff5e00, #c800ff, #00f0ff);
    background-size: 200% 100%;
    animation: headerShimmer 4s ease infinite;
}
.spp-hero-logo {
    max-height: 90px;
    max-width: 100%;
    object-fit: contain;
}
.hero-date {
    font-size: 0.95rem;
    color: rgba(10,15,26,0.70);
    margin-top: 4px;
    font-family: 'Courier New', Courier, monospace;
}
/* Status card — dark glass panel */
.status-card {
    background: rgba(20,25,43,0.85);
    border: 1px solid rgba(0,240,255,0.15);
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
    box-shadow: 0 0 16px rgba(0,240,255,0.07), 0 4px 16px rgba(0,0,0,0.4);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.status-card:hover {
    border-color: rgba(0,240,255,0.35);
    transform: translateY(-3px);
}
.status-card-value {
    font-size: 2rem;
    font-weight: 800;
    color: rgba(255,255,255,0.95);
    font-family: 'Courier New', Courier, monospace;
}
.status-card-label {
    font-size: 0.8rem;
    color: #8a9bb8;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
}
/* Tonight's slate team chips */
.team-chip {
    display: inline-block;
    background: rgba(0,240,255,0.07);
    color: rgba(255,255,255,0.90);
    border: 1px solid rgba(0,240,255,0.25);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    margin: 3px;
}
/* Tier badge pill */
.live-badge {
    display: inline-block;
    background: rgba(0,255,157,0.10);
    color: #00ff9d;
    border: 1px solid rgba(0,255,157,0.35);
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    text-shadow: 0 0 6px rgba(0,255,157,0.4);
}
.sample-badge {
    display: inline-block;
    background: rgba(255,94,0,0.10);
    color: #ff9d4d;
    border: 1px solid rgba(255,94,0,0.35);
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

# ── Premium Status — Check and display in sidebar ─────────────
# This runs silently on app load.  is_premium_user() is cached in
# session state so it won't make Stripe API calls on every rerun.
try:
    from utils.auth import is_premium_user as _is_premium, handle_checkout_redirect as _handle_checkout
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
    # Handle checkout redirects even on the home page
    _handle_checkout()
    _user_is_premium = _is_premium()
except Exception:
    _user_is_premium = True  # Fail open — don't block the home page
    _PREM_PATH = "/6_%F0%9F%92%8E_Premium"

with st.sidebar:
    if _user_is_premium:
        st.markdown(
            '<div style="background:rgba(0,255,157,0.10);border:1px solid rgba(0,255,157,0.3);'
            'border-radius:10px;padding:10px 14px;text-align:center;margin-bottom:8px;">'
            '<span style="color:#00ff9d;font-weight:700;font-size:0.9rem;">💎 Premium Active</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:rgba(255,94,0,0.08);border:1px solid rgba(255,94,0,0.25);'
            f'border-radius:10px;padding:10px 14px;text-align:center;margin-bottom:8px;">'
            f'<span style="color:#a0b4d0;font-size:0.85rem;">⭐ Free Plan</span><br>'
            f'<a href="{_PREM_PATH}" style="color:#ff5e00;font-size:0.78rem;'
            f'font-weight:600;text-decoration:none;">Upgrade to Premium →</a>'
            f'</div>',
            unsafe_allow_html=True,
        )

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
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "session_props" not in st.session_state:
    st.session_state["session_props"] = []
if "fetched_live_picks" not in st.session_state:
    st.session_state["fetched_live_picks"] = []

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

# Embed logo using cached base64 load — root-level high-res version
_logo_b64 = _load_logo_b64(_LOGO_PATH) if os.path.exists(_LOGO_PATH) else ""

_logo_img_tag = (
    f'<img src="data:image/png;base64,{_logo_b64}" class="spp-hero-logo" alt="Smart Pick Pro logo" />'
    if _logo_b64 else ""
)

st.markdown(f"""
<div class="neural-header spp-hero-header" style="display:flex;align-items:center;justify-content:center;padding:18px 36px;">
  {_logo_img_tag}
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero-banner">
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
        chips_html += f'<span style="color:#c800ff; font-weight:700; font-size:0.9rem;">vs</span> '
        chips_html += f'<span class="team-chip">🏠 {home}{rec_h}</span> &nbsp;&nbsp;&nbsp;'

    st.markdown(f'<div style="margin:8px 0 4px 0;">{chips_html}</div>', unsafe_allow_html=True)
    st.caption("Go to 📡 Live Games to update spreads/totals")
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

# ── Teams Data Staleness Check ─────────────────────────────────
try:
    from data.live_data_fetcher import load_last_updated as _load_lu
    from data.data_manager import load_teams_data as _load_teams
    _last_updated = _load_lu() or {}
    _teams_ts = _last_updated.get("teams_stats")
    if _teams_ts:
        import datetime as _dt
        _teams_date = _dt.datetime.fromisoformat(_teams_ts)
        _teams_age_days = (_dt.datetime.now() - _teams_date).days
        if _teams_age_days >= 7:
            st.warning(
                f"⚠️ Team stats are **{_teams_age_days} days old**. "
                f"Go to **📡 Data Feed → Smart Update** to refresh."
            )
        elif _teams_age_days >= 3:
            st.info(
                f"ℹ️ Team stats last updated {_teams_age_days} days ago. "
                f"Consider refreshing on the Data Feed page."
            )
    else:
        _teams_data = _load_teams()
        if not _teams_data:
            st.warning(
                "⚠️ No team stats found. Go to **📡 Data Feed → Smart Update** "
                "to load team data for accurate analysis."
            )
except Exception:
    pass

# ── Data Validation on Startup ─────────────────────────────────
try:
    from data.validators import validate_players_csv, validate_teams_csv
    from data.data_manager import load_players_data as _lp_val, load_teams_data as _lt_val
    _val_players = _lp_val()
    _val_teams = _lt_val()
    _p_errors = validate_players_csv(_val_players)
    _t_errors = validate_teams_csv(_val_teams)
    if _p_errors or _t_errors:
        with st.expander("⚠️ Data Validation Issues (click to expand)", expanded=False):
            for e in _p_errors:
                st.warning(f"players.csv: {e}")
            for e in _t_errors:
                st.warning(f"teams.csv: {e}")
except Exception:
    pass

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
        "📊 **No live data loaded yet** — Go to the **📡 Data Feed** page to pull "
        "real, up-to-date NBA stats for accurate predictions!"
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

    **Step 0** → 📡 **Live Games** — Click
    "**Auto-Load Tonight's Games**" for a ONE-CLICK setup:
    fetches tonight's matchups + current rosters + player stats + team stats.
    Everything you need in a single button press!

    **Step 1** → 🔬 **Prop Scanner** — Enter prop lines manually or upload a CSV.
    Sample props are pre-loaded so you can start immediately.

    **Step 2** → ⚡ **Neural Analysis** — Click "Run Analysis" to run Monte Carlo
    simulation. See probability gauges, tier badges, and force breakdowns.

    **Step 3** → 🧬 **Entry Builder** — Build optimal parlays with exact EV
    calculations for PrizePicks, Underdog, and DraftKings.

    **Step 4** → 📈 **Bet Tracker & Model Health** — After games, log results to track
    how accurate the model is over time.

    ---
    💎 **Premium features** (Entry Builder, Risk Shield, Game Report, Player Simulator,
    Bet Tracker, and unlimited analysis) require a subscription.
    Visit the **💎 Premium** page in the sidebar to unlock everything!
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

# ============================================================
# SECTION: Legal Disclaimer
# ============================================================

with st.expander("⚠️ Important Legal Disclaimer — Please Read", expanded=False):
    st.markdown("""
    ## ⚠️ IMPORTANT DISCLAIMER
    
    **SmartBetPro NBA ("Smart Pick Pro")** is an analytical tool for **entertainment and educational purposes only**. This application does NOT guarantee profits or winning outcomes.
    
    - 📊 Past performance does not guarantee future results
    - 🔢 All predictions are based on statistical models that have inherent limitations  
    - 💰 Sports betting involves significant financial risk — **never bet more than you can afford to lose**
    - 🔞 You must be **21+** (or legal age in your jurisdiction) to participate in sports betting
    - ⚠️ This tool is **not affiliated** with the NBA, PrizePicks, Underdog Fantasy, or DraftKings
    - 🆘 Always gamble responsibly. If you or someone you know has a gambling problem, call **1-800-GAMBLER (1-800-426-2537)**
    
    **By using this application, you acknowledge that all betting decisions are your own responsibility.**
    
    ---
    
    **Responsible Gaming Resources:**
    - 📞 **National Problem Gambling Helpline: 1-800-GAMBLER (1-800-426-2537)** — 24/7 confidential support
    - 📞 National Council on Problem Gambling: **1-800-522-4700** — crisis counseling & referrals
    - 🌐 [www.ncpgambling.org](https://www.ncpgambling.org)
    - 🌐 [www.begambleaware.org](https://www.begambleaware.org)
    """)

# ============================================================
# END SECTION: Legal Disclaimer
# ============================================================

st.divider()

# ============================================================
# SECTION: How It Works
# ============================================================

with st.expander("📖 How Does Smart Pick Pro Work?", expanded=False):
    st.markdown("""
    ### The Engine Under the Hood

    Smart Pick Pro — NBA Edition uses **Monte Carlo simulation** to predict player stat outcomes.
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

# ── System Health Dashboard ───────────────────────────────────────────────────
try:
    from data.data_manager import get_data_health_report
    _health = get_data_health_report()

    with st.expander("🩺 System Health", expanded=False):
        hc1, hc2, hc3, hc4 = st.columns(4)
        hc1.metric("👥 Players", _health["players_count"])
        hc2.metric("🏀 Teams", _health["teams_count"])
        hc3.metric("📋 Props", _health["props_count"])
        _freshness_label = f"{_health['days_old']}d old" if _health.get("last_updated") else "Never"
        hc4.metric("🕐 Data Age", _freshness_label,
                   delta="⚠️ Stale" if _health["is_stale"] else "✅ Fresh",
                   delta_color="inverse" if _health["is_stale"] else "normal")

        if _health["warnings"]:
            for w in _health["warnings"]:
                st.warning(w)
        else:
            st.success("✅ All data files present and fresh.")

        st.caption("Go to **📡 Data Feed** to refresh data.")
except Exception:
    pass

st.caption(
    f"© Smart Pick Pro | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | "
    f"{len(players_data)} players, {len(teams_data)} teams | "
    "For entertainment & educational purposes only. Not financial advice. Bet responsibly. 21+"
)
