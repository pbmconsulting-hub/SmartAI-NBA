# ============================================================
# FILE: pages/6_📊_Model_Health.py
# PURPOSE: Track model performance by logging bet results and
#          showing win rates by tier, platform, and stat type.
# CONNECTS TO: tracking/bet_tracker.py, tracking/database.py
# CONCEPTS COVERED: Data visualization, win rate, performance tracking
# ============================================================

import streamlit as st  # Main UI framework
import datetime         # For bet dates

# Import our tracking modules
from tracking.bet_tracker import (
    log_new_bet,
    record_bet_result,
    get_model_performance_stats,
)
from tracking.database import initialize_database, load_all_bets

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Model Health — SmartAI-NBA",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Model Health")
st.markdown("Track your bets and measure the model's prediction accuracy over time.")
st.divider()

# Ensure database exists
initialize_database()

# ============================================================
# END SECTION: Page Setup
# ============================================================

# ============================================================
# SECTION: Performance Summary Dashboard
# ============================================================

# Get performance statistics
performance_stats = get_model_performance_stats()
overall = performance_stats.get("overall", {})

total_bets = overall.get("total_bets", 0)
wins = overall.get("wins", 0)
losses = overall.get("losses", 0)
pushes = overall.get("pushes", 0)
win_rate = overall.get("win_rate", 0.0)

st.subheader("📈 Overall Performance")

# Show metrics in a row
metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)

metric_col1.metric(
    "Total Bets Tracked",
    total_bets,
    help="Total bets logged with results",
)
metric_col2.metric(
    "✅ Wins",
    wins,
    help="Bets that hit",
)
metric_col3.metric(
    "❌ Losses",
    losses,
    help="Bets that missed",
)
metric_col4.metric(
    "🔄 Pushes",
    pushes,
    help="Bets that pushed (line hit exactly)",
)
metric_col5.metric(
    "🎯 Win Rate",
    f"{win_rate:.1f}%" if total_bets > 0 else "No data",
    help="Percentage of tracked bets that won",
)

# ============================================================
# END SECTION: Performance Summary Dashboard
# ============================================================

if total_bets == 0:
    st.info(
        "📝 No bets logged yet. Use the form below to start tracking your picks! "
        "After logging bets and recording results, you'll see performance stats here."
    )

st.divider()

# ============================================================
# SECTION: Performance Breakdown by Tier
# ============================================================

if total_bets > 0:
    st.subheader("🏆 Win Rate by Tier")
    tier_performance = performance_stats.get("by_tier", {})

    if tier_performance:
        # Order tiers from best to worst
        tier_order = ["Platinum", "Gold", "Silver", "Bronze"]
        tier_rows = []

        for tier in tier_order:
            if tier in tier_performance:
                data = tier_performance[tier]
                tier_rows.append({
                    "Tier": tier,
                    "Total": data.get("total", 0),
                    "Wins": data.get("wins", 0),
                    "Losses": data.get("losses", 0),
                    "Win Rate": f"{data.get('win_rate', 0):.1f}%",
                })

        if tier_rows:
            st.dataframe(tier_rows, use_container_width=True, hide_index=True)

    # Performance by Platform
    st.subheader("🎰 Win Rate by Platform")
    platform_performance = performance_stats.get("by_platform", {})
    if platform_performance:
        platform_rows = [
            {
                "Platform": platform,
                "Total": data.get("total", 0),
                "Wins": data.get("wins", 0),
                "Win Rate": f"{data.get('win_rate', 0):.1f}%",
            }
            for platform, data in platform_performance.items()
        ]
        st.dataframe(platform_rows, use_container_width=True, hide_index=True)

    # Performance by Stat Type
    st.subheader("📐 Win Rate by Stat Type")
    stat_performance = performance_stats.get("by_stat_type", {})
    if stat_performance:
        stat_rows = [
            {
                "Stat Type": stat.capitalize(),
                "Total": data.get("total", 0),
                "Wins": data.get("wins", 0),
                "Win Rate": f"{data.get('win_rate', 0):.1f}%",
            }
            for stat, data in sorted(stat_performance.items())
        ]
        st.dataframe(stat_rows, use_container_width=True, hide_index=True)

    st.divider()

# ============================================================
# END SECTION: Performance Breakdown by Tier
# ============================================================

# ============================================================
# SECTION: Log a New Bet
# ============================================================

st.subheader("📝 Log a New Bet")
st.markdown("Record a bet before the game to track its outcome later.")

with st.form("log_bet_form"):
    form_col1, form_col2, form_col3 = st.columns(3)

    with form_col1:
        log_player_name = st.text_input(
            "Player Name *",
            placeholder="e.g., LeBron James",
        )
        log_stat_type = st.selectbox(
            "Stat Type *",
            options=["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"],
        )
        log_prop_line = st.number_input(
            "Prop Line *",
            min_value=0.0,
            max_value=100.0,
            value=24.5,
            step=0.5,
        )

    with form_col2:
        log_direction = st.selectbox(
            "Direction *",
            options=["OVER", "UNDER"],
        )
        log_platform = st.selectbox(
            "Platform",
            options=["PrizePicks", "Underdog", "DraftKings"],
        )
        log_tier = st.selectbox(
            "Tier",
            options=["Platinum", "Gold", "Silver", "Bronze"],
            index=1,  # Default to Gold
        )

    with form_col3:
        log_confidence = st.number_input(
            "Confidence Score (0-100)",
            min_value=0.0,
            max_value=100.0,
            value=65.0,
            step=1.0,
        )
        log_edge = st.number_input(
            "Edge %",
            min_value=-50.0,
            max_value=50.0,
            value=8.0,
            step=0.5,
        )
        log_probability = st.number_input(
            "Probability (0-1)",
            min_value=0.0,
            max_value=1.0,
            value=0.58,
            step=0.01,
        )

    # Second row
    log_col4, log_col5 = st.columns([2, 2])
    with log_col4:
        log_team = st.text_input("Team (optional)", placeholder="LAL")
        log_entry_fee = st.number_input("Entry Fee ($)", min_value=0.0, value=10.0, step=5.0)
    with log_col5:
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

# ============================================================
# END SECTION: Log a New Bet
# ============================================================

st.divider()

# ============================================================
# SECTION: Record Results
# Let users update pending bets with their outcomes
# ============================================================

st.subheader("✏️ Record Bet Results")
st.markdown("Find pending bets and enter the actual outcome.")

# Load all bets from database
all_bets = load_all_bets(limit=50)

# Filter to pending bets (no result yet)
pending_bets = [b for b in all_bets if not b.get("result")]

if pending_bets:
    st.markdown(f"**{len(pending_bets)} pending bet(s) awaiting results:**")

    for bet in pending_bets[:10]:  # Show max 10 at a time
        result_col1, result_col2, result_col3, result_col4 = st.columns([2, 1, 1, 1])

        with result_col1:
            st.write(f"**{bet.get('player_name','')}** — {bet.get('stat_type','').capitalize()} {bet.get('prop_line',0)} {bet.get('direction','')}")
            st.caption(f"Bet #{bet.get('bet_id','')} | {bet.get('bet_date','')} | {bet.get('platform','')}")

        with result_col2:
            actual_val = st.number_input(
                "Actual value",
                min_value=0.0,
                max_value=200.0,
                value=0.0,
                step=0.5,
                key=f"actual_{bet.get('bet_id', 0)}",
            )

        with result_col3:
            result_choice = st.selectbox(
                "Result",
                options=["", "WIN", "LOSS", "PUSH"],
                key=f"result_{bet.get('bet_id', 0)}",
            )

        with result_col4:
            if st.button("Save", key=f"save_{bet.get('bet_id', 0)}"):
                if result_choice:
                    success, msg = record_bet_result(
                        bet.get("bet_id", 0),
                        result_choice,
                        actual_val,
                    )
                    if success:
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
# END SECTION: Record Results
# ============================================================

st.divider()

# ============================================================
# SECTION: Recent Bet History
# ============================================================

st.subheader("📋 Recent Bet History")

# Load recent bets with results
bets_with_results = [b for b in all_bets if b.get("result")]

if bets_with_results:
    history_rows = []
    for bet in bets_with_results[:30]:  # Show last 30
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
else:
    st.caption("No results recorded yet.")

# ============================================================
# END SECTION: Recent Bet History
# ============================================================
