# ============================================================
# FILE: utils/components.py
# PURPOSE: Shared UI components for the SmartBetPro NBA app.
#          Contains the global settings popover that can be
#          injected into any page's sidebar or header.
# ============================================================

import os
import base64
import functools
import logging
import time as _time_mod
import streamlit as st

_components_logger = logging.getLogger(__name__)


# ── Cached Smart Pick Pro Logo Loader ──────────────────────────────────────
@functools.lru_cache(maxsize=1)
def _get_spp_logo_b64() -> str:
    """Load the Smart Pick Pro logo and return base64-encoded string (cached)."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "..", "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "Smart_Pick_Pro_Logo.png"),
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


@functools.lru_cache(maxsize=1)
def _get_spp_logo_path() -> str:
    """Return the resolved file-system path to the Smart Pick Pro logo (cached)."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "..", "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "assets", "Smart_Pick_Pro_Logo.png"),
        os.path.join(os.getcwd(), "Smart_Pick_Pro_Logo.png"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            return norm
    return ""


# ── Cached Hero Banner Loader ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _get_hero_banner_b64() -> str:
    """Load the Joseph M Smith Hero Banner and return base64-encoded string."""
    _this = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_this, "..", "Joseph M Smith Hero Banner.png"),
        os.path.join(os.getcwd(), "Joseph M Smith Hero Banner.png"),
        os.path.join(_this, "..", "assets", "Joseph M Smith Hero Banner.png"),
    ]
    for path in candidates:
        norm = os.path.normpath(path)
        if os.path.isfile(norm):
            try:
                with open(norm, "rb") as fh:
                    _components_logger.debug("Hero banner loaded from %s", norm)
                    return base64.b64encode(fh.read()).decode("utf-8")
            except Exception:
                _components_logger.warning("Failed reading hero banner at %s", norm)
    _components_logger.warning("Joseph hero banner not found in any candidate path")
    return ""


def render_joseph_hero_banner() -> None:
    """Render the Joseph M Smith Hero Banner at the top of the page."""
    b64 = _get_hero_banner_b64()
    if not b64:
        return
    st.markdown(
        f'<div style="width:100%;margin-bottom:12px;">'
        f'<img src="data:image/png;base64,{b64}" '
        f'style="width:100%;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.4);" '
        f'alt="Joseph M Smith Hero Banner" />'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_global_settings():
    """Render an inline settings popover for edge threshold and simulation depth.

    Uses ``st.popover`` so users can adjust core engine parameters without
    leaving the current page.  Widget values are bound directly to
    ``st.session_state`` keys that the analysis engine already reads
    (``minimum_edge_threshold``, ``simulation_depth``), so changes
    propagate instantly on the next rerun.
    """
    with st.popover("⚙️ Settings"):
        st.markdown(
            "**Quantum Matrix Engine 5.6 — Quick Settings**"
        )

        # ── Simulation Depth ──────────────────────────────────────
        st.number_input(
            "Simulation Depth",
            min_value=100,
            max_value=10000,
            step=100,
            value=st.session_state.get("simulation_depth", 1000),
            key="sim_depth_widget",
            help="Number of Quantum Matrix simulations per prop. Higher = more accurate but slower.",
            on_change=_sync_sim_depth,
        )

        # ── Minimum Edge Threshold ────────────────────────────────
        st.number_input(
            "Min Edge Threshold (%)",
            min_value=0.0,
            max_value=50.0,
            step=0.5,
            value=float(st.session_state.get("minimum_edge_threshold", 5.0)),
            key="edge_threshold_widget",
            help="Only display props with an edge at or above this percentage.",
            on_change=_sync_edge_threshold,
        )

        # ── Entry Fee ─────────────────────────────────────────────
        st.number_input(
            "Entry Fee ($)",
            min_value=1.0,
            max_value=1000.0,
            step=1.0,
            value=float(st.session_state.get("entry_fee", 10.0)),
            key="entry_fee_widget",
            help="Default dollar amount per entry for EV calculations.",
            on_change=_sync_entry_fee,
        )

        st.divider()

        # ── Total Bankroll ────────────────────────────────────────
        st.number_input(
            "Total Bankroll ($)",
            min_value=10.0,
            max_value=1_000_000.0,
            step=50.0,
            value=float(st.session_state.get("total_bankroll", 1000.0)),
            key="total_bankroll_widget",
            help="Your total bankroll in dollars. Used for Kelly Criterion bet sizing.",
            on_change=_sync_total_bankroll,
        )

        # ── Kelly Multiplier ──────────────────────────────────────
        st.slider(
            "Kelly Multiplier",
            min_value=0.1,
            max_value=1.0,
            step=0.05,
            value=float(st.session_state.get("kelly_multiplier", 0.25)),
            key="kelly_multiplier_widget",
            help=(
                "Fraction of the full Kelly bet to use. "
                "0.25 = Quarter Kelly (conservative, recommended). "
                "1.0 = Full Kelly (aggressive, higher variance)."
            ),
            on_change=_sync_kelly_multiplier,
        )

        st.caption("Changes apply on next analysis run.")

    # ── Responsible Gambling Disclaimer ───────────────────────────
    render_sidebar_disclaimer()


# ── Global Broadcast Ticker ──────────────────────────────────────

_TICKER_CSS = """<style>
.joseph-broadcast-ticker{
    position:relative;overflow:hidden;
    background:rgba(7,10,19,0.92);
    border-bottom:2px solid rgba(255,94,0,0.35);
    height:32px;margin-bottom:12px;
    font-family:'Montserrat',sans-serif;
}
.joseph-broadcast-ticker::before{
    content:'🎙️ JOSEPH M. SMITH — LIVE';
    position:absolute;left:0;top:0;z-index:2;
    background:linear-gradient(90deg,#ff5e00,#ff9e00);
    color:#070a13;font-weight:700;font-size:0.7rem;
    letter-spacing:0.5px;padding:7px 14px;
    white-space:nowrap;
}
.joseph-ticker-track{
    display:flex;animation:tickerScroll 45s linear infinite;
    padding-left:260px;height:100%;align-items:center;
}
.joseph-ticker-item{
    white-space:nowrap;color:#e2e8f0;font-size:0.78rem;
    padding:0 28px;flex-shrink:0;
}
.joseph-ticker-sep{
    color:#ff5e00;padding:0 4px;flex-shrink:0;font-size:0.65rem;
}
@keyframes tickerScroll{
    0%{transform:translateX(0)}
    100%{transform:translateX(-50%)}
}
</style>"""


def _render_broadcast_ticker():
    """Render Joseph's global broadcast ticker at the top of the page.

    Shows a scrolling marquee with ambient Joseph lines on every page.
    The ticker re-renders on each page navigation so it appears site-wide.
    """
    # Build ticker items from analysis results or defaults
    ticker_items = []
    analysis = st.session_state.get("analysis_results", [])
    if analysis:
        for r in analysis[:8]:
            player = r.get("player_name", r.get("player", ""))
            verdict = r.get("verdict", "")
            stat = r.get("stat_type", "")
            if player and verdict:
                ticker_items.append(f"{player} — {stat} {verdict}")
    if not ticker_items:
        ticker_items = [
            "Joseph M. Smith is watching EVERY line on the board tonight",
            "The models are LOADED and the analysis is READY",
            "Trust the PROCESS — Joseph doesn't miss",
            "Stay locked in for LIVE updates throughout the night",
        ]

    # Duplicate for seamless loop
    items_html = ""
    for item in ticker_items * 2:
        items_html += (
            f'<span class="joseph-ticker-item">{item}</span>'
            f'<span class="joseph-ticker-sep">◆</span>'
        )

    st.markdown(_TICKER_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="joseph-broadcast-ticker">'
        f'<div class="joseph-ticker-track">{items_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_spp_nav_logo():
    """Render the Smart Pick Pro logo centered at the top of every page."""
    logo_b64 = _get_spp_logo_b64()
    if not logo_b64:
        return
    _NAV_LOGO_CSS = """
    <style>
    .spp-nav-logo-bar {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        padding: 8px 0 4px 0;
        margin-bottom: 4px;
    }
    .spp-nav-logo {
        height: 54px;
        width: auto;
        object-fit: contain;
        filter: drop-shadow(0 2px 8px rgba(0, 255, 213, 0.25));
        transition: transform 0.3s ease;
    }
    .spp-nav-logo:hover {
        transform: scale(1.05);
    }
    </style>
    """
    st.markdown(
        f'<div class="spp-nav-logo-bar">'
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'class="spp-nav-logo" alt="Smart Pick Pro" />'
        f'</div>'
        f'{_NAV_LOGO_CSS}',
        unsafe_allow_html=True,
    )


def inject_joseph_floating():
    """Render the Joseph M. Smith floating widget in the main content area.

    Delegates to :func:`utils.joseph_widget.render_joseph_floating_widget`
    so the widget appears on every page that calls this helper.
    Also renders the responsible gambling disclaimer in the sidebar,
    injects the session keep-alive script, auto-saves/restores
    critical page state, and shows the broadcast ticker.
    """
    # ── Keep session alive & restore/save page state ──────────
    _inject_session_keepalive()
    _auto_restore_page_state()
    _auto_save_page_state()

    # ── Global Broadcast Ticker ───────────────────────────────
    try:
        _render_broadcast_ticker()
    except Exception as exc:
        _components_logger.debug("broadcast ticker failed: %s", exc)

    try:
        from utils.joseph_widget import render_joseph_floating_widget
        render_joseph_floating_widget()
    except Exception as exc:
        _components_logger.debug("inject_joseph_floating failed: %s", exc)
    # Show the disclaimer on every page that calls this helper
    render_sidebar_disclaimer()


# ── Session Keep-Alive & Page State Persistence ──────────────────

def _inject_session_keepalive():
    """Inject JavaScript that keeps the Streamlit WebSocket alive and
    ensures the mobile sidebar toggle button is always accessible.

    Prevents session resets when the app tab is left open but idle
    for an extended period.  Uses periodic health-check fetches and
    visibility-change handlers to maintain the connection.

    Also injects a viewport meta tag (if missing) for proper mobile
    rendering and a MutationObserver that ensures the sidebar toggle
    button remains visible on mobile after the sidebar is closed.
    """
    if st.session_state.get("_keepalive_injected"):
        return
    st.session_state["_keepalive_injected"] = True
    st.markdown(
        """
        <script>
        (function() {
            if (window.__stKeepalive) return;
            window.__stKeepalive = true;

            /* ── Viewport meta — ensure proper mobile scaling ────── */
            if (!document.querySelector('meta[name="viewport"]')) {
                var meta = document.createElement('meta');
                meta.name = 'viewport';
                meta.content = 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes, viewport-fit=cover';
                document.head.appendChild(meta);
            }

            /* ── Periodic ping — keeps proxies / load-balancers ──── */
            var _ping = function() {
                fetch('./_stcore/health').catch(function(){});
            };
            setInterval(_ping, 90000);

            /* When the user returns to the tab after it was hidden,
               fire an immediate ping to re-establish activity. */
            document.addEventListener('visibilitychange', function() {
                if (!document.hidden) _ping();
            });

            /* ── Mobile sidebar toggle fix ────────────────────────
               Streamlit sometimes hides the sidebar toggle button
               or nests it inside an invisible parent. This observer
               ensures the toggle button is always visible and
               tappable on mobile (≤768px).

               THROTTLED to avoid feedback loops: the style mutations
               we apply (display/visibility/opacity) would re-trigger
               the MutationObserver without the throttle guard.  A
               rAF-debounced check runs at most once per animation
               frame (~16ms). */
            var _sidebarPending = false;
            function ensureSidebarToggle() {
                if (window.innerWidth > 768) return;
                if (_sidebarPending) return;
                _sidebarPending = true;
                requestAnimationFrame(function() {
                    _sidebarPending = false;
                    var selectors = [
                        '[data-testid="stSidebarCollapsedControl"]',
                        '[data-testid="collapsedControl"]'
                    ];
                    selectors.forEach(function(sel) {
                        var btn = document.querySelector(sel);
                        if (btn) {
                            btn.style.display = 'flex';
                            btn.style.visibility = 'visible';
                            btn.style.opacity = '1';
                            btn.style.pointerEvents = 'auto';
                        }
                    });
                });
            }
            /* Run once and observe DOM mutations — scoped to the
               header element for performance (avoids monitoring the
               entire body subtree). Falls back to body childList-only
               if the header is not yet rendered. */
            ensureSidebarToggle();
            var headerEl = document.querySelector('header[data-testid="stHeader"]');
            if (headerEl) {
                var obs = new MutationObserver(function() { ensureSidebarToggle(); });
                obs.observe(headerEl, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'aria-expanded'] });
            } else {
                /* Header not yet in DOM — watch body childList only
                   (lightweight) until we can scope to the header. */
                var bodyObs = new MutationObserver(function() {
                    var h = document.querySelector('header[data-testid="stHeader"]');
                    if (h) {
                        bodyObs.disconnect();
                        var obs2 = new MutationObserver(function() { ensureSidebarToggle(); });
                        obs2.observe(h, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class', 'aria-expanded'] });
                    }
                    ensureSidebarToggle();
                });
                bodyObs.observe(document.body, { childList: true, subtree: false });
            }

            /* Also run on resize in case the user rotates their phone */
            window.addEventListener('resize', ensureSidebarToggle);
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def _auto_restore_page_state():
    """Restore persisted page state from SQLite on a fresh session.

    Called once per session (guarded by ``_page_state_restored`` flag).
    Only populates keys that are not already present in session state,
    so it never overwrites data the user has generated in this session.
    """
    if st.session_state.get("_page_state_restored"):
        return
    st.session_state["_page_state_restored"] = True
    try:
        from tracking.database import load_page_state
        saved = load_page_state()
        for key, value in saved.items():
            if key not in st.session_state:
                st.session_state[key] = value
            elif isinstance(st.session_state[key], (list, dict)) and not st.session_state[key] and value:
                # Replace empty defaults with saved non-empty data
                st.session_state[key] = value
    except Exception as exc:
        _components_logger.debug("_auto_restore_page_state failed: %s", exc)


def _auto_save_page_state():
    """Persist critical page state to SQLite, debounced to at most once per 30 seconds.

    This avoids heavy SQLite writes on every single rerender while still
    ensuring data is saved frequently enough to survive session resets.
    """
    _SAVE_INTERVAL = 30  # seconds
    _now = _time_mod.time()
    _last = st.session_state.get("_page_state_last_save_ts", 0)
    if _now - _last < _SAVE_INTERVAL:
        return  # Skip — too soon since last save
    try:
        from tracking.database import save_page_state
        save_page_state(st.session_state)
        st.session_state["_page_state_last_save_ts"] = _now
    except Exception as exc:
        _components_logger.debug("_auto_save_page_state failed: %s", exc)


def render_sidebar_disclaimer():
    """Render a collapsed responsible gambling disclaimer in the sidebar.

    Uses a session-state flag to avoid rendering the same disclaimer
    twice on pages that call both ``render_global_settings()`` and
    ``inject_joseph_floating()``.
    """
    if st.session_state.get("_disclaimer_rendered"):
        return
    st.session_state["_disclaimer_rendered"] = True
    with st.sidebar:
        with st.expander("⚠️ Responsible Gambling", expanded=False):
            st.caption(
                "This app is for **personal entertainment and analysis** only. "
                "Always gamble responsibly. Past model performance does not guarantee "
                "future results. Prop betting involves risk. Never bet more than you "
                "can afford to lose."
            )


# ── on_change callbacks ──────────────────────────────────────────
# These propagate widget values into the canonical session-state keys
# that the rest of the app reads (simulation_depth, minimum_edge_threshold,
# entry_fee).  Each uses .get() with a safe default in case the widget
# key hasn't been registered yet (avoids KeyError on first render).

def _sync_sim_depth():
    st.session_state["simulation_depth"] = st.session_state.get(
        "sim_depth_widget", st.session_state.get("simulation_depth", 1000)
    )
    _persist_settings()


def _sync_edge_threshold():
    st.session_state["minimum_edge_threshold"] = st.session_state.get(
        "edge_threshold_widget", st.session_state.get("minimum_edge_threshold", 5.0)
    )
    _persist_settings()


def _sync_entry_fee():
    st.session_state["entry_fee"] = st.session_state.get(
        "entry_fee_widget", st.session_state.get("entry_fee", 10.0)
    )
    _persist_settings()


def _sync_total_bankroll():
    st.session_state["total_bankroll"] = st.session_state.get(
        "total_bankroll_widget", st.session_state.get("total_bankroll", 1000.0)
    )
    _persist_settings()


def _sync_kelly_multiplier():
    st.session_state["kelly_multiplier"] = st.session_state.get(
        "kelly_multiplier_widget", st.session_state.get("kelly_multiplier", 0.25)
    )
    _persist_settings()


def _persist_settings():
    """Save the current session state settings to the database."""
    try:
        from tracking.database import save_user_settings
        save_user_settings(st.session_state)
    except Exception as exc:
        _components_logger.debug("_persist_settings failed (non-fatal): %s", exc)
