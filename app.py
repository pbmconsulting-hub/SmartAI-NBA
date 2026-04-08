# ============================================================
# FILE: app.py
# PURPOSE: Main entry point for the SmartBetPro NBA Streamlit app.
#          Professional dark-themed landing page that sells outcomes,
#          guards the process, and converts first-time visitors.
# HOW TO RUN: streamlit run app.py
# ============================================================

import streamlit as st
import datetime
import os
import base64
import logging

from data.data_manager import load_players_data, load_props_data, load_teams_data
from data.nba_data_service import load_last_updated
from tracking.database import initialize_database, load_user_settings, load_page_state
from styles.theme import get_global_css

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="Smart Pick Pro — NBA Edition",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
st.markdown(get_global_css(), unsafe_allow_html=True)

# ─── App Logo — Smart Pick Pro ───────────────────────────────
# Logo is rendered per-page only on key pages (Neural Analysis, Studio,
# Live Games, Live Sweat, Bet Tracker) instead of globally.
_ROOT_LOGO_PATH   = os.path.join(os.path.dirname(__file__), "Smart_Pick_Pro_Logo.png")
_ASSETS_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "Smart_Pick_Pro_Logo.png")
_LOGO_PATH = _ROOT_LOGO_PATH if os.path.exists(_ROOT_LOGO_PATH) else _ASSETS_LOGO_PATH


@st.cache_data(show_spinner=False)
def _load_logo_b64(path: str) -> str:
    """Read the logo PNG and return a base64-encoded string (cached per session)."""
    try:
        with open(path, "rb") as _f:
            return base64.b64encode(_f.read()).decode()
    except Exception:
        return ""

# ─── Landing Page Theme CSS — page-level overrides ───────────
st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════
   Hero HUD: Glassmorphic, Responsive Flexbox
   ═══════════════════════════════════════════════════════════ */
.hero-hud {
    background: rgba(15,23,42,0.50);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 24px;
    box-shadow: 0 0 40px rgba(0,240,255,0.06), 0 8px 32px rgba(0,0,0,0.45);
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    gap: 28px;
}
/* Rainbow accent bar at top */
.hero-hud::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #00f0ff, #00ff9d, #FFD700, #c800ff, #00f0ff);
    background-size: 200% 100%;
    animation: headerShimmer 4s ease infinite;
}
.hero-hud-text { flex: 1; min-width: 0; }
.hero-tagline {
    font-size: clamp(1.4rem, 2.8vw, 2.2rem);
    font-weight: 800;
    font-family: 'Orbitron', sans-serif;
    color: #ffffff;
    letter-spacing: 0.04em;
    margin: 0;
    line-height: 1.3;
}
.hero-subtext {
    font-size: clamp(0.82rem, 1.2vw, 0.95rem);
    color: rgba(255,255,255,0.80);
    font-family: 'Inter', -apple-system, sans-serif;
    letter-spacing: 0.02em;
    margin-top: 10px;
    line-height: 1.5;
}
.hero-date {
    font-size: 0.82rem;
    color: rgba(148,163,184,0.80);
    margin-top: 10px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.03em;
}
.spp-hero-logo {
    width: 88px !important;
    max-width: 100%;
    height: auto;
    object-fit: contain;
    border-radius: 50%;
    box-shadow: 0 0 18px rgba(0,240,255,0.30);
    flex-shrink: 0;
}
/* Responsive: stack on mobile */
@media (max-width: 640px) {
    .hero-hud { flex-direction: column; text-align: center; padding: 24px 20px; }
    .spp-hero-logo { width: 88px !important; max-width: 100%; }
}
/* Status card — dark glass panel */
.status-card {
    background: rgba(15,23,42,0.50);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    box-shadow: 0 0 16px rgba(0,240,255,0.04), 0 4px 16px rgba(0,0,0,0.30);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}
.status-card:hover {
    border-color: rgba(0,240,255,0.20);
    transform: translateY(-3px);
    box-shadow: 0 0 24px rgba(0,240,255,0.10), 0 6px 20px rgba(0,0,0,0.40);
}
.status-card-value {
    font-size: 2rem;
    font-weight: 800;
    color: rgba(255,255,255,0.95);
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-variant-numeric: tabular-nums;
}
.status-card-label {
    font-size: 0.72rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 4px;
    font-family: 'Inter', sans-serif;
}
/* Tonight's slate team chips */
.team-chip {
    display: inline-block;
    background: rgba(0,240,255,0.05);
    color: rgba(255,255,255,0.90);
    border: 1px solid rgba(255,255,255,0.08);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    margin: 3px;
    transition: border-color 0.2s ease;
}
.team-chip:hover { border-color: rgba(0,240,255,0.25); }
/* LIVE badge with "The Pulse" dot built in */
.live-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,255,157,0.08);
    color: #00ff9d;
    border: 1px solid rgba(0,255,157,0.30);
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
}
.live-badge::before {
    content: '';
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #00ff9d;
    animation: thePulse 1.8s ease-in-out infinite;
    flex-shrink: 0;
}
.sample-badge {
    display: inline-block;
    background: rgba(255,94,0,0.08);
    color: #ff9d4d;
    border: 1px solid rgba(255,94,0,0.30);
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
}

/* ═══════════════════════════════════════════════════════════
   Joseph Welcome Card
   ═══════════════════════════════════════════════════════════ */
.joseph-welcome-card {
    background: rgba(15,23,42,0.55);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 24px 28px;
    margin: 12px 0 24px 0;
    box-shadow: 0 0 30px rgba(0,240,255,0.05), 0 6px 24px rgba(0,0,0,0.35);
    display: flex;
    align-items: flex-start;
    gap: 20px;
    position: relative;
    overflow: hidden;
}
.joseph-welcome-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #FFD700, #ff5e00, #c800ff);
    background-size: 200% 100%;
    animation: headerShimmer 5s ease infinite;
}
.joseph-welcome-avatar {
    width: 56px; height: 56px;
    border-radius: 50%;
    object-fit: cover;
    box-shadow: 0 0 12px rgba(255,215,0,0.25);
    flex-shrink: 0;
}
.joseph-welcome-text {
    flex: 1;
    min-width: 0;
}
.joseph-welcome-name {
    font-size: 0.78rem;
    color: #FFD700;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 6px;
    font-family: 'Inter', sans-serif;
}
.joseph-welcome-msg {
    font-size: 0.95rem;
    color: rgba(255,255,255,0.88);
    line-height: 1.6;
    font-style: italic;
    font-family: 'Inter', -apple-system, sans-serif;
}

/* ═══════════════════════════════════════════════════════════
   Pillar Cards (Three-column feature cards)
   ═══════════════════════════════════════════════════════════ */
.pillar-card {
    background: rgba(15,23,42,0.55);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 28px 24px;
    box-shadow: 0 0 24px rgba(0,240,255,0.04), 0 6px 20px rgba(0,0,0,0.35);
    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
    height: 100%;
}
.pillar-card:hover {
    border-color: rgba(0,240,255,0.18);
    transform: translateY(-4px);
    box-shadow: 0 0 32px rgba(0,240,255,0.08), 0 8px 28px rgba(0,0,0,0.45);
}
.pillar-icon {
    font-size: 2rem;
    margin-bottom: 10px;
}
.pillar-title {
    font-size: 1rem;
    font-weight: 700;
    color: #00f0ff;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 12px;
    font-family: 'JetBrains Mono', monospace;
}
.pillar-subtitle {
    font-size: 1.1rem;
    font-weight: 700;
    color: rgba(255,255,255,0.92);
    margin-bottom: 14px;
    line-height: 1.35;
}
.pillar-body {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.72);
    line-height: 1.65;
}
.pillar-body ul {
    list-style: none;
    padding-left: 0;
    margin: 10px 0;
}
.pillar-body ul li {
    padding: 3px 0;
    color: rgba(255,255,255,0.78);
}
.pillar-body ul li::before {
    content: '→ ';
    color: #00ff9d;
    font-weight: 700;
}
.pillar-footer {
    font-size: 0.78rem;
    color: #94A3B8;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.05);
    font-style: italic;
}

/* ═══════════════════════════════════════════════════════════
   Metric Proof Cards
   ═══════════════════════════════════════════════════════════ */
.proof-card {
    background: rgba(15,23,42,0.50);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    box-shadow: 0 0 16px rgba(0,240,255,0.04), 0 4px 16px rgba(0,0,0,0.30);
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.proof-card:hover {
    border-color: rgba(0,240,255,0.18);
    transform: translateY(-3px);
}
.proof-card-number {
    font-size: 1.6rem;
    font-weight: 800;
    color: #00f0ff;
    font-family: 'Orbitron', 'JetBrains Mono', monospace;
    margin-bottom: 6px;
}
.proof-card-label {
    font-size: 0.72rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 1px;
    line-height: 1.4;
    font-family: 'Inter', sans-serif;
}

/* ═══════════════════════════════════════════════════════════
   Pipeline Steps
   ═══════════════════════════════════════════════════════════ */
.pipeline-step {
    background: rgba(15,23,42,0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 16px 14px;
    text-align: center;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.pipeline-step.done {
    border-color: rgba(0,255,157,0.30);
    box-shadow: 0 0 18px rgba(0,255,157,0.08);
}
.pipeline-step.pending {
    border-color: rgba(255,165,0,0.30);
    box-shadow: 0 0 18px rgba(255,165,0,0.06);
    animation: amberPulse 2s ease-in-out infinite;
}
@keyframes amberPulse {
    0%, 100% { border-color: rgba(255,165,0,0.20); }
    50% { border-color: rgba(255,165,0,0.50); }
}
.pipeline-step-icon {
    font-size: 1.4rem;
    margin-bottom: 6px;
}
.pipeline-step-label {
    font-size: 0.72rem;
    color: rgba(255,255,255,0.85);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
.pipeline-step-status {
    font-size: 0.72rem;
    margin-top: 6px;
    font-family: 'JetBrains Mono', monospace;
}
.pipeline-step-status.green { color: #00ff9d; }
.pipeline-step-status.amber { color: #FFA500; }
.pipeline-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    color: rgba(255,255,255,0.25);
    font-weight: 700;
}

/* ═══════════════════════════════════════════════════════════
   How It Works Pipeline
   ═══════════════════════════════════════════════════════════ */
.hiw-stage {
    background: rgba(15,23,42,0.40);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 18px 14px;
    text-align: center;
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.hiw-stage:hover {
    border-color: rgba(0,240,255,0.15);
    transform: translateY(-2px);
}
.hiw-stage-icon { font-size: 1.6rem; margin-bottom: 8px; }
.hiw-stage-title {
    font-size: 0.7rem;
    font-weight: 700;
    color: #00f0ff;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
    font-family: 'JetBrains Mono', monospace;
}
.hiw-stage-desc {
    font-size: 0.78rem;
    color: rgba(255,255,255,0.70);
    line-height: 1.55;
}

/* ═══════════════════════════════════════════════════════════
   App Map Nav Cards
   ═══════════════════════════════════════════════════════════ */
.nav-card {
    background: rgba(15,23,42,0.50);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 16px 14px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
    height: 100%;
}
.nav-card:hover {
    border-color: rgba(0,240,255,0.25);
    transform: translateY(-3px);
    box-shadow: 0 0 20px rgba(0,240,255,0.08);
}
.nav-card-icon { font-size: 1.5rem; margin-bottom: 8px; }
.nav-card-title {
    font-size: 0.82rem;
    font-weight: 700;
    color: rgba(255,255,255,0.90);
    margin-bottom: 6px;
}
.nav-card-desc {
    font-size: 0.70rem;
    color: #94A3B8;
    line-height: 1.4;
}

/* ═══════════════════════════════════════════════════════════
   Section Headers
   ═══════════════════════════════════════════════════════════ */
.section-header {
    font-size: clamp(1.1rem, 2vw, 1.5rem);
    font-weight: 800;
    color: rgba(255,255,255,0.92);
    font-family: 'Orbitron', 'Inter', sans-serif;
    margin: 36px 0 8px 0;
    letter-spacing: 0.03em;
}
.section-subheader {
    font-size: 0.88rem;
    color: #94A3B8;
    margin-bottom: 20px;
    line-height: 1.5;
}

/* ═══════════════════════════════════════════════════════════
   Comparison Table
   ═══════════════════════════════════════════════════════════ */
.comp-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    background: rgba(15,23,42,0.40);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.05);
    margin: 16px 0 24px 0;
}
.comp-table th {
    background: rgba(0,240,255,0.06);
    color: rgba(255,255,255,0.90);
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 12px 14px;
    text-align: left;
    font-family: 'JetBrains Mono', monospace;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.comp-table td {
    padding: 10px 14px;
    font-size: 0.80rem;
    color: rgba(255,255,255,0.78);
    border-bottom: 1px solid rgba(255,255,255,0.03);
    vertical-align: top;
}
.comp-table tr:last-child td { border-bottom: none; }
.comp-table .spp-col {
    color: #00ff9d;
    font-weight: 600;
}

/* ═══════════════════════════════════════════════════════════
   Matchup card (enhanced slate)
   ═══════════════════════════════════════════════════════════ */
.matchup-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(15,23,42,0.50);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 10px 16px;
    margin: 4px;
    transition: border-color 0.2s ease;
}
.matchup-chip:hover { border-color: rgba(0,240,255,0.20); }
.matchup-meta {
    font-size: 0.70rem;
    color: #94A3B8;
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Configuration
# ============================================================

# ============================================================
# SECTION: Initialize App on Startup
# ============================================================

initialize_database()

# ── SQLite production warning ─────────────────────────────────
# Warn if running in production mode with the default SQLite path.
# SQLite is not ideal for multi-user cloud deployments.
if os.environ.get("SMARTAI_PRODUCTION", "").lower() in ("true", "1", "yes"):
    _db_path = os.environ.get("DB_PATH", "db/smartai_nba.db")
    if os.path.basename(_db_path) == "smartai_nba.db":
        logging.getLogger(__name__).warning(
            "Running in production mode with SQLite (%s). "
            "SQLite is not recommended for multi-user cloud deployments. "
            "Consider PostgreSQL or persistent storage. See docs/database_migration.md",
            _db_path,
        )
        if "sqlite_warning_shown" not in st.session_state:
            st.session_state["sqlite_warning_shown"] = True
            st.warning(
                "⚠️ **SQLite in Production Mode** — This app is running with SQLite, "
                "which may not persist data on ephemeral cloud platforms (e.g., Streamlit Cloud). "
                "See `docs/database_migration.md` for migration options."
            )

# ── Premium Status — Check and display in sidebar ─────────────
# This runs silently on app load.  is_premium_user() is cached in
# session state so it won't make Stripe API calls on every rerun.
try:
    from utils.auth import is_premium_user as _is_premium, handle_checkout_redirect as _handle_checkout
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
    # Handle checkout redirects even on the home page
    _handle_checkout()
    _user_is_premium = _is_premium()
except Exception:
    _user_is_premium = True  # Fail open — don't block the home page
    _PREM_PATH = "/14_%F0%9F%92%8E_Subscription_Level"

with st.sidebar:
    if _user_is_premium:
        st.markdown(
            '<div style="background:rgba(0,255,157,0.10);border:1px solid rgba(0,255,157,0.3);'
            'border-radius:10px;padding:10px 14px;text-align:center;margin-bottom:8px;">'
            '<span style="color:#00ff9d;font-weight:700;font-size:0.9rem;">💎 Premium Active</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="background:rgba(255,94,0,0.08);border:1px solid rgba(255,94,0,0.25);'
            f'border-radius:10px;padding:10px 14px;text-align:center;margin-bottom:8px;">'
            f'<span style="color:#a0b4d0;font-size:0.85rem;">⭐ Free Plan</span><br>'
            f'<a href="{_PREM_PATH}" style="color:#ff5e00;font-size:0.78rem;'
            f'font-weight:600;text-decoration:none;">Upgrade to Premium →</a>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── Restore user settings from database before applying defaults ───────
# On a fresh browser reload st.session_state is empty.  We read the
# user's last-saved settings from SQLite so they don't have to
# reconfigure everything.  Keys not in the DB fall through to the
# hard-coded defaults below.
_persisted = load_user_settings()  # {} on first run or on error
for _key, _val in _persisted.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ── Restore page state from database ──────────────────────────────────
# Critical page data (analysis results, picks, games, props, etc.) is
# persisted to SQLite so that an idle session timeout doesn't wipe
# the user's work.  Restore once on a fresh session.
if not st.session_state.get("_page_state_restored"):
    st.session_state["_page_state_restored"] = True
    _page_state = load_page_state()  # {} on first run or on error
    for _key, _val in _page_state.items():
        if _key not in st.session_state:
            st.session_state[_key] = _val
        elif isinstance(st.session_state[_key], (list, dict)) and not st.session_state[_key] and _val:
            # Replace empty defaults with saved non-empty data
            st.session_state[_key] = _val

if "simulation_depth" not in st.session_state:
    st.session_state["simulation_depth"] = 1000
if "minimum_edge_threshold" not in st.session_state:
    st.session_state["minimum_edge_threshold"] = 5.0
if "entry_fee" not in st.session_state:
    st.session_state["entry_fee"] = 10.0
if "total_bankroll" not in st.session_state:
    st.session_state["total_bankroll"] = 1000.0
if "kelly_multiplier" not in st.session_state:
    st.session_state["kelly_multiplier"] = 0.25
if "selected_platforms" not in st.session_state:
    st.session_state["selected_platforms"] = [
        "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
    ]
if "todays_games" not in st.session_state:
    st.session_state["todays_games"] = []
if "analysis_results" not in st.session_state:
    st.session_state["analysis_results"] = []
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "session_props" not in st.session_state:
    st.session_state["session_props"] = []
if "loaded_live_picks" not in st.session_state:
    st.session_state["loaded_live_picks"] = []

# ═══ Joseph M. Smith Session State ═══
st.session_state.setdefault("joseph_enabled", True)
st.session_state.setdefault("joseph_used_fragments", set())
st.session_state.setdefault("joseph_bets_logged", False)
st.session_state.setdefault("joseph_results", [])
st.session_state.setdefault("joseph_widget_mode", None)
st.session_state.setdefault("joseph_widget_selection", None)
st.session_state.setdefault("joseph_widget_response", None)
st.session_state.setdefault("joseph_ambient_line", "")
st.session_state.setdefault("joseph_ambient_context", "idle")
st.session_state.setdefault("joseph_last_commentary", "")
st.session_state.setdefault("joseph_entry_just_built", False)

# ── Global Settings Popover (accessible from sidebar) ─────────
from utils.components import render_global_settings, inject_joseph_floating, render_joseph_hero_banner
with st.sidebar:
    render_global_settings()
st.session_state["joseph_page_context"] = "page_home"
inject_joseph_floating()

# ============================================================
# END SECTION: Initialize App on Startup
# ============================================================

# ============================================================
# SECTION 1: Cinematic Hero — Joseph Banner + Hero HUD + CTA
# ============================================================

# Joseph M. Smith Hero Banner — full-width visual hook at absolute top
render_joseph_hero_banner()

today_str = datetime.date.today().strftime("%A, %B %d, %Y")
todays_games = st.session_state.get("todays_games", [])
game_count = len(todays_games)
game_count_text = (
    f"🏟️ {game_count} game{'s' if game_count != 1 else ''} tonight"
    if game_count
    else "🏟️ No games loaded yet"
)

# Embed logo using cached base64 load — root-level high-res version
_logo_b64 = _load_logo_b64(_LOGO_PATH) if os.path.exists(_LOGO_PATH) else ""

_logo_img_tag = (
    f'<img src="data:image/png;base64,{_logo_b64}" class="spp-hero-logo" alt="Smart Pick Pro logo" />'
    if _logo_b64 else ""
)

st.markdown(f"""
<div class="hero-hud ss-fade-in-up">
  {_logo_img_tag}
  <div class="hero-hud-text">
    <div class="hero-tagline">THE SMARTEST NBA PLAYER PROP ENGINE ONLINE</div>
    <div class="hero-subtext">Find Tonight's Best Bets in 60 Seconds. Every Pick Tells You Why.</div>
    <div class="hero-date">📅 {today_str} &nbsp;&bull;&nbsp; {game_count_text}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── ⚡ One-Click Setup CTA — Primary hero action ────────────────
_home_one_click = st.button(
    "⚡ LOAD TONIGHT'S SLATE — ONE CLICK",
    key="home_one_click_btn",
    type="primary",
    use_container_width=True,
    help="Loads tonight's games, rosters, injuries, and live props from all platforms in one click.",
)
if _home_one_click:
    progress = st.progress(0, "Loading tonight's games...")
    try:
        from data.nba_data_service import get_todays_games as _hoc_fg, get_todays_players as _hoc_fp
        from data.data_manager import (
            clear_all_caches as _hoc_cc,
            load_injury_status as _hoc_li,
        )
        progress.progress(25, "Fetching rosters & injuries...")
        _hoc_games = _hoc_fg()
        if _hoc_games:
            st.session_state["todays_games"] = _hoc_games
        else:
            _hoc_games = st.session_state.get("todays_games", [])
        _hoc_fp(_hoc_games)
        _hoc_cc()
        try:
            st.session_state["injury_status_map"] = _hoc_li()
        except Exception:
            pass
        progress.progress(50, "Pulling live props from all platforms...")
        try:
            from data.sportsbook_service import get_all_sportsbook_props as _hoc_fap
            from data.data_manager import (
                save_platform_props_to_session as _hoc_sps,
                save_props_to_session as _hoc_sp,
            )
            _hoc_live = _hoc_fap(
                include_prizepicks=True,
                include_underdog=True,
                include_draftkings=True,
            )
            progress.progress(75, "Enriching player data...")
            if _hoc_live:
                _hoc_sps(_hoc_live, st.session_state)
                _hoc_sp(_hoc_live, st.session_state)
                _hoc_total = len(st.session_state.get("current_props", []))
                progress.progress(100, "✅ Ready! Head to ⚡ Quantum Analysis")
                st.success(f"✅ Setup complete! {len(_hoc_games)} games · {_hoc_total} props loaded. Go to ⚡ Quantum Analysis.")
            else:
                progress.progress(100, "✅ Ready! Head to ⚡ Quantum Analysis")
                st.success(f"✅ Setup complete! {len(_hoc_games)} games loaded. Go to ⚡ Quantum Analysis.")
        except Exception as _hoc_plat_err:
            _hoc_err_str = str(_hoc_plat_err)
            if "WebSocketClosedError" in _hoc_err_str or "StreamClosedError" in _hoc_err_str:
                pass
            else:
                progress.progress(100, "✅ Games loaded!")
                st.success(f"✅ Setup complete! {len(_hoc_games)} games loaded. Go to ⚡ Quantum Analysis.")
    except Exception as _hoc_err:
        _hoc_err_str = str(_hoc_err)
        if "WebSocketClosedError" in _hoc_err_str or "StreamClosedError" in _hoc_err_str:
            pass
        else:
            st.error(f"❌ One-Click Setup failed: {_hoc_err}")

# ============================================================
# END SECTION 1: Cinematic Hero
# ============================================================

# ============================================================
# SECTION 2: Joseph's Welcome — The Personality Hook
# ============================================================

# Load Joseph avatar for welcome card
@st.cache_data(show_spinner=False)
def _load_joseph_avatar_b64() -> str:
    """Load the Joseph M Smith Avatar and return base64-encoded string."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "Joseph M Smith Avatar.png"),
        os.path.join(_this, "assets", "Joseph M Smith Avatar.png"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            try:
                with open(norm, "rb") as fh:
                    return base64.b64encode(fh.read()).decode("utf-8")
            except Exception:
                pass
    return ""

_joseph_avatar_b64 = _load_joseph_avatar_b64()
_joseph_avatar_tag = (
    f'<img src="data:image/png;base64,{_joseph_avatar_b64}" class="joseph-welcome-avatar" alt="Joseph M. Smith" />'
    if _joseph_avatar_b64 else '<div class="joseph-welcome-avatar" style="background:#1e293b;display:flex;align-items:center;justify-content:center;font-size:1.5rem;">🎙️</div>'
)

# Dynamic message based on session state
_analysis_results = st.session_state.get("analysis_results", [])
_games_loaded = len(todays_games)

if _analysis_results:
    _platinum_count = sum(1 for r in _analysis_results if r.get("tier", "").lower() == "platinum")
    _gold_count = sum(1 for r in _analysis_results if r.get("tier", "").lower() == "gold")
    _avoid_count = sum(1 for r in _analysis_results if r.get("tier", "").lower() == "avoid")
    _joseph_msg = (
        f"We've got {_platinum_count} Platinum lock{'s' if _platinum_count != 1 else ''} "
        f"and {_gold_count} Gold play{'s' if _gold_count != 1 else ''} tonight. "
        f"I flagged {_avoid_count} trap{'s' if _avoid_count != 1 else ''} to skip. "
        f"The house doesn't know what's coming."
    )
elif _games_loaded:
    _joseph_msg = (
        f"I see {_games_loaded} game{'s' if _games_loaded != 1 else ''} on the board tonight. "
        f"The lines are up. Run the engine and let me show you where the sportsbooks made mistakes."
    )
else:
    _joseph_msg = (
        "The board is dark. Hit that button and load tonight's slate — "
        "I've been watching the lines ALL DAY and I already see where the books slipped up. "
        "Let's go to work."
    )

st.markdown(f"""
<div class="joseph-welcome-card ss-fade-in-up">
  {_joseph_avatar_tag}
  <div class="joseph-welcome-text">
    <div class="joseph-welcome-name">🎙️ Joseph M. Smith — AI Analyst</div>
    <div class="joseph-welcome-msg">"{_joseph_msg}"</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# END SECTION 2: Joseph's Welcome
# ============================================================

# ============================================================
# SECTION 3: The Competitive Kill Shot — "Why Smart Pick Pro Wins"
# ============================================================

st.markdown("""
<div class="section-header">Most Prop Tools Give You a Number. We Give You the Proof.</div>
<div class="section-subheader">Three things no other prop tool on the internet can match.</div>
""", unsafe_allow_html=True)

# ── 3A: Three Pillars ───────────────────────────────────────────
_p1, _p2, _p3 = st.columns(3)

with _p1:
    st.markdown("""
    <div class="pillar-card">
      <div class="pillar-icon">🎲</div>
      <div class="pillar-title">Quantum Matrix Engine</div>
      <div class="pillar-subtitle">Thousands of Simulated Games Per Prop</div>
      <div class="pillar-body">
        Every prop runs through thousands of simulated game scenarios — randomized
        minutes, game flow, momentum swings, and real-world chaos.
        <br><br>
        The result: a probability distribution built from YOUR player in TONIGHT'S
        specific matchup — not a generic average.
        <br><br>
        <strong>You choose the depth:</strong>
        <ul>
          <li>⚡ Fast (seconds)</li>
          <li>🎯 Standard (recommended)</li>
          <li>🔬 Deep Scan (maximum accuracy)</li>
        </ul>
        <ul>
          <li>Percentile ranges (10th–90th)</li>
          <li>Probability gauges</li>
          <li>Confidence intervals</li>
          <li>Distribution histograms</li>
        </ul>
      </div>
      <div class="pillar-footer">Other tools: one number. No context.</div>
    </div>
    """, unsafe_allow_html=True)

with _p2:
    st.markdown("""
    <div class="pillar-card">
      <div class="pillar-icon">🔬</div>
      <div class="pillar-title">Force Analysis</div>
      <div class="pillar-subtitle">Every Pick Tells You WHY</div>
      <div class="pillar-body">
        Every prop shows the exact factors pushing performance UP or DOWN:
        <br><br>
        ✅ Matchup quality<br>
        ✅ Game environment &amp; pace<br>
        ✅ Rest &amp; fatigue impact<br>
        ✅ Blowout / garbage time risk<br>
        ✅ Market consensus signals<br>
        ✅ Trend &amp; regression detection
        <br><br>
        Plus our proprietary <strong>Trap Line Detection</strong> system that catches lines
        designed to bait public money on the wrong side.
        <br><br>
        You see OVER forces vs UNDER forces, each with a strength rating.
        No black box. Full transparency.
      </div>
      <div class="pillar-footer">Other tools: "63% confidence." That's it.</div>
    </div>
    """, unsafe_allow_html=True)

with _p3:
    st.markdown("""
    <div class="pillar-card">
      <div class="pillar-icon">🏆</div>
      <div class="pillar-title">SAFE Score™</div>
      <div class="pillar-subtitle">Institutional-Grade Scoring</div>
      <div class="pillar-body">
        <em>Statistical Analysis of Force &amp; Edge</em>
        <br><br>
        A proprietary 0–100 composite score that weighs multiple independent signals
        — probability, edge quality, matchup, consistency, momentum, and more —
        into one actionable number.
        <br><br>
        <strong>Built-in safeguards</strong> prevent the engine from being overconfident:
        <br><br>
        🛡️ Automatic tier demotion triggers<br>
        🛡️ Variance-aware scoring<br>
        🛡️ Sample-size adjustments<br>
        🛡️ Tier distribution enforcement
        <br><br>
        💎 Platinum · 🥇 Gold · 🥈 Silver · 🥉 Bronze · ⛔ Avoid
      </div>
      <div class="pillar-footer">Other tools: one number, no safeguards.</div>
    </div>
    """, unsafe_allow_html=True)

# ── 3B: Comparison Table ────────────────────────────────────────
st.markdown("""
<div style="margin-top:28px;">
<table class="comp-table">
  <thead>
    <tr>
      <th>What You Get</th>
      <th>Free Spreadsheet</th>
      <th>Typical Prop Tool</th>
      <th>Smart Pick Pro</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Simulation Engine</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Proprietary Quantum Matrix Simulation</td>
    </tr>
    <tr>
      <td>Why a Pick Wins</td>
      <td>❌ Guessing</td>
      <td>❌ "63% confidence"</td>
      <td class="spp-col">✅ Full force breakdown — every factor shown</td>
    </tr>
    <tr>
      <td>Trap Detection</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Proprietary multi-pattern trap system</td>
    </tr>
    <tr>
      <td>Scoring System</td>
      <td>❌ None</td>
      <td>❌ Single number</td>
      <td class="spp-col">✅ SAFE Score™ — multi-signal composite with tier safeguards</td>
    </tr>
    <tr>
      <td>AI Analyst</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Joseph M. Smith — pre-game, in-game, and post-game commentary</td>
    </tr>
    <tr>
      <td>Risk Assessment</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Risk ratings + auto-flagging on every pick</td>
    </tr>
    <tr>
      <td>Parlay Optimizer</td>
      <td>❌ Manual</td>
      <td>❌ Basic</td>
      <td class="spp-col">✅ EV-optimized Entry Builder across all major platforms</td>
    </tr>
    <tr>
      <td>Live Tracking</td>
      <td>❌ Box score</td>
      <td>❌ Box score</td>
      <td class="spp-col">✅ Live Sweat Room with real-time pace and projection tracking</td>
    </tr>
    <tr>
      <td>Performance Tracking</td>
      <td>❌ None</td>
      <td>❌ None</td>
      <td class="spp-col">✅ Bet Tracker + Model Health Dashboard</td>
    </tr>
    <tr>
      <td>Platforms Supported</td>
      <td>❌ One</td>
      <td>❌ One or two</td>
      <td class="spp-col">✅ PrizePicks · Underdog · DraftKings Pick6 and more</td>
    </tr>
  </tbody>
</table>
</div>
""", unsafe_allow_html=True)

st.divider()

# ============================================================
# END SECTION 3: The Competitive Kill Shot
# ============================================================

# ============================================================
# SECTION 4: The Proof Points — Animated Metric Cards
# ============================================================

st.markdown('<div class="section-header">The Numbers Speak</div>', unsafe_allow_html=True)

_proof_cols = st.columns(5)

_proof_data = [
    ("THOUSANDS", "Simulated Games Per Prop"),
    ("MULTIPLE", "Analysis Models Blended"),
    ("EVERY", "Pick Explains WHY"),
    ("15", "Pages of Tools"),
    ("REAL TIME", "Live Props"),
]

for i, (_num, _label) in enumerate(_proof_data):
    with _proof_cols[i]:
        st.markdown(f"""
        <div class="proof-card">
          <div class="proof-card-number">{_num}</div>
          <div class="proof-card-label">{_label}</div>
        </div>
        """, unsafe_allow_html=True)

# 6th dynamic card — tracked performance if data exists
try:
    from utils.joseph_widget import joseph_get_track_record
    _track_record = joseph_get_track_record()
    if _track_record.get("total", 0) > 10:
        st.metric(
            "Tracked Win Rate",
            f"{_track_record['win_rate']:.0f}%",
            delta=f"{_track_record['total']} picks tracked",
        )
except Exception:
    pass

st.divider()

# ============================================================
# END SECTION 4: The Proof Points
# ============================================================

# ============================================================
# SECTION 5: Session Readiness Pipeline
# ============================================================

st.markdown('<div class="section-header">Your Session</div>', unsafe_allow_html=True)

_sess_games = len(st.session_state.get("todays_games", []))
_sess_props = len(st.session_state.get("current_props", []))
_sess_analysis = len(st.session_state.get("analysis_results", []))
_sess_entries = len(st.session_state.get("selected_picks", []))

def _step_class(done: bool) -> str:
    return "done" if done else "pending"

def _step_icon(done: bool) -> str:
    return "✅" if done else "⏳"

_s1_done = _sess_games > 0
_s2_done = _sess_props > 0
_s3_done = _sess_analysis > 0
_s4_done = _sess_entries > 0

_pc1, _pa1, _pc2, _pa2, _pc3, _pa3, _pc4 = st.columns([3, 1, 3, 1, 3, 1, 3])

with _pc1:
    st.markdown(f"""
    <div class="pipeline-step {_step_class(_s1_done)}">
      <div class="pipeline-step-icon">①</div>
      <div class="pipeline-step-label">Load Games</div>
      <div class="pipeline-step-status {'green' if _s1_done else 'amber'}">{_step_icon(_s1_done)} {_sess_games} game{'s' if _sess_games != 1 else ''}</div>
    </div>
    """, unsafe_allow_html=True)

with _pa1:
    st.markdown('<div class="pipeline-arrow">→</div>', unsafe_allow_html=True)

with _pc2:
    st.markdown(f"""
    <div class="pipeline-step {_step_class(_s2_done)}">
      <div class="pipeline-step-icon">②</div>
      <div class="pipeline-step-label">Load Props</div>
      <div class="pipeline-step-status {'green' if _s2_done else 'amber'}">{_step_icon(_s2_done)} {_sess_props} prop{'s' if _sess_props != 1 else ''}</div>
    </div>
    """, unsafe_allow_html=True)

with _pa2:
    st.markdown('<div class="pipeline-arrow">→</div>', unsafe_allow_html=True)

with _pc3:
    st.markdown(f"""
    <div class="pipeline-step {_step_class(_s3_done)}">
      <div class="pipeline-step-icon">③</div>
      <div class="pipeline-step-label">Run Engine</div>
      <div class="pipeline-step-status {'green' if _s3_done else 'amber'}">{_step_icon(_s3_done)} {_sess_analysis if _sess_analysis else 'Not run'}</div>
    </div>
    """, unsafe_allow_html=True)

with _pa3:
    st.markdown('<div class="pipeline-arrow">→</div>', unsafe_allow_html=True)

with _pc4:
    st.markdown(f"""
    <div class="pipeline-step {_step_class(_s4_done)}">
      <div class="pipeline-step-icon">④</div>
      <div class="pipeline-step-label">Build Entries</div>
      <div class="pipeline-step-status {'green' if _s4_done else 'amber'}">{_step_icon(_s4_done)} {_sess_entries if _sess_entries else '—'}</div>
    </div>
    """, unsafe_allow_html=True)

# ── Consolidated warnings (stale data / validation) — single amber banner ──
_consolidated_warnings = []
try:
    from data.nba_data_service import load_last_updated as _load_lu
    _last_updated = _load_lu() or {}
    _teams_ts = _last_updated.get("teams_stats")
    if _teams_ts:
        import datetime as _dt
        _teams_date = _dt.datetime.fromisoformat(_teams_ts)
        _teams_age_days = (_dt.datetime.now() - _teams_date).days
        if _teams_age_days >= 7:
            _consolidated_warnings.append(
                f"Team stats are **{_teams_age_days} days old**. "
                f"Go to **📡 Data Feed → Smart Update** to refresh."
            )
        elif _teams_age_days >= 3:
            _consolidated_warnings.append(
                f"Team stats last updated {_teams_age_days} days ago. "
                f"Consider refreshing on the Data Feed page."
            )
    else:
        from data.data_manager import load_teams_data as _load_teams
        _teams_data_check = _load_teams()
        if not _teams_data_check:
            _consolidated_warnings.append(
                "No team stats found. Go to **📡 Data Feed → Smart Update** "
                "to load team data for accurate analysis."
            )
except Exception as _exc:
    logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

try:
    from data.validators import validate_players_csv, validate_teams_csv
    from data.data_manager import load_players_data as _lp_val, load_teams_data as _lt_val
    _val_players = _lp_val()
    _val_teams = _lt_val()
    _p_errors = validate_players_csv(_val_players)
    _t_errors = validate_teams_csv(_val_teams)
    if _p_errors or _t_errors:
        for e in _p_errors:
            _consolidated_warnings.append(f"players.csv: {e}")
        for e in _t_errors:
            _consolidated_warnings.append(f"teams.csv: {e}")
except Exception as _exc:
    logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

try:
    from data.nba_data_service import get_teams_staleness_warning
    _staleness_warn = get_teams_staleness_warning()
    if _staleness_warn:
        st.sidebar.warning(_staleness_warn)
except Exception as _exc:
    logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

if _consolidated_warnings:
    with st.expander("⚠️ Data Warnings", expanded=False):
        for _w in _consolidated_warnings:
            st.warning(_w)

st.divider()

# ============================================================
# END SECTION 5: Session Readiness Pipeline
# ============================================================

# ============================================================
# SECTION 6: How It Works — High-Level 5-Stage Pipeline
# ============================================================

st.markdown("""
<div class="section-header">How It Works</div>
<div class="section-subheader">Five stages. Full transparency on what happens. Zero implementation details exposed.</div>
""", unsafe_allow_html=True)

_hiw_stages = [
    ("📡", "Data Ingest",
     "We pull real-time NBA data from multiple sources — player stats, team ratings, injuries, and live prop lines from every major platform."),
    ("📐", "Smart Projections",
     "Our engine adjusts each player's baseline for tonight's specific matchup, game environment, rest, and real-time conditions."),
    ("🎲", "Quantum Matrix Engine",
     "Thousands of game simulations for each prop — every sim randomizes the chaos of a real NBA game to build a true probability distribution."),
    ("🔬", "Edge Analysis",
     "Every directional force is identified, strength-rated, and balanced against opposing signals. Trap lines are flagged. Coin-flip bets are caught."),
    ("🏆", "SAFE Score™",
     "A proprietary multi-signal composite score with built-in safeguards assigns every pick a tier: Platinum, Gold, Silver, Bronze, or Avoid."),
]

_hiw_cols = st.columns(len(_hiw_stages) * 2 - 1)  # stages + arrows between them
for idx, (icon, title, desc) in enumerate(_hiw_stages):
    col_idx = idx * 2
    with _hiw_cols[col_idx]:
        st.markdown(f"""
        <div class="hiw-stage">
          <div class="hiw-stage-icon">{icon}</div>
          <div class="hiw-stage-title">{title}</div>
          <div class="hiw-stage-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
    if idx < 4:
        with _hiw_cols[col_idx + 1]:
            st.markdown('<div class="pipeline-arrow" style="height:100%;display:flex;align-items:center;justify-content:center;">→</div>', unsafe_allow_html=True)

with st.expander("📖 How to Use Smart Pick Pro", expanded=False):
    st.markdown("""
    **Recommended Workflow**
    1. **📡 Live Games** — Click "⚡ Load Tonight's Slate" for a one-click setup
    2. **🔬 Prop Scanner** — Enter props manually or load live lines from all platforms
    3. **⚡ Quantum Analysis** — Run the engine on your props
    4. **🧬 Entry Builder** — Build EV-optimized parlays
    5. **📈 Bet Tracker** — Log results and track performance over time

    💡 **Pro Tip:** Use the one-click button at the top of this page to load games + props in a single action.
    Then head straight to ⚡ Quantum Analysis to run the engine.
    """)

st.divider()

# ============================================================
# END SECTION 6: How It Works
# ============================================================

# ============================================================
# SECTION 7: App Map — Interactive Navigation Cards
# ============================================================

st.markdown("""
<div class="section-header">🗺️ Your Toolkit — 15 Pages of Analysis</div>
<div class="section-subheader">Every tool you need, from data loading to bet tracking.</div>
""", unsafe_allow_html=True)

# Row 1 — Tonight's Workflow
st.markdown("**Tonight's Workflow**")
_nav_r1 = st.columns(4)
_nav_row1 = [
    ("📡", "Live Games", "Load tonight's slate in one click", "pages/1_📡_Live_Games.py"),
    ("🔬", "Prop Scanner", "Enter props manually or pull live lines", "pages/2_🔬_Prop_Scanner.py"),
    ("⚡", "Quantum Analysis", "Run the Quantum Matrix Engine", "pages/3_⚡_Quantum_Analysis_Matrix.py"),
    ("🧬", "Entry Builder", "Build EV-optimized parlays", "pages/6_🧬_Entry_Builder.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row1):
    with _nav_r1[i]:
        st.markdown(f"""
        <div class="nav-card">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

# Row 2 — Deep Analysis
st.markdown("**Deep Analysis**")
_nav_r2 = st.columns(5)
_nav_row2 = [
    ("📋", "Game Report", "Full game breakdowns", "pages/4_📋_Game_Report.py"),
    ("🔮", "Player Simulator", "What-if scenarios", "pages/5b_🔮_Player_Simulator.py"),
    ("🗺️", "Correlation Matrix", "Find correlated props", "pages/10_🗺️_Correlation_Matrix.py"),
    ("🛡️", "Risk Shield", "See what to avoid + why", "pages/8_🛡️_Risk_Shield.py"),
    ("🎙️", "The Studio", "Joseph's AI analysis room", "pages/7_🎙️_The_Studio.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row2):
    with _nav_r2[i]:
        st.markdown(f"""
        <div class="nav-card">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

# Row 3 — Track & Manage
st.markdown("**Track & Manage**")
_nav_r3 = st.columns(6)
_nav_row3 = [
    ("💦", "Live Sweat", "Track bets in real-time", "pages/0_💦_Live_Sweat.py"),
    ("📈", "Bet Tracker", "Log results, track ROI", "pages/11_📈_Bet_Tracker.py"),
    ("📊", "Backtester", "Validate model accuracy", "pages/12_📊_Backtester.py"),
    ("📡", "Data Feed", "Update player/team data", "pages/9_📡_Data_Feed.py"),
    ("⚙️", "Settings", "Tune engine parameters", "pages/13_⚙️_Settings.py"),
    ("💎", "Premium", "Unlock everything", "pages/14_💎_Subscription_Level.py"),
]
for i, (icon, name, desc, page) in enumerate(_nav_row3):
    with _nav_r3[i]:
        st.markdown(f"""
        <div class="nav-card">
          <div class="nav-card-icon">{icon}</div>
          <div class="nav-card-title">{name}</div>
          <div class="nav-card-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        st.page_link(page, label=f"Open {name}", icon=icon)

st.divider()

# ============================================================
# END SECTION 7: App Map
# ============================================================

# ============================================================
# SECTION 8: Tonight's Slate — Enhanced Matchup Cards
# ============================================================

if todays_games:
    st.markdown('<div class="section-header">🏟️ Tonight\'s Slate</div>', unsafe_allow_html=True)

    chips_html = ""
    for game in todays_games:
        away = game.get("away_team", "")
        home = game.get("home_team", "")
        aw = game.get("away_wins", 0)
        al = game.get("away_losses", 0)
        hw = game.get("home_wins", 0)
        hl = game.get("home_losses", 0)
        rec_a = f" ({aw}-{al})" if aw or al else ""
        rec_h = f" ({hw}-{hl})" if hw or hl else ""

        # Enhanced metadata line — spread, total, game time
        _spread = game.get("spread", "")
        _total = game.get("total", "")
        _game_time = game.get("game_time", "")
        _meta_parts = []
        if _spread:
            _meta_parts.append(f"Spread: {_spread}")
        if _total:
            _meta_parts.append(f"O/U: {_total}")
        if _game_time:
            _meta_parts.append(_game_time)
        _meta_line = f'<div class="matchup-meta">{" · ".join(_meta_parts)}</div>' if _meta_parts else ""

        chips_html += (
            f'<span class="matchup-chip">'
            f'<span>🚌 <strong>{away}</strong>{rec_a}</span>'
            f'<span style="color:#c800ff; font-weight:700; margin:0 6px;">vs</span>'
            f'<span>🏠 <strong>{home}</strong>{rec_h}</span>'
            f'{_meta_line}'
            f'</span> '
        )

    st.markdown(f'<div style="margin:8px 0 12px 0;display:flex;flex-wrap:wrap;gap:8px;">{chips_html}</div>', unsafe_allow_html=True)
    st.divider()

# ============================================================
# END SECTION 8: Tonight's Slate
# ============================================================

# ============================================================
# SECTION 9: Status Dashboard — Streamlined (for returning users)
# ============================================================

players_data = load_players_data()
props_data = load_props_data()
teams_data = load_teams_data()

current_props = st.session_state.get("current_props", props_data)
number_of_current_props = len(current_props)
number_of_analysis_results = len(st.session_state.get("analysis_results", []))

# Live data status
live_data_timestamps = load_last_updated()
is_using_live_data = live_data_timestamps.get("is_live", False)
data_badge = '<span class="live-badge">LIVE</span>' if is_using_live_data else '<span class="sample-badge">📊 SAMPLE</span>'

with st.expander("📊 Status Dashboard", expanded=False):
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{len(players_data)}</div>
          <div class="status-card-label">👤 Players</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{number_of_current_props}</div>
          <div class="status-card-label">🎯 Props</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        val3 = str(game_count) if game_count else "—"
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{val3}</div>
          <div class="status-card-label">🏟️ Games Tonight</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        val4 = str(number_of_analysis_results) if number_of_analysis_results else "—"
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value">{val4}</div>
          <div class="status-card-label">📈 Analyzed</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="status-card">
          <div class="status-card-value" style="font-size:1.1rem; padding-top:8px;">{data_badge}</div>
          <div class="status-card-label">Data Source</div>
        </div>
        """, unsafe_allow_html=True)

    # ── System Health — consolidated into status ───────────────────
    try:
        from data.data_manager import get_data_health_report
        _health = get_data_health_report()

        st.markdown("---")
        hc1, hc2, hc3, hc4 = st.columns(4)
        hc1.metric("👥 Players", _health["players_count"])
        hc2.metric("🏀 Teams", _health["teams_count"])
        hc3.metric("📋 Props", _health["props_count"])
        _freshness_label = f"{_health['days_old']}d old" if _health.get("last_updated") else "Never"
        hc4.metric("🕐 Data Age", _freshness_label,
                   delta="⚠️ Stale" if _health["is_stale"] else "✅ Fresh",
                   delta_color="inverse" if _health["is_stale"] else "normal")

        if _health["warnings"]:
            for w in _health["warnings"]:
                st.warning(w)
        else:
            st.success("✅ All data files present and fresh.")

        st.caption("Go to **📡 Data Feed** to refresh data.")
    except Exception as _exc:
        logging.getLogger(__name__).warning(f"[App] Setup step failed: {_exc}")

    # ── Live Data Status ────────────────────────────────────────────
    if is_using_live_data:
        player_ts = live_data_timestamps.get("players")
        team_ts = live_data_timestamps.get("teams")

        def format_timestamp(ts_string):
            if not ts_string:
                return "never"
            try:
                dt = datetime.datetime.fromisoformat(ts_string)
                return dt.strftime("%b %d at %I:%M %p")
            except Exception:
                return "unknown"

        st.success(
            f"✅ **Using Live NBA Data** — "
            f"Players: {format_timestamp(player_ts)} | "
            f"Teams: {format_timestamp(team_ts)}"
        )
    else:
        st.info(
            "📊 **No live data loaded yet** — Go to the **📡 Data Feed** page to pull "
            "real, up-to-date NBA stats for accurate predictions!"
        )

# ============================================================
# END SECTION 9: Status Dashboard
# ============================================================

# ============================================================
# SECTION 10: Legal Disclaimer + Footer
# ============================================================

with st.expander("⚠️ Important Legal Disclaimer — Please Read", expanded=False):
    st.markdown("""
    ## ⚠️ IMPORTANT DISCLAIMER
    
    **SmartBetPro NBA ("Smart Pick Pro")** is an analytical tool for **entertainment and educational purposes only**. This application does NOT guarantee profits or winning outcomes.
    
    - 📊 Past performance does not guarantee future results
    - 🔢 All predictions are based on statistical models that have inherent limitations  
    - 💰 Sports betting involves significant financial risk — **never bet more than you can afford to lose**
    - 🔞 You must be **21+** (or legal age in your jurisdiction) to participate in sports betting
    - ⚠️ This tool is **not affiliated** with the NBA or any sportsbook
    - 🆘 Always gamble responsibly. If you or someone you know has a gambling problem, call **1-800-GAMBLER (1-800-426-2537)**
    
    **By using this application, you acknowledge that all betting decisions are your own responsibility.**
    
    ---
    
    **Responsible Gaming Resources:**
    - 📞 **National Problem Gambling Helpline: 1-800-GAMBLER (1-800-426-2537)** — 24/7 confidential support
    - 📞 National Council on Problem Gambling: **1-800-522-4700** — crisis counseling & referrals
    - 🌐 [www.ncpgambling.org](https://www.ncpgambling.org)
    - 🌐 [www.begambleaware.org](https://www.begambleaware.org)
    """)

st.caption(
    f"© {datetime.datetime.now().year} Smart Pick Pro | NBA Edition | "
    f"For entertainment & educational purposes only. Not financial advice. "
    f"Bet responsibly. 21+ | 1-800-GAMBLER"
)

# ============================================================
# END SECTION 10: Footer
# ============================================================
