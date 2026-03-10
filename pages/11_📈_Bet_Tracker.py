# ============================================================
# FILE: pages/11_📈_Bet_Tracker.py
# PURPOSE: Unified Bet Tracker & Model Health hub combining
#          bet logging, auto-resolve, AI picks, performance
#          predictor, daily history, and per-platform views.
# TABS:
#   1. 📊 Model Health  — Overall metrics + win rate by tier/platform/stat
#   2. 📊 AI Picks      — Auto-logged picks from Neural Analysis
#   3. 🤖 Auto-Resolve  — Fetch actual stats and mark results
#   4. 📋 My Bets       — Full bets as styled cards
#   5. ➕ Log a Bet     — Manual / analysis-prefilled bet entry
#   6. 🔮 Predictor     — Forward-looking bankroll / ROI forecasts
#   7. 📅 History       — 2-week rolling day-by-day timeline
# CONNECTS TO: tracking/bet_tracker.py, tracking/database.py
# ============================================================

import datetime
import json

import streamlit as st

from tracking.bet_tracker import (
    auto_log_analysis_bets,
    auto_resolve_bet_results,
    get_model_performance_stats,
    log_new_bet,
    record_bet_result,
)
from tracking.database import (
    initialize_database,
    load_all_bets,
    load_daily_snapshots,
    get_rolling_stats,
    save_daily_snapshot,
)
from styles.theme import (
    get_global_css,
    get_qds_css,
    get_education_box_html,
    get_bet_card_css,
    get_bet_card_html,
    get_summary_cards_html,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Bet Tracker & Model Health — SmartBetPro NBA",
    page_icon="📈",
    layout="wide",
)

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)
st.markdown(get_bet_card_css(), unsafe_allow_html=True)

# Ensure DB is initialised
initialize_database()

# Auto-resolve past bets AND today's completed bets on page load (best-effort, silent)
try:
    _today_str = datetime.date.today().isoformat()
    _yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    _all_bets_check = load_all_bets(limit=500)

    # Resolve past pending bets (yesterday and older)
    _pending_old = [
        b for b in _all_bets_check
        if not b.get("result") and b.get("bet_date", "") < _today_str
    ]
    if _pending_old:
        _dates_to_resolve = sorted({b.get("bet_date", "") for b in _pending_old if b.get("bet_date")})
        _total_resolved = 0
        for _d in _dates_to_resolve:
            _cnt, _ = auto_resolve_bet_results(date_str=_d)
            _total_resolved += _cnt
        if _total_resolved > 0:
            st.toast(f"🤖 Auto-resolved {_total_resolved} past bet(s) on page load.")

    # Silently attempt to resolve today's bets where games are Final
    try:
        from tracking.bet_tracker import resolve_todays_bets
        _today_result = resolve_todays_bets()
        if _today_result.get("resolved", 0) > 0:
            st.toast(
                f"⚡ Auto-resolved {_today_result['resolved']} of today's bet(s) "
                f"({_today_result['wins']}W / {_today_result['losses']}L)."
            )
    except Exception:
        pass  # Not available or API error — silently skip
except Exception:
    pass  # Best-effort

st.title("📈 Bet Tracker & Model Health")
st.markdown(
    "Your unified hub for tracking model performance, logging bets, "
    "auto-resolving results, and forecasting ROI."
)

# ============================================================
# SECTION: Top-Level Platform Selector
# ============================================================

st.divider()

platform_filter = st.radio(
    "Filter by Platform",
    ["🏠 All Platforms", "🟢 PrizePicks", "🟣 Underdog Fantasy", "🔵 DraftKings Pick6"],
    horizontal=True,
    label_visibility="collapsed",
)

# Map radio selection to DB platform string(s)
def _platform_filter_fn(bet):
    """Return True if this bet matches the selected platform filter."""
    plat = str(bet.get("platform") or "").lower()
    if platform_filter == "🏠 All Platforms":
        return True
    elif platform_filter == "🟢 PrizePicks":
        return "prize" in plat or plat == "pp"
    elif platform_filter == "🟣 Underdog Fantasy":
        return "underdog" in plat or plat == "ud"
    elif platform_filter == "🔵 DraftKings Pick6":
        return "draftkings" in plat or plat == "dk"
    return True

st.divider()

# ============================================================
# END SECTION: Top-Level Platform Selector
# ============================================================

# ============================================================
# SECTION: Tabs
# ============================================================

(
    tab_model_health,
    tab_ai_picks,
    tab_auto_resolve,
    tab_bets,
    tab_log,
    tab_predict,
    tab_history,
) = st.tabs([
    "📊 Model Health",
    "📊 AI Picks",
    "🤖 Auto-Resolve",
    "📋 My Bets",
    "➕ Log a Bet",
    "🔮 Predictor",
    "📅 History",
])

# ============================================================
# END SECTION: Tabs
# ============================================================

# Shared result emoji map
_RESULT_EMOJI = {"WIN": "✅", "LOSS": "❌", "PUSH": "🔄", None: "⏳", "": "⏳"}

# ============================================================
# SECTION: Model Health Tab
# ============================================================

with tab_model_health:
    st.markdown(get_education_box_html(
        "📖 What is Model Health?",
        """
        <strong>Model Calibration</strong>: Are the model's probabilities accurate?
        If we say 70% probability, does the pick hit ~70% of the time?<br><br>
        <strong>Win Rate by Tier</strong>: Platinum picks should win more than Bronze picks.
        If Bronze is winning more than Platinum, the model needs recalibration.<br><br>
        <strong>Why track results?</strong>: The more bets you log, the better we can see
        if the model is making money over time. Track at least 50+ bets to see meaningful
        patterns.<br><br>
        <strong>ROI</strong>: Return on Investment = (profit / total wagered) × 100.
        Positive ROI means you're profitable long-term.
        """
    ), unsafe_allow_html=True)

    all_bets_for_health = load_all_bets(limit=500)
    filtered_health = [b for b in all_bets_for_health if _platform_filter_fn(b)]
    resolved_health = [b for b in filtered_health if b.get("result") in ("WIN", "LOSS", "PUSH")]
    wins_h   = sum(1 for b in resolved_health if b.get("result") == "WIN")
    losses_h = sum(1 for b in resolved_health if b.get("result") == "LOSS")
    pushes_h = sum(1 for b in resolved_health if b.get("result") == "PUSH")
    total_h  = len(resolved_health)
    win_rate_h = round(wins_h / max(wins_h + losses_h, 1) * 100, 1)
    pending_h = sum(1 for b in filtered_health if not b.get("result"))

    # Rolling stats for streak
    rolling = get_rolling_stats(days=14)
    streak_val = rolling.get("streak", 0)

    # Best platform
    _plat_wins: dict = {}
    for b in resolved_health:
        p = str(b.get("platform") or "Unknown")
        w = 1 if b.get("result") == "WIN" else 0
        l = 1 if b.get("result") == "LOSS" else 0
        if p not in _plat_wins:
            _plat_wins[p] = {"wins": 0, "total": 0}
        _plat_wins[p]["wins"] += w
        _plat_wins[p]["total"] += (w + l)
    best_platform = ""
    if _plat_wins:
        _sorted_plats = sorted(
            [(p, d["wins"] / max(d["total"], 1)) for p, d in _plat_wins.items() if d["total"] >= 3],
            key=lambda x: x[1], reverse=True,
        )
        if _sorted_plats:
            best_platform = _sorted_plats[0][0]

    # Summary cards
    st.markdown(
        get_summary_cards_html(
            total=len(filtered_health),
            wins=wins_h,
            losses=losses_h,
            pushes=pushes_h,
            pending=pending_h,
            win_rate=win_rate_h,
            streak=streak_val,
            best_platform=best_platform,
        ),
        unsafe_allow_html=True,
    )

    if total_h == 0:
        st.info(
            "📝 No resolved bets found. Use **➕ Log a Bet** to start tracking your picks! "
            "After logging bets and recording results you'll see performance stats here."
        )

    if total_h > 0:
        st.divider()

        performance_stats = get_model_performance_stats()

        # Win rate by tier
        st.subheader("🏆 Win Rate by Tier")
        tier_perf = performance_stats.get("by_tier", {})
        if tier_perf:
            tier_order = ["Platinum", "Gold", "Silver", "Bronze"]
            tier_rows = [
                {
                    "Tier": t,
                    "Total": tier_perf[t].get("total", 0),
                    "Wins":  tier_perf[t].get("wins", 0),
                    "Losses": tier_perf[t].get("losses", 0),
                    "Win Rate": f"{tier_perf[t].get('win_rate', 0):.1f}%",
                }
                for t in tier_order if t in tier_perf
            ]
            st.dataframe(tier_rows, use_container_width=True, hide_index=True)

        # Win rate by platform
        st.subheader("🎰 Win Rate by Platform")
        plat_perf = performance_stats.get("by_platform", {})
        if plat_perf:
            plat_rows = [
                {
                    "Platform": p,
                    "Total": d.get("total", 0),
                    "Wins":  d.get("wins", 0),
                    "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                }
                for p, d in plat_perf.items()
            ]
            st.dataframe(plat_rows, use_container_width=True, hide_index=True)

        # Win rate by stat type
        st.subheader("📐 Win Rate by Stat Type")
        stat_perf = performance_stats.get("by_stat_type", {})
        if stat_perf:
            stat_rows = [
                {
                    "Stat Type": s.capitalize(),
                    "Total": d.get("total", 0),
                    "Wins":  d.get("wins", 0),
                    "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                }
                for s, d in sorted(stat_perf.items())
            ]
            st.dataframe(stat_rows, use_container_width=True, hide_index=True)

# ============================================================
# END SECTION: Model Health Tab
# ============================================================


# ============================================================
# SECTION: AI Picks Tab
# ============================================================

with tab_ai_picks:
    st.subheader("📊 AI Picks — Auto-Logged by SmartAI")
    st.markdown(
        "These bets were automatically logged by the Neural Analysis engine "
        "or the Platform Props & Analyze pipeline."
    )

    all_bets_for_ai = load_all_bets(limit=500)
    ai_bets_raw = [
        b for b in all_bets_for_ai
        if b.get("platform", "") in ("SmartAI-Auto", "PrizePicks", "Underdog", "DraftKings",
                                      "Underdog Fantasy", "DraftKings Pick6")
        or str(b.get("notes", "")).startswith("Auto-logged")
        or int(b.get("auto_logged", 0) or 0) == 1
    ]
    ai_bets = [b for b in ai_bets_raw if _platform_filter_fn(b)]

    if not ai_bets:
        st.info(
            "📭 No AI-auto-logged picks yet. "
            "Run **⚡ Neural Analysis** or click **📊 Fetch Platform Props & Analyze** on the Live Games page."
        )
    else:
        ai_resolved = [b for b in ai_bets if b.get("result") in ("WIN", "LOSS", "PUSH")]
        ai_wins   = sum(1 for b in ai_resolved if b.get("result") == "WIN")
        ai_losses = sum(1 for b in ai_resolved if b.get("result") == "LOSS")
        ai_pushes = sum(1 for b in ai_resolved if b.get("result") == "PUSH")
        ai_total  = len(ai_resolved)
        ai_rate   = round(ai_wins / max(ai_wins + ai_losses, 1) * 100, 1)

        st.markdown(
            get_summary_cards_html(
                total=len(ai_bets),
                wins=ai_wins,
                losses=ai_losses,
                pushes=ai_pushes,
                pending=sum(1 for b in ai_bets if not b.get("result")),
                win_rate=ai_rate,
            ),
            unsafe_allow_html=True,
        )

        if ai_total > 0:
            st.success(
                f"🎯 **Model accuracy:** Predicted **{ai_wins}/{ai_total}** correctly "
                f"(**{ai_rate:.1f}%**) — {ai_pushes} push(es)"
            )

        st.divider()

        # Daily breakdown with bet cards
        _by_date: dict = {}
        for b in ai_bets:
            _by_date.setdefault(b.get("bet_date", "Unknown"), []).append(b)

        for _date in sorted(_by_date.keys(), reverse=True):
            _day_bets  = _by_date[_date]
            _day_res   = [b for b in _day_bets if b.get("result") in ("WIN", "LOSS", "PUSH")]
            _day_wins  = sum(1 for b in _day_res if b.get("result") == "WIN")
            _day_total = len(_day_res)
            _day_rate  = round(_day_wins / max(_day_wins + (_day_total - _day_wins), 1) * 100, 1) if _day_total > 0 else None

            _day_label = (
                f"📅 {_date} — {len(_day_bets)} picks"
                + (f" · {_day_wins}/{_day_total} correct ({_day_rate:.0f}%)"
                   if _day_rate is not None else " · pending")
            )
            with st.expander(_day_label, expanded=(_date == max(_by_date.keys()))):
                _col_a, _col_b = st.columns(2)
                for _idx, _b in enumerate(_day_bets):
                    _col = _col_a if _idx % 2 == 0 else _col_b
                    with _col:
                        st.markdown(get_bet_card_html(_b), unsafe_allow_html=True)

# ============================================================
# END SECTION: AI Picks Tab
# ============================================================


# ============================================================
# SECTION: Auto-Resolve Tab
# ============================================================

with tab_auto_resolve:
    st.subheader("🤖 Auto-Resolve — Fetch Actual Stats & Mark Results")
    st.markdown(
        "Automatically fetch actual player stats from the NBA API and mark pending bets "
        "as WIN / LOSS / PUSH. Use **⚡ Resolve Now** to resolve today's completed games instantly."
    )

    # ── Resolve Now (today's bets) ────────────────────────────────────
    st.markdown("### ⚡ Resolve Today's Bets")
    st.caption("Checks live NBA scoreboard for Final games and resolves today's pending bets immediately.")

    resolve_today_btn = st.button(
        "⚡ Resolve Now",
        type="primary",
        help="Fetch live game status and resolve today's bets where games are Final",
    )

    if resolve_today_btn:
        with st.spinner("Checking today's games and resolving completed bets…"):
            try:
                from tracking.bet_tracker import resolve_todays_bets
                _result = resolve_todays_bets()
                if _result["resolved"] > 0:
                    st.success(
                        f"✅ Resolved **{_result['resolved']}** bet(s) today: "
                        f"**{_result['wins']}** WIN · **{_result['losses']}** LOSS · **{_result['pushes']}** PUSH"
                    )
                    st.rerun()
                else:
                    st.info(
                        f"ℹ️ No bets resolved. "
                        f"Games may still be in progress or not started. "
                        f"Still pending: {_result.get('pending', 0)}"
                    )
                if _result.get("errors"):
                    with st.expander(f"⚠️ {len(_result['errors'])} issue(s)"):
                        for err in _result["errors"]:
                            st.markdown(f"- {err}")
            except Exception as _err:
                st.error(f"❌ Resolve failed: {_err}")

    st.divider()

    # ── Live Status Section ────────────────────────────────────────────
    st.markdown("### 🔄 Live Bet Status — Today's Picks")
    _today_bets_all = load_all_bets(limit=500)
    _today_str_ar = datetime.date.today().isoformat()
    _today_bets = [
        b for b in _today_bets_all
        if b.get("bet_date") == _today_str_ar and _platform_filter_fn(b)
    ]
    _today_pending = [b for b in _today_bets if not b.get("result")]

    auto_refresh = st.checkbox("🔁 Auto-refresh live status (every 60s)", value=False)

    if _today_bets:
        if _today_pending:
            try:
                from tracking.bet_tracker import get_live_bet_status
                _live_bets = get_live_bet_status(_today_pending)
            except Exception:
                _live_bets = _today_pending

            _col_a, _col_b = st.columns(2)
            for _idx, _lb in enumerate(_live_bets):
                _col = _col_a if _idx % 2 == 0 else _col_b
                with _col:
                    st.markdown(get_bet_card_html(_lb, show_live_status=True), unsafe_allow_html=True)

            # Already resolved today
            _today_resolved = [b for b in _today_bets if b.get("result")]
            if _today_resolved:
                st.markdown("**✅ Already Resolved Today:**")
                _cr_a, _cr_b = st.columns(2)
                for _idx, _rb in enumerate(_today_resolved):
                    _col = _cr_a if _idx % 2 == 0 else _cr_b
                    with _col:
                        st.markdown(get_bet_card_html(_rb), unsafe_allow_html=True)
        else:
            st.markdown("**Today's Bets (All Resolved):**")
            _cr_a, _cr_b = st.columns(2)
            for _idx, _rb in enumerate(_today_bets):
                _col = _cr_a if _idx % 2 == 0 else _cr_b
                with _col:
                    st.markdown(get_bet_card_html(_rb), unsafe_allow_html=True)
    else:
        st.info("No bets logged for today yet.")

    if auto_refresh:
        import time as _time
        _time.sleep(60)
        st.rerun()

    st.divider()

    # ── Resolve Past Bets ─────────────────────────────────────────────
    st.markdown("### 🗓️ Resolve Past Bets")
    all_bets_for_resolve = load_all_bets(limit=500)
    pending_all = [
        b for b in all_bets_for_resolve
        if not b.get("result") and b.get("bet_date", "") < _today_str_ar and _platform_filter_fn(b)
    ]

    if not pending_all:
        st.info("✅ No past pending bets found.")
    else:
        st.markdown(f"**{len(pending_all)} past pending bet(s):**")
        _pa, _pb = st.columns(2)
        for _idx, _pb_bet in enumerate(pending_all):
            _col = _pa if _idx % 2 == 0 else _pb
            with _col:
                st.markdown(get_bet_card_html(_pb_bet), unsafe_allow_html=True)

    col_date, col_btn = st.columns([2, 1])
    with col_date:
        yesterday_dt = datetime.date.today() - datetime.timedelta(days=1)
        resolve_date = st.date_input(
            "Date to resolve",
            value=yesterday_dt,
            help="Bets with this date that still have no result will be auto-resolved.",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        resolve_btn = st.button(
            "🔄 Fetch Actual Stats & Auto-Resolve",
            type="primary",
            width="stretch",
        )

    if resolve_btn:
        with st.spinner("Fetching actual stats from NBA API…"):
            resolved, errors = auto_resolve_bet_results(date_str=resolve_date.isoformat())

        if resolved > 0:
            try:
                save_daily_snapshot(resolve_date.isoformat())
            except Exception:
                pass
            st.success(f"✅ Auto-resolved **{resolved}** bet(s) for {resolve_date.isoformat()}.")
            st.rerun()
        else:
            st.warning(f"⚠️ No bets resolved for {resolve_date.isoformat()}.")

        if errors:
            with st.expander(f"⚠️ {len(errors)} error(s) during auto-resolve"):
                for err in errors:
                    st.markdown(f"- {err}")

# ============================================================
# END SECTION: Auto-Resolve Tab
# ============================================================


# ============================================================
# SECTION: My Bets Tab (Styled Cards)
# ============================================================

with tab_bets:
    st.subheader("📋 My Bets")

    all_bets_raw = load_all_bets(limit=500)
    all_bets = [b for b in all_bets_raw if _platform_filter_fn(b)]

    if not all_bets:
        st.info("No bets logged yet. Use **➕ Log a Bet** to add your first bet.")
    else:
        # ── Filter Pills ──────────────────────────────────────────────
        filter_choice = st.radio(
            "Filter bets",
            ["All", "Wins Only", "Losses Only", "Pending", "Platinum", "Gold", "Silver", "Bronze"],
            horizontal=True,
            label_visibility="collapsed",
        )

        def _apply_filter(bets, choice):
            if choice == "Wins Only":
                return [b for b in bets if b.get("result") == "WIN"]
            elif choice == "Losses Only":
                return [b for b in bets if b.get("result") == "LOSS"]
            elif choice == "Pending":
                return [b for b in bets if not b.get("result")]
            elif choice in ("Platinum", "Gold", "Silver", "Bronze"):
                return [b for b in bets if b.get("tier", "") == choice]
            return bets

        filtered_bets = _apply_filter(all_bets, filter_choice)

        # ── Summary Cards ─────────────────────────────────────────────
        _res_bets = [b for b in all_bets if b.get("result") in ("WIN", "LOSS", "PUSH")]
        _w = sum(1 for b in _res_bets if b.get("result") == "WIN")
        _l = sum(1 for b in _res_bets if b.get("result") == "LOSS")
        _p = sum(1 for b in _res_bets if b.get("result") == "PUSH")
        _wr = round(_w / max(_w + _l, 1) * 100, 1)
        _pend = sum(1 for b in all_bets if not b.get("result"))
        st.markdown(
            get_summary_cards_html(
                total=len(all_bets), wins=_w, losses=_l, pushes=_p,
                pending=_pend, win_rate=_wr,
            ),
            unsafe_allow_html=True,
        )

        st.markdown(f"**Showing {len(filtered_bets)} bet(s)** (filter: {filter_choice})")
        st.divider()

        # ── Mark a Result ─────────────────────────────────────────────
        pending_bets = [b for b in filtered_bets if not b.get("result")]
        if pending_bets:
            with st.expander("✅ Mark a Result", expanded=False):
                pending_labels = {
                    b.get("id", b.get("bet_id", idx)): (
                        f"#{b.get('id', b.get('bet_id', idx))} — {b.get('player_name', '?')} "
                        f"{b.get('direction', '')} {b.get('prop_line', '')} {str(b.get('stat_type', '')).title()} "
                        f"({b.get('platform', '?')}, {b.get('bet_date', '')})"
                    )
                    for idx, b in enumerate(pending_bets)
                }
                with st.form("mark_result_form_bt"):
                    selected_bet_id = st.selectbox(
                        "Select Pending Bet",
                        options=list(pending_labels.keys()),
                        format_func=lambda x: pending_labels[x],
                    )
                    result_choice = st.radio("Result", ["WIN", "LOSS", "PUSH"], horizontal=True)
                    actual_value  = st.number_input(
                        "Actual Stat Value",
                        min_value=0.0, max_value=200.0, value=0.0, step=0.5,
                    )
                    submit_result = st.form_submit_button("💾 Save Result", type="primary")

                if submit_result:
                    ok, msg = record_bet_result(selected_bet_id, result_choice, actual_value)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # ── Bet Cards Grid ────────────────────────────────────────────
        if not filtered_bets:
            st.info(f"No bets match the '{filter_choice}' filter.")
        else:
            col_a, col_b = st.columns(2)
            for idx, bet in enumerate(filtered_bets):
                col = col_a if idx % 2 == 0 else col_b
                with col:
                    st.markdown(get_bet_card_html(bet), unsafe_allow_html=True)

# ============================================================
# END SECTION: My Bets Tab
# ============================================================


# ============================================================
# SECTION: Log a Bet Tab
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

    with st.form("log_bet_form_bt", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            selected_player = st.selectbox(
                "Player (from tonight's analysis)", player_options
            )
            manual_player = st.text_input(
                "Or enter player name manually", placeholder="e.g., LeBron James"
            )
            stat_type  = st.selectbox(
                "Stat Type",
                ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"],
            )
            prop_line  = st.number_input("Line", min_value=0.0, max_value=200.0, value=24.5, step=0.5)
            direction  = st.radio("Direction", ["OVER", "UNDER"], horizontal=True)

        with col2:
            platform   = st.selectbox("Platform", ["PrizePicks", "Underdog", "DraftKings"])
            tier       = st.selectbox("Tier", ["Platinum", "Gold", "Silver", "Bronze"])
            entry_fee  = st.number_input("Entry Fee ($)", min_value=0.0, max_value=10000.0, value=10.0, step=5.0)
            team       = st.text_input("Team (optional)", placeholder="e.g., LAL")
            notes      = st.text_input("Notes (optional)", placeholder="e.g., revenge game")

        # Pre-fill confidence from analysis results
        confidence_score = 0.0
        probability_over = 0.5
        edge_percentage  = 0.0
        final_player = (
            manual_player.strip()
            if manual_player.strip()
            else (selected_player if selected_player != "— type manually —" else "")
        )
        if final_player and analysis_results:
            for r in analysis_results:
                if r.get("player_name", "").lower() == final_player.lower():
                    confidence_score = r.get("confidence_score", 0.0)
                    probability_over = r.get("probability_over", 0.5)
                    edge_percentage  = r.get("edge_percentage", 0.0)
                    if not tier or tier == "Bronze":
                        tier = r.get("tier", "Bronze")
                    break

        st.caption(
            f"Auto-filled from analysis: confidence={confidence_score:.1f}, "
            f"P(over)={probability_over:.2f}, edge={edge_percentage:+.1f}%"
            if confidence_score
            else "Enter player name to auto-fill from tonight's analysis."
        )

        submit_bet = st.form_submit_button(
            "📌 Log Bet", width="stretch", type="primary"
        )

    if submit_bet:
        if not final_player:
            st.error("Please enter or select a player name.")
        elif prop_line <= 0:
            st.error("Prop line must be greater than 0.")
        else:
            ok, msg = log_new_bet(
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
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

# ============================================================
# END SECTION: Log a Bet Tab
# ============================================================


# ============================================================
# SECTION: Performance Predictor Tab
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
        confidences  = [r.get("confidence_score", 0) for r in analysis_results]
        avg_conf     = sum(confidences) / len(confidences) if confidences else 0

        # Tier-weighted win-rate estimation
        _TIER_BASE_WIN_RATE = {
            "Platinum": 72.0,
            "Gold":     62.0,
            "Silver":   54.0,
            "Bronze":   46.0,
        }
        _tier_counts_wr: dict = {}
        for r in analysis_results:
            t = r.get("tier", "Bronze")
            _tier_counts_wr[t] = _tier_counts_wr.get(t, 0) + 1

        total_picks = len(analysis_results)
        tier_weighted_win_rate = 0.0
        if total_picks > 0:
            for tier_name, base_wr in _TIER_BASE_WIN_RATE.items():
                cnt = _tier_counts_wr.get(tier_name, 0)
                tier_weighted_win_rate += (cnt / total_picks) * base_wr

        conf_based = min(95.0, max(40.0, avg_conf * 0.9 + 5.0))
        est_win_rate = round(0.70 * tier_weighted_win_rate + 0.30 * conf_based, 1)
        est_win_rate = min(95.0, max(40.0, est_win_rate))

        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("Props in Slate",  len(analysis_results))
        pc2.metric("Avg Confidence",  f"{avg_conf:.1f}")
        pc3.metric("Est. Win Rate",   f"{est_win_rate:.1f}%",
                   help="Tier-weighted estimate blended with model confidence")

        if _tier_counts_wr:
            st.markdown("**Per-Tier Expected Win Rates**")
            _TIER_EMOJI_WR = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
            tier_wr_rows = [
                {
                    "Tier":            f"{_TIER_EMOJI_WR.get(t, '')} {t}",
                    "Picks":           _tier_counts_wr[t],
                    "Est. Win Rate":   f"{_TIER_BASE_WIN_RATE.get(t, 50):.0f}%",
                }
                for t in ["Platinum", "Gold", "Silver", "Bronze"]
                if t in _tier_counts_wr
            ]
            st.dataframe(tier_wr_rows, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("💰 Recommended Bankroll Allocation")
        st.markdown("Based on the SAFE Score™ tier distribution in tonight's slate.")

        _tier_counts: dict = {}
        for r in analysis_results:
            t = r.get("tier", "Bronze")
            _tier_counts[t] = _tier_counts.get(t, 0) + 1

        _TIER_PCT   = {"Platinum": 0.30, "Gold": 0.25, "Silver": 0.20, "Bronze": 0.10}
        _TIER_EMOJI = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        bankroll    = st.number_input(
            "Total Bankroll ($)", min_value=10.0, max_value=100000.0, value=100.0, step=10.0
        )
        alloc_rows = []
        for tier_name in ["Platinum", "Gold", "Silver", "Bronze"]:
            cnt = _tier_counts.get(tier_name, 0)
            if cnt > 0:
                alloc_pct = _TIER_PCT.get(tier_name, 0.10)
                alloc_amt = bankroll * alloc_pct
                alloc_rows.append({
                    "Tier":          f"{_TIER_EMOJI.get(tier_name, '')} {tier_name}",
                    "Picks":         cnt,
                    "Allocation %":  f"{alloc_pct * 100:.0f}%",
                    "Amount ($)":    f"${alloc_amt:.2f}",
                    "Per Pick ($)":  f"${alloc_amt / max(cnt, 1):.2f}",
                })
        if alloc_rows:
            st.dataframe(alloc_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No tier data found in tonight's analysis results.")

        st.divider()

        platinum_picks = [
            r for r in analysis_results
            if r.get("tier", "") == "Platinum"
            and not r.get("should_avoid", False)
        ]
        if platinum_picks:
            st.subheader("🏆 Projected ROI — All Platinum Picks Hit")
            plat_alloc       = bankroll * 0.30
            projected_payout = plat_alloc * 2.0
            projected_roi    = (
                (projected_payout - plat_alloc) / max(plat_alloc, 1)
            ) * 100

            rp1, rp2, rp3 = st.columns(3)
            rp1.metric("Platinum Picks", len(platinum_picks))
            rp2.metric("Allocated",      f"${plat_alloc:.2f}")
            rp3.metric(
                "Projected Profit",
                f"${projected_payout - plat_alloc:.2f}",
                delta=f"{projected_roi:.1f}% ROI",
            )

            st.caption(
                "⚠️ Projections are illustrative estimates based on typical platform "
                "multipliers. Actual payouts vary by platform and entry type."
            )
        else:
            st.info(
                "No Platinum tier picks found in tonight's analysis. "
                "Run **⚡ Neural Analysis** for updated results."
            )

# ============================================================
# END SECTION: Performance Predictor Tab
# ============================================================


# ============================================================
# SECTION: History Tab — 2-Week Rolling Timeline
# ============================================================

with tab_history:
    st.subheader("📅 2-Week Rolling History")
    st.markdown(
        "Day-by-day breakdown of the last 14 days. "
        "Expand any day to see individual picks as styled cards."
    )

    rolling_stats = get_rolling_stats(days=14)
    snapshots = rolling_stats.get("snapshots", [])

    # ── Rolling Summary Bar ────────────────────────────────────────────
    if rolling_stats.get("total_bets", 0) > 0:
        streak_val = rolling_stats.get("streak", 0)
        streak_label = (
            f"🔥 W{streak_val}" if streak_val > 0
            else f"❄️ L{abs(streak_val)}" if streak_val < 0
            else "—"
        )
        best_d = rolling_stats.get("best_day", {})
        worst_d = rolling_stats.get("worst_day", {})
        best_day_str = f"{best_d.get('snapshot_date','—')} ({best_d.get('win_rate',0):.0f}%)" if best_d else "—"
        worst_day_str = f"{worst_d.get('snapshot_date','—')} ({worst_d.get('win_rate',0):.0f}%)" if worst_d else "—"

        rs1, rs2, rs3, rs4, rs5 = st.columns(5)
        rs1.metric("14-Day Bets",  rolling_stats.get("total_bets", 0))
        rs2.metric("Win Rate",     f"{rolling_stats.get('win_rate', 0):.1f}%")
        rs3.metric("Streak",       streak_label)
        rs4.metric("Best Day",     best_day_str)
        rs5.metric("Worst Day",    worst_day_str)
        st.divider()

    # ── History Filter ─────────────────────────────────────────────────
    hist_filter = st.radio(
        "History filter",
        ["All", "Wins Only", "Losses Only", "Pending"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # ── Day-by-Day Timeline ────────────────────────────────────────────
    if not snapshots:
        # No snapshot data yet — fall back to grouping raw bets by date
        all_bets_hist = load_all_bets(limit=500)
        all_bets_hist = [b for b in all_bets_hist if _platform_filter_fn(b)]
        _by_date_hist: dict = {}
        for _b in all_bets_hist:
            _by_date_hist.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)
        
        if not _by_date_hist:
            st.info("📭 No bets logged yet. Start logging bets to build your history.")
        else:
            for _date in sorted(_by_date_hist.keys(), reverse=True):
                _day_bets = _by_date_hist[_date]
                _day_w = sum(1 for b in _day_bets if b.get("result") == "WIN")
                _day_l = sum(1 for b in _day_bets if b.get("result") == "LOSS")
                _day_p = sum(1 for b in _day_bets if b.get("result") == "PUSH")
                _day_pend = sum(1 for b in _day_bets if not b.get("result"))
                _day_total_res = _day_w + _day_l
                _day_wr = round(_day_w / max(_day_total_res, 1) * 100, 1) if _day_total_res > 0 else None

                if _day_wr is not None and _day_wr >= 55:
                    _day_color = "🟢"
                    _day_card_class = "day-card-green"
                elif _day_wr is not None and _day_wr < 45:
                    _day_color = "🔴"
                    _day_card_class = "day-card-red"
                else:
                    _day_color = "🟡"
                    _day_card_class = "day-card-yellow"

                _wr_str = f" — {_day_wr:.0f}% win rate" if _day_wr is not None else " — ⏳ pending"
                _label = (
                    f"{_day_color} {_date} · {len(_day_bets)} picks · "
                    f"✅{_day_w} ❌{_day_l}" + _wr_str
                )

                # Apply history filter
                if hist_filter == "Wins Only":
                    _show_bets = [b for b in _day_bets if b.get("result") == "WIN"]
                elif hist_filter == "Losses Only":
                    _show_bets = [b for b in _day_bets if b.get("result") == "LOSS"]
                elif hist_filter == "Pending":
                    _show_bets = [b for b in _day_bets if not b.get("result")]
                else:
                    _show_bets = _day_bets

                if not _show_bets and hist_filter != "All":
                    continue

                with st.expander(_label, expanded=(_date == max(_by_date_hist.keys()))):
                    if not _show_bets:
                        st.info(f"No bets match '{hist_filter}' for this day.")
                    else:
                        _ha, _hb = st.columns(2)
                        for _idx, _hb_bet in enumerate(_show_bets):
                            _hcol = _ha if _idx % 2 == 0 else _hb
                            with _hcol:
                                st.markdown(get_bet_card_html(_hb_bet), unsafe_allow_html=True)
    else:
        # Use daily_snapshots for summaries + load individual bets for expansion
        all_bets_hist = load_all_bets(limit=1000)
        all_bets_hist = [b for b in all_bets_hist if _platform_filter_fn(b)]
        _bets_by_date: dict = {}
        for _b in all_bets_hist:
            _bets_by_date.setdefault(_b.get("bet_date", "Unknown"), []).append(_b)

        for snap in snapshots:
            _date = snap.get("snapshot_date", "")
            _w = snap.get("wins", 0)
            _l = snap.get("losses", 0)
            _pend = snap.get("pending", 0)
            _total = snap.get("total_picks", 0)
            _wr = snap.get("win_rate", 0.0)

            if _wr >= 55:
                _day_color = "🟢"
            elif _wr < 45 and (_w + _l) > 0:
                _day_color = "🔴"
            else:
                _day_color = "🟡"

            _wr_str = f" — {_wr:.0f}% win rate" if (_w + _l) > 0 else " — ⏳ all pending"
            _label = (
                f"{_day_color} {_date} · {_total} picks · "
                f"✅{_w} ❌{_l}" + _wr_str
            )

            _day_bets = _bets_by_date.get(_date, [])

            if hist_filter == "Wins Only":
                _show_bets = [b for b in _day_bets if b.get("result") == "WIN"]
            elif hist_filter == "Losses Only":
                _show_bets = [b for b in _day_bets if b.get("result") == "LOSS"]
            elif hist_filter == "Pending":
                _show_bets = [b for b in _day_bets if not b.get("result")]
            else:
                _show_bets = _day_bets

            if not _show_bets and hist_filter != "All" and _total == 0:
                continue

            with st.expander(_label):
                if not _show_bets:
                    if _total > 0:
                        st.info(f"No individual bets match '{hist_filter}' for this day.")
                    else:
                        st.info("No bets logged for this day.")
                else:
                    _ha, _hb = st.columns(2)
                    for _idx, _hb_bet in enumerate(_show_bets):
                        _hcol = _ha if _idx % 2 == 0 else _hb
                        with _hcol:
                            st.markdown(get_bet_card_html(_hb_bet), unsafe_allow_html=True)

# ============================================================
# END SECTION: History Tab
# ============================================================

