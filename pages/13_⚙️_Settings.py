# ============================================================
# FILE: pages/13_⚙️_Settings.py
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

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating
st.session_state["joseph_page_context"] = "page_settings"
inject_joseph_floating()

st.title("⚙️ Settings")
st.markdown("Configure the SmartBetPro NBA prediction engine.")

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Settings — Tune Your Prediction Engine
    
    Configure the SmartBetPro prediction engine to match your betting style and risk tolerance.
    
    **Quick Start — Preset Profiles**
    - **🛡️ Conservative**: Fewer picks, higher confidence. Best for beginners.
    - **⚖️ Balanced**: Middle ground — good mix of volume and quality.
    - **🔥 Aggressive**: More picks, lower thresholds. For experienced bettors.
    
    **Key Settings Explained**
    - **Simulation Depth**: How many Monte Carlo simulations to run (higher = more accurate, slower)
    - **Minimum Edge Threshold**: Only show props where the model finds at least this much edge
    - **Sensitivity Sliders**: Fine-tune how much weight the model gives to pace, fatigue, blowout risk, etc.
    
    💡 **Pro Tips:**
    - Start with the Conservative preset and adjust from there
    - Higher simulation depth (3000+) gives more precise results but takes longer
    - Minimum edge threshold of 5-8% works well for most bettors
    """)

st.divider()

# ============================================================
# SECTION: Preset Profiles
# ============================================================

st.subheader("⚡ Quick Start — Preset Profiles")
st.markdown(
    "Apply a pre-configured profile to instantly tune all settings for your strategy."
)

_PRIMARY_PLATFORMS = [
    "FanDuel", "DraftKings", "BetMGM", "Caesars",
    "Fanatics", "ESPN Bet", "Hard Rock Bet", "BetRivers",
]

_SECONDARY_PLATFORMS = [
    "William Hill", "Unibet", "BetUS", "Bovada", "MyBookie",
    "BetOnline", "LowVig", "Pinnacle", "SuperBook", "WynnBet",
    "TwinSpires", "BetFred", "Fliff",
]

_ALL_PLATFORMS = _PRIMARY_PLATFORMS + _SECONDARY_PLATFORMS

_PROFILES = {
    "🛡️ Conservative": {
        "description": "Fewer, higher-confidence picks. Lower risk, steadier returns.",
        "simulation_depth": 2000,
        "minimum_edge_threshold": 8.0,
        "entry_fee": 10.0,
        "selected_platforms": _PRIMARY_PLATFORMS[:4],
        "home_court_boost": 0.02,
        "blowout_sensitivity": 1.5,
        "fatigue_sensitivity": 1.5,
        "pace_sensitivity": 1.0,
    },
    "⚖️ Balanced": {
        "description": "Recommended defaults. Good mix of volume and confidence.",
        "simulation_depth": 2000,
        "minimum_edge_threshold": 5.0,
        "entry_fee": 10.0,
        "selected_platforms": list(_PRIMARY_PLATFORMS),
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
        "selected_platforms": list(_ALL_PLATFORMS),
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
# SECTION: API Keys
# ============================================================

st.subheader("🔑 API Keys")
st.markdown(
    "Enter your API keys below. Keys entered here are stored in your browser "
    "session only (temporary). For persistent keys across sessions, copy "
    "`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add "
    "your keys there."
)

_api_col1, _api_col2 = st.columns(2)

with _api_col1:
    _current_cs_key = st.session_state.get("api_nba_key", "")
    _new_cs_key = st.text_input(
        "API-NBA Key",
        value=_current_cs_key,
        type="password",
        placeholder="Enter your API-NBA key",
        help="Get your key at https://v2.nba.api-sports.io/",
    )
    if st.session_state.get("api_nba_key"):
        st.caption("✅ API-NBA key is set")
    else:
        st.caption("⚠️ API-NBA key is **not set** — live data will be unavailable")

with _api_col2:
    _current_odds_key = st.session_state.get("odds_api_key", "")
    _new_odds_key = st.text_input(
        "Odds API Key",
        value=_current_odds_key,
        type="password",
        placeholder="Enter your Odds API key",
        help="Get your key at https://the-odds-api.com",
    )
    if st.session_state.get("odds_api_key"):
        st.caption("✅ Odds API key is set")
    else:
        st.caption("⚠️ Odds API key is **not set** — odds data will be unavailable")

_api_btn_col1, _api_btn_col2, _api_btn_col3, _ = st.columns([1, 1, 1, 1])
with _api_btn_col1:
    if st.button("💾 Save Keys", key="save_api_keys"):
        from data.clearsports_client import validate_api_key as _validate_cs_key
        from data.odds_api_client import validate_api_key as _validate_odds_key

        _changed = False
        _errors: list[str] = []
        if _new_cs_key != _current_cs_key:
            if _new_cs_key:
                _ok, _msg = _validate_cs_key(_new_cs_key)
                if not _ok:
                    _errors.append(f"API-NBA: {_msg}")
                else:
                    st.session_state["api_nba_key"] = _new_cs_key
                    _changed = True
            else:
                st.session_state["api_nba_key"] = _new_cs_key
                _changed = True
        if _new_odds_key != _current_odds_key:
            if _new_odds_key:
                _ok, _msg = _validate_odds_key(_new_odds_key)
                if not _ok:
                    _errors.append(f"Odds API: {_msg}")
                else:
                    st.session_state["odds_api_key"] = _new_odds_key
                    _changed = True
            else:
                st.session_state["odds_api_key"] = _new_odds_key
                _changed = True
        if _errors:
            for _e in _errors:
                st.error(f"❌ {_e}")
        elif _changed:
            st.success("✅ API keys saved to session!")
            st.rerun()
        else:
            st.info("No changes to save.")
with _api_btn_col2:
    if st.button("🗑️ Clear Keys", key="clear_api_keys"):
        st.session_state.pop("api_nba_key", None)
        st.session_state.pop("odds_api_key", None)
        st.warning("API keys cleared.")
        st.rerun()
with _api_btn_col3:
    if st.button("🔍 Test Connection", key="test_api_keys"):
        _test_results: list[str] = []
        # ── API-NBA ──
        _cs_key = st.session_state.get("api_nba_key", "")
        if _cs_key:
            try:
                from data.clearsports_client import fetch_api_key_info
                _info = fetch_api_key_info()
                if _info:
                    _credits = _info.get("credits_remaining", "?")
                    _active = _info.get("is_active", None)
                    _status = "active" if _active else ("inactive" if _active is False else "unknown")
                    _test_results.append(
                        f"✅ **API-NBA**: connected — {_credits} credits remaining, status: {_status}"
                    )
                else:
                    _test_results.append("⚠️ **API-NBA**: key is set but API returned no data")
            except Exception as _exc:
                _test_results.append(f"❌ **API-NBA**: connection error — {_exc}")
        else:
            _test_results.append("⚠️ **API-NBA**: no API key configured")
        # ── Odds API ──
        _odds_key = st.session_state.get("odds_api_key", "")
        if _odds_key:
            try:
                from data.odds_api_client import fetch_events, get_odds_api_usage
                _events = fetch_events()
                _usage = get_odds_api_usage()
                _remaining = _usage.get("requests_remaining")
                if _events is not None:
                    _count = len(_events) if isinstance(_events, list) else 0
                    _quota_str = f", {_remaining} requests remaining" if _remaining is not None else ""
                    _test_results.append(
                        f"✅ **Odds API**: connected — {_count} events found{_quota_str}"
                    )
                else:
                    _test_results.append("⚠️ **Odds API**: key is set but API returned no data")
            except Exception as _exc:
                _test_results.append(f"❌ **Odds API**: connection error — {_exc}")
        else:
            _test_results.append("⚠️ **Odds API**: no API key configured")
        # ── Display results ──
        for _msg in _test_results:
            st.markdown(_msg)

# ============================================================
# END SECTION: API Keys
# ============================================================

st.divider()

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
        "Recommended (2,000 sims)": 2000,
        "High Accuracy (5,000 sims)": 5000,
    }

    current_depth = st.session_state.get("simulation_depth", 2000)
    # Find the current label for the default
    current_label = "Recommended (2,000 sims)"
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
        "Quantum Matrix Engine 5.6 simulation runs thousands of random game scenarios. "
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
            "Minimum edge (distance from the -110 breakeven of 52.38%) required "
            "to display a pick in 'Top Picks' view.\n"
            "5% = need at least 57.4% probability (52.38% + 5%).\n"
            "Higher = fewer but stronger picks."
        ),
    )
    st.session_state["minimum_edge_threshold"] = new_edge_threshold
    st.caption(
        f"Picks need at least **{new_edge_threshold}% edge** "
        f"(≥{52.38 + new_edge_threshold:.1f}% probability at -110 odds)"
    )

with edge_col2:
    st.info(
        "💡 **What is Edge?**\n\n"
        "Edge = how far your probability is from the **-110 breakeven** (52.38%).\n\n"
        "At standard -110 odds you need to win 52.38% of the time just to break even, "
        "so the true edge is your model probability **minus 52.38%**, not minus 50%.\n\n"
        "- 63% probability = +10.6% edge (63% − 52.38%)\n"
        "- 55% probability = +2.6% edge (55% − 52.38%)\n"
        "- 52% probability = −0.4% edge (no value at -110)\n\n"
        "For sportsbooks with different juice (e.g. -130), the breakeven is higher (~56.5%), "
        "so the displayed edge automatically adjusts to the actual odds.\n\n"
        "We recommend at least **5% edge** to justify a bet."
    )

# ============================================================
# END SECTION: Edge and Filter Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Entry Fee
# ============================================================

st.subheader("💰 Entry Fee")

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
# END SECTION: Entry Fee
# ============================================================

st.divider()

# ============================================================
# SECTION: Sportsbook Platform Settings
# ============================================================

st.subheader("🎰 Sportsbook Platforms")

st.markdown(
    "Select which sportsbooks to include in analysis. "
    "All odds are fetched from The Odds API."
)

current_platforms = st.session_state.get("selected_platforms", list(_PRIMARY_PLATFORMS))

st.markdown("**Primary Sportsbooks**")
new_platforms = st.multiselect(
    "Primary Sportsbooks",
    options=_PRIMARY_PLATFORMS,
    default=[p for p in current_platforms if p in _PRIMARY_PLATFORMS],
    help="Major US sportsbooks — FanDuel, DraftKings, BetMGM, Caesars, Fanatics, ESPN Bet, Hard Rock Bet, BetRivers",
    label_visibility="collapsed",
)

with st.expander("📋 Secondary Sportsbooks", expanded=False):
    secondary_selection = st.multiselect(
        "Secondary Sportsbooks",
        options=_SECONDARY_PLATFORMS,
        default=[p for p in current_platforms if p in _SECONDARY_PLATFORMS],
        help="Additional sportsbooks for broader market coverage",
        label_visibility="collapsed",
    )

combined = new_platforms + secondary_selection
if combined:
    st.session_state["selected_platforms"] = combined
st.caption(f"Active: **{', '.join(st.session_state.get('selected_platforms', []))}**")

# ============================================================
# END SECTION: Sportsbook Platform Settings
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
    "API-NBA Key": "✅ Set" if st.session_state.get("api_nba_key") else "⚠️ Not set",
    "Odds API Key": "✅ Set" if st.session_state.get("odds_api_key") else "⚠️ Not set",
    "Simulation Depth": f"{st.session_state.get('simulation_depth', 1000):,} simulations",
    "Minimum Edge": f"{st.session_state.get('minimum_edge_threshold', 5.0)}%",
    "Entry Fee": f"${st.session_state.get('entry_fee', 10.0):.2f}",
    "Active Sportsbooks": ", ".join(st.session_state.get("selected_platforms", [])),
    "Home Court Boost": f"{st.session_state.get('home_court_boost', 0.025)*100:.1f}%",
    "Blowout Sensitivity": f"{st.session_state.get('blowout_sensitivity', 1.0):.1f}x",
    "Fatigue Sensitivity": f"{st.session_state.get('fatigue_sensitivity', 1.0):.1f}x",
    "Pace Sensitivity": f"{st.session_state.get('pace_sensitivity', 1.0):.1f}x",
}

summary_rows = [{"Setting": k, "Value": v} for k, v in settings_summary.items()]
st.dataframe(summary_rows, width="stretch", hide_index=True)

# Reset ALL settings button
st.divider()
if st.button("🔄 Reset ALL Settings to Defaults", type="secondary"):
    # Clear all settings from session state
    settings_keys_to_clear = [
        "simulation_depth", "minimum_edge_threshold", "entry_fee",
        "selected_platforms", "home_court_boost", "blowout_sensitivity",
        "fatigue_sensitivity", "pace_sensitivity",
        "api_nba_key", "odds_api_key",
    ]
    for key in settings_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.success("All settings reset to defaults! Refresh the page to see changes.")
    st.rerun()

# ============================================================
# END SECTION: Display Current Settings Summary
# ============================================================
