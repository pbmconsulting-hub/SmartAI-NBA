# ============================================================
# FILE: pages/4_🎰_Entry_Builder.py
# PURPOSE: Build optimal parlay entries for PrizePicks,
#          Underdog, and DraftKings. Calculates EV for each.
# CONNECTS TO: entry_optimizer.py, analysis results in session
# CONCEPTS COVERED: Parlays, EV, combinatorics, entry building
# ============================================================

import streamlit as st  # Main UI framework

# Import our entry optimizer engine
from engine.entry_optimizer import (
    build_optimal_entries,
    calculate_entry_expected_value,
    format_ev_display,
    calculate_correlation_risk,
    identify_weakest_link,
    suggest_swap,
    PRIZEPICKS_FLEX_PAYOUT_TABLE,
    PRIZEPICKS_POWER_PAYOUT_TABLE,
    UNDERDOG_FLEX_PAYOUT_TABLE,
    DRAFTKINGS_PICK6_PAYOUT_TABLE,
    PLATFORM_FLEX_TABLES,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Entry Builder — SmartBetPro NBA",
    page_icon="🧬",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_neural_header_html, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []

st.title("🧬 Entry Builder")
st.markdown("Build optimal parlay entries with maximum Expected Value (EV).")
st.divider()

st.markdown(get_education_box_html(
    "📖 Building a Winning Entry",
    """
    <strong>Expected Value (EV)</strong>: How much you'd expect to win or lose per dollar bet over many entries. 
    Positive EV = good bet in the long run.<br><br>
    <strong>Parlay</strong>: All picks in your entry must hit. More picks = bigger payout but lower probability.<br><br>
    <strong>Flex vs Power</strong>: Flex entries pay even if 1-2 picks miss (at reduced rates). 
    Power requires ALL picks to hit for maximum payout.<br><br>
    <strong>Correlation warning</strong>: Two picks from the same game (e.g., two players on the same team) 
    are correlated — if one does well, the other might too. This can be good or bad.
    """
), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Check for Analysis Results
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

if not analysis_results:
    st.warning(
        "⚠️ No analysis results found. Please go to the **🏆 Analysis** page "
        "and run analysis first!"
    )
    st.stop()  # Stop rendering the rest of the page

# Filter to only non-avoided picks with meaningful edge
qualifying_picks = [
    r for r in analysis_results
    if abs(r.get("edge_percentage", 0)) >= 3.0
    and not r.get("should_avoid", False)
    and r.get("confidence_score", 0) >= 40
]

st.info(
    f"📋 **{len(qualifying_picks)} qualifying picks** available "
    f"(from {len(analysis_results)} total analyzed, filtered for meaningful edge)"
)

if len(qualifying_picks) < 2:
    st.error(
        "Need at least 2 qualifying picks to build entries. "
        "Lower the edge threshold in Settings or add more props."
    )
    st.stop()

# ============================================================
# END SECTION: Check for Analysis Results
# ============================================================

# ============================================================
# SECTION: Entry Builder Controls
# ============================================================

st.subheader("⚙️ Entry Settings")

settings_col1, settings_col2, settings_col3, settings_col4 = st.columns(4)

with settings_col1:
    selected_platform = st.selectbox(
        "Platform",
        options=["PrizePicks", "Underdog", "DraftKings"],
        help="Which platform are you building entries for?",
    )

with settings_col2:
    entry_size = st.selectbox(
        "Entry Size (picks)",
        options=[2, 3, 4, 5, 6],
        index=2,  # Default to 4-pick
        help="How many picks in each entry?",
    )

with settings_col3:
    entry_fee = st.number_input(
        "Entry Fee ($)",
        min_value=1.0,
        max_value=500.0,
        value=st.session_state.get("entry_fee", 10.0),
        step=5.0,
        help="How much are you betting per entry?",
    )

with settings_col4:
    max_entries = st.number_input(
        "Show Top N Entries",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        help="How many top entries to display?",
    )

# ============================================================
# END SECTION: Entry Builder Controls
# ============================================================

# ============================================================
# SECTION: Selected Picks from Analysis
# ============================================================

selected_picks = st.session_state.get("selected_picks", [])

if selected_picks:
    st.subheader(f"✅ Your Selected Picks ({len(selected_picks)} picks)")
    st.caption("These picks were selected from the ⚡ Neural Analysis page. Uncheck any you want to remove.")
    
    # Sort options
    sort_by = st.selectbox("Sort by:", ["Confidence (highest first)", "Probability", "Edge"], key="selected_sort")
    
    # Sort the picks
    if sort_by == "Confidence (highest first)":
        selected_picks_sorted = sorted(selected_picks, key=lambda x: x.get("confidence_score", 0), reverse=True)
    elif sort_by == "Probability":
        selected_picks_sorted = sorted(selected_picks, key=lambda x: abs(x.get("probability_over", 0.5) - 0.5), reverse=True)
    else:
        selected_picks_sorted = sorted(selected_picks, key=lambda x: abs(x.get("edge_percentage", 0)), reverse=True)
    
    # Show picks as checkboxes
    picks_to_include = []
    for i, pick in enumerate(selected_picks_sorted):
        direction = pick.get("direction", "OVER")
        prob = pick.get("probability_over", 0.5)
        display_prob = (1.0 - prob) * 100 if direction == "UNDER" else prob * 100
        tier_emoji = pick.get("tier_emoji", "🥉")
        
        col_check, col_info = st.columns([0.1, 0.9])
        with col_check:
            include = st.checkbox("", value=True, key=f"pick_check_{i}_{pick.get('player_name','')}")
        with col_info:
            st.markdown(
                f"**{pick.get('player_name','')}** — "
                f"{pick.get('stat_type','').capitalize()} {direction} {pick.get('line',0)} "
                f"| {tier_emoji} {pick.get('tier','')} "
                f"| {display_prob:.0f}% "
                f"| Edge: {pick.get('edge_percentage',0):.1f}%"
            )
        
        if include:
            picks_to_include.append(pick)
    
    if len(picks_to_include) >= 2:
        st.divider()
        st.subheader("💰 Quick EV Calculation for Selected Picks")
        
        quick_platform = st.selectbox("Platform for EV calc:", ["PrizePicks", "Underdog", "DraftKings"], key="quick_platform")
        quick_fee = st.number_input("Entry Fee ($):", min_value=1.0, value=10.0, key="quick_fee")
        
        selected_probs = [
            p.get("probability_over", 0.5) if p.get("direction") == "OVER"
            else 1.0 - p.get("probability_over", 0.5)
            for p in picks_to_include
        ]
        
        platform_flex_table = PLATFORM_FLEX_TABLES.get(quick_platform, PRIZEPICKS_FLEX_PAYOUT_TABLE)
        payout_for_selected = platform_flex_table.get(len(picks_to_include), {})
        
        if payout_for_selected:
            quick_ev = calculate_entry_expected_value(
                pick_probabilities=selected_probs,
                payout_table=payout_for_selected,
                entry_fee=quick_fee,
            )
            quick_display = format_ev_display(quick_ev, quick_fee)
            ev_color = "green" if quick_display["is_positive_ev"] else "red"
            
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                st.metric("Expected Value", quick_display["ev_label"])
            with col_ev2:
                st.metric("ROI", quick_display["roi_label"])
            with col_ev3:
                combined_prob = 1.0
                for p in selected_probs:
                    combined_prob *= p
                st.metric("All-Hit Probability", f"{combined_prob*100:.1f}%")
            
            # Correlation check
            corr_risk = calculate_correlation_risk(picks_to_include)
            if corr_risk.get("warnings"):
                for w in corr_risk["warnings"]:
                    st.warning(w)
            
            # Weakest link
            weakest = identify_weakest_link(picks_to_include)
            if weakest:
                weakest_prob = weakest.get("probability_over", 0.5) if weakest.get("direction") == "OVER" else 1.0 - weakest.get("probability_over", 0.5)
                if weakest_prob < 0.60:
                    st.warning(f"⚠️ Weakest leg: **{weakest.get('player_name','')}** ({weakest_prob*100:.0f}%) — consider swapping this pick")
        
        if st.button("🗑️ Clear All Selected Picks", key="clear_selected"):
            st.session_state["selected_picks"] = []
            st.rerun()
    elif selected_picks:
        st.caption(f"Select at least 2 picks to calculate EV ({len(picks_to_include)} currently checked)")
    
    st.divider()
else:
    st.info("💡 No picks selected yet. Go to **⚡ Neural Analysis** and click '➕ Add to Entry' on picks you like.")
    st.divider()

# ============================================================
# END SECTION: Selected Picks from Analysis
# ============================================================

# ============================================================
# SECTION: Show Payout Table
# ============================================================

with st.expander(f"📋 {selected_platform} Payout Table"):
    # Get the right payout table
    payout_tables = {
        "PrizePicks (Flex)": PRIZEPICKS_FLEX_PAYOUT_TABLE,
        "PrizePicks (Power)": PRIZEPICKS_POWER_PAYOUT_TABLE,
        "Underdog (Flex)": UNDERDOG_FLEX_PAYOUT_TABLE,
        "DraftKings Pick6": DRAFTKINGS_PICK6_PAYOUT_TABLE,
    }

    table_to_show_key = f"{selected_platform} (Flex)" if selected_platform != "DraftKings" else "DraftKings Pick6"
    table_to_show = payout_tables.get(table_to_show_key, PRIZEPICKS_FLEX_PAYOUT_TABLE)

    if entry_size in table_to_show:
        payout_for_size = table_to_show[entry_size]
        st.markdown(f"**{entry_size}-pick entry payouts (multipliers on entry fee):**")

        payout_display = []
        for hits, multiplier in sorted(payout_for_size.items(), reverse=True):
            payout_display.append({
                "Hits": hits,
                "Payout (multiplier)": f"{multiplier}x",
                "On $10 entry": f"${multiplier * 10:.2f}",
            })
        st.dataframe(payout_display, use_container_width=True, hide_index=True)
    else:
        st.caption(f"No payout data for {entry_size}-pick entries on this platform.")

# ============================================================
# END SECTION: Show Payout Table
# ============================================================

st.divider()

# ============================================================
# SECTION: Build and Display Optimal Entries
# ============================================================

build_button = st.button(
    f"🔨 Build Top {max_entries} {selected_platform} {entry_size}-Pick Entries",
    type="primary",
    use_container_width=True,
)

if build_button:
    with st.spinner("Building optimal entries..."):
        optimal_entries = build_optimal_entries(
            analyzed_picks=qualifying_picks,
            platform=selected_platform,
            entry_size=int(entry_size),
            entry_fee=float(entry_fee),
            max_entries_to_show=int(max_entries),
        )

    if optimal_entries:
        st.success(f"✅ Built {len(optimal_entries)} optimal entries!")

        for entry_rank, entry in enumerate(optimal_entries, start=1):
            picks = entry["picks"]
            ev_result = entry["ev_result"]
            confidence = entry["combined_confidence"]
            ev_display = format_ev_display(ev_result, entry_fee)

            # Color-code by EV (green = positive, red = negative)
            ev_color = "green" if ev_display["is_positive_ev"] else "red"
            ev_label = ev_display["ev_label"]
            roi_label = ev_display["roi_label"]

            # Entry header
            st.markdown(f"### Entry #{entry_rank} | EV: :{ev_color}[{ev_label}] | ROI: {roi_label}")
            st.caption(f"Combined confidence: {confidence:.0f}/100")

            # W2: Correlation risk warnings
            corr_risk = entry.get("correlation_risk", {})
            corr_warnings = corr_risk.get("warnings", [])
            if corr_warnings:
                for w in corr_warnings:
                    st.warning(w)
            if ev_result.get("correlation_discount_applied"):
                discount_pct = round((1.0 - corr_risk.get("discount_multiplier", 1.0)) * 100)
                st.caption(f"📉 Correlation discount applied: −{discount_pct}% EV adjustment")

            # W9: Weakest link warning + swap suggestion
            weakest = entry.get("weakest_link")
            weakest_label = entry.get("weakest_link_label", "")
            weakest_prob = entry.get("weakest_link_probability", 0.5)
            if weakest and weakest_prob < 0.60:
                swap = suggest_swap(weakest, qualifying_picks, picks)
                if swap:
                    st.warning(
                        f"⚠️ **Weakest leg:** {weakest_label} — "
                        f"consider swapping: {swap.get('swap_reason', '')}"
                    )
                else:
                    st.caption(f"⚠️ Weakest leg: {weakest_label}")

            # Show each pick in this entry
            pick_cols = st.columns(len(picks))
            for i, (pick, pick_col) in enumerate(zip(picks, pick_cols)):
                with pick_col:
                    direction = pick.get("direction", "OVER")
                    arrow = "⬆️" if direction == "OVER" else "⬇️"
                    tier_emoji = pick.get("tier_emoji", "🥉")
                    prob = pick.get("probability_over", 0.5)
                    if direction == "UNDER":
                        display_prob = (1.0 - prob) * 100
                    else:
                        display_prob = prob * 100

                    st.metric(
                        label=f"{pick.get('player_name', '')}",
                        value=f"{arrow} {direction}",
                        delta=f"{pick.get('stat_type','').capitalize()} {pick.get('line',0)} | {display_prob:.0f}%",
                    )
                    st.caption(f"{tier_emoji} {pick.get('tier','')} | Edge: {pick.get('edge_percentage',0):.1f}%")
                    # Show trap line warning inline if present
                    trap = pick.get("trap_line_result", {})
                    if trap and trap.get("is_trap"):
                        st.caption(f"⚠️ {trap.get('warning_message','Trap line')}")

            # Show payout breakdown
            with st.expander(f"💰 Entry #{entry_rank} Payout Breakdown"):
                prob_per_hits = ev_result.get("probability_per_hits", {})
                payout_per_hits = ev_result.get("payout_per_hits", {})

                breakdown_rows = []
                for hits in sorted(prob_per_hits.keys(), reverse=True):
                    prob_pct = prob_per_hits[hits] * 100
                    payout = payout_per_hits.get(hits, 0)
                    breakdown_rows.append({
                        "Hits": hits,
                        "Probability": f"{prob_pct:.1f}%",
                        "Payout": f"${payout:.2f}",
                    })

                st.dataframe(breakdown_rows, use_container_width=True, hide_index=True)
                st.caption(
                    f"**Total Expected Return:** ${ev_result.get('total_expected_return', 0):.2f} "
                    f"on ${entry_fee:.2f} entry = **Net EV: {ev_label}**"
                )

            st.markdown("---")

    else:
        st.warning(
            "Could not build optimal entries. Try: lowering the entry size, "
            "reducing the edge threshold in Settings, or analyzing more props."
        )

# ============================================================
# END SECTION: Build and Display Optimal Entries
# ============================================================

st.divider()

# ============================================================
# SECTION: Custom Entry Builder
# Let the user manually select picks and calculate EV
# ============================================================

st.subheader("🔧 Custom Entry Builder")
st.markdown("Manually pick which props to include and calculate the EV.")

# Show all qualifying picks in a selection table
available_pick_options = [
    f"{r.get('player_name','')} | {r.get('stat_type','').capitalize()} | {r.get('line',0)} | {r.get('direction','')} | {r.get('tier_emoji','')}{r.get('tier','')}"
    for r in qualifying_picks
]

# Multi-select for custom entry
selected_pick_labels = st.multiselect(
    "Select picks for your custom entry (2-6 picks):",
    options=available_pick_options,
    help="Choose 2-6 picks to build a custom entry",
)

if len(selected_pick_labels) >= 2:
    # Find the corresponding results
    selected_picks_data = [
        qualifying_picks[available_pick_options.index(label)]
        for label in selected_pick_labels
        if label in available_pick_options
    ]

    # Get probabilities for the selected direction
    selected_probs = [
        p.get("probability_over", 0.5) if p.get("direction") == "OVER"
        else 1.0 - p.get("probability_over", 0.5)
        for p in selected_picks_data
    ]

    # Get payout table
    platform_flex_table = PLATFORM_FLEX_TABLES.get(selected_platform, PRIZEPICKS_FLEX_PAYOUT_TABLE)
    payout_for_custom = platform_flex_table.get(len(selected_picks_data), {})

    if payout_for_custom:
        custom_ev = calculate_entry_expected_value(
            pick_probabilities=selected_probs,
            payout_table=payout_for_custom,
            entry_fee=entry_fee,
        )
        custom_display = format_ev_display(custom_ev, entry_fee)

        ev_color = "green" if custom_display["is_positive_ev"] else "red"

        st.markdown(
            f"**Custom Entry EV: :{ev_color}[{custom_display['ev_label']}]** | "
            f"ROI: {custom_display['roi_label']}"
        )

        # Show combined probability of all hitting
        combined_prob = 1.0
        for p in selected_probs:
            combined_prob *= p
        st.caption(f"Probability of all {len(selected_picks_data)} hitting: {combined_prob*100:.1f}%")
    else:
        st.caption(f"No payout table for {len(selected_picks_data)}-pick entries on {selected_platform}")

elif selected_pick_labels:
    st.caption(f"Select at least 2 picks ({len(selected_pick_labels)} selected so far)")

# ============================================================
# END SECTION: Custom Entry Builder
# ============================================================
