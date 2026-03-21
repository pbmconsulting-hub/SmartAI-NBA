# ============================================================
# FILE: utils/joseph_widget.py
# PURPOSE: Joseph's global sidebar widget — clickable avatar with
#          ambient commentary that appears on EVERY page. Also
#          provides inline commentary injection function for
#          result-generating pages.
# CONNECTS TO: engine/joseph_brain.py, pages/helpers/joseph_live_desk.py,
#              engine/joseph_bets.py, utils/auth.py
# ============================================================

import html as _html
import logging

try:
    import streamlit as st
except ImportError:  # pragma: no cover – unit-test environments
    st = None

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Engine imports (safe) ────────────────────────────────────
try:
    from pages.helpers.joseph_live_desk import get_joseph_avatar_b64
    _AVATAR_AVAILABLE = True
except ImportError:
    _AVATAR_AVAILABLE = False

    def get_joseph_avatar_b64() -> str:
        return ""

try:
    from engine.joseph_brain import (
        joseph_ambient_line,
        joseph_get_ambient_context,
        joseph_commentary,
    )
    _BRAIN_AVAILABLE = True
except ImportError:
    _BRAIN_AVAILABLE = False

    def joseph_ambient_line(context, **kwargs):
        return ""

    def joseph_get_ambient_context(session_state):
        return ("idle", {})

    def joseph_commentary(results, context_type):
        return ""

try:
    from engine.joseph_bets import joseph_get_track_record
    _BETS_AVAILABLE = True
except ImportError:
    _BETS_AVAILABLE = False

    def joseph_get_track_record():
        return {
            "total": 0, "wins": 0, "losses": 0, "pending": 0,
            "win_rate": 0.0, "roi_estimate": 0.0,
        }

try:
    from utils.auth import is_premium_user
    _AUTH_AVAILABLE = True
except ImportError:
    _AUTH_AVAILABLE = False

    def is_premium_user():
        return True


# ════════════════════════════════════════════════════════════════
# CSS — injected once per session via _inject_widget_css()
# ════════════════════════════════════════════════════════════════

_WIDGET_CSS = """<style>
/* ── Joseph Sidebar Container ───────────────────────────────── */
.joseph-sidebar-container{
    background:rgba(7,10,19,0.90);
    border:1px solid rgba(255,94,0,0.35);
    border-radius:12px;
    padding:12px;
    margin-top:12px;
    text-align:center;
    backdrop-filter:blur(12px);
}
/* ── Joseph Sidebar Avatar ──────────────────────────────────── */
.joseph-sidebar-avatar{
    width:56px;height:56px;border-radius:50%;
    border:2px solid #ff5e00;
    box-shadow:0 0 14px rgba(255,94,0,0.45);
    transition:transform 0.2s ease,box-shadow 0.2s ease;
}
.joseph-sidebar-avatar:hover{
    transform:scale(1.1);
    box-shadow:0 0 22px rgba(255,94,0,0.65);
}
/* ── Ambient Text ───────────────────────────────────────────── */
.joseph-ambient-text{
    color:#ff9d4d;font-size:0.76rem;font-style:italic;
    margin-top:6px;line-height:1.35;min-height:2.5em;
}
/* ── Pulse Dot ──────────────────────────────────────────────── */
.joseph-pulse-dot{
    display:inline-block;width:6px;height:6px;
    border-radius:50%;background:#ff5e00;
    animation:josephPulse 1.5s ease-in-out infinite;
    margin-right:4px;vertical-align:middle;
}
@keyframes josephPulse{
    0%,100%{opacity:0.4;transform:scale(0.8);}
    50%{opacity:1;transform:scale(1.2);}
}
/* ── Inline Commentary Card ─────────────────────────────────── */
.joseph-inline-card{
    background:rgba(7,10,19,0.90);
    border:1px solid rgba(255,94,0,0.25);
    border-radius:10px;
    padding:14px 16px;margin:12px 0;
    backdrop-filter:blur(12px);
}
.joseph-inline-avatar{
    width:36px;height:36px;border-radius:50%;
    border:2px solid #ff5e00;
    vertical-align:middle;margin-right:8px;
}
.joseph-inline-label{
    color:#ff5e00;font-weight:700;font-size:0.85rem;
}
.joseph-inline-text{
    color:#c0d0e8;font-size:0.84rem;margin-top:8px;line-height:1.5;
}
/* ── Verdict Accents ────────────────────────────────────────── */
.joseph-widget-verdict-smash{color:#ff4444;font-weight:700;}
.joseph-widget-verdict-lean{color:#00ff9d;font-weight:700;}
.joseph-widget-verdict-fade{color:#ffc800;font-weight:700;}
</style>"""


# ════════════════════════════════════════════════════════════════
# _inject_widget_css — inject once per Streamlit session
# ════════════════════════════════════════════════════════════════

def _inject_widget_css() -> None:
    """Inject the Joseph widget CSS into the page.

    Uses ``st.markdown`` with ``unsafe_allow_html=True``.
    Guarded by a session-state flag so the ``<style>`` block is
    emitted at most once per session.
    """
    if st is None:
        return
    try:
        if st.session_state.get("_joseph_widget_css_injected"):
            return
        st.markdown(_WIDGET_CSS, unsafe_allow_html=True)
        st.session_state["_joseph_widget_css_injected"] = True
    except Exception as exc:
        _logger.debug("_inject_widget_css skipped: %s", exc)


# ════════════════════════════════════════════════════════════════
# render_joseph_sidebar_widget — sidebar avatar + ambient line
# ════════════════════════════════════════════════════════════════

def render_joseph_sidebar_widget() -> None:
    """Render Joseph's sidebar widget in ``st.sidebar``.

    The widget shows:

    * Joseph's 56 px avatar with hover glow
    * A pulsing "LIVE" dot
    * A rotating ambient commentary line from
      :func:`engine.joseph_brain.joseph_ambient_line`
    * A mini track-record badge (wins / losses / ROI) when data
      is available

    Call this function once from every page's layout code so
    Joseph appears globally.
    """
    if st is None:
        return

    try:
        _inject_widget_css()
    except Exception:
        pass

    try:
        # ── Avatar image ──────────────────────────────────────
        avatar_b64 = ""
        try:
            avatar_b64 = get_joseph_avatar_b64()
        except Exception:
            pass

        if avatar_b64:
            avatar_html = (
                f'<img src="data:image/png;base64,{avatar_b64}" '
                f'class="joseph-sidebar-avatar" '
                f'alt="Joseph M. Smith" />'
            )
        else:
            avatar_html = (
                '<div class="joseph-sidebar-avatar" '
                'style="display:flex;align-items:center;justify-content:center;'
                'background:#1a1a2e;font-size:1.4rem;">🎙️</div>'
            )

        # ── Ambient commentary ────────────────────────────────
        ambient_text = ""
        try:
            session_dict = dict(st.session_state) if hasattr(st, "session_state") else {}
            context_key, ctx_kwargs = joseph_get_ambient_context(session_dict)
            ambient_text = joseph_ambient_line(context_key, **ctx_kwargs)
        except Exception as exc:
            _logger.debug("Ambient line failed: %s", exc)

        if not ambient_text:
            ambient_text = "Joseph M. Smith is ALWAYS watching the board…"

        escaped_ambient = _html.escape(ambient_text)

        # ── Track-record mini badge ───────────────────────────
        track_html = ""
        try:
            record = joseph_get_track_record()
            total = record.get("total", 0)
            if total > 0:
                wins = record.get("wins", 0)
                losses = record.get("losses", 0)
                roi = record.get("roi_estimate", 0.0)
                roi_sign = "+" if roi >= 0 else ""
                track_html = (
                    f'<div style="margin-top:8px;font-size:0.7rem;color:#94a3b8;">'
                    f'📊 {wins}W-{losses}L '
                    f'<span style="color:#00ff9d;">{roi_sign}{roi:.1f}% ROI</span>'
                    f'</div>'
                )
        except Exception:
            pass

        # ── Compose sidebar HTML ──────────────────────────────
        with st.sidebar:
            st.markdown(
                f'<div class="joseph-sidebar-container">'
                f'{avatar_html}'
                f'<div class="joseph-ambient-text">'
                f'<span class="joseph-pulse-dot"></span> '
                f'{escaped_ambient}'
                f'</div>'
                f'{track_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
    except Exception as exc:
        _logger.debug("render_joseph_sidebar_widget failed: %s", exc)


# ════════════════════════════════════════════════════════════════
# inject_joseph_inline_commentary — inline card for result pages
# ════════════════════════════════════════════════════════════════

def inject_joseph_inline_commentary(
    results: list,
    context_type: str = "analysis_results",
) -> None:
    """Inject an inline Joseph commentary card into the page.

    Designed for result-generating pages (Neural Analysis, Entry
    Builder, etc.) where Joseph reacts to the output.

    Parameters
    ----------
    results : list[dict]
        Analysis result dicts that Joseph will comment on.
    context_type : str
        Context type key for :func:`engine.joseph_brain.joseph_commentary`
        (e.g. ``"analysis_results"``, ``"entry_built"``).
    """
    if st is None:
        return
    if not results:
        return

    try:
        _inject_widget_css()
    except Exception:
        pass

    try:
        # ── Commentary text ───────────────────────────────────
        commentary = ""
        try:
            commentary = joseph_commentary(results, context_type)
        except Exception as exc:
            _logger.debug("joseph_commentary failed: %s", exc)

        if not commentary:
            return

        escaped_commentary = _html.escape(commentary)

        # ── Avatar for inline card ────────────────────────────
        avatar_b64 = ""
        try:
            avatar_b64 = get_joseph_avatar_b64()
        except Exception:
            pass

        if avatar_b64:
            inline_avatar = (
                f'<img src="data:image/png;base64,{avatar_b64}" '
                f'class="joseph-inline-avatar" alt="Joseph" />'
            )
        else:
            inline_avatar = (
                '<span class="joseph-inline-avatar" '
                'style="display:inline-flex;align-items:center;'
                'justify-content:center;background:#1a1a2e;'
                'font-size:0.9rem;">🎙️</span>'
            )

        # ── Verdict accent (check top result) ────────────────
        verdict_class = ""
        top = results[0] if results else {}
        verdict = str(top.get("verdict", top.get("joseph_verdict", ""))).upper()
        if verdict == "SMASH":
            verdict_class = " joseph-widget-verdict-smash"
        elif verdict == "LEAN":
            verdict_class = " joseph-widget-verdict-lean"
        elif verdict in ("FADE", "STAY_AWAY"):
            verdict_class = " joseph-widget-verdict-fade"

        # ── Render inline card ────────────────────────────────
        st.markdown(
            f'<div class="joseph-inline-card">'
            f'<div>'
            f'{inline_avatar}'
            f'<span class="joseph-inline-label">Joseph M. Smith</span>'
            f'</div>'
            f'<div class="joseph-inline-text{verdict_class}">'
            f'{escaped_commentary}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception as exc:
        _logger.debug("inject_joseph_inline_commentary failed: %s", exc)
