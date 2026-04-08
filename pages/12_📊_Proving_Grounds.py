# pages/12_📊_Proving_Grounds.py
# Historical backtesting UI for SmartAI-NBA ("Proving Grounds").
# Runs the prediction model against historical game log data to validate accuracy.

import streamlit as st

st.set_page_config(
    page_title="Proving Grounds — SmartAI-NBA",
    page_icon="📊",
    layout="wide",
)

from styles.theme import get_global_css
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating
st.session_state["joseph_page_context"] = "page_backtester"
inject_joseph_floating()

from utils.premium_gate import premium_gate
if not premium_gate("Backtester"):
    st.stop()

import html as _html
import json as _json
import csv as _csv
import io as _io
from datetime import datetime as _datetime

# ── Proving Grounds CSS ───────────────────────────────────────
st.markdown("""
<style>
.pg-glass-card {
    background: linear-gradient(135deg, rgba(0,240,255,0.07) 0%, rgba(10,15,30,0.85) 100%);
    border: 1px solid rgba(0,240,255,0.18);
    border-radius: 14px;
    padding: 18px 16px 14px 16px;
    text-align: center;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,240,255,0.08);
    transition: transform 0.2s, box-shadow 0.2s;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.pg-glass-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0,240,255,0.18);
}
.pg-glass-label {
    font-size: 0.72rem;
    color: rgba(255,255,255,0.55);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 4px;
    font-weight: 600;
}
.pg-glass-value {
    font-size: 1.65rem;
    font-weight: 700;
    color: #00f0ff;
    line-height: 1.2;
}
.pg-glass-delta {
    font-size: 0.72rem;
    margin-top: 4px;
    color: rgba(255,255,255,0.45);
}
.pg-glass-delta.positive { color: #00e676; }
.pg-glass-delta.negative { color: #ff5252; }
.pg-hero-banner {
    background: linear-gradient(135deg, rgba(0,240,255,0.12) 0%, rgba(10,15,30,0.92) 100%);
    border: 1px solid rgba(0,240,255,0.25);
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 8px 40px rgba(0,240,255,0.10);
}
.pg-hero-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #00f0ff;
    margin-bottom: 6px;
    letter-spacing: 0.5px;
}
.pg-hero-subtitle {
    font-size: 0.92rem;
    color: rgba(255,255,255,0.70);
    line-height: 1.6;
}
.pg-hero-stat {
    display: inline-block;
    margin-right: 20px;
    font-weight: 600;
    color: #ffffff;
}
.pg-hero-stat .hl { color: #00f0ff; }
.pg-hero-stat .gold { color: #ffd740; }
.pg-hero-stat .green { color: #00e676; }
.pg-tier-elite { background: rgba(255,215,64,0.08); border-left: 3px solid #ffd740; }
.pg-tier-strong { background: rgba(0,240,255,0.06); border-left: 3px solid #00f0ff; }
.pg-tier-value { background: rgba(255,255,255,0.03); border-left: 3px solid rgba(255,255,255,0.3); }
.pg-tier-lean { background: rgba(255,255,255,0.01); border-left: 3px solid rgba(255,255,255,0.12); }
</style>
""", unsafe_allow_html=True)


def _glass_card(label, value, delta="", delta_class=""):
    """Return HTML for a glassmorphism metric card."""
    safe_label = _html.escape(str(label))
    safe_value = _html.escape(str(value))
    safe_delta = _html.escape(str(delta))
    delta_html = (
        f'<div class="pg-glass-delta {_html.escape(delta_class)}">{safe_delta}</div>'
        if delta else ""
    )
    return f"""<div class="pg-glass-card">
        <div class="pg-glass-label">{safe_label}</div>
        <div class="pg-glass-value">{safe_value}</div>
        {delta_html}
    </div>"""


st.title("📊 Proving Grounds")
st.markdown(
    "Validate the model against real game logs. "
    "See win rates, ROI, and tier-by-tier performance metrics."
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Proving Grounds — Validate Before You Bet
    
    The Proving Grounds runs the prediction model against **real historical game logs** to measure accuracy.
    
    **How to Run a Backtest**
    1. Select players (or use all cached players)
    2. Choose the stat types to backtest (points, rebounds, assists, etc.)
    3. Set the date range and minimum edge threshold
    4. Click "Run Backtest" and watch the real-time progress
    
    **Understanding Results**
    - **Win Rate**: Percentage of picks that would have been correct
    - **ROI**: Return on investment assuming flat unit bets at -110 odds
    - **Tier Breakdown**: How each confidence tier (ELITE/STRONG/VALUE/LEAN) performed
    - **By Stat Type**: Which stat categories the model predicts best
    - **Per-Player**: Top/bottom performers with best/worst stat breakdown
    
    **What Good Results Look Like**
    - Overall win rate above 55% is strong
    - ELITE tier should have the highest win rate
    - If LEAN tier beats ELITE, the confidence model needs recalibration
    - Sharpe ratio > 1.0 indicates consistent profitability
    
    💡 **Pro Tips:**
    - Run "Refresh Game Logs" on the Data Feed page first to load historical data
    - Use **A/B Comparison Mode** to test different edge thresholds side-by-side
    - Use date range filtering to analyze specific stretches (post All-Star, playoffs, etc.)
    - Export results to CSV for deeper Excel analysis
    """)

st.divider()

# ── Imports ──────────────────────────────────────────────────
try:
    from engine.backtester import run_backtest
    _BACKTESTER_AVAILABLE = True
except ImportError:
    _BACKTESTER_AVAILABLE = False

try:
    from data.game_log_cache import (
        get_all_cached_players,
        load_game_logs_from_cache,
        save_game_logs_to_cache,
    )
    _CACHE_AVAILABLE = True
except ImportError:
    _CACHE_AVAILABLE = False

try:
    from data.nba_data_service import refresh_historical_data_for_tonight as _refresh_hist
    _HIST_REFRESH_AVAILABLE = True
except ImportError:
    _HIST_REFRESH_AVAILABLE = False

try:
    from engine.clv_tracker import get_clv_summary, validate_model_edge
    _CLV_AVAILABLE = True
except ImportError:
    _CLV_AVAILABLE = False

try:
    from tracking.database import save_backtest_result, load_backtest_results
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

# ── Load cached game logs (needed for sidebar player list) ────
game_logs_by_player = {}
stale_count = 0
if _CACHE_AVAILABLE:
    cached_players = get_all_cached_players()
    if cached_players:
        for pname in cached_players:
            logs, is_stale = load_game_logs_from_cache(pname)
            if logs:
                game_logs_by_player[pname] = logs
                if is_stale:
                    stale_count += 1

# Also check session state (set by Player Simulator page)
session_logs = st.session_state.get("game_logs_by_player", {})
for pname, logs in session_logs.items():
    if logs and pname not in game_logs_by_player:
        game_logs_by_player[pname] = logs

# ── Sidebar Controls ─────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Proving Grounds Settings")

    season = st.selectbox("Season", ["2025-26", "2024-25", "2023-24", "2022-23"], index=0)

    stat_options = [
        "points", "rebounds", "assists", "steals", "blocks", "threes", "turnovers",
        "ftm", "fta", "fgm", "fga", "minutes", "personal_fouls",
        "offensive_rebounds", "defensive_rebounds",
    ]
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

    # ── Date range filtering ──────────────────────────────────
    st.divider()
    st.subheader("📅 Date Range")
    start_date = st.date_input(
        "Start Date",
        value=_datetime(2024, 10, 22),
        help="Only include game logs on or after this date.",
    )
    end_date = st.date_input(
        "End Date",
        value=_datetime.today(),
        help="Only include game logs on or before this date.",
    )
    start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None

    # ── Player selection ──────────────────────────────────────
    st.divider()
    st.subheader("👤 Player Filter")
    all_players = sorted(game_logs_by_player.keys())
    selected_players = st.multiselect(
        "Filter Players (optional)",
        all_players,
        default=[],
        help="Leave empty to backtest all cached players.",
    )

    # ── Simulation depth from Settings ────────────────────────
    sim_depth = st.session_state.get("simulation_depth", 500)
    st.caption(f"Simulation depth: **{sim_depth:,}** (set in ⚙️ Settings)")

    use_real_lines = st.checkbox(
        "📦 Use Real PrizePicks Lines (archive)",
        value=True,
        help="When available, use actual PrizePicks prop lines from the "
             "mirror archive instead of synthetic season-average lines. "
             "Only available for dates the archive has captured.",
    )

    # ── A/B Comparison Mode ───────────────────────────────────
    st.divider()
    ab_mode = st.checkbox(
        "🔀 A/B Comparison Mode",
        value=False,
        help="Run two backtests with different settings side-by-side "
             "to compare which configuration performs best.",
    )
    if ab_mode:
        min_edge_b = st.slider(
            "Config B — Min Edge (%)",
            min_value=1, max_value=20, value=10, step=1,
            help="Edge threshold for the comparison (Config B).",
        ) / 100.0
        tier_filter_b = st.selectbox(
            "Config B — Tier Filter",
            ["All Tiers", "ELITE", "STRONG", "VALUE", "LEAN"],
            index=0,
            key="tier_filter_b",
        )
        tier_filter_val_b = None if tier_filter_b == "All Tiers" else tier_filter_b

    st.divider()
    run_btn = st.button("▶ Run Backtest", type="primary", use_container_width=True)

    st.divider()

    # ── Historical data refresh ───────────────────────────────
    st.subheader("📡 Historical Data")
    st.caption(
        "Auto-load game logs for tonight's players "
        "and update CLV closing lines."
    )
    refresh_hist_btn = st.button(
        "🔄 Refresh Historical Data",
        use_container_width=True,
        disabled=not _HIST_REFRESH_AVAILABLE,
        help="Retrieves the last 30 games per player for all teams playing tonight.",
    )

# ── Info if backtester not available ─────────────────────────
if not _BACKTESTER_AVAILABLE:
    st.error("⚠️ Backtester engine not available. Check engine/backtester.py.")
    st.stop()

# ── Historical Data Refresh Handler ──────────────────────────
if refresh_hist_btn and _HIST_REFRESH_AVAILABLE:
    _prog = st.progress(0, text="Loading historical game logs…")
    def _prog_cb(current, total, msg):
        _prog.progress(min(current / max(total, 1), 1.0), text=msg)

    with st.spinner("Loading historical game logs from API-NBA…"):
        todays_games = st.session_state.get("todays_games", [])
        hist_result = _refresh_hist(games=todays_games, last_n_games=30, progress_callback=_prog_cb)

    _prog.empty()
    refreshed  = hist_result.get("players_refreshed", 0)
    clv_closed = hist_result.get("clv_updated", 0)
    errs       = hist_result.get("errors", 0)

    if refreshed > 0:
        st.success(
            f"✅ Historical data refreshed: **{refreshed} player(s)** cached"
            + (f", **{clv_closed} CLV record(s)** updated" if clv_closed else "")
            + (f", {errs} error(s)" if errs else "")
        )
    elif not todays_games:
        st.warning(
            "⚠️ No tonight's games loaded. Go to **📡 Live Games** and click "
            "**Auto-Load Tonight's Games** first, then refresh historical data."
        )
    else:
        st.info(
            "ℹ️ No game logs retrieved. This typically means the data feed is "
            "temporarily unavailable, or players don't have IDs in the loaded data."
        )

# ── Status ────────────────────────────────────────────────────
_fresh = len(game_logs_by_player) - stale_count
if game_logs_by_player:
    st.info(
        f"📁 **{len(game_logs_by_player)} player(s)** with cached game logs available "
        f"({_fresh} fresh · {stale_count} stale). "
        f"Use **🔄 Refresh Historical Data** in the sidebar to update all logs at once."
    )
else:
    st.warning(
        "No game log data found. Click **🔄 Refresh Historical Data** in the sidebar "
        "(requires tonight's games to be loaded on **📡 Live Games** first). "
        "Or go to **🔮 Player Simulator**, search for players, "
        "and their logs will be cached for backtesting."
    )
    if not _HIST_REFRESH_AVAILABLE:
        st.stop()

# ── CLV Model Validation Panel ────────────────────────────────
if _CLV_AVAILABLE:
    clv_summary = get_clv_summary(days=90)
    clv_records_count = clv_summary.get("total_records", 0)
    if clv_records_count > 0:
        with st.expander(
            f"🎯 CLV Model Validation — {clv_records_count} records (last 90 days)",
            expanded=False,
        ):
            avg_clv = clv_summary.get("avg_clv", 0.0)
            pos_rate = clv_summary.get("positive_clv_rate", 0.0)
            clv_c1, clv_c2, clv_c3 = st.columns(3)
            clv_c1.metric(
                "Avg CLV",
                f"{avg_clv:+.2f}",
                help="Positive = model consistently beat the closing line (real edge). "
                     "Negative = market moved away from model (no edge).",
            )
            clv_c2.metric(
                "Positive CLV Rate",
                f"{pos_rate*100:.1f}%",
                delta="✅ Sharp" if pos_rate > 0.55 else "⚠️ Below sharp threshold",
                delta_color="off",
                help="% of picks where the market moved in our direction (beat close).",
            )
            clv_c3.metric(
                "Total Records",
                clv_records_count,
                help="Number of picks with both opening and closing lines recorded.",
            )

            # Per-stat breakdown
            edge_data = validate_model_edge(days=90)
            clv_by_stat = edge_data.get("clv_by_stat", {})
            if clv_by_stat:
                st.markdown("**CLV by Stat Type:**")
                _clv_rows = []
                for stat, info in sorted(clv_by_stat.items()):
                    cnt = info.get("count", 0)
                    if cnt >= 3:
                        _clv_rows.append({
                            "Stat": stat.capitalize(),
                            "Picks": cnt,
                            "Avg CLV": f"{info.get('avg_clv', 0):+.2f}",
                            "Positive Rate": f"{info.get('positive_clv_rate', 0)*100:.1f}%",
                            "Signal": "✅ Edge" if info.get("avg_clv", 0) > 0 else "❌ No Edge",
                        })
                if _clv_rows:
                    st.dataframe(_clv_rows, hide_index=True, use_container_width=True)

        st.divider()

# ── Past Backtest Runs ────────────────────────────────────────
if _DB_AVAILABLE:
    past_runs = load_backtest_results(limit=10)
    if past_runs:
        with st.expander(f"📜 Past Backtest Runs ({len(past_runs)} saved)", expanded=False):
            _run_rows = []
            for r in past_runs:
                _run_rows.append({
                    "Date": str(r.get("run_timestamp", r.get("created_at", "")))[:19],
                    "Season": r.get("season", ""),
                    "Picks": r.get("total_picks", 0),
                    "Win Rate": f"{r.get('win_rate', 0)*100:.1f}%",
                    "ROI": f"{r.get('roi', 0)*100:.2f}%",
                    "P&L": f"{r.get('total_pnl', 0):+.2f}",
                    "Min Edge": f"{r.get('min_edge', 0)*100:.0f}%",
                })
            st.dataframe(_run_rows, hide_index=True, use_container_width=True)

if not game_logs_by_player:
    st.stop()


# ── Helper: Run one backtest with progress ────────────────────
def _run_single_backtest(label, edge, tier_filt, progress_placeholder):
    """Run a single backtest with animated progress bar."""
    _prog = progress_placeholder.progress(0, text=f"[{label}] Initializing…")

    def _bt_progress(current, total, msg):
        frac = min(current / max(total, 1), 1.0)
        _prog.progress(frac, text=f"[{label}] {msg}")

    res = run_backtest(
        season=season,
        stat_types=selected_stats,
        min_edge=edge,
        tier_filter=tier_filt,
        game_logs_by_player=game_logs_by_player,
        progress_callback=_bt_progress,
        number_of_simulations=sim_depth,
        start_date=start_date_str,
        end_date=end_date_str,
        selected_players=selected_players if selected_players else None,
    )
    _prog.progress(1.0, text=f"[{label}] Complete ✅")
    return res


# ── Run Backtest ──────────────────────────────────────────────
if run_btn:
    if not selected_stats:
        st.error("Please select at least one stat type.")
        st.stop()

    try:
        prog_a = st.empty()
        result_a = _run_single_backtest("Config A", min_edge, tier_filter_val, prog_a)

        result_b = None
        if ab_mode:
            prog_b = st.empty()
            result_b = _run_single_backtest("Config B", min_edge_b, tier_filter_val_b, prog_b)
            prog_b.empty()

        prog_a.empty()
        st.session_state["backtest_result"] = result_a

        # Auto-save to database
        if _DB_AVAILABLE and result_a.get("status") == "ok":
            save_backtest_result(result_a)

        if result_b:
            st.session_state["backtest_result_b"] = result_b
            if _DB_AVAILABLE and result_b.get("status") == "ok":
                save_backtest_result(result_b)
        else:
            st.session_state.pop("backtest_result_b", None)

    except Exception as _bt_err:
        st.error(f"❌ Backtest failed: {_bt_err}")


# ── Helper: Render results for one config ─────────────────────
def _render_results(result, config_label=""):
    """Render all result sections for a single backtest result."""
    if not result:
        st.markdown("### Configure settings and click **▶ Run Backtest** to see results.")
        return

    if result.get("status") == "no_data":
        st.warning(result.get("message", "No data available."))
        return

    # ── Hero Summary Banner ───────────────────────────────────
    _wr = result.get("win_rate", 0)
    _tp = result.get("total_picks", 0)
    _roi = result.get("roi", 0)
    _sharpe = result.get("sharpe_ratio", 0)
    _elite_wr = result.get("tier_win_rates", {}).get("ELITE", {}).get("win_rate", 0)
    _ws = result.get("longest_win_streak", 0)
    _ls = result.get("longest_loss_streak", 0)
    _season = _html.escape(str(result.get("season", "")))
    _prefix = f"<strong>{_html.escape(config_label)}</strong> · " if config_label else ""

    st.markdown(f"""
    <div class="pg-hero-banner">
        <div class="pg-hero-title">📊 BACKTEST RESULTS</div>
        <div class="pg-hero-subtitle">
            {_prefix}Season {_season} &nbsp;|&nbsp;
            <span class="pg-hero-stat"><span class="hl">{_tp:,}</span> Picks</span>
            <span class="pg-hero-stat"><span class="hl">{_wr*100:.1f}%</span> Win Rate</span>
            <span class="pg-hero-stat">ELITE: <span class="gold">{_elite_wr*100:.0f}%</span> WR</span>
            <span class="pg-hero-stat">ROI: <span class="green">{_roi*100:+.1f}%</span></span>
            <span class="pg-hero-stat">Sharpe: <span class="hl">{_sharpe:.2f}</span></span>
            <span class="pg-hero-stat">🔥{_ws}W / ❄️{_ls}L streaks</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Glassmorphism Metric Cards ────────────────────────────
    _dd = result.get("max_drawdown", 0.0)
    _be_delta = (_wr - 0.5238) * 100

    cards = [
        ("Total Picks", f"{_tp:,}", "", ""),
        ("Wins ✅", str(result["wins"]), "", ""),
        ("Losses ❌", str(result["losses"]), "", ""),
        ("Win Rate", f"{_wr*100:.1f}%",
         f"{_be_delta:+.1f}% vs breakeven",
         "positive" if _be_delta > 0 else "negative"),
        ("ROI", f"{_roi*100:.2f}%",
         f"${result['total_pnl']:.2f} P&L",
         "positive" if _roi > 0 else "negative"),
        ("Sharpe Ratio", f"{_sharpe:.3f}",
         "✅ Good" if _sharpe > 1.0 else ("⚠️ Fair" if _sharpe > 0 else "❌ Bad"), ""),
        ("Max Drawdown", f"{_dd:.2f}u", "Peak-to-trough", ""),
        ("Win Streak 🔥", str(_ws), "", "positive"),
        ("Loss Streak ❄️", str(_ls), "", "negative" if _ls > 5 else ""),
    ]

    # Render 9 cards in rows of 5 + 4
    _row1_cols = st.columns(5)
    for i, col in enumerate(_row1_cols):
        if i < len(cards):
            col.markdown(_glass_card(*cards[i]), unsafe_allow_html=True)
    _row2_cols = st.columns(4)
    for i, col in enumerate(_row2_cols):
        idx = i + 5
        if idx < len(cards):
            col.markdown(_glass_card(*cards[idx]), unsafe_allow_html=True)

    st.divider()

    # ── Sharpe / Drawdown / OOS Explainer ─────────────────────
    with st.expander("📖 Understanding Sharpe Ratio, Drawdown & Out-of-Sample", expanded=False):
        st.markdown("""
        **Sharpe Ratio** measures return-per-unit-of-risk (consistency).
        - > 2.0 = Excellent (consistent profitable edge)
        - 1.0–2.0 = Good
        - 0–1.0 = Fair (profitable but with variance)
        - < 0 = Strategy is losing money

        **Max Drawdown** is the worst peak-to-trough decline in cumulative units.
        - -5 means the strategy fell 5 units from its best point before recovering.
        - Smaller (less negative) is better.

        **Win/Loss Streaks** track longest consecutive wins and losses.
        - Long loss streaks mean higher bankroll risk.
        - Consistent short streaks indicate stable variance.

        **Out-of-Sample (OOS) Split**: The pick log is split 70% in-sample / 30% OOS.
        - If OOS win rate ≈ in-sample win rate, the model generalizes well.
        - If OOS is significantly lower, the model may be overfit to historical data.
        """)

    # ── In-Sample vs Out-of-Sample ────────────────────────────
    oos = result.get("oos_metrics", {})
    if oos and oos.get("oos_picks", 0) > 0:
        st.subheader("🔬 In-Sample vs Out-of-Sample Validation")
        oos_col1, oos_col2, oos_col3, oos_col4 = st.columns(4)
        oos_col1.metric("In-Sample Picks", oos.get("is_picks", 0))
        oos_col2.metric("In-Sample Win Rate", f"{oos.get('is_win_rate', 0)*100:.1f}%")
        oos_col3.metric("OOS Picks", oos.get("oos_picks", 0))
        _oos_wr = oos.get("oos_win_rate", 0)
        _is_wr = oos.get("is_win_rate", 0)
        _wr_gap = (_oos_wr - _is_wr) * 100
        oos_col4.metric(
            "OOS Win Rate",
            f"{_oos_wr*100:.1f}%",
            delta=f"{_wr_gap:+.1f}% vs in-sample",
            delta_color="normal",
        )
        if abs(_wr_gap) < 3:
            st.success("✅ Model generalizes well — OOS win rate is within 3% of in-sample rate.")
        elif _wr_gap < -5:
            st.warning(
                f"⚠️ OOS win rate is {abs(_wr_gap):.1f}% below in-sample. "
                "The model may be overfit — check if thresholds need adjustment."
            )
        else:
            st.info(f"ℹ️ OOS win rate gap: {_wr_gap:+.1f}%")

    st.divider()

    # ── Cumulative P&L Chart (Plotly) ─────────────────────────
    pick_log = result.get("pick_log", [])
    if pick_log:
        st.subheader("📈 Cumulative P&L Curve")
        _PAYOUT = 0.909
        _cumulative = 0.0
        _pnl_series = []
        _peak_series = []
        _dates_list = []
        _players_list = []
        _stats_list = []
        _peak = 0.0

        for _p in pick_log:
            _cumulative += _PAYOUT if _p["correct"] else -1.0
            _pnl_series.append(round(_cumulative, 2))
            if _cumulative > _peak:
                _peak = _cumulative
            _peak_series.append(round(_peak, 2))
            _dates_list.append(_p.get("date", ""))
            _players_list.append(_p.get("player", ""))
            _stats_list.append(_p.get("stat", "").capitalize())

        if _PLOTLY_AVAILABLE:
            fig = go.Figure()

            # Determine fill color based on final P&L
            _fill_color = "rgba(0,230,118,0.12)" if _cumulative >= 0 else "rgba(255,82,82,0.12)"
            _line_color = "#00f0ff"

            # Build hover text
            _hover = [
                f"Pick #{i+1}<br>{_dates_list[i]}<br>"
                f"{_players_list[i]} — {_stats_list[i]}<br>"
                f"P&L: {_pnl_series[i]:+.2f}u"
                for i in range(len(_pnl_series))
            ]

            fig.add_trace(go.Scatter(
                x=list(range(1, len(_pnl_series) + 1)),
                y=_pnl_series,
                mode="lines",
                name="Cumulative P&L",
                line=dict(color=_line_color, width=2),
                fill="tozeroy",
                fillcolor=_fill_color,
                hovertext=_hover,
                hoverinfo="text",
            ))

            # Drawdown shading (peak line)
            fig.add_trace(go.Scatter(
                x=list(range(1, len(_peak_series) + 1)),
                y=_peak_series,
                mode="lines",
                name="Peak",
                line=dict(color="rgba(255,215,64,0.3)", width=1, dash="dot"),
                hoverinfo="skip",
            ))

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(7,10,19,0.8)",
                height=300,
                margin=dict(l=40, r=20, t=30, b=40),
                xaxis=dict(title="Pick #", gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Units", gridcolor="rgba(255,255,255,0.05)", zeroline=True,
                           zerolinecolor="rgba(255,255,255,0.15)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                font=dict(color="rgba(255,255,255,0.7)", size=11),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Fallback to built-in chart if Plotly not installed
            st.line_chart({"Cumulative P&L (units)": _pnl_series}, height=260)

        st.caption(
            f"📊 {len(pick_log)} picks · "
            f"Final: {_cumulative:+.2f} units · "
            f"ROI: {result['roi']*100:+.2f}% per pick"
        )

        st.divider()

    # ── By Tier (color-coded) ─────────────────────────────────
    with st.expander("📊 Win Rate & ROI by Model Tier", expanded=True):
        tier_data = result.get("tier_win_rates", {})
        if tier_data:
            _tier_order = ["ELITE", "STRONG", "VALUE", "LEAN"]
            _tier_css = {"ELITE": "pg-tier-elite", "STRONG": "pg-tier-strong",
                         "VALUE": "pg-tier-value", "LEAN": "pg-tier-lean"}
            for tier in _tier_order:
                d = tier_data.get(tier)
                if not d or d["picks"] == 0:
                    continue
                _roi_pct = d.get("roi", 0.0) * 100
                _pnl = d.get("pnl", 0.0)
                _wr_pct = d["win_rate"] * 100
                _css_class = _tier_css.get(tier, "")
                # Color scale for win rate: green if > 55%, yellow if 50-55%, red if < 50%
                if _wr_pct >= 55:
                    _wr_color = "#00e676"
                elif _wr_pct >= 50:
                    _wr_color = "#ffd740"
                else:
                    _wr_color = "#ff5252"
                _safe_tier = _html.escape(tier)
                st.markdown(f"""
                <div class="{_html.escape(_css_class)}" style="padding:10px 16px;border-radius:8px;margin-bottom:8px;">
                    <strong>{_safe_tier}</strong> &nbsp;·&nbsp;
                    {d['picks']} picks &nbsp;·&nbsp;
                    <span style="color:{_wr_color};font-weight:700;">{_wr_pct:.1f}% WR</span> &nbsp;·&nbsp;
                    ROI: {_roi_pct:+.2f}% &nbsp;·&nbsp;
                    P&amp;L: {_pnl:+.2f}u &nbsp;
                    {"✅" if _roi_pct > 0 else "❌"}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No tier data available.")

    # ── By Stat Type (color-coded) ────────────────────────────
    with st.expander("📈 Win Rate by Stat Type", expanded=True):
        stat_data = result.get("stat_win_rates", {})
        if stat_data:
            rows = []
            for stat, d in sorted(stat_data.items(), key=lambda x: -x[1]["wins"]):
                if d["picks"] > 0:
                    _wr_val = d["win_rate"] * 100
                    rows.append({
                        "Stat": stat.capitalize(),
                        "Picks": d["picks"],
                        "Wins": d["wins"],
                        "Losses": d["picks"] - d["wins"],
                        "Win Rate": f"{_wr_val:.1f}%",
                        "Above 52%": "✅" if d["win_rate"] > 0.52 else "❌",
                    })
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.caption("No picks met the criteria.")
        else:
            st.caption("No stat data available.")

    # ── By Edge Bucket ────────────────────────────────────────
    with st.expander("🎯 Win Rate by Edge Bucket", expanded=True):
        edge_bdata = result.get("edge_win_rates", {})
        if edge_bdata:
            rows = []
            for label, d in edge_bdata.items():
                if d["picks"] > 0:
                    rows.append({
                        "Edge Range": label,
                        "Picks": d["picks"],
                        "Wins": d["wins"],
                        "Win Rate": f"{d['win_rate']*100:.1f}%",
                        "Insight": (
                            "✅ Higher edge = higher win rate (healthy)" if d["win_rate"] > 0.55
                            else "⚠️ Expected >55% win rate at this edge level"
                        ),
                    })
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.caption("No picks in any edge bucket.")

    # ── Per-Player Breakdown ──────────────────────────────────
    player_data = result.get("player_win_rates", {})
    if player_data:
        with st.expander(f"👤 Per-Player Breakdown ({len(player_data)} players)", expanded=False):
            _player_rows = []
            for pname, pd in sorted(player_data.items(), key=lambda x: -x[1]["picks"]):
                if pd["picks"] > 0:
                    _player_rows.append({
                        "Player": pname,
                        "Picks": pd["picks"],
                        "Win Rate": f"{pd['win_rate']*100:.1f}%",
                        "ROI": f"{pd['roi']*100:.2f}%",
                        "P&L": f"{pd['pnl']:+.2f}",
                        "Best Stat": pd.get("best_stat", "N/A"),
                        "Worst Stat": pd.get("worst_stat", "N/A"),
                    })
            if _player_rows:
                st.markdown("**Top Performers** (sorted by pick count):")
                st.dataframe(_player_rows[:20], hide_index=True, use_container_width=True)
                if len(_player_rows) > 20:
                    with st.expander("Show all players"):
                        st.dataframe(_player_rows, hide_index=True, use_container_width=True)

    st.divider()

    # ── Pick Log ──────────────────────────────────────────────
    with st.expander("📋 Full Pick Log (last 200)", expanded=False):
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

            # Download buttons — JSON and CSV
            _dl_col1, _dl_col2 = st.columns(2)
            _log_json = _json.dumps(pick_log, indent=2)
            _dl_col1.download_button(
                "⬇️ Download Pick Log (JSON)",
                data=_log_json,
                file_name=f"backtest_pick_log_{result.get('season','')}.json",
                mime="application/json",
            )

            # CSV export
            _csv_buffer = _io.StringIO()
            if pick_log:
                _writer = _csv.DictWriter(_csv_buffer, fieldnames=pick_log[0].keys())
                _writer.writeheader()
                _writer.writerows(pick_log)
            _dl_col2.download_button(
                "⬇️ Download Pick Log (CSV)",
                data=_csv_buffer.getvalue(),
                file_name=f"backtest_pick_log_{result.get('season','')}.csv",
                mime="text/csv",
            )
        else:
            st.caption("No picks in the log.")


# ── Display Results ───────────────────────────────────────────
result = st.session_state.get("backtest_result")
result_b = st.session_state.get("backtest_result_b")

if not result and not result_b:
    st.markdown("### Configure settings and click **▶ Run Backtest** to see results.")
    st.stop()

if result_b:
    # A/B Comparison mode — show side by side
    st.subheader("🔀 A/B Comparison Results")
    tab_a, tab_b = st.tabs(["⚙️ Config A", "⚙️ Config B"])
    with tab_a:
        _render_results(result, config_label="Config A")
    with tab_b:
        _render_results(result_b, config_label="Config B")

    # Comparison summary
    if (result and result.get("status") == "ok" and
            result_b and result_b.get("status") == "ok"):
        st.divider()
        st.subheader("📊 Head-to-Head Comparison")
        _cmp_cols = st.columns(5)
        _metrics_cmp = [
            ("Win Rate", result["win_rate"]*100, result_b["win_rate"]*100, "%"),
            ("ROI", result["roi"]*100, result_b["roi"]*100, "%"),
            ("Sharpe", result.get("sharpe_ratio", 0), result_b.get("sharpe_ratio", 0), ""),
            ("Picks", result["total_picks"], result_b["total_picks"], ""),
            ("P&L", result["total_pnl"], result_b["total_pnl"], "u"),
        ]
        for i, (name, val_a, val_b, unit) in enumerate(_metrics_cmp):
            with _cmp_cols[i]:
                _winner = "A" if val_a >= val_b else "B"
                st.metric(name, f"A: {val_a:.1f}{unit}", delta=f"B: {val_b:.1f}{unit}",
                          delta_color="off")
                st.caption(f"Winner: Config {_winner}")
else:
    _render_results(result)
