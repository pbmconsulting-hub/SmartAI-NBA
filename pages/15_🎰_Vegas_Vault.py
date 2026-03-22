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
import json as _json
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

# ─── Joseph Hero Banner ──────────────────────────────────────
try:
    from utils.components import render_joseph_hero_banner, inject_joseph_floating
    render_joseph_hero_banner()
    inject_joseph_floating()
except ImportError:
    try:
        from utils.components import inject_joseph_floating
        inject_joseph_floating()
    except Exception:
        pass
except Exception:
    pass

# ─── Joseph sidebar widget ───────────────────────────────────
try:
    from utils.joseph_widget import render_joseph_sidebar_widget
    render_joseph_sidebar_widget()
except ImportError:
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
    from engine.odds_engine import implied_probability_to_american_odds
    _REVERSE_ODDS_AVAILABLE = True
except ImportError:
    _REVERSE_ODDS_AVAILABLE = False
    implied_probability_to_american_odds = None

try:
    from utils.auth import is_premium_user as _is_premium_user
except ImportError:
    def _is_premium_user():
        return True

try:
    from utils.premium_gate import premium_gate as _premium_gate
    _PREMIUM_GATE_AVAILABLE = True
except ImportError:
    _PREMIUM_GATE_AVAILABLE = False

try:
    from styles.theme import get_education_box_html
    _EDUCATION_BOX_AVAILABLE = True
except ImportError:
    _EDUCATION_BOX_AVAILABLE = False
    get_education_box_html = None

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False
    pd = None


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
    animation: headerShimmer 3s ease-in-out infinite;
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
    animation: godModeGlow 2s ease-in-out infinite alternate;
}
@keyframes godModeGlow {
    from { box-shadow: 0 0 15px rgba(200,0,255,0.15); }
    to   { box-shadow: 0 0 30px rgba(200,0,255,0.30), 0 0 60px rgba(200,0,255,0.08); }
}

/* Standard EV card */
.ev-card {
    background: rgba(10,15,26,0.85);
    border: 1px solid rgba(0,240,255,0.20);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    transition: border-color 0.3s, transform 0.2s, box-shadow 0.3s;
}
.ev-card:hover {
    border-color: rgba(0,240,255,0.50);
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0,240,255,0.10);
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
.badge-side-over {
    background: rgba(0,255,157,0.12);
    color: #00ff9d;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-side-under {
    background: rgba(255,94,0,0.12);
    color: #ff5e00;
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

/* Calculator panel */
.calc-panel {
    background: rgba(10,15,26,0.90);
    border: 1px solid rgba(0,240,255,0.15);
    border-radius: 12px;
    padding: 1.5rem;
}
.calc-result {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
    text-align: center;
    padding: 0.8rem;
    border-radius: 8px;
    margin-top: 0.5rem;
}
.calc-result-prob {
    color: #00ff9d;
    background: rgba(0,255,157,0.08);
    border: 1px solid rgba(0,255,157,0.25);
}
.calc-result-odds {
    color: #00f0ff;
    background: rgba(0,240,255,0.08);
    border: 1px solid rgba(0,240,255,0.25);
}

/* Breakdown detail row */
.detail-row {
    display: flex;
    justify-content: space-between;
    padding: 0.4rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 0.88rem;
}
.detail-label { color: #8a9bb8; }
.detail-value { color: #e0e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600; }

/* Probability bar */
.prob-bar-container {
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    height: 8px;
    margin: 0.3rem 0;
    overflow: hidden;
}
.prob-bar-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.5s ease;
}

/* Recommended side badge */
.badge-rec {
    background: linear-gradient(90deg, #00c6ff, #0072ff);
    color: #fff;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin-left: 6px;
}
/* Fair probability highlight */
.fair-prob-tag {
    color: #ffb347;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    font-weight: 600;
}
/* Vig indicator */
.vig-tag {
    color: #ff5e5e;
    font-size: 0.78rem;
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


# ── Premium Gate ──────────────────────────────────────────────
if _PREMIUM_GATE_AVAILABLE:
    if not _premium_gate("Vegas Vault"):
        st.stop()
else:
    if not _is_premium_user():
        st.warning("🔒 Vegas Vault is a **Premium** feature. Upgrade to unlock the full arbitrage scanner.")
        st.stop()

# ── Module availability check ────────────────────────────────
if not _ODDS_CLIENT_AVAILABLE or not _MATCHER_AVAILABLE:
    st.error("⚠️ Required modules not available. Please check your installation.")
    st.stop()

# ── Education Box ─────────────────────────────────────────────
with st.expander("📖 How to Use Vegas Vault", expanded=False):
    if _EDUCATION_BOX_AVAILABLE and get_education_box_html is not None:
        st.markdown(get_education_box_html(
            "Understanding the Vegas Vault",
            """
            <strong>What it does:</strong> The Vegas Vault scans player prop lines across multiple
            sportsbooks (DraftKings, FanDuel, BetMGM, etc.) and identifies pricing discrepancies
            where one book's odds imply a significantly higher probability than the market average.<br><br>

            <strong>EV Edge:</strong> Expected Value edge — the difference between the implied probability
            and a fair 50/50 market. An edge of +10% means the implied probability is 60%, well above
            break-even. Only edges ≥ +7% are shown.<br><br>

            <strong>God Mode Locks 🔒:</strong> Props where the best available odds imply ≥ 60% probability
            (American odds ≤ −150). These represent the strongest pricing discrepancies on the board.<br><br>

            <strong>Implied Probability:</strong> What the odds "imply" about the likelihood of an outcome.
            −150 odds imply 60% probability. −200 odds imply 66.7% probability. +150 odds imply 40%.<br><br>

            <strong>How to act:</strong> God Mode Locks are the highest-conviction finds. Look for props
            where multiple books are pricing the line but one book has significantly stronger odds than
            the rest. These windows typically close within hours as market makers re-calibrate.
            """
        ), unsafe_allow_html=True)
    else:
        st.markdown("""
        **What it does:** Scans player prop lines across sportsbooks to find EV discrepancies.

        **EV Edge:** Implied probability minus 50%. Only edges ≥ +7% are shown.

        **God Mode Locks 🔒:** Props where implied probability ≥ 60% (odds ≤ −150).

        **How to act:** Focus on God Mode Locks — these are the strongest finds and close fast.
        """)


# ============================================================
# SECTION 2: Sidebar Controls & Scan Panel
# ============================================================

# ── Sidebar filters ───────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Vault Settings")

    persona_mode = st.selectbox(
        "AI Persona",
        ["joseph", "professor"],
        format_func=lambda x: "🎙️ Joseph M. Smith" if x == "joseph" else "🎓 The Professor",
        key="vault_persona_select",
    )

    min_ev_edge = st.slider(
        "Min EV Edge (%)",
        min_value=7,
        max_value=25,
        value=7,
        step=1,
        help="Only show discrepancies with EV edge ≥ this threshold.",
        key="vault_min_edge",
    )

    stat_options = [
        "All Stats", "points", "rebounds", "assists",
        "threes", "steals", "blocks", "turnovers",
        "points_rebounds", "points_assists", "rebounds_assists",
        "points_rebounds_assists",
    ]
    stat_filter = st.selectbox(
        "Stat Type Filter",
        stat_options,
        index=0,
        key="vault_stat_filter",
    )

    god_mode_only = st.checkbox(
        "God Mode Locks Only 🔒",
        value=False,
        key="vault_god_mode_only",
    )

    st.divider()

    # ── API quota display ─────────────────────────────────────
    st.subheader("📡 API Status")
    if get_odds_api_usage is not None:
        try:
            usage = get_odds_api_usage()
            remaining = usage.get("requests_remaining", "—")
            used = usage.get("requests_used", "—")
            updated = usage.get("updated_at", "—")
            st.metric("Requests Remaining", remaining)
            st.metric("Requests Used", used)
            if updated and updated != "—":
                st.caption(f"Updated: {updated}")
        except Exception:
            st.metric("Requests Remaining", "—")
    else:
        st.caption("API client not available.")

# ── Scan button (main area) ──────────────────────────────────
scan_col1, scan_col2 = st.columns([3, 1])

with scan_col1:
    scan_btn = st.button(
        "🔍 Scan for EV Discrepancies",
        type="primary",
        use_container_width=True,
    )

with scan_col2:
    scan_time_display = st.session_state.get("vault_scan_time", "")
    if scan_time_display:
        st.markdown(
            f'<p style="text-align:center; color:#8a9bb8; padding-top:0.5rem;">'
            f'Last scan: <strong>{_html.escape(str(scan_time_display))}</strong></p>',
            unsafe_allow_html=True,
        )


# ============================================================
# SECTION 3: Main Scan Logic & Results
# ============================================================

if scan_btn:
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
            st.session_state["vault_scan_time"] = datetime.datetime.now().strftime(
                "%I:%M %p"
            )
            st.session_state["vault_total_props"] = len(raw_props)

# ── Load results from session state ───────────────────────────
_all_discrepancies = st.session_state.get("vault_discrepancies", [])
persona = st.session_state.get("vault_mode", persona_mode)
scan_time = st.session_state.get("vault_scan_time", "")
total_props = st.session_state.get("vault_total_props", 0)

# ── Apply sidebar filters to results ─────────────────────────
discrepancies = _all_discrepancies
if discrepancies:
    # Filter by min EV edge
    discrepancies = [d for d in discrepancies if d.get("ev_edge", 0) >= min_ev_edge]

    # Filter by stat type
    if stat_filter != "All Stats":
        discrepancies = [
            d for d in discrepancies
            if d.get("stat_type", "").lower() == stat_filter.lower()
        ]

    # Filter by God Mode only
    if god_mode_only:
        discrepancies = [d for d in discrepancies if d.get("is_god_mode_lock")]


if discrepancies or scan_time:

    # ── Section 3a: Summary metrics ───────────────────────────
    st.markdown("---")
    god_mode_count = sum(1 for d in discrepancies if d.get("is_god_mode_lock"))
    avg_edge = (
        round(sum(d["ev_edge"] for d in discrepancies) / len(discrepancies), 1)
        if discrepancies
        else 0
    )
    top_edge = discrepancies[0]["ev_edge"] if discrepancies else 0
    total_unfiltered = len(_all_discrepancies)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Props Scanned", f"{total_props:,}")
    m2.metric("EV Edges Found", f"{len(discrepancies)}/{total_unfiltered}")
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
            emoji = "🎙️" if persona == "joseph" else "🎓"
            st.markdown(
                f'<div class="joseph-vault-box">{emoji} {escaped}</div>',
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
            over_prob = d.get("best_over_implied_prob", 0)
            under_prob = d.get("best_under_implied_prob", 0)
            max_prob = max(over_prob, under_prob)
            side = d.get("recommended_side", "OVER" if over_prob >= under_prob else "UNDER")
            rec_book = d.get("recommended_book", "")
            best_book = rec_book or (d["best_over_book"] if side == "OVER" else d["best_under_book"])
            best_odds = d["best_over_odds"] if side == "OVER" else d["best_under_odds"]
            fair_prob = d.get("fair_probability", max_prob)
            true_edge = d.get("true_ev_edge", d["ev_edge"])
            vig = d.get("vig_pct", 0)

            player_esc = _html.escape(str(d["player_name"]))
            stat_esc = _html.escape(
                str(d["stat_type"]).replace("_", " ").title()
            )
            book_esc = _html.escape(str(best_book))

            # Probability bar color
            bar_color = "#c800ff" if max_prob >= 65 else "#00ff9d"

            st.markdown(f"""
            <div class="god-mode-card">
                <span class="badge-god">🔒 GOD MODE LOCK</span>
                <span class="badge-edge">+{d['ev_edge']}% Edge</span>
                <span class="badge-rec">▶ {side}</span>
                <h3 style="margin:0.6rem 0 0.3rem 0; color:#fff;">
                    {player_esc} — {stat_esc} {d['true_line']}
                </h3>
                <div class="prob-bar-container">
                    <div class="prob-bar-fill" style="width:{min(max_prob, 100):.0f}%; background:{bar_color};"></div>
                </div>
                <p style="margin:0; color:#c0d0e8;">
                    Play <strong>{side}</strong> at <span class="badge-book">{book_esc}</span>
                    ({best_odds}) &bull;
                    <span class="fair-prob-tag">{fair_prob:.1f}% fair</span>
                    (true edge +{true_edge}%)
                    &bull; {d['book_count']} books
                    {f'&bull; <span class="vig-tag">{vig:.1f}% vig</span>' if vig > 0 else ''}
                </p>
            </div>
            """, unsafe_allow_html=True)

            # Expandable detail breakdown
            with st.expander(
                f"📋 Full Breakdown — {d['player_name']}",
                expanded=False,
            ):
                bc1, bc2 = st.columns(2)
                with bc1:
                    st.markdown("**📈 OVER Side**")
                    _fo_prob = d.get("fair_over_prob", 0)
                    st.markdown(f"""
                    <div class="detail-row"><span class="detail-label">Book</span>
                    <span class="detail-value">{_html.escape(str(d['best_over_book']))}</span></div>
                    <div class="detail-row"><span class="detail-label">American Odds</span>
                    <span class="detail-value">{d['best_over_odds']}</span></div>
                    <div class="detail-row"><span class="detail-label">Implied Prob</span>
                    <span class="detail-value">{d['best_over_implied_prob']:.1f}%</span></div>
                    <div class="detail-row"><span class="detail-label">Fair Prob (no vig)</span>
                    <span class="detail-value fair-prob-tag">{_fo_prob:.1f}%</span></div>
                    """, unsafe_allow_html=True)
                with bc2:
                    st.markdown("**📉 UNDER Side**")
                    _fu_prob = d.get("fair_under_prob", 0)
                    st.markdown(f"""
                    <div class="detail-row"><span class="detail-label">Book</span>
                    <span class="detail-value">{_html.escape(str(d['best_under_book']))}</span></div>
                    <div class="detail-row"><span class="detail-label">American Odds</span>
                    <span class="detail-value">{d['best_under_odds']}</span></div>
                    <div class="detail-row"><span class="detail-label">Implied Prob</span>
                    <span class="detail-value">{d['best_under_implied_prob']:.1f}%</span></div>
                    <div class="detail-row"><span class="detail-label">Fair Prob (no vig)</span>
                    <span class="detail-value fair-prob-tag">{_fu_prob:.1f}%</span></div>
                    """, unsafe_allow_html=True)
                st.markdown(f"""
                <div class="detail-row"><span class="detail-label">True Line</span>
                <span class="detail-value">{d['true_line']}</span></div>
                <div class="detail-row"><span class="detail-label">Stat Type</span>
                <span class="detail-value">{stat_esc}</span></div>
                <div class="detail-row"><span class="detail-label">Books Pricing</span>
                <span class="detail-value">{d['book_count']}</span></div>
                <div class="detail-row"><span class="detail-label">EV Edge (vigged)</span>
                <span class="detail-value" style="color:#00ff9d;">+{d['ev_edge']}%</span></div>
                <div class="detail-row"><span class="detail-label">True Edge (devigged)</span>
                <span class="detail-value fair-prob-tag">+{true_edge}%</span></div>
                <div class="detail-row"><span class="detail-label">Recommended</span>
                <span class="detail-value" style="color:#00c6ff;">▶ {side} at {book_esc}</span></div>
                {f'<div class="detail-row"><span class="detail-label">Vig</span><span class="detail-value vig-tag">{vig:.1f}%</span></div>' if vig > 0 else ''}
                """, unsafe_allow_html=True)

    # ── Section 3d: All EV Discrepancies Table ────────────────
    st.markdown("### 📊 All EV Discrepancies")

    if not discrepancies:
        st.info(
            "No edges above the current filter threshold. "
            "Try lowering the Min EV Edge in the sidebar."
        )
    else:
        # Tabular data view
        if _PANDAS_AVAILABLE:
            table_data = []
            for d in discrepancies:
                rec_side = d.get("recommended_side", (
                    "OVER"
                    if d.get("best_over_implied_prob", 0)
                    >= d.get("best_under_implied_prob", 0)
                    else "UNDER"
                ))
                table_data.append({
                    "Player": d["player_name"],
                    "Stat": str(d["stat_type"]).replace("_", " ").title(),
                    "Line": d["true_line"],
                    "▶ Play": rec_side,
                    "▶ Book": d.get("recommended_book", ""),
                    "Fair Prob%": d.get("fair_probability", 0),
                    "True Edge%": d.get("true_ev_edge", d["ev_edge"]),
                    "Over Odds": d["best_over_odds"],
                    "Over Book": d["best_over_book"],
                    "Under Odds": d["best_under_odds"],
                    "Under Book": d["best_under_book"],
                    "EV Edge%": d["ev_edge"],
                    "Vig%": d.get("vig_pct", 0),
                    "God Mode": "🔒" if d.get("is_god_mode_lock") else "",
                    "Books": d["book_count"],
                })
            df_table = pd.DataFrame(table_data)
            st.dataframe(
                df_table,
                hide_index=True,
                use_container_width=True,
            )

            # Download button
            csv_data = df_table.to_csv(index=False)
            st.download_button(
                "⬇️ Download Discrepancies (CSV)",
                data=csv_data,
                file_name=f"vegas_vault_{datetime.date.today().isoformat()}.csv",
                mime="text/csv",
            )

        # Card view
        with st.expander("🃏 Card View", expanded=not _PANDAS_AVAILABLE):
            for d in discrepancies:
                if d.get("is_god_mode_lock"):
                    card_class = "god-mode-card"
                    badge = '<span class="badge-god">🔒 GOD MODE</span> '
                else:
                    card_class = "ev-card"
                    badge = ""

                _rec = d.get("recommended_side", "")
                _rec_badge = f'<span class="badge-rec">▶ {_rec}</span>' if _rec else ""

                player_esc = _html.escape(str(d["player_name"]))
                stat_esc = _html.escape(
                    str(d["stat_type"]).replace("_", " ").title()
                )
                over_book_esc = _html.escape(str(d["best_over_book"]))
                under_book_esc = _html.escape(str(d["best_under_book"]))
                over_prob = d.get("best_over_implied_prob", 0)
                under_prob = d.get("best_under_implied_prob", 0)
                _fp = d.get("fair_probability", 0)
                _te = d.get("true_ev_edge", d["ev_edge"])

                st.markdown(f"""
                <div class="{card_class}">
                    {badge}<span class="badge-edge">+{d['ev_edge']}% EV Edge</span>
                    {_rec_badge}
                    <h4 style="margin:0.5rem 0 0.3rem 0; color:#fff;">
                        {player_esc} — {stat_esc} {d['true_line']}
                    </h4>
                    <p style="margin:0; color:#c0d0e8; font-size:0.9rem;">
                        📈 OVER: <span class="badge-side-over">{over_book_esc}</span>
                        {d['best_over_odds']} ({over_prob:.1f}%)
                        &nbsp;&nbsp;|&nbsp;&nbsp;
                        📉 UNDER: <span class="badge-side-under">{under_book_esc}</span>
                        {d['best_under_odds']} ({under_prob:.1f}%)
                        &nbsp;&nbsp;|&nbsp;&nbsp;
                        📚 {d['book_count']} books
                        {f'&nbsp;&nbsp;|&nbsp;&nbsp; <span class="fair-prob-tag">{_fp:.1f}% fair</span>' if _fp > 0 else ''}
                    </p>
                </div>
                """, unsafe_allow_html=True)

    # ── Section 3e: EV Edge Distribution ──────────────────────
    if discrepancies and _PANDAS_AVAILABLE:
        st.markdown("### 📈 Edge Distribution")
        df_chart = pd.DataFrame(discrepancies)
        chart_df = df_chart[["player_name", "ev_edge"]].copy()
        chart_df = chart_df.rename(columns={"player_name": "Player", "ev_edge": "EV Edge %"})
        chart_df = chart_df.set_index("Player")
        st.bar_chart(chart_df, color="#00ff9d")

    # ── Section 3f: Export full JSON ──────────────────────────
    if discrepancies:
        with st.expander("🗄️ Raw Data (JSON)", expanded=False):
            st.json(discrepancies)
            json_export = _json.dumps(discrepancies, indent=2)
            st.download_button(
                "⬇️ Download Full Data (JSON)",
                data=json_export,
                file_name=f"vegas_vault_full_{datetime.date.today().isoformat()}.json",
                mime="application/json",
                key="vault_json_download",
            )

elif not scan_time:
    # ── Empty state ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; padding:3rem 0; color:#8a9bb8;">
        <p style="font-size:3rem; margin-bottom:0.5rem;">🎰</p>
        <h3 style="color:#c0d0e8; margin-bottom:0.5rem;">Ready to Scan</h3>
        <p>Click <strong>Scan for EV Discrepancies</strong> to fetch live odds across
        sportsbooks and surface arbitrage opportunities.</p>
        <p style="font-size:0.85rem; margin-top:1rem;">
        Use the sidebar controls to adjust filters before or after scanning.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# SECTION 4: Implied Probability Calculator & Tools
# ============================================================

st.markdown("---")
st.markdown("### 🧮 Odds & Probability Tools")

tool_tab1, tool_tab2, tool_tab3 = st.tabs([
    "🎲 Odds → Probability",
    "📊 Probability → Odds",
    "📐 EV Formula Reference",
])

# ── Tab 1: American Odds → Implied Probability ───────────────
with tool_tab1:
    st.markdown(
        "Convert **American odds** to **implied probability**. "
        "Enter odds like −110, +150, −200, etc."
    )
    calc_col1, calc_col2 = st.columns(2)

    with calc_col1:
        odds_input = st.number_input(
            "American Odds",
            min_value=-10000,
            max_value=10000,
            value=-110,
            step=5,
            key="calc_odds_input",
        )
    with calc_col2:
        if calculate_implied_probability is not None:
            prob_result = calculate_implied_probability(odds_input)
            # Determine if favourite or underdog
            if odds_input < 0:
                label = "Favourite"
                label_color = "#00ff9d"
            else:
                label = "Underdog"
                label_color = "#ff5e00"
            st.markdown(
                f'<div class="calc-result calc-result-prob">'
                f'{prob_result:.2f}%</div>'
                f'<p style="text-align:center; color:{label_color}; '
                f'font-size:0.85rem; margin-top:0.3rem;">{label}</p>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Calculator not available — odds client not loaded.")

    # Quick reference
    st.markdown("**Quick Reference:**")
    ref_data = {
        "Odds": ["-110", "-150", "-200", "-300", "+100", "+150", "+200", "+300"],
        "Implied Prob": [
            "52.4%", "60.0%", "66.7%", "75.0%",
            "50.0%", "40.0%", "33.3%", "25.0%",
        ],
        "Meaning": [
            "Slight favourite",
            "Moderate favourite",
            "Strong favourite",
            "Heavy favourite",
            "Even money",
            "Moderate underdog",
            "Strong underdog",
            "Heavy underdog",
        ],
    }
    if _PANDAS_AVAILABLE:
        st.dataframe(
            pd.DataFrame(ref_data),
            hide_index=True,
            use_container_width=True,
        )

# ── Tab 2: Probability → American Odds ───────────────────────
with tool_tab2:
    st.markdown(
        "Convert **implied probability** to **American odds**. "
        "Enter a probability between 1% and 99%."
    )
    calc2_col1, calc2_col2 = st.columns(2)

    with calc2_col1:
        prob_input = st.number_input(
            "Implied Probability (%)",
            min_value=1.0,
            max_value=99.0,
            value=55.0,
            step=0.5,
            key="calc_prob_input",
        )
    with calc2_col2:
        if _REVERSE_ODDS_AVAILABLE and implied_probability_to_american_odds is not None:
            odds_result = implied_probability_to_american_odds(prob_input / 100.0)
            sign = "+" if odds_result > 0 else ""
            st.markdown(
                f'<div class="calc-result calc-result-odds">'
                f'{sign}{odds_result:.0f}</div>'
                f'<p style="text-align:center; color:#8a9bb8; '
                f'font-size:0.85rem; margin-top:0.3rem;">American Odds</p>',
                unsafe_allow_html=True,
            )
        elif calculate_implied_probability is not None:
            # Fallback: simple reverse calculation
            p = prob_input / 100.0
            if p >= 0.5:
                odds_result = -(p / (1.0 - p)) * 100.0
            else:
                odds_result = ((1.0 - p) / p) * 100.0
            sign = "+" if odds_result > 0 else ""
            st.markdown(
                f'<div class="calc-result calc-result-odds">'
                f'{sign}{odds_result:.0f}</div>'
                f'<p style="text-align:center; color:#8a9bb8; '
                f'font-size:0.85rem; margin-top:0.3rem;">American Odds</p>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Calculator not available.")

# ── Tab 3: EV Formula Reference ──────────────────────────────
with tool_tab3:
    st.markdown("""
    #### Expected Value (EV) Edge Formula

    The Vegas Vault uses this process to find edges:

    **Step 1 — Implied Probability from American Odds:**
    """)
    st.code("""
# Favourite (negative odds, e.g. -150):
implied_prob = |odds| / (|odds| + 100)
# Example: |-150| / (|-150| + 100) = 150/250 = 0.60 (60%)

# Underdog (positive odds, e.g. +150):
implied_prob = 100 / (odds + 100)
# Example: 100 / (150 + 100) = 100/250 = 0.40 (40%)
    """, language="python")

    st.markdown("""
    **Step 2 — Find Best Odds Across Books:**

    For each player prop (same player, same stat, same line), find the
    single best OVER odds and single best UNDER odds across all sportsbooks.

    **Step 3 — EV Edge Calculation:**
    """)
    st.code("""
ev_edge = max(over_implied_prob, under_implied_prob) - 50.0
# Example: max(60.0, 47.5) - 50.0 = 10.0% edge
    """, language="python")

    st.markdown("""
    **Step 4 — Filters:**
    - Only show props with **EV edge ≥ 7%** (implied prob ≥ 57%)
    - Flag **God Mode Locks** when any side has implied prob ≥ 60% (odds ≤ −150)
    - Sort by EV edge descending — strongest edges first

    **Step 5 — Cross-Book Triangulation:**

    The key insight is that sportsbooks price lines differently. When DraftKings
    prices a player's Over at −160 (61.5% implied) but FanDuel has the same prop
    at −130 (56.5% implied), DraftKings is telling you something the market hasn't
    fully priced in yet. That's your edge.
    """)

