# ============================================================
# FILE: pages/9_📋_Game_Report.py
# PURPOSE: Generate a comprehensive QDS-styled game betting
#          report using SmartBetPro's AI analysis results.
# DESIGN:  Quantum Design System (QDS) — dark futuristic theme
#          with collapsible sections, animated confidence bars,
#          SAFE Score™ prop cards, team analysis, and entry
#          strategy matrix (matching reference QDS HTML spec).
# USAGE:   Load games + run Neural Analysis first, then visit
#          this page to generate a report for any matchup.
# ============================================================

import streamlit as st
import streamlit.components.v1 as components

from styles.theme import get_global_css, get_game_report_html

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="Game Report — SmartBetPro NBA",
    page_icon="📋",
    layout="wide",
)

st.markdown(get_global_css(), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Configuration
# ============================================================


# ============================================================
# SECTION: Data Loading
# ============================================================

todays_games     = st.session_state.get("todays_games",     [])
analysis_results = st.session_state.get("analysis_results", [])

# ============================================================
# END SECTION: Data Loading
# ============================================================


# ============================================================
# SECTION: Page Header
# ============================================================

st.title("📋 Game Report")
st.markdown(
    "AI-powered prop betting report with **SAFE Score™** analysis — "
    "collapsible sections, confidence bars, and entry strategy matrix."
)
st.divider()

# ============================================================
# END SECTION: Page Header
# ============================================================


# ============================================================
# SECTION: Matchup Selector
# ============================================================

selected_game = None

if todays_games:
    col_sel, col_meta = st.columns([2, 1])

    with col_sel:
        game_labels = [
            f"{g.get('away_team','?')} @ {g.get('home_team','?')}"
            for g in todays_games
        ]
        options = ["— All available props —"] + game_labels
        sel_idx = st.selectbox(
            "🏟️ Select Matchup",
            range(len(options)),
            format_func=lambda i: options[i],
            help="Filter the report to a single game, or show all analysed props.",
        )
        if sel_idx > 0:
            selected_game = todays_games[sel_idx - 1]

    with col_meta:
        n_props   = len(analysis_results)
        n_picks   = len([r for r in analysis_results if r.get("confidence_score", 0) >= 70])
        st.metric("Analysed Props",  n_props)
        st.metric("High-Conf Picks", n_picks, help="Picks with confidence ≥ 70")
else:
    st.info(
        "💡 No games loaded yet. "
        "Go to **📡 Live Games** to fetch tonight's NBA slate, "
        "then run **⚡ Neural Analysis** to generate prop predictions."
    )

# ============================================================
# END SECTION: Matchup Selector
# ============================================================


# ============================================================
# SECTION: Filter Results to Selected Game
# ============================================================

if selected_game and analysis_results:
    home = selected_game.get("home_team", "")
    away = selected_game.get("away_team", "")
    filtered = [
        r for r in analysis_results
        if r.get("player_team", "").upper() in (home.upper(), away.upper())
    ]
    report_results = filtered if filtered else analysis_results
elif analysis_results:
    report_results = analysis_results
else:
    report_results = []

# ============================================================
# END SECTION: Filter Results to Selected Game
# ============================================================


# ============================================================
# SECTION: Render QDS Game Report
# ============================================================

html_content = get_game_report_html(
    game=selected_game,
    analysis_results=report_results,
)

# Render in a scrollable iframe — height covers ~3 prop cards + all sections
components.html(html_content, height=6200, scrolling=True)

# ============================================================
# END SECTION: Render QDS Game Report
# ============================================================
