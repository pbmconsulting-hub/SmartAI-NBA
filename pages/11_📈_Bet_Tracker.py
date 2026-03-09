# ============================================================
# FILE: pages/11_📈_Bet_Tracker.py
# PURPOSE: Log bets, track results, and forecast performance
#          for tonight's slate using the AI analysis results.
# CONNECTS TO: tracking/bet_tracker.py, tracking/database.py
# ============================================================

import streamlit as st
import datetime

from tracking.bet_tracker import (
    log_new_bet,
    record_bet_result,
    get_model_performance_stats,
    auto_resolve_bet_results,
)
from tracking.database import load_all_bets, initialize_database
from styles.theme import get_global_css, get_qds_css

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Bet Tracker — SmartBetPro NBA",
    page_icon="📈",
    layout="wide",
)

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# Ensure DB is initialised
initialize_database()

# ── Auto-resolve bets older than 24 hours on page load ───────
_auto_resolved_on_load = False
try:
    import datetime as _dt
    _yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    _all_bets_check = load_all_bets(limit=500)
    _pending_old = [
        b for b in _all_bets_check
        if not b.get("result") and b.get("bet_date", "") <= _yesterday
    ]
    if _pending_old:
        _dates_to_resolve = sorted({b.get("bet_date", "") for b in _pending_old if b.get("bet_date")})
        _total_resolved = 0
        for _d in _dates_to_resolve:
            _cnt, _ = auto_resolve_bet_results(date_str=_d)
            _total_resolved += _cnt
        if _total_resolved > 0:
            _auto_resolved_on_load = True
            st.toast(f"🤖 Auto-resolved {_total_resolved} past bet(s) on page load.")
except Exception as _ar_err:
    pass  # Auto-resolve on load is best-effort

st.title("📈 Bet Tracker & Performance Predictor")
st.markdown(
    "Log your picks, mark results, and see forward-looking performance predictions "
    "based on tonight's analysis."
)
st.divider()

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Tabs
# ============================================================

tab_log, tab_bets, tab_ai_picks, tab_auto_resolve, tab_predict = st.tabs([
    "➕ Log a Bet",
    "📋 My Bets",
    "📊 AI Picks",
    "🤖 Auto-Resolve",
    "🔮 Performance Predictor",
])

# ============================================================
# SECTION: Log a Bet
# ============================================================

with tab_log:
    st.subheader("➕ Log a New Bet")

    analysis_results = st.session_state.get("analysis_results", [])
    player_options = ["— type manually —"]
    if analysis_results:
        player_options += sorted({
            r.get("player_name", "") for r in analysis_results
            if r.get("player_name")
        })

    with st.form("log_bet_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            selected_player = st.selectbox("Player (from tonight's analysis)", player_options)
            manual_player = st.text_input("Or enter player name manually", placeholder="e.g., LeBron James")
            stat_type = st.selectbox(
                "Stat Type",
                ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"],
            )
            prop_line = st.number_input("Line", min_value=0.0, max_value=200.0, value=24.5, step=0.5)
            direction = st.radio("Direction", ["OVER", "UNDER"], horizontal=True)

        with col2:
            platform = st.selectbox("Platform", ["PrizePicks", "Underdog", "DraftKings"])
            tier = st.selectbox("Tier", ["Platinum", "Gold", "Silver", "Bronze"])
            entry_fee = st.number_input("Entry Fee ($)", min_value=0.0, max_value=10000.0, value=10.0, step=5.0)
            team = st.text_input("Team (optional)", placeholder="e.g., LAL")
            notes = st.text_input("Notes (optional)", placeholder="e.g., revenge game, back-to-back")

        # Pre-fill confidence / probability from analysis results
        confidence_score = 0.0
        probability_over = 0.5
        edge_percentage = 0.0
        final_player = manual_player.strip() if manual_player.strip() else (
            selected_player if selected_player != "— type manually —" else ""
        )
        if final_player and analysis_results:
            for r in analysis_results:
                if r.get("player_name", "").lower() == final_player.lower():
                    confidence_score = r.get("confidence_score", 0.0)
                    probability_over = r.get("probability_over", 0.5)
                    edge_percentage = r.get("edge_percentage", 0.0)
                    if not tier or tier == "Bronze":
                        tier = r.get("tier", "Bronze")
                    break

        st.caption(
            f"Auto-filled from analysis: confidence={confidence_score:.1f}, "
            f"P(over)={probability_over:.2f}, edge={edge_percentage:+.1f}%"
            if confidence_score else "Enter player name to auto-fill from tonight's analysis."
        )

        submit_bet = st.form_submit_button("📌 Log Bet", use_container_width=True, type="primary")

    if submit_bet:
        if not final_player:
            st.error("Please enter or select a player name.")
        elif prop_line <= 0:
            st.error("Prop line must be greater than 0.")
        else:
            success, msg = log_new_bet(
                player_name=final_player,
                stat_type=stat_type,
                prop_line=prop_line,
                direction=direction,
                platform=platform,
                confidence_score=confidence_score,
                probability_over=probability_over,
                edge_percentage=edge_percentage,
                tier=tier,
                entry_fee=entry_fee,
                team=team.strip().upper() if team else "",
                notes=notes.strip(),
            )
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

# ============================================================
# END SECTION: Log a Bet
# ============================================================


# ============================================================
# SECTION: My Bets
# ============================================================

with tab_bets:
    st.subheader("📋 My Bets")

    all_bets = load_all_bets(limit=200)

    if not all_bets:
        st.info("No bets logged yet. Use the **➕ Log a Bet** tab to add your first bet.")
    else:
        # ── Mark Result ──────────────────────────────────────────────
        pending_bets = [b for b in all_bets if not b.get("result")]
        if pending_bets:
            st.subheader("✅ Mark Result")
            pending_labels = {
                b["bet_id"]: (
                    f"#{b['bet_id']} — {b['player_name']} "
                    f"{b['direction']} {b['prop_line']} {b['stat_type'].title()} "
                    f"({b.get('platform','?')}, {b.get('bet_date','')})"
                )
                for b in pending_bets
            }
            with st.form("mark_result_form"):
                selected_bet_id = st.selectbox(
                    "Select Pending Bet",
                    options=list(pending_labels.keys()),
                    format_func=lambda x: pending_labels[x],
                )
                result_choice = st.radio("Result", ["WIN", "LOSS", "PUSH"], horizontal=True)
                actual_value = st.number_input(
                    "Actual Stat Value",
                    min_value=0.0, max_value=200.0, value=0.0, step=0.5,
                )
                submit_result = st.form_submit_button("💾 Save Result", type="primary")

            if submit_result:
                success, msg = record_bet_result(selected_bet_id, result_choice, actual_value)
                if success:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

        st.divider()

        # ── Bets Table ────────────────────────────────────────────────
        _RESULT_EMOJI = {"WIN": "✅", "LOSS": "❌", "PUSH": "🔄", None: "⏳", "": "⏳"}
        display_bets = []
        for b in all_bets:
            res = b.get("result") or ""
            display_bets.append({
                "ID": b.get("bet_id", ""),
                "Date": b.get("bet_date", ""),
                "Player": b.get("player_name", ""),
                "Team": b.get("team", ""),
                "Stat": b.get("stat_type", "").title(),
                "Line": b.get("prop_line", 0),
                "Dir": b.get("direction", ""),
                "Platform": b.get("platform", ""),
                "Tier": b.get("tier", ""),
                "Conf": round(b.get("confidence_score", 0), 1),
                "Fee ($)": b.get("entry_fee", 0),
                "Result": f"{_RESULT_EMOJI.get(res, '⏳')} {res}" if res else "⏳ Pending",
                "Actual": b.get("actual_value", "—"),
                "Notes": b.get("notes", ""),
            })

        st.dataframe(
            display_bets,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Line": st.column_config.NumberColumn(format="%.1f"),
                "Conf": st.column_config.NumberColumn(format="%.1f"),
                "Fee ($)": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

        # ── Performance Summary ───────────────────────────────────────
        stats = get_model_performance_stats()
        overall = stats.get("overall", {})
        if overall.get("total_bets", 0) > 0:
            st.divider()
            st.subheader("📊 Performance Summary")
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Total Bets", overall.get("total_bets", 0))
            mc2.metric("Wins", overall.get("wins", 0))
            mc3.metric("Losses", overall.get("losses", 0))
            mc4.metric("Win Rate", f"{overall.get('win_rate', 0):.1f}%")

            # By tier
            by_tier = stats.get("by_tier", {})
            if by_tier:
                st.markdown("**Win Rate by Tier**")
                tier_rows = [
                    {
                        "Tier": t,
                        "Total": d.get("total", 0),
                        "Wins": d.get("wins", 0),
                        "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                    }
                    for t, d in sorted(by_tier.items())
                ]
                st.dataframe(tier_rows, use_container_width=True, hide_index=True)

# ============================================================
# END SECTION: My Bets
# ============================================================


# ============================================================
# SECTION: AI Picks
# ============================================================

with tab_ai_picks:
    st.subheader("📊 AI Picks — Auto-Logged by SmartAI")
    st.markdown(
        "These bets were automatically logged by the Neural Analysis engine "
        "for all qualifying picks (edge > 0%)."
    )

    all_bets_for_ai = load_all_bets(limit=500)
    ai_bets = [
        b for b in all_bets_for_ai
        if b.get("platform", "") == "SmartAI-Auto"
        or str(b.get("notes", "")).startswith("Auto-logged")
        or int(b.get("auto_logged", 0) or 0) == 1
    ]

    if not ai_bets:
        st.info(
            "📭 No AI-auto-logged picks yet. "
            "Run **⚡ Neural Analysis** — qualifying picks above the edge threshold "
            "will be logged here automatically."
        )
    else:
        # ── Overall model accuracy ────────────────────────────────────
        ai_resolved = [b for b in ai_bets if b.get("result") in ("WIN", "LOSS", "PUSH")]
        ai_wins     = sum(1 for b in ai_resolved if b.get("result") == "WIN")
        ai_losses   = sum(1 for b in ai_resolved if b.get("result") == "LOSS")
        ai_pushes   = sum(1 for b in ai_resolved if b.get("result") == "PUSH")
        ai_total    = len(ai_resolved)
        ai_rate     = round(ai_wins / ai_total * 100, 1) if ai_total > 0 else 0.0

        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("AI Picks (Total)", len(ai_bets))
        mc2.metric("Resolved",         ai_total)
        mc3.metric("✅ Wins",          ai_wins)
        mc4.metric("❌ Losses",        ai_losses)
        mc5.metric("🎯 Win Rate",      f"{ai_rate:.1f}%" if ai_total > 0 else "—",
                   help="Model predicted X/Y correctly")

        if ai_total > 0:
            st.success(
                f"🎯 **Model accuracy:** Predicted **{ai_wins}/{ai_total}** correctly "
                f"(**{ai_rate:.1f}%**) — {ai_pushes} push(es)"
            )

        st.divider()

        # ── Daily performance breakdown ───────────────────────────────
        _by_date = {}
        for b in ai_bets:
            _d = b.get("bet_date", "Unknown")
            _by_date.setdefault(_d, []).append(b)

        for _date in sorted(_by_date.keys(), reverse=True):
            _day_bets  = _by_date[_date]
            _day_res   = [b for b in _day_bets if b.get("result") in ("WIN", "LOSS", "PUSH")]
            _day_wins  = sum(1 for b in _day_res if b.get("result") == "WIN")
            _day_total = len(_day_res)
            _day_rate  = round(_day_wins / _day_total * 100, 1) if _day_total > 0 else None

            _day_label = (
                f"📅 {_date} — {len(_day_bets)} picks"
                + (f" · {_day_wins}/{_day_total} correct ({_day_rate:.0f}%)" if _day_rate is not None else " · pending")
            )
            with st.expander(_day_label, expanded=(_date == sorted(_by_date.keys())[-1])):
                _RESULT_EMOJI = {"WIN": "✅", "LOSS": "❌", "PUSH": "🔄"}
                _day_display = []
                for b in _day_bets:
                    res = b.get("result") or ""
                    _day_display.append({
                        "Player":    b.get("player_name", ""),
                        "Team":      b.get("team", ""),
                        "Stat":      b.get("stat_type", "").title(),
                        "Line":      b.get("prop_line", 0),
                        "Direction": b.get("direction", ""),
                        "Tier":      b.get("tier", ""),
                        "Conf":      round(b.get("confidence_score", 0), 1),
                        "Edge%":     round(b.get("edge_percentage", 0), 1),
                        "Result":    f"{_RESULT_EMOJI.get(res, '⏳')} {res}" if res else "⏳ Pending",
                        "Actual":    b.get("actual_value", "—"),
                        "Correct?":  (
                            "✅ Yes" if res == "WIN"
                            else ("❌ No" if res == "LOSS" else ("🔄 Push" if res == "PUSH" else "—"))
                        ),
                    })
                st.dataframe(
                    _day_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Line":  st.column_config.NumberColumn(format="%.1f"),
                        "Conf":  st.column_config.NumberColumn(format="%.1f"),
                        "Edge%": st.column_config.NumberColumn(format="%.1f"),
                    },
                )

# ============================================================
# END SECTION: AI Picks
# ============================================================


# ============================================================
# SECTION: Auto-Resolve
# ============================================================

with tab_auto_resolve:
    st.subheader("🤖 Auto-Resolve — Fetch Actual Stats & Mark Results")
    st.markdown(
        "Automatically fetch yesterday's (or any date's) actual player stats from "
        "the NBA API and mark all pending bets as WIN / LOSS / PUSH."
    )

    all_bets_for_resolve = load_all_bets(limit=500)
    pending_all = [b for b in all_bets_for_resolve if not b.get("result")]

    if not pending_all:
        st.info("✅ No pending bets found. All bets have results recorded.")
    else:
        # Group pending bets by date for display
        _pending_by_date = {}
        for _b in pending_all:
            _d = _b.get("bet_date", "Unknown")
            _pending_by_date.setdefault(_d, []).append(_b)

        st.markdown(f"**{len(pending_all)} pending bet(s)** across {len(_pending_by_date)} date(s):")
        _RESULT_EMOJI = {"WIN": "✅", "LOSS": "❌", "PUSH": "🔄", None: "⏳", "": "⏳"}
        pending_display = []
        for _b in pending_all:
            pending_display.append({
                "ID":     _b.get("bet_id", ""),
                "Date":   _b.get("bet_date", ""),
                "Player": _b.get("player_name", ""),
                "Stat":   _b.get("stat_type", "").title(),
                "Line":   _b.get("prop_line", 0),
                "Dir":    _b.get("direction", ""),
                "Tier":   _b.get("tier", ""),
            })
        st.dataframe(pending_display, use_container_width=True, hide_index=True,
                     column_config={"Line": st.column_config.NumberColumn(format="%.1f")})

    st.divider()

    col_date, col_btn = st.columns([2, 1])
    with col_date:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        resolve_date = st.date_input(
            "Date to resolve",
            value=yesterday,
            help="Bets with this date that still have no result will be auto-resolved.",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)  # vertical alignment
        resolve_btn = st.button(
            "🔄 Fetch Actual Stats & Auto-Resolve",
            type="primary",
            use_container_width=True,
        )

    if resolve_btn:
        with st.spinner("Fetching actual stats from NBA API…"):
            date_str_to_resolve = resolve_date.isoformat()
            resolved, errors = auto_resolve_bet_results(date_str=date_str_to_resolve)

        if resolved > 0:
            st.success(f"✅ Auto-resolved **{resolved}** bet(s) for {date_str_to_resolve}.")
            st.rerun()
        else:
            st.warning(f"⚠️ No bets resolved for {date_str_to_resolve}.")

        if errors:
            with st.expander(f"⚠️ {len(errors)} error(s) during auto-resolve"):
                for err in errors:
                    st.markdown(f"- {err}")

# ============================================================
# END SECTION: Auto-Resolve
# ============================================================


# ============================================================
# SECTION: Performance Predictor
# ============================================================

with tab_predict:
    st.subheader("🔮 Performance Predictor")
    st.markdown(
        "Based on tonight's analysis results, here is a forward-looking prediction "
        "for your slate's expected performance."
    )

    analysis_results = st.session_state.get("analysis_results", [])

    if not analysis_results:
        st.info(
            "💡 No analysis results found. "
            "Go to **⚡ Neural Analysis** and run analysis first, "
            "then return here for your performance forecast."
        )
    else:
        # ── Expected Win Rate ─────────────────────────────────────────
        confidences = [r.get("confidence_score", 0) for r in analysis_results]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        # Rough calibration: confidence score → approx win rate
        est_win_rate = min(95.0, max(40.0, avg_conf * 0.9 + 5.0))

        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Props in Slate", len(analysis_results))
        pc2.metric("Avg Confidence", f"{avg_conf:.1f}")
        pc3.metric("Est. Win Rate", f"{est_win_rate:.1f}%", help="Model estimate based on avg confidence")

        st.divider()

        # ── Recommended Bankroll by Tier ─────────────────────────────
        st.subheader("💰 Recommended Bankroll Allocation")
        st.markdown(
            "Based on the SAFE Score™ tier distribution in tonight's slate."
        )
        _tier_counts = {}
        for r in analysis_results:
            t = r.get("tier", "Bronze")
            _tier_counts[t] = _tier_counts.get(t, 0) + 1

        _TIER_PCT = {"Platinum": 0.30, "Gold": 0.25, "Silver": 0.20, "Bronze": 0.10}
        _TIER_EMOJI = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        bankroll = st.number_input(
            "Total Bankroll ($)", min_value=10.0, max_value=100000.0, value=100.0, step=10.0
        )
        alloc_rows = []
        for tier_name in ["Platinum", "Gold", "Silver", "Bronze"]:
            cnt = _tier_counts.get(tier_name, 0)
            if cnt > 0:
                alloc_pct = _TIER_PCT.get(tier_name, 0.10)
                alloc_amt = bankroll * alloc_pct
                alloc_rows.append({
                    "Tier": f"{_TIER_EMOJI.get(tier_name, '')} {tier_name}",
                    "Picks": cnt,
                    "Allocation %": f"{alloc_pct*100:.0f}%",
                    "Amount ($)": f"${alloc_amt:.2f}",
                    "Per Pick ($)": f"${alloc_amt/max(cnt,1):.2f}",
                })
        if alloc_rows:
            st.dataframe(alloc_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No tier data found in tonight's analysis results.")

        st.divider()

        # ── Projected ROI if All Platinum Picks Hit ───────────────────
        platinum_picks = [
            r for r in analysis_results
            if r.get("tier", "") == "Platinum"
            and not r.get("should_avoid", False)
        ]
        if platinum_picks:
            st.subheader("🏆 Projected ROI — All Platinum Picks Hit")
            plat_alloc = bankroll * 0.30
            # Rough 2× payout for a 2-leg Platinum parlay
            projected_payout = plat_alloc * 2.0
            projected_roi = ((projected_payout - plat_alloc) / max(plat_alloc, 1)) * 100

            rp1, rp2, rp3 = st.columns(3)
            rp1.metric("Platinum Picks", len(platinum_picks))
            rp2.metric("Allocated", f"${plat_alloc:.2f}")
            rp3.metric("Projected Profit", f"${projected_payout - plat_alloc:.2f}", delta=f"{projected_roi:.1f}% ROI")

            st.caption(
                "⚠️ Projections are illustrative estimates based on typical platform multipliers. "
                "Actual payouts vary by platform and entry type."
            )
        else:
            st.info("No Platinum tier picks found in tonight's analysis. Run **⚡ Neural Analysis** for updated results.")

# ============================================================
# END SECTION: Performance Predictor
# ============================================================
