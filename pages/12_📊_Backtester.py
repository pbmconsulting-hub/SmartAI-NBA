# pages/12_📊_Backtester.py
# Historical backtesting UI for SmartAI-NBA.
# Runs the prediction model against historical game log data to validate accuracy.

import streamlit as st

st.set_page_config(
    page_title="Backtester — SmartAI-NBA",
    page_icon="📊",
    layout="wide",
)

from styles.theme import get_global_css
st.markdown(get_global_css(), unsafe_allow_html=True)

from utils.premium_gate import premium_gate
if not premium_gate("Backtester"):
    st.stop()

st.title("📊 Historical Backtester")
st.markdown(
    "Validate the model against real game logs. "
    "See win rates, ROI, and tier-by-tier performance metrics."
)
st.divider()

# ── Imports ──────────────────────────────────────────────────
try:
    from engine.backtester import run_backtest
    _BACKTESTER_AVAILABLE = True
except ImportError:
    _BACKTESTER_AVAILABLE = False

try:
    from data.game_log_cache import get_all_cached_players, load_game_logs_from_cache
    _CACHE_AVAILABLE = True
except ImportError:
    _CACHE_AVAILABLE = False

# ── Sidebar Controls ─────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Backtest Settings")

    season = st.selectbox("Season", ["2024-25", "2023-24", "2022-23"], index=0)

    stat_options = ["points", "rebounds", "assists", "steals", "blocks", "threes", "turnovers"]
    selected_stats = st.multiselect(
        "Stat Types",
        stat_options,
        default=["points", "rebounds", "assists"],
    )

    min_edge = st.slider("Min Edge (%)", min_value=1, max_value=20, value=5, step=1) / 100.0

    tier_filter = st.selectbox(
        "Tier Filter (optional)",
        ["All Tiers", "ELITE", "STRONG", "VALUE", "LEAN"],
        index=0,
    )
    tier_filter_val = None if tier_filter == "All Tiers" else tier_filter

    run_btn = st.button("▶ Run Backtest", type="primary", use_container_width=True)

# ── Info if backtester not available ─────────────────────────
if not _BACKTESTER_AVAILABLE:
    st.error("⚠️ Backtester engine not available. Check engine/backtester.py.")
    st.stop()

# ── Load cached game logs ─────────────────────────────────────
game_logs_by_player = {}
if _CACHE_AVAILABLE:
    cached_players = get_all_cached_players()
    if cached_players:
        for pname in cached_players:
            logs, is_stale = load_game_logs_from_cache(pname)
            if logs and not is_stale:
                game_logs_by_player[pname] = logs

# Also check session state (set by Player Simulator page)
session_logs = st.session_state.get("game_logs_by_player", {})
for pname, logs in session_logs.items():
    if logs and pname not in game_logs_by_player:
        game_logs_by_player[pname] = logs

# ── Status ────────────────────────────────────────────────────
st.info(
    f"📁 **{len(game_logs_by_player)} player(s)** with cached game logs available. "
    "Fetch player game logs on the 🔮 Player Simulator page first, "
    "then return here to backtest."
)

if not game_logs_by_player:
    st.warning(
        "No game log data found. Go to **🔮 Player Simulator**, search for players, "
        "and their logs will be cached for backtesting."
    )
    st.stop()

# ── Run Backtest ──────────────────────────────────────────────
if run_btn:
    if not selected_stats:
        st.error("Please select at least one stat type.")
        st.stop()

    with st.spinner("Running backtest simulation…"):
        result = run_backtest(
            season=season,
            stat_types=selected_stats,
            min_edge=min_edge,
            tier_filter=tier_filter_val,
            game_logs_by_player=game_logs_by_player,
        )

    st.session_state["backtest_result"] = result

# ── Display Results ───────────────────────────────────────────
result = st.session_state.get("backtest_result")

if not result:
    st.markdown("### Configure settings and click **▶ Run Backtest** to see results.")
    st.stop()

if result.get("status") == "no_data":
    st.warning(result.get("message", "No data available."))
    st.stop()

st.success(result.get("message", "Backtest complete."))

# ── Top-level Metrics ─────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Picks", result["total_picks"])
c2.metric("Wins", result["wins"])
c3.metric("Losses", result["losses"])
c4.metric("Win Rate", f"{result['win_rate']*100:.1f}%")
c5.metric("ROI", f"{result['roi']*100:.2f}%", delta=f"${result['total_pnl']:.2f} P&L")

st.divider()

# ── By Tier ───────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 Win Rate by Tier")
    tier_data = result.get("tier_win_rates", {})
    if tier_data:
        rows = []
        for tier, d in tier_data.items():
            if d["picks"] > 0:
                rows.append({
                    "Tier": tier,
                    "Picks": d["picks"],
                    "Wins": d["wins"],
                    "Win Rate": f"{d['win_rate']*100:.1f}%",
                })
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("No picks met the criteria.")
    else:
        st.caption("No tier data available.")

with col_right:
    st.subheader("📈 Win Rate by Stat Type")
    stat_data = result.get("stat_win_rates", {})
    if stat_data:
        rows = []
        for stat, d in stat_data.items():
            if d["picks"] > 0:
                rows.append({
                    "Stat": stat.capitalize(),
                    "Picks": d["picks"],
                    "Wins": d["wins"],
                    "Win Rate": f"{d['win_rate']*100:.1f}%",
                })
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("No picks met the criteria.")
    else:
        st.caption("No stat data available.")

# ── By Edge Bucket ────────────────────────────────────────────
st.subheader("🎯 Win Rate by Edge Bucket")
edge_data = result.get("edge_win_rates", {})
if edge_data:
    rows = []
    for label, d in edge_data.items():
        if d["picks"] > 0:
            rows.append({
                "Edge Range": label,
                "Picks": d["picks"],
                "Wins": d["wins"],
                "Win Rate": f"{d['win_rate']*100:.1f}%",
            })
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.caption("No picks in any edge bucket.")

# ── Pick Log ──────────────────────────────────────────────────
st.divider()
st.subheader("📋 Recent Pick Log (last 200)")
pick_log = result.get("pick_log", [])
if pick_log:
    display = []
    for p in reversed(pick_log):
        display.append({
            "Date": p["date"],
            "Player": p["player"],
            "Stat": p["stat"].capitalize(),
            "Line": p["line"],
            "Actual": p["actual"],
            "Direction": p["direction"],
            "Result": "✅ WIN" if p["correct"] else "❌ LOSS",
            "Prob": f"{p['model_prob']*100:.1f}%",
            "Tier": p["tier"],
            "Edge": f"{p['edge']*100:.1f}%",
        })
    st.dataframe(display, hide_index=True, use_container_width=True)
else:
    st.caption("No picks in the log.")
