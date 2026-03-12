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
    if st.button("📋 Generate Full Report for All Props", width="stretch"):
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
# SECTION: Tabbed Interface — Game Report | Game Builder | Narrative
# ============================================================

_tab_report, _tab_builder, _tab_narrative = st.tabs([
    "📊 Game Report",
    "🏗️ Game Builder",
    "📖 Game Narrative",
])

# Helper functions are defined at module level below before the tab content


def _build_entry_strategy(results):
    """Build entry strategy matrix entries from analysis results.

    Enforces a unique-player constraint: each parlay leg must be a
    different player.  Fantasy-score composite stat types are excluded
    so legs stay comparable across sportsbooks.
    """
    top = [
        r for r in results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and abs(r.get("edge_percentage", 0)) >= 5.0
        # Exclude fantasy-score composite stats from parlay legs
        and not str(r.get("stat_type", "")).startswith("fantasy_score")
    ]
    top = sorted(top, key=lambda r: r.get("confidence_score", 0), reverse=True)

    def _pick_unique_players(candidates, num_legs):
        """Return up to num_legs picks with no repeated players."""
        seen: set = set()
        selected = []
        for r in candidates:
            pname = r.get("player_name", "")
            if pname and pname in seen:
                continue
            seen.add(pname)
            selected.append(r)
            if len(selected) == num_legs:
                break
        return selected

    entries = []
    picks2 = _pick_unique_players(top, 2)
    if len(picks2) >= 2:
        avg2 = round(sum(r.get("confidence_score", 0) for r in picks2) / 2, 1)
        entries.append({
            "combo_type": "Power Play (2)",
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in picks2
            ],
            "safe_avg": f"{avg2:.1f}",
            "strategy": "Highest-confidence 2-leg.",
        })
    picks3 = _pick_unique_players(top, 3)
    if len(picks3) >= 3:
        avg3 = round(sum(r.get("confidence_score", 0) for r in picks3) / 3, 1)
        entries.append({
            "combo_type": "Triple Threat (3)",
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in picks3
            ],
            "safe_avg": f"{avg3:.1f}",
            "strategy": "Top-3 picks, balanced risk.",
        })
    picks5 = _pick_unique_players(top, 5)
    if len(picks5) >= 5:
        avg5 = round(sum(r.get("confidence_score", 0) for r in picks5) / 5, 1)
        entries.append({
            "combo_type": "Max Parlay (5)",
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in picks5
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
        # Apply a ~1.2% home-court advantage (NBA home teams win ~58% of games)
        _HOME_ADV = 1.012
        home_score = round(home_ortg * (avg_pace / 100.0) * (_LEAGUE_AVG_DRTG / away_drtg) * _HOME_ADV, 1)
        away_score = round(away_ortg * (avg_pace / 100.0) * (_LEAGUE_AVG_DRTG / home_drtg) / _HOME_ADV, 1)
        # NBA games cannot end in a tie — add 1 pt to home team if scores are equal
        if home_score == away_score:
            home_score += 1.0
        predicted_total  = round(home_score + away_score, 1)
        predicted_margin = round(abs(home_score - away_score), 1)
        predicted_winner = home_abbrev if home_score >= away_score else away_abbrev

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

    # ── Head-to-Head Visualization ───────────────────────────────────
    ht = TEAMS_DATA.get(home, {})
    at = TEAMS_DATA.get(away, {})
    if ht or at:
        # Numeric stats to visualize
        _h2h_stats = [
            ("Pace",  float(at.get("pace", 100) or 100), float(ht.get("pace", 100) or 100), 85, 115),
            ("ORtg",  float(at.get("ortg", 113) or 113), float(ht.get("ortg", 113) or 113), 105, 125),
            ("DRtg",  float(at.get("drtg", 113) or 113), float(ht.get("drtg", 113) or 113), 105, 125),
        ]
        _h2h_rows = ""
        for _h2h_item in _h2h_stats:
            _label, _av, _hv, _lo, _hi = _h2h_item
            _rng = max(_hi - _lo, 1)
            _a_pct = round(max(0, min(100, (_av - _lo) / _rng * 100)))
            _h_pct = round(max(0, min(100, (_hv - _lo) / _rng * 100)))
            # For DRtg, lower is better (flip colors)
            _flip = _label == "DRtg"
            _a_better = (_av < _hv) if _flip else (_av > _hv)
            _a_c = "#00ff9d" if _a_better else "#8b949e"
            _h_c = "#00ff9d" if not _a_better else "#8b949e"
            import html as _h2h_html
            _h2h_rows += (
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                f'<div style="width:40px;text-align:right;font-size:0.75rem;color:#8a9bb8;">{_h2h_html.escape(away)}</div>'
                f'<div style="flex:1;display:flex;align-items:center;gap:4px;">'
                f'<div style="flex:1;height:10px;background:#1a2035;border-radius:3px;position:relative;">'
                f'<div style="position:absolute;right:0;width:{_a_pct}%;height:10px;background:{_a_c};border-radius:3px;"></div>'
                f'</div>'
                f'<div style="width:40px;text-align:center;font-size:0.78rem;font-weight:700;color:#c0d0e8;">{_label}</div>'
                f'<div style="flex:1;height:10px;background:#1a2035;border-radius:3px;">'
                f'<div style="width:{_h_pct}%;height:10px;background:{_h_c};border-radius:3px;"></div>'
                f'</div>'
                f'</div>'
                f'<div style="width:40px;font-size:0.75rem;color:#8a9bb8;">{_h2h_html.escape(home)}</div>'
                f'</div>'
                f'<div style="display:flex;gap:8px;margin-bottom:4px;font-size:0.72rem;color:#8b949e;">'
                f'<div style="width:40px;text-align:right;color:{_a_c};">{_av:.1f}</div>'
                f'<div style="flex:1;text-align:center;"></div>'
                f'<div style="text-align:left;color:{_h_c};">{_hv:.1f}</div>'
                f'</div>'
            )

        st.markdown(
            f'<div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:14px 18px;margin-top:8px;">'
            f'<div style="font-size:0.78rem;color:#8a9bb8;font-weight:600;margin-bottom:10px;'
            f'letter-spacing:0.5px;">⚡ HEAD-TO-HEAD</div>'
            f'{_h2h_rows}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"| Stat | {away} | {home} |\n"
            f"|------|-------|--------|\n"
            f"| Pace | {at.get('pace','—')} | {ht.get('pace','—')} |\n"
            f"| ORtg | {at.get('ortg','—')} | {ht.get('ortg','—')} |\n"
            f"| DRtg | {at.get('drtg','—')} | {ht.get('drtg','—')} |"
        )


def _render_key_players(team_abbrev, label):
    """
    Show the top 3 scorers and top rebounder from players.csv for a team.
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


# ── Determine which games to display (deduplicated) ──────────
with _tab_report:
    if selected_game:
        _games_to_show = [selected_game]
    else:
        # Deduplicate: keep only the first occurrence of each home+away pair
        _seen_matchups: set = set()
        _games_to_show = []
        for _g in todays_games:
            _key = (
                _g.get("home_team", "").upper().strip(),
                _g.get("away_team", "").upper().strip(),
            )
            if _key not in _seen_matchups and (_key[0] or _key[1]):
                _seen_matchups.add(_key)
                _games_to_show.append(_g)

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
                    # ── Key player matchups from players.csv ────────
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


# ============================================================
# SECTION: Game Builder Tab
# ============================================================

with _tab_builder:
    st.subheader("🏗️ Game Builder & Custom Analyzer")
    st.caption("Build a custom game simulation with specific rosters and minutes")

    from data.data_manager import load_teams_data as _load_teams_gb, load_players_data as _load_players_gb
    _teams_data_gb = _load_teams_gb()
    _team_names_gb = sorted([t.get("abbreviation", t.get("name", "")) for t in _teams_data_gb]) if _teams_data_gb else []

    col_home_gb, col_away_gb = st.columns(2)
    with col_home_gb:
        home_team_gb = st.selectbox("🏠 Home Team", options=_team_names_gb, key="gb_home_team")
    with col_away_gb:
        away_team_gb = st.selectbox(
            "🚌 Away Team",
            options=_team_names_gb,
            key="gb_away_team",
            index=min(1, len(_team_names_gb) - 1) if len(_team_names_gb) > 1 else 0,
        )

    if home_team_gb and away_team_gb and home_team_gb != away_team_gb:
        _all_players_gb = _load_players_gb()

        def _get_team_players_gb(team_abbrev, all_players):
            return [p for p in all_players if p.get("team", "").upper() == team_abbrev.upper()]

        home_players_gb = _get_team_players_gb(home_team_gb, _all_players_gb)
        away_players_gb = _get_team_players_gb(away_team_gb, _all_players_gb)

        st.markdown("---")
        col_hp_gb, col_ap_gb = st.columns(2)

        home_active_gb = {}
        home_minutes_gb = {}
        away_active_gb = {}
        away_minutes_gb = {}

        with col_hp_gb:
            st.markdown(f"**🏠 {home_team_gb} Roster**")
            for p in home_players_gb:
                pname = p.get("name", "Unknown")
                avg_min = float(p.get("minutes_avg", p.get("season_min_avg", 28)) or 28)
                is_active = st.checkbox(f"{pname} ({avg_min:.0f} min/g)", value=True, key=f"gb_h_{pname}")
                if is_active:
                    adj_min = st.slider(f"Minutes — {pname}", 0, 48, int(avg_min), key=f"gb_hm_{pname}")
                    home_active_gb[pname] = p
                    home_minutes_gb[pname] = adj_min

        with col_ap_gb:
            st.markdown(f"**🚌 {away_team_gb} Roster**")
            for p in away_players_gb:
                pname = p.get("name", "Unknown")
                avg_min = float(p.get("minutes_avg", p.get("season_min_avg", 28)) or 28)
                is_active = st.checkbox(f"{pname} ({avg_min:.0f} min/g)", value=True, key=f"gb_a_{pname}")
                if is_active:
                    adj_min = st.slider(f"Minutes — {pname}", 0, 48, int(avg_min), key=f"gb_am_{pname}")
                    away_active_gb[pname] = p
                    away_minutes_gb[pname] = adj_min

        # Game settings
        st.markdown("---")
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            gb_total = st.number_input("Game Total (O/U)", min_value=180.0, max_value=260.0, value=220.0, step=0.5, key="gb_total")
        with gc2:
            gb_spread = st.number_input("Spread (home)", min_value=-30.0, max_value=30.0, value=-3.0, step=0.5, key="gb_spread")
        with gc3:
            gb_sims = st.select_slider("Simulations", options=[500, 1000, 2000, 5000], value=1000, key="gb_sims")

        if st.button("🚀 Run Custom Analysis", type="primary", key="gb_run"):
            from engine.projections import build_player_projection, get_stat_standard_deviation
            from engine.simulation import run_monte_carlo_simulation
            from engine.confidence import calculate_confidence_score
            from data.data_manager import load_defensive_ratings_data as _load_def_gb

            _defensive_ratings_gb = _load_def_gb()
            _teams_for_sim_gb = _load_teams_gb()

            custom_results_gb = []
            all_active_gb = list(home_active_gb.items()) + list(away_active_gb.items())
            all_minutes_gb = {**home_minutes_gb, **away_minutes_gb}

            prog_gb = st.progress(0)
            for idx_gb, (pname_gb, pdata_gb) in enumerate(all_active_gb):
                prog_gb.progress((idx_gb + 1) / max(len(all_active_gb), 1))
                pdata_adj_gb = dict(pdata_gb)
                pdata_adj_gb["minutes_avg"] = all_minutes_gb.get(pname_gb, float(pdata_gb.get("minutes_avg", 28) or 28))
                is_home_gb = pname_gb in home_active_gb
                opponent_gb = away_team_gb if is_home_gb else home_team_gb

                for stat_gb in ["points", "rebounds", "assists", "threes"]:
                    stat_avg_gb = float(pdata_adj_gb.get(f"{stat_gb}_avg", 0) or 0)
                    if stat_avg_gb <= 0:
                        continue
                    orig_min_gb = float(pdata_gb.get("minutes_avg", 28) or 28)
                    if orig_min_gb > 0:
                        stat_avg_gb = stat_avg_gb * (pdata_adj_gb["minutes_avg"] / orig_min_gb)

                    try:
                        proj_gb = build_player_projection(
                            player_data=pdata_adj_gb,
                            opponent_team_abbreviation=opponent_gb,
                            is_home_game=is_home_gb,
                            rest_days=2,
                            game_total=gb_total,
                            defensive_ratings_data=_defensive_ratings_gb,
                            teams_data=_teams_for_sim_gb,
                            vegas_spread=gb_spread if is_home_gb else -gb_spread,
                        )
                        projected_value_gb = float(proj_gb.get(f"projected_{stat_gb}", stat_avg_gb) or stat_avg_gb)
                    except Exception:
                        projected_value_gb = stat_avg_gb

                    if projected_value_gb <= 0:
                        continue

                    std_dev_gb = get_stat_standard_deviation(pdata_adj_gb, stat_gb)
                    if not std_dev_gb or std_dev_gb <= 0:
                        std_dev_gb = projected_value_gb * 0.25

                    prop_line_gb = round(projected_value_gb * 2) / 2  # Round to nearest 0.5

                    try:
                        sim_gb = run_monte_carlo_simulation(
                            projected_stat_average=projected_value_gb,
                            stat_standard_deviation=std_dev_gb,
                            prop_line=prop_line_gb,
                            number_of_simulations=gb_sims,
                            blowout_risk_factor=proj_gb.get("blowout_risk_factor", 0.1),
                            pace_adjustment_factor=proj_gb.get("pace_factor", 1.0),
                            matchup_adjustment_factor=proj_gb.get("defense_factor", 1.0),
                            home_away_adjustment=proj_gb.get("home_away_factor", 0.0),
                            rest_adjustment_factor=proj_gb.get("rest_factor", 1.0),
                        )
                        over_prob_gb = sim_gb.get("over_probability", 0.5)
                    except Exception:
                        over_prob_gb = 0.5

                    try:
                        conf_gb = calculate_confidence_score(
                            over_probability=over_prob_gb,
                            sample_size=gb_sims,
                            edge_percentage=(over_prob_gb - 0.5) * 100,
                            directional_forces_count=1,
                            directional_agreement=0.6,
                            player_consistency=0.7,
                        )
                        conf_score_gb = conf_gb if isinstance(conf_gb, (int, float)) else conf_gb.get("confidence_score", 0)
                    except Exception:
                        conf_score_gb = 0

                    custom_results_gb.append({
                        "player_name": pname_gb,
                        "team": home_team_gb if is_home_gb else away_team_gb,
                        "stat_type": stat_gb,
                        "prop_line": prop_line_gb,
                        "projected": round(projected_value_gb, 1),
                        "over_probability": over_prob_gb,
                        "confidence_score": conf_score_gb,
                        "minutes_used": pdata_adj_gb["minutes_avg"],
                    })

            prog_gb.empty()
            st.session_state["custom_game_analysis"] = custom_results_gb
            st.success(
                f"✅ Custom simulation complete! Analyzed {len(all_active_gb)} players × 4 stats "
                f"= {len(custom_results_gb)} prop projections."
            )

        # Display custom results if available
        if st.session_state.get("custom_game_analysis"):
            st.markdown("### 📊 Custom Simulation Results")
            custom_res_gb = st.session_state["custom_game_analysis"]
            custom_res_sorted_gb = sorted(custom_res_gb, key=lambda x: x.get("confidence_score", 0), reverse=True)

            for r_gb in custom_res_sorted_gb[:20]:  # Top 20
                over_prob_r = r_gb.get("over_probability", 0.5)
                direction_r = "OVER" if over_prob_r > 0.5 else "UNDER"
                conf_r = r_gb.get("confidence_score", 0)
                tier_r = "🥇 Platinum" if conf_r >= 85 else "🥈 Gold" if conf_r >= 70 else "🥉 Silver" if conf_r >= 55 else "Bronze"
                st.markdown(
                    f"**{r_gb['player_name']}** ({r_gb['team']}) — "
                    f"{r_gb['stat_type'].upper()} {direction_r} {r_gb['prop_line']} "
                    f"| Proj: {r_gb['projected']} | {over_prob_r * 100:.1f}% | {tier_r} "
                    f"| {r_gb['minutes_used']:.0f} min"
                )
    elif home_team_gb == away_team_gb:
        st.warning("⚠️ Home and Away teams must be different.")
    else:
        st.info("Select both a home and away team to begin building a custom game simulation.")

# ============================================================
# END SECTION: Game Builder Tab
# ============================================================


# ============================================================
# SECTION: Game Narrative Tab
# ============================================================

def _generate_game_narrative(game, _analysis_results):
    """Generate a readable game preview narrative from analysis results."""
    home_team_n = game.get("home_team", "Home")
    away_team_n = game.get("away_team", "Away")
    total_n     = game.get("game_total", 220)
    spread_n    = game.get("vegas_spread", 0)

    # Get top picks for this game
    game_picks_n = [
        r for r in _analysis_results
        if r.get("team", r.get("player_team", "")).upper() in
           {home_team_n.upper(), away_team_n.upper()}
        and r.get("confidence_score", 0) >= 55
        and not r.get("player_is_out", False)
    ]
    game_picks_n = sorted(game_picks_n, key=lambda x: x.get("confidence_score", 0), reverse=True)

    narrative_n = f"## 🏀 GAME PREVIEW: {away_team_n} @ {home_team_n}\n\n"

    # Projected score
    try:
        total_float = float(total_n or 220)
        spread_float = float(spread_n or 0)
        proj_home_n = round(total_float / 2 + abs(spread_float) / 2 * (-1 if spread_float > 0 else 1))
        proj_away_n = round(total_float - proj_home_n)
        narrative_n += f"The model projects a **{away_team_n} {proj_away_n} — {home_team_n} {proj_home_n}** final.\n\n"
    except Exception:
        narrative_n += f"Game Total: {total_n}\n\n"

    # Spread analysis
    try:
        spread_val = float(spread_n or 0)
        if spread_val != 0:
            fav_n = home_team_n if spread_val < 0 else away_team_n
            dog_n = away_team_n if spread_val < 0 else home_team_n
            narrative_n += f"**{fav_n}** is favored by {abs(spread_val):.1f} points over **{dog_n}**.\n\n"
    except Exception:
        pass

    # Top picks from this matchup
    if game_picks_n:
        narrative_n += "### 🎯 TOP PICKS FROM THIS MATCHUP\n"
        for pick_n in game_picks_n[:5]:
            prob_n = pick_n.get("over_probability", pick_n.get("probability_over", 0.5)) * 100
            direction_n = "OVER" if pick_n.get("over_probability", pick_n.get("probability_over", 0.5)) > 0.5 else "UNDER"
            conf_n = pick_n.get("confidence_score", 0)
            tier_n = "Platinum" if conf_n >= 85 else "Gold" if conf_n >= 70 else "Silver"
            stat_label = pick_n.get("stat_type", "").replace("_", " ")
            line_val = pick_n.get("prop_line", pick_n.get("line", 0))
            narrative_n += (
                f"• **{pick_n['player_name']}** {direction_n} {line_val} {stat_label} "
                f"— {prob_n:.0f}% probability, {tier_n} tier\n"
            )

    return narrative_n


with _tab_narrative:
    st.subheader("📖 Game Narrative")
    st.caption("AI-generated game preview story from analysis results")

    if not analysis_results:
        st.info(
            "💡 Run **⚡ Neural Analysis** first to generate narrative previews. "
            "The narrative is built from prop analysis results."
        )
    elif not todays_games:
        st.info(
            "💡 Load tonight's games on the **📡 Live Games** page to generate per-game narratives."
        )
    else:
        _narrative_games = _games_to_show if "_games_to_show" in dir() and _games_to_show else todays_games
        for _narr_game in _narrative_games:
            _narr_home = _narr_game.get("home_team", "")
            _narr_away = _narr_game.get("away_team", "")
            with st.expander(f"🏀 {_narr_away} @ {_narr_home}", expanded=True):
                _narrative_text = _generate_game_narrative(_narr_game, analysis_results)
                st.markdown(_narrative_text)

# ============================================================
# END SECTION: Game Narrative Tab
# ============================================================
