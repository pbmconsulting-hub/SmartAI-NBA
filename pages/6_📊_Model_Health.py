# ============================================================
# FILE: pages/6_📊_Model_Health.py
# PURPOSE: Track model performance by logging bet results and
#          showing win rates by tier, platform, and stat type.
#          Now a fully tabbed QDS-styled dashboard with a
#          Past Predictions tab for auto-saved picks.
# CONNECTS TO: tracking/bet_tracker.py, tracking/database.py
# ============================================================

import streamlit as st
import datetime

from tracking.bet_tracker import (
    log_new_bet,
    record_bet_result,
    get_model_performance_stats,
)
from tracking.database import (
    initialize_database,
    load_all_bets,
    load_recent_predictions,
    purge_old_predictions,
    get_prediction_accuracy_stats,
    update_prediction_outcome,
)

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Model Health — SmartBetPro NBA",
    page_icon="📊",
    layout="wide",
)

from styles.theme import get_global_css, get_qds_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

st.title("📊 Model Health")
st.markdown("Track your bets and measure the model's prediction accuracy over time.")

initialize_database()

# ============================================================
# END SECTION: Page Setup
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Dashboard", "💾 Log a Bet", "🔮 Past Predictions", "📋 Bet History"]
)

# ============================================================
# TAB 1: Dashboard
# ============================================================

with tab1:
    st.markdown(get_education_box_html(
        "📖 What is Model Health?",
        """
        <strong>Model Calibration</strong>: Are the model's probabilities accurate?<br><br>
        <strong>Win Rate by Tier</strong>: Platinum picks should win more than Bronze picks.<br><br>
        <strong>Why track results?</strong>: Track at least 50+ bets to see meaningful patterns.<br><br>
        <strong>ROI</strong>: Return on Investment = (profit / total wagered) × 100.
        """
    ), unsafe_allow_html=True)

    performance_stats = get_model_performance_stats()
    overall = performance_stats.get("overall", {})

    total_bets = overall.get("total_bets", 0)
    wins = overall.get("wins", 0)
    losses = overall.get("losses", 0)
    pushes = overall.get("pushes", 0)
    win_rate = overall.get("win_rate", 0.0)

    st.subheader("📈 Overall Performance")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Bets", total_bets)
    c2.metric("✅ Wins", wins)
    c3.metric("❌ Losses", losses)
    c4.metric("🔄 Pushes", pushes)
    c5.metric("🎯 Win Rate", f"{win_rate:.1f}%" if total_bets > 0 else "No data")

    if total_bets == 0:
        st.info("📝 No bets logged yet. Use the Log a Bet tab to start tracking!")

    st.divider()

    if total_bets > 0:
        # Win Rate by Tier
        st.subheader("🏆 Win Rate by Tier")
        tier_performance = performance_stats.get("by_tier", {})
        tier_order = ["Platinum", "Gold", "Silver", "Bronze"]
        tier_colors = {"Platinum": "#00ffd5", "Gold": "#ffcc00", "Silver": "#a0b4d0", "Bronze": "#ff5e00"}
        tier_rows = []
        for tier in tier_order:
            if tier in tier_performance:
                d = tier_performance[tier]
                color = tier_colors.get(tier, "#c0d0e8")
                tier_rows.append({
                    "Tier": tier,
                    "Total": d.get("total", 0),
                    "Wins": d.get("wins", 0),
                    "Losses": d.get("losses", 0),
                    "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                })
        if tier_rows:
            st.dataframe(tier_rows, use_container_width=True, hide_index=True)

        # Win Rate by Platform
        st.subheader("🎰 Win Rate by Platform")
        platform_performance = performance_stats.get("by_platform", {})
        if platform_performance:
            plat_rows = [
                {
                    "Platform": p,
                    "Total": d.get("total", 0),
                    "Wins": d.get("wins", 0),
                    "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                }
                for p, d in platform_performance.items()
            ]
            st.dataframe(plat_rows, use_container_width=True, hide_index=True)

        # Win Rate by Direction
        st.subheader("🎯 Win Rate by Direction")
        direction_performance = performance_stats.get("by_direction", {})
        if direction_performance:
            dir_rows = [
                {
                    "Direction": d_name,
                    "Total": d.get("total", 0),
                    "Wins": d.get("wins", 0),
                    "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                }
                for d_name, d in direction_performance.items()
            ]
            st.dataframe(dir_rows, use_container_width=True, hide_index=True)

        # Win Rate by Stat Type
        st.subheader("📐 Win Rate by Stat Type")
        stat_performance = performance_stats.get("by_stat_type", {})
        if stat_performance:
            stat_rows = [
                {
                    "Stat Type": s.capitalize(),
                    "Total": d.get("total", 0),
                    "Wins": d.get("wins", 0),
                    "Win Rate": f"{d.get('win_rate', 0):.1f}%",
                }
                for s, d in sorted(stat_performance.items())
            ]
            st.dataframe(stat_rows, use_container_width=True, hide_index=True)

# ============================================================
# TAB 2: Log a Bet
# ============================================================

with tab2:
    st.subheader("📝 Log a New Bet")
    st.markdown("Record a bet before the game to track its outcome later.")

    with st.form("log_bet_form"):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            log_player_name = st.text_input("Player Name *", placeholder="e.g., LeBron James")
            log_stat_type = st.selectbox(
                "Stat Type *",
                options=["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"],
            )
            log_prop_line = st.number_input("Prop Line *", min_value=0.0, max_value=100.0, value=24.5, step=0.5)
        with fc2:
            log_direction = st.selectbox("Direction *", options=["OVER", "UNDER"])
            log_platform = st.selectbox("Platform", options=["PrizePicks", "Underdog", "DraftKings"])
            log_tier = st.selectbox("Tier", options=["Platinum", "Gold", "Silver", "Bronze"], index=1)
        with fc3:
            log_confidence = st.number_input("Confidence Score (0-100)", min_value=0.0, max_value=100.0, value=65.0, step=1.0)
            log_edge = st.number_input("Edge %", min_value=-50.0, max_value=50.0, value=8.0, step=0.5)
            log_probability = st.number_input("Probability (0-1)", min_value=0.0, max_value=1.0, value=0.58, step=0.01)

        lc4, lc5 = st.columns([2, 2])
        with lc4:
            log_team = st.text_input("Team (optional)", placeholder="LAL")
            log_entry_fee = st.number_input("Entry Fee ($)", min_value=0.0, value=10.0, step=5.0)
        with lc5:
            log_notes = st.text_area("Notes (optional)", placeholder="Any context about this pick...")

        submit_bet_button = st.form_submit_button("💾 Log Bet", type="primary", use_container_width=True)

    if submit_bet_button:
        if not log_player_name.strip():
            st.error("Player name is required.")
        else:
            success, message = log_new_bet(
                player_name=log_player_name,
                stat_type=log_stat_type,
                prop_line=log_prop_line,
                direction=log_direction,
                platform=log_platform,
                confidence_score=log_confidence,
                probability_over=log_probability,
                edge_percentage=log_edge,
                tier=log_tier,
                entry_fee=log_entry_fee,
                team=log_team,
                notes=log_notes,
            )
            if success:
                st.success(f"✅ {message}")
                st.rerun()
            else:
                st.error(f"❌ {message}")

    st.divider()
    st.subheader("✏️ Record Bet Results")
    all_bets = load_all_bets(limit=50)
    pending_bets = [b for b in all_bets if not b.get("result")]
    if pending_bets:
        st.markdown(f"**{len(pending_bets)} pending bet(s) awaiting results:**")
        for bet in pending_bets[:10]:
            rc1, rc2, rc3, rc4 = st.columns([2, 1, 1, 1])
            with rc1:
                st.write(f"**{bet.get('player_name','')}** — {bet.get('stat_type','').capitalize()} {bet.get('prop_line',0)} {bet.get('direction','')}")
                st.caption(f"Bet #{bet.get('bet_id','')} | {bet.get('bet_date','')} | {bet.get('platform','')}")
            with rc2:
                actual_val = st.number_input("Actual", min_value=0.0, max_value=200.0, value=0.0, step=0.5, key=f"actual_{bet.get('bet_id', 0)}")
            with rc3:
                result_choice = st.selectbox("Result", options=["", "WIN", "LOSS", "PUSH"], key=f"result_{bet.get('bet_id', 0)}")
            with rc4:
                if st.button("Save", key=f"save_{bet.get('bet_id', 0)}"):
                    if result_choice:
                        ok, msg = record_bet_result(bet.get("bet_id", 0), result_choice, actual_val)
                        if ok:
                            st.success(f"Saved! {msg}")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Select a result first")
            st.markdown("---")
    else:
        st.info("No pending bets. Log bets above and come back after games to record results!")

# ============================================================
# TAB 3: Past Predictions
# ============================================================

with tab3:
    # Purge predictions older than 10 days on every load
    purge_old_predictions(days=10)

    st.subheader("🔮 Past Predictions")
    st.markdown("Auto-saved Platinum and Gold tier picks from Neural Analysis runs.")

    # Day filter
    day_options = {"Today": 1, "Yesterday": 2, "Last 3 Days": 3, "Last 7 Days": 7, "Last 10 Days": 10}
    day_filter_label = st.radio(
        "Show predictions from:",
        list(day_options.keys()),
        horizontal=True,
        index=4,
    )
    day_filter = day_options[day_filter_label]

    # Accuracy scoreboard
    acc = get_prediction_accuracy_stats(days=day_filter)
    accuracy_pct = acc.get("accuracy_pct", 0.0)
    correct_count = acc.get("correct", 0)
    wrong_count = acc.get("wrong", 0)
    pending_count = acc.get("pending", 0)
    total_pred = acc.get("total", 0)

    if total_pred > 0:
        ac1, ac2, ac3, ac4, ac5 = st.columns(5)
        ac1.metric("🎯 Accuracy", f"{accuracy_pct:.0f}%", help="Correct / (Correct + Wrong)")
        ac2.metric("✅ Correct", correct_count)
        ac3.metric("❌ Wrong", wrong_count)
        ac4.metric("⏳ Pending", pending_count)
        ac5.metric("📅 Window", f"{day_filter} days")

        # Tier accuracy cards
        tier_accuracy = acc.get("by_tier", {})
        tier_colors = {"Platinum": "#00ffd5", "Gold": "#ffcc00", "Silver": "#a0b4d0", "Bronze": "#ff5e00"}
        tier_emojis = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}
        tier_html = ""
        for tier in ["Platinum", "Gold", "Silver", "Bronze"]:
            if tier in tier_accuracy:
                ts = tier_accuracy[tier]
                color = tier_colors.get(tier, "#c0d0e8")
                emoji = tier_emojis.get(tier, "")
                tier_html += (
                    f'<div style="background:rgba(20,25,43,0.8);border-radius:8px;'
                    f'padding:12px;border-left:4px solid {color};margin-right:10px;flex:1;">'
                    f'<strong style="color:{color};">{emoji} {tier}</strong> — '
                    f'{ts["accuracy"]}% ({ts["correct"]}/{ts["correct"]+ts["wrong"]})'
                    f'</div>'
                )
        if tier_html:
            st.markdown(
                f'<div style="display:flex;gap:10px;margin:10px 0;">{tier_html}</div>',
                unsafe_allow_html=True,
            )

        st.divider()

    # Load and display predictions grouped by date
    predictions = load_recent_predictions(days=day_filter)

    if not predictions:
        st.info(
            "No predictions found in this window. "
            "Run **⚡ Neural Analysis** to auto-save Platinum and Gold tier picks."
        )
    else:
        # Group by date
        dates_seen = []
        by_date = {}
        for pred in predictions:
            d = pred.get("prediction_date", "")
            if d not in by_date:
                by_date[d] = []
                dates_seen.append(d)
            by_date[d].append(pred)

        tier_emojis = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}

        for date_str in dates_seen:
            try:
                date_obj = datetime.date.fromisoformat(date_str)
                date_label = date_obj.strftime("%B %-d, %Y")
            except Exception:
                date_label = date_str

            st.markdown(
                f'<div style="color:#00ffd5;font-weight:700;font-size:0.95rem;'
                f'margin:16px 0 8px;padding-bottom:4px;'
                f'border-bottom:1px solid rgba(0,255,213,0.2);">── {date_label} ──</div>',
                unsafe_allow_html=True,
            )

            for pred in by_date[date_str]:
                pid = pred.get("prediction_id", 0)
                pname = pred.get("player_name", "")
                stat = pred.get("stat_type", "").capitalize()
                direction = pred.get("direction", "OVER")
                line = pred.get("prop_line", 0)
                conf = pred.get("confidence_score", 0)
                tier = pred.get("tier", "")
                team = pred.get("team", "")
                was_correct = pred.get("was_correct")
                actual_val = pred.get("actual_value")
                notes = pred.get("notes", "")
                emoji = tier_emojis.get(tier, "📌")

                # Status badge
                if was_correct is None:
                    status_html = '<span style="background:#1a2035;color:#ffcc00;padding:2px 8px;border-radius:4px;font-size:0.75rem;">⏳ PENDING</span>'
                elif was_correct == 1:
                    actual_str = f" — scored {actual_val}" if actual_val is not None else ""
                    status_html = f'<span style="background:rgba(0,255,136,0.15);color:#00ff88;padding:2px 8px;border-radius:4px;font-size:0.75rem;">✅ CORRECT{actual_str}</span>'
                else:
                    actual_str = f" — actual: {actual_val}" if actual_val is not None else ""
                    status_html = f'<span style="background:rgba(255,56,96,0.15);color:#ff3860;padding:2px 8px;border-radius:4px;font-size:0.75rem;">❌ WRONG{actual_str}</span>'

                with st.container():
                    pc1, pc2 = st.columns([3, 2])
                    with pc1:
                        st.markdown(
                            f'<div style="background:rgba(20,25,43,0.7);border-radius:8px;'
                            f'padding:12px;border-left:3px solid #ff5e00;margin-bottom:4px;">'
                            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                            f'<span style="font-size:1.2rem;">{emoji}</span>'
                            f'<strong style="color:#fff;">{pname}</strong>'
                            + (f'<span style="background:rgba(0,240,255,0.15);color:#c0d0e8;'
                               f'padding:1px 6px;border-radius:4px;font-size:0.75rem;">{team}</span>'
                               if team else "")
                            + f'</div>'
                            f'<div style="color:#c0d0e8;font-size:0.9rem;">'
                            f'{stat} · {direction} {line} · Confidence: {conf:.0f}/100'
                            f'</div>'
                            + (f'<div style="color:#8a9bb8;font-size:0.8rem;margin-top:4px;">{notes}</div>' if notes else "")
                            + f'<div style="margin-top:8px;">{status_html}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    with pc2:
                        if was_correct is None:
                            # Pending — allow grading
                            actual_input = st.number_input(
                                "Actual value",
                                min_value=0.0, max_value=300.0, value=0.0, step=0.5,
                                key=f"pred_actual_{pid}",
                            )
                            gc1, gc2 = st.columns(2)
                            with gc1:
                                if st.button("✅ Correct", key=f"pred_correct_{pid}", use_container_width=True):
                                    update_prediction_outcome(pid, True, actual_input)
                                    st.rerun()
                            with gc2:
                                if st.button("❌ Wrong", key=f"pred_wrong_{pid}", use_container_width=True):
                                    update_prediction_outcome(pid, False, actual_input)
                                    st.rerun()

# ============================================================
# TAB 4: Bet History
# ============================================================

with tab4:
    st.subheader("📋 Recent Bet History")

    all_bets_history = load_all_bets(limit=200)
    bets_with_results = [b for b in all_bets_history if b.get("result")]

    # Filter controls
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        filter_platform = st.selectbox(
            "Platform", ["All"] + ["PrizePicks", "Underdog", "DraftKings"],
            key="hist_platform",
        )
    with fc2:
        filter_tier = st.selectbox(
            "Tier", ["All"] + ["Platinum", "Gold", "Silver", "Bronze"],
            key="hist_tier",
        )
    with fc3:
        filter_result = st.selectbox(
            "Result", ["All", "WIN", "LOSS", "PUSH"],
            key="hist_result",
        )
    with fc4:
        filter_stat = st.selectbox(
            "Stat Type", ["All", "points", "rebounds", "assists", "threes", "steals", "blocks"],
            key="hist_stat",
        )

    filtered_history = bets_with_results
    if filter_platform != "All":
        filtered_history = [b for b in filtered_history if b.get("platform") == filter_platform]
    if filter_tier != "All":
        filtered_history = [b for b in filtered_history if b.get("tier") == filter_tier]
    if filter_result != "All":
        filtered_history = [b for b in filtered_history if b.get("result") == filter_result]
    if filter_stat != "All":
        filtered_history = [b for b in filtered_history if b.get("stat_type", "").lower() == filter_stat]

    if filtered_history:
        _show_count = st.session_state.get("hist_show_count", 50)
        history_rows = []
        for bet in filtered_history[:_show_count]:
            result = bet.get("result", "")
            result_icon = "✅" if result == "WIN" else "❌" if result == "LOSS" else "🔄"
            history_rows.append({
                "Date": bet.get("bet_date", ""),
                "Player": bet.get("player_name", ""),
                "Stat": bet.get("stat_type", "").capitalize(),
                "Line": bet.get("prop_line", 0),
                "Direction": bet.get("direction", ""),
                "Actual": bet.get("actual_value", "—"),
                "Result": f"{result_icon} {result}",
                "Tier": bet.get("tier", ""),
                "Platform": bet.get("platform", ""),
            })
        st.dataframe(history_rows, use_container_width=True, hide_index=True)
        if len(filtered_history) > _show_count:
            if st.button("📥 Load More"):
                st.session_state["hist_show_count"] = _show_count + 50
                st.rerun()
    else:
        st.caption("No results found with current filters.")
