# ============================================================
# FILE: pages/7_⚙️_Settings.py
# PURPOSE: Configure the SmartAI-NBA engine settings:
#          simulation depth, edge thresholds, platform selection,
#          and entry fee defaults. All settings persist in session state.
# CONNECTS TO: All engine pages use settings from session state
# CONCEPTS COVERED: Session state, configuration, settings UI
# ============================================================

import streamlit as st  # Main UI framework

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Settings — SmartAI-NBA",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ Settings")
st.markdown("Configure the SmartAI-NBA prediction engine.")
st.divider()

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Simulation Settings
# ============================================================

st.subheader("🎲 Simulation Settings")

col1, col2 = st.columns(2)

with col1:
    # Simulation depth: how many games to simulate per player
    # More simulations = more accurate probability, but slower
    simulation_depth_options = {
        "Fast (500 sims)": 500,
        "Standard (1,000 sims)": 1000,
        "Accurate (2,000 sims)": 2000,
        "High Accuracy (5,000 sims)": 5000,
    }

    current_depth = st.session_state.get("simulation_depth", 1000)
    # Find the current label for the default
    current_label = "Standard (1,000 sims)"
    for label, value in simulation_depth_options.items():
        if value == current_depth:
            current_label = label
            break

    selected_depth_label = st.selectbox(
        "Simulation Depth",
        options=list(simulation_depth_options.keys()),
        index=list(simulation_depth_options.keys()).index(current_label),
        help=(
            "How many games to simulate per player.\n"
            "More = more accurate, but takes longer.\n"
            "500 is fine for quick checks; 5000 for precision."
        ),
    )
    # Store the numeric value in session state
    st.session_state["simulation_depth"] = simulation_depth_options[selected_depth_label]
    st.caption(f"Current: **{st.session_state['simulation_depth']:,} simulations** per prop")

with col2:
    # Random seed for reproducibility (optional)
    st.info(
        "💡 **About Simulation Depth:**\n\n"
        "Monte Carlo simulation runs thousands of random game scenarios. "
        "More simulations = the probability estimate converges to the true value.\n\n"
        "With 500 sims: ±3-4% accuracy\n"
        "With 1,000 sims: ±2-3% accuracy\n"
        "With 5,000 sims: ±1% accuracy"
    )

# ============================================================
# END SECTION: Simulation Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Edge and Filter Settings
# ============================================================

st.subheader("📐 Edge & Filter Settings")

edge_col1, edge_col2 = st.columns(2)

with edge_col1:
    # Minimum edge threshold: how much edge needed to show/recommend a pick
    current_edge_threshold = st.session_state.get("minimum_edge_threshold", 5.0)

    new_edge_threshold = st.slider(
        "Minimum Edge Threshold (%)",
        min_value=0.0,
        max_value=20.0,
        value=float(current_edge_threshold),
        step=0.5,
        help=(
            "Minimum edge (distance from 50% probability) required "
            "to display a pick in 'Top Picks' view.\n"
            "5% = need at least 55% probability (or 45% for unders).\n"
            "Higher = fewer but stronger picks."
        ),
    )
    st.session_state["minimum_edge_threshold"] = new_edge_threshold
    st.caption(
        f"Picks need at least **{new_edge_threshold}% edge** "
        f"(≥{50 + new_edge_threshold:.0f}% or ≤{50 - new_edge_threshold:.0f}%)"
    )

with edge_col2:
    st.info(
        "💡 **What is Edge?**\n\n"
        "Edge = how far your probability is from 50% (the coin flip).\n\n"
        "- 55% probability = +5% edge (lean OVER)\n"
        "- 45% probability = +5% edge (lean UNDER)\n"
        "- 52% probability = only +2% edge (near coin flip)\n\n"
        "We recommend at least **5% edge** to justify a bet."
    )

# ============================================================
# END SECTION: Edge and Filter Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Platform Settings
# ============================================================

st.subheader("🎰 Platform Settings")

platform_col1, platform_col2 = st.columns(2)

with platform_col1:
    # Which platforms to include
    current_platforms = st.session_state.get(
        "selected_platforms", ["PrizePicks", "Underdog", "DraftKings"]
    )

    new_platforms = st.multiselect(
        "Active Platforms",
        options=["PrizePicks", "Underdog", "DraftKings"],
        default=current_platforms,
        help="Which platforms to include in analysis and entry building",
    )
    if new_platforms:
        st.session_state["selected_platforms"] = new_platforms
    st.caption(f"Active: **{', '.join(st.session_state.get('selected_platforms', []))}**")

with platform_col2:
    # Default entry fee
    current_entry_fee = st.session_state.get("entry_fee", 10.0)

    new_entry_fee = st.number_input(
        "Default Entry Fee ($)",
        min_value=1.0,
        max_value=500.0,
        value=float(current_entry_fee),
        step=5.0,
        help="Default entry fee used for EV calculations in Entry Builder",
    )
    st.session_state["entry_fee"] = new_entry_fee
    st.caption(f"Default entry fee: **${new_entry_fee:.2f}**")

# ============================================================
# END SECTION: Platform Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Model Tuning Settings
# ============================================================

st.subheader("🔬 Model Tuning (Advanced)")

with st.expander("Advanced Adjustment Factors"):
    st.markdown(
        "These multipliers adjust how much weight the model gives to each factor. "
        "The default values work well for most users."
    )

    tune_col1, tune_col2 = st.columns(2)

    with tune_col1:
        # Home court advantage boost
        home_court_boost = st.slider(
            "Home Court Advantage Boost",
            min_value=0.0,
            max_value=0.10,
            value=st.session_state.get("home_court_boost", 0.025),
            step=0.005,
            format="%.3f",
            help="Extra multiplier for home games (default: 0.025 = +2.5%)",
        )
        st.session_state["home_court_boost"] = home_court_boost

        # Blowout risk adjustment
        blowout_sensitivity = st.slider(
            "Blowout Risk Sensitivity",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.get("blowout_sensitivity", 1.0),
            step=0.1,
            help="Multiplier on blowout risk (1.0 = default, 2.0 = double sensitivity)",
        )
        st.session_state["blowout_sensitivity"] = blowout_sensitivity

    with tune_col2:
        # Back-to-back fatigue multiplier
        fatigue_sensitivity = st.slider(
            "Back-to-Back Fatigue Sensitivity",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.get("fatigue_sensitivity", 1.0),
            step=0.1,
            help="Multiplier on fatigue penalty (1.0 = default)",
        )
        st.session_state["fatigue_sensitivity"] = fatigue_sensitivity

        # Pace impact sensitivity
        pace_sensitivity = st.slider(
            "Pace Impact Sensitivity",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.get("pace_sensitivity", 1.0),
            step=0.1,
            help="How much game pace affects stat projections",
        )
        st.session_state["pace_sensitivity"] = pace_sensitivity

    # Reset to defaults button
    if st.button("🔄 Reset Advanced Settings to Defaults"):
        st.session_state["home_court_boost"] = 0.025
        st.session_state["blowout_sensitivity"] = 1.0
        st.session_state["fatigue_sensitivity"] = 1.0
        st.session_state["pace_sensitivity"] = 1.0
        st.success("Advanced settings reset to defaults!")
        st.rerun()

# ============================================================
# END SECTION: Model Tuning Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Display Current Settings Summary
# ============================================================

st.subheader("📋 Current Settings Summary")

settings_summary = {
    "Simulation Depth": f"{st.session_state.get('simulation_depth', 1000):,} simulations",
    "Minimum Edge": f"{st.session_state.get('minimum_edge_threshold', 5.0)}%",
    "Entry Fee": f"${st.session_state.get('entry_fee', 10.0):.2f}",
    "Active Platforms": ", ".join(st.session_state.get("selected_platforms", [])),
    "Home Court Boost": f"{st.session_state.get('home_court_boost', 0.025)*100:.1f}%",
    "Blowout Sensitivity": f"{st.session_state.get('blowout_sensitivity', 1.0):.1f}x",
    "Fatigue Sensitivity": f"{st.session_state.get('fatigue_sensitivity', 1.0):.1f}x",
    "Pace Sensitivity": f"{st.session_state.get('pace_sensitivity', 1.0):.1f}x",
}

summary_rows = [{"Setting": k, "Value": v} for k, v in settings_summary.items()]
st.dataframe(summary_rows, use_container_width=True, hide_index=True)

# Reset ALL settings button
st.divider()
if st.button("🔄 Reset ALL Settings to Defaults", type="secondary"):
    # Clear all settings from session state
    settings_keys_to_clear = [
        "simulation_depth", "minimum_edge_threshold", "entry_fee",
        "selected_platforms", "home_court_boost", "blowout_sensitivity",
        "fatigue_sensitivity", "pace_sensitivity",
    ]
    for key in settings_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.success("All settings reset to defaults! Refresh the page to see changes.")
    st.rerun()

# ============================================================
# END SECTION: Display Current Settings Summary
# ============================================================
