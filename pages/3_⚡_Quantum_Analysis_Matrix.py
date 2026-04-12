# ============================================================
# FILE: pages/3_⚡_Quantum_Analysis_Matrix.py
# PURPOSE: The main analysis page. Runs Quantum Matrix Engine 5.6 simulation
#          for each prop and shows probability, edge, tier, and
#          directional forces in the Quantum Design System (QDS) UI.
# CONNECTS TO: engine/ (all modules), data_manager.py, session state
# ============================================================

import streamlit as st  # Main UI framework
import streamlit.components.v1 as _components  # For iframe-based card rendering
import math             # For rounding in display
import html as _html   # For safe HTML escaping in inline cards
import datetime         # For analysis result freshness timestamps
import time             # For elapsed-time measurement
import os               # For logo path resolution
import hashlib          # For content-hash caching of simulation results
import concurrent.futures  # For parallel prop analysis

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

# Import our engine modules
from engine.simulation import (
    run_quantum_matrix_simulation,
    build_histogram_from_results,
    simulate_combo_stat,
    simulate_fantasy_score,
    simulate_double_double,
    simulate_triple_double,
    generate_alt_line_probabilities,
)
from engine import COMBO_STAT_TYPES, FANTASY_STAT_TYPES, YESNO_STAT_TYPES
from engine.projections import build_player_projection, get_stat_standard_deviation, calculate_teammate_out_boost, POSITION_PRIORS
from engine.edge_detection import analyze_directional_forces, should_avoid_prop, detect_correlated_props, detect_trap_line, detect_line_sharpness, classify_bet_type, calculate_composite_win_score

# ── Lazy-loaded optional engine modules ──────────────────────────────────────
# These are imported on first use rather than at module level to reduce the
# initial import chain when navigating to this page.  Each helper returns the
# callable (or None) and caches the result in a module-level variable.

_rotation_tracker_available = None  # sentinel; resolved on first call
track_minutes_trend = None          # lazy-loaded
def _get_track_minutes_trend():
    global _rotation_tracker_available, track_minutes_trend
    if _rotation_tracker_available is None:
        try:
            from engine.rotation_tracker import track_minutes_trend as _fn
            _rotation_tracker_available = _fn
            track_minutes_trend = _fn
        except ImportError:
            _rotation_tracker_available = False
    return _rotation_tracker_available if _rotation_tracker_available else None
from engine.confidence import calculate_confidence_score, get_tier_color
from engine.math_helpers import calculate_edge_percentage, clamp_probability
from engine.explainer import generate_pick_explanation
from engine.odds_engine import american_odds_to_implied_probability as _odds_to_implied_prob
from engine.calibration import get_calibration_adjustment   # C10: historical calibration
from engine.clv_tracker import store_opening_line, get_stat_type_clv_penalties  # C12: CLV + penalties

detect_line_movement = None  # lazy-loaded on first use
def _get_detect_line_movement():
    global detect_line_movement
    if detect_line_movement is None:
        try:
            from engine.market_movement import detect_line_movement as _fn
            detect_line_movement = _fn
        except ImportError:
            detect_line_movement = False
    return detect_line_movement if detect_line_movement else None

calculate_matchup_adjustment = None  # lazy-loaded
get_matchup_force_signal = None      # lazy-loaded
def _get_matchup_fns():
    global calculate_matchup_adjustment, get_matchup_force_signal
    if calculate_matchup_adjustment is None:
        try:
            from engine.matchup_history import (
                calculate_matchup_adjustment as _adj,
                get_matchup_force_signal as _sig,
            )
            calculate_matchup_adjustment = _adj
            get_matchup_force_signal = _sig
        except ImportError:
            calculate_matchup_adjustment = False
            get_matchup_force_signal = False
    return (
        calculate_matchup_adjustment if calculate_matchup_adjustment else None,
        get_matchup_force_signal if get_matchup_force_signal else None,
    )

get_ensemble_projection = None  # lazy-loaded
_ensemble_available = None      # sentinel; resolved on first call
def _get_ensemble_projection():
    global get_ensemble_projection, _ensemble_available
    if _ensemble_available is None:
        try:
            from engine.ensemble import get_ensemble_projection as _fn
            get_ensemble_projection = _fn
            _ensemble_available = True
        except ImportError:
            _ensemble_available = False
            get_ensemble_projection = False
    return get_ensemble_projection if get_ensemble_projection else None

simulate_game_script = None          # lazy-loaded
blend_with_flat_simulation = None    # lazy-loaded
_game_script_available = None        # sentinel
def _get_game_script_fns():
    global simulate_game_script, blend_with_flat_simulation, _game_script_available
    if _game_script_available is None:
        try:
            from engine.game_script import (
                simulate_game_script as _sim,
                blend_with_flat_simulation as _blend,
            )
            simulate_game_script = _sim
            blend_with_flat_simulation = _blend
            _game_script_available = True
        except ImportError:
            _game_script_available = False
            simulate_game_script = False
            blend_with_flat_simulation = False
    return (
        simulate_game_script if simulate_game_script else None,
        blend_with_flat_simulation if blend_with_flat_simulation else None,
    )

project_player_minutes = None    # lazy-loaded
_minutes_model_available = None  # sentinel
def _get_project_player_minutes():
    global project_player_minutes, _minutes_model_available
    if _minutes_model_available is None:
        try:
            from engine.minutes_model import project_player_minutes as _fn
            project_player_minutes = _fn
            _minutes_model_available = True
        except ImportError:
            _minutes_model_available = False
            project_player_minutes = False
    return project_player_minutes if project_player_minutes else None

# Import data loading functions
from data.data_manager import (
    load_players_data,
    load_defensive_ratings_data,
    load_teams_data,
    find_player_by_name,
    load_props_from_session,
    get_roster_health_report,
    validate_props_against_roster,
    get_player_status,
    get_status_badge_html,
    load_injury_status,
)

# Import the theme helpers — including new QDS generators
from styles.theme import (
    get_global_css,
    get_logo_img_tag,
    get_roster_health_html,
    get_best_bets_section_html,
    get_qds_css,
    get_qds_metrics_grid_html,
    get_qds_prop_card_html,
    get_qds_matchup_header_html,
    get_qds_team_card_html,
    get_qds_strategy_table_html,
    get_qds_framework_logic_html,
    get_qds_final_verdict_html,
    get_education_box_html,
    GLOSSARY,
)

from data.platform_mappings import COMBO_STATS, FANTASY_SCORING

from utils.renderers import compile_card_matrix as _compile_card_matrix
from utils.renderers import compile_unified_card_matrix as _compile_unified_matrix
from utils.renderers import build_horizontal_card_html as _build_h_card
from styles.theme import get_quantum_card_matrix_css as _get_qcm_css

# ── Glassmorphic Trading-Card imports ────────────────────────────────────────
from styles.theme import get_glassmorphic_card_css as _get_gm_css
from styles.theme import get_player_trading_card_html as _get_trading_card_html
from utils.data_grouper import group_props_by_player as _group_props
from utils.player_modal import show_player_spotlight as _show_spotlight

# ── Section logo paths ────────────────────────────────────────────────────────
# Logos are stored in assets/ and loaded via st.image() for efficient serving.
_ASSETS_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
# Legacy logo paths disabled – branding removed from UI
_GOLD_LOGO_PATH   = os.path.join(_ASSETS_DIR, "NewGold_Logo.png")


# ── Change 10: Content-Hash Cache for Simulation Results ─────────────────────
# When a user re-runs analysis with the same prop pool, unchanged props return
# instantly from this session-state cache.  Only new/modified props are
# re-computed.  Cache is keyed on (player_name, stat_type, line, sim_depth).
def _prop_cache_key(player_name: str, stat_type: str, line: float,
                    sim_depth: int) -> str:
    """Return a deterministic hash key for a prop's simulation cache."""
    raw = f"{player_name.strip().lower()}|{stat_type.strip().lower()}|{line:.1f}|{sim_depth}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_sim_cache() -> dict:
    """Return the mutable simulation cache dict from session state."""
    if "_sim_result_cache" not in st.session_state:
        st.session_state["_sim_result_cache"] = {}
    return st.session_state["_sim_result_cache"]


# ── Iframe card renderer ─────────────────────────────────────────────────────
# Renders the unified card matrix inside a self-resizing <iframe> via
# streamlit.components.v1.html() instead of st.html().
#
# Why iframe rendering is preferred:
#   1. Atomic delivery — the iframe either loads fully or not at all; a
#      mid-render WebSocket closure does not crash the page.
#   2. CSS isolation — card styles cannot leak into (or be affected by) the
#      main Streamlit page.
#   3. Self-resizing — a ResizeObserver + toggle listener adjusts the iframe
#      height when <details> cards are expanded / collapsed, so no fixed
#      height or scroll-bar is needed.
# ---------------------------------------------------------------------------

_MIN_IFRAME_HEIGHT = 400       # px — minimum even for a single player
_HEIGHT_PER_PLAYER = 200       # px — collapsed card ≈ 180 px + padding
_MAX_IFRAME_HEIGHT = 12000     # px — generous cap; no scrollbar inside iframes
_LAZY_CHUNK_SIZE = 50          # players per iframe — larger chunks = fewer iframes
_MAX_BIO_PREFETCH_WORKERS = 8  # max threads for parallel bio pre-fetching

# Injury status confidence penalties (points deducted from SAFE Score)
_DOUBTFUL_INJURY_PENALTY = 8.0      # Doubtful: ~75% chance of sitting
_QUESTIONABLE_INJURY_PENALTY = 4.0  # Questionable/GTD: uncertain availability

# Tier → emoji mapping used in incremental rendering feedback
_TIER_EMOJI = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}

# ── Iframe auto-height script (v3 — mobile-safe) ────────────────────────────
# Sends ``streamlit:setFrameHeight`` postMessage so Streamlit adjusts the
# iframe height.  Designed to MINIMISE postMessage traffic:
#
#   • On load: sends ONE height message.
#   • On ``<details>`` toggle: sends ONE height message (user-initiated only).
#   • On mobile scroll / address-bar show-hide: does NOTHING.  The iframe
#     uses ``scrolling=False`` and a generous initial ``height`` so it never
#     needs continuous ResizeObserver-driven resize.
#
# Previous versions used a ResizeObserver watching ``document.body`` which
# fired on every CSS reflow (including mobile address-bar show/hide and
# parent-page scroll-induced relayouts).  With 20-30+ iframes on the page
# this cascaded hundreds of postMessages per scroll, overwhelmed the
# Streamlit React frontend, caused WebSocket disconnects, and triggered
# a full page rerun (the "app restart" the user reported).
#
# The new approach removes the ResizeObserver entirely and instead uses a
# targeted ``toggle`` event listener that fires ONLY when the user clicks
# a ``<details>/<summary>`` element.
_IFRAME_RESIZE_JS = (
    "<script>"
    "(function(){"
    "var lastH=0,tid=0;"
    "function sendHeight(){"
    "var h=document.body.scrollHeight;"
    "if(Math.abs(h-lastH)<4)return;"
    "lastH=h;"
    "window.parent.postMessage({type:'streamlit:setFrameHeight',height:h},'*')"
    "}"
    # Debounced wrapper — at most one postMessage per 150 ms.
    # Prevents message storms when multiple events fire in quick
    # succession (e.g. several images loading at once).
    "function debouncedSend(){clearTimeout(tid);tid=setTimeout(sendHeight,150)}"
    # Send initial height once DOM is ready
    "sendHeight();"
    # Re-measure only when a <details> element is toggled (user action).
    # The 60ms delay lets the browser finish the expand/collapse layout
    # shift before we measure scrollHeight.
    "document.addEventListener('toggle',function(){setTimeout(sendHeight,60)},true);"
    # Handle images loading late (can change content height) — debounced
    # so multiple images loading in the same frame don't create a burst
    # of postMessages that overwhelm the Streamlit WebSocket.
    "document.querySelectorAll('img').forEach(function(img){"
    "if(!img.complete)img.addEventListener('load',debouncedSend)"
    "})"
    "})()"
    "</script>"
)


def _render_card_iframe(card_html, player_count):
    """Render *card_html* inside a non-scrolling iframe with auto-height.

    Uses ``streamlit.components.v1.html()`` which creates a real ``<iframe>``
    with full CSS isolation.  A lightweight script inside the iframe sends
    a single ``streamlit:setFrameHeight`` message on load and on
    ``<details>`` toggle so the iframe height matches its content.

    The iframe uses ``scrolling=False`` — it should never need a scrollbar
    because the initial ``height`` estimate is generous and the script
    corrects it on load.  This eliminates the ResizeObserver feedback loop
    that caused mobile "app restart" issues.

    Parameters
    ----------
    card_html : str
        Complete HTML (including ``<style>`` blocks) returned by
        :func:`utils.renderers.compile_unified_card_matrix`.
    player_count : int
        Number of player groups — used to estimate the initial iframe
        height before the load-time script adjusts it.
    """
    _est_h = max(_MIN_IFRAME_HEIGHT, min(player_count * _HEIGHT_PER_PLAYER, _MAX_IFRAME_HEIGHT))
    _doc = (
        "<!DOCTYPE html><html><head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>"
        "html{overflow:hidden;overscroll-behavior:contain;touch-action:pan-y}"
        "body{margin:0;padding:0;background:transparent;color:#e0e0e0;"
        "overscroll-behavior:contain;overflow:hidden;touch-action:pan-y}"
        "</style>"
        "</head><body>"
        f"{card_html}"
        f"{_IFRAME_RESIZE_JS}"
        "</body></html>"
    )
    _components.html(_doc, height=_est_h, scrolling=False)


st.set_page_config(
    page_title="Neural Analysis — SmartBetPro NBA",
    page_icon="⚡",
    layout="wide",
)

# Inject global CSS + QDS CSS
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)
st.markdown(_get_gm_css(), unsafe_allow_html=True)

# ── Reduce excessive bottom padding / blank space ─────────────
# Also disable pull-to-refresh on mobile to prevent accidental reloads
# when scrolling through player bets.  The overscroll-behavior rule must
# cover EVERY scrollable ancestor Streamlit renders — not just html/body
# — because the actual scrolling container is a nested <div> (e.g.
# .main, [data-testid="stAppViewContainer"]).  Without this the mobile
# browser still triggers its native pull-to-refresh gesture and
# "restarts" the app mid-scroll.
st.markdown(
    '<style>'
    '.main .block-container{padding-bottom:1rem !important}'
    'html,body,.stApp,[data-testid="stAppViewContainer"],'
    'section[data-testid="stMain"],.main,.block-container'
    '{overscroll-behavior-y:contain !important}'
    # ── Mobile: prevent accidental widget taps while scrolling ──
    # ``touch-action:manipulation`` disables double-tap-to-zoom and
    # fast-tap on interactive widgets, reducing the chance that a
    # scroll gesture accidentally triggers a Streamlit rerun.
    # ``min-height:48px`` meets mobile touch-target guidelines.
    # Applied to ALL interactive Streamlit widget containers.
    '[data-testid="stToggle"],'
    '[data-testid="stRadio"],'
    '[data-testid="stCheckbox"],'
    '[data-testid="stButton"],'
    '[data-testid="stSelectbox"],'
    '[data-testid="stMultiSelect"]'
    '{touch-action:manipulation;min-height:48px}'
    # ── Prevent iframes from intercepting scroll events ──────
    # During momentum scroll on mobile, iframes can capture touch
    # events and cause Streamlit component re-renders.  Setting
    # pointer-events:none on iframes WHILE the user is scrolling
    # is handled by the JS below; this CSS sets a safe default
    # transition so the pointer-events change is not jarring.
    'iframe{transition:pointer-events 0.1s}'
    '</style>',
    unsafe_allow_html=True,
)

# ── JavaScript: Disable iframe pointer events during scroll ──────
# When the user is actively scrolling, iframes can accidentally
# capture touch/pointer events and trigger Streamlit component
# re-renders (postMessage traffic, focus changes, etc.).  This
# script sets pointer-events:none on all iframes during scroll
# and re-enables them 300ms after scrolling stops.
#
# Also adds a touch-move handler that prevents pull-to-refresh
# when the page is scrolled to the top on mobile browsers where
# overscroll-behavior CSS is not fully supported (older Safari).
st.markdown(
    """<script>
    (function(){
        if(window.__qamScrollGuard) return;
        window.__qamScrollGuard=true;
        var tid=0;
        function disableIframes(){
            document.querySelectorAll('iframe').forEach(function(f){
                f.style.pointerEvents='none';
            });
        }
        function enableIframes(){
            document.querySelectorAll('iframe').forEach(function(f){
                f.style.pointerEvents='';
            });
        }
        /* Use the Streamlit main scroll container if available */
        var sc=document.querySelector('[data-testid="stAppViewContainer"]')||window;
        sc.addEventListener('scroll',function(){
            disableIframes();
            clearTimeout(tid);
            tid=setTimeout(enableIframes,300);
        },{passive:true});
        /* Prevent pull-to-refresh at scroll-top on iOS Safari */
        var lastY=0;
        document.addEventListener('touchstart',function(e){
            lastY=e.touches[0].clientY;
        },{passive:true});
        document.addEventListener('touchmove',function(e){
            var el=document.scrollingElement||document.documentElement;
            var dy=e.touches[0].clientY-lastY;
            if(el.scrollTop<=0 && dy>0){
                e.preventDefault();
            }
        },{passive:false});
    })();
    </script>""",
    unsafe_allow_html=True,
)

# ── Global Settings Popover (accessible from sidebar) ─────────
from utils.components import render_global_settings, inject_joseph_floating, render_joseph_hero_banner
with st.sidebar:
    render_global_settings()
st.session_state.setdefault("joseph_page_context", "page_analysis")
inject_joseph_floating()
render_joseph_hero_banner()

# ── Premium Status (partial gate — free users capped at 3 props) ──
from utils.auth import is_premium_user as _is_premium_user
try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
except Exception:
    _PREM_PATH = "/14_%F0%9F%92%8E_Subscription_Level"
_FREE_ANALYSIS_LIMIT = 3   # Free users can analyze up to 3 props
_user_is_premium = _is_premium_user()
if "selected_picks" not in st.session_state:
    st.session_state["selected_picks"] = []
if "injury_status_map" not in st.session_state:
    st.session_state["injury_status_map"] = load_injury_status()

st.session_state.setdefault("joseph_enabled", True)
st.session_state.setdefault("joseph_used_fragments", set())
st.session_state.setdefault("joseph_bets_logged", False)

# ── Analysis Session Persistence — Rehydrate from DB if session empty ──────
# If the user's session state has no analysis results (e.g. after inactivity
# or a page refresh), reload the most recently saved session from SQLite so
# they never have to re-run analysis just because time passed.
if not st.session_state.get("analysis_results"):
    try:
        from tracking.database import load_latest_analysis_session as _load_session
        _saved_session = _load_session()
        if _saved_session and _saved_session.get("analysis_results"):
            st.session_state["analysis_results"] = _saved_session["analysis_results"]
            if _saved_session.get("todays_games") and not st.session_state.get("todays_games"):
                st.session_state["todays_games"] = _saved_session["todays_games"]
            if _saved_session.get("selected_picks") and not st.session_state.get("selected_picks"):
                st.session_state["selected_picks"] = _saved_session["selected_picks"]
            # Record the timestamp so the UI can show when the session was saved
            st.session_state["_analysis_session_reloaded_at"] = _saved_session.get("analysis_timestamp", "")
    except Exception:
        pass  # Non-fatal — just show empty state

# ─── Auto-refresh injury data if empty or stale (>4 hours) ──
# Use a 30-minute in-session cooldown to avoid re-loading on every
# page navigation, while still updating when data is genuinely stale.
# A short-circuit flag prevents redundant stat() calls on rapid
# reruns (e.g. scroll-triggered reruns that happen seconds apart).
_INJURY_STALE_HOURS = 4
_INJURY_REFRESH_COOLDOWN_SECS = 1800  # 30 minutes

# Short-circuit: if we already checked in this page load cycle
# (i.e. within the last 60 seconds), skip the entire block.
# This prevents repeated file-stat calls during rapid reruns.
import time as _time_mod
_injury_check_ts = st.session_state.get("_injury_check_ts", 0)
_secs_since_check = _time_mod.time() - _injury_check_ts

if _secs_since_check < 60:
    _should_auto_refresh_injuries = False
elif not st.session_state["injury_status_map"]:
    _should_auto_refresh_injuries = True
    st.session_state["_injury_check_ts"] = _time_mod.time()
else:
    st.session_state["_injury_check_ts"] = _time_mod.time()
    _should_auto_refresh_injuries = False
    # Check if we already refreshed recently in this session
    _last_refresh_ts = st.session_state.get("_injury_last_refreshed_at")
    if _last_refresh_ts is not None:
        _mins_since = (_time_mod.time() - _last_refresh_ts) / 60
        if _mins_since < 30:
            _should_auto_refresh_injuries = False
        else:
            # Been 30+ minutes since last refresh — re-check file age
            try:
                import datetime as _dt
                from pathlib import Path as _Path
                _inj_json_path = _Path(__file__).parent.parent / "data" / "injury_status.json"
                if _inj_json_path.exists():
                    _inj_age_hours = (
                        _dt.datetime.now().timestamp() - _inj_json_path.stat().st_mtime
                    ) / 3600.0
                    _should_auto_refresh_injuries = _inj_age_hours > _INJURY_STALE_HOURS
            except Exception:
                pass
    else:
        # No record of a refresh this session — check file age
        try:
            import datetime as _dt
            from pathlib import Path as _Path
            _inj_json_path = _Path(__file__).parent.parent / "data" / "injury_status.json"
            if _inj_json_path.exists():
                _inj_age_hours = (
                    _dt.datetime.now().timestamp() - _inj_json_path.stat().st_mtime
                ) / 3600.0
                _should_auto_refresh_injuries = _inj_age_hours > _INJURY_STALE_HOURS
        except Exception:
            pass  # Staleness check is best-effort

if _should_auto_refresh_injuries:
    try:
        import time as _time_mod
        from data.roster_engine import RosterEngine as _RosterEngine
        _re = _RosterEngine()
        _re.refresh()
        _scraped_inj = _re.get_injury_report()
        if _scraped_inj:
            _auto_status_map = {
                _k: {
                    "status":        _v.get("status", "Active"),
                    "injury_note":   _v.get("injury", ""),
                    "games_missed":  0,
                    "return_date":   _v.get("return_date", ""),
                    "last_game_date": "",
                    "gp_ratio":      1.0,
                    "injury":        _v.get("injury", ""),
                    "source":        _v.get("source", ""),
                    "comment":       _v.get("comment", ""),
                }
                for _k, _v in _scraped_inj.items()
            }
            st.session_state["injury_status_map"] = _auto_status_map
        # Record this refresh so subsequent page navigations skip it
        st.session_state["_injury_last_refreshed_at"] = _time_mod.time()
    except Exception:
        pass  # Non-fatal — analysis page works without auto-refresh

# ============================================================
# END SECTION: Page Setup
# ============================================================


# ============================================================
# SECTION: Helper Functions (extracted to pages/helpers/neural_analysis_helpers.py)
# ============================================================
from pages.helpers.neural_analysis_helpers import (
    find_game_context_for_player,
    _build_result_metrics,
    _build_bonus_factors,
    _build_entry_strategy,
    _render_qds_full_breakdown_html,
    render_inline_breakdown_html as _render_inline_breakdown,
    display_prop_analysis_card_qds,
)
from pages.helpers.quantum_analysis_helpers import (
    JOSEPH_DESK_SIZE_CSS as _JOSEPH_DESK_SIZE_CSS,
    render_dfs_flex_edge_html as _render_dfs_flex_edge_html,
    render_tier_distribution_html as _render_tier_distribution_html,
    render_news_alert_html as _render_news_alert_html,
    render_market_movement_html as _render_market_movement_html,
    render_uncertain_header_html as _render_uncertain_header_html,
    render_uncertain_pick_html as _render_uncertain_pick_html,
    render_gold_tier_banner_html as _render_gold_tier_banner_html,
    render_best_single_bets_header_html as _render_best_single_bets_header_html,
    render_parlays_header_html as _render_parlays_header_html,
    render_parlay_card_html as _render_parlay_card_html,
    render_game_matchup_card_html as _render_game_matchup_card_html,
    IMPACT_COLORS as _IMP_COLORS,
    CATEGORY_EMOJI as _CAT_EMOJI,
)
# ============================================================
# END SECTION: Helper Functions
# ============================================================

# ============================================================
# SECTION: Load All Required Data
# ============================================================

players_data           = load_players_data()
teams_data             = load_teams_data()
defensive_ratings_data = load_defensive_ratings_data()

current_props  = load_props_from_session(st.session_state)
todays_games   = st.session_state.get("todays_games", [])

# ── Safety net: enrich with alt-line categories if missing ──────
# Props saved before the enrichment pipeline was wired may lack
# line_category.  Re-enrich to stamp all props as "standard".
if current_props and not any(p.get("line_category") for p in current_props):
    try:
        from data.sportsbook_service import parse_alt_lines_from_platform_props
        current_props = parse_alt_lines_from_platform_props(current_props)
    except ImportError:
        _logger.warning("parse_alt_lines_from_platform_props unavailable — line categories may be missing")
simulation_depth = st.session_state.get("simulation_depth", 2000)
minimum_edge     = st.session_state.get("minimum_edge_threshold", 5.0)

# ============================================================
# END SECTION: Load All Required Data
# ============================================================

# ============================================================
# SECTION: QDS Page Header
# ============================================================

st.markdown(
    '<h2 style="font-family:\'Orbitron\',sans-serif;color:#00ffd5;'
    'margin-bottom:4px;">⚡ Neural Analysis</h2>'
    '<p style="color:#a0b4d0;margin-top:0;">SmartBetPro Quantum Matrix Engine 5.6 — Powered by N.A.N. (Neural Analysis Network) — '
    'Quantum Matrix Engine 5.6 Prop Analysis with Quantum Design System</p>',
    unsafe_allow_html=True,
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Neural Analysis — Understanding Your Results
    
    **Running Analysis:**
    1. Ensure props are loaded (from Prop Scanner or Live Games page)
    2. Click "▶️ Run Analysis" to start Quantum Matrix Engine 5.6 simulation
    3. Each prop is simulated 1,000+ times to calculate probability
    
    **Reading Results:**
    - **Probability**: % chance the stat goes MORE than the line (>55% = meaningful edge)
    - **Edge**: How much better than 50/50 your edge is (higher = better value)
    - **Confidence Score**: 0-100 composite score (70+ = high confidence)
    - **Tier**: Platinum (85+) > Gold (70+) > Silver (55+) > Bronze
    
    **Directional Forces:**
    - Green arrows = factors pushing MORE (weak defense, fast pace, etc.)
    - Red arrows = factors pushing LESS (tough defense, injury risk, etc.)
    
    **Ensemble Model 🧬:**
    - When game logs are available, the 3-model ensemble is used (season avg + recent form + matchup history)
    - `🧬 Ensemble` badge on result cards means blended projection was used
    - Model disagreement reduces confidence automatically
    
    💡 **Pro Tips:**
    - Focus on Platinum and Gold tier picks for best results
    - Avoid picks with ⚠️ "should avoid" flags
    - Select picks to send to Entry Builder for parlay optimization
    - Run **Smart Update** on the Smart NBA Data page before each session for freshest data
    """)

# ── Data Freshness Banner ─────────────────────────────────────
# Show a warning if players.csv is stale (>24 hours old).
# Stale data is the #1 source of inaccurate projections.
try:
    import os as _os_check
    _players_csv = _os_check.path.join(
        _os_check.path.dirname(_os_check.path.dirname(__file__)), "data", "players.csv"
    )
    if _os_check.path.exists(_players_csv):
        _players_age_h = (
            datetime.datetime.now().timestamp()
            - _os_check.path.getmtime(_players_csv)
        ) / 3600.0
        if _players_age_h > 48:
            st.error(
                f"🚨 **Player data is {_players_age_h:.0f}h old!** "
                "Go to **📡 Smart NBA Data** → Smart Update to refresh. "
                "Stale data severely reduces projection accuracy."
            )
        elif _players_age_h > 24:
            st.warning(
                f"⚠️ **Player data is {_players_age_h:.0f}h old.** "
                "Consider running a **Smart Update** on the Smart NBA Data page for the most accurate projections."
            )
        elif _players_age_h < 2:
            st.success(
                f"✅ Player data is fresh ({_players_age_h*60:.0f} minutes old). "
                "Projections are using current stats."
            )
except Exception:
    pass  # Non-critical check

# ── Matchup header (shown when games are configured) ──────────
if len(todays_games) == 1:
    g = todays_games[0]
    st.markdown(
        get_qds_matchup_header_html(
            away_team=g.get("away_team", "AWAY"),
            home_team=g.get("home_team", "HOME"),
            game_info=(
                f"Tonight · Tip-off: {g.get('game_time', '')}"
                if g.get("game_time") else "Tonight"
            ),
        ),
        unsafe_allow_html=True,
    )
elif len(todays_games) > 1:
    # Multiple games — show count instead of a single matchup header
    st.markdown(
        f'<div style="background:rgba(0,255,213,0.06);border-radius:8px;'
        f'padding:10px 16px;border:1px solid rgba(0,255,213,0.12);'
        f'color:#a0b4d0;font-size:0.85rem;margin-bottom:12px;">'
        f'🏀 {len(todays_games)} games configured for tonight.'
        f'</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# END SECTION: QDS Page Header
# ============================================================

# ============================================================
# SECTION: Pre-Run Status Check
# ============================================================

status_col, settings_col = st.columns([2, 1])

with status_col:
    if current_props:
        # Show per-platform breakdown of loaded props
        _prerun_plat_counts: dict = {}
        for _pp in current_props:
            _plat = _pp.get("platform", "Unknown")
            _prerun_plat_counts[_plat] = _prerun_plat_counts.get(_plat, 0) + 1
        _plat_detail = " · ".join(
            f"**{_pl}**: {_n}" for _pl, _n in sorted(_prerun_plat_counts.items())
        )
        st.info(
            f"📋 **{len(current_props)} props** loaded and ready for analysis — {_plat_detail}."
        )
    else:
        st.warning(
            "⚠️ No props loaded. Go to **🔬 Prop Scanner** → "
            "**🤖 Auto-Generate Props for Tonight's Games** or import props manually."
        )

    if todays_games:
        st.success(f"🏟️ **{len(todays_games)} game(s)** configured for tonight.")
    else:
        st.warning(
            "⚠️ No games loaded for today. Click **🔄 Auto-Load Tonight's Games** "
            "on the Live Games page first to ensure only tonight's players are analyzed."
        )

    if current_props and players_data:
        validation     = validate_props_against_roster(current_props, players_data)
        total          = validation["total"]
        matched_count  = validation["matched_count"]

        if validation["unmatched"] or validation["fuzzy_matched"]:
            with st.expander(
                f"⚠️ Roster Health: {matched_count}/{total} players matched "
                f"({int(matched_count / max(total, 1) * 100)}%) — click to see details"
            ):
                st.markdown(
                    get_roster_health_html(
                        validation["matched"],
                        validation["fuzzy_matched"],
                        validation["unmatched"],
                    ),
                    unsafe_allow_html=True,
                )
        else:
            st.success(f"✅ All {total} players matched in database.")

with settings_col:
    st.caption(f"⚙️ Simulations: **{simulation_depth:,}**")
    st.caption(f"⚙️ Min Edge: **{minimum_edge}%**")
    _shown_platforms = st.session_state.get("selected_platforms", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"])
    st.caption(f"⚙️ Platforms: **{', '.join(_shown_platforms)}**")
    st.caption("Change on the ⚙️ Settings page")

# ============================================================
# END SECTION: Pre-Run Status Check
# ============================================================

st.divider()

# ── Framework Logic (collapsible) ──────────────────────────────
with st.expander("📖 How Neural Analysis Works — Framework Logic"):
    st.markdown(get_qds_framework_logic_html(), unsafe_allow_html=True)

# ============================================================
# SECTION: Prop Pool (all available props passed to engine)
# ============================================================

# All available props are sent to the engine — no stat-type filtering or
# intake cap.  The analysis loop will process every prop until all are
# exhausted, outputting as many high-confidence bets as possible.

# ── Change 9: Smart Prop De-duplication Before Analysis ──────
# If a user loads props from multiple sources (Prop Scanner + Live Games),
# duplicate player/stat/line combos will be analyzed twice.  De-dup on
# (player_name, stat_type, line, platform) before sending to the engine.
_seen_keys: set = set()
_deduped_props: list = []
for _p in current_props:
    _dedup_key = (
        (_p.get("player_name") or "").strip().lower(),
        (_p.get("stat_type") or "").strip().lower(),
        round(float(_p.get("line", 0) or 0), 1),
        (_p.get("platform") or "").strip(),
    )
    if _dedup_key not in _seen_keys:
        _seen_keys.add(_dedup_key)
        _deduped_props.append(_p)
_dedup_removed = len(current_props) - len(_deduped_props)
final_props = _deduped_props

st.metric(
    label="⚡ PROPS IN POOL",
    value=f"{len(final_props):,}",
)
if _dedup_removed > 0:
    st.caption(f"🔁 Removed **{_dedup_removed}** duplicate prop(s) across sources.")

# ============================================================
# END SECTION: Prop Pool
# ============================================================

# ============================================================
# SECTION: Analysis Runner
# ============================================================

# NOTE: The "Show: All picks / Top picks only" radio was moved INSIDE
# _render_results_fragment() so that interacting with it only reruns the
# fragment — NOT the entire ~3000-line page.  This is the single biggest
# fix for the "page restarts when scrolling" problem on mobile.
run_analysis = st.button(
    "🚀 Run Analysis",
    type="primary",
    disabled=(len(final_props) == 0),
    help="Analyze all loaded props with Quantum Matrix Engine 5.6",
)

# ── Feature 14: Quick Filter Chips ──────────────────────────────
# Initialise session-state keys for filter chips (persist across reruns).
for _chip_key in ("chip_platinum", "chip_gold_plus", "chip_high_edge",
                  "chip_hot_form", "chip_hide_avoids"):
    if _chip_key not in st.session_state:
        st.session_state[_chip_key] = False

# ── Feature 15: Sort selector ───────────────────────────────────
if "qam_sort_key" not in st.session_state:
    st.session_state["qam_sort_key"] = "Confidence Score ↓"

# Default for the show-all/top radio (rendered inside the results fragment).
st.session_state.setdefault("qam_show_mode", "All picks")

if run_analysis:
    # Set a flag so that if the user navigates away during analysis
    # and comes back, the page knows to offer a re-run.
    st.session_state["_qam_analysis_requested"] = True
    _analysis_start_time = time.time()
    # ── Joseph Loading Screen — NBA fun facts while analysis runs ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _joseph_loader = joseph_loading_placeholder("Running Quantum Matrix Analysis")
    except Exception:
        _joseph_loader = None
    progress_bar         = st.progress(0, text="Starting analysis...")

    # ── Show Joseph's animated loading screen with NBA fun facts ──
    try:
        from utils.joseph_loading import joseph_loading_placeholder
        _joseph_loading = joseph_loading_placeholder("🔬 Analyzing props — hang tight…")
    except Exception:
        _joseph_loading = None

    analysis_results_list = []

    # Clear stale Joseph results so fresh ones are generated after this run.
    st.session_state.pop("joseph_results", None)
    st.session_state["joseph_bets_logged"] = False

    try:
        # ── Filter props to only tonight's teams (with abbreviation aliases) ──
        # Build expanded playing-teams set that covers all known alias variants
        # (e.g. "GS" ↔ "GSW", "NY" ↔ "NYK") so team-abbreviation mismatches
        # don't silently drop valid props.
        ABBREV_ALIASES = {
            "GS": "GSW", "GSW": "GS",
            "NY": "NYK", "NYK": "NY",
            "NO": "NOP", "NOP": "NO",
            "SA": "SAS", "SAS": "SA",
            "UTAH": "UTA", "UTA": "UTAH",
            "WSH": "WAS", "WAS": "WSH",
            "BKN": "BRK", "BRK": "BKN",
            "PHX": "PHO", "PHO": "PHX",
            "CHA": "CHO", "CHO": "CHA",
            "NJ": "BKN",
        }

        # Full team name → abbreviation mapping for platform props that use
        # full names or nicknames instead of standard 3-letter codes.
        try:
            from data.nba_data_service import TEAM_NAME_TO_ABBREVIATION as _TEAM_FULL_MAP
        except ImportError:
            _TEAM_FULL_MAP = {}

        # Build reverse lookups: nickname → abbrev
        _TEAM_NICKNAME_MAP: dict = {}   # e.g. "LAKERS" → "LAL"
        for _full_name, _abbr in _TEAM_FULL_MAP.items():
            parts = _full_name.rsplit(" ", 1)
            if len(parts) == 2:
                _TEAM_NICKNAME_MAP[parts[1].upper()] = _abbr
            _TEAM_NICKNAME_MAP[_full_name.upper()] = _abbr

        def _normalize_team_to_abbrev(raw_team: str) -> str:
            """Convert any team representation to a standard abbreviation.

            Handles: 3-letter codes, full names, nicknames, common aliases.
            Returns the uppercased team string unchanged if no mapping found.
            """
            team_upper = raw_team.upper().strip()
            if not team_upper:
                return ""
            # Already a known abbreviation or alias?
            if len(team_upper) <= 4:
                return ABBREV_ALIASES.get(team_upper, team_upper)
            # Full name or nickname match? (e.g. "Los Angeles Lakers", "Lakers")
            mapped = _TEAM_NICKNAME_MAP.get(team_upper)
            if mapped:
                return mapped
            # Last word might be nickname (e.g. "LA Lakers" → "Lakers")
            last_word = team_upper.rsplit(" ", 1)[-1] if " " in team_upper else ""
            if last_word:
                mapped = _TEAM_NICKNAME_MAP.get(last_word)
                if mapped:
                    return mapped
            return team_upper

        playing_teams_expanded: set = set()
        for _g in todays_games:
            for _abbrev in (
                _g.get("home_team", "").upper().strip(),
                _g.get("away_team", "").upper().strip(),
            ):
                if not _abbrev:
                    continue
                playing_teams_expanded.add(_abbrev)
                # Add known alias for this abbreviation (if any)
                _alias = ABBREV_ALIASES.get(_abbrev)
                if _alias:
                    playing_teams_expanded.add(_alias)
        playing_teams_expanded.discard("")

        if playing_teams_expanded:
            props_to_analyze = [
                p for p in final_props
                if (
                    _normalize_team_to_abbrev(p.get("team", "")) in playing_teams_expanded
                    or not p.get("team", "").strip()  # include props with no team set
                )
            ]
            skipped_count = len(final_props) - len(props_to_analyze)
            if skipped_count > 0:
                st.info(
                    f"ℹ️ Skipping **{skipped_count}** prop(s) for teams not playing tonight. "
                    f"Analyzing **{len(props_to_analyze)}** prop(s) for tonight's {len(todays_games)} game(s)."
                )

            # ── Fallback: if ALL props were filtered out, analyze them all ──
            # This prevents a dead-end where a team-name format mismatch
            # between platforms and the games list silently drops every prop.
            if len(props_to_analyze) == 0 and len(final_props) > 0:
                st.warning(
                    f"⚠️ All **{len(final_props)}** props were filtered out by tonight's team list. "
                    f"This usually means the team names in your props don't match the loaded games. "
                    f"**Proceeding with all {len(final_props)} props** so your analysis isn't blocked."
                )
                props_to_analyze = list(final_props)
        else:
            props_to_analyze = list(final_props)  # Fallback: no games loaded

        # ── Also skip confirmed Out/IR players via injury map ────────────
        # If injury_map_pre is empty (failed to load), do NOT filter — just proceed.
        # NOTE: "Doubtful" and "Questionable" players are NOT filtered here —
        # they pass through to full analysis with an injury_status_penalty
        # applied to the confidence score.  This matches the in-analysis
        # injury gate which only skips clearly inactive statuses.
        injury_map_pre = st.session_state.get("injury_status_map", {})
        _INACTIVE_STATUSES = frozenset({
            "Out", "Injured Reserve", "Out (No Recent Games)",
            "Suspended", "Not With Team",
            "G League - Two-Way", "G League - On Assignment", "G League",
        })
        if injury_map_pre:
            before_inj = len(props_to_analyze)
            props_to_analyze = [
                p for p in props_to_analyze
                if injury_map_pre.get(
                    p.get("player_name", "").lower().strip(), {}
                ).get("status", "Active") not in _INACTIVE_STATUSES
            ]
            inj_skipped = before_inj - len(props_to_analyze)
            if inj_skipped > 0:
                st.info(f"ℹ️ Skipping **{inj_skipped}** prop(s) for confirmed Out/IR players.")

        # ── Filter to selected platforms (from ⚙️ Settings) ──────────────
        _selected_platforms = st.session_state.get(
            "selected_platforms", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"]
        )
        if _selected_platforms:
            before_plat = len(props_to_analyze)
            props_to_analyze = [
                p for p in props_to_analyze
                if not p.get("platform", "").strip()          # include props with no platform
                or p.get("platform", "") in _selected_platforms
            ]
            plat_skipped = before_plat - len(props_to_analyze)
            if plat_skipped > 0:
                st.info(
                    f"ℹ️ Skipping **{plat_skipped}** prop(s) for platforms not in your "
                    f"selection ({', '.join(_selected_platforms)}). "
                    "Change platforms on the ⚙️ Settings page."
                )

        # ── Show per-platform prop count summary ─────────────────────────
        if props_to_analyze:
            _plat_counts = {}
            for _p in props_to_analyze:
                _plat = _p.get("platform", "Unknown")
                _plat_counts[_plat] = _plat_counts.get(_plat, 0) + 1
            _plat_summary = " · ".join(
                f"**{_plat}**: {_n}" for _plat, _n in sorted(_plat_counts.items())
            )
            st.caption(f"📊 Analyzing: {_plat_summary}")

        total_props_count    = len(props_to_analyze)
        if total_props_count == 0:
            st.warning("⚠️ No props remain after filtering to tonight's teams / injury status. Check your games and props.")
            progress_bar.empty()
            st.stop()

        # ── Analysis proceeds with all available props (no cap) ────

        # ── Change 7: Parallel data pre-fetching ────────────────────
        # Pre-fetch player bios in parallel so the main loop doesn't
        # block on I/O for each unmatched player.  Each prop's
        # simulation is independent, but the loop body accesses
        # Streamlit session state (not thread-safe), so we parallelise
        # the pure-I/O pre-fetch step instead of the whole loop.
        _prefetched_bios: dict = {}
        _names_to_prefetch = list({
            p.get("player_name", "") for p in props_to_analyze
            if p.get("player_name") and not find_player_by_name(players_data, p.get("player_name", ""))
        })
        if _names_to_prefetch:
            try:
                from data.player_profile_service import get_player_bio as _get_bio
                _max_workers = min(_MAX_BIO_PREFETCH_WORKERS, len(_names_to_prefetch))
                with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as _pool:
                    _bio_futures = {
                        _pool.submit(_get_bio, name): name
                        for name in _names_to_prefetch
                    }
                    for _fut in concurrent.futures.as_completed(_bio_futures):
                        _fname = _bio_futures[_fut]
                        try:
                            _prefetched_bios[_fname] = _fut.result()
                        except Exception:
                            pass
            except ImportError:
                pass  # player_profile_service not available

        # ── Change 10: Initialize simulation result cache ─────────────
        _sim_cache = _get_sim_cache()
        _cache_hits = 0

        for prop_index, prop in enumerate(props_to_analyze):
            progress_fraction = (prop_index + 1) / total_props_count
            progress_bar.progress(
                progress_fraction,
                text=f"Analyzing {prop.get('player_name', 'Player')}… ({prop_index + 1}/{total_props_count})"
            )

            # ── Change 10: Check cache for unchanged props ────────────
            _cache_k = _prop_cache_key(
                prop.get("player_name", ""),
                prop.get("stat_type", ""),
                float(prop.get("line", 0) or 0),
                simulation_depth,
            )
            _cached_result = _sim_cache.get(_cache_k)
            if _cached_result is not None:
                analysis_results_list.append(_cached_result)
                _cache_hits += 1
                continue

            try:
                player_name = prop.get("player_name", "")
                stat_type   = prop.get("stat_type", "points").lower()
                prop_line   = float(prop.get("line", 0))
                platform    = prop.get("platform", "DraftKings")

                # Phase 2: Use quarantined main line when available
                _raw_target = prop.get("prop_target_line")
                prop_target_line = None
                if _raw_target is not None:
                    try:
                        _ptl = float(_raw_target)
                        if _ptl > 0:
                            prop_target_line = _ptl
                    except (ValueError, TypeError):
                        pass

                # ── Injury gate ───────────────────────────────────────────
                injury_map        = st.session_state.get("injury_status_map", {})
                player_status_info = get_player_status(player_name, injury_map)
                player_status      = player_status_info.get("status", "Active")

                if player_status in (
                    "Out", "Injured Reserve", "Out (No Recent Games)",
                    "Suspended", "Not With Team",
                    "G League - Two-Way", "G League - On Assignment", "G League",
                ):
                    injury_note = player_status_info.get("injury_note", "Player is not active")
                    analysis_results_list.append({
                        "player_name":   player_name,
                        "team":          prop.get("team", ""),
                        "player_team":   prop.get("team", ""),
                        "player_position": "",
                        "stat_type":     stat_type,
                        "line":          prop_line,
                        "platform":      platform,
                        "season_pts_avg": 0, "season_reb_avg": 0, "season_ast_avg": 0,
                        "points_avg": 0, "rebounds_avg": 0, "assists_avg": 0,
                        "opponent":      "",
                        "is_home":       None,
                        "probability_over": 0.0, "probability_under": 1.0,
                        "simulated_mean": 0.0, "simulated_std": 0.0,
                        "percentile_10": 0.0, "percentile_50": 0.0, "percentile_90": 0.0,
                        "adjusted_projection": 0.0, "overall_adjustment": 1.0,
                        "recent_form_ratio": None, "games_played": None,
                        "edge_percentage": -50.0, "confidence_score": 0,
                        "tier": "Bronze", "tier_emoji": "🥉",
                        "direction": "UNDER",
                        "recommendation": f"SKIP — {player_name} is {player_status}",
                        "forces": {"over_forces": [], "under_forces": []},
                        "should_avoid": True,
                        "avoid_reasons": [f"Player is {player_status}: {injury_note}"],
                        "histogram": [], "score_breakdown": {},
                        "line_vs_avg_pct": 0, "recent_form_results": [],
                        "player_matched": False, "explanation": None,
                        "line_sharpness_force": None, "line_sharpness_penalty": 0.0,
                        "trap_line_result": {}, "trap_line_penalty": 0.0,
                        "teammate_out_notes": [], "minutes_adjustment_factor": 1.0,
                        "player_is_out": True,
                        "player_status": player_status,
                        "player_status_note": injury_note,
                        "player_id": "",
                    })
                    continue

                # ── Find player in database ───────────────────────────────
                player_data    = find_player_by_name(players_data, player_name)
                player_matched = player_data is not None

                if player_data is None:
                    # Build a complete fallback using positional priors.
                    # Using only one stat's avg (the old approach) caused zero-projections for
                    # every other stat — which breaks combo stats, double_double, fantasy scores,
                    # and the directional forces analysis entirely.
                    #
                    # Strategy:
                    #  1. Resolve the player's position from the NBA bio API (or default to SF).
                    #  2. Fill all 7 stat avgs from that position's prior.
                    #  3. For the specific stat being analyzed, anchor to prop_line (the most
                    #     reliable single data point we have) by scaling the prior components
                    #     proportionally so the expected total matches the prop line.
                    #  4. Set games_played=30 (above the Bayesian threshold of 25) so shrinkage
                    #     is NOT applied — the prop_line is already our best anchor and further
                    #     shrinkage toward league priors would move estimates away from it.
                    _pos = "SF"  # default when position is unknown
                    try:
                        # Use prefetched bio when available (Change 7: parallel pre-fetch)
                        _bio = _prefetched_bios.get(player_name)
                        if _bio is None:
                            from data.player_profile_service import get_player_bio
                            _bio = get_player_bio(player_name)
                        if _bio.get("position"):
                            _bio_pos = _bio["position"].split("-")[0].strip()
                            _BIO_POS_ALIAS = {"Guard": "PG", "Forward": "SF", "Center": "C"}
                            _pos = _BIO_POS_ALIAS.get(_bio_pos, _bio_pos)
                    except Exception:
                        pass
                    _prior = POSITION_PRIORS.get(_pos, POSITION_PRIORS["SF"])
                    player_data = {
                        "name":          player_name,
                        "team":          prop.get("team", ""),
                        "position":      _pos,
                        "games_played":  30,   # above Bayesian threshold — trust prop_line anchor
                        "minutes_avg":   28.0,
                        # All seven stats seeded from position priors
                        "points_avg":    str(_prior["points"]),
                        "rebounds_avg":  str(_prior["rebounds"]),
                        "assists_avg":   str(_prior["assists"]),
                        "threes_avg":    str(_prior["threes"]),
                        "steals_avg":    str(_prior["steals"]),
                        "blocks_avg":    str(_prior["blocks"]),
                        "turnovers_avg": str(_prior["turnovers"]),
                    }

                    if stat_type in COMBO_STAT_TYPES:
                        # Scale prior components so they sum to the prop_line.
                        # e.g. PRA line=50.5, SF prior P+R+A=25.0 → scale=2.02
                        # → pts=32.3, reb=11.1, ast=7.1  (realistic split that totals 50.5)
                        _components = COMBO_STATS.get(stat_type, [])
                        _prior_sum = sum(_prior.get(s, 0.0) for s in _components)
                        if _prior_sum > 0 and prop_line > 0:
                            _scale = prop_line / _prior_sum
                            for _c in _components:
                                _est = round(_prior.get(_c, 0.0) * _scale, 1)
                                player_data[f"{_c}_avg"] = str(_est)
                                player_data[f"{_c}_std"] = str(round(max(0.5, _est * 0.35), 1))
                        else:
                            # Equal split fallback
                            _split = round(prop_line / max(len(_components), 1), 1)
                            for _c in _components:
                                player_data[f"{_c}_avg"] = str(_split)
                                player_data[f"{_c}_std"] = str(round(max(0.5, _split * 0.35), 1))

                    elif stat_type in FANTASY_STAT_TYPES:
                        # Scale all stats so the weighted fantasy total matches prop_line.
                        _formula = FANTASY_SCORING.get(stat_type, {})
                        _prior_fantasy = sum(_prior.get(s, 0.0) * w for s, w in _formula.items())
                        if _prior_fantasy > 0 and prop_line > 0:
                            _scale = prop_line / _prior_fantasy
                            for _fs in _formula:
                                _est = round(_prior.get(_fs, 0.0) * _scale, 1)
                                player_data[f"{_fs}_avg"] = str(_est)
                                player_data[f"{_fs}_std"] = str(round(max(0.5, _est * 0.35), 1))

                    elif stat_type not in {"double_double", "triple_double"}:
                        # Simple stat: prop_line is the best single-point estimate.
                        player_data[f"{stat_type}_avg"] = str(prop_line)
                        player_data[f"{stat_type}_std"] = str(round(prop_line * 0.35, 1))
                    # For double_double / triple_double, the position priors already seed
                    # all five required components — no further override needed.

                player_team  = player_data.get("team", prop.get("team", ""))
                game_context = find_game_context_for_player(player_team, todays_games)

                recent_form_games  = prop.get("recent_form_results", [])

                # ── DB fallback: fetch game logs when recent_form_games is empty ──
                if not recent_form_games:
                    try:
                        from data.etl_data_service import get_player_game_logs as _etl_get_logs
                        _pid_for_logs = player_data.get("player_id", "")
                        if _pid_for_logs:
                            recent_form_games = _etl_get_logs(int(_pid_for_logs), limit=20) or []
                    except Exception:
                        pass

                # ── Feature 6: Minutes Trend — compute using rotation_tracker ──
                # If game logs contain minutes (MIN field), detect trend vs season avg.
                _minutes_trend = None
                _minutes_trend_indicator = "➡️"  # default: stable
                if _get_track_minutes_trend() and recent_form_games:
                    try:
                        _minutes_trend = track_minutes_trend(recent_form_games, window=5)
                        _td = _minutes_trend.get("trend_direction", "stable")
                        _minutes_trend_indicator = "🔺" if _td == "up" else ("🔻" if _td == "down" else "➡️")
                    except Exception:
                        _minutes_trend = None

                # ── C4: Teammate-Out Usage Adjustment ────────────────────
                # Check if a high-usage teammate is OUT and boost this player's
                # projection accordingly (+8% primary option, +5% secondary, cap +15%).
                teammate_boost, teammate_boost_notes = calculate_teammate_out_boost(
                    player_data=player_data,
                    injury_status_map=injury_map,
                    teammates_data=players_data,
                )

                # ── Precise Minutes Projection (minutes_model.py) ─────────
                # Use the dedicated minutes model to get a more accurate minutes estimate
                # before running the full stat projection. The minutes projection
                # accounts for blowout spread, back-to-back, teammate injuries, and pace.
                _precise_minutes = None
                if _get_project_player_minutes() is not None:
                    try:
                        _teammate_status = {
                            k: v.get("status", "Active")
                            for k, v in injury_map.items()
                        } if injury_map else None
                        _min_result = project_player_minutes(
                            player_data=player_data,
                            game_context={
                                "opponent": game_context.get("opponent", ""),
                                "is_home": game_context.get("is_home", True),
                                "vegas_spread": game_context.get("vegas_spread", 0.0),
                                "game_total": game_context.get("game_total", 220.0),
                                "rest_days": game_context.get("rest_days", 2),
                                "back_to_back": game_context.get("back_to_back", False),
                                "game_id": game_context.get("game_id", ""),
                            },
                            teammate_status=_teammate_status,
                            game_logs=recent_form_games if recent_form_games else None,
                        )
                        _precise_minutes = _min_result.get("projected_minutes")
                    except Exception:
                        _precise_minutes = None

                # ── Pull per-player advanced context from Deep Fetch enrichment ──
                # After the user clicks "Deep Fetch", st.session_state["advanced_enrichment"]
                # is populated with player_metrics (estimated metrics) for all rostered players.
                # Look up the matching player by ID or name and pass usage_pct to the projection.
                _advanced_context: dict | None = None
                try:
                    _game_enr = st.session_state.get("advanced_enrichment", {}).get(
                        game_context.get("game_id", ""), {}
                    )
                    _all_metrics = _game_enr.get("player_metrics", [])
                    _player_id = player_data.get("player_id") or player_data.get("id")
                    _player_name_lower = str(player_data.get("name", "")).lower()
                    for _m in _all_metrics:
                        _mid = _m.get("PLAYER_ID") or _m.get("playerId")
                        _mname = str(_m.get("PLAYER_NAME") or _m.get("playerName") or "").lower()
                        if (_player_id and _mid and int(_player_id) == int(_mid)) or (
                            _player_name_lower and _mname and _player_name_lower in _mname
                        ):
                            # Normalise usage: API may return 0–100 or 0–1 scale
                            _usg = _m.get("E_USG_PCT") or _m.get("USG_PCT") or _m.get("usage_pct")
                            if _usg is not None:
                                try:
                                    _usg_f = float(_usg)
                                    _advanced_context = {
                                        "usage_pct": _usg_f / 100.0 if _usg_f > 1.0 else _usg_f
                                    }
                                except (TypeError, ValueError):
                                    pass
                            break
                except Exception:
                    pass

                projection_result  = build_player_projection(
                    player_data=player_data,
                    opponent_team_abbreviation=game_context.get("opponent", ""),
                    is_home_game=game_context.get("is_home", True),
                    rest_days=game_context.get("rest_days", 2),
                    game_total=game_context.get("game_total", 220.0),
                    defensive_ratings_data=defensive_ratings_data,
                    teams_data=teams_data,
                    recent_form_games=recent_form_games if recent_form_games else None,
                    vegas_spread=game_context.get("vegas_spread", 0.0),
                    minutes_adjustment_factor=teammate_boost,
                    teammate_out_notes=teammate_boost_notes,
                    advanced_context=_advanced_context,
                )

                # ── Ensemble Model Override (3-model blend) ────────────────
                # When game logs are available, run the full ensemble model (Model A:
                # season avg + context, Model B: recent form, Model C: matchup history)
                # and use the blended projection as the primary projected_stat.
                # This is more accurate than a single model approach.
                _ensemble_result = None
                _ensemble_penalty = 0.0
                if _get_ensemble_projection() is not None and stat_type not in (
                    "double_double", "triple_double"
                ):
                    try:
                        _ens_ctx = {
                            "stat_type": stat_type,
                            "opponent": game_context.get("opponent", ""),
                            "is_home": game_context.get("is_home", True),
                            "rest_factor": projection_result.get("rest_factor", 1.0),
                            "pace_factor": projection_result.get("pace_factor", 1.0),
                            "defense_factor": projection_result.get("defense_factor", 1.0),
                        }
                        _ensemble_result = get_ensemble_projection(
                            player_data=player_data,
                            game_context=_ens_ctx,
                            game_logs=recent_form_games if len(recent_form_games or []) >= 3 else None,
                        )
                        _ensemble_penalty = _ensemble_result.get("confidence_adjustment", 0.0)
                    except Exception:
                        _ensemble_result = None
                        _ensemble_penalty = 0.0

                stat_std      = get_stat_standard_deviation(player_data, stat_type)
                projected_stat = projection_result.get(
                    f"projected_{stat_type}",
                    float(player_data.get(f"{stat_type}_avg", prop_line))
                )

                # ── Apply Ensemble Projection Override ───────────────────
                # When the ensemble produced a blended projection, use it to
                # override the single-model projected_stat. The ensemble blends
                # season-avg, recent-form, and matchup-history models with
                # inverse-variance weighting — consistently more accurate.
                _ensemble_used = False
                if (_ensemble_result is not None
                        and stat_type not in ("double_double", "triple_double")
                        and stat_type not in list(COMBO_STAT_TYPES) + list(FANTASY_STAT_TYPES)):
                    _ens_proj = _ensemble_result.get("ensemble_projection", 0)
                    _ens_std  = _ensemble_result.get("ensemble_std", 0)
                    if _ens_proj and _ens_proj > 0:
                        projected_stat = _ens_proj
                        _ensemble_used = True
                        # Blend ensemble std with base std for richer variance estimate
                        if _ens_std > 0:
                            stat_std = (_ens_std + stat_std) / 2.0

                # ── C8: Minutes-Stat Correlation — pass projected_minutes to sim ─
                # ── C11: KDE from Game Logs — pass recent_game_logs to sim ──────
                # Build stat-specific game log list from recent_form_games for KDE.
                # Maps stat_type keys to the game-log column names.
                _stat_log_key_map = {
                    "points": "pts", "rebounds": "reb", "assists": "ast",
                    "threes": "fg3m", "steals": "stl", "blocks": "blk",
                    "turnovers": "tov",
                }
                _log_key = _stat_log_key_map.get(stat_type, stat_type)
                recent_game_log_values = []
                for _g in (recent_form_games or []):
                    _v = _g.get(_log_key, _g.get(stat_type))
                    if _v is not None:
                        try:
                            recent_game_log_values.append(float(_v))
                        except (TypeError, ValueError):
                            pass

                # ── Simulation dispatch: use specialist functions for combo/fantasy/yesno ──
                # Combo stats (PRA, Pts+Rebs, etc.) use correlated Cholesky simulation (C7).
                # Fantasy score stats use the platform-specific weighted-sum formula.
                # Double/triple-double props use threshold-counting simulation.
                # Simple stats fall back to the standard Quantum Matrix Engine 5.6 path.
                _sim_kwargs = dict(
                    blowout_risk_factor=projection_result.get("blowout_risk", 0.15),
                    pace_adjustment_factor=projection_result.get("pace_factor", 1.0),
                    matchup_adjustment_factor=projection_result.get("defense_factor", 1.0),
                    home_away_adjustment=projection_result.get("home_away_factor", 0.0),
                    rest_adjustment_factor=projection_result.get("rest_factor", 1.0),
                    game_context=game_context if game_context.get("game_id") else None,
                )

                if stat_type in COMBO_STAT_TYPES:
                    # Build component projections from the per-stat projection outputs
                    _combo_stat_components = COMBO_STATS.get(stat_type, [])
                    _comp_proj = {
                        s: projection_result.get(
                            f"projected_{s}",
                            float(player_data.get(f"{s}_avg", 0) or 0),
                        )
                        for s in _combo_stat_components
                    }
                    _comp_std = {
                        s: get_stat_standard_deviation(player_data, s)
                        for s in _combo_stat_components
                    }
                    simulation_output = simulate_combo_stat(
                        component_projections=_comp_proj,
                        component_std_devs=_comp_std,
                        prop_line=prop_line,
                        number_of_simulations=simulation_depth,
                        **_sim_kwargs,
                    )
                    # Update projected_stat to the adjusted combo sum for edge calc
                    projected_stat = simulation_output.get("adjusted_projection", sum(_comp_proj.values()))

                elif stat_type in FANTASY_STAT_TYPES:
                    # Use the platform's weighted-sum fantasy formula
                    _formula = FANTASY_SCORING.get(stat_type, {})
                    _stat_proj = {
                        s: projection_result.get(
                            f"projected_{s}",
                            float(player_data.get(f"{s}_avg", 0) or 0),
                        )
                        for s in _formula
                    }
                    _stat_std = {
                        s: get_stat_standard_deviation(player_data, s)
                        for s in _formula
                    }
                    simulation_output = simulate_fantasy_score(
                        stat_projections=_stat_proj,
                        stat_std_devs=_stat_std,
                        fantasy_formula=_formula,
                        prop_line=prop_line,
                        number_of_simulations=simulation_depth,
                        **_sim_kwargs,
                    )
                    projected_stat = simulation_output.get("adjusted_projection", projected_stat)

                elif stat_type == "double_double":
                    _dd_stats = ["points", "rebounds", "assists", "blocks", "steals"]
                    _dd_proj = {
                        s: projection_result.get(
                            f"projected_{s}",
                            float(player_data.get(f"{s}_avg", 0) or 0),
                        )
                        for s in _dd_stats
                    }
                    _dd_std = {s: get_stat_standard_deviation(player_data, s) for s in _dd_stats}
                    simulation_output = simulate_double_double(
                        stat_projections=_dd_proj,
                        stat_std_devs=_dd_std,
                        number_of_simulations=simulation_depth,
                        **_sim_kwargs,
                    )

                elif stat_type == "triple_double":
                    _td_stats = ["points", "rebounds", "assists"]
                    _td_proj = {
                        s: projection_result.get(
                            f"projected_{s}",
                            float(player_data.get(f"{s}_avg", 0) or 0),
                        )
                        for s in _td_stats
                    }
                    _td_std = {s: get_stat_standard_deviation(player_data, s) for s in _td_stats}
                    simulation_output = simulate_triple_double(
                        stat_projections=_td_proj,
                        stat_std_devs=_td_std,
                        number_of_simulations=simulation_depth,
                        **_sim_kwargs,
                    )

                else:
                    # Simple stat: standard Quantum Matrix Engine 5.6 simulation (C5 skew-normal, C8 minutes, C11 KDE)
                    _flat_sim_minutes = _precise_minutes or projection_result.get("projected_minutes")
                    simulation_output = run_quantum_matrix_simulation(
                        projected_stat_average=projected_stat,
                        stat_standard_deviation=stat_std,
                        prop_line=prop_line,
                        number_of_simulations=simulation_depth,
                        stat_type=stat_type,
                        projected_minutes=_flat_sim_minutes,
                        minutes_std=4.0,
                        recent_game_logs=recent_game_log_values if len(recent_game_log_values) >= 15 else None,
                        prop_target_line=prop_target_line,
                        platform=platform,
                        **_sim_kwargs,
                    )

                    # ── Game Script Blend (30% game-script + 70% flat) ────
                    # For simple stats, blend in the game-script simulation to
                    # capture within-game dynamics (blowout minutes cuts, close
                    # game OT boosts) that the flat model misses.
                    # IMPORTANT: We update the simulated_mean/std but keep all
                    # other keys (probability_over, percentiles, etc.) from the
                    # flat simulation since blend_with_flat_simulation only
                    # provides mean/std — no probability recalculation.
                    _gs_sim, _gs_blend = _get_game_script_fns()
                    if _gs_sim is not None:
                        try:
                            _gs_proj_dict = {
                                "projected_stat":    projected_stat,
                                "projected_minutes": _flat_sim_minutes or 32.0,
                                "stat_std":          stat_std,
                            }
                            _gs_ctx = {
                                "vegas_spread": game_context.get("vegas_spread", 0.0),
                                "game_total":   game_context.get("game_total", 220.0),
                                "is_home":      game_context.get("is_home", True),
                                "stat_type":    stat_type,
                            }
                            _gs_result = simulate_game_script(
                                player_projection=_gs_proj_dict,
                                game_context=_gs_ctx,
                                num_simulations=min(500, simulation_depth),
                            )
                            # game_script returns 'simulated_values' not 'simulated_results'
                            if _gs_result and _gs_result.get("simulated_values"):
                                # blend_with_flat_simulation expects 'mean'/'std' keys,
                                # but simulation.py returns 'simulated_mean'/'simulated_std'.
                                # Build a normalized flat dict for the blend function.
                                _flat_for_blend = {
                                    "mean": simulation_output.get(
                                        "simulated_mean",
                                        simulation_output.get("mean", 0.0)
                                    ),
                                    "std": simulation_output.get(
                                        "simulated_std",
                                        simulation_output.get("std", 0.0)
                                    ),
                                }
                                _blended = blend_with_flat_simulation(
                                    game_script_results=_gs_result,
                                    flat_simulation_results=_flat_for_blend,
                                )
                                if _blended and _blended.get("blended_mean", 0) > 0:
                                    # Merge blended mean/std back into simulation_output
                                    # without overwriting probability keys
                                    simulation_output = dict(simulation_output)
                                    simulation_output["simulated_mean"] = _blended["blended_mean"]
                                    simulation_output["simulated_std"]  = _blended["blended_std"]
                                    simulation_output["game_script_applied"] = True
                        except Exception:
                            pass  # Game script is additive — never block main flow

                forces_result = analyze_directional_forces(
                    player_data=player_data,
                    prop_line=prop_line,
                    stat_type=stat_type,
                    projection_result=projection_result,
                    game_context=game_context,
                )

                season_avg_for_stat  = float(player_data.get(f"{stat_type}_avg", 0) or 0)
                line_sharpness_force = detect_line_sharpness(
                    prop_line=prop_line,
                    season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
                    stat_type=stat_type,
                )
                line_sharpness_penalty = 0.0
                if line_sharpness_force is not None:
                    line_sharpness_penalty = min(8.0, line_sharpness_force.get("strength", 0) * 2.5)

                trap_line_result = detect_trap_line(
                    prop_line=prop_line,
                    season_average=season_avg_for_stat if season_avg_for_stat > 0 else None,
                    defense_factor=projection_result.get("defense_factor", 1.0),
                    rest_factor=projection_result.get("rest_factor", 1.0),
                    game_total=game_context.get("game_total", 220.0),
                    blowout_risk=projection_result.get("blowout_risk", 0.15),
                    stat_type=stat_type,
                )
                trap_line_penalty = trap_line_result.get("confidence_penalty", 0.0)

                probability_over  = simulation_output.get("probability_over", 0.5)

                # Use actual odds from the prop when available so the edge reflects the
                # true implied probability for this platform/line, not a fixed -110 default.
                # No-vig platform list cleared — all platforms now use actual odds.
                _prop_over_odds  = prop.get("over_odds", -110)
                _prop_under_odds = prop.get("under_odds", -110)
                _platform_for_odds = prop.get("platform", "")
                # Platforms without per-leg vig: treat as standard -110 breakeven
                _NO_VIG_PLATFORMS = set()  # Legacy no-vig platforms removed
                if _platform_for_odds in _NO_VIG_PLATFORMS:
                    # No vig — use the standard -110 breakeven (0.5238)
                    _implied_prob_for_edge = None  # let calculate_edge_percentage use default
                else:
                    # DraftKings and other sportsbooks: use actual over odds for the implied prob
                    _implied_prob_for_edge = _odds_to_implied_prob(_prop_over_odds)

                edge_pct = calculate_edge_percentage(probability_over, _implied_prob_for_edge)

                # C10: Historical calibration — adjust confidence score based on
                # how well-calibrated the model has been historically at this
                # probability level.  Returns 0.0 on cold start (no history yet).
                calibration_adj = get_calibration_adjustment(probability_over)

                # ── Fetch real matchup data for SAFE Score enrichment ─────────
                # on_off_data: player's team On/Off net-rating differentials
                # matchup_data: per-matchup defensive assignments from box score
                # Both are optional — confidence scoring degrades gracefully.
                # Skip live API calls for synthetic/future game IDs.
                _on_off_data: dict | None = None
                _matchup_data: dict | None = None
                _game_id_ctx = game_context.get("game_id", "")
                _is_synthetic_game = game_context.get("is_synthetic", False) or "_vs_" in _game_id_ctx
                try:
                    from data.nba_data_service import get_player_on_off, get_box_score_matchups
                    _player_team_id = game_context.get("home_team_id") if game_context.get("is_home") else game_context.get("away_team_id")
                    if _player_team_id and not _is_synthetic_game:
                        _on_off_data = get_player_on_off(_player_team_id) or None
                    if _game_id_ctx and not _is_synthetic_game:
                        _matchup_data = get_box_score_matchups(_game_id_ctx) or None
                except Exception:
                    pass

                # ── DB fallback for on/off and matchup data ───────────────
                if _on_off_data is None or _matchup_data is None:
                    try:
                        from data.etl_data_service import get_player_game_logs as _etl_logs_for_matchup
                        _pid_matchup = player_data.get("player_id", "")
                        if _pid_matchup and _on_off_data is None:
                            _db_logs = _etl_logs_for_matchup(int(_pid_matchup), limit=10)
                            if _db_logs:
                                _on_off_data = {"source": "db_game_logs", "games": len(_db_logs)}
                    except Exception:
                        pass

                # ── Compute injury status penalty for Doubtful/Questionable ─
                _injury_penalty = 0.0
                if player_status == "Doubtful":
                    _injury_penalty = _DOUBTFUL_INJURY_PENALTY
                elif player_status in ("Questionable", "GTD"):
                    _injury_penalty = _QUESTIONABLE_INJURY_PENALTY

                confidence_output = calculate_confidence_score(
                    probability_over=probability_over,
                    edge_percentage=edge_pct,
                    directional_forces=forces_result,
                    defense_factor=projection_result.get("defense_factor", 1.0),
                    stat_standard_deviation=stat_std,
                    stat_average=season_avg_for_stat,
                    simulation_results=simulation_output,
                    games_played=int(player_data.get("games_played", 0) or 0) or None,
                    recent_form_ratio=projection_result.get("recent_form_ratio"),
                    line_sharpness_penalty=line_sharpness_penalty,
                    trap_line_penalty=trap_line_penalty,
                    calibration_adjustment=calibration_adj,  # C10
                    injury_status_penalty=_injury_penalty,
                    on_off_data=_on_off_data,
                    matchup_data=_matchup_data,
                )

                # ── Apply ensemble model-disagreement penalty to confidence ─
                if _ensemble_penalty > 0:
                    _cur_conf = confidence_output.get("confidence_score", 50)
                    confidence_output["confidence_score"] = max(0.0, _cur_conf - _ensemble_penalty)

                # C12: Closing Line Value — record the model's opening projection and
                # recommendation at analysis time.  Callers can later call
                # engine.clv_tracker.update_closing_line() with the final closing line
                # to compute CLV and validate the model's edge.
                try:
                    store_opening_line(
                        player_name=player_name,
                        stat_type=stat_type,
                        opening_line=prop_line,
                        model_projection=projected_stat,
                        model_direction=confidence_output.get("direction", "OVER"),
                        confidence_score=confidence_output.get("confidence_score", 0.0),
                        tier=confidence_output.get("tier", "Bronze"),
                        edge_percentage=edge_pct,
                    )
                except Exception:
                    pass  # CLV recording is non-critical; never block analysis

                # F9: Store initial line snapshot for market movement tracking
                try:
                    _snap_key = f"{player_name}_{stat_type}"
                    if "line_snapshots" not in st.session_state:
                        st.session_state["line_snapshots"] = {}
                    if _snap_key not in st.session_state["line_snapshots"]:
                        st.session_state["line_snapshots"][_snap_key] = {
                            "initial_line": prop_line,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                except Exception:
                    pass

                should_avoid_flag, avoid_reasons = should_avoid_prop(
                    probability_over=probability_over,
                    directional_forces_result=forces_result,
                    edge_percentage=edge_pct,
                    stat_standard_deviation=stat_std,
                    stat_average=float(player_data.get(f"{stat_type}_avg", prop_line)),
                    stat_type=stat_type,
                    platform=prop.get("platform", ""),
                    over_odds=prop.get("over_odds", -110),
                )

                # Merge kill-switch flags from confidence engine (C2/C3) with
                # should_avoid_prop() results so all sources are surfaced in the UI.
                if confidence_output.get("should_avoid"):
                    should_avoid_flag = True
                for extra_reason in confidence_output.get("avoid_reasons", []):
                    if extra_reason and extra_reason not in avoid_reasons:
                        avoid_reasons.append(extra_reason)

                histogram_data = build_histogram_from_results(
                    simulation_output.get("simulated_results", []),
                    prop_line,
                    number_of_buckets=15,
                )

                explanation = generate_pick_explanation(
                    player_data=player_data,
                    prop_line=prop_line,
                    stat_type=stat_type,
                    direction=confidence_output.get("direction", "OVER"),
                    projection_result=projection_result,
                    simulation_results=simulation_output,
                    forces=forces_result,
                    confidence_result=confidence_output,
                    game_context=game_context,
                    platform=platform,
                    recent_form_games=prop.get("recent_form_results", []),
                    should_avoid=should_avoid_flag,
                    avoid_reasons=avoid_reasons,
                    trap_line_result=trap_line_result,
                    line_sharpness_info=line_sharpness_force,
                    teammate_out_notes=projection_result.get("teammate_out_notes", []),
                )

                full_result = {
                    "player_name":      player_name,
                    "team":             player_team,
                    "player_team":      player_team,
                    "player_position":  player_data.get("position", ""),
                    "stat_type":        stat_type,
                    "line":             prop_line,
                    "platform":         platform,
                    "player_id":        player_data.get("player_id", ""),
                    "season_pts_avg":   float(player_data.get("points_avg",   0) or 0),
                    "season_reb_avg":   float(player_data.get("rebounds_avg", 0) or 0),
                    "season_ast_avg":   float(player_data.get("assists_avg",  0) or 0),
                    "points_avg":       float(player_data.get("points_avg",   0) or 0),
                    "rebounds_avg":     float(player_data.get("rebounds_avg", 0) or 0),
                    "assists_avg":      float(player_data.get("assists_avg",  0) or 0),
                    "opponent":         game_context.get("opponent", ""),
                    "is_home":          game_context.get("is_home"),
                    "probability_over": round(probability_over, 4),
                    "probability_under":round(1.0 - probability_over, 4),
                    "simulated_mean":   round(simulation_output.get("simulated_mean", 0), 1),
                    "simulated_std":    round(simulation_output.get("simulated_std",  0), 1),
                    "percentile_10":    round(simulation_output.get("percentile_10",  0), 1),
                    "percentile_50":    round(simulation_output.get("percentile_50",  0), 1),
                    "percentile_90":    round(simulation_output.get("percentile_90",  0), 1),
                    "adjusted_projection": round(projected_stat, 1),
                    "overall_adjustment":  round(projection_result.get("overall_adjustment", 1.0), 3),
                    "recent_form_ratio":   projection_result.get("recent_form_ratio"),
                    "games_played":        int(player_data.get("games_played", 0) or 0) or None,
                    "edge_percentage":     round(edge_pct, 1),
                    "confidence_score":    confidence_output.get("confidence_score", 50),
                    "tier":                confidence_output.get("tier", "Bronze"),
                    "tier_emoji":          confidence_output.get("tier_emoji", "🥉"),
                    "direction":           confidence_output.get("direction", "OVER"),
                    "recommendation":      confidence_output.get("recommendation", ""),
                    "forces":              forces_result,
                    "should_avoid":        should_avoid_flag,
                    "avoid_reasons":       avoid_reasons,
                    "histogram":           histogram_data,
                    "score_breakdown":     confidence_output.get("score_breakdown", {}),
                    "line_vs_avg_pct":     prop.get("line_vs_avg_pct", 0),
                    "recent_form_results": prop.get("recent_form_results", []),
                    "player_matched":      player_matched,
                    "explanation":         explanation,
                    "line_sharpness_force":   line_sharpness_force,
                    "line_sharpness_penalty": round(line_sharpness_penalty, 1),
                    "trap_line_result":       trap_line_result,
                    "trap_line_penalty":      round(trap_line_penalty, 1),
                    "teammate_out_notes":     projection_result.get("teammate_out_notes", []),
                    "minutes_adjustment_factor": round(projection_result.get("minutes_adjustment_factor", 1.0), 4),
                    "minutes_trend":           _minutes_trend,
                    "minutes_trend_indicator": _minutes_trend_indicator,
                    "projected_minutes":       round(_precise_minutes, 1) if _precise_minutes else None,
                    "player_is_out":    False,
                    "player_status":    player_status,
                    "player_status_note": player_status_info.get("injury_note", ""),
                    # Ensemble model metadata
                    "ensemble_used":       _ensemble_used,
                    "ensemble_models":     _ensemble_result.get("effective_models", 1) if _ensemble_result else 1,
                    "ensemble_disagreement": (
                        _ensemble_result.get("disagreement", {}).get("description", "")
                        if _ensemble_result else ""
                    ),
                    "ensemble_model_weights": (
                        _ensemble_result.get("model_weights", {}) if _ensemble_result else {}
                    ),
                    # Simulation array for fair-value odds explorer / slider
                    "simulated_results": simulation_output.get("simulated_results", []),
                }

                # ── Phase 2: DFS Fixed-Payout Metrics ───────────────────────
                # Stamp quarantined target line + DFS parlay EV metrics so the
                # downstream UI can display breakeven thresholds per flex tier.
                if simulation_output.get("prop_target_line"):
                    full_result["prop_target_line"] = simulation_output["prop_target_line"]
                    full_result["probability_over_target"] = simulation_output.get(
                        "probability_over_target", probability_over
                    )
                if simulation_output.get("dfs_breakevens"):
                    full_result["dfs_breakevens"] = simulation_output["dfs_breakevens"]
                if simulation_output.get("dfs_parlay_ev"):
                    full_result["dfs_parlay_ev"] = simulation_output["dfs_parlay_ev"]
                if simulation_output.get("dfs_platform"):
                    full_result["dfs_platform"] = simulation_output["dfs_platform"]

                # ── Bet Classification ──────────────────────────────────────
                # Primary classification is driven by line_category (from the
                # ingestion layer).  Statistical overlay applies to
                # standard-line picks.  Risk flags (conflicting forces, variance,
                # fatigue, regression) are separate from bet_type and feed into
                # the avoid-list system via is_uncertain.
                try:
                    _season_avg_for_classify = float(player_data.get(f"{stat_type}_avg", 0) or 0) or None
                    # Determine the source of the prop line so the classifier can
                    # validate whether it is a real platform line or a synthetic one.
                    _line_source = prop.get("platform") or prop.get("line_source") or "synthetic"
                    _standard_line = prop.get("standard_line", None)
                    _bet_classification = classify_bet_type(
                        probability_over=probability_over,
                        edge_percentage=edge_pct,
                        stat_standard_deviation=stat_std,
                        projected_stat=projected_stat,
                        prop_line=prop_line,
                        stat_type=stat_type,
                        directional_forces_result=forces_result,
                        rest_days=game_context.get("rest_days", 1),
                        vegas_spread=game_context.get("vegas_spread", 0.0),
                        recent_form_ratio=projection_result.get("recent_form_ratio"),
                        season_average=_season_avg_for_classify,
                        line_source=_line_source,
                    )
                    full_result["bet_type"]        = _bet_classification.get("bet_type", "standard")
                    full_result["bet_type_emoji"]  = _bet_classification.get("bet_type_emoji", "")
                    full_result["bet_type_label"]  = _bet_classification.get("bet_type_label", "Standard Bet")
                    full_result["bet_type_reasons"]= _bet_classification.get("reasons", [])
                    full_result["std_devs_from_line"] = _bet_classification.get("std_devs_from_line", 0.0)
                    full_result["line_verified"]   = _bet_classification.get("line_verified", True)
                    full_result["line_reliability_warning"] = _bet_classification.get("line_reliability_warning")
                    full_result["standard_line"]   = _standard_line
                    full_result["risk_flags"]      = _bet_classification.get("risk_flags", [])
                    full_result["is_uncertain"]    = _bet_classification.get("is_uncertain", False)
                    # Risk flags (conflicting forces, high-variance stat, etc.) are
                    # informational — they appear on the card UI as warnings but do NOT
                    # block the pick from being displayed or auto-logged.  The genuine
                    # should_avoid decision comes from should_avoid_prop() only.
                except Exception:
                    full_result["bet_type"]         = "standard"
                    full_result["bet_type_emoji"]   = ""
                    full_result["bet_type_label"]   = "Standard Bet"
                    full_result["bet_type_reasons"] = []
                    full_result["std_devs_from_line"] = 0.0
                    full_result["line_verified"]    = True
                    full_result["line_reliability_warning"] = None
                    full_result["standard_line"]    = None
                    full_result["risk_flags"]       = []
                    full_result["is_uncertain"]     = False

                # ── Capture odds from the original prop (for display) ────────
                full_result["over_odds"]  = prop.get("over_odds",  -110)
                full_result["under_odds"] = prop.get("under_odds", -110)

                # ── Alt-Line Probability Generation ──────────────────────────
                # Generate alt lines for analysis.
                # Probabilities are computed from the raw simulation distribution.
                try:
                    _alt_lines = generate_alt_line_probabilities(simulation_output, prop_line)
                    full_result["alt_lines"] = _alt_lines
                    _best_alt = _alt_lines.get("best_alt", {})
                    full_result["prediction"] = _best_alt.get("prediction", "")
                    # Override: when the bet classification says this prop IS an
                    # alt-line bet type, use the strict prediction string from the
                    # edge_detection formatter (anchored to the actual prop line)
                    # rather than the simulation-best line which may differ.
                except Exception:
                    full_result["alt_lines"] = {}
                    full_result["prediction"] = ""


                try:
                    _clv_penalties = get_stat_type_clv_penalties(days=90)
                    _clv_stat_penalty = _clv_penalties.get(stat_type, 0.0)
                    if _clv_stat_penalty > 0:
                        full_result["confidence_score"] = max(0.0, full_result["confidence_score"] - _clv_stat_penalty)
                        full_result["clv_stat_penalty"] = _clv_stat_penalty
                except Exception:
                    pass

                # ── Feature 9: Market movement adjustment ────────────────────
                try:
                    if _get_detect_line_movement() is not None:
                        _opening_snap = st.session_state.get("line_snapshots", {}).get(
                            f"{player_name}_{stat_type}", {}
                        )
                        if _opening_snap:
                            _mv = detect_line_movement(
                                player_name, stat_type,
                                _opening_snap.get("initial_line", prop_line),
                                prop_line,
                                full_result.get("direction", "OVER"),
                            )
                            _mv_adj = _mv.get("confidence_adjustment", 0.0)
                            if _mv_adj != 0.0:
                                full_result["confidence_score"] = max(0.0, min(100.0, full_result["confidence_score"] + _mv_adj))
                                full_result["market_movement"] = _mv
                except Exception:
                    pass

                # ── Composite Win Score ───────────────────────────────────────
                # Single 0-100 score combining all signals for quick sorting.
                try:
                    _dir = full_result.get("direction", "OVER")
                    _prob_in_dir = (
                        full_result.get("probability_over", 0.5)
                        if _dir == "OVER"
                        else full_result.get("probability_under", 0.5)
                    )
                    _streak_mult = projection_result.get("streak_multiplier", 1.0)
                    _cws_result = calculate_composite_win_score(
                        probability_in_direction=_prob_in_dir,
                        confidence_score=full_result.get("confidence_score", 50),
                        edge_percentage=full_result.get("edge_percentage", 0),
                        directional_forces_result=full_result.get("forces"),
                        streak_multiplier=_streak_mult,
                        risk_score=5.0,
                        is_coin_flip=full_result.get("is_coin_flip", False),
                        should_avoid=full_result.get("should_avoid", False),
                    )
                    full_result["composite_win_score"] = _cws_result["composite_win_score"]
                    full_result["win_score_grade"] = _cws_result["grade"]
                    full_result["win_score_label"] = _cws_result["grade_label"]
                except Exception:
                    full_result["composite_win_score"] = 0.0
                    full_result["win_score_grade"] = "F"
                    full_result["win_score_label"] = "Error"

                analysis_results_list.append(full_result)

                # ── Change 10: Store in simulation cache ──────────────
                _sim_cache[_cache_k] = full_result

            except Exception as _prop_loop_err:
                _logger.warning(
                    "Prop #%d (%s/%s) analysis failed — skipped: %s",
                    prop_index,
                    prop.get('player_name', '?'),
                    prop.get('stat_type', '?'),
                    _prop_loop_err,
                )
                # Build a minimal error result so this prop is still visible
                _err_name = prop.get('player_name', '')
                _err_stat = prop.get('stat_type', 'points').lower()
                _err_line = float(prop.get('line', 0))
                analysis_results_list.append({
                    "player_name": _err_name,
                    "team": prop.get("team", ""),
                    "player_team": prop.get("team", ""),
                    "player_position": "",
                    "stat_type": _err_stat,
                    "line": _err_line,
                    "platform": prop.get("platform", "DraftKings"),
                    "season_pts_avg": 0, "season_reb_avg": 0, "season_ast_avg": 0,
                    "points_avg": 0, "rebounds_avg": 0, "assists_avg": 0,
                    "opponent": "",
                    "is_home": None,
                    "probability_over": 0.5, "probability_under": 0.5,
                    "simulated_mean": _err_line, "simulated_std": 0.0,
                    "percentile_10": 0.0, "percentile_50": 0.0, "percentile_90": 0.0,
                    "adjusted_projection": _err_line, "overall_adjustment": 1.0,
                    "recent_form_ratio": None, "games_played": None,
                    "edge_percentage": 0.0, "confidence_score": 0,
                    "tier": "Bronze", "tier_emoji": "🥉",
                    "direction": "OVER",
                    "recommendation": f"⚠️ Analysis error for {_err_name} ({_err_stat})",
                    "forces": {"over_forces": [], "under_forces": []},
                    "should_avoid": True,
                    "avoid_reasons": [f"Analysis error: {_prop_loop_err}"],
                    "histogram": [], "score_breakdown": {},
                    "line_vs_avg_pct": 0, "recent_form_results": [],
                    "player_matched": False, "explanation": None,
                    "line_sharpness_force": None, "line_sharpness_penalty": 0.0,
                    "trap_line_result": {}, "trap_line_penalty": 0.0,
                    "teammate_out_notes": [], "minutes_adjustment_factor": 1.0,
                    "player_is_out": False,
                    "player_status": "Analysis Error",
                    "player_status_note": str(_prop_loop_err),
                    "player_id": "",
                    "composite_win_score": 0.0,
                    "win_score_grade": "F",
                    "win_score_label": "Error",
                })

        # Detect correlated props
        correlation_warnings = detect_correlated_props(analysis_results_list)
        for idx, warning in correlation_warnings.items():
            if idx < len(analysis_results_list):
                analysis_results_list[idx]["_correlation_warning"] = warning

        # ── Auto-trigger Smart Update if >20% of players are unmatched ─
        # Unmatched players use skeleton stats which reduces accuracy.
        # Loading fresh rosters resolves most mismatches without user action.
        _unmatched_players = list(dict.fromkeys(
            r.get("player_name", "")
            for r in analysis_results_list
            if not r.get("player_matched", True) and not r.get("player_is_out", False)
        ))
        _total_non_out = sum(
            1 for r in analysis_results_list if not r.get("player_is_out", False)
        )
        _unmatched_ratio = len(_unmatched_players) / max(_total_non_out, 1)
        if (
            _unmatched_ratio > 0.20
            and todays_games
            and not st.session_state.get("_smart_update_attempted")
        ):
            # Guard: only attempt the auto-update once per session to
            # prevent an infinite rerun loop when the fetch always fails
            # or the mismatch persists after updating.
            st.session_state["_smart_update_attempted"] = True
            st.info(
                f"🔄 **{len(_unmatched_players)} player(s) not found** in local database "
                f"({_unmatched_ratio*100:.0f}% of props). Triggering Smart Roster Update…"
            )
            try:
                from data.nba_data_service import get_todays_players as _get_today
                _roster_result = _get_today(todays_games, progress_callback=None)
                if _roster_result:
                    # Re-run the full analysis now that players.csv is populated.
                    # Simply clearing the analysis cache and re-running the page gives
                    # every player a complete projection from real season averages
                    # rather than the position-prior estimates used above.
                    try:
                        load_players_data.clear()  # bust Streamlit's CSV cache
                    except Exception:
                        pass
                    st.success(
                        f"✅ Smart Roster Update complete — re-running analysis with "
                        f"fresh player data for {len(_unmatched_players)} player(s)."
                    )
                    st.rerun()
            except Exception as _su_err:
                # Non-fatal — proceed with existing results
                _logger.warning(f"Smart Update error (non-fatal): {_su_err}")

        # ── Sort all analyzed bets by composite win score (keep every single pick) ──
        # The engine analyzes ALL available props and returns ALL of them
        # sorted by composite win score (multi-factor: probability + confidence +
        # edge + forces + streak + risk).  Out players are kept at the end for
        # transparency.  No artificial truncation — every prop is shown.
        _total_analyzed = len(analysis_results_list)
        _out_results = [r for r in analysis_results_list if r.get("player_is_out", False)]
        _active_results = [r for r in analysis_results_list if not r.get("player_is_out", False)]
        _active_results.sort(key=lambda r: r.get("composite_win_score", 0), reverse=True)
        _selected_active = _active_results  # Keep ALL active results — no truncation
        analysis_results_list = _selected_active + _out_results
        _logger.info(
            "QME 5.6 Output: %d analyzed → %d active + %d Out = %d total",
            _total_analyzed, len(_selected_active), len(_out_results), len(analysis_results_list),
        )

        st.session_state["analysis_results"] = analysis_results_list
        st.session_state["analysis_timestamp"] = datetime.datetime.now()
        # Clear the requested flag — analysis completed successfully.
        st.session_state.pop("_qam_analysis_requested", None)

        # ── Persist analysis session to SQLite (survives page refresh/inactivity) ──
        try:
            from tracking.database import save_analysis_session as _save_session
            _save_session(
                analysis_results=analysis_results_list,
                todays_games=st.session_state.get("todays_games", []),
                selected_picks=st.session_state.get("selected_picks", []),
            )
        except Exception as _persist_err:
            pass  # Non-fatal — session state still has results
        progress_bar.empty()
        # Dismiss the Joseph loading screen
        if _joseph_loader is not None:
            try:
                _joseph_loader.empty()
            except Exception:
                pass
        _analysis_elapsed = time.time() - _analysis_start_time
        _cache_msg = f" ({_cache_hits} cached)" if _cache_hits > 0 else ""
        st.success(
            f"✅ Analysis complete! Analyzed and displaying **{len(_selected_active)}** picks "
            f"(+ {len(_out_results)} out) in **{_analysis_elapsed:.1f}s**{_cache_msg}."
        )

        # ── Store ALL picks to all_analysis_picks table ──────────────
        try:
            from tracking.database import insert_analysis_picks as _insert_picks
            _stored = _insert_picks(analysis_results_list)
            if _stored > 0:
                _logger.info(f"Stored {_stored} analysis picks to all_analysis_picks table.")
        except Exception as _store_err:
            _logger.warning(f"Store analysis picks error (non-fatal): {_store_err}")

        # ── Auto-log all qualifying picks to the Bet Tracker ────────
        try:
            from tracking.bet_tracker import auto_log_analysis_bets as _auto_log
            _auto_logged = _auto_log(analysis_results_list, minimum_edge=minimum_edge)
            if _auto_logged > 0:
                st.info(
                    f"📊 Auto-logged **{_auto_logged}** qualifying pick(s) to the Bet Tracker."
                )
        except Exception as _auto_log_err:
            # Auto-logging is best-effort — never block the main analysis flow
            _logger.warning(f"Auto-log error (non-fatal): {_auto_log_err}")

        # NOTE: st.rerun() was removed here.  The results are already
        # stored in st.session_state["analysis_results"] and will render
        # naturally when the script continues past the ``if run_analysis:``
        # block.  The rerun was forcing a double-render which, on mobile,
        # cascaded into an infinite rerun loop (scroll → widget touch →
        # rerun → re-render → scroll → …).
    except Exception as _analysis_err:
        _err_str = str(_analysis_err)
        if "WebSocketClosedError" not in _err_str and "StreamClosedError" not in _err_str:
            st.error(f"❌ Analysis failed: {_analysis_err}")
    finally:
        try:
            progress_bar.empty()
        except Exception:
            pass
        if _joseph_loader is not None:
            try:
                _joseph_loader.empty()
            except Exception:
                pass

# ============================================================
# END SECTION: Analysis Runner
# ============================================================

# ── Auto-retry notice: if user navigated away during analysis ──
if (
    st.session_state.get("_qam_analysis_requested")
    and not st.session_state.get("analysis_results")
    and not run_analysis
):
    st.warning(
        "⚠️ **Analysis was interrupted** (you may have navigated away before it finished). "
        "Click **🚀 Run Analysis** above to restart."
    )
    st.session_state.pop("_qam_analysis_requested", None)

# ============================================================
# SECTION: Display Analysis Results
# ============================================================

analysis_results = st.session_state.get("analysis_results", [])

# NOTE: _player_news_lookup was previously built here and captured by the
# results fragment via closure.  It is now built inside the fragment itself
# to avoid closure dependencies.  Keeping a top-level reference for any
# non-fragment code that might still use it.
_player_news_lookup: dict = {}  # {player_name_lower: [news_item, ...]}
for _ni in st.session_state.get("player_news", []):
    _ni_player = _ni.get("player_name", "").strip().lower()
    if _ni_player:
        _player_news_lookup.setdefault(_ni_player, []).append(_ni)

# Show a notice if results were reloaded from the saved session
if analysis_results and st.session_state.get("_analysis_session_reloaded_at"):
    _reloaded_ts = st.session_state["_analysis_session_reloaded_at"]
    st.info(
        f"💾 **Analysis restored from saved session** (last run: {_reloaded_ts}). "
        "Results are preserved from your last analysis run — click **🚀 Run Analysis** above to refresh."
    )

# ════ JOSEPH M. SMITH LIVE BROADCAST DESK ════
# Reduce Joseph's container size by 60% on this page per design requirements.
# CSS extracted to pages/helpers/quantum_analysis_helpers.py
# Wrapped in @st.fragment so the heavy enrichment loop does NOT re-execute
# on every scroll-triggered rerun — only when the fragment itself reruns.
if analysis_results and st.session_state.get("joseph_enabled", True):
    st.markdown(_JOSEPH_DESK_SIZE_CSS, unsafe_allow_html=True)

    @st.fragment
    def _render_joseph_desk():
        """Render Joseph's Live Broadcast Desk in an isolated fragment.

        The ``enrich_player_god_mode`` loop is expensive — running it on
        every full-page rerun (triggered by mobile scroll events) was a
        major contributor to the rerun cascade.  As a fragment, this
        section only re-executes when a widget *inside* it is touched.

        Reads ``analysis_results`` from session state directly so the
        fragment stays independent of outer-scope closures.
        """
        _desk_analysis_results = st.session_state.get("analysis_results", [])
        try:
            from pages.helpers.joseph_live_desk import render_joseph_live_desk
            from data.advanced_metrics import enrich_player_god_mode
            from data.data_manager import load_players_data, load_teams_data
            from engine.joseph_bets import joseph_auto_log_bets
            from utils.joseph_widget import inject_joseph_inline_commentary

            _players = load_players_data()
            _teams = {t.get("abbreviation", "").upper(): t for t in load_teams_data()}
            _games = st.session_state.get("todays_games", [])

            _enriched = []
            for _p in _players:
                try:
                    _enriched.append(enrich_player_god_mode(_p, _games, _teams))
                except Exception:
                    _enriched.append(_p)
            _enriched_lookup = {str(p.get("name", "")).lower().strip(): p for p in _enriched}

            with st.container():
                render_joseph_live_desk(
                    analysis_results=_desk_analysis_results,
                    enriched_players=_enriched_lookup,
                    teams_data=_teams,
                    todays_games=_games,
                )

            # Use joseph_results (enriched with verdicts) for inline commentary
            # when available; fall back to raw analysis_results.
            _joseph_results = st.session_state.get("joseph_results", [])
            inject_joseph_inline_commentary(
                _joseph_results if _joseph_results else _desk_analysis_results,
                "analysis_results",
            )

            if not st.session_state.get("joseph_bets_logged", False):
                if _joseph_results:
                    _logged_count, _logged_msg = joseph_auto_log_bets(_joseph_results)
                    if _logged_count > 0:
                        st.toast(f"🎙️ {_logged_msg}")
                    st.session_state["joseph_bets_logged"] = True

            st.divider()
        except Exception as _joseph_err:
            import logging
            logging.getLogger(__name__).warning(f"Joseph Live Desk error: {_joseph_err}")

    _render_joseph_desk()
# ════ END JOSEPH LIVE DESK ════


# ── Fragment: isolate results display so widget interactions (toggles,
#    filter chips, multiselect, sort selectbox) only re-render this
#    section — NOT the entire ~2900-line page.  This is the single
#    highest-impact fix for the mobile rerun cascade.
@st.fragment
def _render_results_fragment():
    """Display analysis results inside a Streamlit fragment.

    Widgets inside this fragment (filter chips, sort controls, tier
    multiselect, etc.) will only re-run *this* function on interaction,
    preventing full-page reruns that cascade on mobile.

    All data is read from ``st.session_state`` (or via cached loaders)
    so the fragment remains **independent of outer-scope closures**
    during fragment-only re-runs.  NO outer variables are captured.
    """
    # ── Read ALL needed state directly inside the fragment ────────
    # This ensures values are fresh on every fragment re-run AND
    # eliminates closure captures that would tie the fragment to the
    # full-page execution scope.
    _frag_analysis_results = st.session_state.get("analysis_results", [])
    _frag_current_props = load_props_from_session(st.session_state)
    _frag_minimum_edge = st.session_state.get("minimum_edge_threshold", 5.0)
    _frag_todays_games = st.session_state.get("todays_games", [])
    _frag_players_data = load_players_data()

    # Build player → news lookup inside the fragment (was a closure before).
    _frag_player_news_lookup: dict = {}
    for _ni in st.session_state.get("player_news", []):
        _ni_player = _ni.get("player_name", "").strip().lower()
        if _ni_player:
            _frag_player_news_lookup.setdefault(_ni_player, []).append(_ni)

    if not _frag_analysis_results:
        # ``run_analysis`` is a momentary button — always False after the
        # initial page run, so we check the session-state flag instead.
        _analysis_running = st.session_state.get("_qam_analysis_requested", False)
        if not _analysis_running:
            if _frag_current_props:
                st.info("👆 Click **Run Analysis** to analyze all loaded props.")
            else:
                _has_games = bool(_frag_todays_games)
                if _has_games:
                    st.warning(
                        "⚠️ No props loaded yet. "
                        "Go to **🔬 Prop Scanner** and click **🤖 Auto-Generate Props for Tonight** "
                        "to instantly create props for all active players on tonight's teams — "
                        "or click **🔄 Auto-Load Tonight's Games** on the **📡 Live Games** page "
                        "to reload games and auto-generate props in one step."
                    )
                else:
                    st.warning(
                        "⚠️ No props loaded and no games found. "
                        "Start on the **📡 Live Games** page — click **🔄 Auto-Load Tonight's Games** "
                        "to load tonight's schedule and auto-generate props for all active players."
                    )
        return

    st.divider()

    # ── Show mode radio (moved here from top-level to avoid full-page reruns) ──
    _SHOW_MODE_OPTIONS = ["All picks", "Top picks only (edge ≥ threshold)"]
    _show_mode = st.radio(
        "Show:",
        _SHOW_MODE_OPTIONS,
        horizontal=True,
        index=_SHOW_MODE_OPTIONS.index(
            st.session_state.get("qam_show_mode", "All picks")
        ),
        key="_qam_show_mode_radio",
    )
    st.session_state["qam_show_mode"] = _show_mode

    # Filter results
    if _show_mode == "Top picks only (edge ≥ threshold)":
        displayed_results = [
            r for r in _frag_analysis_results
            if abs(r.get("edge_percentage", 0)) >= _frag_minimum_edge
        ]
    else:
        displayed_results = _frag_analysis_results

    # ── Feature 14: Quick Filter Chips ──────────────────────────────
    # Render filter chips as Streamlit columns of toggle buttons.
    _chip_col1, _chip_col2, _chip_col3, _chip_col4, _chip_col5 = st.columns(5)
    with _chip_col1:
        st.session_state["chip_platinum"] = st.toggle(
            "💎 Platinum Only", value=st.session_state.get("chip_platinum", False),
            key="_chip_platinum_toggle",
        )
    with _chip_col2:
        st.session_state["chip_gold_plus"] = st.toggle(
            "🥇 Gold+", value=st.session_state.get("chip_gold_plus", False),
            key="_chip_gold_plus_toggle",
        )
    with _chip_col3:
        st.session_state["chip_high_edge"] = st.toggle(
            "⚡ High Edge (≥10%)", value=st.session_state.get("chip_high_edge", False),
            key="_chip_high_edge_toggle",
        )
    with _chip_col4:
        st.session_state["chip_hot_form"] = st.toggle(
            "🔥 Hot Form", value=st.session_state.get("chip_hot_form", False),
            key="_chip_hot_form_toggle",
        )
    with _chip_col5:
        st.session_state["chip_hide_avoids"] = st.toggle(
            "❌ Hide Avoids", value=st.session_state.get("chip_hide_avoids", False),
            key="_chip_hide_avoids_toggle",
        )

    # Apply chip filters (chips are additive — if multiple are active
    # the result is the union so the user can combine Platinum + High Edge).
    _any_tier_chip = (
        st.session_state.get("chip_platinum", False)
        or st.session_state.get("chip_gold_plus", False)
    )
    if _any_tier_chip:
        _allowed_tiers: set = set()
        if st.session_state.get("chip_platinum"):
            _allowed_tiers.add("Platinum")
        if st.session_state.get("chip_gold_plus"):
            _allowed_tiers.update({"Platinum", "Gold"})
        displayed_results = [
            r for r in displayed_results if r.get("tier") in _allowed_tiers
        ]
    if st.session_state.get("chip_high_edge"):
        displayed_results = [
            r for r in displayed_results
            if abs(r.get("edge_percentage", 0)) >= 10.0
        ]
    if st.session_state.get("chip_hot_form"):
        displayed_results = [
            r for r in displayed_results
            if (r.get("recent_form_ratio") or 0) >= 1.05
        ]
    if st.session_state.get("chip_hide_avoids"):
        # Only hide avoids when the user explicitly toggles this ON.
        _avoid_count = sum(1 for r in displayed_results if r.get("should_avoid", False))
        displayed_results = [
            r for r in displayed_results
            if not r.get("should_avoid", False)
        ]
        if _avoid_count > 0:
            st.caption(
                f"ℹ️ {_avoid_count} pick(s) hidden (flagged as avoid due to "
                "low edge, high variance, or conflicting signals). "
                "Disable **❌ Hide Avoids** to reveal them."
            )

    # ── Legacy tier multiselect (still useful for multi-tier combos) ──
    _na_filter_col1, _na_filter_col2 = st.columns(2)
    with _na_filter_col1:
        _na_tier_filter = st.multiselect(
            "Filter by Tier",
            ["Platinum 💎", "Gold 🥇", "Silver 🥈", "Bronze 🥉"],
            default=[],
            key="na_tier_filter",
            help="Show only picks matching the selected tiers. Leave empty to show all tiers.",
        )
    with _na_filter_col2:
        # ── Feature 15: Sort Controls ────────────────────────────────
        _sort_options = [
            "Confidence Score ↓",
            "Edge % ↓",
            "Composite Win Score ↓",
            "Alphabetical (A→Z)",
        ]
        _qam_sort_key = st.selectbox(
            "Sort by",
            _sort_options,
            index=_sort_options.index(
                st.session_state.get("qam_sort_key", "Confidence Score ↓")
            ),
            key="_qam_sort_select",
            help="Choose how to order the analysis results.",
        )
        st.session_state["qam_sort_key"] = _qam_sort_key

    if _na_tier_filter:
        _na_tier_names = [t.split(" ")[0] for t in _na_tier_filter]
        displayed_results = [r for r in displayed_results if r.get("tier") in _na_tier_names]

    # ── Feature 15: Apply sort ───────────────────────────────────────
    if _qam_sort_key == "Confidence Score ↓":
        displayed_results.sort(key=lambda r: r.get("confidence_score", 0), reverse=True)
    elif _qam_sort_key == "Edge % ↓":
        displayed_results.sort(key=lambda r: abs(r.get("edge_percentage", 0)), reverse=True)
    elif _qam_sort_key == "Composite Win Score ↓":
        displayed_results.sort(key=lambda r: r.get("composite_win_score", 0), reverse=True)
    elif _qam_sort_key == "Alphabetical (A→Z)":
        displayed_results.sort(key=lambda r: r.get("player_name", "").lower())

    # ── Deduplicate by (player_name, stat_type, line, direction) ──
    # Prevents duplicate player cards and duplicate Streamlit element keys
    # when the same prop appears multiple times (e.g. from multiple platforms).
    _seen_result_keys: set = set()
    _deduped: list = []
    for _r in displayed_results:
        _rkey = (
            _r.get("player_name", ""),
            _r.get("stat_type", ""),
            _r.get("line", 0),
            _r.get("direction", "OVER"),
        )
        if _rkey not in _seen_result_keys:
            _seen_result_keys.add(_rkey)
            _deduped.append(_r)
    displayed_results = _deduped

    # ── Summary metrics ────────────────────────────────────────
    total_analyzed   = len(_frag_analysis_results)
    total_over_picks = sum(1 for r in displayed_results if r.get("direction") == "OVER")
    total_under_picks= sum(1 for r in displayed_results if r.get("direction") == "UNDER")
    platinum_count   = sum(1 for r in displayed_results if r.get("tier") == "Platinum")
    gold_count       = sum(1 for r in displayed_results if r.get("tier") == "Gold")
    avg_edge         = (
        sum(abs(r.get("edge_percentage", 0)) for r in displayed_results) / len(displayed_results)
        if displayed_results else 0
    )
    unmatched_count  = sum(1 for r in _frag_analysis_results if not r.get("player_matched", True))

    # Phase 3: DFS aggregate metrics
    _dfs_results = [r for r in displayed_results if r.get("dfs_parlay_ev")]
    _beats_be_count = sum(
        1 for r in _dfs_results
        if (r.get("dfs_parlay_ev") or {}).get("best_tier") is not None
    )

    st.subheader(f"📊 Results: {len(displayed_results)} picks (of {total_analyzed} analyzed)")

    sum_col1, sum_col2, sum_col3, sum_col4, sum_col5 = st.columns(5)
    sum_col1.metric("Showing",     len(displayed_results))
    sum_col2.metric("⬆️ MORE",    total_over_picks)
    sum_col3.metric("⬇️ LESS",   total_under_picks)
    sum_col4.metric("💎 Platinum", platinum_count)
    sum_col5.metric("Gold 🥇",     gold_count)

    # ── Feature 13: Summary Dashboard ──────────────────────────────
    # DFS Edge + Tier Distribution rendered inside a styled container.
    # NOTE: Previously used split st.markdown('<div class="qam-sticky-summary">')
    # and st.markdown('</div>') which risked orphaned tags if an exception
    # occurred between them, producing malformed HTML that forced Streamlit
    # to re-render and contributed to the "page restart" issue.

    # Build the summary HTML block as a single unit
    _summary_parts: list[str] = []

    # Phase 3: DFS Edge row (only shown when DFS metrics exist)
    if _dfs_results:
        _avg_dfs_edge = sum(
            (r.get("dfs_parlay_ev") or {}).get("tiers", {}).get(
                (r.get("dfs_parlay_ev") or {}).get("best_tier", 3), {}
            ).get("edge_vs_breakeven", 0) * 100
            for r in _dfs_results
            if (r.get("dfs_parlay_ev") or {}).get("best_tier") is not None
        ) / max(_beats_be_count, 1)
        _summary_parts.append(
            _render_dfs_flex_edge_html(_beats_be_count, len(_dfs_results), _avg_dfs_edge)
        )

    # ── Slate Summary Dashboard ────────────────────────────────
    silver_count  = sum(1 for r in displayed_results if r.get("tier") == "Silver")
    bronze_count  = sum(1 for r in displayed_results if r.get("tier") == "Bronze")
    best_pick     = max(
        (r for r in displayed_results if not r.get("player_is_out", False)),
        key=lambda r: r.get("confidence_score", 0),
        default=None,
    )
    _summary_parts.append(
        _render_tier_distribution_html(
            platinum_count, gold_count, silver_count, bronze_count,
            avg_edge, best_pick,
        )
    )

    # Emit as a single st.markdown call with the wrapper div
    st.markdown(
        '<div class="qam-sticky-summary">'
        + "".join(_summary_parts)
        + '</div>',
        unsafe_allow_html=True,
    )

    # ── Quick-select buttons ───────────────────────────────────
    _qb_col1, _qb_col2, _qb_col3 = st.columns([1, 1, 2])
    with _qb_col1:
        if st.button("💎 Select All Platinum", help="Add all Platinum tier picks to Entry Builder"):
            _plat_picks = [
                r for r in displayed_results
                if r.get("tier") == "Platinum"
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
            ]
            _existing_keys = {p.get("key") for p in st.session_state.get("selected_picks", [])}
            _added = 0
            for r in _plat_picks:
                _stat     = r.get("stat_type", "").lower()
                _line     = r.get("line", 0)
                _dir      = r.get("direction", "OVER")
                _pick_key = f"{r.get('player_name', '')}_{_stat}_{_line}_{_dir}"
                if _pick_key not in _existing_keys:
                    st.session_state.setdefault("selected_picks", []).append({
                        "key":             _pick_key,
                        "player_name":     r.get("player_name", ""),
                        "stat_type":       _stat,
                        "line":            _line,
                        "direction":       _dir,
                        "confidence_score": r.get("confidence_score", 0),
                        "tier":            r.get("tier", "Platinum"),
                        "tier_emoji":      "💎",
                        "platform":        r.get("platform", ""),
                        "edge_percentage": r.get("edge_percentage", 0),
                    })
                    _added += 1
            if _added:
                st.toast(f"✅ Added {_added} Platinum pick(s).")
            else:
                st.info("All Platinum picks already added.")
    with _qb_col2:
        if st.button("🥇 Select All Gold+", help="Add all Gold and Platinum tier picks to Entry Builder"):
            _gold_picks = [
                r for r in displayed_results
                if r.get("tier") in ("Platinum", "Gold")
                and not r.get("player_is_out", False)
                and not r.get("should_avoid", False)
            ]
            _existing_keys = {p.get("key") for p in st.session_state.get("selected_picks", [])}
            _added = 0
            for r in _gold_picks:
                _stat     = r.get("stat_type", "").lower()
                _line     = r.get("line", 0)
                _dir      = r.get("direction", "OVER")
                _pick_key = f"{r.get('player_name', '')}_{_stat}_{_line}_{_dir}"
                if _pick_key not in _existing_keys:
                    _t_emoji = "💎" if r.get("tier") == "Platinum" else "🥇"
                    st.session_state.setdefault("selected_picks", []).append({
                        "key":             _pick_key,
                        "player_name":     r.get("player_name", ""),
                        "stat_type":       _stat,
                        "line":            _line,
                        "direction":       _dir,
                        "confidence_score": r.get("confidence_score", 0),
                        "tier":            r.get("tier", "Gold"),
                        "tier_emoji":      _t_emoji,
                        "platform":        r.get("platform", ""),
                        "edge_percentage": r.get("edge_percentage", 0),
                    })
                    _added += 1
            if _added:
                st.toast(f"✅ Added {_added} Gold+ pick(s).")
            else:
                st.info("All Gold+ picks already added.")

    if unmatched_count > 0:
        # Deduplicate: same player may have multiple stat types, each flagged separately.
        # Only count and list each unique player name once.
        unmatched_names_deduped = list(dict.fromkeys(
            r.get("player_name", "") for r in _frag_analysis_results
            if not r.get("player_matched", True)
            and not r.get("player_is_out", False)  # exclude confirmed-out players
        ))
        unmatched_unique_count = len(unmatched_names_deduped)
        if unmatched_unique_count > 0:
            _display_names = unmatched_names_deduped[:10]
            _overflow = unmatched_unique_count - len(_display_names)
            _inline = ", ".join(_display_names) + (f" and {_overflow} more" if _overflow > 0 else "")
            st.warning(
                f"⚠️ **{unmatched_unique_count} player(s) not found** in database — "
                + _inline
                + " — results may be less accurate. Run a **Smart Update** on the Smart NBA Data page to refresh roster data."
            )
            if _overflow > 0:
                with st.expander(f"See all {unmatched_unique_count} unmatched players"):
                    st.write(", ".join(unmatched_names_deduped))

    st.divider()

    if not displayed_results:
        st.warning(
            "📭 **No picks match the current filters.** All analyzed props were filtered out. "
            "Try switching to **All picks** above, or loosen the Tier / Bet Classification filters."
        )

    # ============================================================
    # SECTION: Player News Alerts (API-NBA)
    # Show injury/trade/performance news for players in today's slate.
    # ============================================================
    _slate_players = {
        str(r.get("player_name", "")).strip().lower()
        for r in displayed_results
        if r.get("player_name")
    }
    _slate_news: list = []
    for _pname_lower in _slate_players:
        for _news_item in _frag_player_news_lookup.get(_pname_lower, []):
            _slate_news.append(_news_item)
    # Sort by impact (high > medium > low) then by published date
    _imp_order = {"high": 0, "medium": 1, "low": 2}
    _slate_news.sort(key=lambda x: (_imp_order.get(x.get("impact", "low"), 3), x.get("published_at", "")))

    if _slate_news:
        with st.expander(
            f"📰 Player News Alerts — {len(_slate_news)} item(s) for tonight's slate",
            expanded=any(n.get("impact") == "high" for n in _slate_news),
        ):
            for _na in _slate_news[:15]:
                if not _na.get("title"):
                    continue
                st.markdown(
                    _render_news_alert_html(_na),
                    unsafe_allow_html=True,
                )

    # ============================================================
    # SECTION: Market Movement Alerts (Odds API line snapshots)
    # Shows sharp-money / line-movement signals detected during analysis.
    # ============================================================
    _mm_results = [
        r for r in displayed_results
        if r.get("market_movement") and not r.get("player_is_out", False)
    ]
    if _mm_results:
        with st.expander(
            f"📉 Market Movement Alerts — {len(_mm_results)} line shift(s) detected",
            expanded=False,
        ):
            for _mm_r in _mm_results:
                st.markdown(
                    _render_market_movement_html(_mm_r),
                    unsafe_allow_html=True,
                )

    # ============================================================
    # SECTION B: Uncertain Picks (Risk Warnings — conflicting forces)
    # ============================================================
    _uncertain_picks = [
        r for r in _frag_analysis_results
        if r.get("is_uncertain", False)
        and not r.get("player_is_out", False)
    ]
    if _uncertain_picks:
        with st.expander(
            f"⚠️ Uncertain Picks — Risk Flags ({len(_uncertain_picks)}) — Conflicting Signals, Use Caution",
            expanded=False,
        ):
            st.markdown(
                _render_uncertain_header_html(),
                unsafe_allow_html=True,
            )
            for _up in _uncertain_picks:
                st.markdown(
                    _render_uncertain_pick_html(
                        _up,
                        inline_breakdown_html=_render_inline_breakdown(_up, accent_color="#ffc107"),
                    ),
                    unsafe_allow_html=True,
                )

    # ── 🏆 Best Single Bets (shown before parlays for maximum visibility) ─
    _single_bet_pool = [
        r for r in displayed_results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and r.get("tier", "Bronze") in {"Platinum", "Gold", "Silver"}
    ]
    _single_bet_pool = sorted(
        _single_bet_pool,
        key=lambda r: (r.get("confidence_score", 0), abs(r.get("edge_percentage", 0))),
        reverse=True,
    )[:8]  # Show top 8

    if _single_bet_pool:
        # ── Gold tier banner (with Gold_Logo.png) ──────────────────────
        _gold_pool = [r for r in _single_bet_pool if r.get("tier") in ("Gold", "Platinum")]
        if _gold_pool:
            _goldcol_logo, _goldcol_title = st.columns([1, 6])
            with _goldcol_logo:
                if os.path.exists(_GOLD_LOGO_PATH):
                    st.image(_GOLD_LOGO_PATH, width=110)
            with _goldcol_title:
                st.markdown(
                    _render_gold_tier_banner_html(),
                    unsafe_allow_html=True,
                )

        st.markdown(
            _render_best_single_bets_header_html(),
            unsafe_allow_html=True,
        )
        _TIER_COLORS = {"Platinum": "#c800ff", "Gold": "#ff5e00", "Silver": "#b0c0d8"}
        # Inject the shared QCM CSS once for horizontal cards
        st.markdown(_get_qcm_css(), unsafe_allow_html=True)
        for _sb in _single_bet_pool:
            _sb_tier = _sb.get("tier", "Bronze")
            _sb_color = _TIER_COLORS.get(_sb_tier, "#b0c0d8")
            _h_card_html = _build_h_card(_sb, accent_color=_sb_color)
            st.markdown(_h_card_html, unsafe_allow_html=True)

    st.divider()

    # ── 🎯 Strongly Suggested Parlays (at TOP for maximum visibility) ─
    # Rendered via components.html() iframe to avoid WebSocket-ClosedError
    # that occurs when large HTML payloads are sent over the Tornado
    # WebSocket mid-rerun.
    strategy_entries = _build_entry_strategy(displayed_results)
    if strategy_entries:
        st.markdown(
            _render_parlays_header_html(),
            unsafe_allow_html=True,
        )
        _parlay_cards = "".join(
            _render_parlay_card_html(entry, _i)
            for _i, entry in enumerate(strategy_entries)
        )
        _parlay_html = (
            f'<div class="qam-parlay-container">{_parlay_cards}</div>'
        )
        _parlay_css = _get_qcm_css()
        _render_card_iframe(_parlay_css + _parlay_html, len(strategy_entries))
    else:
        st.info("Not enough high-edge picks to build parlay combinations. Lower the edge threshold or add more props.")

    # ── Team Breakdown (when single game) ────────────────────────
    if len(_frag_todays_games) == 1:
        g = _frag_todays_games[0]
        home_t = g.get("home_team", "")
        away_t = g.get("away_team", "")
        if home_t and away_t:
            with st.expander("🏀 Team Matchup Breakdown"):
                tc1, tc2 = st.columns(2)
                from styles.theme import get_team_colors
                home_color, _ = get_team_colors(home_t)
                away_color, _ = get_team_colors(away_t)
                hw = g.get("home_wins"); hl = g.get("home_losses")
                aw = g.get("away_wins"); al = g.get("away_losses")
                home_record = f"{hw}-{hl}" if hw is not None and hl is not None and (hw > 0 or hl > 0) else "N/A"
                away_record = f"{aw}-{al}" if aw is not None and al is not None and (aw > 0 or al > 0) else "N/A"

                home_players = [
                    r.get("player_name", "") for r in _frag_analysis_results
                    if r.get("player_team") == home_t and not r.get("player_is_out", False)
                ][:5]
                away_players = [
                    r.get("player_name", "") for r in _frag_analysis_results
                    if r.get("player_team") == away_t and not r.get("player_is_out", False)
                ][:5]

                with tc1:
                    st.markdown(
                        get_qds_team_card_html(
                            team_name=home_t,
                            team_abbrev=home_t,
                            record=home_record,
                            stats=[
                                {"label": "Game Total", "value": str(g.get("game_total", "N/A"))},
                                {"label": "Spread",     "value": str(g.get("vegas_spread", "N/A"))},
                            ],
                            key_players=home_players,
                            team_color=home_color,
                        ),
                        unsafe_allow_html=True,
                    )
                with tc2:
                    st.markdown(
                        get_qds_team_card_html(
                            team_name=away_t,
                            team_abbrev=away_t,
                            record=away_record,
                            stats=[
                                {"label": "Game Total", "value": str(g.get("game_total", "N/A"))},
                                {"label": "Spread",     "value": str(g.get("vegas_spread", "N/A"))},
                            ],
                            key_players=away_players,
                            team_color=away_color,
                        ),
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── Unified Expandable Player Cards ──────────────────────────
    # Each player gets one expandable card combining their identity
    # (headshot, name, team, season stats) with all their prop
    # analysis cards.  Click a card to expand and see full analysis.
    #
    # Rendered inside a self-resizing <iframe> via _render_card_iframe()
    # rather than inline st.markdown(). This eliminates the WebSocket-
    # ClosedError crash that occurred when large HTML payloads were sent
    # over the Tornado WebSocket mid-rerun.
    _active_results = [r for r in displayed_results if not r.get("player_is_out", False)]
    _grouped = _group_props(_active_results, _frag_players_data, _frag_todays_games)

    if _grouped:
        st.markdown(
            '<h3 style="font-family:\'Orbitron\',sans-serif;color:#00C6FF;'
            'margin-bottom:8px;">🃏 Quantum Analysis Matrix</h3>'
            '<p style="color:#94A3B8;font-size:0.82rem;margin-bottom:12px;">'
            'Click any player card to expand and view their full prop analysis.</p>',
            unsafe_allow_html=True,
        )

        # Pre-compute Joseph's Platinum Lock opinion for each player
        _joseph_opinions: dict = {}
        try:
            from engine.joseph_brain import joseph_platinum_lock as _joseph_lock
            for _pname, _pdata in _grouped.items():
                _props = _pdata.get("props", [])
                _stats = (_pdata.get("vitals") or {}).get("season_stats", {})
                if _props:
                    try:
                        _joseph_opinions[_pname] = _joseph_lock(_props, _stats)
                    except Exception:
                        _logger.debug("joseph_platinum_lock failed for %s", _pname, exc_info=True)
        except ImportError:
            _logger.debug("joseph_brain not available for card opinions")

        # ── Feature 16: Collapsible Game Groups ──────────────────
        # Build team → game-matchup label mapping from todays_games.
        _team_to_game: dict[str, str] = {}
        _game_meta_map: dict[str, dict] = {}  # matchup_label → game dict
        for _g in (_frag_todays_games or []):
            _ht = (_g.get("home_team") or "").upper().strip()
            _at = (_g.get("away_team") or "").upper().strip()
            if _ht and _at:
                _matchup_label = f"{_at} @ {_ht}"
                _team_to_game[_ht] = _matchup_label
                _team_to_game[_at] = _matchup_label
                _game_meta_map[_matchup_label] = _g

        # Group players by their game matchup.
        _game_groups: dict[str, dict[str, dict]] = {}  # matchup → {player: data}
        _no_game = "Other"
        for _pname, _pdata in _grouped.items():
            # Determine team from vitals or first prop result
            _pteam = (
                (_pdata.get("vitals") or {}).get("team", "")
                or (_pdata["props"][0].get("player_team", "") if _pdata.get("props") else "")
                or (_pdata["props"][0].get("team", "") if _pdata.get("props") else "")
            ).upper().strip()
            _game_label = _team_to_game.get(_pteam, _no_game)
            _game_groups.setdefault(_game_label, {})[_pname] = _pdata

        # Render each game group as a collapsible Streamlit expander
        for _game_idx, (_game_label, _game_players) in enumerate(_game_groups.items()):
            _gp_count = len(_game_players)
            _gp_prop_count = sum(len(d.get("props", [])) for d in _game_players.values())

            # Render matchup card with team logos above the expander
            _gm = _game_meta_map.get(_game_label)
            if _gm and _game_label != _no_game:
                _mc_ht = (_gm.get("home_team") or "").upper().strip()
                _mc_at = (_gm.get("away_team") or "").upper().strip()
                _hw = _gm.get("home_wins"); _hl = _gm.get("home_losses")
                _aw = _gm.get("away_wins"); _al = _gm.get("away_losses")
                _mc_h_rec = f"{_hw}-{_hl}" if _hw is not None and _hl is not None and (_hw > 0 or _hl > 0) else ""
                _mc_a_rec = f"{_aw}-{_al}" if _aw is not None and _al is not None and (_aw > 0 or _al > 0) else ""
                st.markdown(
                    _render_game_matchup_card_html(
                        away_team=_mc_at,
                        home_team=_mc_ht,
                        away_record=_mc_a_rec,
                        home_record=_mc_h_rec,
                        n_players=_gp_count,
                        n_props=_gp_prop_count,
                    ),
                    unsafe_allow_html=True,
                )

            _expander_label = (
                f"📊 View {_gp_count} player{'s' if _gp_count != 1 else ''}"
                f", {_gp_prop_count} prop{'s' if _gp_prop_count != 1 else ''}"
            ) if _gm and _game_label != _no_game else (
                f"🏀 {_game_label} — {_gp_count} player{'s' if _gp_count != 1 else ''}"
                f", {_gp_prop_count} prop{'s' if _gp_prop_count != 1 else ''}"
            )

            with st.expander(_expander_label, expanded=(_game_idx == 0)):
                _game_opinions = {k: _joseph_opinions[k] for k in _game_players if k in _joseph_opinions}
                _game_html = _compile_unified_matrix(_game_players, _game_opinions)

                # Apply lazy-chunk logic within each game group
                _gp_keys = list(_game_players.keys())
                if len(_gp_keys) <= _LAZY_CHUNK_SIZE:
                    _render_card_iframe(_game_html, len(_game_players))
                else:
                    for _ci in range(0, len(_gp_keys), _LAZY_CHUNK_SIZE):
                        _chunk_keys = _gp_keys[_ci : _ci + _LAZY_CHUNK_SIZE]
                        _chunk_data = {k: _game_players[k] for k in _chunk_keys}
                        _chunk_opinions = {k: _game_opinions[k] for k in _chunk_keys if k in _game_opinions}
                        _chunk_html = _compile_unified_matrix(_chunk_data, _chunk_opinions)
                        _render_card_iframe(_chunk_html, len(_chunk_data))

    # Show OUT players in a separate collapsed section
    _out_display = [r for r in displayed_results if r.get("player_is_out", False)]
    if _out_display:
        _out_grouped = _group_props(_out_display, _frag_players_data, _frag_todays_games)
        if _out_grouped:
            st.markdown(
                '<div style="font-size:0.78rem;color:#64748b;margin:12px 0 4px;">'
                '⚠️ OUT / Inactive Players</div>',
                unsafe_allow_html=True,
            )
            _out_unified_html = _compile_unified_matrix(_out_grouped)
            _render_card_iframe(_out_unified_html, len(_out_grouped))

    # ── Final Verdict ─────────────────────────────────────────────
    st.divider()
    with st.expander("🏁 Final Verdict", expanded=True):
        top_picks_for_verdict = [
            r for r in displayed_results
            if not r.get("player_is_out", False)
            and not r.get("should_avoid", False)
        ][:3]

        if top_picks_for_verdict:
            top_names  = ", ".join(r.get("player_name", "") for r in top_picks_for_verdict)
            avg_conf   = round(
                sum(r.get("confidence_score", 0) for r in top_picks_for_verdict)
                / len(top_picks_for_verdict), 1
            )
            summary    = (
                f"The Quantum Matrix Engine 5.6 identified {len(top_picks_for_verdict)} high-confidence "
                f"props led by {top_names}, with a composite confidence score of {avg_conf}/100. "
                f"Layer 5 injury validation and Quantum Matrix Engine 5.6 simulation align on these selections."
            )
        else:
            summary = (
                "No high-confidence picks were identified in the current analysis. "
                "Review injury status updates and consider adjusting your prop list."
            )

        recs = [
            "Focus on Platinum and Gold tier picks for maximum confidence.",
            "Avoid props flagged on the avoid list or with active GTD designations.",
            "Use the Entry Strategy Matrix to build 2-, 3-, or 5-leg combos.",
            "Confirm injury status via 📡 Smart NBA Data before placing bets.",
        ]
        st.markdown(
            get_qds_final_verdict_html(summary, recs),
            unsafe_allow_html=True,
        )

    # ── Floating selected-picks counter ──────────────────────────
    selected_count = len(st.session_state.get("selected_picks", []))
    if selected_count > 0:
        st.success(
            f"✅ {selected_count} pick(s) selected for Entry Builder → "
            "Go to 🧬 Entry Builder to build your entry!"
        )

    if st.session_state.get("selected_picks"):
        if st.button("🗑️ Clear Selected Picks"):
            st.session_state["selected_picks"] = []
            st.toast("🗑️ Selected picks cleared.")


_render_results_fragment()

# ============================================================
# END SECTION: Display Analysis Results
# ============================================================
