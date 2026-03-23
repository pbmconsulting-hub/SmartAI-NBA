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
    - **🧪 Research Mode**: Maximum simulation depth for detailed analysis.
    
    **Key Settings Explained**
    - **Simulation Depth**: How many Monte Carlo simulations to run (higher = more accurate, slower)
    - **Minimum Edge Threshold**: Only show props where the model finds at least this much edge
    - **Platforms**: Which betting platforms to target (affects payout calculations)
    - **Sensitivity Sliders**: Fine-tune how much weight the model gives to pace, fatigue, blowout risk, etc.
    
    **API Keys**
    - **Odds API Key**: Required for fetching live sportsbook odds
    - **ClearSports API Key**: Required for fetching live NBA stats
    - Keys are stored locally and never sent to our servers
    
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
        "simulation_depth": 2000,
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
        "For DraftKings with different juice (e.g. -130), the breakeven is higher (~56.5%), "
        "so the displayed edge automatically adjusts to the actual odds.\n\n"
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
# SECTION: Goblin / Demon Bet Classification Thresholds
# These control when the engine classifies a pick as a "Goblin"
# (easy-money strong edge) or "Demon" (trap/avoid).
# ============================================================

st.subheader("🧌 Goblin & 👿 Demon Bet Classification")

st.markdown(get_education_box_html(
    "📖 What Are Goblin and Demon Bets?",
    """
    <strong>Goblin Bets</strong> are the highest-conviction picks — the model projection is at
    least 2 standard deviations from the line, probability ≥ 80%, and edge ≥ 25%. These are the
    safest, most confident bets. Raising these thresholds = fewer but higher quality Goblins.<br><br>
    <strong>Demon Bets</strong> are trap picks — they <em>look</em> appealing but have hidden
    structural risks (conflicting forces, hot-streak regression, back-to-back fatigue, high variance
    stats). These are automatically added to the Avoid List.<br><br>
    ⚠️ Only change these if you know what you're doing. Defaults are carefully tuned.
    """
), unsafe_allow_html=True)

with st.expander("⚙️ Goblin / Demon Thresholds (Advanced)", expanded=False):
    _gc1, _gc2, _gc3 = st.columns(3)

    with _gc1:
        _goblin_min_std = st.slider(
            "Goblin: Min Std Devs from Line",
            min_value=1.0, max_value=4.0,
            value=float(st.session_state.get("goblin_min_std_devs", 2.0)),
            step=0.25,
            help="How many standard deviations must the projection be from the line to qualify as a Goblin. Default: 2.0",
        )
        st.session_state["goblin_min_std_devs"] = _goblin_min_std
        st.caption(f"Projection must be ≥ **{_goblin_min_std:.2f}** std devs from line")

    with _gc2:
        _goblin_min_prob = st.slider(
            "Goblin: Min Probability (%)",
            min_value=60.0, max_value=95.0,
            value=float(st.session_state.get("goblin_min_probability_pct", 80.0)),
            step=1.0,
            help="Minimum win probability to classify as Goblin. Default: 80%",
        )
        st.session_state["goblin_min_probability_pct"] = _goblin_min_prob
        st.caption(f"Win probability must be ≥ **{_goblin_min_prob:.0f}%**")

    with _gc3:
        _goblin_min_edge = st.slider(
            "Goblin: Min Edge (%)",
            min_value=10.0, max_value=50.0,
            value=float(st.session_state.get("goblin_min_edge_pct", 25.0)),
            step=1.0,
            help="Minimum edge percentage to classify as Goblin. Default: 25%",
        )
        st.session_state["goblin_min_edge_pct"] = _goblin_min_edge
        st.caption(f"Edge must be ≥ **{_goblin_min_edge:.0f}%**")

    st.divider()
    _dc1, _dc2 = st.columns(2)

    with _dc1:
        _demon_min_conflict = st.slider(
            "Uncertain Risk: Min Conflict Force Ratio",
            min_value=0.5, max_value=1.0,
            value=float(st.session_state.get("demon_conflict_ratio", 0.75)),
            step=0.05,
            help="Ratio of under vs over forces that triggers an Uncertain Risk flag. Default: 0.75 (75% as strong as the winning side). Lower = more uncertain picks detected.",
        )
        st.session_state["demon_conflict_ratio"] = _demon_min_conflict
        st.caption(f"Conflict detected when under-force ≥ **{_demon_min_conflict:.0%}** of over-force")

    with _dc2:
        _demon_regression_pct = st.slider(
            "Uncertain Risk: Regression Line Threshold (%)",
            min_value=110.0, max_value=150.0,
            value=float(st.session_state.get("demon_regression_pct", 125.0)),
            step=5.0,
            help="If the prop line is this % above season average, it's flagged as a Regression Risk. Default: 125%",
        )
        st.session_state["demon_regression_pct"] = _demon_regression_pct
        st.caption(f"Line ≥ **{_demon_regression_pct:.0f}%** of season avg → Regression Risk")

    _gc_reset_col, _ = st.columns([1, 2])
    with _gc_reset_col:
        if st.button("🔄 Reset Goblin/Uncertain Risk Thresholds to Defaults"):
            for _k in ("goblin_min_std_devs", "goblin_min_probability_pct", "goblin_min_edge_pct",
                       "demon_conflict_ratio", "demon_regression_pct"):
                if _k in st.session_state:
                    del st.session_state[_k]
            st.success("Goblin/Uncertain Risk thresholds reset to defaults!")
            st.rerun()

# ============================================================
# END SECTION: Goblin / Demon Bet Classification Thresholds
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
    "📖 API Keys for Live Data",
    """
    <strong>The Odds API</strong> provides player props from all major US sportsbooks 
    (DraftKings, FanDuel, BetMGM, Caesars, etc.) in one unified call. Also provides 
    game-level moneylines, spreads, and totals from 15+ bookmakers — used for consensus 
    Vegas line calculation and market movement tracking.
    <a href="https://the-odds-api.com" target="_blank" style="color:#00f0ff;">Free tier: 500 req/month</a>.<br><br>
    <strong>ClearSports API</strong> provides NBA games, player stats, team stats, injuries, 
    rosters, live scores, standings, and player news.
    <a href="https://clearsportsapi.com" target="_blank" style="color:#00f0ff;">Free tier: 1,000 req/month</a>.<br><br>
    Keys are stored only in this browser session and never saved to disk.
    Keys can also be pre-configured via <code>.streamlit/secrets.toml</code> or
    the Streamlit Cloud Secrets dashboard so they load automatically on startup.
    """
), unsafe_allow_html=True)

with st.expander("🔑 Configure The Odds API Key (Props from all sportsbooks)", expanded=False):
    st.markdown(
        "Get your free API key at "
        "[https://the-odds-api.com](https://the-odds-api.com) — free tier gives you "
        "500 requests/month. Covers DraftKings, FanDuel, BetMGM, Caesars, and 15+ more."
    )

    current_key = st.session_state.get("odds_api_key", "")
    if current_key:
        masked = current_key[:4] + "••••••••" + current_key[-4:] if len(current_key) > 8 else "••••••••"
        st.success(f"✅ Odds API key configured: `{masked}`")
    else:
        st.info("ℹ️ No Odds API key set. Player props will be unavailable.")

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
        if st.button("💾 Save Odds API Key", width="stretch"):
            st.session_state["odds_api_key"] = new_key.strip()
            if new_key.strip():
                st.success("✅ Odds API key saved for this session!")
            else:
                st.info("API key cleared.")
            st.rerun()
    with col_clear_key:
        if st.button("🗑️ Clear Odds API Key", width="stretch"):
            st.session_state["odds_api_key"] = ""
            st.info("API key cleared.")
            st.rerun()

with st.expander("🔑 Configure ClearSports API Key (Games, Stats, Injuries, Rosters)", expanded=False):
    st.markdown(
        "Get your free API key at "
        "[https://clearsportsapi.com](https://clearsportsapi.com) — free tier gives you "
        "1,000 requests/month, which is plenty for daily data updates."
    )

    cs_key = st.session_state.get("clearsports_api_key", "")
    if cs_key:
        masked_cs = cs_key[:4] + "••••••••" + cs_key[-4:] if len(cs_key) > 8 else "••••••••"
        st.success(f"✅ ClearSports API key configured: `{masked_cs}`")
    else:
        st.info("ℹ️ No ClearSports API key set. Game/player/team data updates will be limited.")

    new_cs_key = st.text_input(
        "ClearSports API Key",
        value=cs_key,
        type="password",
        placeholder="e.g., cs_live_abc123...",
        help="Your ClearSports API key from clearsportsapi.com. Stored in this session only.",
        key="clearsports_api_key_input",
    )

    cs_col1, cs_col2 = st.columns([1, 1])
    with cs_col1:
        if st.button("💾 Save ClearSports Key", width="stretch"):
            st.session_state["clearsports_api_key"] = new_cs_key.strip()
            if new_cs_key.strip():
                st.success("✅ ClearSports API key saved for this session!")
            else:
                st.info("ClearSports API key cleared.")
            st.rerun()
    with cs_col2:
        if st.button("🗑️ Clear ClearSports Key", width="stretch"):
            st.session_state["clearsports_api_key"] = ""
            st.info("ClearSports API key cleared.")
            st.rerun()

# ── API Connection Status & Quota ──────────────────────────────────────────
# Shows live connection status for both APIs and remaining Odds API quota.
with st.expander("📊 API Connection Status & Usage", expanded=False):
    _status_col_a, _status_col_b = st.columns(2)

    # ── Odds API Status ──
    with _status_col_a:
        st.markdown("**The Odds API**")
        _odds_key = st.session_state.get("odds_api_key", "")
        if _odds_key:
            try:
                from data.odds_api_client import get_odds_api_usage
                _usage = get_odds_api_usage()
                _remaining = _usage.get("requests_remaining")
                _used = _usage.get("requests_used")
                _updated = _usage.get("updated_at")
                if _remaining is not None:
                    _pct_used = round(_used / max(_used + _remaining, 1) * 100) if _used is not None else 0
                    _bar_color = "#00ff9d" if _remaining > 100 else ("#ffd700" if _remaining > 20 else "#ff4444")
                    st.markdown(
                        f'<div style="background:#14192b;border-radius:8px;padding:12px 14px;'
                        f'border:1px solid rgba(0,240,255,0.15);">'
                        f'<div style="font-weight:700;color:#c0d0e8;margin-bottom:4px;">✅ Connected</div>'
                        f'<div style="color:{_bar_color};font-size:1.1rem;font-weight:700;">'
                        f'{_remaining:,} requests remaining</div>'
                        f'<div style="height:6px;background:#1a2035;border-radius:3px;margin:6px 0;">'
                        f'<div style="height:6px;width:{100-_pct_used}%;background:{_bar_color};'
                        f'border-radius:3px;"></div></div>'
                        f'<div style="color:#8b949e;font-size:0.75rem;">'
                        f'{_used if _used is not None else "?"} used · '
                        f'Updated: {_updated[:16] if _updated else "pending first request"}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div style="background:#14192b;border-radius:8px;padding:12px 14px;'
                        'border:1px solid rgba(0,240,255,0.15);">'
                        '<div style="font-weight:700;color:#ffd700;">🔑 Key set — quota loads after first API call</div>'
                        '<div style="color:#8b949e;font-size:0.78rem;margin-top:4px;">'
                        'Run a data fetch or load tonight\'s games to check quota.</div></div>',
                        unsafe_allow_html=True,
                    )
            except ImportError:
                st.info("Odds API client not available.")
        else:
            st.markdown(
                '<div style="background:#14192b;border-radius:8px;padding:12px 14px;'
                'border:1px solid rgba(255,107,107,0.3);">'
                '<div style="font-weight:700;color:#ff6b6b;">❌ Not configured</div>'
                '<div style="color:#8b949e;font-size:0.78rem;margin-top:4px;">'
                'Set your Odds API key above to enable player props and market data.</div></div>',
                unsafe_allow_html=True,
            )

    # ── ClearSports API Status ──
    with _status_col_b:
        st.markdown("**ClearSports API**")
        _cs_key = st.session_state.get("clearsports_api_key", "")
        if _cs_key:
            st.markdown(
                '<div style="background:#14192b;border-radius:8px;padding:12px 14px;'
                'border:1px solid rgba(0,240,255,0.15);">'
                '<div style="font-weight:700;color:#c0d0e8;">✅ Connected</div>'
                '<div style="color:#9ae6b4;font-size:0.85rem;margin-top:4px;">'
                'Games · Players · Teams · Injuries · Scores · Standings · News</div>'
                '<div style="color:#8b949e;font-size:0.75rem;margin-top:4px;">'
                'All ClearSports endpoints active</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="background:#14192b;border-radius:8px;padding:12px 14px;'
                'border:1px solid rgba(255,107,107,0.3);">'
                '<div style="font-weight:700;color:#ff6b6b;">❌ Not configured</div>'
                '<div style="color:#8b949e;font-size:0.78rem;margin-top:4px;">'
                'Set your ClearSports API key above to enable game data, stats, and injuries.</div></div>',
                unsafe_allow_html=True,
            )

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
    "Odds API Key": "Configured ✓" if st.session_state.get("odds_api_key", "") else "Not set",
    "ClearSports API Key": "Configured ✓" if st.session_state.get("clearsports_api_key", "") else "Not set",
    "Goblin Min Std Devs": f"{st.session_state.get('goblin_min_std_devs', 2.0):.2f}σ",
    "Goblin Min Probability": f"{st.session_state.get('goblin_min_probability_pct', 80.0):.0f}%",
    "Goblin Min Edge": f"{st.session_state.get('goblin_min_edge_pct', 25.0):.0f}%",
    "Uncertain: Conflict Ratio": f"{st.session_state.get('demon_conflict_ratio', 0.75):.0%}",
    "Uncertain: Regression Threshold": f"{st.session_state.get('demon_regression_pct', 125.0):.0f}%",
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
        "fetch_prizepicks_enabled", "fetch_underdog_enabled", "fetch_draftkings_enabled",
        "goblin_min_std_devs", "goblin_min_probability_pct", "goblin_min_edge_pct",
        "demon_conflict_ratio", "demon_regression_pct",
    ]
    for key in settings_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.success("All settings reset to defaults! Refresh the page to see changes.")
    st.rerun()

# ============================================================
# END SECTION: Display Current Settings Summary
# ============================================================
