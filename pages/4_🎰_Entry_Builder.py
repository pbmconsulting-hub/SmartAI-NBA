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
    page_title="Entry Builder — SmartAI-NBA",
    page_icon="🎰",
    layout="wide",
)

st.title("🎰 Entry Builder")
st.markdown("Build optimal parlay entries with maximum Expected Value (EV).")
st.divider()

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

            # Show payout breakdown
            with st.expander(f"💰 Entry #{entry_rank} Payout Breakdown"):
                prob_per_hits = ev_result.get("probability_per_hits", {})
                payout_per_hits = ev_result.get("payout_per_hits", {})

                breakdown_rows = []
                for hits in sorted(prob_per_hits.keys(), reverse=True):
                    prob_pct = prob_per_hits[hits] * 100
                    payout = payout_per_hits.get(hits, 0)
                    ev_contribution = (prob_per_hits[hits] * payout) - (entry_fee / (len(prob_per_hits)))
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
