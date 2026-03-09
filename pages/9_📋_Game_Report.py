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

# Load team stats for game predictions (pace, ortg, drtg)
try:
    from data.data_manager import load_teams_data as _load_teams
    _teams_list = _load_teams()
    TEAMS_DATA = {t.get("abbreviation", "").upper(): t for t in _teams_list if t.get("abbreviation")}
except Exception:
    TEAMS_DATA = {}

_LEAGUE_AVG_DRTG = 113.0  # typical NBA league-average defensive rating

# Load sample player data for key-player matchup display
try:
    from data.data_manager import load_players_data as _load_players
    _players_raw = _load_players()
    # Build {team_abbrev_upper: [player_dict, ...]} for fast lookup
    PLAYERS_BY_TEAM: dict = {}
    for _p in _players_raw:
        _t = _p.get("team", "").upper().strip()
        if _t:
            PLAYERS_BY_TEAM.setdefault(_t, []).append(_p)
except Exception:
    PLAYERS_BY_TEAM = {}

# ── Build expanded team alias set for stale-result filtering ──────
# Covers common NBA abbreviation variants (e.g. "GS" ↔ "GSW", "NY" ↔ "NYK").
_ABBREV_ALIASES = {
    "GS": "GSW", "GSW": "GS",
    "NY": "NYK", "NYK": "NY",
    "NO": "NOP", "NOP": "NO",
    "SA": "SAS", "SAS": "SA",
    "UTAH": "UTA", "UTA": "UTAH",
    "WSH": "WAS", "WAS": "WSH",
    "BKN": "BRK", "BRK": "BKN",
    "PHX": "PHO", "PHO": "PHX",
    "CHA": "CHO", "CHO": "CHA",
}

def _expand_teams(abbrevs: set) -> set:
    """Return abbrevs expanded with all known alias variants."""
    expanded = set(abbrevs)
    for a in list(abbrevs):
        alias = _ABBREV_ALIASES.get(a)
        if alias:
            expanded.add(alias)
    return expanded

# ── Filter out stale results not matching tonight's teams ──────
# If the user ran analysis yesterday and didn't clear session state,
# results for teams not playing tonight are silently removed here
# rather than polluting the report with stale data.
# Uses case-insensitive, stripped fuzzy team matching + alias expansion.
if todays_games and analysis_results:
    playing_teams = set()
    for _game in todays_games:
        ht = _game.get("home_team", "").upper().strip()
        at = _game.get("away_team", "").upper().strip()
        if ht:
            playing_teams.add(ht)
        if at:
            playing_teams.add(at)
    playing_teams.discard("")
    playing_teams = _expand_teams(playing_teams)

    if playing_teams:
        _valid = [
            r for r in analysis_results
            if (
                r.get("player_team", r.get("team", "")).upper().strip() in playing_teams
                or not r.get("player_team", r.get("team", "")).strip()
            )
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

selected_game = None

if todays_games:
    col_sel, col_meta = st.columns([2, 1])

    with col_sel:
        game_labels = [
            f"{g.get('away_team','?')} @ {g.get('home_team','?')}"
            for g in todays_games
        ]
        options = ["— All games tonight —"] + game_labels
        sel_idx = st.selectbox(
            "🏟️ Select Matchup",
            range(len(options)),
            format_func=lambda i: options[i],
            index=0,
            help="Filter to a specific game, or show all games tonight.",
        )
        if sel_idx > 0:
            selected_game = todays_games[sel_idx - 1]

    with col_meta:
        n_props   = len(analysis_results)
        n_picks   = len([r for r in analysis_results if r.get("confidence_score", 0) >= 70])
        st.metric("Analysed Props",  n_props)
        st.metric("High-Conf Picks", n_picks, help="Picks with confidence ≥ 70")

    if not analysis_results:
        st.info(
            "💡 Games loaded. Run **⚡ Neural Analysis** to add prop predictions to each report — "
            "team stats and game predictions are shown below for all matchups."
        )

elif not todays_games and analysis_results:
    if st.button("📋 Generate Full Report for All Props", use_container_width=True):
        st.session_state["game_report_show_all"] = True

elif not todays_games and not analysis_results:
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
    home = selected_game.get("home_team", "").upper().strip()
    away = selected_game.get("away_team", "").upper().strip()
    game_teams = _expand_teams({home, away} - {""})
    filtered = [
        r for r in analysis_results
        if r.get("player_team", r.get("team", "")).upper().strip() in game_teams
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


def _predict_game(home_abbrev, away_abbrev):
    """
    Return a simple game score prediction using team ortg/drtg/pace from teams.csv.

    Returns:
        dict with keys: home_score, away_score, predicted_total,
                        predicted_winner, predicted_margin
        or None if team data is unavailable.
    """
    home_t = TEAMS_DATA.get(home_abbrev.upper(), {})
    away_t = TEAMS_DATA.get(away_abbrev.upper(), {})
    if not home_t or not away_t:
        return None

    try:
        home_ortg  = float(home_t.get("ortg",  113.0) or 113.0)
        home_drtg  = float(home_t.get("drtg",  113.0) or 113.0)
        home_pace  = float(home_t.get("pace",  100.0) or 100.0)
        away_ortg  = float(away_t.get("ortg",  113.0) or 113.0)
        away_drtg  = float(away_t.get("drtg",  113.0) or 113.0)
        away_pace  = float(away_t.get("pace",  100.0) or 100.0)

        avg_pace = (home_pace + away_pace) / 2.0

        # Score ≈ ortg * (avg_pace/100) adjusted for opponent's defense
        home_score = round(home_ortg * (avg_pace / 100.0) * (_LEAGUE_AVG_DRTG / away_drtg), 1)
        away_score = round(away_ortg * (avg_pace / 100.0) * (_LEAGUE_AVG_DRTG / home_drtg), 1)
        predicted_total  = round(home_score + away_score, 1)
        predicted_margin = round(abs(home_score - away_score), 1)
        predicted_winner = home_abbrev if home_score > away_score else away_abbrev

        return {
            "home_score":       home_score,
            "away_score":       away_score,
            "predicted_total":  predicted_total,
            "predicted_winner": predicted_winner,
            "predicted_margin": predicted_margin,
            "home_ortg":  home_ortg, "home_drtg":  home_drtg, "home_pace":  home_pace,
            "away_ortg":  away_ortg, "away_drtg":  away_drtg, "away_pace":  away_pace,
        }
    except Exception:
        return None


def _render_game_team_stats(game, game_pred):
    """Render a compact team-stats comparison + game prediction row."""
    home = game.get("home_team", "?").upper()
    away = game.get("away_team", "?").upper()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**{away}** (away)")
    c2.markdown(f"**{home}** (home)")

    if game_pred:
        c3.markdown(
            f"**Predicted:** {away} {game_pred['away_score']:.0f} — "
            f"{home} {game_pred['home_score']:.0f}"
        )
        c4.markdown(
            f"**Total:** {game_pred['predicted_total']:.0f} · "
            f"**Winner:** {game_pred['predicted_winner']} by {game_pred['predicted_margin']:.0f}"
        )

    # Team stats mini-table
    ht = TEAMS_DATA.get(home, {})
    at = TEAMS_DATA.get(away, {})
    if ht or at:
        st.markdown(
            f"| Stat | {away} | {home} |\n"
            f"|------|-------|--------|\n"
            f"| Pace | {at.get('pace','—')} | {ht.get('pace','—')} |\n"
            f"| ORtg | {at.get('ortg','—')} | {ht.get('ortg','—')} |\n"
            f"| DRtg | {at.get('drtg','—')} | {ht.get('drtg','—')} |"
        )


def _render_key_players(team_abbrev, label):
    """
    Show the top 3 scorers and top rebounder from sample_players.csv for a team.
    Falls back gracefully if no data is available.
    """
    players = PLAYERS_BY_TEAM.get(team_abbrev.upper(), [])
    if not players:
        st.caption(f"No player data available for {team_abbrev}.")
        return

    # Sort by points avg, take top 4
    top_by_pts = sorted(players, key=lambda p: float(p.get("points_avg", 0) or 0), reverse=True)[:4]
    # Top rebounder (may already be in top_by_pts)
    top_reb = max(players, key=lambda p: float(p.get("rebounds_avg", 0) or 0), default=None)

    # Combine without duplicates
    shown = {p.get("name", p.get("player_name", "")) for p in top_by_pts}
    key_players = list(top_by_pts)
    if top_reb:
        top_reb_name = top_reb.get("name", top_reb.get("player_name", ""))
        if top_reb_name and top_reb_name not in shown:
            key_players.append(top_reb)

    st.markdown(f"**{label} Key Players** (season averages)")
    rows = []
    for p in key_players:
        name = p.get("name", p.get("player_name", "Unknown"))
        rows.append({
            "Player": name,
            "Pos":    p.get("position", "—"),
            "PTS":    float(p.get("points_avg", 0) or 0),
            "REB":    float(p.get("rebounds_avg", 0) or 0),
            "AST":    float(p.get("assists_avg", 0) or 0),
            "3PM":    float(p.get("threes_avg", 0) or 0),
            "MIN":    float(p.get("minutes_avg", 0) or 0),
        })
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PTS": st.column_config.NumberColumn(format="%.1f"),
            "REB": st.column_config.NumberColumn(format="%.1f"),
            "AST": st.column_config.NumberColumn(format="%.1f"),
            "3PM": st.column_config.NumberColumn(format="%.1f"),
            "MIN": st.column_config.NumberColumn(format="%.1f"),
        },
    )


# ── Determine which games to display ────────────────────────
_games_to_show = [selected_game] if selected_game else todays_games

if _games_to_show:
    for game in _games_to_show:
        home = game.get("home_team", "").upper().strip()
        away = game.get("away_team", "").upper().strip()
        game_teams_expanded = _expand_teams({home, away} - {""})
        game_results = [
            r for r in report_results
            if r.get("player_team", r.get("team", "")).upper().strip() in game_teams_expanded
        ]
        n_game_props = len(game_results)
        n_conf = len([r for r in game_results if r.get("confidence_score", 0) >= 70])

        # Always show every game — even when no props have been analyzed
        expander_label = (
            f"🏀 {away} @ {home}"
            + (f" — {n_game_props} props · {n_conf} high-conf" if n_game_props else " — no props analyzed")
        )

        with st.expander(expander_label, expanded=True):
            game_pred = _predict_game(home, away)

            # ── Always show team stats + game prediction ───────────
            st.markdown("#### 📊 Team Stats & Game Prediction")
            _render_game_team_stats(game, game_pred)

            if game_pred:
                st.caption(
                    f"🔮 Predicted: **{away} {game_pred['away_score']:.0f}** vs "
                    f"**{home} {game_pred['home_score']:.0f}** · "
                    f"Total: **{game_pred['predicted_total']:.0f}** · "
                    f"Predicted winner: **{game_pred['predicted_winner']}** "
                    f"by **{game_pred['predicted_margin']:.0f}**"
                )

            st.divider()

            if game_results:
                # ── Suggested Parlays for this game ───────────────
                game_strategy = _build_entry_strategy(game_results)
                if game_strategy:
                    st.markdown("#### 🎯 Suggested Parlays")
                    for _e in game_strategy[:3]:
                        _picks_str = " + ".join(_e.get("picks", []))
                        st.markdown(
                            f'<div style="background:#14192b;border-radius:6px;padding:10px 14px;'
                            f'margin-bottom:8px;border-left:3px solid #ff5e00;">'
                            f'<span style="color:#ff5e00;font-weight:600;">'
                            f'{_e.get("combo_type","")}</span>'
                            f'<span style="color:#8b949e;font-size:0.8rem;margin:0 8px;">SAFE {_e.get("safe_avg","")}/100</span>'
                            f'<div style="color:#c0d0e8;font-size:0.85rem;margin-top:4px;">{_picks_str}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.divider()

                # ── Full QDS prop card report ──────────────────────
                html_content = get_game_report_html(
                    game=game,
                    analysis_results=game_results,
                )
                card_height = min(6000, 2200 + max(0, n_game_props - 1) * 800)
                components.html(html_content, height=card_height, scrolling=True)
            else:
                # ── Key player matchups from sample_players.csv ────────
                kp_col1, kp_col2 = st.columns(2)
                with kp_col1:
                    _render_key_players(away, away)
                with kp_col2:
                    _render_key_players(home, home)
                st.info(
                    "📭 No props analyzed for this game yet — "
                    "run **⚡ Neural Analysis** with props for these teams "
                    "to see full prop predictions and parlay suggestions."
                )

    # ── Overall Entry Strategy Matrix (cross-game) ────────────────────
    if report_results and not selected_game and len(todays_games) > 1:
        all_strategy = _build_entry_strategy(report_results)
        if all_strategy:
            st.divider()
            st.subheader("📊 Cross-Game Entry Strategy Matrix")
            st.markdown(
                "Best multi-leg combinations across ALL tonight's matchups, "
                "ranked by SAFE Score™.",
            )
            st.markdown(get_qds_strategy_table_html(all_strategy), unsafe_allow_html=True)

elif analysis_results and not todays_games:
    # No games loaded — but analysis results exist from a previous session
    html_content = get_game_report_html(
        game=None,
        analysis_results=report_results,
    )
    components.html(html_content, height=6200, scrolling=True)
else:
    st.info(
        "💡 Load tonight's games on the **📡 Live Games** page to see a full report for every matchup."
    )

# ============================================================
# END SECTION: Render QDS Game Report
# ============================================================
