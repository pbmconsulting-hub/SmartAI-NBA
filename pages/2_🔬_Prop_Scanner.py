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

st.subheader(f"📋 Current Props ({len(current_props)} loaded)")

if current_props:
    # Enrich each prop with player data for display
    enriched_props = [enrich_prop_with_player_data(p, players_data) for p in current_props]

    # Build display rows with season averages and line context
    display_rows = []
    for i, prop in enumerate(enriched_props):
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

        display_rows.append({
            "#": i + 1,
            "Player": player_name,
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
    st.info("No props loaded. Use the forms below to add props.")

# ============================================================
# END SECTION: Current Props Table
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

