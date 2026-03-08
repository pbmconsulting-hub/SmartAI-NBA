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
import datetime

from styles.theme import (
    get_global_css,
    get_game_report_html,
    get_qds_css,
    get_qds_strategy_table_html,
)

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="Game Report — SmartBetPro NBA",
    page_icon="📋",
    layout="wide",
)

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Configuration
# ============================================================


# ============================================================
# SECTION: Data Loading
# ============================================================

todays_games     = st.session_state.get("todays_games",     [])
analysis_results = st.session_state.get("analysis_results", [])

# ── Filter out stale results not matching tonight's teams ──────
# If the user ran analysis yesterday and didn't clear session state,
# results for teams not playing tonight are silently removed here
# rather than polluting the report with stale data.
if todays_games and analysis_results:
    playing_teams = set()
    for _game in todays_games:
        playing_teams.add(_game.get("home_team", "").upper())
        playing_teams.add(_game.get("away_team", "").upper())
    playing_teams.discard("")

    if playing_teams:
        _valid = [
            r for r in analysis_results
            if (r.get("player_team") or r.get("team") or "").upper().strip()
            in playing_teams
        ]
        _stale_count = len(analysis_results) - len(_valid)
        if _stale_count > 0:
            st.warning(
                f"⚠️ Filtered out {_stale_count} stale result(s) from a previous "
                "session (players not on tonight's teams)."
            )
        analysis_results = _valid

# ── Freshness check — warn if results are older than 6 hours ──
_analysis_ts = st.session_state.get("analysis_timestamp")
if _analysis_ts and analysis_results:
    _age_hours = (datetime.datetime.now() - _analysis_ts).total_seconds() / 3600
    if _age_hours > 6:
        st.warning(
            f"⚠️ Analysis results are {_age_hours:.0f} hour(s) old. "
            "Re-run **⚡ Neural Analysis** for fresh data."
        )

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

def _results_for_game(game, results):
    """Return analysis results matching the players in a specific game."""
    home = game.get("home_team", "").upper().strip()
    away = game.get("away_team", "").upper().strip()
    return [
        r for r in results
        if (r.get("player_team") or r.get("team", "")).upper().strip() in {home, away}
    ]


selected_game = None

if todays_games:
    col_sel, col_meta = st.columns([2, 1])

    with col_sel:
        game_labels = [
            f"{g.get('away_team','?').upper().strip()} @ {g.get('home_team','?').upper().strip()}"
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
    filtered = _results_for_game(selected_game, analysis_results)
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

def _build_entry_strategy(results):
    """Build entry strategy matrix entries from analysis results."""
    top = [
        r for r in results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and abs(r.get("edge_percentage", 0)) >= 5.0
    ]
    top = sorted(top, key=lambda r: r.get("confidence_score", 0), reverse=True)

    entries = []
    if len(top) >= 2:
        p1, p2 = top[0], top[1]
        avg2 = round((p1.get("confidence_score", 0) + p2.get("confidence_score", 0)) / 2, 1)
        entries.append({
            "combo_type": "Power Play (2)",
            "picks": [
                f"{p1['player_name']} {p1['direction']} {p1['line']} {p1['stat_type'].title()}",
                f"{p2['player_name']} {p2['direction']} {p2['line']} {p2['stat_type'].title()}",
            ],
            "safe_avg": f"{avg2:.1f}",
            "strategy": "Highest-confidence 2-leg.",
        })
    if len(top) >= 3:
        trio = top[:3]
        avg3 = round(sum(r.get("confidence_score", 0) for r in trio) / 3, 1)
        entries.append({
            "combo_type": "Triple Threat (3)",
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in trio
            ],
            "safe_avg": f"{avg3:.1f}",
            "strategy": "Top-3 picks, balanced risk.",
        })
    if len(top) >= 5:
        five = top[:5]
        avg5 = round(sum(r.get("confidence_score", 0) for r in five) / 5, 1)
        entries.append({
            "combo_type": "Max Parlay (5)",
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in five
            ],
            "safe_avg": f"{avg5:.1f}",
            "strategy": "High ceiling, diversified 5-leg.",
        })
    return entries


if not selected_game and len(todays_games) > 1 and report_results:
    # ── Multiple matchups: per-game collapsible Streamlit expanders ──

    # ── Generate Report for All Games button ─────────────────────────
    if st.button("📊 Generate Report for All Games", type="primary"):
        st.session_state["_game_report_show_all"] = True

    for game in todays_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        game_results = _results_for_game(game, report_results)
        n_game_props = len(game_results)
        n_conf = len([r for r in game_results if r.get("confidence_score", 0) >= 70])
        expander_label = (
            f"🏀 {away} @ {home} — "
            f"{n_game_props} props · {n_conf} high-confidence"
        )

        with st.expander(expander_label, expanded=True):
            if game_results:
                html_content = get_game_report_html(
                    game=game,
                    analysis_results=game_results,
                )
                # Adjust height: ~2000px per prop card + base sections
                card_height = min(6000, 2200 + max(0, n_game_props - 1) * 800)
                components.html(html_content, height=card_height, scrolling=True)
            else:
                st.info(
                    "No analysis results for this matchup yet. "
                    "Run **⚡ Neural Analysis** first."
                )

    # ── Overall Entry Strategy Matrix ─────────────────────────────────
    strategy_entries = _build_entry_strategy(report_results)
    if strategy_entries:
        st.divider()
        st.subheader("📊 Overall Entry Strategy Matrix")
        st.markdown(
            "Optimal multi-leg combinations ranked by SAFE Score™ across all tonight's matchups.",
            help="Based on the highest-confidence, non-avoided props from all games.",
        )
        st.markdown(get_qds_strategy_table_html(strategy_entries), unsafe_allow_html=True)

else:
    # ── Single game or "All" with a selected matchup ──────────────────
    html_content = get_game_report_html(
        game=selected_game,
        analysis_results=report_results,
    )
    # Render in a scrollable iframe — height covers ~3 prop cards + all sections
    components.html(html_content, height=6200, scrolling=True)

# ============================================================
# END SECTION: Render QDS Game Report
# ============================================================
