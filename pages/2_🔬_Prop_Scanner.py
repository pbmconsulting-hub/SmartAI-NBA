# ============================================================
# FILE: pages/2_📥_Import_Props.py
# PURPOSE: Allow users to enter prop lines manually or upload
#          a CSV file. Stores props in session state for Analysis.
# CONNECTS TO: data_manager.py (load/save), Analysis page
# CONCEPTS COVERED: Forms, file upload, data tables, CSV parsing
# ============================================================

import streamlit as st
import datetime

from data.data_manager import (
    load_players_data,
    load_props_data,
    load_props_from_session,
    save_props_to_session,
    get_all_player_names,
    parse_props_from_csv_text,
    get_csv_template,
    find_player_by_name,
    enrich_prop_with_player_data,
    validate_props_against_roster,
    get_player_status,
    load_injury_status,
    generate_props_for_todays_players,
)
from data.platform_mappings import (
    normalize_stat_type,
    detect_platform_from_stat_names,
    COMBO_STATS,
    FANTASY_SCORING,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Prop Scanner — SmartBetPro NBA",
    page_icon="🔬",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
/* Platform color badges */
.plat-prizepicks { background:#276749; color:#9ae6b4; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; }
.plat-underdog   { background:#553c9a; color:#d6bcfa; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; }
.plat-draftkings { background:#2b6cb0; color:#bee3f8; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; }
.plat-default    { background:#1a2035; color:#c0d0e8; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; border:1px solid rgba(0,240,255,0.20); }
/* Team pill */
.team-pill { background:rgba(0,240,255,0.12); color:#fff; border:1px solid rgba(0,240,255,0.30); padding:1px 6px; border-radius:4px; font-size:0.8rem; font-weight:700; }
/* Line context: high/low */
.line-high { color:#ff6b6b; font-size:0.75rem; }
.line-low  { color:#00ff9d; font-size:0.75rem; }
.line-ok   { color:#8a9bb8; font-size:0.75rem; }
</style>
""", unsafe_allow_html=True)

st.title("🔬 Prop Scanner")
st.markdown("Enter prop lines manually or upload a CSV. Sample props are pre-loaded!")
st.divider()

st.markdown(get_education_box_html(
    "📖 What is a Prop Bet?",
    """
    <strong>Prop Bet</strong>: A bet on whether a player will exceed (Over) or fall short of (Under) a 
    statistical threshold set by the platform.<br><br>
    Example: "LeBron James Points OVER 24.5" — you win if LeBron scores 25 or more points.<br><br>
    <strong>How to read a prop line</strong>: The number (24.5) is the threshold. 
    Always bet OVER or UNDER — never equal (that's a push/tie).<br><br>
    <strong>Platforms</strong>: PrizePicks and Underdog use Flex scoring (partial wins). 
    DraftKings Pick6 requires all picks to hit for full payout.
    """
), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Load Available Data
# ============================================================

players_data = load_players_data()
all_player_names = get_all_player_names(players_data)

# Simple stats + combo + fantasy stat types
valid_stat_types = (
    ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"]
    + sorted(COMBO_STATS.keys())
    + sorted(FANTASY_SCORING.keys())
    + ["double_double", "triple_double"]
)
valid_platforms = ["PrizePicks", "Underdog", "DraftKings"]

# ============================================================
# END SECTION: Load Available Data
# ============================================================

# ============================================================
# SECTION: Current Props Table
# ============================================================

current_props = load_props_from_session(st.session_state)

# ── Auto-generate props when games are loaded but no props exist yet ──────────
# This makes the Prop Scanner "just work" immediately after the user loads
# tonight's games on the Live Games page, with no extra manual step needed.
if not current_props:
    _auto_games = st.session_state.get("todays_games", [])
    if _auto_games:
        _auto_platforms = st.session_state.get(
            "selected_platforms", ["PrizePicks", "Underdog", "DraftKings"]
        )
        _silent_props = generate_props_for_todays_players(
            players_data, _auto_games, platforms=_auto_platforms
        )
        if _silent_props:
            save_props_to_session(_silent_props, st.session_state)
            current_props = _silent_props
            st.toast(
                f"✅ Auto-generated {len(_silent_props)} props for tonight's {len(_auto_games)} game(s).",
                icon="🤖",
            )

# Load persisted injury status for warning display (no API call needed)
injury_status_map = load_injury_status()

# ── Injury-status classification of all current props ─────────────
_UNAVAILABLE_STATUSES = {"Out", "Doubtful", "Injured Reserve"}
_GTD_STATUSES = {"GTD", "Questionable", "Day-to-Day"}

_unavailable_props = []
_gtd_props = []
_healthy_props = []

for _p in current_props:
    _pname = _p.get("player_name", "")
    _si = get_player_status(_pname, injury_status_map)
    _pstatus = _si.get("status", "Active")
    if _pstatus in _UNAVAILABLE_STATUSES:
        _unavailable_props.append((_p, _pstatus, _si.get("injury_note", "")))
    elif _pstatus in _GTD_STATUSES:
        _gtd_props.append((_p, _pstatus, _si.get("injury_note", "")))
    else:
        _healthy_props.append((_p, _pstatus, _si.get("injury_note", "")))

# ── Toggle: show injured players anyway ───────────────────────────
_show_injured = st.toggle(
    "👁️ Show injured players anyway (Out/Doubtful)",
    value=False,
    help="By default, players confirmed Out or Doubtful are hidden. Enable this to see all props.",
)

# ── Summary banner for removed props ──────────────────────────────
if _unavailable_props and not _show_injured:
    st.error(
        f"⚠️ **{len(_unavailable_props)} prop(s) hidden** — player(s) are confirmed "
        f"**Out or Doubtful**: "
        + ", ".join(f"**{p.get('player_name','')}**" for p, _, _ in _unavailable_props)
        + ". Enable *'Show injured players anyway'* to view them."
    )

# ── Determine which props to display ──────────────────────────────
if _show_injured:
    _display_props_raw = current_props
    _display_props_enriched = [enrich_prop_with_player_data(p, players_data) for p in _display_props_raw]
else:
    # Only non-unavailable props
    _safe_props = [p for p, _, _ in _healthy_props + _gtd_props]
    _display_props_raw = _safe_props
    _display_props_enriched = [enrich_prop_with_player_data(p, players_data) for p in _safe_props]

st.subheader(f"📋 Current Props ({len(_display_props_enriched)} displayed / {len(current_props)} total)")

# ── Smart Scan Pre-Filter Bar ─────────────────────────────────────
if _display_props_enriched:
    with st.expander("🔍 Smart Scan — Pre-Filter Props", expanded=False):
        st.markdown(
            "Narrow down to the most promising props before running Neural Analysis. "
            "Filters apply to the table below and carry into the analysis run."
        )
        _sf1, _sf2, _sf3, _sf4 = st.columns(4)
        with _sf1:
            _filter_platform = st.multiselect(
                "Platform",
                options=["PrizePicks", "Underdog", "DraftKings"],
                default=[],
                placeholder="All platforms",
                key="scan_platform_filter",
            )
        with _sf2:
            _filter_stat = st.multiselect(
                "Stat Type",
                options=sorted({p.get("stat_type", "").capitalize() for p in _display_props_enriched if p.get("stat_type")}),
                default=[],
                placeholder="All stats",
                key="scan_stat_filter",
            )
        with _sf3:
            _filter_line_max = st.slider(
                "Max Line Value",
                min_value=0.0,
                max_value=60.0,
                value=60.0,
                step=0.5,
                key="scan_line_max",
            )
        with _sf4:
            _filter_healthy_only = st.toggle(
                "Healthy Players Only",
                value=True,
                key="scan_healthy_filter",
                help="Hide GTD/Out players from Smart Scan results",
            )

        # Apply Smart Scan filters
        _scanned = _display_props_enriched
        if _filter_platform:
            _scanned = [p for p in _scanned if p.get("platform", "") in _filter_platform]
        if _filter_stat:
            _scanned = [p for p in _scanned if p.get("stat_type", "").capitalize() in _filter_stat]
        _scanned = [p for p in _scanned if float(p.get("line", 0)) <= _filter_line_max]
        if _filter_healthy_only:
            _healthy_names = {p.get("player_name", "") for p, _, _ in _healthy_props}
            _scanned = [p for p in _scanned if p.get("player_name", "") in _healthy_names]

        st.caption(f"**Smart Scan result: {len(_scanned)} props** match your filters (out of {len(_display_props_enriched)} displayed).")
        if _scanned:
            # Line comparison visual: show line vs season avg as a bar
            _cmp_rows = []
            for _sp in _scanned[:30]:
                _sn = _sp.get("player_name", "")
                _st_t = _sp.get("stat_type", "").capitalize()
                _ln = float(_sp.get("line", 0))
                _sa_map = {
                    "Points": _sp.get("season_pts_avg", 0),
                    "Rebounds": _sp.get("season_reb_avg", 0),
                    "Assists": _sp.get("season_ast_avg", 0),
                }
                _avg = float(_sa_map.get(_st_t, 0) or 0)
                _diff_pct = round((_ln - _avg) / _avg * 100, 1) if _avg > 0 else 0
                _vs = f"+{_diff_pct:.1f}%" if _diff_pct >= 0 else f"{_diff_pct:.1f}%"
                _cmp_rows.append({
                    "Player": _sn,
                    "Stat": _st_t,
                    "Line": _ln,
                    "Season Avg": round(_avg, 1) if _avg else "—",
                    "Line vs Avg": _vs,
                    "Platform": _sp.get("platform", ""),
                })
            st.dataframe(
                _cmp_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Line": st.column_config.NumberColumn(format="%.1f"),
                    "Season Avg": st.column_config.NumberColumn(format="%.1f"),
                    "Line vs Avg": st.column_config.TextColumn(),
                },
            )

            # Bulk edit: update lines for scanned props
            with st.expander("✏️ Bulk Edit Lines", expanded=False):
                st.markdown("Adjust prop lines for the Smart Scan results in bulk:")
                _bulk_adjustments = {}
                for _bi, _bp in enumerate(_scanned[:10]):
                    _bname = _bp.get("player_name", "")
                    _bstat = _bp.get("stat_type", "")
                    _bline = float(_bp.get("line", 0))
                    _bc1, _bc2, _bc3 = st.columns([3, 2, 1])
                    with _bc1:
                        st.markdown(f"**{_bname}** — {_bstat.title()}")
                    with _bc2:
                        _new_line = st.number_input(
                            "Line",
                            min_value=0.0,
                            max_value=100.0,
                            value=_bline,
                            step=0.5,
                            key=f"bulk_line_{_bi}",
                            label_visibility="collapsed",
                        )
                    with _bc3:
                        if _new_line != _bline:
                            _bulk_adjustments[(_bname, _bstat)] = _new_line

                if _bulk_adjustments and st.button("💾 Apply Bulk Edits", type="primary", key="bulk_apply"):
                    _updated = []
                    for _raw in current_props:
                        _k = (_raw.get("player_name", ""), _raw.get("stat_type", ""))
                        if _k in _bulk_adjustments:
                            _raw = dict(_raw)
                            _raw["line"] = _bulk_adjustments[_k]
                        _updated.append(_raw)
                    save_props_to_session(_updated, st.session_state)
                    st.success(f"✅ Updated {len(_bulk_adjustments)} prop line(s)!")
                    st.rerun()

if _display_props_enriched:
    # Build display rows with season averages, line context, and injury status
    display_rows = []
    for i, prop in enumerate(_display_props_enriched):
        player_name = prop.get("player_name", "")
        team = prop.get("player_team", prop.get("team", ""))
        stat = prop.get("stat_type", "").capitalize()
        line = prop.get("line", 0)
        platform = prop.get("platform", "")
        pts = prop.get("season_pts_avg", 0)
        reb = prop.get("season_reb_avg", 0)
        ast = prop.get("season_ast_avg", 0)
        line_diff = prop.get("line_vs_avg_pct", 0)

        # Season avg for this stat type
        stat_key = stat.lower()
        stat_avg_map = {"points": pts, "rebounds": reb, "assists": ast}
        season_avg = stat_avg_map.get(stat_key, 0)

        # Line context
        if line_diff > 10:
            line_ctx = f"↑{line_diff:.0f}% above avg"
        elif line_diff < -10:
            line_ctx = f"↓{abs(line_diff):.0f}% below avg"
        else:
            line_ctx = "near avg"

        # Injury / availability status badge
        status_info = get_player_status(player_name, injury_status_map)
        player_status = status_info.get("status", "Active")
        status_emoji = {
            "Out": "🔴", "Injured Reserve": "🔴", "Doubtful": "🔴",
            "Questionable": "🟡", "GTD": "🟡", "Day-to-Day": "🟡",
            "Active": "🟢", "Probable": "🟢",
        }.get(player_status, "⚪")

        display_rows.append({
            "#": i + 1,
            "Player": player_name,
            "Status": f"{status_emoji} {player_status}",
            "Team": team,
            "Stat": stat,
            "Line": line,
            "Season Avg": round(season_avg, 1) if season_avg else "—",
            "Line Context": line_ctx if season_avg else "—",
            "Platform": platform,
            "Date": prop.get("game_date", ""),
        })

    st.dataframe(
        display_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Line": st.column_config.NumberColumn(format="%.1f"),
            "Season Avg": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # Show GTD / Questionable warnings
    gtd_warnings = []
    for p, pstatus, note in _gtd_props:
        pname = p.get("player_name", "")
        gtd_warnings.append(
            f"⚠️ **{pname}** is **{pstatus}**" + (f" — {note}" if note else "")
        )
    # If showing injured, also show Out/Doubtful warnings
    if _show_injured:
        for p, pstatus, note in _unavailable_props:
            pname = p.get("player_name", "")
            gtd_warnings.append(
                f"⛔ **{pname}** is **{pstatus}**" + (f" — {note}" if note else "")
            )

    if gtd_warnings:
        with st.expander(
            f"🏥 Availability Alerts ({len(gtd_warnings)} player(s)) — click to expand",
            expanded=True,
        ):
            for warning in gtd_warnings:
                if warning.startswith("⛔"):
                    st.error(warning)
                else:
                    st.warning(warning)

    col_clear, col_load_sample, _ = st.columns([1, 1, 3])
    with col_clear:
        if st.button("🗑️ Clear All Props"):
            st.session_state["current_props"] = []
            st.session_state["analysis_results"] = []
            st.rerun()
    with col_load_sample:
        if st.button("📦 Load Sample Props"):
            sample_props = load_props_data()
            save_props_to_session(sample_props, st.session_state)
            st.success(f"Loaded {len(sample_props)} sample props!")
            st.rerun()

    # Roster validation table
    if players_data:
        from styles.theme import get_roster_health_html
        validation = validate_props_against_roster(current_props, players_data)
        total_v = validation["total"]
        matched_count_v = validation["matched_count"]

        # Show OUT warnings from the validation result (these are post-processed by data_manager)
        out_in_validation = [
            item for item in validation["matched"] + validation["fuzzy_matched"]
            if item.get("out_warning")
        ]
        if out_in_validation:
            for item in out_in_validation:
                st.error(item["out_warning"])

        if total_v > 0:
            with st.expander(
                f"🧬 Roster Health: {matched_count_v}/{total_v} props matched "
                f"({int(matched_count_v/max(total_v,1)*100)}%) — click to see details",
                expanded=(len(validation["unmatched"]) > 0),
            ):
                st.markdown(
                    get_roster_health_html(
                        validation["matched"],
                        validation["fuzzy_matched"],
                        validation["unmatched"],
                    ),
                    unsafe_allow_html=True,
                )

else:
    if current_props:
        st.info(
            f"No props to display. "
            f"{'All ' + str(len(current_props)) + ' prop(s) are hidden (players are Out/Doubtful). '  if _unavailable_props and not _show_injured else ''}"
            "Use the toggle above to show injured players."
        )
    else:
        st.info("No props loaded. Use the forms below to add props.")

# ============================================================
# END SECTION: Current Props Table
# ============================================================

st.divider()

# ============================================================
# SECTION: Auto-Generate Props for Tonight's Games
# ============================================================

st.subheader("🤖 Auto-Generate Props for Tonight's Games")
st.markdown(
    "Generate prop entries for **all active players** on tonight's teams across all "
    "three platforms — **PrizePicks**, **Underdog Fantasy**, and **DraftKings Pick 6**. "
    "Prop lines are derived from each player's season averages (rounded to nearest 0.5)."
)

todays_games_for_gen = st.session_state.get("todays_games", [])
if not todays_games_for_gen:
    st.info(
        "💡 No games loaded yet. Load tonight's games on the **📡 Live Games** page first "
        "so only tonight's players are included. You can still auto-generate props for "
        "all players in the database by clicking the button below."
    )
else:
    st.success(
        f"✅ {len(todays_games_for_gen)} game(s) loaded for tonight — "
        "props will be generated for those teams only."
    )

_ag_col1, _ag_col2 = st.columns([2, 3])
with _ag_col1:
    _ag_platforms = st.multiselect(
        "Platforms to generate for:",
        options=["PrizePicks", "Underdog", "DraftKings"],
        default=st.session_state.get("selected_platforms", ["PrizePicks", "Underdog", "DraftKings"]),
        key="autogen_platforms",
        help="Choose which platforms to generate props for.",
    )
with _ag_col2:
    _ag_replace = st.radio(
        "How to add generated props:",
        ["Replace all existing props", "Append to existing props"],
        horizontal=True,
        key="autogen_mode",
    )

if st.button(
    "🤖 Auto-Generate All Props for Tonight",
    type="primary",
    use_container_width=False,
    disabled=not _ag_platforms,
):
    with st.spinner("Generating props for tonight's active roster players…"):
        _gen_props = generate_props_for_todays_players(
            players_data=players_data,
            todays_games=todays_games_for_gen,
            platforms=_ag_platforms,
        )

    if _gen_props:
        # Summary by platform
        _by_plat = {}
        for _gp in _gen_props:
            _plat = _gp.get("platform", "—")
            _by_plat[_plat] = _by_plat.get(_plat, 0) + 1

        if _ag_replace == "Replace all existing props":
            save_props_to_session(_gen_props, st.session_state)
            st.success(
                f"✅ Replaced props with **{len(_gen_props)}** auto-generated entries: "
                + " · ".join(f"{p}: {n}" for p, n in sorted(_by_plat.items()))
            )
        else:
            _existing = load_props_from_session(st.session_state)
            _combined = _existing + _gen_props
            save_props_to_session(_combined, st.session_state)
            st.success(
                f"✅ Added **{len(_gen_props)}** auto-generated props "
                f"(total: {len(_combined)}): "
                + " · ".join(f"{p}: {n}" for p, n in sorted(_by_plat.items()))
            )
        st.rerun()
    else:
        st.warning(
            "⚠️ No props generated. Make sure player data is loaded and tonight's games are set. "
            "Try loading tonight's games on the **📡 Live Games** page."
        )

# ============================================================
# END SECTION: Auto-Generate Props for Tonight's Games
# ============================================================

st.divider()

# ============================================================
# SECTION: Manual Entry Form
# ============================================================

st.subheader("✏️ Add Props Manually")
st.markdown("Enter one prop at a time. Click **Add Prop** to save each one.")

with st.form("manual_prop_entry", clear_on_submit=True):
    col1, col2, col3, col4 = st.columns([3, 1, 1, 2])

    with col1:
        selected_player = st.selectbox(
            "Player Name *",
            options=["— Type or select —"] + all_player_names,
        )
        custom_player_name = st.text_input(
            "Or type player name:",
            placeholder="e.g., LeBron James",
        )

    with col2:
        stat_type_selection = st.selectbox("Stat Type *", options=valid_stat_types)

    with col3:
        prop_line_value = st.number_input(
            "Line *",
            min_value=0.0, max_value=100.0,
            value=24.5, step=0.5,
        )

    with col4:
        platform_selection = st.selectbox("Platform *", options=valid_platforms)

    col5, col6, col7 = st.columns([2, 2, 3])
    with col5:
        team_input = st.text_input("Team (optional)", placeholder="e.g., LAL")
    with col6:
        game_date_input = st.date_input("Game Date", value=datetime.date.today())

    add_prop_button = st.form_submit_button(
        "➕ Add Prop",
        use_container_width=True,
        type="primary",
    )

if add_prop_button:
    if custom_player_name.strip():
        final_player_name = custom_player_name.strip()
    elif selected_player != "— Type or select —":
        final_player_name = selected_player
    else:
        final_player_name = ""

    if not final_player_name:
        st.error("Please enter or select a player name.")
    elif prop_line_value <= 0:
        st.error("Prop line must be greater than 0.")
    else:
        # Auto-fill team from player database if not provided
        auto_team = team_input.strip().upper() if team_input else ""
        if not auto_team:
            player_lookup = find_player_by_name(players_data, final_player_name)
            if player_lookup:
                auto_team = player_lookup.get("team", "")

        new_prop = {
            "player_name": final_player_name,
            "team": auto_team,
            "stat_type": stat_type_selection,
            "line": prop_line_value,
            "platform": platform_selection,
            "game_date": game_date_input.isoformat(),
        }

        current_props_for_update = load_props_from_session(st.session_state)
        current_props_for_update.append(new_prop)
        save_props_to_session(current_props_for_update, st.session_state)
        st.success(f"✅ Added: {final_player_name} ({auto_team}) | {stat_type_selection} | {prop_line_value} | {platform_selection}")
        st.rerun()

# ============================================================
# END SECTION: Manual Entry Form
# ============================================================

st.divider()

# ============================================================
# SECTION: CSV Upload
# ============================================================

st.subheader("📤 Upload Props CSV")

st.markdown("**Required CSV format:**")
st.code(
    "player_name,team,stat_type,line,platform,game_date\n"
    "LeBron James,LAL,points,24.5,PrizePicks,2026-03-05\n"
    "Stephen Curry,GSW,threes,3.5,Underdog,2026-03-05",
    language="csv",
)

template_csv = get_csv_template()
st.download_button(
    label="⬇️ Download CSV Template",
    data=template_csv,
    file_name="props_template.csv",
    mime="text/csv",
)

st.markdown("---")

uploaded_file = st.file_uploader(
    "Upload your props CSV file",
    type=["csv"],
)

if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    parsed_props, parse_errors = parse_props_from_csv_text(file_content)

    if parse_errors:
        for error in parse_errors:
            st.warning(f"⚠️ {error}")

    if parsed_props:
        # Auto-detect platform and normalize stat types through platform mappings
        raw_stat_names = [p.get("stat_type", "") for p in parsed_props]
        detected_platform = detect_platform_from_stat_names(raw_stat_names)
        if detected_platform:
            st.info(f"🔍 Auto-detected platform: **{detected_platform}**")

        for p in parsed_props:
            raw_stat = p.get("stat_type", "")
            platform_hint = p.get("platform", detected_platform or "")
            normalized = normalize_stat_type(raw_stat, platform_hint)
            if normalized != raw_stat:
                p["stat_type"] = normalized

        st.success(f"✅ Parsed {len(parsed_props)} props from upload!")

        # Auto-enrich with player data
        enriched_preview = [enrich_prop_with_player_data(p, players_data) for p in parsed_props]
        preview_rows = [
            {
                "Player": p.get("player_name", ""),
                "Team": p.get("player_team", p.get("team", "")),
                "Stat": p.get("stat_type", ""),
                "Line": p.get("line", ""),
                "Season Avg": round(p.get("season_pts_avg", 0), 1) if p.get("stat_type") == "points" else "—",
                "Platform": p.get("platform", ""),
            }
            for p in enriched_preview[:10]
        ]
        st.markdown("**Preview:**")
        st.dataframe(preview_rows, use_container_width=True, hide_index=True)

        if len(parsed_props) > 10:
            st.caption(f"... and {len(parsed_props) - 10} more")

        col_replace, col_add, col_cancel = st.columns([1, 1, 2])
        with col_replace:
            if st.button("🔄 Replace All Props", type="primary"):
                save_props_to_session(parsed_props, st.session_state)
                st.success(f"Replaced all props with {len(parsed_props)} from upload!")
                st.rerun()
        with col_add:
            if st.button("➕ Add to Existing"):
                existing = load_props_from_session(st.session_state)
                combined = existing + parsed_props
                save_props_to_session(combined, st.session_state)
                st.success(f"Added {len(parsed_props)} props. Total: {len(combined)}")
                st.rerun()
    else:
        st.error("No valid props found in the uploaded file.")

# ============================================================
# END SECTION: CSV Upload
# ============================================================

st.divider()

# ============================================================
# SECTION: Quick Add Multiple Props
# ============================================================

st.subheader("⚡ Quick Add (Paste CSV data)")
st.markdown("Paste prop lines directly as CSV text:")

quick_add_text = st.text_area(
    "Paste CSV data here",
    placeholder="player_name,team,stat_type,line,platform\nLeBron James,LAL,points,24.5,PrizePicks\nStephen Curry,GSW,threes,3.5,Underdog",
    height=150,
)

if st.button("⚡ Parse & Add Props") and quick_add_text.strip():
    parsed_props_quick, errors_quick = parse_props_from_csv_text(quick_add_text)

    for error in errors_quick:
        st.warning(f"⚠️ {error}")

    if parsed_props_quick:
        # Normalize stat types through platform mappings
        for p in parsed_props_quick:
            raw_stat = p.get("stat_type", "")
            platform_hint = p.get("platform", "")
            normalized = normalize_stat_type(raw_stat, platform_hint)
            if normalized != raw_stat:
                p["stat_type"] = normalized

        existing = load_props_from_session(st.session_state)
        combined = existing + parsed_props_quick
        save_props_to_session(combined, st.session_state)
        st.success(f"✅ Added {len(parsed_props_quick)} props! Total: {len(combined)}")
        st.rerun()
    else:
        st.error("Could not parse any props from the input.")

