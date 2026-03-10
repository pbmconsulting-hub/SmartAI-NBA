# ============================================================
# FILE: pages/7_⚙️_Settings.py
# PURPOSE: Configure the SmartBetPro NBA engine settings:
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
    page_title="Settings — SmartBetPro NBA",
    page_icon="⚙️",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

st.title("⚙️ Settings")
st.markdown("Configure the SmartBetPro NBA prediction engine.")
st.divider()

# ============================================================
# SECTION: Preset Profiles
# ============================================================

st.subheader("⚡ Quick Start — Preset Profiles")
st.markdown(
    "Apply a pre-configured profile to instantly tune all settings for your strategy."
)

_PROFILES = {
    "🛡️ Conservative": {
        "description": "Fewer, higher-confidence picks. Lower risk, steadier returns.",
        "simulation_depth": 2000,
        "minimum_edge_threshold": 8.0,
        "entry_fee": 10.0,
        "selected_platforms": ["PrizePicks"],
        "home_court_boost": 0.02,
        "blowout_sensitivity": 1.5,
        "fatigue_sensitivity": 1.5,
        "pace_sensitivity": 1.0,
    },
    "⚖️ Balanced": {
        "description": "Recommended defaults. Good mix of volume and confidence.",
        "simulation_depth": 1000,
        "minimum_edge_threshold": 5.0,
        "entry_fee": 10.0,
        "selected_platforms": ["PrizePicks", "Underdog", "DraftKings"],
        "home_court_boost": 0.025,
        "blowout_sensitivity": 1.0,
        "fatigue_sensitivity": 1.0,
        "pace_sensitivity": 1.0,
    },
    "🚀 Aggressive": {
        "description": "More picks, lower edge threshold. High volume, higher variance.",
        "simulation_depth": 500,
        "minimum_edge_threshold": 2.0,
        "entry_fee": 25.0,
        "selected_platforms": ["PrizePicks", "Underdog", "DraftKings"],
        "home_court_boost": 0.03,
        "blowout_sensitivity": 0.5,
        "fatigue_sensitivity": 0.5,
        "pace_sensitivity": 1.5,
    },
}

_prof_cols = st.columns(3)
for _ci, (_pname, _pdata) in enumerate(_PROFILES.items()):
    with _prof_cols[_ci]:
        st.markdown(
            f'<div style="background:#14192b;border-radius:8px;padding:14px 16px;'
            f'border:1px solid rgba(0,240,255,0.18);margin-bottom:8px;">'
            f'<div style="font-size:1rem;font-weight:700;color:#ff5e00;">{_pname}</div>'
            f'<div style="color:#b0bec5;font-size:0.82rem;margin-top:4px;">{_pdata["description"]}</div>'
            f'<div style="color:#8b949e;font-size:0.75rem;margin-top:6px;">'
            f'Edge ≥ {_pdata["minimum_edge_threshold"]}% · '
            f'{_pdata["simulation_depth"]:,} sims · '
            f'{len(_pdata["selected_platforms"])} platform(s)</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(f"Apply {_pname}", key=f"profile_{_ci}", width="stretch"):
            for _k, _v in _pdata.items():
                if _k != "description":
                    st.session_state[_k] = _v
            st.success(f"✅ {_pname} profile applied!")
            st.rerun()

st.divider()

# ============================================================
# END SECTION: Preset Profiles
# ============================================================

st.markdown(get_education_box_html(
    "📖 What Do These Settings Do?",
    """
    <strong>Simulation Depth</strong>: How many game simulations to run per prop. 
    More = more accurate but slower. 2,000 is the recommended balance.<br><br>
    <strong>Minimum Edge Threshold</strong>: Only show picks with at least this much edge. 
    5% = only show picks where we have at least a 5% probability advantage over the line.<br><br>
    <strong>Entry Fee</strong>: Default dollar amount for EV calculations in Entry Builder.<br><br>
    <strong>Platforms</strong>: Which betting platforms to analyze for. 
    Different platforms have different payout structures.
    """
), unsafe_allow_html=True)

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
# SECTION: API Keys
# Configure API keys needed for platform prop fetching.
# PrizePicks and Underdog have free public APIs (no key needed).
# DraftKings requires The Odds API key (free tier: 500 req/month).
# ============================================================

st.subheader("🔑 API Keys")

st.markdown(get_education_box_html(
    "📖 API Keys for Live Prop Fetching",
    """
    <strong>PrizePicks</strong> and <strong>Underdog Fantasy</strong> have free public APIs — 
    no key needed. Just click "Fetch Live Props" on the Prop Scanner page.<br><br>
    <strong>DraftKings Pick6</strong> lines are fetched via 
    <a href="https://the-odds-api.com" target="_blank" style="color:#00f0ff;">The Odds API</a> 
    (free tier: 500 requests/month). Enter your key below — it's stored only in this 
    browser session and never saved to disk or sent anywhere else.
    """
), unsafe_allow_html=True)

with st.expander("🔑 Configure The Odds API Key (DraftKings)", expanded=False):
    st.markdown(
        "Get your free API key at "
        "[https://the-odds-api.com](https://the-odds-api.com) — free tier gives you "
        "500 requests/month, which is plenty for daily prop fetching."
    )

    # Show the current key status (masked) without revealing the full key
    current_key = st.session_state.get("odds_api_key", "")
    if current_key:
        masked = current_key[:4] + "••••••••" + current_key[-4:] if len(current_key) > 8 else "••••••••"
        st.success(f"✅ API key configured: `{masked}`")
    else:
        st.info("ℹ️ No Odds API key set. DraftKings props will be skipped.")

    # Text input for the key — uses password type to hide it from screen
    new_key = st.text_input(
        "The Odds API Key",
        value=current_key,
        type="password",
        placeholder="e.g., a1b2c3d4e5f6...",
        help="Your Odds API key from the-odds-api.com. Stored in this session only.",
        key="odds_api_key_input",
    )

    col_save_key, col_clear_key = st.columns([1, 1])
    with col_save_key:
        if st.button("💾 Save API Key", width="stretch"):
            st.session_state["odds_api_key"] = new_key.strip()
            if new_key.strip():
                st.success("✅ API key saved for this session!")
            else:
                st.info("API key cleared.")
            st.rerun()
    with col_clear_key:
        if st.button("🗑️ Clear API Key", width="stretch"):
            st.session_state["odds_api_key"] = ""
            st.info("API key cleared.")
            st.rerun()

st.divider()

# ============================================================
# SECTION: Platform Fetch Toggles
# Enable or disable fetching from each platform.
# These are used by the "Fetch Live Props" button on the Prop Scanner
# and the "Fetch Platform Props" section on the Data Feed page.
# ============================================================

st.subheader("🏀 Platform Fetch Settings")

st.markdown("Control which platforms are included when fetching live prop lines.")

toggle_col1, toggle_col2, toggle_col3 = st.columns(3)

with toggle_col1:
    pp_enabled = st.toggle(
        "✅ PrizePicks",
        value=st.session_state.get("fetch_prizepicks_enabled", True),
        help="Fetch props from PrizePicks (free public API, no key required).",
    )
    st.session_state["fetch_prizepicks_enabled"] = pp_enabled
    st.markdown(
        '<div style="color:#9ae6b4;font-size:0.78rem;">No API key needed</div>',
        unsafe_allow_html=True,
    )

with toggle_col2:
    ud_enabled = st.toggle(
        "✅ Underdog Fantasy",
        value=st.session_state.get("fetch_underdog_enabled", True),
        help="Fetch props from Underdog Fantasy (free public API, no key required).",
    )
    st.session_state["fetch_underdog_enabled"] = ud_enabled
    st.markdown(
        '<div style="color:#d6bcfa;font-size:0.78rem;">No API key needed</div>',
        unsafe_allow_html=True,
    )

with toggle_col3:
    dk_enabled = st.toggle(
        "✅ DraftKings Pick6",
        value=st.session_state.get("fetch_draftkings_enabled", True),
        help="Fetch DraftKings lines via The Odds API. Requires a free API key.",
    )
    st.session_state["fetch_draftkings_enabled"] = dk_enabled
    has_dk_key = bool(st.session_state.get("odds_api_key", "").strip())
    st.markdown(
        f'<div style="color:{"#bee3f8" if has_dk_key else "#ff6b6b"};font-size:0.78rem;">'
        f'{"API key ✓" if has_dk_key else "⚠️ Needs API key"}</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ============================================================
# END SECTION: Platform Fetch Settings
# ============================================================

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
    "PrizePicks Fetch": "Enabled" if st.session_state.get("fetch_prizepicks_enabled", True) else "Disabled",
    "Underdog Fetch": "Enabled" if st.session_state.get("fetch_underdog_enabled", True) else "Disabled",
    "DraftKings Fetch": "Enabled" if st.session_state.get("fetch_draftkings_enabled", True) else "Disabled",
    "Odds API Key": "Configured ✓" if st.session_state.get("odds_api_key", "") else "Not set",
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
        "fetch_prizepicks_enabled", "fetch_underdog_enabled", "fetch_draftkings_enabled",
    ]
    for key in settings_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.success("All settings reset to defaults! Refresh the page to see changes.")
    st.rerun()

# ============================================================
# END SECTION: Display Current Settings Summary
# ============================================================
