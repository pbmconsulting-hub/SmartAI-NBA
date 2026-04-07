# ============================================================
# FILE: pages/6_🧬_Entry_Builder.py
# PURPOSE: Build optimal parlay entries for sportsbook platforms
#          (PrizePicks, Underdog Fantasy, DraftKings Pick6). Calculates EV.
# CONNECTS TO: entry_optimizer.py, analysis results in session
# CONCEPTS COVERED: Parlays, EV, combinatorics, entry building
# ============================================================

import streamlit as st  # Main UI framework
import logging
import html as _html_eb  # HTML escaping – single import for the whole file
import datetime as _dt
import math as _math_eb

# Import our entry optimizer engine
from engine.entry_optimizer import (
    build_optimal_entries,
    calculate_entry_expected_value,
    format_ev_display,
    calculate_correlation_risk,
    identify_weakest_link,
    suggest_swap,
    SPORTSBOOK_PARLAY_TABLE,
    PLATFORM_FLEX_TABLES,
    optimize_play_type,
    build_optimal_entries_with_play_type,
    calculate_flex_vs_power_breakeven,
)

try:
    from engine.bankroll import calculate_kelly_fraction, get_bankroll_allocation, get_session_risk_summary  # F5
except ImportError:
    calculate_kelly_fraction = None
    get_bankroll_allocation = None
    get_session_risk_summary = None

try:
    from engine.platform_line_compare import compare_platform_lines  # F3
except ImportError:
    compare_platform_lines = None

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

# ── Global Settings Popover (accessible from sidebar) ─────────
from utils.components import render_global_settings, inject_joseph_floating, render_joseph_hero_banner
with st.sidebar:
    render_global_settings()
st.session_state["joseph_page_context"] = "page_entry_builder"
inject_joseph_floating()

# ── Premium Gate ───────────────────────────────────────────────
from utils.premium_gate import premium_gate
if not premium_gate("Entry Builder"):
    st.stop()
# ── End Premium Gate ───────────────────────────────────────────

if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []

st.title("🧬 Entry Builder")
st.markdown("Build optimal parlay entries with maximum Expected Value (EV).")

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Entry Builder — Building Optimal Parlays
    
    **Concepts:**
    - **Power Play**: All legs must hit to win (higher payout, higher risk)
    - **Flex Play**: Can lose 1 leg and still win a reduced payout
    - **EV (Expected Value)**: Average profit/loss per dollar wagered (+EV = profitable long-term)
    
    **How to Build an Entry:**
    1. Select picks from Neural Analysis (use the checkboxes on prop cards)
    2. Choose your entry size (2-6 legs)
    3. Set your entry fee amount
    4. Click "Build Optimal Entry" to see recommended combos
    
    **Reading EV:**
    - Positive EV (+X%) = profitable bet long-term
    - Negative EV = you lose money long-term on average
    - Higher confidence picks dramatically improve EV
    
    💡 **Pro Tips:**
    - 2-3 leg Power Plays have the best EV for high-confidence picks
    - Never include picks below Silver tier in a parlay
    - Flex entries are safer but pay less — use for 4-6 leg entries
    """)

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

# ── Adjustable Edge / Confidence Threshold Sliders (#14) ──────
_thresh_c1, _thresh_c2 = st.columns(2)
with _thresh_c1:
    _edge_threshold = st.slider(
        "Min Edge Threshold (%)",
        min_value=0.0, max_value=15.0,
        value=st.session_state.get("eb_edge_threshold", 3.0),
        step=0.5,
        key="eb_edge_threshold",
        help="Only include picks with absolute edge ≥ this value.",
    )
with _thresh_c2:
    _conf_threshold = st.slider(
        "Min Confidence Threshold",
        min_value=0, max_value=90,
        value=int(st.session_state.get("eb_conf_threshold", 40)),
        step=5,
        key="eb_conf_threshold",
        help="Only include picks with confidence ≥ this value.",
    )

# Filter to only non-avoided picks with meaningful edge
qualifying_picks = [
    r for r in analysis_results
    if abs(r.get("edge_percentage", 0)) >= _edge_threshold
    and not r.get("should_avoid", False)
    and r.get("confidence_score", 0) >= _conf_threshold
]

st.info(
    f"📋 **{len(qualifying_picks)} qualifying picks** available "
    f"(from {len(analysis_results)} total analyzed, edge ≥ {_edge_threshold}%, confidence ≥ {_conf_threshold})"
)

if len(qualifying_picks) < 2:
    st.error(
        "Need at least 2 qualifying picks to build entries. "
        "Lower the edge threshold in Settings or add more props."
    )
    st.stop()

# ── 🎯 Strongly Suggested Parlays (auto-populated at top) ────────
_top_picks = sorted(
    [r for r in qualifying_picks
     if not r.get("player_is_out", False)
     and abs(r.get("edge_percentage", 0)) >= 5.0],
    key=lambda r: r.get("confidence_score", 0),
    reverse=True,
)
if len(_top_picks) >= 2:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#0f1a2e,#14192b);'
        'border:2px solid #ff5e00;border-radius:10px;padding:14px 18px;margin-bottom:16px;">'
        '<h3 style="color:#ff5e00;margin:0 0 4px;font-family:Orbitron,sans-serif;">🎯 Strongly Suggested Parlays</h3>'
        '<p style="color:#a0b4d0;font-size:0.84rem;margin:0;">Auto-populated from tonight\'s highest-edge picks</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    _PARLAY_CONFIGS = [
        (2, "⭐ Best 2-Leg Parlay"),
        (3, "⭐⭐ Best 3-Leg Parlay"),
        (4, "⭐⭐⭐ Best 4-Leg Parlay"),
        (5, "⭐⭐⭐⭐ Best 5-Leg Parlay"),
    ]
    for _n, _lbl in _PARLAY_CONFIGS:
        if len(_top_picks) < _n:
            continue
        _legs = _top_picks[:_n]
        _avg_c = round(sum(r.get("confidence_score", 0) for r in _legs) / _n, 1)
        _combined = 1.0
        for _r in _legs:
            _combined *= max(0.01, min(0.99, _r.get("confidence_score", 50) / 100.0))
        _combined_pct = round(_combined * 100, 1)
        _avg_edge = round(sum(r.get("edge_percentage", 0) for r in _legs) / _n, 1)
        _picks_str = " + ".join(
            f"{_html_eb.escape(r.get('player_name',''))} "
            f"{r.get('direction','OVER')} {r.get('line','')} {r.get('stat_type','').title()}"
            for r in _legs
        )
        st.markdown(
            f'<div style="background:#14192b;border-radius:8px;padding:12px 16px;'
            f'margin-bottom:10px;border-left:4px solid #ff5e00;'
            f'box-shadow:0 0 10px rgba(255,94,0,0.25);">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="color:#ff5e00;font-weight:700;">{_lbl}</span>'
            f'<span style="background:#ff5e00;color:#0a0f1a;padding:2px 8px;border-radius:4px;'
            f'font-size:0.78rem;font-weight:700;">SAFE {_avg_c}/100</span>'
            f'</div>'
            f'<div style="color:#c0d0e8;font-size:0.85rem;margin-top:6px;">{_picks_str}</div>'
            f'<div style="color:#8b949e;font-size:0.78rem;margin-top:4px;">'
            f'Combined prob: {_combined_pct:.1f}% · Avg edge: {_avg_edge:+.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.divider()

# ============================================================
# END SECTION: Check for Analysis Results
# ============================================================

# ============================================================
# SECTION: Entry Builder Controls
# ============================================================

st.subheader("⚙️ Entry Settings")

settings_col1, settings_col2, settings_col3 = st.columns([2, 1, 1])

with settings_col1:
    selected_platform = st.selectbox(
        "Platform",
        options=["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"],
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

settings_col4, settings_col5 = st.columns([1, 1])

with settings_col4:
    session_budget = st.number_input(
        "Session Budget ($)",
        min_value=0.0,
        max_value=10000.0,
        value=st.session_state.get("session_budget", 50.0),
        step=10.0,
        help="Total amount you're willing to spend this session. Set to 0 to disable.",
    )
    st.session_state["session_budget"] = session_budget

with settings_col5:
    max_entries = st.number_input(
        "Show Top N Entries",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        help="How many top entries to display?",
    )

# ── Kelly Bankroll Inputs ─────────────────────────────────────────
_kelly_col1, _kelly_col2 = st.columns(2)
with _kelly_col1:
    bankroll_amount = st.number_input(
        "💰 Your Bankroll ($)",
        min_value=10.0,
        max_value=100000.0,
        value=float(st.session_state.get("bankroll_amount", 500.0)),
        step=50.0,
        help="Total bankroll for Kelly Criterion sizing",
    )
    st.session_state["bankroll_amount"] = bankroll_amount
with _kelly_col2:
    kelly_mode = st.selectbox(
        "Kelly Sizing Mode",
        options=["quarter", "half", "eighth", "full"],
        index=0,
        help="Quarter Kelly = conservative (recommended). Full Kelly = maximum growth, high risk.",
    )

# ── Session Budget Summary ────────────────────────────────────────
if session_budget > 0 and entry_fee > 0:
    _max_affordable = int(session_budget // entry_fee)
    _budget_pct = min(100, round(_max_affordable / max(max_entries, 1) * 100))
    _budget_color = "#00ff9d" if _max_affordable >= max_entries else ("#ffcc00" if _max_affordable > 0 else "#ff4444")
    st.markdown(
        f'<div style="background:#14192b;border-radius:6px;padding:10px 16px;'
        f'border-left:3px solid {_budget_color};margin-top:4px;">'
        f'<span style="color:#8a9bb8;font-size:0.82rem;">💰 Budget:</span> '
        f'<strong style="color:{_budget_color};">${session_budget:.0f}</strong> total · '
        f'<strong style="color:#c0d0e8;">{_max_affordable}</strong> entries @ ${entry_fee:.0f} each · '
        f'<span style="color:{_budget_color};">'
        f'{"✅ Enough for " + str(min(_max_affordable, int(max_entries))) + " entries" if _max_affordable >= 1 else "⚠️ Budget too low for even 1 entry"}'
        f'</span></div>',
        unsafe_allow_html=True,
    )
    if int(max_entries) > _max_affordable > 0:
        st.warning(
            f"⚠️ Budget allows **{_max_affordable}** entries at ${entry_fee:.0f} each, "
            f"but you requested {int(max_entries)}. Consider raising your budget or lowering entry fee."
        )

# ── Lock/Unlock Legs ─────────────────────────────────────────────
if "locked_legs" not in st.session_state:
    st.session_state["locked_legs"] = set()

with st.expander("🔒 Lock / Unlock Legs (force picks into every entry)", expanded=False):
    st.markdown(
        "Locked legs are **forced into every generated entry**. "
        "Use this to anchor your highest-conviction picks."
    )
    _lock_names = [f"{p.get('player_name','')} — {p.get('stat_type','').title()} {p.get('direction','OVER')} {p.get('line',0)}"
                   for p in qualifying_picks[:20]]
    _locked = st.multiselect(
        "Select legs to lock:",
        options=_lock_names,
        default=[n for n in _lock_names if n.split(" — ")[0] in st.session_state.get("locked_legs", set())],
        key="locked_legs_select",
    )
    # Store locked player names
    st.session_state["locked_legs"] = {n.split(" — ")[0] for n in _locked}
    if _locked:
        st.success(f"🔒 {len(_locked)} leg(s) locked into every entry.")

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

    # ── Tier Filter & Bet Classification Filter ───────────────────────────
    _eb_filter_col1, _eb_filter_col2 = st.columns(2)
    with _eb_filter_col1:
        _eb_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[],
            key="eb_tier_filter",
            help="Show only picks matching the selected tiers. Leave empty to show all tiers.",
        )
    with _eb_filter_col2:
        _eb_bet_type_filter = st.multiselect(
            "Bet Classification",
            ["50/50 — Standard Line", "⚡ Normal"],
            default=[],
            key="eb_bet_type_filter",
            help="Filter by bet classification. '50/50' = standard line. 'Normal' = standard play.",
        )
    _filtered_picks = selected_picks
    if _eb_tier_filter:
        _eb_tier_names = [t.split(" ")[0] for t in _eb_tier_filter]
        _filtered_picks = [p for p in _filtered_picks if p.get("tier") in _eb_tier_names]
    if _eb_bet_type_filter:
        _eb_bt_map = {
            "50/50 — Standard Line":   "50_50",
            "⚡ Normal":               "normal",
        }
        _eb_bt_values = {_eb_bt_map[t] for t in _eb_bet_type_filter if t in _eb_bt_map}
        _filtered_picks = [p for p in _filtered_picks if p.get("bet_type", "normal") in _eb_bt_values]


    # Sort options
    sort_by = st.selectbox("Sort by:", ["Confidence (highest first)", "Probability", "Edge"], key="selected_sort")

    # Sort the picks
    if sort_by == "Confidence (highest first)":
        selected_picks_sorted = sorted(_filtered_picks, key=lambda x: x.get("confidence_score", 0), reverse=True)
    elif sort_by == "Probability":
        selected_picks_sorted = sorted(_filtered_picks, key=lambda x: abs(x.get("probability_over", 0.5) - 0.5), reverse=True)
    else:
        selected_picks_sorted = sorted(_filtered_picks, key=lambda x: abs(x.get("edge_percentage", 0)), reverse=True)
    
    # Show picks as styled mini-cards (#3)
    _tier_badge_colors = {
        "Platinum": "#00f0ff", "Gold": "#ffd700",
        "Silver": "#c0c0c0", "Bronze": "#cd7f32",
    }
    picks_to_include = []
    for i, pick in enumerate(selected_picks_sorted):
        direction = pick.get("direction", "OVER")
        prob = pick.get("probability_over", 0.5)
        display_prob = (1.0 - prob) * 100 if direction == "UNDER" else prob * 100
        tier_emoji = pick.get("tier_emoji", "🥉")
        tier_name = pick.get("tier", "Bronze")
        pick_team = pick.get("player_team", pick.get("team", ""))
        pick_edge = pick.get("edge_percentage", 0)
        pick_conf = pick.get("confidence_score", 50)
        _badge_c = _tier_badge_colors.get(tier_name, "#cd7f32")
        _dir_arrow = "⬆️" if direction == "OVER" else "⬇️"
        _prob_c = "#00ff9d" if display_prob >= 60 else ("#ffcc00" if display_prob >= 55 else "#ff6b6b")
        _conf_pct = min(pick_conf, 100)
        _conf_bar = f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:6px;width:80px;display:inline-block;vertical-align:middle;">' \
                    f'<div style="background:{_prob_c};height:100%;border-radius:3px;width:{_conf_pct}%;"></div></div>'

        col_check, col_card = st.columns([0.06, 0.94])
        with col_check:
            include = st.checkbox("", value=True, key=f"pick_check_{i}_{pick.get('player_name','')}")
        with col_card:
            st.markdown(
                f'<div style="background:#14192b;border-radius:10px;padding:10px 14px;margin-bottom:4px;'
                f'border-left:4px solid {_badge_c};display:flex;justify-content:space-between;'
                f'align-items:center;flex-wrap:wrap;gap:6px;">'
                # Left: player + team + stat
                f'<div style="flex:1;min-width:180px;">'
                f'<span style="color:#e2e8f0;font-weight:700;font-size:0.92rem;">'
                f'{_html_eb.escape(pick.get("player_name",""))}</span>'
                f'<span style="color:#64748b;font-size:0.76rem;margin-left:6px;">{_html_eb.escape(pick_team)}</span><br>'
                f'<span style="color:#94a3b8;font-size:0.82rem;">'
                f'{_dir_arrow} {direction} {pick.get("line",0)} {pick.get("stat_type","").title()}</span>'
                f'</div>'
                # Middle: tier badge
                f'<div style="text-align:center;">'
                f'<span style="background:{_badge_c};color:#0a0f1a;padding:2px 8px;border-radius:4px;'
                f'font-size:0.72rem;font-weight:700;">{tier_emoji} {tier_name}</span>'
                f'</div>'
                # Right: prob + edge + confidence gauge
                f'<div style="text-align:right;min-width:120px;">'
                f'<span style="color:{_prob_c};font-weight:700;font-size:0.92rem;">{display_prob:.0f}%</span>'
                f'<span style="color:#8a9bb8;font-size:0.76rem;margin-left:6px;">Edge {pick_edge:+.1f}%</span><br>'
                f'{_conf_bar}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        
        if include:
            picks_to_include.append(pick)
    
    if len(picks_to_include) >= 2:
        st.divider()
        st.subheader("💰 Quick EV Calculation for Selected Picks")
        
        quick_platform = st.selectbox("Platform for EV calc:", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"], key="quick_platform")
        quick_fee = st.number_input("Entry Fee ($):", min_value=1.0, value=10.0, key="quick_fee")
        
        selected_probs = [
            p.get("probability_over", 0.5) if p.get("direction") == "OVER"
            else 1.0 - p.get("probability_over", 0.5)
            for p in picks_to_include
        ]
        
        platform_flex_table = PLATFORM_FLEX_TABLES.get(quick_platform, SPORTSBOOK_PARLAY_TABLE)
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

            # ── EV Gauge / Speedometer (#4) ─────────────────────────
            _ev_roi_raw = quick_ev.get("return_on_investment", 0) * 100  # as percentage
            _gauge_val = max(-50, min(50, _ev_roi_raw))
            _gauge_color = "#00ff9d" if _gauge_val >= 0 else "#ff4444"
            # Simple SVG radial gauge
            _angle_min, _angle_max = -135, 135  # sweep range
            _needle_angle = _angle_min + (_gauge_val + 50) / 100 * (_angle_max - _angle_min)
            _rad = _math_eb.radians(_needle_angle)
            _nx = 100 + 60 * _math_eb.cos(_rad - _math_eb.pi / 2)
            _ny = 110 + 60 * _math_eb.sin(_rad - _math_eb.pi / 2)
            st.markdown(
                f'<div style="text-align:center;margin:8px 0;">'
                f'<svg width="200" height="130" viewBox="0 0 200 140">'
                # Background arc
                f'<path d="M 20 110 A 80 80 0 0 1 180 110" fill="none" stroke="#1e293b" stroke-width="14" stroke-linecap="round"/>'
                # Red zone (-50% to 0)
                f'<path d="M 20 110 A 80 80 0 0 1 100 30" fill="none" stroke="rgba(255,68,68,0.3)" stroke-width="14" stroke-linecap="round"/>'
                # Green zone (0 to +50%)
                f'<path d="M 100 30 A 80 80 0 0 1 180 110" fill="none" stroke="rgba(0,255,157,0.3)" stroke-width="14" stroke-linecap="round"/>'
                # Needle
                f'<line x1="100" y1="110" x2="{_nx:.1f}" y2="{_ny:.1f}" stroke="{_gauge_color}" stroke-width="3" stroke-linecap="round"/>'
                f'<circle cx="100" cy="110" r="5" fill="{_gauge_color}"/>'
                # Labels
                f'<text x="18" y="130" fill="#ff6b6b" font-size="9" font-family="JetBrains Mono,monospace">-50%</text>'
                f'<text x="90" y="22" fill="#94a3b8" font-size="9" font-family="JetBrains Mono,monospace">0%</text>'
                f'<text x="165" y="130" fill="#00ff9d" font-size="9" font-family="JetBrains Mono,monospace">+50%</text>'
                # Value
                f'<text x="100" y="100" fill="{_gauge_color}" font-size="16" font-weight="800" text-anchor="middle"'
                f' font-family="JetBrains Mono,monospace">{_gauge_val:+.1f}%</text>'
                f'<text x="100" y="115" fill="#64748b" font-size="8" text-anchor="middle" font-family="Inter,sans-serif">EV ROI</text>'
                f'</svg></div>',
                unsafe_allow_html=True,
            )

            # Phase 3: DFS Flex Breakeven Thresholds
            _eb_n_picks = len(picks_to_include)
            _eb_dfs_results = [p for p in picks_to_include if p.get("dfs_parlay_ev")]
            if _eb_dfs_results and _eb_n_picks >= 3:
                try:
                    from engine.odds_engine import calculate_dfs_breakeven_probability
                    _eb_plat = quick_platform.replace(" (Flex)", "").replace(" (Power)", "")
                    _eb_be = calculate_dfs_breakeven_probability(_eb_plat, min(_eb_n_picks, 6))
                    _eb_be_prob = _eb_be.get("breakeven_per_leg", 0.5) * 100
                    _eb_payout = _eb_be.get("all_hit_payout", 1.0)
                    # Per-leg average probability
                    _eb_avg_leg = (sum(selected_probs) / len(selected_probs) * 100) if selected_probs else 50
                    _eb_beats = _eb_avg_leg > _eb_be_prob
                    _eb_color = "#00ff9d" if _eb_beats else "#ff5e00"
                    _eb_icon = "✅" if _eb_beats else "⚠️"
                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,#070A13,#0F172A);'
                        f'border:1px solid rgba(0,255,157,0.2);border-radius:8px;padding:8px 14px;margin:8px 0;">'
                        f'<span style="color:#64748b;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;">'
                        f'📈 DFS {_eb_plat} · {_eb_n_picks}-Pick Flex</span><br>'
                        f'<span style="color:{_eb_color};font-size:0.88rem;font-weight:800;'
                        f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;\">"
                        f'{_eb_icon} Avg leg: {_eb_avg_leg:.0f}%  ·  Breakeven: {_eb_be_prob:.0f}%</span>'
                        f'<span style="color:#475569;font-size:0.65rem;margin-left:8px;">'
                        f'({_eb_payout:.1f}× payout)</span></div>',
                        unsafe_allow_html=True,
                    )
                except (ImportError, Exception):
                    pass
            
            # Correlation check
            corr_risk = calculate_correlation_risk(picks_to_include)
            if corr_risk.get("warnings"):
                for w in corr_risk["warnings"]:
                    st.warning(w)

            # ── Correlation Matrix Heatmap (#11) ──────────────────────
            _corr_matrix = corr_risk.get("correlation_matrix")
            _game_groups = corr_risk.get("game_groups", {})
            if _game_groups and len(picks_to_include) >= 2:
                _n_p = len(picks_to_include)
                _p_names = [p.get("player_name", "?")[:10] for p in picks_to_include]
                # Build simple pairwise matrix (same-game = 1.0, diff-game = 0.0)
                if _corr_matrix and len(_corr_matrix) == _n_p:
                    _cm = _corr_matrix
                else:
                    _cm = [[0.0] * _n_p for _ in range(_n_p)]
                    _game_lookup = {}
                    for gk, pnames in _game_groups.items():
                        for pn in pnames:
                            _game_lookup[pn] = gk
                    for _ri in range(_n_p):
                        for _ci in range(_n_p):
                            if _ri == _ci:
                                _cm[_ri][_ci] = 1.0
                            else:
                                _rn = picks_to_include[_ri].get("player_name", "")
                                _cn = picks_to_include[_ci].get("player_name", "")
                                if _game_lookup.get(_rn) and _game_lookup.get(_rn) == _game_lookup.get(_cn):
                                    _cm[_ri][_ci] = 0.7
                with st.expander("🔥 Correlation Heatmap", expanded=False):
                    _hm_size = max(180, _n_p * 44)
                    _cell = _hm_size // (_n_p + 1)
                    _svg_rects = ""
                    for _ri in range(_n_p):
                        for _ci in range(_n_p):
                            _v = _cm[_ri][_ci]
                            _fill = f"rgba(255,94,0,{min(_v, 1.0):.2f})" if _v > 0.1 else "rgba(148,163,184,0.06)"
                            if _ri == _ci:
                                _fill = "rgba(0,255,157,0.2)"
                            _rx = (_ci + 1) * _cell
                            _ry = (_ri + 1) * _cell
                            _svg_rects += (
                                f'<rect x="{_rx}" y="{_ry}" width="{_cell-2}" height="{_cell-2}" '
                                f'rx="3" fill="{_fill}"/>'
                                f'<text x="{_rx + _cell//2}" y="{_ry + _cell//2 + 4}" '
                                f'fill="#c0d0e8" font-size="9" text-anchor="middle" '
                                f'font-family="JetBrains Mono,monospace">{_v:.1f}</text>'
                            )
                    # Labels
                    _svg_labels = ""
                    for _li, _ln in enumerate(_p_names):
                        _lx = (_li + 1) * _cell + _cell // 2
                        _svg_labels += f'<text x="{_lx}" y="{_cell - 4}" fill="#94a3b8" font-size="8" text-anchor="middle" font-family="Inter,sans-serif">{_html_eb.escape(_ln)}</text>'
                        _ly = (_li + 1) * _cell + _cell // 2 + 3
                        _svg_labels += f'<text x="{_cell - 4}" y="{_ly}" fill="#94a3b8" font-size="8" text-anchor="end" font-family="Inter,sans-serif">{_html_eb.escape(_ln)}</text>'
                    _total_svg = (_n_p + 1) * _cell + 4
                    st.markdown(
                        f'<div style="overflow-x:auto;"><svg width="{_total_svg}" height="{_total_svg}">{_svg_labels}{_svg_rects}</svg></div>',
                        unsafe_allow_html=True,
                    )

            # Weakest link + Swap button (#12)
            weakest = identify_weakest_link(picks_to_include)
            if weakest:
                weakest_prob = weakest.get("probability_over", 0.5) if weakest.get("direction") == "OVER" else 1.0 - weakest.get("probability_over", 0.5)
                if weakest_prob < 0.60:
                    _swap_candidate = suggest_swap(weakest, qualifying_picks, picks_to_include)
                    _swap_msg = f"⚠️ Weakest leg: **{weakest.get('player_name','')}** ({weakest_prob*100:.0f}%)"
                    if _swap_candidate:
                        _swap_msg += f" — {_swap_candidate.get('swap_reason', '')}"
                    st.warning(_swap_msg)
                    if _swap_candidate:
                        if st.button(
                            f"🔄 Swap Now: Replace with {_swap_candidate.get('player_name','')}",
                            key="swap_weakest_btn",
                        ):
                            _new_picks = [
                                _swap_candidate if p.get("player_name") == weakest.get("player_name") and p.get("stat_type") == weakest.get("stat_type")
                                else p
                                for p in st.session_state.get("selected_picks", [])
                            ]
                            st.session_state["selected_picks"] = _new_picks
                            st.rerun()

            # ── Live Ticket Preview (#2) ──────────────────────────────
            _live_legs = ""
            for _lp in picks_to_include:
                _lp_dir = _lp.get("direction", "OVER")
                _lp_name = _html_eb.escape(str(_lp.get("player_name", "?")))
                _lp_team = _html_eb.escape(str(_lp.get("player_team", _lp.get("team", ""))))
                _lp_stat = _html_eb.escape(str(_lp.get("stat_type", "")).title())
                _lp_line = _lp.get("line", 0)
                _lp_tier = _lp.get("tier", "Bronze")
                _lp_edge = _lp.get("edge_percentage", 0)
                _lp_prob = _lp.get("probability_over", 0.5)
                _lp_prob_dir = (_lp_prob if _lp_dir == "OVER" else 1.0 - _lp_prob) * 100
                _lp_tc = _tier_badge_colors.get(_lp_tier, "#94a3b8")
                _lp_pc = "#00ff9d" if _lp_prob_dir >= 60 else ("#ffcc00" if _lp_prob_dir >= 55 else "#ff6b6b")
                _live_legs += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:6px 12px;border-bottom:1px solid rgba(148,163,184,0.08);">'
                    f'<div><span style="color:#e2e8f0;font-weight:600;font-size:0.82rem;">{_lp_name}</span>'
                    f'<span style="color:#64748b;font-size:0.70rem;margin-left:6px;">{_lp_team}</span><br>'
                    f'<span style="color:#94a3b8;font-size:0.74rem;">{_lp_stat} '
                    f'<span style="color:{"#00f0ff" if _lp_dir == "OVER" else "#ff5e00"};">'
                    f'{"MORE" if _lp_dir == "OVER" else "LESS"}</span> {_lp_line}</span></div>'
                    f'<div style="text-align:right;">'
                    f'<span style="color:{_lp_tc};font-size:0.70rem;font-weight:700;">{_lp_tier}</span>'
                    f'<span style="color:{_lp_pc};font-size:0.78rem;font-weight:700;margin-left:6px;">{_lp_prob_dir:.0f}%</span></div></div>'
                )
            _live_ev_val = quick_ev.get("return_on_investment", 0) * 100
            _live_ev_c = "#00ff9d" if _live_ev_val >= 0 else "#ff5e00"
            _live_ev_s = "+" if _live_ev_val > 0 else ""
            _combined_prob_live = 1.0
            for _sp in selected_probs:
                _combined_prob_live *= _sp
            st.markdown(
                f'<div style="background:#070A13;border:2px solid #0F172A;border-radius:12px;'
                f'overflow:hidden;max-width:480px;margin:16px auto;box-shadow:0 4px 24px rgba(0,0,0,0.4);">'
                f'<div style="background:linear-gradient(135deg,#0F172A,#1e293b);'
                f'padding:10px 16px;border-bottom:2px solid rgba(0,255,157,0.15);">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="color:#00ff9d;font-weight:800;font-size:0.92rem;font-family:Inter,sans-serif;">'
                f'🎫 LIVE PREVIEW · {len(picks_to_include)}-LEG SLIP</span>'
                f'<span style="color:#64748b;font-size:0.70rem;">{quick_platform}</span>'
                f'</div></div>'
                f'<div style="padding:2px 0;">{_live_legs}</div>'
                f'<div style="background:#0F172A;padding:10px 16px;border-top:1px solid rgba(148,163,184,0.08);">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                f'<div><span style="color:#64748b;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;">EV ROI</span><br>'
                f'<span style="color:{_live_ev_c};font-size:1.1rem;font-weight:900;'
                f'font-family:\'JetBrains Mono\',monospace;">{_live_ev_s}{_live_ev_val:.1f}%</span></div>'
                f'<div style="text-align:right;"><span style="color:#64748b;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;">ALL-HIT PROB</span><br>'
                f'<span style="color:#e2e8f0;font-size:0.95rem;font-weight:700;'
                f'font-family:\'JetBrains Mono\',monospace;">{_combined_prob_live*100:.1f}%</span></div>'
                f'</div></div></div>',
                unsafe_allow_html=True,
            )
        
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
    table_to_show = PLATFORM_FLEX_TABLES.get(selected_platform, SPORTSBOOK_PARLAY_TABLE)

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
        st.dataframe(payout_display, width="stretch", hide_index=True)
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
    width="stretch",
)

if build_button:
    import time as _time_eb
    _build_progress = st.progress(0, text="Evaluating combinations…")
    _time_eb.sleep(0.15)
    _build_progress.progress(20, text="Checking correlations…")
    _time_eb.sleep(0.15)
    _build_progress.progress(40, text="Ranking by EV…")
    optimal_entries = build_optimal_entries(
        analyzed_picks=qualifying_picks,
        platform=selected_platform,
        entry_size=int(entry_size),
        entry_fee=float(entry_fee),
        max_entries_to_show=int(max_entries),
    )
    _build_progress.progress(80, text="Applying Kelly sizing…")
    _time_eb.sleep(0.15)
    _build_progress.progress(100, text="✅ Done!")
    _time_eb.sleep(0.3)
    _build_progress.empty()

    if optimal_entries:
        _effective_max = int(session_budget // entry_fee) if session_budget > 0 else len(optimal_entries)
        _show_entries = optimal_entries[:_effective_max] if session_budget > 0 else optimal_entries
        st.success(f"✅ Built {len(_show_entries)} optimal entries!"
                   + (f" (budget-limited to {_effective_max})" if session_budget > 0 and _effective_max < len(optimal_entries) else ""))

        # ── Record to Entry History (#8) ──────────────────────────
        if "entry_history" not in st.session_state:
            st.session_state["entry_history"] = []
        for _he_entry in _show_entries:
            _he_ev_d = format_ev_display(_he_entry["ev_result"], entry_fee)
            st.session_state["entry_history"].append({
                "timestamp": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "legs": _he_entry["picks"],
                "ev_label": _he_ev_d["ev_label"],
                "platform": selected_platform,
            })

        for entry_rank, entry in enumerate(_show_entries, start=1):
            picks = entry["picks"]
            ev_result = entry["ev_result"]
            confidence = entry["combined_confidence"]
            ev_display = format_ev_display(ev_result, entry_fee)

            ev_color = "green" if ev_display["is_positive_ev"] else "red"
            ev_label = ev_display["ev_label"]
            roi_label = ev_display["roi_label"]

            # ── Visual Parlay Card ────────────────────────────────────────
            _card_border = "#00ff9d" if ev_display["is_positive_ev"] else "#ff4444"
            _pick_cells = ""
            for _pick in picks:
                _pdir = _pick.get("direction", "OVER")
                _parrow = "⬆️" if _pdir == "OVER" else "⬇️"
                _ptier = _pick.get("tier_emoji", "🥉")
                _pprob = _pick.get("probability_over", 0.5)
                _pdisp_prob = (_pprob if _pdir == "OVER" else 1.0 - _pprob) * 100
                _pname = _pick.get("player_name", "")
                _pstat = _pick.get("stat_type", "").title()
                _pline = _pick.get("line", 0)
                _pedge = _pick.get("edge_percentage", 0)
                _pteam = _pick.get("team", "")
                _is_locked = _pname in st.session_state.get("locked_legs", set())
                _lock_badge = ' <span style="background:#c800ff;color:#fff;padding:1px 5px;border-radius:3px;font-size:0.68rem;">🔒 LOCKED</span>' if _is_locked else ""
                _prob_color = "#00ff9d" if _pdisp_prob >= 60 else ("#ffcc00" if _pdisp_prob >= 55 else "#ff6b6b")
                _pick_cells += (
                    f'<div style="flex:1;min-width:120px;background:rgba(0,0,0,0.3);border-radius:8px;'
                    f'padding:12px;text-align:center;border:1px solid rgba(255,255,255,0.08);">'
                    f'<div style="font-size:0.75rem;color:#8a9bb8;">{_html_eb.escape(_pteam)}</div>'
                    f'<div style="font-size:0.88rem;font-weight:700;color:#c0d0e8;margin:4px 0;">'
                    f'{_html_eb.escape(_pname)}{_lock_badge}</div>'
                    f'<div style="font-size:1.1rem;color:{_prob_color};font-weight:800;">'
                    f'{_parrow} {_pdir}</div>'
                    f'<div style="font-size:0.8rem;color:#8a9bb8;">{_pstat} {_pline}</div>'
                    f'<div style="font-size:0.85rem;color:{_prob_color};font-weight:700;">{_pdisp_prob:.0f}%</div>'
                    f'<div style="font-size:0.72rem;color:#8a9bb8;">{_ptier} Edge: {_pedge:+.1f}%</div>'
                    f'</div>'
                )

            st.markdown(
                f'<div style="background:#14192b;border-radius:10px;padding:16px 20px;'
                f'margin-bottom:16px;border-top:3px solid {_card_border};">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
                f'<div style="font-family:Orbitron,sans-serif;font-size:1rem;color:{_card_border};font-weight:700;">'
                f'Entry #{entry_rank}</div>'
                f'<div style="display:flex;gap:16px;font-size:0.85rem;">'
                f'<span style="color:{_card_border};font-weight:700;">EV: {_html_eb.escape(ev_label)}</span>'
                f'<span style="color:#8a9bb8;">ROI: {_html_eb.escape(roi_label)}</span>'
                f'<span style="color:#8a9bb8;">Confidence: {confidence:.0f}/100</span>'
                f'</div></div>'
                f'<div style="display:flex;gap:8px;flex-wrap:wrap;">{_pick_cells}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Correlation risk warnings
            corr_risk = entry.get("correlation_risk", {})
            corr_warnings = corr_risk.get("warnings", [])
            if corr_warnings:
                for w in corr_warnings:
                    st.warning(w)
            if ev_result.get("correlation_discount_applied"):
                discount_pct = round((1.0 - corr_risk.get("discount_multiplier", 1.0)) * 100)
                st.caption(f"📉 Correlation discount applied: −{discount_pct}% EV adjustment")

            # Weakest link warning + swap suggestion + Swap button (#12)
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
                    if st.button(
                        f"🔄 Swap: Replace with {swap.get('player_name','')}",
                        key=f"swap_built_{entry_rank}",
                    ):
                        _new_picks = [
                            swap if (p.get("player_name") == weakest.get("player_name") and p.get("stat_type") == weakest.get("stat_type"))
                            else p
                            for p in st.session_state.get("selected_picks", [])
                        ]
                        st.session_state["selected_picks"] = _new_picks
                        st.rerun()
                else:
                    st.caption(f"⚠️ Weakest leg: {weakest_label}")

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

                st.dataframe(breakdown_rows, width="stretch", hide_index=True)
                st.caption(
                    f"**Total Expected Return:** ${ev_result.get('total_expected_return', 0):.2f} "
                    f"on ${entry_fee:.2f} entry = **Net EV: {ev_label}**"
                )

            # Feature 5: Kelly bankroll sizing
            try:
                if calculate_kelly_fraction is not None and bankroll_amount > 0:
                    _win_prob = entry.get("combined_probability", 0.5)
                    _payout_mult = entry.get("ev_result", {}).get("best_payout_multiplier", 3.0)
                    if _payout_mult > 0:
                        _kelly = calculate_kelly_fraction(_win_prob, _payout_mult, kelly_mode)
                        _recommended_bet = round(_kelly * bankroll_amount, 2)
                        if _recommended_bet > 0:
                            st.caption(f"💰 Kelly sizing: **${_recommended_bet:.2f}** ({_kelly*100:.1f}% of bankroll) — {kelly_mode} Kelly")
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[EntryBuilder] Unexpected error: {_exc}")

            # Feature 10: Flex vs Power recommendation
            try:
                if selected_platform == "DraftKings":
                    _entry_probs = [
                        p.get("probability_over", 0.5) if p.get("direction") == "OVER"
                        else 1.0 - p.get("probability_over", 0.5)
                        for p in entry.get("picks", [])
                    ]
                    if len(_entry_probs) >= 2:
                        _play_type = optimize_play_type(_entry_probs, len(_entry_probs), "DraftKings")
                        _pt_color = "green" if _play_type["recommended_play_type"] == "Power" else "blue"
                        st.markdown(
                            f"**Play Type:** :{_pt_color}[{_play_type['recommended_play_type']} recommended]** — "
                            f"Flex EV: ${_play_type['flex_ev']:.2f} | Power EV: ${_play_type['power_ev']:.2f}<br>"
                            f"_{_play_type['reasoning']}_",
                            unsafe_allow_html=True,
                        )
            except Exception as _exc:
                logging.getLogger(__name__).warning(f"[EntryBuilder] Unexpected error: {_exc}")

            # ── One-Click "Log to Bet Tracker" (#9) ──────────────────
            if st.button(f"📋 Log Entry #{entry_rank} to Bet Tracker", key=f"log_entry_{entry_rank}"):
                try:
                    from tracking.database import insert_bet as _insert_bet_eb
                    _today_str = _dt.date.today().isoformat()
                    _logged_count = 0
                    for _lp in picks:
                        _bet_data = {
                            "bet_date": _today_str,
                            "player_name": _lp.get("player_name", ""),
                            "team": _lp.get("player_team", _lp.get("team", "")),
                            "stat_type": _lp.get("stat_type", ""),
                            "prop_line": float(_lp.get("line", 0)),
                            "direction": _lp.get("direction", "OVER"),
                            "platform": selected_platform,
                            "confidence_score": float(_lp.get("confidence_score", 0)),
                            "probability_over": float(_lp.get("probability_over", 0.5)),
                            "edge_percentage": float(_lp.get("edge_percentage", 0)),
                            "tier": _lp.get("tier", "Bronze"),
                            "entry_type": "parlay",
                            "entry_fee": float(entry_fee),
                            "notes": f"Entry #{entry_rank} ({entry_size}-pick, EV: {ev_label})",
                            "auto_logged": 1,
                        }
                        _row_id = _insert_bet_eb(_bet_data)
                        if _row_id:
                            _logged_count += 1
                    if _logged_count:
                        st.success(f"✅ Logged {_logged_count} leg(s) from Entry #{entry_rank} to Bet Tracker!")
                    else:
                        st.error("Failed to log entry. Check database connection.")
                except Exception as _log_exc:
                    st.error(f"Error logging entry: {_log_exc}")

            st.markdown("---")

        # ════ JOSEPH REACTS TO ENTRY ════
        if st.session_state.get("joseph_enabled", True):
            try:
                from utils.joseph_widget import inject_joseph_inline_commentary
                st.session_state["joseph_entry_just_built"] = True
                _entry_results = [{"player_name": leg.get("player_name",""), "stat_type": leg.get("stat_type",""),
                                   "line": leg.get("line",0), "direction": leg.get("direction",""),
                                   "edge_percentage": leg.get("edge_percentage",0)}
                                  for entry in (optimal_entries[:3] if 'optimal_entries' in dir() else [])
                                  for leg in entry.get("legs", [])]
                if _entry_results:
                    inject_joseph_inline_commentary(_entry_results, "entry_built")
            except Exception:
                pass
        # ════ END JOSEPH ENTRY REACTION ════

        # ════ AUTO-LOG ENTRIES TO BET TRACKER (B10) ════
        # Automatically save each built entry as a parlay in the Bet Tracker
        # database so users can track multi-leg results from the 🎰 Parlays tab.
        try:
            from tracking.database import insert_entry as _eb_insert_entry, insert_bet as _eb_insert_bet, link_bets_to_entry as _eb_link
            import datetime as _dt_eb

            _today_str = _dt_eb.date.today().isoformat()
            _logged_count = 0

            for _entry in _show_entries:
                _ev_result = _entry.get("ev_result", {})
                _ev_net = _ev_result.get("net_expected_value", 0.0)
                _picks = _entry.get("picks", [])

                _entry_id = _eb_insert_entry({
                    "entry_date": _today_str,
                    "platform": selected_platform,
                    "entry_type": "parlay",
                    "entry_fee": float(entry_fee),
                    "expected_value": _ev_net,
                    "pick_count": len(_picks),
                    "notes": f"Auto-logged from Entry Builder",
                })

                if _entry_id and _picks:
                    _leg_ids = []
                    for _pick in _picks:
                        _bet_id = _eb_insert_bet({
                            "bet_date": _today_str,
                            "player_name": _pick.get("player_name", ""),
                            "team": _pick.get("team", ""),
                            "stat_type": _pick.get("stat_type", ""),
                            "prop_line": _pick.get("line", 0.0),
                            "direction": _pick.get("direction", ""),
                            "platform": selected_platform,
                            "confidence_score": _pick.get("confidence_score", 0.0),
                            "tier": _pick.get("tier", ""),
                            "edge_percentage": _pick.get("edge_percentage", 0.0),
                            "player_id": _pick.get("player_id", ""),
                            "entry_fee": float(entry_fee) / max(len(_picks), 1),
                        })
                        if _bet_id:
                            _leg_ids.append(_bet_id)

                    if _leg_ids:
                        _eb_link(_leg_ids, _entry_id)
                        _logged_count += 1

            if _logged_count > 0:
                st.toast(f"🎰 Auto-logged {_logged_count} entries to the Bet Tracker → Parlays tab.")
        except Exception as _eb_log_exc:
            logging.getLogger(__name__).debug(f"[EntryBuilder] Auto-log to tracker: {_eb_log_exc}")
        # ════ END AUTO-LOG ════

    # Feature 5: Session risk summary
    try:
        if calculate_kelly_fraction is not None and get_session_risk_summary is not None and optimal_entries and bankroll_amount > 0:
            st.divider()
            st.subheader("💰 Kelly Bankroll Summary")
            _kelly_entries = []
            for _e in optimal_entries:
                _wp = _e.get("combined_probability", 0.5)
                _pm = _e.get("ev_result", {}).get("best_payout_multiplier", 3.0)
                _kf = calculate_kelly_fraction(_wp, _pm, kelly_mode)
                _rb = round(_kf * bankroll_amount, 2)
                _kelly_entries.append({
                    "win_probability": _wp,
                    "payout_multiplier": _pm,
                    "recommended_bet": _rb,
                    "kelly_fraction": _kf,
                    "expected_profit": _rb * (_wp * _pm - 1.0),
                })
            _risk_summary = get_session_risk_summary(_kelly_entries, bankroll_amount)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total at Risk", f"${_risk_summary['total_at_risk']:.2f}", f"{_risk_summary['total_at_risk_pct']*100:.1f}% of bankroll")
            c2.metric("Expected Profit", f"${_risk_summary['expected_profit']:.2f}")
            c3.metric("P(Positive Session)", f"{_risk_summary['prob_positive_session']*100:.1f}%")
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[EntryBuilder] Unexpected error: {_exc}")

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

# ── Color-Coded Tier Badges (#7) ─────────────────────────────
if selected_pick_labels:
    _custom_tier_colors = {
        "Platinum": "#00f0ff", "Gold": "#ffd700",
        "Silver": "#c0c0c0", "Bronze": "#cd7f32",
    }
    _chips_html = ""
    for _cl in selected_pick_labels:
        _parts = _cl.split(" | ")
        _c_tier = _parts[-1].strip() if len(_parts) >= 5 else "Bronze"
        # Extract tier name from emoji+name
        for _tn in _custom_tier_colors:
            if _tn in _c_tier:
                _c_bg = _custom_tier_colors[_tn]
                break
        else:
            _c_bg = "#cd7f32"
        _chips_html += (
            f'<span style="display:inline-block;background:{_c_bg};color:#0a0f1a;'
            f'padding:3px 10px;border-radius:14px;font-size:0.76rem;font-weight:700;'
            f'margin:2px 4px;">{_html_eb.escape(_cl)}</span>'
        )
    st.markdown(
        f'<div style="margin:6px 0 12px;line-height:2;">{_chips_html}</div>',
        unsafe_allow_html=True,
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
    platform_flex_table = PLATFORM_FLEX_TABLES.get(selected_platform, SPORTSBOOK_PARLAY_TABLE)
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


# ============================================================
# SECTION: Auto-Slip Optimizer
# ============================================================

st.divider()

st.markdown(
    '<div style="background:linear-gradient(135deg,rgba(7,10,19,0.92),rgba(15,23,42,0.88));'
    'border:1px solid rgba(0,255,157,0.18);border-radius:12px;padding:20px 24px;'
    'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);margin-bottom:16px;">'
    '<h2 style="color:#00ff9d;margin:0 0 6px;font-family:Inter,sans-serif;font-weight:800;">'
    '🚀 Auto-Slip Optimizer</h2>'
    '<p style="color:#94a3b8;font-size:0.84rem;margin:0;">'
    'Generates the mathematically optimal ticket from tonight\'s props using '
    'combinatorial EV analysis with intra-game correlation weighting.</p></div>',
    unsafe_allow_html=True,
)

_opt_c1, _opt_c2 = st.columns(2)
with _opt_c1:
    _opt_platform = st.selectbox(
        "Platform",
        options=["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"],
        index=0,
        key="auto_slip_platform",
    )
with _opt_c2:
    _opt_entry_type = st.selectbox(
        "Entry Type",
        options=["Flex Play", "Power Play"],
        index=0,
        key="auto_slip_entry_type",
    )

_generate_clicked = st.button(
    "⚡  GENERATE OPTIMAL SLIP",
    use_container_width=True,
    type="primary",
    key="generate_optimal_slip_btn",
)

if _generate_clicked:
    from engine.odds_engine import generate_optimal_slip, implied_probability_to_american_odds, calculate_fractional_kelly, calculate_dfs_ev
    from engine.math_helpers import clamp_probability

    # ── Locked legs integration (#13): force locked picks into Auto-Slip ──
    _locked_names = st.session_state.get("locked_legs", set())
    _locked_picks_for_slip = [p for p in qualifying_picks if p.get("player_name", "") in _locked_names] if _locked_names else []

    with st.spinner("🔬 Running combinatorial optimizer..."):
        _slips = generate_optimal_slip(qualifying_picks, platform=_opt_platform)

    # If locked legs exist, force them into every slip
    if _locked_picks_for_slip and _slips:
        _locked_player_set = {p.get("player_name", "") for p in _locked_picks_for_slip}
        for _s in _slips:
            _existing_names = {p.get("player_name", "") for p in _s.get("picks", [])}
            for _lp in _locked_picks_for_slip:
                if _lp.get("player_name", "") not in _existing_names:
                    _s["picks"].append(_lp)
                    _s["slip_size"] = len(_s["picks"])

    if not _slips:
        st.warning("Not enough qualifying picks to generate an optimal slip.")
    else:
        # ── Slip Summary Statistics Bar ───────────────────────────
        _all_evs = [s["cumulative_ev"] for s in _slips]
        _all_probs = [s["combined_probability"] for s in _slips]
        _size_counts = {}
        for s in _slips:
            _size_counts[s["slip_size"]] = _size_counts.get(s["slip_size"], 0) + 1
        _size_dist = " · ".join(f'{sz}-man: {ct}' for sz, ct in sorted(_size_counts.items()))

        _avg_ev = sum(_all_evs) / len(_all_evs) if _all_evs else 0
        _avg_prob = sum(_all_probs) / len(_all_probs) if _all_probs else 0
        _best_ev = max(_all_evs) if _all_evs else 0
        _avg_ev_c = "#00ff9d" if _avg_ev > 0 else "#ff5e00"
        _best_ev_c = "#00ff9d" if _best_ev > 0 else "#ff5e00"

        # DFS aggregate across all slips (Phase 4)
        _all_dfs_edges = [s.get("dfs_avg_edge", 0) for s in _slips if s.get("dfs_leg_edges")]
        _avg_dfs_edge = (sum(_all_dfs_edges) / len(_all_dfs_edges) * 100) if _all_dfs_edges else 0
        _avg_dfs_edge_c = "#00ff9d" if _avg_dfs_edge > 0 else "#ff5e00"

        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0;">'
            # Total slips
            '<div style="flex:1;min-width:110px;background:linear-gradient(135deg,#070A13,#0F172A);'
            'border:1px solid rgba(148,163,184,0.12);border-radius:8px;padding:10px 14px;text-align:center;">'
            '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            'Slips Generated</div>'
            f'<div style="color:#c0d0e8;font-size:1.15rem;font-weight:800;'
            f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
            f'">{len(_slips)}</div></div>'
            # Best EV
            '<div style="flex:1;min-width:110px;background:linear-gradient(135deg,#070A13,#0F172A);'
            'border:1px solid rgba(0,255,157,0.18);border-radius:8px;padding:10px 14px;text-align:center;">'
            '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            'Best EV</div>'
            f'<div style="color:{_best_ev_c};font-size:1.15rem;font-weight:800;'
            f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
            f'">{"+" if _best_ev > 0 else ""}{_best_ev * 100:.1f}%</div></div>'
            # Avg EV
            '<div style="flex:1;min-width:110px;background:linear-gradient(135deg,#070A13,#0F172A);'
            'border:1px solid rgba(0,240,255,0.15);border-radius:8px;padding:10px 14px;text-align:center;">'
            '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            'Avg EV</div>'
            f'<div style="color:{_avg_ev_c};font-size:1.15rem;font-weight:800;'
            f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
            f'">{"+" if _avg_ev > 0 else ""}{_avg_ev * 100:.1f}%</div></div>'
            # Avg All-Hit Prob
            '<div style="flex:1;min-width:110px;background:linear-gradient(135deg,#070A13,#0F172A);'
            'border:1px solid rgba(148,163,184,0.12);border-radius:8px;padding:10px 14px;text-align:center;">'
            '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            'Avg All-Hit</div>'
            f'<div style="color:#c0d0e8;font-size:1.15rem;font-weight:800;'
            f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
            f'">{_avg_prob * 100:.1f}%</div></div>'
            # DFS Avg Edge (Phase 4)
            '<div style="flex:1;min-width:110px;background:linear-gradient(135deg,#070A13,#0F172A);'
            'border:1px solid rgba(0,255,157,0.12);border-radius:8px;padding:10px 14px;text-align:center;">'
            '<div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            'DFS Edge</div>'
            f'<div style="color:{_avg_dfs_edge_c};font-size:1.15rem;font-weight:800;'
            f"font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;"
            f'">{"+" if _avg_dfs_edge > 0 else ""}{_avg_dfs_edge:.1f}%</div></div>'
            '</div>',
            unsafe_allow_html=True,
        )

        _best = _slips[0]
        _picks = _best["picks"]
        _ev = _best["cumulative_ev"]
        _prob = _best["combined_probability"]
        _penalty = _best["correlation_penalty"]
        _fair_odds = _best["fair_odds"]
        _slip_size = _best["slip_size"]

        _ev_color = "#00ff9d" if _ev > 0 else "#ff5e00"
        _ev_sign = "+" if _ev > 0 else ""

        # ── Kelly TARGET ALLOCATION for the slip ──────────────────
        _slip_bankroll = float(st.session_state.get("total_bankroll", 1000.0))
        _slip_kelly_mult = float(st.session_state.get("kelly_multiplier", 0.25))
        _slip_entry_fee = float(st.session_state.get("entry_fee", 10.0))
        _slip_kelly_result = calculate_fractional_kelly(
            clamp_probability(_prob), _fair_odds, _slip_kelly_mult,
        )
        _slip_kelly_frac = _slip_kelly_result.get("fractional_kelly", 0.0)
        _slip_wager = round(_slip_kelly_frac * _slip_bankroll, 2) if _slip_kelly_frac > 0 else 0.0
        _slip_expected_payout = round(_slip_entry_fee * (1.0 + _ev), 2)

        # ── DFS Platform EV (against actual payout table) ─────────
        _dfs_leg_probs = []
        for _pk in _picks:
            _pk_dir = _pk.get("direction", "OVER")
            _pk_prob = _pk.get("probability_over", 0.5)
            _dfs_leg_probs.append(_pk_prob if _pk_dir == "OVER" else (1.0 - _pk_prob))
        _dfs_ev_result = calculate_dfs_ev(
            _dfs_leg_probs, platform=_opt_platform,
            entry_fee=_slip_entry_fee,
        )
        _dfs_ev_val = _dfs_ev_result.get("expected_value", 0.0)
        _dfs_roi = _dfs_ev_result.get("roi_pct", 0.0)

        # ── Digital Betting Ticket ────────────────────────────────
        _dfs_edges = _best.get("dfs_leg_edges", [])
        _legs_html = ""
        for _idx, _pk in enumerate(_picks, 1):
            _pk_name = _html_eb.escape(str(_pk.get("player_name", "?")))
            _pk_stat = _html_eb.escape(str(_pk.get("stat_type", "")).title())
            _pk_dir = _pk.get("direction", "OVER")
            _pk_line = _pk.get("line", 0)
            _pk_prob = _pk.get("probability_over", 0.5)
            _pk_prob_dir = _pk_prob if _pk_dir == "OVER" else (1.0 - _pk_prob)
            _pk_conf = _pk.get("confidence_score", 50)
            _pk_tier = _pk.get("tier", "Bronze")
            _pk_edge = _pk.get("edge_percentage", 0)
            _pk_team = _html_eb.escape(str(_pk.get("player_team", _pk.get("team", ""))))

            _tier_colors = {
                "Platinum": "#00f0ff", "Gold": "#ffd700", "Silver": "#c0c0c0",
                "Bronze": "#cd7f32", "Diamond": "#b9f2ff",
            }
            _tc = _tier_colors.get(_pk_tier, "#94a3b8")
            _edge_c = "#00ff9d" if _pk_edge > 0 else "#ff5e00"
            _edge_s = "+" if _pk_edge > 0 else ""

            _pk_dir_label = "MORE" if _pk_dir == "OVER" else "LESS"

            # Per-leg DFS breakeven badge (Phase 4)
            _dfs_badge = ""
            if _idx - 1 < len(_dfs_edges) and _dfs_edges[_idx - 1] is not None:
                _le = _dfs_edges[_idx - 1]
                _le_beats = _le.get("beats_breakeven", False)
                _le_edge = _le.get("edge_vs_breakeven", 0) * 100
                if _le_beats:
                    _dfs_badge = (
                        f'<span style="color:#00ff9d;font-size:0.60rem;margin-left:4px;" '
                        f'title="Beats {_slip_size}-pick breakeven by {_le_edge:+.1f}%">'
                        f'✅ BE+{_le_edge:.0f}%</span>'
                    )
                else:
                    _dfs_badge = (
                        f'<span style="color:#ff5e00;font-size:0.60rem;margin-left:4px;" '
                        f'title="Below {_slip_size}-pick breakeven by {_le_edge:.1f}%">'
                        f'⚠️ BE{_le_edge:+.0f}%</span>'
                    )

            _legs_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:8px 12px;border-bottom:1px solid rgba(148,163,184,0.08);">'
                f'<div style="flex:1;">'
                f'<span style="color:#e2e8f0;font-weight:600;font-size:0.84rem;">{_pk_name}</span>'
                f'<span style="color:#64748b;font-size:0.72rem;margin-left:6px;">{_pk_team}</span><br>'
                f'<span style="color:#94a3b8;font-size:0.76rem;">{_pk_stat} '
                f'<span style="color:{"#00f0ff" if _pk_dir == "OVER" else "#ff5e00"};">{_pk_dir_label}</span> '
                f'<span style="font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                f'{_pk_line}</span></span></div>'
                f'<div style="text-align:right;">'
                f'<span style="color:{_tc};font-size:0.72rem;font-weight:700;">{_pk_tier}</span>'
                f'<span style="color:{_edge_c};font-size:0.68rem;margin-left:5px;'
                f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                f'{_edge_s}{_pk_edge:.1f}%</span>{_dfs_badge}<br>'
                f'<span style="color:#94a3b8;font-size:0.72rem;font-family:\'JetBrains Mono\',monospace;'
                f'font-variant-numeric:tabular-nums;">{_pk_prob_dir*100:.0f}%</span></div></div>'
            )

        _odds_str = f"+{_fair_odds:.0f}" if _fair_odds > 0 else f"{_fair_odds:.0f}"
        _penalty_note = (
            f'<span style="color:#ff5e00;font-size:0.68rem;">'
            f'⚠️ Correlation penalty: {(1-_penalty)*100:.0f}%</span>'
            if _penalty < 1.0 else ""
        )

        # ── Kelly wager row (only shown when positive) ────────────
        _kelly_row = ""
        if _slip_wager > 0:
            _kelly_row = (
                f'<div style="margin-top:8px;padding-top:8px;'
                f'border-top:1px solid rgba(0,198,255,0.12);">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                f'<div>'
                f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
                f'TARGET ALLOCATION</span><br>'
                f'<span style="color:#00C6FF;font-size:1.1rem;font-weight:800;'
                f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                f'${_slip_wager:,.2f}</span></div>'
                f'<div style="text-align:center;">'
                f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
                f'EXPECTED PAYOUT</span><br>'
                f'<span style="color:#e2e8f0;font-size:1rem;font-weight:700;'
                f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                f'${_slip_expected_payout:,.2f}</span></div>'
                f'<div style="text-align:right;">'
                f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
                f'KELLY %</span><br>'
                f'<span style="color:#94a3b8;font-size:0.85rem;font-weight:600;'
                f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                f'{_slip_kelly_frac*100:.2f}%</span></div>'
                f'</div></div>'
            )

        _ticket_html = (
            f'<div style="background:#070A13;border:2px solid #0F172A;border-radius:12px;'
            f'overflow:hidden;max-width:520px;margin:16px auto;'
            f'box-shadow:0 4px 24px rgba(0,0,0,0.4);">'
            # Header
            f'<div style="background:linear-gradient(135deg,#0F172A,#1e293b);'
            f'padding:14px 18px;border-bottom:2px solid rgba(0,255,157,0.15);">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="color:#00ff9d;font-weight:800;font-size:1rem;font-family:Inter,sans-serif;">'
            f'🎫 OPTIMAL {_slip_size}-MAN SLIP</span>'
            f'<span style="color:#64748b;font-size:0.72rem;">{_opt_platform} · {_opt_entry_type}</span>'
            f'</div></div>'
            # Legs
            f'<div style="padding:4px 0;">{_legs_html}</div>'
            # Footer
            f'<div style="background:#0F172A;padding:14px 18px;'
            f'border-top:1px solid rgba(148,163,184,0.08);">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<div>'
            f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            f'CUMULATIVE EV</span><br>'
            f'<span style="color:{_ev_color};font-size:1.3rem;font-weight:900;'
            f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
            f'{_ev_sign}{_ev*100:.1f}%</span></div>'
            f'<div style="text-align:center;">'
            f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            f'ALL-HIT PROB</span><br>'
            f'<span style="color:#e2e8f0;font-size:1rem;font-weight:700;'
            f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
            f'{_prob*100:.1f}%</span></div>'
            f'<div style="text-align:right;">'
            f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
            f'FAIR ODDS</span><br>'
            f'<span style="color:#00C6FF;font-size:1rem;font-weight:700;'
            f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
            f'{_odds_str}</span></div>'
            f'</div>'
            f'{_penalty_note}'
            f'{_kelly_row}'
            # DFS Platform EV
            f'<div style="margin-top:6px;padding-top:6px;'
            f'border-top:1px solid rgba(0,240,255,0.08);">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<div>'
            f'<span style="color:#64748b;font-size:0.60rem;text-transform:uppercase;letter-spacing:0.08em;">'
            f'DFS EV ({_opt_platform})</span><br>'
            f'<span style="color:{"#00ff9d" if _dfs_ev_val > 0 else "#ff5e00"};font-size:0.9rem;font-weight:700;'
            f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
            f'{"+" if _dfs_ev_val > 0 else ""}{_dfs_ev_val:.2f}</span></div>'
            f'<div style="text-align:right;">'
            f'<span style="color:#64748b;font-size:0.60rem;text-transform:uppercase;letter-spacing:0.08em;">'
            f'DFS ROI</span><br>'
            f'<span style="color:{"#00ff9d" if _dfs_roi > 0 else "#ff5e00"};font-size:0.9rem;font-weight:700;'
            f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
            f'{"+" if _dfs_roi > 0 else ""}{_dfs_roi:.1f}%</span></div>'
            f'</div></div>'
            # DFS per-leg breakeven summary (Phase 4)
            + (
                f'<div style="margin-top:4px;padding-top:4px;'
                f'border-top:1px solid rgba(0,255,157,0.06);">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                f'<span style="color:#64748b;font-size:0.58rem;text-transform:uppercase;letter-spacing:0.06em;">'
                f'LEGS vs {_slip_size}-PICK BREAKEVEN</span>'
                f'<span style="color:{"#00ff9d" if _best.get("dfs_legs_beat_breakeven", 0) == _slip_size else "#94a3b8"};'
                f'font-size:0.72rem;font-weight:700;font-family:\'JetBrains Mono\',monospace;">'
                f'{_best.get("dfs_legs_beat_breakeven", 0)}/{_slip_size} ✅'
                f'</span>'
                f'<span style="color:{"#00ff9d" if _best.get("dfs_avg_edge", 0) > 0 else "#ff5e00"};'
                f'font-size:0.68rem;font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                f'avg {"+" if _best.get("dfs_avg_edge", 0) > 0 else ""}'
                f'{_best.get("dfs_avg_edge", 0) * 100:.1f}%</span>'
                f'</div></div>'
                if _best.get("dfs_leg_edges") and any(e for e in _best.get("dfs_leg_edges", []) if e is not None)
                else ""
            ) +
            f'</div></div>'
        )

        st.markdown(_ticket_html, unsafe_allow_html=True)

        # ── Export Slip to Image (#15) ────────────────────────────
        st.download_button(
            label="📸 Export Slip as HTML",
            data=(
                '<!DOCTYPE html><html><head><meta charset="utf-8">'
                '<style>body{background:#070A13;margin:20px;font-family:Inter,system-ui,sans-serif;}</style>'
                '</head><body>' + _ticket_html + '</body></html>'
            ),
            file_name="optimal_slip.html",
            mime="text/html",
            key="export_slip_html",
        )

        # Show runner-up slips
        if len(_slips) > 1:
            with st.expander(f"📊 {len(_slips)-1} Alternative Slips", expanded=False):
                for _alt_idx, _alt in enumerate(_slips[1:], 2):
                    _alt_ev = _alt["cumulative_ev"]
                    _alt_sz = _alt["slip_size"]
                    _alt_prob = _alt["combined_probability"]
                    _alt_odds = _alt["fair_odds"]
                    _alt_penalty = _alt["correlation_penalty"]
                    _alt_names = ", ".join(
                        _html_eb.escape(str(p.get("player_name", "?"))) for p in _alt["picks"]
                    )
                    _alt_ev_c = "#00ff9d" if _alt_ev > 0 else "#ff5e00"
                    _alt_s = "+" if _alt_ev > 0 else ""
                    _alt_odds_str = f"+{_alt_odds:.0f}" if _alt_odds > 0 else f"{_alt_odds:.0f}"
                    _alt_penalty_tag = (
                        f' <span style="color:#ff5e00;font-size:0.62rem;">⚠ corr {(1-_alt_penalty)*100:.0f}%</span>'
                        if _alt_penalty < 1.0 else ""
                    )
                    st.markdown(
                        f'<div style="padding:8px 10px;border-bottom:1px solid rgba(148,163,184,0.06);">'
                        f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                        f'<span style="color:#94a3b8;font-size:0.76rem;">#{_alt_idx} · {_alt_sz}-man</span>'
                        f'<div>'
                        f'<span style="color:{_alt_ev_c};font-weight:700;font-size:0.82rem;'
                        f'font-family:\'JetBrains Mono\',monospace;font-variant-numeric:tabular-nums;">'
                        f'{_alt_s}{_alt_ev*100:.1f}%</span>'
                        f'<span style="color:#64748b;font-size:0.68rem;margin-left:8px;">'
                        f'{_alt_prob*100:.1f}% · {_alt_odds_str}</span>'
                        f'{_alt_penalty_tag}'
                        f'</div></div>'
                        f'<span style="color:#64748b;font-size:0.72rem;">{_alt_names}</span></div>',
                        unsafe_allow_html=True,
                    )

# ============================================================
# END SECTION: Auto-Slip Optimizer
# ============================================================

# ============================================================
# SECTION: Cross-Platform EV Comparison (#10)
# ============================================================

st.divider()

with st.expander("🔀 Cross-Platform EV Comparison", expanded=False):
    st.markdown(
        '<p style="color:#94a3b8;font-size:0.84rem;margin:0 0 12px;">'
        'See how the same entry&#39;s EV compares across platforms.</p>',
        unsafe_allow_html=True,
    )
    # Use top qualifying picks for comparison
    _cmp_picks = qualifying_picks[:min(int(entry_size), len(qualifying_picks))]
    if len(_cmp_picks) >= 2:
        _cmp_probs = [
            p.get("probability_over", 0.5) if p.get("direction") == "OVER"
            else 1.0 - p.get("probability_over", 0.5)
            for p in _cmp_picks
        ]
        _cmp_platforms = ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"]
        _cmp_rows = ""
        for _cp in _cmp_platforms:
            _cp_table = PLATFORM_FLEX_TABLES.get(_cp, SPORTSBOOK_PARLAY_TABLE)
            _cp_payout = _cp_table.get(len(_cmp_picks), {})
            if _cp_payout:
                _cp_ev = calculate_entry_expected_value(_cmp_probs, _cp_payout, float(entry_fee))
                _cp_display = format_ev_display(_cp_ev, float(entry_fee))
                _cp_color = "#00ff9d" if _cp_display["is_positive_ev"] else "#ff5e00"
                _cmp_rows += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:8px 14px;border-bottom:1px solid rgba(148,163,184,0.06);">'
                    f'<span style="color:#c0d0e8;font-weight:600;font-size:0.85rem;">{_html_eb.escape(_cp)}</span>'
                    f'<div>'
                    f'<span style="color:{_cp_color};font-weight:700;font-size:0.9rem;'
                    f'font-family:\'JetBrains Mono\',monospace;">{_html_eb.escape(_cp_display["ev_label"])}</span>'
                    f'<span style="color:#8a9bb8;font-size:0.76rem;margin-left:10px;">'
                    f'ROI: {_html_eb.escape(_cp_display["roi_label"])}</span>'
                    f'</div></div>'
                )
            else:
                _cmp_rows += (
                    f'<div style="padding:6px 14px;border-bottom:1px solid rgba(148,163,184,0.06);">'
                    f'<span style="color:#64748b;font-size:0.82rem;">{_html_eb.escape(_cp)}: No {len(_cmp_picks)}-pick payout table</span></div>'
                )
        _cmp_names = ", ".join(_html_eb.escape(p.get("player_name", "?")) for p in _cmp_picks)
        st.markdown(
            f'<div style="background:#0a0f1a;border-radius:10px;overflow:hidden;'
            f'border:1px solid rgba(0,255,157,0.12);">'
            f'<div style="background:#0F172A;padding:10px 14px;border-bottom:1px solid rgba(148,163,184,0.08);">'
            f'<span style="color:#00ff9d;font-weight:700;font-size:0.85rem;">📊 {len(_cmp_picks)}-Leg Entry</span>'
            f'<span style="color:#64748b;font-size:0.72rem;margin-left:8px;">{_cmp_names}</span></div>'
            f'{_cmp_rows}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Need at least 2 qualifying picks for comparison.")

# ============================================================
# END SECTION: Cross-Platform EV Comparison
# ============================================================


# ============================================================
# SECTION: Entry History Persistence (#8)
# ============================================================

st.divider()

with st.expander("📜 Entry History", expanded=False):
    if "entry_history" not in st.session_state:
        st.session_state["entry_history"] = []

    _history = st.session_state["entry_history"]

    if _history:
        for _hi, _he in enumerate(reversed(_history), 1):
            _he_time = _he.get("timestamp", "")
            _he_legs = _he.get("legs", [])
            _he_ev = _he.get("ev_label", "N/A")
            _he_plat = _he.get("platform", "")
            _he_leg_names = ", ".join(_html_eb.escape(l.get("player_name", "?")) for l in _he_legs)
            st.markdown(
                f'<div style="background:#14192b;border-radius:8px;padding:10px 14px;'
                f'margin-bottom:6px;border-left:3px solid #00ff9d;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="color:#c0d0e8;font-weight:600;font-size:0.84rem;">'
                f'Entry #{_hi} · {len(_he_legs)} legs</span>'
                f'<span style="color:#64748b;font-size:0.72rem;">{_html_eb.escape(_he_time)} · {_html_eb.escape(_he_plat)}</span>'
                f'</div>'
                f'<div style="color:#8a9bb8;font-size:0.78rem;margin-top:4px;">{_he_leg_names}</div>'
                f'<div style="color:#00ff9d;font-size:0.82rem;font-weight:700;margin-top:2px;">EV: {_html_eb.escape(_he_ev)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if st.button("🗑️ Clear History", key="clear_entry_history"):
            st.session_state["entry_history"] = []
            st.rerun()
    else:
        st.caption("No entries built yet this session. Build an entry above to start tracking.")

# ============================================================
# END SECTION: Entry History Persistence
# ============================================================
