# ============================================================
# FILE: pages/15_🎰_Vegas_Vault.py
# PURPOSE: Vegas Vault — Arbitrage Dashboard.
#          Surfaces EV discrepancies across sportsbook player
#          props, highlights God Mode Locks, and delivers
#          Joseph M. Smith's sharp-money commentary.
# CONNECTS TO: engine/arbitrage_matcher.py, engine/joseph_brain.py,
#              data/odds_api_client.py, utils/auth.py
# ============================================================

import streamlit as st
import datetime
import html as _html

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(page_title="Vegas Vault", page_icon="🎰", layout="wide")

# ─── Inject Global CSS Theme ──────────────────────────────────
try:
    from styles.theme import get_global_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
except ImportError:
    pass

# ─── Joseph floating widget ──────────────────────────────────
try:
    from utils.joseph_widget import render_joseph_sidebar_widget
    render_joseph_sidebar_widget()
except ImportError:
    pass

try:
    from utils.components import inject_joseph_floating
    inject_joseph_floating()
except Exception:
    pass

# ─── Engine / data imports ────────────────────────────────────
try:
    from data.odds_api_client import (
        fetch_player_props,
        calculate_implied_probability,
        get_odds_api_usage,
    )
    _ODDS_CLIENT_AVAILABLE = True
except ImportError:
    _ODDS_CLIENT_AVAILABLE = False
    fetch_player_props = None
    calculate_implied_probability = None
    get_odds_api_usage = None

try:
    from engine.arbitrage_matcher import find_ev_discrepancies
    _MATCHER_AVAILABLE = True
except ImportError:
    _MATCHER_AVAILABLE = False
    find_ev_discrepancies = None

try:
    from engine.joseph_brain import joseph_vault_reaction
    _JOSEPH_AVAILABLE = True
except ImportError:
    _JOSEPH_AVAILABLE = False
    joseph_vault_reaction = None

try:
    from utils.auth import is_premium_user as _is_premium_user
except ImportError:
    def _is_premium_user():
        return True

try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
except Exception:
    _PREM_PATH = "/14_%F0%9F%92%8E_Subscription_Level"


# ============================================================
# SECTION 0: Custom CSS for Vegas Vault
# ============================================================

st.markdown("""
<style>
/* ── Vegas Vault Custom Styles ──────────────────────────────── */
.vault-header {
    text-align: center;
    padding: 1.5rem 0 1rem 0;
}
.vault-header h1 {
    font-family: 'Orbitron', monospace;
    font-size: 2.2rem;
    background: linear-gradient(90deg, #ff5e00, #ffb347, #ff5e00);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.vault-header p {
    color: #8a9bb8;
    font-size: 0.95rem;
}

/* God Mode Lock card glow */
.god-mode-card {
    background: linear-gradient(135deg, rgba(200,0,255,0.12), rgba(0,240,255,0.08));
    border: 1px solid rgba(200,0,255,0.50);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 0 20px rgba(200,0,255,0.15);
}

/* Standard EV card */
.ev-card {
    background: rgba(10,15,26,0.85);
    border: 1px solid rgba(0,240,255,0.20);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    transition: border-color 0.3s;
}
.ev-card:hover {
    border-color: rgba(0,240,255,0.50);
}

/* Badge styles */
.badge-god {
    background: linear-gradient(90deg, #c800ff, #ff00ff);
    color: #fff;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.badge-edge {
    background: rgba(0,255,157,0.15);
    color: #00ff9d;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
}
.badge-book {
    background: rgba(0,240,255,0.12);
    color: #00f0ff;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}

/* Metric highlight */
.vault-metric {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
    color: #00ff9d;
}
.vault-metric-label {
    font-size: 0.78rem;
    color: #8a9bb8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Joseph reaction box */
.joseph-vault-box {
    background: linear-gradient(135deg, rgba(255,94,0,0.08), rgba(255,94,0,0.03));
    border-left: 3px solid #ff5e00;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.2rem;
    margin: 1rem 0;
    font-style: italic;
    color: #e0e8f0;
    line-height: 1.6;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# SECTION 1: Header
# ============================================================

st.markdown("""
<div class="vault-header">
    <h1>🎰 Vegas Vault</h1>
    <p>Cross-book arbitrage scanner &bull; EV discrepancy engine &bull; Sharp money signals</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# SECTION 2: Scan Controls
# ============================================================

_is_premium = _is_premium_user()

if not _ODDS_CLIENT_AVAILABLE or not _MATCHER_AVAILABLE:
    st.error("⚠️ Required modules not available. Please check your installation.")
    st.stop()

col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])

with col_ctrl1:
    scan_btn = st.button("🔍 Scan for EV Discrepancies", type="primary", use_container_width=True)

with col_ctrl2:
    persona_mode = st.selectbox(
        "AI Persona",
        ["joseph", "professor"],
        format_func=lambda x: "🎙️ Joseph M. Smith" if x == "joseph" else "🎓 The Professor",
    )

with col_ctrl3:
    if get_odds_api_usage is not None:
        try:
            usage = get_odds_api_usage()
            remaining = usage.get("requests_remaining", "—")
            st.metric("API Calls Left", remaining)
        except Exception:
            st.metric("API Calls Left", "—")


# ============================================================
# SECTION 3: Main Scan Logic & Results
# ============================================================

if scan_btn:
    if not _is_premium:
        st.warning("🔒 Vegas Vault is a **Premium** feature. Upgrade to unlock the full arbitrage scanner.")
        st.markdown(f"[💎 Upgrade to Premium]({_PREM_PATH})")
        st.stop()

    with st.spinner("🎰 Scanning sportsbooks for EV discrepancies..."):
        try:
            raw_props = fetch_player_props()
        except Exception as exc:
            _logger.warning("Vegas Vault: fetch_player_props failed: %s", exc)
            raw_props = []

        if not raw_props:
            st.info("📭 No player props available right now. Check back closer to game time.")
        else:
            try:
                discrepancies = find_ev_discrepancies(raw_props)
            except Exception as exc:
                _logger.warning("Vegas Vault: find_ev_discrepancies failed: %s", exc)
                discrepancies = []

            # Store in session state for persistence
            st.session_state["vault_discrepancies"] = discrepancies
            st.session_state["vault_mode"] = persona_mode
            st.session_state["vault_scan_time"] = datetime.datetime.now().strftime("%I:%M %p")
            st.session_state["vault_total_props"] = len(raw_props)

# ── Display results from session state ────────────────────────
discrepancies = st.session_state.get("vault_discrepancies", [])
persona = st.session_state.get("vault_mode", persona_mode if 'persona_mode' in dir() else "joseph")
scan_time = st.session_state.get("vault_scan_time", "")
total_props = st.session_state.get("vault_total_props", 0)

if discrepancies or scan_time:

    # ── Section 3a: Summary metrics ───────────────────────────
    st.markdown("---")
    god_mode_count = sum(1 for d in discrepancies if d.get("is_god_mode_lock"))
    avg_edge = round(sum(d["ev_edge"] for d in discrepancies) / len(discrepancies), 1) if discrepancies else 0
    top_edge = discrepancies[0]["ev_edge"] if discrepancies else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Props Scanned", f"{total_props:,}")
    m2.metric("EV Edges Found", len(discrepancies))
    m3.metric("God Mode Locks 🔒", god_mode_count)
    m4.metric("Top Edge", f"+{top_edge}%")
    m5.metric("Avg Edge", f"+{avg_edge}%")

    if scan_time:
        st.caption(f"Last scan: {scan_time}")

    # ── Section 3b: Joseph / Professor reaction ───────────────
    if _JOSEPH_AVAILABLE and joseph_vault_reaction is not None:
        try:
            reaction = joseph_vault_reaction(discrepancies, mode=persona)
            escaped = _html.escape(reaction)
            st.markdown(
                f'<div class="joseph-vault-box">🎙️ {escaped}</div>',
                unsafe_allow_html=True,
            )
        except Exception as exc:
            _logger.debug("Vault reaction failed: %s", exc)

    # ── Section 3c: God Mode Locks ────────────────────────────
    god_locks = [d for d in discrepancies if d.get("is_god_mode_lock")]
    if god_locks:
        st.markdown("### 🔒 God Mode Locks")
        st.caption("Implied probability ≥ 60% — the strongest edges on the board.")

        for d in god_locks:
            max_prob = max(d["best_over_implied_prob"], d["best_under_implied_prob"])
            side = "OVER" if d["best_over_implied_prob"] >= d["best_under_implied_prob"] else "UNDER"
            best_book = d["best_over_book"] if side == "OVER" else d["best_under_book"]
            best_odds = d["best_over_odds"] if side == "OVER" else d["best_under_odds"]

            player_esc = _html.escape(str(d["player_name"]))
            stat_esc = _html.escape(str(d["stat_type"]).replace("_", " ").title())
            book_esc = _html.escape(str(best_book))

            st.markdown(f"""
            <div class="god-mode-card">
                <span class="badge-god">🔒 GOD MODE LOCK</span>
                <span class="badge-edge">+{d['ev_edge']}% Edge</span>
                <h3 style="margin:0.6rem 0 0.3rem 0; color:#fff;">
                    {player_esc} — {stat_esc} {d['true_line']}
                </h3>
                <p style="margin:0; color:#c0d0e8;">
                    Best {side}: <span class="badge-book">{book_esc}</span>
                    at <strong>{best_odds}</strong>
                    ({max_prob:.1f}% implied) &bull; {d['book_count']} books pricing
                </p>
            </div>
            """, unsafe_allow_html=True)

    # ── Section 3d: All EV Discrepancies Table ────────────────
    st.markdown("### 📊 All EV Discrepancies")

    if not discrepancies:
        st.info("No edges above the +7% EV threshold right now. Check back later.")
    else:
        for d in discrepancies:
            if d.get("is_god_mode_lock"):
                card_class = "god-mode-card"
                badge = '<span class="badge-god">🔒 GOD MODE</span> '
            else:
                card_class = "ev-card"
                badge = ""

            player_esc = _html.escape(str(d["player_name"]))
            stat_esc = _html.escape(str(d["stat_type"]).replace("_", " ").title())
            over_book_esc = _html.escape(str(d["best_over_book"]))
            under_book_esc = _html.escape(str(d["best_under_book"]))

            st.markdown(f"""
            <div class="{card_class}">
                {badge}<span class="badge-edge">+{d['ev_edge']}% EV Edge</span>
                <h4 style="margin:0.5rem 0 0.3rem 0; color:#fff;">
                    {player_esc} — {stat_esc} {d['true_line']}
                </h4>
                <p style="margin:0; color:#c0d0e8; font-size:0.9rem;">
                    📈 OVER: <span class="badge-book">{over_book_esc}</span>
                    {d['best_over_odds']} ({d['best_over_implied_prob']:.1f}%)
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    📉 UNDER: <span class="badge-book">{under_book_esc}</span>
                    {d['best_under_odds']} ({d['best_under_implied_prob']:.1f}%)
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    📚 {d['book_count']} books
                </p>
            </div>
            """, unsafe_allow_html=True)

    # ── Section 3e: EV Edge Distribution ──────────────────────
    if discrepancies:
        st.markdown("### 📈 Edge Distribution")
        try:
            import pandas as pd
            df = pd.DataFrame(discrepancies)
            chart_df = df[["player_name", "ev_edge"]].copy()
            chart_df = chart_df.set_index("player_name")
            st.bar_chart(chart_df, color="#00ff9d")
        except ImportError:
            st.caption("Install pandas for edge distribution chart.")
        except Exception:
            pass

elif not scan_time:
    # ── Empty state ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; padding:3rem 0; color:#8a9bb8;">
        <p style="font-size:3rem; margin-bottom:0.5rem;">🎰</p>
        <h3 style="color:#c0d0e8; margin-bottom:0.5rem;">Ready to Scan</h3>
        <p>Click <strong>Scan for EV Discrepancies</strong> to fetch live odds across
        sportsbooks and surface arbitrage opportunities.</p>
    </div>
    """, unsafe_allow_html=True)
